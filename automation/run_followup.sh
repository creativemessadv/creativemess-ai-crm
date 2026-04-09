#!/bin/bash
unset HTTP_PROXY HTTPS_PROXY http_proxy https_proxy
cd /home/user/creativemess-ai-crm/automation
export $(cat .env | grep -v '^#' | xargs)
python3 followup.py
