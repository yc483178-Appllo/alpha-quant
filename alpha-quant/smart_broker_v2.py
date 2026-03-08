"""
智能券商管理器 V2 - V6.0 升级模块
文件: smart_broker_v2.py
功能: 多券商管理、手动/自动切换、执行质量评分、实时状态监控
依赖: requests, threading, logging
注意: 需配合各券商SDK使用（PTrade/QMT/Easytrader）
"""

import os
import json
import time
import logging
import threading
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("SmartBrokerV2")


class BrokerStatus(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"
    MAINTENANCE = "maintenance"


@dataclass
class BrokerHealthMetrics:
    """券商健康指标"""
    broker_id: str
    status: str = "disconnected"
    latency_ms: float = 9999.0        # 最新延迟（毫秒）
    avg_latency_ms: float = 9999.0    # 5分钟平均延迟
    success_rate: float = 0.0         # 下单成功率（过去100笔）
    avg_slippage_bps: float = 0.0     # 平均滑点（基点）
    commission_rate: float = 0.001    # 佣金费率
    last_heartbeat: str = ""
    last_error: str = ""
    quality_score: float = 0.0        # 综合质量评分 0-100
    connected_account: str = ""       # 当前连接账户
    available_cash: float = 0.0       # 可用资金


@dataclass
class SwitchRule:
    """自动切换规则"""
    id: str
    name: str
    condition_type: str    # latency / success_rate / quality_score / scheduled / manual
    threshold: float       # 触发阈值
    target_broker: str     # 切换目标券商
    enabled: bool = True
    priority: int = 0      # 优先级（越大越优先）


class BrokerHealthMonitor:
    """券商健康监控（后台线程）"""
    def __init__(self, broker_configs: List[Dict], check_interval: int = 30):
        self.broker_configs = {b["id"]: b for b in broker_configs}
        self.metrics: Dict[str, BrokerHealthMetrics] = {
            b["id"]: BrokerHealthMetrics(broker_id=b["id"])
            for b in broker_configs
        }
        self.check_interval = check_interval
        self._thread = None
        self._running = False
        self._latency_history: Dict[str, List[float]] = {b["id"]: [] for b in broker_configs}
        self._order_history: Dict[str, List[bool]] = {b["id"]: [] for b in broker_configs}

    def start(self):
        """启动健康监控后台线程"""
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        logger.info("券商健康监控已启动")

    def stop(self):
        self._running = False

    def _monitor_loop(self):
        while self._running:
            for broker_id, config in self.broker_configs.items():
                self._check_broker(broker_id, config)
            time.sleep(self.check_interval)

    def _check_broker(self, broker_id: str, config: Dict):
        """检查单个券商连接状态"""
        metrics = self.metrics[broker_id]
        try:
            start = time.time()
            # 模拟心跳检测（实际需调用各券商SDK的ping/heartbeat接口）
            broker_type = config.get("type", "ptrade")
            if broker_type == "ptrade":
                self._ping_ptrade(config)
            elif broker_type == "qmt":
                self._ping_qmt(config)
            latency = (time.time() - start) * 1000
            self._latency_history[broker_id].append(latency)
            self._latency_history[broker_id] = self._latency_history[broker_id][-10:]
            metrics.status = BrokerStatus.CONNECTED.value
            metrics.latency_ms = latency
            metrics.avg_latency_ms = float(np.mean(self._latency_history[broker_id]))
            metrics.last_heartbeat = datetime.now().isoformat()
        except Exception as e:
            metrics.status = BrokerStatus.ERROR.value
            metrics.last_error = str(e)[:100]
            self._latency_history[broker_id].append(9999.0)
        # 更新综合质量评分
        metrics.quality_score = self._calc_quality_score(broker_id)

    def _ping_ptrade(self, config: Dict):
        """PTrade心跳检测（需配合PTrade SDK）"""
        # 实际实现需调用: pta.get_trading_dates() 等轻量API
        pass  # 模拟成功

    def _ping_qmt(self, config: Dict):
        """QMT心跳检测"""
        pass  # 实际实现调用xtdata.get_trading_dates()

    def _calc_quality_score(self, broker_id: str) -> float:
        """
        综合质量评分计算
        Score = 延迟分×0.3 + 成功率×0.4 + 滑点分×0.2 + 费率分×0.1
        """
        m = self.metrics[broker_id]
        if m.status != BrokerStatus.CONNECTED.value:
            return 0.0
        # 延迟分（0-100，延迟越低越高）
        latency_score = max(0, 100 - m.avg_latency_ms / 10)  # 1000ms → 0分
        # 成功率分
        success_score = m.success_rate * 100
        # 滑点分（滑点越低越高）
        slippage_score = max(0, 100 - m.avg_slippage_bps * 2)
        # 费率分（0.001 → 100分，0.002 → 50分）
        rate_score = max(0, 100 - m.commission_rate * 50000)
        return (
            latency_score * 0.3 +
            success_score * 0.4 +
            slippage_score * 0.2 +
            rate_score * 0.1
        )

    def record_order_result(self, broker_id: str, success: bool, slippage_bps: float = 0):
        """记录下单结果（供执行层调用）"""
        if broker_id not in self._order_history:
            self._order_history[broker_id] = []
        self._order_history[broker_id].append(success)
        self._order_history[broker_id] = self._order_history[broker_id][-100:]
        m = self.metrics[broker_id]
        if self._order_history[broker_id]:
            m.success_rate = float(np.mean(self._order_history[broker_id]))
        # 更新滑点（EMA平滑）
        m.avg_slippage_bps = m.avg_slippage_bps * 0.9 + slippage_bps * 0.1

    def get_best_broker(self) -> Optional[str]:
        """获取当前质量评分最高的券商"""
        connected = {k: v for k, v in self.metrics.items()
                    if v.status == BrokerStatus.CONNECTED.value}
        if not connected:
            return None
        return max(connected, key=lambda k: connected[k].quality_score)

    def get_all_metrics(self) -> Dict[str, Dict]:
        """获取所有券商指标（供看板V3.0调用）"""
        return {k: {
            "broker_id": v.broker_id,
            "status": v.status,
            "latency_ms": round(v.avg_latency_ms, 1),
            "success_rate": round(v.success_rate * 100, 1),
            "avg_slippage_bps": round(v.avg_slippage_bps, 2),
            "commission_rate": v.commission_rate,
            "quality_score": round(v.quality_score, 1),
            "last_heartbeat": v.last_heartbeat,
            "connected_account": v.connected_account,
            "available_cash": v.available_cash
        } for k, v in self.metrics.items()}


class SmartBrokerSwitcher:
    """
    智能券商切换器
    支持: 手动切换 / 自动切换（质量评分）/ 条件规则切换 / 指令切换
    """
    def __init__(self, monitor: BrokerHealthMonitor, config: Dict):
        self.monitor = monitor
        self.rules: List[SwitchRule] = self._load_rules(config)
        self.current_broker_id: str = config.get("primary_broker", "ptrade")
        self.switch_history: List[Dict] = []
        self._auto_switch_thread = None
        self._running = False
        self._switch_callbacks: List[Callable] = []

    def _load_rules(self, config: Dict) -> List[SwitchRule]:
        """加载切换规则"""
        rules_cfg = config.get("switch_rules", [])
        rules = []
        for r in rules_cfg:
            rules.append(SwitchRule(
                id=r.get("id", f"rule_{len(rules)}"),
                name=r.get("name", ""),
                condition_type=r.get("condition_type", "quality_score"),
                threshold=r.get("threshold", 60.0),
                target_broker=r.get("target_broker", ""),
                enabled=r.get("enabled", True),
                priority=r.get("priority", 0)
            ))
        return sorted(rules, key=lambda r: -r.priority)

    def register_switch_callback(self, callback: Callable):
        """注册切换回调（切换后通知OMS等组件）"""
        self._switch_callbacks.append(callback)

    def switch_to(self, broker_id: str, reason: str = "manual") -> Dict:
        """
        执行券商切换
        broker_id: 目标券商ID
        reason: 切换原因（manual/auto/condition/instruction）
        """
        if broker_id == self.current_broker_id:
            return {"success": True, "message": f"已在使用 {broker_id}"}
        # 检查目标券商状态
        metrics = self.monitor.metrics.get(broker_id)
        if not metrics or metrics.status != BrokerStatus.CONNECTED.value:
            return {"success": False, "message": f"目标券商 {broker_id} 不可用（状态: {metrics.status if metrics else '未知'}）"}
        old_broker = self.current_broker_id
        self.current_broker_id = broker_id
        # 记录切换历史
        record = {
            "from": old_broker,
            "to": broker_id,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "old_quality": self.monitor.metrics.get(old_broker, BrokerHealthMetrics(old_broker)).quality_score,
            "new_quality": metrics.quality_score
        }
        self.switch_history.append(record)
        self.switch_history = self.switch_history[-50:]  # 保留最近50条
        logger.info(f"券商已切换: {old_broker} → {broker_id} (原因: {reason})")
        # 通知回调
        for cb in self._switch_callbacks:
            try:
                cb(old_broker, broker_id, reason)
            except Exception:
                pass
        return {"success": True, "from": old_broker, "to": broker_id, "reason": reason}

    def process_instruction(self, instruction: str) -> Dict:
        """
        处理自然语言切换指令（供Kimi Claw调用）
        示例指令:
          "切换到QMT" / "使用华泰券商" / "切换最优券商" / "切回主券商"
        """
        instruction = instruction.strip()
        # 关键词映射
        broker_keywords = {
            "ptrade": ["ptrade", "华泰", "ptrade证券"],
            "qmt": ["qmt", "迅投", "民生", "miniqmt"],
            "easytrader": ["easytrader", "通用", "普通"]
        }
        for broker_id, keywords in broker_keywords.items():
            if any(kw in instruction for kw in keywords):
                return self.switch_to(broker_id, reason="instruction")
        if "最优" in instruction or "最好" in instruction or "best" in instruction.lower():
            best = self.monitor.get_best_broker()
            if best:
                return self.switch_to(best, reason="instruction_best")
        if "主券商" in instruction or "默认" in instruction:
            return self.switch_to("ptrade", reason="instruction_primary")
        return {"success": False, "message": f"无法解析指令: {instruction}"}

    def start_auto_switch(self, check_interval: int = 60):
        """启动自动切换监控"""
        self._running = True
        self._auto_switch_thread = threading.Thread(
            target=self._auto_switch_loop,
            args=(check_interval,),
            daemon=True
        )
        self._auto_switch_thread.start()
        logger.info("自动券商切换已启动")

    def _auto_switch_loop(self, interval: int):
        """自动切换检测循环"""
        while self._running:
            try:
                self._check_switch_rules()
            except Exception as e:
                logger.error(f"自动切换检测异常: {e}")
            time.sleep(interval)

    def _check_switch_rules(self):
        """检查所有启用的切换规则"""
        current_metrics = self.monitor.metrics.get(self.current_broker_id)
        if not current_metrics:
            return
        for rule in self.rules:
            if not rule.enabled:
                continue
            triggered = False
            if rule.condition_type == "quality_score" and current_metrics.quality_score < rule.threshold:
                triggered = True
            elif rule.condition_type == "latency" and current_metrics.avg_latency_ms > rule.threshold:
                triggered = True
            elif rule.condition_type == "success_rate" and current_metrics.success_rate * 100 < rule.threshold:
                triggered = True
            if triggered and rule.target_broker != self.current_broker_id:
                logger.warning(f"切换规则触发: {rule.name} → 切换到 {rule.target_broker}")
                self.switch_to(rule.target_broker, reason=f"auto_rule:{rule.id}")
                break  # 执行第一个触发规则后退出

    def get_dashboard_data(self) -> Dict:
        """获取看板V3.0券商面板所需数据"""
        return {
            "current_broker": self.current_broker_id,
            "all_brokers": self.monitor.get_all_metrics(),
            "switch_history": self.switch_history[-10:],
            "active_rules": [
                {"id": r.id, "name": r.name, "condition": r.condition_type,
                 "threshold": r.threshold, "target": r.target_broker, "enabled": r.enabled}
                for r in self.rules
            ]
        }


class SmartBrokerManagerV2:
    """
    Smart Broker Manager V2 对外接口
    整合健康监控 + 切换器 + OMS适配
    """
    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            cfg = json.load(f)
        broker_cfg = cfg.get("broker_management_v2", {})
        broker_configs = broker_cfg.get("brokers", [
            {"id": "ptrade", "type": "ptrade", "name": "华泰PTrade", "commission_rate": 0.00025},
            {"id": "qmt", "type": "qmt", "name": "迅投QMT", "commission_rate": 0.00030},
        ])
        self.monitor = BrokerHealthMonitor(
            broker_configs=broker_configs,
            check_interval=broker_cfg.get("health_check_interval", 30)
        )
        self.switcher = SmartBrokerSwitcher(self.monitor, broker_cfg)

    def start(self):
        """启动所有组件"""
        self.monitor.start()
        if self.switcher:
            self.switcher.start_auto_switch(check_interval=60)
        logger.info("Smart Broker Manager V2 已启动")

    def switch_broker(self, broker_id: str, reason: str = "manual") -> Dict:
        """对外切换接口"""
        return self.switcher.switch_to(broker_id, reason)

    def process_instruction(self, instruction: str) -> Dict:
        """处理自然语言切换指令"""
        return self.switcher.process_instruction(instruction)

    def get_dashboard_data(self) -> Dict:
        """看板V3.0数据"""
        return self.switcher.get_dashboard_data()

    @property
    def current_broker_id(self) -> str:
        return self.switcher.current_broker_id
