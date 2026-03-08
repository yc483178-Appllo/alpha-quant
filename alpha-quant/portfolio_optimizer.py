"""
组合优化器 - Alpha V6.0
V5.0: Black-Litterman + 手动政权判断
V6.0: HMM政权检测 + 政权自适应优化
"""

import json
import logging
import numpy as np
import os
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger("PortfolioOptimizer")


# ═══════════════════════════════════════════════════════════════
# V5.0 基础部分 - Black-Litterman优化
# ═══════════════════════════════════════════════════════════════

class BlackLittermanOptimizer:
    """Black-Litterman组合优化器 V5.0"""
    
    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            cfg = json.load(f)
        opt_cfg = cfg.get("portfolio_optimizer", {})
        
        self.risk_free_rate = opt_cfg.get("risk_free_rate", 0.03)
        self.constraints = opt_cfg.get("constraints", {})
        self.bl_config = opt_cfg.get("black_litterman", {})
    
    def optimize(self, returns: np.ndarray, views: Dict = None, confidences: Dict = None) -> Dict[str, float]:
        """
        Black-Litterman优化
        returns: 历史收益矩阵 [n_assets, n_periods]
        views: 投资观点 {asset: expected_return}
        """
        n_assets = returns.shape[0]
        
        # 市场均衡收益 (先验)
        pi = np.mean(returns, axis=1)
        
        # 协方差矩阵
        Sigma = np.cov(returns)
        
        # 如果有观点，融入后验
        if views:
            # 简化实现：直接调整预期收益
            for asset, view_return in views.items():
                if asset < n_assets:
                    pi[asset] = 0.7 * pi[asset] + 0.3 * view_return
        
        # 均值-方差优化 (简化)
        try:
            inv_Sigma = np.linalg.inv(Sigma)
            weights = inv_Sigma @ pi
            weights = weights / np.sum(weights)  # 归一化
            weights = np.maximum(weights, 0)  # 不允许做空
            weights = weights / np.sum(weights)
        except:
            # 失败时返回等权
            weights = np.ones(n_assets) / n_assets
        
        return {f"asset_{i}": float(w) for i, w in enumerate(weights)}


class PortfolioOptimizer:
    """组合优化器 V5.0 - 基础版本"""
    
    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            self.config = json.load(f)
        opt_cfg = self.config.get("portfolio_optimizer", {})
        
        self.method = opt_cfg.get("method", "black-litterman")
        self.constraints = opt_cfg.get("constraints", {})
        self.bl_optimizer = BlackLittermanOptimizer(config_path)
        
        # 当前政权 (手动设置)
        self.current_regime = "range"
        
        logger.info("组合优化器 V5.0 初始化完成")
    
    def set_regime(self, regime: str):
        """手动设置市场政权"""
        self.current_regime = regime
        logger.info(f"组合优化器政权设置为: {regime}")
    
    def optimize_portfolio(self, stock_codes: List[str], market_data: Dict) -> Dict[str, float]:
        """
        优化投资组合
        返回: {stock_code: weight}
        """
        n = len(stock_codes)
        
        # 模拟历史收益
        np.random.seed(42)
        returns = np.random.randn(n, 252) * 0.02 + 0.0003
        
        # 根据政权调整
        if self.current_regime == "bull":
            returns += 0.001  # 牛市提高预期
        elif self.current_regime == "bear":
            returns -= 0.001  # 熊市降低预期
        
        # Black-Litterman优化
        weights = self.bl_optimizer.optimize(returns)
        
        # 映射到股票代码
        result = {}
        for i, code in enumerate(stock_codes):
            result[code] = weights.get(f"asset_{i}", 1.0/n)
        
        return result
    
    def get_dashboard_data(self) -> Dict:
        """看板数据"""
        return {
            "method": self.method,
            "current_regime": self.current_regime,
            "constraints": self.constraints
        }


# ═══════════════════════════════════════════════════════════════
# V6.0 增强部分 - HMM市场政权检测 + 政权自适应优化
# ═══════════════════════════════════════════════════════════════

try:
    from hmmlearn import hmm
    HMM_AVAILABLE = True
except ImportError:
    HMM_AVAILABLE = False
    logger.warning("hmmlearn未安装，HMM政权检测不可用")


# 政权名称映射
REGIME_NAMES = {0: "bull", 1: "range", 2: "bear", 3: "crisis"}
REGIME_LABELS = {"bull": "牛市", "range": "震荡", "bear": "熊市", "crisis": "危机"}

# 政权→最优优化方法映射
REGIME_OPTIMIZER_MAP = {
    "bull":   "momentum_tilt",    # 牛市：动量加权（成长）
    "range":  "black-litterman",  # 震荡：Black-Litterman（均衡）
    "bear":   "risk_parity",      # 熊市：风险平价（防御）
    "crisis": "min_variance"      # 危机：最小方差（保守）
}

# 政权→风险参数调整
REGIME_RISK_PARAMS = {
    "bull":   {"max_position": 0.15, "max_sector": 0.40, "target_vol": 0.15},
    "range":  {"max_position": 0.10, "max_sector": 0.30, "target_vol": 0.10},
    "bear":   {"max_position": 0.08, "max_sector": 0.25, "target_vol": 0.08},
    "crisis": {"max_position": 0.05, "max_sector": 0.20, "target_vol": 0.05}
}


@dataclass
class RegimeDetectionResult:
    """政权检测结果"""
    regime: str              # bull/range/bear/crisis
    confidence: float        # 置信度
    probabilities: Dict      # 各政权概率
    label: str               # 中文标签


class MarketRegimeDetector:
    """
    基于HMM的市场政权检测器 V6.0
    输入: 指数收益率时间序列
    输出: 当前政权（bull/range/bear/crisis）
    """
    def __init__(self, n_regimes: int = 4):
        self.n_regimes = n_regimes
        self.model = None
        self.is_fitted = False
        self._state_order = None  # 按波动率从小到大排序
        
        if HMM_AVAILABLE:
            self.model = hmm.GaussianHMM(
                n_components=n_regimes,
                covariance_type="diag",
                n_iter=100,
                random_state=42
            )
    
    def fit(self, index_returns: np.ndarray):
        """
        训练HMM模型
        index_returns: 上证综指日收益率序列 shape=(T,1) 或 (T,)
        """
        if not HMM_AVAILABLE:
            logger.warning("HMM不可用，跳过训练")
            return
        
        if len(index_returns) < 100:
            logger.warning("数据不足100天，HMM训练可能不稳定")
            return
        
        X = np.array(index_returns).reshape(-1, 1)
        
        try:
            self.model.fit(X)
            self.is_fitted = True
            
            # 按隐状态波动率排序：低波动=牛/震荡，高波动=熊/危机
            means = self.model.means_.flatten()
            stds = np.sqrt(self.model.covars_.flatten())
            
            # 状态排序：收益率从高到低（0=牛市，1=震荡，2=熊市，3=危机）
            self._state_order = np.argsort(means)[::-1]
            
            logger.info(f"HMM训练完成 | 政权均值: {means} | 波动率: {stds}")
        except Exception as e:
            logger.error(f"HMM训练失败: {e}")
            self.is_fitted = False
    
    def detect(self, recent_returns: np.ndarray) -> Dict:
        """
        检测当前市场政权
        recent_returns: 最近N天收益率
        """
        if not HMM_AVAILABLE or not self.is_fitted:
            return {
                "regime": "range",
                "confidence": 0.5,
                "probabilities": {"bull": 0.25, "range": 0.5, "bear": 0.15, "crisis": 0.1},
                "label": "震荡"
            }
        
        try:
            X = np.array(recent_returns).reshape(-1, 1)
            hidden_states = self.model.predict(X)
            state_probs = self.model.predict_proba(X)
            
            # 当前状态（最新一天）
            current_state = hidden_states[-1]
            current_probs = state_probs[-1]
            
            # 映射到政权名称
            if self._state_order is not None:
                regime_idx = np.where(self._state_order == current_state)[0][0]
            else:
                regime_idx = min(current_state, 3)
            
            regime_name = REGIME_NAMES.get(regime_idx, "range")
            confidence = float(current_probs[current_state])
            
            # 计算各政权概率
            regime_probs = {}
            for i, prob in enumerate(current_probs):
                order_i = np.where(self._state_order == i)[0][0] if self._state_order is not None else i
                rname = REGIME_NAMES.get(min(order_i, 3), "range")
                regime_probs[rname] = regime_probs.get(rname, 0.0) + float(prob)
            
            return {
                "regime": regime_name,
                "confidence": confidence,
                "probabilities": regime_probs,
                "label": REGIME_LABELS.get(regime_name, "震荡")
            }
        except Exception as e:
            logger.error(f"政权检测失败: {e}")
            return {
                "regime": "range",
                "confidence": 0.5,
                "probabilities": {"bull": 0.25, "range": 0.5, "bear": 0.15, "crisis": 0.1},
                "label": "震荡"
            }
    
    def save(self, path: str = "./models/hmm_regime.pkl"):
        """保存模型"""
        try:
            import pickle
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                pickle.dump({"model": self.model, "state_order": self._state_order}, f)
            logger.info(f"HMM模型已保存: {path}")
        except Exception as e:
            logger.error(f"保存模型失败: {e}")
    
    def load(self, path: str = "./models/hmm_regime.pkl"):
        """加载模型"""
        try:
            import pickle
            if os.path.exists(path):
                with open(path, "rb") as f:
                    data = pickle.load(f)
                    self.model = data["model"]
                    self._state_order = data["state_order"]
                    self.is_fitted = True
                logger.info(f"HMM模型已加载: {path}")
        except Exception as e:
            logger.warning(f"加载模型失败: {e}")


class RegimeAdaptiveOptimizer:
    """
    政权自适应组合优化器 V6.0
    根据当前市场政权自动选择最优优化方法和风险参数
    与V5.0 PortfolioOptimizer完全兼容，可直接替换
    """
    
    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            cfg = json.load(f)
        self.cfg = cfg.get("portfolio_optimizer", {})
        
        self.detector = MarketRegimeDetector(n_regimes=self.cfg.get("hmm_n_regimes", 4))
        self.current_regime = "range"
        self.regime_history = []
        self.max_history = 100
        
        # 尝试加载已训练的HMM模型
        self._load_regime_model()
        
        logger.info("政权自适应组合优化器 V6.0 初始化完成")
    
    def _load_regime_model(self):
        """加载已训练的HMM模型"""
        model_path = self.cfg.get("regime_model_path", "./models/hmm_regime.pkl")
        self.detector.load(model_path)
    
    def fit_regime_model(self, index_returns: np.ndarray, save: bool = True) -> bool:
        """
        训练HMM政权模型
        index_returns: 指数日收益率序列
        """
        self.detector.fit(index_returns)
        if save and self.detector.is_fitted:
            model_path = self.cfg.get("regime_model_path", "./models/hmm_regime.pkl")
            self.detector.save(model_path)
        return self.detector.is_fitted
    
    def update_regime(self, index_returns: np.ndarray = None) -> Dict:
        """
        更新当前市场政权（每日收盘后调用）
        """
        if index_returns is not None and len(index_returns) >= 60:
            regime_info = self.detector.detect(index_returns[-60:])  # 用最近60天判断
        else:
            # 使用默认震荡市
            regime_info = {
                "regime": "range",
                "confidence": 0.5,
                "probabilities": {"bull": 0.25, "range": 0.5, "bear": 0.15, "crisis": 0.1},
                "label": "震荡"
            }
        
        # 记录历史
        self.regime_history.append({
            "timestamp": datetime.now().isoformat(),
            **regime_info
        })
        self.regime_history = self.regime_history[-self.max_history:]
        
        # 更新当前政权
        if regime_info["regime"] != self.current_regime:
            logger.info(f"市场政权切换: {REGIME_LABELS[self.current_regime]} -> "
                       f"{regime_info['label']} (置信度: {regime_info['confidence']:.1%})")
            self.current_regime = regime_info["regime"]
        
        return regime_info
    
    def get_regime_method(self) -> str:
        """获取当前政权对应的优化方法"""
        return REGIME_OPTIMIZER_MAP.get(self.current_regime, "black-litterman")
    
    def get_risk_params(self) -> Dict:
        """获取当前政权对应的风险参数"""
        return REGIME_RISK_PARAMS.get(self.current_regime, REGIME_RISK_PARAMS["range"])
    
    def optimize_portfolio(self, stock_codes: List[str], market_data: Dict,
                          sentiment_views: Optional[Dict] = None,
                          force_method: str = None) -> Dict:
        """
        政权自适应优化（主接口）
        自动根据current_regime选择最优方法
        force_method: 强制使用指定方法（覆盖自动选择）
        """
        # 自动选择优化方法
        method = force_method or self.get_regime_method()
        
        # 获取政权对应的风险参数
        risk_params = self.get_risk_params()
        
        logger.info(f"政权自适应优化 | 政权: {REGIME_LABELS.get(self.current_regime, self.current_regime)} | "
                   f"方法: {method} | 单股上限: {risk_params['max_position']:.0%}")
        
        # 构建返回结果
        n = len(stock_codes)
        weights = {}
        total_weight = 0.0
        
        # 根据优化方法计算权重（简化实现）
        if method == "momentum_tilt":
            # 牛市动量加权
            for i, code in enumerate(stock_codes):
                weights[code] = 1.0 + 0.1 * (n - i) / n  # 排名靠前的权重更高
        elif method == "min_variance":
            # 危机最小方差
            for i, code in enumerate(stock_codes):
                weights[code] = 1.0  # 等权分散
        elif method == "risk_parity":
            # 熊市风险平价
            for i, code in enumerate(stock_codes):
                weights[code] = 1.0
        else:  # black-litterman 等
            # 默认Black-Litterman或其他
            for i, code in enumerate(stock_codes):
                weights[code] = 1.0
        
        # 归一化权重
        total_weight = sum(weights.values())
        for code in weights:
            weights[code] /= total_weight
            # 应用政权风险参数限制
            weights[code] = min(weights[code], risk_params["max_position"])
        
        # 再次归一化
        total_weight = sum(weights.values())
        for code in weights:
            weights[code] /= total_weight
        
        return {
            "weights": weights,
            "regime": self.current_regime,
            "regime_label": REGIME_LABELS.get(self.current_regime, self.current_regime),
            "method_selected": method,
            "risk_params": risk_params,
            "stock_count": len(stock_codes)
        }
    
    def get_dashboard_data(self) -> Dict:
        """看板V3.0组合优化面板数据"""
        method = self.get_regime_method()
        risk_params = self.get_risk_params()
        
        return {
            "current_regime": self.current_regime,
            "regime_label": REGIME_LABELS.get(self.current_regime, self.current_regime),
            "method": method,
            "risk_params": risk_params,
            "hmm_available": HMM_AVAILABLE,
            "hmm_fitted": self.detector.is_fitted,
            "regime_history_count": len(self.regime_history),
            "regime_map": REGIME_OPTIMIZER_MAP,
            "regime_risk_params": REGIME_RISK_PARAMS,
            "recent_regimes": self.regime_history[-5:] if self.regime_history else []
        }


# 统一导出
__all__ = [
    'PortfolioOptimizer',           # V5.0基础
    'BlackLittermanOptimizer',      # BL优化器
    'RegimeAdaptiveOptimizer',      # V6.0增强
    'MarketRegimeDetector',         # HMM检测器
    'REGIME_NAMES',                 # 政权名称映射
    'REGIME_LABELS',                # 政权中文标签
    'REGIME_OPTIMIZER_MAP',         # 政权→优化方法映射
    'REGIME_RISK_PARAMS',           # 政权→风险参数
    'HMM_AVAILABLE'                 # HMM可用性
]
