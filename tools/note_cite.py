#!/usr/bin/env python3
"""Write one block anchor into a note, so nobody types the JSON (spec F3).

    note_cite.py NOTE DECLS_TSV --at LINE --decl FULL.NAME --kind KIND --reader R --date D [options]
    note_cite.py --selftest

The helper resolves the declaration's module through decls.tsv, builds the block anchor, checks it with the same
module the checker uses (rh_anchor), finds the element the anchor belongs to from a line of the note (--at), and
puts the comment after that element and after any anchors already there. By default it only prints what it would
write; --write writes the note. tools/notes_meta.py is the checker of what this writes.

Options
  --module M           pick the row when the name is in more than one module
  --lines A-B          the lines of the declaration's file that were read; must lie inside the declaration's extent
  --item N             the top-level list item (default: the item holding --at)
  --row N [--col N]    the table body row (default: the row holding --at) and an optional column
  --needs X            for kind not_read: one of rh_anchor.NEEDS
  --tool T --tool-version V --check C --options O [--complete true|false]   for kind machine_fact (spec F4)
  --second-reader R:D  a second reader and date (repeatable)
  --notes-dir DIR      where to collect used block ids (default: the note's folder, files `[0-9][0-9]-*.md`)
  --src SRC_ROOT       also print the cited lines from the reader's local copy (spec F8c) and check they exist
  --write              write the note (otherwise a dry run)

CONTRACT (each line is a self-test case, written before the code)
 C1 --decl resolves by full name to exactly one decls.tsv row: none is UNRESOLVED; two or more is AMBIGUOUS, naming
    each candidate's module and extent, unless --module picks one; a --module that is not among the rows of that
    name is NOT-IN-MODULE. The block's `decls` is [{module, name}] and its `file` is the module with dots as slashes
    plus `.lean`. Cases C1a C1b C1c C1d.
 C2 --lines A-B must be two integers 1 <= A <= B (else exit 2, usage) and lie inside the row's [first_line,
    last_line] (else OUTSIDE-EXTENT naming the extent). Without --lines the block has no `lines`. Cases C2a C2b C2c.
 C3 `file` must be listed in the note's file table (the rows the checker reads with check_lean_blocks.listed_files):
    no table is NO-FILE-TABLE, a file not in it is NOT-IN-FILE-TABLE. Cases C3a C3b.
 C4 Placement. The target is rh_anchor.target_at(note, --at). None (a blank line, past the end) is NO-TARGET; a
    heading, quote, HTML line or a non-lean fence (type other) is ORPHAN-TARGET. The comment goes after the target's
    append_after line, so a second anchor on the same element lands below the first (in order). Cases C4a C4b C4c C4d.
 C5 Tables: the row is --row, else the body row holding --at; neither is ROW-NEEDED; a row above the table's body rows
    is ROW-RANGE, a --col above its column count COL-RANGE. Lists: the item is --item, else rh_anchor.item_at(--at);
    neither is ITEM-NEEDED; above nitems is ITEM-RANGE. --item on a target that is not a list is ITEM-NOT-LIST,
    --row or --col on one that is not a table ROW-NOT-TABLE. Cases C5a C5b C5c C5d C5e C5f.
 C6 The note must have exactly one rh-note header (NO-HEADER, SECOND-HEADER), and no MALFORMED, UNCLOSED-FENCE or
    INSIDE-TABLE problem (NOT-CLEAN naming the first): placement in a note the parser cannot read is not trusted.
    Case C6a C6b C6c.
 C7 The id is rh_anchor.next_block_id(header id, every block id in the notes folder). Case C7.
 C8 Required fields: kinds reading, argument, interpretation and correction need --reader and --date (MISSING-FIELD);
    the helper never fills a reader or a date by default. The finished block must have no rh_anchor.problems() (BAD-BLOCK
    with them). Cases C8a C8b C8c.
 C9 Post-conditions, checked on every write before it is returned: strip_anchor_lines(new) == strip_anchor_lines(old);
    the new note parses with one block more, that block's data is the built block, it is canonical, and its target has
    the same first_line as the element chosen; no new parse problem. A failure is exit 4 (a bug here), nothing written.
    The note's line endings are kept (CRLF stays CRLF). Cases C9a C9b.
 C10 Command line: a dry run prints the comment and the line it goes after and leaves the file unchanged; --write
    writes it and says so; --src prints the cited lines, and a file missing under SRC_ROOT or too short is SRC-MISSING
    or SRC-RANGE. Exit codes: 0 done, 2 usage or unreadable input, 4 a post-condition failed, 5 refused (one line
    `REFUSED CODE message`), and --selftest 0 all pass, 1 any fails, 3 no case ran. Cases X1 X2 X3 X4.

LIMIT. One declaration per block: a citation whose lines cross a declaration's end is refused, not split; a block
naming several declarations is written by hand and checked by notes_meta. The extent is the text rule's
(decl_table.py), not Lean's, so a range the text rule cuts short is refused although Lean would accept it. The helper
does not judge whether the cited lines support the sentence they follow, whether the reader read them, or whether
the kind is right: those are the reader's and the peer's. It does not write headers, `defs_opened` or
`conventions_checked` (claims live in the outline). The file table check reads the table by the checker's own
pattern, so a table the checker cannot read is NO-FILE-TABLE here too. Block ids are compared within the notes
folder only. A date is a non-empty string; its form is not checked (as in rh_anchor).
"""
from __future__ import annotations

import argparse
import glob
import importlib.util
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_GLOB = "[0-9][0-9]-*.md"
NEEDS_READER = ("reading", "argument", "interpretation", "correction")


def _load_sibling(name):
    """A module of this folder, loaded by file path (never through sys.path), under a private name."""
    key = "_note_cite_" + name
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, os.path.join(_HERE, name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            sys.modules.pop(key, None)
            raise
    return sys.modules[key]


rh = _load_sibling("rh_anchor")
clb = _load_sibling("check_lean_blocks")


class Refused(Exception):
    def __init__(self, code, message):
        super().__init__(f"{code} {message}")
        self.code, self.message = code, message


class PostConditionFailed(Exception):
    pass


# ---------------------------------------------------------------- the tool
DECL_COLS = ["module", "name", "kind", "first_line", "last_line", "basis"]


def read_decls(lines):
    """name -> list of row dicts, from the lines of a decls.tsv (comment lines start with '#', then a header row).
    A row that is not six columns with integer lines is a ValueError (unreadable input)."""
    out = {}
    header_seen = False
    for n, raw in enumerate(lines, 1):
        line = raw.rstrip("\r\n")
        if not line or line.startswith("#"):
            continue
        cols = line.split("\t")
        if not header_seen:
            if cols != DECL_COLS:
                raise ValueError(f"decls line {n}: header is not {' '.join(DECL_COLS)}")
            header_seen = True
            continue
        if len(cols) != 6 or not cols[3].isdigit() or not cols[4].isdigit():
            raise ValueError(f"decls line {n}: not six columns with numeric lines")
        out.setdefault(cols[1], []).append({"module": cols[0], "name": cols[1], "kind": cols[2],
                                            "first_line": int(cols[3]), "last_line": int(cols[4])})
    if not header_seen:
        raise ValueError("decls: no header row")
    return out


def resolve(rows_by_name, name, module=None):
    rows = rows_by_name.get(name, [])
    if not rows:
        raise Refused("UNRESOLVED", f"{name} is not a name in decls.tsv")
    if module is not None:
        picked = [r for r in rows if r["module"] == module]
        if not picked:
            raise Refused("NOT-IN-MODULE", f"{name} has no row in module {module} (its modules: "
                          + ", ".join(sorted({r['module'] for r in rows})) + ")")
        rows = picked
    if len(rows) > 1:
        raise Refused("AMBIGUOUS", f"{name} has {len(rows)} rows; pick one with --module: "
                      + "; ".join(f"{r['module']} lines {r['first_line']}-{r['last_line']}" for r in rows))
    return rows[0]


def _clean(text):
    """The header data of a note the parser reads without problems, else Refused."""
    headers, blocks, probs = rh.parse_note(text)
    if probs:
        p = probs[0]
        raise Refused("NOT-CLEAN", f"line {p.line}: {p.code} {p.message} (fix the note first)")
    if not headers:
        raise Refused("NO-HEADER", "the note has no rh-note header")
    if len(headers) > 1:
        raise Refused("SECOND-HEADER", "the note has rh-note headers on lines " + ", ".join(str(h.line) for h in headers))
    nid = headers[0].data.get("id") if isinstance(headers[0].data, dict) else None
    if not isinstance(nid, str) or not nid:
        raise Refused("NO-HEADER", f"the header on line {headers[0].line} has no id")
    return nid, blocks, probs


def cite(text, rows_by_name, used_ids, *, at, decl, kind, module=None, lines=None, reader=None, date=None,
         needs=None, item=None, row=None, col=None, machine=None, second_readers=None):
    """(new_text, block, after_line). Raises Refused, or PostConditionFailed on a bug."""
    note_id, old_blocks, old_probs = _clean(text)
    if kind in NEEDS_READER:
        for f, v in (("reader", reader), ("date", date)):
            if not (isinstance(v, str) and v):
                raise Refused("MISSING-FIELD", f"kind {kind} needs --{f}; the helper fills none by default")
    r = resolve(rows_by_name, decl, module)
    path = r["module"].replace(".", "/") + ".lean"
    if lines is not None:
        a, b = lines
        if not (r["first_line"] <= a <= b <= r["last_line"]):
            raise Refused("OUTSIDE-EXTENT", f"lines {a}-{b} are not inside {decl}'s extent, lines "
                          f"{r['first_line']}-{r['last_line']} of {path}")
    files = clb.listed_files(text)
    if not files:
        raise Refused("NO-FILE-TABLE", "the note has no file table the checker can read")
    if path not in files:
        raise Refused("NOT-IN-FILE-TABLE", f"{path} is not in the note's file table; add its row first")

    tgt = rh.target_at(text, at)
    if tgt is None:
        raise Refused("NO-TARGET", f"line {at} is not inside a paragraph, table, list or lean block, nor in the "
                      "anchor lines after one")
    if tgt["type"] not in ("paragraph", "table", "list", "lean"):
        raise Refused("ORPHAN-TARGET", f"line {at} is in a {tgt['type']} element (lines {tgt['first_line']}-"
                      f"{tgt['last_line']}): a heading, quote, HTML line or non-lean fence takes no anchor")
    if item is not None and tgt["type"] != "list":
        raise Refused("ITEM-NOT-LIST", f"--item given, but line {at} is in a {tgt['type']}")
    if (row is not None or col is not None) and tgt["type"] != "table":
        raise Refused("ROW-NOT-TABLE", f"--row/--col given, but line {at} is in a {tgt['type']}")
    place = {}
    if tgt["type"] == "table":
        if row is None:
            k = at - tgt["start_line"] - 1
            if not (tgt["start_line"] + 2 <= at <= tgt["last_line"]):
                raise Refused("ROW-NEEDED", f"line {at} is not a body row of the table at lines "
                              f"{tgt['first_line']}-{tgt['last_line']}; give --row")
            row = k
        if not (1 <= row <= tgt["nrows"]):
            raise Refused("ROW-RANGE", f"row {row}: the table has {tgt['nrows']} body rows")
        place["row"] = row
        if col is not None:
            if not (1 <= col <= tgt["ncols"]):
                raise Refused("COL-RANGE", f"col {col}: the table has {tgt['ncols']} columns")
            place["col"] = col
    elif tgt["type"] == "list":
        if item is None:
            item = rh.item_at(text, at)
            if item is None:
                raise Refused("ITEM-NEEDED", f"line {at} is not inside an item of the list at lines "
                              f"{tgt['first_line']}-{tgt['last_line']}; give --item")
        if not (1 <= item <= tgt["nitems"]):
            raise Refused("ITEM-RANGE", f"item {item}: the list has {tgt['nitems']} top-level items")
        place["item"] = item

    block = {"id": rh.next_block_id(note_id, set(used_ids) | {x.data.get("id") for x in old_blocks
                                                              if isinstance(x.data, dict)}),
             "kind": kind, "decls": [{"module": r["module"], "name": r["name"]}], "file": path}
    if lines is not None:
        block["lines"] = [lines[0], lines[1]]
    if reader is not None:
        block["reader"] = reader
    if date is not None:
        block["date"] = date
    if needs is not None:
        block["needs"] = needs
    if machine:
        block.update(machine)
    if second_readers:
        block["second_readers"] = list(second_readers)
    block.update(place)
    bad = rh.problems(block, note_id)
    if bad:
        raise Refused("BAD-BLOCK", "; ".join(bad))

    after = tgt["append_after"]
    new = rh.insert_after_line(text, after, rh.render_block(block))
    _post(text, new, block, tgt, len(old_blocks), len(old_probs))
    return new, block, after


def _post(old, new, block, tgt, nold, nprobs):
    if rh.strip_anchor_lines(new) != rh.strip_anchor_lines(old):
        raise PostConditionFailed("stripping the new note does not give the old one")
    _, blocks, probs = rh.parse_note(new)
    if len(blocks) != nold + 1:
        raise PostConditionFailed(f"{len(blocks)} blocks after the insert, expected {nold + 1}")
    mine = [x for x in blocks if x.data == block]
    if len(mine) != 1:
        raise PostConditionFailed("the new block does not parse back exactly once")
    if not mine[0].canonical:
        raise PostConditionFailed("the new block is not canonical")
    if mine[0].target.get("first_line") != tgt["first_line"]:
        raise PostConditionFailed(f"the new block's target starts at line {mine[0].target.get('first_line')}, "
                                  f"expected {tgt['first_line']}")
    if len(probs) != nprobs:
        raise PostConditionFailed("the insert made a new parse problem")


def _lines_arg(s):
    a, sep, b = s.partition("-")
    if not sep:
        a = b = s
    if not (a.isdigit() and b.isdigit()) or not (1 <= int(a) <= int(b)):
        raise argparse.ArgumentTypeError(f"--lines {s!r}: want A-B with 1 <= A <= B")
    return int(a), int(b)


def _second_reader(s):
    r, sep, d = s.partition(":")
    if not sep or not r or not d:
        raise argparse.ArgumentTypeError(f"--second-reader {s!r}: want READER:DATE")
    return {"reader": r, "date": d}


def _bool(s):
    if s not in ("true", "false"):
        raise argparse.ArgumentTypeError("--complete: true or false")
    return s == "true"


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise SystemExit(f"usage: {message}")


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    p = _Parser(prog="note_cite.py", description="Write one block anchor into a note (spec F3).")
    p.add_argument("note")
    p.add_argument("decls_tsv")
    p.add_argument("--at", type=int, required=True)
    p.add_argument("--decl", required=True)
    p.add_argument("--kind", required=True, choices=rh.KINDS)
    p.add_argument("--module")
    p.add_argument("--lines", type=_lines_arg)
    p.add_argument("--reader")
    p.add_argument("--date")
    p.add_argument("--needs")
    p.add_argument("--item", type=int)
    p.add_argument("--row", type=int)
    p.add_argument("--col", type=int)
    p.add_argument("--tool")
    p.add_argument("--tool-version")
    p.add_argument("--check")
    p.add_argument("--options")
    p.add_argument("--complete", type=_bool)
    p.add_argument("--second-reader", type=_second_reader, action="append")
    p.add_argument("--notes-dir")
    p.add_argument("--src")
    p.add_argument("--write", action="store_true")
    try:
        a = p.parse_args(argv)
    except SystemExit as e:
        print(e.code if isinstance(e.code, str) else "usage: see --help", file=sys.stderr)
        return 2
    try:
        with open(a.note, encoding="utf-8", newline="") as f:
            text = f.read()
        with open(a.decls_tsv, encoding="utf-8") as f:
            rows = read_decls(f)
        ndir = a.notes_dir or os.path.dirname(os.path.abspath(a.note))
        used = set()
        for path in sorted(glob.glob(os.path.join(ndir, DEFAULT_GLOB))):
            if os.path.abspath(path) == os.path.abspath(a.note):
                continue
            with open(path, encoding="utf-8", newline="") as f:
                _, blocks, _ = rh.parse_note(f.read())
            used |= {x.data.get("id") for x in blocks if isinstance(x.data, dict)}
    except (OSError, UnicodeDecodeError, ValueError) as e:
        print(f"unreadable input: {e}", file=sys.stderr)
        return 2
    machine = None
    if a.kind == "machine_fact":
        machine = {"tool": a.tool, "tool_version": a.tool_version, "check": a.check, "options": a.options}
        if a.complete is not None:
            machine["complete"] = a.complete
        machine = {k: v for k, v in machine.items() if v is not None}
    try:
        new, block, after = cite(text, rows, used, at=a.at, decl=a.decl, kind=a.kind, module=a.module,
                                 lines=a.lines, reader=a.reader, date=a.date, needs=a.needs, item=a.item,
                                 row=a.row, col=a.col, machine=machine, second_readers=a.second_reader)
        shown = None
        if a.src is not None and a.lines is not None:
            sp = os.path.join(a.src, block["file"])
            if not os.path.isfile(sp):
                raise Refused("SRC-MISSING", f"{block['file']} is not a file under the --src root")
            with open(sp, encoding="utf-8") as f:
                src_lines = f.read().splitlines()
            if a.lines[1] > len(src_lines):
                raise Refused("SRC-RANGE", f"{block['file']} has {len(src_lines)} lines, the citation ends at "
                              f"{a.lines[1]}")
            shown = src_lines[a.lines[0] - 1:a.lines[1]]
    except Refused as e:
        print(f"REFUSED {e.code} {e.message}")
        return 5
    except PostConditionFailed as e:
        print(f"POST-CONDITION FAILED (a bug in note_cite; nothing written): {e}", file=sys.stderr)
        return 4
    if shown is not None:
        print(f"{block['file']} lines {a.lines[0]}-{a.lines[1]}, from the --src copy:")
        for k, l in enumerate(shown, a.lines[0]):
            print(f"  {k:>5} | {l}")
    print(rh.render_block(block))
    print(f"after line {after} of {os.path.basename(a.note)}")
    if a.write:
        d = os.path.dirname(os.path.abspath(a.note))
        fd, tmp = tempfile.mkstemp(dir=d, prefix=".note_cite.")
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
                f.write(new)
            os.replace(tmp, a.note)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise
        print(f"wrote {os.path.basename(a.note)}")
    else:
        print("dry run: nothing written (add --write)")
    return 0


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


def refused(code, fn):
    try:
        fn()
    except Refused as e:
        eq(e.code, code, "refusal code")
        return e
    raise AssertionError(f"expected REFUSED {code}, nothing was refused")


HDR = rh.render_header({"id": "15", "level": 2, "group": "g", "list_title": "T", "authors": ["H"], "readers": [],
                        "release": "r"})
FILES = ("## Files this note was written from\n\n| File | SHA-256 |\n|---|---|\n"
         "| `A/B.lean` (lines 2-9 read) | `00` |\n| `A/C.lean` | `00` |\n")
# line numbers:   1 heading, 2 header, 3 blank, 4-5 paragraph, 6 blank, 7-10 table (7 header, 8 sep, 9-10 body),
# 11 blank, 12-14 list (13 item two, 14 nested), 15 blank, 16-18 lean fence, 19 blank, 20 heading, 21 blank,
# 22-24 text fence, 25 blank, 26.. files section
NOTE = ("# 15. Title\n" + HDR + "\n\n"
        "A paragraph that cites `A/B.lean`,\nline 3.\n\n"
        "| x | y |\n|---|---|\n| r1 | s1 |\n| r2 | s2 |\n\n"
        "- item one\n- item two\n  nested\n\n"
        "```lean\ntheorem n : True := trivial\n```\n\n"
        "## A heading\n\n"
        "```text\nplain\n```\n\n" + FILES)
TSV = ["# decl_table.py | test", "module\tname\tkind\tfirst_line\tlast_line\tbasis",
       "A.B\tA.n\ttheorem\t2\t5\ttext-extent",
       "A.B\tA.dup\tdef\t7\t9\ttext-extent",
       "A.C\tA.dup\tdef\t1\t4\ttext-extent",
       "C.D\tC.m\tdef\t1\t3\ttext-extent"]


def R():
    return read_decls(TSV)


def ok_cite(text=NOTE, **kw):
    base = dict(at=4, decl="A.n", kind="reading", reader="Halley", date="2026-11-23")
    base.update(kw)
    used = base.pop("used", set())
    return cite(text, R(), used, **base)


@case("C1a", "a unique name resolves: decls [{module, name}] and file from the module")
def _():
    new, b, after = ok_cite()
    eq(b["decls"], [{"module": "A.B", "name": "A.n"}], "decls")
    eq(b["file"], "A/B.lean", "file")


@case("C1b", "an unknown name is UNRESOLVED")
def _():
    refused("UNRESOLVED", lambda: ok_cite(decl="A.zzz"))


@case("C1c", "a name in two modules is AMBIGUOUS and names both modules")
def _():
    e = refused("AMBIGUOUS", lambda: ok_cite(decl="A.dup"))
    if "A.B" not in e.message or "A.C" not in e.message:
        raise AssertionError(f"candidates not named: {e.message}")


@case("C1d", "--module picks one row; a module not among the rows is NOT-IN-MODULE")
def _():
    new, b, after = ok_cite(decl="A.dup", module="A.C")
    eq(b["decls"], [{"module": "A.C", "name": "A.dup"}], "decls")
    eq(b["file"], "A/C.lean", "file")
    refused("NOT-IN-MODULE", lambda: ok_cite(decl="A.dup", module="A.X"))


@case("C2a", "lines inside the extent are written as [a, b]")
def _():
    new, b, after = ok_cite(lines=(3, 5))
    eq(b["lines"], [3, 5], "lines")


@case("C2b", "lines crossing the declaration's end are OUTSIDE-EXTENT, naming the extent")
def _():
    e = refused("OUTSIDE-EXTENT", lambda: ok_cite(lines=(4, 6)))
    if "2" not in e.message or "5" not in e.message:
        raise AssertionError(f"extent not named: {e.message}")


@case("C2c", "no --lines: the block has no lines key")
def _():
    new, b, after = ok_cite()
    eq("lines" in b, False, "lines key")


@case("C3a", "a file not in the note's file table is NOT-IN-FILE-TABLE")
def _():
    refused("NOT-IN-FILE-TABLE", lambda: ok_cite(decl="C.m"))


@case("C3b", "a note with no file table is NO-FILE-TABLE")
def _():
    refused("NO-FILE-TABLE", lambda: ok_cite(text=NOTE.split("## Files")[0]))


@case("C4a", "at a paragraph line: inserted after the paragraph's last line")
def _():
    new, b, after = ok_cite(at=4)
    eq(after, 5, "after line")
    eq(new.split("\n")[5], rh.render_block(b), "line 6 is the comment")


@case("C4b", "a second anchor on the same element lands below the first, from any line of the run")
def _():
    one, b1, _ = ok_cite(at=4)
    two, b2, after = cite(one, R(), {b1["id"]}, at=6, decl="A.n", kind="reading", reader="H", date="d")
    ls = two.split("\n")
    eq(ls[5], rh.render_block(b1), "first anchor stays on line 6")
    eq(ls[6], rh.render_block(b2), "second anchor on line 7")
    eq(after, 6, "after line")


@case("C4c", "a blank line or a line past the end is NO-TARGET")
def _():
    refused("NO-TARGET", lambda: ok_cite(at=3))
    refused("NO-TARGET", lambda: ok_cite(at=999))


@case("C4d", "a heading or a non-lean fence is ORPHAN-TARGET; a lean fence is a target")
def _():
    refused("ORPHAN-TARGET", lambda: ok_cite(at=20))
    refused("ORPHAN-TARGET", lambda: ok_cite(at=23))
    new, b, after = ok_cite(at=17)
    eq(after, 18, "after the closing fence")


@case("C5a", "table: the body row holding --at; inserted after the table's last line")
def _():
    new, b, after = ok_cite(at=10)
    eq(b["row"], 2, "row")
    eq(after, 10, "after line")


@case("C5b", "table: the header line without --row is ROW-NEEDED; --row given there is used")
def _():
    refused("ROW-NEEDED", lambda: ok_cite(at=7))
    new, b, after = ok_cite(at=7, row=1)
    eq(b["row"], 1, "row")


@case("C5c", "table: a row above the body rows is ROW-RANGE, a col above the columns COL-RANGE")
def _():
    refused("ROW-RANGE", lambda: ok_cite(at=9, row=3))
    refused("COL-RANGE", lambda: ok_cite(at=9, col=3))
    new, b, after = ok_cite(at=9, col=2)
    eq((b["row"], b["col"]), (1, 2), "row, col")


@case("C5d", "list: the top-level item holding --at, a nested line giving its parent item")
def _():
    new, b, after = ok_cite(at=14)
    eq(b["item"], 2, "item")
    eq(after, 14, "after line")


@case("C5e", "list: an anchor line of the run without --item is ITEM-NEEDED; above nitems is ITEM-RANGE")
def _():
    one, b1, _ = ok_cite(at=12)
    refused("ITEM-NEEDED", lambda: cite(one, R(), {b1["id"]}, at=15, decl="A.n", kind="reading", reader="H", date="d"))
    refused("ITEM-RANGE", lambda: ok_cite(at=12, item=3))


@case("C5f", "--item on a paragraph is ITEM-NOT-LIST; --row on a list is ROW-NOT-TABLE")
def _():
    refused("ITEM-NOT-LIST", lambda: ok_cite(at=4, item=1))
    refused("ROW-NOT-TABLE", lambda: ok_cite(at=12, row=1))


@case("C6a", "a note with no header is NO-HEADER")
def _():
    refused("NO-HEADER", lambda: ok_cite(text=NOTE.replace(HDR + "\n", "")))


@case("C6b", "a note with two headers is SECOND-HEADER")
def _():
    refused("SECOND-HEADER", lambda: ok_cite(text=NOTE.replace(HDR, HDR + "\n" + HDR)))


@case("C6c", "a note with a malformed rh- line is NOT-CLEAN")
def _():
    refused("NOT-CLEAN", lambda: ok_cite(text=NOTE.replace("line 3.\n", "line 3.\n<!-- rh-block {oops -->\n")))


@case("C7", "the id is the next one for the note over every used id, holes not reused")
def _():
    new, b, after = ok_cite(used={"15.b01", "15.b07", "14.b09"})
    eq(b["id"], "15.b08", "id")


@case("C8a", "reading without a reader or without a date is MISSING-FIELD; no default is filled")
def _():
    refused("MISSING-FIELD", lambda: ok_cite(reader=None))
    refused("MISSING-FIELD", lambda: ok_cite(date=None))


@case("C8b", "not_read takes needs; a needs outside NEEDS is BAD-BLOCK")
def _():
    new, b, after = ok_cite(kind="not_read", needs="hand_read", reader=None, date=None)
    eq(b["needs"], "hand_read", "needs")
    refused("BAD-BLOCK", lambda: ok_cite(kind="not_read", needs="a hand read"))


@case("C8c", "machine_fact with complete false is BAD-BLOCK; with its four fields it is written")
def _():
    m = {"tool": "fieldsuses", "tool_version": "ec543cd", "check": "proofterm", "options": "", "complete": True}
    new, b, after = ok_cite(kind="machine_fact", machine=m)
    eq((b["tool"], b["complete"]), ("fieldsuses", True), "machine fields")
    refused("BAD-BLOCK", lambda: ok_cite(kind="machine_fact", machine=dict(m, complete=False)))


@case("C9a", "post-conditions: stripping the new note gives the old one; the block parses back canonical")
def _():
    new, b, after = ok_cite(at=10, second_readers=[{"reader": "Kepler", "date": "2026-11-24"}])
    eq(rh.strip_anchor_lines(new), rh.strip_anchor_lines(NOTE), "strip")
    _, blocks, probs = rh.parse_note(new)
    eq([x.data for x in blocks], [b], "blocks")
    eq(blocks[0].canonical, True, "canonical")
    eq(probs, [], "problems")


@case("C9b", "a CRLF note stays CRLF")
def _():
    crlf = NOTE.replace("\n", "\r\n")
    new, b, after = ok_cite(text=crlf)
    eq(new.count("\n"), new.count("\r\n"), "every line ending CRLF")
    eq(rh.strip_anchor_lines(new), rh.strip_anchor_lines(crlf), "strip")


def _tmp_tree(d):
    os.makedirs(os.path.join(d, "docs"))
    os.makedirs(os.path.join(d, "src", "A"))
    note = os.path.join(d, "docs", "15-x.md")
    with open(note, "w", encoding="utf-8", newline="") as f:
        f.write(NOTE)
    with open(os.path.join(d, "decls.tsv"), "w", encoding="utf-8") as f:
        f.write("\n".join(TSV) + "\n")
    with open(os.path.join(d, "src", "A", "B.lean"), "w", encoding="utf-8") as f:
        f.write("".join(f"line {i}\n" for i in range(1, 9)))
    return note, os.path.join(d, "decls.tsv")


def _run_main(args):
    import contextlib
    import io
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(args)
    return code, out.getvalue(), err.getvalue()


BASE_ARGS = ["--at", "4", "--decl", "A.n", "--kind", "reading", "--reader", "Halley", "--date", "2026-11-23"]


@case("X1", "a dry run prints the comment and the line, exit 0, file unchanged")
def _():
    with tempfile.TemporaryDirectory() as d:
        note, tsv = _tmp_tree(d)
        code, out, err = _run_main([note, tsv] + BASE_ARGS)
        eq(code, 0, f"exit ({err})")
        if "<!-- rh-block " not in out or "after line 5" not in out:
            raise AssertionError(f"output: {out!r}")
        eq(open(note, encoding="utf-8", newline="").read(), NOTE, "file unchanged")


@case("X2", "--write writes the note and says so")
def _():
    with tempfile.TemporaryDirectory() as d:
        note, tsv = _tmp_tree(d)
        code, out, err = _run_main([note, tsv] + BASE_ARGS + ["--write"])
        eq(code, 0, f"exit ({err})")
        new = open(note, encoding="utf-8", newline="").read()
        eq(rh.strip_anchor_lines(new), rh.strip_anchor_lines(NOTE), "strip of the written note")
        if "wrote" not in out:
            raise AssertionError(f"output: {out!r}")


@case("X3", "--src prints the cited lines; a short file is SRC-RANGE, a missing one SRC-MISSING; refusals exit 5")
def _():
    with tempfile.TemporaryDirectory() as d:
        note, tsv = _tmp_tree(d)
        src = os.path.join(d, "src")
        code, out, err = _run_main([note, tsv] + BASE_ARGS + ["--lines", "3-4", "--src", src])
        eq(code, 0, f"exit ({err})")
        if "    3 | line 3" not in out or "    4 | line 4" not in out or "| line 5" in out:
            raise AssertionError(f"cited lines: {out!r}")
        os.remove(os.path.join(src, "A", "B.lean"))
        code, out, err = _run_main([note, tsv] + BASE_ARGS + ["--lines", "3-4", "--src", src])
        eq((code, out.split(" ")[:2]), (5, ["REFUSED", "SRC-MISSING"]), "missing")
        with open(os.path.join(src, "A", "B.lean"), "w", encoding="utf-8") as f:
            f.write("one\n")
        code, out, err = _run_main([note, tsv] + BASE_ARGS + ["--lines", "3-4", "--src", src])
        eq((code, out.split(" ")[:2]), (5, ["REFUSED", "SRC-RANGE"]), "short")


@case("X4", "usage errors exit 2: reversed --lines, an unreadable decls file")
def _():
    with tempfile.TemporaryDirectory() as d:
        note, tsv = _tmp_tree(d)
        code, out, err = _run_main([note, tsv] + BASE_ARGS + ["--lines", "5-3"])
        eq(code, 2, "reversed lines")
        code, out, err = _run_main([note, os.path.join(d, "nope.tsv")] + BASE_ARGS)
        eq(code, 2, "missing decls")


def _run_cases(cases, write):
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
    print("# cases range over: resolution (C1), extents (C2), the file table (C3), placement (C4), tables and lists (C5),")
    print("# the note's own state (C6), ids (C7), required fields and the format check (C8), post-conditions and line")
    print("# endings (C9), the command line (X1-X4). Fixtures are a 30-line note and a 4-row table written here.")
    return _run_cases(_CASES, print)


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        sys.exit(selftest())
    sys.exit(main())
