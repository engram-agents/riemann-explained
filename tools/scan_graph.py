#!/usr/bin/env python3
"""First pass of the proof map: one row per Lean file, one row per import edge, from the source text only.

Nothing is compiled. Columns of files.tsv:
  module      dotted module name (path under SRC_ROOT)
  lines       physical lines in the file
  thm, defs   lines that START a declaration: theorem/lemma, def/abbrev/structure/class/inductive/instance
              (a text match on the raw line start after attributes and modifiers; not Lean's own count)
  dec, ndec   occurrences of the words `decide` and `native_decide` (whole word; ndec not counted in dec)
  nnum, omega, simp   occurrences of `norm_num`, `omega`, `simp` (whole word)
  imp_in      imports that resolve to a file under SRC_ROOT
  imp_ext     imports that do not (Mathlib, Lean core, ...), by first component, e.g. Mathlib:1
  whole_mathlib  1 if the file has the line `import Mathlib` (the whole library)
  decode      `ok`, or `ERROR` when the file is not valid UTF-8 (every count column is then `-`)
edges.tsv has the columns `importer` and `imported`.

CONTRACT
 S1 Every `.lean` file under SRC_ROOT has exactly one row in files.tsv; the printed file count equals the
    row count.
 S2 An import that names a module under a top-level folder (or top-level file) of SRC_ROOT but resolves to
    no file is printed as `UNRESOLVED <module> <count>` and the exit code is 1. Imports of outside
    libraries are counted by first component and are not errors.
 S3 Import lines are read only from the file's header (see header_imports); a block comment in the header
    does not end the header early and contributes no imports.
 S4 Word counts (`decide`, `native_decide`, `norm_num`, `omega`, `simp`) are whole-word; `decide` does not
    count inside `native_decide`; the files.tsv `#` line says the counts include comments and strings.
    They are taken on the RAW text, not the masked text.
 S5 Nothing adjusts the `decide` count after the fact: it is the whole-word count and nothing else.
 D1 SRC_ROOT not a directory: exit 2 with a message. No `.lean` file under it: print
    `CHECKED NOTHING: no .lean file under SRC_ROOT` and exit 1.
 D2 A file that does not decode is printed as `UNDECODABLE <relpath>`, counted in the summary line, never
    skipped silently; the exit code is 1. It keeps its row in files.tsv and contributes no edge.
 Every TSV begins with one `#` provenance line, then one column-name row, then data rows.
 With --selftest the tool plants temporary trees, checks each contract line as its own CASE, prints one
 `CASE <id> PASS|FAIL` line each and a final `SELFTEST PASS|FAIL`; exit 0 or 4. A normal run does the same
 quietly first and refuses (exit 4, nothing else reported) if it fails.

SHARED API (importable, no side effects on import; the sibling tools use it): read_text, mask_comments,
header_imports, walk_lean, provenance.

LIMIT. A word count is a count of a word in the text, comments and strings included; it points to where
computation may sit and does not measure it. An import edge says the importer is compiled after the
imported file; it does not say any proof in the importer uses anything in it. A string literal is not
treated specially when comments are masked, so a `--` or `/-` inside a string starts a comment for the
masker. Declarations are counted by raw line start, so a line inside a block comment that begins with
`theorem` is counted.

usage: scan_graph.py SRC_ROOT OUT_DIR
       scan_graph.py --selftest
"""
import collections
import contextlib
import io
import os
import re
import subprocess
import sys
import tempfile

FILES_COLS = ["module", "lines", "thm", "defs", "dec", "ndec", "nnum", "omega", "simp",
              "imp_in", "imp_ext", "whole_mathlib", "decode"]
EDGES_COLS = ["importer", "imported"]


# ---------------------------------------------------------------- shared API (STUBS)

def read_text(path):
    return "", False


def mask_comments(text):
    return text


def header_imports(text):
    return []


def walk_lean(root):
    return []


def provenance(tool, root, not_a):
    return "# stub"


# ---------------------------------------------------------------- the tool (STUB)

def scan_text(text):
    return 0, collections.Counter(), []


def run(root, out):
    return 0


# ---------------------------------------------------------------- self-test

def _plant(root, files):
    for rel, content in files.items():
        p = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(content if isinstance(content, bytes) else content.encode("utf-8"))


def _table(path):
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    body = [ln for ln in lines if not ln.startswith("#")]
    cols = body[0].split("\t") if body else []
    return lines, cols, [dict(zip(cols, ln.split("\t"))) for ln in body[1:]]


def _go(files):
    with tempfile.TemporaryDirectory() as d:
        root, out = os.path.join(d, "src"), os.path.join(d, "out")
        os.makedirs(root)
        _plant(root, files)
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = run(root, out)
        tabs = {}
        for n in ("files", "edges"):
            p = os.path.join(out, n + ".tsv")
            tabs[n] = _table(p) if os.path.isfile(p) else ([], [], [])
        return rc, buf.getvalue(), err.getvalue(), tabs


def _row(tabs, name, module):
    col = "module" if name == "files" else "importer"
    rows = [r for r in tabs[name][2] if r[col] == module]
    return rows[0]


def _edges(tabs):
    return sorted((r["importer"], r["imported"]) for r in tabs["edges"][2])


def _eq(actual, expected):
    return actual == expected, f"expected {expected!r}, got {actual!r}"


def _selftest_cases():
    cases = []

    def case(cid, desc):
        def deco(fn):
            cases.append((cid, desc, fn))
            return fn
        return deco

    # ---- the shared API
    @case("READ1", "read_text: valid UTF-8 gives (text, True); invalid gives ('', False), never replaced")
    def _():
        with tempfile.TemporaryDirectory() as d:
            _plant(d, {"ok.lean": "α\n", "bad.lean": b"a\xffb\n"})
            got = (read_text(os.path.join(d, "ok.lean")), read_text(os.path.join(d, "bad.lean")))
        return _eq(got, (("α\n", True), ("", False)))

    @case("MASK1", "mask_comments: line, nested block, /-- and /-! comments become spaces; newlines and length kept")
    def _():
        t = "a -- c1\nb /- x /- y -/ z -/ c\n/-- d -/ e /-! f -/\n--/ g\n"
        want = ("a " + " " * 5 + "\n" + "b " + " " * 17 + " c\n" + " " * 8 + " e " + " " * 8 + "\n" + " " * 5 + "\n")
        got = mask_comments(t)
        return got == want and len(got) == len(t), f"expected {want!r}, got {got!r}"

    @case("MASK2", "mask_comments: an unterminated block comment is erased to the end of the text")
    def _():
        got = mask_comments("x /- open\nstill\n")
        return _eq(got, "x " + " " * 7 + "\n" + " " * 5 + "\n")

    @case("MASK3", "mask_comments: `--` inside a block comment does not end it early; `-/` after `--` still closes")
    def _():
        got = mask_comments("a /- -- x --/ b\n")
        return _eq(got, "a " + " " * 11 + " b\n")

    @case("S3c", "header_imports: module/prelude skipped, `import A B` gives both, trailing -- note is not a module")
    def _():
        got = header_imports("module\nprelude\n\nimport A B\nimport C.D -- import Z\ntheorem x : True := trivial\nimport Q\n")
        return _eq(got, ["A", "B", "C.D"])

    @case("S3d", "header_imports: block comments in the header neither end it nor yield imports")
    def _():
        got = header_imports("/- doc -/\nimport A\n/-\nimport X\n-/\nimport B\n/-! t -/\ndef f := 1\nimport Late\n")
        return _eq(got, ["A", "B"])

    @case("WALK1", "walk_lean: sorted (module, path) for every .lean, dots for separators, symlinked dirs not followed")
    def _():
        with tempfile.TemporaryDirectory() as d:
            _plant(d, {"b/C.lean": "", "A.lean": "", "x.txt": "", "b/deep/E.lean": ""})
            os.symlink(os.path.join(d, "b"), os.path.join(d, "ln"))
            got = walk_lean(d)
            want = [("A", os.path.join(d, "A.lean")), ("b.C", os.path.join(d, "b", "C.lean")),
                    ("b.deep.E", os.path.join(d, "b", "deep", "E.lean"))]
        return _eq(got, want)

    @case("PROV1", "provenance: a root outside any git work tree says `unversioned`")
    def _():
        with tempfile.TemporaryDirectory() as d:
            got = provenance("t", d, "not x")
        return _eq(got, "# t | source: unversioned| not x")

    @case("PROV2", "provenance: a root in a git work tree carries `git rev-parse HEAD`")
    def _():
        with tempfile.TemporaryDirectory() as d:
            g = ["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", "-C", d]
            subprocess.run(g + ["init", "-q"], check=True, capture_output=True)
            subprocess.run(g + ["commit", "-q", "--allow-empty", "-m", "x"], check=True, capture_output=True)
            sha = subprocess.run(g + ["rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            got = provenance("t", d, "not x")
        return _eq(got, f"# t | source: {sha}| not x")

    @case("PROV3", "provenance: a git work tree whose HEAD cannot be read says `git-unreadable`")
    def _():
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "-C", d, "init", "-q"], check=True, capture_output=True)
            got = provenance("t", d, "not x")
        return _eq(got, "# t | source: git-unreadable| not x")

    # ---- the tool
    @case("S1a", "three files -> printed file count 3 and 3 rows in files.tsv")
    def _():
        rc, out, _e, tabs = _go({"A.lean": "def a := 1\n", "B.lean": "def b := 1\n", "sub/C.lean": "def c := 1\n"})
        m = re.search(r"^files (\d+) ", out, re.M)
        return _eq((rc, m and m.group(1), len(tabs["files"][2])), (0, "3", 3))

    @case("S1b", "a non-UTF-8 file: UNDECODABLE <relpath> printed and counted, row decode ERROR with '-' counts, no edge, exit 1")
    def _():
        rc, out, _e, tabs = _go({"Good.lean": "def g := 1\n", "sub/Bad.lean": b"import Good\n\xff\n"})
        r = _row(tabs, "files", "sub.Bad")
        dash = {k: "-" for k in FILES_COLS[1:-1]}
        got = (rc, "UNDECODABLE sub/Bad.lean" in out.splitlines(), "undecodable 1" in out, len(tabs["files"][2]),
               {k: r[k] for k in dash}, r["decode"], _edges(tabs), _row(tabs, "files", "Good")["decode"])
        return _eq(got, (1, True, True, 2, dash, "ERROR", [], "ok"))

    @case("S2a", "an import of a missing module under an own top-level folder: `UNRESOLVED <module> <count>`, exit 1")
    def _():
        rc, out, _e, tabs = _go({"Own/A.lean": "import Own.Missing\n", "Own/B.lean": "import Own.Missing\nimport Own.A\n"})
        return _eq((rc, "UNRESOLVED Own.Missing 2" in [ln.strip() for ln in out.splitlines()], _edges(tabs)),
                   (1, True, [("Own.B", "Own.A")]))

    @case("S2b", "an outside import is counted by first component and is not an error: exit 0, no UNRESOLVED")
    def _():
        rc, out, _e, tabs = _go({"A.lean": "import Mathlib.Tactic\nimport Mathlib.Data.Nat\nimport Lean\n"})
        r = _row(tabs, "files", "A")
        return _eq((rc, "UNRESOLVED" in out, r["imp_in"], r["imp_ext"], r["whole_mathlib"]), (0, False, "0", "Lean:1,Mathlib:2", "0"))

    @case("S2c", "`import Mathlib` sets whole_mathlib to 1")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "import Mathlib\n"})
        r = _row(tabs, "files", "A")
        return _eq((r["whole_mathlib"], r["imp_ext"]), ("1", "Mathlib:1"))

    @case("S3a", "a block-commented import before a real import: the commented one is not an edge, the real one is")
    def _():
        _rc, _o, _e, tabs = _go({"Entry.lean": "/-\nimport Hidden\n-/\nimport Real\n", "Hidden.lean": "", "Real.lean": ""})
        return _eq(_edges(tabs), [("Entry", "Real")])

    @case("S3b", "an import after the first declaration is not read, not even as an outside import")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "theorem x : True := trivial\nimport B\n", "B.lean": ""})
        r = _row(tabs, "files", "A")
        return _eq((_edges(tabs), r["imp_in"], r["imp_ext"]), ([], "0", "-"))

    @case("S4a", "`native_decide` once and `decide` twice: ndec 1, dec 2")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "theorem t : True := by\n  native_decide\n  decide\n  decide\n"})
        r = _row(tabs, "files", "A")
        return _eq((r["dec"], r["ndec"]), ("2", "1"))

    @case("S4b", "`simp` inside `simpa` and `simp_all` is not counted; a bare `simp` is")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "simpa\nsimp\nsimp_all\n"})
        return _eq(_row(tabs, "files", "A")["simp"], "1")

    @case("S4c", "counts are taken on the raw text: words in comments count, and the files.tsv # line says so")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "-- decide\n/- native_decide -/\n"})
        r = _row(tabs, "files", "A")
        return _eq((r["dec"], r["ndec"], "comments and strings" in tabs["files"][0][0]), ("1", "1", True))

    @case("S4d", "norm_num and omega are whole-word counts")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "norm_num\nomega\nomega\nnorm_num_ext\nomegax\n"})
        r = _row(tabs, "files", "A")
        return _eq((r["nnum"], r["omega"]), ("1", "2"))

    @case("S5a", "only native_decide twice: dec is 0 (no adjustment), ndec 2")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "native_decide\nnative_decide\n"})
        r = _row(tabs, "files", "A")
        return _eq((r["dec"], r["ndec"]), ("0", "2"))

    @case("S6a", "thm and defs count lines that start a declaration after attributes and modifiers")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "theorem a\nlemma b\ndef c\n@[simp] abbrev d\nprivate instance e\nstructureX f\n"})
        r = _row(tabs, "files", "A")
        return _eq((r["thm"], r["defs"]), ("2", "3"))

    @case("S6b", "lines counts physical lines with or without a final newline")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "a\nb", "B.lean": "a\nb\n"})
        return _eq((_row(tabs, "files", "A")["lines"], _row(tabs, "files", "B")["lines"]), ("2", "2"))

    @case("HDR1", "files.tsv: a `#` provenance line first (with its NOT sentence), then the column row")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "def a := 1\n"})
        lines = tabs["files"][0]
        ok = (lines[0].startswith("# scan_graph.py | source: ")
              and "a row is a text count of one file, not a measurement of what any proof uses" in lines[0]
              and lines[1] == "\t".join(FILES_COLS))
        return ok, f"got {lines[:2]!r}"

    @case("HDR2", "edges.tsv: a `#` provenance line first (with its NOT sentence), then the column row")
    def _():
        _rc, _o, _e, tabs = _go({"A.lean": "import B\n", "B.lean": ""})
        lines = tabs["edges"][0]
        ok = (len(lines) > 1 and lines[0].startswith("# scan_graph.py | source: ")
              and "a row says the importer is compiled after the imported file, not that any proof in the importer uses anything in it" in lines[0]
              and lines[1] == "\t".join(EDGES_COLS))
        return ok, f"got {lines[:2]!r}"

    @case("D1a", "SRC_ROOT that is not a directory: exit 2")
    def _():
        with tempfile.TemporaryDirectory() as d:
            err = io.StringIO()
            with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
                rc = run(os.path.join(d, "nope"), os.path.join(d, "out"))
        return _eq((rc, bool(err.getvalue().strip())), (2, True))

    @case("D1b", "no .lean file under SRC_ROOT: `CHECKED NOTHING: no .lean file under SRC_ROOT`, exit 1")
    def _():
        rc, out, _e, _t = _go({"readme.txt": "x"})
        return _eq((rc, "CHECKED NOTHING: no .lean file under SRC_ROOT" in out.splitlines()), (1, True))

    @case("AGREE1", "scan_graph's edges and import_closure.closure give the same closure for a header block comment hiding `import Hidden`")
    def _():
        files = {"Entry.lean": "/-\nimport Hidden\n-/\nimport A\nimport B\ntheorem x : True := trivial\n",
                 "A.lean": "import C\n", "B.lean": "", "C.lean": "", "Hidden.lean": ""}
        _rc, _o, _e, tabs = _go(files)
        adj = collections.defaultdict(list)
        for a, b in _edges(tabs):
            adj[a].append(b)
        seen, stack = {"Entry"}, ["Entry"]
        while stack:
            for y in adj[stack.pop()]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        here = os.path.dirname(os.path.abspath(__file__))
        if here not in sys.path:
            sys.path.insert(0, here)
        import import_closure
        with tempfile.TemporaryDirectory() as d:
            _plant(d, files)
            other, _ext = import_closure.closure(d, "Entry")
        want = {"Entry", "A", "B", "C"}
        return (seen == want and other == want), f"expected {sorted(want)}, scan_graph {sorted(seen)}, import_closure {sorted(other)}"

    return cases


def selftest(verbose=True):
    ok = True
    for cid, desc, fn in _selftest_cases():
        try:
            good, detail = fn()
        except Exception as e:  # a crash is a failed case, not a skipped one
            good, detail = False, f"{type(e).__name__}: {e}"
        ok = ok and bool(good)
        if verbose:
            print(f"CASE {cid} {'PASS' if good else 'FAIL'} {desc}")
            if not good:
                print(f"  detail: {detail}")
    if verbose:
        print("SELFTEST " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 4


def selftest_quiet():
    with contextlib.redirect_stdout(io.StringIO()):
        return selftest(verbose=False)


def main(a):
    if a[1:] == ["--selftest"]:
        return selftest()
    if len(a) != 3:
        print(__doc__.split("usage:")[1].strip(), file=sys.stderr)
        return 2
    if selftest_quiet() != 0:
        print("REFUSED: selftest failed; no result reported", file=sys.stderr)
        return 4
    return run(a[1], a[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
