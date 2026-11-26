// PR 93 fold 2 (peer suggestions S1, S2). S2: the open-framing cap respects zoom.max. S1: an invalid semantic set is blamed
// on semantic.openPx, not on frameMin (resolveFrameMin runs after the semantic check).
import { test } from "node:test";
import assert from "node:assert/strict";
import { createController } from "../controller.js";
import { normalizeOptions, openFrameCap } from "../options.js";
import { recordingView, tiny } from "./helpers.mjs";

const ZM = { max: 1.0, frameMaxOpen: 1.25 };

test("S2: zoom.max 1.0 with frameMaxOpen 1.25 gives openFrameCap 1.0", () => {
  assert.equal(openFrameCap(normalizeOptions({ zoom: ZM })), 1.0);
});
test("S2: with zoom.max 1.0, frameMin 1.1 is refused at creation and frameMin 1.0 is accepted", () => {
  const isCapErr = (e) => e instanceof TypeError && /zoom\.frameMin/.test(e.message) && /open-framing cap/.test(e.message);
  assert.throws(() => normalizeOptions({ zoom: { ...ZM, frameMin: 1.1 } }), isCapErr);
  assert.throws(() => createController({ roots: [], zoom: { ...ZM, frameMin: 1.1 } }, recordingView()), isCapErr);
  assert.equal(normalizeOptions({ zoom: { ...ZM, frameMin: 1.0 } }).zoom.frameMin, 1.0);
});
test("S2: framing an opened node never yields k above zoom.max (with and without frameMin)", async () => {
  const defs = [{ id: "p", kids: Array.from({ length: 12 }, (_, i) => "c" + i) }, ...Array.from({ length: 12 }, (_, i) => ({ id: "c" + i }))];
  for (const frameMin of [undefined, 1.0]) {
    const t = tiny(defs), view = recordingView({ w: 2000, h: 5000 });
    const ctl = createController({ roots: t.roots, loadChildren: t.loader, zoom: { ...ZM, frameMin }, layout: { siblings: "column" } }, view);
    await ctl.ready;
    await ctl.open("p"); await ctl.reveal(["p"]);
    assert.ok(ctl.camera().k <= 1.0, "k " + ctl.camera().k + " exceeds zoom.max 1.0");
    assert.equal(ctl.camera().k, 1.0);
  }
});
test("S2: default options keep the cap at 1.2", () => assert.equal(openFrameCap(normalizeOptions({})), 1.2));
test("S1: openPx 100, closePx 200, frameMin 1 blames semantic.openPx, not frameMin", () => {
  assert.throws(() => normalizeOptions({ semantic: { openPx: 100, closePx: 200 }, zoom: { frameMin: 1 } }),
    (e) => e instanceof TypeError && /semantic\.openPx/.test(e.message) && !/frameMin/.test(e.message));
});
