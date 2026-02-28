#!/usr/bin/env python3
"""
启动数据网关
"""
import subprocess
import os
import sys

os.chdir('/root/.openclaw/workspace/alpha-quant')

venv_python = '/root/.openclaw/workspace/alpha-quant/quant_env/bin/python'

# 先杀掉旧进程
subprocess.run(['pkill', '-f', 'data_gateway.py'], capture_output=True)

log_file = open('logs/gateway_latest.log', 'a')
process = subprocess.Popen(
    [venv_python, 'data_gateway.py'],
    stdout=log_file,
    stderr=subprocess.STDOUT,
    preexec_fn=os.setsid
)

print(f"🚀 数据网关已启动，PID: {process.pid}")
sys.exit(0)
