# Alpha-Genesis V7.0 - 第五章：看板V3.1新增面板

## 5.1 看板V3.1升级概览

V7.0新增模块需要在看板中增加对应的可视化面板，实现全流程监控。

---

## 5.2 新增面板详细设计

### 面板1：因子研发面板 (Factor Research Dashboard)

**位置**：主看板第15个Tab

**内容模块**：
```
┌─────────────────────────────────────────────────────────────┐
│  因子研发面板                                                │
├─────────────────┬─────────────────┬─────────────────────────┤
│  GP进化进度      │  因子IC排行      │  因果检验状态           │
│  [实时进度条]    │  [Top10列表]    │  [通过/待验证/拒绝]     │
│                 │                 │                         │
│  当前代数: 45   │  1. 动量_20D    │  ● 已通过: 12           │
│  最优适应度:    │     IC: 0.08    │  ○ 待验证: 5            │
│     1.85       │     IR: 0.45    │  ✕ 已拒绝: 3            │
│                 │  2. ROE_QoQ     │                         │
│  [进化曲线图]   │     IC: 0.06    │  [因果强度分布图]        │
│                 │     IR: 0.38    │                         │
└─────────────────┴─────────────────┴─────────────────────────┘
```

**关键KPI**：
- IC均值：目标 > 0.03
- IC/IR：目标 > 0.3
- 因果强度：目标 > 0.7
- GP进化代数：实时显示

**API端点**：
- `GET /api/v7/dashboard/factor-research/status`
- `GET /api/v7/dashboard/factor-research/ic-ranking`
- `GET /api/v7/dashboard/factor-research/causal-validation`

---

### 面板2：回测中心面板 (Backtest Center)

**位置**：主看板第16个Tab

**内容模块**：
```
┌─────────────────────────────────────────────────────────────┐
│  回测中心                                                    │
├─────────────────┬─────────────────┬─────────────────────────┤
│  WFA滚动回测    │  成本模型分析    │  过拟合检测             │
│                 │                 │                         │
│  [滚动窗口图]   │  [成本分解饼图]  │  [IS/OS对比图]          │
│                 │                 │                         │
│  窗口数: 24     │  冲击成本: 35%  │  IS夏普: 1.85           │
│  平均夏普: 1.2  │  滑点: 25%      │  OS夏普: 1.42           │
│  稳定性: 85%    │  佣金: 20%      │  衰减: 23%              │
│                 │  其他: 20%      │                         │
│  [收益曲线对比] │                 │  [过拟合警告] ⚠️         │
└─────────────────┴─────────────────┴─────────────────────────┘
```

**关键KPI**：
- IN/OUT收益差：目标 < 20%
- 滑点率：目标 < 0.05%
- 成本占比：实时显示
- WFA稳定性：目标 > 80%

**API端点**：
- `GET /api/v7/dashboard/backtest/wfa-results`
- `GET /api/v7/dashboard/backtest/cost-breakdown`
- `GET /api/v7/dashboard/backtest/overfit-status`

---

### 面板3：绩效归因面板 (Performance Attribution)

**位置**：主看板第17个Tab

**内容模块**：
```
┌─────────────────────────────────────────────────────────────┐
│  绩效归因                                                    │
├─────────────────┬─────────────────┬─────────────────────────┤
│  Brinson分解    │  Barra风格归因   │  成本归因               │
│                 │                 │                         │
│  [瀑布图]       │  [风格暴露热力图]│  [成本趋势图]           │
│                 │                 │                         │
│  配置效应: +2.1%│  市值: 0.45     │  累计成本: -1.2%        │
│  选择效应: +1.8%│  价值: -0.23    │  冲击成本: -0.8%        │
│  交互效应: +0.5%│  动量: 0.67     │  滑点成本: -0.3%        │
│                 │  质量: 0.12     │  佣金: -0.1%            │
│  纯α收益: 4.4%  │                 │                         │
│                 │  [风格漂移警告] │                         │
└─────────────────┴─────────────────┴─────────────────────────┘
```

**关键KPI**：
- 纯Alpha收益：目标 > 3%
- 风格漂移度：目标 < 0.3
- 配置/选择/交互占比
- 各行业/风格贡献

**API端点**：
- `GET /api/v7/dashboard/attribution/brinson`
- `GET /api/v7/dashboard/attribution/barra-style`
- `GET /api/v7/dashboard/attribution/cost`

---

### 面板4：执行算法面板 (Execution Algorithm)

**位置**：主看板第18个Tab

**内容模块**：
```
┌─────────────────────────────────────────────────────────────┐
│  执行算法监控                                                │
├─────────────────┬─────────────────┬─────────────────────────┤
│  TWAP/VWAP进度  │  滑点实时监控    │  执行质量评分           │
│                 │                 │                         │
│  [执行进度条]   │  [滑点热力图]    │  [仪表盘]               │
│                 │                 │                         │
│  订单1: ████████│  股票A: 0.03%   │      ┌─────┐           │
│        80%     │  股票B: 0.05%   │      │  92  │           │
│  订单2: ██████░░│  股票C: 0.02%   │      │  分  │           │
│        60%     │                 │      └─────┘           │
│                 │  平均滑点: 0.04%│                         │
│  [算法分布饼图] │                 │  [历史质量趋势]          │
│  TWAP: 45%     │                 │                         │
│  VWAP: 35%     │                 │                         │
│  POV: 20%      │                 │                         │
└─────────────────┴─────────────────┴─────────────────────────┘
```

**关键KPI**：
- 执行质量分：目标 > 90分
- 平均滑点：目标 < 0.05%
- 算法完成率：实时显示
- 异常订单数

**API端点**：
- `GET /api/v7/dashboard/execution/progress`
- `GET /api/v7/dashboard/execution/slippage`
- `GET /api/v7/dashboard/execution/quality-score`

---

### 面板5：仿真交易面板 (Simulation Trading)

**位置**：主看板第19个Tab

**内容模块**：
```
┌─────────────────────────────────────────────────────────────┐
│  仿真交易与灰度发布                                          │
├─────────────────┬─────────────────┬─────────────────────────┤
│  仿真策略PnL    │  灰度发布状态    │  虚实收益对比           │
│                 │                 │                         │
│  [累计收益曲线]  │  [阶段指示器]   │  [散点对比图]           │
│                 │                 │                         │
│  今日PnL:       │  仿真阶段  ✓   │  仿真收益: +15.2%       │
│    +2.3%       │  10%灰度  ●→   │  实盘收益: +14.8%       │
│  本月PnL:       │  30%灰度  ○    │  偏差: 2.6%             │
│    +8.5%       │  全量上线  ○    │                         │
│                 │                 │  [Bayesian置信度]       │
│  [策略列表]     │  [自动升级条件]  │  置信度: 96.5% ✓        │
│  策略A: 运行中  │  置信度>95%    │                         │
│  策略B: 灰度中  │  时间>15天     │                         │
└─────────────────┴─────────────────┴─────────────────────────┘
```

**关键KPI**：
- 仿真/实盘收益比：目标 0.9-1.1
- 灰度阶段进度：实时显示
- Bayesian置信度：目标 > 95%
- 策略生存率

**API端点**：
- `GET /api/v7/dashboard/simulation/pnl`
- `GET /api/v7/dashboard/canary/status`
- `GET /api/v7/dashboard/simulation-real-comparison`

---

### 面板6：合规审计面板 (Compliance Audit)

**位置**：主看板第20个Tab

**内容模块**：
```
┌─────────────────────────────────────────────────────────────┐
│  合规审计                                                    │
├─────────────────┬─────────────────┬─────────────────────────┤
│  审计日志流水   │  异常交易告警    │  监管报表状态           │
│                 │                 │                         │
│  [时间线]       │  [告警列表]      │  [报表生成状态]          │
│                 │                 │                         │
│  14:32:15 订单  │  ⚠️ 频繁撤单    │  日报: ✓ 已生成         │
│         已审批  │    股票600519   │  周报: ✓ 已生成         │
│  14:32:18 订单  │    15分钟内     │  月报: ○ 生成中         │
│         已发送  │    撤单20次     │                         │
│  14:32:20 成交  │                 │  审计完整度:            │
│         回报接收│  🔴 疑似自成交   │  [███████░░░] 78%       │
│                 │    账户A<->B    │                         │
│                 │                 │  下次检查: 2小时后      │
└─────────────────┴─────────────────┴─────────────────────────┘
```

**关键KPI**：
- 审计完整度：目标 100%
- 异常交易数：实时监控
- 监管报表生成状态
- 合规风险等级

**API端点**：
- `GET /api/v7/dashboard/compliance/audit-log`
- `GET /api/v7/dashboard/compliance/alerts`
- `GET /api/v7/dashboard/compliance/regulatory-reports`

---

### 面板7：GNN股票图面板 (GNN Stock Graph)

**位置**：主看板第21个Tab

**内容模块**：
```
┌─────────────────────────────────────────────────────────────┐
│  GNN股票关系网络                                             │
├─────────────────┬─────────────────┬─────────────────────────┤
│  股票关系图     │  传导效应热力图  │  风险传导预警           │
│                 │                 │                         │
│  [力导向图]     │  [热力矩阵]      │  [风险传播模拟]          │
│                 │                 │                         │
│  节点: 股票     │     宁德 比亚迪  茅台                     │
│  边: 关系类型   │ 宁德  -   0.8   0.1                     │
│  颜色: 行业     │ 比亚迪 0.8   -   0.05                    │
│  大小: 市值     │ 茅台  0.1  0.05   -                      │
│                 │                 │                         │
│  选中节点:      │  影响度范围:    │  若宁德时代跌8%:        │
│  宁德时代       │  0.0 - 0.85     │  比亚迪预计跌: 5.2%     │
│                 │                 │  璞泰来预计跌: 4.8%     │
│                 │                 │  [自动调仓建议]          │
└─────────────────┴─────────────────┴─────────────────────────┘
```

**关键KPI**：
- 传导影响度：实时计算
- 关系网络密度
- 风险节点识别
- 自动调仓建议

**API端点**：
- `GET /api/v7/dashboard/gnn/stock-graph`
- `POST /api/v7/dashboard/gnn/predict-contagion`
- `GET /api/v7/dashboard/gnn/heatmap`

---

## 5.3 看板API汇总

| 面板 | API端点前缀 | 关键接口数 |
|------|-------------|-----------|
| 因子研发 | `/api/v7/dashboard/factor-research/` | 3 |
| 回测中心 | `/api/v7/dashboard/backtest/` | 3 |
| 绩效归因 | `/api/v7/dashboard/attribution/` | 3 |
| 执行算法 | `/api/v7/dashboard/execution/` | 3 |
| 仿真交易 | `/api/v7/dashboard/simulation/` | 3 |
| 合规审计 | `/api/v7/dashboard/compliance/` | 3 |
| GNN股票图 | `/api/v7/dashboard/gnn/` | 3 |
| **总计** | | **21个API端点** |

---

## 5.4 看板技术实现

### 前端技术栈
```javascript
// dashboard_v31.js
import { Chart } from 'chart.js';
import { Graph } from 'react-d3-graph';
import { HeatMap } from 'react-heatmap-grid';

// 7个新面板组件
const panels = {
  factorResearch: FactorResearchPanel,
  backtestCenter: BacktestCenterPanel,
  performanceAttribution: AttributionPanel,
  executionAlgo: ExecutionPanel,
  simulation: SimulationPanel,
  compliance: CompliancePanel,
  gnnGraph: GNNGraphPanel
};

// 实时数据流 (WebSocket)
const ws = new WebSocket('ws://120.76.55.222/v3/ws/dashboard');
ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  updatePanel(update.panel, update.data);
};
```

### 后端数据推送
```python
# dashboard_v31_backend.py
from flask_socketio import SocketIO, emit

class DashboardV31DataFeed:
    def __init__(self):
        self.socketio = SocketIO()
        
    def broadcast_update(self, panel: str, data: dict):
        """实时推送面板更新"""
        self.socketio.emit(f'update_{panel}', data, broadcast=True)
        
    def start_realtime_feed(self):
        """启动实时数据流"""
        # 因子研发数据：每30秒
        # 回测中心数据：每60秒
        # 执行算法数据：每5秒
        # GNN传导计算：每分钟
        pass
```

---

*Module: Chapter 5 - Dashboard V3.1 New Panels*  
*Status: 详细设计记录*
