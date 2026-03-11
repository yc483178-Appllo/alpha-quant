"""
扩散模型场景生成器 - 用于极端市场情景的压力测试
"""

import numpy as np
from typing import Dict, List
from datetime import datetime


class DiffusionScenarioGenerator:
    """扩散模型场景生成器"""
    
    def __init__(self, num_timesteps: int = 100):
        self.num_timesteps = num_timesteps
        
    def generate_crash_scenario(self, base_prices, crash_magnitude=0.3):
        """生成崩盘情景"""
        scenario = {}
        for symbol, base_price in base_prices.items():
            path = [base_price]
            current = base_price
            for t in range(self.num_timesteps):
                drift = -crash_magnitude / self.num_timesteps
                shock = np.random.normal(0, 0.02)
                current = current * (1 + drift + shock)
                path.append(max(current, base_price * 0.1))
            scenario[symbol] = path
        return scenario
    
    def generate_volatility_spike(self, base_prices, spike_factor=3.0):
        """生成波动率飙升情景"""
        scenario = {}
        for symbol, base_price in base_prices.items():
            path = [base_price]
            current = base_price
            for t in range(self.num_timesteps):
                shock = np.random.normal(0, 0.05 * spike_factor)
                current = current * (1 + shock)
                path.append(max(current, base_price * 0.5))
            scenario[symbol] = path
        return scenario
