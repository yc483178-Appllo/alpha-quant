"""
同花顺数据接口模块 (iFinD/THS)
基于官方 API 文档实现
"""
import requests
import pandas as pd
import json
from typing import Optional, List, Dict
from datetime import datetime
from modules.config_manager import config_manager
from modules.logger import log

class THSDataProvider:
    """同花顺数据提供者"""
    
    def __init__(self):
        self.token = config_manager.get('data_sources.ths.token', '')
        self.base_url = "https://ft.10jqka.com.cn/api/v1"
        self.timeout = config_manager.get('data_sources.ths.timeout', 15)
        self.enabled = config_manager.get('data_sources.ths.enabled', False) and bool(self.token)
        
    def _request(self, endpoint: str, params: Dict = None, data: Dict = None, method: str = "GET") -> Dict:
        """发送 HTTP 请求"""
        if not self.enabled:
            return {}
        
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        try:
            if method.upper() == "GET":
                response = requests.get(url, headers=headers, params=params, timeout=self.timeout)
            else:
                response = requests.post(url, headers=headers, json=data, timeout=self.timeout)
            
            response.raise_for_status()
            result = response.json()
            
            if result.get('code') != 0:
                log.error(f"❌ 同花顺 API 错误: {result.get('msg', 'Unknown error')}")
                return {}
            
            return result.get('data', {})
            
        except requests.exceptions.Timeout:
            log.error("⏱️  同花顺 API 请求超时")
            return {}
        except requests.exceptions.RequestException as e:
            log.error(f"❌ 同花顺 API 请求失败: {e}")
            return {}
    
    # ==================== 股票行情接口 ====================
    
    def get_realtime_quotes(self, codes: List[str]) -> pd.DataFrame:
        """
        获取实时行情
        codes: 股票代码列表，如 ['000001.SZ', '600000.SH']
        """
        if not self.enabled:
            return pd.DataFrame()
        
        log.info(f"📊 THS 获取实时行情: {len(codes)} 只股票")
        
        data = self._request("quote/realtime", {"codes": ",".join(codes)})
        
        if not data:
            return pd.DataFrame()
        
        # 转换为 DataFrame
        df = pd.DataFrame(data)
        return df
    
    def get_kline(self, code: str, period: str = "day", start_date: str = None, end_date: str = None, count: int = 100) -> pd.DataFrame:
        """
        获取K线数据
        code: 股票代码，如 '000001.SZ'
        period: day/week/month
        """
        if not self.enabled:
            return pd.DataFrame()
        
        if not end_date:
            end_date = datetime.now().strftime('%Y%m%d')
        
        log.info(f"📈 THS 获取K线: {code} ({period})")
        
        params = {
            "code": code,
            "period": period,
            "end_date": end_date,
            "count": count
        }
        if start_date:
            params["start_date"] = start_date
        
        data = self._request("quote/kline", params)
        
        if not data:
            return pd.DataFrame()
        
        df = pd.DataFrame(data)
        # 标准化列名
        if not df.empty:
            df.columns = [col.lower() for col in df.columns]
        return df
    
    def get_tick(self, code: str, trade_date: str) -> pd.DataFrame:
        """
        获取分时成交数据
        code: 股票代码
        trade_date: 交易日期，如 '20240225'
        """
        if not self.enabled:
            return pd.DataFrame()
        
        log.info(f"⏰ THS 获取分时成交: {code} ({trade_date})")
        
        data = self._request("quote/tick", {"code": code, "trade_date": trade_date})
        
        return pd.DataFrame(data) if data else pd.DataFrame()
    
    # ==================== 股票信息接口 ====================
    
    def get_stock_basic(self, market: str = None) -> pd.DataFrame:
        """
        获取股票基础信息
        market: SH/SZ/BJ，None 表示全部
        """
        if not self.enabled:
            return pd.DataFrame()
        
        log.info("📋 THS 获取股票基础信息")
        
        params = {}
        if market:
            params["market"] = market
        
        data = self._request("stock/basic", params)
        
        return pd.DataFrame(data) if data else pd.DataFrame()
    
    def get_stock_list(self, market: str = "all") -> List[str]:
        """
        获取股票代码列表
        market: all/sh/sz/bj
        """
        if not self.enabled:
            return []
        
        df = self.get_stock_basic(market if market != "all" else None)
        
        if df.empty or 'code' not in df.columns:
            return []
        
        return df['code'].tolist()
    
    # ==================== 财务数据接口 ====================
    
    def get_financial_data(self, code: str, report_type: str = "income", period: str = None) -> pd.DataFrame:
        """
        获取财务数据
        report_type: income/balance/cashflow
        period: 报告期，如 '2023Q4'，None 表示最新
        """
        if not self.enabled:
            return pd.DataFrame()
        
        log.info(f"💰 THS 获取财务数据: {code} ({report_type})")
        
        params = {"code": code, "report_type": report_type}
        if period:
            params["period"] = period
        
        data = self._request("finance/data", params)
        
        return pd.DataFrame(data) if data else pd.DataFrame()
    
    def get_financial_indicator(self, code: str, indicators: List[str] = None) -> Dict:
        """
        获取财务指标
        indicators: 指标列表，如 ['roe', 'eps', 'pe', 'pb']
        """
        if not self.enabled:
            return {}
        
        log.info(f"📊 THS 获取财务指标: {code}")
        
        params = {"code": code}
        if indicators:
            params["indicators"] = ",".join(indicators)
        
        return self._request("finance/indicator", params)
    
    # ==================== 市场数据接口 ====================
    
    def get_market_overview(self) -> Dict:
        """获取市场概况"""
        if not self.enabled:
            return {}
        
        log.info("🌐 THS 获取市场概况")
        
        return self._request("market/overview")
    
    def get_sector_hotspot(self, top_n: int = 20) -> pd.DataFrame:
        """
        获取板块热点
        top_n: 返回前N个板块
        """
        if not self.enabled:
            return pd.DataFrame()
        
        log.info("🔥 THS 获取板块热点")
        
        data = self._request("market/sector_hotspot", {"top_n": top_n})
        
        return pd.DataFrame(data) if data else pd.DataFrame()
    
    def get_northbound_flow(self, days: int = 5) -> pd.DataFrame:
        """
        获取北向资金流向
        days: 最近N天
        """
        if not self.enabled:
            return pd.DataFrame()
        
        log.info(f"💹 THS 获取北向资金流向 ({days}天)")
        
        data = self._request("market/northbound", {"days": days})
        
        return pd.DataFrame(data) if data else pd.DataFrame()
    
    # ==================== 特色数据接口 ====================
    
    def get_limit_up_stocks(self, trade_date: str = None) -> pd.DataFrame:
        """
        获取涨停股票
        trade_date: 交易日期，None 表示当天
        """
        if not self.enabled:
            return pd.DataFrame()
        
        if not trade_date:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        log.info(f"📈 THS 获取涨停股票 ({trade_date})")
        
        data = self._request("feature/limit_up", {"trade_date": trade_date})
        
        return pd.DataFrame(data) if data else pd.DataFrame()
    
    def get_money_flow(self, code: str, days: int = 5) -> pd.DataFrame:
        """
        获取资金流向
        code: 股票代码
        days: 最近N天
        """
        if not self.enabled:
            return pd.DataFrame()
        
        log.info(f"💰 THS 获取资金流向: {code}")
        
        data = self._request("feature/money_flow", {"code": code, "days": days})
        
        return pd.DataFrame(data) if data else pd.DataFrame()
    
    def get_margin_trade(self, code: str = None) -> pd.DataFrame:
        """
        获取融资融券数据
        code: 股票代码，None 表示全市场
        """
        if not self.enabled:
            return pd.DataFrame()
        
        log.info(f"📊 THS 获取融资融券数据: {code or '全市场'}")
        
        params = {}
        if code:
            params["code"] = code
        
        data = self._request("feature/margin_trade", params)
        
        return pd.DataFrame(data) if data else pd.DataFrame()

# 全局实例
ths_provider = THSDataProvider()
