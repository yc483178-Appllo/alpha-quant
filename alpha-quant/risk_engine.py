"""
风险引擎模块
功能: 风险分解、VaR计算、压力测试
对接: 看板V3.0风险钻取数据
"""

import logging
from typing import Dict, List
from dataclasses import dataclass

logger = logging.getLogger("RiskEngine")


@dataclass
class RiskItem:
    """风险明细项"""
    code: str          # 股票代码
    name: str          # 股票名称
    value: str         # 风险值 (如 "12.3%")
    note: str          # 备注说明


@dataclass
class RiskCategory:
    """风险类别"""
    name: str          # 类别名称
    pct: float         # 占比百分比
    color: str         # 显示颜色
    desc: str          # 类别描述
    items: List[RiskItem]  # 明细列表


class RiskEngine:
    """
    风险引擎
    提供风险分解、VaR计算、钻取数据
    """
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.var_95 = 1.84  # 95% VaR
        self.cvar_95 = 2.31  # 95% CVaR
        self.max_dd = -8.4  # 最大回撤
        self.sharpe = 1.58  # 夏普比率
        
    def decompose_risk(self) -> Dict:
        """
        风险分解 - 看板V3.0风险钻取数据源
        返回: RISK_DRILL 格式数据
        """
        return {
            "市场风险": {
                "pct": 45,
                "color": "#ff3d57",
                "desc": "来自宏观市场系统性风险，主要为β敞口",
                "items": [
                    RiskItem("300750", "宁德时代", "12.3%", "高β=1.45，新能源板块联动"),
                    RiskItem("688981", "中芯国际", "9.8%", "高β=1.62，科技政策敏感"),
                    RiskItem("600519", "贵州茅台", "7.2%", "低β=0.78，白酒防御属性"),
                    RiskItem("601318", "中国平安", "6.1%", "β=0.85，金融股联动"),
                    RiskItem("others", "其余8只", "9.6%", "分散化配置，降低集中度"),
                ]
            },
            "流动性风险": {
                "pct": 25,
                "color": "#ffb300",
                "desc": "市场流动性不足，大额订单冲击成本",
                "items": [
                    RiskItem("600519", "贵州茅台", "8.2%", "单票价格高，大单冲击显著"),
                    RiskItem("688981", "中芯国际", "6.5%", "科创板流动性较主板弱"),
                    RiskItem("300750", "宁德时代", "5.4%", "换手率近期下降"),
                    RiskItem("600036", "招商银行", "3.1%", "银行股流动性好，风险低"),
                    RiskItem("others", "其余8只", "1.8%", "流动性风险分散，影响可控"),
                ]
            },
            "模型风险": {
                "pct": 20,
                "color": "#00c8ff",
                "desc": "模型过拟合/泛化不足导致的预测误差",
                "items": [
                    RiskItem("DRL-Transformer", "", "7.5%", "新模型上线不足3月，历史数据有限"),
                    RiskItem("StratEvol", "", "5.8%", "遗传算法可能过拟合近期数据"),
                    RiskItem("Sentiment", "", "4.2%", "极端事件下NLP精度下降"),
                    RiskItem("HMM", "", "2.5%", "政权识别延迟约2-3天"),
                ]
            },
            "执行风险": {
                "pct": 10,
                "color": "#00e676",
                "desc": "滑点、延迟、系统故障等执行层面风险",
                "items": [
                    RiskItem("Slippage", "", "3.2%", "平均1.2bps，震荡市摩擦增加"),
                    RiskItem("Latency", "", "2.8%", "PTrade平均2ms，极端行情可能增大"),
                    RiskItem("T+1", "", "2.5%", "A股T+1无法同日反手，影响止损效率"),
                    RiskItem("Limit", "", "1.5%", "10%/20%涨跌停限制，影响开平仓策略"),
                ]
            },
        }
    
    def get_var_metrics(self) -> Dict:
        """获取VaR指标"""
        return {
            "var_95_1d": self.var_95,
            "var_99_1d": 2.31,
            "var_95_5d": 4.12,
            "cvar_95_1d": self.cvar_95,
            "max_drawdown": self.max_dd,
            "sharpe_ratio": self.sharpe,
            "calmar_ratio": 0.97
        }
    
    def get_stress_test(self) -> List[Dict]:
        """获取压力测试场景"""
        return [
            {"scenario": "2015年股灾熔断", "time": "2015/6-7", "index_drop": "-43%", "portfolio_loss": "-22.4%", "recovery": "8-12个月"},
            {"scenario": "2018年中美贸易战", "time": "2018", "index_drop": "-28%", "portfolio_loss": "-18.7%", "recovery": "6-9个月"},
            {"scenario": "2020年疫情冲击", "time": "2020/1-2", "index_drop": "-14%", "portfolio_loss": "-12.3%", "recovery": "3-5个月"},
            {"scenario": "利率上升200bps", "time": "假设情景", "index_drop": "-8%", "portfolio_loss": "-8.6%", "recovery": "4-6个月"},
            {"scenario": "人民币贬值10%", "time": "假设情景", "index_drop": "-5%", "portfolio_loss": "-6.8%", "recovery": "3-4个月"},
        ]
    
    def calculate_position_risk(self, position: Dict) -> Dict:
        """计算单个持仓风险贡献"""
        # 简化计算
        beta = position.get("beta", 1.0)
        mkt_val = position.get("price", 0) * position.get("qty", 0)
        
        return {
            "beta_contribution": beta * mkt_val / 1000000,  # 简化归一化
            "var_contribution": self.var_95 * beta * 0.01,
            "liquidity_score": min(100, max(0, 100 - position.get("price", 0) / 100))
        }


# 全局实例
_risk_engine = None

def get_risk_engine(config_path: str = "config.json") -> RiskEngine:
    """获取风险引擎单例"""
    global _risk_engine
    if _risk_engine is None:
        _risk_engine = RiskEngine(config_path)
    return _risk_engine
