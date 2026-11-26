/* The maths face sets superscripts and subscripts: the contract C1-C7 and the grammar G1-G5, one case per clause, success AND refusal.
   Synthetic spans only. The real-span population is read from fixtures/note-spans-classes.json and never copied. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { makeFakeDoc } from "./fakedoc.mjs";
import { makeEl, TAGS } from "../dom.js";
import * as NOTE from "../note.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const mk = () => makeEl(makeFakeDoc());
const maths = (text) => NOTE.renderNote(text, mk(), true);

/* A compact picture: tag.class(children); a text node as a JSON string. */
function ser(n) {
  if (n.nodeType === 3) return JSON.stringify(n.textContent);
  const c = n.attrs.class ? "." + n.attrs.class : "";
  return n.tagName.toLowerCase() + c + "(" + n.children.map(ser).join("|") + ")";
}
function walk(n, f) { f(n); for (const c of n.children || []) walk(c, f); }
function flat(n) { let s = ""; walk(n, (x) => { if (x.nodeType === 3) s += x.textContent; }); return s; }
const spanOf = (span) => maths("`" + span + "`").children[0].children[0];   // the one backtick span of a one-span paragraph, as drawn

/* THE ORACLE for C5: the characters a SET span loses, computed from the span's own text (never from the renderer or from scriptParts):
   each ^ or _; the spaces directly before and after a ^; the { } of an operand directly after a script character; the ( ) of an operand of ^
   (after optional spaces). It walks the span once, left to right, marking indexes to drop. */
function expectedFlatten(span) {
  const cs = [...span], drop = new Set();
  const closeOf = (i) => {
    const pairs = { "(": ")", "[": "]", "{": "}" };
    const stack = [];
    for (let k = i; k < cs.length; k++) {
      if (pairs[cs[k]]) stack.push(pairs[cs[k]]);
      else if (cs[k] === ")" || cs[k] === "]" || cs[k] === "}") { if (stack.pop() !== cs[k]) return -1; if (stack.length === 0) return k; }
    }
    return -1;
  };
  for (let i = 0; i < cs.length; i++) {
    if (cs[i] !== "^" && cs[i] !== "_") continue;
    drop.add(i);
    let j = i + 1;
    if (cs[i] === "^") {
      for (let k = i - 1; k >= 0 && cs[k] === " "; k--) drop.add(k);
      while (cs[j] === " ") { drop.add(j); j++; }
    }
    if (cs[j] === "{" || (cs[i] === "^" && cs[j] === "(")) { drop.add(j); drop.add(closeOf(j)); }
  }
  return cs.filter((_, i) => !drop.has(i)).join("");
}
/* The second control on C5: whatever was lost is a script character, a space, a brace or a paren, and nothing was reordered. */
function onlyAllowedLoss(span, out) {
  const cs = [...span], os = [...out];
  let j = 0;
  for (const c of cs) {
    if (j < os.length && os[j] === c) { j++; continue; }
    if (!"^_ {}()".includes(c)) return false;
  }
  return j === os.length;
}

/* The picture of a parse (scriptParts' parts), in the same notation as ser(): the children of a set span.m, a text as a JSON string. */
const pp = (parts) => parts.map((p) => (typeof p === "string" ? JSON.stringify(p) : p.tag + "(" + pp(p.children) + ")")).join("|");
const flatParts = (parts) => parts.map((p) => (typeof p === "string" ? p : flatParts(p.children))).join("");

/* [span, the children of the set span]. Not every span here is a formula by the class rule (C1: `a_i` is an identifier token, so `x^{a_i}` is a
   name-in-formula and stays code on the page); the parse is tested on all of them through scriptParts, the drawing on the formula ones. */
const SET = [
  ["y ^ 12", '"y"|sup("12")'],                         // G2c, spaces round ^ dropped
  ["x^10", '"x"|sup("10")'],
  ["3 s ^ 7", '"3 s"|sup("7")'],                       // the base is only the character before; the rest stays text
  ["x ^ (a + b)", '"x"|sup("a + b")'],                 // G2b, ruling B: parens dropped, inner spaces stay
  ["x^(a+b)", '"x"|sup("a+b")'],
  ["Y_{j-1}", '"Y"|sub("j-1")'],                       // G2a
  ["κ_{i - 1/2}", '"κ"|sub("i - 1/2")'],
  ["P_δ^N", '"P"|sub("δ")|sup("N")'],                  // G4: one sub then one sup on one base
  ["P^N_δ", '"P"|sup("N")|sub("δ")'],                  // a sup then a sub
  ["P_δ ^ N", '"P"|sub("δ")|sup("N")'],
  ["K^×", '"K"|sup("×")'],                             // G2d, ruling C: the seven symbols
  ["K^*", '"K"|sup("*")'],
  ["K^+", '"K"|sup("+")'],
  ["K^-", '"K"|sup("-")'],
  ["K^∨", '"K"|sup("∨")'],
  ["K^∞", '"K"|sup("∞")'],
  ["K^⊥", '"K"|sup("⊥")'],
  ["K^× y", '"K"|sup("×")|" y"'],                      // a symbol followed by a space
  ["(K^×)", '"("|"K"|sup("×")|")"'],                   // a symbol followed by a closing bracket
  ["K_*", '"K"|sub("*")'],
  ["x^{a_i}", '"x"|sup("a"|sub("i"))'],                // G3: two levels
  ["x^(a_i)", '"x"|sup("a"|sub("i"))'],
  ["x_{a^b}", '"x"|sub("a"|sup("b"))'],
  ["x^{a_i} + 1", '"x"|sup("a"|sub("i"))|" + 1"'],     // G5: spaces after an operand stay
  ["x^{α_i}", '"x"|sup("α"|sub("i"))'],                // the same, with a letter that keeps the span a formula
  ["x^(α_i)", '"x"|sup("α"|sub("i"))'],
  ["x_{α^b}", '"x"|sub("α"|sup("b"))'],
  ["x^{α_i} + 1", '"x"|sup("α"|sub("i"))|" + 1"'],
  ["x^α_{i}", '"x"|sup("α")|sub("i")'],
  ["x^2 + y^2", '"x"|sup("2")|" + y"|sup("2")'],
  ["x_1", '"x"|sub("1")'],
  ["x₁^2", '"x₁"|sup("2")'],                           // a subscript digit is a base and a word character
  ["x^q₁", '"x"|sup("q₁")'],
  ["x'^2", '"x\'"|sup("2")'],                          // a prime is a base
  ["x^2′", '"x"|sup("2′")'],                           // and a word character
  ["(a+b)^2", '"(a+b)"|sup("2")'],                     // a closing bracket is a base
  ["[a]_i", '"[a]"|sub("i")'],
  ["{a}^2", '"{a}"|sup("2")'],
  ["f(x)^2", '"f(x)"|sup("2")'],
  ["x^{a}_{b}", '"x"|sup("a")|sub("b")'],
  ["x_{a} ^ 2", '"x"|sub("a")|sup("2")'],
];
const REFUSED = [
  "x^-1", "x^**", "x^×+", "x^+1",             // G2d: a symbol must be the whole operand; two symbols
  "a ^ b ^ c", "a^b^c", "a ^ b ^ c ^ d",      // G4 chain of ^
  "a_b_c", "x_a_b",                           // G4 chain of _
  "x^a_b^c",                                  // two sups on one base (a ^ run)
  "x^{a^{b_c}}", "x_{a_{b_c}}", "x^(a_(b_c))", // G3: a third level
  "^x", "_x", "x ^", "x^", "x_", "x ^ ",      // G1/G2: no base; no operand
  " ^x", "+^x", "x +^2", "a b_ ^",
  "x_ i", "x_ 1",                             // G2c: no space after _
  "x^{}", "x^()", "x_{}",                     // G4: empty groups
  "x^{a", "x^(a", "x^a}", "x^{a)", "x^{(a}b)", "x^{[a}]", // G4: unmatched or crossing brackets
  "x_(a)", "x_[a]", "x^[a]",                  // G2: no such operand
  "x ^ {a}", "x ^{a}",                        // (a) braces are DIRECTLY after the script character
  "x^{_a}", "x^{ ^a}",                        // a group's content has its own bases
  "x^{a}}", "x^{a} ^ b",                      // a following ^ after a group
  "x^2̄", "x_i̅",                   // a combining mark after an operand would attach to the wrong letter
  "x ^ ^ y",
];
const NO_SCRIPT = ["x + y", "f(x)", "a ⊥ b", "∑ a₁", "x{a}", "(a)"];

test("C3: every set span parses to exactly the stated children; C4 and C5 hold on each parse", () => {
  for (const [span, want] of SET) {
    const parts = NOTE.scriptParts(span);
    assert.ok(parts !== null, "scriptParts " + span);
    assert.equal(pp(parts), want, span);
    const got = flatParts(parts);
    assert.ok(!/[\^_]/.test(got), "C4 " + span);
    assert.equal(got, expectedFlatten(span), "C5 " + span);
    assert.ok(onlyAllowedLoss(span, got), "C5 loss " + span);
  }
});

test("C3: a set formula span is DRAWN as span.m holding those children (sup and sub elements, text nodes); the other classes stay code as typed", () => {
  let drawn = 0;
  for (const [span, want] of SET) {
    const n = spanOf(span);
    if (NOTE.spanClass(span) === "formula") {
      drawn++;
      assert.equal(ser(n), "span.m(" + want + ")", span);
      assert.ok(!/[\^_]/.test(flat(n)), "C4 " + span);
      assert.equal(flat(n), expectedFlatten(span), "C5 " + span);
    } else {
      assert.equal(ser(n), "code(" + JSON.stringify(span) + ")", span);
    }
  }
  assert.ok(drawn >= 30, "drawn " + drawn);
});

test("C3: a refused span is code, as typed, ONE text node, never half set; scriptParts says null", () => {
  for (const span of REFUSED) {
    assert.equal(NOTE.scriptParts(span), null, "scriptParts " + JSON.stringify(span));
    assert.equal(ser(spanOf(span)), "code(" + JSON.stringify(span) + ")", JSON.stringify(span));
  }
});

test("C2: a formula span with no ^ and no _ is drawn as before: span.m with ONE text node", () => {
  for (const span of NO_SCRIPT) {
    assert.equal(NOTE.spanClass(span), "formula", span);
    assert.equal(ser(spanOf(span)), "span.m(" + JSON.stringify(span) + ")", span);
  }
  assert.equal(ser(spanOf("x")), 'span.m m1("x")');       // one letter: unchanged
  assert.equal(ser(spanOf("κ")), 'span.m m1("κ")');
});

test("C1: only a 'formula' span is ever parsed: a name, a name with arguments and a name in a formula stay code, as typed", () => {
  for (const span of ["foo_bar", "foo_bar^2", "foo x_i", "foo x^2", "x_i + foo"]) {
    assert.notEqual(NOTE.spanClass(span), "formula", span);
    assert.equal(ser(spanOf(span)), "code(" + JSON.stringify(span) + ")", span);
  }
  assert.equal(NOTE.spanClass("foo_bar"), "name");
  assert.equal(NOTE.spanClass("foo x_i"), "name-with-arguments");
  assert.equal(NOTE.spanClass("foo x^2"), "name-in-formula");
  assert.equal(NOTE.spanClass("x_i"), "name");             // the classes themselves are unchanged (`_` is an identifier character)
  assert.equal(ser(spanOf("x_i")), 'code("x_i")');
  assert.equal(ser(spanOf("x^{a_i}")), 'code("x^{a_i}")');
  assert.equal(NOTE.oneLetter("x"), true);
  assert.equal(NOTE.oneLetter("xy"), false);
});

test("C3: scriptParts is exported and returns the parts (text strings and {tag, children}), or null", () => {
  assert.equal(typeof NOTE.scriptParts, "function");
  assert.deepEqual(NOTE.scriptParts("P_δ^N"), ["P", { tag: "sub", children: ["δ"] }, { tag: "sup", children: ["N"] }]);
  assert.deepEqual(NOTE.scriptParts("x^{a_i}"), ["x", { tag: "sup", children: ["a", { tag: "sub", children: ["i"] }] }]);
  assert.equal(NOTE.scriptParts("x^-1"), null);
});

test("C3: a set span is span.m with the class m only; sup and sub carry NO attributes; the nesting is at most two levels", () => {
  const n = spanOf("x^{α_i} + K_γ^M");
  assert.equal(n.attrs.class, "m");
  walk(n, (x) => { if (x.nodeType === 1 && (x.tagName === "SUP" || x.tagName === "SUB")) assert.deepEqual(x.attrs, {}); });
  let deepest = 0;
  const depth = (x, d) => { if (x.nodeType !== 1) return; const e = (x.tagName === "SUP" || x.tagName === "SUB") ? d + 1 : d; deepest = Math.max(deepest, e); for (const c of x.children) depth(c, e); };
  depth(n, 0);
  assert.equal(deepest, 2);
});

test("the maths face is the same in a heading, a list item and a table cell as in a paragraph", () => {
  const f = maths("# h `x ^ 2`\n\n* item `P_δ^N`\n\n| a | `K^×` |\n|---|---|\n| `x^-1` | `y_{1}` |\n");
  const all = f.children.map(ser).join("\n");
  assert.ok(all.includes('h3.note-h("h "|span.m("x"|sup("2")))'), all);
  assert.ok(all.includes('li("item "|span.m("P"|sub("δ")|sup("N")))'), all);
  assert.ok(all.includes('th(span.m("K"|sup("×")))'), all);
  assert.ok(all.includes('td(code("x^-1"))'), all);
  assert.ok(all.includes('td(span.m("y"|sub("1")))'), all);
});

test("C6: the non-maths view and the exact view are untouched", () => {
  const text = "a `y ^ 12` b `P_δ^N` c `x^-1` d\n";
  const plain = NOTE.renderNote(text, mk()).children.map(ser).join("");
  assert.equal(plain, 'p("a "|code("y ^ 12")|" b "|code("P_δ^N")|" c "|code("x^-1")|" d")');
  assert.equal(NOTE.renderNote(text, mk(), false).children.map(ser).join(""), plain);
  const ex = NOTE.exactNote(text, mk());
  assert.equal(ser(ex), "pre(" + JSON.stringify(text) + ")");
  assert.equal(ex.children.length, 1);
});

test("C7: dom.js TAGS gains sup and sub, and nothing else", () => {
  assert.ok(TAGS.includes("sup") && TAGS.includes("sub"));
  assert.deepEqual([...TAGS].filter((t) => !["div", "span", "button", "nav", "ol", "ul", "li", "p", "h2", "code", "h3", "h4", "h5", "pre", "table", "thead", "tbody", "tr", "th", "td"].includes(t)), ["sup", "sub"]);
});

/* ---------------------------------------------------------------- the population: every real span, from the committed class file, read only */
const SPANS = JSON.parse(readFileSync(path.join(HERE, "fixtures", "note-spans-classes.json"), "utf8")).spans;

test("population: C4 holds on every real span in the maths face; C5 on every set formula span; a refused one is code as typed; counts printed", () => {
  let set = 0, refused = 0, noScript = 0, formulas = 0;
  const bad = [];
  for (const row of SPANS) {
    const span = row.span;
    const frag = maths("`" + span + "`");
    const only = frag.children[0] && frag.children[0].children;
    if (!only || only.length !== 1 || only[0].nodeType !== 1) { bad.push("shape"); continue; }   // every span is the one child of its paragraph
    const n = only[0];
    if (n.tagName === "SPAN" && /[\^_]/.test(flat(n))) bad.push("C4");                          // on every class: the maths face never shows ^ or _
    if (row.class !== "formula") continue;
    formulas++;
    if (NOTE.spanClass(span) !== "formula") bad.push("class");
    if (!/[\^_]/.test(span)) {
      noScript++;
      if (ser(n) !== "span.m" + (NOTE.oneLetter(span) ? " m1" : "") + "(" + JSON.stringify(span) + ")") bad.push("C2");
    } else if (n.tagName === "CODE") {
      refused++;
      if (ser(n) !== "code(" + JSON.stringify(span) + ")" || NOTE.scriptParts(span) !== null) bad.push("refused");
    } else {
      set++;
      const got = flat(n);
      if (n.tagName !== "SPAN" || got !== expectedFlatten(span) || !onlyAllowedLoss(span, got)) bad.push("C5");
      if (NOTE.scriptParts(span) === null) bad.push("parts");
    }
  }
  console.log("population (distinct formula spans): %d total; set %d; refused %d; no-script %d", formulas, set, refused, noScript);
  assert.deepEqual(bad, []);
  assert.equal(set + refused + noScript, formulas);
  assert.ok(set > 0 && refused > 0 && noScript > 0);
});
