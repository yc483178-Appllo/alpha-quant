"""
Alpha-Genesis V6.1 SimEdge - 投研报告模板系统
完善 P1-3: 投研报告模板自定义
======================================
YAML模板配置，用户可自定义章节、指标、图表组合

Author: Alpha-Genesis Team
Version: 6.1.0
Date: 2026-03-09
"""

import os
import yaml
import logging
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = logging.getLogger("ReportTemplates")


@dataclass
class ReportSection:
    """报告章节定义"""
    name: str
    title: str
    enabled: bool = True
    order: int = 0
    subsections: List['ReportSection'] = field(default_factory=list)
    config: Dict = field(default_factory=dict)


@dataclass
class ReportMetric:
    """报告指标定义"""
    name: str
    display_name: str
    data_source: str  # 数据来源: market/fundamental/technical/portfolio
    query: str        # 查询路径
    format: str = "number"  # number/percentage/currency/datetime
    decimals: int = 2
    enabled: bool = True
    warning_threshold: Optional[float] = None
    alert_threshold: Optional[float] = None


@dataclass
class ReportChart:
    """报告图表定义"""
    name: str
    title: str
    chart_type: str  # line/bar/pie/radar/heatmap
    data_sources: List[str]  # 数据来源列表
    config: Dict = field(default_factory=dict)
    enabled: bool = True


@dataclass
class ReportTemplate:
    """报告模板定义"""
    id: str
    name: str
    description: str
    version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sections: List[ReportSection] = field(default_factory=list)
    metrics: List[ReportMetric] = field(default_factory=list)
    charts: List[ReportChart] = field(default_factory=list)
    style: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ReportTemplate':
        """从字典创建模板"""
        sections = [ReportSection(**s) for s in data.get('sections', [])]
        metrics = [ReportMetric(**m) for m in data.get('metrics', [])]
        charts = [ReportChart(**c) for c in data.get('charts', [])]
        
        return cls(
            id=data['id'],
            name=data['name'],
            description=data.get('description', ''),
            version=data.get('version', '1.0'),
            created_at=data.get('created_at', datetime.now().isoformat()),
            sections=sections,
            metrics=metrics,
            charts=charts,
            style=data.get('style', {})
        )


class ReportTemplateManager:
    """
    投研报告模板管理器
    
    功能：
    - YAML 模板加载/保存
    - 模板CRUD操作
    - 模板验证
    - 默认模板库
    """
    
    def __init__(self, template_dir: str = "./templates/reports"):
        """
        初始化模板管理器
        
        Args:
            template_dir: 模板存储目录
        """
        self.template_dir = Path(template_dir)
        self.template_dir.mkdir(parents=True, exist_ok=True)
        
        self.templates: Dict[str, ReportTemplate] = {}
        
        # 加载内置模板
        self._load_builtin_templates()
        
        # 加载用户自定义模板
        self._load_user_templates()
        
        logger.info(f"模板管理器初始化完成 | 模板数: {len(self.templates)}")
    
    def _load_builtin_templates(self):
        """加载内置默认模板"""
        # 1. 晨报模板
        morning_template = ReportTemplate(
            id="morning_default",
            name="默认晨报模板",
            description="Alpha-Genesis 默认晨报模板",
            sections=[
                ReportSection(
                    name="header",
                    title="报告头信息",
                    order=0,
                    config={"show_date": True, "show_version": True}
                ),
                ReportSection(
                    name="market_overview",
                    title="市场概览",
                    order=1,
                    config={"indices": ["sh", "sz", "cy"], "show_futures": True}
                ),
                ReportSection(
                    name="positions",
                    title="持仓概览",
                    order=2,
                    config={"show_details": True, "show_pnl": True}
                ),
                ReportSection(
                    name="signals",
                    title="今日信号",
                    order=3,
                    config={"max_signals": 10}
                ),
                ReportSection(
                    name="watchlist",
                    title="关注清单",
                    order=4,
                    config={"stocks_per_sector": 3}
                )
            ],
            metrics=[
                ReportMetric(
                    name="total_assets",
                    display_name="总资产",
                    data_source="portfolio",
                    query="total_assets",
                    format="currency",
                    decimals=2
                ),
                ReportMetric(
                    name="daily_pnl",
                    display_name="今日盈亏",
                    data_source="portfolio",
                    query="daily_pnl",
                    format="percentage",
                    decimals=2,
                    warning_threshold=-0.02,
                    alert_threshold=-0.05
                ),
                ReportMetric(
                    name="sharpe_ratio",
                    display_name="夏普比率",
                    data_source="portfolio",
                    query="performance.sharpe",
                    format="number",
                    decimals=2
                ),
                ReportMetric(
                    name="max_drawdown",
                    display_name="最大回撤",
                    data_source="portfolio",
                    query="performance.max_drawdown",
                    format="percentage",
                    decimals=2,
                    alert_threshold=0.15
                )
            ],
            charts=[
                ReportChart(
                    name="nav_curve",
                    title="净值曲线",
                    chart_type="line",
                    data_sources=["portfolio.nav_history"],
                    config={"show_benchmark": True, "period": "3m"}
                ),
                ReportChart(
                    name="position_allocation",
                    title="持仓分布",
                    chart_type="pie",
                    data_sources=["portfolio.positions"],
                    config={"group_by": "sector"}
                ),
                ReportChart(
                    name="sector_performance",
                    title="板块表现",
                    chart_type="bar",
                    data_sources=["market.sector_returns"],
                    config={"top_n": 10, "sort_by": "change"}
                )
            ],
            style={
                "primary_color": "#722ed1",
                "font_family": "Noto Sans CJK SC",
                "page_size": "A4",
                "orientation": "portrait"
            }
        )
        
        # 2. 收盘复盘模板
        closing_template = ReportTemplate(
            id="closing_default",
            name="默认收盘复盘模板",
            description="Alpha-Genesis 默认收盘复盘模板",
            sections=[
                ReportSection(name="header", title="报告头信息", order=0),
                ReportSection(name="market_review", title="大盘回顾", order=1),
                ReportSection(name="position_review", title="持仓复盘", order=2),
                ReportSection(name="trades", title="今日交易", order=3),
                ReportSection(name="signals_review", title="信号回顾", order=4),
                ReportSection(name="lessons", title="经验总结", order=5),
                ReportSection(name="tomorrow_plan", title="明日计划", order=6)
            ],
            metrics=[
                ReportMetric(name="total_assets", display_name="总资产", data_source="portfolio", query="total_assets", format="currency"),
                ReportMetric(name="daily_return", display_name="今日收益率", data_source="portfolio", query="daily_return", format="percentage"),
                ReportMetric(name="win_rate", display_name="胜率", data_source="portfolio", query="performance.win_rate", format="percentage"),
                ReportMetric(name="profit_factor", display_name="盈亏比", data_source="portfolio", query="performance.profit_factor", format="number")
            ],
            charts=[
                ReportChart(name="nav_curve", title="净值曲线", chart_type="line", data_sources=["portfolio.nav_history"]),
                ReportChart(name="trade_distribution", title="交易分布", chart_type="heatmap", data_sources=["portfolio.trades"]),
                ReportChart(name="sentiment_timeline", title="情绪时间线", chart_type="line", data_sources=["sentiment.timeline"])
            ]
        )
        
        # 3. 个股深度报告模板
        stock_template = ReportTemplate(
            id="stock_analysis",
            name="个股深度分析模板",
            description="个股技术面+基本面+舆情面四维分析",
            sections=[
                ReportSection(name="overview", title="概览", order=0),
                ReportSection(name="technical", title="技术面分析", order=1),
                ReportSection(name="fundamental", title="基本面分析", order=2),
                ReportSection(name="sentiment", title="舆情面分析", order=3),
                ReportSection(name="risk", title="风险评估", order=4),
                ReportSection(name="conclusion", title="结论建议", order=5)
            ],
            metrics=[
                ReportMetric(name="pe_ratio", display_name="市盈率", data_source="fundamental", query="valuation.pe_ttm", format="number"),
                ReportMetric(name="pb_ratio", display_name="市净率", data_source="fundamental", query="valuation.pb", format="number"),
                ReportMetric(name="roe", display_name="ROE", data_source="fundamental", query="profitability.roe", format="percentage"),
                ReportMetric(name="revenue_growth", display_name="营收增长率", data_source="fundamental", query="growth.revenue_yoy", format="percentage"),
                ReportMetric(name="rsi", display_name="RSI", data_source="technical", query="indicators.rsi_14", format="number", decimals=1),
                ReportMetric(name="macd_signal", display_name="MACD信号", data_source="technical", query="indicators.macd.signal", format="string")
            ],
            charts=[
                ReportChart(name="price_chart", title="K线图", chart_type="candlestick", data_sources=["market.kline"]),
                ReportChart(name="valuation_history", title="估值历史", chart_type="line", data_sources=["fundamental.valuation_history"]),
                ReportChart(name="sentiment_wordcloud", title="舆情词云", chart_type="wordcloud", data_sources=["sentiment.keywords"])
            ]
        )
        
        self.templates[morning_template.id] = morning_template
        self.templates[closing_template.id] = closing_template
        self.templates[stock_template.id] = stock_template
    
    def _load_user_templates(self):
        """加载用户自定义模板"""
        if not self.template_dir.exists():
            return
        
        for yaml_file in self.template_dir.glob("*.yaml"):
            try:
                with open(yaml_file, 'r', encoding='utf-8') as f:
                    data = yaml.safe_load(f)
                
                template = ReportTemplate.from_dict(data)
                self.templates[template.id] = template
                logger.info(f"加载用户模板: {template.id}")
                
            except Exception as e:
                logger.error(f"加载模板失败 {yaml_file}: {e}")
    
    def save_template(self, template: ReportTemplate) -> bool:
        """
        保存模板到 YAML 文件
        
        Args:
            template: 报告模板
        
        Returns:
            是否成功
        """
        try:
            file_path = self.template_dir / f"{template.id}.yaml"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(template.to_dict(), f, allow_unicode=True, sort_keys=False)
            
            self.templates[template.id] = template
            logger.info(f"模板已保存: {template.id}")
            return True
            
        except Exception as e:
            logger.error(f"保存模板失败: {e}")
            return False
    
    def get_template(self, template_id: str) -> Optional[ReportTemplate]:
        """获取模板"""
        return self.templates.get(template_id)
    
    def list_templates(self) -> List[Dict]:
        """列出所有模板"""
        return [
            {
                "id": t.id,
                "name": t.name,
                "description": t.description,
                "version": t.version,
                "created_at": t.created_at
            }
            for t in self.templates.values()
        ]
    
    def delete_template(self, template_id: str) -> bool:
        """删除模板"""
        if template_id in self.templates:
            file_path = self.template_dir / f"{template_id}.yaml"
            if file_path.exists():
                file_path.unlink()
            del self.templates[template_id]
            logger.info(f"模板已删除: {template_id}")
            return True
        return False
    
    def create_template_from_yaml(self, yaml_content: str) -> Optional[ReportTemplate]:
        """
        从 YAML 内容创建模板
        
        Args:
            yaml_content: YAML 格式字符串
        
        Returns:
            创建的模板
        """
        try:
            data = yaml.safe_load(yaml_content)
            template = ReportTemplate.from_dict(data)
            
            # 验证模板
            if not self._validate_template(template):
                logger.error("模板验证失败")
                return None
            
            self.save_template(template)
            return template
            
        except Exception as e:
            logger.error(f"创建模板失败: {e}")
            return None
    
    def _validate_template(self, template: ReportTemplate) -> bool:
        """验证模板有效性"""
        if not template.id or not template.name:
            logger.error("模板 ID 和名称不能为空")
            return False
        
        # 检查 ID 格式
        if not re.match(r'^[a-zA-Z0-9_-]+$', template.id):
            logger.error("模板 ID 只能包含字母、数字、下划线和连字符")
            return False
        
        return True
    
    def export_template_yaml(self, template_id: str) -> str:
        """
        导出模板为 YAML 字符串
        
        Args:
            template_id: 模板ID
        
        Returns:
            YAML 字符串
        """
        template = self.get_template(template_id)
        if not template:
            return ""
        
        return yaml.dump(template.to_dict(), allow_unicode=True, sort_keys=False)


# ═══════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════

def get_template_manager(template_dir: str = "./templates/reports") -> ReportTemplateManager:
    """获取模板管理器单例"""
    return ReportTemplateManager(template_dir)


def create_custom_template(
    template_id: str,
    name: str,
    description: str,
    sections: List[Dict],
    metrics: List[Dict],
    charts: List[Dict]
) -> ReportTemplate:
    """
    便捷函数: 创建自定义模板
    """
    template = ReportTemplate(
        id=template_id,
        name=name,
        description=description,
        sections=[ReportSection(**s) for s in sections],
        metrics=[ReportMetric(**m) for m in metrics],
        charts=[ReportChart(**c) for c in charts]
    )
    
    manager = get_template_manager()
    manager.save_template(template)
    
    return template


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== 投研报告模板系统测试 ===\n")
    
    # 初始化管理器
    manager = ReportTemplateManager()
    
    # 测试列出模板
    print("1. 列出所有模板:")
    templates = manager.list_templates()
    for t in templates:
        print(f"   {t['id']}: {t['name']}")
    
    # 测试获取模板
    print("\n2. 获取晨报模板:")
    morning = manager.get_template("morning_default")
    if morning:
        print(f"   名称: {morning.name}")
        print(f"   章节数: {len(morning.sections)}")
        print(f"   指标数: {len(morning.metrics)}")
        print(f"   图表数: {len(morning.charts)}")
    
    # 测试导出 YAML
    print("\n3. 导出模板 YAML:")
    yaml_content = manager.export_template_yaml("morning_default")
    print(f"   YAML 长度: {len(yaml_content)} 字符")
    print(f"   前200字符:\n{yaml_content[:200]}...")
    
    # 测试创建自定义模板
    print("\n4. 测试创建自定义模板:")
    custom_sections = [
        {"name": "header", "title": "报告头", "order": 0},
        {"name": "custom_section", "title": "自定义章节", "order": 1, "config": {"param": "value"}}
    ]
    custom_metrics = [
        {"name": "custom_metric", "display_name": "自定义指标", "data_source": "custom", "query": "data.value", "format": "number"}
    ]
    custom_charts = [
        {"name": "custom_chart", "title": "自定义图表", "chart_type": "line", "data_sources": ["custom.data"]}
    ]
    
    custom_template = create_custom_template(
        template_id="custom_test",
        name="测试自定义模板",
        description="用于测试的自定义模板",
        sections=custom_sections,
        metrics=custom_metrics,
        charts=custom_charts
    )
    
    if custom_template:
        print(f"   创建成功: {custom_template.id}")
        print(f"   文件路径: ./templates/reports/{custom_template.id}.yaml")
    
    print("\n✅ 模板系统测试完成")
