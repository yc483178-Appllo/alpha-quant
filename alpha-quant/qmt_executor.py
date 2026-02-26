# qmt_executor.py --- QMT/miniQMT 执行器
# 适用于不支持 PTrade 的券商，通过 miniQMT 的 Python API 对接

from xtquant import xtdata
from xtquant.xttrader import XtQuantTrader, XtQuantTraderCallback
from xtquant.xttype import StockAccount
from xtquant import xtconstant
import requests
import time
import os
from datetime import datetime
from loguru import logger
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()

# ==================== 配置区域 ====================
TRADING_MODE = "SIMULATION"  # SIMULATION(模拟) / LIVE(实盘)
SIGNAL_SERVER = os.getenv("SIGNAL_SERVER_URL", "http://127.0.0.1:8765/api/signals")

# QMT 配置（需要根据实际安装路径修改）
QMT_PATH = os.getenv("QMT_PATH", r"D:\国金QMT\userdata_mini")
ACCOUNT_ID = os.getenv("QMT_ACCOUNT_ID", "YOUR_ACCOUNT_ID")

# 风控参数
MAX_POSITION_PCT = 0.20       # 单股最大仓位 20%
MAX_TOTAL_POSITION_PCT = 0.80 # 总仓位上限 80%
STOP_LOSS_PCT = 0.08          # 止损线 8%
TAKE_PROFIT_PCT = 0.20        # 止盈线 20%
DAILY_LOSS_LIMIT_PCT = 0.02   # 单日最大亏损 2%
MAX_TRADES_PER_DAY = 10       # 单日最大交易次数

# 交易参数
COMMISSION_RATE = 0.0003      # 手续费率
SLIPPAGE = 0.001              # 滑点
MIN_ORDER_AMOUNT = 100        # 最小下单股数
# ==================================================


class AlphaCallback(XtQuantTraderCallback):
    """QMT 交易回调处理"""
    
    def on_order_error(self, order_error):
        """委托失败回调"""
        logger.error(f"❌ 委托失败: {order_error.order_id} | {order_error.error_msg}")
    
    def on_order_stock_async_response(self, response):
        """异步委托回报"""
        logger.info(f"📋 委托回报: {response.order_id} | 状态: {response.seq}")
    
    def on_deal_order(self, deal):
        """成交回报"""
        action = "买入" if deal.order_type == xtconstant.STOCK_BUY else "卖出"
        logger.info(f"✅ 成交回报: {deal.stock_code} | {action} | "
                   f"价格: {deal.dealt_price} | 数量: {deal.dealt_quantity}")
    
    def on_cancel_order(self, cancel):
        """撤单回调"""
        logger.info(f"🚫 撤单: {cancel.order_id}")
    
    def on_query_position_async_response(self, response):
        """持仓查询回调"""
        logger.debug(f"持仓查询: {response}")
    
    def on_query_asset_async_response(self, response):
        """资产查询回调"""
        logger.debug(f"资产查询: {response}")


class QMTRiskManager:
    """QMT 风控管理器"""
    
    def __init__(self):
        self.daily_stats = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "trades_count": 0,
            "daily_pnl": 0.0
        }
    
    def check_daily_limit(self) -> bool:
        """检查日度交易限制"""
        today = datetime.now().strftime("%Y-%m-%d")
        if today != self.daily_stats["date"]:
            self.daily_stats = {"date": today, "trades_count": 0, "daily_pnl": 0.0}
        
        if self.daily_stats["trades_count"] >= MAX_TRADES_PER_DAY:
            logger.warning(f"⚠️ 日交易次数超限: 已达 {MAX_TRADES_PER_DAY} 次")
            return False
        return True
    
    def record_trade(self):
        """记录交易"""
        self.daily_stats["trades_count"] += 1


class QMTExecutor:
    """QMT 执行器"""
    
    def __init__(self):
        self.trader: Optional[XtQuantTrader] = None
        self.account: Optional[StockAccount] = None
        self.risk_manager = QMTRiskManager()
        self.last_signal_id = 0
    
    def init_qmt(self) -> bool:
        """初始化 QMT 连接"""
        logger.info("=" * 60)
        logger.info("初始化 QMT 连接...")
        logger.info(f"QMT 路径: {QMT_PATH}")
        logger.info(f"账户 ID: {ACCOUNT_ID}")
        logger.info(f"交易模式: {TRADING_MODE}")
        logger.info("=" * 60)
        
        # 检查路径
        if not os.path.exists(QMT_PATH):
            logger.error(f"❌ QMT 路径不存在: {QMT_PATH}")
            logger.error("请修改 QMT_PATH 环境变量或 .env 文件")
            return False
        
        try:
            # 创建交易对象
            session_id = int(time.time()) % 100000
            self.trader = XtQuantTrader(QMT_PATH, session_id)
            self.account = StockAccount(ACCOUNT_ID)
            
            # 注册回调
            callback = AlphaCallback()
            self.trader.register_callback(callback)
            
            # 启动交易线程
            self.trader.start()
            
            # 连接 QMT
            connect_result = self.trader.connect()
            if connect_result != 0:
                logger.error(f"❌ QMT 连接失败，错误码: {connect_result}")
                return False
            
            # 订阅账户
            subscribe_result = self.trader.subscribe(self.account)
            if subscribe_result != 0:
                logger.error(f"❌ 账户订阅失败，错误码: {subscribe_result}")
                return False
            
            logger.info("✅ QMT 连接成功")
            
            # 查询初始资产
            self.query_asset()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ QMT 初始化异常: {e}")
            return False
    
    def query_asset(self):
        """查询账户资产"""
        if not self.trader:
            return
        
        try:
            # 同步查询资产
            asset = self.trader.query_stock_asset(self.account)
            if asset:
                logger.info(f"💰 账户资产: 总资金={asset.total_asset:.2f}, "
                           f"可用={asset.cash:.2f}, 市值={asset.market_value:.2f}")
            return asset
        except Exception as e:
            logger.error(f"查询资产失败: {e}")
            return None
    
    def query_positions(self) -> Dict:
        """查询持仓"""
        if not self.trader:
            return {}
        
        try:
            positions = self.trader.query_stock_positions(self.account)
            pos_dict = {}
            for pos in positions:
                pos_dict[pos.stock_code] = {
                    "amount": pos.volume,
                    "available": pos.can_use_volume,
                    "cost_price": pos.open_price,
                    "market_value": pos.market_value
                }
            return pos_dict
        except Exception as e:
            logger.error(f"查询持仓失败: {e}")
            return {}
    
    def check_position_limit(self, code: str, action: str, amount: int, price: float) -> bool:
        """检查仓位限制"""
        asset = self.query_asset()
        if not asset:
            return False
        
        total_value = asset.total_asset
        
        if action == "buy":
            # 检查单股仓位
            positions = self.query_positions()
            current_pos_value = 0
            qmt_code = self._to_qmt_code(code)
            if qmt_code in positions:
                current_pos_value = positions[qmt_code]["market_value"]
            
            new_pos_value = current_pos_value + amount * price
            if new_pos_value > total_value * MAX_POSITION_PCT:
                logger.warning(f"❌ 单股仓位超限: {code} 将超过 {MAX_POSITION_PCT:.0%}")
                return False
            
            # 检查总仓位
            total_position_value = sum(p["market_value"] for p in positions.values())
            if total_position_value + amount * price > total_value * MAX_TOTAL_POSITION_PCT:
                logger.warning(f"❌ 总仓位超限: 将超过 {MAX_TOTAL_POSITION_PCT:.0%}")
                return False
        
        return True
    
    def execute_signal(self, signal: Dict) -> bool:
        """执行交易信号"""
        signal_id = signal.get("id", 0)
        code = signal.get("code", "")
        action = signal.get("action", "").lower()
        price = float(signal.get("price", 0))
        amount = int(signal.get("amount", 0))
        reason = signal.get("reason", "")
        
        # 参数校验
        if not code or action not in ["buy", "sell"] or price <= 0 or amount < MIN_ORDER_AMOUNT:
            logger.error(f"❌ 无效信号: {signal}")
            return False
        
        # 风控检查
        if not self.risk_manager.check_daily_limit():
            return False
        
        # 仓位检查
        if not self.check_position_limit(code, action, amount, price):
            return False
        
        # 转换代码格式
        qmt_code = self._to_qmt_code(code)
        
        # 计算实际价格（含滑点）
        if action == "buy":
            actual_price = price * (1 + SLIPPAGE)
            order_type = xtconstant.STOCK_BUY
            action_name = "买入"
        else:
            actual_price = price * (1 - SLIPPAGE)
            order_type = xtconstant.STOCK_SELL
            action_name = "卖出"
        
        logger.info(f"🚀 执行信号 #{signal_id}: {action_name} {qmt_code} @ {actual_price:.2f} x {amount}")
        logger.info(f"   原因: {reason}")
        
        if TRADING_MODE == "SIMULATION":
            logger.info(f"[模拟盘] 委托成功: {action_name} {qmt_code}")
            self.risk_manager.record_trade()
            return True
        
        # 实盘下单
        try:
            order_id = self.trader.order_stock(
                self.account,
                qmt_code,
                order_type,
                amount,
                xtconstant.FIX_PRICE,
                round(actual_price, 2)
            )
            
            if order_id > 0:
                logger.info(f"✅ 委托成功 | 订单ID: {order_id}")
                self.risk_manager.record_trade()
                return True
            else:
                logger.error(f"❌ 委托失败 | 错误码: {order_id}")
                return False
                
        except Exception as e:
            logger.error(f"❌ 下单异常: {e}")
            return False
    
    def _to_qmt_code(self, code: str) -> str:
        """转换为 QMT 代码格式"""
        code = code.upper().replace("SH.", "").replace("SZ.", "").replace(".SH", "").replace(".SZ", "")
        if code.startswith("6"):
            return f"{code}.SH"
        else:
            return f"{code}.SZ"
    
    def fetch_signals(self) -> List[Dict]:
        """从信号服务器获取信号"""
        try:
            resp = requests.get(
                f"{SIGNAL_SERVER}?last_id={self.last_signal_id}",
                timeout=3
            )
            if resp.status_code == 200:
                data = resp.json()
                signals = data.get("signals", [])
                if signals:
                    self.last_signal_id = signals[-1].get("id", self.last_signal_id)
                return signals
        except Exception as e:
            logger.error(f"获取信号失败: {e}")
        return []
    
    def run(self):
        """主循环"""
        logger.info("=" * 60)
        logger.info("Alpha Quant - QMT 执行器启动")
        logger.info("=" * 60)
        
        # 初始化 QMT
        if not self.init_qmt():
            logger.error("QMT 初始化失败，退出")
            return
        
        logger.info("开始轮询信号...")
        
        while True:
            try:
                # 获取信号
                signals = self.fetch_signals()
                
                for signal in signals:
                    # 执行信号
                    success = self.execute_signal(signal)
                    
                    # 上报执行结果
                    if success:
                        self.confirm_signal(signal["id"], True)
                    else:
                        self.confirm_signal(signal["id"], False, "执行失败")
                
            except Exception as e:
                logger.error(f"执行异常: {e}")
            
            time.sleep(3)
    
    def confirm_signal(self, signal_id: int, success: bool, reason: str = ""):
        """确认信号执行结果"""
        try:
            endpoint = "confirm" if success else "reject"
            requests.post(
                f"{SIGNAL_SERVER}/{endpoint}/{signal_id}",
                json={"reason": reason},
                timeout=2
            )
        except Exception as e:
            logger.error(f"信号确认上报失败: {e}")
    
    def stop(self):
        """停止 QMT"""
        if self.trader:
            self.trader.stop()
            logger.info("QMT 已停止")


def main():
    """主入口"""
    executor = QMTExecutor()
    
    try:
        executor.run()
    except KeyboardInterrupt:
        logger.info("收到中断信号，正在停止...")
    finally:
        executor.stop()


if __name__ == "__main__":
    main()
