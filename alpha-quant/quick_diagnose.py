#!/usr/bin/env python3
"""
quick_diagnose.py --- 快速问题诊断脚本
一键排查常见问题
"""

import os
import sys
import requests
from datetime import datetime

sys.path.insert(0, '/root/.openclaw/workspace/alpha-quant')

def check_env():
    """检查环境变量"""
    # 先加载 .env 文件
    from dotenv import load_dotenv
    load_dotenv()
    
    print("=" * 60)
    print("🔍 检查环境变量")
    print("=" * 60)
    
    required_vars = [
        "TUSHARE_TOKEN",
        "THS_ACCOUNT",
        "FEISHU_WEBHOOK_URL"
    ]
    
    for var in required_vars:
        value = os.getenv(var, "")
        status = "✅" if value else "❌"
        display = value[:30] + "..." if len(value) > 30 else value
        print(f"{status} {var}: {display if value else '未配置'}")
    
    return all(os.getenv(var) for var in required_vars)

def check_services():
    """检查服务状态"""
    print("\n" + "=" * 60)
    print("🔍 检查服务状态")
    print("=" * 60)
    
    services = {
        "信号服务器": {"port": 8765, "endpoint": "/health"},
        "数据网关": {"port": 8766, "endpoint": "/api/health"}
    }
    
    all_ok = True
    for name, config in services.items():
        try:
            url = f"http://127.0.0.1:{config['port']}{config['endpoint']}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                print(f"✅ {name}: 运行正常 (端口{config['port']})")
            else:
                print(f"⚠️ {name}: HTTP {resp.status_code}")
                all_ok = False
        except Exception as e:
            print(f"❌ {name}: {str(e)[:50]}")
            all_ok = False
    
    return all_ok

def check_data_sources():
    """检查数据源"""
    print("\n" + "=" * 60)
    print("🔍 检查数据源")
    print("=" * 60)
    
    results = []
    
    # Tushare
    try:
        import tushare as ts
        pro = ts.pro_api(os.getenv("TUSHARE_TOKEN"))
        df = pro.trade_cal(exchange='SSE', start_date='20260101', end_date='20260131', limit=1)
        print("✅ Tushare: 连接正常")
        results.append(True)
    except Exception as e:
        print(f"❌ Tushare: {e}")
        results.append(False)
    
    # AkShare
    try:
        import akshare as ak
        df = ak.stock_zh_index_daily(symbol='sh000001')
        print(f"✅ AkShare: 连接正常 ({len(df)}条数据)")
        results.append(True)
    except Exception as e:
        print(f"⚠️ AkShare: {e}")
        results.append(False)
    
    # 同花顺
    try:
        from modules.trade_calendar import get_calendar
        cal = get_calendar()
        print(f"✅ 同花顺SDK: 连接正常 ({len(cal.trade_dates)}个交易日)")
        results.append(True)
    except Exception as e:
        print(f"❌ 同花顺SDK: {e}")
        results.append(False)
    
    return any(results)  # 至少一个可用

def check_today_market():
    """检查今日市场状态"""
    print("\n" + "=" * 60)
    print("📅 今日市场状态")
    print("=" * 60)
    
    from modules.trade_calendar import get_calendar
    cal = get_calendar()
    
    print(f"日期: {datetime.now().strftime('%Y-%m-%d')}")
    print(f"是否交易日: {'✅ 是' if cal.is_trade_date() else '❌ 否'}")
    print(f"市场阶段: {cal.get_market_phase()}")
    print(f"下一交易日: {cal.next_trade_date()}")

def suggest_fixes():
    """提供修复建议"""
    print("\n" + "=" * 60)
    print("💡 快速修复命令")
    print("=" * 60)
    print("""
1. 重启数据网关:
   tmux kill-session -t gateway 2>/dev/null; tmux new-session -d -s gateway "cd /root/.openclaw/workspace/alpha-quant && source quant_env/bin/activate && python data_gateway.py"

2. 重启信号服务器:
   pkill -f signal_server; cd /root/.openclaw/workspace/alpha-quant && ./run_server.sh

3. 检查日志:
   tail -f logs/gateway_$(date +%Y-%m-%d).log

4. 运行健康检查:
   python health_checker.py

5. 查看所有服务:
   ps aux | grep -E "(signal_server|data_gateway|gunicorn)" | grep -v grep
""")

def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🚀 Alpha Quant 快速诊断工具")
    print("=" * 60)
    
    env_ok = check_env()
    services_ok = check_services()
    data_ok = check_data_sources()
    check_today_market()
    
    # 总结
    print("\n" + "=" * 60)
    print("📊 诊断总结")
    print("=" * 60)
    
    issues = []
    if not env_ok:
        issues.append("环境变量配置不完整")
    if not services_ok:
        issues.append("部分服务未运行")
    if not data_ok:
        issues.append("数据源连接异常")
    
    if issues:
        print(f"❌ 发现 {len(issues)} 个问题:")
        for issue in issues:
            print(f"   - {issue}")
        suggest_fixes()
    else:
        print("✅ 系统运行正常")
    
    return len(issues) == 0

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
