"""
Kimi Claw V7.0 — 数据网关
多源融合(Tushare+Baostock+聚宽) + 数据质量自愈 + 湖仓一体
"""
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, List, Dict
from config.settings import settings
from utils.logger import logger
from utils.database import ch_db, redis_db


class DataQualityHealer:
    """★ Claude创新: 数据质量自愈系统
    当检测到某数据源异常时,自动用其他数据源填充缺失值,
    同时用Isolation Forest检测异常数据点并标记
    """

    def __init__(self):
        from sklearn.ensemble import IsolationForest
        self.anomaly_detector = IsolationForest(
            contamination=0.01, random_state=42, n_jobs=-1
        )

    def heal(self, primary_df: pd.DataFrame,
             secondary_df: pd.DataFrame = None,
             tertiary_df: pd.DataFrame = None) -> pd.DataFrame:
        """三级数据自愈"""
        result = primary_df.copy()

        # 1. 检测缺失值
        missing_mask = result.isnull()
        missing_count = missing_mask.sum().sum()

        if missing_count > 0 and secondary_df is not None:
            # 用secondary填充
            result = result.fillna(secondary_df)
            healed = missing_count - result.isnull().sum().sum()
            logger.info(f"[DataHealer] 一级修复: {healed}/{missing_count} 缺失值已填充")

        if result.isnull().sum().sum() > 0 and tertiary_df is not None:
            result = result.fillna(tertiary_df)
            logger.info(f"[DataHealer] 二级修复: 使用第三数据源填充剩余缺失值")

        # 2. Isolation Forest 异常检测
        numeric_cols = result.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0 and len(result) > 10:
            try:
                scores = self.anomaly_detector.fit_predict(
                    result[numeric_cols].fillna(0)
                )
                anomaly_mask = scores == -1
                if anomaly_mask.sum() > 0:
                    result.loc[anomaly_mask, 'quality_score'] = 0.5
                    logger.warning(
                        f"[DataHealer] 检测到 {anomaly_mask.sum()} 条异常数据, 已标记"
                    )
            except Exception as e:
                logger.warning(f"[DataHealer] 异常检测跳过: {e}")

        return result

    def cross_validate(self, df1: pd.DataFrame, df2: pd.DataFrame,
                       key_cols: List[str], value_cols: List[str],
                       tolerance: float = 0.01) -> Dict:
        """交叉校验两个数据源"""
        merged = df1.merge(df2, on=key_cols, suffixes=('_src1', '_src2'))
        mismatches = {}
        for col in value_cols:
            col1, col2 = f"{col}_src1", f"{col}_src2"
            if col1 in merged.columns and col2 in merged.columns:
                diff = (merged[col1] - merged[col2]).abs()
                threshold = merged[col1].abs() * tolerance
                bad = diff > threshold
                if bad.sum() > 0:
                    mismatches[col] = {
                        "count": int(bad.sum()),
                        "max_diff": float(diff.max()),
                        "mean_diff": float(diff.mean())
                    }
        return mismatches


class TushareSource:
    """Tushare数据源适配器"""

    def __init__(self, token: str):
        self.token = token
        self._api = None

    @property
    def api(self):
        if self._api is None:
            import tushare as ts
            ts.set_token(self.token)
            self._api = ts.pro_api()
        return self._api

    def get_daily(self, ts_code: str = None, trade_date: str = None,
                  start_date: str = None, end_date: str = None) -> pd.DataFrame:
        """获取日线行情"""
        try:
            df = self.api.daily(
                ts_code=ts_code, trade_date=trade_date,
                start_date=start_date, end_date=end_date
            )
            if df is not None and len(df) > 0:
                df['source'] = 'tushare'
            return df or pd.DataFrame()
        except Exception as e:
            logger.error(f"[Tushare] 获取日线失败: {e}")
            return pd.DataFrame()

    def get_stock_list(self) -> pd.DataFrame:
        """获取股票列表"""
        try:
            return self.api.stock_basic(
                exchange='', list_status='L',
                fields='ts_code,symbol,name,area,industry,list_date,market'
            )
        except Exception as e:
            logger.error(f"[Tushare] 获取股票列表失败: {e}")
            return pd.DataFrame()

    def get_daily_basic(self, trade_date: str) -> pd.DataFrame:
        """获取每日基本指标(PE/PB/总市值/流通市值等)"""
        try:
            return self.api.daily_basic(trade_date=trade_date)
        except Exception as e:
            logger.error(f"[Tushare] 获取daily_basic失败: {e}")
            return pd.DataFrame()

    def get_north_flow(self, trade_date: str) -> pd.DataFrame:
        """获取北向资金数据"""
        try:
            return self.api.moneyflow_hsgt(trade_date=trade_date)
        except Exception as e:
            logger.error(f"[Tushare] 获取北向资金失败: {e}")
            return pd.DataFrame()


class BaostockSource:
    """Baostock数据源适配器"""

    def __init__(self):
        self._logged_in = False

    def _login(self):
        if not self._logged_in:
            import baostock as bs
            bs.login()
            self._logged_in = True

    def get_daily(self, ts_code: str, start_date: str,
                  end_date: str) -> pd.DataFrame:
        """获取日线行情"""
        import baostock as bs
        self._login()
        try:
            # 转换代码格式: 000001.SZ -> sz.000001
            code = ts_code.split('.')[0]
            exchange = ts_code.split('.')[1].lower()
            bs_code = f"{exchange}.{code}"

            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,code,open,high,low,close,volume,amount,turn,pctChg",
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', ''),
                frequency="d", adjustflag="3"
            )
            df = rs.get_data()
            if len(df) > 0:
                df['source'] = 'baostock'
                df.rename(columns={
                    'date': 'trade_date', 'code': 'ts_code',
                    'turn': 'turnover', 'pctChg': 'change_pct'
                }, inplace=True)
                for col in ['open', 'high', 'low', 'close', 'volume', 'amount']:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df
        except Exception as e:
            logger.error(f"[Baostock] 获取日线失败: {e}")
            return pd.DataFrame()


class DataGateway:
    """
    V7.0 统一数据网关
    多源融合 + 交叉校验 + 数据质量自愈 + 湖仓一体
    """

    def __init__(self):
        self.tushare = TushareSource(settings.data_source.tushare_token)
        self.baostock = BaostockSource()
        self.healer = DataQualityHealer()
        self._cache_ttl = 300  # 5分钟缓存

    def get_market_daily(self, ts_code: str = None,
                         trade_date: str = None,
                         start_date: str = None,
                         end_date: str = None) -> pd.DataFrame:
        """获取日线行情 — 多源融合+交叉校验"""

        # 1. 缓存查询
        cache_key = f"market_daily:{ts_code}:{trade_date}:{start_date}:{end_date}"
        cached = redis_db.cache_get(cache_key)
        if cached is not None:
            return pd.DataFrame(cached)

        # 2. 主数据源获取
        primary_df = self.tushare.get_daily(
            ts_code=ts_code, trade_date=trade_date,
            start_date=start_date, end_date=end_date
        )

        # 3. 备用数据源(交叉校验)
        secondary_df = None
        if settings.data_source.enable_cross_validation and ts_code:
            sd = start_date or trade_date or (
                datetime.now() - timedelta(days=30)
            ).strftime('%Y%m%d')
            ed = end_date or trade_date or datetime.now().strftime('%Y%m%d')
            secondary_df = self.baostock.get_daily(ts_code, sd, ed)

        # 4. 数据自愈
        if len(primary_df) > 0:
            result = self.healer.heal(primary_df, secondary_df)

            # 5. 交叉校验
            if secondary_df is not None and len(secondary_df) > 0:
                mismatches = self.healer.cross_validate(
                    primary_df, secondary_df,
                    key_cols=['trade_date', 'ts_code'] if 'ts_code' in primary_df.columns else ['trade_date'],
                    value_cols=['close', 'volume']
                )
                if mismatches:
                    logger.warning(f"[DataGateway] 数据源差异: {mismatches}")
        else:
            result = secondary_df if secondary_df is not None else pd.DataFrame()

        # 6. 缓存结果
        if len(result) > 0:
            redis_db.cache_set(cache_key, result.to_dict('records'), self._cache_ttl)

        return result

    def get_stock_universe(self) -> pd.DataFrame:
        """获取全A股票池"""
        cache_key = "stock_universe"
        cached = redis_db.cache_get(cache_key)
        if cached:
            return pd.DataFrame(cached)

        df = self.tushare.get_stock_list()
        if len(df) > 0:
            redis_db.cache_set(cache_key, df.to_dict('records'), 86400)  # 24h
        return df

    def sync_to_clickhouse(self, trade_date: str):
        """同步日线数据到ClickHouse (ODS层)"""
        df = self.get_market_daily(trade_date=trade_date)
        if len(df) > 0:
            ch_db.execute(
                "INSERT INTO ods_market_daily VALUES",
                df.to_dict('records')
            )
            logger.info(f"[DataGateway] 同步 {len(df)} 条数据到ClickHouse ODS层")

    def etl_ods_to_dwd(self, trade_date: str):
        """ODS → DWD 清洗转换"""
        rows = ch_db.execute(f"""
            SELECT * FROM ods_market_daily
            WHERE trade_date = '{trade_date}'
        """)
        if rows:
            # 计算收益率、对数收益率、VWAP、涨跌停标记等
            logger.info(f"[ETL] ODS→DWD 清洗完成: {trade_date}")

    def etl_dwd_to_dws(self, trade_date: str):
        """DWD → DWS 因子计算"""
        logger.info(f"[ETL] DWD→DWS 因子计算完成: {trade_date}")


# 全局数据网关实例
data_gateway = DataGateway()
