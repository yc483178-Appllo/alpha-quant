# trade_signal.py --- Kimi 交易信号发送工具
# 用于从 Kimi Claw 发送交易信号到信号服务器

import requests
from datetime import datetime
from typing import Dict, Optional
from loguru import logger
import os

# 信号服务器配置
SIGNAL_SERVER_URL = os.getenv("SIGNAL_SERVER_URL", "http://127.0.0.1:8765")


class TradeSignal:
    """交易信号发送器"""
    
    def __init__(self, server_url: str = SIGNAL_SERVER_URL):
        self.server_url = server_url
        self.session = requests.Session()
    
    def send_buy_signal(self, code: str, price: float, amount: int, 
                        reason: str = "", strategy: str = "manual", 
                        risk_level: str = "medium") -> Dict:
        """
        发送买入信号
        
        参数:
            code: 股票代码 (如 "600036.SH" 或 "sh.600036")
            price: 目标买入价格
            amount: 买入股数（必须是100的整数倍）
            reason: 买入理由
            strategy: 策略名称
            risk_level: 风险等级 (low/medium/high)
        """
        return self._send_signal(code, "buy", price, amount, reason, strategy, risk_level)
    
    def send_sell_signal(self, code: str, price: float, amount: int, 
                         reason: str = "", strategy: str = "manual", 
                         risk_level: str = "medium") -> Dict:
        """
        发送卖出信号
        
        参数:
            code: 股票代码
            price: 目标卖出价格
            amount: 卖出股数
            reason: 卖出理由（如"止盈"、"止损"、"调仓"等）
            strategy: 策略名称
            risk_level: 风险等级
        """
        return self._send_signal(code, "sell", price, amount, reason, strategy, risk_level)
    
    def _send_signal(self, code: str, action: str, price: float, amount: int, 
                     reason: str, strategy: str, risk_level: str) -> Dict:
        """内部方法：发送信号"""
        # 标准化股票代码
        code = self._normalize_code(code)
        
        # 参数校验
        if amount < 100 or amount % 100 != 0:
            return {"success": False, "error": "股数必须是100的整数倍且不少于100股"}
        
        if price <= 0:
            return {"success": False, "error": "价格必须大于0"}
        
        payload = {
            "code": code,
            "action": action,
            "price": price,
            "amount": amount,
            "reason": reason,
            "strategy": strategy,
            "risk_level": risk_level,
            "source": "kimi_claw",
            "timestamp": datetime.now().isoformat()
        }
        
        try:
            resp = self.session.post(
                f"{self.server_url}/api/signals",
                json=payload,
                timeout=5
            )
            
            if resp.status_code == 201:
                result = resp.json()
                signal_id = result.get("signal_id")
                needs_confirm = result.get("needs_confirm", False)
                
                logger.info(f"✅ 信号发送成功 #{signal_id}: {action.upper()} {code} @ {price} x {amount}")
                if needs_confirm:
                    logger.info(f"⏳ 信号 #{signal_id} 等待人工确认")
                
                return result
            elif resp.status_code == 429:
                logger.warning("⚠️ 信号队列已满，请稍后再试")
                return {"success": False, "error": "信号队列已满"}
            else:
                error = resp.json().get("error", "未知错误")
                logger.error(f"❌ 信号发送失败: {error}")
                return {"success": False, "error": error}
                
        except requests.exceptions.ConnectionError:
            logger.error("❌ 无法连接到信号服务器，请检查服务是否启动")
            return {"success": False, "error": "信号服务器未启动"}
        except Exception as e:
            logger.error(f"❌ 信号发送异常: {e}")
            return {"success": False, "error": str(e)}
    
    def _normalize_code(self, code: str) -> str:
        """标准化股票代码格式"""
        code = code.upper().replace(".SH", "").replace(".SZ", "")
        
        if code.startswith("6"):
            return f"sh.{code}"
        elif code.startswith("0") or code.startswith("3"):
            return f"sz.{code}"
        elif code.startswith("SH.") or code.startswith("SZ."):
            return code.lower()
        return code
    
    def confirm_signal(self, signal_id: int, reason: str = "") -> Dict:
        """确认信号（人工确认）"""
        try:
            resp = self.session.post(
                f"{self.server_url}/api/signals/confirm/{signal_id}",
                json={"reason": reason},
                timeout=3
            )
            return resp.json()
        except Exception as e:
            logger.error(f"信号确认失败: {e}")
            return {"success": False, "error": str(e)}
    
    def reject_signal(self, signal_id: int, reason: str = "") -> Dict:
        """拒绝信号"""
        try:
            resp = self.session.post(
                f"{self.server_url}/api/signals/reject/{signal_id}",
                json={"reason": reason},
                timeout=3
            )
            return resp.json()
        except Exception as e:
            logger.error(f"信号拒绝失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_pending_signals(self) -> Dict:
        """获取待处理的信号列表"""
        try:
            resp = self.session.get(
                f"{self.server_url}/api/signals?status=pending", 
                timeout=3
            )
            return resp.json()
        except Exception as e:
            logger.error(f"获取信号列表失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_history(self, limit: int = 50) -> Dict:
        """获取历史信号"""
        try:
            resp = self.session.get(
                f"{self.server_url}/api/signals/history?limit={limit}", 
                timeout=3
            )
            return resp.json()
        except Exception as e:
            logger.error(f"获取历史信号失败: {e}")
            return {"success": False, "error": str(e)}
    
    def get_stats(self) -> Dict:
        """获取信号统计信息"""
        try:
            resp = self.session.get(
                f"{self.server_url}/api/signals/stats", 
                timeout=3
            )
            return resp.json()
        except Exception as e:
            logger.error(f"获取统计信息失败: {e}")
            return {"success": False, "error": str(e)}


# 全局实例（方便快速调用）
_default_sender = None

def get_sender() -> TradeSignal:
    """获取默认信号发送器实例"""
    global _default_sender
    if _default_sender is None:
        _default_sender = TradeSignal()
    return _default_sender


# 便捷函数
def buy(code: str, price: float, amount: int, reason: str = "", 
        strategy: str = "manual", risk_level: str = "medium") -> Dict:
    """快速发送买入信号"""
    return get_sender().send_buy_signal(code, price, amount, reason, strategy, risk_level)

def sell(code: str, price: float, amount: int, reason: str = "", 
         strategy: str = "manual", risk_level: str = "medium") -> Dict:
    """快速发送卖出信号"""
    return get_sender().send_sell_signal(code, price, amount, reason, strategy, risk_level)


def confirm(signal_id: int, reason: str = "") -> Dict:
    """快速确认信号"""
    return get_sender().confirm_signal(signal_id, reason)


def reject(signal_id: int, reason: str = "") -> Dict:
    """快速拒绝信号"""
    return get_sender().reject_signal(signal_id, reason)


if __name__ == "__main__":
    print("=" * 50)
    print("Alpha Quant - 交易信号发送工具")
    print("=" * 50)
    print(f"服务器: {SIGNAL_SERVER_URL}")
    print("")
    print("使用示例:")
    print("  from trade_signal import buy, sell, confirm")
    print("  buy('600036', 35.50, 1000, '均线金叉买入')")
    print("  sell('600036', 38.00, 1000, '止盈卖出')")
    print("  confirm(1)")
