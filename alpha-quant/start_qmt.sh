#!/bin/bash
# start_qmt.sh --- 启动 QMT/miniQMT 执行器

cd "$(dirname "$0")"

# 激活虚拟环境
source quant_env/bin/activate

# 加载环境变量
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
fi

echo "=========================================="
echo "Alpha Quant - QMT/miniQMT 执行器"
echo "=========================================="
echo ""

# 检查配置
if [ "$QMT_PATH" == "" ] || [ "$QMT_PATH" == "YOUR_QMT_PATH" ]; then
    echo "❌ 请配置 QMT_PATH 环境变量"
    echo "示例: export QMT_PATH=/path/to/miniQMT"
    exit 1
fi

if [ "$QMT_ACCOUNT_ID" == "" ] || [ "$QMT_ACCOUNT_ID" == "YOUR_ACCOUNT_ID" ]; then
    echo "❌ 请配置 QMT_ACCOUNT_ID 环境变量"
    echo "示例: export QMT_ACCOUNT_ID=12345678"
    exit 1
fi

echo "QMT 路径: $QMT_PATH"
echo "账户 ID: $QMT_ACCOUNT_ID"
echo "信号服务器: $SIGNAL_SERVER_URL"
echo ""
echo "按 Ctrl+C 停止"
echo "=========================================="

python qmt_executor.py
