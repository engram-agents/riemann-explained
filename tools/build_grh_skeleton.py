#!/usr/bin/env python3
"""The skeleton of the map for a Lean repository that keeps its own index (CONTENTS.md) and its own folders.

usage: build_grh_skeleton.py --grh DIR --pin COMMIT --strings strings.json --out OUT_DIR [--outline outline.json]
       build_grh_skeleton.py --selftest [--only ID,ID] [--grh DIR]

DIR is the folder that holds CONTENTS.md and src/. The tool reads the `## New` section of CONTENTS.md and the .lean files under src/New and writes
OUT_DIR/graph/index.json, OUT_DIR/graph/step/<id>.json and OUT_DIR/graph/uses.json, and nothing else: no page, no assets (`assets` is {}). It builds ROWS (id,
parent, order, premises, kind, state, proof, title) and hands them to build_site's `_graph_files` and `_graph_bytes`, with a symbol table that has one more kind
row (module); it has no writer of its own for the graph objects, and every refusal of the graph contract (GRAPH-FANOUT, GRAPH-ID, GRAPH-DUP, GRAPH-PARENT,
GRAPH-CYCLE, GRAPH-EDGE, GRAPH-SYMBOL, GRAPH-COUNT, GRAPH-STRINGS) is that function's. --pin is written as the `commit` of every file. --outline (default:
outline/outline.json of this checkout) names the repository's own outline, whose group ids must not be ids of this tool. Exit 0 built; 1 refused, OUT_DIR not
written (the build goes into a sibling folder that is renamed into place); 2 usage error or an input that cannot be read. A normal run does NOT run the
self-test; --selftest does (0 pass, 4 fail, 2 an unknown id after --only). SK13 reads the real source and runs only when --grh is given to the self-test;
otherwise it is skipped.

THE RULES (all mechanical; nothing is typed by hand; kind and face lines are the skeleton's own rules, not reading)
 1 TREE. CONTENTS.md, section `## New` only, in the order of its lines (nothing is sorted, nothing comes from the file system). Each `### heading` is a section;
   a line that is only `**title**` is a group of that section; a line `- `New/<path>` (<n>): <title>` is a file of the latest group. A section whose files have
   no group line gets one anonymous group (id `<section>--`, empty title). A section of exactly one file whose path has no folder (`New/Main`) is a top step
   that is that file. Steps: section > group > file.
 2 IDS. Every id starts with `lean-`. Section: the folder name (the second path segment) in kebab case (a lower-case letter followed by an upper-case one gets
   `-`; `_` becomes `-`; then lower case). Group: `<section id>--<slug of its title>` (NFKD, accents dropped, lower case, each run of characters outside a-z0-9
   one `-`, trimmed). File: its path after `New/`, each segment in kebab case, joined by `-`. An id longer than 64 characters is cut to its first 57, a trailing
   `-` removed, then `-` and the first 6 hex digits of the sha256 of the whole id; an id of 64 or fewer is never touched. A clash is GRAPH-DUP, a bad character
   GRAPH-ID, never corrected; an id that is also an id of the outline is SKEL-ID-CLASH.
 3 TITLES. A file: the text after the colon with its backticks removed. A group: its bold text. A section: its heading. The 50-character bound of the graph
   contract (the face line) is NOT applied here: it lives in build_site's `_graph_line_errors`, which this tool does not call.
 4 PREMISES. A file rests on a file of the SAME group that it imports (`import New.X.Y` at the start of a line), after the transitive reduction of each group's
   edges. A self-import and an import outside New are ignored; an import of a New file of another group (and a reduced one) is not drawn but is listed in
   graph/uses.json. Groups and sections have no premises. A cycle among the files of a group is left as it is (GRAPH-EDGE).
 5 KIND, STATE, PROOF. Every step has kind `module`, state `none`, proof `none`: no declaration is read.
 6 USES. graph/uses.json holds, for every file step, the ids of every New file it imports, in any group, sorted, never itself. It is not part of index.json.
 7 COMPLETENESS. Every .lean file under src/New is a file line of CONTENTS and every file line exists: SKEL-UNLISTED / SKEL-MISSING (`<path>` as in CONTENTS,
   without `.lean`); a line of the section that does not parse, or a file whose folder is not its section's, is SKEL-LINE <n> (n is the line of CONTENTS.md).
   All of one kind are reported together.
 8 STRINGS. The strings file is read and checked as build_site does and must hold symbol_kind_module; `_graph_files` checks the exact key set (21 keys here).
"""
import contextlib
import hashlib
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


PREFIX = "lean-"      # every id of this tool starts with it: its own namespace, apart from the ids of the repository's outline
ID_MAX = 64           # the longest id (the page's router refuses a longer target)
ID_KEEP = 57          # an id longer than ID_MAX keeps this many characters, then `-` and ID_HASH hex digits of the sha256 of the whole id
ID_HASH = 6
MODULE_ROW = {"class": "kind-module", "words": "symbol_kind_module"}
SYMBOLS = dict(bs.GRAPH_SYMBOLS, kinds=dict(bs.GRAPH_SYMBOLS["kinds"], module=MODULE_ROW))   # the table of this tool: today's, with the one more kind row
OUTLINE = os.path.join(_HERE, os.pardir, "outline", "outline.json")
_FILE_LINE = re.compile(r"- `(New/[^`]+)` \((\d+)\): (.*)")
_GROUP_LINE = re.compile(r"\*\*(.+)\*\*")
_IMPORT = re.compile(r"import[ \t]+(\S+)")


def kebab(s):
    """`UpperBound` -> `upper-bound`: `-` between a lower-case letter and an upper-case one, `_` as `-`, then lower case."""
    return re.sub(r"(?<=[a-z])(?=[A-Z])", "-", s).replace("_", "-").lower()


def slug(s):
    """NFKD with the accents dropped, lower case, every run of characters outside a-z0-9 one `-`, trimmed of `-`."""
    folded = "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", "-", folded).strip("-")


def _cap(i):
    """An id of at most ID_MAX characters is returned as it is; a longer one is cut to its first ID_KEEP characters, a trailing `-` removed, then `-` and the
    first ID_HASH hex digits of the sha256 (UTF-8) of the whole, untruncated id are appended."""
    if len(i) <= ID_MAX:
        return i
    return i[:ID_KEEP].rstrip("-") + "-" + hashlib.sha256(i.encode("utf-8")).hexdigest()[:ID_HASH]


def parse_contents(text):
    """(sections, [SKEL-LINE errors]) from CONTENTS.md text. A section is {heading, line, groups: [{title or None, line, files: [{path, title, line}]}],
    top_file, folder}. The order of every list is the order of the lines. Raises Unreadable when there is no `## New` section."""
    lines = text.split("\n")
    start = next((i for i, ln in enumerate(lines) if ln.rstrip() == "## New"), None)
    if start is None:
        raise Unreadable("CONTENTS.md has no `## New` section")
    errors, sections, sec, grp, loose = [], [], None, None, []

    def close():
        if sec is None:
            return
        if sec["groups"]:
            errors.extend(("SKEL-LINE", str(f["line"]), "") for f in loose)
        elif loose:
            sec["groups"].append({"title": None, "line": loose[0]["line"], "files": list(loose)})
    for i in range(start + 1, len(lines)):
        n, line = i + 1, lines[i].rstrip()
        if line.startswith("## "):
            break
        if line == "":
            continue
        if line.startswith("### "):
            close()
            sec, grp, loose = {"heading": line[4:].strip(), "line": n, "groups": []}, None, []
            sections.append(sec)
            continue
        g, f = _GROUP_LINE.fullmatch(line), _FILE_LINE.fullmatch(line)
        if sec is None or not ((g and "**" not in g.group(1)) or f):
            errors.append(("SKEL-LINE", str(n), ""))
        elif f:
            item = {"path": f.group(1), "title": f.group(3).replace("`", ""), "line": n}
            (grp["files"] if grp is not None else loose).append(item)
        else:
            grp = {"title": g.group(1), "line": n, "files": []}
            sec["groups"].append(grp)
    close()
    for s in sections:
        files = [f for g in s["groups"] for f in g["files"]]
        s["top_file"] = len(files) == 1 and files[0]["path"].count("/") == 1
        s["folder"] = None
        if s["top_file"]:
            continue
        if not files:
            errors.append(("SKEL-LINE", str(s["line"]), ""))
        for g in s["groups"]:
            if not g["files"] and files:
                errors.append(("SKEL-LINE", str(g["line"]), ""))
        for f in files:
            segs = f["path"].split("/")
            if len(segs) < 3:
                errors.append(("SKEL-LINE", str(f["line"]), ""))
            elif s["folder"] is None:
                s["folder"] = segs[1]
            elif segs[1] != s["folder"]:
                errors.append(("SKEL-LINE", str(f["line"]), ""))
    errors.sort(key=lambda e: int(e[1]))
    return sections, errors


def _imports(src_text):
    mods = []
    for line in src_text.split("\n"):
        m = _IMPORT.match(line)
        if m and m.group(1) not in mods:
            mods.append(m.group(1))
    return mods


def _reduce(adj):
    """The transitive reduction of an acyclic graph {node: [successors]}: an edge F -> H is dropped when F -> G for some other G and G reaches H. A graph
    with a cycle is returned as it is (the graph contract refuses it)."""
    state, reach = {}, {}

    def visit(x):
        if state.get(x) == 1:
            return False
        if state.get(x) == 2:
            return True
        state[x] = 1
        r = set()
        for y in adj[x]:
            if not visit(y):
                return False
            r |= {y} | reach[y]
        reach[x] = r
        state[x] = 2
        return True
    if not all(visit(x) for x in adj):
        return {x: list(ys) for x, ys in adj.items()}
    return {x: [h for h in ys if not any(h in reach[g] for g in ys if g != h)] for x, ys in adj.items()}


def _depths(kept):
    """{node: depth} of a graph {node: [premises]}: 0 for a node that rests on nothing, else 1 + the deepest premise; None when it has a cycle."""
    memo, busy = {}, set()

    def d(x):
        if x in memo:
            return memo[x]
        if x in busy:
            raise ValueError(x)
        busy.add(x)
        memo[x] = 0 if not kept[x] else 1 + max(d(y) for y in kept[x])
        busy.discard(x)
        return memo[x]
    try:
        return {x: d(x) for x in kept}
    except ValueError:
        return None


def _read(path, what):
    try:
        with open(path, "rb") as fh:
            return fh.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise Unreadable(f"cannot read {what}: {e}")


def _disk_paths(grh):
    def fail(e):
        raise Unreadable(f"cannot read src/New: {e}")
    base = os.path.join(grh, "src")
    found = []
    for r, _, fs in os.walk(os.path.join(base, "New"), onerror=fail):
        found += [os.path.relpath(os.path.join(r, n), base)[:-len(".lean")].replace(os.sep, "/") for n in fs if n.endswith(".lean")]
    return sorted(found)


def build_rows(grh):
    """(errors, rows, report) from the folder `grh`: SKEL-LINE, then SKEL-MISSING and SKEL-UNLISTED, each stops the run before the next stage."""
    sections, errors = parse_contents(_read(os.path.join(grh, "CONTENTS.md"), "CONTENTS.md"))
    if errors:
        return errors, [], {}
    listed = [f["path"] for s in sections for g in s["groups"] for f in g["files"]]
    disk = _disk_paths(grh)
    errors = [("SKEL-MISSING", p, "") for p in listed if p not in set(disk)] + [("SKEL-UNLISTED", p, "") for p in disk if p not in set(listed)]
    if errors:
        return errors, [], {}
    src = {p: _read(os.path.join(grh, "src", *p.split("/")) + ".lean", p + ".lean") for p in listed}
    cut = []

    def ident(i):
        j = _cap(i)
        if j != i:
            cut.append((i, j))
        return j
    fid = {}
    for p in listed:
        fid[p] = ident(PREFIX + "-".join(kebab(x) for x in p.split("/")[1:]))
    where = {}   # file path -> (section, group) it belongs to
    for si, s in enumerate(sections):
        for gi, g in enumerate(s["groups"]):
            for f in g["files"]:
                where[f["path"]] = (si, gi)
    self_imports = drawn = total = 0
    premises, uses, groups = {}, {}, []
    group_files = {}
    for si, s in enumerate(sections):
        for gi, g in enumerate(s["groups"]):
            members = [f["path"] for f in g["files"]]
            adj = {p: [] for p in members}
            for p in members:
                mine = set()
                for mod in _imports(src[p]):
                    q = mod.replace(".", "/")
                    if q == p:
                        self_imports += 1
                    elif q in where:
                        mine.add(q)
                        total += 1
                        if where[q] == (si, gi):
                            adj[p].append(q)
                adj[p].sort(key=members.index)
                uses[fid[p]] = sorted(fid[q] for q in mine)
            kept = _reduce(adj)
            drawn += sum(len(v) for v in kept.values())
            premises.update({p: [fid[q] for q in v] for p, v in kept.items()})
            group_files[(si, gi)] = (members, kept)
    rows = []

    def row(i, parent, order, prem, title):
        rows.append({"id": i, "parent": parent, "order": order, "premises": prem, "kind": "module", "state": "none", "proof": "none", "title": title})
    for ti, s in enumerate(sections):
        if s["top_file"]:
            f = s["groups"][0]["files"][0]
            row(fid[f["path"]], "root", ti, [], f["title"])
            continue
        sid = PREFIX + kebab(s["folder"])
        sid_id = ident(sid)
        row(sid_id, "root", ti, [], s["heading"])
        for gi, g in enumerate(s["groups"]):
            gid = ident(f"{sid}--{slug(g['title'] or '')}")
            row(gid, sid_id, gi, [], g["title"] or "")
            members, kept = group_files[(ti, gi)]
            for fi, f in enumerate(g["files"]):
                row(fid[f["path"]], gid, fi, premises[f["path"]], f["title"])
            ends = {p for p in members if kept[p]} | {q for p in members for q in kept[p]}
            depth = _depths(kept)
            per = {}
            for v in (depth or {}).values():
                per[v] = per.get(v, 0) + 1
            wide = min((k for k in per if per[k] == max(per.values())), default=0)
            groups.append({"group": gid, "files": len(members), "linked": len(ends), "unlinked": len(members) - len(ends),
                           "longest": max((depth or {}).values(), default=0), "widest_depth": wide, "widest_count": per.get(wide, 0)})
    kids, depth_max = {}, 0
    parent = {r["id"]: r["parent"] for r in rows}
    for r in rows:
        kids[r["parent"]] = kids.get(r["parent"], 0) + 1
        d, i = 1, r["parent"]
        while i != "root" and i in parent:
            d, i = d + 1, parent[i]
        depth_max = max(depth_max, d)
    return [], rows, {"steps": len(rows), "top": [r["id"] for r in rows if r["parent"] == "root"], "widest": max([v for k, v in kids.items() if k != "root"] or [0]),
                      "depth": depth_max, "drawn": drawn, "not_drawn": total - drawn, "ignored": {"self": self_imports}, "groups": groups, "cut": cut,
                      "uses": uses}


def build(grh, pin, strings, live_ids=()):
    """(errors, {relative name: bytes}, rows, report): the files only when there are no errors. `live_ids` are the ids of the repository's outline."""
    errors, rows, rep = build_rows(grh)
    if errors:
        return errors, {}, rows, rep
    errors = [("SKEL-ID-CLASH", i, "") for i in sorted({r["id"] for r in rows} & set(live_ids))]
    if errors:
        return errors, {}, rows, rep
    missing = bs._graph_strings_errors({k: strings[k] for k in bs._graph_strings_keys(SYMBOLS) if k in strings}, SYMBOLS)   # only the missing ones: it holds a subset
    if missing:
        return missing, {}, rows, rep
    errors, objs = bs._graph_files(rows, pin, strings, symbols=SYMBOLS)
    if errors:
        return errors, {}, rows, rep
    objs["graph/uses.json"] = {"commit": pin, "format": bs.GRAPH_FORMAT, "uses": rep["uses"]}
    return [], bs._graph_bytes(objs), rows, rep


USAGE = ("usage: build_grh_skeleton.py --grh DIR --pin COMMIT --strings strings.json --out OUT_DIR [--outline outline.json]\n"
         "       build_grh_skeleton.py --selftest [--only ID,ID] [--grh DIR]")


def _parse(a):
    """{grh, pin, strings, out[, outline]} or None: each option once, with a value; --pin not empty; nothing else."""
    opts, i = {}, 0
    while i < len(a):
        if a[i] in ("--grh", "--pin", "--strings", "--out", "--outline") and a[i][2:] not in opts and i + 1 < len(a):
            opts[a[i][2:]] = a[i + 1]
            i += 2
        else:
            return None
    return opts if {"grh", "pin", "strings", "out"} <= set(opts) and opts["pin"] else None


def report_lines(rep):
    cuts = [f"cut id {full} -> {final}" for full, final in rep["cut"]]
    table = [f"group {g['group']}: files {g['files']}, linked {g['linked']}, unlinked {g['unlinked']}, longest {g['longest']}, "
             f"widest row depth {g['widest_depth']} ({g['widest_count']} files)" for g in rep["groups"]]
    return ([f"steps: {rep['steps']}", "top: " + ", ".join(rep["top"]), f"widest: {rep['widest']}", f"depth: {rep['depth']}",
             f"links drawn: {rep['drawn']}", f"imports not drawn: {rep['not_drawn']}", f"self-imports ignored: {rep['ignored']['self']}",
             f"ids cut: {len(cuts)}"] + cuts + table)


def _run(opts):
    if not os.path.isdir(opts["grh"]):
        raise Unreadable(f"--grh is not a directory: {opts['grh']}")
    if os.path.exists(opts["out"]) and not os.path.isdir(opts["out"]):
        raise Unreadable(f"OUT_DIR is not a directory: {opts['out']}")
    try:
        strings = bs._read_json(opts["strings"], "strings file")
        outline = bs._read_json(opts.get("outline", OUTLINE), "outline")
    except bs._Unreadable as e:
        raise Unreadable(str(e))
    if not (isinstance(outline, dict) and isinstance(outline.get("groups"), list) and all(isinstance(g, dict) and isinstance(g.get("id"), str) for g in outline["groups"])):
        raise Unreadable("cannot read the outline: no `groups` list of objects with an `id`")

    def refuse(errors):
        for code, where, msg in errors:
            print(f"{code} {where}" + (f" {msg}" if msg else ""))
        print("REFUSED: nothing written", file=sys.stderr)
        return 1
    if os.path.isdir(opts["out"]) and os.listdir(opts["out"]):
        return refuse([("OUT-NOT-EMPTY", "OUT_DIR", "already holds files")])
    problems = bs._strings_problems(strings)
    if problems:
        return refuse(problems)
    errors, files, rows, rep = build(opts["grh"], opts["pin"], strings, [g["id"] for g in outline["groups"]])
    if errors:
        return refuse(errors)
    try:
        bs._publish(opts["out"], files)
    except OSError as e:
        raise Unreadable(f"cannot write the graph data: {e.strerror or e}")
    print("\n".join(report_lines(rep)))
    return 0


def main(argv):
    """argv with the program name first."""
    if argv[1:2] == ["--selftest"]:
        return _selftest_main(argv[2:])
    opts = _parse(argv[1:])
    if opts is None:
        print(USAGE, file=sys.stderr)
        return 2
    try:
        return _run(opts)
    except Unreadable as e:
        print("build_grh_skeleton: " + str(e), file=sys.stderr)
        return 2


# ---------------------------------------------------------------- self-test: fixtures are built from literals in a temp folder

class _SkipCase(Exception):
    pass


_GRH_FOR_SK13 = None   # the folder given to `--selftest --grh`; SK13 reads it


def _eq(actual, expected):
    return actual == expected, f"expected {expected!r}, got {actual!r}"


PIN = "0123456789abcdef0123456789abcdef01234567"
HEAD = "# Contents\n\nIntro.\n\n## New\n\n"   # the body of a fixture CONTENTS starts on line 7
TAIL = "\n## Lib\n\n- `Lib/Other/File` (1): Not read\n"
MODULE_ROW = {"class": "kind-module", "words": "symbol_kind_module"}
ORDERS = {"kinds": ["module"], "states": [], "proofs": []}


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


def _strings(extra=True):
    """The strings file of this checkout; with `extra` (the default) its symbol_kind_module is the fixture word `Module words`."""
    with open(os.path.join(_HERE, os.pardir, "site", "strings.json"), encoding="utf-8") as f:
        s = json.load(f)
    if extra:
        s["symbol_kind_module"] = "Module words"
    return s


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


def _outline_file(d, ids=(), name="outline.json"):
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"groups": [{"id": i} for i in ids], "release": "r"}, f)
    return p


def _args(g, out, strings_path, outline, pin=PIN):
    return ["--grh", g, "--pin", pin, "--strings", strings_path, "--out", out, "--outline", outline]


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


def _j(files, name):
    return json.loads(files[name].decode("utf-8"))


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
    "New/Beta/Six": _lean(""),
}
SK3_BODY = """### S part

**Grp**

- `New/S/A` (1): a
- `New/S/B` (1): b
- `New/S/C` (1): c

**Other**

- `New/S/D` (1): d
"""
SK3_SRCS = {"New/S/A": _lean(imports=["New.S.D", "New.S.C", "New.S.B", "New.S.A", "Mathlib.Data.Nat", "Lib.Foo.Bar"]),
            "New/S/B": _lean(imports=["New.S.C"]), "New/S/C": _lean(), "New/S/D": _lean(imports=["New.S.A"])}
CHAIN_BODY = """### T part

**Grp**

- `New/T/A` (1): a
- `New/T/B` (1): b
- `New/T/C` (1): c
- `New/T/D` (1): d
"""
CHAIN_SRCS = {"New/T/A": _lean(imports=["New.T.B", "New.T.C", "New.T.D"]), "New/T/B": _lean(imports=["New.T.C"]), "New/T/C": _lean(imports=["New.T.D"]),
              "New/T/D": _lean()}
ALL_MODULE = ("module", "none", "none")


def _selftest_cases():
    cases = []

    def case(cid, desc):
        def deco(fn):
            cases.append((cid, desc, fn))
            return fn
        return deco

    @case("SK1", "a fixture of 2 sections, 3 groups, 6 files: ids (`lean-` then the kebab case of the folder and file names, `<section>--<slug>` for a group), parents, "
                 "orders, titles with the backticks removed, premises (in-group imports only), kind `module`, state none and proof none for EVERY step; `top` in file "
                 "order, `steps` is the number of step files (graph/uses.json is not a step), every file passes the static check, `assets` is {}")
    def _():
        with _tmp() as d:
            g = _tree(d, SK1_BODY, SK1_SRCS)
            errs, files, rows, rep = build(g, PIN, _strings())
            ix = _j(files, "graph/index.json")
            steps = sorted(k for k in files if k.startswith("graph/step/"))
            ok, why = _eq((errs, _rowtuples(rows)), ([], [
                ("lean-alpha", "root", 0, [], "module", "Alpha part"),
                ("lean-alpha--first-group", "lean-alpha", 0, [], "module", "First group"),
                ("lean-alpha-one", "lean-alpha--first-group", 0, [], "module", "The one file"),
                ("lean-alpha-two-parts", "lean-alpha--first-group", 1, ["lean-alpha-one"], "module", "Second file"),
                ("lean-alpha--second-group", "lean-alpha", 1, [], "module", "Second group"),
                ("lean-alpha-three", "lean-alpha--second-group", 0, [], "module", "Third file"),
                ("lean-beta", "root", 1, [], "module", "Beta part"),
                ("lean-beta--third-group", "lean-beta", 0, [], "module", "Third group"),
                ("lean-beta-four", "lean-beta--third-group", 0, [], "module", "Fourth"),
                ("lean-beta-sub-five", "lean-beta--third-group", 1, ["lean-beta-four"], "module", "Fifth"),
                ("lean-beta-six", "lean-beta--third-group", 2, [], "module", "Sixth")]))
            if not ok:
                return ok, why
            beta5 = _j(files, "graph/step/lean-beta-sub-five.json")
            return _eq(([(r["kind"], r["state"], r["proof"]) for r in rows], ix["top"], ix["steps"], len(steps), ix["assets"], sorted(rows[0]),
                        beta5["path"], beta5["card"]["kind"], beta5["card"]["proof"], beta5["card"]["state"], bs._graph_static_problems(files),
                        sorted(files) == ["graph/index.json"] + steps + ["graph/uses.json"],
                        [c["id"] for c in _j(files, "graph/step/lean-alpha.json")["children"]]),
                       ([ALL_MODULE] * 11, ["lean-alpha", "lean-beta"], 11, 11, {},
                        ["id", "kind", "order", "parent", "premises", "proof", "state", "title"],
                        ["lean-beta", "lean-beta--third-group"], "module", "none", "none", [], True,
                        ["lean-alpha--first-group", "lean-alpha--second-group"]))

    @case("SK2", "a section of one file with no folder (`New/Main`) is a TOP step that is that file: id `lean-main`, a leaf in `top`, no section or group above it; a "
                 "section whose files have no group line gets one anonymous group whose id is `<section>--` and whose title is empty")
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
            main_step = _j(files, "graph/step/lean-main.json")
            return _eq((errs, _rowtuples(rows), _j(files, "graph/index.json")["top"], main_step["path"], main_step["children"], main_step["card"]["child_count"],
                        sorted(k for k in files if "last" in k or "no-groups" in k)),
                       ([], [("lean-alpha", "root", 0, [], "module", "Alpha part"), ("lean-alpha--g", "lean-alpha", 0, [], "module", "G"),
                             ("lean-alpha-one", "lean-alpha--g", 0, [], "module", "One"),
                             ("lean-anon", "root", 1, [], "module", "No groups here"), ("lean-anon--", "lean-anon", 0, [], "module", ""),
                             ("lean-anon-solo", "lean-anon--", 0, [], "module", "Solo"),
                             ("lean-main", "root", 2, [], "module", "From here to there")],
                        ["lean-alpha", "lean-anon", "lean-main"], [], [], 0, []))

    @case("SK3", "premises: a imports b, b imports c, a imports c inside one group: the group's rests_on has a->b and b->c only (a->c is reduced away); an import of a "
                 "file of another group and an import outside New draw no edge; counts are literals (drawn 2, not drawn 3, self-imports 1; an import outside New "
                 "is counted nowhere); a longer chain (a->b->c->d with a->c and a->d) reduces to the chain (drawn 3, not drawn 2)")
    def _():
        with _tmp() as d:
            errs, files, rows, rep = build(_tree(d, SK3_BODY, SK3_SRCS), PIN, _strings())
            grp = _j(files, "graph/step/lean-s--grp.json")
        with _tmp() as d:
            cerrs, cfiles, crows, crep = build(_tree(d, CHAIN_BODY, CHAIN_SRCS), PIN, _strings())
        return _eq((errs, [(r["id"], r["premises"]) for r in rows if r["parent"] == "lean-s--grp"], grp["rests_on"], grp["children"][0]["parent_rests_on"],
                    (rep["drawn"], rep["not_drawn"], rep["ignored"]),
                    cerrs, [(r["id"], r["premises"]) for r in crows if r["parent"] == "lean-t--grp"], (crep["drawn"], crep["not_drawn"])),
                   ([], [("lean-s-a", ["lean-s-b"]), ("lean-s-b", ["lean-s-c"]), ("lean-s-c", [])],
                    [{"from": "lean-s-a", "from_path": ["lean-s", "lean-s--grp"], "to": "lean-s-b", "to_path": ["lean-s", "lean-s--grp"]},
                     {"from": "lean-s-b", "from_path": ["lean-s", "lean-s--grp"], "to": "lean-s-c", "to_path": ["lean-s", "lean-s--grp"]}], False,
                    (2, 3, {"self": 1}),
                    [], [("lean-t-a", ["lean-t-b"]), ("lean-t-b", ["lean-t-c"]), ("lean-t-c", ["lean-t-d"]), ("lean-t-d", [])], (3, 2)))

    @case("SK4", "a cycle among files of one group is refused GRAPH-EDGE (named, from _graph_files), also with a chord; nothing is returned")
    def _():
        body = "### S part\n\n**Grp**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n"
        srcs = {"New/S/A": _lean(imports=["New.S.B"]), "New/S/B": _lean(imports=["New.S.A"])}
        three = body + "- `New/S/C` (1): c\n"
        tsrcs = {"New/S/A": _lean(imports=["New.S.B", "New.S.C"]), "New/S/B": _lean(imports=["New.S.C"]), "New/S/C": _lean(imports=["New.S.A"])}
        with _tmp() as d:
            errs, files, rows, rep = build(_tree(d, body, srcs), PIN, _strings())
        with _tmp() as d:
            e3, f3, r3, rep3 = build(_tree(d, three, tsrcs), PIN, _strings())
        return _eq((errs, files, sorted({c for c, _, _ in e3}), bool(e3), f3),
                   ([("GRAPH-EDGE", "lean-s-b lean-s-a", "cycle in rests_on")], {}, ["GRAPH-EDGE"], True, {}))

    @case("SK5", "kind: EVERY step is `module` whatever the file holds (a theorem, a def, a structure, a note naming a ghost, an empty file): no declaration is read, "
                 "so no file is refused for having none; state and proof are `none` on every step; the symbol table of this tool has the row kinds.module, its order lists are exactly kinds [module], states [] and proofs [], and index.json `strings` "
                 "holds 21 keys; site/strings.json holds symbol_kind_module with its placeholder wording")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n- `New/S/C` (1): c\n- `New/S/D` (1): d\n- `New/S/E` (1): e\n"
        srcs = {"New/S/A": _lean("theorem x : True := trivial", note="The `x` one"), "New/S/B": _lean("def y : Nat := 1"),
                "New/S/C": _lean("structure Z where\n  x : Nat", note="The `ghost` one"), "New/S/D": "", "New/S/E": "-- nothing here\n"}
        with _tmp() as d:
            errs, files, rows, rep = build(_tree(d, body, srcs), PIN, _strings())
            ix = _j(files, "graph/index.json")
        return _eq((errs, sorted({(r["kind"], r["state"], r["proof"]) for r in rows}), len(rows), ix["symbols"]["order"], ix["symbols"]["kinds"]["module"],
                    len(ix["strings"]), ix["strings"]["symbol_kind_module"], _strings(extra=False)["symbol_kind_module"]),
                   ([], [ALL_MODULE], 7, ORDERS,
                    {"class": "kind-module", "text": "Module words", "words": "symbol_kind_module"}, 21, "Module words",
                    "A folder or file of the Lean code, shown as it is"))

    @case("SK6", "uses sidecar: graph/uses.json is {commit: the pin, format: 1, uses: {file id: [ids of every New file it imports, in any group, sorted, no self]}} "
                 "with an entry for every FILE step and none for a section or a group; an import outside New is not in it; it is not in index.json `steps`")
    def _():
        with _tmp() as d:
            errs, files, rows, rep = build(_tree(d, SK3_BODY, SK3_SRCS), PIN, _strings())
        u = _j(files, "graph/uses.json")
        return _eq((errs, u, files["graph/uses.json"].endswith(b"\n"), _j(files, "graph/index.json")["steps"]),
                   ([], {"commit": PIN, "format": 1,
                         "uses": {"lean-s-a": ["lean-s-b", "lean-s-c", "lean-s-d"], "lean-s-b": ["lean-s-c"], "lean-s-c": [], "lean-s-d": ["lean-s-a"]}},
                    True, 7))

    @case("SK7", "completeness: a file listed in CONTENTS and not on disk is `SKEL-MISSING <path>` and a .lean file under src/New that is not listed is `SKEL-UNLISTED "
                 "<path>`, all of them in one run (missing in CONTENTS order, then unlisted sorted); in the CLI: exit 1, the lines on stdout, OUT not written; "
                 "a line of the New section that does not parse is `SKEL-LINE <n>` (n = its line in CONTENTS.md), and so is a file whose folder is not its section's")
    def _():
        body = "### S part\n\n**Grp**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n- `New/S/C` (1): c\n"
        srcs = {"New/S/A": _lean(), "New/S/Z": _lean(), "New/S/Y": _lean()}
        bad = "### Sec\n\n**G**\n\n- `New/S/A` (1): ok\nThis is a prose line.\n- `New/S/B` 5: no parens\n"
        folders = "### Sec\n\n**G**\n\n- `New/S/A` (1): ok\n- `New/T/B` (1): other folder\n"
        flat = "### Sec\n\n**G**\n\n- `New/X` (1): no folder\n- `New/S/B` (1): has one\n"
        with _tmp() as d:
            g = _tree(d, body, srcs)
            errs = build_rows(g)[0]
            sp = _strings_file(d)
            rc, out, err = _cli(_args(g, os.path.join(d, "out"), sp, _outline_file(d)))
            absent = not os.path.exists(os.path.join(d, "out"))
        lines = []
        for b in (bad, folders, flat):
            with _tmp() as d2:
                lines.append(build_rows(_tree(d2, b, {}))[0])
        return _eq((errs, rc, out.splitlines(), absent, lines),
                   ([("SKEL-MISSING", "New/S/B", ""), ("SKEL-MISSING", "New/S/C", ""), ("SKEL-UNLISTED", "New/S/Y", ""), ("SKEL-UNLISTED", "New/S/Z", "")],
                    1, ["SKEL-MISSING New/S/B", "SKEL-MISSING New/S/C", "SKEL-UNLISTED New/S/Y", "SKEL-UNLISTED New/S/Z"], True,
                    [[("SKEL-LINE", "12", ""), ("SKEL-LINE", "13", "")], [("SKEL-LINE", "12", "")], [("SKEL-LINE", "11", "")]]))

    @case("SK8", "41 files in one group are refused GRAPH-FANOUT (named with the group id and the count), 40 are accepted and written (42 steps)")
    def _():
        def fx(n):
            body = "### W part\n\n**G**\n\n" + "".join(f"- `New/W/F{i:02d}` (1): f\n" for i in range(1, n + 1))
            return body, {f"New/W/F{i:02d}": _lean() for i in range(1, n + 1)}
        with _tmp() as d:
            e41, f41, r41, _r = build(_tree(d, *fx(41)), PIN, _strings())
        with _tmp() as d:
            e40, f40, r40, _r = build(_tree(d, *fx(40)), PIN, _strings())
        return _eq((e41, f41, e40, len(f40), _j(f40, "graph/index.json")["steps"]),
                   ([("GRAPH-FANOUT", "lean-w--g", "has 41 children (more than 40)")], {}, [], 44, 42))

    @case("SK9", "ids: slug folds accents to ASCII (NFKD), lower-cases and turns every run of other characters into one `-`; two groups of one section whose titles "
                 "give one slug are GRAPH-DUP; a folder name that cannot make an id (a dot) is GRAPH-ID (nothing is corrected); kebab: a lower-case letter before an "
                 "upper-case one gets `-`, `_` becomes `-`")
    def _():
        body = "### S part\n\n**Alpha, beta**\n\n- `New/S/A` (1): a\n\n**Alpha beta!**\n\n- `New/S/B` (1): b\n"
        dot = "### U part\n\n**G**\n\n- `New/Bad.Dir/X` (1): x\n"
        with _tmp() as d:
            edup = build(_tree(d, body, {"New/S/A": _lean(), "New/S/B": _lean()}), PIN, _strings())[0]
        with _tmp() as d:
            eid = build(_tree(d, dot, {"New/Bad.Dir/X": _lean()}), PIN, _strings())[0]
        return _eq((slug("Café, Théorème & `x`!"), slug("Mind's \"eye\""), slug("  --A  b--  "), slug("aθb"), kebab("OneLift"), kebab("UpperBound"), kebab("a_Bc"),
                    kebab("FieldsAndPlaces"), kebab("Main"), edup, [(c, w) for c, w, _ in eid]),
                   ("cafe-theoreme-x", "mind-s-eye", "a-b", "a-b", "one-lift", "upper-bound", "a-bc", "fields-and-places", "main",
                    [("GRAPH-DUP", "lean-s--alpha-beta", "is the id of more than one group")],
                    [("GRAPH-ID", "lean-bad.dir"), ("GRAPH-ID", "lean-bad.dir--g"), ("GRAPH-ID", "lean-bad.dir-x")]))

    @case("SK10", "determinism and escaping: two runs under PYTHONHASHSEED 0 and 1 write byte-identical files (uses.json too); keys are sorted in every object; `<`, `>` and "
                  "`&` are escaped (a hostile title, `<img onerror>` with a backtick span, is escaped in the JSON); the `commit` of every file equals --pin")
    def _():
        hostile = "<img src=x onerror=alert(1)> & `code`"
        body = f"### S part\n\n**G**\n\n- `New/S/A` (1): {hostile}\n- `New/S/B` (1): b\n"
        srcs = {"New/S/A": _lean(), "New/S/B": _lean(imports=["New.S.A"])}
        with _tmp() as d:
            g = _tree(d, body, srcs)
            sp = _strings_file(d)
            ol = _outline_file(d)
            runs = []
            for seed in ("0", "1"):
                out = os.path.join(d, "out" + seed)
                env = dict(os.environ, PYTHONHASHSEED=seed)
                r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, out, sp, ol, pin="pinX"), env=env, capture_output=True, text=True)
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
        return _eq((rc0, rc1, f0 == f1, sorted(f0), sorted_ok,
                    b"\\u003cimg src=x onerror=alert(1)\\u003e \\u0026 code" in f0["graph/step/lean-s-a.json"],
                    [any(c in data for c in (b"<", b">", b"&")) for data in f0.values()].count(True),
                    sorted({json.loads(data)["commit"] for data in f0.values()})),
                   (0, 0, True, ["graph/index.json", "graph/step/lean-s--g.json", "graph/step/lean-s-a.json", "graph/step/lean-s-b.json", "graph/step/lean-s.json",
                                 "graph/uses.json"], True, True, 0, ["pinX"]))

    @case("SK11", "exit codes: 0 built (OUT holds `graph` and nothing else), 1 refused (OUT absent after; a non-empty OUT is refused and left as it was; a strings file "
                  "without a key is refused as build_site refuses it, and the pure build reports GRAPH-STRINGS, no crash), 2 for a missing, repeated or unknown option, an "
                  "empty --pin, or an input that cannot be read (a folder that is not there, a strings file that is not JSON); a normal run does not run the self-test")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n"
        srcs = {"New/S/A": _lean()}
        with _tmp() as d:
            g = _tree(d, body, srcs)
            sp = _strings_file(d)
            ol = _outline_file(d)
            out = os.path.join(d, "out")
            called = []
            real = globals()["selftest"]
            globals()["selftest"] = lambda *a, **k: called.append(1) or 4
            try:
                rc0 = _cli(_args(g, out, sp, ol))
            finally:
                globals()["selftest"] = real
            listing = sorted(os.listdir(out))
            full = os.path.join(d, "full")
            os.makedirs(full)
            with open(os.path.join(full, "keep.txt"), "w") as f:
                f.write("x")
            rc_full = _cli(_args(g, full, sp, ol))[0]
            held = sorted(os.listdir(full))
            nopin = _cli(["--grh", g, "--strings", sp, "--out", os.path.join(d, "o2"), "--outline", ol])
            dup = _cli(_args(g, os.path.join(d, "o3"), sp, ol) + ["--pin", "x"])[0]
            unk = _cli(_args(g, os.path.join(d, "o4"), sp, ol) + ["--force"])[0]
            emptypin = _cli(_args(g, os.path.join(d, "o5"), sp, ol, pin=""))[0]
            nofolder = _cli(_args(os.path.join(d, "nothing"), os.path.join(d, "o6"), sp, ol))[0]
            bad = os.path.join(d, "bad.json")
            with open(bad, "w") as f:
                f.write("{not json")
            notjson = _cli(_args(g, os.path.join(d, "o7"), bad, ol))[0]
            s2 = _strings()
            del s2["sheet_proof_read"]
            nokey = _cli(_args(g, os.path.join(d, "o8"), _strings_file(d, s2, "strings2.json"), ol))
            built_nokey = os.path.exists(os.path.join(d, "o8"))
            s3 = _strings()
            del s3["parts_n"]
            errs3 = build(g, PIN, s3)[0]
            s4 = _strings()
            del s4["symbol_kind_module"]
            errs4 = build(g, PIN, s4)[0]
            absent = [os.path.exists(os.path.join(d, n)) for n in ("o2", "o3", "o4", "o5", "o6", "o7")]
        return _eq((rc0[0], rc0[1].splitlines()[:1] != [], called, listing, rc_full, held, nopin[0], nopin[1], nopin[2] != "", dup, unk, emptypin, nofolder, notjson,
                    nokey[0], nokey[1].splitlines(), built_nokey, errs3, errs4, absent),
                   (0, True, [], ["graph"], 1, ["keep.txt"], 2, "", True, 2, 2, 2, 2, 2,
                    1, ["STRINGS-KEY sheet_proof_read missing"], False, [("GRAPH-STRINGS", "parts_n", "missing")],
                    [("GRAPH-STRINGS", "symbol_kind_module", "missing")], [False] * 6))

    @case("SK12", "the written graph/index.json and every step file equal what build_site's _graph_files and _graph_bytes return for the rows (literal rows and a literal "
                  "table with the module row here): the tool adds no key and drops none, `assets` is {}, and graph/uses.json is the one more file")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n"
        srcs = {"New/S/A": _lean("def a : Nat := 1"), "New/S/B": _lean("theorem b : True := trivial", imports=["New.S.A"])}

        def row(i, parent, order, premises, title):
            return {"id": i, "parent": parent, "order": order, "premises": premises, "kind": "module", "state": "none", "proof": "none", "title": title}
        rows = [row("lean-s", "root", 0, [], "S part"), row("lean-s--g", "lean-s", 0, [], "G"),
                row("lean-s-a", "lean-s--g", 0, [], "a"), row("lean-s-b", "lean-s--g", 1, ["lean-s-a"], "b")]
        table = dict(bs.GRAPH_SYMBOLS, kinds=dict(bs.GRAPH_SYMBOLS["kinds"], module=MODULE_ROW))
        want_errs, want_objs = bs._graph_files(rows, PIN, _strings(), symbols=table, orders=ORDERS)
        want = bs._graph_bytes(want_objs)
        with _tmp() as d:
            g = _tree(d, body, srcs)
            sp = _strings_file(d)
            out = os.path.join(d, "out")
            rc = _cli(_args(g, out, sp, _outline_file(d)))[0]
            got = _tree_files(out)
        uses = got.pop("graph/uses.json")
        return _eq((rc, want_errs, got == want, _j(want, "graph/index.json")["assets"], len(got), uses != b""), (0, [], True, {}, 5, True))

    @case("SK14", "ids are at most 64 characters: an id longer than 64 is cut to its first 57 characters, trailing `-` removed, then `-` and the first 6 hex digits of the "
                  "sha256 of the FULL id; a 64-character id is unchanged and a 65-character one is cut; a planted 80-character group title gives "
                  "`lean-s--` + 49 `a` + `-95d13c` (sha256 of the 88-character id `lean-s--` + 80 `a`, first 6 hex digits); two titles with the same first 57 characters of "
                  "id give two ids; the cut is reported")
    def _():
        long_title = "a" * 80
        two = [("a" * 49 + "c" * 10), ("a" * 49 + "d" * 10)]
        body = ("### S part\n\n**" + long_title + "**\n\n- `New/S/A` (1): a\n\n**" + two[0] + "**\n\n- `New/S/B` (1): b\n\n**" + two[1] + "**\n\n- `New/S/C` (1): c\n")
        with _tmp() as d:
            errs, files, rows, rep = build(_tree(d, body, {"New/S/A": _lean(), "New/S/B": _lean(), "New/S/C": _lean()}), PIN, _strings())
        ids = [r["id"] for r in rows if r["parent"] == "lean-s"]
        full = "lean-s--" + "a" * 80
        return _eq((_cap("x" * 64) == "x" * 64, _cap("x" * 65), len(_cap("x" * 65)), _cap("short"),
                    _cap("lean-s--" + "a" * 48 + "-" + "b" * 30), errs, ids, [len(i) for i in ids], rep["cut"][0], len(rep["cut"]), max(len(r["id"]) for r in rows)),
                   (True, "x" * 57 + "-9537c5", 64, "short", "lean-s--" + "a" * 48 + "-cbbf2f", [],
                    ["lean-s--" + "a" * 49 + "-95d13c", "lean-s--" + "a" * 49 + "-3bd149", "lean-s--" + "a" * 49 + "-ac8b56"], [64, 64, 64],
                    (full, "lean-s--" + "a" * 49 + "-95d13c"), 3, 64))

    @case("SK15", "id clash: an id this tool makes that is also an id of the repository's live outline is `SKEL-ID-CLASH <id>` (all of them, sorted; exit 1 in the CLI, "
                  "OUT not written); disjoint ids build; an outline that is not JSON, or has no `groups` list, is exit 2")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n"
        with _tmp() as d:
            g = _tree(d, body, {"New/S/A": _lean()})
            clash = build(g, PIN, _strings(), live_ids=["zeta", "lean-s-a", "lean-s"])[0]
            fine = build(g, PIN, _strings(), live_ids=["zeta", "lean-sa"])[0]
            sp = _strings_file(d)
            bad = _cli(_args(g, os.path.join(d, "o1"), sp, _outline_file(d, ["lean-s-a"])))
            good = _cli(_args(g, os.path.join(d, "o2"), sp, _outline_file(d, ["other"], "ol2.json")))[0]
            nj = os.path.join(d, "notjson.json")
            with open(nj, "w") as f:
                f.write("{x")
            ng = os.path.join(d, "nogroups.json")
            with open(ng, "w") as f:
                f.write('{"release": "r"}')
            rc_nj = _cli(_args(g, os.path.join(d, "o3"), sp, nj))[0]
            rc_ng = _cli(_args(g, os.path.join(d, "o4"), sp, ng))[0]
            absent = [os.path.exists(os.path.join(d, n)) for n in ("o1", "o3", "o4")]
        return _eq((clash, fine, bad[0], bad[1].splitlines(), good, rc_nj, rc_ng, absent),
                   ([("SKEL-ID-CLASH", "lean-s", ""), ("SKEL-ID-CLASH", "lean-s-a", "")], [], 1, ["SKEL-ID-CLASH lean-s-a"], 0, 2, 2, [False] * 3))

    @case("SK16", "order is CONTENTS line order and nothing else: with sections, groups and files whose alphabetical order differs from the file's, `top` and every "
                  "step's children array follow the file, never a sort")
    def _():
        body = """### Zeta part

**Zed group**

- `New/Zeta/Zz` (1): z
- `New/Zeta/Aa` (1): a

**Abe group**

- `New/Zeta/Mm` (1): m

### Alpha part

**G**

- `New/Alpha/Bb` (1): b
"""
        srcs = {"New/Zeta/Zz": _lean(), "New/Zeta/Aa": _lean(), "New/Zeta/Mm": _lean(), "New/Alpha/Bb": _lean()}
        with _tmp() as d:
            errs, files, rows, rep = build(_tree(d, body, srcs), PIN, _strings())
        kids = lambda i: [c["id"] for c in _j(files, f"graph/step/{i}.json")["children"]]
        return _eq((errs, _j(files, "graph/index.json")["top"], kids("lean-zeta"), kids("lean-zeta--zed-group"), [r["order"] for r in rows]),
                   ([], ["lean-zeta", "lean-alpha"], ["lean-zeta--zed-group", "lean-zeta--abe-group"], ["lean-zeta-zz", "lean-zeta-aa"], [0, 0, 0, 1, 1, 0, 1, 0, 0]))

    @case("SK17", "edges: a section or a group has no premise ever; a section's step file and index.json hold `rests_on: []` (present, empty); a group's step file holds the "
                  "links among its own files (empty and present when it has none)")
    def _():
        with _tmp() as d:
            errs, files, rows, rep = build(_tree(d, SK3_BODY, SK3_SRCS), PIN, _strings())
        return _eq((errs, [r["premises"] for r in rows if r["proof"] == "none" and r["id"] in ("lean-s", "lean-s--grp", "lean-s--other")],
                    _j(files, "graph/index.json")["rests_on"], _j(files, "graph/step/lean-s.json")["rests_on"],
                    _j(files, "graph/step/lean-s--other.json")["rests_on"], len(_j(files, "graph/step/lean-s--grp.json")["rests_on"]),
                    "rests_on" in _j(files, "graph/step/lean-s-d.json"), _j(files, "graph/step/lean-s-d.json")["rests_on"]),
                   ([], [[], [], []], [], [], [], 2, True, []))

    @case("SK18", "the per-group table of the report: files, files with at least one drawn link (either end), files with none, the longest path of rests_on and the "
                  "widest depth row (depth 0 = a file that rests on nothing; the smallest depth wins a tie)")
    def _():
        fan = "### F part\n\n**Fan**\n\n" + "".join(f"- `New/F/{n}` (1): {n}\n" for n in "XYZWV")
        fsrcs = {"New/F/X": _lean(), "New/F/Y": _lean(imports=["New.F.X"]), "New/F/Z": _lean(imports=["New.F.X"]), "New/F/W": _lean(imports=["New.F.X"]),
                 "New/F/V": _lean()}
        with _tmp() as d:
            fe, ff, fr, frep = build(_tree(d, fan, fsrcs), PIN, _strings())
        with _tmp() as d:
            ce, cf, cr, crep = build(_tree(d, CHAIN_BODY, CHAIN_SRCS), PIN, _strings())
        with _tmp() as d:
            se, sf, sr, srep = build(_tree(d, SK3_BODY, SK3_SRCS), PIN, _strings())
        return _eq((fe, frep["groups"], ce, crep["groups"], se, srep["groups"]),
                   ([], [{"group": "lean-f--fan", "files": 5, "linked": 4, "unlinked": 1, "longest": 1, "widest_depth": 1, "widest_count": 3}],
                    [], [{"group": "lean-t--grp", "files": 4, "linked": 4, "unlinked": 0, "longest": 3, "widest_depth": 0, "widest_count": 1}],
                    [], [{"group": "lean-s--grp", "files": 3, "linked": 3, "unlinked": 0, "longest": 2, "widest_depth": 0, "widest_count": 1},
                         {"group": "lean-s--other", "files": 1, "linked": 0, "unlinked": 1, "longest": 0, "widest_depth": 0, "widest_count": 1}]))

    @case("SK13", "the real source (give `--selftest --grh DIR`; otherwise SKIPPED): 352 steps all module with state and proof none, top of 9 in CONTENTS order, widest 23, "
                  "depth 3, 298 links drawn and 226 imports not drawn, every id at most 64 characters with exactly 3 cut, the first 3 children of the first group of "
                  "lean-reduction are the first 3 file lines of that group in CONTENTS, the live outline's ids are disjoint from the build's")
    def _():
        if _GRH_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh given to the self-test")
        with open(os.path.join(_HERE, os.pardir, "outline", "outline.json"), encoding="utf-8") as f:
            live = [g["id"] for g in json.load(f)["groups"]]
        errs, files, rows, rep = build(_GRH_FOR_SK13, "72fead102f663d5c7a407964a13dc0cf9d977207", _strings(), live_ids=live)
        with open(os.path.join(_GRH_FOR_SK13, "CONTENTS.md"), encoding="utf-8") as f:
            lines = f.read().split("\n")
        i = lines.index("## New")
        j = next(k for k in range(i, len(lines)) if lines[k].startswith("**"))
        first3 = [re.fullmatch(r"- `New/[^`]+` \(\d+\): (.*)", ln).group(1).replace("`", "") for ln in [x for x in lines[j:] if x.startswith("- `New/")][:3]]
        gid = next(r["id"] for r in rows if r["parent"] == "lean-reduction")
        kids = _j(files, f"graph/step/{gid}.json")["children"][:3]
        order = _j(files, "graph/index.json")["symbols"]["order"]
        return _eq((errs, order, len(live), rep["steps"], sorted({(r["kind"], r["state"], r["proof"]) for r in rows}), rep["top"], rep["widest"], rep["depth"], rep["drawn"],
                    rep["not_drawn"], max(len(r["id"]) for r in rows), len(rep["cut"]), [c["title"] for c in kids] == first3, len(first3), len(files)),
                   ([], ORDERS, 23, 352, [ALL_MODULE],
                    ["lean-reduction", "lean-derivatives", "lean-upper-bound", "lean-spanning", "lean-determinant", "lean-one-lift", "lean-congruences", "lean-appendix",
                     "lean-main"], 23, 3, 298, 226, 64, 3, True, 3, 354))

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
