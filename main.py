#!/usr/bin/env python
# coding=utf-8

import logging
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
    value = name.upper()
    return "{}\r\n{}\r\n\r\n".format(len(value), value)


def info():
    return "success"


def hander_request(handler, request):
    func = getattr(sys.modules[__name__], request.request_method)
    result = func(request.request_params)
    logging.warn("({}, {})".format(request, result))
    handler.write(result)


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
