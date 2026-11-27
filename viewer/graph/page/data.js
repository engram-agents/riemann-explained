/* The adapter from build_site's graph files (data contract v1) to the engine's NodeSpec.
   Every field of graph/index.json and graph/step/<id>.json is checked here. An invalid file REJECTS with a DataError
   that names its reason; nothing partial is ever returned. This module is the engine's `loadChildren`. */
import { isId, stepPath } from "./dom.js";

/* The enumerated class tables (R3): a kind, state or proof reaches a class name only through these. One that the
   contract's `symbols` lists but that is not here is a refusal, never a blank. The `class` the builder writes in a
   symbols row is checked as a string and IGNORED. */
export const KIND_CLASS = Object.freeze({ theorem: "k-theorem", def: "k-def", structure: "k-structure", part: "k-part", group: "k-group", file: "k-file",
  lemma: "k-lemma", abbrev: "k-abbrev", instance: "k-instance", class: "k-class", inductive: "k-inductive" });
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
/* Strings keys the page reads when the builder supplies them and ignores otherwise (the live map has none): allowed in `strings`, never required.
   note_label and note_source are the words round the repository's note on a sheet; a step that carries a `note` needs both (`bad-note-strings`).
   The four TYPESET_STRINGS are the words of the maths-face view of a note (its label, the line under the source line, the two button labels); the page
   sets formulas in the maths face and draws the line and the button ONLY when all four are present, and otherwise renders the note as it always did. */
export const TYPESET_STRINGS = Object.freeze(["note_label_typeset", "note_typeset_line", "note_exact_button", "note_render_button"]);
/* The Graph view's words (the page reads them ONLY when the map carries both view words; see validateIndex): the switch's two labels, what a box is in the
   view, the sheet's label and its two lines, and the notice for a failed read of the spine. The spine's own sentence is one more key, whose NAME the page does
   not know: spine.json's edge_basis names it (spine.js), and the index may carry exactly one key beyond the lists. */
export const GRAPH_VIEW_STRINGS = Object.freeze(["view_cards", "view_graph", "graph_nodes_text", "spine_content_label", "spine_lives_in", "spine_show_file", "graph_failed_notice"]);
/* THE STATEMENT LEVEL's words (all-or-none): with ANY of them present ALL must be (non-empty), `bad-statement-strings` naming the first missing; with none the
   group is off and a step carrying a statement is refused. With the group on, `spine_content_label` (which labels the doc-string) is required too. */
export const STATEMENT_STRINGS = Object.freeze(["decl_show_lean", "decl_hide_lean", "decl_lean_note", "decl_uses_here", "decl_uses_elsewhere", "decl_no_note",
  "key_statements_heading", "key_statements_text", "decl_prompt_button", "decl_prompt_copied", "decl_prompt_note", "decl_heading_label", "decl_note_source"]);
/* One OPTIONAL statement word, outside the all-or-none group: `decl_reading_none`, the line above the prompt button. Allowed only with the group on (else it is an
   extra-string like any key the page does not read); present, it is non-empty (`empty-string`). */
export const READING_NONE = "decl_reading_none";
/* The eight kind words of the statement level: with the group on the builder writes ALL of them into `strings` even when only some kinds occur on the map,
   so each is a KNOWN optional string (non-empty when present, `empty-string`); a kind row that names one still makes it required, as for any `words`.
   With the group off they are extra-strings like any other key the page does not read. */
export const DECL_KIND_STRINGS = Object.freeze(["decl_kind_theorem", "decl_kind_lemma", "decl_kind_def", "decl_kind_abbrev", "decl_kind_structure", "decl_kind_instance", "decl_kind_class", "decl_kind_inductive"]);
/* Two more OPTIONAL statement words, as a PAIR (both or neither): the line under the other-files list that says how many library names are left out of it. One without the
   other is `bad-statement-strings`; with the group off they are extra-strings; present, each is non-empty. With both absent nothing is drawn. */
export const USES_LIBRARY_STRINGS = Object.freeze(["decl_uses_library_one", "decl_uses_library_many"]);
/* THE READING's words (Kepler 39806, Ariadne's note v2.1 section 9): the block on a statement card that carries an AI agent's reading. All four or none, and only with the
   statement group on (`bad-reading-strings` names the first missing one; with the group off they are extra-strings like any key the page does not read); present, each is
   non-empty. `readings_byline` is the template of the byline ({by}, {second_read_by}, {date}, filled as TEXT). The four headings of a reading are lines of its own text, so
   the page reads no heading key. */
export const READING_STRINGS = Object.freeze(["decl_reading_show", "decl_reading_hide", "decl_reading_about", "readings_byline"]);
export const readingWordsOn = (strings) => READING_STRINGS.some((k) => has(strings, k));
/* THE READING CUE's words (Ariadne's reading-cues note v1): the tag on a box that has a reading and the count line on the boxes above it. All four or none; only with the
   reading words on (`bad-cue-strings` names the first missing or empty one, or says the reading words are missing); `count_reading_many` holds `{n}` (filled as TEXT).
   A map with the reading words and no cue words draws no cue. */
export const CUE_STRINGS = Object.freeze(["face_reading_cue", "count_reading_one", "count_reading_many", "key_reading_cue_text"]);
export const cueWordsOn = (strings) => CUE_STRINGS.some((k) => has(strings, k));
export const statementsOn = (strings) => STATEMENT_STRINGS.some((k) => has(strings, k));
/* One more word of the Graph view that a map MAY hold (Lei, 11-26: the way back from a card to the box it was opened from): present, the sheet shows the control; absent, it does not. Present it is not empty. */
export const GRAPH_VIEW_OPTIONAL = Object.freeze(["spine_back_to_graph"]);
export const OPTIONAL_STRINGS = Object.freeze(["key_kinds_note", "key_scope_text", "note_label", "note_source", ...TYPESET_STRINGS]);
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
  for (const name of Object.keys(symbols.openWords)) out.push(symbols.openWords[name].open, symbols.openWords[name].close);
  for (const name of Object.keys(symbols.childCountWords)) out.push(symbols.childCountWords[name].one, symbols.childCountWords[name].many);
  return out;
}

/* symbols = {order: {kinds, proofs, states}, kinds|proofs|states: {name: {class, text, words}}}: exact key sets. A name the
   page has no table entry for is a refusal. The result keeps TWO things apart, one meaning each: `names[t]` is the TABLE's names
   (what a card's kind, state and proof are checked against, and whose `words` are all required) and `order[t]` is the builder's
   key list (what the key draws, in that order). An `order` list is a subset of the table's names with no duplicates; the builder
   lists exactly the rows that occur on the map, so states and proofs may be empty and kinds may not. `class` and `text` are
   strings and otherwise ignored; `words` is a string (that it is a key of `strings` is checked with the strings). A kinds row may
   also carry `card_words`, a non-empty string (the sheet's one line for that kind); `cardWords` maps the kind to it. It may carry `count_words` too,
   {one, many}, each a non-empty string (the foot's words for a card whose children are of this kind); `countWords` maps the kind to it. It may carry `open_words`,
   {open, close}, each a non-empty string naming a strings key (the sheet's parts button for a card of THIS kind); `openWords` maps the kind to it. And
   `child_count_words`, {one, many} like count_words (the foot of a card of THIS kind whose children name no child_kind with count_words); `childCountWords`. */
function symbolsOf(v) {
  exactKeys(v, ["order", "kinds", "proofs", "states"], [], "symbols");
  exactKeys(v.order, ["kinds", "proofs", "states"], [], "symbols.order");
  const out = { words: {}, names: {}, order: {}, cardWords: {}, countWords: {}, openWords: {}, childCountWords: {} };
  for (const [t, table, code] of TABLES) {
    const rows = v[t];
    if (!isObj(rows) || Object.keys(rows).length === 0) throw new DataError("bad-type", "symbols." + t + " is not a non-empty object");
    const names = Object.keys(rows);
    out.words[t] = {};
    for (const n of names) {
      if (!has(table, n)) throw new DataError(code, "symbols." + t + " names a value this page cannot draw");
      exactKeys(rows[n], ["class", "text", "words"], t === "kinds" ? ["card_words", "count_words", "open_words", "child_count_words"] : [], "symbols." + t + " row");
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
      if (has(rows[n], "open_words")) {
        const ow = rows[n].open_words;
        if (!isObj(ow) || Object.keys(ow).length !== 2 || !has(ow, "open") || !has(ow, "close") || !isStr(ow.open) || ow.open === "" || !isStr(ow.close) || ow.close === "")
          throw new DataError("bad-open-words", "symbols.kinds row has an open_words that is not exactly {open, close} of non-empty strings");
        out.openWords[n] = { open: ow.open, close: ow.close };
      }
      if (has(rows[n], "child_count_words")) {
        const cw = rows[n].child_count_words;
        if (!isObj(cw) || Object.keys(cw).length !== 2 || !has(cw, "one") || !has(cw, "many") || !isStr(cw.one) || cw.one === "" || !isStr(cw.many) || cw.many === "")
          throw new DataError("bad-count-words", "symbols.kinds row has a child_count_words that is not exactly {one, many} of non-empty strings");
        out.childCountWords[n] = { one: cw.one, many: cw.many };
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

/* The page's check of the options it is about to hand createGraph (data contract section 24: the floor's bound is the PAGE's check, made by the
   ENGINE's rule). `check` is the engine's own `checkOptions` (pure; the options normalized, or a TypeError), `floor` is index.openScaleFloor
   (undefined on the live map). Throws what `check` throws, except in one case: `floor` is given, `check` refuses the options, and `check`
   accepts the very same options WITHOUT zoom.frameMin; the floor is then the cause, and it is a DataError bad-scale-floor naming the value.
   No engine message is read. Anything else (the floor is fine, or another option is bad too) is the engine's own TypeError, as before. */
export function checkedOptions(check, options, floor) {
  try {
    return check(options);
  } catch (e) {
    if (floor === undefined) throw e;
    const { frameMin, ...zoom } = options.zoom || {};
    try { check({ ...options, zoom }); } catch (other) { throw e; }
    throw new DataError("bad-scale-floor", "index open_scale_floor is outside the range the engine accepts for an opened node's framing: " + shown(floor));
  }
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
  for (const k of Object.values(symbols.openWords).flatMap((c) => [c.open, c.close]))
    if (!has(raw.strings, k)) throw new DataError("missing-open-words", "index strings lacks the open word " + k);
  for (const k of Object.values(symbols.childCountWords).flatMap((c) => [c.one, c.many]))
    if (!has(raw.strings, k)) throw new DataError("missing-count-words", "index strings lacks the child count word " + k);
  /* The statement level's words are all-or-none (the first missing or empty one is named); with the group on the doc-string's label is required too. */
  const stmtOn = statementsOn(raw.strings);
  if (stmtOn) {
    for (const k of STATEMENT_STRINGS) if (!has(raw.strings, k) || raw.strings[k] === "") throw new DataError("bad-statement-strings", "index strings holds part of the statement words, lacks " + k);
    if (!has(raw.strings, "spine_content_label") || raw.strings.spine_content_label === "") throw new DataError("missing-string", "index strings lacks spine_content_label, the doc-string's label");
  }
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
  if (stmtOn) {
    refuseEmptyOptional(raw.strings, [READING_NONE, ...DECL_KIND_STRINGS, ...USES_LIBRARY_STRINGS]);
    for (const k of USES_LIBRARY_STRINGS) if (!has(raw.strings, k) && USES_LIBRARY_STRINGS.some((o) => has(raw.strings, o))) throw new DataError("bad-statement-strings", "index strings holds only one of decl_uses_library_one and decl_uses_library_many, lacks " + k);
    for (const k of READING_STRINGS) if (readingWordsOn(raw.strings) && (!has(raw.strings, k) || raw.strings[k] === "")) throw new DataError("bad-reading-strings", "index strings holds part of the reading words, lacks " + k);
    if (cueWordsOn(raw.strings)) {
      if (!readingWordsOn(raw.strings)) throw new DataError("bad-cue-strings", "index strings holds cue words but no reading words");
      for (const k of CUE_STRINGS) if (!has(raw.strings, k) || raw.strings[k] === "") throw new DataError("bad-cue-strings", "index strings holds part of the cue words, lacks " + k);
      if (!raw.strings.count_reading_many.includes("{n}")) throw new DataError("bad-cue-strings", "count_reading_many holds no {n}");
    }
  }
  /* The page treats a map as carrying notes only when strings hold BOTH note words; one alone would open note-carrying cards silently without their note. */
  if (has(raw.strings, "note_label") !== has(raw.strings, "note_source"))
    throw new DataError("bad-note-strings", "index strings holds only one of note_label and note_source: both or neither");
  /* THE GRAPH VIEW exists iff the strings hold BOTH view_cards and view_graph (a build with the Graph overlay); one alone is refused by name. Then every
     word of the view is required and not empty, and ONE key more is taken: the spine's sentence (graphView.spineWords), checked against spine.json later. */
  const viewPair = ["view_cards", "view_graph"];
  for (const k of viewPair) if (!has(raw.strings, k) && viewPair.some((o) => has(raw.strings, o))) throw new DataError("bad-view-words", "index strings holds only one of view_cards and view_graph, lacks " + k);
  const viewOn = has(raw.strings, "view_cards");
  if (viewOn) {
    for (const k of GRAPH_VIEW_STRINGS) {
      if (!has(raw.strings, k)) throw new DataError("missing-string", "index strings lacks the Graph view word " + k);
      if (raw.strings[k] === "") throw new DataError(viewPair.includes(k) ? "bad-view-words" : "empty-string", "index strings holds an empty Graph view word " + k);
    }
  }
  for (const k of GRAPH_VIEW_OPTIONAL) {
    if (has(raw.strings, k) && !viewOn) throw new DataError("bad-view-words", "index strings holds " + k + " without the Graph view words");
    if (has(raw.strings, k) && raw.strings[k] === "") throw new DataError("empty-string", "index strings holds an empty Graph view word " + k);
  }
  const known = (k) => need.includes(k) || edgeStrings.includes(k) || OPTIONAL_STRINGS.includes(k) || (viewOn && (GRAPH_VIEW_STRINGS.includes(k) || GRAPH_VIEW_OPTIONAL.includes(k))) || (stmtOn && (STATEMENT_STRINGS.includes(k) || k === "spine_content_label" || k === READING_NONE || DECL_KIND_STRINGS.includes(k) || USES_LIBRARY_STRINGS.includes(k) || READING_STRINGS.includes(k) || CUE_STRINGS.includes(k)));
  const leftover = Object.keys(raw.strings).filter((k) => !known(k));
  if (viewOn && leftover.length === 0) throw new DataError("bad-view-words", "index strings carries no spine sentence key beside the Graph view words");
  for (const k of viewOn ? leftover.slice(1) : leftover) throw new DataError("extra-string", "index strings holds a key the page does not read: " + k);
  if (viewOn && raw.strings[leftover[0]] === "") throw new DataError("empty-string", "index strings holds an empty spine sentence key " + leftover[0]);
  const out = { commit: raw.commit, maxChildren: raw.max_children, top, rests, steps: raw.steps, symbols, strings: { ...raw.strings }, assets: { ...raw.assets } };
  if (edgeBasis) out.edgeBasis = edgeBasis;
  if (viewOn) out.graphView = { spineWords: leftover[0] };
  /* The two optional per-map keys (data contract sections 15 and 24), each absent on the live map and then absent from the record too.
     `sibling_layout`: the only value is "column". `open_scale_floor`: a finite number above 0 here; its range (zoom.min up to the open-framing
     cap) is the ENGINE's rule, asked of the engine itself at start by checkedOptions below, never copied into the page. */
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
  exactKeys(c, ["id", "title", "kind", "state", "proof", "child_count", "path"].concat(isChild ? ["parent_rests_on"] : []), ["role", "child_kind", "reading_count"], where);
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
  /* THE READING COUNT (optional): the number of statements WITH a reading on or under this card, an integer of 1 or more, ABSENT when there is none (never 0). The sums are checked
     in validateStep and across steps in createData, so a builder slip cannot show a false cue. */
  if (has(c, "reading_count")) {
    if (!isInt(c.reading_count) || c.reading_count < 1) throw new DataError("bad-reading-count", where + " has a reading_count that is not an integer of 1 or more");
    out.reading_count = c.reading_count;
  }
  return out;
}

/* A step's optional `note`: {text, source} and, optionally, `review`. text is a string of 1 to 65536 characters (the repository's words, shown as
   text only); source is a repository-root-relative path of 1 to 300 characters from [A-Za-z0-9._/-], with no leading '/' and no '..' segment (it is
   shown as text, never as a link). `review` is reserved: the only value accepted now is exactly {state: "converter"} (that key set, that value);
   anything else is `bad-review` naming the step. The page draws nothing from it. The later field `converter_version` is not accepted yet.
   The page does not look at the step's kind. */
const NOTE_SOURCE = /^[A-Za-z0-9._/-]{1,300}$/;
function noteOf(v, ctx, stepId) {
  const bad = (why) => new DataError("bad-note", "step.note " + why);
  if (!isObj(v) || !has(v, "text") || !has(v, "source") || Object.keys(v).some((k) => k !== "text" && k !== "source" && k !== "review"))
    throw bad("is not {text, source} with at most a review");
  if (!isStr(v.text) || v.text.length < 1 || v.text.length > 65536) throw bad("has a text that is not a string of 1 to 65536 characters");
  if (!isStr(v.source) || !NOTE_SOURCE.test(v.source) || v.source.charAt(0) === "/" || v.source.split("/").includes("..")) throw bad("has a source that is not a repository-relative path");
  if (has(v, "review") && (!isObj(v.review) || Object.keys(v.review).length !== 1 || v.review.state !== "converter"))
    throw new DataError("bad-review", "step " + stepId + " has a note.review that is not exactly {state: converter}");
  const s = ctx.strings || {};
  if (!has(s, "note_label") || !has(s, "note_source")) throw new DataError("bad-note-strings", "a step carries a note but the index strings lack note_label or note_source");
  const out = { text: v.text, source: v.source };
  if (has(v, "review")) out.review = { state: "converter" };
  return out;
}

/* THE STATEMENT STEP. A step may carry these eight keys (uses_library_count, an integer of 0 or more, is carried and never drawn) ALL TOGETHER OR NONE (`bad-statement`, naming the step and the first missing key), and then `heading`
   (a non-empty string of at most 4000 characters, only on a statement step). A step carrying any of them while the strings' statement group is off is
   `bad-statement-strings`. A statement step is a leaf (child_count 0, no children). Carried as step.decl. */
const STMT_KEYS = ["name", "source_path", "statement", "variables", "uses_here", "uses_elsewhere", "prompt", "uses_library_count"];
const STMT_KEYWORDS = ["theorem", "lemma", "def", "abbrev", "structure", "class", "inductive", "instance"];
const SOURCE_PATH = /^([A-Za-z0-9_.-]+\/)+[A-Za-z0-9_.-]+\.lean$/;   /* the builder's rule: a `.` may sit inside a segment; a segment that IS `.` or `..` is refused below */
const NAME_MAX = 300;
function declOf(raw, ctx, id) {
  const bad = (why) => new DataError("bad-statement", "step " + id + " " + why);
  const missing = STMT_KEYS.find((k) => !has(raw, k));
  if (missing) throw bad("lacks the statement key " + missing);
  if (!isStr(raw.name) || raw.name === "" || raw.name.length > NAME_MAX) throw bad("has a name that is not a non-empty string of at most " + NAME_MAX + " characters");
  if (!isStr(raw.source_path) || !SOURCE_PATH.test(raw.source_path) || raw.source_path.split("/").some((g) => g === "." || g === "..")) throw bad("has a source_path that is not a relative .lean path");
  const st = raw.statement;
  if (!isObj(st) || Object.keys(st).length !== 2 || !has(st, "keyword") || !has(st, "text")) throw bad("has a statement that is not exactly {keyword, text}");
  if (!isStr(st.keyword) || !STMT_KEYWORDS.includes(st.keyword)) throw bad("has a statement keyword that is not one of the eight");
  if (!isStr(st.text) || st.text.length < 1 || st.text.length > 65536) throw bad("has a statement text that is not a string of 1 to 65536 characters");
  if (typeof raw.variables !== "boolean") throw bad("has a variables that is not a boolean");
  if (!Array.isArray(raw.uses_here) || raw.uses_here.some((x) => !isId(x)) || new Set(raw.uses_here).size !== raw.uses_here.length || raw.uses_here.includes(id))
    throw bad("has a uses_here that is not a list of other step ids without repeats");
  if (!Array.isArray(raw.uses_elsewhere)) throw bad("has a uses_elsewhere that is not a list");
  const elsewhere = raw.uses_elsewhere.map((u) => {
    if (!isObj(u) || !has(u, "name") || Object.keys(u).some((k) => k !== "name" && k !== "step") || !isStr(u.name) || u.name === "" || u.name.length > NAME_MAX || (has(u, "step") && !isId(u.step)))
      throw bad("has a uses_elsewhere item that is not {name} or {name, step}");
    return has(u, "step") ? { name: u.name, step: u.step } : { name: u.name };
  });
  if (!isInt(raw.uses_library_count) || raw.uses_library_count < 0) throw bad("has a uses_library_count that is not an integer of 0 or more");
  if (!isStr(raw.prompt) || raw.prompt.length < 1 || raw.prompt.length > 20000) throw bad("has a prompt that is not a string of 1 to 20000 characters");
  if (has(raw, "heading") && (!isStr(raw.heading) || raw.heading === "" || raw.heading.length > 4000)) throw bad("has a heading that is not a non-empty string of at most 4000 characters");
  const out = { name: raw.name, sourcePath: raw.source_path, keyword: st.keyword, text: st.text, variables: raw.variables, usesHere: raw.uses_here.slice(), usesElsewhere: elsewhere, usesLibraryCount: raw.uses_library_count, prompt: raw.prompt };
  if (has(raw, "heading")) out.heading = raw.heading;
  return out;
}

/* THE READING of a statement (optional key `reading` on a statement step): exactly {text, by, second_read_by, date}, all non-empty strings; `text` at most 20000 BYTES (the
   note renderer's subset, headings and all, is the reading's own); `by` and `second_read_by` at most 80 characters, no control character; `date` YYYY-MM-DD. Anything else is
   `bad-reading`, naming the step. The text is data: it reaches the page only through note.js. */
/* A real calendar day (2026-02-30 and 2026-13-45 are not): the date's parts rebuilt through UTC must give the same parts back. */
function realDay(d) {
  const [y, m, day] = d.split("-").map(Number);
  const t = new Date(Date.UTC(y, m - 1, day));
  return t.getUTCFullYear() === y && t.getUTCMonth() === m - 1 && t.getUTCDate() === day;
}
const READING_TEXT_MAX_BYTES = 20000;
const READING_NAME_MAX = 80;
function readingOf(raw, id) {
  const bad = (why) => new DataError("bad-reading", "step " + id + " has a reading " + why);
  if (!isObj(raw) || Object.keys(raw).length !== 4 || !["text", "by", "second_read_by", "date"].every((k) => has(raw, k))) throw bad("that is not exactly {text, by, second_read_by, date}");
  for (const k of ["text", "by", "second_read_by", "date"]) if (!isStr(raw[k]) || raw[k] === "") throw bad("whose " + k + " is not a non-empty string");
  if (new TextEncoder().encode(raw.text).length > READING_TEXT_MAX_BYTES) throw bad("whose text is over " + READING_TEXT_MAX_BYTES + " bytes");
  for (const k of ["by", "second_read_by"]) if ([...raw[k]].length > READING_NAME_MAX || /[\p{Cc}\p{Cf}]/u.test(raw[k])) throw bad("whose " + k + " is over " + READING_NAME_MAX + " characters or holds a control or format character");
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw.date) || !realDay(raw.date)) throw bad("whose date is not a real day, YYYY-MM-DD");
  return { text: raw.text, by: raw.by, secondReadBy: raw.second_read_by, date: raw.date };
}

export function validateStep(raw, ctx) {
  const carriesStatement = isObj(raw) && (STMT_KEYS.some((k) => has(raw, k)) || has(raw, "heading"));
  if (carriesStatement && !statementsOn(ctx.strings || {}))
    throw new DataError("bad-statement-strings", "step " + (isStr(raw.id) ? raw.id.slice(0, 80) : "?") + " carries a statement but the index strings hold no statement words");
  if (carriesStatement && !STMT_KEYS.some((k) => has(raw, k))) throw new DataError("bad-statement", "step " + (isStr(raw.id) ? raw.id.slice(0, 80) : "?") + " has a heading but no statement");
  if (carriesStatement) {      // an unknown key on a statement step is bad-statement (named), where on any other step it is extra-key
    const known = new Set(["format", "commit", "id", "path", "card", "children", "rests_on", "note", "index_rows", "spine_rows", "heading", "reading", ...STMT_KEYS]);
    const extra = Object.keys(raw).find((k) => !known.has(k));
    if (extra !== undefined) throw new DataError("bad-statement", "step " + (isStr(raw.id) ? raw.id.slice(0, 80) : "?") + " has a key a statement step does not: " + extra.slice(0, 40));
  }
  exactKeys(raw, ["format", "commit", "id", "path", "card", "children", "rests_on"], ["note", "index_rows", "spine_rows", ...(carriesStatement ? [...STMT_KEYS, "heading", "reading"] : [])], "step");
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
  if (has(raw, "note")) out.note = { ...noteOf(raw.note, ctx, raw.id), commit: raw.commit };
  /* The counts are CHECKED only on a map that holds the cue words (the map that asks for the cue): a map with readings and no counts, which is the data before the cue, must still load. */
  const cueOn = cueWordsOn(ctx.strings || {});
  if (cueOn && !carriesStatement) {      // a card above statements counts the readings below it: its reading_count is the SUM of its children entries' (absent = 0)
    const below = children.reduce((n, c) => n + (c.reading_count || 0), 0);
    if ((card.reading_count || 0) !== below) throw new DataError("bad-reading-count", "step " + raw.id + " has a reading_count of " + (card.reading_count || 0) + " but its children hold " + below);
  }
  if (carriesStatement) {
    if (card.child_count !== 0 || children.length !== 0) throw new DataError("bad-statement", "step " + raw.id + " is a statement but has children");
    out.decl = declOf(raw, ctx, raw.id);
    if (has(raw, "reading")) {
      if (!readingWordsOn(ctx.strings || {})) throw new DataError("bad-reading-strings", "step " + raw.id + " carries a reading but the index strings hold no reading words");
      out.decl.reading = readingOf(raw.reading, raw.id);
    }
    const own = out.card.reading_count || 0;
    if (cueOn && own !== (out.decl.reading ? 1 : 0)) throw new DataError("bad-reading-count", "step " + raw.id + " has a reading_count of " + own + " but " + (out.decl.reading ? "carries a reading" : "carries none"));
  }
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
/* fetchJson(fetchLike, address, timeoutMs): the JSON of an address. With `timeoutMs` (a sidecar's fetch gives one; the page's own loads give none) a server that accepts the request
   and never answers, or sends a body that never ends, is waited for that long and no longer: the failure is `fetch-failed`, like any request that fails, so the
   notice and the event are the same as for every other refusal. The page stops waiting; the request itself is not aborted (a fetch-like takes only an address). */
export async function fetchJson(fetchLike, address, timeoutMs) {
  let timer = null;
  const clock = timeoutMs === undefined ? null : new Promise((resolve, reject) => {
    timer = setTimeout(() => reject(new DataError("fetch-failed", "the request for " + address + " did not answer in " + timeoutMs + " ms")), timeoutMs);
  });
  const within = (p) => (clock === null ? p : Promise.race([p, clock]));
  try {
    let r;
    try { r = await within(fetchLike(address)); } catch (e) { throw new DataError("fetch-failed", "the request for " + address + " failed"); }
    if (!r || !r.ok) throw new DataError("http-" + (r && r.status), "the request for " + address + " was refused");
    try { return await within(r.json()); } catch (e) { throw (e instanceof DataError ? e : new DataError("not-json", address + " is not JSON")); }
  } finally {
    if (timer !== null) clearTimeout(timer);
  }
}

const CACHE_MAX = 32;

/* createData(fetchLike): fetchLike(address) -> Promise of a Response-like {ok, status, json()}. */
export function createData(fetchLike) {
  let index = null;
  const steps = new Map();      // id -> Promise of a validated step (bounded, oldest out)
  const metaOf = new Map();     // id -> what the breadcrumb needs about a step already seen

  const counts = new Map();     // id -> the reading_count the page was first told of this card (a parent's entry or its own step), 0 when none
  function note(c, cueOn) {
    const m = { id: c.id, title: c.title, kind: c.kind, state: c.state, proof: c.proof, childCount: c.child_count, path: c.path.slice() };
    if (has(c, "role")) m.role = c.role;
    /* One card, one count: the parent's entry for a step and the step's own card must say the same (a builder slip would show a cue on the box and none on the card, or the reverse). */
    const n = c.reading_count || 0;
    if (cueOn && counts.has(c.id) && counts.get(c.id) !== n) throw new DataError("bad-reading-count", "step " + c.id + " is told as holding " + counts.get(c.id) + " readings and as holding " + n);
    counts.set(c.id, n);
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
    const cueOn = cueWordsOn(ctx.strings);
    note(v.card, cueOn);
    v.children.forEach((c) => note(c, cueOn));
    return v;
  }

  /* A link flagged in_reduction false is a use the reduction already implies by a longer chain: it is not handed to the engine as a premise link
     (Kepler's ruling). True, and a link with no flags (the live map), are handed over as before. */
  const drawnLinks = (rests) => rests.filter((l) => l.in_reduction !== false);   // the ONE rule for which links reach the engine
  function linksFrom(rests, from) {
    return drawnLinks(rests).filter((l) => l.from === from).map((l) => ({ to: l.to, toPath: l.to_path.concat(l.to) }));
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
  if (has(c, "reading_count")) d.readingCount = c.reading_count;
  if (has(c, "child_kind")) d.childKind = c.child_kind;
  return d;
}
