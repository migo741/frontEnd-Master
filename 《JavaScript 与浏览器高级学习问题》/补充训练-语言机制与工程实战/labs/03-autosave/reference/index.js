import { initialSaveState, transition, isDirty } from '../state.js';
export function createEditor({ docId, text = '', serverVersion = 0, transport }) {
  if (typeof transport !== 'function') throw new TypeError('transport');
  let state = initialSaveState(text),
    epoch = 0,
    sequence = 0,
    disposed = false,
    flight = null;
  const alive = () => {
    if (disposed) throw new Error('Editor disposed');
  };
  function dispatch(event) {
    const next = transition(state, event);
    state = next.state;
    return next.commands;
  }
  function edit(text) {
    alive();
    if (typeof text !== 'string') throw new TypeError('text');
    dispatch({ type: 'EDITED', text });
  }
  function save() {
    alive();
    if (flight) return flight.promise;
    if (!isDirty(state)) return Promise.resolve();
    const owner = { epoch, controller: new AbortController(), promise: null };
    flight = owner;
    // 延至微任务开始，先安装 flight.promise，支持同步抛错和同栈 save 去重。
    owner.promise = Promise.resolve()
      .then(async () => {
        while (!disposed && owner.epoch === epoch && isDirty(state)) {
          const [command] = dispatch({
            type: 'SAVE_REQUESTED',
            requestId: `${epoch}:${++sequence}`
          });
          if (!command) break;
          const event = { requestId: command.id, version: command.version };
          try {
            const result = await transport({
              docId,
              text: command.text,
              baseVersion: serverVersion,
              requestId: command.id,
              signal: owner.controller.signal
            });
            if (disposed || owner.epoch !== epoch) return;
            if (!Number.isInteger(result?.serverVersion) || result.serverVersion <= serverVersion)
              throw new TypeError('Invalid serverVersion');
            serverVersion = result.serverVersion;
            dispatch({ type: 'SAVE_SUCCEEDED', ...event });
          } catch (error) {
            if (disposed || owner.epoch !== epoch) return;
            dispatch({ type: 'SAVE_FAILED', ...event, error });
            throw error; // 保留草稿，停止自动重试，调用方负责呈现。
          }
        }
      })
      .finally(() => {
        if (flight === owner) flight = null;
      });
    return owner.promise;
  }
  function invalidate() {
    epoch++;
    const old = flight;
    flight = null;
    old?.controller.abort(new DOMException('Session ended', 'AbortError'));
  }
  function open(next) {
    alive();
    invalidate();
    docId = next.docId;
    serverVersion = next.serverVersion ?? 0;
    state = initialSaveState(next.text ?? '');
  }
  function dispose() {
    if (disposed) return;
    disposed = true;
    invalidate();
  }
  return {
    edit,
    save,
    open,
    dispose,
    getSnapshot: () => ({ docId, serverVersion, ...state, disposed })
  };
}
