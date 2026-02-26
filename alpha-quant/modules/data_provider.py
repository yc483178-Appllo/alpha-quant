"""
数据获取模块 - 整合 Tushare + AkShare
"""
import pandas as pd
import numpy as np
import tushare as ts
import subprocess
import json
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import config

class DataProvider:
    """数据提供者 - 双源交叉验证"""
    
    def __init__(self):
        self.ts_pro = ts.pro_api(config.TUSHARE_TOKEN)
        self.akshare_path = config.AKSHARE_PATH
        
    def _akshare_exec(self, code: str) -> pd.DataFrame:
        """执行 AkShare Python 代码并返回 DataFrame"""
        try:
            result = subprocess.run(
                [self.akshare_path, "-c", code],
                capture_output=True,
                text=True,
                timeout=30
            )
            if result.returncode == 0:
                # 解析 JSON 输出
                data = json.loads(result.stdout)
                return pd.DataFrame(data)
            else:
                print(f"AkShare Error: {result.stderr}")
                return pd.DataFrame()
        except Exception as e:
            print(f"AkShare Exec Error: {e}")
            return pd.DataFrame()
    
    def get_index_daily(self, index_code: str = "000001.SH") -> pd.DataFrame:
        """
        获取指数日线数据
        index_code: 000001.SH(上证), 399001.SZ(深证), 399006.SZ(创业板)
        """
        # Tushare 数据源
        try:
            df_ts = self.ts_pro.index_daily(ts_code=index_code)
            df_ts = df_ts.sort_values('trade_date')
        except Exception as e:
            print(f"Tushare index error: {e}")
            df_ts = pd.DataFrame()
        
        # AkShare 数据源（交叉验证）
        symbol_map = {
            "000001.SH": "sh000001",
            "399001.SZ": "sz399001",
            "399006.SZ": "sz399006"
        }
        ak_code = symbol_map.get(index_code, "sh000001")
        
        ak_script = f'''
import akshare as ak
import json
df = ak.index_zh_a_hist(symbol="{ak_code}", period="daily", start_date="20240101")
print(df.to_json(orient='records', date_format='iso'))
'''
        df_ak = self._akshare_exec(ak_script)
        
        # 数据验证
        if not df_ts.empty and not df_ak.empty:
            # 比较最新收盘价
            ts_close = float(df_ts.iloc[-1]['close']) if 'close' in df_ts.columns else 0
            ak_close = float(df_ak.iloc[-1]['close']) if 'close' in df_ak.columns else 0
            
            if ts_close > 0 and ak_close > 0:
                diff_pct = abs(ts_close - ak_close) / ts_close
                if diff_pct > 0.05:
                    print(f"⚠️ 数据偏差警告: {index_code} 差异 {diff_pct:.2%}")
        
        return df_ts if not df_ts.empty else df_ak
    
    def get_stock_daily(self, ts_code: str) -> pd.DataFrame:
        """获取个股日线数据"""
        try:
            df = self.ts_pro.daily(ts_code=ts_code)
            return df.sort_values('trade_date')
        except Exception as e:
            print(f"Error fetching {ts_code}: {e}")
            return pd.DataFrame()
    
    def get_stock_basic(self) -> pd.DataFrame:
        """获取股票基础信息"""
        try:
            df = self.ts_pro.stock_basic(exchange='', list_status='L')
            return df
        except Exception as e:
            print(f"Error fetching stock basic: {e}")
            return pd.DataFrame()
    
    def get_daily_market(self, trade_date: Optional[str] = None) -> pd.DataFrame:
        """获取每日市场行情（涨跌家数等）"""
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        try:
            df = self.ts_pro.daily_info(trade_date=trade_date)
            return df
        except Exception as e:
            print(f"Error fetching daily market: {e}")
            return pd.DataFrame()
    
    def get_limit_up_stocks(self, trade_date: Optional[str] = None) -> pd.DataFrame:
        """获取涨停股票列表"""
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y%m%d')
        
        ak_script = f'''
import akshare as ak
import json
df = ak.stock_zt_pool_em(date="{trade_date}")
print(df.to_json(orient='records'))
'''
        return self._akshare_exec(ak_script)
    
    def get_northbound_flow(self, start_date: str, end_date: str) -> pd.DataFrame:
        """获取北向资金流向"""
        try:
            df = self.ts_pro.moneyflow_hsgt(start_date=start_date, end_date=end_date)
            return df
        except Exception as e:
            print(f"Error fetching northbound: {e}")
            return pd.DataFrame()
    
    def get_sector_hotspot(self) -> pd.DataFrame:
        """获取板块热点（成交额排名）"""
        ak_script = '''
import akshare as ak
import json
df = ak.stock_sector_fund_flow_rank(indicator="今日")
print(df.head(20).to_json(orient='records'))
'''
        return self._akshare_exec(ak_script)
    
    def get_realtime_quotes(self, symbols: List[str]) -> pd.DataFrame:
        """获取实时行情"""
        # 使用 AkShare 获取实时行情
        results = []
        for symbol in symbols:
            ak_script = f'''
import akshare as ak
import json
try:
    df = ak.stock_zh_a_spot_em()
    stock = df[df['代码'] == '{symbol.split('.')[0]}']
    if not stock.empty:
        print(stock.to_json(orient='records'))
    else:
        print('[]')
except:
    print('[]')
'''
            df = self._akshare_exec(ak_script)
            if not df.empty:
                results.append(df)
        
        if results:
            return pd.concat(results, ignore_index=True)
        return pd.DataFrame()

# 全局实例
data_provider = DataProvider()
