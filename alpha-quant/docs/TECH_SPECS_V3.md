# Alpha看板V3.0 技术规范

## 7.6.6 技术注意事项

### 1. Chart.js 版本要求

**必须使用 UMD 版本**
```html
<!-- ✅ 正确 -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>

<!-- ❌ 错误 - ESM版本不暴露全局Chart对象 -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.min.js"></script>
```

**原因**: ESM版本使用ES模块导出，不会暴露全局`Chart`对象，导致`new Chart()`调用失败。

---

### 2. 懒加载模式

**使用 `S.chartsInit` 追踪初始化状态**
```javascript
const S = {
  chartsInit: {}  // 追踪图表初始化状态: { chartId: true/false }
};

// 懒加载初始化函数
function initChartLazy(panelName, chartId, chartConfig) {
  // 已初始化则跳过
  if (S.chartsInit[chartId]) return window._charts[chartId];
  
  // 首次初始化
  const chart = new Chart(ctx.getContext('2d'), chartConfig);
  window._charts[chartId] = chart;
  S.chartsInit[chartId] = true;
  return chart;
}
```

**优势**:
- 减少初始加载时间
- 避免不可见图表的渲染开销
- 只在用户切换到对应面板时初始化

---

### 3. DOM安全 (Null Guard)

**所有DOM操作均有null guard**
```javascript
// ✅ 安全DOM获取函数
function $(id) {
  const el = document.getElementById(id);
  if (!el) console.warn(`DOM元素未找到: #${id}`);
  return el;
}

// ✅ 安全文本设置
function safeText(id, text) {
  const el = $(id);
  if (el) el.textContent = text;
}

// ✅ 安全HTML设置
function safeHtml(id, html) {
  const el = $(id);
  if (el) el.innerHTML = html;
}

// ❌ 不安全的写法 - 可能导致null错误
document.getElementById('myId').textContent = 'text';  // 如果元素不存在会报错
```

---

### 4. A股规则内置

**T+1规则**
- 当日买入的股票，次日才能卖出
- 持仓卖出后可立即买入其他股票

**涨跌停限制**
- 主板股票: ±10%
- 科创板/创业板: ±20%
- ST股票: ±5%

**交易时间**
- 早盘: 9:30 - 11:30
- 午盘: 13:00 - 15:00
- 集合竞价: 9:15-9:25, 14:57-15:00

---

### 5. 数据格式规范

**策略库格式 (STRAT_LIB)**
```javascript
{
  id: 'STR-042-007',          // 策略ID
  name: 'MA双均线_42代',       // 策略名称
  type: 'momentum',           // 策略类型
  fit: 8.72,                  // 适应度
  sharpe: 1.85,               // 夏普比率
  mdd: -8.4,                  // 最大回撤
  wr: 64.2,                   // 胜率
  gen: 42,                    // 进化代际
  stocks: '600519,000858',    // 关联股票
  status: 'active'            // 状态: active/hall_of_fame
}
```

**风险钻取格式 (RISK_DRILL)**
```javascript
{
  '市场风险': {
    pct: 45,                    // 占比
    color: '#ff3d57',           // 显示颜色
    desc: '来自宏观市场...',     // 描述
    items: [                    // 明细项
      {c: '300750', n: '宁德时代', v: '12.3%', note: 'β=1.45'}
    ]
  }
}
```

---

### 6. WebSocket实时推送

**推送频道**
```javascript
socket.on('v6_live', (msg) => {
  switch(msg.type) {
    case 'price':     // 价格更新 (1秒)
    case 'agent':     // Agent状态 (5秒)
    case 'drl':       // DRL置信度 (10秒)
    case 'signal':    // 新信号 (15秒)
    case 'broker':    // 券商状态 (30秒)
    case 'evolution': // 进化代际 (60秒)
    case 'alert':     // 系统告警 (实时)
  }
});
```

---

### 7. API端点规范

| 端点 | 方法 | 功能 |
|------|------|------|
| `/v3/api/state` | GET | 获取完整状态 |
| `/v3/api/strategies` | GET | 策略库数据 |
| `/v3/api/risk/decompose` | GET | 风险分解 |
| `/v3/api/risk/metrics` | GET | 风险指标 |
| `/v3/api/risk/stress` | GET | 压力测试 |
| `/v3/api/trade/execute` | POST | 执行交易 |
| `/v3/api/broker/switch` | POST | 切换券商 |
| `/v3/api/command` | POST | AI指令 |

---

### 8. 文件结构

```
/var/www/alpha-dashboard/v3/
├── dashboard_v3.html      # 前端看板

/root/.openclaw/workspace/alpha-quant/
├── dashboard_data_bridge.py   # 数据桥接服务
├── dashboard_v3.py            # Dashboard V3 API
├── risk_engine.py             # 风险引擎
├── smart_broker_v2.py         # 券商管理
├── strategy_evolution_engine.py  # 策略进化
└── ...
```

---

### 9. 服务管理

```bash
# 查看服务状态
systemctl status alpha-dashboard-bridge
systemctl status alpha-dashboard-v3
systemctl status nginx

# 查看日志
journalctl -u alpha-dashboard-bridge -f

# 重启服务
systemctl restart alpha-dashboard-bridge
```

---

### 10. 访问地址

- **看板页面**: http://101.126.150.200/v3/
- **API端点**: http://101.126.150.200/v3/api/
- **WebSocket**: ws://101.126.150.200/v3/socket.io/
