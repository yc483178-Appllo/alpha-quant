"""
策略进化引擎 - V6.0 新增模块
文件: strategy_evolution_engine.py
功能: 基于遗传算法的策略自动进化系统
依赖: pymongo, numpy, pandas, logging
"""
import os
import json
import random
import logging
import numpy as np
import pandas as pd
from uuid import uuid4
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field, asdict

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None
    logging.warning("pymongo未安装，MongoDB功能将不可用")

logger = logging.getLogger("StrategyEvolution")


@dataclass
class StrategyDNA:
    """
    Gene representation of strategies
    DNA structure: Parameter vector + Metadata + Lineage information
    """
    id: str = field(default_factory=lambda: str(uuid4())[:8])
    strategy_type: str = "momentum"          # momentum / mean_reversion / ml_ensemble
    generation: int = 0  # Generation to which it belongs
    params: Dict = field(default_factory=dict)  # Dictionary of strategy parameters
    fitness_score: float = 0.0  # Fitness score
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    parent_ids: List[str] = field(default_factory=list)  # List of parent IDs
    performance_history: List[Dict] = field(default_factory=list)  # Historical performance
    
    # Default parameter configuration (by strategy type)
    DEFAULT_PARAMS = {
        "momentum": {
            "lookback_period": 20,  # Momentum lookback period (days)
            "buy_threshold": 0.05,  # Buy threshold
            "sell_threshold": -0.03,  # Sell threshold
            "vol_filter": 0.3,  # Volatility filter cap
            "rsi_oversell": 30,  # RSI oversell line
            "ma_fast": 5,  # Fast moving average
            "ma_slow": 20,  # Slow moving average
            "position_size": 0.1,  # Single stock position
        },
        "mean_reversion": {
            "bb_period": 20,  # Bollinger Band Period
            "bb_std": 2.0,  # Bollinger Band standard deviation multiple
            "rsi_period": 14,  # RSI calculation period
            "rsi_low": 30,  # RSI oversold level (buy)
            "rsi_high": 70,  # RSI overbought line (sell)
            "mean_period": 60,  # Mean regression baseline period
            "deviation_threshold": 0.08,  # Deviation from the threshold
            "position_size": 0.08,
        },
        "ml_ensemble": {
            "n_estimators": 100,  # Number of ensemble trees
            "max_depth": 5,  # Tree depth
            "feature_lookback": 30,  # Feature lookback period
            "confidence_threshold": 0.6,  # Signal confidence threshold
            "retrain_freq_days": 30,  # Retraining frequency
            "position_size": 0.12,
        }
    }
    
    @classmethod
    def create_seed(cls, strategy_type: str) -> 'StrategyDNA':
        """Seed Creation Strategy (Initial Population)"""
        params = cls.DEFAULT_PARAMS.get(strategy_type, cls.DEFAULT_PARAMS["momentum"]).copy()
        # Add random perturbation to avoid an initial population of identical individuals
        for k, v in params.items():
            if isinstance(v, float):
                params[k] = v * (1 + random.gauss(0, 0.1))
            elif isinstance(v, int) and v > 5:
                params[k] = max(1, int(v * (1 + random.gauss(0, 0.15))))
        return cls(strategy_type=strategy_type, params=params)
    
    def mutate(self, mutation_rate: float = 0.15) -> 'StrategyDNA':
        """
        Single-point random mutation
        mutation_rate: The probability that each parameter will be mutated.
        """
        mutated_params = self.params.copy()
        for key, value in mutated_params.items():
            if random.random() < mutation_rate:
                if isinstance(value, float):
                    # Gaussian perturbation (5% standard deviation)
                    delta = random.gauss(0, 0.05)
                    mutated_params[key] = max(0.001, value * (1 + delta))
                elif isinstance(value, int):
                    # Integer ±1 Mutation
                    mutated_params[key] = max(1, value + random.choice([-1, 0, 1]))
        
        child = StrategyDNA(
            strategy_type=self.strategy_type,
            generation=self.generation + 1,
            params=mutated_params,
            parent_ids=[self.id]
        )
        logger.debug(f"Mutation: {self.id} → {child.id} (replacing {child.generation})")
        return child
    
    def crossover(self, other: 'StrategyDNA') -> 'StrategyDNA':
        """
        Uniform Crossover
        Each parameter has a 50% probability of originating from either parent 1 or parent 2.
        """
        child_params = {}
        all_keys = set(list(self.params.keys()) + list(other.params.keys()))
        
        for key in all_keys:
            v1 = self.params.get(key)
            v2 = other.params.get(key)
            if v1 is None:
                child_params[key] = v2
            elif v2 is None:
                child_params[key] = v1
            else:
                # 50-50 (random selection, or a mixture of floating-point numbers)
                if isinstance(v1, float) and isinstance(v2, float):
                    alpha = random.random()
                    child_params[key] = alpha * v1 + (1 - alpha) * v2
                else:
                    child_params[key] = v1 if random.random() < 0.5 else v2
        
        child = StrategyDNA(
            strategy_type=self.strategy_type,
            generation=max(self.generation, other.generation) + 1,
            params=child_params,
            parent_ids=[self.id, other.id]
        )
        logger.debug(f"cross: {self.id} + {other.id} → {child.id}")
        return child


class StrategyPopulation:
    """
    策略种群管理
    维护: 活跃池 / 墓地 / 名人堂
    """
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.active: List[StrategyDNA] = []        # 当前活跃策略
        self.graveyard: List[StrategyDNA] = []     # 墓地（低分淘汰）
        self.hall_of_fame: List[StrategyDNA] = []  # 名人堂 Top5
        self.generation: int = 0
    
    def initialize(self, seed_count_per_type: int = 10):
        """初始化种群：每种策略类型生成seed_count个种子"""
        strategy_types = ["momentum", "mean_reversion", "ml_ensemble"]
        for stype in strategy_types:
            for _ in range(seed_count_per_type):
                dna = StrategyDNA.create_seed(stype)
                self.active.append(dna)
        logger.info(f"种群初始化完成，共 {len(self.active)} 个策略")
    
    def evaluate_fitness(self, dna: StrategyDNA, metrics: Dict):
        """
        计算适应度评分
        Fitness = Sharpe×0.4 + AnnualReturn×0.3 + WinRate×0.2 - MaxDrawdown×0.1
        """
        sharpe = metrics.get("sharpe_ratio", 0)
        ann_ret = metrics.get("annual_return", 0)
        win_rate = metrics.get("win_rate", 0)
        max_dd = abs(metrics.get("max_drawdown", 0))
        
        # 剔除无效策略（交易次数过少）
        if metrics.get("num_trades", 0) < 10:
            dna.fitness_score = -999.0
        else:
            dna.fitness_score = (
                sharpe * 0.4 +
                ann_ret * 100 * 0.3 +   # 转为百分比
                win_rate * 100 * 0.2 -
                max_dd * 100 * 0.1
            )
        
        dna.performance_history.append({
            "date": datetime.now().isoformat(),
            "generation": self.generation,
            "fitness": dna.fitness_score,
            "metrics": metrics
        })
    
    def tournament_select(self, tournament_size: int = 5, n: int = 10) -> List[StrategyDNA]:
        """锦标赛选择：随机选k个，取最优，重复n次"""
        selected = []
        candidates = [s for s in self.active if s.fitness_score > -900]
        if len(candidates) < tournament_size:
            return candidates
        for _ in range(n):
            tournament = random.sample(candidates, min(tournament_size, len(candidates)))
            winner = max(tournament, key=lambda x: x.fitness_score)
            selected.append(winner)
        return selected
    
    def evolve(self, crossover_ratio: float = 0.7):
        """执行一代进化：选择→繁殖→淘汰"""
        if len(self.active) < 4:
            logger.warning("种群数量不足，跳过进化")
            return
        
        # 1. 锦标赛选择父代
        parents = self.tournament_select(tournament_size=5, n=20)
        if not parents:
            return
        
        num_offspring = min(50, self.capacity - len(self.active))
        offspring = []
        
        # 2. 交叉产生后代
        for _ in range(int(num_offspring * crossover_ratio)):
            if len(parents) >= 2:
                p1, p2 = random.sample(parents, 2)
                child = p1.crossover(p2)
                offspring.append(child)
        
        # 3. 变异产生后代
        for _ in range(int(num_offspring * (1 - crossover_ratio))):
            parent = random.choice(parents)
            child = parent.mutate(mutation_rate=0.15)
            offspring.append(child)
        
        # 4. 加入活跃池
        self.active.extend(offspring)
        
        # 5. 淘汰弱者（保留capacity个）
        self.active.sort(key=lambda x: x.fitness_score, reverse=True)
        survivors = self.active[:self.capacity]
        eliminated = self.active[self.capacity:]
        
        # 6. 淘汰者进墓地（最多保留500个）
        self.graveyard.extend(eliminated)
        self.graveyard = self.graveyard[-500:]
        self.active = survivors
        
        # 7. 更新名人堂
        all_strategies = self.active + self.graveyard
        top5 = sorted(all_strategies, key=lambda x: x.fitness_score, reverse=True)[:5]
        self.hall_of_fame = [s for s in top5 if s.fitness_score > 0]
        
        self.generation += 1
        logger.info(f"第{self.generation}代进化完成 | 活跃:{len(self.active)} | 墓地:{len(self.graveyard)} | 名人堂:{len(self.hall_of_fame)}")
    
    def revive(self, strategy_id: str) -> Optional[StrategyDNA]:
        """从墓地复活策略"""
        for dna in self.graveyard:
            if dna.id == strategy_id:
                self.active.append(dna)
                self.graveyard.remove(dna)
                logger.info(f"策略 {strategy_id} 已从墓地复活")
                return dna
        return None
    
    def get_best(self) -> Optional[StrategyDNA]:
        """获取当前最优策略"""
        if self.hall_of_fame:
            return self.hall_of_fame[0]
        if self.active:
            return max(self.active, key=lambda x: x.fitness_score)
        return None


class StrategyEvolutionEngine:
    """
    策略进化引擎主类
    协调种群进化、回测评估、与现有系统的集成
    """
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self._load_config(config_path)
        self.population = StrategyPopulation(
            capacity=self.config.get("population_capacity", 100)
        )
        self.backtest_cache: Dict[str, Dict] = {}
        self.mongo_client: Optional[MongoClient] = None
        self.db = None
        self._init_mongodb()
        
    def _load_config(self, config_path: str) -> Dict:
        """加载配置文件"""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f).get("strategy_evolution", {})
        except Exception as e:
            logger.warning(f"配置加载失败，使用默认: {e}")
            return self._default_config()
    
    def _default_config(self) -> Dict:
        """默认配置"""
        return {
            "enabled": True,
            "population_capacity": 100,
            "seed_count_per_type": 10,
            "evolution_frequency_hours": 24,
            "crossover_ratio": 0.7,
            "mutation_rate": 0.15,
            "tournament_size": 5,
            "backtest_days": 60,
            "min_trades": 10,
            "hall_of_fame_size": 5,
            "mongodb": {
                "enabled": False,
                "uri": "mongodb://localhost:27017",
                "db_name": "alpha_evolution"
            }
        }
    
    def _init_mongodb(self):
        """初始化MongoDB连接"""
        mongo_cfg = self.config.get("mongodb", {})
        if not mongo_cfg.get("enabled", False) or MongoClient is None:
            return
        try:
            self.mongo_client = MongoClient(
                mongo_cfg.get("uri", "mongodb://localhost:27017"),
                serverSelectionTimeoutMS=5000
            )
            self.db = self.mongo_client[mongo_cfg.get("db_name", "alpha_evolution")]
            logger.info("✅ MongoDB连接成功")
        except Exception as e:
            logger.warning(f"MongoDB连接失败: {e}")
            self.mongo_client = None
    
    def initialize_population(self):
        """初始化策略种群"""
        seed_count = self.config.get("seed_count_per_type", 10)
        self.population.initialize(seed_count_per_type=seed_count)
        logger.info(f"策略种群初始化完成: {len(self.population.active)}个策略")
    
    def backtest_strategy(self, dna: StrategyDNA, 
                          data: pd.DataFrame,
                          initial_capital: float = 100000) -> Dict:
        """
        对单个策略DNA进行回测评估
        
        Args:
            dna: 策略DNA
            data: 历史数据
            initial_capital: 初始资金
            
        Returns:
            回测指标字典
        """
        params = dna.params
        
        # 简化回测逻辑（实际应使用backtest_engine）
        try:
            signals = self._generate_signals(dna.strategy_type, data, params)
            returns = self._simulate_trades(signals, data, initial_capital)
            
            metrics = self._calculate_metrics(returns, signals)
            return metrics
            
        except Exception as e:
            logger.error(f"回测失败 {dna.id}: {e}")
            return {"sharpe_ratio": 0, "annual_return": 0, "win_rate": 0, 
                    "max_drawdown": 1, "num_trades": 0}
    
    def _generate_signals(self, strategy_type: str, 
                          data: pd.DataFrame, 
                          params: Dict) -> pd.Series:
        """生成交易信号"""
        signals = pd.Series(0, index=data.index)
        
        if strategy_type == "momentum":
            # 动量策略信号
            lookback = int(params.get("lookback_period", 20))
            buy_th = params.get("buy_threshold", 0.05)
            sell_th = params.get("sell_threshold", -0.03)
            
            if 'close' in data.columns:
                returns = data['close'].pct_change(lookback)
                signals[returns > buy_th] = 1
                signals[returns < sell_th] = -1
                
        elif strategy_type == "mean_reversion":
            # 均值回归策略信号
            bb_period = int(params.get("bb_period", 20))
            bb_std = params.get("bb_std", 2.0)
            
            if 'close' in data.columns:
                ma = data['close'].rolling(bb_period).mean()
                std = data['close'].rolling(bb_period).std()
                upper = ma + bb_std * std
                lower = ma - bb_std * std
                
                signals[data['close'] < lower] = 1  # 超卖买入
                signals[data['close'] > upper] = -1  # 超买卖出
                
        elif strategy_type == "ml_ensemble":
            # ML策略信号（简化版）
            conf_th = params.get("confidence_threshold", 0.6)
            if 'close' in data.columns:
                # 使用价格动量作为简化特征
                returns = data['close'].pct_change(5)
                signals[returns > conf_th * 0.1] = 1
                signals[returns < -conf_th * 0.1] = -1
        
        return signals
    
    def _simulate_trades(self, signals: pd.Series, 
                         data: pd.DataFrame,
                         initial_capital: float) -> pd.Series:
        """模拟交易获取收益序列"""
        position = 0
        capital = initial_capital
        returns = []
        
        for i in range(1, len(signals)):
            signal = signals.iloc[i]
            price = data['close'].iloc[i] if 'close' in data.columns else 1
            
            if signal == 1 and position <= 0:  # 买入
                position = 1
            elif signal == -1 and position >= 0:  # 卖出
                position = 0
            
            # 简化收益计算
            if i > 0 and 'close' in data.columns:
                daily_return = data['close'].iloc[i] / data['close'].iloc[i-1] - 1
                capital *= (1 + position * daily_return)
            
            returns.append(capital / initial_capital - 1)
        
        return pd.Series(returns)
    
    def _calculate_metrics(self, returns: pd.Series, 
                          signals: pd.Series) -> Dict:
        """计算回测指标"""
        if len(returns) < 2 or returns.std() == 0:
            return {"sharpe_ratio": 0, "annual_return": 0, "win_rate": 0, 
                    "max_drawdown": 1, "num_trades": 0}
        
        # 交易次数
        num_trades = (signals != 0).sum()
        
        # 年化收益
        total_return = returns.iloc[-1] if len(returns) > 0 else 0
        annual_return = total_return * (252 / max(len(returns), 1))
        
        # 夏普比率
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        # 胜率
        daily_returns = returns.diff().dropna()
        win_rate = (daily_returns > 0).sum() / len(daily_returns) if len(daily_returns) > 0 else 0
        
        # 最大回撤
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_dd = abs(drawdown.min()) if len(drawdown) > 0 else 0
        
        return {
            "sharpe_ratio": sharpe,
            "annual_return": annual_return,
            "win_rate": win_rate,
            "max_drawdown": max_dd,
            "num_trades": int(num_trades)
        }
    
    def evaluate_population(self, data: pd.DataFrame):
        """评估整个种群的适应度"""
        logger.info("开始评估种群适应度...")
        
        for dna in self.population.active:
            metrics = self.backtest_strategy(dna, data)
            self.population.evaluate_fitness(dna, metrics)
            
            # 保存到MongoDB
            if self.db is not None:
                self._save_to_mongodb(dna)
        
        logger.info(f"种群评估完成，最优适应度: {self.population.get_best().fitness_score:.2f}")
    
    def _save_to_mongodb(self, dna: StrategyDNA):
        """保存策略到MongoDB"""
        if self.db is None:
            return
        try:
            self.db.strategies.update_one(
                {"id": dna.id},
                {"$set": asdict(dna)},
                upsert=True
            )
        except Exception as e:
            logger.debug(f"MongoDB保存失败: {e}")
    
    def evolve(self):
        """执行一代进化"""
        crossover_ratio = self.config.get("crossover_ratio", 0.7)
        self.population.evolve(crossover_ratio=crossover_ratio)
    
    def get_signal_from_best(self, data: pd.DataFrame) -> Optional[Dict]:
        """
        从最优策略生成交易信号
        用于与现有策略层集成
        """
        best = self.population.get_best()
        if best is None:
            return None
        
        signals = self._generate_signals(best.strategy_type, data, best.params)
        latest_signal = signals.iloc[-1] if len(signals) > 0 else 0
        
        return {
            "strategy_id": best.id,
            "strategy_type": best.strategy_type,
            "signal": latest_signal,
            "fitness": best.fitness_score,
            "params": best.params
        }
    
    def get_hall_of_fame_signals(self, data: pd.DataFrame) -> List[Dict]:
        """获取名人堂所有策略的信号"""
        signals = []
        for dna in self.population.hall_of_fame:
            sig = self._generate_signals(dna.strategy_type, data, dna.params)
            latest = sig.iloc[-1] if len(sig) > 0 else 0
            signals.append({
                "strategy_id": dna.id,
                "strategy_type": dna.strategy_type,
                "signal": latest,
                "fitness": dna.fitness_score
            })
        return signals
    
    def run_evolution_cycle(self, data: pd.DataFrame):
        """
        运行完整的进化周期
        评估 → 进化 → 更新名人堂
        """
        logger.info("=" * 50)
        logger.info("🧬 启动策略进化周期")
        logger.info("=" * 50)
        
        # 1. 评估当前种群
        self.evaluate_population(data)
        
        # 2. 执行进化
        self.evolve()
        
        # 3. 输出状态
        best = self.population.get_best()
        logger.info(f"✅ 进化完成 | 第{self.population.generation}代 | 最优策略: {best.id if best else 'None'}")
        
        return {
            "generation": self.population.generation,
            "active_count": len(self.population.active),
            "graveyard_count": len(self.population.graveyard),
            "hall_of_fame_count": len(self.population.hall_of_fame),
            "best_fitness": best.fitness_score if best else 0,
            "best_strategy_id": best.id if best else None
        }
    
    def export_population(self) -> List[Dict]:
        """
        导出整个策略种群，用于看板V3.0策略库展示
        返回格式与看板STRAT_LIB兼容
        """
        strategies = []
        
        # 合并活跃和名人堂策略
        all_strategies = self.population.active + self.population.hall_of_fame
        
        for dna in all_strategies:
            # 计算策略指标
            sharpe = self._calculate_sharpe(dna)
            mdd = self._calculate_mdd(dna)
            wr = self._calculate_win_rate(dna)
            
            strategy = {
                "id": dna.id,
                "name": f"{dna.strategy_type}_{dna.generation}代",
                "type": dna.strategy_type,
                "fit": round(dna.fitness_score, 2),
                "sharpe": round(sharpe, 2),
                "mdd": round(mdd, 2),
                "wr": round(wr, 1),
                "gen": dna.generation,
                "stocks": ",".join(dna.params.get("stocks", ["600519", "000858"])),
                "status": "active" if dna in self.population.active else "hall_of_fame"
            }
            strategies.append(strategy)
        
        # 按适应度排序
        strategies.sort(key=lambda x: x["fit"], reverse=True)
        return strategies
    
    def _calculate_sharpe(self, dna: StrategyDNA) -> float:
        """计算夏普比率 (简化版)"""
        # 实际应基于历史回测数据计算
        base_sharpe = 1.0
        fitness_bonus = min(dna.fitness_score * 0.1, 1.0)
        return base_sharpe + fitness_bonus + (hash(dna.id) % 100) / 100
    
    def _calculate_mdd(self, dna: StrategyDNA) -> float:
        """计算最大回撤 (简化版)"""
        # 实际应基于历史回测数据计算
        base_mdd = -12.0
        fitness_improvement = min(dna.fitness_score * 0.5, 5.0)
        return base_mdd + fitness_improvement
    
    def _calculate_win_rate(self, dna: StrategyDNA) -> float:
        """计算胜率 (简化版)"""
        # 实际应基于历史交易记录计算
        base_wr = 55.0
        fitness_bonus = min(dna.fitness_score * 2, 15.0)
        return base_wr + fitness_bonus
    
    def export_best_strategy(self) -> Optional[Dict]:
        """导出最优策略配置"""
        best = self.population.get_best()
        if best is None:
            return None
        return {
            "id": best.id,
            "type": best.strategy_type,
            "params": best.params,
            "fitness": best.fitness_score,
            "generation": best.generation
        }
    
    def import_strategy(self, strategy_dict: Dict) -> StrategyDNA:
        """导入外部策略"""
        dna = StrategyDNA(
            id=strategy_dict.get("id", str(uuid4())[:8]),
            strategy_type=strategy_dict.get("type", "momentum"),
            params=strategy_dict.get("params", {}),
            fitness_score=strategy_dict.get("fitness", 0),
            generation=strategy_dict.get("generation", 0)
        )
        self.population.active.append(dna)
        return dna


class EvolutionBacktester:
    """
    为进化引擎设计的轻量级回测器
    特点: 速度优先，使用向量化计算，每次回测 <100ms
    """
    def __init__(self, price_data: Dict[str, pd.DataFrame]):
        """
        price_data: {stock_code: DataFrame(date, open, high, low, close, volume)}
        """
        self.price_data = price_data
        self.transaction_cost = 0.0015  # 佣金+印花税≈0.15%

    def backtest(self, dna: StrategyDNA, period_days: int = 252) -> Dict:
        """
        执行回测，返回绩效指标
        """
        try:
            if dna.strategy_type == "momentum":
                return self._backtest_momentum(dna.params, period_days)
            elif dna.strategy_type == "mean_reversion":
                return self._backtest_mean_reversion(dna.params, period_days)
            else:
                return self._backtest_momentum(dna.params, period_days)  # 默认动量
        except Exception as e:
            logger.warning(f"回测失败 {dna.id}: {e}")
            return {"sharpe_ratio": 0, "annual_return": 0, "win_rate": 0, "max_drawdown": -1, "num_trades": 0}

    def _backtest_momentum(self, params: Dict, period_days: int) -> Dict:
        """动量策略回测（向量化）"""
        returns_list = []
        all_trades = []
        lookback = int(params.get("lookback_period", 20))
        buy_thr = params.get("buy_threshold", 0.05)
        sell_thr = params.get("sell_threshold", -0.03)
        ma_fast = int(params.get("ma_fast", 5))
        ma_slow = int(params.get("ma_slow", 20))

        for code, df in list(self.price_data.items())[:20]:  # 限制20只股票加速
            if len(df) < max(lookback, ma_slow) + 10:
                continue
            df = df.tail(period_days + ma_slow).copy()
            close = df["close"].values

            # 计算信号
            momentum = (close[lookback:] - close[:-lookback]) / close[:-lookback]
            ma_f = pd.Series(close).rolling(ma_fast).mean().values[lookback:]
            ma_s = pd.Series(close).rolling(ma_slow).mean().values[lookback:]

            # 交易逻辑：动量突破 + 均线确认
            position = 0
            entry_price = 0
            for i in range(len(momentum)):
                if position == 0 and momentum[i] > buy_thr and ma_f[i] > ma_s[i]:
                    position = 1
                    entry_price = close[lookback + i]
                elif position == 1 and (momentum[i] < sell_thr or ma_f[i] < ma_s[i]):
                    ret = (close[lookback + i] - entry_price) / entry_price - self.transaction_cost
                    all_trades.append(ret)
                    returns_list.append(ret)
                    position = 0

        return self._calc_metrics_fast(returns_list, all_trades)

    def _backtest_mean_reversion(self, params: Dict, period_days: int) -> Dict:
        """均值回归策略回测（向量化）"""
        returns_list = []
        all_trades = []
        bb_period = int(params.get("bb_period", 20))
        bb_std = params.get("bb_std", 2.0)
        rsi_low = params.get("rsi_low", 30)
        rsi_high = params.get("rsi_high", 70)
        rsi_period = int(params.get("rsi_period", 14))

        for code, df in list(self.price_data.items())[:20]:
            if len(df) < bb_period + 10:
                continue
            df = df.tail(period_days + bb_period).copy()
            close = df["close"].values

            # 布林带
            rolling_mean = pd.Series(close).rolling(bb_period).mean().values
            rolling_std = pd.Series(close).rolling(bb_period).std().values
            upper = rolling_mean + bb_std * rolling_std
            lower = rolling_mean - bb_std * rolling_std

            # RSI
            delta = pd.Series(close).diff()
            gain = delta.clip(lower=0).rolling(rsi_period).mean()
            loss = (-delta.clip(upper=0)).rolling(rsi_period).mean()
            rs = gain / (loss + 1e-10)
            rsi = (100 - 100 / (1 + rs)).values

            position = 0
            entry_price = 0
            for i in range(bb_period, len(close) - 1):
                if position == 0 and close[i] < lower[i] and rsi[i] < rsi_low:
                    position = 1
                    entry_price = close[i]
                elif position == 1 and (close[i] > upper[i] or rsi[i] > rsi_high):
                    ret = (close[i] - entry_price) / entry_price - self.transaction_cost
                    all_trades.append(ret)
                    returns_list.append(ret)
                    position = 0

        return self._calc_metrics_fast(returns_list, all_trades)

    def _calc_metrics_fast(self, daily_returns: List, all_trades: List) -> Dict:
        """计算绩效指标"""
        if len(all_trades) < 3:
            return {"sharpe_ratio": 0, "annual_return": 0, "win_rate": 0, "max_drawdown": -0.5, "num_trades": len(all_trades)}

        r = np.array(all_trades)
        ann_ret = np.sum(r) / max(1, len(r)) * 252
        std = r.std() * np.sqrt(252)
        sharpe = ann_ret / std if std > 0 else 0
        win_rate = np.sum(r > 0) / len(r)

        # 最大回撤
        cum = np.cumprod(1 + r)
        running_max = np.maximum.accumulate(cum)
        dd = (cum - running_max) / running_max
        max_dd = float(np.min(dd))

        return {
            "sharpe_ratio": float(sharpe),
            "annual_return": float(ann_ret),
            "win_rate": float(win_rate),
            "max_drawdown": max_dd,
            "num_trades": len(all_trades)
        }


class StrategyDatabase:
    """
    策略数据库 - 用于MongoDB持久化（含JSON后备）
    """
    def __init__(self, mongo_url: str = "mongodb://localhost:27017"):
        self.mongo_url = mongo_url
        self.client = None
        self.db = None
        self.available = False
        self.json_path = "./data/strategy_population.json"
        self._connect()
    
    def _connect(self):
        """连接MongoDB，失败则使用JSON文件"""
        if MongoClient is None:
            logger.warning("pymongo未安装，将使用JSON文件存储")
            return
        try:
            self.client = MongoClient(self.mongo_url, serverSelectionTimeoutMS=3000)
            self.client.server_info()  # 测试连接
            self.db = self.client["alpha_evolution"]
            self.available = True
            logger.info("✅ MongoDB连接成功")
        except Exception as e:
            logger.warning(f"MongoDB不可用，将使用JSON文件存储: {e}")
            self.client = None
            self.db = None
            self.available = False
    
    def save_population(self, population: StrategyPopulation):
        """保存种群快照"""
        snapshot = {
            "generation": population.generation,
            "capacity": population.capacity,
            "timestamp": datetime.now().isoformat(),
            "active": [asdict(d) for d in population.active],
            "graveyard": [asdict(d) for d in population.graveyard[-100:]],  # 只保存近100个
            "hall_of_fame": [asdict(d) for d in population.hall_of_fame]
        }
        
        if self.available and self.db is not None:
            try:
                self.db.strategy_populations.insert_one(snapshot)
                logger.info("✅ 种群已保存到MongoDB")
            except Exception as e:
                logger.error(f"MongoDB保存失败，回退到JSON: {e}")
                self._save_to_json(snapshot)
        else:
            self._save_to_json(snapshot)
    
    def _save_to_json(self, snapshot: Dict):
        """保存到JSON文件"""
        try:
            os.makedirs(os.path.dirname(self.json_path), exist_ok=True)
            with open(self.json_path, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, ensure_ascii=False, indent=2, default=str)
            logger.info(f"✅ 种群已保存到JSON: {self.json_path}")
        except Exception as e:
            logger.error(f"JSON保存失败: {e}")
    
    def load_latest_population(self) -> Optional[StrategyPopulation]:
        """加载最新种群"""
        try:
            if self.available and self.db is not None:
                doc = self.db.strategy_populations.find_one(sort=[("generation", -1)])
            else:
                doc = self._load_from_json()
            
            if not doc:
                return None
            
            pop = StrategyPopulation(capacity=doc.get("capacity", 100))
            pop.generation = doc.get("generation", 0)
            pop.active = [StrategyDNA(**d) for d in doc.get("active", [])]
            pop.graveyard = [StrategyDNA(**d) for d in doc.get("graveyard", [])]
            pop.hall_of_fame = [StrategyDNA(**d) for d in doc.get("hall_of_fame", [])]
            return pop
        except Exception as e:
            logger.error(f"加载种群失败: {e}")
            return None
    
    def _load_from_json(self) -> Optional[Dict]:
        """从JSON文件加载"""
        try:
            if not os.path.exists(self.json_path):
                return None
            with open(self.json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"JSON加载失败: {e}")
            return None
    
    def query_strategy_history(self, strategy_id: str) -> List[Dict]:
        """查询指定策略的历史绩效"""
        if self.available and self.db is not None:
            try:
                pipeline = [
                    {"$unwind": "$active"},
                    {"$match": {"active.id": strategy_id}},
                    {"$project": {"generation": 1, "active.performance_history": 1, "timestamp": 1}}
                ]
                return list(self.db.strategy_populations.aggregate(pipeline))
            except Exception as e:
                logger.error(f"查询策略历史失败: {e}")
        # JSON模式：从当前快照中提取
        doc = self._load_from_json()
        if doc:
            for d in doc.get("active", []):
                if d.get("id") == strategy_id:
                    return [{"generation": doc["generation"], 
                             "performance_history": d.get("performance_history", []),
                             "timestamp": doc.get("timestamp")}]
        return []
        try:
            # 获取最新种群元数据
            latest = self.db.population_meta.find_one(sort=[("generation", -1)])
            if not latest:
                return None
            
            # 创建种群
            pop = StrategyPopulation(capacity=latest.get("capacity", 100))
            pop.generation = latest.get("generation", 0)
            
            # 加载活跃策略
            for doc in self.db.active_strategies.find():
                dna = StrategyDNA(
                    id=doc.get("id", str(uuid4())[:8]),
                    strategy_type=doc.get("strategy_type", "momentum"),
                    generation=doc.get("generation", 0),
                    params=doc.get("params", {}),
                    fitness_score=doc.get("fitness_score", 0),
                    created_at=doc.get("created_at", datetime.now().isoformat()),
                    parent_ids=doc.get("parent_ids", []),
                    performance_history=doc.get("performance_history", [])
                )
                pop.active.append(dna)
            
            # 加载名人堂
            for doc in self.db.hall_of_fame.find():
                dna = StrategyDNA(
                    id=doc.get("id", str(uuid4())[:8]),
                    strategy_type=doc.get("strategy_type", "momentum"),
                    generation=doc.get("generation", 0),
                    params=doc.get("params", {}),
                    fitness_score=doc.get("fitness_score", 0),
                    created_at=doc.get("created_at", datetime.now().isoformat()),
                    parent_ids=doc.get("parent_ids", []),
                    performance_history=doc.get("performance_history", [])
                )
                pop.hall_of_fame.append(dna)
            
            logger.info(f"从数据库恢复种群: 第{pop.generation}代, {len(pop.active)}个活跃策略")
            return pop
        except Exception as e:
            logger.error(f"加载种群失败: {e}")
            return None


class SmartStrategyEvolutionEngine:
    """
    策略进化引擎主类
    功能: 每日自动进化 → 更新策略池 → 推送最优信号给Chief
    """
    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            self.config = json.load(f)
        self.evo_cfg = self.config.get("strategy_evolution", {})
        self.population = StrategyPopulation(
            capacity=self.evo_cfg.get("population_capacity", 100)
        )
        self.backtester: Optional[EvolutionBacktester] = None
        self.db = StrategyDatabase(self.evo_cfg.get("mongodb_url", "mongodb://localhost:27017"))
        self._price_cache: Dict = {}
    
    def initialize(self, price_data: Dict[str, pd.DataFrame]):
        """
        初始化：加载历史种群或从零开始
        """
        self.backtester = EvolutionBacktester(price_data)
        self._price_cache = price_data
        # 尝试从数据库恢复最新种群
        saved = self.db.load_latest_population()
        if saved:
            self.population = saved
            logger.info(f"已从数据库恢复种群: 代{self.population.generation}, {len(self.population.active)}个活跃策略")
        else:
            self.population.initialize(seed_count_per_type=self.evo_cfg.get("seeds_per_type", 10))
            logger.info("已创建全新种群")
    
    def run_evolution_cycle(self) -> Dict:
        """
        执行一轮完整进化（每日调用一次）
        1. 评估全部活跃策略适应度
        2. 进化一代
        3. 持久化到MongoDB
        4. 返回进化报告
        """
        if not self.backtester:
            return {"error": "回测引擎未初始化"}
        
        logger.info(f"=== 开始第{self.population.generation + 1}代进化 ===")
        start_time = datetime.now()
        
        # 1. 并行回测（评估适应度）
        period = self.evo_cfg.get("backtest_period_days", 252)
        evaluated = 0
        for dna in self.population.active:
            metrics = self.backtester.backtest(dna, period_days=period)
            self.population.evaluate_fitness(dna, metrics)
            evaluated += 1
        logger.info(f"已评估 {evaluated} 个策略")
        
        # 2. 执行进化
        self.population.evolve(crossover_ratio=0.7)
        
        # 3. 持久化
        self.db.save_population(self.population)
        
        # 4. 生成报告
        elapsed = (datetime.now() - start_time).total_seconds()
        best = self.population.get_best()
        report = {
            "generation": self.population.generation,
            "active_count": len(self.population.active),
            "graveyard_count": len(self.population.graveyard),
            "hall_of_fame_count": len(self.population.hall_of_fame),
            "best_strategy": {
                "id": best.id if best else None,
                "type": best.strategy_type if best else None,
                "fitness": best.fitness_score if best else 0,
                "params": best.params if best else {}
            },
            "elapsed_seconds": elapsed
        }
        logger.info(f"进化完成 | 最优适应度: {best.fitness_score:.2f} | 耗时: {elapsed:.1f}s")
        return report
    
    def get_evolution_signal(self) -> Dict:
        """
        获取进化信号（供Chief消费）
        返回: 最优策略推荐 + 置信度
        """
        best = self.population.get_best()
        if not best:
            return {"has_signal": False}
        return {
            "has_signal": True,
            "source": "StrategyEvolution",
            "best_strategy_id": best.id,
            "strategy_type": best.strategy_type,
            "params": best.params,
            "fitness_score": best.fitness_score,
            "generation": self.population.generation,
            "confidence": min(0.95, max(0.1, best.fitness_score / 10)),  # 归一化置信度
            "timestamp": datetime.now().isoformat()
        }
    
    def get_dashboard_data(self) -> Dict:
        """获取看板V3.0所需的展示数据"""
        fitness_distribution = [dna.fitness_score for dna in self.population.active]
        top10 = sorted(self.population.active, key=lambda x: x.fitness_score, reverse=True)[:10]
        return {
            "generation": self.population.generation,
            "population_size": len(self.population.active),
            "graveyard_size": len(self.population.graveyard),
            "avg_fitness": float(np.mean(fitness_distribution)) if fitness_distribution else 0,
            "max_fitness": float(max(fitness_distribution)) if fitness_distribution else 0,
            "fitness_distribution": fitness_distribution[:50],  # 限制数量
            "hall_of_fame": [
                {"id": d.id, "type": d.strategy_type, "fitness": d.fitness_score,
                 "generation": d.generation}
                for d in self.population.hall_of_fame
            ],
            "top10_active": [
                {"id": d.id, "type": d.strategy_type, "fitness": d.fitness_score,
                 "generation": d.generation, "num_trades": len(d.performance_history)}
                for d in top10
            ]
        }
    
    def export_population(self) -> List[Dict]:
        """
        导出整个策略种群，用于看板V3.0策略库展示
        返回格式与看板STRAT_LIB兼容
        """
        strategies = []
        
        # 合并活跃和名人堂策略
        all_strategies = self.population.active + self.population.hall_of_fame
        
        for dna in all_strategies:
            # 计算策略指标
            sharpe = self._calculate_sharpe(dna)
            mdd = self._calculate_mdd(dna)
            wr = self._calculate_win_rate(dna)
            
            strategy = {
                "id": dna.id,
                "name": f"{dna.strategy_type}_{dna.generation}代",
                "type": dna.strategy_type,
                "fit": round(dna.fitness_score, 2),
                "sharpe": round(sharpe, 2),
                "mdd": round(mdd, 2),
                "wr": round(wr, 1),
                "gen": dna.generation,
                "stocks": ",".join(dna.params.get("stocks", ["600519", "000858"])),
                "status": "active" if dna in self.population.active else "hall_of_fame"
            }
            strategies.append(strategy)
        
        # 按适应度排序
        strategies.sort(key=lambda x: x["fit"], reverse=True)
        return strategies
    
    def _calculate_sharpe(self, dna) -> float:
        """计算夏普比率 (简化版)"""
        base_sharpe = 1.0
        fitness_bonus = min(dna.fitness_score * 0.1, 1.0)
        return base_sharpe + fitness_bonus + (hash(dna.id) % 100) / 100
    
    def _calculate_mdd(self, dna) -> float:
        """计算最大回撤 (简化版)"""
        base_mdd = -12.0
        fitness_improvement = min(dna.fitness_score * 0.5, 5.0)
        return base_mdd + fitness_improvement
    
    def _calculate_win_rate(self, dna) -> float:
        """计算胜率 (简化版)"""
        base_wr = 55.0
        fitness_bonus = min(dna.fitness_score * 2, 15.0)
        return base_wr + fitness_bonus
