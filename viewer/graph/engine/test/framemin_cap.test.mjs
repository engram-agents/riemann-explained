// zoom.frameMin may not exceed the open-framing cap (PR 93 fold 1). camera.frame() clamps as max(kmin, min(kmax, k)), so a
// floor above kmax would win silently and put closed children at or above openPx on screen. G1 one definition, G2 refusal.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createController } from "../controller.js";
import * as optionsModule from "../options.js";
import { normalizeOptions } from "../options.js";
import { recordingView, tiny } from "./helpers.mjs";

const isCapErr = (e) => e instanceof TypeError && /zoom\.frameMin/.test(e.message) && /open-framing cap/.test(e.message);

test("G1: options.js exports openFrameCap, and it is the documented expression of the three inputs", () => {
  assert.equal(typeof optionsModule.openFrameCap, "function");
  const o = normalizeOptions({});
  assert.equal(optionsModule.openFrameCap(o), Math.min(o.zoom.frameMaxOpen, o.semantic.frameOpenShare * o.semantic.openPx / o.sizes.nodeW));
  assert.equal(optionsModule.openFrameCap(o), 1.2);
  assert.ok(Math.abs(optionsModule.openFrameCap(normalizeOptions({ sizes: { nodeW: 350 } })) - 360 / 350) < 1e-12, "nodeW 350 gives about 1.029");
});
test("G1: controller.js carries no inline copy of the open cap (it calls openFrameCap)", () => {
  const src = readFileSync(new URL("../controller.js", import.meta.url), "utf8");
  assert.match(src, /openFrameCap\(/);
  assert.doesNotMatch(src, /frameOpenShare/, "the open expression lives only in options.js");
});
test("G2: default sizes with frameMin 1.25 is refused (cap 1.2), message names zoom.frameMin and the open-framing cap", () => {
  assert.throws(() => normalizeOptions({ zoom: { frameMin: 1.25 } }), isCapErr);
  assert.throws(() => createController({ roots: [], zoom: { frameMin: 1.25 } }, recordingView()), isCapErr);
});
test("G2: sizes.nodeW 350 with frameMin 1.2 is refused", () => {
  assert.throws(() => normalizeOptions({ sizes: { nodeW: 350 }, zoom: { frameMin: 1.2 } }), isCapErr);
});
test("G2: frameMin exactly equal to the cap is accepted (the function's own value)", () => {
  const cap = optionsModule.openFrameCap(normalizeOptions({}));
  assert.equal(normalizeOptions({ zoom: { frameMin: cap } }).zoom.frameMin, cap);
  const cap350 = optionsModule.openFrameCap(normalizeOptions({ sizes: { nodeW: 350 } }));
  assert.doesNotThrow(() => normalizeOptions({ sizes: { nodeW: 350 }, zoom: { frameMin: cap350 } }));
});
test("G2: frameMin 1 with default sizes is accepted", () => assert.equal(normalizeOptions({ zoom: { frameMin: 1 } }).zoom.frameMin, 1));
test("G1 behaviour: an opened node framed in a roomy viewport lands exactly at openFrameCap (the cap binds), with and without frameMin", async () => {
  const defs = [{ id: "p", kids: Array.from({ length: 12 }, (_, i) => "c" + i) }, ...Array.from({ length: 12 }, (_, i) => ({ id: "c" + i }))];
  for (const zoom of [undefined, { frameMin: 1 }]) {
    const t = tiny(defs), view = recordingView({ w: 2000, h: 5000 });
    const ctl = createController({ roots: t.roots, loadChildren: t.loader, zoom, layout: { siblings: "column" } }, view);
    await ctl.ready;
    await ctl.open("p"); await ctl.reveal(["p"]);
    assert.equal(ctl.camera().k, optionsModule.openFrameCap(normalizeOptions({ zoom })));
  }
});
test("G2: lower bound and null rule unchanged", () => {
  assert.throws(() => normalizeOptions({ zoom: { frameMin: 0.01 } }), (e) => e instanceof TypeError && /zoom\.frameMin/.test(e.message));
  assert.equal(normalizeOptions({ zoom: { frameMin: null } }).zoom.frameMin, 0.06);
});
