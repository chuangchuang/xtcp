xtcp
====

xiaoyintong tcp server

Demo
----

- 启动服务器

    ``main.py`` content:

    ```python
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
    ```

- 客户端程序:

    ``client.py`` content:

    ```python
        if __name__ == "__main__":
            import logging
            logging.basicConfig(level=logging.DEBUG)

            def handler_response(message):
                return "--------{}--------".format(message)
            client = XTCPClient()

            # test1
            context = Context("localhost", 8001)
            context.concat("toupper", "xiaoxiao", handler_response)
            name = client.acquire(context)
            logging.warn("name: {}".format(name))

            # test2
            context = Context("localhost", 8001)
            context.concat("toupper", "wo men dou shi hao hai zi", handler_response)
            name2 = client.acquire(context)
            logging.warn("name2: {}".format(name2))
    ```


- 执行

    ```python
    python main.py
    python client.py
    ```

    Return:

    ```python
        INFO:root:name: --------XIAOXIAO--------
        INFO:root:name2: --------WO MEN DOU SHI HAO HAI ZI--------
    ```


说明
----

通讯协议：
``request_method_len``\r\n``request_method``\r\n``request_params_len``\r\n``request_params``\r\n\r\n

- 结束符： ``\r\n\r\n``
- 分割符：``\r\n``

远程调用： ``request_method(request_params)``

版本变化
-------

- 0.2.0: 添加XTCPClient，优化代码结构
- 0.1.0: 添加服务器端异常处理，处理解析数据超时

TODO
----
去掉 `tornado` 的 `TCPServer` 和 `TCPClient`
