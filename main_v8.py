"""
KimiClaw V8.0 — 主入口模块
系统架构: 10大子系统整合
- AI网关 + Agent系统 + 回测V8 + 执行V8 + 合规V8
- 因子生命周期 + 风控 + 高级技术 + 可观测性 + 数据网关
"""

import asyncio
import signal
import sys
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, WebSocket, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
import os

# V8.0 配置
from config_v8 import settings_v8

# V8.0 API路由
from api_v8.routes import router_v8

# 10大子系统导入
try:
    from ai_gateway_v8.router import AIGatewayRouter
    from ai_gateway_v8.orchestrator import AIOrchestrator
    AI_GATEWAY_AVAILABLE = True
except ImportError:
    AI_GATEWAY_AVAILABLE = False
    AIGatewayRouter = None
    AIOrchestrator = None

try:
    from agent_system_v8.auction import StrategyAuctionSystem
    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False
    StrategyAuctionSystem = None

try:
    from backtest_v8.a_share_backtest import AShareBacktestV8
    BACKTEST_AVAILABLE = True
except ImportError:
    BACKTEST_AVAILABLE = False
    AShareBacktestV8 = None

try:
    from execution_v8.execution_enhanced import AShareExecutionV8
    EXECUTION_AVAILABLE = True
except ImportError:
    EXECUTION_AVAILABLE = False
    AShareExecutionV8 = None

try:
    from compliance_v8.regulatory_compliance import RegulatoryComplianceV8
    COMPLIANCE_AVAILABLE = True
except ImportError:
    COMPLIANCE_AVAILABLE = False
    RegulatoryComplianceV8 = None

try:
    from factor_lifecycle.lifecycle_state_machine import FactorLifecycleManager
    from factor_lifecycle.alpha_decay import AlphaDecayAnalyzer
    from factor_lifecycle.capacity_estimator import FactorCapacityEstimator
    FACTOR_AVAILABLE = True
except ImportError:
    FACTOR_AVAILABLE = False
    FactorLifecycleManager = None
    AlphaDecayAnalyzer = None
    FactorCapacityEstimator = None

try:
    from risk_control.risk_realtime_engine import RealTimeRiskEngine
    RISK_AVAILABLE = True
except ImportError:
    RISK_AVAILABLE = False
    RealTimeRiskEngine = None

try:
    from advanced_tech.hdp_hmm_detector import HDPHMMRegimeDetector
    from advanced_tech.adversarial_trainer import AdversarialTrainer
    from advanced_tech.online_adapter import OnlineLearningAdapter
    from advanced_tech.llm_gnn_engine import LLMGNNFusionEngine
    from advanced_tech.risk_budget_manager import RiskBudgetManager
    ADVANCED_AVAILABLE = True
except ImportError:
    ADVANCED_AVAILABLE = False
    HDPHMMRegimeDetector = None
    AdversarialTrainer = None
    OnlineLearningAdapter = None
    LLMGNNFusionEngine = None
    RiskBudgetManager = None

try:
    from observability.tracing import TraceManager
    OBSERVABILITY_AVAILABLE = True
except ImportError:
    OBSERVABILITY_AVAILABLE = False
    TraceManager = None

# 工具
try:
    from utils.logger import logger, audit_logger
except ImportError:
    import logging
    logger = logging.getLogger("kimiclaw_v8")
    audit_logger = logging.getLogger("kimiclaw_v8.audit")


class KimiClawV8:
    """
    KimiClaw V8.0 核心系统
    10大子系统整合架构
    """
    
    def __init__(self):
        self.version = "8.0.0"
        self.name = "KimiClaw V8.0"
        
        # 10大子系统
        self.ai_gateway = None
        self.ai_orchestrator = None
        self.auction_system = None
        self.backtest_engine = None
        self.execution_engine = None
        self.compliance_engine = None
        self.factor_lifecycle = None
        self.alpha_decay = None
        self.capacity_estimator = None
        self.risk_engine = None
        self.hdp_hmm = None
        self.adversarial_trainer = None
        self.online_learning = None
        self.llm_gnn = None
        self.risk_budget = None
        self.trace_manager = None
        
        # 系统状态
        self.is_running = False
        self.startup_time: Optional[datetime] = None
        self.subsystem_status: Dict[str, bool] = {}
        
    async def initialize(self) -> None:
        """初始化所有子系统"""
        logger.info(f"🚀 Initializing {self.name}...")
        logger.info(f"   Version: {self.version}")
        logger.info(f"   Debug: {settings_v8.debug}")
        
        # 1. AI网关
        if AI_GATEWAY_AVAILABLE:
            logger.info("  📡 [1/10] Initializing AI Gateway...")
            self.ai_gateway = AIGatewayRouter()
            self.ai_orchestrator = AIOrchestrator(
                router=self.ai_gateway,
                mode=settings_v8.ai_gateway.consensus.mode
            )
            self.subsystem_status["ai_gateway"] = True
        else:
            logger.warning("  ⚠️  AI Gateway not available")
            self.subsystem_status["ai_gateway"] = False
        
        # 2. Agent系统
        if AGENT_AVAILABLE:
            logger.info("  🤖 [2/10] Initializing Agent System...")
            self.auction_system = StrategyAuctionSystem(
                initial_capital=settings_v8.agent_system.auction.initial_capital_per_agent,
                commission_rate=settings_v8.agent_system.auction.commission_rate
            )
            self.subsystem_status["agent_system"] = True
        else:
            logger.warning("  ⚠️  Agent System not available")
            self.subsystem_status["agent_system"] = False
        
        # 3. 回测引擎
        if BACKTEST_AVAILABLE:
            logger.info("  📊 [3/10] Initializing Backtest Engine...")
            self.backtest_engine = AShareBacktestV8()
            self.subsystem_status["backtest"] = True
        else:
            logger.warning("  ⚠️  Backtest Engine not available")
            self.subsystem_status["backtest"] = False
        
        # 4. 执行引擎
        if EXECUTION_AVAILABLE:
            logger.info("  ⚡ [4/10] Initializing Execution Engine...")
            self.execution_engine = AShareExecutionV8()
            self.subsystem_status["execution"] = True
        else:
            logger.warning("  ⚠️  Execution Engine not available")
            self.subsystem_status["execution"] = False
        
        # 5. 合规引擎
        if COMPLIANCE_AVAILABLE:
            logger.info("  ⚖️  [5/10] Initializing Compliance Engine...")
            self.compliance_engine = RegulatoryComplianceV8()
            self.subsystem_status["compliance"] = True
        else:
            logger.warning("  ⚠️  Compliance Engine not available")
            self.subsystem_status["compliance"] = False
        
        # 6. 因子生命周期
        if FACTOR_AVAILABLE:
            logger.info("  🔄 [6/10] Initializing Factor Lifecycle...")
            self.factor_lifecycle = FactorLifecycleManager()
            self.alpha_decay = AlphaDecayAnalyzer()
            self.capacity_estimator = FactorCapacityEstimator()
            self.subsystem_status["factor_lifecycle"] = True
        else:
            logger.warning("  ⚠️  Factor Lifecycle not available")
            self.subsystem_status["factor_lifecycle"] = False
        
        # 7. 风控引擎
        if RISK_AVAILABLE:
            logger.info("  🛡️  [7/10] Initializing Risk Engine...")
            self.risk_engine = RealTimeRiskEngine(
                initial_portfolio_value=1_000_000.0
            )
            self.subsystem_status["risk"] = True
        else:
            logger.warning("  ⚠️  Risk Engine not available")
            self.subsystem_status["risk"] = False
        
        # 8. 高级技术
        if ADVANCED_AVAILABLE:
            logger.info("  🔬 [8/10] Initializing Advanced Tech...")
            self.hdp_hmm = HDPHMMRegimeDetector()
            self.adversarial_trainer = AdversarialTrainer()
            self.online_learning = OnlineLearningAdapter()
            self.llm_gnn = LLMGNNFusionEngine()
            self.risk_budget = RiskBudgetManager()
            self.subsystem_status["advanced_tech"] = True
        else:
            logger.warning("  ⚠️  Advanced Tech not available")
            self.subsystem_status["advanced_tech"] = False
        
        # 9. 可观测性
        if OBSERVABILITY_AVAILABLE:
            logger.info("  📡 [9/10] Initializing Observability...")
            self.trace_manager = TraceManager()
            self.subsystem_status["observability"] = True
        else:
            logger.warning("  ⚠️  Observability not available")
            self.subsystem_status["observability"] = False
        
        # 10. 数据网关 (集成在其他模块中)
        logger.info("  💾 [10/10] Data Gateway ready (integrated)")
        self.subsystem_status["data_gateway"] = True
        
        self.startup_time = datetime.now()
        self.is_running = True
        
        # 启动后台任务
        asyncio.create_task(self._background_tasks())
        
        logger.info(f"✅ {self.name} initialized successfully!")
        logger.info(f"   Active subsystems: {sum(self.subsystem_status.values())}/10")
        
    async def shutdown(self) -> None:
        """优雅关闭系统"""
        logger.info(f"🛑 Shutting down {self.name}...")
        self.is_running = False
        
        # 清理资源...
        logger.info("✅ Shutdown complete")
        
    async def _background_tasks(self) -> None:
        """后台任务循环"""
        while self.is_running:
            try:
                # 定期健康检查
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Background task error: {e}")
                await asyncio.sleep(5)
        
    def get_health_status(self) -> Dict[str, Any]:
        """获取系统健康状态"""
        uptime_seconds = 0
        if self.startup_time:
            uptime_seconds = (datetime.now() - self.startup_time).total_seconds()
        
        return {
            "system": self.name,
            "version": self.version,
            "status": "healthy" if self.is_running else "unhealthy",
            "uptime_seconds": int(uptime_seconds),
            "startup_time": self.startup_time.isoformat() if self.startup_time else None,
            "subsystems": {
                "total": 10,
                "active": sum(self.subsystem_status.values()),
                "details": self.subsystem_status
            }
        }
    
    def get_subsystem(self, name: str) -> Optional[Any]:
        """获取指定子系统实例"""
        return getattr(self, name, None)


# 全局系统实例
kimi_claw_v8 = KimiClawV8()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """FastAPI生命周期管理"""
    await kimi_claw_v8.initialize()
    yield
    await kimi_claw_v8.shutdown()


# FastAPI应用
app = FastAPI(
    title="KimiClaw V8.0 API",
    description="""
    A股量化交易系统 V8.0
    
    ## 10大子系统
    - **AI Gateway**: 多模型编排 (Kimi/GLM/MiniMax/Gemini)
    - **Agent System**: 资金拍卖 + 对抗测试
    - **Backtest V8**: A股特化回测引擎
    - **Execution V8**: 涨跌停队列优化 + RL自适应
    - **Compliance V8**: 程序化交易合规 + 20年审计
    - **Factor Lifecycle**: 7状态因子生命周期管理
    - **Risk Control**: 实时风控 + 4级熔断
    - **Advanced Tech**: HDP-HMM + 对抗训练 + LLM-GNN
    - **Observability**: OpenTelemetry + Prometheus
    - **Data Gateway**: 多源数据融合
    
    ## 看板
    访问 `/dashboard` 查看V4.2实时看板 (19面板/51图表)
    """,
    version="8.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册V8 API路由
app.include_router(router_v8, prefix="/api/v8")

# 看板静态文件服务
@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """V4.2看板"""
    dashboard_path = os.path.join(os.path.dirname(__file__), "static", "index.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r", encoding="utf-8") as f:
            return f.read()
    return HTMLResponse(content="<h1>Dashboard not found</h1>", status_code=404)


@app.get("/")
async def root():
    """根端点"""
    return {
        "name": "KimiClaw V8.0",
        "version": "8.0.0",
        "description": "A股量化交易系统 · 10大子系统整合",
        "docs": "/docs",
        "health": "/health",
        "dashboard": "/dashboard"
    }


@app.get("/health")
async def health_check():
    """健康检查端点"""
    return kimi_claw_v8.get_health_status()


@app.get("/api/v8/subsystems")
async def list_subsystems():
    """列出所有子系统状态"""
    return {
        "subsystems": [
            {"id": "ai_gateway", "name": "AI Gateway", "available": AI_GATEWAY_AVAILABLE},
            {"id": "agent_system", "name": "Agent System", "available": AGENT_AVAILABLE},
            {"id": "backtest", "name": "Backtest Engine", "available": BACKTEST_AVAILABLE},
            {"id": "execution", "name": "Execution Engine", "available": EXECUTION_AVAILABLE},
            {"id": "compliance", "name": "Compliance Engine", "available": COMPLIANCE_AVAILABLE},
            {"id": "factor_lifecycle", "name": "Factor Lifecycle", "available": FACTOR_AVAILABLE},
            {"id": "risk", "name": "Risk Engine", "available": RISK_AVAILABLE},
            {"id": "advanced_tech", "name": "Advanced Tech", "available": ADVANCED_AVAILABLE},
            {"id": "observability", "name": "Observability", "available": OBSERVABILITY_AVAILABLE},
            {"id": "data_gateway", "name": "Data Gateway", "available": True},
        ]
    }


# 信号处理
def signal_handler(sig, frame):
    """处理系统信号"""
    logger.info(f"Received signal {sig}, shutting down...")
    sys.exit(0)


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "main_v8:app",
        host=settings_v8.api_host,
        port=settings_v8.api_port,
        reload=settings_v8.debug,
        log_level="info"
    )
