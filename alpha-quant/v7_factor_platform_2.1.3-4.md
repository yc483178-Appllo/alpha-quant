# Alpha-Genesis V7.0 - 因子研发平台详细设计

## 2.1 全流程因子研发与管理平台

### 2.1.3 因子回测与绩效分析

**功能定位**: 单因子全生命周期绩效评估

**核心功能模块**:

| 功能 | 描述 | 输出指标 |
|------|------|----------|
| 单因子回测 | 纯多头/多空对冲回测 | 累计收益、最大回撤、夏普比率 |
| 分层测试 | 按因子值分5层/10层 | 分层收益单调性、多空收益 |
| 事件窗口分析 | 财报/政策事件前后因子表现 | 事件超额收益、反应速度 |
| IC分析 | 信息系数时间序列 | IC均值、ICIR、IC胜率 |

**绩效指标体系**:

```python
# factor_performance_metrics.py
class FactorPerformanceAnalyzer:
    """因子绩效分析器"""
    
    def calculate_ic_metrics(self, factor_values, forward_returns):
        """
        IC指标计算
        
        Returns:
            {
                'ic_mean': 平均IC,
                'ic_std': IC标准差,
                'ic_ir': IC信息比率,
                'ic_positive_ratio': IC正胜率,
                'rank_ic_mean': 平均Rank IC,
                'rank_ic_ir': Rank ICIR
            }
        """
        pass
    
    def layer_backtest(self, factor_values, returns, n_layers=5):
        """
        分层回测
        
        按因子值分层，测试每层收益表现
        """
        pass
    
    def event_window_analysis(self, factor_values, events, window=(-5, 20)):
        """
        事件窗口分析
        
        分析事件前后因子表现变化
        """
        pass
    
    def generate_factor_report(self, factor_id, output_path):
        """
        自动生成因子投研报告
        
        包含：
        - 因子定义与逻辑
        - 绩效指标汇总
        - IC/IR时间序列图
        - 分层收益图
        - 行业分布热力图
        - 风险提示
        """
        pass
```

### 2.1.4 因子组合优化

**基础功能**:
- 基于因子相关性矩阵的动态加权
- 考虑因子衰减周期的生命周期管理
- 风险收益比优化

**★ Claude创新：Attention-based因子权重网络**

```python
# attention_factor_weights.py
import torch
import torch.nn as nn
import torch.nn.functional as F


class MarketRegimeEncoder(nn.Module):
    """
    市场政权编码器
    识别当前市场状态：上升市/震荡市/下跌市
    """
    def __init__(self, input_dim=20, hidden_dim=64, n_regimes=3):
        super().__init__()
        self.encoder = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU()
        )
        self.regime_classifier = nn.Linear(hidden_dim // 2, n_regimes)
        
    def forward(self, market_features):
        """
        Args:
            market_features: 市场特征 [volatility, trend, breadth, ...]
        Returns:
            regime_probs: 政权概率分布
            regime_embedding: 政权嵌入向量
        """
        hidden = self.encoder(market_features)
        regime_logits = self.regime_classifier(hidden)
        regime_probs = F.softmax(regime_logits, dim=-1)
        return regime_probs, hidden


class AttentionFactorWeightNetwork(nn.Module):
    """
    Attention-based因子权重网络
    
    核心思想：让因子权重随市场政权动态调整
    - 上升市 → 加大动量因子权重
    - 震荡市 → 加大均值回归因子权重
    - 下跌市 → 加大质量/防御因子权重
    """
    def __init__(
        self,
        n_factors: int = 30,
        factor_categories: List[str] = None,
        d_model: int = 128,
        n_heads: int = 8
    ):
        super().__init__()
        self.n_factors = n_factors
        self.factor_categories = factor_categories or [
            'momentum', 'value', 'quality', 'growth', 'volatility'
        ]
        
        # 因子嵌入
        self.factor_embed = nn.Linear(1, d_model // 2)
        
        # 市场政权编码器
        self.regime_encoder = MarketRegimeEncoder(
            input_dim=20,  # 市场特征维度
            hidden_dim=d_model // 2,
            n_regimes=3
        )
        
        # Cross-Attention: 因子关注市场政权
        self.cross_attention = nn.MultiheadAttention(
            embed_dim=d_model,
            num_heads=n_heads,
            batch_first=True
        )
        
        # 权重生成网络
        self.weight_generator = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(d_model // 2, 1),
            nn.Softmax(dim=1)  # 因子权重归一化
        )
        
        # 政权适配偏置
        self.regime_bias = nn.Parameter(
            torch.randn(len(self.factor_categories), len(self.factor_categories))
        )
        
    def forward(
        self,
        factor_values: torch.Tensor,      # [B, n_factors]
        factor_categories: List[int],      # 每个因子的类别索引
        market_features: torch.Tensor     # [B, 20] 市场特征
    ) -> torch.Tensor:
        """
        Args:
            factor_values: 因子值
            factor_categories: 因子类别索引列表
            market_features: 市场状态特征
            
        Returns:
            weights: [B, n_factors] 动态因子权重
        """
        B = factor_values.size(0)
        
        # 1. 编码市场政权
        regime_probs, regime_embed = self.regime_encoder(market_features)
        # regime_embed: [B, d_model//2]
        
        # 2. 因子嵌入
        factor_embeds = self.factor_embed(factor_values.unsqueeze(-1))
        # factor_embeds: [B, n_factors, d_model//2]
        
        # 3. 结合政权信息
        regime_expanded = regime_embed.unsqueeze(1).expand(-1, self.n_factors, -1)
        # regime_expanded: [B, n_factors, d_model//2]
        
        combined = torch.cat([factor_embeds, regime_expanded], dim=-1)
        # combined: [B, n_factors, d_model]
        
        # 4. Cross-Attention: 因子关注市场政权
        # Query: 因子, Key/Value: 政权
        regime_as_kv = regime_embed.unsqueeze(1)  # [B, 1, d_model//2]
        regime_as_kv = regime_as_kv.expand(-1, self.n_factors, -1)
        regime_as_kv = torch.cat([regime_as_kv, regime_as_kv], dim=-1)  # [B, n_factors, d_model]
        
        attn_out, attn_weights = self.cross_attention(
            query=combined,
            key=regime_as_kv,
            value=regime_as_kv
        )
        # attn_out: [B, n_factors, d_model]
        
        # 5. 生成权重
        raw_weights = self.weight_generator(attn_out).squeeze(-1)
        # raw_weights: [B, n_factors]
        
        # 6. 应用政权适配偏置
        category_bias = torch.zeros(B, self.n_factors)
        for b in range(B):
            # 根据政权概率加权偏置
            dominant_regime = regime_probs[b].argmax().item()
            for i, cat_idx in enumerate(factor_categories):
                category_bias[b, i] = self.regime_bias[dominant_regime, cat_idx]
        
        adjusted_weights = raw_weights * (1 + category_bias)
        weights = F.softmax(adjusted_weights, dim=1)
        
        return weights
    
    def get_regime_factor_preferences(self) -> Dict[str, Dict[str, float]]:
        """
        获取各政权下的因子偏好配置
        
        Returns:
            {
                'bull': {'momentum': 0.4, 'growth': 0.3, ...},
                'range': {'mean_reversion': 0.4, 'value': 0.3, ...},
                'bear': {'quality': 0.4, 'defensive': 0.3, ...}
            }
        """
        preferences = {}
        regime_names = ['bull', 'range', 'bear']
        
        for i, regime in enumerate(regime_names):
            pref = {}
            for j, category in enumerate(self.factor_categories):
                pref[category] = F.softmax(self.regime_bias[i], dim=0)[j].item()
            preferences[regime] = pref
        
        return preferences


class DynamicFactorComposer:
    """
    动态因子组合器
    整合多个因子，根据市场状态动态调整权重
    """
    def __init__(self, weight_network: AttentionFactorWeightNetwork):
        self.weight_network = weight_network
        self.factor_cache = {}
        
    def compose(
        self,
        factor_values: pd.DataFrame,      # [n_stocks, n_factors]
        factor_categories: List[str],
        market_state: pd.Series           # 市场状态指标
    ) -> pd.Series:
        """
        组合因子，生成综合因子值
        
        Returns:
            综合因子值 [n_stocks]
        """
        # 转换为tensor
        factor_tensor = torch.tensor(factor_values.values, dtype=torch.float32)
        market_tensor = torch.tensor(market_state.values, dtype=torch.float32).unsqueeze(0)
        
        # 类别映射
        category_map = {cat: i for i, cat in enumerate(self.weight_network.factor_categories)}
        category_indices = [category_map.get(cat, 0) for cat in factor_categories]
        
        # 获取动态权重
        with torch.no_grad():
            weights = self.weight_network(
                factor_tensor,
                category_indices,
                market_tensor
            )
        
        # 加权组合
        weights_np = weights.numpy()
        composite_factor = (factor_values.values * weights_np).sum(axis=1)
        
        return pd.Series(composite_factor, index=factor_values.index)
```

**训练流程**:

```python
# train_attention_weights.py
def train_attention_factor_network(
    model: AttentionFactorWeightNetwork,
    train_data: FactorDataset,
    epochs: int = 100,
    lr: float = 1e-3
):
    """
    训练Attention因子权重网络
    
    目标：预测最优因子权重，使得组合因子IC最大化
    """
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=10)
    
    for epoch in range(epochs):
        total_loss = 0
        
        for batch in train_data:
            factor_values = batch['factor_values']
            market_features = batch['market_features']
            target_ic = batch['target_ic']  # 目标IC
            
            # 前向传播
            weights = model(factor_values, batch['categories'], market_features)
            
            # 计算组合因子IC
            composite_factor = (factor_values * weights).sum(dim=1)
            predicted_ic = calculate_ic(composite_factor, batch['forward_returns'])
            
            # 损失：负IC（最大化IC） + 权重熵（鼓励分散）
            loss = -predicted_ic + 0.01 * (weights * torch.log(weights + 1e-8)).sum()
            
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item()
        
        avg_loss = total_loss / len(train_data)
        scheduler.step(avg_loss)
        
        if epoch % 10 == 0:
            print(f"Epoch {epoch}: Loss = {avg_loss:.4f}")
```

**API接口**:

```python
# factor_api.py
@app.route('/api/v7/factors/compose', methods=['POST'])
def compose_factors():
    """
    动态因子组合
    
    POST /api/v7/factors/compose
    {
        "factor_values": {...},
        "factor_categories": [...],
        "market_features": {...}
    }
    """
    data = request.json
    
    composer = DynamicFactorComposer(weight_network)
    composite = composer.compose(
        pd.DataFrame(data['factor_values']),
        data['factor_categories'],
        pd.Series(data['market_features'])
    )
    
    return jsonify({
        'composite_factor': composite.to_dict(),
        'weights': composer.last_weights.tolist()
    })

@app.route('/api/v7/factors/regime-preferences', methods=['GET'])
def get_regime_preferences():
    """获取各政权下的因子偏好"""
    preferences = weight_network.get_regime_factor_preferences()
    return jsonify(preferences)
```

---

*Module: Factor Research Platform*  
*Sub-module: 2.1.3 - 2.1.4*  
*Status: 详细设计记录*
