"""
金融舆情分析管道
多源数据采集 → 中文NLP情绪分析 → 信号生成
兼容 V4.0 Scout Agent 和信号总线
"""

import json
import math
import re
import os
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, List, Optional
from dataclasses import dataclass
from loguru import logger

# ===== 金融情感词典 =====
POSITIVE_WORDS = {
    "利好": 0.8, "突破": 0.6, "涨停": 0.9, "放量": 0.5, "新高": 0.7,
    "大涨": 0.8, "利多": 0.7, "看多": 0.6, "底部": 0.5, "反弹": 0.5,
    "增持": 0.7, "回购": 0.6, "超预期": 0.8, "景气": 0.6, "龙头": 0.5,
    "翻倍": 0.9, "强势": 0.6, "突破新高": 0.8, "主力加仓": 0.7,
    "业绩暴增": 0.9, "订单爆满": 0.8, "国产替代": 0.6, "政策扶持": 0.7,
}

NEGATIVE_WORDS = {
    "利空": -0.8, "跌停": -0.9, "暴跌": -0.9, "减持": -0.7, "亏损": -0.8,
    "退市": -1.0, "爆雷": -0.9, "崩盘": -0.9, "割肉": -0.6, "套牢": -0.5,
    "ST": -0.8, "违规": -0.7, "处罚": -0.6, "下跌": -0.5, "缩量": -0.4,
    "资金外流": -0.7, "业绩变脸": -0.8, "商誉减值": -0.7, "质押爆仓": -0.9,
    "监管问询": -0.6, "高管离职": -0.5, "产品召回": -0.7,
}

STOCK_CODE_PATTERN = re.compile(r'[036]\d{5}')


@dataclass
class SentimentResult:
    """情感分析结果"""
    score: float  # -1 to 1
    sentiment: str  # bullish/bearish/neutral
    hit_count: int
    related_codes: List[str]
    confidence: float


@dataclass
class StockSentiment:
    """个股情绪数据"""
    code: str
    score: float
    momentum: float
    news_count: int
    signal: str
    timestamp: str


@dataclass
class SectorSentiment:
    """板块情绪数据"""
    sector: str
    score: float
    rank: int
    top_stocks: List[str]


class SentimentAnalyzer:
    """基于词典的金融情感分析器（无需GPU/大模型依赖）"""

    def __init__(self):
        self.positive = POSITIVE_WORDS
        self.negative = NEGATIVE_WORDS

    def analyze_text(self, text: str) -> SentimentResult:
        """分析单条文本的情绪分数"""
        if not text:
            return SentimentResult(0.0, "neutral", 0, [], 0.0)
        
        score = 0.0
        hit_count = 0
        
        # 正面词匹配
        for word, weight in self.positive.items():
            if word in text:
                score += weight
                hit_count += 1
        
        # 负面词匹配
        for word, weight in self.negative.items():
            if word in text:
                score += weight
                hit_count += 1
        
        # 归一化到 [-1, 1]
        if hit_count > 0:
            score = max(-1.0, min(1.0, score / max(hit_count, 1)))
        
        # 提取相关股票代码
        codes = STOCK_CODE_PATTERN.findall(text)
        
        # 置信度基于命中次数
        confidence = min(hit_count * 0.2, 1.0)
        
        sentiment = "bullish" if score > 0.2 else ("bearish" if score < -0.2 else "neutral")
        
        return SentimentResult(
            score=round(score, 4),
            sentiment=sentiment,
            hit_count=hit_count,
            related_codes=list(set(codes)),
            confidence=round(confidence, 4)
        )


class SentimentPipeline:
    """舆情分析管道主类 - V5.0 Sentiment Agent"""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        with open(config_path) as f:
            config = json.load(f)
        
        self.cfg = config.get("sentiment_analysis", {})
        self.enabled = self.cfg.get("enabled", True)
        self.analyzer = SentimentAnalyzer()
        self.lookback_days = self.cfg.get("lookback_days", 30)
        self.half_life = self.cfg.get("time_decay_half_life_days", 7)
        self.bullish_threshold = self.cfg.get("bullish_threshold", 0.3)
        self.bearish_threshold = self.cfg.get("bearish_threshold", -0.3)
        
        # 情绪历史存储
        self.sentiment_history = defaultdict(list)
        
        # 板块映射配置
        self.sector_map = self.cfg.get("sector_mapping", {
            "银行": ["601398", "601288", "600036", "000001"],
            "新能源": ["300750", "601012", "002594", "600438"],
            "科技": ["002415", "000725", "603501", "002236"],
            "消费": ["600519", "000858", "603288", "002714"],
            "医药": ["603259", "000538", "300760", "002007"],
            "地产": ["001979", "600048", "000002", "600383"]
        })
        
        logger.info(f"✅ Sentiment Pipeline初始化完成 | enabled={self.enabled}")

    def _time_decay_weight(self, days_ago: int) -> float:
        """时间衰减权重（指数衰减）"""
        return math.exp(-0.693 * days_ago / self.half_life)

    def process_news_batch(self, news_items: List[Dict]) -> List[Dict]:
        """
        批量处理新闻数据
        
        Args:
            news_items: [{"title": str, "content": str, "source": str, "pub_date": str}, ...]
        
        Returns:
            List[Dict]: 分析结果列表
        """
        if not self.enabled:
            logger.warning("⚠️ Sentiment Pipeline未启用")
            return []
        
        results = []
        source_weights = self.cfg.get("source_weights", {
            "analyst_reports": 0.6,
            "major_news": 0.3,
            "social_sentiment": 0.1
        })
        
        for item in news_items:
            text = f"{item.get('title', '')} {item.get('content', '')}"
            analysis = self.analyzer.analyze_text(text)
            
            # 来源加权
            source = item.get("source", "major_news")
            source_w = source_weights.get(source, 0.3)
            
            # 时间衰减
            pub_date = item.get("pub_date", datetime.now().isoformat())
            try:
                dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                days_ago = (datetime.now() - dt.replace(tzinfo=None)).days
            except:
                days_ago = 0
            time_w = self._time_decay_weight(days_ago)
            
            # 综合得分
            weighted_score = analysis.score * source_w * time_w
            
            result = {
                "title": item.get("title", ""),
                "source": source,
                "raw_score": analysis.score,
                "weighted_score": round(weighted_score, 4),
                "sentiment": analysis.sentiment,
                "related_codes": analysis.related_codes,
                "confidence": analysis.confidence,
                "pub_date": pub_date,
                "days_ago": days_ago
            }
            results.append(result)
            
            # 存储到历史
            for code in analysis.related_codes:
                self.sentiment_history[code].append({
                    "score": weighted_score,
                    "date": pub_date,
                    "title": item.get("title", "")
                })
        
        logger.info(f"📰 处理新闻 {len(news_items)}条，生成分析结果 {len(results)}条")
        return results

    def get_stock_sentiment(self, stock_code: str) -> StockSentiment:
        """获取个股综合情绪评分"""
        history = self.sentiment_history.get(stock_code, [])
        
        if not history:
            return StockSentiment(
                code=stock_code,
                score=0.0,
                momentum=0.0,
                news_count=0,
                signal="neutral",
                timestamp=datetime.now().isoformat()
            )
        
        scores = [h["score"] for h in history]
        avg_score = sum(scores) / len(scores)
        
        # 情绪动量（近5天 vs 近20天）
        recent = scores[-5:] if len(scores) >= 5 else scores
        older = scores[-20:-5] if len(scores) >= 20 else scores[:max(1, len(scores)-5)]
        momentum = (sum(recent)/len(recent)) - (sum(older)/len(older)) if older else 0
        
        # 信号判定
        if avg_score > self.bullish_threshold and momentum > 0:
            signal = "strong_bullish"
        elif avg_score > self.bullish_threshold:
            signal = "bullish"
        elif avg_score < self.bearish_threshold and momentum < 0:
            signal = "strong_bearish"
        elif avg_score < self.bearish_threshold:
            signal = "bearish"
        else:
            signal = "neutral"
        
        return StockSentiment(
            code=stock_code,
            score=round(avg_score, 4),
            momentum=round(momentum, 4),
            news_count=len(history),
            signal=signal,
            timestamp=datetime.now().isoformat()
        )

    def get_sector_sentiment(self) -> Dict[str, float]:
        """获取行业板块情绪排名"""
        sector_scores = {}
        
        for sector, codes in self.sector_map.items():
            scores = []
            for code in codes:
                s = self.get_stock_sentiment(code)
                if s.news_count > 0:
                    scores.append(s.score)
            
            if scores:
                sector_scores[sector] = round(sum(scores) / len(scores), 4)
            else:
                sector_scores[sector] = 0.0
        
        return dict(sorted(sector_scores.items(), key=lambda x: x[1], reverse=True))

    def generate_sentiment_signals(self, stock_pool: List[str]) -> List[Dict]:
        """为股票池生成情绪交易信号（接入信号总线）"""
        signals = []
        
        for code in stock_pool:
            sentiment = self.get_stock_sentiment(code)
            
            if sentiment.signal in ("strong_bullish", "strong_bearish"):
                signals.append({
                    "type": "sentiment_signal",
                    "source": "Alpha-Sentiment",
                    "code": code,
                    "action": "buy" if "bullish" in sentiment.signal else "sell",
                    "strength": "strong",
                    "sentiment_score": sentiment.score,
                    "sentiment_momentum": sentiment.momentum,
                    "confidence": min(abs(sentiment.score), 1.0),
                    "timestamp": datetime.now().isoformat()
                })
        
        logger.info(f"📊 舆情信号生成完毕: {len(signals)}条强信号")
        return signals

    def generate_scout_report(self, stock_pool: List[str]) -> Dict:
        """生成Scout Agent盘前舆情报告"""
        report = {
            "report_type": "sentiment_morning_brief",
            "generated_at": datetime.now().isoformat(),
            "market_sentiment_overview": {},
            "top_bullish": [],
            "top_bearish": [],
            "sector_ranking": self.get_sector_sentiment(),
            "anomaly_alerts": [],
            "total_news_processed": sum(len(v) for v in self.sentiment_history.values())
        }
        
        all_sentiments = []
        for code in stock_pool:
            s = self.get_stock_sentiment(code)
            all_sentiments.append({
                "code": code,
                "score": s.score,
                "momentum": s.momentum,
                "news_count": s.news_count,
                "signal": s.signal
            })
        
        # 排序
        sorted_by_score = sorted(all_sentiments, key=lambda x: x["score"], reverse=True)
        report["top_bullish"] = sorted_by_score[:5]
        report["top_bearish"] = sorted_by_score[-5:]
        
        # 计算市场整体情绪
        if all_sentiments:
            avg_score = sum(s["score"] for s in all_sentiments) / len(all_sentiments)
            report["market_sentiment_overview"] = {
                "average_score": round(avg_score, 4),
                "bullish_count": len([s for s in all_sentiments if s["score"] > 0.2]),
                "bearish_count": len([s for s in all_sentiments if s["score"] < -0.2]),
                "neutral_count": len([s for s in all_sentiments if -0.2 <= s["score"] <= 0.2])
            }
        
        # 异常检测：情绪突变
        for s in all_sentiments:
            if abs(s["momentum"]) > 0.3:
                report["anomaly_alerts"].append({
                    "code": s["code"],
                    "type": "sentiment_spike_up" if s["momentum"] > 0 else "sentiment_spike_down",
                    "magnitude": abs(s["momentum"]),
                    "current_score": s["score"]
                })
        
        return report

    def generate_sentiment_report_for_chief(self) -> Dict:
        """
        生成Chief Agent所需的SentimentReport格式
        
        Returns:
            Dict: 符合chief_agent.SentimentReport格式的数据
        """
        sector_sentiment = self.get_sector_sentiment()
        
        # 计算整体情绪
        all_scores = list(sector_sentiment.values())
        overall_sentiment = sum(all_scores) / len(all_scores) if all_scores else 0.0
        
        # 获取热点话题（从新闻标题中提取）
        hot_topics = []
        for code, history in list(self.sentiment_history.items())[:10]:
            for h in history[-5:]:  # 最近5条
                if h.get("title"):
                    hot_topics.append(h["title"])
        
        # 风险警报
        risk_alerts = []
        for code, history in self.sentiment_history.items():
            if len(history) >= 2:
                recent = history[-1]["score"]
                if recent < -0.5:
                    risk_alerts.append(f"{code} 情绪极度悲观")
        
        return {
            "overall_sentiment": overall_sentiment,
            "sector_sentiment": sector_sentiment,
            "hot_topics": hot_topics[:10],
            "risk_alerts": risk_alerts,
            "timestamp": datetime.now().isoformat()
        }

    def clear_history(self, days: int = 30):
        """清理过期历史数据"""
        cutoff = datetime.now() - timedelta(days=days)
        
        for code in list(self.sentiment_history.keys()):
            self.sentiment_history[code] = [
                h for h in self.sentiment_history[code]
                if datetime.fromisoformat(h["date"].replace("Z", "+00:00")) > cutoff
            ]
        
        logger.info(f"🧹 清理情绪历史数据，保留最近{days}天")


# 便捷函数
def create_sentiment_pipeline(config_path: str = "config.json") -> SentimentPipeline:
    """创建Sentiment Pipeline实例"""
    return SentimentPipeline(config_path)


def analyze_text_quick(text: str) -> Dict:
    """快速分析文本情绪"""
    analyzer = SentimentAnalyzer()
    result = analyzer.analyze_text(text)
    return {
        "score": result.score,
        "sentiment": result.sentiment,
        "confidence": result.confidence,
        "related_codes": result.related_codes
    }


if __name__ == "__main__":
    # 测试Sentiment Pipeline
    print("测试金融舆情分析管道...")
    
    pipeline = create_sentiment_pipeline()
    
    # 测试文本分析
    test_text = "宁德时代发布超预期财报，业绩暴增，主力加仓，股价突破新高"
    result = analyze_text_quick(test_text)
    print(f"\n文本分析: {test_text}")
    print(f"  情绪分数: {result['score']:+.2f}")
    print(f"  情绪标签: {result['sentiment']}")
    print(f"  相关股票: {result['related_codes']}")
    
    # 测试新闻批量处理
    news_items = [
        {
            "title": "固态电池技术突破，行业迎来大利好",
            "content": "多家企业宣布固态电池量产计划",
            "source": "major_news",
            "pub_date": datetime.now().isoformat()
        },
        {
            "title": "某科技股业绩变脸，商誉减值超10亿",
            "content": "公司股价跌停，投资者恐慌",
            "source": "major_news",
            "pub_date": datetime.now().isoformat()
        }
    ]
    
    results = pipeline.process_news_batch(news_items)
    print(f"\n新闻批量处理: {len(results)}条")
    for r in results:
        print(f"  {r['title'][:20]}... | 分数: {r['raw_score']:+.2f} | 情绪: {r['sentiment']}")
    
    # 测试板块情绪
    sector_scores = pipeline.get_sector_sentiment()
    print(f"\n板块情绪排名:")
    for sector, score in list(sector_scores.items())[:5]:
        print(f"  {sector}: {score:+.2f}")
    
    print("\n✅ Sentiment Pipeline测试完成")
