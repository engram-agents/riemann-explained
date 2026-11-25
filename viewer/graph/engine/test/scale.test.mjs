// SCALE: the claim tested, not asserted. A generated tree of 100,000 nodes at fan-out 40, children served by an
// async loader that counts its calls. After EVERY step of a scripted walk:
//   held <= visible + the cache bound (maxHeld * maxChildren),  drawn <= visible,
//   the loader was called only for nodes that were opened (never for the whole tree).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createController } from "../controller.js";
import { recordingView, generated } from "./helpers.mjs";

const MAX_HELD = 4, FAN = 40;

test("100,000-node tree at fan-out 40: held and drawn stay bounded by what is visible", async () => {
  const g = generated({ fanout: FAN, total: 100000 });
  assert.equal(g.total, 100000);
  const view = recordingView();
  const ctl = createController({ roots: g.roots, loadChildren: g.loader, maxHeld: MAX_HELD, maxChildren: FAN, fitOnStart: false }, view);
  await ctl.ready;
  const opened = new Set();                 // every id this script asked to open (or reveal through)
  const stat = { steps: 0, maxHeld: 0, maxDrawn: 0, maxVisible: 0, maxCached: 0 };
  const bound = MAX_HELD * FAN;
  function check(label) {
    const s = ctl.stats();
    stat.steps++; stat.maxHeld = Math.max(stat.maxHeld, s.held); stat.maxDrawn = Math.max(stat.maxDrawn, view.mounted.size);
    stat.maxVisible = Math.max(stat.maxVisible, s.visible); stat.maxCached = Math.max(stat.maxCached, s.cached);
    assert.ok(s.held <= s.visible + bound, label + ": held " + s.held + " > visible " + s.visible + " + bound " + bound);
    assert.ok(s.cached <= MAX_HELD, label + ": cache entries " + s.cached + " > maxHeld");
    assert.ok(view.mounted.size <= s.visible, label + ": drawn " + view.mounted.size + " > visible " + s.visible);
    assert.equal(s.visible, ctl.visibleNodes().length, label + ": stats.visible is the tree walk");
    for (const id of g.calls) assert.ok(opened.has(id), label + ": loader called for " + id + " which was never opened");
    assert.ok(g.calls.length < 100, label + ": loader called " + g.calls.length + " times, far from the tree's 2,500 internal nodes");
  }
  const open = async (id) => { opened.add(id); assert.equal(await ctl.open(id), true, "open " + id); };

  check("start");
  // open a path 4 deep
  const deep = ["n0", "n1", "n" + g.child(1, 0), "n" + g.child(g.child(1, 0), 0)];
  for (const id of deep) { await open(id); check("path " + id); }
  // open siblings of the deepest
  const parentOfDeepest = g.child(1, 0);
  const sibs = [1, 2, 3, 4, 5, 6].map((j) => "n" + g.child(parentOfDeepest, j));
  for (const id of sibs) { await open(id); check("sibling " + id); }
  // close them (cache fills past maxHeld and evicts)
  for (const id of [...sibs, deep[3]]) { assert.equal(ctl.close(id), true); check("close " + id); }
  assert.equal(ctl.stats().cached, MAX_HELD, "the cache is full and bounded");
  // reopening the most recently closed one comes from the cache: no loader call
  const before = g.calls.length;
  await open(deep[3]); check("reopen from cache");
  assert.equal(g.calls.length, before, "a cached subtree reopens without the loader");
  // reopening the oldest closed one was evicted: it asks the loader again
  await open(sibs[0]); check("reopen evicted");
  assert.equal(g.calls.length, before + 1);
  // reveal a deep node: opens its ancestors in order, loading as needed
  const target = 99999, tpath = g.pathOf(target);
  assert.ok(tpath.length >= 5, "target is 5 deep: " + tpath.join(">"));
  tpath.slice(0, -1).forEach((id) => opened.add(id));
  assert.equal(await ctl.reveal(tpath), true);
  check("reveal");
  assert.ok(ctl.node("n" + target), "the revealed node is visible");
  // close all
  assert.equal(ctl.close("n0"), true); check("close all");
  assert.equal(ctl.stats().visible, 1);
  assert.equal(view.mounted.size, 1);
  console.log("SCALE: nodes=" + g.total + " fanout=" + FAN + " steps=" + stat.steps + " maxHeld=" + stat.maxHeld + " (bound at its peak visible " + stat.maxVisible + " + " + bound + ")"
    + " maxDrawn=" + stat.maxDrawn + " maxVisible=" + stat.maxVisible + " maxCached=" + stat.maxCached + " loaderCalls=" + g.calls.length + " opened=" + opened.size);
});

test("a node that is closed while its children are loading is not drawn when they arrive", async () => {
  const g = generated({ fanout: FAN, total: 100000 }), view = recordingView();
  let release;
  const gate = new Promise((r) => { release = r; });
  const ctl = createController({ roots: g.roots, loadChildren: async (id) => { await gate; return g.loader(id); }, maxHeld: 4, fitOnStart: false }, view);
  await ctl.ready;
  const p = ctl.open("n0");
  assert.equal(ctl.close("n0"), false, "a closed node has nothing to close; this cancels the pending load");
  release();
  assert.equal(await p, false);
  assert.equal(view.mounted.size, 1);
  assert.equal(ctl.stats().visible, 1);
});
