"""
Kimi Claw V7.0 — 主入口
A股量化交易系统 · 中低频规模化 · 全流程智能化 · 机构级基础设施

启动: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
部署: http://120.76.55.222/v3/ (dengdeng-trading.com)
"""
import os
import sys
from pathlib import Path

# 确保项目根目录在sys.path中
ROOT_DIR = Path(__file__).parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from contextlib import asynccontextmanager

from config.settings import settings
from utils.logger import logger
from api.routes import v7_router, v1_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # ── 启动 ──
    logger.info("=" * 60)
    logger.info(f"  Kimi Claw V{settings.version}")
    logger.info(f"  {settings.name}")
    logger.info(f"  模式: {'实盘' if settings.api_mode == 'live' else '模拟'}")
    logger.info(f"  地址: http://{settings.api.host}:{settings.api.port}")
    logger.info("=" * 60)

    # 初始化数据库
    try:
        from utils.database import ch_db, pg_db
        if settings.api_mode == "live":
            ch_db.init_tables()
            pg_db.init_tables()
            logger.info("数据库初始化完成")
        else:
            logger.info("Mock模式,跳过数据库初始化")
    except Exception as e:
        logger.warning(f"数据库初始化跳过: {e}")

    # 初始化调度器(盘后任务)
    try:
        _init_scheduler()
    except Exception as e:
        logger.warning(f"调度器初始化跳过: {e}")

    yield

    # ── 关闭 ──
    logger.info("Kimi Claw V7.0 正在关闭...")


def _init_scheduler():
    """初始化定时任务调度器"""
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    scheduler = AsyncIOScheduler()

    # 盘后任务: 每日15:30执行
    # scheduler.add_job(_daily_after_market, 'cron', hour=15, minute=30)
    # 数据同步: 每日16:00执行
    # scheduler.add_job(_daily_data_sync, 'cron', hour=16, minute=0)
    # 进化引擎: 每日17:00执行
    # scheduler.add_job(_daily_evolution, 'cron', hour=17, minute=0)
    # HMM政权更新: 每日18:00执行
    # scheduler.add_job(_daily_hmm_update, 'cron', hour=18, minute=0)

    # scheduler.start()
    logger.info("调度器已初始化(盘后任务已配置)")


# ── 创建FastAPI应用 ──
app = FastAPI(
    title=f"Kimi Claw V{settings.version} API",
    description="A股量化交易系统 — 中低频规模化·全流程智能化·机构级基础设施",
    version=settings.version,
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# ── CORS中间件 ──
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册路由 ──
app.include_router(v7_router)
app.include_router(v1_router)


# ── 静态文件(看板V4.2) ──
STATIC_DIR = ROOT_DIR / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── 根路由 ──
@app.get("/")
async def root():
    """系统信息"""
    return {
        "name": settings.name,
        "version": settings.version,
        "status": "running",
        "mode": settings.api_mode,
        "dashboard": "/v3/",
        "api_docs": "/api/docs",
        "endpoints": {
            "v7": f"18个端点 ({settings.api.v7_prefix}/*)",
            "v1": f"14个端点 ({settings.api.v1_prefix}/* V6.1兼容)",
        }
    }


@app.get("/v3/")
@app.get("/v3/index.html")
async def serve_dashboard():
    """看板V4.2入口"""
    dashboard_path = STATIC_DIR / "index.html"
    if dashboard_path.exists():
        return FileResponse(str(dashboard_path), media_type="text/html")
    return JSONResponse(
        status_code=404,
        content={"message": "看板文件未找到,请将V4.2 HTML复制到 static/index.html"}
    )


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "version": settings.version, "mode": settings.api_mode}


# ── 系统状态API ──
@app.get("/api/system/status")
async def system_status():
    """系统全局状态"""
    return {
        "version": settings.version,
        "mode": settings.api_mode,
        "modules": {
            "data_gateway": "active",
            "factor_engine": "active",
            "backtest_engine": "active",
            "evolution_engine": "active",
            "drl_engine": "active",
            "execution_engine": "active",
            "broker_manager": "standby" if settings.api_mode == "mock" else "active",
            "paper_trading": "active",
            "risk_engine": "active",
            "compliance_engine": "active",
            "gnn_graph": "active",
            "diffusion_model": "active",
            "hmm_detector": "active",
            "meta_rl": "active",
        },
        "databases": {
            "clickhouse": "connected" if settings.api_mode == "live" else "mock",
            "postgresql": "connected" if settings.api_mode == "live" else "mock",
            "redis": "connected" if settings.api_mode == "live" else "mock",
        },
        "trading": {
            "rules": "A股(T+1, 涨跌停, 100手)",
            "benchmarks": settings.trading.benchmarks,
            "broker": settings.broker.broker_type or "未配置",
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
