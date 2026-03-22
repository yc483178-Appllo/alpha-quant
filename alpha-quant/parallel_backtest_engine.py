"""
Alpha-Genesis V6.1 SimEdge - 策略进化并行回测引擎
完善 P1-1: 策略进化并行回测
======================================
使用 multiprocessing.Pool + joblib 实现4核并行回测

Author: Alpha-Genesis Team
Version: 6.1.0
Date: 2026-03-09
"""

import os
import sys
import time
import logging
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List, Callable, Tuple, Optional
from dataclasses import dataclass
from functools import partial

# 并行计算库
try:
    from multiprocessing import Pool, cpu_count
    from joblib import Parallel, delayed
    PARALLEL_AVAILABLE = True
except ImportError:
    PARALLEL_AVAILABLE = False
    logging.warning("joblib 未安装，将使用单线程模式")

# 导入策略进化引擎
try:
    from strategy_evolution_engine import StrategyDNA, StrategyPopulation
    EVOLUTION_AVAILABLE = True
except ImportError:
    EVOLUTION_AVAILABLE = False

logger = logging.getLogger("ParallelBacktest")


@dataclass
class BacktestTask:
    """回测任务数据结构"""
    strategy_id: str
    strategy_type: str
    params: Dict
    data_hash: str  # 数据标识
    start_date: str
    end_date: str


@dataclass
class BacktestResult:
    """回测结果数据结构"""
    strategy_id: str
    fitness_score: float
    metrics: Dict
    execution_time: float
    status: str  # "success" | "failed"
    error_msg: str = ""


class ParallelBacktestEngine:
    """
    并行回测引擎
    
    功能：
    - 使用 multiprocessing.Pool 实现进程级并行
    - 使用 joblib 实现任务调度
    - 自动检测CPU核心数
    - 支持批量任务并行回测
    - 结果自动汇总
    """
    
    def __init__(self, n_jobs: int = None, backend: str = "multiprocessing"):
        """
        初始化并行回测引擎
        
        Args:
            n_jobs: 并行进程数 (默认: CPU核心数)
            backend: 并行后端 ("multiprocessing" | "threading")
        """
        self.n_jobs = n_jobs or (cpu_count() if PARALLEL_AVAILABLE else 1)
        self.backend = backend
        self.results_cache: Dict[str, BacktestResult] = {}
        
        logger.info(f"并行回测引擎初始化 | 并行度: {self.n_jobs} | 后端: {backend}")
    
    def _single_backtest(self, task: BacktestTask, market_data: pd.DataFrame) -> BacktestResult:
        """
        单个策略回测 (用于并行执行)
        
        Args:
            task: 回测任务
            market_data: 市场数据
        
        Returns:
            回测结果
        """
        start_time = time.time()
        
        try:
            # 创建策略DNA
            dna = StrategyDNA(
                id=task.strategy_id,
                strategy_type=task.strategy_type,
                params=task.params
            )
            
            # 执行回测 (简化版，实际应调用 backtest_engine)
            metrics = self._run_backtest_logic(dna, market_data)
            
            # 计算适应度
            fitness = self._calculate_fitness(metrics)
            
            execution_time = time.time() - start_time
            
            return BacktestResult(
                strategy_id=task.strategy_id,
                fitness_score=fitness,
                metrics=metrics,
                execution_time=execution_time,
                status="success"
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"回测失败 {task.strategy_id}: {e}")
            
            return BacktestResult(
                strategy_id=task.strategy_id,
                fitness_score=-999.0,
                metrics={},
                execution_time=execution_time,
                status="failed",
                error_msg=str(e)
            )
    
    def _run_backtest_logic(self, dna: StrategyDNA, data: pd.DataFrame) -> Dict:
        """
        执行回测逻辑 (简化版)
        实际应调用完整的 backtest_engine
        """
        # 模拟回测结果
        np.random.seed(hash(dna.id) % 2**32)
        
        # 基于策略类型和参数生成不同的回测结果
        if dna.strategy_type == "momentum":
            base_return = 0.08 + np.random.randn() * 0.05
            sharpe = 1.0 + np.random.randn() * 0.5
        elif dna.strategy_type == "mean_reversion":
            base_return = 0.06 + np.random.randn() * 0.04
            sharpe = 0.8 + np.random.randn() * 0.4
        else:  # ml_ensemble
            base_return = 0.10 + np.random.randn() * 0.06
            sharpe = 1.2 + np.random.randn() * 0.6
        
        # 参数调优影响
        param_quality = sum(1 for v in dna.params.values() if v > 0) / len(dna.params)
        base_return *= (0.8 + 0.4 * param_quality)
        sharpe *= (0.8 + 0.4 * param_quality)
        
        return {
            "annual_return": round(base_return, 4),
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(0.10 + np.random.rand() * 0.10, 4),
            "win_rate": round(0.45 + np.random.rand() * 0.20, 4),
            "num_trades": int(50 + np.random.rand() * 200),
            "calmar_ratio": round(base_return / 0.15, 2)
        }
    
    def _calculate_fitness(self, metrics: Dict) -> float:
        """计算适应度分数"""
        sharpe = metrics.get("sharpe_ratio", 0)
        ann_ret = metrics.get("annual_return", 0)
        win_rate = metrics.get("win_rate", 0)
        max_dd = abs(metrics.get("max_drawdown", 0))
        
        if metrics.get("num_trades", 0) < 10:
            return -999.0
        
        fitness = (
            sharpe * 0.4 +
            ann_ret * 100 * 0.3 +
            win_rate * 100 * 0.2 -
            max_dd * 100 * 0.1
        )
        return round(fitness, 2)
    
    def parallel_backtest(
        self,
        strategies: List[StrategyDNA],
        market_data: pd.DataFrame,
        use_cache: bool = True
    ) -> List[BacktestResult]:
        """
        并行回测多个策略
        
        Args:
            strategies: 策略列表
            market_data: 市场数据
            use_cache: 是否使用缓存
        
        Returns:
            回测结果列表
        """
        if not strategies:
            return []
        
        # 准备任务
        tasks = []
        for dna in strategies:
            task = BacktestTask(
                strategy_id=dna.id,
                strategy_type=dna.strategy_type,
                params=dna.params,
                data_hash=str(hash(market_data.values.tobytes())),
                start_date=str(market_data.index[0]),
                end_date=str(market_data.index[-1])
            )
            tasks.append(task)
        
        logger.info(f"开始并行回测 | 策略数: {len(tasks)} | 并行度: {self.n_jobs}")
        start_time = time.time()
        
        if PARALLEL_AVAILABLE and self.n_jobs > 1:
            # 使用 joblib 并行回测
            results = Parallel(n_jobs=self.n_jobs, backend=self.backend)(
                delayed(self._single_backtest)(task, market_data)
                for task in tasks
            )
        else:
            # 单线程回测
            logger.info("使用单线程模式")
            results = [
                self._single_backtest(task, market_data)
                for task in tasks
            ]
        
        total_time = time.time() - start_time
        avg_time = total_time / len(tasks)
        
        logger.info(f"并行回测完成 | 总耗时: {total_time:.2f}s | 平均: {avg_time:.2f}s/策略")
        
        # 缓存结果
        if use_cache:
            for result in results:
                self.results_cache[result.strategy_id] = result
        
        return results
    
    def batch_evolution_backtest(
        self,
        population: StrategyPopulation,
        market_data: pd.DataFrame
    ) -> Dict:
        """
        策略进化种群的批量回测
        
        Args:
            population: 策略种群
            market_data: 市场数据
        
        Returns:
            更新后的种群统计
        """
        # 提取所有活跃策略
        strategies = population.active
        
        logger.info(f"种群批量回测 | 活跃策略: {len(strategies)}")
        
        # 并行回测
        results = self.parallel_backtest(strategies, market_data)
        
        # 更新策略适应度
        success_count = 0
        failed_count = 0
        
        for result in results:
            # 找到对应的策略
            for dna in population.active:
                if dna.id == result.strategy_id:
                    if result.status == "success":
                        dna.fitness_score = result.fitness_score
                        dna.performance_history.append({
                            "date": datetime.now().isoformat(),
                            "generation": population.generation,
                            "fitness": result.fitness_score,
                            "metrics": result.metrics,
                            "backtest_time": result.execution_time,
                            "parallel": True
                        })
                        success_count += 1
                    else:
                        dna.fitness_score = -999.0
                        failed_count += 1
                    break
        
        # 按适应度排序
        population.active.sort(key=lambda x: x.fitness_score, reverse=True)
        
        return {
            "total": len(results),
            "success": success_count,
            "failed": failed_count,
            "best_fitness": population.active[0].fitness_score if population.active else 0,
            "avg_backtest_time": sum(r.execution_time for r in results) / len(results) if results else 0
        }
    
    def benchmark_parallel(self, n_strategies: int = 100) -> Dict:
        """
        并行回测性能基准测试
        
        Args:
            n_strategies: 测试策略数量
        
        Returns:
            性能对比结果
        """
        from strategy_evolution_engine import StrategyDNA
        
        # 生成测试策略
        strategies = []
        for i in range(n_strategies):
            stype = ["momentum", "mean_reversion", "ml_ensemble"][i % 3]
            dna = StrategyDNA.create_seed(stype)
            dna.id = f"BENCH_{i:03d}"
            strategies.append(dna)
        
        # 模拟市场数据
        dates = pd.date_range(end=datetime.now(), periods=252, freq='B')
        market_data = pd.DataFrame({
            'close': 100 + np.cumsum(np.random.randn(252) * 0.02),
            'volume': np.random.randint(1000000, 10000000, 252)
        }, index=dates)
        
        logger.info(f"性能基准测试 | 策略数: {n_strategies}")
        
        # 单线程测试
        single_engine = ParallelBacktestEngine(n_jobs=1)
        start = time.time()
        single_results = single_engine.parallel_backtest(strategies, market_data, use_cache=False)
        single_time = time.time() - start
        
        # 并行测试
        parallel_engine = ParallelBacktestEngine(n_jobs=self.n_jobs)
        start = time.time()
        parallel_results = parallel_engine.parallel_backtest(strategies, market_data, use_cache=False)
        parallel_time = time.time() - start
        
        speedup = single_time / parallel_time if parallel_time > 0 else 1
        efficiency = speedup / self.n_jobs * 100
        
        result = {
            "single_thread_time": round(single_time, 2),
            "parallel_time": round(parallel_time, 2),
            "speedup": round(speedup, 2),
            "efficiency": round(efficiency, 1),
            "n_jobs": self.n_jobs,
            "n_strategies": n_strategies
        }
        
        logger.info(f"基准测试完成 | 单线程: {result['single_thread_time']}s | "
                   f"并行: {result['parallel_time']}s | 加速比: {result['speedup']}x")
        
        return result


# ═══════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════

def parallel_evaluate_population(
    population: StrategyPopulation,
    market_data: pd.DataFrame,
    n_jobs: int = 4
) -> Dict:
    """
    便捷函数: 并行评估策略种群
    
    Args:
        population: 策略种群
        market_data: 市场数据
        n_jobs: 并行进程数
    
    Returns:
        评估统计
    """
    engine = ParallelBacktestEngine(n_jobs=n_jobs)
    return engine.batch_evolution_backtest(population, market_data)


def run_parallel_benchmark(n_strategies: int = 100) -> Dict:
    """
    便捷函数: 运行并行性能基准测试
    
    Args:
        n_strategies: 测试策略数量
    
    Returns:
        性能结果
    """
    engine = ParallelBacktestEngine()
    return engine.benchmark_parallel(n_strategies)


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== 策略进化并行回测引擎测试 ===\n")
    
    if not PARALLEL_AVAILABLE:
        print("❌ joblib 未安装，无法进行并行测试")
        exit(0)
    
    if not EVOLUTION_AVAILABLE:
        print("❌ 策略进化引擎未导入，使用模拟测试")
        exit(0)
    
    # 性能基准测试
    print("1. 并行性能基准测试:")
    benchmark = run_parallel_benchmark(n_strategies=50)
    print(f"   单线程耗时: {benchmark['single_thread_time']}s")
    print(f"   并行耗时: {benchmark['parallel_time']}s")
    print(f"   加速比: {benchmark['speedup']}x")
    print(f"   并行效率: {benchmark['efficiency']}%")
    
    # 种群批量回测测试
    print("\n2. 种群批量回测测试:")
    
    # 创建测试种群
    pop = StrategyPopulation(capacity=30)
    pop.initialize(seed_count_per_type=10)
    
    # 模拟市场数据
    dates = pd.date_range(end=datetime.now(), periods=252, freq='B')
    market_data = pd.DataFrame({
        'close': 100 + np.cumsum(np.random.randn(252) * 0.02),
        'volume': np.random.randint(1000000, 10000000, 252)
    }, index=dates)
    
    # 并行回测
    engine = ParallelBacktestEngine(n_jobs=4)
    stats = engine.batch_evolution_backtest(pop, market_data)
    
    print(f"   回测策略数: {stats['total']}")
    print(f"   成功: {stats['success']} | 失败: {stats['failed']}")
    print(f"   最佳适应度: {stats['best_fitness']:.2f}")
    print(f"   平均回测时间: {stats['avg_backtest_time']:.3f}s")
    
    print("\n✅ 并行回测引擎测试完成")
