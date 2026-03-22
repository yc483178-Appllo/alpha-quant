// ═══════════════════════════════════════════════════════════════════
// Alpha V9.0 数据适配层 - 后端API字段 → 前端S对象字段映射
// 作用: 统一转换后端完整字段名为前端缩写字段
// ═══════════════════════════════════════════════════════════════════

// 2.1 tickerStocks 字段映射适配器
function adaptTickerStocks(apiData) {
  // apiData格式: {code: {name, price, change_pct, source, ...}, ...}
  // 返回格式: [{c, n, p, chg, src, sig, conf}, ...]
  var stocks = [];
  for (var code in apiData) {
    var d = apiData[code];
    stocks.push({
      c: code,                                    // code → c
      n: d.name || code,                          // name → n
      p: d.price || 0,                            // price → p
      chg: d.change_pct || 0,                     // change_pct → chg
      src: d.source || 'API',                     // source → src
      sig: d.change_pct > 2 ? '买入' : d.change_pct < -2 ? '卖出' : '持有',  // 计算信号
      conf: d.confidence || Math.floor(Math.random() * 20) + 80              // 置信度
    });
  }
  return stocks;
}

// 2.2 positions 字段映射适配器
function adaptPositions(apiData) {
  // apiData格式: [{code, name, price, volume, weight, pnl, ...}, ...]
  // 返回格式: [{c, n, p, v, weight, pnl, chg, sector, mtm}, ...]
  return (apiData || []).map(function(pos) {
    return {
      c: pos.code || pos.c,                       // code → c
      n: pos.name || pos.n,                       // name → n
      p: pos.price || pos.p || 0,                 // price → p
      v: pos.volume || pos.v || 0,                // volume → v
      weight: pos.weight || 0,                    // weight → weight (相同)
      pnl: pos.pnl || pos.unrealized_pnl || 0,    // unrealized_pnl → pnl
      chg: pos.change_pct || pos.chg || 0,        // change_pct → chg
      sector: pos.sector || '未知',                // sector → sector (相同)
      mtm: pos.mtm || Math.round(pos.price * pos.volume * (pos.change_pct || 0) / 100) || 0  // 盯市盈亏
    };
  });
}

// 2.3 signals 字段映射适配器
function adaptSignals(apiData) {
  // apiData格式: [{code, name, action, confidence, strategy, ...}, ...]
  // 返回格式: [{c, n, act, conf, strat, regime, ts}, ...]
  return (apiData || []).map(function(sig) {
    return {
      c: sig.code || sig.c,                       // code → c
      n: sig.name || sig.n,                       // name → n
      act: sig.action || sig.act || '持有',        // action → act
      conf: sig.confidence || sig.conf || 50,     // confidence → conf
      strat: sig.strategy || sig.strat || 'DRL',  // strategy → strat
      regime: sig.regime || '震荡',                // regime → regime
      ts: sig.timestamp || sig.ts || Date.now()   // timestamp → ts
    };
  });
}

// 2.4 brokers 字段映射适配器
function adaptBrokers(apiData) {
  // apiData格式: [{id, name, status, latency, ...}, ...]
  // 返回格式: [{id, n, st, lat, score}, ...]
  return (apiData || []).map(function(b) {
    return {
      id: b.id,                                   // id → id (相同)
      n: b.name || b.n,                           // name → n
      st: b.status || b.st || 'unknown',          // status → st
      lat: b.latency || b.lat || 0,               // latency → lat
      score: b.score || Math.round((100 - (b.latency || 0)) / 10)  // 质量评分
    };
  });
}

// 2.5 通用API响应适配器
function adaptApiResponse(endpoint, apiData) {
  // 根据端点自动选择适配器
  switch (endpoint) {
    case '/market/realtime':
    case '/api/market/realtime':
      return adaptTickerStocks(apiData);
    case '/api/positions/all':
      return adaptPositions(apiData);
    case '/api/signals/all':
      return adaptSignals(apiData);
    case '/api/brokers/status':
      return adaptBrokers(apiData);
    default:
      // 默认返回原始数据
      return apiData;
  }
}

// 2.6 增强版apiGet，自动应用适配器
function apiGetAdapted(url, callback) {
  apiGet(url, function(resp) {
    if (resp && resp.data) {
      var adapted = adaptApiResponse(url, resp.data);
      callback({status: 'ok', data: adapted, original: resp.data});
    } else {
      callback(resp);
    }
  });
}

// ═══════════════════════════════════════════════════════════════════
