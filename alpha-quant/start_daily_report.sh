#!/bin/bash
# start_daily_report.sh --- 生成每日收盘复盘报告

cd "$(dirname "$0")"

# 激活虚拟环境
source quant_env/bin/activate

# 加载环境变量
if [ -f .env ]; then
    export $(cat .env | grep -v '#' | xargs)
fi

echo "=========================================="
echo "Alpha Quant - 收盘复盘报告生成"
echo "=========================================="
echo ""

# 检查是否为交易日（简单判断：周一到周五）
day_of_week=$(date +%u)
if [ "$day_of_week" -gt 5 ]; then
    echo "今日为周末，跳过报告生成"
    exit 0
fi

# 生成报告
echo "正在生成复盘报告..."
python daily_report_generator.py

echo ""
echo "报告生成完成！"
echo "查看路径: reports/daily/$(date +%Y-%m-%d)-daily.md"
