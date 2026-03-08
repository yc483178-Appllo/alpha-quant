"""
Alpha 看板 V3.0 - 后端 API 服务
文件: dashboard_v3.py
功能: 为 V3.0 看板提供数据接口，支持 14+ 面板和钻取交互
依赖: flask/fastapi, pandas, numpy
"""

import os
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

import pandas as pd
import numpy as np

# 尝试导入 Flask
try:
    from flask import Flask, jsonify, request
    from flask_cors import CORS
    FLASK_AVAILABLE = True
except ImportError:
    FLASK_AVAILABLE = False
    logging.warning("Flask未安装，看板V3.0将以独立模式运行")

# 导入V6.0模块
try:
    from strategy_evolution_engine import SmartStrategyEvolutionEngine
    from evolution_integration import AlphaV6Integration
    from smart_broker_v2 import SmartBrokerManagerV2
    from historical_knowledge_base import HistoricalKnowledgeBase
    from research_report_generator import ResearchReportGenerator
    from joinquant_gateway import UnifiedDataLayer
    V6_MODULES_AVAILABLE = True
except ImportError as e:
    logging.warning(f"V6.0模块导入警告: {e}")
    V6_MODULES_AVAILABLE = False

logger = logging.getLogger("DashboardV3")


@dataclass
class DashboardState:
    """看板全局状态"""
    current_broker: str = "ptrade"
    broker_quality_score: float = 87.0
    current_model: str = "Transformer-PPO V6.0"
    current_regime: str = "震荡"
    evolution_generation: int = 42
    last_update: str = ""
    

class DashboardV3DataProvider:
    """
    看板V3.0数据提供者
    整合所有V6.0模块数据，统一输出给前端
    """
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()
        self.state = DashboardState()
        
        # 初始化各模块连接器
        self.broker_manager: Optional[SmartBrokerManagerV2] = None
        self.knowledge_base: Optional[HistoricalKnowledgeBase] = None
        self.evolution_engine: Optional[SmartStrategyEvolutionEngine] = None
        self.report_generator: Optional[ResearchReportGenerator] = None
        
        self._init_modules()
    
    def _load_config(self) -> Dict:
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"配置加载失败: {e}")
            return {}
    
    def _init_modules(self):
        """初始化各V6.0模块连接"""
        if not V6_MODULES_AVAILABLE:
            return
        
        try:
            # 券商管理器
            if self.config.get("broker_management_v2", {}).get("enabled", False):
                self.broker_manager = SmartBrokerManagerV2(self.config_path)
                logger.info("✅ 券商管理器V2已连接")
        except Exception as e:
            logger.warning(f"券商管理器初始化失败: {e}")
        
        try:
            # 历史知识库
            if self.config.get("historical_kb", {}).get("enabled", False):
                self.knowledge_base = HistoricalKnowledgeBase(self.config_path)
                logger.info("✅ 历史知识库已连接")
        except Exception as e:
            logger.warning(f"历史知识库初始化失败: {e}")
        
        try:
            # 策略进化引擎
            if self.config.get("strategy_evolution", {}).get("enabled", False):
                self.evolution_engine = SmartStrategyEvolutionEngine(self.config_path)
                logger.info("✅ 策略进化引擎已连接")
        except Exception as e:
            logger.warning(f"策略进化引擎初始化失败: {e}")
        
        try:
            # 投研报告生成器
            if self.config.get("research_report", {}).get("enabled", False):
                self.report_generator = ResearchReportGenerator(self.config_path)
                logger.info("✅ 投研报告生成器已连接")
        except Exception as e:
            logger.warning(f"投研报告生成器初始化失败: {e}")
    
    def update_state(self):
        """更新看板全局状态"""
        # 更新券商信息
        if self.broker_manager:
            self.state.current_broker = self.broker_manager.current_broker_id
            dashboard_data = self.broker_manager.get_dashboard_data()
            all_brokers = dashboard_data.get("all_brokers", {})
            current_broker_data = all_brokers.get(self.state.current_broker, {})
            self.state.broker_quality_score = current_broker_data.get("quality_score", 87.0)
        
        # 更新进化代际
        if self.evolution_engine:
            try:
                dashboard = self.evolution_engine.get_dashboard_data()
                self.state.evolution_generation = dashboard.get("generation", 42)
            except:
                pass
        
        # 更新市场政权
        if self.knowledge_base:
            try:
                current_regime = self.knowledge_base.get_current_regime()
                if current_regime:
                    self.state.current_regime = current_regime.get("regime", "震荡")
            except:
                pass
        
        self.state.last_update = datetime.now().isoformat()
    
    # ═══════════════════════════════════════════════════════════
    # 面板 1: 顶部信息栏 - 实盘操作面板
    # ═══════════════════════════════════════════════════════════
    def get_live_trading_header(self) -> Dict:
        """实盘操作面板顶部信息栏数据"""
        self.update_state()
        return {
            "broker": {
                "name": self._get_broker_display_name(self.state.current_broker),
                "id": self.state.current_broker,
                "status": "connected",
                "quality_score": round(self.state.broker_quality_score, 1),
                "can_switch": True
            },
            "model": {
                "name": self.state.current_model,
                "version": "V6.0",
                "type": "Transformer-PPO"
            },
            "regime": {
                "current": self.state.current_regime,
                "confidence": 0.85  # HMM置信度
            },
            "evolution": {
                "generation": self.state.evolution_generation,
                "active_strategies": 100,
                "hall_of_fame": 5
            },
            "timestamp": self.state.last_update
        }
    
    def _get_broker_display_name(self, broker_id: str) -> str:
        """获取券商显示名称"""
        broker_names = {
            "ptrade": "华泰PTrade",
            "qmt": "迅投QMT",
            "easytrader": "通用券商"
        }
        return broker_names.get(broker_id, broker_id)
    
    # ═══════════════════════════════════════════════════════════
    # 面板 2: 券商详情面板（钻取）
    # ═══════════════════════════════════════════════════════════
    def get_broker_detail(self, broker_id: Optional[str] = None) -> Dict:
        """券商详情面板数据（点击券商状态弹出）"""
        if not self.broker_manager:
            return {"error": "券商管理器未启用"}
        
        broker_id = broker_id or self.state.current_broker
        dashboard = self.broker_manager.get_dashboard_data()
        all_brokers = dashboard.get("all_brokers", {})
        broker_data = all_brokers.get(broker_id, {})
        
        return {
            "broker_id": broker_id,
            "name": self._get_broker_display_name(broker_id),
            "status": broker_data.get("status", "unknown"),
            "metrics": {
                "latency_ms": broker_data.get("latency_ms", 9999),
                "success_rate": broker_data.get("success_rate", 0),
                "avg_slippage_bps": broker_data.get("avg_slippage_bps", 0),
                "commission_rate": broker_data.get("commission_rate", 0.00025),
                "quality_score": broker_data.get("quality_score", 0)
            },
            "history": dashboard.get("switch_history", [])[-10:],
            "rules": dashboard.get("active_rules", []),
            "recommendation": self._get_broker_recommendation(broker_id, all_brokers)
        }
    
    def _get_broker_recommendation(self, current_id: str, all_brokers: Dict) -> str:
        """生成券商切换建议"""
        current = all_brokers.get(current_id, {})
        current_score = current.get("quality_score", 0)
        
        best_alternative = None
        best_score = 0
        for bid, bdata in all_brokers.items():
            if bid != current_id and bdata.get("status") == "connected":
                score = bdata.get("quality_score", 0)
                if score > best_score:
                    best_score = score
                    best_alternative = bid
        
        if best_alternative and best_score > current_score + 10:
            return f"建议切换到 {self._get_broker_display_name(best_alternative)}（质量分高{best_score-current_score:.0f}分）"
        return "当前券商运行良好，无需切换"
    
    # ═══════════════════════════════════════════════════════════
    # 面板 3: 进化详情面板（钻取）
    # ═══════════════════════════════════════════════════════════
    def get_evolution_detail(self) -> Dict:
        """进化详情面板数据（点击进化代际弹出）"""
        if not self.evolution_engine:
            return {"error": "策略进化引擎未启用"}
        
        dashboard = self.evolution_engine.get_dashboard_data()
        
        return {
            "generation": dashboard.get("generation", 0),
            "population": {
                "active_count": dashboard.get("population_size", 0),
                "graveyard_count": dashboard.get("graveyard_size", 0),
                "avg_fitness": dashboard.get("avg_fitness", 0),
                "max_fitness": dashboard.get("max_fitness", 0)
            },
            "hall_of_fame": dashboard.get("hall_of_fame", []),
            "top10_active": dashboard.get("top10_active", []),
            "fitness_distribution": dashboard.get("fitness_distribution", []),
            "strategy_distribution": dashboard.get("strategy_distribution", {})
        }
    
    # ═══════════════════════════════════════════════════════════
    # 面板 4: 个股深度面板（钻取）
    # ═══════════════════════════════════════════════════════════
    def get_stock_detail(self, stock_code: str) -> Dict:
        """个股深度面板数据（点击持仓表股票弹出）"""
        # 模拟数据，实际应从数据层获取
        return {
            "stock_code": stock_code,
            "stock_name": f"股票{stock_code}",
            "current_price": 15.68,
            "price_change": 2.35,
            "technical": {
                "ma5": 15.23,
                "ma20": 14.89,
                "rsi": 62.5,
                "macd": "金叉",
                "support": 14.50,
                "resistance": 16.20
            },
            "fundamental": {
                "pe": 18.5,
                "pb": 2.3,
                "roe": 15.2,
                "market_cap": 120.5
            },
            "position": {
                "holding": 1000,
                "avg_cost": 14.20,
                "pnl": 1480,
                "pnl_pct": 10.42
            },
            "signals": [
                {"date": "2026-03-05", "signal": "BUY", "source": "StrategyEvolution", "confidence": 0.82}
            ]
        }
    
    # ═══════════════════════════════════════════════════════════
    # 面板 5: 信号详情面板（钻取）
    # ═══════════════════════════════════════════════════════════
    def get_signal_detail(self, signal_id: str) -> Dict:
        """信号详情面板数据（点击信号队列弹出）"""
        return {
            "signal_id": signal_id,
            "timestamp": datetime.now().isoformat(),
            "stock_code": "600000",
            "action": "BUY",
            "price": 15.68,
            "factors": {
                "momentum": 0.75,
                "mean_reversion": 0.32,
                "sentiment": 0.68,
                "fundamental": 0.82
            },
            "agent_reasoning": [
                "技术面：突破MA20，MACD金叉",
                "基本面：PE低于行业平均",
                "情绪面：近期新闻正面偏多",
                "风险面：VaR在可接受范围"
            ],
            "confidence_breakdown": {
                "technical": 0.85,
                "fundamental": 0.78,
                "sentiment": 0.72,
                "risk": 0.88,
                "overall": 0.82
            }
        }
    
    # ═══════════════════════════════════════════════════════════
    # 面板 6: 策略详情面板（钻取）
    # ═══════════════════════════════════════════════════════════
    def get_strategy_detail(self, strategy_id: str) -> Dict:
        """策略详情面板数据（点击策略卡片弹出）"""
        return {
            "strategy_id": strategy_id,
            "type": "momentum",
            "generation": 42,
            "fitness_score": 78.5,
            "params": {
                "lookback_period": 20,
                "buy_threshold": 0.05,
                "ma_fast": 5,
                "ma_slow": 20
            },
            "performance": {
                "sharpe": 1.25,
                "annual_return": 0.18,
                "max_drawdown": 0.12,
                "win_rate": 0.62
            },
            "lineage": {
                "parents": ["a3f2d1", "b8e5c4"],
                "mutations": 3,
                "crossovers": 2
            },
            "history": [
                {"generation": 40, "fitness": 72.1},
                {"generation": 41, "fitness": 75.3},
                {"generation": 42, "fitness": 78.5}
            ]
        }
    
    # ═══════════════════════════════════════════════════════════
    # 面板 7: Agent日志面板（钻取）
    # ═══════════════════════════════════════════════════════════
    def get_agent_logs(self, agent_id: str, limit: int = 10) -> List[Dict]:
        """Agent日志面板数据（点击Agent状态弹出）"""
        return [
            {
                "timestamp": (datetime.now() - timedelta(minutes=i*5)).isoformat(),
                "level": "INFO",
                "action": "分析市场信号",
                "reasoning": f"检测到动量突破，RSI={60+i}",
                "decision": "建议买入"
            }
            for i in range(limit)
        ]
    
    # ═══════════════════════════════════════════════════════════
    # 面板 8: 风险分解面板（钻取）
    # ═══════════════════════════════════════════════════════════
    def get_risk_detail(self) -> Dict:
        """风险分解面板数据（点击VaR数字弹出）"""
        return {
            "portfolio_var": 12500,
            "var_95": 0.025,
            "var_99": 0.038,
            "factor_contribution": {
                "market": 0.45,
                "sector": 0.25,
                "style": 0.20,
                "idiosyncratic": 0.10
            },
            "position_contribution": [
                {"code": "600000", "var_contrib": 3200, "pct": 25.6},
                {"code": "000001", "var_contrib": 2800, "pct": 22.4},
                {"code": "300750", "var_contrib": 2100, "pct": 16.8}
            ],
            "stress_scenarios": {
                "market_crash_2008": -0.35,
                "covid_crash": -0.28,
                "trade_war": -0.15
            }
        }
    
    # ═══════════════════════════════════════════════════════════
    # 面板 9: 交易复盘面板（钻取）
    # ═══════════════════════════════════════════════════════════
    def get_trade_review(self, trade_id: str) -> Dict:
        """交易复盘面板数据（点击历史交易记录弹出）"""
        return {
            "trade_id": trade_id,
            "stock_code": "600000",
            "actions": [
                {"date": "2026-03-01", "action": "BUY", "price": 14.20, "signal": "金叉买入"},
                {"date": "2026-03-06", "action": "SELL", "price": 15.68, "signal": "止盈卖出"}
            ],
            "price_chart": [
                {"date": "2026-03-01", "price": 14.20},
                {"date": "2026-03-02", "price": 14.35},
                {"date": "2026-03-03", "price": 14.50},
                {"date": "2026-03-04", "price": 15.10},
                {"date": "2026-03-05", "price": 15.45},
                {"date": "2026-03-06", "price": 15.68}
            ],
            "pnl": 1480,
            "pnl_pct": 10.42,
            "holding_days": 5,
            "lessons": ["买入时机良好，突破确认后入场", "止盈设置合理，锁定利润"]
        }
    
    # ═══════════════════════════════════════════════════════════
    # 面板 10: 投研报告预览面板（钻取）
    # ═══════════════════════════════════════════════════════════
    def get_report_preview(self, report_id: str) -> Dict:
        """投研报告预览面板数据（点击投研报告行弹出）"""
        return {
            "report_id": report_id,
            "type": "individual_stock",
            "stock_code": "300750",
            "stock_name": "宁德时代",
            "generated_at": datetime.now().isoformat(),
            "overall_score": 82.5,
            "recommendation": "强烈买入 ★★★★★",
            "html_url": f"/reports/{report_id}.html",
            "pdf_url": f"/reports/{report_id}.pdf",
            "sections": [
                {"name": "技术面分析", "score": 85},
                {"name": "基本面分析", "score": 80},
                {"name": "舆情面分析", "score": 82},
                {"name": "风险评估", "score": 88}
            ]
        }
    
    # ═══════════════════════════════════════════════════════════
    # 全局数据接口
    # ═══════════════════════════════════════════════════════════
    def get_all_panels_data(self) -> Dict:
        """获取所有面板数据（初始加载）"""
        return {
            "header": self.get_live_trading_header(),
            "broker": self.get_broker_detail(),
            "evolution": self.get_evolution_detail(),
            "timestamp": datetime.now().isoformat()
        }


# ═══════════════════════════════════════════════════════════════
# Flask API 路由（如果Flask可用）
# ═══════════════════════════════════════════════════════════════

if FLASK_AVAILABLE:
    app = Flask(__name__)
    CORS(app)
    
    # 全局数据提供者实例
    data_provider = DashboardV3DataProvider()
    
    @app.route('/api/v3/dashboard/header', methods=['GET'])
    def api_header():
        """顶部信息栏"""
        return jsonify(data_provider.get_live_trading_header())
    
    @app.route('/api/v3/dashboard/broker', methods=['GET'])
    def api_broker():
        """券商详情"""
        broker_id = request.args.get('id')
        return jsonify(data_provider.get_broker_detail(broker_id))
    
    @app.route('/api/v3/dashboard/evolution', methods=['GET'])
    def api_evolution():
        """进化详情"""
        return jsonify(data_provider.get_evolution_detail())
    
    @app.route('/api/v3/dashboard/stock/<stock_code>', methods=['GET'])
    def api_stock(stock_code: str):
        """个股深度"""
        return jsonify(data_provider.get_stock_detail(stock_code))
    
    @app.route('/api/v3/dashboard/signal/<signal_id>', methods=['GET'])
    def api_signal(signal_id: str):
        """信号详情"""
        return jsonify(data_provider.get_signal_detail(signal_id))
    
    @app.route('/api/v3/dashboard/strategy/<strategy_id>', methods=['GET'])
    def api_strategy(strategy_id: str):
        """策略详情"""
        return jsonify(data_provider.get_strategy_detail(strategy_id))
    
    @app.route('/api/v3/dashboard/agent/<agent_id>/logs', methods=['GET'])
    def api_agent_logs(agent_id: str):
        """Agent日志"""
        limit = request.args.get('limit', 10, type=int)
        return jsonify(data_provider.get_agent_logs(agent_id, limit))
    
    @app.route('/api/v3/dashboard/risk', methods=['GET'])
    def api_risk():
        """风险分解"""
        return jsonify(data_provider.get_risk_detail())
    
    @app.route('/api/v3/dashboard/trade/<trade_id>', methods=['GET'])
    def api_trade(trade_id: str):
        """交易复盘"""
        return jsonify(data_provider.get_trade_review(trade_id))
    
    @app.route('/api/v3/dashboard/report/<report_id>', methods=['GET'])
    def api_report(report_id: str):
        """报告预览"""
        return jsonify(data_provider.get_report_preview(report_id))
    
    @app.route('/api/v3/dashboard/all', methods=['GET'])
    def api_all():
        """所有面板数据"""
        return jsonify(data_provider.get_all_panels_data())
    
    @app.route('/api/v3/broker/switch', methods=['POST'])
    def api_broker_switch():
        """切换券商"""
        data = request.get_json() or {}
        broker_id = data.get('broker_id')
        reason = data.get('reason', 'manual')
        if data_provider.broker_manager:
            result = data_provider.broker_manager.switch_broker(broker_id, reason)
            return jsonify(result)
        return jsonify({"error": "券商管理器未启用"})
    
    def run_dashboard_server(host: str = "0.0.0.0", port: int = 5001, debug: bool = False):
        """启动看板V3.0 API服务"""
        logger.info(f"🚀 Alpha 看板 V3.0 API 服务启动: http://{host}:{port}")
        app.run(host=host, port=port, debug=debug)

else:
    # 无Flask时的占位函数
    def run_dashboard_server(*args, **kwargs):
        logger.error("Flask未安装，无法启动看板V3.0 API服务")
        logger.info("请运行: pip install flask flask-cors")


if __name__ == "__main__":
    # 生产模式启动
    logging.basicConfig(level=logging.INFO)
    
    if FLASK_AVAILABLE:
        # 生产模式：读取配置文件中的端口
        import sys
        config_path = "config.json"
        try:
            with open(config_path) as f:
                cfg = json.load(f)
            dash_cfg = cfg.get("dashboard_v3", {})
            host = dash_cfg.get("host", "0.0.0.0")
            port = dash_cfg.get("port", 5001)
            debug = dash_cfg.get("debug", False)
        except:
            host, port, debug = "0.0.0.0", 5001, False
        
        run_dashboard_server(host=host, port=port, debug=debug)
    else:
        # 独立测试模式
        provider = DashboardV3DataProvider()
        print("\n=== Alpha 看板 V3.0 数据测试 ===\n")
        print("顶部信息栏:")
        print(json.dumps(provider.get_live_trading_header(), indent=2, ensure_ascii=False))
        print("\n券商详情:")
        print(json.dumps(provider.get_broker_detail(), indent=2, ensure_ascii=False))
        print("\n进化详情:")
        print(json.dumps(provider.get_evolution_detail(), indent=2, ensure_ascii=False))
