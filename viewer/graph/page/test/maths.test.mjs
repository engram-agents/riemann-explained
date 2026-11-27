/* Maths-first part 1, the PAGE accepts and validates (Kepler 40464; Sol's contract section 34 B1 to B3), and draws nothing new: `number` on a closed card and on its entry, `math` and `human` on a
   statement step, `notation` on a step that is not a statement. The fixture (fixtures/maths) is the statements sample plus the keys, titles unchanged; all text made up.
   Part 1: the number; part 2: math and human; part 3: notation; part 4: a tree WITHOUT the keys loads as today, and one WITH them carries them and draws as today. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { DataError, validateIndex, validateStep, createData } from "../data.js";

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");
const read = (dir, ...p) => JSON.parse(readFileSync(path.join(FIX, dir, ...p), "utf8"));
const clone = (o) => JSON.parse(JSON.stringify(o));
const stp = (id, dir = "maths") => read(dir, "step", id + ".json");
const refuses = (fn, code, mention) => assert.throws(fn, (e) => {
  assert.ok(e instanceof DataError, "not a DataError: " + e);
  assert.equal(e.code, code);
  if (mention !== undefined) assert.ok(e.reason.includes(mention), "the reason " + JSON.stringify(e.reason) + " does not name " + mention);
  return true;
});
const ctxOf = (dir = "maths") => { const v = validateIndex(read(dir, "index.json")); return { commit: v.commit, strings: v.strings, symbols: v.symbols, ids: v.ids }; };
const fetchOf = (dir, edit) => async (address) => {
  const name = address.replace(/^step\//, "").replace(/\.json$/, "");
  let raw = address === "index.json" ? read(dir, "index.json") : read(dir, "step", name + ".json");
  if (edit) raw = edit(address, clone(raw)) || raw;
  return { ok: true, status: 200, json: async () => raw };
};
const IDS = ["fx-part", "fx-group", "fx-stmt-file", "fx-thm-a", "fx-lem-b", "fx-def-c", "fx-file-2"];

/* ------------------------------------------------------------------------------------------------ 1: the number */
test("the maths fixture validates: every step, and the numbers are carried on the cards", () => {
  const c = ctxOf();
  for (const id of IDS) validateStep(stp(id), c);
  assert.equal(validateStep(stp("fx-thm-a"), c).card.number, "1.1");
  assert.equal(validateStep(stp("fx-lem-b"), c).card.number, "1.2");
  assert.equal(validateStep(stp("fx-stmt-file"), c).children.find((x) => x.id === "fx-def-c").number, "1.3");
  assert.equal(validateStep(stp("fx-file-2"), c).card.number, undefined);
});

test("number: only <file>.<n>, two counters of 1 or more, no zero, no leading zero, no spaces, nothing else", () => {
  const ok = ["1.1", "2.7", "10.24", "3.12", "123456.654321"];
  const bad = ["", "1", "1.", ".1", "0.1", "1.0", "01.1", "1.01", "1.1.1", "1,1", "1.1 ", " 1.1", "1.1\n", "a.1", "1.a", "1234567.1", "1.1234567", "１.1", "1.1​", 1.1, null, true, ["1.1"]];
  for (const v of ok) { const s = stp("fx-thm-a"); s.card.number = v; validateStep(s, ctxOf()); }
  for (const v of bad) { const s = stp("fx-thm-a"); s.card.number = v; refuses(() => validateStep(s, ctxOf()), "bad-number", "step.card"); }
});

test("number on a closed ENTRY is checked the same way", () => {
  const s = stp("fx-stmt-file"); s.children[0].number = "0.0";
  refuses(() => validateStep(s, ctxOf()), "bad-number", "children");
});

test("createData: a parent's entry and the step's own card must say the same number (absent counts as none), in either load order", async () => {
  const ok = createData(fetchOf("maths"));
  await ok.loadStep("fx-stmt-file"); await ok.loadStep("fx-thm-a");
  const a = createData(fetchOf("maths", (addr, raw) => { if (addr === "step/fx-thm-a.json") raw.card.number = "1.9"; return raw; }));
  await a.loadStep("fx-stmt-file");
  await assert.rejects(() => a.loadStep("fx-thm-a"), (e) => e instanceof DataError && e.code === "bad-number" && e.reason.includes("fx-thm-a"));
  const b = createData(fetchOf("maths", (addr, raw) => { if (addr === "step/fx-stmt-file.json") raw.children[0].number = "1.9"; return raw; }));
  await b.loadStep("fx-thm-a");
  await assert.rejects(() => b.loadStep("fx-stmt-file"), (e) => e instanceof DataError && e.code === "bad-number");
  const c = createData(fetchOf("maths", (addr, raw) => { if (addr === "step/fx-thm-a.json") delete raw.card.number; return raw; }));     // entry has one, the card has none
  await c.loadStep("fx-stmt-file");
  await assert.rejects(() => c.loadStep("fx-thm-a"), (e) => e instanceof DataError && e.code === "bad-number");
});

/* ------------------------------------------------------------------------------------------------ 2: math and human */
test("math and human are carried on the statement's decl; a statement with no row has neither", () => {
  const c = ctxOf();
  const a = validateStep(stp("fx-thm-a"), c);
  assert.deepEqual(a.decl.math, { status: "read", text: "For every natural number `n` the made-up bound holds." });
  assert.deepEqual(a.decl.human, { rule: "classical", status: "read" });
  const b = validateStep(stp("fx-lem-b"), c);
  assert.equal(b.decl.math.status, "draft");
  assert.equal(b.decl.human, undefined);
  const d = validateStep(stp("fx-def-c"), c);
  assert.equal(d.decl.math, undefined);
  assert.equal(d.decl.human, undefined);
});

test("math: not exactly {status, text}, a status that is neither draft nor read, a text that is empty, too long, with a newline, a control character or a lone surrogate: bad-maths naming the step and the key", () => {
  const bad = (edit) => { const s = stp("fx-thm-a"); edit(s.math); refuses(() => validateStep(s, ctxOf()), "bad-maths", "fx-thm-a"); };
  bad((m) => { delete m.status; });
  bad((m) => { delete m.text; });
  bad((m) => { m.extra = "x"; });
  for (const v of ["", "Read", "done", null, 1, ["read"]]) bad((m) => { m.status = v; });
  for (const v of ["", "a\nb", "a\tb", "a\u0000b", "a\u0085b", "x".repeat(601), "\ud800", "a\udc00", 7, null, ["x"]]) bad((m) => { m.text = v; });
  for (const v of [null, "x", ["draft"], 5]) { const s = stp("fx-thm-a"); s.math = v; refuses(() => validateStep(s, ctxOf()), "bad-maths", "fx-thm-a"); }
});

test("math.text: 600 characters pass, 601 do not; a no-break space, a zero-width space and a bidi mark ARE allowed (typesetting may need them); 600 astral letters pass (code points)", () => {
  for (const t of ["x".repeat(600), "a b", "a​b", "a‮b", "\u{1D538}".repeat(600)]) { const s = stp("fx-thm-a"); s.math.text = t; validateStep(s, ctxOf()); }
  const s = stp("fx-thm-a"); s.math.text = "\u{1D538}".repeat(601); refuses(() => validateStep(s, ctxOf()), "bad-maths", "fx-thm-a");
});

test("human: not exactly {rule, status}, a rule outside the four, a status outside draft and read", () => {
  const bad = (edit) => { const s = stp("fx-thm-a"); edit(s.human); refuses(() => validateStep(s, ctxOf()), "bad-maths", "fx-thm-a"); };
  bad((h) => { delete h.rule; });
  bad((h) => { delete h.status; });
  bad((h) => { h.extra = 1; });
  for (const v of ["", "Classical", "invented", null, 3]) bad((h) => { h.rule = v; });
  for (const v of ["", "final", null]) bad((h) => { h.status = v; });
  for (const rule of ["repository-bold", "classical", "lean-name", "ours"]) { const s = stp("fx-thm-a"); s.human.rule = rule; validateStep(s, ctxOf()); }
});

test("math or human on a step that is NOT a statement is the ordinary extra-key refusal; so is a step carrying only them", () => {
  for (const k of ["math", "human"]) {
    const s = stp("fx-file-2"); s[k] = clone(stp("fx-thm-a")[k]);
    refuses(() => validateStep(s, ctxOf()), "extra-key");
  }
});

/* ------------------------------------------------------------------------------------------------ 3: notation */
test("notation on the file step is carried in order as {lean, status, symbol, text}; a step without it has none", () => {
  const c = ctxOf();
  const f = validateStep(stp("fx-stmt-file"), c);
  assert.deepEqual(f.notation.map((r) => r.symbol), ["E_q(t)", "R_q"]);
  assert.deepEqual(f.notation[0].lean, ["Fx.foo_bar", "Fx.qux"]);
  assert.deepEqual(f.notation[1].lean, []);
  assert.equal(validateStep(stp("fx-group"), c).notation, undefined);
});

test("notation: not a list, too many rows, a row with a missing or extra key, a bad lean, status, symbol or text: bad-maths naming the step", () => {
  const bad = (edit) => { const s = stp("fx-stmt-file"); edit(s); refuses(() => validateStep(s, ctxOf()), "bad-maths", "fx-stmt-file"); };
  bad((s) => { s.notation = {}; });
  bad((s) => { s.notation = "x"; });
  bad((s) => { s.notation = null; });
  bad((s) => { s.notation = Array.from({ length: 201 }, () => s.notation[0]); });
  for (const k of ["lean", "status", "symbol", "text"]) bad((s) => { delete s.notation[0][k]; });
  bad((s) => { s.notation[0].file = "fx-stmt-file"; });
  bad((s) => { s.notation[0].lean = "Fx.x"; });
  bad((s) => { s.notation[0].lean = [""]; });
  bad((s) => { s.notation[0].lean = [7]; });
  bad((s) => { s.notation[0].lean = ["x".repeat(301)]; });
  bad((s) => { s.notation[0].lean = Array.from({ length: 51 }, () => "Fx.x"); });
  bad((s) => { s.notation[0].status = "final"; });
  for (const v of ["", "a\nb", "x".repeat(201), "a\u0000", null]) bad((s) => { s.notation[0].symbol = v; });
  for (const v of ["", "a\nb", "x".repeat(601), "\ud800", null]) bad((s) => { s.notation[0].text = v; });
});

test("notation: 200 rows pass; a lean list of 50 passes; an empty list of rows passes", () => {
  const s = stp("fx-stmt-file"); s.notation = Array.from({ length: 200 }, (_, i) => ({ lean: Array.from({ length: 50 }, () => "Fx.x"), status: "draft", symbol: "s" + i, text: "t" })); validateStep(s, ctxOf());
  const e = stp("fx-stmt-file"); e.notation = []; assert.deepEqual(validateStep(e, ctxOf()).notation, []);
});

test("notation on a statement step is bad-statement (the file's key only)", () => {
  const s = stp("fx-thm-a"); s.notation = clone(stp("fx-stmt-file").notation);
  refuses(() => validateStep(s, ctxOf()), "bad-statement", "fx-thm-a");
});

/* ------------------------------------------------------------------------------------------------ 4: nothing changes without the keys */
test("the statements fixture (none of the new keys) validates as before and carries none of them", () => {
  const v = validateIndex(read("statements", "index.json"));
  const c = { commit: v.commit, strings: v.strings, symbols: v.symbols, ids: v.ids };
  for (const id of IDS) {
    const r = validateStep(stp(id, "statements"), c);
    assert.equal(r.card.number, undefined); assert.equal(r.notation, undefined);
    if (r.decl) { assert.equal(r.decl.math, undefined); assert.equal(r.decl.human, undefined); }
  }
});

test("the maths fixture and the statements fixture differ ONLY by the new keys: strip them and every step is equal", () => {
  for (const id of IDS) {
    const m = stp(id), s = stp(id, "statements");
    delete m.card.number; for (const c of m.children) delete c.number;
    delete m.math; delete m.human; delete m.notation;
    assert.deepEqual(m, s, id);
  }
});

test("createData over the maths tree: the engine's data for a box carries no number (nothing is drawn from it yet), the title is as in the statements tree", async () => {
  const m = createData(fetchOf("maths")), s = createData(fetchOf("statements"));
  const [mk, sk] = [await m.loadChildren("fx-stmt-file"), await s.loadChildren("fx-stmt-file")];
  assert.deepEqual(mk.map((k) => k.data), sk.map((k) => k.data));
  assert.deepEqual(mk.map((k) => k.childCount), sk.map((k) => k.childCount));
});
