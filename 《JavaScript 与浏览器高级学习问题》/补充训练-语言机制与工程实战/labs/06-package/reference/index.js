export function createCache({ capacity = 2, ttl = 1000, now = Date.now } = {}) {
  if (
    !Number.isInteger(capacity) ||
    capacity < 1 ||
    !Number.isFinite(ttl) ||
    ttl <= 0 ||
    typeof now !== 'function'
  )
    throw new TypeError('Invalid cache options');
  const entries = new Map();
  const prune = () => {
    const time = now();
    for (const [k, e] of entries) if (e.expires <= time) entries.delete(k);
  };
  return {
    set(key, value) {
      prune();
      entries.delete(key);
      entries.set(key, { value, expires: now() + ttl });
      while (entries.size > capacity) entries.delete(entries.keys().next().value);
    },
    get(key) {
      const e = entries.get(key);
      if (!e) return { hit: false };
      if (e.expires <= now()) {
        entries.delete(key);
        return { hit: false };
      }
      entries.delete(key);
      entries.set(key, e);
      return { hit: true, value: e.value };
    },
    delete(key) {
      return entries.delete(key);
    },
    get size() {
      prune();
      return entries.size;
    }
  };
}
