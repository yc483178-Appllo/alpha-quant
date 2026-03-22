# Alpha-Genesis V7.0 - 智能订单执行算法引擎

## 2.4 智能订单执行算法引擎

### 定位：解决规模化后滑点吞噬收益的问题

**核心问题：** 当策略从10只标的扩展到100-500只时，订单规模急剧增大，市场冲击成本和滑点会严重侵蚀Alpha收益。

**解决思路：**
- 智能拆单：大订单拆分为多个小订单
- 时机选择：选择流动性好的时段执行
- 隐藏意图：避免被市场发现交易意图
- 动态调整：根据市场条件自适应调整

---

### 2.4.1 核心执行引擎架构

```python
# execution_engine.py
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import pandas as pd
import numpy as np


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    PARTIAL_FILL = "partial_fill"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


@dataclass
class ParentOrder:
    """父订单"""
    order_id: str
    code: str
    side: str  # 'buy' or 'sell'
    total_quantity: int
    filled_quantity: int = 0
    
    # 执行参数
    algo: str = 'adaptive_twap'  # 执行算法
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    # 价格限制
    price_limit: Optional[float] = None
    stop_price: Optional[float] = None
    
    # 紧急程度 (0-1)
    urgency: float = 0.5
    
    # 市场数据
    avg_daily_volume: Optional[int] = None
    current_price: Optional[float] = None
    spread: Optional[float] = None


@dataclass
class ChildOrder:
    """子订单 (拆单后的订单)"""
    child_id: str
    parent_id: str
    code: str
    side: str
    quantity: int
    order_type: str  # 'limit', 'market', 'ioc', 'fok'
    limit_price: Optional[float] = None
    trigger_time: datetime = None
    status: ExecutionStatus = ExecutionStatus.PENDING


@dataclass
class ExecutionReport:
    """执行报告"""
    order_id: str
    parent_order: ParentOrder
    child_orders: List[ChildOrder]
    
    # 执行统计
    total_filled: int
    avg_fill_price: float
    vwap: float
    
    # 成本分析
    market_impact_cost: float
    slippage_cost: float
    opportunity_cost: float
    total_cost: float
    
    # 绩效指标
    arrival_price: float  # 下单时的市场价
    implementation_shortfall: float  # 实现价差
    
    def summary(self) -> Dict:
        """执行摘要"""
        return {
            'fill_rate': self.total_filled / self.parent_order.total_quantity,
            'avg_fill_price': self.avg_fill_price,
            'vwap': self.vwap,
            'total_cost_bps': self.total_cost * 10000,  # 基点
            'implementation_shortfall_bps': self.implementation_shortfall * 10000
        }


class SmartExecutionEngine:
    """
    智能订单执行引擎
    
    支持多种执行算法，根据订单特征和市场条件自动选择最优算法
    """
    
    ALGORITHMS = {
        'twap': 'TWAPAlgorithm',          # 时间加权均价
        'vwap': 'VWAPAlgorithm',          # 成交量加权均价
        'pov':  'POVAlgorithm',           # 跟量算法 (Percent of Volume)
        'iceberg': 'IcebergAlgorithm',    # 冰山单
        'sniper': 'SniperAlgorithm',      # 狙击单
        'adaptive_twap': 'AdaptiveTWAP',  # 自适应TWAP
    }
    
    def __init__(self):
        self.risk_checker = ExecutionRiskChecker()
        self.order_router = OrderRouter()
        self.monitor = ExecutionMonitor()
        self.performance_tracker = PerformanceTracker()
        
        # 算法实例缓存
        self._algo_instances = {}
        
    def execute(self, order: ParentOrder, algo: str = None) -> ExecutionReport:
        """
        执行订单
        
        Args:
            order: 父订单
            algo: 执行算法，None则自动选择
            
        Returns:
            ExecutionReport: 执行报告
        """
        # 自动选择算法
        if algo is None:
            algo = self._auto_select_algorithm(order)
        
        # 验证算法可用性
        if algo not in self.ALGORITHMS:
            raise ValueError(f"未知算法: {algo}, 可用算法: {list(self.ALGORITHMS.keys())}")
        
        print(f"[{order.order_id}] 使用 {algo} 算法执行")
        
        # 获取算法实例
        algo_instance = self._get_algorithm_instance(algo, order)
        
        # 拆单
        child_orders = algo_instance.split(order)
        print(f"[{order.order_id}] 拆分为 {len(child_orders)} 个子订单")
        
        # 执行子订单
        filled_children = []
        for child in child_orders:
            # 风控检查
            if not self.risk_check(child):
                print(f"[{child.child_id}] 风控检查未通过，跳过")
                continue
            
            # 等待触发时间
            if child.trigger_time and datetime.now() < child.trigger_time:
                wait_seconds = (child.trigger_time - datetime.now()).total_seconds()
                if wait_seconds > 0:
                    time.sleep(wait_seconds)
            
            # 路由到券商
            self.route(child)
            
            # 监控执行
            self.monitor.watch(child)
            
            filled_children.append(child)
            
            # 更新父订单状态
            order.filled_quantity += child.quantity
        
        # 生成执行报告
        report = ExecutionReport(
            order_id=order.order_id,
            parent_order=order,
            child_orders=filled_children,
            total_filled=order.filled_quantity,
            avg_fill_price=self._calculate_avg_fill_price(filled_children),
            vwap=self._calculate_vwap(filled_children),
            market_impact_cost=self._estimate_impact_cost(order, filled_children),
            slippage_cost=self._estimate_slippage_cost(order, filled_children),
            opportunity_cost=self._estimate_opportunity_cost(order, filled_children),
            total_cost=0,  # 待计算
            arrival_price=order.current_price,
            implementation_shortfall=self._calculate_is(order, filled_children)
        )
        
        report.total_cost = (
            report.market_impact_cost +
            report.slippage_cost +
            report.opportunity_cost
        )
        
        # 记录绩效
        self.performance_tracker.record(report)
        
        return report
    
    def _auto_select_algorithm(self, order: ParentOrder) -> str:
        """
        根据订单特征自动选择最优算法
        
        决策逻辑:
        - 小单 (<1% ADV): 直接限价单
        - 中单 (1-10% ADV): TWAP/VWAP
        - 大单 (>10% ADV): POV/Iceberg
        - 紧急: Sniper/IOC
        """
        adv = order.avg_daily_volume or 0
        if adv == 0:
            return 'twap'
        
        participation = order.total_quantity / adv
        
        if order.urgency > 0.8:
            return 'sniper'
        elif participation < 0.01:
            return 'twap'
        elif participation < 0.1:
            return 'vwap'
        elif participation < 0.3:
            return 'pov'
        else:
            return 'iceberg'
    
    def _get_algorithm_instance(self, algo_name: str, order: ParentOrder):
        """获取算法实例"""
        # 动态导入算法类
        algo_module = globals()[self.ALGORITHMS[algo_name]]
        return algo_module(order)
    
    def risk_check(self, child_order: ChildOrder) -> bool:
        """风控检查"""
        return self.risk_checker.check(child_order)
    
    def route(self, child_order: ChildOrder):
        """订单路由"""
        return self.order_router.route(child_order)
    
    def monitor(self, child_order: ChildOrder):
        """监控执行"""
        return self.monitor.watch(child_order)


### 2.4.2 具体执行算法实现

```python
# execution_algorithms.py

class ExecutionAlgorithm:
    """执行算法基类"""
    
    def __init__(self, parent_order: ParentOrder):
        self.parent_order = parent_order
        
    def split(self, order: ParentOrder) -> List[ChildOrder]:
        """拆单逻辑，子类实现"""
        raise NotImplementedError
    
    def adjust(self, market_conditions: Dict):
        """根据市场条件调整，子类可选实现"""
        pass


class TWAPAlgorithm(ExecutionAlgorithm):
    """
    TWAP (Time-Weighted Average Price)
    时间加权均价算法
    
    将订单均匀拆分到时间窗口内，追求时间平均价
    """
    def __init__(self, parent_order: ParentOrder, n_slices: int = None):
        super().__init__(parent_order)
        
        # 默认拆单数：根据紧急度和订单大小
        if n_slices is None:
            if parent_order.urgency > 0.7:
                self.n_slices = max(5, int(parent_order.total_quantity / 10000))
            else:
                self.n_slices = max(10, int(parent_order.total_quantity / 5000))
        else:
            self.n_slices = n_slices
    
    def split(self, order: ParentOrder) -> List[ChildOrder]:
        """TWAP拆单"""
        child_orders = []
        
        # 确定时间窗口
        start_time = order.start_time or datetime.now()
        end_time = order.end_time or (start_time + timedelta(hours=4))
        
        # 计算时间间隔
        total_seconds = (end_time - start_time).total_seconds()
        interval = total_seconds / self.n_slices
        
        # 等分数量
        base_qty = order.total_quantity // self.n_slices
        remainder = order.total_quantity % self.n_slices
        
        for i in range(self.n_slices):
            # 计算数量 (余数分配到前几个)
            qty = base_qty + (1 if i < remainder else 0)
            if qty == 0:
                continue
            
            trigger_time = start_time + timedelta(seconds=interval * i)
            
            child = ChildOrder(
                child_id=f"{order.order_id}_T{i+1}",
                parent_id=order.order_id,
                code=order.code,
                side=order.side,
                quantity=qty,
                order_type='limit',
                limit_price=order.current_price,  # TWAP通常用限价
                trigger_time=trigger_time
            )
            child_orders.append(child)
        
        return child_orders


class VWAPAlgorithm(ExecutionAlgorithm):
    """
    VWAP (Volume-Weighted Average Price)
    成交量加权均价算法
    
    根据历史成交量分布，在成交量大的时段多下单
    目标：成交价格接近当日VWAP
    """
    
    def __init__(self, parent_order: ParentOrder):
        super().__init__(parent_order)
        # 加载历史成交量分布 (需预计算)
        self.volume_profile = self._load_volume_profile(order.code)
    
    def _load_volume_profile(self, code: str) -> pd.Series:
        """加载历史成交量分布"""
        # 返回日内各时段的成交量占比
        # 示例: 开盘10% 收盘15% 中间时段75%
        return pd.Series({
            '09:30-10:00': 0.15,
            '10:00-10:30': 0.12,
            '10:30-11:00': 0.10,
            '11:00-11:30': 0.08,
            '13:00-13:30': 0.10,
            '13:30-14:00': 0.12,
            '14:00-14:30': 0.13,
            '14:30-15:00': 0.20,
        })
    
    def split(self, order: ParentOrder) -> List[ChildOrder]:
        """VWAP拆单"""
        child_orders = []
        
        # 根据成交量分布分配订单量
        total_qty = order.total_quantity
        
        for time_slot, volume_pct in self.volume_profile.items():
            qty = int(total_qty * volume_pct)
            if qty == 0:
                continue
            
            # 解析时间
            start_str, _ = time_slot.split('-')
            hour, minute = map(int, start_str.split(':'))
            trigger_time = datetime.now().replace(hour=hour, minute=minute, second=0)
            
            child = ChildOrder(
                child_id=f"{order.order_id}_V{len(child_orders)+1}",
                parent_id=order.order_id,
                code=order.code,
                side=order.side,
                quantity=qty,
                order_type='market',  # VWAP通常用市价单确保成交
                trigger_time=trigger_time
            )
            child_orders.append(child)
        
        return child_orders


class POVAlgorithm(ExecutionAlgorithm):
    """
    POV (Percent of Volume) 跟量算法
    
    根据市场实时成交量动态调整下单速度
    目标：订单占比不超过设定阈值
    """
    
    def __init__(self, parent_order: ParentOrder, target_pov: float = 0.1):
        """
        Args:
            target_pov: 目标参与率 (默认10%)
        """
        super().__init__(parent_order)
        self.target_pov = target_pov
    
    def split(self, order: ParentOrder) -> List[ChildOrder]:
        """POV拆单"""
        # POV是动态算法，先创建初始子订单
        # 实际数量由实时成交量决定
        
        child_orders = []
        
        # 预估需要多少个子订单
        est_slices = max(5, int(order.total_quantity / (order.avg_daily_volume * self.target_pov / 10)))
        
        for i in range(est_slices):
            # 初始数量设为0，实际数量在adjust中确定
            child = ChildOrder(
                child_id=f"{order.order_id}_P{i+1}",
                parent_id=order.order_id,
                code=order.code,
                side=order.side,
                quantity=0,  # 待填充
                order_type='market',
                trigger_time=datetime.now() + timedelta(minutes=i*5)
            )
            child_orders.append(child)
        
        return child_orders
    
    def adjust(self, market_conditions: Dict):
        """根据实时成交量调整"""
        recent_volume = market_conditions.get('recent_volume', 0)
        
        # 计算应下单数量
        target_qty = int(recent_volume * self.target_pov)
        
        # 更新下一个子订单的数量
        # (具体实现依赖状态管理)


class IcebergAlgorithm(ExecutionAlgorithm):
    """
    冰山单 (Iceberg Orders)
    
    只显示部分订单量，隐藏真实意图
    当一个子订单成交后，才显示下一个
    """
    
    def __init__(self, parent_order: ParentOrder, display_size: int = None):
        super().__init__(parent_order)
        
        # 显示数量：通常5-10% 或 固定数量
        if display_size is None:
            self.display_size = max(1000, parent_order.total_quantity // 10)
        else:
            self.display_size = display_size
    
    def split(self, order: ParentOrder) -> List[ChildOrder]:
        """冰山单拆单"""
        child_orders = []
        remaining = order.total_quantity
        
        slice_num = 1
        while remaining > 0:
            # 当前显示数量
            display_qty = min(self.display_size, remaining)
            
            child = ChildOrder(
                child_id=f"{order.order_id}_I{slice_num}",
                parent_id=order.order_id,
                code=order.code,
                side=order.side,
                quantity=display_qty,
                order_type='limit',
                limit_price=order.current_price,
                trigger_time=datetime.now()  # 冰山单连续执行
            )
            child_orders.append(child)
            
            remaining -= display_qty
            slice_num += 1
        
        return child_orders
    
    def on_child_fill(self, child: ChildOrder):
        """当一个子订单成交后，激活下一个"""
        # 冰山单逻辑：成交后才显示下一个订单
        pass


class SniperAlgorithm(ExecutionAlgorithm):
    """
    狙击单 (Sniper Orders)
    
    快速、隐蔽地执行，追求立即成交
    适用于紧急订单或流动性好的股票
    """
    
    def split(self, order: ParentOrder) -> List[ChildOrder]:
        """狙击单拆单"""
        # 狙击单通常不拆单，直接执行
        # 或拆成2-3个IOC (Immediate or Cancel) 订单
        
        child_orders = []
        
        # 拆2-3个IOC订单，从不同券商/通道执行
        n_splits = min(3, max(1, order.total_quantity // 5000))
        base_qty = order.total_quantity // n_splits
        
        for i in range(n_splits):
            qty = base_qty + (order.total_quantity % n_splits if i == 0 else 0)
            
            child = ChildOrder(
                child_id=f"{order.order_id}_S{i+1}",
                parent_id=order.order_id,
                code=order.code,
                side=order.side,
                quantity=qty,
                order_type='ioc',  # Immediate or Cancel
                limit_price=order.current_price * (1.002 if order.side == 'buy' else 0.998),
                trigger_time=datetime.now()
            )
            child_orders.append(child)
        
        return child_orders


class AdaptiveTWAP(ExecutionAlgorithm):
    """
    自适应TWAP
    
    根据实时市场条件动态调整TWAP切片
    - 波动率低时：增加切片大小，加速执行
    - 波动率高时：减小切片大小，降低冲击
    - 流动性好时：提前执行
    - 流动性差时：延后执行
    """
    
    def __init__(self, parent_order: ParentOrder):
        super().__init__(parent_order)
        self.base_slices = max(10, parent_order.total_quantity // 5000)
        self.market_monitor = MarketConditionMonitor()
    
    def split(self, order: ParentOrder) -> List[ChildOrder]:
        """初始拆单"""
        child_orders = []
        
        start_time = order.start_time or datetime.now()
        end_time = order.end_time or (start_time + timedelta(hours=4))
        
        base_qty = order.total_quantity // self.base_slices
        
        for i in range(self.base_slices):
            qty = base_qty + (1 if i < (order.total_quantity % self.base_slices) else 0)
            
            child = ChildOrder(
                child_id=f"{order.order_id}_A{i+1}",
                parent_id=order.order_id,
                code=order.code,
                side=order.side,
                quantity=qty,
                order_type='limit',
                limit_price=order.current_price,
                trigger_time=start_time + timedelta(
                    seconds=(end_time - start_time).total_seconds() * i / self.base_slices
                )
            )
            child_orders.append(child)
        
        return child_orders
    
    def adjust(self, market_conditions: Dict):
        """根据市场条件动态调整"""
        volatility = market_conditions.get('volatility', 0.02)
        spread = market_conditions.get('spread', 0.001)
        volume_imbalance = market_conditions.get('volume_imbalance', 0)
        
        # 波动率调整
        if volatility > 0.03:  # 高波动
            # 减小切片，降低每次冲击
            self._reduce_slice_size(factor=0.7)
        elif volatility < 0.01:  # 低波动
            # 增加切片，加速执行
            self._increase_slice_size(factor=1.3)
        
        # 流动性调整
        if volume_imbalance > 0.6:  # 买方占优
            if self.parent_order.side == 'buy':
                # 不好买，延后执行
                self._delay_execution(minutes=5)
            else:
                # 好卖，提前执行
                self._advance_execution(minutes=5)
    
    def _reduce_slice_size(self, factor: float):
        """减小切片大小"""
        # 实现细节：调整未执行子订单的数量
        pass
    
    def _increase_slice_size(self, factor: float):
        """增加切片大小"""
        pass
    
    def _delay_execution(self, minutes: int):
        """延后执行"""
        pass
    
    def _advance_execution(self, minutes: int):
        """提前执行"""
        pass


### 2.4.3 辅助模块

```python
# execution_utils.py

class ExecutionRiskChecker:
    """执行风控检查"""
    
    def check(self, child_order: ChildOrder) -> bool:
        """
        执行前风控检查
        
        检查项:
        1. 价格是否在涨跌停范围内
        2. 是否超过持仓限制
        3. 是否触发单日交易限额
        4. 是否有异常交易特征
        """
        checks = [
            self._check_price_limit(child_order),
            self._check_position_limit(child_order),
            self._check_daily_limit(child_order),
            self._check_anomaly(child_order)
        ]
        
        return all(checks)
    
    def _check_price_limit(self, order: ChildOrder) -> bool:
        """检查价格是否在涨跌停范围内"""
        # 获取当日涨跌停价格
        # 检查order.limit_price是否在范围内
        return True
    
    def _check_position_limit(self, order: ChildOrder) -> bool:
        """检查持仓限制"""
        # 检查执行后是否超过最大持仓
        return True
    
    def _check_daily_limit(self, order: ChildOrder) -> bool:
        """检查单日交易限额"""
        return True
    
    def _check_anomaly(self, order: ChildOrder) -> bool:
        """检查异常交易特征"""
        return True


class OrderRouter:
    """订单路由"""
    
    def __init__(self):
        self.brokers = {}  # 券商连接
        
    def route(self, child_order: ChildOrder):
        """
        路由订单到最优券商/通道
        
        路由策略:
        1. 智能路由：选择延迟最低/费用最低的券商
        2. 负载均衡：分散到多个券商
        3. 主备切换：主券商失败时切换到备用
        """
        # 选择最优券商
        best_broker = self._select_best_broker(child_order)
        
        # 发送订单
        return best_broker.send_order(child_order)
    
    def _select_best_broker(self, order: ChildOrder) -> 'BrokerConnection':
        """选择最优券商"""
        # 考虑因素: 佣金、延迟、成功率、当前负载
        pass


class ExecutionMonitor:
    """执行监控"""
    
    def __init__(self):
        self.active_orders = {}
        
    def watch(self, child_order: ChildOrder):
        """监控订单执行"""
        self.active_orders[child_order.child_id] = {
            'order': child_order,
            'start_time': datetime.now(),
            'status': 'monitoring'
        }
        
        # 启动监控线程/协程
        # 检查: 是否超时、是否部分成交、是否价格偏离
    
    def on_fill_update(self, child_id: str, filled_qty: int, fill_price: float):
        """处理成交更新"""
        if child_id in self.active_orders:
            self.active_orders[child_id]['filled'] = filled_qty
            self.active_orders[child_id]['avg_price'] = fill_price
    
    def cancel_if_needed(self, child_id: str):
        """必要时撤单"""
        # 价格偏离过大、超时等情况
        pass


class PerformanceTracker:
    """执行绩效追踪"""
    
    def __init__(self):
        self.execution_history = []
        
    def record(self, report: ExecutionReport):
        """记录执行报告"""
        self.execution_history.append(report)
        
    def get_algo_performance_comparison(self) -> pd.DataFrame:
        """
        比较各算法的执行绩效
        
        Returns:
            DataFrame: 各算法的平均滑点、成交率等
        """
        results = []
        
        for algo_name in SmartExecutionEngine.ALGORITHMS.keys():
            algo_reports = [
                r for r in self.execution_history
                if r.parent_order.algo == algo_name
            ]
            
            if algo_reports:
                results.append({
                    'algorithm': algo_name,
                    'avg_slippage_bps': np.mean([r.slippage_cost * 10000 for r in algo_reports]),
                    'avg_fill_rate': np.mean([r.summary()['fill_rate'] for r in algo_reports]),
                    'avg_cost_bps': np.mean([r.total_cost * 10000 for r in algo_reports]),
                    'count': len(algo_reports)
                })
        
        return pd.DataFrame(results)
```

### 2.4.4 成本分析

```python
# execution_cost_analysis.py

def calculate_implementation_shortfall(
    parent_order: ParentOrder,
    child_orders: List[ChildOrder]
) -> float:
    """
    计算实现价差 (Implementation Shortfall)
    
    IS = (实际成交均价 - 决策时价格) / 决策时价格
    
    分解为:
    - 显性成本: 手续费、印花税等
    - 隐性成本: 滑点、市场冲击
    - 机会成本: 未成交部分的损失
    """
    if not child_orders or parent_order.current_price is None:
        return 0.0
    
    decision_price = parent_order.current_price
    
    # 实际成交均价 (VWAP)
    total_value = sum(c.quantity * c.fill_price for c in child_orders if hasattr(c, 'fill_price'))
    total_qty = sum(c.quantity for c in child_orders if hasattr(c, 'fill_price'))
    
    if total_qty == 0:
        return 0.0
    
    actual_vwap = total_value / total_qty
    
    # 实现价差
    if parent_order.side == 'buy':
        is_cost = (actual_vwap - decision_price) / decision_price
    else:
        is_cost = (decision_price - actual_vwap) / decision_price
    
    return is_cost


def analyze_execution_cost(report: ExecutionReport) -> Dict:
    """
    详细执行成本分析
    
    分解为:
    1. 固定成本: 佣金 + 过户费
    2. 税费: 印花税
    3. 滑点成本
    4. 市场冲击成本
    5. 机会成本
    """
    return {
        'fixed_cost_bps': 0,  # 待计算
        'tax_cost_bps': 0,
        'slippage_bps': report.slippage_cost * 10000,
        'impact_bps': report.market_impact_cost * 10000,
        'opportunity_bps': report.opportunity_cost * 10000,
        'total_cost_bps': report.total_cost * 10000,
        'breakdown': {
            'explicit': 0,  # 显性成本
            'implicit': report.slippage_cost + report.market_impact_cost,  # 隐性成本
            'opportunity': report.opportunity_cost
        }
    }
```

### 2.4.5 执行绩效分析

```python
# execution_performance_analyzer.py
import pandas as pd
import numpy as np
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass
class OrderExecutionMetrics:
    """订单执行绩效指标"""
    order_id: str
    code: str
    side: str
    
    # 价格指标
    decision_price: float          # 决策时价格
    avg_fill_price: float          # 成交均价
    market_vwap: float             # 市场VWAP (同期)
    arrival_price: float           # 到达价格
    
    # 成本指标
    slippage_bps: float            # 滑点 (基点)
    impact_cost_bps: float         # 冲击成本 (基点)
    total_cost_bps: float          # 总成本 (基点)
    
    # 时间指标
    submit_time: datetime          # 提交时间
    first_fill_time: datetime      # 首次成交时间
    complete_time: datetime        # 完成时间
    duration_seconds: float        # 执行时长
    
    # 成交质量
    fill_rate: float               # 成交率
    quantity_submitted: int        # 提交数量
    quantity_filled: int           # 成交数量
    
    @property
    def price_deviation_from_vwap(self) -> float:
        """成交均价与市场VWAP偏差"""
        if self.market_vwap == 0:
            return 0
        return (self.avg_fill_price - self.market_vwap) / self.market_vwap * 10000  # bps
    
    @property
    def implementation_shortfall_bps(self) -> float:
        """实现价差 (基点)"""
        if self.decision_price == 0:
            return 0
        if self.side == 'buy':
            return (self.avg_fill_price - self.decision_price) / self.decision_price * 10000
        else:
            return (self.decision_price - self.avg_fill_price) / self.decision_price * 10000


class ExecutionPerformanceAnalyzer:
    """
    执行绩效分析器
    
    统计每笔订单的:
    - 成交均价与市场均价偏差
    - 滑点
    - 冲击成本
    - 成交时长
    """
    
    def __init__(self, market_data_source):
        self.market_data = market_data_source
        self.metrics_history = []
        
    def analyze_order(self, order_report: ExecutionReport) -> OrderExecutionMetrics:
        """
        分析单笔订单执行绩效
        """
        parent = order_report.parent_order
        
        # 获取市场VWAP (订单执行期间)
        market_vwap = self._get_market_vwap_during_execution(
            parent.code,
            order_report.child_orders[0].trigger_time if order_report.child_orders else datetime.now(),
            order_report.child_orders[-1].trigger_time if order_report.child_orders else datetime.now()
        )
        
        # 计算执行时长
        duration = self._calculate_execution_duration(order_report.child_orders)
        
        # 计算滑点
        slippage = self._calculate_slippage(order_report)
        
        metrics = OrderExecutionMetrics(
            order_id=parent.order_id,
            code=parent.code,
            side=parent.side,
            decision_price=parent.current_price or 0,
            avg_fill_price=order_report.avg_fill_price,
            market_vwap=market_vwap,
            arrival_price=parent.current_price or 0,
            slippage_bps=slippage * 10000,
            impact_cost_bps=order_report.market_impact_cost * 10000,
            total_cost_bps=order_report.total_cost * 10000,
            submit_time=parent.start_time or datetime.now(),
            first_fill_time=self._get_first_fill_time(order_report.child_orders),
            complete_time=self._get_complete_time(order_report.child_orders),
            duration_seconds=duration,
            fill_rate=order_report.total_filled / parent.total_quantity if parent.total_quantity > 0 else 0,
            quantity_submitted=parent.total_quantity,
            quantity_filled=order_report.total_filled
        )
        
        self.metrics_history.append(metrics)
        return metrics
    
    def generate_daily_report(self, date: str) -> Dict:
        """
        生成每日执行绩效报告
        """
        day_metrics = [
            m for m in self.metrics_history 
            if m.submit_time.strftime('%Y-%m-%d') == date
        ]
        
        if not day_metrics:
            return {'error': 'No data for date'}
        
        return {
            'date': date,
            'total_orders': len(day_metrics),
            'avg_fill_rate': np.mean([m.fill_rate for m in day_metrics]),
            'avg_slippage_bps': np.mean([m.slippage_bps for m in day_metrics]),
            'avg_impact_cost_bps': np.mean([m.impact_cost_bps for m in day_metrics]),
            'avg_duration_seconds': np.mean([m.duration_seconds for m in day_metrics]),
            'avg_deviation_from_vwap_bps': np.mean([m.price_deviation_from_vwap for m in day_metrics]),
            
            # 分位数统计
            'slippage_p50': np.percentile([m.slippage_bps for m in day_metrics], 50),
            'slippage_p90': np.percentile([m.slippage_bps for m in day_metrics], 90),
            'slippage_p99': np.percentile([m.slippage_bps for m in day_metrics], 99),
            
            # 按算法分组
            'by_algorithm': self._group_by_algorithm(day_metrics),
            
            # 异常订单
            'anomalous_orders': self._identify_anomalous_orders(day_metrics)
        }
    
    def _get_market_vwap_during_execution(self, code: str, start: datetime, end: datetime) -> float:
        """获取执行期间市场VWAP"""
        market_data = self.market_data.get_intraday_data(code, start, end)
        if market_data.empty:
            return 0
        return (market_data['price'] * market_data['volume']).sum() / market_data['volume'].sum()
    
    def _calculate_execution_duration(self, child_orders: List) -> float:
        """计算执行时长(秒)"""
        if not child_orders:
            return 0
        start = min(o.trigger_time for o in child_orders if o.trigger_time)
        end = max(o.trigger_time for o in child_orders if o.trigger_time)
        return (end - start).total_seconds()
    
    def _calculate_slippage(self, report: ExecutionReport) -> float:
        """计算滑点"""
        if report.arrival_price == 0:
            return 0
        if report.parent_order.side == 'buy':
            return (report.avg_fill_price - report.arrival_price) / report.arrival_price
        else:
            return (report.arrival_price - report.avg_fill_price) / report.arrival_price
    
    def _identify_anomalous_orders(self, metrics: List[OrderExecutionMetrics]) -> List[Dict]:
        """识别异常订单"""
        anomalous = []
        
        for m in metrics:
            issues = []
            
            # 高滑点
            if abs(m.slippage_bps) > 50:  # 超过50bps
                issues.append(f'High slippage: {m.slippage_bps:.1f} bps')
            
            # 长时间未成交
            if m.duration_seconds > 300:  # 超过5分钟
                issues.append(f'Long duration: {m.duration_seconds:.0f}s')
            
            # 低成交率
            if m.fill_rate < 0.8:
                issues.append(f'Low fill rate: {m.fill_rate:.1%}')
            
            # 价格偏离过大
            if abs(m.price_deviation_from_vwap) > 30:
                issues.append(f'Large VWAP deviation: {m.price_deviation_from_vwap:.1f} bps')
            
            if issues:
                anomalous.append({
                    'order_id': m.order_id,
                    'code': m.code,
                    'issues': issues,
                    'metrics': {
                        'slippage_bps': m.slippage_bps,
                        'duration_seconds': m.duration_seconds,
                        'fill_rate': m.fill_rate
                    }
                })
        
        return anomalous
    
    def benchmark_against_market(self, window_days: int = 30) -> Dict:
        """
        与市场基准对比
        
        对比自己的执行绩效 vs 市场平均水平
        """
        recent_metrics = self.metrics_history[-window_days * 100:]  # 假设每天100单
        
        return {
            'our_avg_slippage': np.mean([m.slippage_bps for m in recent_metrics]),
            'our_avg_duration': np.mean([m.duration_seconds for m in recent_metrics]),
            'market_avg_slippage': 15,  # 假设市场平均15bps
            'vs_market_slippage': (np.mean([m.slippage_bps for m in recent_metrics]) - 15) / 15,
            'assessment': 'Above average' if np.mean([m.slippage_bps for m in recent_metrics]) < 15 else 'Below average'
        }


### 2.4.6 异常订单处理

```python
# exception_order_handler.py
from enum import Enum
from typing import Optional, Callable
import asyncio


class ExceptionType(Enum):
    """异常类型"""
    TIMEOUT = "timeout"                    # 超时未成交
    PRICE_LIMIT_HIT = "price_limit_hit"    # 触发涨跌停
    REJECTED = "rejected"                  # 订单被拒
    PARTIAL_FILL = "partial_fill"          # 部分成交
    PRICE_DRIFT = "price_drift"            # 价格偏离过大
    SYSTEM_ERROR = "system_error"          # 系统错误


class ExceptionOrderHandler:
    """
    异常订单处理器
    
    自动化处理:
    - 超时未成交: 自动撤单重发
    - 涨跌停: 自动调整价格
    - 废单: 自动重试
    """
    
    def __init__(self, execution_engine: SmartExecutionEngine):
        self.engine = execution_engine
        self.max_retries = 3
        self.retry_delay_seconds = 5
        
        # 异常处理策略映射
        self.handlers = {
            ExceptionType.TIMEOUT: self._handle_timeout,
            ExceptionType.PRICE_LIMIT_HIT: self._handle_price_limit,
            ExceptionType.REJECTED: self._handle_rejected,
            ExceptionType.PARTIAL_FILL: self._handle_partial_fill,
            ExceptionType.PRICE_DRIFT: self._handle_price_drift,
            ExceptionType.SYSTEM_ERROR: self._handle_system_error
        }
    
    async def handle_exception(
        self,
        child_order: ChildOrder,
        exception_type: ExceptionType,
        exception_details: Dict
    ) -> Optional[ChildOrder]:
        """
        处理异常订单
        
        Returns:
            新订单(如果重发) 或 None(如果放弃)
        """
        handler = self.handlers.get(exception_type)
        if not handler:
            print(f"[Exception] Unknown exception type: {exception_type}")
            return None
        
        # 获取重试次数
        retry_count = exception_details.get('retry_count', 0)
        
        if retry_count >= self.max_retries:
            print(f"[Exception] Max retries reached for {child_order.child_id}, giving up")
            return None
        
        print(f"[Exception] Handling {exception_type.value} for {child_order.child_id} (retry {retry_count + 1})")
        
        return await handler(child_order, exception_details)
    
    async def _handle_timeout(
        self,
        order: ChildOrder,
        details: Dict
    ) -> Optional[ChildOrder]:
        """
        处理超时未成交
        
        策略:
        1. 撤单
        2. 调整价格(更激进)
        3. 重发
        """
        # 撤单
        await self._cancel_order(order)
        
        # 等待
        await asyncio.sleep(self.retry_delay_seconds)
        
        # 创建新订单，价格更激进
        new_order = ChildOrder(
            child_id=f"{order.child_id}_R{details.get('retry_count', 0) + 1}",
            parent_id=order.parent_id,
            code=order.code,
            side=order.side,
            quantity=order.quantity,
            order_type='ioc',  # 改为IOC，立即成交或取消
            limit_price=self._adjust_price_for_aggression(order),
            trigger_time=datetime.now()
        )
        
        print(f"[TimeoutHandler] Resubmitted {order.child_id} as IOC with aggressive price")
        return new_order
    
    async def _handle_price_limit(
        self,
        order: ChildOrder,
        details: Dict
    ) -> Optional[ChildOrder]:
        """
        处理涨跌停价格调整
        
        策略:
        - 买入遇到涨停: 调整到涨停价排队
        - 卖出遇到跌停: 调整到跌停价排队
        """
        # 获取当日涨跌停价格
        price_limits = self._get_price_limits(order.code)
        
        if order.side == 'buy':
            new_price = price_limits['upper_limit']  # 涨停价
        else:
            new_price = price_limits['lower_limit']  # 跌停价
        
        # 创建新订单
        new_order = ChildOrder(
            child_id=f"{order.child_id}_PL",
            parent_id=order.parent_id,
            code=order.code,
            side=order.side,
            quantity=order.quantity,
            order_type='limit',
            limit_price=new_price,
            trigger_time=datetime.now()
        )
        
        print(f"[PriceLimitHandler] Adjusted {order.child_id} to price limit: {new_price}")
        return new_order
    
    async def _handle_rejected(
        self,
        order: ChildOrder,
        details: Dict
    ) -> Optional[ChildOrder]:
        """
        处理废单重试
        
        策略:
        - 分析拒单原因
        - 针对性修正
        - 重试
        """
        reject_reason = details.get('reason', '')
        
        if 'price' in reject_reason.lower():
            # 价格问题，调整价格
            new_price = self._adjust_price_for_retry(order)
        elif 'quantity' in reject_reason.lower():
            # 数量问题，调整为100的倍数
            new_qty = (order.quantity // 100) * 100
            new_price = order.limit_price
        else:
            # 其他问题，延迟重试
            await asyncio.sleep(self.retry_delay_seconds * 2)
            new_price = order.limit_price
            new_qty = order.quantity
        
        new_order = ChildOrder(
            child_id=f"{order.child_id}_RJ",
            parent_id=order.parent_id,
            code=order.code,
            side=order.side,
            quantity=new_qty if 'new_qty' in dir() else order.quantity,
            order_type=order.order_type,
            limit_price=new_price,
            trigger_time=datetime.now()
        )
        
        print(f"[RejectedHandler] Resubmitting {order.child_id} after rejection: {reject_reason}")
        return new_order
    
    async def _handle_partial_fill(
        self,
        order: ChildOrder,
        details: Dict
    ) -> Optional[ChildOrder]:
        """
        处理部分成交
        
        策略:
        - 对剩余数量发新单
        - 价格根据市场调整
        """
        filled_qty = details.get('filled_quantity', 0)
        remaining_qty = order.quantity - filled_qty
        
        if remaining_qty <= 0:
            return None
        
        # 获取最新市场价格
        current_price = self._get_current_price(order.code)
        
        new_order = ChildOrder(
            child_id=f"{order.child_id}_PF",
            parent_id=order.parent_id,
            code=order.code,
            side=order.side,
            quantity=remaining_qty,
            order_type='limit',
            limit_price=current_price,
            trigger_time=datetime.now()
        )
        
        print(f"[PartialFillHandler] Creating new order for remaining {remaining_qty} shares")
        return new_order
    
    async def _handle_price_drift(
        self,
        order: ChildOrder,
        details: Dict
    ) -> Optional[ChildOrder]:
        """
        处理价格偏离过大
        
        策略:
        - 撤单
        - 按最新市场价格重发
        """
        await self._cancel_order(order)
        
        current_price = self._get_current_price(order.code)
        
        new_order = ChildOrder(
            child_id=f"{order.child_id}_PD",
            parent_id=order.parent_id,
            code=order.code,
            side=order.side,
            quantity=order.quantity,
            order_type='limit',
            limit_price=current_price * (1.001 if order.side == 'buy' else 0.999),
            trigger_time=datetime.now()
        )
        
        print(f"[PriceDriftHandler] Resubmitting at current market price: {current_price}")
        return new_order
    
    async def _handle_system_error(
        self,
        order: ChildOrder,
        details: Dict
    ) -> Optional[ChildOrder]:
        """处理系统错误"""
        # 延迟较长时间后重试
        await asyncio.sleep(self.retry_delay_seconds * 3)
        
        new_order = ChildOrder(
            child_id=f"{order.child_id}_SE",
            parent_id=order.parent_id,
            code=order.code,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
            limit_price=order.limit_price,
            trigger_time=datetime.now()
        )
        
        print(f"[SystemErrorHandler] Resubmitting after system error")
        return new_order
    
    def _adjust_price_for_aggression(self, order: ChildOrder) -> float:
        """调整为更激进的价格"""
        current_price = self._get_current_price(order.code)
        
        if order.side == 'buy':
            # 买：提高价格
            return current_price * 1.002
        else:
            # 卖：降低价格
            return current_price * 0.998
    
    def _adjust_price_for_retry(self, order: ChildOrder) -> float:
        """为重试调整价格"""
        if order.limit_price is None:
            return self._get_current_price(order.code)
        
        # 微幅调整
        if order.side == 'buy':
            return order.limit_price * 1.001
        else:
            return order.limit_price * 0.999
    
    async def _cancel_order(self, order: ChildOrder):
        """撤单"""
        # 调用券商API撤单
        pass
    
    def _get_price_limits(self, code: str) -> Dict:
        """获取涨跌停价格"""
        # 从市场数据获取
        return {'upper_limit': 0, 'lower_limit': 0}
    
    def _get_current_price(self, code: str) -> float:
        """获取当前价格"""
        # 从市场数据获取
        return 0.0


class OrderWatcher:
    """
    订单监控器
    
    实时监控订单状态，自动触发异常处理
    """
    def __init__(self, exception_handler: ExceptionOrderHandler):
        self.handler = exception_handler
        self.watching_orders = {}
        self.timeout_threshold_seconds = 60  # 60秒超时
        self.price_drift_threshold_bps = 50   # 50bps价格偏离
        
    async def watch(self, order: ChildOrder):
        """开始监控订单"""
        self.watching_orders[order.child_id] = {
            'order': order,
            'submit_time': datetime.now(),
            'last_price': order.limit_price,
            'status': 'watching'
        }
        
        # 启动监控任务
        asyncio.create_task(self._monitor_order(order))
    
    async def _monitor_order(self, order: ChildOrder):
        """监控单个订单"""
        while order.child_id in self.watching_orders:
            await asyncio.sleep(5)  # 每5秒检查一次
            
            info = self.watching_orders[order.child_id]
            
            # 检查超时
            elapsed = (datetime.now() - info['submit_time']).total_seconds()
            if elapsed > self.timeout_threshold_seconds:
                if info['status'] != 'filled':
                    await self.handler.handle_exception(
                        order, 
                        ExceptionType.TIMEOUT,
                        {'retry_count': 0}
                    )
                    break
            
            # 检查价格偏离
            current_price = self._get_current_price(order.code)
            if current_price and info['last_price']:
                drift_bps = abs(current_price - info['last_price']) / info['last_price'] * 10000
                if drift_bps > self.price_drift_threshold_bps:
                    await self.handler.handle_exception(
                        order,
                        ExceptionType.PRICE_DRIFT,
                        {'drift_bps': drift_bps}
                    )
                    break
    
    def on_fill(self, child_id: str, fill_qty: int, fill_price: float):
        """成交回调"""
        if child_id in self.watching_orders:
            info = self.watching_orders[child_id]
            info['filled_quantity'] = info.get('filled_quantity', 0) + fill_qty
            
            # 检查是否完全成交
            if info['filled_quantity'] >= info['order'].quantity:
                info['status'] = 'filled'
                del self.watching_orders[child_id]
            else:
                info['status'] = 'partial_fill'
    
    def _get_current_price(self, code: str) -> float:
        """获取当前价格"""
        return 0.0
```

---

*Module: Smart Order Execution Engine*  
*Sub-module: 2.4*  
*Status: 详细设计记录*
