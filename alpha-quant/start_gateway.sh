#!/bin/bash
# 启动数据网关服务

cd /root/.openclaw/workspace/alpha-quant
source quant_env/bin/activate

# 创建日志目录
mkdir -p logs

echo "🚀 启动数据网关服务..."
echo "访问地址: http://localhost:8765"
echo "健康检查: http://localhost:8765/api/health"
echo ""
echo "可用接口:"
echo "  - GET /api/market/realtime    实时行情 TOP100"
echo "  - GET /api/sector/flow        板块资金流向"
echo "  - GET /api/north/flow         北向资金流入"
echo "  - GET /api/limitup/pool       涨停板池"
echo "  - GET /api/stock/detail?code=xxx  个股详情"
echo "  - GET /api/calendar/is_trade_date   交易日检查"
echo ""

python3 data_gateway.py
