export const initialSaveState = (text = '') =>
  Object.freeze({ text, editVersion: 0, savedVersion: 0, request: null, error: null });
export const isDirty = (s) => s.editVersion > s.savedVersion;
export const isSaving = (s) => s.request !== null;
export function transition(s, e) {
  if (e.type === 'EDITED')
    return Object.is(s.text, e.text)
      ? { state: s, commands: [] }
      : {
          state: { ...s, text: e.text, editVersion: s.editVersion + 1, error: null },
          commands: []
        };
  if (e.type === 'SAVE_REQUESTED') {
    if (!isDirty(s) || isSaving(s)) return { state: s, commands: [] };
    if (typeof e.requestId !== 'string' || !e.requestId) throw new TypeError('requestId');
    const request = { id: e.requestId, version: s.editVersion, text: s.text };
    return { state: { ...s, request, error: null }, commands: [{ type: 'SAVE', ...request }] };
  }
  if (e.type === 'SAVE_SUCCEEDED' || e.type === 'SAVE_FAILED') {
    if (!s.request || s.request.id !== e.requestId || s.request.version !== e.version)
      return { state: s, commands: [] };
    return {
      state: {
        ...s,
        request: null,
        savedVersion:
          e.type === 'SAVE_SUCCEEDED'
            ? Math.max(s.savedVersion, s.request.version)
            : s.savedVersion,
        error: e.type === 'SAVE_FAILED' ? e.error : null
      },
      commands: []
    };
  }
  return { state: s, commands: [] };
}
