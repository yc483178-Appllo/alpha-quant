# notifier.py --- 统一通知推送模块
# 支持：飞书（卡片消息）、钉钉（签名验证）、微信（PushPlus）

import os
import time
import hmac
import hashlib
import base64
import urllib.parse
import requests
from loguru import logger
from dotenv import load_dotenv

load_dotenv()

class Notifier:
    """统一消息推送器 - 支持多通道分级推送"""

    def __init__(self):
        self.feishu_webhook = os.getenv("FEISHU_WEBHOOK_URL", "")
        self.dingtalk_webhook = os.getenv("DINGTALK_WEBHOOK_URL", "")
        self.dingtalk_secret = os.getenv("DINGTALK_SECRET", "")
        self.pushplus_token = os.getenv("PUSHPLUS_TOKEN", "")

    # ========== 飞书推送 ==========
    def send_feishu_text(self, text, at_user: str = None):
        """飞书简单文本消息"""
        if not self.feishu_webhook:
            logger.warning("飞书 webhook 未配置")
            return False
        try:
            payload = {
                "msg_type": "text",
                "content": {"text": text}
            }
            if at_user:
                payload["at"] = {"atOpenIds": [at_user]}
            
            resp = requests.post(self.feishu_webhook, json=payload, timeout=5)
            return resp.status_code == 200
        except Exception as e:
            logger.error(f"飞书推送失败: {e}")
            return False

    def send_feishu_card(self, title, content, color="blue", at_user: str = None):
        """飞书卡片消息（富文本，支持Markdown）"""
        if not self.feishu_webhook:
            logger.warning("飞书 webhook 未配置")
            return False
            
        card = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": title},
                    "template": color  # blue/green/orange/red
                },
                "elements": [{
                    "tag": "markdown",
                    "content": content
                }]
            }
        }
        
        if at_user:
            card["card"]["elements"].append({
                "tag": "div",
                "text": {"tag": "lark_md", "content": f"<at id={at_user}></at>"}
            })
            
        try:
            resp = requests.post(self.feishu_webhook, json=card, timeout=5)
            success = resp.status_code == 200
            if success:
                logger.info(f"飞书卡片推送成功: {title}")
            else:
                logger.error(f"飞书卡片推送失败: {resp.status_code}")
            return success
        except Exception as e:
            logger.error(f"飞书卡片推送失败: {e}")
            return False

    # ========== 钉钉推送（含签名验证） ==========
    def _dingtalk_sign(self):
        """生成钉钉签名"""
        if not self.dingtalk_secret:
            return None, None
        timestamp = str(round(time.time() * 1000))
        string_to_sign = f"{timestamp}\n{self.dingtalk_secret}"
        hmac_code = hmac.new(
            self.dingtalk_secret.encode("utf-8"),
            string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256
        ).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        return timestamp, sign

    def send_dingtalk(self, title, text):
        """钉钉机器人推送（Markdown格式）"""
        if not self.dingtalk_webhook:
            logger.warning("钉钉 webhook 未配置")
            return False
            
        timestamp, sign = self._dingtalk_sign()
        if not sign:
            url = self.dingtalk_webhook
        else:
            url = f"{self.dingtalk_webhook}&timestamp={timestamp}&sign={sign}"
            
        try:
            resp = requests.post(url, json={
                "msgtype": "markdown",
                "markdown": {"title": title, "text": text}
            }, timeout=5)
            success = resp.status_code == 200
            if success:
                logger.info(f"钉钉推送成功: {title}")
            return success
        except Exception as e:
            logger.error(f"钉钉推送失败: {e}")
            return False

    # ========== 微信 PushPlus 推送 ==========
    def send_wechat(self, title, content, template="markdown"):
        """微信PushPlus推送"""
        if not self.pushplus_token:
            logger.warning("PushPlus token 未配置")
            return False
        try:
            resp = requests.post("http://www.pushplus.plus/send", json={
                "token": self.pushplus_token,
                "title": title,
                "content": content,
                "template": template
            }, timeout=5)
            success = resp.status_code == 200
            if success:
                logger.info(f"微信推送成功: {title}")
            return success
        except Exception as e:
            logger.error(f"微信推送失败: {e}")
            return False

    # ========== 统一分级推送 ==========
    def notify(self, title, content, level="info", at_user: str = None):
        """
        按通知级别自动选择推送渠道
        
        Args:
            title: 消息标题
            content: 消息内容（支持Markdown）
            level: 级别 - info(飞书) / warning(飞书+钉钉) / critical(全渠道)
            at_user: 飞书用户ID，用于@个人
            
        Returns:
            dict: 各渠道推送结果
        """
        color_map = {"info": "blue", "warning": "orange", "critical": "red"}
        color = color_map.get(level, "blue")
        
        results = {"feishu": False, "dingtalk": False, "wechat": False}
        
        # 飞书（所有级别）
        results["feishu"] = self.send_feishu_card(title, content, color, at_user)
        
        # 钉钉（warning及以上）
        if level in ("warning", "critical"):
            results["dingtalk"] = self.send_dingtalk(title, content)
        
        # 微信（仅critical）
        if level == "critical":
            results["wechat"] = self.send_wechat(title, content)
        
        # 记录推送结果
        success_count = sum(results.values())
        logger.info(f"通知推送完成 [{level}]: {success_count}/3 成功")
        
        return results

    # ========== 便捷方法 ==========
    def info(self, title, content):
        """日常信息"""
        return self.notify(title, content, level="info")
    
    def warning(self, title, content, at_user: str = None):
        """重要警告"""
        return self.notify(title, content, level="warning", at_user=at_user)
    
    def critical(self, title, content, at_user: str = None):
        """紧急通知"""
        return self.notify(title, content, level="critical", at_user=at_user)


# === 使用示例 ===
if __name__ == "__main__":
    notifier = Notifier()
    
    # 日常报告
    notifier.info("📊 每日晨报", "今日大盘预计震荡上行...")
    
    # 重要预警
    notifier.warning("⚠️ 风控预警", "平安银行浮亏超8%", at_user="ou_aa48a587777a9251baf61454b0db5c09")
    
    # 紧急止损
    notifier.critical("🚨 紧急止损", "大盘跌破3%熔断线！", at_user="ou_aa48a587777a9251baf61454b0db5c09")
