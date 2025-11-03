#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# AWS Lambda Handler - Adapts Flask API to Lambda

from api import app
import serverless_wsgi

def lambda_handler(event, context):
    # Lambda entry point
    # Uses serverless-wsgi to convert Flask requests to Lambda responses
    return serverless_wsgi.handle_request(app, event, context)

