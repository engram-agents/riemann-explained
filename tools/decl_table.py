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
Stdout, two lines, printed even on failure:
  files N  declarations N  pairs unique U  pairs not unique D (rows R)  undecodable K
  not rows (counted lines): example E  instance without a name I
U = distinct (module, name) pairs that occur once; D = distinct pairs that occur more than once; R = rows in
decls_dup.tsv. The second line counts lines that are NOT rows: `example` lines at column 0 (comments masked, with
optional attributes and modifiers) and `instance` lines that carry no name.

CONTRACT
 T1 Every `.lean` file is read once. A file that does not decode (`UNDECODABLE <relpath>`) or cannot be read at all
    (`UNREADABLE <relpath>`) is reported by path on stderr and counted in `undecodable`; the run still writes every
    other file's rows; the exit code is 1. No `.lean` file under SRC_ROOT: `CHECKED NOTHING: no .lean file under
    SRC_ROOT` on stdout, exit 1, no table written. A usage error or a SRC_ROOT that is not a directory: exit 2. A
    failing self-test: exit 4, nothing else reported. Exit 0 otherwise, INCLUDING when duplicate pairs exist.
    Cases T1a T1b T1c T1d T1e EXIT4 (exit 0 with duplicates: T2a).
 T2 A (module, name) pair that occurs more than once is written, all of its rows, in decls.tsv AND in
    decls_dup.tsv, never one picked; the summary counts unique and non-unique pairs. The same name in two modules
    is not a duplicate. The pair ignores the kind: a `def x` and a `theorem x` in one module are a duplicate.
    Cases T2a T2b T2c T2d.
 T3 The extent is the text rule's. It starts at the keyword line and ends at the line before the next boundary
    line, so it can include trailing blank lines and plain comment lines. A doc comment (`/-` at column 0) that
    precedes the NEXT declaration is outside the extent; a declaration's own doc comment above it and an attribute
    on its own line above it are not part of its extent; first_line is the keyword line. The `#` line says the
    extent is a text extent, NOT Lean's. Cases T3a T3b T3c T3d T3e EOF1.
 T4 A declaration inside a block comment, nested ones included, does not appear. Cases T4a T4b.
 T5 Names: inside `namespace A.B`, `theorem x` is `A.B.x`; `end B` closes only B (a later declaration in the same
    block is `A.y`); `_root_.x` is `x`; a `section S` adds no prefix. (This is parse_decls' behaviour, pinned here
    through the table.) Cases T5a T5b T5c.
 T6 `private`, `protected`, `noncomputable` and the other modifiers: the declaration appears under its written
    name and its kind is the declaring keyword. Cases T6a.
 T7 Nameless `instance` and `example` lines are not rows and are counted on the second summary line. Case T7a.
 T8 Determinism: two runs under different PYTHONHASHSEED values, and a tree whose files were created in another
    order, give byte-identical decls.tsv and decls_dup.tsv. Cases T8a T8b.
 T9 Files are read once: `run(root, out, reader=...)` takes the function that reads a file (default
    scan_graph.read_text); a counting reader sees exactly one call per file. Case T9a.
 Every row has the six tab-separated fields, none empty; the column row is exact (COL1); rows are sorted (SORT1);
 `--selftest --only ID,ID` runs exactly the named cases and an unknown id exits 2 (SEL1).
 With --selftest the tool plants temporary trees, checks each contract line as its own CASE (each with its own
 planted tree and a control that resolves), prints one `CASE <id> PASS|FAIL` line each and a final
 `SELFTEST PASS|FAIL`; exit 0 or 4. A normal run does the same quietly first and refuses (exit 4, nothing else
 reported) if it fails.

LIMIT. A row is the text rule's extent of a named declaration. It is not Lean's extent and it does not say the
declaration is used or compiled. last_line is parse_decls' end_idx as it stands: for the last declaration of a
file that ends in a newline it is one past the last physical line (EOF1). A declaration inside a block comment
is not read; one inside a string literal is (strings are not special-cased when comments are masked). A keyword
line that is indented is read like one at column 0 (parse_decls does not look at the indent), so an indented
`theorem` inside a `where` block or a tactic block is a row. Names come from the text: a `private` declaration is
not given Lean's mangled name, a name made by a macro or a structure field is not seen, and `open`, `export` and
aliases are not modelled. A `variable`, `open` or `set_option` line ends the extent of the declaration above it.
`mutual` and `noncomputable section` push a scope entry like `section`. The pair test is on the written full name:
two `private` declarations with one name in one module are listed as a duplicate although Lean tells them apart.

usage: decl_table.py SRC_ROOT OUT_DIR
       decl_table.py --selftest
"""
import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scan_graph import (_SkipCase, _plant, _plant_unreadable, _table, failure_word,  # noqa: E402
                        mask_comments, provenance, read_text, walk_lean)
from lean_decls import DECL, parse_decls  # noqa: E402

COLS = ["module", "name", "kind", "first_line", "last_line", "basis"]
BASIS = "text-extent"
EXAMPLE = re.compile(r"^(?:@\[[^\]\n]*\][ \t]*)*(?:(?:private|protected|noncomputable|nonrec|unsafe|partial)[ \t]+)*"
                     r"example\b", re.M)


# ---------------------------------------------------------------- the tool

def run(root, out, reader=None):
    return 0


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
        got = (rc, [(r["module"], r["name"]) for r in tabs["decls"][2]], tabs["dup"][2], tabs["dup"][1] == COLS,
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
              and "NOT Lean" in lines[0] and lines[1] == "\t".join(COLS) and lines[0] == (tabs["dup"][0] or [""])[0])
        return ok, f"got {lines[:2]!r}, dup first line {(tabs['dup'][0] or [''])[0]!r}"

    @case("EOF1", "today's rule, recorded: the last declaration of a file that ends in a newline has last_line one past the last "
                  "physical line (parse_decls' end_idx); a file without the final newline has last_line equal to it")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "def a := 1\ndef b := 2\n", "B.lean": "def a := 1\ndef b := 2"})
        got = [(r["module"], r["name"], r["first_line"], r["last_line"]) for r in tabs["decls"][2]]
        return _eq(got, [("A", "a", "1", "1"), ("A", "b", "2", "3"), ("B", "a", "1", "1"), ("B", "b", "2", "2")])

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

    # ---- table shape
    @case("COL1", "both tables: the exact column row, six tab-separated fields on every row, no empty field, basis always `text-extent`")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "def t := 1\ndef t := 2\nnamespace N\ntheorem u : True := trivial\nend N\n",
                                 "B.lean": "instance : Inhabited Nat := ⟨0⟩\nstructure S where\n  x : Nat\n"})
        bad = []
        for key in ("decls", "dup"):
            lines, cols, rows = tabs[key]
            body = [ln for ln in lines if not ln.startswith("#")]
            if cols != COLS:
                bad.append((key, "columns", cols))
            for ln in body[1:]:
                f = ln.split("\t")
                if len(f) != 6 or "" in f or f[5] != BASIS:
                    bad.append((key, ln))
        n = (len(tabs["decls"][2]), len(tabs["dup"][2]))
        return (not bad and n == (4, 2)), f"rows {n}, bad {bad!r}"

    @case("SORT1", "rows are sorted by (module, first_line as a number, name, kind) even when the file holds them in another order "
                   "(names in reverse order; line 10 after line 2)")
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
