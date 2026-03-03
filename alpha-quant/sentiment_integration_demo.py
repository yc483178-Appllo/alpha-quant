#!/usr/bin/env python3
"""
Alpha V5.0 - Sentiment舆情分析集成演示
展示完整的舆情分析流程和Chief Agent集成
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import datetime
from modules.sentiment_pipeline import create_sentiment_pipeline, analyze_text_quick
from modules.chief_agent import create_chief_agent, ScoutReport, PickerList


class SentimentIntegrationDemo:
    """Sentiment舆情分析集成演示"""
    
    def __init__(self, config_path="config.json"):
        self.config_path = config_path
        self.sentiment = create_sentiment_pipeline(config_path)
        self.chief = create_chief_agent(config_path)
    
    def demo_text_analysis(self):
        """演示文本情绪分析"""
        print("\n" + "="*70)
        print("📰 文本情绪分析演示")
        print("="*70)
        
        test_texts = [
            "宁德时代发布超预期财报，业绩暴增，主力加仓，股价突破新高",
            "某科技股业绩变脸，商誉减值超10亿，公司股价跌停，投资者恐慌",
            "银行板块整体表现平稳，成交量正常，市场观望情绪浓厚",
            "固态电池技术突破！多家企业宣布量产计划，行业迎来大利好",
            "地产股持续低迷，资金外流明显，政策面暂无利好支撑"
        ]
        
        for text in test_texts:
            result = analyze_text_quick(text)
            emoji = "🟢" if result['sentiment'] == 'bullish' else ("🔴" if result['sentiment'] == 'bearish' else "⚪")
            print(f"\n{emoji} {text[:40]}...")
            print(f"   情绪分数: {result['score']:+.2f} | 标签: {result['sentiment']} | 置信度: {result['confidence']:.2f}")
            if result['related_codes']:
                print(f"   相关股票: {', '.join(result['related_codes'])}")
    
    def demo_news_batch_processing(self):
        """演示新闻批量处理"""
        print("\n" + "="*70)
        print("📊 新闻批量处理演示")
        print("="*70)
        
        # 模拟新闻数据
        news_items = [
            {
                "title": "固态电池技术突破，行业迎来大利好",
                "content": "多家企业宣布固态电池量产计划，预计明年实现大规模商业化",
                "source": "major_news",
                "pub_date": datetime.now().isoformat()
            },
            {
                "title": "宁德时代Q4业绩超预期，净利润同比增长80%",
                "content": "公司发布财报，受益于新能源车销量增长，业绩大幅改善",
                "source": "analyst_reports",
                "pub_date": datetime.now().isoformat()
            },
            {
                "title": "某科技股业绩变脸，商誉减值超10亿",
                "content": "公司股价跌停，投资者恐慌抛售，监管发问询函",
                "source": "major_news",
                "pub_date": datetime.now().isoformat()
            },
            {
                "title": "地产板块持续低迷，资金外流明显",
                "content": "多家房企债务压力大，政策面暂无利好支撑",
                "source": "social_sentiment",
                "pub_date": datetime.now().isoformat()
            },
            {
                "title": "AI算力需求爆发，芯片龙头订单爆满",
                "content": "受益于大模型训练需求，GPU订单排期已至明年",
                "source": "major_news",
                "pub_date": datetime.now().isoformat()
            }
        ]
        
        results = self.sentiment.process_news_batch(news_items)
        
        print(f"\n处理 {len(news_items)} 条新闻:\n")
        for i, r in enumerate(results, 1):
            emoji = "🟢" if r['sentiment'] == 'bullish' else ("🔴" if r['sentiment'] == 'bearish' else "⚪")
            print(f"{i}. {emoji} {r['title'][:35]}...")
            print(f"   原始分数: {r['raw_score']:+.2f} | 加权分数: {r['weighted_score']:+.2f}")
            print(f"   来源: {r['source']} | 情绪: {r['sentiment']}")
    
    def demo_sector_sentiment(self):
        """演示板块情绪分析"""
        print("\n" + "="*70)
        print("📈 板块情绪排名演示")
        print("="*70)
        
        # 先处理一些模拟新闻来填充数据
        news_items = [
            {"title": "新能源政策利好", "content": "", "source": "major_news", "pub_date": datetime.now().isoformat()},
            {"title": "银行股业绩稳健", "content": "", "source": "major_news", "pub_date": datetime.now().isoformat()},
            {"title": "科技股回调", "content": "", "source": "major_news", "pub_date": datetime.now().isoformat()},
        ]
        self.sentiment.process_news_batch(news_items)
        
        sector_scores = self.sentiment.get_sector_sentiment()
        
        print("\n板块情绪排名:")
        for i, (sector, score) in enumerate(sector_scores.items(), 1):
            emoji = "🟢" if score > 0.2 else ("🔴" if score < -0.2 else "⚪")
            bar = "█" * int(abs(score) * 20)
            print(f"{i:2d}. {emoji} {sector:8s} {score:+.2f} {bar}")
    
    def demo_sentiment_signals(self):
        """演示情绪交易信号生成"""
        print("\n" + "="*70)
        print("📡 情绪交易信号生成演示")
        print("="*70)
        
        # 模拟股票池
        stock_pool = ["300750", "601012", "002594", "600519", "000858", "601398"]
        
        # 先处理一些新闻来生成情绪数据
        news_items = [
            {"title": "宁德时代业绩暴增，主力加仓", "content": "", "source": "major_news", "pub_date": datetime.now().isoformat()},
            {"title": "茅台批价上涨，渠道库存健康", "content": "", "source": "analyst_reports", "pub_date": datetime.now().isoformat()},
            {"title": "银行股业绩稳健，分红预期好", "content": "", "source": "major_news", "pub_date": datetime.now().isoformat()},
        ]
        self.sentiment.process_news_batch(news_items)
        
        signals = self.sentiment.generate_sentiment_signals(stock_pool)
        
        print(f"\n股票池: {len(stock_pool)}只")
        print(f"生成强信号: {len(signals)}条\n")
        
        for signal in signals:
            emoji = "🟢 BUY" if signal['action'] == 'buy' else "🔴 SELL"
            print(f"{emoji} {signal['code']}")
            print(f"   情绪分数: {signal['sentiment_score']:+.2f}")
            print(f"   情绪动量: {signal['sentiment_momentum']:+.2f}")
            print(f"   置信度: {signal['confidence']:.2%}")
    
    def demo_scout_report(self):
        """演示Scout盘前舆情报告生成"""
        print("\n" + "="*70)
        print("📋 Scout盘前舆情报告生成演示")
        print("="*70)
        
        stock_pool = ["300750", "601012", "002594", "600519", "000858", "601398", "300760", "603259"]
        
        # 处理模拟新闻
        news_items = [
            {"title": "新能源政策利好，固态电池突破", "content": "", "source": "major_news", "pub_date": datetime.now().isoformat()},
            {"title": "白酒消费复苏，茅台批价上涨", "content": "", "source": "analyst_reports", "pub_date": datetime.now().isoformat()},
            {"title": "医药集采落地，创新药企受益", "content": "", "source": "major_news", "pub_date": datetime.now().isoformat()},
        ]
        self.sentiment.process_news_batch(news_items)
        
        report = self.sentiment.generate_scout_report(stock_pool)
        
        print(f"\n报告类型: {report['report_type']}")
        print(f"生成时间: {report['generated_at']}")
        print(f"处理新闻: {report['total_news_processed']}条")
        
        if report['market_sentiment_overview']:
            overview = report['market_sentiment_overview']
            print(f"\n市场整体情绪:")
            print(f"  平均分数: {overview['average_score']:+.2f}")
            print(f"  看涨: {overview['bullish_count']}只 | 看跌: {overview['bearish_count']}只 | 中性: {overview['neutral_count']}只")
        
        print(f"\n板块情绪排名:")
        for sector, score in list(report['sector_ranking'].items())[:5]:
            print(f"  {sector}: {score:+.2f}")
        
        if report['anomaly_alerts']:
            print(f"\n⚠️ 异常警报:")
            for alert in report['anomaly_alerts']:
                print(f"  {alert['code']}: {alert['type']} (幅度: {alert['magnitude']:.2f})")
    
    def demo_chief_integration(self):
        """演示与Chief Agent集成"""
        print("\n" + "="*70)
        print("🔗 Sentiment与Chief Agent集成演示")
        print("="*70)
        
        # 1. 生成Sentiment报告
        stock_pool = ["300750", "601012", "600519", "601398"]
        
        news_items = [
            {"title": "新能源政策利好，固态电池突破", "content": "", "source": "major_news", "pub_date": datetime.now().isoformat()},
            {"title": "白酒消费复苏，茅台批价上涨", "content": "", "source": "analyst_reports", "pub_date": datetime.now().isoformat()},
        ]
        self.sentiment.process_news_batch(news_items)
        
        # 获取SentimentReport格式数据
        sentiment_data = self.sentiment.generate_sentiment_report_for_chief()
        
        print("\n📰 Sentiment报告:")
        print(f"  整体情绪: {sentiment_data['overall_sentiment']:+.2f}")
        print(f"  板块情绪: {sentiment_data['sector_sentiment']}")
        print(f"  热点话题: {len(sentiment_data['hot_topics'])}个")
        print(f"  风险警报: {len(sentiment_data['risk_alerts'])}个")
        
        # 2. 创建Chief Agent输入
        from modules.chief_agent import SentimentReport
        
        sentiment_report = SentimentReport(
            overall_sentiment=sentiment_data['overall_sentiment'],
            sector_sentiment=sentiment_data['sector_sentiment'],
            hot_topics=sentiment_data['hot_topics'],
            risk_alerts=sentiment_data['risk_alerts'],
            timestamp=sentiment_data['timestamp']
        )
        
        # 3. 创建其他输入
        scout_report = ScoutReport(
            market_regime="neutral",
            index_data={},
            sector_hotspot=[],
            risk_signals=[],
            timestamp=datetime.now().isoformat()
        )
        
        picker_list = PickerList(
            selected_stocks=[
                {"ts_code": "300750.SZ", "name": "宁德时代", "sector": "新能源", "score": 88},
                {"ts_code": "600519.SH", "name": "贵州茅台", "sector": "消费", "score": 85},
            ],
            selection_reason="基于舆情情绪选股",
            timestamp=datetime.now().isoformat()
        )
        
        # 4. Chief决策
        print("\n🧠 Chief Agent决策中...")
        decision = self.chief.make_decision(scout_report, sentiment_report, picker_list)
        
        print(f"\n决策结果:")
        print(f"  来源: {decision.decision_source}")
        print(f"  置信度: {decision.confidence:.2%}")
        print(f"  风险等级: {decision.risk_level}")
        print(f"  推理: {decision.reasoning}")
        print(f"  执行计划: {len(decision.execution_plan)}笔交易")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Sentiment舆情分析集成演示')
    parser.add_argument('--mode', 
                       choices=['text', 'news', 'sector', 'signals', 'report', 'chief', 'all'],
                       default='all', help='演示模式')
    parser.add_argument('--config', default='config.json', help='配置文件路径')
    
    args = parser.parse_args()
    
    demo = SentimentIntegrationDemo(config_path=args.config)
    
    if args.mode == 'text' or args.mode == 'all':
        demo.demo_text_analysis()
    
    if args.mode == 'news' or args.mode == 'all':
        demo.demo_news_batch_processing()
    
    if args.mode == 'sector' or args.mode == 'all':
        demo.demo_sector_sentiment()
    
    if args.mode == 'signals' or args.mode == 'all':
        demo.demo_sentiment_signals()
    
    if args.mode == 'report' or args.mode == 'all':
        demo.demo_scout_report()
    
    if args.mode == 'chief' or args.mode == 'all':
        demo.demo_chief_integration()
    
    print("\n" + "="*70)
    print("✅ Sentiment舆情分析演示完成")
    print("="*70)


if __name__ == "__main__":
    main()
