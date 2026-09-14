export async function consumeBatches(source, handleBatch, { batchSize = 128, signal } = {}) {
  throw new Error('TODO: 有界、顺序、有清理的异步消费');
}
export async function summarize(
  rows,
  { signal, chunkSize = 64, yieldTask = () => new Promise((r) => setTimeout(r, 0)) } = {}
) {
  throw new Error('TODO: Worker 内计算要给取消消息执行机会');
}
