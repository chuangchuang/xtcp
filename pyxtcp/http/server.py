#!/usr/bin/env python
# coding=utf-8

import json
import tornado.httpserver
import tornado.ioloop
import tornado.web
from tornado.util import ObjectDict

from .util import server_log


class RPCInputError(Exception):
    pass


class RPCMethodError(Exception):
    pass


class _ServerHandler(tornado.web.RequestHandler):

    def initialize(self, service=None):
        if not service:
            raise RPCMethodError("service is empty. Please run `RPCServer.add_service`")

        self._all_service = service

    def get(self, topic=None, method=None):
        kwargs = self.get_argument("v", None)
        if kwargs is None:
            raise RPCInputError("params v is required")

        if kwargs:
            try:
                kwargs = json.loads(kwargs)
            except ValueError as e:
                raise RPCInputError("params v({}) format error".format(e))

        server_log.debug("{topic}.{method}({kwargs})".format(topic=topic, method=method, kwargs=kwargs))
        exec_method_key = "{}.{}".format(topic, method)
        exec_method = self._all_service.get_rpc_function(exec_method_key)

        if not exec_method:
            raise RPCInputError("{} not exist".format(exec_method_key))

        def _func():
            result = exec_method(**kwargs)
            data = {
                "v": result
            }
            return json.loads(data)

        return self.write(_func())

    def post(self):
        raise RPCMethodError("method POST not implement")


class RPCServer:
    def __init__(self, port, address="0.0.0.0", debug=False):
        self._server_host = address
        self._server_port = port

        self.settings = ObjectDict(dict(
            debug=debug,
            gzip=True))

    def add_service(self, service):
        self._server_urls = [
            ("/([^/]*)/([^/]*)", _ServerHandler, dict(service=service)),
            ("/", _ServerHandler, dict(service=service)),
        ]

    def _get_application(self):
        return tornado.web.Application(self._server_urls, **self.settings)

    def run(self):
        server = tornado.httpserver.HTTPServer(self._get_application())
        server.listen(port=self._server_port, address=self._server_host)

        server_log.debug("Start(Debug: {}) : {}:{}".format(
            self.settings.debug, self._server_host, self._server_port))
        tornado.ioloop.IOLoop.current().start()
