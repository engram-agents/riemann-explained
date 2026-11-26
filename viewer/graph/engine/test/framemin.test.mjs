// zoom.frameMin: a floor on the camera scale when framing an OPENED node (reveal / deep link / semantic open).
// null (the default) resolves to zoom.min, so a caller who does not pass it gets exactly today's camera.
// Closed framing, fit() and the reader's own zoom keep zoom.min.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createController } from "../controller.js";
import { normalizeOptions, DEFAULTS, openFrameCap } from "../options.js";
import { recordingView, generated, tiny } from "./helpers.mjs";

const VP = { w: 390, h: 844 };
const ZMIN = 0.06, PADO = 24;
const isErr = (e) => e instanceof TypeError && /zoom\.frameMin/.test(e.message) && !/unknown option/.test(e.message);
const tick = () => new Promise((r) => setTimeout(r, 0));

/* A FROZEN copy of the arithmetic at eec53ed9 (camera.frame and controller.frameNode), so "default is today" is checked
   against the old code and not against whatever the engine does now. */
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
function frozenFrame(vp, x, y, w, h, kmax, pad, kmin) {
  const k = clamp(Math.min((vp.w - 2 * pad) / w, (vp.h - 2 * pad) / h), kmin, kmax);
  return { k, tx: (vp.w - w * k) / 2 - x * k, ty: Math.max(pad, (vp.h - h * k) / 2) - y * k };
}
function frozenFrameNode(o, vp, n) {
  const open = n.open && n.children && n.children.length > 0, S = o.semantic, Z = o.zoom;
  const kmax = open ? Math.min(Z.frameMaxOpen, S.frameOpenShare * S.openPx / o.sizes.nodeW) : Math.min(Z.frameMaxClosed, S.frameClosedShare * S.openPx / o.sizes.nodeW);
  return frozenFrame(vp, n.x, n.y, n.w, n.h, kmax, open ? Z.framePadOpen : Z.framePadClosed, Z.min);
}

/* One parent "p" with 12 kids in a column: opened, a 364 x 3342 node, tall in a phone viewport (a rows layout would be wide and short). A second root "q" stays closed. */
const defs = [{ id: "p", kids: Array.from({ length: 12 }, (_, i) => "c" + i) }, { id: "q", kids: ["q0"] },
  ...Array.from({ length: 12 }, (_, i) => ({ id: "c" + i })), { id: "q0" }];
async function start(zoom, vp = VP) {
  const t = tiny(defs), view = recordingView(vp);
  const ctl = createController({ roots: t.roots, loadChildren: t.loader, zoom, layout: { siblings: "column" } }, view);
  await ctl.ready;
  return { ctl, view, t };
}

/* ---- F1 the option ---- */
test("F1: DEFAULTS holds null, and null / undefined / absent resolve to zoom.min after the merge", () => {
  assert.equal(DEFAULTS.zoom.frameMin, null);
  assert.equal(normalizeOptions({}).zoom.frameMin, ZMIN);
  assert.equal(normalizeOptions({ zoom: { min: 0.5 } }).zoom.frameMin, 0.5);
  for (const v of [null, undefined]) assert.equal(normalizeOptions({ zoom: { frameMin: v } }).zoom.frameMin, ZMIN);
  assert.equal(normalizeOptions({ zoom: { min: 2, max: 3 } }).zoom.frameMin, 2, "a zoom.min above frameMaxOpen is not newly refused");
});
test("F1: below zoom.min is a TypeError naming zoom.frameMin", () => assert.throws(() => normalizeOptions({ zoom: { frameMin: 0.01 } }), isErr));
test("F1: above zoom.frameMaxOpen is a TypeError naming zoom.frameMin", () => {
  assert.throws(() => normalizeOptions({ zoom: { frameMin: 2 } }), isErr);
  assert.throws(() => normalizeOptions({ zoom: { frameMaxOpen: 0.9, frameMin: 1 } }), isErr);
});
test("F1: NaN is a TypeError naming zoom.frameMin", () => assert.throws(() => normalizeOptions({ zoom: { frameMin: NaN } }), isErr));
test("F1: a string is a TypeError naming zoom.frameMin", () => assert.throws(() => normalizeOptions({ zoom: { frameMin: "1" } }), isErr));
test("F1: the bounds themselves are accepted, and createController refuses at creation", () => {
  for (const ok of [ZMIN, 1, openFrameCap(normalizeOptions({}))]) assert.doesNotThrow(() => normalizeOptions({ zoom: { frameMin: ok } }));
  assert.throws(() => createController({ roots: [], zoom: { frameMin: 5 } }, recordingView()), isErr);
});

/* ---- F2 the floor on open framing ---- */
function assertFramedAtOne(ctl, id) {
  const n = ctl.node(id), c = ctl.camera();
  assert.equal(c.k, 1);
  assert.equal(c.ty + c.k * n.y, PADO, "the node's top sits at framePadOpen from the viewport top");
  assert.equal(c.tx, (VP.w - n.w * c.k) / 2 - n.x * c.k, "centred horizontally");
}
test("F2 control: without frameMin a tall opened node is framed below 1 (so the floor has something to do)", async () => {
  const { ctl } = await start(undefined);
  await ctl.open("p"); await ctl.reveal(["p"]);
  const n = ctl.node("p");
  assert.ok(Math.min((VP.w - 2 * PADO) / n.w, (VP.h - 2 * PADO) / n.h) < 1, "natural frame scale below 1");
  assert.ok(ctl.camera().k < 1);
});
test("F2 route 1, the page's route: open(id) then reveal(path) of the opened node", async () => {
  const { ctl } = await start({ frameMin: 1 });
  assert.equal(await ctl.open("p"), true);
  assert.equal(await ctl.reveal(["p"]), true);
  assertFramedAtOne(ctl, "p");
});
test("F2 route 2, reveal / deep link through an opened node: reveal(['p','c3']) opens p and frames c3 (a closed leaf: zoom.min floor)", async () => {
  const { ctl } = await start({ frameMin: 1 });
  await ctl.reveal(["p", "c3"]);
  assert.ok(ctl.node("p").open);
  assert.deepEqual(ctl.camera(), frozenFrameNode(normalizeOptions({ zoom: { frameMin: 1 } }), VP, ctl.node("c3")));
});
test("F2 route 2b, reveal of a node that is already open frames it with the open floor", async () => {
  const { ctl } = await start({ frameMin: 1 });
  await ctl.reveal(["p", "c3"]);
  await ctl.reveal(["p"]);
  assertFramedAtOne(ctl, "p");
});
test("F2 route 3, semantic open: zooming in on a closed node opens it and frames it with the open floor", async () => {
  const { ctl } = await start({ frameMin: 1 });
  const n = ctl.node("p"), c0 = ctl.camera();
  ctl.zoomAt(c0.tx + (n.x + n.w / 2) * c0.k, c0.ty + (n.y + n.h / 2) * c0.k, 1.5, true);   // wide enough to open
  await tick(); await tick();
  assert.ok(ctl.node("p").open, "the semantic zoom opened it");
  assertFramedAtOne(ctl, "p");
});

/* ---- F3 closed framing unchanged ---- */
test("F3: framing a CLOSED node keeps floor zoom.min whatever frameMin is", async () => {
  for (const fm of [undefined, 1, openFrameCap(normalizeOptions({}))]) {
    const zoom = fm === undefined ? undefined : { frameMin: fm };
    const { ctl } = await start(zoom);
    await ctl.reveal(["q"]);
    const n = ctl.node("q");
    assert.equal(n.open, false);
    assert.deepEqual(ctl.camera(), frozenFrameNode(normalizeOptions({ zoom }), VP, n));
  }
  // a tiny viewport, so the closed frame goes below 1 if the open floor leaks into it
  const { ctl } = await start({ frameMin: 1 }, { w: 120, h: 120 });
  await ctl.reveal(["q"]);
  assert.ok(ctl.camera().k < 1, "closed framing went below frameMin: " + ctl.camera().k);
});

/* ---- F4 default is today ---- */
test("F4: with frameMin absent, every frameNode camera equals the frozen eec53ed9 arithmetic on generated trees (k, tx, ty exact)", async () => {
  for (const [fanout, total, vp] of [[5, 200, VP], [8, 500, { w: 1280, h: 800 }], [3, 80, { w: 320, h: 480 }]]) {
    const g = generated({ fanout, total }), view = recordingView(vp);
    const ctl = createController({ roots: g.roots, loadChildren: g.loader }, view);
    await ctl.ready;
    const o = normalizeOptions({});
    let checked = 0, opened = 0;
    for (const i of [0, 1, 2, 3, 6, 7, 11, 17, 30, 40]) {
      if (i >= total) continue;
      await ctl.reveal(g.pathOf(i));
      assert.deepEqual(ctl.camera(), frozenFrameNode(o, vp, ctl.node("n" + i)), "n" + i + " fanout " + fanout);
      checked++;
    }
    for (const i of [0, 1, 2]) {                 // the page's route: open, then reveal the opened node
      await ctl.open("n" + i); await ctl.reveal(g.pathOf(i));
      const n = ctl.node("n" + i);
      assert.equal(n.open, true);
      assert.deepEqual(ctl.camera(), frozenFrameNode(o, vp, n));
      opened++;
    }
    assert.ok(checked >= 5 && opened === 3, "the sweep exercised both: " + checked + "/" + opened);
  }
});

/* ---- F5 fit and the reader's zoom untouched ---- */
test("F5: fit() keeps zoom.min and the start fit keeps fitMin, whatever frameMin is", async () => {
  const sm = { w: 200, h: 200 };          // small, so the natural fit of the drawing is below 1 and below nothing but zoom.min
  const { ctl } = await start({ frameMin: 1, fitMin: 0.5 }, sm);
  const w = ctl.world();
  assert.ok(Math.min((sm.w - 40) / w.w, (sm.h - 40) / w.h) < 0.5, "the drawing's natural fit is below fitMin");
  assert.deepEqual(ctl.camera(), frozenFrame(sm, 0, 0, w.w, w.h, 1.1, 20, 0.5), "start fit: fitMin");
  ctl.fit();
  assert.deepEqual(ctl.camera(), frozenFrame(sm, 0, 0, w.w, w.h, 1.1, 20, ZMIN), "fit(): zoom.min");
  assert.ok(ctl.camera().k < 0.5);
});
test("F5: fit() goes below frameMin when the drawing needs it", async () => {
  const { ctl } = await start({ frameMin: 1 }, { w: 800, h: 100 });
  ctl.fit();
  assert.ok(ctl.camera().k < 1, "fit goes below frameMin: " + ctl.camera().k);
});
test("F5: the reader's own zoom-out goes below frameMin, down to zoom.min", async () => {
  const { ctl } = await start({ frameMin: 1 });
  ctl.zoomAt(100, 100, 1e-6, true);
  assert.equal(ctl.camera().k, ZMIN);
});
