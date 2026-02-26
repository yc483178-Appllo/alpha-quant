# ptrade_executor.py --- PTrade 自动交易执行引擎
# 配置说明：
# - 当前模式：SIMULATION（模拟盘）
# - 建议模拟盘运行时间：30-90 个交易日
# - 人工确认：require_human_confirm = True（必须）
# - 实盘切换：将 TRADING_MODE 改为 "LIVE" 并确保已开通 PTrade 权限

from PoboAPI import *
import requests
import json
from datetime import datetime
from typing import Dict, List, Optional

# ==================== 配置区域 ====================
TRADING_MODE = "SIMULATION"  # 交易模式: SIMULATION(模拟) / LIVE(实盘)
SIGNAL_SERVER = "http://127.0.0.1:8765/api/signals"  # 信号服务器地址
REQUIRE_HUMAN_CONFIRM = True  # 人工二次确认开关（模拟盘阶段必须保持True）

# 风控参数
MAX_POSITION_PCT = 0.20       # 单股最大仓位 20%
MAX_TOTAL_POSITION_PCT = 0.80 # 总仓位上限 80%
STOP_LOSS_PCT = 0.08          # 止损线 8%
TAKE_PROFIT_PCT = 0.20        # 止盈线 20%
DAILY_LOSS_LIMIT_PCT = 0.02   # 单日最大亏损 2%
MAX_TRADES_PER_DAY = 10       # 单日最大交易次数

# 交易参数
COMMISSION_RATE = 0.0003      # 手续费率（万3）
SLIPPAGE = 0.001              # 滑点（千1）
MIN_ORDER_AMOUNT = 100        # 最小下单股数（1手）

# 模拟盘配置
SIMULATION_INITIAL_CASH = 1000000  # 模拟盘初始资金 100万
# ==================================================

class RiskManager:
    """风控管理器"""
    
    def __init__(self, context):
        self.context = context
        self.daily_stats = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "trades_count": 0,
            "daily_pnl": 0.0,
            "max_drawdown": 0.0
        }
    
    def check_stop_loss(self, code: str, current_price: float) -> bool:
        """检查是否触发止损"""
        if not hasattr(self.context, 'positions_cost'):
            return False
        
        if code in self.context.positions_cost:
            cost_price = self.context.positions_cost[code]
            loss_pct = (current_price - cost_price) / cost_price
            if loss_pct <= -STOP_LOSS_PCT:
                log.warning(f"⚠️ 止损触发: {code} 亏损 {loss_pct:.2%} > {STOP_LOSS_PCT:.0%}")
                return True
        return False
    
    def check_take_profit(self, code: str, current_price: float) -> bool:
        """检查是否触发止盈"""
        if not hasattr(self.context, 'positions_cost'):
            return False
        
        if code in self.context.positions_cost:
            cost_price = self.context.positions_cost[code]
            profit_pct = (current_price - cost_price) / cost_price
            if profit_pct >= TAKE_PROFIT_PCT:
                log.warning(f"✅ 止盈触发: {code} 盈利 {profit_pct:.2%} > {TAKE_PROFIT_PCT:.0%}")
                return True
        return False
    
    def check_position_limit(self, account, code: str, order_amount: float, order_price: float) -> bool:
        """检查仓位限制"""
        total_value = account.total_value
        cash = account.cash
        
        # 检查单股仓位
        positions = get_positions()
        current_pos_value = 0
        if code in positions:
            current_pos_value = positions[code].amount * order_price
        
        new_pos_value = current_pos_value + order_amount * order_price
        if new_pos_value > total_value * MAX_POSITION_PCT:
            log.warning(f"❌ 单股仓位超限: {code} 将超过 {MAX_POSITION_PCT:.0%}")
            return False
        
        # 检查总仓位
        total_position_value = sum(pos.amount * order_price for pos in positions.values())
        if total_position_value + order_amount * order_price > total_value * MAX_TOTAL_POSITION_PCT:
            log.warning(f"❌ 总仓位超限: 将超过 {MAX_TOTAL_POSITION_PCT:.0%}")
            return False
        
        return True
    
    def check_daily_limit(self) -> bool:
        """检查日度限制"""
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self.daily_stats["date"]:
            self.daily_stats = {
                "date": today,
                "trades_count": 0,
                "daily_pnl": 0.0,
                "max_drawdown": 0.0
            }
        
        if self.daily_stats["trades_count"] >= MAX_TRADES_PER_DAY:
            log.warning(f"❌ 日交易次数超限: 已达 {MAX_TRADES_PER_DAY} 次")
            return False
        
        return True
    
    def record_trade(self, pnl: float = 0):
        """记录交易"""
        self.daily_stats["trades_count"] += 1
        self.daily_stats["daily_pnl"] += pnl


class SignalServer:
    """信号服务器对接"""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.last_signal_id = 0
    
    def fetch_signals(self) -> List[Dict]:
        """从信号服务器获取交易信号"""
        try:
            resp = requests.get(
                f"{self.server_url}?last_id={self.last_signal_id}", 
                timeout=3
            )
            if resp.status_code == 200:
                data = resp.json()
                signals = data.get("signals", [])
                if signals:
                    self.last_signal_id = signals[-1].get("id", self.last_signal_id)
                return signals
        except Exception as e:
            log.error(f"信号获取失败: {e}")
        return []
    
    def confirm_signal(self, signal_id: int, confirmed: bool, reason: str = ""):
        """向服务器报告信号执行结果"""
        try:
            requests.post(
                f"{self.server_url}/confirm",
                json={
                    "signal_id": signal_id,
                    "confirmed": confirmed,
                    "reason": reason,
                    "timestamp": datetime.now().isoformat()
                },
                timeout=2
            )
        except Exception as e:
            log.error(f"信号确认上报失败: {e}")


def initialize(context):
    """策略初始化"""
    log.info("=" * 60)
    log.info("Alpha Quant - PTrade 自动交易执行引擎")
    log.info("=" * 60)
    log.info(f"交易模式: {TRADING_MODE}")
    log.info(f"人工确认: {'开启' if REQUIRE_HUMAN_CONFIRM else '关闭'}")
    log.info(f"风控参数: 止损{STOP_LOSS_PCT:.0%} / 止盈{TAKE_PROFIT_PCT:.0%} / 单股仓位上限{MAX_POSITION_PCT:.0%}")
    
    # 初始化组件
    context.risk_manager = RiskManager(context)
    context.signal_server = SignalServer(SIGNAL_SERVER)
    context.pending_signals = []  # 待人工确认的信号
    context.positions_cost = {}   # 持仓成本记录
    context.trade_history = []    # 交易历史
    
    # 模拟盘初始化
    if TRADING_MODE == "SIMULATION":
        log.info(f"模拟盘初始资金: ¥{SIMULATION_INITIAL_CASH:,.0f}")
        context.sim_cash = SIMULATION_INITIAL_CASH
        context.sim_positions = {}  # {code: {amount, cost_price}}
    
    log.info("策略初始化完成，开始运行...")


def handle_data(context, data):
    """
    主执行函数 - 每3秒执行一次（PTrade最小间隔）
    """
    # 1. 获取交易信号
    signals = context.signal_server.fetch_signals()
    
    # 2. 处理待确认信号（人工确认模式）
    if REQUIRE_HUMAN_CONFIRM and context.pending_signals:
        process_pending_signals(context)
    
    # 3. 处理新信号
    for signal in signals:
        process_signal(context, signal)
    
    # 4. 风控检查（止损/止盈）
    check_risk_management(context)
    
    # 5. 更新持仓成本
    update_positions_cost(context)


def process_signal(context, signal: Dict):
    """处理交易信号"""
    signal_id = signal.get("id", 0)
    code = signal.get("code", "")
    action = signal.get("action", "").lower()
    price = signal.get("price", 0.0)
    amount = signal.get("amount", 0)
    reason = signal.get("reason", "")
    
    # 参数校验
    if not code or action not in ["buy", "sell"] or price <= 0 or amount < MIN_ORDER_AMOUNT:
        log.error(f"❌ 无效信号: {signal}")
        return
    
    # 人工确认模式
    if REQUIRE_HUMAN_CONFIRM:
        # 添加到待确认队列
        signal["received_time"] = datetime.now()
        context.pending_signals.append(signal)
        log.info(f"⏳ 信号待确认 [{signal_id}]: {action.upper()} {code} @ {price} x {amount}")
        log.info(f"   理由: {reason}")
        
        # 发送通知（可以通过PTrade的通知功能或外部推送）
        send_notification(f"待确认交易: {action.upper()} {code} @ {price}")
        return
    
    # 直接执行模式（仅建议实盘稳定后使用）
    execute_trade(context, signal)


def process_pending_signals(context):
    """处理待人工确认的信号"""
    # 在实际PTrade环境中，这里可以通过弹窗、邮件或APP推送等待用户确认
    # 简化示例：自动超时取消（实际应等待用户输入）
    
    current_time = datetime.now()
    expired_signals = []
    
    for signal in context.pending_signals:
        received_time = signal.get("received_time", current_time)
        elapsed = (current_time - received_time).total_seconds()
        
        # 超过60秒未确认则过期
        if elapsed > 60:
            expired_signals.append(signal)
            log.warning(f"⏰ 信号超时取消: {signal.get('id')}")
            context.signal_server.confirm_signal(
                signal.get("id", 0), 
                False, 
                "超时未确认"
            )
    
    # 移除过期信号
    for sig in expired_signals:
        context.pending_signals.remove(sig)


def execute_trade(context, signal: Dict) -> bool:
    """执行交易"""
    signal_id = signal.get("id", 0)
    code = signal.get("code", "")
    action = signal.get("action", "").lower()
    price = signal.get("price", 0.0)
    amount = signal.get("amount", 0)
    
    # 风控检查
    if not context.risk_manager.check_daily_limit():
        context.signal_server.confirm_signal(signal_id, False, "日交易次数超限")
        return False
    
    account = get_account()
    
    if action == "buy":
        # 买入风控检查
        if not context.risk_manager.check_position_limit(account, code, amount, price):
            context.signal_server.confirm_signal(signal_id, False, "仓位超限")
            return False
        
        # 计算实际成本（含手续费和滑点）
        actual_price = price * (1 + SLIPPAGE)
        total_cost = amount * actual_price * (1 + COMMISSION_RATE)
        
        if TRADING_MODE == "SIMULATION":
            # 模拟盘执行
            if total_cost > context.sim_cash:
                log.error(f"❌ 模拟盘资金不足: 需要¥{total_cost:,.0f}, 可用¥{context.sim_cash:,.0f}")
                return False
            
            context.sim_cash -= total_cost
            if code in context.sim_positions:
                # 加仓，更新成本
                old_amount = context.sim_positions[code]["amount"]
                old_cost = context.sim_positions[code]["cost_price"]
                new_amount = old_amount + amount
                new_cost = (old_amount * old_cost + amount * actual_price) / new_amount
                context.sim_positions[code] = {"amount": new_amount, "cost_price": new_cost}
            else:
                context.sim_positions[code] = {"amount": amount, "cost_price": actual_price}
            
            log.info(f"✅ [模拟盘] 买入 {code} @ {actual_price:.2f} x {amount} = ¥{total_cost:,.0f}")
        else:
            # 实盘执行
            order(code, amount, price=price)
            log.info(f"✅ [实盘] 买入 {code} @ {price} x {amount}")
        
        context.risk_manager.record_trade()
        context.signal_server.confirm_signal(signal_id, True)
        return True
    
    elif action == "sell":
        # 检查持仓
        positions = get_positions() if TRADING_MODE == "LIVE" else context.sim_positions
        
        if code not in positions:
            log.warning(f"⚠️ 无持仓无法卖出: {code}")
            context.signal_server.confirm_signal(signal_id, False, "无持仓")
            return False
        
        actual_amount = min(amount, positions[code]["amount"])
        actual_price = price * (1 - SLIPPAGE)
        total_revenue = actual_amount * actual_price * (1 - COMMISSION_RATE)
        
        if TRADING_MODE == "SIMULATION":
            # 模拟盘执行
            context.sim_cash += total_revenue
            context.sim_positions[code]["amount"] -= actual_amount
            
            if context.sim_positions[code]["amount"] == 0:
                del context.sim_positions[code]
            
            # 计算盈亏
            cost_price = context.positions_cost.get(code, actual_price)
            pnl = (actual_price - cost_price) * actual_amount
            pnl_pct = (actual_price - cost_price) / cost_price if cost_price > 0 else 0
            
            log.info(f"✅ [模拟盘] 卖出 {code} @ {actual_price:.2f} x {actual_amount} = ¥{total_revenue:,.0f}")
            log.info(f"   盈亏: ¥{pnl:,.0f} ({pnl_pct:+.2%})")
            context.risk_manager.record_trade(pnl)
        else:
            # 实盘执行
            order(code, -actual_amount, price=price)
            log.info(f"✅ [实盘] 卖出 {code} @ {price} x {actual_amount}")
            context.risk_manager.record_trade()
        
        context.signal_server.confirm_signal(signal_id, True)
        return True
    
    return False


def check_risk_management(context):
    """风控检查 - 止损/止盈"""
    positions = get_positions() if TRADING_MODE == "LIVE" else context.sim_positions
    
    for code, pos in positions.items():
        # 获取最新价格
        current_price = get_price(code)
        if current_price is None:
            continue
        
        # 检查止损
        if context.risk_manager.check_stop_loss(code, current_price):
            signal = {
                "id": int(datetime.now().timestamp()),
                "code": code,
                "action": "sell",
                "price": current_price,
                "amount": pos["amount"] if isinstance(pos, dict) else pos.amount,
                "reason": "止损平仓"
            }
            if REQUIRE_HUMAN_CONFIRM:
                log.warning(f"⚠️ 止损信号待确认: {code}")
                context.pending_signals.append(signal)
            else:
                execute_trade(context, signal)
        
        # 检查止盈
        elif context.risk_manager.check_take_profit(code, current_price):
            signal = {
                "id": int(datetime.now().timestamp()),
                "code": code,
                "action": "sell",
                "price": current_price,
                "amount": pos["amount"] if isinstance(pos, dict) else pos.amount,
                "reason": "止盈平仓"
            }
            if REQUIRE_HUMAN_CONFIRM:
                log.warning(f"⚠️ 止盈信号待确认: {code}")
                context.pending_signals.append(signal)
            else:
                execute_trade(context, signal)


def update_positions_cost(context):
    """更新持仓成本记录"""
    positions = get_positions() if TRADING_MODE == "LIVE" else context.sim_positions
    
    for code, pos in positions.items():
        if code not in context.positions_cost:
            if isinstance(pos, dict):
                context.positions_cost[code] = pos.get("cost_price", 0)
            else:
                context.positions_cost[code] = pos.cost_price


def send_notification(message: str):
    """发送通知（可扩展为邮件/短信/APP推送）"""
    log.info(f"[通知] {message}")
    # 实际使用时可以接入:
    # - PTrade 内置通知
    # - 邮件通知 (smtplib)
    # - 微信/钉钉推送
    # - 短信通知


def on_order_response(context, order):
    """订单回调处理"""
    log.info(f"订单响应: {order.code} - {order.status} - {order.filled_amount}/{order.amount}")
    
    # 记录交易历史
    context.trade_history.append({
        "time": datetime.now().isoformat(),
        "code": order.code,
        "action": "buy" if order.amount > 0 else "sell",
        "price": order.price,
        "amount": order.filled_amount,
        "status": order.status
    })


def on_account_update(context, account):
    """账户更新回调"""
    if TRADING_MODE == "SIMULATION":
        total_value = context.sim_cash
        for code, pos in context.sim_positions.items():
            current_price = get_price(code) or pos["cost_price"]
            total_value += pos["amount"] * current_price
        
        log.info(f"[模拟盘] 总资产: ¥{total_value:,.0f}, 现金: ¥{context.sim_cash:,.0f}")
    else:
        log.info(f"[实盘] 总资产: ¥{account.total_value:,.0f}, 现金: ¥{account.cash:,.0f}")


# ==================== 信号服务器（配合PTrade使用）====================
# 以下代码运行在独立的服务器上，接收Kimi的交易信号并推送给PTrade

SIGNAL_STORE = []
SIGNAL_ID_COUNTER = 0

class SimpleSignalServer:
    """简易信号服务器 - 用于接收Kimi的交易信号"""
    
    @staticmethod
    def add_signal(code: str, action: str, price: float, amount: int, reason: str = "") -> int:
        """添加新信号"""
        global SIGNAL_ID_COUNTER
        SIGNAL_ID_COUNTER += 1
        
        signal = {
            "id": SIGNAL_ID_COUNTER,
            "code": code,
            "action": action,
            "price": price,
            "amount": amount,
            "reason": reason,
            "status": "pending",  # pending / confirmed / rejected / executed
            "created_at": datetime.now().isoformat(),
            "confirmed_at": None,
            "confirm_reason": ""
        }
        SIGNAL_STORE.append(signal)
        return SIGNAL_ID_COUNTER
    
    @staticmethod
    def get_signals(last_id: int = 0) -> List[Dict]:
        """获取待执行信号"""
        return [s for s in SIGNAL_STORE if s["id"] > last_id and s["status"] == "pending"]
    
    @staticmethod
    def confirm_signal(signal_id: int, confirmed: bool, reason: str = ""):
        """确认信号"""
        for s in SIGNAL_STORE:
            if s["id"] == signal_id:
                s["status"] = "confirmed" if confirmed else "rejected"
                s["confirmed_at"] = datetime.now().isoformat()
                s["confirm_reason"] = reason
                break


if __name__ == "__main__":
    # 测试模式
    print("PTrade Executor 模块")
    print(f"当前模式: {TRADING_MODE}")
    print(f"人工确认: {'开启' if REQUIRE_HUMAN_CONFIRM else '关闭'}")
    print("\n使用说明:")
    print("1. 将本文件上传至PTrade策略编辑器")
    print("2. 确保 SIGNAL_SERVER 地址可访问")
    print("3. 在模拟盘运行至少30个交易日")
    print("4. 策略稳定后，可将 TRADING_MODE 改为 'LIVE' 并确保已开通权限")
