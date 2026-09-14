import test from 'node:test';
import assert from 'node:assert/strict';
import { load, deferred, ticks } from './helpers.mjs';
const { consumeBatches, summarize } = await load('04-streams');
async function* values(n) {
  for (let i = 0; i < n; i++) yield i;
}
test('04 / 完整顺序与尾批', async () => {
  const batches = [];
  const n = await consumeBatches(values(5), async (b) => batches.push(b), { batchSize: 2 });
  assert.equal(n, 5);
  assert.deepEqual(batches, [[0, 1], [2, 3], [4]]);
});
test('04 / 慢下游期间不预读，批次所有权不复用', async () => {
  let pulled = 0;
  const gate = deferred(),
    seen = [];
  async function* source() {
    for (let i = 0; i < 8; i++) {
      pulled++;
      yield i;
    }
  }
  const p = consumeBatches(
    source(),
    async (b) => {
      seen.push(b);
      if (seen.length === 1) await gate.promise;
    },
    { batchSize: 2 }
  );
  // 学生实现可能立即拒绝；测试本身也要观察它，并在断言失败时释放gate。
  p.catch(() => {});
  try {
    await ticks(30);
    assert.equal(pulled, 2);
  } finally {
    gate.resolve();
    await p.catch(() => {});
  }
  await p;
  assert.deepEqual(seen[0], [0, 1]);
  assert.equal(seen.length, 4);
});
test('04 / 下游失败关闭上游一次', async () => {
  let closed = 0;
  async function* source() {
    try {
      yield 1;
      yield 2;
    } finally {
      closed++;
    }
  }
  const error = new Error('sink');
  await assert.rejects(
    consumeBatches(
      source(),
      () => {
        throw error;
      },
      { batchSize: 1 }
    ),
    (e) => e === error
  );
  assert.equal(closed, 1);
});
test('04 / 取消保留原reason并关闭', async () => {
  const a = new AbortController();
  let closed = 0;
  const reason = new Error('stop');
  async function* source() {
    try {
      yield 1;
      yield 2;
    } finally {
      closed++;
    }
  }
  await assert.rejects(
    consumeBatches(source(), () => a.abort(reason), { batchSize: 1, signal: a.signal }),
    (e) => e === reason
  );
  assert.equal(closed, 1);
});
test('04 / 预取消不取得iterator，空输入不调下游', async () => {
  const a = new AbortController();
  a.abort('stop');
  let obtained = false;
  await assert.rejects(
    consumeBatches(
      {
        [Symbol.asyncIterator]() {
          obtained = true;
        }
      },
      () => {},
      { signal: a.signal }
    ),
    (e) => e === 'stop'
  );
  assert.equal(obtained, false);
  assert.equal(await consumeBatches(values(0), () => assert.fail()), 0);
});
test('04 / 参数与主异常优先', async () => {
  await assert.rejects(
    consumeBatches(values(0), () => {}, { batchSize: 0 }),
    RangeError
  );
  const source = {
    [Symbol.asyncIterator]() {
      return {
        next: async () => ({ value: 1, done: false }),
        return: async () => {
          throw new Error('cleanup');
        }
      };
    }
  };
  await assert.rejects(
    consumeBatches(
      source,
      () => {
        throw new Error('primary');
      },
      { batchSize: 1 }
    ),
    /primary/
  );
});
test('04 / 分片计算与边界验证', async () => {
  let yields = 0;
  assert.deepEqual(
    await summarize(
      Array.from({ length: 10 }, (_, value) => ({ value })),
      { chunkSize: 3, yieldTask: async () => yields++ }
    ),
    { sum: 45, count: 10 }
  );
  assert.equal(yields, 3);
  await assert.rejects(summarize([{ value: NaN }]), TypeError);
});
test('04 / 让出后检查取消，不能跑完整个数组', async () => {
  const a = new AbortController();
  let reads = 0,
    yields = 0;
  const row = {
    get value() {
      reads++;
      return 1;
    }
  };
  await assert.rejects(
    summarize(Array(1000).fill(row), {
      chunkSize: 10,
      signal: a.signal,
      yieldTask: async () => {
        yields++;
        a.abort('stop');
      }
    }),
    (e) => e === 'stop'
  );
  assert.equal(yields, 1);
  assert.ok(reads <= 20);
});
test('04 / 默认让出允许task取消，微任务不够', async () => {
  const a = new AbortController();
  const timer = setTimeout(() => a.abort('task-cancel'), 0);
  try {
    await assert.rejects(
      summarize(Array(1000).fill({ value: 1 }), { chunkSize: 10, signal: a.signal }),
      (e) => e === 'task-cancel'
    );
  } finally {
    clearTimeout(timer);
  }
});
