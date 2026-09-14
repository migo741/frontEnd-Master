export const mode = process.env.LAB_MODE === 'reference' ? 'reference' : 'src';
export const load = (name) => import(new URL(`../labs/${name}/${mode}/index.js`, import.meta.url));
export const deferred = () => {
  let resolve, reject;
  const promise = new Promise((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
};
export async function ticks(n = 12) {
  for (let i = 0; i < n; i++) await Promise.resolve();
}
