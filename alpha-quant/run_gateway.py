#!/usr/bin/env python3
"""
启动数据网关 - 保持进程运行
"""
import os
import sys

os.chdir('/root/.openclaw/workspace/alpha-quant')

# 激活虚拟环境
venv_python = '/root/.openclaw/workspace/alpha-quant/quant_env/bin/python'

# 导入并运行
sys.path.insert(0, '/root/.openclaw/workspace/alpha-quant')

# 设置环境变量
os.environ['SIGNAL_PORT'] = '8765'
os.environ['FEISHU_WEBHOOK_URL'] = 'https://open.feishu.cn/open-apis/bot/v2/hook/ba2ce0cf-7d1a-43aa-ad93-d8747b8a24b0'

# 启动服务
import data_gateway
