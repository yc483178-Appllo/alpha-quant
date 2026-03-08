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

**Alpha 主服务器 (阿里云)**
- 实例名：Ubuntu-rbiz
- 公网 IP：120.76.55.222
- 私有 IP：172.17.39.97
- 用户名：root
- 密码：Yfc244083
- 实例 ID：23c6df6d03154eceb969959695e15aed
- 配置：2核2G / 40GB ESSD
- 地域：华南1（深圳）
- 到期时间：2027-03-08
- 登录命令：`ssh root@120.76.55.222`

---

### SSH 连接方式

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

Add whatever helps you do your job. This is your cheat sheet.
