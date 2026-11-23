#!/usr/bin/env python3
"""The anchor format of the notes, in one module: read, write, check the shape, and place the one-line JSON comments.

A note's Markdown carries its metadata in two kinds of one-line HTML comment, so the rendered page does not change:
  <!-- rh-note {...} -->    the note header (one per note)
  <!-- rh-block {...} -->   a block anchor, on its own line directly after the paragraph, table or lean block it anchors
Both the checker and the helper that writes anchors import this module, so the format lives in one place. It is a
library: `python3 tools/rh_anchor.py --selftest` is the only command line.

API (the names are the contract)
  NEEDS, KINDS                      the closed lists of `not_read` needs and of block kinds
  parse_note(text)                  -> (headers, blocks, malformed); never raises for any str
  format_comment(tag, data)         the canonical one-line comment for "rh-note" or "rh-block"; no line ending
  render_header(d), render_block(d) format_comment with the tag filled in
  strip_anchor_lines(text)          the note without its anchor lines; every other byte unchanged
  block_id_ok(note_id, block_id)    True iff block_id is `<note_id>.b<nn>`, nn two or more ASCII digits
  problems(block, note_id=None)     format-level check of one block dict; a list of strings, empty = fine
  header_problems(d)                the same for a header dict
  target_at(text, line)             the element (paragraph, table, fence) that holds a 1-based line, else None
  next_block_id(note_id, used)      the next unused id of a note, never reusing a hole
  insert_after_line(text, line, c)  insert a comment as its own line after a 1-based line, in that file's line ending
`Item` has line (1-based), data (the parsed object), canonical (the line is byte-equal to format_comment of its own
data), offset and end (character offsets of the line start and of the end after its line ending), and for blocks
`target`, for headers `before_first_h2`. `Problem` has line, code and message.

CONTRACT (each line is a self-test case, written before the code)
 A1 A line whose stripped text starts `<!-- rh-note ` or `<!-- rh-block ` and ends ` -->`, with a JSON object between,
    is recognised. Any other line that starts `<!-- rh-` (other tag, JSON that is not an object or does not parse, no
    ` -->`, a second comment, the comment spread over lines) or that holds `<!-- rh-` after other text is a Problem
    MALFORMED. Never silently ignored. Cases A1a-A1e.
 A2 Inside a fenced block (``` or ~~~, three or more, closed by the same character with at least as many) an rh-
    comment is text: not parsed, not a problem, not stripped. An unclosed fence runs to the end and is a Problem
    UNCLOSED-FENCE on its opening line. Case A2.
 A3 The canonical line is `<!-- {tag} {json} -->`, json with sorted keys, no spaces, non-ASCII kept, and `<` `>` `&`
    written as \\u003c \\u003e \\u0026, so `-->` cannot occur inside it. A recognised line that is not byte-equal to the
    canonical form of its own data is an Item with canonical False (the checker decides). Cases A3a A3b.
 A4 Round trip: parse_note(format_comment(tag, d) + "\\n") is exactly one Item with data == d and canonical True, no
    Problem, for objects of str, int, bool, None, list, dict. Case A4.
 A5 Placement. A block's `target` is the nearest preceding non-blank element: paragraph, table, lean (a fence whose
    info string starts `lean`), other (any other fence, heading, list item, quote, HTML line) or none. Each carries
    first_line, last_line and insert_after (= last_line); a table also ncols, nrows (body rows) and start_line. Anchor
    lines are not elements, so every anchor after a table has that table as its target. Cases A5a-A5d.
 A6 An rh- comment line between two table lines (no blank line between) is a Problem INSIDE-TABLE naming the line;
    the comment is still returned. Case A6.
 A7 Every rh-note is a header; before_first_h2 says whether it comes before the first `## ` line outside a fence. The
    parser does not enforce "exactly one". Case A7.
 A8 strip_anchor_lines is the exact inverse of inserting recognised anchor lines (LF, CRLF, lone CR, no final newline);
    fenced lines and malformed rh- lines are left. A final anchor line that has no line ending takes the line ending
    before it with it. Cases A8a-A8c.
 A9 Never raises: 300 seeded random strings. Case A9.   A10 The same content on two lines is two Items. Case A10.
 A11 `--selftest` exits 0 (all pass), 1 (any fails), 2 (usage), 3 (no case ran). Case A11.
 B1 render_header/render_block equal format_comment with the tag; render(parse(line).data) == line. Case B1.
 B2 problems(): kind in KINDS; id form (and note prefix when note_id is given); machine_fact needs non-empty tool and
    tool_version, check in text/index/proofterm, options a str (may be empty), `complete` True for proofterm, and a
    machine_fact with complete False is refused (it can only be anchored as not_read); not_read needs a needs value
    of NEEDS; argument needs reader, date and a non-empty decls list; decls entries have str module and name;
    defs_opened (if present) is a list of {module, name, lines:[int,int]}; conventions_checked (if present) is a list
    of "a".."e"; row and col (if present) are ints >= 1. Every problem string starts with the field name.
    header_problems(): id, level in {0,1,2}, group, list_title, authors, readers, release. Cases B2a-B2f.
 B3 target_at gives the element holding a line, None between elements; a line inside a table is held by the table, so
    the insertion line is the table's last line, never between rows. Case B3.
 B4 next_block_id is the smallest number above the largest used for that note, at least two digits. Case B4.
 B5 insert_after_line uses CRLF if the line ended CRLF, else LF; on a last line with no line ending it adds one before
    the comment and none after, so strip_anchor_lines(insert_after_line(t, n, c)) == t. Cases B5a-B5d.

LIMIT. The module checks the SHAPE of the format, not its meaning: no outline, no declaration table, no check that a
row, column, declaration or file exists (a table's size is only reported), no date format, no order check on
`lines`, no check that the first words of a block fit its kind, and no rule on which kind carries `defs_opened` or
`conventions_checked` (open; they are validated when present and never required). Markdown is approximated by the
rules in A2, A5 and A6, not CommonMark: a fence may be indented by any spaces or tabs, indented code blocks and HTML
blocks are not recognised as fences, setext headings are not recognised, a table is a run of lines starting with `|`
whose second line is a separator row (a paragraph line above it is not part of it), and a heading, list item, quote
or HTML line is `other`. A line is a line ending in `\\n`, `\\r\\n` or a lone `\\r`. Text in an rh- comment on a line with
other text before it (for example in an inline code span in prose) is reported MALFORMED. Item offsets are character
offsets into the str as given, not bytes. insert_after_line takes the line it is given: choosing the table's last
line for a line inside a table is the caller's job (`target.insert_after`). A final anchor line without a line
ending that was typed by hand after a note that ends in a newline takes that newline with it when stripped.
"""
from __future__ import annotations

import contextlib
import io
import json
import random
import re
import sys
from dataclasses import dataclass

NEEDS = ("callers", "route", "enclosing", "resolve", "fields_read", "uses", "hand_read", "full_build")
KINDS = ("machine_fact", "reading", "interpretation", "correction", "not_read", "argument")


# ---------------------------------------------------------------- the module
_TAGS = ("rh-note", "rh-block")
_RH = "<!-- rh-"
_SPLIT = re.compile(r"(\r\n|\n|\r)")
_FENCE = re.compile(r"[ \t]*(`{3,}|~{3,})(.*)")
_HEADING = re.compile(r"#{1,6}(\s|$)")
_LISTISH = re.compile(r"([-*+]|\d{1,9}[.)])\s")
_RULE = re.compile(r"([-*_])(\s*\1){2,}\s*")
_CELL_SEP = re.compile(r"(?<!\\)\|")
_SEP_CELL = re.compile(r":?-+:?")


@dataclass
class Item:
    line: int
    data: dict
    canonical: bool
    target: dict | None = None
    before_first_h2: bool | None = None
    offset: int = 0
    end: int = 0


@dataclass
class Problem:
    line: int
    code: str
    message: str


def format_comment(tag, data):
    """The canonical one-line comment; `<`, `>` and `&` are written as \\u escapes so `-->` cannot occur inside."""
    if tag not in _TAGS:
        raise ValueError(f"tag must be one of {_TAGS}, not {tag!r}")
    if not isinstance(data, dict):
        raise TypeError("data must be a dict")
    j = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    j = j.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return f"<!-- {tag} {j} -->"


def render_block(data):
    return format_comment("rh-block", data)


def render_header(data):
    return format_comment("rh-note", data)


def _split(text):
    """(contents, endings): one entry per line; the last entry is the text after the final line ending."""
    parts = _SPLIT.split(text)
    return parts[0::2], parts[1::2] + [""]


def _recognise(raw, st):
    """(tag, data, canonical) for a recognised line, else None. `st` is `raw` stripped."""
    for tag in _TAGS:
        pre = "<!-- " + tag + " "
        if st.startswith(pre):
            break
    else:
        return None
    if not st.endswith(" -->") or len(st) < len(pre) + 4:
        return None
    try:
        data = json.loads(st[len(pre):-4])
    except Exception:  # bad JSON, RecursionError on deep nesting, a huge integer: all the same answer
        return None
    if not isinstance(data, dict):
        return None
    try:
        canonical = raw == format_comment(tag, data)
    except Exception:
        canonical = False
    return tag, data, canonical


def _is_sep(s):
    t = s.strip()
    if not t.startswith("|"):
        return False
    inner = t[1:]
    if inner.endswith("|"):
        inner = inner[:-1]
    return all(_SEP_CELL.fullmatch(c.strip()) for c in inner.split("|"))


def _ncols(s):
    t = s.strip()[1:]
    if t.endswith("|") and not t.endswith("\\|"):
        t = t[:-1]
    return len(_CELL_SEP.split(t))


def _classify(s):
    if _HEADING.match(s) or _LISTISH.match(s) or s.startswith((">", "<")) or _RULE.fullmatch(s):
        return "other"
    return "paragraph"


def _element(kind, first, last, **extra):
    d = {"type": kind, "first_line": first + 1, "last_line": last + 1, "insert_after": last + 1}
    d.update(extra)
    return d


class _Analysis:
    """One pass over the lines with a small state (in a fence, a run of table lines); shared by every reader."""

    def __init__(self, text):
        lines, ends = _split(text)
        n = len(lines)
        self.lines, self.ends, self.n = lines, ends, n
        self.nreal = n - 1 if lines[-1] == "" else n
        self.offs = []
        o = 0
        for c, e in zip(lines, ends):
            self.offs.append(o)
            o += len(c) + len(e)
        # fences
        fence_of = [-1] * n
        fences = []
        cur = None
        for i, s in enumerate(lines):
            if cur is not None:
                fence_of[i] = cur
                f = fences[cur]
                t = s.strip()
                if len(t) >= f["n"] and not t.strip(f["ch"]):
                    f["close"] = i
                    cur = None
                continue
            m = _FENCE.match(s)
            if m and m.group(1)[0] == "`" and "`" in m.group(2):
                m = None
            if m:
                fences.append({"open": i, "close": None, "ch": m.group(1)[0], "n": len(m.group(1)), "info": m.group(2).strip()})
                cur = len(fences) - 1
                fence_of[i] = cur
        probs = []
        for f in fences:
            if f["close"] is None:
                probs.append(Problem(f["open"] + 1, "UNCLOSED-FENCE", f"The code fence opened on line {f['open'] + 1} is never closed."))
        # rh- lines
        cand = [False] * n
        rec = {}
        for i, s in enumerate(lines):
            if fence_of[i] != -1:
                continue
            st = s.strip()
            if st.startswith(_RH):
                cand[i] = True
                r = _recognise(s, st)
                if r:
                    rec[i] = r
                else:
                    probs.append(Problem(i + 1, "MALFORMED", f"Line {i + 1} starts an rh- comment that is not one complete "
                                         "`<!-- rh-note {...} -->` or `<!-- rh-block {...} -->` line with a JSON object."))
            elif _RH in s:
                probs.append(Problem(i + 1, "MALFORMED", f"Line {i + 1} has an rh- comment after other text; "
                                     "an anchor comment must be a line of its own."))
        self.fence_of, self.fences, self.cand, self.rec = fence_of, fences, cand, rec

        def is_tl(x):
            return 0 <= x < n and fence_of[x] == -1 and not cand[x] and lines[x].strip().startswith("|")

        i = 0
        while i < n:   # a run of rh- lines between two table lines
            if not cand[i]:
                i += 1
                continue
            j = i
            while j + 1 < n and cand[j + 1]:
                j += 1
            if is_tl(i - 1) and is_tl(j + 1):
                for x in range(i, j + 1):
                    probs.append(Problem(x + 1, "INSIDE-TABLE", f"Line {x + 1} puts an rh- comment between two table rows."))
            i = j + 1
        probs.sort(key=lambda p: (p.line, p.code))
        self.problems = probs
        # elements
        els = []
        el_at = [-1] * n
        for f in fences:
            last = f["close"] if f["close"] is not None else max(self.nreal - 1, f["open"])
            els.append(_element("lean" if f["info"].startswith("lean") else "other", f["open"], last))
            for x in range(f["open"], last + 1):
                el_at[x] = len(els) - 1
        core = [i for i in range(n) if not cand[i]]
        p = 0
        while p < len(core):
            if not is_tl(core[p]):
                p += 1
                continue
            q = p
            while q < len(core) and is_tl(core[q]):
                q += 1
            run = core[p:q]
            if len(run) >= 2 and _is_sep(lines[run[1]]):
                els.append(_element("table", run[0], run[-1], ncols=_ncols(lines[run[0]]), nrows=len(run) - 2, start_line=run[0] + 1))
                for x in run:
                    el_at[x] = len(els) - 1
            p = q
        cur, prev = None, -2
        for i in range(n):
            if cand[i] or el_at[i] != -1:
                cur = None
                continue
            s = lines[i].strip()
            if not s:
                cur = None
                continue
            kind = _classify(s)
            if cur is not None and prev == i - 1 and els[cur]["type"] == kind:
                els[cur]["last_line"] = els[cur]["insert_after"] = i + 1
            else:
                els.append(_element(kind, i, i))
                cur = len(els) - 1
            el_at[i] = cur
            prev = i
        self.elements = els
        last_el = -1
        self.target_of = {}
        for i in range(n):
            if cand[i]:
                self.target_of[i] = last_el
            elif el_at[i] != -1:
                last_el = el_at[i]
        self.h2 = next((i for i in range(n) if fence_of[i] == -1 and lines[i].startswith("## ")), None)


def parse_note(text):
    """(headers, blocks, malformed). Never raises for a str. See the module docstring for the contract."""
    a = _Analysis(text)
    headers, blocks = [], []
    for i in sorted(a.rec):
        tag, data, canon = a.rec[i]
        off = a.offs[i]
        end = off + len(a.lines[i]) + len(a.ends[i])
        if tag == "rh-note":
            headers.append(Item(i + 1, data, canon, None, a.h2 is None or i < a.h2, off, end))
        else:
            t = a.target_of[i]
            blocks.append(Item(i + 1, data, canon, dict(a.elements[t]) if t != -1 else {"type": "none"}, None, off, end))
    return headers, blocks, list(a.problems)


def strip_anchor_lines(text):
    a = _Analysis(text)
    ends = list(a.ends)
    last = a.n - 1
    if a.lines[last] != "" and last in a.rec:   # a final anchor line without a line ending takes the ending before it
        k = last - 1
        while k >= 0 and k in a.rec:
            k -= 1
        if k >= 0:
            ends[k] = ""
    return "".join(a.lines[i] + ends[i] for i in range(a.n) if i not in a.rec)


def target_at(text, line):
    a = _Analysis(text)
    if not isinstance(line, int) or not 1 <= line <= a.nreal:
        return None
    for el in a.elements:
        if el["first_line"] <= line <= el["last_line"]:
            return dict(el)
    return None


def insert_after_line(text, line, comment_line):
    if "\n" in comment_line or "\r" in comment_line:
        raise ValueError("the comment must be one line")
    lines, ends = _split(text)
    nreal = len(lines) - 1 if lines[-1] == "" else len(lines)
    if not isinstance(line, int) or not 1 <= line <= nreal:
        raise ValueError(f"line {line!r} is not one of the {nreal} lines of the text")
    i = line - 1
    if ends[i]:
        nl = "\r\n" if ends[i] == "\r\n" else "\n"
        pos = sum(len(lines[x]) + len(ends[x]) for x in range(i + 1))
        return text[:pos] + comment_line + nl + text[pos:]
    nl = "\r\n" if i > 0 and ends[i - 1] == "\r\n" else "\n"
    return text + nl + comment_line


def block_id_ok(note_id, block_id):
    if not isinstance(note_id, str) or not isinstance(block_id, str):
        return False
    return re.fullmatch(re.escape(note_id) + r"\.b[0-9]{2,}", block_id) is not None


def next_block_id(note_id, used_ids):
    pat = re.compile(re.escape(note_id) + r"\.b([0-9]+)")
    top = 0
    for u in used_ids:
        m = pat.fullmatch(u) if isinstance(u, str) else None
        if m and len(m.group(1)) <= 30:
            top = max(top, int(m.group(1)))
    return f"{note_id}.b{top + 1:02d}"


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _str(v):
    return isinstance(v, str) and v != ""


def _decl_list(name, v, out):
    if not isinstance(v, list):
        out.append(f"{name}: must be a list")
        return
    for k, d in enumerate(v):
        if not isinstance(d, dict):
            out.append(f"{name}[{k}]: must be an object with module and name")
            continue
        for f in ("module", "name"):
            if not _str(d.get(f)):
                out.append(f"{name}[{k}].{f}: must be a non-empty string")
        if name == "defs_opened":
            ln = d.get("lines")
            if not (isinstance(ln, list) and len(ln) == 2 and all(_int(x) for x in ln)):
                out.append(f"{name}[{k}].lines: must be a list of two integers")


def problems(block, note_id=None):
    """Format-level problems of one block dict (a list of strings, each starting with the field name; [] = fine)."""
    if not isinstance(block, dict):
        return ["block: must be a JSON object"]
    out = []
    bid = block.get("id")
    if not isinstance(bid, str):
        out.append("id: missing or not a string")
    else:
        if note_id is None:
            note, sep, _ = bid.rpartition(".b")
            good = sep != "" and note != "" and block_id_ok(note, bid)
        else:
            good = block_id_ok(note_id, bid)
        if not good:
            out.append(f"id: {bid!r} is not <note id>.b<nn>" + (f" for note {note_id!r}" if note_id is not None else ""))
    kind = block.get("kind")
    if kind not in KINDS:
        out.append(f"kind: must be one of {', '.join(KINDS)}")
    elif kind == "machine_fact":
        for f in ("tool", "tool_version"):
            if not _str(block.get(f)):
                out.append(f"{f}: a machine_fact needs a non-empty string")
        if block.get("check") not in ("text", "index", "proofterm"):
            out.append("check: must be text, index or proofterm")
        if not isinstance(block.get("options"), str):
            out.append("options: a machine_fact needs options as a string (it may be empty)")
        c = block.get("complete")
        if c is False:
            out.append("complete: a machine_fact with complete false can only be anchored as not_read")
        elif block.get("check") == "proofterm" and c is not True:
            out.append("complete: check proofterm needs complete true")
    elif kind == "not_read":
        if block.get("needs") not in NEEDS:
            out.append(f"needs: must be one of {', '.join(NEEDS)}")
    elif kind == "argument":
        for f in ("reader", "date"):
            if not _str(block.get(f)):
                out.append(f"{f}: an argument needs a non-empty string")
        if block.get("decls", []) == []:
            out.append("decls: an argument needs at least one declaration")
    if "decls" in block:
        _decl_list("decls", block["decls"], out)
    if "defs_opened" in block:
        _decl_list("defs_opened", block["defs_opened"], out)
    if "conventions_checked" in block:
        cc = block["conventions_checked"]
        if not (isinstance(cc, list) and all(isinstance(x, str) and x in ("a", "b", "c", "d", "e") for x in cc)):
            out.append("conventions_checked: must be a list of letters a to e")
    for f in ("row", "col"):
        if f in block and not (_int(block[f]) and block[f] >= 1):
            out.append(f"{f}: must be an integer of 1 or more")
    return out


def header_problems(data):
    if not isinstance(data, dict):
        return ["header: must be a JSON object"]
    out = []
    for f in ("id", "group", "list_title", "release"):
        if not _str(data.get(f)):
            out.append(f"{f}: missing or not a non-empty string")
    lv = data.get("level")
    if not (_int(lv) and lv in (0, 1, 2)):
        out.append("level: must be 0, 1 or 2")
    for f in ("authors", "readers"):
        if not isinstance(data.get(f), list):
            out.append(f"{f}: missing or not a list")
    return out


# ---------------------------------------------------------------- self-test
_CASES = []


def case(cid, what):
    def deco(fn):
        _CASES.append((cid, what, fn))
        return fn
    return deco


def eq(got, want, what=""):
    if got != want:
        raise AssertionError(f"{what}: got {got!r}, want {want!r}")


def ok(cond, what):
    if not cond:
        raise AssertionError(what)


N = '<!-- rh-note {"id":"15"} -->'


def B(i, extra=""):
    return '<!-- rh-block {"id":"15.b%02d"%s} -->' % (i, extra)


def X(kind, first, last):
    return {"type": kind, "first_line": first, "last_line": last, "insert_after": last}


def T(first, last, ncols, nrows):
    return {"type": "table", "ncols": ncols, "nrows": nrows, "start_line": first,
            "first_line": first, "last_line": last, "insert_after": last}


# ---- A1 recognised lines
@case("A1a", "a valid rh-note line is one header, no problem")
def _():
    h, b, m = parse_note(N + "\n")
    eq((len(h), len(b), len(m)), (1, 0, 0), "counts")
    eq((h[0].line, h[0].data, h[0].canonical), (1, {"id": "15"}, True), "item")


@case("A1b", "a valid rh-block line is one block, no problem; an indented line is recognised but not canonical")
def _():
    h, b, m = parse_note("Text\n" + B(1) + "\n")
    eq((len(h), len(b), len(m)), (0, 1, 0), "counts")
    eq((b[0].line, b[0].data, b[0].canonical), (2, {"id": "15.b01"}, True), "item")
    h, b, m = parse_note("Text\n  " + B(1) + "  \n")
    eq((len(b), len(m), b[0].canonical), (1, 0, False), "indented")


@case("A1c", "every malformed rh- comment is a MALFORMED problem on its line and yields no item")
def _():
    bad = {
        "other tag": '<!-- rh-foo {"a":1} -->',
        "array": "<!-- rh-block [] -->",
        "string": '<!-- rh-block "x" -->',
        "number": "<!-- rh-block 5 -->",
        "not json": "<!-- rh-block {id:1} -->",
        "no close": '<!-- rh-block {"id":"1"} ',
        "close glued": '<!-- rh-block {"id":"1"}-->',
        "bare": "<!-- rh-note -->",
        "tag glued": '<!-- rh-block{"id":"1"} -->',
        "second comment": '<!-- rh-block {"id":"1"} --> <!-- rh-block {"id":"2"} -->',
        "second glued": '<!-- rh-block {"id":"1"} --><!-- rh-block {"id":"2"} -->',
        "text before": 'see <!-- rh-block {"id":"1"} -->',
        "text after": '<!-- rh-block {"id":"1"} --> tail',
    }
    for name, line in bad.items():
        h, b, m = parse_note("x\n" + line + "\ny\n")
        eq([(p.code, p.line) for p in m], [("MALFORMED", 2)], name)
        eq((len(h), len(b)), (0, 0), name + " items")
        ok("line 2" in m[0].message.lower(), name + " message names line")
    h, b, m = parse_note('<!-- rh-note {\n"id":"1"\n} -->\n')
    eq([(p.code, p.line) for p in m], [("MALFORMED", 1)], "spread over lines")
    eq((len(h), len(b)), (0, 0), "spread items")


@case("A1d", "a comment that is not rh- is ignored; a deep or very long line never raises")
def _():
    eq(parse_note("<!-- a note -->\n<!-- rhino -->\n"), ([], [], []), "plain comments")
    deep = "<!-- rh-block " + "[" * 100000 + "]" * 100000 + " -->\n"
    h, b, m = parse_note(deep)
    eq([(p.code, p.line) for p in m], [("MALFORMED", 1)], "deep")
    long = '<!-- rh-block {"id":"' + "x" * 1000000 + '"} -->\n'
    h, b, m = parse_note(long)
    eq((len(b), len(m)), (1, 0), "long line")


@case("A1e", "Problem fields have the named types")
def _():
    h, b, m = parse_note(N + "\n<!-- rh-foo {} -->\n")
    ok(isinstance(m[0].message, str) and isinstance(m[0].code, str) and isinstance(m[0].line, int), "problem types")
    ok(m[0].code.isupper(), "code upper-case")


# ---- A2 fenced code
@case("A2", "rh- comments inside a fence are text: not parsed, no problem; fence rules; unclosed fence")
def _():
    cases = [
        "```\n" + B(1) + "\n```\n",
        "~~~\n" + B(1) + "\n~~~\n",
        "````\n```\n" + B(1) + "\n```\n````\n",        # a shorter fence does not close a longer one
        "~~~\n```\n" + B(1) + "\n```\n~~~\n",          # the other character does not close
        "```lean\n<!-- rh-foo {} -->\n```\n",           # a malformed comment inside is not a problem either
        "```\n" + B(1) + "\n`````\n",                   # a longer closer closes
    ]
    for t in cases:
        eq(parse_note(t), ([], [], []), repr(t))
    h, b, m = parse_note("```\n" + B(1) + "\n```\n" + B(2) + "\n")
    eq([x.line for x in b], [4], "parsed again after the fence closes")
    h, b, m = parse_note("intro\n```lean\n" + B(1) + "\nmore\n")
    eq([(p.code, p.line) for p in m], [("UNCLOSED-FENCE", 2)], "unclosed")
    eq(len(b), 0, "unclosed: inside is text")
    h, b, m = parse_note("a ```not a fence``` here\n" + B(1) + "\n")
    eq((len(b), len(m)), (1, 0), "inline backticks are not a fence")


@case("A2b", "a closing-looking line with an info string does not close a fence; a longer tilde line does")
def _():
    eq(parse_note("```\n" + B(1) + "\n```lean\n" + B(2) + "\n```\n"), ([], [], []), "```lean inside an open fence")
    eq(parse_note("```\n" + B(1) + "\n``` x\n" + B(2) + "\n```\n"), ([], [], []), "``` x inside an open fence")
    eq(parse_note("~~~\n" + B(1) + "\n~~~ x\n" + B(2) + "\n~~~\n"), ([], [], []), "~~~ x inside an open fence")
    h, b, m = parse_note("~~~\n" + B(1) + "\n~~~~\n" + B(2) + "\n")
    eq(([x.line for x in b], m), ([4], []), "a longer tilde line closes; the next anchor is parsed")


# ---- A3 canonical form
@case("A3a", "format_comment literals")
def _():
    eq(format_comment("rh-block", {"kind": "reading", "id": "15.b03"}), '<!-- rh-block {"id":"15.b03","kind":"reading"} -->', "sorted")
    eq(format_comment("rh-note", {"a": "<&>"}), '<!-- rh-note {"a":"\\u003c\\u0026\\u003e"} -->', "escapes")
    eq(format_comment("rh-note", {"t": "é→"}), '<!-- rh-note {"t":"é→"} -->', "non-ascii raw")
    eq(format_comment("rh-note", {"a": "x --> y"}), '<!-- rh-note {"a":"x --\\u003e y"} -->', "arrow")
    eq(format_comment("rh-note", {"b": True, "n": None, "l": [1, 2], "d": {"z": 0}}),
       '<!-- rh-note {"b":true,"d":{"z":0},"l":[1,2],"n":null} -->', "types")
    eq(format_comment("rh-note", {"a": "l1\nl2"}), '<!-- rh-note {"a":"l1\\nl2"} -->', "newline")


@case("A3b", "a recognised line that is not canonical is returned with canonical False")
def _():
    for line in ['<!-- rh-block {"kind":"reading","id":"15.b01"} -->',   # key order
                 '<!-- rh-block {"id": "15.b01"} -->',                  # spaces
                 '<!-- rh-block  {"id":"15.b01"} -->',                  # double space
                 '<!-- rh-block {"id":"15.b01"} -->  ',                 # trailing space
                 '<!-- rh-block {"id":"15.b01","t":"a < b"} -->',       # unescaped <
                 '<!-- rh-block {"id":"15.b01","t":"x --> y"} -->']:    # arrow in a string
        h, b, m = parse_note(line + "\n")
        eq((len(b), len(m)), (1, 0), line)
        eq(b[0].canonical, False, line)
    h, b, m = parse_note('<!-- rh-block {"id":"15.b01"} -->\r\n')
    eq((b[0].canonical, len(m)), (True, 0), "CRLF line is canonical")


# ---- A4 round trip
@case("A4", "format then parse returns the same data, canonical, no problem (hand cases and seeded random)")
def _():
    hand = [{}, {"id": "15.b01"}, {"t": "a<b>c&d"}, {"t": 'q"uo\\te'}, {"t": "x --> y <!-- z -->"},
            {"t": "l1\nl2\r\nl3\rl4"}, {"t": "é→\U0001f600 \x0b\x0c\x85\x00\x7f"},
            {"b": True, "n": None, "i": -12, "big": 10 ** 30, "l": [1, [2, {"k": []}]], "d": {"z": {}}},
            {"<": 1, "&": 2, "-->": 3}]
    rng = random.Random(20261123)
    alpha = ["<", ">", "&", '"', "\\", "é", "→", "\n", "\r", " ", "-->", "\x00", "\t", " ", "a", "0",
             "\U0001f600", "<!--"]

    def s():
        return "".join(rng.choice(alpha) for _ in range(rng.randint(0, 8)))

    def val(d):
        k = rng.randint(0, 6 if d < 3 else 3)
        if k == 0:
            return s()
        if k == 1:
            return rng.randint(-10 ** 12, 10 ** 12)
        if k == 2:
            return rng.choice([True, False])
        if k == 3:
            return None
        if k == 4:
            return [val(d + 1) for _ in range(rng.randint(0, 3))]
        return {s(): val(d + 1) for _ in range(rng.randint(0, 3))}

    rand = [{s(): val(0) for _ in range(rng.randint(0, 4))} for _ in range(300)]
    for d in hand + rand:
        for tag in ("rh-note", "rh-block"):
            h, b, m = parse_note(format_comment(tag, d) + "\n")
            items = h if tag == "rh-note" else b
            eq((len(items), len(m), len(h) + len(b)), (1, 0, 1), repr(d))
            eq(items[0].data, d, repr(d))
            eq(items[0].canonical, True, repr(d))
    h, b, m = parse_note(format_comment("rh-block", {"b": True}) + "\n")
    ok(b[0].data["b"] is True, "bool stays a bool")


# ---- A5 placement and B3 spans
@case("A5a", "paragraph, none, blank lines, header comment")
def _():
    eq(parse_note("Intro line\nsecond line\n" + B(1) + "\n")[1][0].target, X("paragraph", 1, 2), "paragraph")
    eq(parse_note("Para\n\n\n" + B(1) + "\n")[1][0].target, X("paragraph", 1, 1), "blank lines between")
    eq(parse_note(B(1) + "\n")[1][0].target, {"type": "none"}, "start of file")
    eq(parse_note("\n\n" + B(1) + "\n")[1][0].target, {"type": "none"}, "only blanks above")
    eq(parse_note(N + "\n" + B(1) + "\n")[1][0].target, {"type": "none"}, "only the header above")
    h, b, m = parse_note("P\n" + B(1) + "\n" + B(2) + "\n")
    eq([x.target for x in b], [X("paragraph", 1, 1)] * 2, "anchors after anchors")
    eq(parse_note("Intro\n" + B(1) + "\nmore\n" + B(2) + "\n")[1][1].target, X("paragraph", 3, 3), "an anchor ends a paragraph run")
    eq(parse_note(N + "\n")[0][0].target, None, "headers carry no target")


@case("A5b", "fenced blocks: lean, other, tilde")
def _():
    eq(parse_note("Text\n\n```lean\ndef x := 1\n```\n" + B(1) + "\n")[1][0].target, X("lean", 3, 5), "lean")
    eq(parse_note("```lean4\nx\n```\n" + B(1) + "\n")[1][0].target, X("lean", 1, 3), "lean4")
    eq(parse_note("~~~lean\nx\n~~~\n" + B(1) + "\n")[1][0].target, X("lean", 1, 3), "tilde lean")
    eq(parse_note("```text\nx\n```\n" + B(1) + "\n")[1][0].target, X("other", 1, 3), "other fence")
    eq(parse_note("```\nx\n```\n" + B(1) + "\n")[1][0].target, X("other", 1, 3), "no info")
    eq(parse_note("```lean\nx\n\ny\n```\n" + B(1) + "\n")[1][0].target, X("lean", 1, 5), "blank inside")


@case("A5c", "other: headings and list items; a pipe run without a separator is a paragraph")
def _():
    eq(parse_note("## H\n" + B(1) + "\n")[1][0].target, X("other", 1, 1), "heading")
    eq(parse_note("- item\n" + B(1) + "\n")[1][0].target, X("other", 1, 1), "list")
    eq(parse_note("| a | b |\n| 1 | 2 |\n" + B(1) + "\n")[1][0].target, X("paragraph", 1, 2), "pipes, no separator")


@case("A5d", "tables: size, start line, span, both anchors, alignment row, header only, escaped pipe")
def _():
    t = "# Title\n\n| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |\n" + B(1, ',"row":1') + "\n" + B(2, ',"row":2') + "\n"
    h, b, m = parse_note(t)
    eq([x.target for x in b], [T(3, 6, 3, 2)] * 2, "table")
    eq(len(m), 0, "no problem")
    eq(parse_note("|a|b|\n|:--|--:|\n|1|2|\n" + B(1) + "\n")[1][0].target, T(1, 3, 2, 1), "alignment")
    eq(parse_note("| a |\n|---|\n" + B(1) + "\n")[1][0].target, T(1, 2, 1, 0), "header only")
    eq(parse_note("| a \\| b | c |\n|---|---|\n| 1 | 2 |\n" + B(1) + "\n")[1][0].target, T(1, 3, 2, 1), "escaped pipe")
    eq(parse_note("| a | b |\n|---|---|\n| 1 | 2 |\n\ntext\n" + B(1) + "\n")[1][0].target, X("paragraph", 5, 5), "table then prose")


# ---- A6 anchors inside tables
@case("A6", "a comment between two table rows is INSIDE-TABLE naming the line, and is still returned")
def _():
    t = "| a | b |\n|---|---|\n| 1 | 2 |\n" + B(1, ',"row":1') + "\n| 3 | 4 |\n" + B(2, ',"row":2') + "\n"
    h, b, m = parse_note(t)
    eq([(p.code, p.line) for p in m], [("INSIDE-TABLE", 4)], "problem")
    ok("line 4" in m[0].message.lower(), "names the line")
    eq([x.line for x in b], [4, 6], "still returned")
    eq((b[0].target["type"], b[0].target["insert_after"], b[1].target["insert_after"]), ("table", 5, 5), "insert after the table's last line")
    h, b, m = parse_note("| a |\n|---|\n| 1 |\n" + N + "\n| 2 |\n")
    eq(([(p.code, p.line) for p in m], len(h)), ([("INSIDE-TABLE", 4)], 1), "header comment inside a table")
    h, b, m = parse_note("| a |\n|---|\n| 1 |\n" + B(1) + "\n" + B(2) + "\n| 2 |\n")
    eq([(p.code, p.line) for p in m], [("INSIDE-TABLE", 4), ("INSIDE-TABLE", 5)], "two in a row")
    for t in ["| a |\n|---|\n| 1 |\n" + B(1) + "\n", "| a |\n|---|\n| 1 |\n" + B(1) + "\n\n| z |\n",
              "| a |\n|---|\n| 1 |\n" + B(1) + "\ntext\n", "text\n" + B(1) + "\n| a |\n|---|\n"]:
        eq(parse_note(t)[2], [], repr(t))


# ---- A7 header position
@case("A7", "every rh-note is a header with its line and before_first_h2")
def _():
    h, b, m = parse_note(N + "\n## A\n" + N + "\n")
    eq([(x.line, x.before_first_h2) for x in h], [(1, True), (3, False)], "two headers")
    eq([x.before_first_h2 for x in parse_note("# T\n" + N + "\n")[0]], [True], "no h2 at all")
    eq([x.before_first_h2 for x in parse_note("```\n## A\n```\n" + N + "\n")[0]], [True], "h2 in a fence does not count")
    eq([x.before_first_h2 for x in parse_note("### A\n" + N + "\n")[0]], [True], "### is not ##")
    eq([x.before_first_h2 for x in parse_note("##A\n" + N + "\n")[0]], [True], "## needs a space")
    eq([x.before_first_h2 for x in parse_note("## A\n" + N + "\n")[0]], [False], "after")
    eq(parse_note(B(1) + "\n")[1][0].before_first_h2, None, "blocks carry none")


# ---- A8 strip
@case("A8a", "strip is the exact inverse of inserting anchor lines (LF, CRLF, lone CR, no final newline, empty)")
def _():
    a = B(1)
    eq(strip_anchor_lines("x\n" + a + "\ny\n"), "x\ny\n", "LF")
    eq(strip_anchor_lines("x\r\n" + a + "\r\ny\r\n"), "x\r\ny\r\n", "CRLF")
    eq(strip_anchor_lines("x\r" + a + "\ry\r"), "x\ry\r", "lone CR")
    eq(strip_anchor_lines("x\n" + a + "\ny"), "x\ny", "no final newline, anchor before last line")
    eq(strip_anchor_lines(a + "\n"), "", "only an anchor")
    eq(strip_anchor_lines(""), "", "empty")
    eq(strip_anchor_lines(N + "\n" + a + "\n" + a + "\n"), "", "header, blocks and a duplicate")
    eq(strip_anchor_lines("té\x00\t \n" + a + "\n\n\nz"), "té\x00\t \n\n\nz", "other bytes kept")
    eq(strip_anchor_lines("x\n  " + a + "  \ny\n"), "x\ny\n", "indented anchor line is removed whole")


@case("A8b", "strip: a final anchor line without a line ending takes the line ending before it")
def _():
    eq(strip_anchor_lines("x\n" + B(1)), "x", "LF")
    eq(strip_anchor_lines("x\r\ny\r\n" + B(1)), "x\r\ny", "CRLF")
    eq(strip_anchor_lines("x\n" + B(1) + "\n" + B(2)), "x", "two anchors")
    eq(strip_anchor_lines(B(1)), "", "alone")
    eq(strip_anchor_lines("x\n" + B(1) + "\n"), "x\n", "a terminated final anchor leaves the ending")


@case("A8c", "strip leaves fenced anchor lines and malformed rh- lines alone")
def _():
    t = "```\n" + B(1) + "\n```\n"
    eq(strip_anchor_lines(t), t, "fenced")
    t = "~~~\n" + N + "\n~~~\ntext\n"
    eq(strip_anchor_lines(t), t, "tilde fenced")
    t = "x\n<!-- rh-foo {} -->\ny <!-- rh-block {} -->\n"
    eq(strip_anchor_lines(t), t, "malformed lines stay")
    eq(strip_anchor_lines("```\n" + B(1) + "\n```\n" + B(2) + "\nz\n"), "```\n" + B(1) + "\n```\nz\n", "after the fence")


# ---- A9 never raises
@case("A9", "300 seeded random strings: nothing raises, types right, line numbers in range")
def _():
    rng = random.Random(9)
    chars = list('<!-- rh-note block {}[]"\\ \n\r|`~#') + ["\x00", "é"]
    snippets = [N, B(1), B(2, ',"row":1'), '<!-- rh-block {"id":"1.b01"} -->', "```lean", "```", "~~~", "````",
                "## H", "| a | b |", "|---|---|", "<!-- rh-", " -->", "\r\n", "<!-- rh-foo {} -->", "[" * 50]
    for _i in range(300):
        pieces = [rng.choice(chars) if rng.random() < 0.6 else rng.choice(snippets) for _ in range(rng.randint(0, 60))]
        t = "".join(pieces)
        nlines = len(re.split(r"\r\n|\n|\r", t))
        h, b, m = parse_note(t)
        ok(isinstance(h, list) and isinstance(b, list) and isinstance(m, list), "types")
        for x in h + b:
            ok(isinstance(x.data, dict) and isinstance(x.canonical, bool) and 1 <= x.line <= nlines, "item " + repr(t))
            ok(0 <= x.offset < x.end <= len(t), "offsets " + repr(t))
        for p in m:
            ok(isinstance(p.code, str) and isinstance(p.message, str) and 1 <= p.line <= nlines, "problem " + repr(t))
        for x in b:
            ok(isinstance(x.target, dict) and "type" in x.target, "target " + repr(t))
        s = strip_anchor_lines(t)
        ok(isinstance(s, str) and len(s) <= len(t), "strip " + repr(t))
        for ln in (0, 1, nlines, nlines + 3):
            r = target_at(t, ln)
            ok(r is None or isinstance(r, dict), "target_at " + repr(t))


# ---- A10 duplicates
@case("A10", "the same content on two lines is two Items")
def _():
    h, b, m = parse_note("x\n" + B(1) + "\n" + B(1) + "\n")
    eq([x.line for x in b], [2, 3], "two blocks")
    eq(b[0].data, b[1].data, "same data")
    h, b, m = parse_note(N + "\n" + N + "\n")
    eq([x.line for x in h], [1, 2], "two headers")


# ---- A11 exit codes (the runner is exercised with injected case lists)
@case("A11", "selftest exit codes: 0 all pass, 1 any fail, 2 usage, 3 no case ran")
def _():
    quiet = lambda s: None  # noqa: E731
    eq(_run_cases([], quiet), 3, "no cases")
    eq(_run_cases([("p", "d", lambda: None)], quiet), 0, "pass")
    eq(_run_cases([("p", "d", lambda: None), ("f", "d", lambda: eq(1, 2))], quiet), 1, "one fails")
    eq(_run_cases([("c", "d", lambda: 1 / 0)], quiet), 1, "a crash is a failure")
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        eq(main([]), 2, "no args")
        eq(main(["--bogus"]), 2, "unknown")
        eq(main(["--selftest", "x"]), 2, "extra")
    ok("usage" in err.getvalue(), "usage text on stderr")


# ---- B1 writers
@case("B1", "render_block and render_header give the canonical line; render(parse(line).data) == line")
def _():
    eq(render_block({"kind": "reading", "id": "15.b03"}), '<!-- rh-block {"id":"15.b03","kind":"reading"} -->', "block")
    eq(render_header({"id": "15"}), '<!-- rh-note {"id":"15"} -->', "header")
    lines = ['<!-- rh-block {"id":"15.b01","t":"x \\u003e y \\u0026 \\u003c"} -->',
             '<!-- rh-block {"id":"15.b01","t":"x --\\u003e y","u":"é→"} -->',
             '<!-- rh-block {"id":"15.b01","t":"q\\"uo\\\\te\\nl2"} -->']
    for ln in lines:
        h, b, m = parse_note(ln + "\n")
        eq((len(b), len(m), b[0].canonical), (1, 0, True), ln)
        eq(render_block(b[0].data), ln, ln)
    h, b, m = parse_note('<!-- rh-note {"id":"15","t":"a<b"} -->\n')
    eq(render_header(h[0].data), '<!-- rh-note {"id":"15","t":"a\\u003cb"} -->', "header escape")


# ---- B2 validators
def vb(**kw):
    d = {"id": "15.b01", "kind": "reading"}
    d.update(kw)
    return d


def MF(**kw):
    d = {"id": "15.b01", "kind": "machine_fact", "check": "text", "tool": "decl_table.py", "tool_version": "abc1234", "options": ""}
    d.update(kw)
    return d


DECL = {"module": "A.B", "name": "n"}


def one(block, field, note_id=None, word=None):
    ps = problems(block, note_id)
    eq(len(ps), 1, f"{field}: {ps!r}")
    ok(ps[0].startswith(field), f"problem starts with {field!r}: {ps[0]!r}")
    if word:
        ok(word in ps[0], f"mentions {word!r}: {ps[0]!r}")


@case("B2a", "a valid block of each kind has no problems (defs_opened and conventions_checked are not required)")
def _():
    valid = [
        MF(), MF(check="index"), MF(check="proofterm", complete=True), MF(options="--x"),
        vb(), vb(kind="interpretation", reader="R", date="2026-11-23"), vb(kind="correction"),
        vb(decls=[DECL], file="F.lean", lines=[1, 2], reader="R", date="2026-11-23"),
        vb(kind="not_read", needs="callers"),
        vb(kind="argument", reader="R", date="2026-11-23", decls=[DECL]),
        vb(defs_opened=[{"module": "M", "name": "n", "lines": [1, 2]}], conventions_checked=["a", "d"]),
        vb(defs_opened=[], conventions_checked=[]),
        vb(row=1, col=2),
    ]
    for v in valid:
        eq(problems(v), [], repr(v))
        eq(problems(v, "15"), [], repr(v) + " with note")
    for n in NEEDS:
        eq(problems(vb(kind="not_read", needs=n)), [], n)
    eq(problems(vb(id="15.b123")), [], "three digits")


@case("B2b", "kind and id rules")
def _():
    one(vb(kind="nope"), "kind")
    one({"id": "15.b01"}, "kind")
    one(vb(id="15.b3"), "id")
    one(vb(id="15.bxx"), "id")
    one(vb(id="15"), "id")
    one({"kind": "reading"}, "id")
    one(vb(id=15), "id")
    one(vb(id="15.b01"), "id", note_id="16")
    one(vb(id="115.b01"), "id", note_id="15")
    eq(problems(vb(id="15.b01"), "15"), [], "right note")
    ps = problems("x")
    eq(len(ps), 1, "not an object")
    ok(ps[0].startswith("block"), "starts with block")


@case("B2c", "machine_fact rules, including: complete False can only be anchored as not_read")
def _():
    base = MF()
    for f in ("tool", "tool_version", "check", "options"):
        d = dict(base)
        del d[f]
        one(d, f)
    one(MF(tool=""), "tool")
    one(MF(tool_version=""), "tool_version")
    one(MF(check="other"), "check")
    one(MF(options=None), "options")
    one(MF(options=3), "options")
    one(MF(check="proofterm"), "complete")
    one(MF(check="proofterm", complete="yes"), "complete")
    one(MF(check="proofterm", complete=False), "complete", word="not_read")
    one(MF(check="text", complete=False), "complete", word="not_read")
    eq(problems(MF(check="text", complete=True)), [], "complete true is fine for text")


@case("B2d", "not_read and argument rules")
def _():
    one(vb(kind="not_read"), "needs")
    one(vb(kind="not_read", needs="other"), "needs")
    one(vb(kind="not_read", needs=None), "needs")
    arg = dict(kind="argument", reader="R", date="2026-11-23", decls=[DECL])
    eq(problems(vb(**arg)), [], "valid argument")
    for f in ("reader", "date", "decls"):
        d = dict(arg)
        del d[f]
        one(vb(**d), f)
    one(vb(**dict(arg, decls=[])), "decls")
    one(vb(**dict(arg, reader="")), "reader")


@case("B2e", "decls, defs_opened, conventions_checked, row and col shapes")
def _():
    one(vb(decls="x"), "decls")
    one(vb(decls=["x"]), "decls[0]")
    one(vb(decls=[{"module": "A", "name": 5}]), "decls[0].name")
    one(vb(decls=[{"module": 5, "name": "n"}]), "decls[0].module")
    one(vb(decls=[{"name": "n"}]), "decls[0].module")
    one(vb(decls=[DECL, {"module": "A"}]), "decls[1].name")
    one(vb(defs_opened="x"), "defs_opened")
    one(vb(defs_opened=["x"]), "defs_opened[0]")
    one(vb(defs_opened=[{"module": "M", "name": "n"}]), "defs_opened[0].lines")
    one(vb(defs_opened=[{"module": "M", "name": "n", "lines": [1]}]), "defs_opened[0].lines")
    one(vb(defs_opened=[{"module": "M", "name": "n", "lines": [1, "2"]}]), "defs_opened[0].lines")
    one(vb(defs_opened=[{"module": "M", "name": "n", "lines": [True, 2]}]), "defs_opened[0].lines")
    one(vb(defs_opened=[{"module": "M", "lines": [1, 2]}]), "defs_opened[0].name")
    one(vb(conventions_checked="a"), "conventions_checked")
    one(vb(conventions_checked=["f"]), "conventions_checked")
    one(vb(conventions_checked=["a", 1]), "conventions_checked")
    for f in ("row", "col"):
        one(vb(**{f: 0}), f)
        one(vb(**{f: "1"}), f)
        one(vb(**{f: True}), f)
        one(vb(**{f: 1.5}), f)
        one(vb(**{f: -1}), f)


@case("B2f", "header_problems")
def _():
    good = {"id": "15", "level": 2, "group": "g", "list_title": "T", "authors": ["H"], "readers": ["K"], "release": "rh-1"}
    eq(header_problems(good), [], "valid")
    for lv in (0, 1, 2):
        eq(header_problems(dict(good, level=lv)), [], f"level {lv}")
    for f in good:
        d = dict(good)
        del d[f]
        ps = header_problems(d)
        eq(len(ps), 1, f"missing {f}: {ps!r}")
        ok(ps[0].startswith(f), f"starts with {f}: {ps[0]!r}")
    for f, v in [("level", 3), ("level", "2"), ("level", True), ("level", -1), ("list_title", ""), ("list_title", 5),
                 ("authors", "H"), ("readers", "K"), ("group", ""), ("id", ""), ("release", ""), ("release", 5)]:
        ps = header_problems(dict(good, **{f: v}))
        eq(len(ps), 1, f"{f}={v!r}: {ps!r}")
        ok(ps[0].startswith(f), f"starts with {f}: {ps[0]!r}")
    eq(len(header_problems("x")), 1, "not an object")


# ---- B3 target_at and spans
@case("B3", "target_at: table body and separator rows, lean fence, paragraph, between elements, out of range")
def _():
    t = "Intro\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```lean\ndef x := 1\n```\n\n"
    eq(target_at(t, 1), X("paragraph", 1, 1), "paragraph")
    eq(target_at(t, 5), T(3, 5, 2, 1), "table body row")
    eq(target_at(t, 4), T(3, 5, 2, 1), "separator row")
    eq(target_at(t, 3), T(3, 5, 2, 1), "header row")
    eq(target_at(t, 8), X("lean", 7, 9), "inside the lean fence")
    eq(target_at(t, 7), X("lean", 7, 9), "fence opener")
    eq(target_at(t, 2), None, "blank between")
    eq(target_at(t, 6), None, "blank between table and fence")
    eq(target_at(t, 0), None, "line 0")
    eq(target_at(t, 99), None, "past the end")
    eq(target_at("| a |\n|---|\n| 1 |\n" + B(1) + "\n| 2 |\n", 4), T(1, 5, 1, 2), "an anchor line inside a table is held by the table")
    eq(target_at("P\n" + B(1) + "\n", 2), None, "an anchor line after a paragraph is between elements")


# ---- B4 ids
@case("B4", "next_block_id: smallest number above the largest used for that note; holes are never reused")
def _():
    eq(next_block_id("15", []), "15.b01", "none used")
    eq(next_block_id("15", ["15.b01", "15.b02", "15.b05"]), "15.b06", "holes")
    eq(next_block_id("15", ["15.b03"]), "15.b04", "one")
    eq(next_block_id("15", ["15.b09"]), "15.b10", "ten")
    eq(next_block_id("15", ["15.b99"]), "15.b100", "three digits")
    eq(next_block_id("15", ["15.b100"]), "15.b101", "three digits used")
    eq(next_block_id("15", ["16.b09", "115.b07", "15.b2x", "15.b", "15.b٣"]), "15.b01", "other notes and odd ids ignored")
    eq(next_block_id("1", ["11.b05"]), "1.b01", "prefix of another note")
    eq(next_block_id("a.b", ["a.b.b04", "aXb.b09"]), "a.b.b05", "note id is not a pattern")
    eq(next_block_id("15", iter(["15.b02"])), "15.b03", "any iterable")


# ---- B5 offsets and insertion
@case("B5a", "Item.offset and Item.end are character offsets, the line ending kept")
def _():
    t = "ab\r\n" + N + "\nx"
    h, b, m = parse_note(t)
    eq((h[0].offset, h[0].end), (4, 4 + len(N) + 1), "LF after CRLF line")
    eq(t[h[0].offset:h[0].end], N + "\n", "slice")
    t = "x\n" + B(1) + "\r\n" + B(2)
    h, b, m = parse_note(t)
    eq(t[b[0].offset:b[0].end], B(1) + "\r\n", "CRLF kept")
    eq((b[1].offset, b[1].end), (len("x\n" + B(1) + "\r\n"), len(t)), "last line without ending")
    h, b, m = parse_note("a\r" + B(1) + "\r")
    eq((b[0].offset, b[0].end), (2, 2 + len(B(1)) + 1), "lone CR")


@case("B5b", "insert_after_line: that file's line ending; the final newline rule, literal")
def _():
    C = B(1)
    eq(insert_after_line("a\nb\n", 1, C), "a\n" + C + "\nb\n", "LF middle")
    eq(insert_after_line("a\nb\n", 2, C), "a\nb\n" + C + "\n", "LF last, terminated: comment is terminated too")
    eq(insert_after_line("a\r\nb\r\n", 1, C), "a\r\n" + C + "\r\nb\r\n", "CRLF middle")
    eq(insert_after_line("a\r\nb\r\n", 2, C), "a\r\nb\r\n" + C + "\r\n", "CRLF last")
    eq(insert_after_line("a\nb", 1, C), "a\n" + C + "\nb", "no final newline, middle")
    eq(insert_after_line("a\nb", 2, C), "a\nb\n" + C, "no final newline, last: one newline added before, none after")
    eq(insert_after_line("a", 1, C), "a\n" + C, "single unterminated line")
    eq(insert_after_line("a\r\nb", 2, C), "a\r\nb\r\n" + C, "CRLF file, last unterminated: CRLF before")
    eq(insert_after_line("a\rb\r", 1, C), "a\r" + C + "\nb\r", "lone CR line gets LF")


@case("B5c", "strip(insert(t)) == t for every line of LF, CRLF, no-final-newline, single-line and fenced texts")
def _():
    texts = ["a\nb\nc\n", "a\r\nb\r\nc\r\n", "a\nb\nc", "a\r\nb\r\nc", "a", "a\n", "a\r\n", "| h |\n|---|\n| 1 |\n",
             "a\rb\rc", "\n\n", "té\x00\n"]
    C = B(1)
    for t in texts:
        n = len(re.split(r"\r\n|\n|\r", t))
        if t.endswith(("\n", "\r")):
            n -= 1
        for ln in range(1, n + 1):
            r = insert_after_line(t, ln, C)
            eq(strip_anchor_lines(r), t, f"{t!r} after {ln}")
            ok(C in r, "comment present")
    t = "x\n```lean\ny\n```\nz"
    for ln in (1, 4, 5):   # outside the fence; a line inserted inside a fence is text and is not stripped (A2)
        eq(strip_anchor_lines(insert_after_line(t, ln, C)), t, f"fenced text after {ln}")
    eq(strip_anchor_lines(insert_after_line(t, 2, C)), insert_after_line(t, 2, C), "inside a fence stays")
    t = "a\nb"
    r = insert_after_line(insert_after_line(t, 2, B(1)), 3, B(2))
    eq((r, strip_anchor_lines(r)), ("a\nb\n" + B(1) + "\n" + B(2), t), "two insertions at the end")


@case("B5d", "insert_after_line refuses a line out of range and a comment with a line break")
def _():
    for t, ln in [("a\nb\n", 0), ("a\nb\n", 3), ("a\nb", 3), ("", 1), ("a", -1)]:
        try:
            insert_after_line(t, ln, B(1))
        except ValueError:
            continue
        raise AssertionError(f"no ValueError for {t!r}, {ln}")
    for c in ("a\nb", "a\rb", B(1) + "\n"):
        try:
            insert_after_line("a\n", 1, c)
        except ValueError:
            continue
        raise AssertionError(f"no ValueError for comment {c!r}")


# ---- reviewer round: K (discriminating cases for existing behaviour) and V (new rules)
@case("K1", "a backtick opener whose info string holds a backtick is not a fence")
def _():
    h, b, m = parse_note("```x``` y\n" + B(1) + "\n")
    eq((len(b), len(m)), (1, 0), "one block, no problem")


@case("K2", "next_block_id ignores an id with an absurd digit run and does not raise")
def _():
    eq(next_block_id("15", ["15.b" + "9" * 5000]), "15.b01", "5000 digits")


@case("K3", "complete must be exactly true or false on a machine_fact; proofterm needs true")
def _():
    one(MF(check="proofterm", complete=1), "complete", word="proofterm")
    one(MF(check="proofterm", complete=1.0), "complete", word="proofterm")
    one(MF(check="text", complete=0), "complete")
    one(MF(check="text", complete="no"), "complete")
    one(MF(check="text", complete=1), "complete")
    one(MF(check="text", complete=None), "complete")
    eq(problems(MF(check="text", complete=True)), [], "true on text")
    eq(problems(MF(check="proofterm", complete=True)), [], "true on proofterm")


@case("K4", "target type other: a thematic break and ordered list items")
def _():
    eq(parse_note("***\n" + B(1) + "\n")[1][0].target, X("other", 1, 1), "***")
    eq(parse_note("1. x\n" + B(1) + "\n")[1][0].target, X("other", 1, 1), "1.")
    eq(parse_note("2) x\n" + B(1) + "\n")[1][0].target, X("other", 1, 1), "2)")
    eq(parse_note("***bold*** x\n" + B(1) + "\n")[1][0].target, X("paragraph", 1, 1), "emphasis is a paragraph")


@case("V1", "interpretation needs a non-empty reader and date; other kinds are not extended")
def _():
    eq(problems(vb(kind="interpretation", reader="R", date="2026-11-23")), [], "valid")
    one(vb(kind="interpretation", date="2026-11-23"), "reader")
    one(vb(kind="interpretation", reader="R"), "date")
    one(vb(kind="interpretation", reader="", date="2026-11-23"), "reader")
    one(vb(kind="interpretation", reader="R", date=5), "date")
    eq(len(problems(vb(kind="interpretation"))), 2, "both missing")
    eq(problems(vb(kind="correction")), [], "correction unchanged")
    eq(problems(vb(kind="reading")), [], "reading unchanged")
    eq(problems(vb(kind="not_read", needs="route")), [], "not_read unchanged")


@case("V2", "file is a non-empty str; lines two ints >= 1 with first <= last; col needs row")
def _():
    eq(problems(vb(file="F.lean", lines=[1, 1])), [], "valid, equal ends")
    one(vb(file=""), "file")
    one(vb(file=5), "file")
    one(vb(lines=[2, 1]), "lines")
    one(vb(lines=[0, 1]), "lines")
    one(vb(lines=[1]), "lines")
    one(vb(lines=[1, "2"]), "lines")
    one(vb(lines=[True, 2]), "lines")
    one(vb(lines="1-2"), "lines")
    one(vb(col=2), "col", word="row")
    eq(problems(vb(row=1)), [], "row alone is fine")
    eq(problems(vb(row=1, col=1)), [], "row and col")


@case("V3", "format_comment escapes U+2028, U+2029 and U+0085, so the canonical comment is one line")
def _():
    d = {"t": "a b c\x85d"}
    line = format_comment("rh-note", d)
    eq(line, '<!-- rh-note {"t":"a\\u2028b\\u2029c\\u0085d"} -->', "literal")
    eq(len(line.splitlines()), 1, "one line under str.splitlines")
    h, b, m = parse_note(line + "\n")
    eq((len(h), len(m), h[0].data, h[0].canonical), (1, 0, d, True), "round trip")
    h, b, m = parse_note('<!-- rh-note {"t":"a b"} -->\n')
    eq((len(h), h[0].canonical), (1, False), "a raw U+2028 in a hand-written line is not canonical")


@case("CONST", "the closed lists, in order")
def _():
    eq(NEEDS, ("callers", "route", "enclosing", "resolve", "fields_read", "uses", "hand_read", "full_build"), "NEEDS")
    eq(KINDS, ("machine_fact", "reading", "interpretation", "correction", "not_read", "argument"), "KINDS")


@case("IDOK", "block_id_ok: note id, '.b', two or more ASCII digits, nothing else")
def _():
    for n, b in [("15", "15.b01"), ("15", "15.b99"), ("15", "15.b100"), ("landau-step", "landau-step.b07")]:
        eq(block_id_ok(n, b), True, b)
    for n, b in [("15", "15.b1"), ("15", "15.b"), ("15", "16.b01"), ("15", "15.b01x"), ("15", "15.b0a"), ("15", "x15.b01"),
                 ("15", "15.B01"), ("15", "15.b01\n"), ("15", ""), ("15", "15b01"), ("15", "15.b٣٣"),
                 ("a.b", "aXb.b01"), ("15", "115.b01")]:
        eq(block_id_ok(n, b), False, repr(b))
    eq(block_id_ok("a.b", "a.b.b01"), True, "dot in the note id is literal")


def _run_cases(cases, write):
    """Run (id, what, fn) cases; write(line) for each report line. Exit code: 0, 1 (a failure), 3 (none ran)."""
    failed = 0
    for cid, what, fn in cases:
        try:
            fn()
            write(f"CASE {cid} PASS {what}")
        except Exception as e:  # a crash is a failed case
            failed += 1
            write(f"CASE {cid} FAIL {what}")
            write(f"  detail: {type(e).__name__}: {e}")
    write(f"{len(cases)} cases, {failed} failed")
    if not cases:
        write("CHECKED NOTHING: no case ran")
        return 3
    return 1 if failed else 0


def selftest():
    print("# cases range over: line recognition and malformed lines (A1), fences (A2), canonical form and the round trip")
    print("# (A3, A4), placement, spans and tables (A5, A6, B3), header position (A7), strip and insert (A8, B5), 300")
    print("# seeded random strings that must never raise (A9), duplicates (A10), exit codes (A11), writers (B1), format")
    print("# validators (B2), id numbering (B4), the closed lists and block_id_ok. Expected values are literals.")
    return _run_cases(_CASES, print)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--selftest"]:
        return selftest()
    print("usage: rh_anchor.py --selftest   (a library: import it, no other command line)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
