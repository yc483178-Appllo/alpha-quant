"""
KimiClaw V8.0 — 工具模块
"""

import logging
import sys
from datetime import datetime

# 配置日志
def setup_logger(name: str, level=logging.INFO):
    """设置日志记录器"""
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)
    
    logger.addHandler(handler)
    return logger


# 主日志记录器
logger = setup_logger("kimiclaw_v8")
audit_logger = setup_logger("kimiclaw_v8.audit")

__all__ = ["logger", "audit_logger", "setup_logger"]
