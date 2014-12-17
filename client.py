#!/usr/bin/env python
# coding=utf-8

import logging
import socket
import timeit


num = 1

send_message = ["7\r\ntoupper\r\n10\r\nchuangwang\r\n\r\n"]


def beanch():
    _message = send_message[0]

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect(("localhost", 8001))
        sock.sendall(_message)
        data = sock.recv(2014)
        logging.warn("recv: {}".format(data))
    except Exception as e:
        raise e
    finally:
        sock.close()

timeit.timeit("beanch()", setup="from __main__ import beanch", number=10)
