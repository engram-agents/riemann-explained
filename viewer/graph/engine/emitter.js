// A small event emitter. One per graph; no state outside the closure.

export const EVENTS = Object.freeze(["tap", "open", "close", "visible", "loading", "error", "refused"]);

/* A listener that throws never breaks the engine: the fault goes to `onFault(error, type)`, or, by default, is
   rethrown from a fresh call (so it reaches the page's error reporting) while the engine carries on. */
export function createEmitter(names, onFault) {
  const subs = new Map(names.map((n) => [n, new Set()]));
  const fault = onFault || ((e) => { setTimeout(() => { throw e; }, 0); });
  const known = (type) => { if (!subs.has(type)) throw new Error("unknown event " + type); return subs.get(type); };
  return {
    on(type, fn) {
      const set = known(type);
      if (typeof fn !== "function") throw new TypeError("a listener must be a function");
      set.add(fn);
      return () => { set.delete(fn); };
    },
    off(type, fn) { known(type).delete(fn); },
    emit(type, ...args) {
      for (const fn of [...known(type)]) { try { fn(...args); } catch (e) { fault(e, type); } }
    },
    clear() { for (const s of subs.values()) s.clear(); },
  };
}
