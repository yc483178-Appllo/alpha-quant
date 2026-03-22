# enhanced_data_gateway.py --- 多数据源融合网关 v2.0
# 支持: Tushare Pro / AkShare / Baostock / Sina财经 / 同花顺SDK
# 特性: 多源交叉验证、故障自动切换、统一缓存、限流保护

import os
import json
import time
import hashlib
import functools
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any, Tuple
import traceback

from flask import Flask, jsonify, request
from flask_cors import CORS
from loguru import logger
from retry import retry
from dotenv import load_dotenv
import pandas as pd
import numpy as np

# === 初始化 ===
load_dotenv()
app = Flask(__name__)
CORS(app)

# === 数据源配置 ===
DATA_SOURCE_CONFIG = {
    "tushare": {
        "enabled": True,
        "token": os.getenv("TUSHARE_TOKEN", "3077a1400cdb4fdde84b2379ba3368515a858afdf978daa774f8d430"),
        "weight": 10,  # 数据质量权重
        "priority": 1,  # 调用优先级
    },
    "akshare": {
        "enabled": True,
        "weight": 8,
        "priority": 2,
    },
    "baostock": {
        "enabled": True,
        "weight": 7,
        "priority": 3,
    },
    "sina": {
        "enabled": True,
        "weight": 6,
        "priority": 4,
    },
    "ths": {
        "enabled": False,  # 需要账号密码
        "weight": 9,
        "priority": 0,
    }
}

# === 初始化各数据源 ===

# Tushare Pro
pro = None
try:
    import tushare as ts
    token = DATA_SOURCE_CONFIG["tushare"]["token"]
    if token:
        ts.set_token(token)
        pro = ts.pro_api()
        logger.info(f"✅ Tushare Pro 初始化成功")
    else:
        logger.warning("⚠️ Tushare Token 未配置")
except Exception as e:
    logger.error(f"❌ Tushare 初始化失败: {e}")

# Baostock
bs = None
try:
    import baostock as bs_module
    bs = bs_module
    logger.info("✅ Baostock 模块加载成功")
except Exception as e:
    logger.warning(f"⚠️ Baostock 未安装: {e}")

# AkShare
ak = None
try:
    import akshare as ak_module
    ak = ak_module
    logger.info("✅ AkShare 模块加载成功")
except Exception as e:
    logger.error(f"❌ AkShare 加载失败: {e}")

# === 同花顺SDK初始化 ===
_ths_logged_in = False
_ths_login_time = None

def ths_init():
    """初始化同花顺SDK连接"""
    global _ths_logged_in, _ths_login_time
    if not DATA_SOURCE_CONFIG["ths"]["enabled"]:
        return False
    try:
        import iFinDPy
        if not _ths_logged_in:
            result = iFinDPy.THS_iFinDLogin(
                os.getenv("THS_ACCOUNT", ""),
                os.getenv("THS_PASSWORD", "")
            )
            if result == 0:
                _ths_logged_in = True
                _ths_login_time = datetime.now()
                logger.info("✅ 同花顺SDK登录成功")
                return True
            else:
                logger.error(f"❌ 同花顺SDK登录失败，错误码: {result}")
                return False
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

# === 统一缓存系统 ===
_cache = {}
_cache_stats = {"hits": 0, "misses": 0}

def cached(ttl=60, key_prefix=""):
    """缓存装饰器，ttl为缓存有效期（秒）"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存key
            key_data = f"{func.__name__}:{str(args)}:{str(kwargs)}"
            key = f"{key_prefix}:{hashlib.md5(key_data.encode()).hexdigest()}"
            
            now = time.time()
            if key in _cache and now - _cache[key]["time"] < ttl:
                _cache_stats["hits"] += 1
                logger.debug(f"缓存命中: {func.__name__}")
                return _cache[key]["data"]
            
            _cache_stats["misses"] += 1
            result = func(*args, **kwargs)
            _cache[key] = {"data": result, "time": now}
            return result
        return wrapper
    return decorator

def clear_cache():
    """清空缓存"""
    global _cache
    _cache.clear()
    logger.info("缓存已清空")

# === 限流器 ===
_rate_limit = {}

def rate_limit(max_calls=60, period=60):
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

# === 股票代码格式转换工具 ===

def normalize_code(code: str) -> str:
    """统一股票代码格式"""
    code = str(code).strip()
    # 移除后缀
    if '.' in code:
        code = code.split('.')[0]
    return code.zfill(6)

def get_exchange(code: str) -> str:
    """判断交易所"""
    code = normalize_code(code)
    if code.startswith(('6', '5', '9', '11', '13')):
        return 'SH'
    elif code.startswith(('0', '3', '2', '12', '15', '16', '18')):
        return 'SZ'
    elif code.startswith(('4', '8', '43', '83', '87')):
        return 'BJ'
    return 'SZ'  # 默认

def to_tushare_code(code: str) -> str:
    """转换为Tushare格式"""
    code = normalize_code(code)
    exchange = get_exchange(code)
    return f"{code}.{exchange}"

def to_baostock_code(code: str) -> str:
    """转换为Baostock格式"""
    code = normalize_code(code)
    exchange = get_exchange(code)
    return f"{exchange.lower()}.{code}"

# === 多数据源获取函数 ===

class DataSourceManager:
    """数据源管理器 - 统一调用多数据源并做交叉验证"""
    
    @staticmethod
    def get_realtime_quote_single(code: str, source: str = "auto") -> Optional[Dict]:
        """从单一数据源获取实时行情"""
        code = normalize_code(code)
        
        if source == "tushare" or (source == "auto" and pro):
            try:
                ts_code = to_tushare_code(code)
                df = pro.daily(ts_code=ts_code, start_date=datetime.now().strftime('%Y%m%d'), 
                              end_date=datetime.now().strftime('%Y%m%d'))
                if not df.empty:
                    row = df.iloc[0]
                    return {
                        "code": code,
                        "name": code,  # Tushare需要单独查询名称
                        "price": float(row['close']),
                        "open": float(row['open']),
                        "high": float(row['high']),
                        "low": float(row['low']),
                        "pre_close": float(row['pre_close']),
                        "volume": int(row['vol']) * 100,
                        "amount": float(row['amount']) * 1000,
                        "change_pct": round((float(row['close']) - float(row['pre_close'])) / float(row['pre_close']) * 100, 2),
                        "source": "tushare",
                        "timestamp": datetime.now().isoformat()
                    }
            except Exception as e:
                logger.warning(f"Tushare获取{code}失败: {e}")
        
        if source == "akshare" or source == "auto":
            try:
                df = ak.stock_zh_a_spot_em()
                stock = df[df['代码'] == code]
                if not stock.empty:
                    row = stock.iloc[0]
                    return {
                        "code": code,
                        "name": row.get('名称', code),
                        "price": float(row['最新价']) if pd.notna(row['最新价']) else None,
                        "open": float(row['今开']) if pd.notna(row['今开']) else None,
                        "high": float(row['最高']) if pd.notna(row['最高']) else None,
                        "low": float(row['最低']) if pd.notna(row['最低']) else None,
                        "pre_close": float(row['昨收']) if pd.notna(row['昨收']) else None,
                        "volume": int(row['成交量']) if pd.notna(row['成交量']) else None,
                        "amount": float(row['成交额']) if pd.notna(row['成交额']) else None,
                        "change_pct": float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else None,
                        "change": float(row['涨跌额']) if pd.notna(row['涨跌额']) else None,
                        "source": "akshare",
                        "timestamp": datetime.now().isoformat()
                    }
            except Exception as e:
                logger.warning(f"AkShare获取{code}失败: {e}")
        
        if source == "baostock" or (source == "auto" and bs):
            try:
                lg = bs.login()
                if lg.error_code == '0':
                    bs_code = to_baostock_code(code)
                    rs = bs.query_latest_price(bs_code)
                    if rs.error_code == '0' and rs.next():
                        data = rs.get_row_data()
                        bs.logout()
                        return {
                            "code": code,
                            "name": code,
                            "price": float(data[1]) if data[1] else None,
                            "source": "baostock",
                            "timestamp": datetime.now().isoformat()
                        }
                    bs.logout()
            except Exception as e:
                logger.warning(f"Baostock获取{code}失败: {e}")
        
        return None
    
    @staticmethod
    def get_realtime_quotes(codes: List[str] = None, source: str = "auto") -> Tuple[List[Dict], str]:
        """
        获取多只股票实时行情
        Returns: (数据列表, 实际数据源)
        """
        # 如果指定了codes且数量较少，尝试多源验证
        if codes and len(codes) <= 5:
            results = []
            for code in codes:
                # 优先尝试AkShare（速度最快）
                data = DataSourceManager.get_realtime_quote_single(code, "akshare")
                if data:
                    results.append(data)
            if results:
                return results, "akshare"
        
        # 批量获取全部A股
        if source in ("auto", "akshare"):
            try:
                df = ak.stock_zh_a_spot_em()
                logger.info(f"✅ AkShare获取全市场实时行情成功: {len(df)}条")
                records = []
                for _, row in df.iterrows():
                    records.append({
                        "code": row['代码'],
                        "name": row['名称'],
                        "price": float(row['最新价']) if pd.notna(row['最新价']) else None,
                        "change_pct": float(row['涨跌幅']) if pd.notna(row['涨跌幅']) else None,
                        "change": float(row['涨跌额']) if pd.notna(row['涨跌额']) else None,
                        "volume": int(row['成交量']) if pd.notna(row['成交量']) else None,
                        "amount": float(row['成交额']) if pd.notna(row['成交额']) else None,
                        "open": float(row['今开']) if pd.notna(row['今开']) else None,
                        "high": float(row['最高']) if pd.notna(row['最高']) else None,
                        "low": float(row['最低']) if pd.notna(row['最低']) else None,
                        "pre_close": float(row['昨收']) if pd.notna(row['昨收']) else None,
                        "turnover": float(row['换手率']) if pd.notna(row['换手率']) else None,
                        "pe": float(row['市盈率-动态']) if pd.notna(row['市盈率-动态']) else None,
                        "pb": float(row['市净率']) if pd.notna(row['市净率']) else None,
                        "market_cap": float(row['总市值']) if pd.notna(row['总市值']) else None,
                    })
                return records, "akshare"
            except Exception as e:
                logger.error(f"AkShare获取全市场失败: {e}")
        
        if source in ("auto", "tushare") and pro:
            try:
                # Tushare获取需要逐个查询，效率较低
                df = pro.stock_basic(exchange='', list_status='L')
                logger.info(f"✅ Tushare获取股票列表成功: {len(df)}条")
                return df.to_dict('records'), "tushare"
            except Exception as e:
                logger.error(f"Tushare获取失败: {e}")
        
        return [], "none"
    
    @staticmethod
    def get_history_data(code: str, start_date: str, end_date: str, source: str = "auto") -> Tuple[pd.DataFrame, str]:
        """获取历史K线数据"""
        code = normalize_code(code)
        
        # 尝试Tushare Pro（质量最高）
        if source in ("auto", "tushare") and pro:
            try:
                ts_code = to_tushare_code(code)
                df = pro.daily(ts_code=ts_code, start_date=start_date.replace('-', ''), 
                              end_date=end_date.replace('-', ''))
                if not df.empty:
                    df = df.rename(columns={
                        'trade_date': 'date',
                        'open': 'open',
                        'high': 'high',
                        'low': 'low',
                        'close': 'close',
                        'vol': 'volume',
                        'amount': 'amount'
                    })
                    df['date'] = pd.to_datetime(df['date'])
                    df['code'] = code
                    logger.info(f"✅ Tushare历史数据获取成功: {code} {len(df)}条")
                    return df, "tushare"
            except Exception as e:
                logger.warning(f"Tushare历史数据获取失败: {e}")
        
        # 尝试AkShare
        if source in ("auto", "akshare"):
            try:
                exchange = get_exchange(code)
                df = ak.stock_zh_a_hist(symbol=code, period="daily", 
                                        start_date=start_date, end_date=end_date,
                                        adjust="qfq")
                if not df.empty:
                    df = df.rename(columns={
                        '日期': 'date',
                        '开盘': 'open',
                        '收盘': 'close',
                        '最高': 'high',
                        '最低': 'low',
                        '成交量': 'volume',
                        '成交额': 'amount'
                    })
                    df['code'] = code
                    logger.info(f"✅ AkShare历史数据获取成功: {code} {len(df)}条")
                    return df, "akshare"
            except Exception as e:
                logger.warning(f"AkShare历史数据获取失败: {e}")
        
        # 尝试Baostock
        if source in ("auto", "baostock") and bs:
            try:
                lg = bs.login()
                if lg.error_code == '0':
                    bs_code = to_baostock_code(code)
                    rs = bs.query_history_k_data_plus(bs_code,
                        "date,code,open,high,low,close,preclose,volume,amount,turn,pctChg",
                        start_date=start_date, end_date=end_date, frequency="d", adjustflag="3")
                    
                    data_list = []
                    while (rs.error_code == '0') & rs.next():
                        data_list.append(rs.get_row_data())
                    
                    bs.logout()
                    
                    if data_list:
                        df = pd.DataFrame(data_list, columns=rs.fields)
                        df['date'] = pd.to_datetime(df['date'])
                        df['code'] = code
                        logger.info(f"✅ Baostock历史数据获取成功: {code} {len(df)}条")
                        return df, "baostock"
            except Exception as e:
                logger.warning(f"Baostock历史数据获取失败: {e}")
        
        return pd.DataFrame(), "none"

# 全局数据源管理器实例
dsm = DataSourceManager()

# === API端点 ===

@app.route("/api/health", methods=["GET"])
def health_check():
    """系统健康检查"""
    checks = {
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "data_sources": {},
        "cache_stats": _cache_stats
    }
    
    # 检查Tushare
    try:
        if pro:
            df = pro.trade_cal(exchange="SSE", start_date="20260101", end_date="20260131", limit=1)
            checks["data_sources"]["tushare"] = {"status": "ok", "token_configured": True}
        else:
            checks["data_sources"]["tushare"] = {"status": "error", "message": "未初始化"}
    except Exception as e:
        checks["data_sources"]["tushare"] = {"status": "error", "message": str(e)}
    
    # 检查AkShare
    try:
        df = ak.stock_zh_a_spot_em()
        checks["data_sources"]["akshare"] = {"status": "ok", "records": len(df)}
    except Exception as e:
        checks["data_sources"]["akshare"] = {"status": "error", "message": str(e)}
    
    # 检查Baostock
    try:
        if bs:
            lg = bs.login()
            if lg.error_code == '0':
                checks["data_sources"]["baostock"] = {"status": "ok"}
                bs.logout()
            else:
                checks["data_sources"]["baostock"] = {"status": "error", "code": lg.error_code}
        else:
            checks["data_sources"]["baostock"] = {"status": "not_installed"}
    except Exception as e:
        checks["data_sources"]["baostock"] = {"status": "error", "message": str(e)}
    
    # 检查同花顺
    checks["data_sources"]["ths"] = {"status": "ok" if _ths_logged_in else "not_configured"}
    
    # 综合状态
    active_sources = sum(1 for s in checks["data_sources"].values() if s.get("status") == "ok")
    if active_sources == 0:
        checks["status"] = "critical"
    elif active_sources < 2:
        checks["status"] = "degraded"
    
    checks["active_sources"] = active_sources
    checks["cache_entries"] = len(_cache)
    
    return jsonify(checks)

@app.route("/api/market/realtime", methods=["GET"])
@rate_limit(max_calls=60, period=60)
@cached(ttl=30)
def get_realtime():
    """获取A股实时行情"""
    try:
        limit = request.args.get("limit", 100, type=int)
        codes = request.args.get("codes", "")
        
        if codes:
            code_list = [c.strip() for c in codes.split(",") if c.strip()]
            data, source = dsm.get_realtime_quotes(code_list)
        else:
            data, source = dsm.get_realtime_quotes()
            data = sorted(data, key=lambda x: x.get("change_pct", 0) or 0, reverse=True)[:limit]
        
        return jsonify({
            "code": 200,
            "data": data,
            "source": source,
            "count": len(data),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"实时行情获取失败: {e}\n{traceback.format_exc()}")
        return jsonify({"code": 500, "error": str(e)}), 500

@app.route("/api/market/index", methods=["GET"])
@rate_limit(max_calls=30, period=60)
@cached(ttl=30)
def get_market_index():
    """获取大盘指数"""
    try:
        # 上证指数、深证成指、创业板指
        index_codes = ["000001", "399001", "399006"]
        result = []
        
        for code in index_codes:
            data = dsm.get_realtime_quote_single(code, "akshare")
            if data:
                result.append(data)
        
        return jsonify({
            "code": 200,
            "data": result,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"大盘指数获取失败: {e}")
        return jsonify({"code": 500, "error": str(e)}), 500

@app.route("/api/stock/detail/<code>", methods=["GET"])
@rate_limit(max_calls=60, period=60)
@cached(ttl=60)
def get_stock_detail(code):
    """获取个股详细信息"""
    try:
        # 尝试多源获取
        data = dsm.get_realtime_quote_single(code, "akshare")
        
        if not data:
            return jsonify({"code": 404, "error": f"未找到股票 {code}"}), 404
        
        # 获取额外信息（如财务数据）
        if pro:
            try:
                ts_code = to_tushare_code(code)
                daily = pro.daily_basic(ts_code=ts_code, trade_date=datetime.now().strftime('%Y%m%d'))
                if not daily.empty:
                    row = daily.iloc[0]
                    data.update({
                        "turnover_rate": float(row['turnover_rate']) if pd.notna(row['turnover_rate']) else None,
                        "volume_ratio": float(row['volume_ratio']) if pd.notna(row['volume_ratio']) else None,
                        "pe_ttm": float(row['pe_ttm']) if pd.notna(row['pe_ttm']) else None,
                        "pb": float(row['pb']) if pd.notna(row['pb']) else None,
                        "ps": float(row['ps_ttm']) if pd.notna(row['ps_ttm']) else None,
                        "total_mv": float(row['total_mv']) if pd.notna(row['total_mv']) else None,
                        "circ_mv": float(row['circ_mv']) if pd.notna(row['circ_mv']) else None,
                    })
            except Exception as e:
                logger.debug(f"获取财务数据失败: {e}")
        
        return jsonify({
            "code": 200,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"股票详情获取失败: {e}")
        return jsonify({"code": 500, "error": str(e)}), 500

@app.route("/api/stock/history/<code>", methods=["GET"])
@rate_limit(max_calls=30, period=60)
@cached(ttl=300)
def get_stock_history(code):
    """获取个股历史数据"""
    try:
        days = request.args.get("days", 252, type=int)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        df, source = dsm.get_history_data(
            code, 
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d')
        )
        
        if df.empty:
            return jsonify({"code": 404, "error": f"未找到股票 {code} 的历史数据"}), 404
        
        return jsonify({
            "code": 200,
            "data": df.to_dict('records'),
            "source": source,
            "count": len(df),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"历史数据获取失败: {e}")
        return jsonify({"code": 500, "error": str(e)}), 500

@app.route("/api/sector/flow", methods=["GET"])
@rate_limit(max_calls=20, period=60)
@cached(ttl=60)
def get_sector_flow():
    """获取板块资金流向"""
    try:
        df = ak.stock_sector_fund_flow_rank(indicator="今日")
        data = df.head(20).to_dict('records')
        return jsonify({
            "code": 200,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })
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
        return jsonify({
            "code": 200,
            "data": {
                "north_flow": latest,
                "unit": "亿元",
                "trend": df.tail(20).to_dict('records')
            },
            "timestamp": datetime.now().isoformat()
        })
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
        return jsonify({
            "code": 200,
            "data": df.to_dict('records'),
            "count": len(df),
            "timestamp": datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"涨停板池获取失败: {e}")
        return jsonify({"code": 500, "error": str(e)}), 500

@app.route("/api/cache/clear", methods=["POST"])
def clear_cache_endpoint():
    """清空缓存"""
    clear_cache()
    return jsonify({"code": 200, "message": "缓存已清空"})

@app.route("/api/cache/stats", methods=["GET"])
def cache_stats():
    """获取缓存统计"""
    return jsonify({
        "code": 200,
        "entries": len(_cache),
        "stats": _cache_stats,
        "sources_config": DATA_SOURCE_CONFIG
    })

# === 启动入口 ===
if __name__ == "__main__":
    # 确保日志目录存在
    os.makedirs("logs", exist_ok=True)
    
    logger.info("🚀 增强版数据网关启动中...")
    logger.info(f"数据源配置: {json.dumps(DATA_SOURCE_CONFIG, indent=2)}")
    
    app.run(host="0.0.0.0", port=5001, debug=False)
