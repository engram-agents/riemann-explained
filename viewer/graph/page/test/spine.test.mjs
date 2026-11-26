/* The Graph view's spine file (graph/spine.json, docs/tools.md "The spine"): validateSpine and spineRoots of page/spine.js.
   Written before the implementation. Every fixture is generated here with made-up text; no text of the proof's repository is
   copied into a test (Kepler's ruling of 2026-11-26). */
import test from "node:test";
import assert from "node:assert/strict";
import { DataError } from "../data.js";
import { validateSpine, spineRoots, SPINE_BASIS } from "../spine.js";

const clone = (o) => JSON.parse(JSON.stringify(o));
const COMMIT = "0123456789abcdef0123456789abcdef01234567";
const WORDS = "spine_lines_text";
const STRINGS = { key_lines_text: "made-up lines words", [WORDS]: "made-up spine lines words" };
/* The context the page holds when it loads the spine: the index's commit, the index's strings, and the index's own edge-basis words key. */
const CTX = { commit: COMMIT, strings: STRINGS, indexWords: "key_lines_text" };

/* A 9-node spine in the data's shape: n1 rests on n2 and n3, n2 on n4, n3 on n4 (so n1 -> n4 is a link but not in the reduction), and so on. */
function makeSpine() {
  const ids = ["a", "b", "c", "d", "e", "f", "g", "h", "i"].map((x) => "spine-made-up-" + x);
  const nodes = ids.map((id, i) => ({
    constants: ["New.Made.up" + i],
    content: "Made-up sentence number " + i + " of the fixture.",
    counts: { mentions: 1, no_doc: 0, other_constants: 0 },
    file: "lean-made-up-file-" + i,
    id,
    mentions: [{ constant: "New.Made.other" + i }],
    names: ["Made.up" + i],
    source: "grh/INDEX.md",
    theorem: "`Made.up" + i + "`",
  }));
  const L = (from, to, red) => ({ from: ids[from], in_reduction: red, to: ids[to] });
  const links = [L(0, 1, true), L(0, 2, true), L(1, 3, true), L(2, 3, true), L(0, 3, false), L(4, 3, true), L(5, 4, true), L(8, 7, true), L(8, 6, true), L(7, 6, true)];
  return { commit: COMMIT, edge_basis: { basis: SPINE_BASIS, words: WORDS }, format: 1, links, nodes };
}
const refuses = (raw, code, mention, ctx = CTX) => assert.throws(() => validateSpine(raw, ctx), (e) => {
  assert.ok(e instanceof DataError, "not a DataError: " + e);
  assert.equal(e.code, code, e.message);
  if (mention !== undefined) assert.ok(e.reason.includes(mention), "the reason " + JSON.stringify(e.reason) + " does not name " + mention);
  return true;
});
const mutate = (fn) => { const s = makeSpine(); fn(s); return s; };

test("S1 a spine in the data's shape validates; the record holds what the page reads and nothing else", () => {
  const r = validateSpine(makeSpine(), CTX);
  assert.equal(r.nodes.length, 9);
  assert.deepEqual(Object.keys(r.nodes[0]).sort(), ["content", "file", "id", "names", "theorem"]);
  assert.equal(r.nodes[0].content, "Made-up sentence number 0 of the fixture.");
  assert.equal(r.links.length, 10);
  assert.deepEqual(Object.keys(r.links[0]).sort(), ["from", "in_reduction", "to"]);
  assert.equal(r.words, WORDS);
});

test("S2 the record is a copy: changing the input afterwards changes nothing in it", () => {
  const s = makeSpine();
  const r = validateSpine(s, CTX);
  s.nodes[0].content = "changed";
  s.links[0].to = "x";
  assert.equal(r.nodes[0].content, "Made-up sentence number 0 of the fixture.");
  assert.notEqual(r.links[0].to, "x");
});

test("S3 the key sets are exact: a missing or an unknown key, at the top, in a node and in a link, is refused", () => {
  refuses(mutate((s) => { delete s.links; }), "missing-key", "links");
  refuses(mutate((s) => { s.extra = 1; }), "extra-key");
  refuses(mutate((s) => { delete s.nodes[3].theorem; }), "missing-key", "theorem");
  refuses(mutate((s) => { s.nodes[3].extra = 1; }), "extra-key");
  refuses(mutate((s) => { delete s.links[2].in_reduction; }), "missing-key", "in_reduction");
  refuses(mutate((s) => { s.links[2].weight = 1; }), "extra-key");
  refuses([], "bad-type");
  refuses(null, "bad-type");
});

test("S4 format is exactly 1 and the commit is the index's commit", () => {
  refuses(mutate((s) => { s.format = 2; }), "bad-format");
  refuses(mutate((s) => { s.format = "1"; }), "bad-format");
  refuses(mutate((s) => { s.commit = "f".repeat(40); }), "bad-commit");
  refuses(mutate((s) => { s.commit = 5; }), "bad-commit");
});

test("S5 a node id is a spine id of at most 64 characters, once; a file is a step id; the source is the index file", () => {
  refuses(mutate((s) => { s.nodes[0].id = "lean-not-a-spine-id"; }), "bad-spine-node", "id");
  refuses(mutate((s) => { s.nodes[0].id = "spine-" + "a".repeat(60); }), "bad-spine-node", "id");
  refuses(mutate((s) => { s.nodes[0].id = "spine-Upper"; }), "bad-spine-node", "id");
  refuses(mutate((s) => { s.nodes[1].id = s.nodes[0].id; }), "bad-spine-node", "repeats");
  refuses(mutate((s) => { s.nodes[0].file = "Not A Step"; }), "bad-spine-node", "file");
  refuses(mutate((s) => { s.nodes[0].source = "grh/OTHER.md"; }), "bad-spine-node", "source");
  refuses(mutate((s) => { s.nodes = []; }), "bad-spine-node", "empty");
});

test("S6 content and theorem are non-empty strings; names is a non-empty list of non-empty strings", () => {
  refuses(mutate((s) => { s.nodes[0].content = ""; }), "bad-spine-node", "content");
  refuses(mutate((s) => { s.nodes[0].content = 5; }), "bad-spine-node", "content");
  refuses(mutate((s) => { s.nodes[0].theorem = ""; }), "bad-spine-node", "theorem");
  refuses(mutate((s) => { s.nodes[0].names = []; }), "bad-spine-node", "names");
  refuses(mutate((s) => { s.nodes[0].names = ["ok", 3]; }), "bad-spine-node", "names");
  refuses(mutate((s) => { s.nodes[0].names = "Made.up0"; }), "bad-spine-node", "names");
});

test("S7 the keys the page does not draw are still of their shape: constants and mentions lists, counts an object", () => {
  refuses(mutate((s) => { s.nodes[0].constants = "x"; }), "bad-spine-node", "constants");
  refuses(mutate((s) => { s.nodes[0].mentions = {}; }), "bad-spine-node", "mentions");
  refuses(mutate((s) => { s.nodes[0].counts = []; }), "bad-spine-node", "counts");
});

test("S8 a link joins two different nodes of the file, once, and its flag is a boolean", () => {
  refuses(mutate((s) => { s.links[0].from = "spine-made-up-zz"; }), "bad-spine-link", "from");
  refuses(mutate((s) => { s.links[0].to = "spine-made-up-zz"; }), "bad-spine-link", "to");
  refuses(mutate((s) => { s.links[0].to = s.links[0].from; }), "bad-spine-link", "itself");
  refuses(mutate((s) => { s.links[1] = clone(s.links[0]); }), "bad-spine-link", "repeats");
  refuses(mutate((s) => { s.links[0].in_reduction = "yes"; }), "bad-spine-link", "in_reduction");
  refuses(mutate((s) => { s.links[0].in_reduction = 1; }), "bad-spine-link", "in_reduction");
});

test("S9 the links in the reduction have no cycle (the engine draws rows by depth); the others may form one with them", () => {
  refuses(mutate((s) => { s.links.push({ from: s.nodes[3].id, in_reduction: true, to: s.nodes[0].id }); }), "bad-spine-link", "cycle");
  /* a cycle through a link that is NOT in the reduction is not this page's concern: the builder refuses it as SKEL-SPINE-CYCLE */
  const ok = mutate((s) => { s.links.push({ from: s.nodes[3].id, in_reduction: false, to: s.nodes[0].id }); });
  assert.equal(validateSpine(ok, CTX).links.length, 11);
});

test("S10 edge_basis is exactly {basis, words}: the basis the page knows, a words key present in strings and not the index's own", () => {
  refuses(mutate((s) => { delete s.edge_basis; }), "missing-key", "edge_basis");
  refuses(mutate((s) => { s.edge_basis.basis = "something-else"; }), "bad-edge-basis", "basis");
  refuses(mutate((s) => { s.edge_basis.extra = 1; }), "bad-edge-basis");
  refuses(mutate((s) => { s.edge_basis.words = "no_such_key"; }), "bad-edge-basis", "words");
  refuses(mutate((s) => { s.edge_basis.words = ""; }), "bad-edge-basis", "words");
  refuses(mutate((s) => { s.edge_basis.words = "key_lines_text"; }), "bad-edge-basis", "index");
  refuses(makeSpine(), "bad-edge-basis", "strings", { ...CTX, strings: { key_lines_text: "x" } });
  refuses(mutate((s) => { s.edge_basis = "x"; }), "bad-edge-basis");
});

test("S11 hostile text is data, not code: content, theorem and names of any characters validate and are returned as the same strings", () => {
  const evil = ["<img src=x onerror=alert(1)>", "</script><script>alert(1)</script>", "javascript:alert(1)", '" onmouseover="x', "a\u0000b", "x".repeat(10000)];
  const s = makeSpine();
  evil.forEach((t, i) => { s.nodes[i].content = t; s.nodes[i].theorem = t; s.nodes[i].names = [t]; });
  const r = validateSpine(s, CTX);
  evil.forEach((t, i) => { assert.equal(r.nodes[i].content, t); assert.equal(r.nodes[i].theorem, t); assert.deepEqual(r.nodes[i].names, [t]); });
});

test("S12 spineRoots: one NodeSpec per node in the file's order, a leaf, its own path, links only from the reduction", () => {
  const roots = spineRoots(validateSpine(makeSpine(), CTX));
  assert.equal(roots.length, 9);
  roots.forEach((n, i) => {
    assert.equal(n.id, "spine-made-up-" + "abcdefghi"[i]);
    assert.equal(n.childCount, 0);
    assert.deepEqual(n.path, [n.id]);
    assert.equal(n.parentLinksTo, false);
    assert.deepEqual(Object.keys(n).sort(), ["childCount", "data", "id", "links", "parentLinksTo", "path"]);
  });
  const all = roots.flatMap((n) => n.links.map((l) => [n.id, l.to, l.toPath]));
  assert.equal(all.length, 9, "ten links in the file, nine in the reduction");
  for (const [, to, toPath] of all) assert.deepEqual(toPath, [to]);
  assert.deepEqual(roots[0].links.map((l) => l.to), ["spine-made-up-b", "spine-made-up-c"], "n0 rests on n1 and n2 in the reduction, not on n3");
  assert.deepEqual(roots[0].data, { content: "Made-up sentence number 0 of the fixture.", file: "lean-made-up-file-0", names: ["Made.up0"], theorem: "`Made.up0`" });
});

test("S12b the roots hold copies: changing a root's data or links changes nothing in the validated record", () => {
  const spine = validateSpine(makeSpine(), CTX);
  const roots = spineRoots(spine);
  roots[0].data.names.push("added");
  roots[0].links.pop();
  assert.deepEqual(spine.nodes[0].names, ["Made.up0"]);
  assert.equal(spine.links.length, 10);
  assert.equal(spineRoots(spine)[0].links.length, 2);
});

test("S13 every NodeSpec id and path and link target matches the engine's id pattern", () => {
  const ID = /^[a-z0-9][a-z0-9._-]*$/;
  for (const n of spineRoots(validateSpine(makeSpine(), CTX))) {
    assert.match(n.id, ID);
    for (const p of n.path) assert.match(p, ID);
    for (const l of n.links) { assert.match(l.to, ID); for (const p of l.toPath) assert.match(p, ID); }
  }
});
