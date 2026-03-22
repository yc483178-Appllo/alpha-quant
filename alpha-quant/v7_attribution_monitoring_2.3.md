# Alpha-Genesis V7.0 - 实盘绩效归因与后验分析

## 2.3 实盘绩效归因与后验分析

### 2.3.1 收益归因模块

**定位**: 回答「钱是怎么赚的、风险来自哪里、策略是否真的有Alpha」

```python
# performance_attribution.py
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass


@dataclass
class AttributionResult:
    """归因结果"""
    total_return: float
    attributed_return: float
    unexplained_return: float
    components: Dict[str, float]


class BrinsonAttribution:
    """
    Brinson归因模型
    
    将超额收益分解为:
    1. 资产配置效应 (Timing)
    2. 个股选择效应 (Selection)
    3. 交互收益 (Interaction)
    
    公式:
    R_portfolio = Σ w_p,i * r_p,i  (组合收益)
    R_benchmark = Σ w_b,i * r_b,i  (基准收益)
    
    超额收益 = R_portfolio - R_benchmark
            = Σ w_p,i * (r_p,i - r_b,i) + Σ (w_p,i - w_b,i) * r_b,i + Σ (w_p,i - w_b,i) * (r_p,i - r_b,i)
            = 选择效应       + 配置效应       + 交互效应
    """
    
    def __init__(self, sectors: List[str] = None):
        self.sectors = sectors or [
            '金融', '科技', '消费', '医药', '周期', 
            '制造', '能源', '公用事业', '房地产'
        ]
    
    def attribute(
        self,
        portfolio_weights: pd.DataFrame,  # [date, sector] 组合行业权重
        portfolio_returns: pd.DataFrame,  # [date, sector] 组合行业收益
        benchmark_weights: pd.DataFrame,  # [date, sector] 基准行业权重
        benchmark_returns: pd.DataFrame   # [date, sector] 基准行业收益
    ) -> AttributionResult:
        """执行Brinson归因"""
        
        # 对齐日期
        dates = portfolio_weights.index.intersection(benchmark_weights.index)
        
        selection_effect = []
        allocation_effect = []
        interaction_effect = []
        
        for date in dates:
            w_p = portfolio_weights.loc[date]
            r_p = portfolio_returns.loc[date]
            w_b = benchmark_weights.loc[date]
            r_b = benchmark_returns.loc[date]
            
            # 选择效应: 行业内选股能力
            selection = (w_p * (r_p - r_b)).sum()
            
            # 配置效应: 行业配置能力
            allocation = ((w_p - w_b) * r_b).sum()
            
            # 交互效应
            interaction = ((w_p - w_b) * (r_p - r_b)).sum()
            
            selection_effect.append(selection)
            allocation_effect.append(allocation)
            interaction_effect.append(interaction)
        
        return AttributionResult(
            total_return=(portfolio_returns * portfolio_weights).sum().sum(),
            attributed_return=sum(selection_effect + allocation_effect + interaction_effect),
            unexplained_return=0,  # Brinson完全归因
            components={
                'selection_effect': sum(selection_effect),
                'allocation_effect': sum(allocation_effect),
                'interaction_effect': sum(interaction_effect),
                'selection_effect_pct': sum(selection_effect) / sum(selection_effect + allocation_effect + interaction_effect),
                'allocation_effect_pct': sum(allocation_effect) / sum(selection_effect + allocation_effect + interaction_effect),
            }
        )


class BarraCNE6Attribution:
    """
    Barra CNE6 风格归因模型
    
    A股本土化版本，包含10个风格因子:
    1. Beta (贝塔)
    2. Momentum (动量)
    3. Size (市值)
    4. EarningsYield (盈利收益)
    5. ResidualVolatility (特质波动)
    6. Growth (成长)
    7. BookToPrice (账面市值比)
    8. Leverage (杠杆)
    9. Liquidity (流动性)
    10. NonLinearSize (非线性市值)
    
    归因分解:
    组合收益 = 风格收益 + 行业收益 + 线性Alpha + 残差
    """
    
    CNE6_FACTORS = [
        'Beta', 'Momentum', 'Size', 'EarningsYield', 'ResidualVolatility',
        'Growth', 'BookToPrice', 'Leverage', 'Liquidity', 'NonLinearSize'
    ]
    
    def __init__(self, factor_data: pd.DataFrame):
        """
        Args:
            factor_data: [date, code, factor_name] 因子暴露数据
        """
        self.factor_data = factor_data
        
    def attribute(
        self,
        portfolio_weights: pd.DataFrame,  # [date, code] 组合权重
        portfolio_returns: pd.Series,     # [date] 组合日收益
        benchmark_weights: pd.DataFrame,  # [date, code] 基准权重
        factor_returns: pd.DataFrame      # [date, factor] 因子收益
    ) -> AttributionResult:
        """执行Barra CNE6归因"""
        
        dates = portfolio_weights.index
        
        style_contrib = {f: 0 for f in self.CNE6_FACTORS}
        industry_contrib = {}
        alpha_contrib = 0
        
        for date in dates:
            # 组合因子暴露
            port_factor_exposure = self._calculate_factor_exposure(
                portfolio_weights.loc[date], date
            )
            
            # 基准因子暴露
            bench_factor_exposure = self._calculate_factor_exposure(
                benchmark_weights.loc[date], date
            )
            
            # 主动暴露
            active_exposure = port_factor_exposure - bench_factor_exposure
            
            # 当日因子收益
            day_factor_return = factor_returns.loc[date]
            
            # 风格贡献
            for factor in self.CNE6_FACTORS:
                if factor in day_factor_return.index:
                    style_contrib[factor] += (
                        active_exposure.get(factor, 0) * day_factor_return[factor]
                    )
            
            # 行业贡献
            industries = self._get_industry_exposure(portfolio_weights.loc[date], date)
            for industry, exposure in industries.items():
                if industry not in industry_contrib:
                    industry_contrib[industry] = 0
                industry_contrib[industry] += exposure * day_factor_return.get('industry_' + industry, 0)
            
            # 线性Alpha (不能被因子解释的收益)
            explained_return = sum(style_contrib.values()) + sum(industry_contrib.values())
            actual_return = portfolio_returns.loc[date]
            alpha_contrib += actual_return - explained_return
        
        return AttributionResult(
            total_return=portfolio_returns.sum(),
            attributed_return=sum(style_contrib.values()) + sum(industry_contrib.values()) + alpha_contrib,
            unexplained_return=0,
            components={
                'style_contribution': style_contrib,
                'industry_contribution': industry_contrib,
                'linear_alpha': alpha_contrib,
                'style_total': sum(style_contrib.values()),
                'industry_total': sum(industry_contrib.values())
            }
        )
    
    def _calculate_factor_exposure(
        self,
        weights: pd.Series,
        date
    ) -> pd.Series:
        """计算组合因子暴露"""
        # 获取当日因子数据
        day_factors = self.factor_data.loc[date]
        
        # 加权平均
        factor_exposure = {}
        for factor in self.CNE6_FACTORS:
            if factor in day_factors.columns:
                factor_exposure[factor] = (weights * day_factors[factor]).sum()
        
        return pd.Series(factor_exposure)
    
    def generate_attribution_report(self, result: AttributionResult) -> str:
        """生成归因报告"""
        report = []
        report.append("=" * 60)
        report.append("Barra CNE6 归因报告")
        report.append("=" * 60)
        
        report.append(f"\n总收益: {result.total_return:.2%}")
        report.append(f"归因收益: {result.attributed_return:.2%}")
        
        report.append("\n【风格归因】")
        style_total = result.components['style_total']
        for factor, value in sorted(
            result.components['style_contribution'].items(),
            key=lambda x: abs(x[1]),
            reverse=True
        ):
            pct = value / style_total * 100 if style_total != 0 else 0
            report.append(f"  {factor:20s}: {value:+.4f} ({pct:5.1f}%)")
        
        report.append("\n【行业归因】")
        for industry, value in sorted(
            result.components['industry_contribution'].items(),
            key=lambda x: abs(x[1]),
            reverse=True
        )[:5]:  # Top 5
            report.append(f"  {industry}: {value:+.4f}")
        
        report.append(f"\n【线性Alpha】: {result.components['linear_alpha']:+.4f}")
        
        return "\n".join(report)


class TransactionCostAttribution:
    """交易成本归因"""
    
    def attribute(
        self,
        trades: pd.DataFrame  # 交易记录
    ) -> Dict:
        """
        分解交易成本:
        - 佣金 (Commission)
        - 印花税 (Stamp Duty)  
        - 过户费 (Transfer Fee)
        - 滑点 (Slippage)
        - 市场冲击 (Market Impact)
        """
        total_cost = trades['total_cost'].sum()
        
        breakdown = {
            'commission': trades['commission'].sum(),
            'stamp_duty': trades['stamp_duty'].sum(),
            'transfer_fee': trades['transfer_fee'].sum(),
            'slippage': trades['slippage_cost'].sum(),
            'market_impact': trades['impact_cost'].sum()
        }
        
        return {
            'total_cost': total_cost,
            'breakdown': breakdown,
            'cost_ratio': total_cost / trades['amount'].sum() if trades['amount'].sum() > 0 else 0,
            'pct_of_pnl': total_cost / abs(trades['pnl'].sum()) if trades['pnl'].sum() != 0 else float('inf')
        }


### 2.3.2 风险归因模块

```python
# risk_attribution.py

class RiskAttributionAnalyzer:
    """风险归因分析器"""
    
    def __init__(self, barra_model: BarraRiskModel = None):
        self.barra_model = barra_model or BarraRiskModel()
    
    def decompose_risk(
        self,
        portfolio_weights: pd.Series,
        factor_exposures: pd.DataFrame,
        factor_covariance: pd.DataFrame,
        specific_risk: pd.Series
    ) -> Dict:
        """
        风险贡献度分解
        
        分解为:
        - 个股风险贡献
        - 行业风险贡献  
        - 风格风险贡献
        """
        total_var = self._calculate_portfolio_variance(
            portfolio_weights, factor_exposures, 
            factor_covariance, specific_risk
        )
        
        # 个股风险贡献
        stock_contrib = {}
        for stock in portfolio_weights.index:
            marginal_contrib = self._calculate_marginal_contribution(
                stock, portfolio_weights, factor_exposures,
                factor_covariance, specific_risk
            )
            stock_contrib[stock] = {
                'weight': portfolio_weights[stock],
                'marginal_risk': marginal_contrib,
                'risk_contrib': portfolio_weights[stock] * marginal_contrib,
                'pct_contrib': portfolio_weights[stock] * marginal_contrib / total_var
            }
        
        # 行业风险贡献
        industry_contrib = self._aggregate_by_industry(
            stock_contrib, portfolio_weights
        )
        
        # 风格风险贡献
        style_contrib = self._calculate_style_contribution(
            portfolio_weights, factor_exposures, factor_covariance
        )
        
        return {
            'total_variance': total_var,
            'total_volatility': np.sqrt(total_var),
            'stock_contribution': stock_contrib,
            'industry_contribution': industry_contrib,
            'style_contribution': style_contrib,
            'diversification_ratio': self._calculate_diversification_ratio(
                portfolio_weights, stock_contrib
            )
        }
    
    def _calculate_marginal_contribution(
        self,
        stock: str,
        weights: pd.Series,
        factor_exposures: pd.DataFrame,
        factor_cov: pd.DataFrame,
        specific_risk: pd.Series
    ) -> float:
        """计算边际风险贡献"""
        # 组合因子暴露
        port_exposure = weights @ factor_exposures
        
        # 边际贡献 = 2 * Cov(r_stock, r_portfolio)
        stock_factor_exposure = factor_exposures.loc[stock]
        
        # 因子部分
        factor_contrib = 2 * (stock_factor_exposure @ factor_cov @ port_exposure)
        
        # 特质风险部分
        specific_contrib = 2 * weights[stock] * (specific_risk.get(stock, 0) ** 2)
        
        return factor_contrib + specific_contrib


class StressTestAnalyzer:
    """压力测试分析器"""
    
    # 内置A股极端行情场景
    SCENARIOS = {
        '2015_stock_crash': {
            'name': '2015年股灾',
            'period': ('2015-06-15', '2015-08-26'),
            'description': '杠杆牛转熊，三轮千股跌停',
            'market_drop': -0.43,
            'max_daily_drop': -0.087,
            'volatility_spike': 3.5
        },
        '2020_covid_crash': {
            'name': '2020年疫情崩盘',
            'period': ('2020-01-20', '2020-03-19'),
            'description': '新冠疫情爆发，全球熔断潮',
            'market_drop': -0.15,
            'recovery_days': 60,
            'vix_spike': 4.0
        },
        '2022_bear_market': {
            'name': '2022年熊市',
            'period': ('2021-12-13', '2022-10-31'),
            'description': '房地产危机+疫情封控+美联储加息',
            'market_drop': -0.28,
            'duration_months': 11,
            'sector_rotation': True
        },
        '2018_trade_war': {
            'name': '2018年贸易战',
            'period': ('2018-01-26', '2018-12-27'),
            'description': '中美贸易摩擦，关税升级',
            'market_drop': -0.30,
            'currency_impact': 0.10
        }
    }
    
    def __init__(self, historical_data: pd.DataFrame):
        self.historical_data = historical_data
        
    def run_builtin_scenarios(
        self,
        strategy,
        scenarios: List[str] = None
    ) -> Dict:
        """
        运行内置压力测试场景
        
        Args:
            scenarios: 场景名称列表，None则运行全部
        """
        if scenarios is None:
            scenarios = list(self.SCENARIOS.keys())
        
        results = {}
        
        for scenario_key in scenarios:
            scenario = self.SCENARIOS[scenario_key]
            print(f"\n运行场景: {scenario['name']}")
            
            # 获取该时期数据
            period_data = self.historical_data[
                (self.historical_data.index >= scenario['period'][0]) &
                (self.historical_data.index <= scenario['period'][1])
            ]
            
            # 回测
            result = strategy.backtest(period_data)
            
            results[scenario_key] = {
                'scenario_name': scenario['name'],
                'strategy_return': result['total_return'],
                'strategy_maxdd': result['max_drawdown'],
                'benchmark_return': scenario['market_drop'],
                'excess_return': result['total_return'] - scenario['market_drop'],
                'survived': result['max_drawdown'] > -0.30,  # 存活标准
                'trades': len(result['trades'])
            }
        
        return results
    
    def generate_stress_report(self, results: Dict) -> str:
        """生成压力测试报告"""
        report = []
        report.append("=" * 70)
        report.append("压力测试报告")
        report.append("=" * 70)
        
        for key, result in results.items():
            report.append(f"\n【{result['scenario_name']}】")
            report.append(f"  策略收益: {result['strategy_return']:+.2%}")
            report.append(f"  策略最大回撤: {result['strategy_maxdd']:+.2%}")
            report.append(f"  基准跌幅: {result['benchmark_return']:+.2%}")
            report.append(f"  超额收益: {result['excess_return']:+.2%}")
            report.append(f"  存活状态: {'✓ 存活' if result['survived'] else '✗ 爆仓'}")
        
        survival_rate = np.mean([r['survived'] for r in results.values()])
        report.append(f"\n总体存活率: {survival_rate:.0%}")
        
        return "\n".join(report)


class CapacityAnalyzer:
    """策略容量分析器"""
    
    def __init__(self, backtester):
        self.backtester = backtester
        
    def analyze_capacity_curve(
        self,
        strategy,
        data: pd.DataFrame,
        capital_range: List[float] = None
    ) -> pd.DataFrame:
        """
        分析不同资金规模下的收益表现
        
        识别策略的容量上限
        """
        if capital_range is None:
            capital_range = [1e6, 5e6, 1e7, 5e7, 1e8, 5e8, 1e9]  # 100万到10亿
        
        results = []
        
        for capital in capital_range:
            print(f"测试资金规模: {capital/1e8:.1f}亿")
            
            # 设置初始资金
            strategy.set_initial_capital(capital)
            
            # 执行回测 (含冲击成本)
            result = self.backtester.run_backtest(
                strategy, data,
                apply_impact=True,
                capital=capital
            )
            
            results.append({
                'capital': capital,
                'capital_cn': f"{capital/1e8:.1f}亿" if capital >= 1e8 else f"{capital/1e6:.0f}万",
                'sharpe': result.sharpe,
                'annual_return': result.annual_return,
                'max_drawdown': result.max_drawdown,
                'impact_cost_ratio': result.avg_impact_cost,
                'avg_daily_turnover': result.avg_daily_turnover
            })
        
        df = pd.DataFrame(results)
        
        # 计算容量拐点
        df['return_decay'] = df['annual_return'].diff() / df['capital'].diff()
        
        return df
    
    def plot_capacity_curve(self, results: pd.DataFrame):
        """绘制容量曲线"""
        import matplotlib.pyplot as plt
        
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 收益衰减
        axes[0, 0].plot(results['capital']/1e8, results['annual_return'], 'o-')
        axes[0, 0].set_xlabel('Capital (100M)')
        axes[0, 0].set_ylabel('Annual Return')
        axes[0, 0].set_title('Return vs Capacity')
        axes[0, 0].grid(True)
        
        # 夏普比率
        axes[0, 1].plot(results['capital']/1e8, results['sharpe'], 's-', color='green')
        axes[0, 1].set_xlabel('Capital (100M)')
        axes[0, 1].set_ylabel('Sharpe Ratio')
        axes[0, 1].set_title('Sharpe vs Capacity')
        axes[0, 1].grid(True)
        
        # 冲击成本
        axes[1, 0].plot(results['capital']/1e8, results['impact_cost_ratio']*100, '^-', color='red')
        axes[1, 0].set_xlabel('Capital (100M)')
        axes[1, 0].set_ylabel('Impact Cost (%)')
        axes[1, 0].set_title('Impact Cost vs Capacity')
        axes[1, 0].grid(True)
        
        # 综合
        ax = axes[1, 1]
        ax2 = ax.twinx()
        ax.plot(results['capital']/1e8, results['annual_return'], 'o-', label='Return')
        ax2.plot(results['capital']/1e8, results['impact_cost_ratio']*100, '^-', color='red', label='Impact')
        ax.set_xlabel('Capital (100M)')
        ax.set_ylabel('Return', color='blue')
        ax2.set_ylabel('Impact Cost %', color='red')
        ax.set_title('Combined Analysis')
        
        plt.tight_layout()
        return fig


### 2.3.3 策略生命周期监控

```python
# strategy_lifecycle_monitor.py

class StrategyLifecycleMonitor:
    """
    策略生命周期监控
    
    实时跟踪策略健康状况，自动触发预警流程
    """
    
    MONITORING_METRICS = {
        'ic_decay': {
            'threshold': 0.5,  # IC衰减50%触发警告
            'window': 20       # 20日滚动
        },
        'win_rate': {
            'threshold': 0.55,  # 胜率低于55%
            'window': 60
        },
        'style_drift': {
            'threshold': 0.3,   # 风格漂移度
            'window': 30
        },
        'turnover_spike': {
            'threshold': 2.0,   # 换手率突增2倍
            'window': 5
        }
    }
    
    def __init__(self, strategy_id: str):
        self.strategy_id = strategy_id
        self.status = 'active'  # active, warning, degraded, offline
        self.metric_history = {}
        
    def update(self, daily_data: Dict):
        """
        每日更新监控指标
        
        Args:
            daily_data: 当日交易数据
        """
        # 计算各指标
        self._update_ic_metric(daily_data)
        self._update_win_rate(daily_data)
        self._update_style_drift(daily_data)
        self._update_turnover(daily_data)
        
        # 检查状态转换
        self._check_status_transition()
        
    def _update_ic_metric(self, data: Dict):
        """更新IC指标"""
        if 'factor_values' in data and 'forward_returns' in data:
            ic = self._calculate_ic(
                data['factor_values'],
                data['forward_returns']
            )
            self._add_metric('ic', ic)
    
    def _update_win_rate(self, data: Dict):
        """更新胜率"""
        if 'trades' in data:
            win_rate = self._calculate_win_rate(data['trades'])
            self._add_metric('win_rate', win_rate)
    
    def _update_style_drift(self, data: Dict):
        """更新风格漂移度"""
        if 'current_exposure' in data and 'baseline_exposure' in data:
            drift = self._calculate_style_drift(
                data['current_exposure'],
                data['baseline_exposure']
            )
            self._add_metric('style_drift', drift)
    
    def _check_status_transition(self):
        """检查是否需要状态转换"""
        # 检查各指标是否超过阈值
        violations = []
        
        for metric, config in self.MONITORING_METRICS.items():
            if metric in self.metric_history:
                recent = self.metric_history[metric][-config['window']:]
                baseline = np.mean(self.metric_history[metric][:config['window']])
                current = np.mean(recent)
                
                if metric == 'ic_decay':
                    if current < baseline * config['threshold']:
                        violations.append(f"{metric}: {current:.3f} vs {baseline:.3f}")
                elif metric == 'win_rate':
                    if current < config['threshold']:
                        violations.append(f"{metric}: {current:.2%}")
                # ... 其他指标检查
        
        # 状态转换逻辑
        if len(violations) >= 3:
            self._transition_to('offline', violations)
        elif len(violations) >= 2:
            self._transition_to('degraded', violations)
        elif len(violations) >= 1:
            self._transition_to('warning', violations)
    
    def _transition_to(self, new_status: str, reasons: List[str]):
        """执行状态转换"""
        old_status = self.status
        self.status = new_status
        
        # 触发相应动作
        if new_status == 'warning':
            self._send_alert('策略健康警告', reasons)
        elif new_status == 'degraded':
            self._send_alert('策略性能衰退', reasons)
            self._trigger_position_reduction(0.5)  # 自动降仓50%
        elif new_status == 'offline':
            self._send_alert('策略下线', reasons)
            self._trigger_position_reduction(0)  # 清仓
            self._disable_strategy()
    
    def _trigger_position_reduction(self, target_pct: float):
        """触发仓位调整"""
        print(f"[ALERT] 策略 {self.strategy_id} 仓位调整至 {target_pct:.0%}")
        # 调用OMS执行减仓


### ★ Claude创新：Autoencoder异常检测器

```python
# autoencoder_anomaly_detector.py
import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import List, Dict
from datetime import datetime


class StrategyBehaviorEncoder(nn.Module):
    """
    策略行为编码器 (Autoencoder)
    
    学习策略的「正常行为模式」，通过重构误差检测异常
    """
    def __init__(
        self,
        input_dim: int = 50,      # 输入特征维度
        latent_dim: int = 16,      # 潜在空间维度
        hidden_dims: List[int] = [128, 64, 32]
    ):
        super().__init__()
        
        # Encoder
        encoder_layers = []
        prev_dim = input_dim
        for h_dim in hidden_dims:
            encoder_layers.extend([
                nn.Linear(prev_dim, h_dim),
                nn.BatchNorm1d(h_dim),
                nn.ReLU(),
                nn.Dropout(0.2)
            ])
            prev_dim = h_dim
        
        encoder_layers.append(nn.Linear(prev_dim, latent_dim))
        self.encoder = nn.Sequential(*encoder_layers)
        
        # Decoder
        decoder_layers = []
        prev_dim = latent_dim
        for h_dim in reversed(hidden_dims):
            decoder_layers.extend([
                nn.Linear(prev_dim, h_dim),
                nn.BatchNorm1d(h_dim),
                nn.ReLU()
            ])
            prev_dim = h_dim
        
        decoder_layers.append(nn.Linear(prev_dim, input_dim))
        self.decoder = nn.Sequential(*decoder_layers)
        
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Returns:
            reconstructed: 重构输入
            latent: 潜在空间表示
        """
        latent = self.encoder(x)
        reconstructed = self.decoder(latent)
        return reconstructed, latent
    
    def reconstruction_error(self, x: torch.Tensor) -> torch.Tensor:
        """计算重构误差"""
        reconstructed, _ = self.forward(x)
        error = F.mse_loss(reconstructed, x, reduction='none').mean(dim=1)
        return error


class StrategyAnomalyDetector:
    """
    策略异常检测器
    
    核心创新: 比IC衰减更早发现策略失效
    
    原理: 策略失效往往不是突然的，而是行为模式逐渐偏离历史。
         自编码器学习正常行为，当重构误差突然飙升时，
         说明当前行为与历史模式差异巨大，预示策略失效
    """
    def __init__(
        self,
        feature_dim: int = 50,
        window_size: int = 20,
        threshold_sigma: float = 3.0  # 3个标准差作为异常阈值
    ):
        self.model = StrategyBehaviorEncoder(input_dim=feature_dim)
        self.window_size = window_size
        self.threshold_sigma = threshold_sigma
        
        self.baseline_error_mean = None
        self.baseline_error_std = None
        self.is_trained = False
        
    def fit(self, historical_behavior: np.ndarray):
        """
        训练异常检测器
        
        Args:
            historical_behavior: [N, feature_dim] 历史行为特征
                特征包括: 持仓分布、交易频率、风格暴露、行业偏好等
        """
        from torch.utils.data import DataLoader, TensorDataset
        
        # 准备数据
        dataset = TensorDataset(
            torch.FloatTensor(historical_behavior)
        )
        loader = DataLoader(dataset, batch_size=32, shuffle=True)
        
        # 训练
        optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-3)
        
        for epoch in range(100):
            total_loss = 0
            for batch in loader:
                x = batch[0]
                
                reconstructed, _ = self.model(x)
                loss = F.mse_loss(reconstructed, x)
                
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
            
            if epoch % 20 == 0:
                print(f"Epoch {epoch}, Loss: {total_loss/len(loader):.4f}")
        
        # 计算基线重构误差分布
        with torch.no_grad():
            errors = self.model.reconstruction_error(
                torch.FloatTensor(historical_behavior)
            ).numpy()
        
        self.baseline_error_mean = np.mean(errors)
        self.baseline_error_std = np.std(errors)
        self.is_trained = True
        
        print(f"基线重构误差: {self.baseline_error_mean:.4f} ± {self.baseline_error_std:.4f}")
    
    def detect(self, current_behavior: np.ndarray) -> Dict:
        """
        检测当前行为是否异常
        
        Returns:
            {
                'is_anomaly': 是否异常,
                'reconstruction_error': 重构误差,
                'z_score': 标准差偏离,
                'severity': 严重程度,
                'confidence': 置信度
            }
        """
        if not self.is_trained:
            raise ValueError("Detector not trained. Call fit() first.")
        
        with torch.no_grad():
            error = self.model.reconstruction_error(
                torch.FloatTensor(current_behavior)
            ).item()
        
        # 计算偏离度
        z_score = (error - self.baseline_error_mean) / self.baseline_error_std
        
        # 判断是否异常
        is_anomaly = z_score > self.threshold_sigma
        
        # 严重程度分级
        if z_score > 5:
            severity = 'critical'
        elif z_score > 3:
            severity = 'high'
        elif z_score > 2:
            severity = 'medium'
        else:
            severity = 'normal'
        
        # 置信度 (基于重构误差的持续性)
        confidence = min(z_score / self.threshold_sigma, 1.0)
        
        return {
            'is_anomaly': is_anomaly,
            'reconstruction_error': error,
            'z_score': z_score,
            'severity': severity,
            'confidence': confidence,
            'threshold': self.baseline_error_mean + self.threshold_sigma * self.baseline_error_std
        }
    
    def explain_anomaly(self, current_behavior: np.ndarray) -> Dict:
        """
        解释异常原因
        
        通过比较重构前后的差异，识别哪些特征导致异常
        """
        with torch.no_grad():
            reconstructed, _ = self.model(
                torch.FloatTensor(current_behavior)
            )
        
        # 计算每个特征的重构误差
        feature_errors = np.abs(current_behavior - reconstructed.numpy())[0]
        
        # 排序找出最异常的特征
        top_anomalous = np.argsort(feature_errors)[-5:][::-1]
        
        feature_names = [
            '持仓集中度', '换手率', '动量暴露', '价值暴露',
            '行业偏离', '规模暴露', '波动暴露', '交易频率',
            '持仓周期', '日内交易比', '盈亏比', '胜率',
            '最大回撤速度', 'beta偏离', '风格稳定性'
            # ... 更多特征
        ]
        
        explanation = {
            'top_anomalous_features': [
                {
                    'feature': feature_names[i] if i < len(feature_names) else f'feature_{i}',
                    'error': float(feature_errors[i]),
                    'current_value': float(current_behavior[0, i]),
                    'expected_value': float(reconstructed[0, i])
                }
                for i in top_anomalous
            ],
            'behavior_change_summary': self._summarize_behavior_change(
                current_behavior[0], reconstructed[0].numpy()
            )
        }
        
        return explanation
    
    def _summarize_behavior_change(
        self,
        current: np.ndarray,
        expected: np.ndarray
    ) -> str:
        """生成行为变化摘要"""
        diff = current - expected
        
        summaries = []
        
        if abs(diff[1]) > 0.5:  # 换手率变化
            direction = "增加" if diff[1] > 0 else "减少"
            summaries.append(f"换手率显著{direction}")
        
        if abs(diff[2]) > 0.3:  # 动量暴露变化
            direction = "增加" if diff[2] > 0 else "减少"
            summaries.append(f"动量因子暴露{direction}")
        
        if abs(diff[4]) > 0.3:  # 行业偏离
            summaries.append("行业配置出现显著偏离")
        
        return "; ".join(summaries) if summaries else "行为模式正常"


class EnhancedStrategyMonitor(StrategyLifecycleMonitor):
    """
    增强版策略监控器
    
    集成Autoencoder异常检测，比IC衰减更早发现策略失效
    """
    def __init__(self, strategy_id: str):
        super().__init__(strategy_id)
        self.anomaly_detector = StrategyAnomalyDetector()
        self.behavior_history = []
        
    def initialize_detector(self, historical_data: List[Dict]):
        """初始化异常检测器"""
        # 从历史数据提取行为特征
        behavior_features = [
            self._extract_behavior_features(d) for d in historical_data
        ]
        
        self.anomaly_detector.fit(np.array(behavior_features))
        print(f"[{self.strategy_id}] 异常检测器初始化完成")
    
    def _extract_behavior_features(self, daily_data: Dict) -> np.ndarray:
        """
        提取策略行为特征向量
        
        特征维度 (~50维):
        1. 持仓特征 (10维)
        2. 交易特征 (10维)  
        3. 风格暴露 (15维)
        4. 风险指标 (10维)
        5. 收益质量 (5维)
        """
        features = []
        
        # 1. 持仓特征
        positions = daily_data.get('positions', {})
        features.extend([
            len(positions),  # 持仓数量
            max(positions.values()) if positions else 0,  # 最大持仓权重
            np.std(list(positions.values())) if positions else 0,  # 持仓分散度
            # ...
        ])
        
        # 2. 交易特征
        trades = daily_data.get('trades', [])
        features.extend([
            len(trades),  # 交易次数
            sum(t['volume'] for t in trades),  # 总成交量
            # ...
        ])
        
        # 3. 风格暴露
        exposure = daily_data.get('style_exposure', {})
        features.extend([
            exposure.get('momentum', 0),
            exposure.get('value', 0),
            exposure.get('size', 0),
            exposure.get('growth', 0),
            exposure.get('quality', 0),
            # ...
        ])
        
        # 填充到50维
        while len(features) < 50:
            features.append(0.0)
        
        return np.array(features[:50])
    
    def update(self, daily_data: Dict):
        """更新监控 (增强版)"""
        # 原有监控逻辑
        super().update(daily_data)
        
        # 提取行为特征
        behavior = self._extract_behavior_features(daily_data)
        self.behavior_history.append(behavior)
        
        # 异常检测
        if len(self.behavior_history) >= 20:  # 至少20天数据
            current = np.array([behavior])
            detection = self.anomaly_detector.detect(current)
            
            if detection['is_anomaly']:
                explanation = self.anomaly_detector.explain_anomaly(current)
                
                self._handle_anomaly_detection(detection, explanation)
    
    def _handle_anomaly_detection(self, detection: Dict, explanation: Dict):
        """处理异常检测警报"""
        severity = detection['severity']
        
        alert_msg = f"""
【策略行为异常警报】
策略ID: {self.strategy_id}
严重程度: {severity.upper()}
重构误差: {detection['reconstruction_error']:.4f} (基线: {self.anomaly_detector.baseline_error_mean:.4f})
Z-Score: {detection['z_score']:.2f} (阈值: {self.anomaly_detector.threshold_sigma})
置信度: {detection['confidence']:.1%}

主要异常行为:
{chr(10).join('- ' + f['feature'] + f" (误差: {f['error']:.3f})" for f in explanation['top_anomalous_features'][:3])}

行为变化摘要: {explanation['behavior_change_summary']}

建议操作: {self._get_recommendation(severity)}
        """
        
        print(alert_msg)
        
        # 根据严重程度触发不同响应
        if severity == 'critical':
            self._trigger_position_reduction(0)  # 立即清仓
            self._disable_strategy()
        elif severity == 'high':
            self._trigger_position_reduction(0.5)
        elif severity == 'medium':
            self._send_alert('策略行为异常-中风险', alert_msg)
    
    def _get_recommendation(self, severity: str) -> str:
        """生成操作建议"""
        recommendations = {
            'critical': '立即清仓，策略已严重偏离正常行为模式，继续运行风险极高',
            'high': '减仓50%，策略行为出现显著异常，建议密切观察',
            'medium': '增加监控频率，策略出现轻微异常，暂不建议调仓',
            'normal': '继续正常运行'
        }
        return recommendations.get(severity, '未知')


# 使用示例
"""
# 1. 初始化监控器
monitor = EnhancedStrategyMonitor(strategy_id='STR-001')

# 2. 用历史数据训练异常检测器
historical_data = load_strategy_history('STR-001', days=252)
monitor.initialize_detector(historical_data)

# 3. 每日监控
for day_data in daily_updates:
    monitor.update(day_data)
    
    # 可能输出:
    # 【策略行为异常警报】
    # 严重程度: HIGH
    # 重构误差: 0.0856 (基线: 0.0234)
    # Z-Score: 4.32 (阈值: 3.0)
    # 
    # 主要异常行为:
    # - 换手率显著增加 (误差: 0.892)
    # - 动量因子暴露减少 (误差: 0.654)
    # - 行业配置出现显著偏离 (误差: 0.543)
    # 
    # 行为变化摘要: 换手率显著增加; 动量因子暴露减少; 行业配置出现显著偏离
    # 
    # 建议操作: 减仓50%，策略行为出现显著异常，建议密切观察
"""
```

---

*Module: Performance Attribution & Lifecycle Monitoring*  
*Sub-module: 2.3.1 - 2.3.3*  
*Status: 详细设计记录*
