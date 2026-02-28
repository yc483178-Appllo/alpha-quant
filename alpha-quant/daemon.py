#!/usr/bin/env python3
"""
信号服务器守护进程启动器
"""
import subprocess
import os
import sys
import signal
import time

# 设置环境变量
os.environ['SIGNAL_PORT'] = '8765'
os.environ['FEISHU_WEBHOOK_URL'] = 'https://open.feishu.cn/open-apis/bot/v2/hook/ba2ce0cf-7d1a-43aa-ad93-d8747b8a24b0'

# 工作目录
os.chdir('/root/.openclaw/workspace/alpha-quant')

# 激活虚拟环境
venv_python = '/root/.openclaw/workspace/alpha-quant/quant_env/bin/python'

def start_server():
    """启动信号服务器"""
    log_file = open('logs/signal_daemon.log', 'a')
    process = subprocess.Popen(
        [venv_python, 'signal_server.py'],
        stdout=log_file,
        stderr=subprocess.STDOUT,
        preexec_fn=os.setsid
    )
    return process

def main():
    print(f"🚀 启动信号服务器守护进程...")
    print(f"飞书Webhook: {os.environ['FEISHU_WEBHOOK_URL'][:50]}...")
    
    process = start_server()
    print(f"✅ 服务器已启动，PID: {process.pid}")
    
    # 等待几秒确认启动成功
    time.sleep(3)
    
    # 检查进程是否还在运行
    if process.poll() is None:
        print("✅ 服务器运行正常")
        # 分离进程，让其在后台继续运行
        print(f"服务器将在后台继续运行，PID: {process.pid}")
        sys.exit(0)
    else:
        print(f"❌ 服务器启动失败，退出码: {process.returncode}")
        sys.exit(1)

if __name__ == '__main__':
    main()
