// attach equals build: positions after on-demand loading equal positions with the children present.
// "Build" is the pure layout run on a complete tree made by hand from the same data (no controller, no cache,
// no dirty flags); "attach" is the controller after loading node by node, in several orders, with closes between.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createController } from "../controller.js";
import { layoutTree } from "../layout.js";
import { recordingView, fromLevel } from "./helpers.mjs";

const data = JSON.parse(readFileSync(new URL("./fixtures/level1.json", import.meta.url), "utf8"));
const SIZES = { nodeW: 300, nodeH: 190, gapX: 44, gapY: 76, pad: 32, head: 160, top: 34, topInset: 104 };

/* the complete tree, built eagerly, with exactly the `open` set the controller reports */
function build(lvl, openIds) {
  const mk = (s, parent) => {
    const n = { id: s.id, parent, premises: s.premises.slice(), open: openIds.has(s.id) && s.children.length > 0, children: [] };
    n.children = n.open ? s.children.map((c) => mk(c, n)) : [];
    return n;
  };
  const root = { root: true, id: "", parent: null, open: true, premises: [], children: [] };
  root.children = data.steps.map((s) => mk(s, root));
  layoutTree(root, SIZES);
  const out = new Map();
  (function walk(n) { for (const c of n.children) { out.set(c.id, [c.x, c.y, c.w, c.h]); walk(c); } })(root);
  return { out, world: [root.w, root.h] };
}
const snapshot = (ctl) => new Map(ctl.visibleNodes().map((n) => [n.id, [n.x, n.y, n.w, n.h]]));

async function compare(label, ctl, lvl) {
  const openIds = new Set(ctl.visibleNodes().filter((n) => n.open).map((n) => n.id));
  const ref = build(lvl, openIds), got = snapshot(ctl);
  assert.equal(got.size, ref.out.size, label + ": same visible set");
  for (const [id, box] of ref.out) assert.deepEqual(got.get(id), box, label + ": " + id);
  assert.deepEqual([ctl.world().w, ctl.world().h], ref.world, label + ": world");
  return got.size;
}

test("attach equals build, in every order of opening and across closes", async () => {
  let compared = 0, nodes = 0;
  const order = ["rh-from-everycharacter", "three-inputs"];
  for (let seed = 0; seed < 6; seed++) {
    const lvl = fromLevel(data), view = recordingView();
    const ctl = createController({ roots: lvl.roots, loadChildren: lvl.loader, maxHeld: 100, fitOnStart: false, sizes: { topInset: 104 } }, view);
    await ctl.ready;
    const withParts = [...lvl.byId.values()].filter((s) => s.children.length).map((s) => s.id);
    // a deterministic shuffle by seed, always opening a node only after its parent is open (the only order possible)
    const rnd = (() => { let x = seed + 1; return () => (x = (x * 48271) % 2147483647) / 2147483647; })();
    let pending = withParts.slice().sort(() => rnd() - 0.5);
    while (pending.length) {
      const next = pending.find((id) => !lvl.parentOf.get(id) || ctl.node(lvl.parentOf.get(id))?.open);
      if (next === undefined) break;     // what is left sits under a node that was closed again
      pending = pending.filter((id) => id !== next);
      await ctl.open(next);
      nodes += await compare("seed " + seed + " after open " + next, ctl, lvl); compared++;
      if (rnd() < 0.3) { const c = [...ctl.visibleNodes()].filter((n) => n.open && !n.parent.root)[0]; if (c) { ctl.close(c.id); pending.push(c.id); nodes += await compare("seed " + seed + " after close " + c.id, ctl, lvl); compared++; } }
    }
  }
  assert.ok(compared > 40);
  console.log("ATTACH==BUILD: " + compared + " comparisons, " + nodes + " node positions compared");
});

test("the layout of one opened node is computed from its own children: untouched subtrees are not re-measured", async () => {
  const lvl = fromLevel(data), view = recordingView();
  const ctl = createController({ roots: lvl.roots, loadChildren: lvl.loader, maxHeld: 100, fitOnStart: false }, view);
  await ctl.ready;
  for (const n of ctl.visibleNodes().filter((m) => m.childCount > 0)) await ctl.open(n.id);
  const before = ctl.stats().measured;
  const target = ctl.visibleNodes().find((n) => !n.open && n.childCount > 0 && n.depth === 2);
  assert.ok(target, "a closed node with parts at depth 2");
  await ctl.open(target.id);
  const measured = ctl.stats().measured - before;
  assert.ok(measured > 0 && measured <= 2 * (target.depth + 1) + ctl.visibleNodes().length * 0 + 1 + target.childCount, "re-measured " + measured + " nodes for one open at depth " + target.depth);
  assert.ok(measured < ctl.visibleNodes().length, "fewer than all visible nodes were re-measured: " + measured + " of " + ctl.visibleNodes().length);
});
