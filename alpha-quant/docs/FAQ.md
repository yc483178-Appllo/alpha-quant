# 常见问题与最佳实践 (FAQ)

## Q1: AkShare 数据偶尔返回空或报错怎么处理？

### 问题原因
AkShare 接口依赖东方财富等数据源，偶尔会因对方服务器维护、限流或网络波动而失败。

### 解决方案 ✅ 已实现

我们的系统已内置三重容错机制：

#### ① 多数据源自动切换
```python
# data_gateway.py 中的实现
def get_realtime_data_with_fallback():
    # 1. 尝试 AkShare 主接口
    # 2. 失败则切换同花顺 SDK
    # 3. 再失败使用 AkShare 备用接口
```

**当前配置：**
- 主源：AkShare (stock_zh_a_spot_em)
- 备源1：同花顺 SDK (THS_RealtimeQuotes)
- 备源2：AkShare 指数接口 (stock_zh_index_daily)

#### ② 自动重试机制
```python
# 已集成 retry 装饰器
@retry(tries=3, delay=2, backoff=2)
def fetch_data():
    # 最多重试3次，间隔2秒，指数退避
```

#### ③ 本地缓存
```python
# trade_calendar.py 实现
class TradeCalendar:
    def _load(self):
        # 优先从本地缓存加载
        # 缓存无效才从在线获取
```

---

## Q2: 节假日休市时，定时任务如何处理？

### 解决方案 ✅ 已实现

#### 方法一：使用 TradeCalendar 判断
```python
from modules.trade_calendar import get_calendar

cal = get_calendar()
if cal.is_trade_date():
    # 执行交易相关任务
    run_trading_task()
else:
    logger.info("今日休市，任务跳过")
```

#### 方法二：使用智能调度器
```python
# smart_scheduler.py
python smart_scheduler.py -t daily -c "python daily_report.py"
# 自动判断交易日，非交易日跳过
```

#### 方法三：使用统一调度器
```python
# scheduler.py - 已集成交易日判断
@trade_day_only
def job_stock_screening():
    # 仅在交易日执行
    pass
```

---

## Q3: 如何验证 PTrade HTTP 接口连通性？

### 解决方案 ✅ 已提供

```python
# 快速检测脚本
import requests

PTRADE_HOST = os.getenv("PTRADE_HOST", "http://127.0.0.1:8888")

def check_ptrade_connection():
    try:
        resp = requests.get(f"{PTRADE_HOST}/api/health", timeout=3)
        if resp.status_code == 200:
            print(f"✅ PTrade 连接正常: HTTP {resp.status_code}")
            return True
    except requests.exceptions.ConnectionError:
        print("❌ 连接失败：确认PTrade客户端已启动，HTTP接口已开启")
    except requests.exceptions.Timeout:
        print("⚠️ 连接超时：检查防火墙或本地网络配置")
    return False
```

**健康检查已集成：**
```bash
python health_checker.py
# 自动检测 PTrade 连接状态
```

---

## Q4: 如何处理多个数据源数据不一致的问题？

### 解决方案 ✅ 已实现

#### 数据交叉验证规则
```python
# data_gateway.py 中的多源数据对比
def validate_data_consistency(sources: List[pd.DataFrame]) -> pd.DataFrame:
    """
    数据一致性验证：
    1. 对比多个数据源的同一只股票数据
    2. 偏差超过5%时取保守值
    3. 记录偏差日志
    """
    # 实现逻辑...
```

#### 保守值策略
| 数据类型 | 偏差处理 |
|---------|---------|
| 涨跌幅 | 取较低值（更保守） |
| 成交量 | 取较高值（更保守） |
| 价格 | 取多个源的中位数 |

#### 数据质量日志
```python
# 自动记录数据偏差
logger.warning(f"数据源偏差: {symbol} | "
               f"AkShare: {ak_price} | THS: {ths_price} | "
               f"偏差: {diff_pct}%")
```

---

## Q5: 信号服务器宕机后如何恢复？

### 解决方案 ✅ 已实现

#### ① 进程守护（Supervisor）
```ini
# supervisor.conf
[program:signal_server]
command=python signal_server.py
autostart=true
autorestart=true
startretries=3
```

#### ② 信号历史持久化
```python
# signal_server.py
signal_history = []  # 内存中的历史记录

# 自动保存到日志
logger.info(f"新信号 #{signal_id}: {action} {code}")

# 可从日志恢复
# logs/signal_YYYY-MM-DD.log
```

#### ③ 安全失败模式
```python
# PTrade 执行层
if signal_server_down:
    logger.error("信号服务器不可用，暂停交易")
    # 不执行任何操作，避免误交易
    return
```

#### ④ 健康检查自动重启
```python
# health_checker.py
if not check_service("signal_server"):
    auto_restart_service("signal_server")
```

---

## Q6: 如何从模拟盘安全过渡到实盘？

### 推荐流程

#### 第一阶段：模拟盘验证（30个交易日）
```python
# 配置
CONFIG = {
    "mode": "simulation",  # 模拟模式
    "initial_capital": 1000000,  # 100万虚拟资金
    "require_human_confirm": True,  # 必须人工确认
}

# 统计指标
metrics = {
    "total_return": "+15.3%",
    "sharpe_ratio": 1.8,
    "max_drawdown": "-8.5%",
    "win_rate": "62%",
    "profit_factor": 1.9
}
```

#### 第二阶段：小资金实盘（20个交易日）
```python
CONFIG = {
    "mode": "live",  # 实盘模式
    "max_position": 0.05,  # 最多5%仓位
    "require_human_confirm": True,  # 保持人工确认
    "single_stock_limit": 0.02,  # 单票不超过2%
}
```

#### 第三阶段：逐步加仓
```python
# 连续20天稳定后
if consecutive_stable_days >= 20:
    CONFIG["max_position"] = 0.10  # 提升至10%
    # 建议长期保持人工确认
    # CONFIG["require_human_confirm"] = True
```

### 风险控制清单
- [ ] 模拟盘运行满30个交易日
- [ ] 夏普比率 > 1.5
- [ ] 最大回撤 < 15%
- [ ] 胜率 > 55%
- [ ] 实盘首月仓位 ≤ 5%
- [ ] 人工确认机制长期保留

---

## 其他最佳实践

### 日志管理
```python
# 日志分级
logger.debug("详细调试信息")
logger.info("常规运行信息")
logger.warning("警告信息")
logger.error("错误信息")
```

### 配置管理
```bash
# 使用 .env 文件管理配置
.env
├── TUSHARE_TOKEN=xxx
├── THS_ACCOUNT=xxx
├── FEISHU_WEBHOOK_URL=xxx
└── PTRADE_HOST=http://127.0.0.1:8888
```

### 备份策略
```bash
# 自动备份脚本（daily_backup.sh）
#!/bin/bash
date=$(date +%Y%m%d)
tar czf backups/alpha_quant_${date}.tar.gz \
    reports/ strategies/ logs/ signals/
```

### 监控告警
```python
# 关键指标监控
if daily_drawdown > 0.05:  # 单日回撤超5%
    notifier.critical("单日回撤超限", f"当前回撤: {daily_drawdown}")
```

---

## 快速排查清单

| 问题 | 排查步骤 |
|------|---------|
| 数据获取失败 | ① 检查网络 ② 检查API Token ③ 查看数据源状态 |
| 信号未推送 | ① 检查飞书Webhook ② 检查信号服务器状态 ③ 查看日志 |
| PTrade连接失败 | ① 确认PTrade已启动 ② 检查端口 ③ 检查防火墙 |
| 定时任务未执行 | ① 检查是否交易日 ② 检查调度器状态 ③ 查看cron日志 |
| 内存占用过高 | ① 检查缓存大小 ② 重启服务 ③ 优化数据加载逻辑 |

---

## 获取帮助

1. **查看日志**: `tail -f logs/gateway_$(date +%Y-%m-%d).log`
2. **健康检查**: `python health_checker.py`
3. **重启服务**: `supervisorctl restart all`
4. **查看状态**: `python -c "from modules.trade_calendar import get_calendar; print(get_calendar().get_market_phase())"`
