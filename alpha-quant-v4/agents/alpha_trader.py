#!/usr/bin/env python3
"""
Alpha-Trader: 交易执行员
负责精准执行每一笔交易
"""

import os
import json
import time
from datetime import datetime
from loguru import logger
from core.agent_bus import AgentBus
from core.nl_order_parser import NLOrderParser

class AlphaTrader:
    """交易执行员 - 团队的'手臂'"""
    
    def __init__(self):
        self.bus = AgentBus()
        self.nl_parser = NLOrderParser()
        self.trade_history = []
        
    def execute_order(self, order):
        """执行交易指令"""
        signal_id = order.get("signal_id")
        code = order.get("code")
        action = order.get("action")
        
        logger.info(f"[Trader] 接收执行指令: {code} {action}")
        
        # 执行前检查清单
        if not self._pre_trade_checklist(order):
            logger.error(f"[Trader] 执行前检查失败: {signal_id}")
            return None
        
        # 模拟执行（实际应调用PTrade/QMT API）
        trade_result = self._simulate_execution(order)
        
        # 发送成交回报
        self.bus.trader_report(trade_result)
        
        # 记录交易
        self.trade_history.append(trade_result)
        
        logger.info(f"[Trader] 交易执行完成: {code} {action} @ {trade_result['deal_price']}")
        return trade_result
    
    def _pre_trade_checklist(self, order):
        """执行前必检清单"""
        checks = {
            "chief_approved": order.get("chief_approved", False),
            "guard_cleared": order.get("guard_cleared", True),
            "is_trading_day": self._is_trading_day(),
            "in_trading_hours": self._in_trading_hours(),
            "sufficient_funds": True,  # 应从账户检查
            "valid_stock": not self._is_st_stock(order.get("code")),
        }
        
        failed = [k for k, v in checks.items() if not v]
        if failed:
            logger.error(f"[Trader] 检查失败项: {failed}")
            return False
        
        return True
    
    def _is_trading_day(self):
        """检查是否为交易日"""
        # 简化版
        return True
    
    def _in_trading_hours(self):
        """检查是否在交易时段"""
        now = datetime.now()
        hour, minute = now.hour, now.minute
        
        # 上午 9:30-11:30
        morning = (9, 30) <= (hour, minute) <= (11, 30)
        # 下午 13:00-15:00
        afternoon = (13, 0) <= (hour, minute) <= (15, 0)
        
        return morning or afternoon
    
    def _is_st_stock(self, code):
        """检查是否为ST股"""
        # 简化版
        return False
    
    def _simulate_execution(self, order):
        """模拟交易执行"""
        code = order.get("code")
        action = order.get("action")
        entry_price = order.get("entry_price", 0)
        
        # 模拟滑点 0.05%
        slippage = 0.0005
        if action == "buy":
            deal_price = entry_price * (1 + slippage)
        else:
            deal_price = entry_price * (1 - slippage)
        
        # 模拟股数（简化版固定金额5万）
        amount = 50000 / deal_price if deal_price > 0 else 0
        amount = int(amount / 100) * 100  # 整手
        
        total_cost = deal_price * amount
        commission = max(total_cost * 0.0003, 5)  # 佣金最低5元
        
        return {
            "trade_id": f"TRADER-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "signal_id": order.get("signal_id"),
            "code": code,
            "name": order.get("name", ""),
            "action": action,
            "order_price": entry_price,
            "deal_price": round(deal_price, 2),
            "slippage": f"{slippage*100:.2f}%",
            "amount": amount,
            "total_cost": round(total_cost, 2),
            "commission": round(commission, 2),
            "status": "filled",
            "timestamp": datetime.now().isoformat()
        }
    
    def parse_natural_language(self, text):
        """解析自然语言交易指令 - 使用NLParser"""
        parsed = self.nl_parser.parse(text)
        
        if "error" in parsed:
            logger.error(f"[Trader] 指令解析失败: {parsed['error']}")
            return {"parsed": False, "error": parsed["error"], "original": text}
        
        # 转换为内部订单格式
        order = {
            "signal_id": f"NL-{datetime.now().strftime('%Y%m%d%H%M%S')}",
            "code": parsed["code"],
            "name": parsed["name"],
            "action": parsed["action"],
            "entry_price": parsed.get("limit_price", parsed.get("current_price", 0)),
            "amount": parsed.get("amount"),
            "original_text": parsed["original_text"],
            "chief_approved": False,  # 需要Chief审批
            "guard_cleared": True
        }
        
        logger.info(f"[Trader] 自然语言指令解析成功: {text} -> {order['action']} {order['name']}")
        return {"parsed": True, "order": order}
    
    def execute_nl_order(self, text, auto_approve=False):
        """直接执行自然语言指令"""
        result = self.parse_natural_language(text)
        
        if not result.get("parsed"):
            return result
        
        order = result["order"]
        
        if auto_approve:
            order["chief_approved"] = True
            return self.execute_order(order)
        else:
            # 发送给Chief审批
            self.bus.publish("signals", {
                "from": "Trader",
                "type": "nl_order_request",
                "data": order
            })
            logger.info(f"[Trader] 自然语言指令已发送给Chief审批: {order['name']}")
            return {"status": "pending_approval", "order": order}

if __name__ == "__main__":
    trader = AlphaTrader()
    # 测试执行
    test_order = {
        "signal_id": "TEST-001",
        "code": "600036",
        "name": "招商银行",
        "action": "buy",
        "entry_price": 35.50,
        "chief_approved": True,
        "guard_cleared": True
    }
    result = trader.execute_order(test_order)
    print(json.dumps(result, indent=2, ensure_ascii=False))
