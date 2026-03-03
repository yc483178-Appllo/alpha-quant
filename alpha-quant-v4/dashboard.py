#!/usr/bin/env python3
"""
Alpha Quant v4.0 - 系统数据看板
FastAPI + WebSocket 实时数据展示
"""

import os
import json
import asyncio
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from loguru import logger
import akshare as ak
import redis

app = FastAPI(title="Alpha Quant v4.0 Dashboard", version="4.0.0")

# 静态文件目录
os.makedirs("static", exist_ok=True)

# Redis连接
try:
    redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"))
    redis_client.ping()
    redis_connected = True
except:
    redis_connected = False
    logger.warning("Redis未连接，看板将使用模拟数据")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """主看板页面"""
    return HTMLResponse(content=DASHBOARD_HTML)

@app.get("/api/market/snapshot")
async def market_snapshot():
    """获取市场快照"""
    try:
        # 获取指数数据
        df = ak.stock_zh_index_spot()
        indices = {}
        for _, row in df.iterrows():
            code = row.get("代码", "")
            if code == "000001":
                indices["sh"] = {"name": "上证指数", "price": row.get("最新价", 0), "change": row.get("涨跌幅", 0)}
            elif code == "399001":
                indices["sz"] = {"name": "深证成指", "price": row.get("最新价", 0), "change": row.get("涨跌幅", 0)}
            elif code == "399006":
                indices["cy"] = {"name": "创业板指", "price": row.get("最新价", 0), "change": row.get("涨跌幅", 0)}
            elif code == "000688":
                indices["kc"] = {"name": "科创50", "price": row.get("最新价", 0), "change": row.get("涨跌幅", 0)}
        
        return {
            "timestamp": datetime.now().isoformat(),
            "indices": indices,
            "redis_connected": redis_connected
        }
    except Exception as e:
        logger.error(f"获取市场数据失败: {e}")
        return {"error": str(e)}

@app.get("/api/agents/status")
async def agents_status():
    """获取Agent状态"""
    return {
        "Chief": {"status": "online", "task": "监控中"},
        "Scout": {"status": "online", "task": "盘前调研"},
        "Picker": {"status": "idle", "task": "等待选股"},
        "Guard": {"status": "online", "task": "风控监控"},
        "Trader": {"status": "idle", "task": "等待指令"},
        "Review": {"status": "idle", "task": "等待复盘"}
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket实时数据推送"""
    await websocket.accept()
    try:
        while True:
            # 推送实时数据
            data = {
                "timestamp": datetime.now().isoformat(),
                "type": "heartbeat",
                "message": "系统运行正常"
            }
            await websocket.send_json(data)
            await asyncio.sleep(5)
    except WebSocketDisconnect:
        logger.info("WebSocket连接断开")

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Alpha Quant v4.0 Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0a0e27;
            color: #fff;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1f3a 0%, #0a0e27 100%);
            padding: 20px 30px;
            border-bottom: 1px solid #2a3f5f;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .header h1 {
            font-size: 24px;
            background: linear-gradient(90deg, #00d4ff, #7b2cbf);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .container {
            padding: 20px 30px;
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
        }
        .card {
            background: linear-gradient(135deg, #1a1f3a 0%, #0f1429 100%);
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #2a3f5f;
        }
        .card-title {
            font-size: 12px;
            color: #8892b0;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 10px;
        }
        .card-value {
            font-size: 32px;
            font-weight: 700;
        }
        .positive { color: #00d4a0; }
        .negative { color: #ff4757; }
    </style>
</head>
<body>
    <div class="header">
        <h1>⚡ Alpha Quant v4.0 Dashboard</h1>
        <div style="color: #00d4ff;">系统运行中</div>
    </div>
    <div class="container">
        <div class="card">
            <div class="card-title">上证指数</div>
            <div class="card-value" id="sh">加载中...</div>
        </div>
        <div class="card">
            <div class="card-title">深证成指</div>
            <div class="card-value" id="sz">加载中...</div>
        </div>
        <div class="card">
            <div class="card-title">创业板指</div>
            <div class="card-value" id="cy">加载中...</div>
        </div>
        <div class="card">
            <div class="card-title">科创50</div>
            <div class="card-value" id="kc">加载中...</div>
        </div>
    </div>
    <script>
        async function fetchData() {
            try {
                const res = await fetch('/api/market/snapshot');
                const data = await res.json();
                if (data.indices) {
                    for (const [key, value] of Object.entries(data.indices)) {
                        const el = document.getElementById(key);
                        if (el) {
                            el.textContent = value.price.toFixed(2);
                            el.className = 'card-value ' + (value.change >= 0 ? 'positive' : 'negative');
                        }
                    }
                }
            } catch (e) {
                console.error('获取数据失败:', e);
            }
        }
        fetchData();
        setInterval(fetchData, 5000);
    </script>
</body>
</html>
"""

if __name__ == "__main__":
    import uvicorn
    print("🚀 启动 Alpha Quant v4.0 Dashboard")
    print("📊 访问地址: http://localhost:8080")
    uvicorn.run(app, host="0.0.0.0", port=8080)
