# Alpha Quant - A股量化交易系统

## 🚀 快速开始

### 方法一：一键搭建（推荐）

```bash
cd alpha-quant
bash setup_env.sh
```

脚本会自动完成：
- ✅ 创建 Python 虚拟环境
- ✅ 安装所有依赖
- ✅ 验证安装结果
- ✅ 创建启动脚本

### 方法二：手动搭建

```bash
# Step 1: 创建虚拟环境
python3 -m venv quant_env
source quant_env/bin/activate

# Step 2: 安装依赖
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# Step 3: 验证安装
python3 -c "import akshare, tushare; print('✅ 安装成功')"
```

---

## 📋 使用说明

### 激活环境
```bash
source quant_env/bin/activate
```

### 运行命令

```bash
# 测试数据连接
./start_alpha.sh test

# 盘前分析（生成选股报告）
./start_alpha.sh premarket

# 盘中监控（检查风险）
./start_alpha.sh intraday

# 收盘复盘（生成日报）
./start_alpha.sh closing
```

或直接调用：
```bash
python3 alpha.py premarket
```

---

## ⚙️ 配置说明

### 1. 修改 Tushare Token

编辑 `config.py`：
```python
TUSHARE_TOKEN = "你的Token"
```

### 2. 调整风控参数

编辑 `config.py`：
```python
INITIAL_CAPITAL = 1_000_000      # 初始资金
MAX_POSITION_PER_STOCK = 0.20    # 单股最大仓位 20%
MAX_DAILY_LOSS = 0.02            # 单日最大亏损 2%
```

### 3. 设置关注板块

```python
FOCUS_SECTORS = [
    "新能源", "AI", "存储芯片",
    "算力", "半导体", "光伏"
]
```

---

## 📁 项目结构

```
alpha-quant/
├── alpha.py                 # 主程序入口
├── config.py                # 配置文件
├── requirements.txt         # Python依赖
├── setup_env.sh            # 一键搭建脚本
├── start_alpha.sh          # 便捷启动脚本
├── modules/                # 核心模块
│   ├── data_provider.py    # 数据获取
│   ├── technical_analysis.py # 技术分析
│   ├── risk_manager.py     # 风险管理
│   ├── stock_screener.py   # 选股模块
│   └── report_generator.py # 报告生成
└── reports/                # 报告输出目录
```

---

## 🔔 定时任务

系统已配置以下定时任务：

| 任务 | 时间 | 说明 |
|------|------|------|
| 盘前报告 | 工作日 09:00 | 生成选股清单 |
| 盘中监控 | 明日每30分钟 | 风险扫描 |
| 收盘复盘 | 工作日 15:35 | 生成日报 |

---

## 📊 功能特性

- ✅ **双数据源**：Tushare + AkShare 交叉验证
- ✅ **技术分析**：MA/MACD/RSI/KDJ/布林带
- ✅ **风险控制**：仓位/亏损/熔断/止损
- ✅ **智能选股**：多因子评分系统
- ✅ **自动报告**：Markdown 格式输出
- ✅ **实时监控**：盘中风险预警

---

## ⚠️ 免责声明

本系统仅供学习和研究使用，不构成投资建议。投资有风险，入市需谨慎。

---

## 🔧 故障排查

### 1. 数据获取失败
```bash
# 检查网络连接
ping www.tushare.pro

# 测试 Tushare Token 是否有效
python3 -c "import tushare; ts = tushare.pro_api('你的Token'); print(ts.trade_cal())"
```

### 2. 依赖安装失败
```bash
# 更新 pip
pip install --upgrade pip

# 单独安装 problematic 包
pip install akshare --no-deps
```

### 3. 权限问题
```bash
chmod +x setup_env.sh start_alpha.sh
```

---

## 🧪 策略回测

### 快速回测
```bash
# 单策略回测（默认：招商银行，均线交叉策略）
./start_backtest.sh

# 指定标的和策略
./start_backtest.sh single sh.600519 ma_cross

# 多策略对比
./start_backtest.sh compare

# 使用 Tushare 数据源
TUSHARE_TOKEN=your_token ./start_backtest.sh tushare
```

### 支持策略
- `ma_cross`: 双均线交叉策略（5日/20日）
- `momentum`: 动量策略（20日收益率）
- `mean_revert`: 均值回归策略（布林带）
- `multi_factor`: 多因子综合策略

### 回测指标
- 总收益率 / 年化收益率
- 最大回撤 / 夏普比率 / Calmar比率
- 胜率 / 盈亏比 / Beta
- 自动生成交易图表

---

## 📈 收盘复盘报告

### 自动生成每日复盘
```bash
# 手动生成今日复盘报告
./start_daily_report.sh
```

### 报告内容（八个部分）
1. **今日大盘总结** - 三大指数、成交额、情绪评分
2. **热点板块复盘** - 涨幅前5板块、预测准确率
3. **持仓账户表现** - 各持仓涨跌、总浮盈亏
4. **策略执行评估** - 信号数、执行率、风控触发
5. **明日关注标的** - 涨停高开概率、异常放量股
6. **策略迭代建议** - 胜率统计、AI优化建议
7. **明日操作计划** - 具体代码/方向/价位
8. **风险提示** - 政策/解禁/财报提醒

### 定时任务
- **收盘复盘**: 工作日 15:35 自动生成
- **报告路径**: `reports/daily/YYYY-MM-DD-daily.md`
- **飞书推送**: 简版（第一/三/七部分）自动推送

---

## 🤖 自动交易（PTrade / QMT）

### ⚠️ 重要提示
- **当前模式**: SIMULATION（模拟盘）
- **建议模拟运行**: 30-90 个交易日
- **人工确认**: require_human_confirm = True（必须）
- **实盘切换**: 开通权限后修改 TRADING_MODE = "LIVE"

### 方案一：PTrade（恒生电子）
支持券商：国金、招商、华泰等

#### 配置
```bash
# 编辑 .env 文件
PTRADE_TOKEN=your_ptrade_token
TRADING_MODE=SIMULATION
```

#### 上传策略
1. 开通 PTrade 量化交易权限
2. 登录 PTrade 客户端
3. 上传 `ptrade_executor.py` 到策略编辑器
4. 确保信号服务器地址可访问
5. 运行策略

---

### 方案二：QMT/miniQMT（迅投）
支持券商：国金、银河、广发等

#### 配置
```bash
# 编辑 .env 文件
QMT_PATH=D:\国金QMT\userdata_mini  # Windows 示例
QMT_ACCOUNT_ID=your_account_id
TRADING_MODE=SIMULATION
```

#### 安装依赖
```bash
# QMT 需要 xtquant 库
pip install xtquant
```

#### 启动执行器
```bash
./start_qmt.sh
```

#### 注意事项
1. miniQMT 需要券商开通权限
2. 路径配置为 miniQMT 的 userdata_mini 目录
3. 账户 ID 在 QMT 客户端查看
4. Windows 建议使用绝对路径

---

### 启动信号服务器
```bash
./start_signal_server.sh
```

### 从 Kimi 发送交易信号
```python
from trade_signal import buy, sell

# 发送买入信号
buy("600036", 35.50, 1000, "均线金叉买入")

# 发送卖出信号
sell("600036", 38.00, 1000, "止盈卖出")
```

### 风控参数
```python
MAX_POSITION_PCT = 0.20       # 单股最大仓位 20%
MAX_TOTAL_POSITION_PCT = 0.80 # 总仓位上限 80%
STOP_LOSS_PCT = 0.08          # 止损线 8%
TAKE_PROFIT_PCT = 0.20        # 止盈线 20%
DAILY_LOSS_LIMIT_PCT = 0.02   # 单日最大亏损 2%
```

---

## 📁 项目结构

```
alpha-quant/
├── alpha.py                 # 主程序入口
├── backtest_engine.py       # 策略回测引擎
├── daily_report_generator.py # 收盘复盘报告生成器
├── ptrade_executor.py       # PTrade 执行器
├── qmt_executor.py          # QMT/miniQMT 执行器
├── signal_server.py         # 交易信号服务器
├── trade_signal.py          # Kimi 信号发送工具
├── config.py                # 配置文件
├── requirements.txt         # Python依赖
├── setup_env.sh            # 一键搭建脚本
├── start_alpha.sh          # 主程序启动脚本
├── start_backtest.sh       # 回测启动脚本
├── start_daily_report.sh   # 复盘报告启动脚本
├── start_signal_server.sh  # 信号服务器启动脚本
├── start_qmt.sh            # QMT 执行器启动脚本
├── modules/                # 核心模块
│   ├── data_provider.py    # 数据获取（Baostock/Tushare）
│   ├── technical_analysis.py # 技术分析
│   ├── risk_manager.py     # 风险管理
│   ├── stock_screener.py   # 选股模块
│   └── report_generator.py # 报告生成
└── reports/                # 报告输出目录
    ├── daily/              # 每日复盘报告
    └── backtest/           # 回测结果
```

---

## 📞 支持

如有问题，请检查：
1. Python 版本 >= 3.10
2. 虚拟环境已正确激活
3. Tushare Token 有效且有足够积分
4. PTrade 权限已开通（实盘模式）
