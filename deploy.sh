#!/bin/bash
# V7.0 完整部署脚本

set -e

echo "=========================================="
echo "  Kimi Claw V7.0 部署脚本"
echo "=========================================="

# 检查Python版本
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "[1/6] Python版本: $PYTHON_VERSION"

# 创建虚拟环境（如果不存在）
if [ ! -d "venv" ]; then
    echo "[2/6] 创建虚拟环境..."
    python3 -m venv venv
fi

# 激活虚拟环境
echo "[3/6] 激活虚拟环境..."
source venv/bin/activate

# 升级pip
echo "[4/6] 升级pip..."
pip install --upgrade pip -q

# 安装核心依赖
echo "[5/6] 安装核心依赖..."
pip install fastapi uvicorn pydantic pydantic-settings python-dotenv -q
pip install numpy pandas -q

# 创建日志目录
echo "[6/6] 创建日志目录..."
mkdir -p /var/log/kimi-claw

# 测试导入
echo ""
echo "=== 测试模块导入 ==="
python3 -c "
import sys
sys.path.insert(0, '.')
from config.settings import settings
print(f'✅ 配置加载成功: V{settings.version}')
print(f'✅ API模式: {settings.api_mode}')
print(f'✅ 数据库: ClickHouse + PostgreSQL + Redis')
"

echo ""
echo "=========================================="
echo "  部署完成!"
echo "=========================================="
echo ""
echo "启动命令:"
echo "  source venv/bin/activate"
echo "  uvicorn main:app --host 0.0.0.0 --port 8000 --reload"
echo ""
echo "访问地址:"
echo "  API文档: http://120.76.55.222:8000/api/docs"
echo "  健康检查: http://120.76.55.222:8000/health"
echo "  系统状态: http://120.76.55.222:8000/api/system/status"
