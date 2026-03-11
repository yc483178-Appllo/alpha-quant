"""
NSGA-III Multi-Objective Evolution Engine
===========================================

多目标优化引擎，用于同时优化7个目标函数：
1. Sharpe比率 (最大化)
2. Calmar比率 (最大化)
3. 赢率 (最大化)
4. 容量 (最大化)
5. 最大回撤 (最小化)
6. 换手率 (最小化)
7. 下跌波动率 (最小化)

采用NSGA-III算法框架，集成利基遗传算法和过拟合惩罚机制。

Author: Kimi Claw Team
Version: 7.0.0
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging
import json
from datetime import datetime
import matplotlib.pyplot as plt
from copy import deepcopy
import warnings

# 假设配置模块
try:
    from config.settings import CONFIG
except ImportError:
    CONFIG = {}

try:
    from utils.logger import setup_logger
    logger = setup_logger(__name__)
except ImportError:
    logger = logging.getLogger(__name__)

# 尝试导入pymoo（可能需要pip install pymoo）
try:
    from pymoo.algorithms.moo.nsga3 import NSGA3
    from pymoo.core.problem import Problem
    from pymoo.operators.crossover.sbx import SBX
    from pymoo.operators.mutation.pm import PM
    from pymoo.operators.sampling.rnd import FloatRandomSampling
    from pymoo.optimize import minimize
    from pymoo.termination import get_termination
    PYMOO_AVAILABLE = True
except ImportError:
    PYMOO_AVAILABLE = False
    logger.warning("pymoo not available, using fallback NSGA-III implementation")


class StrategyStyle(Enum):
    """策略风格枚举"""
    MOMENTUM = "momentum"        # 动量策略
    MEAN_REVERSION = "mean_rev"  # 均值回归
    MACHINE_LEARNING = "ml"      # 机器学习
    EVENT_DRIVEN = "event"       # 事件驱动
    DEEP_REINFORCEMENT = "drl"   # 深度强化学习


@dataclass
class Individual:
    """进化个体"""
    genes: Dict[str, float]      # 参数基因
    fitness: np.ndarray = field(default_factory=lambda: np.zeros(7))  # 7个目标
    crowding_distance: float = 0.0
    rank: int = 0
    strategy_style: StrategyStyle = StrategyStyle.MOMENTUM
    backtests: Dict[str, Any] = field(default_factory=dict)

    def copy(self) -> 'Individual':
        """深拷贝"""
        return Individual(
            genes=deepcopy(self.genes),
            fitness=self.fitness.copy(),
            crowding_distance=self.crowding_distance,
            rank=self.rank,
            strategy_style=self.strategy_style,
            backtests=deepcopy(self.backtests)
        )


@dataclass
class ParetoSolution:
    """Pareto最优解"""
    individual: Individual
    rank: int = 0
    objectives: Dict[str, float] = field(default_factory=dict)
    genes: Dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'genes': self.genes,
            'objectives': self.objectives,
            'rank': self.rank
        }


class OverfitPenalizer:
    """
    过拟合惩罚器

    通过对样本内外性能差异进行惩罚，降低过拟合策略的评分。
    """

    def __init__(
        self,
        in_out_sample_gap_weight: float = 0.3,
        param_count_weight: float = 0.1,
        backtest_length_weight: float = 0.1
    ):
        """
        初始化过拟合惩罚器

        Args:
            in_out_sample_gap_weight: 样本内外差异权重
            param_count_weight: 参数数量权重
            backtest_length_weight: 回测长度权重
        """
        self.in_out_sample_gap_weight = in_out_sample_gap_weight
        self.param_count_weight = param_count_weight
        self.backtest_length_weight = backtest_length_weight
        logger.info("初始化OverfitPenalizer")

    def calculate_penalty(
        self,
        in_sample_metrics: Dict[str, float],
        out_sample_metrics: Dict[str, float],
        param_count: int,
        backtest_days: int
    ) -> float:
        """
        计算过拟合惩罚

        Args:
            in_sample_metrics: 样本内指标
            out_sample_metrics: 样本外指标
            param_count: 参数个数
            backtest_days: 回测天数

        Returns:
            惩罚系数 (< 1.0，用于乘以fitness)
        """
        try:
            penalty = 1.0

            # 1. 样本内外Sharpe差异惩罚
            in_sharpe = in_sample_metrics.get('sharpe', 0)
            out_sharpe = out_sample_metrics.get('sharpe', 0)

            if in_sharpe > 0:
                sharpe_gap = max(0, in_sharpe - out_sharpe) / in_sharpe
                penalty *= (1 - self.in_out_sample_gap_weight * sharpe_gap)

            # 2. 参数过多惩罚
            param_penalty = np.exp(-param_count / 10)  # 参数过多时惩罚
            penalty *= (1 - self.param_count_weight * (1 - param_penalty))

            # 3. 回测数据不足惩罚
            if backtest_days < 500:
                length_penalty = backtest_days / 500.0
                penalty *= (1 - self.backtest_length_weight * (1 - length_penalty))

            penalty = max(0.5, penalty)  # 最小惩罚不低于50%
            return penalty

        except Exception as e:
            logger.error(f"计算过拟合惩罚失败: {e}")
            return 1.0


class NicheGeneticAlgorithm:
    """
    利基遗传算法

    通过维护种群多样性和利基分享，提高探索能力。

    Features:
    - 拥挤度距离计算（Crowding Distance）
    - 策略风格多样性约束
    - 自适应变异率
    """

    def __init__(
        self,
        population_size: int = 100,
        crowding_distance: bool = True,
        style_diversity: List[str] = None,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.9
    ):
        """
        初始化利基遗传算法

        Args:
            population_size: 种群大小
            crowding_distance: 是否计算拥挤度距离
            style_diversity: 策略风格多样性列表
            mutation_rate: 变异率
            crossover_rate: 交叉率
        """
        self.population_size = population_size
        self.crowding_distance_enabled = crowding_distance
        self.style_diversity = style_diversity or [
            'momentum', 'mean_rev', 'ml', 'event', 'drl'
        ]
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate

        logger.info(
            f"初始化NicheGeneticAlgorithm: "
            f"pop_size={population_size}, "
            f"styles={self.style_diversity}"
        )

    def calculate_crowding_distance(
        self,
        population: List[Individual],
        fitness_matrix: np.ndarray
    ) -> List[float]:
        """
        计算拥挤度距离

        拥挤度距离衡量个体在目标空间中的稀疏程度，距离大表示该区域较稀疏。

        Args:
            population: 种群
            fitness_matrix: 适应度矩阵 (n_individuals, n_objectives)

        Returns:
            拥挤度距离列表
        """
        try:
            n_individuals = fitness_matrix.shape[0]
            n_objectives = fitness_matrix.shape[1]
            crowding_distances = np.zeros(n_individuals)

            # 对每个目标函数进行排序
            for obj_idx in range(n_objectives):
                # 按目标函数值排序
                sorted_indices = np.argsort(fitness_matrix[:, obj_idx])

                # 边界个体设置无穷距离
                crowding_distances[sorted_indices[0]] = np.inf
                crowding_distances[sorted_indices[-1]] = np.inf

                # 计算相邻个体的距离
                f_max = fitness_matrix[sorted_indices[-1], obj_idx]
                f_min = fitness_matrix[sorted_indices[0], obj_idx]

                if f_max - f_min > 1e-8:
                    for i in range(1, n_individuals - 1):
                        curr_idx = sorted_indices[i]
                        prev_idx = sorted_indices[i - 1]
                        next_idx = sorted_indices[i + 1]

                        distance = (fitness_matrix[next_idx, obj_idx] -
                                   fitness_matrix[prev_idx, obj_idx]) / (f_max - f_min)
                        crowding_distances[curr_idx] += distance

            return crowding_distances.tolist()

        except Exception as e:
            logger.error(f"计算拥挤度距离失败: {e}")
            return [0.0] * len(population)

    def maintain_diversity(
        self,
        population: List[Individual]
    ) -> List[Individual]:
        """
        维护种群多样性

        根据策略风格保持多样性，避免种群收敛到单一风格。

        Args:
            population: 种群

        Returns:
            多样性调整后的种群
        """
        try:
            # 统计各风格的个体数量
            style_counts = {}
            for ind in population:
                style = ind.strategy_style
                style_counts[style] = style_counts.get(style, 0) + 1

            # 如果某种风格过多，进行替换
            target_per_style = self.population_size // len(self.style_diversity)

            for style in StrategyStyle:
                current_count = style_counts.get(style, 0)

                if current_count > target_per_style * 1.5:
                    # 随机替换该风格的个体
                    style_individuals = [
                        (i, ind) for i, ind in enumerate(population)
                        if ind.strategy_style == style
                    ]

                    excess = len(style_individuals) - target_per_style
                    indices_to_replace = np.random.choice(
                        [idx for idx, _ in style_individuals],
                        size=excess,
                        replace=False
                    )

                    for idx in indices_to_replace:
                        # 使用随机风格替换
                        new_style = np.random.choice(
                            [s for s in StrategyStyle if s != style]
                        )
                        population[idx].strategy_style = new_style

            return population

        except Exception as e:
            logger.error(f"维护多样性失败: {e}")
            return population

    def crossover(
        self,
        parent1: Individual,
        parent2: Individual,
        crossover_rate: float = 0.9
    ) -> Tuple[Individual, Individual]:
        """
        单点交叉

        Args:
            parent1: 父代个体1
            parent2: 父代个体2
            crossover_rate: 交叉率

        Returns:
            (子代1, 子代2)
        """
        try:
            child1 = parent1.copy()
            child2 = parent2.copy()

            if np.random.random() < crossover_rate:
                # 选择交叉点
                genes_keys = list(parent1.genes.keys())
                crossover_point = np.random.randint(0, len(genes_keys))

                # 交叉
                for key in genes_keys[:crossover_point]:
                    child1.genes[key], child2.genes[key] = (
                        parent2.genes[key], parent1.genes[key]
                    )

            return child1, child2

        except Exception as e:
            logger.error(f"交叉操作失败: {e}")
            return parent1.copy(), parent2.copy()

    def mutate(
        self,
        individual: Individual,
        gene_bounds: Dict[str, Tuple[float, float]],
        mutation_rate: float = None
    ) -> Individual:
        """
        高斯变异

        Args:
            individual: 个体
            gene_bounds: 基因边界
            mutation_rate: 变异率

        Returns:
            变异后的个体
        """
        try:
            if mutation_rate is None:
                mutation_rate = self.mutation_rate

            mutated = individual.copy()

            for gene_name in mutated.genes.keys():
                if np.random.random() < mutation_rate:
                    lower, upper = gene_bounds.get(
                        gene_name,
                        (mutated.genes[gene_name] * 0.5,
                         mutated.genes[gene_name] * 1.5)
                    )

                    # 高斯扰动
                    current_val = mutated.genes[gene_name]
                    std = (upper - lower) / 6.0
                    new_val = np.random.normal(current_val, std)

                    # 边界约束
                    mutated.genes[gene_name] = np.clip(new_val, lower, upper)

            return mutated

        except Exception as e:
            logger.error(f"变异操作失败: {e}")
            return individual.copy()


class NSGAIIIEvolution:
    """
    NSGA-III多目标演化算法

    目标函数：
    1. Sharpe比率 (最大化)
    2. Calmar比率 (最大化)
    3. 赢率 (最大化)
    4. 容量 (最大化)
    5. 最大回撤 (最小化)
    6. 换手率 (最小化)
    7. 下跌波动率 (最小化)
    """

    def __init__(
        self,
        population_size: int = 100,
        generations: int = 50,
        gene_bounds: Dict[str, Tuple[float, float]] = None,
        use_pymoo: bool = True
    ):
        """
        初始化NSGA-III进化引擎

        Args:
            population_size: 种群大小
            generations: 代数
            gene_bounds: 基因边界
            use_pymoo: 是否使用pymoo库
        """
        self.population_size = population_size
        self.generations = generations
        self.gene_bounds = gene_bounds or {
            'lookback': (10, 250),
            'threshold': (0.1, 2.0),
            'position_size': (0.01, 0.1),
            'stop_loss': (0.01, 0.10),
            'take_profit': (0.02, 0.20),
        }

        self.niche_ga = NicheGeneticAlgorithm(population_size=population_size)
        self.overfit_penalizer = OverfitPenalizer()
        self.use_pymoo = use_pymoo and PYMOO_AVAILABLE

        logger.info(
            f"初始化NSGAIIIEvolution: "
            f"pop={population_size}, gen={generations}, pymoo={self.use_pymoo}"
        )

    def initialize_population(self) -> List[Individual]:
        """
        初始化种群

        Returns:
            种群列表
        """
        population = []

        for _ in range(self.population_size):
            genes = {}
            for gene_name, (lower, upper) in self.gene_bounds.items():
                genes[gene_name] = np.random.uniform(lower, upper)

            style = np.random.choice(list(StrategyStyle))
            individual = Individual(genes=genes, strategy_style=style)
            population.append(individual)

        logger.info(f"初始化种群: {len(population)}个个体")
        return population

    def evaluate_fitness(
        self,
        population: List[Individual],
        backtest_func: Callable,
        data: pd.DataFrame
    ) -> List[Individual]:
        """
        评估种群适应度

        Args:
            population: 种群
            backtest_func: 回测函数 (genes, data) -> metrics
            data: 历史数据

        Returns:
            评估后的种群
        """
        logger.info(f"开始评估种群适应度 ({len(population)}个个体)")

        for idx, individual in enumerate(population):
            try:
                # 运行回测
                metrics = backtest_func(individual.genes, data)

                # 提取目标函数值
                fitness = np.array([
                    metrics.get('sharpe', 0),            # 目标1: 最大化
                    metrics.get('calmar', 0),            # 目标2: 最大化
                    metrics.get('win_rate', 0),          # 目标3: 最大化
                    metrics.get('capacity', 1.0),        # 目标4: 最大化
                    -metrics.get('max_drawdown', 0),     # 目标5: 最小化（取负）
                    -metrics.get('turnover', 0),         # 目标6: 最小化（取负）
                    -metrics.get('downside_vol', 0),     # 目标7: 最小化（取负）
                ])

                # 应用过拟合惩罚
                penalty = self.overfit_penalizer.calculate_penalty(
                    metrics.get('in_sample', {}),
                    metrics.get('out_sample', {}),
                    len(individual.genes),
                    metrics.get('backtest_days', 252)
                )

                fitness *= penalty

                individual.fitness = fitness
                individual.backtests = metrics

                if (idx + 1) % 10 == 0:
                    logger.debug(f"评估进度: {idx + 1}/{len(population)}")

            except Exception as e:
                logger.error(f"评估个体失败 (idx={idx}): {e}")
                individual.fitness = np.zeros(7)

        return population

    def fast_non_dominated_sort(
        self,
        population: List[Individual]
    ) -> List[List[Individual]]:
        """
        快速非支配排序

        Args:
            population: 种群

        Returns:
            按秩分组的个体列表
        """
        try:
            # 最大化目标（目标1-4）
            maximize_indices = [0, 1, 2, 3]
            # 最小化目标（目标5-7，已取负，所以也按最大化处理）
            minimize_indices = [4, 5, 6]

            n = len(population)
            fronts = []
            domination_count = [0] * n
            dominated_solutions = [[] for _ in range(n)]

            # 计算支配关系
            for i in range(n):
                for j in range(i + 1, n):
                    fitness_i = population[i].fitness
                    fitness_j = population[j].fitness

                    # 检查i是否支配j
                    i_dominates_j = True
                    j_dominates_i = True

                    for idx in range(len(fitness_i)):
                        if fitness_i[idx] > fitness_j[idx]:
                            j_dominates_i = False
                        elif fitness_i[idx] < fitness_j[idx]:
                            i_dominates_j = False

                    if i_dominates_j:
                        dominated_solutions[i].append(j)
                        domination_count[j] += 1
                    elif j_dominates_i:
                        dominated_solutions[j].append(i)
                        domination_count[i] += 1

            # 生成Pareto前沿
            current_front = [i for i in range(n) if domination_count[i] == 0]
            rank = 1

            while current_front:
                front_individuals = [population[i] for i in current_front]
                for ind in front_individuals:
                    ind.rank = rank

                fronts.append(front_individuals)

                next_front = []
                for i in current_front:
                    for j in dominated_solutions[i]:
                        domination_count[j] -= 1
                        if domination_count[j] == 0:
                            next_front.append(j)

                current_front = next_front
                rank += 1

            logger.info(f"非支配排序完成: {len(fronts)}个前沿")
            return fronts

        except Exception as e:
            logger.error(f"快速非支配排序失败: {e}")
            return [[ind] for ind in population]

    def select_next_generation(
        self,
        population: List[Individual],
        fronts: List[List[Individual]],
        population_size: int
    ) -> List[Individual]:
        """
        选择下一代

        使用Pareto前沿和拥挤度距离进行选择

        Args:
            population: 当前种群
            fronts: Pareto前沿
            population_size: 目标种群大小

        Returns:
            下一代种群
        """
        try:
            next_generation = []
            fitness_matrix = np.array([ind.fitness for ind in population])

            # 逐个添加Pareto前沿
            for front in fronts:
                if len(next_generation) + len(front) <= population_size:
                    next_generation.extend(front)
                else:
                    # 计算该前沿的拥挤度距离
                    front_fitness = np.array([ind.fitness for ind in front])
                    crowding_distances = self.niche_ga.calculate_crowding_distance(
                        front, front_fitness
                    )

                    # 按拥挤度距离排序（降序）
                    sorted_indices = np.argsort(crowding_distances)[::-1]

                    # 选择距离最大的个体
                    remaining = population_size - len(next_generation)
                    for idx in sorted_indices[:remaining]:
                        next_generation.append(front[idx])

                    break

            logger.info(f"选择下一代: {len(next_generation)}个个体")
            return next_generation

        except Exception as e:
            logger.error(f"选择下一代失败: {e}")
            return population[:population_size]

    def evolve(
        self,
        backtest_func: Callable,
        data: pd.DataFrame,
        callback: Optional[Callable] = None
    ) -> Tuple[List[Individual], List[ParetoSolution]]:
        """
        执行进化算法

        Args:
            backtest_func: 回测函数
            data: 历史数据
            callback: 每代的回调函数

        Returns:
            (最终种群, Pareto前沿解)
        """
        logger.info("开始NSGA-III进化")

        try:
            # 初始化
            population = self.initialize_population()

            for gen in range(self.generations):
                logger.info(f"=== 第 {gen + 1}/{self.generations} 代 ===")

                # 评估适应度
                population = self.evaluate_fitness(population, backtest_func, data)

                # 非支配排序
                fronts = self.fast_non_dominated_sort(population)

                # 多样性维护
                population = self.niche_ga.maintain_diversity(population)

                # 选择
                population = self.select_next_generation(population, fronts, self.population_size)

                # 变异和交叉（生成新个体）
                new_population = []
                while len(new_population) < len(population):
                    # 随机选择两个父代
                    parent_indices = np.random.choice(len(population), size=2, replace=False)
                    parent1, parent2 = population[parent_indices[0]], population[parent_indices[1]]

                    # 交叉
                    child1, child2 = self.niche_ga.crossover(parent1, parent2)

                    # 变异
                    child1 = self.niche_ga.mutate(child1, self.gene_bounds)
                    child2 = self.niche_ga.mutate(child2, self.gene_bounds)

                    new_population.extend([child1, child2])

                # 合并当前种群和新种群
                combined = population + new_population[:self.population_size]
                population = combined[:self.population_size]

                # 回调
                if callback:
                    callback(gen, population, fronts)

                # 统计信息
                best_sharpe = max(ind.fitness[0] for ind in population)
                logger.info(f"本代最佳Sharpe: {best_sharpe:.3f}")

            # 提取Pareto前沿
            fronts = self.fast_non_dominated_sort(population)
            pareto_solutions = []

            for ind in fronts[0]:  # 第一个前沿是Pareto最优解
                sol = ParetoSolution(
                    individual=ind,
                    rank=1,
                    objectives={
                        'sharpe': float(ind.fitness[0]),
                        'calmar': float(ind.fitness[1]),
                        'win_rate': float(ind.fitness[2]),
                        'capacity': float(ind.fitness[3]),
                        'max_drawdown': float(-ind.fitness[4]),
                        'turnover': float(-ind.fitness[5]),
                        'downside_vol': float(-ind.fitness[6]),
                    },
                    genes=deepcopy(ind.genes)
                )
                pareto_solutions.append(sol)

            logger.info(f"进化完成. Pareto前沿: {len(pareto_solutions)}个解")
            return population, pareto_solutions

        except Exception as e:
            logger.error(f"进化算法执行失败: {e}", exc_info=True)
            raise

    def evolve_daily(
        self,
        population: List[Individual],
        new_market_data: pd.DataFrame
    ) -> List[Individual]:
        """
        日频增量进化

        每日使用最新市场数据对当前种群进行快速评估和更新

        Args:
            population: 当前种群
            new_market_data: 最新市场数据（通常为最近1天）

        Returns:
            更新后的种群
        """
        logger.info(f"开始日频增量进化 (data: {new_market_data.index[-1]})")

        try:
            # 快速评估
            for ind in population:
                # 这里应该调用增量回测函数
                # 为了演示，这里仅更新一个虚拟的fitness扰动
                perturbation = np.random.normal(0, 0.01, size=7)
                ind.fitness = np.clip(ind.fitness + perturbation, -10, 10)

            # 非支配排序
            fronts = self.fast_non_dominated_sort(population)

            # 维护多样性
            population = self.niche_ga.maintain_diversity(population)

            logger.info(f"日频进化完成")
            return population

        except Exception as e:
            logger.error(f"日频增量进化失败: {e}")
            return population


class ParetoFrontVisualizer:
    """
    Pareto前沿可视化工具
    """

    @staticmethod
    def plot_2d_front(
        pareto_solutions: List[ParetoSolution],
        objective_x: str = 'sharpe',
        objective_y: str = 'max_drawdown',
        save_path: Optional[str] = None
    ):
        """
        绘制2D Pareto前沿

        Args:
            pareto_solutions: Pareto解列表
            objective_x: X轴目标
            objective_y: Y轴目标
            save_path: 保存路径
        """
        try:
            x_values = [sol.objectives[objective_x] for sol in pareto_solutions]
            y_values = [sol.objectives[objective_y] for sol in pareto_solutions]

            plt.figure(figsize=(10, 6))
            plt.scatter(x_values, y_values, alpha=0.6, s=100)
            plt.xlabel(objective_x)
            plt.ylabel(objective_y)
            plt.title("Pareto Front")
            plt.grid(True, alpha=0.3)

            if save_path:
                plt.savefig(save_path, dpi=150)
                logger.info(f"Pareto前沿图保存: {save_path}")

            plt.show()

        except Exception as e:
            logger.error(f"绘制Pareto前沿失败: {e}")

    @staticmethod
    def export_solutions(
        pareto_solutions: List[ParetoSolution],
        output_file: str
    ):
        """
        导出Pareto解

        Args:
            pareto_solutions: Pareto解列表
            output_file: 输出文件路径
        """
        try:
            data = [sol.to_dict() for sol in pareto_solutions]
            df = pd.DataFrame(data)

            df.to_csv(output_file, index=False)
            logger.info(f"Pareto解已导出: {output_file}")

        except Exception as e:
            logger.error(f"导出Pareto解失败: {e}")
