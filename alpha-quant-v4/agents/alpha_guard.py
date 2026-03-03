#!/usr/bin/env python3
"""
Alpha-Guard: 风控总监
拥有对任何交易操作的一票否决权
"""

import akshare as ak
import pandas as pd
from datetime import datetime
from loguru import logger
from core.agent_bus import AgentBus

class AlphaGuard:
    """风控总监 - 团队的'守门员'"""
    
    # 风控阈值配置
    LIMITS = {
        "single_stock_max_pct": 0.20,  # 单股最大仓位20%
        "total_position_max_pct": 0.80,  # 总仓位上限80%
        "daily_loss_limit_pct": 0.02,  # 单日亏损上限2%
        "stop_loss_pct": 0.08,  # 个股止损线8%
        "take_profit_pct": 0.20,  # 个股止盈线20%
        "sector_concentration_limit": 0.40,  # 板块集中度上限40%
    }
    
    def __init__(self):
        self.bus = AgentBus()
        self.risk_status = "GREEN"  # GREEN/YELLOW/ORANGE/RED/BLACK
        
    def pre_market_check(self):
        """开盘前风控预检 - 09:20执行"""
        logger.info("[Guard] 执行开盘前风控预检")
        
        checks = {
            "market_risk": self._check_market_risk(),
            "position_risk": self._check_position_risk(),
            "system_risk": self._check_system_risk(),
        }
        
        # 综合评估
        if any(c["level"] == "high" for c in checks.values()):
            self.risk_status = "RED"
            self.bus.guard_alert({
                "level": "critical",
                "type": "pre_market",
                "message": "开盘前风控检查不通过，建议降低仓位",
                "checks": checks
            })
        else:
            self.risk_status = "GREEN"
            logger.info("[Guard] 开盘前风控检查通过")
        
        return checks
    
    def _check_market_risk(self):
        """检查市场风险"""
        try:
            # 检查大盘是否处于高风险状态
            df = ak.stock_zh_index_daily(symbol="sh000001")
            df["close"] = df["close"].astype(float)
            ma20 = df["close"].tail(20).mean()
            current = float(df["close"].iloc[-1])
            
            # 计算近期波动率
            returns = df["close"].pct_change().tail(20)
            volatility = returns.std() * (252 ** 0.5)
            
            if current < ma20 * 0.95 or volatility > 0.30:
                return {"level": "high", "reason": "大盘偏离MA20或高波动"}
            elif current < ma20:
                return {"level": "medium", "reason": "大盘略低于MA20"}
            return {"level": "low", "reason": "大盘正常"}
        except Exception as e:
            return {"level": "medium", "reason": f"检查失败: {e}"}
    
    def _check_position_risk(self):
        """检查持仓风险（简化版）"""
        # 实际应从交易账户获取持仓数据
        return {"level": "low", "reason": "持仓检查通过"}
    
    def _check_system_risk(self):
        """检查系统风险"""
        return {"level": "low", "reason": "系统正常"}
    
    def check_signal(self, signal):
        """检查交易信号 - 返回是否通过"""
        signal_id = signal.get("signal_id", "unknown")
        code = signal.get("code")
        
        logger.info(f"[Guard] 检查信号 {signal_id}: {code}")
        
        # 检查1: 单股仓位限制
        position_check = self._check_single_position(code)
        if not position_check["pass"]:
            self.bus.guard_veto(signal_id, position_check["reason"])
            return False
        
        # 检查2: 板块集中度
        sector_check = self._check_sector_concentration(code)
        if not sector_check["pass"]:
            self.bus.guard_veto(signal_id, sector_check["reason"])
            return False
        
        # 检查3: 总仓位限制
        total_check = self._check_total_position()
        if not total_check["pass"]:
            self.bus.guard_veto(signal_id, total_check["reason"])
            return False
        
        # 通过检查
        self.bus.publish("risk", {
            "from": "Guard",
            "type": "risk_cleared",
            "signal_id": signal_id,
            "message": "风控检查通过"
        })
        return True
    
    def _check_single_position(self, code):
        """检查单股仓位"""
        # 简化版：假设当前仓位0
        current_pct = 0  # 应从账户获取
        
        if current_pct >= self.LIMITS["single_stock_max_pct"]:
            return {
                "pass": False,
                "reason": f"单股仓位已达{self.LIMITS['single_stock_max_pct']:.0%}上限"
            }
        return {"pass": True}
    
    def _check_sector_concentration(self, code):
        """检查板块集中度"""
        # 简化版
        return {"pass": True}
    
    def _check_total_position(self):
        """检查总仓位"""
        # 简化版
        return {"pass": True}
    
    def realtime_monitor(self):
        """盘中实时监控 - 每30分钟执行"""
        logger.info("[Guard] 执行盘中风控检查")
        
        # 检查大盘是否触发熔断条件
        try:
            df = ak.stock_zh_a_spot_em()
            sh_change = float(df[df["代码"] == "000001"]["涨跌幅"].values[0]) if not df[df["代码"] == "000001"].empty else 0
            
            if sh_change < -3:
                self.risk_status = "ORANGE"
                self.bus.guard_alert({
                    "level": "warning",
                    "type": "market_drop",
                    "message": f"大盘下跌{sh_change}%，触发风控预警"
                })
            
            if sh_change < -5:
                self.risk_status = "BLACK"
                self.bus.emergency_broadcast("Guard", f"大盘暴跌{sh_change}%，系统进入熔断状态")
                
        except Exception as e:
            logger.error(f"[Guard] 盘中监控失败: {e}")
    
    def check_stop_loss(self, holdings):
        """检查止损条件"""
        alerts = []
        for holding in holdings:
            code = holding["code"]
            current_price = holding["current_price"]
            cost_price = holding["cost_price"]
            
            loss_pct = (current_price - cost_price) / cost_price
            
            if loss_pct <= -self.LIMITS["stop_loss_pct"]:
                alerts.append({
                    "code": code,
                    "action": "stop_loss",
                    "loss_pct": loss_pct,
                    "message": f"{code} 触及止损线 {self.LIMITS['stop_loss_pct']:.0%}"
                })
            elif loss_pct >= self.LIMITS["take_profit_pct"]:
                alerts.append({
                    "code": code,
                    "action": "take_profit",
                    "profit_pct": loss_pct,
                    "message": f"{code} 触及止盈线 {self.LIMITS['take_profit_pct']:.0%}"
                })
        
        for alert in alerts:
            self.bus.guard_alert({
                "level": "warning",
                "type": alert["action"],
                "data": alert
            })
        
        return alerts

if __name__ == "__main__":
    guard = AlphaGuard()
    guard.pre_market_check()
