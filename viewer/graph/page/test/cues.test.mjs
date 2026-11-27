/* The reading cue (Lei, 11-27; Ariadne's reading-cues note v1, Kepler 40265; Sol's data contract section 33, 40266): the outlined tag on a box that has a reading, the count line on the boxes
   above it, the optional `reading_count` on a closed card and its checks, the four cue words, the Key sentence, the filled reading button. The fixture (fixtures/cues) is made up:
   the readings sample plus the four words and the counts. Part 1: the words, part 2: the card key and its sums, part 3: the face, part 4: a tree WITHOUT the count draws as today. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { DataError, validateIndex, validateStep, createData, CUE_STRINGS } from "../data.js";
import { makeRenderFace, cueText } from "../face.js";
import { buildStatement } from "../statement.js";
import { makeEl } from "../dom.js";
import { makeFakeDoc } from "./fakedoc.mjs";

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");
const read = (dir, ...p) => JSON.parse(readFileSync(path.join(FIX, dir, ...p), "utf8"));
const clone = (o) => JSON.parse(JSON.stringify(o));
const idx = () => read("cues", "index.json");
const stp = (id) => read("cues", "step", id + ".json");
const refuses = (fn, code, mention) => assert.throws(fn, (e) => {
  assert.ok(e instanceof DataError, "not a DataError: " + e);
  assert.equal(e.code, code);
  if (mention !== undefined) assert.ok(e.reason.includes(mention), "the reason " + JSON.stringify(e.reason) + " does not name " + mention);
  return true;
});
const ctx = () => { const v = validateIndex(idx()); return { commit: v.commit, strings: v.strings, symbols: v.symbols, ids: v.ids }; };
const fetchOf = (dir, edit) => async (address) => {
  const name = address.replace(/^step\//, "").replace(/\.json$/, "");
  let raw = address === "index.json" ? read(dir, "index.json") : read(dir, "step", name + ".json");
  if (edit) raw = edit(address, clone(raw)) || raw;
  return { ok: true, status: 200, json: async () => raw };
};

/* ------------------------------------------------------------------------------------------------ 1: the words */
test("the four cue words are the page's group; the fixture index validates with them", () => {
  assert.deepEqual([...CUE_STRINGS], ["face_reading_cue", "count_reading_one", "count_reading_many", "key_reading_cue_text"]);
  const v = validateIndex(idx());
  for (const k of CUE_STRINGS) assert.ok(typeof v.strings[k] === "string" && v.strings[k] !== "", k);
});

test("the cue words are all-or-none: any one missing or empty beside the others is bad-cue-strings naming it", () => {
  for (const k of CUE_STRINGS) {
    const a = idx(); delete a.strings[k];
    refuses(() => validateIndex(a), "bad-cue-strings", k);
    const b = idx(); b.strings[k] = "";
    refuses(() => validateIndex(b), "bad-cue-strings", k);
  }
});

test("count_reading_many must hold {n}", () => {
  const i = idx(); i.strings.count_reading_many = "many AI readings";
  refuses(() => validateIndex(i), "bad-cue-strings", "{n}");
});

test("cue words without the reading words are bad-cue-strings; the reading words alone (no cue words) validate", () => {
  const a = idx();
  for (const k of ["decl_reading_show", "decl_reading_hide", "decl_reading_about", "readings_byline"]) delete a.strings[k];
  refuses(() => validateIndex(a), "bad-cue-strings", "reading words");
  const b = idx(); for (const k of CUE_STRINGS) delete b.strings[k];
  validateIndex(b);
});

/* ------------------------------------------------------------------------------------------------ 2: reading_count */
test("the fixture's cards carry reading_count: the statement 1, the file, the group and the part 1; the statements without a reading and fx-file-2 none", () => {
  const c = ctx();
  assert.equal(validateStep(stp("fx-thm-a"), c).card.reading_count, 1);
  assert.equal(validateStep(stp("fx-stmt-file"), c).card.reading_count, 1);
  assert.equal(validateStep(stp("fx-group"), c).card.reading_count, 1);
  assert.equal(validateStep(stp("fx-part"), c).card.reading_count, 1);
  for (const id of ["fx-lem-b", "fx-def-c", "fx-file-2"]) assert.equal(validateStep(stp(id), c).card.reading_count, undefined, id);
  assert.equal(validateStep(stp("fx-stmt-file"), c).children.find((x) => x.id === "fx-thm-a").reading_count, 1);
});

test("reading_count: 0, a negative, a float, a string, a bool, null are bad-reading-count (absent is the way to say none)", () => {
  for (const v of [0, -1, 1.5, "1", true, false, null]) {
    const s = stp("fx-thm-a"); s.card.reading_count = v;
    refuses(() => validateStep(s, ctx()), "bad-reading-count", "step.card");
  }
});

test("a statement WITH a reading must carry reading_count 1 on its card; one WITHOUT must carry none", () => {
  const a = stp("fx-thm-a"); delete a.card.reading_count;
  refuses(() => validateStep(a, ctx()), "bad-reading-count", "fx-thm-a");
  const b = stp("fx-thm-a"); b.card.reading_count = 2;
  refuses(() => validateStep(b, ctx()), "bad-reading-count", "fx-thm-a");
  const c = stp("fx-lem-b"); c.card.reading_count = 1;
  refuses(() => validateStep(c, ctx()), "bad-reading-count", "fx-lem-b");
});

test("a card above statements: its reading_count must equal the SUM of its children entries' (absent = 0), whichever way it is wrong", () => {
  for (const edit of [(s) => { s.card.reading_count = 2; }, (s) => { delete s.card.reading_count; }, (s) => { s.children[0].reading_count = 3; },
                      (s) => { s.children[1].reading_count = 1; }]) {
    const s = stp("fx-stmt-file"); edit(s);
    refuses(() => validateStep(s, ctx()), "bad-reading-count", "fx-stmt-file");
  }
  const g = stp("fx-group"); g.children[1].reading_count = 1;                 // the other file claims a reading too: the group's own 1 is now wrong
  refuses(() => validateStep(g, ctx()), "bad-reading-count", "fx-group");
});

test("the counts are checked only where the cue words are: a map with readings and NO counts and NO cue words loads (the data before the cue); wrong sums without cue words are not refused", () => {
  const i = idx(); for (const k of CUE_STRINGS) delete i.strings[k];
  const v = validateIndex(i);
  const c = { commit: v.commit, strings: v.strings, symbols: v.symbols, ids: v.ids };
  const s = stp("fx-thm-a"); delete s.card.reading_count; validateStep(s, c);
  const f = stp("fx-stmt-file"); f.card.reading_count = 9; validateStep(f, c);
  const bad = stp("fx-thm-a"); bad.card.reading_count = 0;            // the SHAPE of a count is always checked
  refuses(() => validateStep(bad, c), "bad-reading-count", "step.card");
});

test("the sum of several readings: a file whose entries hold 2 and 1 is 3", () => {
  const s = stp("fx-stmt-file");
  s.children[0].reading_count = 2; s.children[1].reading_count = 1; s.card.reading_count = 3;
  validateStep(s, ctx());
});

test("createData: a parent's entry and the child's own card must say the same count, whichever is loaded first", async () => {
  const lie = (edit) => (addr, raw) => (addr === "step/fx-stmt-file.json" ? edit(raw) : raw);
  // the file's own card says 1; its entry in the group says 1: fine
  const ok = createData(fetchOf("cues"));
  await ok.loadStep("fx-group"); await ok.loadStep("fx-stmt-file");
  // the group lists the file with 1; the file's step says 2 (and its children sum to 2): the entry and the card disagree
  const two = createData(fetchOf("cues", (addr, raw) => {
    if (addr === "step/fx-stmt-file.json") { raw.card.reading_count = 2; raw.children[0].reading_count = 2; }
    return raw;
  }));
  await two.loadStep("fx-group");
  await assert.rejects(() => two.loadStep("fx-stmt-file"), (e) => e instanceof DataError && e.code === "bad-reading-count" && e.reason.includes("fx-stmt-file"));
  // the other order: the file first, then the group listing it with another count
  const rev = createData(fetchOf("cues", (addr, raw) => {
    if (addr === "step/fx-group.json") { raw.children[0].reading_count = 2; raw.card.reading_count = 2; }
    return raw;
  }));
  await rev.loadStep("fx-stmt-file");
  await assert.rejects(() => rev.loadStep("fx-group"), (e) => e instanceof DataError && e.code === "bad-reading-count");
  void lie;
});

test("createData: the engine's data carries readingCount on a card that has one and no key on one that has not", async () => {
  const d = createData(fetchOf("cues"));
  const roots = await d.loadRoots();
  assert.equal(roots[0].data.readingCount, 1);
  const kids = await d.loadChildren("fx-stmt-file");
  assert.equal(kids.find((k) => k.id === "fx-thm-a").data.readingCount, 1);
  assert.equal("readingCount" in kids.find((k) => k.id === "fx-lem-b").data, false);
});

/* ------------------------------------------------------------------------------------------------ 3: the face */
function richDoc() {
  const doc = makeFakeDoc();
  const create = doc.createElement;
  doc.createElement = (t) => {
    const n = create(t);
    n.listeners = [];
    n.addEventListener = (type, fn, opts) => { n.listeners.push({ type, fn, opts }); };
    return n;
  };
  doc.defaultView = {};
  return doc;
}
const textOf = (n) => (n.nodeType === 3 ? n.textContent : (n.children || []).map(textOf).join(""));
const cls = (n) => (n.attrs && n.attrs.class) || "";
const STR = { parts_n: "{n} parts", part_one: "1 part", count_statement_one: "{n} statement", count_statement_many: "{n} statements",
  face_reading_cue: "AI reading", count_reading_one: "1 AI reading", count_reading_many: "{n} AI readings", key_reading_cue_text: "[key]" };
const CW = {};
const CCW = { file: { one: "count_statement_one", many: "count_statement_many" } };
function face(over = {}, strings = STR, childCount = 0) {
  const doc = richDoc(); globalThis.document = doc;
  try {
    const r = makeRenderFace(strings, CW, CCW)({ id: "x", childCount, data: { title: "T", kind: over.kind || "theorem", state: "none", ...over.data } });
    return r;
  } finally { delete globalThis.document; }
}

test("a statement box with a reading draws the tag word in a div.face-reading AFTER the title; the face carries has-cue", () => {
  const f = face({ data: { readingCount: 1 } });
  assert.deepEqual(f.children.map(cls), ["face-title", "face-reading"]);
  assert.equal(textOf(f.children[1]), "AI reading");
  assert.ok(cls(f).split(" ").includes("has-cue"));
});

test("a box above statements draws the count line AFTER the foot: '1 AI reading' for one, '{n} AI readings' for more, with {n} as text", () => {
  const one = face({ kind: "file", data: { readingCount: 1 } }, STR, 3);
  assert.deepEqual(one.children.map(cls), ["face-title", "face-foot", "face-reading"]);
  assert.equal(textOf(one.children[2]), "1 AI reading");
  const many = face({ kind: "file", data: { readingCount: 2 } }, STR, 3);
  assert.equal(textOf(many.children[2]), "2 AI readings");
  const hostile = { ...STR, count_reading_many: "{n} $& $1 readings" };
  assert.equal(textOf(face({ kind: "file", data: { readingCount: 12 } }, hostile, 3).children[2]), "12 $& $1 readings");
});

test("cueText: null without the cue words, without a count, with a count that is not an integer of 1 or more", () => {
  assert.equal(cueText(STR, 1, 0), "AI reading");
  assert.equal(cueText({ parts_n: "x" }, 1, 0), null);
  for (const n of [undefined, 0, -2, 1.5, "1", null]) assert.equal(cueText(STR, n, 0), null, String(n));
});

test("the cue is a text node: a hostile tag word or count word is text, never an element", () => {
  const evil = { ...STR, face_reading_cue: "<b>AI</b> reading", count_reading_many: "<script>{n}</script>" };
  const f = face({ data: { readingCount: 1 } }, evil);
  assert.equal(textOf(f.children[1]), "<b>AI</b> reading");
  assert.equal(f.children[1].children.length, 1);
  assert.equal(f.children[1].children[0].nodeType, 3);
  const g = face({ kind: "file", data: { readingCount: 3 } }, evil, 2);
  assert.equal(textOf(g.children[2]), "<script>3</script>");
});

/* ------------------------------------------------------------------------------------------------ 4: nothing changes without the count */
test("a face with no reading_count, or with the count but no cue words, is the face of today: same children, same classes", () => {
  const without = face({ data: {} });
  assert.deepEqual(without.children.map(cls), ["face-title"]);
  assert.ok(!cls(without).includes("has-cue"));
  const noWords = { parts_n: "{n} parts", part_one: "1 part", count_statement_one: "{n} statement", count_statement_many: "{n} statements" };
  const f = face({ data: { readingCount: 1 } }, noWords);
  assert.deepEqual(f.children.map(cls), ["face-title"]);
  assert.ok(!cls(f).includes("has-cue"));
  const g = face({ kind: "file", data: { readingCount: 2 } }, noWords, 3);
  assert.deepEqual(g.children.map(cls), ["face-title", "face-foot"]);
});

test("the live-shaped indexes and steps (no reading_count anywhere) validate as before: the statements fixture too", () => {
  const v = validateIndex(read("statements", "index.json"));
  const c = { commit: v.commit, strings: v.strings, symbols: v.symbols, ids: v.ids };
  for (const id of ["fx-part", "fx-group", "fx-stmt-file", "fx-thm-a", "fx-lem-b", "fx-def-c", "fx-file-2"]) validateStep(read("statements", "step", id + ".json"), c);
});

/* ------------------------------------------------------------------------------------------------ the open card's button */
test("on a card that has a reading the show button carries the filled main class; the card without a reading has no such button", () => {
  const doc = richDoc(); globalThis.document = doc;
  const el = makeEl(doc);
  const STRS = { ...Object.fromEntries(["decl_show_lean", "decl_hide_lean", "decl_lean_note", "decl_uses_here", "decl_uses_elsewhere", "decl_no_note", "key_statements_heading",
    "key_statements_text", "decl_prompt_button", "decl_prompt_copied", "decl_prompt_note", "decl_heading_label", "decl_note_source"].map((k) => [k, "[" + k + "]"])),
    spine_content_label: "[l]", decl_reading_show: "[show]", decl_reading_hide: "[hide]", decl_reading_about: "[about]", readings_byline: "{by}" };
  const decl = { name: "F.x", sourcePath: "src/a.lean", keyword: "theorem", text: "t", variables: false, usesHere: [], usesElsewhere: [], usesLibraryCount: 0, prompt: "P" };
  try {
    const w = buildStatement({ strings: STRS, decl: { ...decl, reading: { text: "x", by: "A", secondReadBy: "B", date: "2026-01-02" } }, hasNote: true, titleOf: () => undefined, el, doc, signal: new AbortController().signal, typeset: false });
    const btn = w.tail[1].children[0];
    assert.equal(cls(btn), "sheet-tool sheet-tool-main");
  } finally { delete globalThis.document; }
});
