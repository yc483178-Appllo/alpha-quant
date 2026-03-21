# CI/CD 自动化部署配置

本指南帮助你在 GitHub Actions 中配置自动化部署到阿里云轻量服务器。

---

## 🚀 快速开始

### 步骤 1: 配置 GitHub Secrets

在 GitHub 仓库设置中添加以下密钥：

1. 访问: `https://github.com/yc483178-Appllo/alpha-quant/settings/secrets/actions`

2. 添加以下 Secrets：

| Secret 名称 | 说明 | 示例值 |
|------------|------|--------|
| `ALPACA_HOST` | 阿里云服务器 IP | `120.76.55.222` |
| `ALPACA_USER` | 服务器用户名 | `root` |
| `ALPACA_PASSWORD` | 服务器密码 | `your_password` |

### 步骤 2: 推送代码触发部署

```bash
# 在本地克隆的仓库中
cd /tmp/alpha-quant/alpha-quant

# 添加 GitHub 仓库作为远程源（如果没有的话）
git remote add origin https://github.com/yc483178-Appllo/alpha-quant.git

# 提交 workflow 文件
git add .github/
git commit -m "feat: 添加 CI/CD 自动化部署"

# 推送到 GitHub
git push origin master
```

### 步骤 3: 查看部署状态

1. 访问: `https://github.com/yc483178-Appllo/alpha-quant/actions`
2. 查看部署日志

---

## ⚙️ 部署模式

### 自动部署（推送代码时）
推送到 `master` 或 `main` 分支时自动触发。

### 手动部署（可选）
1. 访问 Actions 页面
2. 选择 "Deploy to Alibaba Cloud"
3. 点击 "Run workflow"
4. 选择部署模式：
   - `full`: 完整部署（安装依赖 + 重启服务）
   - `code-only`: 仅更新代码
   - `restart`: 仅重启服务

---

## 📁 部署流程

```
代码推送 → GitHub Actions → SSH 连接到阿里云 → 拉取代码 → 安装依赖 → 重启服务
```

### 详细步骤：

1. **代码同步**: 通过 SSH 连接到阿里云服务器
2. **Git 拉取**: 从 GitHub 拉取最新代码
3. **依赖安装**: 安装 Python 依赖
4. **服务重启**: 重启 Gunicorn/Flask 服务
5. **状态检查**: 确认服务运行正常

---

## 🔧 阿里云服务器准备

确保你的阿里云服务器已配置：

### 1. 安装 Python 3
```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3 python3-pip

# 验证
python3 --version
```

### 2. 安装 Gunicorn
```bash
pip3 install gunicorn flask flask-cors
```

### 3. 配置 Systemd 服务（推荐）
```bash
# 创建服务文件
sudo nano /etc/systemd/system/alpha-quant.service
```

内容：
```ini
[Unit]
Description=Alpha Quant Trading System
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/alpha
ExecStart=/usr/bin/python3 dashboard.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启用服务：
```bash
sudo systemctl enable alpha-quant
sudo systemctl start alpha-quant
```

### 4. 配置 Caddy（Web 服务器）
```bash
# 安装 Caddy
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install caddy
```

### 5. 配置防火墙
```bash
# 开放端口
sudo ufw allow 22    # SSH
sudo ufw allow 80     # HTTP
sudo ufw allow 443    # HTTPS
sudo ufw allow 5001   # Dashboard API
sudo ufw allow 8765   # Signal API
sudo ufw enable
```

---

## 📝 常用命令

### 在阿里云服务器上

```bash
# 查看服务状态
sudo systemctl status alpha-quant

# 重启服务
sudo systemctl restart alpha-quant

# 查看日志
sudo journalctl -u alpha-quant -f

# 或查看应用日志
tail -f /tmp/alpha.log
```

### 在本地

```bash
# 强制触发部署
git push --force origin master

# 查看远程状态
git remote -v
```

---

## 🔐 安全建议

1. **使用 SSH Key 认证**（替代密码）
   ```bash
   # 生成本地 SSH Key
   ssh-keygen -t ed25519 -C "your_email"
   
   # 复制公钥到服务器
   ssh-copy-id root@120.76.55.222
   
   # 在 GitHub Secrets 中移除密码，只保留 Key 认证
   ```

2. **使用只读 Deploy Token**
   - 创建 GitHub Personal Access Token
   - 在服务器上配置只读访问

3. **限制 IP 访问**
   - 在阿里云安全组中限制 SSH 访问来源 IP

---

## ❓ 故障排除

### 部署失败
1. 检查 GitHub Actions 日志
2. 确认服务器 SSH 连接正常
3. 验证 Secrets 配置正确

### 服务启动失败
```bash
# 在服务器上手动测试
cd /opt/alpha
python3 dashboard.py
```

### 依赖安装失败
```bash
# 在服务器上手动安装
pip3 install -r requirements.txt --break-system-packages
```

---

## 📞 支持

如有问题，请检查：
1. GitHub Actions 日志
2. 阿里云服务器日志
3. 服务运行状态
