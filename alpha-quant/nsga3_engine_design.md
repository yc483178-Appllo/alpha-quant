# Alpha-Genesis V7.0 - NSGA-III 多目标进化引擎

## 1. 架构概述

NSGA-III (Non-dominated Sorting Genetic Algorithm III) 是Deb等人于2014年提出的多目标优化算法，特别适用于3个及以上目标的优化问题。

### 1.1 为什么选择NSGA-III

| 特性 | 单目标GA | NSGA-II | NSGA-III |
|------|---------|---------|----------|
| 目标数量 | 1 | 2-3 | 3-15+ |
| 选择压力 | 高 | 中等 | 均匀分布 |
| 解多样性 | - | 较好 | 优秀 |
| 适合场景 | 单一目标 | 少目标权衡 | 多目标权衡 |

### 1.2 策略DNA编码 (5目标版本)

```python
class StrategyDNA_V7:
    """
    V7.0策略DNA - 支持多目标优化
    
    基因结构 (共50维):
    - 因子权重 (20维): 各因子的权重配置
    - 筛选参数 (15维): 流动性/市值/波动率筛选
    - 风控参数 (10维): 止损/止盈/仓位控制
    - 信号参数 (5维): 信号生成与衰减
    """
    
    GENE_STRUCTURE = {
        'factor_weights': {
            'start': 0,
            'end': 20,
            'factors': [
                'BARRA_BP', 'BARRA_EP', 'BARRA_Momentum',
                'BARRA_Size', 'BARRA_Beta', 'BARRA_ResidualVol',
                'Alpha_RSI', 'Alpha_MACD', 'Alpha_ROE',
                'Alpha_ProfitGrowth', 'Alpha_GrossMargin',
                # ... 更多因子
            ]
        },
        'filter_params': {
            'start': 20,
            'end': 35,
            'params': [
                'min_market_cap',      # 最小市值
                'max_market_cap',      # 最大市值
                'min_daily_amount',    # 最小日均成交额
                'max_volatility',      # 最大波动率
                'min_turnover',        # 最小换手率
                # ... 更多筛选参数
            ]
        },
        'risk_params': {
            'start': 35,
            'end': 45,
            'params': [
                'stop_loss_pct',       # 止损百分比
                'take_profit_pct',     # 止盈百分比
                'max_position_pct',    # 最大单仓占比
                'max_sector_pct',      # 最大行业占比
                'volatility_target',   # 目标波动率
                # ... 更多风控参数
            ]
        },
        'signal_params': {
            'start': 45,
            'end': 50,
            'params': [
                'signal_threshold',    # 信号阈值
                'signal_decay',        # 信号衰减系数
                'rebalance_freq',      # 换仓频率
                'holding_period',      # 目标持仓周期
                'urgency_level',       # 执行紧急程度
            ]
        }
    }
```

## 2. NSGA-III核心实现

### 2.1 参考点生成 (Reference Points)

```python
import numpy as np
from itertools import combinations
from typing import List

class ReferencePointGenerator:
    """
    生成NSGA-III参考点
    
    使用单纯形格点法 (Simplex-lattice Design)
    在M维目标空间中均匀分布参考点
    """
    
    def __init__(self, n_objectives: int, n_divisions: int):
        """
        Args:
            n_objectives: 目标数量 (5)
            n_divisions: 每维分割数 (决定参考点数量)
        """
        self.n_objectives = n_objectives
        self.n_divisions = n_divisions
        self.reference_points = self._generate_reference_points()
        
    def _generate_reference_points(self) -> np.ndarray:
        """生成参考点"""
        def recursive_generate(remaining_dims, remaining_sum, current_point):
            if remaining_dims == 1:
                return [current_point + [remaining_sum]]
            
            points = []
            for v in range(remaining_sum + 1):
                points.extend(
                    recursive_generate(
                        remaining_dims - 1,
                        remaining_sum - v,
                        current_point + [v]
                    )
                )
            return points
        
        # 生成所有可能的组合
        raw_points = recursive_generate(
            self.n_objectives,
            self.n_divisions,
            []
        )
        
        # 转换为概率单纯形
        points = np.array(raw_points) / self.n_divisions
        
        # 过滤掉边界点 (保留内部和边界)
        return points
    
    def associate(self, normalized_objectives: np.ndarray) -> int:
        """
        将解关联到最近的参考点
        
        Returns:
            最近参考点的索引
        """
        # 计算到各参考点的垂直距离
        distances = []
        for rp in self.reference_points:
            # 投影到参考线
            rp_norm = rp / np.linalg.norm(rp)
            projection = np.dot(normalized_objectives, rp_norm)
            perpendicular_dist = np.sqrt(
                np.sum(normalized_objectives ** 2) - projection ** 2
            )
            distances.append(perpendicular_dist)
        
        return np.argmin(distances)
    
    def get_niche_count(self, associated_points: List[int]) -> np.ndarray:
        """计算每个小生境的个体数"""
        niche_count = np.zeros(len(self.reference_points))
        for idx in associated_points:
            niche_count[idx] += 1
        return niche_count
```

### 2.2 非支配排序 (Non-dominated Sorting)

```python
class NonDominatedSorter:
    """非支配排序"""
    
    def sort(self, objectives: np.ndarray) -> List[List[int]]:
        """
        对种群进行非支配排序
        
        Args:
            objectives: [N, M] N个个体，M个目标
            
        Returns:
            fronts: 分层的前沿列表
        """
        n_individuals = len(objectives)
        
        # 支配计数和被支配集合
        domination_count = np.zeros(n_individuals, dtype=int)
        dominated_solutions = [set() for _ in range(n_individuals)]
        
        # 计算支配关系
        for i in range(n_individuals):
            for j in range(i + 1, n_individuals):
                if self._dominates(objectives[i], objectives[j]):
                    dominated_solutions[i].add(j)
                    domination_count[j] += 1
                elif self._dominates(objectives[j], objectives[i]):
                    dominated_solutions[j].add(i)
                    domination_count[i] += 1
        
        # 第一层前沿
        fronts = [[]]
        for i in range(n_individuals):
            if domination_count[i] == 0:
                fronts[0].append(i)
        
        # 后续前沿
        i = 0
        while len(fronts[i]) > 0:
            next_front = []
            for p in fronts[i]:
                for q in dominated_solutions[p]:
                    domination_count[q] -= 1
                    if domination_count[q] == 0:
                        next_front.append(q)
            i += 1
            fronts.append(next_front)
        
        # 移除空前沿
        fronts = [f for f in fronts if len(f) > 0]
        
        return fronts
    
    def _dominates(self, obj1: np.ndarray, obj2: np.ndarray) -> bool:
        """
        判断obj1是否支配obj2
        
        支配定义: 所有目标都不差于obj2，且至少一个目标严格优于
        """
        better_in_all = np.all(obj1 >= obj2)
        better_in_one = np.any(obj1 > obj2)
        return better_in_all and better_in_one
```

### 2.3 NSGA-III主算法

```python
import numpy as np
import random
from typing import List, Tuple, Callable
from dataclasses import dataclass
import logging


@dataclass
class Individual:
    """进化个体"""
    genes: np.ndarray
    objectives: np.ndarray = None
    rank: int = 0
    reference_point_idx: int = 0
    niche_count: float = 0.0


class NSGA3Engine:
    """
    NSGA-III 多目标进化引擎
    
    优化5个目标:
    1. 年化收益率 (最大化)
    2. 夏普比率 (最大化)
    3. 最大回撤 (最小化 -> 取负)
    4. 平均换手率 (最小化 -> 取负)
    5. 因子拥挤度 (最小化 -> 取负)
    """
    
    def __init__(
        self,
        n_objectives: int = 5,
        population_size: int = 200,
        n_generations: int = 100,
        crossover_prob: float = 0.9,
        mutation_prob: float = 0.1,
        eta_crossover: float = 30.0,
        eta_mutation: float = 20.0,
        n_divisions: int = 12  # 参考点分割数
    ):
        self.n_objectives = n_objectives
        self.population_size = population_size
        self.n_generations = n_generations
        self.crossover_prob = crossover_prob
        self.mutation_prob = mutation_prob
        self.eta_crossover = eta_crossover
        self.eta_mutation = eta_mutation
        
        # 生成参考点
        self.ref_point_gen = ReferencePointGenerator(
            n_objectives, n_divisions
        )
        self.reference_points = self.ref_point_gen.reference_points
        
        self.logger = logging.getLogger(__name__)
        
        # 目标边界 (用于归一化)
        self.ideal_point = None
        self.nadir_point = None
        
    def evolve(
        self,
        evaluate_func: Callable[[np.ndarray], np.ndarray]
    ) -> List[Individual]:
        """
        执行NSGA-III进化
        
        Args:
            evaluate_func: 评估函数，输入genes，输出objectives [M]
            
        Returns:
            Pareto前沿个体列表
        """
        self.logger.info("=" * 60)
        self.logger.info("NSGA-III 进化开始")
        self.logger.info(f"目标数: {self.n_objectives}")
        self.logger.info(f"种群大小: {self.population_size}")
        self.logger.info(f"进化代数: {self.n_generations}")
        self.logger.info(f"参考点数: {len(self.reference_points)}")
        self.logger.info("=" * 60)
        
        # 初始化种群
        population = self._initialize_population()
        
        # 评估初始种群
        for ind in population:
            ind.objectives = evaluate_func(ind.genes)
        
        # 进化循环
        for generation in range(self.n_generations):
            # 生成子代
            offspring = self._generate_offspring(population)
            
            # 评估子代
            for ind in offspring:
                ind.objectives = evaluate_func(ind.genes)
            
            # 合并种群
            combined = population + offspring
            
            # 环境选择
            population = self._environmental_selection(combined)
            
            # 日志
            if generation % 10 == 0:
                self._log_generation(generation, population)
        
        # 返回最终Pareto前沿
        fronts = NonDominatedSorter().sort(
            np.array([ind.objectives for ind in population])
        )
        pareto_front = [population[i] for i in fronts[0]]
        
        self.logger.info(f"进化完成，Pareto前沿大小: {len(pareto_front)}")
        
        return pareto_front
    
    def _initialize_population(self) -> List[Individual]:
        """初始化种群 (实数编码)"""
        population = []
        for _ in range(self.population_size):
            # 随机初始化基因 (范围 [-1, 1])
            genes = np.random.uniform(-1, 1, 50)
            population.append(Individual(genes=genes))
        return population
    
    def _generate_offspring(self, population: List[Individual]) -> List[Individual]:
        """生成子代"""
        offspring = []
        
        while len(offspring) < self.population_size:
            # 锦标赛选择父代
            parent1 = self._tournament_selection(population)
            parent2 = self._tournament_selection(population)
            
            # 交叉
            if random.random() < self.crossover_prob:
                child1_genes, child2_genes = self._simulated_binary_crossover(
                    parent1.genes, parent2.genes
                )
            else:
                child1_genes = parent1.genes.copy()
                child2_genes = parent2.genes.copy()
            
            # 变异
            if random.random() < self.mutation_prob:
                child1_genes = self._polynomial_mutation(child1_genes)
            if random.random() < self.mutation_prob:
                child2_genes = self._polynomial_mutation(child2_genes)
            
            offspring.append(Individual(genes=child1_genes))
            if len(offspring) < self.population_size:
                offspring.append(Individual(genes=child2_genes))
        
        return offspring
    
    def _tournament_selection(self, population: List[Individual]) -> Individual:
        """锦标赛选择"""
        tournament_size = 2
        tournament = random.sample(population, tournament_size)
        
        # 选择rank最小的 (非支配排序靠前)
        best = tournament[0]
        for ind in tournament[1:]:
            if ind.rank < best.rank:
                best = ind
            elif ind.rank == best.rank and ind.niche_count < best.niche_count:
                best = ind
        
        return best
    
    def _simulated_binary_crossover(
        self,
        parent1: np.ndarray,
        parent2: np.ndarray
    ) -> Tuple[np.ndarray, np.ndarray]:
        """模拟二进制交叉 (SBX)"""
        child1 = np.zeros_like(parent1)
        child2 = np.zeros_like(parent1)
        
        for i in range(len(parent1)):
            if random.random() <= 0.5:
                # 计算beta
                if abs(parent1[i] - parent2[i]) > 1e-14:
                    if parent1[i] < parent2[i]:
                        y1, y2 = parent1[i], parent2[i]
                    else:
                        y1, y2 = parent2[i], parent1[i]
                    
                    beta = 1.0 + (2.0 * (y1 - (-1)) / (y2 - y1))
                    alpha = 2.0 - beta ** (-(self.eta_crossover + 1.0))
                    
                    rand = random.random()
                    if rand <= 1.0 / alpha:
                        beta_q = (rand * alpha) ** (1.0 / (self.eta_crossover + 1.0))
                    else:
                        beta_q = (1.0 / (2.0 - rand * alpha)) ** (1.0 / (self.eta_crossover + 1.0))
                    
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
    
    def _polynomial_mutation(self, genes: np.ndarray) -> np.ndarray:
        """多项式变异"""
        mutant = genes.copy()
        
        for i in range(len(genes)):
            if random.random() <= 1.0 / len(genes):
                y = genes[i]
                delta1 = (y - (-1)) / (1 - (-1))
                delta2 = (1 - y) / (1 - (-1))
                
                rand = random.random()
                mut_pow = 1.0 / (self.eta_mutation + 1.0)
                
                if rand <= 0.5:
                    xy = 1.0 - delta1
                    val = 2.0 * rand + (1.0 - 2.0 * rand) * (xy ** (self.eta_mutation + 1.0))
                    delta_q = val ** mut_pow - 1.0
                else:
                    xy = 1.0 - delta2
                    val = 2.0 * (1.0 - rand) + 2.0 * (rand - 0.5) * (xy ** (self.eta_mutation + 1.0))
                    delta_q = 1.0 - val ** mut_pow
                
                y = y + delta_q * (1 - (-1))
                mutant[i] = np.clip(y, -1, 1)
        
        return mutant
    
    def _environmental_selection(
        self,
        combined: List[Individual]
    ) -> List[Individual]:
        """环境选择 (NSGA-III核心)"""
        # 获取目标值矩阵
        objectives = np.array([ind.objectives for ind in combined])
        
        # 非支配排序
        fronts = NonDominatedSorter().sort(objectives)
        
        # 分配rank
        for rank, front in enumerate(fronts):
            for idx in front:
                combined[idx].rank = rank
        
        # 选择直到填满种群
        new_population = []
        front_idx = 0
        
        while len(new_population) + len(fronts[front_idx]) <= self.population_size:
            for idx in fronts[front_idx]:
                new_population.append(combined[idx])
            front_idx += 1
            
            if front_idx >= len(fronts):
                break
        
        # 如果还需要选择
        remaining = self.population_size - len(new_population)
        if remaining > 0 and front_idx < len(fronts):
            last_front = [combined[i] for i in fronts[front_idx]]
            
            # 归一化目标值
            normalized_objs = self._normalize_objectives(
                np.array([ind.objectives for ind in new_population + last_front])
            )
            
            # 关联参考点
            associated = []
            for i, ind in enumerate(last_front):
                idx = len(new_population) + i
                rp_idx = self.ref_point_gen.associate(normalized_objs[idx])
                ind.reference_point_idx = rp_idx
                associated.append(rp_idx)
            
            # 计算小生境数
            niche_count = self.ref_point_gen.get_niche_count(associated)
            
            # 根据小生境数选择
            selected_from_last = self._niching_selection(
                last_front, niche_count, remaining
            )
            new_population.extend(selected_from_last)
        
        return new_population
    
    def _normalize_objectives(self, objectives: np.ndarray) -> np.ndarray:
        """归一化目标值"""
        # 更新理想点和Nadir点
        self.ideal_point = np.min(objectives, axis=0)
        self.nadir_point = np.max(objectives, axis=0)
        
        # 避免除零
        denominator = self.nadir_point - self.ideal_point
        denominator[denominator == 0] = 1e-10
        
        normalized = (objectives - self.ideal_point) / denominator
        
        # 处理最小化目标 (已经在外部取负)
        return normalized
    
    def _niching_selection(
        self,
        candidates: List[Individual],
        niche_count: np.ndarray,
        n_select: int
    ) -> List[Individual]:
        """小生境选择"""
        selected = []
        candidates = candidates.copy()
        
        while len(selected) < n_select and candidates:
            # 找到小生境数最少的参考点
            min_niche = np.min(niche_count)
            min_indices = np.where(niche_count == min_niche)[0]
            
            # 随机选择一个
            selected_rp = random.choice(min_indices)
            
            # 找到关联该参考点的候选解
            associated_candidates = [
                i for i, c in enumerate(candidates)
                if c.reference_point_idx == selected_rp
            ]
            
            if associated_candidates:
                # 随机选择一个
                selected_idx = random.choice(associated_candidates)
                selected.append(candidates[selected_idx])
                candidates.pop(selected_idx)
                niche_count[selected_rp] += 1
            else:
                # 没有候选解关联此参考点，标记为无穷大
                niche_count[selected_rp] = float('inf')
        
        return selected
    
    def _log_generation(self, generation: int, population: List[Individual]):
        """记录世代信息"""
        objectives = np.array([ind.objectives for ind in population])
        
        self.logger.info(f"Generation {generation}:")
        self.logger.info(f"  Return: {objectives[:, 0].mean():.4f} (±{objectives[:, 0].std():.4f})")
        self.logger.info(f"  Sharpe: {objectives[:, 1].mean():.4f} (±{objectives[:, 1].std():.4f})")
        self.logger.info(f"  MaxDD:  {objectives[:, 2].mean():.4f} (±{objectives[:, 2].std():.4f})")
        self.logger.info(f"  Turnover: {objectives[:, 3].mean():.4f}")
        self.logger.info(f"  Crowding: {objectives[:, 4].mean():.4f}")
```

## 3. 并行评估系统

```python
from concurrent.futures import ProcessPoolExecutor, as_completed
from typing import List, Callable
import multiprocessing as mp

class ParallelStrategyEvaluator:
    """并行策略评估器"""
    
    def __init__(self, n_workers: int = None):
        self.n_workers = n_workers or mp.cpu_count()
        
    def batch_evaluate(
        self,
        strategies: List[np.ndarray],
        evaluate_func: Callable[[np.ndarray], np.ndarray]
    ) -> List[np.ndarray]:
        """批量并行评估"""
        results = [None] * len(strategies)
        
        with ProcessPoolExecutor(max_workers=self.n_workers) as executor:
            # 提交任务
            future_to_idx = {
                executor.submit(evaluate_func, strategy): i
                for i, strategy in enumerate(strategies)
            }
            
            # 收集结果
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logging.error(f"策略 {idx} 评估失败: {e}")
                    # 返回惩罚值
                    results[idx] = np.array([0, 0, 1, 1, 1])
        
        return results
```

## 4. 评估函数实现

```python
class StrategyEvaluator:
    """策略评估器 - 计算5个优化目标"""
    
    def __init__(
        self,
        backtest_engine,
        data_source,
        risk_free_rate: float = 0.03
    ):
        self.backtest_engine = backtest_engine
        self.data_source = data_source
        self.risk_free_rate = risk_free_rate
        
    def evaluate(self, genes: np.ndarray) -> np.ndarray:
        """
        评估策略DNA
        
        Returns:
            [return, sharpe, -maxdd, -turnover, -crowding]
        """
        # 解码DNA为策略配置
        strategy_config = self._decode_genes(genes)
        
        # 执行回测
        backtest_result = self.backtest_engine.run(strategy_config)
        
        # 计算目标值
        annual_return = backtest_result['annual_return']
        sharpe_ratio = backtest_result['sharpe_ratio']
        max_drawdown = backtest_result['max_drawdown']
        avg_turnover = backtest_result['avg_turnover']
        factor_crowding = self._calculate_factor_crowding(strategy_config)
        
        # 注意: 最小化目标取负
        return np.array([
            annual_return,
            sharpe_ratio,
            -max_drawdown,
            -avg_turnover,
            -factor_crowding
        ])
    
    def _decode_genes(self, genes: np.ndarray) -> Dict:
        """解码基因为策略配置"""
        config = {}
        
        # 因子权重
        config['factor_weights'] = {}
        for i, factor in enumerate(StrategyDNA_V7.GENE_STRUCTURE['factor_weights']['factors']):
            config['factor_weights'][factor] = max(0, genes[i])  # 非负权重
        
        # 归一化权重
        total_weight = sum(config['factor_weights'].values())
        if total_weight > 0:
            for factor in config['factor_weights']:
                config['factor_weights'][factor] /= total_weight
        
        # 其他参数...
        
        return config
    
    def _calculate_factor_crowding(self, strategy_config: Dict) -> float:
        """计算因子拥挤度"""
        # 基于市场上使用该因子的资金规模估算
        # 高拥挤度 = 高风险
        factor_weights = strategy_config['factor_weights']
        
        # 获取各因子的市场拥挤度数据
        crowding_scores = {}
        for factor in factor_weights:
            crowding_scores[factor] = self.data_source.get_factor_crowding(factor)
        
        # 加权平均
        total_crowding = sum(
            factor_weights[f] * crowding_scores[f]
            for f in factor_weights
        )
        
        return total_crowding
```

## 5. 使用示例

```python
def main():
    """NSGA-III使用示例"""
    
    # 初始化组件
    data_source = DataSource()
    backtest_engine = BacktestEngine()
    evaluator = StrategyEvaluator(backtest_engine, data_source)
    
    # 初始化NSGA-III引擎
    engine = NSGA3Engine(
        n_objectives=5,
        population_size=200,
        n_generations=100,
        n_divisions=12
    )
    
    # 执行进化
    pareto_front = engine.evolve(evaluator.evaluate)
    
    # 分析结果
    print(f"找到 {len(pareto_front)} 个Pareto最优策略")
    
    for i, ind in enumerate(pareto_front[:5]):
        print(f"\n策略 {i+1}:")
        print(f"  年化收益: {ind.objectives[0]:.2%}")
        print(f"  夏普比率: {ind.objectives[1]:.2f}")
        print(f"  最大回撤: {-ind.objectives[2]:.2%}")
        print(f"  换手率: {-ind.objectives[3]:.2%}")
        print(f"  拥挤度: {-ind.objectives[4]:.4f}")

if __name__ == "__main__":
    main()
```

## 6. API接口设计

```python
from flask import Flask, request, jsonify

app = Flask(__name__)
nsga3_engine = None

@app.route('/api/v7/evolution/nsga3/start', methods=['POST'])
def start_evolution():
    """启动NSGA-III进化"""
    data = request.json
    
    global nsga3_engine
    nsga3_engine = NSGA3Engine(
        n_objectives=data.get('n_objectives', 5),
        population_size=data.get('population_size', 200),
        n_generations=data.get('n_generations', 100)
    )
    
    # 异步启动进化
    # ...
    
    return jsonify({
        "status": "started",
        "job_id": generate_job_id()
    })

@app.route('/api/v7/evolution/nsga3/status/<job_id>', methods=['GET'])
def get_evolution_status(job_id):
    """获取进化状态"""
    # 返回当前进度、当前代、最佳指标等
    pass

@app.route('/api/v7/evolution/nsga3/results/<job_id>', methods=['GET'])
def get_evolution_results(job_id):
    """获取进化结果"""
    # 返回Pareto前沿
    pass
```

---

*Module: NSGA-III Evolution Engine*  
*Version: V7.0*  
*Status: 详细设计完成，待实施*
