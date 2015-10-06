#!/usr/bin/env python
# coding=utf-8

import functools
import logging
logging.basicConfig(level=logging.DEBUG)

from tornado import ioloop
from pyxtcp import RPCServer
from pyxtcp.util import Service, server_callback_by_json
service = Service()


class CompanyService(object):

    @staticmethod
    @service.with_f_rpc
    def get_company_by_company_id(company_id):
        logging.warn(("HiHi", company_id))
        return "wwwwwwwwwwwwwwwww{}".format(company_id)

    @staticmethod
    @service.with_f_rpc
    def get_company_by_company_token(company_token):
        pass


def main():
    logging.info(service.__dict__)
    port = 8001
    app = RPCServer(functools.partial(server_callback_by_json, service))
    app.listen(port)
    ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
