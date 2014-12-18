#!/usr/bin/env python
# coding=utf-8

import re
import traceback

from tornado import ioloop
from tornado import gen
from tornado.tcpserver import TCPServer

from util import xtcp_logger
from util import XTCPRequestContentException, XTCPHandleRequestTimeoutException
from util import Storage


class XTCPRequestContext(object):

    def __init__(self, stream, address):
        self.address = address


class XTCPServer(TCPServer):

    def __init__(self, callback, io_loop=None, max_buffer_size=None, read_chunk_size=None):
        super(XTCPServer, self).__init__(
            io_loop=io_loop, max_buffer_size=max_buffer_size, read_chunk_size=read_chunk_size)

        self.server_callback = callback
        self._connections = set()

    def handle_stream(self, stream, address):
        xtcp_logger.info("Connection: {} Start".format(address))
        context = XTCPRequestContext(stream, address)
        conn = XTCPServerConnection(self, stream, context)
        conn.start_handler()

    def start_request(self, connection):
        self._connections.add(connection)
        return XTCPServerRequest(self, connection)

    def close_request(self, connection):
        self._connections.remove(connection)


class XTCPServerRequest(object):

    def __init__(self, server, connection):
        self.server = server
        self.connection = connection
        self._delimiter = "\r\n"

        self._is_valid_request = True
        self._err_valid_request_message = None
        self._request = Storage()
        self._reg_length = re.compile(r"^\d{1,}$")
        self._reg_method = re.compile(r"^((\w)|(\.)){1,}$")

    @property
    def is_valid_request(self):
        return self._is_valid_request

    @property
    def err_valid_request_message(self):
        return self._err_valid_request_message

    def _set_request_message(self, request_method, request_params):
        self._request.request_method = request_method
        self._request.request_params = request_params

    def parse_request_message(self, data):
        try:
            try:
                method_len, method, params_len, params, _end_1, _end_2 = data.split(self._delimiter)
                method_len = method_len.strip()
                method = method.strip()
                params_len = params_len.strip()
                params = params.strip()

                if not self._reg_length.match(method_len) or not self._reg_length.match(params_len):
                    raise XTCPRequestContentException("Request Length Not Number")
                else:
                    method_len = int(method_len)
                    params_len = int(params_len)

                if method_len != len(method) or params_len != len(params):
                    raise XTCPRequestContentException("Request Content Error")
                if not self._reg_method.match(method):
                    raise XTCPRequestContentException("Request Method Not In [0-9A-Za-z_.] : {}".format(method))

                self._set_request_message(method, params)
            except ValueError:
                raise XTCPRequestContentException("Request Content Error")
        except XTCPRequestContentException as e:
            self._is_valid_request = False
            self._err_valid_request_message = e.message
            xtcp_logger.error(e.message)

    def finish(self):
        if self._valid_request:
            if self.server.server_callback:
                self.server.server_callback(self, self._request)

    def write(self, message):
        self.connection.stream.write(message)


class XTCPServerConnection(object):

    def __init__(self, server, stream, context):
        self.server = server
        self.stream = stream
        self.context = context
        self._read_delimiter = b"\r\n\r\n"
        self._read_max_bytes = 1 * 1024 * 1024  # 1M
        self._read_timeout = 0.2  # 200 ms

        self._request_message = None
        self._is_handler_request_timeout = False
        self._is_parse_request_error = (False, None)

        self._is_connection_close = False
        self.set_close_callback(self._on_connection_close)

    def set_close_callback(self, callback):
        self.stream.set_close_callback(callback)

    def _on_connection_close(self):
        if not self._is_connection_close:
            self._is_connection_close = True
            self.close()

    def close(self):
        if self.stream is not None and not self.stream.closed():
            if self._is_handler_request_timeout:
                self.stream.write("XTCP Error: Handler Request TimeoutError")
            if self._is_parse_request_error[0]:
                self.stream.write("XTCP Error: Parse Request Params => {}".format(self._is_parse_request_error[1]))
            self.stream.close()
        self._clean_callback()

    def _clean_callback(self):
        if self.stream is not None:
            self.set_close_callback(None)

    def start_handler(self):
        _server_start_handler = self._start_handler()
        # catch execption
        ioloop.IOLoop.instance().add_future(_server_start_handler, lambda f: f.result())

    @gen.coroutine
    def _start_handler(self):
        try:
            server_request = self.server.start_request(self)
            status = yield self._read_message()
            if not status:
                return
            server_request.parse_request_message(self._request_message)
            if not server_request.is_valid_request:
                self._is_parse_request_error = (True, server_request.err_valid_request_message)
            else:
                server_request.finish()
        except Exception:
            traceback.print_exc()
        finally:
            self.close()
            self.server.close_request(self)

    @gen.coroutine
    def _read_message(self):
        try:
            future = self.stream.read_until_regex(
                self._read_delimiter, max_bytes=self._read_max_bytes)
            try:
                self._request_message = yield gen.with_timeout(
                    self.stream.io_loop.time() + self._read_timeout,
                    future, io_loop=self.stream.io_loop)
            except gen.TimeoutError as e:
                xtcp_logger.error("XTCP Handler Request TimeoutError")
                self._is_handler_request_timeout = True
                raise gen.Return(False)
        except Exception:
            raise gen.Return(False)
        raise gen.Return(True)
