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


    send_message = ["7\r\ntoupper\r\n10\r\nchuangwang\r\n\r\n", "7\r\ntoupper\r\n6\r\nchuang\r\n\r\n"]


    def beanch():
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        try:
            sock.connect(("localhost", 8001))
            sock.sendall(send_message[0])
            logging.warn("first recv: {}".format(sock.recv(1024)))

        except Exception as e:
            raise e
        finally:
            sock.close()

    beanch()
```

Run: `` python client.py``

Return: ``CHUNGWANG``


说明
----

通讯协议：
``request_method_len``\r\n``request_method``\r\n``request_params_len``\r\n``request_params``\r\n\r\n

- 结束符： ``\r\n\r\n``
- 分割符：``\r\n``

远程调用： ``request_method(request_params)``

版本变化
-------

- 0.1.0: 添加服务器端异常处理，处理解析数据超时
