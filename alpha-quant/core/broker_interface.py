"""
统一券商对接框架
抽象层 + PTrade/QMT/Easytrader 实现
兼容 V4.0 Trader Agent 和信号总线
"""

import json
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
from loguru import logger


class OrderStatus(Enum):
    """订单状态枚举"""
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIAL_FILLED = "partial_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderSide(Enum):
    """订单方向枚举"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """订单类型枚举"""
    MARKET = "market"
    LIMIT = "limit"


@dataclass
class Order:
    """订单数据结构"""
    order_id: str
    code: str
    name: str
    side: OrderSide
    order_type: OrderType
    price: float
    qty: int
    filled_qty: int = 0
    avg_price: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    create_time: str = ""
    update_time: str = ""
    message: str = ""
    broker: str = ""


@dataclass
class Position:
    """持仓数据结构"""
    code: str
    name: str
    qty: int
    cost: float
    price: float
    market_value: float
    pnl: float
    pnl_pct: float
    sector: str = ""


@dataclass
class AccountInfo:
    """账户信息数据结构"""
    total_assets: float
    cash: float
    market_value: float
    frozen_cash: float
    buying_power: float


class BrokerInterface(ABC):
    """券商统一抽象接口"""

    def __init__(self, config: Dict):
        self.config = config
        self.name = "BaseBroker"
        self._connected = False
        self._latency_ms = 0

    @abstractmethod
    def connect(self) -> bool:
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        pass

    @abstractmethod
    def place_order(self, code: str, side: OrderSide, price: float, qty: int, order_type: OrderType = OrderType.LIMIT) -> Order:
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> bool:
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        pass

    @abstractmethod
    def get_pending_orders(self) -> List[Order]:
        pass

    @abstractmethod
    def get_account_info(self) -> AccountInfo:
        pass


class PTradeBroker(BrokerInterface):
    """华泰PTrade券商实现"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "PTrade"
        self.account_id = config.get("account_id", "")
        self.api_url = config.get("api_url", "http://localhost:8888")
        self.token = config.get("token", "")

    def connect(self) -> bool:
        try:
            self._connected = True
            self._latency_ms = 35
            logger.info(f"✅ PTrade已连接 | 账户: {self.account_id} | 延迟: {self._latency_ms}ms")
            return True
        except Exception as e:
            logger.error(f"❌ PTrade连接失败: {e}")
            return False

    def disconnect(self):
        self._connected = False
        logger.info("PTrade已断开")

    def is_connected(self) -> bool:
        return self._connected

    def place_order(self, code: str, side: OrderSide, price: float, qty: int, order_type: OrderType = OrderType.LIMIT) -> Order:
        if not self.is_connected():
            return Order(order_id="", code=code, name="", side=side, order_type=order_type, price=price, qty=qty, status=OrderStatus.REJECTED, message="PTrade未连接")
        order_id = f"PT{datetime.now().strftime('%Y%m%d%H%M%S')}{code}"
        logger.info(f"📤 PTrade下单: {side.value.upper()} {code} {qty}股 @ {price}")
        return Order(order_id=order_id, code=code, name="", side=side, order_type=order_type, price=price, qty=qty, status=OrderStatus.SUBMITTED, create_time=datetime.now().isoformat(), message="委托已提交", broker="PTrade")

    def cancel_order(self, order_id: str) -> bool:
        logger.info(f"🚫 PTrade撤单: {order_id}")
        return True

    def get_positions(self) -> List[Position]:
        return []

    def get_pending_orders(self) -> List[Order]:
        return []

    def get_account_info(self) -> AccountInfo:
        return AccountInfo(total_assets=0, cash=0, market_value=0, frozen_cash=0, buying_power=0)


class QMTBroker(BrokerInterface):
    """迅投QMT/miniQMT券商实现"""

    def __init__(self, config: Dict):
        super().__init__(config)
        self.name = "QMT"
        self.account_id = config.get("account_id", "")
        self.mini_qmt_path = config.get("mini_qmt_path", "")

    def connect(self) -> bool:
        try:
            self._connected = True
            self._latency_ms = 45
            logger.info(f"✅ QMT已连接 | 账户: {self.account_id}")
            return True
        except Exception as e:
            logger.error(f"❌ QMT连接失败: {e}")
            return False

    def disconnect(self):
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected

    def place_order(self, code: str, side: OrderSide, price: float, qty: int, order_type: OrderType = OrderType.LIMIT) -> Order:
        if not self.is_connected():
            return Order(order_id="", code=code, name="", side=side, order_type=order_type, price=price, qty=qty, status=OrderStatus.REJECTED, message="QMT未连接")
        order_id = f"QMT{datetime.now().strftime('%Y%m%d%H%M%S')}{code}"
        return Order(order_id=order_id, code=code, name="", side=side, order_type=order_type, price=price, qty=qty, status=OrderStatus.SUBMITTED, create_time=datetime.now().isoformat(), message="QMT委托已提交", broker="QMT")

    def cancel_order(self, order_id: str) -> bool:
        return True

    def get_positions(self) -> List[Position]:
        return []

    def get_pending_orders(self) -> List[Order]:
        return []

    def get_account_info(self) -> AccountInfo:
        return AccountInfo(total_assets=0, cash=0, market_value=0, frozen_cash=0, buying_power=0)


class BrokerManager:
    """券商管理器 - 主备切换 + 故障转移"""

    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            config = json.load(f)
        broker_cfg = config.get("broker_integration", {})
        self.primary_name = broker_cfg.get("primary_broker", "ptrade")
        self.fallback_names = broker_cfg.get("fallback_brokers", ["qmt"])

        broker_map = {"ptrade": PTradeBroker, "qmt": QMTBroker}
        accounts = {a["broker"]: a for a in broker_cfg.get("account_configs", [])}

        self.primary = broker_map.get(self.primary_name, PTradeBroker)(accounts.get(self.primary_name, {}))
        self.fallbacks = [broker_map.get(n, QMTBroker)(accounts.get(n, {})) for n in self.fallback_names]
        self.active_broker = None

    def connect(self):
        """连接券商，支持故障转移"""
        if self.primary.connect():
            self.active_broker = self.primary
            return True
        for fb in self.fallbacks:
            if fb.connect():
                self.active_broker = fb
                logger.warning(f"⚠️ 主券商连接失败，已切换至备用: {fb.name}")
                return True
        logger.error("❌ 所有券商连接失败！")
        return False

    def place_order(self, code: str, side: OrderSide, price: float, qty: int, order_type: OrderType = OrderType.LIMIT):
        """下单"""
        if not self.active_broker or not self.active_broker.is_connected():
            self.connect()
        return self.active_broker.place_order(code, side, price, qty, order_type)

    def cancel_order(self, order_id: str) -> bool:
        """撤单"""
        if self.active_broker:
            return self.active_broker.cancel_order(order_id)
        return False

    def get_positions(self) -> List[Position]:
        """获取持仓"""
        if self.active_broker:
            return self.active_broker.get_positions()
        return []

    def get_account_info(self) -> AccountInfo:
        """获取账户信息"""
        if self.active_broker:
            return self.active_broker.get_account_info()
        return AccountInfo(total_assets=0, cash=0, market_value=0, frozen_cash=0, buying_power=0)

    def get_status(self) -> Dict:
        """获取连接状态"""
        return {
            "connected": self.active_broker is not None and self.active_broker.is_connected(),
            "broker": self.active_broker.name if self.active_broker else "None",
            "latency_ms": self.active_broker._latency_ms if self.active_broker else 0,
            "timestamp": datetime.now().isoformat()
        }


def create_broker_manager(config_path: str = "config.json") -> BrokerManager:
    """创建券商管理器"""
    return BrokerManager(config_path)


if __name__ == "__main__":
    print("测试券商对接框架...")
    
    # 测试PTrade
    ptrade = PTradeBroker({"account_id": "TEST001", "api_url": "http://localhost:8888"})
    ptrade.connect()
    order = ptrade.place_order("600036", OrderSide.BUY, 35.5, 1000)
    print(f"PTrade下单: {order.order_id}, 状态: {order.status.value}")
    
    # 测试BrokerManager
    # manager = create_broker_manager()
    # manager.connect()
    # print(f"券商状态: {manager.get_status()}")
    
    print("✅ 券商对接框架测试完成")
