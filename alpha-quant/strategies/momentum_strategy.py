#!/usr/bin/env python3
"""
momentum_strategy.py --- A股动量选股策略

选股条件：
1. 涨跌幅 > 2%
2. 换手率 3% ~ 10%
3. 量比 > 1.5

输出：DataFrame，包含代码/名称/价格/综合评分

Author: Alpha Quant System
Date: 2026-02-27
"""

import os
import sys
import logging
from typing import Optional, List, Dict
from datetime import datetime
from dataclasses import dataclass

import pandas as pd
import numpy as np

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f'logs/momentum_{datetime.now().strftime("%Y%m%d")}.log')
    ]
)
logger = logging.getLogger(__name__)


@dataclass
class MomentumConfig:
    """动量策略配置"""
    min_change: float = 2.0          # 最小涨跌幅 (%)
    max_change: float = 20.0         # 最大涨跌幅 (过滤涨停)
    min_turnover: float = 3.0        # 最小换手率 (%)
    max_turnover: float = 10.0       # 最大换手率 (%)
    min_volume_ratio: float = 1.5    # 最小量比
    top_n: int = 20                  # 返回前N只股票


class MomentumStrategy:
    """
    A股动量选股策略
    
    基于量价配合的动量选股，筛选短期强势且流动性良好的标的。
    """
    
    def __init__(self, config: Optional[MomentumConfig] = None):
        """
        初始化策略
        
        Args:
            config: 策略配置，默认使用预设参数
        """
        self.config = config or MomentumConfig()
        self.data: Optional[pd.DataFrame] = None
        
    def fetch_data(self, source: str = "auto") -> pd.DataFrame:
        """
        获取A股实时行情数据
        
        Args:
            source: 数据源，可选 "auto", "akshare", "ths"
            
        Returns:
            DataFrame 包含股票实时数据
            
        Raises:
            Exception: 所有数据源均失败时抛出
        """
        logger.info(f"开始获取实时行情数据 (source: {source})")
        
        errors = []
        
        # 1. 尝试 AkShare
        if source in ("auto", "akshare"):
            try:
                import akshare as ak
                df = ak.stock_zh_a_spot_em()
                logger.info(f"✅ AkShare 数据获取成功: {len(df)} 条")
                self.data = df
                return df
            except Exception as e:
                errors.append(f"AkShare: {e}")
                logger.warning(f"⚠️ AkShare 失败: {e}")
        
        # 2. 尝试同花顺 SDK
        if source in ("auto", "ths"):
            try:
                from data_gateway import get_realtime_data_with_fallback
                df, src = get_realtime_data_with_fallback()
                logger.info(f"✅ 同花顺数据获取成功: {len(df)} 条 (来源: {src})")
                self.data = df
                return df
            except Exception as e:
                errors.append(f"THS: {e}")
                logger.warning(f"⚠️ 同花顺失败: {e}")
        
        # 所有源都失败
        error_msg = f"所有数据源均失败: {'; '.join(errors)}"
        logger.error(f"❌ {error_msg}")
        raise Exception(error_msg)
    
    def calculate_score(self, row: pd.Series) -> float:
        """
        计算综合评分
        
        评分维度：
        - 涨跌幅得分 (40%): 涨幅越高越好，但过滤过高涨幅
        - 换手率得分 (30%): 适中为佳，过高或过低都扣分
        - 量比得分 (30%): 量比越高越好，表示资金关注度高
        
        Args:
            row: 单只股票数据行
            
        Returns:
            综合评分 (0-100)
        """
        try:
            # 涨跌幅得分 (0-40)
            change = float(row.get('涨跌幅', 0))
            change_score = min(change * 2, 40) if change > 0 else 0
            
            # 换手率得分 (0-30) - 适中为佳
            turnover = float(row.get('换手率', 0))
            if 3 <= turnover <= 10:
                turnover_score = 30 - abs(turnover - 6) * 3  # 6%为最佳
            else:
                turnover_score = max(0, 30 - abs(turnover - 6) * 5)
            
            # 量比得分 (0-30)
            volume_ratio = float(row.get('量比', 0))
            volume_score = min(volume_ratio * 10, 30)
            
            total_score = change_score + turnover_score + volume_score
            return round(total_score, 2)
            
        except (ValueError, TypeError) as e:
            logger.debug(f"评分计算异常: {e}")
            return 0.0
    
    def filter_stocks(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """
        根据动量条件筛选股票
        
        Args:
            df: 输入数据，默认使用 self.data
            
        Returns:
            筛选后的 DataFrame
        """
        if df is None:
            df = self.data
            
        if df is None or df.empty:
            logger.warning("⚠️ 输入数据为空")
            return pd.DataFrame()
        
        logger.info(f"开始筛选，原始数据: {len(df)} 条")
        
        # 数据清洗
        df = df.copy()
        
        # 检查必要的列
        required_cols = ['涨跌幅', '换手率', '量比', '最新价']
        missing_cols = [col for col in required_cols if col not in df.columns]
        
        if missing_cols:
            logger.error(f"❌ 缺少必要的列: {missing_cols}")
            logger.info(f"可用列: {list(df.columns)}")
            # 如果缺少关键列，返回空DataFrame
            if any(col in missing_cols for col in ['涨跌幅', '最新价']):
                return pd.DataFrame()
            # 为缺失的列填充默认值
            for col in missing_cols:
                df[col] = 0.0
        
        # 转换数值列
        numeric_cols = ['涨跌幅', '换手率', '量比', '最新价']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 过滤条件
        mask = (
            (df['涨跌幅'] > self.config.min_change) &
            (df['涨跌幅'] < self.config.max_change) &
            (df['换手率'] > self.config.min_turnover) &
            (df['换手率'] < self.config.max_turnover) &
            (df['量比'] > self.config.min_volume_ratio) &
            (df['最新价'] > 0)  # 排除停牌
        )
        
        filtered = df[mask].copy()
        logger.info(f"条件筛选后: {len(filtered)} 条")
        
        # 计算综合评分
        filtered['综合评分'] = filtered.apply(self.calculate_score, axis=1)
        
        # 排序并取前N
        result = filtered.nlargest(self.config.top_n, '综合评分')
        
        return result
    
    def format_output(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        格式化输出结果
        
        Args:
            df: 筛选后的数据
            
        Returns:
            格式化后的 DataFrame
        """
        if df.empty:
            return pd.DataFrame()
        
        # 选择输出列
        output_cols = {
            '代码': '代码',
            '名称': '名称',
            '最新价': '最新价',
            '涨跌幅': '涨跌幅',
            '换手率': '换手率',
            '量比': '量比',
            '综合评分': '综合评分'
        }
        
        # 重命名并选择列
        result = pd.DataFrame()
        for old_col, new_col in output_cols.items():
            if old_col in df.columns:
                result[new_col] = df[old_col]
        
        # 添加时间戳
        result['选股时间'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        return result.reset_index(drop=True)
    
    def run(self, source: str = "auto") -> pd.DataFrame:
        """
        执行完整的选股流程
        
        Args:
            source: 数据源
            
        Returns:
            选股结果 DataFrame
        """
        logger.info("=" * 50)
        logger.info("🚀 启动动量选股策略")
        logger.info("=" * 50)
        
        try:
            # 1. 获取数据
            raw_data = self.fetch_data(source)
            
            # 2. 筛选股票
            filtered = self.filter_stocks(raw_data)
            
            # 3. 格式化输出
            result = self.format_output(filtered)
            
            logger.info(f"✅ 选股完成，选出 {len(result)} 只股票")
            
            if not result.empty:
                logger.info("\n📊 选股结果:")
                for idx, row in result.iterrows():
                    logger.info(f"  {idx+1}. {row['代码']} {row['名称']} | "
                              f"价格:{row['最新价']} | "
                              f"涨幅:{row['涨跌幅']}% | "
                              f"评分:{row['综合评分']}")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ 策略执行失败: {e}")
            raise
    
    def save_result(self, df: pd.DataFrame, filepath: Optional[str] = None):
        """
        保存选股结果到文件
        
        Args:
            df: 选股结果
            filepath: 保存路径，默认按日期生成
        """
        if filepath is None:
            os.makedirs('results', exist_ok=True)
            filepath = f"results/momentum_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        
        df.to_csv(filepath, index=False, encoding='utf-8-sig')
        logger.info(f"💾 结果已保存: {filepath}")


# 便捷函数
def screen_momentum_stocks(
    min_change: float = 2.0,
    max_change: float = 20.0,
    min_turnover: float = 3.0,
    max_turnover: float = 10.0,
    min_volume_ratio: float = 1.5,
    top_n: int = 20,
    source: str = "auto"
) -> pd.DataFrame:
    """
    快速选股函数
    
    Args:
        min_change: 最小涨跌幅
        max_change: 最大涨跌幅
        min_turnover: 最小换手率
        max_turnover: 最大换手率
        min_volume_ratio: 最小量比
        top_n: 返回前N只
        source: 数据源
        
    Returns:
        选股结果 DataFrame
    """
    config = MomentumConfig(
        min_change=min_change,
        max_change=max_change,
        min_turnover=min_turnover,
        max_turnover=max_turnover,
        min_volume_ratio=min_volume_ratio,
        top_n=top_n
    )
    
    strategy = MomentumStrategy(config)
    return strategy.run(source)


# 测试用例
if __name__ == "__main__":
    # 创建日志目录
    os.makedirs('logs', exist_ok=True)
    os.makedirs('results', exist_ok=True)
    
    # 运行策略
    try:
        result = screen_momentum_stocks()
        
        print("\n" + "=" * 60)
        print("📊 动量选股结果")
        print("=" * 60)
        print(result.to_string(index=False))
        print("=" * 60)
        
    except Exception as e:
        logger.error(f"程序异常: {e}")
        sys.exit(1)
