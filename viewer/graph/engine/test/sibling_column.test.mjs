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
import { normalizeOptions, DEFAULTS } from "../options.js";
import { fromLevel } from "./helpers.mjs";
import { recordingView, tiny } from "./helpers.mjs";
import { readFileSync, readdirSync } from "node:fs";

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

const rec = (id, premises = [], kids = null, stem) => ({
  id, premises, children: kids, open: kids !== null, clean: false,
  x: 0, y: 0, w: 0, h: 0, rx: 0, ry: 0, layer: 0, inner: null,
  ...(stem === undefined ? {} : { spec: { parentLinksTo: stem } }),     // the controller's record carries its NodeSpec as `spec`
});
const top = (kids) => ({ id: "root", root: true, premises: [], children: kids, open: true, clean: false, x: 0, y: 0, w: 0, h: 0, rx: 0, ry: 0, layer: 0, inner: null });
/* a sibling set of closed nodes from [id, premises] pairs; an entry with a third item is an OPEN node with that many closed children */
const build = (defs) => defs.map(([id, pr, nk, stem]) => rec(id, pr || [], nk ? Array.from({ length: nk }, (_, i) => rec(id + "." + i)) : null, stem));
const run = (fn, defs) => { const r = top(build(defs)); fn(r, S); return r; };
const lay = (defs) => run((r, S) => layoutTree(r, S, "column"), defs);      // every case below runs with layout.siblings "column"
const frozen = (defs) => run(frozenLayoutTree, defs);
/* the same set as the children of an open NON-root node (a stem is a drawn edge only there); the result has .children and .inner of that node */
const underP = (fn, defs) => { const p = rec("P", [], build(defs)), r = top([p]); fn(r, S); return { children: p.children, inner: p.inner }; };
const layP = (defs) => underP((r, S) => layoutTree(r, S, "column"), defs);
const frozenP = (defs) => underP(frozenLayoutTree, defs);
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
  const ctl = createController({ roots: t.roots, loadChildren: t.loader, maxHeld: 20, fitOnStart: false, layout: { siblings: "column" } }, view);
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

/* ---- Round 2: a stem is a drawn edge. A sibling whose parent rests on it (spec.parentLinksTo) counts as LINKED. ---- */

test("S2: no sibling links, b and d are stem children: b, d share row 0 (b left of d); a and c are a column below, in array order", () => {
  const r = layP([["a"], ["b", [], 0, true], ["c"], ["d", [], 0, true]]);
  const k = Object.fromEntries(r.children.map((x) => [x.id, x]));
  assert.deepEqual([k.b.rx, k.b.ry, k.b.layer, k.d.rx, k.d.ry, k.d.layer], [0, 0, 0, W0 + S.gapX, 0, 0]);
  const Wb = 2 * W0 + S.gapX;
  assert.deepEqual([k.a.rx, k.a.ry, k.c.rx, k.c.ry], [(Wb - W0) / 2, H + G, (Wb - W0) / 2, 2 * (H + G)]);
  assert.deepEqual([k.a.layer, k.c.layer], [1, 2]);
  assert.deepEqual(size(r), { w: Wb, h: 3 * H + 2 * G });
});

test("S2: a set whose siblings are all stem children is one row, as before (no sibling link, all layer 0)", () => {
  const defs = [["a", [], 0, true], ["b", [], 0, true], ["c", [], 0, true]];
  assert.deepEqual(pos(layP(defs)), pos(frozenP(defs)));
});

test("S3: a stem child that a sibling rests on is at layer > 0 as before, with no stem (control)", async () => {
  const defs = [["p", [], 0, true], ["q", ["p"]], ["z"]];
  const r = lay(defs), f = frozen(defs.slice(0, 2));
  assert.deepEqual([r.children[0].layer, r.children[1].layer], [1, 0]);
  assert.deepEqual(pos(r).slice(0, 2), pos(f));
  const t = tiny([{ id: "par", kids: ["p", "q", "z"] }, { id: "p", stem: true }, { id: "q", premises: ["p"] }, { id: "z" }]);
  const { ctl } = await ctlOf(t);
  await ctl.open("par");
  assert.deepEqual(ctl.links().filter((e) => e.kind === "stem"), []);
});

test("S2 through the controller: both stem children of an otherwise edgeless set get their stem", async () => {
  const t = tiny([{ id: "par", kids: ["a", "b", "c"] }, { id: "a", stem: true }, { id: "b" }, { id: "c", stem: true }]);
  const { ctl } = await ctlOf(t);
  await ctl.open("par");
  assert.deepEqual(ctl.links().filter((e) => e.kind === "stem").map((e) => e.from.id).sort(), ["a", "c"]);
  assert.deepEqual([ctl.node("a").layer, ctl.node("c").layer, ctl.node("b").layer], [0, 0, 1]);
});

test("S1: on the level data and the page real fixtures every stem child that was at layer 0 under fd42c540 is at layer 0 again", () => {
  const sets = [];
  const lv = JSON.parse(readFileSync(new URL("./fixtures/level1.json", import.meta.url), "utf8"));
  (function walk(list, parent) {
    sets.push(["level1 " + (parent ? parent.id : "top"), list.map((x) => [x.id, x.premises || [], 0, parent ? parent.premises.includes(x.id) : false])]);
    for (const x of list) if (x.children && x.children.length) walk(x.children, x);
  })(lv.steps, null);
  const real = new URL("../../page/test/fixtures/real/step/", import.meta.url);
  for (const f of readdirSync(real)) {
    const st = JSON.parse(readFileSync(new URL(f, real), "utf8"));
    if (!st.children.length) continue;
    const pr = {}; for (const l of st.rests_on) (pr[l.from] = pr[l.from] || []).push(l.to);
    sets.push(["page real " + st.id, st.children.map((c) => [c.id, pr[c.id] || [], 0, c.parent_rests_on])]);
  }
  let stems = 0, sets0 = 0;
  for (const [name, defs] of sets) {
    const a = layP(defs), b = frozenP(defs);
    a.children.forEach((k, i) => {
      if (defs[i][3] === true && b.children[i].layer === 0) { stems++; assert.equal(k.layer, 0, name + ": " + k.id + " lost its first row"); }
    });
    sets0++;
  }
  assert.ok(sets0 >= 10 && stems >= 6, "the fixtures hold stem children at layer 0: sets " + sets0 + ", stems " + stems);
});

/* ---- Round 3: the column rule is an option, layout.siblings, default "rows" (the layout of fd42c540 for every set) ---- */

const SHAPES = {
  edgeless: [["a"], ["b"], ["c"]],
  mixed: [["a"], ["c"], ["b", ["a"]], ["d"]],
  linked: [["a", ["b"]], ["b", ["c"]], ["c"]],
  stemOnly: [["a", [], 0, true], ["b"], ["c", [], 0, true], ["d"]],
  stemWithSiblingLink: [["p", [], 0, true], ["q", ["p"]], ["z"]],
  selfAndForeign: [["a", ["a"]], ["b", ["elsewhere"]], ["c"]],
  single: [["only"]],
  empty: [],
  openChildren: [["o", [], 3], ["c"], ["d", [], 1], ["e", ["c"]]],
  openNestedEdgeless: [["a", [], 2], ["b", [], 4], ["c"]],
};
const whole = (r) => { const out = []; (function walk(n) { for (const c of n.children || []) { out.push([c.id, c.x, c.y, c.w, c.h, c.rx, c.ry, c.layer]); walk(c); } })(r); return out.concat([[r.w, r.h, r.inner && r.inner.w, r.inner && r.inner.h]]); };

test("O2: with the default and with layout.siblings 'rows', every node of every set shape equals the frozen fd42c540 layout", () => {
  for (const [name, defs] of Object.entries(SHAPES)) {
    const f = whole(frozen(defs));
    assert.ok(f.length >= 1);
    assert.deepEqual(whole(run(layoutTree, defs)), f, name + " (default)");
    assert.deepEqual(whole(run((r, S) => layoutTree(r, S, "rows"), defs)), f, name + " (rows)");
    assert.deepEqual(whole(run((r, S) => layoutTree(r, S, undefined), defs)), f, name + " (undefined)");
  }
});

test("O2 control: with 'column' the edgeless, mixed and stem-only shapes differ from the frozen layout (the comparison can fail)", () => {
  for (const name of ["edgeless", "mixed", "stemOnly"]) assert.notDeepEqual(whole(run((r, S) => layoutTree(r, S, "column"), SHAPES[name])), whole(frozen(SHAPES[name])), name);
});

test("O1: layout.siblings: default 'rows', frozen DEFAULTS, 'column' accepted, anything else refused like the other options", () => {
  assert.equal(DEFAULTS.layout.siblings, "rows");
  assert.ok(Object.isFrozen(DEFAULTS.layout));
  assert.equal(normalizeOptions({}).layout.siblings, "rows");
  assert.equal(normalizeOptions({ layout: {} }).layout.siblings, "rows");
  assert.equal(normalizeOptions({ layout: { siblings: undefined } }).layout.siblings, "rows");
  assert.equal(normalizeOptions({ layout: { siblings: "rows" } }).layout.siblings, "rows");
  assert.equal(normalizeOptions({ layout: { siblings: "column" } }).layout.siblings, "column");
  assert.equal(DEFAULTS.layout.siblings, "rows", "normalizing did not touch DEFAULTS");
  const refused = (raw, re) => assert.throws(() => normalizeOptions(raw), (e) => e instanceof TypeError && re.test(e.message), JSON.stringify(raw));
  for (const bad of ["columns", "Column", "", "row", null, 1, true, ["column"], {}]) refused({ layout: { siblings: bad } }, /layout\.siblings/);
  refused({ layout: { rows: 1 } }, /unknown option layout\.rows/);
  refused({ layout: "column" }, /layout must be an object/);
  refused({ layout: null }, /layout must be an object/);
});

test("O3 through the controller: 'column' lays out the level data with the stems of fd42c540 and the new sizes; the default does not change", async () => {
  const run1 = async (layout) => {
    const lvl = fromLevel(JSON.parse(readFileSync(new URL("./fixtures/level1.json", import.meta.url), "utf8"))), view = recordingView();
    const ctl = createController({ roots: lvl.roots, loadChildren: lvl.loader, maxHeld: 500, fitOnStart: false, sizes: { topInset: 104 }, ...(layout ? { layout } : {}) }, view);
    await ctl.ready;
    const st = () => { const w = ctl.world(), l = ctl.links(); return [ctl.visibleNodes().length, Math.round(w.w), Math.round(w.h), l.filter((e) => e.kind === "rests").length, l.filter((e) => e.kind === "stem").length]; };
    for (const n of ctl.visibleNodes().filter((m) => m.parent.root && m.childCount > 0)) await ctl.open(n.id);
    const first = st();
    for (let again = true; again; ) { again = false; for (const n of ctl.visibleNodes()) if (n.childCount > 0 && !n.open) { await ctl.open(n.id); again = true; } }
    return { first, all: st() };
  };
  assert.deepEqual(await run1(null), { first: [10, 1052, 2036, 4, 3], all: [23, 2824, 3472, 7, 6] });
  assert.deepEqual(await run1({ siblings: "rows" }), { first: [10, 1052, 2036, 4, 3], all: [23, 2824, 3472, 7, 6] });
  assert.deepEqual(await run1({ siblings: "column" }), { first: [10, 1052, 2036, 4, 3], all: [23, 1620, 4270, 7, 6] });
});

test("O2 through the controller: with no layout option an edgeless and a mixed set sit where the frozen fd42c540 layout puts them", async () => {
  const t = tiny([{ id: "par", kids: ["a", "b", "c", "d"] }, { id: "a" }, { id: "b", premises: ["a"] }, { id: "c" }, { id: "d", stem: true }]);
  const view = recordingView();
  const ctl = createController({ roots: t.roots, loadChildren: t.loader, maxHeld: 20, fitOnStart: false }, view);
  await ctl.ready; await ctl.open("par");
  const f = frozen([["a"], ["b", ["a"]], ["c"], ["d", [], 0, true]]);
  assert.deepEqual(["a", "b", "c", "d"].map((id) => [ctl.node(id).rx, ctl.node(id).ry, ctl.node(id).layer]), f.children.map((k) => [k.rx, k.ry, k.layer]));
  const e = tiny([{ id: "par", kids: ["x", "y", "z"] }, { id: "x" }, { id: "y" }, { id: "z" }]);
  const c2 = createController({ roots: e.roots, loadChildren: e.loader, maxHeld: 20, fitOnStart: false }, recordingView());
  await c2.ready; await c2.open("par");
  assert.deepEqual(["x", "y", "z"].map((id) => [c2.node(id).rx, c2.node(id).ry]), [[0, 0], [W0 + S.gapX, 0], [2 * (W0 + S.gapX), 0]], "one row, as before");
});

/* ---- Round 3 (PR 87 review): a stem counts as a drawn edge only for a child of a real (non-root) parent. ---- */

test("S4: in the ROOT's top list a stem flag is not a link: three siblings with no premises are a column in array order", async () => {
  const t = tiny([{ id: "a" }, { id: "b", stem: true }, { id: "c" }]);
  const { ctl, view } = await ctlOf(t);
  const n = ["a", "b", "c"].map((id) => ctl.node(id));
  assert.deepEqual(n.map((k) => [k.rx, k.ry, k.layer]), [[0, 0, 0], [0, H + G, 1], [0, 2 * (H + G), 2]]);
  assert.deepEqual(ctl.links(), []); assert.deepEqual(view.links, []);
  assert.equal(ctl.world().h, 3 * H + 2 * G);
});

test("S5 control: the same three as children of an opened non-root node: the stem child is linked (row 0), the others follow as a column", async () => {
  const t = tiny([{ id: "par", kids: ["a", "b", "c"] }, { id: "a" }, { id: "b", stem: true }, { id: "c" }]);
  const { ctl } = await ctlOf(t);
  await ctl.open("par");
  const n = ["a", "b", "c"].map((id) => ctl.node(id));
  assert.deepEqual(n.map((k) => [k.rx, k.ry, k.layer]), [[0, H + G, 1], [0, 0, 0], [0, 2 * (H + G), 2]]);
  assert.deepEqual(ctl.links().filter((e) => e.kind === "stem").map((e) => e.from.id), ["b"]);
});
