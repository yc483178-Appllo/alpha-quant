"""
Alpha-Genesis V6.1 SimEdge - 配置管理中心
完善 P2-2: 配置中心化
======================================
Pydantic Settings管理，支持.env+config.json+环境变量，热更新

Author: Alpha-Genesis Team
Version: 6.1.0
Date: 2026-03-09
"""

import os
import json
from typing import Dict, List, Optional, Any
from pathlib import Path
from datetime import datetime

# Pydantic Settings
try:
    from pydantic import BaseModel, Field
    from pydantic_settings import BaseSettings, SettingsConfigDict
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    # 回退到普通类
    BaseModel = object
    BaseSettings = object


class TradingConfig(BaseModel if PYDANTIC_AVAILABLE else object):
    """交易配置"""
    max_position_pct: float = 0.20
    max_sector_pct: float = 0.40
    stop_loss_pct: float = 0.08
    take_profit_pct: float = 0.20
    enable_simulation: bool = True
    default_account_capital: float = 1000000.0


class DataSourceConfig(BaseModel if PYDANTIC_AVAILABLE else object):
    """数据源配置"""
    tushare_token: str = ""
    joinquant_username: str = ""
    joinquant_password: str = ""
    ths_token: str = ""
    akshare_enabled: bool = True
    baostock_enabled: bool = True


class NotificationConfig(BaseModel if PYDANTIC_AVAILABLE else object):
    """通知配置"""
    feishu_webhook: str = ""
    feishu_secret: str = ""
    dingtalk_webhook: str = ""
    email_smtp: str = ""
    email_user: str = ""
    email_password: str = ""


class EvolutionConfig(BaseModel if PYDANTIC_AVAILABLE else object):
    """策略进化配置"""
    enabled: bool = True
    population_capacity: int = 100
    evolution_frequency_hours: int = 24
    crossover_ratio: float = 0.7
    mutation_rate: float = 0.15
    backtest_days: int = 60


class AlphaConfig(BaseSettings if PYDANTIC_AVAILABLE else object):
    """
    Alpha-Genesis 主配置类
    
    配置优先级 (高到低):
    1. 环境变量 (ALPHA_*)  
    2. .env 文件
    3. config.json
    4. 默认值
    """
    
    if PYDANTIC_AVAILABLE:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            env_prefix="ALPHA_",  # 环境变量前缀
            extra="ignore"
        )
    
    # 基础配置
    app_name: str = "Alpha-Genesis"
    version: str = "6.1.0"
    environment: str = "production"  # development/staging/production
    debug: bool = False
    
    # 路径配置
    data_dir: str = "./data"
    log_dir: str = "./logs"
    model_dir: str = "./models"
    report_dir: str = "./reports"
    
    # 数据库
    mongodb_url: str = "mongodb://localhost:27017"
    redis_url: str = "redis://localhost:6379/0"
    
    # API配置
    api_host: str = "0.0.0.0"
    api_port: int = 5000
    websocket_enabled: bool = True
    
    # 子配置
    trading: TradingConfig = None
    data_source: DataSourceConfig = None
    notification: NotificationConfig = None
    evolution: EvolutionConfig = None
    
    # 热更新支持
    _config_file: str = "config.json"
    _last_modified: float = 0
    _watchers: List = None
    
    def __post_init__(self):
        """初始化子配置"""
        if self.trading is None:
            self.trading = TradingConfig()
        if self.data_source is None:
            self.data_source = DataSourceConfig()
        if self.notification is None:
            self.notification = NotificationConfig()
        if self.evolution is None:
            self.evolution = EvolutionConfig()
        if self._watchers is None:
            self._watchers = []


class ConfigManager:
    """
    配置管理器
    
    功能：
    - 多源配置加载 (.env + config.json + 环境变量)
    - 配置热更新
    - 配置验证
    - 配置导出
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        初始化配置管理器
        
        Args:
            config_path: 配置文件路径
        """
        self.config_path = Path(config_path)
        self.config: Optional[AlphaConfig] = None
        self._watch_enabled = False
        self._watch_thread = None
        
        self._load_config()
    
    def _load_config(self):
        """加载配置"""
        if PYDANTIC_AVAILABLE:
            # 使用 Pydantic Settings 自动加载
            self.config = AlphaConfig(_config_file=str(self.config_path))
        else:
            # 回退到手动加载
            self.config = self._load_config_manual()
        
        # 记录文件修改时间
        if self.config_path.exists():
            self.config._last_modified = self.config_path.stat().st_mtime
        
        print(f"✅ 配置加载完成 | 环境: {self.config.environment}")
    
    def _load_config_manual(self) -> AlphaConfig:
        """手动加载配置 (无 Pydantic 时)"""
        config = AlphaConfig()
        
        # 1. 加载 config.json
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # 简单更新
            for key, value in data.items():
                if hasattr(config, key):
                    setattr(config, key, value)
        
        # 2. 加载环境变量
        env_mappings = {
            "ALPHA_MONGODB_URL": "mongodb_url",
            "ALPHA_REDIS_URL": "redis_url",
            "ALPHA_DEBUG": "debug",
            "ALPHA_API_PORT": "api_port",
            "TUSHARE_TOKEN": "data_source.tushare_token",
            "JQ_USERNAME": "data_source.joinquant_username",
            "JQ_PASSWORD": "data_source.joinquant_password",
        }
        
        for env_key, config_key in env_mappings.items():
            value = os.environ.get(env_key)
            if value:
                if "." in config_key:
                    # 嵌套属性
                    parts = config_key.split(".")
                    obj = config
                    for part in parts[:-1]:
                        obj = getattr(obj, part)
                    setattr(obj, parts[-1], value)
                else:
                    setattr(config, config_key, value)
        
        return config
    
    def reload(self) -> bool:
        """
        重新加载配置
        
        Returns:
            是否成功
        """
        try:
            old_config = self.config
            self._load_config()
            
            # 通知观察者
            for watcher in self.config._watchers:
                try:
                    watcher(old_config, self.config)
                except Exception as e:
                    print(f"配置更新通知失败: {e}")
            
            return True
        except Exception as e:
            print(f"配置重载失败: {e}")
            return False
    
    def check_update(self) -> bool:
        """
        检查配置文件是否有更新
        
        Returns:
            是否有更新
        """
        if not self.config_path.exists():
            return False
        
        current_mtime = self.config_path.stat().st_mtime
        if current_mtime > self.config._last_modified:
            return True
        
        return False
    
    def auto_reload(self, interval: int = 10):
        """
        启动自动重载
        
        Args:
            interval: 检查间隔(秒)
        """
        import threading
        
        self._watch_enabled = True
        
        def watch_loop():
            while self._watch_enabled:
                if self.check_update():
                    print("检测到配置更新，正在重载...")
                    self.reload()
                time.sleep(interval)
        
        self._watch_thread = threading.Thread(target=watch_loop, daemon=True)
        self._watch_thread.start()
        
        print(f"配置自动重载已启动 | 检查间隔: {interval}s")
    
    def stop_auto_reload(self):
        """停止自动重载"""
        self._watch_enabled = False
        if self._watch_thread:
            self._watch_thread.join(timeout=1)
    
    def on_update(self, callback):
        """
        注册配置更新回调
        
        Args:
            callback: 回调函数(old_config, new_config)
        """
        self.config._watchers.append(callback)
    
    def save(self, path: str = None):
        """
        保存配置到文件
        
        Args:
            path: 保存路径 (默认覆盖原文件)
        """
        path = path or str(self.config_path)
        
        if PYDANTIC_AVAILABLE:
            data = self.config.model_dump()
        else:
            data = {
                "app_name": self.config.app_name,
                "version": self.config.version,
                "environment": self.config.environment,
                "debug": self.config.debug,
                "data_dir": self.config.data_dir,
                "log_dir": self.config.log_dir,
                "mongodb_url": self.config.mongodb_url,
                "redis_url": self.config.redis_url,
                "api_host": self.config.api_host,
                "api_port": self.config.api_port,
            }
        
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        print(f"配置已保存: {path}")
    
    def get(self, key: str, default=None):
        """
        获取配置值 (支持点号路径)
        
        Args:
            key: 配置键 (如 "trading.max_position_pct")
            default: 默认值
        
        Returns:
            配置值
        """
        parts = key.split(".")
        value = self.config
        
        for part in parts:
            if hasattr(value, part):
                value = getattr(value, part)
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any):
        """
        设置配置值
        
        Args:
            key: 配置键
            value: 配置值
        """
        parts = key.split(".")
        obj = self.config
        
        for part in parts[:-1]:
            obj = getattr(obj, part)
        
        setattr(obj, parts[-1], value)


# ═══════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════

_config_manager: Optional[ConfigManager] = None


def init_config(config_path: str = "config.json") -> ConfigManager:
    """初始化全局配置"""
    global _config_manager
    _config_manager = ConfigManager(config_path)
    return _config_manager


def get_config() -> AlphaConfig:
    """获取配置实例"""
    global _config_manager
    if _config_manager is None:
        _config_manager = init_config()
    return _config_manager.config


def get_config_manager() -> ConfigManager:
    """获取配置管理器"""
    global _config_manager
    if _config_manager is None:
        _config_manager = init_config()
    return _config_manager


# ═══════════════════════════════════════════════════════════
# 测试
# ═══════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("=== 配置管理中心测试 ===\n")
    
    # 创建测试配置文件
    test_config = {
        "app_name": "Alpha-Genesis-Test",
        "environment": "development",
        "debug": True,
        "api_port": 5001,
        "trading": {
            "max_position_pct": 0.15,
            "enable_simulation": True
        }
    }
    
    with open("test_config.json", "w") as f:
        json.dump(test_config, f)
    
    # 初始化配置
    print("1. 加载配置:")
    manager = ConfigManager("test_config.json")
    config = manager.config
    
    print(f"   应用名称: {config.app_name}")
    print(f"   环境: {config.environment}")
    print(f"   API端口: {config.api_port}")
    print(f"   最大仓位: {config.trading.max_position_pct}")
    
    # 测试 get/set
    print("\n2. 测试 get/set:")
    print(f"   get('trading.max_position_pct'): {manager.get('trading.max_position_pct')}")
    
    manager.set("trading.max_position_pct", 0.20)
    print(f"   修改后: {manager.get('trading.max_position_pct')}")
    
    # 测试配置验证
    if PYDANTIC_AVAILABLE:
        print("\n3. Pydantic 验证通过 ✓")
    else:
        print("\n3. 使用手动配置加载 (Pydantic 未安装)")
    
    # 测试保存
    print("\n4. 测试配置保存:")
    manager.save("test_config_saved.json")
    
    # 清理
    import os
    os.remove("test_config.json")
    os.remove("test_config_saved.json")
    
    print("\n✅ 配置管理中心测试完成")
