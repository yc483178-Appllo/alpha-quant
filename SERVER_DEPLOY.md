# ⚠️ 阿里云轻量服务器 - 关键配置

## 服务器信息（重要！务必记住！）
- **服务器类型**: 阿里云轻量服务器
- **公网 IP**: 120.76.55.222 ⚠️
- **私网 IP**: 172.17.39.97 ⚠️
- **用户名**: root
- **密码**: Yfc244083
- **SSH**: `ssh root@120.76.55.222`

## Caddy 配置（绝对不能搞错！）

### Web 根目录
```
/opt/alpha/v3/     ← 看板 V3/V6 主目录
/opt/alpha/        ← API 和其他文件根目录
```

### Caddyfile 位置
```
/etc/caddy/Caddyfile
```

### 关键配置
```caddy
# v3 仪表盘 - 重要！root 指向 /opt/alpha/v3
handle /v3/* {
    root * /opt/alpha/v3        ← ⚠️ 记住这个路径！
    uri strip_prefix /v3
    file_server
    encode gzip
}
```

## 文件部署位置（重要！）

| 文件 | 正确位置 | 说明 |
|------|----------|------|
| index.html | `/opt/alpha/v3/index.html` | 看板主文件 |
| dashboard_v31_*.js | `/opt/alpha/v3/` | JavaScript 文件 |
| API 服务器 | `/opt/alpha/` | Python 后端 |

## 错误路径（千万不要用！）
❌ `/var/www/alpha-dashboard/v3/` - 这是错误路径，Caddy 不指向这里

## 部署流程
1. 文件上传到 `/opt/alpha/v3/`
2. 重启 Caddy: `systemctl restart caddy`
3. 验证: `curl http://120.76.55.222/v3/`

## 访问地址
```
http://120.76.55.222/v3/
```

---
**最后更新**: 2026-03-09
**状态**: V6.1 已部署
