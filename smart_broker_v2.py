#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alpha V6.0 - 智能券商管理器 V2 (Smart Broker Manager V2)
管理多个券商连接，智能切换，订单路由
"""

import json
import logging
import random
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    ERROR = "error"


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


@dataclass
class Order:
    """订单结构"""
    order_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: float
    price: Optional[float]
    stop_price: Optional[float]
    status: OrderStatus
    filled_quantity: float
    avg_fill_price: float
    commission: float
    broker_id: str
    created_at: str
    updated_at: str
    metadata: Dict[str, Any]


@dataclass
class BrokerStatus:
    """券商状态"""
    broker_id: str
    name: str
    enabled: bool
    connected: bool
    latency_ms: float
    error_rate: float
    last_check: str
    position_count: int
    available_cash: float
    total_equity: float
    daily_volume: float
    order_success_rate: float


class SmartBrokerManagerV2:
    """
    智能券商管理器 V2
    
    功能：
    1. 多券商管理
    2. 智能订单路由
    3. 故障自动切换
    4. 订单状态跟踪
    5. 执行质量分析
    """
    
    def __init__(self, config_path: str = "/opt/alpha-system/config/config.json"):
        self.config = self._load_config(config_path)
        self.broker_config = self.config.get("brokers", {})
        
        # 券商列表
        self.brokers: Dict[str, Any] = {}
        self.broker_status: Dict[str, BrokerStatus] = {}
        
        # 订单跟踪
        self.orders: Dict[str, Order] = {}
        self.order_history: List[Order] = []
        
        # 执行统计
        self.execution_stats = {
            "total_orders": 0,
            "filled_orders": 0,
            "cancelled_orders": 0,
            "rejected_orders": 0,
            "avg_fill_time_ms": 0,
            "avg_slippage": 0
        }
        
        # 锁
        self.order_lock = threading.Lock()
        
        self._init_brokers()
        logger.info("智能券商管理器 V2 初始化完成")
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"无法加载配置: {e}，使用默认配置")
            return {
                "brokers": {
                    "primary": "simulation",
                    "available": ["simulation"],
                    "auto_switch": {"enabled": True, "latency_threshold_ms": 500}
                }
            }
    
    def _init_brokers(self):
        """初始化券商连接"""
        available_brokers = self.broker_config.get("available", ["simulation"])
        
        for broker_id in available_brokers:
            self.brokers[broker_id] = {
                "id": broker_id,
                "config": self.broker_config.get(broker_id, {}),
                "connection": None,
                "enabled": True
            }
            
            # 初始化状态
            self.broker_status[broker_id] = BrokerStatus(
                broker_id=broker_id,
                name=broker_id.upper(),
                enabled=True,
                connected=broker_id == "simulation",  # 模拟券商始终连接
                latency_ms=random.uniform(10, 100),
                error_rate=0.0,
                last_check=datetime.now().isoformat(),
                position_count=random.randint(0, 20),
                available_cash=random.uniform(100000, 10000000),
                total_equity=random.uniform(500000, 50000000),
                daily_volume=random.uniform(1000000, 100000000),
                order_success_rate=random.uniform(0.95, 0.999)
            )
        
        logger.info(f"已初始化 {len(self.brokers)} 个券商")
    
    def _generate_order_id(self) -> str:
        """生成订单ID"""
        return f"ORD{datetime.now().strftime('%Y%m%d%H%M%S')}{random.randint(1000, 9999)}"
    
    def get_primary_broker(self) -> Optional[str]:
        """获取主券商"""
        primary = self.broker_config.get("primary", "simulation")
        if primary in self.brokers and self.broker_status[primary].enabled:
            return primary
        
        # 寻找备选
        for broker_id, status in self.broker_status.items():
            if status.enabled and status.connected:
                return broker_id
        
        return None
    
    def select_best_broker(self, symbol: str = None, order_size: float = None) -> Optional[str]:
        """
        智能选择最佳券商
        
        基于：
        - 延迟
        - 成功率
        - 成本
        - 当前负载
        """
        candidates = []
        
        for broker_id, status in self.broker_status.items():
            if not status.enabled or not status.connected:
                continue
            
            # 评分算法
            latency_score = max(0, 1 - status.latency_ms / 1000)
            success_score = status.order_success_rate
            load_score = max(0, 1 - status.daily_volume / 1000000000)
            
            total_score = latency_score * 0.4 + success_score * 0.4 + load_score * 0.2
            
            candidates.append((broker_id, total_score))
        
        if not candidates:
            return None
        
        # 选择得分最高的
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]
    
    def place_order(self, symbol: str, side: str, quantity: float,
                    order_type: str = "market", price: float = None,
                    stop_price: float = None, broker_id: str = None) -> Dict:
        """
        下单
        
        Args:
            symbol: 股票代码
            side: buy/sell
            quantity: 数量
            order_type: market/limit/stop/stop_limit
            price: 限价
            stop_price: 止损价
            broker_id: 指定券商（可选）
        """
        order_id = self._generate_order_id()
        
        # 选择券商
        if not broker_id:
            broker_id = self.select_best_broker(symbol, quantity)
        
        if not broker_id or broker_id not in self.brokers:
            return {"success": False, "error": "无可用的券商", "order_id": None}
        
        # 创建订单对象
        order = Order(
            order_id=order_id,
            symbol=symbol,
            side=OrderSide(side.lower()),
            order_type=OrderType(order_type.lower()),
            quantity=quantity,
            price=price,
            stop_price=stop_price,
            status=OrderStatus.PENDING,
            filled_quantity=0,
            avg_fill_price=0,
            commission=0,
            broker_id=broker_id,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            metadata={}
        )
        
        with self.order_lock:
            self.orders[order_id] = order
        
        # 模拟订单执行
        result = self._execute_order(order)
        
        return result
    
    def _execute_order(self, order: Order) -> Dict:
        """执行订单（模拟）"""
        # 模拟延迟
        time.sleep(random.uniform(0.01, 0.1))
        
        # 模拟成功率
        success_rate = self.broker_status[order.broker_id].order_success_rate
        
        if random.random() > success_rate:
            order.status = OrderStatus.REJECTED
            order.updated_at = datetime.now().isoformat()
            return {
                "success": False,
                "order_id": order.order_id,
                "error": "订单被拒绝"
            }
        
        # 模拟成交
        fill_ratio = random.uniform(0.8, 1.0)
        order.filled_quantity = order.quantity * fill_ratio
        order.avg_fill_price = order.price if order.price else random.uniform(10, 100)
        order.commission = order.filled_quantity * order.avg_fill_price * 0.00025
        order.status = OrderStatus.FILLED if fill_ratio >= 0.99 else OrderStatus.PARTIAL_FILLED
        order.updated_at = datetime.now().isoformat()
        
        # 更新统计
        self.execution_stats["total_orders"] += 1
        self.execution_stats["filled_orders"] += 1
        
        return {
            "success": True,
            "order_id": order.order_id,
            "filled_quantity": order.filled_quantity,
            "avg_fill_price": order.avg_fill_price,
            "commission": order.commission,
            "status": order.status.value
        }
    
    def cancel_order(self, order_id: str) -> Dict:
        """取消订单"""
        with self.order_lock:
            order = self.orders.get(order_id)
            if not order:
                return {"success": False, "error": "订单不存在"}
            
            if order.status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                return {"success": False, "error": f"订单状态为 {order.status.value}，无法取消"}
            
            order.status = OrderStatus.CANCELLED
            order.updated_at = datetime.now().isoformat()
            self.execution_stats["cancelled_orders"] += 1
        
        return {"success": True, "order_id": order_id}
    
    def get_order_status(self, order_id: str) -> Optional[Dict]:
        """获取订单状态"""
        order = self.orders.get(order_id)
        if not order:
            return None
        
        return {
            "order_id": order.order_id,
            "symbol": order.symbol,
            "side": order.side.value,
            "status": order.status.value,
            "quantity": order.quantity,
            "filled_quantity": order.filled_quantity,
            "avg_fill_price": order.avg_fill_price,
            "commission": order.commission,
            "broker_id": order.broker_id,
            "created_at": order.created_at,
            "updated_at": order.updated_at
        }
    
    def get_all_orders(self, status: str = None) -> List[Dict]:
        """获取所有订单"""
        orders = []
        for order in self.orders.values():
            if status and order.status.value != status:
                continue
            orders.append(self.get_order_status(order.order_id))
        return orders
    
    def switch_broker(self, new_broker_id: str) -> Dict:
        """
        切换主券商
        
        Args:
            new_broker_id: 新券商ID
        """
        if new_broker_id not in self.brokers:
            return {"success": False, "error": f"券商 {new_broker_id} 不存在"}
        
        if not self.broker_status[new_broker_id].enabled:
            return {"success": False, "error": f"券商 {new_broker_id} 未启用"}
        
        old_broker = self.broker_config.get("primary", "simulation")
        self.broker_config["primary"] = new_broker_id
        
        logger.info(f"主券商已切换: {old_broker} -> {new_broker_id}")
        
        return {
            "success": True,
            "previous_broker": old_broker,
            "current_broker": new_broker_id,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_broker_status(self, broker_id: str = None) -> Dict:
        """获取券商状态"""
        if broker_id:
            status = self.broker_status.get(broker_id)
            if status:
                return asdict(status)
            return {"error": "券商不存在"}
        
        return {
            broker_id: asdict(status)
            for broker_id, status in self.broker_status.items()
        }
    
    def get_all_brokers_status(self) -> List[Dict]:
        """获取所有券商状态列表"""
        return [asdict(status) for status in self.broker_status.values()]
    
    def update_broker_health(self):
        """更新券商健康状态"""
        for broker_id, status in self.broker_status.items():
            # 模拟健康检查
            status.latency_ms = random.uniform(10, 500)
            status.error_rate = random.uniform(0, 0.05)
            status.last_check = datetime.now().isoformat()
            status.order_success_rate = random.uniform(0.9, 0.999)
            
            # 自动切换逻辑
            auto_switch = self.broker_config.get("auto_switch", {})
            if auto_switch.get("enabled", False):
                latency_threshold = auto_switch.get("latency_threshold_ms", 500)
                error_threshold = auto_switch.get("error_rate_threshold", 0.05)
                
                if (status.latency_ms > latency_threshold or 
                    status.error_rate > error_threshold):
                    if broker_id == self.get_primary_broker():
                        # 切换到最佳券商
                        best = self.select_best_broker()
                        if best and best != broker_id:
                            self.switch_broker(best)
    
    def get_execution_log(self, limit: int = 100) -> List[Dict]:
        """获取执行日志"""
        logs = []
        for order in list(self.orders.values())[-limit:]:
            logs.append({
                "timestamp": order.updated_at,
                "order_id": order.order_id,
                "symbol": order.symbol,
                "action": order.side.value,
                "quantity": order.quantity,
                "price": order.avg_fill_price,
                "status": order.status.value,
                "broker": order.broker_id
            })
        return logs[::-1]  # 最新的在前
    
    def get_execution_stats(self) -> Dict:
        """获取执行统计"""
        return {
            **self.execution_stats,
            "active_orders": len([o for o in self.orders.values() 
                                  if o.status in [OrderStatus.PENDING, OrderStatus.SUBMITTED]]),
            "fill_rate": (self.execution_stats["filled_orders"] / 
                         max(1, self.execution_stats["total_orders"]))
        }


# 单例实例
_broker_manager = None

def get_broker_manager() -> SmartBrokerManagerV2:
    """获取券商管理器单例"""
    global _broker_manager
    if _broker_manager is None:
        _broker_manager = SmartBrokerManagerV2()
    return _broker_manager


if __name__ == "__main__":
    # 测试
    manager = SmartBrokerManagerV2()
    
    # 获取券商状态
    print("券商状态:")
    print(json.dumps(manager.get_all_brokers_status(), indent=2, ensure_ascii=False))
    
    # 测试下单
    result = manager.place_order("000001.XSHE", "buy", 1000, "market")
    print(f"\n下单结果: {result}")
    
    # 获取执行统计
    print(f"\n执行统计: {manager.get_execution_stats()}")
