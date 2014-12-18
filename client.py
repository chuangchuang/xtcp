#!/usr/bin/env python
# coding=utf-8

import logging
import socket
import time
import timeit


send_message = ["8\r\ntou-pper\r\n10\r\nchuangwang\r\n\r\n", "7\r\ntoupper\r\n6\r\nchuang\r\n\r\n"]


def beanch():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect(("localhost", 8001))
        #time.sleep(5)
        sock.sendall(send_message[0])
        logging.warn("first recv: {}".format(sock.recv(1024)))

        #sock.sendall(send_message[1])
        #logging.warn("second recv: {}".format(sock.recv(1024)))
    except Exception as e:
        raise e
    finally:
        sock.close()

beanch()
#timeit.timeit("beanch()", setup="from __main__ import beanch", number=10)
