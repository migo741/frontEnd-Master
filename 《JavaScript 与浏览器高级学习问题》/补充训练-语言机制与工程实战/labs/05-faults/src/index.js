// 故意保留的可运行故障。先按题目复现，再调查原因。
export function createSearch({ fetchRows, render, onError = () => {} }) {
  return {
    async search(query) {
      try {
        const rows = await fetchRows(query);
        render(rows);
      } catch (e) {
        onError(e);
      }
    },
    dispose() {}
  };
}
export function mountPanel({ root, events }) {
  const panel = root.ownerDocument.createElement('article');
  panel.textContent = '详情面板 ' + 'x'.repeat(50000);
  root.append(panel);
  const update = () => {
    panel.dataset.updated = 'yes';
  };
  events.addEventListener('tick', update);
  return () => panel.remove();
}
export function resizeRows(rows, width) {
  let height = 0;
  for (const row of rows) {
    row.style.width = `${width}px`;
    height += row.getBoundingClientRect().height;
  }
  return height;
}

export function readFeature(config) {
  return config.features.inventory.enabled;
}
