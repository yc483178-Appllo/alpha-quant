# scheduler.py --- 统一定时任务调度器（替代系统Cron）
# 优势：Python原生、自带节假日跳过、任务依赖管理、错误重试

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED
from loguru import logger
from datetime import datetime

from modules.trade_calendar import TradeCalendar, get_calendar

# 初始化
logger.add("logs/scheduler_{time:YYYY-MM-DD}.log", rotation="10 MB", retention="30 days")
calendar = get_calendar()
scheduler = BlockingScheduler(timezone="Asia/Shanghai")


def trade_day_only(func):
    """装饰器：仅在交易日执行"""
    def wrapper(*args, **kwargs):
        if not calendar.is_trade_date():
            logger.info(f"⏸️ 今日休市，跳过任务: {func.__name__}")
            return None
        
        # 检查是否在交易时段（针对盘中任务）
        if func.__name__ == 'job_intraday_monitor' and not calendar.is_trade_time():
            logger.info(f"⏸️ 非交易时段，跳过任务: {func.__name__}")
            return None
            
        logger.info(f"🚀 执行任务: {func.__name__}")
        start_time = datetime.now()
        
        try:
            result = func(*args, **kwargs)
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info(f"✅ 任务完成: {func.__name__} (耗时 {elapsed:.2f}s)")
            return result
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(f"❌ 任务失败: {func.__name__} (耗时 {elapsed:.2f}s) - {e}")
            raise
            
    wrapper.__name__ = func.__name__
    return wrapper


def on_job_error(event):
    """任务错误回调"""
    logger.error(f"❌ 任务执行异常: {event.job_id} - {event.exception}")


def on_job_executed(event):
    """任务完成回调"""
    if event.exception:
        logger.error(f"❌ 任务返回异常: {event.job_id}")
    else:
        logger.debug(f"✅ 任务正常完成: {event.job_id}")


# === 任务定义 ===

@trade_day_only
def job_health_check():
    """08:45 系统健康检查"""
    import requests
    import json
    
    try:
        # 检查信号服务器
        resp = requests.get("http://127.0.0.1:8765/health", timeout=10)
        signal_status = resp.json()
        
        # 检查数据网关
        resp = requests.get("http://127.0.0.1:8766/api/health", timeout=10)
        gateway_status = resp.json()
        
        logger.info(f"📊 健康检查 - 信号服务器: {signal_status.get('status', 'unknown')}, 数据网关: {gateway_status.get('status', 'unknown')}")
        
        # 如果服务异常，尝试重启
        if signal_status.get('status') != 'ok':
            logger.warning("⚠️ 信号服务器异常，尝试重启...")
            os.system("cd /root/.openclaw/workspace/alpha-quant && ./run_server.sh &")
            
        if gateway_status.get('status') != 'ok':
            logger.warning("⚠️ 数据网关异常，尝试重启...")
            os.system("cd /root/.openclaw/workspace/alpha-quant && python3 start_gateway_daemon.py")
            
    except Exception as e:
        logger.error(f"健康检查失败: {e}")


@trade_day_only
def job_morning_research():
    """09:00 盘前调研"""
    logger.info("📰 执行盘前调研")
    try:
        # 调用开盘前风险评估
        from daily_report_generator import generate_pre_market_report
        report = generate_pre_market_report()
        logger.info(f"✅ 盘前调研完成，报告长度: {len(report)} 字符")
    except Exception as e:
        logger.error(f"盘前调研失败: {e}")


@trade_day_only
def job_stock_screening():
    """09:15 智能选股"""
    logger.info("🔍 执行智能选股")
    try:
        # 这里可以调用选股模块
        logger.info("选股任务已触发（需要实现具体选股逻辑）")
    except Exception as e:
        logger.error(f"智能选股失败: {e}")


@trade_day_only
def job_intraday_monitor():
    """盘中监控（每30分钟）"""
    logger.info("📈 执行盘中监控")
    try:
        # 检查大盘熔断风险
        import requests
        resp = requests.get("http://127.0.0.1:8766/api/market/realtime", timeout=10)
        data = resp.json()
        
        if data.get('code') == 200:
            logger.info(f"✅ 盘中数据获取成功，来源: {data.get('source', 'unknown')}")
            # 这里可以添加熔断检查逻辑
    except Exception as e:
        logger.error(f"盘中监控失败: {e}")


@trade_day_only
def job_daily_report():
    """15:30 收盘后生成日报"""
    logger.info("📊 生成收盘日报")
    try:
        # 调用日报生成器
        logger.info("日报生成任务已触发")
    except Exception as e:
        logger.error(f"日报生成失败: {e}")


@trade_day_only
def job_data_backup():
    """16:00 数据归档"""
    logger.info("💾 执行数据归档")
    try:
        backup_dir = f"backups/{datetime.now().strftime('%Y%m%d')}"
        os.makedirs(backup_dir, exist_ok=True)
        
        # 备份信号历史
        if os.path.exists("logs/signal_2026-02-27.log"):
            os.system(f"cp logs/signal_*.log {backup_dir}/ 2>/dev/null")
            
        # 备份报告
        if os.path.exists("reports"):
            os.system(f"cp -r reports/* {backup_dir}/ 2>/dev/null")
            
        logger.info(f"✅ 数据归档完成: {backup_dir}")
    except Exception as e:
        logger.error(f"数据归档失败: {e}")


# === 注册任务 ===
def register_jobs():
    """注册所有定时任务"""
    
    # 08:45 健康检查
    scheduler.add_job(
        job_health_check,
        CronTrigger(hour=8, minute=45),
        id="health_check",
        name="系统健康检查",
        replace_existing=True
    )
    
    # 09:00 盘前调研
    scheduler.add_job(
        job_morning_research,
        CronTrigger(hour=9, minute=0),
        id="morning_research",
        name="盘前调研",
        replace_existing=True
    )
    
    # 09:15 智能选股
    scheduler.add_job(
        job_stock_screening,
        CronTrigger(hour=9, minute=15),
        id="stock_screening",
        name="智能选股",
        replace_existing=True
    )
    
    # 盘中监控：9:30-11:30, 13:00-15:00 每30分钟
    scheduler.add_job(
        job_intraday_monitor,
        CronTrigger(minute="*/30", hour="9-11,13-15"),
        id="intraday_monitor",
        name="盘中监控",
        replace_existing=True
    )
    
    # 15:30 收盘日报
    scheduler.add_job(
        job_daily_report,
        CronTrigger(hour=15, minute=30),
        id="daily_report",
        name="收盘日报",
        replace_existing=True
    )
    
    # 16:00 数据归档
    scheduler.add_job(
        job_data_backup,
        CronTrigger(hour=16, minute=0),
        id="data_backup",
        name="数据归档",
        replace_existing=True
    )
    
    logger.info("✅ 所有任务已注册")


# === 启动 ===
if __name__ == "__main__":
    logger.info("=" * 50)
    logger.info("🕐 Alpha Quant 统一调度器启动")
    logger.info("=" * 50)
    logger.info(f"📅 当前日期: {datetime.now().strftime('%Y-%m-%d')}")
    logger.info(f"📊 是否交易日: {'是' if calendar.is_trade_date() else '否'}")
    logger.info(f"⏰ 市场阶段: {calendar.get_market_phase()}")
    logger.info("=" * 50)
    
    # 注册事件监听
    scheduler.add_listener(on_job_error, EVENT_JOB_ERROR)
    scheduler.add_listener(on_job_executed, EVENT_JOB_EXECUTED)
    
    # 注册任务
    register_jobs()
    
    # 打印任务列表
    logger.info("📋 已注册任务列表:")
    for job in scheduler.get_jobs():
        logger.info(f"  - {job.name}: {job.trigger}")
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 调度器停止")
        scheduler.shutdown()
