#!/usr/bin/env python3
# Alpha Dashboard Server V3.0 - API v6
# 提供看板 V3.0 所需的所有 API 端点

import os
import json
import logging
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient

# 初始化 Flask
app = Flask(__name__)
CORS(app)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('AlphaAPIv6')

# MongoDB 连接
try:
    db = MongoClient('mongodb://localhost:27017').kimi_claw
    mongo_ok = True
except:
    mongo_ok = False
    logger.warning('MongoDB 连接失败，使用内存存储')

# 模拟数据存储
DATA = {
    'market': {
        'sh_index': {'price': 3284.5, 'change': 0.82},
        'sz_index': {'price': 10521, 'change': -0.31},
        'cy_index': {'price': 2134, 'change': 1.24},
        'portfolio_nav': {'price': 108.4, 'change': 2.328}
    },
    'positions': [
        {'symbol': '600519', 'name': '贵州茅台', 'quantity': 100, 'avg_price': 1800, 'current_price': 1924.30, 'pnl': 12430},
        {'symbol': '000858', 'name': '五粮液', 'quantity': 200, 'avg_price': 140, 'current_price': 145.67, 'pnl': 1134}
    ],
    'signals': [
        {'symbol': '600519', 'action': 'BUY', 'price': 1924.30, 'confidence': 92, 'time': '10:30:15'},
        {'symbol': '000858', 'action': 'ADD', 'price': 145.67, 'confidence': 87, 'time': '10:35:22'}
    ],
    'agents': {
        'ChiefAgent': 'active',
        'DRLAgent': 'active',
        'RiskAgent': 'active',
        'EvolutionAgent': 'active'
    },
    'brokers': [
        {'id': 'paper', 'name': '模拟交易', 'active': True, 'quality_score': 95}
    ]
}

# ═══ REST API v6 ═══

@app.route('/api/v6/market/realtime')
def market_realtime():
    return jsonify({
        'timestamp': datetime.now().isoformat(),
        'indices': DATA['market'],
        'update_time': datetime.now().strftime('%H:%M:%S')
    })

@app.route('/api/v6/positions')
def positions():
    return jsonify({
        'positions': DATA['positions'],
        'total_value': sum(p['current_price'] * p['quantity'] for p in DATA['positions']),
        'total_pnl': sum(p['pnl'] for p in DATA['positions'])
    })

@app.route('/api/v6/signals')
def signals():
    return jsonify({
        'signals': DATA['signals'],
        'count': len(DATA['signals']),
        'last_update': datetime.now().isoformat()
    })

@app.route('/api/v6/agents/status')
def agents_status():
    return jsonify({
        'agents': DATA['agents'],
        'active_count': sum(1 for v in DATA['agents'].values() if v == 'active')
    })

@app.route('/api/v6/brokers/status')
def brokers_status():
    return jsonify({
        'brokers': DATA['brokers'],
        'active_broker': next((b for b in DATA['brokers'] if b['active']), None)
    })

@app.route('/api/v6/evolution/status')
def evolution_status():
    return jsonify({
        'generation': 42,
        'best_fitness': 2.15,
        'population_size': 100,
        'diversity': 0.78,
        'last_evolution': '2026-03-07 09:00:00'
    })

@app.route('/api/v6/drl/state')
def drl_state():
    return jsonify({
        'confidence': 0.72,
        'regime': '震荡',
        'generation': 42,
        'algorithm': 'transformer-ppo'
    })

@app.route('/api/v6/risk/decompose')
def risk_decompose():
    return jsonify({
        'total_risk': 0.15,
        'market_risk': 0.08,
        'sector_risk': 0.04,
        'stock_risk': 0.03,
        'var_95': 0.023
    })

@app.route('/api/v6/strategies')
def strategies():
    return jsonify({
        'strategies': [
            {'id': 'momentum_001', 'name': '动量策略V1', 'type': 'momentum', 'sharpe': 1.85, 'status': 'active'},
            {'id': 'mr_002', 'name': '均值回归V2', 'type': 'mean_reversion', 'sharpe': 1.62, 'status': 'active'}
        ],
        'total_count': 50
    })

@app.route('/api/v6/trades/history')
def trades_history():
    limit = request.args.get('limit', 180, type=int)
    return jsonify({
        'trades': [
            {'time': '10:30:15', 'symbol': '600519', 'action': 'BUY', 'price': 1924.30, 'qty': 100, 'pnl': 0},
            {'time': '14:15:22', 'symbol': '000858', 'action': 'SELL', 'price': 145.67, 'qty': 50, 'pnl': 283}
        ],
        'count': 2
    })

@app.route('/api/v6/portfolio/allocation')
def portfolio_allocation():
    return jsonify({
        'stocks': 0.65,
        'cash': 0.25,
        'bonds': 0.10,
        'recommendation': '增加科技股配置'
    })

@app.route('/api/v6/sentiment/events')
def sentiment_events():
    return jsonify({
        'events': [
            {'type': 'policy', 'title': '央行降准', 'impact': 'positive', 'time': '09:00'},
            {'type': 'earnings', 'title': '茅台业绩超预期', 'impact': 'positive', 'time': '10:30'}
        ],
        'overall_sentiment': 68.5
    })

# ═══ POST API ═══

@app.route('/api/v6/trade/execute', methods=['POST'])
def trade_execute():
    data = request.json
    logger.info(f"交易执行: {data}")
    return jsonify({'status': 'success', 'order_id': f'ORD{datetime.now().timestamp()}'})

@app.route('/api/v6/broker/switch', methods=['POST'])
def broker_switch():
    data = request.json
    return jsonify({'status': 'success', 'new_broker': data.get('broker_id')})

@app.route('/api/v6/report/generate', methods=['POST'])
def report_generate():
    data = request.json
    return jsonify({'status': 'success', 'report_url': '/reports/morning_report.html'})

# ═══ WebSocket (简化版) ═══

@app.route('/ws/v6/live')
def ws_live():
    # WebSocket 连接处理
    return jsonify({'status': 'WebSocket endpoint ready'})

# ═══ 静态文件服务 ═══

@app.route('/')
def index():
    return send_from_directory('/opt/alpha', 'Alpha量化看板V3.0.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory('/opt/alpha', filename)

# 健康检查
@app.route('/api/health')
def health():
    return jsonify({
        'status': 'running',
        'version': '6.0.0',
        'codename': 'Alpha-Genesis',
        'mongodb': mongo_ok,
        'timestamp': datetime.now().isoformat()
    })

if __name__ == '__main__':
    logger.info('Alpha Dashboard Server V3.0 启动中...')
    logger.info('API v6 端点已就绪')
    app.run(host='0.0.0.0', port=8765, debug=False, threaded=True)
