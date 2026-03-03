"""
Alpha V5.0 - 实时交易看板 Dashboard V2.0
9面板增强版 + 交易操作UI
Flask + WebSocket 实时数据推送
"""

import os
import json
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from loguru import logger

# 尝试导入可选依赖
try:
    from flask_socketio import SocketIO, emit
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    logger.warning("⚠️ flask-socketio未安装，将使用轮询模式")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'alpha-dashboard-v2-secret'
CORS(app)

if SOCKETIO_AVAILABLE:
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# 模拟数据存储（实际应从各模块获取）
dashboard_data = {
    "market": {
        "indices": {
            "上证指数": {"price": 3300.5, "change": 0.25, "volume": 3500},
            "深证成指": {"price": 10500.3, "change": -0.15, "volume": 4200},
            "创业板指": {"price": 2100.8, "change": -0.45, "volume": 1800}
        },
        "sentiment": 0.15,
        "risk_level": "medium"
    },
    "portfolio": {
        "total_value": 1085000,
        "total_return": 8.5,
        "cash": 150000,
        "positions": [
            {"code": "300750", "name": "宁德时代", "shares": 100, "cost": 180.0, "price": 195.5, "pnl": 8.6},
            {"code": "600519", "name": "贵州茅台", "shares": 50, "cost": 1650.0, "price": 1720.0, "pnl": 4.2},
        ]
    },
    "signals": [],
    "agents": {},
    "drl": {
        "training": False,
        "episode": 0,
        "confidence": 0.72,
        "recommended_weights": []
    },
    "sentiment": {
        "sector_heatmap": {},
        "news_flow": []
    },
    "risk": {
        "var_95": 15000,
        "stress_test": "passed"
    }
}

# ===== 路由定义 =====

@app.route('/')
def index():
    """看板主页"""
    return render_template('dashboard_v2.html')

@app.route('/api/market/overview')
def api_market_overview():
    """市场总览数据"""
    return jsonify({
        "code": 200,
        "data": dashboard_data["market"],
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/portfolio/summary')
def api_portfolio_summary():
    """持仓摘要"""
    return jsonify({
        "code": 200,
        "data": dashboard_data["portfolio"],
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/signals')
def api_signals():
    """信号队列"""
    return jsonify({
        "code": 200,
        "data": dashboard_data["signals"],
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/agents/status')
def api_agents_status():
    """Agent状态"""
    agents = {
        "Chief": {"status": "running", "last_update": datetime.now().isoformat()},
        "Scout": {"status": "running", "last_update": datetime.now().isoformat()},
        "Picker": {"status": "running", "last_update": datetime.now().isoformat()},
        "Guard": {"status": "running", "last_update": datetime.now().isoformat()},
        "Trader": {"status": "idle", "last_update": datetime.now().isoformat()},
        "DRL": {"status": "training", "progress": 45, "last_update": datetime.now().isoformat()},
        "Sentiment": {"status": "running", "last_update": datetime.now().isoformat()},
        "Optimizer": {"status": "running", "last_update": datetime.now().isoformat()},
    }
    return jsonify({
        "code": 200,
        "data": agents,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/drl/status')
def api_drl_status():
    """DRL状态"""
    return jsonify({
        "code": 200,
        "data": dashboard_data["drl"],
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/sentiment/overview')
def api_sentiment_overview():
    """舆情概览"""
    sector_heatmap = {
        "新能源": 0.35,
        "科技": 0.12,
        "消费": 0.08,
        "医药": -0.05,
        "银行": 0.02,
        "地产": -0.25
    }
    return jsonify({
        "code": 200,
        "data": {
            "overall": 0.15,
            "sector_heatmap": sector_heatmap,
            "top_positive": ["固态电池", "AI算力"],
            "top_negative": ["地产链", "传统能源"]
        },
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/risk/metrics')
def api_risk_metrics():
    """风险指标"""
    return jsonify({
        "code": 200,
        "data": {
            "var_95": {"value": 15200, "pct": 1.4},
            "var_99": {"value": 28500, "pct": 2.6},
            "max_drawdown": {"value": 8.5, "pct": 8.5},
            "sharpe": {"value": 1.85},
            "beta": {"value": 0.92},
            "stress_test": {
                "market_crash_10": -85000,
                "sector_rotation": -32000,
                "liquidity_shock": -45000
            }
        },
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/portfolio/analysis')
def api_portfolio_analysis():
    """组合分析"""
    return jsonify({
        "code": 200,
        "data": {
            "attribution": {
                "stock_selection": 3.5,
                "sector_allocation": 2.1,
                "market_timing": 1.2,
                "luck": 1.7
            },
            "rolling_sharpe": [1.2, 1.5, 1.8, 1.85, 1.82],
            "drawdown_waterfall": [
                {"date": "2026-02-01", "drawdown": 0},
                {"date": "2026-02-15", "drawdown": -2.5},
                {"date": "2026-03-01", "drawdown": -1.2}
            ],
            "correlation_heatmap": []
        },
        "timestamp": datetime.now().isoformat()
    })

# ===== 交易操作API =====

@app.route('/api/trade/quick_buy', methods=['POST'])
def api_quick_buy():
    """快速买入"""
    data = request.json
    code = data.get('code')
    amount = data.get('amount')
    price_type = data.get('price_type', 'market')  # market/limit
    price = data.get('price')
    
    # 模拟风控检查
    if amount > 100000:
        return jsonify({
            "code": 403,
            "message": "单笔金额超限，需Guard审批",
            "requires_approval": True
        })
    
    return jsonify({
        "code": 200,
        "message": "买入指令已提交",
        "order_id": f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "details": {
            "code": code,
            "action": "buy",
            "amount": amount,
            "price_type": price_type,
            "price": price
        }
    })

@app.route('/api/trade/quick_sell', methods=['POST'])
def api_quick_sell():
    """快速卖出"""
    data = request.json
    code = data.get('code')
    shares = data.get('shares')
    sell_type = data.get('sell_type', 'partial')  # partial/all
    
    return jsonify({
        "code": 200,
        "message": "卖出指令已提交",
        "order_id": f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}",
        "details": {
            "code": code,
            "action": "sell",
            "shares": shares,
            "sell_type": sell_type
        }
    })

@app.route('/api/trade/emergency_close', methods=['POST'])
def api_emergency_close():
    """紧急平仓"""
    data = request.json
    codes = data.get('codes', [])  # 为空则全部
    
    return jsonify({
        "code": 200,
        "message": "紧急平仓指令已提交",
        "warning": "此操作将市价卖出，请确认",
        "order_ids": [f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}" for i in range(len(codes) if codes else 1)]
    })

@app.route('/api/trade/orders')
def api_trade_orders():
    """订单管理"""
    return jsonify({
        "code": 200,
        "data": {
            "pending": [
                {"id": "ORD001", "code": "300750", "action": "buy", "status": "pending", "price": 195.5}
            ],
            "filled": [],
            "cancelled": []
        }
    })

@app.route('/api/trade/cancel/<order_id>', methods=['POST'])
def api_cancel_order(order_id):
    """撤单"""
    return jsonify({
        "code": 200,
        "message": f"订单{order_id}已撤销"
    })

# ===== 券商连接状态 =====

@app.route('/api/broker/status')
def api_broker_status():
    """券商连接状态"""
    return jsonify({
        "code": 200,
        "data": {
            "ptrade": {
                "connected": True,
                "latency_ms": 45,
                "status": "green",  # green/yellow/red
                "account": {
                    "available": 150000,
                    "total": 1085000
                }
            },
            "qmt": {
                "connected": False,
                "latency_ms": None,
                "status": "red"
            }
        }
    })

# ===== WebSocket实时推送 =====

if SOCKETIO_AVAILABLE:
    @socketio.on('connect')
    def handle_connect():
        """客户端连接"""
        logger.info(f"客户端已连接: {request.sid}")
        emit('connected', {'message': 'Dashboard V2.0 Connected'})

    @socketio.on('disconnect')
    def handle_disconnect():
        """客户端断开"""
        logger.info(f"客户端已断开: {request.sid}")

    def broadcast_update(channel, data):
        """广播更新"""
        socketio.emit(channel, data, broadcast=True)

# ===== 模板渲染 =====

@app.route('/dashboard')
def dashboard_page():
    """看板页面"""
    html = '''
<!DOCTYPE html>
<html>
<head>
    <title>Alpha Dashboard V2.0</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
            background: #0a0e1a;
            color: #e0e6ed;
        }
        .header { 
            background: #1a1f2e; 
            padding: 15px 30px; 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            border-bottom: 1px solid #2d3548;
        }
        .header h1 { font-size: 20px; color: #00d4aa; }
        .broker-status { display: flex; gap: 20px; }
        .status-dot { 
            width: 10px; height: 10px; 
            border-radius: 50%; 
            display: inline-block;
            margin-right: 5px;
        }
        .status-green { background: #00d4aa; }
        .status-yellow { background: #f5a623; }
        .status-red { background: #ff4757; }
        
        .grid { 
            display: grid; 
            grid-template-columns: repeat(3, 1fr); 
            gap: 15px; 
            padding: 20px;
        }
        .panel { 
            background: #1a1f2e; 
            border-radius: 12px; 
            padding: 20px;
            border: 1px solid #2d3548;
        }
        .panel-header { 
            display: flex; 
            justify-content: space-between; 
            align-items: center;
            margin-bottom: 15px;
        }
        .panel-title { font-size: 14px; color: #8b92a8; }
        .panel-icon { font-size: 20px; }
        
        .metric { 
            display: flex; 
            justify-content: space-between; 
            padding: 8px 0;
            border-bottom: 1px solid #2d3548;
        }
        .metric:last-child { border-bottom: none; }
        .metric-label { color: #8b92a8; font-size: 12px; }
        .metric-value { font-size: 14px; font-weight: 600; }
        .positive { color: #00d4aa; }
        .negative { color: #ff4757; }
        
        .index-card {
            background: #252b3d;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 10px;
        }
        .index-name { font-size: 12px; color: #8b92a8; }
        .index-price { font-size: 24px; font-weight: bold; margin: 5px 0; }
        .index-change { font-size: 14px; }
        
        .trade-btn {
            background: #00d4aa;
            color: #0a0e1a;
            border: none;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            font-weight: 600;
            margin-right: 10px;
        }
        .trade-btn.sell { background: #ff4757; color: white; }
        .trade-btn.emergency { background: #f5a623; color: #0a0e1a; }
        
        .agent-status {
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        .agent-tag {
            background: #252b3d;
            padding: 5px 12px;
            border-radius: 20px;
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        .agent-tag.running { border: 1px solid #00d4aa; }
        .agent-tag.training { border: 1px solid #f5a623; }
        .agent-tag.idle { border: 1px solid #8b92a8; }
        
        .sector-heatmap {
            display: flex;
            gap: 5px;
            flex-wrap: wrap;
        }
        .sector-tag {
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 11px;
        }
        .heat-high { background: rgba(0, 212, 170, 0.3); color: #00d4aa; }
        .heat-medium { background: rgba(245, 166, 35, 0.3); color: #f5a623; }
        .heat-low { background: rgba(255, 71, 87, 0.3); color: #ff4757; }
        
        .risk-gauge {
            text-align: center;
            padding: 20px;
        }
        .risk-value { font-size: 36px; font-weight: bold; }
        .risk-label { font-size: 12px; color: #8b92a8; margin-top: 5px; }
        
        @media (max-width: 1200px) {
            .grid { grid-template-columns: repeat(2, 1fr); }
        }
        @media (max-width: 768px) {
            .grid { grid-template-columns: 1fr; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Alpha Dashboard V2.0</h1>
        <div class="broker-status">
            <div>
                <span class="status-dot status-green"></span>
                PTrade 已连接 (45ms)
            </div>
            <div>
                <span>可用资金: ¥150,000</span>
            </div>
            <div>
                <span>总资产: ¥1,085,000</span>
            </div>
        </div>
    </div>
    
    <div class="grid">
        <!-- 面板1: 总览 -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">📈 市场总览</span>
            </div>
            <div class="index-card">
                <div class="index-name">上证指数</div>
                <div class="index-price">3,300.50</div>
                <div class="index-change positive">+0.25%</div>
            </div>
            <div class="index-card">
                <div class="index-name">深证成指</div>
                <div class="index-price">10,500.30</div>
                <div class="index-change negative">-0.15%</div>
            </div>
            <div class="index-card">
                <div class="index-name">创业板指</div>
                <div class="index-price">2,100.80</div>
                <div class="index-change negative">-0.45%</div>
            </div>
        </div>
        
        <!-- 面板2: 持仓 -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">💼 持仓概览</span>
            </div>
            <div class="metric">
                <span class="metric-label">总资产</span>
                <span class="metric-value">¥1,085,000</span>
            </div>
            <div class="metric">
                <span class="metric-label">总收益</span>
                <span class="metric-value positive">+8.50%</span>
            </div>
            <div class="metric">
                <span class="metric-label">可用现金</span>
                <span class="metric-value">¥150,000</span>
            </div>
            <div class="metric">
                <span class="metric-label">持仓数量</span>
                <span class="metric-value">2只</span>
            </div>
        </div>
        
        <!-- 面板3: 信号 -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">📡 信号队列</span>
            </div>
            <div class="metric">
                <span class="metric-label">待处理</span>
                <span class="metric-value">0</span>
            </div>
            <div class="metric">
                <span class="metric-label">今日已执行</span>
                <span class="metric-value">3</span>
            </div>
            <div class="metric">
                <span class="metric-label">成功率</span>
                <span class="metric-value positive">85%</span>
            </div>
            <div style="margin-top: 15px;">
                <button class="trade-btn">快速买入</button>
                <button class="trade-btn sell">快速卖出</button>
            </div>
        </div>
        
        <!-- 面板4: Agent -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">🤖 Agent状态</span>
            </div>
            <div class="agent-status">
                <span class="agent-tag running">● Chief</span>
                <span class="agent-tag running">● Scout</span>
                <span class="agent-tag running">● Picker</span>
                <span class="agent-tag running">● Guard</span>
                <span class="agent-tag training">◐ DRL</span>
                <span class="agent-tag running">● Sentiment</span>
                <span class="agent-tag idle">○ Trader</span>
            </div>
        </div>
        
        <!-- 面板5: 策略 -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">🧠 策略绩效</span>
            </div>
            <div class="metric">
                <span class="metric-label">动量策略</span>
                <span class="metric-value positive">+12.5%</span>
            </div>
            <div class="metric">
                <span class="metric-label">价值策略</span>
                <span class="metric-value positive">+8.3%</span>
            </div>
            <div class="metric">
                <span class="metric-label">质量策略</span>
                <span class="metric-value positive">+6.7%</span>
            </div>
            <div class="metric">
                <span class="metric-label">情绪策略</span>
                <span class="metric-value positive">+15.2%</span>
            </div>
        </div>
        
        <!-- 面板6: 组合分析 -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">📊 组合分析</span>
            </div>
            <div class="metric">
                <span class="metric-label">Sharpe比率</span>
                <span class="metric-value positive">1.85</span>
            </div>
            <div class="metric">
                <span class="metric-label">最大回撤</span>
                <span class="metric-value negative">-8.5%</span>
            </div>
            <div class="metric">
                <span class="metric-label">选股贡献</span>
                <span class="metric-value positive">+3.5%</span>
            </div>
            <div class="metric">
                <span class="metric-label">配置贡献</span>
                <span class="metric-value positive">+2.1%</span>
            </div>
        </div>
        
        <!-- 面板7: 舆情 -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">📰 舆情热度</span>
            </div>
            <div class="sector-heatmap">
                <span class="sector-tag heat-high">新能源 +35%</span>
                <span class="sector-tag heat-medium">科技 +12%</span>
                <span class="sector-tag heat-medium">消费 +8%</span>
                <span class="sector-tag heat-low">医药 -5%</span>
                <span class="sector-tag heat-low">地产 -25%</span>
            </div>
            <div style="margin-top: 15px; font-size: 12px; color: #8b92a8;">
                <div>🔥 固态电池技术突破</div>
                <div>🔥 AI算力需求爆发</div>
                <div>❄️ 地产政策收紧</div>
            </div>
        </div>
        
        <!-- 面板8: DRL -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">🤖 DRL状态</span>
            </div>
            <div class="metric">
                <span class="metric-label">训练进度</span>
                <span class="metric-value">45/100</span>
            </div>
            <div class="metric">
                <span class="metric-label">置信度</span>
                <span class="metric-value positive">72%</span>
            </div>
            <div class="metric">
                <span class="metric-label">建议仓位</span>
                <span class="metric-value">70%</span>
            </div>
            <div class="metric">
                <span class="metric-label">损失趋势</span>
                <span class="metric-value positive">↓ 下降</span>
            </div>
        </div>
        
        <!-- 面板9: 风险 -->
        <div class="panel">
            <div class="panel-header">
                <span class="panel-title">⚠️ 风险监控</span>
            </div>
            <div class="risk-gauge">
                <div class="risk-value" style="color: #f5a623;">中</div>
                <div class="risk-label">风险等级</div>
            </div>
            <div class="metric">
                <span class="metric-label">VaR(95%)</span>
                <span class="metric-value">¥15,200</span>
            </div>
            <div class="metric">
                <span class="metric-label">Beta</span>
                <span class="metric-value">0.92</span>
            </div>
            <div style="margin-top: 10px;">
                <button class="trade-btn emergency">⚡ 紧急平仓</button>
            </div>
        </div>
    </div>
    
    <script>
        // 定时刷新数据
        setInterval(() => {
            fetch('/api/market/overview')
                .then(r => r.json())
                .then(data => console.log('Market update:', data));
        }, 5000);
    </script>
</body>
</html>
    '''
    return html


def create_templates():
    """创建模板目录和文件"""
    template_dir = os.path.join(os.path.dirname(__file__), 'templates')
    os.makedirs(template_dir, exist_ok=True)
    
    # 创建dashboard_v2.html模板
    template_path = os.path.join(template_dir, 'dashboard_v2.html')
    if not os.path.exists(template_path):
        with open(template_path, 'w', encoding='utf-8') as f:
            f.write('''{% extends "base.html" %}
{% block content %}
<div id="dashboard-v2"></div>
<script src="/static/js/dashboard_v2.js"></script>
{% endblock %}''')


if __name__ == '__main__':
    create_templates()
    
    logger.info("="*60)
    logger.info("🚀 Alpha Dashboard V2.0 启动")
    logger.info("="*60)
    logger.info("访问地址: http://localhost:5000/dashboard")
    logger.info("API文档: http://localhost:5000/api/...")
    
    if SOCKETIO_AVAILABLE:
        socketio.run(app, host='0.0.0.0', port=5000, debug=False)
    else:
        app.run(host='0.0.0.0', port=5000, debug=False)
