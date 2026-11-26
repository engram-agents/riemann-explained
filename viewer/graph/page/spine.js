/* The Graph view's data: graph/spine.json (docs/tools.md "The spine"), validated, and its adapter to the engine's NodeSpec.
   Like data.js, an invalid file REJECTS with a DataError that names its reason; nothing partial is ever returned, and no string
   of a refusal reaches the page. The page reads, of a node, only `id`, `file`, `content`, `theorem` and `names`; the three keys
   it does not draw (`constants`, `mentions`, `counts`) must still be of their shape, so a file that drifted is refused here and
   not found later. The links the engine draws are the ones in the transitive reduction. */
import { isId } from "./dom.js";
import { DataError } from "./data.js";

/* The one basis value this page knows for the spine's links: a spine link means the upper result reaches the lower through any chain of uses. */
export const SPINE_BASIS = "reaches-through-any-chain-of-uses";
const SPINE_ID = /^spine-[a-z0-9-]+$/;
const SPINE_ID_MAX = 64;
const SPINE_SOURCE = "grh/INDEX.md";
/* The node's keys, written as an object's own keys: a quoted `file` would read as a kind name to the page's source gate (A1). */
const NODE_KEYS = Object.freeze(Object.keys({ constants: 0, content: 0, counts: 0, file: 0, id: 0, mentions: 0, names: 0, source: 0, theorem: 0 }));

const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const isStr = (v) => typeof v === "string";
const nonEmpty = (v) => isStr(v) && v !== "";
const shown = (v) => { let t; try { t = JSON.stringify(v); } catch (e) { t = undefined; } return t === undefined ? String(typeof v) : t.slice(0, 60); };

/* Exactly these keys, none missing, none extra: the same rule and codes as data.js. */
function exactKeys(obj, required, where) {
  if (!isObj(obj)) throw new DataError("bad-type", where + " is not an object");
  for (const k of required) if (!has(obj, k)) throw new DataError("missing-key", where + " lacks " + k);
  for (const k of Object.keys(obj)) if (!required.includes(k)) throw new DataError("extra-key", where + " has an unknown key");
}

function edgeBasisOf(v, ctx) {
  if (!isObj(v) || Object.keys(v).length !== 2 || !has(v, "basis") || !has(v, "words"))
    throw new DataError("bad-edge-basis", "spine edge_basis is not exactly {basis, words}");
  if (v.basis !== SPINE_BASIS) throw new DataError("bad-edge-basis", "spine edge_basis basis is not the one this page knows: " + shown(v.basis));
  if (!nonEmpty(v.words)) throw new DataError("bad-edge-basis", "spine edge_basis words is not a key name: " + shown(v.words));
  if (ctx.edgeBasis && v.words === ctx.edgeBasis.words) throw new DataError("bad-edge-basis", "spine edge_basis words is the index's own words key: " + shown(v.words));
  if (!has(ctx.strings, v.words)) throw new DataError("bad-edge-basis", "spine edge_basis words is not a key of the index strings: " + shown(v.words));
  return v.words;
}

function nodeOf(n, i, seen) {
  const where = "spine node " + i;
  exactKeys(n, NODE_KEYS, where);
  if (!isStr(n.id) || !SPINE_ID.test(n.id) || n.id.length > SPINE_ID_MAX) throw new DataError("bad-spine-node", where + " id is not a spine id: " + shown(n.id));
  if (seen.has(n.id)) throw new DataError("bad-spine-node", where + " id repeats an earlier node");
  if (!isId(n.file)) throw new DataError("bad-spine-node", where + " file is not a step id, got " + shown(n.file));
  if (n.source !== SPINE_SOURCE) throw new DataError("bad-spine-node", where + " source is not the index file, got " + shown(n.source));
  if (!nonEmpty(n.content)) throw new DataError("bad-spine-node", where + " content is not a non-empty string");
  if (!nonEmpty(n.theorem)) throw new DataError("bad-spine-node", where + " theorem is not a non-empty string");
  if (!Array.isArray(n.names) || n.names.length === 0 || !n.names.every(nonEmpty)) throw new DataError("bad-spine-node", where + " names is not a non-empty list of non-empty strings");
  if (!Array.isArray(n.constants)) throw new DataError("bad-spine-node", where + " constants is not a list");
  if (!Array.isArray(n.mentions)) throw new DataError("bad-spine-node", where + " mentions is not a list");
  if (!isObj(n.counts)) throw new DataError("bad-spine-node", where + " counts is not an object");
  seen.add(n.id);
  return { id: n.id, file: n.file, content: n.content, names: n.names.slice(), theorem: n.theorem };
}

function linkOf(l, i, ids, pairs) {
  const where = "spine link " + i;
  exactKeys(l, ["from", "in_reduction", "to"], where);
  if (!isStr(l.from) || !ids.has(l.from)) throw new DataError("bad-spine-link", where + " from is not a node of the file, got " + shown(l.from));
  if (!isStr(l.to) || !ids.has(l.to)) throw new DataError("bad-spine-link", where + " to is not a node of the file, got " + shown(l.to));
  if (l.from === l.to) throw new DataError("bad-spine-link", where + " rests on itself");
  if (typeof l.in_reduction !== "boolean") throw new DataError("bad-spine-link", where + " in_reduction is not a boolean");
  const key = l.from + "\n" + l.to;
  if (pairs.has(key)) throw new DataError("bad-spine-link", where + " repeats an earlier link");
  pairs.add(key);
  return { from: l.from, to: l.to, in_reduction: l.in_reduction };
}

/* The links in the reduction must have no cycle: the engine lays the nodes out in rows by dependency. Kahn's method, iterative. */
function refuseReductionCycle(nodes, links) {
  const out = new Map(nodes.map((n) => [n.id, []]));
  const indeg = new Map(nodes.map((n) => [n.id, 0]));
  for (const l of links) if (l.in_reduction) { out.get(l.from).push(l.to); indeg.set(l.to, indeg.get(l.to) + 1); }
  const ready = nodes.filter((n) => indeg.get(n.id) === 0).map((n) => n.id);
  let done = 0;
  while (ready.length > 0) {
    const id = ready.pop();
    done += 1;
    for (const to of out.get(id)) { indeg.set(to, indeg.get(to) - 1); if (indeg.get(to) === 0) ready.push(to); }
  }
  if (done !== nodes.length) throw new DataError("bad-spine-link", "spine links in the reduction hold a cycle");
}

/* validateSpine(raw, ctx): ctx is the VALIDATED index, data.js validateIndex's record: its `commit`, its `strings` and its `edgeBasis` (absent when the
   index has none; the spine's words key must not be the one it names). A raw index.json (its key is `edge_basis`) is a TypeError: handed one, the
   comparison with the index's own key would be skipped without a word. Returns {nodes, links, words}. */
export function validateSpine(raw, ctx) {
  if (!isObj(ctx) || has(ctx, "edge_basis") || !isObj(ctx.strings)) throw new TypeError("validateSpine takes the validated index");
  exactKeys(raw, ["commit", "edge_basis", "format", "links", "nodes"], "spine");
  if (raw.format !== 1) throw new DataError("bad-format", "spine format is not 1");
  if (!nonEmpty(raw.commit) || raw.commit !== ctx.commit) throw new DataError("bad-commit", "spine commit is not the index's commit");
  const words = edgeBasisOf(raw.edge_basis, ctx);
  if (!Array.isArray(raw.nodes) || raw.nodes.length === 0) throw new DataError("bad-spine-node", "spine nodes is empty or not a list");
  if (!Array.isArray(raw.links)) throw new DataError("bad-spine-link", "spine links is not a list");
  const seen = new Set();
  const nodes = raw.nodes.map((n, i) => nodeOf(n, i, seen));
  const pairs = new Set();
  const links = raw.links.map((l, i) => linkOf(l, i, seen, pairs));
  refuseReductionCycle(nodes, links);
  return { nodes, links, words };
}

/* The engine's roots: one NodeSpec per node, in the file's order, a leaf with its own one-element path; its links are the file's links in the
   reduction that start at it, each ending at the other node's one-element path. `data` carries what the face and the sheet read. */
export function spineRoots(spine) {
  return spine.nodes.map((n) => ({
    id: n.id,
    childCount: 0,
    links: spine.links.filter((l) => l.in_reduction && l.from === n.id).map((l) => ({ to: l.to, toPath: [l.to] })),
    parentLinksTo: false,
    path: [n.id],
    data: { content: n.content, file: n.file, names: n.names.slice(), theorem: n.theorem },
  }));
}
