(() => {
  const button = document.getElementById('run-test');
  const result = document.getElementById('result');
  if (!button || !result) return;
  button.addEventListener('click', async () => {
    button.disabled = true;
    result.classList.remove('result--error');
    result.textContent = 'Alpaca Paper API에 읽기 전용 요청을 보내는 중…';
    try {
      const response = await fetch(`${window.APP_CONFIG?.apiBase || ''}/api/alpaca-test/paper/account`);
      const data = await response.json();
      if (!data.ok) {
        result.classList.add('result--error');
        result.textContent = `점검 결과: 실패\n${data.message || '알 수 없는 오류'}`;
        return;
      }
      const info = data.result;
      result.textContent = [
        '점검 결과: 성공', `환경: ${info.environment}`, `연결: ${info.connection}`,
        `계정 상태: ${info.accountStatus || '-'}`, `통화: ${info.currency || '-'}`,
        `거래 차단: ${info.tradingBlocked ? '예' : '아니오'}`,
        `계정 차단: ${info.accountBlocked ? '예' : '아니오'}`,
      ].join('\n');
    } catch (error) {
      result.classList.add('result--error');
      result.textContent = `요청 실패\n${error.message}`;
    } finally { button.disabled = false; }
  });
})();
