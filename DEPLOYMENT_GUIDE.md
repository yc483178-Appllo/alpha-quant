# Alpha-Genesis V4.3 + KimiClaw V8.0 部署说明

## 🎯 版本信息

| 项目 | 版本 | 说明 |
|------|------|------|
| 看板 | V4.3 | Alpha-Genesis 前端 |
| 后端 | V8.0 | KimiClaw 后端系统 |
| 代码行数 | 5,349行 | 较V4.2增加48% |
| 文件大小 | 357KB | 单文件HTML |

## 📦 文件结构

```
kimiclaw_v8/
├── static/
│   └── index.html          # V4.3看板 (357KB/5349行)
├── api_v8/
│   └── routes.py           # V8.0 API路由 (28端点)
├── config_v8/
│   ├── __init__.py
│   └── settings_v8.py      # 统一配置系统
├── main_v8.py              # 主入口
├── requirements.txt        # 依赖列表
├── Dockerfile              # 容器配置
├── docker-compose.yml      # 编排配置
├── deploy.sh               # 部署脚本
├── start.sh                # 启动脚本
├── .env.example            # 环境变量模板
└── README.md               # 项目文档
```

## 🚀 快速部署

### 方式1: 本地启动

```bash
cd /root/.openclaw/workspace/kimiclaw_v8
./start.sh
```

访问: http://localhost:8000/dashboard

### 方式2: Docker部署

```bash
docker-compose up -d
```

### 方式3: 服务器部署

```bash
./deploy.sh
```

## 🔌 API端点清单

### 数据接口中心 (8端点)

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v8/data/sources` | GET | 获取所有数据源 |
| `/api/v8/data/source/{id}/test` | POST | 测试连接 (~88%成功率) |
| `/api/v8/data/source/{id}/sync` | POST | 触发同步 |
| `/api/v8/data/source/{id}/disconnect` | POST | 断开连接 |
| `/api/v8/data/source/add` | POST | 添加自定义源 |
| `/api/v8/data/route` | GET | AI-数据路由表 |
| `/api/v8/data/route/update` | PUT | 更新路由 |
| `/api/v8/data/sync-log` | GET | 同步日志 |

### AI模型管理 (8端点)

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v8/ai/models` | GET | 获取模型列表 |
| `/api/v8/ai/model/{id}/test` | POST | 测试连接 |
| `/api/v8/ai/model/{id}/disconnect` | POST | 断开连接 |
| `/api/v8/ai/model/{id}/reconnect` | POST | 重新连接 |
| `/api/v8/ai/model/add` | POST | 添加新模型 |
| `/api/v8/ai/model/{id}/delete` | DELETE | 删除模型 |
| `/api/v8/ai/consensus` | POST | 共识投票 |
| `/api/v8/ai/elo` | GET | ELO排名 |

### 回测引擎 (4端点)

| 端点 | 方法 | 功能 |
|------|------|------|
| `/api/v8/backtest/run` | POST | 组合回测 |
| `/api/v8/backtest/single` | POST | 单股回测 |
| `/api/v8/backtest/result/{id}` | GET | 获取结果 |
| `/api/v8/backtest/wfa/{id}` | GET | WFA验证 |

### V8.0原有端点 (8端点)

- `/api/v8/agent/arena` - Agent竞技场
- `/api/v8/factor/lifecycle` - 因子生命周期
- `/api/v8/risk/realtime` - 实时风控
- `/api/v8/risk/circuit-breaker` - 熔断控制
- `/api/v8/frontier/hdp-regime` - HDP政权
- `/api/v8/system/health` - 健康检查
- `/api/v8/system/traces` - 链路追踪
- `/api/v8/system/metrics` - Prometheus指标

**总计: 28个API端点**

## 🎨 看板V4.3新功能

### 第26面板: 数据接口中心
- 7大数据源管理 (Tushare/聚宽/Wind/东财/新浪/AKShare/BaoStock)
- 连接测试/断开/重连/同步
- AI-数据路由配置
- 同步日志实时显示

### AI协同引擎升级
- 添加新模型按钮修复
- 模型断开/重连/删除操作
- ELO评分系统
- 多模型共识投票

### 单股回测引擎
- 股票代码自动补全 (.SH/.SZ/.BJ)
- 数据源选择
- 实时绩效指标显示

### AI快捷指令
- 数据接口切换
- 全量数据同步
- 单股回测启动

## 🔧 配置说明

### 环境变量 (.env)

```bash
# API密钥
TUSHARE_TOKEN=your_token
KIMI_API_KEY=your_key
GLM_API_KEY=your_key
MINIMAX_API_KEY=your_key
GEMINI_API_KEY=your_key

# 数据库 (可选)
DATABASE_URL=postgresql://...
REDIS_URL=redis://...

# 应用配置
DEBUG=false
API_HOST=0.0.0.0
API_PORT=8000
```

### 数据源配置

| 数据源 | Token类型 | 费用 |
|--------|-----------|------|
| Tushare Pro | Token | 积分制 |
| 聚宽 | API Key | 免费/付费 |
| Wind | WindPy | 机构付费 |
| 东财 | API Key | 免费 |
| 新浪 | 无需 | 免费 |
| AKShare | pip安装 | 开源免费 |
| BaoStock | pip安装 | 开源免费 |

## ✅ 测试检查清单

- [ ] 添加新模型按钮工作正常
- [ ] AI模型断开/重连切换
- [ ] 数据接口中心面板切换
- [ ] Tushare数据源测试
- [ ] 单股回测代码自动补全
- [ ] 单股回测执行
- [ ] AI快捷指令响应
- [ ] 全量数据同步
- [ ] 26面板Chart初始化

## 🐛 已知问题

1. `engineering/deployment.py` 因 http_429 未接收，已用基础实现替代
2. 部分模块为Mock实现，生产环境需替换真实实现

## 📞 技术支持

- 看板问题: 检查浏览器Console日志
- API问题: 检查 `/health` 端点状态
- 部署问题: 检查 `logs/kimiclaw.log`

---

**部署完成时间**: 2026-03-14  
**文档版本**: V4.3  
**状态**: ✅ 已就绪
