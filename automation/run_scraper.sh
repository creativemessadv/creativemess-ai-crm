#!/bin/bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
cd /root/agency/automation
set -a; source .env; set +a
python3 scraper.py "$@"
