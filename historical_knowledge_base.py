#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alpha V6.0 - 历史知识库 (Historical Knowledge Base)
存储和检索历史交易知识、模式识别、市场规律
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import hashlib
import os

try:
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.errors import ConnectionFailure
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False
    logger.warning("pymongo未安装，将使用内存存储")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class KnowledgeEntry:
    """知识条目"""
    entry_id: str
    entry_type: str  # "pattern", "rule", "insight", "lesson"
    title: str
    content: str
    tags: List[str]
    market_condition: str
    related_symbols: List[str]
    confidence: float
    occurrence_count: int
    first_seen: str
    last_seen: str
    performance_score: float
    metadata: Dict[str, Any]


class HistoricalKnowledgeBase:
    """
    历史知识库
    
    功能：
    1. 存储历史交易模式
    2. 知识检索和匹配
    3. 模式置信度更新
    4. 知识图谱构建
    5. 经验教训记录
    """
    
    def __init__(self, config_path: str = "/opt/alpha-system/config/config.json"):
        self.config = self._load_config(config_path)
        self.db_config = self.config.get("database", {})
        self.db_name = self.db_config.get("name", "alpha_v6")
        
        self.use_mongo = MONGO_AVAILABLE
        self.memory_store: Dict[str, KnowledgeEntry] = {}
        self.db = None
        self.collection = None
        
        if self.use_mongo:
            try:
                self._init_mongodb()
            except Exception as e:
                logger.warning(f"MongoDB连接失败: {e}，使用内存存储")
                self.use_mongo = False
        
        self._ensure_indexes()
        logger.info(f"历史知识库初始化完成，存储模式: {'MongoDB' if self.use_mongo else '内存'}")
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"无法加载配置: {e}，使用默认配置")
            return {"database": {"name": "alpha_v6"}}
    
    def _init_mongodb(self):
        """初始化MongoDB连接"""
        host = self.db_config.get("host", "localhost")
        port = self.db_config.get("port", 27017)
        
        self.client = MongoClient(host, port, serverSelectionTimeoutMS=5000)
        self.client.admin.command('ping')
        self.db = self.client[self.db_name]
        self.collection = self.db["historical_knowledge"]
        logger.info(f"MongoDB连接成功: {host}:{port}/{self.db_name}")
    
    def _ensure_indexes(self):
        """确保索引存在"""
        if self.use_mongo and self.collection:
            self.collection.create_index([("entry_type", ASCENDING)])
            self.collection.create_index([("tags", ASCENDING)])
            self.collection.create_index([("market_condition", ASCENDING)])
            self.collection.create_index([("confidence", DESCENDING)])
    
    def _generate_id(self, content: str) -> str:
        """生成条目ID"""
        return hashlib.md5(content.encode()).hexdigest()[:16]
    
    def add_knowledge(self, entry_type: str, title: str, content: str,
                      tags: List[str] = None, market_condition: str = "",
                      related_symbols: List[str] = None, 
                      metadata: Dict = None) -> str:
        """
        添加知识条目
        
        Args:
            entry_type: 条目类型 (pattern, rule, insight, lesson)
            title: 标题
            content: 内容
            tags: 标签列表
            market_condition: 市场条件
            related_symbols: 相关股票代码
            metadata: 额外元数据
        """
        entry_id = self._generate_id(f"{title}:{content}")
        
        # 检查是否已存在
        existing = self.get_entry(entry_id)
        if existing:
            # 更新已有条目
            self._update_entry(entry_id, {
                "occurrence_count": existing.occurrence_count + 1,
                "last_seen": datetime.now().isoformat()
            })
            return entry_id
        
        entry = KnowledgeEntry(
            entry_id=entry_id,
            entry_type=entry_type,
            title=title,
            content=content,
            tags=tags or [],
            market_condition=market_condition,
            related_symbols=related_symbols or [],
            confidence=0.5,
            occurrence_count=1,
            first_seen=datetime.now().isoformat(),
            last_seen=datetime.now().isoformat(),
            performance_score=0.0,
            metadata=metadata or {}
        )
        
        if self.use_mongo:
            self.collection.insert_one(asdict(entry))
        else:
            self.memory_store[entry_id] = entry
        
        logger.info(f"知识条目已添加: {entry_id} - {title}")
        return entry_id
    
    def get_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """获取知识条目"""
        if self.use_mongo:
            doc = self.collection.find_one({"entry_id": entry_id})
            if doc:
                doc.pop('_id', None)
                return KnowledgeEntry(**doc)
            return None
        else:
            return self.memory_store.get(entry_id)
    
    def search_knowledge(self, query: str = None, entry_type: str = None,
                         tags: List[str] = None, market_condition: str = None,
                         min_confidence: float = 0.0, limit: int = 10) -> List[Dict]:
        """
        搜索知识条目
        
        Args:
            query: 搜索关键词
            entry_type: 条目类型过滤
            tags: 标签过滤
            market_condition: 市场条件过滤
            min_confidence: 最小置信度
            limit: 返回数量限制
        """
        results = []
        
        if self.use_mongo:
            filter_query = {"confidence": {"$gte": min_confidence}}
            if entry_type:
                filter_query["entry_type"] = entry_type
            if tags:
                filter_query["tags"] = {"$in": tags}
            if market_condition:
                filter_query["market_condition"] = market_condition
            if query:
                filter_query["$or"] = [
                    {"title": {"$regex": query, "$options": "i"}},
                    {"content": {"$regex": query, "$options": "i"}}
                ]
            
            cursor = self.collection.find(filter_query).sort("confidence", DESCENDING).limit(limit)
            for doc in cursor:
                doc.pop('_id', None)
                results.append(doc)
        else:
            for entry in self.memory_store.values():
                if entry.confidence < min_confidence:
                    continue
                if entry_type and entry.entry_type != entry_type:
                    continue
                if tags and not any(t in entry.tags for t in tags):
                    continue
                if market_condition and entry.market_condition != market_condition:
                    continue
                if query and query.lower() not in entry.title.lower() and query.lower() not in entry.content.lower():
                    continue
                results.append(asdict(entry))
            
            results.sort(key=lambda x: x["confidence"], reverse=True)
            results = results[:limit]
        
        return results
    
    def update_confidence(self, entry_id: str, new_confidence: float,
                         performance_delta: float = 0):
        """更新条目置信度"""
        new_confidence = max(0.0, min(1.0, new_confidence))
        
        update_data = {
            "confidence": new_confidence,
            "last_seen": datetime.now().isoformat()
        }
        
        if performance_delta != 0:
            entry = self.get_entry(entry_id)
            if entry:
                update_data["performance_score"] = entry.performance_score + performance_delta
        
        self._update_entry(entry_id, update_data)
        logger.debug(f"条目 {entry_id} 置信度更新为 {new_confidence}")
    
    def _update_entry(self, entry_id: str, update_data: Dict):
        """内部更新方法"""
        if self.use_mongo:
            self.collection.update_one(
                {"entry_id": entry_id},
                {"$set": update_data}
            )
        else:
            entry = self.memory_store.get(entry_id)
            if entry:
                for key, value in update_data.items():
                    setattr(entry, key, value)
    
    def find_similar_patterns(self, current_condition: str, symbol: str = None,
                              lookback_days: int = 30) -> List[Dict]:
        """
        查找相似历史模式
        
        Args:
            current_condition: 当前市场条件描述
            symbol: 股票代码（可选）
            lookback_days: 回溯天数
        """
        # 构建查询条件
        tags = ["pattern"]
        if symbol:
            # 先搜索特定股票的模式
            specific_patterns = self.search_knowledge(
                entry_type="pattern",
                tags=tags,
                query=current_condition,
                limit=5
            )
            if specific_patterns:
                return specific_patterns
        
        # 搜索通用模式
        general_patterns = self.search_knowledge(
            entry_type="pattern",
            tags=tags,
            query=current_condition,
            min_confidence=0.6,
            limit=10
        )
        
        return general_patterns
    
    def record_lesson(self, title: str, content: str, outcome: str,
                     market_condition: str, related_symbols: List[str] = None):
        """记录交易经验教训"""
        metadata = {"outcome": outcome}
        entry_id = self.add_knowledge(
            entry_type="lesson",
            title=title,
            content=content,
            tags=["lesson", outcome],
            market_condition=market_condition,
            related_symbols=related_symbols or [],
            metadata=metadata
        )
        logger.info(f"经验教训已记录: {entry_id}")
        return entry_id
    
    def get_market_insights(self, market_condition: str, limit: int = 5) -> List[Dict]:
        """获取市场洞察"""
        return self.search_knowledge(
            entry_type="insight",
            market_condition=market_condition,
            min_confidence=0.7,
            limit=limit
        )
    
    def get_trading_rules(self, tags: List[str] = None, limit: int = 10) -> List[Dict]:
        """获取交易规则"""
        return self.search_knowledge(
            entry_type="rule",
            tags=tags,
            min_confidence=0.8,
            limit=limit
        )
    
    def get_stats(self) -> Dict:
        """获取知识库统计"""
        if self.use_mongo:
            total = self.collection.count_documents({})
            by_type = list(self.collection.aggregate([
                {"$group": {"_id": "$entry_type", "count": {"$sum": 1}}}
            ]))
            avg_confidence = list(self.collection.aggregate([
                {"$group": {"_id": None, "avg": {"$avg": "$confidence"}}}
            ]))
        else:
            total = len(self.memory_store)
            by_type_dict = {}
            total_confidence = 0
            for entry in self.memory_store.values():
                by_type_dict[entry.entry_type] = by_type_dict.get(entry.entry_type, 0) + 1
                total_confidence += entry.confidence
            by_type = [{"_id": k, "count": v} for k, v in by_type_dict.items()]
            avg_confidence = [{"avg": total_confidence / total if total > 0 else 0}]
        
        return {
            "total_entries": total,
            "by_type": {item["_id"]: item["count"] for item in by_type},
            "avg_confidence": round(avg_confidence[0]["avg"], 4) if avg_confidence else 0,
            "storage_mode": "MongoDB" if self.use_mongo else "内存"
        }
    
    def export_knowledge(self, filepath: str):
        """导出知识库到文件"""
        if self.use_mongo:
            entries = list(self.collection.find({}, {"_id": 0}))
        else:
            entries = [asdict(e) for e in self.memory_store.values()]
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=2)
        
        logger.info(f"知识库已导出到: {filepath}")
    
    def import_knowledge(self, filepath: str):
        """从文件导入知识库"""
        with open(filepath, 'r', encoding='utf-8') as f:
            entries = json.load(f)
        
        for entry_data in entries:
            entry = KnowledgeEntry(**entry_data)
            if self.use_mongo:
                self.collection.replace_one(
                    {"entry_id": entry.entry_id},
                    asdict(entry),
                    upsert=True
                )
            else:
                self.memory_store[entry.entry_id] = entry
        
        logger.info(f"从 {filepath} 导入了 {len(entries)} 条知识")


# 单例实例
_knowledge_base = None

def get_knowledge_base() -> HistoricalKnowledgeBase:
    """获取知识库单例"""
    global _knowledge_base
    if _knowledge_base is None:
        _knowledge_base = HistoricalKnowledgeBase()
    return _knowledge_base


if __name__ == "__main__":
    # 测试
    kb = HistoricalKnowledgeBase()
    
    # 添加测试知识
    kb.add_knowledge(
        entry_type="pattern",
        title="突破后回踩买入模式",
        content="当股价突破关键阻力位后回踩确认支撑有效，是较好的买入时机",
        tags=["pattern", "breakout", "technical"],
        market_condition="bullish",
        related_symbols=["000001.XSHE"]
    )
    
    kb.record_lesson(
        title="追涨杀跌的教训",
        content="在市场情绪极度乐观时追高，往往面临较大回撤风险",
        outcome="loss",
        market_condition="overbought"
    )
    
    # 搜索知识
    patterns = kb.search_knowledge(entry_type="pattern", limit=5)
    print(f"找到 {len(patterns)} 个模式")
    
    # 统计
    stats = kb.get_stats()
    print(f"知识库统计: {json.dumps(stats, indent=2, ensure_ascii=False)}")
