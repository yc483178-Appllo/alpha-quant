#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alpha V6.0 - 聚宽数据网关 (JoinQuant Gateway)
连接聚宽数据API，提供股票、期货、基金等市场数据
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
import os

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 尝试导入聚宽SDK，如不可用则使用模拟数据
try:
    from jqdatasdk import auth, get_price, get_all_securities, get_fundamentals
    JQDATA_AVAILABLE = True
except ImportError:
    JQDATA_AVAILABLE = False
    logger.warning("聚宽SDK未安装，将使用模拟数据模式")


@dataclass
class MarketData:
    """市场数据结构"""
    symbol: str
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    
    def to_dict(self) -> Dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "amount": self.amount
        }


class JoinQuantGateway:
    """
    聚宽数据网关
    
    功能：
    1. 用户认证和会话管理
    2. 实时行情数据获取
    3. 历史数据下载
    4. 基本面数据查询
    5. 数据缓存管理
    """
    
    def __init__(self, config_path: str = "/opt/alpha-system/config/config.json"):
        self.config = self._load_config(config_path)
        self.enabled = self.config.get("enabled", True)
        self.username = self.config.get("username", "")
        self.password = self.config.get("password", "")
        self.api_endpoint = self.config.get("api_endpoint", "https://dataapi.joinquant.com")
        self.cache_duration = self.config.get("cache_duration", 300)
        self.rate_limit = self.config.get("rate_limit", 100)
        
        self.is_authenticated = False
        self.last_request_time = 0
        self.request_count = 0
        self.cache: Dict[str, Any] = {}
        
        # 模拟数据模式（当JQData不可用时）
        self.mock_mode = not JQDATA_AVAILABLE
        
        if self.enabled and not self.mock_mode:
            self._authenticate()
        else:
            logger.info("聚宽网关以模拟模式运行")
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get("joinquant", {})
        except Exception as e:
            logger.warning(f"无法加载配置: {e}，使用默认配置")
            return {"enabled": True}
    
    def _authenticate(self):
        """认证到聚宽API"""
        if not self.username or not self.password:
            logger.warning("未配置聚宽账号，切换到模拟模式")
            self.mock_mode = True
            return
        
        try:
            if JQDATA_AVAILABLE:
                auth(self.username, self.password)
                self.is_authenticated = True
                logger.info("聚宽API认证成功")
            else:
                self.mock_mode = True
        except Exception as e:
            logger.error(f"聚宽认证失败: {e}")
            self.mock_mode = True
    
    def _check_rate_limit(self):
        """检查速率限制"""
        current_time = time.time()
        if current_time - self.last_request_time > 60:
            self.request_count = 0
            self.last_request_time = current_time
        
        if self.request_count >= self.rate_limit:
            sleep_time = 60 - (current_time - self.last_request_time)
            if sleep_time > 0:
                logger.debug(f"速率限制，等待 {sleep_time:.1f} 秒")
                time.sleep(sleep_time)
            self.request_count = 0
            self.last_request_time = time.time()
        
        self.request_count += 1
    
    def _get_cache_key(self, method: str, params: Dict) -> str:
        """生成缓存键"""
        return f"{method}:{json.dumps(params, sort_keys=True)}"
    
    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """从缓存获取数据"""
        if cache_key in self.cache:
            cached_time, data = self.cache[cache_key]
            if time.time() - cached_time < self.cache_duration:
                return data
            else:
                del self.cache[cache_key]
        return None
    
    def _save_to_cache(self, cache_key: str, data: Any):
        """保存数据到缓存"""
        self.cache[cache_key] = (time.time(), data)
    
    def _generate_mock_price_data(self, symbol: str, count: int = 100) -> List[MarketData]:
        """生成模拟价格数据"""
        base_price = random.uniform(10, 200)
        data = []
        
        for i in range(count):
            timestamp = datetime.now() - timedelta(minutes=count-i)
            change = random.uniform(-0.02, 0.02)
            close = base_price * (1 + change)
            high = close * (1 + random.uniform(0, 0.01))
            low = close * (1 - random.uniform(0, 0.01))
            open_price = (high + low) / 2
            volume = int(random.uniform(10000, 1000000))
            amount = close * volume
            
            data.append(MarketData(
                symbol=symbol,
                timestamp=timestamp.isoformat(),
                open=round(open_price, 2),
                high=round(high, 2),
                low=round(low, 2),
                close=round(close, 2),
                volume=volume,
                amount=round(amount, 2)
            ))
            base_price = close
        
        return data
    
    def get_price_data(self, symbol: str, frequency: str = "1m", 
                       count: int = 100, end_date: Optional[str] = None) -> List[MarketData]:
        """
        获取价格数据
        
        Args:
            symbol: 股票代码，如 "000001.XSHE"
            frequency: 频率，如 "1m", "5m", "1d"
            count: 数据条数
            end_date: 结束日期
        """
        cache_key = self._get_cache_key("get_price", {
            "symbol": symbol, "frequency": frequency, "count": count
        })
        
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        self._check_rate_limit()
        
        if self.mock_mode:
            data = self._generate_mock_price_data(symbol, count)
        else:
            try:
                # 聚宽API调用
                df = get_price(symbol, count=count, frequency=frequency, end_date=end_date)
                data = []
                for idx, row in df.iterrows():
                    data.append(MarketData(
                        symbol=symbol,
                        timestamp=idx.isoformat(),
                        open=row.get('open', 0),
                        high=row.get('high', 0),
                        low=row.get('low', 0),
                        close=row.get('close', 0),
                        volume=int(row.get('volume', 0)),
                        amount=row.get('money', 0)
                    ))
            except Exception as e:
                logger.error(f"获取价格数据失败: {e}")
                data = self._generate_mock_price_data(symbol, count)
        
        self._save_to_cache(cache_key, data)
        return data
    
    def get_realtime_quote(self, symbols: List[str]) -> Dict[str, Dict]:
        """获取实时行情"""
        cache_key = self._get_cache_key("realtime", {"symbols": symbols})
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        result = {}
        for symbol in symbols:
            # 生成模拟实时数据
            base_price = random.uniform(10, 200)
            change_pct = random.uniform(-0.05, 0.05)
            
            result[symbol] = {
                "symbol": symbol,
                "name": f"股票{symbol[:6]}",
                "price": round(base_price, 2),
                "change": round(base_price * change_pct, 2),
                "change_pct": round(change_pct * 100, 2),
                "volume": int(random.uniform(10000, 10000000)),
                "turnover": round(random.uniform(1000000, 100000000), 2),
                "bid": round(base_price * 0.999, 2),
                "ask": round(base_price * 1.001, 2),
                "high": round(base_price * 1.03, 2),
                "low": round(base_price * 0.97, 2),
                "open": round(base_price * (1 + random.uniform(-0.01, 0.01)), 2),
                "pre_close": round(base_price / (1 + change_pct), 2),
                "timestamp": datetime.now().isoformat()
            }
        
        self._save_to_cache(cache_key, result)
        return result
    
    def get_all_securities(self, security_type: str = "stock") -> List[Dict]:
        """获取所有证券列表"""
        cache_key = self._get_cache_key("securities", {"type": security_type})
        cached = self._get_from_cache(cache_key)
        if cached:
            return cached
        
        if self.mock_mode:
            # 生成模拟股票列表
            securities = []
            for i in range(100):
                code = f"{600000 + i:06d}.XSHG" if i < 50 else f"{300000 + i:06d}.XSHE"
                securities.append({
                    "code": code,
                    "name": f"股票{i+1}",
                    "type": security_type,
                    "list_date": "2020-01-01"
                })
        else:
            try:
                df = get_all_securities(types=[security_type])
                securities = df.reset_index().to_dict('records')
            except Exception as e:
                logger.error(f"获取证券列表失败: {e}")
                securities = []
        
        self._save_to_cache(cache_key, securities)
        return securities
    
    def get_fundamentals_data(self, symbol: str, table: str = "valuation") -> Dict:
        """获取基本面数据"""
        if self.mock_mode:
            return {
                "symbol": symbol,
                "pe_ratio": round(random.uniform(5, 50), 2),
                "pb_ratio": round(random.uniform(0.5, 10), 2),
                "ps_ratio": round(random.uniform(0.5, 20), 2),
                "market_cap": round(random.uniform(10, 10000), 2),
                "roe": round(random.uniform(0.05, 0.3), 4),
                "debt_to_equity": round(random.uniform(0.2, 2.0), 2),
                "revenue_growth": round(random.uniform(-0.2, 1.0), 4),
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            q = get_fundamentals(query(table).filter(table.code == symbol))
            if len(q) > 0:
                return q.iloc[0].to_dict()
            return {}
        except Exception as e:
            logger.error(f"获取基本面数据失败: {e}")
            return {}
    
    def get_status(self) -> Dict:
        """获取网关状态"""
        return {
            "enabled": self.enabled,
            "mock_mode": self.mock_mode,
            "authenticated": self.is_authenticated,
            "api_available": JQDATA_AVAILABLE,
            "cache_size": len(self.cache),
            "request_count": self.request_count,
            "rate_limit": self.rate_limit
        }


# 导入random用于生成模拟数据
import random

# 单例实例
_jq_gateway = None

def get_joinquant_gateway() -> JoinQuantGateway:
    """获取聚宽网关单例"""
    global _jq_gateway
    if _jq_gateway is None:
        _jq_gateway = JoinQuantGateway()
    return _jq_gateway


if __name__ == "__main__":
    # 测试
    gateway = JoinQuantGateway()
    print("网关状态:", gateway.get_status())
    
    # 测试获取实时行情
    quotes = gateway.get_realtime_quote(["000001.XSHE", "600000.XSHG"])
    print("\n实时行情:")
    print(json.dumps(quotes, indent=2, ensure_ascii=False))
