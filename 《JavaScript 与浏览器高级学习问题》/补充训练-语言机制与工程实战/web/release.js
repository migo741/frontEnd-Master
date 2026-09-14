import { mode, $ } from './common.js';
const logs = [];
addEventListener('message', (event) => {
  if (
    event.origin !== location.origin ||
    event.source !== $('frame').contentWindow ||
    event.data?.type !== 'lab-release-log'
  )
    return;
  logs.push(event.data);
  $('logs').textContent = JSON.stringify(logs, null, 2);
});
const start = (path) => {
  logs.length = 0;
  $('logs').textContent = '';
  $('frame').src = path + '?mode=' + mode;
};
$('old').onclick = () => start('/release/old/register.html');
$('fresh').onclick = () => start('/release/fresh/index.html');
$('cleanup').onclick = async () => {
  $('frame').src = 'about:blank';
  const scope = new URL('/release/old/', location.href).href;
  for (const registration of await navigator.serviceWorker.getRegistrations())
    if (registration.scope === scope) await registration.unregister();
  await caches.delete('js-lab-legacy-v1');
  $('status').textContent = '本实验历史会话已清理';
};
