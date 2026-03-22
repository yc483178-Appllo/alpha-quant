#!/bin/bash
# deploy_data_gateway.sh - 部署增强版数据网关到服务器

set -e

echo "🚀 开始部署数据网关..."

SERVER_IP="120.76.55.222"
SERVER_USER="root"
REMOTE_PATH="/opt/alpha/v7"
LOCAL_PATH="/root/.openclaw/workspace/alpha-quant"

# 1. 同步增强版数据网关
echo "📤 同步 enhanced_data_gateway.py..."
scp "${LOCAL_PATH}/enhanced_data_gateway.py" "${SERVER_USER}@${SERVER_IP}:${REMOTE_PATH}/"

# 2. 同步环境变量配置
echo "📤 同步 .env 配置文件..."
scp "${LOCAL_PATH}/.env" "${SERVER_USER}@${SERVER_IP}:${REMOTE_PATH}/"

# 3. 在服务器上安装依赖
echo "📦 安装依赖..."
ssh "${SERVER_USER}@${SERVER_IP}" "cd ${REMOTE_PATH} && pip install tushare baostock akshare -q 2>&1 || echo '依赖安装可能需要手动处理'"

# 4. 重启数据网关服务
echo "🔄 重启数据网关服务..."
ssh "${SERVER_USER}@${SERVER_IP}" "
    cd ${REMOTE_PATH}
    
    # 查找并停止旧的数据网关进程
    pkill -f 'enhanced_data_gateway.py' 2>/dev/null || true
    sleep 1
    
    # 启动新的数据网关（后台运行）
    nohup python enhanced_data_gateway.py > logs/gateway.log 2>&1 &
    sleep 2
    
    # 检查是否启动成功
    if pgrep -f 'enhanced_data_gateway.py' > /dev/null; then
        echo '✅ 数据网关启动成功'
    else
        echo '❌ 数据网关启动失败，请检查日志'
    fi
"

# 5. 健康检查
echo "🏥 执行健康检查..."
sleep 3
if curl -s "http://${SERVER_IP}:5001/api/health" > /dev/null; then
    echo "✅ 数据网关健康检查通过"
    curl -s "http://${SERVER_IP}:5001/api/health" | head -20
else
    echo "⚠️ 健康检查失败，请手动检查服务状态"
fi

echo ""
echo "🎉 部署完成！"
echo "数据网关地址: http://${SERVER_IP}:5001"
echo "健康检查: http://${SERVER_IP}:5001/api/health"
echo ""
echo "如需查看日志: ssh ${SERVER_USER}@${SERVER_IP} 'tail -f ${REMOTE_PATH}/logs/gateway_\$(date +%Y-%m-%d).log'"
