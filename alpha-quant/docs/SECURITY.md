# 系统安全最佳实践指南

## 🔐 核心安全原则

> **安全不是可选项，是量化系统的生命线。**

---

## 1. 密钥管理

### ✅ 已实现

#### 环境变量隔离
```bash
# .env 文件 - 所有敏感信息集中管理
TUSHARE_TOKEN=sk-xxxx...
THS_ACCOUNT=grsyzh1006
THS_PASSWORD=NANbF9Sk
FEISHU_WEBHOOK_URL=https://open.feishu.cn/...
```

#### .gitignore 保护
```gitignore
# .gitignore
.env
.env.local
.env.*.local
*.log
__pycache__/
*.pyc
.DS_Store
```

#### 代码中安全读取
```python
# 正确做法 ✅
from dotenv import load_dotenv
load_dotenv()
token = os.getenv("TUSHARE_TOKEN")

# 错误做法 ❌
token = "sk-xxxx..."  # 永远不要硬编码！
```

### 检查清单
- [x] 所有 API Token 存储在 .env
- [x] .env 已加入 .gitignore
- [x] 代码中无硬编码密钥
- [x] 密钥定期轮换（建议每90天）

---

## 2. 交易安全

### ✅ 已实现

#### 人工确认机制
```python
# signal_server.py
CONFIG = {
    "require_human_confirm": True,  # 实盘必须保持 True
    "signal_timeout_seconds": 60,
    "max_pending_signals": 10
}
```

#### 仓位控制
```python
# ptrade_executor.py
RISK_LIMITS = {
    "max_single_position": 0.05,    # 单票最多 5%
    "max_total_position": 0.80,     # 总仓位最多 80%
    "max_daily_loss": 0.02          # 单日最大亏损 2%
}
```

#### 每日亏损阈值监控
```python
# risk_monitor.py
def check_daily_loss_limit(account):
    daily_pnl = account.get_daily_pnl()
    if daily_pnl < -0.02:  # 亏损超过2%
        notifier.critical(
            "每日亏损阈值触发",
            f"当前亏损: {daily_pnl:.2%}，系统已暂停"
        )
        account.pause_trading()  # 自动暂停
        return False
    return True
```

### 检查清单
- [x] require_human_confirm = True
- [x] 单票仓位限制 5%
- [x] 总仓位限制 80%
- [x] 每日亏损阈值 2%
- [ ] 实盘/测试账户隔离（需用户配置）

---

## 3. 审计与监控

### ✅ 已实现

#### 完整操作日志
```python
# 所有关键操作记录
logger.info(f"信号创建: #{signal_id} {action} {code} @ {price}")
logger.info(f"订单执行: {order_id} 状态: {status}")
logger.info(f"风控触发: {risk_level} {reason}")
```

#### 日志归档
```python
# cloud_storage.py 自动归档
storage.archive_log(log_content, date="2026-02-27")
# 保存到: cloud_storage/Logs/2026-02-27.log
```

#### 每周审计检查表
```bash
# audit_checklist.sh
#!/bin/bash
echo "=== Alpha Quant 周度审计 ==="
echo "1. 检查异常交易..."
grep "ERROR\|CRITICAL" logs/signal_*.log | tail -20

echo "2. 检查风控触发..."
grep "风控触发" logs/*.log | wc -l

echo "3. 检查盈亏情况..."
python -c "from modules.cloud_storage import CloudStorage; \
           s = CloudStorage(); \
           print(f'本周报告: {len(list(s.base_path/\"Reports/Daily\".glob(\"*.md\")))} 份')"

echo "4. 检查数据源稳定性..."
grep "数据源.*失败" logs/gateway_*.log | tail -10
```

### 检查清单
- [x] 所有操作记录日志
- [x] 日志自动归档
- [ ] 每周人工审计（需用户执行）

---

## 4. 环境隔离

### ⚠️ 待配置

#### 账户隔离策略
```python
# config.py
ENVIRONMENT = os.getenv("ALPHA_ENV", "paper")  # paper / live

if ENVIRONMENT == "paper":
    # 模拟盘配置
    EXECUTOR = "simulation"
    INITIAL_CAPITAL = 1000000
    COMMISSION = 0.00025
elif ENVIRONMENT == "live":
    # 实盘配置
    EXECUTOR = "ptrade"  # 或 "qmt"
    REQUIRE_CONFIRM = True  # 强制人工确认
    MAX_POSITION = 0.05     # 严格仓位控制
```

#### 策略验证流程
```
新策略
  ↓
回测验证 (历史数据)
  ↓
模拟盘验证 (30交易日)
  ↓
小资金实盘 (5%仓位, 20交易日)
  ↓
逐步加仓 (10%仓位)
  ↓
正常仓位 (长期保持人工确认)
```

### 检查清单
- [ ] 设置 ALPHA_ENV 环境变量
- [ ] 模拟盘/实盘账户物理隔离
- [ ] 新策略必须经过完整验证流程

---

## 5. 系统防护

### ✅ 已实现

#### API 限流
```python
# data_gateway.py
@rate_limit(max_calls=30, period=60)  # 30次/分钟
def get_realtime():
    ...
```

#### 异常熔断
```python
# 连续错误自动熔断
error_count = 0
MAX_ERRORS = 5

def fetch_data():
    global error_count
    try:
        data = api.get_data()
        error_count = 0  # 成功重置
        return data
    except Exception as e:
        error_count += 1
        if error_count >= MAX_ERRORS:
            notifier.critical("数据获取连续失败", "已自动熔断")
            raise CircuitBreakerError("服务暂时不可用")
        raise
```

#### 依赖更新检查
```bash
# update_checker.sh
#!/bin/bash
echo "检查依赖更新..."
pip list --outdated | grep -E "akshare|tushare|flask"

echo "检查安全漏洞..."
pip audit  # 需要安装 pip-audit

echo "更新建议:"
echo "- AkShare: 关注东方财富接口变更公告"
echo "- Tushare: 关注版本更新日志"
echo "- Flask: 关注安全补丁"
```

### 检查清单
- [x] API 限流 30次/分钟
- [x] 错误熔断机制
- [ ] 定期依赖更新（建议每月）

---

## 6. 应急响应

### 紧急停止命令

```bash
# 一键停止所有交易
pkill -f signal_server
pkill -f data_gateway
tmux kill-session -t gateway
supervisorctl stop all
```

### 数据备份
```bash
# emergency_backup.sh
#!/bin/bash
BACKUP_DIR="emergency_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p $BACKUP_DIR

cp -r logs/ $BACKUP_DIR/
cp -r signals/ $BACKUP_DIR/
cp -r reports/ $BACKUP_DIR/
cp .env $BACKUP_DIR/

tar czf ${BACKUP_DIR}.tar.gz $BACKUP_DIR
echo "紧急备份完成: ${BACKUP_DIR}.tar.gz"
```

---

## 7. 安全配置检查脚本

```bash
#!/bin/bash
# security_audit.sh - 安全配置审计

echo "🔐 Alpha Quant 安全配置审计"
echo "=============================="

# 1. 检查 .env 文件权限
echo "1. 检查 .env 文件权限..."
if [ -f ".env" ]; then
    perms=$(stat -c "%a" .env)
    if [ "$perms" = "600" ]; then
        echo "✅ .env 权限正确 (600)"
    else
        echo "⚠️ .env 权限为 $perms，建议改为 600"
        chmod 600 .env
    fi
else
    echo "❌ .env 文件不存在"
fi

# 2. 检查 .gitignore
echo "2. 检查 .gitignore..."
if grep -q "\.env" .gitignore; then
    echo "✅ .env 已在 .gitignore 中"
else
    echo "❌ .env 未在 .gitignore 中"
fi

# 3. 检查硬编码密钥
echo "3. 检查硬编码密钥..."
if grep -r "sk-[a-zA-Z0-9]\{20,\}" --include="*.py" .; then
    echo "❌ 发现硬编码密钥！"
else
    echo "✅ 未发现硬编码密钥"
fi

# 4. 检查人工确认设置
echo "4. 检查人工确认设置..."
if grep -q "require_human_confirm.*=.*True" signal_server.py; then
    echo "✅ 人工确认已启用"
else
    echo "⚠️ 人工确认可能未启用"
fi

# 5. 检查日志记录
echo "5. 检查日志记录..."
if [ -d "logs" ] && [ "$(ls -A logs)" ]; then
    echo "✅ 日志目录正常"
else
    echo "⚠️ 日志目录为空或不存在"
fi

echo "=============================="
echo "审计完成"
```

---

## 8. 安全最佳实践总结

| 类别 | 措施 | 状态 | 优先级 |
|------|------|------|--------|
| 密钥管理 | .env 环境变量 | ✅ 已实施 | P0 |
| 密钥管理 | .gitignore 保护 | ✅ 已实施 | P0 |
| 交易安全 | 人工确认机制 | ✅ 已实施 | P0 |
| 交易安全 | 仓位控制 5% | ✅ 已实施 | P0 |
| 交易安全 | 每日亏损阈值 2% | ✅ 已实施 | P0 |
| 交易安全 | 实盘/测试隔离 | ⚠️ 需配置 | P1 |
| 审计监控 | 完整操作日志 | ✅ 已实施 | P1 |
| 审计监控 | 每周人工审计 | ⚠️ 需执行 | P1 |
| 系统防护 | API 限流 | ✅ 已实施 | P1 |
| 系统防护 | 依赖定期更新 | ⚠️ 需执行 | P2 |

---

## 9. 安全联系人

| 角色 | 职责 | 联系方式 |
|------|------|----------|
| 系统管理员 | 服务器/网络/安全 | - |
| 量化研究员 | 策略开发/回测 | - |
| 风控专员 | 风险监控/止损 | - |
| 券商对接人 | 交易通道/PTrade | - |

---

## 10. 安全事件响应流程

```
发现异常
  ↓
立即暂停交易（一键停止）
  ↓
保留现场（日志/数据备份）
  ↓
分析原因
  ├─ 代码bug → 修复 → 测试 → 恢复
  ├─ 数据异常 → 切换数据源 → 恢复
  ├─ 安全事件 → 更换密钥 → 审计 → 恢复
  └─ 外部攻击 → 断网 → 安全加固 → 恢复
  ↓
复盘总结 → 更新安全规范
```

---

**最后更新**: 2026-02-27  
**下次审计**: 建议每周执行一次安全审计
