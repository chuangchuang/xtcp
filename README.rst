pyxtcp
============

基于 `tcp` 的简单的 `socket` 通信协议

You can install pyxtcp from PyPI with

.. sourcecode:: bash

    $ pip install pyxtcp


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
