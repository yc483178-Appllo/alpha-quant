# KimiClaw V8.0 — A股量化交易系统

## 🚀 快速开始

### 环境要求
- Python 3.9+
- Redis (可选，用于缓存)
- PostgreSQL (可选，用于数据存储)

### 安装

```bash
# 克隆仓库
git clone <repository>
cd kimiclaw_v8

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入API密钥
```

### 启动

```bash
# 方式1: 使用启动脚本
chmod +x start.sh
./start.sh

# 方式2: 直接启动
python3 main_v8.py
```

### Docker部署

```bash
# 构建镜像
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f kimiclaw-v8
```

## 📊 系统架构

### 10大子系统

| 子系统 | 功能 | 状态 |
|--------|------|------|
| AI Gateway | 多模型编排 (Kimi/GLM/MiniMax/Gemini) | ✅ |
| Agent System | 资金拍卖 + 对抗测试 | ✅ |
| Backtest V8 | A股特化回测引擎 | ✅ |
| Execution V8 | 涨跌停队列优化 + RL自适应 | ✅ |
| Compliance V8 | 程序化交易合规 + 20年审计 | ✅ |
| Factor Lifecycle | 7状态因子生命周期管理 | ✅ |
| Risk Control | 实时风控 + 4级熔断 | ✅ |
| Advanced Tech | HDP-HMM + 对抗训练 + LLM-GNN | ✅ |
| Observability | OpenTelemetry + Prometheus | ✅ |
| Data Gateway | 多源数据融合 | ✅ |

### API端点

| 端点 | 描述 |
|------|------|
| `/` | 系统信息 |
| `/health` | 健康检查 |
| `/docs` | API文档 (Swagger UI) |
| `/dashboard` | V4.2实时看板 |
| `/api/v8/subsystems` | 子系统状态 |

## 🛠️ 开发

### 项目结构

```
kimiclaw_v8/
├── ai_gateway_v8/      # AI网关
├── agent_system_v8/    # Agent系统
├── api_v8/             # API路由
├── backtest_v8/        # 回测引擎
├── compliance_v8/      # 合规引擎
├── config_v8/          # 配置系统
├── execution_v8/       # 执行引擎
├── factor_lifecycle/   # 因子生命周期
├── advanced_tech/      # 高级技术
├── risk_control/       # 风控系统
├── observability/      # 可观测性
├── static/             # 看板静态文件
├── main_v8.py          # 主入口
├── requirements.txt    # 依赖
└── README.md           # 本文件
```

### 配置

所有配置通过 `config_v8/settings_v8.py` 管理，支持环境变量覆盖。

```python
from config_v8 import settings_v8

# 访问配置
print(settings_v8.ai_gateway.consensus.mode)
print(settings_v8.risk.circuit_breaker_levels)
```

## 📈 看板

访问 `http://localhost:8000/dashboard` 查看V4.2实时看板：

- 19个功能面板
- 51个实时图表
- AI Gateway监控
- 因子生命周期追踪
- 实时风控指标

## 🔒 合规

- 程序化交易报告自动生成
- 内幕信息注册与隔离
- 20年审计日志保留
- 实时合规检查

## 📄 许可证

MIT License
