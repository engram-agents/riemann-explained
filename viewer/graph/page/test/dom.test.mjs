import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { makeFakeDoc } from "./fakedoc.mjs";
import * as dom from "../dom.js";

const HOSTILE = [
  "<img src=x onerror=alert(1)>", "</script><script>alert(1)</script>", "javascript:alert(1)",
  '" onmouseover="x', "a b", "x".repeat(10000),
];

test("el: tag table is exactly the R1 list", () => {
  assert.deepEqual([...dom.TAGS].sort(), ["button", "code", "div", "h2", "li", "nav", "ol", "p", "span", "ul"]);
});

test("el: every allowed tag is created; every other tag THROWS", () => {
  const el = dom.makeEl(makeFakeDoc());
  for (const t of dom.TAGS) assert.equal(el(t).tagName, t.toUpperCase());
  for (const bad of ["svg", "path", "g", "script", "img", "a", "iframe", "style", "link", "input", "details", "article", "DIV", "div ", "", "constructor", "__proto__", "toString"])
    assert.throws(() => el(bad), /tag/i, "tag " + JSON.stringify(bad));
});

test("el: attribute allow-list; any other attribute THROWS", () => {
  const el = dom.makeEl(makeFakeDoc());
  const n = el("div", { class: "a-b c", "data-id": "step-1", role: "navigation", tabindex: "0", hidden: "", "aria-label": "x", "aria-expanded": "false" });
  assert.equal(n.attrs.class, "a-b c");
  assert.equal(n.attrs["data-id"], "step-1");
  assert.equal(el("button", { type: "button" }).attrs.type, "button");
  for (const bad of ["onclick", "onerror", "onmouseover", "style", "href", "src", "srcdoc", "id", "name", "target", "rel", "formaction", "xlink:href", "data-x", "aria-", "ARIA-label", "aria-label x", "constructor"])
    assert.throws(() => el("div", { [bad]: "x" }), /attribute/i, "attr " + bad);
  assert.throws(() => el("div", { type: "button" }), /attribute/i, "type only on button");
  assert.throws(() => el("button", { type: "submit" }), /type/i, "button type is only 'button'");
});

test("el: class tokens and data-id are validated before they land (R3)", () => {
  const el = dom.makeEl(makeFakeDoc());
  assert.throws(() => el("div", { class: '" onmouseover="x' }), /class/i);
  assert.throws(() => el("div", { class: "a<b" }), /class/i);
  assert.throws(() => el("div", { "data-id": "Bad Id" }), /id/i);
  assert.throws(() => el("div", { "data-id": '"><script>' }), /id/i);
  assert.throws(() => el("div", { "data-id": "-lead" }), /id/i);
  assert.equal(el("div", { "data-id": "a.b_c-d" }).attrs["data-id"], "a.b_c-d");
});

test("el: strings become TEXT nodes only; hostile strings add no element", () => {
  const doc = makeFakeDoc();
  const el = dom.makeEl(doc);
  for (const h of HOSTILE) {
    const before = doc.made.length;
    const n = el("span", {}, [h]);
    assert.equal(n.children.length, 1);
    assert.equal(n.children[0].nodeType, 3);
    assert.equal(n.children[0].textContent, h);
    assert.equal(doc.made.length, before + 1, "exactly the one element, nothing parsed out of the string");
  }
});

test("el: children must be strings, finite numbers or nodes; anything else THROWS", () => {
  const el = dom.makeEl(makeFakeDoc());
  const inner = el("span");
  assert.equal(el("div", {}, [inner, "t"]).children.length, 2);
  assert.equal(el("div", {}, [12]).children[0].textContent, "12");
  for (const bad of [NaN, Infinity, {}, null, undefined, () => 1, [], true])
    assert.throws(() => el("div", {}, [bad]), /child/i, String(bad));
});

test("ids: the R3 pattern", () => {
  for (const ok of ["a", "0", "a-b", "a.b", "a_b", "good-pair", "x1.2_3"]) assert.equal(dom.isId(ok), true, ok);
  for (const bad of ["", "-a", ".a", "_a", "A", "a b", "a/b", "a\n", "a ", "<img>", '"x', "javascript:alert(1)", 5, null, undefined, {}, "x".repeat(10000) + "!"])
    assert.equal(dom.isId(bad), false, String(bad).slice(0, 20));
  assert.throws(() => dom.assertId("../x"), /id/i);
  assert.equal(dom.assertId("ok-1"), "ok-1");
});

test("step file path is built only from a validated id (R4)", () => {
  assert.equal(dom.stepPath("good-pair"), "step/good-pair.json");
  for (const bad of ["../x", "a/b", "A", "", "x.json?y", "a\\b"]) assert.throws(() => dom.stepPath(bad), /id/i);
  assert.equal(dom.hashFor("good-pair"), "#good-pair");
  assert.throws(() => dom.hashFor("<x>"), /id/i);
});

test("the module source has no sink and no URL literal", () => {
  const src = readFileSync(new URL("../dom.js", import.meta.url), "utf8");
  for (const s of ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "DOMParser", "createElementNS", "eval(", "new Function", "http:", "https:"])
    assert.ok(!src.includes(s), "dom.js contains " + s);
});

/* ---- A6: a step title's backtick spans are typeset as code, by ONE helper. The definition of a span is the builder's
   (tools/notes_meta.py _BACKTICK_SPAN); backtick-titles.json holds the edge strings with the segments that regex itself finds. ---- */
const flat = (n) => (typeof n === "string" ? n : n.nodeType === 3 ? n.textContent : n.children.map(flat).join(""));   // a string child becomes one text node under el()
const render = (title) => { const doc = makeFakeDoc(); const kids = dom.titleChildren(title, dom.makeEl(doc)); return { doc, kids }; };
const BT = JSON.parse(readFileSync(new URL("./fixtures/backtick-titles.json", import.meta.url), "utf8"));

test("A6 agreement: titleSegments equals the segments the builder's own regex finds, for EVERY fixture title (edge strings and the real span titles)", () => {
  assert.ok(BT.cases.length >= 16, "the edge strings are there");
  for (const c of BT.cases) {
    assert.deepEqual(dom.titleSegments(c.title).map((x) => [x.kind, x.text]), c.segments, JSON.stringify(c.title));
    // and what is DRAWN: a plain string for text, a code element for a span, with the same characters
    const drawn = render(c.title).kids.map((k) => (typeof k === "string" ? ["text", k] : [k.tagName.toLowerCase() === "code" ? "code" : "other", flat(k)]));
    assert.deepEqual(drawn, c.segments, "drawn: " + JSON.stringify(c.title));
  }
  assert.ok(BT.cases.some((c) => c.title === "``" && c.segments.length === 1 && c.segments[0][0] === "text"), "an empty pair stays two literal backticks");
});

test("A6 T1: 'a `x` b' -> text 'a ', code 'x', text ' b'; no backtick shown", () => {
  const { kids } = render("a `x` b");
  assert.equal(kids.length, 3);
  assert.equal(kids[0], "a ");
  assert.equal(kids[1].tagName, "CODE");
  assert.equal(flat(kids[1]), "x");
  assert.equal(kids[2], " b");
  assert.ok(!kids.map(flat).join("").includes("`"));
});

test("A6 T2: the real title -> a code element with the text 'P* s P' (the asterisk stays literal)", () => {
  const { kids } = render("The second moments of the operators `P* s P`, and good forms");
  const code = kids.filter((k) => typeof k !== "string");
  assert.equal(code.length, 1);
  assert.equal(flat(code[0]), "P* s P");
  assert.equal(kids.map(flat).join(""), "The second moments of the operators P* s P, and good forms");
});

test("A6 T3: '`<b>&`' -> one code element whose text is '<b>&'; no <b> element exists", () => {
  const { doc, kids } = render("`<b>&`");
  assert.equal(kids.length, 1);
  assert.equal(flat(kids[0]), "<b>&");
  assert.deepEqual(doc.made.map((n) => n.tagName), ["CODE"]);
});

test("A6 T4/T5: an unpaired backtick and an empty pair are shown as written (the builder's rule)", () => {
  assert.equal(render("a `b").kids.map(flat).join(""), "a `b");
  assert.equal(render("a `b").doc.made.length, 0);
  assert.equal(render("``").kids.map(flat).join(""), "``");
  assert.equal(render("``").doc.made.length, 0);
});

test("A6 T6: a title with no backtick is one plain text node, exactly as before", () => {
  for (const t of ["Title of step goal-chain", "a <b> & c", "x".repeat(300)]) {
    const { doc, kids } = render(t);
    assert.equal(kids.length, 1);
    assert.equal(kids[0], t, "a plain string child, which el() turns into one text node");
    assert.equal(doc.made.length, 0);
  }
});

test("A6: the helper builds with el() only (text nodes and code elements, never markup)", () => {
  const src = readFileSync(new URL("../dom.js", import.meta.url), "utf8");
  const at = src.indexOf("export function titleSegments");
  assert.ok(at >= 0, "the helper exists");
  const body = src.slice(at);
  assert.ok(!/innerHTML|insertAdjacentHTML|outerHTML|DOMParser|createContextualFragment/.test(body));
});
