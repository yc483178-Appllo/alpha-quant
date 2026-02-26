"""
模块二：智能优选股筛选（增强版 · 多策略）
多策略选股引擎：动量突破、价值低估、趋势跟踪、超跌反弹、综合多因子
"""
import akshare as ak
import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime
from modules.config_manager import config_manager
from modules.logger import log

class StockScreenerEnhanced:
    """增强版选股器"""
    
    def __init__(self):
        self.strategies = {
            "momentum": "动量突破（适合强势行情）",
            "value": "价值低估（适合震荡/弱势行情）",
            "trend": "趋势跟踪（适合单边行情）",
            "reversal": "超跌反弹（适合恐慌修复期）",
            "composite": "综合多因子（默认推荐）"
        }
    
    def _get_base_data(self) -> pd.DataFrame:
        """获取基础数据"""
        log.info("📊 获取全市场股票数据")
        try:
            df = ak.stock_zh_a_spot_em()
            return df
        except Exception as e:
            log.error(f"获取股票数据失败: {e}")
            return pd.DataFrame()
    
    def _base_filter(self, df: pd.DataFrame) -> pd.DataFrame:
        """基础过滤（硬性条件）"""
        initial_count = len(df)
        
        # 排除科创板、ST股、极端价格
        df = df[
            (~df["代码"].str.startswith("688")) &    # 排除科创板
            (~df["名称"].str.contains("ST|退", na=False)) &    # 排除ST股
            (df["最新价"] > 2) &                     # 排除低价股
            (df["最新价"] < 200) &                   # 排除超高价股
            (df["总市值"] > 20e8) &                  # 市值 > 20亿
            (df["总市值"] < 2000e8) &                # 市值 < 2000亿
            (df["涨跌幅"] < 9.9) &                   # 排除已涨停
            (df["涨跌幅"] > -9.9)                    # 排除已跌停
        ]
        
        log.info(f"基础过滤: {initial_count} → {len(df)} 只")
        return df
    
    def screen_momentum(self, df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
        """策略一：动量突破（适合强势行情）"""
        log.info("🚀 执行动量突破策略")
        
        df = df[
            (df["涨跌幅"] > 2) &
            (df["换手率"] > 3) & (df["换手率"] < 12) &
            (df["量比"] > 1.5)
        ]
        
        if df.empty:
            return df
        
        df["score"] = (
            df["换手率"].rank(pct=True) * 0.25 +
            df["涨跌幅"].rank(pct=True) * 0.30 +
            df["量比"].rank(pct=True) * 0.25 +
            df["成交额"].rank(pct=True) * 0.20
        )
        
        return df.nlargest(top_n, "score")
    
    def screen_value(self, df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
        """策略二：价值低估（适合震荡/弱势行情）"""
        log.info("💎 执行价值低估策略")
        
        # 确保市盈率、市净率列存在且有效
        if "市盈率-动态" not in df.columns or "市净率" not in df.columns:
            log.warning("缺少估值指标，跳过价值策略")
            return pd.DataFrame()
        
        df = df[
            (df["市盈率-动态"] > 0) & (df["市盈率-动态"] < 25) &
            (df["市净率"] < 2.5) & (df["市净率"] > 0) &
            (df["换手率"] > 1)
        ]
        
        if df.empty:
            return df
        
        df["score"] = (
            (1 / df["市盈率-动态"]).rank(pct=True) * 0.35 +
            (1 / df["市净率"]).rank(pct=True) * 0.30 +
            df["成交额"].rank(pct=True) * 0.20 +
            df["换手率"].rank(pct=True) * 0.15
        )
        
        return df.nlargest(top_n, "score")
    
    def screen_trend(self, df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
        """策略三：趋势跟踪（适合单边行情）"""
        log.info("📈 执行趋势跟踪策略")
        
        df = df[
            (df["涨跌幅"] > 0) & (df["涨跌幅"] < 7) &
            (df["换手率"] > 2) & (df["换手率"] < 8) &
            (df["量比"] > 1.2)
        ]
        
        if df.empty:
            return df
        
        df["score"] = (
            df["涨跌幅"].rank(pct=True) * 0.20 +
            df["换手率"].rank(pct=True) * 0.25 +
            df["量比"].rank(pct=True) * 0.25 +
            df["成交额"].rank(pct=True) * 0.30
        )
        
        return df.nlargest(top_n, "score")
    
    def screen_reversal(self, df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
        """策略四：超跌反弹（适合恐慌后的修复期）"""
        log.info("🔄 执行超跌反弹策略")
        
        df = df[
            (df["涨跌幅"] > 0) & (df["涨跌幅"] < 5) &
            (df["换手率"] > 2) &
            (df["量比"] > 2.0)
        ]
        
        if df.empty:
            return df
        
        df["score"] = (
            df["量比"].rank(pct=True) * 0.35 +
            df["换手率"].rank(pct=True) * 0.30 +
            df["涨跌幅"].rank(pct=True) * 0.15 +
            df["成交额"].rank(pct=True) * 0.20
        )
        
        return df.nlargest(top_n, "score")
    
    def screen_composite(self, df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
        """策略五：综合多因子（默认推荐）"""
        log.info("🎯 执行综合多因子策略")
        
        df = df[
            (df["涨跌幅"] > -2) & (df["涨跌幅"] < 7) &
            (df["换手率"] > 1.5) & (df["换手率"] < 15) &
            (df["量比"] > 1.0)
        ]
        
        if df.empty:
            return df
        
        # 市值适中加分
        df["market_cap_score"] = 1 - abs(df["总市值"].rank(pct=True) - 0.5)
        
        df["score"] = (
            df["换手率"].rank(pct=True) * 0.20 +
            df["涨跌幅"].rank(pct=True) * 0.20 +
            df["量比"].rank(pct=True) * 0.20 +
            df["成交额"].rank(pct=True) * 0.20 +
            df["market_cap_score"] * 0.20
        )
        
        return df.nlargest(top_n, "score")
    
    def screen(self, strategy: str = "composite", top_n: int = 10) -> pd.DataFrame:
        """
        执行选股
        
        参数:
            strategy: 策略类型 (momentum/value/trend/reversal/composite)
            top_n: 返回股票数量
        """
        log.info(f"开始选股 | 策略: {strategy} | 时间: {datetime.now()}")
        
        # 获取基础数据
        df = self._get_base_data()
        if df.empty:
            log.error("获取股票数据失败")
            return pd.DataFrame()
        
        # 基础过滤
        df = self._base_filter(df)
        if df.empty:
            log.warning("基础过滤后无股票")
            return pd.DataFrame()
        
        # 执行策略
        strategy_map = {
            "momentum": self.screen_momentum,
            "value": self.screen_value,
            "trend": self.screen_trend,
            "reversal": self.screen_reversal,
            "composite": self.screen_composite
        }
        
        if strategy not in strategy_map:
            log.error(f"未知策略: {strategy}")
            return pd.DataFrame()
        
        result = strategy_map[strategy](df, top_n)
        
        if result.empty:
            log.warning(f"策略 {strategy} 未筛选到符合条件的股票")
            return pd.DataFrame()
        
        # 格式化输出
        output = result[[
            "代码", "名称", "最新价", "涨跌幅", "换手率", "量比", "总市值", "score"
        ]].copy()
        
        output["策略"] = strategy
        output["筛选时间"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        output["score"] = output["score"].round(4)
        output["总市值"] = (output["总市值"] / 1e8).round(2).astype(str) + "亿"
        
        log.info(f"选股完成 | 策略: {strategy} | 筛选出 {len(output)} 只")
        return output
    
    def screen_all_strategies(self, top_n: int = 5) -> Dict[str, pd.DataFrame]:
        """执行所有策略选股"""
        results = {}
        
        for strategy in self.strategies.keys():
            log.info(f"\n{'='*60}")
            log.info(f"执行策略: {strategy}")
            log.info('='*60)
            
            result = self.screen(strategy, top_n)
            results[strategy] = result
        
        return results

# 全局实例
screener = StockScreenerEnhanced()

if __name__ == "__main__":
    # 测试所有策略
    results = screener.screen_all_strategies(top_n=5)
    
    for strategy, df in results.items():
        print(f"\n{'='*60}")
        print(f"策略: {strategy}")
        print('='*60)
        if not df.empty:
            print(df.to_markdown(index=False))
        else:
            print("未筛选到符合条件的股票")
