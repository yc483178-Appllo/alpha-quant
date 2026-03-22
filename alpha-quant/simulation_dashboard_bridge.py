"""
Alpha-Genesis V6.1 SimEdge - 看板数据桥接增强
=============================================
扩展 dashboard_data_bridge.py，集成模拟盘数据

Author: Alpha-Genesis Team
Version: 6.1.0
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from simulation_trading_engine import SimulationTradingEngine, create_simulation_engine
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
from dataclasses import dataclass


class SimulationDashboardBridge:
    """
    模拟盘看板数据桥接器
    为看板 V3.0 提供模拟盘数据
    """
    
    def __init__(self, engine: Optional[SimulationTradingEngine] = None):
        self.engine = engine or create_simulation_engine()
    
    # ========== 账户概览面板数据 ==========
    
    def get_accounts_overview(self) -> Dict[str, Any]:
        """获取账户概览数据（用于看板账户列表）"""
        accounts = self.engine.get_all_accounts()
        
        total_equity = sum(acc.total_equity for acc in accounts)
        total_pnl = sum(acc.realized_pnl + acc.unrealized_pnl for acc in accounts)
        
        account_list = []
        for acc in accounts:
            positions = self.engine.get_positions(acc.account_id)
            position_value = sum(p.market_value for p in positions)
            
            account_list.append({
                'account_id': acc.account_id,
                'name': acc.name,
                'initial_capital': acc.initial_capital,
                'total_equity': acc.total_equity,
                'available_cash': acc.available_cash,
                'position_value': position_value,
                'total_return': acc.total_return,
                'realized_pnl': acc.realized_pnl,
                'unrealized_pnl': acc.unrealized_pnl,
                'position_count': len(positions),
                'cash_ratio': acc.available_cash / acc.total_equity if acc.total_equity > 0 else 0,
                'position_ratio': position_value / acc.total_equity if acc.total_equity > 0 else 0,
                'update_time': acc.update_time.isoformat()
            })
        
        # 按总资产排序
        account_list.sort(key=lambda x: x['total_equity'], reverse=True)
        
        return {
            'summary': {
                'total_accounts': len(accounts),
                'total_equity': total_equity,
                'total_pnl': total_pnl,
                'avg_return': sum(acc.total_return for acc in accounts) / len(accounts) if accounts else 0
            },
            'accounts': account_list,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_account_detail(self, account_id: str) -> Dict[str, Any]:
        """获取单个账户详情"""
        account = self.engine.get_account(account_id)
        if not account:
            return {}
        
        positions = self.engine.get_positions(account_id)
        recent_orders = self.engine.get_orders(account_id, limit=20)
        recent_trades = self.engine.get_trades(account_id, limit=20)
        
        position_value = sum(p.market_value for p in positions)
        
        # 计算持仓分布
        position_distribution = {}
        for pos in positions:
            sector = self._get_stock_sector(pos.symbol)
            position_distribution[sector] = position_distribution.get(sector, 0) + pos.market_value
        
        return {
            'account': account.to_dict(),
            'metrics': {
                'position_value': position_value,
                'cash_ratio': account.available_cash / account.total_equity if account.total_equity > 0 else 0,
                'position_ratio': position_value / account.total_equity if account.total_equity > 0 else 0,
                'total_commission': account.total_commission,
                'total_slippage': account.total_slippage
            },
            'positions': [p.to_dict() for p in positions],
            'position_distribution': position_distribution,
            'recent_orders': [o.to_dict() for o in recent_orders],
            'recent_trades': [t.to_dict() for t in recent_trades],
            'timestamp': datetime.now().isoformat()
        }
    
    # ========== 持仓面板数据 ==========
    
    def get_all_positions_summary(self) -> Dict[str, Any]:
        """获取所有账户持仓汇总"""
        accounts = self.engine.get_all_accounts()
        
        all_positions = []
        total_long_value = 0
        total_short_value = 0
        
        for acc in accounts:
            positions = self.engine.get_positions(acc.account_id)
            for pos in positions:
                pos_data = pos.to_dict()
                pos_data['account_name'] = acc.name
                pos_data['account_id'] = acc.account_id
                all_positions.append(pos_data)
                
                if pos.side.value == 'long':
                    total_long_value += pos.market_value
                else:
                    total_short_value += pos.market_value
        
        # 按盈亏排序
        all_positions.sort(key=lambda x: x['total_pnl'], reverse=True)
        
        return {
            'summary': {
                'total_positions': len(all_positions),
                'total_long_value': total_long_value,
                'total_short_value': total_short_value,
                'net_exposure': total_long_value - total_short_value
            },
            'positions': all_positions,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_positions_by_symbol(self, symbol: str) -> List[Dict]:
        """获取某股票在所有账户的持仓"""
        accounts = self.engine.get_all_accounts()
        
        results = []
        for acc in accounts:
            pos = self.engine.get_position(acc.account_id, symbol)
            if pos:
                results.append({
                    'account_id': acc.account_id,
                    'account_name': acc.name,
                    'position': pos.to_dict()
                })
        
        return results
    
    # ========== 交易面板数据 ==========
    
    def get_recent_trades_summary(self, hours: int = 24) -> Dict[str, Any]:
        """获取近期交易汇总"""
        accounts = self.engine.get_all_accounts()
        
        all_trades = []
        for acc in accounts:
            trades = self.engine.get_trades(acc.account_id, limit=100)
            cutoff_time = datetime.now() - timedelta(hours=hours)
            recent_trades = [t for t in trades if t.trade_time > cutoff_time]
            
            for trade in recent_trades:
                trade_data = trade.to_dict()
                trade_data['account_name'] = acc.name
                all_trades.append(trade_data)
        
        # 按时间排序
        all_trades.sort(key=lambda x: x['trade_time'], reverse=True)
        
        # 统计
        buy_volume = sum(t['quantity'] for t in all_trades if t['side'] == 'buy')
        sell_volume = sum(t['quantity'] for t in all_trades if t['side'] == 'sell')
        total_commission = sum(t['commission'] for t in all_trades)
        
        return {
            'summary': {
                'total_trades': len(all_trades),
                'buy_volume': buy_volume,
                'sell_volume': sell_volume,
                'net_volume': buy_volume - sell_volume,
                'total_commission': total_commission
            },
            'trades': all_trades[:50],  # 最多返回50条
            'timestamp': datetime.now().isoformat()
        }
    
    def get_order_flow(self, limit: int = 50) -> List[Dict]:
        """获取订单流数据"""
        accounts = self.engine.get_all_accounts()
        
        all_orders = []
        for acc in accounts:
            orders = self.engine.get_orders(acc.account_id, limit=limit)
            for order in orders:
                order_data = order.to_dict()
                order_data['account_name'] = acc.name
                all_orders.append(order_data)
        
        # 按时间排序
        all_orders.sort(key=lambda x: x['create_time'], reverse=True)
        
        return all_orders[:limit]
    
    # ========== 绩效面板数据 ==========
    
    def get_performance_ranking(self) -> Dict[str, Any]:
        """获取账户绩效排名"""
        accounts = self.engine.get_all_accounts()
        
        rankings = []
        for acc in accounts:
            positions = self.engine.get_positions(acc.account_id)
            position_count = len(positions)
            
            # 计算夏普比率简化版（假设无风险利率3%）
            if acc.total_return != 0:
                sharpe = (acc.total_return - 0.03) / 0.15  # 假设波动率15%
            else:
                sharpe = 0
            
            rankings.append({
                'account_id': acc.account_id,
                'name': acc.name,
                'initial_capital': acc.initial_capital,
                'total_equity': acc.total_equity,
                'total_return': acc.total_return,
                'realized_pnl': acc.realized_pnl,
                'unrealized_pnl': acc.unrealized_pnl,
                'position_count': position_count,
                'sharpe_ratio': sharpe,
                'total_commission': acc.total_commission
            })
        
        # 按收益率排序
        rankings.sort(key=lambda x: x['total_return'], reverse=True)
        
        # 添加排名
        for i, r in enumerate(rankings):
            r['rank'] = i + 1
        
        return {
            'rankings': rankings,
            'best_performer': rankings[0] if rankings else None,
            'worst_performer': rankings[-1] if rankings else None,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_daily_pnl_series(self, days: int = 30) -> List[Dict]:
        """获取每日盈亏序列（模拟数据，实际应从历史表查询）"""
        # TODO: 实现从历史表查询真实数据
        series = []
        for i in range(days):
            date = datetime.now() - timedelta(days=i)
            series.append({
                'date': date.strftime('%Y-%m-%d'),
                'realized_pnl': 0,
                'unrealized_pnl': 0,
                'total_pnl': 0
            })
        
        return list(reversed(series))
    
    # ========== 策略集成面板数据 ==========
    
    def get_strategy_accounts_mapping(self) -> Dict[str, Any]:
        """获取策略与账户映射关系"""
        accounts = self.engine.get_all_accounts()
        
        mapping = []
        for acc in accounts:
            strategy_id = acc.settings.get('strategy_id')
            if strategy_id:
                mapping.append({
                    'strategy_id': strategy_id,
                    'account_id': acc.account_id,
                    'account_name': acc.name,
                    'initial_capital': acc.initial_capital,
                    'current_equity': acc.total_equity,
                    'total_return': acc.total_return
                })
        
        return {
            'mappings': mapping,
            'strategy_count': len(set(m['strategy_id'] for m in mapping)),
            'timestamp': datetime.now().isoformat()
        }
    
    def get_strategy_comparison(self) -> Dict[str, Any]:
        """获取策略对比数据"""
        accounts = self.engine.get_all_accounts()
        
        strategies = {}
        for acc in accounts:
            strategy_id = acc.settings.get('strategy_id')
            if strategy_id:
                if strategy_id not in strategies:
                    strategies[strategy_id] = {
                        'strategy_id': strategy_id,
                        'accounts': [],
                        'total_equity': 0,
                        'total_pnl': 0
                    }
                
                strategies[strategy_id]['accounts'].append({
                    'account_id': acc.account_id,
                    'name': acc.name,
                    'equity': acc.total_equity,
                    'return': acc.total_return
                })
                strategies[strategy_id]['total_equity'] += acc.total_equity
                strategies[strategy_id]['total_pnl'] += (acc.realized_pnl + acc.unrealized_pnl)
        
        # 转换为列表并排序
        strategy_list = list(strategies.values())
        strategy_list.sort(key=lambda x: x['total_pnl'], reverse=True)
        
        return {
            'strategies': strategy_list,
            'count': len(strategy_list),
            'timestamp': datetime.now().isoformat()
        }
    
    # ========== 风险监控面板数据 ==========
    
    def get_risk_overview(self) -> Dict[str, Any]:
        """获取风险概览"""
        accounts = self.engine.get_all_accounts()
        
        total_equity = sum(acc.total_equity for acc in accounts)
        total_position_value = 0
        concentration_risks = []
        
        for acc in accounts:
            positions = self.engine.get_positions(acc.account_id)
            position_value = sum(p.market_value for p in positions)
            total_position_value += position_value
            
            # 检查集中度风险
            for pos in positions:
                if pos.market_value / acc.total_equity > 0.2:  # 超过20%
                    concentration_risks.append({
                        'account_id': acc.account_id,
                        'account_name': acc.name,
                        'symbol': pos.symbol,
                        'position_ratio': pos.market_value / acc.total_equity,
                        'risk_level': 'high' if pos.market_value / acc.total_equity > 0.3 else 'medium'
                    })
        
        return {
            'summary': {
                'total_equity': total_equity,
                'total_position_value': total_position_value,
                'overall_position_ratio': total_position_value / total_equity if total_equity > 0 else 0,
                'concentration_risk_count': len(concentration_risks)
            },
            'concentration_risks': concentration_risks,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_margin_usage(self) -> Dict[str, Any]:
        """获取保证金使用情况"""
        accounts = self.engine.get_all_accounts()
        
        margin_data = []
        for acc in accounts:
            if acc.total_margin_used > 0:
                margin_data.append({
                    'account_id': acc.account_id,
                    'name': acc.name,
                    'margin_used': acc.total_margin_used,
                    'equity': acc.total_equity,
                    'margin_ratio': acc.total_margin_used / acc.total_equity if acc.total_equity > 0 else 0
                })
        
        return {
            'margin_accounts': margin_data,
            'total_margin_used': sum(m['margin_used'] for m in margin_data),
            'timestamp': datetime.now().isoformat()
        }
    
    # ========== 工具方法 ==========
    
    def _get_stock_sector(self, symbol: str) -> str:
        """获取股票所属行业（简化版）"""
        # TODO: 从数据库或外部API获取真实行业数据
        sector_map = {
            '000001': '金融',
            '000002': '地产',
            '600000': '金融',
            '600519': '消费',
            '300750': '新能源',
            '002594': '新能源'
        }
        
        code = symbol.split('.')[0] if '.' in symbol else symbol
        return sector_map.get(code, '其他')
    
    # ========== 统一数据接口 ==========
    
    def get_full_dashboard_data(self) -> Dict[str, Any]:
        """获取完整的看板数据"""
        return {
            'accounts_overview': self.get_accounts_overview(),
            'positions_summary': self.get_all_positions_summary(),
            'recent_trades': self.get_recent_trades_summary(),
            'order_flow': self.get_order_flow(),
            'performance_ranking': self.get_performance_ranking(),
            'strategy_comparison': self.get_strategy_comparison(),
            'risk_overview': self.get_risk_overview(),
            'timestamp': datetime.now().isoformat()
        }


# ========== 与现有 Dashboard Bridge 集成 ==========

def extend_dashboard_bridge(existing_bridge):
    """
    扩展现有 DashboardBridge，添加模拟盘功能
    
    Usage:
        from dashboard_data_bridge import DashboardBridge
        from simulation_dashboard_bridge import extend_dashboard_bridge
        
        bridge = DashboardBridge()
        extend_dashboard_bridge(bridge)
    """
    sim_bridge = SimulationDashboardBridge()
    
    # 添加模拟盘相关方法
    existing_bridge.simulation = sim_bridge
    
    # 添加获取模拟盘数据的方法
    existing_bridge.get_simulation_data = sim_bridge.get_full_dashboard_data
    existing_bridge.get_sim_accounts = sim_bridge.get_accounts_overview
    existing_bridge.get_sim_positions = sim_bridge.get_all_positions_summary
    existing_bridge.get_sim_trades = sim_bridge.get_recent_trades_summary
    existing_bridge.get_sim_performance = sim_bridge.get_performance_ranking
    existing_bridge.get_sim_risk = sim_bridge.get_risk_overview
    
    return existing_bridge


# ========== 独立测试 ==========

if __name__ == '__main__':
    bridge = SimulationDashboardBridge()
    
    # 创建测试账户
    engine = bridge.engine
    account = engine.create_account("测试看板账户", 1000000.0)
    
    # 提交测试订单
    from simulation_trading_engine import OrderSide, OrderType
    engine.set_price_feed(lambda s: 100.0)
    engine.submit_order(
        account.account_id, '000001.SZ', OrderSide.BUY, 1000, OrderType.MARKET
    )
    
    # 获取看板数据
    data = bridge.get_full_dashboard_data()
    print(json.dumps(data, indent=2, ensure_ascii=False))
