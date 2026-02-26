# daily_report_generator.py --- 智能收盘复盘报告生成器
# 自动生成包含八个部分的完整复盘报告

import os
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from loguru import logger
import requests

# 导入 Alpha Quant 模块
from modules.data_provider import data_provider
from modules.technical_analysis import technical_analyzer
from modules.risk_manager import risk_manager
from modules.report_generator import report_generator
from modules.notification import notification_manager
import config


class DailyReportGenerator:
    """每日收盘复盘报告生成器"""
    
    def __init__(self):
        self.report_date = datetime.now().strftime("%Y-%m-%d")
        self.report_data = {}
        
    def generate_full_report(self) -> str:
        """生成完整复盘报告"""
        logger.info(f"开始生成 {self.report_date} 收盘复盘报告...")
        
        # 检查是否为交易日
        if not self._is_trading_day():
            logger.info("今日非交易日，跳过报告生成")
            return ""
        
        # 收集数据
        self._collect_market_data()
        self._collect_sector_data()
        self._collect_portfolio_data()
        self._collect_strategy_data()
        
        # 生成报告
        report = self._build_report()
        
        # 保存报告
        self._save_report(report)
        
        # 推送简版
        self._push_summary()
        
        return report
    
    def _is_trading_day(self) -> bool:
        """检查今日是否为交易日"""
        try:
            today = datetime.now().strftime("%Y%m%d")
            df = data_provider.pro.trade_cal(exchange='SSE', start_date=today, end_date=today)
            if not df.empty:
                return df.iloc[0]['is_open'] == 1
        except Exception as e:
            logger.error(f"交易日检查失败: {e}")
        # 默认假设是交易日（周一至周五）
        return datetime.now().weekday() < 5
    
    def _collect_market_data(self):
        """收集大盘数据"""
        logger.info("收集大盘数据...")
        
        indices = {
            "上证指数": "000001.SH",
            "深证成指": "399001.SZ",
            "创业板指": "399006.SZ"
        }
        
        market_data = {}
        for name, code in indices.items():
            try:
                df = data_provider.get_index_daily(code)
                if not df.empty and len(df) >= 2:
                    today = df.iloc[-1]
                    yesterday = df.iloc[-2]
                    
                    change_pct = (today['close'] - yesterday['close']) / yesterday['close'] * 100
                    
                    market_data[name] = {
                        "close": today['close'],
                        "change_pct": change_pct,
                        "volume": today.get('vol', 0),
                        "amount": today.get('amount', 0)
                    }
            except Exception as e:
                logger.error(f"获取 {name} 数据失败: {e}")
        
        self.report_data['market'] = market_data
        
        # 获取成交额
        try:
            sh_df = data_provider.get_index_daily("000001.SH")
            sz_df = data_provider.get_index_daily("399001.SZ")
            
            if not sh_df.empty and not sz_df.empty:
                today_amount = sh_df.iloc[-1].get('amount', 0) + sz_df.iloc[-1].get('amount', 0)
                yesterday_amount = sh_df.iloc[-2].get('amount', 0) + sz_df.iloc[-2].get('amount', 0)
                
                self.report_data['total_amount'] = today_amount
                self.report_data['amount_change'] = today_amount - yesterday_amount
        except Exception as e:
            logger.error(f"获取成交额失败: {e}")
    
    def _collect_sector_data(self):
        """收集板块数据"""
        logger.info("收集板块数据...")
        
        try:
            # 获取板块涨幅排行
            sector_df = data_provider.get_sector_hotspot()
            if not sector_df.empty:
                top_sectors = sector_df.head(5).to_dict('records')
                self.report_data['top_sectors'] = top_sectors
        except Exception as e:
            logger.error(f"获取板块数据失败: {e}")
            self.report_data['top_sectors'] = []
    
    def _collect_portfolio_data(self):
        """收集持仓数据"""
        logger.info("收集持仓数据...")
        
        # 从配置文件或数据库读取持仓
        portfolio = getattr(config, 'PORTFOLIO', {})
        
        portfolio_data = {
            "positions": [],
            "total_pnl": 0,
            "total_pnl_pct": 0
        }
        
        total_value = 0
        total_cost = 0
        
        for code, pos in portfolio.items():
            try:
                df = data_provider.get_stock_daily(code)
                if not df.empty:
                    today = df.iloc[-1]
                    current_price = today['close']
                    
                    pnl = (current_price - pos['cost']) * pos['amount']
                    pnl_pct = (current_price - pos['cost']) / pos['cost'] * 100
                    
                    position_value = current_price * pos['amount']
                    position_cost = pos['cost'] * pos['amount']
                    
                    portfolio_data['positions'].append({
                        "code": code,
                        "name": pos.get('name', code),
                        "amount": pos['amount'],
                        "cost": pos['cost'],
                        "current": current_price,
                        "pnl": pnl,
                        "pnl_pct": pnl_pct
                    })
                    
                    total_value += position_value
                    total_cost += position_cost
            except Exception as e:
                logger.error(f"获取持仓 {code} 数据失败: {e}")
        
        if total_cost > 0:
            portfolio_data['total_pnl'] = total_value - total_cost
            portfolio_data['total_pnl_pct'] = (total_value - total_cost) / total_cost * 100
        
        self.report_data['portfolio'] = portfolio_data
    
    def _collect_strategy_data(self):
        """收集策略执行数据"""
        logger.info("收集策略数据...")
        
        # 从日志或数据库读取今日信号
        self.report_data['strategy'] = {
            "signals_sent": 0,
            "signals_executed": 0,
            "execution_rate": 0,
            "risk_events": []
        }
    
    def _build_report(self) -> str:
        """构建报告内容"""
        report = f"""# 📊 Alpha Quant 收盘复盘报告 — {self.report_date}

---

## 第一部分：今日大盘总结

### 三大指数表现
"""
        
        # 指数数据
        for name, data in self.report_data.get('market', {}).items():
            emoji = "🟢" if data['change_pct'] > 0 else "🔴"
            report += f"| {name} | {data['close']:.2f} | {data['change_pct']:+.2f}% |\n"
        
        # 成交额
        total_amount = self.report_data.get('total_amount', 0)
        amount_change = self.report_data.get('amount_change', 0)
        report += f"\n**两市成交额**: ¥{total_amount/1e8:.2f}亿 ({amount_change/1e8:+.2f}亿)\n"
        
        # 情绪评分
        market_change = list(self.report_data.get('market', {}).values())[0].get('change_pct', 0) if self.report_data.get('market') else 0
        sentiment_score = min(10, max(1, 5 + market_change / 2))
        report += f"**情绪评分**: {sentiment_score:.1f}/10\n"
        
        # 情绪周期
        if sentiment_score >= 8:
            cycle = "🔥 亢奋期"
        elif sentiment_score >= 6:
            cycle = "📈 上升期"
        elif sentiment_score >= 4:
            cycle = "➡️ 震荡期"
        else:
            cycle = "📉 调整期"
        report += f"**情绪周期**: {cycle}\n"
        
        # 第二部分：热点板块
        report += f"""
---

## 第二部分：热点板块复盘

### 今日涨幅前5板块
"""
        for i, sector in enumerate(self.report_data.get('top_sectors', [])[:5], 1):
            report += f"{i}. {sector.get('name', 'Unknown')}: {sector.get('change_pct', 0):+.2f}%\n"
        
        report += "\n**预测准确率自评**: 待评估\n"
        
        # 第三部分：持仓表现
        portfolio = self.report_data.get('portfolio', {})
        report += f"""
---

## 第三部分：持仓账户表现

### 持仓明细
"""
        if portfolio.get('positions'):
            report += "| 代码 | 名称 | 持仓 | 成本 | 现价 | 盈亏 | 盈亏率 |\n"
            report += "|------|------|------|------|------|------|--------|\n"
            
            for pos in portfolio['positions']:
                emoji = "🟢" if pos['pnl'] > 0 else "🔴"
                report += f"| {pos['code']} | {pos['name']} | {pos['amount']} | {pos['cost']:.2f} | {pos['current']:.2f} | {emoji}¥{pos['pnl']:,.0f} | {pos['pnl_pct']:+.2f}% |\n"
            
            total_pnl = portfolio.get('total_pnl', 0)
            total_pnl_pct = portfolio.get('total_pnl_pct', 0)
            emoji = "🟢" if total_pnl > 0 else "🔴"
            report += f"\n**总浮盈亏**: {emoji}¥{total_pnl:,.0f} ({total_pnl_pct:+.2f}%)\n"
        else:
            report += "暂无持仓\n"
        
        # 第四部分：策略执行
        strategy = self.report_data.get('strategy', {})
        report += f"""
---

## 第四部分：策略执行评估

- **今日发出信号数**: {strategy.get('signals_sent', 0)}
- **实际执行率**: {strategy.get('execution_rate', 0):.1f}%
- **风控触发记录**: {len(strategy.get('risk_events', []))} 次

"""
        
        # 第五部分：明日关注
        report += f"""
---

## 第五部分：明日关注标的

### 涨停板高开概率分析（前3）
待分析...

### 异常放量个股
待筛选...

"""
        
        # 第六部分：策略迭代
        report += f"""
---

## 第六部分：策略迭代建议

### 本周策略胜率统计
待统计...

### AI 优化建议
- 根据近期市场特征，建议关注...

"""
        
        # 第七部分：明日操作计划
        report += f"""
---

## 第七部分：明日操作计划

| 代码 | 方向 | 目标价位 | 止损价位 | 理由 |
|------|------|----------|----------|------|
| 待添加 | - | - | - | - |

"""
        
        # 第八部分：风险提示
        report += f"""
---

## 第八部分：风险提示

### 近期重点规避
- 政策风险：关注...
- 季节性风险：...
- 技术面风险：...

### 重要事件提醒
- 即将解禁个股：...
- 财报发布窗口：...

---

*报告生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}*  
*数据来源: Tushare / AkShare*
"""
        
        return report
    
    def _save_report(self, report: str):
        """保存报告到文件"""
        # 创建目录
        report_dir = os.path.join("reports", "daily")
        os.makedirs(report_dir, exist_ok=True)
        
        # 保存完整报告
        filename = f"{self.report_date}-daily.md"
        filepath = os.path.join(report_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"报告已保存: {filepath}")
    
    def _push_summary(self):
        """推送简版报告到飞书"""
        try:
            # 构建简版内容（第一、三、七部分）
            summary = self._build_summary()
            
            # 推送通知
            webhook = os.getenv("FEISHU_WEBHOOK_URL", "")
            if webhook:
                requests.post(webhook, json={
                    "msg_type": "interactive",
                    "card": {
                        "header": {
                            "title": {"tag": "plain_text", "content": f"📊 {self.report_date} 收盘复盘"},
                            "template": "blue"
                        },
                        "elements": [{"tag": "markdown", "content": summary}]
                    }
                }, timeout=5)
                
                logger.info("简版报告已推送至飞书")
        except Exception as e:
            logger.error(f"推送失败: {e}")
    
    def _build_summary(self) -> str:
        """构建简版报告"""
        # 第一部分摘要
        market = self.report_data.get('market', {})
        sh_data = market.get('上证指数', {})
        
        summary = f"**大盘**: 沪指 {sh_data.get('change_pct', 0):+.2f}%\n\n"
        
        # 第三部分摘要
        portfolio = self.report_data.get('portfolio', {})
        if portfolio.get('positions'):
            total_pnl = portfolio.get('total_pnl', 0)
            emoji = "🟢" if total_pnl > 0 else "🔴"
            summary += f"**持仓**: {emoji}¥{total_pnl:,.0f}\n\n"
        
        # 第七部分摘要
        summary += "**明日计划**: 待更新\n"
        
        return summary


def main():
    """主入口"""
    generator = DailyReportGenerator()
    report = generator.generate_full_report()
    
    if report:
        print(report)
    else:
        print("今日非交易日或报告生成失败")


if __name__ == "__main__":
    main()
