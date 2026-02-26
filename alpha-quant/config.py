"""
Alpha Quant - A股量化交易系统配置
"""
import os

# 资金配置
INITIAL_CAPITAL = 1_000_000  # 初始资金 100万
MAX_POSITION_PER_STOCK = 0.20  # 单股最大仓位 20%
MAX_DAILY_LOSS = 0.02  # 单日最大亏损 2%
MAX_CONSECUTIVE_DAYS = 3  # 连续亏损天数阈值
MAX_CONSECUTIVE_LOSS = 0.01  # 连续每日亏损阈值 1%
MARKET_FUSE_THRESHOLD = -0.03  # 大盘熔断阈值 -3%

# 数据接口配置 - 从环境变量读取
TUSHARE_TOKEN = os.getenv("TUSHARE_TOKEN", "")
AKSHARE_PATH = "/opt/akshare-env/bin/python3"

# 关注板块
FOCUS_SECTORS = [
    "新能源",
    "AI",
    "存储芯片",
    "算力",
    "半导体",
    "光伏",
    "锂电池",
    "机器人"
]

# 交易时间
TRADE_HOURS = {
    "morning_start": "09:30",
    "morning_end": "11:30",
    "afternoon_start": "13:00",
    "afternoon_end": "15:00"
}

# 数据缓存时间（秒）
CACHE_TTL = {
    "realtime": 30,  # 实时行情30秒
    "daily": 3600,   # 日线数据1小时
    "fundamental": 86400  # 基本面数据1天
}

# 输出配置
OUTPUT_FORMAT = "markdown"  # markdown / json
VERBOSE = True
