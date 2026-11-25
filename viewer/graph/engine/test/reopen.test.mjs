// Round 2 contracts, written before the code:
//  F1 a child list served from the cache on reopen is validated again, against the CURRENT held set, like a fresh one;
//  F2 an open issued after a cancelled load starts a FRESH load; the cancelled answer is discarded whenever it arrives;
//  F3 a loader answer whose length differs from the node's childCount is refused whole (invalid-spec, both numbers named).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createController } from "../controller.js";
import { recordingView } from "./helpers.mjs";

const spec = (id, over = {}) => ({ id, childCount: 0, links: [], parentLinksTo: false, path: [id], data: null, ...over });
const kid = (parent, id) => spec(id, { path: [parent, id] });
function collect(ctl) {
  const log = [];
  for (const t of ["refused", "error", "open", "close", "loading"]) ctl.on(t, (...a) => log.push([t, ...a]));
  return log;
}
const deferred = () => { let resolve, reject; const promise = new Promise((a, b) => { resolve = a; reject = b; }); return { promise, resolve, reject }; };
const tick = () => new Promise((r) => setTimeout(r, 0));

test("F1: a duplicate id served from the cache on reopen is refused like a fresh one (exact order from the review)", async () => {
  const view = recordingView(), calls = [];
  const ctl = createController({
    roots: [spec("a", { childCount: 1 }), spec("b", { childCount: 1 })],
    loadChildren: async (id) => { calls.push(id); return [kid(id, "x")]; },
    fitOnStart: false,
  }, view);
  const log = collect(ctl); await ctl.ready;
  assert.equal(await ctl.open("a"), true);
  assert.equal(ctl.close("a"), true);                 // a's list goes to the cache
  assert.equal(await ctl.open("b"), true);            // accepted: x is not held now
  const heldBefore = ctl.stats().held, mountsBefore = view.mountCalls, cachedBefore = ctl.stats().cached;
  assert.equal(cachedBefore, 1, "a's list is in the cache");
  assert.equal(await ctl.open("a"), false, "served from the cache, validated, refused");
  assert.deepEqual(log.filter((e) => e[0] === "refused").map((e) => [e[1].id, e[2]]), [["a", "duplicate-id"]]);
  assert.equal(view.mountCalls, mountsBefore, "nothing of the refused list was drawn");
  const xs = ctl.visibleNodes().filter((n) => n.id === "x");
  assert.equal(xs.length, 1, "exactly one visible x");
  assert.equal(xs[0].parent.id, "b", "and it is b's");
  assert.equal(ctl.node("a").open, false);
  assert.equal(ctl.node("a").blocked, "duplicate-id", "the node says so (ge-refused) and is not asked again");
  assert.equal(ctl.stats().cached, cachedBefore - 1, "G3: the refused list is dropped from the cache, it holds no slot");
  assert.equal(ctl.stats().held, heldBefore - 1, "G3: the held count fell by exactly the dropped list (one node); nothing was added");
  assert.equal(ctl.stats().held, ctl.stats().visible + ctl.stats().cachedNodes, "held == visible + cached: the accounting is consistent");
  assert.equal(view.mounted.size, ctl.stats().visible, "what the view draws is what the controller says is visible");
  assert.equal(ctl.close("b"), true);
  assert.equal(ctl.node("x"), undefined, "closing b leaves no x in the map");
  assert.equal(view.mounted.has("x"), false, "and none on the page");
  assert.equal(view.mounted.size, ctl.stats().visible);
  // a refused node stays refused: the blocked flag is read before the cache, so the conflict being gone changes nothing
  const callsBefore = calls.length, mountsAfter = view.mountCalls, refusedBefore = log.filter((e) => e[0] === "refused").length;
  assert.equal(await ctl.open("a"), false, "a is opened again after the conflicting node closed: still refused");
  assert.equal(calls.length, callsBefore, "the loader was not called again");
  assert.equal(ctl.node("a").blocked, "duplicate-id", "a is still blocked, with the same reason");
  assert.equal(ctl.node("a").open, false);
  assert.equal(view.mountCalls, mountsAfter, "nothing new was drawn");
  assert.equal(view.mounted.size, ctl.stats().visible);
  assert.equal(log.filter((e) => e[0] === "refused").length, refusedBefore + 1, "the refusal is reported again (refused earlier), not silently dropped");
});

test("F1: a valid cached list still reopens from the cache without a second load", async () => {
  const view = recordingView(), calls = [];
  const ctl = createController({ roots: [spec("a", { childCount: 1 })], loadChildren: async (id) => { calls.push(id); return [kid(id, "x")]; }, fitOnStart: false }, view);
  await ctl.ready;
  await ctl.open("a"); ctl.close("a");
  assert.equal(await ctl.open("a"), true);
  assert.deepEqual(calls, ["a"], "the loader was called once; the second open came from the cache");
  assert.equal(view.mounted.has("x"), true);
});

test("F2: open, close, open before the first answer starts a fresh load; the cancelled answer is discarded (late after the second)", async () => {
  const view = recordingView(), loads = [];
  const ctl = createController({ roots: [spec("a", { childCount: 1 })], loadChildren: (id) => { const d = deferred(); loads.push(d); return d.promise; }, fitOnStart: false }, view);
  const log = collect(ctl); await ctl.ready;
  let r1 = "pending", r2 = "pending";
  const p1 = ctl.open("a").then((v) => (r1 = v));
  assert.equal(loads.length, 1);
  assert.equal(ctl.close("a"), false, "closing a node that is loading cancels the load (and returns false: nothing was open, as scale.test pins)");
  const p2 = ctl.open("a").then((v) => (r2 = v));
  assert.equal(loads.length, 2, "the second open called the loader again");
  loads[1].resolve([kid("a", "x")]); await p2;
  assert.equal(r2, true, "the second promise resolves true when ITS load lands");
  assert.equal(view.mounted.has("x"), true);
  const opens = log.filter((e) => e[0] === "open").length, mounts = view.mountCalls;
  loads[0].resolve([kid("a", "x")]); await p1;          // the cancelled answer, arriving late
  assert.equal(r1, false, "the cancelled first promise resolves false");
  assert.equal(view.mountCalls, mounts, "the late cancelled answer drew nothing");
  assert.equal(log.filter((e) => e[0] === "open").length, opens, "and opened nothing again");
  assert.equal(log.filter((e) => e[0] === "refused" || e[0] === "error").length, 0, "and was not read as a duplicate");
  assert.equal(view.mounted.size, 2);
});

test("F2: the cancelled answer arriving BEFORE the second answer is discarded too and does not resolve the second promise", async () => {
  const view = recordingView(), loads = [];
  const ctl = createController({ roots: [spec("a", { childCount: 1 })], loadChildren: () => { const d = deferred(); loads.push(d); return d.promise; }, fitOnStart: false }, view);
  await ctl.ready;
  let r1 = "pending", r2 = "pending";
  const p1 = ctl.open("a").then((v) => (r1 = v));
  ctl.close("a");
  const p2 = ctl.open("a").then((v) => (r2 = v));
  loads[0].resolve([kid("a", "x")]); await p1; await tick();
  assert.equal(r1, false);
  assert.equal(r2, "pending", "the cancelled answer did not resolve the second promise");
  assert.equal(view.mounted.has("x"), false, "and drew nothing");
  assert.equal(ctl.node("a").open, false);
  loads[1].resolve([kid("a", "x")]); await p2;
  assert.equal(r2, true);
  assert.equal(view.mounted.has("x"), true); assert.equal(ctl.node("a").open, true);
});

test("F2: a cancelled load that REJECTS late is silent, and the fresh load is unaffected", async () => {
  const view = recordingView(), loads = [];
  const ctl = createController({ roots: [spec("a", { childCount: 1 })], loadChildren: () => { const d = deferred(); loads.push(d); return d.promise; }, fitOnStart: false }, view);
  const log = collect(ctl); await ctl.ready;
  const p1 = ctl.open("a"); ctl.close("a"); const p2 = ctl.open("a");
  loads[0].reject(new Error("late boom")); assert.equal(await p1, false);
  loads[1].resolve([kid("a", "x")]); assert.equal(await p2, true);
  assert.equal(log.filter((e) => e[0] === "error").length, 0);
});

test("G1 (Halley's scenario): open, close, open, load 1 settles, close during load 2, load 2 settles: the node stays CLOSED and nothing is drawn", async () => {
  const view = recordingView(), loads = [];
  const ctl = createController({ roots: [spec("a", { childCount: 1 })], loadChildren: () => { const d = deferred(); loads.push(d); return d.promise; }, fitOnStart: false }, view);
  const log = collect(ctl); await ctl.ready;
  let r1 = "pending", r2 = "pending";
  const p1 = ctl.open("a").then((v) => (r1 = v));
  assert.equal(ctl.close("a"), false, "cancels load 1 (false: nothing was open)");
  const p2 = ctl.open("a").then((v) => (r2 = v));
  assert.equal(loads.length, 2);
  loads[0].resolve([kid("a", "x")]); await p1; await tick();       // load 1 settles: its finally must not touch load 2's promise
  assert.equal(r1, false); assert.equal(r2, "pending");
  const visibleBefore = ctl.visibleNodes().length, mounts = view.mountCalls;
  assert.equal(ctl.close("a"), false, "the close during load 2 cancels it (false: nothing was open)");
  assert.equal(ctl.node("a").pending, null, "and load 2 no longer counts as pending");
  loads[1].resolve([kid("a", "x")]); await p2;                     // load 2 settles after it was cancelled
  assert.equal(r2, false, "the second open's promise is false: its load was cancelled");
  assert.equal(ctl.node("a").open, false, "the node stays closed");
  assert.equal(view.mountCalls, mounts, "nothing was drawn");
  assert.equal(view.mounted.has("x"), false);
  assert.equal(ctl.visibleNodes().length, visibleBefore, "visible is unchanged");
  assert.equal(log.filter((e) => e[0] === "open").length, 0);
  assert.equal(loads.length, 2, "and no further load was started");
});

test("G1 (reviewer's variant): after load 1 settles, a third open does not start a third load while load 2 is pending; load 2 resolves both true", async () => {
  const view = recordingView(), loads = [];
  const ctl = createController({ roots: [spec("a", { childCount: 1 })], loadChildren: () => { const d = deferred(); loads.push(d); return d.promise; }, fitOnStart: false }, view);
  await ctl.ready;
  let r2 = "pending", r3 = "pending";
  const p1 = ctl.open("a");
  ctl.close("a");
  const p2 = ctl.open("a").then((v) => (r2 = v));
  loads[0].resolve([kid("a", "x")]); await p1; await tick();
  const p3 = ctl.open("a").then((v) => (r3 = v));
  assert.equal(loads.length, 2, "no third load while load 2 is pending");
  loads[1].resolve([kid("a", "x")]); await p2; await p3;
  assert.equal(r2, true, "the second open's promise resolves true when load 2 lands");
  assert.equal(r3, true);
  assert.equal(ctl.node("a").open, true);
  assert.equal(view.mounted.size, 2);
});

for (const [label, returned, detailRe] of [["too few", 2, /childCount 3.*returned 2/], ["too many", 5, /childCount 3.*returned 5/]]) {
  test("F3: a loader answer with " + label + " children for childCount 3 is refused whole: invalid-spec, both numbers named, nothing drawn", async () => {
    const view = recordingView();
    const list = Array.from({ length: returned }, (_, i) => kid("p", "k" + i));
    const ctl = createController({ roots: [spec("p", { childCount: 3 })], loadChildren: async () => list, fitOnStart: false }, view);
    const log = collect(ctl); await ctl.ready;
    assert.equal(await ctl.open("p"), false);
    const refused = log.filter((e) => e[0] === "refused");
    assert.equal(refused.length, 1); assert.equal(refused[0][1].id, "p"); assert.equal(refused[0][2], "invalid-spec");
    assert.match(refused[0][3], detailRe, "the detail names both numbers");
    assert.equal(view.mounted.size, 1, "nothing of the batch was drawn");
    assert.equal(ctl.node("p").open, false); assert.equal(ctl.node("p").blocked, "invalid-spec");
  });
}

test("F3: a count that matches is accepted", async () => {
  const view = recordingView();
  const ctl = createController({ roots: [spec("p", { childCount: 2 })], loadChildren: async () => [kid("p", "k0"), kid("p", "k1")], fitOnStart: false }, view);
  await ctl.ready;
  assert.equal(await ctl.open("p"), true);
});

test("F5: reveal resolves to a boolean as INTERFACE.md says: true when framed, false (with its event) otherwise", async () => {
  const view = recordingView();
  const ctl = createController({ roots: [spec("p", { childCount: 1 })], loadChildren: async () => [kid("p", "k")], fitOnStart: false }, view);
  const log = collect(ctl); await ctl.ready;
  assert.equal(await ctl.reveal(["p", "k"]), true);
  assert.equal(await ctl.reveal(["p", "zz"]), false, "an unknown last step");
  assert.equal(await ctl.reveal(["zz", "k"]), false, "an unknown ancestor step");
  assert.equal(await ctl.reveal(["p", "k", "x"]), false, "an ancestor (a leaf) that does not open");
  assert.equal(await ctl.reveal(["Bad Id"]), false);
  assert.deepEqual(log.filter((e) => e[0] === "refused").map((e) => e[2]), ["invalid-path"]);
  assert.deepEqual(log.filter((e) => e[0] === "error").map((e) => e[2]), ["path-not-found", "path-not-found"]);
  ctl.destroy();
  assert.equal(await ctl.reveal(["p"]), false);
});
