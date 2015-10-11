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

    @staticmethod
    @service.with_f_rpc
    def get_company_by_company_token(company_token):
        pass


def main():
    port = 8001
    app = RPCServer(port, "0.0.0.0")
    app.add_service(service)
    app.run()


if __name__ == "__main__":
    main()
