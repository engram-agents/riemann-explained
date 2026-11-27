#!/usr/bin/env python3
"""Alias layer of the proof map, from text only.

An alias is a theorem whose whole proof is the wrapper
  `first | exact @X | exact X | (intros; apply X <;> assumption)`
(the three X equal). This tool finds the aliases, resolves each X to the file and line that declares it,
and lists where the alias names and the targets are written out in full.

Outputs under OUT_DIR (each starts with a `#` provenance line, then the column row):
  aliases.tsv           public_name, target, file, line, target_file, target_line, target_matches
  aliases_odd.tsv       public_name, x1, x2, x3, file, line, reason, tail   (wrapper shape that is not an exact
                        wrapper: reason unequal_x or trailing_text; tail = the trailing text with whitespace runs
                        collapsed, cut to 80 characters)
  alias_candidates.tsv  public_name, target, candidate_file, candidate_line   (only when target_matches >= 2)
  refs.tsv              file, public_name, occurrences, in_comment_only
  callers.tsv           name, kind (alias|target), file, line, in_comment (0|1)
  uncalled.tsv          name, kind

CONTRACT
 A1 Every theorem (or lemma) in ANY .lean file whose body is exactly the wrapper shape with the three X equal
    yields one row in aliases.tsv (public name, target X, file, line). Several per file are allowed. The body
    is the text after the LAST `:= by` that is directly followed by `first | exact @` and sits outside any
    bracket (a binder default proof such as `(h : P := by assumption)` is part of the signature and ignored),
    within the declaration's extent; the extent runs from its line to the line
    before the next column-0 declaration keyword, `end`, `namespace`, `section`, `open`, `set_option`,
    `attribute`, `variable`, `universe`, `noncomputable`, `@[`, `/-` (also the modifiers private, protected,
    nonrec, unsafe, partial, `mutual`, and example, axiom, opaque, macro, syntax, notation, local, scoped,
    export, deriving, initialize, #check, #print, #eval), or to the end of the file. Whitespace around the tokens may vary.
 A2 A theorem whose body has the shape at its start but is not an exact equal-X wrapper is listed in
    aliases_odd.tsv, not dropped: reason `unequal_x` (the X differ) or `trailing_text` (equal X, then more
    non-blank text, e.g. a second chain). It is not in aliases.tsv.
 A3 Each target is resolved to its DECLARING file and line. A target X written inside `namespace N1..Nk`
    (the wrapper's enclosing namespace components, from the scope stack below) is looked up as a declaration
    whose full name is N1..Nk.X, then N1..Nk-1.X, ..., then X; the FIRST level with any declaration decides,
    and the count is taken at that level only (an outer level is never consulted once an inner one matches).
    `_root_.X` is looked up as X only (one leading `_root_.` is stripped, nothing else). The `target` column
    keeps X as written; callers.tsv and uncalled.tsv name the full name of the deciding level.
    target_matches = number of declarations found at the deciding level: 0 = UNRESOLVED, 1 = resolved, 2 or more = AMBIGUOUS; for
    2 or more every candidate is written to alias_candidates.tsv and target_file/target_line are `-`. The tool
    never picks one. The summary line prints `targets resolved N / ambiguous N / unresolved N`, counted per
    alias row. The full name is the enclosing `namespace` names plus the declared name; `_root_.` means no
    namespace prefix. The scope stack has one entry per namespace component (`namespace A.B.C` pushes three,
    `section`, `noncomputable section` and `mutual` push one); `end N1.N2...Nk` pops k entries and a bare
    `end` pops one section entry if the top is one, else nothing. Structure is read from the comment-masked text, so a declaration inside a comment is
    not a candidate.
 A4 refs.tsv: for every file and every distinct token `GlobalTheory.T.<name>` that is a known public name under
    `GlobalTheory.T.`, one row (the file that holds the name's own wrapper is skipped), with in_comment_only = 1
    when every occurrence in that file sits inside a line or block comment.
 A5 callers.tsv: for every alias public name and every resolved (matches = 1) target full name, the files and
    lines where that exact full name occurs as a whole dotted token (maximal run of `[\\w'.₀-₉]` characters with
    trailing dots trimmed), outside its own declaration line and outside the alias wrapper's own lines, from the
    `first | exact @` line through the line where the shape ends, where the wrapper names its own target (that
    is the alias link itself, already in aliases.tsv; any other name or line is kept); one row per file and line, in_comment = 1 when
    every occurrence on that line is inside a comment. A name with no row is listed in uncalled.tsv.
 D1 SRC_ROOT not a directory: exit 2. No `.lean` file: `CHECKED NOTHING: no .lean file under SRC_ROOT`, exit 1.
 D2 A file that does not decode is printed as `UNDECODABLE <relpath>`, one that cannot be read at all as
    `UNREADABLE <relpath>`; both are counted in the summary (`undecodable`) and the exit code is 1.
 Two passes over the files: pass 1 finds the wrappers and the target set; pass 2 collects the declarations for
 the full names in the target set and tokenizes for A4 and A5 with one regex scan per file.
 With --selftest it plants temporary trees, checks each contract line as its own CASE, prints one
 `CASE <id> PASS|FAIL` line each and a final `SELFTEST PASS|FAIL`; exit 0 or 4. A normal run does the same
 quietly first and refuses (exit 4, nothing else reported) if it fails.

LIMIT. A run that checks nothing (no `.lean` file) writes nothing, so an output file left in OUT_DIR by an earlier run is
still there, and a tool that reads OUT_DIR next cannot tell it from this run's; the run names such files on stdout
(STALE1) and keeps exit 1, it does not delete them.
A target is looked up through the wrapper's own enclosing namespaces (innermost first, then outward
to the root; the first level with a declaration decides). Not modelled: `open`, `export`, aliases, shorter
names and dot notation, so a target that relies on one of them stays UNRESOLVED or resolves at the wrong
level only if a declaration of the written name exists at another level.
A reference is a text match on the fully written name; a use through an opened namespace, a shorter
name or dot notation is not seen, so `uncalled` means "not named in full anywhere", not "unused". Names
inside comments are matched (flagged by in_comment). A declaration is recognised by its keyword at a line
start; names built by macros, `private` name mangling and structure fields are not seen. The shape must be
written as above; a differently written alias is not found. A string literal is not special-cased when
comments are masked. Refs (A4) use the token `GlobalTheory.T.<name>` as written, so a longer dotted name
that starts with a known public name also counts for the shorter one there, while callers (A5) do not.
Names that end in `!` or `?` are not matched by the callers token rule. The bracket counting that finds a
wrapper's body is not string-aware: a bracket inside a string literal can hide a wrapper, silently. A UTF-8
byte-order mark at the start of a file is not removed.

usage: alias_edges.py SRC_ROOT OUT_DIR
       alias_edges.py --selftest
"""

import sys
if sys.version_info[:2] < (3, 12):
    raise SystemExit("alias_edges.py: needs Python 3.12 or newer (tested with 3.12); this is %d.%d.%d at %s" % (sys.version_info[0], sys.version_info[1], sys.version_info[2], sys.executable))

import collections
import contextlib
import io
import os
import re
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scan_graph import failure_word, mask_comments, provenance, read_text, report_stale_output, walk_lean  # noqa: E402
from lean_decls import parse_decls  # noqa: E402

ALIASES_COLS = ["public_name", "target", "file", "line", "target_file", "target_line", "target_matches"]
ODD_COLS = ["public_name", "x1", "x2", "x3", "file", "line", "reason", "tail"]
CAND_COLS = ["public_name", "target", "candidate_file", "candidate_line"]
REFS_COLS = ["file", "public_name", "occurrences", "in_comment_only"]
CALLERS_COLS = ["name", "kind", "file", "line", "in_comment"]
UNCALLED_COLS = ["name", "kind"]


# ---------------------------------------------------------------- the tool

WRAP_QUICK = re.compile(r"first\s*\|\s*exact\s+@")
WRAP = re.compile(r"first\s*\|\s*exact\s+@([^\s|]+)\s*\|\s*exact\s+([^\s|]+)\s*\|\s*"
                  r"\(\s*intros\s*;\s*apply\s+([^\s<]+)\s*<;>\s*assumption\s*\)")
BY_SHAPE = re.compile(r":=\s*by\s+(?=first\s*\|\s*exact\s+@)")
OPEN, CLOSE = "([{\u27e8", ")]}\u27e9"
RUN = re.compile(r"[\w'.₀-₉]+")
TOK = re.compile(r"GlobalTheory\.T\.[A-Za-z_][\w'₀-₉]*")
PUB = "GlobalTheory.T."


def target_levels(x, ns):
    """The full names a target written X can mean, innermost first: N1..Nk.X, ..., N1.X, X. A target written
    `_root_.X` means X only."""
    if x.startswith("_root_."):
        return [x[len("_root_."):]]
    return [".".join(ns[:i]) + "." + x if i else x for i in range(len(ns), -1, -1)]


def norm_target(x):
    """A target written `_root_.X` is the root name X: strip one leading `_root_.`, nothing else."""
    return x[len("_root_."):] if x.startswith("_root_.") else x


def find_wrappers(raw, masked):
    """([(public, x, line, (first_line, last_line), namespaces)] exact wrappers, the span being the wrapper's own lines, [(public, x1, x2, x3, line, reason, tail)] odd shapes).
    reason is `unequal_x` (the three X differ) or `trailing_text` (equal X, more non-blank text follows; tail is
    that text with whitespace runs collapsed, cut to 80 characters)."""
    good, odd = [], []
    if not WRAP_QUICK.search(masked):
        return good, odd
    ml = masked.split("\n")
    for line_no, kind, full, end, ns in parse_decls(raw, masked):
        if kind not in ("theorem", "lemma"):
            continue
        extent = "\n".join(ml[line_no - 1:end])
        start = None
        for b in BY_SHAPE.finditer(extent):
            head = extent[:b.start()]
            if sum(head.count(c) for c in OPEN) == sum(head.count(c) for c in CLOSE):   # not inside a binder
                start = b.end()
        if start is None:
            continue
        body = extent[start:].strip()
        m = WRAP.match(body)
        if not m:
            continue
        x1, x2, x3 = m.groups()
        tail = " ".join(body[m.end():].split())[:80]
        if x1 != x2 or x2 != x3:
            odd.append((full, x1, x2, x3, line_no, "unequal_x", tail))
        elif tail:
            odd.append((full, x1, x2, x3, line_no, "trailing_text", tail))
        else:
            first = line_no + extent.count("\n", 0, start)
            last = line_no + extent.count("\n", 0, start + m.end() - 1)
            good.append((full, x1, line_no, (first, last), ns))
    return good, odd


def write_tsv(out, name, header, cols, rows):
    with open(os.path.join(out, name + ".tsv"), "w", encoding="utf-8", newline="\n") as f:
        f.write(header + "\n" + "\t".join(cols) + "\n")
        for r in rows:
            f.write("\t".join(str(x) for x in r) + "\n")


def run(root, out):
    root = root.rstrip(os.sep) or root
    if not os.path.isdir(root):
        print(f"SRC_ROOT is not a directory: {root}", file=sys.stderr)
        return 2
    mods = walk_lean(root)
    if not mods:
        print("CHECKED NOTHING: no .lean file under SRC_ROOT")
        report_stale_output(out, [n + ".tsv" for n in TABLES])
        return 1
    os.makedirs(out, exist_ok=True)
    rel = {p: os.path.relpath(p, root).replace(os.sep, "/") for _, p in mods}
    undecodable = []
    # pass 1: wrappers and the target set
    aliases, odd = [], []          # aliases: (public, target as written, file, line, namespaces, (first, last) wrapper lines)
    for _, p in mods:
        text, ok = read_text(p)
        if not ok:
            undecodable.append((failure_word(p), rel[p]))
            continue
        good, bad = find_wrappers(text, mask_comments(text))
        aliases += [(pub, x, rel[p], ln, ns, span) for pub, x, ln, span, ns in good]
        odd += [(pub, x1, x2, x3, rel[p], ln, why, tail) for pub, x1, x2, x3, ln, why, tail in bad]
    targets = {n for a in aliases for n in target_levels(a[1], a[4])}   # every full name a target may mean
    alias_names = {a[0] for a in aliases}
    names = targets | alias_names
    pub_t = {n for n in alias_names if n.startswith(PUB)}
    wrapper_files = collections.defaultdict(set)
    for pub, _x, f, _ln, _ns, _span in aliases:
        wrapper_files[pub].add(f)
    # pass 2: declarations of the targets, and the tokens of A4 / A5
    cands = collections.defaultdict(list)
    occ = collections.defaultdict(list)             # name -> [(file, line, in_comment)]
    refs = collections.defaultdict(lambda: [0, 0])  # (file, public) -> [occurrences, occurrences in code]
    if aliases:
        for _, p in mods:
            text, ok = read_text(p)
            if not ok:
                continue
            masked = mask_comments(text)
            for line_no, _kind, full, _end, _ns in parse_decls(text, masked):
                if full in targets:
                    cands[full].append((rel[p], line_no))
            for m in RUN.finditer(text):
                tok = m.group().rstrip(".")
                if tok in names:
                    occ[tok].append((rel[p], text.count("\n", 0, m.start()) + 1, int(masked[m.start()] != text[m.start()])))
                if PUB in tok:
                    for t in TOK.finditer(tok):
                        if t.group() in pub_t:
                            pos = m.start() + t.start()
                            c = refs[(rel[p], t.group())]
                            c[0] += 1
                            c[1] += int(masked[pos] == text[pos])
    # outputs
    alias_rows, cand_rows, counts = [], [], collections.Counter()
    deciding = []   # (public, file, line, wrapper span, target as written, deciding full name) for each resolved alias
    for pub, x, f, ln, ns, span in sorted(aliases, key=lambda a: (a[0], a[2], a[3])):
        level = next((n for n in target_levels(x, ns) if cands.get(n)), None)   # the first level with any declaration decides
        c = sorted(cands.get(level, [])) if level else []
        if len(c) == 1:
            deciding.append((pub, f, ln, span, x, level))
            alias_rows.append((pub, x, f, ln, c[0][0], c[0][1], 1))
            counts["resolved"] += 1
        else:
            alias_rows.append((pub, x, f, ln, "-", "-", len(c)))
            counts["ambiguous" if c else "unresolved"] += 1
            cand_rows += [(pub, x, cf, cl) for cf, cl in c]
    ref_rows = [(f, n, v[0], int(v[1] == 0)) for (f, n), v in sorted(refs.items()) if f not in wrapper_files[n]]
    decl_lines = collections.defaultdict(set)
    for pub, _x, f, ln, _ns, _span in aliases:
        decl_lines[(pub, "alias")].add((f, ln))
    universe = {(n, "alias") for n in alias_names}
    wrap_hits = set()   # (file, line, name): a wrapper's own text naming its own target, which is the alias link itself
    for pub, f, _ln, (first, last), x, level in deciding:
        universe.add((level, "target"))
        decl_lines[(level, "target")].add(cands[level][0])
        wrap_hits.update((f, l, n) for l in range(first, last + 1) for n in (norm_target(x), pub, level))
    caller_rows, uncalled_rows = [], []
    for n, kind in sorted(universe):
        per_line = {}
        for f, ln, inc in occ.get(n, []):
            if (f, ln) in decl_lines[(n, kind)] or (f, ln, n) in wrap_hits:
                continue
            per_line[(f, ln)] = min(per_line.get((f, ln), 1), inc)
        for (f, ln), inc in sorted(per_line.items()):
            caller_rows.append((n, kind, f, ln, inc))
        if not per_line:
            uncalled_rows.append((n, kind))
    caveat = ("a full-name text match; a use through an opened namespace, a shorter name or dot notation is not seen, "
              "so `uncalled` means \"not named in full anywhere\", not \"unused\"")
    tool = "alias_edges.py"
    write_tsv(out, "aliases", provenance(tool, root, "a row says the theorem's whole proof is the wrapper around the target, "
                                         "not that the target proves the same statement"), ALIASES_COLS, alias_rows)
    write_tsv(out, "aliases_odd", provenance(tool, root, "a row has the wrapper shape but is not an exact equal-name wrapper (reason says how); it is listed, not judged"),
              ODD_COLS, sorted(odd))
    write_tsv(out, "alias_candidates", provenance(tool, root, "a row is one declaration of the target's full name; none is chosen "
                                                  "as the target"), CAND_COLS, cand_rows)
    write_tsv(out, "refs", provenance(tool, root, "a row says the file writes the public name out in full, not that any proof "
                                      "there uses it"), REFS_COLS, ref_rows)
    write_tsv(out, "callers", provenance(tool, root, caveat), CALLERS_COLS, caller_rows)
    write_tsv(out, "uncalled", provenance(tool, root, caveat), UNCALLED_COLS, uncalled_rows)
    n_ux = sum(1 for o in odd if o[6] == "unequal_x")
    print(f"files {len(mods)}  aliases {len(aliases)}  odd-shape {len(odd)} (unequal_x {n_ux}, trailing_text {len(odd) - n_ux})  "
          f"undecodable {len(undecodable)}")
    print(f"targets resolved {counts['resolved']} / ambiguous {counts['ambiguous']} / unresolved {counts['unresolved']}")
    print(f"reference rows {len(ref_rows)}  callers rows {len(caller_rows)}  uncalled {len(uncalled_rows)}")
    for word, r in undecodable:
        print(word, r)
    return 1 if undecodable else 0


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


class _SkipCase(Exception):
    """Raised by a case that cannot set up its plant on this system; the case is reported SKIP."""


def _plant_unreadable(root, rel):
    """A `.lean` entry that cannot be read: a dangling symlink, else a mode-000 file (not as root)."""
    p = os.path.join(root, *rel.split("/"))
    os.makedirs(os.path.dirname(p), exist_ok=True)
    try:
        os.symlink(os.path.join(root, "no-such-target"), p)
        return
    except OSError:
        pass
    if hasattr(os, "geteuid") and os.geteuid() != 0:
        with open(p, "w") as f:
            f.write("def a := 1\n")
        os.chmod(p, 0)
        return
    raise _SkipCase("cannot plant an unreadable .lean entry here")


def _go(files, count_reads=False, prep=None):
    with tempfile.TemporaryDirectory() as d:
        root, out = os.path.join(d, "src"), os.path.join(d, "out")
        os.makedirs(root)
        _plant(root, files)
        if prep:
            prep(root)
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

    @case("A1d", "a body that is not the wrapper shape at all (a plain `exact`) is neither an alias nor odd; a shape then `simp` is odd, not an alias")
    def _():
        t = ("theorem t : P := by\n  first | exact @L.x | exact L.x | (intros; apply L.x <;> assumption)\n  simp\n"
             "theorem u : P := by\n  exact L.x\n" + _W("good", "L.z"))
        _rc, _o, _e, tabs, _n = _go({"T.lean": t})
        return _eq((_pairs(tabs, "aliases", "public_name"), _pairs(tabs, "aliases_odd", "public_name", "reason", "tail")),
                   ([("good",)], [("t", "trailing_text", "simp")]))

    @case("A2a", "the shape with unequal X goes to aliases_odd.tsv with its three X, and not to aliases.tsv")
    def _():
        _rc, _o, _e, tabs, _n = _go({"Odd.lean": _W("odd", "L.a", "L.b", "L.a")})
        return _eq((tabs["aliases"][2], tabs["aliases_odd"][2]),
                   ([], [dict(public_name="odd", x1="L.a", x2="L.b", x3="L.a", file="Odd.lean", line="1", reason="unequal_x", tail="")]))

    @case("A2c", "only the THIRD X differs: one aliases_odd.tsv row (unequal_x, x1 = x2, x3 the other), none in aliases.tsv")
    def _():
        _rc, _o, _e, tabs, _n = _go({"Odd.lean": _W("odd", "A.t", "A.t", "A.other")})
        return _eq((tabs["aliases"][2], _pairs(tabs, "aliases_odd", "public_name", "x1", "x2", "x3", "reason")),
                   ([], [("odd", "A.t", "A.t", "A.other", "unequal_x")]))

    @case("A2d", "only the SECOND X differs: one aliases_odd.tsv row (unequal_x), none in aliases.tsv")
    def _():
        _rc, _o, _e, tabs, _n = _go({"Odd.lean": _W("odd", "A.t", "A.other", "A.t")})
        return _eq((tabs["aliases"][2], _pairs(tabs, "aliases_odd", "public_name", "x1", "x2", "x3", "reason")),
                   ([], [("odd", "A.t", "A.other", "A.t", "unequal_x")]))

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

    @case("A5h", "the wrapper naming its own target is the alias link, not a caller: alone, both alias and target are uncalled")
    def _():
        _rc, _o, _e, tabs, _n = _go(PUB_ALPHA)
        return _eq((tabs["callers"][2], _pairs(tabs, "uncalled", "name", "kind")),
                   ([], [("GlobalTheory.T.alpha", "alias"), ("Lib.alpha_core", "target")]))

    DECL_AB = {"D/F.lean": decl("A.B", "foo")}

    @case("G1a", "a target written `_root_.A.B.foo` resolves to `foo` declared in `namespace A.B`; `target` keeps the text as written")
    def _():
        _rc, _o, _e, tabs, _n = _go({**DECL_AB, "Pub/W.lean": _W("viaR", "_root_.A.B.foo")})
        r = tabs["aliases"][2][0]
        return _eq((r["target"], r["target_file"], r["target_line"], r["target_matches"]), ("_root_.A.B.foo", "D/F.lean", "2", "1"))

    @case("G1b", "a `_root_.` target declared nowhere: matches 0, with a resolving control beside it")
    def _():
        _rc, _o, _e, tabs, _n = _go({**DECL_AB, "Pub/W.lean": _W("w1", "_root_.A.B.foo") + _W("w2", "_root_.A.B.nothing")})
        return _eq({r["public_name"]: r["target_matches"] for r in tabs["aliases"][2]}, {"w1": "1", "w2": "0"})

    @case("G1c", "a decoy file that opens `namespace A.B` but declares `bar` is not a candidate: matches stays 1")
    def _():
        _rc, _o, _e, tabs, _n = _go({**DECL_AB, "Decoy/D.lean": decl("A.B", "bar"), "Pub/W.lean": _W("viaR", "_root_.A.B.foo")})
        r = tabs["aliases"][2][0]
        return _eq((r["target_matches"], r["target_file"], tabs["alias_candidates"][2]), ("1", "D/F.lean", []))

    @case("G1d", "`_root_.` is stripped once and only at the start of the target")
    def _():
        ws = _W("w1", "_root_.A.B.foo") + _W("w2", "_root_._root_.A.B.foo") + _W("w3", "A._root_.B.foo")
        _rc, _o, _e, tabs, _n = _go({**DECL_AB, "Pub/W.lean": ws})
        return _eq({r["public_name"]: r["target_matches"] for r in tabs["aliases"][2]}, {"w1": "1", "w2": "0", "w3": "0"})

    @case("G1e", "callers.tsv names a resolved `_root_.` target by its stripped full name")
    def _():
        _rc, _o, _e, tabs, _n = _go({**DECL_AB, "Pub/W.lean": _W("viaR", "_root_.A.B.foo"), "Use/C.lean": "exact A.B.foo\n"})
        return _eq(_pairs(tabs, "callers", "name", "kind", "file", "line", "in_comment"),
                   [("A.B.foo", "target", "Use/C.lean", "1", "0")])

    def scope_map(text, targets):
        files = {"S/Scope.lean": text, "Pub/W.lean": "".join(_W(f"w{i}", t) for i, t in enumerate(targets))}
        _rc, _o, _e, tabs, _n = _go(files)
        return {r["target"]: r["target_matches"] for r in tabs["aliases"][2]}

    @case("G2a", "`namespace A.B.C` ... `end C` pops one component: the next theorem is `A.B.foo`, not `A.B.C.foo`")
    def _():
        t = "namespace A.B.C\ntheorem inner : P := sorry\nend C\ntheorem foo : P := sorry\nend B\nend A\n"
        return _eq(scope_map(t, ["A.B.foo", "A.B.C.foo", "A.B.C.inner"]), {"A.B.foo": "1", "A.B.C.foo": "0", "A.B.C.inner": "1"})

    @case("G2b", "`end B.C` pops two components")
    def _():
        t = "namespace A.B.C\nend B.C\ntheorem foo : P := sorry\nend A\n"
        return _eq(scope_map(t, ["A.foo", "A.B.foo", "A.B.C.foo"]), {"A.foo": "1", "A.B.foo": "0", "A.B.C.foo": "0"})

    @case("G2c", "a full `end A.B.C` pops three, and a later partial end still works")
    def _():
        t = ("namespace A.B.C\nend A.B.C\ntheorem foo : P := sorry\nnamespace D.E\nend E\ntheorem bar : P := sorry\nend D\n")
        return _eq(scope_map(t, ["foo", "A.B.C.foo", "D.bar", "D.E.bar"]), {"foo": "1", "A.B.C.foo": "0", "D.bar": "1", "D.E.bar": "0"})

    @case("G2d", "an inner `section` between does not disturb the pops")
    def _():
        t = "namespace A.B.C\nsection S\ntheorem i : P := sorry\nend S\nend C\ntheorem foo : P := sorry\nend B\nend A\n"
        return _eq(scope_map(t, ["A.B.C.i", "A.B.foo", "A.B.C.foo"]), {"A.B.C.i": "1", "A.B.foo": "1", "A.B.C.foo": "0"})

    @case("G2e", "a bare `end` after a bare `section` leaves the namespaces; a bare `end` on a namespace pops nothing")
    def _():
        t = "namespace A.B\nsection\nend\nend\ntheorem foo : P := sorry\nend A.B\ntheorem bar : P := sorry\n"
        return _eq(scope_map(t, ["A.B.foo", "foo", "bar", "A.B.bar"]), {"A.B.foo": "1", "foo": "0", "bar": "1", "A.B.bar": "0"})

    CHAIN2 = "  | exact @L.y | exact L.y | (intros; apply L.y <;> assumption)\n"

    @case("G3a", "the shape followed by a second chain: an odd row (reason trailing_text, first target as x1, tail), not in aliases.tsv")
    def _():
        _rc, _o, _e, tabs, _n = _go({"Two.lean": _W("two", "L.x") + CHAIN2})
        return _eq((tabs["aliases"][2], tabs["aliases_odd"][2]),
                   ([], [dict(public_name="two", x1="L.x", x2="L.x", x3="L.x", file="Two.lean", line="1",
                              reason="trailing_text", tail="| exact @L.y | exact L.y | (intros; apply L.y <;> assumption)")]))

    @case("G3b", "unequal X is reason unequal_x (the tail stays empty when nothing follows)")
    def _():
        _rc, _o, _e, tabs, _n = _go({"Odd.lean": _W("odd", "L.a", "L.b", "L.a")})
        return _eq(_pairs(tabs, "aliases_odd", "public_name", "reason", "tail"), [("odd", "unequal_x", "")])

    @case("G3c", "a clean wrapper followed only by blank lines and the next declaration is still an alias, not odd")
    def _():
        _rc, _o, _e, tabs, _n = _go({"C.lean": _W("clean", "L.x") + "\n\n" + "theorem next : P := sorry\n"})
        return _eq((_pairs(tabs, "aliases", "public_name"), tabs["aliases_odd"][2]), ([("clean",)], []))

    @case("G3d", "the tail is the trailing text cut to 80 characters; a trailing comment alone is not trailing text")
    def _():
        long_tail = "  simp [" + ", ".join(f"h{i}" for i in range(60)) + "]\n"
        _rc, _o, _e, tabs, _n = _go({"L.lean": _W("lng", "L.x") + long_tail, "K.lean": _W("cmt", "L.x") + "  -- note\n"})
        want = ("simp [" + ", ".join(f"h{i}" for i in range(60)) + "]")[:80]
        return _eq((_pairs(tabs, "aliases_odd", "public_name", "reason", "tail"), _pairs(tabs, "aliases", "public_name")),
                   ([("lng", "trailing_text", want)], [("cmt",)]))

    @case("G3e", "the summary line prints `odd-shape N (unequal_x A, trailing_text B)`")
    def _():
        _rc, out, _e, _t, _n = _go({"A.lean": _W("w1", "L.a", "L.b", "L.a"), "B.lean": _W("w2", "L.x") + CHAIN2,
                                    "C.lean": _W("w3", "L.x") + CHAIN2})
        return _eq("odd-shape 3 (unequal_x 1, trailing_text 2)" in out, True)

    SHAPE_X = "first | exact @L.x | exact L.x | (intros; apply L.x <;> assumption)"
    SHAPE_Y = SHAPE_X.replace("L.x", "L.y")

    @case("G4a", "a binder default proof `(h : P := by assumption)` in the signature does not hide the wrapper")
    def _():
        t = f"theorem w (h : P := by assumption) : Q := by\n  {SHAPE_X}\n"
        _rc, _o, _e, tabs, _n = _go({"W.lean": t})
        return _eq((_pairs(tabs, "aliases", "public_name", "target", "line"), tabs["aliases_odd"][2]), ([("w", "L.x", "1")], []))

    @case("G4b", "two binder default proofs plus the wrapper: still an alias")
    def _():
        t = f"theorem w (h : P := by assumption) (k : R := by simp) : Q := by\n  {SHAPE_X}\n"
        _rc, _o, _e, tabs, _n = _go({"W.lean": t})
        return _eq((_pairs(tabs, "aliases", "public_name", "target"), tabs["aliases_odd"][2]), ([("w", "L.x")], []))

    @case("G4c", "a shape inside a default proof, then a real wrapper to Y: the alias targets Y, not X")
    def _():
        t = f"theorem w (h : P := by {SHAPE_X}) : Q := by\n  {SHAPE_Y}\n"
        _rc, _o, _e, tabs, _n = _go({"W.lean": t})
        return _eq((_pairs(tabs, "aliases", "public_name", "target"), tabs["aliases_odd"][2]), ([("w", "L.y")], []))

    @case("G4d", "the shape only inside the signature and a different real proof: neither alias nor odd")
    def _():
        t = f"theorem w (h : P := by {SHAPE_X}) : Q := by simp\n"
        _rc, _o, _e, tabs, _n = _go({"W.lean": t})
        return _eq((tabs["aliases"][2], tabs["aliases_odd"][2]), ([], []))

    @case("G4e", "a default proof, the wrapper, then trailing text: odd trailing_text with x1 the wrapper's target")
    def _():
        t = f"theorem w (h : P := by assumption) : Q := by\n  {SHAPE_Y}\n  simp\n"
        _rc, _o, _e, tabs, _n = _go({"W.lean": t})
        return _eq((tabs["aliases"][2], _pairs(tabs, "aliases_odd", "public_name", "x1", "reason", "tail")),
                   ([], [("w", "L.y", "trailing_text", "simp")]))

    BOUNDARY_LINES = [
        ("open", "open Foo"), ("attribute", "attribute [simp] foo"), ("variable", "variable (x : Nat)"), ("universe", "universe u"),
        ("noncomputable", "noncomputable def q : P := sorry"), ("namespace", "namespace Foo"), ("section", "section"), ("end", "end"),
        ("def", "def q : P := sorry"), ("theorem", "theorem q : P := sorry"), ("lemma", "lemma q : P := sorry"),
        ("abbrev", "abbrev q := 1"), ("structure", "structure Q where"), ("class", "class Q where"),
        ("inductive", "inductive Q where"), ("instance", "instance : Foo := sorry"), ("private", "private def q : P := sorry"),
        ("protected", "protected def q : P := sorry"), ("nonrec", "nonrec def q := 1"), ("unsafe", "unsafe def q := 1"),
        ("partial", "partial def q := 1"), ("mutual", "mutual"), ("set_option", "set_option maxHeartbeats 0"),
        ("@[", "@[simp] theorem q : P := sorry"), ("/-", "/- note -/"), ("example", "example : P := sorry"),
        ("axiom", "axiom q : P"), ("opaque", "opaque q : Nat"), ("macro", 'macro "x" : term => `(1)'),
        ("syntax", 'syntax "x" : term'), ("notation", 'notation "x" => 1'), ("local", 'local notation "x" => 1'),
        ("scoped", 'scoped notation "x" => 1'), ("export", "export Foo (bar)"), ("deriving", "deriving instance Foo for Bar"),
        ("initialize", "initialize q : Nat"), ("#check", "#check foo"), ("#print", "#print foo"), ("#eval", "#eval foo"),
    ]

    @case("A1e", "a wrapper directly followed by a column-0 line that starts with any extent-boundary keyword stays an alias, not odd")
    def _():
        for kw, line in BOUNDARY_LINES:
            _rc, _o, _e, tabs, _n = _go({"W.lean": _W("w", "L.x") + line + "\n"})
            got = (_pairs(tabs, "aliases", "public_name"), tabs["aliases_odd"][2])
            if got != ([("w",)], []):
                return False, f"first keyword that breaks: {kw!r} (line {line!r}); got aliases/odd {got!r}"
        return True, ""

    @case("A1f", "a wrapper written with `lemma` is an alias")
    def _():
        _rc, _o, _e, tabs, _n = _go({"W.lean": _W("lw", "L.x").replace("theorem", "lemma", 1)})
        return _eq((_pairs(tabs, "aliases", "public_name", "target"), tabs["aliases_odd"][2]), ([("lw", "L.x")], []))

    @case("A3j", "a target declared with a universe list, `theorem foo.{u} : P` in `namespace A`, resolves for `A.foo`")
    def _():
        t = "namespace A\ntheorem foo.{u} : P := sorry\nend A\n"
        _rc, _o, _e, tabs, _n = _go({"U.lean": t, "Pub/W.lean": _W("viaU", "A.foo")})
        r = tabs["aliases"][2][0]
        return _eq((r["target_file"], r["target_line"], r["target_matches"]), ("U.lean", "2", "1"))

    @case("A4d", "the wrapper's own file writing the FULL token in code is skipped for refs.tsv; another file with the token gets its row")
    def _():
        own = "theorem GlobalTheory.T.alpha : P := by\n  first | exact @Lib.a | exact Lib.a | (intros; apply Lib.a <;> assumption)\n"
        _rc, _o, _e, tabs, _n = _go({"Pub/Alpha.lean": own, "Use/C.lean": "def x := GlobalTheory.T.alpha\n"})
        return _eq(_pairs(tabs, "refs", "file", "public_name", "occurrences", "in_comment_only"),
                   [("Use/C.lean", "GlobalTheory.T.alpha", "1", "0")])

    @case("A5i", "a comment line right after a wrapper that names its target is a callers row (in_comment 1); the target is not uncalled")
    def _():
        _rc, _o, _e, tabs, _n = _go({"W.lean": _W("w", "L.x") + "-- see L.x\n", "L/X.lean": decl("L", "x")})
        return _eq((_pairs(tabs, "callers", "name", "kind", "file", "line", "in_comment"), _pairs(tabs, "uncalled", "name", "kind")),
                   ([("L.x", "target", "W.lean", "3", "1")], [("w", "alias")]))

    @case("A5j", "a second name on the wrapper's own lines is not suppressed; only the wrapper's own target is")
    def _():
        w = "theorem w : P := by\n  " + SHAPE_X + " -- see L.y\n"
        _rc, _o, _e, tabs, _n = _go({"W.lean": w, "W2.lean": _W("w2", "L.y"), "L/X.lean": decl("L", "x"), "L/Y.lean": decl("L", "y")})
        return _eq((_pairs(tabs, "callers", "name", "kind", "file", "line", "in_comment"),
                    [r for r in _pairs(tabs, "uncalled", "name", "kind") if r[1] == "target"]),
                   ([("L.y", "target", "W.lean", "2", "1")], [("L.x", "target")]))

    def inside(ns, wrappers):
        return f"namespace {ns}\n" + wrappers + f"end {ns}\n"

    def by_pub(tabs):
        return {r["public_name"]: (r["target_file"], r["target_line"], r["target_matches"]) for r in tabs["aliases"][2]}

    ROOT_AX = "theorem A.x : P := sorry\n"

    @case("NS1", "a wrapper inside `namespace N` writing `A.x` resolves to `N.A.x`, not to a root `A.x` decoy; a root wrapper still gets the root one")
    def _():
        _rc, _o, _e, tabs, _n = _go({"D/F.lean": decl("N", "A.x"), "Decoy/R.lean": ROOT_AX,
                                     "Pub/W.lean": inside("N", _W("w", "A.x")), "Pub/W2.lean": _W("w2", "A.x")})
        return _eq(by_pub(tabs), {"N.w": ("D/F.lean", "2", "1"), "w2": ("Decoy/R.lean", "1", "1")})

    @case("NS2", "only a root `A.x` exists: a wrapper inside `namespace N` falls back to it; another wrapper resolves at level N")
    def _():
        _rc, _o, _e, tabs, _n = _go({"R/R.lean": ROOT_AX, "D/B.lean": decl("N", "B.y"),
                                     "Pub/W.lean": inside("N", _W("w", "A.x") + _W("v", "B.y"))})
        return _eq(by_pub(tabs), {"N.w": ("R/R.lean", "1", "1"), "N.v": ("D/B.lean", "2", "1")})

    @case("NS3", "a wrapper inside `namespace N.M` with N.A.x and root A.x present (no N.M.A.x) picks the middle level N.A.x")
    def _():
        _rc, _o, _e, tabs, _n = _go({"D/F.lean": decl("N", "A.x"), "Decoy/R.lean": ROOT_AX, "D/Z.lean": decl("N.M", "A.z"),
                                     "Pub/W.lean": inside("N.M", _W("w", "A.x") + _W("v", "A.z"))})
        return _eq(by_pub(tabs), {"N.M.w": ("D/F.lean", "2", "1"), "N.M.v": ("D/Z.lean", "2", "1")})

    @case("NS4", "with N.M.A.x and N.A.x both present the innermost level wins inside `namespace N.M`; inside `namespace N` the outer one")
    def _():
        _rc, _o, _e, tabs, _n = _go({"D/Inner.lean": decl("N.M", "A.x"), "D/Outer.lean": decl("N", "A.x"),
                                     "Pub/W.lean": inside("N.M", _W("w", "A.x")), "Pub/W2.lean": inside("N", _W("v", "A.x"))})
        return _eq(by_pub(tabs), {"N.M.w": ("D/Inner.lean", "2", "1"), "N.v": ("D/Outer.lean", "2", "1")})

    @case("NS5", "two declarations of N.A.x plus a root A.x: AMBIGUOUS at the deciding level (matches 2, both candidates), never 1 from the root")
    def _():
        _rc, _o, _e, tabs, _n = _go({"D/F1.lean": decl("N", "A.x"), "D/F2.lean": decl("N", "A.x"), "Decoy/R.lean": ROOT_AX,
                                     "Pub/W.lean": inside("N", _W("w", "A.x")), "Pub/W2.lean": _W("w2", "A.x")})
        return _eq((by_pub(tabs), _pairs(tabs, "alias_candidates", "public_name", "candidate_file")),
                   ({"N.w": ("-", "-", "2"), "w2": ("Decoy/R.lean", "1", "1")}, [("N.w", "D/F1.lean"), ("N.w", "D/F2.lean")]))

    @case("NS6", "a wrapper inside `namespace N` writing `_root_.A.x` skips the prefixes and resolves root A.x; written `A.x` it resolves N.A.x")
    def _():
        _rc, _o, _e, tabs, _n = _go({"D/F.lean": decl("N", "A.x"), "Decoy/R.lean": ROOT_AX,
                                     "Pub/W.lean": inside("N", _W("w", "_root_.A.x") + _W("v", "A.x"))})
        return _eq(by_pub(tabs), {"N.w": ("Decoy/R.lean", "1", "1"), "N.v": ("D/F.lean", "2", "1")})

    @case("NS7", "a wrapper after `end N` has no prefix: it resolves root A.x, while one inside N resolves N.A.x in the same file")
    def _():
        t = inside("N", _W("win", "A.x")) + _W("wout", "A.x")
        _rc, _o, _e, tabs, _n = _go({"D/F.lean": decl("N", "A.x"), "Decoy/R.lean": ROOT_AX, "Pub/W.lean": t})
        return _eq(by_pub(tabs), {"N.win": ("D/F.lean", "2", "1"), "wout": ("Decoy/R.lean", "1", "1")})

    @case("NS8", "callers.tsv and uncalled.tsv name the deciding-level full name N.A.x; a use `exact N.A.x` is its caller, the text `A.x` is not")
    def _():
        _rc, _o, _e, tabs, _n = _go({"D/F.lean": decl("N", "A.x"), "Pub/W.lean": inside("N", _W("w", "A.x")),
                                     "Use/U.lean": "exact N.A.x\n", "Use/V.lean": "exact A.x\n"})
        return _eq((_pairs(tabs, "callers", "name", "kind", "file", "line", "in_comment"), _pairs(tabs, "uncalled", "name", "kind")),
                   ([("N.A.x", "target", "Use/U.lean", "1", "0")], [("N.w", "alias")]))

    @case("NS9", "`section S` adds no lookup level, only `namespace` components do; a wrapper in a real `namespace N.S` does use N.S.A.x")
    def _():
        in_section = "namespace N\nsection S\n" + _W("w", "A.x") + "end S\nend N\n"
        _rc, _o, _e, tabs, _n = _go({"D/One.lean": decl("N", "A.x"), "D/Two.lean": decl("N.S", "A.x"),
                                     "Pub/W.lean": in_section, "Pub/V.lean": inside("N.S", _W("v", "A.x"))})
        return _eq(by_pub(tabs), {"N.w": ("D/One.lean", "2", "1"), "N.S.v": ("D/Two.lean", "2", "1")})

    @case("NS10", "a wrapper's own written `A.x` is not a use of a root `A.x` that is another wrapper's target; a real `exact N.A.x` is a use of N.A.x only")
    def _():
        base = {"D/One.lean": decl("N.A", "x"), "R/Root.lean": ROOT_AX,   # N.A.x declared without spelling `A.x`
                "Pub/W.lean": inside("N", _W("w", "A.x")), "Pub/W2.lean": _W("w2", "A.x")}
        _rc, _o, _e, tabs, _n = _go(base)
        _rc2, _o2, _e2, tabs2, _n2 = _go({**base, "Use/U.lean": "exact N.A.x\n"})
        return _eq((tabs["callers"][2], _pairs(tabs, "uncalled", "name", "kind"),
                    _pairs(tabs2, "callers", "name", "kind", "file", "line", "in_comment")),
                   ([], [("A.x", "target"), ("N.A.x", "target"), ("N.w", "alias"), ("w2", "alias")],
                    [("N.A.x", "target", "Use/U.lean", "1", "0")]))

    SHAPE_AX = "first | exact @A.x | exact A.x | (intros; apply A.x <;> assumption)"

    @case("NS11", "the deciding full name written in a comment on the wrapper's own last line is the alias link, not a use; on the next line it is a use")
    def _():
        own = "theorem w : P := by\n  " + SHAPE_AX + " -- N.A.x\n"
        nxt = "theorem w : P := by\n  " + SHAPE_AX + "\n-- N.A.x\n"
        _rc, _o, _e, tabs, _n = _go({"D/One.lean": decl("N", "A.x"), "Pub/W.lean": inside("N", own)})
        _rc2, _o2, _e2, tabs2, _n2 = _go({"D/One.lean": decl("N", "A.x"), "Pub/W.lean": inside("N", nxt)})
        return _eq((tabs["callers"][2], _pairs(tabs, "uncalled", "name", "kind"),
                    _pairs(tabs2, "callers", "name", "kind", "file", "line", "in_comment")),
                   ([], [("N.A.x", "target"), ("N.w", "alias")], [("N.A.x", "target", "Pub/W.lean", "4", "1")]))

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

    @case("STALE1", "no .lean file and OUT_DIR already holds output of an earlier run: the message names those files and says this run "
                    "wrote nothing, exit 1, the old files untouched; only the files present are named; control: a fresh OUT_DIR "
                    "gets the CHECKED NOTHING line alone")
    def _():
        nothing = "CHECKED NOTHING: no .lean file under SRC_ROOT"
        got = []
        for planted in (('aliases.tsv', 'aliases_odd.tsv', 'alias_candidates.tsv', 'refs.tsv', 'callers.tsv', 'uncalled.tsv'), ('uncalled.tsv',), ()):
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
            (1, [nothing, 'OUT_DIR holds files from an earlier run: alias_candidates.tsv, aliases.tsv, aliases_odd.tsv, callers.tsv, refs.tsv, uncalled.tsv; this run wrote nothing'], ["old\n"] * 6, True),
            (1, [nothing, 'OUT_DIR holds files from an earlier run: uncalled.tsv; this run wrote nothing'], ["old\n"], True),
            (1, [nothing], [], True)])

    @case("D2a", "a file that does not decode: UNDECODABLE <relpath> printed and counted, exit 1, the other files still processed")
    def _():
        rc, out, _e, tabs, _n = _go({**PUB_ALPHA, "sub/Bad.lean": b"theorem \xff\n"})
        return _eq((rc, "UNDECODABLE sub/Bad.lean" in out.splitlines(), "undecodable 1" in out, len(tabs["aliases"][2])), (1, True, True, 1))

    @case("D2b", "an unreadable .lean entry: UNREADABLE <relpath> printed and counted, exit 1, no traceback, the other files still processed")
    def _():
        rc, out, _e, tabs, _n = _go(PUB_ALPHA, prep=lambda root: _plant_unreadable(root, "sub/X.lean"))
        return _eq((rc, "UNREADABLE sub/X.lean" in out.splitlines(), "undecodable 1" in out, len(tabs["aliases"][2])), (1, True, True, 1))

    return cases


def selftest(verbose=True):
    ok, skipped = True, 0
    for cid, desc, fn in _selftest_cases():
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
    if len(a) != 3:
        print(__doc__.split("usage:")[1].strip(), file=sys.stderr)
        return 2
    if selftest_quiet() != 0:
        print("REFUSED: selftest failed; no result reported", file=sys.stderr)
        return 4
    return run(a[1], a[2])


if __name__ == "__main__":
    sys.exit(main(sys.argv))
