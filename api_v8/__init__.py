"""
KimiClaw V8.0 — API路由模块
"""

from fastapi import APIRouter

router_v8 = APIRouter(prefix="/v8")

# 将在 routes.py 中定义具体端点
__all__ = ["router_v8"]
