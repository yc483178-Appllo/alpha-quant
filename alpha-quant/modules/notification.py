"""
通知模块 - 支持多渠道消息推送
"""
import requests
import json
import hmac
import hashlib
import base64
import urllib.parse
import time
from typing import Dict, List
from modules.config_manager import config_manager

class NotificationManager:
    """通知管理器"""
    
    def __init__(self):
        self.config = config_manager.get_notification_config()
    
    def send(self, message: str, level: str = "info", title: str = None):
        """
        发送通知
        level: info, warning, critical
        """
        channels = config_manager.get_notification_channels(level)
        
        if not channels:
            print(f"[{level.upper()}] {message}")
            return
        
        for channel in channels:
            try:
                if channel == "feishu":
                    self._send_feishu(message, title)
                elif channel == "dingtalk":
                    self._send_dingtalk(message, title)
                elif channel == "wechat":
                    self._send_wechat(message, title)
            except Exception as e:
                print(f"发送 {channel} 通知失败: {e}")
    
    def _send_feishu(self, message: str, title: str = None):
        """发送飞书通知（支持签名校验）"""
        webhook_url = self.config.get('feishu_webhook')
        secret = self.config.get('feishu_secret')  # 签名密钥
        
        if not webhook_url:
            return
        
        # 构建payload
        payload = {
            "msg_type": "text",
            "content": {
                "text": f"{title}\n{message}" if title else message
            }
        }
        
        # 如果有签名密钥，计算签名
        if secret:
            timestamp = str(int(time.time()))
            # 飞书签名校验：timestamp + "\n" + secret 的 HMAC-SHA256，再Base64编码
            string_to_sign = f"{timestamp}\n{secret}"
            hmac_code = hmac.new(
                string_to_sign.encode('utf-8'),
                digestmod=hashlib.sha256
            ).digest()
            sign = base64.b64encode(hmac_code).decode('utf-8')
            
            # 签名和时间戳放在payload中（不是请求头）
            payload["timestamp"] = timestamp
            payload["sign"] = sign
        
        headers = {"Content-Type": "application/json"}
        
        response = requests.post(webhook_url, json=payload, headers=headers, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get("code") == 0:
                print("✅ 飞书通知发送成功")
            else:
                print(f"❌ 飞书通知发送失败: {result.get('msg', '未知错误')}")
        else:
            print(f"❌ 飞书通知发送失败: {response.status_code} - {response.text}")
    
    def _send_dingtalk(self, message: str, title: str = None):
        """发送钉钉通知"""
        webhook_url = self.config.get('dingtalk_webhook')
        secret = self.config.get('dingtalk_secret')
        
        if not webhook_url:
            return
        
        # 计算签名
        if secret:
            timestamp = str(round(time.time() * 1000))
            string_to_sign = f"{timestamp}\n{secret}"
            hmac_code = hmac.new(
                secret.encode('utf-8'),
                string_to_sign.encode('utf-8'),
                digestmod=hashlib.sha256
            ).digest()
            sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
            webhook_url = f"{webhook_url}&timestamp={timestamp}&sign={sign}"
        
        payload = {
            "msgtype": "text",
            "text": {
                "content": f"{title}\n{message}" if title else message
            }
        }
        
        response = requests.post(webhook_url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ 钉钉通知发送成功")
        else:
            print(f"❌ 钉钉通知发送失败: {response.text}")
    
    def _send_wechat(self, message: str, title: str = None):
        """发送微信通知（PushPlus）"""
        token = self.config.get('wechat_pushplus_token')
        if not token:
            return
        
        url = f"http://www.pushplus.plus/send/{token}"
        payload = {
            "title": title or "Alpha Quant 通知",
            "content": message,
            "template": "txt"
        }
        
        response = requests.post(url, json=payload, timeout=10)
        if response.status_code == 200:
            print("✅ 微信通知发送成功")
        else:
            print(f"❌ 微信通知发送失败: {response.text}")
    
    def send_daily_report(self, report: str):
        """发送日报"""
        self.send(report, level="daily_report", title="📊 Alpha 每日报告")
    
    def send_warning(self, message: str):
        """发送警告"""
        self.send(f"⚠️ {message}", level="warning", title="Alpha 警告")
    
    def send_critical(self, message: str):
        """发送紧急通知"""
        self.send(f"🚨 {message}", level="critical", title="Alpha 紧急通知")

# 全局实例
notification_manager = NotificationManager()
