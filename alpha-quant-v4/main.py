#!/usr/bin/env python3
"""
Alpha Quant v4.0 - Multi-Agent System
主入口程序

启动命令: python main.py [--mode dev|prod]
"""

import os
import sys
import argparse
from pathlib import Path
from dotenv import load_dotenv
from loguru import logger

# 加载环境变量
load_dotenv()

# 配置日志
logger.remove()
logger.add(
    "logs/alpha_v4_{time:YYYY-MM-DD}.log",
    rotation="10 MB",
    retention="30 days",
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} | {message}"
)
logger.add(sys.stdout, level="INFO")

def check_dependencies():
    """检查依赖"""
    required = ["akshare", "redis", "apscheduler", "sklearn", "pandas", "numpy", "re"]
    missing = []
    
    for pkg in required:
        try:
            if pkg == "re":
                import re
            elif pkg == "sklearn":
                import sklearn
            else:
                __import__(pkg)
        except ImportError:
            missing.append(pkg)
    
    if missing:
        logger.error(f"缺少依赖: {', '.join(missing)}")
        logger.info("请执行: pip install " + " ".join(missing))
        return False
    
    return True

def check_redis():
    """检查Redis连接"""
    try:
        import redis
        r = redis.from_url(os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
        r.ping()
        logger.info("✅ Redis连接正常")
        return True
    except Exception as e:
        logger.error(f"❌ Redis连接失败: {e}")
        return False

def print_banner():
    """打印启动横幅"""
    banner = """
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║     █████╗ ██╗     ██████╗ ██╗  ██╗ █████╗                  ║
    ║    ██╔══██╗██║     ██╔══██╗██║  ██║██╔══██╗                 ║
    ║    ███████║██║     ██████╔╝███████║███████║                 ║
    ║    ██╔══██║██║     ██╔═══╝ ██╔══██║██╔══██║                 ║
    ║    ██║  ██║███████╗██║     ██║  ██║██║  ██║                 ║
    ║    ╚═╝  ╚═╝╚══════╝╚═╝     ╚═╝  ╚═╝╚═╝  ╚═╝                 ║
    ║                                                               ║
    ║              Multi-Agent Quantitative System v4.0            ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝
    
    🤖 Agent团队:
       👑 Chief    - 首席策略官 (总协调)
       📡 Scout    - 市场情报员 (盘前侦察)
       🎯 Picker   - 量化选股师 (策略选股)
       🛡️  Guard    - 风控总监 (风险管控)
       💼 Trader   - 交易执行员 (精准执行)
       📊 Review   - 复盘分析师 (每日复盘)
    
    """
    print(banner)

def main():
    parser = argparse.ArgumentParser(description="Alpha Quant v4.0")
    parser.add_argument("--mode", choices=["dev", "prod"], default="dev", help="运行模式")
    parser.add_argument("--agent", choices=["chief", "scout", "picker", "guard", "trader", "review", "scheduler"], 
                        help="单独启动某个Agent")
    args = parser.parse_args()
    
    print_banner()
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查Redis
    if not check_redis():
        logger.warning("Redis未连接，部分功能可能受限")
    
    logger.info(f"🚀 Alpha Quant v4.0 启动 | 模式: {args.mode}")
    
    if args.agent:
        # 单独启动某个Agent
        logger.info(f"单独启动Agent: {args.agent}")
        
        if args.agent == "scheduler":
            from core.agent_scheduler import scheduler
            try:
                scheduler.start()
            except KeyboardInterrupt:
                logger.info("调度器已停止")
        elif args.agent == "chief":
            from agents.alpha_chief import AlphaChief
            agent = AlphaChief()
            agent.startup_check()
        elif args.agent == "scout":
            from agents.alpha_scout import AlphaScout
            agent = AlphaScout()
            agent.morning_research()
        elif args.agent == "picker":
            from agents.alpha_picker import AlphaPicker
            agent = AlphaPicker()
            agent.screen_stocks()
        elif args.agent == "guard":
            from agents.alpha_guard import AlphaGuard
            agent = AlphaGuard()
            agent.pre_market_check()
        elif args.agent == "trader":
            from agents.alpha_trader import AlphaTrader
            agent = AlphaTrader()
            logger.info("Trader已启动，等待交易指令")
            
            # 交互模式：测试自然语言下单
            logger.info("📝 自然语言下单测试模式")
            logger.info("示例指令：")
            logger.info('  - "买入5万块招商银行"')
            logger.info('  - "600036买入1000股，限价35元"')
            logger.info('  - "卖掉一半平安银行"')
            
            # 测试解析
            test_orders = [
                "买入5万块招商银行",
                "600036买入1000股，限价35元",
                "卖掉一半平安银行"
            ]
            for order_text in test_orders:
                result = agent.parse_natural_language(order_text)
                if result.get("parsed"):
                    logger.info(f"✅ 解析成功: {order_text}")
                    logger.info(f"   结果: {result['order']['action']} {result['order']['name']}({result['order']['code']})")
                else:
                    logger.warning(f"❌ 解析失败: {order_text} - {result.get('error', '未知错误')}")
        elif args.agent == "review":
            from agents.alpha_review import AlphaReview
            agent = AlphaReview()
            agent.daily_review([], {})
    else:
        # 启动完整系统
        logger.info("启动完整Multi-Agent系统")
        logger.info("建议使用: python main.py --agent scheduler 启动调度器")
        
        # 测试模式：运行一次完整流程
        logger.info("🧪 测试模式：执行一次完整流程")
        
        from agents.alpha_chief import AlphaChief
        from agents.alpha_scout import AlphaScout
        from agents.alpha_picker import AlphaPicker
        from agents.alpha_guard import AlphaGuard
        
        chief = AlphaChief()
        scout = AlphaScout()
        picker = AlphaPicker()
        guard = AlphaGuard()
        
        # 1. Chief启动
        chief.startup_check()
        
        # 2. Scout盘前调研
        scout.morning_research()
        
        # 3. Guard风控预检
        guard.pre_market_check()
        
        # 4. Picker选股
        signals = picker.screen_stocks()
        
        logger.info(f"✅ 测试完成，生成 {len(signals)} 个交易信号")

if __name__ == "__main__":
    main()
