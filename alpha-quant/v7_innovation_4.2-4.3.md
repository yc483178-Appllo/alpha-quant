# Alpha-Genesis V7.0 - 第四章：Claude创新增强（续）

## 4.2 Diffusion Model情景生成器

### 创新背景

**传统回测的局限：**
- 只能测试历史上发生过的场景
- 对「历史上未出现的极端组合」无能为力
- 压力测试场景单一，缺乏多样性

**Diffusion Model解决方案：**
- 学习市场数据的内在分布
- 生成逼真的、但历史上未出现过的情景
- 组合多个极端因素，测试策略鲁棒性

```python
# diffusion_scenario_generator.py
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta


class FinancialTimeSeriesDiffusion(nn.Module):
    """
    金融时间序列Diffusion模型
    
    基于DDPM (Denoising Diffusion Probabilistic Models)
    生成逼真的市场情景
    """
    
    def __init__(
        self,
        seq_len: int = 252,           # 生成序列长度 (1年交易日)
        n_features: int = 5,           # 特征维度 (OHLCV)
        d_model: int = 256,
        n_layers: int = 6,
        n_heads: int = 8,
        timesteps: int = 1000,
        beta_schedule: str = 'cosine'
    ):
        super().__init__()
        self.seq_len = seq_len
        self.n_features = n_features
        self.timesteps = timesteps
        
        # 时间步嵌入
        self.time_embed = nn.Sequential(
            nn.Linear(1, d_model),
            nn.SiLU(),
            nn.Linear(d_model, d_model)
        )
        
        # 条件嵌入 (用于控制生成风格)
        self.condition_embed = nn.Sequential(
            nn.Linear(10, d_model),  # 条件向量维度
            nn.SiLU(),
            nn.Linear(d_model, d_model)
        )
        
        # 输入投影
        self.input_proj = nn.Linear(n_features, d_model)
        
        # Transformer编码器 (U-Net结构)
        self.encoder_layers = nn.ModuleList([
            TransformerBlock(d_model, n_heads)
            for _ in range(n_layers // 2)
        ])
        
        self.bottleneck = TransformerBlock(d_model, n_heads)
        
        self.decoder_layers = nn.ModuleList([
            TransformerBlock(d_model, n_heads)
            for _ in range(n_layers // 2)
        ])
        
        # 输出投影
        self.output_proj = nn.Linear(d_model, n_features)
        
        # 初始化噪声调度
        self._init_noise_schedule(beta_schedule)
        
    def _init_noise_schedule(self, schedule: str):
        """初始化噪声调度"""
        if schedule == 'linear':
            self.betas = torch.linspace(1e-4, 0.02, self.timesteps)
        elif schedule == 'cosine':
            s = 0.008
            steps = self.timesteps + 1
            x = torch.linspace(0, self.timesteps, steps)
            alphas_cumprod = torch.cos(((x / self.timesteps) + s) / (1 + s) * torch.pi * 0.5) ** 2
            alphas_cumprod = alphas_cumprod / alphas_cumprod[0]
            self.betas = 1 - (alphas_cumprod[1:] / alphas_cumprod[:-1])
            self.betas = torch.clip(self.betas, 0.0001, 0.9999)
        
        self.alphas = 1.0 - self.betas
        self.alphas_cumprod = torch.cumprod(self.alphas, dim=0)
        self.sqrt_alphas_cumprod = torch.sqrt(self.alphas_cumprod)
        self.sqrt_one_minus_alphas_cumprod = torch.sqrt(1.0 - self.alphas_cumprod)
        
    def forward(self, x: torch.Tensor, t: torch.Tensor, cond: torch.Tensor) -> torch.Tensor:
        """
        去噪网络前向传播
        
        Args:
            x: [B, seq_len, n_features] 带噪输入
            t: [B] 时间步
            cond: [B, 10] 条件向量
        """
        B = x.size(0)
        
        # 时间嵌入
        t_embed = self.time_embed(t.unsqueeze(-1).float() / self.timesteps)
        
        # 条件嵌入
        c_embed = self.condition_embed(cond)
        
        # 输入投影
        h = self.input_proj(x)
        
        # 添加时间和条件信息
        h = h + t_embed.unsqueeze(1) + c_embed.unsqueeze(1)
        
        # 编码器
        skips = []
        for layer in self.encoder_layers:
            h = layer(h)
            skips.append(h)
        
        # Bottleneck
        h = self.bottleneck(h)
        
        # 解码器 (带跳跃连接)
        for layer in self.decoder_layers:
            h = h + skips.pop()
            h = layer(h)
        
        # 输出
        return self.output_proj(h)
    
    def q_sample(self, x_0: torch.Tensor, t: torch.Tensor, noise: torch.Tensor = None):
        """前向扩散：添加噪声"""
        if noise is None:
            noise = torch.randn_like(x_0)
        
        sqrt_alpha = self.sqrt_alphas_cumprod[t].view(-1, 1, 1)
        sqrt_one_minus_alpha = self.sqrt_one_minus_alphas_cumprod[t].view(-1, 1, 1)
        
        return sqrt_alpha * x_0 + sqrt_one_minus_alpha * noise
    
    def p_sample(self, x_t: torch.Tensor, t: int, cond: torch.Tensor) -> torch.Tensor:
        """反向去噪：单步"""
        t_tensor = torch.full((x_t.size(0),), t, device=x_t.device)
        
        # 预测噪声
        predicted_noise = self.forward(x_t, t_tensor, cond)
        
        # 计算x_{t-1}
        alpha = self.alphas[t]
        alpha_cumprod = self.alphas_cumprod[t]
        beta = self.betas[t]
        
        # 均值
        mean = (x_t - beta / torch.sqrt(1 - alpha_cumprod) * predicted_noise) / torch.sqrt(alpha)
        
        # 方差
        if t > 0:
            variance = beta
            noise = torch.randn_like(x_t)
            return mean + torch.sqrt(variance) * noise
        else:
            return mean
    
    @torch.no_grad()
    def generate(self, batch_size: int, condition: torch.Tensor) -> torch.Tensor:
        """
        生成市场情景
        
        Args:
            condition: [B, 10] 条件向量，控制生成风格
            
        Returns:
            [B, seq_len, n_features] 生成的价格序列
        """
        # 从纯噪声开始
        x = torch.randn(batch_size, self.seq_len, self.n_features)
        
        # 逐步去噪
        for t in reversed(range(self.timesteps)):
            x = self.p_sample(x, t, condition)
        
        return x


class ExtremeScenarioGenerator:
    """
    极端情景生成器
    
    生成历史上未出现过的极端市场组合
    """
    
    def __init__(self, diffusion_model: FinancialTimeSeriesDiffusion):
        self.model = diffusion_model
        
        # 历史情景模板
        self.scenario_templates = {
            'financial_crisis_2008': {
                'volatility': 0.05,
                'max_drawdown': -0.50,
                'trend': -0.30,
                'duration': 200
            },
            'covid_crash_2020': {
                'volatility': 0.06,
                'max_drawdown': -0.35,
                'trend': -0.15,
                'recovery_speed': 'v_shape',
                'duration': 60
            },
            'trade_war_2018': {
                'volatility': 0.03,
                'max_drawdown': -0.30,
                'trend': -0.20,
                'sector_rotation': True,
                'duration': 150
            },
            'property_crisis': {
                'volatility': 0.04,
                'max_drawdown': -0.30,
                'trend': -0.25,
                'credit_tightening': True,
                'duration': 300
            }
        }
    
    def generate_composite_scenario(
        self,
        components: List[str],
        intensities: Dict[str, float],
        n_samples: int = 100
    ) -> List[pd.DataFrame]:
        """
        ★ 核心创新：组合多个历史上未同时出现的极端因素
        
        例如：
        - "中美脱钩" + "房地产危机" (历史上未同时出现)
        - "疫情崩盘" + "金融危机" (复合危机)
        
        Args:
            components: 情景组件列表，如 ['trade_war', 'property_crisis']
            intensities: 各组件强度，如 {'trade_war': 0.9, 'property_crisis': 1.0}
            n_samples: 生成样本数
            
        Returns:
            生成的价格序列列表
        """
        # 构建条件向量
        condition = self._build_condition_vector(components, intensities)
        
        # 批量生成
        samples = self.model.generate(n_samples, condition)
        
        # 后处理：应用情景特征变换
        results = []
        for i in range(n_samples):
            df = self._post_process(samples[i], components, intensities)
            results.append(df)
        
        return results
    
    def _build_condition_vector(
        self,
        components: List[str],
        intensities: Dict[str, float]
    ) -> torch.Tensor:
        """构建条件向量"""
        # 10维条件向量
        cond = torch.zeros(10)
        
        # 前4维：情景类型one-hot
        scenario_types = ['crisis', 'bear', 'bull', 'sideways']
        for i, comp in enumerate(components):
            if i < 4:
                template = self.scenario_templates.get(comp, {})
                if template.get('max_drawdown', 0) < -0.3:
                    cond[0] = 1  # crisis
                elif template.get('max_drawdown', 0) < -0.1:
                    cond[1] = 1  # bear
                elif template.get('trend', 0) > 0.2:
                    cond[2] = 1  # bull
                else:
                    cond[3] = 1  # sideways
        
        # 第5-6维：波动率范围
        avg_vol = np.mean([
            self.scenario_templates.get(c, {}).get('volatility', 0.02)
            for c in components
        ])
        cond[4] = avg_vol
        cond[5] = avg_vol * 2
        
        # 第7-8维：回撤范围
        avg_dd = np.mean([
            self.scenario_templates.get(c, {}).get('max_drawdown', -0.1)
            for c in components
        ])
        cond[6] = abs(avg_dd)
        cond[7] = abs(avg_dd) * 0.5
        
        # 第9维：整体强度
        cond[8] = np.mean(list(intensities.values()))
        
        # 第10维：复杂度 (组件数量)
        cond[9] = len(components) / 4.0
        
        return cond.unsqueeze(0)
    
    def _post_process(
        self,
        sample: torch.Tensor,
        components: List[str],
        intensities: Dict[str, float]
    ) -> pd.DataFrame:
        """后处理生成的序列"""
        data = sample.numpy()
        
        # 转换为DataFrame
        df = pd.DataFrame(data, columns=['open', 'high', 'low', 'close', 'volume'])
        
        # 应用情景特定的变换
        for comp in components:
            template = self.scenario_templates.get(comp, {})
            intensity = intensities.get(comp, 0.5)
            
            # 波动率调整
            if 'volatility' in template:
                vol_scale = 1 + (template['volatility'] / 0.02 - 1) * intensity
                df['close'] = df['close'] * vol_scale
            
            # 趋势调整
            if 'trend' in template:
                trend = template['trend'] * intensity
                trend_line = np.linspace(0, trend, len(df))
                df['close'] = df['close'] * (1 + trend_line)
        
        # 生成日期索引
        df['date'] = pd.date_range(start='2025-01-01', periods=len(df), freq='B')
        df.set_index('date', inplace=True)
        
        return df


class StressTestEngineWithDiffusion:
    """
    基于Diffusion的压力测试引擎
    """
    
    def __init__(
        self,
        scenario_generator: ExtremeScenarioGenerator,
        backtest_engine
    ):
        self.generator = scenario_generator
        self.backtest = backtest_engine
        
    def run_comprehensive_stress_test(
        self,
        strategy,
        scenarios: List[Dict],
        n_samples_per_scenario: int = 50
    ) -> Dict:
        """
        综合压力测试
        
        测试历史上未出现过的复合极端情景
        """
        all_results = []
        
        for scenario_config in scenarios:
            print(f"\n测试情景: {scenario_config['name']}")
            
            # 生成样本
            samples = self.generator.generate_composite_scenario(
                components=scenario_config['components'],
                intensities=scenario_config['intensities'],
                n_samples=n_samples_per_scenario
            )
            
            # 在每个样本上回测
            scenario_results = []
            for i, sample_data in enumerate(samples):
                print(f"  样本 {i+1}/{n_samples_per_scenario}...", end='\r')
                
                result = self.backtest.run(
                    strategy, sample_data,
                    apply_impact=True,
                    apply_slippage=True
                )
                
                scenario_results.append({
                    'max_drawdown': result.max_drawdown,
                    'final_return': result.total_return,
                    'sharpe': result.sharpe,
                    'survived': result.max_drawdown > -0.30
                })
            
            # 统计
            survival_rate = np.mean([r['survived'] for r in scenario_results])
            avg_maxdd = np.mean([r['max_drawdown'] for r in scenario_results])
            
            all_results.append({
                'scenario_name': scenario_config['name'],
                'components': scenario_config['components'],
                'survival_rate': survival_rate,
                'avg_max_drawdown': avg_maxdd,
                'worst_case': min([r['max_drawdown'] for r in scenario_results]),
                'sample_results': scenario_results
            })
            
            print(f"  存活率: {survival_rate:.1%}, 平均回撤: {avg_maxdd:.2%}")
        
        return self._generate_report(all_results)
    
    def _generate_report(self, results: List[Dict]) -> Dict:
        """生成压力测试报告"""
        return {
            'summary': {
                'n_scenarios': len(results),
                'avg_survival_rate': np.mean([r['survival_rate'] for r in results]),
                'min_survival_rate': min([r['survival_rate'] for r in results]),
                'critical_scenarios': [
                    r['scenario_name'] for r in results
                    if r['survival_rate'] < 0.5
                ]
            },
            'detailed_results': results,
            'recommendations': self._generate_recommendations(results)
        }
    
    def _generate_recommendations(self, results: List[Dict]) -> List[str]:
        """生成改进建议"""
        recommendations = []
        
        min_survival = min([r['survival_rate'] for r in results])
        
        if min_survival < 0.3:
            recommendations.append(
                "警告: 策略在多个极端情景下存活率低于30%，建议大幅加强风控"
            )
        elif min_survival < 0.6:
            recommendations.append(
                "注意: 策略在部分复合极端情景下表现脆弱，建议优化策略鲁棒性"
            )
        else:
            recommendations.append(
                "良好: 策略在压力测试中表现稳健"
            )
        
        return recommendations


# 使用示例
"""
# 1. 训练Diffusion模型
print("训练Diffusion模型...")
model = FinancialTimeSeriesDiffusion(
    seq_len=252,
    n_features=5,
    d_model=256,
    n_layers=6
)

# 加载历史数据训练
trainer = DiffusionTrainer(model)
trainer.train(historical_data, epochs=100)

# 2. 创建情景生成器
generator = ExtremeScenarioGenerator(model)

# 3. 定义复合极端情景
stress_scenarios = [
    {
        'name': '中美脱钩+房地产危机',
        'components': ['trade_war', 'property_crisis'],
        'intensities': {'trade_war': 0.9, 'property_crisis': 1.0}
    },
    {
        'name': '全球疫情+金融危机',
        'components': ['covid_crash_2020', 'financial_crisis_2008'],
        'intensities': {'covid_crash_2020': 1.0, 'financial_crisis_2008': 0.8}
    },
    {
        'name': '三重重压',
        'components': ['trade_war', 'property_crisis', 'covid_crash_2020'],
        'intensities': {'trade_war': 0.8, 'property_crisis': 0.9, 'covid_crash_2020': 0.7}
    }
]

# 4. 执行压力测试
print("\n执行压力测试...")
engine = StressTestEngineWithDiffusion(generator, backtester)
report = engine.run_comprehensive_stress_test(
    strategy=my_strategy,
    scenarios=stress_scenarios,
    n_samples_per_scenario=50
)

# 5. 查看结果
print("\n" + "="*60)
print("压力测试报告")
print("="*60)
print(f"测试情景数: {report['summary']['n_scenarios']}")
print(f"平均存活率: {report['summary']['avg_survival_rate']:.1%}")
print(f"最低存活率: {report['summary']['min_survival_rate']:.1%}")

if report['summary']['critical_scenarios']:
    print(f"\n危险情景: {', '.join(report['summary']['critical_scenarios'])}")

print("\n建议:")
for rec in report['recommendations']:
    print(f"  - {rec}")
"""

---

## 4.3 因果推断因子挖掘

### 创新背景

**传统因子挖掘的问题：**
- 只关注相关性，忽略因果关系
- 容易产生伪相关因子 (spurious correlation)
- 因子在经济逻辑上可能不成立

**因果推断解决方案：**
- 区分相关性与因果性
- 识别真正的驱动因素
- 提高因子的稳定性和可解释性

```python
# causal_factor_mining.py
import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import dowhy
from dowhy import CausalModel
from causalinference import CausalModel as CIModel
from sklearn.ensemble import RandomForestRegressor
import networkx as nx


class CausalFactorMiner:
    """
    因果推断因子挖掘器
    
    使用DoWhy + CausalNex进行因果分析
    """
    
    def __init__(self):
        self.discovered_factors = []
        self.causal_graph = None
        
    def discover_causal_relationships(
        self,
        data: pd.DataFrame,
        treatment_candidates: List[str],
        outcome: str = 'returns',
        common_causes: List[str] = None
    ) -> List[Dict]:
        """
        发现因果关系的因子
        
        Args:
            data: 包含潜在因子和收益的数据
            treatment_candidates: 候选因子列表
            outcome: 目标变量 (收益率)
            common_causes: 混杂变量
            
        Returns:
            因果效应显著的因子列表
        """
        valid_factors = []
        
        for factor in treatment_candidates:
            print(f"\n分析因子: {factor}")
            
            try:
                # 构建因果模型
                causal_graph = self._build_causal_graph(
                    factor, outcome, common_causes
                )
                
                model = CausalModel(
                    data=data,
                    treatment=factor,
                    outcome=outcome,
                    graph=causal_graph
                )
                
                # 识别因果效应
                identified_estimand = model.identify_effect()
                
                # 估计因果效应
                estimate = model.estimate_effect(
                    identified_estimand,
                    method_name="backdoor.propensity_score_matching"
                )
                
                #  refutation测试
                refutation = model.refute_estimate(
                    identified_estimand,
                    estimate,
                    method_name="placebo_treatment_refuter"
                )
                
                # 判断因果效应是否显著
                if abs(estimate.value) > 0.001 and refutation.p_value > 0.05:
                    valid_factors.append({
                        'factor': factor,
                        'causal_effect': estimate.value,
                        'p_value': refutation.p_value,
                        'confidence': self._calculate_confidence(estimate, refutation),
                        'causal_graph': causal_graph
                    })
                    
                    print(f"  ✓ 因果效应: {estimate.value:.4f}, p-value: {refutation.p_value:.4f}")
                else:
                    print(f"  ✗ 因果效应不显著或无法通过反驳测试")
                    
            except Exception as e:
                print(f"  ✗ 分析失败: {e}")
        
        # 按因果效应排序
        valid_factors.sort(key=lambda x: abs(x['causal_effect']), reverse=True)
        
        return valid_factors
    
    def _build_causal_graph(
        self,
        treatment: str,
        outcome: str,
        common_causes: List[str] = None
    ) -> str:
        """构建因果图 (DOT格式)"""
        if common_causes is None:
            common_causes = ['market_cap', 'industry', 'beta']
        
        edges = []
        
        # 混杂变量到处理变量和结果
        for cause in common_causes:
            edges.append(f"{cause} -> {treatment}")
            edges.append(f"{cause} -> {outcome}")
        
        # 处理变量到结果
        edges.append(f"{treatment} -> {outcome}")
        
        # 构建DOT字符串
        dot_str = "digraph {" + "; ".join(edges) + "}"
        
        return dot_str
    
    def _calculate_confidence(self, estimate, refutation) -> float:
        """计算因果关系的置信度"""
        # 基于效应大小和反驳测试p值
        effect_score = min(abs(estimate.value) / 0.01, 1.0)  # 归一化到0-1
        robustness_score = 1 - refutation.p_value
        
        return (effect_score + robustness_score) / 2
    
    def build_factor_causal_network(
        self,
        data: pd.DataFrame,
        factors: List[str]
    ) -> nx.DiGraph:
        """
        构建因子因果网络
        
        识别因子间的因果关系，而非仅仅是相关性
        """
        from causalnex.structure import DAGRegressor
        from causalnex.structure.pytorch import from_pandas
        
        # 使用NOTEALS学习因果结构
        sm = from_pandas(data[factors], tabu_edges=[], tabu_parent_nodes=[])
        
        # 转换为NetworkX图
        G = nx.DiGraph()
        
        for edge in sm.edges:
            G.add_edge(edge[0], edge[1], weight=sm.get_edge_data(edge[0], edge[1]))
        
        self.causal_graph = G
        
        return G
    
    def identify_confounding_factors(
        self,
        factor_a: str,
        factor_b: str,
        data: pd.DataFrame
    ) -> List[str]:
        """
        识别两个因子之间的混杂因子
        
        找出导致伪相关的共同原因
        """
        if self.causal_graph is None:
            raise ValueError("请先构建因果网络")
        
        # 寻找共同祖先
        ancestors_a = nx.ancestors(self.causal_graph, factor_a)
        ancestors_b = nx.ancestors(self.causal_graph, factor_b)
        
        common_ancestors = ancestors_a.intersection(ancestors_b)
        
        return list(common_ancestors)
    
    def validate_factor_stability(
        self,
        factor: str,
        data: pd.DataFrame,
        n_bootstrap: int = 100
    ) -> Dict:
        """
        验证因子的稳定性 (Bootstrap)
        
        因果因子应该在不同子样本中表现稳定
        """
        effects = []
        
        for i in range(n_bootstrap):
            # Bootstrap采样
            sample = data.sample(frac=0.8, replace=True)
            
            # 计算IC
            ic = sample[factor].corr(sample['returns'], method='spearman')
            effects.append(ic)
        
        return {
            'mean_ic': np.mean(effects),
            'std_ic': np.std(effects),
            'ic_ir': np.mean(effects) / np.std(effects) if np.std(effects) > 0 else 0,
            'stability_score': 1 - np.std(effects) / (abs(np.mean(effects)) + 1e-6)
        }


class CausalFactorValidator:
    """
    因果因子验证器
    
    在生产环境中持续验证因子的因果有效性
    """
    
    def __init__(self, alert_threshold: float = 0.3):
        self.alert_threshold = alert_threshold
        self.factor_history = {}
        
    def validate_online(
        self,
        factor_name: str,
        factor_values: pd.Series,
        returns: pd.Series,
        market_conditions: Dict
    ) -> Dict:
        """
        在线验证因子
        
        检测因子是否失效 (因果效应衰减)
        """
        # 计算当前IC
        current_ic = factor_values.corr(returns, method='spearman')
        
        # 记录历史
        if factor_name not in self.factor_history:
            self.factor_history[factor_name] = []
        
        self.factor_history[factor_name].append({
            'timestamp': pd.Timestamp.now(),
            'ic': current_ic,
            'market_regime': market_conditions.get('regime', 'unknown')
        })
        
        # 计算IC衰减
        if len(self.factor_history[factor_name]) > 20:
            recent_ic = np.mean([h['ic'] for h in self.factor_history[factor_name][-20:]])
            baseline_ic = np.mean([h['ic'] for h in self.factor_history[factor_name][:20]])
            
            decay = (baseline_ic - recent_ic) / (abs(baseline_ic) + 1e-6)
            
            if decay > self.alert_threshold:
                return {
                    'status': 'degraded',
                    'decay': decay,
                    'current_ic': current_ic,
                    'recommendation': 'Consider retiring this factor'
                }
        
        return {
            'status': 'active',
            'current_ic': current_ic
        }


# 使用示例
"""
# 1. 准备数据
data = load_factor_data(start='2018-01-01', end='2024-12-31')

# 候选因子 (包含一些可能是伪相关的)
candidate_factors = [
    'roe_ttm',           # 净资产收益率
    'pe_ratio',          # 市盈率
    'momentum_20d',      # 20日动量
    'turnover_ratio',    # 换手率
    'volume_price_divergence',  # 量价背离
    'retail_sentiment',  # 散户情绪 (可能是伪相关)
    'analyst_coverage',  # 分析师覆盖度
    'earnings_surprise', # 盈利惊喜
    'moon_phase',        # 月相 (明显伪相关)
    'solar_activity'     # 太阳活动 (伪相关)
]

# 2. 挖掘因果因子
miner = CausalFactorMiner()

print("开始因果因子挖掘...")
causal_factors = miner.discover_causal_relationships(
    data=data,
    treatment_candidates=candidate_factors,
    outcome='forward_returns',
    common_causes=['market_cap', 'industry', 'beta', 'volatility']
)

print("\n因果显著的因子:")
for f in causal_factors[:5]:
    print(f"  {f['factor']}: 因果效应={f['causal_effect']:.4f}, 置信度={f['confidence']:.2%}")

# 3. 构建因子因果网络
print("\n构建因子因果网络...")
causal_network = miner.build_factor_causal_network(
    data, [f['factor'] for f in causal_factors]
)

# 识别伪相关
confounders = miner.identify_confounding_factors(
    'volume_price_divergence', 'retail_sentiment', data
)
print(f"\n量价背离与散户情绪的混杂因子: {confounders}")

# 4. 在线验证
validator = CausalFactorValidator()
for date in pd.date_range('2025-01-01', '2025-03-01'):
    day_data = data[data.index == date]
    
    for factor in causal_factors:
        result = validator.validate_online(
            factor['factor'],
            day_data[factor['factor']],
            day_data['forward_returns'],
            {'regime': detect_regime(day_data)}
        )
        
        if result['status'] == 'degraded':
            print(f"[Alert] 因子 {factor['factor']} 失效，IC衰减: {result['decay']:.1%}")
"""

---

*Module: 4.2-4.3 Diffusion Scenario + Causal Factor Mining*  
*Chapter: 4*  
*Status: 详细设计记录*
