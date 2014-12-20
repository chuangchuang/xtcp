#!/usr/bin/env python
# coding=utf-8

import collections
import functools
import socket
import sys
import traceback

from tornado import gen
from tornado.concurrent import Future
from tornado.ioloop import IOLoop
from tornado.iostream import StreamClosedError
from tornado.tcpclient import TCPClient

from util import RequestContext, ResponseContext
from util import Storage
from util import XTCPConnectionException, XTCPContextException
from util import xtcp_logger


class Context(object):

    def __init__(self, host, port, af=socket.AF_INET,
                 connect_timeout=0.2, waiting_timeout=0.2, request_timeout=2):
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

    def acquire(self, request):
        response = self._io_loop.run_sync(functools.partial(self._acquire_by_request, request))
        return response

    def _acquire_by_request(self, request):
        future = Future()

        def _handle_response(success, response=None):
            if success is True:
                response_message = response
                if request.user_request_callback is not None:
                    response_message = request.user_request_callback(response)
                future.set_result(response_message)
            else:
                future.set_exc_info(response)
        request.request_callback = _handle_response
        self._acquire_loop_by_request(request)
        return future

    def _acquire_loop_by_request(self, request):
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
            xtcp_logger.debug("max_clients limits reached. {} active, {} queued requests".format(len(self.active), len(self.queue)))

    def _on_waiting_timeout(self, key):
        xtcp_logger.debug("_on_waiting_timeout : {}".format(self.waiting[key]))
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
        connection = _ClientConnection(
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


class _ClientConnection(object):

    def __init__(self, client, request, release_callback, io_loop):
        self.client = client
        self.request = request
        self.release_callback = release_callback
        self._io_loop = io_loop
        self.stream = None

        self._connection_timeout_handle = None

    def connect(self):
        self._connection_timeout_handle = self._io_loop.add_timeout(
            self._io_loop.time() + self.request.connect_timeout, self._on_connection_timeout)
        self.client.tcp_client.connect(
            self.request.host, self.request.port, self.request.af,
            max_buffer_size=self.client.max_buffer_size, callback=self.on_connect)

    def close(self):
        if self.stream is not None and not self.stream.closed():
            self.stream.close()

    def on_connect(self, stream):
        self._remove_connection_timeout()
        _on_connect_future = self._on_connect(stream)
        self._io_loop.add_future(_on_connect_future, lambda f: f.result())

    @gen.coroutine
    def _on_connect(self, stream):
        try:
            if self.request.request_callback is None:
                stream.close()
                self.release_callback()
                return
            self.stream = stream
            self.stream.set_close_callback(self._on_connection_close)
            self.stream.set_nodelay(True)
            self._handle_send_request()

            response = _ClientResponse(self, self.client, self.request, self.stream, self._io_loop)
            future = response.read()
            if self.request.request_timeout is None:
                yield future
            else:
                try:
                    yield gen.with_timeout(
                        self._io_loop.time() + self.request.request_timeout,
                        future, io_loop=self._io_loop)
                except gen.TimeoutError:
                    raise XTCPConnectionException("XTCP Client: Request Overtime")
        except Exception:
            traceback.print_exc()
        finally:
            self.close()
            self.release_callback()

    def _handle_send_request(self):
        if self.stream is not None and not self.stream.closed():
            request_context = RequestContext()
            self.stream.write(request_context.encrypt(self.request.request_message))

    def _on_connection_close(self):
        pass

    def _remove_connection_timeout(self):
        if self._connection_timeout_handle is not None:
            self._io_loop.remove_timeout(self._connection_timeout_handle)
            self._connection_timeout_handle = None

    def _on_connection_timeout(self):
        raise XTCPConnectionException("ClientConnection: Connection Timeout")


class _ClientResponse(object):

    def __init__(self, connection, client, request, stream, io_loop):
        self.connection = connection
        self.client = client
        self.request = request
        self.stream = stream
        self._io_loop = io_loop

        self._read_delimiter = "\r\n\r\n"

    def read(self):
        future = self._read_response()
        return future

    @gen.coroutine
    def _read_response(self):
        try:
            future = self.stream.read_until_regex(
                self._read_delimiter, max_bytes=self.client.max_response_size)
            response_message = yield future

            response_context = ResponseContext()
            real_response_message = response_context.decrypt(response_message)

            self.request.request_callback(True, real_response_message)
        except StreamClosedError:
            raise XTCPContextException("Response Content not regex or over max response size")
        except Exception:
            self.request.request_callback(False, sys.exc_info())
        finally:
            self.connection.close()


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.DEBUG)

    def handler_response(message):
        return "--------{}--------".format(message)
    client = XTCPClient()

    # test1
    context = Context("localhost", 8001)
    context.concat("toupper", "xiaoxiao", handler_response)
    name = client.acquire(context)
    logging.info("name: {}".format(name))

    # test1
    context = Context("localhost", 8001)
    context.concat("toupper", "wo men dou shi hao hai zi", handler_response)
    name2 = client.acquire(context)
    logging.info("name2: {}".format(name2))
