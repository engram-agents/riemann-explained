#!/usr/bin/env python3
"""The skeleton of the map for a Lean repository that keeps its own index (CONTENTS.md) and its own folders.

usage: build_grh_skeleton.py --grh DIR --pin COMMIT --strings strings.json --out OUT_DIR [--outline outline.json] [--strings-overlay overlay.json]
       build_grh_skeleton.py --selftest [--only ID,ID] [--grh DIR]

DIR is the folder that holds CONTENTS.md and src/. The tool reads the `## New` section of CONTENTS.md and the .lean files under src/New and writes
OUT_DIR/graph/index.json, OUT_DIR/graph/step/<id>.json and OUT_DIR/graph/uses.json, and nothing else: no page, no assets (`assets` is {}). It builds ROWS (id,
parent, order, premises, kind, state, proof, title) and hands them to build_site's `_graph_files` and `_graph_bytes`, with a symbol table of its own (`symbols=`) that has
only the three kinds (part, group, file) as rows, its order lists (`orders=`) and `layout="column"`; it has no writer of its own for the graph objects, and every refusal of the graph contract (GRAPH-FANOUT, GRAPH-ID, GRAPH-DUP, GRAPH-PARENT,
GRAPH-CYCLE, GRAPH-EDGE, GRAPH-SYMBOL, GRAPH-COUNT, GRAPH-STRINGS) is that function's. --pin is written as the `commit` of every file. --outline (default:
outline/outline.json of this checkout) names the repository's own outline, whose group ids must not be ids of this tool. --strings-overlay (default:
site/strings-lean.json) holds keys that replace or add to the strings file for this map only; no file is edited. Exit 0 built; 1 refused, OUT_DIR not
written (the build goes into a sibling folder that is renamed into place); 2 usage error or an input that cannot be read. A normal run does NOT run the
self-test; --selftest does (0 pass, 4 fail, 2 an unknown id after --only). SK13 reads the real source and runs only when --grh is given to the self-test;
otherwise it is skipped.

THE RULES (all mechanical; nothing is typed by hand; kind and face lines are the skeleton's own rules, not reading)
 1 TREE. CONTENTS.md, section `## New` only, in the order of its lines (nothing is sorted, nothing comes from the file system). Each `### heading` is a section;
   a line that is only `**title**` is a group of that section; a line `- `New/<path>` (<n>): <title>` is a file of the latest group. A section whose files have
   no group line gets one anonymous group (id `<section>--`, empty title). A section of exactly one file whose path has no folder (`New/Main`) is a top step
   that is the child of a part made from the heading (its id is the slug of the heading), with no group between. Steps: part > group > file.
 2 IDS. Every id starts with `lean-`. Section: the folder name (the second path segment) in kebab case (a lower-case letter followed by an upper-case one gets
   `-`; `_` becomes `-`; then lower case). Group: `<section id>--<slug of its title>` (NFKD, accents dropped, lower case, each run of characters outside a-z0-9
   one `-`, trimmed). File: its path after `New/`, each segment in kebab case, joined by `-`. An id longer than 64 characters is cut to its first 57, a trailing
   `-` removed, then `-` and the first 6 hex digits of the sha256 of the whole id; an id of 64 or fewer is never touched. A clash is GRAPH-DUP, a bad character
   GRAPH-ID, never corrected; an id that is also an id of the outline is SKEL-ID-CLASH.
 3 TITLES. A file: the text after the colon, exactly as written (a backtick span keeps its backticks). A group: its bold text. A section: its heading. The 50-character bound of the graph
   contract (the face line) is NOT applied here: it lives in build_site's `_graph_line_errors`, which this tool does not call.
 4 PREMISES. A file rests on a file of the SAME group that it imports (`import New.X.Y` at the start of a line), after the transitive reduction of each group's
   edges. A self-import and an import outside New are ignored; an import of a New file of another group (and a reduced one) is not drawn but is listed in
   graph/uses.json. Groups and sections have no premises. A cycle among the files of a group is left as it is (GRAPH-EDGE).
 5 KIND, STATE, PROOF. A `###` heading is a `part`, a bold line a `group`, a file line a `file`; every step has state `none`, proof `none`. No declaration is read.
 6 USES. graph/uses.json holds, for every file step, the ids of every New file it imports, in any group, sorted, never itself. It is not part of index.json.
 7 COMPLETENESS. Every .lean file under src/New is a file line of CONTENTS and every file line exists: SKEL-UNLISTED / SKEL-MISSING (`<path>` as in CONTENTS,
   without `.lean`); a line of the section that does not parse, or a file whose folder is not its section's, is SKEL-LINE <n> (n is the line of CONTENTS.md).
   All of one kind are reported together.
 8 STRINGS. The strings file is read and checked as build_site does and overlaid; `_graph_files` checks the exact key set (23 keys: the kind words and the card words come from the overlay).
"""
import contextlib
import errno
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import stat
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


class SourceError(Exception):
    """A file that cannot be taken as an input of the build (`reason` says why): the caller names it in a SKEL-* line."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


SOURCE_READ_LIMIT = 1048576   # the most bytes of a source file the tool reads (1 MiB)


PREFIX = "lean-"      # every id of this tool starts with it: its own namespace, apart from the ids of the repository's outline
ID_MAX = 64           # the longest id (the page's router refuses a longer target)
ID_KEEP = 57          # an id longer than ID_MAX keeps this many characters, then `-` and ID_HASH hex digits of the sha256 of the whole id
ID_HASH = 6
KINDS = ("part", "group", "file")   # a part is a `###` heading, a group a bold line, a file a file line
SYMBOLS = dict(bs.GRAPH_SYMBOLS, kinds={k: {"card_words": f"card_kind_{k}", "class": f"kind-{k}", "words": f"symbol_kind_{k}"} for k in KINDS})   # this tool's table: its three kinds, today's states and proofs
MAP_ORDERS = {"kinds": list(KINDS), "states": [], "proofs": []}   # what is drawn on this map: the three kinds; no state or proof (a card of these kinds has no status)
OVERLAY = os.path.join(_HERE, os.pardir, "site", "strings-lean.json")
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
            item = {"path": f.group(1), "title": f.group(3), "line": n}
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
            errors.extend(("SKEL-LINE", str(g["line"]), "") for g in s["groups"] if not g["files"])   # a bold line with no file in a section of one file
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


def _read_bounded(path, limit):
    """The bytes of the regular file `path`, read through ONE descriptor that is opened without following a symlink and without blocking (so a FIFO does not hang the open),
    checked with fstat, and read at most `limit` + 1 bytes. Raises SourceError: missing, symlink, not-a-regular-file, too-large, unreadable."""
    try:
        if stat.S_ISLNK(os.lstat(path).st_mode):
            raise SourceError("symlink")
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0))
    except OSError as e:
        raise SourceError("missing" if e.errno == errno.ENOENT else ("symlink" if e.errno == errno.ELOOP else "unreadable"))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise SourceError("not-a-regular-file")
        chunks, need = [], limit + 1
        while need > 0:
            part = os.read(fd, min(need, 65536))
            if not part:
                break
            chunks.append(part)
            need -= len(part)
        data = b"".join(chunks)
        if len(data) > limit:
            raise SourceError("too-large")
        return data
    except OSError:
        raise SourceError("unreadable")
    finally:
        os.close(fd)


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
    for r, ds, fs in os.walk(os.path.join(base, "New"), onerror=fail):
        found += [os.path.relpath(os.path.join(r, n), base)[:-len(".lean")].replace(os.sep, "/") for n in fs + ds if n.endswith(".lean")]   # a directory named X.lean is listed too: it is refused as not a regular file
    return sorted(found)


def _group_report(gid, members, kept):
    """The numbers of one group for the report: files, files that are an end of a drawn link, files with none, the longest path of `rests_on` and the depth row with most files
    (depth 0 = a file that rests on nothing; the smallest depth wins a tie)."""
    ends = {p for p in members if kept[p]} | {q for p in members for q in kept[p]}
    depth = _depths(kept)
    per = {}
    for v in (depth or {}).values():
        per[v] = per.get(v, 0) + 1
    wide = min((k for k in per if per[k] == max(per.values())), default=0)
    return {"group": gid, "files": len(members), "linked": len(ends), "unlinked": len(members) - len(ends),
            "longest": max((depth or {}).values(), default=0), "widest_depth": wide, "widest_count": per.get(wide, 0)}


def _report(rows, drawn, total, self_imports, groups, cut, uses):
    """The report of a build: the steps, the top ids, the widest step, the depth, the counts of the links and of the kinds, the groups, the ids that were cut, the uses."""
    kids, depth_max = {}, 0
    parent = {r["id"]: r["parent"] for r in rows}
    for r in rows:
        kids[r["parent"]] = kids.get(r["parent"], 0) + 1
        d, i = 1, r["parent"]
        while i != "root" and i in parent:
            d, i = d + 1, parent[i]
        depth_max = max(depth_max, d)
    return {"steps": len(rows), "top": [r["id"] for r in rows if r["parent"] == "root"], "widest": max([v for k, v in kids.items() if k != "root"] or [0]),
            "depth": depth_max, "drawn": drawn, "not_drawn": total - drawn, "ignored": {"self": self_imports}, "groups": groups, "cut": cut,
            "kinds": {k: sum(1 for r in rows if r["kind"] == k) for k in KINDS}, "uses": uses}


def build_rows(grh):
    """(errors, rows, report) from the folder `grh`: SKEL-LINE, then SKEL-MISSING and SKEL-UNLISTED, then SKEL-SOURCE (a source file that cannot be read, all reported), each stops the run before the next stage."""
    sections, errors = parse_contents(_read(os.path.join(grh, "CONTENTS.md"), "CONTENTS.md"))
    if errors:
        return errors, [], {}
    listed = [f["path"] for s in sections for g in s["groups"] for f in g["files"]]
    disk = _disk_paths(grh)
    errors = [("SKEL-MISSING", p, "") for p in listed if p not in set(disk)] + [("SKEL-UNLISTED", p, "") for p in disk if p not in set(listed)]
    if errors:
        return errors, [], {}
    src = {}
    for p in listed:
        try:
            src[p] = _read_bounded(os.path.join(grh, "src", *p.split("/")) + ".lean", SOURCE_READ_LIMIT).decode("utf-8")
        except SourceError as e:
            errors.append(("SKEL-SOURCE", p, e.reason))
        except UnicodeDecodeError:
            errors.append(("SKEL-SOURCE", p, "not-utf-8"))
    if errors:
        return errors, [], {}
    cut = []

    def ident(i):
        if not bs.GRAPH_ID.fullmatch(i):   # a bad id is never cut (the cut could hide its bad character): _graph_files names the whole id
            return i
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

    def row(i, parent, order, prem, kind, title):
        rows.append({"id": i, "parent": parent, "order": order, "premises": prem, "kind": kind, "state": "none", "proof": "none", "title": title})
    for ti, s in enumerate(sections):
        if s["top_file"]:   # a part whose one file has no folder: the part is made from the heading, the file is its child (no group between)
            f = next(f for g in s["groups"] for f in g["files"])
            pid = ident(PREFIX + slug(s["heading"]))
            row(pid, "root", ti, [], "part", s["heading"])
            row(fid[f["path"]], pid, 0, [], "file", f["title"])
            continue
        sid = PREFIX + kebab(s["folder"])
        sid_id = ident(sid)
        row(sid_id, "root", ti, [], "part", s["heading"])
        for gi, g in enumerate(s["groups"]):
            gid = ident(f"{sid}--{slug(g['title'] or '')}")
            row(gid, sid_id, gi, [], "group", g["title"] or "")
            members, kept = group_files[(ti, gi)]
            for fi, f in enumerate(g["files"]):
                row(fid[f["path"]], gid, fi, premises[f["path"]], "file", f["title"])
            groups.append(_group_report(gid, members, kept))
    return [], rows, _report(rows, drawn, total, self_imports, groups, cut, uses)


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
    errors, objs = bs._graph_files(rows, pin, strings, symbols=SYMBOLS, orders=MAP_ORDERS, layout="column")
    if errors:
        return errors, {}, rows, rep
    objs["graph/uses.json"] = {"commit": pin, "format": bs.GRAPH_FORMAT, "uses": rep["uses"]}
    return [], bs._graph_bytes(objs), rows, rep


USAGE = ("usage: build_grh_skeleton.py --grh DIR --pin COMMIT --strings strings.json --out OUT_DIR [--outline outline.json] [--strings-overlay overlay.json]\n"
         "       build_grh_skeleton.py --selftest [--only ID,ID] [--grh DIR]")


def _parse(a):
    """{grh, pin, strings, out[, outline][, strings-overlay]} or None: each option once, with a value; --pin not empty; nothing else."""
    opts, i = {}, 0
    while i < len(a):
        if a[i] in ("--grh", "--pin", "--strings", "--out", "--outline", "--strings-overlay") and a[i][2:] not in opts and i + 1 < len(a):
            opts[a[i][2:]] = a[i + 1]
            i += 2
        else:
            return None
    return opts if {"grh", "pin", "strings", "out"} <= set(opts) and opts["pin"] else None


def report_lines(rep):
    cuts = [f"cut id {full} -> {final}" for full, final in rep["cut"]]
    table = [f"group {g['group']}: files {g['files']}, linked {g['linked']}, unlinked {g['unlinked']}, longest {g['longest']}, "
             f"widest row depth {g['widest_depth']} ({g['widest_count']} files)" for g in rep["groups"]]
    return ([f"steps: {rep['steps']}", "kinds: " + ", ".join(f"{k} {rep['kinds'][k]}" for k in KINDS), "top: " + ", ".join(rep["top"]), f"widest: {rep['widest']}", f"depth: {rep['depth']}",
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
        overlay = bs._read_json(opts.get("strings-overlay", OVERLAY), "strings overlay")
    except bs._Unreadable as e:
        raise Unreadable(str(e))
    if not (isinstance(overlay, dict) and isinstance(strings, dict)):
        raise Unreadable("cannot read the strings overlay: it and the strings file must be JSON objects")
    strings = dict(strings, **overlay)   # the overlay's keys replace or add to the strings file, for this map only (no file is edited)
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
KIND_ROWS = {"part": {"card_words": "card_kind_part", "class": "kind-part", "words": "symbol_kind_part"},
             "group": {"card_words": "card_kind_group", "class": "kind-group", "words": "symbol_kind_group"},
             "file": {"card_words": "card_kind_file", "class": "kind-file", "words": "symbol_kind_file"}}
ORDERS = {"kinds": ["part", "group", "file"], "states": [], "proofs": []}
OVERLAY_WORDS = {"key_kinds_heading": "What a box is", "symbol_kind_part": "Part of the argument", "symbol_kind_group": "Group of files",
                 "symbol_kind_file": "Lean file", "card_kind_part": "Part", "card_kind_group": "Group", "card_kind_file": "File"}
OPTIONAL_WORDS = {"key_kinds_note": "Parts and groups follow the repository's own contents list (CONTENTS.md).", "note_label": "From the repository, unchanged",
                  "note_source": "Source file: {source} \u00b7 version {commit} of lsernau/grh-lean"}   # the three optional page-drawn words, final


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
        with open(fp, "wb") as f:
            f.write(text if isinstance(text, bytes) else text.encode("utf-8"))
    return g


def _strings(extra=True):
    """The strings file of this checkout; with `extra` (the default) the overlay words of this map are in it, as the literals of OVERLAY_WORDS."""
    with open(os.path.join(_HERE, os.pardir, "site", "strings.json"), encoding="utf-8") as f:
        s = json.load(f)
    if extra:
        s.update(OVERLAY_WORDS)
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


def _args(g, out, strings_path, outline, pin=PIN, overlay=None):
    return ["--grh", g, "--pin", pin, "--strings", strings_path, "--out", out, "--outline", outline] + (["--strings-overlay", overlay] if overlay else [])


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


def _selftest_cases():
    cases = []

    def case(cid, desc):
        def deco(fn):
            cases.append((cid, desc, fn))
            return fn
        return deco

    @case("SK1", "a fixture of 2 sections, 3 groups, 6 files: ids (`lean-` then the kebab case of the folder and file names, `<section>--<slug>` for a group), parents, "
                 "orders, titles exactly as written in CONTENTS (a backtick span keeps its backticks, in the step file and in the parent's `children` entry), premises (in-group imports only), kinds part, group and file, state none and proof none for EVERY step; `top` in file "
                 "order, `steps` is the number of step files (graph/uses.json is not a step), every file passes the static check, `assets` is {}")
    def _():
        with _tmp() as d:
            g = _tree(d, SK1_BODY, SK1_SRCS)
            errs, files, rows, rep = build(g, PIN, _strings())
            ix = _j(files, "graph/index.json")
            steps = sorted(k for k in files if k.startswith("graph/step/"))
            ok, why = _eq((errs, _rowtuples(rows)), ([], [
                ("lean-alpha", "root", 0, [], "part", "Alpha part"),
                ("lean-alpha--first-group", "lean-alpha", 0, [], "group", "First group"),
                ("lean-alpha-one", "lean-alpha--first-group", 0, [], "file", "The `one` file"),
                ("lean-alpha-two-parts", "lean-alpha--first-group", 1, ["lean-alpha-one"], "file", "Second file"),
                ("lean-alpha--second-group", "lean-alpha", 1, [], "group", "Second group"),
                ("lean-alpha-three", "lean-alpha--second-group", 0, [], "file", "Third file"),
                ("lean-beta", "root", 1, [], "part", "Beta part"),
                ("lean-beta--third-group", "lean-beta", 0, [], "group", "Third group"),
                ("lean-beta-four", "lean-beta--third-group", 0, [], "file", "Fourth"),
                ("lean-beta-sub-five", "lean-beta--third-group", 1, ["lean-beta-four"], "file", "Fifth"),
                ("lean-beta-six", "lean-beta--third-group", 2, [], "file", "Sixth")]))
            if not ok:
                return ok, why
            beta5 = _j(files, "graph/step/lean-beta-sub-five.json")
            return _eq(([(r["kind"], r["state"], r["proof"]) for r in rows], ix["top"], ix["steps"], len(steps), ix["assets"], sorted(rows[0]),
                        beta5["path"], beta5["card"]["kind"], beta5["card"]["proof"], beta5["card"]["state"], bs._graph_static_problems(files),
                        sorted(files) == ["graph/index.json"] + steps + ["graph/uses.json"],
                        [c["id"] for c in _j(files, "graph/step/lean-alpha.json")["children"]],
                        _j(files, "graph/step/lean-alpha-one.json")["card"]["title"],
                        [c["title"] for c in _j(files, "graph/step/lean-alpha--first-group.json")["children"]]),
                       ([("part", "none", "none"), ("group", "none", "none"), ("file", "none", "none"), ("file", "none", "none"), ("group", "none", "none"),
                         ("file", "none", "none"), ("part", "none", "none"), ("group", "none", "none"), ("file", "none", "none"), ("file", "none", "none"),
                         ("file", "none", "none")], ["lean-alpha", "lean-beta"], 11, 11, {},
                        ["id", "kind", "order", "parent", "premises", "proof", "state", "title"],
                        ["lean-beta", "lean-beta--third-group"], "file", "none", "none", [], True,
                        ["lean-alpha--first-group", "lean-alpha--second-group"], "The `one` file", ["The `one` file", "Second file"]))

    @case("SK2", "a section of one file with no folder (`New/Main`) is the CHILD of a part made from the heading (id `lean-the-last-file`), with no group between; "
                 "a section whose files have no group line gets one anonymous group whose id is `<section>--` and whose title is empty; the kinds are part, group, file")
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
            last = _j(files, "graph/step/lean-the-last-file.json")
            return _eq((errs, _rowtuples(rows), _j(files, "graph/index.json")["top"], main_step["path"], main_step["children"], main_step["card"]["child_count"],
                        [c["id"] for c in last["children"]], last["card"]["kind"], main_step["card"]["kind"], sorted(k for k in files if "no-groups" in k)),
                       ([], [("lean-alpha", "root", 0, [], "part", "Alpha part"), ("lean-alpha--g", "lean-alpha", 0, [], "group", "G"),
                             ("lean-alpha-one", "lean-alpha--g", 0, [], "file", "One"),
                             ("lean-anon", "root", 1, [], "part", "No groups here"), ("lean-anon--", "lean-anon", 0, [], "group", ""),
                             ("lean-anon-solo", "lean-anon--", 0, [], "file", "Solo"),
                             ("lean-the-last-file", "root", 2, [], "part", "The last file"),
                             ("lean-main", "lean-the-last-file", 0, [], "file", "From here to there")],
                        ["lean-alpha", "lean-anon", "lean-the-last-file"], ["lean-the-last-file"], [], 0, ["lean-main"], "part", "file", []))

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

    @case("SK5", "kinds are read off CONTENTS: `part` for each `###` heading, `group` for each bold line (an anonymous group too), `file` for each file line; the table of "
                 "this tool has exactly the rows part, group, file (classes kind-part|kind-group|kind-file, words symbol_kind_part|group|file) and the three rows of the "
                 "states and of the proofs; order lists kinds [part, group, file], states [], proofs []; state and proof are `none` on every card; index.json `strings` is "
                 "23 keys with the overlay words and has no symbol_kind_module; index.json has sibling_layout column; site/strings.json has no symbol_kind_module")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n\n### T part\n\n- `New/T/C` (1): c\n"
        srcs = {"New/S/A": _lean("theorem x : True := trivial"), "New/S/B": "", "New/T/C": "-- nothing here\n"}
        with _tmp() as d:
            errs, files, rows, rep = build(_tree(d, body, srcs), PIN, _strings())
            ix = _j(files, "graph/index.json")
        return _eq((errs, [r["kind"] for r in rows], rep["kinds"], sorted({(r["state"], r["proof"]) for r in rows}), ix["symbols"]["order"],
                    {k: v for k, v in ix["symbols"]["kinds"].items()}, sorted(ix["symbols"]["states"]), sorted(ix["symbols"]["proofs"]), len(ix["strings"]),
                    ix["strings"]["key_kinds_heading"], "symbol_kind_module" in ix["strings"], ix["sibling_layout"], "symbol_kind_module" in _strings(extra=False),
                    sorted({c["state"] for k, v in files.items() if k.startswith("graph/step/") for c in [json.loads(v.decode("utf-8"))["card"]]})),
                   ([], ["part", "group", "file", "file", "part", "group", "file"], {"part": 2, "group": 2, "file": 3}, [("none", "none")], ORDERS,
                    {"part": {"card_words": "card_kind_part", "class": "kind-part", "text": "Part of the argument", "words": "symbol_kind_part"},
                     "group": {"card_words": "card_kind_group", "class": "kind-group", "text": "Group of files", "words": "symbol_kind_group"},
                     "file": {"card_words": "card_kind_file", "class": "kind-file", "text": "Lean file", "words": "symbol_kind_file"}},
                    ["census", "none", "read"], ["none", "not_read", "read"], 23, "What a box is", False, "column", False, ["none"]))

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
                  "`&` are escaped (a hostile title, `<img onerror>` with a backtick span, is escaped in the JSON and keeps its backticks); the `commit` of every file equals --pin")
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
                    b"\\u003cimg src=x onerror=alert(1)\\u003e \\u0026 `code`" in f0["graph/step/lean-s-a.json"],
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
            del s4["symbol_kind_file"]
            errs4 = build(g, PIN, s4)[0]
            absent = [os.path.exists(os.path.join(d, n)) for n in ("o2", "o3", "o4", "o5", "o6", "o7")]
        return _eq((rc0[0], rc0[1].splitlines()[:1] != [], called, listing, rc_full, held, nopin[0], nopin[1], nopin[2] != "", dup, unk, emptypin, nofolder, notjson,
                    nokey[0], nokey[1].splitlines(), built_nokey, errs3, errs4, absent),
                   (0, True, [], ["graph"], 1, ["keep.txt"], 2, "", True, 2, 2, 2, 2, 2,
                    1, ["STRINGS-KEY sheet_proof_read missing"], False, [("GRAPH-STRINGS", "parts_n", "missing")],
                    [("GRAPH-STRINGS", "symbol_kind_file", "missing")], [False] * 6))

    @case("SK12", "the written graph/index.json and every step file equal what build_site's _graph_files and _graph_bytes return for the rows (literal rows and a literal "
                  "table of the three kinds here): the tool adds no key and drops none, `assets` is {}, and graph/uses.json is the one more file")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n"
        srcs = {"New/S/A": _lean("def a : Nat := 1"), "New/S/B": _lean("theorem b : True := trivial", imports=["New.S.A"])}

        def row(i, parent, order, premises, kind, title):
            return {"id": i, "parent": parent, "order": order, "premises": premises, "kind": kind, "state": "none", "proof": "none", "title": title}
        rows = [row("lean-s", "root", 0, [], "part", "S part"), row("lean-s--g", "lean-s", 0, [], "group", "G"),
                row("lean-s-a", "lean-s--g", 0, [], "file", "a"), row("lean-s-b", "lean-s--g", 1, ["lean-s-a"], "file", "b")]
        table = dict(bs.GRAPH_SYMBOLS, kinds=KIND_ROWS)
        want_errs, want_objs = bs._graph_files(rows, PIN, dict(_strings(), **OPTIONAL_WORDS), symbols=table, orders=ORDERS, layout="column")
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

    @case("SK3b", "a link inside a group is never reduced by a path that leaves the group: a imports b (same group), a imports x and x imports b (x in another group): "
                  "a still rests on b (drawn 1, not drawn 2)")
    def _():
        body = "### S part\n\n**Grp**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n\n**Other**\n\n- `New/S/X` (1): x\n"
        srcs = {"New/S/A": _lean(imports=["New.S.B", "New.S.X"]), "New/S/B": _lean(), "New/S/X": _lean(imports=["New.S.B"])}
        with _tmp() as d:
            errs, files, rows, rep = build(_tree(d, body, srcs), PIN, _strings())
        return _eq((errs, [(r["id"], r["premises"]) for r in rows if r["parent"] == "lean-s--grp"], rep["drawn"], rep["not_drawn"]),
                   ([], [("lean-s-a", ["lean-s-b"]), ("lean-s-b", [])], 1, 2))

    @case("SK19", "titles are the CONTENTS text with no bound: a file title of 98 characters, a group title and a section heading of 60, both with a backtick span, are kept whole (no refusal, no cut, backticks kept)")
    def _():
        ft = "w" * 49 + " " + "z" * 48
        gt = "g" * 30 + " `" + "h" * 27 + "`"
        st = "s" * 30 + " `" + "t" * 27 + "`"
        body = f"### {st}\n\n**{gt}**\n\n- `New/S/A` (1): {ft}\n"
        with _tmp() as d:
            errs, files, rows, rep = build(_tree(d, body, {"New/S/A": _lean()}), PIN, _strings())
        return _eq((errs, [len(r["title"]) for r in rows], [r["title"] for r in rows] == [st, gt, ft]), ([], [60, 60, 98], True))

    @case("SK20", "determinism of the sidecar: a file that imports six files has its uses listed in sorted order under both hash seeds (graph/uses.json is byte-identical "
                  "and its list is the sorted literal)")
    def _():
        names = "ABCDEF"
        body = "### S part\n\n**Grp**\n\n" + "".join(f"- `New/S/{n}` (1): {n}\n" for n in names) + "\n**Hub**\n\n- `New/S/Hub` (1): hub\n"
        srcs = {f"New/S/{n}": _lean() for n in names}
        srcs["New/S/Hub"] = _lean(imports=[f"New.S.{n}" for n in "FCEBDA"])
        with _tmp() as d:
            g = _tree(d, body, srcs)
            sp = _strings_file(d)
            ol = _outline_file(d)
            got = []
            for seed in ("0", "1", "2"):
                out = os.path.join(d, "out" + seed)
                r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, out, sp, ol), env=dict(os.environ, PYTHONHASHSEED=seed),
                                   capture_output=True, text=True)
                got.append((r.returncode, _tree_files(out)["graph/uses.json"]))
        u = json.loads(got[0][1].decode("utf-8"))["uses"]["lean-s-hub"]
        return _eq(([g[0] for g in got], got[0][1] == got[1][1] == got[2][1], u), ([0, 0, 0], True, [f"lean-s-{n}" for n in "abcdef"]))

    @case("SK21", "the strings overlay (`--strings-overlay FILE`): its keys replace or add to the strings file for this map only; with the overlay giving the three kind "
                  "words and a new heading the index holds exactly the 23 keys with those words (an extra overlay key is not in it); the strings file is not edited; an "
                  "overlay without one kind word is refused GRAPH-STRINGS (exit 1); a file that is not there, not JSON or not an object is exit 2; the overlay file of this "
                  "checkout (site/strings-lean.json) holds exactly ten words: the seven of OVERLAY_WORDS (the kinds heading, the three kind words and the three card words, "
                  "placeholders) and the three of OPTIONAL_WORDS (final)")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n"
        full = {"key_kinds_heading": "Replaced heading", "symbol_kind_part": "P words", "symbol_kind_group": "G words", "symbol_kind_file": "F words",
                "card_kind_part": "P", "card_kind_group": "G", "card_kind_file": "F", "extra_key": "x"}
        with _tmp() as d:
            g = _tree(d, body, {"New/S/A": _lean()})
            sp = _strings_file(d, _strings(extra=False))
            before = open(sp, "rb").read()
            ol = _outline_file(d)

            def overlay(obj, name):
                path = os.path.join(d, name)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(obj if isinstance(obj, str) else json.dumps(obj))
                return path
            ok = _cli(_args(g, os.path.join(d, "o1"), sp, ol, overlay=overlay(full, "ov1.json")))
            ix = _j(_tree_files(os.path.join(d, "o1")), "graph/index.json")
            part = {k: v for k, v in full.items() if k != "symbol_kind_group"}
            short = _cli(_args(g, os.path.join(d, "o2"), sp, ol, overlay=overlay(part, "ov2.json")))
            nocard = _cli(_args(g, os.path.join(d, "o6"), sp, ol, overlay=overlay({k: v for k, v in full.items() if k != "card_kind_group"}, "ov6.json")))
            gone = _cli(_args(g, os.path.join(d, "o3"), sp, ol, overlay=os.path.join(d, "nothing.json")))[0]
            bad = _cli(_args(g, os.path.join(d, "o4"), sp, ol, overlay=overlay("{x", "ov4.json")))[0]
            arr = _cli(_args(g, os.path.join(d, "o5"), sp, ol, overlay=overlay("[1]", "ov5.json")))[0]
            unchanged = open(sp, "rb").read() == before
            absent = [os.path.exists(os.path.join(d, n)) for n in ("o2", "o3", "o4", "o5")]
        with open(os.path.join(_HERE, os.pardir, "site", "strings-lean.json"), encoding="utf-8") as f:
            repo_overlay = json.load(f)
        return _eq((ok[0], len(ix["strings"]), ix["strings"]["key_kinds_heading"], ix["symbols"]["kinds"]["file"]["text"], ix["symbols"]["kinds"]["file"]["card_words"],
                    ix["strings"]["card_kind_file"], "extra_key" in ix["strings"], unchanged, short[0], short[1].splitlines(), nocard[0], nocard[1].splitlines(), gone, bad, arr,
                    absent, repo_overlay),
                   (0, 23, "Replaced heading", "F words", "card_kind_file", "F", False, True, 1, ["GRAPH-STRINGS symbol_kind_group missing"], 1,
                    ["GRAPH-STRINGS card_kind_group missing"], 2, 2, 2, [False] * 4, dict(OVERLAY_WORDS, **OPTIONAL_WORDS)))

    @case("SK22", "a section of one file with no folder whose first bold line holds no file (`### X`, `**A**`, `**B**`, the file `New/Main`) is `SKEL-LINE <n>` for the empty bold line "
                  "(a named refusal, exit 1, no traceback), and the same section with its one bold line over the file builds")
    def _():
        bad = "### X\n**A**\n**B**\n- `New/Main` (1): m\n"
        good = "### X\n**B**\n- `New/Main` (1): m\n"
        with _tmp() as d:
            g = _tree(d, bad, {"New/Main": _lean()})
            errs = build_rows(g)[0]
            rc, out, err = _cli(_args(g, os.path.join(d, "out"), _strings_file(d), _outline_file(d)))
        with _tmp() as d:
            ok = build(_tree(d, good, {"New/Main": _lean()}), PIN, _strings())
        return _eq((errs, rc, out.splitlines(), "Traceback" in err, ok[0], [r["id"] for r in ok[2]]), ([("SKEL-LINE", "8", "")], 1, ["SKEL-LINE 8"], False, [], ["lean-x", "lean-main"]))

    @case("SK23", "an id that is cut cannot hide a bad character: the UNCUT id is checked against the id pattern first, so a file name with a non-ASCII character past the 57th "
                  "character of an over-long id (`New/X/` + 60 `a` + `\u00e9`) is GRAPH-ID with the whole id, as it is at the front; an over-long id of good characters is still cut")
    def _():
        name = "a" * 60 + "\u00e9"
        body = f"### X part\n\n**G**\n\n- `New/X/{name}` (1): x\n"
        with _tmp() as d:
            errs = build(_tree(d, body, {f"New/X/{name}": _lean()}), PIN, _strings())[0]
        good = "a" * 60 + "b"
        with _tmp() as d:
            ok = build(_tree(d, f"### X part\n\n**G**\n\n- `New/X/{good}` (1): x\n", {f"New/X/{good}": _lean()}), PIN, _strings())
        return _eq(([(c, w) for c, w, _ in errs], ok[0], len(ok[3]["cut"]), [len(r["id"]) for r in ok[2]]), ([("GRAPH-ID", "lean-x-" + name)], [], 1, [6, 9, 64]))

    @case("SK24", "a source file is read through one bounded, non-blocking, non-following descriptor: a .lean that is a symlink (to a file outside the tree), a FIFO, a directory or "
                  "larger than 1 MiB, or not UTF-8, is `SKEL-SOURCE <path> <reason>` (`symlink`, `not-a-regular-file`, `not-a-regular-file`, `too-large`, `not-utf-8`; all reported, "
                  "exit 1, OUT not written), and one of exactly 1 MiB is read. The case runs the CLI in a subprocess with a 60 second timeout, so a tool that blocked on the FIFO "
                  "would fail the case, not hang the self-test")
    def _():
        body = "### S part\n\n**G**\n\n" + "".join(f"- `New/S/{n}` (1): {n}\n" for n in "ABCDEFG")
        limit = 1048576
        srcs = {f"New/S/{n}": _lean() for n in "ABCDEFG"}
        srcs["New/S/D"] = "-" * (limit + 1)
        srcs["New/S/E"] = "-" * limit
        srcs["New/S/G"] = b"\xff\xfe"
        with _tmp() as d:
            g = _tree(d, body, srcs)
            base = os.path.join(g, "src", "New", "S")
            outside = os.path.join(d, "outside.lean")
            with open(outside, "w") as f:
                f.write("theorem x : True := trivial\n")
            os.remove(os.path.join(base, "A.lean"))
            os.symlink(outside, os.path.join(base, "A.lean"))
            os.remove(os.path.join(base, "B.lean"))
            os.mkfifo(os.path.join(base, "B.lean"))
            os.remove(os.path.join(base, "C.lean"))
            os.mkdir(os.path.join(base, "C.lean"))
            out = os.path.join(d, "out")
            r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, out, _strings_file(d), _outline_file(d)), capture_output=True, text=True, timeout=60)
            absent = not os.path.exists(out)
        return _eq((r.returncode, r.stdout.splitlines(), "Traceback" in r.stderr, absent),
                   (1, ["SKEL-SOURCE New/S/A symlink", "SKEL-SOURCE New/S/B not-a-regular-file", "SKEL-SOURCE New/S/C not-a-regular-file", "SKEL-SOURCE New/S/D too-large",
                        "SKEL-SOURCE New/S/G not-utf-8"], False, True))

    @case("SK25", "the other branches of the CONTENTS reader each give `SKEL-LINE <n>` with their own line: a bold line that holds another bold span (`**one** and **two**`), a file "
                  "before the first bold line of a section that has bold lines, a `###` heading with no file, and a bold line with no file in a section that has files")
    def _():
        bold = "### Sec\n\n**one** and **two**\n\n- `New/S/A` (1): a\n"
        loose = "### Sec\n- `New/S/A` (1): a\n**G**\n- `New/S/B` (1): b\n"
        empty = "### Empty\n\n### Sec\n**G**\n- `New/S/A` (1): a\n"
        group = "### Sec\n**Empty**\n**G**\n- `New/S/A` (1): a\n"
        out = []
        for b in (bold, loose, empty, group):
            with _tmp() as d:
                out.append(build_rows(_tree(d, b, {}))[0])
        return _eq(out, [[("SKEL-LINE", "9", "")], [("SKEL-LINE", "8", "")], [("SKEL-LINE", "7", "")], [("SKEL-LINE", "8", "")]])

    @case("SK26", "the three optional page words (key_kinds_note, note_label, note_source; final, `{source}` and `{commit}` kept literal) are index.json `strings` keys when the strings "
                  "hold them: 23 keys with none, 25 with two, 26 with all three, the values exactly the literals of OPTIONAL_WORDS (typed in this case as well); the overlay file of "
                  "this checkout holds those three values")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n"
        typed = {"key_kinds_note": "Parts and groups follow the repository's own contents list (CONTENTS.md).", "note_label": "From the repository, unchanged",
                 "note_source": "Source file: {source} \u00b7 version {commit} of lsernau/grh-lean"}
        with _tmp() as d:
            g = _tree(d, body, {"New/S/A": _lean()})
            n = lambda extra: len(_j(build(g, PIN, dict(_strings(), **extra))[1], "graph/index.json")["strings"])
            full = _j(build(g, PIN, dict(_strings(), **OPTIONAL_WORDS))[1], "graph/index.json")["strings"]
            counts = (n({}), n({"note_label": "L", "note_source": "S"}), n(OPTIONAL_WORDS))
        with open(os.path.join(_HERE, os.pardir, "site", "strings-lean.json"), encoding="utf-8") as f:
            overlay = json.load(f)
        return _eq((counts, OPTIONAL_WORDS == typed, {k: full[k] for k in typed}, {k: overlay.get(k) for k in typed}), ((23, 25, 26), True, typed, typed))

    @case("SK28", "hostile folders and CONTENTS.md, one tree per row of the colleague's table, each a named refusal (exit 1, no traceback, OUT not written, no hang: the CLI runs in a "
                  "subprocess with a 60 second timeout): `src` a symlink to a folder outside, `src/New` a symlink, CONTENTS.md a symlink, CONTENTS.md a FIFO, CONTENTS.md over 4 MiB, "
                  "an intermediate folder `src/New/S` a symlink to a folder outside")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n"
        srcs = {"New/S/A": _lean(), "New/S/B": _lean()}
        limit = 4 * 1024 * 1024
        res = {}
        for kind in ("src", "srcnew", "contents", "fifo", "big", "inter"):
            with _tmp() as d:
                g = _tree(d, body, srcs)
                if kind == "src":
                    shutil.move(os.path.join(g, "src"), os.path.join(d, "outside"))
                    os.symlink(os.path.join(d, "outside"), os.path.join(g, "src"))
                elif kind == "srcnew":
                    shutil.move(os.path.join(g, "src", "New"), os.path.join(d, "outside"))
                    os.symlink(os.path.join(d, "outside"), os.path.join(g, "src", "New"))
                elif kind == "inter":
                    shutil.move(os.path.join(g, "src", "New", "S"), os.path.join(d, "outside"))
                    os.symlink(os.path.join(d, "outside"), os.path.join(g, "src", "New", "S"))
                else:
                    c = os.path.join(g, "CONTENTS.md")
                    if kind == "contents":
                        shutil.move(c, os.path.join(d, "real.md"))
                        os.symlink(os.path.join(d, "real.md"), c)
                    elif kind == "fifo":
                        os.remove(c)
                        os.mkfifo(c)
                    else:
                        with open(c, "a") as f:
                            f.write(" " * (limit + 1 - os.path.getsize(c)))
                out = os.path.join(d, "out")
                r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, out, _strings_file(d), _outline_file(d)), capture_output=True, text=True, timeout=60)
                res[kind] = (r.returncode, r.stdout.splitlines(), "Traceback" in r.stderr, os.path.exists(out))
        return _eq(res, {"src": (1, ["SKEL-ESCAPE src symlink"], False, False), "srcnew": (1, ["SKEL-ESCAPE src/New symlink"], False, False),
                         "contents": (1, ["SKEL-CONTENTS CONTENTS.md symlink"], False, False), "fifo": (1, ["SKEL-CONTENTS CONTENTS.md not-a-regular-file"], False, False),
                         "big": (1, ["SKEL-CONTENTS CONTENTS.md too-large"], False, False), "inter": (1, ["SKEL-ESCAPE src/New/S symlink"], False, False)})

    @case("SK29", "the two guards against a symlink are each pinned ALONE: with only the lstat guard a symlink is refused `symlink`, with only O_NOFOLLOW it is refused `symlink`, with "
                  "neither it is read through the link (so each guard is what refuses, not a second copy of the other); with both (the default) it is refused; a FIFO is refused "
                  "`not-a-regular-file` by fstat whatever the guards, without blocking")
    def _():
        with _tmp() as d:
            real = os.path.join(d, "real.txt")
            with open(real, "wb") as f:
                f.write(b"x")
            link = os.path.join(d, "link.txt")
            os.symlink(real, link)
            fifo = os.path.join(d, "fifo")
            os.mkfifo(fifo)

            def attempt(path, **kw):
                try:
                    return ("ok", _read_bounded(path, 100, **kw))
                except SourceError as e:
                    return ("err", e.reason)
            got = (attempt(link), attempt(link, guards=("lstat",)), attempt(link, guards=("nofollow",)), attempt(link, guards=()), attempt(real, guards=()),
                   attempt(fifo, guards=()), attempt(fifo))
        return _eq(got, (("err", "symlink"), ("err", "symlink"), ("err", "symlink"), ("ok", b"x"), ("ok", b"x"), ("err", "not-a-regular-file"), ("err", "not-a-regular-file")))

    @case("SK30", "containment by REAL path: _contained(root, path) is true for the root and for a file under it, false for a file reached through a symlinked folder that leads "
                  "outside (every component is covered, not only the last), false for a sibling folder whose name starts with the root's name; _read_in refuses a path that is not "
                  "contained with `outside`, reads one that is, and a symlink to a file INSIDE the root is still refused by the descriptor guards (`symlink`)")
    def _():
        with _tmp() as d:
            root = os.path.join(d, "grh")
            os.makedirs(os.path.join(root, "inside"))
            os.makedirs(os.path.join(d, "grh2"))
            os.makedirs(os.path.join(d, "elsewhere"))
            for p_ in (os.path.join(root, "inside", "f.txt"), os.path.join(d, "grh2", "f.txt"), os.path.join(d, "elsewhere", "f.txt")):
                with open(p_, "wb") as f:
                    f.write(b"x")
            os.symlink(os.path.join(d, "elsewhere"), os.path.join(root, "via"))
            os.symlink(os.path.join(root, "inside", "f.txt"), os.path.join(root, "inside", "l.txt"))

            def rd(path):
                try:
                    return ("ok", _read_in(root, path, 10))
                except SourceError as e:
                    return ("err", e.reason)
            got = (_contained(root, root), _contained(root, os.path.join(root, "inside", "f.txt")), _contained(root, os.path.join(root, "via", "f.txt")),
                   _contained(root, os.path.join(d, "grh2", "f.txt")), _contained(root, os.path.join(d, "elsewhere", "f.txt")),
                   rd(os.path.join(root, "inside", "f.txt")), rd(os.path.join(root, "via", "f.txt")), rd(os.path.join(root, "inside", "l.txt")))
        return _eq(got, (True, True, False, False, False, ("ok", b"x"), ("err", "outside"), ("err", "symlink")))

    @case("SK13", "the real source (give `--selftest --grh DIR`; otherwise SKIPPED): 353 steps (parts 9, groups 38, files 306) with state and proof none, the three cut ids literally, top of 9 in CONTENTS order, widest 23, "
                  "depth 3, 298 links drawn and 226 imports not drawn, every id at most 64 characters with exactly 3 cut, the first 3 children of the first group of "
                  "lean-reduction are the first 3 file lines of that group in CONTENTS, the live outline's ids are disjoint from the build's, "
                  "every title (353 of 353, in the rows and in the step files) equals its CONTENTS text byte for byte and 22 of them hold a backtick, and the static check passes on the output")
    def _():
        if _GRH_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh given to the self-test")
        with open(os.path.join(_HERE, os.pardir, "outline", "outline.json"), encoding="utf-8") as f:
            live = [g["id"] for g in json.load(f)["groups"]]
        errs, files, rows, rep = build(_GRH_FOR_SK13, "72fead102f663d5c7a407964a13dc0cf9d977207", _strings(), live_ids=live)
        cut_ids = sorted(final for _, final in rep["cut"])
        with open(os.path.join(_GRH_FOR_SK13, "CONTENTS.md"), encoding="utf-8") as f:
            lines = f.read().split("\n")
        i = lines.index("## New")
        j = next(k for k in range(i, len(lines)) if lines[k].startswith("**"))
        first3 = [re.fullmatch(r"- `New/[^`]+` \(\d+\): (.*)", ln).group(1) for ln in [x for x in lines[j:] if x.startswith("- `New/")][:3]]
        src_titles = []
        for ln in lines[i + 1:]:
            if ln.startswith("## "):
                break
            m = re.fullmatch(r"- `New/[^`]+` \(\d+\): (.*)", ln)
            if ln.startswith("### "):
                src_titles.append(ln[4:])
            elif ln.startswith("**") and ln.endswith("**"):
                src_titles.append(ln[2:-2])
            elif m:
                src_titles.append(m.group(1))
        by_id = {r["id"]: r["title"] for r in rows}
        card_titles = [_j(files, f"graph/step/{r['id']}.json")["card"]["title"] for r in rows]
        gid = next(r["id"] for r in rows if r["parent"] == "lean-reduction")
        kids = _j(files, f"graph/step/{gid}.json")["children"][:3]
        order = _j(files, "graph/index.json")["symbols"]["order"]
        stems = sum(1 for k, v in files.items() if k.startswith("graph/step/") for c in json.loads(v.decode("utf-8"))["children"] if c["parent_rests_on"])
        return _eq((errs, order, _j(files, "graph/index.json")["sibling_layout"], stems, len(_j(files, "graph/index.json")["strings"]), len(live), rep["steps"], rep["kinds"], sorted({(r["state"], r["proof"]) for r in rows}), rep["top"], rep["widest"], rep["depth"], rep["drawn"],
                    rep["not_drawn"], max(len(r["id"]) for r in rows), len(rep["cut"]), cut_ids, [c["title"] for c in kids] == first3, len(first3), len(files),
                    [r["title"] for r in rows] == src_titles, card_titles == src_titles, len(src_titles), sum("`" in s for s in src_titles), bs._graph_static_problems(files)),
                   ([], ORDERS, "column", 0, 23, 23, 353, {"part": 9, "group": 38, "file": 306}, [("none", "none")],
                    ["lean-reduction", "lean-derivatives", "lean-upper-bound", "lean-spanning", "lean-determinant", "lean-one-lift", "lean-congruences", "lean-appendix",
                     "lean-the-last-file"], 23, 3, 298, 226, 64, 3,
                    ["lean-congruences--lifting-crystalline-extension-classes-i-07869b", "lean-congruences-galois-representations-rows-and-columns-7a36a5",
                     "lean-one-lift--hecke-l-values-as-squared-norms-and-their-25fb42"], True, 3, 355, True, True, 353, 22, []))

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
