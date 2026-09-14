export function createSearch({ fetchRows, render, onError = () => {} }) {
  let generation = 0,
    disposed = false,
    controller = null;
  return {
    async search(query) {
      if (disposed) return;
      const own = ++generation;
      controller?.abort();
      const current = new AbortController();
      controller = current;
      try {
        const rows = await fetchRows(query, { signal: current.signal });
        if (!disposed && own === generation) render(rows);
      } catch (e) {
        if (!disposed && own === generation) onError(e);
      }
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      generation++;
      controller?.abort();
      controller = null;
    }
  };
}
export function mountPanel({ root, events }) {
  let panel = root.ownerDocument.createElement('article');
  panel.textContent = '详情面板 ' + 'x'.repeat(50000);
  root.append(panel);
  const update = () => {
    if (panel) panel.dataset.updated = 'yes';
  };
  events.addEventListener('tick', update);
  return () => {
    if (!panel) return;
    events.removeEventListener('tick', update);
    panel.remove();
    panel = null;
  };
}
export function resizeRows(rows, width) {
  for (const row of rows) row.style.width = `${width}px`;
  let height = 0;
  for (const row of rows) height += row.getBoundingClientRect().height;
  return height;
}

export function readFeature(config) {
  if (config?.schema === 2 && typeof config.features?.inventory?.enabled === 'boolean')
    return config.features.inventory.enabled;
  if (config?.schema === 1 && typeof config.inventoryEnabled === 'boolean')
    return config.inventoryEnabled;
  throw new TypeError('Unsupported config schema');
}
