"""
订单管理系统 (OMS)
订单生命周期 | 重试逻辑 | 滑点追踪 | 审计日志
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from loguru import logger

from .broker_integration import BrokerManager, OrderSide, OrderStatus


@dataclass
class OrderRecord:
    """订单记录数据结构"""
    order_id: str
    code: str
    name: str
    side: str
    price: float
    qty: int
    filled_qty: int = 0
    avg_fill_price: float = 0.0
    status: str = "created"
    signal_source: str = "manual"
    submit_time: str = ""
    fill_time: str = ""
    cancel_time: str = ""
    attempts: int = 0
    slippage_bps: float = 0.0
    error_message: str = ""
    broker: str = ""
    metadata: Dict = field(default_factory=dict)


class OrderManagementSystem:
    """订单管理系统 (OMS)"""

    def __init__(self, broker_manager: BrokerManager, config_path: str = "config.json"):
        self.broker = broker_manager
        
        with open(config_path) as f:
            config = json.load(f)
        
        oms_cfg = config.get("broker_integration", {}).get("oms", {})
        self.max_retry = oms_cfg.get("max_retry_attempts", 3)
        self.retry_delay = oms_cfg.get("retry_delay_seconds", 5)
        self.order_timeout = oms_cfg.get("order_timeout_seconds", 300)
        
        self.orders: Dict[str, OrderRecord] = {}
        self.trade_log: List[Dict] = []
        
        logger.info(f"✅ OMS初始化完成 | max_retry={self.max_retry}")

    def submit_order(self, code: str, side: str, price: float, qty: int, signal_source: str = "manual", name: str = ""):
        """提交订单（含重试逻辑）"""
        order_side = OrderSide.BUY if side == "buy" else OrderSide.SELL
        
        for attempt in range(1, self.max_retry + 1):
            try:
                result = self.broker.place_order(code, order_side, price, qty)
                
                if result.status != OrderStatus.REJECTED:
                    order_record = OrderRecord(
                        order_id=result.order_id,
                        code=code,
                        name=name or code,
                        side=side,
                        price=price,
                        qty=qty,
                        status=result.status.value,
                        signal_source=signal_source,
                        submit_time=datetime.now().isoformat(),
                        attempts=attempt,
                        broker=result.broker
                    )
                    
                    self.orders[result.order_id] = order_record
                    self._log_trade("SUBMIT", order_record)
                    
                    return {"success": True, "order_id": result.order_id, "status": result.status.value}
                else:
                    logger.warning(f"订单被拒绝(第{attempt}次): {result.message}")
                    if attempt < self.max_retry:
                        time.sleep(self.retry_delay)
                    else:
                        return {"success": False, "order_id": None, "status": "rejected", "message": result.message}
                        
            except Exception as e:
                logger.error(f"下单异常(第{attempt}次): {e}")
                if attempt < self.max_retry:
                    time.sleep(self.retry_delay)
                else:
                    return {"success": False, "order_id": None, "status": "error", "message": str(e)}
        
        return {"success": False, "order_id": None, "status": "failed"}

    def cancel_order(self, order_id: str) -> bool:
        """撤销订单"""
        if order_id not in self.orders:
            return False
        
        order = self.orders[order_id]
        
        if order.status in ["filled", "cancelled", "rejected"]:
            return False
        
        try:
            success = self.broker.cancel_order(order_id)
            if success:
                order.status = "cancelled"
                order.cancel_time = datetime.now().isoformat()
                self._log_trade("CANCEL", order)
                return True
            return False
        except Exception as e:
            logger.error(f"撤单异常: {e}")
            return False

    def update_fill(self, order_id: str, filled_qty: int, fill_price: float):
        """更新成交信息并计算滑点"""
        if order_id not in self.orders:
            return
        
        order = self.orders[order_id]
        order.filled_qty = filled_qty
        order.avg_fill_price = fill_price
        order.fill_time = datetime.now().isoformat()
        
        # 计算滑点（基点）
        if order.price > 0:
            slippage = (fill_price - order.price) / order.price * 10000
            if order.side == "sell":
                slippage = -slippage
            order.slippage_bps = round(slippage, 2)
        
        if filled_qty >= order.qty:
            order.status = "filled"
        else:
            order.status = "partial_filled"
        
        self._log_trade("FILL", order)

    def _log_trade(self, action: str, order: OrderRecord):
        """审计日志"""
        log_entry = {
            "action": action,
            "order_id": order.order_id,
            "code": order.code,
            "side": order.side,
            "qty": order.qty,
            "price": order.price,
            "status": order.status,
            "timestamp": datetime.now().isoformat()
        }
        self.trade_log.append(log_entry)
        logger.info(f"[OMS] {action}: {order.code} {order.side} {order.qty}股 @ {order.price}")

    def get_order(self, order_id: str) -> Optional[OrderRecord]:
        """获取订单信息"""
        return self.orders.get(order_id)

    def get_pending_orders(self) -> List[OrderRecord]:
        """获取未成交订单"""
        return [o for o in self.orders.values() if o.status in ["submitted", "pending", "partial_filled"]]

    def get_daily_summary(self) -> Dict:
        """获取当日交易汇总"""
        today = datetime.now().strftime("%Y-%m-%d")
        today_orders = [o for o in self.orders.values() if o.submit_time.startswith(today)]
        
        filled_orders = [o for o in today_orders if o.status == "filled"]
        avg_slippage = sum(o.slippage_bps for o in filled_orders) / max(1, len(filled_orders))
        
        return {
            "date": today,
            "total_orders": len(today_orders),
            "filled": len(filled_orders),
            "cancelled": len([o for o in today_orders if o.status == "cancelled"]),
            "rejected": len([o for o in today_orders if o.status == "rejected"]),
            "avg_slippage_bps": round(avg_slippage, 2),
            "total_volume": sum(o.qty for o in filled_orders)
        }


def create_oms(broker_manager: BrokerManager, config_path: str = "config.json"):
    """创建OMS实例"""
    return OrderManagementSystem(broker_manager, config_path)
