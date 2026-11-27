/* The file neighbourhood's data: graph/uses.json (format 3), validated. Like data.js and spine.js, an invalid file REJECTS with a DataError that names its
   reason; nothing partial is returned and no string of a refusal reaches the page. The page reads, of the file, only `titles`, `uses` and `used_by`; `imports`
   and `lib_index_rows` must still be of their shape, so a file that drifted is refused here and not found later.

   A FILE is a key of `uses` (the page names no kind word here: a title row's kind is checked against the index's own list of kinds, nothing more). */
import { isId } from "./dom.js";
import { DataError } from "./data.js";

const has = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const isObj = (v) => v !== null && typeof v === "object" && !Array.isArray(v);
const isStr = (v) => typeof v === "string";
const nonEmpty = (v) => isStr(v) && v !== "";
const shown = (v) => { let t; try { t = JSON.stringify(v); } catch (e) { t = undefined; } return t === undefined ? String(typeof v) : t.slice(0, 60); };

/* A library row's keys, written as an object's own keys: a quoted `file` would read as a kind name to the page's source gate (A1). */
const LIB_ROW_KEYS = Object.freeze(Object.keys({ file: 0, source: 0, text: 0 }));

function exactKeys(obj, required, where) {
  if (!isObj(obj)) throw new DataError("bad-type", where + " is not an object");
  for (const k of required) if (!has(obj, k)) throw new DataError("missing-key", where + " lacks " + k);
  for (const k of Object.keys(obj)) if (!required.includes(k)) throw new DataError("extra-key", where + " has an unknown key");
}

/* titles: one row per step, {kind, path, title}; the keys are exactly as many as the index says (`steps`) and hold every top id; a row's kind is one of the
   index's kinds, its path is a list of ids that are themselves keys, and no path holds its own row's id. */
function titlesOf(v, ctx) {
  if (!isObj(v)) throw new DataError("bad-titles", "uses titles is not an object");
  const ids = Object.keys(v);
  if (ids.length !== ctx.steps) throw new DataError("bad-titles", "uses titles holds " + ids.length + " steps, the index says " + ctx.steps);
  for (const t of ctx.top) if (!has(v, t)) throw new DataError("bad-titles", "uses titles lacks the top step " + shown(t));
  const out = new Map();
  for (const id of ids) {
    if (!isId(id)) throw new DataError("bad-titles", "uses titles has a key that is not a step id: " + shown(id));
    const r = v[id];
    const where = "uses titles row " + shown(id);
    exactKeys(r, ["kind", "path", "title"], where);
    if (!isStr(r.kind) || !ctx.kinds.includes(r.kind)) throw new DataError("bad-titles", where + " kind is not one the index lists: " + shown(r.kind));
    if (!Array.isArray(r.path) || !r.path.every((p) => isStr(p) && has(v, p) && p !== id)) throw new DataError("bad-titles", where + " path is not a list of other steps");
    if (!nonEmpty(r.title)) throw new DataError("bad-titles", where + " title is not a non-empty string");
    out.set(id, { kind: r.kind, path: r.path.slice(), title: r.title });
  }
  return out;
}

/* A side's rows: [{id, names, same_group}] sorted by id (strictly: no id twice), each id a file other than the owner, names a positive whole number. */
function rowsOf(list, owner, files, where) {
  if (!Array.isArray(list)) throw new DataError("bad-uses", where + " is not a list");
  let prev = null;
  return list.map((r) => {
    exactKeys(r, ["id", "names", "same_group"], where + " row");
    if (!isStr(r.id) || !files.has(r.id)) throw new DataError("bad-uses", where + " row names a file the map does not have: " + shown(r.id));
    if (r.id === owner) throw new DataError("bad-uses", where + " row is the file itself");
    if (prev !== null && !(prev < r.id)) throw new DataError("bad-uses", where + " rows are not sorted by id, once each");
    prev = r.id;
    if (!Number.isInteger(r.names) || r.names < 1) throw new DataError("bad-uses", where + " row names is not a positive whole number: " + shown(r.names));
    if (typeof r.same_group !== "boolean") throw new DataError("bad-uses", where + " row same_group is not a boolean");
    return { id: r.id, names: r.names, same_group: r.same_group };
  });
}

function sideOf(v, files, what) {
  if (!isObj(v)) throw new DataError("bad-uses", "uses " + what + " is not an object");
  const keys = Object.keys(v);
  if (keys.length !== files.size || !keys.every((k) => files.has(k))) throw new DataError("bad-uses", "uses " + what + " does not have exactly the files as keys");
  const out = new Map();
  for (const k of keys) out.set(k, rowsOf(v[k], k, files, "uses " + what + " " + shown(k)));
  return out;
}

/* validateUses(raw, ctx): ctx = {commit, steps, top, kinds}, taken from the VALIDATED index (data.js validateIndex's record: its commit, its `steps` count, its
   top ids and the kinds of its symbols). Returns {titles: Map, files: [ids], uses: Map, usedBy: Map}. */
export function validateUses(raw, ctx) {
  if (!isObj(ctx) || !Number.isInteger(ctx.steps) || !Array.isArray(ctx.top) || !Array.isArray(ctx.kinds) || !isStr(ctx.commit))
    throw new TypeError("validateUses takes the validated index's commit, steps, top and kinds");
  exactKeys(raw, ["commit", "format", "imports", "lib_index_rows", "titles", "used_by", "uses"], "uses file");
  if (raw.format !== 3) throw new DataError("bad-format", "uses format is not 3");
  if (!nonEmpty(raw.commit) || raw.commit !== ctx.commit) throw new DataError("bad-commit", "uses commit is not the index's commit");
  const titles = titlesOf(raw.titles, ctx);
  if (!isObj(raw.uses)) throw new DataError("bad-uses", "uses uses is not an object");
  const files = new Set(Object.keys(raw.uses));
  for (const f of files) {
    if (!titles.has(f)) throw new DataError("bad-uses", "uses names a file that titles lacks: " + shown(f));
    for (const row of titles.values()) if (row.path.includes(f)) throw new DataError("bad-uses", "uses names a file that is an ancestor of a step: " + shown(f));
  }
  const uses = sideOf(raw.uses, files, "uses");
  const usedBy = sideOf(raw.used_by, files, "used_by");
  /* used_by is the EXACT inverse of uses: the same pairs with the same weights. The first pair that differs is named. */
  for (const [a, rows] of uses) {
    for (const r of rows) {
      const back = usedBy.get(r.id).find((x) => x.id === a);
      if (!back || back.names !== r.names || back.same_group !== r.same_group)
        throw new DataError("uses-inverse-mismatch", "used_by is not the inverse of uses at the pair " + shown(a) + " -> " + shown(r.id));
    }
  }
  for (const [b, rows] of usedBy) {
    for (const r of rows) {
      if (!uses.get(r.id).some((x) => x.id === b))
        throw new DataError("uses-inverse-mismatch", "used_by has a pair that uses lacks: " + shown(r.id) + " -> " + shown(b));
    }
  }
  /* imports and lib_index_rows: shape only. */
  if (!isObj(raw.imports)) throw new DataError("bad-uses", "uses imports is not an object");
  const ik = Object.keys(raw.imports);
  if (ik.length !== files.size || !ik.every((k) => files.has(k) && Array.isArray(raw.imports[k]) && raw.imports[k].every((x) => isStr(x) && files.has(x))))
    throw new DataError("bad-uses", "uses imports is not a list of files for each file");
  if (!Array.isArray(raw.lib_index_rows)) throw new DataError("bad-uses", "uses lib_index_rows is not a list");
  for (const r of raw.lib_index_rows) {
    exactKeys(r, LIB_ROW_KEYS, "uses lib_index_rows row");
    if (!nonEmpty(r.file) || !nonEmpty(r.source) || !isStr(r.text)) throw new DataError("bad-uses", "uses lib_index_rows row is not three strings");
  }
  return { titles, files: [...files], uses, usedBy };
}
