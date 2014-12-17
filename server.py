#!/usr/bin/env python
# coding=utf-8

import logging
import traceback

from tornado import ioloop
from tornado import gen
from tornado.tcpserver import TCPServer


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

    def parse_request_message(self, data):
        delimiter_len = len("\r\n")
        data = data.strip()
        requests = list()

        while data.find("\r\n") > -1:
            eol = data.find("\r\n")
            requests.append(data[:eol])
            data = data[eol + delimiter_len:]
        requests.append(data)
        self.request_method = requests[1]
        self.request_params = requests[3]

    def finish(self):
        callback = self.server.server_callback
        if callback:
            callback(self, self.request_method, self.request_params)

    def write(self, message):
        self.connection.stream.write(message)


class XTCPServerConnection(object):

    def __init__(self, server, stream, context):
        self.server = server
        self.stream = stream
        self.context = context
        self._read_delimiter = b"\r\n\r\n"
        self._read_max_bytes = 1 * 1024 * 1024  # 1M
        self._read_timeout = 200  # 200 ms

        self._request_message = None

        self._is_connection_close = False
        self.set_close_callback(self._on_connection_close)

    def set_close_callback(self, callback):
        self.stream.set_close_callback(callback)

    def _clean_callback(self):
        if self.stream is not None:
            self.set_close_callback(None)

    def _on_connection_close(self):
        self._is_connection_close = True
        self._clean_callback()

    def close(self):
        if self.stream is not None:
            self.stream.close()
        self._clean_callback()

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
            server_request.finish()
            self.close()
        except Exception:
            traceback.print_exc()
        finally:
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
                logging.warn("gen.TimeoutError : {}".format(e))
                self.close()
                raise gen.Return(False)
        except Exception as e:
            self.close()
            traceback.print_exc()
            raise gen.Return(False)
        finally:
            self._clean_callback()
        raise gen.Return(True)
