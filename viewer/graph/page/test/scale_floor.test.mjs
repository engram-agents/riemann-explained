/* PR 98 round 4: the scale floor is checked by the ENGINE's own rule, named. The page runs the engine's `checkOptions` on the exact options it is
   about to pass to createGraph; when that throws and the index carries open_scale_floor, a second run WITHOUT zoom.frameMin says whether the
   floor is the cause (then DataError bad-scale-floor naming the value) or something else is (then the engine's own TypeError goes on).
   F2/F3 (the page's helper, `checkedOptions` in data.js, with the real engine's checkOptions), F4 (the both-or-neither message is reachable).
   Written before the implementation. The browser cases for the same contract are in test_page_browser.py. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import * as DATA from "../data.js";
import * as ENGINE from "../../engine/index.js";

const { DataError, validateIndex, validateStep } = DATA;
const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");
const read = (dir, ...p) => JSON.parse(readFileSync(path.join(FIX, dir, ...p), "utf8"));
const APP = readFileSync(path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "app.js"), "utf8");

/* The options as app.js builds them for a map: the card sizes, fitMin 1, and the floor as frameMin when the index has one. */
const optionsFor = (floor, extra = {}) => ({
  roots: [], maxChildren: 40, sizes: { nodeH: 140, gapY: 56, ...(extra.sizes || {}) },
  zoom: { fitMin: 1, ...(floor !== undefined ? { frameMin: floor } : {}) },
  loadChildren: () => Promise.resolve([]), renderFace: () => null,
});
const helper = () => { assert.equal(typeof DATA.checkedOptions, "function", "data.js exports checkedOptions"); return DATA.checkedOptions; };
const check = ENGINE.checkOptions;

test("F2 the engine's checkOptions is there for the page (the one source of the bound)", () => assert.equal(typeof check, "function"));

test("F3 an open_scale_floor below zoom.min (0.01, 0.05) is bad-scale-floor naming the value", () => {
  for (const f of [0.01, 0.05]) {
    assert.throws(() => helper()(check, optionsFor(f), f), (e) => e instanceof DataError && e.code === "bad-scale-floor" && e.reason.includes(String(f)), String(f));
  }
});

test("F3 an open_scale_floor above the engine's open-framing cap (1.3, 2) is bad-scale-floor naming the value", () => {
  for (const f of [1.3, 2]) {
    assert.throws(() => helper()(check, optionsFor(f), f), (e) => e instanceof DataError && e.code === "bad-scale-floor" && e.reason.includes(String(f)), String(f));
  }
});

test("F3 control: a floor inside the engine's range (1, 0.5, the cap itself 1.2) passes, and so does no floor at all", () => {
  for (const f of [1, 0.5, 1.2, 0.06]) assert.doesNotThrow(() => helper()(check, optionsFor(f), f), String(f));
  assert.doesNotThrow(() => helper()(check, optionsFor(undefined), undefined));
});

test("F2 the second check: a VALID floor beside ANOTHER bad option is the engine's own TypeError, not bad-scale-floor", () => {
  assert.throws(() => helper()(check, optionsFor(1, { sizes: { nodeH: -1 } }), 1), (e) => e instanceof TypeError && !(e instanceof DataError) && /sizes\.nodeH/.test(e.message));
});

test("F2 a BAD floor beside another bad option: the floor is not the only cause, so the engine's TypeError goes on", () => {
  assert.throws(() => helper()(check, optionsFor(2, { sizes: { nodeH: -1 } }), 2), (e) => e instanceof TypeError && !(e instanceof DataError) && /sizes\.nodeH/.test(e.message));
});

test("F2 no open_scale_floor: a bad option is the engine's own TypeError exactly as today", () => {
  assert.throws(() => helper()(check, optionsFor(undefined, { sizes: { nodeH: -1 } }), undefined), (e) => e instanceof TypeError && !(e instanceof DataError));
});

test("F2 no engine message is parsed: a checker that throws a message of its own on the floor still gives bad-scale-floor, and one that passes without the floor decides", () => {
  const onlyFloor = (o) => { if (o.zoom.frameMin !== undefined) throw new TypeError("something unrecognisable"); };
  assert.throws(() => helper()(onlyFloor, optionsFor(1), 1), (e) => e instanceof DataError && e.code === "bad-scale-floor");
  const always = () => { throw new TypeError("zoom.frameMin must be a number"); };
  assert.throws(() => helper()(always, optionsFor(1), 1), (e) => e instanceof TypeError && !(e instanceof DataError));
});

test("F2 the second run is on the SAME options without zoom.frameMin only (the other zoom keys stay, the caller's object is not changed)", () => {
  const seen = [];
  const spy = (o) => { seen.push(JSON.stringify(o.zoom)); if (o.zoom.frameMin !== undefined) throw new TypeError("x"); };
  const opts = optionsFor(1);
  assert.throws(() => helper()(spy, opts, 1), DataError);
  assert.deepEqual(seen, ['{"fitMin":1,"frameMin":1}', '{"fitMin":1}']);
  assert.equal(opts.zoom.frameMin, 1);
});

test("F2 app.js runs the check on the options it passes, before createGraph (the helper is called, then the engine)", () => {
  const i = APP.indexOf("checkedOptions(");
  assert.ok(i > 0, "app.js calls checkedOptions");
  assert.ok(i < APP.indexOf("deps.createGraph("), "the check comes before createGraph");
  assert.match(APP, /checkOptions/);
});

/* ---------------------------------------------------------------------------------------------- F4 both or neither */

test("F4 a lone weight and a lone in_reduction, valid or not, report 'both or neither' (the flag-pair message), never a type message", () => {
  const v = validateIndex(read("skeleton", "index.json"));
  for (const [k, val] of [["weight", 2], ["weight", 0], ["weight", "x"], ["in_reduction", true], ["in_reduction", "yes"], ["in_reduction", null]]) {
    const s = read("skeleton", "step", "sk-group-a.json");
    const l = s.rests_on[0];
    delete l.weight; delete l.in_reduction;
    l[k] = val;
    assert.throws(() => validateStep(s, v), (e) => e instanceof DataError && e.code === "bad-link-flags" && /one of weight and in_reduction without the other/.test(e.reason), k + "=" + JSON.stringify(val));
  }
});
