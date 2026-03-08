"""
历史知识库 - V6.0 新增模块
文件: historical_knowledge_base.py
功能: 策略绩效归档、交易模式挖掘、市场政权数据库、可搜索历史数据
依赖: pymongo, numpy, pandas, hmmlearn
"""

import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict

try:
    from pymongo import MongoClient
except ImportError:
    MongoClient = None

logger = logging.getLogger("HistoricalKnowledgeBase")


@dataclass
class TradeRecord:
    """标准化交易记录"""
    id: str
    stock_code: str
    stock_name: str
    action: str               # BUY / SELL
    price: float
    quantity: int
    amount: float
    signal_source: str        # 信号来源（Chief/DRL/Sentiment等）
    strategy_type: str        # 策略类型
    sentiment_score: float    # 当时情绪分
    market_regime: str        # 当时市场政权
    execution_time: str
    pnl: float = 0.0          # 盈亏（仅SELL时有值）
    pnl_pct: float = 0.0
    holding_days: int = 0


@dataclass
class MarketRegime:
    """市场政权快照"""
    date: str
    regime: str               # bull / bear / range / crisis
    confidence: float         # HMM置信度
    features: Dict            # 特征向量（指数收益率、波动率、换手率等）
    dominant_sectors: List[str]  # 主力板块


class HistoricalKnowledgeBase:
    """
    历史知识库主类
    功能: 存储/查询/挖掘历史交易数据和市场政权数据
    """
    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            cfg = json.load(f)
        kb_cfg = cfg.get("historical_kb", {})
        mongo_url = kb_cfg.get("mongodb_url", "mongodb://localhost:27017/kimi_claw")
        try:
            if MongoClient is None:
                raise ImportError("pymongo未安装")
            client = MongoClient(mongo_url, serverSelectionTimeoutMS=3000)
            client.server_info()
            self.db = client.kimi_claw
            self.available = True
            # 创建索引
            self.db.trades.create_index([("stock_code", 1), ("execution_time", -1)])
            self.db.trades.create_index([("strategy_type", 1)])
            self.db.market_regimes.create_index([("date", -1)], unique=True)
            logger.info("历史知识库 MongoDB 连接成功")
        except Exception as e:
            logger.warning(f"MongoDB不可用，使用JSON文件存储: {e}")
            self.available = False
            self.data_dir = kb_cfg.get("data_dir", "./data/knowledge_base")
            os.makedirs(self.data_dir, exist_ok=True)

    # ── 交易记录存档 ──
    def save_trade(self, trade: TradeRecord):
        """保存交易记录"""
        doc = asdict(trade)
        if self.available:
            self.db.trades.insert_one(doc)
        else:
            self._append_json("trades.jsonl", doc)
        logger.debug(f"已归档交易: {trade.id} {trade.stock_code} {trade.action}")

    def get_trades(
        self,
        stock_code: str = None,
        strategy_type: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        查询历史交易记录（看板V3.0历史查询面板调用）
        """
        if not self.available:
            return []
        query = {}
        if stock_code:
            query["stock_code"] = stock_code
        if strategy_type:
            query["strategy_type"] = strategy_type
        if start_date or end_date:
            query["execution_time"] = {}
            if start_date:
                query["execution_time"]["$gte"] = start_date
            if end_date:
                query["execution_time"]["$lte"] = end_date
        cursor = self.db.trades.find(query).sort("execution_time", -1).limit(limit)
        return [self._clean_doc(d) for d in cursor]

    # ── 策略绩效归档 ──
    def save_strategy_snapshot(self, strategy_id: str, date: str, metrics: Dict):
        """保存策略每日绩效快照"""
        doc = {
            "strategy_id": strategy_id,
            "date": date,
            "metrics": metrics,
            "saved_at": datetime.now().isoformat()
        }
        if self.available:
            self.db.strategy_snapshots.update_one(
                {"strategy_id": strategy_id, "date": date},
                {"$set": doc},
                upsert=True
            )
        else:
            self._append_json("strategy_snapshots.jsonl", doc)

    def get_strategy_performance(self, strategy_id: str, days: int = 90) -> List[Dict]:
        """获取策略历史绩效曲线"""
        if not self.available:
            return []
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        cursor = self.db.strategy_snapshots.find(
            {"strategy_id": strategy_id, "date": {"$gte": start}}
        ).sort("date", 1)
        return [self._clean_doc(d) for d in cursor]

    # ── 市场政权数据库 ──
    def save_market_regime(self, regime: MarketRegime):
        """保存市场政权快照"""
        doc = asdict(regime)
        if self.available:
            self.db.market_regimes.update_one(
                {"date": regime.date},
                {"$set": doc},
                upsert=True
            )

    def get_regime_history(self, days: int = 252) -> List[Dict]:
        """获取市场政权历史序列"""
        if not self.available:
            return []
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        cursor = self.db.market_regimes.find(
            {"date": {"$gte": start}}
        ).sort("date", 1)
        return [self._clean_doc(d) for d in cursor]

    def get_current_regime(self) -> Optional[Dict]:
        """获取最新市场政权"""
        if not self.available:
            return None
        doc = self.db.market_regimes.find_one(sort=[("date", -1)])
        return self._clean_doc(doc) if doc else None

    # ── 交易模式挖掘 ──
    def mine_trade_patterns(self, days: int = 180) -> Dict:
        """
        挖掘历史交易模式
        分析: 胜率最高的策略/时间/市场政权/行业
        """
        trades = self.get_trades(start_date=(datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d"), limit=5000)
        if not trades:
            return {"error": "无足够历史数据"}
        df = pd.DataFrame(trades)
        sell_df = df[df["action"] == "SELL"].copy()
        if sell_df.empty:
            return {"error": "无已平仓记录"}
        patterns = {}
        # 按策略类型分析胜率
        if "strategy_type" in sell_df.columns:
            strategy_stats = sell_df.groupby("strategy_type").agg(
                win_rate=("pnl", lambda x: (x > 0).mean()),
                avg_pnl=("pnl_pct", "mean"),
                count=("pnl", "count")
            ).reset_index()
            patterns["by_strategy"] = strategy_stats.to_dict("records")
        # 按市场政权分析
        if "market_regime" in sell_df.columns:
            regime_stats = sell_df.groupby("market_regime").agg(
                win_rate=("pnl", lambda x: (x > 0).mean()),
                avg_pnl=("pnl_pct", "mean"),
                count=("pnl", "count")
            ).reset_index()
            patterns["by_regime"] = regime_stats.to_dict("records")
        # 整体统计
        patterns["overall"] = {
            "total_trades": len(sell_df),
            "win_rate": float((sell_df["pnl"] > 0).mean()),
            "avg_pnl_pct": float(sell_df["pnl_pct"].mean()),
            "best_trade": sell_df.nlargest(1, "pnl_pct").to_dict("records"),
            "worst_trade": sell_df.nsmallest(1, "pnl_pct").to_dict("records")
        }
        # 保存挖掘结果
        if self.available:
            self.db.trade_patterns.insert_one({
                "mined_at": datetime.now().isoformat(),
                "period_days": days,
                "patterns": patterns
            })
        return patterns

    # ── 全文搜索接口（供看板V3.0调用）──
    def search(self, query: str, limit: int = 20) -> Dict:
        """
        多集合搜索（股票代码/策略名/日期/关键词）
        """
        results = {"trades": [], "strategies": [], "regimes": []}
        if not self.available:
            return results
        # 尝试识别查询类型
        if len(query) == 6 and query.isdigit():
            # 股票代码查询
            results["trades"] = self.get_trades(stock_code=query, limit=limit)
        elif query in ["momentum", "mean_reversion", "ml_ensemble", "动量", "均值回归"]:
            # 策略类型查询
            stype = {"动量": "momentum", "均值回归": "mean_reversion"}.get(query, query)
            results["trades"] = self.get_trades(strategy_type=stype, limit=limit)
        elif query in ["bull", "bear", "range", "crisis", "牛市", "熊市", "震荡", "危机"]:
            # 市场政权查询
            regime_map = {"牛市": "bull", "熊市": "bear", "震荡": "range", "危机": "crisis"}
            regime = regime_map.get(query, query)
            cursor = self.db.market_regimes.find({"regime": regime}).sort("date", -1).limit(limit)
            results["regimes"] = [self._clean_doc(d) for d in cursor]
        else:
            # 日期查询（YYYY-MM-DD格式）
            results["trades"] = self.get_trades(start_date=query, end_date=query, limit=limit)
        return results

    # ── 工具方法 ──
    def get_dashboard_data(self) -> Dict:
        """获取看板V3.0历史查询面板所需数据"""
        patterns = self.mine_trade_patterns(days=90)
        current_regime = self.get_current_regime()
        recent_trades = self.get_trades(limit=20)
        return {
            "trade_patterns": patterns,
            "current_regime": current_regime,
            "recent_trades": recent_trades,
            "total_trades": self.db.trades.count_documents({}) if self.available else 0
        }

    def _clean_doc(self, doc: Dict) -> Dict:
        """清理MongoDB文档（移除_id字段）"""
        if doc and "_id" in doc:
            doc.pop("_id")
        return doc

    def _append_json(self, filename: str, data: Dict):
        """JSON Lines格式追加存储"""
        path = os.path.join(self.data_dir, filename)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, default=str) + "\n")
