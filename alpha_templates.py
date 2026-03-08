# Alpha V6.0 完整模板 - 包含所有功能模块
# 保存到服务器

DASHBOARD_V6 = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Alpha Trading System V6.0 - 智能量化交易平台</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        :root {
            --primary: #e94560; --secondary: #0f3460; --accent: #00d9ff;
            --success: #00ff88; --warning: #ffaa00; --danger: #ff4757;
            --dark: #0a0a0a; --card-bg: rgba(255,255,255,0.05);
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 50%, #16213e 100%);
            color: #fff; min-height: 100vh;
        }
        .sidebar {
            position: fixed; left: 0; top: 0; width: 260px; height: 100vh;
            background: rgba(0,0,0,0.5); backdrop-filter: blur(10px);
            border-right: 1px solid rgba(255,255,255,0.1); z-index: 1000; overflow-y: auto;
        }
        .logo { padding: 30px 25px; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .logo h1 { font-size: 24px; color: var(--primary); display: flex; align-items: center; gap: 10px; }
        .logo span { font-size: 12px; color: #888; background: var(--secondary); padding: 4px 12px; border-radius: 20px; }
        .nav-section { padding: 20px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .nav-title { padding: 0 25px; font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 10px; }
        .nav-item { display: flex; align-items: center; padding: 12px 25px; color: #ccc; text-decoration: none; transition: all 0.3s; border-left: 3px solid transparent; cursor: pointer; }
        .nav-item:hover, .nav-item.active { background: rgba(233,69,96,0.1); color: var(--primary); border-left-color: var(--primary); }
        .nav-item i { width: 30px; font-size: 16px; }
        .main-content { margin-left: 260px; min-height: 100vh; }
        .header { background: rgba(0,0,0,0.3); padding: 20px 30px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .header-left { display: flex; align-items: center; gap: 30px; }
        .market-ticker { display: flex; gap: 20px; }
        .ticker-item { display: flex; flex-direction: column; }
        .ticker-item .label { font-size: 11px; color: #888; }
        .ticker-item .value { font-size: 16px; font-weight: bold; }
        .ticker-item .change { font-size: 12px; }
        .positive { color: var(--success); } .negative { color: var(--danger); }
        .header-right { display: flex; align-items: center; gap: 20px; }
        .mode-toggle { display: flex; gap: 10px; background: rgba(255,255,255,0.05); padding: 5px; border-radius: 8px; }
        .mode-btn { padding: 8px 16px; border: none; background: transparent; color: #888; cursor: pointer; border-radius: 5px; font-size: 12px; }
        .mode-btn.active { background: var(--primary); color: white; }
        .content { padding: 30px; }
        .page { display: none; } .page.active { display: block; }
        .overview-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; margin-bottom: 30px; }
        .metric-card { background: var(--card-bg); border-radius: 12px; padding: 20px; border: 1px solid rgba(255,255,255,0.1); }
        .metric-card h3 { font-size: 12px; color: #888; margin-bottom: 10px; }
        .metric-card .value { font-size: 28px; font-weight: bold; color: var(--accent); }
        .metric-card .change { font-size: 13px; margin-top: 5px; }
        .trading-layout { display: grid; grid-template-columns: 1fr 350px; gap: 20px; }
        .chart-area { background: var(--card-bg); border-radius: 12px; padding: 20px; min-height: 500px; }
        .order-panel { background: var(--card-bg); border-radius: 12px; padding: 20px; }
        .order-tabs { display: flex; gap: 10px; margin-bottom: 20px; }
        .order-tab { flex: 1; padding: 10px; border: none; background: rgba(255,255,255,0.05); color: #888; cursor: pointer; border-radius: 5px; }
        .order-tab.buy { background: rgba(0,255,136,0.2); color: var(--success); }
        .order-tab.sell { background: rgba(255,71,87,0.2); color: var(--danger); }
        .order-form .form-group { margin-bottom: 15px; }
        .order-form label { display: block; font-size: 12px; color: #888; margin-bottom: 5px; }
        .order-form input, .order-form select { width: 100%; padding: 12px; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); border-radius: 5px; color: white; font-size: 14px; }
        .submit-btn { width: 100%; padding: 15px; border: none; border-radius: 5px; font-size: 16px; font-weight: bold; cursor: pointer; margin-top: 20px; }
        .submit-btn.buy { background: var(--success); color: #000; } .submit-btn.sell { background: var(--danger); color: white; }
        .positions-table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        .positions-table th, .positions-table td { padding: 12px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
        .positions-table th { font-size: 12px; color: #888; text-transform: uppercase; }
        .btn-action { padding: 5px 12px; border: none; border-radius: 3px; font-size: 11px; cursor: pointer; margin-right: 5px; }
        .btn-buy { background: var(--success); color: #000; } .btn-sell { background: var(--danger); color: white; }
        .strategy-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
        .strategy-card { background: var(--card-bg); border-radius: 12px; padding: 20px; border: 1px solid rgba(255,255,255,0.1); }
        .strategy-card h3 { color: var(--accent); margin-bottom: 10px; }
        .strategy-status { display: flex; align-items: center; gap: 8px; margin: 15px 0; }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; background: var(--success); animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .strategy-params { background: rgba(0,0,0,0.3); padding: 15px; border-radius: 8px; margin: 15px 0; }
        .param-row { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.05); }
        .risk-dashboard { display: grid; grid-template-columns: repeat(2, 1fr); gap: 20px; }
        .risk-gauge { background: var(--card-bg); border-radius: 12px; padding: 30px; text-align: center; }
        .gauge-value { font-size: 48px; font-weight: bold; color: var(--accent); }
        .risk-alerts { background: var(--card-bg); border-radius: 12px; padding: 20px; }
        .alert-item { display: flex; align-items: center; gap: 15px; padding: 15px; background: rgba(255,71,87,0.1); border-left: 3px solid var(--danger); border-radius: 5px; margin-bottom: 10px; }
        .sentiment-dashboard { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; }
        .sentiment-card { background: var(--card-bg); border-radius: 12px; padding: 20px; text-align: center; }
        .sentiment-score { font-size: 48px; font-weight: bold; }
        .sentiment-score.positive { color: var(--success); } .sentiment-score.negative { color: var(--danger); } .sentiment-score.neutral { color: var(--warning); }
        .hot-topics { grid-column: span 3; background: var(--card-bg); border-radius: 12px; padding: 20px; }
        .topic-tag { display: inline-flex; align-items: center; gap: 8px; padding: 8px 16px; background: rgba(255,255,255,0.1); border-radius: 20px; margin: 5px; font-size: 13px; }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="logo"><h1>⚡ Alpha <span>V6.0</span></h1></div>
        <div class="nav-section">
            <div class="nav-title">主要</div>
            <a class="nav-item active" onclick="showPage('overview')"><i class="fas fa-chart-line"></i> 概览看板</a>
            <a class="nav-item" onclick="showPage('trading')"><i class="fas fa-exchange-alt"></i> 模拟交易</a>
            <a class="nav-item" onclick="showPage('positions')"><i class="fas fa-wallet"></i> 持仓管理</a>
        </div>
        <div class="nav-section">
            <div class="nav-title">策略与研究</div>
            <a class="nav-item" onclick="showPage('strategy')"><i class="fas fa-brain"></i> 策略引擎</a>
            <a class="nav-item" onclick="showPage('backtest')"><i class="fas fa-history"></i> 回测中心</a>
            <a class="nav-item" onclick="showPage('optimization')"><i class="fas fa-balance-scale"></i> 组合优化</a>
        </div>
        <div class="nav-section">
            <div class="nav-title">风控与数据</div>
            <a class="nav-item" onclick="showPage('risk')"><i class="fas fa-shield-alt"></i> 风险管理</a>
            <a class="nav-item" onclick="showPage('sentiment')"><i class="fas fa-comments"></i> 舆情分析</a>
            <a class="nav-item" onclick="showPage('data')"><i class="fas fa-database"></i> 数据中心</a>
        </div>
        <div class="nav-section">
            <div class="nav-title">系统</div>
            <a class="nav-item" onclick="showPage('settings')"><i class="fas fa-cog"></i> 设置</a>
            <a class="nav-item" href="/api/logs"><i class="fas fa-file-alt"></i> 日志</a>
        </div>
    </div>
    <div class="main-content">
        <div class="header">
            <div class="header-left">
                <div class="market-ticker">
                    <div class="ticker-item"><span class="label">上证指数</span><span class="value">3,089.25</span><span class="change positive">+0.40%</span></div>
                    <div class="ticker-item"><span class="label">深证成指</span><span class="value">9,876.54</span><span class="change positive">+0.46%</span></div>
                    <div class="ticker-item"><span class="label">创业板指</span><span class="value">2,045.67</span><span class="change positive">+1.16%</span></div>
                </div>
            </div>
            <div class="header-right">
                <div class="mode-toggle"><button class="mode-btn active">模拟</button><button class="mode-btn">实盘</button></div>
                <span style="color: #888;"><i class="fas fa-circle" style="color: #00ff88; font-size: 8px;"></i> 系统运行中</span>
            </div>
        </div>
        <div class="content">
            <div id="overview" class="page active">
                <div class="overview-grid">
                    <div class="metric-card"><h3>总资产</h3><div class="value">¥1,245,678.90</div><div class="change positive">+15.67%</div></div>
                    <div class="metric-card"><h3>日收益</h3><div class="value" style="color: var(--success);">+1.23%</div><div class="change">¥15,234.56</div></div>
                    <div class="metric-card"><h3>持仓市值</h3><div class="value" style="color: var(--accent);">¥987,654.32</div><div class="change">12 只股票</div></div>
                    <div class="metric-card"><h3>可用资金</h3><div class="value">¥258,024.58</div><div class="change">现金比例 20.7%</div></div>
                </div>
                <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 20px;">
                    <div class="chart-area"><h3 style="margin-bottom: 20px;"><i class="fas fa-chart-area"></i> 收益曲线</h3><canvas id="pnlChart"></canvas></div>
                    <div style="background: var(--card-bg); border-radius: 12px; padding: 20px;">
                        <h3 style="margin-bottom: 20px;"><i class="fas fa-list"></i> 今日信号</h3>
                        <div style="padding: 12px; background: rgba(0,0,0,0.3); border-radius: 8px; margin-bottom: 10px; border-left: 3px solid var(--success);">
                            <div style="display: flex; justify-content: space-between;"><strong>000001</strong><span style="color: var(--success);">BUY</span></div>
                            <div style="font-size: 12px; color: #888;">动量策略 | 置信度 85%</div>
                        </div>
                        <div style="padding: 12px; background: rgba(0,0,0,0.3); border-radius: 8px; margin-bottom: 10px; border-left: 3px solid var(--danger);">
                            <div style="display: flex; justify-content: space-between;"><strong>000002</strong><span style="color: var(--danger);">SELL</span></div>
                            <div style="font-size: 12px; color: #888;">止损触发 | 盈亏 -5.2%</div>
                        </div>
                    </div>
                </div>
            </div>
            <div id="trading" class="page">
                <div class="trading-layout">
                    <div class="chart-area">
                        <h3 style="margin-bottom: 20px;"><i class="fas fa-chart-candlestick"></i> K线图</h3>
                        <canvas id="klineChart"></canvas>
                        <div style="margin-top: 20px;">
                            <input type="text" id="stock-search" placeholder="输入股票代码/名称..." style="width: 100%; padding: 12px; background: rgba(0,0,0,0.3); border: 1px solid rgba(255,255,255,0.1); border-radius: 5px; color: white;">
                        </div>
                    </div>
                    <div class="order-panel">
                        <div class="order-tabs">
                            <button class="order-tab buy active" onclick="switchOrderType('buy')">买入</button>
                            <button class="order-tab sell" onclick="switchOrderType('sell')">卖出</button>
                        </div>
                        <form class="order-form" id="order-form" onsubmit="submitOrder(event)">
                            <div class="form-group"><label>股票代码</label><input type="text" id="symbol" placeholder="如: 000001" required></div>
                            <div class="form-group"><label>股票名称</label><input type="text" id="stock-name" placeholder="自动识别" readonly></div>
                            <div class="form-group"><label>最新价格</label><input type="text" id="current-price" placeholder="--" readonly style="color: var(--accent);"></div>
                            <div class="form-group"><label>委托价格</label><input type="number" id="order-price" step="0.01" required></div>
                            <div class="form-group"><label>委托数量</label><input type="number" id="quantity" min="100" step="100" required></div>
                            <div style="background: rgba(0,0,0,0.3); padding: 15px; border-radius: 8px; margin: 15px 0;">
                                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;"><span style="color: #888;">预计金额</span><span id="estimated-amount">¥0.00</span></div>
                                <div style="display: flex; justify-content: space-between; margin-bottom: 8px;"><span style="color: #888;">手续费</span><span style="color: #888;">¥0.00</span></div>
                                <div style="display: flex; justify-content: space-between;"><span style="color: #888;">印花税</span><span style="color: #888;">¥0.00</span></div>
                            </div>
                            <button type="submit" class="submit-btn buy" id="submit-btn">买入</button>
                        </form>
                    </div>
                </div>
            </div>
            <div id="positions" class="page">
                <h2 style="margin-bottom: 20px;"><i class="fas fa-wallet"></i> 持仓详情</h2>
                <table class="positions-table">
                    <thead><tr><th>股票</th><th>持仓量</th><th>成本价</th><th>现价</th><th>市值</th><th>盈亏</th><th>盈亏率</th><th>操作</th></tr></thead>
                    <tbody>
                        <tr><td><strong>000001</strong><div style="font-size: 11px; color: #888;">平安银行</div></td><td>1000</td><td>¥12.50</td><td style="color: var(--accent);">¥13.80</td><td>¥13,800</td><td style="color: var(--success);">+¥1,300</td><td style="color: var(--success);">+10.4%</td><td><button class="btn-action btn-buy" onclick="quickTrade('000001', 'buy')">加仓</button><button class="btn-action btn-sell" onclick="quickTrade('000001', 'sell')">卖出</button></td></tr>
                        <tr><td><strong>000002</strong><div style="font-size: 11px; color: #888;">万科A</div></td><td>500</td><td>¥18.20</td><td style="color: var(--accent);">¥17.50</td><td>¥8,750</td><td style="color: var(--danger);">-¥350</td><td style="color: var(--danger);">-3.8%</td><td><button class="btn-action btn-buy" onclick="quickTrade('000002', 'buy')">加仓</button><button class="btn-action btn-sell" onclick="quickTrade('000002', 'sell')">卖出</button></td></tr>
                    </tbody>
                </table>
                <h2 style="margin: 30px 0 20px;"><i class="fas fa-history"></i> 成交记录</h2>
                <table class="positions-table">
                    <thead><tr><th>时间</th><th>股票</th><th>操作</th><th>价格</th><th>数量</th><th>金额</th><th>手续费</th><th>盈亏</th></tr></thead>
                    <tbody>
                        <tr><td>2026-03-07 10:30:15</td><td>000001</td><td style="color: var(--success);">BUY</td><td>¥12.50</td><td>1000</td><td>¥12,500</td><td style="color: #888;">¥5.00</td><td style="color: #888;">--</td></tr>
                        <tr><td>2026-03-07 14:15:22</td><td>000002</td><td style="color: var(--danger);">SELL</td><td>¥17.50</td><td>500</td><td>¥8,750</td><td style="color: #888;">¥13.75</td><td style="color: var(--danger);">-¥350</td></tr>
                    </tbody>
                </table>
            </div>
            <div id="strategy" class="page">
                <h2 style="margin-bottom: 20px;"><i class="fas fa-brain"></i> 策略引擎</h2>
                <div class="strategy-grid">
                    <div class="strategy-card"><h3>动量策略</h3><p style="color: #888; font-size: 13px;">基于价格动量的趋势跟踪策略</p><div class="strategy-status"><div class="status-dot"></div><span style="color: var(--success);">运行中</span></div><div class="strategy-params"><div class="param-row"><span style="color: #888;">lookback</span><span style="color: var(--accent);">20</span></div><div class="param-row"><span style="color: #888;">threshold</span><span style="color: var(--accent);">0.05</span></div></div><button style="width: 100%; padding: 10px; background: var(--secondary); border: none; border-radius: 5px; color: white; cursor: pointer; margin-top: 10px;">配置参数</button></div>
                    <div class="strategy-card"><h3>均值回归</h3><p style="color: #888; font-size: 13px;">基于统计套利的均值回归策略</p><div class="strategy-status"><div class="status-dot"></div><span style="color: var(--success);">运行中</span></div><div class="strategy-params"><div class="param-row"><span style="color: #888;">window</span><span style="color: var(--accent);">30</span></div><div class="param-row"><span style="color: #888;">std_threshold</span><span style="color: var(--accent);">2.0</span></div></div><button style="width: 100%; padding: 10px; background: var(--secondary); border: none; border-radius: 5px; color: white; cursor: pointer; margin-top: 10px;">配置参数</button></div>
                    <div class="strategy-card"><h3>突破策略</h3><p style="color: #888; font-size: 13px;">基于支撑阻力位的突破策略</p><div class="strategy-status"><div class="status-dot"></div><span style="color: var(--success);">运行中</span></div><div class="strategy-params"><div class="param-row"><span style="color: #888;">period</span><span style="color: var(--accent);">60</span></div><div class="param-row"><span style="color: #888;">volume_factor</span><span style="color: var(--accent);">1.5</span></div></div><button style="width: 100%; padding: 10px; background: var(--secondary); border: none; border-radius: 5px; color: white; cursor: pointer; margin-top: 10px;">配置参数</button></div>
                </div>
            </div>
            <div id="risk" class="page">
                <h2 style="margin-bottom: 20px;"><i class="fas fa-shield-alt"></i> 风险管理</h2>
                <div class="risk-dashboard">
                    <div class="risk-gauge"><h3 style="margin-bottom: 20px;">风险等级</h3><div class="gauge-value" style="color: var(--warning);">中等</div><div style="margin-top: 20px; color: #888;">当前组合风险可控</div></div>
                    <div class="risk-gauge"><h3 style="margin-bottom: 20px;">最大回撤</h3><div class="gauge-value" style="color: var(--success);">8.5%</div><div style="margin-top: 20px; color: #888;">历史最大 12.3%</div></div>
                    <div class="risk-alerts" style="grid-column: span 2;"><h3 style="margin-bottom: 20px;"><i class="fas fa-exclamation-triangle"></i> 风险告警</h3><div class="alert-item"><i class="fas fa-info-circle" style="color: var(--warning);"></i><div><div>单只股票仓位超过 20%</div><div style="font-size: 12px; color: #888;">建议分散持仓</div></div></div><div class="alert-item"><i class="fas fa-check-circle" style="color: var(--success);"></i><div><div>止损机制正常运行</div><div style="font-size: 12px; color: #888;">今日触发 0 次</div></div></div></div>
                </div>
            </div>
            <div id="sentiment" class="page">
                <h2 style="margin-bottom: 20px;"><i class="fas fa-comments"></i> 舆情分析</h2>
                <div class="sentiment-dashboard">
                    <div class="sentiment-card"><h3>市场整体情绪</h3><div class="sentiment-score positive">68.5</div><div style="color: var(--success);">偏乐观</div></div>
                    <div class="sentiment-card"><h3>新闻舆情</h3><div class="sentiment-score positive">72.3</div><div style="color: var(--success);">正面</div></div>
                    <div class="sentiment-card"><h3>社交媒体</h3><div class="sentiment-score neutral">55.8</div><div style="color: var(--warning);">中性</div></div>
                    <div class="hot-topics"><h3 style="margin-bottom: 15px;"><i class="fas fa-fire"></i> 热点话题</h3><div><span class="topic-tag">人工智能 <span style="color: var(--success);">▲ 3.45%</span></span><span class="topic-tag">新能源 <span style="color: var(--success);">▲ 2.12%</span></span><span class="topic-tag">半导体 <span style="color: var(--success);">▲ 1.89%</span></span><span class="topic-tag">医药生物 <span style="color: var(--danger);">▼ 0.56%</span></span><span class="topic-tag">银行 <span style="color: var(--danger);">▼ 0.23%</span></span></div></div>
                </div>
            </div>
            <div id="backtest" class="page"><h2>回测中心</h2><p style="color: #888;">历史策略回测功能开发中...</p></div>
            <div id="optimization" class="page"><h2>组合优化</h2><p style="color: #888;">资产配置优化功能开发中...</p></div>
            <div id="data" class="page"><h2>数据中心</h2><p style="color: #888;">数据管理功能开发中...</p></div>
            <div id="settings" class="page"><h2>系统设置</h2><p style="color: #888;">设置功能开发中...</p></div>
        </div>
    </div>
    <script>
        function showPage(pageId) {
            document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
            document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
            document.getElementById(pageId).classList.add('active');
            event.target.closest('.nav-item').classList.add('active');
        }
        let currentOrderType = 'buy';
        function switchOrderType(type) {
            currentOrderType = type;
            document.querySelectorAll('.order-tab').forEach(t => t.classList.remove('active'));
            event.target.classList.add('active');
            document.getElementById('submit-btn').className = 'submit-btn ' + type;
            document.getElementById('submit-btn').textContent = type === 'buy' ? '买入' : '卖出';
        }
        function submitOrder(e) {
            e.preventDefault();
            const symbol = document.getElementById('symbol').value;
            const price = document.getElementById('order-price').value;
            const quantity = document.getElementById('quantity').value;
            fetch('/api/paper-trade', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: currentOrderType.toUpperCase(), symbol: symbol, price: parseFloat(price), quantity: parseInt(quantity)})
            }).then(r => r.json()).then(data => {
                alert(data.status === 'filled' ? '交易成功!' : data.reason);
                location.reload();
            });
        }
        function quickTrade(symbol, type) {
            document.getElementById('symbol').value = symbol;
            showPage('trading');
            switchOrderType(type);
        }
        document.addEventListener('DOMContentLoaded', function() {
            new Chart(document.getElementById('pnlChart'), {
                type: 'line',
                data: {labels: ['09:30', '10:00', '10:30', '11:00', '11:30', '13:00', '13:30', '14:00', '14:30', '15:00'], datasets: [{label: '今日收益', data: [0, 0.3, 0.8, 0.5, 1.2, 0.9, 1.5, 1.1, 1.4, 1.23], borderColor: '#00ff88', backgroundColor: 'rgba(0,255,136,0.1)', fill: true, tension: 0.4}]},
                options: {responsive: true, maintainAspectRatio: false, plugins: {legend: {display: false}}, scales: {y: {grid: {color: 'rgba(255,255,255,0.1)'}, ticks: {color: '#888'}}, x: {grid: {display: false}, ticks: {color: '#888'}}}}
            });
        });
    </script>
</body>
</html>'''
