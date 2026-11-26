#!/usr/bin/env python3
"""The skeleton of the map for a Lean repository that keeps its own index (CONTENTS.md) and its own folders.

STEP 1 OF THE BUILD: this file holds the cases and the names of the functions; the functions do not exist yet.
"""
import contextlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unicodedata

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    """A module of this folder, loaded by file path (never through sys.path), under a private name."""
    key = "_grh_skeleton_" + name
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, os.path.join(_HERE, name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            sys.modules.pop(key, None)
            raise
        finally:
            sys.dont_write_bytecode = keep
    return sys.modules[key]


bs = _load("build_site")


class Unreadable(Exception):
    """An input that cannot be read: exit 2."""


def kebab(s):
    raise NotImplementedError


def slug(s):
    raise NotImplementedError


def parse_contents(text):
    raise NotImplementedError


def _module_note(src_text):
    raise NotImplementedError


def _file_kind(src_text, note):
    raise NotImplementedError


def _folder_kind(child_kinds):
    raise NotImplementedError


def build_rows(grh):
    raise NotImplementedError


def build(grh, pin, strings):
    raise NotImplementedError


def main(argv):
    if argv[1:2] == ["--selftest"]:
        return _selftest_main(argv[2:])
    raise NotImplementedError


# ---------------------------------------------------------------- self-test: fixtures are built from literals in a temp folder

class _SkipCase(Exception):
    pass


_GRH_FOR_SK13 = None   # the folder given to `--selftest --grh`; SK13 reads it


def _eq(actual, expected):
    return actual == expected, f"expected {expected!r}, got {actual!r}"


PIN = "0123456789abcdef0123456789abcdef01234567"
HEAD = "# Contents\n\nIntro.\n\n## New\n\n"   # the body of a fixture CONTENTS starts on line 7
TAIL = "\n## Lib\n\n- `Lib/Other/File` (1): Not read\n"


def _lean(decl="theorem t : True := trivial", note="", imports=()):
    return "".join(f"import {m}\n" for m in imports) + (f"/-!\n{note}\n-/\n" if note else "") + decl + "\n"


def _tree(root, body, srcs):
    """Write <root>/grh/CONTENTS.md (HEAD, body, TAIL) and one src/<path>.lean per entry of `srcs` (path as in CONTENTS, e.g. New/A/B); return <root>/grh."""
    g = os.path.join(root, "grh")
    os.makedirs(g)
    with open(os.path.join(g, "CONTENTS.md"), "w", encoding="utf-8") as f:
        f.write(HEAD + body + TAIL)
    for p, text in list(srcs.items()) + [("Lib/Other/File", _lean())]:
        fp = os.path.join(g, "src", *p.split("/")) + ".lean"
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(text)
    return g


def _strings():
    with open(os.path.join(_HERE, os.pardir, "site", "strings.json"), encoding="utf-8") as f:
        return json.load(f)


def _tmp():
    return tempfile.TemporaryDirectory(prefix="grh-skel-")


def _rowtuples(rows):
    return [(r["id"], r["parent"], r["order"], r["premises"], r["kind"], r["title"]) for r in rows]


def _cli(argv):
    """(exit code, stdout, stderr) of main(argv)."""
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        rc = main(["build_grh_skeleton.py"] + argv)
    return rc, o.getvalue(), e.getvalue()


def _args(g, out, strings_path, pin=PIN):
    return ["--grh", g, "--pin", pin, "--strings", strings_path, "--out", out]


def _strings_file(d, s=None, name="strings.json"):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(_strings() if s is None else s, f)
    return p


def _tree_files(out):
    """{relative path: bytes} of every file under out."""
    res = {}
    for r, _, fs in os.walk(out):
        for n in fs:
            p = os.path.join(r, n)
            with open(p, "rb") as f:
                res[os.path.relpath(p, out).replace(os.sep, "/")] = f.read()
    return res


SK1_BODY = """### Alpha part

**First group**

- `New/Alpha/One` (10): The `one` file
- `New/Alpha/TwoParts` (20): Second file

**Second group**

- `New/Alpha/Three` (30): Third file

### Beta part

**Third group**

- `New/Beta/Four` (40): Fourth
- `New/Beta/Sub/Five` (50): Fifth
- `New/Beta/Six` (60): Sixth
"""
SK1_SRCS = {
    "New/Alpha/One": _lean("theorem a1 : True := trivial"),
    "New/Alpha/TwoParts": _lean("def a2 : Nat := 1", imports=["New.Alpha.One", "Mathlib.Foo"]),
    "New/Alpha/Three": _lean("theorem a3 : True := trivial", imports=["New.Alpha.TwoParts"]),
    "New/Beta/Four": _lean("def b4 : Nat := 1"),
    "New/Beta/Sub/Five": _lean("structure B5 where\n  x : Nat", imports=["New.Beta.Four"]),
    "New/Beta/Six": _lean("theorem b6 : True := trivial"),
}


def _selftest_cases():
    cases = []

    def case(cid, desc):
        def deco(fn):
            cases.append((cid, desc, fn))
            return fn
        return deco

    @case("SK1", "a fixture of 2 sections, 3 groups, 6 files: ids (kebab case of the folder and file names, `<section>--<slug>` for a group), parents, orders, "
                 "titles with the backticks removed, kinds (a folder has the kind of its LAST child), premises (in-group imports only), state none and proof "
                 "not_read for a file and none for a folder; `top` in file order, `steps` is the number of step files, every file passes the static check")
    def _():
        with _tmp() as d:
            g = _tree(d, SK1_BODY, SK1_SRCS)
            errs, files, rows, rep = build(g, PIN, _strings())
            ix = json.loads(files["graph/index.json"])
            steps = sorted(k for k in files if k.startswith("graph/step/"))
            ok, why = _eq((errs, _rowtuples(rows)), ([], [
                ("alpha", "root", 0, [], "theorem", "Alpha part"),
                ("alpha--first-group", "alpha", 0, [], "def", "First group"),
                ("alpha-one", "alpha--first-group", 0, [], "theorem", "The one file"),
                ("alpha-two-parts", "alpha--first-group", 1, ["alpha-one"], "def", "Second file"),
                ("alpha--second-group", "alpha", 1, [], "theorem", "Second group"),
                ("alpha-three", "alpha--second-group", 0, [], "theorem", "Third file"),
                ("beta", "root", 1, [], "theorem", "Beta part"),
                ("beta--third-group", "beta", 0, [], "theorem", "Third group"),
                ("beta-four", "beta--third-group", 0, [], "def", "Fourth"),
                ("beta-sub-five", "beta--third-group", 1, ["beta-four"], "structure", "Fifth"),
                ("beta-six", "beta--third-group", 2, [], "theorem", "Sixth")]))
            if not ok:
                return ok, why
            ok, why = _eq([(r["state"], r["proof"]) for r in rows],
                          [("none", "none"), ("none", "none"), ("none", "not_read"), ("none", "not_read"), ("none", "none"), ("none", "not_read"),
                           ("none", "none"), ("none", "none"), ("none", "not_read"), ("none", "not_read"), ("none", "not_read")])
            if not ok:
                return ok, why
            beta5 = json.loads(files["graph/step/beta-sub-five.json"])
            return _eq((ix["top"], ix["steps"], len(steps), ix["assets"], [tuple(sorted(r)) for r in rows[:1]],
                        beta5["path"], beta5["card"]["kind"], beta5["card"]["proof"], bs._graph_static_problems(files),
                        sorted(files) == ["graph/index.json"] + steps,
                        [c["id"] for c in json.loads(files["graph/step/alpha.json"])["children"]]),
                       (["alpha", "beta"], 11, 11, {}, [("id", "kind", "order", "parent", "premises", "proof", "state", "title")],
                        ["beta", "beta--third-group"], "structure", "not_read", [], True, ["alpha--first-group", "alpha--second-group"]))

    @case("SK2", "a section of one file with no folder (`New/Main`) is a TOP step that is that file: id `main`, a leaf in `top`, no section or group above it; a section "
                 "whose files have no group line gets one anonymous group whose id is `<section>--` and whose title is empty")
    def _():
        body = """### Alpha part

**G**

- `New/Alpha/One` (1): One

### No groups here

- `New/Anon/Solo` (2): Solo

### The last file

- `New/Main` (3): From here to there
"""
        srcs = {"New/Alpha/One": _lean(), "New/Anon/Solo": _lean("def s : Nat := 1"), "New/Main": _lean("theorem main_thm : True := trivial")}
        with _tmp() as d:
            g = _tree(d, body, srcs)
            errs, files, rows, rep = build(g, PIN, _strings())
            main_step = json.loads(files["graph/step/main.json"])
            return _eq((errs, _rowtuples(rows), json.loads(files["graph/index.json"])["top"], main_step["path"], main_step["children"], main_step["card"]["child_count"],
                        [r["proof"] for r in rows if r["id"] == "main"], sorted(k for k in files if "last" in k or "no-groups" in k)),
                       ([], [("alpha", "root", 0, [], "theorem", "Alpha part"), ("alpha--g", "alpha", 0, [], "theorem", "G"),
                             ("alpha-one", "alpha--g", 0, [], "theorem", "One"),
                             ("anon", "root", 1, [], "def", "No groups here"), ("anon--", "anon", 0, [], "def", ""),
                             ("anon-solo", "anon--", 0, [], "def", "Solo"),
                             ("main", "root", 2, [], "theorem", "From here to there")],
                        ["alpha", "anon", "main"], [], [], 0, ["not_read"], []))

    @case("SK3", "premises: a imports b, b imports c, a imports c inside one group: the group's rests_on has a->b and b->c only (a->c is reduced away); an import of a "
                 "file of another group, an import outside New and a self-import add no edge and are counted (self 1, cross-group 2, outside 2; edges 3, reduced 2); "
                 "a longer chain (a->b->c->d with a->c and a->d) reduces to the chain")
    def _():
        body = """### S part

**Grp**

- `New/S/A` (1): a
- `New/S/B` (1): b
- `New/S/C` (1): c

**Other**

- `New/S/D` (1): d
"""
        srcs = {"New/S/A": _lean(imports=["New.S.B", "New.S.C", "New.S.D", "New.S.A", "Mathlib.Data.Nat", "Lib.Foo.Bar"]),
                "New/S/B": _lean(imports=["New.S.C"]), "New/S/C": _lean(), "New/S/D": _lean(imports=["New.S.A"])}
        chain = """### T part

**Grp**

- `New/T/A` (1): a
- `New/T/B` (1): b
- `New/T/C` (1): c
- `New/T/D` (1): d
"""
        csrcs = {"New/T/A": _lean(imports=["New.T.B", "New.T.C", "New.T.D"]), "New/T/B": _lean(imports=["New.T.C"]), "New/T/C": _lean(imports=["New.T.D"]),
                 "New/T/D": _lean()}
        with _tmp() as d:
            g = _tree(d, body, srcs)
            errs, files, rows, rep = build(g, PIN, _strings())
            grp = json.loads(files["graph/step/s--grp.json"])
        with _tmp() as d:
            g = _tree(d, chain, csrcs)
            cerrs, cfiles, crows, crep = build(g, PIN, _strings())
        return _eq((errs, [(r["id"], r["premises"]) for r in rows if r["parent"] == "s--grp"], grp["rests_on"], grp["children"][0]["parent_rests_on"],
                    rep["edges"], rep["reduced"], rep["ignored"],
                    cerrs, [(r["id"], r["premises"]) for r in crows if r["parent"] == "t--grp"], (crep["edges"], crep["reduced"])),
                   ([], [("s-a", ["s-b"]), ("s-b", ["s-c"]), ("s-c", [])],
                    [{"from": "s-a", "from_path": ["s", "s--grp"], "to": "s-b", "to_path": ["s", "s--grp"]},
                     {"from": "s-b", "from_path": ["s", "s--grp"], "to": "s-c", "to_path": ["s", "s--grp"]}], False,
                    3, 2, {"self": 1, "cross_group": 2, "outside": 2},
                    [], [("t-a", ["t-b"]), ("t-b", ["t-c"]), ("t-c", ["t-d"]), ("t-d", [])], (5, 3)))

    @case("SK4", "a cycle among files of one group is refused GRAPH-EDGE (named, from _graph_files), also with a chord; nothing is written")
    def _():
        body = """### S part

**Grp**

- `New/S/A` (1): a
- `New/S/B` (1): b
"""
        srcs = {"New/S/A": _lean(imports=["New.S.B"]), "New/S/B": _lean(imports=["New.S.A"])}
        three = body + "- `New/S/C` (1): c\n"
        tsrcs = dict(srcs, **{"New/S/A": _lean(imports=["New.S.B", "New.S.C"]), "New/S/B": _lean(imports=["New.S.C"]), "New/S/C": _lean(imports=["New.S.A"])})
        with _tmp() as d:
            errs, files, rows, rep = build(_tree(d, body, srcs), PIN, _strings())
        with _tmp() as d:
            e3, f3, r3, rep3 = build(_tree(d, three, tsrcs), PIN, _strings())
        return _eq((errs, files, sorted({c for c, _, _ in e3}), bool(e3), f3),
                   ([("GRAPH-EDGE", "s-b s-a", "cycle in rests_on")], {}, ["GRAPH-EDGE"], True, {}))

    @case("SK5", "kinds: each of the 8 keywords maps as written (theorem, lemma -> theorem; def, abbrev, instance -> def; structure, class, inductive -> structure), also "
                 "behind @[...] and the modifiers private, protected, noncomputable, unsafe, partial; the name the module note gives wins over an earlier declaration "
                 "of another kind (also `New.` prefixed and dotted, and when the first name does not resolve); no resolving name uses the first declaration and is "
                 "counted as a fallback; a declaration that is indented, and a file with no declaration, give no kind")
    def _():
        kw = [("theorem t1 : True := trivial", "theorem"), ("lemma t2 : True := trivial", "theorem"), ("def t3 : Nat := 1", "def"), ("abbrev t4 := Nat", "def"),
              ("instance t5 : Inhabited Nat := ⟨0⟩", "def"), ("structure t6 where\n  x : Nat", "structure"), ("class t7 where\n  x : Nat", "structure"),
              ("inductive t8 where\n  | a", "structure")]
        got = [_file_kind(src, f"The `t{i + 1}` part") for i, (src, _) in enumerate(kw)]
        mods = [("@[simp] private lemma m1 : True := trivial", "m1", "theorem"), ("noncomputable def m2 : Nat := 1", "m2", "def"),
                ("protected theorem m3 : True := trivial", "m3", "theorem"), ("unsafe def m4 : Nat := 1", "m4", "def"),
                ("partial def m5 : Nat := 1", "m5", "def"), ("@[reducible, inline]\nabbrev m6 := Nat", "m6", "def"),
                ("private noncomputable def m7 : Nat := 1", "m7", "def"), ("@[simp] theorem m8 : True := trivial", "m8", "theorem"),
                ("@[simp] protected structure m9 where\n  x : Nat", "m9", "structure")]
        gotm = [_file_kind("/-! n -/\ndef zz : Nat := 1\n" + src + "\n", f"`{n}`") for src, n, _ in mods]
        two = "def helper : Nat := 1\ntheorem main_thm : True := trivial\n"
        qual = "def helper : Nat := 1\ntheorem Foo.bar_baz : True := trivial\n"
        return _eq((got, gotm,
                    _file_kind(two, "The `main_thm` result"), _file_kind(two, "`New.Foo.main_thm`"), _file_kind(two, "`ghost` and `main_thm`"),
                    _file_kind(qual, "`bar_baz`"), _file_kind(qual, "`Foo.bar_baz`"),
                    _file_kind(two, "`ghost`"), _file_kind(two, ""), _file_kind(two, "`a + b` and `helper`"),
                    _file_kind("instance : Inhabited Nat := ⟨0⟩\n", "`x`"),
                    _file_kind("-- nothing\n  theorem indented : True := trivial\n", "`indented`"), _file_kind("", "")),
                   ([(k, False) for _, k in kw], [(k, False) for _, _, k in mods],
                    ("theorem", False), ("theorem", False), ("theorem", False),
                    ("theorem", False), ("theorem", False),
                    ("def", True), ("def", True), ("def", False),
                    ("def", True), (None, False), (None, False)))

    @case("SK5b", "through the build: a file with no declaration is `SKEL-KIND <path>` (all of them, exit 1 in the CLI), a file whose note names nothing it declares "
                  "uses its first declaration and its path is listed as a fallback (once); the module note is the FIRST `/-!` block only")
    def _():
        body = """### S part

**Grp**

- `New/S/Fine` (1): fine
- `New/S/Fb` (1): fallback
- `New/S/Empty` (1): empty
"""
        srcs = {"New/S/Fine": _lean("theorem good : True := trivial", note="The `good` one"),
                "New/S/Fb": _lean("structure Thing where\n  x : Nat", note="The `ghost` one"),
                "New/S/Empty": "-- nothing here\n"}
        ok = body.replace("- `New/S/Empty` (1): empty\n", "")
        with _tmp() as d:
            errs, files, rows, rep = build(_tree(d, body, srcs), PIN, _strings())
        with _tmp() as d:
            e2, f2, r2, rep2 = build(_tree(d, ok, {k: v for k, v in srcs.items() if k != "New/S/Empty"}), PIN, _strings())
        return _eq((errs, files, e2, [(r["id"], r["kind"]) for r in r2 if r["parent"] == "s--grp"], rep2["fallback"],
                    _module_note("/- c -/\n/-! A `x` b -/\ndef y\n/-! two `y` -/\n"), _module_note("def y := 1\n"), _module_note("/-! never closed\n")),
                   ([("SKEL-KIND", "New/S/Empty", "")], {}, [], [("s-fine", "theorem"), ("s-fb", "structure")], ["New/S/Fb"],
                    " A `x` b ", "", ""))

    @case("SK6", "the kind of a folder is the kind of its LAST child, at both levels (group, then section); _folder_kind takes the kinds of the children")
    def _():
        body = """### P part

**G1**

- `New/P/P1` (1): p1
- `New/P/P2` (1): p2

**G2**

- `New/P/P3` (1): p3
- `New/P/P4` (1): p4
"""
        srcs = {"New/P/P1": _lean("structure P1 where\n  x : Nat"), "New/P/P2": _lean("def p2 : Nat := 1"), "New/P/P3": _lean("def p3 : Nat := 1"),
                "New/P/P4": _lean("structure P4 where\n  x : Nat")}
        with _tmp() as d:
            errs, files, rows, rep = build(_tree(d, body, srcs), PIN, _strings())
        return _eq((errs, [(r["id"], r["kind"]) for r in rows], _folder_kind(["def", "theorem", "structure"]), _folder_kind(["structure", "def"]),
                    _folder_kind(["theorem"])),
                   ([], [("p", "structure"), ("p--g1", "def"), ("p-p1", "structure"), ("p-p2", "def"), ("p--g2", "structure"), ("p-p3", "def"), ("p-p4", "structure")],
                    "structure", "def", "theorem"))

    @case("SK7", "completeness: a file listed in CONTENTS and not on disk is `SKEL-MISSING <path>` and a .lean file under src/New that is not listed is `SKEL-UNLISTED "
                 "<path>`, all of them in one run (missing in CONTENTS order, then unlisted sorted); in the CLI: exit 1, the lines on stdout, OUT not written; "
                 "a line of the New section that does not parse is `SKEL-LINE <n>` (n = its line in CONTENTS.md), and so is a file whose folder is not its section's")
    def _():
        body = """### S part

**Grp**

- `New/S/A` (1): a
- `New/S/B` (1): b
- `New/S/C` (1): c
"""
        srcs = {"New/S/A": _lean(), "New/S/Z": _lean(), "New/S/Y": _lean()}
        bad = """### Sec

**G**

- `New/S/A` (1): ok
This is a prose line.
- `New/S/B` 5: no parens
"""
        folders = """### Sec

**G**

- `New/S/A` (1): ok
- `New/T/B` (1): other folder
"""
        flat = """### Sec

**G**

- `New/X` (1): no folder
- `New/S/B` (1): has one
"""
        with _tmp() as d:
            g = _tree(d, body, srcs)
            errs = build_rows(g)[0]
            sp = _strings_file(d)
            rc, out, err = _cli(_args(g, os.path.join(d, "out"), sp))
            absent = not os.path.exists(os.path.join(d, "out"))
        lines = []
        for i, b in enumerate((bad, folders, flat)):
            with _tmp() as d2:
                lines.append(build_rows(_tree(d2, b, {}))[0])
        return _eq((errs, rc, out.splitlines(), absent, lines),
                   ([("SKEL-MISSING", "New/S/B", ""), ("SKEL-MISSING", "New/S/C", ""), ("SKEL-UNLISTED", "New/S/Y", ""), ("SKEL-UNLISTED", "New/S/Z", "")],
                    1, ["SKEL-MISSING New/S/B", "SKEL-MISSING New/S/C", "SKEL-UNLISTED New/S/Y", "SKEL-UNLISTED New/S/Z"], True,
                    [[("SKEL-LINE", "12", ""), ("SKEL-LINE", "13", "")], [("SKEL-LINE", "12", "")], [("SKEL-LINE", "11", "")]]))

    @case("SK8", "41 files in one group are refused GRAPH-FANOUT (named with the group id and the count), 40 are accepted and written")
    def _():
        def fx(n):
            body = "### W part\n\n**G**\n\n" + "".join(f"- `New/W/F{i:02d}` (1): f\n" for i in range(1, n + 1))
            return body, {f"New/W/F{i:02d}": _lean() for i in range(1, n + 1)}
        with _tmp() as d:
            e41, f41, r41, _r = build(_tree(d, *fx(41)), PIN, _strings())
        with _tmp() as d:
            e40, f40, r40, _r = build(_tree(d, *fx(40)), PIN, _strings())
        return _eq((e41, f41, e40, len(f40), json.loads(f40["graph/index.json"])["steps"]),
                   ([("GRAPH-FANOUT", "w--g", "has 41 children (more than 40)")], {}, [], 43, 42))

    @case("SK9", "ids: slug folds accents to ASCII (NFKD), lower-cases and turns every run of other characters into one `-`; two groups of one section whose titles "
                 "give one slug are GRAPH-DUP; a folder name that cannot make an id is GRAPH-ID (nothing is corrected); kebab: a lower-case letter before an upper-case "
                 "one gets `-`, `_` becomes `-`")
    def _():
        body = """### S part

**Alpha, beta**

- `New/S/A` (1): a

**Alpha beta!**

- `New/S/B` (1): b
"""
        under = "### U part\n\n**G**\n\n- `New/_Under/X` (1): x\n"
        with _tmp() as d:
            edup = build(_tree(d, body, {"New/S/A": _lean(), "New/S/B": _lean()}), PIN, _strings())[0]
        with _tmp() as d:
            eid = build(_tree(d, under, {"New/_Under/X": _lean()}), PIN, _strings())[0]
        return _eq((slug("Café, Théorème & `x`!"), slug("Mind's \"eye\""), slug("  --A  b--  "), slug("aθb"), kebab("OneLift"), kebab("UpperBound"), kebab("a_Bc"),
                    kebab("FieldsAndPlaces"), kebab("Main"), edup, [(c, w) for c, w, _ in eid]),
                   ("cafe-theoreme-x", "mind-s-eye", "a-b", "a-b", "one-lift", "upper-bound", "a-bc", "fields-and-places", "main",
                    [("GRAPH-DUP", "s--alpha-beta", "is the id of more than one group")],
                    [("GRAPH-ID", "-under"), ("GRAPH-ID", "-under--g"), ("GRAPH-ID", "-under-x")]))

    @case("SK10", "determinism and escaping: two runs under PYTHONHASHSEED 0 and 1 write byte-identical files; keys are sorted in every object; `<`, `>` and `&` are "
                  "escaped (a hostile title, `<img onerror>` with a backtick span, is escaped in the JSON); the `commit` of every file equals --pin")
    def _():
        hostile = "<img src=x onerror=alert(1)> & `code`"
        body = f"### S part\n\n**G**\n\n- `New/S/A` (1): {hostile}\n- `New/S/B` (1): b\n"
        srcs = {"New/S/A": _lean(), "New/S/B": _lean(imports=["New.S.A"])}
        with _tmp() as d:
            g = _tree(d, body, srcs)
            sp = _strings_file(d)
            runs = []
            for seed in ("0", "1"):
                out = os.path.join(d, "out" + seed)
                env = dict(os.environ, PYTHONHASHSEED=seed)
                r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, out, sp, pin="pinX"), env=env, capture_output=True, text=True)
                runs.append((r.returncode, _tree_files(out)))
        (rc0, f0), (rc1, f1) = runs
        sorted_ok = True

        def chk(pairs):
            nonlocal sorted_ok
            keys = [k for k, _ in pairs]
            sorted_ok = sorted_ok and keys == sorted(keys)
            return dict(pairs)
        for data in f0.values():
            json.loads(data.decode("utf-8"), object_pairs_hook=chk)
        step_a = f0["graph/step/s-a.json"]
        return _eq((rc0, rc1, f0 == f1, sorted(f0), sorted_ok,
                    b"\\u003cimg src=x onerror=alert(1)\\u003e \\u0026 code" in step_a,
                    [any(c in data for c in (b"<", b">", b"&")) for data in f0.values()].count(True),
                    sorted({json.loads(data)["commit"] for data in f0.values()})),
                   (0, 0, True, ["graph/index.json", "graph/step/s--g.json", "graph/step/s-a.json", "graph/step/s-b.json", "graph/step/s.json"], True, True, 0, ["pinX"]))

    @case("SK11", "exit codes: 0 built (OUT holds `graph` and nothing else), 1 refused (OUT absent after; a non-empty OUT is refused and left as it was; a strings file "
                  "without a key is refused as build_site refuses it, and the pure build reports GRAPH-STRINGS, no crash), 2 for a missing, repeated or unknown option, an empty --pin, or an input that cannot be read (a folder that is "
                  "not there, a strings file that is not JSON); a normal run does not run the self-test")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n"
        srcs = {"New/S/A": _lean()}
        with _tmp() as d:
            g = _tree(d, body, srcs)
            sp = _strings_file(d)
            out = os.path.join(d, "out")
            called = []
            real = globals()["selftest"]
            globals()["selftest"] = lambda *a, **k: called.append(1) or 4
            try:
                rc0 = _cli(_args(g, out, sp))
            finally:
                globals()["selftest"] = real
            listing = sorted(os.listdir(out))
            full = os.path.join(d, "full")
            os.makedirs(full)
            with open(os.path.join(full, "keep.txt"), "w") as f:
                f.write("x")
            rc_full = _cli(_args(g, full, sp))[0]
            held = sorted(os.listdir(full))
            nopin = _cli(["--grh", g, "--strings", sp, "--out", os.path.join(d, "o2")])
            dup = _cli(_args(g, os.path.join(d, "o3"), sp) + ["--pin", "x"])[0]
            unk = _cli(_args(g, os.path.join(d, "o4"), sp) + ["--force"])[0]
            emptypin = _cli(_args(g, os.path.join(d, "o5"), sp, pin=""))[0]
            nofolder = _cli(_args(os.path.join(d, "nothing"), os.path.join(d, "o6"), sp))[0]
            bad = os.path.join(d, "bad.json")
            with open(bad, "w") as f:
                f.write("{not json")
            notjson = _cli(_args(g, os.path.join(d, "o7"), bad))[0]
            s2 = _strings()
            del s2["sheet_proof_read"]
            nokey = _cli(_args(g, os.path.join(d, "o8"), _strings_file(d, s2, "strings2.json")))
            built_nokey = os.path.exists(os.path.join(d, "o8"))
            s3 = _strings()
            del s3["parts_n"]
            errs3 = build(g, PIN, s3)[0]
            absent = [os.path.exists(os.path.join(d, n)) for n in ("o2", "o3", "o4", "o5", "o6", "o7")]
        return _eq((rc0[0], rc0[1].splitlines()[:1] != [], called, listing, rc_full, held, nopin[0], nopin[1], nopin[2] != "", dup, unk, emptypin, nofolder, notjson,
                    nokey[0], nokey[1].splitlines(), built_nokey, errs3, absent),
                   (0, True, [], ["graph"], 1, ["keep.txt"], 2, "", True, 2, 2, 2, 2, 2,
                    1, ["STRINGS-KEY sheet_proof_read missing"], False, [("GRAPH-STRINGS", "parts_n", "missing")], [False] * 6))

    @case("SK12", "the written graph/index.json and every step file equal what build_site's _graph_files and _graph_bytes return for the rows (literal rows here): "
                  "the tool adds no key and drops none, and `assets` is {}")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n"
        srcs = {"New/S/A": _lean("def a : Nat := 1"), "New/S/B": _lean("theorem b : True := trivial", imports=["New.S.A"])}

        def row(i, parent, order, premises, kind, proof, title):
            return {"id": i, "parent": parent, "order": order, "premises": premises, "kind": kind, "state": "none", "proof": proof, "title": title}
        rows = [row("s", "root", 0, [], "theorem", "none", "S part"), row("s--g", "s", 0, [], "theorem", "none", "G"),
                row("s-a", "s--g", 0, [], "def", "not_read", "a"), row("s-b", "s--g", 1, ["s-a"], "theorem", "not_read", "b")]
        want_errs, want_objs = bs._graph_files(rows, PIN, _strings())
        want = bs._graph_bytes(want_objs)
        with _tmp() as d:
            g = _tree(d, body, srcs)
            sp = _strings_file(d)
            out = os.path.join(d, "out")
            rc = _cli(_args(g, out, sp))[0]
            got = _tree_files(out)
        return _eq((rc, want_errs, got == want, json.loads(got["graph/index.json"])["assets"], len(got)), (0, [], True, {}, 5))

    @case("SK13", "the real source (give `--selftest --grh DIR`; otherwise SKIPPED): 352 steps, top of 9 in order, widest 23, depth 3, in-group file edges 298 and "
                  "reduced 298, kinds over the steps theorem 190, def 127, structure 35, over the files 157, 115, 34, 14 fallback files, no refusal")
    def _():
        if _GRH_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh given to the self-test")
        errs, files, rows, rep = build(_GRH_FOR_SK13, "72fead102f663d5c7a407964a13dc0cf9d977207", _strings())
        return _eq((errs, rep["steps"], rep["top"], rep["widest"], rep["depth"], rep["edges"], rep["reduced"], rep["kinds_steps"], rep["kinds_files"], len(rep["fallback"]),
                    len(files)),
                   ([], 352, ["reduction", "derivatives", "upper-bound", "spanning", "determinant", "one-lift", "congruences", "appendix", "main"], 23, 3, 298, 298,
                    {"theorem": 190, "def": 127, "structure": 35}, {"theorem": 157, "def": 115, "structure": 34}, 14, 353))

    return cases


def selftest(verbose=True, only=None, grh=None):
    """Run the cases: 0 all pass (a skipped case does not fail), 4 one fails, 2 an unknown id in `only`. `grh` is the folder SK13 reads."""
    global _GRH_FOR_SK13
    cases = _selftest_cases()
    if only is not None:
        bad = [i for i in only if i not in {c[0] for c in cases}]
        if bad or not only:
            print("unknown case id: " + ", ".join(bad) if bad else "no case id given", file=sys.stderr)
            return 2
        cases = [c for c in cases if c[0] in only]
    ok, skipped, before = True, 0, _GRH_FOR_SK13
    _GRH_FOR_SK13 = grh
    try:
        for cid, desc, fn in cases:
            try:
                good, detail = fn()
            except _SkipCase as e:
                skipped += 1
                if verbose:
                    print(f"CASE {cid} SKIP {e}")
                continue
            except Exception as e:   # a crash is a failed case, not a skipped one
                good, detail = False, f"{type(e).__name__}: {e}"
            ok = ok and bool(good)
            if verbose:
                print(f"CASE {cid} {'PASS' if good else 'FAIL'} {desc}")
                if not good:
                    print(f"  detail: {detail}")
    finally:
        _GRH_FOR_SK13 = before
    if verbose:
        print("SELFTEST " + ("PASS" if ok else "FAIL") + (f" ({skipped} skipped)" if ok and skipped else ""))
    return 0 if ok else 4


def _selftest_main(rest):
    """`--selftest [--only ID,ID] [--grh DIR]`, in either order, each once."""
    only = grh = None
    i = 0
    while i < len(rest):
        if rest[i] == "--only" and only is None and i + 1 < len(rest):
            only = [x for x in rest[i + 1].split(",") if x]
        elif rest[i] == "--grh" and grh is None and i + 1 < len(rest):
            grh = rest[i + 1]
        else:
            return 2
        i += 2
    return selftest(only=only, grh=grh)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
