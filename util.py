#!/usr/bin/env python
# coding=utf-8

import logging

xtcp_logger = logging.getLogger("XTCP.access")
xtcp_logger.setLevel(logging.DEBUG)

# stream_handler = logging.StreamHandler()
# stream_handler.setLevel(logging.DEBUG)

# formatter = logging.Formatter("%(name)s:%(levelname)s: %(message)s")

# stream_handler.setFormatter(formatter)
# xtcp_logger.addHandler(stream_handler)


class XTCPRequestContentException(Exception):
    pass


class XTCPHandleRequestTimeoutException(Exception):
    pass


class XTCPClientConnectionException(Exception):
    pass


class Storage(dict):

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        self[name] = value
