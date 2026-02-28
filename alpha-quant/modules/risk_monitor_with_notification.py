#!/usr/bin/env python3
"""
risk_monitor_with_notification.py --- 带通知的风控监控

集成三级通知分层策略：
- 日常报告（蓝色）: 晨报/复盘
- 重要预警（橙色）: 一二级风控触发
- 紧急止损（红色）: 三级风控/熔断
"""

import sys
import os
sys.path.insert(0, '/root/.openclaw/workspace/alpha-quant')

from datetime import datetime
from typing import Dict, List
from loguru import logger

from modules.notification_service import NotificationService, NotificationLevel


class RiskMonitor:
    """
    风控监控器 - 集成三级通知
    
    风控级别定义：
    - 一级风控: 个股跌幅 > 5% 或 大盘跌幅 > 2%
    - 二级风控: 个股跌幅 > 7% 或 大盘跌幅 > 3%
    - 三级风控: 个股跌停 或 大盘跌幅 > 5%（熔断阈值）
    """
    
    def __init__(self):
        self.notifier = NotificationService()
        self.risk_levels = {
            1: {"name": "一级风控", "threshold_stock": -5.0, "threshold_index": -2.0},
            2: {"name": "二级风控", "threshold_stock": -7.0, "threshold_index": -3.0},
            3: {"name": "三级风控", "threshold_stock": -10.0, "threshold_index": -5.0}
        }
    
    def check_market_risk(self, index_data: Dict) -> int:
        """
        检查大盘风险级别
        
        Args:
            index_data: 大盘数据，如 {"上证指数": -2.5, "深证成指": -3.1}
            
        Returns:
            风险级别 (0-3)，0表示正常
        """
        max_drop = min(index_data.values())
        
        if max_drop <= -5.0:
            return 3
        elif max_drop <= -3.0:
            return 2
        elif max_drop <= -2.0:
            return 1
        return 0
    
    def check_position_risk(self, positions: List[Dict]) -> List[Dict]:
        """
        检查持仓风险
        
        Args:
            positions: 持仓列表，每个包含 code, name, change_pct
            
        Returns:
            触发风控的持仓列表
        """
        alerts = []
        
        for pos in positions:
            change = pos.get("change_pct", 0)
            
            if change <= -10.0:
                pos["risk_level"] = 3
                pos["risk_name"] = "三级风控"
                alerts.append(pos)
            elif change <= -7.0:
                pos["risk_level"] = 2
                pos["risk_name"] = "二级风控"
                alerts.append(pos)
            elif change <= -5.0:
                pos["risk_level"] = 1
                pos["risk_name"] = "一级风控"
                alerts.append(pos)
        
        return alerts
    
    def send_risk_notification(self, risk_level: int, context: Dict):
        """
        根据风险级别发送通知
        
        Args:
            risk_level: 风险级别 (1-3)
            context: 上下文信息
        """
        if risk_level == 0:
            return
        
        risk_info = self.risk_levels[risk_level]
        
        if risk_level == 1:
            # 一级风控 -> 重要预警（橙色）
            self.notifier.send_warning_alert(
                alert_type=risk_info["name"],
                message=context.get("message", "触发风控阈值"),
                key_data={
                    "触发标的": context.get("symbol", "未知"),
                    "当前跌幅": f"{context.get('change', 0):.2f}%",
                    "风控阈值": f"{risk_info['threshold_stock']}%"
                },
                suggestion=context.get("suggestion", "建议密切关注")
            )
            
        elif risk_level == 2:
            # 二级风控 -> 重要预警（橙色），更紧急
            self.notifier.send_warning_alert(
                alert_type=f"⚠️ {risk_info['name']}",
                message=context.get("message", "风险加剧，请立即处理"),
                key_data={
                    "触发标的": context.get("symbol", "未知"),
                    "当前跌幅": f"{context.get('change', 0):.2f}%",
                    "持仓占比": context.get("position_ratio", "未知"),
                    "预计亏损": context.get("estimated_loss", "未知")
                },
                suggestion=context.get("suggestion", "建议减仓或止损")
            )
            
        elif risk_level == 3:
            # 三级风控 -> 紧急止损（红色）
            self.notifier.send_urgent_stop(
                reason=f"{risk_info['name']}触发 - {context.get('symbol', '')}",
                action=context.get("action", "立即清仓"),
                position_info=context.get("position_detail", "")
            )
    
    def run_daily_report(self, market_summary: Dict):
        """
        发送日常报告（蓝色）
        
        Args:
            market_summary: 市场汇总数据
        """
        content = f"""
### 大盘概况
- 上证指数: {market_summary.get('sh_index', 'N/A')}
- 深证成指: {market_summary.get('sz_index', 'N/A')}
- 创业板指: {market_summary.get('cy_index', 'N/A')}
- 成交额: {market_summary.get('volume', 'N/A')}

### 市场情绪
- 涨跌比: {market_summary.get('up_down_ratio', 'N/A')}
- 涨停家数: {market_summary.get('limit_up', 'N/A')}
- 跌停家数: {market_summary.get('limit_down', 'N/A')}

### 今日操作
{market_summary.get('suggestion', '持仓观望')}
"""
        
        self.notifier.send_daily_report(
            title=f"Alpha每日晨报 - {datetime.now().strftime('%Y-%m-%d')}",
            content=content,
            data=market_summary.get("key_metrics", {})
        )
    
    def monitor(self, index_data: Dict, positions: List[Dict]):
        """
        执行完整的风控监控流程
        
        Args:
            index_data: 大盘数据
            positions: 持仓列表
        """
        logger.info("=" * 50)
        logger.info("🔍 启动风控监控")
        logger.info("=" * 50)
        
        # 1. 检查大盘风险
        market_risk = self.check_market_risk(index_data)
        if market_risk > 0:
            logger.warning(f"⚠️ 大盘风险级别: {market_risk}")
            self.send_risk_notification(market_risk, {
                "symbol": "大盘",
                "change": min(index_data.values()),
                "message": f"大盘跌幅超过{self.risk_levels[market_risk]['threshold_index']}%"
            })
        else:
            logger.info("✅ 大盘风险正常")
        
        # 2. 检查持仓风险
        position_alerts = self.check_position_risk(positions)
        if position_alerts:
            logger.warning(f"⚠️ 发现 {len(position_alerts)} 只持仓触发风控")
            for alert in position_alerts:
                self.send_risk_notification(alert["risk_level"], {
                    "symbol": f"{alert['code']} {alert['name']}",
                    "change": alert["change_pct"],
                    "position_ratio": alert.get("ratio", "未知"),
                    "suggestion": "建议减仓" if alert["risk_level"] < 3 else "立即清仓"
                })
        else:
            logger.info("✅ 持仓风险正常")
        
        logger.info("=" * 50)


# 使用示例
if __name__ == "__main__":
    monitor = RiskMonitor()
    
    # 示例1: 日常报告
    monitor.run_daily_report({
        "sh_index": "+0.5%",
        "sz_index": "+0.8%",
        "cy_index": "+1.2%",
        "volume": "1.2万亿",
        "up_down_ratio": "3:2",
        "limit_up": 45,
        "limit_down": 3,
        "suggestion": "市场情绪良好，可适当加仓",
        "key_metrics": {
            "北向资金": "+25亿",
            "主力净流入": "+50亿",
            "VIX指数": "18.5"
        }
    })
    
    # 示例2: 风控监控
    monitor.monitor(
        index_data={"上证指数": -1.5, "深证成指": -2.2, "创业板指": -2.8},
        positions=[
            {"code": "000001.SZ", "name": "平安银行", "change_pct": -3.5, "ratio": "10%"},
            {"code": "688256.SH", "name": "寒武纪", "change_pct": -6.0, "ratio": "15%"},  # 触发一级
            {"code": "300394.SZ", "name": "天孚通信", "change_pct": -8.5, "ratio": "8%"},  # 触发二级
        ]
    )
