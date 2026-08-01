/* ── 초기화: 보유자산 fetch → DOM 렌더 → WebSocket 연결 ──────── */
(async () => {
  await initPage({ requireAuth: true });

  const res = await apiFetch('/api/trade/hold');
  if (!res.ok) {
    document.getElementById('holdCryptoTableBody').innerHTML =
      '<tr><td colspan="6" class="px-4 py-6 text-center" style="color:var(--muted);">데이터를 불러올 수 없습니다.</td></tr>';
    return;
  }

  const { memberAsset, totalBuyKrw, holdCryptoList, marketArrayList } = await res.json();

  // 상단 통계 초기값 설정
  setText('member_asset', fmt(memberAsset));
  setText('total_buy_krw', fmt(totalBuyKrw));

  // 보유 코인 테이블 렌더
  renderHoldTable(holdCryptoList);
  await loadStockPortfolio();

  if (!holdCryptoList.length) {
    setText('total_member_asset', fmt(memberAsset));
    setText('total_evaluation_krw', '0');
    setText('total_krw_of_return', '0');
    setText('total_evaluation_rate_of_return', '0');
    // 보유 코인이 없어도 KRW 자산 비중 차트는 표시한다.
    await renderPortfolioChart([], [], memberAsset);
    return;
  }

  // 웹소켓 연결 (평가금액 실시간 업데이트)
  initWebSocket(marketArrayList, memberAsset, totalBuyKrw);

  // 포트폴리오 차트
  renderPortfolioChart(holdCryptoList, marketArrayList, memberAsset);
})();

/* ── 주식 포트폴리오 / 섹터별 집계 ────────────────────────────── */
async function loadStockPortfolio() {
  const tbody = document.getElementById('holdStockTableBody');
  try {
    const res = await apiFetch('/api/stocks/positions');
    if (!res.ok) throw new Error('stock positions unavailable');
    const { positions = [] } = await res.json();

    const totalEval = positions.reduce((sum, pos) => sum + Number(pos.evalAmount || 0), 0);
    const totalPnl = positions.reduce((sum, pos) => sum + Number(pos.pnl || 0), 0);
    setText('stockPositionCount', positions.length);
    setText('stockPortfolioEval', fmt(totalEval));
    setColorText('stockPortfolioPnl', totalPnl >= 0 ? '+' + fmt(totalPnl) : fmt(totalPnl), totalPnl);

    renderStockSectorSummary(positions, totalEval);
    if (!positions.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-6 text-center" style="color:var(--muted);">보유 주식이 없습니다.</td></tr>';
      return;
    }

    tbody.innerHTML = positions.map(pos => {
      const pnl = Number(pos.pnl || 0);
      const color = pnl >= 0 ? '#E11D48' : '#2563EB';
      return `<tr>
        <td><div class="font-bold" style="color:var(--fg);">${pos.name}</div><div class="text-xs" style="color:var(--accent);">${pos.symbol}</div></td>
        <td><span class="badge badge-muted" style="font-size:10px;">${pos.sector || '기타'}</span></td>
        <td class="text-right font-semibold" style="color:var(--fg);">${Number(pos.quantity).toLocaleString('ko-KR')}주</td>
        <td class="text-right" style="color:var(--fg);">${fmt(pos.avgPrice)}원</td>
        <td class="text-right" style="color:var(--fg);">${fmt(pos.currentPrice)}원</td>
        <td class="text-right font-bold" style="color:var(--accent);">${fmt(pos.evalAmount)}원</td>
        <td class="text-right font-bold" style="color:${color};">${pnl >= 0 ? '+' : ''}${fmt(pnl)}원</td>
      </tr>`;
    }).join('');
  } catch {
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" class="px-4 py-6 text-center" style="color:var(--muted);">주식 포트폴리오를 불러올 수 없습니다.</td></tr>';
  }
}

function renderStockSectorSummary(positions, totalEval) {
  const container = document.getElementById('stockSectorSummary');
  if (!container) return;
  if (!positions.length) {
    container.innerHTML = '<p class="text-xs" style="color:var(--muted);">섹터별 집계는 주식 보유 후 표시됩니다.</p>';
    return;
  }
  const sectors = positions.reduce((result, pos) => {
    const name = pos.sector || '기타';
    const group = result[name] || { count: 0, evalAmount: 0 };
    group.count += 1;
    group.evalAmount += Number(pos.evalAmount || 0);
    result[name] = group;
    return result;
  }, {});
  const palette = ['#2563EB', '#7C3AED', '#059669', '#EA580C', '#DB2777', '#0891B2'];
  const items = Object.entries(sectors).sort((a, b) => b[1].evalAmount - a[1].evalAmount);
  container.innerHTML = `<div style="font-size:11px;font-weight:800;color:var(--muted);margin-bottom:8px;">섹터별 평가 비중</div><div class="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">${items.map(([sector, data], index) => {
    const pct = totalEval ? data.evalAmount / totalEval * 100 : 0;
    const color = palette[index % palette.length];
    return `<div style="border:1px solid var(--border);border-radius:8px;padding:9px 10px;background:var(--surface-2);">
      <div style="display:flex;justify-content:space-between;gap:8px;font-size:11px;font-weight:800;color:var(--fg);"><span>${sector}</span><span>${pct.toFixed(1)}%</span></div>
      <div style="height:5px;border-radius:99px;background:var(--border);overflow:hidden;margin:7px 0 5px;"><div style="width:${pct}%;height:100%;background:${color};"></div></div>
      <div style="font-size:10px;color:var(--muted);">${data.count}종목 · ${fmt(data.evalAmount)}원</div>
    </div>`;
  }).join('')}</div>`;
}

/* ── 보유 코인 테이블 렌더 ────────────────────────────────────── */
function renderHoldTable(holdCryptoList) {
  const tbody = document.getElementById('holdCryptoTableBody');
  if (!holdCryptoList.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="px-4 py-6 text-center" style="color:var(--muted);">보유 코인이 없습니다.</td></tr>';
    return;
  }
  tbody.innerHTML = holdCryptoList.map(h => `
    <tr>
      <td>
        <div class="flex items-center gap-3">
          <img src="https://static.upbit.com/logos/${h.marketCodeOnlySymbol}.png" alt="" class="h-9 w-9 rounded-full" style="border:1px solid var(--border);">
          <div>
            <p class="font-bold" style="color:var(--fg);">${h.koreanName}</p>
            <p class="text-xs font-semibold" style="color:var(--accent);">${h.marketCodeOnlySymbol}</p>
          </div>
        </div>
      </td>
      <td class="text-right">
        <span class="font-semibold" style="color:var(--fg);" id="${h.marketCode}-hold-count">${fmtDec(h.holdCount, 8)}</span>
        <span class="ml-1 text-xs" style="color:var(--muted);">${h.marketCodeOnlySymbol}</span>
      </td>
      <td class="text-right">
        <span class="font-semibold" style="color:var(--fg);" id="${h.marketCode}-buy-average">${fmtDec(h.buyAverage, 4)}</span>
        <span class="ml-1 text-xs" style="color:var(--muted);">KRW</span>
      </td>
      <td class="text-right">
        <span class="font-semibold" style="color:var(--fg);" id="${h.marketCode}-buy-total-krw">${fmt(h.buyTotalKrw)}</span>
        <span class="ml-1 text-xs" style="color:var(--muted);">KRW</span>
      </td>
      <td class="text-right" style="background:var(--accent-light);">
        <span class="font-bold" style="color:var(--accent);" id="${h.marketCode}-evaluation-krw">-</span>
        <span class="ml-1 text-xs" style="color:var(--muted);">KRW</span>
      </td>
      <td class="text-right">
        <p class="mb-1">
          <span class="font-bold" id="${h.marketCode}-krw-of-return">-</span>
          <span class="ml-1 text-xs" style="color:var(--muted);">KRW</span>
        </p>
        <p>
          <span class="font-black text-base" id="${h.marketCode}-rate-of-return">-</span>
          <span class="ml-1 text-xs" style="color:var(--muted);">%</span>
        </p>
      </td>
    </tr>`).join('');
}

/* ── 업비트 웹소켓 (실시간 평가금액) ──────────────────────────── */
function initWebSocket(marketArrayList, memberAsset, totalBuyKrw) {
  const evalMap = {};
  const socket = new WebSocket(upbitWebSocketUrl());

  socket.onopen = () => {
    socket.send(JSON.stringify([
      { ticket: 'edumgt-hold' },
      { type: 'ticker', codes: marketArrayList },
    ]));
  };

  socket.onmessage = async (e) => {
    try {
      const result = JSON.parse(await e.data.text());
      if (result.type !== 'ticker') return;

      const code      = result.code;
      const nowPrice  = result.trade_price;
      const holdCount = parseFloat(document.getElementById(code + '-hold-count')?.textContent.replaceAll(',', '') || '0');
      const evalKrw   = Math.round(nowPrice * holdCount);
      evalMap[code]   = evalKrw;

      const totalEval = Object.values(evalMap).reduce((a, b) => a + b, 0);
      const totalAsset = memberAsset + totalEval;

      setText('total_evaluation_krw', fmt(totalEval));
      setText('total_member_asset',   fmt(totalAsset));

      const totalReturn = totalEval - totalBuyKrw;
      setColorText('total_krw_of_return', totalReturn > 0 ? '+' + fmt(totalReturn) : fmt(totalReturn), totalReturn);

      const rate = totalBuyKrw > 0 ? (totalEval / totalBuyKrw) * 100 - 100 : 0;
      setColorText('total_evaluation_rate_of_return', rate > 0 ? '+' + rate.toFixed(2) : rate.toFixed(2), rate);

      // 개별 코인 평가
      const buyKrwEl = document.getElementById(code + '-buy-total-krw');
      const buyKrw   = parseFloat(buyKrwEl?.textContent.replaceAll(',', '') || '0');

      setText(code + '-evaluation-krw', fmt(evalKrw));

      const krwReturn = evalKrw - buyKrw;
      setColorText(code + '-krw-of-return', krwReturn > 0 ? '+' + fmt(krwReturn) : fmt(krwReturn), krwReturn);

      const coinRate = buyKrw > 0 ? (evalKrw / buyKrw) * 100 - 100 : 0;
      const coinRateStr = coinRate > 0 ? '+' + coinRate.toFixed(2) : coinRate.toFixed(2);
      setColorText(code + '-rate-of-return', coinRateStr, coinRate);
    } catch {}
  };

  socket.onerror = () => console.warn('업비트 웹소켓 연결 실패');
}

/* ── 포트폴리오 차트 (Highcharts) ──────────────────────────────── */
async function renderPortfolioChart(holdCryptoList, marketArrayList, memberAsset) {
  try {
    let upbitData = [];
    if (marketArrayList.length) {
      const marketListStr = marketArrayList.join(',');
      const upbitRes = await fetch('/upbit-api/ticker?markets=' + encodeURIComponent(marketListStr));
      if (upbitRes.ok) upbitData = await upbitRes.json();
    }

    const priceMap = {};
    upbitData.forEach(d => { priceMap[d.market.split('-')[1]] = d.trade_price; });

    let totalEval = 0;
    const evalMap = {};
    holdCryptoList.forEach(h => {
      const price = priceMap[h.marketCodeOnlySymbol] || 0;
      const eval_ = Math.round(price * h.holdCount);
      evalMap[h.marketCodeOnlySymbol] = eval_;
      totalEval += eval_;
    });

    const totalAsset = memberAsset + totalEval;
    const chartData = holdCryptoList.map(h => ({
      name: h.marketCodeOnlySymbol,
      y: totalAsset > 0 ? (evalMap[h.marketCodeOnlySymbol] / totalAsset) * 100 : 0,
    }));
    chartData.push({ name: 'KRW', y: totalAsset > 0 ? (memberAsset / totalAsset) * 100 : 100 });

    const accentPalette = ['#7C5CFC','#5865F2','#A78BFA','#E11D48','#2563EB','#059669','#F59E0B','#8B5CF6'];
    Highcharts.chart('hold_asset_chart', {
      chart: { plotBackgroundColor:'transparent', backgroundColor:'transparent', type:'pie',
               style:{ fontFamily:"'Pretendard', sans-serif" } },
      title: { text:'보유 비중', align:'center', style:{ color:'#334155', fontSize:'14px', fontWeight:'800' } },
      tooltip: { backgroundColor:'#1A1A2E', borderColor:'rgba(124,92,252,0.3)', style:{ color:'#fff' }, pointFormat:'{series.name}: <b>{point.percentage:.1f}%</b>' },
      plotOptions: { pie: { cursor:'pointer', colors:accentPalette, borderWidth:2, borderColor:'rgba(255,255,255,0.06)', borderRadius:4,
        dataLabels:{ enabled:true, format:'<b style="color:rgba(255,255,255,0.85)">{point.name}</b><br><span style="color:#A78BFA">{point.percentage:.1f}%</span>',
          distance:-45, style:{ fontSize:'12px', fontWeight:'700', textOutline:'none' }, filter:{ property:'percentage', operator:'>', value:4 } } } },
      credits: { enabled:false },
      series: [{ name:'비중', data:chartData }],
    });
  } catch {}
}

/* ── 유틸 ────────────────────────────────────────────────────── */
function setText(id, val) { const el = document.getElementById(id); if (el) el.textContent = val; }
function setColorText(id, val, numericVal) {
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = val;
  el.style.color = numericVal > 0 ? '#F87171' : numericVal < 0 ? '#60A5FA' : 'rgba(255,255,255,0.7)';
}
function fmt(n)          { return new Intl.NumberFormat('ko-KR').format(n); }
function fmtDec(n, dec)  { return new Intl.NumberFormat('ko-KR', { maximumFractionDigits: dec }).format(n); }
