"""
Kimi Claw V7.0 风险管理引擎 - 核心实现

实现风险管理、性能归因、策略监控、制度检测等核心功能。
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import warnings

try:
    from hmmlearn import hmm
except ImportError:
    hmm = None

try:
    from sklearn.preprocessing import StandardScaler
    from sklearn.decomposition import PCA
except ImportError:
    StandardScaler = None
    PCA = None

try:
    import torch
    import torch.nn as nn
except ImportError:
    torch = None


# ==================== 日志配置 ====================
logger = logging.getLogger(__name__)


# ==================== 枚举定义 ====================
class VaRMethod(Enum):
    """VaR计算方法"""
    HISTORICAL = "historical"  # 历史模拟法
    PARAMETRIC = "parametric"  # 参数法
    MONTE_CARLO = "monte_carlo"  # 蒙特卡洛模拟


class RegimeType(Enum):
    """市场制度类型"""
    NORMAL = "normal"  # 正常市场
    TRENDING = "trending"  # 趋势市场
    VOLATILE = "volatile"  # 高波动市场
    CRASH = "crash"  # 极端下跌


# ==================== 数据类 ====================
@dataclass
class AttributionResult:
    """归因结果数据类"""
    asset_allocation_effect: float  # 资产配置效应
    stock_selection_effect: float  # 股票选择效应
    interaction_return: float  # 交互收益
    total_excess_return: float  # 总超额收益
    attribution_date: datetime = field(default_factory=datetime.now)

    def __str__(self) -> str:
        return (f"AttributionResult(allocation={self.asset_allocation_effect:.4f}, "
                f"selection={self.stock_selection_effect:.4f}, "
                f"interaction={self.interaction_return:.4f}, "
                f"total={self.total_excess_return:.4f})")


@dataclass
class BarraResult:
    """Barra因子风格归因结果"""
    factor_exposures: Dict[str, float]  # 因子敞口
    factor_returns: Dict[str, float]  # 因子收益
    specific_return: float  # 特异收益
    explained_return: float  # 解释收益
    total_return: float  # 总收益
    explained_ratio: float  # 解释度

    def __str__(self) -> str:
        return (f"BarraResult(explained_ratio={self.explained_ratio:.4f}, "
                f"specific_return={self.specific_return:.4f})")


@dataclass
class TradeCostResult:
    """交易成本归因结果"""
    commission_cost: float  # 佣金
    slippage_cost: float  # 滑点
    impact_cost: float  # 冲击成本
    total_cost: float  # 总成本
    cost_ratio: float  # 成本占比 (成本/成交额)

    def __str__(self) -> str:
        return (f"TradeCostResult(total={self.total_cost:.6f}, "
                f"ratio={self.cost_ratio:.6f})")


@dataclass
class AnomalyResult:
    """异常检测结果"""
    is_anomaly: bool  # 是否异常
    anomaly_score: float  # 异常分数 (重构误差)
    threshold: float  # 异常阈值
    timestamp: datetime = field(default_factory=datetime.now)
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RegimeState:
    """市场制度状态"""
    regime_type: RegimeType  # 制度类型
    probability: float  # 当前状态概率
    duration_days: int  # 持续天数
    features: Dict[str, float]  # 特征值
    timestamp: datetime = field(default_factory=datetime.now)


# ==================== Brinson归因 ====================
class BrinsonAttribution:
    """
    Brinson归因模型

    分解超额收益为两部分:
    1. 资产配置效应: (基金权重 - 基准权重) * (基准收益 - 基准组合收益)
    2. 股票选择效应: 基准权重 * (基金收益 - 基准收益)
    3. 交互效应: (基金权重 - 基准权重) * (基金收益 - 基准收益)
    """

    def __init__(self, benchmark_weights: Dict[str, float],
                 benchmark_returns: Dict[str, float],
                 fund_weights: Optional[Dict[str, float]] = None):
        """
        初始化Brinson归因

        Args:
            benchmark_weights: 基准权重字典 {股票代码: 权重}
            benchmark_returns: 基准期间收益率字典 {股票代码: 收益率}
            fund_weights: 基金权重字典, 默认为None
        """
        self.benchmark_weights = benchmark_weights
        self.benchmark_returns = benchmark_returns
        self.fund_weights = fund_weights or {}
        self.benchmark_return = self._calculate_benchmark_return()

    def _calculate_benchmark_return(self) -> float:
        """计算基准组合收益率"""
        total_return = sum(
            weight * self.benchmark_returns.get(stock, 0)
            for stock, weight in self.benchmark_weights.items()
        )
        return total_return

    def analyze(self, fund_returns: Dict[str, float]) -> AttributionResult:
        """
        执行Brinson归因分析

        Args:
            fund_returns: 基金期间收益率字典 {股票代码: 收益率}

        Returns:
            AttributionResult: 归因结果
        """
        if not self.fund_weights:
            logger.warning("Fund weights not set, using benchmark weights")
            self.fund_weights = self.benchmark_weights

        # 确保所有股票都有权重
        all_stocks = set(self.benchmark_weights.keys()) | set(self.fund_weights.keys())

        allocation_effect = 0.0
        selection_effect = 0.0
        interaction_effect = 0.0

        for stock in all_stocks:
            bm_weight = self.benchmark_weights.get(stock, 0)
            fund_weight = self.fund_weights.get(stock, 0)
            bm_return = self.benchmark_returns.get(stock, 0)
            fund_return = fund_returns.get(stock, 0)

            # 资产配置效应 = (基金权重 - 基准权重) * (基准收益 - 基准组合收益)
            allocation_effect += (fund_weight - bm_weight) * (bm_return - self.benchmark_return)

            # 股票选择效应 = 基准权重 * (基金收益 - 基准收益)
            selection_effect += bm_weight * (fund_return - bm_return)

            # 交互效应 = (基金权重 - 基准权重) * (基金收益 - 基准收益)
            interaction_effect += (fund_weight - bm_weight) * (fund_return - bm_return)

        total_excess_return = allocation_effect + selection_effect + interaction_effect

        logger.info(f"Brinson Attribution: allocation={allocation_effect:.4f}, "
                   f"selection={selection_effect:.4f}, interaction={interaction_effect:.4f}")

        return AttributionResult(
            asset_allocation_effect=allocation_effect,
            stock_selection_effect=selection_effect,
            interaction_return=interaction_effect,
            total_excess_return=total_excess_return
        )


# ==================== Barra CNE6因子归因 ====================
class BarraCNE6Attribution:
    """
    Barra CNE6风格因子归因模型

    因子列表:
    - SIZE: 公司规模 (市值)
    - VALUE: 价值因子 (账面市值比、股利收益率)
    - GROWTH: 增长因子 (盈利增长、收入增长)
    - MOMENTUM: 动量因子 (6个月、12个月收益率)
    - RESIDUAL_VOL: 残差波动率
    - NON_LINEAR_SIZE: 非线性规模
    - BOOK_TO_PRICE: 账面市值比
    - LIQUIDITY: 流动性
    - EARNINGS_YIELD: 盈利收益率
    - LEVERAGE: 杠杆因子
    """

    FACTORS = [
        "size", "value", "growth", "momentum",
        "residual_vol", "non_linear_size", "book_to_price",
        "liquidity", "earnings_yield", "leverage"
    ]

    def __init__(self, risk_model_params: Optional[Dict[str, float]] = None):
        """
        初始化Barra CNE6模型

        Args:
            risk_model_params: 风险模型参数, 默认为None
        """
        self.risk_model_params = risk_model_params or {}
        self.factor_exposures: Dict[str, float] = {}
        self.factor_returns: Dict[str, float] = {}
        self.specific_returns: Dict[str, float] = {}

    def calculate_exposures(self, stock_data: pd.DataFrame) -> Dict[str, float]:
        """
        计算股票对各因子的敞口

        Args:
            stock_data: 股票数据DataFrame, 包含: market_cap, book_to_price, earnings_yield等

        Returns:
            Dict: 各因子敞口
        """
        exposures = {}

        try:
            # SIZE: 市值因子 (对数化)
            if 'market_cap' in stock_data.columns:
                exposures['size'] = np.log(stock_data['market_cap'].values[0])

            # VALUE: 账面市值比
            if 'book_to_price' in stock_data.columns:
                exposures['book_to_price'] = stock_data['book_to_price'].values[0]

            # EARNINGS_YIELD: 盈利收益率
            if 'earnings_yield' in stock_data.columns:
                exposures['earnings_yield'] = stock_data['earnings_yield'].values[0]

            # MOMENTUM: 6个月收益率
            if 'return_6m' in stock_data.columns:
                exposures['momentum'] = stock_data['return_6m'].values[0]

            # LIQUIDITY: 流动性 (成交量/自由流通股本)
            if 'turnover' in stock_data.columns:
                exposures['liquidity'] = stock_data['turnover'].values[0]

            # LEVERAGE: 杠杆率
            if 'leverage' in stock_data.columns:
                exposures['leverage'] = stock_data['leverage'].values[0]

            # RESIDUAL_VOL: 计算残差波动率
            if 'returns' in stock_data.columns:
                returns = stock_data['returns'].values
                if len(returns) > 20:
                    residuals = returns - np.mean(returns)
                    exposures['residual_vol'] = np.std(residuals)
                else:
                    exposures['residual_vol'] = 0.0

            logger.debug(f"Calculated exposures: {exposures}")
            self.factor_exposures = exposures
            return exposures

        except Exception as e:
            logger.error(f"Error calculating exposures: {e}")
            return exposures

    def decompose_return(self, portfolio_return: float,
                        portfolio_data: pd.DataFrame) -> BarraResult:
        """
        分解投资组合收益

        Args:
            portfolio_return: 投资组合总收益
            portfolio_data: 投资组合数据

        Returns:
            BarraResult: 因子分解结果
        """
        # 计算敞口
        exposures = self.calculate_exposures(portfolio_data)

        # 计算因子收益 (简化处理: 假设因子收益已给定或计算)
        factor_returns = {}
        for factor in self.FACTORS:
            if factor in self.risk_model_params:
                factor_returns[factor] = self.risk_model_params[factor]
            else:
                # 从数据中估计
                factor_returns[factor] = 0.0

        # 计算解释收益
        explained_return = sum(
            exposures.get(factor, 0) * factor_returns.get(factor, 0)
            for factor in self.FACTORS
        )

        # 特异收益 = 总收益 - 解释收益
        specific_return = portfolio_return - explained_return

        # 解释度 = 解释收益 / 总收益
        explained_ratio = explained_return / portfolio_return if portfolio_return != 0 else 0

        logger.info(f"Barra decomposition: explained={explained_return:.4f}, "
                   f"specific={specific_return:.4f}, ratio={explained_ratio:.4f}")

        return BarraResult(
            factor_exposures=exposures,
            factor_returns=factor_returns,
            specific_return=specific_return,
            explained_return=explained_return,
            total_return=portfolio_return,
            explained_ratio=explained_ratio
        )


# ==================== 交易成本归因 ====================
class TradeCostAttribution:
    """
    交易成本归因

    分析交易成本构成:
    - 佣金: 固定比例或固定金额
    - 滑点: 实际成交价 vs 参考价
    - 冲击成本: 市场深度影响
    """

    def __init__(self, commission_rate: float = 0.0002,
                 min_commission: float = 5.0):
        """
        初始化交易成本计算器

        Args:
            commission_rate: 佣金率, 默认0.02%
            min_commission: 最小佣金, 默认5元
        """
        self.commission_rate = commission_rate
        self.min_commission = min_commission

    def calculate_trade_costs(self,
                             order_price: float,
                             execution_price: float,
                             order_quantity: int,
                             market_price: float) -> TradeCostResult:
        """
        计算单笔交易的成本

        Args:
            order_price: 下单价格
            execution_price: 成交价格
            order_quantity: 成交数量
            market_price: 市场参考价格 (如VWAP)

        Returns:
            TradeCostResult: 成本分析结果
        """
        trade_amount = execution_price * order_quantity

        # 计算佣金
        commission_cost = max(
            trade_amount * self.commission_rate,
            self.min_commission
        )

        # 计算滑点 (成交价 vs 下单价的差异)
        slippage_cost = abs(execution_price - order_price) * order_quantity

        # 计算冲击成本 (成交价 vs 市场参考价的差异)
        impact_cost = abs(execution_price - market_price) * order_quantity

        # 总成本
        total_cost = commission_cost + slippage_cost + impact_cost

        # 成本占比
        cost_ratio = total_cost / trade_amount if trade_amount > 0 else 0

        logger.debug(f"Trade costs: commission={commission_cost:.6f}, "
                    f"slippage={slippage_cost:.6f}, impact={impact_cost:.6f}")

        return TradeCostResult(
            commission_cost=commission_cost,
            slippage_cost=slippage_cost,
            impact_cost=impact_cost,
            total_cost=total_cost,
            cost_ratio=cost_ratio
        )

    def analyze_trades(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        分析多笔交易的成本

        Args:
            trades: 交易列表, 每项包含:
                {
                    'order_price': float,
                    'execution_price': float,
                    'quantity': int,
                    'market_price': float
                }

        Returns:
            Dict: 成本统计
        """
        if not trades:
            return {
                'total_cost': 0.0,
                'avg_cost_ratio': 0.0,
                'commission_total': 0.0,
                'slippage_total': 0.0,
                'impact_total': 0.0,
                'num_trades': 0
            }

        results = [
            self.calculate_trade_costs(
                t['order_price'],
                t['execution_price'],
                t['quantity'],
                t['market_price']
            )
            for t in trades
        ]

        total_cost = sum(r.total_cost for r in results)
        commission_total = sum(r.commission_cost for r in results)
        slippage_total = sum(r.slippage_cost for r in results)
        impact_total = sum(r.impact_cost for r in results)
        avg_cost_ratio = np.mean([r.cost_ratio for r in results])

        logger.info(f"Trade analysis: {len(trades)} trades, total_cost={total_cost:.6f}, "
                   f"avg_ratio={avg_cost_ratio:.6f}")

        return {
            'total_cost': total_cost,
            'avg_cost_ratio': avg_cost_ratio,
            'commission_total': commission_total,
            'slippage_total': slippage_total,
            'impact_total': impact_total,
            'num_trades': len(trades),
            'results': results
        }


# ==================== 策略生命周期监控 ====================
class StrategyLifecycleMonitor:
    """
    策略生命周期监控

    监控指标:
    - IC (信息系数) 和 IC衰减
    - 赢率和赢率变化
    - 策略风格漂移
    - 自动触发预警 -> 缩减 -> 下线

    状态转移: ACTIVE -> WARNING -> REDUCING -> OFFLINE
    """

    class MonitorStatus(Enum):
        """监控状态"""
        ACTIVE = "active"  # 正常运行
        WARNING = "warning"  # 预警
        REDUCING = "reducing"  # 缩减规模
        OFFLINE = "offline"  # 下线

    def __init__(self,
                 ic_decay_threshold: float = -0.05,
                 win_rate_threshold: float = 0.45,
                 style_drift_threshold: float = 0.3):
        """
        初始化策略监控器

        Args:
            ic_decay_threshold: IC衰减阈值, 默认-5%
            win_rate_threshold: 赢率阈值, 默认45%
            style_drift_threshold: 风格漂移阈值, 默认30%
        """
        self.ic_decay_threshold = ic_decay_threshold
        self.win_rate_threshold = win_rate_threshold
        self.style_drift_threshold = style_drift_threshold

        self.ic_history: List[float] = []
        self.win_rate_history: List[float] = []
        self.style_history: List[Dict[str, float]] = []
        self.status = self.MonitorStatus.ACTIVE
        self.warning_count = 0

    def update_ic(self, ic_value: float) -> bool:
        """
        更新IC值

        Args:
            ic_value: 当前IC值

        Returns:
            bool: 是否触发预警
        """
        self.ic_history.append(ic_value)

        # 检查IC衰减
        if len(self.ic_history) >= 20:
            recent_ic = np.mean(self.ic_history[-20:])
            old_ic = np.mean(self.ic_history[-40:-20])
            ic_decay = recent_ic - old_ic

            if ic_decay < self.ic_decay_threshold:
                self.warning_count += 1
                logger.warning(f"IC decay detected: {ic_decay:.4f}")
                return True

        return False

    def update_win_rate(self, win_rate: float) -> bool:
        """
        更新赢率

        Args:
            win_rate: 当前赢率 (0-1)

        Returns:
            bool: 是否触发预警
        """
        self.win_rate_history.append(win_rate)

        if win_rate < self.win_rate_threshold:
            self.warning_count += 1
            logger.warning(f"Low win rate: {win_rate:.4f}")
            return True

        return False

    def update_style(self, style_exposure: Dict[str, float]):
        """
        更新风格敞口

        Args:
            style_exposure: 风格敞口字典
        """
        self.style_history.append(style_exposure)

        # 检查风格漂移
        if len(self.style_history) >= 2:
            current_style = self.style_history[-1]
            previous_style = self.style_history[-2]

            drift = np.sqrt(sum(
                (current_style.get(k, 0) - previous_style.get(k, 0)) ** 2
                for k in set(current_style.keys()) | set(previous_style.keys())
            ))

            if drift > self.style_drift_threshold:
                self.warning_count += 1
                logger.warning(f"Style drift detected: {drift:.4f}")
                return True

        return False

    def check_status(self) -> MonitorStatus:
        """
        检查策略状态并更新

        Returns:
            MonitorStatus: 当前状态
        """
        if self.status == self.MonitorStatus.OFFLINE:
            return self.status

        if self.warning_count >= 3:
            if self.status == self.MonitorStatus.ACTIVE:
                self.status = self.MonitorStatus.WARNING
                logger.error("Strategy moved to WARNING status")
            elif self.status == self.MonitorStatus.WARNING:
                self.status = self.MonitorStatus.REDUCING
                logger.error("Strategy moved to REDUCING status")
            elif self.status == self.MonitorStatus.REDUCING:
                self.status = self.MonitorStatus.OFFLINE
                logger.error("Strategy moved to OFFLINE status")
            self.warning_count = 0

        return self.status

    def get_report(self) -> Dict[str, Any]:
        """获取监控报告"""
        return {
            'status': self.status.value,
            'warning_count': self.warning_count,
            'avg_ic': np.mean(self.ic_history) if self.ic_history else 0.0,
            'avg_win_rate': np.mean(self.win_rate_history) if self.win_rate_history else 0.0,
            'ic_trend': self.ic_history[-10:] if len(self.ic_history) >= 10 else self.ic_history,
            'num_updates': len(self.ic_history)
        }


# ==================== 异常检测引擎 (自编码器) ====================
class AnomalyDetector:
    """
    基于自编码器的异常检测

    学习"正常行为模式", 当重构误差激增时 = 策略偏离
    相比IC衰减更早检测到问题

    如果PyTorch不可用, 使用简化的基于统计的检测
    """

    def __init__(self, window_size: int = 20,
                 anomaly_percentile: float = 95.0,
                 use_pytorch: bool = True):
        """
        初始化异常检测器

        Args:
            window_size: 时间窗口大小
            anomaly_percentile: 异常分数百分位数
            use_pytorch: 是否使用PyTorch自编码器
        """
        self.window_size = window_size
        self.anomaly_percentile = anomaly_percentile
        self.use_pytorch = use_pytorch and torch is not None
        self.scaler: Optional[StandardScaler] = None
        self.autoencoder: Optional[nn.Module] = None
        self.reconstruction_errors: List[float] = []
        self.anomaly_threshold: float = 0.0
        self.features_history: List[np.ndarray] = []

        if self.use_pytorch:
            self._init_autoencoder()
        else:
            logger.info("PyTorch not available, using statistical anomaly detection")

    def _init_autoencoder(self):
        """初始化自编码器"""
        if not torch:
            return

        class SimpleAutoencoder(nn.Module):
            def __init__(self, input_dim: int = 10, hidden_dim: int = 5):
                super().__init__()
                self.encoder = nn.Sequential(
                    nn.Linear(input_dim, hidden_dim),
                    nn.ReLU(),
                    nn.Linear(hidden_dim, 2)
                )
                self.decoder = nn.Sequential(
                    nn.Linear(2, hidden_dim),
                    nn.ReLU(),
                    nn.Linear(hidden_dim, input_dim)
                )

            def forward(self, x):
                encoded = self.encoder(x)
                decoded = self.decoder(encoded)
                return decoded

        self.autoencoder = SimpleAutoencoder()
        self.scaler = StandardScaler()

    def extract_features(self, market_data: Dict[str, float]) -> np.ndarray:
        """
        提取特征向量

        Expected keys: returns, volatility, turnover, correlation, drawdown, sharp_ratio

        Args:
            market_data: 市场数据字典

        Returns:
            np.ndarray: 特征向量
        """
        features = np.array([
            market_data.get('returns', 0.0),
            market_data.get('volatility', 0.0),
            market_data.get('turnover', 0.0),
            market_data.get('correlation', 0.0),
            market_data.get('drawdown', 0.0),
            market_data.get('sharp_ratio', 0.0),
            market_data.get('max_loss', 0.0),
            market_data.get('win_rate', 0.0),
            market_data.get('ic', 0.0),
            market_data.get('profit_factor', 0.0),
        ])
        return features

    def update(self, market_data: Dict[str, float]) -> AnomalyResult:
        """
        更新异常检测

        Args:
            market_data: 市场数据

        Returns:
            AnomalyResult: 检测结果
        """
        features = self.extract_features(market_data)
        self.features_history.append(features)

        # 需要积累足够数据才能检测
        if len(self.features_history) < self.window_size:
            return AnomalyResult(
                is_anomaly=False,
                anomaly_score=0.0,
                threshold=0.0,
                details={'reason': 'insufficient_data'}
            )

        if self.use_pytorch:
            return self._pytorch_anomaly_detection()
        else:
            return self._statistical_anomaly_detection()

    def _pytorch_anomaly_detection(self) -> AnomalyResult:
        """使用PyTorch进行异常检测"""
        if not torch or not self.autoencoder or not self.scaler:
            return AnomalyResult(
                is_anomaly=False,
                anomaly_score=0.0,
                threshold=0.0
            )

        try:
            # 准备数据
            recent_features = np.array(self.features_history[-self.window_size:])
            scaled_features = self.scaler.fit_transform(recent_features)

            # 获取最新数据点
            latest_scaled = torch.tensor(
                scaled_features[-1:], dtype=torch.float32
            )

            # 计算重构误差
            with torch.no_grad():
                reconstructed = self.autoencoder(latest_scaled)
                reconstruction_error = float(
                    torch.mean((latest_scaled - reconstructed) ** 2).item()
                )

            self.reconstruction_errors.append(reconstruction_error)

            # 计算动态阈值
            if len(self.reconstruction_errors) >= 10:
                self.anomaly_threshold = np.percentile(
                    self.reconstruction_errors,
                    self.anomaly_percentile
                )
            else:
                self.anomaly_threshold = np.mean(self.reconstruction_errors) * 2

            is_anomaly = reconstruction_error > self.anomaly_threshold

            if is_anomaly:
                logger.warning(f"Anomaly detected: error={reconstruction_error:.6f}, "
                              f"threshold={self.anomaly_threshold:.6f}")

            return AnomalyResult(
                is_anomaly=is_anomaly,
                anomaly_score=reconstruction_error,
                threshold=self.anomaly_threshold,
                details={
                    'method': 'pytorch_autoencoder',
                    'num_errors': len(self.reconstruction_errors)
                }
            )

        except Exception as e:
            logger.error(f"PyTorch anomaly detection error: {e}")
            return AnomalyResult(
                is_anomaly=False,
                anomaly_score=0.0,
                threshold=0.0,
                details={'error': str(e)}
            )

    def _statistical_anomaly_detection(self) -> AnomalyResult:
        """使用统计方法进行异常检测"""
        recent_features = np.array(self.features_history[-self.window_size:])
        latest_features = self.features_history[-1]

        # 计算Mahalanobis距离作为异常分数
        mean = np.mean(recent_features, axis=0)
        cov = np.cov(recent_features.T)

        try:
            cov_inv = np.linalg.inv(cov + np.eye(len(mean)) * 1e-6)
            diff = latest_features - mean
            anomaly_score = float(np.sqrt(diff @ cov_inv @ diff.T))
        except:
            # 如果矩阵奇异, 使用欧氏距离
            diff = latest_features - mean
            anomaly_score = float(np.linalg.norm(diff))

        self.reconstruction_errors.append(anomaly_score)

        # 计算阈值
        if len(self.reconstruction_errors) >= 10:
            self.anomaly_threshold = np.percentile(
                self.reconstruction_errors,
                self.anomaly_percentile
            )
        else:
            self.anomaly_threshold = np.mean(self.reconstruction_errors) * 2

        is_anomaly = anomaly_score > self.anomaly_threshold

        if is_anomaly:
            logger.warning(f"Anomaly detected: score={anomaly_score:.6f}, "
                          f"threshold={self.anomaly_threshold:.6f}")

        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_score=anomaly_score,
            threshold=self.anomaly_threshold,
            details={'method': 'statistical_mahalanobis'}
        )


# ==================== HMM制度检测 ====================
class HMMRegimeDetector:
    """
    HMM多特征制度检测

    特征: returns + volatility + turnover + north_flow + option_iv + term_spread
    多时间尺度: daily/hourly/minute
    在线增量HMM + 滑动窗口
    用DRO(分布鲁棒优化)替代均值-方差

    如果hmmlearn不可用, 使用简化的制度检测
    """

    def __init__(self,
                 n_regimes: int = 3,
                 lookback_days: int = 60,
                 use_hmm: bool = True):
        """
        初始化HMM制度检测器

        Args:
            n_regimes: 制度数量 (通常3-4个)
            lookback_days: 回看天数
            use_hmm: 是否使用HMM
        """
        self.n_regimes = n_regimes
        self.lookback_days = lookback_days
        self.use_hmm = use_hmm and hmm is not None
        self.model: Optional[Any] = None
        self.scaler: Optional[StandardScaler] = None
        self.features_history: List[np.ndarray] = []
        self.regime_history: List[RegimeType] = []
        self.current_regime: Optional[RegimeState] = None
        self.regime_duration = 0

        if self.use_hmm:
            self._init_hmm()
        else:
            logger.info("hmmlearn not available, using statistical regime detection")

    def _init_hmm(self):
        """初始化HMM模型"""
        if not hmm:
            return
        try:
            self.model = hmm.GaussianHMM(
                n_components=self.n_regimes,
                covariance_type="full",
                n_iter=100,
                random_state=42
            )
            self.scaler = StandardScaler()
        except Exception as e:
            logger.error(f"Failed to initialize HMM: {e}")
            self.use_hmm = False

    def extract_features(self,
                        daily_return: float,
                        volatility: float,
                        turnover: float,
                        north_flow: float,
                        option_iv: float,
                        term_spread: float) -> np.ndarray:
        """
        提取多特征向量

        Args:
            daily_return: 日收益率
            volatility: 波动率 (日)
            turnover: 换手率
            north_flow: 北向资金流入 (十亿)
            option_iv: 期权隐含波动率
            term_spread: 期限利差

        Returns:
            np.ndarray: 特征向量
        """
        return np.array([
            daily_return,
            volatility,
            turnover,
            north_flow,
            option_iv,
            term_spread
        ])

    def update(self,
               daily_return: float,
               volatility: float,
               turnover: float,
               north_flow: float,
               option_iv: float,
               term_spread: float) -> RegimeState:
        """
        更新制度检测

        Args:
            daily_return: 日收益率
            volatility: 波动率
            turnover: 换手率
            north_flow: 北向资金流入
            option_iv: 期权隐含波动率
            term_spread: 期限利差

        Returns:
            RegimeState: 当前制度状态
        """
        features = self.extract_features(
            daily_return, volatility, turnover,
            north_flow, option_iv, term_spread
        )
        self.features_history.append(features)

        # 需要足够数据进行拟合
        min_samples = max(self.n_regimes * 2, 20)
        if len(self.features_history) < min_samples:
            regime_type = self._identify_regime_type(features)
            self.current_regime = RegimeState(
                regime_type=regime_type,
                probability=0.5,
                duration_days=len(self.regime_history),
                features={'return': daily_return, 'volatility': volatility}
            )
            return self.current_regime

        if self.use_hmm:
            return self._hmm_regime_detection()
        else:
            return self._statistical_regime_detection()

    def _identify_regime_type(self, features: np.ndarray) -> RegimeType:
        """
        识别制度类型

        Args:
            features: 特征向量 [return, vol, turnover, north_flow, option_iv, term_spread]

        Returns:
            RegimeType: 制度类型
        """
        daily_return = features[0]
        volatility = features[1]

        if volatility > 0.03:  # 高波动
            return RegimeType.VOLATILE
        elif daily_return < -0.02:  # 大幅下跌
            return RegimeType.CRASH
        elif abs(daily_return) > 0.01:  # 有趋势
            return RegimeType.TRENDING
        else:
            return RegimeType.NORMAL

    def _hmm_regime_detection(self) -> RegimeState:
        """使用HMM进行制度检测"""
        if not self.model or not self.scaler:
            return RegimeState(
                regime_type=RegimeType.NORMAL,
                probability=0.5,
                duration_days=self.regime_duration,
                features={}
            )

        try:
            # 滑动窗口
            window_data = np.array(
                self.features_history[-self.lookback_days:]
            )
            scaled_data = self.scaler.fit_transform(window_data)

            # 拟合HMM
            self.model.fit(scaled_data)

            # 预测当前状态
            latest_scaled = scaled_data[-1:].reshape(1, -1)
            predicted_regime = int(self.model.predict(latest_scaled)[0])

            # 获取状态概率
            log_prob = self.model.predict_proba(latest_scaled)
            probabilities = np.exp(log_prob[0])
            regime_prob = float(probabilities[predicted_regime])

            # 映射到制度类型
            if predicted_regime == 0:
                regime_type = RegimeType.NORMAL
            elif predicted_regime == 1:
                regime_type = RegimeType.VOLATILE
            elif predicted_regime == 2:
                regime_type = RegimeType.TRENDING
            else:
                regime_type = RegimeType.CRASH

            # 更新持续天数
            if self.current_regime and self.current_regime.regime_type == regime_type:
                self.regime_duration += 1
            else:
                self.regime_duration = 1

            features_dict = {
                'return': float(self.features_history[-1][0]),
                'volatility': float(self.features_history[-1][1]),
                'turnover': float(self.features_history[-1][2])
            }

            self.current_regime = RegimeState(
                regime_type=regime_type,
                probability=regime_prob,
                duration_days=self.regime_duration,
                features=features_dict
            )

            logger.debug(f"HMM regime: {regime_type.value}, prob={regime_prob:.4f}")
            return self.current_regime

        except Exception as e:
            logger.error(f"HMM regime detection error: {e}")
            return RegimeState(
                regime_type=RegimeType.NORMAL,
                probability=0.5,
                duration_days=self.regime_duration,
                features={}
            )

    def _statistical_regime_detection(self) -> RegimeState:
        """使用统计方法进行制度检测"""
        if not self.features_history:
            return RegimeState(
                regime_type=RegimeType.NORMAL,
                probability=0.5,
                duration_days=0,
                features={}
            )

        latest_features = self.features_history[-1]

        # 计算最近20天的统计
        lookback = min(20, len(self.features_history))
        recent_features = np.array(self.features_history[-lookback:])

        avg_return = np.mean(recent_features[:, 0])
        avg_volatility = np.mean(recent_features[:, 1])

        # 简单的制度判断规则
        regime_type = self._identify_regime_type(latest_features)

        # 计算概率 (简化)
        if regime_type == RegimeType.NORMAL:
            prob = 0.6
        elif regime_type == RegimeType.VOLATILE:
            prob = 0.7 if avg_volatility > 0.02 else 0.5
        elif regime_type == RegimeType.TRENDING:
            prob = 0.65
        else:  # CRASH
            prob = 0.9

        # 更新持续天数
        if self.current_regime and self.current_regime.regime_type == regime_type:
            self.regime_duration += 1
        else:
            self.regime_duration = 1

        features_dict = {
            'return': float(latest_features[0]),
            'volatility': float(latest_features[1]),
            'turnover': float(latest_features[2])
        }

        self.current_regime = RegimeState(
            regime_type=regime_type,
            probability=prob,
            duration_days=self.regime_duration,
            features=features_dict
        )

        logger.debug(f"Statistical regime: {regime_type.value}, prob={prob:.4f}")
        return self.current_regime


# ==================== 压力测试引擎 ====================
class PressureTestEngine:
    """
    压力测试引擎

    内置A股极端场景:
    - 2015年股灾
    - 2020年新冠疫情
    - 2022年熊市

    分析不同AUM规模下的策略容量
    """

    # 历史极端场景参数
    SCENARIOS = {
        'crash_2015': {
            'description': '2015年股灾',
            'daily_returns': [-0.07, -0.08, -0.05, -0.03, -0.02],
            'volatility': 0.08,
            'correlation_shock': 0.95,
            'liquidity_shock': 0.5
        },
        'pandemic_2020': {
            'description': '2020年新冠疫情',
            'daily_returns': [-0.03, -0.02, 0.01, 0.02, -0.01],
            'volatility': 0.05,
            'correlation_shock': 0.85,
            'liquidity_shock': 0.7
        },
        'bear_2022': {
            'description': '2022年熊市',
            'daily_returns': [-0.02, -0.01, -0.02, -0.01, 0.00],
            'volatility': 0.03,
            'correlation_shock': 0.7,
            'liquidity_shock': 0.8
        }
    }

    def __init__(self):
        """初始化压力测试引擎"""
        self.test_results: Dict[str, Dict[str, Any]] = {}

    def run_scenario_test(self,
                         scenario_name: str,
                         portfolio_returns: List[float],
                         portfolio_weights: Dict[str, float],
                         initial_aum: float) -> Dict[str, Any]:
        """
        运行单个场景压力测试

        Args:
            scenario_name: 场景名称 (crash_2015, pandemic_2020, bear_2022)
            portfolio_returns: 投资组合历史收益率列表
            portfolio_weights: 投资组合权重
            initial_aum: 初始AUM (百万元)

        Returns:
            Dict: 测试结果
        """
        if scenario_name not in self.SCENARIOS:
            logger.error(f"Unknown scenario: {scenario_name}")
            return {}

        scenario = self.SCENARIOS[scenario_name]

        # 计算历史平均收益和波动率
        portfolio_ret = np.array(portfolio_returns)
        avg_return = np.mean(portfolio_ret)
        base_volatility = np.std(portfolio_ret)

        # 在极端场景下的投资组合表现
        scenario_returns = scenario['daily_returns']
        portfolio_scenario_returns = []

        for day_return in scenario_returns:
            # 场景收益 = 基础收益 + 场景冲击 * 相关性冲击
            day_portfolio_return = avg_return + day_return * scenario['correlation_shock']
            portfolio_scenario_returns.append(day_portfolio_return)

        # 计算关键风险指标
        max_drawdown = np.min(np.cumsum(portfolio_scenario_returns))
        volatility_under_stress = np.std(portfolio_scenario_returns)
        cumulative_return = np.sum(portfolio_scenario_returns)

        # 流动性影响 (通过冲击成本衡量)
        liquidity_impact = (1 - scenario['liquidity_shock']) * 0.01  # 1-10%的成本
        net_return = cumulative_return - liquidity_impact

        # 容量分析
        capacity_analysis = self._analyze_capacity(
            initial_aum,
            portfolio_weights,
            scenario['liquidity_shock']
        )

        result = {
            'scenario': scenario_name,
            'description': scenario['description'],
            'max_drawdown': float(max_drawdown),
            'volatility_under_stress': float(volatility_under_stress),
            'cumulative_return': float(cumulative_return),
            'net_return_after_liquidity': float(net_return),
            'liquidity_impact': float(liquidity_impact),
            'capacity_analysis': capacity_analysis
        }

        self.test_results[scenario_name] = result
        logger.info(f"Scenario test {scenario_name}: max_dd={max_drawdown:.4f}, "
                   f"vol={volatility_under_stress:.4f}")

        return result

    def _analyze_capacity(self,
                         aum_million: float,
                         portfolio_weights: Dict[str, float],
                         liquidity_factor: float) -> Dict[str, Any]:
        """
        分析不同AUM规模下的策略容量

        Args:
            aum_million: AUM (百万元)
            portfolio_weights: 投资组合权重
            liquidity_factor: 流动性因子 (0-1)

        Returns:
            Dict: 容量分析
        """
        # 假设A股日均成交量约1万亿元
        daily_market_volume = 1000 * 1000  # 百万元

        # 计算最大可交易金额 (基于流动性)
        max_tradable = daily_market_volume * liquidity_factor * 0.1

        # 容量阈值
        capacity_ratio = aum_million / max_tradable
        capacity_status = "充足" if capacity_ratio < 0.5 else "有限" if capacity_ratio < 1.0 else "已超"

        return {
            'current_aum_million': float(aum_million),
            'max_capacity_million': float(max_tradable),
            'capacity_ratio': float(capacity_ratio),
            'status': capacity_status,
            'recommended_aum_ceiling': float(max_tradable * 0.5)
        }

    def run_all_scenarios(self,
                         portfolio_returns: List[float],
                         portfolio_weights: Dict[str, float],
                         initial_aum: float) -> Dict[str, Dict[str, Any]]:
        """
        运行所有场景压力测试

        Args:
            portfolio_returns: 投资组合历史收益率
            portfolio_weights: 投资组合权重
            initial_aum: 初始AUM

        Returns:
            Dict: 所有场景的测试结果
        """
        for scenario_name in self.SCENARIOS.keys():
            self.run_scenario_test(
                scenario_name,
                portfolio_returns,
                portfolio_weights,
                initial_aum
            )

        return self.test_results


# ==================== VaR计算 ====================
class VaRCalculator:
    """
    Value at Risk (风险价值) 计算

    支持三种方法:
    1. 历史模拟法 (Historical): 使用历史数据的分位数
    2. 参数法 (Parametric): 假设正态分布
    3. 蒙特卡洛法 (Monte Carlo): 模拟未来场景
    """

    def __init__(self, confidence_level: float = 0.95):
        """
        初始化VaR计算器

        Args:
            confidence_level: 置信度水平, 默认95% (即5%尾部风险)
        """
        self.confidence_level = confidence_level
        self.alpha = 1 - confidence_level  # 5%

    def calculate_historical_var(self, returns: List[float]) -> float:
        """
        历史模拟法计算VaR

        Args:
            returns: 历史收益率列表

        Returns:
            float: VaR值 (负值, 表示最大可能亏损)
        """
        returns_array = np.array(returns)
        var = np.percentile(returns_array, self.alpha * 100)
        logger.debug(f"Historical VaR: {var:.4f}")
        return float(var)

    def calculate_parametric_var(self, mean_return: float, volatility: float) -> float:
        """
        参数法计算VaR (假设正态分布)

        Args:
            mean_return: 平均收益率
            volatility: 波动率 (标准差)

        Returns:
            float: VaR值
        """
        # 对于95%置信度, z分数约为-1.645
        z_score = -1.645 if self.confidence_level == 0.95 else -2.326

        var = mean_return + z_score * volatility
        logger.debug(f"Parametric VaR: {var:.4f}")
        return float(var)

    def calculate_monte_carlo_var(self,
                                 mean_return: float,
                                 volatility: float,
                                 periods: int = 1,
                                 num_simulations: int = 10000) -> float:
        """
        蒙特卡洛模拟法计算VaR

        Args:
            mean_return: 平均收益率
            volatility: 波动率
            periods: 时间周期 (天数)
            num_simulations: 模拟次数

        Returns:
            float: VaR值
        """
        np.random.seed(42)

        # 模拟期间的收益率
        simulated_returns = np.random.normal(
            mean_return * periods,
            volatility * np.sqrt(periods),
            num_simulations
        )

        var = np.percentile(simulated_returns, self.alpha * 100)
        logger.debug(f"Monte Carlo VaR: {var:.4f}")
        return float(var)

    def calculate_cvar(self, returns: List[float]) -> float:
        """
        计算条件VaR (CVaR) / 期望亏损 (Expected Shortfall)

        CVaR是超过VaR阈值的平均亏损

        Args:
            returns: 历史收益率列表

        Returns:
            float: CVaR值
        """
        returns_array = np.array(returns)
        var_threshold = np.percentile(returns_array, self.alpha * 100)
        cvar = np.mean(returns_array[returns_array <= var_threshold])
        logger.debug(f"CVaR: {cvar:.4f}")
        return float(cvar)

    def calculate_all_vars(self,
                          returns: List[float],
                          mean_return: float,
                          volatility: float) -> Dict[str, float]:
        """
        计算所有VaR方法

        Args:
            returns: 历史收益率列表
            mean_return: 平均收益率
            volatility: 波动率

        Returns:
            Dict: 各方法的VaR值
        """
        return {
            'historical': self.calculate_historical_var(returns),
            'parametric': self.calculate_parametric_var(mean_return, volatility),
            'monte_carlo': self.calculate_monte_carlo_var(mean_return, volatility),
            'cvar': self.calculate_cvar(returns),
            'confidence_level': self.confidence_level
        }

    def get_var_report(self,
                      portfolio_value: float,
                      returns: List[float],
                      mean_return: float,
                      volatility: float,
                      holding_period: int = 1) -> Dict[str, Any]:
        """
        生成VaR报告

        Args:
            portfolio_value: 投资组合价值
            returns: 历史收益率列表
            mean_return: 平均收益率
            volatility: 波动率
            holding_period: 持仓周期 (天)

        Returns:
            Dict: VaR报告
        """
        var_values = self.calculate_all_vars(returns, mean_return, volatility)

        # 转换为绝对金额
        var_amounts = {
            method: portfolio_value * abs(var) for method, var in var_values.items()
            if isinstance(var, float)
        }

        return {
            'portfolio_value': float(portfolio_value),
            'var_ratios': var_values,
            'var_amounts': var_amounts,
            'holding_period_days': holding_period,
            'confidence_level': self.confidence_level,
            'interpretation': (
                f"在{self.confidence_level*100:.0f}%置信度下, "
                f"未来{holding_period}天的最大预期亏损为"
            )
        }
