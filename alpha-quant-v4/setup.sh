#!/bin/bash
# setup.sh - Alpha Quant v4.0 安装脚本

set -e

echo "🚀 Alpha Quant v4.0 安装脚本"
echo "=============================="

# 检查 Python 版本
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "✓ Python 版本: $python_version"

# 创建虚拟环境（可选）
if [ "$1" == "--venv" ]; then
    echo "📦 创建虚拟环境..."
    python3 -m venv venv
    source venv/bin/activate
fi

# 安装依赖
echo "📦 安装依赖..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

echo "✅ 依赖安装完成"

# 创建必要的目录
mkdir -p logs
mkdir -p data
mkdir -p backups

echo "✅ 目录结构创建完成"

# 检查 Redis
echo "🔍 检查 Redis..."
if redis-cli ping > /dev/null 2>&1; then
    echo "✅ Redis 已启动"
else
    echo "⚠️  Redis 未启动，请先启动 Redis"
    echo "    Ubuntu/Debian: sudo service redis-server start"
    echo "    macOS: brew services start redis"
fi

# 检查环境变量
echo "🔍 检查环境变量..."
if [ -f ".env" ]; then
    echo "✅ .env 文件存在"
    
    # 检查关键配置
    if grep -q "TUSHARE_TOKEN=your_token" .env; then
        echo "⚠️  请编辑 .env 文件，配置 TUSHARE_TOKEN"
    fi
    
    if grep -q "FEISHU_WEBHOOK_URL=https://open.feishu.cn" .env; then
        echo "✅ 飞书 Webhook 已配置"
    fi
else
    echo "⚠️  .env 文件不存在，从模板创建..."
    cp .env.example .env 2>/dev/null || echo "请手动创建 .env 文件"
fi

echo ""
echo "=============================="
echo "🎉 安装完成！"
echo ""
echo "启动命令:"
echo "  python main.py              # 完整系统"
echo "  python main.py --agent scheduler  # 仅启动调度器"
echo ""
echo "查看日志:"
echo "  tail -f logs/alpha_v4_*.log"
echo ""
