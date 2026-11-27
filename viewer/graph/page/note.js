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
   <code> but <span class="m"> (class "m m1" for one letter) holding the span's characters in ONE text node. A name, a name with arguments and a
   name inside a formula stay <code>; an unsure class is code. A formula span with ^ or _ is set with <sup> and <sub> when it parses under the
   grammar of scriptParts below, and is <code>, as typed, when it does not. Apart from the script characters, the spaces round a ^ and the brackets
   of a {...} or ^(...) operand, every character comes through, in the same order.
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

/* ---- scripts. A formula span with ^ or _ is set with <sup> and <sub> when it parses under the grammar below, and is code, as typed, when it does
   not: never half set. scriptParts(span) -> the parts (a string is text; {tag: "sup"|"sub", children: parts}) or null (refused).

   G1  a script is ^ or _ with a BASE before it in the same group: for _ the character right before, for ^ the nearest non-space character before
       (the spaces between are dropped); a base is a letter, a digit (also a subscript digit), a prime, a closing ) ] }, or a letter followed by
       combining marks (the marks belong to the letter and the script is drawn after both). No base: refuse. A mark run that does not start at a
       letter (the group's start, a digit, a bracket, a space) is no base.
   G2  only the OPERAND to the right is parsed: (a) {...} directly after the script character (braces dropped); (b) (...) after ^, optionally after
       spaces (parens dropped); (c) a WORD of letters, digits and primes (after ^ optional spaces, dropped; after _ none); (d) ONE of * × + - ∨ ∞ ⊥
       directly after the script character, then the group's end, a space or a closing bracket.
   G3  a group's content is parsed by the same grammar, at most two script levels deep.
   G4  refuse on: an unmatched or crossing bracket in an operand group; an empty group; a second ^ (or second _) attached to the same run of scripts
       (a ^ b ^ c); any script left over; an operand that is none of (a)-(d); a combining mark directly after an operand (it would attach to the
       wrong glyph); a ^ whose base WORD follows another word, or a closing bracket, and a space (`g k ^ d` means (g k)^d in Lean, where an
       application binds tighter than ^, and setting d over k alone would read g(k^d); look-alikes that read correctly cannot be told apart by
       syntax, so the whole shape is code). The base word is the run of word characters and their marks that ends at the base; a base that carries
       a subscript (`g k_1 ^ d`, `g k_{ij}^d`: a _ operand directly before the ^, on the same base) is that base's word, so the test is made on the
       word before the _; a closing-bracket base, a ^ at a group's start and a ^ after an operator and a space are not covered. A combining mark
       directly after the opening { or ( of an operand group is refused too (the same reason). One _ and one ^ on one base is allowed, in either order.
       The exponent side too: a ^ with spaces before a WORD operand that is followed by spaces and a word or an opening bracket, or directly by a _, is refused
       (`a ^ b c` is a^(b c); `a ^ b_c` has the one name b_c as its exponent). An unspaced ^, an operator, comma or closing bracket after it, or the end: not covered.
       A ^ whose operand is followed directly by a superscript glyph (¹ ² ³ ⁰ ⁱ ⁴-⁹ ⁺ ⁻ ⁼ ⁽ ⁾ ⁿ: U+00B9, U+00B2, U+00B3, U+2070, U+2071, U+2074-U+207F) is refused: the glyph is a raised character of its own that the operand cannot absorb (`x ^ 10⁶` is x ^ (10 ^ 6) in Lean; set, it would read x^10 and then a raised 6). Modifier letters, a space before the glyph, and a _ operand followed by a glyph are not covered.
   G5  spaces after an operand stay as typed.
   Nothing but the script characters, the spaces round a ^, and the brackets of a {...} or ^(...) operand is ever dropped; every other character
   comes through in its place. */
const BASE_CHAR = /^[\p{L}\p{Nd}₀-₉′'’)\]}]$/u;
const WORD_CHAR = /^[\p{L}\p{Nd}₀-₉′'’]$/u;
const MARK = /^\p{M}$/u;
const SUP_GLYPH = /^[\u00B9\u00B2\u00B3\u2070\u2071\u2074-\u207F]$/u;   // G4: U+00B9, U+00B2, U+00B3, U+2070, U+2071, U+2074-U+207F
const LETTER = /^\p{L}$/u;
const SYMBOLS = new Set(["*", "×", "+", "-", "∨", "∞", "⊥"]);
const OPENERS = new Map([["(", ")"], ["[", "]"], ["{", "}"]]);
const CLOSERS = new Set([")", "]", "}"]);
const MAX_SCRIPT_LEVELS = 2;

/* G4, the exponent side: does the word at cs[j..end) end directly at a _, or at spaces and then a word or an opening bracket? By index, nothing copied. */
function juxtaposed(cs, j, end) {
  const at = (k) => (k < end ? cs[k] : "");
  let k = j, m;
  while (WORD_CHAR.test(at(k))) k++;
  for (m = k; at(m) === " "; m++);
  return k > j && (at(k) === "_" || (m > k && (WORD_CHAR.test(at(m)) || OPENERS.has(at(m)))));
}

/* The index of the bracket that closes the one opening at cs[i], looking only below `end`; -1 when it is unmatched or the brackets cross. */
function closeAt(cs, i, end) {
  const stack = [];
  for (let k = i; k < end; k++) {
    if (OPENERS.has(cs[k])) stack.push(OPENERS.get(cs[k]));
    else if (CLOSERS.has(cs[k])) {
      if (stack.pop() !== cs[k]) return -1;
      if (stack.length === 0) return k;
    }
  }
  return -1;
}

/* G1, the base of the script character c at cs[i] in the group cs[start..): the index of the base's LAST character (a letter's last mark), or -1. */
function baseAt(cs, start, i, c) {
  let p = i - 1;
  if (c === "^") while (p >= start && cs[p] === " ") p--;
  if (p < start) return -1;
  if (BASE_CHAR.test(cs[p])) return p;
  if (!MARK.test(cs[p])) return -1;
  let q = p;
  while (q >= start && MARK.test(cs[q])) q--;                                       // the mark run must start at a letter
  return q >= start && LETTER.test(cs[q]) ? p : -1;
}

/* G4, the juxtaposed power: does the base word that ends at cs[last] follow another word, or a closing bracket, and a space? A closing-bracket base has no base word. */
function followsWord(cs, start, last) {
  const isWord = (ch) => WORD_CHAR.test(ch) || MARK.test(ch);
  let s = last;
  while (s >= start && isWord(cs[s])) s--;
  if (s === last || s < start || cs[s] !== " ") return false;
  while (s >= start && cs[s] === " ") s--;
  return s >= start && (isWord(cs[s]) || CLOSERS.has(cs[s]));
}

/* G2, the operand of the script character c at cs[i], which starts at cs[j] (j is past the spaces after a ^): {children, next} or null.
   G4: a combining mark directly after the operand refuses it. */
function parseOperand(cs, i, j, end, c, level) {
  if (j >= end) return null;
  const done = (children, next) => (next < end && (MARK.test(cs[next]) || (c === "^" && SUP_GLYPH.test(cs[next]))) ? null : { children, next });
  if ((cs[j] === "{" && j === i + 1) || (cs[j] === "(" && c === "^")) {          // (a) and (b): a group, its brackets dropped
    const k = closeAt(cs, j, end);
    if (k < 0 || k === j + 1) return null;
    if (MARK.test(cs[j + 1])) return null;                                          // a mark right after the opening bracket would attach to the wrong glyph
    const children = parseGroup(cs, j + 1, k, level + 1);
    if (children === null || children.every((t) => typeof t === "string" && t.trim() === "")) return null;
    return done(children, k + 1);
  }
  if (WORD_CHAR.test(cs[j])) {                                                       // (c): a word
    let k = j;
    while (k < end && WORD_CHAR.test(cs[k])) k++;
    return done([cs.slice(j, k).join("")], k);
  }
  if (j === i + 1 && SYMBOLS.has(cs[j]) && (j + 1 >= end || cs[j + 1] === " " || CLOSERS.has(cs[j + 1]))) {   // (d): one symbol
    return done([cs[j]], j + 1);
  }
  return null;
}

/* One group cs[start..end) -> parts, or null. `level` counts the script groups this one sits inside. */
function parseGroup(cs, start, end, level) {
  const out = [];
  let buf = "", runEnd = -1, runStart = -1, run = new Set(), i = start;
  while (i < end) {
    const c = cs[i];
    if (c !== "^" && c !== "_") { buf += c; i++; continue; }
    if (level >= MAX_SCRIPT_LEVELS) return null;
    const base = baseAt(cs, start, i, c);                               // G1: the base
    if (base < 0) return null;
    const attached = c === "_" ? i === runEnd : runEnd >= 0 && cs.slice(runEnd, i).every((t) => t === " ");   // G4: the same run of scripts
    if (c === "^" && followsWord(cs, start, attached ? runStart - 1 : base)) return null;   // G4: a juxtaposed power; a subscripted base is the word before its _
    let j = i + 1;                                                      // G2: the operand
    if (c === "^") while (j < end && cs[j] === " ") j++;
    if (c === "^" && j > i + 1 && juxtaposed(cs, j, end)) return null;   // G4: a juxtaposed exponent
    const operand = parseOperand(cs, i, j, end, c, level);
    if (operand === null) return null;
    const { children, next } = operand;
    if (attached) {
      if (run.has(c)) return null;
      run.add(c);
    } else { run = new Set([c]); runStart = i; }
    if (c === "^") buf = buf.replace(/ +$/, "");                        // the spaces directly before a set ^ are dropped
    if (buf !== "") out.push(buf);
    buf = "";
    out.push({ tag: c === "^" ? "sup" : "sub", children });
    runEnd = next;
    i = next;
  }
  if (buf !== "") out.push(buf);
  return out;
}

/* span text -> parts, or null when the grammar refuses it. A span with no script is its own text. */
export function scriptParts(span) {
  const cs = Array.from(String(span));
  if (!cs.some((c) => c === "^" || c === "_")) return [String(span)];
  return parseGroup(cs, 0, cs.length, 0);
}
const setChildren = (parts, el) => parts.map((p) => (typeof p === "string" ? p : el(p.tag, {}, setChildren(p.children, el))));

/* One backtick span in the maths view: span.m (class "m m1" for one letter) when it is set, else code with its characters as typed. */
function typesetSpan(sp, el) {
  if (!mathsFace(sp)) return el("code", {}, [sp]);
  if (oneLetter(sp)) return el("span", { class: "m m1" }, [sp]);
  if (!/[\^_]/.test(sp)) return el("span", { class: "m" }, [sp]);
  const parts = scriptParts(sp);
  return parts === null ? el("code", {}, [sp]) : el("span", { class: "m" }, setChildren(parts, el));
}

/* The inline children with the maths face: a plain string for text, el("span") for a maths span, el("code") for the rest. */
function typesetChildren(text, el) {
  return titleSegments(text).map((seg) => (seg.kind !== "code" ? seg.text : typesetSpan(seg.text, el)));
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

/* The sheet's source line: the template split on {source} and {commit}, each replaced by its value AS TEXT (never put into a markup string).
   Returns the children for el(): plain strings. */
export function templateParts(template, values) {
  return String(template).split(/(\{source\}|\{commit\})/)
    .map((p) => (p === "{source}" ? values.source : p === "{commit}" ? values.commit : p))
    .filter((p) => p !== "");
}
