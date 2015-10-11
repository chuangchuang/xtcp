#!/usr/bin/env python
# coding=utf-8

import inspect
import functools
import logging

#: logging handler
log = logging.getLogger("pyxtcp")
_log_handler = logging.StreamHandler()
_log_formatter = logging.Formatter("[%(levelname)s][][%(asctime)s]: %(message)s")
_log_handler.setFormatter(_log_formatter)
log.addHandler(_log_handler)


CONNECTION_TYPE_IN_REQUEST = "req"
CONNECTION_TYPE_IN_RESPONSE = "res"
CONNECTION_PREFIX = {
    CONNECTION_TYPE_IN_REQUEST: "-",
    CONNECTION_TYPE_IN_RESPONSE: "="
}

RESPONSE_SUCCESS_TAG = "S"
RESPONSE_ERROR_TAG = "E"


class RPCInputError(Exception):
    def __init__(self, error):
        super(RPCInputError, self).__init__("")
        self.error = error


class RPCConnectionError(Exception):
    def __init__(self, error):
        super(RPCConnectionError, self).__init__("")
        self.error = error


class RPCServiceError(Exception):
    pass


class Storage(dict):

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value


class RPCMessage(object):
    def __init__(self, type_, topic, body):
        self.type_ = type_
        self.topic = topic
        self.body = body


class MessageUtils(object):
    def __init__(self):

        self.header_delimiter = b"\"r\"n"
        self.header_delimiter_len = len(self.header_delimiter)

        self.header_item_delimiter = b"\"t"

        self.body_suffix = b"\"r\"n"
        self.body_suffix_len = len(self.body_suffix)

    def encrypt(self, tube):
        connection_prefix = CONNECTION_PREFIX[tube.type_]
        return b"{type_}{topic_len}{item_delimiter}{topic}{item_delimiter}{body_len}{header_delimiter}{body}{body_suffix}"\
            .format(
                type_=connection_prefix, topic_len=len(tube.topic),
                item_delimiter=self.header_item_delimiter, topic=tube.topic,
                body_len=len(tube.body), header_delimiter=self.header_delimiter,
                body=tube.body, body_suffix=self.body_suffix
            )

    def parse_header(self, connection_type, message):
        connection_prefix = CONNECTION_PREFIX[connection_type]

        if not message or len(message) <= self.header_delimiter_len:
            raise RPCInputError("Malformed jx message. message is empty")
        if message[0] != connection_prefix:
            raise RPCInputError(u"Malformed jx message from {}".format(message))

        real_message = message[1:-self.header_delimiter_len]
        try:
            topic_len, topic_msg, body_len = real_message.split(self.header_item_delimiter)
            topic_len = int(topic_len)
            body_len = int(body_len)
        except ValueError:
            raise RPCInputError(u"Malformed jx message from {}".format(message))

        if len(topic_msg) != topic_len:
            raise RPCInputError(u"Multiple unequal topic length: {}, {}".format(topic_msg, topic_len))

        if topic_len <= 0:
            raise RPCInputError("Malformed jx message. message is empty")

        return Storage({
            "topic": topic_msg,
            "body_len": body_len
        })

    def parse_body(self, message):
        if (not message
                or len(message) < self.body_suffix_len
                or message[-self.body_suffix_len:] != self.body_suffix):
            raise RPCInputError(u"Malformed js body message from {}".format(message))
        return message[:-self.body_suffix_len]


message_utils = MessageUtils()


class BasicConnection(object):

    def _on_connection_close(self):
        raise NotImplementedError()

    def close(self):
        raise NotImplementedError()

    def send_success_response(self, message):
        self.communicate(RPCMessage(CONNECTION_TYPE_IN_RESPONSE, RESPONSE_SUCCESS_TAG, message))

    def send_error_response(self, message):
        self.communicate(RPCMessage(CONNECTION_TYPE_IN_RESPONSE, RESPONSE_ERROR_TAG, message))

    def send_request(self, topic, message):
        self.communicate(RPCMessage(CONNECTION_TYPE_IN_REQUEST, topic, message))

    def communicate(self, item):
        raise NotImplementedError()


SERVICE_NAME_SUFFIX = "Service"


class Service(object):
    def __init__(self):
        self._rpc = dict()

    def _get_rpc_service_name(self, frames):
        log.warn(inspect.getframeinfo(inspect.currentframe()))

    def _is_valid_service_name(self, service_name):
        if len(service_name) <= len(SERVICE_NAME_SUFFIX):
            return False
        return service_name.endswith(SERVICE_NAME_SUFFIX)

    def _get_rpc_class_name_by_frames(self, frames):
        for item in frames:
            if self._is_valid_service_name(item[3]):
                return item[3]

    def with_f_rpc(self, method):

        _last_frame = inspect.currentframe().f_back
        _last_frame_info = inspect.getframeinfo(_last_frame)
        _rpc_class_name = None
        if self._is_valid_service_name(_last_frame_info.function):
            _rpc_class_name = _last_frame_info.function
        else:
            _rpc_class_name = self._get_rpc_class_name_by_frames(inspect.getouterframes(_last_frame))

        if not _rpc_class_name:
            raise RPCServiceError("rpc class name must reg r'^(.{1,})Service$', method must is staticmethod or classmethod")

        self._rpc["{}.{}".format(_rpc_class_name, method.func_name)] = method

        @functools.wraps(method)
        def _wrapper(*args, **kwrags):
            return method(*args, **kwrags)
        return _wrapper

    def get_rpc_function(self, func_key):
        if func_key in self._rpc:
            return self._rpc[func_key]


def server_callback_by_json(service, message):
    import json
    log.debug("Request Message {}".format(message.__dict__))

    method_name = message.topic
    kwargs = {}
    if message.body:
        kwargs = json.loads(message.body)

    method = service.get_rpc_function(method_name)
    if not method:
        raise "rpc function not exist"

    result = method(**kwargs)
    if not result:
        result = ""
    return result
