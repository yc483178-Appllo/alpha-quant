#!/bin/bash
# start_gateway_gunicorn.sh --- 使用 Gunicorn 启动数据网关

cd /root/.openclaw/workspace/alpha-quant
source quant_env/bin/activate

# 杀掉旧进程
pkill -f "gunicorn.*data_gateway" 2>/dev/null
sleep 2

echo "🚀 启动数据网关 (Gunicorn)..."

# 使用 Gunicorn 启动
exec gunicorn \
    -w 2 \
    -b 0.0.0.0:8766 \
    --timeout 60 \
    --access-logfile logs/gateway_access.log \
    --error-logfile logs/gateway_error.log \
    --daemon \
    data_gateway:app

echo "✅ 数据网关已启动在 http://0.0.0.0:8766"
