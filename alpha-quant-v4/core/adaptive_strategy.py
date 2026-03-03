# adaptive_strategy.py --- 自适应策略切换器
# 根据市场环境自动选择最优策略组合

import akshare as ak
import pandas as pd
import numpy as np
from loguru import logger
from datetime import datetime, timedelta

class MarketRegimeDetector:
    """市场环境识别器 — 判断当前处于牛市/熊市/震荡"""

    def detect(self):
        """
        基于多维度指标判断市场环境
        返回: "bull" / "bear" / "oscillation"
        """
        scores = {}

        # 维度1: 指数趋势（MA20 vs MA60）
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            df["close"] = df["close"].astype(float)
            ma20 = df["close"].tail(20).mean()
            ma60 = df["close"].tail(60).mean()
            current = float(df["close"].iloc[-1])

            if current > ma20 > ma60:
                scores["trend"] = 1  # 多头排列
            elif current < ma20 < ma60:
                scores["trend"] = -1  # 空头排列
            else:
                scores["trend"] = 0  # 纠缠
        except Exception as e:
            logger.error(f"指数趋势判断失败: {e}")
            scores["trend"] = 0

        # 维度2: 涨跌比
        try:
            df = ak.stock_zh_a_spot_em()
            ups = len(df[df["涨跌幅"] > 0])
            downs = len(df[df["涨跌幅"] < 0])
            ratio = ups / max(downs, 1)

            if ratio > 2:
                scores["breadth"] = 1
            elif ratio < 0.5:
                scores["breadth"] = -1
            else:
                scores["breadth"] = 0
        except:
            scores["breadth"] = 0

        # 维度3: 北向资金趋势
        try:
            nf = ak.stock_hsgt_north_net_flow_in_em(symbol="沪深港通")
            recent_5d = nf["值"].tail(5).astype(float).sum()

            if recent_5d > 100:
                scores["northflow"] = 1
            elif recent_5d < -100:
                scores["northflow"] = -1
            else:
                scores["northflow"] = 0
        except:
            scores["northflow"] = 0

        # 维度4: 波动率
        try:
            df = ak.stock_zh_index_daily(symbol="sh000001")
            returns = df["close"].astype(float).pct_change().tail(20)
            vol = returns.std() * np.sqrt(252)

            if vol > 0.25:
                scores["volatility"] = -1  # 高波动偏熊
            elif vol < 0.12:
                scores["volatility"] = 1   # 低波动偏牛
            else:
                scores["volatility"] = 0
        except:
            scores["volatility"] = 0

        # 综合评分
        total = sum(scores.values())
        if total >= 2:
            regime = "bull"
        elif total <= -2:
            regime = "bear"
        else:
            regime = "oscillation"

        logger.info(f"市场环境判断: {regime} (评分: {scores}, 总分: {total})")
        return regime, scores

class AdaptiveStrategySelector:
    """自适应策略选择器"""

    STRATEGY_MAP = {
        "bull": {
            "primary": "momentum",
            "secondary": "trend",
            "weight": {"momentum": 0.5, "trend": 0.3, "composite": 0.2},
            "position_limit": 0.80,
            "description": "牛市模式：偏进攻，动量+趋势为主"
        },
        "bear": {
            "primary": "value",
            "secondary": "reversal",
            "weight": {"value": 0.5, "reversal": 0.3, "composite": 0.2},
            "position_limit": 0.40,
            "description": "熊市模式：偏防守，价值+超跌为主，降低仓位"
        },
        "oscillation": {
            "primary": "composite",
            "secondary": "value",
            "weight": {"composite": 0.4, "value": 0.3, "momentum": 0.3},
            "position_limit": 0.60,
            "description": "震荡模式：均衡配置，综合策略为主"
        }
    }

    def __init__(self):
        self.detector = MarketRegimeDetector()

    def select(self):
        """根据当前市场环境选择策略组合"""
        regime, scores = self.detector.detect()
        config = self.STRATEGY_MAP[regime]

        logger.info(f"策略选择: {config['description']}")
        return {
            "regime": regime,
            "scores": scores,
            "config": config,
            "selected_at": datetime.now().isoformat()
        }

if __name__ == "__main__":
    selector = AdaptiveStrategySelector()
    result = selector.select()
    print(f"\n当前市场: {result['regime']}")
    print(f"策略配置: {result['config']['description']}")
    print(f"策略权重: {result['config']['weight']}")
    print(f"仓位上限: {result['config']['position_limit']:.0%}")
