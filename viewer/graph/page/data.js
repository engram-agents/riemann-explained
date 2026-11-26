/* The adapter from build_site's graph files (data contract v1) to the engine's NodeSpec.
   Every field of graph/index.json and graph/step/<id>.json is checked here. An invalid file REJECTS with a DataError
   that names its reason; nothing partial is ever returned. This module is the engine's `loadChildren`. */
import { isId, stepPath } from "./dom.js";

/* The enumerated class tables (R3): a kind, state or proof reaches a class name only through these. One that the
   contract's `symbols` lists but that is not here is a refusal, never a blank. The `class` the builder writes in a
   symbols row is checked as a string and IGNORED. */
export const KIND_CLASS = Object.freeze({ theorem: "k-theorem", def: "k-def", structure: "k-structure", part: "k-part", group: "k-group", file: "k-file" });
export const STATE_CLASS = Object.freeze({ read: "s-read", census: "s-census", none: "s-none" });
export const PROOF_CLASS = Object.freeze({ read: "p-read", not_read: "p-not-read", none: "p-none" });
/* The class the SHEET takes from the shown card's `proof` (never from any text): only `none` has one, because a card with no proof
   keeps the list page's proof line (it says why there is none). graph.css hides the list page's other lines under the sheet. */
export const SHEET_PROOF_CLASS = Object.freeze({ read: "", not_read: "", none: "sheet-proof-none" });

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

/* The runtime words the page reads from index.json `strings`: the fixed list, plus the `words` key of every symbols TABLE row,
   whether or not the order lists it (the legend and the sheet's status line read the same name per symbol). `strings` must be
   EXACTLY this set. */
export const FIXED_STRINGS = Object.freeze(["parts_n", "part_one", "open_parts", "close_parts", "claim_more", "claim_less", "crumb_label",
  "link_refused", "parts_failed_notice", "key_kinds_heading", "key_states_heading"]);
/* Strings keys the page reads when the builder supplies them and ignores otherwise (the live map has none): allowed in `strings`, never required. */
export const OPTIONAL_STRINGS = Object.freeze(["key_kinds_note", "key_scope_text"]);
/* The strings the page reads ONLY because `edge_basis` is present (data contract section 25): the key's line heading, and the one key
   `edge_basis.words` names. They are neither fixed nor optional: validateIndex adds them to the required set when edge_basis is there, and
   without it they are not read, so their presence is an extra-string (the page reads exactly what it draws). */
export const EDGE_BASIS_HEADING = "key_lines_heading";
/* The one basis value this page knows for an index's links: the names written in the source, from the compiled index. */
export const EDGE_BASIS = "names-written-in-source-from-compiled-index";

/* An optional strings key that is present but empty is refused under its own code (a required key that is absent or empty is
   "missing-string"). The rule is keyed to the set it is handed, never to a name. */
export function refuseEmptyOptional(strings, optional) {
  for (const k of optional) {
    if (has(strings, k) && strings[k] === "") throw new DataError("empty-string", "index strings holds an empty optional key " + k);
  }
}
const TABLES = Object.freeze([["kinds", KIND_CLASS, "unknown-kind"], ["proofs", PROOF_CLASS, "unknown-proof"], ["states", STATE_CLASS, "unknown-state"]]);

export function requiredStrings(symbols) {
  const out = FIXED_STRINGS.slice();
  for (const [t] of TABLES) for (const name of symbols.names[t]) out.push(symbols.words[t][name]);
  for (const name of Object.keys(symbols.cardWords)) out.push(symbols.cardWords[name]);
  for (const name of Object.keys(symbols.countWords)) out.push(symbols.countWords[name].one, symbols.countWords[name].many);
  return out;
}

/* symbols = {order: {kinds, proofs, states}, kinds|proofs|states: {name: {class, text, words}}}: exact key sets. A name the
   page has no table entry for is a refusal. The result keeps TWO things apart, one meaning each: `names[t]` is the TABLE's names
   (what a card's kind, state and proof are checked against, and whose `words` are all required) and `order[t]` is the builder's
   key list (what the key draws, in that order). An `order` list is a subset of the table's names with no duplicates; the builder
   lists exactly the rows that occur on the map, so states and proofs may be empty and kinds may not. `class` and `text` are
   strings and otherwise ignored; `words` is a string (that it is a key of `strings` is checked with the strings). A kinds row may
   also carry `card_words`, a non-empty string (the sheet's one line for that kind); `cardWords` maps the kind to it. It may carry `count_words` too,
   {one, many}, each a non-empty string (the foot's words for a card whose children are of this kind); `countWords` maps the kind to it. */
function symbolsOf(v) {
  exactKeys(v, ["order", "kinds", "proofs", "states"], [], "symbols");
  exactKeys(v.order, ["kinds", "proofs", "states"], [], "symbols.order");
  const out = { words: {}, names: {}, order: {}, cardWords: {}, countWords: {} };
  for (const [t, table, code] of TABLES) {
    const rows = v[t];
    if (!isObj(rows) || Object.keys(rows).length === 0) throw new DataError("bad-type", "symbols." + t + " is not a non-empty object");
    const names = Object.keys(rows);
    out.words[t] = {};
    for (const n of names) {
      if (!has(table, n)) throw new DataError(code, "symbols." + t + " names a value this page cannot draw");
      exactKeys(rows[n], ["class", "text", "words"], t === "kinds" ? ["card_words", "count_words"] : [], "symbols." + t + " row");
      if (!isStr(rows[n].class) || !isStr(rows[n].text) || !isStr(rows[n].words))
        throw new DataError("bad-type", "symbols." + t + " row has a class, text or words that is not a string");
      out.words[t][n] = rows[n].words;
      if (has(rows[n], "card_words")) {
        if (!isStr(rows[n].card_words) || rows[n].card_words === "") throw new DataError("bad-card-words", "symbols.kinds row has a card_words that is not a non-empty string");
        out.cardWords[n] = rows[n].card_words;
      }
      if (has(rows[n], "count_words")) {
        const cw = rows[n].count_words;
        if (!isObj(cw) || Object.keys(cw).length !== 2 || !has(cw, "one") || !has(cw, "many") || !isStr(cw.one) || cw.one === "" || !isStr(cw.many) || cw.many === "")
          throw new DataError("bad-count-words", "symbols.kinds row has a count_words that is not exactly {one, many} of non-empty strings");
        out.countWords[n] = { one: cw.one, many: cw.many };
      }
    }
    out.names[t] = names;
    out.order[t] = orderOf(v.order[t], names, "symbols.order." + t, t !== "kinds");
  }
  return out;
}
function orderOf(list, names, where, mayBeEmpty) {
  if (!Array.isArray(list)) throw new DataError("bad-order", where + " is not a list");
  if (!list.every((x) => typeof x === "string" && names.includes(x))) throw new DataError("bad-order", where + " names a row the table does not have");
  if (new Set(list).size !== list.length) throw new DataError("bad-order", where + " repeats a name");
  if (list.length === 0 && !mayBeEmpty) throw new DataError("bad-order", where + " is empty");
  return list.slice();
}

/* A short, bounded rendering of a refused value for a DataError's reason (never reaches the page: no string from an exception does). */
const shown = (v) => { let t; try { t = JSON.stringify(v); } catch (e) { t = undefined; } return t === undefined ? String(typeof v) : t.slice(0, 60); };

/* `edge_basis` (data contract section 25): exactly {basis, words}. `basis` is the one value this page knows; `words` is the name of a key
   PRESENT in `strings` (the key prints strings[words], and the page never names that key itself). Any other shape is bad-edge-basis. */
function edgeBasisOf(v, strings) {
  if (!isObj(v) || Object.keys(v).length !== 2 || !has(v, "basis") || !has(v, "words"))
    throw new DataError("bad-edge-basis", "index edge_basis is not exactly {basis, words}");
  if (v.basis !== EDGE_BASIS) throw new DataError("bad-edge-basis", "index edge_basis basis is not the one this page knows: " + shown(v.basis));
  if (!isStr(v.words) || v.words === "" || !has(strings, v.words))
    throw new DataError("bad-edge-basis", "index edge_basis words is not the name of a key in strings: " + shown(v.words));
  return { basis: v.basis, words: v.words };
}

/* A link may carry `weight` (a positive integer, the distinct names used) and `in_reduction` (a boolean, the link is in the transitive
   reduction of its set): BOTH or NEITHER (data contract section 20). The live map's links have neither.
   ERROR ORDER, pinned for a link with two faults: the key set is checked first, so an unknown key beside a bad flag is `extra-key`; only a
   link whose keys are all known reaches the flag checks, where one flag without the other, or a weight that is not a positive integer,
   is `bad-link-flags`. */
function linkOf(l, expectPathFrom, expectPathTo, where) {
  exactKeys(l, ["from", "to", "from_path", "to_path"], ["weight", "in_reduction"], where);
  const flagged = has(l, "weight") || has(l, "in_reduction");
  if (flagged) {
    if (!(has(l, "weight") && has(l, "in_reduction"))) throw new DataError("bad-link-flags", where + " has one of weight and in_reduction without the other");
    if (!isInt(l.weight) || l.weight < 1) throw new DataError("bad-link-flags", where + " has a weight that is not a positive integer");
    if (typeof l.in_reduction !== "boolean") throw new DataError("bad-link-flags", where + " has an in_reduction that is not a boolean");
  }
  idOf(l.from, where + ".from");
  idOf(l.to, where + ".to");
  const fp = idList(l.from_path, where + ".from_path");
  const tp = idList(l.to_path, where + ".to_path");
  if (!sameList(fp, expectPathFrom) || !sameList(tp, expectPathTo)) throw new DataError("bad-link", where + " has a path that is not its siblings' path");
  if (l.from === l.to) throw new DataError("bad-link", where + " rests on itself");
  const out = { from: l.from, to: l.to, from_path: fp, to_path: tp };
  if (flagged) { out.weight = l.weight; out.in_reduction = l.in_reduction; }
  return out;
}

export function validateIndex(raw) {
  exactKeys(raw, ["format", "commit", "max_children", "top", "rests_on", "steps", "symbols", "assets", "strings"], ["sibling_layout", "open_scale_floor", "edge_basis"], "index");
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
  for (const k of Object.values(symbols.cardWords))
    if (!has(raw.strings, k)) throw new DataError("missing-card-words", "index strings lacks the card word " + k);
  for (const k of Object.values(symbols.countWords).flatMap((c) => [c.one, c.many]))
    if (!has(raw.strings, k)) throw new DataError("missing-count-words", "index strings lacks the count word " + k);
  /* The set the strings check uses depends on edge_basis: present, the key's line heading and the key edge_basis.words names are read too
     (required, an empty one is empty-string); absent, neither is read, so key_lines_heading and key_lines_text are extra-string like any other. */
  const edgeBasis = has(raw, "edge_basis") ? edgeBasisOf(raw.edge_basis, raw.strings) : null;
  const edgeStrings = edgeBasis ? [EDGE_BASIS_HEADING, edgeBasis.words] : [];
  const need = requiredStrings(symbols);
  for (const k of need) {
    if (!has(raw.strings, k) || raw.strings[k] === "") throw new DataError("missing-string", "index strings lacks the runtime key " + k);
  }
  for (const k of edgeStrings) {
    if (!has(raw.strings, k)) throw new DataError("missing-string", "index strings lacks the edge basis key " + k);
    if (raw.strings[k] === "") throw new DataError("empty-string", "index strings holds an empty edge basis key " + k);
  }
  refuseEmptyOptional(raw.strings, OPTIONAL_STRINGS);
  for (const k of Object.keys(raw.strings)) {
    if (!need.includes(k) && !edgeStrings.includes(k) && !OPTIONAL_STRINGS.includes(k)) throw new DataError("extra-string", "index strings holds a key the page does not read: " + k);
  }
  const out = { commit: raw.commit, maxChildren: raw.max_children, top, rests, steps: raw.steps, symbols, strings: { ...raw.strings }, assets: { ...raw.assets } };
  if (edgeBasis) out.edgeBasis = edgeBasis;
  /* The two optional per-map keys (data contract sections 15 and 24), each absent on the live map and then absent from the record too.
     `sibling_layout`: the only value is "column". `open_scale_floor`: a finite number above 0 (the engine checks its upper bound). */
  if (has(raw, "sibling_layout")) {
    if (raw.sibling_layout !== "column") throw new DataError("bad-layout", "index sibling_layout is not column: " + shown(raw.sibling_layout));
    out.siblingLayout = raw.sibling_layout;
  }
  if (has(raw, "open_scale_floor")) {
    const f = raw.open_scale_floor;
    if (typeof f !== "number" || !Number.isFinite(f) || f <= 0) throw new DataError("bad-scale-floor", "index open_scale_floor is not a finite number above 0: " + shown(f));
    out.openScaleFloor = f;
  }
  return out;
}

/* The file-step rows (data contract section 22), validated and carried, not drawn by this page. */
const INDEX_ROWS_SOURCE = "grh/INDEX.md";
const INDEX_ROW_MAX = 4000;
const SPINE_ID = /^spine-[a-z0-9-]+$/;
function indexRowsOf(v) {
  if (!Array.isArray(v) || v.length === 0) throw new DataError("bad-index-rows", "step index_rows is not a non-empty list");
  return v.map((r) => {
    if (!isObj(r) || Object.keys(r).length !== 2 || !has(r, "source") || !has(r, "text"))
      throw new DataError("bad-index-rows", "step index_rows holds a row that is not exactly {source, text}");
    if (r.source !== INDEX_ROWS_SOURCE) throw new DataError("bad-index-rows", "step index_rows holds a row whose source is not " + INDEX_ROWS_SOURCE);
    if (!isStr(r.text) || r.text === "" || r.text.length > INDEX_ROW_MAX)
      throw new DataError("bad-index-rows", "step index_rows holds a row whose text is not a non-empty string of at most " + INDEX_ROW_MAX + " characters");
    return { source: r.source, text: r.text };
  });
}
function spineRowsOf(v) {
  if (!Array.isArray(v) || v.length === 0) throw new DataError("bad-spine-rows", "step spine_rows is not a non-empty list");
  for (const x of v) if (!isStr(x) || !SPINE_ID.test(x)) throw new DataError("bad-spine-rows", "step spine_rows holds a value that is not a spine id");
  if (new Set(v).size !== v.length) throw new DataError("bad-spine-rows", "step spine_rows repeats an id");
  return v.slice();
}

function closedOf(c, ctx, isChild, where) {
  exactKeys(c, ["id", "title", "kind", "state", "proof", "child_count", "path"].concat(isChild ? ["parent_rests_on"] : []), ["role", "child_kind"], where);
  idOf(c.id, where + ".id");
  if (!isStr(c.title) || c.title === "") throw new DataError("bad-title", where + " has no title");
  if (!isStr(c.kind) || !ctx.symbols.names.kinds.includes(c.kind)) throw new DataError("unknown-kind", where + " has a kind that symbols does not list");
  if (!isStr(c.state) || !ctx.symbols.names.states.includes(c.state)) throw new DataError("unknown-state", where + " has a state that symbols does not list");
  if (!isStr(c.proof) || !ctx.symbols.names.proofs.includes(c.proof)) throw new DataError("unknown-proof", where + " has a proof that symbols does not list");
  if (!isInt(c.child_count) || c.child_count < 0) throw new DataError("bad-count", where + " child_count is not a count");
  const path = idList(c.path, where + ".path");
  if (has(c, "role") && (!isStr(c.role) || c.role === "")) throw new DataError("bad-role", where + " role is not a non-empty string");
  if (isChild && typeof c.parent_rests_on !== "boolean") throw new DataError("bad-type", where + " parent_rests_on is not a boolean");
  if (has(c, "child_kind")) {
    if (!isStr(c.child_kind) || !ctx.symbols.names.kinds.includes(c.child_kind)) throw new DataError("unknown-child-kind", where + " has a child_kind that symbols does not list");
    if (c.child_count === 0) throw new DataError("bad-child-kind", where + " has a child_kind but no children");
  }
  const out = { id: c.id, title: c.title, kind: c.kind, state: c.state, proof: c.proof, child_count: c.child_count, path };
  if (has(c, "role")) out.role = c.role;
  if (has(c, "child_kind")) out.child_kind = c.child_kind;
  if (isChild) out.parent_rests_on = c.parent_rests_on;
  return out;
}

export function validateStep(raw, ctx) {
  exactKeys(raw, ["format", "commit", "id", "path", "card", "children", "rests_on"], ["index_rows", "spine_rows"], "step");
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
  if (has(card, "child_kind")) {
    const odd = children.find((k) => k.kind !== card.child_kind);
    if (odd) throw new DataError("child-kind-mismatch", "step " + raw.id + " declares child_kind " + card.child_kind + " but child " + odd.id + " is a " + odd.kind);
  }
  if (!Array.isArray(raw.rests_on)) throw new DataError("bad-type", "step.rests_on is not a list");
  const rests = raw.rests_on.map((l, i) => {
    const k = linkOf(l, here, here, "step.rests_on " + i);
    if (!seen.has(k.from) || !seen.has(k.to)) throw new DataError("bad-link", "step.rests_on names an id that is not a child of this step");
    return k;
  });
  /* `rests_on` keeps every link as the data gives it (a link flagged in_reduction false included); only the set handed to the engine
     (linksFrom in createData) drops in_reduction false. */
  const out = { id: raw.id, path, card, children, rests_on: rests };
  if (has(raw, "index_rows")) out.index_rows = indexRowsOf(raw.index_rows);
  if (has(raw, "spine_rows")) out.spine_rows = spineRowsOf(raw.spine_rows);
  return out;
}

/* THE FAILURE SPLIT. A failed load is one of two classes. TRANSPORT (the fetch rejected, or the answer had a non-2xx status) is
   a notice: the reader may try again. DATA that arrived and is invalid (not JSON, any contract refusal) is the fallback. This is
   the explicit allow-list of KNOWN codes for the first class (fetchJson below throws exactly `fetch-failed` and `http-<status>`);
   anything else, a code not named here, a non-DataError, an engine error, is the second class. */
export function isTransportCode(code) {
  if (typeof code !== "string") return false;
  if (code === "fetch-failed") return true;
  const m = /^http-([0-9]{3})$/.exec(code);
  if (!m) return false;
  const status = Number(m[1]);
  return status >= 100 && status <= 599 && !(status >= 200 && status <= 299);
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
    const m = { id: c.id, title: c.title, kind: c.kind, state: c.state, proof: c.proof, childCount: c.child_count, path: c.path.slice() };
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

  /* A link flagged in_reduction false is a use the reduction already implies by a longer chain: it is not handed to the engine as a premise link
     (Kepler's ruling). True, and a link with no flags (the live map), are handed over as before. */
  function linksFrom(rests, from) {
    return rests.filter((l) => l.from === from && l.in_reduction !== false).map((l) => ({ to: l.to, toPath: l.to_path.concat(l.to) }));
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

/* What the engine carries and hands back to renderFace: no role key when the builder gave none, no childKind key when the card names none. */
function dataOf(c) {
  const d = { title: c.title, kind: c.kind, state: c.state };
  if (has(c, "role")) d.role = c.role;
  if (has(c, "child_kind")) d.childKind = c.child_kind;
  return d;
}
