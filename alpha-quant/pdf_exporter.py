"""
Alpha-Genesis V6.1 SimEdge - PDF 报告导出修复
修复 4.5: PDF 报告导出完善
================================================
使用 WeasyPrint 替代原有实现
原生支持中文字体 + CSS3 渲染 + 图表嵌入

Author: Alpha-Genesis Team
Version: 6.1.0
Date: 2026-03-09
"""

import os
import json
import base64
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union
from io import BytesIO

import pandas as pd
import numpy as np

# WeasyPrint 导入
try:
    from weasyprint import HTML, CSS
    from weasyprint.text.fonts import FontConfiguration
    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logging.warning("weasyprint 未安装，PDF 导出功能不可用")

# 图表生成
try:
    import matplotlib
    matplotlib.use('Agg')  # 无头模式
    import matplotlib.pyplot as plt
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

logger = logging.getLogger("PDFExporter")


class PDFReportExporter:
    """
    PDF 报告导出器
    基于 WeasyPrint，支持中文、CSS3、图表嵌入
    """
    
    def __init__(self, template_dir: str = "./templates", output_dir: str = "./reports"):
        """
        初始化 PDF 导出器
        
        Args:
            template_dir: HTML 模板目录
            output_dir: PDF 输出目录
        """
        self.template_dir = Path(template_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # 字体配置
        self.font_config = FontConfiguration() if WEASYPRINT_AVAILABLE else None
        
        # 默认 CSS 样式
        self.default_css = self._get_default_css()
        
        logger.info("PDF 导出器初始化完成")
    
    def _get_default_css(self) -> str:
        """获取默认 CSS 样式"""
        return '''
            @page {
                size: A4;
                margin: 2cm;
                @bottom-center {
                    content: "Alpha-Genesis V6.1 | 第 " counter(page) " 页";
                    font-size: 9pt;
                    color: #666;
                }
            }
            
            body {
                font-family: "Noto Sans CJK SC", "Source Han Sans SC", "WenQuanYi Micro Hei", "SimHei", sans-serif;
                font-size: 11pt;
                line-height: 1.6;
                color: #333;
            }
            
            h1 {
                font-size: 24pt;
                color: #722ed1;
                border-bottom: 3px solid #722ed1;
                padding-bottom: 10px;
                margin-bottom: 20px;
            }
            
            h2 {
                font-size: 16pt;
                color: #333;
                border-left: 4px solid #722ed1;
                padding-left: 10px;
                margin-top: 25px;
            }
            
            h3 {
                font-size: 13pt;
                color: #555;
                margin-top: 20px;
            }
            
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
                font-size: 10pt;
            }
            
            th {
                background: linear-gradient(135deg, #722ed1 0%, #b37feb 100%);
                color: white;
                padding: 10px;
                text-align: left;
                font-weight: 600;
            }
            
            td {
                padding: 8px 10px;
                border-bottom: 1px solid #e8e8e8;
            }
            
            tr:nth-child(even) {
                background: #fafafa;
            }
            
            .highlight {
                background: #f9f0ff;
                padding: 15px;
                border-radius: 8px;
                border-left: 4px solid #722ed1;
                margin: 15px 0;
            }
            
            .metric-card {
                display: inline-block;
                width: 22%;
                padding: 15px;
                margin: 5px;
                background: linear-gradient(135deg, #f9f0ff 0%, #ffffff 100%);
                border: 1px solid #d3adf7;
                border-radius: 8px;
                text-align: center;
            }
            
            .metric-value {
                font-size: 20pt;
                font-weight: bold;
                color: #722ed1;
            }
            
            .metric-label {
                font-size: 9pt;
                color: #666;
                margin-top: 5px;
            }
            
            .positive {
                color: #52c41a;
            }
            
            .negative {
                color: #f5222d;
            }
            
            .chart-container {
                text-align: center;
                margin: 20px 0;
                padding: 10px;
                background: #fafafa;
                border-radius: 8px;
            }
            
            .chart-container img {
                max-width: 100%;
                height: auto;
            }
            
            .footer {
                margin-top: 30px;
                padding-top: 15px;
                border-top: 1px solid #e8e8e8;
                font-size: 9pt;
                color: #999;
                text-align: center;
            }
        '''
    
    def _chart_to_base64(self, fig) -> str:
        """将 matplotlib 图表转换为 base64 图片"""
        if not MATPLOTLIB_AVAILABLE:
            return ""
        
        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=150, bbox_inches='tight')
        buffer.seek(0)
        image_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close(fig)
        return f"data:image/png;base64,{image_base64}"
    
    def create_nav_chart(self, nav_data: Dict) -> str:
        """创建净值曲线图"""
        if not MATPLOTLIB_AVAILABLE:
            return ""
        
        fig, ax = plt.subplots(figsize=(8, 4))
        
        dates = nav_data.get('dates', [])
        values = nav_data.get('values', [])
        
        ax.plot(dates, values, linewidth=2, color='#722ed1')
        ax.fill_between(range(len(values)), 1, values, alpha=0.3, color='#d3adf7')
        ax.axhline(y=1, color='#999', linestyle='--', linewidth=0.8)
        
        ax.set_title('净值曲线', fontsize=14, fontweight='bold', pad=15)
        ax.set_xlabel('日期', fontsize=10)
        ax.set_ylabel('净值', fontsize=10)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        return self._chart_to_base64(fig)
    
    def create_pie_chart(self, data: Dict, title: str = "分布图") -> str:
        """创建饼图"""
        if not MATPLOTLIB_AVAILABLE:
            return ""
        
        fig, ax = plt.subplots(figsize=(6, 6))
        
        labels = list(data.keys())
        sizes = list(data.values())
        colors = ['#722ed1', '#b37feb', '#d3adf7', '#f9f0ff', '#1890ff']
        
        ax.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=90, colors=colors)
        ax.set_title(title, fontsize=14, fontweight='bold', pad=15)
        
        plt.tight_layout()
        return self._chart_to_base64(fig)
    
    def export_report(
        self,
        report_data: Dict,
        template: str = None,
        output_filename: str = None
    ) -> str:
        """
        导出 PDF 报告
        
        Args:
            report_data: 报告数据字典
            template: HTML 模板字符串 (可选)
            output_filename: 输出文件名 (可选)
        
        Returns:
            PDF 文件路径
        """
        if not WEASYPRINT_AVAILABLE:
            logger.error("WeasyPrint 未安装，无法导出 PDF")
            return ""
        
        # 生成默认文件名
        if not output_filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_type = report_data.get('type', 'report')
            output_filename = f"{report_type}_{timestamp}.pdf"
        
        output_path = self.output_dir / output_filename
        
        # 生成 HTML 内容
        if template:
            html_content = template
        else:
            html_content = self._generate_default_report_html(report_data)
        
        # 创建 PDF
        try:
            html = HTML(string=html_content)
            css = CSS(string=self.default_css, font_config=self.font_config)
            html.write_pdf(output_path, stylesheets=[css], font_config=self.font_config)
            
            logger.info(f"PDF 报告已生成: {output_path}")
            return str(output_path)
            
        except Exception as e:
            logger.error(f"PDF 生成失败: {e}")
            return ""
    
    def _generate_default_report_html(self, data: Dict) -> str:
        """生成默认报告 HTML"""
        report_type = data.get('type', '通用报告')
        title = data.get('title', f'Alpha-Genesis {report_type}')
        date = data.get('date', datetime.now().strftime('%Y-%m-%d'))
        
        # 指标卡片
        metrics = data.get('metrics', {})
        metrics_html = ""
        for label, value in metrics.items():
            css_class = ""
            if isinstance(value, (int, float)):
                if value > 0:
                    css_class = "positive"
                    display_value = f"+{value}"
                elif value < 0:
                    css_class = "negative"
                    display_value = f"{value}"
                else:
                    display_value = str(value)
            else:
                display_value = str(value)
            
            metrics_html += f'''
                <div class="metric-card">
                    <div class="metric-value {css_class}">{display_value}</div>
                    <div class="metric-label">{label}</div>
                </div>
            '''
        
        # 持仓表格
        positions = data.get('positions', [])
        positions_html = ""
        if positions:
            positions_html = '''
                <h2>持仓明细</h2>
                <table>
                    <tr>
                        <th>股票代码</th>
                        <th>股票名称</th>
                        <th>持仓数量</th>
                        <th>成本价</th>
                        <th>当前价</th>
                        <th>盈亏</th>
                    </tr>
            '''
            for pos in positions:
                pnl_class = "positive" if pos.get('pnl', 0) >= 0 else "negative"
                positions_html += f'''
                    <tr>
                        <td>{pos.get('code', '')}</td>
                        <td>{pos.get('name', '')}</td>
                        <td>{pos.get('qty', 0)}</td>
                        <td>{pos.get('cost_price', 0)}</td>
                        <td>{pos.get('current_price', 0)}</td>
                        <td class="{pnl_class}">{pos.get('pnl', 0):+.2f}</td>
                    </tr>
                '''
            positions_html += "</table>"
        
        # 图表
        charts_html = ""
        nav_chart = data.get('nav_chart')
        if nav_chart:
            chart_base64 = self.create_nav_chart(nav_chart)
            if chart_base64:
                charts_html += f'''
                    <div class="chart-container">
                        <img src="{chart_base64}" alt="净值曲线" />
                    </div>
                '''
        
        # 组装 HTML
        html = f'''<!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <title>{title}</title>
        </head>
        <body>
            <h1>{title}</h1>
            
            <div class="highlight">
                报告日期: {date} | 生成时间: {datetime.now().strftime('%H:%M:%S')}
            </div>
            
            <h2>核心指标</h2>
            <div>{metrics_html}</div>
            
            {charts_html}
            {positions_html}
            
            <div class="footer">
                本报告由 Alpha-Genesis V6.1 自动生成，仅供参考，不构成投资建议。
            </div>
        </body>
        </html>'''
        
        return html
    
    def export_morning_report(self, data: Dict, output_filename: str = None) -> str:
        """
        导出晨报 PDF
        
        Args:
            data: 晨报数据
            output_filename: 输出文件名
        
        Returns:
            PDF 路径
        """
        data['type'] = '晨报'
        data['title'] = f"Alpha-Genesis 晨报 - {datetime.now().strftime('%Y年%m月%d日')}"
        return self.export_report(data, output_filename=output_filename)
    
    def export_daily_report(self, data: Dict, output_filename: str = None) -> str:
        """
        导出收盘复盘报告 PDF
        
        Args:
            data: 复盘数据
            output_filename: 输出文件名
        
        Returns:
            PDF 路径
        """
        data['type'] = '收盘复盘'  
        data['title'] = f"Alpha-Genesis 收盘复盘 - {datetime.now().strftime('%Y年%m月%d日')}"
        return self.export_report(data, output_filename=output_filename)


# ═══════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════

def export_to_pdf(data: Dict, output_path: str = None) -> str:
    """
    便捷函数: 导出 PDF
    
    Args:
        data: 报告数据
        output_path: 输出路径
    
    Returns:
        PDF 文件路径
    """
    exporter = PDFReportExporter()
    return exporter.export_report(data, output_filename=output_path)


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== PDF 报告导出器测试 ===\n")
    
    if not WEASYPRINT_AVAILABLE:
        print("❌ WeasyPrint 未安装，跳过测试")
        exit(0)
    
    # 测试数据
    test_data = {
        'type': '测试报告',
        'title': 'Alpha-Genesis 测试报告',
        'date': datetime.now().strftime('%Y-%m-%d'),
        'metrics': {
            '总资产': '¥1,234,567',
            '累计收益': '+12.5%',
            '今日收益': '+1.2%',
            '夏普比率': '1.85',
            '最大回撤': '-5.3%'
        },
        'positions': [
            {'code': '600519', 'name': '贵州茅台', 'qty': 100, 'cost_price': 1800, 'current_price': 1924, 'pnl': 12400},
            {'code': '300750', 'name': '宁德时代', 'qty': 200, 'cost_price': 200, 'current_price': 195, 'pnl': -1000},
        ],
        'nav_chart': {
            'dates': list(range(30)),
            'values': [1 + i * 0.005 + np.random.randn() * 0.01 for i in range(30)]
        }
    }
    
    # 测试导出
    print("1. 测试 PDF 导出:")
    exporter = PDFReportExporter()
    pdf_path = exporter.export_report(test_data, output_filename="test_report.pdf")
    
    if pdf_path:
        print(f"   ✅ PDF 已生成: {pdf_path}")
        print(f"   文件大小: {os.path.getsize(pdf_path) / 1024:.1f} KB")
    else:
        print("   ❌ PDF 生成失败")
    
    # 测试晨报导出
    print("\n2. 测试晨报导出:")
    morning_data = {
        'metrics': {
            '上证指数': '+0.42%',
            '深证成指': '+0.68%',
            '创业板指': '+1.15%'
        },
        'positions': []
    }
    morning_path = exporter.export_morning_report(morning_data, "morning_test.pdf")
    if morning_path:
        print(f"   ✅ 晨报 PDF: {morning_path}")
    
    print("\n✅ PDF 导出器测试完成")
