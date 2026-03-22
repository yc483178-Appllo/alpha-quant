#!/usr/bin/env python3
"""
修复看板V5.0的实时数据显示问题
- 修复API数据获取后图表不更新
- 添加真实数据到动态线图
- 修复指数数据显示
"""

import re

def fix_dashboard():
    with open('/opt/alpha/v3/index.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 修复apiGet回调 - 在获取实时行情后更新图表
    old_realtime_callback = """apiGet('/market/realtime', function(resp) {
      if(resp && resp.data) {
        console.log('[INIT] 实时行情:', Object.keys(resp.data).length, '只股票');
        // 更新tickerStocks
        var stocks = [];
        for(var code in resp.data) {
          var d = resp.data[code];
          stocks.push({
            c: code,
            n: d.name || code,
            p: d.price || 0,
            chg: d.change_pct || 0,
            sig: d.change_pct > 0 ? '买入' : d.change_pct < -2 ? '卖出' : '持有',
            src: d.source || 'API',
            conf: Math.floor(Math.random() * 20) + 80
          });
        }
        if(stocks.length > 0) {
          S.tickerStocks = stocks;
          console.log('[INIT] tickerStocks已更新:', stocks.length);
          // 重新渲染ticker显示真实数据
          try { renderTickerV43(); } catch(e) { console.warn("Ticker render error", e); }
        }
      }
    });"""
    
    new_realtime_callback = """apiGet('/market/realtime', function(resp) {
      if(resp && resp.data) {
        console.log('[INIT] 实时行情:', Object.keys(resp.data).length, '只股票');
        // 更新tickerStocks
        var stocks = [];
        var prices = [];
        var names = [];
        for(var code in resp.data) {
          var d = resp.data[code];
          stocks.push({
            c: code,
            n: d.name || code,
            p: d.price || 0,
            chg: d.change_pct || 0,
            sig: d.change_pct > 0 ? '买入' : d.change_pct < -2 ? '卖出' : '持有',
            src: d.source || 'API',
            conf: Math.floor(Math.random() * 20) + 80
          });
          prices.push(d.price || 0);
          names.push(d.name || code);
        }
        if(stocks.length > 0) {
          S.tickerStocks = stocks;
          console.log('[INIT] tickerStocks已更新:', stocks.length);
          // 重新渲染ticker显示真实数据
          try { renderTickerV43(); } catch(e) { console.warn("Ticker render error", e); }
          // 更新行情分布图表
          try {
            var priceDistChart = window._charts['c-price-dist'];
            if(priceDistChart) {
              priceDistChart.data.labels = names.slice(0, 10);
              priceDistChart.data.datasets[0].data = prices.slice(0, 10);
              priceDistChart.update('none');
              console.log('[INIT] 行情分布图表已更新');
            }
          } catch(e) { console.warn('Price dist chart update error', e); }
          // 更新涨跌分布饼图
          try {
            var upCount = stocks.filter(function(s){ return s.chg > 0; }).length;
            var downCount = stocks.filter(function(s){ return s.chg < 0; }).length;
            var flatCount = stocks.length - upCount - downCount;
            var pieChart = window._charts['c-signal-pie'];
            if(pieChart) {
              pieChart.data.datasets[0].data = [upCount, downCount, flatCount];
              pieChart.update('none');
              console.log('[INIT] 涨跌分布饼图已更新');
            }
          } catch(e) { console.warn('Pie chart update error', e); }
        }
      }
    });"""
    
    content = content.replace(old_realtime_callback, new_realtime_callback)
    
    # 2. 修复指数数据回调 - 更新指数图表
    old_index_callback = """apiGet('/market/index', function(resp) {
      if(resp && resp.data) {
        console.log('[INIT] 指数数据:', resp.data);
        var d = resp.data;
        // 更新S.priceData数组的最后一个值（最新价格）
        if(d['000001'] && d['000001'].price) {
          var shPrice = d['000001'].price;
          S.priceData.sh[S.priceData.sh.length-1] = shPrice;
          // 更新显示元素
          var shEl = document.getElementById('idx-sh-price');
          if(shEl) shEl.textContent = shPrice.toFixed(2);
          var shChgEl = document.getElementById('idx-sh-chg');
          if(shChgEl) shChgEl.textContent = (d['000001'].change_pct > 0 ? '+' : '') + d['000001'].change_pct + '%';
        }
        if(d['399001'] && d['399001'].price) {
          var szPrice = d['399001'].price;
          S.priceData.sz[S.priceData.sz.length-1] = szPrice;
          var szEl = document.getElementById('idx-sz-price');
          if(szEl) szEl.textContent = szPrice.toFixed(2);
        }
        if(d['399006'] && d['399006'].price) {
          var cyPrice = d['399006'].price;
          S.priceData.cy[S.priceData.cy.length-1] = cyPrice;
          var cyEl = document.getElementById('idx-cy-price');
          if(cyEl) cyEl.textContent = cyPrice.toFixed(2);
        }
        // 更新显示元素
        setTimeout(function() {
          var shVal = d['000001'] ? d['000001'].price : 0;
          var szVal = d['399001'] ? d['399001'].price : 0;
          var cyVal = d['399006'] ? d['399006'].price : 0;
          // 更新卡片大数字
          var shEl = document.getElementById('sh-val');
          if(shEl) shEl.textContent = shVal ? shVal.toLocaleString('en-US', {minimumFractionDigits: 1, maximumFractionDigits: 1}) : '--';
          var szEl = document.getElementById('sz-val');
          if(szEl) szEl.textContent = szVal ? szVal.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}) : '--';
          var cyEl = document.getElementById('cy-val');
          if(cyEl) cyEl.textContent = cyVal ? cyVal.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}) : '--';
          // 更新表格数据
          var shPriceEl = document.getElementById('idx-sh-price');
          if(shPriceEl) shPriceEl.textContent = shVal ? shVal.toFixed(2) : '--';
          var szPriceEl = document.getElementById('idx-sz-price');
          if(szPriceEl) szPriceEl.textContent = szVal ? szVal.toFixed(2) : '--';
          var cyPriceEl = document.getElementById('idx-cy-price');
          if(cyPriceEl) cyPriceEl.textContent = cyVal ? cyVal.toFixed(2) : '--';
          // 更新topbar
          var tbSh = document.getElementById('tb-sh');
          if(tbSh) tbSh.textContent = shVal ? Math.round(shVal) : '--';
          // 触发图表更新
          try { updateCharts(); } catch(e) {}
          try { updateChartsV41(); } catch(e) {}
        }, 500);
      }
    });"""
    
    new_index_callback = """apiGet('/market/index', function(resp) {
      if(resp && resp.data) {
        console.log('[INIT] 指数数据:', resp.data);
        var d = resp.data;
        // 更新指数图表数据
        try {
          var idxChart = window._charts['c-index-trend'];
          if(idxChart && d['000001'] && d['000001'].price) {
            var shData = idxChart.data.datasets[0].data;
            shData.push(d['000001'].price);
            if(shData.length > 30) shData.shift();
            idxChart.update('none');
            console.log('[INIT] 指数趋势图表已更新');
          }
        } catch(e) { console.warn('Index chart update error', e); }
        // 更新S.priceData数组的最后一个值（最新价格）
        if(d['000001'] && d['000001'].price) {
          var shPrice = d['000001'].price;
          S.priceData.sh[S.priceData.sh.length-1] = shPrice;
          // 更新显示元素
          var shEl = document.getElementById('idx-sh-price');
          if(shEl) shEl.textContent = shPrice.toFixed(2);
          var shChgEl = document.getElementById('idx-sh-chg');
          if(shChgEl) shChgEl.textContent = (d['000001'].change_pct > 0 ? '+' : '') + d['000001'].change_pct + '%';
        }
        if(d['399001'] && d['399001'].price) {
          var szPrice = d['399001'].price;
          S.priceData.sz[S.priceData.sz.length-1] = szPrice;
          var szEl = document.getElementById('idx-sz-price');
          if(szEl) szEl.textContent = szPrice.toFixed(2);
        }
        if(d['399006'] && d['399006'].price) {
          var cyPrice = d['399006'].price;
          S.priceData.cy[S.priceData.cy.length-1] = cyPrice;
          var cyEl = document.getElementById('idx-cy-price');
          if(cyEl) cyEl.textContent = cyPrice.toFixed(2);
        }
        // 更新显示元素
        setTimeout(function() {
          var shVal = d['000001'] ? d['000001'].price : 0;
          var szVal = d['399001'] ? d['399001'].price : 0;
          var cyVal = d['399006'] ? d['399006'].price : 0;
          // 更新卡片大数字
          var shEl = document.getElementById('sh-val');
          if(shEl) shEl.textContent = shVal ? shVal.toLocaleString('en-US', {minimumFractionDigits: 1, maximumFractionDigits: 1}) : '--';
          var szEl = document.getElementById('sz-val');
          if(szEl) szEl.textContent = szVal ? szVal.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}) : '--';
          var cyEl = document.getElementById('cy-val');
          if(cyEl) cyEl.textContent = cyVal ? cyVal.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0}) : '--';
          // 更新表格数据
          var shPriceEl = document.getElementById('idx-sh-price');
          if(shPriceEl) shPriceEl.textContent = shVal ? shVal.toFixed(2) : '--';
          var szPriceEl = document.getElementById('idx-sz-price');
          if(szPriceEl) szPriceEl.textContent = szVal ? szVal.toFixed(2) : '--';
          var cyPriceEl = document.getElementById('idx-cy-price');
          if(cyPriceEl) cyPriceEl.textContent = cyVal ? cyVal.toFixed(2) : '--';
          // 更新topbar
          var tbSh = document.getElementById('tb-sh');
          if(tbSh) tbSh.textContent = shVal ? Math.round(shVal) : '--';
          // 更新指数对比雷达图
          try {
            var radarChart = window._charts['c-index-radar'];
            if(radarChart && shVal && szVal && cyVal) {
              radarChart.data.datasets[0].data = [shVal/100, szVal/100, cyVal/50, (shVal+szVal)/200, cyVal/40];
              radarChart.update('none');
            }
          } catch(e) {}
        }, 500);
      }
    });"""
    
    content = content.replace(old_index_callback, new_index_callback)
    
    # 3. 添加定时轮询获取实时数据
    old_tick = """function tickV41() {
  try {
    // Update factor IC values periodically
    if(Math.random() > 0.7) {
      S.factorLib.forEach(function(f) {
        f.ic = parseFloat(Math.max(0.01, f.ic + (Math.random()-0.5)*0.005).toFixed(3));
        f.ir = parseFloat(Math.max(0.3, f.ir + (Math.random()-0.5)*0.02).toFixed(2));
      });
    }"""
    
    new_tick = """function tickV41() {
  try {
    // 每10秒轮询获取实时数据
    if(typeof window._tickCounter === 'undefined') window._tickCounter = 0;
    window._tickCounter++;
    
    // 每10个tick(约10秒)获取一次实时行情
    if(window._tickCounter % 10 === 0) {
      apiGet('/market/realtime', function(resp) {
        if(resp && resp.data) {
          // 更新ticker
          var stocks = [];
          for(var code in resp.data) {
            var d = resp.data[code];
            stocks.push({
              c: code,
              n: d.name || code,
              p: d.price || 0,
              chg: d.change_pct || 0,
              sig: d.change_pct > 0 ? '买入' : d.change_pct < -2 ? '卖出' : '持有',
              src: d.source || 'API',
              conf: Math.floor(Math.random() * 20) + 80
            });
          }
          if(stocks.length > 0) {
            S.tickerStocks = stocks;
            try { renderTickerV43(); } catch(e) {}
            // 更新价格分布图
            try {
              var priceDistChart = window._charts['c-price-dist'];
              if(priceDistChart) {
                var prices = stocks.map(function(s){ return s.p; }).slice(0, 10);
                var names = stocks.map(function(s){ return s.n; }).slice(0, 10);
                priceDistChart.data.datasets[0].data = prices;
                priceDistChart.data.labels = names;
                priceDistChart.update('none');
              }
            } catch(e) {}
          }
        }
      });
      
      // 获取指数数据
      apiGet('/market/index', function(resp) {
        if(resp && resp.data && resp.data['000001']) {
          var sh = resp.data['000001'];
          // 更新指数趋势图
          try {
            var idxChart = window._charts['c-index-trend'];
            if(idxChart) {
              var data = idxChart.data.datasets[0].data;
              data.push(sh.price);
              if(data.length > 30) data.shift();
              idxChart.update('none');
            }
          } catch(e) {}
          // 更新topbar
          var tbSh = document.getElementById('tb-sh');
          if(tbSh) tbSh.textContent = Math.round(sh.price);
          var shEl = document.getElementById('sh-val');
          if(shEl) shEl.textContent = sh.price.toLocaleString('en-US', {minimumFractionDigits: 1});
        }
      });
    }
    
    // Update factor IC values periodically
    if(Math.random() > 0.7) {
      S.factorLib.forEach(function(f) {
        f.ic = parseFloat(Math.max(0.01, f.ic + (Math.random()-0.5)*0.005).toFixed(3));
        f.ir = parseFloat(Math.max(0.3, f.ir + (Math.random()-0.5)*0.02).toFixed(2));
      });
    }"""
    
    content = content.replace(old_tick, new_tick)
    
    # 4. 修改底部script标签错误
    content = content.replace(
        "</html>\\<script src=\"http://120.76.55.222/api/static/chart_bridge.js\"\\>\\</script\\>\\<script src=\"http://120.76.55.222/api/static/data_sync_v9.js\"\\>\\</script\\>",
        "</html>"
    )
    
    with open('/opt/alpha/v3/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 看板修复完成!")
    print("- API数据现在会正确更新图表")
    print("- 添加了10秒轮询获取实时数据")
    print("- 修复了底部script标签错误")

if __name__ == '__main__':
    fix_dashboard()
