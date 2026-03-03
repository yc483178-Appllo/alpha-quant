"""
高级投资组合优化器
马科维茨 / Black-Litterman / 风险平价 / 最大分散度
兼容 V4.0 config.json 和 A股监管约束
"""

import numpy as np
from scipy.optimize import minimize
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from loguru import logger


@dataclass
class OptimizationResult:
    """优化结果数据结构"""
    weights: List[float]
    method: str
    expected_annual_return: float
    expected_annual_volatility: float
    sharpe_ratio: float
    position_count: int
    max_weight: float
    timestamp: str
    risk_contribution: Optional[List[float]] = None


class PortfolioOptimizer:
    """
    投资组合优化器 - 多算法支持
    
    支持4种优化算法:
    1. 马科维茨(MVO) - 低波动市场，经典均值方差
    2. Black-Litterman - 有情绪观点时，融合市场均衡+主观观点
    3. 风险平价 - 高波动市场，等风险贡献
    4. 最大分散度 - 相关性不稳定时，追求最大化分散化
    """

    # A股监管约束默认值
    DEFAULT_CONSTRAINTS = {
        "single_stock_max_pct": 0.10,      # 单票最大10%
        "sector_max_pct": 0.30,            # 单行业最大30%
        "min_position_count": 8,           # 最少持仓8只
        "max_position_count": 30,          # 最多持仓30只
        "min_weight": 0.02,               # 单票最小2%（低于则不持有）
        "st_forbidden": True,             # ST股禁入
        "new_stock_forbidden_days": 5,    # 新股上市5日内禁入
        "t_plus_1": True,                 # T+1交易规则
    }

    def __init__(self, config_path: str = "config.json"):
        import json
        with open(config_path) as f:
            config = json.load(f)
        
        self.cfg = config.get("portfolio_optimizer", {})
        self.constraints = {**self.DEFAULT_CONSTRAINTS, **self.cfg.get("constraints", {})}
        self.risk_free_rate = self.cfg.get("risk_free_rate", 0.03) / 252  # 日度无风险利率
        self.method = self.cfg.get("method", "black-litterman")
        
        # Black-Litterman参数
        self.bl_cfg = self.cfg.get("black_litterman", {})
        self.bl_tau = self.bl_cfg.get("uncertainty_scale", 0.1)
        self.bl_confidence = self.bl_cfg.get("confidence_in_views", 0.5)
        
        logger.info(f"✅ Portfolio Optimizer初始化完成 | method={self.method}")

    def optimize(
        self,
        expected_returns: np.ndarray,
        cov_matrix: np.ndarray,
        sentiment_views: Optional[Dict[int, float]] = None,
        method: Optional[str] = None,
        sector_map: Optional[Dict[int, str]] = None
    ) -> OptimizationResult:
        """
        统一优化入口
        
        Args:
            expected_returns: np.array (N,) 预期日收益率
            cov_matrix: np.array (N,N) 协方差矩阵
            sentiment_views: dict {stock_idx: view_return} 情绪观点（可选）
            method: 优化方法，None则使用配置默认值
            sector_map: dict {stock_idx: sector_name} 行业映射（用于行业约束）
        
        Returns:
            OptimizationResult: 优化结果
        """
        method = method or self.method
        n = len(expected_returns)
        
        logger.info(f"🎯 开始优化 | method={method}, assets={n}")

        # 根据方法选择优化算法
        if method == "markowitz":
            weights = self._markowitz(expected_returns, cov_matrix)
        elif method == "black-litterman":
            if sentiment_views:
                weights = self._black_litterman(expected_returns, cov_matrix, sentiment_views)
            else:
                logger.warning("⚠️ Black-Litterman需要sentiment_views，回退到Markowitz")
                weights = self._markowitz(expected_returns, cov_matrix)
        elif method == "risk-parity":
            weights = self._risk_parity(cov_matrix)
        elif method == "max-diversification":
            weights = self._max_diversification(cov_matrix)
        else:
            logger.warning(f"⚠️ 未知方法{method}，使用Markowitz")
            weights = self._markowitz(expected_returns, cov_matrix)

        # 施加A股约束
        weights = self._apply_constraints(weights, sector_map)

        # 计算组合指标
        port_return = np.dot(weights, expected_returns) * 252
        port_vol = np.sqrt(np.dot(weights, np.dot(cov_matrix, weights))) * np.sqrt(252)
        sharpe = (port_return - self.cfg.get("risk_free_rate", 0.03)) / port_vol if port_vol > 0 else 0
        
        # 计算风险贡献
        risk_contrib = self._calculate_risk_contribution(weights, cov_matrix)

        result = OptimizationResult(
            weights=weights.tolist(),
            method=method,
            expected_annual_return=round(float(port_return), 4),
            expected_annual_volatility=round(float(port_vol), 4),
            sharpe_ratio=round(float(sharpe), 4),
            position_count=int(np.sum(weights > self.constraints["min_weight"])),
            max_weight=round(float(np.max(weights)), 4),
            timestamp=datetime.now().isoformat(),
            risk_contribution=risk_contrib.tolist() if risk_contrib is not None else None
        )
        
        logger.info(f"✅ 优化完成 | return={result.expected_annual_return:.2%}, "
                   f"vol={result.expected_annual_volatility:.2%}, sharpe={result.sharpe_ratio:.2f}")
        
        return result

    def _markowitz(self, mu: np.ndarray, sigma: np.ndarray) -> np.ndarray:
        """
        马科维茨均值-方差优化
        
        最大化夏普比率
        """
        n = len(mu)
        w0 = np.ones(n) / n

        def neg_sharpe(w):
            ret = np.dot(w, mu)
            vol = np.sqrt(np.dot(w, np.dot(sigma, w)))
            return -(ret - self.risk_free_rate) / (vol + 1e-10)

        bounds = [(0, self.constraints.get("single_stock_max_pct", 0.10))] * n
        constraints = [
            {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}  # 权重和为1
        ]
        
        result = minimize(
            neg_sharpe, w0, method="SLSQP", 
            bounds=bounds, constraints=constraints,
            options={'maxiter': 1000, 'ftol': 1e-9}
        )
        
        if result.success:
            return result.x
        else:
            logger.warning(f"⚠️ Markowitz优化未收敛: {result.message}")
            return w0

    def _black_litterman(
        self,
        mu: np.ndarray,
        sigma: np.ndarray,
        views: Dict[int, float]
    ) -> np.ndarray:
        """
        Black-Litterman 模型
        
        融合市场均衡收益和主观观点（如舆情情绪）
        
        Args:
            mu: 预期收益
            sigma: 协方差矩阵
            views: {stock_idx: view_return} 观点收益
        """
        n = len(mu)
        tau = self.bl_tau
        confidence = self.bl_confidence

        # 市场隐含均衡收益（使用等权作为市场组合近似）
        w_market = np.ones(n) / n
        pi = np.dot(sigma, w_market) * tau

        # 构建观点矩阵
        m = len(views)
        if m == 0:
            logger.warning("⚠️ Black-Litterman无观点，回退到Markowitz")
            return self._markowitz(mu, sigma)
        
        P = np.zeros((m, n))
        Q = np.zeros(m)
        
        for i, (idx, view_ret) in enumerate(views.items()):
            if 0 <= idx < n:
                P[i, idx] = 1.0
                Q[i] = view_ret

        # 观点不确定性矩阵（对角阵）
        omega = np.diag(np.diag(P @ (tau * sigma) @ P.T)) / max(confidence, 0.01)

        try:
            # 后验收益计算
            inv_tau_sigma = np.linalg.inv(tau * sigma + np.eye(n) * 1e-10)
            inv_omega = np.linalg.inv(omega + np.eye(m) * 1e-10)
            
            posterior_cov = np.linalg.inv(inv_tau_sigma + P.T @ inv_omega @ P)
            posterior_mu = posterior_cov @ (inv_tau_sigma @ pi + P.T @ inv_omega @ Q)
            
            # 用后验收益做MVO
            return self._markowitz(posterior_mu, sigma)
            
        except np.linalg.LinAlgError as e:
            logger.error(f"❌ Black-Litterman矩阵求逆失败: {e}")
            return self._markowitz(mu, sigma)

    def _risk_parity(self, sigma: np.ndarray) -> np.ndarray:
        """
        风险平价配置
        
        使各资产对组合风险的贡献相等
        """
        n = sigma.shape[0]
        
        # 使用波动率倒数作为初始权重
        vols = np.sqrt(np.diag(sigma))
        inv_vols = 1.0 / (vols + 1e-10)
        weights = inv_vols / inv_vols.sum()
        
        # 迭代优化使风险贡献更均衡
        def risk_objective(w):
            port_vol = np.sqrt(np.dot(w, np.dot(sigma, w)))
            marginal_risk = np.dot(sigma, w) / (port_vol + 1e-10)
            risk_contrib = w * marginal_risk
            # 最小化风险贡献的方差
            return np.var(risk_contrib)
        
        bounds = [(0.001, self.constraints.get("single_stock_max_pct", 0.10))] * n
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        
        result = minimize(
            risk_objective, weights, method="SLSQP",
            bounds=bounds, constraints=constraints
        )
        
        return result.x if result.success else weights

    def _max_diversification(self, sigma: np.ndarray) -> np.ndarray:
        """
        最大分散度优化
        
        最大化加权平均波动率 / 组合波动率
        """
        n = sigma.shape[0]
        vols = np.sqrt(np.diag(sigma))
        w0 = np.ones(n) / n

        def neg_diversification(w):
            port_vol = np.sqrt(np.dot(w, np.dot(sigma, w)))
            weighted_avg_vol = np.dot(w, vols)
            return -(weighted_avg_vol / (port_vol + 1e-10))

        bounds = [(0, self.constraints.get("single_stock_max_pct", 0.10))] * n
        constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
        
        result = minimize(
            neg_diversification, w0, method="SLSQP",
            bounds=bounds, constraints=constraints
        )
        
        return result.x if result.success else w0

    def _apply_constraints(
        self,
        weights: np.ndarray,
        sector_map: Optional[Dict[int, str]] = None
    ) -> np.ndarray:
        """
        施加A股监管约束
        
        Args:
            weights: 原始权重
            sector_map: 行业映射 {idx: sector_name}
        """
        weights = weights.copy()
        max_w = self.constraints.get("single_stock_max_pct", 0.10)
        min_w = self.constraints.get("min_weight", 0.02)
        max_pos = self.constraints.get("max_position_count", 30)

        # 1. 上限裁剪
        weights = np.clip(weights, 0, max_w)
        
        # 2. 下限过滤
        weights[weights < min_w] = 0
        
        # 3. 限制持仓数量
        if np.sum(weights > 0) > max_pos:
            # 保留权重最大的max_pos只
            threshold = np.sort(weights)[-max_pos]
            weights[weights < threshold] = 0
        
        # 4. 行业约束
        if sector_map:
            weights = self._apply_sector_constraint(weights, sector_map)
        
        # 5. 重新归一化
        total = weights.sum()
        if total > 0:
            weights = weights / total
        
        return weights

    def _apply_sector_constraint(
        self,
        weights: np.ndarray,
        sector_map: Dict[int, str]
    ) -> np.ndarray:
        """施加行业约束"""
        max_sector_pct = self.constraints.get("sector_max_pct", 0.30)
        
        # 计算各行业权重
        sector_weights = {}
        for idx, sector in sector_map.items():
            if idx < len(weights):
                sector_weights[sector] = sector_weights.get(sector, 0) + weights[idx]
        
        # 如果某行业超限，等比例缩减该行业股票权重
        for sector, total_weight in sector_weights.items():
            if total_weight > max_sector_pct:
                scale = max_sector_pct / total_weight
                for idx, s in sector_map.items():
                    if s == sector and idx < len(weights):
                        weights[idx] *= scale
        
        return weights

    def _calculate_risk_contribution(
        self,
        weights: np.ndarray,
        sigma: np.ndarray
    ) -> Optional[np.ndarray]:
        """计算各资产的风险贡献"""
        try:
            port_vol = np.sqrt(np.dot(weights, np.dot(sigma, weights)))
            if port_vol < 1e-10:
                return None
            marginal_risk = np.dot(sigma, weights) / port_vol
            risk_contrib = weights * marginal_risk
            return risk_contrib / port_vol  # 归一化为百分比
        except:
            return None

    def auto_select_method(self, market_regime: str, volatility: float) -> str:
        """
        根据市场环境自动选择优化方法
        
        Args:
            market_regime: bear/bull/neutral
            volatility: 年化波动率
        
        Returns:
            str: 推荐的优化方法
        """
        if volatility > 0.25:  # 高波动
            return "risk-parity"
        elif market_regime == "bull" and volatility < 0.15:  # 牛市低波
            return "markowitz"
        elif market_regime == "neutral":  # 震荡市
            return "black-litterman"
        else:  # 熊市或相关不稳定
            return "max-diversification"

    def generate_signal_for_bus(self, result: OptimizationResult) -> Dict:
        """生成信号总线消息"""
        return {
            "type": "optimizer_recommendation",
            "source": "Alpha-Optimizer",
            "data": {
                "weights": result.weights,
                "method": result.method,
                "expected_return": result.expected_annual_return,
                "expected_risk": result.expected_annual_volatility,
                "sharpe_ratio": result.sharpe_ratio
            },
            "priority": "high" if result.sharpe_ratio > 1.0 else "medium",
            "timestamp": datetime.now().isoformat()
        }


# 便捷函数
def create_portfolio_optimizer(config_path: str = "config.json") -> PortfolioOptimizer:
    """创建Portfolio Optimizer实例"""
    return PortfolioOptimizer(config_path)


def quick_optimize(
    returns: List[float],
    cov_matrix: List[List[float]],
    method: str = "black-litterman"
) -> OptimizationResult:
    """快速优化（无需配置文件）"""
    optimizer = PortfolioOptimizer()
    return optimizer.optimize(
        np.array(returns),
        np.array(cov_matrix),
        method=method
    )


if __name__ == "__main__":
    # 测试Portfolio Optimizer
    print("测试投资组合优化器...")
    
    optimizer = create_portfolio_optimizer()
    
    # 模拟数据
    n = 10
    expected_returns = np.random.randn(n) * 0.001 + 0.0005  # 日收益
    cov_matrix = np.eye(n) * 0.0004  # 简化协方差
    
    # 测试各种方法
    methods = ["markowitz", "risk-parity", "max-diversification"]
    
    for method in methods:
        print(f"\n{'='*50}")
        print(f"方法: {method}")
        print('='*50)
        
        result = optimizer.optimize(expected_returns, cov_matrix, method=method)
        
        print(f"预期年化收益: {result.expected_annual_return:.2%}")
        print(f"预期年化波动: {result.expected_annual_volatility:.2%}")
        print(f"夏普比率: {result.sharpe_ratio:.2f}")
        print(f"持仓数量: {result.position_count}")
        print(f"最大权重: {result.max_weight:.2%}")
        print(f"权重分布: {[f'{w:.2%}' for w in result.weights[:5]]}...")
    
    # 测试Black-Litterman（带观点）
    print(f"\n{'='*50}")
    print("方法: black-litterman (带情绪观点)")
    print('='*50)
    
    views = {0: 0.001, 1: -0.0005}  # 看多第1只，看空第2只
    result = optimizer.optimize(expected_returns, cov_matrix, sentiment_views=views, method="black-litterman")
    
    print(f"预期年化收益: {result.expected_annual_return:.2%}")
    print(f"夏普比率: {result.sharpe_ratio:.2f}")
    print(f"前3只权重: {[f'{w:.2%}' for w in result.weights[:3]]}")
    
    print("\n✅ Portfolio Optimizer测试完成")
