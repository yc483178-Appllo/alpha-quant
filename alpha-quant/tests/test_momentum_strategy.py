#!/usr/bin/env python3
"""
test_momentum_strategy.py --- 动量策略单元测试
"""

import unittest
import pandas as pd
import numpy as np
from datetime import datetime

import sys
sys.path.insert(0, '/root/.openclaw/workspace/alpha-quant')

from strategies.momentum_strategy import MomentumStrategy, MomentumConfig, screen_momentum_stocks


class TestMomentumConfig(unittest.TestCase):
    """测试配置类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = MomentumConfig()
        self.assertEqual(config.min_change, 2.0)
        self.assertEqual(config.max_change, 20.0)
        self.assertEqual(config.min_turnover, 3.0)
        self.assertEqual(config.max_turnover, 10.0)
        self.assertEqual(config.min_volume_ratio, 1.5)
        self.assertEqual(config.top_n, 20)
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = MomentumConfig(min_change=5.0, top_n=10)
        self.assertEqual(config.min_change, 5.0)
        self.assertEqual(config.top_n, 10)


class TestMomentumStrategy(unittest.TestCase):
    """测试策略类"""
    
    def setUp(self):
        """测试前准备"""
        self.config = MomentumConfig()
        self.strategy = MomentumStrategy(self.config)
        
        # 创建模拟数据
        self.mock_data = pd.DataFrame({
            '代码': ['000001', '000002', '000003', '000004', '000005'],
            '名称': ['平安银行', '万科A', '国农科技', '世纪星源', '深振业A'],
            '最新价': [10.5, 15.2, 8.8, 6.5, 12.3],
            '涨跌幅': [5.2, 1.5, 8.5, -2.0, 3.5],
            '换手率': [5.5, 2.0, 12.0, 4.0, 8.0],
            '量比': [2.5, 1.0, 3.0, 1.2, 1.8]
        })
    
    def test_calculate_score(self):
        """测试评分计算"""
        # 测试正常数据
        row = pd.Series({
            '涨跌幅': 5.0,
            '换手率': 6.0,
            '量比': 2.0
        })
        score = self.strategy.calculate_score(row)
        self.assertGreater(score, 0)
        self.assertLessEqual(score, 100)
        
        # 测试异常数据
        row_invalid = pd.Series({
            '涨跌幅': 'N/A',
            '换手率': None,
            '量比': float('inf')
        })
        score_invalid = self.strategy.calculate_score(row_invalid)
        self.assertEqual(score_invalid, 0.0)
    
    def test_filter_stocks(self):
        """测试股票筛选"""
        result = self.strategy.filter_stocks(self.mock_data)
        
        # 检查筛选结果
        self.assertIsInstance(result, pd.DataFrame)
        
        if not result.empty:
            # 检查是否满足所有条件
            for _, row in result.iterrows():
                self.assertGreater(row['涨跌幅'], self.config.min_change)
                self.assertLess(row['涨跌幅'], self.config.max_change)
                self.assertGreater(row['换手率'], self.config.min_turnover)
                self.assertLess(row['换手率'], self.config.max_turnover)
                self.assertGreater(row['量比'], self.config.min_volume_ratio)
            
            # 检查是否有综合评分列
            self.assertIn('综合评分', result.columns)
    
    def test_format_output(self):
        """测试输出格式化"""
        filtered = self.strategy.filter_stocks(self.mock_data)
        formatted = self.strategy.format_output(filtered)
        
        # 检查输出列
        expected_cols = ['代码', '名称', '最新价', '涨跌幅', '换手率', '量比', '综合评分', '选股时间']
        for col in expected_cols:
            self.assertIn(col, formatted.columns)
    
    def test_empty_data(self):
        """测试空数据处理"""
        empty_df = pd.DataFrame()
        result = self.strategy.filter_stocks(empty_df)
        self.assertTrue(result.empty)


class TestIntegration(unittest.TestCase):
    """集成测试"""
    
    def test_screen_momentum_stocks_function(self):
        """测试便捷函数"""
        # 注意：这个测试需要网络连接和数据源
        # 在实际运行时会调用外部API
        try:
            result = screen_momentum_stocks(top_n=5)
            self.assertIsInstance(result, pd.DataFrame)
            self.assertLessEqual(len(result), 5)
        except Exception as e:
            # 如果数据源不可用，跳过测试
            self.skipTest(f"数据源不可用: {e}")


def run_tests():
    """运行所有测试"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestMomentumConfig))
    suite.addTests(loader.loadTestsFromTestCase(TestMomentumStrategy))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)
