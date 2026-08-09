const form = document.querySelector('#crawl-form');
const statusEl = document.querySelector('#sheet-status');
const workspace = document.querySelector('#sheet-workspace');
const table = document.querySelector('#data-sheet');
let model = { columns: [], rows: [] };

initPage();

function esc(value) {
  return String(value ?? '').replace(/[&<>"']/g, char => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  })[char]);
}
function draw() {
  table.innerHTML = `<thead><tr>${model.columns.map((column, i) => `<th><input aria-label="${i + 1}번째 열 제목" value="${esc(column)}"></th>`).join('')}</tr></thead><tbody>${model.rows.map(row => `<tr>${model.columns.map((_, i) => `<td><input value="${esc(row[i] ?? '')}"></td>`).join('')}</tr>`).join('')}</tbody>`;
}
function readModel() {
  model.columns = [...table.querySelectorAll('thead input')].map(input => input.value.trim() || '열');
  model.rows = [...table.querySelectorAll('tbody tr')].map(row => [...row.querySelectorAll('input')].map(input => input.value));
}
function csvCell(value) { return `"${String(value).replaceAll('"', '""')}"`; }

form.addEventListener('submit', async event => {
  event.preventDefault();
  const button = document.querySelector('#crawl-button'); const url = document.querySelector('#source-url').value.trim();
  button.disabled = true; statusEl.className = 'sheet-status loading'; statusEl.textContent = '페이지를 읽고 시트를 만드는 중입니다…'; workspace.hidden = true;
  try {
    const response = await apiFetch('/api/ai-sheet/crawl', { method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({url}) });
    const data = await response.json();
    if (!response.ok) throw new Error(data.message || '시트를 만들지 못했습니다.');
    model = { columns: data.columns, rows: data.rows }; draw();
    document.querySelector('#sheet-title').textContent = data.title;
    const source = document.querySelector('#sheet-source'); source.href = data.sourceUrl; source.textContent = `${data.sourceType} 원문 열기 ↗`;
    statusEl.className = 'sheet-status'; statusEl.textContent = `${data.rows.length}행 · ${data.columns.length}열을 가져왔습니다. ${data.notice}`; workspace.hidden = false;
  } catch (error) { statusEl.className = 'sheet-status error'; statusEl.textContent = error.message; }
  finally { button.disabled = false; }
});
document.querySelector('#add-row').addEventListener('click', () => { readModel(); model.rows.push(Array(model.columns.length).fill('')); draw(); table.querySelector('tbody tr:last-child input')?.focus(); });
document.querySelector('#download-csv').addEventListener('click', () => { readModel(); const csv = [model.columns, ...model.rows].map(row => row.map(csvCell).join(',')).join('\r\n'); const link = document.createElement('a'); link.href = URL.createObjectURL(new Blob(['\ufeff' + csv], {type:'text/csv;charset=utf-8'})); link.download = 'ai-sheet.csv'; link.click(); URL.revokeObjectURL(link.href); });
