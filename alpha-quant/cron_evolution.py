"""
策略进化引擎定时任务 - V6.0
每日 09:00（开盘前）自动运行策略进化

功能:
1. 执行策略种群进化 (run_evolution_cycle)
2. 获取最优策略信号 (get_evolution_signal)
3. 通过Redis通道 "signal:evolution" 发布给Chief Agent
4. 更新看板V3.0 "策略进化"面板数据
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import logging
from datetime import datetime
from typing import Dict, Optional

import akshare as ak
import pandas as pd
import numpy as np

# 尝试导入Redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logging.warning("redis未安装，信号发布功能将不可用")

from evolution_integration import AlphaV6Integration
from strategy_evolution_engine import SmartStrategyEvolutionEngine

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("EvolutionCron")


class EvolutionCronTask:
    """策略进化定时任务类"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.redis_client = None
        self._init_redis()
        
    def _load_config(self) -> dict:
        """加载配置"""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"配置加载失败: {e}")
            return {}
    
    def _init_redis(self):
        """初始化Redis连接"""
        if not REDIS_AVAILABLE:
            return
        try:
            cache_config = self.config.get("cache", {})
            redis_url = cache_config.get("redis_url", "redis://127.0.0.1:6379/0")
            self.redis_client = redis.from_url(redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("✅ Redis连接成功")
        except Exception as e:
            logger.warning(f"Redis连接失败: {e}")
            self.redis_client = None
    
    def get_price_data_for_backtest(self) -> dict:
        """获取价格数据用于进化回测"""
        price_data = {}
        
        try:
            # 获取沪深300成分股作为样本
            logger.info("获取沪深300成分股数据...")
            stocks = ak.index_stock_cons_weight_csindex(symbol="000300")
            stock_codes = stocks['成分券代码'].tolist()[:30]  # 取前30只加速
            
            for code in stock_codes:
                try:
                    # 获取历史数据
                    df = ak.stock_zh_a_hist(symbol=code, period="daily", adjust="qfq")
                    if len(df) > 60:  # 至少60天数据
                        price_data[code] = df.rename(columns={
                            '日期': 'date',
                            '开盘': 'open',
                            '收盘': 'close',
                            '最高': 'high',
                            '最低': 'low',
                            '成交量': 'volume'
                        })
                except Exception as e:
                    logger.debug(f"获取 {code} 数据失败: {e}")
                    continue
            
            logger.info(f"成功获取 {len(price_data)} 只股票数据")
            
        except Exception as e:
            logger.error(f"数据获取失败: {e}")
            # 创建模拟数据作为后备
            price_data = self._create_mock_price_data()
        
        return price_data
    
    def _create_mock_price_data(self) -> dict:
        """创建模拟价格数据"""
        price_data = {}
        for i in range(20):
            code = f"{600000 + i:06d}"
            dates = pd.date_range(end=datetime.now(), periods=300, freq="D")
            price_data[code] = pd.DataFrame({
                'date': dates,
                'open': 100 + np.cumsum(np.random.randn(300) * 0.01),
                'close': 100 + np.cumsum(np.random.randn(300) * 0.01),
                'high': 100 + np.cumsum(np.random.randn(300) * 0.01) + 0.02,
                'low': 100 + np.cumsum(np.random.randn(300) * 0.01) - 0.02,
                'volume': np.random.randint(1000000, 10000000, 300)
            })
        logger.info(f"使用模拟数据: {len(price_data)}只股票")
        return price_data
    
    def publish_to_redis(self, channel: str, message: dict):
        """发布消息到Redis通道"""
        if self.redis_client is None:
            logger.warning(f"Redis不可用，无法发布到 {channel}")
            return False
        try:
            self.redis_client.publish(channel, json.dumps(message, ensure_ascii=False))
            logger.info(f"✅ 消息已发布到 {channel}")
            return True
        except Exception as e:
            logger.error(f"Redis发布失败: {e}")
            return False
    
    def save_dashboard_data(self, dashboard_data: dict):
        """保存看板数据到Redis"""
        if self.redis_client is None:
            return False
        try:
            self.redis_client.set("dashboard:evolution", json.dumps(dashboard_data, ensure_ascii=False))
            logger.info("✅ 看板数据已更新")
            return True
        except Exception as e:
            logger.error(f"看板数据保存失败: {e}")
            return False
    
    def run(self):
        """
        执行定时任务
        1. 执行策略进化
        2. 获取最优信号
        3. 发布到Redis
        4. 更新看板
        """
        logger.info("=" * 60)
        logger.info("🧬 Alpha V6.0 策略进化引擎定时任务")
        logger.info("=" * 60)
        
        # 1. 获取价格数据
        price_data = self.get_price_data_for_backtest()
        
        # 2. 创建并初始化引擎
        engine = SmartStrategyEvolutionEngine(self.config_path)
        engine.initialize(price_data)
        
        evo_cfg = self.config.get("strategy_evolution", {})
        if not evo_cfg.get("enabled", True):
            logger.info("策略进化已禁用，跳过")
            return {"status": "disabled"}
        
        # 3. 执行进化周期
        logger.info("开始执行进化周期...")
        result = engine.run_evolution_cycle()
        
        logger.info("=" * 60)
        logger.info(f"✅ 第{result['generation']}代进化完成")
        logger.info(f"   活跃策略: {result['active_count']}")
        logger.info(f"   墓地策略: {result['graveyard_count']}")
        logger.info(f"   名人堂: {result['hall_of_fame_count']}")
        logger.info(f"   最优适应度: {result['best_strategy']['fitness']:.2f}")
        logger.info(f"   耗时: {result['elapsed_seconds']:.1f}s")
        logger.info("=" * 60)
        
        # 4. 获取进化信号
        signal = engine.get_evolution_signal()
        if signal.get("has_signal"):
            logger.info(f"📊 最优策略信号: {signal['best_strategy_id']} ({signal['strategy_type']})")
            logger.info(f"   适应度: {signal['fitness_score']:.2f}, 置信度: {signal['confidence']:.2f}")
            
            # 5. 发布到Redis
            self.publish_to_redis("signal:evolution", signal)
            
            # 同时保存到信号队列
            if self.redis_client:
                self.redis_client.lpush("signals:queue", json.dumps(signal, ensure_ascii=False))
        
        # 6. 更新看板数据
        dashboard_data = engine.get_dashboard_data()
        self.save_dashboard_data(dashboard_data)
        logger.info(f"📈 看板数据更新: 平均适应度={dashboard_data['avg_fitness']:.2f}")
        
        return {
            "status": "success",
            "generation": result['generation'],
            "best_fitness": result['best_strategy']['fitness'],
            "signal_published": signal.get("has_signal", False)
        }


def run_daily_evolution():
    """独立运行函数（供外部调用）"""
    task = EvolutionCronTask()
    return task.run()


if __name__ == "__main__":
    run_daily_evolution()
