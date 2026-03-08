# Alpha V6.0 策略进化引擎 - 集成文档

## 概述

Alpha V6.0 (代号: Alpha-Genesis) 引入了**策略进化引擎**，基于遗传算法实现策略的自动进化。系统将交易策略编码为"DNA"，通过自然选择、交叉繁殖、随机变异，让策略在历史数据压力下自动进化。

## 核心特性

- 🧬 **策略种群**: 维护100个并行策略，按适应度竞争生存
- 🔄 **基因进化**: 每日自动运行一代进化（交叉+变异+淘汰）
- ⚰️ **策略墓地**: 低分策略不删除，存入墓地供条件触发复活
- 🏆 **名人堂**: 保存历史最优策略Top5，随时可调用实盘

## 文件结构

```
alpha-quant/
├── strategy_evolution_engine.py    # 进化引擎核心
├── evolution_integration.py        # V5.0系统集成层
├── cron_evolution.py               # 每日进化定时任务
└── config.json                     # 已添加V6.0配置
```

## 快速开始

### 1. 初始化进化引擎

```python
from evolution_integration import AlphaV6Integration

# 创建集成实例
integration = AlphaV6Integration("config.json")

# 初始化种群
integration.initialize()
```

### 2. 运行每日进化

```python
import pandas as pd

# 获取市场数据
data = pd.read_csv("market_data.csv")

# 执行进化
result = integration.daily_evolution(data)
print(f"第{result['generation']}代进化完成")
```

### 3. 获取交易信号

```python
# 获取进化策略生成的信号
signals = integration.get_trading_signals(market_data)

for sig in signals:
    print(f"{sig['strategy_id']}: {sig['signal']} (置信度: {sig['confidence']:.2f})")
```

### 4. 查看进化状态

```python
# 获取看板数据
dashboard = integration.get_dashboard_data()

print(f"当前代数: {dashboard['evolution_status']['generation']}")
print(f"名人堂策略数: {dashboard['evolution_status']['hall_of_fame_size']}")
print(f"活跃策略数: {dashboard['evolution_status']['active_strategies']}")
```

## 配置说明

在 `config.json` 中添加以下配置：

```json
{
  "strategy_evolution": {
    "enabled": true,
    "population_capacity": 100,           // 种群容量
    "seed_count_per_type": 10,            // 每种策略类型的种子数
    "evolution_frequency_hours": 24,      // 进化频率
    "crossover_ratio": 0.7,               // 交叉比例
    "mutation_rate": 0.15,                // 变异率
    "tournament_size": 5,                 // 锦标赛选择大小
    "backtest_days": 60,                  // 回测天数
    "min_trades": 10,                     // 最小交易次数
    "hall_of_fame_size": 5,               // 名人堂大小
    "signal_weights": {                   // 信号权重
      "best_strategy": 0.4,
      "hall_of_fame_vote": 0.35,
      "top_active": 0.25
    },
    "schedule": {
      "daily_evolution_time": "15:35",    // 每日进化时间（收盘后）
      "save_checkpoint": true
    }
  }
}
```

## 定时任务设置

添加每日进化任务到 crontab：

```bash
# 编辑 crontab
crontab -e

# 添加每日15:35运行进化（收盘后）
35 15 * * * cd /root/.openclaw/workspace/alpha-quant && python3 cron_evolution.py >> logs/evolution_cron.log 2>&1
```

## 与现有系统集成

### 信号总线集成

进化引擎生成的信号自动接入现有信号系统，优先级如下：

1. **最优策略信号** (priority=1): 当前适应度最高的策略
2. **名人堂投票信号** (priority=2): 名人堂Top5策略投票结果
3. **活跃池Top5信号** (priority=3-7): 活跃池中表现最好的5个策略

### 看板集成

在看板V3.0中新增以下面板：

- **进化状态面板**: 显示当前代数、活跃策略数、名人堂
- **名人堂榜单**: Top5策略的适应度和类型
- **策略分布图**: 按策略类型的分布
- **进化历史曲线**: 适应度随代数变化

### 回测引擎集成

进化引擎自动使用现有的 `backtest_engine.py` 进行适应度评估：

```python
from evolution_integration import EvolutionBacktestBridge
from backtest_engine import BacktestEngine

# 创建桥接器
bridge = EvolutionBacktestBridge(BacktestEngine())

# 评估策略DNA
metrics = bridge.evaluate_dna(dna, market_data)
```

## 策略类型

当前支持三种策略类型：

### 1. 动量策略 (momentum)

```python
params = {
    "lookback_period": 20,      // 回看周期
    "buy_threshold": 0.05,      // 买入阈值
    "sell_threshold": -0.03,    // 卖出阈值
    "vol_filter": 0.3,          // 波动率过滤
    "rsi_oversell": 30,         // RSI超卖线
    "ma_fast": 5,               // 快均线
    "ma_slow": 20,              // 慢均线
    "position_size": 0.1        // 仓位比例
}
```

### 2. 均值回归策略 (mean_reversion)

```python
params = {
    "bb_period": 20,            // 布林带周期
    "bb_std": 2.0,              // 布林带标准差倍数
    "rsi_period": 14,           // RSI周期
    "rsi_low": 30,              // RSI超卖
    "rsi_high": 70,             // RSI超买
    "mean_period": 60,          // 均值回归基准周期
    "deviation_threshold": 0.08,// 偏离阈值
    "position_size": 0.08
}
```

### 3. ML集成策略 (ml_ensemble)

```python
params = {
    "n_estimators": 100,        // 集成树数量
    "max_depth": 5,             // 树深度
    "feature_lookback": 30,     // 特征回看周期
    "confidence_threshold": 0.6,// 置信度阈值
    "retrain_freq_days": 30,    // 重训练频率
    "position_size": 0.12
}
```

## 适应度函数

策略适应度计算公式：

```
Fitness = Sharpe×0.4 + AnnualReturn×0.3 + WinRate×0.2 - MaxDrawdown×0.1
```

剔除条件：交易次数 < 10

## 进化算法流程

1. **选择**: 锦标赛选择（随机选5个，取最优，重复10次）
2. **交叉**: 70%的后代通过交叉产生（均匀交叉）
3. **变异**: 30%的后代通过变异产生（高斯扰动）
4. **淘汰**: 按适应度排序，保留前100名
5. **墓地**: 淘汰者进入墓地（最多保留500个）
6. **名人堂**: 更新Top5策略

## API参考

### StrategyDNA

```python
# 创建种子
dna = StrategyDNA.create_seed("momentum")

# 变异
mutated = dna.mutate(mutation_rate=0.15)

# 交叉
child = dna1.crossover(dna2)
```

### StrategyPopulation

```python
pop = StrategyPopulation(capacity=100)

# 初始化
pop.initialize(seed_count_per_type=10)

# 评估适应度
pop.evaluate_fitness(dna, metrics)

# 执行进化
pop.evolve(crossover_ratio=0.7)

# 复活策略
pop.revive(strategy_id)

# 获取最优
best = pop.get_best()
```

### AlphaV6Integration

```python
integration = AlphaV6Integration("config.json")

# 初始化
integration.initialize()

# 每日进化
result = integration.daily_evolution(market_data)

# 获取信号
signals = integration.get_trading_signals(market_data)

# 看板数据
data = integration.get_dashboard_data()

# 导出最优策略
best = integration.export_best_strategy()
```

## 监控与调试

### 日志输出

进化引擎会输出详细日志：

```
2026-03-06 15:35:00 | INFO | 种群初始化完成，共 30 个策略
2026-03-06 15:35:01 | INFO | 第1代进化完成 | 活跃:100 | 墓地:0 | 名人堂:5
2026-03-06 15:35:02 | INFO | 最优策略: a43a66ce (momentum, 适应度: 18.60)
```

### 状态检查

```python
# 检查种群状态
pop = integration.evolution.population
print(f"活跃: {len(pop.active)}, 墓地: {len(pop.graveyard)}, 名人堂: {len(pop.hall_of_fame)}")

# 查看名人堂
for dna in pop.hall_of_fame:
    print(f"{dna.id}: {dna.strategy_type} (fitness: {dna.fitness_score:.2f})")
```

## 故障排除

### 1. 进化停滞

如果适应度长期不提升：
- 增加变异率 `mutation_rate: 0.2`
- 检查回测数据质量
- 增加种群容量

### 2. 策略过于相似

如果种群多样性不足：
- 增加种子数量 `seed_count_per_type: 15`
- 提高交叉比例 `crossover_ratio: 0.8`

### 3. 回测太慢

- 减少回测天数 `backtest_days: 30`
- 使用简化回测模式
- 并行评估（待实现）

## 后续计划

V6.0其他模块待集成：

- [ ] 聚宽数据网关
- [ ] 专业投研报告生成器
- [ ] 历史知识库
- [ ] 智能券商管理器 V2
- [ ] Alpha 看板 V3.0
- [ ] DRL 引擎增强（Transformer）
- [ ] 舆情分析增强（事件驱动）
- [ ] 组合优化增强（政权自适应）

---

**版本**: 6.0 (Alpha-Genesis)  
**最后更新**: 2026-03-06
