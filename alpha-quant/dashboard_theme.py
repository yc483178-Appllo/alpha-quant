"""
Alpha-Genesis V6.1 SimEdge - 看板主题系统
完善 P2-5: 看板主题切换
======================================
新增亮色主题CSS变量集，一键切换暗黑/亮色（Claude创新：增加"交易日/非交易日"自动切换）

Author: Alpha-Genesis Team
Version: 6.1.0
Date: 2026-03-09
"""

from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


class ThemeMode(Enum):
    """主题模式"""
    DARK = "dark"
    LIGHT = "light"
    AUTO = "auto"  # 自动根据交易日切换


class TradingDayStatus(Enum):
    """交易日状态"""
    TRADING_DAY = "trading_day"      # 交易日
    NON_TRADING_DAY = "non_trading"  # 非交易日
    PRE_MARKET = "pre_market"        # 盘前
    POST_MARKET = "post_market"      # 盘后


@dataclass
class ThemeConfig:
    """主题配置"""
    mode: ThemeMode
    primary_color: str
    bg_color: str
    text_color: str
    card_bg: str
    border_color: str
    success_color: str
    warning_color: str
    danger_color: str
    chart_grid: str


class DashboardThemeManager:
    """
    看板主题管理器
    
    功能：
    - 暗黑/亮色主题切换
    - CSS 变量管理
    - 交易日自动检测和主题切换
    - 主题预设
    """
    
    # 主题定义
    THEMES = {
        "dark": ThemeConfig(
            mode=ThemeMode.DARK,
            primary_color="#722ed1",
            bg_color="#0d1117",
            text_color="#e6edf3",
            card_bg="#161b22",
            border_color="#30363d",
            success_color="#52c41a",
            warning_color="#faad14",
            danger_color="#f5222d",
            chart_grid="#21262d"
        ),
        "light": ThemeConfig(
            mode=ThemeMode.LIGHT,
            primary_color="#722ed1",
            bg_color="#f5f5f5",
            text_color="#1f1f1f",
            card_bg="#ffffff",
            border_color="#e8e8e8",
            success_color="#52c41a",
            warning_color="#fa8c16",
            danger_color="#f5222d",
            chart_grid="#f0f0f0"
        ),
        "trading": ThemeConfig(  # 交易日专属主题（高对比度）
            mode=ThemeMode.DARK,
            primary_color="#a855f7",
            bg_color="#0a0a0a",
            text_color="#ffffff",
            card_bg="#141414",
            border_color="#2a2a2a",
            success_color="#22c55e",
            warning_color="#f59e0b",
            danger_color="#ef4444",
            chart_grid="#1a1a1a"
        ),
        "relax": ThemeConfig(  # 非交易日放松主题（暖色调）
            mode=ThemeMode.LIGHT,
            primary_color="#6366f1",
            bg_color="#fafaf9",
            text_color="#44403c",
            card_bg="#ffffff",
            border_color="#e7e5e4",
            success_color="#10b981",
            warning_color="#f59e0b",
            danger_color="#ef4444",
            chart_grid="#f5f5f4"
        )
    }
    
    def __init__(self):
        self.current_theme = "dark"
        self.auto_switch_enabled = True
        self.trading_hours = {
            "pre_market": ("09:00", "09:30"),
            "morning": ("09:30", "11:30"),
            "afternoon": ("13:00", "15:00"),
            "post_market": ("15:00", "15:30")
        }
    
    def get_css_variables(self, theme_name: str = None) -> str:
        """
        获取主题 CSS 变量
        
        Args:
            theme_name: 主题名称 (默认当前主题)
        
        Returns:
            CSS 变量字符串
        """
        theme_name = theme_name or self.current_theme
        theme = self.THEMES.get(theme_name, self.THEMES["dark"])
        
        return f"""
:root {{
  /* 主色调 */
  --color-primary: {theme.primary_color};
  --color-primary-light: {theme.primary_color}dd;
  --color-primary-dark: {theme.primary_color}aa;
  
  /* 背景色 */
  --color-bg: {theme.bg_color};
  --color-bg-secondary: {theme.card_bg};
  --color-bg-tertiary: {theme.border_color};
  
  /* 文字色 */
  --color-text: {theme.text_color};
  --color-text-secondary: {theme.text_color}aa;
  --color-text-tertiary: {theme.text_color}66;
  
  /* 边框 */
  --color-border: {theme.border_color};
  --color-divider: {theme.border_color}80;
  
  /* 状态色 */
  --color-success: {theme.success_color};
  --color-warning: {theme.warning_color};
  --color-danger: {theme.danger_color};
  
  /* 图表 */
  --color-chart-grid: {theme.chart_grid};
  --color-chart-line: {theme.primary_color};
  --color-chart-area: {theme.primary_color}20;
  
  /* 阴影 */
  --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
  --shadow-md: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
  --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
  
  /* 圆角 */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  
  /* 过渡 */
  --transition-fast: 150ms ease;
  --transition-normal: 250ms ease;
  --transition-slow: 350ms ease;
}}

/* 主题切换动画 */
* {{
  transition: background-color var(--transition-normal),
              color var(--transition-fast),
              border-color var(--transition-fast);
}}
"""
    
    def switch_theme(self, theme_name: str) -> bool:
        """
        切换主题
        
        Args:
            theme_name: 主题名称 (dark/light/trading/relax/auto)
        
        Returns:
            是否成功
        """
        if theme_name == "auto":
            self.auto_switch_enabled = True
            theme_name = self._detect_theme_by_time()
        else:
            self.auto_switch_enabled = False
        
        if theme_name in self.THEMES:
            self.current_theme = theme_name
            return True
        
        return False
    
    def _detect_theme_by_time(self) -> str:
        """
        根据时间自动检测主题
        
        Returns:
            主题名称
        """
        now = datetime.now()
        weekday = now.weekday()
        time_str = now.strftime("%H:%M")
        
        # 检查是否是交易日 (周一到周五)
        is_trading_day = weekday < 5
        
        if not is_trading_day:
            # 周末使用放松主题
            return "relax"
        
        # 检查是否在交易时间
        in_trading_hours = False
        for period, (start, end) in self.trading_hours.items():
            if start <= time_str <= end:
                in_trading_hours = True
                break
        
        if in_trading_hours:
            return "trading"  # 交易时间使用高对比度主题
        else:
            return "dark" if self._is_night() else "light"
    
    def _is_night(self) -> bool:
        """检查是否是夜间 (18:00 - 06:00)"""
        hour = datetime.now().hour
        return hour >= 18 or hour < 6
    
    def get_trading_day_status(self) -> TradingDayStatus:
        """获取当前交易日状态"""
        now = datetime.now()
        weekday = now.weekday()
        time_str = now.strftime("%H:%M")
        
        # 非交易日
        if weekday >= 5:
            return TradingDayStatus.NON_TRADING_DAY
        
        # 检查交易时段
        if "09:00" <= time_str < "09:30":
            return TradingDayStatus.PRE_MARKET
        elif "09:30" <= time_str < "11:30" or "13:00" <= time_str < "15:00":
            return TradingDayStatus.TRADING_DAY
        elif "15:00" <= time_str < "15:30":
            return TradingDayStatus.POST_MARKET
        else:
            return TradingDayStatus.NON_TRADING_DAY
    
    def get_theme_for_status(self, status: TradingDayStatus) -> str:
        """根据交易日状态获取推荐主题"""
        theme_map = {
            TradingDayStatus.TRADING_DAY: "trading",
            TradingDayStatus.PRE_MARKET: "dark",
            TradingDayStatus.POST_MARKET: "dark",
            TradingDayStatus.NON_TRADING_DAY: "relax"
        }
        return theme_map.get(status, "dark")
    
    def generate_theme_css(self) -> str:
        """生成完整主题 CSS"""
        css = self.get_css_variables(self.current_theme)
        
        # 添加通用样式
        css += """
/* 通用组件样式 */
.card {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 16px;
  box-shadow: var(--shadow-sm);
}

.metric-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--color-text);
}

.metric-value.positive {
  color: var(--color-success);
}

.metric-value.negative {
  color: var(--color-danger);
}

.btn-primary {
  background: var(--color-primary);
  color: white;
  border: none;
  padding: 8px 16px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.btn-primary:hover {
  background: var(--color-primary-light);
}

/* 表格样式 */
table {
  width: 100%;
  border-collapse: collapse;
}

th {
  background: var(--color-bg-tertiary);
  color: var(--color-text);
  padding: 12px;
  text-align: left;
  font-weight: 600;
}

td {
  padding: 10px 12px;
  border-bottom: 1px solid var(--color-border);
  color: var(--color-text);
}

tr:hover {
  background: var(--color-bg-tertiary);
}

/* 状态徽章 */
.badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.badge-success {
  background: var(--color-success)20;
  color: var(--color-success);
}

.badge-warning {
  background: var(--color-warning)20;
  color: var(--color-warning);
}

.badge-danger {
  background: var(--color-danger)20;
  color: var(--color-danger);
}

/* 导航栏 */
.navbar {
  background: var(--color-bg-secondary);
  border-bottom: 1px solid var(--color-border);
  padding: 12px 24px;
}

/* 侧边栏 */
.sidebar {
  background: var(--color-bg-secondary);
  border-right: 1px solid var(--color-border);
}

.sidebar-item {
  padding: 12px 16px;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
}

.sidebar-item:hover,
.sidebar-item.active {
  background: var(--color-primary)20;
  color: var(--color-primary);
}

/* 图表容器 */
.chart-container {
  background: var(--color-bg-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 16px;
}

/* 滚动条 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}

::-webkit-scrollbar-track {
  background: var(--color-bg);
}

::-webkit-scrollbar-thumb {
  background: var(--color-border);
  border-radius: 4px;
}

::-webkit-scrollbar-thumb:hover {
  background: var(--color-text-tertiary);
}
"""
        
        return css
    
    def get_theme_toggle_js(self) -> str:
        """获取主题切换 JavaScript"""
        return """
// 主题切换功能
class ThemeManager {
    constructor() {
        this.currentTheme = localStorage.getItem('theme') || 'auto';
        this.autoSwitch = localStorage.getItem('auto_theme') !== 'false';
        this.init();
    }
    
    init() {
        this.applyTheme(this.currentTheme);
        
        // 每分钟检查一次（用于交易日自动切换）
        if (this.autoSwitch) {
            setInterval(() => this.checkAutoSwitch(), 60000);
        }
    }
    
    applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('theme', theme);
        
        // 更新 CSS 变量
        this.updateCSSVariables(theme);
    }
    
    updateCSSVariables(theme) {
        // 通过 API 获取主题变量并应用
        fetch(`/api/v6/theme/css?theme=${theme}`)
            .then(r => r.text())
            .then(css => {
                let styleEl = document.getElementById('theme-style');
                if (!styleEl) {
                    styleEl = document.createElement('style');
                    styleEl.id = 'theme-style';
                    document.head.appendChild(styleEl);
                }
                styleEl.textContent = css;
            });
    }
    
    toggle() {
        const themes = ['dark', 'light', 'trading', 'relax'];
        const currentIndex = themes.indexOf(this.currentTheme);
        const nextTheme = themes[(currentIndex + 1) % themes.length];
        this.applyTheme(nextTheme);
    }
    
    checkAutoSwitch() {
        // 调用后端 API 检测当前应该使用什么主题
        fetch('/api/v6/theme/detect')
            .then(r => r.json())
            .then(data => {
                if (data.theme !== this.currentTheme) {
                    this.applyTheme(data.theme);
                }
            });
    }
}

// 初始化
const themeManager = new ThemeManager();

// 导出全局函数
window.toggleTheme = () => themeManager.toggle();
window.setTheme = (t) => themeManager.applyTheme(t);
"""


# ═══════════════════════════════════════════════════════════
# Flask 路由
# ═══════════════════════════════════════════════════════════

def register_theme_routes(app, theme_manager: DashboardThemeManager):
    """
    注册主题路由到 Flask
    
    Args:
        app: Flask 应用
        theme_manager: 主题管理器
    """
    from flask import jsonify, request
    
    @app.route("/api/v6/theme/current", methods=["GET"])
    def get_current_theme():
        """获取当前主题"""
        return jsonify({
            "theme": theme_manager.current_theme,
            "auto_switch": theme_manager.auto_switch_enabled,
            "trading_status": theme_manager.get_trading_day_status().value
        })
    
    @app.route("/api/v6/theme/switch", methods=["POST"])
    def switch_theme():
        """切换主题"""
        data = request.get_json() or {}
        theme = data.get("theme", "dark")
        
        success = theme_manager.switch_theme(theme)
        
        return jsonify({
            "success": success,
            "theme": theme_manager.current_theme
        })
    
    @app.route("/api/v6/theme/css", methods=["GET"])
    def get_theme_css():
        """获取主题 CSS"""
        theme = request.args.get("theme", theme_manager.current_theme)
        css = theme_manager.get_css_variables(theme)
        return css, 200, {"Content-Type": "text/css"}
    
    @app.route("/api/v6/theme/detect", methods=["GET"])
    def detect_theme():
        """自动检测主题"""
        status = theme_manager.get_trading_day_status()
        recommended_theme = theme_manager.get_theme_for_status(status)
        
        return jsonify({
            "status": status.value,
            "theme": recommended_theme,
            "is_trading_hours": status == TradingDayStatus.TRADING_DAY
        })


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== 看板主题系统测试 ===\n")
    
    # 初始化主题管理器
    theme_mgr = DashboardThemeManager()
    
    # 测试获取 CSS 变量
    print("1. 测试获取暗黑主题 CSS:")
    css = theme_mgr.get_css_variables("dark")
    print(f"   CSS 长度: {len(css)} 字符")
    print(f"   包含变量: {'--color-primary' in css}")
    
    # 测试主题切换
    print("\n2. 测试主题切换:")
    print(f"   当前主题: {theme_mgr.current_theme}")
    theme_mgr.switch_theme("light")
    print(f"   切换后: {theme_mgr.current_theme}")
    
    # 测试交易日状态检测
    print("\n3. 测试交易日状态检测:")
    status = theme_mgr.get_trading_day_status()
    print(f"   当前状态: {status.value}")
    
    recommended = theme_mgr.get_theme_for_status(status)
    print(f"   推荐主题: {recommended}")
    
    # 测试自动生成 CSS
    print("\n4. 测试生成完整主题 CSS:")
    full_css = theme_mgr.generate_theme_css()
    print(f"   完整 CSS 长度: {len(full_css)} 字符")
    
    # 保存示例 CSS 文件
    with open("theme_example.css", "w") as f:
        f.write(full_css)
    print("   示例 CSS 已保存: theme_example.css")
    
    print("\n✅ 看板主题系统测试完成")
