// zoom.fitMin: a lower bound on the scale of the START fit only. fit() keeps its meaning (the whole drawing, bounded
// below by zoom.min); the reader's own zoom is bounded only by zoom.min and zoom.max.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createController } from "../controller.js";
import { normalizeOptions, DEFAULTS } from "../options.js";
import { frame } from "../camera.js";
import { recordingView } from "./helpers.mjs";

const root = () => [{ id: "r", childCount: 0, links: [], parentLinksTo: false, path: ["r"], data: null }];
const PAD = 20, FITMAX = 1.1, ZMIN = 0.06;

async function start(zoom, size) {
  const view = recordingView(size);
  const ctl = createController({ roots: root(), zoom }, view);
  await ctl.ready;
  const w = ctl.world();
  return { ctl, view, w, cam: ctl.camera(), vp: view.viewport() };
}
const natural = (w, vp) => Math.min((vp.w - 2 * PAD) / w.w, (vp.h - 2 * PAD) / w.h);
const SHORT = { w: 800, h: 100 };       // a short strip: the natural fit of the one card is well below 1
const isFitMinError = (e) => e instanceof TypeError && /zoom\.fitMin/.test(e.message);

test("default unchanged: with no fitMin the start fit is the fit the engine always did (same k, tx, ty)", async () => {
  const { w, cam, vp } = await start(undefined, SHORT);
  assert.ok(natural(w, vp) < 1, "the drawing would fit below scale 1: " + natural(w, vp));
  assert.deepEqual(cam, frame(vp, 0, 0, w.w, w.h, FITMAX, PAD, ZMIN));
});

test("default fitMin is zoom.min as the caller set it, resolved after the merge", async () => {
  const a = await start({ min: 0.5 }, SHORT);
  assert.deepEqual(a.cam, frame(a.vp, 0, 0, a.w.w, a.w.h, FITMAX, PAD, 0.5));
  assert.equal(normalizeOptions({ zoom: { min: 0.5 } }).zoom.fitMin, 0.5);
  assert.equal(normalizeOptions({}).zoom.fitMin, ZMIN);
  assert.equal(DEFAULTS.zoom.fitMin, null, "DEFAULTS holds null; the resolution is on the caller's copy");
});

test("fitMin 1 on a tall drawing in a short viewport: start k is 1, top-anchored; unset gives k < 1", async () => {
  const un = await start(undefined, SHORT);
  assert.ok(un.cam.k < 1);
  const { w, cam, vp } = await start({ fitMin: 1 }, SHORT);
  assert.equal(cam.k, 1);
  assert.equal(cam.ty, PAD, "the top of the drawing sits at fitPad from the stage top");
  assert.ok(Math.abs(cam.tx - (vp.w - w.w) / 2) < 1e-9, "horizontally centred as today");
  assert.deepEqual(cam, frame(vp, 0, 0, w.w, w.h, FITMAX, PAD, 1));
});

test("fitMin 1, then handle.fit(): k < 1, the whole drawing (fit is not bounded by fitMin)", async () => {
  const { ctl, w, vp } = await start({ fitMin: 1 }, SHORT);
  assert.equal(ctl.camera().k, 1);
  ctl.fit();
  assert.ok(ctl.camera().k < 1);
  assert.deepEqual(ctl.camera(), frame(vp, 0, 0, w.w, w.h, FITMAX, PAD, ZMIN));
});

test("fitMin 1, then the reader's own zoom-out goes below 1, down to zoom.min", async () => {
  const { ctl } = await start({ fitMin: 1 }, SHORT);
  ctl.zoomAt(100, 50, 0.5, true);
  assert.equal(ctl.camera().k, 0.5);
  ctl.zoomAt(100, 50, 1e-6, true);
  assert.equal(ctl.camera().k, ZMIN);
});

test("fitMin is only a lower bound: a small drawing still fits at the natural scale, up to fitMax", async () => {
  const big = await start({ fitMin: 1 }, { w: 2000, h: 2000 });
  assert.equal(big.cam.k, FITMAX, "natural fit above fitMax is clamped at fitMax as today");
  const sz = { w: 600, h: 160 };
  const probe = await start(undefined, sz);
  const nat = natural(probe.w, probe.vp);
  assert.ok(nat > 0.3 && nat < 1, "a drawing whose natural fit lies between: " + nat);
  const mid = await start({ fitMin: 0.3 }, sz);
  assert.equal(mid.cam.k, nat);
});

test("validation: fitMin <= 0, below zoom.min, above fitMax, or not a number is a TypeError naming zoom.fitMin", () => {
  for (const bad of [0, -1, 0.01, 2, "1", NaN, Infinity])
    assert.throws(() => normalizeOptions({ zoom: { fitMin: bad } }), isFitMinError, "fitMin " + String(bad));
  assert.throws(() => normalizeOptions({ zoom: { min: 0.2, fitMin: 0.1 } }), isFitMinError);
  assert.throws(() => normalizeOptions({ zoom: { fitMax: 0.9, fitMin: 1 } }), isFitMinError);
  assert.throws(() => createController({ roots: root(), zoom: { fitMin: 5 } }, recordingView()), isFitMinError);
  for (const ok of [ZMIN, 1, FITMAX]) assert.doesNotThrow(() => normalizeOptions({ zoom: { fitMin: ok } }));
});

test("an existing caller whose zoom.min is above fitMax (no fitMin given) is not newly refused", () => {
  assert.doesNotThrow(() => normalizeOptions({ zoom: { min: 2, max: 3 } }));
});

test("clamped start fit, narrower than the stage: centred horizontally and top-anchored (deliberate; a wider-than-stage drawing would be cut on both sides, see INTERFACE)", async () => {
  const { w, cam, vp } = await start({ fitMin: 1 }, SHORT);
  assert.ok(w.w < vp.w && w.h > vp.h, "narrower than the stage, taller than it: " + JSON.stringify([w, vp]));
  assert.equal(cam.k, 1);
  assert.equal(cam.tx, (vp.w - w.w * cam.k) / 2 - 0 * cam.k, "centred: tx = (vp.w - w*k)/2 - x*k with x = 0");
  assert.equal(cam.ty, PAD, "top-anchored: ty = fitPad - y*k with y = 0");
});

test("after a fitMin 1 start, reveal() of a node frames it below scale 1, bounded by zoom.min", async () => {
  const kid = { id: "c", childCount: 0, links: [], parentLinksTo: false, path: ["p", "c"], data: null };
  const par = { id: "p", childCount: 1, links: [], parentLinksTo: false, path: ["p"], data: null };
  const view = recordingView(SHORT);
  const ctl = createController({ roots: [par], loadChildren: async () => [kid], zoom: { fitMin: 1 } }, view);
  await ctl.ready;
  assert.equal(ctl.camera().k, 1);
  assert.equal(await ctl.reveal(["p", "c"]), true);
  const k = ctl.camera().k;
  assert.ok(k < 1 && k >= ZMIN, "framed below 1, not below zoom.min: " + k);
});

test("an explicit null or undefined fitMin means not given: it resolves to zoom.min like an absent key", () => {
  for (const v of [null, undefined]) {
    assert.equal(normalizeOptions({ zoom: { fitMin: v } }).zoom.fitMin, ZMIN);
    assert.equal(normalizeOptions({ zoom: { min: 0.1, fitMin: v } }).zoom.fitMin, 0.1);
  }
});

test("CLASS: the documented defaults can be passed back (the whole DEFAULTS, and each option group of it)", () => {
  const o = normalizeOptions({ ...DEFAULTS, roots: [] });
  for (const k of Object.keys(DEFAULTS)) {
    if (k === "loadChildren") continue;                     // null by default, a function once normalised
    const want = k === "zoom" ? { ...DEFAULTS.zoom, fitMin: DEFAULTS.zoom.min, frameMin: DEFAULTS.zoom.min } : DEFAULTS[k];
    assert.deepEqual(o[k], want, "resolved " + k + " equals its default (fitMin and frameMin resolve to zoom.min)");
  }
  const groups = Object.keys(DEFAULTS).filter((k) => DEFAULTS[k] && typeof DEFAULTS[k] === "object" && !Array.isArray(DEFAULTS[k]));
  assert.ok(groups.includes("zoom") && groups.includes("sizes"), "the generated list has the known groups: " + groups);
  for (const g of groups) assert.doesNotThrow(() => normalizeOptions({ [g]: { ...DEFAULTS[g] } }), "group " + g + " passed back");
  assert.doesNotThrow(() => normalizeOptions({ zoom: { ...DEFAULTS.zoom, min: 0.1 } }));
});
