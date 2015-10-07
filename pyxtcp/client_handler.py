#!/usr/bin/env python
# coding=utf-8

import functools
import json

from tornado import gen

from .util import CONNECTION_TYPE_IN_REQUEST, RESPONSE_ERROR_TAG
from .util import RPCMessage, Storage, log
from .simple_client import RPCClientItem


class BasicRPCClientHandler(object):
    def __init__(self, client):
        self._client = client

    def service_name(self, service_name):
        return _BasicRPCClientServiceHandler(self._client, service_name)


class _BasicRPCClientServiceHandler(object):
    def __init__(self, client, service_name):
        self._client = client
        self._service_name = service_name

    @gen.coroutine
    def ___handler_request(self, func_name, **kwargs):
        topic_name = "{}.{}".format(self._service_name, func_name)
        body = ""
        if kwargs:
            body = json.dumps(kwargs)

        log.debug("{}({})".format(topic_name, body))
        request_message = RPCMessage(CONNECTION_TYPE_IN_REQUEST, topic_name, body)

        def _f(_message):
            log.debug("Request Message {}".format(_message.__dict__))

            status = _message.topic
            content = _message.body
            if status == RESPONSE_ERROR_TAG:
                raise gen.Return(content)

            if not content:
                raise gen.Return(content)

            v = content
            try:
                v = Storage(json.loads(content))
            except:
                v = content
            raise gen.Return(v)

        yield self._client.fetch(RPCClientItem(request_message, _f))

    def __getattr__(self, func):
        try:
            return self.__dict__[func]
        except KeyError:
            return functools.partial(self.___handler_request, func)
