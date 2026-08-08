let markets = [], selected = null, category = '전체', chart, candleSeries, propertyMap, propertyMarkers = [];
const won = value => Number(value || 0).toLocaleString('ko-KR') + '원';

(async () => { await initPage({ requireAuth: true }); initChart(); await refresh(); })();

function initChart() {
  const el = document.getElementById('alternativeChart');
  if (!el || !window.LightweightCharts) return;
  chart = LightweightCharts.createChart(el, { height: 400, layout: { background: { color: '#fff' }, textColor: '#64748B' }, grid: { vertLines: { color: '#F1F5F9' }, horzLines: { color: '#F1F5F9' } }, rightPriceScale: { borderColor: '#E2E8F0' }, timeScale: { borderColor: '#E2E8F0' } });
  candleSeries = chart.addCandlestickSeries({ upColor: '#E11D48', downColor: '#2563EB', borderUpColor: '#E11D48', borderDownColor: '#2563EB', wickUpColor: '#E11D48', wickDownColor: '#2563EB' });
  window.addEventListener('resize', () => chart?.applyOptions({ width: el.clientWidth }));
}

async function refresh() {
  const [marketRes, meRes, positionRes] = await Promise.all([apiFetch('/api/alternatives/markets'), apiFetch('/api/member/me'), apiFetch('/api/alternatives/positions')]);
  if (!marketRes.ok) return;
  markets = (await marketRes.json()).markets || [];
  const me = await meRes.json(); document.getElementById('cash').textContent = won(me.asset);
  renderSideMenu(); renderMarkets(); renderPositions((await positionRes.json()).positions || []);
  if (!selected && markets.length) selectMarket(markets[0].symbol);
}
function renderSideMenu() {
  const chartCategories = ['선물', '옵션', '파생상품', '금', '은'];
  const rows = [
    { title: '부동산 지도 거래', icon: '🗺️', key: '부동산', note: '지역을 지도에서 선택하고 시세를 확인한 뒤 바로 주문합니다.' },
    { title: '캔들 차트 거래', icon: '📈', key: 'ALL_CHART', note: '일봉 차트를 보며 선물·옵션·파생상품·금·은을 주문합니다.' },
    ...chartCategories.map(name => ({ title: name, icon: '•', key: name, note: '' })),
  ];
  document.getElementById('sideMenu').innerHTML = rows.map(item => `<div ${item.note ? 'style="margin-bottom:8px;"' : ''}><button class="asset-menu-btn ${category === item.key || (item.key === 'ALL_CHART' && category === '전체') ? 'active' : ''}" data-menu-category="${item.key}"><span class="asset-menu-icon">${item.icon}</span><span>${item.title}</span></button>${item.note ? `<p class="asset-menu-note">${item.note}</p>` : ''}</div>`).join('');
  document.querySelectorAll('[data-menu-category]').forEach(btn => btn.onclick = () => {
    category = btn.dataset.menuCategory === 'ALL_CHART' ? '전체' : btn.dataset.menuCategory;
    renderSideMenu(); renderMarkets();
    if (category === '부동산') selectMarket(markets.find(item => item.category === '부동산')?.symbol);
    else if (selected?.category === '부동산' || (category !== '전체' && selected?.category !== category)) selectMarket(markets.find(item => item.category === category)?.symbol);
  });
}
function renderMarkets() {
  const rows = markets.filter(item => category === '전체' ? item.category !== '부동산' : item.category === category);
  document.getElementById('marketListTitle').textContent = category === '부동산' ? '부동산 지도 거래 상품' : category === '전체' ? '캔들 차트 거래 상품' : `${category} 캔들 차트 거래 상품`;
  document.getElementById('marketListGuide').textContent = category === '부동산' ? '아래 상품 또는 지도 핀을 선택하면 지역 시세와 주문창이 연동됩니다.' : '상품을 선택하면 일봉 캔들 차트와 주문창이 함께 표시됩니다.';
  document.getElementById('marketBody').innerHTML = rows.map(item => `<tr class="market-row ${selected?.symbol === item.symbol ? 'selected' : ''}" data-symbol="${item.symbol}"><td><div class="font-bold" style="color:var(--fg);">${item.name}</div><div class="mt-1 text-xs" style="color:var(--muted);">${item.description}</div></td><td class="text-right font-bold" style="color:var(--fg);">${won(item.price)}</td><td class="text-right font-bold" style="color:${item.changeRate >= 0 ? '#E11D48' : '#2563EB'};">${item.changeRate >= 0 ? '+' : ''}${item.changeRate}%</td><td class="text-right font-bold" style="color:var(--accent);">${won(item.tradeAmountPerUnit)}</td><td class="text-right text-xs" style="color:var(--muted);">${item.unit}<br>${item.marginRate === 100 ? '현금 100%' : '증거금 ' + item.marginRate + '%'}</td></tr>`).join('');
  document.querySelectorAll('[data-symbol]').forEach(row => row.onclick = () => selectMarket(row.dataset.symbol));
}
async function selectMarket(symbol) {
  selected = markets.find(item => item.symbol === symbol); if (!selected) return;
  document.getElementById('selectedName').textContent = selected.name; document.getElementById('selectedCategory').textContent = selected.category;
  document.getElementById('selectedInfo').textContent = `${selected.description} · 기준가 ${won(selected.price)} / ${selected.unit}`;
  document.getElementById('viewTitle').textContent = selected.category === '부동산' ? '부동산 시세 지도' : `${selected.name} 일봉 차트`;
  document.getElementById('viewSubtitle').textContent = selected.category === '부동산' ? `${selected.location?.label || ''} · 지도에서 다른 지역도 선택할 수 있습니다.` : '교육용 기준 시세 일봉 · 주문 기준가는 당일 종가와 연동됩니다.';
  document.getElementById('viewBadge').textContent = selected.category === '부동산' ? '지도 시세' : '일봉';
  document.getElementById('chartView').classList.toggle('active', selected.category !== '부동산'); document.getElementById('mapView').classList.toggle('active', selected.category === '부동산');
  renderMarkets(); updateAmount();
  if (selected.category === '부동산') renderPropertyMap(); else await loadChart();
}
async function loadChart() {
  const res = await apiFetch(`/api/alternatives/markets/${encodeURIComponent(selected.symbol)}/chart?days=120`); if (!res.ok || !candleSeries) return;
  const data = (await res.json()).data || []; candleSeries.setData(data); chart.timeScale().fitContent();
}
function renderPropertyMap() {
  if (!window.L) return;
  const properties = markets.filter(item => item.category === '부동산' && item.location);
  if (!propertyMap) {
    propertyMap = L.map('propertyMap', { scrollWheelZoom: false }).setView([36.6, 127.8], 7);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 18, attribution: '&copy; OpenStreetMap contributors' }).addTo(propertyMap);
  }
  propertyMarkers.forEach(marker => marker.remove()); propertyMarkers = properties.map(item => {
    const marker = L.circleMarker([item.location.lat, item.location.lng], { radius: item.symbol === selected.symbol ? 11 : 8, color: item.symbol === selected.symbol ? '#2563EB' : '#64748B', fillColor: item.symbol === selected.symbol ? '#60A5FA' : '#CBD5E1', fillOpacity: 1, weight: 2 }).addTo(propertyMap);
    marker.bindPopup(`<strong>${item.name}</strong><br>${item.location.label}<br>${won(item.price)} / ${item.unit}`); marker.on('click', () => selectMarket(item.symbol)); return marker;
  });
  propertyMap.setView([selected.location.lat, selected.location.lng], 12); setTimeout(() => propertyMap.invalidateSize(), 80);
}
function updateAmount() { const qty = Math.max(1, Number(document.getElementById('quantity').value || 1)); document.getElementById('orderAmount').textContent = selected ? won(selected.tradeAmountPerUnit * qty) : '-'; document.getElementById('orderNote').textContent = selected ? (selected.marginRate === 100 ? '현금 전액 기준' : `명목금액 ${won(selected.notionalPerUnit * qty)} · 증거금 ${selected.marginRate}% 적용`) : ''; }
document.getElementById('quantity').addEventListener('input', updateAmount);
document.getElementById('buyBtn').onclick = () => submitOrder('BUY'); document.getElementById('sellBtn').onclick = () => submitOrder('SELL');
async function submitOrder(side) { if (!selected) return; const quantity = Math.max(1, Number(document.getElementById('quantity').value || 1)); const res = await apiFetch('/api/alternatives/orders', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({symbol:selected.symbol, side, quantity}) }); const data = await res.json(); const el = document.getElementById('orderMessage'); el.style.color = res.ok ? '#059669' : '#E11D48'; el.textContent = res.ok ? `${side === 'BUY' ? '매수' : '매도'} 체결: ${selected.name} ${quantity}${selected.unit}` : (data.message || '주문에 실패했습니다.'); if (res.ok) await refresh(); }
function renderPositions(positions) { const tbody = document.getElementById('positionBody'); tbody.innerHTML = positions.length ? positions.map(pos => `<tr><td><div class="font-bold" style="color:var(--fg);">${pos.name}</div><div class="text-xs" style="color:var(--muted);">${pos.category}</div></td><td class="text-right">${Number(pos.quantity).toLocaleString()}${pos.unit}</td><td class="text-right font-bold" style="color:var(--accent);">${won(pos.evalAmount)}</td><td class="text-right font-bold" style="color:${pos.pnl >= 0 ? '#E11D48' : '#2563EB'};">${pos.pnl >= 0 ? '+' : ''}${won(pos.pnl)}</td></tr>`).join('') : '<tr><td colspan="4" class="px-4 py-6 text-center text-sm" style="color:var(--muted);">보유한 대체자산이 없습니다.</td></tr>'; }
