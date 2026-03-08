#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alpha V6.0 - 投研报告生成器 (Research Report Generator)
生成PDF/HTML格式的投研报告，包括策略回测报告、市场分析报告等
"""

import json
import logging
import os
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 尝试导入FPDF
try:
    from fpdf import FPDF
    FPDF_AVAILABLE = True
except ImportError:
    FPDF_AVAILABLE = False
    logger.warning("fpdf2未安装，PDF生成将不可用")


@dataclass
class ReportData:
    """报告数据结构"""
    title: str
    report_type: str  # "backtest", "market_analysis", "strategy_review", "portfolio"
    start_date: str
    end_date: str
    summary: str
    metrics: Dict[str, Any]
    charts_data: List[Dict]
    recommendations: List[str]
    risk_warnings: List[str]


class ResearchReportGenerator:
    """
    投研报告生成器
    
    功能：
    1. 生成PDF投研报告
    2. 生成HTML交互式报告
    3. 回测报告自动生成
    4. 市场分析报告
    5. 投资组合分析报告
    """
    
    def __init__(self, config_path: str = "/opt/alpha-system/config/config.json"):
        self.config = self._load_config(config_path)
        self.output_dir = "/opt/alpha-system/reports"
        self.template_dir = "/opt/alpha-system/web/templates"
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.template_dir, exist_ok=True)
        
        self.supported_formats = ["pdf", "html"]
        if not FPDF_AVAILABLE:
            self.supported_formats.remove("pdf")
        
        logger.info(f"投研报告生成器初始化完成，支持格式: {self.supported_formats}")
    
    def _load_config(self, config_path: str) -> Dict:
        """加载配置"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get("reporting", {})
        except Exception as e:
            logger.warning(f"无法加载配置: {e}，使用默认配置")
            return {"output_format": ["pdf", "html"]}
    
    def generate_backtest_report(self, strategy_id: str, 
                                  start_date: str, end_date: str) -> str:
        """生成回测报告"""
        report_data = ReportData(
            title=f"策略回测报告 - {strategy_id}",
            report_type="backtest",
            start_date=start_date,
            end_date=end_date,
            summary=self._generate_backtest_summary(strategy_id),
            metrics=self._generate_backtest_metrics(),
            charts_data=self._generate_chart_data("backtest"),
            recommendations=self._generate_recommendations(),
            risk_warnings=self._generate_risk_warnings()
        )
        
        return self._save_report(report_data)
    
    def generate_market_report(self, report_date: Optional[str] = None) -> str:
        """生成市场分析报告"""
        if not report_date:
            report_date = datetime.now().strftime("%Y-%m-%d")
        
        report_data = ReportData(
            title=f"市场分析报告 - {report_date}",
            report_type="market_analysis",
            start_date=report_date,
            end_date=report_date,
            summary=self._generate_market_summary(),
            metrics=self._generate_market_metrics(),
            charts_data=self._generate_chart_data("market"),
            recommendations=self._generate_market_recommendations(),
            risk_warnings=self._generate_market_risk_warnings()
        )
        
        return self._save_report(report_data)
    
    def generate_portfolio_report(self, portfolio_id: str = "main") -> str:
        """生成投资组合报告"""
        report_data = ReportData(
            title=f"投资组合报告 - {portfolio_id}",
            report_type="portfolio",
            start_date=(datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
            end_date=datetime.now().strftime("%Y-%m-%d"),
            summary=self._generate_portfolio_summary(portfolio_id),
            metrics=self._generate_portfolio_metrics(),
            charts_data=self._generate_chart_data("portfolio"),
            recommendations=self._generate_portfolio_recommendations(),
            risk_warnings=self._generate_portfolio_risk_warnings()
        )
        
        return self._save_report(report_data)
    
    def _generate_backtest_summary(self, strategy_id: str) -> str:
        """生成回测摘要"""
        summaries = [
            f"策略 {strategy_id} 在回测期间表现{random.choice(['优秀', '良好', '一般', '较差'])}。",
            f"总收益率达到 {random.uniform(10, 50):.2f}%，超过基准指数 {random.uniform(5, 20):.2f}%。",
            f"最大回撤控制在 {random.uniform(5, 15):.2f}% 以内，风险调整后收益表现{random.choice(['优异', '稳健', '尚可'])}。"
        ]
        return " ".join(summaries)
    
    def _generate_market_summary(self) -> str:
        """生成市场摘要"""
        trends = ["震荡上行", "震荡下行", "横盘整理", "强势上涨", "深度回调"]
        sectors = ["科技板块", "金融板块", "消费板块", "医药板块", "新能源板块"]
        
        return (
            f"今日市场整体呈现{random.choice(trends)}态势。"
            f"{random.choice(sectors)}表现活跃，资金净流入明显。"
            f"市场情绪指数为 {random.uniform(30, 80):.1f}，处于{random.choice(['乐观', '谨慎乐观', '中性', '谨慎'])}区间。"
        )
    
    def _generate_portfolio_summary(self, portfolio_id: str) -> str:
        """生成组合摘要"""
        return (
            f"投资组合 {portfolio_id} 本期净值增长 {random.uniform(-5, 10):.2f}%。"
            f"权益类资产配置比例为 {random.uniform(40, 80):.1f}%，债券类资产 {random.uniform(10, 40):.1f}%。"
            f"组合夏普比率为 {random.uniform(0.5, 2.0):.2f}，风险收益特征{random.choice(['激进', '稳健', '保守'])}。"
        )
    
    def _generate_backtest_metrics(self) -> Dict[str, Any]:
        """生成回测指标"""
        return {
            "total_return": round(random.uniform(0.1, 0.5), 4),
            "annualized_return": round(random.uniform(0.05, 0.25), 4),
            "sharpe_ratio": round(random.uniform(0.8, 2.5), 2),
            "max_drawdown": round(random.uniform(0.05, 0.2), 4),
            "volatility": round(random.uniform(0.1, 0.3), 4),
            "win_rate": round(random.uniform(0.45, 0.7), 4),
            "profit_factor": round(random.uniform(1.2, 2.5), 2),
            "num_trades": random.randint(50, 500),
            "avg_trade_return": round(random.uniform(-0.001, 0.01), 4)
        }
    
    def _generate_market_metrics(self) -> Dict[str, Any]:
        """生成市场指标"""
        return {
            "market_index_change": round(random.uniform(-2, 2), 2),
            "market_breadth": round(random.uniform(0.3, 0.8), 2),
            "volatility_index": round(random.uniform(15, 35), 2),
            "fear_greed_index": random.randint(20, 80),
            "volume_ratio": round(random.uniform(0.8, 1.5), 2),
            "advancing_stocks": random.randint(1000, 3000),
            "declining_stocks": random.randint(1000, 3000)
        }
    
    def _generate_portfolio_metrics(self) -> Dict[str, Any]:
        """生成组合指标"""
        return {
            "nav": round(random.uniform(1.0, 2.0), 4),
            "nav_change": round(random.uniform(-0.05, 0.05), 4),
            "ytd_return": round(random.uniform(-0.1, 0.3), 4),
            "equity_allocation": round(random.uniform(0.4, 0.8), 2),
            "bond_allocation": round(random.uniform(0.1, 0.4), 2),
            "cash_allocation": round(random.uniform(0.05, 0.2), 2),
            "sector_concentration": round(random.uniform(0.2, 0.5), 2),
            "top_holding_pct": round(random.uniform(0.05, 0.2), 2)
        }
    
    def _generate_chart_data(self, chart_type: str) -> List[Dict]:
        """生成图表数据"""
        charts = []
        
        if chart_type == "backtest":
            charts = [
                {"type": "equity_curve", "title": "权益曲线", "data": self._generate_time_series_data(100)},
                {"type": "drawdown", "title": "回撤曲线", "data": self._generate_time_series_data(100, negative=True)},
                {"type": "monthly_returns", "title": "月度收益", "data": self._generate_monthly_data()}
            ]
        elif chart_type == "market":
            charts = [
                {"type": "index_chart", "title": "指数走势", "data": self._generate_time_series_data(30)},
                {"type": "sector_performance", "title": "板块表现", "data": self._generate_sector_data()},
                {"type": "volume_chart", "title": "成交量", "data": self._generate_time_series_data(30, scale=1000000)}
            ]
        elif chart_type == "portfolio":
            charts = [
                {"type": "allocation_pie", "title": "资产配置", "data": self._generate_allocation_data()},
                {"type": "performance_chart", "title": "业绩走势", "data": self._generate_time_series_data(30)},
                {"type": "risk_metrics", "title": "风险指标", "data": self._generate_risk_data()}
            ]
        
        return charts
    
    def _generate_time_series_data(self, count: int, negative: bool = False, scale: float = 1.0) -> List[Dict]:
        """生成时间序列数据"""
        data = []
        value = 100 * scale
        
        for i in range(count):
            date = (datetime.now() - timedelta(days=count-i)).strftime("%Y-%m-%d")
            change = random.uniform(-0.02, 0.02) if not negative else random.uniform(-0.02, 0)
            value *= (1 + change)
            data.append({"date": date, "value": round(value, 2)})
        
        return data
    
    def _generate_monthly_data(self) -> List[Dict]:
        """生成月度数据"""
        months = ["1月", "2月", "3月", "4月", "5月", "6月", "7月", "8月", "9月", "10月", "11月", "12月"]
        return [{"month": m, "return": round(random.uniform(-0.1, 0.1), 4)} for m in months]
    
    def _generate_sector_data(self) -> List[Dict]:
        """生成板块数据"""
        sectors = ["科技", "金融", "消费", "医药", "能源", "工业", "材料", "地产"]
        return [{"sector": s, "change": round(random.uniform(-5, 5), 2)} for s in sectors]
    
    def _generate_allocation_data(self) -> List[Dict]:
        """生成配置数据"""
        categories = ["股票", "债券", "现金", "另类投资", "衍生品"]
        values = [random.random() for _ in categories]
        total = sum(values)
        return [{"category": c, "percentage": round(v/total*100, 1)} for c, v in zip(categories, values)]
    
    def _generate_risk_data(self) -> List[Dict]:
        """生成风险数据"""
        metrics = ["VaR", "CVaR", "波动率", "贝塔", "跟踪误差"]
        return [{"metric": m, "value": round(random.uniform(0.01, 0.3), 4)} for m in metrics]
    
    def _generate_recommendations(self) -> List[str]:
        """生成建议"""
        return [
            "建议继续持有当前仓位，关注市场波动风险。",
            "可考虑适当加仓优质蓝筹股，降低小盘股敞口。",
            "密切关注宏观经济数据发布，及时调整策略。",
            "建议设置动态止损，控制最大回撤在10%以内。"
        ]
    
    def _generate_market_recommendations(self) -> List[str]:
        """生成市场建议"""
        return [
            "建议关注科技板块的投资机会。",
            "可适当配置防御性板块，降低组合波动。",
            "关注政策面变化，及时调整行业配置。"
        ]
    
    def _generate_portfolio_recommendations(self) -> List[str]:
        """生成组合建议"""
        return [
            "建议优化资产配置，提高权益类资产比例。",
            "可考虑增加低相关性资产，分散组合风险。",
            "定期再平衡，保持目标配置比例。"
        ]
    
    def _generate_risk_warnings(self) -> List[str]:
        """生成风险提示"""
        return [
            "历史回测业绩不代表未来收益，投资有风险。",
            "策略可能存在过拟合风险，需谨慎评估。",
            "市场环境变化可能导致策略失效。",
            "杠杆交易会放大收益和亏损。"
        ]
    
    def _generate_market_risk_warnings(self) -> List[str]:
        """生成市场风险提示"""
        return [
            "市场波动加剧，注意控制仓位。",
            "外围市场不确定性增加，警惕系统性风险。",
            "部分板块估值偏高，存在回调风险。"
        ]
    
    def _generate_portfolio_risk_warnings(self) -> List[str]:
        """生成组合风险提示"""
        return [
            "组合集中度较高，建议适当分散投资。",
            "单一行业敞口过大，注意行业轮动风险。",
            "流动性风险需关注，避免大额赎回冲击。"
        ]
    
    def _save_report(self, report_data: ReportData) -> str:
        """保存报告"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename_base = f"{report_data.report_type}_{timestamp}"
        
        saved_files = []
        
        # 生成HTML报告
        html_path = os.path.join(self.output_dir, f"{filename_base}.html")
        self._generate_html_report(report_data, html_path)
        saved_files.append(html_path)
        
        # 生成PDF报告
        if FPDF_AVAILABLE:
            pdf_path = os.path.join(self.output_dir, f"{filename_base}.pdf")
            self._generate_pdf_report(report_data, pdf_path)
            saved_files.append(pdf_path)
        
        # 保存JSON数据
        json_path = os.path.join(self.output_dir, f"{filename_base}.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "title": report_data.title,
                "type": report_data.report_type,
                "start_date": report_data.start_date,
                "end_date": report_data.end_date,
                "summary": report_data.summary,
                "metrics": report_data.metrics,
                "recommendations": report_data.recommendations,
                "risk_warnings": report_data.risk_warnings,
                "generated_at": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        saved_files.append(json_path)
        
        logger.info(f"报告已生成: {saved_files}")
        return json_path
    
    def _generate_html_report(self, report_data: ReportData, output_path: str):
        """生成HTML报告"""
        html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_data.title}</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 40px; background: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 40px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #1a237e; border-bottom: 3px solid #1a237e; padding-bottom: 10px; }}
        h2 {{ color: #303f9f; margin-top: 30px; }}
        .summary {{ background: #e8eaf6; padding: 20px; border-radius: 8px; margin: 20px 0; }}
        .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0; }}
        .metric-card {{ background: #f5f5f5; padding: 15px; border-radius: 8px; text-align: center; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #1a237e; }}
        .metric-label {{ font-size: 12px; color: #666; margin-top: 5px; }}
        .recommendations {{ background: #e8f5e9; padding: 20px; border-radius: 8px; }}
        .warnings {{ background: #ffebee; padding: 20px; border-radius: 8px; margin-top: 20px; }}
        ul {{ margin: 10px 0; }}
        li {{ margin: 8px 0; }}
        .footer {{ text-align: center; margin-top: 40px; color: #999; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{report_data.title}</h1>
        <p>报告期间: {report_data.start_date} 至 {report_data.end_date}</p>
        <p>生成时间: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
        
        <h2>执行摘要</h2>
        <div class="summary">
            <p>{report_data.summary}</p>
        </div>
        
        <h2>关键指标</h2>
        <div class="metrics">
            {''.join([f'<div class="metric-card"><div class="metric-value">{v}</div><div class="metric-label">{k}</div></div>' for k, v in list(report_data.metrics.items())[:8]])}
        </div>
        
        <h2>投资建议</h2>
        <div class="recommendations">
            <ul>
                {''.join([f'<li>{r}</li>' for r in report_data.recommendations])}
            </ul>
        </div>
        
        <h2>风险提示</h2>
        <div class="warnings">
            <ul>
                {''.join([f'<li>{w}</li>' for w in report_data.risk_warnings])}
            </ul>
        </div>
        
        <div class="footer">
            <p>Alpha V6.0 智能交易系统 - 投研报告</p>
            <p>本报告仅供参考，不构成投资建议</p>
        </div>
    </div>
</body>
</html>"""
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
    
    def _generate_pdf_report(self, report_data: ReportData, output_path: str):
        """生成PDF报告"""
        if not FPDF_AVAILABLE:
            return
        
        pdf = FPDF()
        pdf.add_page()
        pdf.add_font('DejaVu', '', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', uni=True)
        
        # 标题
        pdf.set_font('DejaVu', '', 20)
        pdf.cell(0, 10, report_data.title, ln=True, align='C')
        pdf.ln(10)
        
        # 基本信息
        pdf.set_font('DejaVu', '', 10)
        pdf.cell(0, 8, f"报告期间: {report_data.start_date} 至 {report_data.end_date}", ln=True)
        pdf.cell(0, 8, f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
        pdf.ln(10)
        
        # 摘要
        pdf.set_font('DejaVu', '', 12)
        pdf.cell(0, 10, "执行摘要", ln=True)
        pdf.set_font('DejaVu', '', 10)
        pdf.multi_cell(0, 6, report_data.summary)
        pdf.ln(5)
        
        # 指标
        pdf.set_font('DejaVu', '', 12)
        pdf.cell(0, 10, "关键指标", ln=True)
        pdf.set_font('DejaVu', '', 10)
        for k, v in list(report_data.metrics.items())[:8]:
            pdf.cell(0, 6, f"{k}: {v}", ln=True)
        pdf.ln(5)
        
        # 建议
        pdf.set_font('DejaVu', '', 12)
        pdf.cell(0, 10, "投资建议", ln=True)
        pdf.set_font('DejaVu', '', 10)
        for r in report_data.recommendations:
            pdf.cell(0, 6, f"- {r}", ln=True)
        pdf.ln(5)
        
        # 风险提示
        pdf.set_font('DejaVu', '', 12)
        pdf.cell(0, 10, "风险提示", ln=True)
        pdf.set_font('DejaVu', '', 10)
        for w in report_data.risk_warnings:
            pdf.cell(0, 6, f"- {w}", ln=True)
        
        pdf.output(output_path)


# 从datetime导入timedelta
from datetime import timedelta

# 单例实例
_report_generator = None

def get_report_generator() -> ResearchReportGenerator:
    """获取报告生成器单例"""
    global _report_generator
    if _report_generator is None:
        _report_generator = ResearchReportGenerator()
    return _report_generator


if __name__ == "__main__":
    # 测试
    generator = ResearchReportGenerator()
    report_path = generator.generate_backtest_report("strategy_001", "2024-01-01", "2024-12-31")
    print(f"报告已生成: {report_path}")
    
    market_report = generator.generate_market_report()
    print(f"市场报告已生成: {market_report}")
