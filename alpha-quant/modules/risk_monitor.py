"""
模块三：实时风控监控（盘中每30分钟）
个股风控 + 大盘风控 + 北向资金监控 + 板块集中度检查
"""
import os
import akshare as ak
import requests
import pandas as pd
from datetime import datetime
from typing import List, Tuple, Dict
from modules.config_manager import config_manager
from modules.logger import log
from modules.notification import notification_manager

class RiskMonitor:
    """实时风控监控器"""
    
    def __init__(self):
        self.total_assets = config_manager.get('risk.total_assets', 1_000_000)
        self.stop_loss_pct = config_manager.get('risk.stop_loss_pct', 0.08)
        self.take_profit_pct = config_manager.get('risk.take_profit_pct', 0.20)
        self.trailing_stop_pct = config_manager.get('risk.trailing_stop_pct', 0.05)
        self.max_position_pct = config_manager.get('risk.max_position_pct', 0.20)
        self.sector_concentration_limit = config_manager.get('risk.sector_concentration_limit', 0.40)
        self.pause_on_market_drop = config_manager.get('risk.pause_on_market_drop', 0.02)
        self.north_flow_alert_threshold = config_manager.get('risk.north_flow_alert_threshold', -80)
        
        # 持仓数据（实际应从PTrade/QMT API读取）
        self.positions = self._load_positions()
    
    def _load_positions(self) -> Dict:
        """加载持仓数据"""
        # TODO: 从实际交易接口读取
        # 示例持仓
        return {
            # "000001": {"name": "平安银行", "cost": 12.50, "qty": 1000, "highest": 13.80, "sector": "银行"},
        }
    
    def _get_price_map(self) -> Dict[str, float]:
        """获取实时价格映射"""
        try:
            df = ak.stock_zh_a_spot_em()
            return dict(zip(df["代码"], df["最新价"]))
        except Exception as e:
            log.error(f"获取实时价格失败: {e}")
            return {}
    
    def check_individual_risk(self, price_map: Dict) -> List[Tuple[str, str]]:
        """个股风控检查"""
        alerts = []
        
        for code, pos in self.positions.items():
            cur_price = price_map.get(code, pos["cost"])
            pnl = (cur_price - pos["cost"]) / pos["cost"]
            
            # 止损检查
            if pnl <= -0.10:
                alerts.append(("critical", f"🔴 **三级止损** | {pos['name']}({code}) 浮亏{pnl:.1%}，建议立即止损"))
            elif pnl <= -0.08:
                alerts.append(("warning", f"🟠 **二级预警** | {pos['name']}({code}) 浮亏{pnl:.1%}，建议关注"))
            elif pnl <= -0.05:
                alerts.append(("info", f"🟡 **一级提示** | {pos['name']}({code}) 浮亏{pnl:.1%}"))
            
            # 移动止盈检查
            if cur_price > pos.get("highest", pos["cost"]):
                pos["highest"] = cur_price
            
            if pos.get("highest", pos["cost"]) > pos["cost"] * 1.05:
                retreat = (pos["highest"] - cur_price) / pos["highest"]
                if retreat > self.trailing_stop_pct:
                    alerts.append(("warning", f"📉 **移动止盈** | {pos['name']}({code}) 从最高点回落{retreat:.1%}，考虑锁定利润"))
            
            # 仓位集中度检查
            position_value = cur_price * pos["qty"]
            position_pct = position_value / self.total_assets
            if position_pct > self.max_position_pct:
                alerts.append(("warning", f"⚖️ **仓位超限** | {pos['name']}({code}) 当前仓位{position_pct:.1%}，超过{self.max_position_pct:.0%}上限"))
        
        return alerts
    
    def check_market_risk(self, df: pd.DataFrame) -> List[Tuple[str, str]]:
        """大盘风控检查"""
        alerts = []
        
        try:
            # 指数代码映射
            index_codes = {
                "000001": "上证指数",
                "399001": "深证成指", 
                "399006": "创业板指"
            }
            
            for code, name in index_codes.items():
                stock = df[df["代码"] == code]
                if not stock.empty:
                    change_pct = stock.iloc[0]["涨跌幅"]
                    if change_pct <= -3:
                        alerts.append(("critical", f"🔴 **大盘熔断** | {name} 跌幅{change_pct:.2f}%，暂停全部买入！"))
                    elif change_pct <= -self.pause_on_market_drop * 100:
                        alerts.append(("warning", f"🟠 **大盘预警** | {name} 跌幅{change_pct:.2f}%"))
        except Exception as e:
            log.error(f"大盘检查失败: {e}")
        
        return alerts
    
    def check_northbound_flow(self) -> List[Tuple[str, str]]:
        """北向资金监控"""
        alerts = []
        
        try:
            north_df = ak.stock_hsgt_north_net_flow_in_em(symbol="沪深港通")
            north_flow = float(north_df.iloc[-1]["值"])
            
            if north_flow < self.north_flow_alert_threshold:
                alerts.append(("critical", f"🔴 **北向大幅流出** | 今日净流出 {abs(north_flow):.1f}亿，建议降低仓位"))
            elif north_flow < -50:
                alerts.append(("warning", f"🟠 **北向流出** | 今日净流出 {abs(north_flow):.1f}亿，保持关注"))
        except Exception as e:
            log.error(f"北向资金检查失败: {e}")
        
        return alerts
    
    def check_sector_concentration(self, price_map: Dict) -> List[Tuple[str, str]]:
        """板块集中度检查"""
        alerts = []
        
        sector_exposure = {}
        for code, pos in self.positions.items():
            cur_price = price_map.get(code, pos["cost"])
            sector = pos.get("sector", "未知")
            sector_exposure[sector] = sector_exposure.get(sector, 0) + cur_price * pos["qty"]
        
        for sector, value in sector_exposure.items():
            pct = value / self.total_assets
            if pct > self.sector_concentration_limit:
                alerts.append(("warning", f"⚖️ **板块集中** | {sector}板块仓位{pct:.1%}，超过{self.sector_concentration_limit:.0%}建议分散"))
        
        return alerts
    
    def run_check(self) -> List[Tuple[str, str]]:
        """执行完整风控检查"""
        log.info("===== 🔍 风控检查开始 =====")
        
        # 获取实时数据
        price_map = self._get_price_map()
        if not price_map:
            log.error("获取实时价格失败，跳过风控检查")
            return []
        
        try:
            df = ak.stock_zh_a_spot_em()
        except Exception as e:
            log.error(f"获取市场数据失败: {e}")
            return []
        
        all_alerts = []
        
        # 各项检查
        all_alerts.extend(self.check_individual_risk(price_map))
        all_alerts.extend(self.check_market_risk(df))
        all_alerts.extend(self.check_northbound_flow())
        all_alerts.extend(self.check_sector_concentration(price_map))
        
        if not all_alerts:
            log.info("✅ 风控检查通过，无异常")
        else:
            log.info(f"⚠️  发现 {len(all_alerts)} 条风险警告")
        
        return all_alerts
    
    def send_alerts(self, alerts: List[Tuple[str, str]]):
        """发送风控预警"""
        if not alerts:
            return
        
        # 按级别分组
        msg_parts = []
        has_critical = any(level == "critical" for level, _ in alerts)
        
        for level, msg in alerts:
            msg_parts.append(msg)
        
        full_msg = "\n\n".join(msg_parts)
        
        # 飞书推送（所有级别）
        notification_manager.send(
            full_msg,
            level="critical" if has_critical else "warning",
            title="🚨 Alpha 量化风控预警"
        )
        
        log.info(f"风控预警已推送: {len(alerts)} 条")
    
    def run(self):
        """执行风控检查并推送"""
        try:
            alerts = self.run_check()
            self.send_alerts(alerts)
            return alerts
        except Exception as e:
            log.error(f"风控检查异常: {e}")
            notification_manager.send_critical(f"⚠️ 风控系统异常: {str(e)}")
            return []

# 全局实例
risk_monitor = RiskMonitor()

if __name__ == "__main__":
    risk_monitor.run()
