"""
Alpha-Genesis V6.1 SimEdge - 知识库全文检索增强
完善 P1-4: 知识库全文检索
======================================
MongoDB Atlas Search 全文索引 + 向量语义搜索

Author: Alpha-Genesis Team
Version: 6.1.0
Date: 2026-03-09
"""

import os
import json
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

# MongoDB
try:
    from pymongo import MongoClient, ASCENDING, DESCENDING
    from pymongo.errors import OperationFailure
    PYMONGO_AVAILABLE = True
except ImportError:
    PYMONGO_AVAILABLE = False
    logging.warning("pymongo 未安装，知识库功能将受限")

# 向量搜索
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False

logger = logging.getLogger("KnowledgeSearch")


@dataclass
class SearchResult:
    """搜索结果"""
    id: str
    collection: str
    score: float
    content: Dict
    highlights: List[str] = None
    vector_score: float = 0.0
    
    def __post_init__(self):
        if self.highlights is None:
            self.highlights = []


class KnowledgeBaseSearch:
    """
    知识库全文检索引擎
    
    功能：
    - MongoDB Atlas Search 全文索引
    - 向量语义搜索 (TF-IDF + Cosine Similarity)
    - 混合搜索 (全文 + 向量融合排序)
    - 多集合联合搜索
    """
    
    def __init__(self, mongo_url: str = None, db_name: str = "kimi_claw"):
        """
        初始化知识库搜索引擎
        
        Args:
            mongo_url: MongoDB 连接URL
            db_name: 数据库名
        """
        self.mongo_url = mongo_url or os.environ.get("MONGODB_URL", "mongodb://localhost:27017")
        self.db_name = db_name
        
        self.client = None
        self.db = None
        self.vectorizer = None
        self.document_vectors = {}
        
        self._connect()
        self._init_vectorizer()
        self._create_search_indexes()
    
    def _connect(self):
        """连接 MongoDB"""
        if not PYMONGO_AVAILABLE:
            logger.error("pymongo 未安装，无法连接 MongoDB")
            return
        
        try:
            self.client = MongoClient(self.mongo_url, serverSelectionTimeoutMS=5000)
            self.db = self.client[self.db_name]
            
            # 测试连接
            self.client.server_info()
            logger.info(f"✅ MongoDB 连接成功: {self.db_name}")
            
        except Exception as e:
            logger.error(f"MongoDB 连接失败: {e}")
            self.client = None
    
    def _init_vectorizer(self):
        """初始化向量器"""
        if SKLEARN_AVAILABLE:
            self.vectorizer = TfidfVectorizer(
                max_features=5000,
                ngram_range=(1, 2),
                stop_words='english',
                min_df=1
            )
            logger.info("✅ TF-IDF 向量器初始化完成")
    
    def _create_search_indexes(self):
        """创建 Atlas Search 索引"""
        if not self.db:
            return
        
        # 定义搜索索引配置
        search_indexes = {
            "trades": {
                "mappings": {
                    "dynamic": False,
                    "fields": {
                        "stock_code": {"type": "string", "analyzer": "standard"},
                        "stock_name": {"type": "string", "analyzer": "standard"},
                        "action": {"type": "string"},
                        "strategy_type": {"type": "string"},
                        "market_regime": {"type": "string"},
                        "signal_source": {"type": "string"}
                    }
                }
            },
            "reports": {
                "mappings": {
                    "dynamic": False,
                    "fields": {
                        "title": {"type": "string", "analyzer": "standard"},
                        "content": {"type": "string", "analyzer": "standard"},
                        "stock_code": {"type": "string"},
                        "report_type": {"type": "string"}
                    }
                }
            },
            "strategy_snapshots": {
                "mappings": {
                    "dynamic": False,
                    "fields": {
                        "strategy_id": {"type": "string"},
                        "strategy_type": {"type": "string"}
                    }
                }
            }
        }
        
        # 注意：实际创建 Atlas Search 索引需要在 MongoDB Atlas 控制台进行
        # 这里仅记录配置
        logger.info("Atlas Search 索引配置已准备 (需在 Atlas 控制台创建)")
    
    # ═══════════════════════════════════════════════════════════
    # 全文搜索 (Atlas Search)
    # ═══════════════════════════════════════════════════════════
    
    def full_text_search(
        self,
        query: str,
        collections: List[str] = None,
        limit: int = 20,
        fuzzy: bool = True
    ) -> List[SearchResult]:
        """
        全文搜索
        
        Args:
            query: 搜索关键词
            collections: 搜索的集合列表 (默认: trades, reports, strategy_snapshots)
            limit: 返回结果数
            fuzzy: 是否启用模糊匹配
        
        Returns:
            搜索结果列表
        """
        if not self.db:
            logger.warning("MongoDB 未连接，返回空结果")
            return []
        
        collections = collections or ["trades", "reports", "strategy_snapshots"]
        results = []
        
        for collection_name in collections:
            try:
                collection = self.db[collection_name]
                
                # 使用 Atlas Search
                pipeline = [
                    {
                        "$search": {
                            "index": f"{collection_name}_search",  # 搜索索引名
                            "text": {
                                "query": query,
                                "path": {
                                    "wildcard": "*"  # 搜索所有字段
                                },
                                "fuzzy": {"maxEdits": 1} if fuzzy else None
                            },
                            "highlight": {
                                "path": {"wildcard": "*"}
                            }
                        }
                    },
                    {"$limit": limit},
                    {
                        "$project": {
                            "score": {"$meta": "searchScore"},
                            "highlights": {"$meta": "searchHighlights"},
                            "document": "$$ROOT"
                        }
                    }
                ]
                
                # 如果 Atlas Search 不可用，回退到普通查询
                try:
                    cursor = collection.aggregate(pipeline)
                except OperationFailure:
                    # Atlas Search 未配置，使用正则查询
                    cursor = self._fallback_text_search(collection, query, limit)
                
                for doc in cursor:
                    results.append(SearchResult(
                        id=str(doc.get("document", {}).get("_id", "")),
                        collection=collection_name,
                        score=doc.get("score", 0),
                        content=self._clean_doc(doc.get("document", {})),
                        highlights=doc.get("highlights", [])
                    ))
                    
            except Exception as e:
                logger.error(f"全文搜索失败 {collection_name}: {e}")
        
        # 按分数排序
        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]
    
    def _fallback_text_search(self, collection, query: str, limit: int):
        """回退文本搜索 (正则匹配)"""
        regex_pattern = f".*{query}.*"
        
        return collection.find(
            {"$or": [
                {"stock_code": {"$regex": regex_pattern, "$options": "i"}},
                {"stock_name": {"$regex": regex_pattern, "$options": "i"}},
                {"title": {"$regex": regex_pattern, "$options": "i"}},
                {"content": {"$regex": regex_pattern, "$options": "i"}},
                {"strategy_id": {"$regex": regex_pattern, "$options": "i"}}
            ]}
        ).limit(limit)
    
    # ═══════════════════════════════════════════════════════════
    # 向量语义搜索
    # ═══════════════════════════════════════════════════════════
    
    def build_vector_index(self, collection_name: str, text_field: str = "content"):
        """
        构建向量索引
        
        Args:
            collection_name: 集合名
            text_field: 文本字段名
        """
        if not self.db or not self.vectorizer:
            logger.warning("无法构建向量索引")
            return
        
        try:
            collection = self.db[collection_name]
            documents = list(collection.find({}, {text_field: 1, "_id": 1}))
            
            if not documents:
                logger.warning(f"集合 {collection_name} 为空，跳过向量索引")
                return
            
            # 提取文本
            texts = []
            doc_ids = []
            for doc in documents:
                text = doc.get(text_field, "")
                if text:
                    texts.append(str(text))
                    doc_ids.append(str(doc["_id"]))
            
            if not texts:
                return
            
            # 计算 TF-IDF 向量
            vectors = self.vectorizer.fit_transform(texts)
            
            # 存储向量
            self.document_vectors[collection_name] = {
                "ids": doc_ids,
                "vectors": vectors,
                "vectorizer": self.vectorizer
            }
            
            logger.info(f"向量索引构建完成: {collection_name} | 文档数: {len(texts)}")
            
        except Exception as e:
            logger.error(f"构建向量索引失败: {e}")
    
    def vector_search(
        self,
        query: str,
        collection_name: str,
        limit: int = 10
    ) -> List[SearchResult]:
        """
        向量语义搜索
        
        Args:
            query: 查询文本
            collection_name: 集合名
            limit: 返回数量
        
        Returns:
            搜索结果
        """
        if collection_name not in self.document_vectors:
            logger.warning(f"集合 {collection_name} 未建立向量索引")
            return []
        
        try:
            index_data = self.document_vectors[collection_name]
            vectorizer = index_data["vectorizer"]
            doc_vectors = index_data["vectors"]
            doc_ids = index_data["ids"]
            
            # 计算查询向量
            query_vector = vectorizer.transform([query])
            
            # 计算余弦相似度
            similarities = cosine_similarity(query_vector, doc_vectors).flatten()
            
            # 获取 top-k
            top_indices = similarities.argsort()[-limit:][::-1]
            
            # 获取文档内容
            collection = self.db[collection_name]
            results = []
            
            for idx in top_indices:
                doc_id = doc_ids[idx]
                score = similarities[idx]
                
                doc = collection.find_one({"_id": doc_id})
                if doc:
                    results.append(SearchResult(
                        id=doc_id,
                        collection=collection_name,
                        score=score,
                        content=self._clean_doc(doc),
                        vector_score=score
                    ))
            
            return results
            
        except Exception as e:
            logger.error(f"向量搜索失败: {e}")
            return []
    
    # ═══════════════════════════════════════════════════════════
    # 混合搜索
    # ═══════════════════════════════════════════════════════════
    
    def hybrid_search(
        self,
        query: str,
        collections: List[str] = None,
        limit: int = 20,
        alpha: float = 0.5
    ) -> List[SearchResult]:
        """
        混合搜索 (全文 + 向量)
        
        Args:
            query: 查询文本
            collections: 搜索集合
            limit: 返回数量
            alpha: 全文权重 (0-1)，向量权重为 (1-alpha)
        
        Returns:
            融合后的搜索结果
        """
        collections = collections or ["reports"]
        
        # 全文搜索
        text_results = self.full_text_search(query, collections, limit * 2)
        text_scores = {r.id: r.score for r in text_results}
        
        # 向量搜索
        vector_scores = {}
        for collection in collections:
            if collection in self.document_vectors:
                vec_results = self.vector_search(query, collection, limit * 2)
                for r in vec_results:
                    vector_scores[r.id] = r.score
        
        # 融合分数
        all_ids = set(text_scores.keys()) | set(vector_scores.keys())
        fused_results = []
        
        for doc_id in all_ids:
            text_score = text_scores.get(doc_id, 0)
            vec_score = vector_scores.get(doc_id, 0)
            
            # 加权融合
            fused_score = alpha * text_score + (1 - alpha) * vec_score
            
            # 获取文档内容
            for r in text_results:
                if r.id == doc_id:
                    fused_results.append(SearchResult(
                        id=doc_id,
                        collection=r.collection,
                        score=fused_score,
                        content=r.content,
                        highlights=r.highlights
                    ))
                    break
        
        # 排序
        fused_results.sort(key=lambda x: x.score, reverse=True)
        return fused_results[:limit]
    
    # ═══════════════════════════════════════════════════════════
    # 高级搜索功能
    # ═══════════════════════════════════════════════════════════
    
    def semantic_query(self, query: str, context: str = None) -> List[SearchResult]:
        """
        语义查询（自然语言理解）
        
        Args:
            query: 自然语言查询
            context: 上下文
        
        Returns:
            语义匹配结果
        """
        # 简单的查询扩展
        expanded_query = query
        if "盈利" in query or "利润" in query:
            expanded_query += " earnings profit financial"
        if "买入" in query or "buy" in query:
            expanded_query += " BUY 买入"
        if "卖出" in query or "sell" in query:
            expanded_query += " SELL 卖出"
        
        return self.hybrid_search(expanded_query, limit=15)
    
    def time_range_search(
        self,
        query: str,
        start_date: str,
        end_date: str,
        collections: List[str] = None
    ) -> List[SearchResult]:
        """
        时间范围搜索
        
        Args:
            query: 查询关键词
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            collections: 搜索集合
        
        Returns:
            时间过滤后的结果
        """
        results = self.full_text_search(query, collections, limit=100)
        
        # 时间过滤
        filtered = []
        for r in results:
            content = r.content
            date_fields = ['execution_time', 'date', 'timestamp', 'created_at', 'trade_time']
            
            for field in date_fields:
                if field in content:
                    doc_date = str(content[field])[:10]
                    if start_date <= doc_date <= end_date:
                        filtered.append(r)
                        break
        
        return filtered
    
    # ═══════════════════════════════════════════════════════════
    # 工具方法
    # ═══════════════════════════════════════════════════════════
    
    def _clean_doc(self, doc: Dict) -> Dict:
        """清理 MongoDB 文档"""
        if doc and "_id" in doc:
            doc = doc.copy()
            doc["id"] = str(doc.pop("_id"))
        return doc
    
    def get_search_suggestions(self, query: str, limit: int = 5) -> List[str]:
        """
        搜索建议
        
        Args:
            query: 部分输入
            limit: 建议数量
        
        Returns:
            建议列表
        """
        # 基于历史搜索或热门关键词
        suggestions = []
        
        # 股票代码建议
        if query.isdigit() and len(query) >= 3:
            suggestions.extend([f"{query} 股票", f"{query} 交易记录"])
        
        # 策略建议
        if "策略" in query or "strategy" in query.lower():
            suggestions.extend(["momentum 策略", "mean_reversion 策略", "策略绩效"])
        
        # 市场建议
        if "市场" in query or "market" in query.lower():
            suggestions.extend(["市场情绪", "市场政权", "市场回顾"])
        
        return suggestions[:limit]


# ═══════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════

def search_knowledge_base(
    query: str,
    search_type: str = "hybrid",
    limit: int = 20
) -> List[SearchResult]:
    """
    便捷函数: 搜索知识库
    
    Args:
        query: 查询
        search_type: 搜索类型 (full_text/vector/hybrid)
        limit: 返回数量
    
    Returns:
        搜索结果
    """
    search = KnowledgeBaseSearch()
    
    if search_type == "full_text":
        return search.full_text_search(query, limit=limit)
    elif search_type == "vector":
        return search.vector_search(query, "trades", limit=limit)
    else:
        return search.hybrid_search(query, limit=limit)


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== 知识库全文检索测试 ===\n")
    
    if not PYMONGO_AVAILABLE:
        print("❌ pymongo 未安装，跳过测试")
        exit(0)
    
    # 初始化搜索
    search = KnowledgeBaseSearch()
    
    # 构建向量索引
    print("1. 构建向量索引:")
    search.build_vector_index("trades", "stock_name")
    
    # 测试全文搜索
    print("\n2. 测试全文搜索:")
    results = search.full_text_search("茅台", limit=5)
    print(f"   找到 {len(results)} 条结果")
    for r in results[:3]:
        print(f"   - {r.collection}: {r.id[:20]}... (score: {r.score:.2f})")
    
    # 测试向量搜索
    print("\n3. 测试向量搜索:")
    if "trades" in search.document_vectors:
        results = search.vector_search("贵州茅台", "trades", limit=5)
        print(f"   找到 {len(results)} 条结果")
        for r in results[:3]:
            print(f"   - {r.id[:20]}... (score: {r.score:.2f})")
    else:
        print("   向量索引未建立，跳过")
    
    # 测试混合搜索
    print("\n4. 测试混合搜索:")
    results = search.hybrid_search("茅台 买入", limit=5)
    print(f"   找到 {len(results)} 条结果")
    
    # 测试语义查询
    print("\n5. 测试语义查询:")
    results = search.semantic_query("盈利好的股票")
    print(f"   找到 {len(results)} 条结果")
    
    print("\n✅ 知识库全文检索测试完成")
