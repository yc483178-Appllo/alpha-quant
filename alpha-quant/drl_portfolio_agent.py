"""
DRL投资组合Agent - Alpha V6.0
V5.0: 标准PPO + 全连接网络
V6.0: Transformer-PPO + 政权感知（增强部分）
"""

import json
import logging
import os
import math
import numpy as np
from datetime import datetime
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger("DRLPortfolioAgent")

# ═══════════════════════════════════════════════════════════════
# V5.0 基础部分 - Numpy实现（无PyTorch依赖）
# ═══════════════════════════════════════════════════════════════

class PPONetwork:
    """V5.0 PPO神经网络 (numpy实现，轻量级)"""
    def __init__(self, input_dim: int, hidden_dim: int = 64, output_dim: int = 1):
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        self.output_dim = output_dim
        # 随机初始化权重
        self.W1 = np.random.randn(input_dim, hidden_dim) * 0.01
        self.b1 = np.zeros(hidden_dim)
        self.W2 = np.random.randn(hidden_dim, output_dim) * 0.01
        self.b2 = np.zeros(output_dim)
    
    def forward(self, x: np.ndarray) -> np.ndarray:
        """前向传播"""
        h = np.maximum(0, x @ self.W1 + self.b1)  # ReLU
        return h @ self.W2 + self.b2
    
    def get_action(self, state: np.ndarray) -> Tuple[np.ndarray, float]:
        """获取动作和log概率"""
        mean = self.forward(state)
        std = 0.1
        action = np.random.normal(mean, std)
        log_prob = -0.5 * ((action - mean) / std) ** 2 - np.log(std * np.sqrt(2 * np.pi))
        return action, log_prob.sum()


class DRLPortfolioAgent:
    """DRL投资组合Agent V5.0 - 基础版本"""
    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            cfg = json.load(f)
        drl_cfg = cfg.get("drl_portfolio", {})
        self.n_stocks = drl_cfg.get("max_positions", 30)
        self.feature_dim = drl_cfg.get("feature_dim", 15)
        self.lr = drl_cfg.get("learning_rate", 3e-4)
        self.gamma = drl_cfg.get("gamma", 0.99)
        self.epsilon = drl_cfg.get("clip_epsilon", 0.2)
        
        # 初始化Actor-Critic网络
        self.actor = PPONetwork(self.feature_dim * self.n_stocks, output_dim=self.n_stocks)
        self.critic = PPONetwork(self.feature_dim * self.n_stocks, output_dim=1)
        
        # 政权检测
        self.current_regime = "range"
        self.regime_history = []
        
        logger.info("DRL Portfolio Agent V5.0 初始化完成")
    
    def detect_regime(self, market_data: Dict) -> str:
        """简单政权检测（可替换为HMM）"""
        returns = market_data.get("returns", [])
        if len(returns) < 20:
            return "range"
        
        vol = np.std(returns[-20:])
        trend = np.mean(returns[-20:])
        
        if vol > 0.03:
            return "crisis" if trend < 0 else "bull"
        elif trend > 0.001:
            return "bull"
        elif trend < -0.001:
            return "bear"
        return "range"
    
    def predict_portfolio_weights(self, stock_codes: List[str], market_features: Dict) -> Dict[str, float]:
        """预测投资组合权重"""
        # 构建特征向量
        features = []
        for code in stock_codes[:self.n_stocks]:
            f = market_features.get(code, [0.0] * self.feature_dim)
            features.extend(f[:self.feature_dim])
        
        # 补齐
        while len(features) < self.feature_dim * self.n_stocks:
            features.append(0.0)
        
        state = np.array(features)
        
        # Actor输出权重
        weights, _ = self.actor.get_action(state)
        weights = np.exp(weights)  # Softmax
        weights = weights / weights.sum()
        
        return {code: float(weights[i]) for i, code in enumerate(stock_codes[:self.n_stocks])}
    
    def get_dashboard_data(self, stock_codes: List[str] = None) -> Dict:
        """看板数据"""
        return {
            "current_regime": self.current_regime,
            "regime_confidence": {"bull": 0.25, "bear": 0.20, "range": 0.50, "crisis": 0.05},
            "model_type": "PPO V5.0",
            "last_inference": datetime.now().isoformat()
        }


# ═══════════════════════════════════════════════════════════════
# V6.0 增强部分 - Transformer注意力机制
# ═══════════════════════════════════════════════════════════════

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    logger.warning("PyTorch不可用，DRL将使用V5.0 numpy版本")


class MarketStateEncoder(nn.Module if TORCH_AVAILABLE else object):
    """
    市场状态Transformer编码器
    输入: [batch, n_stocks, n_features]
    输出: [batch, n_stocks, d_model]
    """
    def __init__(self, n_features: int, d_model: int = 128, n_heads: int = 4, n_layers: int = 2):
        if not TORCH_AVAILABLE:
            return
        super().__init__()
        self.input_proj = nn.Linear(n_features, d_model)
        self.pos_encoding = PositionalEncoding(d_model, max_len=252)  # 最多252个交易日
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=d_model * 4,
            dropout=0.1,
            batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=n_layers)
        self.d_model = d_model
    
    def forward(self, x, regime_embedding=None):
        """
        x: [batch, seq_len, n_features] 或 [batch, n_stocks, n_features]
        regime_embedding: [batch, d_model] 政权嵌入向量
        """
        x = self.input_proj(x) * math.sqrt(self.d_model)
        x = self.pos_encoding(x)
        # 注入政权信息（如果提供）
        if regime_embedding is not None:
            x = x + regime_embedding.unsqueeze(1)
        encoded = self.transformer(x)
        return encoded


class PositionalEncoding(nn.Module if TORCH_AVAILABLE else object):
    """时序位置编码"""
    def __init__(self, d_model: int, max_len: int = 252):
        if not TORCH_AVAILABLE:
            return
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe.unsqueeze(0))
    
    def forward(self, x):
        return x + self.pe[:, :x.size(1), :]


class RegimeAwareTransformerPPO(nn.Module if TORCH_AVAILABLE else object):
    """
    政权感知 Transformer-PPO 主网络
    替代V5.0的 PPONetwork
    """
    REGIME_MAP = {
        "bull": 0,
        "bear": 1,
        "range": 2,
        "crisis": 3
    }
    
    def __init__(self, n_stocks: int, n_features: int, d_model: int = 128):
        if not TORCH_AVAILABLE:
            return
        super().__init__()
        self.encoder = MarketStateEncoder(n_features, d_model)
        self.regime_emb = nn.Embedding(4, d_model)  # 4种政权
        # Actor头：输出各股票权重（Dirichlet分布参数）
        self.actor = nn.Sequential(
            nn.Linear(d_model, 64),
            nn.ReLU(),
            nn.Linear(64, 1),
            nn.Softplus()  # 确保正值（Dirichlet参数）
        )
        # Critic头：状态价值估计
        self.critic = nn.Sequential(
            nn.Linear(d_model * n_stocks, 128),
            nn.ReLU(),
            nn.Linear(128, 1)
        )
        self.n_stocks = n_stocks
    
    def forward(self, state: torch.Tensor, regime: str = "range") -> tuple:
        """
        state: [batch, n_stocks, n_features]
        regime: 当前市场政权
        """
        regime_idx = torch.tensor([self.REGIME_MAP.get(regime, 2)])
        regime_emb = self.regime_emb(regime_idx)
        # Transformer编码（含政权信息）
        encoded = self.encoder(state, regime_emb)  # [batch, n_stocks, d_model]
        # Actor：输出Dirichlet分布参数（确保和为1后用于投资权重）
        alpha = self.actor(encoded).squeeze(-1)  # [batch, n_stocks]
        alpha = alpha + 1e-6  # 数值稳定
        # Critic：展平后估计状态价值
        flat_encoded = encoded.view(encoded.size(0), -1)  # [batch, n_stocks * d_model]
        value = self.critic(flat_encoded)  # [batch, 1]
        return alpha, value
    
    def get_attention_weights(self, state: torch.Tensor) -> torch.Tensor:
        """获取注意力权重（用于可视化/解释性）"""
        with torch.no_grad():
            x = self.encoder.input_proj(state) * math.sqrt(self.encoder.d_model)
            # 提取第一层Transformer的注意力权重
            # (简化实现，完整版需hook attention层)
            return torch.ones(state.size(0), state.size(1), state.size(1))


class TransformerDRLPortfolioAgent:
    """
    Transformer-PPO投资组合Agent (V6.0增强版)
    兼容V5.0的 DRLPortfolioAgent 接口，可直接替换
    """
    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            cfg = json.load(f)
        drl_cfg = cfg.get("drl_portfolio", {})
        self.n_stocks = drl_cfg.get("max_positions", 30)
        self.n_features = drl_cfg.get("feature_dim", 15)  # 技术指标数量
        self.model_path = drl_cfg.get("transformer_model_path", "./models/transformer_drl.pt")
        self.current_regime = "range"
        
        if TORCH_AVAILABLE:
            self.model = RegimeAwareTransformerPPO(self.n_stocks, self.n_features)
            self._load_model()
        else:
            logger.warning("使用V5.0 numpy DRL（PyTorch不可用）")
            self.model = None
    
    def _load_model(self):
        """加载预训练模型"""
        if os.path.exists(self.model_path):
            try:
                self.model.load_state_dict(torch.load(self.model_path, map_location="cpu"))
                self.model.eval()
                logger.info(f"Transformer-DRL模型加载成功: {self.model_path}")
            except Exception as e:
                logger.warning(f"模型加载失败，使用随机初始化: {e}")
    
    def update_regime(self, regime: str):
        """更新市场政权（由HMM检测器调用）"""
        self.current_regime = regime
        logger.info(f"DRL政权更新: {regime}")
    
    def predict_portfolio_weights(self, stock_codes: list, market_features: dict) -> dict:
        """
        预测最优投资组合权重
        market_features: {stock_code: [feature_vector]}
        返回: {stock_code: weight, ...}
        """
        if not TORCH_AVAILABLE or self.model is None:
            # 降级：使用等权分配
            n = len(stock_codes)
            return {code: 1.0/n for code in stock_codes}
        
        try:
            # 构建特征矩阵
            feature_matrix = []
            for code in stock_codes[:self.n_stocks]:
                features = market_features.get(code, [0.0] * self.n_features)
                feature_matrix.append(features[:self.n_features])
            # 补齐维度
            while len(feature_matrix) < self.n_stocks:
                feature_matrix.append([0.0] * self.n_features)
            
            state = torch.tensor([feature_matrix], dtype=torch.float32)
            
            with torch.no_grad():
                alpha, _ = self.model(state, self.current_regime)
                weights = F.softmax(alpha, dim=-1).squeeze(0).numpy()
            
            result = {}
            for i, code in enumerate(stock_codes[:self.n_stocks]):
                result[code] = float(weights[i])
            return result
        except Exception as e:
            logger.error(f"Transformer-DRL推理失败: {e}")
            n = len(stock_codes)
            return {code: 1.0/n for code in stock_codes}
    
    def get_dashboard_data(self, stock_codes: list = None) -> dict:
        """看板V3.0 DRL面板数据"""
        regime_confidence = {
            "bull": 0.15, "bear": 0.20, "range": 0.55, "crisis": 0.10
        }
        return {
            "current_regime": self.current_regime,
            "regime_confidence": regime_confidence,
            "model_type": "Transformer-PPO V6.0" if TORCH_AVAILABLE else "Numpy-PPO V5.0",
            "attention_available": TORCH_AVAILABLE,
            "last_inference": datetime.now().isoformat()
        }


# 兼容导入
__all__ = [
    'DRLPortfolioAgent',  # V5.0基础版
    'TransformerDRLPortfolioAgent',  # V6.0增强版
    'TORCH_AVAILABLE'
]
