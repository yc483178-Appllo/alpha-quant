"""
技术分析模块
"""
import pandas as pd
import numpy as np
from typing import Dict, Tuple

class TechnicalAnalyzer:
    """技术分析器"""
    
    @staticmethod
    def calculate_ma(df: pd.DataFrame, periods: list = [5, 10, 20, 60]) -> pd.DataFrame:
        """计算移动平均线"""
        for period in periods:
            df[f'MA{period}'] = df['close'].rolling(window=period).mean()
        return df
    
    @staticmethod
    def calculate_macd(df: pd.DataFrame, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
        """计算 MACD"""
        ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
        ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
        df['MACD'] = ema_fast - ema_slow
        df['MACD_Signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
        df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
        return df
    
    @staticmethod
    def calculate_rsi(df: pd.DataFrame, period: int = 14) -> pd.DataFrame:
        """计算 RSI"""
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        return df
    
    @staticmethod
    def calculate_bollinger(df: pd.DataFrame, period: int = 20, std_dev: float = 2.0) -> pd.DataFrame:
        """计算布林带"""
        df['BOLL_MID'] = df['close'].rolling(window=period).mean()
        df['BOLL_STD'] = df['close'].rolling(window=period).std()
        df['BOLL_UP'] = df['BOLL_MID'] + (df['BOLL_STD'] * std_dev)
        df['BOLL_DOWN'] = df['BOLL_MID'] - (df['BOLL_STD'] * std_dev)
        return df
    
    @staticmethod
    def calculate_kdj(df: pd.DataFrame, n: int = 9, m1: int = 3, m2: int = 3) -> pd.DataFrame:
        """计算 KDJ 指标"""
        low_list = df['low'].rolling(window=n, min_periods=n).min()
        high_list = df['high'].rolling(window=n, min_periods=n).max()
        rsv = (df['close'] - low_list) / (high_list - low_list) * 100
        df['K'] = rsv.ewm(alpha=1/m1, adjust=False).mean()
        df['D'] = df['K'].ewm(alpha=1/m2, adjust=False).mean()
        df['J'] = 3 * df['K'] - 2 * df['D']
        return df
    
    @staticmethod
    def analyze_trend(df: pd.DataFrame) -> Dict:
        """分析趋势"""
        if len(df) < 20:
            return {"trend": "unknown", "confidence": 0}
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # 均线排列
        ma_bullish = latest['MA5'] > latest['MA10'] > latest['MA20']
        ma_bearish = latest['MA5'] < latest['MA10'] < latest['MA20']
        
        # MACD
        macd_bullish = latest['MACD'] > latest['MACD_Signal'] > 0
        macd_bearish = latest['MACD'] < latest['MACD_Signal'] < 0
        
        # RSI
        rsi_overbought = latest['RSI'] > 70
        rsi_oversold = latest['RSI'] < 30
        
        # 综合判断
        bullish_signals = sum([ma_bullish, macd_bullish])
        bearish_signals = sum([ma_bearish, macd_bearish])
        
        if bullish_signals >= 2:
            trend = "bullish"
            confidence = 60 + bullish_signals * 15
        elif bearish_signals >= 2:
            trend = "bearish"
            confidence = 60 + bearish_signals * 15
        else:
            trend = "neutral"
            confidence = 50
        
        # 调整置信度
        if rsi_overbought and trend == "bullish":
            confidence -= 10
        if rsi_oversold and trend == "bearish":
            confidence -= 10
        
        return {
            "trend": trend,
            "confidence": min(confidence, 95),
            "rsi": round(latest['RSI'], 2),
            "macd_signal": "golden_cross" if latest['MACD'] > latest['MACD_Signal'] and prev['MACD'] <= prev['MACD_Signal'] else 
                          "death_cross" if latest['MACD'] < latest['MACD_Signal'] and prev['MACD'] >= prev['MACD_Signal'] else "none"
        }
    
    @staticmethod
    def calculate_support_resistance(df: pd.DataFrame, window: int = 20) -> Tuple[float, float]:
        """计算支撑阻力位"""
        recent = df.tail(window)
        support = recent['low'].min()
        resistance = recent['high'].max()
        return support, resistance

# 全局实例
technical_analyzer = TechnicalAnalyzer()
