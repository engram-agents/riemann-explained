import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync, existsSync, readdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { createData, DataError, validateIndex, validateStep, requiredStrings } from "../data.js";

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
  assert.deepEqual(v.symbols.kinds, ["theorem", "def", "structure"]);
  assert.deepEqual(v.symbols.states, ["read", "census", "none"]);
  const req = requiredStrings(v.symbols);
  for (const k of ["parts_n", "part_one", "open_parts", "close_parts", "claim_more", "claim_less", "crumb_label", "link_refused",
    "status_read", "status_census", "status_none", "key_kind_theorem", "key_kind_def", "key_kind_structure", "key_state_read", "key_state_census", "key_state_none"])
    assert.ok(req.includes(k), k);
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
