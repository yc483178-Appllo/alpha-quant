#!/bin/bash
# start_signal_server.sh --- 启动 Alpha Quant 信号服务器

cd "$(dirname "$0")"

# 激活虚拟环境
source quant_env/bin/activate

# 加载环境变量
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
fi

echo "=========================================="
echo "Alpha Quant - 交易信号服务器"
echo "=========================================="
echo ""

# 检查依赖
python -c "import flask" 2>/dev/null || {
    echo "❌ 缺少依赖，正在安装..."
    pip install flask flask-cors loguru python-dotenv -q
}

# 创建日志目录
mkdir -p logs

# 启动服务器
echo "🚀 启动信号服务器..."
echo "服务地址: http://0.0.0.0:${SIGNAL_PORT:-8765}"
echo ""
echo "API 接口:"
echo "  GET  /api/signals              - 获取待处理信号（PTrade调用）"
echo "  POST /api/signals              - 创建新信号（Kimi调用）"
echo "  POST /api/signals/confirm/<id> - 确认信号"
echo "  POST /api/signals/reject/<id>  - 拒绝信号"
echo "  GET  /api/signals/history      - 查看历史信号"
echo "  GET  /api/signals/stats        - 获取统计信息"
echo "  GET  /health                   - 健康检查"
echo ""
echo "按 Ctrl+C 停止服务"
echo "=========================================="

python signal_server.py
