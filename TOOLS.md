# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

---

## 当前系统配置

### 服务器列表

**Alpha 主服务器 (阿里云轻量服务器)** ⚠️ **重要！务必记住！**
- 实例名：Ubuntu-rbiz
- **公网 IP：120.76.55.222** ← 用户强调！
- **私有 IP：172.17.39.97** ← 用户强调！(2026-03-18 确认)
- 实例 ID：23c6df6d03154eceb969959695e15aed
- ⚠️ **部署时务必使用这两个 IP，不要搞错！**
- 用户名：root
- 密码：Yfc244083
- 实例 ID：23c6df6d03154eceb969959695e15aed
- 配置：2核2G / 40GB ESSD
- 地域：华南1（深圳）
- 到期时间：2027-03-08
- 登录命令：`ssh root@120.76.55.222`

---

## ⚠️⚠️⚠️ 量化交易系统部署配置（绝对不能搞错！）

### V7.0 当前版本部署路径

**Web 根目录（Caddy配置）：**
```
/opt/alpha/v7/     ← V7.0 API和静态文件根目录
```

**看板访问地址：**
```
http://120.76.55.222:8000/v3/
```

**API访问地址：**
```
API文档:   http://120.76.55.222:8000/api/docs
健康检查: http://120.76.55.222:8000/health
系统状态: http://120.76.55.222:8000/api/system/status
```

**Caddyfile位置：**
```
/etc/caddy/Caddyfile
```

**Caddy关键配置（V7.0）：**
```caddy
handle /v3/* {
    root * /opt/alpha/v7        ← ⚠️ 必须是这个路径！
    uri strip_prefix /v3
    file_server
    encode gzip
}
```

---

### V8.0 新版本部署路径

**看板部署位置（Caddy配置）：**
```
/opt/alpha/v3/index.html     ← ⚠️ 看板V4.3部署位置
```

**后端API部署位置：**
```
/opt/alpha/v7/kimiclaw_v8_api/     ← V8.0后端代码
├── main_v8.py
├── api_v8/routes.py
├── config_v8/settings_v8.py
└── logs/kimiclaw_v8.log
```

**看板访问地址：**
```
http://120.76.55.222/v3/
```

**API访问地址：**
```
API文档:    http://120.76.55.222:8000/docs
健康检查:   http://120.76.55.222:8000/health
数据源API:  http://120.76.55.222:8000/api/v8/data/sources
AI模型API:  http://120.76.55.222:8000/api/v8/ai/models
```

**Caddy关键配置（V8.0）：**
```caddy
handle_path /v3/* {
    root * /opt/alpha/v3        ← ⚠️ 必须是这个路径！
    file_server
}
```

---

### ❌ 错误路径（千万不要用）
- `/var/www/html/v3/` - Caddy不指向这里！
- `/var/www/alpha-dashboard/v3/` - Caddy不指向这里！
- `/opt/alpha/v7/static/` - V4.3看板不应该放这里！

---

### ✅ V8.0部署流程（正确步骤）

**1. 部署看板V4.3：**
```bash
scp static/index.html root@120.76.55.222:/opt/alpha/v3/index.html
```

**2. 部署后端API：**
```bash
rsync -avz --exclude='.venv' --exclude='__pycache__' --exclude='static' \
    ./ root@120.76.55.222:/opt/alpha/v7/kimiclaw_v8_api/
```

**3. 启动服务：**
```bash
ssh root@120.76.55.222 "cd /opt/alpha/v7/kimiclaw_v8_api && \
  pip3 install -r requirements.txt -q && \
  nohup python3 main_v8.py > logs/kimiclaw_v8.log 2>&1 &"
```

**4. 验证部署：**
```bash
# 检查看板
curl http://120.76.55.222/v3/ | head -c 200

# 检查API
curl http://120.76.55.222:8000/health

# 检查端口
ssh root@120.76.55.222 "netstat -tlnp | grep 8000"
```

---

### 📋 服务管理命令

```bash
# 查看服务状态
ssh root@120.76.55.222 "ps aux | grep main_v8"

# 查看日志
ssh root@120.76.55.222 "tail -f /opt/alpha/v7/kimiclaw_v8_api/logs/kimiclaw_v8.log"

# 重启服务
ssh root@120.76.55.222 "pkill -f main_v8; sleep 2; \
  cd /opt/alpha/v7/kimiclaw_v8_api && \
  nohup python3 main_v8.py > logs/kimiclaw_v8.log 2>&1 &"

# 检查Caddy状态
ssh root@120.76.55.222 "systemctl status caddy"

# 重载Caddy配置
ssh root@120.76.55.222 "caddy reload --config /etc/caddy/Caddyfile"
```

---

### 🔑 关键记忆点

| 项目 | V7.0 | V8.0 | V9.0 |
|------|------|------|------|
| 看板路径 | `/opt/alpha/v7/static/` | `/opt/alpha/v3/` | `/opt/alpha/v3/` |
| Nginx 配置 | Caddy | Caddy | ✅ Nginx (端口80) |
| 缓存控制 | ❌ 外部代理缓存 | ❌ 外部代理缓存 | ✅ Cloudflare 已清除 |

---

### V9.0 最新部署配置 (2026-03-18)

**看板部署位置：**
```
/opt/alpha/v3/index.html     ← V9.0 看板部署位置
```

**Nginx 配置位置：**
```
/etc/nginx/sites-available/alpha-dashboard
```

**Nginx 关键配置（V9.0）：**
```nginx
location /v3/ {
    alias /opt/alpha/v3/;
    try_files $uri $uri/ =404;
    index index.html;
    
    # 禁用缓存
    add_header Cache-Control "no-cache, no-store, must-revalidate";
    add_header Pragma "no-cache";
    expires -1;
}
```

**当前访问地址：**
- 公网 (阿里云代理缓存): `http://120.76.55.222/v3/` — 等待缓存过期
- 内网 (直接访问): `http://172.17.39.97/v3/` ✅ V9.0 正常
- 本地: `http://127.0.0.1/v3/` ✅ V9.0 正常

**V9.0 部署流程：**
```bash
# 1. 部署看板V9.0
scp index.html root@120.76.55.222:/opt/alpha/v3/index.html

# 2. 重载 Nginx
ssh root@120.76.55.222 "nginx -s reload"

# 3. 验证部署
curl http://172.17.39.97/v3/ | grep -o 'V[0-9]\.[0-9]'
```
| 后端路径 | `/opt/alpha/v7/` | `/opt/alpha/v7/kimiclaw_v8_api/` |
| 看板URL | `:8000/v3/` | `/v3/` (Caddy代理) |
| API端口 | 8000 | 8000 |
| Caddy路由 | `handle /v3/*` | `handle_path /v3/*` |

⚠️ **每次部署前必须确认：**
1. Caddy配置中的root路径
2. 看板文件的实际位置
3. 后端服务的运行端口
4. 访问URL是否匹配

**务必记住！不要再搞错！**

```bash
# 连接 Alpha 服务器
ssh root@120.76.55.222

# 如果提示 Host key verification failed，先清除旧记录
ssh-keygen -R 120.76.55.222
```

### Cloudflare API Token

**用途**: 自动管理 SSL 证书 (DNS Challenge)
**Token**: `0e3l-qtI-5-EFRp1MHRbdP6f9wOE6cYhsKWBgyP_`

**使用方式**:
```bash
# Caddy 配置中用于 TLS DNS 验证
tls {
    dns cloudflare {env.CF_API_TOKEN}
}
```

**安全提醒**: 此 Token 仅用于 DNS 验证，勿泄露。

---

## GitHub 代码仓

**仓库地址**: `git@github.com:yc483178-Appllo/alpha-quant.git`
**主要分支**: `main`, `master`, `v8.0-release`
**SSH Key**: `SHA256:UVHv6JrYyNN9/HCmKabRKSESUtx6A9UaoDdVUkXaydo`
**公钥**: `ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAINKKGxPxtVUbeFpaoxgcizFxfFAQYD/VxZ93Ne2HSH7q`

**自动上传指令**: 当用户说"上传资料到github代码仓"时，自动执行：
```bash
git add -A .
git commit -m "update: $(date '+%Y-%m-%d %H:%M')"
git push origin $(git branch --show-current) 2>/dev/null || git push origin HEAD:v8.0-release
```

**手动推送命令**:
```bash
# 在阿里云服务器上执行
ssh root@120.76.55.222 "cd /opt/alpha/v7/kimiclaw_v8_api && git add -A . && git commit -m 'update' && git push origin v8.0-release"
```

---

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

## Playwright MCP 浏览器自动化

**版本**: 0.0.68
**安装位置**: `/root/.openclaw/skills/playwright-mcp/`
**浏览器缓存**: `/root/.cache/ms-playwright/`

**已安装组件**:
- Chromium 145.0.7632.6 (v1208)
- Chrome Headless Shell 145.0.7632.6 (v1208)
- FFmpeg v1011 (录屏支持)

**启动命令**:
```bash
# STDIO 模式（默认）
npx @playwright/mcp

# Headless 模式
npx @playwright/mcp --headless

# 指定浏览器
npx @playwright/mcp --browser chromium
```

**常用工具**:
- `browser_navigate` - 网页导航
- `browser_click` - 点击元素
- `browser_type` - 输入文本
- `browser_evaluate` - 执行 JavaScript
- `browser_snapshot` - 获取页面结构
- `browser_get_text` - 提取文本内容
- `browser_close` - 关闭浏览器

---

## Obsidian CLI (notesmd-cli)

**版本**: v0.3.2
**安装位置**: `/root/go/bin/notesmd-cli`
**命令路径**: `/usr/local/bin/obsidian-cli`

**常用命令**:
```bash
# 设置默认 Vault
obsidian-cli set-default "MyVault"

# 查看默认 Vault
obsidian-cli print-default

# 搜索笔记
obsidian-cli search "关键词"

# 搜索内容
obsidian-cli search-content "关键词"

# 创建笔记
obsidian-cli create "Folder/New Note" --content "内容" --open

# 移动/重命名
obsidian-cli move "old/path" "new/path"

# 删除笔记
obsidian-cli delete "path/note"

# 打开每日笔记
obsidian-cli daily
```

**配置**:
- Obsidian Vault 配置: `~/.config/obsidian/obsidian.json`
- CLI 配置: `~/.config/notesmd-cli/preferences.json`

---

## Nano Banana Pro (图像生成)

**版本**: Gemini 2.0 Flash Image API
**安装位置**: `/root/.openclaw/skills/nano-banana-pro/`
**依赖**: uv v0.10.8, google-genai v1.66.0, pillow v12.1.1

**使用方法**:
```bash
# 生成新图像
nano-banana \
  --prompt "A serene Japanese garden" \
  --filename "2025-11-23-japanese-garden.png" \
  --resolution 4K

# 编辑现有图像
nano-banana \
  --prompt "make the sky more dramatic" \
  --filename "output.png" \
  --input-image "original.png" \
  --resolution 2K
```

**分辨率选项**: 1K (默认), 2K, 4K

**API Key**: 已配置 `GEMINI_API_KEY` 环境变量

**快捷命令**:
```bash
# 使用包装脚本（推荐）
nano-banana --prompt "..." --filename "..."

# 或直接调用虚拟环境 Python
/root/.openclaw/skills/nano-banana-pro/.venv/bin/python \
  /root/.openclaw/skills/nano-banana-pro/scripts/generate_image.py \
  --prompt "..." --filename "..."
```

**工作流程**:
1. Draft (1K): 快速验证 prompt
2. Iterate: 调整 prompt 细节
3. Final (4K): 确定后生成高清图

**注意**: API 调用可能需要较长时间，请耐心等待。

---

## 浏览器偏好

**用户当前使用**: Tabbit 浏览器（海外版）

**我的使用策略**:
- 优先尝试系统默认的 Chromium/Chrome（headless 模式）
- 如遇兼容性问题，可灵活切换至其他可用浏览器
- 可用选项包括但不限于：Tabbit（国内版）、Firefox、Edge 等
- 通过 Playwright MCP 的 `--browser` 参数指定

---

Add whatever helps you do your job. This is your cheat sheet.
