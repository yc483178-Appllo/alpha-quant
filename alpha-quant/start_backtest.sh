#!/bin/bash
# start_backtest.sh --- 启动策略回测

cd "$(dirname "$0")"
source quant_env/bin/activate

echo "=========================================="
echo "Alpha Quant - 策略回测引擎"
echo "=========================================="
echo ""

# 解析参数
MODE=${1:-"single"}  # single / compare / tushare
STOCK=${2:-"sh.600036"}
STRATEGY=${3:-"ma_cross"}

if [ "$MODE" == "compare" ]; then
    echo "📊 多策略对比模式"
    python backtest_engine.py compare
elif [ "$MODE" == "tushare" ]; then
    echo "📊 Tushare 数据源模式"
    if [ -z "$TUSHARE_TOKEN" ]; then
        echo "❌ 请设置 TUSHARE_TOKEN 环境变量"
        echo "用法: TUSHARE_TOKEN=xxx $0 tushare"
        exit 1
    fi
    python backtest_engine.py tushare "$TUSHARE_TOKEN"
else
    echo "📊 单策略回测模式"
    echo "标的: $STOCK"
    echo "策略: $STRATEGY"
    echo ""
    python -c "
from backtest_engine import run_backtest
result = run_backtest(stock_code='$STOCK', strategy='$STRATEGY', plot=True)
if result:
    for k, v in result.items():
        if k not in ['trades', 'portfolio', 'dates']:
            print(f'  {k}: {v}')
"
fi
