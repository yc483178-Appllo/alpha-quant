# Alpha-Genesis V7.0 - 3.2 数据网关多源融合与湖仓一体

## 3.2 数据网关 → 多源融合+湖仓一体

### 架构总览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          数据源层 (Sources)                               │
├─────────────┬─────────────┬─────────────┬─────────────────────────────┤
│  Tushare    │  Baostock   │   聚宽      │        其他数据源              │
│  - 实时行情  │  - 历史K线   │  - 基本面    │  - 新浪财经/东方财富           │
│  - 财务数据  │  - 指数数据  │  - 因子数据  │  - 新闻舆情                   │
│  - 龙虎榜   │  - 资金流向   │  - 行业数据  │  - 另类数据                  │
└──────┬──────┴──────┬──────┴──────┬──────┴──────────────┬──────────────┘
       │             │             │                      │
       └─────────────┴─────────────┴──────────────────────┘
                             │
                    ┌────────▼────────┐
                    │  数据质量自愈系统  │  ★ Claude创新
                    │  - 异常检测      │
                    │  - 交叉校验      │
                    │  - 缺失值填充     │
                    └────────┬────────┘
                             │
       ┌─────────────────────┼─────────────────────┐
       │                     │                     │
┌──────▼──────┐     ┌───────▼────────┐   ┌───────▼───────┐
│   Kafka     │     │   批量数据管道   │   │   Flink      │
│  (实时流)   │     │   (离线处理)    │   │  (实时计算)   │
└──────┬──────┘     └───────┬────────┘   └───────┬───────┘
       │                     │                     │
       └─────────────────────┼─────────────────────┘
                             │
                    ┌────────▼────────┐
                    │   湖仓一体层     │
                    │  Delta Lake/    │
                    │  Iceberg        │
                    └────────┬────────┘
                             │
       ┌─────────────────────┼─────────────────────┐
       │                     │                     │
┌──────▼──────┐    ┌────────▼────────┐   ┌───────▼────────┐
│ ClickHouse  │    │   PostgreSQL    │   │     Redis      │
│ (时序数据)   │    │   (业务数据)     │   │    (缓存)      │
│ - 行情数据   │    │ - 策略配置       │   │ - 热点数据     │
│ - 因子数据   │    │ - 用户信息       │   │ - 实时行情     │
│ -  tick数据  │    │ - 审计日志       │   │ - 会话状态     │
└─────────────┘    └─────────────────┘   └────────────────┘
                             │
                    ┌────────▼────────┐
                    │  分层数据模型    │
                    │  ODS→DWD→DWS→ADS│
                    └─────────────────┘
```

### 3.2.1 多源数据融合与交叉校验

```python
# multi_source_data_gateway.py
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import tushare as ts
import baostock as bs
from jqdata import *  # 聚宽
import asyncio


class DataSourceAdapter:
    """数据源适配器基类"""
    
    def __init__(self, source_name: str, priority: int = 1):
        self.source_name = source_name
        self.priority = priority
        self.status = 'active'  # active, degraded, offline
        
    async def fetch_price_data(
        self,
        code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """获取价格数据"""
        raise NotImplementedError
    
    async def fetch_fundamental_data(
        self,
        code: str,
        report_date: str
    ) -> pd.DataFrame:
        """获取基本面数据"""
        raise NotImplementedError
    
    def health_check(self) -> bool:
        """健康检查"""
        return self.status == 'active'


class TushareAdapter(DataSourceAdapter):
    """Tushare数据源适配器"""
    
    def __init__(self, token: str):
        super().__init__('tushare', priority=1)
        self.pro = ts.pro_api(token)
        
    async def fetch_price_data(
        self,
        code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """获取日线数据"""
        try:
            # Tushare代码格式转换
            ts_code = self._convert_code_format(code)
            
            df = self.pro.daily(
                ts_code=ts_code,
                start_date=start_date.replace('-', ''),
                end_date=end_date.replace('-', '')
            )
            
            # 标准化列名
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
            df['source'] = 'tushare'
            
            return df
            
        except Exception as e:
            self.status = 'degraded'
            print(f"[Tushare] Error fetching {code}: {e}")
            return pd.DataFrame()
    
    def _convert_code_format(self, code: str) -> str:
        """转换为Tushare代码格式"""
        if code.startswith('6'):
            return f"{code}.SH"
        else:
            return f"{code}.SZ"


class BaostockAdapter(DataSourceAdapter):
    """Baostock数据源适配器"""
    
    def __init__(self):
        super().__init__('baostock', priority=2)
        bs.login()
        
    async def fetch_price_data(
        self,
        code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """获取日线数据"""
        try:
            bs_code = self._convert_code_format(code)
            
            rs = bs.query_history_k_data_plus(
                bs_code,
                "date,code,open,high,low,close,volume,amount,turn,pctChg",
                start_date=start_date,
                end_date=end_date,
                frequency="d"
            )
            
            data_list = []
            while (rs.error_code == '0') & rs.next():
                data_list.append(rs.get_row_data())
            
            df = pd.DataFrame(data_list, columns=rs.fields)
            df['date'] = pd.to_datetime(df['date'])
            df['source'] = 'baostock'
            
            # 类型转换
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'pctChg']
            for col in numeric_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
            
        except Exception as e:
            self.status = 'degraded'
            print(f"[Baostock] Error fetching {code}: {e}")
            return pd.DataFrame()
    
    def _convert_code_format(self, code: str) -> str:
        """转换为Baostock代码格式"""
        if code.startswith('6'):
            return f"sh.{code}"
        else:
            return f"sz.{code}"


class JoinQuantAdapter(DataSourceAdapter):
    """聚宽数据源适配器"""
    
    def __init__(self, username: str, password: str):
        super().__init__('joinquant', priority=1)
        auth(username, password)
        
    async def fetch_price_data(
        self,
        code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """获取日线数据"""
        try:
            # 聚宽代码格式
            jq_code = self._convert_code_format(code)
            
            df = get_price(
                jq_code,
                start_date=start_date,
                end_date=end_date,
                frequency='daily'
            )
            
            df = df.reset_index()
            df = df.rename(columns={'index': 'date'})
            df['source'] = 'joinquant'
            
            return df
            
        except Exception as e:
            self.status = 'degraded'
            print(f"[JoinQuant] Error fetching {code}: {e}")
            return pd.DataFrame()


class MultiSourceDataGateway:
    """
    多源数据网关
    
    统一管理多个数据源，自动交叉校验
    """
    
    def __init__(self):
        self.adapters: List[DataSourceAdapter] = []
        self.quality_healer = DataQualityHealer()
        
    def register_adapter(self, adapter: DataSourceAdapter):
        """注册数据源适配器"""
        self.adapters.append(adapter)
        
    async def fetch_price_data(
        self,
        code: str,
        start_date: str,
        end_date: str,
        prefer_source: str = None
    ) -> pd.DataFrame:
        """
        获取价格数据（多源融合）
        
        流程:
        1. 从多个数据源并行获取
        2. 交叉校验
        3. 异常检测与修复
        4. 融合输出
        """
        # 并行获取数据
        tasks = []
        for adapter in self.adapters:
            if adapter.health_check():
                tasks.append(adapter.fetch_price_data(code, start_date, end_date))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 过滤异常结果
        valid_data = {}
        for adapter, result in zip(self.adapters, results):
            if isinstance(result, pd.DataFrame) and not result.empty:
                valid_data[adapter.source_name] = result
        
        if not valid_data:
            raise Exception(f"No data available for {code} from any source")
        
        # 交叉校验与融合
        fused_data = self._cross_validate_and_fuse(valid_data)
        
        # 数据质量修复
        healed_data = self.quality_healer.heal(fused_data, valid_data)
        
        return healed_data
    
    def _cross_validate_and_fuse(
        self,
        data_sources: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """
        交叉校验与融合
        
        策略:
        1. 以优先级最高的数据源为基准
        2. 其他数据源作为校验
        3. 出现差异时标记并处理
        """
        # 按优先级排序
        sorted_sources = sorted(
            self.adapters,
            key=lambda x: x.priority
        )
        
        # 选择基准数据源
        base_source = None
        for adapter in sorted_sources:
            if adapter.source_name in data_sources:
                base_source = adapter.source_name
                break
        
        if not base_source:
            return pd.DataFrame()
        
        base_df = data_sources[base_source].copy()
        base_df['data_quality'] = 'high'
        base_df['verified_by'] = base_source
        
        # 与其他数据源交叉校验
        for source_name, df in data_sources.items():
            if source_name == base_source:
                continue
            
            # 对齐日期
            merged = base_df.merge(
                df[['date', 'close']],
                on='date',
                suffixes=('', f'_{source_name}'),
                how='left'
            )
            
            # 检查价格差异
            close_col = f'close_{source_name}'
            if close_col in merged.columns:
                price_diff = abs(merged['close'] - merged[close_col]) / merged['close']
                
                # 标记差异超过1%的数据点
                suspicious = price_diff > 0.01
                base_df.loc[suspicious, 'data_quality'] = 'suspicious'
                base_df.loc[suspicious, 'verified_by'] += f',{source_name}(diff)'
                
                # 差异超过5%的数据点需要修复
                needs_healing = price_diff > 0.05
                base_df.loc[needs_healing, 'data_quality'] = 'needs_healing'
        
        return base_df


### 3.2.2 ★ 数据质量自愈系统 (Claude创新)

```python
# data_quality_healer.py
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from typing import Dict, List, Optional


class DataQualityHealer:
    """
    数据质量自愈系统
    
    ★ Claude创新：
    1. 自动异常检测 (Isolation Forest)
    2. 多源数据交叉填充
    3. 异常数据点标记
    """
    
    def __init__(self):
        self.anomaly_detector = IsolationForest(
            contamination=0.05,  # 预期5%的异常率
            random_state=42
        )
        self.is_fitted = False
        
    def heal(
        self,
        base_data: pd.DataFrame,
        alternative_sources: Dict[str, pd.DataFrame]
    ) -> pd.DataFrame:
        """
        数据质量修复主入口
        
        Args:
            base_data: 基准数据（已交叉校验标记）
            alternative_sources: 其他数据源数据
            
        Returns:
            修复后的数据
        """
        healed_data = base_data.copy()
        
        # 1. 检测异常数据点
        anomaly_scores = self._detect_anomalies(healed_data)
        healed_data['anomaly_score'] = anomaly_scores
        healed_data['is_anomaly'] = anomaly_scores < -0.5  # 阈值
        
        # 2. 修复异常/缺失值
        for idx in healed_data[healed_data['data_quality'] == 'needs_healing'].index:
            healed_data.loc[idx] = self._heal_row(
                healed_data.loc[idx],
                alternative_sources
            )
        
        # 3. 修复Isolation Forest检测到的异常
        for idx in healed_data[healed_data['is_anomaly']].index:
            if healed_data.loc[idx, 'data_quality'] == 'high':
                # 交叉校验通过但被模型标记为异常，需要人工复核
                healed_data.loc[idx, 'data_quality'] = 'anomaly_detected'
        
        return healed_data
    
    def _detect_anomalies(self, data: pd.DataFrame) -> np.ndarray:
        """
        使用Isolation Forest检测异常
        
        检测维度:
        - 价格变动率异常
        - 成交量异常
        - 价格-成交量关系异常
        """
        # 构建特征
        features = pd.DataFrame()
        features['price_change'] = data['close'].pct_change().abs()
        features['volume_zscore'] = (data['volume'] - data['volume'].rolling(20).mean()) / data['volume'].rolling(20).std()
        features['high_low_range'] = (data['high'] - data['low']) / data['close']
        
        # 填充缺失值
        features = features.fillna(0)
        
        # 训练/预测
        if not self.is_fitted:
            self.anomaly_detector.fit(features)
            self.is_fitted = True
        
        anomaly_scores = self.anomaly_detector.decision_function(features)
        
        return anomaly_scores
    
    def _heal_row(
        self,
        row: pd.Series,
        alternative_sources: Dict[str, pd.DataFrame]
    ) -> pd.Series:
        """
        修复单行数据
        
        策略：用其他数据源的数据填充
        """
        healed = row.copy()
        date = row['date']
        
        # 收集所有数据源的对应值
        candidates = {}
        for source_name, df in alternative_sources.items():
            match = df[df['date'] == date]
            if not match.empty:
                candidates[source_name] = match.iloc[0]
        
        if not candidates:
            # 无替代数据源，标记为不可修复
            healed['data_quality'] = 'unrecoverable'
            return healed
        
        # 使用中位数修复
        for col in ['open', 'high', 'low', 'close', 'volume']:
            if col in row.index:
                values = [candidates[s][col] for s in candidates if col in candidates[s]]
                if values:
                    healed[col] = np.median(values)
        
        healed['data_quality'] = 'healed'
        healed['healed_by'] = ','.join(candidates.keys())
        
        return healed
    
    def generate_quality_report(self, data: pd.DataFrame) -> Dict:
        """生成数据质量报告"""
        total = len(data)
        
        return {
            'total_records': total,
            'high_quality': len(data[data['data_quality'] == 'high']),
            'suspicious': len(data[data['data_quality'] == 'suspicious']),
            'healed': len(data[data['data_quality'] == 'healed']),
            'anomaly_detected': len(data[data['data_quality'] == 'anomaly_detected']),
            'unrecoverable': len(data[data['data_quality'] == 'unrecoverable']),
            'anomaly_rate': data['is_anomaly'].mean(),
            'sources_used': data['verified_by'].str.split(',').str.len().mean()
        }


### 3.2.3 ClickHouse时序数据库

```python
# clickhouse_manager.py
from clickhouse_driver import Client
import pandas as pd
from typing import List, Dict


class ClickHouseManager:
    """
    ClickHouse时序数据管理
    
    相比MongoDB的优势:
    - 查询性能提升100倍
    - 更好的时间序列支持
    - 列式存储，压缩率高
    - 适合大规模数据聚合分析
    """
    
    def __init__(self, host: str = 'localhost', port: int = 9000):
        self.client = Client(host=host, port=port)
        self._init_tables()
    
    def _init_tables(self):
        """初始化表结构"""
        # 日K线数据表
        self.client.execute('''
            CREATE TABLE IF NOT EXISTS stock_daily (
                code String,
                date Date,
                open Float64,
                high Float64,
                low Float64,
                close Float64,
                volume UInt64,
                amount Float64,
                turn Float64,
                pct_chg Float64,
                source String,
                data_quality String
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(date)
            ORDER BY (code, date)
            TTL date + INTERVAL 5 YEAR
            SETTINGS index_granularity = 8192
        ''')
        
        # tick数据表
        self.client.execute('''
            CREATE TABLE IF NOT EXISTS stock_ticks (
                code String,
                timestamp DateTime64(3),
                price Float64,
                volume UInt64,
                side String,
                bid1 Float64,
                ask1 Float64,
                bid1_vol UInt64,
                ask1_vol UInt64
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMMDD(timestamp)
            ORDER BY (code, timestamp)
            TTL timestamp + INTERVAL 1 MONTH
        ''')
        
        # 因子数据表
        self.client.execute('''
            CREATE TABLE IF NOT EXISTS factor_data (
                code String,
                date Date,
                factor_name String,
                factor_value Float64,
                factor_category String
            ) ENGINE = MergeTree()
            PARTITION BY toYYYYMM(date)
            ORDER BY (factor_name, code, date)
        ''')
    
    def insert_price_data(self, df: pd.DataFrame, table: str = 'stock_daily'):
        """插入价格数据"""
        data = df.to_dict('records')
        
        self.client.execute(
            f"INSERT INTO {table} VALUES",
            data
        )
    
    def query_price_data(
        self,
        codes: List[str],
        start_date: str,
        end_date: str,
        fields: List[str] = None
    ) -> pd.DataFrame:
        """
        查询价格数据
        
        性能优化:
        - 分区裁剪
        - 列裁剪
        - 索引利用
        """
        fields_str = ', '.join(fields) if fields else '*'
        codes_str = ', '.join([f"'{c}'" for c in codes])
        
        query = f'''
            SELECT {fields_str}
            FROM stock_daily
            WHERE code IN ({codes_str})
              AND date >= '{start_date}'
              AND date <= '{end_date}'
            ORDER BY code, date
        '''
        
        result = self.client.execute(query, with_column_types=True)
        
        df = pd.DataFrame(result[0], columns=[c[0] for c in result[1]])
        return df
    
    def query_factor_data(
        self,
        factor_names: List[str],
        codes: List[str],
        date: str
    ) -> pd.DataFrame:
        """查询因子数据（截面）"""
        factors_str = ', '.join([f"'{f}'" for f in factor_names])
        codes_str = ', '.join([f"'{c}'" for c in codes])
        
        query = f'''
            SELECT code, factor_name, factor_value
            FROM factor_data
            WHERE factor_name IN ({factors_str})
              AND code IN ({codes_str})
              AND date = '{date}'
        '''
        
        result = self.client.execute(query, with_column_types=True)
        
        df = pd.DataFrame(result[0], columns=[c[0] for c in result[1]])
        return df.pivot(index='code', columns='factor_name', values='factor_value')


### 3.2.4 Kafka+Flink实时流处理

```python
# realtime_stream_processing.py
from kafka import KafkaProducer, KafkaConsumer
import json
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment
import asyncio


class RealtimeDataPipeline:
    """
    实时行情流处理管道
    
    Kafka + Flink架构
    """
    
    def __init__(
        self,
        kafka_bootstrap_servers: str = 'localhost:9092',
        flink_parallelism: int = 4
    ):
        self.kafka_servers = kafka_bootstrap_servers
        
        # Flink环境
        self.env = StreamExecutionEnvironment.get_execution_environment()
        self.env.set_parallelism(flink_parallelism)
        self.table_env = StreamTableEnvironment.create(self.env)
        
    def setup_kafka_topics(self):
        """设置Kafka主题"""
        self.topics = {
            'raw_ticks': 'stock-ticks-raw',      # 原始tick数据
            'processed_bars': 'stock-bars-processed',  # 处理后K线
            'factor_updates': 'factor-updates',   # 因子更新
            'signals': 'trading-signals',         # 交易信号
            'alerts': 'system-alerts'             # 系统告警
        }
    
    def create_flink_pipeline(self):
        """创建Flink处理管道"""
        
        # 读取Kafka流
        self.table_env.execute_sql('''
            CREATE TABLE tick_stream (
                code STRING,
                timestamp TIMESTAMP(3),
                price DOUBLE,
                volume BIGINT,
                side STRING,
                WATERMARK FOR timestamp AS timestamp - INTERVAL '5' SECOND
            ) WITH (
                'connector' = 'kafka',
                'topic' = 'stock-ticks-raw',
                'properties.bootstrap.servers' = 'localhost:9092',
                'format' = 'json'
            )
        ''')
        
        # 1分钟K线聚合
        self.table_env.execute_sql('''
            CREATE TABLE minute_bars (
                code STRING,
                window_start TIMESTAMP(3),
                open_price DOUBLE,
                high_price DOUBLE,
                low_price DOUBLE,
                close_price DOUBLE,
                volume BIGINT,
                PRIMARY KEY (code, window_start) NOT ENFORCED
            ) WITH (
                'connector' = 'jdbc',
                'url' = 'jdbc:clickhouse://localhost:8123/default',
                'table-name' = 'minute_bars'
            )
        ''')
        
        # 插入聚合结果
        self.table_env.execute_sql('''
            INSERT INTO minute_bars
            SELECT
                code,
                TUMBLE_START(timestamp, INTERVAL '1' MINUTE) as window_start,
                FIRST_VALUE(price) as open_price,
                MAX(price) as high_price,
                MIN(price) as low_price,
                LAST_VALUE(price) as close_price,
                SUM(volume) as volume
            FROM tick_stream
            GROUP BY
                code,
                TUMBLE(timestamp, INTERVAL '1' MINUTE)
        ''')


### 3.2.5 分层数据模型

```
分层数据架构 (ODS → DWD → DWS → ADS)

┌─────────────────────────────────────────────────────────┐
│  ADS (Application Data Store) 应用数据层                 │
│  - 策略回测结果表                                         │
│  - 实盘交易记录表                                         │
│  - 绩效归因报表                                          │
│  - 用户看板数据                                          │
└─────────────────────────────────────────────────────────┘
                            ↑
┌─────────────────────────────────────────────────────────┐
│  DWS (Data Warehouse Summary) 汇总数据层                 │
│  - 日K线汇总表                                          │
│  - 因子宽表 (多因子合并)                                  │
│  - 行业/板块统计表                                       │
│  - 策略信号表                                           │
└─────────────────────────────────────────────────────────┘
                            ↑
┌─────────────────────────────────────────────────────────┐
│  DWD (Data Warehouse Detail) 明细数据层                  │
│  - 清洗后的行情数据                                       │
│  - 标准化财务数据                                        │
│  - 清洗后的基本面数据                                     │
│  - 统一的代码映射表                                      │
└─────────────────────────────────────────────────────────┘
                            ↑
┌─────────────────────────────────────────────────────────┐
│  ODS (Operational Data Store) 原始数据层                 │
│  - Tushare原始数据                                       │
│  - Baostock原始数据                                      │
│  - 聚宽原始数据                                          │
│  - 其他数据源原始数据                                     │
│  - 日志数据                                             │
└─────────────────────────────────────────────────────────┘
```

---

*Module: Data Gateway - Multi-Source Fusion + Lakehouse*  
*Chapter: 3.2*  
*Status: 详细设计记录*
