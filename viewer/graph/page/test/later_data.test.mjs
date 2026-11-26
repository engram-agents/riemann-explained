/* The data side of the later-blocks line: the optional `later_blocks` of a note (the number of further module-doc blocks in the file) and the two
   optional strings keys note_more_one and note_more_many. Fixture: fixtures/later (a synthetic maths-face map plus the two keys; sk-file-1 has 1, sk-file-2 has 2,
   sk-file-3 has 0, sk-file-4 has a note and no `later_blocks`). */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { DataError, validateIndex, validateStep, OPTIONAL_STRINGS } from "../data.js";

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures", "later");
const idx = () => JSON.parse(readFileSync(path.join(FIX, "index.json"), "utf8"));
const step = (id) => JSON.parse(readFileSync(path.join(FIX, "step", id + ".json"), "utf8"));
const isErr = (code) => (e) => e instanceof DataError && e.code === code;
const withLater = (n) => { const s = step("sk-file-1"); s.note.later_blocks = n; return s; };
const KEYS = ["note_more_one", "note_more_many"];

test("L2 strings: note_more_one and note_more_many are in the page's ONE OPTIONAL_STRINGS set; the fixture map validates with both; each is optional alone; empty is `empty-string`; a non-string is refused", () => {
  for (const k of KEYS) assert.ok(OPTIONAL_STRINGS.includes(k), k);
  const v = validateIndex(idx());
  assert.equal(v.strings.note_more_one, "We count {n} more repository note in this file. This map does not show it.");
  assert.equal(v.strings.note_more_many, "We count {n} more repository notes in this file. This map does not show them.");
  for (const k of KEYS) {
    const a = idx(); delete a.strings[k]; validateIndex(a);
    const b = idx(); b.strings[k] = "";
    assert.throws(() => validateIndex(b), (e) => isErr("empty-string")(e) && e.message.includes(k), k);
    const c = idx(); c.strings[k] = 5;
    assert.throws(() => validateIndex(c), isErr("bad-type"), k + " not a string");
  }
});

test("L1 `later_blocks` is optional: a note without it validates and its step carries no later_blocks key; a present one is carried through unchanged", () => {
  const ctx = validateIndex(idx());
  const none = validateStep(step("sk-file-4"), ctx);
  assert.ok(!("later_blocks" in none.note), "absent stays absent");
  assert.deepEqual(Object.keys(none.note).sort(), ["commit", "source", "text"]);
  for (const [id, n] of [["sk-file-1", 1], ["sk-file-2", 2], ["sk-file-3", 0]]) {
    const v = validateStep(step(id), ctx);
    assert.equal(v.note.later_blocks, n, id);
    assert.equal(Object.keys(v.note).includes("later_blocks"), true, id);
  }
  assert.equal(validateStep(withLater(1000000), ctx).note.later_blocks, 1000000);
});

test("L1 `later_blocks` that is not an integer >= 0 (a float, a string, a boolean, null, a negative, an array, an object) is `bad-later-blocks` naming the step", () => {
  const ctx = validateIndex(idx());
  for (const [what, n] of [["a float", 1.5], ["a float that is small", 0.5], ["a string", "1"], ["an empty string", ""], ["true", true], ["false", false], ["null", null],
    ["-1", -1], ["a negative float", -0.5], ["an array", [1]], ["an object", { n: 1 }]]) {
    assert.throws(() => validateStep(withLater(n), ctx), (e) => isErr("bad-later-blocks")(e) && e.message.includes("sk-file-1"), what);
  }
});

test("L1 any OTHER unknown note key stays `bad-note`, with or without a valid later_blocks beside it", () => {
  const ctx = validateIndex(idx());
  for (const extra of [{ extra: "x" }, { later_block: 1 }, { laterBlocks: 1 }, { later_blocks: 1, extra: "x" }, { commit: "0123456789" }]) {
    const s = step("sk-file-1"); Object.assign(s.note, extra);
    assert.throws(() => validateStep(s, ctx), isErr("bad-note"), JSON.stringify(extra));
  }
});

test("L2 a note whose later_blocks > 0 on a map lacking either string key is `bad-note-strings` naming the step; later_blocks 0 or absent needs neither", () => {
  for (const drop of [["note_more_one"], ["note_more_many"], KEYS]) {
    const i = idx(); for (const k of drop) delete i.strings[k];
    const ctx = validateIndex(i);
    for (const n of [1, 2]) {
      assert.throws(() => validateStep(withLater(n), ctx), (e) => isErr("bad-note-strings")(e) && e.message.includes("sk-file-1"), drop.join("+") + " n=" + n);
    }
    // 0 and absent: no key needed; the step validates
    validateStep(withLater(0), ctx);
    validateStep(step("sk-file-4"), ctx);
    validateStep(step("sk-file-3"), ctx);
  }
  // a map with both keys takes any n
  const ctx = validateIndex(idx());
  validateStep(withLater(1), ctx); validateStep(withLater(7), ctx);
});

test("the live and the notes maps, which carry neither key, still validate and every note step there has no later_blocks", () => {
  for (const sub of ["notes", "typeset"]) {
    const i = JSON.parse(readFileSync(path.join(FIX, "..", sub, "index.json"), "utf8"));
    assert.ok(!KEYS.some((k) => k in i.strings), sub);
    const ctx = validateIndex(i);
    for (const id of ["sk-file-1", "sk-file-2"]) {
      const v = validateStep(JSON.parse(readFileSync(path.join(FIX, "..", sub, "step", id + ".json"), "utf8")), ctx);
      assert.ok(!("later_blocks" in v.note), sub + " " + id);
    }
  }
});
