export const mode =
  new URL(location.href).searchParams.get('mode') === 'reference' ? 'reference' : 'src';
document.querySelector('#mode').textContent = mode === 'reference' ? '参考模式' : '学生模式';
export const $ = (id) => document.getElementById(id);
export function failure(error) {
  $('status').textContent = String(error?.message ?? error);
  $('status').classList.add('warning');
}
