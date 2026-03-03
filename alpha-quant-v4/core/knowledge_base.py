# knowledge_base.py --- 交易知识库
# 将每日复盘发现、策略规律结构化存储，支持检索

import json
import os
from datetime import datetime
from loguru import logger

class KnowledgeBase:
    """
    量化交易知识库

    存储类型：
    - pattern: 市场规律（如"LPR下调后银行股3日反弹"）
    - rule: 交易铁律（如"连板股第二天竞价低于-3%必须放弃"）
    - lesson: 教训总结（如"追高龙头的亏损记录"）
    - insight: 策略洞察（如"震荡市value策略胜率最高"）
    """

    def __init__(self, db_path="data/knowledge_db.json"):
        self.db_path = db_path
        self.entries = []
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self._load()

    def _load(self):
        """加载知识库"""
        if os.path.exists(self.db_path):
            with open(self.db_path, "r", encoding="utf-8") as f:
                self.entries = json.load(f)
            logger.info(f"知识库加载完成: {len(self.entries)} 条记录")
        else:
            self.entries = []

    def _save(self):
        """保存知识库"""
        with open(self.db_path, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, ensure_ascii=False, indent=2)

    def add(self, category, title, evidence, confidence=0.8, scenario=""):
        """新增知识条目"""
        entry = {
            "id": f"KB-{datetime.now().strftime('%Y%m%d')}-{len(self.entries)+1:03d}",
            "category": category,
            "title": title,
            "evidence": evidence,
            "confidence": confidence,
            "applicable_scenario": scenario,
            "created_at": datetime.now().isoformat(),
            "usage_count": 0,
            "last_validated": None
        }
        self.entries.append(entry)
        self._save()
        logger.info(f"知识库新增: [{category}] {title}")
        return entry

    def search(self, keyword="", category=None, min_confidence=0.0):
        """检索知识"""
        results = self.entries
        if category:
            results = [e for e in results if e["category"] == category]
        if keyword:
            results = [e for e in results if keyword in e["title"] or keyword in e.get("evidence", "")]
        if min_confidence > 0:
            results = [e for e in results if e["confidence"] >= min_confidence]
        return sorted(results, key=lambda x: x["confidence"], reverse=True)

    def get_stats(self):
        """知识库统计"""
        from collections import Counter
        cats = Counter(e["category"] for e in self.entries)
        return {
            "total": len(self.entries),
            "by_category": dict(cats),
            "avg_confidence": sum(e["confidence"] for e in self.entries) / max(len(self.entries), 1)
        }

if __name__ == "__main__":
    kb = KnowledgeBase()
    kb.add("pattern", "LPR下调后银行板块通常3日内反弹",
           "回测20次LPR下调事件，18次银行板块3日内上涨", 0.90, "央行宣布LPR下调后")
    kb.add("rule", "连板股竞价低于-3%必须放弃",
           "统计100次追板，竞价低开超3%的胜率仅12%", 0.95, "连板股次日竞价阶段")
    kb.add("lesson", "大盘跌超2%时抄底往往被套",
           "过去1年6次大跌日抄底，5次第二天继续跌", 0.85, "大盘大幅下跌日")

    print(f"知识库统计: {kb.get_stats()}")
    results = kb.search("银行")
    for r in results:
        print(f"  [{r['category']}] {r['title']} (置信度:{r['confidence']:.0%})")
