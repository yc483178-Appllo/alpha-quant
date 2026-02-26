"""
配置管理模块 - 支持 JSON 配置文件和环境变量替换
"""
import json
import os
import re
from typing import Any, Dict
from pathlib import Path

class ConfigManager:
    """配置管理器"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件并替换环境变量"""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 替换环境变量 ${VAR_NAME} 或 ${VAR_NAME:default}
        def replace_env_var(match):
            var_expr = match.group(1)
            if ':' in var_expr:
                var_name, default = var_expr.split(':', 1)
            else:
                var_name, default = var_expr, None
            
            value = os.getenv(var_name, default)
            if value is None:
                print(f"⚠️  警告: 环境变量 {var_name} 未设置")
                return match.group(0)  # 保持原样
            return value
        
        content = re.sub(r'\$\{([^}]+)\}', replace_env_var, content)
        
        return json.loads(content)
    
    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项，支持点号分隔的路径"""
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_data_source_config(self, source_name: str) -> Dict[str, Any]:
        """获取数据源配置"""
        return self.get(f'data_sources.{source_name}', {})
    
    def get_risk_config(self) -> Dict[str, Any]:
        """获取风控配置"""
        return self.get('risk', {})
    
    def get_notification_config(self) -> Dict[str, Any]:
        """获取通知配置"""
        return self.get('notification', {})
    
    def get_cache_config(self) -> Dict[str, Any]:
        """获取缓存配置"""
        return self.get('cache', {})
    
    def get_execution_config(self) -> Dict[str, Any]:
        """获取交易执行配置"""
        return self.get('execution', {})
    
    def get_logging_config(self) -> Dict[str, Any]:
        """获取日志配置"""
        return self.get('logging', {})
    
    def get_global_config(self) -> Dict[str, Any]:
        """获取全局配置"""
        return self.get('global_config', {})
    
    def is_data_source_enabled(self, source_name: str) -> bool:
        """检查数据源是否启用"""
        return self.get(f'data_sources.{source_name}.enabled', False)
    
    def get_data_source_priority(self) -> list:
        """获取按优先级排序的数据源列表"""
        sources = self.get('data_sources', {})
        enabled_sources = [
            (name, config) for name, config in sources.items()
            if config.get('enabled', False)
        ]
        # 按优先级排序
        enabled_sources.sort(key=lambda x: x[1].get('priority', 999))
        return [name for name, _ in enabled_sources]
    
    def get_notification_channels(self, level: str) -> list:
        """获取指定级别的通知渠道"""
        return self.get(f'notification.notification_levels.{level}', [])
    
    def reload(self):
        """重新加载配置"""
        self.config = self._load_config()
        print("✅ 配置已重新加载")

# 全局配置实例
config_manager = ConfigManager()

# 便捷访问函数
def get_config(key: str, default: Any = None) -> Any:
    """获取配置项"""
    return config_manager.get(key, default)
