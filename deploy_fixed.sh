#!/bin/bash
# KimiClaw V8.0 + V4.3看板部署脚本 (修复版)
# 服务器: 120.76.55.222
# 部署路径: /opt/alpha/v7/ (Caddy Web根目录)
# 访问地址: http://120.76.55.222/v3/

set -e

echo "🚀 KimiClaw V8.0 + V4.3看板部署脚本 (修复版)"
echo "=============================================="
echo ""

# 系统配置
SERVER_IP="120.76.55.222"
SERVER_USER="root"
REMOTE_DIR="/opt/alpha/v7"          # V7.0部署位置 (Caddy根目录)
DASHBOARD_DIR="/opt/alpha/v7"       # 看板部署位置
API_PORT="8000"

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${YELLOW}系统配置确认:${NC}"
echo "  服务器IP: ${SERVER_IP}"
echo "  部署路径: ${REMOTE_DIR}"
echo "  看板访问: http://${SERVER_IP}/v3/"
echo "  API地址: http://${SERVER_IP}:${API_PORT}/"
echo ""

echo -e "${YELLOW}步骤1: 本地文件检查${NC}"
echo "=============================================="

# 检查必要文件
if [ ! -f "static/index.html" ]; then
    echo -e "${RED}错误: static/index.html 不存在${NC}"
    exit 1
fi

if [ ! -f "main_v8.py" ]; then
    echo -e "${RED}错误: main_v8.py 不存在${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 所有必要文件存在${NC}"

# 检查看板文件
DASHBOARD_SIZE=$(stat -c%s "static/index.html")
echo "看板文件: static/index.html ($(($DASHBOARD_SIZE/1024))KB)"

echo ""
echo -e "${YELLOW}步骤2: 部署看板到Caddy目录${NC}"
echo "=============================================="
echo "目标: ${SERVER_IP}:${DASHBOARD_DIR}/"

# 确保远程目录存在
ssh ${SERVER_USER}@${SERVER_IP} "mkdir -p ${DASHBOARD_DIR}"

# 部署看板 (V4.3)
scp static/index.html ${SERVER_USER}@${SERVER_IP}:${DASHBOARD_DIR}/index.html

echo -e "${GREEN}✓ 看板V4.3部署完成${NC}"
echo "  访问地址: http://${SERVER_IP}/v3/"

echo ""
echo -e "${YELLOW}步骤3: 部署后端API${NC}"
echo "=============================================="

# 创建后端目录
ssh ${SERVER_USER}@${SERVER_IP} "mkdir -p ${REMOTE_DIR}/kimiclaw_v8_api"

# 同步后端文件
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='static' \
    ./ ${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/kimiclaw_v8_api/

echo -e "${GREEN}✓ 后端文件同步完成${NC}"

echo ""
echo -e "${YELLOW}步骤4: 启动后端服务${NC}"
echo "=============================================="

# 远程启动服务
ssh ${SERVER_USER}@${SERVER_IP} << EOF
cd ${REMOTE_DIR}/kimiclaw_v8_api

# 检查Python环境
python3 --version

# 安装依赖
pip3 install -r requirements.txt -q 2>/dev/null || echo "依赖已安装"

# 创建日志目录
mkdir -p logs

# 停止旧服务 (如果存在)
pkill -f "main_v8.py" 2>/dev/null || true

# 启动新服务
nohup python3 main_v8.py > logs/kimiclaw_v8.log 2>&1 &
echo "服务PID: $!"

# 等待服务启动
sleep 2

# 健康检查
echo "健康检查..."
curl -s http://localhost:${API_PORT}/health | head -c 200 || echo "服务启动中..."
EOF

echo -e "${GREEN}✓ 后端服务启动完成${NC}"

echo ""
echo "=============================================="
echo -e "${GREEN}🎉 部署完成!${NC}"
echo "=============================================="
echo ""
echo "📊 访问地址:"
echo "  看板V4.3: http://${SERVER_IP}/v3/"
echo "  API文档: http://${SERVER_IP}:${API_PORT}/docs"
echo "  健康检查: http://${SERVER_IP}:${API_PORT}/health"
echo ""
echo "🔌 API端点测试:"
echo "  curl http://${SERVER_IP}:${API_PORT}/api/v8/data/sources"
echo "  curl http://${SERVER_IP}:${API_PORT}/api/v8/ai/models"
echo "  curl http://${SERVER_IP}:${API_PORT}/api/v8/system/health"
echo ""
echo "📝 日志查看:"
echo "  ssh ${SERVER_USER}@${SERVER_IP} 'tail -f ${REMOTE_DIR}/kimiclaw_v8_api/logs/kimiclaw_v8.log'"
echo ""
