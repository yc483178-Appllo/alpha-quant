"""
Alpha-Genesis V6.1 SimEdge - 统一日志体系
完善 P2-1: 统一日志体系
======================================
loguru替代logging，统一JSON格式，自动轮转，异常堆栈完整捕获

Author: Alpha-Genesis Team
Version: 6.1.0
Date: 2026-03-09
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

# 尝试导入 loguru
try:
    from loguru import logger
    LOGURU_AVAILABLE = True
except ImportError:
    LOGURU_AVAILABLE = False
    import logging
    logger = logging.getLogger("AlphaLogger")


class UnifiedLogger:
    """
    统一日志管理器
    
    功能：
    - loguru 替代标准 logging
    - JSON 格式输出
    - 自动日志轮转
    - 异常堆栈完整捕获
    - 多级别日志分离
    """
    
    def __init__(
        self,
        log_dir: str = "./logs",
        app_name: str = "alpha-genesis",
        level: str = "INFO",
        rotation: str = "10 MB",
        retention: str = "30 days"
    ):
        """
        初始化统一日志
        
        Args:
            log_dir: 日志目录
            app_name: 应用名称
            level: 日志级别
            rotation: 轮转条件
            retention: 保留时间
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.app_name = app_name
        
        if LOGURU_AVAILABLE:
            self._setup_loguru(level, rotation, retention)
        else:
            self._setup_std_logging(level)
    
    def _setup_loguru(self, level: str, rotation: str, retention: str):
        """配置 loguru"""
        # 移除默认处理器
        logger.remove()
        
        # 1. 控制台输出 - 彩色格式
        logger.add(
            sys.stdout,
            level=level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                   "<level>{message}</level>",
            colorize=True,
            enqueue=True
        )
        
        # 2. 主日志文件 - JSON格式
        main_log = self.log_dir / f"{self.app_name}.jsonl"
        logger.add(
            str(main_log),
            level=level,
            format="{message}",  # JSON格式，由serialize处理
            serialize=True,      # 自动序列化为JSON
            rotation=rotation,
            retention=retention,
            encoding="utf-8",
            enqueue=True,
            backtrace=True,      # 捕获完整堆栈
            diagnose=True
        )
        
        # 3. 错误日志文件 - 单独记录ERROR及以上
        error_log = self.log_dir / f"{self.app_name}_error.log"
        logger.add(
            str(error_log),
            level="ERROR",
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}\n{exception}",
            rotation=rotation,
            retention=retention,
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=True
        )
        
        # 4. 模块分离日志
        modules = ["trading", "evolution", "sentiment", "broker", "api"]
        for module in modules:
            module_log = self.log_dir / f"{self.app_name}_{module}.jsonl"
            logger.add(
                str(module_log),
                level=level,
                format="{message}",
                serialize=True,
                rotation=rotation,
                retention=retention,
                encoding="utf-8",
                enqueue=True,
                filter=lambda record, mod=module: mod in record["name"]
            )
        
        logger.info(f"Loguru 日志系统初始化完成 | 目录: {self.log_dir}")
    
    def _setup_std_logging(self, level: str):
        """回退到标准 logging"""
        logging.basicConfig(
            level=getattr(logging, level),
            format="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler(self.log_dir / f"{self.app_name}.log", encoding="utf-8")
            ]
        )
        logger.warning("loguru 未安装，使用标准 logging")
    
    def get_logger(self, name: str):
        """
        获取命名日志器
        
        Args:
            name: 日志器名称 (如 "alpha.trading", "alpha.evolution")
        
        Returns:
            logger 实例
        """
        if LOGURU_AVAILABLE:
            # loguru 使用 bind 来区分不同模块
            return logger.bind(name=f"{self.app_name}.{name}")
        else:
            return logging.getLogger(f"{self.app_name}.{name}")
    
    def log_structured(self, level: str, message: str, extra: Dict = None):
        """
        结构化日志记录
        
        Args:
            level: 日志级别
            message: 消息
            extra: 额外结构化数据
        """
        extra = extra or {}
        
        log_data = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "app": self.app_name,
            **extra
        }
        
        if LOGURU_AVAILABLE:
            logger.log(level, json.dumps(log_data, ensure_ascii=False))
        else:
            getattr(logger, level.lower())(json.dumps(log_data, ensure_ascii=False))


# 全局日志实例
_unified_logger: Optional[UnifiedLogger] = None


def init_logging(
    log_dir: str = "./logs",
    app_name: str = "alpha-genesis",
    level: str = "INFO"
) -> UnifiedLogger:
    """
    初始化全局日志
    
    Args:
        log_dir: 日志目录
        app_name: 应用名称
        level: 日志级别
    
    Returns:
        UnifiedLogger 实例
    """
    global _unified_logger
    _unified_logger = UnifiedLogger(log_dir, app_name, level)
    return _unified_logger


def get_logger(name: str = ""):
    """
    获取日志器
    
    Args:
        name: 模块名称
    
    Returns:
        logger 实例
    """
    global _unified_logger
    
    if _unified_logger is None:
        _unified_logger = init_logging()
    
    return _unified_logger.get_logger(name)


# ═══════════════════════════════════════════════════════════
# 异常捕获装饰器
# ═══════════════════════════════════════════════════════════

def catch_exceptions(logger_name: str = None):
    """
    异常捕获装饰器
    
    用法:
        @catch_exceptions("trading")
        def my_function():
            ...
    """
    def decorator(func):
        log = get_logger(logger_name or func.__module__)
        
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log.error(f"函数 {func.__name__} 执行失败: {e}")
                # 重新抛出异常
                raise
        
        return wrapper
    return decorator


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== 统一日志体系测试 ===\n")
    
    # 初始化日志
    init_logging(log_dir="./test_logs", level="DEBUG")
    
    # 获取模块日志器
    trading_log = get_logger("trading")
    evolution_log = get_logger("evolution")
    
    # 测试不同级别日志
    print("1. 测试不同级别日志:")
    trading_log.debug("这是 DEBUG 日志")
    trading_log.info("这是 INFO 日志")
    trading_log.warning("这是 WARNING 日志")
    trading_log.error("这是 ERROR 日志")
    
    # 测试结构化日志
    print("\n2. 测试结构化日志:")
    unified = UnifiedLogger(log_dir="./test_logs")
    unified.log_structured("INFO", "交易执行", {
        "order_id": "ORD001",
        "code": "600519",
        "side": "buy",
        "qty": 100,
        "price": 1800.0
    })
    
    # 测试异常捕获
    print("\n3. 测试异常捕获:")
    @catch_exceptions("test")
    def test_exception():
        raise ValueError("测试异常")
    
    try:
        test_exception()
    except:
        print("   异常已捕获并记录")
    
    # 测试不同模块日志
    print("\n4. 测试模块分离:")
    evolution_log.info("进化引擎日志 - 应写入 evolution 日志文件")
    
    print("\n✅ 日志系统测试完成")
    print(f"   日志目录: ./test_logs/")
