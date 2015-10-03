#!/usr/bin/env python
# coding=utf-8

import traceback

from tornado import gen
from tornado.ioloop import IOLoop
from tornado.tcpserver import TCPServer
from tornado.iostream import StreamClosedError

from .util import CONNECTION_TYPE_IN_REQUEST
from .util import BasicConnection, RPCInputError, Storage
from .util import log, message_utils


__all__ = [
    "RPCServer", "RPCInputError",
]


class _ServerConfig(object):
    def __init__(self, header_max_bytes=None,
                 header_timeout=None, body_max_bytes=None, body_timeout=None):

        self.header_max_bytes = header_max_bytes or 1 * 1024  # 1K
        self.header_timeout = header_timeout
        self.body_max_bytes = body_max_bytes or 10 * 1024 * 1024  # 10M
        self.body_timeout = body_timeout

    def set_connection(self, host, port):
        self.host = host
        self.port = port
        self.address_str = "{}:{}".format(host, port)


class RPCServer(TCPServer):

    def __init__(self, server_callback, io_loop=None, max_buffer_size=None, read_chunk_size=None,
                 read_header_max_bytes=None, read_header_timeout=None,
                 read_body_max_bytes=None, read_body_timeout=None):

        #: default 100M
        max_buffer_size = max_buffer_size or 104857600
        read_header_timeout = 1

        #: default 64KB
        read_chunk_size = min(read_chunk_size or 65536, max_buffer_size // 2)

        self._io_loop = io_loop or IOLoop.instance()
        TCPServer.__init__(self, io_loop=self._io_loop,
                           max_buffer_size=max_buffer_size, read_chunk_size=read_chunk_size)

        self.server_callback = server_callback
        self.server_config = _ServerConfig(
            header_max_bytes=read_header_max_bytes,
            header_timeout=read_header_timeout,
            body_max_bytes=read_body_max_bytes,
            body_timeout=read_body_timeout
        )

        self._connections = set()

    def handle_stream(self, stream, address):

        #: set connection information
        self.server_config.set_connection(address[0], address[1])

        log.debug("Connection start {}".format(address))
        conn = _ServerConnection(self, stream, io_loop=self._io_loop)
        log.debug("Connection end {}".format(address))
        conn.start_service()

    def start_request(self, connection):
        self._connections.add(connection)

    def close_request(self, connection):
        self._connections.remove(connection)


class _ServerConnection(BasicConnection):

    def __init__(self, server, stream, io_loop):
        self.server = server
        self.stream = stream
        self.server_config = server.server_config
        self._io_loop = io_loop

        self._is_connection_close = False
        self.stream.set_close_callback(self._on_connection_close)

    def _on_connection_close(self):
        if not self._is_connection_close:
            self._is_connection_close = True
            self.close()

    def close(self):
        if self.stream is not None and not self.stream.closed():
            self.stream.close()
            self.stream.set_close_callback(None)

    def start_service(self):
        _service_future = self._service()
        self._io_loop.add_future(_service_future, lambda f: f.result())

    @gen.coroutine
    def _service(self):
        try:

            #: start request
            self.server.start_request(self)

            client_request = _ConnectionUtils(self, io_loop=self._io_loop)

            #: read content
            read_status = yield client_request.read()

            if read_status:

                #: get request message
                request_message = client_request.get_message()

                #: execute
                response_message = self._handle_server_callback(request_message)
                self.send_success_response(response_message)

            else:
                log.error("Malformed Client Request")

        except Exception:
            traceback_info = traceback.format_exc()
            self.send_error_response(traceback_info)
        finally:
            self.close()
            self.server.close_request(self)

    def _handle_server_callback(self, request_message):
        if self.server.server_callback is not None:
            return self.server.server_callback(request_message)

    def communicate(self, item):
        self.stream.write(message_utils.encrypt(item))


class _ConnectionUtils(object):

    def __init__(self, connection, io_loop):
        self.connection = connection
        self.server = connection.server
        self.stream = connection.stream
        self.server_config = connection.server_config
        self._io_loop = io_loop

        self._header_data = None
        self._body_data = None
        self._message = Storage()

    def get_message(self):
        return self._message

    def read(self):
        _read_message_future = self._read_message()
        self._io_loop.add_future(_read_message_future, lambda f: f.result())
        return _read_message_future

    @gen.coroutine
    def _read_message(self):
        try:

            #: read header data
            header_data_future = self.stream.read_until_regex(
                regex=message_utils.header_delimiter,
                max_bytes=self.server_config.header_max_bytes
            )

            if self.server_config.header_timeout is None:
                self._header_data = yield header_data_future
            else:
                try:
                    self._header_data = yield gen.with_timeout(
                        timeout=self._io_loop.time() + self.server_config.header_timeout,
                        future=header_data_future,
                        io_loop=self._io_loop
                    )
                except gen.TimeoutError:
                    self.connection.send_error_response("Timeout reading header from {}".format(self.server_config.address_str))
                    raise gen.Return(False)

            #: parse header data
            try:
                header_tube = message_utils.parse_header(
                    CONNECTION_TYPE_IN_REQUEST, self._header_data)

            except RPCInputError as e:
                self.connection.send_error_response(e.error)
                raise gen.Return(False)

            self._message.topic = header_tube.topic

            #: read body data
            body_data_future = self.stream.read_bytes(
                header_tube.body_len + len(message_utils.body_suffix))

            if self.server_config.body_timeout is None:
                self._body_data = yield body_data_future
            else:
                try:
                    self._body_data = yield gen.with_timeout(
                        timeout=self._io_loop.time() + self.server_config.body_timeout,
                        future=body_data_future,
                        io_loop=self._io_loop
                    )
                except gen.TimeoutError:
                    self.connection.send_error_response("Timeout reading body from {}".format(self.server_config.address_str))
                    raise gen.Return(False)

            #: parse body data
            try:
                body_msg = message_utils.parse_body(self._body_data)
            except RPCInputError as e:
                self.connection.send_error_response(e.error)
                raise gen.Return(False)

            self._message.body = body_msg

        except StreamClosedError:
            raise gen.Return(False)
        raise gen.Return(True)
