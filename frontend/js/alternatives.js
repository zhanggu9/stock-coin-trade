let markets = [], selected = null, category = '전체';
const won = value => Number(value || 0).toLocaleString('ko-KR') + '원';

(async () => { await initPage({ requireAuth: true }); await refresh(); })();

async function refresh() {
  const [marketRes, meRes, positionRes] = await Promise.all([apiFetch('/api/alternatives/markets'), apiFetch('/api/member/me'), apiFetch('/api/alternatives/positions')]);
  if (!marketRes.ok) return;
  markets = (await marketRes.json()).markets || [];
  const me = await meRes.json(); document.getElementById('cash').textContent = won(me.asset);
  renderTabs(); renderMarkets(); renderPositions((await positionRes.json()).positions || []);
  if (!selected && markets.length) selectMarket(markets[0].symbol);
}
function renderTabs() {
  const categories = ['전체', ...new Set(markets.map(item => item.category))];
  document.getElementById('tabs').innerHTML = categories.map(item => `<button class="market-tab ${item === category ? 'active' : ''}" data-category="${item}">${item}</button>`).join('');
  document.querySelectorAll('[data-category]').forEach(btn => btn.onclick = () => { category = btn.dataset.category; renderTabs(); renderMarkets(); });
}
function renderMarkets() {
  const rows = markets.filter(item => category === '전체' || item.category === category);
  document.getElementById('marketBody').innerHTML = rows.map(item => `<tr class="market-row ${selected?.symbol === item.symbol ? 'selected' : ''}" data-symbol="${item.symbol}"><td><div class="font-bold" style="color:var(--fg);">${item.name}</div><div class="mt-1 text-xs" style="color:var(--muted);">${item.description}</div></td><td class="text-right font-bold" style="color:var(--fg);">${won(item.price)}</td><td class="text-right font-bold" style="color:${item.changeRate >= 0 ? '#E11D48' : '#2563EB'};">${item.changeRate >= 0 ? '+' : ''}${item.changeRate}%</td><td class="text-right font-bold" style="color:var(--accent);">${won(item.tradeAmountPerUnit)}</td><td class="text-right text-xs" style="color:var(--muted);">${item.unit}<br>${item.marginRate === 100 ? '현금 100%' : '증거금 ' + item.marginRate + '%'}</td></tr>`).join('');
  document.querySelectorAll('[data-symbol]').forEach(row => row.onclick = () => selectMarket(row.dataset.symbol));
}
function selectMarket(symbol) { selected = markets.find(item => item.symbol === symbol); document.getElementById('selectedName').textContent = selected.name; document.getElementById('selectedCategory').textContent = selected.category; document.getElementById('selectedInfo').textContent = `${selected.description} · 기준가 ${won(selected.price)} / ${selected.unit}`; renderMarkets(); updateAmount(); }
function updateAmount() { const qty = Math.max(1, Number(document.getElementById('quantity').value || 1)); document.getElementById('orderAmount').textContent = selected ? won(selected.tradeAmountPerUnit * qty) : '-'; document.getElementById('orderNote').textContent = selected ? (selected.marginRate === 100 ? '현금 전액 기준' : `명목금액 ${won(selected.notionalPerUnit * qty)} · 증거금 ${selected.marginRate}% 적용`) : ''; }
document.getElementById('quantity').addEventListener('input', updateAmount);
document.getElementById('buyBtn').onclick = () => submitOrder('BUY'); document.getElementById('sellBtn').onclick = () => submitOrder('SELL');
async function submitOrder(side) { if (!selected) return; const quantity = Math.max(1, Number(document.getElementById('quantity').value || 1)); const res = await apiFetch('/api/alternatives/orders', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({symbol:selected.symbol, side, quantity})}); const data = await res.json(); const el = document.getElementById('orderMessage'); el.style.color = res.ok ? '#059669' : '#E11D48'; el.textContent = res.ok ? `${side === 'BUY' ? '매수' : '매도'} 체결: ${selected.name} ${quantity}${selected.unit}` : (data.message || '주문에 실패했습니다.'); if (res.ok) await refresh(); }
function renderPositions(positions) { const tbody = document.getElementById('positionBody'); tbody.innerHTML = positions.length ? positions.map(pos => `<tr><td><div class="font-bold" style="color:var(--fg);">${pos.name}</div><div class="text-xs" style="color:var(--muted);">${pos.category}</div></td><td class="text-right">${Number(pos.quantity).toLocaleString()}${pos.unit}</td><td class="text-right font-bold" style="color:var(--accent);">${won(pos.evalAmount)}</td><td class="text-right font-bold" style="color:${pos.pnl >= 0 ? '#E11D48' : '#2563EB'};">${pos.pnl >= 0 ? '+' : ''}${won(pos.pnl)}</td></tr>`).join('') : '<tr><td colspan="4" class="px-4 py-6 text-center text-sm" style="color:var(--muted);">보유한 대체자산이 없습니다.</td></tr>'; }
