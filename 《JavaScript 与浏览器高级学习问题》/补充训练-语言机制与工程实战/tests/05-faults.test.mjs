import test from 'node:test';
import assert from 'node:assert/strict';
import { load, deferred } from './helpers.mjs';
const { createSearch, mountPanel, resizeRows, readFeature } = await load('05-faults');
test('05 / 场景A：最后一次意图决定显示', async () => {
  const a = deferred(),
    b = deferred(),
    seen = [];
  const s = createSearch({
    fetchRows: (q) => (q === 'a' ? a.promise : b.promise),
    render: (r) => seen.push(r)
  });
  const x = s.search('a'),
    y = s.search('b');
  b.resolve(['B']);
  await y;
  a.resolve(['A']);
  await x;
  assert.deepEqual(seen, [['B']]);
});
test('05 / 场景A：过期错误和销毁后的结果无效', async () => {
  const a = deferred(),
    b = deferred(),
    seen = [];
  const s = createSearch({
    fetchRows: (q) => (q === 'a' ? a.promise : b.promise),
    render: (r) => seen.push(r),
    onError: (e) => seen.push(e)
  });
  const x = s.search('a'),
    y = s.search('b');
  a.reject('old');
  await x;
  s.dispose();
  b.resolve('late');
  await y;
  assert.deepEqual(seen, []);
});
test('05 / 场景A：当前错误仍需呈现', async () => {
  const seen = [];
  const s = createSearch({
    fetchRows: () => {
      throw new Error('current');
    },
    render: () => {},
    onError: (e) => seen.push(e.message)
  });
  await s.search('x');
  assert.deepEqual(seen, ['current']);
});
test('05 / 场景B：100次挂载销毁后订阅回到基线', () => {
  const listeners = new Set();
  const events = {
    addEventListener: (_, f) => listeners.add(f),
    removeEventListener: (_, f) => listeners.delete(f)
  };
  let nodes = 0;
  const root = {
    ownerDocument: {
      createElement: () => ({
        dataset: {},
        remove() {
          nodes--;
        }
      })
    },
    append() {
      nodes++;
    }
  };
  for (let i = 0; i < 100; i++) {
    const off = mountPanel({ root, events });
    off();
  }
  assert.equal(nodes, 0);
  assert.equal(listeners.size, 0);
});
test('05 / 场景B：销毁幂等', () => {
  let removed = 0;
  const root = {
    ownerDocument: {
      createElement: () => ({
        dataset: {},
        remove() {
          removed++;
        }
      })
    },
    append() {}
  };
  const off = mountPanel({ root, events: new EventTarget() });
  off();
  off();
  assert.equal(removed, 1);
});
test('05 / 场景C：尺寸正确且布局屏障有界', () => {
  let dirty = false,
    flushes = 0;
  const rows = Array.from({ length: 100 }, () => {
    let width = 0;
    return {
      style: {
        set width(v) {
          width = parseFloat(v);
          dirty = true;
        }
      },
      getBoundingClientRect() {
        if (dirty) {
          flushes++;
          dirty = false;
        }
        return { height: width / 10 };
      }
    };
  });
  assert.equal(resizeRows(rows, 200), 2000);
  assert.ok(flushes <= 2, `布局读写切换 ${flushes} 次，应批量安排`);
});
test('05 / 场景D：两个灰度配置协议均可消费', () => {
  assert.equal(readFeature({ schema: 1, inventoryEnabled: true }), true);
  assert.equal(readFeature({ schema: 2, features: { inventory: { enabled: false } } }), false);
});
test('05 / 场景D：未知或错误形状显式失败', () => {
  assert.throws(
    () => readFeature({ schema: 99, features: { inventory: { enabled: true } } }),
    TypeError
  );
  assert.throws(
    () => readFeature({ schema: 2, features: { inventory: { enabled: 'false' } } }),
    TypeError
  );
});
