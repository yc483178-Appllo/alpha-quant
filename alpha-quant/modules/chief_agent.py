#!/usr/bin/env python3
"""
Alpha V5.0 - Chief Agent 决策引擎
整合DRL建议、组合优化、风控检查，输出最终交易决策
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from loguru import logger

# 导入DRL Agent
from modules.drl_portfolio_agent import DRLPortfolioAgent


@dataclass
class ScoutReport:
    """Scout盘前报告"""
    market_regime: str  # bear/bull/neutral
    index_data: Dict
    sector_hotspot: List[Dict]
    risk_signals: List[str]
    timestamp: str


@dataclass
class SentimentReport:
    """Sentiment舆情报告"""
    overall_sentiment: float  # -1 to 1
    sector_sentiment: Dict[str, float]
    hot_topics: List[str]
    risk_alerts: List[str]
    timestamp: str


@dataclass
class PickerList:
    """Picker选股清单"""
    selected_stocks: List[Dict]
    selection_reason: str
    timestamp: str


@dataclass
class DRLRecommendation:
    """DRL Agent建议"""
    weights: List[float]
    confidence: float
    expected_value: float
    timestamp: str


@dataclass
class OptimizerRecommendation:
    """组合优化器建议"""
    weights: List[float]
    expected_return: float
    expected_risk: float
    sharpe_ratio: float
    timestamp: str


@dataclass
class GuardCheckResult:
    """Guard风控检查结果"""
    passed: bool
    risk_level: str  # low/medium/high/critical
    warnings: List[str]
    max_position_size: float
    timestamp: str


@dataclass
class ChiefDecision:
    """Chief最终决策"""
    decision_id: str
    timestamp: str
    final_weights: List[float]
    decision_source: str  # drl/optimizer/conservative
    confidence: float
    risk_level: str
    execution_plan: List[Dict]
    reasoning: str


class ChiefAgent:
    """
    Chief Agent - V5.0决策核心
    
    决策流程：
    1. 接收 Scout 盘前报告 + Sentiment 舆情报告
    2. 接收 Picker 选股清单
    3. 接收 DRL Agent 组合权重建议（含置信度）
    4. 接收 Portfolio Optimizer 优化建议
    5. Guard 风控预检
    6. Chief 综合决策
    7. 下发执行指令给 Trader
    """
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        
        # 初始化DRL Agent
        self.drl_agent = None
        if self.config.get("drl_portfolio", {}).get("enabled", False):
            try:
                self.drl_agent = DRLPortfolioAgent(config_path)
                logger.info("✅ Chief Agent: DRL Agent初始化成功")
            except Exception as e:
                logger.error(f"❌ Chief Agent: DRL Agent初始化失败: {e}")
        
        # 决策历史
        self.decision_history: List[ChiefDecision] = []
        
        # 决策阈值配置
        self.thresholds = {
            "drl_high_confidence": 0.7,
            "drl_low_confidence": 0.5,
            "max_single_position": 0.20,
            "max_total_position": 0.80,
            "risk_conservative_factor": 0.8
        }
    
    def _load_config(self) -> Dict:
        """加载配置"""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"加载配置失败: {e}")
            return {}
    
    def make_decision(
        self,
        scout_report: ScoutReport,
        sentiment_report: SentimentReport,
        picker_list: PickerList,
        current_portfolio: Optional[Dict] = None
    ) -> ChiefDecision:
        """
        执行完整决策流程
        
        Args:
            scout_report: Scout盘前报告
            sentiment_report: Sentiment舆情报告
            picker_list: Picker选股清单
            current_portfolio: 当前持仓（可选）
        
        Returns:
            ChiefDecision: 最终决策
        """
        decision_id = f"DEC{datetime.now().strftime('%Y%m%d%H%M%S')}"
        logger.info(f"🧠 Chief Agent开始决策 | ID: {decision_id}")
        
        # Step 1-2: 记录输入报告
        self._log_inputs(scout_report, sentiment_report, picker_list)
        
        # Step 3: 获取DRL建议
        drl_rec = self._get_drl_recommendation(picker_list, scout_report, sentiment_report)
        
        # Step 4: 获取组合优化器建议（简化版，实际可接入Black-Litterman等）
        optimizer_rec = self._get_optimizer_recommendation(picker_list, scout_report)
        
        # Step 5: Guard风控预检
        guard_result = self._guard_precheck(
            drl_rec, optimizer_rec, scout_report, sentiment_report
        )
        
        # Step 6: Chief综合决策
        final_weights, decision_source, confidence, reasoning = self._combine_decisions(
            drl_rec, optimizer_rec, guard_result
        )
        
        # Step 7: 生成执行计划
        execution_plan = self._generate_execution_plan(
            final_weights, current_portfolio, picker_list
        )
        
        # 创建决策对象
        decision = ChiefDecision(
            decision_id=decision_id,
            timestamp=datetime.now().isoformat(),
            final_weights=final_weights,
            decision_source=decision_source,
            confidence=confidence,
            risk_level=guard_result.risk_level,
            execution_plan=execution_plan,
            reasoning=reasoning
        )
        
        # 保存决策历史
        self.decision_history.append(decision)
        
        # 记录决策结果
        self._log_decision(decision)
        
        return decision
    
    def _log_inputs(self, scout: ScoutReport, sentiment: SentimentReport, picker: PickerList):
        """记录输入信息"""
        logger.info(f"📊 Scout报告: 市场环境={scout.market_regime}, 风险信号={len(scout.risk_signals)}个")
        logger.info(f"📰 Sentiment报告: 整体情绪={sentiment.overall_sentiment:.2f}")
        logger.info(f"📋 Picker选股: {len(picker.selected_stocks)}只股票")
    
    def _get_drl_recommendation(
        self,
        picker_list: PickerList,
        scout_report: ScoutReport,
        sentiment_report: SentimentReport
    ) -> Optional[DRLRecommendation]:
        """获取DRL Agent建议"""
        if not self.drl_agent or not self.drl_agent.enabled:
            logger.warning("⚠️ DRL Agent未启用，跳过DRL建议")
            return None
        
        try:
            # 构建股票特征
            stock_features = []
            for stock in picker_list.selected_stocks[:self.drl_agent.env.max_positions]:
                # 从选股结果提取特征（实际应从data_provider获取）
                stock_features.append({
                    "price_change_5d": stock.get("change_5d", 0.0),
                    "price_change_20d": stock.get("change_20d", 0.0),
                    "volatility_20d": stock.get("volatility", 0.02),
                    "volume_ratio": stock.get("volume_ratio", 1.0),
                    "turnover_rate": stock.get("turnover", 0.03),
                    "rsi_14": stock.get("rsi", 50.0),
                    "macd_histogram": stock.get("macd", 0.0),
                    "sentiment_score": sentiment_report.sector_sentiment.get(
                        stock.get("sector", ""), sentiment_report.overall_sentiment
                    )
                })
            
            # 填充剩余位置
            while len(stock_features) < self.drl_agent.env.max_positions:
                stock_features.append({
                    "price_change_5d": 0, "price_change_20d": 0, "volatility_20d": 0,
                    "volume_ratio": 1.0, "turnover_rate": 0, "rsi_14": 50,
                    "macd_histogram": 0, "sentiment_score": 0
                })
            
            # 全局特征
            regime_map = {"bear": 0.0, "neutral": 1.0, "bull": 2.0}
            global_features = {
                "market_regime": regime_map.get(scout_report.market_regime, 1.0),
                "portfolio_sharpe": 1.0,  # 应从当前组合计算
                "portfolio_drawdown": -0.02,  # 应从当前组合计算
                "cash_ratio": 0.3,  # 应从当前组合计算
                "total_position_pct": 0.7  # 应从当前组合计算
            }
            
            # 构建状态并预测
            state = self.drl_agent.get_state_from_market_data(stock_features, global_features)
            result = self.drl_agent.predict_portfolio_weights(state)
            
            if result:
                rec = DRLRecommendation(
                    weights=result["recommended_weights"],
                    confidence=result["confidence"],
                    expected_value=result["expected_value"],
                    timestamp=result["timestamp"]
                )
                logger.info(f"🤖 DRL建议: 置信度={rec.confidence:.4f}, 预期价值={rec.expected_value:.4f}")
                return rec
            
        except Exception as e:
            logger.error(f"❌ DRL建议获取失败: {e}")
        
        return None
    
    def _get_optimizer_recommendation(
        self,
        picker_list: PickerList,
        scout_report: ScoutReport
    ) -> OptimizerRecommendation:
        """获取组合优化器建议（简化版等权配置）"""
        n_stocks = len(picker_list.selected_stocks)
        if n_stocks == 0:
            weights = []
        else:
            # 等权配置作为基准
            weight = 1.0 / n_stocks
            weights = [weight] * n_stocks
            # 填充到max_positions
            weights.extend([0.0] * (30 - len(weights)))
        
        rec = OptimizerRecommendation(
            weights=weights[:30],
            expected_return=0.10,  # 假设年化10%
            expected_risk=0.15,    # 假设年化波动15%
            sharpe_ratio=0.67,
            timestamp=datetime.now().isoformat()
        )
        
        logger.info(f"📐 Optimizer建议: 等权配置, 预期Sharpe={rec.sharpe_ratio:.2f}")
        return rec
    
    def _guard_precheck(
        self,
        drl_rec: Optional[DRLRecommendation],
        optimizer_rec: OptimizerRecommendation,
        scout_report: ScoutReport,
        sentiment_report: SentimentReport
    ) -> GuardCheckResult:
        """Guard风控预检"""
        warnings = []
        risk_level = "low"
        
        # 检查1: 市场环境
        if scout_report.market_regime == "bear":
            warnings.append("熊市环境，建议降低仓位")
            risk_level = "high"
        elif scout_report.market_regime == "neutral":
            risk_level = "medium"
        
        # 检查2: 舆情风险
        if sentiment_report.overall_sentiment < -0.3:
            warnings.append("市场情绪极度悲观")
            risk_level = "high"
        elif sentiment_report.overall_sentiment < 0:
            warnings.append("市场情绪偏空")
            if risk_level == "low":
                risk_level = "medium"
        
        # 检查3: Scout风险信号
        if scout_report.risk_signals:
            warnings.extend(scout_report.risk_signals)
            if len(scout_report.risk_signals) >= 3:
                risk_level = "critical"
            elif risk_level != "critical":
                risk_level = "high"
        
        # 检查4: DRL置信度
        if drl_rec and drl_rec.confidence < 0.5:
            warnings.append(f"DRL置信度低({drl_rec.confidence:.2f})")
        
        # 计算最大仓位限制
        max_position = self.thresholds["max_single_position"]
        if risk_level == "high":
            max_position *= self.thresholds["risk_conservative_factor"]
        elif risk_level == "critical":
            max_position *= 0.5
        
        result = GuardCheckResult(
            passed=risk_level != "critical",
            risk_level=risk_level,
            warnings=warnings,
            max_position_size=max_position,
            timestamp=datetime.now().isoformat()
        )
        
        logger.info(f"🛡️ Guard检查: 通过={result.passed}, 风险等级={result.risk_level}, 警告={len(warnings)}个")
        return result
    
    def _combine_decisions(
        self,
        drl_rec: Optional[DRLRecommendation],
        optimizer_rec: OptimizerRecommendation,
        guard_result: GuardCheckResult
    ) -> Tuple[List[float], str, float, str]:
        """
        综合决策逻辑
        
        规则:
        - 若 DRL 置信度 > 0.7 且 Guard 通过 → 采纳 DRL 权重
        - 若 DRL 置信度 < 0.5 → 使用 Portfolio Optimizer 建议
        - 若两者冲突 → 取保守方案（仓位较低者）
        """
        reasoning_parts = []
        
        # 情况1: DRL高置信度 + Guard通过
        if (drl_rec and 
            drl_rec.confidence > self.thresholds["drl_high_confidence"] and 
            guard_result.passed and
            guard_result.risk_level in ["low", "medium"]):
            
            final_weights = drl_rec.weights
            decision_source = "drl"
            confidence = drl_rec.confidence
            reasoning_parts.append(f"DRL置信度高({drl_rec.confidence:.2f})，采纳DRL建议")
        
        # 情况2: DRL低置信度
        elif drl_rec and drl_rec.confidence < self.thresholds["drl_low_confidence"]:
            final_weights = optimizer_rec.weights
            decision_source = "optimizer"
            confidence = 0.6  # 基准置信度
            reasoning_parts.append(f"DRL置信度低({drl_rec.confidence:.2f})，使用Optimizer建议")
        
        # 情况3: 两者冲突或中间状态 → 取保守方案
        else:
            if drl_rec:
                # 取仓位较低者
                drl_position = sum(abs(w) for w in drl_rec.weights)
                opt_position = sum(abs(w) for w in optimizer_rec.weights)
                
                if drl_position < opt_position:
                    final_weights = drl_rec.weights
                    decision_source = "drl_conservative"
                    confidence = drl_rec.confidence * 0.9
                    reasoning_parts.append("DRL与Optimizer冲突，取仓位较低的DRL方案")
                else:
                    final_weights = optimizer_rec.weights
                    decision_source = "optimizer_conservative"
                    confidence = 0.6
                    reasoning_parts.append("DRL与Optimizer冲突，取仓位较低的Optimizer方案")
            else:
                final_weights = optimizer_rec.weights
                decision_source = "optimizer_fallback"
                confidence = 0.5
                reasoning_parts.append("DRL不可用，使用Optimizer作为fallback")
        
        # 应用风控限制
        if guard_result.risk_level in ["high", "critical"]:
            # 降低整体仓位
            position_scale = 0.6 if guard_result.risk_level == "critical" else 0.8
            final_weights = [w * position_scale for w in final_weights]
            reasoning_parts.append(f"因风险等级{guard_result.risk_level}，仓位降至{position_scale*100:.0f}%")
        
        # 应用单股仓位限制
        max_pos = guard_result.max_position_size
        final_weights = [min(abs(w), max_pos) * (1 if w >= 0 else -1) for w in final_weights]
        
        # 归一化
        total = sum(abs(w) for w in final_weights)
        if total > 1.0:
            final_weights = [w / total for w in final_weights]
        
        reasoning = "; ".join(reasoning_parts)
        logger.info(f"🎯 综合决策: 来源={decision_source}, 置信度={confidence:.2f}")
        
        return final_weights, decision_source, confidence, reasoning
    
    def _generate_execution_plan(
        self,
        final_weights: List[float],
        current_portfolio: Optional[Dict],
        picker_list: PickerList
    ) -> List[Dict]:
        """生成执行计划"""
        plan = []
        
        # 假设总资金100万
        total_capital = 1_000_000
        
        for i, weight in enumerate(final_weights[:len(picker_list.selected_stocks)]):
            if abs(weight) < 0.01:  # 忽略过小仓位
                continue
            
            stock = picker_list.selected_stocks[i]
            target_value = total_capital * abs(weight)
            
            plan.append({
                "stock_code": stock.get("ts_code", ""),
                "stock_name": stock.get("name", ""),
                "action": "buy" if weight > 0 else "sell",
                "target_weight": abs(weight),
                "target_value": target_value,
                "reason": f"Chief决策权重: {weight:.4f}"
            })
        
        logger.info(f"📋 生成执行计划: {len(plan)}笔交易")
        return plan
    
    def _log_decision(self, decision: ChiefDecision):
        """记录决策结果"""
        logger.info(f"✅ Chief决策完成 | ID={decision.decision_id}")
        logger.info(f"   来源: {decision.decision_source}, 置信度: {decision.confidence:.2f}")
        logger.info(f"   风险等级: {decision.risk_level}, 交易笔数: {len(decision.execution_plan)}")
        logger.info(f"   推理: {decision.reasoning}")
    
    def get_decision_history(self, n: int = 10) -> List[ChiefDecision]:
        """获取决策历史"""
        return self.decision_history[-n:]
    
    def generate_signal_for_trader(self, decision: ChiefDecision) -> List[Dict]:
        """
        生成给Trader的信号
        
        Returns:
            List[Dict]: 交易信号列表，可直接发送给signal_server
        """
        signals = []
        
        for item in decision.execution_plan:
            signal = {
                "type": "trade_signal",
                "source": "Chief-Agent",
                "decision_id": decision.decision_id,
                "code": item["stock_code"],
                "action": item["action"],
                "reason": item["reason"],
                "strategy": f"chief_{decision.decision_source}",
                "risk_level": decision.risk_level,
                "confidence": decision.confidence,
                "timestamp": datetime.now().isoformat()
            }
            signals.append(signal)
        
        return signals


# 便捷函数
def create_chief_agent(config_path: str = "config.json") -> ChiefAgent:
    """创建Chief Agent实例"""
    return ChiefAgent(config_path)


if __name__ == "__main__":
    # 测试Chief Agent
    print("测试Chief Agent...")
    
    chief = create_chief_agent()
    
    # 构造测试输入
    scout = ScoutReport(
        market_regime="neutral",
        index_data={"sh": 3000},
        sector_hotspot=[],
        risk_signals=[],
        timestamp=datetime.now().isoformat()
    )
    
    sentiment = SentimentReport(
        overall_sentiment=0.2,
        sector_sentiment={},
        hot_topics=[],
        risk_alerts=[],
        timestamp=datetime.now().isoformat()
    )
    
    picker = PickerList(
        selected_stocks=[
            {"ts_code": "000001.SZ", "name": "平安银行", "sector": "银行"},
            {"ts_code": "000002.SZ", "name": "万科A", "sector": "地产"},
        ],
        selection_reason="测试",
        timestamp=datetime.now().isoformat()
    )
    
    # 执行决策
    decision = chief.make_decision(scout, sentiment, picker)
    
    print(f"\n决策结果:")
    print(f"  ID: {decision.decision_id}")
    print(f"  来源: {decision.decision_source}")
    print(f"  置信度: {decision.confidence}")
    print(f"  风险等级: {decision.risk_level}")
    print(f"  推理: {decision.reasoning}")
    print(f"  执行计划: {len(decision.execution_plan)}笔")
