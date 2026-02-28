#!/usr/bin/env python3
"""
health_checker.py --- 系统健康自检（每日08:45执行）

检查项：
1. 数据网关状态
2. 信号服务器状态
3. 数据源连通性（Tushare/AkShare/同花顺）
4. 交易日历
5. 磁盘空间
6. 通知服务

自动修复：尝试重启异常服务
"""

import os
import sys
import json
import psutil
import requests
import subprocess
from datetime import datetime
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from loguru import logger

sys.path.insert(0, '/root/.openclaw/workspace/alpha-quant')

from modules.notifier import Notifier
from modules.cloud_storage import CloudStorage


@dataclass
class HealthCheckResult:
    """健康检查结果"""
    name: str
    status: bool
    detail: str
    auto_fixed: bool = False


class HealthChecker:
    """系统健康检查器"""
    
    def __init__(self):
        self.results: List[HealthCheckResult] = []
        self.notifier = Notifier()
        self.storage = CloudStorage()
        
        # 服务配置
        self.services = {
            "signal_server": {"port": 8765, "health_url": "/health", "start_cmd": "./run_server.sh"},
            "data_gateway": {"port": 8766, "health_url": "/api/health", "start_cmd": "python3 start_gateway.py"}
        }
    
    def check_service(self, name: str, config: Dict) -> HealthCheckResult:
        """检查单个服务状态"""
        url = f"http://127.0.0.1:{config['port']}{config['health_url']}"
        
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                status = data.get("status", "unknown")
                return HealthCheckResult(name, status == "ok", f"状态: {status}")
            else:
                return HealthCheckResult(name, False, f"HTTP {resp.status_code}")
        except Exception as e:
            return HealthCheckResult(name, False, f"连接失败: {str(e)[:50]}")
    
    def auto_restart_service(self, name: str, config: Dict) -> bool:
        """自动重启服务"""
        logger.warning(f"🔄 尝试重启服务: {name}")
        
        try:
            # 先杀掉旧进程
            subprocess.run(["pkill", "-f", name.replace("_", "")], 
                         capture_output=True, timeout=5)
            
            # 启动新进程
            cmd = config["start_cmd"]
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, 
                           stderr=subprocess.DEVNULL)
            
            # 等待服务启动
            import time
            time.sleep(3)
            
            # 验证重启成功
            result = self.check_service(name, config)
            return result.status
            
        except Exception as e:
            logger.error(f"❌ 重启失败: {e}")
            return False
    
    def check_data_sources(self) -> List[HealthCheckResult]:
        """检查数据源连通性"""
        results = []
        
        # 1. Tushare
        try:
            import tushare as ts
            from dotenv import load_dotenv
            load_dotenv()
            
            pro = ts.pro_api(os.getenv("TUSHARE_TOKEN"))
            df = pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20260131', limit=1)
            results.append(HealthCheckResult("Tushare", True, f"Token有效"))
        except Exception as e:
            results.append(HealthCheckResult("Tushare", False, str(e)[:50]))
        
        # 2. AkShare
        try:
            import akshare as ak
            df = ak.stock_zh_index_daily(symbol='sh000001')
            results.append(HealthCheckResult("AkShare", len(df) > 0, f"{len(df)}条历史数据"))
        except Exception as e:
            results.append(HealthCheckResult("AkShare", False, str(e)[:50]))
        
        # 3. 同花顺SDK
        try:
            from modules.trade_calendar import get_calendar
            cal = get_calendar()
            results.append(HealthCheckResult("同花顺SDK", True, f"交易日历: {len(cal.trade_dates)}天"))
        except Exception as e:
            results.append(HealthCheckResult("同花顺SDK", False, str(e)[:50]))
        
        return results
    
    def check_system_resources(self) -> List[HealthCheckResult]:
        """检查系统资源"""
        results = []
        
        # 1. 磁盘空间
        disk = psutil.disk_usage('/')
        disk_ok = disk.percent < 90
        results.append(HealthCheckResult(
            "磁盘空间", disk_ok, 
            f"已用 {disk.percent}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)"
        ))
        
        # 2. 内存使用
        mem = psutil.virtual_memory()
        mem_ok = mem.percent < 90
        results.append(HealthCheckResult(
            "内存使用", mem_ok,
            f"已用 {mem.percent}% ({mem.used // (1024**3)}GB / {mem.total // (1024**3)}GB)"
        ))
        
        # 3. CPU负载
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_ok = cpu_percent < 80
        results.append(HealthCheckResult(
            "CPU负载", cpu_ok, f"{cpu_percent}%"
        ))
        
        return results
    
    def check_notification(self) -> HealthCheckResult:
        """检查通知服务配置"""
        webhook = os.getenv("FEISHU_WEBHOOK_URL", "")
        if webhook:
            return HealthCheckResult("通知服务", True, "飞书Webhook已配置")
        else:
            return HealthCheckResult("通知服务", False, "飞书Webhook未配置")
    
    def run_full_check(self, auto_fix: bool = True) -> Tuple[str, bool]:
        """
        执行完整健康检查
        
        Args:
            auto_fix: 是否尝试自动修复
            
        Returns:
            (报告文本, 是否全部正常)
        """
        logger.info("=" * 60)
        logger.info("🏥 启动系统健康检查")
        logger.info("=" * 60)
        
        self.results = []
        
        # 1. 检查核心服务
        logger.info("检查核心服务...")
        for name, config in self.services.items():
            result = self.check_service(name, config)
            
            # 尝试自动修复
            if not result.status and auto_fix:
                fixed = self.auto_restart_service(name, config)
                if fixed:
                    result = HealthCheckResult(name, True, "已自动重启恢复", auto_fixed=True)
            
            self.results.append(result)
        
        # 2. 检查数据源
        logger.info("检查数据源...")
        self.results.extend(self.check_data_sources())
        
        # 3. 检查系统资源
        logger.info("检查系统资源...")
        self.results.extend(self.check_system_resources())
        
        # 4. 检查通知服务
        logger.info("检查通知服务...")
        self.results.append(self.check_notification())
        
        # 生成报告
        return self.generate_report()
    
    def generate_report(self) -> Tuple[str, bool]:
        """生成检查报告"""
        all_ok = all(r.status for r in self.results)
        failed_count = sum(1 for r in self.results if not r.status)
        fixed_count = sum(1 for r in self.results if r.auto_fixed)
        
        report_lines = [
            "## 🏥 Alpha系统健康检查报告",
            f"**检查时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"**检查项**: {len(self.results)} 项",
            "",
            "### 检查结果",
            ""
        ]
        
        # 分类显示
        for result in self.results:
            icon = "✅" if result.status else "❌"
            fixed_tag = " [已自动修复]" if result.auto_fixed else ""
            report_lines.append(f"- {icon} **{result.name}**: {result.detail}{fixed_tag}")
        
        # 总体状态
        report_lines.extend([
            "",
            "### 总体状态",
            ""
        ])
        
        if all_ok:
            if fixed_count > 0:
                report_lines.append(f"🟡 **基本正常** ({fixed_count}项已自动修复)")
            else:
                report_lines.append("🟢 **全部正常**")
        else:
            report_lines.append(f"🔴 **存在异常** ({failed_count}项需要关注)")
        
        # 建议
        if failed_count > 0:
            report_lines.extend([
                "",
                "### 处理建议",
                ""
            ])
            for r in self.results:
                if not r.status:
                    report_lines.append(f"- **{r.name}**: 请检查配置或手动重启服务")
        
        report = "\n".join(report_lines)
        
        # 保存报告
        self.storage.save_daily_report(report, datetime.now().strftime("%Y-%m-%d-health"))
        
        # 发送通知（如果有异常）
        if not all_ok:
            self.notifier.warning(
                title="⚠️ 系统健康异常",
                content=f"健康检查发现 {failed_count} 项异常，请查看详细报告并处理。"
            )
        
        logger.info(f"健康检查完成: {'全部正常' if all_ok else f'{failed_count}项异常'}")
        
        return report, all_ok


# 便捷函数
def quick_check() -> bool:
    """快速检查，返回是否全部正常"""
    checker = HealthChecker()
    _, ok = checker.run_full_check(auto_fix=True)
    return ok


def full_health_check() -> Tuple[str, bool]:
    """完整健康检查"""
    checker = HealthChecker()
    return checker.run_full_check(auto_fix=True)


# 使用示例
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='系统健康检查')
    parser.add_argument('--no-fix', action='store_true', help='不自动修复')
    parser.add_argument('--notify', action='store_true', help='强制发送通知')
    args = parser.parse_args()
    
    report, ok = full_health_check()
    print(report)
    
    sys.exit(0 if ok else 1)
