/* Data v3 (DATA-CONTRACT-v1 sections 15, 20, 22, 24): the keys the Lean map carries and the live map does not.
   D1 sibling_layout, D2 open_scale_floor, D3 link flags (weight, in_reduction) and their drawing, D4 file-step rows
   (index_rows, spine_rows). Written before the implementation. The live map (no v3 key) must validate and draw as before. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createData, DataError, validateIndex, validateStep, OPTIONAL_STRINGS } from "../data.js";

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");
const read = (dir, ...p) => JSON.parse(readFileSync(path.join(FIX, dir, ...p), "utf8"));
const skIndex = () => read("skeleton", "index.json");
const skStep = (id) => read("skeleton", "step", id + ".json");
const realIndex = () => read("real", "index.json");
const realStep = (id) => read("real", "step", id + ".json");
const clone = (o) => JSON.parse(JSON.stringify(o));

function dirFetch(dir) {
  return async (url) => {
    const p = path.join(dir, url);
    if (!existsSync(p)) return { ok: false, status: 404, json: async () => { throw new SyntaxError("no body"); } };
    const text = readFileSync(p, "utf8");
    return { ok: true, status: 200, json: async () => JSON.parse(text) };
  };
}
const refuses = (fn, code, mention) => assert.throws(fn, (e) => {
  assert.ok(e instanceof DataError, "not a DataError: " + e);
  assert.equal(e.code, code);
  if (mention !== undefined) assert.ok(e.reason.includes(mention), "the reason " + JSON.stringify(e.reason) + " does not name " + mention);
  return true;
});

/* ---------------------------------------------------------------------------------------------- D1 sibling_layout */

test("D1 the skeleton index carries sibling_layout column and the record says so", () => {
  const idx = skIndex();
  assert.equal(idx.sibling_layout, "column");
  assert.equal(validateIndex(idx).siblingLayout, "column");
});

test("D1 absent: the record has no siblingLayout key at all (the live map is unchanged)", () => {
  const v = validateIndex(realIndex());
  assert.equal(Object.prototype.hasOwnProperty.call(v, "siblingLayout"), false);
});

test("D1 the only allowed value is column: null, empty, rows, 1, a list, an object are bad-layout naming the value", () => {
  for (const [val, text] of [[null, "null"], ["", '""'], ["rows", "rows"], [1, "1"], [["column"], "column"], [{}, "{}"], [true, "true"], ["Column", "Column"]]) {
    const b = skIndex();
    b.sibling_layout = val;
    refuses(() => validateIndex(b), "bad-layout", text);
  }
});

/* ---------------------------------------------------------------------------------------------- D2 open_scale_floor */

test("D2 the skeleton index carries open_scale_floor 1 and the record says so; a fraction is fine", () => {
  const idx = skIndex();
  assert.equal(idx.open_scale_floor, 1);
  assert.equal(validateIndex(idx).openScaleFloor, 1);
  idx.open_scale_floor = 0.5;
  assert.equal(validateIndex(idx).openScaleFloor, 0.5);
});

test("D2 absent: the record has no openScaleFloor key at all", () => {
  assert.equal(Object.prototype.hasOwnProperty.call(validateIndex(realIndex()), "openScaleFloor"), false);
});

test("D2 a finite number above 0, else bad-scale-floor naming the value (0, -1, a string, null, a list, true; NaN is not JSON)", () => {
  for (const [val, text] of [[0, "0"], [-1, "-1"], ["1", '"1"'], [null, "null"], [[1], "1"], [true, "true"], ["NaN", "NaN"], ["", '""']]) {
    const b = skIndex();
    b.open_scale_floor = val;
    refuses(() => validateIndex(b), "bad-scale-floor", text);
  }
});

/* ---------------------------------------------------------------------------------------------- D3 link flags */

const linkAt = (step, i = 0) => step.rests_on[i];

test("D3 a step link with both flags validates and keeps weight and in_reduction on the record", () => {
  const v = validateIndex(skIndex());
  const st = validateStep(skStep("sk-group-a"), v);
  assert.equal(st.rests_on.length, 3);
  assert.deepEqual(st.rests_on.map((l) => [l.from, l.to, l.weight, l.in_reduction]),
    [["sk-file-1", "sk-file-2", 3, true], ["sk-file-2", "sk-file-3", 1, true], ["sk-file-1", "sk-file-3", 2, false]]);
});

test("D3 a link with neither flag validates (the live map's four keys)", () => {
  const v = validateIndex(realIndex());
  const st = validateStep(realStep("goal-chain"), v);
  assert.ok(st.rests_on.length > 0);
  for (const l of st.rests_on) {
    assert.deepEqual(Object.keys(l).sort(), ["from", "from_path", "to", "to_path"]);
  }
});

test("D3 both or neither: weight alone and in_reduction alone are bad-link-flags (step link and index link)", () => {
  const v = validateIndex(skIndex());
  for (const drop of ["weight", "in_reduction"]) {
    const s = skStep("sk-group-a");
    delete linkAt(s)[drop];
    refuses(() => validateStep(s, v), "bad-link-flags");
  }
  const idx = realIndex();
  idx.rests_on[0].weight = 2;
  refuses(() => validateIndex(idx), "bad-link-flags");
});

test("D3 weight is a positive integer, in_reduction a boolean: 0, -1, 1.5, a string, null, true; 'yes', 1, null, 0", () => {
  const v = validateIndex(skIndex());
  for (const w of [0, -1, 1.5, "2", null, true, [2]]) {
    const s = skStep("sk-group-a");
    linkAt(s).weight = w;
    refuses(() => validateStep(s, v), "bad-link-flags");
  }
  for (const r of ["yes", "true", 1, 0, null, [true]]) {
    const s = skStep("sk-group-a");
    linkAt(s).in_reduction = r;
    refuses(() => validateStep(s, v), "bad-link-flags");
  }
});

test("D3 a link with the flags still has to be a sibling link (the path rule is unchanged); an unknown key is still extra-key", () => {
  const v = validateIndex(skIndex());
  const s = skStep("sk-group-a");
  linkAt(s).to = "sk-file-1";            // from sk-file-1 to itself
  refuses(() => validateStep(s, v), "bad-link");
  const t = skStep("sk-group-a");
  linkAt(t).claim = "x";
  refuses(() => validateStep(t, v), "extra-key");
});

test("D3 DRAWING: in_reduction false is not passed to the engine; a->b and b->c are, a->c is not", async () => {
  const d = createData(dirFetch(path.join(FIX, "skeleton")));
  const files = await d.loadChildren("sk-group-a");
  const by = Object.fromEntries(files.map((f) => [f.id, f]));
  assert.deepEqual(by["sk-file-1"].links.map((l) => l.to), ["sk-file-2"], "a->b is drawn, a->c (false) is not");
  assert.deepEqual(by["sk-file-2"].links.map((l) => l.to), ["sk-file-3"], "b->c is drawn");
  assert.deepEqual(by["sk-file-3"].links, []);
  assert.equal(files.reduce((n, f) => n + f.links.length, 0), 2);
  for (const f of files) for (const l of f.links) assert.deepEqual(Object.keys(l).sort(), ["to", "toPath"], "the engine's link shape is unchanged");
});

test("D3 DRAWING: true flags and absent flags are drawn; the live map draws all of its links as before", async () => {
  const d = createData(dirFetch(path.join(FIX, "real")));
  await d.loadIndex();
  const roots = await d.loadRoots();
  assert.equal(roots.reduce((n, r) => n + r.links.length, 0), 2);
  const kids = await d.loadChildren("goal-chain");
  assert.equal(kids.reduce((n, k) => n + k.links.length, 0), 3);
});

/* ---------------------------------------------------------------------------------------------- D4 file-step rows */

test("D4 the two skeleton file steps carry index_rows and spine_rows and the step record keeps them; the others have neither key", () => {
  const v = validateIndex(skIndex());
  const one = validateStep(skStep("sk-file-1"), v);
  assert.deepEqual(one.index_rows, [{ source: "grh/INDEX.md", text: "The first file: the definitions the later files rest on." }]);
  assert.deepEqual(one.spine_rows, ["spine-theorem-a"]);
  const four = validateStep(skStep("sk-file-4"), v);
  assert.equal(four.index_rows.length, 2);
  assert.deepEqual(four.spine_rows, ["spine-theorem-b", "spine-theorem-c"]);
  const other = validateStep(skStep("sk-file-2"), v);
  assert.equal(Object.prototype.hasOwnProperty.call(other, "index_rows"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(other, "spine_rows"), false);
});

test("D4 index_rows malformed: empty list, not a list, a row that is not {source, text}, a wrong source, an empty or long text", () => {
  const v = validateIndex(skIndex());
  const row = { source: "grh/INDEX.md", text: "a sentence" };
  const bad = [[], "rows", null, {}, [null], ["a sentence"], [{ source: "grh/INDEX.md" }], [{ text: "a" }], [{ ...row, extra: 1 }],
    [{ source: "grh/index.md", text: "a" }], [{ source: "", text: "a" }], [{ source: 1, text: "a" }], [{ source: "grh/INDEX.md", text: "" }],
    [{ source: "grh/INDEX.md", text: 5 }], [{ source: "grh/INDEX.md", text: "x".repeat(4001) }], [row, { source: "grh/INDEX.md", text: "" }]];
  for (const b of bad) {
    const s = skStep("sk-file-1");
    s.index_rows = b;
    refuses(() => validateStep(s, v), "bad-index-rows");
  }
  const ok = skStep("sk-file-1");
  ok.index_rows = [{ source: "grh/INDEX.md", text: "x".repeat(4000) }];
  assert.equal(validateStep(ok, v).index_rows[0].text.length, 4000, "4000 characters is the bound, and it is allowed");
});

test("D4 spine_rows malformed: empty list, not a list, a non-string, a bad pattern, a repeat", () => {
  const v = validateIndex(skIndex());
  const bad = [[], "spine-a", null, {}, [1], [null], ["spine-"], ["spine-A"], ["spine_a"], ["spine-a b"], ["Spine-a"], ["spine-a\n"], ["x-spine-a"], [""],
    ["spine-a", "spine-a"], ["spine-a", "bad"]];
  for (const b of bad) {
    const s = skStep("sk-file-1");
    s.spine_rows = b;
    refuses(() => validateStep(s, v), "bad-spine-rows");
  }
  const ok = skStep("sk-file-1");
  ok.spine_rows = ["spine-a", "spine-b-2", "spine-0"];
  assert.deepEqual(validateStep(ok, v).spine_rows, ["spine-a", "spine-b-2", "spine-0"]);
});

test("D4 the rows are carried, never drawn: the node handed to the engine has no rows and no flag", async () => {
  const d = createData(dirFetch(path.join(FIX, "skeleton")));
  await d.loadIndex();
  const kids = await d.loadChildren("sk-group-a");
  for (const k of kids) {
    for (const key of Object.keys(k)) assert.ok(["id", "childCount", "links", "parentLinksTo", "path", "data"].includes(key), key);
    for (const key of Object.keys(k.data)) assert.ok(["title", "kind", "state", "childKind"].includes(key), key);
  }
  const step = await d.loadStep("sk-file-4");
  assert.equal(step.index_rows.length, 2);
});

/* ---------------------------------------------------------------------------------------------- what stays refused */

test("not in this PR: note on a step stays refused (extra-key); spine_lines_text stays refused (extra-string), with or without edge_basis", () => {
  const v = validateIndex(skIndex());
  const s = skStep("sk-file-1");
  s.note = "a note";
  refuses(() => validateStep(s, v), "extra-key");
  const b = skIndex();
  b.strings.spine_lines_text = "A line means the upper result rests on the lower one.";
  refuses(() => validateIndex(b), "extra-string", "spine_lines_text");
  const c = skIndex();
  delete c.edge_basis;
  delete c.strings.key_lines_heading;
  delete c.strings.key_lines_text;
  c.strings.spine_lines_text = "x";
  refuses(() => validateIndex(c), "extra-string", "spine_lines_text");
});

/* ---------------------------------------------------------------------------------- PR 98 round 2: E1, E2, E3, K1, S1 */

const BASIS = "names-written-in-source-from-compiled-index";

test("E1 the skeleton's edge_basis validates and the record carries {basis, words}; the live map's record has no such key", () => {
  const v = validateIndex(skIndex());
  assert.deepEqual(v.edgeBasis, { basis: BASIS, words: "key_lines_text" });
  assert.ok(!("edgeBasis" in validateIndex(realIndex())));
});

test("E1 a basis value other than the one this page knows is bad-edge-basis and the reason names it", () => {
  for (const bad of ["names-written-in-source", "", "Names-Written-In-Source-From-Compiled-Index", 7, null]) {
    const idx = skIndex();
    idx.edge_basis.basis = bad;
    refuses(() => validateIndex(idx), "bad-edge-basis", typeof bad === "string" && bad !== "" ? bad : "basis");
  }
});

test("E1 words must be a non-empty string naming a key PRESENT in strings (else bad-edge-basis)", () => {
  for (const bad of ["no_such_key", "", 7, null, ["key_lines_text"]]) {
    const idx = skIndex();
    idx.edge_basis.words = bad;
    refuses(() => validateIndex(idx), "bad-edge-basis");
  }
});

test("E1 any other shape of edge_basis is bad-edge-basis: null, a string, a list, a number, an extra key, a missing key, an empty object", () => {
  const shapes = [null, "key_lines_text", ["a"], 7, true, { basis: BASIS, words: "key_lines_text", more: 1 }, { basis: BASIS }, { words: "key_lines_text" }, {}];
  for (const bad of shapes) {
    const idx = skIndex();
    idx.edge_basis = bad;
    refuses(() => validateIndex(idx), "bad-edge-basis");
  }
});

test("E2 with edge_basis, key_lines_heading is REQUIRED: absent is missing-string, empty is empty-string", () => {
  const a = skIndex();
  delete a.strings.key_lines_heading;
  refuses(() => validateIndex(a), "missing-string", "key_lines_heading");
  const e = skIndex();
  e.strings.key_lines_heading = "";
  refuses(() => validateIndex(e), "empty-string", "key_lines_heading");
});

test("E2 with edge_basis, the strings key it names is REQUIRED non-empty (empty is empty-string); an absent one is bad-edge-basis (E1)", () => {
  const e = skIndex();
  e.strings.key_lines_text = "";
  refuses(() => validateIndex(e), "empty-string", "key_lines_text");
  const a = skIndex();
  delete a.strings.key_lines_text;
  refuses(() => validateIndex(a), "bad-edge-basis");
});

test("E2 without edge_basis, key_lines_heading and key_lines_text are not read: each present is extra-string", () => {
  const base = () => { const i = skIndex(); delete i.edge_basis; return i; };
  const both = base();
  refuses(() => validateIndex(both), "extra-string");
  const onlyHeading = base();
  delete onlyHeading.strings.key_lines_text;
  refuses(() => validateIndex(onlyHeading), "extra-string", "key_lines_heading");
  const onlyText = base();
  delete onlyText.strings.key_lines_heading;
  refuses(() => validateIndex(onlyText), "extra-string", "key_lines_text");
  const none = base();
  delete none.strings.key_lines_heading;
  delete none.strings.key_lines_text;
  validateIndex(none);
  for (const k of ["key_lines_heading", "key_lines_text"]) assert.ok(!OPTIONAL_STRINGS.includes(k), k + " is never unconditionally optional");
});

test("E2 the set follows edge_basis.words: words naming another key reads THAT key, and key_lines_text is then not read (extra-string)", () => {
  const idx = skIndex();
  idx.strings.test_words = "A test paragraph";
  idx.edge_basis.words = "test_words";
  refuses(() => validateIndex(idx), "extra-string", "key_lines_text");
  delete idx.strings.key_lines_text;
  const v = validateIndex(idx);
  assert.equal(v.edgeBasis.words, "test_words");
});

test("K1 key_scope_text is an OPTIONAL strings key: in OPTIONAL_STRINGS, accepted absent, accepted present on the live map, empty is empty-string", () => {
  assert.ok(OPTIONAL_STRINGS.includes("key_scope_text"));
  const a = skIndex();
  delete a.strings.key_scope_text;
  validateIndex(a);
  const e = skIndex();
  e.strings.key_scope_text = "";
  refuses(() => validateIndex(e), "empty-string", "key_scope_text");
  const live = realIndex();
  live.strings.key_scope_text = "A scope paragraph";
  validateIndex(live);
});

test("S1 error order on a link: an unknown key beside a bad flag is extra-key; one flag with a non-integer weight is bad-link-flags", () => {
  const both = skStep("sk-group-a");
  both.rests_on[0].bogus = 1;
  both.rests_on[0].weight = 1.5;
  both.rests_on[0].in_reduction = "yes";
  refuses(() => validateStep(both, validateIndex(skIndex())), "extra-key");
  const one = skStep("sk-group-a");
  delete one.rests_on[0].in_reduction;
  one.rests_on[0].weight = 1.5;
  refuses(() => validateStep(one, validateIndex(skIndex())), "bad-link-flags");
});

test("the v3 keys do not leak into the live map's record: its index and step records carry exactly the keys they carried", () => {
  const v = validateIndex(realIndex());
  assert.deepEqual(Object.keys(v).sort(), ["assets", "commit", "maxChildren", "rests", "steps", "strings", "symbols", "top"]);
  assert.deepEqual(Object.keys(validateStep(realStep("goal-chain"), v)).sort(), ["card", "children", "id", "path", "rests_on"]);
});
