import { initialSaveState, transition, isDirty } from '../state.js';
export function createEditor({ docId, text = '', serverVersion = 0, transport }) {
  // 复用上面的状态机，实现 getSnapshot/edit/save/open/dispose。
  throw new Error('TODO: 补齐 command runner 与会话生命周期');
}
