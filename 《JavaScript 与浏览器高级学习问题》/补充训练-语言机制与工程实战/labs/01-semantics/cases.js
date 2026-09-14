// 先阅读预测。每个 run 独立执行，返回能被 JSON 表达的观察值。
export const cases = [
  {
    id: 'conversion',
    run() {
      const log = [];
      const x = {
        [Symbol.toPrimitive](hint) {
          log.push(hint);
          return hint === 'string' ? 'S' : 7;
        },
        valueOf() {
          log.push('valueOf');
          return 99;
        }
      };
      return [x + 1, String(x), log];
    }
  },
  {
    id: 'tdz',
    run() {
      let x = 8;
      let kind;
      {
        try {
          typeof x;
        } catch (e) {
          kind = e.name;
        }
        let x = 3;
      }
      return [kind, x];
    }
  },
  {
    id: 'binding',
    run() {
      const x = {
        n: 2,
        method() {
          return this?.n ?? 'none';
        }
      };
      const f = x.method;
      const arrow = (function () {
        return () => this;
      })();
      return [x.method(), f(), f.call({ n: 9 }), arrow.call({ n: 5 }) === undefined];
    }
  },
  {
    id: 'bound-constructor',
    run() {
      function F(n) {
        this.n = n;
      }
      const other = { n: 0 };
      const B = F.bind(other, 4);
      const x = new B(9);
      return [x.n, other.n, x instanceof F, x instanceof B];
    }
  },
  {
    id: 'receiver',
    run() {
      const base = {
        get x() {
          return this.y;
        }
      };
      const p = new Proxy(base, {
        get(t, k, r) {
          return Reflect.get(t, k, r);
        }
      });
      const child = Object.create(p);
      child.y = 6;
      return child.x;
    }
  },
  {
    id: 'invariant',
    run() {
      const target = Object.freeze({ x: 1 });
      const p = new Proxy(target, {
        get() {
          return 2;
        }
      });
      try {
        return p.x;
      } catch (e) {
        return e.name;
      }
    }
  },
  {
    id: 'thenable',
    async run() {
      const log = [];
      const x = {
        get then() {
          log.push('get');
          return (resolve) => {
            log.push('call');
            resolve(3);
            resolve(4);
          };
        }
      };
      const p = Promise.resolve(x);
      log.push('sync');
      const value = await p;
      log.push('await');
      return [value, log];
    }
  },
  {
    id: 'iterator-close',
    run() {
      const log = [];
      function* values() {
        try {
          yield 1;
          yield 2;
        } finally {
          log.push('close');
        }
      }
      for (const x of values()) {
        log.push(x);
        break;
      }
      return log;
    }
  },
  {
    id: 'sparse',
    run() {
      const a = [, undefined];
      let calls = 0;
      a.map(() => calls++);
      return [calls, 0 in a, 1 in a, JSON.stringify(a), 0 in [...a]];
    }
  },
  {
    id: 'home-object',
    run() {
      const parent = { x: 1 };
      const a = {
        __proto__: parent,
        getX() {
          return super.x;
        }
      };
      const b = { __proto__: { x: 9 }, getX: a.getX };
      return b.getX();
    }
  },
  {
    id: 'function-prototype',
    run() {
      function F() {}
      const proto = function Proto() {};
      F.prototype = proto;
      return [Object.getPrototypeOf(new F()) === proto, typeof proto];
    }
  },
  {
    id: 'then-getter-error',
    async run() {
      const x = {
        get then() {
          throw new Error('getter');
        }
      };
      const log = [];
      let p;
      try {
        p = Promise.resolve(x);
        log.push('returned');
      } catch {
        log.push('sync-throw');
      }
      try {
        await p;
      } catch (e) {
        log.push(e.message);
      }
      return log;
    }
  }
];
