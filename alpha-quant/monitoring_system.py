"""
Alpha-Genesis V6.1 SimEdge - 监控告警系统
完善 P2-3: 监控告警
======================================
/api/v6/health 健康检查端点 + 飞书/邮件/企微 webhook告警

Author: Alpha-Genesis Team
Version: 6.1.0
Date: 2026-03-09
"""

import os
import json
import time
import logging
import requests
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger("MonitorAlert")


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """告警渠道"""
    FEISHU = "feishu"
    DINGTALK = "dingtalk"
    WECHAT = "wechat"
    EMAIL = "email"
    SLACK = "slack"


@dataclass
class HealthStatus:
    """健康状态"""
    component: str
    status: str  # healthy/degraded/unhealthy
    latency_ms: float
    last_check: str
    error_msg: str = ""
    metadata: Dict = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Alert:
    """告警数据结构"""
    id: str
    level: AlertLevel
    title: str
    message: str
    component: str
    timestamp: str
    channels: List[AlertChannel]
    acknowledged: bool = False


class HealthChecker:
    """
    健康检查器
    
    功能：
    - 多组件健康检查
    - 性能指标收集
    - 依赖服务检测
    """
    
    def __init__(self):
        self.components: Dict[str, Callable] = {}
        self.status_cache: Dict[str, HealthStatus] = {}
        self.check_interval = 30  # 秒
        
    def register_component(self, name: str, check_func: Callable):
        """
        注册健康检查组件
        
        Args:
            name: 组件名称
            check_func: 检查函数，返回 (status, latency_ms, metadata)
        """
        self.components[name] = check_func
        logger.info(f"注册健康检查组件: {name}")
    
    def check_all(self) -> Dict[str, HealthStatus]:
        """
        检查所有组件
        
        Returns:
            组件状态字典
        """
        results = {}
        
        for name, check_func in self.components.items():
            start = time.time()
            try:
                status, metadata = check_func()
                latency = (time.time() - start) * 1000
                
                results[name] = HealthStatus(
                    component=name,
                    status=status,
                    latency_ms=latency,
                    last_check=datetime.now().isoformat(),
                    metadata=metadata or {}
                )
            except Exception as e:
                results[name] = HealthStatus(
                    component=name,
                    status="unhealthy",
                    latency_ms=9999,
                    last_check=datetime.now().isoformat(),
                    error_msg=str(e)
                )
        
        self.status_cache = results
        return results
    
    def get_overall_status(self) -> Dict:
        """获取整体健康状态"""
        if not self.status_cache:
            self.check_all()
        
        statuses = [s.status for s in self.status_cache.values()]
        
        if all(s == "healthy" for s in statuses):
            overall = "healthy"
        elif all(s == "unhealthy" for s in statuses):
            overall = "unhealthy"
        else:
            overall = "degraded"
        
        return {
            "status": overall,
            "components": {name: asdict(status) for name, status in self.status_cache.items()},
            "timestamp": datetime.now().isoformat(),
            "version": "6.1.0"
        }


class AlertManager:
    """
    告警管理器
    
    功能：
    - 多渠道告警发送
    - 告警聚合
    - 告警抑制
    - 告警历史
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.alert_history: List[Alert] = []
        self.webhook_configs: Dict[AlertChannel, Dict] = {}
        self._load_webhook_configs()
        
        # 告警抑制
        self.last_alert_time: Dict[str, float] = {}
        self.alert_cooldown = 300  # 5分钟冷却
    
    def _load_webhook_configs(self):
        """加载 webhook 配置"""
        # 飞书
        feishu_webhook = self.config.get("feishu_webhook") or os.environ.get("FEISHU_WEBHOOK")
        feishu_secret = self.config.get("feishu_secret") or os.environ.get("FEISHU_SECRET")
        if feishu_webhook:
            self.webhook_configs[AlertChannel.FEISHU] = {
                "webhook": feishu_webhook,
                "secret": feishu_secret
            }
        
        # 钉钉
        dingtalk_webhook = self.config.get("dingtalk_webhook") or os.environ.get("DINGTALK_WEBHOOK")
        if dingtalk_webhook:
            self.webhook_configs[AlertChannel.DINGTALK] = {
                "webhook": dingtalk_webhook
            }
        
        # 企业微信
        wechat_webhook = self.config.get("wechat_webhook") or os.environ.get("WECHAT_WEBHOOK")
        if wechat_webhook:
            self.webhook_configs[AlertChannel.WECHAT] = {
                "webhook": wechat_webhook
            }
    
    def send_alert(
        self,
        level: AlertLevel,
        title: str,
        message: str,
        component: str = "system",
        channels: List[AlertChannel] = None
    ) -> bool:
        """
        发送告警
        
        Args:
            level: 告警级别
            title: 标题
            message: 消息
            component: 组件名
            channels: 发送渠道 (默认所有已配置渠道)
        
        Returns:
            是否成功
        """
        channels = channels or list(self.webhook_configs.keys())
        
        # 告警抑制检查
        alert_key = f"{component}:{title}"
        now = time.time()
        if alert_key in self.last_alert_time:
            if now - self.last_alert_time[alert_key] < self.alert_cooldown:
                logger.debug(f"告警抑制: {alert_key}")
                return False
        
        self.last_alert_time[alert_key] = now
        
        # 创建告警记录
        alert = Alert(
            id=f"ALT_{int(now * 1000)}",
            level=level,
            title=title,
            message=message,
            component=component,
            timestamp=datetime.now().isoformat(),
            channels=channels
        )
        self.alert_history.append(alert)
        
        # 发送到各渠道
        success = True
        for channel in channels:
            if channel in self.webhook_configs:
                try:
                    if channel == AlertChannel.FEISHU:
                        self._send_feishu(alert)
                    elif channel == AlertChannel.DINGTALK:
                        self._send_dingtalk(alert)
                    elif channel == AlertChannel.WECHAT:
                        self._send_wechat(alert)
                except Exception as e:
                    logger.error(f"发送告警到 {channel.value} 失败: {e}")
                    success = False
        
        return success
    
    def _send_feishu(self, alert: Alert):
        """发送飞书告警"""
        config = self.webhook_configs[AlertChannel.FEISHU]
        webhook = config["webhook"]
        
        # 颜色映射
        color_map = {
            AlertLevel.INFO: "blue",
            AlertLevel.WARNING: "orange",
            AlertLevel.ERROR: "red",
            AlertLevel.CRITICAL: "red"
        }
        
        card = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": f"🔔 {alert.title}"
                    },
                    "template": color_map.get(alert.level, "blue")
                },
                "elements": [
                    {
                        "tag": "div",
                        "text": {
                            "tag": "lark_md",
                            "content": f"**级别:** {alert.level.value}\n**组件:** {alert.component}\n**时间:** {alert.timestamp}\n\n{alert.message}"
                        }
                    }
                ]
            }
        }
        
        response = requests.post(webhook, json=card, timeout=10)
        response.raise_for_status()
        logger.info(f"飞书告警发送成功: {alert.title}")
    
    def _send_dingtalk(self, alert: Alert):
        """发送钉钉告警"""
        config = self.webhook_configs[AlertChannel.DINGTALK]
        webhook = config["webhook"]
        
        message = {
            "msgtype": "markdown",
            "markdown": {
                "title": alert.title,
                "text": f"## 🔔 {alert.title}\n\n"
                        f"**级别:** {alert.level.value}\n\n"
                        f"**组件:** {alert.component}\n\n"
                        f"**时间:** {alert.timestamp}\n\n"
                        f"**内容:** {alert.message}"
            }
        }
        
        response = requests.post(webhook, json=message, timeout=10)
        response.raise_for_status()
        logger.info(f"钉钉告警发送成功: {alert.title}")
    
    def _send_wechat(self, alert: Alert):
        """发送企业微信告警"""
        config = self.webhook_configs[AlertChannel.WECHAT]
        webhook = config["webhook"]
        
        message = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"**{alert.title}**\n\n"
                          f"级别: {alert.level.value}\n"
                          f"组件: {alert.component}\n"
                          f"时间: {alert.timestamp}\n\n"
                          f"{alert.message}"
            }
        }
        
        response = requests.post(webhook, json=message, timeout=10)
        response.raise_for_status()
        logger.info(f"企业微信告警发送成功: {alert.title}")
    
    def send_health_report(self, health_status: Dict):
        """发送健康报告"""
        status = health_status.get("status", "unknown")
        components = health_status.get("components", {})
        
        # 只有非健康状态才发送告警
        if status != "healthy":
            unhealthy = [name for name, s in components.items() if s["status"] != "healthy"]
            
            level = AlertLevel.ERROR if status == "unhealthy" else AlertLevel.WARNING
            
            self.send_alert(
                level=level,
                title=f"系统健康状态异常: {status}",
                message=f"以下组件异常: {', '.join(unhealthy)}",
                component="health_checker",
                channels=[AlertChannel.FEISHU]
            )


class MonitoringSystem:
    """
    监控系统
    
    整合健康检查和告警管理
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.health_checker = HealthChecker()
        self.alert_manager = AlertManager(config)
        
        self._running = False
        self._monitor_thread = None
    
    def start(self, interval: int = 30):
        """
        启动监控
        
        Args:
            interval: 检查间隔(秒)
        """
        self._running = True
        
        def monitor_loop():
            while self._running:
                try:
                    # 执行健康检查
                    health = self.health_checker.get_overall_status()
                    
                    # 发送健康报告
                    self.alert_manager.send_health_report(health)
                    
                    time.sleep(interval)
                except Exception as e:
                    logger.error(f"监控循环出错: {e}")
                    time.sleep(interval)
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
        
        logger.info(f"监控系统已启动 | 检查间隔: {interval}s")
    
    def stop(self):
        """停止监控"""
        self._running = False
        logger.info("监控系统已停止")


# ═══════════════════════════════════════════════════════════
# Flask 健康检查端点
# ═══════════════════════════════════════════════════════════

def register_health_routes(app, health_checker: HealthChecker):
    """
    注册健康检查路由到 Flask 应用
    
    Args:
        app: Flask 应用
        health_checker: 健康检查器
    """
    from flask import jsonify
    
    @app.route("/api/v6/health", methods=["GET"])
    def health_endpoint():
        """健康检查端点"""
        return jsonify(health_checker.get_overall_status())
    
    @app.route("/api/v6/health/components", methods=["GET"])
    def health_components():
        """组件健康详情"""
        return jsonify({
            "components": {name: asdict(status) for name, status in health_checker.status_cache.items()}
        })
    
    @app.route("/api/v6/health/ready", methods=["GET"])
    def health_ready():
        """就绪检查"""
        status = health_checker.get_overall_status()
        if status["status"] == "healthy":
            return jsonify({"ready": True}), 200
        else:
            return jsonify({"ready": False, "reason": status["status"]}), 503


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== 监控告警系统测试 ===\n")
    
    # 创建健康检查器
    checker = HealthChecker()
    
    # 注册测试组件
    def check_database():
        return "healthy", {"connections": 10, "latency_ms": 5}
    
    def check_api():
        return "healthy", {"requests_per_min": 120}
    
    def check_broker():
        # 模拟异常
        return "degraded", {"latency_ms": 500}
    
    checker.register_component("database", check_database)
    checker.register_component("api", check_api)
    checker.register_component("broker", check_broker)
    
    # 测试健康检查
    print("1. 测试健康检查:")
    status = checker.get_overall_status()
    print(f"   整体状态: {status['status']}")
    for name, comp in status['components'].items():
        print(f"   - {name}: {comp['status']} ({comp['latency_ms']:.1f}ms)")
    
    # 测试告警管理器 (模拟模式)
    print("\n2. 测试告警管理器:")
    alert_mgr = AlertManager()
    
    # 模拟发送告警 (无 webhook 配置时会跳过)
    result = alert_mgr.send_alert(
        level=AlertLevel.WARNING,
        title="测试告警",
        message="这是一条测试告警消息",
        component="test"
    )
    print(f"   告警发送结果: {result}")
    
    # 测试健康报告
    print("\n3. 测试健康报告:")
    alert_mgr.send_health_report(status)
    
    print("\n✅ 监控告警系统测试完成")
    print("   提示: 配置 webhook URL 后可测试真实告警发送")
