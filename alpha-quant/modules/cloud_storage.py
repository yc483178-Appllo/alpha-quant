# cloud_storage.py --- 云端存储管理模块
# 实现规范的目录结构和文件管理

import os
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, List, Dict
from dataclasses import dataclass
from loguru import logger


@dataclass
class StorageConfig:
    """存储配置"""
    base_path: str = "./cloud_storage"  # 本地存储路径（可同步到云端）
    retention_days: int = 90  # 文件保留天数
    auto_cleanup: bool = True  # 自动清理旧文件


class CloudStorage:
    """
    云端存储管理器
    
    目录结构:
    cloud_storage/
    ├── Reports/
    │   ├── Morning/        # 每日盘前调研
    │   ├── Daily/          # 每日收盘复盘
    │   ├── Weekly/         # 每周策略总结
    │   └── Monthly/        # 月度绩效报告
    ├── Strategies/         # 策略代码版本管理
    ├── Backtests/          # 回测结果存档
    ├── Signals/            # 交易信号归档
    ├── Logs/               # 系统日志归档
    └── Watchlist/          # 持续关注的股票池
    """
    
    def __init__(self, config: Optional[StorageConfig] = None):
        self.config = config or StorageConfig()
        self.base_path = Path(self.config.base_path)
        self._init_directories()
    
    def _init_directories(self):
        """初始化目录结构"""
        directories = [
            "Reports/Morning",
            "Reports/Daily", 
            "Reports/Weekly",
            "Reports/Monthly",
            "Strategies",
            "Backtests",
            "Signals",
            "Logs",
            "Watchlist"
        ]
        
        for dir_path in directories:
            full_path = self.base_path / dir_path
            full_path.mkdir(parents=True, exist_ok=True)
            
        logger.info(f"✅ 云端存储目录初始化完成: {self.base_path}")
    
    # ========== 报告存储 ==========
    def save_morning_report(self, content: str, date: Optional[str] = None) -> str:
        """保存盘前调研报告"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        filepath = self.base_path / "Reports/Morning" / f"{date}-morning.md"
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"💾 盘前报告已保存: {filepath}")
        return str(filepath)
    
    def save_daily_report(self, content: str, date: Optional[str] = None) -> str:
        """保存每日收盘复盘"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        filepath = self.base_path / "Reports/Daily" / f"{date}-daily.md"
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"💾 每日复盘已保存: {filepath}")
        return str(filepath)
    
    def save_weekly_report(self, content: str, date: Optional[str] = None) -> str:
        """保存每周策略总结"""
        if date is None:
            # 获取当前周数
            date = datetime.now().strftime("%Y-W%W")
        
        filepath = self.base_path / "Reports/Weekly" / f"{date}-weekly.md"
        filepath.write_text(content, encoding="utf-8")
        logger.info(f"💾 周报已保存: {filepath}")
        return str(filepath)
    
    def save_monthly_report(self, content: bytes, date: Optional[str] = None) -> str:
        """保存月度绩效报告（PDF）"""
        if date is None:
            date = datetime.now().strftime("%Y-%m")
        
        filepath = self.base_path / "Reports/Monthly" / f"{date}-monthly.pdf"
        filepath.write_bytes(content)
        logger.info(f"💾 月报已保存: {filepath}")
        return str(filepath)
    
    # ========== 策略管理 ==========
    def save_strategy(self, name: str, code: str, version: Optional[str] = None) -> str:
        """保存策略代码"""
        if version is None:
            version = "v1"
        
        filename = f"{name}_{version}.py"
        filepath = self.base_path / "Strategies" / filename
        filepath.write_text(code, encoding="utf-8")
        logger.info(f"💾 策略已保存: {filepath}")
        return str(filepath)
    
    def list_strategies(self) -> List[Dict]:
        """列出所有策略"""
        strategies = []
        strategy_dir = self.base_path / "Strategies"
        
        for file_path in strategy_dir.glob("*.py"):
            stat = file_path.stat()
            strategies.append({
                "name": file_path.stem,
                "path": str(file_path),
                "size": stat.st_size,
                "modified": datetime.fromtimestamp(stat.st_mtime).isoformat()
            })
        
        return sorted(strategies, key=lambda x: x["modified"], reverse=True)
    
    # ========== 回测结果 ==========
    def save_backtest(self, result: Dict, name: Optional[str] = None) -> str:
        """保存回测结果"""
        if name is None:
            name = datetime.now().strftime("%Y-%m-%d-%H%M%S")
        
        filepath = self.base_path / "Backtests" / f"{name}-backtest.json"
        filepath.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"💾 回测结果已保存: {filepath}")
        return str(filepath)
    
    def load_backtest(self, name: str) -> Optional[Dict]:
        """加载回测结果"""
        filepath = self.base_path / "Backtests" / f"{name}-backtest.json"
        if not filepath.exists():
            return None
        
        return json.loads(filepath.read_text(encoding="utf-8"))
    
    # ========== 交易信号 ==========
    def save_signals(self, signals: List[Dict], date: Optional[str] = None) -> str:
        """保存交易信号"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        filepath = self.base_path / "Signals" / f"{date}-signals.json"
        filepath.write_text(json.dumps(signals, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"💾 交易信号已保存: {filepath} ({len(signals)} 条)")
        return str(filepath)
    
    def load_signals(self, date: Optional[str] = None) -> List[Dict]:
        """加载交易信号"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        filepath = self.base_path / "Signals" / f"{date}-signals.json"
        if not filepath.exists():
            return []
        
        return json.loads(filepath.read_text(encoding="utf-8"))
    
    # ========== 日志归档 ==========
    def archive_log(self, log_content: str, date: Optional[str] = None) -> str:
        """归档系统日志"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        
        filepath = self.base_path / "Logs" / f"{date}.log"
        filepath.write_text(log_content, encoding="utf-8")
        logger.info(f"💾 日志已归档: {filepath}")
        return str(filepath)
    
    # ========== 股票池 ==========
    def save_watchlist(self, stocks: List[Dict], name: str = "default") -> str:
        """保存关注股票池"""
        filepath = self.base_path / "Watchlist" / f"{name}.csv"
        
        import pandas as pd
        df = pd.DataFrame(stocks)
        df.to_csv(filepath, index=False, encoding="utf-8-sig")
        
        logger.info(f"💾 股票池已保存: {filepath} ({len(stocks)} 只)")
        return str(filepath)
    
    def load_watchlist(self, name: str = "default") -> List[Dict]:
        """加载关注股票池"""
        filepath = self.base_path / "Watchlist" / f"{name}.csv"
        if not filepath.exists():
            return []
        
        import pandas as pd
        df = pd.read_csv(filepath, encoding="utf-8-sig")
        return df.to_dict("records")
    
    # ========== 清理维护 ==========
    def cleanup_old_files(self, days: Optional[int] = None):
        """清理过期文件"""
        if not self.config.auto_cleanup:
            return
        
        if days is None:
            days = self.config.retention_days
        
        cutoff = datetime.now() - timedelta(days=days)
        deleted_count = 0
        
        for root, dirs, files in os.walk(self.base_path):
            for file in files:
                filepath = Path(root) / file
                try:
                    stat = filepath.stat()
                    mtime = datetime.fromtimestamp(stat.st_mtime)
                    if mtime < cutoff:
                        filepath.unlink()
                        deleted_count += 1
                        logger.debug(f"🗑️ 删除过期文件: {filepath}")
                except Exception as e:
                    logger.error(f"删除文件失败 {filepath}: {e}")
        
        if deleted_count > 0:
            logger.info(f"🧹 清理完成，删除 {deleted_count} 个过期文件")
    
    def get_storage_stats(self) -> Dict:
        """获取存储统计信息"""
        stats = {
            "base_path": str(self.base_path),
            "total_size": 0,
            "file_count": 0,
            "directories": {}
        }
        
        for root, dirs, files in os.walk(self.base_path):
            for file in files:
                filepath = Path(root) / file
                try:
                    size = filepath.stat().st_size
                    stats["total_size"] += size
                    stats["file_count"] += 1
                except:
                    pass
        
        # 统计各目录
        for subdir in ["Reports", "Strategies", "Backtests", "Signals", "Logs", "Watchlist"]:
            dir_path = self.base_path / subdir
            if dir_path.exists():
                count = len(list(dir_path.rglob("*")))
                stats["directories"][subdir] = count
        
        return stats


# 便捷函数
def get_storage() -> CloudStorage:
    """获取存储实例（单例）"""
    return CloudStorage()


# 使用示例
if __name__ == "__main__":
    storage = CloudStorage()
    
    # 保存报告示例
    storage.save_daily_report("# 每日复盘\n\n今日大盘上涨0.5%...")
    
    # 保存策略示例
    storage.save_strategy("momentum", "# 动量策略代码...", version="v2")
    
    # 保存信号示例
    storage.save_signals([
        {"code": "000001.SZ", "action": "buy", "price": 10.5},
        {"code": "688256.SH", "action": "sell", "price": 850.0}
    ])
    
    # 查看统计
    stats = storage.get_storage_stats()
    print(f"存储统计: {stats}")
    
    # 清理旧文件
    storage.cleanup_old_files(days=30)
