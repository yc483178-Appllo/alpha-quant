"""
投研报告生成器 - V6.0 新增模块
文件: research_report_generator.py
功能: 生成专业级投资研究报告（技术面+基本面+舆情+风险四维）
依赖: fpdf2, ta-lib(可选), pandas, numpy
输出: PDF + HTML双格式
"""

import os
import json
import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional

logger = logging.getLogger("ResearchReport")


class TechnicalAnalyzer:
    """技术指标计算与信号解读"""
    def analyze(self, df: pd.DataFrame) -> Dict:
        """
        分析个股技术面
        df: DataFrame(date, open, high, low, close, volume)
        返回: 技术面综合分析结果
        """
        if len(df) < 30:
            return {"error": "数据不足"}
        close = df["close"]
        result = {}
        # 均线系统
        result["ma"] = {
            "ma5": float(close.rolling(5).mean().iloc[-1]),
            "ma10": float(close.rolling(10).mean().iloc[-1]),
            "ma20": float(close.rolling(20).mean().iloc[-1]),
            "ma60": float(close.rolling(60).mean().iloc[-1]) if len(df) >= 60 else None,
            "ma120": float(close.rolling(120).mean().iloc[-1]) if len(df) >= 120 else None,
        }
        # MACD
        ema12 = close.ewm(span=12).mean()
        ema26 = close.ewm(span=26).mean()
        dif = ema12 - ema26
        dea = dif.ewm(span=9).mean()
        macd_bar = (dif - dea) * 2
        result["macd"] = {
            "dif": float(dif.iloc[-1]),
            "dea": float(dea.iloc[-1]),
            "bar": float(macd_bar.iloc[-1]),
            "trend": "金叉" if dif.iloc[-1] > dea.iloc[-1] else "死叉",
            "bar_trend": "红柱扩大" if macd_bar.iloc[-1] > macd_bar.iloc[-2] > 0 else
                        "红柱缩小" if macd_bar.iloc[-1] > 0 > macd_bar.iloc[-2] else
                        "绿柱缩小" if macd_bar.iloc[-1] < macd_bar.iloc[-2] < 0 else "绿柱扩大"
        }
        # RSI
        delta = close.diff()
        gain = delta.clip(lower=0).rolling(14).mean()
        loss = (-delta.clip(upper=0)).rolling(14).mean()
        rs = gain / (loss + 1e-10)
        rsi = 100 - 100 / (1 + rs)
        result["rsi"] = {
            "rsi14": float(rsi.iloc[-1]),
            "status": "超买（>70）" if rsi.iloc[-1] > 70 else
                     "超卖（<30）" if rsi.iloc[-1] < 30 else "中性"
        }
        # 布林带
        bb_mean = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        upper = bb_mean + 2 * bb_std
        lower = bb_mean - 2 * bb_std
        current = close.iloc[-1]
        result["bollinger"] = {
            "upper": float(upper.iloc[-1]),
            "middle": float(bb_mean.iloc[-1]),
            "lower": float(lower.iloc[-1]),
            "current_price": current,
            "bandwidth": float((upper.iloc[-1] - lower.iloc[-1]) / bb_mean.iloc[-1]),
            "position": "上轨附近" if current > upper.iloc[-1] * 0.98 else
                       "下轨附近" if current < lower.iloc[-1] * 1.02 else "中轨附近"
        }
        # 成交量分析
        vol = df["volume"]
        result["volume"] = {
            "vol_ratio": float(vol.iloc[-1] / vol.rolling(20).mean().iloc[-1]),
            "vol_trend": "放量" if vol.iloc[-1] > vol.rolling(5).mean().iloc[-1] * 1.5 else
                        "缩量" if vol.iloc[-1] < vol.rolling(5).mean().iloc[-1] * 0.5 else "平量"
        }
        # 支撑压力位
        recent_high = float(df["high"].rolling(20).max().iloc[-1])
        recent_low = float(df["low"].rolling(20).min().iloc[-1])
        result["support_resistance"] = {
            "resistance": recent_high,
            "support": recent_low,
            "current_position_pct": float((current - recent_low) / (recent_high - recent_low + 1e-6))
        }
        # 综合评分（0-100）
        score = 50
        if rsi.iloc[-1] < 30: score += 15
        if rsi.iloc[-1] > 70: score -= 15
        if dif.iloc[-1] > dea.iloc[-1]: score += 10
        if macd_bar.iloc[-1] > 0: score += 5
        if current > result["ma"]["ma20"]: score += 10
        if result["volume"]["vol_ratio"] > 1.5: score += 10
        result["technical_score"] = max(0, min(100, score))
        return result


class FundamentalAnalyzer:
    """基本面指标分析（结合聚宽数据）"""
    def analyze(self, stock_code: str, fundamentals: Dict) -> Dict:
        """
        分析个股基本面
        fundamentals: 从JoinQuantDataGateway获取的基本面数据
        """
        if not fundamentals:
            return {"error": "无基本面数据", "fundamental_score": 50}
        result = {}
        pe = fundamentals.get("pe_ratio", 0)
        pb = fundamentals.get("pb_ratio", 0)
        roe = fundamentals.get("roe", 0)
        gross_margin = fundamentals.get("gross_profit_margin", 0)
        dividend_yield = fundamentals.get("dividend_ratio", 0)
        market_cap = fundamentals.get("market_cap", 0)
        # 估值分析
        result["valuation"] = {
            "pe_ratio": pe,
            "pe_status": "低估（<15）" if 0 < pe < 15 else "合理（15-30）" if 15 <= pe <= 30 else "高估（>30）" if pe > 30 else "亏损",
            "pb_ratio": pb,
            "pb_status": "破净（<1）" if pb < 1 else "低估（1-2）" if pb <= 2 else "合理（2-5）" if pb <= 5 else "高估（>5）",
            "dividend_yield": dividend_yield,
            "market_cap_bn": round(market_cap / 1e8, 2) if market_cap else 0
        }
        # 盈利能力
        result["profitability"] = {
            "roe": roe,
            "roe_status": "优秀（>20%）" if roe > 20 else "良好（10-20%）" if roe > 10 else "较差（<10%）",
            "gross_margin": gross_margin,
        }
        # 综合评分
        score = 50
        if 0 < pe < 20: score += 15
        elif pe > 50: score -= 15
        if pb < 3: score += 10
        if roe > 15: score += 15
        if gross_margin > 30: score += 10
        if dividend_yield > 3: score += 10
        result["fundamental_score"] = max(0, min(100, score))
        return result


class ResearchReportGenerator:
    """
    投研报告生成器主类
    支持: 个股深度/晨报/收盘报告/风险预警报告
    输出: HTML字符串 + PDF文件
    """
    def __init__(self, config_path: str = "config.json"):
        with open(config_path) as f:
            cfg = json.load(f)
        self.cfg = cfg.get("research_report", {})
        self.tech_analyzer = TechnicalAnalyzer()
        self.fund_analyzer = FundamentalAnalyzer()
        self.output_dir = self.cfg.get("output_dir", "./reports")
        os.makedirs(self.output_dir, exist_ok=True)

    def generate_stock_report(
        self,
        stock_code: str,
        stock_name: str,
        price_data: pd.DataFrame,
        fundamentals: Dict = None,
        sentiment_data: Dict = None,
        risk_data: Dict = None
    ) -> Dict:
        """
        生成个股深度报告
        返回: {"html": ..., "pdf_path": ..., "summary": ...}
        """
        logger.info(f"生成个股报告: {stock_code} {stock_name}")
        # 四维分析
        tech = self.tech_analyzer.analyze(price_data)
        fund = self.fund_analyzer.analyze(stock_code, fundamentals or {})
        sent_score = (sentiment_data or {}).get("sentiment_score", 0)
        risk_level = (risk_data or {}).get("risk_level", "中")
        # 综合评分与建议
        overall_score = (
            tech.get("technical_score", 50) * 0.35 +
            fund.get("fundamental_score", 50) * 0.35 +
            (sent_score + 1) * 50 * 0.20 +  # 情绪分 -1~1 → 0~100
            ({"低": 80, "中": 50, "高": 20}.get(risk_level, 50)) * 0.10
        )
        recommendation = (
            "强烈买入 ★★★★★" if overall_score >= 80 else
            "建议买入 ★★★★" if overall_score >= 65 else
            "中性观望 ★★★" if overall_score >= 50 else
            "建议减持 ★★" if overall_score >= 35 else
            "建议卖出 ★"
        )
        current_price = float(price_data["close"].iloc[-1])
        report_date = datetime.now().strftime("%Y年%m月%d日")
        # 生成HTML
        html = self._render_stock_report_html(
            stock_code=stock_code,
            stock_name=stock_name,
            current_price=current_price,
            report_date=report_date,
            tech=tech,
            fund=fund,
            sentiment_score=sent_score,
            risk_level=risk_level,
            overall_score=overall_score,
            recommendation=recommendation
        )
        # 保存HTML文件
        html_path = os.path.join(self.output_dir, f"{stock_code}_{datetime.now().strftime('%Y%m%d')}.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)
        # 尝试生成PDF（需要fpdf2）
        pdf_path = None
        try:
            pdf_path = self._export_pdf(html, stock_code)
        except Exception as e:
            logger.warning(f"PDF生成失败（不影响HTML报告）: {e}")
        return {
            "html": html,
            "html_path": html_path,
            "pdf_path": pdf_path,
            "overall_score": overall_score,
            "recommendation": recommendation,
            "technical_score": tech.get("technical_score", 50),
            "fundamental_score": fund.get("fundamental_score", 50),
            "sentiment_score": sent_score,
            "risk_level": risk_level,
            "generated_at": datetime.now().isoformat()
        }

    def generate_morning_report(self, market_data: Dict, positions: List[Dict], signals: List[Dict]) -> Dict:
        """生成每日晨报"""
        report_date = datetime.now().strftime("%Y年%m月%d日")
        html = f"""
<!DOCTYPE html><html lang="zh-CN">
<head><meta charset="UTF-8"><title>Alpha量化晨报 {report_date}</title>
<style>
body{{font-family:"Microsoft YaHei",Arial,sans-serif;margin:20px;background:#0d1117;color:#e0e0e0;}}
h1{{color:#00d4ff;border-bottom:2px solid #00d4ff;padding-bottom:8px;}}
h2{{color:#7fba00;margin-top:20px;}}
.card{{background:#1a1f2e;border:1px solid #2a3550;border-radius:8px;padding:15px;margin:10px 0;}}
.green{{color:#00c851;}} .red{{color:#ff4444;}} .yellow{{color:#ffbb33;}}
table{{width:100%;border-collapse:collapse;}}
th{{background:#1e3a5f;padding:8px;text-align:left;}}
td{{padding:7px;border-bottom:1px solid #2a3550;}}
</style></head><body>
<h1>📊 Alpha量化晨报 {report_date}</h1>
<div class="card">
<h2>🌅 市场概述</h2>
<p>上证指数: <span class="{'green' if market_data.get('sh_change',0)>0 else 'red'}">{market_data.get('sh_index','--')} ({market_data.get('sh_change',0):+.2f}%)</span></p>
<p>深证成指: <span class="{'green' if market_data.get('sz_change',0)>0 else 'red'}">{market_data.get('sz_index','--')} ({market_data.get('sz_change',0):+.2f}%)</span></p>
<p>市场情绪: <span class="yellow">{market_data.get('sentiment','中性')}</span></p>
</div>
<div class="card">
<h2>📋 今日关注信号</h2>
<table><tr><th>股票</th><th>信号</th><th>来源</th><th>置信度</th></tr>
{''.join(f"<tr><td>{s.get('code','')}</td><td class='{'green' if s.get('action')=='BUY' else 'red'}'>{s.get('action','')}</td><td>{s.get('source','')}</td><td>{s.get('confidence',0):.0%}</td></tr>" for s in signals[:10])}
</table>
</div>
<div class="card">
<h2>💼 当前持仓</h2>
<table><tr><th>股票</th><th>持仓比例</th><th>浮动盈亏</th></tr>
{''.join(f"<tr><td>{p.get('code','')}</td><td>{p.get('weight',0):.1%}</td><td class='{'green' if p.get('pnl',0)>0 else 'red'}'>{p.get('pnl',0):+.2f}%</td></tr>" for p in positions[:15])}
</table>
</div>
<div class="card">
<h2>⚠️ 风险提示</h2>
<p>{market_data.get('risk_warning','今日市场无特别风险提示，正常操作。')}</p>
</div>
<p style="color:#666;font-size:12px;margin-top:20px;">本报告由 Alpha-Genesis V6.0 自动生成 · 仅供参考，不构成投资建议</p>
</body></html>"""
        path = os.path.join(self.output_dir, f"morning_report_{datetime.now().strftime('%Y%m%d')}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        return {"html": html, "html_path": path, "type": "morning_report"}

    def _render_stock_report_html(self, **kwargs) -> str:
        """渲染个股深度报告HTML"""
        sc = kwargs["overall_score"]
        color = "#00c851" if sc >= 65 else "#ffbb33" if sc >= 50 else "#ff4444"
        tech = kwargs["tech"]
        fund = kwargs["fund"]
        return f"""<!DOCTYPE html><html lang="zh-CN">
<head><meta charset="UTF-8"><title>{kwargs['stock_name']} 深度研究报告</title>
<style>
body{{font-family:"Microsoft YaHei",Arial,sans-serif;margin:0;background:#0d1117;color:#e0e0e0;}}
.header{{background:linear-gradient(135deg,#1a1f2e,#0a2a4a);padding:30px;}}
.header h1{{color:#00d4ff;margin:0 0 5px;font-size:24px;}}
.header .subtitle{{color:#aaa;font-size:14px;}}
.score-circle{{display:inline-block;width:80px;height:80px;border-radius:50%;border:4px solid {color};text-align:center;line-height:80px;font-size:28px;font-weight:bold;color:{color};float:right;margin-top:-20px;}}
.section{{padding:20px 30px;border-bottom:1px solid #1a2a3a;}}
.section h2{{color:#7fba00;margin:0 0 15px;font-size:16px;}}
.metric-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;}}
.metric{{background:#1a1f2e;border:1px solid #2a3550;border-radius:6px;padding:12px;}}
.metric .label{{color:#888;font-size:12px;}}
.metric .value{{color:#e0e0e0;font-size:18px;font-weight:bold;margin-top:4px;}}
.metric .status{{font-size:11px;margin-top:3px;}}
.recommendation{{background:linear-gradient(135deg,{color}22,{color}11);border:2px solid {color};border-radius:8px;padding:20px;text-align:center;}}
.recommendation .rec-text{{color:{color};font-size:20px;font-weight:bold;}}
.footer{{padding:15px 30px;color:#555;font-size:12px;}}
</style></head><body>
<div class="header">
  <div class="score-circle">{sc:.0f}</div>
  <h1>{kwargs['stock_name']} ({kwargs['stock_code']})</h1>
  <div class="subtitle">深度研究报告 · {kwargs['report_date']} · 当前价: ¥{kwargs['current_price']:.2f}</div>
</div>
<div class="section">
  <h2>📈 技术面分析（评分: {tech.get('technical_score',50):.0f}/100）</h2>
  <div class="metric-grid">
    <div class="metric"><div class="label">MACD信号</div><div class="value" style="color:{'#00c851' if tech.get('macd',{}).get('trend')=='金叉' else '#ff4444'}">{tech.get('macd',{}).get('trend','--')}</div></div>
    <div class="metric"><div class="label">RSI(14)</div><div class="value">{tech.get('rsi',{}).get('rsi14',0):.1f}</div><div class="status">{tech.get('rsi',{}).get('status','--')}</div></div>
    <div class="metric"><div class="label">布林带位置</div><div class="value" style="font-size:14px">{tech.get('bollinger',{}).get('position','--')}</div></div>
    <div class="metric"><div class="label">量比</div><div class="value">{tech.get('volume',{}).get('vol_ratio',1):.2f}x</div><div class="status">{tech.get('volume',{}).get('vol_trend','--')}</div></div>
    <div class="metric"><div class="label">MA20</div><div class="value">¥{tech.get('ma',{}).get('ma20',0):.2f}</div></div>
    <div class="metric"><div class="label">阻力位</div><div class="value">¥{tech.get('support_resistance',{}).get('resistance',0):.2f}</div></div>
  </div>
</div>
<div class="section">
  <h2>📊 基本面分析（评分: {fund.get('fundamental_score',50):.0f}/100）</h2>
  <div class="metric-grid">
    <div class="metric"><div class="label">市盈率(PE)</div><div class="value">{fund.get('valuation',{}).get('pe_ratio',0):.1f}x</div><div class="status">{fund.get('valuation',{}).get('pe_status','--')}</div></div>
    <div class="metric"><div class="label">市净率(PB)</div><div class="value">{fund.get('valuation',{}).get('pb_ratio',0):.2f}x</div><div class="status">{fund.get('valuation',{}).get('pb_status','--')}</div></div>
    <div class="metric"><div class="label">ROE</div><div class="value">{fund.get('profitability',{}).get('roe',0):.1f}%</div><div class="status">{fund.get('profitability',{}).get('roe_status','--')}</div></div>
    <div class="metric"><div class="label">毛利率</div><div class="value">{fund.get('profitability',{}).get('gross_margin',0):.1f}%</div></div>
    <div class="metric"><div class="label">股息率</div><div class="value">{fund.get('valuation',{}).get('dividend_yield',0):.1f}%</div></div>
    <div class="metric"><div class="label">市值</div><div class="value">{fund.get('valuation',{}).get('market_cap_bn',0):.0f}亿</div></div>
  </div>
</div>
<div class="section">
  <h2>📰 舆情面分析</h2>
  <p>情绪评分: <strong style="color:{'#00c851' if kwargs['sentiment_score']>0 else '#ff4444' if kwargs['sentiment_score']<0 else '#ffbb33'}">{kwargs['sentiment_score']:+.2f}</strong>（-1极度悲观 ~ +1极度乐观）</p>
</div>
<div class="section">
  <h2>⚠️ 风险评估</h2>
  <p>综合风险等级: <strong style="color:{'#00c851' if kwargs['risk_level']=='低' else '#ffbb33' if kwargs['risk_level']=='中' else '#ff4444'}">{kwargs['risk_level']}风险</strong></p>
</div>
<div class="section">
  <div class="recommendation">
    <div style="color:#aaa;font-size:13px;margin-bottom:8px">综合评分: {sc:.1f}/100</div>
    <div class="rec-text">{kwargs['recommendation']}</div>
  </div>
</div>
<div class="footer">本报告由 Alpha-Genesis V6.0 自动生成 · 仅供参考，不构成投资建议 · 投资有风险，入市需谨慎</div>
</body></html>"""

    def _export_pdf(self, html_content: str, stock_code: str) -> Optional[str]:
        """HTML → PDF（使用fpdf2）"""
        try:
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            # 简化版PDF（完整版需配置中文字体）
            pdf.cell(0, 10, f"Research Report - {stock_code}", ln=True)
            pdf.cell(0, 10, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", ln=True)
            pdf_path = os.path.join(self.output_dir, f"{stock_code}_{datetime.now().strftime('%Y%m%d')}.pdf")
            pdf.output(pdf_path)
            return pdf_path
        except Exception as e:
            logger.debug(f"PDF导出: {e}")
            return None
