#!/usr/bin/env python
# coding=utf-8


# TODO
from tornado.ioloop import IOLoop


class TCPServer(object):

    def __init__(self, io_loop=None, max_buffer_size=None, read_chunk_size=None):
        self.io_loop = io_loop
        self._sockets = {}
        self.max_buffer_size = max_buffer_size
        self.read_chunk_size = read_chunk_size

    def listen(self, port, address=""):
        sockets = bind_sockets(port, address)
        self.add_sockets(sockets)

    def add_sockets(self, sockets):
        if self.io_loop is None:
            self.io_loop = IOLoop.current()

        for sock in sockets:
            self._sockets[sock.fileno()] = sock
