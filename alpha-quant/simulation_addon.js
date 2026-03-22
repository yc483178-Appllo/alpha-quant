// V3.1 Simulation Add-on - Load this after main dashboard loads
(function() {
  // Add simulation tab if not exists
  const tabsContainer = document.querySelector('.tabs');
  if (tabsContainer && !document.querySelector('[data-tab="simulation"]')) {
    const simTab = document.createElement('button');
    simTab.className = 'tab-btn';
    simTab.setAttribute('data-tab', 'simulation');
    simTab.style.color = 'var(--purple)';
    simTab.innerHTML = '<i class="fa-solid fa-flask" style="color:var(--purple)"></i>模拟盘<span class="tab-badge" style="background:var(--purple);color:#fff">SIM</span>';
    simTab.onclick = function() { switchTab('simulation', this); };
    tabsContainer.appendChild(simTab);
  }

  // Add simulation panel if not exists
  const mainContainer = document.querySelector('.main');
  if (mainContainer && !document.getElementById('panel-simulation')) {
    const simPanel = document.createElement('div');
    simPanel.className = 'panel';
    simPanel.id = 'panel-simulation';
    simPanel.innerHTML = `
      <div class="g4" style="margin-bottom:12px">
        <div class="card"><div class="card-hdr"><div class="card-title"><i class="fa-solid fa-wallet"></i>总资产</div></div><div class="kpi"><div class="kpi-val cyan" id="sim-total">1,000,000</div><div class="kpi-lbl">初始资金</div></div></div>
        <div class="card"><div class="card-hdr"><div class="card-title"><i class="fa-solid fa-coins"></i>现金</div></div><div class="kpi"><div class="kpi-val" id="sim-cash">1,000,000</div><div class="kpi-lbl">可用</div></div></div>
        <div class="card"><div class="card-hdr"><div class="card-title"><i class="fa-solid fa-chart-line"></i>净值</div></div><div class="kpi"><div class="kpi-val" id="sim-nav">1.0000</div><div class="kpi-lbl">基准1.0</div></div></div>
        <div class="card"><div class="card-hdr"><div class="card-title"><i class="fa-solid fa-percent"></i>盈亏</div></div><div class="kpi"><div class="kpi-val" id="sim-pnl">0.00%</div><div class="kpi-lbl">累计</div></div></div>
      </div>
      <div class="card">
        <div class="card-hdr"><div class="card-title"><i class="fa-solid fa-list"></i>模拟持仓</div><span class="card-badge cb-purple">T+1</span></div>
        <div id="sim-holdings">暂无持仓数据</div>
        <div style="margin-top:12px">
          <button class="btn btn-success" onclick="alert('模拟买入')">买入</button>
          <button class="btn btn-danger" onclick="alert('模拟卖出')">卖出</button>
        </div>
      </div>
    `;
    mainContainer.appendChild(simPanel);
  }

  // Load simulation data from API
  window.loadSimData = async function() {
    try {
      const res = await fetch('/api/v6/sim/accounts');
      const data = await res.json();
      if(data.success && data.data.length > 0) {
        const acc = data.data[0];
        const totalEl = document.getElementById('sim-total');
        const cashEl = document.getElementById('sim-cash');
        const navEl = document.getElementById('sim-nav');
        const pnlEl = document.getElementById('sim-pnl');
        if(totalEl) totalEl.textContent = acc.total_assets.toLocaleString();
        if(cashEl) cashEl.textContent = acc.cash.toLocaleString();
        if(navEl) navEl.textContent = acc.nav.toFixed(4);
        if(pnlEl) {
          pnlEl.textContent = (acc.pnl_pct >= 0 ? '+' : '') + acc.pnl_pct.toFixed(2) + '%';
          pnlEl.className = 'kpi-val ' + (acc.pnl_pct >= 0 ? 'up' : 'down');
        }
      }
    } catch(e) {
      console.error('Load sim data failed:', e);
    }
  };

  // Auto-load when simulation tab is clicked
  const origSwitchTab = window.switchTab;
  window.switchTab = function(name, el) {
    if (origSwitchTab) origSwitchTab(name, el);
    if (name === 'simulation') {
      loadSimData();
    }
  };

  console.log('V3.1 Simulation module loaded');
})();