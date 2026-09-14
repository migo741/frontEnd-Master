import test from 'node:test';
import assert from 'node:assert/strict';
import { load, deferred, ticks } from './helpers.mjs';
const { createEditor } = await load('03-autosave');
function fixture() {
  const calls = [];
  const editor = createEditor({
    docId: 'A',
    transport: (input) => {
      const d = deferred();
      calls.push({ ...input, ...d });
      return d.promise;
    }
  });
  return { editor, calls };
}
test('03 / clean 不发请求，同值编辑不脏', async () => {
  const { editor: e, calls } = fixture();
  e.edit('');
  await e.save();
  assert.equal(calls.length, 0);
  assert.equal(e.getSnapshot().editVersion, 0);
});
test('03 / 保存中继续编辑，串行确认各自快照', async () => {
  const { editor: e, calls } = fixture();
  e.edit('one');
  const p = e.save();
  assert.equal(e.save(), p);
  await ticks();
  e.edit('two');
  assert.equal(calls.length, 1);
  calls[0].resolve({ serverVersion: 1 });
  await ticks();
  assert.equal(calls.length, 2);
  assert.equal(calls[1].text, 'two');
  assert.equal(calls[1].baseVersion, 1);
  assert.equal(e.getSnapshot().savedVersion, 1);
  calls[1].resolve({ serverVersion: 2 });
  await p;
  assert.equal(e.getSnapshot().savedVersion, 2);
  assert.equal(e.getSnapshot().request, null);
});
test('03 / 同栈切换文档后不启动旧保存', async () => {
  const { editor: e, calls } = fixture();
  e.edit('old');
  const p = e.save();
  e.open({ docId: 'B' });
  await p;
  assert.equal(calls.length, 0);
});
test('03 / 忽略 abort 的旧成功不能污染新会话', async () => {
  const { editor: e, calls } = fixture();
  e.edit('old');
  const old = e.save();
  await ticks();
  e.open({ docId: 'B', text: 'base', serverVersion: 7 });
  assert.equal(calls[0].signal.aborted, true);
  e.edit('new');
  const current = e.save();
  await ticks();
  calls[0].resolve({ serverVersion: 1 });
  await old;
  assert.equal(e.getSnapshot().docId, 'B');
  assert.equal(e.getSnapshot().text, 'new');
  assert.equal(e.getSnapshot().savedVersion, 0);
  assert.notEqual(e.getSnapshot().request, null);
  calls[1].resolve({ serverVersion: 8 });
  await current;
  assert.equal(e.getSnapshot().serverVersion, 8);
});
test('03 / 旧失败被观察但不变成新文档错误', async () => {
  const { editor: e, calls } = fixture();
  e.edit('old');
  const p = e.save();
  await ticks();
  e.open({ docId: 'B' });
  calls[0].reject(new Error('old'));
  await p;
  assert.equal(e.getSnapshot().error, null);
});
test('03 / 同步抛错保留草稿，显式重试', async () => {
  let n = 0;
  const error = new Error('network');
  const e = createEditor({
    docId: 'A',
    transport: () => {
      if (++n === 1) throw error;
      return { serverVersion: 1 };
    }
  });
  e.edit('draft');
  await assert.rejects(e.save(), (x) => x === error);
  assert.equal(e.getSnapshot().text, 'draft');
  assert.equal(e.getSnapshot().request, null);
  assert.equal(e.getSnapshot().error, error);
  await e.save();
  assert.equal(n, 2);
  assert.equal(e.getSnapshot().savedVersion, 1);
});
test('03 / 异步409冲突停止，不能标为已保存', async () => {
  const { editor: e, calls } = fixture();
  e.edit('draft');
  const p = e.save();
  const error = Object.assign(new Error('Conflict'), { status: 409 });
  const rejection = assert.rejects(p, (x) => x === error);
  await ticks();
  calls[0].reject(error);
  await rejection;
  assert.equal(calls.length, 1);
  assert.equal(e.getSnapshot().savedVersion, 0);
  assert.equal(e.getSnapshot().error.status, 409);
});
test('03 / dispose 幂等，迟到结果和新任务受限', async () => {
  const { editor: e, calls } = fixture();
  e.edit('draft');
  const p = e.save();
  await ticks();
  e.dispose();
  e.dispose();
  assert.equal(calls[0].signal.aborted, true);
  const before = e.getSnapshot();
  calls[0].resolve({ serverVersion: 1 });
  await p;
  assert.deepEqual(e.getSnapshot(), before);
  assert.throws(() => e.edit('x'));
  assert.throws(() => e.save());
});
test('03 / 无效服务端版本走失败路径', async () => {
  const e = createEditor({
    docId: 'A',
    serverVersion: 4,
    transport: async () => ({ serverVersion: 4 })
  });
  e.edit('x');
  await assert.rejects(e.save(), TypeError);
  assert.equal(e.getSnapshot().savedVersion, 0);
});
