"""
模拟交易引擎核心模块
功能: 模拟订单执行、成交模拟、资金管理、持仓管理
"""

import os
import json
import sqlite3
import logging
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from contextlib import contextmanager
import uuid

from modules.simulation_models import (
    SimAccount, SimPosition, SimOrder, SimTransaction, SimFundFlow,
    SimPerformance, SimulationPortfolio, OrderStatus, OrderType, ActionType
)

logger = logging.getLogger("SimulationEngine")


class SimulationConfig:
    """模拟盘配置"""
    
    # 交易费用配置
    COMMISSION_RATE = 0.00025           # 佣金率 万2.5
    MIN_COMMISSION = 5.0                # 最低佣金 5元
    STAMP_TAX_RATE = 0.0005             # 印花税率 0.05% (卖出时收取)
    TRANSFER_FEE_RATE = 0.00002         # 过户费率 0.002%
    
    # 滑点配置
    SLIPPAGE_RATE = 0.001               # 滑点率 0.1%
    
    # 交易规则
    MIN_ORDER_AMOUNT = 100              # 最小下单股数 (1手)
    T_PLUS_1 = True                     # T+1交易规则
    
    # 风险控制
    MAX_POSITION_PCT = 0.20             # 单股最大仓位 20%
    MAX_TOTAL_POSITION_PCT = 0.90       # 总仓位上限 90%
    DAILY_LOSS_LIMIT_PCT = 0.02         # 单日最大亏损 2%


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = "data/simulation.db"):
        self.db_path = db_path
        self._local = threading.local()
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """获取数据库连接（线程安全）"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(self.db_path)
            self._local.connection.row_factory = sqlite3.Row
        try:
            yield self._local.connection
        except Exception as e:
            self._local.connection.rollback()
            raise e
    
    def _init_database(self):
        """初始化数据库表结构"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with self.get_connection() as conn:
            # 模拟账户表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sim_accounts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_name TEXT NOT NULL,
                    initial_capital REAL NOT NULL,
                    available_cash REAL NOT NULL,
                    total_value REAL NOT NULL,
                    total_profit REAL DEFAULT 0,
                    total_return_pct REAL DEFAULT 0,
                    max_drawdown REAL DEFAULT 0,
                    sharpe_ratio REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    status TEXT DEFAULT 'active'
                )
            """)
            
            # 模拟持仓表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sim_positions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    stock_code TEXT NOT NULL,
                    stock_name TEXT,
                    quantity INTEGER NOT NULL,
                    avg_cost REAL NOT NULL,
                    current_price REAL,
                    market_value REAL,
                    unrealized_pnl REAL,
                    unrealized_pnl_pct REAL,
                    sector TEXT,
                    opened_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(account_id, stock_code)
                )
            """)
            
            # 模拟订单表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sim_orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    order_id TEXT UNIQUE NOT NULL,
                    stock_code TEXT NOT NULL,
                    order_type TEXT NOT NULL,
                    action TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL,
                    filled_quantity INTEGER DEFAULT 0,
                    filled_price REAL,
                    status TEXT DEFAULT 'pending',
                    strategy TEXT,
                    signal_id INTEGER,
                    commission REAL DEFAULT 0,
                    slippage REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    filled_at TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 模拟成交表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sim_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    order_id TEXT NOT NULL,
                    transaction_id TEXT UNIQUE NOT NULL,
                    stock_code TEXT NOT NULL,
                    action TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    price REAL NOT NULL,
                    amount REAL NOT NULL,
                    commission REAL NOT NULL,
                    stamp_tax REAL DEFAULT 0,
                    transfer_fee REAL DEFAULT 0,
                    total_cost REAL NOT NULL,
                    realized_pnl REAL,
                    transaction_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 资金流水表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sim_fund_flow (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    flow_type TEXT NOT NULL,
                    amount REAL NOT NULL,
                    balance_after REAL NOT NULL,
                    reference_id TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 权益曲线表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sim_equity_curve (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_id INTEGER NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    total_value REAL NOT NULL,
                    cash REAL NOT NULL,
                    positions_value REAL NOT NULL,
                    unrealized_pnl REAL,
                    benchmark_value REAL
                )
            """)
            
            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_account ON sim_orders(account_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_orders_status ON sim_orders(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_positions_account ON sim_positions(account_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_transactions_account ON sim_transactions(account_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_fundflow_account ON sim_fund_flow(account_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_equity_account ON sim_equity_curve(account_id)")
            
            conn.commit()
            logger.info("✅ 模拟盘数据库初始化完成")


class SimulationTradingEngine:
    """模拟交易引擎"""
    
    def __init__(self, config_path: str = "config.json", db_path: str = "data/simulation.db"):
        self.config_path = config_path
        self.db = DatabaseManager(db_path)
        self.config = self._load_config()
        self.portfolios: Dict[int, SimulationPortfolio] = {}  # account_id -> portfolio
        self._price_cache: Dict[str, float] = {}  # stock_code -> price
        self._lock = threading.RLock()
        
        # 初始化默认账户
        self._init_default_account()
    
    def _load_config(self) -> Dict:
        """加载配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"配置加载失败: {e}，使用默认配置")
            return {"simulation": {"enabled": True, "initial_capital": 1000000}}
    
    def _init_default_account(self):
        """初始化默认模拟账户"""
        accounts = self.get_accounts()
        if not accounts:
            initial_capital = self.config.get("simulation", {}).get("initial_capital", 1000000)
            account = self.create_account("默认模拟账户", initial_capital)
            logger.info(f"✅ 创建默认模拟账户: ID={account.id}, 初始资金={initial_capital:,.0f}")
    
    # ═══════════════════════════════════════════════════════════
    # 账户管理
    # ═══════════════════════════════════════════════════════════
    
    def create_account(self, account_name: str, initial_capital: float) -> SimAccount:
        """创建模拟账户"""
        account = SimAccount(
            account_name=account_name,
            initial_capital=initial_capital,
            available_cash=initial_capital,
            total_value=initial_capital,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            status="active"
        )
        
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO sim_accounts 
                (account_name, initial_capital, available_cash, total_value, created_at, updated_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (account.account_name, account.initial_capital, account.available_cash,
                  account.total_value, account.created_at, account.updated_at, account.status))
            account.id = cursor.lastrowid
            
            # 记录初始资金流水
            self._record_fund_flow_internal(conn, account.id, "initial_capital", 
                                            initial_capital, initial_capital, None,
                                            "初始资金入账")
            conn.commit()
        
        return account
    
    def get_accounts(self) -> List[SimAccount]:
        """获取所有模拟账户"""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM sim_accounts ORDER BY id")
            rows = cursor.fetchall()
            return [SimAccount(**dict(row)) for row in rows]
    
    def get_account(self, account_id: int) -> Optional[SimAccount]:
        """获取指定账户"""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM sim_accounts WHERE id = ?", (account_id,))
            row = cursor.fetchone()
            return SimAccount(**dict(row)) if row else None
    
    def reset_account(self, account_id: int) -> bool:
        """重置模拟账户（清空所有数据，保留账户）"""
        with self.db.get_connection() as conn:
            account = self.get_account(account_id)
            if not account:
                return False
            
            # 删除相关数据
            conn.execute("DELETE FROM sim_positions WHERE account_id = ?", (account_id,))
            conn.execute("DELETE FROM sim_orders WHERE account_id = ?", (account_id,))
            conn.execute("DELETE FROM sim_transactions WHERE account_id = ?", (account_id,))
            conn.execute("DELETE FROM sim_fund_flow WHERE account_id = ?", (account_id,))
            conn.execute("DELETE FROM sim_equity_curve WHERE account_id = ?", (account_id,))
            
            # 重置账户
            conn.execute("""
                UPDATE sim_accounts 
                SET available_cash = initial_capital, total_value = initial_capital,
                    total_profit = 0, total_return_pct = 0, max_drawdown = 0, sharpe_ratio = 0,
                    updated_at = ?
                WHERE id = ?
            """, (datetime.now(), account_id))
            
            # 重新记录初始资金
            self._record_fund_flow_internal(conn, account_id, "initial_capital",
                                            account.initial_capital, account.initial_capital, None,
                                            "账户重置-初始资金")
            conn.commit()
        
        # 清除缓存
        if account_id in self.portfolios:
            del self.portfolios[account_id]
        
        logger.info(f"✅ 模拟账户 {account_id} 已重置")
        return True
    
    # ═══════════════════════════════════════════════════════════
    # 持仓管理
    # ═══════════════════════════════════════════════════════════
    
    def get_positions(self, account_id: int) -> List[SimPosition]:
        """获取账户持仓"""
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM sim_positions WHERE account_id = ? AND quantity > 0
            """, (account_id,))
            rows = cursor.fetchall()
            return [SimPosition(**dict(row)) for row in rows]
    
    def get_position(self, account_id: int, stock_code: str) -> Optional[SimPosition]:
        """获取指定持仓"""
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM sim_positions WHERE account_id = ? AND stock_code = ?
            """, (account_id, stock_code))
            row = cursor.fetchone()
            return SimPosition(**dict(row)) if row else None
    
    def update_position_price(self, account_id: int, stock_code: str, current_price: float):
        """更新持仓价格"""
        position = self.get_position(account_id, stock_code)
        if position:
            position.update_market_value(current_price)
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE sim_positions 
                    SET current_price = ?, market_value = ?, unrealized_pnl = ?, 
                        unrealized_pnl_pct = ?, updated_at = ?
                    WHERE id = ?
                """, (position.current_price, position.market_value, position.unrealized_pnl,
                      position.unrealized_pnl_pct, datetime.now(), position.id))
                conn.commit()
    
    # ═══════════════════════════════════════════════════════════
    # 订单管理
    # ═══════════════════════════════════════════════════════════
    
    def submit_order(self, account_id: int, stock_code: str, action: str,
                     quantity: int, price: Optional[float] = None,
                     order_type: str = "limit", strategy: str = "",
                     signal_id: Optional[int] = None) -> Tuple[SimOrder, str]:
        """提交订单
        
        Returns:
            (order, message) - 订单对象和状态消息
        """
        with self._lock:
            account = self.get_account(account_id)
            if not account:
                return None, "账户不存在"
            
            if account.status != "active":
                return None, "账户已禁用"
            
            # 参数校验
            if quantity < SimulationConfig.MIN_ORDER_AMOUNT:
                return None, f"最小下单数量为{SimulationConfig.MIN_ORDER_AMOUNT}股"
            
            if quantity % 100 != 0:
                return None, "下单数量必须是100的整数倍"
            
            if order_type == "limit" and price is None:
                return None, "限价单必须指定价格"
            
            # 买入检查
            if action == "buy":
                estimated_cost = quantity * (price or self._get_current_price(stock_code))
                commission = max(estimated_cost * SimulationConfig.COMMISSION_RATE, 
                               SimulationConfig.MIN_COMMISSION)
                total_cost = estimated_cost + commission
                
                if total_cost > account.available_cash:
                    return None, f"可用资金不足: 需要{total_cost:,.2f}，可用{account.available_cash:,.2f}"
            
            # 卖出检查
            elif action == "sell":
                position = self.get_position(account_id, stock_code)
                if not position or position.quantity < quantity:
                    available = position.quantity if position else 0
                    return None, f"持仓不足: 可卖{available}股，请求卖出{quantity}股"
                
                # T+1检查
                if SimulationConfig.T_PLUS_1:
                    can_sell = self._get_sellable_quantity(account_id, stock_code)
                    if can_sell < quantity:
                        return None, f"T+1限制: 可卖{can_sell}股，{quantity - can_sell}股需等待"
            
            else:
                return None, f"无效的操作类型: {action}"
            
            # 创建订单
            order = SimOrder(
                account_id=account_id,
                order_id=f"SIM{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
                stock_code=stock_code,
                order_type=order_type,
                action=action,
                quantity=quantity,
                price=price,
                status="pending",
                strategy=strategy,
                signal_id=signal_id,
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            # 保存订单
            with self.db.get_connection() as conn:
                cursor = conn.execute("""
                    INSERT INTO sim_orders 
                    (account_id, order_id, stock_code, order_type, action, quantity, price,
                     status, strategy, signal_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (order.account_id, order.order_id, order.stock_code, order.order_type,
                      order.action, order.quantity, order.price, order.status,
                      order.strategy, order.signal_id, order.created_at, order.updated_at))
                order.id = cursor.lastrowid
                
                # 买入时冻结资金
                if action == "buy":
                    freeze_amount = quantity * (price or self._get_current_price(stock_code))
                    new_cash = account.available_cash - freeze_amount
                    conn.execute("""
                        UPDATE sim_accounts SET available_cash = ?, updated_at = ? WHERE id = ?
                    """, (new_cash, datetime.now(), account_id))
                    
                    self._record_fund_flow_internal(conn, account_id, "buy_order",
                                                    -freeze_amount, new_cash, order.order_id,
                                                    f"买入订单冻结: {stock_code} {quantity}股")
                
                conn.commit()
            
            logger.info(f"✅ 订单提交: {order.order_id} {action} {stock_code} {quantity}股 @ {price}")
            
            # 市价单立即成交
            if order_type == "market":
                self._execute_order(order)
            
            return order, "订单提交成功"
    
    def cancel_order(self, account_id: int, order_id: str) -> Tuple[bool, str]:
        """撤单"""
        with self._lock:
            order = self.get_order(order_id)
            if not order or order.account_id != account_id:
                return False, "订单不存在"
            
            if not order.is_active:
                return False, f"订单状态为{order.status}，无法撤单"
            
            # 解冻资金（买入订单）
            if order.action == "buy":
                account = self.get_account(account_id)
                unfreeze_amount = order.remaining_quantity * (order.price or 0)
                new_cash = account.available_cash + unfreeze_amount
                
                with self.db.get_connection() as conn:
                    conn.execute("""
                        UPDATE sim_accounts SET available_cash = ?, updated_at = ? WHERE id = ?
                    """, (new_cash, datetime.now(), account_id))
                    
                    self._record_fund_flow_internal(conn, account_id, "buy_order",
                                                    unfreeze_amount, new_cash, order_id,
                                                    f"撤单解冻: {order.stock_code}")
            
            # 更新订单状态
            order.cancel()
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE sim_orders SET status = ?, updated_at = ? WHERE id = ?
                """, (order.status, datetime.now(), order.id))
                conn.commit()
            
            logger.info(f"✅ 订单撤单: {order_id}")
            return True, "撤单成功"
    
    def get_order(self, order_id: str) -> Optional[SimOrder]:
        """获取订单"""
        with self.db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM sim_orders WHERE order_id = ?", (order_id,))
            row = cursor.fetchone()
            return SimOrder(**dict(row)) if row else None
    
    def get_orders(self, account_id: int, status: Optional[str] = None) -> List[SimOrder]:
        """获取订单列表"""
        with self.db.get_connection() as conn:
            if status:
                cursor = conn.execute("""
                    SELECT * FROM sim_orders WHERE account_id = ? AND status = ?
                    ORDER BY created_at DESC
                """, (account_id, status))
            else:
                cursor = conn.execute("""
                    SELECT * FROM sim_orders WHERE account_id = ?
                    ORDER BY created_at DESC
                """, (account_id,))
            rows = cursor.fetchall()
            return [SimOrder(**dict(row)) for row in rows]
    
    # ═══════════════════════════════════════════════════════════
    # 成交处理
    # ═══════════════════════════════════════════════════════════
    
    def _execute_order(self, order: SimOrder) -> Optional[SimTransaction]:
        """执行订单"""
        with self._lock:
            # 获取当前价格
            current_price = self._get_current_price(order.stock_code)
            if current_price <= 0:
                logger.error(f"无法获取价格: {order.stock_code}")
                return None
            
            # 计算成交价格（加入滑点）
            if order.action == "buy":
                fill_price = current_price * (1 + SimulationConfig.SLIPPAGE_RATE)
            else:
                fill_price = current_price * (1 - SimulationConfig.SLIPPAGE_RATE)
            
            fill_qty = order.remaining_quantity
            
            # 计算费用
            amount = fill_qty * fill_price
            commission = max(amount * SimulationConfig.COMMISSION_RATE, SimulationConfig.MIN_COMMISSION)
            stamp_tax = amount * SimulationConfig.STAMP_TAX_RATE if order.action == "sell" else 0
            transfer_fee = amount * SimulationConfig.TRANSFER_FEE_RATE
            total_cost = amount + commission + stamp_tax + transfer_fee
            
            # 计算已实现盈亏（卖出时）
            realized_pnl = None
            if order.action == "sell":
                position = self.get_position(order.account_id, order.stock_code)
                if position:
                    realized_pnl = (fill_price - position.avg_cost) * fill_qty - commission - stamp_tax - transfer_fee
            
            # 创建成交记录
            transaction = SimTransaction(
                account_id=order.account_id,
                order_id=order.order_id,
                transaction_id=f"TRX{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}",
                stock_code=order.stock_code,
                action=order.action,
                quantity=fill_qty,
                price=fill_price,
                amount=amount,
                commission=commission,
                stamp_tax=stamp_tax,
                transfer_fee=transfer_fee,
                total_cost=total_cost,
                realized_pnl=realized_pnl,
                transaction_time=datetime.now()
            )
            
            with self.db.get_connection() as conn:
                # 保存成交
                cursor = conn.execute("""
                    INSERT INTO sim_transactions
                    (account_id, order_id, transaction_id, stock_code, action, quantity, price,
                     amount, commission, stamp_tax, transfer_fee, total_cost, realized_pnl, transaction_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (transaction.account_id, transaction.order_id, transaction.transaction_id,
                      transaction.stock_code, transaction.action, transaction.quantity,
                      transaction.price, transaction.amount, transaction.commission,
                      transaction.stamp_tax, transaction.transfer_fee, transaction.total_cost,
                      transaction.realized_pnl, transaction.transaction_time))
                transaction.id = cursor.lastrowid
                
                # 更新订单状态
                order.fill(fill_qty, fill_price)
                conn.execute("""
                    UPDATE sim_orders 
                    SET filled_quantity = ?, filled_price = ?, status = ?, 
                        commission = ?, slippage = ?, filled_at = ?, updated_at = ?
                    WHERE id = ?
                """, (order.filled_quantity, order.filled_price, order.status,
                      commission, SimulationConfig.SLIPPAGE_RATE, order.filled_at,
                      datetime.now(), order.id))
                
                # 更新账户和持仓
                self._update_account_on_fill(conn, order, transaction)
                
                conn.commit()
            
            logger.info(f"✅ 订单成交: {order.order_id} {order.action} {order.stock_code} "
                       f"{fill_qty}股 @ {fill_price:.2f} 费用:{total_cost - amount:.2f}")
            
            return transaction
    
    def _update_account_on_fill(self, conn, order: SimOrder, transaction: SimTransaction):
        """成交后更新账户和持仓"""
        account = self.get_account(order.account_id)
        
        if order.action == "buy":
            # 买入：更新持仓
            position = self.get_position(order.account_id, order.stock_code)
            if position:
                # 加仓，更新平均成本
                total_cost = position.quantity * position.avg_cost + transaction.total_cost
                new_qty = position.quantity + transaction.quantity
                new_avg_cost = total_cost / new_qty
                
                conn.execute("""
                    UPDATE sim_positions 
                    SET quantity = ?, avg_cost = ?, current_price = ?, market_value = ?,
                        unrealized_pnl = ?, unrealized_pnl_pct = ?, updated_at = ?
                    WHERE id = ?
                """, (new_qty, new_avg_cost, transaction.price, new_qty * transaction.price,
                      (transaction.price - new_avg_cost) * new_qty,
                      (transaction.price - new_avg_cost) / new_avg_cost if new_avg_cost > 0 else 0,
                      datetime.now(), position.id))
            else:
                # 新建仓
                conn.execute("""
                    INSERT INTO sim_positions
                    (account_id, stock_code, quantity, avg_cost, current_price, market_value,
                     unrealized_pnl, unrealized_pnl_pct, opened_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (order.account_id, order.stock_code, transaction.quantity,
                      transaction.price, transaction.price, transaction.total_cost,
                      0, 0, datetime.now(), datetime.now()))
            
            # 记录资金流出（实际扣除）
            actual_deduct = transaction.total_cost
            new_cash = account.available_cash - actual_deduct
            conn.execute("""
                UPDATE sim_accounts SET available_cash = ?, updated_at = ? WHERE id = ?
            """, (new_cash, datetime.now(), order.account_id))
            
            # 记录资金流水
            self._record_fund_flow_internal(conn, order.account_id, "commission",
                                            -transaction.commission, new_cash, transaction.transaction_id,
                                            f"佣金: {order.stock_code}")
            self._record_fund_flow_internal(conn, order.account_id, "transfer_fee",
                                            -transaction.transfer_fee, new_cash, transaction.transaction_id,
                                            f"过户费: {order.stock_code}")
        
        else:  # sell
            # 卖出：更新持仓
            position = self.get_position(order.account_id, order.stock_code)
            if position:
                new_qty = position.quantity - transaction.quantity
                if new_qty > 0:
                    conn.execute("""
                        UPDATE sim_positions 
                        SET quantity = ?, current_price = ?, market_value = ?, updated_at = ?
                        WHERE id = ?
                    """, (new_qty, transaction.price, new_qty * transaction.price,
                          datetime.now(), position.id))
                else:
                    # 清仓
                    conn.execute("DELETE FROM sim_positions WHERE id = ?", (position.id,))
            
            # 增加可用资金（扣除费用后的净收入）
            net_income = transaction.amount - transaction.commission - transaction.stamp_tax - transaction.transfer_fee
            new_cash = account.available_cash + net_income
            
            conn.execute("""
                UPDATE sim_accounts SET available_cash = ?, updated_at = ? WHERE id = ?
            """, (new_cash, datetime.now(), order.account_id))
            
            # 记录已实现盈亏
            if transaction.realized_pnl:
                conn.execute("""
                    UPDATE sim_accounts SET total_profit = total_profit + ? WHERE id = ?
                """, (transaction.realized_pnl, order.account_id))
            
            # 记录资金流水
            self._record_fund_flow_internal(conn, order.account_id, "sell_order",
                                            net_income, new_cash, transaction.transaction_id,
                                            f"卖出收入: {order.stock_code} {transaction.quantity}股")
            self._record_fund_flow_internal(conn, order.account_id, "commission",
                                            -transaction.commission, new_cash, transaction.transaction_id,
                                            f"佣金: {order.stock_code}")
            self._record_fund_flow_internal(conn, order.account_id, "stamp_tax",
                                            -transaction.stamp_tax, new_cash, transaction.transaction_id,
                                            f"印花税: {order.stock_code}")
            if transaction.realized_pnl:
                self._record_fund_flow_internal(conn, order.account_id, "realized_pnl",
                                                transaction.realized_pnl, new_cash, transaction.transaction_id,
                                                f"已实现盈亏: {order.stock_code}")
    
    def get_transactions(self, account_id: int, limit: int = 100) -> List[SimTransaction]:
        """获取成交记录"""
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM sim_transactions 
                WHERE account_id = ?
                ORDER BY transaction_time DESC
                LIMIT ?
            """, (account_id, limit))
            rows = cursor.fetchall()
            return [SimTransaction(**dict(row)) for row in rows]
    
    # ═══════════════════════════════════════════════════════════
    # 资金流水
    # ═══════════════════════════════════════════════════════════
    
    def _record_fund_flow_internal(self, conn, account_id: int, flow_type: str,
                                    amount: float, balance_after: float,
                                    reference_id: Optional[str], description: str):
        """内部方法：记录资金流水"""
        conn.execute("""
            INSERT INTO sim_fund_flow
            (account_id, flow_type, amount, balance_after, reference_id, description, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (account_id, flow_type, amount, balance_after, reference_id, description, datetime.now()))
    
    def get_fund_flow(self, account_id: int, limit: int = 100) -> List[SimFundFlow]:
        """获取资金流水"""
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM sim_fund_flow 
                WHERE account_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            """, (account_id, limit))
            rows = cursor.fetchall()
            return [SimFundFlow(**dict(row)) for row in rows]
    
    # ═══════════════════════════════════════════════════════════
    # 价格和行情
    # ═══════════════════════════════════════════════════════════
    
    def _get_current_price(self, stock_code: str) -> float:
        """获取当前价格（可从数据源获取）"""
        # 优先从缓存获取
        if stock_code in self._price_cache:
            return self._price_cache[stock_code]
        
        # 尝试从akshare获取实时价格
        try:
            import akshare as ak
            # 转换股票代码格式
            if stock_code.startswith('6'):
                code_fmt = f"sh{stock_code}"
            else:
                code_fmt = f"sz{stock_code}"
            
            df = ak.stock_zh_a_spot_em()
            row = df[df['代码'] == stock_code]
            if not row.empty:
                price = float(row.iloc[0]['最新价'])
                self._price_cache[stock_code] = price
                return price
        except Exception as e:
            logger.warning(f"获取实时价格失败: {stock_code}, {e}")
        
        # 返回默认价格
        return 10.0
    
    def update_prices(self, prices: Dict[str, float]):
        """批量更新价格"""
        self._price_cache.update(prices)
    
    # ═══════════════════════════════════════════════════════════
    # T+1 卖出限制
    # ═══════════════════════════════════════════════════════════
    
    def _get_sellable_quantity(self, account_id: int, stock_code: str) -> int:
        """获取可卖数量（扣除T+1限制）"""
        position = self.get_position(account_id, stock_code)
        if not position:
            return 0
        
        # 查询今日买入的数量
        with self.db.get_connection() as conn:
            today = datetime.now().strftime('%Y-%m-%d')
            cursor = conn.execute("""
                SELECT SUM(filled_quantity) as today_bought
                FROM sim_orders
                WHERE account_id = ? AND stock_code = ? AND action = 'buy'
                AND date(created_at) = ? AND status IN ('filled', 'partial')
            """, (account_id, stock_code, today))
            row = cursor.fetchone()
            today_bought = row[0] or 0
        
        return max(0, position.quantity - today_bought)
    
    # ═══════════════════════════════════════════════════════════
    # 业绩计算
    # ═══════════════════════════════════════════════════════════
    
    def get_performance(self, account_id: int) -> SimPerformance:
        """获取业绩指标"""
        account = self.get_account(account_id)
        transactions = self.get_transactions(account_id, limit=1000)
        
        perf = SimPerformance(account_id=account_id)
        
        # 基础指标
        if account.initial_capital > 0:
            perf.total_return = (account.total_value - account.initial_capital) / account.initial_capital
        
        # 交易统计
        perf.total_trades = len([t for t in transactions if t.realized_pnl is not None])
        profitable = [t for t in transactions if t.realized_pnl and t.realized_pnl > 0]
        loss = [t for t in transactions if t.realized_pnl and t.realized_pnl <= 0]
        perf.profitable_trades = len(profitable)
        perf.loss_trades = len(loss)
        
        if perf.total_trades > 0:
            perf.win_rate = perf.profitable_trades / perf.total_trades
        
        # 盈亏比
        avg_profit = sum(t.realized_pnl for t in profitable) / len(profitable) if profitable else 0
        avg_loss = abs(sum(t.realized_pnl for t in loss) / len(loss)) if loss else 1
        if avg_loss > 0:
            perf.profit_loss_ratio = avg_profit / avg_loss
        
        # 费用统计
        perf.total_commission = sum(t.commission for t in transactions)
        perf.total_tax = sum(t.stamp_tax for t in transactions)
        
        return perf
    
    def get_equity_curve(self, account_id: int, days: int = 30) -> List[Dict]:
        """获取权益曲线"""
        with self.db.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM sim_equity_curve
                WHERE account_id = ?
                AND timestamp >= datetime('now', '-{} days')
                ORDER BY timestamp
            """.format(days), (account_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
    
    # ═══════════════════════════════════════════════════════════
    # 看板数据对接
    # ═══════════════════════════════════════════════════════════
    
    def get_dashboard_data(self, account_id: int) -> Dict:
        """获取看板数据"""
        account = self.get_account(account_id)
        positions = self.get_positions(account_id)
        orders = self.get_orders(account_id)
        transactions = self.get_transactions(account_id, limit=20)
        performance = self.get_performance(account_id)
        
        # 计算持仓盈亏
        total_unrealized = sum(p.unrealized_pnl for p in positions)
        positions_value = sum(p.market_value for p in positions)
        
        # 活跃订单
        active_orders = [o for o in orders if o.is_active]
        
        return {
            "account": account.to_dict() if account else None,
            "positions": {
                "count": len(positions),
                "total_value": positions_value,
                "total_unrealized_pnl": total_unrealized,
                "list": [p.to_dict() for p in positions]
            },
            "orders": {
                "total": len(orders),
                "active": len(active_orders),
                "today_filled": len([o for o in orders if o.status == "filled" 
                                      and o.filled_at and o.filled_at.date() == datetime.now().date()]),
                "list": [o.to_dict() for o in orders[:20]]
            },
            "transactions": [t.to_dict() for t in transactions],
            "performance": performance.to_dict(),
            "summary": {
                "total_assets": account.total_value if account else 0,
                "available_cash": account.available_cash if account else 0,
                "positions_value": positions_value,
                "total_return": account.total_return_pct if account else 0,
                "daily_pnl": 0,  # 需要计算
                "win_rate": performance.win_rate
            }
        }
    
    # ═══════════════════════════════════════════════════════════
    # 模拟盘控制
    # ═══════════════════════════════════════════════════════════
    
    def process_market_data(self, market_data: Dict[str, float]):
        """处理市场数据，更新持仓市值"""
        self.update_prices(market_data)
        
        # 更新所有账户的持仓价格
        accounts = self.get_accounts()
        for account in accounts:
            positions = self.get_positions(account.id)
            for position in positions:
                if position.stock_code in market_data:
                    self.update_position_price(account.id, position.stock_code, 
                                               market_data[position.stock_code])
            
            # 更新账户总资产
            positions = self.get_positions(account.id)  # 重新获取更新后的数据
            total_value = account.available_cash + sum(p.market_value for p in positions)
            
            with self.db.get_connection() as conn:
                conn.execute("""
                    UPDATE sim_accounts 
                    SET total_value = ?, total_return_pct = ?, updated_at = ?
                    WHERE id = ?
                """, (total_value, 
                      (total_value - account.initial_capital) / account.initial_capital if account.initial_capital > 0 else 0,
                      datetime.now(), account.id))
                conn.commit()
    
    def match_orders(self):
        """撮合待成交订单（模拟）"""
        # 获取所有待成交订单
        accounts = self.get_accounts()
        for account in accounts:
            pending_orders = [o for o in self.get_orders(account.id) if o.is_active]
            for order in pending_orders:
                # 模拟成交
                current_price = self._get_current_price(order.stock_code)
                
                # 价格检查
                if order.order_type == "limit" and order.price:
                    if order.action == "buy" and current_price > order.price:
                        continue  # 买限价单，当前价高于限价，不成交
                    if order.action == "sell" and current_price < order.price:
                        continue  # 卖限价单，当前价低于限价，不成交
                
                # 执行成交
                self._execute_order(order)


# 全局引擎实例
_sim_engine = None

def get_simulation_engine(config_path: str = "config.json") -> SimulationTradingEngine:
    """获取模拟引擎单例"""
    global _sim_engine
    if _sim_engine is None:
        _sim_engine = SimulationTradingEngine(config_path)
    return _sim_engine
