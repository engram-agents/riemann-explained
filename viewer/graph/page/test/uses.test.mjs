/* The file neighbourhood's data (graph/uses.json, format 3): validateUses of page/uses.js. Every fixture is generated here with made-up text; no text of the
   proof's repository is copied into a test (Kepler's ruling of 2026-11-26). */
import test from "node:test";
import assert from "node:assert/strict";
import { DataError } from "../data.js";
import { validateUses } from "../uses.js";

const clone = (o) => JSON.parse(JSON.stringify(o));
const COMMIT = "0123456789abcdef0123456789abcdef01234567";
/* A map of six steps: one part, two groups, three files. f1 uses f2 (same group, 3 names) and f3 (across groups, 1 name); f2 uses f3 (across, 2 names). */
const CTX = { commit: COMMIT, steps: 6, top: ["made-part"], kinds: ["part", "group", "file"] };
function makeUses() {
  const T = (kind, path, title) => ({ kind, path, title });
  return {
    commit: COMMIT, format: 3,
    imports: { "made-file-1": ["made-file-2"], "made-file-2": [], "made-file-3": [] },
    lib_index_rows: [{ file: "Made/Lib.lean", source: "made/INDEX.md", text: "Made row" }],
    titles: {
      "made-part": T("part", [], "Made part"),
      "made-group-a": T("group", ["made-part"], "Made group a"),
      "made-group-b": T("group", ["made-part"], "Made group b"),
      "made-file-1": T("file", ["made-part", "made-group-a"], "Made file one"),
      "made-file-2": T("file", ["made-part", "made-group-a"], "Made file two"),
      "made-file-3": T("file", ["made-part", "made-group-b"], "Made file three"),
    },
    uses: {
      "made-file-1": [{ id: "made-file-2", names: 3, same_group: true }, { id: "made-file-3", names: 1, same_group: false }],
      "made-file-2": [{ id: "made-file-3", names: 2, same_group: false }],
      "made-file-3": [],
    },
    used_by: {
      "made-file-1": [],
      "made-file-2": [{ id: "made-file-1", names: 3, same_group: true }],
      "made-file-3": [{ id: "made-file-1", names: 1, same_group: false }, { id: "made-file-2", names: 2, same_group: false }],
    },
  };
}
const refuses = (raw, code, mention, ctx = CTX) => assert.throws(() => validateUses(raw, ctx), (e) => {
  assert.ok(e instanceof DataError, "not a DataError: " + e);
  assert.equal(e.code, code, e.message);
  if (mention !== undefined) assert.ok(e.reason.includes(mention), "the reason " + JSON.stringify(e.reason) + " does not name " + mention);
  return true;
});
const mutate = (fn) => { const u = makeUses(); fn(u); return u; };

test("U1 a file in the data's shape validates; the record holds the titles, the files and both sides", () => {
  const r = validateUses(makeUses(), CTX);
  assert.deepEqual(r.files.sort(), ["made-file-1", "made-file-2", "made-file-3"]);
  assert.equal(r.titles.size, 6);
  assert.deepEqual(r.titles.get("made-file-1"), { kind: "file", path: ["made-part", "made-group-a"], title: "Made file one" });
  assert.deepEqual(r.uses.get("made-file-1"), [{ id: "made-file-2", names: 3, same_group: true }, { id: "made-file-3", names: 1, same_group: false }]);
  assert.equal(r.usedBy.get("made-file-3").length, 2);
});

test("U2 the record is a copy: changing the input afterwards changes nothing in it", () => {
  const u = makeUses();
  const r = validateUses(u, CTX);
  u.titles["made-file-1"].title = "changed";
  u.uses["made-file-1"][0].names = 99;
  assert.equal(r.titles.get("made-file-1").title, "Made file one");
  assert.equal(r.uses.get("made-file-1")[0].names, 3);
});

test("U3 the key set is exactly the seven keys: a missing one and an extra one are named", () => {
  for (const k of ["commit", "format", "imports", "lib_index_rows", "titles", "used_by", "uses"]) refuses(mutate((u) => { delete u[k]; }), "missing-key", k);
  refuses(mutate((u) => { u.extra = 1; }), "extra-key");
  refuses([], "bad-type");
});

test("U4 the format is 3 and the commit is the index's", () => {
  refuses(mutate((u) => { u.format = 2; }), "bad-format");
  refuses(mutate((u) => { u.format = "3"; }), "bad-format");
  refuses(mutate((u) => { u.commit = "f".repeat(40); }), "bad-commit");
  refuses(mutate((u) => { u.commit = ""; }), "bad-commit");
});

test("U5 titles: as many steps as the index says, the top steps among them, each row {kind, path, title} with a listed kind, existing ancestors and a title", () => {
  refuses(mutate((u) => { delete u.titles["made-file-3"]; }), "bad-titles", "5 steps");
  refuses(mutate((u) => { u.titles["made-other"] = u.titles["made-file-3"]; delete u.titles["made-file-3"]; delete u.used_by["made-file-3"]; }), "bad-uses", "titles lacks");   // the titles keys still count 6: the file is the one refused
  refuses(mutate((u) => { u.titles["made-file-1"].kind = "bogus"; }), "bad-titles", "kind");
  refuses(mutate((u) => { u.titles["made-file-1"].path = ["nowhere"]; }), "bad-titles", "path");
  refuses(mutate((u) => { u.titles["made-file-1"].path = ["made-file-1"]; }), "bad-titles", "path");
  refuses(mutate((u) => { u.titles["made-file-1"].title = ""; }), "bad-titles", "title");
  refuses(mutate((u) => { u.titles["made-file-1"].title = 5; }), "bad-titles", "title");
  refuses(mutate((u) => { u.titles["made-file-1"].extra = 1; }), "extra-key");
  refuses(mutate((u) => { delete u.titles["made-file-1"].path; }), "missing-key");
  refuses(mutate((u) => { u.titles = []; }), "bad-titles");
  refuses(makeUses(), "bad-titles", "top step", { ...CTX, top: ["made-nothing"] });
});

test("U6 uses and used_by have exactly the files as keys, each a file of titles that is no ancestor of a step", () => {
  refuses(mutate((u) => { delete u.used_by["made-file-1"]; }), "bad-uses", "used_by");
  refuses(mutate((u) => { u.uses["made-group-a"] = []; }), "bad-uses", "ancestor");
  refuses(mutate((u) => { u.uses["made-ghost"] = []; }), "bad-uses", "titles lacks");
  refuses(mutate((u) => { u.uses = []; }), "bad-uses");
});

test("U7 a row is {id, names, same_group}: a file other than the owner, a positive whole number, a boolean; rows sorted by id, once each", () => {
  const bad = (fn, mention) => refuses(mutate(fn), "bad-uses", mention);
  bad((u) => { u.uses["made-file-1"][0].names = 0; }, "names");
  bad((u) => { u.uses["made-file-1"][0].names = 1.5; }, "names");
  bad((u) => { u.uses["made-file-1"][0].names = "3"; }, "names");
  bad((u) => { u.uses["made-file-1"][0].same_group = 1; }, "same_group");
  bad((u) => { u.uses["made-file-1"][0].id = "made-file-1"; }, "itself");
  bad((u) => { u.uses["made-file-1"][0].id = "made-group-a"; }, "file the map does not have");
  bad((u) => { u.uses["made-file-1"].reverse(); }, "sorted");
  bad((u) => { u.uses["made-file-1"][1].id = "made-file-2"; }, "sorted");
  bad((u) => { u.uses["made-file-1"] = {}; }, "not a list");
  refuses(mutate((u) => { u.uses["made-file-1"][0].extra = 1; }), "extra-key");
});

test("U8 used_by is the EXACT inverse of uses: a different weight, a different same_group, a missing pair and an extra pair each refuse, naming the pair", () => {
  refuses(mutate((u) => { u.used_by["made-file-2"][0].names = 4; }), "uses-inverse-mismatch", "made-file-1");
  refuses(mutate((u) => { u.used_by["made-file-2"][0].same_group = false; }), "uses-inverse-mismatch", "made-file-2");
  refuses(mutate((u) => { u.used_by["made-file-3"].pop(); }), "uses-inverse-mismatch", "made-file-3");
  refuses(mutate((u) => { u.used_by["made-file-1"].push({ id: "made-file-3", names: 1, same_group: false }); u.used_by["made-file-1"].sort((a, b) => (a.id < b.id ? -1 : 1)); }), "uses-inverse-mismatch");
  /* the first differing pair is the one named: uses is walked in file order, then used_by for a pair uses lacks */
  const u = mutate((x) => { x.used_by["made-file-2"][0].names = 4; x.used_by["made-file-3"][1].names = 9; });
  refuses(u, "uses-inverse-mismatch", "made-file-1\" -> \"made-file-2");
});

test("U9 imports and lib_index_rows are checked for shape only", () => {
  refuses(mutate((u) => { delete u.imports["made-file-2"]; }), "bad-uses", "imports");
  refuses(mutate((u) => { u.imports["made-file-1"] = ["made-nothing"]; }), "bad-uses", "imports");
  refuses(mutate((u) => { u.imports["made-file-1"] = "made-file-2"; }), "bad-uses", "imports");
  refuses(mutate((u) => { u.lib_index_rows = {}; }), "bad-uses", "lib_index_rows");
  refuses(mutate((u) => { u.lib_index_rows[0].text = 5; }), "bad-uses", "lib_index_rows");
  refuses(mutate((u) => { delete u.lib_index_rows[0].source; }), "missing-key");
  validateUses(mutate((u) => { u.lib_index_rows = []; u.imports["made-file-1"] = []; }), CTX);   // empty is fine
});

test("U10 handed no validated index context it is a TypeError, not a quiet pass", () => {
  assert.throws(() => validateUses(makeUses(), {}), TypeError);
  assert.throws(() => validateUses(makeUses(), { ...CTX, kinds: undefined }), TypeError);
  assert.throws(() => validateUses(makeUses(), undefined), TypeError);
});

test("U11 hostile text stays a value: a title with markup validates and is returned as the string it is", () => {
  const hostile = "<img src=x onerror=alert(1)> and `<b>code</b>`";
  const r = validateUses(mutate((u) => { u.titles["made-file-1"].title = hostile; }), CTX);
  assert.equal(r.titles.get("made-file-1").title, hostile);
});

test("U12 a key that is an Object.prototype name is no reach: __proto__ as a file id is refused, not looked up", () => {
  const u = JSON.parse(JSON.stringify(makeUses()).replace(/made-file-3/g, "__proto__"));
  assert.throws(() => validateUses(u, CTX), DataError);
});
