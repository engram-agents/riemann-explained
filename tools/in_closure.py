#!/usr/bin/env python3
"""Which of a list of sites lie in the import closure of a start module? (a necessary condition only)

EDGES_TSV is the edges.tsv written by scan_graph.py: lines starting with `#` are skipped, the first other
line is the column row `importer<TAB>imported`, every later non-empty line is one edge. The known modules are
the names in either column. The closure is found by a breadth-first walk from START_MODULE along importer ->
imported edges, keeping one parent per module so one SHORTEST import path can be printed.

SITES_FILE has one site per non-empty line. The site token is the text before the first `:` on the line,
stripped. A trailing `.lean` is dropped and `/` becomes `.`; if the result is a known module, that is the
module. Otherwise a token with no `.` matches every known module whose last component equals it; a dotted
token that is not a known module is not a module.

CONTRACT
 C1 At least one --control is REQUIRED; without one the tool says why and exits 2.
 C2 If any control is not in the closure (or is not a known module) it prints `BROKEN: <control name>` for
    each, prints NO site verdicts, and exits 3.
 C3 START_MODULE and every control are matched as FULL module names (START not a known module: exit 2). A site
    given as a bare name that matches more than one module is printed `AMBIGUOUS <token>` followed by every
    candidate (full module names), gets no verdict, and the exit code is 1. A bare name that matches exactly
    one module gets that module's verdict.
 C4 Each site gets `INSIDE <module>   path: A <- B <- C` (a shortest import path in FULL module names, from the
    site back to START) or `OUTSIDE <module>`. The output header lines state: INSIDE means "compiled before
    START, so it may be used", never "is used"; OUTSIDE means START's proofs cannot use it. A site repeated
    in the file is printed once.
 C5 A site that is not a known module (typo, wrong folder) is printed `NOT A MODULE <token>` and the exit code
    is 1. It is never printed OUTSIDE.
 C6 A SITES_FILE with no site prints `CHECKED NOTHING: no site in SITES_FILE` and exits 1.
 Exit 0 only if every site got INSIDE or OUTSIDE. Exit 2 is a usage or input error, 3 a broken control,
 4 a failed self-test. With --selftest the tool plants small edges files, checks each contract line as its own
 CASE, prints one `CASE <id> PASS|FAIL` line each and a final `SELFTEST PASS|FAIL`; exit 0 or 4. A normal run
 does the same quietly first and refuses (exit 4, nothing else reported) if it fails.

LIMIT. Modules are known only from EDGES_TSV, so a real file with no internal import in or out cannot be told
from a typo and is printed NOT A MODULE (loud on purpose). INSIDE says the module is compiled before START,
so START's proofs may use it; it never says they do.

usage: in_closure.py EDGES_TSV START_MODULE SITES_FILE --control MODULE [--control MODULE ...]
       in_closure.py --selftest
"""
import collections
import contextlib
import io
import os
import sys
import tempfile

HEADER = [
    '# INSIDE means: compiled before START, so it may be used, never "is used".',
    "# OUTSIDE means: START's proofs cannot use it.",
]


# ---------------------------------------------------------------- the tool (STUB)

def parse_args(a):
    return None


def load_edges(path):
    return {}, set()


def main_run(edges_path, start, sites_path, controls):
    return 0


# ---------------------------------------------------------------- self-test

CHAIN = ["Chain.M1\tChain.M2", "Chain.M2\tChain.M3", "Chain.M3\tChain.M4", "Chain.M4\tChain.M5", "Side.Z\tChain.M3"]


def _go(edge_rows, start, sites, controls, edges_text=None, argv_extra=None):
    with tempfile.TemporaryDirectory() as d:
        e, s = os.path.join(d, "edges.tsv"), os.path.join(d, "sites.txt")
        with open(e, "w", encoding="utf-8") as f:
            f.write(edges_text if edges_text is not None
                    else "# edges | source: unversioned| x\nimporter\timported\n" + "".join(r + "\n" for r in edge_rows))
        with open(s, "w", encoding="utf-8") as f:
            f.write("".join(x + "\n" for x in sites))
        argv = ["in_closure.py", e, start, s]
        for c in controls:
            argv += ["--control", c]
        argv += argv_extra or []
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = main(argv, selftest_first=False)
        return rc, buf.getvalue().split("\n"), err.getvalue()


def _eq(actual, expected):
    return actual == expected, f"expected {expected!r}, got {actual!r}"


def _verdicts(lines):
    return [ln for ln in lines if ln.split(" ")[0] in ("INSIDE", "OUTSIDE", "AMBIGUOUS", "NOT")]


def _selftest_cases():
    cases = []

    def case(cid, desc):
        def deco(fn):
            cases.append((cid, desc, fn))
            return fn
        return deco

    M4 = "INSIDE Chain.M4   path: Chain.M4 <- Chain.M3 <- Chain.M2 <- Chain.M1"

    @case("C4a", "a five-module chain: INSIDE with the exact full-name shortest path for M4, exit 0")
    def _():
        rc, out, _e = _go(CHAIN, "Chain.M1", ["Chain.M4"], ["Chain.M3"])
        return _eq((rc, _verdicts(out)), (0, [M4]))

    @case("C4b", "a side branch that is not on the chain is OUTSIDE")
    def _():
        rc, out, _e = _go(CHAIN, "Chain.M1", ["Side.Z"], ["Chain.M3"])
        return _eq((rc, _verdicts(out)), (0, ["OUTSIDE Side.Z"]))

    @case("C4c", "a site repeated in the file (as module, path, and with a position) is printed once")
    def _():
        rc, out, _e = _go(CHAIN, "Chain.M1", ["Chain.M4", "Chain/M4.lean:3", "Chain.M4:5"], ["Chain.M3"])
        return _eq((rc, _verdicts(out)), (0, [M4]))

    @case("C4d", "the header lines say what INSIDE and OUTSIDE mean")
    def _():
        rc, out, _e = _go(CHAIN, "Chain.M1", ["Chain.M4"], ["Chain.M3"])
        return _eq((HEADER[0] in out, HEADER[1] in out), (True, True))

    @case("C4e", "the start module as a site is INSIDE with a one-element path")
    def _():
        _rc, out, _e = _go(CHAIN, "Chain.M1", ["Chain.M1"], ["Chain.M3"])
        return _eq(_verdicts(out), ["INSIDE Chain.M1   path: Chain.M1"])

    @case("C4f", "the printed path is a shortest one")
    def _():
        rows = ["M1\tX1", "X1\tD", "M1\tY1", "Y1\tY2", "Y2\tD"]
        _rc, out, _e = _go(rows, "M1", ["D"], ["Y2"])
        return _eq(_verdicts(out), ["INSIDE D   path: D <- X1 <- M1"])

    @case("C4g", "the summary line counts the verdicts")
    def _():
        _rc, out, _e = _go(CHAIN, "Chain.M1", ["Chain.M4", "Side.Z"], ["Chain.M3"])
        return _eq("sites 2: inside 1 / outside 1 / ambiguous 0 / not a module 0" in out, True)

    @case("C1a", "no --control: exit 2, a message about controls, no verdict")
    def _():
        rc, out, err = _go(CHAIN, "Chain.M1", ["Chain.M4"], [])
        return _eq((rc, "control" in (err + "\n".join(out)).lower(), _verdicts(out)), (2, True, []))

    @case("C2a", "a control off the chain: exit 3, BROKEN named, and no INSIDE/OUTSIDE anywhere in the output")
    def _():
        rc, out, _e = _go(CHAIN, "Chain.M1", ["Chain.M4"], ["Chain.M3", "Side.Z"])
        text = "\n".join(out)
        return _eq((rc, "BROKEN: Side.Z" in out, "INSIDE" in text, "OUTSIDE" in text), (3, True, False, False))

    @case("C2b", "a control that is not a known module is BROKEN too; every broken control is named")
    def _():
        rc, out, _e = _go(CHAIN, "Chain.M1", ["Chain.M4"], ["Nope.X", "Chain.M3", "Side.Z"])
        return _eq((rc, [ln for ln in out if ln.startswith("BROKEN")]), (3, ["BROKEN: Nope.X", "BROKEN: Side.Z"]))

    @case("C3a", "a bare name matching two modules: AMBIGUOUS, both candidates, no verdict line for it, exit 1")
    def _():
        rows = ["M1\tDir1.Util", "M1\tDir2.Util"]
        rc, out, _e = _go(rows, "M1", ["Util"], ["Dir1.Util"])
        i = out.index("AMBIGUOUS Util") if "AMBIGUOUS Util" in out else -1
        return _eq((rc, out[i + 1:i + 3], [v for v in _verdicts(out) if not v.startswith("AMBIGUOUS")]),
                   (1, ["  Dir1.Util", "  Dir2.Util"], []))

    @case("C3b", "a bare name matching exactly one module gets that module's verdict, exit 0")
    def _():
        rc, out, _e = _go(CHAIN, "Chain.M1", ["M4"], ["Chain.M3"])
        return _eq((rc, _verdicts(out)), (0, [M4]))

    @case("C3c", "a site given as Dir/File.lean:12:3 is resolved")
    def _():
        rc, out, _e = _go(CHAIN, "Chain.M1", ["Chain/M4.lean:12:3"], ["Chain.M3"])
        return _eq((rc, _verdicts(out)), (0, [M4]))

    @case("C3d", "START given as a bare name is not matched: exit 2")
    def _():
        rc, out, _e = _go(CHAIN, "M1", ["Chain.M4"], ["Chain.M3"])
        return _eq((rc, _verdicts(out)), (2, []))

    @case("C3e", "a control given as a bare name is not matched: BROKEN, exit 3")
    def _():
        rc, out, _e = _go(CHAIN, "Chain.M1", ["Chain.M4"], ["M3"])
        return _eq((rc, "BROKEN: M3" in out), (3, True))

    @case("C3f", "a bare name that is itself a known module wins over other modules ending in that name")
    def _():
        rows = ["M1\tUtil", "M1\tDir.Util"]
        rc, out, _e = _go(rows, "M1", ["Util"], ["Util"])
        return _eq((rc, _verdicts(out)), (0, ["INSIDE Util   path: Util <- M1"]))

    @case("C5a", "a misspelt site and an unknown bare name are NOT A MODULE, never OUTSIDE, exit 1")
    def _():
        rc, out, _e = _go(CHAIN, "Chain.M1", ["Chian.M4", "M44", "Chain.M4"], ["Chain.M3"])
        return _eq((rc, _verdicts(out)), (1, ["NOT A MODULE Chian.M4", "NOT A MODULE M44", M4]))

    @case("C5b", "a dotted suffix-only name is NOT A MODULE")
    def _():
        rows = ["M1\tLib.Dir1.Util"]
        rc, out, _e = _go(rows, "M1", ["Dir1.Util"], ["Lib.Dir1.Util"])
        return _eq((rc, _verdicts(out)), (1, ["NOT A MODULE Dir1.Util"]))

    @case("C6a", "a SITES_FILE with no site: CHECKED NOTHING, exit 1")
    def _():
        rc, out, _e = _go(CHAIN, "Chain.M1", ["", "   "], ["Chain.M3"])
        return _eq((rc, "CHECKED NOTHING: no site in SITES_FILE" in out), (1, True))

    @case("E1", "the `#` line and the column row are skipped, not read as edges or modules")
    def _():
        rc, out, _e = _go(CHAIN, "Chain.M1", ["importer", "Chain.M4"], ["Chain.M3"])
        return _eq((rc, _verdicts(out)), (1, ["NOT A MODULE importer", M4]))

    @case("E2", "an edge row that is not two tab-separated names: exit 2")
    def _():
        rc, out, _e = _go(None, "Chain.M1", ["Chain.M4"], ["Chain.M3"],
                          edges_text="# x\nimporter\timported\nChain.M1\tChain.M2\tx\n")
        return _eq((rc, _verdicts(out)), (2, []))

    @case("E3", "a column row that is not `importer<TAB>imported`: exit 2")
    def _():
        rc, out, _e = _go(None, "Chain.M1", ["Chain.M4"], ["Chain.M3"], edges_text="# x\na\tb\nChain.M1\tChain.M2\n")
        return _eq((rc, _verdicts(out)), (2, []))

    @case("USE1", "a --control with no value: exit 2")
    def _():
        with tempfile.TemporaryDirectory() as d:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                rc = main(["in_closure.py", os.path.join(d, "e"), "M1", os.path.join(d, "s"), "--control"], selftest_first=False)
        return _eq(rc, 2)

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


def main(a, selftest_first=True):
    if a[1:] == ["--selftest"]:
        return selftest()
    parsed = parse_args(a)
    if parsed is None:
        return 0
    if selftest_first and selftest_quiet() != 0:
        print("REFUSED: selftest failed; no result reported", file=sys.stderr)
        return 4
    return main_run(*parsed)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
