"""
报告生成模块
"""
import pandas as pd
from datetime import datetime
from typing import Dict, List
import config

class ReportGenerator:
    """报告生成器"""
    
    @staticmethod
    def generate_premarket_report(
        index_data: Dict,
        sector_hotspot: pd.DataFrame,
        selected_stocks: List[Dict],
        risk_status: Dict
    ) -> str:
        """生成盘前报告"""
        
        report = f"""# 📊 Alpha 盘前调研报告
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**分析师**: Alpha (AI Quant)

---

## 一、大盘情绪分析

| 指数 | 最新点位 | 涨跌幅 | 趋势判断 | 置信度 |
|------|----------|--------|----------|--------|
"""
        
        for idx_name, data in index_data.items():
            trend_emoji = "📈" if data['trend'] == 'bullish' else "📉" if data['trend'] == 'bearish' else "➡️"
            report += f"| {idx_name} | {data['close']:.2f} | {data['change_pct']:+.2f}% | {trend_emoji} {data['trend']} | {data['confidence']}% |\n"
        
        report += f"""

## 二、板块热点追踪

| 排名 | 板块名称 | 涨跌幅 | 成交额 | 资金流向 |
|------|----------|--------|--------|----------|
"""
        
        if not sector_hotspot.empty:
            for i, (_, row) in enumerate(sector_hotspot.head(10).iterrows(), 1):
                change_emoji = "🔴" if row.get('涨跌幅', 0) > 0 else "🟢"
                report += f"| {i} | {row.get('名称', 'N/A')} | {change_emoji} {row.get('涨跌幅', 0):+.2f}% | {row.get('成交额', 'N/A')} | {row.get('主力净流入', 'N/A')} |\n"
        
        report += f"""

## 三、选股清单

**筛选标准**: 技术面多头 + 量能放大 + 趋势确认  
**风险等级说明**: 🔴 高 | 🟡 中 | 🟢 低

| 代码 | 名称 | 评分 | 趋势 | 置信度 | 现价 | 涨跌幅 | RSI | 风险等级 |
|------|------|------|------|--------|------|--------|-----|----------|
"""
        
        for stock in selected_stocks:
            risk_emoji = "🟢" if stock['score'] >= 80 else "🟡" if stock['score'] >= 70 else "🔴"
            trend_emoji = "📈" if stock['trend'] == 'bullish' else "📉" if stock['trend'] == 'bearish' else "➡️"
            report += f"| {stock['ts_code']} | {stock['name']} | {stock['score']} | {trend_emoji} {stock['trend']} | {stock['confidence']}% | {stock['close']:.2f} | {stock['change_pct']:+.2f}% | {stock['rsi']:.1f} | {risk_emoji} |\n"
        
        report += f"""

## 四、风控状态

| 检查项 | 状态 | 说明 |
|--------|------|------|
| 大盘熔断 | {'⚡ 触发' if risk_status.get('fuse') else '✅ 正常'} | {risk_status.get('fuse_message', '-')} |
| 单日亏损 | {'🚨 超限' if risk_status.get('daily_loss') else '✅ 正常'} | {risk_status.get('daily_loss_message', '-')} |
| 连续亏损 | {'🛡️ 防守' if risk_status.get('consecutive') else '✅ 正常'} | {risk_status.get('consecutive_message', '-')} |

**今日操作建议**: {'⚠️ 谨慎操作，严格风控' if risk_status.get('cautious') else '✅ 正常交易'}

---

*免责声明: 本报告由 AI 生成，仅供参考，不构成投资建议。投资有风险，入市需谨慎。*
"""
        return report
    
    @staticmethod
    def generate_intraday_alert(
        index_change: float,
        risk_messages: List[str],
        hot_sectors: List[str]
    ) -> str:
        """生成盘中预警"""
        
        alert = f"""# ⚡ Alpha 盘中监控预警
**时间**: {datetime.now().strftime('%H:%M:%S')}  
**大盘涨跌**: {index_change:+.2f}%

---

## 风险警报
"""
        if risk_messages:
            for msg in risk_messages:
                alert += f"- {msg}\n"
        else:
            alert += "✅ 暂无风险警报\n"
        
        alert += f"""

## 活跃板块
{', '.join(hot_sectors) if hot_sectors else '暂无异常'}

---
*实时监控中...*
"""
        return alert
    
    @staticmethod
    def generate_closing_report(
        index_summary: Dict,
        portfolio_pnl: float,
        market_sentiment: Dict,
        tomorrow_watchlist: List[str]
    ) -> str:
        """生成收盘复盘报告"""
        
        report = f"""# 📈 Alpha 收盘复盘报告
**日期**: {datetime.now().strftime('%Y-%m-%d')}  
**生成时间**: {datetime.now().strftime('%H:%M:%S')}

---

## 一、大盘回顾

| 指数 | 开盘 | 最高 | 最低 | 收盘 | 涨跌幅 |
|------|------|------|------|------|--------|
"""
        
        for idx_name, data in index_summary.items():
            report += f"| {idx_name} | {data['open']:.2f} | {data['high']:.2f} | {data['low']:.2f} | {data['close']:.2f} | {data['change_pct']:+.2f}% |\n"
        
        pnl_emoji = "📈" if portfolio_pnl >= 0 else "📉"
        report += f"""

## 二、持仓表现

**今日盈亏**: {pnl_emoji} {portfolio_pnl:+.2f}%  
**累计盈亏**: {portfolio_pnl:+.2f}%

## 三、市场情绪

| 指标 | 数值 | 解读 |
|------|------|------|
| 涨跌家数比 | {market_sentiment.get('up_down_ratio', 'N/A')} | {market_sentiment.get('sentiment', '中性')} |
| 涨停家数 | {market_sentiment.get('limit_up_count', 'N/A')} | {'🔥 活跃' if market_sentiment.get('limit_up_count', 0) > 50 else '❄️ 低迷'} |
| 跌停家数 | {market_sentiment.get('limit_down_count', 'N/A')} | {'⚠️ 恐慌' if market_sentiment.get('limit_down_count', 0) > 20 else '正常'} |
| 成交额 | {market_sentiment.get('total_amount', 'N/A')} 亿 | {'💰 放量' if market_sentiment.get('amount_change', 0) > 0 else '📉 缩量'} |

## 四、明日关注

{chr(10).join(['- ' + code for code in tomorrow_watchlist]) if tomorrow_watchlist else '暂无'}

## 五、策略优化建议

{market_sentiment.get('suggestion', '继续观察市场走势，严格执行风控规则。')}

---
*复盘完成，准备明日交易*
"""
        return report

# 全局实例
report_generator = ReportGenerator()
