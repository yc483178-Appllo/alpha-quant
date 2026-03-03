#!/usr/bin/env python3
"""
Alpha-Picker: 量化选股师
负责多策略选股和信号生成
"""

import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime
from loguru import logger
from core.agent_bus import AgentBus
from core.adaptive_strategy import AdaptiveStrategySelector
from core.multi_timeframe import MultiTimeframeStrategy
from core.ml_factor_engine import MLFactorEngine

class AlphaPicker:
    """量化选股师 - 团队的'大脑'"""
    
    STRATEGIES = ["momentum", "trend", "value", "reversal", "composite"]
    
    def __init__(self):
        self.bus = AgentBus()
        self.adaptive = AdaptiveStrategySelector()
        self.mtf = MultiTimeframeStrategy()
        self.ml_engine = MLFactorEngine()
        
    def screen_stocks(self):
        """多策略选股 - 09:10执行"""
        logger.info("[Picker] 启动多策略选股引擎")
        
        # 1. 获取市场环境
        market_regime = self.adaptive.select()
        logger.info(f"[Picker] 当前市场: {market_regime['regime']}")
        
        # 2. 获取全市场数据
        try:
            all_stocks = ak.stock_zh_a_spot_em()
            # 过滤ST和退市股
            all_stocks = all_stocks[~all_stocks["名称"].str.contains("ST|退", na=False)]
            # 过滤科创板（流动性考虑）
            all_stocks = all_stocks[~all_stocks["代码"].str.startswith("688", na=False)]
        except Exception as e:
            logger.error(f"[Picker] 获取股票列表失败: {e}")
            return []
        
        # 3. 运行各策略选股
        candidates = {}
        
        # 动量策略
        momentum_picks = self._momentum_strategy(all_stocks)
        candidates["momentum"] = momentum_picks
        
        # 趋势策略
        trend_picks = self._trend_strategy(all_stocks)
        candidates["trend"] = trend_picks
        
        # 价值策略
        value_picks = self._value_strategy(all_stocks)
        candidates["value"] = value_picks
        
        # 4. 综合评分
        final_signals = self._aggregate_signals(candidates, market_regime)
        
        # 5. 发送强信号给Chief
        for signal in final_signals:
            if signal["signal_strength"] in ["strong", "medium"]:
                self.bus.picker_signal(signal)
        
        logger.info(f"[Picker] 选股完成，发送 {len([s for s in final_signals if s['signal_strength'] in ['strong', 'medium']])} 个信号")
        return final_signals
    
    def _momentum_strategy(self, df):
        """动量策略：近期强势+放量"""
        try:
            # 条件：涨幅3-8%（避免涨停追高风险），量比>1.5，换手率3-15%
            filtered = df[
                (df["涨跌幅"].astype(float) > 3) &
                (df["涨跌幅"].astype(float) < 8) &
                (df["量比"].astype(float) > 1.5) &
                (df["换手率"].astype(float) > 3) &
                (df["换手率"].astype(float) < 15)
            ]
            
            # 按涨跌幅排序
            filtered = filtered.sort_values("涨跌幅", ascending=False)
            return filtered.head(20)["代码"].tolist()
        except Exception as e:
            logger.error(f"[Picker] 动量策略失败: {e}")
            return []
    
    def _trend_strategy(self, df):
        """趋势策略：均线多头排列"""
        # 简化版：基于当日强势判断
        try:
            filtered = df[
                (df["涨跌幅"].astype(float) > 2) &
                (df["最新价"].astype(float) > df["今开"].astype(float))
            ]
            return filtered.head(15)["代码"].tolist()
        except Exception as e:
            logger.error(f"[Picker] 趋势策略失败: {e}")
            return []
    
    def _value_strategy(self, df):
        """价值策略：低PE+低PB"""
        try:
            # 过滤PE和PB有效的股票
            df["PE"] = pd.to_numeric(df.get("市盈率-动态", 0), errors="coerce")
            df["PB"] = pd.to_numeric(df.get("市净率", 0), errors="coerce")
            
            filtered = df[
                (df["PE"] > 0) & (df["PE"] < 20) &
                (df["PB"] > 0) & (df["PB"] < 2)
            ]
            return filtered.head(10)["代码"].tolist()
        except Exception as e:
            logger.error(f"[Picker] 价值策略失败: {e}")
            return []
    
    def _aggregate_signals(self, candidates, market_regime):
        """综合各策略信号"""
        # 统计每只股票被多少策略选中
        from collections import Counter
        all_picks = []
        for strategy, picks in candidates.items():
            for code in picks:
                all_picks.append((code, strategy))
        
        code_counter = Counter([code for code, _ in all_picks])
        code_strategies = {}
        for code, strategy in all_picks:
            if code not in code_strategies:
                code_strategies[code] = []
            code_strategies[code].append(strategy)
        
        # 生成信号
        signals = []
        for code, count in code_counter.most_common(10):
            if count >= 3:
                strength = "strong"
            elif count == 2:
                strength = "medium"
            else:
                strength = "weak"
            
            # 获取股票名称
            try:
                df = ak.stock_zh_a_spot_em()
                name = df[df["代码"] == code]["名称"].values[0] if not df[df["代码"] == code].empty else ""
            except:
                name = ""
            
            signals.append({
                "signal_id": f"PICKER-{datetime.now().strftime('%Y%m%d')}-{code}",
                "code": code,
                "name": name,
                "action": "buy",
                "strategies_agreed": code_strategies[code],
                "signal_strength": strength,
                "score": min(count / 5, 1.0),
                "timestamp": datetime.now().isoformat()
            })
        
        return signals

if __name__ == "__main__":
    picker = AlphaPicker()
    picker.screen_stocks()
