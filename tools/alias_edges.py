#!/usr/bin/env python3
"""Alias layer of the proof map, from text only.

An alias is a theorem whose whole proof is the wrapper
  `first | exact @X | exact X | (intros; apply X <;> assumption)`
(the three X equal). This tool finds the aliases, resolves each X to the file and line that declares it,
and lists where the alias names and the targets are written out in full.

Outputs under OUT_DIR (each starts with a `#` provenance line, then the column row):
  aliases.tsv           public_name, target, file, line, target_file, target_line, target_matches
  aliases_odd.tsv       public_name, x1, x2, x3, file, line, reason, tail   (wrapper shape that is not an exact
                        wrapper: reason unequal_x or trailing_text; tail = the trailing text, first 80 characters)
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
 A2 A theorem whose body has the shape at its start but is not an exact equal-X wrapper is listed in
    aliases_odd.tsv, not dropped: reason `unequal_x` (the X differ) or `trailing_text` (equal X, then more
    non-blank text, e.g. a second chain). It is not in aliases.tsv.
 A3 Each target is resolved to its DECLARING file and line: a declaration whose full name equals X exactly
    (one leading `_root_.` of X is stripped first; the `target` column keeps X as written).
    target_matches = number of declarations found: 0 = UNRESOLVED, 1 = resolved, 2 or more = AMBIGUOUS; for
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
    trailing dots trimmed), outside its own declaration line and outside the lines of an alias wrapper (the
    wrapper naming its target is the alias link itself, already in aliases.tsv); one row per file and line, in_comment = 1 when
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
ODD_COLS = ["public_name", "x1", "x2", "x3", "file", "line", "reason", "tail"]
CAND_COLS = ["public_name", "target", "candidate_file", "candidate_line"]
REFS_COLS = ["file", "public_name", "occurrences", "in_comment_only"]
CALLERS_COLS = ["name", "kind", "file", "line", "in_comment"]
UNCALLED_COLS = ["name", "kind"]


# ---------------------------------------------------------------- the tool

WRAP_QUICK = re.compile(r"first\s*\|\s*exact\s+@")
WRAP = re.compile(r"first\s*\|\s*exact\s+@([^\s|]+)\s*\|\s*exact\s+([^\s|]+)\s*\|\s*"
                  r"\(\s*intros\s*;\s*apply\s+([^\s<]+)\s*<;>\s*assumption\s*\)")
BY = re.compile(r":=\s*by(?![\w'])")
DECL_QUICK = re.compile(r"\b(?:theorem|lemma|def|abbrev|structure|class|inductive|instance)\b")
DECL = re.compile(r"[ \t]*(?:@\[[^\]]*\][ \t]*)*(?:(?:private|protected|noncomputable|nonrec|unsafe|partial)[ \t]+)*"
                  r"(theorem|lemma|def|abbrev|structure|class|inductive|instance)[ \t]+([^\s:({\[]*)")
BOUND = re.compile(r"(?:(?:theorem|lemma|def|abbrev|structure|class|inductive|instance|end|namespace|section|open|"
                   r"set_option|attribute|variable|universe|noncomputable|private|protected|nonrec|unsafe|partial|mutual)"
                   r"(?![\w'.])|@\[)")
NS = re.compile(r"namespace[ \t]+(\S+)")
SEC = re.compile(r"(?:noncomputable[ \t]+)?section(?:[ \t]+(\S+))?[ \t]*$")
END = re.compile(r"end(?:[ \t]+(\S+))?[ \t]*$")
MUT = re.compile(r"mutual[ \t]*$")
RUN = re.compile(r"[\w'.₀-₉]+")
TOK = re.compile(r"GlobalTheory\.T\.[A-Za-z_][\w'₀-₉]*")
PUB = "GlobalTheory.T."


def parse_decls(raw, masked):
    """[(line_no, kind, full_name, end_idx)] for every declaration with a name. Structure comes from the
    masked text; end_idx is the 0-based index of the first line after the declaration's extent."""
    if not DECL_QUICK.search(masked):
        return []
    ml, rl = masked.split("\n"), raw.split("\n")
    n = len(ml)
    nxt = [n] * (n + 1)
    for k in range(n - 1, -1, -1):
        m = ml[k]
        is_b = bool(m) and m[0] not in " \t" and BOUND.match(m) is not None
        nxt[k] = k if (is_b or rl[k].startswith("/-")) else nxt[k + 1]
    stack, found = [], []
    for k in range(n):
        line = ml[k]
        if not line.strip():
            continue
        if line[0] not in " \t":
            m = NS.match(line)
            if m:
                stack.extend(("namespace", c) for c in m.group(1).split("."))
                continue
            m = SEC.match(line)
            if m:
                stack.append(("section", m.group(1)))
                continue
            if MUT.match(line):
                stack.append(("section", None))
                continue
            m = END.match(line)
            if m:
                want = m.group(1)
                if want is None:
                    if stack and stack[-1][0] == "section":
                        stack.pop()
                else:
                    del stack[max(0, len(stack) - len(want.split("."))):]
                continue
        m = DECL.match(line)
        if not m:
            continue
        name = m.group(2).rstrip(".")
        if not name:
            continue
        if name.startswith("_root_."):
            full = name[len("_root_."):]
        else:
            prefix = ".".join(nm for kind, nm in stack if kind == "namespace")
            full = prefix + "." + name if prefix else name
        found.append((k + 1, m.group(1), full, nxt[k + 1]))
    return found


def norm_target(x):
    """A target written `_root_.X` is the root name X: strip one leading `_root_.`, nothing else."""
    return x[len("_root_."):] if x.startswith("_root_.") else x


def find_wrappers(raw, masked):
    """([(public, x, line, last_line)] exact wrappers, [(public, x1, x2, x3, line, reason, tail)] odd shapes).
    reason is `unequal_x` (the three X differ) or `trailing_text` (equal X, more non-blank text follows; tail is
    that text with whitespace runs collapsed, cut to 80 characters)."""
    good, odd = [], []
    if not WRAP_QUICK.search(masked):
        return good, odd
    ml = masked.split("\n")
    for line_no, kind, full, end in parse_decls(raw, masked):
        if kind not in ("theorem", "lemma"):
            continue
        extent = "\n".join(ml[line_no - 1:end])
        b = BY.search(extent)
        if not b:
            continue
        body = extent[b.end():].strip()
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
            good.append((full, x1, line_no, end))
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
        return 1
    os.makedirs(out, exist_ok=True)
    rel = {p: os.path.relpath(p, root).replace(os.sep, "/") for _, p in mods}
    undecodable = []
    # pass 1: wrappers and the target set
    aliases, odd = [], []          # aliases: (public, target, file, line)
    wrap_lines = collections.defaultdict(set)   # file -> lines inside an alias wrapper (the alias link itself)
    for _, p in mods:
        text, ok = read_text(p)
        if not ok:
            undecodable.append(rel[p])
            continue
        good, bad = find_wrappers(text, mask_comments(text))
        aliases += [(pub, x, rel[p], ln) for pub, x, ln, _last in good]
        wrap_lines[rel[p]].update(l for _pub, _x, ln, last in good for l in range(ln, last + 1))
        odd += [(pub, x1, x2, x3, rel[p], ln, why, tail) for pub, x1, x2, x3, ln, why, tail in bad]
    targets = {norm_target(a[1]) for a in aliases}   # resolution and callers use the stripped full name
    alias_names = {a[0] for a in aliases}
    names = targets | alias_names
    pub_t = {n for n in alias_names if n.startswith(PUB)}
    wrapper_files = collections.defaultdict(set)
    for pub, _x, f, _ln in aliases:
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
            for line_no, _kind, full, _end in parse_decls(text, masked):
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
    for pub, x, f, ln in sorted(aliases, key=lambda a: (a[0], a[2], a[3])):
        c = sorted(cands.get(norm_target(x), []))
        if len(c) == 1:
            alias_rows.append((pub, x, f, ln, c[0][0], c[0][1], 1))
            counts["resolved"] += 1
        else:
            alias_rows.append((pub, x, f, ln, "-", "-", len(c)))
            counts["ambiguous" if c else "unresolved"] += 1
            cand_rows += [(pub, x, cf, cl) for cf, cl in c]
    ref_rows = [(f, n, v[0], int(v[1] == 0)) for (f, n), v in sorted(refs.items()) if f not in wrapper_files[n]]
    decl_lines = collections.defaultdict(set)
    for pub, _x, f, ln in aliases:
        decl_lines[(pub, "alias")].add((f, ln))
    universe = {(n, "alias") for n in alias_names}
    for x in targets:
        if len(cands.get(x, [])) == 1:
            universe.add((x, "target"))
            decl_lines[(x, "target")].add(cands[x][0])
    caller_rows, uncalled_rows = [], []
    for n, kind in sorted(universe):
        per_line = {}
        for f, ln, inc in occ.get(n, []):
            if (f, ln) in decl_lines[(n, kind)] or ln in wrap_lines[f]:
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
    for r in undecodable:
        print("UNDECODABLE", r)
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
