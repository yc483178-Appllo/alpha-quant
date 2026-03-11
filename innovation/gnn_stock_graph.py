"""
Kimi Claw V7.0 创新研究模块 (Innovation Research)

包含Claude创新的前沿技术:
- 图神经网络 (GNN) 股票关系图
- 扩散模型 (Diffusion) 场景生成
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class StockNode:
    """股票节点"""
    symbol: str
    features: np.ndarray
    sector: str
    market_cap: float


@dataclass
class StockEdge:
    """股票关系边"""
    source: str
    target: str
    relation_type: str  # industry_correlation, supply_chain, ownership
    weight: float


class StockRelationGraph:
    """
    图神经网络 (GNN) 股票关系图
    
    构建股票间的关系网络:
    - 行业相关性边
    - 供应链关系边
    - 股权关系边
    """
    
    def __init__(self):
        self.nodes: Dict[str, StockNode] = {}
        self.edges: List[StockEdge] = []
        self.adjacency_matrix: Optional[np.ndarray] = None
        
    def add_stock(self, symbol: str, features: np.ndarray, 
                  sector: str, market_cap: float):
        """添加股票节点"""
        self.nodes[symbol] = StockNode(
            symbol=symbol,
            features=features,
            sector=sector,
            market_cap=market_cap
        )
        
    def add_relation(self, source: str, target: str, 
                    relation_type: str, weight: float):
        """添加关系边"""
        self.edges.append(StockEdge(
            source=source,
            target=target,
            relation_type=relation_type,
            weight=weight
        ))
        
    def build_industry_edges(self, correlation_threshold: float = 0.7):
        """构建行业相关性边"""
        symbols = list(self.nodes.keys())
        
        for i, sym1 in enumerate(symbols):
            for sym2 in symbols[i+1:]:
                node1 = self.nodes[sym1]
                node2 = self.nodes[sym2]
                
                # 同行业的股票建立边
                if node1.sector == node2.sector:
                    # 计算特征相关性
                    corr = np.corrcoef(node1.features, node2.features)[0, 1]
                    if abs(corr) > correlation_threshold:
                        self.add_relation(sym1, sym2, "industry_correlation", abs(corr))
                        
    def build_graph(self):
        """构建图结构"""
        n = len(self.nodes)
        self.adjacency_matrix = np.zeros((n, n))
        
        symbol_to_idx = {sym: i for i, sym in enumerate(self.nodes.keys())}
        
        for edge in self.edges:
            if edge.source in symbol_to_idx and edge.target in symbol_to_idx:
                i = symbol_to_idx[edge.source]
                j = symbol_to_idx[edge.target]
                self.adjacency_matrix[i, j] = edge.weight
                self.adjacency_matrix[j, i] = edge.weight  # 无向图
                
        logger.info(f"Graph built: {n} nodes, {len(self.edges)} edges")
        
    def get_neighbors(self, symbol: str, hop: int = 1) -> List[str]:
        """获取邻居节点"""
        if symbol not in self.nodes:
            return []
            
        neighbors = set()
        for edge in self.edges:
            if edge.source == symbol:
                neighbors.add(edge.target)
            elif edge.target == symbol:
                neighbors.add(edge.source)
                
        return list(neighbors)
    
    def propagate_signal(self, initial_signals: Dict[str, float], 
                        iterations: int = 3) -> Dict[str, float]:
        """
        图信号传播
        
        基于邻居节点的信号传播和聚合
        """
        signals = initial_signals.copy()
        
        for _ in range(iterations):
            new_signals = signals.copy()
            
            for symbol in self.nodes:
                if symbol not in signals:
                    continue
                    
                neighbors = self.get_neighbors(symbol)
                neighbor_signals = [signals.get(n, 0) for n in neighbors]
                
                if neighbor_signals:
                    # 聚合邻居信号
                    aggregated = np.mean(neighbor_signals)
                    # 更新信号
                    new_signals[symbol] = 0.7 * signals[symbol] + 0.3 * aggregated
                    
            signals = new_signals
            
        return signals


class DiffusionScenarioGenerator:
    """
    扩散模型 (Diffusion) 场景生成器
    
    生成极端市场情景用于压力测试
    """
    
    def __init__(self, num_timesteps: int = 100):
        self.num_timesteps = num_timesteps
        self.scenarios: List[Dict] = []
        
    def generate_crash_scenario(self, 
                               base_prices: Dict[str, float],
                               crash_magnitude: float = 0.3) -> Dict[str, List[float]]:
        """
        生成崩盘情景
        
        Args:
            base_prices: 基准价格
            crash_magnitude: 下跌幅度 (默认30%)
            
        Returns:
            价格路径
        """
        scenario = {}
        
        for symbol, base_price in base_prices.items():
            # 生成下跌路径
            path = [base_price]
            current = base_price
            
            for t in range(self.num_timesteps):
                # 扩散过程：逐步下跌
                drift = -crash_magnitude / self.num_timesteps
                shock = np.random.normal(0, 0.02)  # 波动冲击
                
                current = current * (1 + drift + shock)
                path.append(max(current, base_price * 0.1))  # 最低10%
                
            scenario[symbol] = path
            
        return scenario
    
    def generate_volatility_spike(self,
                                 base_prices: Dict[str, float],
                                 spike_factor: float = 3.0) -> Dict[str, List[float]]:
        """
        生成波动率飙升情景
        
        Args:
            base_prices: 基准价格
            spike_factor: 波动率放大倍数
            
        Returns:
            价格路径
        """
        scenario = {}
        
        for symbol, base_price in base_prices.items():
            path = [base_price]
            current = base_price
            
            for t in range(self.num_timesteps):
                # 高波动随机游走
                shock = np.random.normal(0, 0.05 * spike_factor)
                current = current * (1 + shock)
                path.append(max(current, base_price * 0.5))
                
            scenario[symbol] = path
            
        return scenario
    
    def generate_liquidity_crisis(self,
                                  base_prices: Dict[str, float],
                                  volume_drop: float = 0.8) -> Dict[str, Any]:
        """
        生成流动性危机情景
        
        Returns:
            包含价格和成交量的场景
        """
        scenario = {
            "prices": {},
            "volumes": {},
            "spreads": {}
        }
        
        for symbol, base_price in base_prices.items():
            # 价格小幅下跌但成交量暴跌
            scenario["prices"][symbol] = [base_price * 0.95] * self.num_timesteps
            scenario["volumes"][symbol] = [1 - volume_drop] * self.num_timesteps
            scenario["spreads"][symbol] = [0.02] * self.num_timesteps  # 价差扩大
            
        return scenario
    
    def generate_comprehensive_stress_test(self,
                                          base_prices: Dict[str, float],
                                          correlations: np.ndarray) -> Dict[str, Any]:
        """
        生成综合压力测试场景
        
        结合多种极端情况
        """
        scenarios = {
            "market_crash": self.generate_crash_scenario(base_prices, 0.3),
            "volatility_spike": self.generate_volatility_spike(base_prices, 3.0),
            "liquidity_crisis": self.generate_liquidity_crisis(base_prices, 0.8),
            "correlation_breakdown": correlations * 0.5  # 相关性瓦解
        }
        
        return scenarios


class AShareRules:
    """A股规则适配器"""
    
    # 涨跌停限制
    LIMIT_CONFIGS = {
        'main_board': 0.10,
        'gem': 0.20,
        'star': 0.20,
        'st': 0.05,
    }
    
    @staticmethod
    def check_limit_up(prev_close: float, current_price: float, 
                      board_type: str = 'main_board') -> bool:
        """检查是否涨停"""
        limit = AShareRules.LIMIT_CONFIGS.get(board_type, 0.10)
        upper_limit = prev_close * (1 + limit)
        return current_price >= upper_limit * 0.999
    
    @staticmethod
    def check_limit_down(prev_close: float, current_price: float,
                        board_type: str = 'main_board') -> bool:
        """检查是否跌停"""
        limit = AShareRules.LIMIT_CONFIGS.get(board_type, 0.10)
        lower_limit = prev_close * (1 - limit)
        return current_price <= lower_limit * 1.001
    
    @staticmethod
    def apply_t_plus_one(position_date: datetime, 
                        sell_date: datetime) -> bool:
        """检查T+1规则"""
        return sell_date > position_date
