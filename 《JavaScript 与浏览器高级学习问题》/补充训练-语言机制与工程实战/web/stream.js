import { mode, $, failure } from './common.js';
const { consumeBatches } = await import(`/labs/04-streams/${mode}/index.js`);
let controller = null,
  worker = null,
  id = 0;
const metrics = { count: 0, sum: 0, batches: 0, maxBatch: 0, pending: 0, maxPending: 0 };
function draw() {
  $('metrics').textContent = JSON.stringify(metrics, null, 2);
}
function ready(target, signal) {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      clearTimeout(timer);
      target.removeEventListener('message', message);
      target.removeEventListener('error', error);
      signal.removeEventListener('abort', abort);
    };
    const message = ({ data }) => {
      if (data.type !== 'ready') return;
      cleanup();
      resolve();
    };
    const error = (event) => {
      cleanup();
      reject(new Error(event.message || 'Worker 启动失败'));
    };
    const abort = () => {
      cleanup();
      reject(signal.reason);
    };
    const timer = setTimeout(() => {
      cleanup();
      reject(new Error('Worker 启动超时'));
    }, 5000);
    target.addEventListener('message', message);
    target.addEventListener('error', error);
    signal.addEventListener('abort', abort, { once: true });
    if (signal.aborted) abort();
  });
}
async function* decode(body, signal) {
  const reader = body.getReader(),
    decoder = new TextDecoder('utf-8', { fatal: true });
  let buffer = '',
    done = false;
  try {
    while (true) {
      signal.throwIfAborted();
      const part = await reader.read();
      if (part.done) {
        done = true;
        buffer += decoder.decode();
        break;
      }
      buffer += decoder.decode(part.value, { stream: true });
      let end;
      while ((end = buffer.indexOf('\n')) >= 0) {
        const line = buffer.slice(0, end);
        buffer = buffer.slice(end + 1);
        if (line.trim()) yield JSON.parse(line);
      }
      if (buffer.length > 1024 * 1024) throw new Error('Line limit');
    }
    if (buffer.trim()) yield JSON.parse(buffer);
  } finally {
    try {
      if (!done) await reader.cancel();
    } finally {
      reader.releaseLock();
    }
  }
}
function job(rows, signal, { cancelOnStarted = false } = {}) {
  const own = ++id;
  metrics.pending++;
  metrics.maxPending = Math.max(metrics.maxPending, metrics.pending);
  return new Promise((resolve, reject) => {
    let began = 0;
    const cancel = () => {
      metrics.cancelSent = true;
      worker.postMessage({ type: 'cancel', id: own });
      draw();
    };
    const cleanup = () => {
      metrics.pending--;
      worker.removeEventListener('message', message);
      worker.removeEventListener('error', error);
      signal.removeEventListener('abort', cancel);
    };
    const error = (e) => {
      cleanup();
      reject(new Error(e.message || 'Worker crashed'));
    };
    const message = ({ data }) => {
      if (data.id !== own) return;
      if (data.type === 'started') {
        metrics.started = true;
        if (cancelOnStarted) {
          began = performance.now();
          cancel();
        }
        return;
      }
      if (!['result', 'error'].includes(data.type)) return;
      if (began) metrics.cancelAckMs = Math.round((performance.now() - began) * 10) / 10;
      cleanup();
      if (data.type === 'result') resolve(data.result);
      else reject(Object.assign(new Error(data.message), { name: data.name }));
    };
    worker.addEventListener('message', message);
    worker.addEventListener('error', error);
    signal.addEventListener('abort', cancel, { once: true });
    worker.postMessage({ type: 'job', id: own, rows });
    if (signal.aborted) cancel();
  });
}
async function start(probe = false) {
  if (controller) return;
  controller = new AbortController();
  worker = new Worker(`/web/analysis.worker.js?mode=${mode}`, { type: 'module' });
  for (const k of Object.keys(metrics)) delete metrics[k];
  Object.assign(metrics, { count: 0, sum: 0, batches: 0, maxBatch: 0, pending: 0, maxPending: 0 });
  $('start').disabled = $('probe').disabled = true;
  $('cancel').disabled = false;
  $('status').textContent = probe ? '探针计算中' : '流式处理进行中';
  draw();
  try {
    await ready(worker, controller.signal);
    if (probe) {
      await job(
        Array.from({ length: 100000 }, (_, value) => ({ value })),
        controller.signal,
        { cancelOnStarted: true }
      );
      throw new Error('探针未响应取消，需检查任务让出');
    }
    const response = await fetch('/api/rows', { signal: controller.signal });
    await consumeBatches(
      decode(response.body, controller.signal),
      async (rows) => {
        metrics.maxBatch = Math.max(metrics.maxBatch, rows.length);
        const result = await job(rows, controller.signal);
        metrics.count += result.count;
        metrics.sum += result.sum;
        metrics.batches++;
        draw();
      },
      { batchSize: 128, signal: controller.signal }
    );
    $('status').textContent = '处理完成';
  } catch (e) {
    if (e.name === 'AbortError')
      $('status').textContent = probe ? 'Worker 已在计算中确认取消' : '本次处理已取消';
    else failure(e);
  } finally {
    worker.terminate();
    worker = null;
    controller = null;
    $('start').disabled = $('probe').disabled = false;
    $('cancel').disabled = true;
    draw();
  }
}
$('start').onclick = () => start();
$('probe').onclick = () => start(true);
$('cancel').onclick = () => {
  controller?.abort();
  $('status').textContent = '正在取消';
};
draw();
addEventListener(
  'pagehide',
  () => {
    controller?.abort();
    worker?.terminate();
  },
  { once: true }
);
