#!/usr/bin/env python
# coding=utf-8

import logging
logging.basicConfig(level=logging.DEBUG)

import signal
import sys

import tornado.autoreload
import tornado.ioloop

import server


def shutdown():
    logging.warn("Stopping XTCPServer")
    tornado.ioloop.IOLoop.instance().stop()


def sig_handler(sig, frame):
    logging.warn("Caught Signal: ({}, {})".format(sig, frame))
    tornado.ioloop.IOLoop.instance().add_callback(shutdown)


def toupper(name):
    return name.upper()


def info(v=None):
    return "success"


def hander_request(request):
    func = getattr(sys.modules[__name__], request.method)
    return func(request.params)


if __name__ == "__main__":
    port = 8001
    app = server.XTCPServer(hander_request)
    app.listen(port)

    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    instance = tornado.ioloop.IOLoop.instance()
    tornado.autoreload.start(instance)
    logging.warn("XTCPServer start => localhost:{}".format(port))
    instance.start()
