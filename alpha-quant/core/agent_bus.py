#!/usr/bin/env python3
"""
Alpha V5.0 - Agent Bus 信号总线
协调Multi-Agent之间的通信和信号路由
"""

import json
import redis
import threading
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from loguru import logger


@dataclass
class AgentSignal:
    """Agent信号标准格式"""
    signal_type: str  # scout_report / sentiment_report / picker_list / 
                      # drl_recommendation / optimizer_recommendation / 
                      # guard_check / chief_decision / trade_signal
    source: str       # Scout / Sentiment / Picker / DRL / Optimizer / Guard / Chief / Trader
    data: Dict
    priority: str     # low / medium / high / critical
    timestamp: str
    target_agents: List[str] = None  # 目标Agent列表，None表示广播
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentSignal':
        return cls(**data)


class AgentBus:
    """
    Agent Bus - V5.0信号总线
    
    功能:
    1. 信号发布/订阅
    2. 信号路由
    3. 优先级仲裁
    4. 冲突解决
    5. 降级容错
    """
    
    def __init__(self, redis_url: str = "redis://127.0.0.1:6379/0"):
        self.redis_url = redis_url
        self.redis_client = None
        self._connect_redis()
        
        # 本地订阅者
        self.subscribers: Dict[str, List[Callable]] = {}
        
        # 信号优先级权重
        self.priority_weights = {
            "critical": 100,
            "high": 50,
            "medium": 10,
            "low": 1
        }
        
        # 运行状态
        self.running = False
        self.listener_thread = None
        
        logger.info("✅ Agent Bus初始化完成")
    
    def _connect_redis(self):
        """连接Redis"""
        try:
            self.redis_client = redis.from_url(self.redis_url, decode_responses=True)
            self.redis_client.ping()
            logger.info("✅ Redis连接成功")
        except Exception as e:
            logger.warning(f"⚠️ Redis连接失败: {e}，将使用本地模式")
            self.redis_client = None
    
    def publish(self, signal: AgentSignal) -> bool:
        """
        发布信号
        
        Args:
            signal: Agent信号
        
        Returns:
            bool: 是否成功
        """
        try:
            signal_data = json.dumps(signal.to_dict())
            
            if self.redis_client:
                # 发布到Redis
                channel = f"alpha:agent:{signal.signal_type}"
                self.redis_client.publish(channel, signal_data)
                
                # 同时存入历史记录
                self.redis_client.lpush("alpha:signal_history", signal_data)
                self.redis_client.ltrim("alpha:signal_history", 0, 999)  # 保留最近1000条
            
            # 本地分发
            self._local_dispatch(signal)
            
            logger.debug(f"📡 信号发布: {signal.signal_type} from {signal.source} [{signal.priority}]")
            return True
            
        except Exception as e:
            logger.error(f"❌ 信号发布失败: {e}")
            return False
    
    def subscribe(self, signal_type: str, callback: Callable[[AgentSignal], None]):
        """
        订阅信号
        
        Args:
            signal_type: 信号类型
            callback: 回调函数
        """
        if signal_type not in self.subscribers:
            self.subscribers[signal_type] = []
        self.subscribers[signal_type].append(callback)
        logger.info(f"📬 订阅信号: {signal_type}")
    
    def _local_dispatch(self, signal: AgentSignal):
        """本地信号分发"""
        # 按信号类型分发
        if signal.signal_type in self.subscribers:
            for callback in self.subscribers[signal.signal_type]:
                try:
                    callback(signal)
                except Exception as e:
                    logger.error(f"❌ 信号处理失败: {e}")
        
        # 通配符订阅
        if "*" in self.subscribers:
            for callback in self.subscribers["*"]:
                try:
                    callback(signal)
                except Exception as e:
                    logger.error(f"❌ 通配符信号处理失败: {e}")
    
    def start_listener(self):
        """启动Redis监听线程"""
        if not self.redis_client or self.running:
            return
        
        self.running = True
        self.listener_thread = threading.Thread(target=self._redis_listener, daemon=True)
        self.listener_thread.start()
        logger.info("🎧 Redis监听线程已启动")
    
    def _redis_listener(self):
        """Redis订阅监听"""
        try:
            pubsub = self.redis_client.pubsub()
            pubsub.psubscribe("alpha:agent:*")
            
            for message in pubsub.listen():
                if not self.running:
                    break
                
                if message["type"] == "pmessage":
                    try:
                        signal_data = json.loads(message["data"])
                        signal = AgentSignal.from_dict(signal_data)
                        self._local_dispatch(signal)
                    except Exception as e:
                        logger.error(f"❌ Redis消息解析失败: {e}")
                        
        except Exception as e:
            logger.error(f"❌ Redis监听异常: {e}")
            self.running = False
    
    def stop_listener(self):
        """停止监听"""
        self.running = False
        logger.info("🛑 Redis监听线程已停止")
    
    def get_signal_history(self, n: int = 100) -> List[AgentSignal]:
        """获取信号历史"""
        if not self.redis_client:
            return []
        
        try:
            history = self.redis_client.lrange("alpha:signal_history", 0, n - 1)
            return [AgentSignal.from_dict(json.loads(h)) for h in history]
        except Exception as e:
            logger.error(f"❌ 获取信号历史失败: {e}")
            return []
    
    def route_signal(self, signal: AgentSignal, target_agents: List[str]) -> AgentSignal:
        """
        信号路由
        
        根据目标Agent列表进行路由
        """
        signal.target_agents = target_agents
        return signal
    
    def arbitrate_conflicts(self, signals: List[AgentSignal]) -> Optional[AgentSignal]:
        """
        冲突仲裁
        
        当多个信号冲突时，根据优先级和时间戳仲裁
        """
        if not signals:
            return None
        
        if len(signals) == 1:
            return signals[0]
        
        # 按优先级和时间戳排序
        def sort_key(s: AgentSignal):
            return (
                -self.priority_weights.get(s.priority, 0),
                s.timestamp  # 时间戳早的优先
            )
        
        sorted_signals = sorted(signals, key=sort_key)
        winner = sorted_signals[0]
        
        logger.info(f"⚖️ 冲突仲裁: 从{len(signals)}个信号中选择 {winner.source} 的信号")
        return winner
    
    def check_degradation(self, agent_name: str, last_heartbeat: datetime) -> bool:
        """
        降级检查
        
        检查Agent是否超时，需要降级
        """
        timeout_seconds = 60  # 默认60秒超时
        elapsed = (datetime.now() - last_heartbeat).total_seconds()
        
        if elapsed > timeout_seconds:
            logger.warning(f"⚠️ Agent {agent_name} 超时 ({elapsed:.0f}s)，触发降级")
            return True
        
        return False


class AgentCoordinator:
    """
    Agent协调器
    
    封装常用的Agent协调模式
    """
    
    def __init__(self, agent_bus: AgentBus):
        self.bus = agent_bus
        self.agent_heartbeats: Dict[str, datetime] = {}
        
        # 启动心跳检查线程
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_checker, daemon=True)
        self.heartbeat_thread.start()
    
    def register_agent(self, agent_name: str):
        """注册Agent"""
        self.agent_heartbeats[agent_name] = datetime.now()
        logger.info(f"📝 Agent注册: {agent_name}")
    
    def heartbeat(self, agent_name: str):
        """Agent心跳"""
        self.agent_heartbeats[agent_name] = datetime.now()
    
    def _heartbeat_checker(self):
        """心跳检查线程"""
        while True:
            threading.Event().wait(30)  # 每30秒检查一次
            
            for agent_name, last_beat in list(self.agent_heartbeats.items()):
                if self.bus.check_degradation(agent_name, last_beat):
                    # 触发降级处理
                    self._handle_degradation(agent_name)
    
    def _handle_degradation(self, agent_name: str):
        """处理Agent降级"""
        logger.warning(f"🚨 Agent {agent_name} 降级处理")
        
        # 发布降级信号
        signal = AgentSignal(
            signal_type="agent_degradation",
            source="AgentCoordinator",
            data={"agent": agent_name, "action": "degraded"},
            priority="high",
            timestamp=datetime.now().isoformat()
        )
        self.bus.publish(signal)
    
    def coordinate_premarket_flow(self, chief_agent, scout_data, sentiment_data, picker_data):
        """
        协调盘前决策流程
        
        1. Scout发布盘前报告
        2. Sentiment发布舆情报告
        3. Picker发布选股清单
        4. Chief执行决策
        5. 发布交易信号
        """
        from modules.chief_agent import ScoutReport, SentimentReport, PickerList
        
        # 转换为标准格式
        scout_report = ScoutReport(**scout_data)
        sentiment_report = SentimentReport(**sentiment_data)
        picker_list = PickerList(**picker_data)
        
        # Chief决策
        decision = chief_agent.make_decision(
            scout_report, sentiment_report, picker_list
        )
        
        # 发布决策信号
        signal = AgentSignal(
            signal_type="chief_decision",
            source="Chief",
            data={
                "decision_id": decision.decision_id,
                "source": decision.decision_source,
                "confidence": decision.confidence,
                "risk_level": decision.risk_level,
                "execution_plan": decision.execution_plan,
                "reasoning": decision.reasoning
            },
            priority="high" if decision.risk_level != "low" else "medium",
            timestamp=datetime.now().isoformat()
        )
        
        self.bus.publish(signal)
        
        # 生成交易信号
        trade_signals = chief_agent.generate_signal_for_trader(decision)
        for ts in trade_signals:
            trade_signal = AgentSignal(
                signal_type="trade_signal",
                source="Chief",
                data=ts,
                priority="high" if decision.confidence > 0.7 else "medium",
                timestamp=datetime.now().isoformat()
            )
            self.bus.publish(trade_signal)
        
        return decision


# 便捷函数
def create_agent_bus(redis_url: str = "redis://127.0.0.1:6379/0") -> AgentBus:
    """创建Agent Bus实例"""
    return AgentBus(redis_url)


def create_agent_coordinator(agent_bus: AgentBus) -> AgentCoordinator:
    """创建Agent协调器"""
    return AgentCoordinator(agent_bus)


if __name__ == "__main__":
    # 测试Agent Bus
    print("测试Agent Bus...")
    
    bus = create_agent_bus()
    
    # 订阅测试
    def test_handler(signal: AgentSignal):
        print(f"收到信号: {signal.signal_type} from {signal.source}")
    
    bus.subscribe("test_signal", test_handler)
    
    # 发布测试信号
    signal = AgentSignal(
        signal_type="test_signal",
        source="Test",
        data={"message": "Hello"},
        priority="medium",
        timestamp=datetime.now().isoformat()
    )
    bus.publish(signal)
    
    print("Agent Bus测试完成")
