"""
舆情分析管道 - Alpha V6.0
V5.0: 情绪评分（关键词匹配）
V6.0: 事件驱动信号（因果推理链）
"""

import json
import logging
import re
from datetime import datetime
from dataclasses import dataclass
from typing import List, Dict, Optional

logger = logging.getLogger("SentimentPipeline")


# ═══════════════════════════════════════════════════════════════
# V6.0 增强部分 - 事件驱动信号
# ═══════════════════════════════════════════════════════════════

@dataclass
class MarketEvent:
    """市场事件结构"""
    event_id: str
    event_type: str          # earnings/policy/merger/blackswan/industry
    title: str
    source: str
    published_at: str
    affected_stocks: List[str]   # 直接受影响股票
    affected_sectors: List[str]  # 受影响行业
    impact_direction: str    # positive/negative/neutral/mixed
    impact_magnitude: str    # strong/moderate/weak
    duration_estimate: str   # intraday/1week/1month/longterm
    causal_chain: str        # 因果推理描述
    confidence: float        # 事件识别置信度
    raw_text: str


class EventClassifier:
    """
    事件类型分类器
    基于规则 + 关键词，可扩展为NLP模型
    """
    
    EVENT_PATTERNS = {
        "earnings": {
            "keywords": ["业绩", "财报", "净利润", "营收", "每股收益", "利润增长", "亏损", "扭亏"],
            "subtype_rules": {
                "positive": ["大幅增长", "超预期", "创历史", "翻倍"],
                "negative": ["亏损", "下滑", "低于预期", "暴跌"]
            }
        },
        "policy": {
            "keywords": ["政策", "监管", "证监会", "银保监", "国务院", "发改委", "补贴", "税收", "利率"],
            "subtype_rules": {
                "positive": ["支持", "鼓励", "补贴", "减税", "放开", "利好"],
                "negative": ["限制", "整顿", "处罚", "收紧", "利空"]
            }
        },
        "merger": {
            "keywords": ["并购", "重组", "收购", "合并", "战略合作", "入股", "定增", "大股东增持"],
            "subtype_rules": {
                "positive": ["增持", "回购", "合并", "协同"],
                "negative": ["减持", "分拆", "解散"]
            }
        },
        "blackswan": {
            "keywords": ["暴跌", "熔断", "崩盘", "危机", "违约", "爆雷", "造假", "停牌", "退市"],
            "subtype_rules": {
                "negative": ["暴跌", "崩盘", "违约", "爆雷"]
            }
        },
        "industry": {
            "keywords": ["行业", "赛道", "产业链", "供应链", "上游", "下游", "竞争格局"],
            "subtype_rules": {
                "positive": ["景气", "扩容", "爆发", "风口"],
                "negative": ["内卷", "价格战", "萎缩", "洗牌"]
            }
        }
    }
    
    # 因果推理规则库
    CAUSAL_RULES = {
        ("earnings", "positive"): {
            "direction": "positive",
            "magnitude": "strong",
            "duration": "1week",
            "chain": "业绩超预期→市场上调EPS预期→估值提升→股价上涨"
        },
        ("earnings", "negative"): {
            "direction": "negative",
            "magnitude": "strong",
            "duration": "1month",
            "chain": "业绩不达预期→机构下调目标价→资金离场→股价下跌"
        },
        ("policy", "positive"): {
            "direction": "positive",
            "magnitude": "moderate",
            "duration": "1month",
            "chain": "利好政策出台→行业受益预期→板块资金流入→相关股价上涨"
        },
        ("policy", "negative"): {
            "direction": "negative",
            "magnitude": "moderate",
            "duration": "1month",
            "chain": "监管趋严→合规成本增加→盈利预期下调→估值压缩"
        },
        ("merger", "positive"): {
            "direction": "positive",
            "magnitude": "strong",
            "duration": "intraday",
            "chain": "并购重组公告→协同效应预期→溢价收购预期→相关股票涨停"
        },
        ("blackswan", "negative"): {
            "direction": "negative",
            "magnitude": "strong",
            "duration": "1month",
            "chain": "黑天鹅事件→恐慌情绪蔓延→抛售压力→市场系统性调整"
        }
    }
    
    def classify(self, text: str, title: str = "") -> Optional[MarketEvent]:
        """对单篇新闻进行事件分类"""
        combined = (title + " " + text)[:500]
        
        # 识别事件类型
        best_type = None
        best_score = 0
        for etype, config in self.EVENT_PATTERNS.items():
            score = sum(1 for kw in config["keywords"] if kw in combined)
            if score > best_score:
                best_score = score
                best_type = etype
        
        if not best_type or best_score < 2:
            return None  # 无法识别为明确事件
        
        # 识别情感方向
        direction = "neutral"
        config = self.EVENT_PATTERNS[best_type]
        for sentiment, keywords in config.get("subtype_rules", {}).items():
            if any(kw in combined for kw in keywords):
                direction = sentiment
                break
        
        # 获取因果链
        causal = self.CAUSAL_RULES.get((best_type, direction), {
            "direction": direction,
            "magnitude": "weak",
            "duration": "intraday",
            "chain": f"{best_type}事件→市场反应"
        })
        
        return MarketEvent(
            event_id=f"evt_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            event_type=best_type,
            title=title[:100],
            source="",
            published_at=datetime.now().isoformat(),
            affected_stocks=[],     # 由实体识别器填充
            affected_sectors=[],
            impact_direction=causal["direction"],
            impact_magnitude=causal["magnitude"],
            duration_estimate=causal["duration"],
            causal_chain=causal["chain"],
            confidence=min(0.95, best_score * 0.2),
            raw_text=text[:200]
        )


class EntityLinker:
    """
    实体链接器
    从事件文本中识别受影响的股票和行业
    """
    
    def __init__(self, stock_pool: Dict[str, str]):
        """stock_pool: {stock_code: stock_name}"""
        self.stock_pool = stock_pool
        # 行业-关键词映射
        self.sector_keywords = {
            "科技": ["芯片", "半导体", "软件", "云计算", "AI", "人工智能", "互联网"],
            "新能源": ["光伏", "风电", "储能", "新能源车", "锂电池", "充电桩"],
            "医药": ["医药", "生物", "药品", "疫苗", "医疗器械", "医保"],
            "金融": ["银行", "保险", "券商", "基金", "信托", "金融"],
            "消费": ["白酒", "食品", "饮料", "零售", "电商", "消费"],
            "地产": ["房地产", "地产", "建材", "物业", "住宅"],
            "周期": ["钢铁", "煤炭", "有色", "化工", "建材"]
        }
    
    def link_stocks(self, text: str, event: MarketEvent) -> MarketEvent:
        """识别事件涉及的股票和行业"""
        # 股票名称匹配
        for code, name in self.stock_pool.items():
            if name and len(name) >= 2 and name in text:
                if code not in event.affected_stocks:
                    event.affected_stocks.append(code)
        
        # 行业匹配
        for sector, keywords in self.sector_keywords.items():
            if any(kw in text for kw in keywords):
                if sector not in event.affected_sectors:
                    event.affected_sectors.append(sector)
        
        return event
    
    def generate_event_signals(self, events: List[MarketEvent]) -> List[Dict]:
        """
        将事件转化为量化信号
        返回: Redis总线信号列表
        """
        signals = []
        for evt in events:
            if not evt.affected_stocks:
                continue
            
            # 计算信号强度
            magnitude_map = {"strong": 0.9, "moderate": 0.6, "weak": 0.3}
            confidence = evt.confidence * magnitude_map.get(evt.impact_magnitude, 0.5)
            
            for code in evt.affected_stocks:
                signal = {
                    "type": "event_driven",
                    "source": f"EventClassifier:{evt.event_type}",
                    "stock_code": code,
                    "action": "BUY" if evt.impact_direction == "positive" else
                             "SELL" if evt.impact_direction == "negative" else "HOLD",
                    "confidence": confidence,
                    "event_type": evt.event_type,
                    "causal_chain": evt.causal_chain,
                    "duration": evt.duration_estimate,
                    "timestamp": datetime.now().isoformat()
                }
                signals.append(signal)
        
        return signals


class EventDrivenSentimentPipeline:
    """
    事件驱动舆情管道（V6.0增强版）
    扩展V5.0的SentimentPipeline，增加事件识别
    """
    
    def __init__(self, stock_pool: Dict[str, str] = None, config_path: str = "config.json"):
        self.classifier = EventClassifier()
        self.stock_pool = stock_pool or self._default_stock_pool()
        self.linker = EntityLinker(self.stock_pool)
        self.recent_events: List[MarketEvent] = []
        self.max_events = 200
    
    def _default_stock_pool(self) -> Dict[str, str]:
        """默认股票池"""
        return {
            "600519": "贵州茅台", "000858": "五粮液", "300750": "宁德时代",
            "688981": "中芯国际", "601318": "中国平安", "600036": "招商银行",
            "002415": "海康威视", "600900": "长江电力", "000333": "美的集团",
            "600276": "恒瑞医药", "601888": "中国中免", "601166": "兴业银行",
            "300014": "亿纬锂能", "002594": "比亚迪", "600887": "伊利股份"
        }
    
    def process_news_with_events(self, news_items: List[Dict]) -> Dict:
        """
        处理新闻列表，提取事件+情绪信号
        news_items: [{"title": ..., "content": ..., "source": ...}]
        """
        events = []
        for item in news_items:
            text = item.get("content", "") + " " + item.get("title", "")
            event = self.classifier.classify(text, item.get("title", ""))
            if event:
                event.source = item.get("source", "")
                event = self.linker.link_stocks(text, event)
                events.append(event)
        
        # 更新事件缓存
        self.recent_events.extend(events)
        self.recent_events = self.recent_events[-self.max_events:]
        
        # 生成信号
        signals = self.linker.generate_event_signals(events)
        
        return {
            "new_events": len(events),
            "total_events": len(self.recent_events),
            "signals": signals,
            "events": [
                {
                    "id": e.event_id, "type": e.event_type, "title": e.title,
                    "direction": e.impact_direction, "magnitude": e.impact_magnitude,
                    "affected_stocks": e.affected_stocks, "causal_chain": e.causal_chain
                } for e in events
            ]
        }
    
    def get_dashboard_data(self) -> Dict:
        """看板V3.0舆情面板数据（含事件列表）"""
        event_type_counts = {}
        for evt in self.recent_events:
            event_type_counts[evt.event_type] = event_type_counts.get(evt.event_type, 0) + 1
        
        return {
            "event_count": len(self.recent_events),
            "event_type_distribution": event_type_counts,
            "recent_events": [
                {"type": e.event_type, "title": e.title, "direction": e.impact_direction,
                 "stocks": e.affected_stocks[:3], "chain": e.causal_chain[:80]}
                for e in self.recent_events[-10:]
            ]
        }


# ═══════════════════════════════════════════════════════════════
# V5.0 基础部分（兼容性保留）
# ═══════════════════════════════════════════════════════════════

class SentimentPipeline:
    """V5.0 基础情绪分析管道（保留兼容）"""
    
    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            self.config = json.load(f)
        self.sentiment_config = self.config.get("sentiment_analysis", {})
        
        # 情绪词典（简化版）
        self.positive_words = ["上涨", "利好", "增长", "突破", "超预期", "看好"]
        self.negative_words = ["下跌", "利空", "下滑", "跌破", "低于预期", "看空"]
    
    def analyze_text(self, text: str) -> float:
        """简单的情绪评分（-1到+1）"""
        score = 0
        for word in self.positive_words:
            if word in text:
                score += 0.1
        for word in self.negative_words:
            if word in text:
                score -= 0.1
        return max(-1, min(1, score))
    
    def get_dashboard_data(self) -> Dict:
        """看板数据（V5.0兼容）"""
        return {
            "sentiment_score": 0.3,
            "bullish_ratio": 0.6,
            "bearish_ratio": 0.3,
            "neutral_ratio": 0.1,
            "hot_topics": ["新能源", "AI芯片", "消费复苏"]
        }


# 统一导出
__all__ = [
    'SentimentPipeline',           # V5.0基础
    'EventDrivenSentimentPipeline', # V6.0增强
    'EventClassifier',
    'EntityLinker',
    'MarketEvent'
]
