#!/bin/bash
# Alpha Quant Python 环境一键搭建脚本
# 使用方法: bash setup_env.sh

set -e  # 遇到错误立即退出

echo "=========================================="
echo "🚀 Alpha Quant Python 环境搭建"
echo "=========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检查 Python 版本
echo -e "\n📋 检查 Python 版本..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python 版本: $python_version"

# 检查 python3-venv 是否安装
echo -e "\n📦 检查虚拟环境支持..."
if ! python3 -m venv --help > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  python3-venv 未安装，正在安装...${NC}"
    apt update && apt install -y python3-venv
fi
echo -e "${GREEN}✅ 虚拟环境支持已就绪${NC}"

# Step 1: 创建虚拟环境
echo -e "\n=========================================="
echo "Step 1: 创建虚拟环境 (quant_env)"
echo "=========================================="

if [ -d "quant_env" ]; then
    echo -e "${YELLOW}⚠️  检测到已存在的虚拟环境，是否删除重建? (y/n)${NC}"
    read -r response
    if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
        rm -rf quant_env
        echo "已删除旧环境"
    else
        echo "使用现有环境"
    fi
fi

if [ ! -d "quant_env" ]; then
    python3 -m venv quant_env
    echo -e "${GREEN}✅ 虚拟环境创建成功${NC}"
else
    echo -e "${GREEN}✅ 使用现有虚拟环境${NC}"
fi

# 激活虚拟环境
echo -e "\n🔄 激活虚拟环境..."
source quant_env/bin/activate

# Step 2: 升级 pip
echo -e "\n=========================================="
echo "Step 2: 升级 pip"
echo "=========================================="
pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple

# Step 3: 安装依赖
echo -e "\n=========================================="
echo "Step 3: 安装依赖包"
echo "=========================================="

if [ -f "requirements.txt" ]; then
    echo "从 requirements.txt 安装依赖..."
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
else
    echo -e "${RED}❌ requirements.txt 不存在${NC}"
    exit 1
fi

# Step 4: 验证安装
echo -e "\n=========================================="
echo "Step 4: 验证安装"
echo "=========================================="

python3 -c "
import sys
print(f'Python: {sys.version}')
print()

try:
    import akshare
    print(f'✅ AkShare: {akshare.__version__}')
except ImportError as e:
    print(f'❌ AkShare: {e}')

try:
    import tushare
    print(f'✅ Tushare: {tushare.__version__}')
except ImportError as e:
    print(f'❌ Tushare: {e}')

try:
    import baostock
    print(f'✅ Baostock: 已安装')
except ImportError as e:
    print(f'❌ Baostock: {e}')

try:
    import flask
    print(f'✅ Flask: {flask.__version__}')
except ImportError as e:
    print(f'❌ Flask: {e}')

try:
    import redis
    print(f'✅ Redis: {redis.__version__}')
except ImportError as e:
    print(f'❌ Redis: {e}')

try:
    import apscheduler
    print(f'✅ APScheduler: {apscheduler.__version__}')
except ImportError as e:
    print(f'❌ APScheduler: {e}')

try:
    import loguru
    print(f'✅ Loguru: 已安装')
except ImportError as e:
    print(f'❌ Loguru: {e}')

try:
    import pandas
    print(f'✅ Pandas: {pandas.__version__}')
except ImportError as e:
    print(f'❌ Pandas: {e}')

try:
    import numpy
    print(f'✅ NumPy: {numpy.__version__}')
except ImportError as e:
    print(f'❌ NumPy: {e}')

try:
    import matplotlib
    print(f'✅ Matplotlib: {matplotlib.__version__}')
except ImportError as e:
    print(f'❌ Matplotlib: {e}')

print()
print('🎉 核心依赖验证完成!')
"

# Step 5: 创建启动脚本
echo -e "\n=========================================="
echo "Step 5: 创建便捷启动脚本"
echo "=========================================="

cat > start_alpha.sh << 'EOF'
#!/bin/bash
# Alpha Quant 启动脚本

source quant_env/bin/activate

case "$1" in
    test)
        python3 alpha.py test
        ;;
    premarket)
        python3 alpha.py premarket
        ;;
    intraday)
        python3 alpha.py intraday
        ;;
    closing)
        python3 alpha.py closing
        ;;
    *)
        echo "使用方法:"
        echo "  ./start_alpha.sh test      # 测试连接"
        echo "  ./start_alpha.sh premarket # 盘前分析"
        echo "  ./start_alpha.sh intraday  # 盘中监控"
        echo "  ./start_alpha.sh closing   # 收盘复盘"
        ;;
esac
EOF

chmod +x start_alpha.sh

echo -e "${GREEN}✅ 启动脚本已创建: start_alpha.sh${NC}"

# Step 6: 创建环境配置模板
echo -e "\n=========================================="
echo "Step 6: 创建环境配置模板"
echo "=========================================="

if [ ! -f ".env" ]; then
    cat > .env << EOF
# Alpha Quant 环境配置
TUSHARE_TOKEN=your_tushare_token_here
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
LOG_LEVEL=INFO
EOF
    echo -e "${GREEN}✅ 环境配置模板已创建: .env${NC}"
    echo -e "${YELLOW}⚠️  请编辑 .env 文件，填入你的 Tushare Token${NC}"
else
    echo -e "${YELLOW}⚠️  .env 文件已存在，跳过创建${NC}"
fi

echo -e "\n=========================================="
echo -e "${GREEN}🎉 环境搭建完成!${NC}"
echo "=========================================="
echo ""
echo "使用说明:"
echo "  1. 激活环境: source quant_env/bin/activate"
echo "  2. 测试连接: ./start_alpha.sh test"
echo "  3. 盘前分析: ./start_alpha.sh premarket"
echo "  4. 盘中监控: ./start_alpha.sh intraday"
echo "  5. 收盘复盘: ./start_alpha.sh closing"
echo ""
echo "配置文件:"
echo "  - config.py      # 系统配置"
echo "  - .env           # 环境变量（需手动配置）"
echo ""
