// The card the page MAKES from the data when the markup has none for an id (the assembler writes an empty card block).
// Contract (M1): madeCard(title, elFn = el) -> a `div.card` holding one `h3.claim` whose children are titleChildren(title); built through el() only;
// no id attribute of any kind; nothing else in it. Test-only; synthetic titles only.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { makeFakeDoc } from "./fakedoc.mjs";
import { makeEl, titleChildren } from "../dom.js";
import * as app from "../app.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const tags = (doc) => doc.made.map((n) => n.tagName).sort();
const kids = (n) => n.children.map((c) => (c.nodeType === 3 ? { text: c.textContent } : { tag: c.tagName, kids: kids(c) }));

test("M1 app.js exports madeCard", () => {
  assert.equal(typeof app.madeCard, "function");
});

test("M1 the made card is div.card > h3.claim and nothing else; the title is one text node", () => {
  const doc = makeFakeDoc();
  const card = app.madeCard("A synthetic plain title", makeEl(doc));
  assert.equal(card.tagName, "DIV");
  assert.deepEqual(card.attrs, { class: "card" });
  assert.equal(card.children.length, 1);
  const h = card.children[0];
  assert.equal(h.tagName, "H3");
  assert.deepEqual(h.attrs, { class: "claim" });
  assert.deepEqual(kids(h), [{ text: "A synthetic plain title" }]);
  assert.deepEqual(tags(doc), ["DIV", "H3"], "no other element is made (no paragraph, no list)");
});

test("M1 the card carries no id of any kind (the page keys cards by its own Map, never by a DOM id)", () => {
  const doc = makeFakeDoc();
  const card = app.madeCard("synthetic-title-that-looks-like-an-id", makeEl(doc));
  for (const n of doc.made) for (const k of Object.keys(n.attrs)) assert.ok(k === "class", "attribute " + k + " on " + n.tagName);
  assert.equal(card.attrs.id, undefined);
  assert.equal(card.attrs["data-id"], undefined);
});

test("A6/M1 a backtick span in the title is a code element, no backtick character is shown", () => {
  const doc = makeFakeDoc();
  const card = app.madeCard("Use `P x P` here and `Q` there", makeEl(doc));
  const h = card.children[0];
  assert.deepEqual(kids(h), [{ text: "Use " }, { tag: "CODE", kids: [{ text: "P x P" }] }, { text: " here and " }, { tag: "CODE", kids: [{ text: "Q" }] }, { text: " there" }]);
  assert.deepEqual(tags(doc), ["CODE", "CODE", "DIV", "H3"]);
});

test("M1 a title that would be markup stays text, inside a span too", () => {
  for (const title of ["<img src=x onerror=1>", "`<img src=x onerror=1>`", "</h3><script>alert(1)</script>", "&amp; <b>x</b>"]) {
    const doc = makeFakeDoc();
    const card = app.madeCard(title, makeEl(doc));
    const t = tags(doc);
    assert.ok(t.every((x) => ["DIV", "H3", "CODE"].includes(x)), title + " made " + t);
    const flat = [];
    (function walk(n) { for (const c of n.children) { if (c.nodeType === 3) flat.push(c.textContent); else walk(c); } })(card);
    assert.equal(flat.join(""), title.replace(/^`(.*)`$/, "$1"), title);
  }
});

test("M1 the claim's children are exactly titleChildren(title) for every title of the backtick agreement fixture", () => {
  const cases = JSON.parse(readFileSync(path.join(HERE, "fixtures", "backtick-titles.json"), "utf8")).cases;
  assert.ok(cases.length > 5);
  for (const c of cases) {
    const doc = makeFakeDoc();
    const card = app.madeCard(c.title, makeEl(doc));
    const want = titleChildren(c.title, makeEl(makeFakeDoc()));
    assert.deepEqual(kids(card.children[0]), want.map((w) => (typeof w === "string" ? { text: w } : { tag: w.tagName, kids: kids(w) })), c.title);
  }
});

test("M1 with no element creator given, madeCard uses the page's el() (the document's own)", () => {
  const saved = globalThis.document;
  globalThis.document = makeFakeDoc();
  try {
    const card = app.madeCard("A synthetic title");
    assert.equal(card.tagName, "DIV");
    assert.equal(card.children[0].tagName, "H3");
  } finally {
    if (saved === undefined) delete globalThis.document; else globalThis.document = saved;
  }
});

test("M1 madeCard is built through el() only: its source names no createElement, innerHTML, insertAdjacentHTML, setAttribute or textContent", () => {
  const src = readFileSync(path.join(HERE, "..", "app.js"), "utf8");
  const i = src.indexOf("export function madeCard");
  assert.ok(i >= 0, "madeCard is declared as an export");
  const body = src.slice(i, src.indexOf("\n}\n", i));
  for (const bad of ["createElement", "innerHTML", "insertAdjacentHTML", "setAttribute", "textContent", "outerHTML", "DOMParser"]) assert.ok(!body.includes(bad), bad);
  assert.ok(body.includes("titleChildren"), "the title goes through titleChildren");
});
