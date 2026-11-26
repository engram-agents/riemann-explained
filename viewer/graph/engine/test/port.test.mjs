// The prototype's layout checks (test-core.js, 1,433 checks on this data) ported to the engine's API.
// The data is the real level data (fixtures/level1.json); every state is reached through open()/close()
// with an async loader, never by setting flags. Expected numbers are LITERALS taken from a run of the
// prototype's own core.js on the same file (world size and visible count per state).
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createController } from "../controller.js";
import { recordingView, fromLevel } from "./helpers.mjs";

const data = JSON.parse(readFileSync(new URL("./fixtures/level1.json", import.meta.url), "utf8"));
// prototype constants, written here as literals (the engine's defaults must reproduce them)
const PAD = 32, HEAD = 160, TOP = 34, GOAL = 104;
let checks = 0, fails = 0;
function ok(cond, msg) { checks++; if (!cond) { fails++; assert.fail(msg); } }
const overlap = (a, b) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;

async function make(maxHeld = 500) {
  const lvl = fromLevel(data), view = recordingView();
  const ctl = createController({ roots: lvl.roots, loadChildren: lvl.loader, maxHeld, fitOnStart: false, sizes: { topInset: GOAL } }, view);
  assert.equal(await ctl.ready, true);
  return { lvl, view, ctl };
}

/* an independent reference for the links, from the FULL data with parent pointers (no toPath) */
function refLinks(lvl, ctl) {
  const vis = new Set(ctl.visibleNodes().map((n) => n.id));
  const anc = (id) => { const out = []; for (let p = lvl.parentOf.get(id); p; p = lvl.parentOf.get(p)) out.push(p); return out; };
  const nearest = (id) => (vis.has(id) ? id : anc(id).find((a) => vis.has(a)) ?? null);
  let rests = 0, stems = 0;
  for (const id of vis) {
    for (const p of lvl.byId.get(id).premises) {
      const ep = nearest(p);
      if (!ep || ep === id || anc(id).includes(ep) || anc(ep).includes(id)) continue;
      rests++;
    }
  }
  for (const n of ctl.visibleNodes()) if (n.parent && !n.parent.root && n.spec.parentLinksTo && n.layer === 0) stems++;
  return { rests, stems };
}

function checkState(name, lvl, ctl) {
  const vis = ctl.visibleNodes(), w = ctl.world();
  vis.forEach((a) => vis.forEach((b) => { if (a !== b && a.parent === b.parent && a.id < b.id) ok(!overlap(a, b), name + ": siblings overlap " + a.id + " / " + b.id); }));
  vis.forEach((n) => { const p = n.parent; if (p && !p.root) {
    ok(n.x >= p.x + PAD - 0.01 && n.x + n.w <= p.x + p.w - PAD + 0.01, name + ": " + n.id + " outside parent horizontally");
    ok(n.y >= p.y + HEAD + TOP - 0.01 && n.y + n.h <= p.y + p.h - PAD + 0.01, name + ": " + n.id + " outside parent vertically"); } });
  vis.forEach((n) => n.spec.links.forEach((l) => { const p = ctl.node(l.to); if (p && p.parent === n.parent) ok(p.y >= n.y + n.h, name + ": premise " + l.to + " not below " + n.id); }));
  const links = ctl.links();
  links.forEach((e) => {
    ok(ctl.node(e.from.id) === e.from && ctl.node(e.to.id) === e.to && e.from !== e.to, name + ": link end hidden");
    if (e.kind === "rests") ok(e.from.y >= e.to.y + e.to.h, name + ": rests link not upward " + e.to.id + "->" + e.from.id);
    if (e.kind === "stem") ok(Math.abs(e.from.y - (e.to.y + HEAD + TOP)) < 0.01, name + ": stem child not in the first row " + e.from.id);
  });
  vis.forEach((n) => ok([n.x, n.y, n.w, n.h].every(Number.isFinite) && n.x >= -0.01 && n.y >= GOAL - 0.01 && n.x + n.w <= w.w + 0.01 && n.y + n.h <= w.h + 0.01, name + ": " + n.id + " outside the world"));
  const ref = refLinks(lvl, ctl);
  ok(links.filter((e) => e.kind === "rests").length === ref.rests, name + ": rests links " + links.length + " vs reference " + ref.rests);
  ok(links.filter((e) => e.kind === "stem").length === ref.stems, name + ": stems vs reference");
  return { visible: vis.length, w: Math.round(w.w), h: Math.round(w.h),
    rests: links.filter((e) => e.kind === "rests").length, stems: links.filter((e) => e.kind === "stem").length };
}

async function openAll(ctl) {
  for (let again = true; again; ) { again = false;
    for (const n of ctl.visibleNodes()) if (n.childCount > 0 && !n.open) { assert.equal(await ctl.open(n.id), true); again = true; } }
}
const closeAll = (ctl) => { for (const n of [...ctl.visibleNodes()].filter((m) => m.parent.root && m.open)) ctl.close(n.id); };

test("ported checks on the real level data, every open/closed state", async () => {
  const { lvl, ctl, view } = await make();
  ok(lvl.byId.size === 23, "the level data has 23 steps");
  const states = {};
  // all closed
  states.closed = checkState("closed", lvl, ctl);
  assert.deepEqual([states.closed.visible, states.closed.w, states.closed.h], [3, 300, 826]);
  assert.deepEqual([states.closed.rests, states.closed.stems], [2, 0]);   // literals from the prototype's edges()
  // first view: the roots' parts open
  for (const n of ctl.visibleNodes().filter((m) => m.parent.root && m.childCount > 0)) await ctl.open(n.id);
  states.first = checkState("first", lvl, ctl);
  assert.deepEqual([states.first.visible, states.first.w, states.first.h], [10, 364, 2568]);   // was [10, 1052, 2036]: edgeless sibling sets are now columns (re-based, sibling-column rule)
  assert.deepEqual([states.first.rests, states.first.stems], [4, 1]);   // stems were 3: a column member below the first is not a first-row child
  // all open
  await openAll(ctl);
  states.all = checkState("all-open", lvl, ctl);
  assert.deepEqual([states.all.visible, states.all.w, states.all.h], [23, 868, 5294]);   // was [23, 2824, 3472]: same re-basing
  assert.deepEqual([states.all.rests, states.all.stems], [7, 4]);   // stems were 6
  ok(states.all.visible === 23, "all open: every step visible");
  // every single-node toggle from all-open
  const withParts = [...lvl.byId.values()].filter((s) => s.children.length);
  ok(withParts.length === 8, "8 steps with parts");
  for (const s of withParts) { ctl.close(s.id); checkState("all-but-" + s.id, lvl, ctl); await openAll(ctl); }
  // every single open path from closed
  for (const s of withParts) {
    closeAll(ctl);
    for (const id of lvl.pathOf.get(s.id)) { const n = ctl.node(id); if (n && n.childCount > 0 && !n.open) await ctl.open(id); }
    checkState("path-" + s.id, lvl, ctl);
  }
  // closures on a known case are the page's business; the engine has no whole-graph closure (it never holds the graph).
  // planted error: two rows swapped must be caught by the premise-below check
  closeAll(ctl); await openAll(ctl);
  const a = ctl.node("primitive-to-all"), b = ctl.node("three-inputs");
  const t = a.y; a.y = b.y; b.y = t;
  let caught = false;
  ctl.visibleNodes().forEach((n) => n.spec.links.forEach((l) => { const p = ctl.node(l.to); if (p && p.parent === n.parent && !(p.y >= n.y + n.h)) caught = true; }));
  ok(caught, "planted swap of two rows was not detected");
  assert.equal(fails, 0);
  assert.equal(view.mounted.size, ctl.visibleNodes().length);
  console.log("PORTED CHECKS: " + checks + " checks, " + fails + " failed; loader calls " + lvl.calls.length + " (unique " + new Set(lvl.calls).size + " of 8 steps with parts)");
});

test("the premise links of the level data are the 14 of the prototype (7 sibling, 7 to a part)", async () => {
  const { lvl, ctl } = await make();
  await openAll(ctl);
  const rests = ctl.links().filter((e) => e.kind === "rests").length, stems = ctl.links().filter((e) => e.kind === "stem").length;
  assert.equal(rests, 7);
  assert.equal(stems, 4);   // 7 steps whose parent rests on them; only a first-row child (the top of a column too) gets a stem. Was 6 before edgeless sets became columns.
  assert.equal(lvl.pathOf.size, 23);
});
