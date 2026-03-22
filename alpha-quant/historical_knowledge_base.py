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
    account_type: str = "real"  # 新增: "real" | "simulation"
    account_id: str = ""      # 账户ID（实盘或模拟盘）


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
        account_type: str = None,  # 新增: "real" | "simulation"
        limit: int = 100
    ) -> List[Dict]:
        """
        查询历史交易记录（看板V3.0历史查询面板调用）
        支持按账户类型筛选（实盘/模拟盘）
        """
        if not self.available:
            return []
        query = {}
        if stock_code:
            query["$or"] = [{"stock_code": stock_code}, {"code": stock_code}]
        if strategy_type:
            query["strategy_type"] = strategy_type
        if account_type:
            query["account_type"] = account_type
        if start_date or end_date:
            time_query = {}
            if start_date:
                time_query["$gte"] = start_date
            if end_date:
                time_query["$lte"] = end_date
            query["$or"] = [{"execution_time": time_query}, {"timestamp": time_query}]
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

    # ── 模拟盘交易记录存档 ──
    def save_simulation_trade(self, trade_data: Dict):
        """
        保存模拟盘交易记录
        数据格式与实盘一致，仅增加 account_type: "simulation"
        """
        doc = {
            "account_type": "simulation",
            "account_id": trade_data.get("account_id", ""),
            "code": trade_data.get("code", ""),
            "name": trade_data.get("name", ""),
            "side": trade_data.get("side", ""),
            "price": trade_data.get("price", 0.0),
            "qty": trade_data.get("qty", 0),
            "amount": trade_data.get("amount", 0.0),
            "strategy": trade_data.get("strategy", ""),
            "fees": trade_data.get("fees", 0.0),
            "timestamp": trade_data.get("timestamp", datetime.now().isoformat()),
            "execution_time": trade_data.get("timestamp", datetime.now().isoformat()),
            "stock_code": trade_data.get("code", ""),
            "stock_name": trade_data.get("name", ""),
            "action": trade_data.get("side", "").upper(),
            "signal_source": trade_data.get("signal_source", "simulation"),
            "strategy_type": trade_data.get("strategy_type", ""),
            "market_regime": trade_data.get("market_regime", ""),
            "sentiment_score": trade_data.get("sentiment_score", 0.0),
            "saved_at": datetime.now().isoformat()
        }
        if self.available:
            self.db.trades.insert_one(doc)
        else:
            self._append_json("simulation_trades.jsonl", doc)
        logger.info(f"已归档模拟盘交易: {doc['code']} {doc['side']} via {doc['account_id']}")

    def save_simulation_snapshot(self, snapshot: Dict):
        """
        保存模拟盘账户快照
        """
        doc = {
            "account_type": "simulation",
            "account_id": snapshot.get("account_id", ""),
            "account_type_detail": snapshot.get("account_type", "simulation"),
            "timestamp": snapshot.get("timestamp", datetime.now().isoformat()),
            "metrics": snapshot.get("metrics", {}),
            "positions": snapshot.get("positions", {}),
            "cash": snapshot.get("cash", 0.0),
            "saved_at": datetime.now().isoformat()
        }
        if self.available:
            self.db.simulation_snapshots.update_one(
                {"account_id": doc["account_id"], "timestamp": doc["timestamp"]},
                {"$set": doc},
                upsert=True
            )
        else:
            self._append_json("simulation_snapshots.jsonl", doc)
        logger.debug(f"已归档模拟盘快照: {doc['account_id']}")

    def get_trades_by_account_type(
        self,
        account_type: str = "real",  # "real" | "simulation" | "all"
        stock_code: str = None,
        start_date: str = None,
        end_date: str = None,
        limit: int = 100
    ) -> List[Dict]:
        """
        按账户类型查询交易记录
        """
        if not self.available:
            return []
        
        query = {}
        
        # 账户类型筛选
        if account_type != "all":
            query["account_type"] = account_type
        
        # 股票代码筛选
        if stock_code:
            query["$or"] = [
                {"stock_code": stock_code},
                {"code": stock_code}
            ]
        
        # 日期范围筛选
        if start_date or end_date:
            time_query = {}
            if start_date:
                time_query["$gte"] = start_date
            if end_date:
                time_query["$lte"] = end_date
            query["$or"] = [
                {"execution_time": time_query},
                {"timestamp": time_query}
            ]
        
        cursor = self.db.trades.find(query).sort("execution_time", -1).limit(limit)
        return [self._clean_doc(d) for d in cursor]

    def compare_real_sim_performance(
        self,
        real_account_id: str = None,
        sim_account_id: str = None,
        days: int = 30
    ) -> Dict:
        """
        对比实盘与模拟盘绩效
        """
        start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        
        # 获取实盘交易
        real_query = {"account_type": "real", "execution_time": {"$gte": start}}
        if real_account_id:
            real_query["account_id"] = real_account_id
        
        # 获取模拟盘交易
        sim_query = {"account_type": "simulation", "execution_time": {"$gte": start}}
        if sim_account_id:
            sim_query["account_id"] = sim_account_id
        
        if not self.available:
            return {"error": "MongoDB不可用"}
        
        real_trades = list(self.db.trades.find(real_query))
        sim_trades = list(self.db.trades.find(sim_query))
        
        # 计算统计指标
        def calc_stats(trades):
            if not trades:
                return {"count": 0, "avg_price": 0, "total_amount": 0}
            
            buy_trades = [t for t in trades if t.get("side", "").upper() == "BUY" or t.get("action", "") == "BUY"]
            sell_trades = [t for t in trades if t.get("side", "").upper() == "SELL" or t.get("action", "") == "SELL"]
            
            total_buy = sum(t.get("amount", 0) for t in buy_trades)
            total_sell = sum(t.get("amount", 0) for t in sell_trades)
            
            return {
                "count": len(trades),
                "buy_count": len(buy_trades),
                "sell_count": len(sell_trades),
                "total_buy_amount": round(total_buy, 2),
                "total_sell_amount": round(total_sell, 2),
                "avg_trade_price": round(sum(t.get("price", 0) for t in trades) / len(trades), 2) if trades else 0
            }
        
        real_stats = calc_stats(real_trades)
        sim_stats = calc_stats(sim_trades)
        
        return {
            "period_days": days,
            "real_account_id": real_account_id or "default",
            "sim_account_id": sim_account_id or "default",
            "real": real_stats,
            "simulation": sim_stats,
            "comparison": {
                "trade_count_diff": sim_stats["count"] - real_stats["count"],
                "amount_diff_pct": round((sim_stats["total_buy_amount"] - real_stats["total_buy_amount"]) / real_stats["total_buy_amount"] * 100, 2) if real_stats["total_buy_amount"] > 0 else 0
            }
        }
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
        多集合搜索（股票代码/策略名/日期/关键词/账户类型）
        新增: 支持按 "模拟盘" | "实盘" 搜索
        """
        results = {"trades": [], "strategies": [], "regimes": [], "simulation": []}
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
        elif query in ["模拟盘", "simulation", "SIM"]:
            # 模拟盘交易查询
            results["trades"] = self.get_trades_by_account_type("simulation", limit=limit)
            results["simulation"] = results["trades"]
        elif query in ["实盘", "real"]:
            # 实盘交易查询
            results["trades"] = self.get_trades_by_account_type("real", limit=limit)
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
        
        # V6.1 新增: 模拟盘数据
        sim_trades = self.get_trades_by_account_type("simulation", limit=20)
        real_trades = self.get_trades_by_account_type("real", limit=20)
        
        # 统计
        total_real = self.db.trades.count_documents({"account_type": "real"}) if self.available else 0
        total_sim = self.db.trades.count_documents({"account_type": "simulation"}) if self.available else 0
        
        return {
            "trade_patterns": patterns,
            "current_regime": current_regime,
            "recent_trades": recent_trades,
            "total_trades": total_real + total_sim,
            "total_real_trades": total_real,
            "total_simulation_trades": total_sim,
            # V6.1 新增
            "simulation": {
                "recent_trades": sim_trades,
                "count": total_sim
            },
            "real": {
                "recent_trades": real_trades,
                "count": total_real
            },
            "comparison": self.compare_real_sim_performance(days=30) if self.available else {}
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
