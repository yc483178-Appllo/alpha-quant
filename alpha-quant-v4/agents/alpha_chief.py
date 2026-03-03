#!/usr/bin/env python3
"""
Alpha-Chief: 首席策略官
Multi-Agent系统的总协调人和最终决策者
"""

import json
import time
from datetime import datetime
from loguru import logger
from core.agent_bus import AgentBus

class AlphaChief:
    """首席策略官 - 系统总协调者"""
    
    def __init__(self):
        self.bus = AgentBus()
        self.pending_signals = {}  # 待审批信号
        self.daily_decisions = []  # 当日决策记录
        self.agent_status = {
            "Scout": False,
            "Picker": False,
            "Guard": False,
            "Trader": False,
            "Review": False
        }
        
    def startup_check(self):
        """系统启动检查 - 08:45执行"""
        logger.info("[Chief] 执行Agent就绪检查")
        self.bus.publish("emergency", {
            "from": "Chief",
            "type": "system_start",
            "message": "Alpha团队早安！今日系统启动，各Agent请就位。",
            "timestamp": datetime.now().isoformat()
        })
        return True
    
    def process_scout_report(self, report):
        """处理Scout情报报告"""
        logger.info(f"[Chief] 接收Scout情报: {report.get('priority', 'normal')}")
        # 存储情报供后续决策参考
        self.latest_intel = report
        return True
    
    def process_picker_signal(self, signal):
        """处理Picker选股信号 - 需要审批"""
        signal_id = signal.get('signal_id', f"SIG-{datetime.now().strftime('%Y%m%d-%H%M%S')}")
        logger.info(f"[Chief] 接收Picker信号: {signal.get('code')} - {signal.get('action')}")
        
        # 发送到Guard进行风控检查
        self.bus.publish("risk", {
            "from": "Chief",
            "type": "risk_check_request",
            "signal_id": signal_id,
            "signal": signal
        })
        
        # 暂存等待Guard反馈
        self.pending_signals[signal_id] = {
            "signal": signal,
            "guard_approved": None,
            "timestamp": datetime.now().isoformat()
        }
        
        return signal_id
    
    def process_guard_feedback(self, feedback):
        """处理Guard风控反馈"""
        signal_id = feedback.get('signal_id')
        feedback_type = feedback.get('type')
        
        if feedback_type == 'veto':
            logger.warning(f"[Chief] Guard否决信号 {signal_id}: {feedback.get('reason')}")
            # 记录否决决策
            self._record_decision(signal_id, 'rejected_by_guard', feedback.get('reason'))
            return
        
        if feedback_type == 'risk_cleared':
            logger.info(f"[Chief] Guard放行信号 {signal_id}")
            if signal_id in self.pending_signals:
                self.pending_signals[signal_id]['guard_approved'] = True
                # Chief做出最终决策
                self._make_final_decision(signal_id)
    
    def _make_final_decision(self, signal_id):
        """做出最终决策"""
        pending = self.pending_signals.get(signal_id)
        if not pending:
            return
        
        signal = pending['signal']
        
        # 综合判断逻辑
        decision = {
            "decision_id": f"CHIEF-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "signal_id": signal_id,
            "action": "approve",  # 简化版默认通过
            "target": signal.get('code'),
            "reason": f"Guard已放行，信号强度{signal.get('signal_strength', 'normal')}",
            "risk_level": signal.get('risk_level', 'medium'),
            "agents_consulted": ["Picker", "Guard"],
            "confidence": signal.get('score', 0.7),
            "timestamp": datetime.now().isoformat()
        }
        
        # 发送给Trader执行
        self.bus.chief_approve(signal_id, modifications=decision)
        self._record_decision(signal_id, 'approved', decision)
        
        logger.info(f"[Chief] 签发交易指令: {signal.get('code')} {signal.get('action')}")
    
    def _record_decision(self, signal_id, result, details):
        """记录决策"""
        self.daily_decisions.append({
            "signal_id": signal_id,
            "result": result,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
    
    def daily_meeting(self):
        """日终会议 - 15:30执行"""
        logger.info("[Chief] 召开日终Agent会议")
        
        summary = {
            "date": datetime.now().strftime('%Y-%m-%d'),
            "total_decisions": len(self.daily_decisions),
            "approved": len([d for d in self.daily_decisions if d['result'] == 'approved']),
            "rejected": len([d for d in self.daily_decisions if 'rejected' in d['result']]),
            "timestamp": datetime.now().isoformat()
        }
        
        self.bus.publish("review", {
            "from": "Chief",
            "type": "daily_summary",
            "data": summary
        })
        
        return summary
    
    def emergency_handler(self, message):
        """紧急事件处理"""
        logger.error(f"[Chief] 🚨 紧急事件: {message}")
        # 暂停所有操作
        self.bus.emergency_broadcast("Chief", "系统进入紧急暂停状态，所有Agent停止操作")

if __name__ == "__main__":
    chief = AlphaChief()
    chief.startup_check()
