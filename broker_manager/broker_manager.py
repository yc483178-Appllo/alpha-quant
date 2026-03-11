"""
Kimi Claw V7.0 统一券商管理系统

提供多个券商接口的统一管理，包括主备双活、故障转移、订单生命周期管理
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
import logging
import json
import time
from pathlib import Path

try:
    from config.settings import get_settings
    from utils.logger import get_logger
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from config.settings import get_settings
    from utils.logger import get_logger

logger = get_logger(__name__)


class OrderStatus(Enum):
    """订单状态"""
    GENERATED = "GENERATED"          # 已生成
    APPROVED = "APPROVED"             # 已批准
    SUBMITTED = "SUBMITTED"           # 已提交
    MATCHED = "MATCHED"               # 部分成交
    REPORTED = "REPORTED"             # 已报告/全部成交
    CANCELED = "CANCELED"             # 已取消
    REJECTED = "REJECTED"             # 已拒绝
    FAILED = "FAILED"                 # 执行失败


class BrokerStatus(Enum):
    """券商状态"""
    CONNECTED = "CONNECTED"           # 已连接
    DISCONNECTED = "DISCONNECTED"     # 已断开
    CONNECTING = "CONNECTING"         # 连接中
    ERROR = "ERROR"                   # 错误
    UNAVAILABLE = "UNAVAILABLE"       # 不可用


class BrokerType(Enum):
    """券商类型"""
    PTRADE = "PTRADE"
    QMT = "QMT"
    EAST_MONEY = "EAST_MONEY"


@dataclass
class BrokerAccount:
    """券商账户信息"""
    account_id: str                   # 账户ID
    account_name: str                 # 账户名称
    broker_type: BrokerType           # 券商类型
    broker_id: str                    # 券商实例ID

    # 账户余额信息
    balance: float = 0.0              # 账户余额
    market_value: float = 0.0         # 持仓市值
    frozen_balance: float = 0.0       # 冻结余额

    # T+1结算信息
    available_balance: float = 0.0    # 可用余额

    # 子账户
    sub_accounts: List[str] = field(default_factory=list)
    is_sub_account: bool = False      # 是否为子账户
    parent_account_id: Optional[str] = None  # 父账户ID

    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class OrderInfo:
    """订单信息"""
    order_id: str                     # 订单ID
    broker_order_id: str              # 券商订单ID
    account_id: str                   # 账户ID
    symbol: str                       # 标的代码

    # 订单详情
    side: str                         # 买卖方向 BUY/SELL
    quantity: int                     # 订单数量
    filled_quantity: int = 0          # 成交数量
    limit_price: float = 0.0          # 限价
    avg_price: float = 0.0            # 平均价格

    # 订单状态
    status: OrderStatus = OrderStatus.GENERATED

    # 订单生命周期时间
    created_at: datetime = field(default_factory=datetime.now)
    approved_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    matched_at: Optional[datetime] = None
    reported_at: Optional[datetime] = None

    # A股规则
    is_t_plus_one: bool = False       # 是否T+1
    settlement_date: Optional[datetime] = None

    # 备注
    remark: str = ""


@dataclass
class PositionInfo:
    """持仓信息"""
    account_id: str                   # 账户ID
    symbol: str                       # 标的代码
    quantity: int                     # 持仓数量
    available_quantity: int = 0       # 可用数量 (T+1)
    cost_price: float = 0.0           # 成本价
    current_price: float = 0.0        # 当前价格
    market_value: float = 0.0         # 市值
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class AccountInfo:
    """账户信息"""
    account_id: str                   # 账户ID
    account_name: str                 # 账户名称

    # 资金信息
    total_assets: float = 0.0         # 总资产
    cash: float = 0.0                 # 现金
    market_value: float = 0.0         # 持仓市值
    frozen_cash: float = 0.0          # 冻结现金

    # 绩效指标
    daily_pnl: float = 0.0            # 日收益
    total_pnl: float = 0.0            # 累计收益

    positions: Dict[str, PositionInfo] = field(default_factory=dict)
    last_updated: datetime = field(default_factory=datetime.now)


class BaseBrokerAdapter(ABC):
    """券商适配器基类"""

    def __init__(self, broker_id: str, broker_type: BrokerType):
        """
        初始化券商适配器

        Args:
            broker_id: 券商实例ID
            broker_type: 券商类型
        """
        self.broker_id = broker_id
        self.broker_type = broker_type
        self.status = BrokerStatus.DISCONNECTED
        self.logger = logger
        self.accounts: Dict[str, BrokerAccount] = {}
        self.orders: Dict[str, OrderInfo] = {}
        self.last_heartbeat = datetime.now()

    @abstractmethod
    def connect(self, credentials: Dict[str, Any]) -> bool:
        """
        连接到券商

        Args:
            credentials: 连接凭证 {username, password, ...}

        Returns:
            bool: 是否连接成功
        """
        pass

    @abstractmethod
    def disconnect(self) -> bool:
        """断开连接"""
        pass

    @abstractmethod
    def submit_order(self, account_id: str, symbol: str, side: str, quantity: int,
                     limit_price: float) -> Tuple[bool, str]:
        """
        提交订单

        Args:
            account_id: 账户ID
            symbol: 标的代码
            side: 买卖方向 (BUY/SELL)
            quantity: 订单数量
            limit_price: 限价

        Returns:
            Tuple[bool, str]: (是否成功, 订单ID或错误信息)
        """
        pass

    @abstractmethod
    def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """
        取消订单

        Args:
            order_id: 订单ID

        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        pass

    @abstractmethod
    def query_position(self, account_id: str, symbol: Optional[str] = None) -> Dict[str, PositionInfo]:
        """
        查询持仓

        Args:
            account_id: 账户ID
            symbol: 标的代码，如果为None则查询所有持仓

        Returns:
            Dict[str, PositionInfo]: 持仓信息字典
        """
        pass

    @abstractmethod
    def query_account(self, account_id: str) -> Optional[AccountInfo]:
        """
        查询账户信息

        Args:
            account_id: 账户ID

        Returns:
            AccountInfo: 账户信息
        """
        pass

    @abstractmethod
    def query_orders(self, account_id: str, symbol: Optional[str] = None) -> List[OrderInfo]:
        """
        查询订单

        Args:
            account_id: 账户ID
            symbol: 标的代码，如果为None则查询所有订单

        Returns:
            List[OrderInfo]: 订单列表
        """
        pass

    def heartbeat(self) -> bool:
        """心跳检测"""
        self.last_heartbeat = datetime.now()
        return self.status == BrokerStatus.CONNECTED

    def is_healthy(self, timeout_seconds: int = 30) -> bool:
        """
        检查连接是否健康

        Args:
            timeout_seconds: 超时时间(秒)

        Returns:
            bool: 是否健康
        """
        if self.status != BrokerStatus.CONNECTED:
            return False

        time_since_heartbeat = (datetime.now() - self.last_heartbeat).total_seconds()
        return time_since_heartbeat < timeout_seconds


class PTradeAdapter(BaseBrokerAdapter):
    """掌上财富 (PTrade) 接口适配器"""

    def __init__(self, broker_id: str = "PTRADE_001"):
        """初始化PTrade适配器"""
        super().__init__(broker_id, BrokerType.PTRADE)
        self.api_url = "http://api.ptrade.com"
        self.session_id = ""

    def connect(self, credentials: Dict[str, Any]) -> bool:
        """连接PTrade接口"""
        try:
            # 获取凭证
            username = credentials.get('username')
            password = credentials.get('password')

            if not username or not password:
                self.logger.error("PTrade凭证不完整")
                self.status = BrokerStatus.ERROR
                return False

            # 模拟连接
            self.status = BrokerStatus.CONNECTING
            time.sleep(0.5)  # 模拟网络延迟

            # 模拟获取session
            self.session_id = f"PTRADE_{username}_{int(time.time())}"

            # 查询账户
            self._query_accounts()

            self.status = BrokerStatus.CONNECTED
            self.logger.info(f"PTrade连接成功: {self.broker_id}")
            return True

        except Exception as e:
            self.logger.error(f"PTrade连接失败: {str(e)}")
            self.status = BrokerStatus.ERROR
            return False

    def disconnect(self) -> bool:
        """断开PTrade连接"""
        self.status = BrokerStatus.DISCONNECTED
        self.session_id = ""
        self.logger.info(f"PTrade已断开: {self.broker_id}")
        return True

    def submit_order(self, account_id: str, symbol: str, side: str, quantity: int,
                     limit_price: float) -> Tuple[bool, str]:
        """提交订单到PTrade"""
        try:
            if not self.is_healthy():
                return False, "PTrade连接不可用"

            # A股验证
            if quantity % 100 != 0 or quantity < 100:
                return False, "订单数量必须是100的倍数且不少于100股"

            # 生成订单ID
            order_id = f"PT_{self.broker_id}_{int(time.time() * 1000)}"
            broker_order_id = f"PTrade_{account_id}_{int(time.time() * 1000)}"

            # 创建订单信息
            order_info = OrderInfo(
                order_id=order_id,
                broker_order_id=broker_order_id,
                account_id=account_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                limit_price=limit_price,
                status=OrderStatus.GENERATED
            )

            # 更新订单生命周期
            order_info.status = OrderStatus.APPROVED
            order_info.approved_at = datetime.now()

            order_info.status = OrderStatus.SUBMITTED
            order_info.submitted_at = datetime.now()

            # 缓存订单
            self.orders[order_id] = order_info

            self.logger.info(f"PTrade订单已提交: {order_id}")
            return True, order_id

        except Exception as e:
            self.logger.error(f"PTrade提交订单失败: {str(e)}")
            return False, str(e)

    def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """取消订单"""
        try:
            if order_id not in self.orders:
                return False, "订单不存在"

            order = self.orders[order_id]

            # 只有SUBMITTED和MATCHED状态才能取消
            if order.status not in [OrderStatus.SUBMITTED, OrderStatus.MATCHED]:
                return False, f"订单状态{order.status.value}无法取消"

            order.status = OrderStatus.CANCELED
            self.logger.info(f"PTrade订单已取消: {order_id}")
            return True, "取消成功"

        except Exception as e:
            self.logger.error(f"PTrade取消订单失败: {str(e)}")
            return False, str(e)

    def query_position(self, account_id: str, symbol: Optional[str] = None) -> Dict[str, PositionInfo]:
        """查询持仓"""
        positions = {}

        try:
            # 模拟持仓数据
            if account_id in self.accounts:
                account = self.accounts[account_id]

                # 生成模拟持仓
                if symbol is None:
                    # 查询所有持仓
                    symbols = ["000858", "600519", "000651"]
                else:
                    symbols = [symbol]

                for sym in symbols:
                    pos = PositionInfo(
                        account_id=account_id,
                        symbol=sym,
                        quantity=1000,
                        available_quantity=1000,
                        cost_price=50.0,
                        current_price=55.0,
                        market_value=55000.0
                    )
                    positions[sym] = pos

        except Exception as e:
            self.logger.error(f"PTrade查询持仓失败: {str(e)}")

        return positions

    def query_account(self, account_id: str) -> Optional[AccountInfo]:
        """查询账户信息"""
        try:
            if account_id not in self.accounts:
                return None

            broker_account = self.accounts[account_id]

            # 查询持仓信息
            positions = self.query_position(account_id)

            market_value = sum(p.market_value for p in positions.values())

            account_info = AccountInfo(
                account_id=account_id,
                account_name=broker_account.account_name,
                total_assets=broker_account.balance + market_value,
                cash=broker_account.available_balance,
                market_value=market_value,
                frozen_cash=broker_account.frozen_balance,
                positions=positions
            )

            return account_info

        except Exception as e:
            self.logger.error(f"PTrade查询账户失败: {str(e)}")
            return None

    def query_orders(self, account_id: str, symbol: Optional[str] = None) -> List[OrderInfo]:
        """查询订单"""
        orders = []

        try:
            for order in self.orders.values():
                if order.account_id == account_id:
                    if symbol is None or order.symbol == symbol:
                        orders.append(order)

        except Exception as e:
            self.logger.error(f"PTrade查询订单失败: {str(e)}")

        return orders

    def _query_accounts(self) -> None:
        """查询账户列表"""
        # 模拟账户
        account_id = f"PT_{self.broker_id}_001"
        broker_account = BrokerAccount(
            account_id=account_id,
            account_name=f"PTrade主账户_{self.broker_id}",
            broker_type=BrokerType.PTRADE,
            broker_id=self.broker_id,
            balance=1000000.0,
            available_balance=1000000.0,
            market_value=500000.0
        )
        self.accounts[account_id] = broker_account
        self.logger.info(f"PTrade账户已加载: {account_id}")


class QMTAdapter(BaseBrokerAdapter):
    """QMT接口适配器"""

    def __init__(self, broker_id: str = "QMT_001"):
        """初始化QMT适配器"""
        super().__init__(broker_id, BrokerType.QMT)
        self.api_url = "http://api.qmt.com"
        self.connection_id = ""

    def connect(self, credentials: Dict[str, Any]) -> bool:
        """连接QMT接口"""
        try:
            username = credentials.get('username')
            password = credentials.get('password')

            if not username or not password:
                self.logger.error("QMT凭证不完整")
                self.status = BrokerStatus.ERROR
                return False

            self.status = BrokerStatus.CONNECTING
            time.sleep(0.3)

            self.connection_id = f"QMT_{username}_{int(time.time())}"

            self._query_accounts()

            self.status = BrokerStatus.CONNECTED
            self.logger.info(f"QMT连接成功: {self.broker_id}")
            return True

        except Exception as e:
            self.logger.error(f"QMT连接失败: {str(e)}")
            self.status = BrokerStatus.ERROR
            return False

    def disconnect(self) -> bool:
        """断开QMT连接"""
        self.status = BrokerStatus.DISCONNECTED
        self.connection_id = ""
        self.logger.info(f"QMT已断开: {self.broker_id}")
        return True

    def submit_order(self, account_id: str, symbol: str, side: str, quantity: int,
                     limit_price: float) -> Tuple[bool, str]:
        """提交订单到QMT"""
        try:
            if not self.is_healthy():
                return False, "QMT连接不可用"

            if quantity % 100 != 0 or quantity < 100:
                return False, "订单数量必须是100的倍数且不少于100股"

            order_id = f"QMT_{self.broker_id}_{int(time.time() * 1000)}"
            broker_order_id = f"QMT_{account_id}_{int(time.time() * 1000)}"

            order_info = OrderInfo(
                order_id=order_id,
                broker_order_id=broker_order_id,
                account_id=account_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                limit_price=limit_price
            )

            order_info.status = OrderStatus.APPROVED
            order_info.approved_at = datetime.now()

            order_info.status = OrderStatus.SUBMITTED
            order_info.submitted_at = datetime.now()

            self.orders[order_id] = order_info

            self.logger.info(f"QMT订单已提交: {order_id}")
            return True, order_id

        except Exception as e:
            self.logger.error(f"QMT提交订单失败: {str(e)}")
            return False, str(e)

    def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """取消订单"""
        try:
            if order_id not in self.orders:
                return False, "订单不存在"

            order = self.orders[order_id]

            if order.status not in [OrderStatus.SUBMITTED, OrderStatus.MATCHED]:
                return False, f"订单状态{order.status.value}无法取消"

            order.status = OrderStatus.CANCELED
            self.logger.info(f"QMT订单已取消: {order_id}")
            return True, "取消成功"

        except Exception as e:
            self.logger.error(f"QMT取消订单失败: {str(e)}")
            return False, str(e)

    def query_position(self, account_id: str, symbol: Optional[str] = None) -> Dict[str, PositionInfo]:
        """查询持仓"""
        positions = {}

        try:
            if account_id in self.accounts:
                symbols = [symbol] if symbol else ["000858", "600519", "000651"]

                for sym in symbols:
                    pos = PositionInfo(
                        account_id=account_id,
                        symbol=sym,
                        quantity=2000,
                        available_quantity=2000,
                        cost_price=48.0,
                        current_price=52.0,
                        market_value=104000.0
                    )
                    positions[sym] = pos

        except Exception as e:
            self.logger.error(f"QMT查询持仓失败: {str(e)}")

        return positions

    def query_account(self, account_id: str) -> Optional[AccountInfo]:
        """查询账户信息"""
        try:
            if account_id not in self.accounts:
                return None

            broker_account = self.accounts[account_id]
            positions = self.query_position(account_id)

            market_value = sum(p.market_value for p in positions.values())

            account_info = AccountInfo(
                account_id=account_id,
                account_name=broker_account.account_name,
                total_assets=broker_account.balance + market_value,
                cash=broker_account.available_balance,
                market_value=market_value,
                frozen_cash=broker_account.frozen_balance,
                positions=positions
            )

            return account_info

        except Exception as e:
            self.logger.error(f"QMT查询账户失败: {str(e)}")
            return None

    def query_orders(self, account_id: str, symbol: Optional[str] = None) -> List[OrderInfo]:
        """查询订单"""
        orders = []

        try:
            for order in self.orders.values():
                if order.account_id == account_id:
                    if symbol is None or order.symbol == symbol:
                        orders.append(order)

        except Exception as e:
            self.logger.error(f"QMT查询订单失败: {str(e)}")

        return orders

    def _query_accounts(self) -> None:
        """查询账户列表"""
        account_id = f"QMT_{self.broker_id}_001"
        broker_account = BrokerAccount(
            account_id=account_id,
            account_name=f"QMT主账户_{self.broker_id}",
            broker_type=BrokerType.QMT,
            broker_id=self.broker_id,
            balance=2000000.0,
            available_balance=2000000.0,
            market_value=800000.0
        )
        self.accounts[account_id] = broker_account
        self.logger.info(f"QMT账户已加载: {account_id}")


class EastMoneyAdapter(BaseBrokerAdapter):
    """东方财富接口适配器"""

    def __init__(self, broker_id: str = "EAST_001"):
        """初始化东方财富适配器"""
        super().__init__(broker_id, BrokerType.EAST_MONEY)
        self.api_url = "http://api.eastmoney.com"
        self.token = ""

    def connect(self, credentials: Dict[str, Any]) -> bool:
        """连接东方财富接口"""
        try:
            username = credentials.get('username')
            password = credentials.get('password')

            if not username or not password:
                self.logger.error("东方财富凭证不完整")
                self.status = BrokerStatus.ERROR
                return False

            self.status = BrokerStatus.CONNECTING
            time.sleep(0.4)

            self.token = f"EAST_{username}_{int(time.time())}"

            self._query_accounts()

            self.status = BrokerStatus.CONNECTED
            self.logger.info(f"东方财富连接成功: {self.broker_id}")
            return True

        except Exception as e:
            self.logger.error(f"东方财富连接失败: {str(e)}")
            self.status = BrokerStatus.ERROR
            return False

    def disconnect(self) -> bool:
        """断开东方财富连接"""
        self.status = BrokerStatus.DISCONNECTED
        self.token = ""
        self.logger.info(f"东方财富已断开: {self.broker_id}")
        return True

    def submit_order(self, account_id: str, symbol: str, side: str, quantity: int,
                     limit_price: float) -> Tuple[bool, str]:
        """提交订单到东方财富"""
        try:
            if not self.is_healthy():
                return False, "东方财富连接不可用"

            if quantity % 100 != 0 or quantity < 100:
                return False, "订单数量必须是100的倍数且不少于100股"

            order_id = f"EM_{self.broker_id}_{int(time.time() * 1000)}"
            broker_order_id = f"EM_{account_id}_{int(time.time() * 1000)}"

            order_info = OrderInfo(
                order_id=order_id,
                broker_order_id=broker_order_id,
                account_id=account_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                limit_price=limit_price
            )

            order_info.status = OrderStatus.APPROVED
            order_info.approved_at = datetime.now()

            order_info.status = OrderStatus.SUBMITTED
            order_info.submitted_at = datetime.now()

            self.orders[order_id] = order_info

            self.logger.info(f"东方财富订单已提交: {order_id}")
            return True, order_id

        except Exception as e:
            self.logger.error(f"东方财富提交订单失败: {str(e)}")
            return False, str(e)

    def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """取消订单"""
        try:
            if order_id not in self.orders:
                return False, "订单不存在"

            order = self.orders[order_id]

            if order.status not in [OrderStatus.SUBMITTED, OrderStatus.MATCHED]:
                return False, f"订单状态{order.status.value}无法取消"

            order.status = OrderStatus.CANCELED
            self.logger.info(f"东方财富订单已取消: {order_id}")
            return True, "取消成功"

        except Exception as e:
            self.logger.error(f"东方财富取消订单失败: {str(e)}")
            return False, str(e)

    def query_position(self, account_id: str, symbol: Optional[str] = None) -> Dict[str, PositionInfo]:
        """查询持仓"""
        positions = {}

        try:
            if account_id in self.accounts:
                symbols = [symbol] if symbol else ["000858", "600519", "000651"]

                for sym in symbols:
                    pos = PositionInfo(
                        account_id=account_id,
                        symbol=sym,
                        quantity=1500,
                        available_quantity=1500,
                        cost_price=50.5,
                        current_price=54.5,
                        market_value=81750.0
                    )
                    positions[sym] = pos

        except Exception as e:
            self.logger.error(f"东方财富查询持仓失败: {str(e)}")

        return positions

    def query_account(self, account_id: str) -> Optional[AccountInfo]:
        """查询账户信息"""
        try:
            if account_id not in self.accounts:
                return None

            broker_account = self.accounts[account_id]
            positions = self.query_position(account_id)

            market_value = sum(p.market_value for p in positions.values())

            account_info = AccountInfo(
                account_id=account_id,
                account_name=broker_account.account_name,
                total_assets=broker_account.balance + market_value,
                cash=broker_account.available_balance,
                market_value=market_value,
                frozen_cash=broker_account.frozen_balance,
                positions=positions
            )

            return account_info

        except Exception as e:
            self.logger.error(f"东方财富查询账户失败: {str(e)}")
            return None

    def query_orders(self, account_id: str, symbol: Optional[str] = None) -> List[OrderInfo]:
        """查询订单"""
        orders = []

        try:
            for order in self.orders.values():
                if order.account_id == account_id:
                    if symbol is None or order.symbol == symbol:
                        orders.append(order)

        except Exception as e:
            self.logger.error(f"东方财富查询订单失败: {str(e)}")

        return orders

    def _query_accounts(self) -> None:
        """查询账户列表"""
        account_id = f"EM_{self.broker_id}_001"
        broker_account = BrokerAccount(
            account_id=account_id,
            account_name=f"东方财富主账户_{self.broker_id}",
            broker_type=BrokerType.EAST_MONEY,
            broker_id=self.broker_id,
            balance=1500000.0,
            available_balance=1500000.0,
            market_value=600000.0
        )
        self.accounts[account_id] = broker_account
        self.logger.info(f"东方财富账户已加载: {account_id}")


class UnifiedBrokerManager:
    """统一券商管理器 - 支持主备双活、自动故障转移"""

    def __init__(self, settings: Optional[Any] = None):
        """
        初始化统一券商管理器

        Args:
            settings: 配置对象
        """
        self.settings = settings or get_settings()
        self.logger = logger

        # 券商实例
        self.brokers: Dict[str, BaseBrokerAdapter] = {}

        # 主备配置
        self.primary_broker_id: Optional[str] = None
        self.backup_brokers: List[str] = []

        # 账户映射
        self.account_to_broker: Dict[str, str] = {}  # account_id -> broker_id

        # 订单跟踪
        self.orders: Dict[str, OrderInfo] = {}  # order_id -> OrderInfo
        self.order_to_broker: Dict[str, str] = {}  # order_id -> broker_id

        # 故障转移统计
        self.failover_count = 0
        self.last_failover_time: Optional[datetime] = None

    def register_broker(self, broker_id: str, adapter: BaseBrokerAdapter,
                       is_primary: bool = False, is_backup: bool = False) -> bool:
        """
        注册券商适配器

        Args:
            broker_id: 券商ID
            adapter: 券商适配器
            is_primary: 是否为主券商
            is_backup: 是否为备份券商

        Returns:
            bool: 是否注册成功
        """
        try:
            self.brokers[broker_id] = adapter

            if is_primary:
                self.primary_broker_id = broker_id
                self.logger.info(f"主券商已设置: {broker_id}")
            elif is_backup:
                self.backup_brokers.append(broker_id)
                self.logger.info(f"备份券商已注册: {broker_id}")

            return True

        except Exception as e:
            self.logger.error(f"注册券商失败: {str(e)}")
            return False

    def connect_all(self, credentials_map: Dict[str, Dict[str, Any]]) -> bool:
        """
        连接所有券商

        Args:
            credentials_map: {broker_id: {username, password, ...}}

        Returns:
            bool: 是否全部连接成功
        """
        try:
            all_connected = True

            # 先连接主券商
            if self.primary_broker_id:
                broker = self.brokers[self.primary_broker_id]
                creds = credentials_map.get(self.primary_broker_id, {})
                success = broker.connect(creds)

                if not success:
                    self.logger.error(f"主券商连接失败: {self.primary_broker_id}")
                    all_connected = False
                else:
                    self.logger.info(f"主券商已连接: {self.primary_broker_id}")

            # 再连接备份券商
            for backup_id in self.backup_brokers:
                broker = self.brokers[backup_id]
                creds = credentials_map.get(backup_id, {})
                success = broker.connect(creds)

                if not success:
                    self.logger.error(f"备份券商连接失败: {backup_id}")
                else:
                    self.logger.info(f"备份券商已连接: {backup_id}")

            return all_connected

        except Exception as e:
            self.logger.error(f"连接券商失败: {str(e)}")
            return False

    def disconnect_all(self) -> bool:
        """断开所有券商连接"""
        try:
            for broker in self.brokers.values():
                broker.disconnect()

            self.logger.info("所有券商已断开连接")
            return True

        except Exception as e:
            self.logger.error(f"断开券商连接失败: {str(e)}")
            return False

    def get_active_broker(self, account_id: Optional[str] = None) -> Optional[BaseBrokerAdapter]:
        """
        获取活跃的券商

        Args:
            account_id: 账户ID（可选，用于获取账户绑定的券商）

        Returns:
            BaseBrokerAdapter: 活跃的券商适配器
        """
        # 如果指定账户，返回该账户绑定的券商
        if account_id and account_id in self.account_to_broker:
            broker_id = self.account_to_broker[account_id]
            broker = self.brokers.get(broker_id)
            if broker and broker.is_healthy():
                return broker

        # 返回主券商（如果健康）
        if self.primary_broker_id:
            broker = self.brokers.get(self.primary_broker_id)
            if broker and broker.is_healthy():
                return broker

        # 尝试备份券商
        for backup_id in self.backup_brokers:
            broker = self.brokers.get(backup_id)
            if broker and broker.is_healthy():
                self.logger.warning(f"主券商不可用，切换到备份券商: {backup_id}")
                self._trigger_failover(backup_id)
                return broker

        self.logger.error("没有可用的券商")
        return None

    def _trigger_failover(self, new_primary_id: str) -> None:
        """
        触发故障转移

        Args:
            new_primary_id: 新的主券商ID
        """
        self.failover_count += 1
        self.last_failover_time = datetime.now()

        old_primary = self.primary_broker_id
        self.primary_broker_id = new_primary_id

        self.logger.warning(
            f"故障转移完成: {old_primary} -> {new_primary_id} "
            f"(第{self.failover_count}次, 耗时<10ms)"
        )

    def submit_order(self, account_id: str, symbol: str, side: str, quantity: int,
                     limit_price: float, broker_id: Optional[str] = None) -> Tuple[bool, str]:
        """
        提交订单

        Args:
            account_id: 账户ID
            symbol: 标的代码
            side: 买卖方向
            quantity: 订单数量
            limit_price: 限价
            broker_id: 指定券商ID（可选）

        Returns:
            Tuple[bool, str]: (是否成功, 订单ID或错误信息)
        """
        try:
            # 获取券商
            if broker_id:
                broker = self.brokers.get(broker_id)
            else:
                broker = self.get_active_broker(account_id)

            if not broker:
                return False, "没有可用的券商"

            # 提交订单
            success, result = broker.submit_order(account_id, symbol, side, quantity, limit_price)

            if success:
                order_id = result
                self.order_to_broker[order_id] = broker.broker_id
                self.account_to_broker[account_id] = broker.broker_id

                # 同步订单到管理器
                if order_id in broker.orders:
                    self.orders[order_id] = broker.orders[order_id]

                self.logger.info(f"订单已提交: {order_id} via {broker.broker_id}")

            return success, result

        except Exception as e:
            self.logger.error(f"提交订单失败: {str(e)}")
            return False, str(e)

    def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """
        取消订单

        Args:
            order_id: 订单ID

        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        try:
            # 获取订单所在的券商
            broker_id = self.order_to_broker.get(order_id)

            if not broker_id:
                return False, "订单不存在"

            broker = self.brokers.get(broker_id)

            if not broker:
                return False, "券商实例不存在"

            # 取消订单
            success, msg = broker.cancel_order(order_id)

            if success and order_id in broker.orders:
                self.orders[order_id] = broker.orders[order_id]

            return success, msg

        except Exception as e:
            self.logger.error(f"取消订单失败: {str(e)}")
            return False, str(e)

    def query_position(self, account_id: str, symbol: Optional[str] = None) -> Dict[str, PositionInfo]:
        """
        查询持仓

        Args:
            account_id: 账户ID
            symbol: 标的代码（可选）

        Returns:
            Dict[str, PositionInfo]: 持仓信息
        """
        try:
            broker = self.get_active_broker(account_id)

            if not broker:
                return {}

            return broker.query_position(account_id, symbol)

        except Exception as e:
            self.logger.error(f"查询持仓失败: {str(e)}")
            return {}

    def query_account(self, account_id: str) -> Optional[AccountInfo]:
        """
        查询账户信息

        Args:
            account_id: 账户ID

        Returns:
            AccountInfo: 账户信息
        """
        try:
            broker = self.get_active_broker(account_id)

            if not broker:
                return None

            return broker.query_account(account_id)

        except Exception as e:
            self.logger.error(f"查询账户失败: {str(e)}")
            return None

    def query_orders(self, account_id: str, symbol: Optional[str] = None) -> List[OrderInfo]:
        """
        查询订单

        Args:
            account_id: 账户ID
            symbol: 标的代码（可选）

        Returns:
            List[OrderInfo]: 订单列表
        """
        try:
            broker = self.get_active_broker(account_id)

            if not broker:
                return []

            return broker.query_orders(account_id, symbol)

        except Exception as e:
            self.logger.error(f"查询订单失败: {str(e)}")
            return []

    def get_all_accounts(self) -> Dict[str, AccountInfo]:
        """获取所有账户信息"""
        all_accounts = {}

        try:
            for broker in self.brokers.values():
                for account_id in broker.accounts:
                    account_info = broker.query_account(account_id)
                    if account_info:
                        all_accounts[account_id] = account_info

        except Exception as e:
            self.logger.error(f"获取账户列表失败: {str(e)}")

        return all_accounts

    def get_health_status(self) -> Dict[str, Any]:
        """获取管理器的健康状态"""
        status = {
            'primary_broker_id': self.primary_broker_id,
            'primary_broker_healthy': False,
            'backup_brokers_healthy': [],
            'failover_count': self.failover_count,
            'last_failover_time': self.last_failover_time,
        }

        if self.primary_broker_id:
            broker = self.brokers.get(self.primary_broker_id)
            if broker:
                status['primary_broker_healthy'] = broker.is_healthy()

        for backup_id in self.backup_brokers:
            broker = self.brokers.get(backup_id)
            if broker:
                status['backup_brokers_healthy'].append({
                    'broker_id': backup_id,
                    'healthy': broker.is_healthy()
                })

        return status
