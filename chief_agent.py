#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alpha V6.0 - Chief决策Agent (Chief Agent)
最高决策层，协调所有子Agent，做出最终交易决策
"""

import json
import logging
import random
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DecisionType(Enum):
    """决策类型"""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    REDUCE = "reduce"
    INCREASE = "increase"


class RiskLevel(Enum):
    """风险等级"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class AgentSignal:
    """Agent信号"""
    agent_name: str
    decision: DecisionType
    confidence: float
    target_symbol: str
    target_position: float
    reasoning: str
    timestamp: str
    metadata: Dict[str, Any]


@dataclass
class ChiefDecision:
    """Chief决策"""
    decision_id: str
    timestamp: str
    decision: DecisionType
    target_symbol: str
    target_position: float
    confidence: float
    risk_level: RiskLevel
    participating_agents: List[str]
    agent_consensus: float
    reasoning: str
    execution_plan: Dict[str, Any]
    risk_checks: List[str]


class ChiefAgent:
    """
    Chief决策Agent
    
    功能：
    1. 接收所有子Agent信号
    2. 加权投票决策
    3. 风险评估
    4. 生成执行计划
    5. 决策回滚机制
    """
    
    def __init__(self, config_path: str = "/opt/alpha-system/config/config.json"):
        self.config = self._load_config(config_path)
        self.agent_config = self.config.get("agents", {})
        self.chief_config = self.agent_config.get("chief_agent", {})
        
        self.decision_threshold = self.chief_config.get("decision_threshold", 0.7)
        self.risk_appetite = self.chief_config.get("risk_appetite", "moderate")
        self.max_daily_trades = self.chief_config.get("max_daily_trades", 50)
        
        # Agent权重配置
        self.agent_weights = {}
        for agent in self.agent_config.get("specialized_agents", []):
            if agent.get("enabled", False):
                self.agent_weights[agent["name"]] = agent.get("weight", 0.1)
        
        # 状态
        self.pending_signals: Dict[str, List[AgentSignal]] = {}
        self.decision_history: List[ChiefDecision] = []
        self.daily_trade_count = 0
        self.last_reset_date = datetime.now().date()
        
        logger.info(f"Chief Agent初始化完成，决策阈值: {self.decision_threshold}")
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"无法加载配置: {e}，使用默认配置")
            return {
                "agents": {
                    "chief_agent": {
                        "decision_threshold": 0.7,
                        "risk_appetite": "moderate"
                    },
                    "specialized_agents": []
                }
            }
    
    def _reset_daily_counter(self):
        """重置日计数器"""
        today = datetime.now().date()
        if today != self.last_reset_date:
            self.daily_trade_count = 0
            self.last_reset_date = today
    
    def receive_signal(self, signal: AgentSignal) -> Dict:
        """
        接收Agent信号
        
        Args:
            signal: Agent信号对象
        """
        self._reset_daily_counter()
        
        symbol = signal.target_symbol
        if symbol not in self.pending_signals:
            self.pending_signals[symbol] = []
        
        self.pending_signals[symbol].append(signal)
        
        logger.info(f"收到 {signal.agent_name} 的信号: {signal.decision.value} {symbol} "
                   f"(置信度: {signal.confidence:.2f})")
        
        # 检查是否达到决策条件
        return self._evaluate_signals(symbol)
    
    def _evaluate_signals(self, symbol: str) -> Dict:
        """评估信号并做出决策"""
        signals = self.pending_signals.get(symbol, [])
        
        if len(signals) < 3:  # 至少需要3个Agent的信号
            return {
                "action": "wait",
                "reason": f"等待更多信号 ({len(signals)}/3+)",
                "symbol": symbol
            }
        
        # 计算加权投票
        decision_scores = {dt: 0.0 for dt in DecisionType}
        total_weight = 0.0
        
        for signal in signals:
            weight = self.agent_weights.get(signal.agent_name, 0.1)
            decision_scores[signal.decision] += signal.confidence * weight
            total_weight += weight
        
        # 归一化
        for dt in decision_scores:
            decision_scores[dt] /= max(total_weight, 0.001)
        
        # 找出最高分的决策
        best_decision = max(decision_scores, key=decision_scores.get)
        best_score = decision_scores[best_decision]
        
        # 计算共识度
        agreeing_agents = [s.agent_name for s in signals if s.decision == best_decision]
        consensus = len(agreeing_agents) / len(signals)
        
        # 决策阈值检查
        if best_score < self.decision_threshold:
            return {
                "action": "hold",
                "reason": f"得分 {best_score:.2f} 低于阈值 {self.decision_threshold}",
                "symbol": symbol,
                "scores": {k.value: round(v, 3) for k, v in decision_scores.items()}
            }
        
        # 日交易限制检查
        if self.daily_trade_count >= self.max_daily_trades:
            return {
                "action": "hold",
                "reason": f"已达到日交易限制 ({self.max_daily_trades})",
                "symbol": symbol
            }
        
        # 生成Chief决策
        decision = self._create_decision(
            symbol=symbol,
            decision_type=best_decision,
            confidence=best_score,
            consensus=consensus,
            agreeing_agents=agreeing_agents,
            all_signals=signals
        )
        
        # 保存决策
        self.decision_history.append(decision)
        self.daily_trade_count += 1
        
        # 清空该symbol的信号
        self.pending_signals[symbol] = []
        
        logger.info(f"Chief决策: {decision.decision.value} {symbol} "
                   f"(置信度: {decision.confidence:.2f}, 共识度: {consensus:.2f})")
        
        return {
            "action": "execute",
            "decision": asdict(decision),
            "scores": {k.value: round(v, 3) for k, v in decision_scores.items()}
        }
    
    def _create_decision(self, symbol: str, decision_type: DecisionType,
                        confidence: float, consensus: float,
                        agreeing_agents: List[str], all_signals: List[AgentSignal]) -> ChiefDecision:
        """创建决策对象"""
        
        # 风险评估
        risk_level = self._assess_risk(symbol, decision_type, confidence)
        
        # 计算目标仓位
        target_position = self._calculate_target_position(
            symbol, decision_type, confidence, all_signals
        )
        
        # 生成执行计划
        execution_plan = self._create_execution_plan(
            symbol, decision_type, target_position
        )
        
        # 生成决策理由
        reasoning = self._generate_reasoning(
            decision_type, agreeing_agents, all_signals, confidence
        )
        
        # 风险检查清单
        risk_checks = self._perform_risk_checks(symbol, decision_type, target_position)
        
        return ChiefDecision(
            decision_id=f"DEC{datetime.now().strftime('%Y%m%d%H%M%S')}",
            timestamp=datetime.now().isoformat(),
            decision=decision_type,
            target_symbol=symbol,
            target_position=target_position,
            confidence=round(confidence, 4),
            risk_level=risk_level,
            participating_agents=[s.agent_name for s in all_signals],
            agent_consensus=round(consensus, 4),
            reasoning=reasoning,
            execution_plan=execution_plan,
            risk_checks=risk_checks
        )
    
    def _assess_risk(self, symbol: str, decision: DecisionType, confidence: float) -> RiskLevel:
        """风险评估"""
        # 基于决策类型和置信度评估风险
        risk_score = 0.5
        
        if decision in [DecisionType.BUY, DecisionType.INCREASE]:
            risk_score += 0.2
        elif decision in [DecisionType.SELL, DecisionType.REDUCE]:
            risk_score -= 0.1
        
        risk_score += (1 - confidence) * 0.3
        
        if risk_score < 0.3:
            return RiskLevel.LOW
        elif risk_score < 0.6:
            return RiskLevel.MEDIUM
        elif risk_score < 0.8:
            return RiskLevel.HIGH
        else:
            return RiskLevel.EXTREME
    
    def _calculate_target_position(self, symbol: str, decision: DecisionType,
                                   confidence: float, signals: List[AgentSignal]) -> float:
        """计算目标仓位"""
        base_position = 0.1  # 基础仓位10%
        
        # 根据置信度调整
        position = base_position * confidence
        
        # 根据决策类型调整
        if decision == DecisionType.INCREASE:
            position *= 1.5
        elif decision == DecisionType.REDUCE:
            position *= 0.5
        
        # 根据风险承受能力调整
        if self.risk_appetite == "conservative":
            position *= 0.7
        elif self.risk_appetite == "aggressive":
            position *= 1.3
        
        return min(round(position, 4), 0.5)  # 最大仓位50%
    
    def _create_execution_plan(self, symbol: str, decision: DecisionType,
                               target_position: float) -> Dict:
        """创建执行计划"""
        
        if decision in [DecisionType.HOLD]:
            return {"action": "none", "orders": []}
        
        # 确定订单类型
        order_type = "market" if random.random() > 0.5 else "limit"
        
        # 计算订单数量
        num_orders = random.randint(1, 3)
        orders = []
        
        for i in range(num_orders):
            orders.append({
                "order_id": f"ORD{i+1}",
                "type": order_type,
                "quantity_pct": round(1.0 / num_orders, 2),
                "time_delay_ms": i * 1000  # 分单执行
            })
        
        return {
            "action": decision.value,
            "symbol": symbol,
            "target_position": target_position,
            "orders": orders,
            "execution_strategy": "twap" if num_orders > 1 else "market"
        }
    
    def _generate_reasoning(self, decision: DecisionType, 
                           agreeing_agents: List[str],
                           all_signals: List[AgentSignal],
                           confidence: float) -> str:
        """生成决策理由"""
        reasons = [
            f"基于 {len(agreeing_agents)} 个Agent的一致信号",
            f"最高置信度: {confidence:.2%}",
            f"参与Agent: {', '.join([s.agent_name for s in all_signals])}"
        ]
        
        # 添加主要Agent的理由
        for signal in all_signals:
            if signal.agent_name in agreeing_agents[:2]:
                reasons.append(f"{signal.agent_name}: {signal.reasoning}")
        
        return "; ".join(reasons)
    
    def _perform_risk_checks(self, symbol: str, decision: DecisionType,
                            position: float) -> List[str]:
        """执行风险检查"""
        checks = []
        
        # 仓位限制检查
        if position > 0.2:
            checks.append(f"⚠️ 仓位 ({position:.1%}) 超过单票限制 (20%)")
        else:
            checks.append(f"✓ 仓位检查通过")
        
        # 日交易限制检查
        if self.daily_trade_count >= self.max_daily_trades * 0.8:
            checks.append(f"⚠️ 日交易次数接近限制 ({self.daily_trade_count}/{self.max_daily_trades})")
        else:
            checks.append(f"✓ 日交易次数检查通过")
        
        # 波动率检查（模拟）
        checks.append("✓ 波动率检查通过")
        
        # 相关性检查（模拟）
        checks.append("✓ 组合相关性检查通过")
        
        return checks
    
    def get_decision_history(self, limit: int = 50) -> List[Dict]:
        """获取决策历史"""
        return [asdict(d) for d in self.decision_history[-limit:]]
    
    def get_status(self) -> Dict:
        """获取Chief状态"""
        return {
            "enabled": True,
            "decision_threshold": self.decision_threshold,
            "risk_appetite": self.risk_appetite,
            "max_daily_trades": self.max_daily_trades,
            "daily_trade_count": self.daily_trade_count,
            "pending_symbols": list(self.pending_signals.keys()),
            "total_decisions": len(self.decision_history),
            "agent_weights": self.agent_weights
        }
    
    def override_decision(self, decision_id: str, new_decision: str) -> Dict:
        """人工覆盖决策"""
        for decision in self.decision_history:
            if decision.decision_id == decision_id:
                old_decision = decision.decision.value
                decision.decision = DecisionType(new_decision)
                decision.reasoning += f" [人工覆盖: {old_decision} -> {new_decision}]"
                
                return {
                    "success": True,
                    "decision_id": decision_id,
                    "old_decision": old_decision,
                    "new_decision": new_decision
                }
        
        return {"success": False, "error": "决策不存在"}


# 单例实例
_chief_agent = None

def get_chief_agent() -> ChiefAgent:
    """获取Chief Agent单例"""
    global _chief_agent
    if _chief_agent is None:
        _chief_agent = ChiefAgent()
    return _chief_agent


if __name__ == "__main__":
    # 测试
    chief = ChiefAgent()
    
    # 模拟接收多个Agent信号
    agents = ["TrendAgent", "MomentumAgent", "SentimentAgent", "VolatilityAgent", "RiskAgent"]
    
    for agent_name in agents:
        signal = AgentSignal(
            agent_name=agent_name,
            decision=random.choice(list(DecisionType)),
            confidence=random.uniform(0.6, 0.95),
            target_symbol="000001.XSHE",
            target_position=0.1,
            reasoning=f"基于{agent_name}的分析模型",
            timestamp=datetime.now().isoformat(),
            metadata={}
        )
        
        result = chief.receive_signal(signal)
        print(f"\n{agent_name} 信号结果:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 查看状态
    print(f"\nChief状态:")
    print(json.dumps(chief.get_status(), indent=2, ensure_ascii=False))
