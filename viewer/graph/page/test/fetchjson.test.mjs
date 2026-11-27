/* data.js fetchJson with a timeout (Zephyr's read of PR 117): a server that accepts the request and never answers, or whose body never ends, ends as fetch-failed after the
   limit; without a limit nothing changes. Made-up addresses; the limits are a few milliseconds here. */
import test from "node:test";
import assert from "node:assert/strict";
import { DataError, fetchJson } from "../data.js";
import { SIDECAR_TIMEOUT_MS } from "../graphview.js";

const never = () => new Promise(() => {});
const ok = (v) => () => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(v) });
const code = async (p) => { try { await p; return "no error"; } catch (e) { assert.ok(e instanceof DataError, String(e)); return e.code; } };

test("T1 a request that never answers ends as fetch-failed after the limit, and takes about that long", async () => {
  const t0 = Date.now();
  assert.equal(await code(fetchJson(never, "made-up.json", 40)), "fetch-failed");
  const took = Date.now() - t0;
  assert.ok(took >= 30 && took < 1000, "took " + took + " ms");
});

test("T2 a body that never ends is fetch-failed too, not not-json", async () => {
  const stalled = () => Promise.resolve({ ok: true, status: 200, json: never });
  assert.equal(await code(fetchJson(stalled, "made-up.json", 40)), "fetch-failed");
});

test("T3 an answer in time is returned as before, and the timer is cleared: no rejection comes later", async () => {
  let unhandled = 0;
  const on = () => { unhandled += 1; };
  process.on("unhandledRejection", on);
  assert.deepEqual(await fetchJson(ok({ a: 1 }), "made-up.json", 30), { a: 1 });
  await new Promise((r) => setTimeout(r, 90));
  process.off("unhandledRejection", on);
  assert.equal(unhandled, 0);
});

test("T4 the other failures keep their codes under a limit: a refused answer, a body that is not JSON, a request that throws", async () => {
  assert.equal(await code(fetchJson(() => Promise.resolve({ ok: false, status: 404 }), "x", 50)), "http-404");
  assert.equal(await code(fetchJson(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.reject(new Error("bad")) }), "x", 50)), "not-json");
  assert.equal(await code(fetchJson(() => Promise.reject(new Error("down")), "x", 50)), "fetch-failed");
});

test("T5 with no limit given the call is as it was: it waits for a slow answer", async () => {
  const slow = () => new Promise((resolve) => setTimeout(() => resolve({ ok: true, status: 200, json: () => Promise.resolve(7) }), 60));
  assert.equal(await fetchJson(slow, "x"), 7);
});

test("T6 the page's contract: a sidecar is waited for 20 seconds", () => {
  assert.equal(SIDECAR_TIMEOUT_MS, 20000);
});

test("T7 the timer a call sets is cleared when the call ends, by an answer or by a failure (no timer is left pending)", async () => {
  const real = { set: globalThis.setTimeout, clear: globalThis.clearTimeout };
  const live = new Set();
  globalThis.setTimeout = (f, ms) => { const h = real.set(f, ms); live.add(h); return h; };
  globalThis.clearTimeout = (h) => { live.delete(h); return real.clear(h); };
  try {
    await fetchJson(ok({ a: 1 }), "made-up.json", 5000);
    assert.equal(live.size, 0, "a timer is left after an answer");
    await code(fetchJson(() => Promise.resolve({ ok: false, status: 500 }), "made-up.json", 5000));
    assert.equal(live.size, 0, "a timer is left after a refused answer");
    await code(fetchJson(never, "made-up.json", 20));
    await new Promise((r) => real.set(r, 40));
  } finally {
    globalThis.setTimeout = real.set; globalThis.clearTimeout = real.clear;
  }
});
