function positive(n) {
  if (!Number.isInteger(n) || n < 1) throw new RangeError('positive integer required');
}
export async function consumeBatches(source, handleBatch, { batchSize = 128, signal } = {}) {
  positive(batchSize);
  signal?.throwIfAborted();
  const iterator = source[Symbol.asyncIterator]();
  let done = false,
    failed = false,
    count = 0;
  try {
    let batch = [];
    while (true) {
      signal?.throwIfAborted();
      const item = await iterator.next();
      signal?.throwIfAborted();
      if (item.done) {
        done = true;
        break;
      }
      batch.push(item.value);
      if (batch.length === batchSize) {
        await handleBatch(batch);
        count += batch.length;
        batch = [];
      }
    }
    signal?.throwIfAborted();
    if (batch.length) {
      await handleBatch(batch);
      count += batch.length;
    }
    signal?.throwIfAborted();
    return count;
  } catch (error) {
    failed = true;
    throw error;
  } finally {
    if (!done && typeof iterator.return === 'function') {
      try {
        await iterator.return();
      } catch (error) {
        if (!failed) throw error;
      }
    }
  }
}
export async function summarize(
  rows,
  { signal, chunkSize = 64, yieldTask = () => new Promise((r) => setTimeout(r, 0)) } = {}
) {
  positive(chunkSize);
  signal?.throwIfAborted();
  let sum = 0;
  for (let start = 0; start < rows.length; start += chunkSize) {
    const end = Math.min(rows.length, start + chunkSize);
    for (let i = start; i < end; i++) {
      if (!Number.isFinite(rows[i]?.value)) throw new TypeError('finite row.value required');
      sum += rows[i].value;
    }
    if (end < rows.length) {
      await yieldTask();
      signal?.throwIfAborted();
    }
  }
  return { count: rows.length, sum };
}
