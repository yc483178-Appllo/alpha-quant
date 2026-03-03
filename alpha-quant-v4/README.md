# Alpha Quant v4.0 - Multi-Agent 量化交易系统

## 🎯 系统概述

Alpha Quant v4.0 是一个基于 Multi-Agent 架构的量化交易系统，通过6个专业Agent协作完成从市场侦察、选股、风控到交易执行的全流程自动化。

## 🤖 Agent 团队

| Agent | 角色 | 职责 |
|-------|------|------|
| **Alpha-Chief** | 首席策略官 | 总协调、决策审批、冲突仲裁 |
| **Alpha-Scout** | 市场情报员 | 盘前侦察、舆情监控、异动预警 |
| **Alpha-Picker** | 量化选股师 | 多策略选股、因子分析、信号生成 |
| **Alpha-Guard** | 风控总监 | 五维风控、一票否决、紧急熔断 |
| **Alpha-Trader** | 交易执行员 | 委托执行、成交确认、滑点控制 |
| **Alpha-Review** | 复盘分析师 | 每日复盘、策略评估、知识积累 |

### 自然语言下单

```bash
# 启动Trader并测试自然语言解析
python main.py --agent trader

# 支持的指令格式：
# - "买入5万块招商银行"
# - "600036买入1000股，限价35元"
# - "卖掉一半平安银行"
# - "清仓所有持仓"
```

## 📁 项目结构

```
alpha-quant-v4/
├── agents/                 # Agent 实现
│   ├── alpha_chief.py     # 首席策略官
│   ├── alpha_scout.py     # 市场情报员
│   ├── alpha_picker.py    # 量化选股师
│   ├── alpha_guard.py     # 风控总监
│   ├── alpha_trader.py    # 交易执行员
│   └── alpha_review.py    # 复盘分析师
├── core/                  # 核心模块
│   ├── agent_bus.py       # Agent 通信总线
│   ├── agent_scheduler.py # 协作调度器
│   ├── adaptive_strategy.py   # 自适应策略切换
│   ├── multi_timeframe.py     # 多时间框架确认
│   ├── ml_factor_engine.py    # ML因子合成
│   ├── sentiment_cycle.py     # 情绪周期模型
│   ├── nl_order_parser.py     # 自然语言下单解析
│   ├── strategy_evolution.py  # 策略自进化引擎
│   └── knowledge_base.py      # 交易知识库
├── config/                # 配置文件
├── data/                  # 数据存储
├── models/                # ML模型存储
├── executors/             # 交易执行器
├── strategies/            # 策略目录
├── logs/                  # 日志目录
├── main.py                # 主入口
├── requirements.txt       # 依赖清单
└── .env                   # 环境变量
```

## 🚀 快速启动

### 1. 安装依赖

```bash
cd alpha-quant-v4
pip install -r requirements.txt
```

### 2. 配置环境变量

编辑 `.env` 文件：
```bash
# 数据源 Token
TUSHARE_TOKEN=your_token_here

# Redis
REDIS_URL=redis://127.0.0.1:6379/0

# 飞书通知
FEISHU_WEBHOOK_URL=https://open.feishu.cn/open-apis/bot/v2/hook/xxx
FEISHU_SECRET=your_secret
```

### 3. 启动系统

```bash
# 完整系统启动
python main.py

# 单独启动调度器
python main.py --agent scheduler

# 单独测试某个Agent
python main.py --agent scout
python main.py --agent picker
python main.py --agent guard
```

## 📅 每日工作流程

```
08:45  Chief    系统启动与健康检查
08:50  Scout    盘前市场全景调研
09:10  Picker   多策略选股
09:20  Guard    开盘前风控预检
09:25  Chief    审批并签发交易指令
09:30  Market   开盘
09:30-15:00  Guard 盘中每30分钟风控检查
15:10  Review   收盘复盘
15:30  Chief    日终Agent会议

周五 16:00  Review 周度策略大阅兵
```

## 🔧 核心功能

### 知识库累积
结构化存储交易知识，支持检索：
- **pattern**: 市场规律（如"LPR下调后银行股3日反弹"）
- **rule**: 交易铁律（如"连板股竞价低于-3%必须放弃"）
- **lesson**: 教训总结（如"追高龙头的亏损记录"）
- **insight**: 策略洞察（如"震荡市value策略胜率最高"）

### 策略自进化
每周自动评估策略表现，根据夏普比率、胜率、回撤等指标自动标记/降级/淘汰弱策略：
- 健康策略：保持当前参数
- 警告策略：微调相关参数
- 严重策略：暂停并深度回测

### 启动数据看板

```bash
# 启动Web看板（默认端口8080）
python dashboard.py

# 访问 http://localhost:8080 查看实时数据
```

看板功能：
- 实时大盘指数（上证/深证/创业板/科创50）
- Agent状态监控
- WebSocket实时推送
- 暗色主题UI

### 自然语言交易
支持自然语言下达交易指令：
- "买入5万块招商银行" → 自动计算股数
- "600036买入1000股，限价35元" → 精确控制
- "卖掉一半平安银行" → 智能减仓
- "清仓所有持仓" → 一键清仓

Trader Agent会自动解析并提交Chief审批。

### 自适应策略切换
根据市场环境（牛市/熊市/震荡）自动切换最优策略组合：
- 牛市：动量+趋势，仓位上限80%
- 熊市：价值+超跌，仓位上限40%
- 震荡：综合策略，仓位上限60%

### 多时间框架确认
日线 + 60分钟 + 15分钟三重信号共振，大幅降低假信号。

### 机器学习因子合成
使用随机森林/GBDT对多因子进行权重优化，替代手动设定权重。

### 情绪周期四阶段模型
冰点期 → 回暖期 → 高潮期 → 退潮期，指导仓位和策略选择。

## 🛡️ 五维风控体系

1. **个股风控**：止损线8%、止盈线20%、单股仓位上限20%
2. **账户风控**：单日亏损上限2%、总仓位上限80%
3. **市场风控**：大盘跌2%熔断、跌3%超级熔断
4. **板块风控**：同板块仓位上限40%
5. **系统风控**：数据延迟>30秒暂停交易

## 📊 信号总线频道

| 频道 | 用途 | 流向 |
|------|------|------|
| `alpha:intel` | 市场情报 | Scout → Chief |
| `alpha:signals` | 选股信号 | Picker → Chief |
| `alpha:risk` | 风控预警 | Guard → Chief |
| `alpha:orders` | 交易指令 | Chief → Trader |
| `alpha:trades` | 成交回报 | Trader → Review |
| `alpha:review` | 复盘报告 | Review → Chief |
| `alpha:emergency` | 紧急广播 | 任意Agent → 全体 |

## 📝 配置说明

### 系统配置 (`config/system.json`)

```json
{
  "agents": {
    "chief": { "enabled": true },
    "scout": { "enabled": true },
    "picker": { "enabled": true },
    "guard": { "enabled": true },
    "trader": { "enabled": true },
    "review": { "enabled": true }
  },
  "risk": {
    "stop_loss_pct": 0.08,
    "take_profit_pct": 0.20,
    "max_position_pct": 0.20
  }
}
```

## 🔍 日志查看

```bash
# 实时查看日志
tail -f logs/alpha_v4_YYYY-MM-DD.log

# 查看Agent通信日志
tail -f logs/agent_bus_YYYY-MM-DD.log
```

## ⚠️ 注意事项

1. **Redis 必需**：系统依赖 Redis 进行 Agent 间通信
2. **Tushare Token**：需要有效的 Tushare Pro 会员 Token
3. **交易模式**：默认模拟交易，实盘需配置券商API
4. **风险提示**：量化交易有风险，请充分测试后再实盘

## 📄 License

MIT License

## 🙏 致谢

- 数据源：Tushare、AkShare、Baostock
- 消息队列：Redis
- 机器学习：scikit-learn
