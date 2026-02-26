"""
日志模块 - 基于 Loguru 的增强日志
"""
import os
import sys
from pathlib import Path
from loguru import logger
from modules.config_manager import config_manager

def setup_logging():
    """配置日志系统"""
    log_config = config_manager.get_logging_config()
    
    # 日志目录
    log_dir = Path(log_config.get('log_dir', './logs'))
    log_dir.mkdir(exist_ok=True)
    
    # 日志格式
    log_format = log_config.get(
        'format',
        "{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} | {message}"
    )
    
    # 移除默认处理器
    logger.remove()
    
    # 添加控制台处理器
    logger.add(
        sys.stdout,
        format=log_format,
        level=config_manager.get('global_config.log_level', 'INFO'),
        colorize=True
    )
    
    # 添加文件处理器
    rotation = log_config.get('rotation', '10 MB')
    retention = log_config.get('retention', '30 days')
    
    logger.add(
        log_dir / "alpha_{time:YYYY-MM-DD}.log",
        rotation=rotation,
        retention=retention,
        format=log_format,
        level="DEBUG",
        encoding='utf-8'
    )
    
    # 错误日志单独文件
    logger.add(
        log_dir / "alpha_error_{time:YYYY-MM-DD}.log",
        rotation=rotation,
        retention=retention,
        format=log_format,
        level="ERROR",
        encoding='utf-8',
        filter=lambda record: record["level"].name == "ERROR"
    )
    
    logger.info("📝 日志系统初始化完成")
    return logger

# 全局 logger
log = setup_logging()
