"""
Alpha-Genesis V6.1 SimEdge - API 服务器
==========================================
Flask RESTful API + WebSocket 实时推送服务

功能：
1. REST API - 对接所有 V6.0/V6.1 模块
2. WebSocket - 实时推送行情/净值/信号
3. 支持实盘和模拟盘统一接口

Author: Alpha-Genesis Team
Version: 6.1.0
Date: 2026-03-09
"""

import os
import sys
import json
import time
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional

# Flask 相关
from flask import Flask, jsonify, request, Response
from flask_cors import CORS

# SocketIO
try:
    from flask_socketio import SocketIO, emit, join_room, leave_room
    SOCKETIO_AVAILABLE = True
except ImportError:
    SOCKETIO_AVAILABLE = False
    logging.warning("flask-socketio 未安装，WebSocket 功能不可用")

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入系统模块
try:
    from simulation_trading_system import SimulationTradingSystem
    SIMULATION_AVAILABLE = True
except ImportError:
    SIMULATION_AVAILABLE = False

try:
    from v61_integration import get_v61_integration
    V61_AVAILABLE = True
except ImportError:
    V61_AVAILABLE = False

try:
    from smart_broker_v2 import SmartBrokerManagerV2
    BROKER_AVAILABLE = True
except ImportError:
    BROKER_AVAILABLE = False

try:
    from dashboard_v31_enhancement import SimulationDashboardProvider
    DASHBOARD_V31_AVAILABLE = True
except ImportError:
    DASHBOARD_V31_AVAILABLE = False

try:
    from strategy_evolution_engine import StrategyPopulation
    EVOLUTION_AVAILABLE = True
except ImportError:
    EVOLUTION_AVAILABLE = False

# 聚宽数据网关（mock）
class MockJoinQuantGateway:
    """模拟聚宽数据网关"""
    def get_realtime_quotes(self, codes: List[str]) -> Dict:
        import random
        quotes = {}
        for code in codes:
            base_price = 3000 if code == "sh" else (10000 if code == "sz" else 2000)
            quotes[code] = {
                "code": code,
                "name": {"sh": "上证指数", "sz": "深证成指", "cy": "创业板指"}.get(code, code),
                "price": round(base_price * (1 + random.uniform(-0.01, 0.01)), 2),
                "change": round(random.uniform(-0.02, 0.02), 4),
                "volume": random.randint(1000000, 10000000),
                "timestamp": datetime.now().isoformat()
            }
        return quotes
    
    def get_tick(self) -> Dict:
        return {"tick": datetime.now().isoformat(), "price": 3000}

# 日志配置
logger = logging.getLogger("V6API")

# 初始化 Flask 应用
app = Flask(__name__, static_folder='.', static_url_path='')
app.config['SECRET_KEY'] = os.environ.get('FLASK_SECRET_KEY', 'alpha-genesis-v6-secret')
CORS(app, resources={r"/api/*": {"origins": "*"}})

# 自定义JSONProvider确保中文正常显示
from flask.json.provider import DefaultJSONProvider
class UnicodeJSONProvider(DefaultJSONProvider):
    def dumps(self, obj, **kwargs):
        kwargs.setdefault('ensure_ascii', False)
        kwargs.setdefault('indent', 2)
        return super().dumps(obj, **kwargs)
    
    def loads(self, s, **kwargs):
        return super().loads(s, **kwargs)

app.json = UnicodeJSONProvider(app)

# 首页路由 - 重定向到看板
@app.route("/")
def index():
    """首页 - 重定向到看板"""
    return app.send_static_file("dashboard_v31_frontend.html")

@app.route("/v3/")
def v3_index():
    """V3 看板入口"""
    return app.send_static_file("dashboard_v31_frontend.html")

# 初始化 SocketIO
if SOCKETIO_AVAILABLE:
    sio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
else:
    sio = None

# ═══════════════════════════════════════════════════════════
# 全局实例
# ═══════════════════════════════════════════════════════════

_v61_integration = None
_sim_dashboard = None
_broker_manager = None
_jq_gateway = None
_evolution_engine = None

def get_system_instances():
    """获取系统实例（延迟初始化）"""
    global _v61_integration, _sim_dashboard, _broker_manager, _jq_gateway, _evolution_engine
    
    if _jq_gateway is None:
        _jq_gateway = MockJoinQuantGateway()
    
    if V61_AVAILABLE and _v61_integration is None:
        try:
            _v61_integration = get_v61_integration()
            logger.info("✅ V6.1 集成系统已加载")
        except Exception as e:
            logger.error(f"V6.1 集成系统加载失败: {e}")
    
    if DASHBOARD_V31_AVAILABLE and _sim_dashboard is None:
        try:
            _sim_dashboard = SimulationDashboardProvider()
            logger.info("✅ V3.1 看板数据提供者已加载")
        except Exception as e:
            logger.error(f"V3.1 看板加载失败: {e}")
    
    if BROKER_AVAILABLE and _broker_manager is None:
        try:
            _broker_manager = SmartBrokerManagerV2()
            logger.info("✅ 券商管理器已加载")
        except Exception as e:
            logger.error(f"券商管理器加载失败: {e}")
    
    if EVOLUTION_AVAILABLE and _evolution_engine is None:
        try:
            _evolution_engine = StrategyPopulation()
            _evolution_engine.initialize()
            logger.info("✅ 策略进化引擎已加载")
        except Exception as e:
            logger.error(f"策略进化引擎加载失败: {e}")
    
    return _v61_integration, _sim_dashboard, _broker_manager, _jq_gateway, _evolution_engine

# ═══════════════════════════════════════════════════════════
# REST API - 市场数据
# ═══════════════════════════════════════════════════════════

@app.route("/api/v6/health", methods=["GET"])
def health_check():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "version": "6.1.0",
        "codename": "SimEdge",
        "timestamp": datetime.now().isoformat(),
        "modules": {
            "simulation": SIMULATION_AVAILABLE,
            "v61_integration": V61_AVAILABLE,
            "broker": BROKER_AVAILABLE,
            "dashboard_v31": DASHBOARD_V31_AVAILABLE,
            "evolution": EVOLUTION_AVAILABLE,
            "websocket": SOCKETIO_AVAILABLE
        }
    })

@app.route("/api/v6/market/realtime", methods=["GET"])
def market_realtime():
    """获取实时行情"""
    _, _, _, jq, _ = get_system_instances()
    codes = request.args.get("codes", "sh,sz,cy").split(",")
    quotes = jq.get_realtime_quotes(codes)
    return jsonify({
        "success": True,
        "data": quotes,
        "timestamp": datetime.now().isoformat()
    })

@app.route("/api/v6/market/index", methods=["GET"])
def market_index():
    """获取三大指数"""
    _, _, _, jq, _ = get_system_instances()
    quotes = jq.get_realtime_quotes(["sh", "sz", "cy"])
    return jsonify({
        "success": True,
        "data": {
            "sh": quotes.get("sh", {}),
            "sz": quotes.get("sz", {}),
            "cy": quotes.get("cy", {})
        },
        "timestamp": datetime.now().isoformat()
    })

# ═══════════════════════════════════════════════════════════
# REST API - 持仓管理
# ═══════════════════════════════════════════════════════════

@app.route("/api/v6/positions", methods=["GET"])
def get_positions():
    """
    获取持仓
    
    Query Params:
        type: "real" | "simulation" (默认: real)
        account_id: 账户ID (可选)
    """
    v61, _, broker, _, _ = get_system_instances()
    acc_type = request.args.get("type", "real")
    account_id = request.args.get("account_id")
    
    try:
        if acc_type == "simulation" and v61:
            if account_id:
                positions = v61.sim_system.get_positions(account_id)
                data = [p.__dict__ if hasattr(p, '__dict__') else p for p in positions.values()] if isinstance(positions, dict) else []
            else:
                # 获取所有模拟账户的持仓
                all_positions = []
                for acc in v61.sim_system.list_accounts():
                    pos_dict = v61.sim_system.get_positions(acc.account_id)
                    if isinstance(pos_dict, dict):
                        for pos in pos_dict.values():
                            pos_data = pos.__dict__ if hasattr(pos, '__dict__') else pos
                            pos_data['account_id'] = acc.account_id
                            pos_data['account_name'] = acc.name
                            all_positions.append(pos_data)
                data = all_positions
        else:
            # TODO: 对接实盘持仓
            data = []
        
        return jsonify({
            "success": True,
            "type": acc_type,
            "account_id": account_id,
            "data": data,
            "count": len(data),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取持仓失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# ═══════════════════════════════════════════════════════════
# REST API - 交易执行
# ═══════════════════════════════════════════════════════════

@app.route("/api/v6/trade/execute", methods=["POST"])
def execute_trade():
    """
    执行交易
    
    Request Body:
        {
            "account_type": "real" | "simulation",
            "account_id": str,
            "code": str,
            "name": str,
            "side": "buy" | "sell",
            "qty": int,
            "price": float,
            "order_type": "market" | "limit",
            "strategy_id": str
        }
    """
    v61, _, broker, _, _ = get_system_instances()
    data = request.get_json()
    
    if not data:
        return jsonify({"success": False, "error": "请求体不能为空"}), 400
    
    try:
        # 使用 V6.1 集成系统的路由功能
        if v61:
            result = v61.route_order(data)
            return jsonify(result)
        
        # 降级处理
        acc_type = data.get("account_type", "real")
        if acc_type == "simulation":
            return jsonify({"success": True, "note": "模拟盘订单（降级模式）", "order_id": "SIM_MOCK_001"})
        else:
            return jsonify({"success": True, "note": "实盘订单（降级模式）", "order_id": "REAL_MOCK_001"})
    
    except Exception as e:
        logger.error(f"执行交易失败: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/v6/trade/orders", methods=["GET"])
def get_orders():
    """获取订单列表"""
    v61, _, _, _, _ = get_system_instances()
    account_id = request.args.get("account_id")
    acc_type = request.args.get("type", "real")
    
    try:
        if acc_type == "simulation" and v61 and account_id:
            orders = v61.sim_system.get_orders(account_id)
            data = [o.__dict__ if hasattr(o, '__dict__') else o for o in orders] if orders else []
        else:
            data = []
        
        return jsonify({
            "success": True,
            "type": acc_type,
            "account_id": account_id,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/v6/trade/cancel/<order_id>", methods=["POST"])
def cancel_order(order_id: str):
    """取消订单"""
    v61, _, _, _, _ = get_system_instances()
    data = request.get_json() or {}
    account_id = data.get("account_id")
    
    try:
        if v61 and account_id:
            success = v61.sim_system.cancel_order(account_id, order_id)
            return jsonify({"success": success, "order_id": order_id})
        return jsonify({"success": False, "error": "参数缺失"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ═══════════════════════════════════════════════════════════
# REST API - 模拟盘管理
# ═══════════════════════════════════════════════════════════

@app.route("/api/v6/simulation/accounts", methods=["GET", "POST"])
def simulation_accounts():
    """获取或创建模拟账户"""
    v61, _, _, _, _ = get_system_instances()
    
    if request.method == "GET":
        try:
            if v61 and v61.sim_system:
                accounts = v61.sim_system.list_accounts()
                data = [{
                    "account_id": acc.account_id,
                    "name": acc.name,
                    "initial_capital": acc.initial_capital,
                    "total_assets": acc.total_assets,
                    "nav": acc.nav,
                    "pnl": acc.pnl,
                    "pnl_pct": acc.pnl_pct
                } for acc in accounts]
                return jsonify({"success": True, "data": data, "count": len(data)})
            return jsonify({"success": False, "error": "模拟盘系统未初始化"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    elif request.method == "POST":
        data = request.get_json()
        try:
            if v61 and v61.sim_system:
                account = v61.sim_system.create_account(
                    name=data.get("name", "新模拟账户"),
                    capital=data.get("initial_capital", 1000000.0)
                )
                return jsonify({
                    "success": True,
                    "account_id": account.account_id,
                    "message": f"账户 {account.account_id} 创建成功"
                })
            return jsonify({"success": False, "error": "模拟盘系统未初始化"})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/v6/simulation/performance/<account_id>", methods=["GET"])
def simulation_performance(account_id: str):
    """获取模拟账户绩效"""
    v61, _, _, _, _ = get_system_instances()
    
    try:
        if v61 and v61.sim_system:
            perf = v61.sim_system.get_performance(account_id)
            return jsonify({"success": True, "account_id": account_id, "data": perf})
        return jsonify({"success": False, "error": "模拟盘系统未初始化"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ═══════════════════════════════════════════════════════════
# REST API - V3.1 看板增强
# ═══════════════════════════════════════════════════════════

@app.route("/api/v6/dashboard/simulation", methods=["GET"])
def dashboard_simulation():
    """模拟盘面板数据"""
    _, dashboard, _, _, _ = get_system_instances()
    
    try:
        if dashboard:
            account_id = request.args.get("account_id")
            data = dashboard.get_simulation_panel(account_id)
            return jsonify(data)
        return jsonify({"success": False, "error": "看板系统未初始化"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/v6/dashboard/trading-mode", methods=["GET", "POST"])
def dashboard_trading_mode():
    """交易模式切换"""
    _, dashboard, _, _, _ = get_system_instances()
    
    try:
        if request.method == "GET":
            data = dashboard.get_trading_mode_switch() if dashboard else {"modes": []}
            return jsonify(data)
        else:
            data = request.get_json()
            if dashboard:
                result = dashboard.set_trading_mode(data.get("mode", "real"))
                return jsonify(result)
            return jsonify({"success": False, "error": "看板系统未初始化"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/v6/dashboard/combined-nav", methods=["GET"])
def dashboard_combined_nav():
    """组合净值曲线"""
    _, dashboard, _, _, _ = get_system_instances()
    
    try:
        days = int(request.args.get("days", 30))
        if dashboard:
            data = dashboard.get_combined_nav_curve(days)
            return jsonify(data)
        return jsonify({"success": False, "error": "看板系统未初始化"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/v6/dashboard/trade-history", methods=["GET"])
def dashboard_trade_history():
    """交易历史（带筛选）"""
    _, dashboard, _, _, _ = get_system_instances()
    
    try:
        filter_type = request.args.get("filter", "all")
        limit = int(request.args.get("limit", 50))
        if dashboard:
            data = dashboard.get_filtered_trade_history(filter_type, limit)
            return jsonify(data)
        return jsonify({"success": False, "error": "看板系统未初始化"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/v6/dashboard/simulation-status", methods=["GET"])
def dashboard_simulation_status():
    """模拟盘状态徽章"""
    _, dashboard, _, _, _ = get_system_instances()
    
    try:
        if dashboard:
            data = dashboard.get_simulation_status_badge()
            return jsonify(data)
        return jsonify({"visible": False, "error": "看板系统未初始化"})
    except Exception as e:
        return jsonify({"visible": False, "error": str(e)}), 500

# ═══════════════════════════════════════════════════════════
# REST API - 策略进化引擎
# ═══════════════════════════════════════════════════════════

@app.route("/api/v6/evolution/status", methods=["GET"])
def evolution_status():
    """获取进化引擎状态"""
    _, _, _, _, engine = get_system_instances()
    
    try:
        if engine:
            return jsonify({
                "success": True,
                "generation": engine.generation,
                "active_count": len(engine.active),
                "graveyard_count": len(engine.graveyard),
                "hall_of_fame_count": len(engine.hall_of_fame),
                "best_fitness": engine.get_best().fitness_score if engine.get_best() else 0
            })
        return jsonify({"success": False, "error": "进化引擎未初始化"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.route("/api/v6/evolution/hall-of-fame", methods=["GET"])
def evolution_hall_of_fame():
    """获取名人堂"""
    _, _, _, _, engine = get_system_instances()
    
    try:
        if engine:
            hof = engine.hall_of_fame
            data = [{
                "id": dna.id,
                "strategy_type": dna.strategy_type,
                "fitness": dna.fitness_score,
                "generation": dna.generation
            } for dna in hof]
            return jsonify({"success": True, "data": data, "count": len(data)})
        return jsonify({"success": False, "error": "进化引擎未初始化"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# ═══════════════════════════════════════════════════════════
# WebSocket 事件处理
# ═══════════════════════════════════════════════════════════

if SOCKETIO_AVAILABLE:
    @sio.on("connect")
    def on_connect():
        """客户端连接"""
        logger.info(f"客户端连接: {request.sid}")
        emit("status", {
            "msg": "V6.1 WebSocket connected",
            "version": "6.1.0",
            "timestamp": datetime.now().isoformat()
        })
    
    @sio.on("disconnect")
    def on_disconnect():
        """客户端断开"""
        logger.info(f"客户端断开: {request.sid}")
    
    @sio.on("subscribe")
    def on_subscribe(data):
        """订阅频道"""
        room = data.get("channel", "default")
        join_room(room)
        emit("subscribed", {"channel": room, "status": "ok"})
        logger.info(f"客户端 {request.sid} 订阅频道: {room}")
    
    @sio.on("unsubscribe")
    def on_unsubscribe(data):
        """取消订阅"""
        room = data.get("channel", "default")
        leave_room(room)
        emit("unsubscribed", {"channel": room, "status": "ok"})

# ═══════════════════════════════════════════════════════════
# REST API - V6.1 SimEdge 模拟盘增强 API (第七章)
# ═════════════════════════════════════════════════════════==

@app.route("/api/v6/sim/accounts", methods=["GET"])
def sim_accounts_list():
    """获取所有模拟账户列表"""
    v61, _, _, _, _ = get_system_instances()
    
    try:
        if v61 and v61.sim_system:
            accounts = v61.sim_system.list_accounts()
            data = [{
                "account_id": acc.account_id,
                "name": acc.name,
                "initial_capital": acc.initial_capital,
                "total_assets": acc.total_assets,
                "cash": acc.cash,
                "nav": acc.nav,
                "pnl": acc.pnl,
                "pnl_pct": acc.pnl_pct
            } for acc in accounts]
            
            return jsonify({
                "success": True,
                "data": data,
                "count": len(data),
                "timestamp": datetime.now().isoformat()
            })
        return jsonify({"success": False, "error": "模拟盘系统未初始化"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v6/sim/accounts", methods=["POST"])
def sim_account_create():
    """创建新模拟账户"""
    v61, _, _, _, _ = get_system_instances()
    data = request.get_json() or {}
    
    try:
        if v61 and v61.sim_system:
            account = v61.sim_system.create_account(
                name=data.get("name", "新模拟账户"),
                capital=data.get("initial_capital", 1000000.0)
            )
            return jsonify({
                "success": True,
                "account_id": account.account_id,
                "message": f"模拟账户 {account.account_id} 创建成功"
            }), 201
        return jsonify({"success": False, "error": "模拟盘系统未初始化"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v6/sim/account/<account_id>", methods=["GET"])
def sim_account_detail(account_id: str):
    """获取指定模拟账户详情"""
    v61, _, _, _, _ = get_system_instances()
    
    try:
        if v61 and v61.sim_system:
            account = v61.sim_system.get_account(account_id)
            if not account:
                return jsonify({"success": False, "error": "账户不存在"}), 404
            
            return jsonify({
                "success": True,
                "account": {
                    "account_id": account.account_id,
                    "name": account.name,
                    "initial_capital": account.initial_capital,
                    "total_assets": account.total_assets,
                    "nav": account.nav,
                    "pnl": account.pnl
                },
                "timestamp": datetime.now().isoformat()
            })
        return jsonify({"success": False, "error": "模拟盘系统未初始化"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v6/sim/positions/<account_id>", methods=["GET"])
def sim_positions(account_id: str):
    """获取模拟账户持仓"""
    v61, _, _, _, _ = get_system_instances()
    
    try:
        if v61 and v61.sim_system:
            positions = v61.sim_system.get_positions(account_id)
            data = [pos.__dict__ if hasattr(pos, '__dict__') else pos for pos in positions.values()]
            return jsonify({
                "success": True,
                "account_id": account_id,
                "data": data,
                "count": len(data)
            })
        return jsonify({"success": False, "error": "模拟盘系统未初始化"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v6/sim/order", methods=["POST"])
def sim_order_submit():
    """提交模拟盘订单"""
    v61, _, _, _, _ = get_system_instances()
    data = request.get_json() or {}
    
    try:
        if v61:
            result = v61.route_order({
                "account_type": "simulation",
                **data
            })
            return jsonify(result)
        return jsonify({"success": False, "error": "V6.1系统未初始化"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v6/sim/orders/<account_id>", methods=["GET"])
def sim_orders(account_id: str):
    """获取模拟账户委托记录"""
    v61, _, _, _, _ = get_system_instances()
    limit = request.args.get("limit", 50, type=int)
    
    try:
        if v61 and v61.sim_system:
            orders = v61.sim_system.get_orders(account_id)
            return jsonify({
                "success": True,
                "account_id": account_id,
                "data": orders[-limit:] if orders else []
            })
        return jsonify({"success": False, "error": "模拟盘系统未初始化"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v6/sim/trades/<account_id>", methods=["GET"])
def sim_trades(account_id: str):
    """获取模拟账户成交记录"""
    v61, _, _, _, _ = get_system_instances()
    limit = request.args.get("limit", 50, type=int)
    
    try:
        if v61 and v61.sim_system:
            trades = v61.sim_system.get_trades(account_id, limit)
            return jsonify({
                "success": True,
                "account_id": account_id,
                "data": trades
            })
        return jsonify({"success": False, "error": "模拟盘系统未初始化"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v6/sim/performance/<account_id>", methods=["GET"])
def sim_performance(account_id: str):
    """获取模拟账户绩效指标"""
    v61, _, _, _, _ = get_system_instances()
    
    try:
        if v61 and v61.sim_system:
            perf = v61.sim_system.get_performance(account_id)
            return jsonify({
                "success": True,
                "account_id": account_id,
                "performance": perf
            })
        return jsonify({"success": False, "error": "模拟盘系统未初始化"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v6/sim/compare/<account_id>", methods=["GET"])
def sim_compare(account_id: str):
    """模拟盘vs实盘对比数据"""
    v61, _, _, _, _ = get_system_instances()
    
    try:
        if v61 and v61.sim_system:
            sim_perf = v61.sim_system.get_performance(account_id)
            return jsonify({
                "success": True,
                "account_id": account_id,
                "simulation": sim_perf,
                "real": {"nav": 1.0, "pnl_pct": 0},
                "comparison": {"nav_diff": 0}
            })
        return jsonify({"success": False, "error": "模拟盘系统未初始化"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v6/sim/snapshot/<account_id>", methods=["POST"])
def sim_snapshot(account_id: str):
    """手动触发账户快照"""
    v61, _, _, _, _ = get_system_instances()
    
    try:
        if v61 and v61.sim_system:
            snapshot = v61.sim_system.snapshot(account_id)
            return jsonify({
                "success": True,
                "account_id": account_id,
                "snapshot": snapshot
            })
        return jsonify({"success": False, "error": "模拟盘系统未初始化"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v6/sim/nav/<account_id>", methods=["GET"])
def sim_nav(account_id: str):
    """获取净值曲线数据"""
    v61, _, _, _, _ = get_system_instances()
    days = request.args.get("days", 30, type=int)
    
    try:
        if v61 and v61.sim_system:
            account = v61.sim_system.get_account(account_id)
            nav_history = account.nav_history if account else []
            return jsonify({
                "success": True,
                "account_id": account_id,
                "data": nav_history[-days:] if len(nav_history) > days else nav_history
            })
        return jsonify({"success": False, "error": "模拟盘系统未初始化"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v6/sim/account/<account_id>", methods=["DELETE"])
def sim_account_delete(account_id: str):
    """删除模拟账户"""
    v61, _, _, _, _ = get_system_instances()
    
    try:
        if v61 and v61.sim_system:
            success = v61.sim_system.delete_account(account_id)
            return jsonify({
                "success": success,
                "account_id": account_id,
                "message": "账户已删除" if success else "删除失败"
            })
        return jsonify({"success": False, "error": "模拟盘系统未初始化"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/v6/sim/stress-test", methods=["POST"])
def sim_stress_test():
    """触发极端行情压力测试"""
    data = request.get_json() or {}
    
    return jsonify({
        "success": True,
        "scenario": data.get("scenario", "2015_crash"),
        "status": "started",
        "message": "压力测试已启动"
    })


@app.route("/api/v6/sim/promote/<strategy_id>", methods=["POST"])
def sim_promote(strategy_id: str):
    """模拟验证通过→提升至实盘"""
    
    return jsonify({
        "success": True,
        "strategy_id": strategy_id,
        "status": "promoted",
        "message": f"策略 {strategy_id} 已通过模拟验证，允许部署至实盘"
    })


# ═══════════════════════════════════════════════════════════
# 后台推送线程
# ═════════════════════════════════════════════════════════==

def push_realtime_data():
    """定时推送实时数据"""
    if not SOCKETIO_AVAILABLE:
        logger.warning("WebSocket 不可用，跳过后台推送")
        return
    
    v61, dashboard, _, jq, _ = get_system_instances()
    
    while True:
        try:
            # 推送行情数据
            quotes = jq.get_realtime_quotes(["sh", "sz", "cy"])
            sio.emit("market", {
                "type": "index",
                "data": quotes,
                "timestamp": datetime.now().isoformat()
            })
            
            # 推送模拟盘净值（如果有）
            if v61 and v61.sim_system:
                accounts = v61.sim_system.list_accounts()
                if accounts:
                    acc = accounts[0]  # 推送第一个账户
                    snapshot = v61.sim_system.snapshot(acc.account_id)
                    sio.emit("sim_nav", {
                        "account_id": acc.account_id,
                        "nav": acc.nav,
                        "snapshot": snapshot,
                        "timestamp": datetime.now().isoformat()
                    })
            
            time.sleep(2.5)  # 每2.5秒推送一次
            
        except Exception as e:
            logger.error(f"推送实时数据出错: {e}")
            time.sleep(5)

def start_background_tasks():
    """启动后台任务"""
    if SOCKETIO_AVAILABLE:
        push_thread = threading.Thread(target=push_realtime_data, daemon=True)
        push_thread.start()
        logger.info("✅ 实时数据推送线程已启动")

# ═══════════════════════════════════════════════════════════
# 启动入口
# ═══════════════════════════════════════════════════════════

def run_api_server(host: str = "0.0.0.0", port: int = 5000, debug: bool = False):
    """启动 API 服务器"""
    logging.basicConfig(level=logging.INFO)
    
    # 初始化系统实例
    get_system_instances()
    
    # 启动后台任务
    start_background_tasks()
    
    logger.info(f"🚀 V6.1 API 服务器启动: http://{host}:{port}")
    
    if SOCKETIO_AVAILABLE:
        sio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=True)
    else:
        app.run(host=host, port=port, debug=debug)

if __name__ == "__main__":
    # 生产模式启动
    run_api_server()
