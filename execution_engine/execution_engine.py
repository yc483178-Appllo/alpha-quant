"""
Kimi Claw V7.0 智能执行引擎实现

提供多种执行算法和智能路由、风险管理、性能分析功能
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any
import logging
import json
from pathlib import Path

try:
    from config.settings import get_settings
    from utils.logger import get_logger
except ImportError:
    # 后备导入处理
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from config.settings import get_settings
    from utils.logger import get_logger

logger = get_logger(__name__)


class OrderSide(Enum):
    """订单方向"""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """订单类型"""
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class AlgorithmType(Enum):
    """执行算法类型"""
    TWAP = "TWAP"
    VWAP = "VWAP"
    POV = "POV"
    ICEBERG = "ICEBERG"
    SNIPER = "SNIPER"
    ADAPTIVE_TWAP = "ADAPTIVE_TWAP"


@dataclass
class Order:
    """订单对象"""
    symbol: str                          # 标的代码
    side: OrderSide                      # 买卖方向
    quantity: int                        # 订单总量
    limit_price: float                   # 限价
    order_id: str = ""                   # 订单ID
    created_at: datetime = field(default_factory=datetime.now)
    time_window: Optional[int] = None    # 执行时间窗口(秒)
    vwap_reference: Optional[float] = None  # VWAP参考价格
    market_cap_pct: Optional[float] = None  # 市场参与率(%)
    visible_qty: Optional[int] = None    # 冰山算法的显示数量
    price_level: Optional[float] = None  # 狙击算法的目标价位
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外信息


@dataclass
class ExecutionReport:
    """执行报告 - 包含成本分析和性能指标"""
    order_id: str                        # 订单ID
    symbol: str                          # 标的代码
    side: OrderSide                      # 买卖方向
    quantity: int                        # 订单数量
    limit_price: float                   # 订单价格

    # 执行结果
    filled_quantity: int = 0             # 成交数量
    avg_fill_price: float = 0.0          # 平均成交价
    fill_rate: float = 0.0               # 成交率 (%)
    duration: float = 0.0                # 执行时长 (秒)

    # 成本分析
    vwap_slippage: float = 0.0           # VWAP滑点成本
    market_impact: float = 0.0           # 市场冲击成本
    commission: float = 0.0              # 手续费
    stamp_tax: float = 0.0               # 印花税 (卖出时)
    opportunity_cost: float = 0.0        # 机会成本

    # 总成本
    visible_cost: float = 0.0            # 显性成本 (手续费 + 印花税)
    hidden_cost: float = 0.0             # 隐性成本 (滑点 + 冲击 + 机会成本)
    total_cost: float = 0.0              # 总成本 (bps)

    # 时间信息
    created_at: datetime = field(default_factory=datetime.now)
    executed_at: Optional[datetime] = None
    algorithm: str = ""                  # 使用的执行算法
    status: str = "PENDING"              # 状态: PENDING, EXECUTING, COMPLETED, CANCELED


class ExecutionAlgorithm(ABC):
    """执行算法基类"""

    def __init__(self, name: str):
        """初始化执行算法"""
        self.name = name
        self.logger = logger

    @abstractmethod
    def execute(self, order: Order, market_data: Dict[str, Any]) -> ExecutionReport:
        """
        执行订单

        Args:
            order: 订单对象
            market_data: 市场数据 {symbol: {price, volume, bid, ask, vwap, volume_profile}}

        Returns:
            ExecutionReport: 执行报告
        """
        pass

    @abstractmethod
    def estimate_cost(self, order: Order, market_data: Dict[str, Any]) -> float:
        """
        估计执行成本 (bps)

        Args:
            order: 订单对象
            market_data: 市场数据

        Returns:
            float: 预期成本 (基点)
        """
        pass


class TWAPAlgorithm(ExecutionAlgorithm):
    """TWAP算法 - 时间加权平均价格"""

    def __init__(self, slice_count: int = 10, time_variance: float = 0.1):
        """
        初始化TWAP算法

        Args:
            slice_count: 分片数量，默认10份
            time_variance: 时间间隔方差(0-1)，增加随机性
        """
        super().__init__("TWAP")
        self.slice_count = slice_count
        self.time_variance = time_variance

    def execute(self, order: Order, market_data: Dict[str, Any]) -> ExecutionReport:
        """
        执行TWAP算法

        将订单平均分割到多个时间段，每个时间段以市场价格成交
        """
        report = ExecutionReport(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            algorithm="TWAP"
        )

        try:
            # 计算分片大小
            slice_qty = order.quantity // self.slice_count
            remainder = order.quantity % self.slice_count

            # 计算时间间隔
            time_window = order.time_window or 300  # 默认5分钟
            base_interval = time_window / self.slice_count

            current_price = market_data.get(order.symbol, {}).get('price', order.limit_price)
            total_fill = 0
            total_cost = 0.0
            execution_prices = []

            start_time = datetime.now()

            # 执行分片
            for i in range(self.slice_count):
                # 添加时间随机性
                import random
                variance = random.uniform(1 - self.time_variance, 1 + self.time_variance)

                # 当前分片的执行数量
                current_slice_qty = slice_qty + (1 if i < remainder else 0)

                # 模拟市场执行 - 实际系统中应连接真实市场
                fill_price = current_price * (1 + random.uniform(-0.001, 0.001))
                execution_prices.append(fill_price)

                total_fill += current_slice_qty
                total_cost += fill_price * current_slice_qty

                # 更新市场价格（模拟）
                current_price = fill_price

            # 计算执行结果
            report.filled_quantity = total_fill
            report.avg_fill_price = total_cost / total_fill if total_fill > 0 else 0.0
            report.fill_rate = (total_fill / order.quantity * 100) if order.quantity > 0 else 0.0
            report.duration = (datetime.now() - start_time).total_seconds()

            # 计算成本
            reference_price = market_data.get(order.symbol, {}).get('price', order.limit_price)
            self._calculate_costs(report, reference_price)

            report.status = "COMPLETED"
            self.logger.info(f"TWAP执行完成: {order.symbol} 成交{total_fill}股 @{report.avg_fill_price:.2f}")

        except Exception as e:
            self.logger.error(f"TWAP执行失败: {str(e)}")
            report.status = "FAILED"

        return report

    def estimate_cost(self, order: Order, market_data: Dict[str, Any]) -> float:
        """
        估计TWAP成本

        基础滑点成本约为: 订单规模占比 * 市场深度系数
        """
        symbol_data = market_data.get(order.symbol, {})
        daily_volume = symbol_data.get('daily_volume', 1e6)

        # 订单占比
        order_pct = order.quantity / daily_volume

        # 基础滑点成本 (bps)
        # 小单0.5bps, 大单最多5bps
        slippage_bps = min(order_pct * 1000, 50) * 0.1

        # 加上佣金和印花税
        commission_bps = 2.0  # 0.002% = 2bps
        stamp_tax_bps = 1.0 if order.side == OrderSide.SELL else 0.0

        return slippage_bps + commission_bps + stamp_tax_bps

    def _calculate_costs(self, report: ExecutionReport, reference_price: float) -> None:
        """计算执行成本"""
        # VWAP滑点
        report.vwap_slippage = abs(report.avg_fill_price - reference_price) / reference_price * 10000

        # 市场冲击 (订单规模越大影响越大)
        order_size_bps = (report.quantity / 1000000) * 100
        report.market_impact = min(order_size_bps * 2, 20)

        # 佣金 (0.002%)
        report.commission = report.filled_quantity * report.avg_fill_price * 0.00002

        # 印花税 (卖出时 0.001%)
        if report.side == OrderSide.SELL:
            report.stamp_tax = report.filled_quantity * report.avg_fill_price * 0.00001

        # 计算总成本
        report.visible_cost = (report.commission + report.stamp_tax) / (report.filled_quantity * report.avg_fill_price) * 10000 if report.filled_quantity > 0 else 0
        report.hidden_cost = report.vwap_slippage + report.market_impact
        report.total_cost = report.visible_cost + report.hidden_cost


class VWAPAlgorithm(ExecutionAlgorithm):
    """VWAP算法 - 成交量加权平均价格"""

    def __init__(self, participation_rate: float = 0.2):
        """
        初始化VWAP算法

        Args:
            participation_rate: 参与率，跟踪市场成交量的比例(0-1)
        """
        super().__init__("VWAP")
        self.participation_rate = participation_rate

    def execute(self, order: Order, market_data: Dict[str, Any]) -> ExecutionReport:
        """
        执行VWAP算法

        根据历史成交量分布调整执行策略，在高成交量时段加大执行力度
        """
        report = ExecutionReport(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            algorithm="VWAP"
        )

        try:
            symbol_data = market_data.get(order.symbol, {})
            volume_profile = symbol_data.get('volume_profile', [])  # 整日成交量分布
            vwap_price = symbol_data.get('vwap', order.limit_price)
            current_price = symbol_data.get('price', order.limit_price)

            # 如果没有成交量数据，使用均匀分布
            if not volume_profile:
                volume_profile = [1.0 / 24] * 24  # 24小时均匀分布

            total_fill = 0
            total_cost = 0.0
            start_time = datetime.now()

            # 根据成交量分布执行
            for vol_pct in volume_profile:
                slice_qty = int(order.quantity * vol_pct)

                if slice_qty == 0:
                    continue

                # 在高成交量时段，执行成本较低
                # 在低成交量时段，执行成本较高
                price_adjustment = 1.0 / (vol_pct + 0.1)  # 成交量越低，价格调整越大
                fill_price = current_price * (1 + (price_adjustment - 1) * 0.001)

                total_fill += slice_qty
                total_cost += fill_price * slice_qty
                current_price = fill_price

            report.filled_quantity = total_fill
            report.avg_fill_price = total_cost / total_fill if total_fill > 0 else 0.0
            report.fill_rate = (total_fill / order.quantity * 100) if order.quantity > 0 else 0.0
            report.duration = (datetime.now() - start_time).total_seconds()
            report.vwap_reference = vwap_price

            # 计算成本
            self._calculate_costs(report, vwap_price)

            report.status = "COMPLETED"
            self.logger.info(f"VWAP执行完成: {order.symbol} VWAP={vwap_price:.2f} 成交价={report.avg_fill_price:.2f}")

        except Exception as e:
            self.logger.error(f"VWAP执行失败: {str(e)}")
            report.status = "FAILED"

        return report

    def estimate_cost(self, order: Order, market_data: Dict[str, Any]) -> float:
        """
        估计VWAP成本

        VWAP通常比TWAP更优，因为它利用成交量信息
        """
        symbol_data = market_data.get(order.symbol, {})
        daily_volume = symbol_data.get('daily_volume', 1e6)

        order_pct = order.quantity / daily_volume

        # VWAP成本通常更低
        slippage_bps = min(order_pct * 500, 30) * 0.1

        commission_bps = 2.0
        stamp_tax_bps = 1.0 if order.side == OrderSide.SELL else 0.0

        return slippage_bps + commission_bps + stamp_tax_bps

    def _calculate_costs(self, report: ExecutionReport, vwap_price: float) -> None:
        """计算成本"""
        # 相对VWAP的滑点
        report.vwap_slippage = abs(report.avg_fill_price - vwap_price) / vwap_price * 10000

        # 市场冲击
        order_size_bps = (report.quantity / 1000000) * 100
        report.market_impact = min(order_size_bps * 1.5, 15)

        # 佣金和印花税
        report.commission = report.filled_quantity * report.avg_fill_price * 0.00002
        if report.side == OrderSide.SELL:
            report.stamp_tax = report.filled_quantity * report.avg_fill_price * 0.00001

        report.visible_cost = (report.commission + report.stamp_tax) / (report.filled_quantity * report.avg_fill_price) * 10000 if report.filled_quantity > 0 else 0
        report.hidden_cost = report.vwap_slippage + report.market_impact
        report.total_cost = report.visible_cost + report.hidden_cost


class POVAlgorithm(ExecutionAlgorithm):
    """POV算法 - 成交量占比算法"""

    def __init__(self, market_participation_rate: float = 0.1):
        """
        初始化POV算法

        Args:
            market_participation_rate: 市场参与率，追踪市场成交量的比例(0-1)
        """
        super().__init__("POV")
        self.market_participation_rate = market_participation_rate

    def execute(self, order: Order, market_data: Dict[str, Any]) -> ExecutionReport:
        """
        执行POV算法

        订单成交速率与市场成交速率成比例，隐藏在市场成交中
        """
        report = ExecutionReport(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            algorithm="POV"
        )

        try:
            symbol_data = market_data.get(order.symbol, {})
            daily_volume = symbol_data.get('daily_volume', 1e6)
            current_price = symbol_data.get('price', order.limit_price)

            # POV执行：按市场参与率执行
            # 目标成交时间 = 订单量 / (日均成交量 * 参与率)
            target_volume = daily_volume * self.market_participation_rate
            target_execution_time = (order.quantity / target_volume) * 24 * 3600  # 秒

            total_fill = 0
            total_cost = 0.0
            start_time = datetime.now()

            # 模拟逐笔成交
            execution_slices = max(10, int(target_execution_time / 100))
            slice_qty = order.quantity // execution_slices

            for i in range(execution_slices):
                current_slice_qty = slice_qty + (order.quantity % execution_slices if i == execution_slices - 1 else 0)

                # POV的优势：订单隐藏在市场成交中，避免过度冲击
                # 价格变动较小
                import random
                fill_price = current_price * (1 + random.uniform(-0.0005, 0.0005))

                total_fill += current_slice_qty
                total_cost += fill_price * current_slice_qty
                current_price = fill_price

            report.filled_quantity = total_fill
            report.avg_fill_price = total_cost / total_fill if total_fill > 0 else 0.0
            report.fill_rate = (total_fill / order.quantity * 100) if order.quantity > 0 else 0.0
            report.market_cap_pct = self.market_participation_rate * 100
            report.duration = (datetime.now() - start_time).total_seconds()

            # 计算成本
            self._calculate_costs(report, current_price)

            report.status = "COMPLETED"
            self.logger.info(f"POV执行完成: {order.symbol} 市场参与率={self.market_participation_rate*100:.1f}%")

        except Exception as e:
            self.logger.error(f"POV执行失败: {str(e)}")
            report.status = "FAILED"

        return report

    def estimate_cost(self, order: Order, market_data: Dict[str, Any]) -> float:
        """
        估计POV成本

        POV因为隐藏在市场成交中，通常有最低的市场冲击
        """
        symbol_data = market_data.get(order.symbol, {})
        daily_volume = symbol_data.get('daily_volume', 1e6)

        order_pct = order.quantity / daily_volume

        # POV市场冲击最小
        slippage_bps = min(order_pct * 300, 15) * 0.1

        commission_bps = 2.0
        stamp_tax_bps = 1.0 if order.side == OrderSide.SELL else 0.0

        return slippage_bps + commission_bps + stamp_tax_bps

    def _calculate_costs(self, report: ExecutionReport, reference_price: float) -> None:
        """计算成本"""
        # POV滑点通常最小
        report.vwap_slippage = abs(report.avg_fill_price - reference_price) / reference_price * 10000 * 0.5

        # 市场冲击最小
        order_size_bps = (report.quantity / 1000000) * 100
        report.market_impact = min(order_size_bps * 0.8, 10)

        # 佣金和印花税
        report.commission = report.filled_quantity * report.avg_fill_price * 0.00002
        if report.side == OrderSide.SELL:
            report.stamp_tax = report.filled_quantity * report.avg_fill_price * 0.00001

        report.visible_cost = (report.commission + report.stamp_tax) / (report.filled_quantity * report.avg_fill_price) * 10000 if report.filled_quantity > 0 else 0
        report.hidden_cost = report.vwap_slippage + report.market_impact
        report.total_cost = report.visible_cost + report.hidden_cost


class IcebergAlgorithm(ExecutionAlgorithm):
    """冰山算法 - 显示小量，隐藏大量"""

    def __init__(self, visible_qty: Optional[int] = None, visible_ratio: float = 0.1):
        """
        初始化冰山算法

        Args:
            visible_qty: 显示数量，如果为None则使用visible_ratio计算
            visible_ratio: 显示比例(0-1)，默认10%
        """
        super().__init__("ICEBERG")
        self.visible_qty = visible_qty
        self.visible_ratio = visible_ratio

    def execute(self, order: Order, market_data: Dict[str, Any]) -> ExecutionReport:
        """
        执行冰山算法

        在市场上显示小量订单，隐藏大量。成交后自动补充新的订单。
        """
        report = ExecutionReport(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            algorithm="ICEBERG"
        )

        try:
            symbol_data = market_data.get(order.symbol, {})
            current_price = symbol_data.get('price', order.limit_price)

            # 计算显示数量
            visible_qty = self.visible_qty or int(order.quantity * self.visible_ratio)
            visible_qty = max(visible_qty, 100)  # 最少100股

            total_fill = 0
            total_cost = 0.0
            start_time = datetime.now()

            # 逐级显示订单
            remaining = order.quantity
            while remaining > 0:
                current_visible = min(visible_qty, remaining)

                # 冰山订单的优势：避免市场看到大量订单
                # 执行价格相对较优
                import random
                fill_price = current_price * (1 + random.uniform(-0.002, 0.002))

                total_fill += current_visible
                total_cost += fill_price * current_visible
                remaining -= current_visible
                current_price = fill_price

            report.filled_quantity = total_fill
            report.avg_fill_price = total_cost / total_fill if total_fill > 0 else 0.0
            report.fill_rate = (total_fill / order.quantity * 100) if order.quantity > 0 else 0.0
            report.visible_qty = visible_qty
            report.duration = (datetime.now() - start_time).total_seconds()

            # 计算成本
            self._calculate_costs(report, current_price)

            report.status = "COMPLETED"
            self.logger.info(f"冰山执行完成: {order.symbol} 显示量={visible_qty}股 总成交={total_fill}股")

        except Exception as e:
            self.logger.error(f"冰山执行失败: {str(e)}")
            report.status = "FAILED"

        return report

    def estimate_cost(self, order: Order, market_data: Dict[str, Any]) -> float:
        """
        估计冰山算法成本

        通过隐藏大量订单减少市场冲击
        """
        symbol_data = market_data.get(order.symbol, {})
        daily_volume = symbol_data.get('daily_volume', 1e6)

        order_pct = order.quantity / daily_volume

        # 冰山算法通过隐藏减少冲击
        slippage_bps = min(order_pct * 400, 20) * 0.1

        commission_bps = 2.0
        stamp_tax_bps = 1.0 if order.side == OrderSide.SELL else 0.0

        return slippage_bps + commission_bps + stamp_tax_bps

    def _calculate_costs(self, report: ExecutionReport, reference_price: float) -> None:
        """计算成本"""
        report.vwap_slippage = abs(report.avg_fill_price - reference_price) / reference_price * 10000

        order_size_bps = (report.quantity / 1000000) * 100
        report.market_impact = min(order_size_bps * 1.2, 12)

        report.commission = report.filled_quantity * report.avg_fill_price * 0.00002
        if report.side == OrderSide.SELL:
            report.stamp_tax = report.filled_quantity * report.avg_fill_price * 0.00001

        report.visible_cost = (report.commission + report.stamp_tax) / (report.filled_quantity * report.avg_fill_price) * 10000 if report.filled_quantity > 0 else 0
        report.hidden_cost = report.vwap_slippage + report.market_impact
        report.total_cost = report.visible_cost + report.hidden_cost


class SniperAlgorithm(ExecutionAlgorithm):
    """狙击算法 - 等待最优价位"""

    def __init__(self, target_price: Optional[float] = None, price_threshold_bps: int = 10):
        """
        初始化狙击算法

        Args:
            target_price: 目标价位，如果为None则使用限价
            price_threshold_bps: 价位阈值(基点)
        """
        super().__init__("SNIPER")
        self.target_price = target_price
        self.price_threshold_bps = price_threshold_bps

    def execute(self, order: Order, market_data: Dict[str, Any]) -> ExecutionReport:
        """
        执行狙击算法

        在特定的有利价位才执行，如果市场不达标则等待或部分成交
        """
        report = ExecutionReport(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            algorithm="SNIPER"
        )

        try:
            symbol_data = market_data.get(order.symbol, {})
            current_price = symbol_data.get('price', order.limit_price)

            # 确定目标价位
            target_price = self.target_price or order.limit_price

            # 计算触发价位范围
            threshold = target_price * (self.price_threshold_bps / 10000)

            total_fill = 0
            total_cost = 0.0
            start_time = datetime.now()

            # 狙击模拟：检查是否达到目标价位
            import random

            # 模拟价格变动
            for attempt in range(20):  # 最多20次尝试
                simulated_price = target_price * (1 + random.uniform(-0.005, 0.005))

                # 买入时，价格需要低于目标价位
                # 卖出时，价格需要高于目标价位
                price_ok = False
                if order.side == OrderSide.BUY:
                    price_ok = simulated_price <= target_price + threshold
                else:
                    price_ok = simulated_price >= target_price - threshold

                if price_ok:
                    fill_price = simulated_price
                    total_fill = order.quantity
                    total_cost = fill_price * total_fill
                    report.price_level = fill_price
                    break

            # 如果未成交，则部分成交或不成交
            if total_fill == 0:
                total_fill = order.quantity // 2  # 部分成交
                fill_price = current_price
                total_cost = fill_price * total_fill

            report.filled_quantity = total_fill
            report.avg_fill_price = total_cost / total_fill if total_fill > 0 else 0.0
            report.fill_rate = (total_fill / order.quantity * 100) if order.quantity > 0 else 0.0
            report.duration = (datetime.now() - start_time).total_seconds()

            # 计算成本
            self._calculate_costs(report, current_price)

            report.status = "COMPLETED"
            self.logger.info(f"狙击执行完成: {order.symbol} 目标价={target_price:.2f} 成交价={report.avg_fill_price:.2f}")

        except Exception as e:
            self.logger.error(f"狙击执行失败: {str(e)}")
            report.status = "FAILED"

        return report

    def estimate_cost(self, order: Order, market_data: Dict[str, Any]) -> float:
        """
        估计狙击算法成本

        狙击算法通过等待最优价位可以显著降低成本，但有不成交风险
        """
        symbol_data = market_data.get(order.symbol, {})
        daily_volume = symbol_data.get('daily_volume', 1e6)

        order_pct = order.quantity / daily_volume

        # 狙击算法的成本取决于目标价位的可达性
        # 假设有50%概率成交
        slippage_bps = min(order_pct * 200, 10) * 0.1

        commission_bps = 2.0
        stamp_tax_bps = 1.0 if order.side == OrderSide.SELL else 0.0

        return slippage_bps + commission_bps + stamp_tax_bps

    def _calculate_costs(self, report: ExecutionReport, reference_price: float) -> None:
        """计算成本"""
        report.vwap_slippage = abs(report.avg_fill_price - reference_price) / reference_price * 10000 * 0.3

        order_size_bps = (report.quantity / 1000000) * 100
        report.market_impact = min(order_size_bps * 0.5, 8)

        report.commission = report.filled_quantity * report.avg_fill_price * 0.00002
        if report.side == OrderSide.SELL:
            report.stamp_tax = report.filled_quantity * report.avg_fill_price * 0.00001

        report.visible_cost = (report.commission + report.stamp_tax) / (report.filled_quantity * report.avg_fill_price) * 10000 if report.filled_quantity > 0 else 0
        report.hidden_cost = report.vwap_slippage + report.market_impact
        report.total_cost = report.visible_cost + report.hidden_cost


class AdaptiveTWAP(ExecutionAlgorithm):
    """自适应TWAP算法 - 根据市场条件自动调整"""

    def __init__(self, base_slice_count: int = 10, volatility_sensitivity: float = 0.5):
        """
        初始化自适应TWAP算法

        Args:
            base_slice_count: 基础分片数
            volatility_sensitivity: 波动率敏感度(0-1)，越高越敏感
        """
        super().__init__("ADAPTIVE_TWAP")
        self.base_slice_count = base_slice_count
        self.volatility_sensitivity = volatility_sensitivity

    def execute(self, order: Order, market_data: Dict[str, Any]) -> ExecutionReport:
        """
        执行自适应TWAP算法

        根据市场波动率和成交量动态调整执行策略
        """
        report = ExecutionReport(
            order_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            limit_price=order.limit_price,
            algorithm="ADAPTIVE_TWAP"
        )

        try:
            symbol_data = market_data.get(order.symbol, {})
            current_price = symbol_data.get('price', order.limit_price)
            volatility = symbol_data.get('volatility', 0.02)  # 默认2%
            volume = symbol_data.get('volume', 1000000)

            # 根据波动率调整分片数
            # 高波动率 -> 更多分片（更小的每笔执行量）
            # 低波动率 -> 较少分片（较大的每笔执行量）
            volatility_factor = 1.0 + (volatility - 0.02) * self.volatility_sensitivity * 50
            adaptive_slice_count = max(5, int(self.base_slice_count * volatility_factor))

            # 根据成交量调整执行时间窗口
            time_window = order.time_window or 300
            volume_factor = 1.0 / (max(volume / 1000000, 0.1))
            adjusted_time_window = int(time_window * volume_factor)

            # 执行TWAP
            slice_qty = order.quantity // adaptive_slice_count
            remainder = order.quantity % adaptive_slice_count

            total_fill = 0
            total_cost = 0.0
            start_time = datetime.now()

            import random
            for i in range(adaptive_slice_count):
                current_slice_qty = slice_qty + (1 if i < remainder else 0)

                # 在高波动率时减小成交量波动
                volatility_adjustment = 1.0 / (1.0 + volatility)
                fill_price = current_price * (1 + random.uniform(-volatility * volatility_adjustment, volatility * volatility_adjustment))

                total_fill += current_slice_qty
                total_cost += fill_price * current_slice_qty
                current_price = fill_price

            report.filled_quantity = total_fill
            report.avg_fill_price = total_cost / total_fill if total_fill > 0 else 0.0
            report.fill_rate = (total_fill / order.quantity * 100) if order.quantity > 0 else 0.0
            report.duration = (datetime.now() - start_time).total_seconds()
            report.metadata['adaptive_slice_count'] = adaptive_slice_count
            report.metadata['volatility'] = volatility

            # 计算成本
            self._calculate_costs(report, symbol_data.get('vwap', current_price))

            report.status = "COMPLETED"
            self.logger.info(f"自适应TWAP执行完成: {order.symbol} 动态分片={adaptive_slice_count}")

        except Exception as e:
            self.logger.error(f"自适应TWAP执行失败: {str(e)}")
            report.status = "FAILED"

        return report

    def estimate_cost(self, order: Order, market_data: Dict[str, Any]) -> float:
        """
        估计自适应TWAP成本

        自适应算法会根据市场条件自动优化
        """
        symbol_data = market_data.get(order.symbol, {})
        daily_volume = symbol_data.get('daily_volume', 1e6)
        volatility = symbol_data.get('volatility', 0.02)

        order_pct = order.quantity / daily_volume

        # 基础成本
        base_slippage = min(order_pct * 1000, 50) * 0.08

        # 波动率调整
        volatility_adjustment = volatility * 100  # bps

        commission_bps = 2.0
        stamp_tax_bps = 1.0 if order.side == OrderSide.SELL else 0.0

        return base_slippage + volatility_adjustment + commission_bps + stamp_tax_bps

    def _calculate_costs(self, report: ExecutionReport, reference_price: float) -> None:
        """计算成本"""
        report.vwap_slippage = abs(report.avg_fill_price - reference_price) / reference_price * 10000 * 0.8

        volatility = report.metadata.get('volatility', 0.02)
        order_size_bps = (report.quantity / 1000000) * 100
        report.market_impact = min(order_size_bps * 1.8 * volatility, 18)

        report.commission = report.filled_quantity * report.avg_fill_price * 0.00002
        if report.side == OrderSide.SELL:
            report.stamp_tax = report.filled_quantity * report.avg_fill_price * 0.00001

        report.visible_cost = (report.commission + report.stamp_tax) / (report.filled_quantity * report.avg_fill_price) * 10000 if report.filled_quantity > 0 else 0
        report.hidden_cost = report.vwap_slippage + report.market_impact
        report.total_cost = report.visible_cost + report.hidden_cost


class SmartExecutionEngine:
    """智能执行引擎 - 支持多种算法、风险管理、订单路由"""

    # 算法注册表
    ALGORITHMS: Dict[AlgorithmType, ExecutionAlgorithm] = {
        AlgorithmType.TWAP: TWAPAlgorithm(),
        AlgorithmType.VWAP: VWAPAlgorithm(),
        AlgorithmType.POV: POVAlgorithm(),
        AlgorithmType.ICEBERG: IcebergAlgorithm(),
        AlgorithmType.SNIPER: SniperAlgorithm(),
        AlgorithmType.ADAPTIVE_TWAP: AdaptiveTWAP(),
    }

    def __init__(self, settings: Optional[Any] = None):
        """
        初始化智能执行引擎

        Args:
            settings: 配置对象
        """
        self.settings = settings or get_settings()
        self.logger = logger
        self.execution_reports: Dict[str, ExecutionReport] = {}
        self.order_cache: Dict[str, Order] = {}

    def execute(self, order: Order, algorithm: AlgorithmType, market_data: Dict[str, Any]) -> ExecutionReport:
        """
        执行订单

        Args:
            order: 订单对象
            algorithm: 执行算法类型
            market_data: 市场数据

        Returns:
            ExecutionReport: 执行报告
        """
        # 风险检查
        if not self.risk_check(order):
            report = ExecutionReport(
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                limit_price=order.limit_price,
                status="REJECTED"
            )
            self.logger.warning(f"订单风险检查失败: {order.symbol}")
            return report

        # 获取执行算法
        exec_algo = self.ALGORITHMS.get(algorithm)
        if not exec_algo:
            self.logger.error(f"未知的执行算法: {algorithm}")
            report = ExecutionReport(
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                limit_price=order.limit_price,
                status="FAILED"
            )
            return report

        # 执行订单
        self.logger.info(f"执行订单: {order.symbol} {order.side.value} {order.quantity} @ {algorithm.value}")
        report = exec_algo.execute(order, market_data)

        # 缓存报告
        self.execution_reports[order.order_id] = report
        self.order_cache[order.order_id] = order

        return report

    def risk_check(self, order: Order) -> bool:
        """
        风险检查

        Args:
            order: 订单对象

        Returns:
            bool: 是否通过风险检查
        """
        # 基本验证
        if order.quantity <= 0:
            self.logger.warning(f"订单数量无效: {order.quantity}")
            return False

        if order.limit_price <= 0:
            self.logger.warning(f"订单价格无效: {order.limit_price}")
            return False

        # A股规则检查
        # 1. 最小下单数量100股
        if order.quantity < 100:
            self.logger.warning(f"订单数量小于100股: {order.quantity}")
            return False

        # 2. 检查是否为100的整数倍
        if order.quantity % 100 != 0:
            self.logger.warning(f"订单数量不是100的倍数: {order.quantity}")
            return False

        # 3. 最大单笔数量限制（例如1000万股）
        max_order_size = getattr(self.settings, 'MAX_ORDER_SIZE', 10000000)
        if order.quantity > max_order_size:
            self.logger.warning(f"订单数量超过限制: {order.quantity} > {max_order_size}")
            return False

        return True

    def route(self, order: Order, market_data: Dict[str, Any]) -> AlgorithmType:
        """
        订单路由 - 自动选择最优执行算法

        Args:
            order: 订单对象
            market_data: 市场数据

        Returns:
            AlgorithmType: 推荐的执行算法
        """
        symbol_data = market_data.get(order.symbol, {})
        daily_volume = symbol_data.get('daily_volume', 1e6)
        volatility = symbol_data.get('volatility', 0.02)

        # 计算订单占比
        order_pct = order.quantity / daily_volume

        # 路由规则
        if volatility > 0.05:
            # 高波动率使用自适应TWAP
            return AlgorithmType.ADAPTIVE_TWAP
        elif order_pct > 0.1:
            # 大单使用冰山或POV
            return AlgorithmType.ICEBERG if order.quantity > 1000000 else AlgorithmType.POV
        elif hasattr(order, 'price_level') and order.price_level:
            # 有目标价位使用狙击
            return AlgorithmType.SNIPER
        elif symbol_data.get('volume_profile'):
            # 有成交量分布数据使用VWAP
            return AlgorithmType.VWAP
        else:
            # 默认使用TWAP
            return AlgorithmType.TWAP

    def monitor(self, order_id: str) -> Optional[ExecutionReport]:
        """
        监控订单执行状态

        Args:
            order_id: 订单ID

        Returns:
            ExecutionReport: 执行报告
        """
        return self.execution_reports.get(order_id)

    def get_execution_stats(self) -> Dict[str, Any]:
        """获取执行统计信息"""
        if not self.execution_reports:
            return {
                'total_orders': 0,
                'avg_fill_rate': 0.0,
                'avg_total_cost_bps': 0.0,
                'avg_vwap_slippage': 0.0,
                'avg_market_impact': 0.0,
            }

        reports = list(self.execution_reports.values())
        completed = [r for r in reports if r.status == "COMPLETED"]

        if not completed:
            return {
                'total_orders': len(reports),
                'completed_orders': 0,
                'avg_fill_rate': 0.0,
                'avg_total_cost_bps': 0.0,
            }

        avg_fill_rate = sum(r.fill_rate for r in completed) / len(completed)
        avg_total_cost = sum(r.total_cost for r in completed) / len(completed)
        avg_vwap_slippage = sum(r.vwap_slippage for r in completed) / len(completed)
        avg_market_impact = sum(r.market_impact for r in completed) / len(completed)

        return {
            'total_orders': len(reports),
            'completed_orders': len(completed),
            'avg_fill_rate': avg_fill_rate,
            'avg_total_cost_bps': avg_total_cost,
            'avg_vwap_slippage': avg_vwap_slippage,
            'avg_market_impact': avg_market_impact,
        }


class ExecutionPerformanceAnalyzer:
    """执行性能分析器 - 分析成本并自动选择最优算法"""

    def __init__(self, engine: SmartExecutionEngine):
        """
        初始化性能分析器

        Args:
            engine: 智能执行引擎
        """
        self.engine = engine
        self.logger = logger
        self.cost_history: Dict[str, List[ExecutionReport]] = {}

    def analyze_cost_breakdown(self, report: ExecutionReport) -> Dict[str, Any]:
        """
        分析成本构成

        Args:
            report: 执行报告

        Returns:
            Dict[str, Any]: 成本分析结果
        """
        total_cost = report.total_cost

        if total_cost == 0:
            return {
                'visible_cost_pct': 0.0,
                'hidden_cost_pct': 0.0,
                'vwap_slippage_pct': 0.0,
                'market_impact_pct': 0.0,
                'opportunity_cost_pct': 0.0,
            }

        return {
            'visible_cost_pct': (report.visible_cost / total_cost * 100) if total_cost > 0 else 0,
            'hidden_cost_pct': (report.hidden_cost / total_cost * 100) if total_cost > 0 else 0,
            'vwap_slippage_pct': (report.vwap_slippage / total_cost * 100) if total_cost > 0 else 0,
            'market_impact_pct': (report.market_impact / total_cost * 100) if total_cost > 0 else 0,
            'commission_amount': report.commission,
            'stamp_tax_amount': report.stamp_tax,
            'total_cost_bps': report.total_cost,
        }

    def compare_algorithms(self, order: Order, market_data: Dict[str, Any]) -> List[Tuple[AlgorithmType, ExecutionReport, float]]:
        """
        比较不同算法的成本

        Args:
            order: 订单对象
            market_data: 市场数据

        Returns:
            List: [(算法类型, 执行报告, 预期成本)]，按成本排序
        """
        results = []

        for algo_type, algo in self.engine.ALGORITHMS.items():
            # 获取预期成本
            estimated_cost = algo.estimate_cost(order, market_data)

            # 执行订单获取实际成本
            report = algo.execute(order, market_data)

            results.append((algo_type, report, estimated_cost))

        # 按总成本排序
        results.sort(key=lambda x: x[1].total_cost)

        self.logger.info(f"算法对比: {order.symbol} {[(t.value, f'{r.total_cost:.2f}bps') for t, r, _ in results]}")

        return results

    def recommend_algorithm(self, order: Order, market_data: Dict[str, Any]) -> Tuple[AlgorithmType, Dict[str, Any]]:
        """
        推荐最优执行算法

        Args:
            order: 订单对象
            market_data: 市场数据

        Returns:
            Tuple: (推荐算法, 分析信息)
        """
        symbol_data = market_data.get(order.symbol, {})
        daily_volume = symbol_data.get('daily_volume', 1e6)
        volatility = symbol_data.get('volatility', 0.02)

        order_pct = order.quantity / daily_volume

        # 收集各算法的预期成本
        cost_estimates = {}
        for algo_type, algo in self.engine.ALGORITHMS.items():
            cost_estimates[algo_type] = algo.estimate_cost(order, market_data)

        # 找出最低成本的算法
        best_algo = min(cost_estimates, key=cost_estimates.get)
        best_cost = cost_estimates[best_algo]

        analysis = {
            'recommended_algorithm': best_algo.value,
            'estimated_cost_bps': best_cost,
            'cost_breakdown': cost_estimates,
            'factors': {
                'order_size_pct': order_pct * 100,
                'volatility': volatility * 100,
                'daily_volume': daily_volume,
            }
        }

        self.logger.info(f"推荐算法: {order.symbol} -> {best_algo.value} ({best_cost:.2f}bps)")

        return best_algo, analysis
