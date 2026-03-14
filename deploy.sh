#!/bin/bash
# KimiClaw V8.0 + V4.3看板部署脚本
# 部署到服务器: 120.76.55.222

set -e

echo "🚀 KimiClaw V8.0 + V4.3看板部署脚本"
echo "======================================"
echo ""

# 配置
SERVER_IP="120.76.55.222"
SERVER_USER="root"
REMOTE_DIR="/opt/kimiclaw-v8"
NGINX_ROOT="/var/www/html/v3"

# 颜色
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}步骤1: 本地构建检查${NC}"
echo "======================================"

# 检查必要文件
if [ ! -f "static/index.html" ]; then
    echo -e "${RED}错误: static/index.html 不存在${NC}"
    exit 1
fi

if [ ! -f "main_v8.py" ]; then
    echo -e "${RED}错误: main_v8.py 不存在${NC}"
    exit 1
fi

if [ ! -f "requirements.txt" ]; then
    echo -e "${RED}错误: requirements.txt 不存在${NC}"
    exit 1
fi

echo -e "${GREEN}✓ 所有必要文件存在${NC}"

# 检查看板文件大小
DASHBOARD_SIZE=$(stat -c%s "static/index.html")
echo "看板文件大小: $DASHBOARD_SIZE bytes ($(($DASHBOARD_SIZE/1024))KB)"

if [ $DASHBOARD_SIZE -lt 300000 ]; then
    echo -e "${RED}警告: 看板文件可能不完整 (预期 >300KB)${NC}"
fi

echo ""
echo -e "${YELLOW}步骤2: 部署后端API${NC}"
echo "======================================"

# SSH部署后端
ssh ${SERVER_USER}@${SERVER_IP} "mkdir -p ${REMOTE_DIR}"

# 同步后端文件
echo "同步后端文件到服务器..."
rsync -avz --exclude='.venv' --exclude='__pycache__' \
    ./ ${SERVER_USER}@${SERVER_IP}:${REMOTE_DIR}/

echo -e "${GREEN}✓ 后端文件同步完成${NC}"

echo ""
echo -e "${YELLOW}步骤3: 部署前端看板${NC}"
echo "======================================"

# 部署看板到nginx目录
ssh ${SERVER_USER}@${SERVER_IP} "mkdir -p ${NGINX_ROOT}"
scp static/index.html ${SERVER_USER}@${SERVER_IP}:${NGINX_ROOT}/

echo -e "${GREEN}✓ 看板部署完成${NC}"

echo ""
echo -e "${YELLOW}步骤4: 启动后端服务${NC}"
echo "======================================"

# 远程启动服务
ssh ${SERVER_USER}@${SERVER_IP} << EOF
cd ${REMOTE_DIR}

# 检查Python环境
python3 --version

# 安装依赖
pip3 install -r requirements.txt -q

# 启动服务 (使用nohup后台运行)
nohup python3 main_v8.py > logs/kimiclaw.log 2>&1 &
echo "服务PID: $!"

# 等待服务启动
sleep 3

# 健康检查
curl -s http://localhost:8000/health | head -c 200
EOF

echo ""
echo -e "${GREEN}✓ 后端服务启动完成${NC}"

echo ""
echo "======================================"
echo -e "${GREEN}🎉 部署完成!${NC}"
echo "======================================"
echo ""
echo "访问地址:"
echo "  看板V4.3: http://${SERVER_IP}/v3/"
echo "  API文档: http://${SERVER_IP}:8000/docs"
echo "  健康检查: http://${SERVER_IP}:8000/health"
echo ""
echo "API端点测试:"
echo "  curl http://${SERVER_IP}:8000/api/v8/data/sources"
echo "  curl http://${SERVER_IP}:8000/api/v8/ai/models"
echo ""
