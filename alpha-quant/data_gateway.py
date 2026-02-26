# data_gateway.py --- 增强版数据网关（部署在本机或云服务器）
# 新增功能：请求缓存、异常重试、限流、健康检查、统一日志、CORS支持

import os
import json
import time
import hashlib
import functools
from datetime import datetime, timedelta

from flask import Flask, jsonify, request
from flask_cors import CORS
import akshare as ak
import tushare as ts
from loguru import logger
from retry import retry
from dotenv import load_dotenv

# === 初始化 ===
load_dotenv()
app = Flask(__name__)
CORS(app)

pro = ts.pro_api(os.getenv("TUSHARE_TOKEN", ""))

# === 日志配置 ===
logger.add("logs/gateway_{time:YYYY-MM-DD}.log", rotation="10 MB", retention="30 days",
           format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

# === 简易内存缓存（无Redis时使用） ===
_cache = {}
def cached(ttl=300):
    """缓存装饰器，ttl为缓存有效期（秒）"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = f"{func.__name__}:{hashlib.md5(str(args).encode()+str(kwargs).encode()).hexdigest()}"
            now = time.time()
            if key in _cache and now - _cache[key]["time"] < ttl:
                logger.debug(f"缓存命中: {func.__name__}")
                return _cache[key]["data"]
            result = func(*args, **kwargs)
            _cache[key] = {"data": result, "time": now}
            return result
        return wrapper
    return decorator

# === 限流器 ===
_rate_limit = {}
def rate_limit(max_calls=30, period=60):
    """简易限流：period秒内最多max_calls次"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            now = time.time()
            key = func.__name__
            if key not in _rate_limit:
                _rate_limit[key] = []
            _rate_limit[key] = [t for t in _rate_limit[key] if now - t < period]
            if len(_rate_limit[key]) >= max_calls:
                return jsonify({"error": "请求过于频繁，请稍后再试", "code": 429}), 429
            _rate_limit[key].append(now)
            return func(*args, **kwargs)
        return wrapper
    return decorator

# === 交易日历判断 ===
_trade_dates = set()
def load_trade_calendar():
    """加载A股交易日历"""
    global _trade_dates
    try:
        df = ak.tool_trade_date_hist_sina()
        _trade_dates = set(df["trade_date"].astype(str).tolist())
        logger.info(f"交易日历加载完成，共 {len(_trade_dates)} 个交易日")
    except Exception as e:
        logger.error(f"交易日历加载失败: {e}")

def is_trade_date(date_str=None):
    """判断指定日期（YYYY-MM-DD）是否为交易日"""
    if not _trade_dates:
        load_trade_calendar()
    if date_str is None:
        date_str = datetime.now().strftime("%Y-%m-%d")
    return date_str in _trade_dates

# === 健康检查端点 ===
@app.route("/api/health", methods=["GET"])
def health_check():
    """系统健康检查"""
    checks = {"status": "ok", "timestamp": datetime.now().isoformat(), "checks": {}}

    # 检查AkShare
    try:
        df = ak.stock_zh_a_spot_em()
        checks["checks"]["akshare"] = {"status": "ok", "records": len(df)}
    except Exception as e:
        checks["checks"]["akshare"] = {"status": "error", "message": str(e)}
        checks["status"] = "degraded"

    # 检查Tushare
    try:
        df = pro.trade_cal(exchange="SSE", start_date="20260101", end_date="20260131")
        checks["checks"]["tushare"] = {"status": "ok"}
    except Exception as e:
        checks["checks"]["tushare"] = {"status": "error", "message": str(e)}
        checks["status"] = "degraded"

    # 检查交易日
    checks["checks"]["is_trade_date"] = is_trade_date()
    checks["checks"]["cache_entries"] = len(_cache)

    return jsonify(checks)

# === 数据接口 ===
@app.route("/api/market/realtime", methods=["GET"])
@rate_limit(max_calls=30, period=60)
@cached(ttl=30)
def get_realtime():
    """获取A股实时行情 TOP100"""
    try:
        df = ak.stock_zh_a_spot_em()
        top = df.nlargest(100, "涨跌幅")[["代码","名称","最新价","涨跌幅","成交量","换手率","量比","总市值"]]
        logger.info(f"实时行情获取成功，返回 {len(top)} 条")
        return jsonify({"code": 200, "data": top.to_dict("records"), "timestamp": datetime.now().isoformat()})
    except Exception as e:
        logger.error(f"实时行情获取失败: {e}")
        return jsonify({"code": 500, "error": str(e)}), 500

@app.route("/api/sector/flow", methods=["GET"])
@rate_limit(max_calls=20, period=60)
@cached(ttl=60)
def get_sector_flow():
    """获取板块资金流向"""
    try:
        df = ak.stock_sector_fund_flow_rank(indicator="今日")
        logger.info("板块资金流向获取成功")
        return jsonify({"code": 200, "data": df.head(20).to_dict("records")})
    except Exception as e:
        logger.error(f"板块资金流向获取失败: {e}")
        return jsonify({"code": 500, "error": str(e)}), 500

@app.route("/api/north/flow", methods=["GET"])
@rate_limit(max_calls=20, period=60)
@cached(ttl=60)
def get_north_flow():
    """获取北向资金流入"""
    try:
        df = ak.stock_hsgt_north_net_flow_in_em(symbol="沪深港通")
        latest = float(df.iloc[-1]["值"])
        logger.info(f"北向资金: {latest}亿元")
        return jsonify({"code": 200, "data": {"north_flow": latest, "unit": "亿元"},
                        "timestamp": datetime.now().isoformat()})
    except Exception as e:
        logger.error(f"北向资金获取失败: {e}")
        return jsonify({"code": 500, "error": str(e)}), 500

@app.route("/api/limitup/pool", methods=["GET"])
@rate_limit(max_calls=10, period=60)
@cached(ttl=120)
def get_limitup():
    """获取涨停板池"""
    try:
        df = ak.stock_zt_pool_em(date="")
        return jsonify({"code": 200, "data": df.to_dict("records")})
    except Exception as e:
        logger.error(f"涨停板池获取失败: {e}")
        return jsonify({"code": 500, "error": str(e)}), 500

@app.route("/api/stock/detail", methods=["GET"])
@rate_limit(max_calls=30, period=60)
@cached(ttl=60)
def get_stock_detail():
    """获取个股详细信息"""
    code = request.args.get("code", "")
    if not code:
        return jsonify({"code": 400, "error": "缺少股票代码参数"}), 400
    try:
        df = ak.stock_zh_a_spot_em()
        stock = df[df["代码"] == code]
        if stock.empty:
            return jsonify({"code": 404, "error": f"未找到股票 {code}"}), 404
        return jsonify({"code": 200, "data": stock.iloc[0].to_dict()})
    except Exception as e:
        return jsonify({"code": 500, "error": str(e)}), 500

@app.route("/api/calendar/is_trade_date", methods=["GET"])
def check_trade_date():
    """检查是否为交易日"""
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    return jsonify({"code": 200, "date": date, "is_trade_date": is_trade_date(date)})

# === 启动 ===
if __name__ == "__main__":
    load_trade_calendar()
    logger.info("📊 数据网关服务启动，端口 8765")
    app.run(host="0.0.0.0", port=8765, debug=False)
