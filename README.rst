pyxtcp
============

基于 `tcp` 的简单的 `socket` 通信协议

You can install pyxtcp from PyPI with

.. sourcecode:: bash

    $ pip install pyxtcp


协议说明
-------
- 协议格式：

  ```
  {type}{topic_len}"t{topic}"t{body_len}"r"n{body}"r"n
  ```

- 例子

  ```
   __ __ __ __ __ __ __ __ __ __ __
  | - | 4 | " | t | p | i | n | g |
  | " | t | 5 | " | r | " | n | t |
  | o | p | i | c | " | r | " | n |
  __ __ __ __ __ __ __ __ __ __ __ __
  ```

- 协议说明
  协议按内容分为两部分：`topic`, `body`
  协议按协议信息也分为两部分：`header`, `body`
  `"t` 为 `header` 信息的分隔符
  `"r"n` 为 `body` 和 `header` 的分隔符和两条消息的分隔符

 - param char type: `-` 表示请求；`=` 表示回复
 - param int topic_len: `topic` 长度
 - param string topic: `topic` 内容
 - param int body_len: `body` 长度
 - param string body: `body` 内容

Version update
--------------

- 1.0.1 initialize project


Getting Started
---------------

- server

    .. sourcecode:: python

        #!/usr/bin/env python
        # coding=utf-8

        import logging
        logging.basicConfig(level=logging.DEBUG)
        import tornado.ioloop
        from pyxtcp import RPCServer

        def handler_request(message):
            logging.info(message.__dict__)
            return message.topic.upper()


        if __name__ == "__main__":
            port = 8001
            app = RPCServer(handler_request)
            app.listen(port)
            ioloop.IOLoop.instance().start()

- client

    .. sourcecode:: python

      #!/usr/bin/env python
      # coding=utf-8

      import logging
      logging.basicConfig(level=logging.DEBUG)
      from pyxtcp import SimpleRPCClient, RPCClientItem, RPCMessage, CONNECTION_TYPE_IN_REQUEST

      def handler_response(message):
          logging.info(message.__dict__)


      if __name__ == "__main__":
          client = SimpleRPCClient(host="127.0.0.1", port=8001)
          message_item = RPCMessage(
              type_=CONNECTION_TYPE_IN_REQUEST,
              topic="ping",
              body="")
          client.fetch(RPCClientItem(message_item, handler_response))


Support
-------

If you need help using `pyxtcp` or have found a bug, please open a `github issue`_.

.. _github issue: https://github.com/nashuiliang/xtcp/issues
