# Alpha-Genesis V6.0 域名与CDN架构规划
# 当前状态: 阿里云IP直链 (http://101.126.150.200/v3/)
# 目标架构: Cloudflare + 阿里云 双栈部署

═══════════════════════════════════════════════════════════════════
## 一、推荐域名架构
═══════════════════════════════════════════════════════════════════

### 方案A: 单域名路径式 (推荐)
```
主域名:     alpha.yourdomain.com
├── /v3/          → 看板V3.0主界面
├── /api/v3/      → REST API端点
├── /ws/          → WebSocket实时数据
└── /static/      → 静态资源CDN加速
```

### 方案B: 子域名分离式
```
dashboard.alpha.yourdomain.com    → 看板V3.0
api.alpha.yourdomain.com          → REST API
ws.alpha.yourdomain.com           → WebSocket
reports.alpha.yourdomain.com      → 投研报告
```

### 方案C: 环境分离式 (生产环境推荐)
```
生产环境:
  alpha.yourdomain.com            → 生产看板
  api.alpha.yourdomain.com        → 生产API
  
测试环境:
  alpha-staging.yourdomain.com    → 测试看板
  api-staging.alpha.yourdomain.com → 测试API
```

═══════════════════════════════════════════════════════════════════
## 二、Cloudflare配置清单
═══════════════════════════════════════════════════════════════════

### 1. DNS记录配置
```
Type    Name              Value                  TTL    Proxy
A       alpha             101.126.150.200        Auto   🟠 Proxied
A       api               101.126.150.200        Auto   🟠 Proxied
A       ws                101.126.150.200        Auto   🟠 Proxied
```

### 2. SSL/TLS设置
```
模式: Full (Strict)
├── 始终使用HTTPS: ✅ 开启
├── 自动HTTPS重写: ✅ 开启
├── HSTS: ✅ 开启 (max-age: 31536000)
├── 最低TLS版本: 1.2
└── 加密模式: 现代 (AES-128-GCM-SHA256)
```

### 3. 速度优化
```
├── 自动压缩: ✅ 开启 (Brotli)
├── 早期提示: ✅ 开启 (103 Early Hints)
├── Rocket Loader: ⚠️ 测试后开启 (可能影响JS)
├── 0-RTT连接恢复: ✅ 开启
└── 智能路由: ✅ 开启 (Argo Smart Routing)
```

### 4. 缓存规则 (Page Rules)
```
规则1: 静态资源缓存
  URL: alpha.yourdomain.com/static/*
  缓存级别: 缓存所有内容
  边缘TTL: 7天
  浏览器TTL: 1天

规则2: API不缓存
  URL: alpha.yourdomain.com/api/*
  缓存级别: 绕过

规则3: WebSocket不缓存
  URL: alpha.yourdomain.com/ws/*
  缓存级别: 绕过

规则4: 看板主页面
  URL: alpha.yourdomain.com/v3/*
  缓存级别: 标准
  边缘TTL: 1小时
```

### 5. 安全设置
```
├── 安全级别: 高
├── 质询通过期: 1小时
├── 浏览器完整性检查: ✅ 开启
├── WAF: ✅ 开启 (托管规则集)
├── DDoS防护: ✅ 开启 (自动)
├── Bot管理: ✅ 开启
└── Rate Limiting:
    ├── API限制: 100次/分钟
    ├── 登录限制: 10次/分钟
    └── 全局限制: 1000次/分钟
```

═══════════════════════════════════════════════════════════════════
## 三、Nginx配置 (配合Cloudflare)
═══════════════════════════════════════════════════════════════════

```nginx
# /etc/nginx/sites-available/alpha-dashboard

server {
    listen 80;
    listen [::]:80;
    
    # 方案A: 单域名
    server_name alpha.yourdomain.com;
    
    # Cloudflare真实IP
    set_real_ip_from 103.21.244.0/22;
    set_real_ip_from 103.22.200.0/22;
    set_real_ip_from 103.31.4.0/22;
    set_real_ip_from 104.16.0.0/13;
    set_real_ip_from 104.24.0.0/14;
    set_real_ip_from 108.162.192.0/18;
    set_real_ip_from 131.0.72.0/22;
    set_real_ip_from 141.101.64.0/18;
    set_real_ip_from 162.158.0.0/15;
    set_real_ip_from 172.64.0.0/13;
    set_real_ip_from 173.245.48.0/20;
    set_real_ip_from 188.114.96.0/20;
    set_real_ip_from 190.93.240.0/20;
    set_real_ip_from 197.234.240.0/22;
    set_real_ip_from 198.41.128.0/17;
    set_real_ip_from 2400:cb00::/32;
    set_real_ip_from 2606:4700::/32;
    set_real_ip_from 2803:f800::/32;
    set_real_ip_from 2405:b500::/32;
    set_real_ip_from 2405:8100::/32;
    real_ip_header CF-Connecting-IP;
    
    # 强制HTTPS (Cloudflare已处理时可省略)
    # return 301 https://$server_name$request_uri;
    
    # 看板V3.0
    location /v3/ {
        alias /var/www/alpha-dashboard/v3/;
        index dashboard_v3.html;
        try_files $uri $uri/ =404;
        
        # 缓存控制
        expires 1h;
        add_header Cache-Control "public, must-revalidate";
    }
    
    # API代理到数据桥接服务
    location /api/v3/ {
        proxy_pass http://127.0.0.1:5002/v3/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # 禁用缓存
        add_header Cache-Control "no-cache, no-store, must-revalidate";
        
        # 超时设置
        proxy_connect_timeout 5s;
        proxy_send_timeout 10s;
        proxy_read_timeout 30s;
    }
    
    # WebSocket代理
    location /ws/ {
        proxy_pass http://127.0.0.1:5002/ws/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
    
    # 静态资源
    location /static/ {
        alias /var/www/alpha-dashboard/static/;
        expires 7d;
        add_header Cache-Control "public, immutable";
    }
    
    # 健康检查
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}

# HTTPS配置 (如果使用Cloudflare Origin CA证书)
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    
    server_name alpha.yourdomain.com;
    
    # Cloudflare Origin CA证书
    ssl_certificate /etc/ssl/certs/cloudflare_origin.pem;
    ssl_certificate_key /etc/ssl/private/cloudflare_origin.key;
    
    # SSL优化
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-ECDSA-AES128-GCM-SHA256:ECDHE-RSA-AES128-GCM-SHA256:ECDHE-ECDSA-AES256-GCM-SHA384:ECDHE-RSA-AES256-GCM-SHA384;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    
    # 包含上述location配置
    include /etc/nginx/snippets/alpha-locations.conf;
}
```

═══════════════════════════════════════════════════════════════════
## 四、数据桥接服务配置
═══════════════════════════════════════════════════════════════════

```python
# alpha_dashboard_server_v3.py 配置更新

# 支持Cloudflare真实IP
from flask import Flask, request

app = Flask(__name__)

@app.before_request
def log_real_ip():
    """记录Cloudflare传递的真实IP"""
    cf_ip = request.headers.get('CF-Connecting-IP')
    real_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    app.logger.info(f"Request from: {cf_ip or real_ip}")

# CORS配置 (允许Cloudflare域名)
from flask_cors import CORS
CORS(app, origins=[
    "https://alpha.yourdomain.com",
    "https://*.yourdomain.com"
])

# 运行配置
if __name__ == '__main__':
    app.run(
        host='127.0.0.1',  # 仅本地监听，Nginx代理
        port=5002,
        threaded=True
    )
```

═══════════════════════════════════════════════════════════════════
## 五、部署检查清单
═══════════════════════════════════════════════════════════════════

### 步骤1: 域名购买与配置
- [ ] 购买域名 (yourdomain.com)
- [ ] 在Cloudflare添加域名
- [ ] 修改域名DNS为Cloudflare提供的服务器
- [ ] 等待DNS生效 (通常5分钟-24小时)

### 步骤2: Cloudflare基础配置
- [ ] 添加A记录指向101.126.150.200
- [ ] 开启橙色云朵 (Proxied)
- [ ] 配置SSL/TLS为Full (Strict)
- [ ] 开启Always Use HTTPS

### 步骤3: 服务器配置
- [ ] 生成Cloudflare Origin CA证书
- [ ] 安装证书到服务器
- [ ] 更新Nginx配置
- [ ] 测试Nginx配置: nginx -t
- [ ] 重启Nginx: systemctl restart nginx

### 步骤4: 应用配置更新
- [ ] 更新数据桥接服务CORS设置
- [ ] 重启数据桥接服务
- [ ] 测试所有API端点
- [ ] 测试WebSocket连接

### 步骤5: 性能优化
- [ ] 配置Page Rules缓存策略
- [ ] 开启Brotli压缩
- [ ] 开启HTTP/2和HTTP/3
- [ ] 配置Argo Smart Routing (可选)

### 步骤6: 安全加固
- [ ] 配置WAF规则
- [ ] 设置Rate Limiting
- [ ] 开启Bot Management
- [ ] 配置IP白名单 (管理后台)

═══════════════════════════════════════════════════════════════════
## 六、V6.0新增API端点
═══════════════════════════════════════════════════════════════════

```
看板V3.0 API端点 (已部署):

# 基础端点
GET  /v3/api/portfolio/regime          → 市场政权数据
POST /v3/api/portfolio/optimize        → 组合优化
GET  /v3/api/sentiment/events          → 舆情事件列表
POST /v3/api/sentiment/events          → 提交舆情事件

# V6.0新增端点 (需配置)
GET  /api/v3/evolution                 → 策略进化数据
GET  /api/v3/research                  → 投研报告列表
GET  /api/v3/broker                    → 券商管理数据
GET  /api/v3/history                   → 历史查询接口
GET  /api/v3/drill/{id}                → 钻取数据查询
POST /api/v3/broker/switch             → 券商切换指令
POST /api/v3/report/generate           → 触发生成报告
```

═══════════════════════════════════════════════════════════════════
## 七、访问地址对比
═══════════════════════════════════════════════════════════════════

### 当前 (IP直链)
```
http://101.126.150.200/v3/
```
⚠️ 缺点: 不安全、无CDN、暴露源站IP

### 配置后 (Cloudflare)
```
https://alpha.yourdomain.com/v3/
```
✅ 优点: HTTPS安全、全球CDN、DDoS防护、隐藏源站

═══════════════════════════════════════════════════════════════════
## 八、成本估算
═══════════════════════════════════════════════════════════════════

| 项目 | 费用 | 说明 |
|------|------|------|
| 域名 | ¥50-100/年 | .com/.cn域名 |
| Cloudflare Free | ¥0 | 基础CDN+SSL |
| Cloudflare Pro | $20/月 | WAF+高级分析 |
| 阿里云ECS | 现有 | 已部署 |
| 流量费用 | 现有 | 出站流量 |

建议: 先用Free套餐，需要WAF时再升级Pro

═══════════════════════════════════════════════════════════════════
