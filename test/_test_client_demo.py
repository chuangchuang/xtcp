#!/usr/bin/env python
# coding=utf-8

import logging
logging.basicConfig(level=logging.INFO)
from pyxtcp.http import RPCClient

company = RPCClient("localhost:8001").service_name("CompanyService")

logging.info(company.get_company_by_company_id(company_id=7))
