"""
模块一：市场热点板块调研（每日 09:00）
盘前市场全景扫描，为选股提供方向和依据
"""
import akshare as ak
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List
from modules.config_manager import config_manager
from modules.logger import log
from modules.notification import notification_manager

class MarketResearch:
    """市场研究员"""
    
    def __init__(self):
        self.is_trade_date = self._check_trade_date()
    
    def _check_trade_date(self) -> bool:
        """检查今日是否为交易日"""
        try:
            today = datetime.now().strftime('%Y%m%d')
            df = ak.tool_trade_date_hist_sina()
            trade_dates = set(df['trade_date'].astype(str).tolist())
            return today in trade_dates
        except Exception as e:
            log.error(f"交易日历检查失败: {e}")
            return True  # 默认继续执行
    
    def get_index_data(self) -> Dict:
        """获取大盘指数数据"""
        log.info("📊 获取大盘指数数据")
        
        try:
            # 上证指数
            sh_df = ak.index_zh_a_hist(symbol="sh000001", period="daily", start_date="20250220")
            # 深证成指
            sz_df = ak.index_zh_a_hist(symbol="sz399001", period="daily", start_date="20250220")
            # 创业板指
            cy_df = ak.index_zh_a_hist(symbol="sz399006", period="daily", start_date="20250220")
            
            result = {}
            for name, df in [("上证指数", sh_df), ("深证成指", sz_df), ("创业板指", cy_df)]:
                if not df.empty and len(df) >= 2:
                    latest = df.iloc[-1]
                    prev = df.iloc[-2]
                    change_pct = (latest['收盘'] - prev['收盘']) / prev['收盘'] * 100
                    result[name] = {
                        "close": latest['收盘'],
                        "change_pct": change_pct,
                        "volume": latest['成交量'] if '成交量' in latest else 0
                    }
            return result
        except Exception as e:
            log.error(f"获取指数数据失败: {e}")
            return {}
    
    def get_market_sentiment(self) -> Dict:
        """获取市场情绪数据"""
        log.info("📈 获取市场情绪数据")
        
        try:
            # 获取全市场股票
            df = ak.stock_zh_a_spot_em()
            
            limit_up = len(df[df['涨跌幅'] >= 9.9])
            limit_down = len(df[df['涨跌幅'] <= -9.9])
            up_count = len(df[df['涨跌幅'] > 0])
            down_count = len(df[df['涨跌幅'] < 0])
            
            return {
                "limit_up": limit_up,
                "limit_down": limit_down,
                "up_count": up_count,
                "down_count": down_count,
                "up_down_ratio": round(up_count / down_count, 2) if down_count > 0 else float('inf'),
                "total_amount": round(df['成交额'].sum() / 1e8, 2)  # 亿元
            }
        except Exception as e:
            log.error(f"获取市场情绪失败: {e}")
            return {}
    
    def get_northbound_flow(self) -> float:
        """获取北向资金流向"""
        log.info("💹 获取北向资金流向")
        
        try:
            df = ak.stock_hsgt_north_net_flow_in_em(symbol="沪深港通")
            if not df.empty:
                latest = float(df.iloc[-1]['值'])
                return round(latest, 2)
            return 0
        except Exception as e:
            log.error(f"获取北向资金失败: {e}")
            return 0
    
    def get_sector_hotspot(self) -> pd.DataFrame:
        """获取板块热点"""
        log.info("🔥 获取板块热点")
        
        try:
            df = ak.stock_sector_fund_flow_rank(indicator="今日")
            return df.head(10)
        except Exception as e:
            log.error(f"获取板块热点失败: {e}")
            return pd.DataFrame()
    
    def get_limit_up_stats(self) -> Dict:
        """获取涨停统计"""
        log.info("📈 获取涨停统计")
        
        try:
            today = datetime.now().strftime('%Y%m%d')
            df = ak.stock_zt_pool_em(date=today)
            
            # 连板统计
            consecutive_2 = len(df[df['连板数'] == 2]) if '连板数' in df.columns else 0
            consecutive_3 = len(df[df['连板数'] == 3]) if '连板数' in df.columns else 0
            consecutive_4_plus = len(df[df['连板数'] >= 4]) if '连板数' in df.columns else 0
            
            return {
                "total_limit_up": len(df),
                "consecutive_2": consecutive_2,
                "consecutive_3": consecutive_3,
                "consecutive_4_plus": consecutive_4_plus
            }
        except Exception as e:
            log.error(f"获取涨停统计失败: {e}")
            return {}
    
    def analyze_market_stage(self, index_data: Dict, sentiment: Dict) -> str:
        """分析市场所处阶段"""
        if not index_data or not sentiment:
            return "unknown"
        
        # 简单判断逻辑
        sh_change = index_data.get('上证指数', {}).get('change_pct', 0)
        up_down_ratio = sentiment.get('up_down_ratio', 1)
        
        if sh_change > 1.5 and up_down_ratio > 2:
            return "牛市扩张"
        elif sh_change > -0.5 and up_down_ratio > 1.2:
            return "高位震荡"
        else:
            return "下跌修整"
    
    def generate_report(self) -> str:
        """生成盘前调研报告"""
        if not self.is_trade_date:
            return "今日休市，任务已跳过"
        
        log.info("📝 开始生成盘前调研报告")
        
        # 收集数据
        index_data = self.get_index_data()
        sentiment = self.get_market_sentiment()
        north_flow = self.get_northbound_flow()
        sector_df = self.get_sector_hotspot()
        limit_up_stats = self.get_limit_up_stats()
        market_stage = self.analyze_market_stage(index_data, sentiment)
        
        # 生成报告
        report = f"""# 📊 Alpha 盘前市场调研报告
**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 一、大盘情绪扫描

| 指数 | 收盘 | 涨跌幅 | 状态 |
|------|------|--------|------|
"""
        
        for name, data in index_data.items():
            emoji = "📈" if data['change_pct'] > 0 else "📉"
            report += f"| {name} | {data['close']:.2f} | {emoji} {data['change_pct']:+.2f}% | {'强势' if data['change_pct'] > 1 else '震荡' if data['change_pct'] > -1 else '弱势'} |\n"
        
        report += f"""
**市场情绪**:
- 涨停家数: {sentiment.get('limit_up', 0)} | 跌停家数: {sentiment.get('limit_down', 0)}
- 涨跌比: {sentiment.get('up_count', 0)} : {sentiment.get('down_count', 0)} ({sentiment.get('up_down_ratio', 0):.2f})
- 北向资金: {'📈' if north_flow > 0 else '📉'} {north_flow:+.2f} 亿元
- 两市成交额: {sentiment.get('total_amount', 0):.2f} 亿元

---

## 二、热点板块识别

| 排名 | 板块 | 涨跌幅 | 主力资金 |
|------|------|--------|----------|
"""
        
        if not sector_df.empty:
            for i, (_, row) in enumerate(sector_df.head(5).iterrows(), 1):
                report += f"| {i} | {row.get('名称', 'N/A')} | {row.get('涨跌幅', 0):+.2f}% | {row.get('主力净流入', 'N/A')} |\n"
        
        report += f"""
---

## 三、涨停分析

| 指标 | 数值 |
|------|------|
| 涨停家数 | {limit_up_stats.get('total_limit_up', 0)} |
| 2连板 | {limit_up_stats.get('consecutive_2', 0)} 家 |
| 3连板 | {limit_up_stats.get('consecutive_3', 0)} 家 |
| 4连板+ | {limit_up_stats.get('consecutive_4_plus', 0)} 家 |

---

## 四、市场阶段判断

**当前阶段**: {market_stage}

**今日操作策略**:
- 总体倾向: {'进攻' if market_stage == '牛市扩张' else '防守' if market_stage == '下跌修整' else '观望'}
- 仓位建议: {'80-100%' if market_stage == '牛市扩张' else '30-50%' if market_stage == '下跌修整' else '50-70%'}
- 重点关注: 新能源、AI、存储芯片

---

*报告由 Alpha Quant 自动生成*
"""
        
        log.info("✅ 盘前调研报告生成完成")
        return report
    
    def run(self):
        """执行盘前调研"""
        report = self.generate_report()
        
        # 发送通知
        if self.is_trade_date:
            notification_manager.send_daily_report(report)
        
        return report

# 全局实例
market_research = MarketResearch()

if __name__ == "__main__":
    result = market_research.run()
    print(result)
