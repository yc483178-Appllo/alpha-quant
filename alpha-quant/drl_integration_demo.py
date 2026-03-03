#!/usr/bin/env python3
"""
DRL投资组合引擎集成演示
展示如何在Alpha V4.0系统中使用V5.0 DRL模块
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import numpy as np
from datetime import datetime
from core.drl_portfolio_agent import DRLPortfolioAgent, create_drl_agent
from modules.data_provider import data_provider
from modules.technical_analysis import technical_analyzer
from modules.logger import log


class DRLIntegrationDemo:
    """DRL集成演示类"""
    
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.drl_agent = None
        self._init_agent()
    
    def _init_agent(self):
        """初始化DRL Agent"""
        try:
            self.drl_agent = create_drl_agent(self.config_path)
            log.info(f"✅ DRL Agent初始化成功 | enabled={self.drl_agent.enabled}")
        except Exception as e:
            log.error(f"❌ DRL Agent初始化失败: {e}")
            self.drl_agent = None
    
    def demo_train(self, n_episodes=10):
        """演示训练流程"""
        print("\n" + "="*60)
        print("🧠 DRL训练演示")
        print("="*60)
        
        if not self.drl_agent or not self.drl_agent.enabled:
            print("⚠️ DRL Agent未启用或初始化失败")
            return None
        
        print(f"开始训练 {n_episodes} 个episode...")
        results = self.drl_agent.train_episode(n_episodes=n_episodes)
        
        # 显示训练结果
        print("\n📊 训练结果摘要:")
        print(f"  总Episode数: {len(results)}")
        print(f"  平均Reward: {np.mean([r['total_reward'] for r in results]):.4f}")
        print(f"  平均最终价值: {np.mean([r['final_value'] for r in results]):.2f}")
        print(f"  平均Sharpe: {np.mean([r['sharpe'] for r in results]):.4f}")
        print(f"  模型保存路径: {self.drl_agent.model_path}")
        
        return results
    
    def demo_predict(self, stock_codes=None):
        """演示预测流程"""
        print("\n" + "="*60)
        print("🎯 DRL预测演示")
        print("="*60)
        
        if not self.drl_agent or not self.drl_agent.enabled:
            print("⚠️ DRL Agent未启用或初始化失败")
            return None
        
        # 如果没有指定股票，使用默认测试数据
        if stock_codes is None:
            stock_codes = ["000001.SZ", "000002.SZ", "600000.SH"]
        
        print(f"分析股票: {stock_codes}")
        
        # 构建模拟状态（实际使用时从data_provider获取真实数据）
        stock_features = []
        for i, code in enumerate(stock_codes[:self.drl_agent.env.max_positions]):
            stock_features.append({
                "price_change_5d": np.random.randn() * 0.05,
                "price_change_20d": np.random.randn() * 0.10,
                "volatility_20d": abs(np.random.randn()) * 0.02,
                "volume_ratio": 1.0 + np.random.randn() * 0.5,
                "turnover_rate": abs(np.random.randn()) * 0.03,
                "rsi_14": 50 + np.random.randn() * 20,
                "macd_histogram": np.random.randn() * 0.5,
                "sentiment_score": np.random.randn() * 0.3
            })
        
        # 填充剩余位置
        while len(stock_features) < self.drl_agent.env.max_positions:
            stock_features.append({
                "price_change_5d": 0, "price_change_20d": 0, "volatility_20d": 0,
                "volume_ratio": 1.0, "turnover_rate": 0, "rsi_14": 50,
                "macd_histogram": 0, "sentiment_score": 0
            })
        
        global_features = {
            "market_regime": 1.0,  # 震荡市
            "portfolio_sharpe": 1.2,
            "portfolio_drawdown": -0.02,
            "cash_ratio": 0.3,
            "total_position_pct": 0.7
        }
        
        # 构建状态向量
        state = self.drl_agent.get_state_from_market_data(stock_features, global_features)
        
        # 预测
        recommendation = self.drl_agent.predict_portfolio_weights(state)
        
        print("\n📈 预测结果:")
        print(f"  置信度: {recommendation['confidence']:.4f}")
        print(f"  预期价值: {recommendation['expected_value']:.4f}")
        print(f"  时间戳: {recommendation['timestamp']}")
        
        # 显示前10只股票的推荐权重
        weights = recommendation['recommended_weights'][:10]
        print(f"\n  推荐权重调整(前10只):")
        for i, w in enumerate(weights):
            action = "加仓" if w > 0.1 else ("减仓" if w < -0.1 else "持有")
            print(f"    股票{i+1}: {w:+.4f} ({action})")
        
        return recommendation
    
    def demo_signal_bus(self):
        """演示信号总线集成"""
        print("\n" + "="*60)
        print("📡 信号总线集成演示")
        print("="*60)
        
        if not self.drl_agent or not self.drl_agent.enabled:
            print("⚠️ DRL Agent未启用或初始化失败")
            return None
        
        # 构建测试状态
        state = np.random.randn(self.drl_agent.env.state_dim).astype(np.float32)
        
        # 生成信号
        signal = self.drl_agent.generate_signal_for_bus(state)
        
        print("生成的信号消息:")
        print(json.dumps(signal, indent=2, ensure_ascii=False))
        
        return signal
    
    def demo_full_pipeline(self):
        """演示完整流程"""
        print("\n" + "="*60)
        print("🚀 DRL完整流程演示")
        print("="*60)
        
        # 1. 训练
        print("\n[1/3] 训练阶段...")
        train_results = self.demo_train(n_episodes=5)
        
        # 2. 预测
        print("\n[2/3] 预测阶段...")
        prediction = self.demo_predict()
        
        # 3. 信号生成
        print("\n[3/3] 信号生成阶段...")
        signal = self.demo_signal_bus()
        
        print("\n" + "="*60)
        print("✅ 完整流程演示完成")
        print("="*60)
        
        return {
            "train_results": train_results,
            "prediction": prediction,
            "signal": signal
        }


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='DRL投资组合引擎集成演示')
    parser.add_argument('--mode', choices=['train', 'predict', 'signal', 'full'], 
                       default='full', help='演示模式')
    parser.add_argument('--episodes', type=int, default=10, help='训练episode数')
    parser.add_argument('--config', default='config.json', help='配置文件路径')
    
    args = parser.parse_args()
    
    # 创建演示实例
    demo = DRLIntegrationDemo(config_path=args.config)
    
    if args.mode == 'train':
        demo.demo_train(n_episodes=args.episodes)
    elif args.mode == 'predict':
        demo.demo_predict()
    elif args.mode == 'signal':
        demo.demo_signal_bus()
    elif args.mode == 'full':
        demo.demo_full_pipeline()


if __name__ == "__main__":
    main()
