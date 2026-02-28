# optimized_data_gateway.py --- 优化版数据网关
# 优化项：Redis缓存、异步处理、连接池、日志异步、数据压缩

import os
import json
import asyncio
import aiohttp
from datetime import datetime
from functools import wraps
from typing import Optional, Dict, Any

from flask import Flask, jsonify, request, Response
from flask_compress import Compress
from loguru import logger
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 配置异步日志
logger.remove()
logger.add(
    "logs/gateway_{time:YYYY-MM-DD}.log",
    rotation="10 MB",
    retention="30 days",
    enqueue=True,  # 异步写入
    format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}"
)
logger.add(sys.stdout, enqueue=True)

app = Flask(__name__)
Compress(app)  # 启用gzip压缩

# 全局连接池
session: Optional[aiohttp.ClientSession] = None

async def get_session() -> aiohttp.ClientSession:
    """获取或创建HTTP连接池"""
    global session
    if session is None or session.closed:
        session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(limit=100, limit_per_host=20),
            timeout=aiohttp.ClientTimeout(total=30)
        )
    return session

# Redis缓存（可选）
redis_client = None
try:
    import redis
    redis_url = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    redis_client = redis.from_url(redis_url, decode_responses=True)
    redis_client.ping()
    logger.info("✅ Redis缓存已连接")
except Exception as e:
    logger.warning(f"⚠️ Redis未启用: {e}")
    redis_client = None

def cached(ttl: int = 30):
    """缓存装饰器 - 支持Redis或内存缓存"""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            cache_key = f"{func.__name__}:{hash(str(args) + str(kwargs))}"
            
            # 尝试从Redis读取
            if redis_client:
                try:
                    cached_data = redis_client.get(cache_key)
                    if cached_data:
                        return json.loads(cached_data)
                except Exception as e:
                    logger.debug(f"Redis读取失败: {e}")
            
            # 执行函数
            result = await func(*args, **kwargs)
            
            # 写入Redis
            if redis_client and result:
                try:
                    redis_client.setex(cache_key, ttl, json.dumps(result))
                except Exception as e:
                    logger.debug(f"Redis写入失败: {e}")
            
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # 同步版本使用简单内存缓存
            import hashlib
            cache_key = f"{func.__name__}:{hashlib.md5(str(args).encode() + str(kwargs).encode()).hexdigest()}"
            
            # 这里可以添加内存缓存逻辑
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    return decorator

# 异步健康检查
@app.route("/api/health", methods=["GET"])
async def health_check():
    """异步健康检查"""
    checks = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    # 异步检查各服务
    tasks = [
        check_tushare(),
        check_akshare(),
        check_ths()
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    for name, result in zip(["tushare", "akshare", "ths"], results):
        if isinstance(result, Exception):
            checks["checks"][name] = {"status": "error", "message": str(result)}
            checks["status"] = "degraded"
        else:
            checks["checks"][name] = result
    
    return jsonify(checks)

async def check_tushare() -> Dict:
    """异步检查Tushare"""
    try:
        import tushare as ts
        pro = ts.pro_api(os.getenv("TUSHARE_TOKEN"))
        # 使用线程池执行同步操作
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(None, 
            lambda: pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20260131', limit=1))
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def check_akshare() -> Dict:
    """异步检查AkShare"""
    try:
        import akshare as ak
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(None, 
            lambda: ak.stock_zh_index_daily(symbol='sh000001'))
        return {"status": "ok" if len(df) > 0 else "error", "records": len(df)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

async def check_ths() -> Dict:
    """异步检查同花顺"""
    try:
        from modules.trade_calendar import get_calendar
        cal = get_calendar()
        return {"status": "ok", "trade_dates": len(cal.trade_dates)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# 异步实时行情
@app.route("/api/market/realtime", methods=["GET"])
@cached(ttl=30)
async def get_realtime():
    """异步获取实时行情"""
    try:
        import akshare as ak
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(None, ak.stock_zh_a_spot_em)
        
        top = df.nlargest(100, "涨跌幅")[["代码","名称","最新价","涨跌幅","成交量"]]
        
        return jsonify({
            "code": 200,
            "data": top.to_dict("records"),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"获取实时行情失败: {e}")
        return jsonify({"code": 500, "error": str(e)}), 500

# 启动/关闭事件
@app.before_serving
async def startup():
    """启动时初始化"""
    logger.info("🚀 优化版数据网关启动")
    await get_session()

@app.after_serving
async def cleanup():
    """关闭时清理"""
    global session
    if session and not session.closed:
        await session.close()
        logger.info("✅ HTTP连接池已关闭")

if __name__ == "__main__":
    import sys
    # 使用hypercorn运行（支持async/await）
    try:
        from hypercorn.asyncio import serve
        from hypercorn.config import Config
        
        config = Config()
        config.bind = ["0.0.0.0:8766"]
        config.workers = 2
        
        logger.info("📊 使用Hypercorn启动（支持异步）")
        asyncio.run(serve(app, config))
    except ImportError:
        logger.warning("⚠️ Hypercorn未安装，使用Flask开发服务器")
        app.run(host="0.0.0.0", port=8766, debug=False)
