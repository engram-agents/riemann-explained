// Refusals are events, never throws: fan-out over maxChildren, an invalid id or path in a NodeSpec,
// a loader that fails. Nothing of a refused spec reaches the view.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createController } from "../controller.js";
import { recordingView, tiny, generated } from "./helpers.mjs";

function collect(ctl) {
  const log = [];
  for (const t of ["refused", "error", "open", "close", "loading", "tap"]) ctl.on(t, (...a) => log.push([t, ...a]));
  return log;
}
const spec = (id, over = {}) => ({ id, childCount: 0, links: [], parentLinksTo: false, path: [id], data: null, ...over });

test("fan-out over maxChildren: refused event, nothing drawn for that node's children, no throw, loader not called", async () => {
  const calls = [];
  const view = recordingView();
  const ctl = createController({ roots: [spec("big", { childCount: 41 })], loadChildren: async (id) => { calls.push(id); return []; }, maxChildren: 40, fitOnStart: false }, view);
  const log = collect(ctl); await ctl.ready;
  assert.equal(await ctl.open("big"), false);
  const refused = log.filter((e) => e[0] === "refused");
  assert.equal(refused.length, 1);
  assert.equal(refused[0][1].id, "big"); assert.equal(refused[0][2], "fan-out");
  assert.deepEqual(calls, []); assert.equal(view.mounted.size, 1);
});

test("a loader that returns more than maxChildren is refused too, and nothing of the batch is drawn", async () => {
  const view = recordingView();
  const many = Array.from({ length: 41 }, (_, i) => spec("k" + i, { path: ["p", "k" + i] }));
  const ctl = createController({ roots: [spec("p", { childCount: 5 })], loadChildren: async () => many, maxChildren: 40, fitOnStart: false }, view);
  const log = collect(ctl); await ctl.ready;
  assert.equal(await ctl.open("p"), false);
  assert.deepEqual(log.filter((e) => e[0] === "refused").map((e) => [e[1].id, e[2]]), [["p", "fan-out"]]);
  assert.equal(view.mounted.size, 1);
});

test("roots over maxChildren: refused with a null node, nothing drawn", async () => {
  const view = recordingView();
  const roots = Array.from({ length: 3 }, (_, i) => spec("r" + i));
  const ctl = createController({ roots, loadChildren: async () => [], maxChildren: 2, fitOnStart: false }, view);
  const log = collect(ctl); await ctl.ready;
  assert.deepEqual(log.filter((e) => e[0] === "refused").map((e) => [e[1], e[2]]), [[null, "fan-out"]]);
  assert.equal(view.mounted.size, 0);
});

const BAD_IDS = ["", "Bad", "UPPER", "-x", ".x", "a b", "a/b", "<img src=x onerror=alert(1)>", '" onmouseover="x', "javascript:alert(1)", "a b", "x".repeat(10) + "\n", 7, null, undefined, {}, ["a"]];
for (const bad of BAD_IDS) {
  test("an invalid root id is refused and nothing is drawn: " + JSON.stringify(bad)?.slice(0, 40), async () => {
    const view = recordingView();
    const ctl = createController({ roots: [spec("ok"), { ...spec("ok2"), id: bad, path: ["ok2"] }], loadChildren: async () => [], fitOnStart: false }, view);
    const log = collect(ctl); await ctl.ready;
    const r = log.filter((e) => e[0] === "refused");
    assert.equal(r.length, 1); assert.equal(r[0][1], null); assert.equal(r[0][2], "invalid-id");
    assert.equal(view.mounted.size, 0, "the valid sibling is not drawn either: the batch is refused whole");
    assert.equal(view.mountCalls, 0);
  });
}

test("an invalid id, path, toPath or link target inside loaded children is refused; the parent stays closed", async () => {
  const cases = {
    "invalid-id": (k) => ({ ...k, id: "Bad Id" }),
    "invalid-path": (k) => ({ ...k, path: ["p", "<b>"] }),
    "invalid-path ": (k) => ({ ...k, links: [{ to: "x", toPath: ["x", "Y!"] }] }),
    "invalid-id ": (k) => ({ ...k, links: [{ to: "x y", toPath: ["x"] }] }),
    "invalid-spec": (k) => ({ ...k, childCount: -1 }),
    "invalid-spec ": (k) => ({ ...k, childCount: 1.5 }),
    "invalid-spec  ": (k) => ({ ...k, links: "nope" }),
    "invalid-spec   ": (k) => ({ ...k, parentLinksTo: "yes" }),
    "invalid-path  ": (k) => ({ ...k, path: ["other", "k"] }),   // a path that does not run through the parent
  };
  for (const [reason, mut] of Object.entries(cases)) {
    const view = recordingView();
    const ctl = createController({ roots: [spec("p", { childCount: 1 })], loadChildren: async () => [mut(spec("k", { path: ["p", "k"] }))], fitOnStart: false }, view);
    const log = collect(ctl); await ctl.ready;
    assert.equal(await ctl.open("p"), false);
    assert.deepEqual(log.filter((e) => e[0] === "refused").map((e) => [e[1].id, e[2]]), [["p", reason.trim()]], reason);
    assert.equal(view.mounted.size, 1, reason + ": nothing of the child reached the view");
  }
});

test("a duplicate id is refused", async () => {
  const view = recordingView();
  const ctl = createController({ roots: [spec("p", { childCount: 2 })], loadChildren: async () => [spec("k", { path: ["p", "k"] }), spec("k", { path: ["p", "k"] })], fitOnStart: false }, view);
  const log = collect(ctl); await ctl.ready;
  await ctl.open("p");
  assert.deepEqual(log.filter((e) => e[0] === "refused").map((e) => e[2]), ["duplicate-id"]);
  assert.equal(view.mounted.size, 1);
});

test("a loader that throws or returns a non-array is an error event, not a throw; the node can be tried again", async () => {
  const view = recordingView(); let mode = "throw";
  const ctl = createController({ roots: [spec("p", { childCount: 1 })], loadChildren: async () => { if (mode === "throw") throw new Error("boom"); if (mode === "bad") return { not: "array" }; return [spec("k", { path: ["p", "k"] })]; }, fitOnStart: false }, view);
  const log = collect(ctl); await ctl.ready;
  assert.equal(await ctl.open("p"), false); mode = "bad";
  assert.equal(await ctl.open("p"), false); mode = "ok";
  assert.deepEqual(log.filter((e) => e[0] === "error").map((e) => [e[1].id, e[2]]), [["p", "load-failed"], ["p", "bad-result"]]);
  assert.equal(await ctl.open("p"), true);
  assert.equal(view.mounted.size, 2);
});

test("events: loading, open, visible, close in order; a listener that throws is reported to onListenerError and does not break the engine", async () => {
  const t = tiny([{ id: "a", kids: ["a1"] }, { id: "a1" }]), view = recordingView(), faults = [];
  const ctl = createController({ roots: t.roots, loadChildren: t.loader, fitOnStart: false, onListenerError: (err, type) => faults.push([err.message, type]) }, view);
  const seen = [];
  ctl.on("loading", (n) => seen.push("loading:" + n.id)); ctl.on("open", (n) => seen.push("open:" + n.id)); ctl.on("close", (n) => seen.push("close:" + n.id));
  ctl.on("visible", (ns) => seen.push("visible:" + ns.map((n) => n.id).join(",")));
  ctl.on("open", () => { throw new Error("listener fault"); });
  await ctl.ready;
  await ctl.open("a"); ctl.close("a");
  const pick = (re) => seen.filter((s) => re.test(s));
  assert.deepEqual(pick(/^(loading|open|close):/), ["loading:a", "open:a", "close:a"]);
  assert.ok(seen.includes("visible:a,a1") && seen.filter((s) => s.startsWith("visible:")).pop() === "visible:a");
  assert.deepEqual(faults, [["listener fault", "open"]]);
  assert.equal(view.mounted.size, 1, "the engine went on after the fault");
  assert.throws(() => ctl.on("nonsense", () => {}), /unknown event/);
  const off = ctl.on("tap", () => {}); assert.equal(typeof off, "function"); off();
});

test("two controllers are independent: a camera move in one is invisible to the other", async () => {
  const g = generated({ fanout: 40, total: 100000 });
  const v1 = recordingView(), v2 = recordingView({ w: 800, h: 600 });
  const c1 = createController({ roots: g.roots, loadChildren: g.loader, fitOnStart: true }, v1);
  const c2 = createController({ roots: g.roots, loadChildren: g.loader, fitOnStart: true }, v2);
  await Promise.all([c1.ready, c2.ready]);
  const k2 = c2.camera().k, t2 = [c2.camera().tx, c2.camera().ty];
  c1.zoomAt(100, 100, 1.5, false); c1.panBy(30, 40);
  assert.deepEqual([c2.camera().k, c2.camera().tx, c2.camera().ty], [k2, ...t2], "the second engine's camera did not move");
  await c1.open("n0");
  assert.equal(c2.stats().visible, 1);
  assert.notEqual(c1.camera().k, k2);
});
