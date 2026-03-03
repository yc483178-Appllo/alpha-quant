# agent_bus.py --- Multi-Agent 信号总线
# 基于 Redis Pub/Sub 实现Agent间实时通信

import os
import json
import redis
from datetime import datetime
from loguru import logger
from dotenv import load_dotenv

load_dotenv()
logger.add("logs/agent_bus_{time:YYYY-MM-DD}.log", rotation="10 MB", retention="30 days")

class AgentBus:
    """Multi-Agent 信号总线"""

    # 标准频道定义
    CHANNELS = {
        "intel": "alpha:intel",        # Scout → Chief（情报）
        "signals": "alpha:signals",    # Picker → Chief（选股信号）
        "risk": "alpha:risk",          # Guard → Chief（风控）
        "orders": "alpha:orders",      # Chief → Trader（交易指令）
        "trades": "alpha:trades",      # Trader → Review（成交回报）
        "review": "alpha:review",      # Review → Chief（复盘报告）
        "emergency": "alpha:emergency" # 任意Agent → 全体（紧急广播）
    }

    def __init__(self):
        redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
        self.redis = redis.from_url(redis_url)
        self.pubsub = self.redis.pubsub()
        logger.info("Agent信号总线初始化完成")

    def publish(self, channel, message):
        """发布消息到频道"""
        if channel not in self.CHANNELS:
            logger.error(f"未知频道: {channel}")
            return

        envelope = {
            "timestamp": datetime.now().isoformat(),
            "channel": channel,
            "payload": message
        }
        self.redis.publish(self.CHANNELS[channel], json.dumps(envelope, ensure_ascii=False))
        logger.info(f"[PUB] {channel} ← {message.get('from', 'unknown')}: {message.get('type', 'unknown')}")

    def subscribe(self, channels):
        """订阅频道"""
        ch_keys = [self.CHANNELS[c] for c in channels if c in self.CHANNELS]
        self.pubsub.subscribe(*ch_keys)
        logger.info(f"已订阅频道: {channels}")

    def listen(self):
        """监听消息（阻塞式）"""
        for message in self.pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                yield data

    # ===== 预定义消息类型 =====

    def scout_report(self, report_data):
        """Scout发布情报报告"""
        self.publish("intel", {
            "from": "Scout",
            "type": "morning_report",
            "priority": report_data.get("priority", "normal"),
            "data": report_data
        })

    def picker_signal(self, signal_data):
        """Picker发布选股信号"""
        self.publish("signals", {
            "from": "Picker",
            "type": "stock_signal",
            "data": signal_data
        })

    def guard_alert(self, alert_data):
        """Guard发布风控预警"""
        self.publish("risk", {
            "from": "Guard",
            "type": "risk_alert",
            "level": alert_data.get("level", "info"),
            "data": alert_data
        })

    def guard_veto(self, signal_id, reason):
        """Guard一票否决"""
        self.publish("risk", {
            "from": "Guard",
            "type": "veto",
            "signal_id": signal_id,
            "reason": reason
        })

    def chief_approve(self, signal_id, modifications=None):
        """Chief审批通过"""
        self.publish("orders", {
            "from": "Chief",
            "type": "approved",
            "signal_id": signal_id,
            "modifications": modifications
        })

    def chief_reject(self, signal_id, reason):
        """Chief驳回"""
        self.publish("orders", {
            "from": "Chief",
            "type": "rejected",
            "signal_id": signal_id,
            "reason": reason
        })

    def trader_report(self, trade_data):
        """Trader发布成交回报"""
        self.publish("trades", {
            "from": "Trader",
            "type": "trade_report",
            "data": trade_data
        })

    def emergency_broadcast(self, sender, message):
        """紧急广播（全体接收）"""
        self.publish("emergency", {
            "from": sender,
            "type": "emergency",
            "message": message
        })
        logger.warning(f"🚨 紧急广播 [{sender}]: {message}")

# === 使用示例 ===
if __name__ == "__main__":
    bus = AgentBus()

    # Scout 发布晨间情报
    bus.scout_report({
        "priority": "important",
        "market_sentiment": "偏多",
        "hot_sectors": ["半导体", "AI算力", "新能源车"],
        "north_flow_forecast": "+25亿",
        "risk_factors": ["美债收益率上行"]
    })

    # Picker 发布选股信号
    bus.picker_signal({
        "code": "600036",
        "name": "招商银行",
        "action": "buy",
        "signal_strength": "strong",
        "entry_price": 35.50,
        "strategies_agreed": ["momentum", "trend", "composite"]
    })

    # Guard 发布风控预警
    bus.guard_alert({
        "level": "warning",
        "type": "position_limit",
        "message": "平安银行仓位达18%，接近20%上限"
    })
