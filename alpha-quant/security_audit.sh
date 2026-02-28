#!/bin/bash
# security_audit.sh - 安全配置审计

cd /root/.openclaw/workspace/alpha-quant

echo "🔐 Alpha Quant 安全配置审计"
echo "=============================="

# 1. 检查 .env 文件权限
echo ""
echo "1. 检查 .env 文件权限..."
if [ -f ".env" ]; then
    perms=$(stat -c "%a" .env 2>/dev/null || stat -f "%Lp" .env)
    if [ "$perms" = "600" ] || [ "$perms" = "644" ]; then
        echo "✅ .env 权限正确 ($perms)"
    else
        echo "⚠️ .env 权限为 $perms，建议改为 600"
        chmod 600 .env 2>/dev/null && echo "   已自动修复为 600"
    fi
else
    echo "❌ .env 文件不存在"
fi

# 2. 检查 .gitignore
echo ""
echo "2. 检查 .gitignore..."
if [ -f ".gitignore" ]; then
    if grep -q "\.env" .gitignore; then
        echo "✅ .env 已在 .gitignore 中"
    else
        echo "❌ .env 未在 .gitignore 中"
        echo ".env" >> .gitignore
        echo "   已自动添加"
    fi
else
    echo "⚠️ .gitignore 不存在，创建中..."
    cat > .gitignore << 'EOF'
.env
.env.local
*.log
__pycache__/
*.pyc
.DS_Store
cloud_storage/
backups/
EOF
    echo "✅ .gitignore 已创建"
fi

# 3. 检查硬编码密钥（简单检查）
echo ""
echo "3. 检查硬编码密钥..."
# 检查常见的密钥模式
suspicious=$(grep -r "sk-[a-zA-Z0-9]\{20,\}" --include="*.py" . 2>/dev/null | grep -v ".pyc" | head -5)
if [ -n "$suspicious" ]; then
    echo "⚠️ 发现疑似硬编码密钥:"
    echo "$suspicious" | head -3
else
    echo "✅ 未发现明显硬编码密钥"
fi

# 4. 检查人工确认设置
echo ""
echo "4. 检查人工确认设置..."
if [ -f "signal_server.py" ]; then
    if grep -q '"require_human_confirm".*:.*True' signal_server.py; then
        echo "✅ 人工确认已启用 (require_human_confirm=True)"
    else
        echo "⚠️ 人工确认可能未启用，请检查 signal_server.py"
    fi
else
    echo "⚠️ signal_server.py 不存在"
fi

# 5. 检查日志目录
echo ""
echo "5. 检查日志记录..."
if [ -d "logs" ]; then
    log_count=$(ls -1 logs/*.log 2>/dev/null | wc -l)
    if [ $log_count -gt 0 ]; then
        echo "✅ 日志目录正常 ($log_count 个日志文件)"
    else
        echo "⚠️ 日志目录为空"
    fi
else
    echo "⚠️ 日志目录不存在，创建中..."
    mkdir -p logs
    echo "✅ 日志目录已创建"
fi

# 6. 检查敏感文件是否被git跟踪
echo ""
echo "6. 检查Git跟踪状态..."
if [ -d ".git" ]; then
    tracked_env=$(git ls-files .env 2>/dev/null)
    if [ -n "$tracked_env" ]; then
        echo "❌ 警告: .env 文件被Git跟踪！"
        echo "   执行: git rm --cached .env"
    else
        echo "✅ .env 未被Git跟踪"
    fi
else
    echo "⚠️ 不是Git仓库"
fi

# 7. 检查目录权限
echo ""
echo "7. 检查目录权限..."
for dir in "logs" "cloud_storage" "cache"; do
    if [ -d "$dir" ]; then
        echo "✅ $dir 目录存在"
    else
        echo "⚠️ $dir 目录不存在"
    fi
done

echo ""
echo "=============================="
echo "审计完成"
echo ""
echo "建议操作:"
echo "1. 定期执行: ./security_audit.sh"
echo "2. 每周检查日志: tail -f logs/signal_$(date +%Y-%m-%d).log"
echo "3. 阅读安全文档: cat docs/SECURITY.md"
