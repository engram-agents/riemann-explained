import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createData, DataError, validateIndex, validateStep, requiredStrings, FIXED_STRINGS, KIND_CLASS, STATE_CLASS, PROOF_CLASS, isTransportCode, SHEET_PROOF_CLASS } from "../data.js";

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");

/* A fetch-like over a fixture directory. Counts calls. A missing file answers 404; a file that is not JSON
   makes .json() reject, exactly as a real Response does. */
function dirFetch(dir, overrides = {}) {
  const calls = [];
  const f = async (url) => {
    calls.push(url);
    if (url in overrides) return overrides[url];
    const p = path.join(dir, url);
    if (!existsSync(p)) return { ok: false, status: 404, json: async () => { throw new SyntaxError("no body"); } };
    const text = readFileSync(p, "utf8");
    return { ok: true, status: 200, json: async () => JSON.parse(text) };
  };
  f.calls = calls;
  return f;
}
const real = () => dirFetch(path.join(FIX, "real"));
const refusalDir = (n) => dirFetch(path.join(FIX, "refusals", n));

async function loadEverything(fetchLike) {
  const d = createData(fetchLike);
  await d.loadIndex();
  const roots = await d.loadRoots();
  const kids = await d.loadChildren(roots[0].id);
  return { d, roots, kids };
}

test("real-shaped build: index, roots and every step load; counts are 2 + 5 + 7", async () => {
  const d = createData(real());
  const idx = await d.loadIndex();
  assert.deepEqual(idx.top, ["goal-chain", "inputs", "bounds"]);
  assert.equal(idx.steps, 23);
  assert.equal(idx.maxChildren, 40);
  const roots = await d.loadRoots();
  assert.equal(roots.length, 3);
  let topLinks = roots.reduce((n, r) => n + r.links.length, 0);
  let stepLinks = 0, parentStems = 0, nodes = roots.length, deepest = 0, widest = roots.length;
  const stack = [...roots];
  while (stack.length) {
    const n = stack.pop();
    deepest = Math.max(deepest, n.path.length);
    if (n.childCount === 0) continue;
    const kids = await d.loadChildren(n.id);
    assert.equal(kids.length, n.childCount);
    widest = Math.max(widest, kids.length);
    nodes += kids.length;
    for (const k of kids) { stepLinks += k.links.length; parentStems += k.parentLinksTo ? 1 : 0; stack.push(k); }
  }
  assert.equal(topLinks, 2, "links among the top steps (index.json rests_on)");
  assert.equal(stepLinks, 5, "links among a step's children (step files rests_on)");
  assert.equal(parentStems, 7, "parent_rests_on true");
  assert.equal(nodes, 23);
  assert.equal(deepest, 5, "engine path of the deepest step has 5 elements");
  assert.equal(widest, 6);
});

test("PATH RULE: engine path = contract path + [id]; toPath = to_path + [to] (depth-5 step and a top step)", async () => {
  const d = createData(real());
  await d.loadIndex();
  const roots = await d.loadRoots();
  const top = roots.find((r) => r.id === "goal-chain");
  assert.deepEqual(top.path, ["goal-chain"], "a top step's path is [id]");
  assert.deepEqual(top.links, [{ to: "inputs", toPath: ["inputs"] }], "a top link's toPath is [to]");
  assert.equal(top.parentLinksTo, false);
  // walk down to the depth-5 step
  const a1 = (await d.loadChildren("goal-chain")).find((k) => k.id === "a1");
  const a1a = (await d.loadChildren("a1")).find((k) => k.id === "a1-a");
  const a1a1 = (await d.loadChildren("a1-a")).find((k) => k.id === "a1-a-1");
  const x = (await d.loadChildren("a1-a-1"))[0];
  assert.equal(x.id, "a1-a-1-x");
  assert.deepEqual(x.path, ["goal-chain", "a1", "a1-a", "a1-a-1", "a1-a-1-x"]);
  assert.deepEqual(a1.path, ["goal-chain", "a1"]);
  assert.equal(a1.parentLinksTo, true);
  // a sibling link inside a1's children: a1-b rests on a1-a
  const kids = await d.loadChildren("a1");
  const b = kids.find((k) => k.id === "a1-b");
  assert.deepEqual(b.links, [{ to: "a1-a", toPath: ["goal-chain", "a1", "a1-a"] }]);
  assert.deepEqual(kids.find((k) => k.id === "a1-a").links, []);
  assert.equal(a1a.childCount, 2);
  assert.equal(a1a1.childCount, 1);
});

test("NodeSpec carries only engine vocabulary plus data {title, kind, state, role?}", async () => {
  const d = createData(real());
  await d.loadIndex();
  const roots = await d.loadRoots();
  const r = roots[0];
  assert.deepEqual(Object.keys(r).sort(), ["childCount", "data", "id", "links", "parentLinksTo", "path"]);
  assert.equal(r.data.title, "Title of step goal-chain");
  assert.ok(["theorem", "def", "structure"].includes(r.data.kind));
  assert.ok(["read", "census", "none"].includes(r.data.state));
  assert.equal(r.data.role, "Theorem");
});

test("ROLE is optional: a role-less step has NO role key in data, and is not a refusal", async () => {
  const d = createData(real());
  await d.loadIndex();
  await d.loadRoots();
  const kids = await d.loadChildren("goal-chain");
  const topg = kids.find((k) => k.id === "topg");
  assert.ok(topg, "fixture step topg exists");
  assert.equal("role" in topg.data, false);
  assert.equal(JSON.stringify(topg.data).includes("undefined"), false);
  assert.equal(kids.find((k) => k.id === "a1").data.role, "Theorem");
  const meta = d.meta("topg");
  assert.equal(meta.title, "Title of step topg");
  assert.equal("role" in meta, false);
  await d.loadChildren("bounds");
  assert.equal("role" in d.meta("linkn"), false);
});

test("meta(id) gives titles for the breadcrumb of every step seen, and nothing for a step not seen", async () => {
  const d = createData(real());
  await d.loadIndex();
  await d.loadRoots();
  await d.loadChildren("goal-chain");
  assert.equal(d.meta("a1").title, "Title of step a1");
  assert.deepEqual(d.meta("a1").path, ["goal-chain"], "meta keeps the contract's ancestors-only path");
  assert.equal(d.meta("a1-a"), undefined);
  assert.equal(d.meta("../x"), undefined);
});

test("loadStep: a hostile id is refused BEFORE any fetch; a missing file is a named refusal", async () => {
  const f = real();
  const d = createData(f);
  await d.loadIndex();
  const before = f.calls.length;
  for (const bad of ["../index", "a/b", "A", "", "<img src=x onerror=alert(1)>", "javascript:alert(1)", "x.json?y=1", 'a" onmouseover="x', "a b"])
    await assert.rejects(d.loadStep(bad), (e) => e instanceof DataError && e.code === "bad-id", JSON.stringify(bad));
  assert.equal(f.calls.length, before, "no fetch for a bad id");
  await assert.rejects(d.loadStep("no-such-step"), (e) => e instanceof DataError && e.code === "http-404");
  assert.ok(f.calls.includes("step/no-such-step.json"), "the address is step/ + id + .json, relative");
  for (const c of f.calls) assert.match(c, /^(index\.json|step\/[a-z0-9][a-z0-9._-]*\.json)$/);
});

test("a step file whose id is not the id asked for is refused", async () => {
  const f = dirFetch(path.join(FIX, "real"), {});
  const d = createData(async (u) => (u === "step/a1.json" ? f("step/a2.json") : f(u)));
  await d.loadIndex();
  await assert.rejects(d.loadStep("a1"), (e) => e instanceof DataError && e.code === "id-mismatch");
});

/* One fixture per refusal: the dir, the code it must be refused with, and what to call to reach it. */
const REFUSALS = [
  ["bad-id", "bad-id"], ["bad-id-in-top", "bad-id"], ["unknown-kind", "unknown-kind"], ["unknown-state", "unknown-state"],
  ["child-count-mismatch", "child-count"], ["path-invalid-id", "bad-path"], ["non-json", "not-json"], ["non-json-index", "not-json"],
  ["missing-string", "missing-string"], ["empty-strings", "missing-string"], ["bad-format", "bad-format"],
  ["link-not-sibling", "bad-link"], ["commit-mismatch", "commit-mismatch"], ["symbols-lacks-kind", "unknown-kind"],
  ["unrenderable-kind", "unknown-kind"], ["empty-role", "bad-role"], ["role-not-string", "bad-role"], ["empty-title", "bad-title"],
  ["extra-key", "extra-key"],
  // contract section 8
  ["unrenderable-proof", "unknown-proof"], ["bad-proof-value", "unknown-proof"], ["missing-proof", "missing-key"],
  ["missing-words-string", "missing-string"], ["extra-string", "extra-string"], ["extra-string-proofs-heading", "extra-string"],
  ["order-not-array", "bad-order"], ["order-unknown-name", "bad-order"], ["order-kinds-empty", "bad-order"], ["order-repeats", "bad-order"], ["class-not-string", "bad-type"], ["words-not-string", "bad-type"],
  ["symbols-old-shape", "missing-key"], ["missing-parts-failed-notice", "missing-string"],
];

test("refusal fixtures: the list covers every fixture directory", () => {
  const dirs = readdirSync(path.join(FIX, "refusals")).sort();
  assert.deepEqual(REFUSALS.map((r) => r[0]).sort(), dirs);
});

for (const [name, code] of REFUSALS) {
  test("refusal: " + name + " -> " + code + " (named reason, never partial data)", async () => {
    let got;
    await assert.rejects(
      async () => { got = await loadEverything(refusalDir(name)); },
      (e) => e instanceof DataError && e.code === code && typeof e.message === "string" && e.message.length > 0,
    );
    assert.equal(got, undefined, "nothing partial comes back");
  });
}

test("one bad step file among the roots rejects the whole root load", async () => {
  const f = dirFetch(path.join(FIX, "real"), {
    "step/inputs.json": { ok: true, status: 200, json: async () => { throw new SyntaxError("x"); } },
  });
  const d = createData(f);
  await d.loadIndex();
  await assert.rejects(d.loadRoots(), (e) => e instanceof DataError && e.code === "not-json");
});

test("validateIndex / validateStep are pure and exported; requiredStrings is generated from the closed lists", async () => {
  const idx = JSON.parse(readFileSync(path.join(FIX, "real", "index.json"), "utf8"));
  const v = validateIndex(idx);
  assert.deepEqual(v.symbols.order.kinds, ["theorem", "def", "structure"]);
  assert.deepEqual(v.symbols.order.states, ["read", "census", "none"]);
  const req = requiredStrings(v.symbols);
  assert.deepEqual(FIXED_STRINGS, ["parts_n", "part_one", "open_parts", "close_parts", "claim_more", "claim_less", "crumb_label", "link_refused",
    "parts_failed_notice", "key_kinds_heading", "key_states_heading"], "the fixed runtime list (no proofs heading: the key has no proofs section)");
  for (const k of ["sheet_statement_read", "sheet_statement_census", "sheet_statement_not_read", "sheet_proof_read", "sheet_proof_not_read",
    "sheet_proof_none", "key_kind_theorem", "key_kind_def", "key_kind_structure"]) assert.ok(req.includes(k), k);
  assert.equal(req.length, 20, "11 fixed + one `words` key per row (3 kinds, 3 states, 3 proofs)");
  assert.deepEqual([...req].sort(), Object.keys(idx.strings).sort(), "strings is EXACTLY the required set");
  for (const k of req) assert.equal(typeof idx.strings[k], "string", k);
  // a runtime key missing -> refusal naming it
  for (const k of req) {
    const bad = JSON.parse(JSON.stringify(idx));
    delete bad.strings[k];
    assert.throws(() => validateIndex(bad), (e) => e.code === "missing-string" && e.message.includes(k), k);
  }
  const step = JSON.parse(readFileSync(path.join(FIX, "real", "step", "a1.json"), "utf8"));
  assert.equal(validateStep(step, v).id, "a1");
});

test("field-by-field: each contract field's wrong type is refused (generated from the real index and a real step)", () => {
  const idx = JSON.parse(readFileSync(path.join(FIX, "real", "index.json"), "utf8"));
  const v = validateIndex(idx);
  /* wrong TYPES only, chosen by the original's type, so a value that is also valid for the field is never tried */
  const wrongFor = (orig) => {
    if (typeof orig === "string") return [null, 5, [], {}, true];
    if (typeof orig === "number") return ["x", null, [], {}, true, -1, 1.5];
    if (typeof orig === "boolean") return ["x", null, 5, [], {}];
    if (Array.isArray(orig)) return ["x", null, 5, {}, true];
    return ["x", null, 5, [], true];
  };
  for (const key of Object.keys(idx)) {
    for (const w of wrongFor(idx[key])) {
      const bad = { ...idx, [key]: w };
      assert.throws(() => validateIndex(bad), DataError, "index." + key + " = " + JSON.stringify(w));
    }
    const missing = { ...idx }; delete missing[key];
    assert.throws(() => validateIndex(missing), DataError, "index." + key + " missing");
  }
  const step = JSON.parse(readFileSync(path.join(FIX, "real", "step", "a1.json"), "utf8"));
  for (const key of Object.keys(step)) {
    for (const w of wrongFor(step[key])) {
      assert.throws(() => validateStep({ ...step, [key]: w }, v), DataError, "step." + key + " = " + JSON.stringify(w));
    }
    const missing = { ...step }; delete missing[key];
    assert.throws(() => validateStep(missing, v), DataError, "step." + key + " missing");
  }
  for (const key of Object.keys(step.children[0])) {
    for (const w of wrongFor(step.children[0][key])) {
      const bad = JSON.parse(JSON.stringify(step));
      bad.children[0][key] = w;
      assert.throws(() => validateStep(bad, v), DataError, "child." + key + " = " + JSON.stringify(w));
    }
    if (key !== "role") {
      const bad = JSON.parse(JSON.stringify(step));
      delete bad.children[0][key];
      assert.throws(() => validateStep(bad, v), DataError, "child." + key + " missing");
    }
  }
  // hostile strings in titles are DATA, valid, and come back byte for byte
  for (const h of ["<img src=x onerror=alert(1)>", "</script><script>alert(1)</script>", "javascript:alert(1)", '" onmouseover="x', "a b", "x".repeat(10000)]) {
    const ok = JSON.parse(JSON.stringify(step));
    ok.children[0].title = h;
    assert.equal(validateStep(ok, v).children[0].title, h);
  }
});

test("the module source has no sink, no URL literal, no reader-facing sentence literal", () => {
  const src = readFileSync(new URL("../data.js", import.meta.url), "utf8");
  for (const s of ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "DOMParser", "createElementNS", "eval(", "new Function", "http:", "https:", "import("])
    assert.ok(!src.includes(s), "data.js contains " + s);
});

test("INDEX LINKS: the contract gives top steps the empty path, so an index rests_on entry with a non-empty from_path or to_path is refused", () => {
  const idx = JSON.parse(readFileSync(path.join(FIX, "real", "index.json"), "utf8"));
  validateIndex(idx);                                            // the real one (empty paths) is accepted
  for (const field of ["from_path", "to_path"]) {
    for (const value of [["goal-chain"], ["x"], ["goal-chain", "a1"]]) {
      const bad = JSON.parse(JSON.stringify(idx));
      bad.rests_on[0][field] = value;
      assert.throws(() => validateIndex(bad), (e) => e instanceof DataError && e.code === "bad-link", field + " = " + JSON.stringify(value));
    }
  }
});


/* ------------------------------------------------------------------------------------------ contract section 8 */

const realIndex = () => JSON.parse(readFileSync(path.join(FIX, "real", "index.json"), "utf8"));
const clone = (o) => JSON.parse(JSON.stringify(o));

test("SECTION 8 symbols: the exact shape is accepted, with order, words by table, and the page's own class tables", () => {
  const v = validateIndex(realIndex());
  assert.deepEqual(v.symbols.order.kinds, ["theorem", "def", "structure"]);
  assert.deepEqual(v.symbols.order.proofs, ["read", "not_read", "none"]);
  assert.deepEqual(v.symbols.order.states, ["read", "census", "none"]);
  assert.deepEqual(v.symbols.words.proofs, { read: "sheet_proof_read", not_read: "sheet_proof_not_read", none: "sheet_proof_none" });
  assert.deepEqual(v.symbols.words.states, { read: "sheet_statement_read", census: "sheet_statement_census", none: "sheet_statement_not_read" });
  assert.deepEqual(Object.keys(PROOF_CLASS), ["read", "not_read", "none"]);
  assert.deepEqual(Object.keys(KIND_CLASS), ["theorem", "def", "structure"]);
  assert.deepEqual(Object.keys(STATE_CLASS), ["read", "census", "none"]);
});

test("SECTION 8 order: a permutation is accepted and changes the order; a repeat, a stranger and a non-list are refused", () => {
  const idx = realIndex();
  const ok = clone(idx);
  ok.symbols.order.kinds = ["structure", "theorem", "def"];
  ok.symbols.order.proofs = ["none", "read", "not_read"];
  const v = validateIndex(ok);
  assert.deepEqual(v.symbols.order.kinds, ["structure", "theorem", "def"]);
  assert.deepEqual(v.symbols.order.proofs, ["none", "read", "not_read"]);
  for (const t of ["kinds", "proofs", "states"]) {
    const names = idx.symbols.order[t];
    for (const bad of [[...names, names[0]], [names[0], names[0], ...names.slice(2)], [...names.slice(0, -1), "stranger"], "x", null, {}, 7]) {
      const b = clone(idx);
      b.symbols.order[t] = bad;
      assert.throws(() => validateIndex(b), (e) => e instanceof DataError && e.code === "bad-order", t + " " + JSON.stringify(bad));
    }
  }
});

/* P3: an order list is a SUBSET of its table's names, in the order given. */
test("P3 order is a subset: any subset in the order given is accepted; kinds may not be empty, states and proofs may", () => {
  const idx = realIndex();
  for (const [t, list] of [["kinds", ["structure"]], ["kinds", ["structure", "theorem"]], ["states", []], ["states", ["none"]], ["proofs", []], ["proofs", ["none", "read"]]]) {
    const b = clone(idx);
    b.symbols.order[t] = list;
    const v = validateIndex(b);
    assert.deepEqual(v.symbols.order[t], list, t + " " + JSON.stringify(list));
    assert.equal(v.symbols.names[t].length, 3, "the table's names are untouched by the order");
  }
  const b = clone(idx);
  b.symbols.order.kinds = [];
  assert.throws(() => validateIndex(b), (e) => e instanceof DataError && e.code === "bad-order" && /kinds/.test(e.message));
});

test("P3 the four refusals each carry their own reason text", () => {
  const idx = realIndex();
  const reason = (t, bad) => {
    const b = clone(idx);
    b.symbols.order[t] = bad;
    try { validateIndex(b); } catch (e) { assert.ok(e instanceof DataError && e.code === "bad-order", JSON.stringify(bad)); return e.reason; }
    assert.fail("accepted " + JSON.stringify(bad));
  };
  const texts = [reason("states", "read"), reason("states", ["read", "stranger"]), reason("states", ["read", "read"]), reason("kinds", [])];
  assert.equal(new Set(texts).size, 4, JSON.stringify(texts));
});

/* P1, P2, P8: the module map. */
const modIndex = () => JSON.parse(readFileSync(path.join(FIX, "modules", "index.json"), "utf8"));
const modStep = (id) => JSON.parse(readFileSync(path.join(FIX, "modules", "step", id + ".json"), "utf8"));

test("P1 KIND_CLASS has module: k-module", () => {
  assert.equal(KIND_CLASS.module, "k-module");
  assert.deepEqual(Object.keys(KIND_CLASS).sort(), ["def", "module", "structure", "theorem"]);
});

test("P2 module map: validates although its order lists omit rows; the table names and the order are kept apart", () => {
  const v = validateIndex(modIndex());
  assert.deepEqual(v.symbols.order, { kinds: ["module"], proofs: [], states: [] });
  assert.deepEqual([...v.symbols.names.kinds].sort(), ["def", "module", "structure", "theorem"]);
  assert.deepEqual([...v.symbols.names.states].sort(), ["census", "none", "read"]);
  assert.deepEqual([...v.symbols.names.proofs].sort(), ["none", "not_read", "read"]);
});

test("P2 module map: the strings set is EXACTLY the fixed list plus the words of every TABLE row (21 keys), not of the ordered rows", () => {
  const idx = modIndex();
  const v = validateIndex(idx);
  const rows = ["kinds", "proofs", "states"].flatMap((t) => Object.values(idx.symbols[t]).map((r) => r.words));
  const need = requiredStrings(v.symbols);
  assert.equal(need.length, 21);
  assert.deepEqual([...need].sort(), [...FIXED_STRINGS, ...rows].sort());
  assert.deepEqual(Object.keys(idx.strings).sort(), [...need].sort());
  const extra = clone(idx);
  extra.strings.bonus = "x";
  assert.throws(() => validateIndex(extra), (e) => e instanceof DataError && e.code === "extra-string");
  const missing = clone(idx);
  delete missing.strings.sheet_statement_read;          // a row that is in the table but NOT in the order
  assert.throws(() => validateIndex(missing), (e) => e instanceof DataError && e.code === "missing-string" && e.message.includes("sheet_statement_read"));
});

test("P2 module map: a card is checked against the TABLE (state none, proof none are table names although the order omits them); a stranger is refused", () => {
  const v = validateIndex(modIndex());
  const st = validateStep(modStep("mod-core"), v);
  assert.equal(st.card.kind, "module");
  assert.equal(st.card.state, "none");
  assert.equal(st.card.proof, "none");
  assert.equal(st.children.length, 3);
  for (const [field, code] of [["kind", "unknown-kind"], ["state", "unknown-state"], ["proof", "unknown-proof"]]) {
    const b = modStep("mod-core");
    b.card[field] = "lemma";
    assert.throws(() => validateStep(b, v), (e) => e instanceof DataError && e.code === code, field);
  }
});

test("P2 module map: loads end to end (index, roots, children, the sibling link)", async () => {
  const d = createData(dirFetch(path.join(FIX, "modules")));
  const idx = await d.loadIndex();
  assert.deepEqual(idx.top, ["mod-core", "mod-tools"]);
  const roots = await d.loadRoots();
  assert.equal(roots.length, 2);
  assert.ok(roots.every((r) => r.data.kind === "module"));
  const kids = await d.loadChildren("mod-core");
  assert.equal(kids.length, 3);
  assert.equal(kids.reduce((n, k) => n + k.links.length, 0), 1);
  assert.equal(d.meta("mod-core-basic").kind, "module");
});

test("P4 the live map: the full orders, the same 20 strings, nothing moved", () => {
  const idx = realIndex();
  const v = validateIndex(idx);
  assert.deepEqual(v.symbols.order, { kinds: ["theorem", "def", "structure"], proofs: ["read", "not_read", "none"], states: ["read", "census", "none"] });
  assert.deepEqual(v.symbols.names, v.symbols.order, "on the live map the table names and the order are the same lists");
  assert.deepEqual([...requiredStrings(v.symbols)].sort(), Object.keys(idx.strings).sort());
  assert.equal(requiredStrings(v.symbols).length, 20);
});

test("SECTION 8 symbols: exact key sets at every level (an extra or a missing key is refused)", () => {
  const idx = realIndex();
  for (const where of [["symbols"], ["symbols", "order"], ["symbols", "kinds", "theorem"], ["symbols", "proofs", "read"], ["symbols", "states", "none"]]) {
    const get = (o) => where.reduce((a, k) => a[k], o);
    const extra = clone(idx);
    get(extra).unexpected = "x";
    assert.throws(() => validateIndex(extra), (e) => e instanceof DataError && e.code === "extra-key", where.join(".") + " extra");
    for (const k of Object.keys(get(idx))) {
      const miss = clone(idx);
      delete get(miss)[k];
      assert.throws(() => validateIndex(miss), DataError, where.join(".") + " lacks " + k);
    }
  }
});

test("SECTION 8: `class` and `text` must be strings and are IGNORED; the page's class comes only from its own tables", () => {
  const idx = realIndex();
  for (const t of ["kinds", "proofs", "states"]) {
    const name = Object.keys(idx.symbols[t])[0];
    for (const field of ["class", "text", "words"]) {
      for (const bad of [7, null, [], {}, true]) {
        const b = clone(idx);
        b.symbols[t][name][field] = bad;
        assert.throws(() => validateIndex(b), (e) => e instanceof DataError && e.code === "bad-type", t + "." + name + "." + field + " = " + JSON.stringify(bad));
      }
    }
  }
  const hostile = clone(idx);
  hostile.symbols.kinds.theorem.class = '" onmouseover="x';
  hostile.symbols.kinds.theorem.text = "<img src=x onerror=alert(1)>";
  const v = validateIndex(hostile);
  assert.ok(!JSON.stringify(v).includes("onmouseover") && !JSON.stringify(v).includes("<img"), "neither class nor text is carried into the page's data");
});

test("SECTION 8: a symbols name the page has no table entry for is refused, per table", () => {
  const idx = realIndex();
  for (const [t, code, order] of [["kinds", "unknown-kind"], ["proofs", "unknown-proof"], ["states", "unknown-state"]]) {
    const b = clone(idx);
    b.symbols[t].stranger = { class: "x", text: "x", words: Object.values(idx.symbols[t])[0].words };
    b.symbols.order[t] = [...b.symbols.order[t], "stranger"];
    assert.throws(() => validateIndex(b), (e) => e instanceof DataError && e.code === code, t);
  }
});

test("SECTION 8 strings: EXACTLY the required set; each missing key and each extra key is a named refusal", () => {
  const idx = realIndex();
  const need = requiredStrings(validateIndex(idx).symbols);
  for (const k of need) {
    const b = clone(idx);
    delete b.strings[k];
    assert.throws(() => validateIndex(b), (e) => e instanceof DataError && e.code === "missing-string" && e.message.includes(k), "missing " + k);
    const empty = clone(idx);
    empty.strings[k] = "";
    assert.throws(() => validateIndex(empty), (e) => e instanceof DataError && e.code === "missing-string", "empty " + k);
  }
  for (const extra of ["key_proofs_heading", "bonus", "status_read", "key_state_read", "key_kind_lemma"]) {
    const b = clone(idx);
    b.strings[extra] = "a word";
    assert.throws(() => validateIndex(b), (e) => e instanceof DataError && e.code === "extra-string" && e.message.includes(extra), "extra " + extra);
  }
  // a `words` that names no key of strings: the row's words key is then a missing string
  const dangling = clone(idx);
  dangling.symbols.proofs.read.words = "no_such_key";
  assert.throws(() => validateIndex(dangling), (e) => e instanceof DataError && e.code === "missing-string" && e.message.includes("no_such_key"));
  // two rows may share a words key (one label, two symbols): the set stays exact
  const shared = clone(idx);
  shared.symbols.kinds.def.words = shared.symbols.kinds.theorem.words;
  delete shared.strings.key_kind_def;
  assert.equal(validateIndex(shared).symbols.words.kinds.def, "key_kind_theorem");
});

test("SECTION 8 cards: `proof` is a required key with the three values; nothing else is accepted; meta carries it", async () => {
  const v = validateIndex(realIndex());
  const step = JSON.parse(readFileSync(path.join(FIX, "real", "step", "a1.json"), "utf8"));
  const seen = new Set();
  for (const c of [step.card, ...step.children]) seen.add(c.proof);
  for (const val of ["read", "not_read", "none"]) {
    const b = clone(step);
    b.card.proof = val;
    assert.equal(validateStep(b, v).card.proof, val);
    const c = clone(step);
    c.children[0].proof = val;
    assert.equal(validateStep(c, v).children[0].proof, val);
  }
  for (const bad of ["maybe", "Read", "", null, 1, [], {}, "read "]) {
    for (const where of ["card", "child"]) {
      const b = clone(step);
      (where === "card" ? b.card : b.children[0]).proof = bad;
      assert.throws(() => validateStep(b, v), (e) => e instanceof DataError && e.code === "unknown-proof", where + " " + JSON.stringify(bad));
    }
  }
  const missing = clone(step);
  delete missing.children[0].proof;
  assert.throws(() => validateStep(missing, v), (e) => e instanceof DataError && e.code === "missing-key");
  const d = createData(real());
  await d.loadIndex();
  await d.loadRoots();
  assert.equal(d.meta("goal-chain").proof, "not_read");
  await d.loadChildren("goal-chain");
  assert.ok(["read", "not_read", "none"].includes(d.meta("a1").proof));
});

test("SECTION 8 fixtures: every real step carries a proof derived from its card (definitions and structures have none to read)", () => {
  const dir = path.join(FIX, "real", "step");
  let n = 0;
  const counts = { read: 0, not_read: 0, none: 0 };
  for (const f of readdirSync(dir)) {
    const st = JSON.parse(readFileSync(path.join(dir, f), "utf8"));
    for (const c of [st.card, ...st.children]) {
      n++;
      counts[c.proof]++;
      assert.equal(c.proof === "none", c.kind !== "theorem", c.id + ": " + c.kind + " -> " + c.proof);
    }
  }
  assert.ok(n > 23 && counts.read > 0 && counts.not_read > 0 && counts.none > 0, JSON.stringify(counts));
});


/* ---------------------------------------------------------------------------------- K2: which load failures are a notice */

test("K2: the notice arm is an explicit allow-list of KNOWN codes: a rejected fetch and the non-2xx statuses; everything else is not", () => {
  for (const yes of ["fetch-failed", "http-404", "http-500", "http-503", "http-403", "http-301", "http-304", "http-100", "http-599"])
    assert.equal(isTransportCode(yes), true, yes);
  for (const no of ["http-200", "http-204", "http-299", "http-undefined", "http-", "http-0", "http-99", "http-600", "http-4040", "http-40x", "http-404 ", "HTTP-404",
    "fetch-failed ", "Fetch-failed", "fetch-failed2", "not-json", "bad-format", "bad-id", "bad-title", "unknown-kind", "unknown-proof", "missing-key", "extra-key", "id-mismatch",
    "commit-mismatch", "child-count", "bad-link", "bad-path", "bad-order", "weird-code", "", "x", " "])
    assert.equal(isTransportCode(no), false, JSON.stringify(no));
  for (const notAString of [undefined, null, 404, {}, [], ["fetch-failed"], true])
    assert.equal(isTransportCode(notAString), false, String(notAString));
});

test("K2: the codes the data layer really throws for a rejected fetch and for a bad status are the ones on the allow-list; data that arrived is not", async () => {
  const code = async (fetchLike) => {
    const d = createData(fetchLike);
    try { await d.loadIndex(); } catch (e) { return e instanceof DataError ? e.code : "NOT-A-DATAERROR"; }
    return "no-error";
  };
  assert.equal(await code(async () => { throw new TypeError("network down"); }), "fetch-failed");
  for (const status of [404, 500, 503]) {
    const c = await code(async () => ({ ok: false, status, json: async () => ({}) }));
    assert.equal(c, "http-" + status);
    assert.equal(isTransportCode(c), true);
  }
  assert.equal(isTransportCode(await code(async () => ({ ok: true, status: 200, json: async () => { throw new SyntaxError("x"); } }))), false, "not-json arrived");
  assert.equal(isTransportCode(await code(async () => ({ ok: true, status: 200, json: async () => ({ format: 2 }) }))), false, "a contract refusal arrived");
  assert.equal(isTransportCode(await code(async () => undefined)), false, "no response object at all is not a recognised status");
});


test("S5: the sheet's proof class comes from a page-owned table keyed exactly like PROOF_CLASS; only `none` has a class", () => {
  assert.deepEqual(Object.keys(SHEET_PROOF_CLASS), Object.keys(PROOF_CLASS));
  assert.deepEqual(Object.entries(SHEET_PROOF_CLASS).filter(([, v]) => v !== ""), [["none", "sheet-proof-none"]]);
  assert.ok(Object.isFrozen(SHEET_PROOF_CLASS));
});
