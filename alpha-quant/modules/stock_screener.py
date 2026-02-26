"""
选股模块 - 多因子筛选
"""
import pandas as pd
import numpy as np
from typing import List, Dict
from datetime import datetime, timedelta
from modules.data_provider import data_provider
from modules.technical_analysis import technical_analyzer
import config

class StockScreener:
    """股票筛选器"""
    
    # 排除的板块/类型
    EXCLUDE_ST_TYPES = ['ST', '*ST', '退市']
    
    def __init__(self):
        self.data = data_provider
    
    def filter_technical(self, df: pd.DataFrame) -> pd.DataFrame:
        """技术面筛选"""
        if len(df) < 60:
            return pd.DataFrame()
        
        # 计算技术指标
        df = technical_analyzer.calculate_ma(df)
        df = technical_analyzer.calculate_macd(df)
        df = technical_analyzer.calculate_rsi(df)
        
        latest = df.iloc[-1]
        
        # 筛选条件
        conditions = []
        
        # 1. 股价在 MA20 上方（趋势向上）
        conditions.append(latest['close'] > latest['MA20'])
        
        # 2. MA5 > MA10（短期均线金叉）
        conditions.append(latest['MA5'] > latest['MA10'])
        
        # 3. MACD > 0（多头市场）
        conditions.append(latest['MACD'] > 0)
        
        # 4. RSI 在 30-70 之间（非超买超卖）
        conditions.append(30 < latest['RSI'] < 70)
        
        # 5. 成交量放大（今日成交量 > 20日均量）
        df['vol_ma20'] = df['vol'].rolling(window=20).mean()
        conditions.append(latest['vol'] > latest['vol_ma20'])
        
        if all(conditions):
            return df
        return pd.DataFrame()
    
    def calculate_score(self, df: pd.DataFrame) -> Dict:
        """计算股票评分"""
        if len(df) < 20:
            return {"total": 0, "details": {}}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        scores = {
            "trend": 0,      # 趋势得分
            "momentum": 0,   # 动量得分
            "volume": 0,     # 量能得分
            "volatility": 0  # 波动率得分
        }
        
        # 趋势得分 (0-30)
        if latest['close'] > latest['MA5'] > latest['MA10'] > latest['MA20']:
            scores['trend'] = 30
        elif latest['close'] > latest['MA20']:
            scores['trend'] = 20
        elif latest['close'] > latest['MA60']:
            scores['trend'] = 10
        
        # 动量得分 (0-30)
        if latest['MACD'] > latest['MACD_Signal'] > 0:
            scores['momentum'] = 30
        elif latest['MACD'] > 0:
            scores['momentum'] = 20
        elif latest['MACD'] > latest['MACD_Signal']:
            scores['momentum'] = 15
        
        # 量能得分 (0-25)
        vol_ratio = latest['vol'] / latest['vol_ma20'] if 'vol_ma20' in latest else 1
        if vol_ratio > 2:
            scores['volume'] = 25
        elif vol_ratio > 1.5:
            scores['volume'] = 20
        elif vol_ratio > 1:
            scores['volume'] = 15
        
        # 波动率得分 (0-15) - 适中波动较好
        recent_volatility = df['close'].tail(20).pct_change().std() * np.sqrt(252)
        if 0.15 < recent_volatility < 0.35:
            scores['volatility'] = 15
        elif 0.10 < recent_volatility < 0.45:
            scores['volatility'] = 10
        
        total_score = sum(scores.values())
        
        return {
            "total": total_score,
            "details": scores,
            "trend_analysis": technical_analyzer.analyze_trend(df)
        }
    
    def screen_stocks(self, max_results: int = 10) -> List[Dict]:
        """
        筛选股票
        返回: 按评分排序的股票列表
        """
        results = []
        
        # 获取股票基础信息
        stock_basic = self.data.get_stock_basic()
        if stock_basic.empty:
            print("无法获取股票基础信息")
            return []
        
        # 过滤 ST 股和科创板（风险较高）
        stock_basic = stock_basic[
            ~stock_basic['name'].str.contains('|'.join(self.EXCLUDE_ST_TYPES), na=False)
        ]
        
        # 只选主板和创业板
        stock_basic = stock_basic[stock_basic['market'].isin(['主板', '创业板'])]
        
        print(f"开始筛选 {len(stock_basic)} 只股票...")
        
        # 限制数量，避免请求过多
        sample_stocks = stock_basic.sample(min(100, len(stock_basic)))
        
        for _, stock in sample_stocks.iterrows():
            ts_code = stock['ts_code']
            name = stock['name']
            
            try:
                # 获取日线数据
                df = self.data.get_stock_daily(ts_code)
                if df.empty or len(df) < 60:
                    continue
                
                # 技术面筛选
                filtered_df = self.filter_technical(df)
                if filtered_df.empty:
                    continue
                
                # 计算评分
                score_result = self.calculate_score(filtered_df)
                
                if score_result['total'] >= 60:  # 只保留评分 >= 60 的
                    latest = filtered_df.iloc[-1]
                    
                    results.append({
                        "ts_code": ts_code,
                        "name": name,
                        "score": score_result['total'],
                        "score_details": score_result['details'],
                        "trend": score_result['trend_analysis']['trend'],
                        "confidence": score_result['trend_analysis']['confidence'],
                        "rsi": score_result['trend_analysis']['rsi'],
                        "close": latest['close'],
                        "change_pct": (latest['close'] - latest['pre_close']) / latest['pre_close'] * 100 if 'pre_close' in latest else 0,
                        "vol_ratio": latest['vol'] / latest['vol_ma20'] if 'vol_ma20' in latest else 1
                    })
                    
                    print(f"✓ {name}({ts_code}): 评分 {score_result['total']}")
                    
            except Exception as e:
                continue
        
        # 按评分排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:max_results]
    
    def get_sector_leaders(self, sector_name: str) -> List[Dict]:
        """获取板块龙头股"""
        # 这里可以通过 AkShare 获取板块成分股
        # 然后筛选评分最高的
        pass

# 全局实例
stock_screener = StockScreener()
