"""
KimiClaw V8.0 — 统一配置系统
整合10大子系统配置
"""

import os
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# ═══════════════════════════════════════════════════════════════
# 1. AI Gateway 配置
# ═══════════════════════════════════════════════════════════════

class ConsensusConfig(BaseModel):
    """AI共识配置"""
    mode: str = "majority_vote"  # majority_vote, weighted_vote, highest_confidence
    min_agreement_ratio: float = 0.6
    confidence_threshold: float = 0.7


class ModelConfig(BaseModel):
    """模型配置"""
    enabled: bool = True
    priority: int = 1
    timeout_seconds: float = 30.0
    max_tokens: int = 4096
    temperature: float = 0.7


class AIGatewayConfig(BaseModel):
    """AI网关配置"""
    # 模型配置
    models: Dict[str, ModelConfig] = Field(default_factory=lambda: {
        "kimi": ModelConfig(enabled=True, priority=1, timeout_seconds=30.0),
        "glm": ModelConfig(enabled=True, priority=2, timeout_seconds=30.0),
        "minimax": ModelConfig(enabled=True, priority=3, timeout_seconds=30.0),
        "gemini": ModelConfig(enabled=True, priority=4, timeout_seconds=30.0),
    })
    
    # 共识模式
    consensus: ConsensusConfig = ConsensusConfig()
    
    # 熔断器
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout: int = 60
    
    # 成本优化
    cost_optimization: bool = True
    token_budget_daily: int = 1_000_000


# ═══════════════════════════════════════════════════════════════
# 2. Agent系统配置
# ═══════════════════════════════════════════════════════════════

class AuctionConfig(BaseModel):
    """资金拍卖配置"""
    initial_capital_per_agent: float = 1_000_000.0
    commission_rate: float = 0.0003
    slippage_model: str = "almgren_chriss"
    min_allocation: float = 1000.0
    max_allocation_ratio: float = 0.3


class AdversarialConfig(BaseModel):
    """对抗测试配置"""
    enabled: bool = True
    epsilon: float = 0.05
    max_price_change: float = 0.10
    pgd_iterations: int = 20
    pgd_restarts: int = 5
    robustness_threshold: float = 0.70


class AgentSystemConfig(BaseModel):
    """Agent系统配置"""
    auction: AuctionConfig = AuctionConfig()
    adversarial: AdversarialConfig = AdversarialConfig()
    max_agents: int = 100
    evolution_interval_hours: int = 24


# ═══════════════════════════════════════════════════════════════
# 3. 回测配置
# ═══════════════════════════════════════════════════════════════

class BacktestConfig(BaseModel):
    """回测配置"""
    # A股特化
    enable_short_selling: bool = False
    strict_t1: bool = True
    session_matching: bool = True
    
    # 成本模型
    commission_rate: float = 0.0003
    stamp_duty_rate: float = 0.001
    transfer_fee_rate: float = 0.00002
    
    # 滑点
    slippage_model: str = "adaptive"
    base_slippage: float = 0.001


# ═══════════════════════════════════════════════════════════════
# 4. 执行配置
# ═══════════════════════════════════════════════════════════════

class ExecutionConfig(BaseModel):
    """执行配置"""
    # 订单簿监控
    order_book_depth: int = 10
    update_interval_ms: int = 100
    
    # 涨停队列分析
    limit_up_queue_analysis: bool = True
    cancel_rate_threshold: float = 0.3
    
    # 尾盘集合竞价
    auction_matching_enabled: bool = True
    auction_history_window: int = 20
    
    # RL自适应
    rl_adaptation_enabled: bool = True
    q_learning_rate: float = 0.1
    epsilon_greedy: float = 0.1


# ═══════════════════════════════════════════════════════════════
# 5. 合规配置
# ═══════════════════════════════════════════════════════════════

class ComplianceConfig(BaseModel):
    """合规配置"""
    # 程序化交易限制
    max_orders_per_second: int = 100
    max_cancel_ratio: float = 0.3
    
    # 内幕交易防控
    restricted_securities: List[str] = Field(default_factory=list)
    blackout_period_days: int = 30
    
    # 审计
    audit_retention_years: int = 20
    audit_enabled: bool = True


# ═══════════════════════════════════════════════════════════════
# 6. 因子生命周期配置
# ═══════════════════════════════════════════════════════════════

class FactorLifecycleConfig(BaseModel):
    """因子生命周期配置"""
    # IC阈值
    ic_candidate_threshold: float = 0.01
    ic_validation_threshold: float = 0.02
    ir_stable_threshold: float = 0.8
    ic_decay_monthly_threshold: float = 0.002
    ic_retirement_threshold: float = 0.005
    max_drawdown_retirement: float = 0.30
    
    # 容量估计
    capacity_almgren_gamma: float = 0.5
    capacity_max_positions: int = 100
    
    # 正交化
    orthogonalization_method: str = "gram_schmidt"
    min_pure_alpha_ratio: float = 0.70
    correlation_threshold: float = 0.3
    
    # 替代数据
    alternative_data_sources: List[str] = Field(default_factory=lambda: [
        "satellite", "ecommerce", "logistics", "job_postings", "supply_chain", "credit_card"
    ])


# ═══════════════════════════════════════════════════════════════
# 7. 风控配置
# ═══════════════════════════════════════════════════════════════

class RiskConfig(BaseModel):
    """风控配置"""
    # 熔断阈值
    circuit_breaker_levels: Dict[str, float] = Field(default_factory=lambda: {
        "level1_warning": -0.02,
        "level2_suspend_open": -0.03,
        "level3_force_reduce": -0.05,
        "level4_close_all": -0.15,
    })
    
    # 集中度限制
    single_stock_limit: float = 0.15
    industry_limit: float = 0.30
    style_limit: float = 0.25
    
    # 流动性
    liquidity_dried_up_threshold: int = 10000
    liquidity_scarce_threshold: int = 50000
    
    # 极端市场
    emergency_volatility_threshold: float = 0.05
    emergency_liquidity_threshold: float = 0.3
    emergency_sentiment_threshold: float = -0.5


# ═══════════════════════════════════════════════════════════════
# 8. 高级技术配置
# ═══════════════════════════════════════════════════════════════

class HDPHMMConfig(BaseModel):
    """HDP-HMM配置"""
    min_states: int = 3
    max_states: int = 8
    window_days: int = 252
    update_frequency_minutes: int = 60


class OnlineLearningConfig(BaseModel):
    """在线学习配置"""
    ftrl_learning_rate: float = 0.01
    ftrl_l1: float = 0.01
    ftrl_l2: float = 0.01
    ogd_learning_rate: float = 0.05
    maml_inner_lr: float = 0.01
    maml_outer_lr: float = 0.001
    maml_adaptation_steps: int = 5
    drift_method: str = "adwin"
    drift_threshold: float = 0.5


class LLMGNNConfig(BaseModel):
    """LLM-GNN配置"""
    max_graph_nodes: int = 500
    message_passing_steps: int = 3
    contagion_threshold: float = 0.3
    edge_decay_factor: float = 0.95


class RiskBudgetConfig(BaseModel):
    """风险预算配置"""
    account_risk_target: float = 0.15
    max_strategies: int = 20
    min_strategy_budget: float = 0.01
    max_strategy_budget: float = 0.10
    consumption_threshold: float = 0.80
    emergency_threshold: float = 0.95
    copula_model: str = "clayton"
    rebalance_frequency_days: int = 5


class AdvancedTechConfig(BaseModel):
    """高级技术配置"""
    hdp_hmm: HDPHMMConfig = HDPHMMConfig()
    online_learning: OnlineLearningConfig = OnlineLearningConfig()
    llm_gnn: LLMGNNConfig = LLMGNNConfig()
    risk_budget: RiskBudgetConfig = RiskBudgetConfig()


# ═══════════════════════════════════════════════════════════════
# 9. 可观测性配置
# ═══════════════════════════════════════════════════════════════

class ObservabilityConfig(BaseModel):
    """可观测性配置"""
    # 链路追踪
    tracing_enabled: bool = True
    service_name: str = "kimiclaw_v8"
    sample_rate: float = 1.0
    
    # SLO阈值(ms)
    slo_signal_generation: float = 100.0
    slo_risk_check: float = 50.0
    slo_order_routing: float = 100.0
    slo_broker_execution: float = 500.0
    
    # Prometheus
    prometheus_enabled: bool = True
    metrics_port: int = 8000
    
    # 告警
    alerting_enabled: bool = True
    alert_channels: List[str] = Field(default_factory=lambda: ["feishu", "sms"])
    anomaly_sensitivity: float = 2.0


# ═══════════════════════════════════════════════════════════════
# 10. 数据网关配置
# ═══════════════════════════════════════════════════════════════

class DataGatewayConfig(BaseModel):
    """数据网关配置"""
    # 数据源
    primary_source: str = "tushare"
    backup_sources: List[str] = Field(default_factory=lambda: ["akshare", "baostock"])
    
    # 缓存
    cache_ttl_seconds: int = 60
    cache_max_size: int = 10000
    
    # 限流
    rate_limit_per_minute: int = 60


# ═══════════════════════════════════════════════════════════════
# 主配置类
# ═══════════════════════════════════════════════════════════════

class SystemV8Config(BaseSettings):
    """
    KimiClaw V8.0 统一配置
    整合10大子系统
    """
    
    # 应用基础配置
    app_name: str = "KimiClaw V8.0"
    version: str = "8.0.0"
    debug: bool = Field(default=False, env="DEBUG")
    
    # API配置
    api_host: str = Field(default="0.0.0.0", env="API_HOST")
    api_port: int = Field(default=8000, env="API_PORT")
    
    # 10大子系统配置
    ai_gateway: AIGatewayConfig = AIGatewayConfig()
    agent_system: AgentSystemConfig = AgentSystemConfig()
    backtest: BacktestConfig = BacktestConfig()
    execution: ExecutionConfig = ExecutionConfig()
    compliance: ComplianceConfig = ComplianceConfig()
    factor_lifecycle: FactorLifecycleConfig = FactorLifecycleConfig()
    risk: RiskConfig = RiskConfig()
    advanced_tech: AdvancedTechConfig = AdvancedTechConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
    data_gateway: DataGatewayConfig = DataGatewayConfig()
    
    # 数据库配置
    database_url: Optional[str] = Field(default=None, env="DATABASE_URL")
    redis_url: Optional[str] = Field(default=None, env="REDIS_URL")
    clickhouse_url: Optional[str] = Field(default=None, env="CLICKHOUSE_URL")
    
    # API密钥
    tushare_token: Optional[str] = Field(default=None, env="TUSHARE_TOKEN")
    kimi_api_key: Optional[str] = Field(default=None, env="KIMI_API_KEY")
    glm_api_key: Optional[str] = Field(default=None, env="GLM_API_KEY")
    minimax_api_key: Optional[str] = Field(default=None, env="MINIMAX_API_KEY")
    gemini_api_key: Optional[str] = Field(default=None, env="GEMINI_API_KEY")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# 全局配置实例
settings_v8 = SystemV8Config()
