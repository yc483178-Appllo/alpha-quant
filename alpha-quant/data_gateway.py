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

# === 交易日历初始化 ===
from modules.trade_calendar import TradeCalendar
_trade_calendar = None

def get_trade_calendar():
    """获取交易日历实例（懒加载）"""
    global _trade_calendar
    if _trade_calendar is None:
        _trade_calendar = TradeCalendar()
    return _trade_calendar

# === 同花顺SDK初始化 ===
_ths_logged_in = False
_ths_login_time = None

def ths_init():
    """初始化同花顺SDK连接"""
    global _ths_logged_in, _ths_login_time
    try:
        import iFinDPy
        if not _ths_logged_in:
            result = iFinDPy.THS_iFinDLogin(
                os.getenv("THS_ACCOUNT", "grsyzh1006"),
                os.getenv("THS_PASSWORD", "NANbF9Sk")
            )
            if result == 0:
                _ths_logged_in = True
                _ths_login_time = datetime.now()
                logger.info("✅ 同花顺SDK登录成功")
                return True
            else:
                logger.error(f"❌ 同花顺SDK登录失败，错误码: {result}")
                return False
        # 检查登录是否超过6小时，如果是则重新登录
        elif _ths_login_time and (datetime.now() - _ths_login_time).total_seconds() > 21600:
            iFinDPy.THS_iFinDLogout()
            return ths_init()
        return True
    except Exception as e:
        logger.error(f"❌ 同花顺SDK初始化失败: {e}")
        return False

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

# === 多数据源获取函数 ===
def get_realtime_data_with_fallback():
    """获取实时行情，支持多数据源自动切换"""
    errors = []
    
    # 1. 尝试AkShare主接口
    try:
        df = ak.stock_zh_a_spot_em()
        logger.info("✅ AkShare主接口获取实时行情成功")
        return df, "akshare"
    except Exception as e:
        errors.append(f"AkShare主接口: {e}")
        logger.warning(f"⚠️ AkShare主接口失败: {e}")
    
    # 2. 尝试同花顺SDK
    try:
        if ths_init():
            import iFinDPy
            # 获取沪深A股所有股票代码（前100只）
            codes = "000001.SZ,000002.SZ,000063.SZ,000100.SZ,000333.SZ,000538.SZ,000568.SZ,000651.SZ,000725.SZ,000768.SZ,000858.SZ,000895.SZ,002001.SZ,002007.SZ,002024.SZ,002027.SZ,002142.SZ,002230.SZ,002236.SZ,002271.SZ,002304.SZ,002352.SZ,002415.SZ,002460.SZ,002475.SZ,002594.SZ,002714.SZ,002812.SZ,300003.SZ,300014.SZ,300015.SZ,300033.SZ,300059.SZ,300122.SZ,300124.SZ,300142.SZ,300274.SZ,300408.SZ,300413.SZ,300433.SZ,300498.SZ,300750.SZ,300760.SZ,300832.SZ,300896.SZ,600000.SH,600009.SH,600016.SH,600028.SH,600030.SH,600031.SH,600036.SH,600048.SH,600050.SH,600104.SH,600276.SH,600309.SH,600346.SH,600406.SH,600436.SH,600438.SH,600519.SH,600547.SH,600570.SH,600585.SH,600588.SH,600600.SH,600690.SH,600703.SH,600745.SH,600809.SH,600837.SH,600887.SH,600893.SH,600900.SH,600919.SH,601012.SH,601066.SH,601088.SH,601111.SH,601138.SH,601166.SH,601211.SH,601225.SH,601288.SH,601318.SH,601319.SH,601328.SH,601390.SH,601398.SH,601601.SH,601628.SH,601668.SH,601688.SH,601728.SH,601766.SH,601857.SH,601888.SH,601899.SH,601901.SH,601933.SH,601988.SH,601989.SH,603259.SH,603288.SH,603501.SH,603986.SH,603993.SH,688008.SH,688009.SH,688012.SH,688036.SH,688111.SH,688126.SH,688169.SH,688185.SH,688256.SH,688981.SH"
            result = iFinDPy.THS_RealtimeQuotes(codes, 'close,open,high,low,volume,changeRatio')
            
            if result.get('errorcode') == 0:
                # 转换为DataFrame格式
                import pandas as pd
                data_list = []
                for item in result.get('tables', []):
                    code = item.get('thscode', '')
                    table = item.get('table', {})
                    data_list.append({
                        '代码': code.replace('.SZ', '').replace('.SH', ''),
                        '最新价': table.get('close', [None])[0],
                        '涨跌幅': table.get('changeRatio', [None])[0],
                        '成交量': table.get('volume', [None])[0],
                        'open': table.get('open', [None])[0],
                        'high': table.get('high', [None])[0],
                        'low': table.get('low', [None])[0]
                    })
                df = pd.DataFrame(data_list)
                logger.info(f"✅ 同花顺SDK获取实时行情成功，共 {len(df)} 条")
                return df, "ths"
    except Exception as e:
        errors.append(f"同花顺SDK: {e}")
        logger.warning(f"⚠️ 同花顺SDK失败: {e}")
    
    # 3. 尝试AkShare备用接口
    try:
        df = ak.stock_zh_index_daily(symbol='sh000001')
        logger.info("✅ AkShare备用接口获取指数数据成功")
        return df, "akshare_backup"
    except Exception as e:
        errors.append(f"AkShare备用接口: {e}")
    
    raise Exception(f"所有数据源均失败: {'; '.join(errors)}")

# === 交易日历判断 ===
_trade_dates = set()
def load_trade_calendar():
    """加载A股交易日历"""
    global _trade_dates
    try:
        # 优先使用Tushare
        df = pro.trade_cal(exchange='SSE', start_date='20250101', end_date='20261231')
        df = df[df['is_open'] == 1]
        _trade_dates = set(df['cal_date'].astype(str).tolist())
        logger.info(f"✅ 交易日历加载完成(Tushare)，共 {len(_trade_dates)} 个交易日")
    except Exception as e:
        logger.warning(f"⚠️ Tushare交易日历失败: {e}，尝试AkShare")
        try:
            df = ak.tool_trade_date_hist_sina()
            _trade_dates = set(df["trade_date"].astype(str).tolist())
            logger.info(f"✅ 交易日历加载完成(AkShare)，共 {len(_trade_dates)} 个交易日")
        except Exception as e2:
            logger.error(f"❌ 交易日历加载失败: {e2}")

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
    
    # 检查同花顺SDK
    try:
        if ths_init():
            checks["checks"]["ths"] = {"status": "ok"}
        else:
            checks["checks"]["ths"] = {"status": "error", "message": "登录失败"}
            checks["status"] = "degraded"
    except Exception as e:
        checks["checks"]["ths"] = {"status": "error", "message": str(e)}
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
    """获取A股实时行情 TOP100，支持多数据源自动切换"""
    try:
        df, source = get_realtime_data_with_fallback()
        
        if source == "akshare":
            top = df.nlargest(100, "涨跌幅")[["代码","名称","最新价","涨跌幅","成交量","换手率","量比","总市值"]]
        elif source == "ths":
            # 同花顺数据格式转换
            df = df.sort_values('涨跌幅', ascending=False).head(100)
            top = df.rename(columns={'最新价': '最新价', '涨跌幅': '涨跌幅', '成交量': '成交量'})
            top['名称'] = top['代码']  # 同花顺返回中没有名称，用代码代替
            top['换手率'] = None
            top['量比'] = None
            top['总市值'] = None
        else:
            top = df
        
        logger.info(f"✅ 实时行情获取成功(来源:{source})，返回 {len(top)} 条")
        return jsonify({
            "code": 200, 
            "data": top.to_dict("records"), 
            "source": source,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"❌ 实时行情获取失败: {e}")
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

@app.route("/api/ths/quotes", methods=["GET"])
@rate_limit(max_calls=50, period=60)
def get_ths_quotes():
    """同花顺实时行情接口"""
    codes = request.args.get("codes", "")
    indicators = request.args.get("indicators", "close,open,high,low,volume")
    
    if not codes:
        return jsonify({"code": 400, "error": "缺少股票代码参数(codes)"}), 400
    
    try:
        if not ths_init():
            return jsonify({"code": 503, "error": "同花顺SDK未登录"}), 503
        
        import iFinDPy
        result = iFinDPy.THS_RealtimeQuotes(codes, indicators)
        
        if result.get('errorcode') == 0:
            return jsonify({
                "code": 200,
                "data": result.get('tables', []),
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "code": 500,
                "error": result.get('errmsg', '未知错误')
            }), 500
    except Exception as e:
        logger.error(f"❌ 同花顺行情获取失败: {e}")
        return jsonify({"code": 500, "error": str(e)}), 500

@app.route("/api/ths/history", methods=["GET"])
@rate_limit(max_calls=30, period=60)
@cached(ttl=300)
def get_ths_history():
    """同花顺历史数据接口"""
    code = request.args.get("code", "")
    indicators = request.args.get("indicators", "close,open,high,low,volume")
    start_date = request.args.get("start", "")
    end_date = request.args.get("end", "")
    
    if not code:
        return jsonify({"code": 400, "error": "缺少股票代码参数(code)"}), 400
    
    try:
        if not ths_init():
            return jsonify({"code": 503, "error": "同花顺SDK未登录"}), 503
        
        import iFinDPy
        result = iFinDPy.THS_HistoryQuotes(code, indicators, 'period=D', start_date, end_date)
        
        if result.get('errorcode') == 0:
            return jsonify({
                "code": 200,
                "data": result.get('tables', []),
                "timestamp": datetime.now().isoformat()
            })
        else:
            return jsonify({
                "code": 500,
                "error": result.get('errmsg', '未知错误')
            }), 500
    except Exception as e:
        logger.error(f"❌ 同花顺历史数据获取失败: {e}")
        return jsonify({"code": 500, "error": str(e)}), 500

@app.route("/api/calendar/is_trade_date", methods=["GET"])
def check_trade_date():
    """检查是否为交易日"""
    cal = get_trade_calendar()
    date = request.args.get("date", datetime.now().strftime("%Y-%m-%d"))
    return jsonify({
        "code": 200, 
        "date": date, 
        "is_trade_date": cal.is_trade_date(date),
        "market_phase": cal.get_market_phase() if date == datetime.now().strftime("%Y-%m-%d") else None
    })

@app.route("/api/calendar/next_trade_date", methods=["GET"])
def get_next_trade_date():
    """获取下一个交易日"""
    cal = get_trade_calendar()
    n = request.args.get("n", 1, type=int)
    next_date = cal.next_trade_date(n=n)
    return jsonify({
        "code": 200,
        "next_trade_date": next_date,
        "n": n
    })

@app.route("/api/calendar/trade_dates", methods=["GET"])
def get_trade_dates():
    """获取最近N个交易日"""
    cal = get_trade_calendar()
    days = request.args.get("days", 20, type=int)
    dates = cal.get_trade_dates(days)
    return jsonify({
        "code": 200,
        "days": days,
        "trade_dates": dates
    })

@app.route("/api/calendar/market_status", methods=["GET"])
def get_market_status():
    """获取市场状态"""
    cal = get_trade_calendar()
    return jsonify({
        "code": 200,
        "is_trade_date": cal.is_trade_date(),
        "is_trade_time": cal.is_trade_time(),
        "market_phase": cal.get_market_phase(),
        "timestamp": datetime.now().isoformat()
    })

# === 启动 ===
if __name__ == "__main__":
    logger.info("📊 数据网关服务启动，端口 8766")
    app.run(host="0.0.0.0", port=8766, debug=False)
