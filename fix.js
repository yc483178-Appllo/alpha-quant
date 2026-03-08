
// Fix: DOMContentLoaded event listener
document.addEventListener('DOMContentLoaded', function() {
  console.log('Alpha V3.0 初始化...');
  if(document.getElementById('pos-tbody')) renderPositions();
  if(document.getElementById('sig-tbody')) renderSignals();
  if(document.getElementById('ag-grid')) renderAgents();
  if(document.getElementById('heat-grid')) renderHeatGrid();
  if(document.getElementById('sent-grid')) renderSentiment();
  if(document.getElementById('sys-snap')) renderSysSnap();
  if(document.getElementById('sig-ticker')) renderSigTicker();
  if(document.getElementById('strat-tbody')) renderStratLib();
  if(document.getElementById('hof-list')) renderEvolution();
  if(document.getElementById('broker-cards')) renderBrokers();
  if(document.getElementById('hist-tbody')) renderHistoryTable(TRADES);
  if(document.getElementById('exec-tbody')) renderExecLog();
  if(document.getElementById('live-perf')) renderLivePerf();
  if(document.getElementById('report-list')) renderReportList();
  if(!S.chartsInit['overview']) {
    S.chartsInit['overview'] = true;
    initPanelCharts('overview');
  }
  console.log('Alpha V3.0 初始化完成');
});
