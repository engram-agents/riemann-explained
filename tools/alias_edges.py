#!/usr/bin/env python3
"""Alias layer of the proof map, from text only.

An alias is a theorem whose whole proof is the wrapper
  `first | exact @X | exact X | (intros; apply X <;> assumption)`
(the three X equal). This tool finds the aliases, resolves each X to the file and line that declares it,
and lists where the alias names and the targets are written out in full.

Outputs under OUT_DIR (each starts with a `#` provenance line, then the column row):
  aliases.tsv           public_name, target, file, line, target_file, target_line, target_matches
  aliases_odd.tsv       public_name, x1, x2, x3, file, line     (wrapper shape, the three X not all equal)
  alias_candidates.tsv  public_name, target, candidate_file, candidate_line   (only when target_matches >= 2)
  refs.tsv              file, public_name, occurrences, in_comment_only
  callers.tsv           name, kind (alias|target), file, line, in_comment (0|1)
  uncalled.tsv          name, kind

CONTRACT
 A1 Every theorem (or lemma) in ANY .lean file whose body is exactly the wrapper shape with the three X equal
    yields one row in aliases.tsv (public name, target X, file, line). Several per file are allowed. The body
    is the text after the first `:= by` of the declaration's extent; the extent runs from its line to the line
    before the next column-0 declaration keyword, `end`, `namespace`, `section`, `open`, `set_option`,
    `attribute`, `variable`, `universe`, `noncomputable`, `@[`, `/-` (also the modifiers private, protected,
    nonrec, unsafe, partial and `mutual`), or to the end of the file. Whitespace around the tokens may vary.
 A2 A theorem whose body has the shape but with unequal X is listed in aliases_odd.tsv, not dropped.
 A3 Each target is resolved to its DECLARING file and line: a declaration whose full name equals X exactly.
    target_matches = number of declarations found: 0 = UNRESOLVED, 1 = resolved, 2 or more = AMBIGUOUS; for
    2 or more every candidate is written to alias_candidates.tsv and target_file/target_line are `-`. The tool
    never picks one. The summary line prints `targets resolved N / ambiguous N / unresolved N`, counted per
    alias row. The full name is the enclosing `namespace` names plus the declared name; `_root_.` means no
    namespace prefix. Structure is read from the comment-masked text, so a declaration inside a comment is
    not a candidate.
 A4 refs.tsv: for every file and every distinct token `GlobalTheory.T.<name>` that is a known public name under
    `GlobalTheory.T.`, one row (the file that holds the name's own wrapper is skipped), with in_comment_only = 1
    when every occurrence in that file sits inside a line or block comment.
 A5 callers.tsv: for every alias public name and every resolved (matches = 1) target full name, the files and
    lines where that exact full name occurs as a whole dotted token (maximal run of `[\\w'.₀-₉]` characters with
    trailing dots trimmed), outside its own declaration line; one row per file and line, in_comment = 1 when
    every occurrence on that line is inside a comment. A name with no row is listed in uncalled.tsv.
 D1 SRC_ROOT not a directory: exit 2. No `.lean` file: `CHECKED NOTHING: no .lean file under SRC_ROOT`, exit 1.
 D2 A file that does not decode is printed as `UNDECODABLE <relpath>`, counted in the summary, and the exit
    code is 1.
 Two passes over the files: pass 1 finds the wrappers and the target set; pass 2 collects the declarations for
 the full names in the target set and tokenizes for A4 and A5 with one regex scan per file.
 With --selftest it plants temporary trees, checks each contract line as its own CASE, prints one
 `CASE <id> PASS|FAIL` line each and a final `SELFTEST PASS|FAIL`; exit 0 or 4. A normal run does the same
 quietly first and refuses (exit 4, nothing else reported) if it fails.

LIMIT. A reference is a text match on the fully written name; a use through an opened namespace, a shorter
name or dot notation is not seen, so `uncalled` means "not named in full anywhere", not "unused". Names
inside comments are matched (flagged by in_comment). A declaration is recognised by its keyword at a line
start; names built by macros, `private` name mangling and structure fields are not seen. The shape must be
written as above; a differently written alias is not found. A string literal is not special-cased when
comments are masked. Refs (A4) use the token `GlobalTheory.T.<name>` as written, so a longer dotted name
that starts with a known public name also counts for the shorter one there, while callers (A5) do not.

usage: alias_edges.py SRC_ROOT OUT_DIR
       alias_edges.py --selftest
"""
import collections
import contextlib
import io
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scan_graph import mask_comments, provenance, read_text, walk_lean  # noqa: E402

ALIASES_COLS = ["public_name", "target", "file", "line", "target_file", "target_line", "target_matches"]
ODD_COLS = ["public_name", "x1", "x2", "x3", "file", "line"]
CAND_COLS = ["public_name", "target", "candidate_file", "candidate_line"]
REFS_COLS = ["file", "public_name", "occurrences", "in_comment_only"]
CALLERS_COLS = ["name", "kind", "file", "line", "in_comment"]
UNCALLED_COLS = ["name", "kind"]


# ---------------------------------------------------------------- the tool (STUB)

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


TABLES = ["aliases", "aliases_odd", "alias_candidates", "refs", "callers", "uncalled"]


def _go(files, count_reads=False):
    with tempfile.TemporaryDirectory() as d:
        root, out = os.path.join(d, "src"), os.path.join(d, "out")
        os.makedirs(root)
        _plant(root, files)
        buf, err = io.StringIO(), io.StringIO()
        reads = [0]
        real = globals()["read_text"]

        def counting(path):
            reads[0] += 1
            return real(path)
        if count_reads:
            globals()["read_text"] = counting
        try:
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
                rc = run(root, out)
        finally:
            globals()["read_text"] = real
        tabs = {}
        for n in TABLES:
            p = os.path.join(out, n + ".tsv")
            tabs[n] = _table(p) if os.path.isfile(p) else ([], [], [])
        return rc, buf.getvalue(), err.getvalue(), tabs, reads[0]


def _W(name, x1, x2=None, x3=None):
    x2 = x2 or x1
    x3 = x3 or x1
    return f"theorem {name} : P := by\n  first | exact @{x1} | exact {x2} | (intros; apply {x3} <;> assumption)\n"


def _pairs(tabs, name, *cols):
    return sorted(tuple(r[c] for c in cols) for r in tabs[name][2])


def _eq(actual, expected):
    return actual == expected, f"expected {expected!r}, got {actual!r}"


def _selftest_cases():
    cases = []

    def case(cid, desc):
        def deco(fn):
            cases.append((cid, desc, fn))
            return fn
        return deco

    CORE = {"Lib/Core.lean": "namespace Lib\ntheorem alpha_core : P := sorry\nend Lib\n"}
    ALPHA = {"Pub/Thing.lean": "namespace GlobalTheory.T\n" + _W("alpha", "Lib.alpha_core") + "end GlobalTheory.T\n"}

    @case("A1a", "one wrapper in a file not named *Statement.lean: one aliases.tsv row, target resolved with file and line")
    def _():
        _rc, _o, _e, tabs, _n = _go({**ALPHA, **CORE})
        return _eq(tabs["aliases"][2], [dict(public_name="GlobalTheory.T.alpha", target="Lib.alpha_core", file="Pub/Thing.lean",
                                              line="2", target_file="Lib/Core.lean", target_line="2", target_matches="1")])

    @case("A1b", "two wrappers in one file: two rows with their own lines")
    def _():
        _rc, _o, _e, tabs, _n = _go({"Two.lean": "namespace GlobalTheory.T\n" + _W("one", "L.x") + _W("two", "L.y") + "end GlobalTheory.T\n"})
        return _eq(_pairs(tabs, "aliases", "public_name", "line"), [("GlobalTheory.T.one", "2"), ("GlobalTheory.T.two", "4")])

    @case("A1c", "whitespace may vary: a one-line compact wrapper and a multi-line wrapper are both found")
    def _():
        t = ("theorem w : P := by first|exact @L.x|exact L.x|(intros;apply L.x<;>assumption)\n"
             "theorem v : P := by\n  first\n    | exact @L.y\n    | exact L.y\n    | (intros; apply L.y <;> assumption)\n")
        _rc, _o, _e, tabs, _n = _go({"W.lean": t})
        return _eq(_pairs(tabs, "aliases", "public_name", "target", "line"), [("v", "L.y", "2"), ("w", "L.x", "1")])

    @case("A1d", "a body with anything after the wrapper, or another tactic, is neither an alias nor odd")
    def _():
        t = ("theorem t : P := by\n  first | exact @L.x | exact L.x | (intros; apply L.x <;> assumption)\n  simp\n"
             "theorem u : P := by\n  exact L.x\n" + _W("good", "L.z"))
        _rc, _o, _e, tabs, _n = _go({"T.lean": t})
        return _eq((_pairs(tabs, "aliases", "public_name"), tabs["aliases_odd"][2]), ([("good",)], []))

    @case("A2a", "the shape with unequal X goes to aliases_odd.tsv with its three X, and not to aliases.tsv")
    def _():
        _rc, _o, _e, tabs, _n = _go({"Odd.lean": _W("odd", "L.a", "L.b", "L.a")})
        return _eq((tabs["aliases"][2], tabs["aliases_odd"][2]),
                   ([], [dict(public_name="odd", x1="L.a", x2="L.b", x3="L.a", file="Odd.lean", line="1")]))

    def decl(ns, name="main"):
        return f"namespace {ns}\ntheorem {name} : P := sorry\nend {ns}\n"

    @case("A3a", "two `main` in two folders and namespaces, one the target: it resolves to the right one, matches 1")
    def _():
        _rc, _o, _e, tabs, _n = _go({"A/M.lean": decl("NsA"), "B/M.lean": decl("NsB"), "Pub/W.lean": _W("viaA", "NsA.main")})
        r = tabs["aliases"][2][0]
        return _eq((r["target_file"], r["target_line"], r["target_matches"], tabs["alias_candidates"][2]), ("A/M.lean", "2", "1", []))

    @case("A3b", "the same pair in the SAME namespace: matches 2, `-` columns, both candidates listed, none picked")
    def _():
        _rc, _o, _e, tabs, _n = _go({"C1/M.lean": decl("NsC"), "C2/M.lean": decl("NsC"), "Pub/W.lean": _W("viaC", "NsC.main")})
        r = tabs["aliases"][2][0]
        return _eq((r["target_file"], r["target_line"], r["target_matches"],
                    _pairs(tabs, "alias_candidates", "public_name", "target", "candidate_file", "candidate_line")),
                   ("-", "-", "2", [("viaC", "NsC.main", "C1/M.lean", "2"), ("viaC", "NsC.main", "C2/M.lean", "2")]))

    @case("A3c", "a target declared nowhere: matches 0, `-` columns, no candidate rows")
    def _():
        _rc, _o, _e, tabs, _n = _go({"Pub/W.lean": _W("lost", "Nowhere.thing")})
        r = tabs["aliases"][2][0]
        return _eq((r["target_file"], r["target_line"], r["target_matches"], tabs["alias_candidates"][2]), ("-", "-", "0", []))

    @case("A3d", "a target declared inside `namespace A.B` as `foo` is found by the wrapper naming `A.B.foo`")
    def _():
        _rc, _o, _e, tabs, _n = _go({"D/F.lean": decl("A.B", "foo"), "Pub/W.lean": _W("viaD", "A.B.foo")})
        r = tabs["aliases"][2][0]
        return _eq((r["target_file"], r["target_line"], r["target_matches"]), ("D/F.lean", "2", "1"))

    @case("A3e", "a `_root_.` declaration has no namespace prefix: `rooted_thm` resolves, `Zed.rooted_thm` does not")
    def _():
        _rc, _o, _e, tabs, _n = _go({"E/R.lean": "namespace Zed\ntheorem _root_.rooted_thm : P := sorry\nend Zed\n",
                                     "Pub/W.lean": _W("w1", "rooted_thm") + _W("w2", "Zed.rooted_thm")})
        return _eq(_pairs(tabs, "aliases", "public_name", "target_matches"), [("w1", "1"), ("w2", "0")])

    @case("A3f", "a declaration inside a block, line or doc comment is not a candidate")
    def _():
        ghost = ("/-\nnamespace Gh\ntheorem only_real : P := sorry\nend Gh\n-/\n-- theorem Gh.only_real : P := sorry\n"
                 "/-- theorem Gh.only_ghost -/\n/- namespace Gh -/\n/- theorem only_ghost : P := sorry -/\n")
        _rc, _o, _e, tabs, _n = _go({"G/Real.lean": decl("Gh", "only_real"), "G/Ghost.lean": ghost,
                                     "Pub/W.lean": _W("w1", "Gh.only_real") + _W("w2", "Gh.only_ghost")})
        rows = {r["public_name"]: r for r in tabs["aliases"][2]}
        return _eq((rows["w1"]["target_matches"], rows["w1"]["target_file"], rows["w2"]["target_matches"]), ("1", "G/Real.lean", "0"))

    @case("A3g", "scopes: sections, anonymous and noncomputable sections, mutual blocks and `end` give the right full names")
    def _():
        scope = ("namespace A\nsection X\ntheorem t1 : P := sorry\nend X\nsection\ntheorem t2 : P := sorry\nend\n"
                 "noncomputable section\ntheorem t3 : P := sorry\nend\nmutual\ntheorem t4 : P := sorry\nend\n"
                 "theorem t5 : P := sorry\nend A\ntheorem t6 : P := sorry\n")
        targets = ["A.t1", "A.t2", "A.t3", "A.t4", "A.t5", "t6", "A.t6", "t5"]
        _rc, _o, _e, tabs, _n = _go({"S/Scope.lean": scope, "Pub/W.lean": "".join(_W(f"w{i}", t) for i, t in enumerate(targets))})
        got = {r["target"]: r["target_matches"] for r in tabs["aliases"][2]}
        return _eq(got, {"A.t1": "1", "A.t2": "1", "A.t3": "1", "A.t4": "1", "A.t5": "1", "t6": "1", "A.t6": "0", "t5": "0"})

    @case("A3h", "attributes, modifiers and an inline doc comment before the keyword do not hide a declaration")
    def _():
        t = ("namespace N\nprivate theorem hidden : P := sorry\n@[simp] theorem sm : P := sorry\n/-- d -/ theorem dc : P := sorry\n"
             "instance : Foo := sorry\ninstance inst : Foo := sorry\nend N\n")
        _rc, _o, _e, tabs, _n = _go({"N.lean": t, "Pub/W.lean": "".join(_W(f"w{i}", "N." + n) for i, n in enumerate(["hidden", "sm", "dc", "inst"]))})
        return _eq(sorted(r["target_matches"] for r in tabs["aliases"][2]), ["1", "1", "1", "1"])

    @case("A3i", "the summary line prints `targets resolved N / ambiguous N / unresolved N`")
    def _():
        _rc, out, _e, _t, _n = _go({"A/M.lean": decl("NsA"), "C1/M.lean": decl("NsC"), "C2/M.lean": decl("NsC"),
                                    "Pub/W.lean": _W("w1", "NsA.main") + _W("w2", "NsC.main") + _W("w3", "Nowhere.x")})
        return _eq("targets resolved 1 / ambiguous 1 / unresolved 1" in out, True)

    PUB_ALPHA = {**ALPHA, **CORE}

    @case("A4a", "a public name mentioned only in a comment: refs row with in_comment_only 1; the wrapper's own file has no row")
    def _():
        _rc, _o, _e, tabs, _n = _go({**PUB_ALPHA, "Use/C.lean": "-- GlobalTheory.T.alpha\n"})
        return _eq(_pairs(tabs, "refs", "file", "public_name", "occurrences", "in_comment_only"),
                   [("Use/C.lean", "GlobalTheory.T.alpha", "1", "1")])

    @case("A4b", "a name in code and in a comment: occurrences 2, in_comment_only 0")
    def _():
        _rc, _o, _e, tabs, _n = _go({**PUB_ALPHA, "Use/D.lean": "def x := GlobalTheory.T.alpha\n-- see GlobalTheory.T.alpha\n"})
        return _eq(_pairs(tabs, "refs", "file", "occurrences", "in_comment_only"), [("Use/D.lean", "2", "0")])

    @case("A4c", "a name inside a block comment counts as in a comment")
    def _():
        _rc, _o, _e, tabs, _n = _go({**PUB_ALPHA, "Use/F.lean": "/-\nGlobalTheory.T.alpha\n-/\n"})
        return _eq(_pairs(tabs, "refs", "file", "occurrences", "in_comment_only"), [("Use/F.lean", "1", "1")])

    @case("A5a", "a target named in full by another file: a callers row with its line, kind target, in_comment 0")
    def _():
        _rc, _o, _e, tabs, _n = _go({**PUB_ALPHA, "Use/E.lean": "import Lib.Core\ntheorem z : P := Lib.alpha_core\n"})
        return _eq(_pairs(tabs, "callers", "name", "kind", "file", "line", "in_comment"),
                   [("Lib.alpha_core", "target", "Use/E.lean", "2", "0")])

    @case("A5b", "a theorem named by nobody is in uncalled.tsv; a named one is not")
    def _():
        _rc, _o, _e, tabs, _n = _go({**PUB_ALPHA, "Use/E.lean": "theorem z : P := Lib.alpha_core\n"})
        return _eq(_pairs(tabs, "uncalled", "name", "kind"), [("GlobalTheory.T.alpha", "alias")])

    @case("A5c", "`GlobalTheory.T.foo.bar` is not an occurrence of `GlobalTheory.T.foo`: no callers row, foo is uncalled")
    def _():
        _rc, _o, _e, tabs, _n = _go({"Pub/Foo.lean": "namespace GlobalTheory.T\n" + _W("foo", "L.x") + "end GlobalTheory.T\n",
                                     "Use/H.lean": "exact GlobalTheory.T.foo.bar\n"})
        return _eq((tabs["callers"][2], _pairs(tabs, "uncalled", "name", "kind")), ([], [("GlobalTheory.T.foo", "alias")]))

    @case("A5d", "a trailing dot after the name (end of a sentence) is trimmed: the name still counts, flagged as in a comment")
    def _():
        _rc, _o, _e, tabs, _n = _go({"Pub/Foo.lean": "namespace GlobalTheory.T\n" + _W("foo", "L.x") + "end GlobalTheory.T\n",
                                     "Use/I.lean": "-- see GlobalTheory.T.foo.\n"})
        return _eq(_pairs(tabs, "callers", "name", "kind", "file", "line", "in_comment"),
                   [("GlobalTheory.T.foo", "alias", "Use/I.lean", "1", "1")])

    @case("A5e", "a name on its own declaration line is not a caller; another line is")
    def _():
        _rc, _o, _e, tabs, _n = _go({"Pub/W.lean": _W("viaT", "Lib2.t"), "Lib2/T.lean": "theorem Lib2.t : P := sorry\n",
                                     "Use/G.lean": "-- x\nexact Lib2.t\n"})
        return _eq(_pairs(tabs, "callers", "name", "kind", "file", "line"), [("Lib2.t", "target", "Use/G.lean", "2")])

    @case("A5f", "an alias name used in code and in a comment: one row per line, in_comment 0 and 1")
    def _():
        _rc, _o, _e, tabs, _n = _go({**PUB_ALPHA, "Use/D.lean": "def x := GlobalTheory.T.alpha\n-- see GlobalTheory.T.alpha\n"})
        rows = [r for r in _pairs(tabs, "callers", "name", "kind", "file", "line", "in_comment") if r[1] == "alias"]
        return _eq(rows, [("GlobalTheory.T.alpha", "alias", "Use/D.lean", "1", "0"), ("GlobalTheory.T.alpha", "alias", "Use/D.lean", "2", "1")])

    @case("A5g", "an ambiguous target gets no callers row and no uncalled row; only the alias is uncalled")
    def _():
        _rc, _o, _e, tabs, _n = _go({"C1/M.lean": decl("NsC"), "C2/M.lean": decl("NsC"), "Pub/W.lean": _W("viaC", "NsC.main"),
                                     "Use/U.lean": "exact NsC.main\n"})
        return _eq((tabs["callers"][2], _pairs(tabs, "uncalled", "name", "kind")), ([], [("viaC", "alias")]))

    @case("PASS2", "exactly two passes: every file is read exactly twice")
    def _():
        _rc, _o, _e, _t, n = _go({**PUB_ALPHA, "Use/E.lean": "theorem z : P := Lib.alpha_core\n"}, count_reads=True)
        return _eq(n, 6)

    @case("HDR1", "all six TSVs start with the `#` provenance line then the column row; callers and uncalled carry the caveat")
    def _():
        _rc, _o, _e, tabs, _n = _go({**PUB_ALPHA, "Use/E.lean": "theorem z : P := Lib.alpha_core\n"})
        cols = dict(zip(TABLES, [ALIASES_COLS, ODD_COLS, CAND_COLS, REFS_COLS, CALLERS_COLS, UNCALLED_COLS]))
        bad = [n for n in TABLES
               if not (len(tabs[n][0]) > 1 and tabs[n][0][0].startswith("# alias_edges.py | source: ")
                       and tabs[n][0][1] == "\t".join(cols[n]))]
        caveat = all("not named in full anywhere" in tabs[n][0][0] for n in ("callers", "uncalled") if tabs[n][0])
        return _eq((bad, caveat and bool(tabs["callers"][0])), ([], True))

    @case("D1a", "SRC_ROOT that is not a directory: exit 2")
    def _():
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                rc = run(os.path.join(d, "nope"), os.path.join(d, "out"))
        return _eq(rc, 2)

    @case("D1b", "no .lean file under SRC_ROOT: `CHECKED NOTHING: no .lean file under SRC_ROOT`, exit 1")
    def _():
        rc, out, _e, _t, _n = _go({"readme.txt": "x"})
        return _eq((rc, "CHECKED NOTHING: no .lean file under SRC_ROOT" in out.splitlines()), (1, True))

    @case("D2a", "a file that does not decode: UNDECODABLE <relpath> printed and counted, exit 1, the other files still processed")
    def _():
        rc, out, _e, tabs, _n = _go({**PUB_ALPHA, "sub/Bad.lean": b"theorem \xff\n"})
        return _eq((rc, "UNDECODABLE sub/Bad.lean" in out.splitlines(), "undecodable 1" in out, len(tabs["aliases"][2])), (1, True, True, 1))

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
