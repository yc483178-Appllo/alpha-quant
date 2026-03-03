#!/usr/bin/env python3
"""
Alpha V5.0 - Chief Agent集成演示
展示完整的Chief决策流程
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import datetime
from modules.chief_agent import (
    ChiefAgent, create_chief_agent,
    ScoutReport, SentimentReport, PickerList
)
from modules.agent_bus import create_agent_bus, create_agent_coordinator


class ChiefIntegrationDemo:
    """Chief Agent集成演示"""
    
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.chief = create_chief_agent(config_path)
        self.agent_bus = create_agent_bus()
        self.coordinator = create_agent_coordinator(self.agent_bus)
        
        # 注册Agent
        self.coordinator.register_agent("Chief")
        self.coordinator.register_agent("DRL")
        self.coordinator.register_agent("Guard")
    
    def demo_full_decision_flow(self):
        """演示完整决策流程"""
        print("\n" + "="*70)
        print("🧠 Chief Agent V5.0 完整决策流程演示")
        print("="*70)
        
        # Step 1: Scout盘前报告
        print("\n📊 [Step 1/6] Scout盘前报告")
        scout_report = ScoutReport(
            market_regime="neutral",  # bear/bull/neutral
            index_data={
                "上证指数": {"close": 3300.5, "change_pct": 0.25},
                "深证成指": {"close": 10500.3, "change_pct": -0.15},
                "创业板指": {"close": 2100.8, "change_pct": -0.45}
            },
            sector_hotspot=[
                {"name": "固态电池", "change_pct": 3.5},
                {"name": "AI算力", "change_pct": -2.1}
            ],
            risk_signals=[],  # 无特殊风险信号
            timestamp=datetime.now().isoformat()
        )
        print(f"  市场环境: {scout_report.market_regime}")
        print(f"  风险信号: {len(scout_report.risk_signals)}个")
        
        # Step 2: Sentiment舆情报告
        print("\n📰 [Step 2/6] Sentiment舆情报告")
        sentiment_report = SentimentReport(
            overall_sentiment=0.15,  # 略微乐观 (-1 to 1)
            sector_sentiment={
                "新能源": 0.35,
                "AI": -0.20,
                "半导体": 0.10,
                "地产": -0.30
            },
            hot_topics=["固态电池技术突破", "两会政策预期"],
            risk_alerts=[],
            timestamp=datetime.now().isoformat()
        )
        print(f"  整体情绪: {sentiment_report.overall_sentiment:+.2f} (略微乐观)")
        print(f"  热点话题: {', '.join(sentiment_report.hot_topics)}")
        
        # Step 3: Picker选股清单
        print("\n📋 [Step 3/6] Picker选股清单")
        picker_list = PickerList(
            selected_stocks=[
                {
                    "ts_code": "300014.SZ",
                    "name": "亿纬锂能",
                    "sector": "新能源",
                    "score": 85,
                    "change_5d": 0.05,
                    "change_20d": 0.12,
                    "volatility": 0.025,
                    "rsi": 55
                },
                {
                    "ts_code": "002460.SZ",
                    "name": "赣锋锂业",
                    "sector": "新能源",
                    "score": 82,
                    "change_5d": 0.03,
                    "change_20d": 0.08,
                    "volatility": 0.028,
                    "rsi": 52
                },
                {
                    "ts_code": "300750.SZ",
                    "name": "宁德时代",
                    "sector": "新能源",
                    "score": 88,
                    "change_5d": 0.06,
                    "change_20d": 0.15,
                    "volatility": 0.022,
                    "rsi": 58
                },
                {
                    "ts_code": "000001.SZ",
                    "name": "平安银行",
                    "sector": "银行",
                    "score": 75,
                    "change_5d": 0.01,
                    "change_20d": 0.03,
                    "volatility": 0.015,
                    "rsi": 48
                },
                {
                    "ts_code": "600519.SH",
                    "name": "贵州茅台",
                    "sector": "白酒",
                    "score": 80,
                    "change_5d": 0.02,
                    "change_20d": 0.05,
                    "volatility": 0.018,
                    "rsi": 50
                }
            ],
            selection_reason="基于动量+质量因子选股，重点关注新能源板块",
            timestamp=datetime.now().isoformat()
        )
        print(f"  选中股票: {len(picker_list.selected_stocks)}只")
        for stock in picker_list.selected_stocks:
            print(f"    - {stock['name']}({stock['ts_code']}): 评分{stock['score']}")
        
        # Step 4-6: Chief执行完整决策
        print("\n🧠 [Step 4-6] Chief综合决策")
        print("  ├─ 接收DRL Agent建议...")
        print("  ├─ 接收Portfolio Optimizer建议...")
        print("  ├─ Guard风控预检...")
        print("  └─ 综合决策...")
        
        decision = self.chief.make_decision(
            scout_report=scout_report,
            sentiment_report=sentiment_report,
            picker_list=picker_list
        )
        
        # 输出决策结果
        print("\n" + "="*70)
        print("📋 Chief决策结果")
        print("="*70)
        print(f"决策ID: {decision.decision_id}")
        print(f"决策来源: {decision.decision_source}")
        print(f"置信度: {decision.confidence:.2%}")
        print(f"风险等级: {decision.risk_level}")
        print(f"决策推理: {decision.reasoning}")
        
        print(f"\n执行计划 ({len(decision.execution_plan)}笔交易):")
        for i, plan in enumerate(decision.execution_plan, 1):
            print(f"  {i}. {plan['stock_name']}({plan['stock_code']}): "
                  f"{plan['action'].upper()} 权重{plan['target_weight']:.2%} "
                  f"金额¥{plan['target_value']:,.0f}")
        
        # 生成交易信号
        print("\n📡 生成交易信号:")
        trade_signals = self.chief.generate_signal_for_trader(decision)
        for signal in trade_signals:
            print(f"  → {signal['code']}: {signal['action'].upper()} | "
                  f"策略: {signal['strategy']} | 风险: {signal['risk_level']}")
        
        return decision
    
    def demo_drl_high_confidence(self):
        """演示DRL高置信度场景"""
        print("\n" + "="*70)
        print("🎯 场景1: DRL高置信度 (>0.7) + Guard通过")
        print("="*70)
        
        scout = ScoutReport(
            market_regime="bull",
            index_data={},
            sector_hotspot=[],
            risk_signals=[],
            timestamp=datetime.now().isoformat()
        )
        
        sentiment = SentimentReport(
            overall_sentiment=0.5,  # 乐观
            sector_sentiment={},
            hot_topics=[],
            risk_alerts=[],
            timestamp=datetime.now().isoformat()
        )
        
        picker = PickerList(
            selected_stocks=[
                {"ts_code": "300014.SZ", "name": "亿纬锂能", "sector": "新能源",
                 "change_5d": 0.08, "change_20d": 0.20, "volatility": 0.02, "rsi": 60},
                {"ts_code": "300750.SZ", "name": "宁德时代", "sector": "新能源",
                 "change_5d": 0.10, "change_20d": 0.25, "volatility": 0.018, "rsi": 65},
            ],
            selection_reason="强势板块龙头",
            timestamp=datetime.now().isoformat()
        )
        
        decision = self.chief.make_decision(scout, sentiment, picker)
        
        print(f"\n决策来源: {decision.decision_source}")
        print(f"置信度: {decision.confidence:.2%}")
        print(f"推理: {decision.reasoning}")
        print(f"预期: DRL高置信度，应采纳DRL权重建议")
    
    def demo_drl_low_confidence(self):
        """演示DRL低置信度场景"""
        print("\n" + "="*70)
        print("🎯 场景2: DRL低置信度 (<0.5)")
        print("="*70)
        
        scout = ScoutReport(
            market_regime="neutral",
            index_data={},
            sector_hotspot=[],
            risk_signals=["市场波动率上升"],
            timestamp=datetime.now().isoformat()
        )
        
        sentiment = SentimentReport(
            overall_sentiment=-0.1,  # 略偏空
            sector_sentiment={},
            hot_topics=[],
            risk_alerts=["外资流出"],
            timestamp=datetime.now().isoformat()
        )
        
        picker = PickerList(
            selected_stocks=[
                {"ts_code": "000001.SZ", "name": "平安银行", "sector": "银行",
                 "change_5d": -0.02, "change_20d": 0.01, "volatility": 0.015, "rsi": 45},
            ],
            selection_reason="防御性配置",
            timestamp=datetime.now().isoformat()
        )
        
        decision = self.chief.make_decision(scout, sentiment, picker)
        
        print(f"\n决策来源: {decision.decision_source}")
        print(f"置信度: {decision.confidence:.2%}")
        print(f"推理: {decision.reasoning}")
        print(f"预期: DRL低置信度，应使用Optimizer建议")
    
    def demo_conflict_resolution(self):
        """演示冲突解决场景"""
        print("\n" + "="*70)
        print("🎯 场景3: DRL与Optimizer冲突 → 取保守方案")
        print("="*70)
        
        scout = ScoutReport(
            market_regime="neutral",
            index_data={},
            sector_hotspot=[],
            risk_signals=[],
            timestamp=datetime.now().isoformat()
        )
        
        sentiment = SentimentReport(
            overall_sentiment=0.0,  # 中性
            sector_sentiment={},
            hot_topics=[],
            risk_alerts=[],
            timestamp=datetime.now().isoformat()
        )
        
        picker = PickerList(
            selected_stocks=[
                {"ts_code": "300014.SZ", "name": "亿纬锂能", "sector": "新能源",
                 "change_5d": 0.03, "change_20d": 0.08, "volatility": 0.025, "rsi": 52},
                {"ts_code": "600519.SH", "name": "贵州茅台", "sector": "白酒",
                 "change_5d": 0.01, "change_20d": 0.03, "volatility": 0.018, "rsi": 50},
            ],
            selection_reason="均衡配置",
            timestamp=datetime.now().isoformat()
        )
        
        decision = self.chief.make_decision(scout, sentiment, picker)
        
        print(f"\n决策来源: {decision.decision_source}")
        print(f"置信度: {decision.confidence:.2%}")
        print(f"推理: {decision.reasoning}")
        print(f"预期: 两者冲突，取仓位较低的保守方案")
    
    def demo_guard_intervention(self):
        """演示Guard风控干预场景"""
        print("\n" + "="*70)
        print("🎯 场景4: Guard风控干预 (高风险市场)")
        print("="*70)
        
        scout = ScoutReport(
            market_regime="bear",  # 熊市
            index_data={},
            sector_hotspot=[],
            risk_signals=["大盘跌破支撑位", "成交量萎缩", "北向资金大幅流出"],
            timestamp=datetime.now().isoformat()
        )
        
        sentiment = SentimentReport(
            overall_sentiment=-0.5,  # 悲观
            sector_sentiment={},
            hot_topics=[],
            risk_alerts=["恐慌情绪蔓延"],
            timestamp=datetime.now().isoformat()
        )
        
        picker = PickerList(
            selected_stocks=[
                {"ts_code": "300014.SZ", "name": "亿纬锂能", "sector": "新能源",
                 "change_5d": -0.05, "change_20d": -0.10, "volatility": 0.035, "rsi": 35},
            ],
            selection_reason="超跌反弹",
            timestamp=datetime.now().isoformat()
        )
        
        decision = self.chief.make_decision(scout, sentiment, picker)
        
        print(f"\n决策来源: {decision.decision_source}")
        print(f"风险等级: {decision.risk_level}")
        print(f"置信度: {decision.confidence:.2%}")
        print(f"推理: {decision.reasoning}")
        print(f"执行计划: {len(decision.execution_plan)}笔")
        print(f"预期: 高风险环境，Guard应降低仓位或阻止交易")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Chief Agent V5.0集成演示')
    parser.add_argument('--mode', choices=['full', 'high', 'low', 'conflict', 'guard', 'all'],
                       default='all', help='演示模式')
    parser.add_argument('--config', default='config.json', help='配置文件路径')
    
    args = parser.parse_args()
    
    demo = ChiefIntegrationDemo(config_path=args.config)
    
    if args.mode == 'full' or args.mode == 'all':
        demo.demo_full_decision_flow()
    
    if args.mode == 'high' or args.mode == 'all':
        demo.demo_drl_high_confidence()
    
    if args.mode == 'low' or args.mode == 'all':
        demo.demo_drl_low_confidence()
    
    if args.mode == 'conflict' or args.mode == 'all':
        demo.demo_conflict_resolution()
    
    if args.mode == 'guard' or args.mode == 'all':
        demo.demo_guard_intervention()
    
    print("\n" + "="*70)
    print("✅ Chief Agent V5.0演示完成")
    print("="*70)


if __name__ == "__main__":
    main()
