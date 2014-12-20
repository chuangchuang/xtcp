#!/usr/bin/env python
# coding=utf-8

import logging
import re

xtcp_logger = logging.getLogger("XTCP.ACCESS")

# xtcp_logger.setLevel(logging.DEBUG)

# stream_handler = logging.StreamHandler()
# stream_handler.setLevel(logging.DEBUG)

# formatter = logging.Formatter("%(name)s:%(levelname)s: %(message)s")

# stream_handler.setFormatter(formatter)
# xtcp_logger.addHandler(stream_handler)


class Storage(dict):

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


class XTCPContextException(Exception):
    pass


class XTCPConnectionException(Exception):
    pass


class XTCPServiceException(Exception):
    pass


class RequestContext(object):

    def __init__(self):
        self._delimiter = "\r\n"
        self._reg_length = re.compile(r"^\d{1,}$")
        self._reg_method = re.compile(r"^((\w)|(\.)){1,}$")

    def encrypt(self, request_message):
        method_len = len(request_message.method)
        params_len = len(request_message.params)
        message = self._delimiter.join(
            [str(method_len), request_message.method, str(params_len), request_message.params])
        return message + self._delimiter + self._delimiter

    def decrypt(self, request_message):
        try:
            method_len, method, params_len, params, _1, _2 = request_message.split(self._delimiter)
        except ValueError:
            raise XTCPContextException("XTCP Server: Malformed Client Request")
        method_len = method_len.strip()
        method = method.strip()
        params_len = params_len.strip()
        params = params.strip()

        if not self._reg_length.match(method_len) or not self._reg_length.match(params_len):
            raise XTCPContextException("XTCP Server: Malformed Client Request")
        else:
            method_len = int(method_len)
            params_len = int(params_len)
        if method_len != len(method) or params_len != len(params):
            raise XTCPContextException("XTCP Server: Malformed Client Request")
        if not self._reg_method.match(method):
            raise XTCPContextException("XTCP Server: Malformed Client Request(Request Method Not In [0-9A-Za-z_.] : {})".format(method))
        return Storage(method=method, params=params)


class ResponseContext(object):

    def __init__(self):
        self._delimiter = "\r\n"
        self._reg_length = re.compile(r"^\d{1,}$")

    def encrypt(self, response_message):
        message_len = len(response_message)
        message = self._delimiter.join([str(message_len), response_message])
        return message + self._delimiter + self._delimiter

    def _decrypt_client_message(self, message):
        response_len, response, _end_1, _end_2 = message.split(self._delimiter)
        response_len = response_len.strip()

        if not self._reg_length.match(response_len):
            raise XTCPContextException("Response Length Not Number")
        else:
            response_len = int(response_len)

        if response_len != len(response):
            raise XTCPContextException("Response Content Error")
        return response.strip()

    def decrypt(self, message):
        return self._decrypt_client_message(message)
