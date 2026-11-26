/* The repository's note on a sheet: fetched source text -> DOM elements. THE SAFETY CLAIM, in one place:
     - every element is made by the page's one element creator (`el`, dom.js), which refuses any tag or attribute outside its tables;
     - every character of the note reaches the DOM as a TEXT NODE (el() appends strings as text nodes and nothing else);
     - the only attribute this file ever passes is `class` (a fixed token) and `start` on <ol> (digits only, from a parsed integer).
   Nothing here parses markup, builds a markup string, makes a link, or interprets a character beyond the rules below. It takes the text and
   `el` and touches nothing else: no global, no fetch, no timer, no randomness.

   THE RULES (line based; "\r\n" is read as "\n"; blank lines separate blocks):
     heading   '#'..'######' at column 0 then a space: h3 for '#', h4 for '##', h5 for deeper (the sheet's own title sits above), class note-h
     list      '*' or '-' (ul) or digits then '.' or ')' (ol, `start` from the first item) after any indent; a deeper marker nests (at most MAX_DEPTH
               levels, deeper ones stay text of their item); a line indented under its item, or by 2+ spaces past its marker, continues it
     pre       lines indented 4+ spaces outside a list: ONE <pre>, the common 4-space indent removed, no inline processing
     table     2+ consecutive lines starting with '|': a header row when the second is a separator; rows of unequal width are ONE <pre> of the
               literal lines (never a guessed table)
     paragraph any other run of non-blank lines, joined with a space; a heading, list marker or table line ends it
     inline    backtick pairs are <code> (dom.js titleChildren, the helper the titles use); EVERYTHING else is literal text: no emphasis ('*' and '_'
               are characters), no escapes, no links, no entities.

   THE MATHS FACE (renderNote's third argument, off by default): a backtick span that is ONE LETTER, or FORMULA-ONLY by the classes below, is not
   <code> but <span class="m"> (class "m m1" for one letter) whose only child is ONE text node holding the span's characters exactly. A name, a name
   with arguments and a name inside a formula stay <code>; an unsure class is code. It changes appearance only: every character, in the same order.
   The classes are a port of the measurement's cls3 (one definition, here); fixtures/note-spans-classes.json holds its answer for every real span. */
import { titleChildren, titleSegments } from "./dom.js";

/* ---- the span classes. Python's \w is Unicode letters, digits and underscore; JS's \w is ASCII only and MUST NOT be used here. ---- */
const IDENT = /^[\p{L}\p{N}_.'\u2032\u2019]+$/u;
const IDENT_TOKEN = /[\p{L}\p{N}_.'\u2032\u2019]+/gu;

/* span text -> 'name' | 'formula' | 'name-with-arguments' | 'name-in-formula'. */
export function spanClass(sp) {
  if (IDENT.test(sp)) return "name";
  const hasName = (sp.match(IDENT_TOKEN) || []).some((w) => w.replace(/[^A-Za-z]/g, "").length >= 2);
  if (!hasName) return "formula";
  const onlySpace = sp.includes(" ") && sp.split(" ").filter((t) => t !== "").every((t) => IDENT.test(t));
  return onlySpace ? "name-with-arguments" : "name-in-formula";
}
/* The span is exactly one code point and it is a letter. */
export function oneLetter(sp) { return [...sp].length === 1 && /^\p{L}$/u.test(sp); }

const mathsFace = (sp) => oneLetter(sp) || spanClass(sp) === "formula";

/* The inline children with the maths face: a plain string for text, el("span") for a maths span, el("code") for the rest. */
function typesetChildren(text, el) {
  return titleSegments(text).map((seg) => {
    if (seg.kind !== "code") return seg.text;
    return mathsFace(seg.text) ? el("span", { class: oneLetter(seg.text) ? "m m1" : "m" }, [seg.text]) : el("code", {}, [seg.text]);
  });
}

/* The exact text: the note's text verbatim in ONE <pre> (one text node, every character, backticks included). */
export function exactNote(text, el) { return el("pre", {}, [String(text)]); }

const HEADING = /^(#{1,6})\s+([\s\S]*)$/;
const BULLET = /^(\s*)([*-])\s+([\s\S]*)$/;
const NUMBERED = /^(\s*)(\d{1,9})[.)]\s+([\s\S]*)$/;
const PIPE_LINE = /^\s*\|/;
const SEPARATOR_CELL = /^[-: ]+$/;
const HEADING_TAG = ["h3", "h4", "h5"];
const MAX_DEPTH = 6;

const blank = (line) => line.trim() === "";
const indented4 = (line) => line.startsWith("    ");
const indentOf = (line) => line.length - line.replace(/^ +/, "").length;

/* A list marker line -> {indent, ordered, num, text, textCol}, or null. */
function marker(line) {
  const b = BULLET.exec(line);
  if (b) return { indent: b[1].length, ordered: false, num: "", text: b[3], textCol: line.length - b[3].length };
  const n = NUMBERED.exec(line);
  if (n) return { indent: n[1].length, ordered: true, num: n[2], text: n[3], textCol: line.length - n[3].length };
  return null;
}

/* The list whose first marker is on lines[i]; returns {node, next}. An item is its first line, its continuation lines, then its nested lists. */
function parseList(lines, i, depth, el, inl) {
  const first = marker(lines[i]);
  const items = [];
  while (i < lines.length) {
    const m = marker(lines[i]);
    if (!m || m.indent !== first.indent || m.ordered !== first.ordered) break;
    const text = [m.text.trim()], nested = [];
    i++;
    while (i < lines.length) {
      const line = lines[i];
      if (blank(line)) {   // a blank line ends the item; the list goes on only when the next line is a marker at this item's indent or deeper
        let j = i;
        while (j < lines.length && blank(lines[j])) j++;
        const next = j < lines.length ? marker(lines[j]) : null;
        if (next && next.indent >= m.indent) { i = j; continue; }
        break;
      }
      const mk = marker(line);
      if (mk) {
        if (mk.indent <= m.indent) break;                                    // a sibling, or shallower: this item is done
        if (depth >= MAX_DEPTH) { text.push(line.trim()); i++; continue; }   // too deep: plain text of the item
        const r = parseList(lines, i, depth + 1, el, inl);
        nested.push(r.node);
        i = r.next;
        continue;
      }
      if (indentOf(line) >= m.indent + 2 || indentOf(line) >= m.textCol) { text.push(line.trim()); i++; continue; }
      break;
    }
    items.push(el("li", {}, inl(text.filter((t) => t !== "").join(" ")).concat(nested)));
  }
  const attrs = first.ordered ? { start: String(parseInt(first.num, 10)) } : {};
  return { node: el(first.ordered ? "ol" : "ul", attrs, items), next: i };
}

/* '|'-separated cells of one table line; a '|' inside a backtick span does not split. The empty cell the edge pipes leave is dropped. */
function splitCells(line) {
  const cells = [""];
  for (const seg of titleSegments(line.trim())) {
    if (seg.kind === "code") { cells[cells.length - 1] += "`" + seg.text + "`"; continue; }
    const parts = seg.text.split("|");
    cells[cells.length - 1] += parts[0];
    for (let k = 1; k < parts.length; k++) cells.push(parts[k]);
  }
  const out = cells.map((c) => c.trim());
  if (out[0] === "") out.shift();
  if (out.length > 0 && out[out.length - 1] === "") out.pop();
  return out;
}

function renderTable(run, el, inl) {
  const rows = run.map(splitCells);
  if (rows[0].length === 0 || rows.some((r) => r.length !== rows[0].length)) return el("pre", {}, [run.join("\n")]);
  const cell = (tag) => (c) => el(tag, {}, inl(c));
  const row = (tag) => (r) => el("tr", {}, r.map(cell(tag)));
  const hasHead = rows.length >= 2 && rows[1].every((c) => SEPARATOR_CELL.test(c));
  const parts = [];
  if (hasHead) parts.push(el("thead", {}, [row("th")(rows[0])]));
  const body = hasHead ? rows.slice(2) : rows;
  if (body.length > 0) parts.push(el("tbody", {}, body.map(row("td"))));
  return el("table", {}, parts);
}

const tableAt = (lines, i) => PIPE_LINE.test(lines[i]) && i + 1 < lines.length && PIPE_LINE.test(lines[i + 1]);
/* A line that ends a paragraph run. */
const startsBlock = (lines, j) => HEADING.test(lines[j]) || tableAt(lines, j) || (!indented4(lines[j]) && marker(lines[j]) !== null);

/* text, el, typeset -> DocumentFragment of the note's blocks. typeset true: the maths face (above); omitted or false: every span is <code>. */
export function renderNote(text, el, typeset = false) {
  const inl = typeset ? (t) => typesetChildren(t, el) : (t) => titleChildren(t, el);
  const lines = String(text).replace(/\r\n/g, "\n").split("\n");
  const blocks = [];
  let i = 0;
  while (i < lines.length) {
    const line = lines[i];
    if (blank(line)) { i++; continue; }
    const h = HEADING.exec(line);
    if (h) {
      blocks.push(el(HEADING_TAG[Math.min(h[1].length, 3) - 1], { class: "note-h" }, inl(h[2].trim())));
      i++;
    } else if (indented4(line)) {
      let last = i, j = i;
      while (j < lines.length && (indented4(lines[j]) || blank(lines[j]))) { if (!blank(lines[j])) last = j; j++; }
      blocks.push(el("pre", {}, [lines.slice(i, last + 1).map((l) => (blank(l) ? "" : l.slice(4))).join("\n")]));
      i = last + 1;
    } else if (marker(line)) {
      const r = parseList(lines, i, 1, el, inl);
      blocks.push(r.node);
      i = r.next;
    } else if (tableAt(lines, i)) {
      let j = i;
      while (j < lines.length && PIPE_LINE.test(lines[j])) j++;
      blocks.push(renderTable(lines.slice(i, j), el, inl));
      i = j;
    } else {
      const run = [line.trim()];
      i++;
      while (i < lines.length && !blank(lines[i]) && !startsBlock(lines, i)) { run.push(lines[i].trim()); i++; }
      blocks.push(el("p", {}, inl(run.join(" "))));
    }
  }
  const frag = (blocks[0] || el("p", {})).ownerDocument.createDocumentFragment();   // the fragment comes from the document the elements are in
  for (const b of blocks) frag.appendChild(b);
  return frag;
}

/* A line of words with placeholders: the template split on the placeholders named by the KEYS of `values` (each written {key} in the template), each
   replaced by its value AS TEXT (never put into a markup string). A placeholder whose name is not a key of `values` stays as literal text.
   Returns the children for el(): plain strings. The sheet's source line is templateParts(template, {source, commit}); the later-blocks line, {n}. */
export function templateParts(template, values) {
  const keys = Object.keys(values);
  if (keys.length === 0) return [String(template)].filter((p) => p !== "");
  const named = keys.map((k) => "\\{" + k.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + "\\}");
  const own = (p) => p.length > 2 && p.charAt(0) === "{" && p.charAt(p.length - 1) === "}" && Object.prototype.hasOwnProperty.call(values, p.slice(1, -1));
  return String(template).split(new RegExp("(" + named.join("|") + ")"))
    .map((p) => (own(p) ? values[p.slice(1, -1)] : p))
    .filter((p) => p !== "");
}
