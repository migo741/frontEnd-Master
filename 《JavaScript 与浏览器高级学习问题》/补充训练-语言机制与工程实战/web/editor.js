import { mode, $, failure } from './common.js';
const { createEditor } = await import(`/labs/03-autosave/${mode}/index.js`);
const records = { A: { text: '', serverVersion: 0 }, B: { text: '', serverVersion: 0 } };
let serial = 0,
  timer,
  editor;
const requests = [];
function draw() {
  if (!editor) return;
  const state = editor.getSnapshot();
  $('state').textContent = JSON.stringify(
    state,
    (k, v) => (v instanceof Error ? { message: v.message, status: v.status } : v),
    2
  );
  $('server').textContent = JSON.stringify(records, null, 2);
  $('status').textContent = state.disposed
    ? '会话已销毁'
    : state.error
      ? `保存失败：${state.error.message}`
      : state.request
        ? '保存中'
        : state.editVersion > state.savedVersion
          ? '尚有未保存编辑'
          : '当前版本已保存';
}
function transport(input) {
  return new Promise((resolve, reject) => {
    const number = ++serial,
      request = { input, done: false };
    requests.push(request);
    const row = document.createElement('div');
    row.className = 'bar';
    const label = document.createElement('span');
    label.textContent = `#${number} 文档${input.docId} · base=${input.baseVersion} · ${input.text.slice(0, 30)}`;
    row.append(label);
    function settle(kind) {
      if (request.done) return;
      request.done = true;
      input.signal.removeEventListener('abort', onAbort);
      for (const button of row.querySelectorAll('button')) button.disabled = true;
      if (kind === 'ok' && records[input.docId].serverVersion === input.baseVersion) {
        records[input.docId] = { text: input.text, serverVersion: input.baseVersion + 1 };
        resolve({ ...records[input.docId] });
      } else {
        const conflict = kind === 'conflict' || kind === 'ok';
        reject(
          Object.assign(new Error(conflict ? '版本冲突' : '模拟网络失败'), {
            status: conflict ? 409 : 503
          })
        );
      }
      queueMicrotask(() => queueMicrotask(draw));
    }
    for (const [text, kind] of [
      ['成功', 'ok'],
      ['失败', 'error'],
      ['409冲突', 'conflict']
    ]) {
      const b = document.createElement('button');
      b.textContent = text;
      b.className = 'secondary';
      b.onclick = () => settle(kind);
      row.append(b);
    }
    function onAbort() {
      label.textContent += ' · 已收到取消';
      if (!$('ignore').checked) settle('error');
    }
    input.signal.addEventListener('abort', onAbort, { once: true });
    $('requests').append(row);
  });
}
async function save() {
  try {
    const p = editor.save();
    queueMicrotask(draw);
    await p;
  } catch (e) {
    failure(e);
  } finally {
    draw();
  }
}
try {
  editor = createEditor({ docId: 'A', transport });
  draw();
} catch (e) {
  failure(e);
}
$('text').oninput = () => {
  if (!editor) return;
  try {
    editor.edit($('text').value);
    draw();
    clearTimeout(timer);
    timer = setTimeout(save, 300);
  } catch (e) {
    failure(e);
  }
};
$('save').onclick = () => {
  clearTimeout(timer);
  if (editor) save();
};
for (const id of ['A', 'B'])
  $('doc' + id).onclick = () => {
    if (!editor) return;
    try {
      clearTimeout(timer);
      editor.open({ docId: id, ...records[id] });
      $('text').value = records[id].text;
      draw();
    } catch (e) {
      failure(e);
    }
  };
$('dispose').onclick = () => {
  clearTimeout(timer);
  editor?.dispose();
  draw();
};
addEventListener(
  'pagehide',
  () => {
    clearTimeout(timer);
    editor?.dispose();
  },
  { once: true }
);
