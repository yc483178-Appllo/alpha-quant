"""
风险控制模块
"""
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
import config

@dataclass
class Position:
    """持仓数据类"""
    ts_code: str
    name: str
    volume: int
    avg_cost: float
    current_price: float
    market_value: float
    pnl: float
    pnl_pct: float
    weight: float

@dataclass
class RiskStatus:
    """风险状态"""
    level: str  # low, medium, high, fuse
    can_buy: bool
    can_sell: bool
    messages: List[str]

class RiskManager:
    """风险管理器"""
    
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.daily_pnl_history: List[Dict] = []
        self.total_capital = config.INITIAL_CAPITAL
        self.available_capital = config.INITIAL_CAPITAL
        
    def update_position(self, position: Position):
        """更新持仓"""
        self.positions[position.ts_code] = position
        self._recalculate_capital()
    
    def _recalculate_capital(self):
        """重新计算资金"""
        market_value = sum(p.market_value for p in self.positions.values())
        self.available_capital = self.total_capital - market_value
    
    def check_position_limit(self, ts_code: str, planned_amount: float) -> tuple[bool, str]:
        """检查个股仓位限制"""
        current_position = self.positions.get(ts_code)
        current_value = current_position.market_value if current_position else 0
        
        max_value = self.total_capital * config.MAX_POSITION_PER_STOCK
        planned_value = current_value + planned_amount
        
        if planned_value > max_value:
            return False, f"仓位超限: {ts_code} 计划仓位 {planned_value/self.total_capital:.1%} > 最大 {config.MAX_POSITION_PER_STOCK:.0%}"
        return True, "OK"
    
    def check_daily_loss_limit(self, today_pnl_pct: float) -> RiskStatus:
        """检查单日亏损限制"""
        messages = []
        can_buy = True
        
        if today_pnl_pct < -config.MAX_DAILY_LOSS:
            can_buy = False
            messages.append(f"🚨 单日亏损 {today_pnl_pct:.2%} 超过阈值 {config.MAX_DAILY_LOSS:.0%}，暂停买入")
        
        return RiskStatus(
            level="high" if not can_buy else "low",
            can_buy=can_buy,
            can_sell=True,
            messages=messages
        )
    
    def check_consecutive_loss(self) -> RiskStatus:
        """检查连续亏损"""
        messages = []
        can_buy = True
        
        if len(self.daily_pnl_history) >= config.MAX_CONSECUTIVE_DAYS:
            recent = self.daily_pnl_history[-config.MAX_CONSECUTIVE_DAYS:]
            consecutive_loss_days = sum(1 for d in recent if d['pnl_pct'] < -config.MAX_CONSECUTIVE_LOSS)
            
            if consecutive_loss_days >= config.MAX_CONSECUTIVE_DAYS:
                can_buy = False
                messages.append(f"🛡️ 连续{config.MAX_CONSECUTIVE_DAYS}日亏损超{config.MAX_CONSECUTIVE_LOSS:.0%}，进入防守模式")
        
        return RiskStatus(
            level="defense" if not can_buy else "low",
            can_buy=can_buy,
            can_sell=True,
            messages=messages
        )
    
    def check_market_fuse(self, index_change_pct: float) -> RiskStatus:
        """检查大盘熔断"""
        messages = []
        can_buy = True
        level = "low"
        
        if index_change_pct <= config.MARKET_FUSE_THRESHOLD:
            can_buy = False
            level = "fuse"
            messages.append(f"⚡ 大盘跌幅 {index_change_pct:.2%} 触发熔断，禁止买入")
        elif index_change_pct < -0.02:
            level = "medium"
            messages.append(f"⚠️ 大盘跌幅 {index_change_pct:.2%}，谨慎操作")
        
        return RiskStatus(
            level=level,
            can_buy=can_buy,
            can_sell=True,
            messages=messages
        )
    
    def check_stock_stop_loss(self, position: Position) -> Optional[str]:
        """检查个股止损"""
        if position.pnl_pct < -0.08:
            return f"🛑 {position.name}({position.ts_code}) 亏损 {position.pnl_pct:.2%}，建议止损"
        return None
    
    def get_portfolio_summary(self) -> Dict:
        """获取组合概览"""
        total_market_value = sum(p.market_value for p in self.positions.values())
        total_pnl = sum(p.pnl for p in self.positions.values())
        
        return {
            "total_capital": self.total_capital,
            "market_value": total_market_value,
            "available_capital": self.available_capital,
            "total_pnl": total_pnl,
            "total_pnl_pct": total_pnl / config.INITIAL_CAPITAL,
            "position_count": len(self.positions),
            "positions": [
                {
                    "code": p.ts_code,
                    "name": p.name,
                    "weight": p.weight,
                    "pnl_pct": p.pnl_pct
                }
                for p in self.positions.values()
            ]
        }
    
    def comprehensive_check(self, index_change_pct: float, today_pnl_pct: float) -> RiskStatus:
        """综合风险检查"""
        all_messages = []
        can_buy = True
        max_level = "low"
        
        # 大盘熔断检查
        fuse_status = self.check_market_fuse(index_change_pct)
        if fuse_status.level == "fuse":
            return fuse_status
        all_messages.extend(fuse_status.messages)
        
        # 单日亏损检查
        daily_status = self.check_daily_loss_limit(today_pnl_pct)
        if not daily_status.can_buy:
            can_buy = False
            max_level = max(max_level, daily_status.level)
        all_messages.extend(daily_status.messages)
        
        # 连续亏损检查
        consecutive_status = self.check_consecutive_loss()
        if not consecutive_status.can_buy:
            can_buy = False
            max_level = max(max_level, consecutive_status.level)
        all_messages.extend(consecutive_status.messages)
        
        # 个股止损检查
        for pos in self.positions.values():
            stop_msg = self.check_stock_stop_loss(pos)
            if stop_msg:
                all_messages.append(stop_msg)
        
        return RiskStatus(
            level=max_level,
            can_buy=can_buy,
            can_sell=True,
            messages=all_messages
        )

# 全局实例
risk_manager = RiskManager()
