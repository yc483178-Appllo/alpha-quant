"""
Kimi Claw V7.0 — 全局配置
基于V6.1 + V7.0升级文档
部署地址: http://120.76.55.222/v3/ (dengdeng-trading.com)
"""
import os
from pydantic import BaseModel
from typing import Optional, Dict, List


class DatabaseConfig(BaseModel):
    """数据库配置 — V7.0升级: ClickHouse+PostgreSQL+Redis"""
    # ClickHouse 时序数据库(替代MongoDB)
    clickhouse_host: str = os.getenv("CH_HOST", "127.0.0.1")
    clickhouse_port: int = int(os.getenv("CH_PORT", "9000"))
    clickhouse_db: str = os.getenv("CH_DB", "kimi_claw")
    clickhouse_user: str = os.getenv("CH_USER", "default")
    clickhouse_password: str = os.getenv("CH_PASSWORD", "")

    # PostgreSQL 业务数据库
    pg_host: str = os.getenv("PG_HOST", "127.0.0.1")
    pg_port: int = int(os.getenv("PG_PORT", "5432"))
    pg_db: str = os.getenv("PG_DB", "kimi_claw")
    pg_user: str = os.getenv("PG_USER", "postgres")
    pg_password: str = os.getenv("PG_PASSWORD", "")

    # Redis 缓存 + Agent消息总线
    redis_host: str = os.getenv("REDIS_HOST", "127.0.0.1")
    redis_port: int = int(os.getenv("REDIS_PORT", "6379"))
    redis_db: int = int(os.getenv("REDIS_DB", "0"))
    redis_password: str = os.getenv("REDIS_PASSWORD", "")

    @property
    def clickhouse_url(self) -> str:
        return f"clickhouse://{self.clickhouse_user}:{self.clickhouse_password}@{self.clickhouse_host}:{self.clickhouse_port}/{self.clickhouse_db}"

    @property
    def pg_url(self) -> str:
        return f"postgresql://{self.pg_user}:{self.pg_password}@{self.pg_host}:{self.pg_port}/{self.pg_db}"


class DataSourceConfig(BaseModel):
    """数据源配置 — V7.0: 多源交叉校验"""
    tushare_token: str = os.getenv("TUSHARE_TOKEN", "")
    jq_user: str = os.getenv("JQ_USER", "")
    jq_password: str = os.getenv("JQ_PASSWORD", "")
    # Baostock 无需token

    # 数据源优先级
    primary_source: str = "tushare"
    secondary_source: str = "baostock"
    tertiary_source: str = "jqdatasdk"
    enable_cross_validation: bool = True


class KafkaConfig(BaseModel):
    """Kafka 实时流配置"""
    bootstrap_servers: str = os.getenv("KAFKA_SERVERS", "127.0.0.1:9092")
    topics: Dict[str, str] = {
        "market_tick": "kimi.market.tick",
        "signals": "kimi.strategy.signals",
        "orders": "kimi.execution.orders",
        "risk_alerts": "kimi.risk.alerts",
        "agent_messages": "kimi.agent.messages",
    }


class BrokerConfig(BaseModel):
    """券商接口配置 — V7.0: 统一API抽象层"""
    broker_type: str = os.getenv("BROKER_TYPE", "ptrade")  # ptrade/qmt/eastmoney/ths/ctp
    broker_host: str = os.getenv("BROKER_HOST", "")
    broker_port: int = int(os.getenv("BROKER_PORT", "0"))
    broker_account: str = os.getenv("BROKER_ACCOUNT", "")
    broker_password: str = os.getenv("BROKER_PASSWORD", "")

    # 备用券商(双活)
    backup_broker_type: str = os.getenv("BACKUP_BROKER_TYPE", "")
    backup_broker_host: str = os.getenv("BACKUP_BROKER_HOST", "")


class TradingConfig(BaseModel):
    """交易规则配置 — A股规则全适配"""
    # T+1规则
    t_plus_1: bool = True
    # 涨跌停限制
    main_board_limit: float = 0.10     # 主板±10%
    gem_board_limit: float = 0.20      # 创业板/科创板±20%
    st_limit: float = 0.05             # ST股±5%
    # 最小交易单位
    min_lot_size: int = 100            # 100股整手
    # 交易费用
    commission_rate: float = 0.0003    # 佣金费率(万三)
    stamp_tax_rate: float = 0.001      # 印花税(千一, 仅卖出)
    transfer_fee_rate: float = 0.00002 # 过户费
    # 基准
    benchmarks: List[str] = ["000300.SH", "000905.SH"]  # CSI300, CSI500

    # 交易时段
    morning_open: str = "09:30"
    morning_close: str = "11:30"
    afternoon_open: str = "13:00"
    afternoon_close: str = "15:00"
    call_auction_am: str = "09:15-09:25"
    call_auction_pm: str = "14:57-15:00"


class RiskConfig(BaseModel):
    """风控配置"""
    # VaR参数
    var_confidence: float = 0.95
    var_window: int = 252
    # 最大回撤限制
    max_drawdown_warning: float = 0.05
    max_drawdown_limit: float = 0.10
    # 持仓集中度
    max_single_stock_weight: float = 0.10  # 单股最大10%
    max_industry_weight: float = 0.30       # 单行业最大30%
    # 止损
    single_stock_stop_loss: float = 0.08


class EvolutionConfig(BaseModel):
    """进化引擎配置 — V7.0: NSGA-III"""
    population_size: int = 200
    generations: int = 100
    objectives: List[str] = [
        "sharpe", "calmar", "win_rate", "capacity",
        "max_drawdown", "turnover", "downside_vol"
    ]
    # 过拟合惩罚
    in_out_sample_gap_weight: float = 0.3
    param_count_weight: float = 0.1
    backtest_length_weight: float = 0.1
    # 小生境多样性
    style_diversity: List[str] = [
        "momentum", "mean_reversion", "ml", "event", "drl"
    ]


class FactorConfig(BaseModel):
    """因子引擎配置"""
    # GP遗传编程
    gp_population: int = 500
    gp_generations: int = 100
    gp_operators: List[str] = [
        "add", "sub", "mul", "div", "rank",
        "ts_mean", "ts_std", "ts_corr", "delay", "delta"
    ]
    # Optuna AutoML
    optuna_n_trials: int = 1000
    optuna_timeout: int = 3600
    # IC阈值
    ic_threshold: float = 0.03
    icir_threshold: float = 0.5
    # Barra CNE6
    barra_factors: List[str] = [
        "size", "beta", "momentum", "residual_vol",
        "non_linear_size", "book_to_price", "liquidity",
        "earnings_yield", "growth", "leverage"
    ]


class ExecutionConfig(BaseModel):
    """执行算法配置"""
    default_algorithm: str = "adaptive_twap"
    algorithms: List[str] = [
        "twap", "vwap", "pov", "iceberg", "sniper", "adaptive_twap"
    ]
    # 滑点模型
    slippage_mode: str = "volume_adaptive"
    depth_levels: int = 5
    # Almgren-Chriss冲击模型
    permanent_impact: float = 0.1
    temporary_impact: float = 0.3


class PaperTradingConfig(BaseModel):
    """仿真交易配置 — V6.1多账户"""
    max_paper_accounts: int = 10
    # 灰度发布
    graduation_conditions: Dict[str, float] = {
        "min_sharpe": 1.0,
        "max_drawdown": 0.10,
        "min_days": 30,
        "confidence_level": 0.95,  # Bayesian A/B Testing
    }
    # 灰度阶段
    stages: List[Dict] = [
        {"name": "仿真验证", "allocation": 0.0},
        {"name": "小资金实盘", "allocation": 0.10},
        {"name": "半量实盘", "allocation": 0.30},
        {"name": "全量上线", "allocation": 1.0},
    ]


class HMMConfig(BaseModel):
    """HMM政权检测配置 — V7.0: 多特征多尺度"""
    n_regimes: int = 4  # 默认4种政权
    features: List[str] = [
        "returns", "volatility", "turnover",
        "north_flow", "option_iv", "term_spread"
    ]
    # 多尺度
    time_scales: List[str] = ["daily", "hourly", "minute"]
    # 在线增量更新
    online_update: bool = True
    sliding_window: int = 60


class APIConfig(BaseModel):
    """API配置"""
    host: str = "0.0.0.0"
    port: int = 8000
    api_prefix: str = "/api"
    cors_origins: List[str] = ["*"]
    # V7.0 API版本
    v7_prefix: str = "/api/v7"
    # V6.1 API版本(兼容)
    v1_prefix: str = "/api/v1"


class SystemConfig(BaseModel):
    """V7.0 系统总配置"""
    version: str = "7.0.0"
    name: str = "Kimi Claw A股量化交易系统"
    deploy_url: str = "http://120.76.55.222/v3/"
    domain: str = "dengdeng-trading.com"

    # 子配置
    database: DatabaseConfig = DatabaseConfig()
    data_source: DataSourceConfig = DataSourceConfig()
    kafka: KafkaConfig = KafkaConfig()
    broker: BrokerConfig = BrokerConfig()
    trading: TradingConfig = TradingConfig()
    risk: RiskConfig = RiskConfig()
    evolution: EvolutionConfig = EvolutionConfig()
    factor: FactorConfig = FactorConfig()
    execution: ExecutionConfig = ExecutionConfig()
    paper_trading: PaperTradingConfig = PaperTradingConfig()
    hmm: HMMConfig = HMMConfig()
    api: APIConfig = APIConfig()

    # 模式
    api_mode: str = os.getenv("API_MODE", "mock")  # mock / live
    debug: bool = os.getenv("DEBUG", "true").lower() == "true"
    log_level: str = os.getenv("LOG_LEVEL", "INFO")


# 全局配置单例
settings = SystemConfig()
