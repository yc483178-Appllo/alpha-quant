# MEMORY.md — Long-Term Memory

## About Kimi (用户)
- **Name**: Kimi
- **Role**: AI Assistant / Quant Trading System Developer
- **Timezone**: Asia/Shanghai (CST)
- **Communication Style**: Direct, technical, prefers action over explanation
- **Project Focus**: Alpha-Genesis Quantitative Trading System V6.0

## User Preferences
- **Name**: (待填写)
- **称呼**: (待填写)
- **时区**: Asia/Shanghai
- **工作模式**: 高效执行型，偏好直接结果
- **技术栈**: Python, JavaScript, Quantitative Finance, AI/ML

## Active Projects

### Alpha-Genesis V6.0 量化交易系统
**Status**: 🔧 持续集成中
**Last Activity**: 2026-03-07 (部署看板修复 ES6→ES5 兼容性问题)

**Key Components**:
- 11层架构，8个专业AI Agent
- 策略进化引擎（基因算法，策略种群100个）
- 聚宽数据网关（基本面/因子/行业/机构持仓）
- Transformer-DRL（政权感知注意力机制）
- 智能券商管理V2（手动/自动/条件切换）

**Technical Stack**:
- Backend: Python (Tushare Pro, AkShare)
- Frontend: HTML/CSS/JS + Chart.js 4.4.0
- Notifications: 飞书（签名校验已配置）
- Server: http://120.76.55.222 / http://101.126.150.200/v3/

**Recent Decisions**:
- 2026-03-06: 授权AI自主创建skill
- 2026-03-07: 安装 memory-setup skill 配置持久化记忆

### V6.0 新增模块 (2026-03-06)

#### 1. 舆情分析 - 事件驱动信号
- **文件**: `sentiment_pipeline.py`
- **功能**: EventClassifier, EntityLinker, EventDrivenSentimentPipeline
- **事件类型**: earnings, policy, merger, blackswan, industry
- **API**: GET/POST `/v3/api/sentiment/events`

#### 2. 组合优化增强 - HMM政权检测
- **文件**: `portfolio_optimizer.py`
- **功能**: MarketRegimeDetector, RegimeAdaptiveOptimizer
- **政权映射**:
  - bull → momentum_tilt
  - range → black_litterman
  - bear → risk_parity
  - crisis → min_variance
- **风险参数**: 单股5%-15%，行业20%-40%，目标波动5%-15%
- **API**: GET/POST `/v3/api/portfolio/regime|optimize`

---

## Important Decisions & Lessons

### 2026-03-06: Skill 自主创建授权
- **决策**: 用户授权我可以自行创建 skill
- **范围**: 当发现现有技能不足或有更好的实现方式时，可自主创建
- **依据**: 已安装 skill-creator，具备创建能力
- **约束**: 负责任地使用，确保 skill 质量

### 2026-03-07: 安装 memory-setup skill
- **决策**: 配置持久化记忆系统
- **原因**: 解决跨会话记忆丢失问题
- **实施**: 创建 MEMORY.md 结构，配置向量搜索

---

### 2026-03-08: 安装 playwright-mcp skill
- **决策**: 配置浏览器自动化工具
- **组件**:
  - @playwright/mcp v0.0.68
  - Chromium 145.0.7632.6 (v1208)
  - Chrome Headless Shell 145.0.7632.6
  - FFmpeg v1011
- **用途**: 网页数据抓取、表单自动化、截图录屏
- **状态**: ✅ 已配置并测试完成
- **自主操作授权**: 用户授权我可根据需要自主使用 playwright-mcp 进行网页自动化，无需事先询问

---

### 2026-03-08: 安装 Obsidian skill
- **决策**: 配置 Obsidian Vault 管理工具
- **组件**:
  - notesmd-cli (obsidian-cli) v0.3.2
  - 通过 Go 安装: `go install github.com/Yakitrak/notesmd-cli@latest`
  - 软链接: `obsidian-cli` → `notesmd-cli`
- **用途**: 
  - 管理 Obsidian 笔记库 (Vault)
  - 创建/搜索/移动/删除笔记
  - 自动更新 wiki links 和 markdown links
  - 支持每日笔记 (daily notes)
- **状态**: ✅ 已配置完成

---

### 2026-03-08: 安装 nano-banana-pro skill
- **决策**: 配置图像生成和编辑工具
- **组件**:
  - uv (Python 包管理器) v0.10.8
  - google-genai v1.66.0
  - pillow v12.1.1
  - 虚拟环境: `/root/.openclaw/skills/nano-banana-pro/.venv/`
  - 包装脚本: `nano-banana` → `generate_image.py`
- **功能**: 
  - 文生图 (text-to-image)
  - 图生图/编辑 (image-to-image)
  - 支持 1K/2K/4K 分辨率
- **依赖**: `GEMINI_API_KEY` 环境变量 (已配置)
- **模型**: gemini-2.0-flash-exp-image-generation
- **状态**: ✅ 已配置完成，等待 API 测试

---

## Lessons Learned

### ES6 → ES5 转换教训
- 箭头函数 `=>` 必须完整替换为 `function(){}`
- 展开运算符 `...CD` 必须完全展开为对象
- 模板字符串需要正确处理
- 每次修改后必须验证语法 (node --check)

---

## TODOs & Follow-ups

- [ ] 完成 Alpha V3.0 看板部署和验证
- [ ] 配置 memory 向量搜索 provider
- [ ] 补充用户个人信息（姓名/称呼）
- [ ] 测试 playwright-mcp 实际网页抓取场景
- [ ] 配置 Obsidian Vault 路径并测试
- [ ] 测试 nano-banana-pro 图像生成功能

---

*Last Updated: 2026-03-08*
