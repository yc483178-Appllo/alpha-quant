"""
策略进化引擎集成层
将V6.0策略进化引擎与V5.0 Alpha系统无缝集成

集成点:
1. 信号总线 - 进化策略信号接入现有信号系统
2. 策略层 - 与现有momentum_strategy等协同工作
3. 回测引擎 - 使用EvolutionBacktester快速回测（<100ms）
4. 看板 - 进化状态实时展示
5. 定时任务 - 每日自动进化
"""

import os
import sys
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from dataclasses import asdict

import pandas as pd
import numpy as np

# 导入进化引擎
from strategy_evolution_engine import (
    StrategyEvolutionEngine, 
    StrategyDNA, 
    StrategyPopulation,
    EvolutionBacktester,
    SmartStrategyEvolutionEngine
)

# 导入现有系统组件
try:
    from backtest_engine import BacktestEngine
    from signal_server import SignalServer
    from strategies.momentum_strategy import MomentumStrategy
except ImportError as e:
    logging.warning(f"现有系统组件导入警告: {e}")

logger = logging.getLogger("EvolutionIntegration")


class EvolutionSignalAdapter:
    """
    进化策略信号适配器
    将进化引擎生成的信号转换为现有系统格式
    """
    
    def __init__(self, evolution_engine: StrategyEvolutionEngine):
        self.evolution = evolution_engine
        self.signal_history: List[Dict] = []
        
    def generate_signals(self, market_data: pd.DataFrame) -> List[Dict]:
        """
        生成标准化信号列表
        
        Returns:
            信号列表，兼容现有信号格式
        """
        signals = []
        
        # 1. 最优策略信号
        best_signal = self.evolution.get_signal_from_best(market_data)
        if best_signal:
            signals.append(self._format_signal(best_signal, priority=1))
        
        # 2. 名人堂策略信号（投票机制）
        hof_signals = self.evolution.get_hall_of_fame_signals(market_data)
        vote_result = self._vote_signals(hof_signals)
        if vote_result:
            signals.append(self._format_signal(vote_result, priority=2))
        
        # 3. 活跃池Top5策略信号
        top_signals = self._get_top_active_signals(market_data, n=5)
        for i, sig in enumerate(top_signals):
            signals.append(self._format_signal(sig, priority=3+i))
        
        self.signal_history.extend(signals)
        return signals
    
    def _format_signal(self, raw_signal: Dict, priority: int) -> Dict:
        """转换为标准信号格式"""
        signal_map = {1: "BUY", -1: "SELL", 0: "HOLD"}
        
        return {
            "source": "evolution_engine",
            "strategy_id": raw_signal.get("strategy_id"),
            "strategy_type": raw_signal.get("strategy_type", "unknown"),
            "signal": signal_map.get(raw_signal.get("signal", 0), "HOLD"),
            "raw_signal": raw_signal.get("signal", 0),
            "confidence": min(raw_signal.get("fitness", 0) / 100, 1.0),
            "priority": priority,
            "params": raw_signal.get("params", {}),
            "timestamp": datetime.now().isoformat()
        }
    
    def _vote_signals(self, signals: List[Dict]) -> Optional[Dict]:
        """名人堂投票机制"""
        if not signals:
            return None
        
        # 按权重聚合信号
        total_weight = sum(s.get("fitness", 1) for s in signals)
        weighted_signal = sum(
            s.get("signal", 0) * s.get("fitness", 1) / total_weight 
            for s in signals
        )
        
        # 阈值判断
        if weighted_signal > 0.3:
            vote = 1
        elif weighted_signal < -0.3:
            vote = -1
        else:
            vote = 0
        
        return {
            "strategy_id": "hall_of_fame_vote",
            "strategy_type": "ensemble",
            "signal": vote,
            "fitness": sum(s.get("fitness", 0) for s in signals) / len(signals),
            "vote_detail": signals
        }
    
    def _get_top_active_signals(self, market_data: pd.DataFrame, n: int = 5) -> List[Dict]:
        """获取活跃池Top N策略信号"""
        top_strategies = sorted(
            self.evolution.population.active,
            key=lambda x: x.fitness_score,
            reverse=True
        )[:n]
        
        signals = []
        for dna in top_strategies:
            sig = self.evolution._generate_signals(dna.strategy_type, market_data, dna.params)
            latest = sig.iloc[-1] if len(sig) > 0 else 0
            signals.append({
                "strategy_id": dna.id,
                "strategy_type": dna.strategy_type,
                "signal": latest,
                "fitness": dna.fitness_score,
                "params": dna.params
            })
        return signals


class EvolutionBacktestBridge:
    """
    回测引擎桥接器
    使用EvolutionBacktester（快速回测，<100ms）
    """
    
    def __init__(self, price_data: Optional[Dict[str, pd.DataFrame]] = None):
        self.fast_backtester = None
        if price_data is not None:
            self.fast_backtester = EvolutionBacktester(price_data)
        
    def set_price_data(self, price_data: Dict[str, pd.DataFrame]):
        """设置价格数据（用于快速回测器）"""
        self.fast_backtester = EvolutionBacktester(price_data)
        
    def evaluate_dna(self, dna: StrategyDNA, data: Optional[pd.DataFrame] = None) -> Dict:
        """
        评估单个策略DNA的适应度
        使用快速回测器（<100ms）
        """
        if self.fast_backtester is not None:
            return self.fast_backtester.backtest(dna, period_days=252)
        else:
            # 回退到进化引擎内置回测
            return StrategyEvolutionEngine().backtest_strategy(dna, data or pd.DataFrame())


class EvolutionDashboardIntegration:
    """
    看板集成
    将进化状态实时推送到V3.0看板
    """
    
    def __init__(self, evolution_engine: StrategyEvolutionEngine):
        self.evolution = evolution_engine
        
    def get_dashboard_data(self) -> Dict:
        """获取看板展示数据"""
        pop = self.evolution.population
        
        return {
            "evolution_status": {
                "generation": pop.generation,
                "active_strategies": len(pop.active),
                "graveyard_size": len(pop.graveyard),
                "hall_of_fame_size": len(pop.hall_of_fame),
                "last_update": datetime.now().isoformat()
            },
            "hall_of_fame": [
                {
                    "id": dna.id,
                    "type": dna.strategy_type,
                    "fitness": round(dna.fitness_score, 2),
                    "generation": dna.generation
                }
                for dna in pop.hall_of_fame[:5]
            ],
            "active_pool_top10": [
                {
                    "id": dna.id,
                    "type": dna.strategy_type,
                    "fitness": round(dna.fitness_score, 2),
                    "age": pop.generation - dna.generation
                }
                for dna in sorted(pop.active, key=lambda x: x.fitness_score, reverse=True)[:10]
            ],
            "evolution_history": self._get_evolution_history(),
            "strategy_distribution": self._get_strategy_type_distribution()
        }
    
    def _get_evolution_history(self) -> List[Dict]:
        """获取进化历史（模拟数据，实际应从数据库读取）"""
        # 从performance_history聚合
        history = []
        for dna in self.evolution.population.active[:5]:
            if dna.performance_history:
                history.extend(dna.performance_history[-10:])
        return sorted(history, key=lambda x: x.get("date", ""))[-20:]
    
    def _get_strategy_type_distribution(self) -> Dict[str, int]:
        """策略类型分布"""
        distribution = {}
        for dna in self.evolution.population.active:
            distribution[dna.strategy_type] = distribution.get(dna.strategy_type, 0) + 1
        return distribution


class AlphaV6Integration:
    """
    V6.0 集成主类
    统一管理进化引擎与V5.0系统的集成
    """
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        
        # 初始化智能进化引擎（新版）
        self.engine = SmartStrategyEvolutionEngine(config_path)
        
        # 兼容性：保留旧接口
        self.evolution = self.engine
        
        self.enabled = self.config.get("strategy_evolution", {}).get("enabled", True)
        
    def _load_config(self, config_path: str) -> Dict:
        """加载配置"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"配置加载失败: {e}")
            return {}
    
    def initialize(self, price_data: Optional[Dict[str, pd.DataFrame]] = None):
        """初始化系统"""
        if not self.enabled:
            logger.info("策略进化引擎已禁用")
            return
        
        logger.info("=" * 60)
        logger.info("🚀 Alpha V6.0 策略进化引擎初始化")
        logger.info("=" * 60)
        
        # 初始化引擎
        if price_data is None:
            # 创建默认空数据
            price_data = {}
        self.engine.initialize(price_data)
        
        logger.info("✅ 进化引擎初始化完成")
    
    def daily_evolution(self) -> Dict:
        """
        每日进化周期
        应在收盘后执行
        """
        if not self.enabled:
            return {"status": "disabled"}
        
        logger.info("🧬 执行每日策略进化...")
        
        # 使用智能引擎执行进化
        result = self.engine.run_evolution_cycle()
        
        logger.info(f"✅ 第{result['generation']}代进化完成")
        return result
    
    def get_trading_signals(self) -> List[Dict]:
        """
        获取交易信号
        供交易执行层调用
        """
        if not self.enabled:
            return []
        
        # 获取进化信号
        signal = self.engine.get_evolution_signal()
        if signal.get("has_signal"):
            return [{
                "source": signal["source"],
                "strategy_id": signal["best_strategy_id"],
                "strategy_type": signal["strategy_type"],
                "params": signal["params"],
                "fitness": signal["fitness_score"],
                "confidence": signal["confidence"],
                "timestamp": signal["timestamp"]
            }]
        return []
    
    def get_dashboard_data(self) -> Dict:
        """获取看板数据"""
        return self.engine.get_dashboard_data()
    
    def export_best_strategy(self) -> Optional[Dict]:
        """导出最优策略"""
        best = self.engine.population.get_best()
        if best is None:
            return None
        return {
            "id": best.id,
            "type": best.strategy_type,
            "params": best.params,
            "fitness": best.fitness_score,
            "generation": best.generation
        }
    
    def revive_strategy(self, strategy_id: str) -> bool:
        """复活墓地中的策略"""
        dna = self.engine.population.revive(strategy_id)
        return dna is not None


# 便捷函数
def create_evolution_integration(config_path: str = "config.json",
                                  price_data: Optional[Dict[str, pd.DataFrame]] = None) -> AlphaV6Integration:
    """创建集成实例"""
    integration = AlphaV6Integration(config_path)
    integration.initialize(price_data)
    return integration


def run_daily_evolution(price_data: Optional[Dict[str, pd.DataFrame]] = None, 
                        config_path: str = "config.json") -> Dict:
    """运行每日进化（独立函数）"""
    integration = create_evolution_integration(config_path, price_data)
    return integration.daily_evolution()


if __name__ == "__main__":
    # 测试运行
    logging.basicConfig(level=logging.INFO)
    
    # 创建模拟价格数据
    mock_price_data = {}
    for i in range(20):
        code = f"0000{i+1:02d}"
        dates = pd.date_range(start="2024-01-01", periods=300, freq="D")
        mock_price_data[code] = pd.DataFrame({
            "date": dates,
            "open": 100 + np.cumsum(np.random.randn(300) * 0.01),
            "high": 100 + np.cumsum(np.random.randn(300) * 0.01) + 0.02,
            "low": 100 + np.cumsum(np.random.randn(300) * 0.01) - 0.02,
            "close": 100 + np.cumsum(np.random.randn(300) * 0.01),
            "volume": np.random.randint(1000000, 10000000, 300)
        })
    
    # 运行进化
    result = run_daily_evolution(mock_price_data)
    print("\n进化结果:", json.dumps(result, indent=2, ensure_ascii=False))
