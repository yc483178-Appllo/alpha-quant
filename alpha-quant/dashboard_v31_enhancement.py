"""
Alpha-Genesis V6.1 SimEdge - 看板 V3.1 增强模块
=================================================
为看板 V3.0 添加模拟盘相关 UI 组件和数据接口

新增组件：
1. 模拟盘面板（第15个Tab）
2. 实盘/模拟切换开关
3. 模拟盘净值曲线（总览面板）
4. 数据筛选器（历史数据面板）
5. 模拟盘状态徽章（Topbar）

Author: Alpha-Genesis Team
Version: 6.1.0
Date: 2026-03-09
"""

import os
import sys
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

# 导入模拟盘系统
try:
    from simulation_trading_system import SimulationTradingSystem, SimAccount
    from v61_integration import V61SystemIntegration, get_v61_integration
    SIMULATION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"模拟盘模块导入失败: {e}")
    SIMULATION_AVAILABLE = False

logger = logging.getLogger("DashboardV31")


@dataclass
class SimulationDashboardState:
    """模拟盘看板状态"""
    enabled: bool = True
    active_account_id: str = ""  # 当前查看的模拟账户
    trading_mode: str = "real"   # "real" | "simulation" | "both"
    show_comparison: bool = True  # 是否显示实盘/模拟对比
    last_update: str = ""


class SimulationDashboardProvider:
    """
    模拟盘看板数据提供者
    为前端 UI 组件提供数据支持
    """
    
    def __init__(self):
        self.state = SimulationDashboardState()
        self.v61_integration: Optional[V61SystemIntegration] = None
        self._init_integration()
    
    def _init_integration(self):
        """初始化 V6.1 集成系统"""
        if SIMULATION_AVAILABLE:
            try:
                self.v61_integration = get_v61_integration()
                self.state.enabled = True
                self.state.last_update = datetime.now().isoformat()
                
                # 设置默认账户
                if self.v61_integration.sim_system:
                    accounts = self.v61_integration.sim_system.list_accounts()
                    if accounts:
                        self.state.active_account_id = accounts[0].account_id
                        
                logger.info("✅ 模拟盘看板数据提供者已初始化")
            except Exception as e:
                logger.warning(f"V6.1集成初始化失败: {e}")
                self.state.enabled = False
        else:
            self.state.enabled = False
    
    # ═══════════════════════════════════════════════════════════
    # 组件 1: 模拟盘面板（第15个Tab）
    # ═══════════════════════════════════════════════════════════
    
    def get_simulation_panel(self, account_id: str = None) -> Dict:
        """
        获取模拟盘面板完整数据
        
        Returns:
            {
                "account_overview": {...},    # 账户概况
                "positions": [...],           # 持仓明细
                "orders": [...],              # 委托记录
                "trades": [...],              # 成交记录
                "nav_curve": [...],           # 净值曲线
                "performance": {...}          # 绩效指标
            }
        """
        if not self.state.enabled or not self.v61_integration:
            return {"enabled": False, "error": "模拟盘系统未启用"}
        
        account_id = account_id or self.state.active_account_id
        if not account_id:
            return {"enabled": False, "error": "未选择模拟账户"}
        
        sim_system = self.v61_integration.sim_system
        account = sim_system.get_account(account_id)
        
        if not account:
            return {"enabled": False, "error": f"账户 {account_id} 不存在"}
        
        return {
            "enabled": True,
            "account_overview": self._get_account_overview(account),
            "positions": self._get_positions_detail(account_id),
            "orders": self._get_orders_detail(account_id),
            "trades": self._get_trades_detail(account_id),
            "nav_curve": self._get_nav_curve(account),
            "performance": sim_system.get_performance(account_id),
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_account_overview(self, account: SimAccount) -> Dict:
        """获取账户概况"""
        return {
            "account_id": account.account_id,
            "name": account.name,
            "initial_capital": account.initial_capital,
            "total_assets": account.total_assets,
            "cash": account.cash,
            "market_value": account.market_value,
            "pnl": account.pnl,
            "pnl_pct": round(account.pnl_pct, 2),
            "nav": round(account.nav, 4),
            "position_count": len(account.positions),
            "trade_count": len(account.trades),
            "created_at": account.created_at
        }
    
    def _get_positions_detail(self, account_id: str) -> List[Dict]:
        """获取持仓明细"""
        if not self.v61_integration:
            return []
        
        positions = self.v61_integration.sim_system.get_positions(account_id)
        result = []
        for code, pos in positions.items():
            result.append({
                "code": pos.code,
                "name": pos.name,
                "qty": pos.qty,
                "available_qty": pos.available_qty,
                "cost_price": round(pos.cost_price, 2),
                "current_price": round(pos.current_price, 2),
                "market_value": round(pos.qty * pos.current_price, 2),
                "pnl": round(pos.pnl, 2),
                "pnl_pct": round(pos.pnl_pct, 2),
                "buy_date": pos.buy_date,
                "weight": 0  # 持仓占比，需要计算
            })
        
        # 计算权重
        total_mv = sum(p["market_value"] for p in result)
        for p in result:
            p["weight"] = round(p["market_value"] / total_mv * 100, 2) if total_mv > 0 else 0
        
        # 按市值排序
        result.sort(key=lambda x: x["market_value"], reverse=True)
        return result
    
    def _get_orders_detail(self, account_id: str, limit: int = 20) -> List[Dict]:
        """获取委托记录"""
        if not self.v61_integration:
            return []
        
        orders = self.v61_integration.sim_system.get_orders(account_id)
        result = []
        for order in orders[-limit:]:
            result.append({
                "order_id": order.order_id,
                "code": order.code,
                "name": order.name,
                "side": order.side.value,
                "order_type": order.order_type.value,
                "price": order.price,
                "qty": order.qty,
                "filled_qty": order.filled_qty,
                "filled_price": order.filled_price,
                "status": order.status.value,
                "created_at": order.created_at,
                "filled_at": order.filled_at,
                "commission": order.commission,
                "stamp_duty": order.stamp_duty,
                "slippage_cost": order.slippage_cost,
                "strategy_id": order.strategy_id
            })
        return result
    
    def _get_trades_detail(self, account_id: str, limit: int = 20) -> List[Dict]:
        """获取成交记录"""
        if not self.v61_integration:
            return []
        
        trades = self.v61_integration.sim_system.get_trades(account_id, limit)
        return trades
    
    def _get_nav_curve(self, account: SimAccount, days: int = 30) -> List[Dict]:
        """获取净值曲线数据"""
        nav_history = account.nav_history
        
        if not nav_history:
            # 生成模拟数据
            return self._generate_mock_nav_curve(account, days)
        
        # 使用真实数据
        return nav_history[-days:] if len(nav_history) > days else nav_history
    
    def _generate_mock_nav_curve(self, account: SimAccount, days: int) -> List[Dict]:
        """生成模拟净值曲线（用于新账户）"""
        import random
        curve = []
        base_nav = 1.0
        
        for i in range(days, 0, -1):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            change = random.uniform(-0.02, 0.025)
            base_nav *= (1 + change)
            curve.append({
                "date": date,
                "nav": round(base_nav, 4),
                "total_assets": round(account.initial_capital * base_nav, 2)
            })
        
        return curve
    
    def get_simulation_accounts_list(self) -> List[Dict]:
        """获取模拟账户列表（用于下拉选择）"""
        if not self.v61_integration or not self.v61_integration.sim_system:
            return []
        
        accounts = self.v61_integration.sim_system.list_accounts()
        return [{
            "account_id": acc.account_id,
            "name": acc.name,
            "nav": round(acc.nav, 4),
            "pnl_pct": round(acc.pnl_pct, 2),
            "total_assets": acc.total_assets
        } for acc in accounts]
    
    # ═══════════════════════════════════════════════════════════
    # 组件 2: 实盘/模拟切换开关状态
    # ═══════════════════════════════════════════════════════════
    
    def get_trading_mode_switch(self) -> Dict:
        """
        获取交易模式切换开关状态
        
        Returns:
            {
                "current_mode": "real" | "simulation" | "both",
                "modes": [
                    {"id": "real", "name": "实盘", "color": "#52c41a"},
                    {"id": "simulation", "name": "模拟盘", "color": "#722ed1"},
                    {"id": "both", "name": "并行", "color": "#faad14"}
                ],
                "warning": "..."  // 模式切换时的警告信息
            }
        """
        return {
            "current_mode": self.state.trading_mode,
            "modes": [
                {"id": "real", "name": "实盘交易", "color": "#52c41a", "description": "所有订单路由到实盘券商"},
                {"id": "simulation", "name": "模拟盘", "color": "#722ed1", "description": "所有订单在模拟环境执行"},
                {"id": "both", "name": "实盘+模拟", "color": "#faad14", "description": "同时执行实盘和模拟交易"}
            ],
            "warning": self._get_mode_switch_warning(),
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_mode_switch_warning(self) -> str:
        """获取模式切换警告"""
        if self.state.trading_mode == "real":
            return "⚠️ 实盘模式：订单将真实成交，请谨慎操作"
        elif self.state.trading_mode == "simulation":
            return "ℹ️ 模拟模式：订单仅在模拟环境执行，无真实资金风险"
        else:
            return "⚠️ 并行模式：实盘和模拟将同时执行，注意资金分配"
    
    def set_trading_mode(self, mode: str) -> Dict:
        """设置交易模式"""
        if mode not in ["real", "simulation", "both"]:
            return {"success": False, "error": "无效的交易模式"}
        
        old_mode = self.state.trading_mode
        self.state.trading_mode = mode
        
        logger.info(f"交易模式切换: {old_mode} → {mode}")
        
        return {
            "success": True,
            "previous_mode": old_mode,
            "current_mode": mode,
            "message": f"已切换至{'实盘' if mode=='real' else '模拟盘' if mode=='simulation' else '并行'}模式"
        }
    
    # ═══════════════════════════════════════════════════════════
    # 组件 3: 模拟盘净值曲线（总览面板）
    # ═══════════════════════════════════════════════════════════
    
    def get_combined_nav_curve(self, days: int = 30) -> Dict:
        """
        获取组合净值曲线（实盘+模拟盘对比）
        
        Returns:
            {
                "dates": ["2026-03-01", ...],
                "real_nav": [1.0, 1.02, ...],      // 实盘净值
                "sim_nav": [1.0, 1.015, ...],      // 模拟盘净值
                "benchmark": [1.0, 1.01, ...],     // 基准净值
                "comparison": {
                    "real_total_return": 5.2,
                    "sim_total_return": 4.8,
                    "tracking_error": 0.4
                }
            }
        """
        dates = []
        real_nav = []
        sim_nav = []
        benchmark = []
        
        # 生成日期序列
        for i in range(days, 0, -1):
            date = datetime.now() - timedelta(days=i)
            dates.append(date.strftime("%Y-%m-%d"))
        
        # TODO: 从实际数据源获取实盘净值
        # 这里使用模拟数据
        import random
        real_base = 1.0
        sim_base = 1.0
        bench_base = 1.0
        
        for _ in range(days):
            real_change = random.uniform(-0.015, 0.02)
            sim_change = real_change + random.uniform(-0.005, 0.005)  # 模拟盘有轻微差异
            bench_change = random.uniform(-0.01, 0.015)
            
            real_base *= (1 + real_change)
            sim_base *= (1 + sim_change)
            bench_base *= (1 + bench_change)
            
            real_nav.append(round(real_base, 4))
            sim_nav.append(round(sim_base, 4))
            benchmark.append(round(bench_base, 4))
        
        real_return = (real_nav[-1] - 1) * 100
        sim_return = (sim_nav[-1] - 1) * 100
        tracking_error = abs(real_return - sim_return)
        
        return {
            "dates": dates,
            "real_nav": real_nav,
            "sim_nav": sim_nav,
            "benchmark": benchmark,
            "comparison": {
                "real_total_return": round(real_return, 2),
                "sim_total_return": round(sim_return, 2),
                "tracking_error": round(tracking_error, 2),
                "correlation": round(1 - tracking_error/100, 2)
            },
            "chart_config": {
                "real_line": {"color": "#52c41a", "type": "solid", "name": "实盘净值"},
                "sim_line": {"color": "#722ed1", "type": "dashed", "name": "模拟盘净值"},
                "benchmark_line": {"color": "#999999", "type": "dotted", "name": "基准"}
            }
        }
    
    # ═══════════════════════════════════════════════════════════
    # 组件 4: 数据筛选器（历史数据面板）
    # ═══════════════════════════════════════════════════════════
    
    def get_filtered_trade_history(self, filter_type: str = "all", limit: int = 50) -> Dict:
        """
        获取筛选后的交易历史
        
        Args:
            filter_type: "real" | "simulation" | "all"
            limit: 返回记录数
        
        Returns:
            {
                "filter": "all",
                "real_count": 30,
                "sim_count": 20,
                "trades": [...]
            }
        """
        trades = []
        
        # 实盘交易（TODO: 从实际数据源获取）
        if filter_type in ["real", "all"]:
            real_trades = self._get_mock_real_trades(limit//2)
            for t in real_trades:
                t["account_type"] = "real"
                t["badge_color"] = "#52c41a"
            trades.extend(real_trades)
        
        # 模拟盘交易
        if filter_type in ["simulation", "all"] and self.v61_integration:
            for account in self.v61_integration.sim_system.list_accounts():
                sim_trades = self.v61_integration.sim_system.get_trades(account.account_id, limit//2)
                for t in sim_trades:
                    t["account_type"] = "simulation"
                    t["badge_color"] = "#722ed1"
                    t["account_name"] = account.name
                trades.extend(sim_trades)
        
        # 按时间排序
        trades.sort(key=lambda x: x.get("time", ""), reverse=True)
        
        real_count = sum(1 for t in trades if t.get("account_type") == "real")
        sim_count = sum(1 for t in trades if t.get("account_type") == "simulation")
        
        return {
            "filter": filter_type,
            "real_count": real_count,
            "sim_count": sim_count,
            "total_count": len(trades),
            "trades": trades[:limit],
            "filters": [
                {"id": "all", "name": "全部", "count": real_count + sim_count},
                {"id": "real", "name": "实盘", "count": real_count, "color": "#52c41a"},
                {"id": "simulation", "name": "模拟盘", "count": sim_count, "color": "#722ed1"}
            ]
        }
    
    def _get_mock_real_trades(self, limit: int) -> List[Dict]:
        """获取模拟的实盘交易记录"""
        trades = []
        import random
        
        stocks = [
            {"code": "600519", "name": "贵州茅台"},
            {"code": "000001", "name": "平安银行"},
            {"code": "300750", "name": "宁德时代"},
            {"code": "601012", "name": "隆基绿能"}
        ]
        
        for i in range(limit):
            stock = random.choice(stocks)
            side = random.choice(["buy", "sell"])
            price = random.uniform(50, 500)
            qty = random.choice([100, 200, 500, 1000])
            
            trades.append({
                "trade_id": f"R{datetime.now().strftime('%Y%m%d%H%M%S')}{i}",
                "code": stock["code"],
                "name": stock["name"],
                "side": side,
                "price": round(price, 2),
                "qty": qty,
                "amount": round(price * qty, 2),
                "time": (datetime.now() - timedelta(hours=i*2)).isoformat(),
                "broker": "华泰PTrade",
                "strategy_id": f"STRATEGY_{random.randint(1,5)}"
            })
        
        return trades
    
    # ═══════════════════════════════════════════════════════════
    # 组件 5: 模拟盘状态徽章（Topbar）
    # ═══════════════════════════════════════════════════════════
    
    def get_simulation_status_badge(self) -> Dict:
        """
        获取模拟盘状态徽章数据
        
        Returns:
            {
                "visible": true,
                "status": "running" | "paused" | "error",
                "text": "模拟盘运行中",
                "account_count": 3,
                "badge_color": "#722ed1",
                "tooltip": "3个模拟账户正在运行",
                "alert": null  // 或警告信息
            }
        """
        if not self.state.enabled:
            return {
                "visible": False,
                "status": "disabled",
                "text": "模拟盘未启用"
            }
        
        account_count = 0
        if self.v61_integration and self.v61_integration.sim_system:
            account_count = len(self.v61_integration.sim_system.list_accounts())
        
        return {
            "visible": True,
            "status": "running",
            "text": f"模拟盘 · {account_count}账户",
            "account_count": account_count,
            "badge_color": "#722ed1",
            "bg_color": "#f9f0ff",
            "border_color": "#d3adf7",
            "tooltip": f"{account_count}个模拟账户正在运行，点击切换至模拟盘面板",
            "alert": None,
            "timestamp": datetime.now().isoformat()
        }
    
    # ═══════════════════════════════════════════════════════════
    # 统一数据接口
    # ═══════════════════════════════════════════════════════════
    
    def get_all_v31_data(self) -> Dict:
        """获取所有 V3.1 增强数据"""
        return {
            "simulation_enabled": self.state.enabled,
            "simulation_panel": self.get_simulation_panel(),
            "trading_mode_switch": self.get_trading_mode_switch(),
            "combined_nav": self.get_combined_nav_curve(),
            "trade_history": self.get_filtered_trade_history(),
            "status_badge": self.get_simulation_status_badge(),
            "accounts_list": self.get_simulation_accounts_list(),
            "timestamp": datetime.now().isoformat()
        }


# ═══════════════════════════════════════════════════════════
# Flask API 路由扩展
# ═══════════════════════════════════════════════════════════

def register_v31_routes(app, provider: SimulationDashboardProvider = None):
    """注册 V3.1 API 路由到 Flask 应用"""
    
    if provider is None:
        provider = SimulationDashboardProvider()
    
    # 模拟盘面板数据
    @app.route('/api/v3/dashboard/simulation', methods=['GET'])
    def api_simulation_panel():
        """模拟盘面板"""
        account_id = request.args.get('account_id')
        return jsonify(provider.get_simulation_panel(account_id))
    
    # 模拟账户列表
    @app.route('/api/v3/dashboard/simulation/accounts', methods=['GET'])
    def api_simulation_accounts():
        """模拟账户列表"""
        return jsonify({
            "accounts": provider.get_simulation_accounts_list(),
            "current_account_id": provider.state.active_account_id
        })
    
    # 交易模式切换
    @app.route('/api/v3/dashboard/trading-mode', methods=['GET', 'POST'])
    def api_trading_mode():
        """交易模式切换"""
        if request.method == 'POST':
            data = request.get_json() or {}
            mode = data.get('mode')
            return jsonify(provider.set_trading_mode(mode))
        else:
            return jsonify(provider.get_trading_mode_switch())
    
    # 组合净值曲线
    @app.route('/api/v3/dashboard/combined-nav', methods=['GET'])
    def api_combined_nav():
        """组合净值曲线"""
        days = request.args.get('days', 30, type=int)
        return jsonify(provider.get_combined_nav_curve(days))
    
    # 筛选后的交易历史
    @app.route('/api/v3/dashboard/trade-history', methods=['GET'])
    def api_trade_history():
        """交易历史（带筛选）"""
        filter_type = request.args.get('filter', 'all')
        limit = request.args.get('limit', 50, type=int)
        return jsonify(provider.get_filtered_trade_history(filter_type, limit))
    
    # 模拟盘状态徽章
    @app.route('/api/v3/dashboard/simulation-status', methods=['GET'])
    def api_simulation_status():
        """模拟盘状态徽章"""
        return jsonify(provider.get_simulation_status_badge())
    
    # 所有 V3.1 数据
    @app.route('/api/v3/dashboard/v31/all', methods=['GET'])
    def api_v31_all():
        """所有 V3.1 数据"""
        return jsonify(provider.get_all_v31_data())
    
    logger.info("✅ V3.1 API 路由已注册")


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    provider = SimulationDashboardProvider()
    
    print("\n=== Alpha 看板 V3.1 数据测试 ===\n")
    
    print("1. 模拟盘面板:")
    print(json.dumps(provider.get_simulation_panel(), indent=2, ensure_ascii=False)[:500])
    
    print("\n2. 交易模式切换:")
    print(json.dumps(provider.get_trading_mode_switch(), indent=2, ensure_ascii=False))
    
    print("\n3. 组合净值曲线:")
    nav_data = provider.get_combined_nav_curve(10)
    print(f"   实盘收益: {nav_data['comparison']['real_total_return']}%")
    print(f"   模拟收益: {nav_data['comparison']['sim_total_return']}%")
    
    print("\n4. 状态徽章:")
    print(json.dumps(provider.get_simulation_status_badge(), indent=2, ensure_ascii=False))
    
    print("\n✅ V3.1 数据测试完成")
