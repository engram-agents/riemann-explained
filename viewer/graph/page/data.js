/* The adapter from build_site's graph files (data contract v1) to the engine's NodeSpec.
   Every field of graph/index.json and graph/step/<id>.json is checked here. An invalid file REJECTS with a DataError
   that names its reason; nothing partial is ever returned. This module is the engine's `loadChildren`. */
import { isId, stepPath } from "./dom.js";

/* The enumerated class tables (R3): a kind or state reaches a class name only through these. A kind or state that
   the contract's `symbols` lists but that is not here is a refusal, never a blank. */
export const KIND_CLASS = Object.freeze({ theorem: "k-theorem", def: "k-def", structure: "k-structure" });
export const STATE_CLASS = Object.freeze({ read: "s-read", census: "s-census", none: "s-none" });

export class DataError extends Error {
  constructor(code, detail) {
    super(code + ": " + detail);
    this.name = "DataError";
    this.code = code;
    this.reason = detail;
  }
}

const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const isInt = (v) => typeof v === "number" && Number.isInteger(v);
const isStr = (v) => typeof v === "string";

/* Exactly these keys, none missing, none extra (the contract says "Nothing else"). */
function exactKeys(obj, required, optional, where) {
  if (!isObj(obj)) throw new DataError("bad-type", where + " is not an object");
  for (const k of required) if (!has(obj, k)) throw new DataError("missing-key", where + " lacks " + k);
  for (const k of Object.keys(obj))
    if (!required.includes(k) && !optional.includes(k)) throw new DataError("extra-key", where + " has an unknown key");
}

function idOf(v, where) {
  if (!isId(v)) throw new DataError("bad-id", where + " is not a valid step id");
  return v;
}
function idList(v, where) {
  if (!Array.isArray(v)) throw new DataError("bad-path", where + " is not a list");
  return v.map((x) => {
    if (!isId(x)) throw new DataError("bad-path", where + " holds an invalid id");
    return x;
  });
}
const sameList = (a, b) => a.length === b.length && a.every((x, i) => x === b[i]);

/* The runtime words the page uses, generated from the closed lists so a kind or state cannot exist without its words. */
export function requiredStrings(symbols) {
  const out = ["parts_n", "part_one", "open_parts", "close_parts", "claim_more", "claim_less", "crumb_label", "link_refused",
    "key_kinds_heading", "key_states_heading"];
  for (const k of symbols.kinds) out.push("key_kind_" + k);
  for (const s of symbols.states) out.push("key_state_" + s, "status_" + s);
  return out;
}

function nameList(v, table, code, where) {
  const names = Array.isArray(v) ? v : isObj(v) ? Object.keys(v) : null;
  if (!names || names.length === 0) throw new DataError("bad-type", where + " is not a non-empty list");
  for (const n of names) {
    if (!isStr(n) || !has(table, n)) throw new DataError(code, where + " names a value this page cannot draw");
  }
  return names.slice();
}

function symbolsOf(v) {
  exactKeys(v, ["kinds", "states"], ["order"], "symbols");
  let kinds = nameList(v.kinds, KIND_CLASS, "unknown-kind", "symbols.kinds");
  let states = nameList(v.states, STATE_CLASS, "unknown-state", "symbols.states");
  if (has(v, "order")) {
    exactKeys(v.order, [], ["kinds", "states"], "symbols.order");
    if (has(v.order, "kinds")) kinds = orderOf(v.order.kinds, kinds, "symbols.order.kinds");
    if (has(v.order, "states")) states = orderOf(v.order.states, states, "symbols.order.states");
  }
  return { kinds, states };
}
function orderOf(list, names, where) {
  if (!Array.isArray(list) || list.length !== names.length || !list.every((x) => names.includes(x)) || new Set(list).size !== list.length)
    throw new DataError("bad-type", where + " is not an ordering of the same names");
  return list.slice();
}

function linkOf(l, expectPathFrom, expectPathTo, where) {
  exactKeys(l, ["from", "to", "from_path", "to_path"], [], where);
  idOf(l.from, where + ".from");
  idOf(l.to, where + ".to");
  const fp = idList(l.from_path, where + ".from_path");
  const tp = idList(l.to_path, where + ".to_path");
  if (!sameList(fp, expectPathFrom) || !sameList(tp, expectPathTo)) throw new DataError("bad-link", where + " has a path that is not its siblings' path");
  if (l.from === l.to) throw new DataError("bad-link", where + " rests on itself");
  return { from: l.from, to: l.to, from_path: fp, to_path: tp };
}

export function validateIndex(raw) {
  exactKeys(raw, ["format", "commit", "max_children", "top", "rests_on", "steps", "symbols", "assets", "strings"], [], "index");
  if (raw.format !== 1) throw new DataError("bad-format", "index format is not 1");
  if (!isStr(raw.commit) || raw.commit === "") throw new DataError("bad-commit", "index commit is not a non-empty string");
  if (!isInt(raw.max_children) || raw.max_children < 1) throw new DataError("bad-type", "index max_children is not a positive integer");
  if (!Array.isArray(raw.top) || raw.top.length === 0) throw new DataError("bad-type", "index top is not a non-empty list");
  const top = raw.top.map((x) => idOf(x, "index top entry"));
  if (new Set(top).size !== top.length) throw new DataError("bad-id", "index top repeats an id");
  if (!Array.isArray(raw.rests_on)) throw new DataError("bad-type", "index rests_on is not a list");
  const rests = raw.rests_on.map((l, i) => {
    const k = linkOf(l, [], [], "index rests_on " + i);
    if (!top.includes(k.from) || !top.includes(k.to)) throw new DataError("bad-link", "index rests_on names a step that is not a top step");
    return k;
  });
  if (!isInt(raw.steps) || raw.steps < top.length) throw new DataError("bad-type", "index steps is not a count");
  const symbols = symbolsOf(raw.symbols);
  if (!isObj(raw.assets)) throw new DataError("bad-type", "index assets is not an object");
  for (const k of Object.keys(raw.assets)) {
    if (!/^[a-z0-9._/-]+$/.test(k) || !isStr(raw.assets[k]) || !/^[0-9a-f]{64}$/.test(raw.assets[k]))
      throw new DataError("bad-type", "index assets entry is not a path and a sha256");
  }
  if (!isObj(raw.strings)) throw new DataError("bad-type", "index strings is not an object");
  for (const k of Object.keys(raw.strings)) if (!isStr(raw.strings[k])) throw new DataError("bad-type", "index strings holds a non-string");
  for (const k of requiredStrings(symbols)) {
    if (!has(raw.strings, k) || raw.strings[k] === "") throw new DataError("missing-string", "index strings lacks the runtime key " + k);
  }
  return { commit: raw.commit, maxChildren: raw.max_children, top, rests, steps: raw.steps, symbols, strings: { ...raw.strings }, assets: { ...raw.assets } };
}

function closedOf(c, ctx, isChild, where) {
  exactKeys(c, ["id", "title", "kind", "state", "child_count", "path"].concat(isChild ? ["parent_rests_on"] : []), ["role"], where);
  idOf(c.id, where + ".id");
  if (!isStr(c.title) || c.title === "") throw new DataError("bad-title", where + " has no title");
  if (!isStr(c.kind) || !ctx.symbols.kinds.includes(c.kind)) throw new DataError("unknown-kind", where + " has a kind that symbols does not list");
  if (!isStr(c.state) || !ctx.symbols.states.includes(c.state)) throw new DataError("unknown-state", where + " has a state that symbols does not list");
  if (!isInt(c.child_count) || c.child_count < 0) throw new DataError("bad-count", where + " child_count is not a count");
  const path = idList(c.path, where + ".path");
  if (has(c, "role") && (!isStr(c.role) || c.role === "")) throw new DataError("bad-role", where + " role is not a non-empty string");
  if (isChild && typeof c.parent_rests_on !== "boolean") throw new DataError("bad-type", where + " parent_rests_on is not a boolean");
  const out = { id: c.id, title: c.title, kind: c.kind, state: c.state, child_count: c.child_count, path };
  if (has(c, "role")) out.role = c.role;
  if (isChild) out.parent_rests_on = c.parent_rests_on;
  return out;
}

export function validateStep(raw, ctx) {
  exactKeys(raw, ["format", "commit", "id", "path", "card", "children", "rests_on"], [], "step");
  if (raw.format !== 1) throw new DataError("bad-format", "step format is not 1");
  if (!isStr(raw.commit) || raw.commit === "") throw new DataError("bad-commit", "step commit is not a non-empty string");
  if (raw.commit !== ctx.commit) throw new DataError("commit-mismatch", "step commit differs from the index's");
  idOf(raw.id, "step.id");
  const path = idList(raw.path, "step.path");
  const card = closedOf(raw.card, ctx, false, "step.card");
  if (card.id !== raw.id) throw new DataError("id-mismatch", "step.card.id is not the step's id");
  if (!sameList(card.path, path)) throw new DataError("bad-path", "step.card.path is not the step's path");
  if (!Array.isArray(raw.children)) throw new DataError("bad-type", "step.children is not a list");
  const here = path.concat(raw.id);
  const seen = new Set();
  const children = raw.children.map((c, i) => {
    const k = closedOf(c, ctx, true, "step.children " + i);
    if (!sameList(k.path, here)) throw new DataError("bad-path", "a child's path is not this step's path plus its id");
    if (seen.has(k.id)) throw new DataError("bad-id", "a child id repeats");
    seen.add(k.id);
    return k;
  });
  if (card.child_count !== children.length) throw new DataError("child-count", "child_count " + card.child_count + " is not the number of children " + children.length);
  if (!Array.isArray(raw.rests_on)) throw new DataError("bad-type", "step.rests_on is not a list");
  const rests = raw.rests_on.map((l, i) => {
    const k = linkOf(l, here, here, "step.rests_on " + i);
    if (!seen.has(k.from) || !seen.has(k.to)) throw new DataError("bad-link", "step.rests_on names an id that is not a child of this step");
    return k;
  });
  return { id: raw.id, path, card, children, rests_on: rests };
}

/* Response -> parsed JSON, with a named reason for each way it can fail. */
async function fetchJson(fetchLike, address) {
  let r;
  try { r = await fetchLike(address); } catch (e) { throw new DataError("fetch-failed", "the request for " + address + " failed"); }
  if (!r || !r.ok) throw new DataError("http-" + (r && r.status), "the request for " + address + " was refused");
  try { return await r.json(); } catch (e) { throw new DataError("not-json", address + " is not JSON"); }
}

const CACHE_MAX = 32;

/* createData(fetchLike): fetchLike(address) -> Promise of a Response-like {ok, status, json()}. */
export function createData(fetchLike) {
  let index = null;
  const steps = new Map();      // id -> Promise of a validated step (bounded, oldest out)
  const metaOf = new Map();     // id -> what the breadcrumb needs about a step already seen

  function note(c) {
    const m = { id: c.id, title: c.title, kind: c.kind, state: c.state, childCount: c.child_count, path: c.path.slice() };
    if (has(c, "role")) m.role = c.role;
    metaOf.set(c.id, m);
  }

  async function loadIndex() {
    if (!index) index = validateIndex(await fetchJson(fetchLike, "index.json"));
    return index;
  }

  async function loadStep(id) {
    if (!isId(id)) throw new DataError("bad-id", "not a valid step id");   // refused before any request
    const address = stepPath(id);
    const ctx = await loadIndex();
    if (!steps.has(id)) {
      const p = fetchJson(fetchLike, address).then((raw) => {
        const v = validateStep(raw, ctx);
        if (v.id !== id) throw new DataError("id-mismatch", address + " holds another step");
        return v;
      });
      steps.set(id, p);
      if (steps.size > CACHE_MAX) steps.delete(steps.keys().next().value);
      p.catch(() => { if (steps.get(id) === p) steps.delete(id); });
    }
    const v = await steps.get(id);
    note(v.card);
    v.children.forEach(note);
    return v;
  }

  function linksFrom(rests, from) {
    return rests.filter((l) => l.from === from).map((l) => ({ to: l.to, toPath: l.to_path.concat(l.to) }));
  }

  async function loadRoots() {
    const ctx = await loadIndex();
    const files = await Promise.all(ctx.top.map((id) => loadStep(id)));
    return files.map((f) => ({
      id: f.id, childCount: f.card.child_count, links: linksFrom(ctx.rests, f.id),
      parentLinksTo: false, path: f.path.concat(f.id), data: dataOf(f.card),
    }));
  }

  async function loadChildren(id) {
    const f = await loadStep(id);
    return f.children.map((c) => ({
      id: c.id, childCount: c.child_count, links: linksFrom(f.rests_on, c.id),
      parentLinksTo: c.parent_rests_on, path: c.path.concat(c.id), data: dataOf(c),
    }));
  }

  function meta(id) { return isId(id) && metaOf.has(id) ? { ...metaOf.get(id) } : undefined; }

  return { loadIndex, loadRoots, loadStep, loadChildren, meta };
}

/* What the engine carries and hands back to renderFace: no role key when the builder gave none. */
function dataOf(c) {
  const d = { title: c.title, kind: c.kind, state: c.state };
  if (has(c, "role")) d.role = c.role;
  return d;
}
