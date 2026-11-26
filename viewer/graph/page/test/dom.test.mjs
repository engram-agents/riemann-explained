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
  assert.deepEqual([...dom.TAGS].sort(), ["button", "div", "h2", "li", "nav", "ol", "p", "span", "ul"]);
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
