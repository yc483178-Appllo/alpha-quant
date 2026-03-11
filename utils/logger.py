"""
统一日志系统 — V7.0: 20年审计留存
"""
import logging
import sys
from pathlib import Path
from datetime import datetime

# 日志目录
LOG_DIR = Path("/var/log/kimi-claw")
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 格式化
formatter = logging.Formatter(
    '%(asctime)s | %(levelname)-8s | %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 文件处理器 (保留20年)
today = datetime.now().strftime("%Y-%m-%d")
file_handler = logging.FileHandler(LOG_DIR / f"kimi-claw-{today}.log", encoding='utf-8')
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

# 控制台处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(formatter)
console_handler.setLevel(logging.DEBUG)

# 根日志器
root_logger = logging.getLogger("kimi-claw")
root_logger.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)
root_logger.addHandler(console_handler)


def get_logger(name: str) -> logging.Logger:
    """获取命名日志器"""
    return logging.getLogger(f"kimi-claw.{name}")


# 导出
logger = root_logger
