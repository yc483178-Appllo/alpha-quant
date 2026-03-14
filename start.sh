#!/bin/bash
# KimiClaw V8.0 启动脚本

set -e

echo "🚀 KimiClaw V8.0 启动脚本"
echo "=========================="

# 检查Python版本
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python版本: $PYTHON_VERSION"

# 检查虚拟环境
if [ -d ".venv" ]; then
    echo "✓ 检测到虚拟环境"
    source .venv/bin/activate
else
    echo "⚠️  未检测到虚拟环境，建议创建: python3 -m venv .venv"
fi

# 安装依赖
echo ""
echo "📦 检查依赖..."
pip install -q -r requirements.txt

# 检查环境变量
echo ""
echo "🔑 检查环境变量..."
REQUIRED_VARS=("TUSHARE_TOKEN" "KIMI_API_KEY")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        MISSING_VARS+=("$var")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo "⚠️  缺少以下环境变量:"
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "请设置环境变量或创建 .env 文件:"
    echo "  export TUSHARE_TOKEN=your_token"
    echo "  export KIMI_API_KEY=your_key"
    echo ""
fi

# 检查看板文件
echo ""
echo "📊 检查看板文件..."
if [ -f "static/index.html" ]; then
    echo "✓ 看板文件已就绪"
else
    echo "⚠️  看板文件不存在，请确保 static/index.html 存在"
fi

# 启动服务
echo ""
echo "🌟 启动 KimiClaw V8.0..."
echo "=========================="
echo "API地址: http://localhost:8000"
echo "看板地址: http://localhost:8000/dashboard"
echo "API文档: http://localhost:8000/docs"
echo "健康检查: http://localhost:8000/health"
echo "=========================="
echo ""

# 启动
python3 main_v8.py
