"""
Alpha-Genesis V6.1 SimEdge - 系统集成融合模块
================================================
将模拟盘系统无缝集成到现有 V6.0 架构中

融合点：
1. OMS 订单路由（实盘/模拟盘自动切换）
2. 数据桥接（看板展示模拟盘数据）
3. 策略对接（进化引擎信号自动路由到模拟盘）
4. 知识库归档（模拟盘绩效进入历史知识库）

Author: Alpha-Genesis Team
Version: 6.1.0
Date: 2026-03-09
"""

import os
import sys
import json
import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
from dataclasses import dataclass, asdict

# 添加项目路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入模拟盘系统
from simulation_trading_system import (
    SimulationTradingSystem, SimOrder, SimAccount, SimPosition,
    OrderSide, OrderType, OrderStatus
)

# 导入现有系统组件（如果可用）
try:
    from smart_broker_v2 import SmartBrokerManager
    from dashboard_data_bridge import DashboardBridge
    from historical_knowledge_base import HistoricalKnowledgeBase
    EXISTING_SYSTEM_AVAILABLE = True
except ImportError as e:
    logging.warning(f"部分现有系统组件导入失败: {e}")
    EXISTING_SYSTEM_AVAILABLE = False

logger = logging.getLogger("V6.1Integration")


class V61SystemIntegration:
    """
    V6.1 SimEdge 系统集成器
    实现模拟盘与现有系统的无缝融合
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        初始化 V6.1 集成系统
        
        Args:
            config_path: 配置文件路径
        """
        self.config = self._load_config(config_path)
        self.sim_config = self.config.get("simulation_trading", {})
        
        # 初始化模拟盘系统
        self.sim_system: Optional[SimulationTradingSystem] = None
        self._init_simulation_system()
        
        # 现有系统引用（可选）
        self.broker_manager = None
        self.dashboard_bridge = None
        self.knowledge_base = None
        
        # 回调函数列表
        self._callbacks: List[Callable] = []
        
        # 订单路由状态跟踪
        self._order_routing_stats = {
            "real_orders": 0,
            "sim_orders": 0,
            "total_orders": 0
        }
        
        logger.info("V6.1 SimEdge 集成系统初始化完成")
    
    def _load_config(self, path: str) -> dict:
        """加载配置文件"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"配置文件加载失败: {e}，使用默认配置")
            return {"simulation_trading": {"enabled": True}}
    
    def _init_simulation_system(self):
        """初始化模拟盘系统"""
        if not self.sim_config.get("enabled", True):
            logger.info("模拟盘系统已禁用")
            return
        
        match_cfg = self.sim_config.get("match_engine", {})
        self.sim_system = SimulationTradingSystem(config={
            "commission_rate": match_cfg.get("commission_rate", 0.00025),
            "min_commission": match_cfg.get("min_commission", 5.0),
            "stamp_duty_rate": match_cfg.get("stamp_duty_rate", 0.0005),
            "transfer_fee_rate": match_cfg.get("transfer_fee_rate", 0.00001),
            "slippage_mode": match_cfg.get("slippage_mode", "dynamic"),
            "slippage_bps": match_cfg.get("slippage_bps", 2),
            "initial_capital": self.sim_config.get("default_account", {}).get("initial_capital", 1000000.0)
        })
        
        # 创建默认账户
        default_name = self.sim_config.get("default_account", {}).get("name", "默认模拟账户")
        self.sim_system.create_account(default_name, self.sim_config.get("default_account", {}).get("initial_capital", 1000000.0))
        
        logger.info(f"模拟盘系统初始化完成 | 默认账户: {default_name}")
    
    # ═══════════════════════════════════════════
    # OMS 订单路由（核心融合点）
    # ═══════════════════════════════════════════
    
    def route_order(self, order_request: dict) -> dict:
        """
        订单路由 - 根据 account_type 决定走实盘还是模拟盘
        
        路由规则：
        - account_type == "simulation" → 模拟盘
        - account_type == "real" 或不存在 → 实盘
        
        Args:
            order_request: 订单请求字典
                {
                    "account_type": "simulation" | "real",
                    "account_id": str,
                    "code": str,
                    "name": str,
                    "side": "buy" | "sell",
                    "qty": int,
                    "price": float,
                    "order_type": "market" | "limit",
                    "strategy_id": str
                }
        
        Returns:
            统一格式的执行结果
        """
        account_type = order_request.get("account_type", "real")
        
        if account_type == "simulation":
            return self._execute_simulation_order(order_request)
        else:
            return self._execute_real_order(order_request)
    
    def _execute_simulation_order(self, order_request: dict) -> dict:
        """执行模拟盘订单"""
        if not self.sim_system:
            return {
                "success": False,
                "error": "模拟盘系统未初始化",
                "order_type": "simulation"
            }
        
        try:
            # 提取参数
            account_id = order_request.get("account_id")
            if not account_id:
                # 使用第一个可用账户
                accounts = self.sim_system.list_accounts()
                if not accounts:
                    return {"success": False, "error": "无可用模拟账户"}
                account_id = accounts[0].account_id
            
            # 提交订单到模拟盘
            result = self.sim_system.submit_order(
                account_id=account_id,
                code=order_request["code"],
                name=order_request.get("name", order_request["code"]),
                side=order_request["side"],
                qty=order_request["qty"],
                price=order_request.get("price", 0),
                order_type=order_request.get("order_type", "limit"),
                strategy_id=order_request.get("strategy_id", "")
            )
            
            # 更新统计
            self._order_routing_stats["sim_orders"] += 1
            self._order_routing_stats["total_orders"] += 1
            
            # 触发回调
            self._notify_callbacks({
                "type": "simulation_order_executed",
                "data": result.__dict__
            })
            
            # 返回统一格式
            return {
                "success": result.status == OrderStatus.FILLED,
                "order_id": result.order_id,
                "status": result.status.value,
                "filled_qty": result.filled_qty,
                "filled_price": result.filled_price,
                "commission": result.commission,
                "stamp_duty": result.stamp_duty,
                "order_type": "simulation",
                "account_id": account_id,
                "reject_reason": result.reject_reason if hasattr(result, 'reject_reason') else ""
            }
            
        except Exception as e:
            logger.error(f"模拟盘订单执行失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "order_type": "simulation"
            }
    
    def _execute_real_order(self, order_request: dict) -> dict:
        """执行实盘订单（调用现有券商管理器）"""
        self._order_routing_stats["real_orders"] += 1
        self._order_routing_stats["total_orders"] += 1
        
        if self.broker_manager and EXISTING_SYSTEM_AVAILABLE:
            # 使用 V6.0 券商管理器
            return self.broker_manager.execute_order(order_request)
        else:
            # 模拟模式（无实盘环境）
            logger.warning("实盘券商管理器未初始化，订单未实际执行")
            return {
                "success": False,
                "error": "实盘券商管理器未初始化",
                "order_type": "real",
                "note": "请配置券商管理器以执行实盘订单"
            }
    
    def batch_route_orders(self, orders: List[dict]) -> List[dict]:
        """批量路由订单"""
        results = []
        for order in orders:
            result = self.route_order(order)
            results.append(result)
        return results
    
    # ═══════════════════════════════════════════
    # 策略对接（进化引擎集成）
    # ═══════════════════════════════════════════
    
    def create_strategy_simulation_account(self, strategy_id: str, 
                                           strategy_name: str,
                                           initial_capital: float = 1000000.0) -> str:
        """
        为策略创建专属模拟账户
        
        Args:
            strategy_id: 策略ID
            strategy_name: 策略名称
            initial_capital: 初始资金
        
        Returns:
            account_id: 创建的模拟账户ID
        """
        if not self.sim_system:
            raise RuntimeError("模拟盘系统未初始化")
        
        account_name = f"策略-{strategy_name}-{strategy_id[:8]}"
        account = self.sim_system.create_account(account_name, initial_capital)
        
        logger.info(f"为策略 {strategy_id} 创建模拟账户: {account.account_id}")
        return account.account_id
    
    def route_strategy_signal(self, strategy_id: str, signal: dict) -> dict:
        """
        路由策略信号到模拟盘
        
        Args:
            strategy_id: 策略ID
            signal: 信号字典
                {
                    "action": "buy" | "sell",
                    "code": str,
                    "qty": int,
                    "confidence": float,
                    "price": float (optional)
                }
        
        Returns:
            执行结果
        """
        # 查找策略对应的模拟账户
        sim_account_id = self._find_strategy_account(strategy_id)
        if not sim_account_id:
            logger.warning(f"策略 {strategy_id} 无对应模拟账户，自动创建")
            sim_account_id = self.create_strategy_simulation_account(
                strategy_id, strategy_id
            )
        
        # 构建订单请求
        order_request = {
            "account_type": "simulation",
            "account_id": sim_account_id,
            "code": signal["code"],
            "name": signal.get("name", signal["code"]),
            "side": signal["action"],
            "qty": signal.get("qty", 100),
            "price": signal.get("price", 0),
            "order_type": "market" if signal.get("price", 0) == 0 else "limit",
            "strategy_id": strategy_id
        }
        
        return self.route_order(order_request)
    
    def _find_strategy_account(self, strategy_id: str) -> Optional[str]:
        """查找策略对应的模拟账户"""
        if not self.sim_system:
            return None
        
        for account in self.sim_system.list_accounts():
            if strategy_id in account.name:
                return account.account_id
        return None
    
    # ═══════════════════════════════════════════
    # 知识库归档
    # ═══════════════════════════════════════════
    
    def archive_simulation_performance(self, account_id: str):
        """
        将模拟盘绩效归档到历史知识库
        
        Args:
            account_id: 模拟账户ID
        """
        if not self.sim_system:
            return
        
        snapshot = self.sim_system.snapshot(account_id)
        if not snapshot:
            return
        
        # 归档到知识库（V6.1 增强）
        if self.knowledge_base:
            try:
                # 归档账户快照
                self.knowledge_base.save_simulation_snapshot(snapshot)
                
                # 归档账户的所有交易记录
                trades = self.sim_system.get_trades(account_id)
                for trade in trades:
                    trade_data = {
                        "account_id": account_id,
                        "code": trade.get("code", ""),
                        "name": trade.get("name", ""),
                        "side": trade.get("side", ""),
                        "price": trade.get("price", 0),
                        "qty": trade.get("qty", 0),
                        "amount": trade.get("amount", 0),
                        "strategy": trade.get("strategy", ""),
                        "fees": trade.get("fees", 0),
                        "timestamp": trade.get("time", ""),
                        "strategy_type": trade.get("strategy_type", ""),
                        "signal_source": trade.get("signal_source", "simulation"),
                        "market_regime": trade.get("market_regime", "")
                    }
                    self.knowledge_base.save_simulation_trade(trade_data)
                
                logger.info(f"模拟盘绩效已归档: {account_id} | 交易记录: {len(trades)}")
            except Exception as e:
                logger.error(f"归档失败: {e}")
        
        return snapshot
    
    # ═══════════════════════════════════════════
    # 看板数据对接
    # ═══════════════════════════════════════════
    
    def get_simulation_dashboard_data(self) -> dict:
        """
        获取模拟盘看板数据
        
        Returns:
            看板展示所需的所有数据
        """
        if not self.sim_system:
            return {"enabled": False}
        
        accounts = self.sim_system.list_accounts()
        
        # 汇总数据
        total_accounts = len(accounts)
        total_equity = sum(acc.total_assets for acc in accounts)
        total_pnl = sum(acc.pnl for acc in accounts)
        
        # 账户列表
        account_data = []
        for acc in accounts:
            perf = self.sim_system.get_performance(acc.account_id)
            account_data.append({
                "account_id": acc.account_id,
                "name": acc.name,
                "initial_capital": acc.initial_capital,
                "total_assets": acc.total_assets,
                "pnl": acc.pnl,
                "pnl_pct": acc.pnl_pct,
                "nav": acc.nav,
                "position_count": len(acc.positions),
                "trade_count": len(acc.trades),
                "sharpe": perf.get("sharpe", 0),
                "max_drawdown": perf.get("max_drawdown", 0),
                "win_rate": perf.get("win_rate", 0)
            })
        
        # 按盈亏排序
        account_data.sort(key=lambda x: x["pnl_pct"], reverse=True)
        
        return {
            "enabled": True,
            "summary": {
                "total_accounts": total_accounts,
                "total_equity": total_equity,
                "total_pnl": total_pnl,
                "avg_pnl_pct": sum(a["pnl_pct"] for a in account_data) / len(account_data) if account_data else 0
            },
            "accounts": account_data,
            "routing_stats": self._order_routing_stats,
            "timestamp": datetime.now().isoformat()
        }
    
    def get_simulation_comparison_data(self, real_account_data: dict = None) -> dict:
        """
        获取模拟盘与实盘对比数据
        
        Args:
            real_account_data: 实盘账户数据（可选）
        
        Returns:
            对比数据
        """
        sim_data = self.get_simulation_dashboard_data()
        
        if not real_account_data:
            return {
                "simulation": sim_data,
                "real": None,
                "comparison": None
            }
        
        # 计算差异
        comparison = {}
        sim_accounts = {a["account_id"]: a for a in sim_data.get("accounts", [])}
        
        # TODO: 实现更详细的对比逻辑
        
        return {
            "simulation": sim_data,
            "real": real_account_data,
            "comparison": comparison
        }
    
    # ═══════════════════════════════════════════
    # 回调管理
    # ═══════════════════════════════════════════
    
    def register_callback(self, callback: Callable[[dict], None]):
        """注册回调函数"""
        self._callbacks.append(callback)
    
    def _notify_callbacks(self, event: dict):
        """通知所有回调"""
        for cb in self._callbacks:
            try:
                cb(event)
            except Exception as e:
                logger.error(f"回调执行失败: {e}")
    
    # ═══════════════════════════════════════════
    # 系统对接
    # ═══════════════════════════════════════════
    
    def connect_existing_system(self, 
                                broker_manager=None,
                                dashboard_bridge=None,
                                knowledge_base=None):
        """
        连接现有 V6.0 系统组件
        
        Args:
            broker_manager: 券商管理器实例
            dashboard_bridge: 看板数据桥接实例
            knowledge_base: 历史知识库实例
        """
        self.broker_manager = broker_manager
        self.dashboard_bridge = dashboard_bridge
        self.knowledge_base = knowledge_base
        
        logger.info("V6.1 集成系统已连接现有系统组件")
    
    # ═══════════════════════════════════════════
    # 每日结算
    # ═══════════════════════════════════════════
    
    def daily_settlement(self):
        """每日结算（收盘后调用）"""
        if not self.sim_system:
            return
        
        logger.info("开始 V6.1 每日结算")
        
        # 模拟盘结算
        self.sim_system.daily_settlement()
        
        # 归档所有模拟账户绩效
        for account in self.sim_system.list_accounts():
            self.archive_simulation_performance(account.account_id)
        
        logger.info("V6.1 每日结算完成")
    
    # ═══════════════════════════════════════════
    # 工具方法
    # ═══════════════════════════════════════════
    
    def get_system_status(self) -> dict:
        """获取系统状态"""
        return {
            "version": "6.1.0",
            "codename": "SimEdge",
            "simulation_enabled": self.sim_system is not None,
            "simulation_accounts": len(self.sim_system.list_accounts()) if self.sim_system else 0,
            "routing_stats": self._order_routing_stats,
            "broker_manager_connected": self.broker_manager is not None,
            "knowledge_base_connected": self.knowledge_base is not None,
            "timestamp": datetime.now().isoformat()
        }


# ═══════════════════════════════════════════
# 全局单例
# ═══════════════════════════════════════════

_v61_integration: Optional[V61SystemIntegration] = None


def get_v61_integration(config_path: str = "config.json") -> V61SystemIntegration:
    """获取 V6.1 集成系统单例"""
    global _v61_integration
    if _v61_integration is None:
        _v61_integration = V61SystemIntegration(config_path)
    return _v61_integration


def reset_v61_integration():
    """重置单例（测试用）"""
    global _v61_integration
    _v61_integration = None


# ═══════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════

def route_order(order_request: dict) -> dict:
    """便捷函数：路由订单"""
    integration = get_v61_integration()
    return integration.route_order(order_request)


def create_simulation_account(name: str, capital: float) -> str:
    """便捷函数：创建模拟账户"""
    integration = get_v61_integration()
    if integration.sim_system:
        account = integration.sim_system.create_account(name, capital)
        return account.account_id
    return ""


def get_simulation_performance(account_id: str) -> dict:
    """便捷函数：获取模拟账户绩效"""
    integration = get_v61_integration()
    if integration.sim_system:
        return integration.sim_system.get_performance(account_id)
    return {}


# ═══════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════

if __name__ == "__main__":
    # 测试集成系统
    integration = V61SystemIntegration()
    
    print("V6.1 SimEdge 集成系统测试")
    print("=" * 50)
    
    # 创建测试账户
    account_id = create_simulation_account("测试账户", 1000000)
    print(f"\n创建模拟账户: {account_id}")
    
    # 测试订单路由
    order_result = route_order({
        "account_type": "simulation",
        "account_id": account_id,
        "code": "000001",
        "name": "平安银行",
        "side": "buy",
        "qty": 1000,
        "price": 10.5,
        "order_type": "limit",
        "strategy_id": "TEST_STRATEGY"
    })
    
    print(f"\n订单路由结果:")
    print(json.dumps(order_result, indent=2, ensure_ascii=False))
    
    # 获取系统状态
    status = integration.get_system_status()
    print(f"\n系统状态:")
    print(json.dumps(status, indent=2, ensure_ascii=False))
    
    print("\n✅ V6.1 集成系统测试完成")
