/* The reading block of a statement card (Kepler 39806; Ariadne's note v2.1 section 9; Sol's `reading` shape, 39808 and 39968). Written BEFORE the implementation was run.
   Part 1: the data layer (the four reading words, the step's optional `reading`), part 2: statement.js (the block, its order, its closed state, its byline). The fixture
   (fixtures/readings) is the statements sample plus the words and a MADE-UP reading on fx-thm-a: no text of any real reading is in this file or in the fixture. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { DataError, validateIndex, validateStep, READING_STRINGS } from "../data.js";
import { buildStatement, bylineParts } from "../statement.js";
import { makeEl } from "../dom.js";
import { makeFakeDoc } from "./fakedoc.mjs";

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");
const read = (dir, ...p) => JSON.parse(readFileSync(path.join(FIX, dir, ...p), "utf8"));
const clone = (o) => JSON.parse(JSON.stringify(o));
const idx = () => read("readings", "index.json");
const stp = (id) => read("readings", "step", id + ".json");
const refuses = (fn, code, mention) => assert.throws(fn, (e) => {
  assert.ok(e instanceof DataError, "not a DataError: " + e);
  assert.equal(e.code, code);
  if (mention !== undefined) assert.ok(e.reason.includes(mention), "the reason " + JSON.stringify(e.reason) + " does not name " + mention);
  return true;
});
const ctxOf = () => { const v = validateIndex(idx()); return { commit: v.commit, strings: v.strings, ...v }; };
const stepCtx = () => { const v = validateIndex(idx()); return { commit: v.commit, strings: v.strings, symbols: v.symbols, ids: v.ids }; };

/* ------------------------------------------------------------------------------------------------ the words */
test("the four reading words are the page's group; the fixture index validates with them", () => {
  assert.deepEqual([...READING_STRINGS], ["decl_reading_show", "decl_reading_hide", "decl_reading_about", "readings_byline"]);
  const v = validateIndex(idx());
  for (const k of READING_STRINGS) assert.ok(typeof v.strings[k] === "string" && v.strings[k] !== "", k);
});

test("the reading words are all-or-none: any one missing or empty, the others present, is bad-reading-strings naming it", () => {
  for (const k of READING_STRINGS) {
    const a = idx(); delete a.strings[k];
    refuses(() => validateIndex(a), "bad-reading-strings", k);
    const b = idx(); b.strings[k] = "";
    refuses(() => validateIndex(b), "bad-reading-strings", k);
  }
});

test("a map with none of the reading words validates (the statements sample as it is today)", () => {
  const i = idx();
  for (const k of READING_STRINGS) delete i.strings[k];
  validateIndex(i);
});

test("with the statement group off, a reading word is an extra-string like any key the page does not read", () => {
  const i = read("readings", "index.json");
  for (const k of Object.keys(i.strings)) if (/^(decl_|key_statements_|open_statements|close_statements|count_statement)/.test(k)) delete i.strings[k];
  // the kind rows still name decl_kind_*; drop the statement kinds from the symbols so the index is the live shape plus the reading words
  const kinds = i.symbols.kinds;
  for (const k of ["theorem", "lemma", "def"]) { delete kinds[k]; }
  i.symbols.order.kinds = i.symbols.order.kinds.filter((k) => !["theorem", "lemma", "def"].includes(k));
  for (const r of Object.values(kinds)) { delete r.open_words; delete r.child_count_words; }
  delete i.strings.spine_content_label;
  assert.throws(() => validateIndex(i), (e) => e instanceof DataError && (e.code === "extra-string" || e.code === "bad-reading-strings"));
});

/* ------------------------------------------------------------------------------------------------ the step's reading */
test("the fixture's theorem step validates and carries decl.reading as {text, by, secondReadBy, date}; the other statements carry none", () => {
  const ctx = stepCtx();
  const a = validateStep(stp("fx-thm-a"), ctx);
  assert.deepEqual(Object.keys(a.decl.reading).sort(), ["by", "date", "secondReadBy", "text"]);
  assert.equal(a.decl.reading.by, "Made-Up Writer");
  assert.equal(a.decl.reading.secondReadBy, "Made-Up Checker");
  assert.equal(a.decl.reading.date, "2026-01-02");
  assert.ok(a.decl.reading.text.includes("## What it rests on"));
  assert.equal(validateStep(stp("fx-lem-b"), ctx).decl.reading, undefined);
  assert.equal(validateStep(stp("fx-def-c"), ctx).decl.reading, undefined);
});

test("reading: not an object, a missing key, an extra key, or a key that is not a non-empty string is bad-reading naming the step", () => {
  const ctx = stepCtx();
  const bad = (edit, mention) => { const s = stp("fx-thm-a"); edit(s.reading); refuses(() => validateStep(s, ctx), "bad-reading", mention || "fx-thm-a"); };
  for (const k of ["text", "by", "second_read_by", "date"]) bad((r) => { delete r[k]; });
  bad((r) => { r.extra = "x"; });
  for (const k of ["text", "by", "second_read_by", "date"]) {
    bad((r) => { r[k] = ""; });
    bad((r) => { r[k] = 7; });
    bad((r) => { r[k] = null; });
  }
  const s = stp("fx-thm-a"); s.reading = ["x"]; refuses(() => validateStep(s, ctx), "bad-reading", "fx-thm-a");
  const t = stp("fx-thm-a"); t.reading = null; refuses(() => validateStep(t, ctx), "bad-reading", "fx-thm-a");
});

test("reading.text: 20000 bytes passes, one byte more is refused; the count is BYTES (a multi-byte letter counts more than once)", () => {
  const ctx = stepCtx();
  const ok = stp("fx-thm-a"); ok.reading.text = "a".repeat(20000); validateStep(ok, ctx);
  const over = stp("fx-thm-a"); over.reading.text = "a".repeat(20001); refuses(() => validateStep(over, ctx), "bad-reading", "text");
  const multi = stp("fx-thm-a"); multi.reading.text = "é".repeat(10001); refuses(() => validateStep(multi, ctx), "bad-reading", "text");   // 20002 bytes, 10001 characters
  const multiOk = stp("fx-thm-a"); multiOk.reading.text = "é".repeat(10000); validateStep(multiOk, ctx);
});

test("reading.by and second_read_by: 80 characters pass, 81 are refused, a control character is refused, a space and a name with a dot pass", () => {
  const ctx = stepCtx();
  for (const k of ["by", "second_read_by"]) {
    const ok = stp("fx-thm-a"); ok.reading[k] = "A".repeat(80); validateStep(ok, ctx);
    const fine = stp("fx-thm-a"); fine.reading[k] = "Dr. A Name"; validateStep(fine, ctx);
    const over = stp("fx-thm-a"); over.reading[k] = "A".repeat(81); refuses(() => validateStep(over, ctx), "bad-reading", k);
    for (const c of ["\n", "\t", "\u0000", "\u007f"]) { const bad = stp("fx-thm-a"); bad.reading[k] = "A" + c + "B"; refuses(() => validateStep(bad, ctx), "bad-reading", k); }
  }
});

test("reading.date: YYYY-MM-DD only", () => {
  const ctx = stepCtx();
  for (const d of ["2026-1-2", "26-01-02", "2026/01/02", "2026-01-02 ", " 2026-01-02", "2026-01-02T00:00:00Z", "January 2", "2026-01-020"]) {
    const s = stp("fx-thm-a"); s.reading.date = d; refuses(() => validateStep(s, ctx), "bad-reading", "date");
  }
});

test("a reading on a step that is not a statement is an extra-key (the page reads it on statements only)", () => {
  const ctx = stepCtx();
  const s = stp("fx-file-2"); s.reading = clone(stp("fx-thm-a").reading);
  assert.throws(() => validateStep(s, ctx), (e) => e instanceof DataError && (e.code === "extra-key" || e.code === "bad-statement"));
});

test("a reading while the index strings hold no reading words is bad-reading-strings", () => {
  const i = idx(); for (const k of READING_STRINGS) delete i.strings[k];
  const v = validateIndex(i);
  refuses(() => validateStep(stp("fx-thm-a"), { commit: v.commit, strings: v.strings, symbols: v.symbols, ids: v.ids }), "bad-reading-strings", "fx-thm-a");
});

/* ------------------------------------------------------------------------------------------------ statement.js */
function richDoc() {
  const doc = makeFakeDoc();
  const create = doc.createElement;
  doc.createElement = (t) => {
    const n = create(t);
    n.listeners = [];
    n.addEventListener = (type, fn, opts) => { n.listeners.push({ type, fn, opts }); };
    n.removeChild = (c) => { n.children.splice(n.children.indexOf(c), 1); return c; };
    n.replaceChildren = (...c) => { n.children.splice(0, n.children.length, ...c); };
    return n;
  };
  doc.defaultView = {};
  return doc;
}
const textOf = (n) => (n.nodeType === 3 ? n.textContent : (n.children || []).map(textOf).join(""));
const walk = (n, out = []) => { out.push(n); for (const c of n.children || []) walk(c, out); return out; };
const cls = (n) => (n.attrs && n.attrs.class) || "";
const has = (n, c) => cls(n).split(" ").includes(c);
const GROUP = ["decl_show_lean", "decl_hide_lean", "decl_lean_note", "decl_uses_here", "decl_uses_elsewhere", "decl_no_note", "key_statements_heading",
  "key_statements_text", "decl_prompt_button", "decl_prompt_copied", "decl_prompt_note", "decl_heading_label", "decl_note_source"];
const STR = { ...Object.fromEntries(GROUP.map((k) => [k, "[" + k + "]"])), decl_reading_none: "[decl_reading_none]", spine_content_label: "[label]",
  decl_reading_show: "[show reading]", decl_reading_hide: "[hide reading]", decl_reading_about: "[about reading]", readings_byline: "by {by} / {second_read_by} / {date}" };
const READING = { text: "A preface.\n\n## What it rests on\n\n- `Fx.helper`\n\n## What it states\n\nFor `n` it holds.", by: "A", secondReadBy: "B", date: "2026-01-02" };
const decl = (extra = {}) => ({ name: "Fx.foo_bar", sourcePath: "src/New/Fx/File.lean", keyword: "theorem", text: "theorem foo_bar : True", variables: false,
  usesHere: [], usesElsewhere: [], usesLibraryCount: 0, prompt: "P", ...extra });
function build(over = {}) {
  const doc = richDoc();
  const el = makeEl(doc);
  doc.defaultView = { navigator: {}, getSelection: () => ({ selectAllChildren() {} }) };
  const ctl = new AbortController();
  globalThis.document = doc;
  const out = buildStatement({ strings: over.strings || STR, decl: decl(over.decl), hasNote: true, titleOf: () => undefined, el, doc, signal: ctl.signal, typeset: !!over.typeset });
  return { out, doc, el, ctl };
}

test("a statement with a reading: the tail is Lean, reading, uses here, uses elsewhere, prompt; without one the tail is as before (no reading element)", () => {
  const w = build({ decl: { reading: READING } });
  const wo = build({});
  try {
    assert.deepEqual(w.out.tail.map(cls), ["decl-lean", "decl-reading", "decl-uses decl-uses-here", "decl-uses decl-uses-elsewhere", "decl-prompt"]);
    assert.deepEqual(wo.out.tail.map(cls), ["decl-lean", "decl-uses decl-uses-here", "decl-uses decl-uses-elsewhere", "decl-prompt"]);
  } finally { delete globalThis.document; }
});

test("the reading block: a button first (aria-expanded false, the show word), then a hidden body holding the label, the rendered text and the byline last", () => {
  const { out } = build({ decl: { reading: READING } });
  try {
    const block = out.tail[1];
    const [btn, body] = block.children;
    assert.equal(btn.tagName, "BUTTON");
    assert.ok(has(btn, "sheet-tool"));
    assert.equal(btn.attrs["aria-expanded"], "false");
    assert.equal(textOf(btn), "[show reading]");
    assert.equal(body.hidden, true, "closed when the card is built");
    assert.deepEqual(body.children.map(cls), ["decl-reading-about", "decl-reading-text", "decl-reading-byline"]);
    assert.equal(textOf(body.children[0]), "[about reading]");
    assert.equal(textOf(body.children[2]), "by A / B / 2026-01-02");
  } finally { delete globalThis.document; }
});

test("the reading goes through the note renderer: the ## lines are h4 headings, the list is a list, a code span is <code>; the preface is a paragraph", () => {
  const { out } = build({ decl: { reading: READING } });
  try {
    const all = walk(out.tail[1]);
    const tags = (t) => all.filter((n) => n.tagName === t);
    assert.equal(tags("H4").length, 2);
    assert.deepEqual(tags("H4").map(textOf), ["What it rests on", "What it states"]);
    assert.equal(tags("UL").length, 1);
    assert.ok(tags("CODE").some((c) => textOf(c) === "Fx.helper"));
    assert.ok(tags("P").some((p) => textOf(p) === "A preface."));
  } finally { delete globalThis.document; }
});

test("the button toggles the body, aria-expanded and its own words, and a second press closes it again", () => {
  const { out } = build({ decl: { reading: READING } });
  try {
    const [btn, body] = out.tail[1].children;
    const press = () => btn.listeners.find((l) => l.type === "click").fn();
    press();
    assert.equal(body.hidden, false);
    assert.equal(btn.attrs["aria-expanded"], "true");
    assert.equal(textOf(btn), "[hide reading]");
    press();
    assert.equal(body.hidden, true);
    assert.equal(btn.attrs["aria-expanded"], "false");
    assert.equal(textOf(btn), "[show reading]");
  } finally { delete globalThis.document; }
});

test("a card built again is closed again (the block keeps no memory between cards)", () => {
  const first = build({ decl: { reading: READING } });
  try {
    first.out.tail[1].children[0].listeners.find((l) => l.type === "click").fn();
    assert.equal(first.out.tail[1].children[1].hidden, false);
    const second = build({ decl: { reading: READING } });
    assert.equal(second.out.tail[1].children[1].hidden, true);
  } finally { delete globalThis.document; }
});

test("on a card WITH a reading the decl_reading_none line is not shown; on a card without one it is, directly above the copy button", () => {
  const w = build({ decl: { reading: READING } });
  const wo = build({});
  try {
    assert.deepEqual(w.out.tail[4].children.map(cls), ["sheet-tool", "decl-prompt-status", "decl-prompt-text", "decl-prompt-note"]);
    assert.deepEqual(wo.out.tail[3].children.map(cls), ["decl-reading-none", "sheet-tool", "decl-prompt-status", "decl-prompt-text", "decl-prompt-note"]);
    assert.equal(walk({ children: w.out.tail }).filter((n) => has(n, "decl-reading-none")).length, 0);
  } finally { delete globalThis.document; }
});

test("a card without a reading has no show button: only the copy button and the Lean button are buttons", () => {
  const { out } = build({});
  try {
    const buttons = walk({ children: out.tail }).filter((n) => n.tagName === "BUTTON");
    assert.equal(buttons.length, 2);
    assert.deepEqual(buttons.map(textOf).sort(), ["[decl_prompt_button]", "[decl_show_lean]"].sort());
  } finally { delete globalThis.document; }
});

test("the reading's text, the names and the date reach the DOM as text only: markup, braces and a hostile name stay literal", () => {
  const hostile = { text: "<script>alert(1)</script> {by} &amp; <b>x</b>\n\n## What it states\n\n<img src=x onerror=alert(1)>", by: "<b>A</b>", secondReadBy: "{date}", date: "2026-01-02" };
  const { out } = build({ decl: { reading: hostile } });
  try {
    const all = walk(out.tail[1]);
    for (const bad of ["SCRIPT", "B", "IMG"]) assert.equal(all.filter((n) => n.tagName === bad).length, 0, bad + " must not be an element");
    const t = textOf(out.tail[1]);
    assert.ok(t.includes("<script>alert(1)</script> {by} &amp; <b>x</b>"));
    assert.ok(t.includes("<img src=x onerror=alert(1)>"));
    assert.ok(textOf(out.tail[1].children[1].children[2]).includes("<b>A</b>"), "the name is text");
    assert.ok(textOf(out.tail[1].children[1].children[2]).includes("by <b>A</b> / {date} / 2026-01-02"), "a placeholder inside a value is not filled twice");
  } finally { delete globalThis.document; }
});

test("bylineParts fills {by}, {second_read_by} and {date} as text pieces, leaves any other brace alone, and fills a repeated placeholder everywhere", () => {
  const r = { by: "A", secondReadBy: "B", date: "D" };
  assert.deepEqual(bylineParts("Written by {by}, checked by {second_read_by}, {date}", r), ["Written by ", "A", ", checked by ", "B", ", ", "D"]);
  assert.deepEqual(bylineParts("{n} {by} {by} {other}", r), ["{n} ", "A", " ", "A", " {other}"]);
  assert.deepEqual(bylineParts("no placeholders", r), ["no placeholders"]);
});

test("every listener of the reading block carries the page's abort signal", () => {
  const { out, ctl } = build({ decl: { reading: READING } });
  try {
    const btn = out.tail[1].children[0];
    assert.equal(btn.listeners.length, 1);
    assert.equal(btn.listeners[0].opts.signal, ctl.signal);
  } finally { delete globalThis.document; }
});
