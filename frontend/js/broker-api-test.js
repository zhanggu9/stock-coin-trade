(() => {
  const apiBase = window.APP_CONFIG?.apiBase || '';
  const format = (data) => {
    if (!data.ok) return `점검 결과: 실패\n${data.message || '알 수 없는 오류'}`;
    const q = data.quote;
    return [
      '성공', `증권사: ${q.broker}`, `종목코드: ${q.symbol}`,
      `현재가: ${Number(q.price ?? 0).toLocaleString()}원`,
      `전일대비: ${q.change ?? '-'}`, `등락률: ${q.changeRate ?? '-'}%`,
      `누적거래량: ${q.volume ?? '-'}`, `체결시각: ${q.tradeTime || '-'}`,
    ].join('\n');
  };
  document.querySelectorAll('.run').forEach((button) => {
    button.addEventListener('click', async () => {
      const broker = button.dataset.broker;
      const symbol = document.getElementById(`${broker}-symbol`).value.trim();
      const result = document.getElementById(`${broker}-result`);
      if (!/^\d{6}$/.test(symbol)) { result.textContent = '종목코드는 6자리 숫자로 입력하세요.'; return; }
      button.disabled = true;
      result.classList.remove('result--error');
      result.textContent = '서버에서 읽기 전용 API를 호출하는 중…';
      try {
        const response = await fetch(`${apiBase}/api/broker-test/${broker}/quote?symbol=${encodeURIComponent(symbol)}`);
        const data = await response.json();
        result.textContent = format(data);
        result.classList.toggle('result--error', !data.ok);
      } catch (error) {
        result.textContent = `요청 실패\n${error.message}`;
        result.classList.add('result--error');
      } finally { button.disabled = false; }
    });
  });
})();
