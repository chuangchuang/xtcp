#!/usr/bin/env python
# coding=utf-8

import logging
from pyxtcp import SimpleRPCClient
from pyxtcp.client_handler import BasicRPCClientHandler


company = BasicRPCClientHandler(SimpleRPCClient(host="127.0.0.1", port=8001)).service_name("CompanyService")
logging.warn(company.get_company_by_company_id(company_id="12121212"))
