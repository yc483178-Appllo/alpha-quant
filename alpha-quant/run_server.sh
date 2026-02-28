#!/bin/bash
cd /root/.openclaw/workspace/alpha-quant
source quant_env/bin/activate
export SIGNAL_PORT=8765
export FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/ba2ce0cf-7d1a-43aa-ad93-d8747b8a24b0
python signal_server.py
