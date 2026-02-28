#!/usr/bin/env python3
"""
数据网关守护进程启动器
"""
import subprocess
import os
import sys

os.chdir('/root/.openclaw/workspace/alpha-quant')

venv_python = '/root/.openclaw/workspace/alpha-quant/quant_env/bin/python'

log_file = open('logs/gateway_daemon.log', 'a')
process = subprocess.Popen(
    [venv_python, 'data_gateway.py'],
    stdout=log_file,
    stderr=subprocess.STDOUT,
    preexec_fn=os.setsid
)

print(f"🚀 数据网关已启动，PID: {process.pid}")
sys.exit(0)
