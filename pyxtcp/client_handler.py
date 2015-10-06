#!/usr/bin/env python
# coding=utf-8

import functools
import json

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

    def ___handler_request(self, func_name, **kwargs):
        topic_name = "{}.{}".format(self._service_name, func_name)
        body = ""
        if kwargs:
            body = json.dumps(kwargs)

        log.debug("{}({})".format(topic_name, body))
        request_message = RPCMessage(CONNECTION_TYPE_IN_REQUEST, topic_name, body)

        response_message = Storage()

        def _f(_message):
            log.debug("Request Message {}".format(_message.__dict__))

            status = _message.topic
            content = _message.body
            if status == RESPONSE_ERROR_TAG:
                raise content

            if not content:
                response_message.v = content
                return

            try:
                response_message.v = Storage(json.loads(content))
            except:
                response_message.v = content
            return

        self._client.fetch(RPCClientItem(request_message, _f))
        return response_message.v

    def ___handler_response(self, message):
        log.debug("Request Message {}".format(message.__dict__))

        status = message.topic
        content = message.body
        if status == RESPONSE_ERROR_TAG:
            raise content

        if not content:
            return content

        json.loads(content)

        try:
            log.warn(("*******", content))
            return Storage(json.loads(content))
        except:
            return content

    def __getattr__(self, func):
        try:
            return self.__dict__[func]
        except KeyError:
            return functools.partial(self.___handler_request, func)
