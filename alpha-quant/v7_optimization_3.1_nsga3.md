# Alpha-Genesis V7.0 - 第三章：5项深度优化

## 3.1 策略进化引擎 → NSGA-III多目标

### 采纳全部用户建议，从单目标适应度升级为多目标优化

```python
# evolution_engine_v7.py

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Callable
from dataclasses import dataclass
from datetime import datetime
import random


@dataclass
class StrategyGenome:
    """策略基因组"""
    strategy_id: str
    genes: np.ndarray
    objectives: Dict[str, float] = None
    rank: int = 0
    crowding_distance: float = 0.0
    style: str = ''  # 策略风格
    generation: int = 0


class NSGAIIIEvolution:
    """
    NSGA-III 多目标策略进化引擎 V7.0
    
    优化目标 (7维):
    1. sharpe: 最大化夏普比率
    2. calmar: 最大化Calmar比率 (收益/最大回撤)
    3. win_rate: 最大化胜率
    4. capacity: 最大化策略容量
    5. max_drawdown: 最小化最大回撤
    6. turnover: 最小化换手率
    7. downside_vol: 最小化下行波动率
    """
    
    OBJECTIVES = [
        ('sharpe', 'maximize'),        # 最大化夏普比
        ('calmar', 'maximize'),        # 最大化Calmar比
        ('win_rate', 'maximize'),      # 最大化胜率
        ('capacity', 'maximize'),      # 最大化策略容量
        ('max_drawdown', 'minimize'),  # 最小化最大回撤
        ('turnover', 'minimize'),      # 最小化换手率
        ('downside_vol', 'minimize'),  # 最小化下行波动率
    ]
    
    def __init__(
        self,
        population_size: int = 200,
        reference_points_per_axis: int = 12,
        crossover_prob: float = 0.9,
        mutation_prob: float = 0.1
    ):
        self.population_size = population_size
        self.n_objectives = len(self.OBJECTIVES)
        
        # 小生境遗传算法 (保持多样性)
        self.niche_ga = NicheGeneticAlgorithm(
            crowding_distance=True,
            style_diversity=['momentum', 'mean_rev', 'ml', 'event', 'drl']
        )
        
        # 过拟合惩罚器
        self.overfit_penalty = OverfitPenalizer(
            in_out_sample_gap_weight=0.3,   # 样本内外差惩罚
            param_count_weight=0.1,          # 参数数量惩罚
            backtest_length_weight=0.1       # 回测期长惩罚
        )
        
        # 生成参考点
        self.reference_points = self._generate_reference_points(
            reference_points_per_axis
        )
        
        # 进化统计
        self.generation = 0
        self.pareto_history = []
        
    def _generate_reference_points(self, p: int) -> np.ndarray:
        """
        生成NSGA-III参考点
        
        使用单纯形格点法在M维目标空间均匀分布参考点
        """
        def generate_recursive(m, remaining_sum, current):
            if m == 1:
                return [current + [remaining_sum]]
            
            points = []
            for v in range(remaining_sum + 1):
                points.extend(
                    generate_recursive(m - 1, remaining_sum - v, current + [v])
                )
            return points
        
        raw_points = generate_recursive(self.n_objectives, p, [])
        points = np.array(raw_points) / p
        
        return points
    
    def evolve_daily(
        self,
        population: List[StrategyGenome],
        new_market_data: pd.DataFrame
    ) -> List[StrategyGenome]:
        """
        Online增量进化（盘后）
        
        每日收盘后执行一次进化迭代：
        1. 对现有种群进行增量回测
        2. 多目标适应度评估
        3. 应用过拟合惩罚
        4. 小生境选择下一代
        """
        print(f"[NSGA-III] Generation {self.generation + 1} evolution start")
        
        # 1. 增量回测 (只回测最新数据)
        updated_population = self._incremental_backtest(
            population, new_market_data
        )
        
        # 2. 多目标适应度评估
        fitness_matrix = self._multi_objective_evaluate(updated_population)
        
        # 3. 过拟合惩罚
        penalized_fitness = self._apply_overfit_penalty(
            updated_population, fitness_matrix
        )
        
        # 4. NSGA-III选择
        next_generation = self._nsga3_select(
            updated_population, penalized_fitness
        )
        
        # 5. 遗传操作 (交叉、变异)
        offspring = self._genetic_operators(next_generation)
        
        # 6. 环境选择 (精英保留)
        final_population = self._environmental_selection(
            next_generation + offspring
        )
        
        self.generation += 1
        
        # 记录Pareto前沿
        self._record_pareto_front(final_population)
        
        print(f"[NSGA-III] Generation {self.generation} complete, "
              f"Pareto front size: {len(self._get_pareto_front(final_population))}")
        
        return final_population
    
    def _incremental_backtest(
        self,
        population: List[StrategyGenome],
        new_data: pd.DataFrame
    ) -> List[StrategyGenome]:
        """
        增量回测
        
        只对最新一天数据进行回测，更新策略表现
        避免全量回测的巨大计算成本
        """
        updated = []
        
        for genome in population:
            # 解码基因为策略
            strategy = self._decode_genome(genome)
            
            # 执行当日回测
            daily_result = strategy.backtest(new_data)
            
            # 更新累计绩效 (滚动更新)
            if genome.objectives is None:
                genome.objectives = {}
            
            # 滚动计算各项指标
            genome.objectives = self._update_rolling_metrics(
                genome.objectives, daily_result
            )
            
            updated.append(genome)
        
        return updated
    
    def _multi_objective_evaluate(
        self,
        population: List[StrategyGenome]
    ) -> np.ndarray:
        """
        多目标适应度评估
        
        Returns:
            [N, M] 适应度矩阵，N=种群大小, M=目标数
        """
        fitness = []
        
        for genome in population:
            obj_values = []
            for obj_name, direction in self.OBJECTIVES:
                value = genome.objectives.get(obj_name, 0)
                
                # 最小化目标取负
                if direction == 'minimize':
                    value = -value
                
                obj_values.append(value)
            
            fitness.append(obj_values)
        
        return np.array(fitness)
    
    def _apply_overfit_penalty(
        self,
        population: List[StrategyGenome],
        fitness: np.ndarray
    ) -> np.ndarray:
        """应用过拟合惩罚"""
        penalized = fitness.copy()
        
        for i, genome in enumerate(population):
            penalty = self.overfit_penalty.calculate(genome)
            
            # 对所有目标应用惩罚
            penalized[i] *= (1 - penalty)
        
        return penalized
    
    def _nsga3_select(
        self,
        population: List[StrategyGenome],
        fitness: np.ndarray
    ) -> List[StrategyGenome]:
        """
        NSGA-III核心选择机制
        
        1. 非支配排序
        2. 参考点关联
        3. 小生境选择
        """
        # 非支配排序
        fronts = self._non_dominated_sort(fitness)
        
        # 为每个解分配rank
        for rank, front in enumerate(fronts):
            for idx in front:
                population[idx].rank = rank
        
        # 选择直到填满种群
        selected = []
        front_idx = 0
        
        while len(selected) + len(fronts[front_idx]) <= self.population_size:
            for idx in fronts[front_idx]:
                selected.append(population[idx])
            front_idx += 1
        
        # 处理最后一个前沿
        if len(selected) < self.population_size:
            last_front = [population[i] for i in fronts[front_idx]]
            
            # 归一化目标值
            normalized = self._normalize_objectives(fitness)
            
            # 关联参考点
            associated = self._associate_to_reference_points(
                normalized, fronts[front_idx]
            )
            
            # 小生境选择
            remaining = self.population_size - len(selected)
            niche_selected = self._niche_selection(
                last_front, associated, remaining
            )
            
            selected.extend(niche_selected)
        
        return selected
    
    def _non_dominated_sort(self, fitness: np.ndarray) -> List[List[int]]:
        """非支配排序"""
        n = len(fitness)
        domination_count = np.zeros(n, dtype=int)
        dominated_sets = [set() for _ in range(n)]
        
        for i in range(n):
            for j in range(i + 1, n):
                if self._dominates(fitness[i], fitness[j]):
                    dominated_sets[i].add(j)
                    domination_count[j] += 1
                elif self._dominates(fitness[j], fitness[i]):
                    dominated_sets[j].add(i)
                    domination_count[i] += 1
        
        # 构建前沿
        fronts = [[]]
        for i in range(n):
            if domination_count[i] == 0:
                fronts[0].append(i)
        
        i = 0
        while len(fronts[i]) > 0:
            next_front = []
            for p in fronts[i]:
                for q in dominated_sets[p]:
                    domination_count[q] -= 1
                    if domination_count[q] == 0:
                        next_front.append(q)
            i += 1
            fronts.append(next_front)
        
        return [f for f in fronts if len(f) > 0]
    
    def _dominates(self, a: np.ndarray, b: np.ndarray) -> bool:
        """判断a是否支配b"""
        return np.all(a >= b) and np.any(a > b)
    
    def _normalize_objectives(self, fitness: np.ndarray) -> np.ndarray:
        """归一化目标值"""
        ideal = np.min(fitness, axis=0)
        nadir = np.max(fitness, axis=0)
        
        denominator = nadir - ideal
        denominator[denominator == 0] = 1e-10
        
        return (fitness - ideal) / denominator
    
    def _associate_to_reference_points(
        self,
        normalized: np.ndarray,
        front: List[int]
    ) -> Dict[int, int]:
        """将前沿解关联到参考点"""
        associated = {}
        
        for idx in front:
            # 计算到各参考点的垂直距离
            distances = []
            for rp in self.reference_points:
                rp_norm = rp / np.linalg.norm(rp)
                projection = np.dot(normalized[idx], rp_norm)
                perp_dist = np.sqrt(
                    np.sum(normalized[idx]**2) - projection**2
                )
                distances.append(perp_dist)
            
            # 选择最近的参考点
            associated[idx] = np.argmin(distances)
        
        return associated
    
    def _niche_selection(
        self,
        candidates: List[StrategyGenome],
        associated: Dict[int, int],
        n_select: int
    ) -> List[StrategyGenome]:
        """小生境选择"""
        selected = []
        
        # 计算每个参考点的小生境数
        niche_count = {}
        for idx, rp_idx in associated.items():
            niche_count[rp_idx] = niche_count.get(rp_idx, 0) + 1
        
        # 按小生境数排序选择
        while len(selected) < n_select and candidates:
            # 找到小生境数最少的参考点
            min_niche = min(niche_count.values())
            min_rps = [rp for rp, count in niche_count.items() if count == min_niche]
            
            # 随机选择一个
            selected_rp = random.choice(min_rps)
            
            # 找到关联该参考点的候选解
            candidates_for_rp = [
                (i, genome) for i, genome in enumerate(candidates)
                if associated.get(id(genome)) == selected_rp
            ]
            
            if candidates_for_rp:
                # 选择距离最近的
                _, selected_genome = candidates_for_rp[0]
                selected.append(selected_genome)
                candidates.remove(selected_genome)
                niche_count[selected_rp] += 1
            else:
                # 该参考点无候选，标记为无穷
                niche_count[selected_rp] = float('inf')
        
        return selected
    
    def _genetic_operators(
        self,
        population: List[StrategyGenome]
    ) -> List[StrategyGenome]:
        """遗传操作 (交叉、变异)"""
        offspring = []
        
        while len(offspring) < self.population_size // 2:
            # 锦标赛选择父代
            parent1 = self._tournament_select(population)
            parent2 = self._tournament_select(population)
            
            # 交叉 (SBX)
            if random.random() < 0.9:
                child1_genes, child2_genes = self._simulated_binary_crossover(
                    parent1.genes, parent2.genes
                )
            else:
                child1_genes = parent1.genes.copy()
                child2_genes = parent2.genes.copy()
            
            # 变异 (多项式变异)
            if random.random() < 0.1:
                child1_genes = self._polynomial_mutation(child1_genes)
            if random.random() < 0.1:
                child2_genes = self._polynomial_mutation(child2_genes)
            
            # 继承风格
            style = random.choice([parent1.style, parent2.style])
            
            offspring.append(StrategyGenome(
                strategy_id=f"GEN{self.generation}_{len(offspring)}",
                genes=child1_genes,
                style=style,
                generation=self.generation
            ))
            
            if len(offspring) < self.population_size // 2:
                offspring.append(StrategyGenome(
                    strategy_id=f"GEN{self.generation}_{len(offspring)}",
                    genes=child2_genes,
                    style=style,
                    generation=self.generation
                ))
        
        return offspring
    
    def _tournament_select(
        self,
        population: List[StrategyGenome],
        tournament_size: int = 2
    ) -> StrategyGenome:
        """锦标赛选择"""
        tournament = random.sample(population, tournament_size)
        
        # 选择rank最小 (非支配排序靠前) 的个体
        best = tournament[0]
        for ind in tournament[1:]:
            if ind.rank < best.rank:
                best = ind
            elif ind.rank == best.rank and ind.crowding_distance > best.crowding_distance:
                best = ind
        
        return best
    
    def _simulated_binary_crossover(
        self,
        parent1: np.ndarray,
        parent2: np.ndarray,
        eta: float = 30.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """模拟二进制交叉 (SBX)"""
        child1 = np.zeros_like(parent1)
        child2 = np.zeros_like(parent1)
        
        for i in range(len(parent1)):
            if random.random() <= 0.5:
                if abs(parent1[i] - parent2[i]) > 1e-14:
                    if parent1[i] < parent2[i]:
                        y1, y2 = parent1[i], parent2[i]
                    else:
                        y1, y2 = parent2[i], parent1[i]
                    
                    beta = 1.0 + (2.0 * (y1 + 1) / (y2 - y1))
                    alpha = 2.0 - beta ** (-(eta + 1.0))
                    
                    rand = random.random()
                    if rand <= 1.0 / alpha:
                        beta_q = (rand * alpha) ** (1.0 / (eta + 1.0))
                    else:
                        beta_q = (1.0 / (2.0 - rand * alpha)) ** (1.0 / (eta + 1.0))
                    
                    c1 = 0.5 * ((y1 + y2) - beta_q * (y2 - y1))
                    c2 = 0.5 * ((y1 + y2) + beta_q * (y2 - y1))
                    
                    child1[i] = np.clip(c1, -1, 1)
                    child2[i] = np.clip(c2, -1, 1)
                else:
                    child1[i] = parent1[i]
                    child2[i] = parent2[i]
            else:
                child1[i] = parent1[i]
                child2[i] = parent2[i]
        
        return child1, child2
    
    def _polynomial_mutation(
        self,
        genes: np.ndarray,
        eta: float = 20.0
    ) -> np.ndarray:
        """多项式变异"""
        mutant = genes.copy()
        
        for i in range(len(genes)):
            if random.random() <= 1.0 / len(genes):
                y = genes[i]
                delta1 = (y + 1) / 2.0
                delta2 = (1 - y) / 2.0
                
                rand = random.random()
                mut_pow = 1.0 / (eta + 1.0)
                
                if rand <= 0.5:
                    xy = 1.0 - delta1
                    val = 2.0 * rand + (1.0 - 2.0 * rand) * (xy ** (eta + 1.0))
                    delta_q = val ** mut_pow - 1.0
                else:
                    xy = 1.0 - delta2
                    val = 2.0 * (1.0 - rand) + 2.0 * (rand - 0.5) * (xy ** (eta + 1.0))
                    delta_q = 1.0 - val ** mut_pow
                
                y = y + delta_q * 2.0
                mutant[i] = np.clip(y, -1, 1)
        
        return mutant
    
    def _environmental_selection(
        self,
        combined: List[StrategyGenome]
    ) -> List[StrategyGenome]:
        """环境选择"""
        # 获取适应度
        fitness = self._multi_objective_evaluate(combined)
        
        # 非支配排序
        fronts = self._non_dominated_sort(fitness)
        
        # 选择
        selected = []
        for front in fronts:
            if len(selected) + len(front) <= self.population_size:
                for idx in front:
                    selected.append(combined[idx])
            else:
                # 按拥挤距离排序选择
                front_fitness = fitness[front]
                crowding = self._calculate_crowding_distance(front_fitness)
                
                # 按拥挤距离降序
                sorted_indices = np.argsort(crowding)[::-1]
                remaining = self.population_size - len(selected)
                
                for i in sorted_indices[:remaining]:
                    selected.append(combined[front[i]])
                
                break
        
        return selected
    
    def _calculate_crowding_distance(self, fitness: np.ndarray) -> np.ndarray:
        """计算拥挤距离"""
        n = len(fitness)
        distances = np.zeros(n)
        
        for m in range(fitness.shape[1]):
            sorted_indices = np.argsort(fitness[:, m])
            distances[sorted_indices[0]] = float('inf')
            distances[sorted_indices[-1]] = float('inf')
            
            f_max = fitness[sorted_indices[-1], m]
            f_min = fitness[sorted_indices[0], m]
            
            if f_max > f_min:
                for i in range(1, n - 1):
                    distances[sorted_indices[i]] += (
                        fitness[sorted_indices[i + 1], m] -
                        fitness[sorted_indices[i - 1], m]
                    ) / (f_max - f_min)
        
        return distances
    
    def _get_pareto_front(self, population: List[StrategyGenome]) -> List[StrategyGenome]:
        """获取Pareto前沿"""
        fitness = self._multi_objective_evaluate(population)
        fronts = self._non_dominated_sort(fitness)
        
        return [population[i] for i in fronts[0]]
    
    def _record_pareto_front(self, population: List[StrategyGenome]):
        """记录Pareto前沿"""
        front = self._get_pareto_front(population)
        
        self.pareto_history.append({
            'generation': self.generation,
            'size': len(front),
            'hypervolume': self._calculate_hypervolume(front),
            'diversity': self._calculate_diversity(front)
        })
    
    def _calculate_hypervolume(self, front: List[StrategyGenome]) -> float:
        """计算超体积指标 (Hypervolume)"""
        # 简化的超体积计算
        # 实际实现需要更精确的算法
        return 0.0
    
    def _calculate_diversity(self, front: List[StrategyGenome]) -> float:
        """计算多样性指标"""
        # 计算前沿解的风格分布
        styles = [genome.style for genome in front]
        unique_styles = len(set(styles))
        
        return unique_styles / len(self.niche_ga.style_diversity)
    
    def _decode_genome(self, genome: StrategyGenome):
        """解码基因为可执行策略"""
        # 实际实现需要将基因数组转换为策略参数
        pass
    
    def _update_rolling_metrics(
        self,
        current: Dict,
        daily_result: Dict
    ) -> Dict:
        """滚动更新绩效指标"""
        # 简化的滚动更新逻辑
        updated = current.copy()
        
        # 更新收益
        updated['total_return'] = current.get('total_return', 0) + daily_result.get('return', 0)
        
        # 更新回撤
        # ...
        
        return updated


class NicheGeneticAlgorithm:
    """小生境遗传算法 - 保持种群多样性"""
    
    def __init__(
        self,
        crowding_distance: bool = True,
        style_diversity: List[str] = None
    ):
        self.crowding_distance = crowding_distance
        self.style_diversity = style_diversity or []
    
    def select(self, population, fitness):
        """小生境选择"""
        # 实现小生境选择逻辑
        return population


class OverfitPenalizer:
    """过拟合惩罚器"""
    
    def __init__(
        self,
        in_out_sample_gap_weight: float = 0.3,
        param_count_weight: float = 0.1,
        backtest_length_weight: float = 0.1
    ):
        self.weights = {
            'gap': in_out_sample_gap_weight,
            'params': param_count_weight,
            'length': backtest_length_weight
        }
    
    def calculate(self, genome: StrategyGenome) -> float:
        """计算过拟合惩罚"""
        # 样本内外差距
        gap_penalty = 0
        if 'in_sample_sharpe' in genome.objectives and 'out_sample_sharpe' in genome.objectives:
            gap = genome.objectives['in_sample_sharpe'] - genome.objectives['out_sample_sharpe']
            gap_penalty = max(0, gap) * self.weights['gap']
        
        # 参数数量惩罚
        param_penalty = len(genome.genes) * self.weights['params'] / 100.0
        
        # 回测期惩罚 (回测期越短越可能过拟合)
        length_penalty = self.weights['length'] / max(genome.objectives.get('backtest_days', 252), 1)
        
        return min(gap_penalty + param_penalty + length_penalty, 0.5)  # 最大惩罚50%



# API接口
"""
# 使用示例

engine = NSGAIIIEvolution(
    population_size=200,
    reference_points_per_axis=12
)

# 初始化种群
population = engine.initialize_population()

# 每日进化
daily_data = get_market_data('2025-03-10')
new_population = engine.evolve_daily(population, daily_data)

# 获取Pareto前沿策略
pareto_front = engine._get_pareto_front(new_population)

# 选择最优策略 (根据偏好)
best_strategy = select_by_preference(pareto_front, preference='balanced')
"""
```

---

*Module: Evolution Engine V7 - NSGA-III Multi-Objective Optimization*  
*Chapter: 3.1*  
*Status: 详细设计记录*
