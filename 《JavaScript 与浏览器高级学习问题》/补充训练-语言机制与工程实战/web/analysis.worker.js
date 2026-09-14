const mode =
  new URL(self.location.href).searchParams.get('mode') === 'reference' ? 'reference' : 'src';
const { summarize } = await import(`/labs/04-streams/${mode}/index.js`);
const jobs = new Map();
self.onmessage = async ({ data }) => {
  if (data.type === 'cancel') {
    jobs.get(data.id)?.abort(new DOMException('User cancelled', 'AbortError'));
    return;
  }
  if (data.type !== 'job') return;
  const controller = new AbortController();
  jobs.set(data.id, controller);
  postMessage({ type: 'started', id: data.id });
  try {
    const result = await summarize(data.rows, { signal: controller.signal, chunkSize: 64 });
    postMessage({ type: 'result', id: data.id, result });
  } catch (error) {
    postMessage({ type: 'error', id: data.id, name: error.name, message: error.message });
  } finally {
    jobs.delete(data.id);
  }
};
// 模块依赖就绪且消息处理器安装之后，主线程才能提交第一个任务。
postMessage({ type: 'ready' });
