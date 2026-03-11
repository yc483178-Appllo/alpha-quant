"""
Kimi Claw V7.0 模拟交易系统实现

完整的模拟交易引擎，包括A股规则、成交模拟、绩效分析和毕业评估
"""

from abc import ABC
from dataclasses import dataclass, field
from datetime import datetime, timedelta, date
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import logging
import json
from pathlib import Path
import numpy as np
from collections import defaultdict

try:
    from config.settings import get_settings
    from utils.logger import get_logger
except ImportError:
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from config.settings import get_settings
    from utils.logger import get_logger

logger = get_logger(__name__)


class GraduationLevel(Enum):
    """毕业等级"""
    SIMULATION = "SIMULATION"         # 模拟交易
    LEVEL_10_PERCENT = "LEVEL_10"     # 10%真实资金
    LEVEL_30_PERCENT = "LEVEL_30"     # 30%真实资金
    FULL = "FULL"                     # 全额真实资金


class OrderStatus(Enum):
    """订单状态"""
    PENDING = "PENDING"               # 待处理
    FILLED = "FILLED"                 # 已成交
    PARTIAL = "PARTIAL"               # 部分成交
    CANCELED = "CANCELED"             # 已取消
    REJECTED = "REJECTED"             # 被拒绝


class PerformanceMetrics(Enum):
    """绩效指标"""
    SHARPE_RATIO = "sharpe_ratio"     # Sharpe比率 (目标>1.0)
    MAX_DRAWDOWN = "max_drawdown"     # 最大回撤 (目标<10%)
    WIN_RATE = "win_rate"             # 胜率
    TOTAL_RETURN = "total_return"     # 累计收益
    DAYS_TRADING = "days_trading"     # 交易天数


@dataclass
class PaperOrder:
    """模拟订单"""
    order_id: str                     # 订单ID
    symbol: str                       # 标的代码
    side: str                         # 买卖方向 (BUY/SELL)
    quantity: int                     # 订单数量
    limit_price: float                # 限价

    # 成交信息
    filled_quantity: int = 0          # 成交数量
    avg_price: float = 0.0            # 平均价格
    status: OrderStatus = OrderStatus.PENDING

    # A股规则
    is_limit_up: bool = False         # 是否涨停
    is_limit_down: bool = False       # 是否跌停

    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    filled_at: Optional[datetime] = None
    settlement_date: Optional[date] = None  # T+1结算日期


@dataclass
class PaperPosition:
    """模拟持仓"""
    symbol: str                       # 标的代码
    quantity: int                     # 持仓数量
    available_quantity: int = 0       # 可用数量 (T+1)
    cost_price: float = 0.0           # 成本价
    current_price: float = 0.0        # 当前价格

    # 持仓统计
    value: float = 0.0                # 市值
    profit_loss: float = 0.0          # 浮动收益
    profit_loss_pct: float = 0.0      # 浮动收益率

    # 时间
    opened_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)


@dataclass
class PaperAccount:
    """模拟账户"""
    account_id: str                   # 账户ID
    name: str                         # 账户名称
    initial_capital: float            # 初始资金

    # 资金情况
    cash: float = 0.0                 # 现金
    frozen_cash: float = 0.0          # 冻结现金
    market_value: float = 0.0         # 持仓市值
    nav: float = 0.0                  # 净资产价值

    # 持仓
    positions: Dict[str, PaperPosition] = field(default_factory=dict)

    # 订单历史
    orders: List[PaperOrder] = field(default_factory=list)
    closed_orders: List[PaperOrder] = field(default_factory=list)

    # 绩效指标
    daily_nav: List[float] = field(default_factory=list)
    nav_history: Dict[str, float] = field(default_factory=dict)  # {date: nav}

    sharpe_ratio: float = 0.0         # Sharpe比率
    max_drawdown: float = 0.0         # 最大回撤
    win_rate: float = 0.0             # 胜率
    total_return: float = 0.0         # 累计收益

    # 毕业信息
    graduation_level: GraduationLevel = GraduationLevel.SIMULATION
    promotion_date: Optional[datetime] = None

    # 时间
    created_at: datetime = field(default_factory=datetime.now)
    last_updated: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """初始化后设置现金"""
        self.cash = self.initial_capital
        self.nav = self.initial_capital


class PaperTradingEngine:
    """模拟交易引擎 V6.1"""

    def __init__(self, settings: Optional[Any] = None):
        """
        初始化模拟交易引擎

        Args:
            settings: 配置对象
        """
        self.settings = settings or get_settings()
        self.logger = logger

        # 账户管理
        self.accounts: Dict[str, PaperAccount] = {}

        # 订单ID生成
        self.next_order_id = 1

        # 市场数据缓存
        self.market_data: Dict[str, Dict[str, float]] = {}

        # 成交记录
        self.trades: Dict[str, List[Dict]] = defaultdict(list)

    def create_account(self, account_id: str, name: str, initial_capital: float) -> bool:
        """
        创建模拟账户

        Args:
            account_id: 账户ID
            name: 账户名称
            initial_capital: 初始资金

        Returns:
            bool: 是否创建成功
        """
        try:
            if account_id in self.accounts:
                self.logger.warning(f"账户已存在: {account_id}")
                return False

            account = PaperAccount(
                account_id=account_id,
                name=name,
                initial_capital=initial_capital
            )

            self.accounts[account_id] = account
            self.logger.info(f"模拟账户已创建: {account_id} 初始资金={initial_capital:.2f}")

            return True

        except Exception as e:
            self.logger.error(f"创建账户失败: {str(e)}")
            return False

    def delete_account(self, account_id: str) -> bool:
        """删除模拟账户"""
        try:
            if account_id not in self.accounts:
                return False

            del self.accounts[account_id]
            self.logger.info(f"模拟账户已删除: {account_id}")

            return True

        except Exception as e:
            self.logger.error(f"删除账户失败: {str(e)}")
            return False

    def get_account(self, account_id: str) -> Optional[PaperAccount]:
        """获取账户"""
        return self.accounts.get(account_id)

    def get_accounts_list(self) -> List[PaperAccount]:
        """获取所有账户列表"""
        return list(self.accounts.values())

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
        try:
            # 获取账户
            account = self.accounts.get(account_id)
            if not account:
                return False, "账户不存在"

            # A股规则验证
            # 1. 最小下单100股
            if quantity < 100:
                return False, "订单数量最少100股"

            # 2. 必须是100的倍数
            if quantity % 100 != 0:
                return False, "订单数量必须是100的倍数"

            # 3. 检查涨跌停限制
            market_data = self.market_data.get(symbol, {})
            current_price = market_data.get('price', limit_price)
            limit_up = market_data.get('limit_up', current_price * 1.1)
            limit_down = market_data.get('limit_down', current_price * 0.9)

            is_limit_up = False
            is_limit_down = False

            if side == "BUY" and limit_price > limit_up * 1.001:
                # 买入超过涨停价
                is_limit_up = True

            if side == "SELL" and limit_price < limit_down * 0.999:
                # 卖出低于跌停价
                is_limit_down = True

            # 生成订单ID
            order_id = f"PT_{account_id}_{self.next_order_id}_{int(datetime.now().timestamp() * 1000)}"
            self.next_order_id += 1

            # 创建订单
            order = PaperOrder(
                order_id=order_id,
                symbol=symbol,
                side=side,
                quantity=quantity,
                limit_price=limit_price,
                is_limit_up=is_limit_up,
                is_limit_down=is_limit_down
            )

            # 风险检查：检查资金是否足够（买入时）
            if side == "BUY":
                required_cash = quantity * limit_price

                if required_cash > account.cash:
                    return False, f"资金不足，需要{required_cash:.2f}，现有{account.cash:.2f}"

                # 冻结资金
                account.frozen_cash += required_cash

            # 检查持仓是否足够（卖出时）
            elif side == "SELL":
                position = account.positions.get(symbol)

                if not position or position.available_quantity < quantity:
                    available = position.available_quantity if position else 0
                    return False, f"持仓不足，需要{quantity}，可用{available}"

            # 立即成交
            self._fill_order(account, order, current_price)

            account.orders.append(order)

            # 更新账户
            self._update_account(account)

            self.logger.info(f"订单已成交: {order_id} {symbol} {side} {order.filled_quantity}@{order.avg_price:.2f}")

            return True, order_id

        except Exception as e:
            self.logger.error(f"提交订单失败: {str(e)}")
            return False, str(e)

    def _fill_order(self, account: PaperAccount, order: PaperOrder, market_price: float) -> None:
        """
        成交订单（模拟高保真成交）

        Args:
            account: 账户
            order: 订单
            market_price: 市场价格
        """
        # 计算成交价格（考虑滑点）
        # 买入时通常成交价稍高，卖出时稍低
        import random

        if order.side == "BUY":
            # 买入滑点 0-0.2%
            slippage = random.uniform(0, 0.002)
            fill_price = market_price * (1 + slippage)
        else:
            # 卖出滑点 0-0.2%
            slippage = random.uniform(0, 0.002)
            fill_price = market_price * (1 - slippage)

        order.filled_quantity = order.quantity
        order.avg_price = fill_price
        order.status = OrderStatus.FILLED
        order.filled_at = datetime.now()

        # 计算T+1结算日期
        today = datetime.now().date()
        # 模拟下一个交易日为明天
        order.settlement_date = today + timedelta(days=1)

        # 更新账户和持仓
        if order.side == "BUY":
            # 买入：现金扣除，持仓增加
            cost = order.filled_quantity * fill_price

            account.cash -= cost
            account.frozen_cash -= cost

            # 更新或创建持仓
            if order.symbol not in account.positions:
                account.positions[order.symbol] = PaperPosition(symbol=order.symbol)

            position = account.positions[order.symbol]

            # 更新成本价 (加权平均)
            if position.quantity > 0:
                old_cost = position.quantity * position.cost_price
                new_cost = order.filled_quantity * fill_price
                position.quantity += order.filled_quantity
                position.cost_price = (old_cost + new_cost) / position.quantity
            else:
                position.quantity = order.filled_quantity
                position.cost_price = fill_price

            position.last_updated = datetime.now()

        else:
            # 卖出：现金增加，持仓减少（T+1有效）
            proceeds = order.filled_quantity * fill_price

            # T+1规则：卖出的资金下一个交易日才能使用
            account.frozen_cash += proceeds

            # 更新持仓
            position = account.positions.get(order.symbol)

            if position:
                position.quantity -= order.filled_quantity
                if position.quantity <= 0:
                    # 完全卖出，删除持仓
                    del account.positions[order.symbol]
                position.last_updated = datetime.now()

        # 记录成交
        self.trades[order.symbol].append({
            'time': order.filled_at,
            'side': order.side,
            'quantity': order.filled_quantity,
            'price': order.avg_price,
            'account_id': account.account_id,
        })

    def cancel_order(self, account_id: str, order_id: str) -> Tuple[bool, str]:
        """
        取消订单

        Args:
            account_id: 账户ID
            order_id: 订单ID

        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        try:
            account = self.accounts.get(account_id)
            if not account:
                return False, "账户不存在"

            # 查找订单
            order = None
            for o in account.orders:
                if o.order_id == order_id:
                    order = o
                    break

            if not order:
                return False, "订单不存在"

            # 只有待处理的订单才能取消
            if order.status != OrderStatus.PENDING:
                return False, f"订单状态{order.status.value}无法取消"

            order.status = OrderStatus.CANCELED

            # 解冻资金
            if order.side == "BUY":
                account.frozen_cash -= order.quantity * order.limit_price

            self.logger.info(f"订单已取消: {order_id}")

            return True, "取消成功"

        except Exception as e:
            self.logger.error(f"取消订单失败: {str(e)}")
            return False, str(e)

    def get_orders(self, account_id: str, symbol: Optional[str] = None) -> List[PaperOrder]:
        """
        获取订单列表

        Args:
            account_id: 账户ID
            symbol: 标的代码（可选）

        Returns:
            List[PaperOrder]: 订单列表
        """
        account = self.accounts.get(account_id)
        if not account:
            return []

        orders = account.orders

        if symbol:
            orders = [o for o in orders if o.symbol == symbol]

        return orders

    def get_trades(self, account_id: str, symbol: Optional[str] = None) -> List[Dict]:
        """获取成交记录"""
        trades = []

        if symbol:
            trades = self.trades.get(symbol, [])
        else:
            for symbol_trades in self.trades.values():
                trades.extend(symbol_trades)

        # 过滤账户
        trades = [t for t in trades if t.get('account_id') == account_id]

        return trades

    def get_positions(self, account_id: str) -> Dict[str, PaperPosition]:
        """获取持仓"""
        account = self.accounts.get(account_id)
        if not account:
            return {}

        return account.positions

    def update_market_price(self, symbol: str, price: float, limit_up: Optional[float] = None,
                           limit_down: Optional[float] = None, volume: float = 0.0) -> None:
        """
        更新市场价格

        Args:
            symbol: 标的代码
            price: 当前价格
            limit_up: 涨停价
            limit_down: 跌停价
            volume: 成交量
        """
        self.market_data[symbol] = {
            'price': price,
            'limit_up': limit_up or price * 1.1,
            'limit_down': limit_down or price * 0.9,
            'volume': volume,
            'updated_at': datetime.now(),
        }

        # 更新所有账户的持仓市值
        for account in self.accounts.values():
            if symbol in account.positions:
                position = account.positions[symbol]
                position.current_price = price
                position.value = position.quantity * price
                position.profit_loss = position.value - position.quantity * position.cost_price
                position.profit_loss_pct = position.profit_loss / (position.quantity * position.cost_price) if position.cost_price > 0 else 0

    def daily_settlement(self, account_id: str, settlement_date: date) -> bool:
        """
        日终结算（T+1）

        Args:
            account_id: 账户ID
            settlement_date: 结算日期

        Returns:
            bool: 是否结算成功
        """
        try:
            account = self.accounts.get(account_id)
            if not account:
                return False

            # 处理T+1资金可用
            for order in account.orders:
                if order.settlement_date == settlement_date and order.side == "SELL":
                    # 卖出资金可用
                    proceeds = order.filled_quantity * order.avg_price
                    account.frozen_cash -= proceeds
                    account.cash += proceeds

            # 计算账户NAV
            self._calculate_nav(account)

            # 记录NAV历史
            account.nav_history[settlement_date.isoformat()] = account.nav

            # 记录日NAV
            account.daily_nav.append(account.nav)

            self.logger.info(f"账户{account_id}已结算: NAV={account.nav:.2f}")

            return True

        except Exception as e:
            self.logger.error(f"结算失败: {str(e)}")
            return False

    def _calculate_nav(self, account: PaperAccount) -> None:
        """
        计算账户净资产价值

        Args:
            account: 账户
        """
        # NAV = 现金 + 持仓市值
        market_value = sum(p.value for p in account.positions.values())
        account.nav = account.cash + market_value
        account.market_value = market_value

    def _update_account(self, account: PaperAccount) -> None:
        """更新账户信息"""
        self._calculate_nav(account)
        account.last_updated = datetime.now()

    def calculate_performance(self, account_id: str) -> Dict[str, float]:
        """
        计算绩效指标

        Args:
            account_id: 账户ID

        Returns:
            Dict[str, float]: 绩效指标
        """
        account = self.accounts.get(account_id)
        if not account or not account.daily_nav:
            return {
                'sharpe_ratio': 0.0,
                'max_drawdown': 0.0,
                'win_rate': 0.0,
                'total_return': 0.0,
                'days_trading': 0,
            }

        # 计算日收益率
        daily_nav_array = np.array(account.daily_nav)
        daily_returns = np.diff(daily_nav_array) / daily_nav_array[:-1]

        # Sharpe比率 (假设无风险率为3%)
        annual_returns = daily_returns.mean() * 252
        annual_volatility = daily_returns.std() * np.sqrt(252)
        sharpe_ratio = (annual_returns - 0.03) / annual_volatility if annual_volatility > 0 else 0

        # 最大回撤
        cumulative_returns = np.cumprod(1 + daily_returns)
        running_max = np.maximum.accumulate(cumulative_returns)
        drawdowns = (cumulative_returns - running_max) / running_max
        max_drawdown = np.abs(np.min(drawdowns)) if len(drawdowns) > 0 else 0

        # 胜率
        win_rate = np.sum(daily_returns > 0) / len(daily_returns) if len(daily_returns) > 0 else 0

        # 累计收益
        total_return = (account.nav - account.initial_capital) / account.initial_capital

        account.sharpe_ratio = float(sharpe_ratio)
        account.max_drawdown = float(max_drawdown)
        account.win_rate = float(win_rate)
        account.total_return = float(total_return)

        return {
            'sharpe_ratio': float(sharpe_ratio),
            'max_drawdown': float(max_drawdown),
            'win_rate': float(win_rate),
            'total_return': float(total_return),
            'days_trading': len(account.daily_nav),
        }

    def take_snapshot(self, account_id: str) -> Dict[str, Any]:
        """
        获取账户快照

        Args:
            account_id: 账户ID

        Returns:
            Dict[str, Any]: 账户快照
        """
        account = self.accounts.get(account_id)
        if not account:
            return {}

        self.calculate_performance(account_id)

        return {
            'account_id': account.account_id,
            'name': account.name,
            'cash': account.cash,
            'market_value': account.market_value,
            'nav': account.nav,
            'total_return': account.total_return,
            'sharpe_ratio': account.sharpe_ratio,
            'max_drawdown': account.max_drawdown,
            'win_rate': account.win_rate,
            'positions': {
                symbol: {
                    'quantity': pos.quantity,
                    'cost_price': pos.cost_price,
                    'current_price': pos.current_price,
                    'value': pos.value,
                    'profit_loss': pos.profit_loss,
                    'profit_loss_pct': pos.profit_loss_pct,
                }
                for symbol, pos in account.positions.items()
            }
        }

    def get_nav_curve(self, account_id: str) -> Dict[str, float]:
        """获取NAV曲线"""
        account = self.accounts.get(account_id)
        if not account:
            return {}

        return account.nav_history


class GraduationEvaluator:
    """毕业评估系统 - Bayesian A/B测试"""

    def __init__(self, engine: PaperTradingEngine):
        """
        初始化毕业评估器

        Args:
            engine: 模拟交易引擎
        """
        self.engine = engine
        self.logger = logger

        # 毕业标准
        self.min_sharpe_ratio = 1.0
        self.max_drawdown = 0.1
        self.min_trading_days = 30
        self.confidence_level = 0.95

    def evaluate_graduation(self, account_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        评估是否可以毕业

        Args:
            account_id: 账户ID

        Returns:
            Tuple[bool, Dict]: (是否通过, 评估报告)
        """
        account = self.engine.get_account(account_id)
        if not account:
            return False, {}

        # 计算绩效
        performance = self.engine.calculate_performance(account_id)

        # 评估各项指标
        passed_metrics = {
            'sharpe_ratio': performance['sharpe_ratio'] > self.min_sharpe_ratio,
            'max_drawdown': performance['max_drawdown'] < self.max_drawdown,
            'days_trading': performance['days_trading'] >= self.min_trading_days,
        }

        # 计算通过概率（Bayesian）
        passed_count = sum(1 for v in passed_metrics.values() if v)
        probability = passed_count / len(passed_metrics)

        # 判断是否通过 (所有指标都通过，且信心度>=95%)
        is_passed = all(passed_metrics.values()) and probability >= self.confidence_level

        report = {
            'account_id': account_id,
            'passed': is_passed,
            'probability': probability,
            'confidence_level': self.confidence_level,
            'metrics': {
                'sharpe_ratio': {
                    'value': performance['sharpe_ratio'],
                    'threshold': self.min_sharpe_ratio,
                    'passed': passed_metrics['sharpe_ratio'],
                },
                'max_drawdown': {
                    'value': performance['max_drawdown'],
                    'threshold': self.max_drawdown,
                    'passed': passed_metrics['max_drawdown'],
                },
                'days_trading': {
                    'value': performance['days_trading'],
                    'threshold': self.min_trading_days,
                    'passed': passed_metrics['days_trading'],
                },
            }
        }

        return is_passed, report

    def recommend_next_level(self, account_id: str) -> GraduationLevel:
        """
        推荐下一个毕业等级

        Args:
            account_id: 账户ID

        Returns:
            GraduationLevel: 推荐的毕业等级
        """
        account = self.engine.get_account(account_id)
        if not account:
            return GraduationLevel.SIMULATION

        current_level = account.graduation_level

        # 毕业流程：模拟 -> 10% -> 30% -> 全额
        graduation_path = [
            GraduationLevel.SIMULATION,
            GraduationLevel.LEVEL_10_PERCENT,
            GraduationLevel.LEVEL_30_PERCENT,
            GraduationLevel.FULL,
        ]

        # 评估是否通过
        is_passed, _ = self.evaluate_graduation(account_id)

        if not is_passed:
            return current_level

        # 获取当前等级的索引
        current_index = graduation_path.index(current_level)

        # 推荐下一个等级（如果有的话）
        if current_index < len(graduation_path) - 1:
            return graduation_path[current_index + 1]
        else:
            return GraduationLevel.FULL

    def promote_account(self, account_id: str) -> Tuple[bool, str]:
        """
        将账户升级到下一个等级

        Args:
            account_id: 账户ID

        Returns:
            Tuple[bool, str]: (是否成功, 消息)
        """
        try:
            # 评估
            is_passed, report = self.evaluate_graduation(account_id)

            if not is_passed:
                return False, f"毕业评估失败: {report}"

            account = self.engine.get_account(account_id)
            if not account:
                return False, "账户不存在"

            # 获取下一个等级
            next_level = self.recommend_next_level(account_id)

            if next_level == account.graduation_level:
                return False, "已达到最高等级"

            # 升级账户
            old_level = account.graduation_level
            account.graduation_level = next_level
            account.promotion_date = datetime.now()

            self.logger.info(f"账户{account_id}已升级: {old_level.value} -> {next_level.value}")

            return True, f"已升级到{next_level.value}"

        except Exception as e:
            self.logger.error(f"升级账户失败: {str(e)}")
            return False, str(e)


class PaperVsLiveComparer:
    """模拟vs真实交易对比分析"""

    def __init__(self, paper_engine: PaperTradingEngine):
        """
        初始化对比分析器

        Args:
            paper_engine: 模拟交易引擎
        """
        self.paper_engine = paper_engine
        self.logger = logger
        self.live_accounts: Dict[str, Dict[str, Any]] = {}

    def register_live_account(self, live_account_id: str, paper_account_id: str,
                             live_data: Dict[str, Any]) -> bool:
        """
        注册真实账户用于对比

        Args:
            live_account_id: 真实账户ID
            paper_account_id: 对应的模拟账户ID
            live_data: 真实账户数据

        Returns:
            bool: 是否注册成功
        """
        try:
            paper_account = self.paper_engine.get_account(paper_account_id)
            if not paper_account:
                return False

            self.live_accounts[live_account_id] = {
                'paper_account_id': paper_account_id,
                'live_data': live_data,
                'comparison_history': [],
            }

            return True

        except Exception as e:
            self.logger.error(f"注册真实账户失败: {str(e)}")
            return False

    def compare_performance(self, live_account_id: str) -> Dict[str, Any]:
        """
        对比模拟和真实账户的绩效

        Args:
            live_account_id: 真实账户ID

        Returns:
            Dict[str, Any]: 对比结果
        """
        try:
            if live_account_id not in self.live_accounts:
                return {}

            account_mapping = self.live_accounts[live_account_id]
            paper_account_id = account_mapping['paper_account_id']
            live_data = account_mapping['live_data']

            # 获取模拟账户的绩效
            paper_snapshot = self.paper_engine.take_snapshot(paper_account_id)
            paper_performance = self.paper_engine.calculate_performance(paper_account_id)

            # 对比
            comparison = {
                'live_account_id': live_account_id,
                'paper_account_id': paper_account_id,
                'paper_nav': paper_snapshot.get('nav', 0),
                'live_nav': live_data.get('nav', 0),
                'nav_diff': paper_snapshot.get('nav', 0) - live_data.get('nav', 0),
                'paper_return': paper_performance.get('total_return', 0),
                'live_return': live_data.get('total_return', 0),
                'return_diff': paper_performance.get('total_return', 0) - live_data.get('total_return', 0),
                'paper_sharpe': paper_performance.get('sharpe_ratio', 0),
                'live_sharpe': live_data.get('sharpe_ratio', 0),
                'paper_max_dd': paper_performance.get('max_drawdown', 0),
                'live_max_dd': live_data.get('max_drawdown', 0),
                'comparison_date': datetime.now().isoformat(),
            }

            # 记录对比历史
            account_mapping['comparison_history'].append(comparison)

            return comparison

        except Exception as e:
            self.logger.error(f"绩效对比失败: {str(e)}")
            return {}

    def get_comparison_summary(self, live_account_id: str) -> Dict[str, Any]:
        """获取对比总结"""
        if live_account_id not in self.live_accounts:
            return {}

        account_mapping = self.live_accounts[live_account_id]
        history = account_mapping['comparison_history']

        if not history:
            return {}

        # 计算平均差值
        nav_diffs = [h['nav_diff'] for h in history]
        return_diffs = [h['return_diff'] for h in history]

        return {
            'live_account_id': live_account_id,
            'total_comparisons': len(history),
            'avg_nav_diff': np.mean(nav_diffs) if nav_diffs else 0,
            'avg_return_diff': np.mean(return_diffs) if return_diffs else 0,
            'latest_comparison': history[-1] if history else {},
        }

    def suggest_live_promotion(self, live_account_id: str) -> Tuple[bool, str]:
        """
        建议是否应该提升到真实交易

        Args:
            live_account_id: 真实账户ID

        Returns:
            Tuple[bool, str]: (是否建议提升, 理由)
        """
        summary = self.get_comparison_summary(live_account_id)

        if not summary:
            return False, "没有足够的对比数据"

        avg_return_diff = abs(summary.get('avg_return_diff', 0))

        # 如果模拟和真实的收益差异在5%以内，建议提升
        if avg_return_diff < 0.05:
            return True, "模拟和真实交易表现接近，建议提升"
        else:
            return False, f"收益差异{avg_return_diff*100:.2f}%超过阈值(5%)，继续观察"
