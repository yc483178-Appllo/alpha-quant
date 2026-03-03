# Alpha V5.0 Chief Agent 集成文档

## 概述

Chief Agent V5.0是Alpha量化交易系统的核心决策引擎，整合DRL建议、组合优化、风控检查，输出最终交易决策。

## 架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                     Chief Agent V5.0                            │
├─────────────────────────────────────────────────────────────────┤
│  输入层                                                          │
│  ├── Scout盘前报告 (market_regime, index_data, risk_signals)    │
│  ├── Sentiment舆情报告 (sentiment_score, sector_sentiment)      │
│  └── Picker选股清单 (selected_stocks, scores)                   │
├─────────────────────────────────────────────────────────────────┤
│  决策层                                                          │
│  ├── DRL Agent → 组合权重建议 + 置信度                          │
│  ├── Portfolio Optimizer → 优化权重建议                         │
│  └── Guard → 风控预检结果                                       │
├─────────────────────────────────────────────────────────────────┤
│  综合决策                                                        │
│  ├── DRL置信度 > 0.7 + Guard通过 → 采纳DRL                      │
│  ├── DRL置信度 < 0.5 → 使用Optimizer                            │
│  └── 冲突 → 取保守方案（仓位较低者）                            │
├─────────────────────────────────────────────────────────────────┤
│  输出层                                                          │
│  └── 交易执行计划 → Trader                                      │
└─────────────────────────────────────────────────────────────────┘
```

## 决策规则详解

### 规则1: DRL高置信度优先
```python
if drl.confidence > 0.7 and guard.passed:
    采纳DRL权重建议
```

### 规则2: DRL低置信度降级
```python
if drl.confidence < 0.5:
    使用Portfolio Optimizer建议
```

### 规则3: 冲突时保守策略
```python
if 两者冲突:
    取仓位较低的方案
```

### 规则4: Guard风控干预
```python
if risk_level in ["high", "critical"]:
    降低整体仓位至60%-80%
if risk_level == "critical":
    可能阻止交易
```

## 快速开始

### 1. 基础使用

```python
from modules.chief_agent import create_chief_agent, ScoutReport, SentimentReport, PickerList

# 创建Chief Agent
chief = create_chief_agent("config.json")

# 准备输入数据
scout = ScoutReport(
    market_regime="neutral",  # bear/bull/neutral
    index_data={"上证指数": {"close": 3300, "change_pct": 0.25}},
    sector_hotspot=[],
    risk_signals=[],
    timestamp=datetime.now().isoformat()
)

sentiment = SentimentReport(
    overall_sentiment=0.15,  # -1 to 1
    sector_sentiment={"新能源": 0.35},
    hot_topics=[],
    risk_alerts=[],
    timestamp=datetime.now().isoformat()
)

picker = PickerList(
    selected_stocks=[
        {"ts_code": "300014.SZ", "name": "亿纬锂能", "score": 85},
        {"ts_code": "300750.SZ", "name": "宁德时代", "score": 88},
    ],
    selection_reason="动量选股",
    timestamp=datetime.now().isoformat()
)

# 执行决策
decision = chief.make_decision(scout, sentiment, picker)

# 获取结果
print(f"决策来源: {decision.decision_source}")
print(f"置信度: {decision.confidence}")
print(f"风险等级: {decision.risk_level}")
print(f"执行计划: {len(decision.execution_plan)}笔交易")
```

### 2. 生成交易信号

```python
# 生成给Trader的信号
trade_signals = chief.generate_signal_for_trader(decision)

for signal in trade_signals:
    print(f"{signal['code']}: {signal['action']}")
    # 发送到signal_server
    # requests.post("http://localhost:8765/api/signals", json=signal)
```

### 3. 使用Agent Bus协调

```python
from modules.agent_bus import create_agent_bus, create_agent_coordinator

# 创建Agent Bus
bus = create_agent_bus()
coordinator = create_agent_coordinator(bus)

# 注册Agent
coordinator.register_agent("Chief")
coordinator.register_agent("DRL")
coordinator.register_agent("Guard")

# 协调盘前决策流程
decision = coordinator.coordinate_premarket_flow(
    chief_agent=chief,
    scout_data={...},
    sentiment_data={...},
    picker_data={...}
)
```

## 配置说明

### config.json

```json
{
  "drl_portfolio": {
    "enabled": true,
    "model_save_path": "./models/drl_portfolio.npz",
    "max_positions": 30,
    "initial_cash": 1000000,
    "transaction_cost": 0.001,
    "hidden_size": 128,
    "learning_rate": 0.0003
  }
}
```

### 决策阈值配置

```python
# chief_agent.py 中的阈值
thresholds = {
    "drl_high_confidence": 0.7,    # DRL高置信度阈值
    "drl_low_confidence": 0.5,      # DRL低置信度阈值
    "max_single_position": 0.20,    # 单股最大仓位
    "max_total_position": 0.80,     # 总最大仓位
    "risk_conservative_factor": 0.8  # 高风险时仓位折扣
}
```

## 演示脚本

### 完整流程演示
```bash
cd /root/.openclaw/workspace/alpha-quant
python3 chief_integration_demo.py --mode full
```

### 特定场景演示
```bash
# DRL高置信度场景
python3 chief_integration_demo.py --mode high

# DRL低置信度场景
python3 chief_integration_demo.py --mode low

# 冲突解决场景
python3 chief_integration_demo.py --mode conflict

# Guard风控干预场景
python3 chief_integration_demo.py --mode guard

# 所有场景
python3 chief_integration_demo.py --mode all
```

## 集成文件清单

| 文件 | 说明 |
|------|------|
| `modules/chief_agent.py` | Chief Agent核心实现 |
| `modules/agent_bus.py` | Agent Bus信号总线 |
| `modules/drl_portfolio_agent.py` | DRL投资组合引擎 |
| `chief_integration_demo.py` | 集成演示脚本 |
| `config.json` | 配置文件（已更新） |

## 下一步

1. **接入真实数据源**: 将mock数据替换为data_provider获取的实时数据
2. **实现Portfolio Optimizer**: 接入Black-Litterman或风险平价模型
3. **完善Guard规则**: 添加更多风控检查项
4. **接入Trader执行**: 将信号发送到signal_server执行
