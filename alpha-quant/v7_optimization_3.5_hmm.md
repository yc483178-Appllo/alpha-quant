# Alpha-Genesis V7.0 - 3.5 HMM政权检测多特征多尺度升级

## 3.5 HMM政权检测 → 多特征多尺度

### 升级特性概览

| 维度 | V6.1 (旧版) | V7.0 (新版) |
|------|------------|------------|
| **特征** | 仅收益率 | 收益率+波动率+换手率+北向资金+期权波动率+期限利差 |
| **时间尺度** | 日级 | 日/小时/分钟级多尺度 |
| **更新方式** | 离线批处理 | 在线增量滑动窗口 |
| **优化方法** | 均值方差 | 分布鲁棒优化(DRO) |
| **切换策略** | 硬切换 | 置信度阈值+权重平滑 |

---

```python
# hmm_regime_detection_v2.py
import numpy as np
import pandas as pd
from hmmlearn import hmm
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings('ignore')


class MultiFeatureMultiScaleHMM:
    """
    多特征多尺度HMM政权检测器 V7.0
    
    核心升级：
    1. 多特征输入：6维特征向量
    2. 多时间尺度：日/小时/分钟三级检测
    3. 在线增量学习：盘中实时更新
    4. 平滑过渡机制：避免硬切换带来的冲击
    """
    
    REGIME_NAMES = {
        0: 'low_volatility_bull',      # 低波动牛市
        1: 'high_volatility_bull',     # 高波动牛市
        2: 'low_volatility_bear',      # 低波动熊市
        3: 'high_volatility_bear',     # 高波动熊市
        4: 'sideways',                  # 震荡市
        5: 'crisis'                     # 危机模式
    }
    
    # 6维特征定义
    FEATURES = [
        'returns',           # 收益率 (对数收益率)
        'volatility',        # 波动率 (已实现波动率)
        'turnover',          # 换手率
        'northbound_flow',   # 北向资金流向 (标准化)
        'iv_skew',           # 期权隐含波动率偏斜
        'term_spread'        # 期限利差 (10Y-2Y国债)
    ]
    
    def __init__(
        self,
        n_regimes: int = 6,
        time_scales: List[str] = None,
        online_window: int = 60,      # 在线学习窗口
        smoothing_factor: float = 0.3  # 平滑系数
    ):
        self.n_regimes = n_regimes
        self.time_scales = time_scales or ['daily', 'hourly', 'minute']
        self.online_window = online_window
        self.smoothing_factor = smoothing_factor
        
        # 各尺度模型
        self.hmm_models = {}
        self.scalers = {}
        
        for scale in self.time_scales:
            self.hmm_models[scale] = hmm.GaussianHMM(
                n_components=n_regimes,
                covariance_type='full',
                n_iter=100,
                random_state=42
            )
            self.scalers[scale] = StandardScaler()
        
        # 在线学习缓冲区
        self.online_buffer = {scale: [] for scale in self.time_scales}
        
        # 当前政权概率分布 (平滑后)
        self.current_regime_probs = np.ones(n_regimes) / n_regimes
        self.current_regime = 0
        
        # 置信度阈值
        self.confidence_threshold = 0.6
        
        # 状态转移平滑
        self.transition_weights = np.eye(n_regimes) * 0.7 + np.ones((n_regimes, n_regimes)) * 0.05
        
    def fit(self, historical_data: Dict[str, pd.DataFrame]):
        """
        初始训练
        
        Args:
            historical_data: {'daily': df, 'hourly': df, 'minute': df}
        """
        for scale in self.time_scales:
            if scale not in historical_data:
                continue
                
            df = historical_data[scale]
            
            # 提取特征
            features = self._extract_features(df)
            
            # 标准化
            features_scaled = self.scalers[scale].fit_transform(features)
            
            # 训练HMM
            print(f"[HMM] Training {scale} model with {len(features)} samples...")
            self.hmm_models[scale].fit(features_scaled)
            
            print(f"[HMM] {scale} model converged: {self.hmm_models[scale].monitor_.converged}")
    
    def _extract_features(self, df: pd.DataFrame) -> np.ndarray:
        """
        提取6维特征向量
        
        Features:
        1. returns: 对数收益率
        2. volatility: 已实现波动率 (日内高频数据计算)
        3. turnover: 换手率
        4. northbound_flow: 北向资金流向
        5. iv_skew: 期权隐含波动率偏斜 (IV 25 Delta Put - 25 Delta Call)
        6. term_spread: 期限利差
        """
        features = np.zeros((len(df), len(self.FEATURES)))
        
        # 1. 收益率
        if 'close' in df.columns:
            features[:, 0] = np.log(df['close'] / df['close'].shift(1)).fillna(0).values
        
        # 2. 已实现波动率 (假设有高频数据)
        if 'high' in df.columns and 'low' in df.columns:
            # Parkinson波动率估计
            features[:, 1] = np.sqrt(
                (np.log(df['high'] / df['low']) ** 2 / (4 * np.log(2))).fillna(0).values
            )
        
        # 3. 换手率
        if 'turnover' in df.columns:
            features[:, 2] = df['turnover'].fillna(0).values
        elif 'volume' in df.columns and 'float_shares' in df.columns:
            features[:, 2] = (df['volume'] / df['float_shares']).fillna(0).values
        
        # 4. 北向资金流向
        if 'northbound_flow' in df.columns:
            features[:, 3] = df['northbound_flow'].fillna(0).values
        
        # 5. 期权隐含波动率偏斜
        if 'iv_skew' in df.columns:
            features[:, 4] = df['iv_skew'].fillna(0).values
        
        # 6. 期限利差
        if 'term_spread' in df.columns:
            features[:, 5] = df['term_spread'].fillna(0).values
        
        return features
    
    def predict_online(
        self,
        new_data: Dict[str, pd.DataFrame],
        update_model: bool = True
    ) -> Dict:
        """
        在线预测 (盘中实时)
        
        Args:
            new_data: 最新数据
            update_model: 是否增量更新模型
            
        Returns:
            {
                'regime': 当前政权,
                'regime_name': 政权名称,
                'confidence': 置信度,
                'probabilities': 各政权概率,
                'is_transition': 是否处于切换期,
                'scale_predictions': 各尺度预测结果
            }
        """
        scale_predictions = {}
        
        # 各尺度独立预测
        for scale in self.time_scales:
            if scale not in new_data or new_data[scale].empty:
                continue
            
            df = new_data[scale]
            features = self._extract_features(df)
            
            # 标准化
            features_scaled = self.scalers[scale].transform(features)
            
            # 预测政权概率
            log_probs = self.hmm_models[scale].score_samples(features_scaled)
            probs = np.exp(log_probs - log_probs.max())  # 数值稳定性
            probs = probs / probs.sum()
            
            # 最近一个时间点的政权
            hidden_states = self.hmm_models[scale].predict(features_scaled)
            current_state = hidden_states[-1]
            
            scale_predictions[scale] = {
                'state': current_state,
                'state_name': self.REGIME_NAMES.get(current_state, 'unknown'),
                'probabilities': probs,
                'log_likelihood': self.hmm_models[scale].score(features_scaled)
            }
            
            # 更新在线缓冲区
            self.online_buffer[scale].append(features_scaled[-1])
            if len(self.online_buffer[scale]) > self.online_window:
                self.online_buffer[scale].pop(0)
        
        # 多尺度融合
        fused_probs = self._fuse_multi_scale_predictions(scale_predictions)
        
        # 平滑过渡
        smoothed_probs = self._smooth_transition(fused_probs)
        
        # 确定当前政权
        predicted_regime = np.argmax(smoothed_probs)
        confidence = smoothed_probs[predicted_regime]
        
        # 检测是否处于切换期
        is_transition = self._detect_regime_transition(smoothed_probs)
        
        # 更新当前状态
        self.current_regime_probs = smoothed_probs
        if confidence >= self.confidence_threshold:
            self.current_regime = predicted_regime
        
        # 增量更新模型
        if update_model and len(self.online_buffer.get('daily', [])) >= 20:
            self._incremental_update('daily')
        
        return {
            'regime': self.current_regime,
            'regime_name': self.REGIME_NAMES.get(self.current_regime, 'unknown'),
            'confidence': confidence,
            'probabilities': smoothed_probs.tolist(),
            'is_transition': is_transition,
            'scale_predictions': scale_predictions,
            'transition_smoothness': self._calculate_smoothness()
        }
    
    def _fuse_multi_scale_predictions(
        self,
        scale_predictions: Dict
    ) -> np.ndarray:
        """
        融合多尺度预测结果
        
        策略：
        - 日级：权重0.5 (长期趋势)
        - 小时级：权重0.3 (中期趋势)
        - 分钟级：权重0.2 (短期噪音)
        """
        weights = {'daily': 0.5, 'hourly': 0.3, 'minute': 0.2}
        
        fused = np.zeros(self.n_regimes)
        total_weight = 0
        
        for scale, pred in scale_predictions.items():
            if scale in weights:
                # 取最近一个时间点的概率分布
                probs = pred['probabilities']
                # 如果是序列，取最后一个
                if len(probs.shape) > 1:
                    probs = probs[-1]
                fused += probs * weights[scale]
                total_weight += weights[scale]
        
        if total_weight > 0:
            fused /= total_weight
        
        return fused
    
    def _smooth_transition(
        self,
        new_probs: np.ndarray
    ) -> np.ndarray:
        """
        政权切换平滑
        
        使用指数平滑避免硬切换
        """
        smoothed = (
            self.smoothing_factor * new_probs +
            (1 - self.smoothing_factor) * self.current_regime_probs
        )
        
        return smoothed / smoothed.sum()  # 归一化
    
    def _detect_regime_transition(
        self,
        probs: np.ndarray
    ) -> bool:
        """
        检测是否处于政权切换期
        
        条件：
        1. 最高概率低于阈值
        2. 次高概率与最高概率接近
        """
        sorted_probs = np.sort(probs)[::-1]
        
        # 最高概率低于阈值
        if sorted_probs[0] < self.confidence_threshold:
            return True
        
        # 前两名概率接近 (差距小于15%)
        if sorted_probs[0] - sorted_probs[1] < 0.15:
            return True
        
        return False
    
    def _calculate_smoothness(self) -> float:
        """计算切换平滑度"""
        # 计算概率分布的熵
        entropy = -np.sum(
            self.current_regime_probs * np.log(self.current_regime_probs + 1e-10)
        )
        max_entropy = np.log(self.n_regimes)
        
        # 归一化到0-1，1表示完全确定，0表示完全模糊
        return 1 - (entropy / max_entropy)
    
    def _incremental_update(self, scale: str):
        """
        在线增量更新HMM模型
        
        使用滑动窗口数据微调模型参数
        """
        buffer = np.array(self.online_buffer[scale])
        
        if len(buffer) < 20:
            return
        
        # 增量EM算法 (简化版)
        # 实际应用中可以使用hmmlearn的partial fit或自定义实现
        
        # 这里使用简单的参数微调
        # 更新均值向量的滑动平均
        new_means = buffer.mean(axis=0)
        
        # 混合新旧参数 (指数衰减)
        alpha = 0.95  # 历史权重
        self.hmm_models[scale].means_ = (
            alpha * self.hmm_models[scale].means_ +
            (1 - alpha) * np.tile(new_means, (self.n_regimes, 1))
        )
    
    def get_regime_characteristics(self, regime_id: int) -> Dict:
        """
        获取政权特征描述
        
        用于解释当前市场状态
        """
        characteristics = {
            0: {
                'name': '低波动牛市',
                'description': '趋势向上，波动率低，适合趋势跟随策略',
                'recommended_strategies': ['momentum', 'trend_following'],
                'risk_level': 'low',
                'position_sizing': 'aggressive'
            },
            1: {
                'name': '高波动牛市',
                'description': '趋势向上但波动大，适合波动率套利',
                'recommended_strategies': ['volatility_arbitrage', 'momentum'],
                'risk_level': 'medium',
                'position_sizing': 'moderate'
            },
            2: {
                'name': '低波动熊市',
                'description': '阴跌行情，适合防守型策略',
                'recommended_strategies': ['defensive', 'market_neutral'],
                'risk_level': 'medium',
                'position_sizing': 'conservative'
            },
            3: {
                'name': '高波动熊市',
                'description': '恐慌性下跌，适合空头或观望',
                'recommended_strategies': ['short', 'cash'],
                'risk_level': 'high',
                'position_sizing': 'minimal'
            },
            4: {
                'name': '震荡市',
                'description': '无明显趋势，适合均值回归策略',
                'recommended_strategies': ['mean_reversion', 'range_trading'],
                'risk_level': 'medium',
                'position_sizing': 'moderate'
            },
            5: {
                'name': '危机模式',
                'description': '极端行情，流动性枯竭，建议空仓或对冲',
                'recommended_strategies': ['hedge', 'cash'],
                'risk_level': 'extreme',
                'position_sizing': 'minimal'
            }
        }
        
        return characteristics.get(regime_id, {})


class DistributionallyRobustOptimizer:
    """
    分布鲁棒优化 (DRO)
    
    替代传统的均值方差优化
    考虑模型不确定性，构建更鲁棒的投资组合
    """
    
    def __init__(
        self,
        ambiguity_radius: float = 0.1,  # 模糊集半径
        confidence_level: float = 0.95
    ):
        self.radius = ambiguity_radius
        self.confidence = confidence_level
    
    def optimize(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        regime_probs: np.ndarray
    ) -> np.ndarray:
        """
        DRO优化
        
        目标：在最坏分布情况下最大化收益
        
        简化的DRO实现 (基于均值-方差+不确定性调整)
        """
        n_assets = len(expected_returns)
        
        # 调整预期收益 (考虑不确定性)
        adjusted_returns = expected_returns - self.radius * np.diag(cov_matrix) ** 0.5
        
        # 调整协方差 (放大不确定性)
        adjusted_cov = cov_matrix * (1 + self.radius)
        
        # 均值-方差优化 (简化版)
        try:
            inv_cov = np.linalg.inv(adjusted_cov)
            
            # 最大夏普比率权重
            weights = inv_cov @ adjusted_returns
            weights = weights / np.sum(weights)  # 归一化
            
            # 限制空头 (A股限制)
            weights = np.maximum(weights, 0)
            weights = weights / np.sum(weights)
            
            return weights
            
        except np.linalg.LinAlgError:
            # 协方差矩阵奇异，使用等权
            return np.ones(n_assets) / n_assets
    
    def worst_case_analysis(
        self,
        weights: np.ndarray,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray
    ) -> Dict:
        """
        最坏情况分析
        
        分析在当前权重下，最坏情况下的组合表现
        """
        # 最坏情况收益
        worst_return = weights @ (expected_returns - self.radius * np.diag(cov_matrix) ** 0.5)
        
        # 最坏情况波动
        worst_vol = np.sqrt(weights @ (cov_matrix * (1 + self.radius)) @ weights)
        
        return {
            'worst_case_return': worst_return,
            'worst_case_volatility': worst_vol,
            'worst_case_sharpe': worst_return / worst_vol if worst_vol > 0 else 0,
            'ambiguity_radius': self.radius
        }


class RegimeAdaptivePortfolio:
    """
    政权自适应投资组合
    
    根据HMM政权检测结果动态调整组合
    """
    
    def __init__(
        self,
        hmm_detector: MultiFeatureMultiScaleHMM,
        dro_optimizer: DistributionallyRobustOptimizer
    ):
        self.hmm = hmm_detector
        self.dro = dro_optimizer
        
        # 政权-策略映射
        self.regime_strategy_map = {
            0: {'strategy': 'momentum', 'leverage': 1.2},      # 低波牛市加杠杆
            1: {'strategy': 'momentum', 'leverage': 1.0},      # 高波牛市标准
            2: {'strategy': 'defensive', 'leverage': 0.5},     # 低波熊市降仓
            3: {'strategy': 'short', 'leverage': 0.3},         # 高波熊市空头
            4: {'strategy': 'mean_reversion', 'leverage': 0.8}, # 震荡市
            5: {'strategy': 'cash', 'leverage': 0.0}           # 危机模式空仓
        }
        
        # 当前组合
        self.current_weights = None
        self.target_weights = None
        
        # 平滑过渡参数
        self.transition_speed = 0.1  # 每日调整10%
    
    def update(
        self,
        market_data: Dict[str, pd.DataFrame],
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray
    ) -> Dict:
        """
        更新投资组合
        
        Returns:
            {
                'current_regime': 当前政权,
                'target_weights': 目标权重,
                'actual_weights': 实际权重 (考虑平滑过渡),
                'rebalance_needed': 是否需要调仓,
                'transition_phase': 是否处于过渡期
            }
        """
        # 1. 检测当前政权
        regime_info = self.hmm.predict_online(market_data)
        regime_id = regime_info['regime']
        
        # 2. 获取政权对应的策略配置
        strategy_config = self.regime_strategy_map.get(regime_id, {'strategy': 'neutral', 'leverage': 1.0})
        
        # 3. DRO优化目标权重
        target = self.dro.optimize(
            expected_returns * strategy_config['leverage'],
            cov_matrix,
            regime_info['probabilities']
        )
        
        self.target_weights = target
        
        # 4. 平滑过渡
        if self.current_weights is None:
            self.current_weights = target
        else:
            # 渐进式调整
            self.current_weights = (
                (1 - self.transition_speed) * self.current_weights +
                self.transition_speed * target
            )
        
        # 5. 判断是否处于过渡期
        weight_diff = np.abs(self.current_weights - target).sum()
        is_transition = weight_diff > 0.1  # 差异超过10%认为是过渡期
        
        return {
            'current_regime': regime_id,
            'regime_name': regime_info['regime_name'],
            'regime_confidence': regime_info['confidence'],
            'target_weights': target.tolist(),
            'actual_weights': self.current_weights.tolist(),
            'rebalance_needed': weight_diff > 0.05,
            'transition_phase': is_transition,
            'strategy': strategy_config['strategy'],
            'leverage': strategy_config['leverage']
        }


# 使用示例
"""
# 1. 初始化HMM检测器
hmm = MultiFeatureMultiScaleHMM(
    n_regimes=6,
    time_scales=['daily', 'hourly', 'minute'],
    smoothing_factor=0.3
)

# 2. 历史数据训练
historical_data = {
    'daily': load_daily_data('2018-01-01', '2024-12-31'),
    'hourly': load_hourly_data('2020-01-01', '2024-12-31'),
    'minute': load_minute_data('2023-01-01', '2024-12-31')
}
hmm.fit(historical_data)

# 3. 初始化DRO优化器
dro = DistributionallyRobustOptimizer(ambiguity_radius=0.1)

# 4. 创建自适应组合
portfolio = RegimeAdaptivePortfolio(hmm, dro)

# 5. 每日更新 (盘中可多次调用)
market_data = {
    'daily': get_latest_daily(),
    'hourly': get_latest_hourly(),
    'minute': get_latest_minute()
}

result = portfolio.update(
    market_data,
    expected_returns=model.predict(),
    cov_matrix=calculate_covariance()
)

print(f"当前政权: {result['regime_name']} (置信度: {result['regime_confidence']:.2%})")
print(f"采用策略: {result['strategy']} (杠杆: {result['leverage']})")
print(f"目标权重: {result['target_weights']}")
print(f"实际权重: {result['actual_weights']}")
print(f"过渡期: {result['transition_phase']}")
"""

---

*Module: HMM Regime Detection V2 - Multi-Feature Multi-Scale*  
*Chapter: 3.5*  
*Status: 详细设计记录*
