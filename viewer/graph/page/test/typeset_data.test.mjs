/* The data side of the maths-face step: the four optional strings keys (note_label_typeset, note_typeset_line, note_exact_button,
   note_render_button) and the reserved `review` field of a note. Fixture: fixtures/typeset (the notes map plus the four keys; sk-file-3 carries
   the real LineCoordinates note with review {"state": "converter"}). */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { DataError, validateIndex, validateStep, OPTIONAL_STRINGS } from "../data.js";

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures", "typeset");
const idx = () => JSON.parse(readFileSync(path.join(FIX, "index.json"), "utf8"));
const step = (id) => JSON.parse(readFileSync(path.join(FIX, "step", id + ".json"), "utf8"));
const isErr = (code) => (e) => e instanceof DataError && e.code === code;
const NEW = ["note_label_typeset", "note_typeset_line", "note_exact_button", "note_render_button"];

test("T5 strings: the four maths-face keys are optional (in the one OPTIONAL set), accepted present and absent, each alone; empty is `empty-string`; a non-string is refused", () => {
  for (const k of NEW) assert.ok(OPTIONAL_STRINGS.includes(k), k);
  const full = validateIndex(idx());
  assert.equal(full.strings.note_label, "The file's opening note, from the repository, unchanged");
  assert.equal(full.strings.note_label_typeset, "The file's opening note, from the repository");
  assert.equal(full.strings.note_typeset_line, "Formulas are set in maths type by us from the repository's text, so some signs (such as ^ for a power) look different. Tap Show the exact text to see it as written.");
  assert.equal(full.strings.note_exact_button, "Show the exact text");
  assert.ok(full.strings.note_render_button.length > 0);
  for (const k of NEW) {
    const absent = idx(); delete absent.strings[k]; validateIndex(absent);
    const empty = idx(); empty.strings[k] = "";
    assert.throws(() => validateIndex(empty), (e) => isErr("empty-string")(e) && e.message.includes(k), k + " empty");
    const num = idx(); num.strings[k] = 5;
    assert.throws(() => validateIndex(num), isErr("bad-type"), k + " not a string");
  }
  const none = idx(); for (const k of NEW) delete none.strings[k]; validateIndex(none);
  for (const extra of ["note_label_typeset2", "note_typeset", "note_exact", "note_render", "note_checked_line"]) {
    const i = idx(); i.strings[extra] = "x";
    assert.throws(() => validateIndex(i), isErr("extra-string"), extra);
  }
});

test("L2 a note may carry `review` {state: converter} (exact key set): accepted, carried as {state}, and a note without it is accepted as before", () => {
  const ctx = validateIndex(idx());
  const withIt = validateStep(step("sk-file-3"), ctx);
  assert.deepEqual(withIt.note.review, { state: "converter" });
  assert.deepEqual(Object.keys(withIt.note).sort(), ["commit", "review", "source", "text"]);
  const plain = validateStep(step("sk-file-1"), ctx);
  assert.ok(!("review" in plain.note), "no review in, none out");
  assert.deepEqual(Object.keys(plain.note).sort(), ["commit", "source", "text"]);
  // the same on a map without the four strings: review is the note's own field, not a strings matter
  const bare = idx(); for (const k of NEW) delete bare.strings[k];
  assert.deepEqual(validateStep(step("sk-file-3"), validateIndex(bare)).note.review, { state: "converter" });
});

test("L3 any other review is DataError `bad-review` naming the step: another state, an extra key, a missing state, a non-object, a later field name", () => {
  const ctx = validateIndex(idx());
  const withReview = (r) => { const s = step("sk-file-3"); s.note.review = r; return s; };
  const bad = (what, r) => assert.throws(() => validateStep(withReview(r), ctx), (e) => isErr("bad-review")(e) && e.message.includes("sk-file-3"), what);
  bad("confirmed", { state: "confirmed" });
  bad("unchecked", { state: "unchecked" });
  bad("an extra key", { state: "converter", extra: 1 });
  bad("converter_version is not accepted yet", { state: "converter", converter_version: "1" });
  bad("converter_version alone", { converter_version: "1" });
  bad("no state", {});
  bad("a state that is not a string", { state: 5 });
  bad("a state in other case", { state: "Converter" });
  bad("null", null);
  bad("a string", "converter");
  bad("an array", [{ state: "converter" }]);
  // the note's own shape is still checked first, and an unknown key beside text and source is still `bad-note`
  const extra = step("sk-file-3"); extra.note.extra = "x";
  assert.throws(() => validateStep(extra, ctx), isErr("bad-note"));
  // a note without review stays valid
  validateStep(step("sk-file-1"), ctx);
});
