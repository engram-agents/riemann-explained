#!/usr/bin/env python3
"""The declaration table of the proof map: one row per named declaration, from the source text only.

Nothing is compiled. The rows are what the text rule of `lean_decls.parse_decls` finds: a declaration keyword at a
line start (after attributes and modifiers), its full name with the enclosing `namespace` names applied, and the
extent from the keyword line to the line before the next boundary line.

Outputs under OUT_DIR (each starts with one `#` provenance line, then the column row):
  decls.tsv      module, name, kind, first_line, last_line, basis
  decls_dup.tsv  the same columns; every row whose (module, name) pair occurs more than once
Columns: module = dotted module name (path under SRC_ROOT, the rule scan_graph.walk_lean uses); name = the full
name; kind = the declaring keyword (theorem, lemma, def, abbrev, structure, class, inductive, instance);
first_line = the 1-based keyword line; last_line = the 1-based last line of the text extent; basis is always
`text-extent`: the row is the text rule's extent, NOT Lean's.
Rows are sorted by (module, first_line as a number, name, kind), so the output does not depend on the order the
files were walked or on PYTHONHASHSEED.
Stdout is two lines, printed whenever the tree was read, also when the exit is 1 for an undecodable or unreadable
file. A run with no `.lean` file prints the `CHECKED NOTHING` line, then the stale-files line when OUT_DIR holds output of
an earlier run (STALE1); exit 2 prints nothing to stdout:
  files N  declarations N  pairs unique U  pairs not unique D (rows R)  undecodable K
  not rows (counted lines): example E  instance without a name I
U = distinct (module, name) pairs that occur once; D = distinct pairs that occur more than once; R = rows in
decls_dup.tsv. The second line counts lines that are NOT rows: `example` lines at column 0 (comments masked, with
optional attributes and modifiers) and `instance` lines that carry no name.

CONTRACT
 T1 Every `.lean` file is read once. A file that does not decode (`UNDECODABLE <relpath>`) or cannot be read at all
    (`UNREADABLE <relpath>`) is reported by path on stderr and counted in `undecodable`; the run still writes every
    other file's rows; the exit code is 1. No `.lean` file under SRC_ROOT: `CHECKED NOTHING: no .lean file under
    SRC_ROOT` on stdout (a stale-files line may follow, STALE1), exit 1, no table written. A usage error or a SRC_ROOT that is not a directory: exit 2. A
    failing self-test: exit 4, nothing else reported. Exit 0 otherwise, INCLUDING when duplicate pairs exist.
    Cases T1a T1b T1c T1d T1e T1f T1g EXIT4 (exit 0 with duplicates: T2a).
 T2 A (module, name) pair that occurs more than once is written, all of its rows, in decls.tsv AND in
    decls_dup.tsv, never one picked; the summary counts unique and non-unique pairs. The same name in two modules
    is not a duplicate. The pair ignores the kind: a `def x` and a `theorem x` in one module are a duplicate.
    Cases T2a T2b T2c T2d.
 T3 The extent is the text rule's. It starts at the keyword line and ends at the line before the next boundary
    line, so it can include trailing blank lines and plain comment lines. A doc comment (`/-` at column 0) that
    precedes the NEXT declaration is outside the extent; a declaration's own doc comment above it and an attribute
    on its own line above it are not part of its extent; first_line is the keyword line. The `#` line says the
    extent is a text extent, NOT Lean's. The extent of the last declaration in a file ends at the file's last
    physical line (parse_decls' end_idx is one larger when the file ends in a newline; last_line is clamped to
    the line count as an editor shows it). Cases T3a T3b T3c T3d T3e EOF1 EOF2 EOF3 EOF4 EOF5.
 T4 A declaration inside a block comment, nested ones included, does not appear. Cases T4a T4b.
 T5 Names: inside `namespace A.B`, `theorem x` is `A.B.x`; `end B` closes only B (a later declaration in the same
    block is `A.y`); `_root_.x` is `x`; a `section S` adds no prefix. (This is parse_decls' behaviour, pinned here
    through the table.) Cases T5a T5b T5c.
 T6 `private`, `protected`, `noncomputable` and the other modifiers: the declaration appears under its written
    name and its kind is the declaring keyword. Cases T6a.
 T7 Nameless `instance` and `example` lines are not rows and are counted on the second summary line. Cases T7a T7b T7c.
 T8 Determinism: two runs under different PYTHONHASHSEED values, and a tree whose files were created in another
    order, give byte-identical decls.tsv and decls_dup.tsv. Cases T8a T8b.
 T9 Files are read once: `run(root, out, reader=...)` takes the function that reads a file (default
    scan_graph.read_text); a counting reader sees exactly one call per file. Case T9a.
 Line endings and module names: a `\r\n` or lone `\r` file reads like a `\n` one (CRLF1 CRLF2 CRLF3); the module
 column is the whole dotted path (MOD1); a leading byte-order mark is BOM1.
 Every row has the six tab-separated fields, none empty; the column row is exact (COL1); rows are sorted (SORT1,
 SORT2);
 `--selftest --only ID,ID` runs exactly the named cases and an unknown id exits 2 (SEL1).
 With --selftest the tool plants temporary trees, checks each contract line as its own CASE (each with its own
 planted tree and a control that resolves), prints one `CASE <id> PASS|FAIL` line each and a final
 `SELFTEST PASS|FAIL`; exit 0 or 4. The total with zero skips is for a non-root run: T1d skips as root, where a
 mode-000 file stays readable. A normal run does the same quietly first and refuses (exit 4, nothing else
 reported) if it fails.

LIMIT. A run that checks nothing (no `.lean` file) writes nothing, so an output file left in OUT_DIR by an earlier run is
still there, and a tool that reads OUT_DIR next cannot tell it from this run's; the run names such files on stdout
(STALE1) and keeps exit 1, it does not delete them.
A row is the text rule's extent of a named declaration. It is not Lean's extent and it does not say the
declaration is used or compiled. A block comment at column 0 after the last declaration is a boundary, so it is
outside the extent (EOF5). A declaration inside a block comment
is not read; one inside a string literal is (strings are not special-cased when comments are masked). A keyword
line that is indented is read like one at column 0 (parse_decls does not look at the indent), so an indented
`theorem` inside a `where` block or a tactic block is a row. Names come from the text: a `private` declaration is
not given Lean's mangled name, a name made by a macro or a structure field is not seen, and `open`, `export` and
aliases are not modelled. A `variable`, `open` or `set_option` line ends the extent of the declaration above it. Line endings `\r\n` (and a
lone `\r`) are handled because the shared reader translates them to `\n` before the text rule runs (CRLF1-3). A
UTF-8 byte-order mark at the start of a file hides a declaration on that first line (the rule is inherited from
the moved parse_decls; BOM1 records it; none was found in the release read, a later release must be checked).
`mutual` and `noncomputable section` push a scope entry like `section`. The pair test is on the written full name:
two `private` declarations with one name in one module are listed as a duplicate although Lean tells them apart.

usage: decl_table.py SRC_ROOT OUT_DIR
       decl_table.py --selftest
"""

import sys
if sys.version_info[:2] < (3, 12):
    raise SystemExit("decl_table.py: needs Python 3.12 or newer (tested with 3.12); this is %d.%d.%d at %s" % (sys.version_info[0], sys.version_info[1], sys.version_info[2], sys.executable))

import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scan_graph import (_SkipCase, _plant, _plant_unreadable, _table, failure_word,  # noqa: E402
                        mask_comments, provenance, read_text, report_stale_output, walk_lean)
from lean_decls import DECL, parse_decls  # noqa: E402

COLS = ["module", "name", "kind", "first_line", "last_line", "basis"]
BASIS = "text-extent"
EXAMPLE = re.compile(r"^(?:@\[[^\]\n]*\][ \t]*)*(?:(?:private|protected|noncomputable|nonrec|unsafe|partial)[ \t]+)*"
                     r"example\b", re.M)


# ---------------------------------------------------------------- the tool

def _nameless_instance(line):
    """True for a line parse_decls skips because its `instance` carries no name."""
    m = DECL.match(line)
    return bool(m) and m.group(1) == "instance" and not m.group(2).rstrip(".")


def _physical_lines(text):
    """Lines as an editor shows them: a final newline does not start a new line, a last partial line counts, an
    empty text has none."""
    return text.count("\n") + (0 if text == "" or text.endswith("\n") else 1)


def _write(path, prov, rows):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(prov + "\n" + "\t".join(COLS) + "\n")
        for r in rows:
            f.write("\t".join(map(str, r)) + "\n")


def run(root, out, reader=None):
    read = read_text if reader is None else reader
    root = root.rstrip(os.sep) or root
    if not os.path.isdir(root):
        print(f"SRC_ROOT is not a directory: {root}", file=sys.stderr)
        return 2
    mods = walk_lean(root)
    if not mods:
        print("CHECKED NOTHING: no .lean file under SRC_ROOT")
        report_stale_output(out, ("decls.tsv", "decls_dup.tsv"))
        return 1
    rows, bad, n_example, n_instance = [], 0, 0, 0
    for module, path in mods:
        text, ok = read(path)
        if not ok:
            bad += 1
            print(failure_word(path), os.path.relpath(path, root).replace(os.sep, "/"), file=sys.stderr)
            continue
        masked = mask_comments(text)
        last_physical = _physical_lines(text)
        for line_no, kind, full, end_idx, _ns in parse_decls(text, masked):
            rows.append((module, full, kind, line_no, min(end_idx, last_physical), BASIS))
        n_example += len(EXAMPLE.findall(masked))
        n_instance += sum(1 for ln in masked.split("\n") if _nameless_instance(ln))
    rows.sort(key=lambda r: (r[0], r[3], r[1], r[2]))
    seen = {}
    for r in rows:
        seen[(r[0], r[1])] = seen.get((r[0], r[1]), 0) + 1
    dup = [r for r in rows if seen[(r[0], r[1])] > 1]
    n_dup_pairs = sum(1 for c in seen.values() if c > 1)
    prov = provenance("decl_table.py", root, "a row is the TEXT RULE's extent of a named declaration (a text extent, NOT "
                      "Lean's extent); it does not say the declaration is used or compiled")
    os.makedirs(out, exist_ok=True)
    _write(os.path.join(out, "decls.tsv"), prov, rows)
    _write(os.path.join(out, "decls_dup.tsv"), prov, dup)
    print(f"files {len(mods)}  declarations {len(rows)}  pairs unique {len(seen) - n_dup_pairs}  "
          f"pairs not unique {n_dup_pairs} (rows {len(dup)})  undecodable {bad}")
    print(f"not rows (counted lines): example {n_example}  instance without a name {n_instance}")
    return 1 if bad else 0


# ---------------------------------------------------------------- self-test

def _go(files, prep=None, reader=None):
    """(exit code, stdout, stderr, {"decls": table, "dup": table}) for a fresh planted tree; a table is
    (lines, columns, rows as dicts), empty when the file was not written."""
    with tempfile.TemporaryDirectory() as d:
        root, out = os.path.join(d, "src"), os.path.join(d, "out")
        os.makedirs(root)
        _plant(root, files)
        if prep:
            prep(root)
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = run(root, out, reader=reader) if reader else run(root, out)
        tabs = {}
        for key, name in (("decls", "decls.tsv"), ("dup", "decls_dup.tsv")):
            p = os.path.join(out, name)
            tabs[key] = _table(p) if os.path.isfile(p) else ([], [], [])
        return rc, buf.getvalue(), err.getvalue(), tabs


def _eq(actual, expected):
    return actual == expected, f"expected {expected!r}, got {actual!r}"


def _names(tabs, key="decls"):
    return [r["name"] for r in tabs[key][2]]


def _extents(tabs, key="decls"):
    return [(r["name"], r["first_line"], r["last_line"]) for r in tabs[key][2]]


def _sum(out):
    """The two summary lines as numbers: {"files": N, "declarations": N, "unique": U, "dup": D, "dup_rows": R,
    "undecodable": K, "example": E, "instance": I}, or {} when a line is missing."""
    m1 = re.search(r"^files (\d+)  declarations (\d+)  pairs unique (\d+)  pairs not unique (\d+) \(rows (\d+)\)  "
                   r"undecodable (\d+)$", out, re.M)
    m2 = re.search(r"^not rows \(counted lines\): example (\d+)  instance without a name (\d+)$", out, re.M)
    if not (m1 and m2):
        return {}
    k = ["files", "declarations", "unique", "dup", "dup_rows", "undecodable"]
    got = dict(zip(k, map(int, m1.groups())))
    got.update(example=int(m2.group(1)), instance=int(m2.group(2)))
    return got


def _read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def _run_child(root, out, seed):
    """One run of this module's `run` in a child interpreter under the given PYTHONHASHSEED. (The self-test is not
    run: `main` would start it again, and PYTHONHASHSEED is ignored under -I.)"""
    code = "import sys; sys.path.insert(0, sys.argv[3]); import decl_table; sys.exit(decl_table.run(sys.argv[1], sys.argv[2]))"
    here = os.path.dirname(os.path.abspath(__file__))
    r = subprocess.run([sys.executable, "-c", code, root, out, here], capture_output=True, text=True, timeout=120,
                       env=dict(os.environ, PYTHONHASHSEED=str(seed)))
    return r.returncode


def _selftest_cases():
    cases = []

    def case(cid, desc):
        def deco(fn):
            cases.append((cid, desc, fn))
            return fn
        return deco

    # ---- T1: exit codes, nothing skipped silently
    @case("T1a", "a non-UTF-8 file: UNDECODABLE <relpath> on stderr, counted, exit 1, the other file's rows still written; "
                 "control: the same tree without it is exit 0 and undecodable 0")
    def _():
        good = {"Good.lean": "theorem g : True := trivial\n"}
        rc, out, err, tabs = _go({**good, "sub/Bad.lean": b"theorem b : True := trivial\n\xff\n"})
        rc0, out0, err0, tabs0 = _go(good)
        got = (rc, "UNDECODABLE sub/Bad.lean" in err.splitlines(), _sum(out).get("undecodable"), _sum(out).get("files"),
               _names(tabs), rc0, err0, _sum(out0).get("undecodable"), _names(tabs0))
        return _eq(got, (1, True, 1, 2, ["g"], 0, "", 0, ["g"]))

    @case("T1b", "no .lean file under SRC_ROOT: `CHECKED NOTHING: no .lean file under SRC_ROOT`, exit 1, no table written; "
                 "control: one .lean file added is exit 0")
    def _():
        rc, out, _e, tabs = _go({"readme.txt": "x"})
        rc1, _o, _e1, tabs1 = _go({"readme.txt": "x", "A.lean": "theorem a : True := trivial\n"})
        got = (rc, "CHECKED NOTHING: no .lean file under SRC_ROOT" in out.splitlines(), tabs["decls"][0], rc1, _names(tabs1))
        return _eq(got, (1, True, [], 0, ["a"]))

    @case("T1c", "usage error (wrong number of arguments) and a SRC_ROOT that is not a directory: exit 2 with a message; "
                 "control: a real directory is exit 0")
    def _():
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "src"))
            _plant(os.path.join(d, "src"), {"A.lean": "theorem a : True := trivial\n"})
            err1, err2, err3 = io.StringIO(), io.StringIO(), io.StringIO()
            with contextlib.redirect_stderr(err1), contextlib.redirect_stdout(io.StringIO()):
                rc_usage = main(["decl_table.py"])
            with contextlib.redirect_stderr(err2), contextlib.redirect_stdout(io.StringIO()):
                rc_nodir = run(os.path.join(d, "nope"), os.path.join(d, "out"))
            with contextlib.redirect_stderr(err3), contextlib.redirect_stdout(io.StringIO()):
                rc_ok = run(os.path.join(d, "src"), os.path.join(d, "out"))
        return _eq((rc_usage, bool(err1.getvalue().strip()), rc_nodir, bool(err2.getvalue().strip()), rc_ok),
                   (2, True, 2, True, 0))

    @case("T1d", "an unreadable .lean file (mode 000): UNREADABLE <relpath> on stderr, counted, exit 1, the other file's "
                 "rows written (SKIPPED when the permission bits cannot make a file unreadable, e.g. as root)")
    def _():
        def prep(root):
            p = os.path.join(root, "sub", "X.lean")
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w") as f:
                f.write("theorem x : True := trivial\n")
            os.chmod(p, 0)
            try:
                open(p).close()
            except OSError:
                return
            raise _SkipCase("mode 000 does not make a file unreadable here (running as root?)")
        rc, out, err, tabs = _go({"Good.lean": "theorem g : True := trivial\n"}, prep=prep)
        return _eq((rc, "UNREADABLE sub/X.lean" in err.splitlines(), _sum(out).get("undecodable"), _names(tabs)),
                   (1, True, 1, ["g"]))

    @case("T1e", "a dangling symlink named *.lean: UNREADABLE <relpath> on stderr, counted, exit 1, the other file's rows written")
    def _():
        rc, out, err, tabs = _go({"Good.lean": "theorem g : True := trivial\n"},
                                 prep=lambda root: _plant_unreadable(root, "sub/X.lean"))
        return _eq((rc, "UNREADABLE sub/X.lean" in err.splitlines(), _sum(out).get("undecodable"), _names(tabs)),
                   (1, True, 1, ["g"]))

    @case("EXIT4", "a failing self-test makes the real run exit 4 with REFUSED and writes nothing; control: a passing one "
                   "runs and exits 0")
    def _():
        real = globals()["selftest_quiet"]
        try:
            res = []
            for fake in (1, 0):
                globals()["selftest_quiet"] = lambda fake=fake: fake
                with tempfile.TemporaryDirectory() as d:
                    _plant(os.path.join(d, "src"), {"A.lean": "theorem a : True := trivial\n"})
                    err = io.StringIO()
                    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                        rc = main(["decl_table.py", os.path.join(d, "src"), os.path.join(d, "out")])
                    res.append((rc, "REFUSED" in err.getvalue(), os.path.isfile(os.path.join(d, "out", "decls.tsv"))))
        finally:
            globals()["selftest_quiet"] = real
        return _eq(res, [(4, True, False), (0, False, True)])

    # ---- T2: duplicates are kept, all of them
    @case("T2a", "the same (module, name) twice in one file: both rows in decls.tsv and in decls_dup.tsv, `pairs not unique 1 "
                 "(rows 2)`, exit 0")
    def _():
        rc, out, _e, tabs = _go({"A.lean": "def t := 1\ndef t := 2\ndef u := 3\nend\n"})
        s = _sum(out)
        got = (rc, [(r["name"], r["first_line"]) for r in tabs["decls"][2]], [(r["name"], r["first_line"]) for r in tabs["dup"][2]],
               (s.get("unique"), s.get("dup"), s.get("dup_rows"), s.get("declarations")))
        return _eq(got, (0, [("t", "1"), ("t", "2"), ("u", "3")], [("t", "1"), ("t", "2")], (1, 1, 2, 3)))

    @case("T2b", "the same name in two files (two modules) is NOT a duplicate: `pairs not unique 0 (rows 0)`, decls_dup.tsv "
                 "empty; control for T2a")
    def _():
        rc, out, _e, tabs = _go({"A.lean": "def t := 1\n", "B.lean": "def t := 1\n"})
        s = _sum(out)
        got = (rc, [(r["module"], r["name"]) for r in tabs["decls"][2]], tabs["dup"][2],
               tabs["dup"][1] == ["module", "name", "kind", "first_line", "last_line", "basis"],
               (s.get("unique"), s.get("dup"), s.get("dup_rows")))
        return _eq(got, (0, [("A", "t"), ("B", "t")], [], True, (2, 0, 0)))

    @case("T2c", "a pair three times: all three rows in both tables, `pairs not unique 1 (rows 3)`, never one picked")
    def _():
        rc, out, _e, tabs = _go({"A.lean": "def t := 1\ndef t := 2\ntheorem t : True := trivial\ndef w := 1\nend\n"})
        s = _sum(out)
        got = (rc, [(r["name"], r["kind"], r["first_line"]) for r in tabs["dup"][2]], (s.get("unique"), s.get("dup"), s.get("dup_rows")))
        return _eq(got, (0, [("t", "def", "1"), ("t", "def", "2"), ("t", "theorem", "3")], (1, 1, 3)))

    @case("T2d", "a pair is (module, name): a `def x` and a `theorem x` in one module are a duplicate; control: different names are not")
    def _():
        rc, out, _e, tabs = _go({"A.lean": "def x := 1\ntheorem x : True := trivial\nend\n",
                                 "B.lean": "def p := 1\ntheorem q : True := trivial\nend\n"})
        s = _sum(out)
        got = ([(r["module"], r["name"], r["kind"]) for r in tabs["dup"][2]], (s.get("unique"), s.get("dup"), s.get("dup_rows")))
        return _eq(got, ([("A", "x", "def"), ("A", "x", "theorem")], (2, 1, 2)))

    # ---- T3: the text extent
    @case("T3a", "a declaration followed by the doc comment of the next one: the first extent ends before the `/--` line; "
                 "control: a plain `--` line in the same place stays inside the extent")
    def _():
        _rc, _o, _e, tabs = _go({"Doc.lean": "def a := 1\n/-- about b -/\ndef b := 2\nend\n",
                                 "Plain.lean": "def a := 1\n-- about b\ndef b := 2\nend\n"})
        got = [(r["module"], r["name"], r["first_line"], r["last_line"]) for r in tabs["decls"][2]]
        return _eq(got, [("Doc", "a", "1", "1"), ("Doc", "b", "3", "3"), ("Plain", "a", "1", "2"), ("Plain", "b", "3", "3")])

    @case("T3b", "two declarations on adjacent lines: the first one's last line is its own line, the second starts on the next")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "def a := 1\ndef b := 2\nend\n"})
        return _eq(_extents(tabs), [("a", "1", "1"), ("b", "2", "2")])

    @case("T3c", "trailing blank lines and a `--` comment line after a declaration, then `end N`: last_line includes them. "
                 "This pins the TEXT rule (the extent runs to the next boundary line), not Lean's extent. Control: without them it is the keyword line")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "namespace N\ntheorem t : True := trivial\n\n-- a note\n\nend N\n",
                                 "B.lean": "namespace N\ntheorem t : True := trivial\nend N\n"})
        got = [(r["module"], r["first_line"], r["last_line"]) for r in tabs["decls"][2]]
        return _eq(got, [("A", "2", "5"), ("B", "2", "2")])

    @case("T3d", "a declaration's own doc comment and an `@[simp]` line above it are not in its extent and first_line is the keyword "
                 "line; control: an attribute on the keyword's own line starts there")
    def _():
        _rc, _o, _e, tabs = _go({"Above.lean": "def p := 1\n/-- own doc -/\n@[simp]\ntheorem t : True := trivial\nend\n",
                                 "Same.lean": "def p := 1\n@[simp] theorem t : True := trivial\nend\n"})
        got = [(r["module"], r["name"], r["first_line"], r["last_line"]) for r in tabs["decls"][2]]
        return _eq(got, [("Above", "p", "1", "1"), ("Above", "t", "4", "4"), ("Same", "p", "1", "1"), ("Same", "t", "2", "2")])

    @case("T3e", "the `#` first line names the extent a text extent and NOT Lean's, and names the tool; the column row follows")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "def a := 1\n"})
        lines = tabs["decls"][0]
        ok = (len(lines) > 1 and lines[0].startswith("# decl_table.py | source: ") and "text extent" in lines[0]
              and "NOT Lean" in lines[0] and lines[1] == "module\tname\tkind\tfirst_line\tlast_line\tbasis" and lines[0] == (tabs["dup"][0] or [""])[0])
        return ok, f"got {lines[:2]!r}, dup first line {(tabs['dup'][0] or [''])[0]!r}"

    def _ext(tabs):
        return [(r["module"], r["name"], r["first_line"], r["last_line"]) for r in tabs["decls"][2]]

    @case("EOF1", "the last declaration of a file WITH a final newline ends at the last physical line (2 lines: last_line 2, not 3); "
                  "control: the non-last declaration ends at the line before the next boundary")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "def a := 1\ndef b := 2\n"})
        return _eq(_ext(tabs), [("A", "a", "1", "1"), ("A", "b", "2", "2")])

    @case("EOF2", "the same file WITHOUT a final newline: the last declaration's last_line is its last line (2); control: the first one")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "def a := 1\ndef b := 2"})
        return _eq(_ext(tabs), [("A", "a", "1", "1"), ("A", "b", "2", "2")])

    @case("EOF3", "blank lines at the end of the file after the last declaration are inside its extent (the text rule, as in T3c): "
                  "last_line is the last physical blank line (4), not one past it; control: the first declaration")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "def a := 1\ndef b := 2\n\n\n"})
        return _eq(_ext(tabs), [("A", "a", "1", "1"), ("A", "b", "2", "4")])

    @case("EOF4", "a file whose last line is a declaration's keyword line with no newline: first_line = last_line; control: the "
                  "declaration above it, with blank lines between, ends at the line before the next boundary")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "def a := 1\n\n\ndef b := 2"})
        return _eq(_ext(tabs), [("A", "a", "1", "3"), ("A", "b", "4", "4")])

    @case("EOF5", "one declaration followed by a block comment at column 0 and nothing else: the comment starts a boundary, so the "
                  "extent is the keyword line only (last_line 1, pinned); control: a `--` line there stays inside it (last_line 2)")
    def _():
        _rc, _o, _e, tabs = _go({"Block.lean": "def a := 1\n/- note -/\n", "Line.lean": "def a := 1\n-- note\n"})
        return _eq(_ext(tabs), [("Block", "a", "1", "1"), ("Line", "a", "1", "2")])

    # ---- T4: comments
    @case("T4a", "a declaration inside a block comment does not appear; the real one after it does (control)")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "/-\ntheorem hidden : True := trivial\n-/\ntheorem real : True := trivial\nend\n"})
        return _eq(_names(tabs), ["real"])

    @case("T4b", "a nested block comment: a declaration after the INNER close, still inside the outer comment, does not appear; "
                 "the real one after the outer close does (control)")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "/- outer /- inner\ntheorem h1 : True := trivial\n-/ theorem h2 : True := trivial\n-/\n"
                                           "theorem real : True := trivial\nend\n"})
        return _eq(_names(tabs), ["real"])

    # ---- T5: names
    @case("T5a", "`namespace A.B`, `end B`, then a declaration: `A.B.x` then `A.y`")
    def _():
        _rc, _o, _e, tabs = _go({"M.lean": "namespace A.B\ntheorem x : True := trivial\nend B\ntheorem y : True := trivial\nend A\n"})
        return _eq(_names(tabs), ["A.B.x", "A.y"])

    @case("T5b", "`_root_.x` inside a namespace is `x`; control: the plain name beside it gets the prefix")
    def _():
        _rc, _o, _e, tabs = _go({"M.lean": "namespace N\ntheorem _root_.x : True := trivial\ntheorem z : True := trivial\nend N\n"})
        return _eq(_names(tabs), ["x", "N.z"])

    @case("T5c", "a `section S` adds no prefix: named and anonymous sections inside a namespace and at the top level")
    def _():
        _rc, _o, _e, tabs = _go({"M.lean": "namespace N\nsection S\ntheorem a : True := trivial\nend S\nsection\n"
                                           "theorem b : True := trivial\nend\ntheorem c : True := trivial\nend N\n",
                                 "T.lean": "section S\ntheorem q : True := trivial\nend S\n"})
        return _eq([(r["module"], r["name"]) for r in tabs["decls"][2]], [("M", "N.a"), ("M", "N.b"), ("M", "N.c"), ("T", "q")])

    # ---- T6: modifiers
    @case("T6a", "`private theorem`, `protected def`, `noncomputable def`: the written name, the declaring keyword as kind")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "private theorem p : True := trivial\nprotected def q := 1\nnoncomputable def r := 1\nend\n"})
        return _eq([(r["name"], r["kind"]) for r in tabs["decls"][2]], [("p", "theorem"), ("q", "def"), ("r", "def")])

    # ---- T7: lines that are not rows
    @case("T7a", "nameless instance and example lines are no rows and are counted on the second summary line; a named instance "
                 "is a row; an `example` inside a block comment is not counted")
    def _():
        src = ("instance : Inhabited Nat := ⟨0⟩\n"
               "example : True := trivial\n"
               "instance named : Inhabited Bool := ⟨true⟩\n"
               "private example : True := trivial\n"
               "@[simp] example : 1 = 1 := rfl\n"
               "instance (n : Nat) : Inhabited Nat := ⟨n⟩\n"
               "/-\nexample : True := trivial\n-/\n"
               "end\n")
        rc, out, _e, tabs = _go({"A.lean": src})
        s = _sum(out)
        return _eq((rc, [(r["name"], r["kind"]) for r in tabs["decls"][2]], s.get("example"), s.get("instance"), s.get("declarations")),
                   (0, [("named", "instance")], 3, 2, 1))

    # ---- T8: determinism
    DET = {f"M{i % 3}/F{i}.lean": f"def a{i} := 1\ndef a{i} := 2\ndef b{i} := 3\n" for i in range(12)}

    @case("T8a", "two runs under different PYTHONHASHSEED values give byte-identical decls.tsv and decls_dup.tsv (twelve duplicate pairs)")
    def _():
        got = []
        for seed in (1, 2):
            with tempfile.TemporaryDirectory() as d:
                root, out = os.path.join(d, "src"), os.path.join(d, "out")
                os.makedirs(root)
                _plant(root, DET)
                rc = _run_child(root, out, seed)
                got.append((rc, _read_bytes(os.path.join(out, "decls.tsv")) if os.path.isfile(os.path.join(out, "decls.tsv")) else None,
                            _read_bytes(os.path.join(out, "decls_dup.tsv")) if os.path.isfile(os.path.join(out, "decls_dup.tsv")) else None))
        (rc1, d1, u1), (rc2, d2, u2) = got
        ok = rc1 == rc2 == 0 and d1 is not None and u1 is not None and d1 == d2 and u1 == u2 and d1.count(b"\n") > 30
        return ok, f"exit {rc1}/{rc2}, decls equal {d1 == d2}, dup equal {u1 == u2}"

    @case("T8b", "a tree whose files were created in the reverse order gives byte-identical decls.tsv and decls_dup.tsv")
    def _():
        got = []
        for order in (list(DET), list(reversed(DET))):
            with tempfile.TemporaryDirectory() as d:
                root, out = os.path.join(d, "src"), os.path.join(d, "out")
                os.makedirs(root)
                for rel in order:
                    _plant(root, {rel: DET[rel]})
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                    rc = run(root, out)
                paths = [os.path.join(out, n) for n in ("decls.tsv", "decls_dup.tsv")]
                got.append((rc, [_read_bytes(p) if os.path.isfile(p) else None for p in paths]))
        ok = got[0][0] == got[1][0] == 0 and got[0][1] == got[1][1] and None not in got[0][1] and got[0][1][0].count(b"\n") > 30
        return ok, f"exit {got[0][0]}/{got[1][0]}, tables equal {got[0][1] == got[1][1]}"

    # ---- T9: one read per file
    @case("T9a", "a counting reader passed to run sees exactly one call per .lean file (one of them undecodable)")
    def _():
        calls = []

        def reader(path):
            calls.append(os.path.basename(path))
            return read_text(path)
        rc, _o, _e, tabs = _go({"A.lean": "def a := 1\n", "sub/B.lean": "def b := 1\n", "C.lean": b"def c := 1\n\xff\n"}, reader=reader)
        return _eq((rc, sorted(calls), _names(tabs)), (1, ["A.lean", "B.lean", "C.lean"], ["a", "b"]))

    # ---- T1f, T1g: what stdout holds on the two exits that print no summary
    @case("T1f", "no .lean file: stdout is exactly the one line `CHECKED NOTHING: no .lean file under SRC_ROOT` when OUT_DIR holds no old output (no summary line; STALE1 covers the stale-files line that may follow), "
                 "nothing on stderr; control: one .lean file prints the two summary lines")
    def _():
        rc, out, err, _t = _go({"readme.txt": "x"})
        rc1, out1, _e1, _t1 = _go({"A.lean": "def a := 1\n"})
        return _eq((rc, out, err, rc1, out1.count("\n")), (1, "CHECKED NOTHING: no .lean file under SRC_ROOT\n", "", 0, 2))

    @case("STALE1", "no .lean file and OUT_DIR already holds output of an earlier run: the message names those files and says this run "
                    "wrote nothing, exit 1, the old files untouched; only the files present are named; control: a fresh OUT_DIR "
                    "gets the CHECKED NOTHING line alone")
    def _():
        nothing = "CHECKED NOTHING: no .lean file under SRC_ROOT"
        got = []
        for planted in (('decls.tsv', 'decls_dup.tsv'), ('decls_dup.tsv',), ()):
            with tempfile.TemporaryDirectory() as d:
                root, out = os.path.join(d, "src"), os.path.join(d, "out")
                os.makedirs(root)
                os.makedirs(out)
                for n in planted:
                    with open(os.path.join(out, n), "w", encoding="utf-8", newline="\n") as f:
                        f.write("old\n")
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = run(root, out)
                kept = [open(os.path.join(out, n), encoding="utf-8").read() for n in planted]
                got.append((rc, buf.getvalue().splitlines(), kept, sorted(os.listdir(out)) == sorted(planted)))
        return _eq(got, [
            (1, [nothing, 'OUT_DIR holds files from an earlier run: decls.tsv, decls_dup.tsv; this run wrote nothing'], ["old\n"] * 2, True),
            (1, [nothing, 'OUT_DIR holds files from an earlier run: decls_dup.tsv; this run wrote nothing'], ["old\n"], True),
            (1, [nothing], [], True)])

    @case("T1g", "SRC_ROOT not a directory (exit 2): nothing on stdout, a message on stderr; control: a directory prints the summary")
    def _():
        with tempfile.TemporaryDirectory() as d:
            os.makedirs(os.path.join(d, "src"))
            _plant(os.path.join(d, "src"), {"A.lean": "def a := 1\n"})
            res = []
            for root in (os.path.join(d, "nope"), os.path.join(d, "src")):
                o, e = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                    rc = run(root, os.path.join(d, "out"))
                res.append((rc, o.getvalue() != "", bool(e.getvalue().strip())))
        return _eq(res, [(2, False, True), (0, True, False)])

    # ---- line endings, the byte-order mark, module names
    CRLF = "namespace N\r\ntheorem a : True := trivial\r\nend N\r\ntheorem b : True := trivial"

    @case("CRLF1", "a file with `\\r\\n` line endings and a final `\\r\\n`: `end N` closes the namespace, so a is `N.a` (2,2) and b is `b` "
                   "(4,4); pinned: the shared reader translates the newlines")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": (CRLF + "\r\n").encode("utf-8")})
        return _eq([(r["name"], r["first_line"], r["last_line"]) for r in tabs["decls"][2]], [("N.a", "2", "2"), ("b", "4", "4")])

    @case("CRLF2", "the same file without the final `\\r\\n`: the same rows; control: the same text with `\\n` endings")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": CRLF.encode("utf-8"), "B.lean": CRLF.replace("\r\n", "\n").encode("utf-8")})
        return _eq([(r["module"], r["name"], r["first_line"], r["last_line"]) for r in tabs["decls"][2]],
                   [("A", "N.a", "2", "2"), ("A", "b", "4", "4"), ("B", "N.a", "2", "2"), ("B", "b", "4", "4")])

    @case("CRLF3", "a file with lone `\\r` line endings reads like `\\n` (the reader's universal newlines): the same rows, pinned")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": (CRLF.replace("\r\n", "\r") + "\r").encode("utf-8")})
        return _eq([(r["name"], r["first_line"], r["last_line"]) for r in tabs["decls"][2]], [("N.a", "2", "2"), ("b", "4", "4")])

    @case("BOM1", "a UTF-8 byte-order mark at the start of a file hides a declaration on that first line (the inherited rule, recorded); "
                  "the declaration on line 2 is a row (control)")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": b"\xef\xbb\xbftheorem z : True := trivial\ntheorem y : True := trivial\n"})
        return _eq([(r["name"], r["first_line"]) for r in tabs["decls"][2]], [("y", "2")])

    @case("MOD1", "the module column of a nested file is the whole dotted path: `A/B.lean` is `A.B`, `A/C/D.lean` is `A.C.D`")
    def _():
        _rc, _o, _e, tabs = _go({"A/B.lean": "def b := 1\n", "A/C/D.lean": "def d := 1\n"})
        return _eq([(r["module"], r["name"]) for r in tabs["decls"][2]], [("A.B", "b"), ("A.C.D", "d")])

    @case("SORT2", "the sort matters: `A.B.lean` and `A/B.lean` are both module `A.B` and are walked in path order, so the line-10 "
                   "declaration of the first would come before the line-2 declaration of the second; the table lists line 2 first")
    def _():
        _rc, _o, _e, tabs = _go({"A.B.lean": "\n" * 9 + "def late := 1\n", "A/B.lean": "\ndef early := 1\n"})
        return _eq([(r["module"], r["name"], r["first_line"]) for r in tabs["decls"][2]], [("A.B", "early", "2"), ("A.B", "late", "10")])

    @case("T7b", "a nameless `instance` inside a block comment is NOT counted; a real nameless one beside it is (control: count 1)")
    def _():
        src = "/-\ninstance : Inhabited Nat := \u27e80\u27e9\n-/\ninstance : Inhabited Bool := \u27e8true\u27e9\nend\n"
        rc, out, _e, tabs = _go({"A.lean": src})
        return _eq((rc, _sum(out).get("instance"), tabs["decls"][2]), (0, 1, []))

    @case("T7c", "an `example` indented two spaces is NOT counted (column 0 only); after `noncomputable` and after `protected` it IS "
                 "counted (control: 2)")
    def _():
        src = "section S\n  example : True := trivial\nend S\nnoncomputable example : True := trivial\nprotected example : True := trivial\n"
        _rc, out, _e, _t = _go({"A.lean": src})
        return _eq((_sum(out).get("example"), _sum(out).get("instance")), (2, 0))

    # ---- table shape
    @case("COL1", "both tables: the exact column row, six tab-separated fields on every row, no empty field, basis always `text-extent`")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "def t := 1\ndef t := 2\nnamespace N\ntheorem u : True := trivial\nend N\n",
                                 "B.lean": "instance : Inhabited Nat := ⟨0⟩\nstructure S where\n  x : Nat\n"})
        bad = []
        for key in ("decls", "dup"):
            lines, cols, rows = tabs[key]
            body = [ln for ln in lines if not ln.startswith("#")]
            if cols != ["module", "name", "kind", "first_line", "last_line", "basis"]:
                bad.append((key, "columns", cols))
            for ln in body[1:]:
                f = ln.split("\t")
                if len(f) != 6 or "" in f or f[5] != "text-extent":
                    bad.append((key, ln))
        n = (len(tabs["decls"][2]), len(tabs["dup"][2]))
        return (not bad and n == (4, 2)), f"rows {n}, bad {bad!r}"

    @case("SORT1", "rows are sorted by (module, first_line as a number, name, kind) even when the file holds them in another order "
                   "(names in reverse order; line 10 after line 2). It pins the key's TYPE (number, not text) and the name tie-break; "
                   "deleting the sort alone does not turn it red, because one file is already in line order (SORT2 pins that)")
    def _():
        zs = "".join(f"def {chr(ord('z') - i)} := {i}\n" for i in range(11)) + "end\n"
        _rc, _o, _e, tabs = _go({"Z.lean": zs, "A.lean": "def zz := 1\ndef aa := 2\nend\n"})
        got = [(r["module"], int(r["first_line"]), r["name"]) for r in tabs["decls"][2]]
        want = [("A", 1, "zz"), ("A", 2, "aa")] + [("Z", i + 1, chr(ord("z") - i)) for i in range(11)]
        return _eq(got, want)

    # ---- the selector
    @case("SEL1", "`--selftest --only ID,ID` runs exactly the named cases; an unknown id exits 2 naming it and runs nothing")
    def _():
        ok_out, bad_out, bad_err = io.StringIO(), io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(ok_out):
            selftest(only=["T1b", "T3b"])
        with contextlib.redirect_stdout(bad_out), contextlib.redirect_stderr(bad_err):
            rc = selftest(only=["T1b", "NOPE"])
        ran = [ln.split(" ")[1] for ln in ok_out.getvalue().splitlines() if ln.startswith("CASE ")]
        return _eq((ran, rc, "NOPE" in bad_err.getvalue(), bad_out.getvalue()), (["T1b", "T3b"], 2, True, ""))

    return cases


def selftest(verbose=True, only=None):
    """A case returns (True|False, detail), or (None, text) to be SKIPPED (a skip never fails the self-test).
    `only` is a list of case ids: exactly those cases run (an unknown id returns 2 and names it)."""
    ok, skipped = True, 0
    cases = _selftest_cases()
    if only is not None:
        known = {c[0] for c in cases}
        bad = [i for i in only if i not in known]
        if bad or not only:
            print("unknown case id: " + ", ".join(bad) if bad else "no case id given", file=sys.stderr)
            return 2
        cases = [c for c in cases if c[0] in only]
    for cid, desc, fn in cases:
        try:
            good, detail = fn()
        except _SkipCase as e:
            good, detail = None, str(e)
        except Exception as e:  # a crash is a failed case, not a skipped one
            good, detail = False, f"{type(e).__name__}: {e}"
        if good is None:
            skipped += 1
            if verbose:
                print(f"CASE {cid} SKIP {detail}")
            continue
        ok = ok and bool(good)
        if verbose:
            print(f"CASE {cid} {'PASS' if good else 'FAIL'} {desc}")
            if not good:
                print(f"  detail: {detail}")
    if verbose:
        print("SELFTEST " + ("PASS" if ok else "FAIL") + (f" ({skipped} skipped)" if ok and skipped else ""))
    return 0 if ok else 4


def selftest_quiet():
    with contextlib.redirect_stdout(io.StringIO()):
        return selftest(verbose=False)


def main(a):
    if a[1:] == ["--selftest"]:
        return selftest()
    if len(a) == 4 and a[1] == "--selftest" and a[2] == "--only":   # selector, kept out of the usage block
        return selftest(only=[i for i in a[3].split(",") if i])
    if len(a) != 3:
        print(__doc__.split("usage:")[1].strip(), file=sys.stderr)
        return 2
    if selftest_quiet() != 0:
        print("REFUSED: selftest failed; no result reported", file=sys.stderr)
        return 4
    return run(a[1], a[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
