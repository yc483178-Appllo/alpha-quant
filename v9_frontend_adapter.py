#!/usr/bin/env python3
"""
Alpha V9.0 前端数据适配层 - 简化版
直接插入到 index.html 的 init() 函数中
"""

frontend_adapter = '''
  // ═══════════════════════════════════════════════════════════
  // V9.0 全面真实数据接入 - 前端适配层
  // ═══════════════════════════════════════════════════════════
  
  function loadAllRealData() {
    console.log('[V9.0] 开始加载全面真实数据...');
    
    // 持仓数据
    apiGet('/api/positions/all', function(resp) {
      if(resp && resp.data) { S.positions = resp.data; try { renderPositions(); } catch(e) {} }
    });
    
    // 全量信号
    apiGet('/api/signals/all', function(resp) {
      if(resp && resp.data) { S.signals = resp.data; try { renderSignals(); renderSigTicker(); } catch(e) {} }
    });
    
    // 券商状态
    apiGet('/api/brokers/status', function(resp) {
      if(resp && resp.data) { S.brokers = resp.data; try { renderBrokers(); } catch(e) {} }
    });
    
    // 执行日志
    apiGet('/api/execution/log', function(resp) {
      if(resp && resp.data) { S.execLog = resp.data; try { renderExecLogV41(); } catch(e) {} }
    });
    
    // 真实因子库
    apiGet('/api/factor/real_library', function(resp) {
      if(resp && resp.data) { S.factorLib = resp.data; try { renderFactorLibV41(); } catch(e) {} }
    });
    
    // 模拟盘账户
    apiGet('/api/paper/accounts_real', function(resp) {
      if(resp && resp.data) { S.paperAccounts = resp.data; try { renderLivePerf(); } catch(e) {} }
    });
    
    // 实盘账户
    apiGet('/api/live/accounts_real', function(resp) {
      if(resp && resp.data) { S.liveAccounts = resp.data; }
    });
    
    // 合规规则
    apiGet('/api/compliance/rules_real', function(resp) {
      if(resp && resp.data) { S.complianceRules = resp.data; try { renderComplianceRules(); } catch(e) {} }
    });
    
    // AI模型
    apiGet('/api/ai/models_real', function(resp) {
      if(resp && resp.data) { S.aiModels = resp.data; try { renderAIGateway(); } catch(e) {} }
    });
    
    // Pareto前沿
    apiGet('/api/evolution/pareto_real', function(resp) {
      if(resp && resp.data) { S._paretoData = resp.data; }
    });
    
    // 回测结果
    apiGet('/api/backtest/result_real', function(resp) {
      if(resp && resp.data) { S.btResult = resp.data; try { renderBtTradesV41(); } catch(e) {} }
    });
    
    // Meta-RL
    apiGet('/api/drl/meta_rl_real', function(resp) {
      if(resp && resp.data) { S._metaRLData = resp.data; }
    });
    
    // Brinson归因
    apiGet('/api/attribution/brinson_real', function(resp) {
      if(resp && resp.data) { S._brinsonData = resp.data; S.brinsonSectors = resp.data; try { renderBrinsonTable(); } catch(e) {} }
    });
    
    // 因子IC时序
    apiGet('/api/factor/ic_timeseries', function(resp) {
      if(resp && resp.data) { S._factorICData = resp.data; try { updateChartsV41(); } catch(e) {} }
    });
    
    // 策略Agent
    apiGet('/api/strategy/agents_real', function(resp) {
      if(resp && resp.data) { S.strategyAgents = resp.data; try { renderAgentArena(); } catch(e) {} }
    });
    
    // 权益曲线
    apiGet('/api/paper/equity_curve', function(resp) {
      if(resp && resp.data) { S._paperEquity = resp.data; try { updateChartsV41(); } catch(e) {} }
    });
    
    console.log('[V9.0] 全面真实数据加载完成 ✓');
  }
  
  // 启动实时数据加载
  if(API_MODE === 'live') {
    loadAllRealData();
    // 每10秒刷新
    setInterval(loadAllRealData, 10000);
  }
  // ═══════════════════════════════════════════════════════════
'''

print("=" * 70)
print("将此代码插入到 index.html 的 init() 函数中")
print("位置: 在 '// LIVE模式：从API加载真实数据...' 之后")
print("=" * 70)
print(frontend_adapter)
