# simulation_trading_system.py
# Kimi Claw V6.1 - 模拟盘交易系统
# 放置路径: /project_root/simulation_trading_system.py

import datetime, uuid, json, logging, threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable
from enum import Enum
from collections import defaultdict
import numpy as np

# ═══════════════════════════════════════════
# 枚举定义
# ═══════════════════════════════════════════
class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"

class OrderType(Enum):
    MARKET = "market"
    LIMIT = "limit"

class OrderStatus(Enum):
    PENDING = "pending"        # 待撮合
    PARTIAL = "partial_filled" # 部分成交
    FILLED = "filled"          # 全部成交
    CANCELLED = "cancelled"    # 已撤单
    REJECTED = "rejected"      # 已拒绝

class SlippageMode(Enum):
    FIXED = "fixed"            # 固定滑点(bps)
    RATIO = "ratio"            # 比例滑点
    DYNAMIC = "dynamic"        # 动态(按成交量)

# ═══════════════════════════════════════════
# 数据结构
# ═══════════════════════════════════════════
@dataclass
class SimOrder:
    order_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    account_id: str = ""
    code: str = ""             # 股票代码 e.g. "600519"
    name: str = ""             # 股票名称
    side: OrderSide = OrderSide.BUY
    order_type: OrderType = OrderType.LIMIT
    price: float = 0.0         # 限价单价格
    qty: int = 0               # 委托数量
    filled_qty: int = 0        # 已成交数量
    filled_price: float = 0.0  # 成交均价
    status: OrderStatus = OrderStatus.PENDING
    created_at: str = ""       # 委托时间
    filled_at: str = ""        # 成交时间
    commission: float = 0.0    # 佣金
    stamp_duty: float = 0.0    # 印花税
    slippage_cost: float = 0.0 # 滑点成本
    reject_reason: str = ""
    strategy_id: str = ""      # 来源策略
    validity: str = "day"      # day=当日有效, gtc=永久有效

@dataclass
class SimPosition:
    code: str = ""
    name: str = ""
    qty: int = 0               # 持仓数量
    available_qty: int = 0     # 可卖数量(T+1)
    cost_price: float = 0.0    # 成本价
    current_price: float = 0.0
    buy_date: str = ""         # 买入日期(T+1检查)
    pnl: float = 0.0           # 浮动盈亏
    pnl_pct: float = 0.0       # 盈亏百分比

@dataclass
class SimAccount:
    account_id: str = field(default_factory=lambda: f"SIM_{str(uuid.uuid4())[:6]}")
    name: str = "默认模拟账户"
    initial_capital: float = 1_000_000.0
    cash: float = 1_000_000.0
    positions: Dict[str, SimPosition] = field(default_factory=dict)
    orders: List[SimOrder] = field(default_factory=list)
    trades: List[dict] = field(default_factory=list)  # 成交记录
    nav_history: List[dict] = field(default_factory=list)  # 净值曲线
    created_at: str = field(default_factory=lambda: datetime.datetime.now().isoformat())

    @property
    def market_value(self) -> float:
        return sum(p.qty * p.current_price for p in self.positions.values())

    @property
    def total_assets(self) -> float:
        return self.cash + self.market_value

    @property
    def nav(self) -> float:
        return self.total_assets / self.initial_capital

    @property
    def pnl(self) -> float:
        return self.total_assets - self.initial_capital

    @property
    def pnl_pct(self) -> float:
        return (self.total_assets / self.initial_capital - 1) * 100


# ═══════════════════════════════════════════
# 核心撮合引擎
# ═══════════════════════════════════════════
class SimulationMatchEngine:
    """A股规则适配的仿真撮合引擎"""

    # 板块涨跌停映射
    LIMIT_MAP = {
        "main": 0.10,     # 主板 ±10%
        "gem": 0.20,      # 创业板 ±20% (300xxx)
        "star": 0.20,     # 科创板 ±20% (688xxx)
        "st": 0.05,       # ST股 ±5%
    }

    def __init__(self, config: dict = None):
        cfg = config or {}
        self.commission_rate = cfg.get("commission_rate", 0.00025)
        self.min_commission = cfg.get("min_commission", 5.0)
        self.stamp_duty_rate = cfg.get("stamp_duty_rate", 0.0005)
        self.transfer_fee_rate = cfg.get("transfer_fee_rate", 0.00001)
        self.slippage_mode = SlippageMode(cfg.get("slippage_mode", "fixed"))
        self.slippage_bps = cfg.get("slippage_bps", 2)
        self.today = datetime.date.today().isoformat()
        self.pending_orders: List[SimOrder] = []
        self._lock = threading.Lock()

    def get_board_type(self, code: str) -> str:
        if code.startswith("300"): return "gem"
        if code.startswith("688"): return "star"
        # ST检查需要外部数据源标记
        return "main"

    def get_limit_prices(self, code: str, prev_close: float) -> tuple:
        """返回(涨停价, 跌停价)"""
        board = self.get_board_type(code)
        pct = self.LIMIT_MAP.get(board, 0.10)
        up = round(prev_close * (1 + pct), 2)
        down = round(prev_close * (1 - pct), 2)
        return up, down

    def calc_slippage(self, price: float, side: OrderSide, volume: int = 0) -> float:
        if self.slippage_mode == SlippageMode.FIXED:
            delta = price * self.slippage_bps / 10000
        elif self.slippage_mode == SlippageMode.RATIO:
            delta = price * self.slippage_bps / 10000
        else:  # DYNAMIC
            impact = min(0.005, (volume / 1_000_000) * 0.001) if volume > 0 else 0.0005
            delta = price * impact
        return delta if side == OrderSide.BUY else -delta

    def calc_commission(self, amount: float, side: OrderSide) -> dict:
        comm = max(self.min_commission, amount * self.commission_rate)
        stamp = amount * self.stamp_duty_rate if side == OrderSide.SELL else 0
        transfer = amount * self.transfer_fee_rate
        return {"commission": round(comm, 2), "stamp_duty": round(stamp, 2), "transfer_fee": round(transfer, 2)}

    def validate_order(self, order: SimOrder, account: SimAccount, market_data: dict) -> str:
        """验证订单合法性，返回空字符串表示通过，否则返回拒绝原因"""
        code = order.code
        data = market_data.get(code, {})
        if not data:
            return f"无{code}行情数据"

        prev_close = data.get("prev_close", 0)
        current = data.get("current", 0)
        if prev_close <= 0 or current <= 0:
            return "行情数据异常"

        # 涨跌停检查
        up_limit, down_limit = self.get_limit_prices(code, prev_close)
        if order.order_type == OrderType.LIMIT:
            if order.price > up_limit or order.price < down_limit:
                return f"委托价{order.price}超出涨跌停[{down_limit},{up_limit}]"

        # 买入100股整数倍
        if order.side == OrderSide.BUY and order.qty % 100 != 0:
            return f"买入数量{order.qty}必须为100股整数倍"

        # 资金检查(买入)
        if order.side == OrderSide.BUY:
            price = order.price if order.order_type == OrderType.LIMIT else current
            needed = price * order.qty * 1.003  # 预留手续费
            if needed > account.cash:
                return f"资金不足：需{needed:.2f}，可用{account.cash:.2f}"

        # T+1检查(卖出)
        if order.side == OrderSide.SELL:
            pos = account.positions.get(code)
            if not pos or pos.available_qty < order.qty:
                avail = pos.available_qty if pos else 0
                return f"可卖不足：需{order.qty}，可卖{avail}(T+1限制)"

        return ""

    def match_order(self, order: SimOrder, account: SimAccount, market_data: dict) -> SimOrder:
        """撮合单笔订单"""
        with self._lock:
            # 1.验证
            reject = self.validate_order(order, account, market_data)
            if reject:
                order.status = OrderStatus.REJECTED
                order.reject_reason = reject
                return order

            data = market_data[order.code]
            current = data["current"]

            # 2.确定成交价
            if order.order_type == OrderType.MARKET:
                base_price = current
            else:
                # 限价单：买入委托价>=现价成交，卖出委托价<=现价成交
                if order.side == OrderSide.BUY and order.price < current:
                    self.pending_orders.append(order)
                    return order  # 挂单
                if order.side == OrderSide.SELL and order.price > current:
                    self.pending_orders.append(order)
                    return order  # 挂单
                base_price = order.price

            # 3.加滑点
            volume = data.get("volume", 0)
            slippage = self.calc_slippage(base_price, order.side, volume)
            fill_price = round(base_price + slippage, 2)

            # 4.计算费用
            amount = fill_price * order.qty
            fees = self.calc_commission(amount, order.side)
            total_cost = fees["commission"] + fees["stamp_duty"] + fees["transfer_fee"]

            # 5.更新账户
            if order.side == OrderSide.BUY:
                account.cash -= (amount + total_cost)
                pos = account.positions.get(order.code)
                if pos:
                    total_qty = pos.qty + order.qty
                    pos.cost_price = (pos.cost_price*pos.qty + fill_price*order.qty) / total_qty
                    pos.qty = total_qty
                else:
                    account.positions[order.code] = SimPosition(
                        code=order.code, name=order.name,
                        qty=order.qty, available_qty=0,
                        cost_price=fill_price, current_price=fill_price,
                        buy_date=self.today
                    )
            else:  # SELL
                account.cash += (amount - total_cost)
                pos = account.positions[order.code]
                pos.qty -= order.qty
                pos.available_qty -= order.qty
                if pos.qty <= 0:
                    del account.positions[order.code]

            # 6.更新订单状态
            order.filled_qty = order.qty
            order.filled_price = fill_price
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.datetime.now().isoformat()
            order.commission = fees["commission"]
            order.stamp_duty = fees["stamp_duty"]
            order.slippage_cost = round(abs(slippage) * order.qty, 2)

            # 7.记录成交
            account.trades.append({
                "order_id": order.order_id, "code": order.code,
                "name": order.name, "side": order.side.value,
                "price": fill_price, "qty": order.qty,
                "amount": round(amount, 2), "fees": round(total_cost, 2),
                "time": order.filled_at, "strategy": order.strategy_id,
                "account_type": "simulation"
            })

            account.orders.append(order)
            return order


# ═══════════════════════════════════════════
# 绩效统计引擎
# ═══════════════════════════════════════════
class SimulationPerformance:
    """模拟盘绩效计算 + 与实盘对比"""

    @staticmethod
    def calc_metrics(account: SimAccount) -> dict:
        navs = [h["nav"] for h in account.nav_history]
        if len(navs) < 2:
            return {"nav": account.nav, "pnl_pct": account.pnl_pct}
        returns = np.diff(navs) / navs[:-1]
        sharpe = float(np.mean(returns) / np.std(returns) * np.sqrt(252)) if np.std(returns)>0 else 0
        drawdowns = []
        peak = navs[0]
        for n in navs:
            peak = max(peak, n)
            drawdowns.append((n - peak) / peak * 100)
        max_dd = min(drawdowns) if drawdowns else 0
        wins = sum(1 for t in account.trades if t.get("pnl",0)>0)
        total = len(account.trades)
        win_rate = wins/total*100 if total>0 else 0
        return {
            "nav": round(account.nav, 4),
            "total_assets": round(account.total_assets, 2),
            "pnl": round(account.pnl, 2),
            "pnl_pct": round(account.pnl_pct, 2),
            "sharpe": round(sharpe, 2),
            "max_drawdown": round(max_dd, 2),
            "win_rate": round(win_rate, 1),
            "total_trades": total,
            "positions_count": len(account.positions),
        }

    @staticmethod
    def compare_with_real(sim_metrics: dict, real_metrics: dict) -> dict:
        """模拟盘 vs 实盘对比分析"""
        compare = {}
        for key in ["pnl_pct", "sharpe", "max_drawdown", "win_rate"]:
            sv = sim_metrics.get(key, 0)
            rv = real_metrics.get(key, 0)
            compare[key] = {"sim": sv, "real": rv, "diff": round(sv-rv, 2)}
        return compare


# ═══════════════════════════════════════════
# 模拟盘主系统
# ═══════════════════════════════════════════
class SimulationTradingSystem:
    """模拟盘主系统 - 统一入口"""

    def __init__(self, config: dict = None):
        """
        初始化模拟盘主系统
        
        Args:
            config: 配置字典，包含初始资金、手续费率等
        """
        self.config = config or {}
        self.accounts: Dict[str, SimAccount] = {}
        self.engine = SimulationMatchEngine(self.config)
        self.perf = SimulationPerformance()
        self.callbacks: List[Callable] = []
        self._create_default_account()

    def delete_account(self, account_id: str) -> bool:
        """
        删除模拟账户
        
        Args:
            account_id: 账户ID
            
        Returns:
            是否删除成功
        """
        if account_id in self.accounts:
            del self.accounts[account_id]
            return True
        return False

    def list_accounts(self) -> List[SimAccount]:
        """
        获取所有模拟账户列表
        
        Returns:
            账户列表
        """
        return list(self.accounts.values())

    def get_account(self, account_id: str) -> Optional[SimAccount]:
        """
        获取指定模拟账户
        
        Args:
            account_id: 账户ID
            
        Returns:
            账户对象，不存在返回None
        """
        return self.accounts.get(account_id)

    def snapshot(self, account_id: str) -> dict:
        """
        生成账户快照
        
        Args:
            account_id: 账户ID
            
        Returns:
            账户快照数据
        """
        acc = self.accounts.get(account_id)
        if not acc:
            return {}
        
        return {
            "account_id": account_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "total_assets": acc.total_assets,
            "cash": acc.cash,
            "market_value": acc.market_value,
            "nav": acc.nav,
            "pnl": acc.pnl,
            "positions": {code: {
                "code": pos.code,
                "name": pos.name,
                "qty": pos.qty,
                "available_qty": pos.available_qty,
                "cost_price": pos.cost_price,
                "current_price": pos.current_price,
                "pnl": pos.pnl
            } for code, pos in acc.positions.items()},
            "performance": self.perf.calc_metrics(acc)
        }

    def _create_default_account(self):
        capital = self.config.get("initial_capital", 1_000_000)
        acc = SimAccount(initial_capital=capital, cash=capital)
        self.accounts[acc.account_id] = acc

    def create_account(self, name: str, capital: float) -> SimAccount:
        acc = SimAccount(name=name, initial_capital=capital, cash=capital)
        self.accounts[acc.account_id] = acc
        return acc

    def submit_order(self, account_id: str, code: str, name: str,
                     side: str, qty: int, price: float = 0,
                     order_type: str = "limit", strategy_id: str = "") -> SimOrder:
        """提交订单 - 与券商管理器V2接口完全一致"""
        acc = self.accounts.get(account_id)
        if not acc: raise ValueError(f"账户{account_id}不存在")
        order = SimOrder(
            account_id=account_id, code=code, name=name,
            side=OrderSide(side), order_type=OrderType(order_type),
            price=price, qty=qty, strategy_id=strategy_id,
            created_at=datetime.datetime.now().isoformat()
        )
        # 获取行情并撮合(需对接聚宽网关)
        market_data = self._get_market_data([code])
        result = self.engine.match_order(order, acc, market_data)
        # 触发回调(与实盘一致)
        for cb in self.callbacks:
            try: cb({"type":"order_update","data":result.__dict__})
            except: pass
        return result

    def _get_market_data(self, codes: list) -> dict:
        """获取行情 - 对接聚宽数据网关"""
        # TODO: 对接 joinquant_gateway.py
        return {}

    def update_t1(self):
        """每日开盘调用：更新T+1可卖数量"""
        today = datetime.date.today().isoformat()
        for acc in self.accounts.values():
            for pos in acc.positions.values():
                if pos.buy_date < today:
                    pos.available_qty = pos.qty

    def snapshot(self, account_id: str) -> dict:
        """账户快照 - 存入历史知识库"""
        acc = self.accounts.get(account_id)
        if not acc: return {}
        metrics = self.perf.calc_metrics(acc)
        return {
            "account_id": acc.account_id,
            "account_type": "simulation",
            "timestamp": datetime.datetime.now().isoformat(),
            "metrics": metrics,
            "positions": {k:v.__dict__ for k,v in acc.positions.items()},
            "cash": acc.cash,
        }

    def register_callback(self, cb: Callable):
        """注册订单回调 - 与券商管理器V2完全兼容"""
        self.callbacks.append(cb)

    # ═══════════════════════════════════════════
    # 新增：对接聚宽网关获取行情
    # ═══════════════════════════════════════════
    def set_market_data_source(self, data_func: Callable):
        """设置行情数据源函数"""
        self._market_data_func = data_func
    
    def _get_market_data(self, codes: list) -> dict:
        """获取行情 - 优先使用外部数据源"""
        if hasattr(self, '_market_data_func') and self._market_data_func:
            return self._market_data_func(codes)
        return {}

    # ═══════════════════════════════════════════
    # 新增：批量操作接口
    # ═══════════════════════════════════════════
    def batch_submit_orders(self, orders: list) -> list:
        """批量提交订单"""
        results = []
        for order_data in orders:
            try:
                result = self.submit_order(**order_data)
                results.append({"success": True, "order": result})
            except Exception as e:
                results.append({"success": False, "error": str(e), "data": order_data})
        return results

    # ═══════════════════════════════════════════
    # 新增：账户管理接口
    # ═══════════════════════════════════════════
    def get_account(self, account_id: str) -> Optional[SimAccount]:
        """获取账户"""
        return self.accounts.get(account_id)
    
    def list_accounts(self) -> List[SimAccount]:
        """列出所有账户"""
        return list(self.accounts.values())
    
    def delete_account(self, account_id: str) -> bool:
        """删除账户"""
        if account_id in self.accounts:
            del self.accounts[account_id]
            return True
        return False

    # ═══════════════════════════════════════════
    # 新增：持仓查询接口
    # ═══════════════════════════════════════════
    def get_positions(self, account_id: str) -> Dict[str, SimPosition]:
        """获取账户持仓"""
        acc = self.accounts.get(account_id)
        if acc:
            return acc.positions
        return {}
    
    def get_position(self, account_id: str, code: str) -> Optional[SimPosition]:
        """获取单只股票持仓"""
        acc = self.accounts.get(account_id)
        if acc:
            return acc.positions.get(code)
        return None

    # ═══════════════════════════════════════════
    # 新增：订单查询接口
    # ═══════════════════════════════════════════
    def get_orders(self, account_id: str, status: str = None) -> List[SimOrder]:
        """获取账户订单"""
        acc = self.accounts.get(account_id)
        if not acc:
            return []
        
        orders = acc.orders
        if status:
            orders = [o for o in orders if o.status.value == status]
        return orders
    
    def get_order(self, account_id: str, order_id: str) -> Optional[SimOrder]:
        """获取单个订单"""
        acc = self.accounts.get(account_id)
        if acc:
            for o in acc.orders:
                if o.order_id == order_id:
                    return o
        return None
    
    def cancel_order(self, account_id: str, order_id: str) -> bool:
        """撤销订单"""
        acc = self.accounts.get(account_id)
        if acc:
            for o in acc.orders:
                if o.order_id == order_id and o.status == OrderStatus.PENDING:
                    o.status = OrderStatus.CANCELLED
                    return True
        return False

    # ═══════════════════════════════════════════
    # 新增：成交记录接口
    # ═══════════════════════════════════════════
    def get_trades(self, account_id: str, limit: int = 100) -> List[dict]:
        """获取成交记录"""
        acc = self.accounts.get(account_id)
        if acc:
            return acc.trades[-limit:]
        return []

    # ═══════════════════════════════════════════
    # 新增：绩效统计接口
    # ═══════════════════════════════════════════
    def get_performance(self, account_id: str) -> dict:
        """获取账户绩效"""
        acc = self.accounts.get(account_id)
        if acc:
            return self.perf.calc_metrics(acc)
        return {}
    
    def compare_performance(self, sim_account_id: str, real_metrics: dict) -> dict:
        """对比模拟盘与实盘绩效"""
        sim_metrics = self.get_performance(sim_account_id)
        return self.perf.compare_with_real(sim_metrics, real_metrics)

    # ═══════════════════════════════════════════
    # 新增：净值曲线记录
    # ═══════════════════════════════════════════
    def record_nav(self, account_id: str):
        """记录账户净值"""
        acc = self.accounts.get(account_id)
        if acc:
            acc.nav_history.append({
                "timestamp": datetime.datetime.now().isoformat(),
                "nav": acc.nav,
                "total_assets": acc.total_assets
            })

    # ═══════════════════════════════════════════
    # 新增：每日结算
    # ═══════════════════════════════════════════
    def daily_settlement(self):
        """每日结算：更新T+1、记录净值、清理过期订单"""
        self.update_t1()
        for account_id in self.accounts:
            self.record_nav(account_id)
        # 清理当日有效但未成交的订单
        self.engine.pending_orders = [
            o for o in self.engine.pending_orders 
            if o.validity == "gtc"
        ]

    # ═══════════════════════════════════════════
    # 新增：数据导出
    # ═══════════════════════════════════════════
    def export_account_data(self, account_id: str) -> dict:
        """导出账户完整数据"""
        acc = self.accounts.get(account_id)
        if not acc:
            return {}
        
        return {
            "account": acc.__dict__,
            "performance": self.get_performance(account_id),
            "trades": acc.trades,
            "nav_history": acc.nav_history
        }
    
    def import_account_data(self, data: dict) -> SimAccount:
        """导入账户数据"""
        acc = SimAccount(**data.get("account", {}))
        self.accounts[acc.account_id] = acc
        return acc
