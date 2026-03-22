"""
Alpha-Genesis V6.1 SimEdge - 模拟盘 API 服务
=============================================
提供 RESTful API 接口，支持模拟盘的所有操作

Base Path: /v3/api/simulation
Author: Alpha-Genesis Team
Version: 6.1.0
"""

from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
import json
from datetime import datetime
from typing import Dict, Any, Optional
import os
import sys

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from simulation_trading_engine import (
    SimulationTradingEngine, SimulationEngineIntegration,
    OrderSide, OrderType, OrderStatus, create_simulation_engine
)
from loguru import logger

# 初始化 Flask 应用
app = Flask(__name__)
CORS(app)

# 初始化模拟盘引擎
sim_engine: Optional[SimulationTradingEngine] = None
sim_integration: Optional[SimulationEngineIntegration] = None


def init_engine(db_path: str = "simulation_trading.db"):
    """初始化引擎"""
    global sim_engine, sim_integration
    sim_engine = create_simulation_engine(db_path)
    sim_integration = SimulationEngineIntegration(sim_engine)
    logger.info("模拟盘 API 服务初始化完成")


# ========== 装饰器 ==========

def require_json(f):
    """要求 JSON 请求体"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not request.is_json:
            return jsonify({'success': False, 'error': '需要 JSON 请求体'}), 400
        return f(*args, **kwargs)
    return decorated


def handle_errors(f):
    """统一错误处理"""
    @wraps(f)
    def decorated(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except Exception as e:
            logger.error(f"API 错误: {e}")
            return jsonify({
                'success': False,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }), 500
    return decorated


# ========== 账户管理 API ==========

@app.route('/v3/api/simulation/accounts', methods=['GET'])
@handle_errors
def list_accounts():
    """获取所有模拟账户列表"""
    accounts = sim_engine.get_all_accounts()
    return jsonify({
        'success': True,
        'data': [acc.to_dict() for acc in accounts],
        'count': len(accounts),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/v3/api/simulation/accounts', methods=['POST'])
@require_json
@handle_errors
def create_account():
    """创建模拟账户"""
    data = request.get_json()
    
    name = data.get('name')
    initial_capital = data.get('initial_capital', 1000000.0)
    settings = data.get('settings', {})
    
    if not name:
        return jsonify({'success': False, 'error': '缺少账户名称'}), 400
    
    account = sim_engine.create_account(name, initial_capital, settings)
    
    return jsonify({
        'success': True,
        'data': account.to_dict(),
        'message': f'账户 {account.account_id} 创建成功',
        'timestamp': datetime.now().isoformat()
    }), 201


@app.route('/v3/api/simulation/accounts/<account_id>', methods=['GET'])
@handle_errors
def get_account(account_id: str):
    """获取账户详情"""
    account = sim_engine.get_account(account_id)
    if not account:
        return jsonify({'success': False, 'error': '账户不存在'}), 404
    
    return jsonify({
        'success': True,
        'data': account.to_dict(),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/v3/api/simulation/accounts/<account_id>/summary', methods=['GET'])
@handle_errors
def get_account_summary(account_id: str):
    """获取账户完整摘要（含持仓、订单、成交）"""
    summary = sim_engine.export_account_summary(account_id)
    if not summary:
        return jsonify({'success': False, 'error': '账户不存在'}), 404
    
    return jsonify({
        'success': True,
        'data': summary,
        'timestamp': datetime.now().isoformat()
    })


# ========== 持仓管理 API ==========

@app.route('/v3/api/simulation/accounts/<account_id>/positions', methods=['GET'])
@handle_errors
def get_positions(account_id: str):
    """获取账户持仓"""
    account = sim_engine.get_account(account_id)
    if not account:
        return jsonify({'success': False, 'error': '账户不存在'}), 404
    
    positions = sim_engine.get_positions(account_id)
    
    return jsonify({
        'success': True,
        'data': [pos.to_dict() for pos in positions],
        'count': len(positions),
        'account_id': account_id,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/v3/api/simulation/accounts/<account_id>/positions/<symbol>', methods=['GET'])
@handle_errors
def get_position(account_id: str, symbol: str):
    """获取单个持仓详情"""
    position = sim_engine.get_position(account_id, symbol)
    if not position:
        return jsonify({'success': False, 'error': '持仓不存在'}), 404
    
    return jsonify({
        'success': True,
        'data': position.to_dict(),
        'timestamp': datetime.now().isoformat()
    })


# ========== 订单管理 API ==========

@app.route('/v3/api/simulation/accounts/<account_id>/orders', methods=['GET'])
@handle_errors
def get_orders(account_id: str):
    """获取账户订单列表"""
    account = sim_engine.get_account(account_id)
    if not account:
        return jsonify({'success': False, 'error': '账户不存在'}), 404
    
    # 查询参数
    status = request.args.get('status')
    limit = request.args.get('limit', 100, type=int)
    
    order_status = None
    if status:
        try:
            order_status = OrderStatus(status)
        except ValueError:
            return jsonify({'success': False, 'error': f'无效的订单状态: {status}'}), 400
    
    orders = sim_engine.get_orders(account_id, order_status, limit)
    
    return jsonify({
        'success': True,
        'data': [order.to_dict() for order in orders],
        'count': len(orders),
        'account_id': account_id,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/v3/api/simulation/accounts/<account_id>/orders', methods=['POST'])
@require_json
@handle_errors
def submit_order(account_id: str):
    """提交订单"""
    data = request.get_json()
    
    # 必需参数
    symbol = data.get('symbol')
    side = data.get('side')
    quantity = data.get('quantity')
    
    if not all([symbol, side, quantity]):
        return jsonify({
            'success': False, 
            'error': '缺少必需参数: symbol, side, quantity'
        }), 400
    
    # 解析参数
    try:
        order_side = OrderSide(side.lower())
        order_type = OrderType(data.get('order_type', 'market').lower())
    except ValueError as e:
        return jsonify({'success': False, 'error': f'无效的参数: {e}'}), 400
    
    # 提交订单
    success, message, order = sim_engine.submit_order(
        account_id=account_id,
        symbol=symbol,
        side=order_side,
        quantity=int(quantity),
        order_type=order_type,
        price=data.get('price'),
        stop_price=data.get('stop_price'),
        strategy_id=data.get('strategy_id'),
        tags=data.get('tags', {})
    )
    
    if success:
        return jsonify({
            'success': True,
            'data': order.to_dict(),
            'message': message,
            'timestamp': datetime.now().isoformat()
        }), 201
    else:
        return jsonify({
            'success': False,
            'error': message,
            'timestamp': datetime.now().isoformat()
        }), 400


@app.route('/v3/api/simulation/orders/<order_id>', methods=['GET'])
@handle_errors
def get_order(order_id: str):
    """获取订单详情"""
    order = sim_engine.get_order(order_id)
    if not order:
        return jsonify({'success': False, 'error': '订单不存在'}), 404
    
    return jsonify({
        'success': True,
        'data': order.to_dict(),
        'timestamp': datetime.now().isoformat()
    })


@app.route('/v3/api/simulation/orders/<order_id>/cancel', methods=['POST'])
@handle_errors
def cancel_order(order_id: str):
    """取消订单"""
    success, message = sim_engine.cancel_order(order_id)
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'order_id': order_id,
            'timestamp': datetime.now().isoformat()
        })
    else:
        return jsonify({
            'success': False,
            'error': message,
            'timestamp': datetime.now().isoformat()
        }), 400


# ========== 成交记录 API ==========

@app.route('/v3/api/simulation/accounts/<account_id>/trades', methods=['GET'])
@handle_errors
def get_trades(account_id: str):
    """获取成交记录"""
    account = sim_engine.get_account(account_id)
    if not account:
        return jsonify({'success': False, 'error': '账户不存在'}), 404
    
    limit = request.args.get('limit', 100, type=int)
    trades = sim_engine.get_trades(account_id, limit)
    
    return jsonify({
        'success': True,
        'data': [trade.to_dict() for trade in trades],
        'count': len(trades),
        'account_id': account_id,
        'timestamp': datetime.now().isoformat()
    })


# ========== 策略集成 API ==========

@app.route('/v3/api/simulation/strategies/<strategy_id>/account', methods=['POST'])
@require_json
@handle_errors
def create_strategy_account(strategy_id: str):
    """为策略创建模拟账户"""
    data = request.get_json() or {}
    
    strategy_name = data.get('strategy_name', strategy_id)
    initial_capital = data.get('initial_capital', 1000000.0)
    
    account = sim_integration.create_strategy_account(
        strategy_id, strategy_name, initial_capital
    )
    
    return jsonify({
        'success': True,
        'data': account.to_dict(),
        'strategy_id': strategy_id,
        'message': f'策略账户创建成功: {account.account_id}',
        'timestamp': datetime.now().isoformat()
    }), 201


@app.route('/v3/api/simulation/strategies/<strategy_id>/signals', methods=['POST'])
@require_json
@handle_errors
def execute_strategy_signal(strategy_id: str):
    """执行策略信号"""
    data = request.get_json()
    
    success, message = sim_integration.execute_strategy_signal(strategy_id, data)
    
    if success:
        return jsonify({
            'success': True,
            'message': message,
            'strategy_id': strategy_id,
            'signal': data,
            'timestamp': datetime.now().isoformat()
        })
    else:
        return jsonify({
            'success': False,
            'error': message,
            'strategy_id': strategy_id,
            'timestamp': datetime.now().isoformat()
        }), 400


@app.route('/v3/api/simulation/strategies/<strategy_id>/performance', methods=['GET'])
@handle_errors
def get_strategy_performance(strategy_id: str):
    """获取策略绩效"""
    performance = sim_integration.get_strategy_performance(strategy_id)
    
    if not performance:
        return jsonify({
            'success': False,
            'error': f'策略 {strategy_id} 未找到或暂无绩效数据'
        }), 404
    
    return jsonify({
        'success': True,
        'data': performance,
        'strategy_id': strategy_id,
        'timestamp': datetime.now().isoformat()
    })


@app.route('/v3/api/simulation/strategies/performance', methods=['GET'])
@handle_errors
def get_all_strategies_performance():
    """获取所有策略绩效对比"""
    performances = sim_integration.get_all_strategies_performance()
    
    return jsonify({
        'success': True,
        'data': performances,
        'count': len(performances),
        'timestamp': datetime.now().isoformat()
    })


# ========== 风控检查 API ==========

@app.route('/v3/api/simulation/accounts/<account_id>/risk-check', methods=['POST'])
@require_json
@handle_errors
def check_risk(account_id: str):
    """风险检查"""
    data = request.get_json()
    
    symbol = data.get('symbol')
    quantity = data.get('quantity')
    side = data.get('side')
    
    if not all([symbol, quantity, side]):
        return jsonify({
            'success': False,
            'error': '缺少必需参数: symbol, quantity, side'
        }), 400
    
    try:
        order_side = OrderSide(side.lower())
    except ValueError:
        return jsonify({'success': False, 'error': f'无效的 side: {side}'}), 400
    
    passed, reason = sim_engine.check_risk_limits(
        account_id, symbol, int(quantity), order_side
    )
    
    return jsonify({
        'success': True,
        'passed': passed,
        'reason': reason,
        'account_id': account_id,
        'timestamp': datetime.now().isoformat()
    })


# ========== 批量操作 API ==========

@app.route('/v3/api/simulation/accounts/<account_id>/batch-orders', methods=['POST'])
@require_json
@handle_errors
def batch_submit_orders(account_id: str):
    """批量提交订单"""
    data = request.get_json()
    orders = data.get('orders', [])
    
    if not orders:
        return jsonify({'success': False, 'error': '订单列表为空'}), 400
    
    results = []
    for order_data in orders:
        try:
            success, message, order = sim_engine.submit_order(
                account_id=account_id,
                symbol=order_data['symbol'],
                side=OrderSide(order_data['side'].lower()),
                quantity=int(order_data['quantity']),
                order_type=OrderType(order_data.get('order_type', 'market').lower()),
                price=order_data.get('price'),
                strategy_id=order_data.get('strategy_id'),
                tags=order_data.get('tags', {})
            )
            results.append({
                'success': success,
                'message': message,
                'order': order.to_dict() if order else None
            })
        except Exception as e:
            results.append({
                'success': False,
                'error': str(e),
                'order_data': order_data
            })
    
    success_count = sum(1 for r in results if r.get('success'))
    
    return jsonify({
        'success': success_count > 0,
        'data': results,
        'summary': {
            'total': len(orders),
            'success': success_count,
            'failed': len(orders) - success_count
        },
        'timestamp': datetime.now().isoformat()
    })


# ========== 价格更新 API ==========

@app.route('/v3/api/simulation/prices', methods=['POST'])
@require_json
@handle_errors
def update_prices():
    """批量更新价格"""
    data = request.get_json()
    prices = data.get('prices', {})
    
    if not prices:
        return jsonify({'success': False, 'error': '价格数据为空'}), 400
    
    sim_engine.update_positions_price(prices)
    
    return jsonify({
        'success': True,
        'message': f'已更新 {len(prices)} 只股票价格',
        'prices': prices,
        'timestamp': datetime.now().isoformat()
    })


# ========== 系统状态 API ==========

@app.route('/v3/api/simulation/status', methods=['GET'])
@handle_errors
def get_system_status():
    """获取模拟盘系统状态"""
    accounts = sim_engine.get_all_accounts()
    
    total_accounts = len(accounts)
    total_equity = sum(acc.total_equity for acc in accounts)
    total_realized_pnl = sum(acc.realized_pnl for acc in accounts)
    total_unrealized_pnl = sum(acc.unrealized_pnl for acc in accounts)
    
    return jsonify({
        'success': True,
        'data': {
            'status': 'running',
            'version': '6.1.0',
            'total_accounts': total_accounts,
            'total_equity': total_equity,
            'total_realized_pnl': total_realized_pnl,
            'total_unrealized_pnl': total_unrealized_pnl,
            'total_pnl': total_realized_pnl + total_unrealized_pnl
        },
        'timestamp': datetime.now().isoformat()
    })


# ========== 健康检查 ==========

@app.route('/v3/api/simulation/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        'status': 'healthy',
        'service': 'alpha-simulation-api',
        'version': '6.1.0',
        'timestamp': datetime.now().isoformat()
    })


# ========== 错误处理 ==========

@app.errorhandler(404)
def not_found(error):
    return jsonify({
        'success': False,
        'error': 'API 端点不存在',
        'timestamp': datetime.now().isoformat()
    }), 404


@app.errorhandler(405)
def method_not_allowed(error):
    return jsonify({
        'success': False,
        'error': '请求方法不允许',
        'timestamp': datetime.now().isoformat()
    }), 405


# ========== 启动服务 ==========

def run_api_server(host: str = '0.0.0.0', port: int = 5002, debug: bool = False):
    """运行 API 服务器"""
    init_engine()
    logger.info(f"启动模拟盘 API 服务 | {host}:{port}")
    app.run(host=host, port=port, debug=debug)


if __name__ == '__main__':
    run_api_server()
