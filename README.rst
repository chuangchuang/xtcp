Pyxtcp
======

HTTP-based communication protocol, `RPC` protocol

You can install pyxtcp from PyPI with

.. sourcecode:: bash

    $ pip install pyxtcp


Protocol
--------
- format：

  .. sourcecode:: text

        /topic/method?v={params}


Version update
--------------

- 1.1.0 添加 HTTP-based RPC
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

        from pyxtcp.http import RPCServer, Service
        service = Service()


        class CompanyService(object):

            @staticmethod
            @service.with_f_rpc
            def get_company_by_company_id(company_id):
                logging.warn(("HiHi", company_id))
                return "wwwwwwwwwwwwwwwww{}".format(company_id)

        if __name__ == "__main__":
            port = 8001
            app = RPCServer(8001, "0.0.0.0")
            app.add_service(service)
            app.run()

- client

    .. sourcecode:: python

        #!/usr/bin/env python
        # coding=utf-8

        import logging
        import requests
        import json

        data = {
            "company_id": 7,
        }

        params = {
            "v": json.dumps(data)
        }

        content = requests.get("http://localhost:8001/CompanyService/get_company_by_company_id", params=params)
        logging.info((content.status_code, content.text))


Support
-------

If you need help using `pyxtcp` or have found a bug, please open a `github issue`_.

.. _github issue: https://github.com/nashuiliang/xtcp/issues
