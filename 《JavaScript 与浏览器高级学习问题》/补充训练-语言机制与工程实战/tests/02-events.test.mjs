import test from 'node:test';
import assert from 'node:assert/strict';
import { load } from './helpers.mjs';
const { createHub } = await load('02-events');
test('02 / 取消订阅幂等且事件隔离', () => {
  const h = createHub(),
    log = [];
  const off = h.on('x', (v) => log.push(v));
  h.emit('y', 0);
  h.emit('x', 1);
  off();
  off();
  h.emit('x', 2);
  assert.deepEqual(log, [1]);
  h.dispose();
});
test('02 / 重入按 FIFO，不递归插队', () => {
  const h = createHub(),
    log = [];
  h.on('x', (v) => {
    log.push('a' + v);
    if (v === 1) h.emit('x', 2);
  });
  h.on('x', (v) => log.push('b' + v));
  h.emit('x', 1);
  assert.deepEqual(log, ['a1', 'b1', 'a2', 'b2']);
});
test('02 / once 在调用前移除', () => {
  const h = createHub();
  let n = 0;
  h.on(
    'x',
    () => {
      n++;
      if (n < 3) h.emit('x');
    },
    { once: true }
  );
  h.emit('x');
  assert.equal(n, 1);
});
test('02 / 分发期间添加者下轮生效、删除者本轮跳过', () => {
  const h = createHub(),
    log = [];
  let off;
  h.on('x', () => {
    log.push('a');
    off();
    h.on('x', () => log.push('new'));
  });
  off = h.on('x', () => log.push('b'));
  h.emit('x');
  assert.deepEqual(log, ['a']);
  h.emit('x');
  assert.deepEqual(log, ['a', 'a', 'new']);
});
test('02 / 订阅项独立，不按函数身份去重', () => {
  const h = createHub();
  let n = 0;
  const f = () => n++;
  const off = h.on('x', f);
  h.on('x', f);
  off();
  h.emit('x');
  assert.equal(n, 1);
});
test('02 / abort 与预取消', () => {
  const h = createHub(),
    a = new AbortController();
  let n = 0;
  h.on('x', () => n++, { signal: a.signal });
  a.abort();
  h.on('x', () => n++, { signal: a.signal });
  h.emit('x');
  assert.equal(n, 0);
});
test('02 / 异常隔离与错误通道', () => {
  const errors = [],
    h = createHub({
      onError: (e) => {
        errors.push(e.message);
        throw 0;
      }
    });
  let n = 0;
  h.on('x', () => {
    throw new Error('bad');
  });
  h.on('x', () => n++);
  h.emit('x');
  assert.deepEqual(errors, ['bad']);
  assert.equal(n, 1);
});
test('02 / dispose 停止当前分发和排队事件', () => {
  const h = createHub(),
    log = [];
  h.on('x', () => {
    h.emit('y');
    h.dispose();
    log.push(1);
  });
  h.on('x', () => log.push(2));
  h.on('y', () => log.push(3));
  h.emit('x');
  h.dispose();
  h.emit('x');
  assert.deepEqual(log, [1]);
  assert.throws(() => h.on('x', () => {}));
});
test('02 / 深度重入不溢栈', () => {
  const h = createHub();
  let n = 0;
  h.on('x', () => {
    n++;
    if (n < 20000) h.emit('x');
  });
  h.emit('x');
  assert.equal(n, 20000);
});
