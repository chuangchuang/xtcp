Pyxtcp
======

Tcp-based communication protocol, `RPC` protocol

You can install pyxtcp from PyPI with

.. sourcecode:: bash

    $ pip install pyxtcp


Protocol
--------
- format：

  .. sourcecode:: text

        {type}{topic_len}"t{topic}"t{body_len}"r"n{body}"r"n


- demo

  .. sourcecode:: text

        __ __ __ __ __ __ __ __ __ __ __
        | - | 4 | " | t | p | i | n | g |
        | " | t | 5 | " | r | " | n | t |
        | o | p | i | c | " | r | " | n |
        __ __ __ __ __ __ __ __ __ __ __


- Explanation:

  - Protocol by content into two parts: `topic` `body`
  - Protocol by format consists of two parts(like `HTTP`): `header` `body`
  
    - `"t` is `header` separator
    - `"r"n` is `body` and `header` separator and two messages delimiter


- Parameter Description:

 - param char type: `-` is request; `=` is response
 - param int topic_len: `topic` length
 - param string topic: `topic` content
 - param int body_len: `body` length
 - param string body: `body` content

Version update
--------------

- 1.0.2 添加client_handler, Service, server_callback_by_json
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
