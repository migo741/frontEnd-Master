import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, cp, mkdir, writeFile, rm, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { load, mode } from './helpers.mjs';
const { createCache } = await load('06-package');
test('06 / 容量、LRU与对象键', () => {
  const c = createCache({ capacity: 2 }),
    key = {};
  c.set(key, 1);
  c.set('b', 2);
  assert.deepEqual(c.get(key), { hit: true, value: 1 });
  c.set('c', 3);
  assert.deepEqual(c.get('b'), { hit: false });
  assert.equal(c.size, 2);
});
test('06 / TTL边界与undefined缓存', () => {
  let clock = 0;
  const c = createCache({ ttl: 10, now: () => clock });
  c.set('x', undefined);
  clock = 9;
  assert.deepEqual(c.get('x'), { hit: true, value: undefined });
  clock = 10;
  assert.deepEqual(c.get('x'), { hit: false });
  assert.equal(c.size, 0);
});
test('06 / 覆盖重置TTL且实例隔离', () => {
  let clock = 0;
  const a = createCache({ ttl: 10, now: () => clock }),
    b = createCache();
  a.set('x', 1);
  clock = 9;
  a.set('x', 2);
  clock = 10;
  assert.equal(a.get('x').value, 2);
  assert.equal(b.size, 0);
  assert.equal(a.delete('x'), true);
  assert.equal(a.delete('x'), false);
});
test('06 / 非法配置', () => {
  assert.throws(() => createCache({ capacity: 0 }), TypeError);
  assert.throws(() => createCache({ ttl: Infinity }), TypeError);
});
test('06 / npm真实打包后由独立consumer导入，私有路径不能穿透', async () => {
  const temp = await mkdtemp(join(tmpdir(), 'js-lab-package-'));
  const source = fileURLToPath(new URL(`../labs/06-package/${mode}`, import.meta.url));
  try {
    const packed = spawnSync(
      'npm',
      ['pack', '--json', '--ignore-scripts', '--pack-destination', temp],
      {
        cwd: source,
        encoding: 'utf8',
        env: { ...process.env, npm_config_cache: join(temp, 'npm-cache') }
      }
    );
    assert.equal(packed.status, 0, packed.stderr);
    const metadata = JSON.parse(packed.stdout)[0];
    assert.ok(metadata.files.some((f) => f.path === 'index.js'));
    const pkg = join(temp, 'node_modules/@js-lab/tiny-cache');
    await mkdir(pkg, { recursive: true });
    const unpack = spawnSync(
      'tar',
      ['-xzf', join(temp, metadata.filename), '-C', pkg, '--strip-components=1'],
      { encoding: 'utf8' }
    );
    assert.equal(unpack.status, 0, unpack.stderr);
    await writeFile(
      join(temp, 'consumer.mjs'),
      `
      import assert from 'node:assert/strict';
      const before=Reflect.ownKeys(globalThis);
      const {createCache}=await import('@js-lab/tiny-cache');
      assert.deepEqual(Reflect.ownKeys(globalThis),before);
      const cache=createCache();cache.set('x',3);assert.equal(cache.get('x').value,3);
      await assert.rejects(import('@js-lab/tiny-cache/index.js'),e=>e.code==='ERR_PACKAGE_PATH_NOT_EXPORTED');
    `
    );
    const consumer = spawnSync(process.execPath, ['consumer.mjs'], { cwd: temp, encoding: 'utf8' });
    assert.equal(consumer.status, 0, consumer.stderr);
  } finally {
    await rm(temp, { recursive: true, force: true });
  }
});
