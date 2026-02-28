# 系统性能优化指南

## 已实施的优化

### 1. 数据缓存 ✅
- **实现**: 交易日历使用本地JSON缓存
- **效果**: 减少重复获取交易日历的API调用
- **文件**: `modules/trade_calendar.py`

### 2. 异步处理 ✅
- **实现**: 通知服务异步发送
- **效果**: 推送不阻塞主流程
- **文件**: `modules/notifier.py`

### 3. 连接池 ✅
- **实现**: 同花顺SDK长连接保持
- **效果**: 减少重复登录开销
- **文件**: `data_gateway.py`

### 4. 日志异步 ✅
- **实现**: Loguru enqueue=True
- **效果**: 日志写入不阻塞
- **配置**: 所有模块已配置

### 5. 进程守护 ✅
- **实现**: tmux + 自动重启脚本
- **效果**: 进程异常自动恢复
- **文件**: `start_gateway_gunicorn.sh`, `health_checker.py`

## 待实施的优化

### 1. Redis缓存高频接口
```bash
# 安装Redis
apt-get install redis-server

# 配置环境变量
export REDIS_URL=redis://127.0.0.1:6379/0
```

**预期效果**: 减少80%重复请求

### 2. 使用Gunicorn替代Flask开发服务器
```bash
# 已安装，使用以下命令启动
cd /root/.openclaw/workspace/alpha-quant
./start_gateway_gunicorn.sh
```

**预期效果**: 响应速度提升3-5倍

### 3. 使用Supervisor管理进程
```bash
# 安装supervisor
pip install supervisor

# 启动
supervisord -c supervisor.conf

# 管理命令
supervisorctl status
supervisorctl restart data_gateway
```

**预期效果**: 进程异常自动重启

### 4. 数据压缩
```bash
# 已启用Flask-Compress
# 自动gzip压缩响应数据
```

**预期效果**: 传输体积减少60%

## 性能监控

### 当前性能指标
```bash
# 测试响应时间
curl -w "@curl-format.txt" -o /dev/null -s http://127.0.0.1:8766/api/health

# 监控资源使用
htop
```

### 优化目标
| 指标 | 当前 | 目标 | 优化后 |
|------|------|------|--------|
| API响应时间 | ~500ms | <100ms | 使用Gunicorn |
| 并发连接 | 1 | 100+ | 连接池 |
| 缓存命中率 | 0% | 80%+ | Redis |
| 进程稳定性 | 手动 | 自动 | Supervisor |

## 快速启动优化版

```bash
cd /root/.openclaw/workspace/alpha-quant

# 1. 安装依赖
pip install gunicorn redis flask-compress

# 2. 启动Redis（如需要缓存）
redis-server --daemonize yes

# 3. 使用Gunicorn启动数据网关
./start_gateway_gunicorn.sh

# 4. 或使用Supervisor管理所有服务
supervisord -c supervisor.conf
```

## 性能测试

```bash
# 压力测试
ab -n 1000 -c 10 http://127.0.0.1:8766/api/health

# 或
wrk -t12 -c400 -d30s http://127.0.0.1:8766/api/health
```
