#!/usr/bin/env python3
"""
Alpha V5.0 - Portfolio Optimizer集成演示
展示4种优化算法和Chief Agent集成
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from datetime import datetime
from modules.portfolio_optimizer import create_portfolio_optimizer, quick_optimize
from modules.chief_agent import create_chief_agent, ScoutReport, SentimentReport, PickerList


class PortfolioOptimizerDemo:
    """Portfolio Optimizer集成演示"""
    
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.optimizer = create_portfolio_optimizer(config_path)
        self.chief = create_chief_agent(config_path)
    
    def _generate_test_data(self, n=10):
        """生成测试数据"""
        np.random.seed(42)
        # 预期日收益率 (年化约10-15%)
        expected_returns = np.random.randn(n) * 0.001 + 0.0005
        # 协方差矩阵 (年化波动约20%)
        cov_matrix = np.eye(n) * 0.0004
        # 添加一些相关性
        for i in range(n):
            for j in range(i+1, n):
                cov_matrix[i, j] = cov_matrix[j, i] = np.random.randn() * 0.0001
        
        return expected_returns, cov_matrix
    
    def demo_markowitz(self):
        """演示马科维茨优化"""
        print("\n" + "="*70)
        print("📊 马科维茨均值-方差优化 (MVO)")
        print("="*70)
        print("适用场景: 低波动市场，追求最大夏普比率")
        
        returns, cov = self._generate_test_data(10)
        result = self.optimizer.optimize(returns, cov, method="markowitz")
        
        print(f"\n优化结果:")
        print(f"  预期年化收益: {result.expected_annual_return:.2%}")
        print(f"  预期年化波动: {result.expected_annual_volatility:.2%}")
        print(f"  夏普比率: {result.sharpe_ratio:.2f}")
        print(f"  持仓数量: {result.position_count}")
        print(f"  最大权重: {result.max_weight:.2%}")
        print(f"\n前5只权重: {[f'{w:.2%}' for w in result.weights[:5]]}")
    
    def demo_black_litterman(self):
        """演示Black-Litterman优化"""
        print("\n" + "="*70)
        print("🎯 Black-Litterman优化 (融合情绪观点)")
        print("="*70)
        print("适用场景: 有主观观点(如舆情情绪)时，融合市场均衡+观点")
        
        returns, cov = self._generate_test_data(10)
        
        # 模拟情绪观点: 看多第1、3只，看空第2只
        sentiment_views = {
            0: 0.0015,   # 看多
            1: -0.0005,  # 看空
            2: 0.0012,   # 看多
        }
        
        print(f"\n输入观点:")
        for idx, view in sentiment_views.items():
            print(f"  股票{idx}: {'看多' if view > 0 else '看空'} {abs(view):.4f}")
        
        result = self.optimizer.optimize(
            returns, cov,
            sentiment_views=sentiment_views,
            method="black-litterman"
        )
        
        print(f"\n优化结果:")
        print(f"  预期年化收益: {result.expected_annual_return:.2%}")
        print(f"  夏普比率: {result.sharpe_ratio:.2f}")
        print(f"\n权重分布:")
        for i, w in enumerate(result.weights[:5]):
            view_str = ""
            if i in sentiment_views:
                view_str = f" ({'看多' if sentiment_views[i] > 0 else '看空'})"
            print(f"  股票{i}: {w:.2%}{view_str}")
    
    def demo_risk_parity(self):
        """演示风险平价优化"""
        print("\n" + "="*70)
        print("⚖️ 风险平价优化 (Risk Parity)")
        print("="*70)
        print("适用场景: 高波动市场，追求各资产风险贡献相等")
        
        returns, cov = self._generate_test_data(10)
        result = self.optimizer.optimize(returns, cov, method="risk-parity")
        
        print(f"\n优化结果:")
        print(f"  预期年化收益: {result.expected_annual_return:.2%}")
        print(f"  预期年化波动: {result.expected_annual_volatility:.2%}")
        print(f"  夏普比率: {result.sharpe_ratio:.2f}")
        print(f"  持仓数量: {result.position_count}")
        
        if result.risk_contribution:
            print(f"\n风险贡献分布 (应接近相等):")
            for i, rc in enumerate(result.risk_contribution[:5]):
                print(f"  股票{i}: {rc:.2%}")
        
        print(f"\n权重分布: {[f'{w:.2%}' for w in result.weights[:5]]}")
    
    def demo_max_diversification(self):
        """演示最大分散度优化"""
        print("\n" + "="*70)
        print("🌐 最大分散度优化 (Max Diversification)")
        print("="*70)
        print("适用场景: 资产相关性不稳定时，追求最大化分散化收益")
        
        returns, cov = self._generate_test_data(10)
        result = self.optimizer.optimize(returns, cov, method="max-diversification")
        
        print(f"\n优化结果:")
        print(f"  预期年化收益: {result.expected_annual_return:.2%}")
        print(f"  预期年化波动: {result.expected_annual_volatility:.2%}")
        print(f"  夏普比率: {result.sharpe_ratio:.2f}")
        print(f"  持仓数量: {result.position_count}")
        print(f"\n前5只权重: {[f'{w:.2%}' for w in result.weights[:5]]}")
    
    def demo_auto_select_method(self):
        """演示自动方法选择"""
        print("\n" + "="*70)
        print("🤖 自动优化方法选择")
        print("="*70)
        
        scenarios = [
            ("bull", 0.12, "牛市低波"),
            ("bear", 0.30, "熊市高波"),
            ("neutral", 0.20, "震荡市中波"),
        ]
        
        for regime, vol, desc in scenarios:
            method = self.optimizer.auto_select_method(regime, vol)
            print(f"\n场景: {desc}")
            print(f"  市场环境: {regime}, 波动率: {vol:.2%}")
            print(f"  推荐方法: {method}")
    
    def demo_constraints(self):
        """演示A股约束"""
        print("\n" + "="*70)
        print("📋 A股监管约束演示")
        print("="*70)
        
        constraints = self.optimizer.constraints
        print("\n当前约束配置:")
        print(f"  单票最大: {constraints['single_stock_max_pct']:.0%}")
        print(f"  行业最大: {constraints['sector_max_pct']:.0%}")
        print(f"  最少持仓: {constraints['min_position_count']}只")
        print(f"  最多持仓: {constraints['max_position_count']}只")
        print(f"  最小权重: {constraints['min_weight']:.0%}")
        print(f"  ST股禁入: {constraints['st_forbidden']}")
        print(f"  T+1规则: {constraints['t_plus_1']}")
        
        # 测试约束生效
        returns, cov = self._generate_test_data(20)
        result = self.optimizer.optimize(returns, cov, method="markowitz")
        
        print(f"\n优化结果验证:")
        print(f"  持仓数量: {result.position_count} (约束: {constraints['min_position_count']}-{constraints['max_position_count']})")
        print(f"  最大权重: {result.max_weight:.2%} (约束: ≤{constraints['single_stock_max_pct']:.0%})")
        
        # 检查是否有低于min_weight的持仓
        small_positions = sum(1 for w in result.weights if 0 < w < constraints['min_weight'])
        print(f"  低于{constraints['min_weight']:.0%}的持仓: {small_positions}只 (应被过滤)")
    
    def demo_chief_integration(self):
        """演示与Chief Agent集成"""
        print("\n" + "="*70)
        print("🔗 Portfolio Optimizer与Chief Agent集成")
        print("="*70)
        
        # 1. 生成优化结果
        returns, cov = self._generate_test_data(5)
        opt_result = self.optimizer.optimize(returns, cov, method="black-litterman")
        
        print("\n📐 Optimizer输出:")
        print(f"  方法: {opt_result.method}")
        print(f"  预期收益: {opt_result.expected_annual_return:.2%}")
        print(f"  预期风险: {opt_result.expected_annual_volatility:.2%}")
        print(f"  权重: {[f'{w:.2%}' for w in opt_result.weights[:5]]}")
        
        # 2. 生成信号
        signal = self.optimizer.generate_signal_for_bus(opt_result)
        
        print("\n📡 信号总线消息:")
        print(f"  类型: {signal['type']}")
        print(f"  来源: {signal['source']}")
        print(f"  优先级: {signal['priority']}")
        print(f"  数据: 预期收益={signal['data']['expected_return']:.2%}, "
              f"Sharpe={signal['data']['sharpe_ratio']:.2f}")
        
        # 3. 在Chief Agent中使用
        print("\n🧠 Chief Agent决策流程:")
        print("  ├─ 接收DRL建议 (含置信度)")
        print("  ├─ 接收Optimizer建议 ← 当前步骤")
        print("  ├─ Guard风控检查")
        print("  └─ 综合决策")
        
        # 模拟Chief决策场景
        print("\n场景: DRL置信度0.6 (中低)，Optimizer Sharpe 1.2")
        print("决策: DRL置信度<0.7，采纳Optimizer建议")
    
    def demo_full_workflow(self):
        """演示完整工作流程"""
        print("\n" + "="*70)
        print("🚀 完整工作流程演示")
        print("="*70)
        
        # 模拟股票池
        stocks = [
            {"ts_code": "300750.SZ", "name": "宁德时代", "sector": "新能源"},
            {"ts_code": "601012.SH", "name": "隆基绿能", "sector": "新能源"},
            {"ts_code": "600519.SH", "name": "贵州茅台", "sector": "消费"},
            {"ts_code": "000858.SZ", "name": "五粮液", "sector": "消费"},
            {"ts_code": "601398.SH", "name": "工商银行", "sector": "银行"},
        ]
        
        n = len(stocks)
        returns, cov = self._generate_test_data(n)
        
        # 步骤1: 选择优化方法
        method = self.optimizer.auto_select_method("neutral", 0.20)
        print(f"\n[1/4] 自动选择优化方法: {method}")
        
        # 步骤2: 执行优化
        print(f"[2/4] 执行优化...")
        result = self.optimizer.optimize(returns, cov, method=method)
        
        print(f"      预期收益: {result.expected_annual_return:.2%}")
        print(f"      预期风险: {result.expected_annual_volatility:.2%}")
        print(f"      Sharpe: {result.sharpe_ratio:.2f}")
        
        # 步骤3: 生成持仓方案
        print(f"[3/4] 生成持仓方案:")
        for i, (stock, weight) in enumerate(zip(stocks, result.weights)):
            if weight > 0.01:
                print(f"      {stock['name']}: {weight:.2%}")
        
        # 步骤4: 生成交易信号
        print(f"[4/4] 生成交易信号")
        signal = self.optimizer.generate_signal_for_bus(result)
        print(f"      信号类型: {signal['type']}")
        print(f"      优先级: {signal['priority']}")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Portfolio Optimizer集成演示')
    parser.add_argument('--mode',
                       choices=['markowitz', 'bl', 'rp', 'md', 'auto', 'constraints', 'chief', 'full', 'all'],
                       default='all', help='演示模式')
    parser.add_argument('--config', default='config.json', help='配置文件路径')
    
    args = parser.parse_args()
    
    demo = PortfolioOptimizerDemo(config_path=args.config)
    
    if args.mode == 'markowitz' or args.mode == 'all':
        demo.demo_markowitz()
    
    if args.mode == 'bl' or args.mode == 'all':
        demo.demo_black_litterman()
    
    if args.mode == 'rp' or args.mode == 'all':
        demo.demo_risk_parity()
    
    if args.mode == 'md' or args.mode == 'all':
        demo.demo_max_diversification()
    
    if args.mode == 'auto' or args.mode == 'all':
        demo.demo_auto_select_method()
    
    if args.mode == 'constraints' or args.mode == 'all':
        demo.demo_constraints()
    
    if args.mode == 'chief' or args.mode == 'all':
        demo.demo_chief_integration()
    
    if args.mode == 'full' or args.mode == 'all':
        demo.demo_full_workflow()
    
    print("\n" + "="*70)
    print("✅ Portfolio Optimizer演示完成")
    print("="*70)


if __name__ == "__main__":
    main()
