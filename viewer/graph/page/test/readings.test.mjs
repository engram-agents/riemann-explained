/* Our reading notes (data contract sections 28 and 28b), the data half: R1 every refusal of D1 to D4 by code, with each cap at the limit and one over;
   R2 the strings set, conditional on the index's `readings`, both ways, and the byline placeholder pin. Written before the implementation.
   The fixtures (fixtures/readings) are synthetic; the cases below edit copies of them in memory. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createData, DataError, validateIndex, validateStep } from "../data.js";

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");
const read = (dir, ...p) => JSON.parse(readFileSync(path.join(FIX, dir, ...p), "utf8"));
const rIndex = () => read("readings", "index.json");
const rStep = (id) => read("readings", "step", id + ".json");
const clone = (o) => JSON.parse(JSON.stringify(o));
const refuses = (fn, code, mention) => assert.throws(fn, (e) => {
  assert.ok(e instanceof DataError, "not a DataError: " + e);
  assert.equal(e.code, code, "the code: " + e.message);
  if (mention !== undefined) assert.ok(e.reason.includes(mention), "the reason " + JSON.stringify(e.reason) + " does not name " + mention);
  return true;
});
const ctxOf = (edit) => { const i = rIndex(); if (edit) edit(i); return validateIndex(i); };
/* a step of the fixture, edited, validated against the fixture's own index */
const stepWith = (id, edit, ctx = ctxOf()) => { const s = rStep(id); edit(s); return validateStep(s, ctx); };
const STRING_KEYS = ["readings_heading", "readings_about", "readings_byline", "key_readings_heading"];

function dirFetch(dir, over = {}) {
  return async (url) => {
    if (Object.prototype.hasOwnProperty.call(over, url)) return { ok: true, status: 200, json: async () => clone(over[url]) };
    const p = path.join(dir, url);
    if (!existsSync(p)) return { ok: false, status: 404, json: async () => { throw new SyntaxError("no body"); } };
    const text = readFileSync(p, "utf8");
    return { ok: true, status: 200, json: async () => JSON.parse(text) };
  };
}

/* ------------------------------------------------------------------------------------------------ the fixtures are the shape the contract says */

test("R1 control: the synthetic fixture validates, the record carries the rows and each step carries its readings unchanged", () => {
  const raw = rIndex();
  const ctx = validateIndex(raw);
  assert.deepEqual(ctx.readings, raw.readings);
  assert.equal(ctx.readings.length, 5);
  assert.deepEqual(ctx.readings.map((r) => r.id), ["a-first", "b-second", "c-third", "d-hostile", "e-single"]);
  for (const sid of ["sk-file-1", "sk-file-2", "sk-file-4"]) {
    const v = validateStep(rStep(sid), ctx);
    assert.deepEqual(v.readings, rStep(sid).readings, sid);
  }
  assert.equal(Object.prototype.hasOwnProperty.call(validateStep(rStep("sk-file-3"), ctx), "readings"), false, "a step with none has no key");
  assert.equal(validateStep(rStep("sk-file-4"), ctx).readings[0].about.length, 2, "`about` is carried");
});

test("R8 the live map: no `readings` key in the record, nothing else changes", () => {
  const live = read("real", "index.json");
  assert.equal(Object.prototype.hasOwnProperty.call(validateIndex(live), "readings"), false);
  const sk = read("skeleton", "index.json");
  assert.equal(Object.prototype.hasOwnProperty.call(validateIndex(sk), "readings"), false);
});

/* ------------------------------------------------------------------------------------------------ R1 / D1: index `readings` */

test("R1 D1: a list that is not a non-empty list is bad-readings (empty, object, string, null)", () => {
  for (const v of [[], {}, "x", null, 3]) refuses(() => ctxOf((i) => { i.readings = v; }), "bad-readings");
});

test("R1 D1: a row is exactly {id, title, step}: a missing key, an extra key, a non-object", () => {
  for (const k of ["id", "title", "step"]) refuses(() => ctxOf((i) => { delete i.readings[0][k]; }), "bad-readings");
  refuses(() => ctxOf((i) => { i.readings[0].text = "x"; }), "bad-readings");
  refuses(() => ctxOf((i) => { i.readings[0] = "a-first"; }), "bad-readings");
  refuses(() => ctxOf((i) => { i.readings[0] = null; }), "bad-readings");
});

test("R1 D1: an id is [a-z0-9-]{1,64}: 64 characters pass, 65, '', capitals, a space, a dot, an underscore, a non-string do not; a leading hyphen is refused (the id is the element's data-id, and dom.js's data-id takes only ids that start with a-z or 0-9)", () => {
  const first = (id) => (i) => { i.readings[0].id = id; i.readings.sort((a, b) => (a.id < b.id ? -1 : a.id > b.id ? 1 : 0)); };
  const ok = (id) => { const c = ctxOf(first(id)); assert.ok(c.readings.some((r) => r.id === id)); };
  ok("a".repeat(64));
  ok("0");
  ok("a-");
  ok("0-9");
  for (const bad of ["a".repeat(65), "", "A", "a b", "a.b", "a_b", "é", 5, null, "-lead", "-", "--"]) refuses(() => ctxOf((i) => { i.readings[0].id = bad; }), "bad-readings");
});

test("R1 D1: a repeated id is bad-readings; rows out of plain string order of id are bad-readings", () => {
  refuses(() => ctxOf((i) => { i.readings[1].id = "a-first"; }), "bad-readings");
  refuses(() => ctxOf((i) => { i.readings.reverse(); }), "bad-readings");
  refuses(() => ctxOf((i) => { [i.readings[0], i.readings[1]] = [i.readings[1], i.readings[0]]; }), "bad-readings");
  /* plain string order: a digit (0x30) sorts before a letter, and 'a-' (0x2d after 'a') before 'aa' and 'a0' */
  const c = ctxOf((i) => { i.readings[0].id = "0y"; i.readings[1].id = "a-z"; i.readings[2].id = "a0"; i.readings[3].id = "aa"; });
  assert.deepEqual(c.readings.slice(0, 4).map((r) => r.id), ["0y", "a-z", "a0", "aa"]);
  refuses(() => ctxOf((i) => { i.readings[0].id = "aa"; i.readings[1].id = "a-z"; }), "bad-readings");
});

test("R1 D1: a title is a non-empty string with no backtick (the cap has its own case)", () => {
  const title = (t) => (i) => { i.readings[0].title = t; };
  assert.equal(ctxOf(title(" ")).readings[0].title, " ");
  for (const bad of ["", "a`b", "`", 5, null]) refuses(() => ctxOf(title(bad)), "bad-readings");
});

test("R1 the title cap is 200 characters, in an index row and in a step's reading: 200 pass (also as astral characters), 201 is bad-readings", () => {
  const rowTitle = (t) => (i) => { i.readings[0].title = t; };
  for (const ok of ["x".repeat(200), "\u00e9".repeat(200), "\ud83d\ude00".repeat(200)]) assert.equal(ctxOf(rowTitle(ok)).readings[0].title, ok);
  for (const bad of ["x".repeat(201), "\ud83d\ude00".repeat(201)]) refuses(() => ctxOf(rowTitle(bad)), "bad-readings");
  const both = (t) => stepWith("sk-file-1", (s) => { s.readings[0].title = t; }, ctxOf((i) => { i.readings.find((r) => r.id === "a-first").title = t; }));
  for (const ok of ["x".repeat(200), "\ud83d\ude00".repeat(200)]) assert.equal(both(ok).readings[0].title, ok);
  for (const bad of ["x".repeat(201), "\ud83d\ude00".repeat(201)]) {
    refuses(() => stepWith("sk-file-1", (s) => { s.readings[0].title = bad; }), "bad-readings");
  }
});

test("R1 D1: `step` is a step id that is a FILE: a bad id, a non-string and a part (a top step) are bad-readings", () => {
  for (const bad of ["Bad Id", "", 5, null, "../x"]) refuses(() => ctxOf((i) => { i.readings[0].step = bad; }), "bad-readings");
  refuses(() => ctxOf((i) => { i.readings[0].step = "sk-part"; }), "bad-readings", "sk-part");
  refuses(() => ctxOf((i) => { i.readings[0].step = "sk-part-2"; }), "bad-readings");
});

test("R1 D1 at load: a row naming a group is refused when that group's step loads (the index alone cannot tell a group from a file)", () => {
  const ctx = ctxOf((i) => { i.readings[0].step = "sk-group-a"; });
  refuses(() => validateStep(rStep("sk-group-a"), ctx), "bad-readings", "sk-group-a");
});

/* ------------------------------------------------------------------------------------------------ R1 / D3: a step's `readings` */

const setR = (k, v) => (s) => { s.readings[0][k] = v; };

test("R1 D3: a step's readings is a non-empty list, in plain string order of id; a repeated id is refused", () => {
  for (const v of [[], {}, "x", null, 3]) refuses(() => stepWith("sk-file-1", (s) => { s.readings = v; }), "bad-readings");
  refuses(() => stepWith("sk-file-1", (s) => { s.readings.reverse(); }), "bad-readings");
  refuses(() => stepWith("sk-file-1", (s) => { s.readings[1] = clone(s.readings[0]); }), "bad-readings");
});

test("R1 D3: a reading has EXACTLY {id, title, text, by, second_read_by, date} plus an optional `about`: any missing key, any extra key", () => {
  for (const k of ["id", "title", "text", "by", "second_read_by", "date"]) refuses(() => stepWith("sk-file-1", (s) => { delete s.readings[0][k]; }), "bad-readings", k);
  refuses(() => stepWith("sk-file-1", (s) => { s.readings[0].extra = "x"; }), "bad-readings");
  refuses(() => stepWith("sk-file-1", (s) => { s.readings[0].source_commit = "x"; }), "bad-readings");
  refuses(() => stepWith("sk-file-1", (s) => { s.readings[0] = "a-first"; }), "bad-readings");
  assert.equal(stepWith("sk-file-4", () => {}).readings[0].about.length, 2, "the optional seventh key is accepted");
});

test("R1 D3: id and title follow D1 (65-character id, capitals, backtick, empty, non-string)", () => {
  /* the id and title edited together with the index so that only D3's own rule can refuse */
  const both = (id, title) => {
    const ctx = ctxOf((i) => { i.readings[0].id = id; i.readings[0].title = title; i.readings.sort((a, b) => (a.id < b.id ? -1 : 1)); });
    return stepWith("sk-file-1", (s) => { s.readings[0].id = id; s.readings[0].title = title; s.readings.sort((a, b) => (a.id < b.id ? -1 : 1)); }, ctx);
  };
  assert.equal(both("a".repeat(64), "A title").readings.length, 3);
  refuses(() => stepWith("sk-file-1", setR("id", "a".repeat(65))), "bad-readings");
  refuses(() => stepWith("sk-file-1", setR("id", "A")), "bad-readings");
  refuses(() => stepWith("sk-file-1", setR("title", "a`b")), "bad-readings");
  refuses(() => stepWith("sk-file-1", setR("title", "")), "bad-readings");
  refuses(() => stepWith("sk-file-1", setR("title", 5)), "bad-readings");
});

test("R1 D3: text is a non-empty string of at most 20000 UTF-8 BYTES: 20000 pass (ASCII, 2-byte, 4-byte), 20001, 20002 as 2-byte characters, empty, a non-string do not; whitespace-only passes", () => {
  const ok = (t) => assert.equal(stepWith("sk-file-1", setR("text", t)).readings[0].text, t);
  ok("x".repeat(20000));
  ok("é".repeat(10000));
  ok("😀".repeat(5000));
  ok("   \n\t ");
  ok(" ");
  for (const bad of ["x".repeat(20001), "é".repeat(10001), "😀".repeat(5001), "", 5, null, ["x"]]) refuses(() => stepWith("sk-file-1", setR("text", bad)), "bad-readings");
});

test("R1 D3: by and second_read_by are non-empty, at most 100 characters each: 100 pass, 101, empty, non-string do not", () => {
  for (const k of ["by", "second_read_by"]) {
    const other = k === "by" ? "second_read_by" : "by";
    assert.equal(stepWith("sk-file-1", setR(k, "n".repeat(100))).readings[0][k].length, 100);
    assert.equal(stepWith("sk-file-1", setR(k, "😀".repeat(100))).readings[0][k].length, 200, "100 astral characters are 100 characters");
    for (const bad of ["n".repeat(101), "😀".repeat(101), "", 5, null]) refuses(() => stepWith("sk-file-1", setR(k, bad)), "bad-readings", undefined);
    assert.notEqual(rStep("sk-file-1").readings[0][other], "n".repeat(100));
  }
});

test("R1 D3: by equal to second_read_by is bad-readings; different by case or a trailing space is not equal", () => {
  refuses(() => stepWith("sk-file-1", (s) => { s.readings[0].second_read_by = s.readings[0].by; }), "bad-readings");
  assert.ok(stepWith("sk-file-1", (s) => { s.readings[0].second_read_by = s.readings[0].by.toUpperCase(); }));
  assert.ok(stepWith("sk-file-1", (s) => { s.readings[0].second_read_by = s.readings[0].by + " "; }));
});

test("R1 D3: date is exactly YYYY-MM-DD and a real calendar date: 2026-02-30, 2026-02-29, 2026-13-01, 2026-00-10, 2026-04-31, 0000-01-01, short forms, other separators, trailing newline are refused; leap days pass", () => {
  for (const ok of ["2026-02-28", "2024-02-29", "2000-02-29", "2026-12-31", "0001-01-01", "9999-12-31"]) assert.equal(stepWith("sk-file-1", setR("date", ok)).readings[0].date, ok);
  for (const bad of ["2026-02-30", "2026-02-29", "1900-02-29", "2026-13-01", "2026-00-10", "2026-04-31", "2026-01-00", "0000-01-01", "2026-2-3", "2026/02/03", "20260203",
    "2026-02-03\n", " 2026-02-03", "2026-02-03T00:00:00Z", "", 20260203, null]) refuses(() => stepWith("sk-file-1", setR("date", bad)), "bad-readings");
});

test("R1 D3: about, when present, is a non-empty list of non-empty strings of at most 200 characters; it is validated and carried", () => {
  const ok = (a) => assert.deepEqual(stepWith("sk-file-1", setR("about", a)).readings[0].about, a);
  ok(["N"]);
  ok(["n".repeat(200)]);
  for (const bad of [[], "N", {}, null, [""], [5], ["n".repeat(201)], ["fine", ""], ["fine", null]]) refuses(() => stepWith("sk-file-1", setR("about", bad)), "bad-readings");
});

test("R1 D3: a part or a group step carrying `readings` is bad-readings", () => {
  for (const sid of ["sk-part", "sk-group-a"]) {
    refuses(() => stepWith(sid, (s) => { s.readings = clone(rStep("sk-file-1").readings); }), "bad-readings");
  }
});

/* ------------------------------------------------------------------------------------------------ R1 / D4: consistency at step load */

test("R1 D4: a reading with no row in the index list is readings-mismatch naming the id", () => {
  const ctx = ctxOf((i) => { i.readings = i.readings.filter((r) => r.id !== "b-second"); });
  refuses(() => validateStep(rStep("sk-file-1"), ctx), "readings-mismatch", "b-second");
});

test("R1 D4: a row whose title differs is readings-mismatch naming the id", () => {
  const ctx = ctxOf((i) => { i.readings.find((r) => r.id === "a-first").title = "Another title"; });
  refuses(() => validateStep(rStep("sk-file-1"), ctx), "readings-mismatch", "a-first");
});

test("R1 D4: a row whose `step` is another step is readings-mismatch naming the id", () => {
  const ctx = ctxOf((i) => { i.readings.find((r) => r.id === "c-third").step = "sk-file-5"; });
  refuses(() => validateStep(rStep("sk-file-1"), ctx), "readings-mismatch", "c-third");
});

test("R1 D4: a step carrying readings while the index has none is readings-mismatch", () => {
  const raw = rIndex();
  delete raw.readings;
  for (const k of STRING_KEYS) delete raw.strings[k];
  const ctx = validateIndex(raw);
  refuses(() => validateStep(rStep("sk-file-1"), ctx), "readings-mismatch");
});

test("R1 D4: the check is made on a load through createData, and a good step still loads", async () => {
  const dir = path.join(FIX, "readings");
  const bad = rStep("sk-file-1");
  bad.readings[0].title = "A different title";
  const data = createData(dirFetch(dir, { "step/sk-file-1.json": bad }));
  await assert.rejects(() => data.loadStep("sk-file-1"), (e) => e instanceof DataError && e.code === "readings-mismatch" && e.reason.includes("a-first"));
  const good = createData(dirFetch(dir));
  const v = await good.loadStep("sk-file-1");
  assert.equal(v.readings.length, 3);
});

/* ------------------------------------------------------------------------------------------------ R2 the strings, conditional on `readings` */

test("R2 present `readings`: each of the four strings is REQUIRED (absent: missing-string naming it; \"\": empty-string naming it)", () => {
  for (const k of STRING_KEYS) {
    refuses(() => ctxOf((i) => { delete i.strings[k]; }), "missing-string", k);
    refuses(() => ctxOf((i) => { i.strings[k] = ""; }), "empty-string", k);
  }
});

test("R2 absent `readings`: none of the four is read, so a present one is extra-string naming it; with none present the index validates", () => {
  const base = () => { const i = rIndex(); delete i.readings; for (const k of STRING_KEYS) delete i.strings[k]; return i; };
  assert.ok(validateIndex(base()), "no readings, no strings: valid");
  for (const k of STRING_KEYS) {
    const i = base();
    i.strings[k] = k === "readings_byline" ? "{by} {second_read_by} {date}" : "a word";
    refuses(() => validateIndex(i), "extra-string", k);
  }
});

test("R2 readings_front is a shell key, never an index string: present with or without `readings` it is extra-string", () => {
  const withR = rIndex();
  withR.strings.readings_front = "a word";
  refuses(() => validateIndex(withR), "extra-string", "readings_front");
  const without = read("skeleton", "index.json");
  without.strings.readings_front = "a word";
  refuses(() => validateIndex(without), "extra-string", "readings_front");
});

test("R2 byline pin: the placeholders are EXACTLY {by}, {second_read_by}, {date}; they are the field names of a reading", () => {
  const byline = rIndex().strings.readings_byline;
  const found = [...byline.matchAll(/\{([^{}]*)\}/g)].map((m) => m[1]);
  assert.deepEqual([...found].sort(), ["by", "date", "second_read_by"]);
  const reading = rStep("sk-file-1").readings[0];
  for (const name of found) assert.ok(Object.prototype.hasOwnProperty.call(reading, name), name + " is a field of a reading");
  assert.ok(ctxOf((i) => { i.strings.readings_byline = "{date} {by} {second_read_by}"; }), "any order");
  assert.ok(ctxOf((i) => { i.strings.readings_byline = "{by} and {second_read_by} on {date} ({date})"; }), "a repeated one is still the same set");
});

test("R2 byline pin: a missing, an unknown or a misspelled placeholder is bad-readings-strings", () => {
  for (const bad of [
    "{by} {second_read_by}",                                    // no {date}
    "{second_read_by} {date}",                                  // no {by}
    "{by} {date}",                                              // no {second_read_by}
    "no placeholder at all",
    "{by} {second_read_by} {date} {source}",                    // an unknown one
    "{by} {second_read_by} {date} {}",                          // an empty one
    "{by} {second_read_by} {Date}",                             // a capital
    "{by} {second_read_by} {dat}",                              // a prefix
    "{by} {second_read_by} {date} {commit}",
  ]) refuses(() => ctxOf((i) => { i.strings.readings_byline = bad; }), "bad-readings-strings");
});
