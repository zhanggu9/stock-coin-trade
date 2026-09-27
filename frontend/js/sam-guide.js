(() => {
  let toastTimer;
  const toast = message => {
    const node = document.getElementById('lambda-toast');
    node.textContent = message;
    node.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => node.classList.remove('show'), 1600);
  };

  document.addEventListener('DOMContentLoaded', async () => {
    await initPage();
    document.querySelectorAll('[data-copy-code]').forEach(button => {
      button.addEventListener('click', async () => {
        const value = button.closest('.lambda-code').querySelector('code').textContent;
        try {
          await navigator.clipboard.writeText(value);
        } catch {
          const area = document.createElement('textarea');
          area.value = value;
          document.body.appendChild(area);
          area.select();
          document.execCommand('copy');
          area.remove();
        }
        toast('코드를 복사했습니다.');
      });
    });
  });
})();
