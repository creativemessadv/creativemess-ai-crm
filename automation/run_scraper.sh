#!/bin/bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
cd /home/user/creativemess-ai-crm/automation
source .env
export $(cat .env | grep -v '^#' | xargs)
python3 scraper.py "$@"
