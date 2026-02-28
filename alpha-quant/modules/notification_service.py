# notification_service.py --- 三级通知分层服务
"""
通知级别：
- 日常报告（蓝色）: 晨报/复盘/周报等定时任务 → 飞书群消息 → Markdown 详细报告
- 重要预警（橙色）: 一二级风控触发，北向资金异常 → 飞书 @个人 → 简洁文字 + 关键数据  
- 紧急止损（红色）: 三级风控，大盘熔断触发 → 飞书 + 微信双推送 → 一行核心信息 + 操作建议
"""

import os
import json
import requests
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict
from datetime import datetime
from loguru import logger


class NotificationLevel(Enum):
    """通知级别枚举"""
    DAILY = "daily"      # 日常报告（蓝色）
    WARNING = "warning"  # 重要预警（橙色）
    URGENT = "urgent"    # 紧急止损（红色）


@dataclass
class NotificationConfig:
    """通知配置"""
    # 飞书配置
    feishu_webhook: str = ""
    feishu_user_id: str = ""  # 用于@个人
    
    # 微信配置（企业微信/推送加等）
    wechat_webhook: str = ""
    pushplus_token: str = ""
    
    # 通知开关
    enable_feishu: bool = True
    enable_wechat: bool = True


class NotificationService:
    """
    三级通知分层服务
    
    根据事件严重程度，自动选择合适的通知渠道和格式
    """
    
    # 级别颜色映射
    LEVEL_COLORS = {
        NotificationLevel.DAILY: "blue",
        NotificationLevel.WARNING: "orange", 
        NotificationLevel.URGENT: "red"
    }
    
    # 级别标题映射
    LEVEL_TITLES = {
        NotificationLevel.DAILY: "📊 日常报告",
        NotificationLevel.WARNING: "⚠️ 重要预警",
        NotificationLevel.URGENT: "🚨 紧急止损"
    }
    
    def __init__(self, config: Optional[NotificationConfig] = None):
        """
        初始化通知服务
        
        Args:
            config: 通知配置，默认从环境变量读取
        """
        # 先加载环境变量
        from dotenv import load_dotenv
        load_dotenv()
        
        if config is None:
            config = NotificationConfig(
                feishu_webhook=os.getenv("FEISHU_WEBHOOK_URL", ""),
                feishu_user_id=os.getenv("FEISHU_USER_ID", ""),
                wechat_webhook=os.getenv("WECHAT_WEBHOOK_URL", ""),
                pushplus_token=os.getenv("PUSHPLUS_TOKEN", ""),
                enable_feishu=True,
                enable_wechat=True
            )
        
        self.config = config
        logger.debug(f"通知服务初始化: feishu_webhook={config.feishu_webhook[:30]}..." if config.feishu_webhook else "feishu_webhook=空")
        
    def _send_feishu(self, content: str, level: NotificationLevel, 
                     at_user: bool = False) -> bool:
        """
        发送飞书消息
        
        Args:
            content: 消息内容
            level: 通知级别
            at_user: 是否@个人
            
        Returns:
            是否发送成功
        """
        if not self.config.enable_feishu or not self.config.feishu_webhook:
            logger.warning("飞书通知未启用或未配置")
            return False
        
        try:
            color = self.LEVEL_COLORS[level]
            title = self.LEVEL_TITLES[level]
            
            # 构建消息卡片
            card = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": title
                        },
                        "template": color
                    },
                    "elements": [
                        {
                            "tag": "markdown",
                            "content": content
                        }
                    ]
                }
            }
            
            # 添加@个人
            if at_user and self.config.feishu_user_id:
                card["card"]["elements"].append({
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"<at id={self.config.feishu_user_id}></at>"
                    }
                })
            
            response = requests.post(
                self.config.feishu_webhook,
                json=card,
                timeout=10
            )
            
            if response.status_code == 200:
                logger.info(f"✅ 飞书通知发送成功 [{level.value}]")
                return True
            else:
                logger.error(f"❌ 飞书通知失败: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 飞书通知异常: {e}")
            return False
    
    def _send_wechat(self, content: str, level: NotificationLevel) -> bool:
        """
        发送微信消息（企业微信/推送加）
        
        Args:
            content: 消息内容
            level: 通知级别
            
        Returns:
            是否发送成功
        """
        if not self.config.enable_wechat:
            return False
        
        success = False
        
        # 尝试企业微信
        if self.config.wechat_webhook:
            try:
                response = requests.post(
                    self.config.wechat_webhook,
                    json={"msgtype": "text", "text": {"content": content}},
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info("✅ 企业微信通知发送成功")
                    success = True
            except Exception as e:
                logger.error(f"❌ 企业微信通知失败: {e}")
        
        # 尝试 PushPlus
        if self.config.pushplus_token:
            try:
                response = requests.post(
                    "http://www.pushplus.plus/send",
                    json={
                        "token": self.config.pushplus_token,
                        "title": self.LEVEL_TITLES[level],
                        "content": content,
                        "template": "txt"
                    },
                    timeout=10
                )
                if response.status_code == 200:
                    logger.info("✅ PushPlus通知发送成功")
                    success = True
            except Exception as e:
                logger.error(f"❌ PushPlus通知失败: {e}")
        
        return success
    
    def send_daily_report(self, title: str, content: str, 
                          data: Optional[Dict] = None) -> bool:
        """
        发送日常报告（蓝色级别）
        
        Args:
            title: 报告标题
            content: Markdown 格式的详细内容
            data: 附加数据
            
        Returns:
            是否发送成功
        """
        logger.info("📊 发送日常报告")
        
        # 构建详细报告
        report = f"## {title}\n\n{content}"
        
        if data:
            report += "\n\n### 关键数据\n"
            for key, value in data.items():
                report += f"- **{key}**: {value}\n"
        
        report += f"\n\n---\n*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
        
        return self._send_feishu(report, NotificationLevel.DAILY, at_user=False)
    
    def send_warning_alert(self, alert_type: str, message: str, 
                          key_data: Dict, suggestion: str = "") -> bool:
        """
        发送重要预警（橙色级别）
        
        Args:
            alert_type: 预警类型（如"风控触发"/"资金异常"）
            message: 预警消息
            key_data: 关键数据字典
            suggestion: 建议操作
            
        Returns:
            是否发送成功
        """
        logger.warning(f"⚠️ 发送重要预警: {alert_type}")
        
        # 构建简洁预警信息
        content = f"**{alert_type}**\n\n{message}\n\n"
        
        # 关键数据
        content += "**关键数据:**\n"
        for key, value in key_data.items():
            content += f"- {key}: {value}\n"
        
        if suggestion:
            content += f"\n**建议:** {suggestion}"
        
        content += f"\n\n*时间: {datetime.now().strftime('%H:%M:%S')}*"
        
        return self._send_feishu(content, NotificationLevel.WARNING, at_user=True)
    
    def send_urgent_stop(self, reason: str, action: str, 
                         position_info: Optional[str] = None) -> bool:
        """
        发送紧急止损通知（红色级别）
        
        Args:
            reason: 触发原因
            action: 核心操作建议
            position_info: 持仓信息（可选）
            
        Returns:
            是否发送成功
        """
        logger.error(f"🚨 发送紧急止损: {reason}")
        
        # 一行核心信息
        core_message = f"【紧急】{reason} - {action}"
        
        # 飞书卡片（稍详细）
        feishu_content = f"**{reason}**\n\n🚨 **操作建议:** {action}"
        if position_info:
            feishu_content += f"\n\n📋 **持仓信息:** {position_info}"
        feishu_content += f"\n\n*时间: {datetime.now().strftime('%H:%M:%S')}*"
        
        # 发送飞书
        feishu_ok = self._send_feishu(feishu_content, NotificationLevel.URGENT, at_user=True)
        
        # 发送微信（更简洁）
        wechat_ok = self._send_wechat(core_message, NotificationLevel.URGENT)
        
        return feishu_ok or wechat_ok
    
    def notify(self, level: NotificationLevel, **kwargs) -> bool:
        """
        通用通知接口
        
        Args:
            level: 通知级别
            **kwargs: 根据级别不同的参数
            
        Returns:
            是否发送成功
        """
        if level == NotificationLevel.DAILY:
            return self.send_daily_report(
                title=kwargs.get("title", "日常报告"),
                content=kwargs.get("content", ""),
                data=kwargs.get("data")
            )
        elif level == NotificationLevel.WARNING:
            return self.send_warning_alert(
                alert_type=kwargs.get("alert_type", "预警"),
                message=kwargs.get("message", ""),
                key_data=kwargs.get("key_data", {}),
                suggestion=kwargs.get("suggestion", "")
            )
        elif level == NotificationLevel.URGENT:
            return self.send_urgent_stop(
                reason=kwargs.get("reason", ""),
                action=kwargs.get("action", ""),
                position_info=kwargs.get("position_info")
            )
        else:
            logger.error(f"未知的通知级别: {level}")
            return False


# 便捷函数
def notify_daily(title: str, content: str, **kwargs) -> bool:
    """发送日常报告"""
    service = NotificationService()
    return service.send_daily_report(title, content, **kwargs)


def notify_warning(alert_type: str, message: str, **kwargs) -> bool:
    """发送重要预警"""
    service = NotificationService()
    return service.send_warning_alert(alert_type, message, **kwargs)


def notify_urgent(reason: str, action: str, **kwargs) -> bool:
    """发送紧急止损"""
    service = NotificationService()
    return service.send_urgent_stop(reason, action, **kwargs)


# 使用示例
if __name__ == "__main__":
    # 初始化服务
    notifier = NotificationService()
    
    # 示例1: 日常报告
    notifier.send_daily_report(
        title="Alpha每日晨报",
        content="今日市场震荡上行，北向资金净流入25亿...",
        data={
            "上证指数": "+0.5%",
            "深证成指": "+0.8%",
            "创业板指": "+1.2%",
            "成交额": "1.2万亿"
        }
    )
    
    # 示例2: 重要预警
    notifier.send_warning_alert(
        alert_type="二级风控触发",
        message="持仓个股跌幅超过5%",
        key_data={
            "触发股票": "000001.SZ",
            "当前跌幅": "-5.2%",
            "持仓占比": "10%"
        },
        suggestion="建议减仓50%或设置止损"
    )
    
    # 示例3: 紧急止损
    notifier.send_urgent_stop(
        reason="三级风控触发 - 个股跌停",
        action="立即清仓",
        position_info="000001.SZ 持仓1000股，亏损8%"
    )
