# signal_server.py --- Alpha Quant 交易信号服务器 V5.0
# 接收来自 Kimi Claw 的交易信号，推送给 PTrade/QMT 执行
# 集成 Dashboard V2.0 API

import os
import json
import random
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque
from loguru import logger
from dotenv import load_dotenv
import threading
import time

load_dotenv()

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

# 日志配置
logger.add("logs/signal_{time:YYYY-MM-DD}.log", rotation="10 MB", retention="30 days")

# === 信号队列（先进先出，最大100条） ===
signal_queue = deque(maxlen=100)
signal_history = []  # 历史信号记录
LOCK = threading.Lock()

# === 配置 ===
CONFIG = {
    "require_human_confirm": True,  # 是否需要人工确认
    "signal_timeout_seconds": 60,   # 信号超时时间
    "max_pending_signals": 10,      # 最大待处理信号数
    "host": "0.0.0.0",
    "port": int(os.getenv("SIGNAL_PORT", "8765")),
    "feishu_webhook": os.getenv("FEISHU_WEBHOOK_URL", "")
}


class SignalManager:
    """信号管理器"""
    
    @staticmethod
    def add_signal(code: str, action: str, price: float, amount: int, 
                   reason: str = "", strategy: str = "manual", 
                   risk_level: str = "medium", source: str = "kimi") -> Dict:
        """添加新信号"""
        with LOCK:
            # 检查待处理信号数量
            pending_count = len([s for s in signal_queue if s.get("status") == "pending"])
            if pending_count >= CONFIG["max_pending_signals"]:
                return {"success": False, "error": "待处理信号过多，请稍后再试"}
            
            signal_id = len(signal_history) + 1
            
            signal = {
                "id": signal_id,
                "code": code,
                "action": action.lower(),  # buy / sell
                "price": float(price),
                "amount": int(amount),
                "reason": reason,
                "strategy": strategy,
                "risk_level": risk_level,
                "source": source,
                "confirmed": not CONFIG["require_human_confirm"],
                "status": "pending",  # pending / confirmed / rejected / executed / expired
                "created_at": datetime.now().isoformat(),
                "expires_at": (datetime.now().timestamp() + CONFIG["signal_timeout_seconds"]),
                "confirmed_at": None,
                "executed_at": None,
                "confirm_reason": "",
                "execution_result": None
            }
            
            signal_queue.append(signal)
            signal_history.append(signal)
        
        logger.info(f"新信号 #{signal_id}: {action.upper()} {code} @ {price} x {amount} | 原因: {reason}")
        
        # 如果需要人工确认，推送通知
        if CONFIG["require_human_confirm"]:
            notify_for_confirmation(signal)
        
        return {
            "success": True, 
            "signal": signal, 
            "needs_confirm": CONFIG["require_human_confirm"]
        }
    
    @staticmethod
    def get_signals(last_id: int = 0, status: Optional[str] = None) -> List[Dict]:
        """获取信号列表"""
        with LOCK:
            signals = list(signal_queue)
            if last_id > 0:
                signals = [s for s in signals if s["id"] > last_id]
            if status:
                signals = [s for s in signals if s.get("status") == status]
            # 只返回已确认的信号给PTrade
            if status is None:
                signals = [s for s in signals if s.get("confirmed", True)]
            return signals
    
    @staticmethod
    def confirm_signal(signal_id: int, confirmed: bool, reason: str = "") -> Dict:
        """确认/拒绝信号"""
        with LOCK:
            for s in signal_queue:
                if s["id"] == signal_id:
                    if s.get("status") != "pending":
                        return {"success": False, "error": f"信号状态为 {s.get('status')}，无法确认"}
                    
                    s["confirmed"] = confirmed
                    s["status"] = "confirmed" if confirmed else "rejected"
                    s["confirmed_at"] = datetime.now().isoformat()
                    s["confirm_reason"] = reason
                    
                    action = "确认" if confirmed else "拒绝"
                    logger.info(f"信号 #{signal_id} 已{action}: {reason}")
                    return {"success": True, "signal": s}
            
            return {"success": False, "error": "信号不存在"}
    
    @staticmethod
    def mark_executed(signal_id: int, result: Dict) -> Dict:
        """标记信号已执行"""
        with LOCK:
            for s in signal_queue:
                if s["id"] == signal_id:
                    s["status"] = "executed"
                    s["executed_at"] = datetime.now().isoformat()
                    s["execution_result"] = result
                    logger.info(f"信号 #{signal_id} 已执行")
                    return {"success": True}
            return {"success": False, "error": "信号不存在"}
    
    @staticmethod
    def cleanup_expired():
        """清理过期信号"""
        current_time = datetime.now().timestamp()
        with LOCK:
            for s in signal_queue:
                if s.get("status") == "pending" and s.get("expires_at", 0) < current_time:
                    s["status"] = "expired"
                    logger.warning(f"信号 #{s['id']} 已过期")


def notify_for_confirmation(signal: Dict):
    """推送确认通知到飞书"""
    webhook = CONFIG["feishu_webhook"]
    if not webhook:
        return
    
    try:
        import requests
        
        action_emoji = "🟢买入" if signal["action"] == "buy" else "🔴卖出"
        
        msg = (f"📋 **待确认交易信号 #{signal['id']}**\n\n"
               f"操作: {action_emoji}\n"
               f"标的: {signal['code']}\n"
               f"价格: {signal['price']}\n"
               f"数量: {signal['amount']}股\n"
               f"原因: {signal['reason']}\n"
               f"策略: {signal['strategy']}\n"
               f"风险: {signal['risk_level']}\n\n"
               f"请访问 http://localhost:{CONFIG['port']}/api/signals/confirm 进行确认")
        
        requests.post(webhook, json={
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": "📋 交易信号待确认"},
                    "template": "orange"
                },
                "elements": [{"tag": "markdown", "content": msg}]
            }
        }, timeout=5)
        
        logger.info(f"飞书通知已发送 | 信号 #{signal['id']}")
    except Exception as e:
        logger.error(f"飞书通知推送失败: {e}")


# ==================== Dashboard V2.0 API 路由 ====================

@app.route("/dashboard")
def dashboard_v2():
    """Dashboard V2.0 主页"""
    return send_from_directory('static', 'dashboard_v2_full.html')


@app.route("/api/v2/overview")
def api_v2_overview():
    """返回总览数据（实时行情+风控+情绪）"""
    # 模拟数据，实际应从data_gateway获取
    return jsonify({
        "code": 200,
        "data": {
            "indices": {
                "上证指数": {"price": 3387.5, "change_pct": 0.48, "volume": 4200},
                "深证成指": {"price": 10980.3, "change_pct": 0.71, "volume": 5600},
                "创业板指": {"price": 2250.8, "change_pct": 0.89, "volume": 2800}
            },
            "market_sentiment": {
                "overall": 0.35,
                "phase": "回暖期",
                "advice": "轻仓试水，关注AI应用端"
            },
            "risk_status": {
                "level": "GREEN",
                "var_95": -1.2,
                "max_drawdown": -5.8
            },
            "broker": {
                "connected": True,
                "latency_ms": 45,
                "available_cash": 150000
            }
        },
        "timestamp": datetime.now().isoformat()
    })


@app.route("/api/v2/drl-status")
def api_v2_drl_status():
    """返回DRL Agent状态"""
    return jsonify({
        "code": 200,
        "data": {
            "training": False,
            "episode": 2450,
            "confidence": 0.72,
            "loss": 0.0342,
            "status": "converged",
            "recommended_weights": {
                "300750": 0.12,
                "601012": 0.10,
                "002594": 0.08,
                "600519": 0.05
            },
            "expected_sharpe_improvement": "+0.15"
        },
        "timestamp": datetime.now().isoformat()
    })


@app.route("/api/v2/sentiment")
def api_v2_sentiment():
    """返回舆情分析数据"""
    return jsonify({
        "code": 200,
        "data": {
            "overall": 0.35,
            "sector_heatmap": {
                "新能源": 0.72,
                "科技": 0.55,
                "银行": 0.38,
                "消费": 0.15,
                "医药": -0.25,
                "地产": -0.45
            },
            "top_bullish": [
                {"code": "300750", "name": "宁德时代", "score": 0.78, "momentum": 0.25},
                {"code": "002594", "name": "比亚迪", "score": 0.82, "momentum": 0.18}
            ],
            "top_bearish": [
                {"code": "600519", "name": "贵州茅台", "score": -0.42, "momentum": -0.35},
                {"code": "603259", "name": "药明康德", "score": -0.55, "momentum": -0.28}
            ],
            "anomaly_alerts": []
        },
        "timestamp": datetime.now().isoformat()
    })


@app.route("/api/v2/risk")
def api_v2_risk():
    """返回VaR+压力测试+风险分解"""
    return jsonify({
        "code": 200,
        "data": {
            "var": {
                "1d_95": -1.82,
                "5d_95": -3.95,
                "30d_95": -8.21
            },
            "risk_decomposition": {
                "市场风险": 42,
                "行业风险": 25,
                "个股风险": 18,
                "流动性风险": 8,
                "情绪风险": 7
            },
            "stress_test": [
                {"scenario": "2015股灾重现", "impact": -18.5},
                {"scenario": "2020疫情冲击", "impact": -12.3},
                {"scenario": "加息100bp", "impact": -6.7},
                {"scenario": "北向大幅流出", "impact": -4.2}
            ]
        },
        "timestamp": datetime.now().isoformat()
    })


@app.route("/api/v2/trade", methods=["POST"])
def api_v2_trade():
    """接收交易指令（需Guard审批）"""
    data = request.json
    
    # 验证必要字段
    required = ["code", "side", "price", "qty"]
    for field in required:
        if field not in data:
            return jsonify({"code": 400, "error": f"缺少字段: {field}"}), 400
    
    # 模拟Guard审批
    risk_level = "medium"
    if data.get("qty", 0) * data.get("price", 0) > 100000:
        risk_level = "high"
    
    # 创建信号
    result = SignalManager.add_signal(
        code=data["code"],
        action=data["side"],
        price=data["price"],
        amount=data["qty"],
        reason=data.get("reason", "Dashboard交易"),
        strategy=data.get("strategy", "manual"),
        risk_level=risk_level,
        source="dashboard_v2"
    )
    
    if result["success"]:
        return jsonify({
            "code": 200,
            "success": True,
            "order_id": result["signal"]["id"],
            "status": "pending",
            "message": "交易指令已提交，等待Guard审批" if CONFIG["require_human_confirm"] else "交易指令已执行"
        })
    else:
        return jsonify({"code": 429, "success": False, "error": result["error"]}), 429


@app.route("/api/v2/agents")
def api_v2_agents():
    """返回8个Agent状态"""
    return jsonify({
        "code": 200,
        "data": {
            "Chief": {"status": "active", "msg": "已整合DRL+情绪信号，审批3条"},
            "Scout": {"status": "idle", "msg": "舆情报告已发送，情绪：回暖期"},
            "Picker": {"status": "active", "msg": "综合5策略+情绪因子选出8只标的"},
            "Guard": {"status": "alert", "msg": "平安银行浮亏接近预警线"},
            "Trader": {"status": "active", "msg": "已通过PTrade执行2笔，滑点0.02%"},
            "Review": {"status": "idle", "msg": "等待收盘后启动绩效归因"},
            "DRL": {"status": "active", "msg": "置信度72%，建议增配新能源+3%"},
            "Sentiment": {"status": "active", "msg": "贵州茅台负面舆情+45%，建议减仓"}
        },
        "timestamp": datetime.now().isoformat()
    })


@app.route("/api/v2/portfolio")
def api_v2_portfolio():
    """返回持仓数据"""
    return jsonify({
        "code": 200,
        "data": {
            "total_assets": 1085000,
            "cash": 150000,
            "market_value": 935000,
            "total_return": 8.5,
            "positions": [
                {"code": "600036", "name": "招商银行", "qty": 1400, "cost": 35.20, "price": 36.8, "pnl": 8.6},
                {"code": "000001", "name": "平安银行", "qty": 2000, "cost": 12.50, "price": 12.1, "pnl": -3.2},
                {"code": "300750", "name": "宁德时代", "qty": 200, "cost": 185.0, "price": 195.5, "pnl": 5.7},
                {"code": "002475", "name": "立讯精密", "qty": 1000, "cost": 28.6, "price": 30.2, "pnl": 5.6},
                {"code": "601012", "name": "隆基绿能", "qty": 1500, "cost": 22.8, "price": 21.5, "pnl": -5.7}
            ]
        },
        "timestamp": datetime.now().isoformat()
    })


# ==================== 原有API 路由 ====================

@app.route("/api/signals", methods=["GET"])
def get_signals():
    """PTrade/QMT 轮询消费信号"""
    last_id = request.args.get("last_id", 0, type=int)
    status = request.args.get("status")
    
    signals = SignalManager.get_signals(last_id, status)
    return jsonify({
        "code": 200,
        "success": True,
        "signals": signals,
        "count": len(signals)
    })


@app.route("/api/signals", methods=["POST"])
def push_signal():
    """Kimi Claw 推送交易信号"""
    data = request.json
    required_fields = ["code", "action", "price", "amount", "reason"]
    
    for field in required_fields:
        if field not in data:
            return jsonify({"code": 400, "success": False, "error": f"缺少字段: {field}"}), 400
    
    result = SignalManager.add_signal(
        code=data["code"],
        action=data["action"],
        price=data["price"],
        amount=data["amount"],
        reason=data["reason"],
        strategy=data.get("strategy", "manual"),
        risk_level=data.get("risk_level", "medium"),
        source=data.get("source", "kimi")
    )
    
    if result["success"]:
        return jsonify({
            "code": 200, 
            "success": True,
            "signal_id": result["signal"]["id"],
            "needs_confirm": result["needs_confirm"]
        }), 201
    else:
        return jsonify({"code": 429, "success": False, "error": result["error"]}), 429


@app.route("/api/signals/confirm/<int:signal_id>", methods=["POST"])
def confirm_signal_endpoint(signal_id: int):
    """人工确认信号"""
    data = request.json or {}
    reason = data.get("reason", "")
    
    result = SignalManager.confirm_signal(signal_id, True, reason)
    
    if result["success"]:
        return jsonify({"code": 200, "success": True, "message": "信号已确认", "signal": result["signal"]})
    else:
        return jsonify({"code": 400, "success": False, "error": result["error"]}), 400


@app.route("/api/signals/reject/<int:signal_id>", methods=["POST"])
def reject_signal_endpoint(signal_id: int):
    """拒绝信号"""
    data = request.json or {}
    reason = data.get("reason", "")
    
    result = SignalManager.confirm_signal(signal_id, False, reason)
    
    if result["success"]:
        return jsonify({"code": 200, "success": True, "message": "信号已拒绝", "signal": result["signal"]})
    else:
        return jsonify({"code": 400, "success": False, "error": result["error"]}), 400


@app.route("/api/signals/history", methods=["GET"])
def get_history():
    """查看历史信号"""
    limit = int(request.args.get("limit", 50))
    return jsonify({
        "code": 200,
        "success": True,
        "data": signal_history[-limit:],
        "count": len(signal_history)
    })


@app.route("/api/signals/stats", methods=["GET"])
def get_stats():
    """获取统计信息"""
    with LOCK:
        stats = {
            "total": len(signal_history),
            "pending": len([s for s in signal_queue if s.get("status") == "pending"]),
            "confirmed": len([s for s in signal_history if s.get("status") == "confirmed"]),
            "rejected": len([s for s in signal_history if s.get("status") == "rejected"]),
            "executed": len([s for s in signal_history if s.get("status") == "executed"]),
            "expired": len([s for s in signal_history if s.get("status") == "expired"])
        }
    return jsonify({"code": 200, "success": True, "stats": stats})


@app.route("/health", methods=["GET"])
def health_check():
    """健康检查"""
    return jsonify({
        "code": 200,
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "pending_signals": len([s for s in signal_queue if s.get("status") == "pending"])
    })


def cleanup_task():
    """清理过期信号的后台任务"""
    while True:
        time.sleep(10)
        SignalManager.cleanup_expired()


if __name__ == "__main__":
    # 创建日志目录
    os.makedirs("logs", exist_ok=True)
    
    # 启动清理线程
    cleanup_thread = threading.Thread(target=cleanup_task, daemon=True)
    cleanup_thread.start()
    
    logger.info(f"📡 信号服务器启动于 http://{CONFIG['host']}:{CONFIG['port']}")
    logger.info(f"Dashboard V2.0: http://{CONFIG['host']}:{CONFIG['port']}/dashboard")
    logger.info(f"人工确认: {'开启' if CONFIG['require_human_confirm'] else '关闭'}")
    logger.info(f"飞书通知: {'开启' if CONFIG['feishu_webhook'] else '未配置'}")
    
    app.run(host=CONFIG["host"], port=CONFIG["port"], debug=False)
