#!/usr/bin/env python3
"""
Alpha Quant - A股量化交易系统主程序
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 首先加载环境变量
from env_loader import get_env
env = get_env()

import argparse
from datetime import datetime, timedelta
from modules.data_provider import data_provider
from modules.technical_analysis import technical_analyzer
from modules.risk_manager import risk_manager
from modules.stock_screener import stock_screener
from modules.report_generator import report_generator
from modules.notification import notification_manager
from modules.logger import log
import config

def premarket_analysis():
    """盘前分析"""
    print("=" * 60)
    print("📊 Alpha 盘前分析启动")
    print("=" * 60)
    
    # 1. 获取大盘指数数据
    print("\n[1/4] 获取大盘数据...")
    indices = {
        "上证指数": "000001.SH",
        "深证成指": "399001.SZ",
        "创业板指": "399006.SZ"
    }
    
    index_data = {}
    for name, code in indices.items():
        try:
            df = data_provider.get_index_daily(code)
            if not df.empty:
                df = technical_analyzer.calculate_ma(df)
                df = technical_analyzer.calculate_macd(df)
                df = technical_analyzer.calculate_rsi(df)
                
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else latest
                
                trend_analysis = technical_analyzer.analyze_trend(df)
                
                index_data[name] = {
                    "close": float(latest['close']),
                    "change_pct": (float(latest['close']) - float(prev['close'])) / float(prev['close']) * 100 if 'close' in prev else 0,
                    "trend": trend_analysis['trend'],
                    "confidence": trend_analysis['confidence']
                }
                print(f"  ✓ {name}: {latest['close']:.2f} ({index_data[name]['change_pct']:+.2f}%)")
        except Exception as e:
            print(f"  ✗ {name}: {e}")
    
    # 2. 获取板块热点
    print("\n[2/4] 获取板块热点...")
    try:
        sector_df = data_provider.get_sector_hotspot()
        if not sector_df.empty:
            print(f"  ✓ 获取到 {len(sector_df)} 个板块数据")
        else:
            print("  ⚠ 板块数据为空")
    except Exception as e:
        print(f"  ✗ 板块数据获取失败: {e}")
        sector_df = None
    
    # 3. 选股
    print("\n[3/4] 执行选股策略...")
    try:
        selected_stocks = stock_screener.screen_stocks(max_results=5)
        print(f"  ✓ 筛选出 {len(selected_stocks)} 只股票")
        for stock in selected_stocks:
            print(f"    - {stock['name']}({stock['ts_code']}): 评分 {stock['score']}")
    except Exception as e:
        print(f"  ✗ 选股失败: {e}")
        selected_stocks = []
    
    # 4. 风控检查
    print("\n[4/4] 风控状态检查...")
    sh_change = index_data.get('上证指数', {}).get('change_pct', 0)
    risk_status = {
        'fuse': sh_change <= -3,
        'fuse_message': f'大盘跌幅 {sh_change:.2f}%，已触发熔断' if sh_change <= -3 else '正常',
        'cautious': sh_change < -1
    }
    print(f"  ✓ 风控检查完成")
    
    # 生成报告
    print("\n" + "=" * 60)
    print("生成报告中...")
    report = report_generator.generate_premarket_report(
        index_data=index_data,
        sector_hotspot=sector_df if sector_df is not None else [],
        selected_stocks=selected_stocks,
        risk_status=risk_status
    )
    
    # 保存报告
    report_file = f"reports/premarket_{datetime.now().strftime('%Y%m%d')}.md"
    os.makedirs("reports", exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ 报告已保存: {report_file}")
    print("=" * 60)
    
    return report

def intraday_monitor():
    """盘中监控"""
    print("=" * 60)
    print("⚡ Alpha 盘中监控")
    print("=" * 60)
    
    # 获取大盘实时数据
    try:
        df = data_provider.get_index_daily("000001.SH")
        if not df.empty and len(df) >= 2:
            latest = df.iloc[-1]
            prev = df.iloc[-2]
            change_pct = (float(latest['close']) - float(prev['close'])) / float(prev['close']) * 100
            
            print(f"上证指数: {latest['close']:.2f} ({change_pct:+.2f}%)")
            
            # 风控检查
            risk_messages = []
            if change_pct <= -3:
                risk_messages.append(f"⚡ 大盘跌幅 {change_pct:.2f}% 触发熔断，禁止买入")
            elif change_pct < -2:
                risk_messages.append(f"⚠️ 大盘跌幅 {change_pct:.2f}%，谨慎操作")
            
            if risk_messages:
                print("\n风险警报:")
                for msg in risk_messages:
                    print(f"  {msg}")
            else:
                print("✅ 暂无风险警报")
    except Exception as e:
        print(f"监控失败: {e}")
    
    print("=" * 60)

def closing_report():
    """收盘复盘"""
    print("=" * 60)
    print("📈 Alpha 收盘复盘")
    print("=" * 60)
    
    # 获取大盘数据
    indices = {
        "上证指数": "000001.SH",
        "深证成指": "399001.SZ",
        "创业板指": "399006.SZ"
    }
    
    index_summary = {}
    for name, code in indices.items():
        try:
            df = data_provider.get_index_daily(code)
            if not df.empty:
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) > 1 else latest
                
                index_summary[name] = {
                    "open": float(latest.get('open', latest['close'])),
                    "high": float(latest.get('high', latest['close'])),
                    "low": float(latest.get('low', latest['close'])),
                    "close": float(latest['close']),
                    "change_pct": (float(latest['close']) - float(prev['close'])) / float(prev['close']) * 100 if 'close' in prev else 0
                }
                print(f"✓ {name} 数据获取成功")
        except Exception as e:
            print(f"✗ {name}: {e}")
    
    # 生成报告
    report = report_generator.generate_closing_report(
        index_summary=index_summary,
        portfolio_pnl=0,  # 暂无持仓数据
        market_sentiment={},
        tomorrow_watchlist=[]
    )
    
    # 保存报告
    report_file = f"reports/closing_{datetime.now().strftime('%Y%m%d')}.md"
    os.makedirs("reports", exist_ok=True)
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\n✅ 收盘报告已保存: {report_file}")
    print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description='Alpha Quant - A股量化交易系统')
    parser.add_argument('command', choices=['premarket', 'intraday', 'closing', 'test'],
                       help='执行命令: premarket(盘前分析), intraday(盘中监控), closing(收盘复盘), test(测试)')
    
    args = parser.parse_args()
    
    if args.command == 'premarket':
        report = premarket_analysis()
        print("\n" + report)
    elif args.command == 'intraday':
        intraday_monitor()
    elif args.command == 'closing':
        closing_report()
    elif args.command == 'test':
        print("测试数据连接...")
        try:
            df = data_provider.get_index_daily("000001.SH")
            if not df.empty:
                print(f"✓ Tushare 连接正常，获取到 {len(df)} 条数据")
            else:
                print("✗ Tushare 连接失败")
        except Exception as e:
            print(f"✗ 测试失败: {e}")

if __name__ == "__main__":
    main()
