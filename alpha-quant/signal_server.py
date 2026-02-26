# signal_server.py --- Alpha Quant 交易信号服务器
# 接收来自 Kimi Claw 的交易信号，推送给 PTrade/QMT 执行

import os
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque
from loguru import logger
from dotenv import load_dotenv
import threading
import time

load_dotenv()

app = Flask(__name__)
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


# ==================== API 路由 ====================

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
    logger.info(f"人工确认: {'开启' if CONFIG['require_human_confirm'] else '关闭'}")
    logger.info(f"飞书通知: {'开启' if CONFIG['feishu_webhook'] else '未配置'}")
    
    app.run(host=CONFIG["host"], port=CONFIG["port"], debug=False)
