# Alpha-Genesis V7.0 - DRL多模态融合模块

## 1. 架构概述

### 1.1 为什么需要多模态融合

| 信息源 | 频率 | 延迟 | 价值 |
|--------|------|------|------|
| 价格序列 | Tick/分钟 | 实时 | 市场微观结构 |
| 多因子数据 | 日频 | T+0 | 系统Alpha |
| 文本舆情 | 实时/日 | 分钟级 | 事件驱动Alpha |
| 股票关系 | 低频 | T+0 | 组合协同效应 |

**核心洞察**: 单一模态信息有限，融合多模态可显著提升决策质量

### 1.2 架构全景

```
输入层                    编码层                    融合层                    决策层
─────────────────────────────────────────────────────────────────────────────────
价格序列  ────┐
             │         ┌─────────────────┐
             ├────────▶│  TCN/Transformer │──────┐
             │         │   价格编码器      │      │
OHLCV数据  ────┘         └─────────────────┘      │      ┌─────────────────┐
                                                 │      │                 │
                                                 ├─────▶│   跨模态注意力   │─────▶ 策略网络 ────▶ 投资组合权重
多因子数据 ────┐                                   │      │    (Fusion)     │
             │         ┌─────────────────┐      │      │                 │
             ├────────▶│    因子编码器    │──────┤      └─────────────────┘
             │         │   (MLP/Transformer)│   │
             │         └─────────────────┘      │              ▲
                                                 │              │
文本舆情   ────┐         ┌─────────────────┐      │              │
             │         │   Kimi嵌入     │      │              │
             ├────────▶│   文本编码器    │──────┤              │
             │         └─────────────────┘      │              │
                                                 │              │
股票关系图 ────┐         ┌─────────────────┐      │              │
             │         │    GNN网络      │      │              │
             ├────────▶│   图编码器      │──────┘              │
             │         └─────────────────┘                     │
                                                               │
                                          回测反馈、市场奖励      │
                                                 ───────────────┘
```

## 2. 多模态编码器

### 2.1 价格序列编码器 (TCN + Attention)

```python
import torch
import torch.nn as nn
import torch.nn.functional as F


class TemporalBlock(nn.Module):
    """TCN时序块"""
    def __init__(
        self,
        in_channels: int,
        out_channels: int,
        kernel_size: int,
        stride: int,
        dilation: int,
        dropout: float = 0.2
    ):
        super().__init__()
        
        self.conv1 = nn.Conv1d(
            in_channels, out_channels, kernel_size,
            stride=stride, padding=(kernel_size-1) * dilation,
            dilation=dilation
        )
        self.relu1 = nn.ReLU()
        self.dropout1 = nn.Dropout(dropout)
        
        self.conv2 = nn.Conv1d(
            out_channels, out_channels, kernel_size,
            stride=stride, padding=(kernel_size-1) * dilation,
            dilation=dilation
        )
        self.relu2 = nn.ReLU()
        self.dropout2 = nn.Dropout(dropout)
        
        # 残差连接
        self.downsample = nn.Conv1d(in_channels, out_channels, 1) \
            if in_channels != out_channels else None
        
    def forward(self, x):
        # x: [B, C, T]
        out = self.conv1(x)
        out = out[:, :, :x.size(2)]  # 裁剪以保持长度
        out = self.relu1(out)
        out = self.dropout1(out)
        
        out = self.conv2(out)
        out = out[:, :, :x.size(2)]
        out = self.relu2(out)
        out = self.dropout2(out)
        
        res = x if self.downsample is None else self.downsample(x)
        return F.relu(out + res)


class PriceEncoder(nn.Module):
    """
    价格序列编码器
    TCN提取局部特征 + Transformer提取全局依赖
    """
    def __init__(
        self,
        input_dim: int = 5,  # OHLCV
        hidden_dim: int = 128,
        tcn_channels: List[int] = [64, 128, 128],
        kernel_size: int = 3,
        dropout: float = 0.2
    ):
        super().__init__()
        
        # TCN层
        layers = []
        in_ch = input_dim
        for i, out_ch in enumerate(tcn_channels):
            dilation = 2 ** i
            layers.append(TemporalBlock(
                in_ch, out_ch, kernel_size, stride=1,
                dilation=dilation, dropout=dropout
            ))
            in_ch = out_ch
        
        self.tcn = nn.Sequential(*layers)
        self.tcn_out_dim = tcn_channels[-1]
        
        # Transformer编码全局依赖
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=self.tcn_out_dim,
            nhead=8,
            dim_feedforward=self.tcn_out_dim * 4,
            dropout=dropout,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=2)
        
        # 输出投影
        self.output_proj = nn.Linear(self.tcn_out_dim, hidden_dim)
        
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Args:
            x: [B, T, input_dim] 价格序列
        Returns:
            [B, hidden_dim] 编码特征
        """
        # TCN需要 [B, C, T]
        x = x.transpose(1, 2)
        x = self.tcn(x)
        
        # Transformer需要 [B, T, C]
        x = x.transpose(1, 2)
        x = self.transformer(x)
        
        # 全局平均池化
        x = x.mean(dim=1)
        
        return self.output_proj(x)
```

### 2.2 多因子编码器

```python
class FactorEncoder(nn.Module):
    """
    多因子编码器
    处理Barra风格因子 + Alpha因子
    """
    def __init__(
        self,
        n_factors: int = 30,
        n_stocks: int = 500,
        hidden_dim: int = 128,
        n_layers: int = 3
    ):
        super().__init__()
        self.n_stocks = n_stocks
        
        # 个股因子嵌入
        self.factor_embed = nn.Sequential(
            nn.Linear(n_factors, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.1)
        )
        
        # 自注意力层 (学习因子间关系)
        self.attention_layers = nn.ModuleList([
            nn.MultiheadAttention(hidden_dim, n_heads=8, batch_first=True)
            for _ in range(n_layers)
        ])
        
        # 前馈网络
        self.ff_layers = nn.ModuleList([
            nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim * 4),
                nn.ReLU(),
                nn.Dropout(0.1),
                nn.Linear(hidden_dim * 4, hidden_dim),
                nn.LayerNorm(hidden_dim)
            )
            for _ in range(n_layers)
        ])
        
    def forward(self, factors: torch.Tensor) -> torch.Tensor:
        """
        Args:
            factors: [B, n_stocks, n_factors]
        Returns:
            [B, n_stocks, hidden_dim]
        """
        # 因子嵌入
        x = self.factor_embed(factors)  # [B, n_stocks, hidden_dim]
        
        # 自注意力层
        for attn, ff in zip(self.attention_layers, self.ff_layers):
            # 自注意力
            attn_out, _ = attn(x, x, x)
            x = x + attn_out
            
            # 前馈
            ff_out = ff(x)
            x = x + ff_out
        
        return x
```

### 2.3 文本舆情编码器 (Kimi嵌入)

```python
class TextEncoder(nn.Module):
    """
    文本舆情编码器
    使用预训练的Kimi嵌入 + 轻量级MLP微调
    """
    def __init__(
        self,
        embedding_dim: int = 1536,  # Kimi嵌入维度
        hidden_dim: int = 128,
        freeze_embeddings: bool = True
    ):
        super().__init__()
        
        # 假设Kimi嵌入通过API获取，这里只做变换
        self.embedding_proj = nn.Sequential(
            nn.Linear(embedding_dim, hidden_dim * 2),
            nn.LayerNorm(hidden_dim * 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim * 2, hidden_dim)
        )
        
        # 情感极性分类头 (用于辅助训练)
        self.sentiment_head = nn.Linear(hidden_dim, 3)  # 负面/中性/正面
        
    def forward(self, text_embeddings: torch.Tensor) -> torch.Tensor:
        """
        Args:
            text_embeddings: [B, embedding_dim] 预计算的Kimi嵌入
        Returns:
            [B, hidden_dim] 编码特征
        """
        features = self.embedding_proj(text_embeddings)
        return features
    
    def predict_sentiment(self, text_embeddings: torch.Tensor) -> torch.Tensor:
        """预测情感极性"""
        features = self.forward(text_embeddings)
        return self.sentiment_head(features)
```

### 2.4 GNN股票关系编码器

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GATConv, HeteroConv


class StockRelationGraph(nn.Module):
    """
    股票关系图神经网络
    建模: 行业关系、产业链关系、相关性关系
    """
    def __init__(
        self,
        n_stocks: int,
        node_feature_dim: int,
        hidden_dim: int = 128,
        n_layers: int = 3,
        n_heads: int = 4
    ):
        super().__init__()
        self.n_stocks = n_stocks
        
        # 异构图注意力层
        # 支持多种边类型
        self.convs = nn.ModuleList()
        for _ in range(n_layers):
            conv = HeteroConv({
                ('stock', 'industry', 'stock'): GATConv(
                    node_feature_dim if _ == 0 else hidden_dim,
                    hidden_dim // n_heads,
                    heads=n_heads,
                    concat=True,
                    dropout=0.2
                ),
                ('stock', 'supply_chain', 'stock'): GATConv(
                    node_feature_dim if _ == 0 else hidden_dim,
                    hidden_dim // n_heads,
                    heads=n_heads,
                    concat=True,
                    dropout=0.2
                ),
                ('stock', 'correlation', 'stock'): GATConv(
                    node_feature_dim if _ == 0 else hidden_dim,
                    hidden_dim // n_heads,
                    heads=n_heads,
                    concat=True,
                    dropout=0.2
                ),
            }, aggr='mean')
            self.convs.append(conv)
        
    def forward(
        self,
        x: torch.Tensor,
        edge_index_dict: Dict[str, torch.Tensor]
    ) -> torch.Tensor:
        """
        Args:
            x: [n_stocks, node_feature_dim] 节点特征
            edge_index_dict: {'edge_type': [2, n_edges]}
        Returns:
            [n_stocks, hidden_dim]
        """
        # 构建异构图数据
        x_dict = {'stock': x}
        
        for conv in self.convs:
            x_dict = conv(x_dict, edge_index_dict)
            x_dict = {key: F.relu(x) for key, x in x_dict.items()}
        
        return x_dict['stock']


class RelationEncoder(nn.Module):
    """关系编码器包装"""
    def __init__(self, n_stocks: int, input_dim: int, hidden_dim: int = 128):
        super().__init__()
        self.gnn = StockRelationGraph(n_stocks, input_dim, hidden_dim)
        
    def forward(
        self,
        node_features: torch.Tensor,
        industry_edges: torch.Tensor,
        supply_edges: torch.Tensor,
        corr_edges: torch.Tensor
    ) -> torch.Tensor:
        edge_index_dict = {
            ('stock', 'industry', 'stock'): industry_edges,
            ('stock', 'supply_chain', 'stock'): supply_edges,
            ('stock', 'correlation', 'stock'): corr_edges,
        }
        return self.gnn(node_features, edge_index_dict)
```

## 3. 跨模态融合

### 3.1 跨模态注意力融合

```python
class CrossModalAttention(nn.Module):
    """
    跨模态注意力融合
    学习不同模态间的交互关系
    """
    def __init__(
        self,
        n_stocks: int,
        hidden_dim: int = 128,
        n_heads: int = 8
    ):
        super().__init__()
        self.n_stocks = n_stocks
        self.hidden_dim = hidden_dim
        
        # 价格-因子交叉注意力
        self.price_factor_attn = nn.MultiheadAttention(
            hidden_dim, n_heads, batch_first=True
        )
        
        # 因子-文本交叉注意力
        self.factor_text_attn = nn.MultiheadAttention(
            hidden_dim, n_heads, batch_first=True
        )
        
        # 文本-价格交叉注意力
        self.text_price_attn = nn.MultiheadAttention(
            hidden_dim, n_heads, batch_first=True
        )
        
        # 门控融合
        self.gate = nn.Sequential(
            nn.Linear(hidden_dim * 4, hidden_dim),
            nn.Sigmoid()
        )
        
        # 最终融合
        self.fusion = nn.Sequential(
            nn.Linear(hidden_dim * 4, hidden_dim * 2),
            nn.LayerNorm(hidden_dim * 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim * 2, hidden_dim)
        )
        
    def forward(
        self,
        price_feat: torch.Tensor,   # [B, hidden_dim]
        factor_feat: torch.Tensor,  # [B, n_stocks, hidden_dim]
        text_feat: torch.Tensor,    # [B, hidden_dim]
        graph_feat: torch.Tensor    # [B, n_stocks, hidden_dim]
    ) -> torch.Tensor:
        """
        融合多模态特征
        Returns:
            [B, n_stocks, hidden_dim] 融合后的特征
        """
        B = price_feat.size(0)
        
        # 扩展价格特征到每只股票
        price_expanded = price_feat.unsqueeze(1).expand(-1, self.n_stocks, -1)
        
        # 扩展文本特征到每只股票
        text_expanded = text_feat.unsqueeze(1).expand(-1, self.n_stocks, -1)
        
        # 交叉注意力1: 价格关注因子
        pf_attn, _ = self.price_factor_attn(
            price_expanded, factor_feat, factor_feat
        )
        
        # 交叉注意力2: 因子关注文本
        ft_attn, _ = self.factor_text_attn(
            factor_feat, text_expanded, text_expanded
        )
        
        # 交叉注意力3: 文本关注价格
        tp_attn, _ = self.text_price_attn(
            text_expanded, price_expanded, price_expanded
        )
        
        # 合并所有特征
        combined = torch.cat([
            pf_attn,
            ft_attn,
            tp_attn,
            graph_feat
        ], dim=-1)  # [B, n_stocks, hidden_dim * 4]
        
        # 门控
        gate = self.gate(combined)
        
        # 融合
        fused = self.fusion(combined)
        fused = gate * fused + (1 - gate) * factor_feat  # 残差
        
        return fused
```

### 3.2 多模态状态表示

```python
class MultiModalStateEncoder(nn.Module):
    """
    多模态状态编码器
    整合所有模态输入为统一的状态表示
    """
    def __init__(
        self,
        n_stocks: int,
        price_dim: int = 5,
        n_factors: int = 30,
        text_embed_dim: int = 1536,
        hidden_dim: int = 128
    ):
        super().__init__()
        self.n_stocks = n_stocks
        
        # 各模态编码器
        self.price_encoder = PriceEncoder(price_dim, hidden_dim)
        self.factor_encoder = FactorEncoder(n_factors, n_stocks, hidden_dim)
        self.text_encoder = TextEncoder(text_embed_dim, hidden_dim)
        self.graph_encoder = RelationEncoder(n_stocks, hidden_dim, hidden_dim)
        
        # 跨模态融合
        self.cross_modal_fusion = CrossModalAttention(n_stocks, hidden_dim)
        
        # 全局状态编码
        self.global_encoder = nn.Sequential(
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU()
        )
        
    def forward(
        self,
        price_seq: torch.Tensor,
        factors: torch.Tensor,
        text_embed: torch.Tensor,
        graph_edges: Dict[str, torch.Tensor],
        node_features: torch.Tensor
    ) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Args:
            price_seq: [B, T, price_dim]
            factors: [B, n_stocks, n_factors]
            text_embed: [B, text_embed_dim]
            graph_edges: {'industry': [...], 'supply': [...], 'corr': [...]}
            node_features: [n_stocks, hidden_dim]
        Returns:
            stock_states: [B, n_stocks, hidden_dim] 每只股票的状态
            global_state: [B, hidden_dim] 全局市场状态
        """
        # 编码各模态
        price_feat = self.price_encoder(price_seq)  # [B, hidden_dim]
        factor_feat = self.factor_encoder(factors)  # [B, n_stocks, hidden_dim]
        text_feat = self.text_encoder(text_embed)   # [B, hidden_dim]
        
        # GNN编码 (需要batch处理)
        B = price_seq.size(0)
        graph_feats = []
        for i in range(B):
            gf = self.graph_encoder(
                node_features,
                graph_edges['industry'],
                graph_edges['supply'],
                graph_edges['corr']
            )
            graph_feats.append(gf)
        graph_feat = torch.stack(graph_feats)  # [B, n_stocks, hidden_dim]
        
        # 跨模态融合
        fused = self.cross_modal_fusion(
            price_feat, factor_feat, text_feat, graph_feat
        )  # [B, n_stocks, hidden_dim]
        
        # 全局状态
        global_feat = torch.cat([
            price_feat,
            text_feat
        ], dim=-1)
        global_state = self.global_encoder(global_feat)
        
        return fused, global_state
```

## 4. CRL约束强化学习

### 4.1 约束PPO (Constrained PPO)

```python
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.distributions import Categorical


class ConstrainedActorCritic(nn.Module):
    """
    约束Actor-Critic网络
    在标准PPO基础上增加约束处理
    """
    def __init__(
        self,
        state_dim: int,
        n_stocks: int,
        n_constraints: int = 3,  # 风险/换手/暴露约束
        hidden_dim: int = 256
    ):
        super().__init__()
        self.n_stocks = n_stocks
        self.n_constraints = n_constraints
        
        # 共享特征提取
        self.shared = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, hidden_dim),
            nn.LayerNorm(hidden_dim),
            nn.ReLU()
        )
        
        # Actor: 策略网络
        self.actor = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, n_stocks),
            nn.Softmax(dim=-1)  # 输出权重分布
        )
        
        # Critic: 价值网络
        self.critic = nn.Sequential(
            nn.Linear(hidden_dim, hidden_dim // 2),
            nn.ReLU(),
            nn.Linear(hidden_dim // 2, 1)
        )
        
        # Constraint Critics: 约束值估计
        self.constraint_critics = nn.ModuleList([
            nn.Sequential(
                nn.Linear(hidden_dim, hidden_dim // 2),
                nn.ReLU(),
                nn.Linear(hidden_dim // 2, 1)
            )
            for _ in range(n_constraints)
        ])
        
        # 约束阈值
        self.register_buffer('constraint_limits', torch.tensor([
            0.15,   # 最大回撤限制
            0.5,    # 换手率限制
            0.3     # 行业暴露限制
        ]))
        
    def forward(self, state: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        Returns:
            action_probs: [B, n_stocks]
            value: [B, 1]
            constraint_values: [B, n_constraints]
        """
        features = self.shared(state)
        
        action_probs = self.actor(features)
        value = self.critic(features)
        
        constraint_values = torch.stack([
            critic(features).squeeze(-1) for critic in self.constraint_critics
        ], dim=-1)  # [B, n_constraints]
        
        return action_probs, value, constraint_values
    
    def get_action(
        self,
        state: torch.Tensor,
        constraint_costs: torch.Tensor = None,
        deterministic: bool = False
    ) -> Tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """
        获取动作 (带约束处理)
        
        Args:
            constraint_costs: [B, n_constraints] 当前约束违反程度
        """
        action_probs, value, constraint_values = self.forward(state)
        
        # 如果存在约束违反，调整动作概率
        if constraint_costs is not None:
            action_probs = self._adjust_for_constraints(
                action_probs, constraint_costs, constraint_values
            )
        
        if deterministic:
            action = action_probs.argmax(dim=-1)
        else:
            dist = Categorical(action_probs)
            action = dist.sample()
        
        log_prob = torch.log(action_probs.gather(1, action.unsqueeze(1)) + 1e-8)
        
        return action, log_prob, value
    
    def _adjust_for_constraints(
        self,
        action_probs: torch.Tensor,
        constraint_costs: torch.Tensor,
        constraint_values: torch.Tensor
    ) -> torch.Tensor:
        """
        根据约束违反情况调整动作概率
        使用拉格朗日乘子法思想
        """
        # 计算约束违反程度
        violations = F.relu(constraint_costs - self.constraint_limits)
        
        # 如果存在违反，降低风险资产的权重
        if violations.sum() > 0:
            # 简化的约束调整：降低所有权重
            penalty = violations.sum(dim=-1, keepdim=True)
            action_probs = action_probs * (1 - penalty * 0.1)
            action_probs = action_probs / action_probs.sum(dim=-1, keepdim=True)
        
        return action_probs


class ConstrainedPPOTrainer:
    """约束PPO训练器"""
    def __init__(
        self,
        model: ConstrainedActorCritic,
        lr: float = 3e-4,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        clip_epsilon: float = 0.2,
        value_coef: float = 0.5,
        entropy_coef: float = 0.01,
        constraint_coef: float = 0.5,
        max_kl: float = 0.01
    ):
        self.model = model
        self.optimizer = torch.optim.Adam(model.parameters(), lr=lr)
        
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.clip_epsilon = clip_epsilon
        self.value_coef = value_coef
        self.entropy_coef = entropy_coef
        self.constraint_coef = constraint_coef
        self.max_kl = max_kl
        
        # 拉格朗日乘子 (用于约束)
        self.lagrange_multipliers = torch.ones(model.n_constraints) * 0.1
        
    def update(self, rollout_buffer: 'ConstrainedRolloutBuffer'):
        """PPO更新 (带约束)"""
        # 计算GAE优势
        advantages, returns = self._compute_gae(rollout_buffer)
        
        # 多epoch更新
        for epoch in range(4):
            for batch in rollout_buffer.get_batches():
                # 前向传播
                new_probs, new_values, new_constraint_values = self.model(batch['states'])
                new_log_probs = torch.log(new_probs.gather(1, batch['actions']) + 1e-8)
                
                # 比率
                ratio = torch.exp(new_log_probs - batch['old_log_probs'])
                
                # PPO策略损失
                surr1 = ratio * advantages
                surr2 = torch.clamp(ratio, 1-self.clip_epsilon, 1+self.clip_epsilon) * advantages
                policy_loss = -torch.min(surr1, surr2).mean()
                
                # 价值损失
                value_loss = F.mse_loss(new_values, returns)
                
                # 约束损失
                constraint_loss = 0
                for i in range(self.model.n_constraints):
                    violation = F.relu(
                        new_constraint_values[:, i] - self.model.constraint_limits[i]
                    )
                    constraint_loss += self.lagrange_multipliers[i] * violation.mean()
                
                # 熵损失
                entropy = -(new_probs * torch.log(new_probs + 1e-8)).sum(dim=-1).mean()
                
                # 总损失
                loss = (
                    policy_loss +
                    self.value_coef * value_loss +
                    self.constraint_coef * constraint_loss -
                    self.entropy_coef * entropy
                )
                
                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 0.5)
                self.optimizer.step()
                
                # 更新拉格朗日乘子
                with torch.no_grad():
                    for i in range(self.model.n_constraints):
                        avg_violation = F.relu(
                            new_constraint_values[:, i] - self.model.constraint_limits[i]
                        ).mean()
                        self.lagrange_multipliers[i] += 0.01 * avg_violation
                        self.lagrange_multipliers[i] = torch.clamp(
                            self.lagrange_multipliers[i], 0, 10
                        )
    
    def _compute_gae(self, rollout_buffer):
        """计算GAE"""
        # 实现GAE计算
        pass
```

## 5. SHAP可解释性分析

```python
import shap
import torch
import numpy as np


class DRLExplainer:
    """
    DRL决策可解释性分析
    使用SHAP值解释模型决策
    """
    def __init__(self, model: nn.Module):
        self.model = model
        self.explainer = None
        
    def explain_decision(
        self,
        state: Dict[str, torch.Tensor],
        action: int
    ) -> Dict:
        """
        解释单次决策
        
        Returns:
            shap_values: 各特征的SHAP值
            feature_importance: 特征重要性排序
        """
        # 将状态转换为特征向量
        features = self._state_to_features(state)
        
        # 创建SHAP解释器
        if self.explainer is None:
            self.explainer = shap.DeepExplainer(
                self.model,
                self._get_background_data()
            )
        
        # 计算SHAP值
        shap_values = self.explainer.shap_values(features)
        
        # 分析特征重要性
        importance = np.abs(shap_values).mean(axis=0)
        
        return {
            'shap_values': shap_values.tolist(),
            'feature_importance': importance.tolist(),
            'base_value': self.explainer.expected_value,
            'prediction': self.model(features)[0].argmax().item()
        }
    
    def explain_portfolio_weights(
        self,
        weights: np.ndarray,
        states: List[Dict]
    ) -> pd.DataFrame:
        """
        解释投资组合权重分配
        
        Returns:
            DataFrame: 各股票权重的主要驱动因素
        """
        explanations = []
        
        for i, (weight, state) in enumerate(zip(weights, states)):
            if weight > 0.01:  # 只解释显著持仓
                exp = self.explain_decision(state, i)
                exp['stock'] = i
                exp['weight'] = weight
                explanations.append(exp)
        
        return pd.DataFrame(explanations)
    
    def generate_explanation_report(self, decision_history: List[Dict]) -> str:
        """生成可解释性报告"""
        report = []
        report.append("=" * 60)
        report.append("DRL决策可解释性报告")
        report.append("=" * 60)
        
        # 统计最常使用的特征
        all_importance = []
        for decision in decision_history:
            all_importance.append(decision['feature_importance'])
        
        avg_importance = np.mean(all_importance, axis=0)
        top_features = np.argsort(avg_importance)[-10:][::-1]
        
        report.append("\nTop 10 重要特征:")
        for i, idx in enumerate(top_features, 1):
            report.append(f"  {i}. 特征{idx}: {avg_importance[idx]:.4f}")
        
        report.append("\n决策一致性分析:")
        # 分析模型决策的稳定性
        
        return "\n".join(report)
```

## 6. 完整训练流程

```python
class MultiModalDRLTrainer:
    """多模态DRL训练器"""
    def __init__(
        self,
        state_encoder: MultiModalStateEncoder,
        policy_model: ConstrainedActorCritic,
        env: 'TradingEnvironment',
        config: Dict
    ):
        self.state_encoder = state_encoder
        self.policy_model = policy_model
        self.env = env
        self.config = config
        
        self.trainer = ConstrainedPPOTrainer(policy_model)
        self.explainer = DRLExplainer(policy_model)
        
    def train(self, n_episodes: int = 1000):
        """训练主循环"""
        for episode in range(n_episodes):
            state = self.env.reset()
            episode_reward = 0
            
            while True:
                # 编码多模态状态
                stock_states, global_state = self.state_encoder(
                    price_seq=state['price_seq'],
                    factors=state['factors'],
                    text_embed=state['text_embed'],
                    graph_edges=state['graph_edges'],
                    node_features=state['node_features']
                )
                
                # 组合状态
                combined_state = torch.cat([
                    stock_states.view(stock_states.size(0), -1),
                    global_state
                ], dim=-1)
                
                # 获取动作
                action, log_prob, value = self.policy_model.get_action(combined_state)
                
                # 执行动作
                next_state, reward, done, info = self.env.step(action)
                
                # 存储经验
                # ...
                
                episode_reward += reward
                state = next_state
                
                if done:
                    break
            
            # 更新策略
            if episode % self.config['update_freq'] == 0:
                self.trainer.update(rollout_buffer)
            
            # 日志
            if episode % 10 == 0:
                print(f"Episode {episode}: Reward = {episode_reward:.2f}")

    def evaluate(self, n_episodes: int = 10) -> Dict:
        """评估模型"""
        results = []
        
        for _ in range(n_episodes):
            state = self.env.reset()
            episode_reward = 0
            
            while True:
                # ... 类似train的前向传播 ...
                action, _, _ = self.policy_model.get_action(
                    state, deterministic=True
                )
                state, reward, done, _ = self.env.step(action)
                episode_reward += reward
                
                if done:
                    break
            
            results.append(episode_reward)
        
        return {
            'mean_reward': np.mean(results),
            'std_reward': np.std(results),
            'sharpe': np.mean(results) / np.std(results) if np.std(results) > 0 else 0
        }
```

## 7. API接口

```python
from flask import Flask, request, jsonify

app = Flask(__name__)
drl_model = None
state_encoder = None

@app.route('/api/v7/drl/predict', methods=['POST'])
def drl_predict():
    """DRL预测接口"""
    data = request.json
    
    # 编码状态
    stock_states, global_state = state_encoder(
        price_seq=torch.tensor(data['price_seq']),
        factors=torch.tensor(data['factors']),
        text_embed=torch.tensor(data['text_embed']),
        graph_edges=data['graph_edges'],
        node_features=torch.tensor(data['node_features'])
    )
    
    # 预测
    combined = torch.cat([
        stock_states.view(1, -1),
        global_state
    ], dim=-1)
    
    action_probs, value, constraints = drl_model(combined)
    
    return jsonify({
        'portfolio_weights': action_probs.tolist()[0],
        'state_value': value.item(),
        'constraint_predictions': constraints.tolist()[0]
    })

@app.route('/api/v7/drl/explain', methods=['POST'])
def drl_explain():
    """DRL决策解释接口"""
    data = request.json
    
    explanation = explainer.explain_decision(
        state=data['state'],
        action=data['action']
    )
    
    return jsonify(explanation)
```

---

*Module: Multi-Modal DRL Fusion*  
*Version: V7.0*  
*Status: 详细设计完成，待实施*
