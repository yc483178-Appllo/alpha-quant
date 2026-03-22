"""
模拟盘数据模型模块
定义账户、持仓、订单、成交、资金流水等数据模型
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict
from enum import Enum
import json


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"           # 待成交
    PARTIAL = "partial"           # 部分成交
    FILLED = "filled"             # 全部成交
    CANCELLED = "cancelled"       # 已撤单
    REJECTED = "rejected"         # 已拒绝
    EXPIRED = "expired"           # 已过期


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"             # 市价单
    LIMIT = "limit"               # 限价单


class ActionType(Enum):
    """操作类型"""
    BUY = "buy"                   # 买入
    SELL = "sell"                 # 卖出


class FundFlowType(Enum):
    """资金流水类型"""
    INITIAL_CAPITAL = "initial_capital"   # 初始资金
    BUY_ORDER = "buy_order"               # 买入订单冻结
    SELL_ORDER = "sell_order"             # 卖出资金解冻
    COMMISSION = "commission"             # 佣金支出
    STAMP_TAX = "stamp_tax"               # 印花税
    TRANSFER_FEE = "transfer_fee"         # 过户费
    REALIZED_PNL = "realized_pnl"         # 已实现盈亏


@dataclass
class SimAccount:
    """模拟账户模型"""
    id: Optional[int] = None
    account_name: str = "模拟账户"
    initial_capital: float = 1000000.0      # 初始资金 100万
    available_cash: float = 1000000.0       # 可用现金
    total_value: float = 1000000.0          # 总资产
    total_profit: float = 0.0               # 累计盈亏
    total_return_pct: float = 0.0           # 累计收益率
    max_drawdown: float = 0.0               # 最大回撤
    sharpe_ratio: float = 0.0               # 夏普比率
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    status: str = "active"
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_name": self.account_name,
            "initial_capital": self.initial_capital,
            "available_cash": self.available_cash,
            "total_value": self.total_value,
            "total_profit": self.total_profit,
            "total_return_pct": self.total_return_pct,
            "max_drawdown": self.max_drawdown,
            "sharpe_ratio": self.sharpe_ratio,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SimAccount':
        """从字典创建"""
        if 'created_at' in data and data['created_at']:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'updated_at' in data and data['updated_at']:
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


@dataclass
class SimPosition:
    """模拟持仓模型"""
    id: Optional[int] = None
    account_id: int = 0
    stock_code: str = ""
    stock_name: str = ""
    quantity: int = 0
    avg_cost: float = 0.0                   # 平均成本
    current_price: float = 0.0              # 当前价格
    market_value: float = 0.0               # 市值
    unrealized_pnl: float = 0.0             # 浮动盈亏
    unrealized_pnl_pct: float = 0.0         # 浮动盈亏率
    sector: str = ""
    opened_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    def update_market_value(self, current_price: float):
        """更新市值和盈亏"""
        self.current_price = current_price
        self.market_value = self.quantity * current_price
        self.unrealized_pnl = self.market_value - (self.quantity * self.avg_cost)
        if self.avg_cost > 0:
            self.unrealized_pnl_pct = self.unrealized_pnl / (self.quantity * self.avg_cost)
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "stock_code": self.stock_code,
            "stock_name": self.stock_name,
            "quantity": self.quantity,
            "avg_cost": self.avg_cost,
            "current_price": self.current_price,
            "market_value": self.market_value,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "sector": self.sector,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SimPosition':
        """从字典创建"""
        if 'opened_at' in data and data['opened_at']:
            data['opened_at'] = datetime.fromisoformat(data['opened_at'])
        if 'updated_at' in data and data['updated_at']:
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


@dataclass
class SimOrder:
    """模拟订单模型"""
    id: Optional[int] = None
    account_id: int = 0
    order_id: str = ""
    stock_code: str = ""
    order_type: str = "limit"               # market, limit
    action: str = ""                        # buy, sell
    quantity: int = 0
    price: Optional[float] = None
    filled_quantity: int = 0
    filled_price: Optional[float] = None
    status: str = "pending"                 # pending, partial, filled, cancelled, rejected
    strategy: str = ""
    signal_id: Optional[int] = None
    commission: float = 0.0
    slippage: float = 0.0
    created_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    @property
    def remaining_quantity(self) -> int:
        """剩余未成交数量"""
        return self.quantity - self.filled_quantity
    
    @property
    def is_active(self) -> bool:
        """是否处于活动状态"""
        return self.status in ["pending", "partial"]
    
    def fill(self, fill_qty: int, fill_price: float):
        """成交处理"""
        self.filled_quantity += fill_qty
        if self.filled_quantity >= self.quantity:
            self.status = "filled"
            self.filled_at = datetime.now()
        else:
            self.status = "partial"
        self.filled_price = fill_price
        self.updated_at = datetime.now()
    
    def cancel(self):
        """撤单处理"""
        if self.is_active:
            self.status = "cancelled"
            self.updated_at = datetime.now()
    
    def reject(self, reason: str = ""):
        """拒绝处理"""
        self.status = "rejected"
        self.updated_at = datetime.now()
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "order_id": self.order_id,
            "stock_code": self.stock_code,
            "order_type": self.order_type,
            "action": self.action,
            "quantity": self.quantity,
            "price": self.price,
            "filled_quantity": self.filled_quantity,
            "filled_price": self.filled_price,
            "status": self.status,
            "strategy": self.strategy,
            "signal_id": self.signal_id,
            "commission": self.commission,
            "slippage": self.slippage,
            "remaining_quantity": self.remaining_quantity,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SimOrder':
        """从字典创建"""
        if 'created_at' in data and data['created_at']:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        if 'filled_at' in data and data['filled_at']:
            data['filled_at'] = datetime.fromisoformat(data['filled_at'])
        if 'updated_at' in data and data['updated_at']:
            data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        return cls(**data)


@dataclass
class SimTransaction:
    """模拟成交模型"""
    id: Optional[int] = None
    account_id: int = 0
    order_id: str = ""
    transaction_id: str = ""
    stock_code: str = ""
    action: str = ""
    quantity: int = 0
    price: float = 0.0
    amount: float = 0.0
    commission: float = 0.0
    stamp_tax: float = 0.0                  # 印花税（卖出时收取）
    transfer_fee: float = 0.0               # 过户费
    total_cost: float = 0.0                 # 总成本
    realized_pnl: Optional[float] = None    # 已实现盈亏（卖出时计算）
    transaction_time: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "order_id": self.order_id,
            "transaction_id": self.transaction_id,
            "stock_code": self.stock_code,
            "action": self.action,
            "quantity": self.quantity,
            "price": self.price,
            "amount": self.amount,
            "commission": self.commission,
            "stamp_tax": self.stamp_tax,
            "transfer_fee": self.transfer_fee,
            "total_cost": self.total_cost,
            "realized_pnl": self.realized_pnl,
            "transaction_time": self.transaction_time.isoformat() if self.transaction_time else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SimTransaction':
        """从字典创建"""
        if 'transaction_time' in data and data['transaction_time']:
            data['transaction_time'] = datetime.fromisoformat(data['transaction_time'])
        return cls(**data)


@dataclass
class SimFundFlow:
    """模拟资金流水模型"""
    id: Optional[int] = None
    account_id: int = 0
    flow_type: str = ""                     # 流水类型
    amount: float = 0.0                     # 金额（正为收入，负为支出）
    balance_after: float = 0.0              # 变动后余额
    reference_id: Optional[str] = None      # 关联订单/成交ID
    description: str = ""
    created_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "account_id": self.account_id,
            "flow_type": self.flow_type,
            "amount": self.amount,
            "balance_after": self.balance_after,
            "reference_id": self.reference_id,
            "description": self.description,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SimFundFlow':
        """从字典创建"""
        if 'created_at' in data and data['created_at']:
            data['created_at'] = datetime.fromisoformat(data['created_at'])
        return cls(**data)


@dataclass
class SimPerformance:
    """模拟盘业绩指标"""
    account_id: int = 0
    total_return: float = 0.0               # 总收益率
    annualized_return: float = 0.0          # 年化收益率
    max_drawdown: float = 0.0               # 最大回撤
    sharpe_ratio: float = 0.0               # 夏普比率
    sortino_ratio: float = 0.0              # 索提诺比率
    calmar_ratio: float = 0.0               # 卡玛比率
    win_rate: float = 0.0                   # 胜率
    profit_loss_ratio: float = 0.0          # 盈亏比
    total_trades: int = 0                   # 总交易次数
    profitable_trades: int = 0              # 盈利交易次数
    loss_trades: int = 0                    # 亏损交易次数
    avg_holding_days: float = 0.0           # 平均持仓天数
    total_commission: float = 0.0           # 总佣金
    total_tax: float = 0.0                  # 总税费
    beta: float = 0.0                       # Beta系数
    alpha: float = 0.0                      # Alpha系数
    volatility: float = 0.0                 # 波动率
    var_95: float = 0.0                     # 95% VaR
    var_99: float = 0.0                     # 99% VaR
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return asdict(self)


class SimulationPortfolio:
    """模拟组合状态（运行时聚合）"""
    
    def __init__(self, account_id: int):
        self.account_id = account_id
        self.positions: Dict[str, SimPosition] = {}  # stock_code -> position
        self.orders: Dict[str, SimOrder] = {}        # order_id -> order
        self.available_cash: float = 0.0
        self.total_value: float = 0.0
        self.positions_value: float = 0.0
        self.unrealized_pnl: float = 0.0
        self.equity_curve: List[Dict] = []
        
    def update_position(self, position: SimPosition):
        """更新持仓"""
        if position.quantity > 0:
            self.positions[position.stock_code] = position
        else:
            self.positions.pop(position.stock_code, None)
    
    def update_prices(self, prices: Dict[str, float]):
        """更新价格"""
        self.positions_value = 0.0
        self.unrealized_pnl = 0.0
        
        for code, position in self.positions.items():
            if code in prices:
                position.update_market_value(prices[code])
            self.positions_value += position.market_value
            self.unrealized_pnl += position.unrealized_pnl
        
        self.total_value = self.available_cash + self.positions_value
        
    def add_equity_point(self):
        """添加权益曲线点"""
        self.equity_curve.append({
            "timestamp": datetime.now().isoformat(),
            "total_value": self.total_value,
            "cash": self.available_cash,
            "positions_value": self.positions_value,
            "unrealized_pnl": self.unrealized_pnl
        })
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "account_id": self.account_id,
            "available_cash": self.available_cash,
            "positions_value": self.positions_value,
            "total_value": self.total_value,
            "unrealized_pnl": self.unrealized_pnl,
            "positions_count": len(self.positions),
            "positions": [p.to_dict() for p in self.positions.values()],
            "active_orders": [o.to_dict() for o in self.orders.values() if o.is_active],
            "equity_curve": self.equity_curve[-30:]  # 最近30个点
        }
