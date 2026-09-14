import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
const root = fileURLToPath(new URL('../', import.meta.url));
const args = process.argv.slice(2);
const reference = args.includes('--reference');
const chapter = args.find((x) => !x.startsWith('--'));
if (chapter && !/^0[1-6]$/.test(chapter)) throw new Error('单元号应为 01–06');
const files = ['01-semantics', '02-events', '03-autosave', '04-streams', '05-faults', '06-package']
  .filter((x) => !chapter || x.startsWith(chapter))
  .map((x) => `tests/${x}.test.mjs`);
console.log(
  reference
    ? '验证参考答案。不要把这次通过计入自己的学习进度。'
    : '验证学生实现。初始失败是预期，请按 README 完成对应任务。'
);
const result = spawnSync(process.execPath, ['--test', '--test-timeout=10000', ...files], {
  cwd: root,
  stdio: 'inherit',
  env: { ...process.env, LAB_MODE: reference ? 'reference' : 'src' }
});
process.exit(result.status ?? 1);
