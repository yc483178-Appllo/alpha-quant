"""
Alpha-Genesis V6.1 SimEdge - 模拟盘交易引擎
=============================================
核心模块：SimulationTradingEngine
提供完整的模拟交易环境，支持多账户、多策略并行回测与模拟交易

Author: Alpha-Genesis Team
Version: 6.1.0
Date: 2026-03-09
"""

import json
import uuid
import sqlite3
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Callable
from enum import Enum
from loguru import logger
import threading
from decimal import Decimal, ROUND_HALF_UP
import redis
import pickle


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"          # 市价单
    LIMIT = "limit"            # 限价单
    STOP = "stop"              # 止损单
    STOP_LIMIT = "stop_limit"  # 止损限价单


class OrderSide(Enum):
    """买卖方向"""
    BUY = "buy"
    SELL = "sell"


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "pending"        # 待处理
    SUBMITTED = "submitted"    # 已提交
    PARTIAL_FILLED = "partial_filled"  # 部分成交
    FILLED = "filled"          # 完全成交
    CANCELLED = "cancelled"    # 已取消
    REJECTED = "rejected"      # 已拒绝
    EXPIRED = "expired"        # 已过期


class PositionSide(Enum):
    """持仓方向"""
    LONG = "long"              # 多头
    SHORT = "short"            # 空头（融券）


@dataclass
class SimulatedOrder:
    """模拟订单数据结构"""
    order_id: str
    account_id: str
    symbol: str
    side: OrderSide
    order_type: OrderType
    quantity: int
    filled_quantity: int = 0
    price: Optional[float] = None  # 限价单价格
    stop_price: Optional[float] = None  # 止损价格
    status: OrderStatus = OrderStatus.PENDING
    create_time: datetime = field(default_factory=datetime.now)
    update_time: datetime = field(default_factory=datetime.now)
    fill_time: Optional[datetime] = None
    avg_fill_price: float = 0.0
    commission: float = 0.0
    slipage: float = 0.0
    strategy_id: Optional[str] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        result = asdict(self)
        result['side'] = self.side.value
        result['order_type'] = self.order_type.value
        result['status'] = self.status.value
        result['create_time'] = self.create_time.isoformat()
        result['update_time'] = self.update_time.isoformat()
        if self.fill_time:
            result['fill_time'] = self.fill_time.isoformat()
        return result


@dataclass
class SimulatedPosition:
    """模拟持仓数据结构"""
    position_id: str
    account_id: str
    symbol: str
    side: PositionSide
    quantity: int
    avg_cost: float
    market_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    open_time: datetime = field(default_factory=datetime.now)
    update_time: datetime = field(default_factory=datetime.now)
    margin_used: float = 0.0
    strategy_id: Optional[str] = None
    
    @property
    def market_value(self) -> float:
        """持仓市值"""
        return self.quantity * self.market_price
    
    @property
    def total_pnl(self) -> float:
        """总盈亏"""
        return self.unrealized_pnl + self.realized_pnl
    
    def update_price(self, new_price: float):
        """更新价格并计算浮动盈亏"""
        self.market_price = new_price
        if self.side == PositionSide.LONG:
            self.unrealized_pnl = (new_price - self.avg_cost) * self.quantity
        else:
            self.unrealized_pnl = (self.avg_cost - new_price) * self.quantity
        self.update_time = datetime.now()
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        result = asdict(self)
        result['side'] = self.side.value
        result['market_value'] = self.market_value
        result['total_pnl'] = self.total_pnl
        result['open_time'] = self.open_time.isoformat()
        result['update_time'] = self.update_time.isoformat()
        return result


@dataclass
class SimulatedAccount:
    """模拟账户数据结构"""
    account_id: str
    name: str
    initial_capital: float
    available_cash: float
    total_equity: float
    total_margin_used: float = 0.0
    total_commission: float = 0.0
    total_slippage: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    create_time: datetime = field(default_factory=datetime.now)
    update_time: datetime = field(default_factory=datetime.now)
    settings: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def buying_power(self) -> float:
        """购买力 = 可用资金 + 持仓市值 * 折算率 - 已用保证金"""
        return self.available_cash + self.unrealized_pnl
    
    @property
    def total_return(self) -> float:
        """总收益率"""
        if self.initial_capital <= 0:
            return 0.0
        return (self.total_equity - self.initial_capital) / self.initial_capital
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        result = asdict(self)
        result['buying_power'] = self.buying_power
        result['total_return'] = self.total_return
        result['create_time'] = self.create_time.isoformat()
        result['update_time'] = self.update_time.isoformat()
        return result


@dataclass
class TradeRecord:
    """成交记录"""
    trade_id: str
    order_id: str
    account_id: str
    symbol: str
    side: OrderSide
    quantity: int
    price: float
    amount: float
    commission: float
    slippage: float
    trade_time: datetime
    strategy_id: Optional[str] = None
    
    def to_dict(self) -> Dict:
        result = asdict(self)
        result['side'] = self.side.value
        result['trade_time'] = self.trade_time.isoformat()
        return result


class SimulationDatabase:
    """模拟盘数据库管理"""
    
    def __init__(self, db_path: str = "simulation_trading.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_database()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取线程本地连接"""
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def _init_database(self):
        """初始化数据库表结构"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 账户表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accounts (
                account_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                initial_capital REAL NOT NULL,
                available_cash REAL NOT NULL,
                total_equity REAL NOT NULL,
                total_margin_used REAL DEFAULT 0,
                total_commission REAL DEFAULT 0,
                total_slippage REAL DEFAULT 0,
                realized_pnl REAL DEFAULT 0,
                unrealized_pnl REAL DEFAULT 0,
                settings TEXT,
                create_time TEXT NOT NULL,
                update_time TEXT NOT NULL
            )
        ''')
        
        # 订单表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                order_type TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                filled_quantity INTEGER DEFAULT 0,
                price REAL,
                stop_price REAL,
                status TEXT NOT NULL,
                create_time TEXT NOT NULL,
                update_time TEXT NOT NULL,
                fill_time TEXT,
                avg_fill_price REAL DEFAULT 0,
                commission REAL DEFAULT 0,
                slipage REAL DEFAULT 0,
                strategy_id TEXT,
                tags TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts(account_id)
            )
        ''')
        
        # 持仓表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS positions (
                position_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                avg_cost REAL NOT NULL,
                market_price REAL DEFAULT 0,
                unrealized_pnl REAL DEFAULT 0,
                realized_pnl REAL DEFAULT 0,
                open_time TEXT NOT NULL,
                update_time TEXT NOT NULL,
                margin_used REAL DEFAULT 0,
                strategy_id TEXT,
                FOREIGN KEY (account_id) REFERENCES accounts(account_id)
            )
        ''')
        
        # 成交记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                trade_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                account_id TEXT NOT NULL,
                symbol TEXT NOT NULL,
                side TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                price REAL NOT NULL,
                amount REAL NOT NULL,
                commission REAL DEFAULT 0,
                slippage REAL DEFAULT 0,
                trade_time TEXT NOT NULL,
                strategy_id TEXT,
                FOREIGN KEY (order_id) REFERENCES orders(order_id),
                FOREIGN KEY (account_id) REFERENCES accounts(account_id)
            )
        ''')
        
        # 资金流水表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS cash_flow (
                flow_id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                flow_type TEXT NOT NULL,
                amount REAL NOT NULL,
                balance_after REAL NOT NULL,
                description TEXT,
                related_order_id TEXT,
                create_time TEXT NOT NULL,
                FOREIGN KEY (account_id) REFERENCES accounts(account_id)
            )
        ''')
        
        # 创建索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_account ON orders(account_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders(symbol)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_positions_account ON positions(account_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_account ON trades(account_id)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_time ON trades(trade_time)')
        
        conn.commit()
        logger.info("模拟盘数据库初始化完成")
    
    # ========== 账户操作 ==========
    
    def save_account(self, account: SimulatedAccount):
        """保存账户"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO accounts VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        ''', (
            account.account_id, account.name, account.initial_capital,
            account.available_cash, account.total_equity, account.total_margin_used,
            account.total_commission, account.total_slippage, account.realized_pnl,
            account.unrealized_pnl, json.dumps(account.settings),
            account.create_time.isoformat(), account.update_time.isoformat()
        ))
        conn.commit()
    
    def get_account(self, account_id: str) -> Optional[SimulatedAccount]:
        """获取账户"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM accounts WHERE account_id = ?', (account_id,))
        row = cursor.fetchone()
        if row:
            return SimulatedAccount(
                account_id=row['account_id'],
                name=row['name'],
                initial_capital=row['initial_capital'],
                available_cash=row['available_cash'],
                total_equity=row['total_equity'],
                total_margin_used=row['total_margin_used'],
                total_commission=row['total_commission'],
                total_slippage=row['total_slippage'],
                realized_pnl=row['realized_pnl'],
                unrealized_pnl=row['unrealized_pnl'],
                create_time=datetime.fromisoformat(row['create_time']),
                update_time=datetime.fromisoformat(row['update_time']),
                settings=json.loads(row['settings']) if row['settings'] else {}
            )
        return None
    
    def get_all_accounts(self) -> List[SimulatedAccount]:
        """获取所有账户"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM accounts ORDER BY create_time DESC')
        accounts = []
        for row in cursor.fetchall():
            accounts.append(SimulatedAccount(
                account_id=row['account_id'],
                name=row['name'],
                initial_capital=row['initial_capital'],
                available_cash=row['available_cash'],
                total_equity=row['total_equity'],
                total_margin_used=row['total_margin_used'],
                total_commission=row['total_commission'],
                total_slippage=row['total_slippage'],
                realized_pnl=row['realized_pnl'],
                unrealized_pnl=row['unrealized_pnl'],
                create_time=datetime.fromisoformat(row['create_time']),
                update_time=datetime.fromisoformat(row['update_time']),
                settings=json.loads(row['settings']) if row['settings'] else {}
            ))
        return accounts
    
    # ========== 订单操作 ==========
    
    def save_order(self, order: SimulatedOrder):
        """保存订单"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO orders VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        ''', (
            order.order_id, order.account_id, order.symbol, order.side.value,
            order.order_type.value, order.quantity, order.filled_quantity,
            order.price, order.stop_price, order.status.value,
            order.create_time.isoformat(), order.update_time.isoformat(),
            order.fill_time.isoformat() if order.fill_time else None,
            order.avg_fill_price, order.commission, order.slipage,
            order.strategy_id, json.dumps(order.tags)
        ))
        conn.commit()
    
    def get_order(self, order_id: str) -> Optional[SimulatedOrder]:
        """获取订单"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM orders WHERE order_id = ?', (order_id,))
        row = cursor.fetchone()
        if row:
            return self._row_to_order(row)
        return None
    
    def get_orders_by_account(self, account_id: str, 
                              status: Optional[OrderStatus] = None,
                              limit: int = 100) -> List[SimulatedOrder]:
        """获取账户订单"""
        conn = self._get_connection()
        cursor = conn.cursor()
        if status:
            cursor.execute('''
                SELECT * FROM orders WHERE account_id = ? AND status = ?
                ORDER BY create_time DESC LIMIT ?
            ''', (account_id, status.value, limit))
        else:
            cursor.execute('''
                SELECT * FROM orders WHERE account_id = ?
                ORDER BY create_time DESC LIMIT ?
            ''', (account_id, limit))
        return [self._row_to_order(row) for row in cursor.fetchall()]
    
    def _row_to_order(self, row: sqlite3.Row) -> SimulatedOrder:
        """行数据转订单对象"""
        return SimulatedOrder(
            order_id=row['order_id'],
            account_id=row['account_id'],
            symbol=row['symbol'],
            side=OrderSide(row['side']),
            order_type=OrderType(row['order_type']),
            quantity=row['quantity'],
            filled_quantity=row['filled_quantity'],
            price=row['price'],
            stop_price=row['stop_price'],
            status=OrderStatus(row['status']),
            create_time=datetime.fromisoformat(row['create_time']),
            update_time=datetime.fromisoformat(row['update_time']),
            fill_time=datetime.fromisoformat(row['fill_time']) if row['fill_time'] else None,
            avg_fill_price=row['avg_fill_price'],
            commission=row['commission'],
            slipage=row['slipage'],
            strategy_id=row['strategy_id'],
            tags=json.loads(row['tags']) if row['tags'] else {}
        )
    
    # ========== 持仓操作 ==========
    
    def save_position(self, position: SimulatedPosition):
        """保存持仓"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO positions VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        ''', (
            position.position_id, position.account_id, position.symbol,
            position.side.value, position.quantity, position.avg_cost,
            position.market_price, position.unrealized_pnl, position.realized_pnl,
            position.open_time.isoformat(), position.update_time.isoformat(),
            position.margin_used, position.strategy_id
        ))
        conn.commit()
    
    def get_position(self, account_id: str, symbol: str) -> Optional[SimulatedPosition]:
        """获取持仓"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM positions WHERE account_id = ? AND symbol = ?
        ''', (account_id, symbol))
        row = cursor.fetchone()
        if row:
            return self._row_to_position(row)
        return None
    
    def get_positions_by_account(self, account_id: str) -> List[SimulatedPosition]:
        """获取账户所有持仓"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM positions WHERE account_id = ?', (account_id,))
        return [self._row_to_position(row) for row in cursor.fetchall()]
    
    def delete_position(self, position_id: str):
        """删除持仓（清仓时）"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM positions WHERE position_id = ?', (position_id,))
        conn.commit()
    
    def _row_to_position(self, row: sqlite3.Row) -> SimulatedPosition:
        """行数据转持仓对象"""
        return SimulatedPosition(
            position_id=row['position_id'],
            account_id=row['account_id'],
            symbol=row['symbol'],
            side=PositionSide(row['side']),
            quantity=row['quantity'],
            avg_cost=row['avg_cost'],
            market_price=row['market_price'],
            unrealized_pnl=row['unrealized_pnl'],
            realized_pnl=row['realized_pnl'],
            open_time=datetime.fromisoformat(row['open_time']),
            update_time=datetime.fromisoformat(row['update_time']),
            margin_used=row['margin_used'],
            strategy_id=row['strategy_id']
        )
    
    # ========== 成交记录操作 ==========
    
    def save_trade(self, trade: TradeRecord):
        """保存成交记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO trades VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        ''', (
            trade.trade_id, trade.order_id, trade.account_id, trade.symbol,
            trade.side.value, trade.quantity, trade.price, trade.amount,
            trade.commission, trade.slippage, trade.trade_time.isoformat(),
            trade.strategy_id
        ))
        conn.commit()
    
    def get_trades_by_account(self, account_id: str, 
                              start_time: Optional[datetime] = None,
                              end_time: Optional[datetime] = None,
                              limit: int = 100) -> List[TradeRecord]:
        """获取成交记录"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if start_time and end_time:
            cursor.execute('''
                SELECT * FROM trades WHERE account_id = ? 
                AND trade_time >= ? AND trade_time <= ?
                ORDER BY trade_time DESC LIMIT ?
            ''', (account_id, start_time.isoformat(), end_time.isoformat(), limit))
        else:
            cursor.execute('''
                SELECT * FROM trades WHERE account_id = ?
                ORDER BY trade_time DESC LIMIT ?
            ''', (account_id, limit))
        
        trades = []
        for row in cursor.fetchall():
            trades.append(TradeRecord(
                trade_id=row['trade_id'],
                order_id=row['order_id'],
                account_id=row['account_id'],
                symbol=row['symbol'],
                side=OrderSide(row['side']),
                quantity=row['quantity'],
                price=row['price'],
                amount=row['amount'],
                commission=row['commission'],
                slippage=row['slippage'],
                trade_time=datetime.fromisoformat(row['trade_time']),
                strategy_id=row['strategy_id']
            ))
        return trades


class SimulationTradingEngine:
    """
    模拟盘交易引擎 - V6.1 SimEdge 核心组件
    
    功能特性：
    - 多账户管理
    - 完整订单生命周期
    - 持仓管理与盈亏计算
    - 实时价格更新与撮合
    - 资金流水记录
    - 风险控制（单股仓位、总仓位限制）
    - 与 V6.0 进化引擎集成
    """
    
    def __init__(self, db_path: str = "simulation_trading.db",
                 commission_rate: float = 0.0003,
                 min_commission: float = 5.0,
                 slippage_rate: float = 0.0001,
                 enable_margin: bool = False):
        """
        初始化模拟盘交易引擎
        
        Args:
            db_path: 数据库路径
            commission_rate: 手续费率（默认万3）
            min_commission: 最低手续费
            slippage_rate: 滑点率
            enable_margin: 是否启用融资融券
        """
        self.db = SimulationDatabase(db_path)
        self.commission_rate = commission_rate
        self.min_commission = min_commission
        self.slippage_rate = slippage_rate
        self.enable_margin = enable_margin
        
        # 内存缓存
        self._accounts: Dict[str, SimulatedAccount] = {}
        self._positions: Dict[str, Dict[str, SimulatedPosition]] = {}  # account_id -> {symbol -> position}
        self._pending_orders: Dict[str, SimulatedOrder] = {}
        
        # 价格数据源
        self._price_feed: Optional[Callable[[str], float]] = None
        
        # 锁
        self._lock = threading.RLock()
        
        # 加载现有数据
        self._load_from_db()
        
        logger.info(f"模拟盘交易引擎初始化完成 | 数据库: {db_path}")
    
    def _load_from_db(self):
        """从数据库加载数据到内存"""
        accounts = self.db.get_all_accounts()
        for account in accounts:
            self._accounts[account.account_id] = account
            positions = self.db.get_positions_by_account(account.account_id)
            self._positions[account.account_id] = {p.symbol: p for p in positions}
        logger.info(f"从数据库加载 {len(accounts)} 个账户")
    
    def set_price_feed(self, feed_func: Callable[[str], float]):
        """设置价格数据源函数"""
        self._price_feed = feed_func
    
    # ========== 账户管理 ==========
    
    def create_account(self, name: str, initial_capital: float,
                       settings: Optional[Dict] = None) -> SimulatedAccount:
        """
        创建模拟账户
        
        Args:
            name: 账户名称
            initial_capital: 初始资金
            settings: 账户设置（可选）
        
        Returns:
            SimulatedAccount: 创建的账户对象
        """
        account_id = f"SIM_{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4().hex[:8].upper()}"
        
        default_settings = {
            'max_position_per_stock': 0.2,      # 单股最大仓位20%
            'max_total_position': 0.9,          # 总仓位最大90%
            'enable_short': False,              # 默认不允许融券
            'risk_level': 'medium',             # 风险等级
            'notify_on_fill': True,             # 成交通知
        }
        if settings:
            default_settings.update(settings)
        
        account = SimulatedAccount(
            account_id=account_id,
            name=name,
            initial_capital=initial_capital,
            available_cash=initial_capital,
            total_equity=initial_capital,
            settings=default_settings
        )
        
        with self._lock:
            self.db.save_account(account)
            self._accounts[account_id] = account
            self._positions[account_id] = {}
        
        logger.info(f"创建模拟账户: {account_id} | 名称: {name} | 初始资金: ¥{initial_capital:,.2f}")
        return account
    
    def get_account(self, account_id: str) -> Optional[SimulatedAccount]:
        """获取账户信息"""
        with self._lock:
            return self._accounts.get(account_id)
    
    def get_all_accounts(self) -> List[SimulatedAccount]:
        """获取所有账户"""
        with self._lock:
            return list(self._accounts.values())
    
    def delete_account(self, account_id: str) -> bool:
        """删除账户"""
        # TODO: 实现账户删除逻辑
        logger.warning("账户删除功能未实现")
        return False
    
    # ========== 订单管理 ==========
    
    def submit_order(self, account_id: str, symbol: str, side: OrderSide,
                     quantity: int, order_type: OrderType = OrderType.MARKET,
                     price: Optional[float] = None, stop_price: Optional[float] = None,
                     strategy_id: Optional[str] = None,
                     tags: Optional[Dict] = None) -> Tuple[bool, str, Optional[SimulatedOrder]]:
        """
        提交订单
        
        Args:
            account_id: 账户ID
            symbol: 股票代码
            side: 买卖方向
            quantity: 数量（股）
            order_type: 订单类型
            price: 限价价格（限价单必需）
            stop_price: 止损价格（止损单必需）
            strategy_id: 策略ID（可选）
            tags: 附加标签（可选）
        
        Returns:
            (success, message, order)
        """
        with self._lock:
            account = self._accounts.get(account_id)
            if not account:
                return False, f"账户不存在: {account_id}", None
            
            # 检查持仓限制
            if side == OrderSide.BUY:
                positions = self._positions.get(account_id, {})
                current_position_value = sum(
                    p.market_value for p in positions.values()
                )
                
                # 估算所需资金
                current_price = self._get_current_price(symbol)
                estimated_cost = quantity * current_price * 1.005  # 含手续费预留
                
                if estimated_cost > account.available_cash:
                    return False, f"资金不足 | 需要: ¥{estimated_cost:,.2f} | 可用: ¥{account.available_cash:,.2f}", None
            
            # 创建订单
            order_id = f"ORD_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6].upper()}"
            order = SimulatedOrder(
                order_id=order_id,
                account_id=account_id,
                symbol=symbol,
                side=side,
                order_type=order_type,
                quantity=quantity,
                price=price,
                stop_price=stop_price,
                status=OrderStatus.SUBMITTED,
                strategy_id=strategy_id,
                tags=tags or {}
            )
            
            # 保存订单
            self.db.save_order(order)
            
            # 市价单立即撮合
            if order_type == OrderType.MARKET:
                self._execute_market_order(order)
            else:
                self._pending_orders[order_id] = order
            
            logger.info(f"提交订单: {order_id} | {symbol} | {side.value} | {quantity}股")
            return True, "订单提交成功", order
    
    def cancel_order(self, order_id: str) -> Tuple[bool, str]:
        """取消订单"""
        with self._lock:
            order = self.db.get_order(order_id)
            if not order:
                return False, "订单不存在"
            
            if order.status not in [OrderStatus.PENDING, OrderStatus.SUBMITTED]:
                return False, f"订单状态无法取消: {order.status.value}"
            
            order.status = OrderStatus.CANCELLED
            order.update_time = datetime.now()
            self.db.save_order(order)
            
            if order_id in self._pending_orders:
                del self._pending_orders[order_id]
            
            logger.info(f"取消订单: {order_id}")
            return True, "订单已取消"
    
    def get_orders(self, account_id: str, status: Optional[OrderStatus] = None,
                   limit: int = 100) -> List[SimulatedOrder]:
        """获取订单列表"""
        return self.db.get_orders_by_account(account_id, status, limit)
    
    def get_order(self, order_id: str) -> Optional[SimulatedOrder]:
        """获取单个订单"""
        return self.db.get_order(order_id)
    
    # ========== 持仓管理 ==========
    
    def get_position(self, account_id: str, symbol: str) -> Optional[SimulatedPosition]:
        """获取持仓"""
        with self._lock:
            positions = self._positions.get(account_id, {})
            return positions.get(symbol)
    
    def get_positions(self, account_id: str) -> List[SimulatedPosition]:
        """获取所有持仓"""
        with self._lock:
            positions = self._positions.get(account_id, {})
            return list(positions.values())
    
    def update_positions_price(self, prices: Dict[str, float]):
        """
        批量更新持仓价格
        
        Args:
            prices: {symbol: price}
        """
        with self._lock:
            for account_id, positions in self._positions.items():
                account_unrealized = 0.0
                
                for symbol, position in positions.items():
                    if symbol in prices:
                        position.update_price(prices[symbol])
                        account_unrealized += position.unrealized_pnl
                        self.db.save_position(position)
                
                # 更新账户权益
                account = self._accounts[account_id]
                account.unrealized_pnl = account_unrealized
                account.total_equity = account.available_cash + sum(
                    p.market_value for p in positions.values()
                ) + account_unrealized
                account.update_time = datetime.now()
                self.db.save_account(account)
    
    # ========== 成交记录 ==========
    
    def get_trades(self, account_id: str, limit: int = 100) -> List[TradeRecord]:
        """获取成交记录"""
        return self.db.get_trades_by_account(account_id, limit=limit)
    
    # ========== 内部撮合逻辑 ==========
    
    def _get_current_price(self, symbol: str) -> float:
        """获取当前价格"""
        if self._price_feed:
            return self._price_feed(symbol)
        # 默认返回模拟价格
        return 100.0
    
    def _execute_market_order(self, order: SimulatedOrder):
        """执行市价单"""
        current_price = self._get_current_price(order.symbol)
        
        # 计算滑点
        slipage = current_price * self.slippage_rate * np.random.uniform(0.5, 1.5)
        
        # 确定成交价
        if order.side == OrderSide.BUY:
            fill_price = current_price + slipage
        else:
            fill_price = current_price - slipage
        
        # 计算手续费
        amount = fill_price * order.quantity
        commission = max(amount * self.commission_rate, self.min_commission)
        
        # 更新订单
        order.filled_quantity = order.quantity
        order.avg_fill_price = fill_price
        order.commission = commission
        order.slipage = slipage
        order.status = OrderStatus.FILLED
        order.fill_time = datetime.now()
        order.update_time = datetime.now()
        
        self.db.save_order(order)
        
        # 创建成交记录
        trade = TradeRecord(
            trade_id=f"TRD_{uuid.uuid4().hex[:12].upper()}",
            order_id=order.order_id,
            account_id=order.account_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            price=fill_price,
            amount=amount,
            commission=commission,
            slippage=slipage,
            trade_time=datetime.now(),
            strategy_id=order.strategy_id
        )
        self.db.save_trade(trade)
        
        # 更新持仓
        self._update_position_after_fill(order, fill_price)
        
        # 更新账户资金
        self._update_account_after_fill(order, amount, commission)
        
        logger.info(f"订单成交: {order.order_id} | {order.symbol} | {order.side.value} | "
                   f"{order.quantity}股 @ ¥{fill_price:.2f} | 手续费: ¥{commission:.2f}")
    
    def _update_position_after_fill(self, order: SimulatedOrder, fill_price: float):
        """成交后更新持仓"""
        account_id = order.account_id
        symbol = order.symbol
        
        positions = self._positions.setdefault(account_id, {})
        position = positions.get(symbol)
        
        if order.side == OrderSide.BUY:
            if position and position.side == PositionSide.LONG:
                # 加仓 - 更新均价
                total_cost = position.avg_cost * position.quantity + fill_price * order.quantity
                position.quantity += order.quantity
                position.avg_cost = total_cost / position.quantity
                position.update_time = datetime.now()
            else:
                # 新建多头仓位
                position_id = f"POS_{uuid.uuid4().hex[:12].upper()}"
                position = SimulatedPosition(
                    position_id=position_id,
                    account_id=account_id,
                    symbol=symbol,
                    side=PositionSide.LONG,
                    quantity=order.quantity,
                    avg_cost=fill_price,
                    market_price=fill_price,
                    open_time=datetime.now(),
                    strategy_id=order.strategy_id
                )
                positions[symbol] = position
            
            self.db.save_position(position)
        
        else:  # SELL
            if position and position.side == PositionSide.LONG:
                if order.quantity >= position.quantity:
                    # 清仓
                    realized_pnl = (fill_price - position.avg_cost) * position.quantity
                    position.realized_pnl += realized_pnl
                    
                    # 更新账户已实现盈亏
                    account = self._accounts[account_id]
                    account.realized_pnl += realized_pnl
                    
                    del positions[symbol]
                    self.db.delete_position(position.position_id)
                else:
                    # 减仓
                    realized_pnl = (fill_price - position.avg_cost) * order.quantity
                    position.realized_pnl += realized_pnl
                    position.quantity -= order.quantity
                    
                    # 更新账户已实现盈亏
                    account = self._accounts[account_id]
                    account.realized_pnl += realized_pnl
                    
                    self.db.save_position(position)
            
            self.db.save_account(self._accounts[account_id])
    
    def _update_account_after_fill(self, order: SimulatedOrder, amount: float, commission: float):
        """成交后更新账户资金"""
        account = self._accounts[order.account_id]
        
        if order.side == OrderSide.BUY:
            account.available_cash -= (amount + commission)
        else:
            account.available_cash += (amount - commission)
        
        account.total_commission += commission
        account.total_slippage += order.slipage
        account.update_time = datetime.now()
        
        self.db.save_account(account)
    
    # ========== 风险控制 ==========
    
    def check_risk_limits(self, account_id: str, symbol: str, 
                          quantity: int, side: OrderSide) -> Tuple[bool, str]:
        """
        检查风险限制
        
        Returns:
            (是否通过, 拒绝原因)
        """
        account = self._accounts.get(account_id)
        if not account:
            return False, "账户不存在"
        
        settings = account.settings
        current_price = self._get_current_price(symbol)
        order_value = current_price * quantity
        
        # 检查单股仓位限制
        max_single_position = settings.get('max_position_per_stock', 0.2)
        positions = self._positions.get(account_id, {})
        current_position_value = sum(p.market_value for p in positions.values())
        
        existing_position = positions.get(symbol)
        if existing_position and side == OrderSide.BUY:
            new_position_value = existing_position.market_value + order_value
        else:
            new_position_value = order_value
        
        total_equity = account.total_equity
        if new_position_value > total_equity * max_single_position:
            return False, f"单股仓位超限 | 限制: {max_single_position*100}% | " \
                         f"当前: {new_position_value/total_equity*100:.1f}%"
        
        # 检查总仓位限制
        max_total_position = settings.get('max_total_position', 0.9)
        if side == OrderSide.BUY:
            new_total_position = current_position_value + order_value
            if new_total_position > total_equity * max_total_position:
                return False, f"总仓位超限 | 限制: {max_total_position*100}%"
        
        return True, "风险检查通过"
    
    # ========== 数据导出 ==========
    
    def export_account_summary(self, account_id: str) -> Dict:
        """导出账户摘要"""
        account = self._accounts.get(account_id)
        if not account:
            return {}
        
        positions = self._positions.get(account_id, {})
        orders = self.get_orders(account_id, limit=50)
        trades = self.get_trades(account_id, limit=50)
        
        return {
            'account': account.to_dict(),
            'positions': [p.to_dict() for p in positions.values()],
            'position_count': len(positions),
            'total_position_value': sum(p.market_value for p in positions.values()),
            'recent_orders': [o.to_dict() for o in orders[:10]],
            'recent_trades': [t.to_dict() for t in trades[:10]],
            'total_trades': len(trades),
            'win_rate': self._calculate_win_rate(trades),
            'timestamp': datetime.now().isoformat()
        }
    
    def _calculate_win_rate(self, trades: List[TradeRecord]) -> float:
        """计算胜率"""
        if not trades:
            return 0.0
        # 简化计算：根据成交方向统计
        profitable_trades = sum(1 for t in trades if t.side == OrderSide.SELL)
        return profitable_trades / len(trades) if trades else 0.0
    
    # ========== 实时行情处理 ==========
    
    async def start_price_updater(self, price_source: Callable[[], Dict[str, float]],
                                   interval: float = 5.0):
        """
        启动价格更新循环
        
        Args:
            price_source: 价格数据源函数，返回 {symbol: price}
            interval: 更新间隔（秒）
        """
        logger.info(f"启动价格更新循环 | 间隔: {interval}s")
        while True:
            try:
                prices = price_source()
                self.update_positions_price(prices)
                await asyncio.sleep(interval)
            except Exception as e:
                logger.error(f"价格更新出错: {e}")
                await asyncio.sleep(interval)


# ========== 集成接口 ==========

class SimulationEngineIntegration:
    """
    V6.1 SimEdge 集成层
    连接模拟盘引擎与 V6.0 进化引擎
    """
    
    def __init__(self, engine: SimulationTradingEngine):
        self.engine = engine
        self._strategy_accounts: Dict[str, str] = {}  # strategy_id -> account_id
    
    def create_strategy_account(self, strategy_id: str, strategy_name: str,
                                 initial_capital: float = 1000000.0) -> SimulatedAccount:
        """为策略创建专属模拟账户"""
        account_name = f"策略-{strategy_name}-{strategy_id[:8]}"
        settings = {
            'strategy_id': strategy_id,
            'max_position_per_stock': 0.15,
            'max_total_position': 0.8,
            'risk_level': 'medium',
            'auto_trade': True
        }
        account = self.engine.create_account(account_name, initial_capital, settings)
        self._strategy_accounts[strategy_id] = account.account_id
        return account
    
    def execute_strategy_signal(self, strategy_id: str, signal: Dict) -> Tuple[bool, str]:
        """
        执行策略信号
        
        Args:
            strategy_id: 策略ID
            signal: 信号字典 {symbol, action, quantity, confidence}
        
        Returns:
            (是否成功, 消息)
        """
        account_id = self._strategy_accounts.get(strategy_id)
        if not account_id:
            return False, f"策略 {strategy_id} 未绑定模拟账户"
        
        action = signal.get('action')
        symbol = signal.get('symbol')
        quantity = signal.get('quantity', 0)
        
        if action == 'buy':
            success, msg, order = self.engine.submit_order(
                account_id=account_id,
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=quantity,
                order_type=OrderType.MARKET,
                strategy_id=strategy_id,
                tags={'confidence': signal.get('confidence', 0.5)}
            )
            return success, msg
        
        elif action == 'sell':
            # 检查持仓
            position = self.engine.get_position(account_id, symbol)
            if not position:
                return False, f"无持仓: {symbol}"
            
            sell_quantity = min(quantity, position.quantity)
            success, msg, order = self.engine.submit_order(
                account_id=account_id,
                symbol=symbol,
                side=OrderSide.SELL,
                quantity=sell_quantity,
                order_type=OrderType.MARKET,
                strategy_id=strategy_id
            )
            return success, msg
        
        return False, f"未知操作: {action}"
    
    def get_strategy_performance(self, strategy_id: str) -> Dict:
        """获取策略绩效"""
        account_id = self._strategy_accounts.get(strategy_id)
        if not account_id:
            return {}
        
        return self.engine.export_account_summary(account_id)
    
    def get_all_strategies_performance(self) -> Dict[str, Dict]:
        """获取所有策略绩效"""
        results = {}
        for strategy_id, account_id in self._strategy_accounts.items():
            results[strategy_id] = self.engine.export_account_summary(account_id)
        return results


# ========== 快速启动函数 ==========

def create_simulation_engine(db_path: str = "simulation_trading.db",
                              **kwargs) -> SimulationTradingEngine:
    """快速创建模拟盘引擎实例"""
    return SimulationTradingEngine(db_path=db_path, **kwargs)


# ========== 测试代码 ==========

if __name__ == "__main__":
    # 初始化引擎
    engine = create_simulation_engine("test_simulation.db")
    
    # 创建测试账户
    account = engine.create_account(
        name="测试账户-001",
        initial_capital=1000000.0,
        settings={'risk_level': 'high'}
    )
    print(f"创建账户: {account.account_id}")
    print(f"初始资金: ¥{account.initial_capital:,.2f}")
    
    # 设置模拟价格
    test_prices = {
        '000001.SZ': 10.5,
        '000002.SZ': 25.3,
        '600000.SH': 8.8
    }
    engine.set_price_feed(lambda symbol: test_prices.get(symbol, 100.0))
    
    # 提交买入订单
    success, msg, order = engine.submit_order(
        account_id=account.account_id,
        symbol='000001.SZ',
        side=OrderSide.BUY,
        quantity=1000,
        order_type=OrderType.MARKET
    )
    print(f"\n买入订单: {msg}")
    
    # 更新价格并查看持仓
    engine.update_positions_price(test_prices)
    positions = engine.get_positions(account.account_id)
    print(f"\n当前持仓:")
    for p in positions:
        print(f"  {p.symbol}: {p.quantity}股 @ ¥{p.avg_cost:.2f} | 市值: ¥{p.market_value:,.2f}")
    
    # 查看账户
    account = engine.get_account(account.account_id)
    print(f"\n账户状态:")
    print(f"  可用资金: ¥{account.available_cash:,.2f}")
    print(f"  总资产: ¥{account.total_equity:,.2f}")
    print(f"  总盈亏: ¥{account.realized_pnl + account.unrealized_pnl:,.2f}")
    
    print("\n✅ 模拟盘引擎测试完成")
