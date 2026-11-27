/* The statement-level sample page (spec SPEC-sample-page.md, A-I plus amendments 1 and 2). Written BEFORE the implementation.
   Part 1: the data layer (index keys, strings group, the step's seven keys), part 2: the face foot and the parts label, part 3: statement.js. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { DataError, validateIndex, validateStep, KIND_CLASS, requiredStrings } from "../data.js";
import { footText, makeRenderFace } from "../face.js";
import { partsWords } from "../sheet.js";
import { buildStatement } from "../statement.js";
import { makeEl } from "../dom.js";
import { makeFakeDoc } from "./fakedoc.mjs";

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");
const read = (dir, ...p) => JSON.parse(readFileSync(path.join(FIX, dir, ...p), "utf8"));
const clone = (o) => JSON.parse(JSON.stringify(o));
const idx = () => read("statements", "index.json");
const stp = (id) => read("statements", "step", id + ".json");
const refuses = (fn, code, mention) => assert.throws(fn, (e) => {
  assert.ok(e instanceof DataError, "not a DataError: " + e);
  assert.equal(e.code, code);
  if (mention !== undefined) assert.ok(e.reason.includes(mention), "the reason " + JSON.stringify(e.reason) + " does not name " + mention);
  return true;
});
const GROUP = ["decl_show_lean", "decl_hide_lean", "decl_lean_note", "decl_uses_here", "decl_uses_elsewhere", "decl_no_note", "key_statements_heading",
  "key_statements_text", "decl_prompt_button", "decl_prompt_copied", "decl_prompt_note", "decl_heading_label"];
const STMT = ["name", "source_path", "statement", "variables", "uses_here", "uses_elsewhere", "prompt"];

/* ------------------------------------------------------------------------------------------------ A: the kinds table */
test("A: lemma, abbrev, instance, class, inductive are in the kinds table with their classes; theorem, def, structure stay", () => {
  assert.deepEqual({ ...KIND_CLASS }, { theorem: "k-theorem", def: "k-def", structure: "k-structure", part: "k-part", group: "k-group", file: "k-file",
    lemma: "k-lemma", abbrev: "k-abbrev", instance: "k-instance", class: "k-class", inductive: "k-inductive" });
});

/* ------------------------------------------------------------------------------------------------ the fixture is valid */
test("the statement fixture index validates; the file row's open_words and child_count_words are collected, the other rows have none", () => {
  const v = validateIndex(idx());
  assert.deepEqual(v.symbols.openWords.file, { open: "open_statements", close: "close_statements" });
  assert.deepEqual(v.symbols.openWords.group, { open: "open_parts", close: "close_parts" });
  assert.deepEqual(v.symbols.childCountWords, { file: { one: "count_statement_one", many: "count_statement_many" } });
  assert.deepEqual(Object.keys(v.symbols.openWords).sort(), ["file", "group"]);
  assert.equal(v.symbols.cardWords.lemma, "decl_kind_lemma");
  assert.deepEqual(v.symbols.countWords.theorem, undefined);
});

test("the keys of open_words and child_count_words are required strings, exactly like card_words and count_words", () => {
  const v = validateIndex(idx());
  const need = requiredStrings(v.symbols);
  for (const k of ["open_statements", "close_statements", "count_statement_one", "count_statement_many", "open_parts", "close_parts"]) assert.ok(need.includes(k), k);
});

/* ------------------------------------------------------------------------------------------------ B: open_words / child_count_words */
test("B: open_words that is not exactly {open, close} of non-empty strings is bad-open-words", () => {
  for (const bad of [[], "open_parts", null, 7, {}, { open: "open_parts" }, { close: "close_parts" }, { open: "open_parts", close: "close_parts", more: "x" },
    { open: "", close: "close_parts" }, { open: "open_parts", close: "" }, { open: 1, close: "close_parts" }, { open: "open_parts", close: ["x"] }]) {
    const i = idx(); i.symbols.kinds.file.open_words = bad;
    refuses(() => validateIndex(i), "bad-open-words");
  }
});
test("B: an open_words key absent from strings is missing-open-words; an empty one is missing-string", () => {
  let i = idx(); i.symbols.kinds.file.open_words = { open: "no_such_word", close: "close_statements" };
  refuses(() => validateIndex(i), "missing-open-words", "no_such_word");
  i = idx(); i.symbols.kinds.file.open_words = { open: "open_statements", close: "no_such_close" };
  refuses(() => validateIndex(i), "missing-open-words", "no_such_close");
  i = idx(); i.strings.open_statements = "";
  refuses(() => validateIndex(i), "missing-string", "open_statements");
});
test("B: child_count_words that is not exactly {one, many} of non-empty strings is bad-count-words; a key absent from strings is missing-count-words", () => {
  for (const bad of [[], "x", null, {}, { one: "count_statement_one" }, { one: "count_statement_one", many: "count_statement_many", few: "x" }, { one: "", many: "count_statement_many" }, { one: "count_statement_one", many: 2 }]) {
    const i = idx(); i.symbols.kinds.file.child_count_words = bad;
    refuses(() => validateIndex(i), "bad-count-words");
  }
  let i = idx(); i.symbols.kinds.file.child_count_words = { one: "no_such_one", many: "count_statement_many" };
  refuses(() => validateIndex(i), "missing-count-words", "no_such_one");
  i = idx(); i.strings.count_statement_many = "";
  refuses(() => validateIndex(i), "missing-string", "count_statement_many");
});
test("B: a kinds row may carry only these keys beside class, text, words, card_words, count_words: any other is extra-key", () => {
  const i = idx(); i.symbols.kinds.file.child_words = { one: "a", many: "b" };
  refuses(() => validateIndex(i), "extra-key");
});

/* ------------------------------------------------------------------------------------------------ D: the strings group */
test("D: with the group on, every one of its keys is known (no extra-string) and all twelve are present", () => {
  const i = idx();
  for (const k of GROUP) assert.ok(typeof i.strings[k] === "string" && i.strings[k] !== "", k);
  assert.doesNotThrow(() => validateIndex(i));
});
test("D: the group partly present is bad-statement-strings naming the first missing key (absent or empty), whichever key is missing", () => {
  for (const k of GROUP) {
    let i = idx(); delete i.strings[k];
    refuses(() => validateIndex(i), "bad-statement-strings", k);
    i = idx(); i.strings[k] = "";
    refuses(() => validateIndex(i), "bad-statement-strings", k);
  }
  const i = idx(); delete i.strings.decl_show_lean; delete i.strings.decl_prompt_note;
  refuses(() => validateIndex(i), "bad-statement-strings", "decl_show_lean");   // the first in the group's order
});
test("D: a map with none of the group's keys and no statement is the live shape (no refusal), and spine_content_label is then an extra-string", () => {
  const i = idx();
  for (const k of GROUP) delete i.strings[k];
  const withLabel = clone(i);
  refuses(() => validateIndex(withLabel), "extra-string", "spine_content_label");
  delete i.strings.spine_content_label;
  assert.doesNotThrow(() => validateIndex(i));
});
test("D: with the group on, spine_content_label must be present, else missing-string", () => {
  const i = idx(); delete i.strings.spine_content_label;
  refuses(() => validateIndex(i), "missing-string", "spine_content_label");
});

/* ------------------------------------------------------------------------------------------------ C: the statement step */
const ctxOf = (i = idx()) => validateIndex(i);
test("C: a full valid statement step is accepted and carried as step.decl", () => {
  const ctx = ctxOf();
  const s = validateStep(stp("fx-thm-a"), ctx);
  assert.deepEqual(s.decl, {
    name: "Fx.foo_bar", sourcePath: "src/New/Fx/File.lean", keyword: "theorem", text: "theorem foo_bar (n : ℕ) : n ≤ n + 1", variables: false,
    usesHere: [], usesElsewhere: [], prompt: stp("fx-thm-a").prompt, heading: stp("fx-thm-a").heading,
  });
  assert.ok(s.note && s.note.text.startsWith("The theorem"), "the note keeps its validation");
  const c = validateStep(stp("fx-def-c"), ctx);
  assert.deepEqual(c.decl.usesHere, ["fx-lem-b"]);
  assert.deepEqual(c.decl.usesElsewhere, [{ name: "New.Other.helper", step: "fx-file-2" }, { name: "Mathlib.Foo.bar" }]);
  assert.ok(!("heading" in c.decl), "no heading key when the data has none");
  const l = validateStep(stp("fx-lem-b"), ctx);
  assert.equal(l.decl.variables, true);
  assert.equal(l.note, undefined, "a statement step may have no note");
});
test("C: the file and group steps of the fixture validate and carry no decl", () => {
  const ctx = ctxOf();
  for (const id of ["fx-group", "fx-stmt-file", "fx-file-2"]) assert.equal(validateStep(stp(id), ctx).decl, undefined, id);
});

const stmtRefusal = (edit, mention) => {
  const s = stp("fx-thm-a"); edit(s);
  refuses(() => validateStep(s, ctxOf()), "bad-statement", mention || "fx-thm-a");
};
test("C: each of the seven keys missing is bad-statement naming the step and that key", () => {
  for (const k of STMT) {
    const s = stp("fx-thm-a"); delete s[k];
    refuses(() => validateStep(s, ctxOf()), "bad-statement", "fx-thm-a");
    refuses(() => validateStep(s, ctxOf()), "bad-statement", k);
  }
});
test("C: a missing key is named first in the seven's order when several are missing", () => {
  const s = stp("fx-thm-a"); delete s.prompt; delete s.variables;
  refuses(() => validateStep(s, ctxOf()), "bad-statement", "variables");
});
test("C: a key beyond the seven and the heading, on a statement step, is bad-statement naming it", () => {
  stmtRefusal((s) => { s.extra_field = 1; }, "extra_field");
});
test("C: name: empty, not a string, or over 300 characters", () => {
  for (const bad of ["", 5, null, "x".repeat(301)]) stmtRefusal((s) => { s.name = bad; });
  const s = stp("fx-thm-a"); s.name = "x".repeat(300);
  assert.doesNotThrow(() => validateStep(s, ctxOf()));
});
test("C: source_path: '..', a leading '/', not .lean, a bad character, empty are refused", () => {
  for (const bad of ["src/../x.lean", "../x.lean", "/src/x.lean", "src/x.txt", "src/x", "x.lean", "src//x.lean", "src/x y.lean", "src/x.lean\n", "", 5, "src/a.b.lean", "src/.lean"])
    stmtRefusal((s) => { s.source_path = bad; });
  const s = stp("fx-thm-a"); s.source_path = "src/New_1/A-b.lean";
  assert.doesNotThrow(() => validateStep(s, ctxOf()));
});
test("C: statement must be exactly {keyword, text}; keyword one of the eight; text 1 to 65536 characters", () => {
  for (const bad of [null, "theorem x", [], {}, { keyword: "theorem" }, { text: "x" }, { keyword: "theorem", text: "x", extra: 1 }])
    stmtRefusal((s) => { s.statement = bad; });
  for (const bad of ["proof", "Theorem", "noncomputable def", "", 5, "example", "axiom"]) stmtRefusal((s) => { s.statement = { keyword: bad, text: "x" }; });
  for (const bad of ["", 5, null, "x".repeat(65537)]) stmtRefusal((s) => { s.statement = { keyword: "theorem", text: bad }; });
  for (const kw of ["theorem", "lemma", "def", "abbrev", "structure", "class", "inductive", "instance"]) {
    const s = stp("fx-thm-a"); s.statement = { keyword: kw, text: "x".repeat(65536) };
    assert.doesNotThrow(() => validateStep(s, ctxOf()), kw);
  }
});
test("C: variables must be a boolean", () => {
  for (const bad of [0, 1, "true", null, [], {}]) stmtRefusal((s) => { s.variables = bad; });
});
test("C: uses_here: not a list, an invalid id, the step's own id, a repeat", () => {
  for (const bad of ["fx-lem-b", null, {}, ["Bad Id"], [5], ["fx-thm-a"], ["fx-lem-b", "fx-lem-b"], ["../x"]]) stmtRefusal((s) => { s.uses_here = bad; });
  const s = stp("fx-thm-a"); s.uses_here = ["fx-lem-b", "fx-def-c"];
  assert.deepEqual(validateStep(s, ctxOf()).decl.usesHere, ["fx-lem-b", "fx-def-c"]);
});
test("C: uses_elsewhere: not a list, an item that is not exactly {name} or {name, step}, a bad name, a bad step id", () => {
  for (const bad of ["x", null, {}, ["x"], [5], [{}], [{ step: "fx-file-2" }], [{ name: "" }], [{ name: 5 }], [{ name: "x".repeat(301) }], [{ name: "a", step: "Bad Id" }],
    [{ name: "a", step: 5 }], [{ name: "a", step: "fx-file-2", extra: 1 }], [{ name: "a", other: 1 }], [{ name: "a", step: "" }]])
    stmtRefusal((s) => { s.uses_elsewhere = bad; });
  const s = stp("fx-thm-a"); s.uses_elsewhere = [{ name: "x".repeat(300) }, { name: "a", step: "fx-file-2" }];
  assert.equal(validateStep(s, ctxOf()).decl.usesElsewhere.length, 2);
});
test("C: prompt: empty, not a string, or over 20000 characters", () => {
  for (const bad of ["", 5, null, "x".repeat(20001)]) stmtRefusal((s) => { s.prompt = bad; });
  const s = stp("fx-thm-a"); s.prompt = "x".repeat(20000);
  assert.doesNotThrow(() => validateStep(s, ctxOf()));
});
test("C: heading: empty, not a string or over 4000 characters on a statement step is bad-statement", () => {
  for (const bad of ["", 5, null, "x".repeat(4001)]) stmtRefusal((s) => { s.heading = bad; });
  const s = stp("fx-thm-a"); s.heading = "x".repeat(4000);
  assert.doesNotThrow(() => validateStep(s, ctxOf()));
});
test("C: a heading on a step with no statement keys is bad-statement", () => {
  const s = stp("fx-stmt-file"); s.heading = "### A heading";
  refuses(() => validateStep(s, ctxOf()), "bad-statement", "fx-stmt-file");
});
test("C: a statement step with children or a child_count above 0 is bad-statement", () => {
  stmtRefusal((s) => { s.card.child_count = 1; s.children = [{ id: "fx-lem-b", title: "`baz`", kind: "lemma", state: "none", proof: "none", child_count: 0, path: ["fx-group", "fx-stmt-file", "fx-thm-a"], parent_rests_on: false }]; });
});
test("C: the note on a statement step keeps its own validation (a bad note is still bad-note)", () => {
  const s = stp("fx-thm-a"); s.note = { text: "", source: "x.lean" };
  refuses(() => validateStep(s, ctxOf()), "bad-note");
});
test("D: a step carrying statement keys while the group is off is bad-statement-strings (and not bad-statement)", () => {
  const i = idx();
  for (const k of GROUP) delete i.strings[k];
  delete i.strings.spine_content_label;
  const ctx = validateIndex(i);
  refuses(() => validateStep(stp("fx-thm-a"), ctx), "bad-statement-strings", "fx-thm-a");
  const s = stp("fx-thm-a"); delete s.prompt;
  refuses(() => validateStep(s, ctx), "bad-statement-strings", "fx-thm-a");
  assert.doesNotThrow(() => validateStep(stp("fx-stmt-file"), ctx));
});

/* ------------------------------------------------------------------------------------------------ the live map is unchanged */
test("the live-shaped indexes (real, skeleton, notes, typeset; no new key) validate to the object they validated to at base, and their steps too", () => {
  const base = read("", "validated-at-base.json");
  for (const dir of ["real", "skeleton", "notes", "typeset"]) {
    const v = validateIndex(read(dir, "index.json"));
    assert.deepEqual(v.symbols.openWords, {}, dir);
    assert.deepEqual(v.symbols.childCountWords, {}, dir);
    const { openWords, childCountWords, ...symbols } = v.symbols;
    assert.deepEqual(JSON.parse(JSON.stringify({ ...v, symbols })), base[dir].index, dir);
    const dirSteps = path.join(FIX, dir, "step");
    for (const id of Object.keys(base[dir].steps)) {
      const got = validateStep(read(dir, "step", id + ".json"), v);
      assert.deepEqual(JSON.parse(JSON.stringify(got)), base[dir].steps[id], dir + "/" + id);
      assert.equal(got.decl, undefined);
    }
    assert.ok(existsSync(dirSteps));
  }
});

/* ------------------------------------------------------------------------------------------------ F: the foot */
const S = { parts_n: "{n} parts", part_one: "1 part", cw1: "{n} child", cwn: "{n} children", ow1: "{n} item", own: "{n} items" };
test("F: footText precedence: the child_kind's count_words, else the card's own kind child_count_words, else parts_n / part_one", () => {
  const countWords = { file: { one: "cw1", many: "cwn" } };
  const childCountWords = { group: { one: "ow1", many: "own" } };
  // 1: the child kind has count_words: it wins over the card's own row
  assert.equal(footText(S, countWords, "file", 3, "group", childCountWords), "3 children");
  assert.equal(footText(S, countWords, "file", 1, "group", childCountWords), "1 child");
  // 2: no child_kind (or one with no count_words): the card's own kind row
  assert.equal(footText(S, countWords, undefined, 3, "group", childCountWords), "3 items");
  assert.equal(footText(S, countWords, undefined, 1, "group", childCountWords), "1 item");
  assert.equal(footText(S, countWords, "theorem", 2, "group", childCountWords), "2 items");
  // 3: neither
  assert.equal(footText(S, countWords, undefined, 3, "part", childCountWords), "3 parts");
  assert.equal(footText(S, countWords, undefined, 1, "part", childCountWords), "1 part");
  assert.equal(footText(S, countWords, undefined, 3), "3 parts");
  assert.equal(footText(S, countWords, undefined, 3, "group", undefined), "3 parts");
});
test("F: the '{n}' of a child_count_words foot is filled as text, whatever the words hold", () => {
  const strings = { ...S, own: "$& {n} $1" };
  assert.equal(footText(strings, {}, undefined, 4, "group", { group: { one: "ow1", many: "own" } }), "$& 4 $1");
});
test("F: makeRenderFace takes the card's own kind row (third parameter, default {}): the statement file's face foot reads '3 statements'", () => {
  const doc = makeFakeDoc();
  const v = validateIndex(idx());
  const face = makeRenderFace(v.strings, v.symbols.countWords, v.symbols.childCountWords);
  const text = (n) => (n.children || []).map((c) => (c.nodeType === 3 ? c.textContent : text(c))).join("");
  const spec = { childCount: 3, data: { title: "Lean file `Fx.File`", kind: "file", state: "none" } };
  // makeRenderFace builds with the page's el(), which needs a document; the face's own test double does it below
  globalThis.document = doc;
  try {
    const foot = (n) => n.children.find((c) => c.attrs && c.attrs.class === "face-foot");
    assert.equal(text(foot(face(spec))), "3 statements");
    assert.equal(text(foot(face({ ...spec, childCount: 1 }))), "1 statement");
    const g = face({ childCount: 2, data: { title: "Group", kind: "group", state: "none", childKind: "file" } });
    assert.equal(text(foot(g)), "2 files");
    assert.equal(text(foot(makeRenderFace(v.strings, v.symbols.countWords)(spec))), "3 parts", "with no third argument the foot is the parts foot");
  } finally { delete globalThis.document; }
});

/* ------------------------------------------------------------------------------------------------ E: the parts label */
test("E: partsWords: the open_words row's strings when the kind has one, else open_parts / close_parts exactly as today", () => {
  const strings = { open_parts: "Open its parts", close_parts: "Close its parts", open_statements: "Open its statements", close_statements: "Close its statements" };
  const ow = { file: { open: "open_statements", close: "close_statements" } };
  assert.deepEqual(partsWords(strings, ow, "file"), { open: "Open its statements", close: "Close its statements" });
  assert.deepEqual(partsWords(strings, ow, "group"), { open: "Open its parts", close: "Close its parts" });
  assert.deepEqual(partsWords(strings, {}, "file"), { open: "Open its parts", close: "Close its parts" });
  assert.deepEqual(partsWords(strings, undefined, "file"), { open: "Open its parts", close: "Close its parts" });
  assert.deepEqual(partsWords(strings, ow, "constructor"), { open: "Open its parts", close: "Close its parts" });
  assert.deepEqual(partsWords(strings, { group: { open: "open_parts", close: "close_parts" } }, "group"), { open: "Open its parts", close: "Close its parts" });
});

/* ------------------------------------------------------------------------------------------------ H: statement.js */
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
const decl = (extra = {}) => ({ name: "Fx.foo_bar", sourcePath: "src/New/Fx/File.lean", keyword: "theorem", text: "theorem foo_bar : True", variables: false,
  usesHere: [], usesElsewhere: [], prompt: "P", ...extra });
const STR = { ...Object.fromEntries(GROUP.map((k) => [k, "[" + k + "]"])), spine_content_label: "[label]", decl_uses_here: "Uses here ({n})", decl_uses_elsewhere: "Uses elsewhere ({n})" };
function build(over = {}) {
  const doc = richDoc();
  const el = makeEl(doc);
  const win = over.win || { navigator: {}, getSelection: () => ({ selectAllChildren() {} }) };
  doc.defaultView = win;
  const ctl = new AbortController();
  globalThis.document = doc;
  const out = buildStatement({ strings: STR, decl: decl(over.decl), hasNote: over.hasNote ?? true, titleOf: over.titleOf || (() => undefined), el, doc, signal: ctl.signal, typeset: !!over.typeset });
  return { out, doc, el, ctl, win };
}
test("H: the builder returns lead and tail node arrays; the cards' pieces are in the H order, name first and the prompt note last", () => {
  const { out } = build({ decl: { heading: "### Section\n\nText." } });
  try {
    assert.deepEqual(out.lead.map(cls), ["decl-name", "decl-heading"]);
    assert.deepEqual(out.tail.map(cls), ["decl-lean", "decl-uses decl-uses-here", "decl-uses decl-uses-elsewhere", "decl-prompt"]);
    const all = walk({ children: out.lead.concat(out.tail) });
    const at = (c) => all.findIndex((n) => cls(n).split(" ").includes(c));
    for (const [a, b] of [["decl-name", "decl-heading"], ["decl-heading", "decl-lean"], ["decl-lean", "decl-uses-here"], ["decl-uses-here", "decl-uses-elsewhere"], ["decl-uses-elsewhere", "decl-prompt"]])
      assert.ok(at(a) >= 0 && at(a) < at(b), a + " before " + b);
    assert.equal(textOf(out.lead[0]), "Fx.foo_bar");
    assert.equal(out.lead[0].children[0].tagName, "CODE", "the full name is in <code>");
    assert.equal(textOf(out.lead[1].children[0]), "[decl_heading_label]", "the label line first");
    assert.ok(textOf(out.lead[1]).includes("Section"));
    assert.equal(cls(out.tail[3].children[out.tail[3].children.length - 1]), "decl-prompt-note");
    assert.equal(textOf(out.tail[3].children[out.tail[3].children.length - 1]), "[decl_prompt_note]");
  } finally { delete globalThis.document; }
});
test("H: no heading, no heading block; with no note the lead carries the label line then the decl_no_note paragraph; with a note it does not", () => {
  const a = build({ hasNote: false });
  try {
    assert.deepEqual(a.out.lead.map(cls), ["decl-name", "note-label", "decl-no-note"]);
    assert.equal(textOf(a.out.lead[1]), "[label]");
    assert.equal(textOf(a.out.lead[2]), "[decl_no_note]");
    const b = build({ hasNote: true });
    assert.deepEqual(b.out.lead.map(cls), ["decl-name"]);
  } finally { delete globalThis.document; }
});
test("H: the Lean button toggles the code and aria-expanded; the variables note shows and hides with the code and only when variables is true", () => {
  for (const variables of [false, true]) {
    const { out } = build({ decl: { variables, text: "lemma x := <script>alert(1)</script> {page_url}" } });
    try {
      const nodes = walk(out.tail[0]);
      const btn = nodes.find((n) => n.tagName === "BUTTON");
      assert.equal(cls(btn), "sheet-tool");
      assert.equal(btn.attrs["aria-expanded"], "false");
      assert.equal(textOf(btn), "[decl_show_lean]");
      const code = nodes.find((n) => n.tagName === "CODE");
      assert.equal(code.children.length, 1);
      assert.equal(code.children[0].nodeType, 3, "the statement is ONE text node");
      assert.equal(code.children[0].textContent, "lemma x := <script>alert(1)</script> {page_url}");
      const pre = nodes.find((n) => n.tagName === "PRE");
      assert.ok(pre.children.includes(code));
      const body = out.tail[0].children.find((c) => cls(c) === "decl-lean-body");
      assert.equal(body.hidden, true);
      const note = nodes.find((n) => cls(n) === "decl-lean-note");
      assert.equal(!!note, variables);
      if (note) assert.equal(textOf(note), "[decl_lean_note]");
      btn.listeners.find((l) => l.type === "click").fn();
      assert.equal(btn.attrs["aria-expanded"], "true");
      assert.equal(textOf(btn), "[decl_hide_lean]");
      assert.equal(body.hidden, false);
      btn.listeners.find((l) => l.type === "click").fn();
      assert.equal(btn.attrs["aria-expanded"], "false");
      assert.equal(textOf(btn), "[decl_show_lean]");
      assert.equal(body.hidden, true);
    } finally { delete globalThis.document; }
  }
});
test("H: uses lists: {n} filled as text, links href '#id' with the title as known (code span as <code>) or the bare id, elsewhere names in <code> and linked only with a step; an empty list has its heading with 0 and no <ul>", () => {
  const titles = { "fx-lem-b": "`baz`" };
  const { out } = build({ decl: { usesHere: ["fx-lem-b", "fx-unknown"], usesElsewhere: [{ name: "A.b", step: "fx-file-2" }, { name: "Mathlib.x" }] }, titleOf: (id) => titles[id] });
  try {
    const here = out.tail[1], else_ = out.tail[2];
    assert.equal(textOf(here.children[0]), "Uses here (2)");
    const links = walk(here).filter((n) => n.tagName === "A");
    assert.deepEqual(links.map((a) => a.attrs.href), ["#fx-lem-b", "#fx-unknown"]);
    assert.equal(links[0].children[0].tagName, "CODE");
    assert.equal(textOf(links[0]), "baz");
    assert.equal(textOf(links[1]), "fx-unknown");
    assert.equal(textOf(else_.children[0]), "Uses elsewhere (2)");
    const items = walk(else_).filter((n) => n.tagName === "LI");
    assert.equal(items.length, 2);
    assert.equal(walk(items[0]).filter((n) => n.tagName === "A").length, 1);
    assert.equal(walk(items[0]).filter((n) => n.tagName === "A")[0].attrs.href, "#fx-file-2");
    assert.equal(walk(items[0]).find((n) => n.tagName === "CODE").children[0].textContent, "A.b");
    assert.equal(walk(items[1]).filter((n) => n.tagName === "A").length, 0);
    assert.equal(walk(items[1]).find((n) => n.tagName === "CODE").children[0].textContent, "Mathlib.x");
    const e = build({});
    assert.equal(textOf(e.out.tail[1].children[0]), "Uses here (0)");
    assert.equal(walk(e.out.tail[1]).filter((n) => n.tagName === "UL").length, 0);
    assert.equal(textOf(e.out.tail[2].children[0]), "Uses elsewhere (0)");
    assert.equal(walk(e.out.tail[2]).filter((n) => n.tagName === "UL").length, 0);
  } finally { delete globalThis.document; }
});
test("H: the prompt and the statement text come out as literal text: '<script>alert(1)</script>' and '{page_url}' are text nodes, never parsed or filled", () => {
  const hostile = "<script>alert(1)</script> {page_url} <b>x</b> &amp;";
  const { out } = build({ decl: { prompt: hostile, text: hostile, name: hostile, heading: hostile, usesElsewhere: [{ name: hostile }] } });
  try {
    const all = walk({ children: out.lead.concat(out.tail) });
    assert.ok(!all.some((n) => n.tagName === "SCRIPT" || n.tagName === "B"), "no element came from the text");
    const texts = all.filter((n) => n.nodeType === 3).map((n) => n.textContent);
    assert.ok(texts.filter((t) => t === hostile).length >= 3, "the prompt, the statement and the name each hold the exact text in one text node: " + texts.length);
    const pre = all.find((n) => cls(n) === "decl-prompt-text");
    assert.equal(pre.tagName, "PRE");
    assert.equal(pre.children.length, 1);
    assert.equal(pre.children[0].textContent, hostile);
    assert.equal(pre.hidden, true, "the prompt block starts hidden");
  } finally { delete globalThis.document; }
});
const flush = () => new Promise((r) => setTimeout(r, 0));
test("H: copy resolved: writeText gets the prompt exactly, the role=status line shows decl_prompt_copied, the fallback block stays hidden", async () => {
  const calls = [];
  const win = { navigator: { clipboard: { writeText: (t) => { calls.push(t); return Promise.resolve(); } } }, getSelection: () => ({ selectAllChildren() { throw new Error("no selection on success"); } }) };
  const { out } = build({ decl: { prompt: "the <b>prompt</b>\nline 2" }, win });
  try {
    const nodes = walk(out.tail[3]);
    const btn = nodes.find((n) => n.tagName === "BUTTON");
    assert.equal(cls(btn), "sheet-tool");
    assert.equal(textOf(btn), "[decl_prompt_button]");
    const status = nodes.find((n) => n.attrs && n.attrs.role === "status");
    assert.ok(status && textOf(status) === "");
    btn.listeners.find((l) => l.type === "click").fn();
    await flush();
    assert.deepEqual(calls, ["the <b>prompt</b>\nline 2"]);
    assert.equal(textOf(status), "[decl_prompt_copied]");
    assert.equal(nodes.find((n) => cls(n) === "decl-prompt-text").hidden, true);
  } finally { delete globalThis.document; }
});
test("H: copy rejected, or no clipboard API at all: the fallback <pre> is shown with the prompt and its contents selected; nothing thrown or logged", async () => {
  for (const clipboard of [{ writeText: () => Promise.reject(new Error("denied")) }, { writeText: () => { throw new Error("sync"); } }, undefined]) {
    const selected = [];
    const win = { navigator: { clipboard }, getSelection: () => ({ selectAllChildren: (n) => selected.push(n) }) };
    const { out } = build({ decl: { prompt: "P2" }, win });
    const seen = [];
    const orig = console.error; console.error = (...a) => seen.push(a);
    try {
      const nodes = walk(out.tail[3]);
      const btn = nodes.find((n) => n.tagName === "BUTTON");
      const pre = nodes.find((n) => cls(n) === "decl-prompt-text");
      btn.listeners.find((l) => l.type === "click").fn();
      await flush();
      assert.equal(pre.hidden, false);
      assert.equal(pre.children[0].textContent, "P2");
      assert.deepEqual(selected, [pre]);
      assert.equal(textOf(nodes.find((n) => n.attrs && n.attrs.role === "status")), "", "no 'copied' line on failure");
      assert.deepEqual(seen, []);
    } finally { console.error = orig; delete globalThis.document; }
  }
});
test("H: every listener the builder adds carries the page's abort signal", () => {
  const { out, ctl } = build({ decl: { usesHere: ["fx-lem-b"] } });
  try {
    const bs = walk({ children: out.lead.concat(out.tail) }).filter((n) => n.listeners && n.listeners.length);
    assert.ok(bs.length >= 2);
    for (const n of bs) for (const l of n.listeners) assert.equal(l.opts && l.opts.signal, ctl.signal);
  } finally { delete globalThis.document; }
});
