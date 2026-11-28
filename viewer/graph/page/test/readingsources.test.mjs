/* Maths-first part 2, page A3: a reading may carry `sources` and `rests_on` TOGETHER, and the page ACCEPTS and VALIDATES them and draws nothing (Sol's contract section 34 C2, C3, C5 and the limits table of his
   PR 150; Kepler's order: the page accepts before the builder writes). The fixture (fixtures/sources) is the readings sample whose reading also carries the two keys, the text unchanged; all text made up.
   Part 1: the fixture and the pair (a tree without the keys loads as today, one with them carries them); part 2: the all-or-none rule and the shape; part 3: a source of each kind; part 4: rests_on;
   part 5: the sizes (the text bound is asserted, not assumed) and the chunk rule of `paragraph`. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { DataError, validateIndex, validateStep } from "../data.js";

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");
const read = (dir, ...p) => JSON.parse(readFileSync(path.join(FIX, dir, ...p), "utf8"));
const clone = (o) => JSON.parse(JSON.stringify(o));
const stp = (id, dir = "sources") => read(dir, "step", id + ".json");
const ctxOf = (dir = "sources") => { const v = validateIndex(read(dir, "index.json")); return { commit: v.commit, strings: v.strings, symbols: v.symbols, ids: v.ids }; };
const refuses = (fn, mention) => assert.throws(fn, (e) => {
  assert.ok(e instanceof DataError, "not a DataError: " + e);
  assert.equal(e.code, "bad-reading");
  if (mention !== undefined) assert.ok(e.reason.includes(mention), "the reason " + JSON.stringify(e.reason) + " does not name " + mention);
  return true;
});
const withReading = (edit) => { const s = stp("fx-thm-a"); edit(s.reading, s); return s; };
const bad = (edit, mention) => refuses(() => validateStep(withReading(edit), ctxOf()), mention);
const good = (edit) => validateStep(withReading(edit), ctxOf());
const chunksOf = (t) => t.split(/\n(?:[ \t]*\n)+/).length;

/* ------------------------------------------------------------------------------------------------ 1: the fixture and the pair */
test("the sources fixture validates and carries both lists; the readings fixture (four keys) still validates and has neither", () => {
  const r = validateStep(stp("fx-thm-a"), ctxOf()).decl.reading;
  assert.deepEqual(r.sources.map((s) => s.kind), ["result", "result", "quote", "unopened"]);
  assert.equal(r.sources[0].step, "fx-lem-b");
  assert.equal(r.sources[1].step, undefined);
  assert.deepEqual(r.restsOn.map((e) => e.name), ["Fx.lemB", undefined]);
  const old = validateStep(stp("fx-thm-a", "readings"), ctxOf("readings")).decl.reading;
  assert.equal(old.sources, undefined);
  assert.equal(old.restsOn, undefined);
});

test("the sources fixture and the readings fixture differ ONLY by the two keys: strip them and every step is equal", () => {
  for (const id of ["fx-part", "fx-group", "fx-stmt-file", "fx-thm-a", "fx-lem-b", "fx-def-c", "fx-file-2"]) {
    const m = stp(id), s = stp(id, "readings");
    if (m.reading) { delete m.reading.sources; delete m.reading.rests_on; }
    assert.deepEqual(m, s, id);
  }
});

test("the quote's paragraph in the fixture points at the chunk that holds the quotation paragraph", () => {
  const s = stp("fx-thm-a"), q = s.reading.sources.find((x) => x.kind === "quote");
  assert.ok(s.reading.text.split(/\n(?:[ \t]*\n)+/)[q.paragraph].startsWith("In the repository's words ("));
});

/* ------------------------------------------------------------------------------------------------ 2: both or neither, and the shape of a reading */
test("sources without rests_on, rests_on without sources, and an extra key are refused; both empty lists are fine", () => {
  bad((r) => { delete r.rests_on; });
  bad((r) => { delete r.sources; });
  bad((r) => { r.extra = 1; });
  bad((r) => { r.sources = null; });
  bad((r) => { r.rests_on = {}; });
  const e = good((r) => { r.sources = []; r.rests_on = []; }).decl.reading;
  assert.deepEqual([e.sources, e.restsOn], [[], []]);
});

/* ------------------------------------------------------------------------------------------------ 3: the sources */
test("a source is an object of a known kind with exactly its keys", () => {
  for (const v of [null, "x", 7, [], {}, { kind: 7 }, { kind: "other" }]) bad((r) => { r.sources = [v]; }, "sources entry 1");
  bad((r) => { delete r.sources[0].lean; });
  bad((r) => { r.sources[0].extra = 1; });
  bad((r) => { delete r.sources[2].paragraph; });
  bad((r) => { r.sources[2].extra = 1; });
  bad((r) => { r.sources[3].extra = 1; });
  bad((r) => { delete r.sources[3].text; });
});

test("result: lean 1 to 300 code points of visible text; a line from 1 to 999999999; a src/ Lean path; words one line without a backtick; an id for step", () => {
  const okLean = "\u{1D4DD}".repeat(300);
  assert.equal(good((r) => { r.sources[0].lean = okLean; }).decl.reading.sources[0].lean, okLean);
  for (const v of ["", "\u{1D4DD}".repeat(301), "a\nb", "a\tb", "a\u0000", "\ud800", 7, null]) bad((r) => { r.sources[0].lean = v; }, "lean");
  for (const v of [1, 999999999]) good((r) => { r.sources[0].line = v; });
  for (const v of [0, -1, 1000000000, 1.5, "3", null, true]) bad((r) => { r.sources[0].line = v; }, "line");
  for (const v of ["src/A.lean", "src/A/b_c-d.1.lean", "src/" + "a/".repeat(95) + "x.lean"]) good((r) => { r.sources[0].path = v; });
  for (const v of ["", "A.lean", "src/A.txt", "src/A", "src//A.lean", "src/../A.lean", "src/./A.lean", "/src/A.lean", "src/A b.lean", "src\\A.lean", "src/" + "a/".repeat(98) + "x.lean", "src/" + "a/".repeat(95) + "xy.lean", 7, null]) bad((r) => { r.sources[0].path = v; }, "path");
  for (const v of ["", "a`b", "a\nb", "a\tb", "a\ud800", 7, null]) bad((r) => { r.sources[0].words = v; }, "words");
  good((r) => { r.sources[0].words = "a: b c ​‮ é 𝓝"; });
  good((r) => { r.sources[0].step = "a".repeat(64); });
  for (const v of ["", "A", "-a", "a b", "a".repeat(65), 7, null]) bad((r) => { r.sources[0].step = v; }, "step");
});

test("quote: from and to are lines from 1 with from at most to; the path as for a result", () => {
  good((r) => { r.sources[2].from = 5; r.sources[2].to = 5; });
  for (const [a, b] of [[0, 3], [4, 3], [1.5, 2], ["1", 2], [1, 1000000000], [null, null]]) bad((r) => { r.sources[2].from = a; r.sources[2].to = b; }, "lines");
  bad((r) => { r.sources[2].path = "x"; }, "path");
});

test("quote: paragraph is a whole number from 0 to (chunks - 1), and strictly increasing along the sources", () => {
  const last = chunksOf(stp("fx-thm-a").reading.text) - 1;
  good((r) => { r.sources[2].paragraph = last; });
  good((r) => { r.sources[2].paragraph = 0; });
  for (const v of [-1, -0, last + 1, 1.5, "2", null, 1e9]) bad((r) => { r.sources[2].paragraph = v; }, "paragraph");
  const two = (a, b) => (r) => { r.sources.push({ kind: "quote", from: 5, paragraph: b, path: "src/Fx/File.lean", to: 6 }); r.sources[2].paragraph = a; };
  good(two(2, 3));
  bad(two(3, 3), "does not come after");
  bad(two(4, 3), "does not come after");
});

test("unopened: a text that is one non-blank line (blank as Python strips: U+FEFF is not whitespace there)", () => {
  good((r) => { r.sources[3].text = "x"; });
  good((r) => { r.sources[3].text = "\uFEFF"; });
  for (const v of ["", "   ", "  ".trim() === "" ? "  　 " : "x", "a\nb", "a\tb", "\ud800", 7, null]) bad((r) => { r.sources[3].text = v; }, "text");
});

/* ------------------------------------------------------------------------------------------------ 4: rests_on */
test("rests_on: an entry is {gives, words} or {gives, name, step, words}; name and step go together", () => {
  for (const v of [null, "x", 7, [], {}]) bad((r) => { r.rests_on = [v]; }, "rests_on entry 1");
  bad((r) => { r.rests_on[0].extra = 1; });
  bad((r) => { delete r.rests_on[0].step; });
  bad((r) => { delete r.rests_on[0].gives; });
  bad((r) => { r.rests_on[1].step = "fx-lem-b"; });
  bad((r) => { r.rests_on[1].name = "Fx.x"; });
  bad((r) => { delete r.rests_on[1].words; });
});

test("rests_on: words one trimmed line without ': '; gives one non-blank line; name 1 to 200 code points; step an id", () => {
  good((r) => { r.rests_on[0].words = "a:b  é`x`"; });
  good((r) => { r.rests_on[0].words = "a\uFEFF"; r.rests_on[1].gives = "\uFEFF"; });          // Python strip leaves U+FEFF: legal for the builder
  for (const v of ["", " a", "a ", "a: b", "a\nb", "a\tb", "\ud800", 7, null]) bad((r) => { r.rests_on[0].words = v; }, "words");
  good((r) => { r.rests_on[1].gives = "a: b `c`  "; });
  for (const v of ["", "   ", "a\nb", "a\tb", "\ud800", 7, null]) bad((r) => { r.rests_on[1].gives = v; }, "gives");
  good((r) => { r.rests_on[0].name = "\u{1D4DD}".repeat(200); });
  for (const v of ["", "\u{1D4DD}".repeat(201), "a\nb", 7, null]) bad((r) => { r.rests_on[0].name = v; }, "name");
  good((r) => { r.rests_on[0].step = "a".repeat(64); });
  for (const v of ["", "A", "a".repeat(65), 7, null]) bad((r) => { r.rests_on[0].step = v; }, "step");
});

/* ------------------------------------------------------------------------------------------------ 5: the sizes and the chunks */
test("list sizes: 2000 sources and 3000 rests_on pass; one more of either is refused; the empty lists pass", () => {
  const u = { kind: "unopened", text: "x" }, e = { gives: "g", words: "w" };
  good((r) => { r.sources = Array.from({ length: 2000 }, () => u); r.rests_on = Array.from({ length: 3000 }, () => e); });
  bad((r) => { r.sources = Array.from({ length: 2001 }, () => u); }, "2000");
  bad((r) => { r.rests_on = Array.from({ length: 3001 }, () => e); }, "3000");
});

test("the text keeps its bound with the keys present: 20000 bytes pass (and the sources then still load), 20001 are refused; a free text of 20000 bytes passes, 20001 refused", () => {
  const quote = stp("fx-thm-a").reading.text;
  good((r) => { r.text = "a".repeat(20000); r.sources = []; r.rests_on = []; });
  bad((r) => { r.text = "a".repeat(20001); }, "20000");
  good((r) => { r.text = quote; });
  good((r) => { r.sources[3].text = "a".repeat(20000); r.rests_on = []; });
  bad((r) => { r.sources[3].text = "a".repeat(20001); }, "text");
  bad((r) => { r.sources[0].words = "a".repeat(20001); }, "words");
  bad((r) => { r.rests_on[1].gives = "é".repeat(10001); }, "gives");
  good((r) => { r.rests_on[1].gives = "é".repeat(10000); });
});

test("the chunks of the text are the builder's split, on the text as given: a blank line of spaces and tabs is a separator, a line holding a no-break space or a carriage return is not, and nothing is trimmed", () => {
  const t = "a\n\nb\n \t\nc\n \nd\n\n";
  assert.equal(chunksOf(t), 4);                                   // a | b | c\n \nd | "" (a trailing separator leaves an empty last chunk: the page counts it, the builder writes none)
  const ok = (n) => good((r) => { r.text = t; r.sources = [{ kind: "quote", from: 1, paragraph: n, path: "src/A.lean", to: 1 }]; r.rests_on = []; });
  ok(3);
  bad((r) => { r.text = t; r.sources = [{ kind: "quote", from: 1, paragraph: 4, path: "src/A.lean", to: 1 }]; r.rests_on = []; }, "paragraph");
  const u = "a\n\nb\n \nc";
  assert.equal(chunksOf(u), 2);
  bad((r) => { r.text = u; r.sources = [{ kind: "quote", from: 1, paragraph: 2, path: "src/A.lean", to: 1 }]; r.rests_on = []; }, "paragraph");
});

test("a statement step with a four-key reading is refused only by the old rule (a fifth key alone is not a reading)", () => {
  bad((r) => { delete r.sources; delete r.rests_on; r.sources_x = []; });
  const old = stp("fx-thm-a", "readings"); old.reading.sources = [];
  refuses(() => validateStep(old, ctxOf("readings")));
});
