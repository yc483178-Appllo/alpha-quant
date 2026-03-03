#!/usr/bin/env python3
"""
Alpha-Review: 复盘分析师
负责每日复盘和策略优化
"""

import json
import pandas as pd
from datetime import datetime, timedelta
from loguru import logger
from core.agent_bus import AgentBus
from core.strategy_evolution import StrategyEvolution
from core.knowledge_base import KnowledgeBase

class AlphaReview:
    """复盘分析师 - 团队的'大脑后台'"""
    
    def __init__(self):
        self.bus = AgentBus()
        self.evolution = StrategyEvolution()
        self.kb = KnowledgeBase()
        self.knowledge_base = []  # 兼容旧代码
        
    def daily_review(self, trades, market_data):
        """每日复盘 - 15:10执行"""
        logger.info("[Review] 开始生成每日复盘报告")
        
        report = {
            "date": datetime.now().strftime('%Y-%m-%d'),
            "sections": {}
        }
        
        # 十维分析框架
        report["sections"]["market_review"] = self._market_review(market_data)
        report["sections"]["trade_review"] = self._trade_review(trades)
        report["sections"]["signal_quality"] = self._signal_quality_analysis(trades)
        report["sections"]["strategy_performance"] = self._strategy_performance()
        report["sections"]["risk_review"] = self._risk_review(trades)
        report["sections"]["agent_performance"] = self._agent_performance()
        report["sections"]["prediction_accuracy"] = self._prediction_accuracy()
        report["sections"]["tomorrow_candidates"] = self._tomorrow_candidates()
        report["sections"]["strategy_suggestions"] = self._strategy_suggestions()
        report["sections"]["knowledge_base"] = self._update_knowledge_base()
        
        # 发送复盘报告给Chief
        self.bus.publish("review", {
            "from": "Review",
            "type": "daily_report",
            "data": report
        })
        
        logger.info("[Review] 每日复盘报告已生成")
        return report
    
    def _market_review(self, market_data):
        """大盘环境回顾"""
        return {
            "summary": "大盘震荡整理",
            "key_events": ["英伟达财报超预期", "北向资金持续流入"],
            "sentiment": "中性偏谨慎"
        }
    
    def _trade_review(self, trades):
        """持仓表现评分"""
        if not trades:
            return {"message": "今日无交易"}
        
        total_trades = len(trades)
        profitable = len([t for t in trades if t.get("pnl", 0) > 0])
        
        return {
            "total_trades": total_trades,
            "profitable": profitable,
            "win_rate": f"{profitable/total_trades*100:.1f}%" if total_trades > 0 else "N/A"
        }
    
    def _signal_quality_analysis(self, trades):
        """信号质量评估"""
        return {
            "hit_rate": "75%",
            "avg_return": "+2.3%",
            "max_drawdown": "-1.5%"
        }
    
    def _strategy_performance(self):
        """策略贡献度"""
        return {
            "momentum": {"return": "+3.2%", "contribution": "40%"},
            "trend": {"return": "+1.8%", "contribution": "30%"},
            "value": {"return": "+0.9%", "contribution": "20%"},
            "composite": {"return": "+0.5%", "contribution": "10%"}
        }
    
    def _risk_review(self, trades):
        """风控触发回顾"""
        return {
            "stop_loss_triggered": 0,
            "take_profit_triggered": 2,
            "position_limit_warnings": 1
        }
    
    def _agent_performance(self):
        """Agent协作评估"""
        return {
            "Scout": {"score": 8.5, "comment": "情报准确及时"},
            "Picker": {"score": 8.0, "comment": "选股命中率良好"},
            "Guard": {"score": 9.0, "comment": "风控执行到位"},
            "Trader": {"score": 8.5, "comment": "执行无滑点"}
        }
    
    def _prediction_accuracy(self):
        """预测准确率"""
        return {
            "market_direction": "70%",
            "sector_rotation": "65%",
            "stock_selection": "75%"
        }
    
    def _tomorrow_candidates(self):
        """明日标的候选"""
        return {
            "watchlist": ["AI算力", "存储芯片", "通信设备"],
            "strategy": "关注硬科技主线"
        }
    
    def _strategy_suggestions(self):
        """策略迭代建议"""
        return [
            "动量策略参数可适当放宽",
            "增加盘中止损触发频率",
            "Scout情报可增加外围市场权重"
        ]
    
    def _update_knowledge_base(self):
        """知识库更新 - 使用KnowledgeBase模块"""
        # 添加示例知识条目
        new_entries = [
            self.kb.add("pattern", "英伟达财报后A股AI板块通常有3天行情",
                       "历史3次英伟达超预期财报后，A股AI算力板块3日内平均涨幅5%", 
                       0.75, "美股科技股龙头财报超预期后首个交易日"),
            self.kb.add("insight", "震荡市value策略胜率最高",
                       "回测显示震荡市期间价值策略胜率58%，高于动量策略45%",
                       0.82, "市场处于震荡阶段时")
        ]
        
        # 兼容旧代码返回格式
        return new_entries[0] if new_entries else {}
    
    def weekly_strategy_review(self):
        """每周策略大阅兵 - 周五16:00执行"""
        logger.info("[Review] 执行周度策略评估（使用StrategyEvolution引擎）")
        
        # 获取各策略的实际表现数据（模拟数据）
        all_metrics = {
            "momentum": {"win_rate": 0.58, "sharpe": 1.5, "max_dd": -0.12, "profit_factor": 1.9},
            "value": {"win_rate": 0.52, "sharpe": 0.8, "max_dd": -0.08, "profit_factor": 1.5},
            "trend": {"win_rate": 0.42, "sharpe": 0.3, "max_dd": -0.22, "profit_factor": 0.9},
            "reversal": {"win_rate": 0.55, "sharpe": 1.1, "max_dd": -0.10, "profit_factor": 1.6},
            "composite": {"win_rate": 0.60, "sharpe": 1.8, "max_dd": -0.06, "profit_factor": 2.1},
        }
        
        # 使用StrategyEvolution进行评估
        evolution_report = self.evolution.weekly_review(all_metrics)
        
        # 生成推荐建议
        recommendations = []
        for name, data in evolution_report["strategies"].items():
            if data["status"] == "healthy":
                recommendations.append(f"{name}策略表现良好，建议维持")
            elif data["status"] == "warning":
                recommendations.append(f"{name}策略需关注: {', '.join(data['issues'])}")
            else:
                recommendations.append(f"{name}策略严重告警，建议暂停")
        
        report = {
            "week": datetime.now().strftime('%Y-W%U'),
            "evolution_report": evolution_report,
            "recommendations": recommendations
        }
        
        # 发送给Chief
        self.bus.publish("review", {
            "from": "Review",
            "type": "weekly_report",
            "data": report
        })
        
        logger.info(f"[Review] 策略健康度: {evolution_report['summary']['overall_health']}")
        return report
        
        # 发送给Chief
        self.bus.publish("review", {
            "from": "Review",
            "type": "weekly_report",
            "data": report
        })
        
        return report

if __name__ == "__main__":
    review = AlphaReview()
    review.daily_review([], {})
