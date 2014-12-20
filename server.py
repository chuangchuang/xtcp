#!/usr/bin/env python
# coding=utf-8

import traceback

from tornado import gen
from tornado.ioloop import IOLoop
from tornado.tcpserver import TCPServer
from tornado.iostream import StreamClosedError

from util import xtcp_logger
from util import RequestContext, ResponseContext
from util import XTCPServiceException


class _RequestContext(object):
    def __init__(self, read_max_bytes=None, read_timeout=None):
        self.read_max_bytes = read_max_bytes or 1 * 1024 * 1024  # 1M
        self.read_timeout = read_timeout


class XTCPServer(TCPServer):

    def __init__(self, callback, io_loop=None, max_buffer_size=None, read_chunk_size=None):
        self._io_loop = io_loop or IOLoop.instance()
        super(XTCPServer, self).__init__(
            io_loop=self._io_loop, max_buffer_size=max_buffer_size, read_chunk_size=read_chunk_size)

        self.server_callback = callback
        self._connections = set()

    def handle_stream(self, stream, address):
        xtcp_logger.debug("Connection: {} Start".format(address))
        context = _RequestContext()
        conn = XTCPServerConnection(self, stream, context, io_loop=self._io_loop)
        conn.service()

    def start_request(self, connection):
        self._connections.add(connection)

    def close_request(self, connection):
        self._connections.remove(connection)


class XTCPServerConnection(object):

    def __init__(self, server, stream, context, io_loop):
        self.server = server
        self.stream = stream
        self.context = context
        self._io_loop = io_loop

        self._request_message = None

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
            self.stream.close()
        self._clean_callback()

    def _clean_callback(self):
        if self.stream is not None:
            self.set_close_callback(None)

    def service(self):
        _service_future = self._service()
        self._io_loop.add_future(_service_future, lambda f: f.result())

    @gen.coroutine
    def _service(self):
        try:
            self.server.start_request(self)

            client_request = _ClientRequest(self, self.server, self.stream, io_loop=self._io_loop)
            read_status = yield client_request.read()
            if not read_status:
                raise XTCPServiceException("XTCP Server: Malformed Client Request")
            request_context = RequestContext()
            request_message = request_context.decrypt(client_request.get_request_message())

            response_message = self._handle_server_callback(request_message)
            self._send_response(response_message)
        except Exception as e:
            traceback_info = traceback.format_exc()
            xtcp_logger.error("XTCP Server: ({}) =>\n {}".format(e, traceback_info))
            self._send_response(traceback_info)
        finally:
            self.close()
            self.server.close_request(self)

    def _handle_server_callback(self, request_message):
        if self.server.server_callback is not None:
            return self.server.server_callback(request_message)

    def _send_response(self, response_message=None):
        if response_message:
            response_context = ResponseContext()
            self.stream.write(response_context.encrypt(response_message))


class _ClientRequest(object):

    def __init__(self, connection, server, stream, io_loop):
        self.connection = connection
        self.server = server
        self.stream = stream
        self._io_loop = io_loop

        self._read_delimiter = b"\r\n\r\n"
        self._read_max_bytes = self.connection.context.read_max_bytes
        self._read_timeout = self.connection.context.read_timeout

        self._request_message = None

    def get_request_message(self):
        return self._request_message

    def read(self):
        _read_message_future = self._read_message()
        self._io_loop.add_future(_read_message_future, lambda f: f.result())
        return _read_message_future

    @gen.coroutine
    def _read_message(self):
        try:
            future = self.stream.read_until_regex(self._read_delimiter, max_bytes=self._read_max_bytes)
            if self._read_timeout is None:
                self._request_message = yield future
            else:
                try:
                    self._request_message = yield gen.with_timeout(
                        self._io_loop.time() + self._read_timeout, future, io_loop=self._io_loop)
                except gen.TimeoutError:
                    self.connection.close()
                    raise gen.Return(False)
        except StreamClosedError:
            raise gen.Return(False)
        except Exception:
            xtcp_logger.error("Uncaught exception")
            raise gen.Return(False)
        raise gen.Return(True)
