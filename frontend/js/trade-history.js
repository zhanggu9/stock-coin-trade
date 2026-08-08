let tradeHistoryGridApi = null;

function krw(value) { return `${Number(value || 0).toLocaleString('ko-KR')}원`; }
function formatDate(timestamp) {
  return new Date(timestamp).toLocaleString('ko-KR', { year:'numeric', month:'2-digit', day:'2-digit', hour:'2-digit', minute:'2-digit', second:'2-digit', hour12:false });
}

function updateHistorySummary(rows) {
  const buys = rows.filter(row => row.type === 'BUY');
  const sells = rows.filter(row => row.type === 'SELL');
  document.getElementById('historyTotalCount').textContent = rows.length.toLocaleString('ko-KR');
  document.getElementById('historyBuyAmount').textContent = krw(buys.reduce((sum, row) => sum + Number(row.amount || 0), 0));
  document.getElementById('historySellAmount').textContent = krw(sells.reduce((sum, row) => sum + Number(row.amount || 0), 0));
}

function createHistoryGrid() {
  const element = document.getElementById('historyGrid');
  if (!element || !window.agGrid) return null;
  const columnDefs = [
    { headerName:'체결시간', field:'ts', minWidth:175, sort:'desc', valueFormatter: params => formatDate(params.value) },
    { headerName:'구분', field:'type', width:100, cellRenderer: params => `<span style="font-weight:800;color:${params.value === 'BUY' ? '#E11D48' : '#2563EB'};">${params.value === 'BUY' ? '매수' : '매도'}</span>` },
    { headerName:'종목', field:'name', minWidth:180, flex:1, cellRenderer: params => `<a href="/trade/stock.html?symbol=${encodeURIComponent(params.data.symbol)}" style="font-weight:800;color:var(--fg);text-decoration:none;">${params.value} <span style="font-size:11px;color:var(--accent);">매매 ↗</span></a>` },
    { headerName:'종목코드', field:'symbol', width:110, cellStyle:{ color:'var(--accent)', fontWeight:'700' } },
    { headerName:'수량', field:'quantity', width:110, type:'rightAligned', valueFormatter: params => `${Number(params.value).toLocaleString('ko-KR')}주` },
    { headerName:'체결가', field:'price', minWidth:125, type:'rightAligned', valueFormatter: params => krw(params.value) },
    { headerName:'거래금액', field:'amount', minWidth:145, type:'rightAligned', valueFormatter: params => krw(params.value), cellStyle:{ fontWeight:'800', color:'var(--accent-dark)' } },
    { headerName:'주문경로', field:'source', minWidth:115, valueFormatter: params => ({ WEB:'웹', PINE:'Pine 전략', OPENAPI:'Open API', DEMO_SEED:'샘플' }[params.value] || params.value || '웹') },
  ];
  return agGrid.createGrid(element, {
    columnDefs,
    rowData: [],
    defaultColDef: { sortable:true, filter:true, resizable:true, suppressHeaderMenuButton:true },
    animateRows:true,
    pagination:true,
    paginationPageSize:20,
    paginationPageSizeSelector:[20, 50, 100],
    overlayNoRowsTemplate:'<span style="padding:16px;color:#64748B;">표시할 거래이력이 없습니다.</span>',
  });
}

async function loadTradeHistory() {
  const status = document.getElementById('historyStatus');
  if (status) status.textContent = '거래이력을 불러오는 중입니다…';
  try {
    const response = await apiFetch('/api/stocks/orders/history?limit=1000');
    if (!response.ok) throw new Error('거래이력을 불러오지 못했습니다.');
    const data = await response.json();
    const rows = data.history ?? [];
    tradeHistoryGridApi?.setGridOption('rowData', rows);
    updateHistorySummary(rows);
    if (status) status.textContent = `${rows.length.toLocaleString('ko-KR')}건 · 최근 체결순`;
  } catch (error) {
    if (status) status.textContent = error.message;
  }
}

(async () => {
  await initPage({ requireAuth:true });
  tradeHistoryGridApi = createHistoryGrid();
  if (!tradeHistoryGridApi) {
    document.getElementById('historyStatus').textContent = 'AG Grid를 불러오지 못했습니다.';
    return;
  }
  document.getElementById('historyQuickFilter')?.addEventListener('input', event => tradeHistoryGridApi.setGridOption('quickFilterText', event.target.value));
  document.getElementById('historyRefreshBtn')?.addEventListener('click', loadTradeHistory);
  document.getElementById('historyCsvBtn')?.addEventListener('click', () => tradeHistoryGridApi.exportDataAsCsv({ fileName:'my-stock-trade-history.csv' }));
  await loadTradeHistory();
})();
