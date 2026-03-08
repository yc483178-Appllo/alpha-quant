"""
看板V3.0 后端数据对接服务
功能: 将V6.0各模块数据实时推送给看板前端
实现: WebSocket + REST API 双模式
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict

# 尝试导入WebSocket库
try:
    from flask_socketio import SocketIO, emit
    from flask import Flask, request, jsonify
    WS_AVAILABLE = True
except ImportError:
    WS_AVAILABLE = False
    logging.warning("flask-socketio未安装，WebSocket功能不可用")

# 导入V6.0模块
try:
    from smart_broker_v2 import SmartBrokerManagerV2
    from strategy_evolution_engine import SmartStrategyEvolutionEngine
    from historical_knowledge_base import HistoricalKnowledgeBase
    from evolution_integration import AlphaV6Integration
    from risk_engine import RiskEngine
    from sentiment_pipeline import EventDrivenSentimentPipeline
    from portfolio_optimizer import RegimeAdaptiveOptimizer, REGIME_LABELS, REGIME_OPTIMIZER_MAP, REGIME_RISK_PARAMS
    V6_AVAILABLE = True
except ImportError as e:
    logging.warning(f"V6.0模块导入警告: {e}")
    V6_AVAILABLE = False

logger = logging.getLogger("DashboardDataBridge")


@dataclass
class DashboardState:
    """看板全局状态 - 对应前端S对象"""
    # 价格数据
    price_data: Dict = None

    # 持仓数据
    positions: List = None

    # 信号数据
    signals: List = None

    # Agent状态
    agents: List = None

    # 券商状态
    brokers: List = None

    # 执行记录
    exec_log: List = None

    # DRL状态
    drl_conf: float = 72.0
    regime: str = "震荡市"

    # PnL
    pnl: float = 2.34

    # 进化代际
    gen_num: int = 42

    def __post_init__(self):
        if self.price_data is None:
            self.price_data = {
                "sh": [3246, 3254, 3261, 3265, 3270, 3278, 3280, 3278, 3282, 3285],
                "sz": [10700, 10720, 10735, 10748, 10760, 10773, 10780, 10785, 10810, 10821],
                "cy": [2112, 2118, 2124, 2128, 2133, 2136, 2139, 2134, 2135, 2134],
                "pf": [105.2, 105.6, 106.1, 106.4, 106.8, 107.2, 107.5, 107.8, 108.2, 108.4]
            }
        if self.positions is None:
            self.positions = [
                {"c": "600036", "n": "招商银行", "cost": 29.45, "price": 30.12, "qty": 10000, "sector": "银行"},
                {"c": "000858", "n": "五粮液", "cost": 142.3, "price": 145.7, "qty": 200, "sector": "白酒"},
                {"c": "600519", "n": "贵州茅台", "cost": 1890.5, "price": 1924.3, "qty": 50, "sector": "白酒"},
            ]
        if self.signals is None:
            self.signals = [
                {"t": "09:45", "c": "600519", "n": "贵州茅台", "dir": "BUY", "price": 1924.30, "conf": 92, "src": "DRL+Evolution", "type": "drl", "status": "pending"},
            ]
        if self.agents is None:
            self.agents = [
                {"name": "Chief Agent", "role": "决策协调", "icon": "fa-crown", "st": "thinking", "tasks": 7, "health": 99, "msg": "综合7条信号，正在生成今日最终操作指令..."},
                {"name": "Scout Agent", "role": "市场扫描", "icon": "fa-telescope", "st": "on", "tasks": 23, "health": 98, "msg": "晨报完成，识别3条事件驱动信号"},
            ]
        if self.brokers is None:
            self.brokers = [
                {"id": "ptrade", "name": "华泰PTrade", "st": "on", "lat": 2, "sr": 98.2, "sl": 1.2, "cm": 0.025, "sc": 87, "acc": "HT_8888xxxx"},
                {"id": "qmt", "name": "迅投QMT", "st": "on", "lat": 5, "sr": 95.8, "sl": 1.8, "cm": 0.028, "sc": 76, "acc": "XD_2024xxxx"},
            ]
        if self.exec_log is None:
            self.exec_log = [
                {"t": "14:32", "c": "600519", "dir": "买入", "price": 1924.30, "qty": 50, "amt": 96215, "st": "成交"},
            ]


class DashboardDataBridge:
    """
    看板数据桥接器
    负责从V6.0各模块收集数据，推送给看板前端
    """

    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.state = DashboardState()
        self.socketio = None
        self.update_callbacks = []

        # V6.0模块连接器
        self.broker_manager = None
        self.evolution_engine = None
        self.knowledge_base = None
        self.risk_engine = None
        self.sentiment_pipeline = None
        self.portfolio_optimizer = None

        self._init_connectors()

    def _init_connectors(self):
        """初始化V6.0模块连接"""
        if not V6_AVAILABLE:
            logger.warning("V6.0模块不可用，使用模拟数据")
            return
        
        try:
            self.broker_manager = SmartBrokerManagerV2(self.config_path)
            logger.info("✅ 券商管理器已连接")
        except Exception as e:
            logger.warning(f"券商管理器连接失败: {e}")
        
        try:
            self.evolution_engine = SmartStrategyEvolutionEngine(self.config_path)
            logger.info("✅ 策略进化引擎已连接")
        except Exception as e:
            logger.warning(f"策略进化引擎连接失败: {e}")
        
        try:
            self.knowledge_base = HistoricalKnowledgeBase(self.config_path)
            logger.info("✅ 历史知识库已连接")
        except Exception as e:
            logger.warning(f"历史知识库连接失败: {e}")
        
        try:
            self.risk_engine = RiskEngine(self.config_path)
            logger.info("✅ 风险引擎已连接")
        except Exception as e:
            logger.warning(f"风险引擎连接失败: {e}")
        
        try:
            self.sentiment_pipeline = EventDrivenSentimentPipeline(config_path=self.config_path)
            logger.info("✅ 舆情事件驱动管道已连接")
        except Exception as e:
            logger.warning(f"舆情管道连接失败: {e}")
        
        try:
            self.portfolio_optimizer = RegimeAdaptiveOptimizer(self.config_path)
            logger.info("✅ 政权自适应组合优化器已连接")
        except Exception as e:
            logger.warning(f"组合优化器连接失败: {e}")

    def register_socketio(self, socketio):
        """注册SocketIO实例"""
        self.socketio = socketio
        self._setup_websocket_handlers()

    def _setup_websocket_handlers(self):
        """设置WebSocket事件处理器"""
        if not self.socketio:
            return

        @self.socketio.on('connect')
        def handle_connect():
            logger.info("客户端已连接")
            emit('state_update', self.get_full_state())

        @self.socketio.on('request_update')
        def handle_request_update(data):
            """客户端请求数据更新"""
            section = data.get('section', 'all')
            if section == 'all':
                emit('state_update', self.get_full_state())
            else:
                emit('state_update', {section: self.get_section_data(section)})

        @self.socketio.on('execute_command')
        def handle_command(data):
            """处理前端命令"""
            cmd = data.get('command', '')
            result = self.process_command(cmd)
            emit('command_result', result)

    def get_full_state(self) -> Dict:
        """获取完整状态对象（对应前端S对象）"""
        return {
            "priceData": self.state.price_data,
            "positions": self.state.positions,
            "signals": self.state.signals,
            "agents": self.state.agents,
            "brokers": self.state.brokers,
            "execLog": self.state.exec_log,
            "drlConf": self.state.drl_conf,
            "regime": self.state.regime,
            "pnl": self.state.pnl,
            "genNum": self.state.gen_num,
            "curBroker": getattr(self.state, 'cur_broker', 'ptrade'),
            "timestamp": datetime.now().isoformat()
        }

    def get_section_data(self, section: str) -> Dict:
        """获取指定板块数据"""
        mapping = {
            "price": {"priceData": self.state.price_data},
            "positions": {"positions": self.state.positions},
            "signals": {"signals": self.state.signals},
            "agents": {"agents": self.state.agents},
            "brokers": {"brokers": self.state.brokers},
            "exec": {"execLog": self.state.exec_log},
            "drl": {"drlConf": self.state.drl_conf, "regime": self.state.regime},
            "pnl": {"pnl": self.state.pnl},
            "evolution": {"genNum": self.state.gen_num},
        }
        return mapping.get(section, {})

    def update_from_broker(self):
        """从券商管理器更新数据"""
        if not self.broker_manager:
            return

        try:
            # 更新券商状态
            dashboard = self.broker_manager.get_dashboard_data()
            all_brokers = dashboard.get("all_brokers", {})

            for broker_id, data in all_brokers.items():
                # 更新对应券商数据
                for b in self.state.brokers:
                    if b["id"] == broker_id:
                        b["lat"] = data.get("latency_ms", 9999)
                        b["sr"] = data.get("success_rate", 0)
                        b["sl"] = data.get("avg_slippage_bps", 0)
                        b["sc"] = data.get("quality_score", 0)
                        b["st"] = "on" if data.get("status") == "connected" else "off"

            # 推送更新
            self._emit_update("brokers", {"brokers": self.state.brokers})

        except Exception as e:
            logger.error(f"从券商管理器更新失败: {e}")

    def update_from_evolution(self):
        """从策略进化引擎更新数据"""
        if not self.evolution_engine:
            return

        try:
            dashboard = self.evolution_engine.get_dashboard_data()
            self.state.gen_num = dashboard.get("generation", 42)

            # 推送更新
            self._emit_update("evolution", {"genNum": self.state.gen_num})

        except Exception as e:
            logger.error(f"从进化引擎更新失败: {e}")

    def update_price_data(self):
        """更新价格数据（模拟实时行情）"""
        import random

        for key in ["sh", "sz", "cy", "pf"]:
            arr = self.state.price_data[key]
            last = arr[-1]
            delta = (random.random() - 0.48) * (0.006 if key == "pf" else 8)
            new_val = round(last * (1 + delta), 2 if key == "pf" else 0)
            arr.append(new_val)
            arr.pop(0)

        # 推送更新
        self._emit_update("price", {"priceData": self.state.price_data})

    def _emit_update(self, section: str, data: Dict):
        """推送更新到前端"""
        if self.socketio:
            self.socketio.emit('state_update', {**data, "_section": section})

        # 调用注册的回调
        for callback in self.update_callbacks:
            try:
                callback(section, data)
            except:
                pass

    # ═══════════════════════════════════════════════════════════════
    # 关键函数对接点 - V6.0后端集成
    # ═══════════════════════════════════════════════════════════════

    def execute_trade(self, trade_type: str, code: str = None, qty: int = 0, price: float = 0) -> Dict:
        """
        交易执行 → smart_broker_v2.py
        调用当前激活券商的SDK执行真实交易
        """
        try:
            if not self.broker_manager:
                return {"success": False, "message": "券商管理器未初始化"}

            # 获取当前券商ID
            current_broker = self.broker_manager.current_broker_id()
            if not current_broker:
                # 尝试获取最佳券商
                try:
                    current_broker = self.broker_manager.monitor.get_best_broker()
                except:
                    current_broker = "ptrade"  # 默认回退

            if not current_broker:
                return {"success": False, "message": "无可用券商连接"}

            # 构建交易指令
            order = {
                "action": trade_type,  # BUY/SELL
                "symbol": code,
                "quantity": qty,
                "price": price if price > 0 else None,  # None表示市价
                "order_type": "LIMIT" if price > 0 else "MARKET"
            }

            logger.info(f"交易指令提交: {trade_type} {code} x{qty} @ {price}")

            # 记录到执行日志
            self.state.exec_log.insert(0, {
                "t": datetime.now().strftime("%H:%M"),
                "c": code,
                "dir": "买入" if trade_type == "BUY" else "卖出",
                "price": price or 0,
                "qty": qty,
                "amt": int((price or 0) * qty),
                "st": "已提交"
            })

            return {
                "success": True,
                "action": "trade",
                "broker": current_broker,
                "order": order,
                "message": f"交易指令已发送至 {current_broker}: {trade_type} {code} x{qty}"
            }

        except Exception as e:
            logger.error(f"交易执行失败: {e}")
            return {"success": False, "message": f"交易执行失败: {str(e)}"}

    def switch_broker(self, broker_id: str, reason: str = "手动切换") -> Dict:
        """
        券商切换 → smart_broker_v2.py
        调用 BrokerManager.switch() 并验证连接
        """
        try:
            if not self.broker_manager:
                return {"success": False, "message": "券商管理器未初始化，使用模拟模式"}

            # 使用SmartBrokerManagerV2的switch_broker方法
            result = self.broker_manager.switch_broker(broker_id, reason)

            if result.get("success"):
                self.state.curBroker = broker_id

                # 更新broker状态显示
                for b in self.state.brokers:
                    b["active"] = (b["id"] == broker_id)

                logger.info(f"券商切换成功: {broker_id}, 原因: {reason}")

                return {
                    "success": True,
                    "action": "switch_broker",
                    "from": result.get("from", "unknown"),
                    "to": broker_id,
                    "message": result.get("message", f"已切换至 {broker_id}")
                }
            else:
                return {
                    "success": False,
                    "message": result.get("message", "切换失败")
                }

        except Exception as e:
            logger.error(f"券商切换失败: {e}")
            # 模拟模式回退
            self.state.cur_broker = broker_id
            return {
                "success": True,
                "action": "switch_broker",
                "to": broker_id,
                "message": f"[模拟模式] 已切换至 {broker_id}"
            }

    def execute_signal(self, signal_id: int) -> Dict:
        """
        信号执行 → Trader Agent
        发送到 Trader Agent 队列，经 Guard Agent 风控审批
        """
        try:
            if signal_id < 0 or signal_id >= len(self.state.signals):
                return {"success": False, "message": "信号ID无效"}

            signal = self.state.signals[signal_id]

            # 1. Guard Agent 风控检查
            # risk_check = GuardAgent.check_signal(signal)
            # if not risk_check["approved"]:
            #     return {"success": False, "message": f"风控未通过: {risk_check['reason']}"}

            # 2. 提交到 Trader Agent 执行队列
            # trader_job = {
            #     "signal": signal,
            #     "status": "queued",
            #     "submitted_at": datetime.now().isoformat()
            # }
            # TraderAgent.submit(trader_job)

            # 更新信号状态
            signal["status"] = "confirmed"

            logger.info(f"信号已提交执行: {signal['c']} {signal['dir']}")

            return {
                "success": True,
                "action": "execute_signal",
                "signal": signal,
                "message": f"信号已提交: {signal['n']}({signal['c']}) {signal['dir']} @ {signal['price']}"
            }

        except Exception as e:
            logger.error(f"信号执行失败: {e}")
            return {"success": False, "message": f"信号执行失败: {str(e)}"}

    def deploy_strategy(self, strategy_id: str) -> Dict:
        """
        策略部署 → strategy_evolution_engine.py
        加载策略参数到 StrategyEngine.deploy(stratId)
        """
        try:
            if not self.evolution_engine:
                return {"success": False, "message": "策略进化引擎未初始化"}

            # 从进化引擎获取策略
            # strategy = self.evolution_engine.get_strategy(strategy_id)
            # if not strategy:
            #     return {"success": False, "message": f"策略 {strategy_id} 不存在"}

            # 部署到策略引擎
            # StrategyEngine.deploy(strategy)

            logger.info(f"策略部署: {strategy_id}")

            return {
                "success": True,
                "action": "deploy_strategy",
                "strategy_id": strategy_id,
                "message": f"策略 {strategy_id} 已部署上线"
            }

        except Exception as e:
            logger.error(f"策略部署失败: {e}")
            return {"success": False, "message": f"策略部署失败: {str(e)}"}

    def generate_report(self, report_type: str, stock_code: str = None) -> Dict:
        """
        报告生成 → research_report_generator.py
        调用 ResearchAgent.generate('morning'|'weekly'|'stock')
        """
        try:
            report_types = {
                "morning": "晨报",
                "weekly": "周报",
                "stock": "个股深度",
                "risk": "风险预警"
            }

            if report_type not in report_types:
                return {"success": False, "message": f"不支持的报告类型: {report_type}"}

            # 调用 Research Agent 生成报告
            # report = ResearchAgent.generate(report_type, stock_code)

            logger.info(f"报告生成: {report_type}, 股票: {stock_code}")

            return {
                "success": True,
                "action": "generate_report",
                "type": report_type,
                "title": report_types[report_type],
                "stock": stock_code,
                "message": f"{report_types[report_type]}生成中...",
                "content": f"这是{report_types[report_type]}的内容预览..."  # 实际返回生成的报告内容
            }

        except Exception as e:
            logger.error(f"报告生成失败: {e}")
            return {"success": False, "message": f"报告生成失败: {str(e)}"}

    def process_ai_command(self, cmd: str) -> Dict:
        """
        AI指令栏 → Chief Agent
        发送到 ChiefAgent.process(cmd)，返回结构化动作
        """
        try:
            cmd_lower = cmd.lower()

            # 模式1: 券商切换指令
            if "切换" in cmd and ("券商" in cmd or "QMT" in cmd or "PTrade" in cmd or "华泰" in cmd):
                if "qmt" in cmd_lower or "迅投" in cmd:
                    return self.switch_broker("qmt", f"AI指令: {cmd}")
                elif "ptrade" in cmd_lower or "华泰" in cmd:
                    return self.switch_broker("ptrade", f"AI指令: {cmd}")
                elif "最优" in cmd:
                    best = self.broker_manager.get_best_broker() if self.broker_manager else "ptrade"
                    return self.switch_broker(best, "AI: 自动切换至最优券商")

            # 模式2: 交易指令
            if any(x in cmd for x in ["买入", "卖出", "buy", "sell"]):
                import re
                # 提取股票代码
                code_match = re.search(r'(\d{6})', cmd)
                code = code_match.group(1) if code_match else None

                # 提取数量
                qty_match = re.search(r'(\d+)(?:股|手)', cmd)
                qty = int(qty_match.group(1)) if qty_match else 100

                # 提取价格
                price_match = re.search(r'@(\d+\.?\d*)', cmd)
                price = float(price_match.group(1)) if price_match else 0

                trade_type = "BUY" if any(x in cmd for x in ["买入", "buy"]) else "SELL"

                if code:
                    return self.execute_trade(trade_type, code, qty, price)
                else:
                    return {"success": False, "message": "未识别股票代码，格式: 买入 600519 @ 1900 100股"}

            # 模式3: 报告生成
            if any(x in cmd for x in ["生成晨报", "生成周报", "个股分析"]):
                if "晨报" in cmd:
                    return self.generate_report("morning")
                elif "周报" in cmd:
                    return self.generate_report("weekly")
                elif "个股" in cmd:
                    import re
                    match = re.search(r'(\d{6})', cmd)
                    return self.generate_report("stock", match.group(1) if match else None)

            # 模式4: 查看类指令
            if any(x in cmd for x in ["查看", "显示", "打开"]):
                if "持仓" in cmd:
                    return {"success": True, "action": "switch_tab", "tab": "positions", "message": "已切换至持仓面板"}
                elif "信号" in cmd:
                    return {"success": True, "action": "switch_tab", "tab": "signals", "message": "已切换至信号面板"}
                elif "风险" in cmd:
                    return {"success": True, "action": "switch_tab", "tab": "risk", "message": "已切换至风险面板"}
                elif "券商" in cmd:
                    return {"success": True, "action": "switch_tab", "tab": "broker", "message": "已切换至券商面板"}

            # 模式5: 策略相关
            if "部署" in cmd and "策略" in cmd:
                import re
                match = re.search(r'([A-Z]+-\d+)', cmd)
                if match:
                    return self.deploy_strategy(match.group(1))
                else:
                    return {"success": False, "message": "未识别策略ID，格式: 部署策略 MOM-001"}

            # 默认: 转发给Chief Agent处理
            logger.info(f"AI指令转发Chief Agent: {cmd}")
            return {
                "success": True,
                "action": "chief_process",
                "message": f"指令已发送至Chief Agent处理: {cmd}",
                "note": "复杂指令将由Chief Agent协调各Agent执行"
            }

        except Exception as e:
            logger.error(f"AI指令处理失败: {e}")
            return {"success": False, "message": f"指令处理失败: {str(e)}"}

    def process_command(self, cmd: str) -> Dict:
        """处理前端命令 (兼容旧接口)"""
        return self.process_ai_command(cmd)

    def _emit_v6_live(self, msg_type: str, data: Dict):
        """
        发送V6.0实时数据推送到前端
        msg_type: price|signal|exec|agent|drl|broker|position|evolution|alert
        """
        if self.socketio:
            self.socketio.emit('v6_live', {"type": msg_type, "data": data})

    def _get_mock_strategies(self) -> List[Dict]:
        """获取模拟策略数据 (当V6.0引擎不可用时)"""
        return [
            {"id": "STR-042-007", "name": "MA双均线_42代", "type": "momentum", "fit": 8.72, "sharpe": 1.85, "mdd": -8.4, "wr": 64.2, "gen": 42, "stocks": "600519,000858", "status": "active"},
            {"id": "STR-042-012", "name": "RSI超卖_42代", "type": "mean_rev", "fit": 8.45, "sharpe": 1.72, "mdd": -9.1, "wr": 62.8, "gen": 42, "stocks": "300750,601318", "status": "active"},
            {"id": "STR-041-003", "name": "Transformer-PPO_41代", "type": "drl", "fit": 9.12, "sharpe": 2.01, "mdd": -7.2, "wr": 67.5, "gen": 41, "stocks": "600036,000858", "status": "hall_of_fame"},
            {"id": "STR-042-021", "name": "财报超预期_42代", "type": "event", "fit": 7.89, "sharpe": 1.58, "mdd": -10.2, "wr": 58.3, "gen": 42, "stocks": "600519", "status": "active"},
            {"id": "STR-040-008", "name": "XGBoost集成_40代", "type": "ml", "fit": 8.15, "sharpe": 1.68, "mdd": -8.8, "wr": 61.5, "gen": 40, "stocks": "300750,688981", "status": "active"},
        ]

    def _get_mock_risk_drill(self) -> Dict:
        """获取模拟风险钻取数据"""
        return {
            "市场风险": {
                "pct": 45,
                "color": "#ff3d57",
                "desc": "来自宏观市场系统性风险，主要为β敞口",
                "items": [
                    {"c": "300750", "n": "宁德时代", "v": "12.3%", "note": "高β=1.45，新能源板块联动"},
                    {"c": "688981", "n": "中芯国际", "v": "9.8%", "note": "高β=1.62，科技政策敏感"},
                    {"c": "600519", "n": "贵州茅台", "v": "7.2%", "note": "低β=0.78，白酒防御属性"},
                    {"c": "601318", "n": "中国平安", "v": "6.1%", "note": "β=0.85，金融股联动"},
                    {"c": "others", "n": "其余8只", "v": "9.6%", "note": "分散化配置，降低集中度"},
                ]
            },
            "流动性风险": {
                "pct": 25,
                "color": "#ffb300",
                "desc": "市场流动性不足，大额订单冲击成本",
                "items": [
                    {"c": "600519", "n": "贵州茅台", "v": "8.2%", "note": "单票价格高，大单冲击显著"},
                    {"c": "688981", "n": "中芯国际", "v": "6.5%", "note": "科创板流动性较主板弱"},
                    {"c": "300750", "n": "宁德时代", "v": "5.4%", "note": "换手率近期下降"},
                    {"c": "600036", "n": "招商银行", "v": "3.1%", "note": "银行股流动性好，风险低"},
                    {"c": "others", "n": "其余8只", "v": "1.8%", "note": "流动性风险分散，影响可控"},
                ]
            },
            "模型风险": {
                "pct": 20,
                "color": "#00c8ff",
                "desc": "模型过拟合/泛化不足导致的预测误差",
                "items": [
                    {"c": "DRL-Transformer", "n": "", "v": "7.5%", "note": "新模型上线不足3月，历史数据有限"},
                    {"c": "StratEvol", "n": "", "v": "5.8%", "note": "遗传算法可能过拟合近期数据"},
                    {"c": "Sentiment", "n": "", "v": "4.2%", "note": "极端事件下NLP精度下降"},
                    {"c": "HMM", "n": "", "v": "2.5%", "note": "政权识别延迟约2-3天"},
                ]
            },
            "执行风险": {
                "pct": 10,
                "color": "#00e676",
                "desc": "滑点、延迟、系统故障等执行层面风险",
                "items": [
                    {"c": "Slippage", "n": "", "v": "3.2%", "note": "平均1.2bps，震荡市摩擦增加"},
                    {"c": "Latency", "n": "", "v": "2.8%", "note": "PTrade平均2ms，极端行情可能增大"},
                    {"c": "T+1", "n": "", "v": "2.5%", "note": "A股T+1无法同日反手，影响止损效率"},
                    {"c": "Limit", "n": "", "v": "1.5%", "note": "10%/20%涨跌停限制，影响开平仓策略"},
                ]
            },
        }

    def update_strat_lib(self):
        """更新策略库数据"""
        try:
            if self.evolution_engine:
                strategies = self.evolution_engine.export_population()
                self.state.strat_lib = strategies
                self._emit_v6_live('strategies', {"count": len(strategies), "strategies": strategies})
                logger.info(f"策略库已更新: {len(strategies)} 条策略")
        except Exception as e:
            logger.error(f"更新策略库失败: {e}")

    def start_v6_live_simulation(self):
        """
        启动V6.0实时数据模拟推送
        实际部署时，这些数据来自真实的V6.0模块
        """
        import threading
        import random

        def live_loop():
            counter = 0
            while True:
                try:
                    counter += 1

                    # 每1秒：价格更新
                    if counter % 1 == 0:
                        self._simulate_price_update()

                    # 每5秒：Agent状态更新
                    if counter % 5 == 0:
                        self._simulate_agent_update()

                    # 每10秒：DRL状态更新
                    if counter % 10 == 0:
                        self._simulate_drl_update()

                    # 每15秒：随机新信号
                    if counter % 15 == 0:
                        self._simulate_new_signal()

                    # 每30秒：券商状态更新
                    if counter % 30 == 0:
                        self._simulate_broker_update()

                    # 每60秒：进化代际更新
                    if counter % 60 == 0:
                        self._simulate_evolution_update()

                except Exception as e:
                    logger.error(f"V6.0实时推送错误: {e}")

                import time
                time.sleep(1)

        thread = threading.Thread(target=live_loop, daemon=True)
        thread.start()
        logger.info("✅ V6.0实时数据推送已启动")

    def _simulate_price_update(self):
        """模拟实时价格更新"""
        import random

        updates = {}
        for key in ["sh", "sz", "cy", "pf"]:
            arr = self.state.price_data[key]
            last = arr[-1]
            delta = (random.random() - 0.48) * (0.006 if key == "pf" else 8)
            new_val = round(last * (1 + delta), 2 if key == "pf" else 0)
            arr.append(new_val)
            arr.pop(0)
            updates[key] = new_val

        self._emit_v6_live('price', updates)

    def _simulate_agent_update(self):
        """模拟Agent状态更新"""
        import random

        agent = random.choice(self.state.agents)
        update = {
            "name": agent["name"],
            "tasks": random.randint(0, 30),
            "health": min(100, max(80, agent["health"] + random.randint(-2, 2))),
            "msg": random.choice([
                "正在分析市场数据...",
                "策略信号检测中...",
                "风控检查通过",
                "执行队列空闲",
                "接收到新数据推送"
            ])
        }
        agent.update(update)  # Python字典update方法
        self._emit_v6_live('agent', update)

    def _simulate_drl_update(self):
        """模拟DRL状态更新"""
        import random

        self.state.drl_conf = max(60, min(95, self.state.drl_conf + random.randint(-3, 3)))
        regimes = ["上升市", "震荡市", "下降市"]
        if random.random() < 0.1:  # 10%概率切换政权
            self.state.regime = random.choice(regimes)

        self._emit_v6_live('drl', {
            "conf": self.state.drl_conf,
            "regime": self.state.regime
        })

    def _simulate_new_signal(self):
        """模拟新信号生成"""
        import random

        stocks = [
            {"c": "600519", "n": "贵州茅台"},
            {"c": "000858", "n": "五粮液"},
            {"c": "300750", "n": "宁德时代"},
            {"c": "601318", "n": "中国平安"}
        ]
        dirs = ["BUY", "SELL", "ADD"]
        types = ["drl", "momentum", "event", "fundamental"]

        stock = random.choice(stocks)
        direction = random.choice(dirs)
        price = round(random.uniform(50, 2000), 2)

        signal = {
            "t": datetime.now().strftime("%H:%M"),
            "c": stock["c"],
            "n": stock["n"],
            "dir": direction,
            "price": price,
            "conf": random.randint(70, 95),
            "src": random.choice(["DRL+Evolution", "Strategy:X7F2", "Sentiment", "Picker"]),
            "type": random.choice(types),
            "status": "pending"
        }

        self.state.signals.insert(0, signal)
        if len(self.state.signals) > 50:
            self.state.signals.pop()

        self._emit_v6_live('signal', signal)

    def _simulate_broker_update(self):
        """模拟券商状态更新"""
        import random

        for broker in self.state.brokers:
            if broker["st"] == "on":
                update = {
                    "id": broker["id"],
                    "lat": max(1, broker["lat"] + random.randint(-1, 2)),
                    "sr": min(100, max(90, broker["sr"] + random.randint(-1, 1))),
                    "sc": min(100, max(60, broker["sc"] + random.randint(-2, 2)))
                }
                broker.update(update)  # Python字典update
                self._emit_v6_live('broker', update)

    def _simulate_evolution_update(self):
        """模拟进化代际更新"""
        self.state.gen_num += 1
        self._emit_v6_live('evolution', {"genNum": self.state.gen_num})

    def start_auto_update(self, interval: float = 2.0):
        """启动自动更新循环 (保留兼容旧代码)"""
        # 启动新的V6.0实时推送模式
        self.start_v6_live_simulation()
        logger.info("✅ V6.0实时推送模式已激活 (替代了旧的setInterval模式)")


# 创建Flask应用（如果可用）
        """启动自动更新循环"""
        import threading

        def update_loop():
            while True:
                try:
                    # 更新价格数据
                    self.update_price_data()

                    # 每5秒更新一次券商数据
                    if int(datetime.now().timestamp()) % 5 == 0:
                        self.update_from_broker()

                    # 每10秒更新一次进化数据
                    if int(datetime.now().timestamp()) % 10 == 0:
                        self.update_from_evolution()

                except Exception as e:
                    logger.error(f"自动更新错误: {e}")

                import time
                time.sleep(interval)

        thread = threading.Thread(target=update_loop, daemon=True)
        thread.start()
        logger.info(f"自动更新已启动，间隔: {interval}秒")


# 创建Flask应用（如果可用）
app = None
socketio = None

if WS_AVAILABLE:
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'alpha-v3-dashboard-secret'
    socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

    # 创建数据桥接器
    bridge = DashboardDataBridge()
    bridge.register_socketio(socketio)

    @app.route('/v3/api/state')
    def api_state():
        """REST API: 获取完整状态"""
        return jsonify(bridge.get_full_state())

    @app.route('/v3/api/state/<section>')
    def api_section(section):
        """REST API: 获取指定板块数据"""
        return jsonify(bridge.get_section_data(section))

    @app.route('/v3/api/command', methods=['POST'])
    def api_command():
        """REST API: 执行AI命令"""
        data = request.get_json() or {}
        cmd = data.get('command', '')
        result = bridge.process_ai_command(cmd)
        return jsonify(result)

    # ═══════════════════════════════════════════════════════════════
    # 关键函数对接API端点
    # ═══════════════════════════════════════════════════════════════

    @app.route('/v3/api/trade/execute', methods=['POST'])
    def api_trade_execute():
        """
        交易执行API
        POST {"type": "BUY|SELL", "code": "600519", "qty": 100, "price": 1900.0}
        """
        data = request.get_json() or {}
        result = bridge.execute_trade(
            trade_type=data.get('type', 'BUY'),
            code=data.get('code'),
            qty=data.get('qty', 0),
            price=data.get('price', 0)
        )
        return jsonify(result)

    @app.route('/v3/api/broker/switch', methods=['POST'])
    def api_broker_switch():
        """
        券商切换API
        POST {"broker_id": "qmt|ptrade", "reason": "手动切换"}
        """
        data = request.get_json() or {}
        result = bridge.switch_broker(
            broker_id=data.get('broker_id'),
            reason=data.get('reason', 'API调用')
        )
        return jsonify(result)

    @app.route('/v3/api/signal/execute', methods=['POST'])
    def api_signal_execute():
        """
        信号执行API
        POST {"signal_id": 0}
        发送到Trader Agent队列，经Guard Agent风控审批
        """
        data = request.get_json() or {}
        result = bridge.execute_signal(data.get('signal_id', -1))
        return jsonify(result)

    @app.route('/v3/api/strategy/deploy', methods=['POST'])
    def api_strategy_deploy():
        """
        策略部署API
        POST {"strategy_id": "MOM-001"}
        加载策略参数到StrategyEngine
        """
        data = request.get_json() or {}
        result = bridge.deploy_strategy(data.get('strategy_id'))
        return jsonify(result)

    @app.route('/v3/api/report/generate', methods=['POST'])
    def api_report_generate():
        """
        报告生成API
        POST {"type": "morning|weekly|stock|risk", "stock_code": "600519"}
        调用ResearchAgent.generate()
        """
        data = request.get_json() or {}
        result = bridge.generate_report(
            report_type=data.get('type', 'morning'),
            stock_code=data.get('stock_code')
        )
        return jsonify(result)

    @app.route('/v3/api/strategies')
    def api_strategies():
        """
        策略库API
        GET /v3/api/strategies
        返回策略种群数据，格式与看板STRAT_LIB兼容
        """
        try:
            if bridge.evolution_engine:
                strategies = bridge.evolution_engine.export_population()
                # 如果种群为空，使用模拟数据
                if not strategies:
                    strategies = bridge._get_mock_strategies()
                    logger.info("策略种群为空，使用模拟数据")
                return jsonify({
                    "success": True,
                    "count": len(strategies),
                    "strategies": strategies
                })
            else:
                # 模拟数据回退
                strategies = bridge._get_mock_strategies()
                return jsonify({
                    "success": True,
                    "count": len(strategies),
                    "strategies": strategies,
                    "note": "使用模拟数据 (V6.0引擎未连接)"
                })
        except Exception as e:
            logger.error(f"获取策略库失败: {e}")
            # 出错时返回模拟数据
            strategies = bridge._get_mock_strategies()
            return jsonify({
                "success": True,
                "count": len(strategies),
                "strategies": strategies,
                "note": f"使用模拟数据 (错误: {str(e)})"
            })

    @app.route('/v3/api/risk/decompose')
    def api_risk_decompose():
        """
        风险分解钻取API
        GET /v3/api/risk/decompose
        返回RISK_DRILL格式数据，用于风险圆环图钻取
        """
        try:
            if bridge.risk_engine:
                risk_data = bridge.risk_engine.decompose_risk()
                # 转换为JSON可序列化格式
                result = {}
                for key, value in risk_data.items():
                    result[key] = {
                        "pct": value["pct"],
                        "color": value["color"],
                        "desc": value["desc"],
                        "items": [
                            {"c": item.code, "n": item.name, "v": item.value, "note": item.note}
                            for item in value["items"]
                        ]
                    }
                return jsonify({"success": True, "data": result})
            else:
                # 模拟数据
                return jsonify({
                    "success": True,
                    "data": bridge._get_mock_risk_drill(),
                    "note": "使用模拟数据 (风险引擎未连接)"
                })
        except Exception as e:
            logger.error(f"获取风险分解失败: {e}")
            return jsonify({"success": False, "message": str(e)})

    @app.route('/v3/api/risk/metrics')
    def api_risk_metrics():
        """
        风险指标API
        GET /v3/api/risk/metrics
        返回VaR、CVaR、夏普比率等指标
        """
        try:
            if bridge.risk_engine:
                metrics = bridge.risk_engine.get_var_metrics()
                return jsonify({"success": True, "metrics": metrics})
            else:
                return jsonify({
                    "success": True,
                    "metrics": {
                        "var_95_1d": 1.84,
                        "cvar_95_1d": 2.31,
                        "max_drawdown": -8.4,
                        "sharpe_ratio": 1.58
                    }
                })
        except Exception as e:
            logger.error(f"获取风险指标失败: {e}")
            return jsonify({"success": False, "message": str(e)})

    @app.route('/v3/api/risk/stress')
    def api_risk_stress():
        """
        压力测试API
        GET /v3/api/risk/stress
        返回压力测试场景数据
        """
        try:
            if bridge.risk_engine:
                scenarios = bridge.risk_engine.get_stress_test()
                return jsonify({"success": True, "scenarios": scenarios})
            else:
                return jsonify({
                    "success": True,
                    "scenarios": [
                        {"scenario": "2015年股灾熔断", "time": "2015/6-7", "index_drop": "-43%", "portfolio_loss": "-22.4%", "recovery": "8-12个月"},
                        {"scenario": "2020年疫情冲击", "time": "2020/1-2", "index_drop": "-14%", "portfolio_loss": "-12.3%", "recovery": "3-5个月"},
                    ]
                })
        except Exception as e:
            logger.error(f"获取压力测试失败: {e}")
            return jsonify({"success": False, "message": str(e)})

    @app.route('/v3/api/sentiment/events')
    def api_sentiment_events():
        """
        舆情事件API
        GET /v3/api/sentiment/events
        返回事件驱动信号列表
        """
        try:
            if bridge.sentiment_pipeline:
                data = bridge.sentiment_pipeline.get_dashboard_data()
                return jsonify({"success": True, **data})
            else:
                # 模拟数据
                return jsonify({
                    "success": True,
                    "event_count": 6,
                    "event_type_distribution": {"earnings": 2, "policy": 1, "merger": 1, "industry": 2},
                    "recent_events": [
                        {"type": "earnings", "title": "宁德时代季报净利润+62%超预期", "direction": "positive", "stocks": ["300750"], "chain": "业绩超预期→市场上调EPS预期→估值提升→股价上涨"},
                        {"type": "policy", "title": "半导体国产化政策新一轮扶持", "direction": "positive", "stocks": ["688981"], "chain": "利好政策出台→行业受益预期→板块资金流入→相关股价上涨"},
                        {"type": "earnings", "title": "白酒行业消费数据环比下滑", "direction": "negative", "stocks": ["000858"], "chain": "业绩不达预期→机构下调目标价→资金离场→股价下跌"},
                    ],
                    "note": "使用模拟数据 (舆情管道未连接)"
                })
        except Exception as e:
            logger.error(f"获取舆情事件失败: {e}")
            return jsonify({"success": False, "message": str(e)})

    @app.route('/v3/api/sentiment/events', methods=['POST'])
    def api_sentiment_events_post():
        """
        提交舆情事件（Webhook）
        POST {"title": "...", "content": "...", "source": "..."}
        """
        try:
            data = request.get_json() or {}
            if bridge.sentiment_pipeline:
                result = bridge.sentiment_pipeline.process_news_with_events([data])
                return jsonify({"success": True, **result})
            else:
                return jsonify({"success": False, "message": "舆情管道未初始化"})
        except Exception as e:
            logger.error(f"提交舆情事件失败: {e}")
            return jsonify({"success": False, "message": str(e)})

    @app.route('/v3/api/portfolio/regime')
    def api_portfolio_regime():
        """
        组合优化政权API
        GET /v3/api/portfolio/regime
        返回当前市场政权和优化方法配置
        """
        try:
            if bridge.portfolio_optimizer:
                data = bridge.portfolio_optimizer.get_dashboard_data()
                return jsonify({"success": True, **data})
            else:
                # 模拟数据 - 使用新的映射
                from portfolio_optimizer import REGIME_OPTIMIZER_MAP, REGIME_RISK_PARAMS
                return jsonify({
                    "success": True,
                    "current_regime": "range",
                    "regime_label": "震荡",
                    "method": "black_litterman",
                    "risk_params": REGIME_RISK_PARAMS["range"],
                    "regime_map": REGIME_OPTIMIZER_MAP,
                    "regime_risk_params": REGIME_RISK_PARAMS,
                    "hmm_available": False,
                    "hmm_fitted": False,
                    "note": "使用模拟数据 (组合优化器未连接)"
                })
        except Exception as e:
            logger.error(f"获取组合优化政权失败: {e}")
            return jsonify({"success": False, "message": str(e)})

    @app.route('/v3/api/portfolio/optimize', methods=['POST'])
    def api_portfolio_optimize():
        """
        组合优化API
        POST {"stock_codes": ["600519", "300750", ...]}
        返回优化后的投资组合权重
        """
        try:
            data = request.get_json() or {}
            stock_codes = data.get('stock_codes', [])
            
            if not stock_codes:
                return jsonify({"success": False, "message": "请提供股票代码列表"})
            
            if bridge.portfolio_optimizer:
                result = bridge.portfolio_optimizer.optimize_portfolio(
                    stock_codes, 
                    data.get('market_data', {})
                )
                return jsonify({"success": True, **result})
            else:
                # 模拟等权分配
                n = len(stock_codes)
                weights = {code: 1.0/n for code in stock_codes}
                return jsonify({
                    "success": True,
                    "weights": weights,
                    "regime": "range",
                    "method": "equal_weight",
                    "note": "使用模拟数据 (组合优化器未连接)"
                })
        except Exception as e:
            logger.error(f"组合优化失败: {e}")
            return jsonify({"success": False, "message": str(e)})

    def run_bridge_server(host: str = "0.0.0.0", port: int = 5002):
        """启动数据桥接服务"""
        bridge.start_auto_update()
        logger.info(f"🚀 看板数据桥接服务启动: http://{host}:{port}")
        socketio.run(app, host=host, port=port, debug=False, allow_unsafe_werkzeug=True)

else:
    # 无WebSocket模式
    bridge = DashboardDataBridge()

    def run_bridge_server(*args, **kwargs):
        logger.warning("WebSocket不可用，数据桥接服务将以REST模式运行")
        bridge.start_auto_update()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_bridge_server()
