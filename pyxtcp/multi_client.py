#!/usr/bin/env python
# coding=utf-8

import Queue
import functools
import threading
import traceback

from tornado import gen
from tornado.tcpclient import TCPClient
from tornado.ioloop import IOLoop
from tornado.iostream import StreamClosedError

from util import CONNECTION_TYPE_IN_REQUEST
from util import BasicConnection, RPCMessage, RPCConnectionError, RPCInputError
from util import log, message_utils


class _ClientContext(object):

    def __init__(self, connect_timeout=0.2, request_timeout=2):
        self.connect_timeout = connect_timeout
        self.request_timeout = request_timeout

    def set_handler_callback(self, callback):
        self._handler_callback = callback

    def get_handler_callback(self):
        return self._handler_callback


class _RPCClientConfig(object):
    def __init__(self, host, port, max_clients=5,
                 max_buffer_size=None, max_response_size=None, connect_timeout=0.2):
        self.host = host
        self.port = port
        self.address_str = "{},{}".format(self.host, self.port)
        self.max_clients = max_clients
        self.max_buffer_size = max_buffer_size
        self.max_response_size = max_response_size
        self.connect_timeout = connect_timeout


class RPCClient(object):

    def __init__(self, host, port, max_clients=5, max_buffer_size=None,
                 max_response_size=None, connect_timeout=0.2):

        self._io_loop = IOLoop.current()
        self.client_config = _RPCClientConfig(
            host=host,
            port=port,
            max_clients=max_clients,
            max_buffer_size=max_buffer_size,
            max_response_size=max_response_size,
            connect_timeout=connect_timeout
        )

        self.tcp_client = TCPClient(io_loop=self._io_loop)
        self._create_new_connection()

    def _create_new_connection(self):
        self._connection = _ClientConnection(
            client=self,
            io_loop=self._io_loop)
        self._connection.connect()
        # self._io_loop.start()

    def reset_connect(self):
        if self._connection:
            self._connection.close_connection()
        self._create_new_connection()

    def ping(self):
        def _func():
            log.warn("here!!!!!!!!!!!!!")

        self.fetch(ClientConnectionItem(RPCMessage(CONNECTION_TYPE_IN_REQUEST, "ping", ""), _func))

    def fetch(self, item):
        self._connection.add_item(item)


class _ClientConnection(BasicConnection):
    def __init__(self, client, io_loop=None):
        self.client = client
        self.client_config = client.client_config
        self._io_loop = io_loop or IOLoop.current()

        self.stream = None
        self._connection_timeout_handler = None
        self._client_connection_tubes = _ClientConnectionTubes(self, self._io_loop)
        # self._client_connection_tubes.thread.start()

    def add_item(self, item):
        self._client_connection_tubes.append(item)

    def is_avaliable_stream(self):
        return bool(self.stream is not None and not self.stream.closed())

    def set_connection_timeout_handler(self, func):
        self._connection_timeout_handler = func

    def _off_connection_timeout_handler(self):
        if self._connection_timeout_handler is not None:
            self._io_loop.remove_timeout(self._connection_timeout_handler)
            self.set_connection_timeout_handler(None)

    def connect(self):
        self.set_connection_timeout_handler(self._io_loop.add_timeout(
            deadline=self._io_loop.time() + self.client_config.connect_timeout,
            callback=self._on_connection_timeout))

        def _connect():
            return self.client.tcp_client.connect(
                host=self.client_config.host, port=self.client_config.port,
                max_buffer_size=self.client_config.max_buffer_size, callback=self._on_connection_success)

        #: tcp_client callback
        self._io_loop.run_sync(_connect)

    def _on_connection_timeout(self):
        raise RPCConnectionError("Connection Timeout {}".format(self.client_config.address_str))

    def _on_connection_success(self, stream):
        self._off_connection_timeout_handler()
        log.debug(u"Connection Success {}".format(self.client_config.address_str))

        self.stream = stream
        self.stream.set_close_callback(self._on_connection_close)

        # Nagle’s algorithm
        self.stream.set_nodelay(True)

        #: test
        self.client.ping()

    def _on_connection_close(self):
        log.info("Connection Timeout {}".format(self.client_config.address_str))

    def close(self):
        if self.is_avaliable_stream():
            self.stream.close()
            self.stream = None

    def communicate(self, item):
        if self.is_avaliable_stream():
            self.stream.write(message_utils.encrypt(item))


class _ClientConnectionTubes(object):

    def __init__(self, connection, io_loop=None):
        self.connection = connection
        self._io_loop = io_loop or IOLoop.current()
        self.client_config = self.connection.client_config

        self.queue = Queue.Queue(self.client_config.max_clients)
        self.active = {}
        self.waiting = {}
        self.thread = _ConnectionThreadingHandler(self._run_item)

    def _on_waiting_timeout(self, key):
        log.debug("_on_waiting_timeout : {}".format(self.waiting[key]))
        connection_item, waiting_timeout_handle = self.waiting[key]
        self.queue.remove((key, connection_item))
        del self.waiting[key]

    def _off_waiting_timeout(self, key):
        if key in self.waiting:
            _, func = self.waiting[key]
            if func is not None:
                self._io_loop.remove_timeout(func)
            del self.waiting[key]

    def append(self, connection_item):
        key = object()
        self.queue.put_nowait((key, connection_item))

        if not len(self.active) < self.client_config.max_clients:
            waiting_timeout_handle = self._io_loop.add_timeout(
                deadline=self._io_loop.time() + self.connection_item.waiting_timeout,
                callback=functools.partial(self._on_waiting_timeout, key))
        else:
            waiting_timeout_handle = None

        self.waiting[key] = (connection_item, waiting_timeout_handle)

        self._run_item()

    def _run_item(self):
        while self.queue and len(self.active) < self.client_config.max_clients:
            log.warn("^&^^^^^^^^^^^^^^^^^")
            key, connection_item = self.queue.get()
            log.warn((key, connection_item))
            if key not in self.waiting:
                continue

            log.warn("9999999999")
            self._off_waiting_timeout(key)
            self.active[key] = connection_item
            self._handle_connection_item(connection_item, functools.partial(self._release_connection_item, key))

    def _release_connection_item(self, key):
        del self.active[key]
        self._run_item()

    def _handle_connection_item(self, connection_item, release_callback):
        connection_item.set_release_callback(release_callback)
        # self._io_loop.run_sync(functools.partial(self._on_sending, connection_item))
        _sending_future = self._on_sending(connection_item)
        self._io_loop.add_future(_sending_future, lambda f: f.result())

    @gen.coroutine
    def _on_sending(self, connection_item):
        try:

            #: send request
            self._sending_connection_item(connection_item)
            content = yield self._read_message(connection_item)
            log.warn(content)

        except Exception:
            traceback.print_exc()

    def _sending_connection_item(self, connection_item):
        log.warn(("_send_request", connection_item.item.__dict__))
        self.connection.communicate(connection_item.item)

    @gen.coroutine
    def _read_message(self, connection_item):
        try:

            if not self.connection.is_avaliable_stream():
                log.error("Malformed Client Request stream closed")
                raise gen.Return(False)

            #: read header data
            header_data_future = self.connection.stream.read_until_regex(
                regex=message_utils.header_delimiter,
                max_bytes=connection_item.header_max_bytes
            )

            if connection_item.header_timeout is None:
                self._header_data = yield header_data_future
            else:
                try:
                    self._header_data = yield gen.with_timeout(
                        timeout=self._io_loop.time() + connection_item.header_timeout,
                        future=header_data_future,
                        io_loop=self._io_loop
                    )
                except gen.TimeoutError:
                    log.error("Timeout reading header from {}".format(self.client_config.address_str))
                    raise gen.Return(False)

            #: parse header data
            try:
                header_tube = message_utils.parse_header(
                    CONNECTION_TYPE_IN_REQUEST, self._header_data)

            except RPCInputError as e:
                log.warn(e.error)
                raise gen.Return(False)

            self._message.topic = header_tube.topic

            #: read body data
            body_data_future = self.connection.stream.read_bytes(
                header_tube.body_len + len(message_utils.body_suffix))

            if connection_item.body_timeout is None:
                self._body_data = yield body_data_future
            else:
                try:
                    self._body_data = yield gen.with_timeout(
                        timeout=self._io_loop.time() + connection_item.body_timeout,
                        future=body_data_future,
                        io_loop=self._io_loop
                    )
                except gen.TimeoutError:
                    log.error("Timeout reading body from {}".format(self.client_config.address_str))
                    raise gen.Return(False)

            #: parse body data
            try:
                body_msg = message_utils.parse_body(self._body_data)
            except RPCInputError as e:
                log.error(e.error)
                raise gen.Return(False)

            self._message.body = body_msg

        except StreamClosedError:
            raise gen.Return(False)
        raise gen.Return(True)


class _ConnectionThreadingHandler(threading.Thread):

    def __init__(self, func, group=None, target=None, name=None):
        super(_ConnectionThreadingHandler, self).__init__(group=group, target=target, name=name)
        self.func = func

    def run(self):
        self.func()


class ClientConnectionItem(object):

    def __init__(self, item, callback, header_max_bytes=None, header_timeout=None,
                 body_max_bytes=None, body_timeout=None, waiting_timeout=0.2):
        assert callback is not None

        self.item = item
        self.callback = callback
        self.header_max_bytes = header_max_bytes or 1 * 1024  # 1K
        self.header_timeout = header_timeout or 10  # 10s
        self.body_max_bytes = body_max_bytes or 10 * 1024 * 1024  # 10M
        self.body_timeout = body_timeout

    def set_release_callback(self, callback):
        self._release_callback = callback


rpc_client = RPCClient(host="127.0.0.1", port=8001)
