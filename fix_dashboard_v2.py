#!/usr/bin/env python3
"""
修复看板V5.0的实时数据显示问题 - 修正版
更新实际存在的图表ID
"""

def fix_dashboard_v2():
    with open('/opt/alpha/v3/index.html', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 1. 替换错误的图表更新代码 - 使用实际存在的图表ID
    old_update = """// 更新行情分布图表
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
          } catch(e) { console.warn('Pie chart update error', e); }"""
    
    new_update = """// 更新行业分布饼图 (使用实时数据的股票涨跌)
          try {
            var upCount = stocks.filter(function(s){ return s.chg > 0; }).length;
            var downCount = stocks.filter(function(s){ return s.chg < 0; }).length;
            var flatCount = stocks.length - upCount - downCount;
            var sectorChart = window._charts['c-sector-donut'];
            if(sectorChart) {
              // 更新为涨跌分布数据
              sectorChart.data.labels = ['上涨','下跌','平盘'];
              sectorChart.data.datasets[0].data = [upCount, downCount, flatCount];
              sectorChart.data.datasets[0].backgroundColor = ['rgba(0,230,118,.8)','rgba(255,61,87,.8)','rgba(255,179,0,.8)'];
              sectorChart.update('none');
              console.log('[INIT] 涨跌分布图表已更新');
            }
          } catch(e) { console.warn('Sector chart update error', e); }"""
    
    content = content.replace(old_update, new_update)
    
    # 2. 替换定时tick中的图表更新
    old_tick_update = """// 更新价格分布图
            try {
              var priceDistChart = window._charts['c-price-dist'];
              if(priceDistChart) {
                var prices = stocks.map(function(s){ return s.p; }).slice(0, 10);
                var names = stocks.map(function(s){ return s.n; }).slice(0, 10);
                priceDistChart.data.datasets[0].data = prices;
                priceDistChart.data.labels = names;
                priceDistChart.update('none');
              }
            } catch(e) {}"""
    
    new_tick_update = """// 更新行业分布饼图为涨跌分布
            try {
              var upCount = stocks.filter(function(s){ return s.chg > 0; }).length;
              var downCount = stocks.filter(function(s){ return s.chg < 0; }).length;
              var flatCount = stocks.length - upCount - downCount;
              var sectorChart = window._charts['c-sector-donut'];
              if(sectorChart) {
                sectorChart.data.labels = ['上涨','下跌','平盘'];
                sectorChart.data.datasets[0].data = [upCount, downCount, flatCount];
                sectorChart.data.datasets[0].backgroundColor = ['rgba(0,230,118,.8)','rgba(255,61,87,.8)','rgba(255,179,0,.8)'];
                sectorChart.update('none');
              }
            } catch(e) {}"""
    
    content = content.replace(old_tick_update, new_tick_update)
    
    # 3. 替换指数图表更新代码 - 使用实际存在的c-sh图表
    old_idx_update = """// 更新指数趋势图
          try {
            var idxChart = window._charts['c-index-trend'];
            if(idxChart && d['000001'] && d['000001'].price) {
              var shData = idxChart.data.datasets[0].data;
              shData.push(d['000001'].price);
              if(shData.length > 30) shData.shift();
              idxChart.update('none');
              console.log('[INIT] 指数趋势图表已更新');
            }
          } catch(e) { console.warn('Index chart update error', e); }"""
    
    new_idx_update = """// 更新上证指数图表
          try {
            var shChart = window._charts['c-sh'];
            if(shChart && d['000001'] && d['000001'].price) {
              var shData = shChart.data.datasets[0].data;
              shData.push(d['000001'].price);
              if(shData.length > 20) shData.shift();
              shChart.update('none');
              console.log('[INIT] 上证指数图表已更新');
            }
          } catch(e) { console.warn('SH chart update error', e); }
          // 更新深证指数图表
          try {
            var szChart = window._charts['c-sz'];
            if(szChart && d['399001'] && d['399001'].price) {
              var szData = szChart.data.datasets[0].data;
              szData.push(d['399001'].price);
              if(szData.length > 20) szData.shift();
              szChart.update('none');
            }
          } catch(e) {}
          // 更新创业板指数图表
          try {
            var cyChart = window._charts['c-cy'];
            if(cyChart && d['399006'] && d['399006'].price) {
              var cyData = cyChart.data.datasets[0].data;
              cyData.push(d['399006'].price);
              if(cyData.length > 20) cyData.shift();
              cyChart.update('none');
            }
          } catch(e) {}"""
    
    content = content.replace(old_idx_update, new_idx_update)
    
    # 4. 替换tick中的指数更新
    old_tick_idx = """// 更新指数趋势图
          try {
            var idxChart = window._charts['c-index-trend'];
            if(idxChart) {
              var data = idxChart.data.datasets[0].data;
              data.push(sh.price);
              if(data.length > 30) data.shift();
              idxChart.update('none');
            }
          } catch(e) {}"""
    
    new_tick_idx = """// 更新上证指数图表
          try {
            var shChart = window._charts['c-sh'];
            if(shChart) {
              var shData = shChart.data.datasets[0].data;
              shData.push(sh.price);
              if(shData.length > 20) shData.shift();
              shChart.update('none');
            }
          } catch(e) {}"""
    
    content = content.replace(old_tick_idx, new_tick_idx)
    
    # 5. 删除雷达图更新代码（可能不存在）
    content = content.replace(
        """// 更新指数对比雷达图
          try {
            var radarChart = window._charts['c-index-radar'];
            if(radarChart && shVal && szVal && cyVal) {
              radarChart.data.datasets[0].data = [shVal/100, szVal/100, cyVal/50, (shVal+szVal)/200, cyVal/40];
              radarChart.update('none');
            }
          } catch(e) {}""",
        ""
    )
    
    with open('/opt/alpha/v3/index.html', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ 看板修复完成 (v2)!")
    print("- 使用实际存在的图表ID: c-sh, c-sz, c-cy, c-sector-donut")
    print("- 上证指数图表现在会显示实时数据")
    print("- 行业分布图现在显示涨跌分布")

if __name__ == '__main__':
    fix_dashboard_v2()
