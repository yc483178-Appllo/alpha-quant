# strategy_evolution.py --- 策略自进化引擎
# 每周自动评估 → 调参优化 → 淘汰弱策略 → 生成迭代报告

from datetime import datetime, timedelta
from loguru import logger

class StrategyEvolution:
    """
    策略自进化引擎

    工作流：
    1. 收集过去N周各策略的实盘/模拟表现
    2. 计算滚动指标（夏普、胜率、盈亏比）
    3. 与基准对比，评估Alpha
    4. 自动标记/降级/淘汰表现差的策略
    5. 生成迭代建议书
    """

    # 策略评估阈值
    THRESHOLDS = {
        "min_win_rate": 0.45,       # 最低胜率
        "min_sharpe": 0.5,          # 最低夏普
        "max_drawdown": -0.20,      # 最大回撤容忍
        "min_profit_factor": 1.2,   # 最低盈亏比
        "degrade_weeks": 2,         # 连续不达标周数 → 降级
        "remove_weeks": 4,          # 连续不达标周数 → 淘汰
    }

    def __init__(self):
        self.strategy_records = {}  # 各策略历史表现记录

    def evaluate_strategy(self, strategy_name, metrics):
        """
        评估单个策略

        参数:
            strategy_name: 策略名称
            metrics: {"win_rate": 0.55, "sharpe": 1.2, "max_dd": -0.08, "profit_factor": 1.8}
        """
        issues = []

        if metrics["win_rate"] < self.THRESHOLDS["min_win_rate"]:
            issues.append(f"胜率 {metrics['win_rate']:.0%} < {self.THRESHOLDS['min_win_rate']:.0%}")

        if metrics["sharpe"] < self.THRESHOLDS["min_sharpe"]:
            issues.append(f"夏普 {metrics['sharpe']:.2f} < {self.THRESHOLDS['min_sharpe']}")

        if metrics["max_dd"] < self.THRESHOLDS["max_drawdown"]:
            issues.append(f"回撤 {metrics['max_dd']:.0%} > 容忍线 {self.THRESHOLDS['max_drawdown']:.0%}")

        if metrics["profit_factor"] < self.THRESHOLDS["min_profit_factor"]:
            issues.append(f"盈亏比 {metrics['profit_factor']:.2f} < {self.THRESHOLDS['min_profit_factor']}")

        status = "healthy" if not issues else "warning" if len(issues) <= 1 else "critical"

        return {
            "strategy": strategy_name,
            "status": status,
            "metrics": metrics,
            "issues": issues,
            "recommendation": self._get_recommendation(status, issues)
        }

    def _get_recommendation(self, status, issues):
        """生成改进建议"""
        if status == "healthy":
            return "策略表现良好，保持当前参数"
        elif status == "warning":
            return f"需关注: {'; '.join(issues)}。建议微调相关参数。"
        else:
            return f"严重告警: {'; '.join(issues)}。建议暂停该策略并进行深度回测。"

    def weekly_review(self, all_strategy_metrics):
        """
        周度策略大阅兵

        参数:
            all_strategy_metrics: {"momentum": {...}, "value": {...}, ...}
        返回:
            完整评估报告
        """
        report = {
            "review_date": datetime.now().strftime("%Y-%m-%d"),
            "strategies": {},
            "summary": {}
        }

        healthy_count = 0
        for name, metrics in all_strategy_metrics.items():
            eval_result = self.evaluate_strategy(name, metrics)
            report["strategies"][name] = eval_result
            if eval_result["status"] == "healthy":
                healthy_count += 1

        report["summary"] = {
            "total_strategies": len(all_strategy_metrics),
            "healthy": healthy_count,
            "warning": sum(1 for s in report["strategies"].values() if s["status"] == "warning"),
            "critical": sum(1 for s in report["strategies"].values() if s["status"] == "critical"),
            "overall_health": "良好" if healthy_count >= len(all_strategy_metrics) * 0.6 else "需关注"
        }

        return report

if __name__ == "__main__":
    engine = StrategyEvolution()
    metrics = {
        "momentum": {"win_rate": 0.58, "sharpe": 1.5, "max_dd": -0.12, "profit_factor": 1.9},
        "value": {"win_rate": 0.52, "sharpe": 0.8, "max_dd": -0.08, "profit_factor": 1.5},
        "trend": {"win_rate": 0.42, "sharpe": 0.3, "max_dd": -0.22, "profit_factor": 0.9},
        "reversal": {"win_rate": 0.55, "sharpe": 1.1, "max_dd": -0.10, "profit_factor": 1.6},
        "composite": {"win_rate": 0.60, "sharpe": 1.8, "max_dd": -0.06, "profit_factor": 2.1},
    }

    report = engine.weekly_review(metrics)
    print(f"策略健康度: {report['summary']['overall_health']}")
    for name, data in report["strategies"].items():
        icon = {"healthy": "✅", "warning": "⚠️", "critical": "❌"}[data["status"]]
        print(f"  {icon} {name}: {data['status']} - {data['recommendation']}")
