"""
Professional Backtest Engine Implementation
==============================================

包含以下核心组件：
1. AlmgrenChrissImpact - 永久性和临时性市场冲击模型
2. DynamicSlippage - 基于订单簿深度的动态滑点模型
3. BiasDetector - 检测前瞻偏差、幸存者偏差、过拟合
4. AShareRules - A股交易规则引擎
5. ProfessionalBacktester - Walk Forward Analysis分析框架

Author: Kimi Claw Team
Version: 7.0.0
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import logging
import warnings
from datetime import datetime, timedelta
import json

# 假设配置模块
try:
    from config.settings import CONFIG
except ImportError:
    CONFIG = {}

try:
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """市场制度枚举"""
    BULL = "bull"
    BEAR = "bear"
    SIDEWAYS = "sideways"


@dataclass
class ExecutionCost:
    """执行成本数据类"""
    permanent_impact: float = 0.0
    temporary_impact: float = 0.0
    slippage: float = 0.0
    commission: float = 0.0
    tax: float = 0.0
    transfer_fee: float = 0.0

    @property
    def total(self) -> float:
        """总成本"""
        return (self.permanent_impact + self.temporary_impact +
                self.slippage + self.commission + self.tax + self.transfer_fee)


@dataclass
class WFAReport:
    """Walk Forward Analysis报告"""
    strategy_name: str
    total_trades: int = 0
    in_sample_sharpe: float = 0.0
    out_sample_sharpe: float = 0.0
    sharpe_gap: float = 0.0
    in_sample_calmar: float = 0.0
    out_sample_calmar: float = 0.0
    calmar_gap: float = 0.0
    in_sample_max_dd: float = 0.0
    out_sample_max_dd: float = 0.0
    in_sample_win_rate: float = 0.0
    out_sample_win_rate: float = 0.0
    in_sample_turnover: float = 0.0
    out_sample_turnover: float = 0.0
    bias_flags: List[str] = field(default_factory=list)
    metrics_history: Dict[str, List[float]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'strategy_name': self.strategy_name,
            'total_trades': self.total_trades,
            'in_sample_sharpe': self.in_sample_sharpe,
            'out_sample_sharpe': self.out_sample_sharpe,
            'sharpe_gap': self.sharpe_gap,
            'in_sample_calmar': self.in_sample_calmar,
            'out_sample_calmar': self.out_sample_calmar,
            'calmar_gap': self.calmar_gap,
            'in_sample_max_dd': self.in_sample_max_dd,
            'out_sample_max_dd': self.out_sample_max_dd,
            'in_sample_win_rate': self.in_sample_win_rate,
            'out_sample_win_rate': self.out_sample_win_rate,
            'in_sample_turnover': self.in_sample_turnover,
            'out_sample_turnover': self.out_sample_turnover,
            'bias_flags': self.bias_flags,
        }


class AlmgrenChrissImpact:
    """
    Almgren-Chriss市场冲击模型

    参考论文：Almgren & Chriss (2000)
    "Optimal execution of portfolio transactions"

    Attributes:
        permanent_impact: 永久性冲击系数（默认0.1）
        temporary_impact: 临时性冲击系数（默认0.3）
        volatility_scale: 是否按波动率缩放
    """

    def __init__(
        self,
        permanent_impact: float = 0.1,
        temporary_impact: float = 0.3,
        volatility_scale: bool = True
    ):
        """
        初始化Almgren-Chriss模型

        Args:
            permanent_impact: 永久性冲击系数
            temporary_impact: 临时性冲击系数
            volatility_scale: 是否按波动率缩放
        """
        self.permanent_impact = permanent_impact
        self.temporary_impact = temporary_impact
        self.volatility_scale = volatility_scale
        logger.info(
            f"初始化AlmgrenChrissImpact: "
            f"permanent={permanent_impact}, temporary={temporary_impact}"
        )

    def calculate_impact(
        self,
        order_size: float,
        adv: float,  # Average Daily Volume
        volatility: float,
        mid_price: float
    ) -> Tuple[float, float]:
        """
        计算永久性和临时性冲击

        Args:
            order_size: 订单大小（金额或股数）
            adv: 日均成交量
            volatility: 波动率
            mid_price: 中间价

        Returns:
            (permanent_impact_bp, temporary_impact_bp): 以基点计
        """
        try:
            # 避免除零
            if adv <= 0 or mid_price <= 0:
                logger.warning(f"异常的ADV或中间价: adv={adv}, mid_price={mid_price}")
                return 0.0, 0.0

            # 参与度 (participation rate)
            participation_rate = order_size / adv

            # 永久性冲击：取决于参与度
            permanent_bp = self.permanent_impact * participation_rate * 10000

            # 临时性冲击：与成交量和波动率相关
            if self.volatility_scale:
                temporary_bp = (self.temporary_impact *
                               participation_rate * volatility * 10000)
            else:
                temporary_bp = self.temporary_impact * participation_rate * 10000

            return permanent_bp, temporary_bp

        except Exception as e:
            logger.error(f"计算冲击失败: {e}", exc_info=True)
            return 0.0, 0.0

    def get_execution_cost(
        self,
        order_size: float,
        adv: float,
        volatility: float,
        mid_price: float,
        commission: float = 0.0003
    ) -> ExecutionCost:
        """
        获取完整的执行成本

        Args:
            order_size: 订单大小
            adv: 日均成交量
            volatility: 波动率
            mid_price: 中间价
            commission: 佣金率

        Returns:
            ExecutionCost对象
        """
        perm_bp, temp_bp = self.calculate_impact(
            order_size, adv, volatility, mid_price
        )

        cost = ExecutionCost(
            permanent_impact=perm_bp / 10000,
            temporary_impact=temp_bp / 10000,
            commission=commission
        )

        return cost


class DynamicSlippage:
    """
    动态滑点模型 - 基于订单簿深度的5层模型

    根据订单簿各档的流动性深度动态计算滑点，反映真实的执行成本。
    """

    def __init__(self, depth_levels: int = 5):
        """
        初始化动态滑点模型

        Args:
            depth_levels: 订单簿深度级数（默认5层）
        """
        self.depth_levels = depth_levels
        logger.info(f"初始化DynamicSlippage: depth_levels={depth_levels}")

    def calculate_slippage(
        self,
        order_size: float,
        bid_volumes: List[float],
        ask_volumes: List[float],
        bid_prices: List[float],
        ask_prices: List[float],
        mid_price: float,
        order_side: str = 'BUY'
    ) -> float:
        """
        基于订单簿计算滑点

        Args:
            order_size: 订单大小
            bid_volumes: 买方各档数量
            ask_volumes: 卖方各档数量
            bid_prices: 买方各档价格
            ask_prices: 卖方各档价格
            mid_price: 中间价
            order_side: 订单方向 'BUY' 或 'SELL'

        Returns:
            滑点（以比例计）
        """
        try:
            if order_side == 'BUY':
                # 买单滑点：从卖方订单簿消耗
                return self._calculate_buy_slippage(
                    order_size, ask_volumes, ask_prices, mid_price
                )
            else:
                # 卖单滑点：从买方订单簿消耗
                return self._calculate_sell_slippage(
                    order_size, bid_volumes, bid_prices, mid_price
                )
        except Exception as e:
            logger.error(f"计算滑点失败: {e}", exc_info=True)
            return 0.0

    def _calculate_buy_slippage(
        self,
        order_size: float,
        ask_volumes: List[float],
        ask_prices: List[float],
        mid_price: float
    ) -> float:
        """计算买入滑点"""
        cumulative_vol = 0.0
        weighted_price = mid_price

        for i in range(min(self.depth_levels, len(ask_volumes))):
            if cumulative_vol >= order_size:
                break
            vol_to_fill = min(ask_volumes[i], order_size - cumulative_vol)
            weighted_price += (ask_prices[i] - mid_price) * (vol_to_fill / order_size)
            cumulative_vol += vol_to_fill

        slippage = (weighted_price - mid_price) / mid_price
        return max(slippage, 0.0)

    def _calculate_sell_slippage(
        self,
        order_size: float,
        bid_volumes: List[float],
        bid_prices: List[float],
        mid_price: float
    ) -> float:
        """计算卖出滑点"""
        cumulative_vol = 0.0
        weighted_price = mid_price

        for i in range(min(self.depth_levels, len(bid_volumes))):
            if cumulative_vol >= order_size:
                break
            vol_to_fill = min(bid_volumes[i], order_size - cumulative_vol)
            weighted_price += (bid_prices[i] - mid_price) * (vol_to_fill / order_size)
            cumulative_vol += vol_to_fill

        slippage = (mid_price - weighted_price) / mid_price
        return max(slippage, 0.0)


class BiasDetector:
    """
    偏差检测器 - 检测回测中的常见偏差

    检测项目：
    1. 前瞻偏差（Lookahead Bias）
    2. 幸存者偏差（Survivorship Bias）
    3. 过拟合（Overfitting）
    """

    def __init__(self):
        """初始化偏差检测器"""
        logger.info("初始化BiasDetector")

    def check_lookahead(
        self,
        signal_dates: List[pd.Timestamp],
        data_available_dates: List[pd.Timestamp]
    ) -> Tuple[bool, str]:
        """
        检查前瞻偏差

        前瞻偏差：使用了未来信息来生成历史信号

        Args:
            signal_dates: 信号生成日期
            data_available_dates: 数据可用日期

        Returns:
            (has_bias, description)
        """
        try:
            signal_set = set(signal_dates)
            available_set = set(data_available_dates)

            # 检查是否有信号在数据可用之前
            future_signals = signal_set - available_set

            if future_signals:
                msg = f"检测到前瞻偏差: {len(future_signals)}个信号使用了未来数据"
                logger.warning(msg)
                return True, msg

            return False, "未检测到前瞻偏差"

        except Exception as e:
            logger.error(f"检查前瞻偏差失败: {e}", exc_info=True)
            return False, f"检查失败: {str(e)}"

    def check_survivorship(
        self,
        backtest_universe: set,
        current_universe: set
    ) -> Tuple[bool, str]:
        """
        检查幸存者偏差

        幸存者偏差：只用现存股票进行回测，忽略退市股票

        Args:
            backtest_universe: 回测中使用的股票集合
            current_universe: 当前存活的股票集合

        Returns:
            (has_bias, description)
        """
        try:
            removed_stocks = backtest_universe - current_universe

            if removed_stocks:
                bias_ratio = len(removed_stocks) / len(backtest_universe)
                msg = f"检测到幸存者偏差: {len(removed_stocks)}只股票退市 ({bias_ratio:.1%})"
                if bias_ratio > 0.1:
                    logger.warning(msg)
                    return True, msg

            return False, "未检测到明显幸存者偏差"

        except Exception as e:
            logger.error(f"检查幸存者偏差失败: {e}", exc_info=True)
            return False, f"检查失败: {str(e)}"

    def check_overfit(
        self,
        in_sample_metrics: Dict[str, float],
        out_sample_metrics: Dict[str, float],
        threshold: float = 0.5
    ) -> Tuple[bool, str]:
        """
        检查过拟合

        使用样本内外绩效差异来判断过拟合程度

        Args:
            in_sample_metrics: 样本内指标字典
            out_sample_metrics: 样本外指标字典
            threshold: 过拟合阈值（默认50%的性能衰退）

        Returns:
            (has_overfit, description)
        """
        try:
            warnings_list = []

            # 检查Sharpe比率
            if 'sharpe' in in_sample_metrics and 'sharpe' in out_sample_metrics:
                in_sharpe = in_sample_metrics['sharpe']
                out_sharpe = out_sample_metrics['sharpe']

                if in_sharpe > 0:
                    sharpe_degradation = (in_sharpe - out_sharpe) / in_sharpe
                    if sharpe_degradation > threshold:
                        msg = f"Sharpe比率衰退: {sharpe_degradation:.1%}"
                        warnings_list.append(msg)

            # 检查赢率
            if 'win_rate' in in_sample_metrics and 'win_rate' in out_sample_metrics:
                in_wr = in_sample_metrics['win_rate']
                out_wr = out_sample_metrics['win_rate']

                if in_wr > 0:
                    wr_degradation = (in_wr - out_wr) / in_wr
                    if wr_degradation > threshold:
                        msg = f"赢率衰退: {wr_degradation:.1%}"
                        warnings_list.append(msg)

            if warnings_list:
                full_msg = "检测到过拟合迹象: " + "; ".join(warnings_list)
                logger.warning(full_msg)
                return True, full_msg

            return False, "未检测到明显过拟合"

        except Exception as e:
            logger.error(f"检查过拟合失败: {e}", exc_info=True)
            return False, f"检查失败: {str(e)}"


class AShareRules:
    """
    A股交易规则引擎

    规则集：
    - T+1交割制
    - 涨跌停限制（主板±10%, 创业板/科创板±20%, *ST±5%）
    - 最小下单单位：100股
    - 印花税：0.1% （仅卖出）
    - 佣金：0.03%
    - 过户费：0.002%
    """

    # 涨跌停限制
    LIMIT_MOVE_CONFIGS = {
        'main_board': 0.10,      # 主板 ±10%
        'gem': 0.20,             # 创业板 ±20%
        'star': 0.20,            # 科创板 ±20%
        'st': 0.05,              # *ST ±5%
    }

    # 费用配置
    STAMP_TAX = 0.001           # 印花税 0.1% （仅卖出）
    COMMISSION = 0.0003          # 佣金 0.03%
    TRANSFER_FEE = 0.00002       # 过户费 0.002%
    MIN_LOT_SIZE = 100            # 最小100股一手

    def __init__(self):
        """初始化A股规则引擎"""
        logger.info("初始化AShareRules引擎")

    def check_t_plus_one(
        self,
        position_date: pd.Timestamp,
        sell_date: pd.Timestamp
    ) -> bool:
        """
        检查T+1规则

        同日买入的股票不能在同一天卖出

        Args:
            position_date: 建仓日期
            sell_date: 卖出日期

        Returns:
            True如果允许卖出
        """
        return sell_date > position_date

    def check_limit_up_down(
        self,
        prev_close: float,
        order_price: float,
        stock_type: str = 'main_board'
    ) -> bool:
        """
        检查涨跌停

        Args:
            prev_close: 前日收盘价
            order_price: 下单价格
            stock_type: 股票类型 ('main_board', 'gem', 'star', 'st')

        Returns:
            True如果价格有效
        """
        if stock_type not in self.LIMIT_MOVE_CONFIGS:
            logger.warning(f"未知股票类型: {stock_type}")
            stock_type = 'main_board'

        limit_ratio = self.LIMIT_MOVE_CONFIGS[stock_type]
        upper_limit = prev_close * (1 + limit_ratio)
        lower_limit = prev_close * (1 - limit_ratio)

        is_valid = lower_limit <= order_price <= upper_limit

        if not is_valid:
            logger.debug(
                f"价格超出涨跌停: price={order_price}, "
                f"upper={upper_limit}, lower={lower_limit}"
            )

        return is_valid

    def check_min_lot(self, shares: int) -> bool:
        """
        检查最小下单单位

        Args:
            shares: 股数

        Returns:
            True如果符合100股倍数
        """
        is_valid = shares % self.MIN_LOT_SIZE == 0
        if not is_valid:
            logger.warning(f"下单股数不符合100股倍数: {shares}")
        return is_valid

    def calculate_costs(
        self,
        trade_amount: float,
        order_side: str = 'BUY',
        include_slippage: bool = False,
        slippage: float = 0.0
    ) -> ExecutionCost:
        """
        计算交易成本

        Args:
            trade_amount: 交易金额
            order_side: 'BUY' 或 'SELL'
            include_slippage: 是否包含滑点
            slippage: 滑点比例

        Returns:
            ExecutionCost对象
        """
        cost = ExecutionCost()

        # 佣金
        cost.commission = trade_amount * self.COMMISSION

        # 过户费
        cost.transfer_fee = trade_amount * self.TRANSFER_FEE

        # 印花税 (仅卖出)
        if order_side.upper() == 'SELL':
            cost.tax = trade_amount * self.STAMP_TAX

        # 滑点
        if include_slippage:
            cost.slippage = trade_amount * slippage

        return cost

    def apply_rules(
        self,
        order: Dict[str, Any]
    ) -> Tuple[bool, str]:
        """
        应用所有A股规则

        Args:
            order: 订单字典，包含:
                - price: 价格
                - shares: 股数
                - side: 买卖方向
                - prev_close: 前日收盘
                - stock_type: 股票类型
                - position_date: 建仓日期（如果是卖单）
                - order_date: 下单日期

        Returns:
            (is_valid, description)
        """
        try:
            # 检查涨跌停
            if not self.check_limit_up_down(
                order['prev_close'],
                order['price'],
                order.get('stock_type', 'main_board')
            ):
                return False, "价格超出涨跌停限制"

            # 检查最小手数
            if not self.check_min_lot(order['shares']):
                return False, f"下单数量不符合100股倍数: {order['shares']}"

            # 检查T+1 （仅卖单）
            if order['side'].upper() == 'SELL':
                if not self.check_t_plus_one(
                    order['position_date'],
                    order['order_date']
                ):
                    return False, "T+1规则：当日建仓无法卖出"

            return True, "通过所有规则检查"

        except Exception as e:
            logger.error(f"应用规则失败: {e}", exc_info=True)
            return False, f"规则检查异常: {str(e)}"


class ProfessionalBacktester:
    """
    专业回测引擎 - 支持Walk Forward Analysis

    Features:
    - Single backtest：单次回测
    - Walk Forward Analysis：时间序列交叉验证
    - 完整的成本模型（冲击、滑点、费用）
    - 性能指标计算（Sharpe、Calmar、最大回撤等）
    - 偏差检测
    """

    def __init__(
        self,
        use_market_impact: bool = True,
        use_slippage: bool = True,
        apply_ashare_rules: bool = True,
        risk_free_rate: float = 0.02
    ):
        """
        初始化专业回测引擎

        Args:
            use_market_impact: 是否使用市场冲击模型
            use_slippage: 是否使用滑点模型
            apply_ashare_rules: 是否应用A股规则
            risk_free_rate: 无风险收益率（默认2%）
        """
        self.use_market_impact = use_market_impact
        self.use_slippage = use_slippage
        self.apply_ashare_rules = apply_ashare_rules
        self.risk_free_rate = risk_free_rate

        self.impact_model = AlmgrenChrissImpact()
        self.slippage_model = DynamicSlippage()
        self.bias_detector = BiasDetector()
        self.ashare_rules = AShareRules()

        logger.info(
            f"初始化ProfessionalBacktester: "
            f"impact={use_market_impact}, slippage={use_slippage}, "
            f"ashare_rules={apply_ashare_rules}"
        )

    def calculate_sharpe(
        self,
        returns: np.ndarray,
        periods_per_year: int = 252
    ) -> float:
        """
        计算Sharpe比率

        Args:
            returns: 收益率序列
            periods_per_year: 年化周期数（默认252个交易日）

        Returns:
            Sharpe比率
        """
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - self.risk_free_rate / periods_per_year
        return np.sqrt(periods_per_year) * np.mean(excess_returns) / (
            np.std(excess_returns) + 1e-8
        )

    def calculate_sortino(
        self,
        returns: np.ndarray,
        periods_per_year: int = 252
    ) -> float:
        """
        计算Sortino比率

        Args:
            returns: 收益率序列
            periods_per_year: 年化周期数

        Returns:
            Sortino比率
        """
        if len(returns) < 2:
            return 0.0

        excess_returns = returns - self.risk_free_rate / periods_per_year
        downside = returns[returns < 0]

        if len(downside) == 0:
            downside_std = 0.0
        else:
            downside_std = np.std(downside)

        return np.sqrt(periods_per_year) * np.mean(excess_returns) / (
            downside_std + 1e-8
        )

    def calculate_calmar(
        self,
        cumulative_returns: np.ndarray,
        periods_per_year: int = 252
    ) -> float:
        """
        计算Calmar比率

        Args:
            cumulative_returns: 累计收益率序列
            periods_per_year: 年化周期数

        Returns:
            Calmar比率
        """
        if len(cumulative_returns) < 2:
            return 0.0

        # 计算年化收益
        total_return = cumulative_returns[-1]
        years = len(cumulative_returns) / periods_per_year
        annual_return = (1 + total_return) ** (1 / years) - 1 if years > 0 else 0

        # 计算最大回撤
        max_dd = self.calculate_max_drawdown(cumulative_returns)

        if abs(max_dd) < 1e-8:
            return 0.0

        return annual_return / abs(max_dd)

    def calculate_max_drawdown(
        self,
        cumulative_returns: np.ndarray
    ) -> float:
        """
        计算最大回撤

        Args:
            cumulative_returns: 累计收益率序列

        Returns:
            最大回撤（负值）
        """
        if len(cumulative_returns) < 2:
            return 0.0

        cummax = np.maximum.accumulate(cumulative_returns)
        drawdown = (cumulative_returns - cummax) / (cummax + 1e-8)
        return np.min(drawdown)

    def calculate_win_rate(
        self,
        returns: np.ndarray
    ) -> float:
        """
        计算赢率

        Args:
            returns: 收益率序列

        Returns:
            赢率（0-1）
        """
        if len(returns) == 0:
            return 0.0

        wins = np.sum(returns > 0)
        return wins / len(returns)

    def calculate_turnover(
        self,
        position_history: pd.DataFrame,
        price_history: pd.DataFrame
    ) -> float:
        """
        计算换手率

        Args:
            position_history: 头寸历史
            price_history: 价格历史

        Returns:
            换手率（年化）
        """
        try:
            if position_history.empty or price_history.empty:
                return 0.0

            # 计算每日交易额
            daily_trades = np.abs(position_history.diff().fillna(0)).sum(axis=1)
            daily_value = (position_history.abs() * price_history).sum(axis=1)

            # 避免除零
            daily_value = daily_value.replace(0, np.nan)
            daily_turnover = daily_trades / daily_value

            # 年化
            annual_turnover = daily_turnover.mean() * 252
            return annual_turnover

        except Exception as e:
            logger.error(f"计算换手率失败: {e}")
            return 0.0

    def run_single(
        self,
        strategy: 'Strategy',
        data: pd.DataFrame,
        initial_capital: float = 1000000.0
    ) -> Dict[str, Any]:
        """
        执行单次回测

        Args:
            strategy: 策略对象
            data: OHLCV数据
            initial_capital: 初始资金

        Returns:
            回测结果字典
        """
        logger.info(f"开始单次回测: {strategy.name}")

        try:
            # 初始化
            equity = initial_capital
            positions = {}
            trades = []
            equity_history = [initial_capital]

            # 逐日遍历
            for idx, (date, row) in enumerate(data.iterrows()):
                # 获取策略信号
                signal = strategy.generate_signal(date, data.iloc[:idx+1])

                if signal:
                    # 执行交易逻辑
                    equity = self._execute_trade(
                        signal, row, equity, positions, trades, date
                    )

                equity_history.append(equity)

            # 计算性能指标
            returns = np.diff(equity_history) / np.array(equity_history[:-1])
            cumulative_returns = np.array(equity_history) / initial_capital - 1

            metrics = {
                'total_return': cumulative_returns[-1],
                'annual_return': (1 + cumulative_returns[-1]) ** (252 / len(data)) - 1,
                'sharpe': self.calculate_sharpe(returns),
                'sortino': self.calculate_sortino(returns),
                'calmar': self.calculate_calmar(cumulative_returns),
                'max_drawdown': self.calculate_max_drawdown(cumulative_returns),
                'win_rate': self.calculate_win_rate(returns),
                'total_trades': len(trades),
            }

            logger.info(f"单次回测完成. Sharpe={metrics['sharpe']:.3f}")

            return {
                'metrics': metrics,
                'equity_history': np.array(equity_history),
                'trades': trades,
                'final_capital': equity_history[-1]
            }

        except Exception as e:
            logger.error(f"单次回测失败: {e}", exc_info=True)
            raise

    def run_wfa(
        self,
        strategy: 'Strategy',
        data: pd.DataFrame,
        train_window: int = 252,
        test_window: int = 63,
        initial_capital: float = 1000000.0
    ) -> WFAReport:
        """
        执行Walk Forward Analysis

        WFA是时间序列交叉验证方法，用于评估策略的稳健性

        Args:
            strategy: 策略对象
            data: 完整历史数据
            train_window: 训练窗口大小（默认252个交易日，1年）
            test_window: 测试窗口大小（默认63个交易日，3月）
            initial_capital: 初始资金

        Returns:
            WFAReport对象
        """
        logger.info(
            f"开始Walk Forward Analysis: {strategy.name} "
            f"(train={train_window}, test={test_window})"
        )

        report = WFAReport(strategy_name=strategy.name)
        report.metrics_history = {
            'in_sample_sharpe': [],
            'out_sample_sharpe': [],
            'gap': []
        }

        try:
            # 生成WFA窗口
            windows = []
            for i in range(train_window, len(data), test_window):
                train_end = i
                test_end = min(i + test_window, len(data))

                if test_end - train_end > 0:
                    windows.append({
                        'train': (0, train_end),
                        'test': (train_end, test_end)
                    })

            logger.info(f"共生成 {len(windows)} 个WFA窗口")

            in_sample_returns_all = []
            out_sample_returns_all = []

            # 遍历每个窗口
            for idx, window in enumerate(windows):
                logger.info(
                    f"处理窗口 {idx+1}/{len(windows)}: "
                    f"train=[{window['train'][0]}, {window['train'][1]}), "
                    f"test=[{window['test'][0]}, {window['test'][1]})"
                )

                # 样本内（训练）回测
                train_data = data.iloc[window['train'][0]:window['train'][1]]
                train_result = self.run_single(strategy, train_data, initial_capital)
                in_sample_returns = np.diff(train_result['equity_history']) / \
                                   np.array(train_result['equity_history'][:-1])
                in_sample_returns_all.extend(in_sample_returns)

                # 样本外（测试）回测
                test_data = data.iloc[window['test'][0]:window['test'][1]]
                test_result = self.run_single(strategy, test_data, initial_capital)
                out_sample_returns = np.diff(test_result['equity_history']) / \
                                    np.array(test_result['equity_history'][:-1])
                out_sample_returns_all.extend(out_sample_returns)

                # 记录差异
                in_sharpe = self.calculate_sharpe(in_sample_returns)
                out_sharpe = self.calculate_sharpe(out_sample_returns)
                gap = abs(in_sharpe - out_sharpe) / (abs(in_sharpe) + 1e-8)

                report.metrics_history['in_sample_sharpe'].append(in_sharpe)
                report.metrics_history['out_sample_sharpe'].append(out_sharpe)
                report.metrics_history['gap'].append(gap)

                report.total_trades += train_result['metrics']['total_trades']

            # 计算整体WFA指标
            in_sample_returns_all = np.array(in_sample_returns_all)
            out_sample_returns_all = np.array(out_sample_returns_all)

            cum_in_sample = np.cumprod(1 + in_sample_returns_all) - 1
            cum_out_sample = np.cumprod(1 + out_sample_returns_all) - 1

            # Sharpe对比
            report.in_sample_sharpe = self.calculate_sharpe(in_sample_returns_all)
            report.out_sample_sharpe = self.calculate_sharpe(out_sample_returns_all)
            report.sharpe_gap = abs(report.in_sample_sharpe - report.out_sample_sharpe) / (
                abs(report.in_sample_sharpe) + 1e-8
            )

            # Calmar对比
            report.in_sample_calmar = self.calculate_calmar(cum_in_sample)
            report.out_sample_calmar = self.calculate_calmar(cum_out_sample)
            report.calmar_gap = abs(report.in_sample_calmar - report.out_sample_calmar) / (
                abs(report.in_sample_calmar) + 1e-8
            )

            # 最大回撤
            report.in_sample_max_dd = self.calculate_max_drawdown(cum_in_sample)
            report.out_sample_max_dd = self.calculate_max_drawdown(cum_out_sample)

            # 赢率
            report.in_sample_win_rate = self.calculate_win_rate(in_sample_returns_all)
            report.out_sample_win_rate = self.calculate_win_rate(out_sample_returns_all)

            # 偏差检测
            metrics_dict = {
                'sharpe': report.out_sample_sharpe,
                'win_rate': report.out_sample_win_rate
            }
            has_overfit, overfit_msg = self.bias_detector.check_overfit(
                {
                    'sharpe': report.in_sample_sharpe,
                    'win_rate': report.in_sample_win_rate
                },
                metrics_dict
            )

            if has_overfit:
                report.bias_flags.append(overfit_msg)

            logger.info(
                f"WFA完成. 样本内Sharpe={report.in_sample_sharpe:.3f}, "
                f"样本外Sharpe={report.out_sample_sharpe:.3f}, "
                f"差异={report.sharpe_gap:.1%}"
            )

            return report

        except Exception as e:
            logger.error(f"Walk Forward Analysis失败: {e}", exc_info=True)
            raise

    def _execute_trade(
        self,
        signal: Dict[str, Any],
        price_row: pd.Series,
        equity: float,
        positions: Dict[str, float],
        trades: List[Dict],
        date: pd.Timestamp
    ) -> float:
        """
        执行交易逻辑

        Args:
            signal: 交易信号
            price_row: 价格行
            equity: 当前资金
            positions: 当前头寸
            trades: 交易记录
            date: 交易日期

        Returns:
            更新后的资金
        """
        try:
            symbol = signal.get('symbol')
            direction = signal.get('direction')  # 'BUY' 或 'SELL'
            quantity = signal.get('quantity', 0)
            price = signal.get('price', price_row.get('close', 0))

            if quantity <= 0:
                return equity

            # 应用A股规则
            if self.apply_ashare_rules:
                is_valid, msg = self.ashare_rules.apply_rules({
                    'price': price,
                    'shares': quantity,
                    'side': direction,
                    'prev_close': price_row.get('close', price),
                    'stock_type': 'main_board',
                    'position_date': date,
                    'order_date': date
                })

                if not is_valid:
                    logger.debug(f"A股规则检查失败: {msg}")
                    return equity

            # 计算成本
            trade_amount = price * quantity
            cost = self.ashare_rules.calculate_costs(
                trade_amount,
                order_side=direction,
                include_slippage=self.use_slippage,
                slippage=0.0001  # 假设0.01%滑点
            )

            total_cost = trade_amount + cost.total

            # 检查资金
            if direction.upper() == 'BUY':
                if total_cost > equity:
                    logger.debug(f"资金不足: {equity} < {total_cost}")
                    return equity

                equity -= total_cost
                positions[symbol] = positions.get(symbol, 0) + quantity

            else:  # SELL
                if symbol not in positions or positions[symbol] < quantity:
                    logger.debug(f"卖出数量超过持仓: {symbol}")
                    return equity

                equity += trade_amount - cost.total
                positions[symbol] -= quantity

            # 记录交易
            trades.append({
                'date': date,
                'symbol': symbol,
                'direction': direction,
                'quantity': quantity,
                'price': price,
                'cost': cost.total,
                'total_cost': total_cost if direction.upper() == 'BUY' else trade_amount - cost.total
            })

            return equity

        except Exception as e:
            logger.error(f"执行交易失败: {e}", exc_info=True)
            return equity


# 策略基类（供用户继承）
class Strategy:
    """
    策略基类

    用户应继承此类并实现generate_signal方法
    """

    def __init__(self, name: str = "CustomStrategy"):
        """
        Args:
            name: 策略名称
        """
        self.name = name

    def generate_signal(
        self,
        date: pd.Timestamp,
        data: pd.DataFrame
    ) -> Optional[Dict[str, Any]]:
        """
        生成交易信号

        Args:
            date: 当前交易日期
            data: 截至当前日期的历史数据

        Returns:
            信号字典或None
            信号格式:
            {
                'symbol': 股票代码,
                'direction': 'BUY' 或 'SELL',
                'quantity': 交易数量,
                'price': 价格,
                ...
            }
        """
        raise NotImplementedError("子类必须实现generate_signal方法")
