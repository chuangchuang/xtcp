#!/usr/bin/env python
# coding=utf-8

import collections
import logging
import functools
import re
import socket

from tornado import gen
from tornado.concurrent import Future
from tornado.ioloop import IOLoop
from tornado.tcpclient import TCPClient
from tornado.iostream import StreamClosedError

from util import Storage


class Context(object):

    def __init__(self, host, port, af=socket.AF_INET,
                 connect_timeout=0.2, waiting_timeout=0.2, request_timeout=0.2):
        self.host = host
        self.port = port
        self.af = af
        self.connect_timeout = connect_timeout
        self.waiting_timeout = waiting_timeout
        self.request_timeout = request_timeout

        self.request_message = Storage()
        self._request_callback = None
        self._user_request_callback = None

    def concat(self, method, params, callback):
        self.request_message.method = method
        self.request_message.params = params
        self._user_request_callback = callback

    @property
    def user_request_callback(self):
        return self._user_request_callback

    @property
    def request_callback(self):
        return self._request_callback

    @request_callback.setter
    def request_callback(self, callback):
        self._request_callback = callback


class XTCPClient(object):

    def __init__(self, io_loop=None, max_clients=10, max_buffer_size=None, max_response_size=None):
        self._io_loop = io_loop or IOLoop.instance()
        self.max_clients = max_clients
        self.max_buffer_size = max_buffer_size or 104857600  # 100M
        self.max_response_size = max_response_size or 10 * 1024 * 1024  # 10M

        self.queue = collections.deque()
        self.active = {}
        self.waiting = {}
        self._client_closed = False
        self.tcp_client = TCPClient(io_loop=self._io_loop)

    def __del__(self):
        self.close()

    def close(self):
        if not self._client_closed:
            self._client_closed = True
            self.tcp_client.close()
            self._io_loop.close()

    def fetch(self, request):
        response = self._io_loop.run_sync(functools.partial(self._get, request))
        return response

    def _get(self, request):
        future = Future()

        def _handle_response(response):
            response_message = request.user_request_callback(response)
            future.set_result(response_message)
        request.request_callback = _handle_response
        self._fetch(request)
        return future

    def _fetch(self, request):
        key = object()
        self.queue.append((key, request))
        if not len(self.active) < self.max_clients:
            waiting_timeout_handle = self._io_loop.add_timeout(
                self._io_loop.time() + self.request.waiting_timeout, functools.partial(self._on_waiting_timeout, key))
        else:
            waiting_timeout_handle = None
        self.waiting[key] = (request, waiting_timeout_handle)
        self._process_queue()
        if self.queue:
            logging.debug("max_clients limits reached. {} active, {} queued requests".format(len(self.active), len(self.queue)))

    def _on_waiting_timeout(self, key):
        logging.debug("_on_waiting_timeout : {}".format(self.waiting[key]))
        request, callback, waiting_timeout_handle = self.waiting[key]
        self.queue.remove((key, request, callback))
        del self.waiting[key]

    def _process_queue(self):
        while self.queue and len(self.active) < self.max_clients:
            key, request = self.queue.popleft()
            if key not in self.waiting:
                continue
            self._remove_waiting_timeout_request(key)
            self.active[key] = request
            self._handle_request(request, functools.partial(self._release_request, key))

    def _handle_request(self, request, release_callback):
        connection = XTCPClientConnection(
            self, io_loop=self._io_loop, request=request, release_callback=release_callback)
        connection.connect()

    def _release_request(self, key):
        del self.active[key]
        self._process_queue()

    def _remove_waiting_timeout_request(self, key):
        if key in self.waiting:
            _, timeout_handle = self.waiting[key]
            if timeout_handle is not None:
                self._io_loop.remove_timeout(timeout_handle)
            del self.waiting[key]


class XTCPClientConnection(object):

    def __init__(self, client, request, release_callback, io_loop):
        self.client = client
        self.request = request
        self.release_callback = release_callback
        self._io_loop = io_loop
        self.stream = None

        self._connection_timeout_handle = None
        self._request_timeout_handle = None

    def connect(self):
        self._connection_timeout_handle = self._io_loop.add_timeout(
            self._io_loop.time() + self.request.connect_timeout, self._on_connection_timeout)
        self.client.tcp_client.connect(
            self.request.host, self.request.port, self.request.af,
            max_buffer_size=self.client.max_buffer_size, callback=self._on_connect)

    def close(self):
        if self.stream is not None and not self.stream.closed():
            self.stream.close()

    def _on_connect(self, stream):
        try:
            self._remove_connection_timeout()
            if self.request.request_callback is None:
                stream.close()
                self.release_callback()
                return
            self.stream = stream
            self.stream.set_close_callback(self._on_connection_close)
            if self.request.request_timeout:
                self._request_timeout_handle = self._io_loop.add_timeout(
                    self._io_loop.time() + self.request.request_timeout, self._on_request_timeout)
            self.stream.set_nodelay(True)

            self._handle_send_request()
            self._handle_response()
        except Exception:
            self.close()
            raise
        finally:
            self._remove_request_timeout()
            self.release_callback()

    def _handle_send_request(self):
        if self.stream is not None and not self.stream.closed():
            context_request = XTCPRequestContext(self.request.request_message)
            self.stream.write(context_request.encrypt())

    def _handle_response(self):
        if self.stream is not None and not self.stream.closed():
            response = XTCPClientResponse(self, self.client, self.request, self.stream, self._io_loop)
            response.handle_response()

    def _on_request_timeout(self):
        logging.debug("Client Reqeust Timeout")
        if self.stream.error:
            raise self.stream.error
        raise XTCPConnectionException("Client Reqeust Timeout")

    def _on_connection_close(self):
        pass

    def _remove_connection_timeout(self):
        if self._connection_timeout_handle is not None:
            self._io_loop.remove_timeout(self._connection_timeout_handle)
            self._connection_timeout_handle = None

    def _remove_request_timeout(self):
        if self._request_timeout_handle is not None:
            self._io_loop.remove_timeout(self._request_timeout_handle)
            self._request_timeout_handle = None

    def _on_connection_timeout(self):
        raise XTCPConnectionException("XTCPClientConnection: Connection Timeout")


class XTCPClientResponse(object):

    def __init__(self, connection, client, request, stream, io_loop):
        self.connection = connection
        self.client = client
        self.request = request
        self.stream = stream
        self._io_loop = io_loop

        self._read_delimiter = "\r\n\r\n"
        self._response_context = None

    def handle_response(self):
        _future_handle_response = self._handle_response()
        # catch execption
        self._io_loop.add_future(_future_handle_response, lambda f: f.result())

    @gen.coroutine
    def _handle_response(self):
        try:
            future = self.stream.read_until_regex(
                self._read_delimiter, max_bytes=self.client.max_response_size)
            response_context = yield future

            self._response_context = XTCPResponseContext(response_context)
            real_response_message = self._response_context.decrypt()

            self.request.request_callback(real_response_message)
        except StreamClosedError:
            raise XTCPContextException("Response Content Not Regex")
        except Exception:
            raise
        finally:
            self.connection.close()


class XTCPRequestContext(object):

    def __init__(self, request_message):
        self.request_message = request_message
        self._delimiter = "\r\n"

    def encrypt(self):
        method_len = len(self.request_message.method)
        params_len = len(self.request_message.params)
        message = self._delimiter.join(
            [str(method_len), self.request_message.method, str(params_len), self.request_message.params])
        return message + self._delimiter + self._delimiter


class XTCPResponseContext(object):

    def __init__(self, message, is_client=True):
        self.message = message
        self.is_client = is_client
        self._delimiter = "\r\n"
        self._reg_length = re.compile(r"^\d{1,}$")

    def _decrypt_client_message(self):
        response_len, response, _end_1, _end_2 = self.message.split(self._delimiter)
        response_len = response_len.strip()
        response = response.strip()

        if not self._reg_length.match(response_len):
            raise XTCPContextException("Response Length Not Number")
        else:
            response_len = int(response_len)

        if response_len != len(response):
            raise XTCPContextException("Response Content Error")
        return response

    def decrypt(self):
        if self.is_client:
            return self._decrypt_client_message()


class XTCPContextException(Exception):
    pass


class XTCPConnectionException(Exception):
    pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    def handler_response(message):
        return "--------{}--------".format(message)

    client = XTCPClient()
    context = Context("localhost", 8001)
    context.concat("toupper", "xiaoxiao", handler_response)

    name = client.fetch(context)
    logging.warn("name: {}".format(name))

    context = Context("localhost", 8001)
    context.concat("toupper", "wo men dou shi hao hai zi", handler_response)
    name2 = client.fetch(context)
    logging.warn("name2: {}".format(name2))
