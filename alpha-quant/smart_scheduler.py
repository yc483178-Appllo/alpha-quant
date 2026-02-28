#!/usr/bin/env python3
"""
smart_scheduler.py --- 智能任务调度器
根据交易日历自动判断是否执行任务
"""
import sys
import os
import argparse
from datetime import datetime
from loguru import logger

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.trade_calendar import TradeCalendar, get_calendar


def setup_logger():
    """配置日志"""
    logger.remove()
    logger.add(
        sys.stdout,
        format="{time:HH:mm:ss} | {level} | {message}",
        level="INFO"
    )


def main():
    parser = argparse.ArgumentParser(description='智能任务调度器 - 基于交易日历')
    parser.add_argument(
        '--task-type', '-t',
        choices=['daily', 'intraday', 'pre_market', 'post_market', 'any'],
        default='daily',
        help='任务类型: daily(每日), intraday(盘中), pre_market(盘前), post_market(盘后), any(任意时间)'
    )
    parser.add_argument(
        '--command', '-c',
        required=True,
        help='要执行的命令（如果满足条件）'
    )
    parser.add_argument(
        '--force', '-f',
        action='store_true',
        help='强制执行，忽略交易日历检查'
    )
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='试运行模式，只检查条件不执行命令'
    )
    
    args = parser.parse_args()
    setup_logger()
    
    # 获取交易日历
    cal = get_calendar()
    today = datetime.now().strftime("%Y-%m-%d")
    
    logger.info("=" * 50)
    logger.info(f"📅 智能任务调度器 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 50)
    logger.info(f"任务类型: {args.task_type}")
    logger.info(f"执行命令: {args.command[:50]}..." if len(args.command) > 50 else f"执行命令: {args.command}")
    logger.info(f"今日日期: {today}")
    logger.info(f"是否交易日: {'✅ 是' if cal.is_trade_date() else '❌ 否'}")
    logger.info(f"市场阶段: {cal.get_market_phase()}")
    
    # 判断是否执行
    should_execute = args.force or cal.should_run_task(args.task_type)
    
    if should_execute:
        logger.info(f"✅ 条件满足，{'准备执行' if not args.dry_run else '[试运行] 将执行'}任务")
        
        if args.dry_run:
            logger.info("[试运行模式] 命令未实际执行")
            logger.info(f"将执行的命令: {args.command}")
            return 0
        
        # 执行命令
        logger.info("🚀 开始执行任务...")
        exit_code = os.system(args.command)
        
        if exit_code == 0:
            logger.info("✅ 任务执行成功")
        else:
            logger.error(f"❌ 任务执行失败，退出码: {exit_code}")
        
        return exit_code
    else:
        logger.info(f"⏸️ 条件不满足，跳过任务执行")
        logger.info(f"原因: 非交易日或不在{args.task_type}时段内")
        return 0


if __name__ == "__main__":
    sys.exit(main())
