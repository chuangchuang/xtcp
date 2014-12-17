xtcp
====

xiaoyintong tcp server

Demo
----

```python
    python main.py
```

``client.py`` content:

```python
    #!/usr/bin/env python
    # coding=utf-8

    import logging
    import socket
    import timeit


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
```

Run: `` python client.py``


说明
----

通讯协议：
``request_method_len``\r\n``request_method``\r\n``request_params_len``\r\n``request_params``\r\n\r\n

- 结束符： ``\r\n\r\n``
- 分割符：``\r\n``

远程调用： ``request_method(request_params)``
