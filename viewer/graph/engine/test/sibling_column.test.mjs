// Sibling layout: an edgeless sibling set is a COLUMN in data order; the loose siblings of a mixed set follow the linked
// block as a column; a fully linked set keeps the rows. Written BEFORE the layout change (contract-first).
//
//  L1 edgeless -> column, centred, exact numbers   L2 order is the array's   L3 fully linked unchanged (frozen copy)
//  L4 mixed: linked block by the old algorithm alone, loose column after it   L5 self and foreign premises are not links
//  L6 an open sibling takes its measured size in the column   L7 no links invented (through the controller)
//  L8 pure and deterministic   L9 one child, empty set
import { test } from "node:test";
import assert from "node:assert/strict";
import { createController } from "../controller.js";
import { layoutTree } from "../layout.js";
import { recordingView, tiny } from "./helpers.mjs";
import { readFileSync } from "node:fs";

const S = { nodeW: 300, nodeH: 190, gapX: 44, gapY: 76, pad: 32, head: 160, top: 34, topInset: 0 };

/* ---- FROZEN COPY of layout.js as of fd42c540 (rows only): the oracle for L3 and for the linked block of L4. ---- */
// Layout of an open node from its OWN children: rows by dependency depth among siblings. Pure: no DOM.
// Ported from the prototype's core.js (place / measure / position), with two differences: a node's measured size
// is kept (`clean`), so opening one node re-measures it and its ancestors only; and the sizes are options.
//
// A node record (the fields this file reads and writes):
//   reads   root (true for the virtual top), open, children (array, or null when closed), premises (ids)
//   writes  x, y, w, h (world coordinates), rx, ry (relative to the parent's body), layer, inner, clean
// A node is re-measured unless `clean === true`; the caller sets `clean = false` on the node and every ancestor
// whenever the node's children change.

function frozenLayoutTree(root, S) {
  let measured = 0;
  const isOpen = (n) => n.root === true || (n.open === true && Array.isArray(n.children) && n.children.length > 0);

  /* a step sits below every sibling that rests on it; a cycle among siblings stops, it does not loop */
  function layers(kids) {
    const memo = {};
    function L(k, guard) {
      if (memo[k.id] !== undefined) return memo[k.id];
      if (guard > kids.length) return 0;
      let v = 0;
      for (const m of kids) if (m !== k && m.premises.indexOf(k.id) >= 0) v = Math.max(v, L(m, guard + 1) + 1);
      memo[k.id] = v;
      return v;
    }
    for (const k of kids) k.layer = L(k, 0);
  }

  function measure(n) {
    if (n.clean === true) return;
    measured++;
    if (isOpen(n)) {
      const inner = place(n.children);
      n.inner = inner;
      if (n.root) { n.w = inner.w; n.h = inner.h + S.topInset; }
      else { n.w = Math.max(S.nodeW, inner.w + 2 * S.pad); n.h = S.head + S.top + inner.h + S.pad; }
    } else { n.w = S.nodeW; n.h = S.nodeH; n.inner = null; }
    n.clean = true;
  }

  function place(kids) {
    if (!kids.length) return { w: 0, h: 0 };
    kids.forEach(measure);
    layers(kids);
    const rows = [];
    for (const k of kids) (rows[k.layer] = rows[k.layer] || []).push(k);
    let y = 0, minX = Infinity, maxX = -Infinity;
    rows.forEach((row, li) => {
      const items = row.map((k, i) => {
        let want = null;
        if (li > 0) {
          const deps = kids.filter((m) => m.layer < li && m.premises.indexOf(k.id) >= 0);
          if (deps.length) want = deps.reduce((s, m) => s + m.rx + m.w / 2, 0) / deps.length;
        }
        return { k, i, want };
      });
      items.sort((a, b) => {
        if (a.want === null && b.want === null) return a.i - b.i;
        if (a.want === null) return 1;
        if (b.want === null) return -1;
        return (a.want - b.want) || (a.i - b.i);
      });
      let cur = null, rowH = 0;
      for (const it of items) {
        const k = it.k;
        let left = it.want === null ? (cur === null ? 0 : cur) : it.want - k.w / 2;
        if (cur !== null && left < cur) left = cur;
        k.rx = left; k.ry = y; cur = left + k.w + S.gapX; rowH = Math.max(rowH, k.h);
        minX = Math.min(minX, left); maxX = Math.max(maxX, left + k.w);
      }
      y += rowH + S.gapY;
    });
    for (const k of kids) k.rx -= minX;
    return { w: maxX - minX, h: y - S.gapY };
  }

  function position(n) {
    if (!n.inner) return;
    const ox = n.root ? 0 : n.x + (n.w - n.inner.w) / 2, oy = n.root ? S.topInset : n.y + S.head + S.top;
    for (const c of n.children) { c.x = ox + c.rx; c.y = oy + c.ry; position(c); }
  }

  measure(root);
  root.x = 0; root.y = 0;
  position(root);
  return measured;
}
/* ---- end of the frozen copy ---- */

const rec = (id, premises = [], kids = null) => ({
  id, premises, children: kids, open: kids !== null, clean: false,
  x: 0, y: 0, w: 0, h: 0, rx: 0, ry: 0, layer: 0, inner: null,
});
const top = (kids) => ({ id: "root", root: true, premises: [], children: kids, open: true, clean: false, x: 0, y: 0, w: 0, h: 0, rx: 0, ry: 0, layer: 0, inner: null });
/* a sibling set of closed nodes from [id, premises] pairs; an entry with a third item is an OPEN node with that many closed children */
const build = (defs) => defs.map(([id, pr, nk]) => rec(id, pr || [], nk ? Array.from({ length: nk }, (_, i) => rec(id + "." + i)) : null));
const run = (fn, defs) => { const r = top(build(defs)); fn(r, S); return r; };
const lay = (defs) => run(layoutTree, defs);
const frozen = (defs) => run(frozenLayoutTree, defs);
const pos = (r) => r.children.map((k) => [k.id, k.rx, k.ry, k.layer]);
const size = (r) => ({ w: r.inner.w, h: r.inner.h });
const H = S.nodeH, W0 = S.nodeW, G = S.gapY;

/* an independent classifier for the tests: the definition from the contract, not the layout's code */
function classify(defs) {
  const ids = new Set(defs.map((d) => d[0]));
  const linked = new Set();
  for (const [id, pr] of defs) for (const p of pr || []) if (p !== id && ids.has(p)) { linked.add(id); linked.add(p); }
  return linked.size === 0 ? "edgeless" : linked.size === defs.length ? "linked" : "mixed";
}

test("L1: an edgeless set is a column in array order, centred on the axis, exact numbers", () => {
  const r = lay([["a"], ["b"], ["c"]]);
  assert.deepEqual(pos(r).map((p) => [p[0], p[1], p[2]]), [["a", 0, 0], ["b", 0, H + G], ["c", 0, 2 * (H + G)]]);
  assert.deepEqual(size(r), { w: W0, h: 3 * H + 2 * G });
  assert.equal(r.h, 3 * H + 2 * G + S.topInset);
});

test("L1: centring uses each sibling's own width against W = max width (an open sibling is wider)", () => {
  const r = lay([["a"], ["b", [], 1], ["c"]]);
  const [a, b, c] = r.children, Wmax = S.nodeW + 2 * S.pad;
  assert.equal(b.w, Wmax); assert.equal(b.h, S.head + S.top + H + S.pad);
  assert.deepEqual([a.rx, b.rx, c.rx], [S.pad, 0, S.pad]);
  assert.deepEqual([a.ry, b.ry, c.ry], [0, H + G, H + G + b.h + G]);
  assert.deepEqual(size(r), { w: Wmax, h: H + G + b.h + G + H });
});

test("L2: the column is never sorted: reverse-alphabetical ids come out in array order", () => {
  const r = lay([["z"], ["m"], ["a"]]);
  assert.deepEqual(pos(r).map((p) => p[0]), ["z", "m", "a"]);
  assert.deepEqual(r.children.map((k) => k.ry), [0, H + G, 2 * (H + G)]);
  const r2 = lay([["c", ["x-foreign"]], ["b"], ["a"]]);
  assert.deepEqual(r2.children.map((k) => [k.id, k.ry]), [["c", 0], ["b", H + G], ["a", 2 * (H + G)]]);
});

test("L3: a fully linked set gets exactly the positions of the frozen fd42c540 layout (generated shapes)", () => {
  const shapes = {
    chain: [["a", ["b"]], ["b", ["c"]], ["c", ["d"]], ["d"]],
    chainReversed: [["d"], ["c", ["d"]], ["b", ["c"]], ["a", ["b"]]],
    diamond: [["top", ["l", "r"]], ["l", ["base"]], ["r", ["base"]], ["base"]],
    fan: [["hub"], ["s1", ["hub"]], ["s2", ["hub"]], ["s3", ["hub"]], ["s4", ["hub"]]],
    fanIn: [["goal", ["p1", "p2", "p3"]], ["p1"], ["p2"], ["p3"]],
    pair: [["x", ["y"]], ["y"]],
    twoChains: [["a", ["b"]], ["b"], ["c", ["d"]], ["d"]],
    withOpen: [["a", ["b"]], ["b", [], 1], ["c", ["b"], 1]],   // open siblings with ONE child: a nested set of one is unchanged
    cycle: [["a", ["b"]], ["b", ["a"]]],
  };
  for (const [name, defs] of Object.entries(shapes)) {
    assert.equal(classify(defs), "linked", name + " must be fully linked for this case");
    const a = lay(defs), b = frozen(defs);
    assert.ok(a.children.length >= 2 && a.inner.w > 0, name);
    assert.deepEqual(pos(a), pos(b), name + ": rx, ry, layer");
    assert.deepEqual(size(a), size(b), name + ": set size");
    assert.deepEqual([a.w, a.h], [b.w, b.h], name);
  }
});

test("L3: every fully linked set of the engine fixture level1.json equals the frozen layout, at every level", () => {
  const data = JSON.parse(readFileSync(new URL("./fixtures/level1.json", import.meta.url), "utf8"));
  let checked = 0;
  (function walk(list) {
    const defs = list.map((s) => [s.id, s.premises || []]);
    if (list.length >= 2 && classify(defs) === "linked") {
      const a = lay(defs), b = frozen(defs);
      assert.deepEqual(pos(a), pos(b)); assert.deepEqual(size(a), size(b)); checked++;
    }
    for (const s of list) if (s.children && s.children.length) walk(s.children);
  })(data.steps);
  assert.ok(checked >= 1, "the fixture has at least one fully linked set: " + checked);
});

test("L4: a mixed set: the linked block is the old algorithm on the linked siblings alone; the loose ones follow as a column", () => {
  const defs = [["a"], ["c"], ["b", ["a"]], ["d"]];                 // a and b linked (b rests on a); c, d loose
  assert.equal(classify(defs), "mixed");
  const r = lay(defs), byId = Object.fromEntries(r.children.map((k) => [k.id, k]));
  const alone = frozen([["a"], ["b", ["a"]]]);                       // the oracle: linked subset alone
  assert.deepEqual([byId.a.rx, byId.a.ry, byId.a.layer], [alone.children[0].rx, alone.children[0].ry, alone.children[0].layer]);
  assert.deepEqual([byId.b.rx, byId.b.ry, byId.b.layer], [alone.children[1].rx, alone.children[1].ry, alone.children[1].layer]);
  // exact numbers: b is the first row (ry 0), a the second; the block is 2 rows high
  const linkedH = 2 * H + G;
  assert.deepEqual([byId.b.ry, byId.a.ry], [0, H + G]);
  assert.deepEqual([byId.c.ry, byId.d.ry], [linkedH + G, linkedH + G + H + G]);
  assert.deepEqual([byId.c.rx, byId.d.rx, byId.a.rx, byId.b.rx], [0, 0, 0, 0]);
  assert.deepEqual(size(r), { w: W0, h: linkedH + G + 2 * H + G });
});

test("L4: a column wider than the linked block shifts the block right by half the difference; both centred on W / 2", () => {
  const r = lay([["a"], ["b", ["a"]], ["wide", [], 1], ["e"]]);
  const k = Object.fromEntries(r.children.map((x) => [x.id, x]));
  const Wd = S.nodeW + 2 * S.pad, shift = (Wd - W0) / 2, linkedH = 2 * H + G;
  assert.equal(k.wide.w, Wd);
  assert.deepEqual([k.a.rx, k.b.rx], [shift, shift]);
  assert.deepEqual([k.wide.rx, k.e.rx], [0, shift]);
  assert.deepEqual([k.b.ry, k.a.ry, k.wide.ry, k.e.ry], [0, H + G, linkedH + G, linkedH + G + k.wide.h + G]);
  assert.deepEqual(size(r), { w: Wd, h: linkedH + G + k.wide.h + G + H });
});

test("L4: a linked block wider than the loose column keeps its rows at rx from the old algorithm; the column is centred under it", () => {
  const r = lay([["p"], ["q"], ["g", ["p", "q"]], ["loose"]]);        // p, q side by side below g: block is 2 nodes wide
  const k = Object.fromEntries(r.children.map((x) => [x.id, x]));
  const alone = frozen([["p"], ["q"], ["g", ["p", "q"]]]);
  const Wl = alone.inner.w;
  assert.ok(Wl > W0);
  assert.deepEqual([k.p.rx, k.q.rx, k.g.rx], alone.children.map((x) => x.rx));
  assert.equal(k.loose.rx, (Wl - W0) / 2);
  assert.deepEqual(size(r), { w: Wl, h: alone.inner.h + G + H });
});

test("L5: a premise naming the node itself is not a link: the node is loose", () => {
  const r = lay([["a", ["a"]], ["b"]]);
  assert.deepEqual(r.children.map((k) => [k.id, k.rx, k.ry]), [["a", 0, 0], ["b", 0, H + G]]);
  const m = lay([["x"], ["y", ["x"]], ["s", ["s"]]]);                  // mixed: s is loose, after the linked block
  assert.equal(m.children[2].ry, 2 * H + G + G);
});

test("L5: a premise naming an id outside the set is not a link: the node is loose", () => {
  const r = lay([["a", ["elsewhere"]], ["b"]]);
  assert.deepEqual(r.children.map((k) => [k.id, k.rx, k.ry]), [["a", 0, 0], ["b", 0, H + G]]);
  const m = lay([["x"], ["y", ["x"]], ["f", ["elsewhere"]]]);
  assert.equal(m.children[2].ry, 2 * H + G + G);
  assert.deepEqual(size(m), { w: W0, h: 3 * H + 2 * G });
});

test("L6: an open sibling in an edgeless set takes its measured w and h; centring uses its w", () => {
  const r = lay([["o", [], 3], ["c"]]);
  const [o, c] = r.children;
  assert.equal(o.w, S.nodeW + 2 * S.pad);
  assert.equal(o.h, S.head + S.top + (3 * H + 2 * G) + S.pad);
  assert.equal(o.rx, 0); assert.equal(c.rx, S.pad);
  assert.equal(c.ry, o.h + G);
  assert.deepEqual(size(r), { w: o.w, h: o.h + G + H });
});

test("L9: one child: rx 0, ry 0, the set is its size; an empty set is 0 by 0", () => {
  const r = lay([["only"]]);
  assert.deepEqual(pos(r), [["only", 0, 0, 0]]);
  assert.deepEqual(size(r), { w: W0, h: H });
  const e = top([]); layoutTree(e, S);
  assert.deepEqual(e.inner, { w: 0, h: 0 });
});

test("L8: the same input gives the same output twice; layout.js still touches no DOM", () => {
  const defs = [["a"], ["b", ["a"]], ["o", [], 2], ["z"], ["c", ["c"]]];
  const x = lay(defs), y = lay(defs);
  assert.deepEqual(pos(x), pos(y)); assert.deepEqual(size(x), size(y));
  assert.deepEqual(x.children.map((k) => [k.w, k.h, k.x, k.y]), y.children.map((k) => [k.w, k.h, k.x, k.y]));
  assert.ok(!/\b(document|window|Element|HTMLElement|createElement)\b/.test(readFileSync(new URL("../layout.js", import.meta.url), "utf8")));
});

test("L8: world coordinates follow the column (x, y of an edgeless set under the root)", () => {
  const r = lay([["a"], ["b"]]);
  assert.deepEqual(r.children.map((k) => [k.x, k.y]), [[0, 0], [0, H + G]]);
});

test("column members: layer is the row index of the column (stem only from the top one); loose after a block continue the count", () => {
  assert.deepEqual(lay([["a"], ["b"], ["c"]]).children.map((k) => k.layer), [0, 1, 2]);
  const m = lay([["a"], ["b", ["a"]], ["c"], ["d"]]);                  // block has layers 0 (b) and 1 (a)
  assert.deepEqual(m.children.map((k) => [k.id, k.layer]), [["a", 1], ["b", 0], ["c", 2], ["d", 3]]);
});

async function ctlOf(t) {
  const view = recordingView();
  const ctl = createController({ roots: t.roots, loadChildren: t.loader, maxHeld: 20, fitOnStart: false }, view);
  await ctl.ready;
  return { ctl, view };
}

test("L7: an edgeless set (top level and an opened node's children) is handed to setLinks with no link between siblings", async () => {
  const t = tiny([
    { id: "t1", kids: ["k1", "k2", "k3"] }, { id: "t2" }, { id: "t3" },
    { id: "k1" }, { id: "k2" }, { id: "k3" },
  ]);
  const { ctl, view } = await ctlOf(t);
  assert.deepEqual(ctl.links(), []); assert.deepEqual(view.links, []);
  await ctl.open("t1");
  assert.deepEqual(ctl.links(), []); assert.deepEqual(view.links, []);
  const col = ["k1", "k2", "k3"].map((id) => ctl.node(id));
  assert.ok(col[0].y < col[1].y && col[1].y < col[2].y, "the opened node's children are stacked");
});

test("L7: in a mixed set only the real links are handed over; the loose sibling has none", async () => {
  const t = tiny([{ id: "p", kids: ["u", "v", "w"] }, { id: "u" }, { id: "v", premises: ["u"] }, { id: "w" }]);
  const { ctl, view } = await ctlOf(t);
  await ctl.open("p");
  const l = ctl.links().filter((e) => e.kind === "rests").map((e) => e.from.id + ">" + e.to.id);
  assert.deepEqual(l, ["u>v"]);
  assert.deepEqual(view.links.filter((e) => e.kind === "rests").length, 1);
  assert.ok(ctl.links().every((e) => e.from.id !== "w" && e.to.id !== "w"));
});
