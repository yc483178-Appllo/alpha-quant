# env_loader.py --- 项目启动时首先调用
import os
from dotenv import load_dotenv
from modules.logger import log

def init_env():
    """加载环境变量并验证必要配置"""
    # 加载 .env 文件
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path)
        log.info(f"✅ 已加载环境变量: {env_path}")
    else:
        load_dotenv()  # 尝试从系统环境变量加载
        log.warning("⚠️  .env 文件不存在，使用系统环境变量")

    # 检查必要的环境变量
    required_vars = ["TUSHARE_TOKEN"]
    missing = [v for v in required_vars if not os.getenv(v)]

    if missing:
        log.error(f"❌ 缺少必要的环境变量: {missing}")
        log.info("请检查 .env 文件是否正确配置")
        raise EnvironmentError(f"Missing required env vars: {missing}")

    log.info("✅ 环境变量加载完成")
    
    # 返回环境变量字典
    return {
        "tushare_token": os.getenv("TUSHARE_TOKEN", ""),
        "ths_token": os.getenv("THS_TOKEN", ""),
        "feishu_webhook": os.getenv("FEISHU_WEBHOOK_URL", ""),
        "dingtalk_webhook": os.getenv("DINGTALK_WEBHOOK_URL", ""),
        "dingtalk_secret": os.getenv("DINGTALK_SECRET", ""),
        "pushplus_token": os.getenv("PUSHPLUS_TOKEN", ""),
        "ptrade_token": os.getenv("PTRADE_TOKEN", ""),
        "ptrade_host": os.getenv("PTRADE_HOST", "http://127.0.0.1:8888"),
        "redis_url": os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0"),
    }

# 全局环境变量
env_vars = None

def get_env():
    """获取环境变量（延迟加载）"""
    global env_vars
    if env_vars is None:
        env_vars = init_env()
    return env_vars
