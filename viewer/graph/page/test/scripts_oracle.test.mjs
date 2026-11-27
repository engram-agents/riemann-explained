/* The ORACLE for the maths face's superscripts and subscripts: every real formula-class span that holds a ^ or a _ (454 distinct, read from
   fixtures/note-spans-scripts.json), against `scriptParts` of note.js. The expected structure of each span is written by an independent reference
   (fixtures/make_scripts_oracle.py), a span the grammar refuses is expected as null (left as typed). Short fragments of the repository's notes only,
   each once; nothing is copied from the notes at length. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import * as NOTE from "../note.js";

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");
const ORACLE = JSON.parse(readFileSync(path.join(FIX, "note-spans-scripts.json"), "utf8"));
const CLASSES = JSON.parse(readFileSync(path.join(FIX, "note-spans-classes.json"), "utf8"));

/* the page's parts -> the oracle's shape: a string, or [tag, [parts]]; adjacent strings merged */
function canon(parts) {
  if (parts === null) return null;
  const out = [];
  for (const p of parts) {
    if (typeof p === "string") {
      if (out.length && typeof out[out.length - 1] === "string") out[out.length - 1] += p;
      else out.push(p);
    } else out.push([p.tag, canon(p.children)]);
  }
  return out;
}

test("SO1 the oracle covers exactly the formula-class spans with a script of the classes fixture, each once", () => {
  const want = new Set(CLASSES.spans.filter((r) => r.class === "formula" && /[\^_]/.test(r.span)).map((r) => r.span));
  const have = ORACLE.spans.map((r) => r.span);
  assert.equal(new Set(have).size, have.length, "a span is listed twice");
  assert.deepEqual([...want].sort(), [...have].sort());
  assert.equal(ORACLE.distinct, have.length);
});

test("SO2 the counts the oracle states are the counts of its rows: 454 distinct, 371 set, 83 left", () => {
  const set = ORACLE.spans.filter((r) => r.expected !== null).length;
  assert.deepEqual([ORACLE.distinct, ORACLE.set, ORACLE.left], [454, 371, 83]);
  assert.deepEqual([set, ORACLE.spans.length - set], [ORACLE.set, ORACLE.left]);
  assert.ok(ORACLE.spans.every((r) => (r.expected === null) === (typeof r.reason === "string" && r.reason !== "")), "a left span names its reason, a set span has none");
});

test("SO3 scriptParts sets every span the oracle sets, exactly as the oracle's structure, and leaves every span the oracle leaves", () => {
  const bad = [];
  for (const r of ORACLE.spans) {
    const got = canon(NOTE.scriptParts(r.span));
    try {
      assert.deepEqual(got, r.expected);
    } catch {
      bad.push(`${JSON.stringify(r.span)}: page ${JSON.stringify(got)} oracle ${JSON.stringify(r.expected)}`);
    }
  }
  assert.deepEqual(bad.slice(0, 20), [], `${bad.length} of ${ORACLE.spans.length} spans differ`);
});

test("SO4 every span of the oracle is a span the maths face sets scripts on (formula class), so none is code by class", () => {
  for (const r of ORACLE.spans) assert.equal(NOTE.spanClass(r.span), "formula", r.span);
});

test("SO5 a set span keeps every character: the text of its structure, with the script characters and the dropped spaces and brackets removed, is the span's text", () => {
  const text = (parts) => parts.map((p) => (typeof p === "string" ? p : text(p[1]))).join("");
  for (const r of ORACLE.spans) {
    if (r.expected === null) continue;
    const stripped = [...r.span].filter((c) => c !== "^" && c !== "_" && c !== " " && c !== "{" && c !== "}" && c !== "(" && c !== ")").join("");
    const kept = [...text(r.expected)].filter((c) => c !== " " && c !== "(" && c !== ")").join("");
    assert.equal(kept, stripped, r.span);
  }
});
