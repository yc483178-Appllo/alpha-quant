# backtest_engine.py --- 增强版策略回测引擎
# 新增：真实交易逻辑、手续费计算、滑点模拟、可视化、多策略对比

import baostock as bs
import tushare as ts
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from loguru import logger
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from typing import Dict, List, Optional, Tuple
import json

# Tushare Token 配置（从环境变量或配置文件读取）
TUSHARE_TOKEN = None  # 将在初始化时设置

def set_tushare_token(token: str):
    """设置 Tushare Token"""
    global TUSHARE_TOKEN
    TUSHARE_TOKEN = token
    ts.set_token(token)
    return ts.pro_api()

class DataProvider:
    """统一数据接口 - 支持 Baostock 和 Tushare"""
    
    def __init__(self, source: str = "baostock", tushare_token: Optional[str] = None):
        self.source = source
        self.pro = None
        if source == "tushare" and tushare_token:
            self.pro = set_tushare_token(tushare_token)
    
    def login(self):
        """登录数据源"""
        if self.source == "baostock":
            bs.login()
    
    def logout(self):
        """登出数据源"""
        if self.source == "baostock":
            bs.logout()
    
    def get_stock_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """获取股票历史数据"""
        if self.source == "tushare" and self.pro:
            return self._get_tushare_data(stock_code, start_date, end_date)
        else:
            return self._get_baostock_data(stock_code, start_date, end_date)
    
    def _get_baostock_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从 Baostock 获取数据"""
        rs = bs.query_history_k_data_plus(
            stock_code, "date,open,high,low,close,volume,amount,turn",
            start_date=start_date,
            end_date=end_date,
            frequency="d", adjustflag="2"
        )
        if rs is None:
            logger.error("Baostock 返回空数据")
            return pd.DataFrame()
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            row = rs.get_row_data()
            data_list.append(row)
        
        if not data_list:
            logger.error("Baostock 返回空数据列表")
            return pd.DataFrame()
        
        data = pd.DataFrame(data_list, columns=rs.fields)
        
        # 转换数据类型
        numeric_cols = ["open", "high", "low", "close", "volume", "amount", "turn"]
        for col in numeric_cols:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors="coerce")
        
        data["date"] = pd.to_datetime(data["date"])
        return data.dropna()
        # 转换数据类型
        numeric_cols = ["open", "high", "low", "close", "volume", "amount", "turn"]
        for col in numeric_cols:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors="coerce")
        
        data["date"] = pd.to_datetime(data["date"])
        logger.info(f"获取到 {len(data)} 条数据")
        return data.dropna()
    
    def _get_tushare_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """从 Tushare 获取数据"""
        # 转换股票代码格式
        ts_code = self._convert_code(stock_code)
        
        df = self.pro.daily(ts_code=ts_code, start_date=start_date.replace("-", ""), 
                           end_date=end_date.replace("-", ""))
        if df is None or df.empty:
            return pd.DataFrame()
        
        df = df.sort_values("trade_date")
        df["date"] = pd.to_datetime(df["trade_date"])
        df = df.rename(columns={
            "open": "open", "high": "high", "low": "low", 
            "close": "close", "vol": "volume", "amount": "amount"
        })
        
        # 获取换手率数据
        basic = self.pro.daily_basic(ts_code=ts_code, start_date=start_date.replace("-", ""),
                                     end_date=end_date.replace("-", ""))
        if basic is not None and not basic.empty:
            basic["date"] = pd.to_datetime(basic["trade_date"])
            df = df.merge(basic[["date", "turnover_rate"]], on="date", how="left")
            df["turn"] = df["turnover_rate"]
        
        return df[["date", "open", "high", "low", "close", "volume", "amount", "turn"]].dropna()
    
    def _convert_code(self, bs_code: str) -> str:
        """Baostock 代码转 Tushare 代码"""
        if bs_code.startswith("sh."):
            return bs_code.replace("sh.", "") + ".SH"
        elif bs_code.startswith("sz."):
            return bs_code.replace("sz.", "") + ".SZ"
        return bs_code
    
    def get_stock_basic(self) -> pd.DataFrame:
        """获取股票基础信息（Tushare 专用）"""
        if self.pro:
            df = self.pro.stock_basic(exchange='', list_status='L', 
                                     fields='ts_code,symbol,name,area,industry,market,list_date')
            return df
        return pd.DataFrame()


class MultiFactorStrategy:
    """多因子选股策略"""
    
    def __init__(self, data_provider: DataProvider):
        self.dp = data_provider
    
    def momentum_factor(self, df: pd.DataFrame, lookback: int = 20) -> pd.Series:
        """动量因子：N日收益率"""
        return df["close"].pct_change(lookback)
    
    def volatility_factor(self, df: pd.DataFrame, lookback: int = 20) -> pd.Series:
        """波动率因子：N日收益率标准差"""
        return df["close"].pct_change().rolling(lookback).std()
    
    def volume_factor(self, df: pd.DataFrame, lookback: int = 20) -> pd.Series:
        """成交量因子：N日均量/近期均量"""
        return df["volume"] / df["volume"].rolling(lookback).mean()
    
    def rsi_factor(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """RSI因子"""
        delta = df["close"].diff()
        gain = (delta.where(delta > 0, 0)).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi / 100  # 归一化到0-1
    
    def ma_trend_factor(self, df: pd.DataFrame) -> pd.Series:
        """均线趋势因子：价格在MA20上方且MA5>MA20"""
        ma5 = df["close"].rolling(5).mean()
        ma20 = df["close"].rolling(20).mean()
        return ((df["close"] > ma20) & (ma5 > ma20)).astype(float)
    
    def compute_composite_score(self, df: pd.DataFrame) -> pd.Series:
        """计算综合因子得分"""
        mom = self.momentum_factor(df)
        vol = self.volatility_factor(df)
        volume = self.volume_factor(df)
        rsi = self.rsi_factor(df)
        trend = self.ma_trend_factor(df)
        
        # 综合得分（动量正向，波动率负向）
        score = (
            mom * 0.3 +           # 动量 30%
            (1 - vol * 10) * 0.2 + # 低波动 20%（波动率越小越好）
            (volume - 1) * 0.2 +   # 放量 20%
            rsi * 0.15 +           # RSI 15%
            trend * 0.15           # 趋势 15%
        )
        return score


def run_backtest(stock_code="sh.600036", start_date="2023-01-01", end_date="2025-12-31",
                 capital=100000, strategy="ma_cross", commission=0.0003, slippage=0.001,
                 data_source="baostock", tushare_token=None, plot=True):
    """
    完整策略回测引擎

    参数:
        stock_code: 股票代码（Baostock格式，如 sh.600036）
        start_date/end_date: 回测区间
        capital: 初始资金
        strategy: 策略类型 (ma_cross / momentum / mean_revert / multi_factor)
        commission: 手续费率（双边）
        slippage: 滑点（百分比）
        data_source: 数据源 (baostock / tushare)
        tushare_token: Tushare API Token
        plot: 是否绘制图表
    """
    logger.info(f"回测开始 | 标的: {stock_code} | 区间: {start_date} ~ {end_date} | 策略: {strategy} | 数据源: {data_source}")

    # 初始化数据接口
    dp = DataProvider(source=data_source, tushare_token=tushare_token)
    dp.login()

    # 获取历史数据
    data = dp.get_stock_data(stock_code, start_date, end_date)
    
    if data.empty:
        logger.error("无有效数据")
        dp.logout()
        return None

    # 计算技术指标
    data["ma5"] = data["close"].rolling(5).mean()
    data["ma10"] = data["close"].rolling(10).mean()
    data["ma20"] = data["close"].rolling(20).mean()
    data["ma60"] = data["close"].rolling(60).mean()
    data["rsi14"] = compute_rsi(data["close"], 14)
    data["atr14"] = compute_atr(data, 14)
    
    # 多因子策略计算
    if strategy == "multi_factor":
        mf = MultiFactorStrategy(dp)
        data["factor_score"] = mf.compute_composite_score(data)
    
    data = data.dropna()

    # === 策略信号生成 ===
    if strategy == "ma_cross":
        # 双均线交叉策略（5日/20日均线）
        data["signal"] = 0
        data.loc[data["ma5"] > data["ma20"], "signal"] = 1
        data.loc[data["ma5"] < data["ma20"], "signal"] = -1

    elif strategy == "momentum":
        # 动量策略（20日收益率排名）
        data["ret20"] = data["close"].pct_change(20)
        data["signal"] = 0
        data.loc[data["ret20"] > 0.05, "signal"] = 1
        data.loc[data["ret20"] < -0.05, "signal"] = -1

    elif strategy == "mean_revert":
        # 均值回归策略（布林带）
        data["bb_mid"] = data["close"].rolling(20).mean()
        data["bb_std"] = data["close"].rolling(20).std()
        data["bb_upper"] = data["bb_mid"] + 2 * data["bb_std"]
        data["bb_lower"] = data["bb_mid"] - 2 * data["bb_std"]
        data["signal"] = 0
        data.loc[data["close"] < data["bb_lower"], "signal"] = 1
        data.loc[data["close"] > data["bb_upper"], "signal"] = -1
    
    elif strategy == "multi_factor":
        # 多因子策略：综合得分高于阈值买入，低于阈值卖出
        data["signal"] = 0
        data.loc[data["factor_score"] > 0.1, "signal"] = 1
        data.loc[data["factor_score"] < -0.1, "signal"] = -1

    # === 模拟交易 ===
    cash = capital
    shares = 0
    portfolio_values = []
    trades = []
    
    # 记录每日持仓状态
    daily_records = []

    for i, row in data.iterrows():
        # 计算当前市值
        portfolio_value = cash + shares * row["close"]
        portfolio_values.append(portfolio_value)
        
        daily_records.append({
            "date": row["date"],
            "close": row["close"],
            "signal": row["signal"],
            "cash": cash,
            "shares": shares,
            "portfolio_value": portfolio_value
        })

        # 买入信号
        if row["signal"] == 1 and shares == 0:
            buy_price = row["close"] * (1 + slippage)
            max_shares = int(cash * 0.95 / (buy_price * 100)) * 100  # 整百股
            if max_shares >= 100:
                cost = max_shares * buy_price * (1 + commission)
                cash -= cost
                shares = max_shares
                trades.append({
                    "date": row["date"], 
                    "action": "BUY", 
                    "price": buy_price, 
                    "qty": max_shares,
                    "cost": cost
                })

        # 卖出信号
        elif row["signal"] == -1 and shares > 0:
            sell_price = row["close"] * (1 - slippage)
            revenue = shares * sell_price * (1 - commission)
            cash += revenue
            trades.append({
                "date": row["date"], 
                "action": "SELL", 
                "price": sell_price, 
                "qty": shares,
                "revenue": revenue
            })
            shares = 0

    # 最后一日清仓
    if shares > 0:
        sell_price = data["close"].iloc[-1] * (1 - slippage)
        revenue = shares * sell_price * (1 - commission)
        cash += revenue
        trades.append({
            "date": data["date"].iloc[-1], 
            "action": "SELL", 
            "price": sell_price, 
            "qty": shares,
            "revenue": revenue
        })
        shares = 0

    # === 计算绩效指标 ===
    portfolio = pd.Series(portfolio_values, index=data.index)
    daily_ret = portfolio.pct_change().dropna()

    total_return = (portfolio.iloc[-1] / capital) - 1
    trading_days = len(portfolio)
    annual_return = (1 + total_return) ** (252 / trading_days) - 1 if trading_days > 0 else 0
    max_drawdown = ((portfolio / portfolio.cummax()) - 1).min()
    sharpe = daily_ret.mean() / daily_ret.std() * np.sqrt(252) if daily_ret.std() != 0 else 0
    
    # 年化波动率
    volatility = daily_ret.std() * np.sqrt(252)
    
    # Calmar比率
    calmar = annual_return / abs(max_drawdown) if max_drawdown != 0 else float("inf")

    # 胜率计算
    trade_returns = []
    for i in range(0, len(trades) - 1, 2):
        if i + 1 < len(trades):
            buy_trade = trades[i]
            sell_trade = trades[i + 1]
            if buy_trade["action"] == "BUY" and sell_trade["action"] == "SELL":
                trade_ret = (sell_trade["price"] - buy_trade["price"]) / buy_trade["price"]
                trade_returns.append(trade_ret)

    win_rate = len([r for r in trade_returns if r > 0]) / len(trade_returns) if trade_returns else 0
    avg_win = np.mean([r for r in trade_returns if r > 0]) if any(r > 0 for r in trade_returns) else 0
    avg_loss = np.mean([r for r in trade_returns if r <= 0]) if any(r <= 0 for r in trade_returns) else 0
    profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float("inf")

    # 基准对比
    benchmark_return = (data["close"].iloc[-1] / data["close"].iloc[0]) - 1
    alpha = total_return - benchmark_return
    
    # 计算Beta
    benchmark_daily_ret = data["close"].pct_change().dropna()
    if len(daily_ret) == len(benchmark_daily_ret) and daily_ret.std() != 0:
        beta = np.cov(daily_ret, benchmark_daily_ret)[0][1] / np.var(benchmark_daily_ret)
    else:
        beta = 1.0

    dp.logout()

    result = {
        "标的": stock_code,
        "策略": strategy,
        "数据源": data_source,
        "回测区间": f"{start_date} ~ {end_date}",
        "初始资金": f"¥{capital:,.0f}",
        "最终市值": f"¥{portfolio.iloc[-1]:,.0f}",
        "总收益率": f"{total_return:.2%}",
        "年化收益率": f"{annual_return:.2%}",
        "年化波动率": f"{volatility:.2%}",
        "最大回撤": f"{max_drawdown:.2%}",
        "夏普比率": f"{sharpe:.2f}",
        "Calmar比率": f"{calmar:.2f}",
        "Beta": f"{beta:.2f}",
        "交易次数": len(trades),
        "胜率": f"{win_rate:.2%}",
        "平均盈利": f"{avg_win:.2%}",
        "平均亏损": f"{avg_loss:.2%}",
        "盈亏比": f"{profit_factor:.2f}",
        "基准收益": f"{benchmark_return:.2%}",
        "超额收益Alpha": f"{alpha:.2%}",
        "trades": trades,
        "portfolio": portfolio.tolist(),
        "dates": data["date"].tolist()
    }

    logger.info(f"回测完成 | 年化: {annual_return:.2%} | 夏普: {sharpe:.2f} | 回撤: {max_drawdown:.2%}")
    
    # 绘制图表
    if plot:
        plot_backtest_result(data, portfolio, trades, result)
    
    return result


def plot_backtest_result(data: pd.DataFrame, portfolio: pd.Series, trades: List[Dict], result: Dict):
    """绘制回测结果图表"""
    fig, axes = plt.subplots(3, 1, figsize=(14, 12), gridspec_kw={'height_ratios': [3, 1, 1]})
    
    dates = data["date"]
    
    # 图1: 价格与交易信号
    ax1 = axes[0]
    ax1.plot(dates, data["close"], label="收盘价", color="black", linewidth=1)
    
    # 标记买卖点
    buy_dates = [t["date"] for t in trades if t["action"] == "BUY"]
    buy_prices = [t["price"] for t in trades if t["action"] == "BUY"]
    sell_dates = [t["date"] for t in trades if t["action"] == "SELL"]
    sell_prices = [t["price"] for t in trades if t["action"] == "SELL"]
    
    ax1.scatter(buy_dates, buy_prices, color="red", marker="^", s=100, label="买入", zorder=5)
    ax1.scatter(sell_dates, sell_prices, color="green", marker="v", s=100, label="卖出", zorder=5)
    
    # 添加均线
    if "ma20" in data.columns:
        ax1.plot(dates, data["ma20"], label="MA20", color="orange", alpha=0.7)
    if "ma60" in data.columns:
        ax1.plot(dates, data["ma60"], label="MA60", color="blue", alpha=0.7)
    
    ax1.set_title(f"回测结果 - {result['标的']} | {result['策略']} | 年化收益: {result['年化收益率']}", fontsize=12)
    ax1.set_ylabel("价格")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)
    
    # 图2: 资金曲线
    ax2 = axes[1]
    ax2.fill_between(dates, portfolio, result["初始资金"], 
                     where=(portfolio >= float(result["初始资金"].replace("¥", "").replace(",", ""))), 
                     alpha=0.3, color="red", label="盈利")
    ax2.fill_between(dates, portfolio, result["初始资金"], 
                     where=(portfolio < float(result["初始资金"].replace("¥", "").replace(",", ""))), 
                     alpha=0.3, color="green", label="亏损")
    ax2.plot(dates, portfolio, color="blue", linewidth=1.5, label="资金曲线")
    ax2.axhline(y=float(result["初始资金"].replace("¥", "").replace(",", "")), color="gray", linestyle="--", alpha=0.5)
    ax2.set_ylabel("资金")
    ax2.legend(loc="upper left")
    ax2.grid(True, alpha=0.3)
    
    # 图3: 回撤曲线
    ax3 = axes[2]
    drawdown = (portfolio / portfolio.cummax()) - 1
    ax3.fill_between(dates, drawdown, 0, alpha=0.3, color="red")
    ax3.plot(dates, drawdown, color="red", linewidth=1)
    ax3.set_ylabel("回撤")
    ax3.set_xlabel("日期")
    ax3.set_title(f"最大回撤: {result['最大回撤']}")
    ax3.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("backtest_result.png", dpi=150, bbox_inches="tight")
    logger.info("图表已保存至 backtest_result.png")
    plt.show()


def compare_strategies(stock_code="sh.600036", start_date="2023-01-01", end_date="2025-12-31",
                      capital=100000, data_source="baostock", tushare_token=None):
    """多策略对比回测"""
    strategies = ["ma_cross", "momentum", "mean_revert", "multi_factor"]
    results = []
    
    logger.info(f"开始多策略对比回测 | 标的: {stock_code}")
    
    for strategy in strategies:
        logger.info(f"运行策略: {strategy}")
        result = run_backtest(
            stock_code=stock_code,
            start_date=start_date,
            end_date=end_date,
            capital=capital,
            strategy=strategy,
            data_source=data_source,
            tushare_token=tushare_token,
            plot=False
        )
        if result:
            results.append(result)
    
    # 对比表格
    print("\n" + "="*100)
    print("策略对比结果")
    print("="*100)
    
    metrics = ["策略", "总收益率", "年化收益率", "最大回撤", "夏普比率", "胜率", "交易次数", "超额收益Alpha"]
    print(f"{'指标':<15}", end="")
    for r in results:
        print(f"{r['策略']:<15}", end="")
    print()
    print("-"*100)
    
    for metric in metrics:
        print(f"{metric:<15}", end="")
        for r in results:
            print(f"{r.get(metric, '-'):<15}", end="")
        print()
    
    # 绘制对比图
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    
    # 收益对比
    ax1 = axes[0, 0]
    returns = [float(r["年化收益率"].replace("%", "")) for r in results]
    colors = ["green" if r > 0 else "red" for r in returns]
    ax1.bar([r["策略"] for r in results], returns, color=colors, alpha=0.7)
    ax1.set_title("年化收益率对比")
    ax1.set_ylabel("收益率 (%)")
    ax1.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax1.grid(True, alpha=0.3)
    
    # 夏普比率对比
    ax2 = axes[0, 1]
    sharpes = [float(r["夏普比率"]) for r in results]
    ax2.bar([r["策略"] for r in results], sharpes, color="blue", alpha=0.7)
    ax2.set_title("夏普比率对比")
    ax2.set_ylabel("夏普比率")
    ax2.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
    ax2.grid(True, alpha=0.3)
    
    # 最大回撤对比
    ax3 = axes[1, 0]
    drawdowns = [abs(float(r["最大回撤"].replace("%", ""))) for r in results]
    ax3.bar([r["策略"] for r in results], drawdowns, color="red", alpha=0.7)
    ax3.set_title("最大回撤对比")
    ax3.set_ylabel("回撤 (%)")
    ax3.grid(True, alpha=0.3)
    
    # 胜率对比
    ax4 = axes[1, 1]
    win_rates = [float(r["胜率"].replace("%", "")) for r in results]
    ax4.bar([r["策略"] for r in results], win_rates, color="purple", alpha=0.7)
    ax4.set_title("胜率对比")
    ax4.set_ylabel("胜率 (%)")
    ax4.axhline(y=50, color="gray", linestyle="--", alpha=0.5)
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("strategy_comparison.png", dpi=150, bbox_inches="tight")
    logger.info("对比图表已保存至 strategy_comparison.png")
    plt.show()
    
    return results


def compute_rsi(series, period=14):
    """计算RSI"""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def compute_atr(data, period=14):
    """计算ATR"""
    high_low = data["high"] - data["low"]
    high_close = abs(data["high"] - data["close"].shift())
    low_close = abs(data["low"] - data["close"].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    return tr.rolling(period).mean()


if __name__ == "__main__":
    import sys
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        command = sys.argv[1]
        
        if command == "compare":
            # 多策略对比模式
            compare_strategies()
        elif command == "tushare":
            # 使用 Tushare 数据源
            token = sys.argv[2] if len(sys.argv) > 2 else None
            if token:
                for strategy in ["ma_cross", "multi_factor"]:
                    print(f"\n{'='*50}")
                    result = run_backtest(
                        strategy=strategy,
                        data_source="tushare",
                        tushare_token=token,
                        plot=True
                    )
                    if result:
                        for k, v in result.items():
                            if k not in ["trades", "portfolio", "dates"]:
                                print(f"  {k}: {v}")
            else:
                print("请提供 Tushare Token: python backtest_engine.py tushare <token>")
        else:
            print(f"未知命令: {command}")
            print("用法:")
            print("  python backtest_engine.py              # 单策略回测")
            print("  python backtest_engine.py compare      # 多策略对比")
            print("  python backtest_engine.py tushare <token>  # 使用Tushare数据源")
    else:
        # 默认：单策略回测，对比所有策略
        print("="*60)
        print("Alpha Quant - 策略回测引擎")
        print("="*60)
        
        for strategy in ["ma_cross", "momentum", "mean_revert", "multi_factor"]:
            print(f"\n{'='*50}")
            result = run_backtest(strategy=strategy, plot=False)
            if result:
                for k, v in result.items():
                    if k not in ["trades", "portfolio", "dates"]:
                        print(f"  {k}: {v}")
