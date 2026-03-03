#!/usr/bin/env python3
"""
Alpha-Scout: 市场情报员
负责盘前市场全景调研和实时情报监控
"""

import akshare as ak
import pandas as pd
from datetime import datetime
from loguru import logger
from core.agent_bus import AgentBus

class AlphaScout:
    """市场情报员 - 团队的'眼睛'"""
    
    def __init__(self):
        self.bus = AgentBus()
        
    def morning_research(self):
        """晨间盘前调研 - 08:50执行"""
        logger.info("[Scout] 开始盘前全景调研")
        
        report = {
            "date": datetime.now().strftime('%Y-%m-%d'),
            "priority": "normal",
            "sections": {}
        }
        
        # 1. 外围环境
        report["sections"]["global"] = self._check_global_markets()
        
        # 2. 大盘情绪
        report["sections"]["market_sentiment"] = self._analyze_market_sentiment()
        
        # 3. 热点板块
        report["sections"]["hot_sectors"] = self._scan_hot_sectors()
        
        # 4. 北向资金预判
        report["sections"]["north_flow"] = self._predict_north_flow()
        
        # 5. 涨停生态
        report["sections"]["zt_ecology"] = self._analyze_zt_ecology()
        
        # 确定优先级
        risk_factors = report["sections"].get("global", {}).get("risk_factors", [])
        if len(risk_factors) >= 2:
            report["priority"] = "important"
        
        # 发送情报报告
        self.bus.scout_report(report)
        logger.info(f"[Scout] 盘前情报报告已发送，优先级: {report['priority']}")
        
        return report
    
    def _check_global_markets(self):
        """检查外围市场"""
        try:
            # 获取A50期指
            a50 = ak.futures_zh_realtime(symbol="CN0")
            a50_change = float(a50.iloc[0]["涨跌"]) if not a50.empty else 0
            
            return {
                "a50_futures": {"change": a50_change, "impact": "positive" if a50_change > 0 else "negative"},
                "risk_factors": ["美债收益率上行"] if a50_change < -0.5 else [],
                "update_time": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"[Scout] 外围市场检查失败: {e}")
            return {"error": str(e)}
    
    def _analyze_market_sentiment(self):
        """分析大盘情绪"""
        try:
            df = ak.stock_zh_a_spot_em()
            ups = len(df[df["涨跌幅"] > 0])
            downs = len(df[df["涨跌幅"] < 0])
            total = len(df)
            
            # 涨停跌停统计
            zt_df = ak.stock_zt_pool_em(date="")
            zt_count = len(zt_df) if not zt_df.empty else 0
            
            return {
                "ups": ups,
                "downs": downs,
                "ratio": round(ups/max(downs, 1), 2),
                "zt_count": zt_count,
                "sentiment": "bullish" if ups > downs else "bearish" if ups < downs * 0.8 else "neutral",
                "update_time": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"[Scout] 情绪分析失败: {e}")
            return {"error": str(e)}
    
    def _scan_hot_sectors(self):
        """扫描热点板块"""
        try:
            # 获取板块资金流向
            sector_df = ak.stock_sector_fund_flow_rank()
            if not sector_df.empty:
                top_sectors = sector_df.head(5)["名称"].tolist()
                return {
                    "top_sectors": top_sectors,
                    "update_time": datetime.now().isoformat()
                }
            return {"top_sectors": []}
        except Exception as e:
            logger.error(f"[Scout] 板块扫描失败: {e}")
            return {"error": str(e)}
    
    def _predict_north_flow(self):
        """预判北向资金"""
        try:
            # 获取最近5日北向资金流向
            nf_df = ak.stock_hsgt_north_net_flow_in_em(symbol="沪深港通")
            recent_5d = nf_df["值"].tail(5).astype(float).sum() if not nf_df.empty else 0
            
            forecast = "+25亿" if recent_5d > 50 else "-15亿" if recent_5d < -50 else "±10亿"
            
            return {
                "recent_5d_total": round(recent_5d, 2),
                "forecast": forecast,
                "trend": "inflow" if recent_5d > 0 else "outflow",
                "update_time": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"[Scout] 北向预判失败: {e}")
            return {"error": str(e)}
    
    def _analyze_zt_ecology(self):
        """分析涨停生态"""
        try:
            zt_df = ak.stock_zt_pool_em(date="")
            if zt_df.empty:
                return {"zt_count": 0, "max_board": 0}
            
            zt_count = len(zt_df)
            max_board = int(zt_df["连板数"].max()) if "连板数" in zt_df.columns else 0
            
            return {
                "zt_count": zt_count,
                "max_board": max_board,
                "status": "hot" if zt_count > 60 else "warm" if zt_count > 30 else "cold",
                "update_time": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"[Scout] 涨停生态分析失败: {e}")
            return {"error": str(e)}
    
    def realtime_monitor(self):
        """盘中实时监控 - 检测异动"""
        # 简化版：检查北向资金是否异常流出
        try:
            nf_df = ak.stock_hsgt_north_net_flow_in_em(symbol="沪深港通")
            today_flow = float(nf_df.iloc[-1]["值"]) if not nf_df.empty else 0
            
            if today_flow < -50:
                # 异常流出，上报Chief
                self.bus.publish("intel", {
                    "from": "Scout",
                    "type": "alert",
                    "priority": "urgent",
                    "message": f"北向资金异常流出 {today_flow}亿",
                    "timestamp": datetime.now().isoformat()
                })
                logger.warning(f"[Scout] ⚠️ 北向异常流出: {today_flow}亿")
        except Exception as e:
            logger.error(f"[Scout] 实时监控失败: {e}")

if __name__ == "__main__":
    scout = AlphaScout()
    scout.morning_research()
