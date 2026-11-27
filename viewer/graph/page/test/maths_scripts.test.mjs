/* The maths face sets superscripts and subscripts: the contract C1-C7 and the grammar G1-G5, one case per clause, success AND refusal.
   Synthetic spans only. The real-span population is read from fixtures/note-spans-classes.json and never copied. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { pathToFileURL } from "node:url";
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
  ["(K^×)", '"(K"|sup("×")|")"'],                   // a symbol followed by a closing bracket
  ["K_*", '"K"|sub("*")'],
  ["x ^{a}", '"x"|sup("a")'],                          // the spaces are BEFORE the ^: dropped; the brace is directly after it
  ["x^{a}}", '"x"|sup("a")|"}"'],
  ["x^a}", '"x"|sup("a")|"}"'],                       // a bracket outside an operand group is plain text (G4 speaks of operand groups only)
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
  "x^=", "x^/ y", "x^!)", "x_<", "x^†", "x_.",  // G2d: a lone character that is not one of the seven is no operand
  "a ^ b ^ c", "a^b^c", "a ^ b ^ c ^ d",      // G4 chain of ^
  "a_b_c", "x_a_b",                           // G4 chain of _
  "x^a_b^c",                                  // two sups on one base (a ^ run)
  "x^{a^{b_c}}", "x_{a_{b_c}}", "x^(a_(b_c))", // G3: a third level
  "^x", "_x", "x ^", "x^", "x_", "x ^ ",      // G1/G2: no base; no operand
  " ^x", "+^x", "x +^2", "a b_ ^",
  "x_ i", "x_ 1",                             // G2c: no space after _
  "x^{}", "x^()", "x_{}",                     // G4: empty groups
  "x^{a", "x^(a", "x^{a)", "x^{(a}b)", "x^{[a}]", // G4: unmatched or crossing brackets
  "x_(a)", "x_[a]", "x^[a]",                  // G2: no such operand
  "x ^ {a}", "x ^ \u00d7 y",                  // (a) braces and (d) a symbol are DIRECTLY after the script character
  "x^{_a}", "x^{ ^a}",                        // a group's content has its own bases
  "x^{a} ^ b", "x^{a}^b",                     // a following ^ after a group
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
  assert.deepEqual([...TAGS].filter((t) => !["div", "span", "button", "nav", "ol", "ul", "li", "p", "h2", "code", "h3", "h4", "h5", "pre", "table", "thead", "tbody", "tr", "th", "td"].includes(t)), ["a", "sup", "sub"]);   // `a`: the statement card's one link (dom.js, amendment 1)
});

/* ---------------------------------------------------------------- fold 1 (rulings 39389, 39396, 39398). Synthetic spans only; marks are written as \u escapes. */
const M1 = "̄", M2 = "̈", M3 = "̂", M4 = "̃";   // combining macron, diaeresis, circumflex, tilde

/* F1: a base may be a LETTER followed by combining marks; the mark belongs to the letter and the script is drawn after both. */
const SET_MARKS = [
  ["X" + M1 + "_ℓ", '"X' + M1 + '"|sub("ℓ")'],
  ["a" + M1 + "^2", '"a' + M1 + '"|sup("2")'],
  ["y" + M3 + " ^ 3", '"y' + M3 + '"|sup("3")'],                 // the spaces before a ^ are dropped, the mark stays on its letter
  ["b" + M4 + "_{i-1}", '"b' + M4 + '"|sub("i-1")'],
  ["x" + M2 + M1 + "_i", '"x' + M2 + M1 + '"|sub("i")'],       // two marks on one letter
];
test("F1: a letter with combining marks is a base; the marks stay on the letter and the script follows both (C4, C5 on each)", () => {
  for (const [span, want] of SET_MARKS) {
    const parts = NOTE.scriptParts(span);
    assert.ok(parts !== null, "scriptParts " + JSON.stringify(span));
    assert.equal(pp(parts), want, JSON.stringify(span));
    const got = flatParts(parts);
    assert.ok(!/[\^_]/.test(got), "C4 " + JSON.stringify(span));
    assert.equal(got, expectedFlatten(span), "C5 " + JSON.stringify(span));
    assert.ok(onlyAllowedLoss(span, got), "C5 loss " + JSON.stringify(span));
    if (NOTE.spanClass(span) === "formula") assert.equal(ser(spanOf(span)), "span.m(" + want + ")", JSON.stringify(span));
  }
});
const REFUSED_MARKS = [
  M1 + "_x", M1 + "^2",                     // a mark run at the span's start is no base
  "2" + M1 + "_x", "2" + M1 + " ^ 3",       // a digit then a mark
  ")" + M1 + "_x", ")" + M1 + "^2",         // a closing bracket then a mark
  " " + M1 + "_x",                          // a space then a mark
];
test("F1: a mark run that does not start at a letter is still no base: refused, drawn as code, as typed", () => {
  for (const span of REFUSED_MARKS) {
    assert.equal(NOTE.scriptParts(span), null, "scriptParts " + JSON.stringify(span));
    assert.equal(ser(spanOf(span)), "code(" + JSON.stringify(span) + ")", JSON.stringify(span));
  }
});

/* F2a: a combining mark directly after ANY operand is refused (it would attach to the wrong glyph). */
const REFUSED_AFTER_OPERAND = [
  "x^{a}" + M1,                             // after a {...} group
  "x ^ (a)" + M1,                           // after a ^(...) group
  "x^×" + M1,                               // after a symbol
  "x^a" + M1, "x_i" + M1,                   // after a word (already refused before the fold)
];
test("F2a: a combining mark directly after an operand (group, parenthesised group, symbol, word) refuses the span", () => {
  for (const span of REFUSED_AFTER_OPERAND) {
    assert.equal(NOTE.scriptParts(span), null, "scriptParts " + JSON.stringify(span));
    assert.equal(ser(spanOf(span)), "code(" + JSON.stringify(span) + ")", JSON.stringify(span));
  }
});

/* F3: a ^ whose BASE WORD follows another word (or a closing bracket) and a space is refused. THE 13 REFUSED SHAPES:
   (1) (g k ^ d)⁻¹   (2) φ (t + 1) ≡ φ t ^ Q   (3) 2 q ^ 2   (4) 400 q ^ 3 + B   (5) μ Z ^ (q + 1)   (6) a Ê ^ (σ × σ')   (7) w Ê^ν
   (8) (ρ θ^t)⁻¹   (9) x y ^ k   (10) σ ^ (m + 4) E ζ ^ (-k)   (11) κ ≤ 2 q ^ 2   (12) z w^C   (13) 5 m₀ 2 ^ t
   (1) and (2) read falsely in Lean syntax, where an application binds tighter than ^; the other eleven read correctly but cannot be told from them by syntax. */
const JUXTAPOSED = [
  "(g k ^ d)⁻¹", "φ (t + 1) ≡ φ t ^ Q",
  "2 q ^ 2", "400 q ^ 3 + B", "μ Z ^ (q + 1)", "a Ê ^ (σ × σ')", "w Ê^ν", "(ρ θ^t)⁻¹", "x y ^ k",
  "σ ^ (m + 4) E ζ ^ (-k)", "κ ≤ 2 q ^ 2", "z w^C", "5 m₀ 2 ^ t",
];
test("F3: the juxtaposed-power list has 13 distinct shapes", () => {
  assert.equal(new Set(JUXTAPOSED).size, 13);
});
for (const span of JUXTAPOSED) {
  test("F3 refused: " + JSON.stringify(span), () => {
    assert.equal(NOTE.scriptParts(span), null);
    assert.equal(ser(spanOf(span)), "code(" + JSON.stringify(span) + ")");
  });
}
/* A combining mark on the base word counts as part of the word (the same shape as (6) and (7), with a mark on the base). */
test("F3 refused: the base word keeps its combining marks", () => {
  for (const span of ["a E" + M1 + " ^ 2", "w y" + M3 + "^3"]) assert.equal(NOTE.scriptParts(span), null, JSON.stringify(span));
});
const STILL_SET = [
  ["y = x ^ 2", '"y = x"|sup("2")'],                  // an operator and a space before the base word
  ["(x ^ 2)", '"(x"|sup("2")|")"'],                   // a bracket directly before the base word
  ["(g k)^d", '"(g k)"|sup("d")'],                    // a closing bracket is the base: a grouped base
  ["X Y_i", '"X Y"|sub("i")'],                        // a subscript in the same place stays set
  ["a + b ^ 2", '"a + b"|sup("2")'],
  ["x ^ 2", '"x"|sup("2")'],                          // the span's start
  ["x^{y ^ 2}", '"x"|sup("y"|sup("2"))'],             // a group's start
];
test("F3: the shapes the rule does not name stay set", () => {
  for (const [span, want] of STILL_SET) {
    const parts = NOTE.scriptParts(span);
    assert.ok(parts !== null, "scriptParts " + span);
    assert.equal(pp(parts), want, span);
    assert.equal(flatParts(parts), expectedFlatten(span), "C5 " + span);
  }
});

/* ---------------------------------------------------------------- fold 2 (reviewer round 2). Synthetic spans only. */
/* G1: the two F3 arms the round-2 mutants showed untested. A closing bracket, a space, then the base word; and more than one space between the words. */
for (const span of ["(a) b ^ 2", "f (x) y ^ 2"]) {
  test("G1 closing-bracket arm: refused " + JSON.stringify(span), () => {
    assert.equal(NOTE.scriptParts(span), null);
    assert.equal(ser(spanOf(span)), "code(" + JSON.stringify(span) + ")");
  });
}
for (const span of ["a  b ^ 2", "g   k ^ d"]) {
  test("G1 more than one space: refused " + JSON.stringify(span), () => {
    assert.equal(NOTE.scriptParts(span), null);
    assert.equal(ser(spanOf(span)), "code(" + JSON.stringify(span) + ")");
  });
}

/* G2: a combining mark directly after the opening { or ( of an operand group would attach to the wrong glyph (the F2a class, on the opening side). */
for (const span of ["a_{" + "́" + "e}", "x ^ (" + "́" + "b)"]) {
  test("G2 mark after an opening operand bracket: refused " + JSON.stringify(span), () => {
    assert.equal(NOTE.scriptParts(span), null);
    assert.equal(ser(spanOf(span)), "code(" + JSON.stringify(span) + ")");
  });
}

/* G3: a base that carries a subscript run is the base word of a following ^: in Lean the whole `k_1` is one identifier, so `g k_1 ^ d` means (g k_1)^d. */
for (const span of ["g k_1 ^ d", "g k_{ij}^d"]) {
  test("G3 subscripted base: refused " + JSON.stringify(span), () => {
    assert.equal(NOTE.scriptParts(span), null);
    assert.equal(ser(spanOf(span)), "code(" + JSON.stringify(span) + ")");
  });
}
test("G3: a subscripted base after an operator, or at the span's start, stays set", () => {
  for (const [span, want] of [["y = k_1 ^ d", '"y = k"|sub("1")|sup("d")'], ["k_1^d", '"k"|sub("1")|sup("d")']]) {
    const parts = NOTE.scriptParts(span);
    assert.ok(parts !== null, "scriptParts " + span);
    assert.equal(pp(parts), want, span);
    assert.equal(flatParts(parts), expectedFlatten(span), "C5 " + span);
  }
});

/* ---------------------------------------------------------------- fold 3 (reviewer round 3). Synthetic spans only.
   The operand-side juxtaposition set. In Lean a function application binds tighter than ^, so `a ^ b c` means a^(b c) and `a ^ b_c` has the one name
   b_c as its exponent; setting the operand over the first word alone would draw something else. Look-alikes that read as products cannot be told apart
   by syntax, so a spaced ^ with a word operand followed by spaces and a word or an opening bracket (arm a), or directly by a _ (arm b), is refused.
   Asserted at the GRAMMAR layer (scriptParts), never through renderNote: spanClass sends a synthetic letter_letter span (`a ^ b_c`, `x_i ^ 2 + y`) to
   the name-in-formula class and the code face before the grammar runs, so a renderNote assertion would pass for the wrong reason. */
const OPERAND_REFUSED = [
  "a ^ b c", "a ^ b (c)", "a ^ b [c]", "a ^ b  c",   // arm (a): spaces, then a word or an opening bracket
  "a ^ b_c",                                          // arm (b): directly a _
  "u ^ 2 v",                                          // a digit operand is a word
  "a ^ b c + d", "s = t ^ m q",                       // later operators, or an operator before the ^, do not save it
];
for (const span of OPERAND_REFUSED) {
  test("F4 operand-side juxtaposition: refused " + JSON.stringify(span), () => {
    assert.equal(NOTE.scriptParts(span), null, "scriptParts " + JSON.stringify(span));
  });
}
const OPERAND_SET = [
  ["a ^ b + c", '"a"|sup("b")|" + c"'],               // an operator after the operand
  ["(a ^ b) c", '"(a"|sup("b")|") c"'],               // a closing bracket after the operand
  ["a ^ b", '"a"|sup("b")'],                          // the span's end
  ["a ^ (b c) d", '"a"|sup("b c")|" d"'],             // a group operand is not a word operand
  ["a^{b c}", '"a"|sup("b c")'],
  ["w^k_3", '"w"|sup("k")|sub("3")'],                 // an unspaced ^: stacked indices stay set
  ["x_i ^ 2 + y", '"x"|sub("i")|sup("2")|" + y"'],
  ["[u ^ 3, v]", '"[u"|sup("3")|", v]"'],             // a comma after the operand is not covered
  ["h^n(k)", '"h"|sup("n")|"(k)"'],                   // U1: unspaced, directly an opening bracket
  ["(h^n q)^m", '"(h"|sup("n")|" q)"|sup("m")'],      // U2: unspaced, spaces, a word
];
test("F4 operand-side juxtaposition: the shapes the rule does not cover stay set, exact children", () => {
  for (const [span, want] of OPERAND_SET) {
    const parts = NOTE.scriptParts(span);
    assert.ok(parts !== null, "scriptParts " + JSON.stringify(span));
    assert.equal(pp(parts), want, span);
    assert.equal(flatParts(parts), expectedFlatten(span), "C5 " + span);
  }
});

/* ---------------------------------------------------------------- the superscript glyph after a ^ operand. Synthetic spans only.
   G4: a ^ whose operand (a group, a parenthesised group, a word, a symbol) is followed DIRECTLY by a superscript glyph is refused: `x ^ 10⁶` is
   x ^ (10 ^ 6) in Lean, and set it would read x^10 and then a raised 6. The glyph set is U+00B9, U+00B2, U+00B3, U+2070, U+2071, U+2074-U+207F.
   Not covered: modifier letters, a space before the glyph, a _ operand followed by a glyph. U+207F and U+2071 are letters (Lm), so a WORD operand
   absorbs them (`a ^ bⁿ`: the exponent is the word `bⁿ`) and the rule never sees a glyph after it. */
const SUP_REFUSED = ["x ^ 10⁶", "x^2⁻¹", "x^{a}²", "x ^ (a)⁺", "x^{a}ⁿ"];
test("G4 superscript glyph: a ^ operand directly followed by a superscript glyph is refused, drawn as code, as typed", () => {
  for (const span of SUP_REFUSED) {
    assert.equal(NOTE.scriptParts(span), null, "scriptParts " + JSON.stringify(span));
    assert.equal(ser(spanOf(span)), "code(" + JSON.stringify(span) + ")", JSON.stringify(span));
  }
});
const SUP_SET = [
  ["x ^ 10", '"x"|sup("10")'],
  ["w ^ c", '"w"|sup("c")'],
  ["x ^ 10 ⁶", '"x"|sup("10")|" ⁶"'],                          // a space before the glyph: not covered
  ["μ_j⁰", '"μ"|sub("j")|"⁰"'],                       // a _ operand: not covered
  ["x¹¹ ≤ m ^ 22", '"x¹¹ ≤ m"|sup("22")'],  // a glyph elsewhere, not after a ^ operand
  ["(A^⊥ / A)²", '"(A"|sup("⊥")|" / A)²"'],
  ["a ^ bⁿ", '"a"|sup("bⁿ")'],                                  // the word operand absorbs U+207F
];
test("G4 superscript glyph: the shapes the rule does not cover stay set, exact children", () => {
  for (const [span, want] of SUP_SET) {
    const parts = NOTE.scriptParts(span);
    assert.ok(parts !== null, "scriptParts " + JSON.stringify(span));
    assert.equal(pp(parts), want, JSON.stringify(span));
    assert.equal(flatParts(parts), expectedFlatten(span), "C5 " + JSON.stringify(span));
  }
});

/* ---------------------------------------------------------------- the population: every real span, from the committed class file, read only */
const SPANS = JSON.parse(readFileSync(path.join(HERE, "fixtures", "note-spans-classes.json"), "utf8")).spans;

/* The detector for the glyph rule, written here and independent of note.js: some ^, after optional spaces, has a bracket group, a word or one symbol
   directly followed by a superscript glyph. The glyphs are listed by code point. */
const GLYPHS = new Set([0xb9, 0xb2, 0xb3, 0x2070, 0x2071, ...Array.from({ length: 0x207f - 0x2074 + 1 }, (_, k) => 0x2074 + k)]);
const isGlyph = (ch) => ch !== undefined && GLYPHS.has(ch.codePointAt(0));
function glyphAfterOperand(span) {
  const cs = [...span], pair = { "(": ")", "[": "]", "{": "}" };
  for (let i = 0; i < cs.length; i++) {
    if (cs[i] !== "^") continue;
    let j = i + 1;
    while (cs[j] === " ") j++;
    let next = -1;
    if (pair[cs[j]]) {
      const stack = [];
      for (let k = j; k < cs.length && next < 0; k++) {
        if (pair[cs[k]]) stack.push(pair[cs[k]]);
        else if (")]}".includes(cs[k])) { if (stack.pop() !== cs[k]) break; if (stack.length === 0) next = k + 1; }
      }
    } else if (cs[j] !== undefined && /^[\p{L}\p{Nd}₀-₉′'’]$/u.test(cs[j])) {
      next = j;
      while (cs[next] !== undefined && /^[\p{L}\p{Nd}₀-₉′'’]$/u.test(cs[next])) next++;
    } else if (cs[j] !== undefined && "*×+-∨∞⊥".includes(cs[j])) next = j + 1;
    if (next >= 0 && isGlyph(cs[next])) return true;
  }
  return false;
}
test("G4 superscript glyph population: exactly 2 distinct real formula spans have a glyph after a ^ operand; each is refused and drawn as code", () => {
  const hits = new Set();
  for (const row of SPANS) if (row.class === "formula" && glyphAfterOperand(row.span)) hits.add(row.span);
  console.log("glyph-after-operand population: %d distinct formula spans", hits.size);
  assert.equal(hits.size, 2);
  for (const span of hits) {
    assert.equal(NOTE.scriptParts(span), null, "scriptParts " + JSON.stringify(span));
    assert.equal(ser(spanOf(span)), "code(" + JSON.stringify(span) + ")", JSON.stringify(span));
  }
});

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

test("F1 population: no real formula span that parses once the marks on its letters are removed is refused with them (computed, nothing copied)", () => {
  let checked = 0, withMarks = 0;
  const bad = [];
  for (const row of SPANS) {
    if (row.class !== "formula" || !/[\^_]/.test(row.span)) continue;
    const stripped = row.span.replace(/(\p{L})\p{M}+/gu, "$1");
    if (stripped !== row.span) withMarks++;
    if (NOTE.scriptParts(stripped) !== null) {
      checked++;
      if (NOTE.scriptParts(row.span) === null) bad.push(row.span.length);
    }
  }
  console.log("F1 population: %d formula spans with a script parse once stripped; %d of the script spans carry marks on a letter; %d refused with them", checked, withMarks, bad.length);
  assert.deepEqual(bad, []);
});

/* ---------------------------------------------------------------- fold 3b: the exponent-side check is linear, and decides exactly as the regex did.
   REFERENCE: note.js's own source with the juxtaposed-exponent guard put back to the fold 3 form, the regex applied to a slice and join of the rest of the
   span (the quadratic form). The new code and the reference are compared span by span on the decision (null or not) and the parts when set. */
const OLD_JUXTAPOSED = String.raw`/^[\p{L}\p{Nd}₀-₉′'’]+(?:_| +[\p{L}\p{Nd}₀-₉′'’(\[{])/u`;
async function loadReference() {
  const here = path.join(HERE, "..");
  let src = readFileSync(path.join(here, "note.js"), "utf8");
  const guard = /(?<=j > i \+ 1 && )(?:JUXTAPOSED\.test\(cs\.slice\(j, end\)\.join\(""\)\)|juxtaposed\(cs, j, end\))/g;
  assert.equal((src.match(guard) || []).length, 1, "the guard call appears once in note.js");
  src = src.replace(guard, "OLD_JUXTAPOSED.test(cs.slice(j, end).join(\"\"))");
  src = src.replace('from "./dom.js"', 'from "' + pathToFileURL(path.join(here, "dom.js")).href + '"');
  src += "\nconst OLD_JUXTAPOSED = " + OLD_JUXTAPOSED + ";\n";
  return import("data:text/javascript;base64," + Buffer.from(src).toString("base64"));
}

test("F5 performance: scriptParts on 20000 spaced powers, every one set, is linear (under 1500 ms)", () => {
  const span = Array.from({ length: 20000 }, () => "a ^ b").join(" + ");
  const t0 = performance.now();
  const parts = NOTE.scriptParts(span);
  const ms = performance.now() - t0;
  assert.ok(parts !== null, "20000 spaced powers are set");
  assert.ok(ms < 1500, "took " + ms.toFixed(0) + " ms");
});

function syntheticSpans() {
  const out = new Set();
  const bases = ["a", "x_i ", "s = t ", "(", "a b "];
  const hats = [" ^ ", "^", " ^", "^ ", "  ^  "];
  const operands = ["b", "bc", "2", "b′", "b’", "₂", "é"];
  const tails = ["", "_c", "_", " c", "  c", " 2", " ′", " (c)", " [c]", " {c}", " )", " ]", " +", " + c", " ^", " _c", " ", "  ", ")", "(c)",
    "́", "́ c", " ́", "b́ c", "_c d", " -", " ,", " é", " ₂", " =", ".", " .", "'", " 'c", " ( ", " (", ") c", "  ("];
  for (const b of bases) for (const h of hats) for (const o of operands) for (const t of tails) {
    for (const wrap of [(s) => s, (s) => "(" + s + ")", (s) => "{" + s + "}", (s) => s + " ^ d e", (s) => "m ^{" + s + "}", (s) => "k_" + "{" + s + "} z"]) out.add(wrap(b + "a" + h + o + t));
  }
  for (const s of ["a ^ b c", "a ^ b (c)", "a ^ b [c]", "a ^ b_c", "a ^ (b c) d", "a^{b c}", "a ^ b", "u ^ 2 v", "a ^ b  c", "w^k_3", "x ^ ", "x ^", "^ b", "a ^ b c ^ d e"]) out.add(s);
  return [...out];
}

test("F5 equivalence: the new check decides every span as the regex did (class fixture and a synthetic set), 0 differences", async () => {
  const REF = await loadReference();
  const spans = [...SPANS.map((r) => r.span), ...syntheticSpans()];
  let both = 0, refused = 0, setSpans = 0;
  const diff = [];
  for (const span of spans) {
    const a = NOTE.scriptParts(span), b = REF.scriptParts(span);
    if (JSON.stringify(a) !== JSON.stringify(b)) diff.push(span.length + ":" + JSON.stringify(span).slice(0, 40));
    if (/\^/.test(span)) { both++; if (a === null) refused++; else setSpans++; }
  }
  console.log("F5 equivalence: %d spans, %d with a ^; new code refuses %d, sets %d; %d differences", spans.length, both, refused, setSpans, diff.length);
  assert.deepEqual(diff, []);
  assert.ok(refused > 100 && setSpans > 100, "the synthetic set exercises both outcomes");
});
