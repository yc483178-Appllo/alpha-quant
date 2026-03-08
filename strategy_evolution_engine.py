#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alpha V6.0 - 策略进化引擎 (Strategy Evolution Engine)
基于遗传算法的策略参数优化和策略组合进化
"""

import json
import logging
import random
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Any, Optional
from dataclasses import dataclass, asdict
import pickle
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class StrategyGenome:
    """策略基因组 - 代表一个策略的参数配置"""
    strategy_id: str
    params: Dict[str, float]
    fitness: float = 0.0
    generation: int = 0
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


class StrategyEvolutionEngine:
    """
    策略进化引擎 - 使用遗传算法优化交易策略
    
    功能：
    1. 策略参数自动优化
    2. 多策略组合进化
    3. 适应度评估
    4. 精英策略保存
    """
    
    def __init__(self, config_path: str = "/opt/alpha-system/config/config.json"):
        self.config = self._load_config(config_path)
        self.population_size = self.config.get("population_size", 50)
        self.mutation_rate = self.config.get("mutation_rate", 0.1)
        self.crossover_rate = self.config.get("crossover_rate", 0.8)
        self.elite_ratio = self.config.get("elite_ratio", 0.1)
        self.generation = 0
        self.population: List[StrategyGenome] = []
        self.elite_strategies: List[StrategyGenome] = []
        self.fitness_history: List[float] = []
        
        # 参数范围定义
        self.param_ranges = {
            "lookback_period": (5, 50),
            "entry_threshold": (0.001, 0.05),
            "exit_threshold": (0.001, 0.05),
            "stop_loss": (0.01, 0.1),
            "take_profit": (0.02, 0.2),
            "position_size": (0.01, 0.2),
            "momentum_period": (5, 30),
            "volatility_window": (10, 60),
            "rsi_period": (7, 21),
            "macd_fast": (8, 16),
            "macd_slow": (20, 35),
            "macd_signal": (5, 12)
        }
        
        self._init_population()
        logger.info(f"策略进化引擎初始化完成，种群大小: {self.population_size}")
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get("strategy_evolution", {})
        except Exception as e:
            logger.warning(f"无法加载配置文件: {e}，使用默认配置")
            return {}
    
    def _init_population(self):
        """初始化种群"""
        self.population = []
        for i in range(self.population_size):
            genome = self._create_random_genome(f"strategy_{i}")
            self.population.append(genome)
        logger.info(f"初始化种群完成，共 {len(self.population)} 个策略")
    
    def _create_random_genome(self, strategy_id: str) -> StrategyGenome:
        """创建随机基因组"""
        params = {}
        for param_name, (min_val, max_val) in self.param_ranges.items():
            params[param_name] = random.uniform(min_val, max_val)
        return StrategyGenome(
            strategy_id=strategy_id,
            params=params,
            generation=self.generation
        )
    
    def evaluate_fitness(self, strategy_id: str = None) -> Dict[str, float]:
        """
        评估策略适应度
        
        模拟回测评估，返回：
        - sharpe_ratio: 夏普比率
        - total_return: 总收益率
        - max_drawdown: 最大回撤
        - win_rate: 胜率
        - fitness: 综合适应度得分
        """
        results = {}
        
        genomes_to_eval = [g for g in self.population if g.strategy_id == strategy_id] if strategy_id else self.population
        
        for genome in genomes_to_eval:
            # 模拟回测结果（实际应连接到真实回测系统）
            sharpe = random.uniform(0.5, 2.5)
            total_return = random.uniform(-0.1, 0.5)
            max_dd = random.uniform(0.05, 0.25)
            win_rate = random.uniform(0.4, 0.7)
            
            # 综合适应度计算
            fitness = (
                sharpe * 0.4 +
                total_return * 0.3 -
                max_dd * 0.2 +
                win_rate * 0.1
            )
            
            genome.fitness = max(0, fitness)
            results[genome.strategy_id] = {
                "sharpe_ratio": round(sharpe, 3),
                "total_return": round(total_return, 4),
                "max_drawdown": round(max_dd, 4),
                "win_rate": round(win_rate, 3),
                "fitness": round(genome.fitness, 4)
            }
        
        return results
    
    def select_parents(self) -> Tuple[StrategyGenome, StrategyGenome]:
        """锦标赛选择父母"""
        tournament_size = 3
        
        def tournament():
            contestants = random.sample(self.population, min(tournament_size, len(self.population)))
            return max(contestants, key=lambda x: x.fitness)
        
        return tournament(), tournament()
    
    def crossover(self, parent1: StrategyGenome, parent2: StrategyGenome) -> Tuple[StrategyGenome, StrategyGenome]:
        """参数交叉"""
        if random.random() > self.crossover_rate:
            return parent1, parent2
        
        child1_params = {}
        child2_params = {}
        
        for param_name in self.param_ranges.keys():
            if random.random() < 0.5:
                child1_params[param_name] = parent1.params[param_name]
                child2_params[param_name] = parent2.params[param_name]
            else:
                child1_params[param_name] = parent2.params[param_name]
                child2_params[param_name] = parent1.params[param_name]
        
        child1 = StrategyGenome(
            strategy_id=f"{parent1.strategy_id}_child1",
            params=child1_params,
            generation=self.generation + 1
        )
        child2 = StrategyGenome(
            strategy_id=f"{parent2.strategy_id}_child2",
            params=child2_params,
            generation=self.generation + 1
        )
        
        return child1, child2
    
    def mutate(self, genome: StrategyGenome) -> StrategyGenome:
        """基因突变"""
        mutated_params = genome.params.copy()
        
        for param_name, (min_val, max_val) in self.param_ranges.items():
            if random.random() < self.mutation_rate:
                # 高斯突变
                current_val = mutated_params[param_name]
                mutation = random.gauss(0, (max_val - min_val) * 0.1)
                new_val = current_val + mutation
                mutated_params[param_name] = max(min_val, min(max_val, new_val))
        
        return StrategyGenome(
            strategy_id=f"{genome.strategy_id}_mut",
            params=mutated_params,
            generation=genome.generation
        )
    
    def evolve_generation(self) -> Dict[str, Any]:
        """进化一代"""
        # 评估当前种群适应度
        self.evaluate_fitness()
        
        # 按适应度排序
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        
        # 保存精英
        elite_count = int(self.population_size * self.elite_ratio)
        new_population = self.population[:elite_count]
        self.elite_strategies = new_population.copy()
        
        # 生成新一代
        while len(new_population) < self.population_size:
            parent1, parent2 = self.select_parents()
            child1, child2 = self.crossover(parent1, parent2)
            child1 = self.mutate(child1)
            child2 = self.mutate(child2)
            new_population.extend([child1, child2])
        
        # 裁剪到种群大小
        self.population = new_population[:self.population_size]
        self.generation += 1
        
        # 记录历史
        avg_fitness = sum(g.fitness for g in self.population) / len(self.population)
        best_fitness = self.population[0].fitness if self.population else 0
        self.fitness_history.append(avg_fitness)
        
        logger.info(f"第 {self.generation} 代进化完成，最佳适应度: {best_fitness:.4f}, 平均: {avg_fitness:.4f}")
        
        return {
            "generation": self.generation,
            "best_fitness": round(best_fitness, 4),
            "avg_fitness": round(avg_fitness, 4),
            "elite_count": len(self.elite_strategies),
            "population_size": len(self.population)
        }
    
    def get_best_strategy(self) -> Optional[Dict]:
        """获取最佳策略"""
        if not self.population:
            return None
        
        best = max(self.population, key=lambda x: x.fitness)
        return {
            "strategy_id": best.strategy_id,
            "generation": best.generation,
            "fitness": round(best.fitness, 4),
            "params": {k: round(v, 4) for k, v in best.params.items()},
            "created_at": best.created_at
        }
    
    def get_population_stats(self) -> Dict[str, Any]:
        """获取种群统计信息"""
        if not self.population:
            return {"error": "种群为空"}
        
        fitnesses = [g.fitness for g in self.population]
        return {
            "generation": self.generation,
            "population_size": len(self.population),
            "best_fitness": round(max(fitnesses), 4),
            "worst_fitness": round(min(fitnesses), 4),
            "avg_fitness": round(sum(fitnesses) / len(fitnesses), 4),
            "std_fitness": round(np.std(fitnesses), 4) if len(fitnesses) > 1 else 0,
            "elite_strategies": len(self.elite_strategies),
            "fitness_history": [round(f, 4) for f in self.fitness_history[-20:]]
        }
    
    def export_strategy(self, strategy_id: str) -> Dict:
        """导出策略配置"""
        for genome in self.population:
            if genome.strategy_id == strategy_id:
                return {
                    "strategy_id": genome.strategy_id,
                    "params": genome.params,
                    "fitness": genome.fitness,
                    "generation": genome.generation,
                    "exported_at": datetime.now().isoformat()
                }
        return {"error": "策略未找到"}
    
    def save_state(self, filepath: str = "/opt/alpha-system/models/evolution/state.pkl"):
        """保存进化状态"""
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        state = {
            "generation": self.generation,
            "population": self.population,
            "elite_strategies": self.elite_strategies,
            "fitness_history": self.fitness_history,
            "config": self.config
        }
        with open(filepath, 'wb') as f:
            pickle.dump(state, f)
        logger.info(f"进化状态已保存到 {filepath}")
    
    def load_state(self, filepath: str = "/opt/alpha-system/models/evolution/state.pkl"):
        """加载进化状态"""
        if not os.path.exists(filepath):
            logger.warning(f"状态文件不存在: {filepath}")
            return False
        
        with open(filepath, 'rb') as f:
            state = pickle.load(f)
        
        self.generation = state["generation"]
        self.population = state["population"]
        self.elite_strategies = state["elite_strategies"]
        self.fitness_history = state["fitness_history"]
        
        logger.info(f"进化状态已加载，当前第 {self.generation} 代")
        return True


# 单例实例
_evolution_engine = None

def get_evolution_engine() -> StrategyEvolutionEngine:
    """获取进化引擎单例"""
    global _evolution_engine
    if _evolution_engine is None:
        _evolution_engine = StrategyEvolutionEngine()
    return _evolution_engine


if __name__ == "__main__":
    # 测试
    engine = StrategyEvolutionEngine()
    
    # 进化5代
    for i in range(5):
        result = engine.evolve_generation()
        print(f"第 {result['generation']} 代: 最佳={result['best_fitness']}, 平均={result['avg_fitness']}")
    
    # 输出最佳策略
    best = engine.get_best_strategy()
    print("\n最佳策略:")
    print(json.dumps(best, indent=2, ensure_ascii=False))
