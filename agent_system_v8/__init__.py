"""
KimiClaw V8.0 — Agent系统模块
资金拍卖、对抗测试、策略生命周期
"""

from .auction import StrategyAuctionSystem
from .adversarial import AdversarialTester
from .lifecycle import StrategyLifecycleManager

__all__ = [
    "StrategyAuctionSystem",
    "AdversarialTester",
    "StrategyLifecycleManager"
]
