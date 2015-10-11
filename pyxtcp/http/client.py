#!/usr/bin/env python
# coding=utf-8

import json
import functools
import requests

from tornado.util import ObjectDict
from .util import server_log


class RPCClient(object):
    def __init__(self, address):
        self.address = address
        self.address_prefix = "http://" + self.address

    def service_name(self, service_name):
        return _RPCClientServiceHandler(self, service_name)


class _RPCClientServiceHandler(object):
    def __init__(self, client, service_name):
        self._client = client
        self._service_name = service_name
        self._server_address_prefix = self._client.address_prefix + "/" + self._service_name

    def ___handler_request(self, func_name, **kwargs):

        kwargs_v = ""
        if kwargs:
            kwargs_v = json.dumps(kwargs)

        server_log.debug("Request To {}.{}({})".format(self._service_name, func_name, kwargs))

        request_params = {
            "v": kwargs_v
        }

        content = requests.get(
            self._server_address_prefix + "/" + func_name,
            params=request_params
        ).text
        if not content:
            return content

        try:
            return ObjectDict(json.loads(content))
        except:
            return content

    def __getattr__(self, func):
        try:
            return self.__dict__[func]
        except KeyError:
            return functools.partial(self.___handler_request, func)
