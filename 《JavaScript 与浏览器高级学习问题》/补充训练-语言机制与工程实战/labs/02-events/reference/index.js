export function createHub({ onError = () => {} } = {}) {
  const buckets = new Map();
  const queue = [];
  let draining = false,
    disposed = false;
  function report(error) {
    try {
      onError(error);
    } catch {
      /* 报错通道不允许破坏分发 */
    }
  }
  function on(type, callback, { once = false, signal } = {}) {
    if (disposed) throw new Error('Hub disposed');
    if (typeof callback !== 'function') throw new TypeError('callback');
    if (signal?.aborted) return () => {};
    const record = { callback, once, active: true };
    let bucket = buckets.get(type);
    if (!bucket) buckets.set(type, (bucket = new Set()));
    bucket.add(record);
    const off = () => {
      if (!record.active) return;
      record.active = false;
      bucket.delete(record);
      signal?.removeEventListener('abort', off);
      if (!bucket.size && buckets.get(type) === bucket) buckets.delete(type);
    };
    record.off = off;
    signal?.addEventListener('abort', off, { once: true });
    return off;
  }
  function emit(type, payload) {
    if (disposed) return;
    queue.push([type, payload]);
    if (draining) return;
    draining = true;
    try {
      // 游标避免 shift 的反复搬移；finally 释放所有排队 payload。
      for (let i = 0; i < queue.length && !disposed; i++) {
        const [type, payload] = queue[i];
        const snapshot = [...(buckets.get(type) ?? [])];
        for (const record of snapshot) {
          if (disposed) break;
          if (!record.active) continue;
          if (record.once) record.off();
          try {
            record.callback(payload);
          } catch (error) {
            report(error);
          }
        }
      }
    } finally {
      queue.length = 0;
      draining = false;
    }
  }
  function dispose() {
    if (disposed) return;
    disposed = true;
    for (const bucket of [...buckets.values()]) for (const r of [...bucket]) r.off();
    queue.length = 0;
  }
  return { on, emit, dispose };
}
