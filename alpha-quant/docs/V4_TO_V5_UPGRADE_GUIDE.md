# Alpha V4.0 → V5.0 升级部署指南

## 概述

本文档描述从Alpha V4.0升级到V5.0的完整部署路径，包含7个阶段，预计10周完成。

## 升级前准备

### 1. 代码备份
```bash
cd /root/.openclaw/workspace/alpha-quant
git tag v4.0-stable
git push origin v4.0-stable
```

### 2. 数据备份
```bash
# 备份配置文件
cp config.json config.json.v4.0.backup

# 备份历史数据
cp -r data/ data-backup-v4.0/
cp -r logs/ logs-backup-v4.0/

# 备份模型文件
cp -r models/ models-backup-v4.0/
```

### 3. 安装新依赖
```bash
# 激活虚拟环境
source quant_env/bin/activate

# 安装V5.0新增依赖
pip install optuna>=3.4.0 beautifulsoup4>=4.12.0 newspaper3k>=0.2.8 jieba>=0.42.1

# 可选：安装高级DRL依赖
# pip install stable-baselines3>=2.1.0 gymnasium>=0.29.0
```

## 分阶段部署计划

### 阶段1（第1周）：环境准备

**目标**：搭建V5.0基础环境，验证数据流

**任务清单**：
- [ ] 安装新依赖
- [ ] 备份V4.0全量配置和数据
- [ ] 创建新模块目录结构
- [ ] 部署sentiment_pipeline.py（先跑通数据采集）

**验证标准**：
```python
from modules.sentiment_pipeline import create_sentiment_pipeline
sentiment = create_sentiment_pipeline()
result = sentiment.analyze_text("宁德时代业绩超预期")
print(result)  # 应输出情绪分数
```

**回滚方案**：
```bash
# 如出现问题，恢复V4.0
git checkout v4.0-stable
pip install -r requirements.txt.v4.0
```

---

### 阶段2（第2周）：核心模块

**目标**：部署DRL、优化器、券商接口、OMS

**任务清单**：
- [ ] 部署drl_portfolio_agent.py（开始首次训练）
- [ ] 部署portfolio_optimizer.py（验证约束逻辑）
- [ ] 部署broker_integration.py（纸面交易模式）
- [ ] 部署oms.py

**DRL首次训练**：
```python
from modules.drl_portfolio_agent import create_drl_agent

drl = create_drl_agent()
results = drl.train_episode(n_episodes=100)

# 检查收敛性
import numpy as np
recent_rewards = [r['total_reward'] for r in results[-20:]]
if np.mean(recent_rewards) > 0:
    print("✅ DRL模型收敛")
else:
    print("⚠️ DRL模型未收敛，继续训练")
```

**优化器约束验证**：
```python
from modules.portfolio_optimizer import create_portfolio_optimizer

opt = create_portfolio_optimizer()
# 验证A股约束
assert opt.constraints['single_stock_max_pct'] == 0.10
assert opt.constraints['sector_max_pct'] == 0.30
```

**回滚方案**：
```json
// config.json 中临时关闭新模块
{
  "drl_portfolio": {"enabled": false},
  "portfolio_optimizer": {"enabled": false}
}
```

---

### 阶段3（第3周）：看板升级

**目标**：替换V1.0为V2.0，测试全部功能

**任务清单**：
- [ ] 替换看板V1.0为V2.0
- [ ] 测试全部9个面板
- [ ] 验证交易操作UI（纸面模式）
- [ ] 测试券商连接指示器

**部署步骤**：
```bash
# 1. 复制看板文件
cp static/dashboard_v2_full.html templates/alpha_dashboard_v2.html

# 2. 启动信号服务器
python signal_server.py

# 3. 测试访问
curl http://localhost:8765/dashboard
curl http://localhost:8765/api/v2/overview
```

**面板测试清单**：
- [ ] 📈 总览面板 - 三大指数、市场全景
- [ ] 💼 持仓面板 - 持仓明细、板块分布
- [ ] 📡 信号面板 - 信号队列、确认/拒绝
- [ ] 🤖 Agent面板 - 8 Agent状态
- [ ] 🧠 策略面板 - 5策略绩效
- [ ] 📊 组合分析面板 - 绩效归因、滚动Sharpe
- [ ] 📰 舆情面板 - 情绪网格、新闻流
- [ ] 🧬 DRL面板 - 训练进度、权重建议
- [ ] ⚠️ 风险面板 - VaR、压力测试、交易操作

**回滚方案**：
```bash
# 恢复V1.0看板
git checkout v4.0-stable -- dashboard.py templates/
```

---

### 阶段4（第4周）：学习系统

**目标**：部署持续学习、异常检测、A/B测试

**任务清单**：
- [ ] 部署continuous_learning.py
- [ ] 部署anomaly_detector.py
- [ ] 启用在线学习管道（日终自动重训）
- [ ] 配置A/B测试框架

**验证持续学习**：
```python
from modules.continuous_learning import create_continuous_learning_system

cls = create_continuous_learning_system()

# 模拟日终数据
trades = [
    {"pnl": 1000, "strategy": "momentum", "entry_features": [0.1, 0.2, 0.3]},
    {"pnl": -500, "strategy": "value", "entry_features": [0.2, 0.1, 0.4]},
]
import numpy as np
returns = np.random.randn(30, 5) * 0.02

# 执行日终学习
result = cls.daily_routine(trades, returns)
print(f"学习完成: {result['samples_collected']}条样本")
```

**配置Cron定时任务**：
```bash
# 日终学习（每天15:30）
0 30 15 * * * cd /root/.openclaw/workspace/alpha-quant && ./quant_env/bin/python -c "from modules.continuous_learning import create_continuous_learning_system; cls = create_continuous_learning_system(); cls.daily_routine([], np.array([]))"

# 异常检测（每小时）
0 0 * * * * cd /root/.openclaw/workspace/alpha-quant && ./quant_env/bin/python -c "from modules.continuous_learning import create_continuous_learning_system; cls = create_continuous_learning_system(); cls.anomaly_detector.detect(np.random.randn(5, 10))"
```

---

### 阶段5（第5-8周）：纸面验证

**目标**：全系统纸面交易运行4周，验证稳定性

**监控指标**：

| 指标 | 目标值 | 检查频率 |
|------|--------|----------|
| DRL收敛性 | 损失<0.1 | 每日 |
| 情绪信号准确率 | >60% | 每周 |
| Agent协作流畅度 | 无超时 | 每日 |
| OMS订单成功率 | >95% | 每日 |
| 看板响应时间 | <500ms | 每日 |

**每周复盘清单**：
- [ ] DRL训练曲线是否正常
- [ ] 情绪信号与价格走势是否匹配
- [ ] Agent之间信号传递是否延迟
- [ ] OMS滑点是否在合理范围(<5bps)
- [ ] 异常检测是否误报

**V5.0 vs V4.0回测对比**：
```python
# 运行回测对比
python backtest_engine.py --strategy v5.0_combined --period 2024-01-01_2024-12-31
python backtest_engine.py --strategy v4.0_baseline --period 2024-01-01_2024-12-31

# 对比指标
# - 年化收益率
# - 夏普比率
# - 最大回撤
# - 胜率
```

**通过标准**：
- V5.0夏普比率 > V4.0夏普比率
- V5.0最大回撤 < V4.0最大回撤
- 连续4周无重大故障

---

### 阶段6（第9周）：实盘上线

**目标**：逐步实盘，从10%资金开始

**资金配置计划**：

| 周次 | 资金比例 | Guard熔断阈值 | 监控强度 |
|------|----------|---------------|----------|
| 第1周 | 10% | V4.0的50% | 每日审查 |
| 第2周 | 10% | V4.0的50% | 每日审查 |
| 第3周 | 25% | V4.0的70% | 每日审查 |
| 第4周 | 50% | V4.0的100% | 每周审查 |
| 第5周+ | 100% | V4.0的100% | 每周审查 |

**每日审查清单**：
- [ ] 当日所有交易记录
- [ ] DRL置信度变化
- [ ] 情绪信号触发情况
- [ ] 滑点统计
- [ ] 异常告警

**紧急停止条件**：
- 单日亏损 > 5%
- 连续3日亏损
- DRL置信度连续<50%
- 异常检测触发红色警报

---

### 阶段7（第10周+）：持续优化

**目标**：根据实盘反馈调优

**优化方向**：
1. **DRL模型**：根据实盘表现调整奖励函数权重
2. **情绪数据源**：优化新浪/东财/微博的权重配比
3. **策略权重**：根据绩效归因调整5策略配比
4. **风控参数**：根据VaR实际值调整阈值

**建立长期跟踪库**：
```python
# 每日记录关键指标
performance_log = {
    "date": "2026-03-03",
    "daily_return": 0.015,
    "drl_confidence": 0.72,
    "sentiment_score": 0.35,
    "slippage_avg_bps": 3.2,
    "var_95": -1.8,
    "max_drawdown": -5.8,
    "strategy_attribution": {
        "momentum": 0.008,
        "value": 0.003,
        "sentiment": 0.005,
        "drl": 0.012
    }
}
```

---

## 回滚方案

### 模块级回滚（单模块关闭）

在 `config.json` 中设置 `"enabled": false`：

```json
{
  "drl_portfolio": {"enabled": false},
  "sentiment_analysis": {"enabled": false},
  "portfolio_optimizer": {"enabled": false},
  "continuous_learning": {"enabled": false}
}
```

### 全量回滚（恢复V4.0）

```bash
# 1. 停止服务
pkill -f signal_server.py

# 2. 恢复代码
git checkout v4.0-stable

# 3. 恢复配置
cp config.json.v4.0.backup config.json

# 4. 恢复依赖
pip install -r requirements.txt.v4.0

# 5. 重启服务
python signal_server.py

# 总耗时 < 5分钟
```

---

## 附录：配置文件模板

### V5.0完整配置

详见 `config.json`，已包含所有V5.0模块配置。

### 关键配置项说明

| 配置项 | 说明 | 建议值 |
|--------|------|--------|
| `drl_portfolio.enabled` | DRL模块开关 | 阶段2后设为true |
| `sentiment_analysis.enabled` | 舆情模块开关 | 阶段1后设为true |
| `portfolio_optimizer.method` | 优化算法 | black-litterman |
| `broker_integration.oms.max_retry_attempts` | 订单重试次数 | 3 |
| `continuous_learning.anomaly_detection.enabled` | 异常检测开关 | 阶段4后设为true |

---

## 总结

V5.0升级是一个渐进过程，通过7个阶段、10周时间，从环境准备到实盘上线，每一步都有明确的验证标准和回滚方案。确保系统稳定性是首要目标，切勿急于求成。

**关键原则**：
1. 先纸面，后实盘
2. 小资金，逐步加
3. 有问题，立即回滚
4. 持续监控，每周复盘
