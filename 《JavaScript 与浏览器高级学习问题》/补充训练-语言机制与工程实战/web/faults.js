import { mode, $ } from './common.js';
const { createSearch, mountPanel, resizeRows } = await import(`/labs/05-faults/${mode}/index.js`);
const timeline = [];
let searchRun = 0;
const log = (x) => {
  timeline.push(x);
  $('timeline').textContent = timeline.join('\n');
};
const search = createSearch({
  // 故意忽略 signal 的传输适配器，检验结果归属是否也被保护。
  fetchRows: (query) =>
    new Promise((resolve) => {
      log('开始 ' + query);
      setTimeout(
        () => {
          log('完成 ' + query);
          resolve([query]);
        },
        query.startsWith('旧') ? 400 : 70
      );
    }),
  render: (rows) => {
    $('result').textContent = '显示：' + rows.join(',');
    log('显示 ' + rows);
  },
  onError: (e) => log('错误 ' + e.message)
});
$('repro').onclick = () => {
  searchRun++;
  search.search('旧查询' + searchRun);
  search.search('新查询' + searchRun);
};
$('resetA').onclick = () => {
  $('result').textContent = '尚未搜索';
  timeline.length = 0;
  $('timeline').textContent = '';
};
class TrackedEvents extends EventTarget {
  listeners = new Set();
  addEventListener(t, f, o) {
    super.addEventListener(t, f, o);
    if (t === 'tick') this.listeners.add(f);
  }
  removeEventListener(t, f, o) {
    super.removeEventListener(t, f, o);
    if (t === 'tick') this.listeners.delete(f);
  }
}
const events = new TrackedEvents();
let cycles = 0;
const resources = () => {
  $('resources').textContent =
    `已开关 ${cycles} 次 · 当前面板 ${$('panel').children.length} · 外部订阅 ${events.listeners.size}`;
};
$('cycle').onclick = () => {
  for (let i = 0; i < 100; i++) {
    const off = mountPanel({ root: $('panel'), events });
    off();
    cycles++;
  }
  resources();
};
$('tick').onclick = () => events.dispatchEvent(new Event('tick'));
resources();
for (let i = 0; i < 2000; i++) {
  const row = document.createElement('div');
  row.textContent = `第 ${i} 行。用于稳定复现的表格数据，包含会因宽度变化而换行的说明文字。`;
  $('table').append(row);
}
let narrow = false;
$('resize').onclick = () => {
  narrow = !narrow;
  const start = performance.now();
  performance.mark('resize-start');
  const total = resizeRows([...$('table').children], narrow ? 210 : 420);
  performance.mark('resize-end');
  performance.measure('resizeRows', 'resize-start', 'resize-end');
  $('timing').textContent =
    `本次 ${(performance.now() - start).toFixed(1)}ms · 汇总高度 ${total.toFixed(0)}px（应随宽度变化）`;
};
addEventListener('pagehide', () => search.dispose(), { once: true });
