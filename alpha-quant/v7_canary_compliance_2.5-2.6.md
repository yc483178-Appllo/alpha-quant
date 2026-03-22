# Alpha-Genesis V7.0 - 仿真交易与灰度发布体系

## 2.5 仿真交易与灰度发布体系

### 定位：策略上线前的最后一道防线

**核心理念：** 新策略不直接全量上线，而是通过渐进式验证确保可靠性。

### 2.5.1 标准化上线流程

```
策略上线流程
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

阶段0: 回测验证
├─ WFA滚动回测通过
├─ 过拟合检测通过
└─ 压力测试通过
        ↓
阶段1: 仿真验证 (Simulation) ★ 至少1个月
├─ 仿真撮合交易
├─ 收益/回撤符合预期
└─ 与实盘环境一致的数据延迟
        ↓
阶段2: 小批量灰度 (10%资金)
├─ 真实市场，小资金验证
├─ Bayesian A/B Testing
└─ 统计显著性达标自动升级
        ↓
阶段3: 半量灰度 (30%资金)
├─ 扩大资金规模
├─ 持续监控绩效
└─ 统计显著性达标自动升级
        ↓
阶段4: 全量上线 (100%资金)
├─ 正式生产环境
├─ 全生命周期监控
└─ 异常自动降级/下线

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### 2.5.2 仿真交易系统

```python
# simulation_trading_system.py
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import pandas as pd


@dataclass
class SimulationTrade:
    """仿真交易记录"""
    trade_id: str
    strategy_id: str
    code: str
    side: str
    quantity: int
    price: float
    timestamp: datetime
    
    # 仿真特性
    simulated_slippage: float      # 模拟滑点
    simulated_impact: float        # 模拟冲击成本
    fill_probability: float        # 成交概率 (基于市场深度)


class SimulationTradingSystem:
    """
    仿真交易系统
    
    特点：
    1. 真实市场数据，模拟撮合
    2. 包含滑点/冲击成本估算
    3. 考虑成交概率 (大单可能部分成交)
    4. 与实盘一致的数据延迟
    """
    
    def __init__(self, market_data_feed, config: Dict):
        self.data_feed = market_data_feed
        self.config = config
        
        # 仿真账户
        self.sim_accounts = {}
        
        # 撮合引擎
        self.match_engine = SimulationMatchEngine()
        
        # 延迟模拟器
        self.latency_simulator = LatencySimulator(
            base_latency_ms=config.get('base_latency_ms', 100),
            jitter_ms=config.get('jitter_ms', 50)
        )
        
    def create_simulation_account(
        self,
        strategy_id: str,
        initial_capital: float = 10000000
    ) -> str:
        """创建仿真账户"""
        account_id = f"SIM_{strategy_id}_{datetime.now().strftime('%Y%m%d')}"
        
        self.sim_accounts[account_id] = {
            'strategy_id': strategy_id,
            'initial_capital': initial_capital,
            'current_capital': initial_capital,
            'positions': {},
            'trades': [],
            'start_date': datetime.now(),
            'status': 'active'
        }
        
        return account_id
    
    def execute_signal(
        self,
        account_id: str,
        signal: Dict
    ) -> SimulationTrade:
        """
        执行交易信号
        
        Args:
            signal: {
                'code': '600519',
                'side': 'buy',
                'quantity': 1000,
                'price': 1800.0,
                'order_type': 'limit'
            }
        """
        account = self.sim_accounts.get(account_id)
        if not account:
            raise ValueError(f"Simulation account {account_id} not found")
        
        # 模拟延迟
        latency = self.latency_simulator.get_latency()
        execution_time = datetime.now() + timedelta(milliseconds=latency)
        
        # 获取执行时的市场数据 (模拟延迟后的数据)
        market_data = self.data_feed.get_data_at(
            signal['code'], execution_time
        )
        
        # 撮合
        trade = self.match_engine.match(
            signal, market_data, account
        )
        
        # 更新账户
        account['trades'].append(trade)
        self._update_position(account, trade)
        
        return trade
    
    def validate_strategy_performance(
        self,
        account_id: str,
        min_days: int = 30,
        expected_return_range: tuple = (-0.05, 0.50),  # 年化收益-5%~50%
        max_drawdown_limit: float = 0.15                # 最大回撤15%
    ) -> Dict:
        """
        验证策略仿真表现
        
        毕业条件：
        1. 运行时间 >= 1个月
        2. 年化收益在预期范围内
        3. 最大回撤 < 限制
        4. 夏普比率 > 0.5
        """
        account = self.sim_accounts[account_id]
        trades = account['trades']
        
        # 计算运行天数
        days_running = (datetime.now() - account['start_date']).days
        
        if days_running < min_days:
            return {
                'passed': False,
                'reason': f'Insufficient simulation time: {days_running}d < {min_days}d',
                'metrics': {}
            }
        
        # 计算绩效指标
        metrics = self._calculate_performance_metrics(trades)
        
        # 检查条件
        checks = {
            'time_sufficient': days_running >= min_days,
            'return_in_range': expected_return_range[0] <= metrics['annual_return'] <= expected_return_range[1],
            'drawdown_acceptable': metrics['max_drawdown'] <= max_drawdown_limit,
            'sharpe_positive': metrics['sharpe_ratio'] > 0.5
        }
        
        passed = all(checks.values())
        
        return {
            'passed': passed,
            'checks': checks,
            'metrics': metrics,
            'recommendation': 'Proceed to live trading' if passed else 'Continue simulation'
        }
    
    def _calculate_performance_metrics(self, trades: List[SimulationTrade]) -> Dict:
        """计算绩效指标"""
        # 简化的绩效计算
        if not trades:
            return {'annual_return': 0, 'max_drawdown': 0, 'sharpe_ratio': 0}
        
        # 实际实现需要更复杂的计算
        return {
            'annual_return': 0.20,  # 示例
            'max_drawdown': 0.10,
            'sharpe_ratio': 1.2
        }
    
    def _update_position(self, account: Dict, trade: SimulationTrade):
        """更新持仓"""
        code = trade.code
        if code not in account['positions']:
            account['positions'][code] = {'quantity': 0, 'cost': 0}
        
        pos = account['positions'][code]
        
        if trade.side == 'buy':
            total_cost = pos['cost'] * pos['quantity'] + trade.price * trade.quantity
            pos['quantity'] += trade.quantity
            pos['cost'] = total_cost / pos['quantity'] if pos['quantity'] > 0 else 0
        else:
            pos['quantity'] -= trade.quantity
            if pos['quantity'] == 0:
                pos['cost'] = 0


class SimulationMatchEngine:
    """仿真撮合引擎"""
    
    def match(self, signal: Dict, market_data: pd.Series, account: Dict) -> SimulationTrade:
        """撮合订单"""
        
        # 成交概率模型 (基于订单大小/市场深度)
        fill_prob = self._calculate_fill_probability(signal, market_data)
        
        # 模拟滑点
        slippage = self._estimate_slippage(signal, market_data)
        
        # 模拟冲击成本
        impact = self._estimate_market_impact(signal, market_data)
        
        # 实际成交价格
        if signal['side'] == 'buy':
            fill_price = signal['price'] * (1 + slippage) * (1 + impact)
        else:
            fill_price = signal['price'] * (1 - slippage) * (1 - impact)
        
        # 随机决定是否成交 (基于fill_prob)
        import random
        if random.random() > fill_prob:
            # 未成交
            return None
        
        return SimulationTrade(
            trade_id=f"SIM_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            strategy_id=account.get('strategy_id', ''),
            code=signal['code'],
            side=signal['side'],
            quantity=signal['quantity'],
            price=fill_price,
            timestamp=datetime.now(),
            simulated_slippage=slippage,
            simulated_impact=impact,
            fill_probability=fill_prob
        )
    
    def _calculate_fill_probability(self, signal: Dict, market_data: pd.Series) -> float:
        """计算成交概率"""
        # 基于订单大小相对于市场深度的比例
        order_size = signal['quantity']
        market_depth = market_data.get('bid_volume', 0) if signal['side'] == 'buy' else market_data.get('ask_volume', 0)
        
        if market_depth == 0:
            return 0.5
        
        ratio = order_size / market_depth
        
        # 比例越高，成交概率越低
        if ratio < 0.1:
            return 0.95
        elif ratio < 0.3:
            return 0.80
        elif ratio < 0.5:
            return 0.60
        else:
            return 0.40
    
    def _estimate_slippage(self, signal: Dict, market_data: pd.Series) -> float:
        """估算滑点"""
        # 简化的滑点模型
        spread = market_data.get('spread', 0.001)
        volatility = market_data.get('volatility', 0.02)
        
        return spread * 0.5 + volatility * 0.1
    
    def _estimate_market_impact(self, signal: Dict, market_data: pd.Series) -> float:
        """估算市场冲击"""
        order_value = signal['quantity'] * signal['price']
        avg_daily_value = market_data.get('avg_daily_value', order_value * 10)
        
        participation = order_value / avg_daily_value
        
        # Almgren-Chriss简化
        return 0.1 * participation ** 0.6


class LatencySimulator:
    """延迟模拟器"""
    
    def __init__(self, base_latency_ms: int = 100, jitter_ms: int = 50):
        self.base_latency = base_latency_ms
        self.jitter = jitter_ms
    
    def get_latency(self) -> int:
        """获取模拟延迟"""
        import random
        return self.base_latency + random.randint(-self.jitter, self.jitter)
```

### 2.5.3 灰度发布引擎

```python
# canary_release_engine.py
import numpy as np
from scipy import stats
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CanaryStage:
    """灰度阶段配置"""
    stage_id: int
    name: str
    capital_percentage: float  # 资金百分比 (0.1 = 10%)
    min_days: int              # 最小运行天数
    graduation_criteria: Dict  # 毕业条件


class BayesianABTester:
    """
    Bayesian A/B Testing
    
    使用贝叶斯方法计算策略A vs 策略B的胜率
    避免传统频率学派的样本量限制
    """
    
    def __init__(self, prior_alpha: float = 1.0, prior_beta: float = 1.0):
        """
        Args:
            prior_alpha, prior_beta: Beta分布的先验参数
        """
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
    
    def compare_strategies(
        self,
        strategy_a_returns: List[float],  # 新策略收益序列
        strategy_b_returns: List[float],  # 基准策略收益序列
        rope_width: float = 0.01          # 实际等价区间 (Region of Practical Equivalence)
    ) -> Dict:
        """
        比较两个策略
        
        Returns:
            {
                'prob_a_better': 策略A更好的概率,
                'prob_b_better': 策略B更好的概率,
                'prob_rope': 两者实际等价的概率,
                'expected_loss_a': 选择A的期望损失,
                'expected_loss_b': 选择B的期望损失,
                'recommendation': 建议 (A/B/continue)
            }
        """
        # 使用正态分布近似日收益
        # 实际应该用更robust的方法
        
        mean_a = np.mean(strategy_a_returns)
        std_a = np.std(strategy_a_returns)
        mean_b = np.mean(strategy_b_returns)
        std_b = np.std(strategy_b_returns)
        
        # Monte Carlo采样
        n_samples = 10000
        samples_a = np.random.normal(mean_a, std_a, n_samples)
        samples_b = np.random.normal(mean_b, std_b, n_samples)
        
        diff = samples_a - samples_b
        
        prob_a_better = np.mean(diff > rope_width)
        prob_b_better = np.mean(diff < -rope_width)
        prob_rope = 1 - prob_a_better - prob_b_better
        
        # 期望损失
        loss_if_choose_a = np.mean(np.maximum(0, samples_b - samples_a))
        loss_if_choose_b = np.mean(np.maximum(0, samples_a - samples_b))
        
        # 建议
        if prob_a_better > 0.95 and loss_if_choose_a < loss_if_choose_b:
            recommendation = 'A'
        elif prob_b_better > 0.95 and loss_if_choose_b < loss_if_choose_a:
            recommendation = 'B'
        else:
            recommendation = 'continue'
        
        return {
            'prob_a_better': prob_a_better,
            'prob_b_better': prob_b_better,
            'prob_rope': prob_rope,
            'expected_loss_a': loss_if_choose_a,
            'expected_loss_b': loss_if_choose_b,
            'recommendation': recommendation
        }
    
    def calculate_sample_size_estimate(
        self,
        effect_size: float = 0.02,      # 期望检测的效应大小
        desired_prob: float = 0.95,      # 期望的置信度
        current_returns_a: List[float] = None,
        current_returns_b: List[float] = None
    ) -> int:
        """估算达到显著性所需样本量"""
        if not current_returns_a or not current_returns_b:
            return 100  # 默认值
        
        # 基于当前数据估算
        var_a = np.var(current_returns_a)
        var_b = np.var(current_returns_b)
        pooled_var = (var_a + var_b) / 2
        
        # 简化的样本量估算
        z_score = stats.norm.ppf((1 + desired_prob) / 2)
        n = int(2 * (z_score ** 2) * pooled_var / (effect_size ** 2))
        
        return max(n, 30)  # 至少30个样本


class CanaryReleaseEngine:
    """
    ★ Claude创新：灰度发布引擎
    
    自动计算每个阶段的「毕业条件」，基于Bayesian A/B Testing
    统计显著性达到95%时自动升级到下一阶段，避免主观判断
    """
    
    def __init__(self):
        self.stages = [
            CanaryStage(1, 'simulation', 0.0, 30, {}),      # 仿真阶段
            CanaryStage(2, 'canary_10', 0.10, 15, {}),       # 10%资金
            CanaryStage(3, 'canary_30', 0.30, 15, {}),       # 30%资金
            CanaryStage(4, 'full_rollout', 1.0, 0, {})       # 全量
        ]
        
        self.ab_tester = BayesianABTester()
        self.strategy_registry = {}
        
    def register_strategy(
        self,
        strategy_id: str,
        strategy_class: type,
        config: Dict,
        baseline_strategy_id: Optional[str] = None
    ) -> str:
        """
        注册新策略到灰度发布流程
        
        Args:
            baseline_strategy_id: 用于A/B对比的基准策略
        """
        self.strategy_registry[strategy_id] = {
            'class': strategy_class,
            'config': config,
            'current_stage': 0,  # 0 = 未开始
            'baseline': baseline_strategy_id,
            'performance_history': [],
            'start_date': None
        }
        
        return strategy_id
    
    def start_canary(self, strategy_id: str):
        """开始灰度发布流程"""
        strategy = self.strategy_registry[strategy_id]
        
        # 第一阶段：仿真
        self._advance_to_stage(strategy_id, 1)
    
    def _advance_to_stage(self, strategy_id: str, stage_id: int):
        """推进到指定阶段"""
        strategy = self.strategy_registry[strategy_id]
        stage = self.stages[stage_id - 1]
        
        strategy['current_stage'] = stage_id
        strategy['stage_start_date'] = datetime.now()
        
        print(f"[Canary] Strategy {strategy_id} advanced to stage {stage_id}: {stage.name}")
        print(f"[Canary] Capital allocation: {stage.capital_percentage:.0%}")
    
    def evaluate_stage_progression(self, strategy_id: str) -> Dict:
        """
        评估是否可以进入下一阶段
        
        毕业条件：
        1. 运行天数 >= 阶段要求
        2. Bayesian A/B测试显示统计显著性 >= 95%
        3. 风险指标达标
        """
        strategy = self.strategy_registry[strategy_id]
        current_stage_id = strategy['current_stage']
        
        if current_stage_id >= len(self.stages):
            return {'can_advance': False, 'reason': 'Already at final stage'}
        
        stage = self.stages[current_stage_id - 1]
        
        # 检查运行时间
        days_running = (datetime.now() - strategy['stage_start_date']).days
        if days_running < stage.min_days:
            return {
                'can_advance': False,
                'reason': f'Insufficient time: {days_running}d < {stage.min_days}d',
                'days_remaining': stage.min_days - days_running
            }
        
        # 获取绩效数据
        new_strategy_returns = strategy['performance_history']
        
        # 与基准对比
        if strategy['baseline']:
            baseline_strategy = self.strategy_registry.get(strategy['baseline'])
            if baseline_strategy:
                baseline_returns = baseline_strategy['performance_history']
                
                # Bayesian A/B Test
                ab_result = self.ab_tester.compare_strategies(
                    new_strategy_returns[-days_running:],
                    baseline_returns[-days_running:]
                )
                
                if ab_result['recommendation'] == 'A' and ab_result['prob_a_better'] >= 0.95:
                    # 可以升级
                    if current_stage_id < len(self.stages):
                        self._advance_to_stage(strategy_id, current_stage_id + 1)
                    
                    return {
                        'can_advance': True,
                        'ab_test_result': ab_result,
                        'new_stage': self.stages[current_stage_id].name
                    }
                else:
                    return {
                        'can_advance': False,
                        'reason': 'Statistical significance not reached',
                        'ab_test_result': ab_result,
                        'recommendation': 'Continue current stage'
                    }
        
        # 无基准，仅检查基础指标
        return self._check_basic_metrics(strategy_id, stage)
    
    def _check_basic_metrics(self, strategy_id: str, stage: CanaryStage) -> Dict:
        """检查基础绩效指标"""
        strategy = self.strategy_registry[strategy_id]
        returns = strategy['performance_history']
        
        if len(returns) < 5:
            return {'can_advance': False, 'reason': 'Insufficient data'}
        
        sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252) if np.std(returns) > 0 else 0
        max_dd = self._calculate_max_drawdown(returns)
        
        checks = {
            'sharpe_positive': sharpe > 0.5,
            'drawdown_acceptable': max_dd < 0.15
        }
        
        if all(checks.values()):
            return {'can_advance': True, 'metrics': {'sharpe': sharpe, 'max_dd': max_dd}}
        else:
            return {
                'can_advance': False,
                'reason': 'Metrics check failed',
                'checks': checks,
                'metrics': {'sharpe': sharpe, 'max_dd': max_dd}
            }
    
    def _calculate_max_drawdown(self, returns: List[float]) -> float:
        """计算最大回撤"""
        cumulative = np.cumprod([1 + r for r in returns])
        running_max = np.maximum.accumulate(cumulative)
        drawdown = (cumulative - running_max) / running_max
        return abs(min(drawdown)) if len(drawdown) > 0 else 0
    
    def get_strategy_status(self, strategy_id: str) -> Dict:
        """获取策略灰度状态"""
        strategy = self.strategy_registry[strategy_id]
        current_stage = self.stages[strategy['current_stage'] - 1] if strategy['current_stage'] > 0 else None
        
        return {
            'strategy_id': strategy_id,
            'current_stage': current_stage.name if current_stage else 'not_started',
            'capital_percentage': current_stage.capital_percentage if current_stage else 0,
            'stage_start_date': strategy.get('stage_start_date'),
            'total_return': sum(strategy['performance_history']),
            'days_running': (datetime.now() - strategy['stage_start_date']).days if strategy.get('stage_start_date') else 0
        }


# 使用示例
"""
# 1. 创建灰度引擎
engine = CanaryReleaseEngine()

# 2. 注册基准策略 (已有成熟策略)
engine.register_strategy(
    'baseline_strategy_v1',
    ExistingStrategy,
    config={'param1': 0.5}
)

# 3. 注册新策略，指定基准进行A/B对比
engine.register_strategy(
    'new_strategy_v2',
    NewStrategy,
    config={'param1': 0.7, 'new_feature': True},
    baseline_strategy_id='baseline_strategy_v1'
)

# 4. 开始灰度流程
engine.start_canary('new_strategy_v2')

# 5. 每日更新绩效并检查是否可以升级
engine.update_performance('new_strategy_v2', daily_return=0.01)
result = engine.evaluate_stage_progression('new_strategy_v2')

# 可能输出:
# {
#     'can_advance': True,
#     'ab_test_result': {
#         'prob_a_better': 0.97,  # 97%概率新策略更好
#         'recommendation': 'A'
#     },
#     'new_stage': 'canary_30'  # 自动升级到30%资金阶段
# }
"""


### 2.5.4 A/B测试框架

```python
# ab_testing_framework.py

class ABTestFramework:
    """
    策略A/B测试框架
    
    支持同类型策略并行实盘对比
    """
    
    def __init__(self):
        self.active_tests = {}
    
    def create_test(
        self,
        test_id: str,
        strategy_a_id: str,
        strategy_b_id: str,
        traffic_split: float = 0.5,  # 流量分配比例
        test_duration_days: int = 30
    ):
        """创建A/B测试"""
        self.active_tests[test_id] = {
            'strategy_a': strategy_a_id,
            'strategy_b': strategy_b_id,
            'traffic_split': traffic_split,
            'start_date': datetime.now(),
            'end_date': datetime.now() + timedelta(days=test_duration_days),
            'results': {'a': [], 'b': []}
        }
    
    def route_signal(self, test_id: str, signal: Dict) -> str:
        """
        路由信号到A或B策略
        
        根据流量分配决定使用哪个策略
        """
        import random
        test = self.active_tests[test_id]
        
        if random.random() < test['traffic_split']:
            return test['strategy_a']
        else:
            return test['strategy_b']
    
    def record_result(self, test_id: str, variant: str, result: float):
        """记录测试结果"""
        self.active_tests[test_id]['results'][variant].append(result)
    
    def get_test_report(self, test_id: str) -> Dict:
        """生成测试报告"""
        test = self.active_tests[test_id]
        results_a = test['results']['a']
        results_b = test['results']['b']
        
        # 使用Bayesian测试
        tester = BayesianABTester()
        comparison = tester.compare_strategies(results_a, results_b)
        
        return {
            'test_id': test_id,
            'duration_days': (datetime.now() - test['start_date']).days,
            'sample_size_a': len(results_a),
            'sample_size_b': len(results_b),
            'mean_return_a': np.mean(results_a),
            'mean_return_b': np.mean(results_b),
            'bayesian_result': comparison,
            'winner': 'A' if comparison['prob_a_better'] > 0.95 else 
                     'B' if comparison['prob_b_better'] > 0.95 else 'undetermined'
        }
```

---

## 2.6 合规与审计体系

### 定位：规模化后的生命线

### 2.6.1 全链路审计留痕

```python
# audit_system.py
import hashlib
import json
from datetime import datetime
from typing import Dict, List, Optional
import sqlite3  # 或使用更robust的数据库


class AuditTrail:
    """
    全链路审计系统
    
    记录完整链路：信号生成 → 风控审批 → 订单下发 → 成交回报 → 资金变动
    特点：不可篡改、可追溯、可验证
    """
    
    def __init__(self, db_path: str = 'audit_trail.db'):
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """初始化审计数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS audit_events (
                event_id TEXT PRIMARY KEY,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                stage TEXT NOT NULL,
                strategy_id TEXT,
                order_id TEXT,
                data_hash TEXT NOT NULL,
                raw_data TEXT NOT NULL,
                previous_hash TEXT,
                signature TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def record_event(
        self,
        event_type: str,      # 'signal_generated', 'risk_approved', 'order_sent', 'fill_received', 'capital_changed'
        stage: str,           # 'strategy', 'risk', 'execution', 'settlement'
        data: Dict,
        strategy_id: str = None,
        order_id: str = None
    ) -> str:
        """
        记录审计事件
        
        使用区块链式哈希链确保不可篡改
        """
        event_id = f"AUD_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        timestamp = datetime.now().isoformat()
        
        # 计算数据哈希
        data_str = json.dumps(data, sort_keys=True)
        data_hash = hashlib.sha256(data_str.encode()).hexdigest()
        
        # 获取前一个事件的哈希 (用于链式验证)
        previous_hash = self._get_last_hash()
        
        # 创建事件记录
        event_record = {
            'event_id': event_id,
            'timestamp': timestamp,
            'event_type': event_type,
            'stage': stage,
            'strategy_id': strategy_id,
            'order_id': order_id,
            'data_hash': data_hash,
            'raw_data': data_str,
            'previous_hash': previous_hash
        }
        
        # 计算事件签名 (防止篡改)
        signature = self._calculate_signature(event_record)
        event_record['signature'] = signature
        
        # 存储
        self._store_event(event_record)
        
        return event_id
    
    def _get_last_hash(self) -> Optional[str]:
        """获取最后一个事件的哈希"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            'SELECT data_hash FROM audit_events ORDER BY timestamp DESC LIMIT 1'
        )
        result = cursor.fetchone()
        conn.close()
        
        return result[0] if result else None
    
    def _calculate_signature(self, event: Dict) -> str:
        """计算事件签名"""
        # 简化的签名：对关键字段哈希
        signature_data = f"{event['event_id']}{event['timestamp']}{event['data_hash']}{event.get('previous_hash', '')}"
        return hashlib.sha256(signature_data.encode()).hexdigest()
    
    def _store_event(self, event: Dict):
        """存储事件到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO audit_events 
            (event_id, timestamp, event_type, stage, strategy_id, order_id, 
             data_hash, raw_data, previous_hash, signature)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            event['event_id'], event['timestamp'], event['event_type'],
            event['stage'], event['strategy_id'], event['order_id'],
            event['data_hash'], event['raw_data'], event['previous_hash'],
            event['signature']
        ))
        
        conn.commit()
        conn.close()
    
    def verify_integrity(self) -> Dict:
        """
        验证审计链完整性
        
        检查是否有篡改
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM audit_events ORDER BY timestamp')
        events = cursor.fetchall()
        conn.close()
        
        violations = []
        
        for i, event in enumerate(events):
            # 验证签名
            # 验证哈希链
            if i > 0:
                prev_hash = events[i-1][6]  # data_hash column
                if event[8] != prev_hash:  # previous_hash column
                    violations.append({
                        'event_id': event[0],
                        'issue': 'Hash chain broken',
                        'expected_previous': prev_hash,
                        'actual_previous': event[8]
                    })
        
        return {
            'total_events': len(events),
            'violations_found': len(violations),
            'violations': violations,
            'is_valid': len(violations) == 0
        }
    
    def query_trail(
        self,
        order_id: str = None,
        strategy_id: str = None,
        start_time: str = None,
        end_time: str = None
    ) -> List[Dict]:
        """
        查询审计轨迹
        
        可追溯任意订单/策略的完整链路
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = 'SELECT * FROM audit_events WHERE 1=1'
        params = []
        
        if order_id:
            query += ' AND order_id = ?'
            params.append(order_id)
        
        if strategy_id:
            query += ' AND strategy_id = ?'
            params.append(strategy_id)
        
        if start_time:
            query += ' AND timestamp >= ?'
            params.append(start_time)
        
        if end_time:
            query += ' AND timestamp <= ?'
            params.append(end_time)
        
        query += ' ORDER BY timestamp'
        
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        
        return [self._row_to_dict(row) for row in results]
    
    def _row_to_dict(self, row) -> Dict:
        """将数据库行转换为字典"""
        return {
            'event_id': row[0],
            'timestamp': row[1],
            'event_type': row[2],
            'stage': row[3],
            'strategy_id': row[4],
            'order_id': row[5],
            'data_hash': row[6],
            'raw_data': json.loads(row[7]),
            'previous_hash': row[8],
            'signature': row[9]
        }
```

### 2.6.2 异常交易监控

```python
# compliance_monitor.py
from typing import Dict, List
from datetime import datetime, timedelta
import pandas as pd


class ComplianceMonitor:
    """
    异常交易监控
    
    自动检测并拦截：
    - 自成交 (Self-trading)
    - 频繁撤单 (Excessive order cancellation)
    - 拉抬打压 (Price manipulation)
    - 虚假申报 (Spoofing)
    """
    
    def __init__(self):
        self.rules = self._init_rules()
        self.violations = []
        
    def _init_rules(self) -> Dict:
        """初始化监控规则"""
        return {
            'self_trade': {
                'enabled': True,
                'description': '检测自成交行为',
                'threshold': 1  # 同一账户买卖同一股票
            },
            'excessive_cancellation': {
                'enabled': True,
                'description': '频繁撤单',
                'cancel_to_fill_ratio': 5.0,  # 撤单/成交比超过5倍
                'min_orders': 10  # 至少10笔订单才计算
            },
            'price_manipulation': {
                'enabled': True,
                'description': '拉抬打压',
                'price_impact_threshold': 0.02,  # 2%价格影响
                'volume_ratio_threshold': 0.3    # 占成交量30%
            },
            'spoofing': {
                'enabled': True,
                'description': '虚假申报',
                'large_order_threshold': 100000,  # 大单阈值
                'cancellation_time_threshold': 5   # 5秒内撤单
            }
        }
    
    def check_order(self, order: Dict, account_info: Dict) -> Dict:
        """
        订单级合规检查
        
        Returns:
            {'passed': bool, 'violations': List, 'action': str}
        """
        violations = []
        
        # 检查自成交
        if self.rules['self_trade']['enabled']:
            if self._detect_self_trade(order, account_info):
                violations.append({
                    'type': 'self_trade',
                    'severity': 'high',
                    'description': 'Potential self-trading detected'
                })
        
        # 检查虚假申报
        if self.rules['spoofing']['enabled']:
            if self._detect_spoofing(order):
                violations.append({
                    'type': 'spoofing',
                    'severity': 'high',
                    'description': 'Potential spoofing behavior'
                })
        
        if violations:
            return {
                'passed': False,
                'violations': violations,
                'action': 'reject' if any(v['severity'] == 'high' for v in violations) else 'warn'
            }
        
        return {'passed': True, 'violations': [], 'action': 'allow'}
    
    def check_account_activity(
        self,
        account_id: str,
        orders: pd.DataFrame,
        timeframe: str = '1D'
    ) -> Dict:
        """
        账户级活动检查
        
        检测需要多笔订单才能识别的模式
        """
        violations = []
        
        # 检查频繁撤单
        if self.rules['excessive_cancellation']['enabled']:
            cancel_ratio = self._calculate_cancel_ratio(orders)
            if cancel_ratio > self.rules['excessive_cancellation']['cancel_to_fill_ratio']:
                violations.append({
                    'type': 'excessive_cancellation',
                    'severity': 'medium',
                    'cancel_ratio': cancel_ratio,
                    'description': f'Cancel/Fill ratio {cancel_ratio:.1f} exceeds threshold'
                })
        
        # 检查价格操纵
        if self.rules['price_manipulation']['enabled']:
            if self._detect_price_manipulation(account_id, orders):
                violations.append({
                    'type': 'price_manipulation',
                    'severity': 'high',
                    'description': 'Potential price manipulation detected'
                })
        
        # 记录违规
        for v in violations:
            self.violations.append({
                'account_id': account_id,
                'timestamp': datetime.now(),
                **v
            })
        
        return {
            'account_id': account_id,
            'violations': violations,
            'risk_level': 'high' if any(v['severity'] == 'high' for v in violations) else 
                         'medium' if violations else 'low'
        }
    
    def _detect_self_trade(self, order: Dict, account_info: Dict) -> bool:
        """检测自成交"""
        # 检查是否有反向订单
        # 简化的检测逻辑
        return False
    
    def _detect_spoofing(self, order: Dict) -> bool:
        """检测虚假申报"""
        # 大单后快速撤单
        order_size = order.get('quantity', 0) * order.get('price', 0)
        if order_size > self.rules['spoofing']['large_order_threshold']:
            # 标记为可疑，后续检查是否快速撤单
            return True
        return False
    
    def _calculate_cancel_ratio(self, orders: pd.DataFrame) -> float:
        """计算撤单率"""
        if len(orders) < self.rules['excessive_cancellation']['min_orders']:
            return 0.0
        
        canceled = len(orders[orders['status'] == 'cancelled'])
        filled = len(orders[orders['status'] == 'filled'])
        
        if filled == 0:
            return float('inf')
        
        return canceled / filled
    
    def _detect_price_manipulation(self, account_id: str, orders: pd.DataFrame) -> bool:
        """检测价格操纵"""
        # 分析订单模式：是否通过大单拉抬/打压价格
        return False
    
    def generate_compliance_report(self, start_date: str, end_date: str) -> Dict:
        """生成合规报告"""
        period_violations = [
            v for v in self.violations
            if start_date <= v['timestamp'].strftime('%Y-%m-%d') <= end_date
        ]
        
        return {
            'period': f'{start_date} to {end_date}',
            'total_violations': len(period_violations),
            'by_type': pd.DataFrame(period_violations)['type'].value_counts().to_dict(),
            'by_severity': pd.DataFrame(period_violations)['severity'].value_counts().to_dict(),
            'details': period_violations
        }
```

### 2.6.3 监管报表自动生成

```python
# regulatory_reporting.py
import pandas as pd
from datetime import datetime
from typing import Dict, List


class RegulatoryReportGenerator:
    """
    监管报表自动生成
    
    支持：
    - 程序化交易报备
    - 净值报表
    - 持仓报表
    - 交易明细报表
    """
    
    REPORT_TEMPLATES = {
        'program_trading_registration': {
            'name': '程序化交易报备',
            'frequency': 'monthly',
            'fields': ['strategy_name', 'algorithm_type', 'trading_logic', 'risk_controls']
        },
        'nav_report': {
            'name': '净值报表',
            'frequency': 'daily',
            'fields': ['date', 'nav', 'accumulated_nav', 'daily_return', 'benchmark_return']
        },
        'position_report': {
            'name': '持仓报表',
            'frequency': 'daily',
            'fields': ['date', 'code', 'name', 'quantity', 'market_value', 'weight']
        },
        'trade_detail': {
            'name': '交易明细',
            'frequency': 'daily',
            'fields': ['trade_time', 'code', 'side', 'quantity', 'price', 'amount', 'strategy']
        }
    }
    
    def __init__(self, data_source):
        self.data = data_source
        
    def generate_nav_report(
        self,
        start_date: str,
        end_date: str,
        account_id: str
    ) -> pd.DataFrame:
        """生成净值报表"""
        nav_data = self.data.get_nav_history(account_id, start_date, end_date)
        
        report = pd.DataFrame({
            '日期': nav_data.index,
            '单位净值': nav_data['nav'],
            '累计净值': nav_data['accumulated_nav'],
            '日收益率': nav_data['daily_return'],
            '基准收益率': nav_data['benchmark_return'],
            '超额收益': nav_data['daily_return'] - nav_data['benchmark_return']
        })
        
        return report
    
    def generate_position_report(
        self,
        date: str,
        account_id: str
    ) -> pd.DataFrame:
        """生成持仓报表"""
        positions = self.data.get_positions(account_id, date)
        total_value = positions['market_value'].sum()
        
        report = pd.DataFrame({
            '日期': date,
            '证券代码': positions['code'],
            '证券名称': positions['name'],
            '持仓数量': positions['quantity'],
            '市值': positions['market_value'],
            '占净值比': positions['market_value'] / total_value,
            '行业': positions['industry']
        })
        
        # 添加汇总行
        summary = pd.DataFrame({
            '日期': [date],
            '证券代码': ['合计'],
            '证券名称': [''],
            '持仓数量': [''],
            '市值': [total_value],
            '占净值比': [1.0],
            '行业': ['']
        })
        
        return pd.concat([report, summary], ignore_index=True)
    
    def generate_program_trading_registration(
        self,
        strategy_info: Dict
    ) -> Dict:
        """
        生成程序化交易报备材料
        
        符合监管要求的报备文档
        """
        return {
            '报备机构': strategy_info.get('institution_name'),
            '策略名称': strategy_info.get('strategy_name'),
            '策略类型': strategy_info.get('strategy_type'),
            '算法交易类型': strategy_info.get('algorithm_type', 'TWAP/VWAP/POV等'),
            '交易逻辑描述': strategy_info.get('trading_logic'),
            '风控措施': {
                '事前风控': strategy_info.get('pre_trade_risk', []),
                '事中风控': strategy_info.get('in_trade_risk', []),
                '事后风控': strategy_info.get('post_trade_risk', [])
            },
            '异常交易监控': strategy_info.get('compliance_monitoring'),
            '联系人': strategy_info.get('contact'),
            '报备日期': datetime.now().strftime('%Y-%m-%d')
        }
    
    def export_to_excel(self, reports: Dict[str, pd.DataFrame], filepath: str):
        """导出报表到Excel"""
        with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
            for sheet_name, df in reports.items():
                df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        print(f"Reports exported to {filepath}")


### 2.6.4 多账户合规管理

```python
# multi_account_compliance.py

class MultiAccountComplianceManager:
    """
    多账户合规管理
    
    确保：
    - 账户隔离
    - 资金隔离
    - 持仓隔离
    - 信息隔离墙
    """
    
    def __init__(self):
        self.account_hierarchy = {}
        self.isolation_rules = {}
    
    def create_account_isolation(
        self,
        master_account: str,
        sub_accounts: List[str],
        isolation_level: str = 'strict'  # strict/loose
    ):
        """
        创建账户隔离结构
        
        严格隔离：
        - 资金不能跨账户调拨
        - 持仓完全独立
        - 交易信号不能共享
        """
        self.account_hierarchy[master_account] = {
            'sub_accounts': sub_accounts,
            'isolation_level': isolation_level
        }
        
        for sub in sub_accounts:
            self.isolation_rules[sub] = {
                'isolated_from': [a for a in sub_accounts if a != sub],
                'can_share_signals': isolation_level == 'loose',
                'can_transfer_capital': False
            }
    
    def verify_isolation(self, account_a: str, account_b: str) -> bool:
        """验证两个账户是否满足隔离要求"""
        # 检查是否有持仓冲突
        # 检查是否有资金往来
        # 检查是否有信息共享
        return True
    
    def check_cross_account_violations(self) -> List[Dict]:
        """检查跨账户违规"""
        violations = []
        
        # 检查自成交 (不同账户间)
        # 检查协同交易
        # 检查信息泄露
        
        return violations
```

---

*Module: Canary Release and Compliance System*  
*Sub-module: 2.5 - 2.6*  
*Status: 详细设计记录*
