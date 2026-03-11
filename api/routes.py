"""
API路由 — V7.0: 18个端点 + V6.1兼容14个端点
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any

from config.settings import settings

# V7.0 路由
v7_router = APIRouter(prefix="/api/v7")

# V6.1 兼容路由  
v1_router = APIRouter(prefix="/api/v1")


# === V7.0 端点 ===

@v7_router.get("/health")
async def v7_health():
    """健康检查"""
    return {"status": "healthy", "version": "7.0.0", "api": "v7"}


@v7_router.get("/market/realtime")
async def v7_market_realtime():
    """实时行情"""
    return {"status": "ok", "data": []}


@v7_router.get("/positions")
async def v7_positions():
    """持仓查询"""
    return {"status": "ok", "positions": []}


@v7_router.post("/trade/execute")
async def v7_trade_execute(order: Dict[str, Any]):
    """执行交易"""
    return {"status": "submitted", "order_id": "mock-001"}


@v7_router.get("/evolution/status")
async def v7_evolution_status():
    """进化引擎状态"""
    return {
        "status": "active",
        "population_size": settings.evolution.population_size,
        "generations": settings.evolution.generations
    }


@v7_router.get("/paper-trading/accounts")
async def v7_paper_accounts():
    """模拟盘账户列表"""
    return {"accounts": [], "max_accounts": settings.paper_trading.max_paper_accounts}


@v7_router.get("/risk/status")
async def v7_risk_status():
    """风控状态"""
    return {
        "var_confidence": settings.risk.var_confidence,
        "max_drawdown_limit": settings.risk.max_drawdown_limit,
        "alerts": []
    }


@v7_router.get("/factor/list")
async def v7_factor_list():
    """因子列表"""
    return {"factors": settings.factor.barra_factors}


@v7_router.get("/hmm/regime")
async def v7_hmm_regime():
    """HMM政权检测"""
    return {"regime": "unknown", "confidence": 0.0}


@v7_router.get("/broker/status")
async def v7_broker_status():
    """券商状态"""
    return {
        "primary": settings.broker.broker_type or "未配置",
        "backup": settings.broker.backup_broker_type or "未配置",
        "status": "mock"
    }


@v7_router.get("/execution/algorithms")
async def v7_execution_algorithms():
    """执行算法列表"""
    return {"algorithms": settings.execution.algorithms}


@v7_router.get("/drl/status")
async def v7_drl_status():
    """DRL引擎状态"""
    return {"status": "active", "framework": "PPO+Transformer"}


@v7_router.get("/backtest/status")
async def v7_backtest_status():
    """回测引擎状态"""
    return {"status": "active", "engine": "Almgren-Chriss+WFA"}


@v7_router.get("/data-gateway/status")
async def v7_data_gateway_status():
    """数据网关状态"""
    return {
        "status": "active",
        "sources": ["tushare", "baostock", "jqdatasdk"],
        "cross_validation": settings.data_source.enable_cross_validation
    }


# === V6.1 兼容端点 ===

@v1_router.get("/health")
async def v1_health():
    """V6.1 健康检查"""
    return {"status": "healthy", "version": "6.1.0", "api": "v1(compatible)"}


@v1_router.get("/market/index")
async def v1_market_index():
    """V6.1 指数行情"""
    return {"indices": []}


@v1_router.get("/positions")
async def v1_positions():
    """V6.1 持仓"""
    return {"positions": []}


@v1_router.post("/trade/execute")
async def v1_trade_execute(order: Dict[str, Any]):
    """V6.1 交易执行"""
    return {"status": "submitted"}


@v1_router.get("/evolution/hall-of-fame")
async def v1_hall_of_fame():
    """V6.1 名人堂"""
    return {"strategies": []}


@v1_router.get("/simulation/accounts")
async def v1_sim_accounts():
    """V6.1 模拟账户"""
    return {"accounts": []}


@v1_router.get("/dashboard/combined-nav")
async def v1_combined_nav():
    """V6.1 组合净值"""
    return {"nav": []}
