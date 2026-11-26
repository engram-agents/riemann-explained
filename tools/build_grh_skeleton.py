#!/usr/bin/env python3
"""The skeleton of the map for a Lean repository that keeps its own index (CONTENTS.md) and its own folders.

usage: build_grh_skeleton.py --grh DIR --pin COMMIT --strings strings.json --out OUT_DIR --ilean-dir DIR [--outline outline.json] [--strings-overlay overlay.json] [--strings-overlay-graph overlay.json]
       build_grh_skeleton.py --selftest [--only ID,ID] [--grh DIR] [--ilean-dir DIR]

DIR is the folder that holds CONTENTS.md and src/. The tool reads the `## New` section of CONTENTS.md and the .lean files under src/New and writes
OUT_DIR/graph/index.json, OUT_DIR/graph/step/<id>.json and OUT_DIR/graph/uses.json, and nothing else: no page, no assets (`assets` is {}). It builds ROWS (id,
parent, order, premises, kind, state, proof, title) and hands them to build_site's `_graph_files` and `_graph_bytes`, with a symbol table of its own (`symbols=`) that has
only the three kinds (part, group, file) as rows, its order lists (`orders=`) and `layout="column"`; it has no writer of its own for the graph objects, and every refusal of the graph contract (GRAPH-FANOUT, GRAPH-ID, GRAPH-DUP, GRAPH-PARENT,
GRAPH-CYCLE, GRAPH-EDGE, GRAPH-SYMBOL, GRAPH-COUNT, GRAPH-STRINGS) is that function's. --pin is written as the `commit` of every file. --outline (default:
outline/outline.json of this checkout) names the repository's own outline, whose group ids must not be ids of this tool. --strings-overlay (default:
site/strings-lean.json) holds keys that replace or add to the strings file for this map only; no file is edited. --strings-overlay-graph (no default; site/strings-lean-graph.json
holds the Graph view's words) adds the words only the Graph view reads: without it the build is a Cards-only build, the file's keys are not in `strings` and spine.json has no `edge_basis`;
a key in both overlays, or in it and the strings file, is refused `SKEL-OVERLAY-CLASH <key>`; a key of either overlay that the page does not read (not copied into `strings`) is refused `SKEL-OVERLAY-KEY <overlay file name> <key> is not a key the page reads`. A Graph-view build passes --strings-overlay-graph; one that passes only --strings-overlay is Cards-only.
The Graph overlay is read by the same reader as the Cards overlay and its keys meet the same `{n}` placeholder rule at build time; the value rules (no `[proposal]`, no `[placeholder]`, no
word `edge`) are not checked by the build: case OVL1 holds them on the checked-in file of each overlay. Every .ilean the tool loads must have `version` exactly 5 (ILEAN_VERSIONS), else
`SKEL-ILEAN-VERSION <path under --ilean-dir> <value as JSON text, or missing>`. Exit 0 built; 1 refused, OUT_DIR not
written (the build goes into a sibling folder that is renamed into place); 2 usage error or an input that cannot be read. A normal run does NOT run the
self-test; --selftest does (0 pass, 4 fail, 2 an unknown id after --only). SK13 and U5 read the real source and run only when --grh and --ilean-dir are given to
the self-test; otherwise they are skipped.

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
 4 LINKS. A file rests on another New file of the SAME group that it USES: a constant reference of its .ilean (read from --ilean-dir as data) with at least one usage;
   the weight is the number of distinct names used. The data is not reduced; each link has weight and in_reduction (membership in the transitive reduction of the
   group's uses). A use across groups is not drawn, only listed in uses.json. Groups and sections have no premises. The uses of files must be acyclic (SKEL-USES-CYCLE).
 5 KIND, STATE, PROOF. A `###` heading is a `part`, a bold line a `group`, a file line a `file`; every step has state `none`, proof `none`. No declaration is read.
 6 USES. graph/uses.json (format 2) holds, for every file step, `imports` (the New files it directly imports, sorted) and `uses` ({id, names, same_group} for every New
   file it uses, in any group, sorted by id). It is not part of index.json.
 7 COMPLETENESS. (SKEL-USES: a missing, odd, mismatched or unlisted .ilean, all reported.) Every .lean file under src/New is a file line of CONTENTS and every file line exists: SKEL-UNLISTED / SKEL-MISSING (`<path>` as in CONTENTS,
   without `.lean`); a line of the section that does not parse, or a file whose folder is not its section's, is SKEL-LINE <n> (n is the line of CONTENTS.md).
   All of one kind are reported together.
 8 STRINGS. The strings file is read and checked as build_site does and overlaid; `_graph_files` checks the exact key set (27 keys: the kind words, the card words and the count words come from the overlay).
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


class IleanVersionError(SourceError):
    """An .ilean whose `version` is missing or not one of ILEAN_VERSIONS: `reason` is the value as JSON text, or `missing` (the caller names the file in `SKEL-ILEAN-VERSION`)."""


class NoteError(Exception):
    """A source file whose module note cannot be taken: `SKEL-NOTE <path> <reason>`."""

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


SOURCE_READ_LIMIT = 1048576   # the most bytes of a source file the tool reads (1 MiB)
SOURCE_PREFIX = "grh/src/"   # the path of src/ from the repository root; `source` of a note is this and the CONTENTS path and `.lean`
_IMPORT_LINE = re.compile(r"import\s+\S.*")
ILEAN_READ_LIMIT = 16 * 1024 * 1024   # the most bytes of an .ilean file the tool reads (16 MiB; the largest of the real source is 260 KB)
ILEAN_VERSIONS = (5,)   # the `version` of the .ilean files the tool takes (all 803 files of the compiled index of the real source carry 5); any other value, or none, is SKEL-ILEAN-VERSION
USES_FORMAT = 3   # the format of graph/uses.json
CONTENTS_READ_LIMIT = 4 * 1024 * 1024   # the most bytes of CONTENTS.md the tool reads (4 MiB)
INDEX_READ_LIMIT = 1048576   # the most bytes of INDEX.md the tool reads (1 MiB)
SPINE_FORMAT = 1   # the format of graph/spine.json
INDEX_SOURCE = "grh/INDEX.md"
EDGE_BASIS_VALUE = "names-written-in-source-from-compiled-index"   # what an edge is: a name written in the source of one file and declared in another (a lower bound); the words are in strings
EDGE_BASIS_WORDS = "key_lines_text"   # the key of `strings` that states it
SPINE_EDGE_BASIS = "reaches-through-any-chain-of-uses"   # what a spine link is: the upper result reaches the lower through any chain of uses of the declaration graph, then reduced
SPINE_EDGE_WORDS = "spine_lines_text"   # the key of `strings` that states it; never the index's key
CONSTANT_KEYWORDS = ("theorem", "lemma", "def", "abbrev", "structure", "class", "inductive", "instance", "axiom", "opaque", "example")   # the keyword a mention's kind is read as


PREFIX = "lean-"      # every id of this tool starts with it: its own namespace, apart from the ids of the repository's outline
ID_MAX = 64           # the longest id (the page's router refuses a longer target)
ID_KEEP = 57          # an id longer than ID_MAX keeps this many characters, then `-` and ID_HASH hex digits of the sha256 of the whole id
ID_HASH = 6
KINDS = ("part", "group", "file")   # a part is a `###` heading, a group a bold line, a file a file line
SYMBOLS = dict(bs.GRAPH_SYMBOLS, kinds={k: dict({"card_words": f"card_kind_{k}", "class": f"kind-{k}", "words": f"symbol_kind_{k}"},
                                                  **({"count_words": {"many": f"count_{k}_many", "one": f"count_{k}_one"}} if k != "part" else {})) for k in KINDS})   # this tool's table: its three kinds, today's states and proofs
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


def _comment_end(text, start):
    """The index just past the `-/` that closes the block comment whose three-character opener (`/-!` or `/--`) begins at `start` in `text`, the nesting of `/-` and `-/` counted;
    None when it never closes. The ONE counter: the module note and a doc comment both end where it says."""
    depth, i = 1, start + 3
    while i < len(text):
        if text.startswith("/-", i):
            depth += 1
            i += 2
        elif text.startswith("-/", i):
            depth -= 1
            i += 2
            if depth == 0:
                return i
        else:
            i += 1
    return None


def _module_note(raw):
    """The inner text of the FIRST `/-!` ... `-/` block of the source bytes `raw`, delimiters excluded, byte for byte (strict UTF-8, no newline change, no trimming), the
    nesting of `/-` and `-/` counted. Only blank lines and `import` lines may precede the block. Raises NoteError(reason): not-utf-8, no-note, text-before-note, unterminated."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise NoteError("not-utf-8")
    start = text.find("/-!")
    if start < 0:
        raise NoteError("no-note")
    before = text[:start].split("\n")
    if not all(ln.strip() == "" or _IMPORT_LINE.fullmatch(ln.strip()) for ln in before[:-1]) or before[-1].strip() != "":
        raise NoteError("text-before-note")
    end = _comment_end(text, start)
    if end is None:
        raise NoteError("unterminated")
    return text[start + 3:end - 2]


def _contained(root, path):
    """True when the REAL path of `path` (every component resolved, not only the last) is `root`'s real path or under it."""
    r, p = os.path.realpath(root), os.path.realpath(path)
    return p == r or p.startswith(r + os.sep)


def _read_in(root, path, limit):
    """`_read_bounded` of a path whose real path must be under the real path of `root` (SourceError `outside` otherwise)."""
    if os.path.islink(path):
        raise SourceError("symlink")
    if not _contained(root, path):
        raise SourceError("outside")
    return _read_bounded(path, limit)


def _read_bounded(path, limit, guards=("lstat", "nofollow")):
    """The bytes of the regular file `path`, read through ONE descriptor that is opened without following a symlink and without blocking (so a FIFO does not hang the open),
    checked with fstat, and read at most `limit` + 1 bytes. Raises SourceError: missing, symlink, not-a-regular-file, too-large, unreadable. `guards` names the two checks against a
    symlink that are on (lstat before the open; O_NOFOLLOW in the open): the default is both, a case turns one off to see that each refuses by itself."""
    try:
        if "lstat" in guards and stat.S_ISLNK(os.lstat(path).st_mode):
            raise SourceError("symlink")
        fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK | (getattr(os, "O_NOFOLLOW", 0) if "nofollow" in guards else 0) | getattr(os, "O_CLOEXEC", 0))
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


def _check_ilean_version(obj):
    """Raises IleanVersionError unless the object of an .ilean has a `version` that is exactly one of ILEAN_VERSIONS. `type(v) is int` and not `isinstance(v, int)`: a bool is an int to
    isinstance (true == 1), and 5.0 == 5 in Python, so neither a bool nor a float is let through by equality; the value of a refusal is its JSON text (`true`, `5.0`, `"5"`, `null`)."""
    if "version" not in obj:
        raise IleanVersionError("missing")
    v = obj["version"]
    if type(v) is int and v in ILEAN_VERSIONS:
        return
    try:
        text = json.dumps(v, separators=(",", ":"))
    except (ValueError, RecursionError):
        text = "unprintable"
    raise IleanVersionError(text)


def _ilean_uses(raw, own_module, new_modules):
    """{module: number of distinct names used} from the bytes of an .ilean: a reference `{"c": {"m", "n"}}` with at least one usage counts for the module `m` when `m` is a module
    of `new_modules` other than `own_module`; the weight of a module is the number of distinct names `n`. Raises SourceError: not-json, bad-ilean, module-mismatch,
    unknown-reference-shape; IleanVersionError (a SourceError) when the object has a bad `version`, before any other fault of the file."""
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise SourceError("not-json")
    if isinstance(obj, dict):
        _check_ilean_version(obj)
    if not (isinstance(obj, dict) and isinstance(obj.get("module"), str) and isinstance(obj.get("references"), dict)):
        raise SourceError("bad-ilean")
    if obj["module"] != own_module:
        raise SourceError("module-mismatch")
    names = {}
    for key, val in obj["references"].items():
        try:
            ref = json.loads(key)
        except (ValueError, RecursionError):
            raise SourceError("unknown-reference-shape")
        if not isinstance(val, dict) or not isinstance(val.get("usages"), list):
            raise SourceError("bad-ilean")
        if isinstance(ref, dict) and set(ref) == {"f"}:   # a local variable: not a constant, never a use
            continue
        if not (isinstance(ref, dict) and set(ref) == {"c"} and isinstance(ref["c"], dict) and set(ref["c"]) == {"m", "n"}
                and isinstance(ref["c"]["m"], str) and isinstance(ref["c"]["n"], str)):
            raise SourceError("unknown-reference-shape")
        m = ref["c"]["m"]
        if val["usages"] and m in new_modules and m != own_module:
            names.setdefault(m, set()).add(ref["c"]["n"])
    return {m: len(v) for m, v in names.items()}


def _find_cycle(order, adj):
    """The first cycle of the graph {node: [successors]} as a list of nodes in the order of the cycle, searching in the order of `order` (and of each successor list); None when
    there is none."""
    state = {}
    for start in order:
        if state.get(start):
            continue
        stack, iters = [start], {start: iter(adj[start])}
        state[start] = 1
        while stack:
            node = stack[-1]
            for nxt in iters[node]:
                if state.get(nxt) == 1:
                    return stack[stack.index(nxt):]
                if not state.get(nxt):
                    state[nxt] = 1
                    stack.append(nxt)
                    iters[nxt] = iter(adj[nxt])
                    break
            else:
                state[node] = 2
                stack.pop()
    return None


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


def _src_escapes(grh):
    """[SKEL-ESCAPE errors] for `src` and `src/New` when either is a symlink, or when its REAL path is not under the real path of `grh`: nothing is walked through a symlinked top."""
    out = []
    for rel in ("src", "src/New"):
        path = os.path.join(grh, *rel.split("/"))
        if os.path.islink(path):
            out.append(("SKEL-ESCAPE", rel, "symlink"))
        elif os.path.exists(path) and not _contained(grh, path):
            out.append(("SKEL-ESCAPE", rel, "outside"))
        if out:
            break   # the folder below a refused top is not looked at
    return out


def _ilean_escapes(ilean_dir):
    """[SKEL-ESCAPE errors] for every folder below `ilean_dir` that is a symlink: it is named and never walked. That covers `ilean/New`, the tree the uses links are read from (a symlinked `ilean/New`
    is named `ilean/New` and not walked; so is any symlinked folder below it), as `_src_escapes` covers `src` and `src/New` for the source.
    `ilean_dir` itself and the files are not looked at here: a file that is a symlink is refused by the bounded reader."""
    out = []
    for r, ds, fs in os.walk(ilean_dir):
        out += [("SKEL-ESCAPE", "ilean/" + os.path.relpath(os.path.join(r, n), ilean_dir).replace(os.sep, "/"), "symlink") for n in sorted(ds) if os.path.islink(os.path.join(r, n))]
    return out


def _disk_paths(grh):
    """(the sorted paths of the .lean files under src/New, [SKEL-ESCAPE errors]): a folder under src/New that is a symlink is not walked and is named."""
    def fail(e):
        raise Unreadable(f"cannot read src/New: {e}")
    base = os.path.join(grh, "src")
    found, escapes = [], []
    for r, ds, fs in os.walk(os.path.join(base, "New"), onerror=fail):
        found += [os.path.relpath(os.path.join(r, n), base)[:-len(".lean")].replace(os.sep, "/") for n in fs + ds if n.endswith(".lean")]   # a directory named X.lean is listed too: it is refused as not a regular file
        escapes += [("SKEL-ESCAPE", "src/" + os.path.relpath(os.path.join(r, n), base).replace(os.sep, "/"), "symlink") for n in ds if os.path.islink(os.path.join(r, n))]
    return sorted(found), escapes


def _read_contents(grh):
    """(the text of CONTENTS.md, []) or (None, [SKEL-CONTENTS error]): read through the bounded reader, under the real path of `grh`. A missing file is Unreadable (exit 2)."""
    try:
        raw = _read_in(grh, os.path.join(grh, "CONTENTS.md"), CONTENTS_READ_LIMIT)
        return raw.decode("utf-8"), []
    except SourceError as e:
        if e.reason == "missing":
            raise Unreadable("cannot read CONTENTS.md: missing")
        return None, [("SKEL-CONTENTS", "CONTENTS.md", e.reason)]
    except UnicodeDecodeError:
        return None, [("SKEL-CONTENTS", "CONTENTS.md", "not-utf-8")]


def _index_cells(line):
    """The cells of a table row: split on `|` that is not escaped, the one space of padding of each cell removed, nothing else (the text is kept byte for byte)."""
    inner = line.strip()
    inner = inner[1:-1] if inner.endswith("|") else inner[1:]
    return [c[1:] if c.startswith(" ") else c for c in (x[:-1] if x.endswith(" ") else x for x in re.split(r"(?<!\\)\|", inner))]


def _index_table(lines, heading, ncells):
    """([(line number, cells)], [SKEL-INDEX errors]) for the table under `heading` (the header row and the separator are skipped); a row with another number of cells is
    `SKEL-INDEX <line>`. Raises Unreadable when the heading is not there."""
    if heading not in [ln.rstrip() for ln in lines]:
        raise Unreadable(f"INDEX.md has no `{heading}` section")
    i = [ln.rstrip() for ln in lines].index(heading) + 1
    while i < len(lines) and not lines[i].startswith("|"):
        i += 1
    rows, errors = [], []
    j = i
    while j < len(lines) and lines[j].startswith("|"):
        if j >= i + 2:
            cells = _index_cells(lines[j])
            (rows if len(cells) == ncells else errors).append((j + 1, cells) if len(cells) == ncells else ("SKEL-INDEX", str(j + 1), ""))
        elif j == i and len(_index_cells(lines[j])) != ncells:
            errors.append(("SKEL-INDEX", str(j + 1), ""))
        j += 1
    return rows, errors


def _load_json_in(root, path, limit):
    """The parsed JSON of an .ilean file read through the contained, bounded reader; raises SourceError (the reader's reasons, `not-json`) and IleanVersionError (an object with a bad `version`)."""
    raw = _read_in(root, path, limit)
    try:
        obj = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise SourceError("not-json")
    if isinstance(obj, dict):
        _check_ilean_version(obj)
    return obj


def _ilean_index(ilean_dir, row_constants):
    """(errors, where, uses_of, first_pos) from every .ilean under `ilean_dir`: where {declared name: (module, range entry)}, uses_of {enclosing declaration: {names it uses}} (a usage
    record with a 5th element that is not the name itself) and first_pos {(enclosing, name): the smallest (line, col)} for the enclosing declarations in `row_constants`."""
    errors, where, uses_of, first_pos = [], {}, {}, {}
    paths = []
    for r, ds, fs in os.walk(ilean_dir):
        ds.sort()
        paths += [os.path.join(r, n) for n in sorted(fs) if n.endswith(".ilean")]
    for path in sorted(paths):
        rel = os.path.relpath(path, ilean_dir)[:-len(".ilean")].replace(os.sep, "/")
        try:
            obj = _load_json_in(ilean_dir, path, ILEAN_READ_LIMIT)
        except IleanVersionError as e:
            errors.append(("SKEL-ILEAN-VERSION", rel + ".ilean", e.reason))
            continue
        except SourceError as e:
            errors.append(("SKEL-USES", rel, e.reason))
            continue
        if not (isinstance(obj, dict) and isinstance(obj.get("module"), str) and isinstance(obj.get("decls"), dict) and isinstance(obj.get("references"), dict)):
            errors.append(("SKEL-USES", rel, "bad-ilean"))
            continue
        for n, pos in obj["decls"].items():
            where.setdefault(n, (obj["module"], pos))
        for key, val in obj["references"].items():
            try:
                ref = json.loads(key)
            except (ValueError, RecursionError):
                continue
            c = ref.get("c") if isinstance(ref, dict) else None
            if not (isinstance(c, dict) and isinstance(c.get("n"), str)) or not isinstance(val, dict):
                continue
            for u in val.get("usages") or []:
                if isinstance(u, list) and len(u) > 4 and isinstance(u[4], str) and u[4] and u[4] != c["n"]:
                    uses_of.setdefault(u[4], set()).add(c["n"])
                    if u[4] in row_constants:
                        k = (u[4], c["n"])
                        if all(isinstance(x, int) and not isinstance(x, bool) for x in u[:2]):   # a record without a usable position gives no first use (a mention that has none is refused)
                            first_pos[k] = min(first_pos.get(k, (u[0], u[1])), (u[0], u[1]))
    return errors, where, uses_of, first_pos


def _reach(starts, uses_of):
    """The set of names reachable from `starts` along `uses_of` by any chain (iterative)."""
    seen, stack = set(), list(starts)
    while stack:
        x = stack.pop()
        for y in uses_of.get(x, ()):
            if y not in seen:
                seen.add(y)
                stack.append(y)
    return seen


def _kind_and_doc(lines, pos):
    """(kind or None, doc dict or None) of a declaration from the lines of its source and its range entry [start line, col, end line, col, name line, col, ...] (0-based lines).
    The doc comment runs to the `-/` that closes it, nesting counted by `_comment_end` (so an inner `/- ... -/` stays inside it); raises ValueError("unterminated doc comment") when it
    never closes."""
    sl, sc, nl, nc = pos[0], pos[1], pos[4], pos[5]
    line = lines[nl] if nl < len(lines) else ""
    before = re.sub(r"@\[[^\]]*\]", " ", line[:nc])
    kind = next((w for w in reversed(re.findall(r"[A-Za-z_]+", before)) if w in CONSTANT_KEYWORDS), None)
    doc = None
    if sl < nl and sl < len(lines) and lines[sl][sc:].startswith("/--"):
        txt = "\n".join([lines[sl][sc:]] + lines[sl + 1:nl])
        end = _comment_end(txt, 0)
        if end is None:
            raise ValueError("unterminated doc comment")
        doc = {"line": sl + 1, "text": txt[:end]}
    return kind, doc


def _group_report(gid, members, adj, kept):
    """The numbers of one group for the report: files, use edges, reduction edges, files that are an end of a drawn link, files with none, the longest path of `rests_on` and the
    depth row with most files (depth 0 = a file that rests on nothing; the smallest depth wins a tie). `adj` is the group's use relation, `kept` its transitive reduction."""
    ends = {p for p in members if adj[p]} | {q for p in members for q in adj[p]}
    depth = _depths(adj)
    per = {}
    for v in (depth or {}).values():
        per[v] = per.get(v, 0) + 1
    wide = min((k for k in per if per[k] == max(per.values())), default=0)
    return {"group": gid, "files": len(members), "uses": sum(len(v) for v in adj.values()), "reduction": sum(len(v) for v in kept.values()), "linked": len(ends), "unlinked": len(members) - len(ends),
            "longest": max((depth or {}).values(), default=0), "widest_depth": wide, "widest_count": per.get(wide, 0)}


def _report(rows, drawn, total, reduction, groups, cut, uses, imports, link_info):
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
            "depth": depth_max, "drawn": drawn, "not_drawn": total - drawn, "reduction": reduction, "uses_total": total, "groups": groups, "cut": cut,
            "kinds": {k: sum(1 for r in rows if r["kind"] == k) for k in KINDS}, "uses": uses, "imports": imports, "link_info": link_info}


def _spine_and_index(grh, ilean_dir, fid, rows, report):
    """Adds to `report`: spine {nodes, links}, step_extra {file step id: {index_rows, spine_rows}}, index {carried, lib_rows, lib_files}, lib_index_rows, titles, used_by. Returns
    the errors (SKEL-INDEX, SKEL-SPINE, SKEL-SPINE-CYCLE, SKEL-KIND, SKEL-USES) instead, all of one stage together."""
    try:
        raw = _read_in(grh, os.path.join(grh, "INDEX.md"), INDEX_READ_LIMIT)
        text = raw.decode("utf-8")
    except SourceError as e:
        return [("SKEL-INDEX", "INDEX.md", e.reason)]
    except UnicodeDecodeError:
        return [("SKEL-INDEX", "INDEX.md", "not-utf-8")]
    lines = text.split("\n")
    spine_rows, e1 = _index_table(lines, "## The last step", 3)
    step_rows, e2 = _index_table(lines, "## Steps of the argument", 4)
    errors = e1 + e2
    cell_path = lambda cell: (re.findall(r"`([^`]+)`", cell) or [None])[0]
    step_extra, lib_rows, carried = {}, [], 0
    for ln, cells in step_rows:
        path = cell_path(cells[1])
        if path in fid:
            step_extra.setdefault(fid[path], {"index_rows": []})["index_rows"].append({"source": INDEX_SOURCE, "text": cells[0]})
            carried += 1
        elif path is not None and path.startswith("Lib/"):
            lib_rows.append({"file": path, "source": INDEX_SOURCE, "text": cells[0]})
        else:
            errors.append(("SKEL-INDEX", str(ln), f"{path} is not a step" if path else "no file"))
    nodes, consts = [], {}
    for number, (ln, cells) in enumerate(spine_rows, 1):
        path = cell_path(cells[1])
        if path not in fid:
            errors.append(("SKEL-INDEX", str(ln), f"{path} is not a step" if path else "no file"))
            continue
        try:
            obj = _load_json_in(ilean_dir, os.path.join(ilean_dir, *path.split("/")) + ".ilean", ILEAN_READ_LIMIT)
            decls = obj["decls"]
        except IleanVersionError as e:
            if ("SKEL-ILEAN-VERSION", path + ".ilean", e.reason) not in errors:   # two rows may name one file: it is reported once
                errors.append(("SKEL-ILEAN-VERSION", path + ".ilean", e.reason))
            continue
        except (SourceError, KeyError, TypeError):
            errors.append(("SKEL-USES", path, "bad-ilean"))
            continue
        names, resolved = re.findall(r"`([^`]+)`", cells[0]), []
        for name in names:
            cand = sorted({n for n in decls if n in (name, "New." + name, "New." + (("Data." + name[2:]) if name.startswith("D.") else name))})
            if len(cand) != 1:
                errors.append(("SKEL-SPINE", f"{number} {name}", "unresolved" if not cand else "ambiguous"))
            else:
                resolved.append(cand[0])
        if names and len(resolved) == len(names):
            nid = _cap("spine-" + slug(names[0]))
            nodes.append({"content": cells[2], "constants": resolved, "file": fid[path], "id": nid, "names": names, "source": INDEX_SOURCE, "theorem": cells[0]})
            for c in resolved:
                consts[c] = nid
        elif not names:
            errors.append(("SKEL-SPINE", f"{number}", "no name"))
    if errors:
        return sorted(errors, key=lambda e: (e[0] != "SKEL-INDEX", int(e[1]) if e[0] == "SKEL-INDEX" else 0, e[1]))
    ie, where, uses_of, first_pos = _ilean_index(ilean_dir, set(consts))
    if ie:
        return ie
    # the links: row A rests on row B when a constant of A reaches a constant of B by any chain
    rests = {}
    for k, n in enumerate(nodes):
        reach = _reach(n["constants"], uses_of)
        rests[k] = [j for j, m in enumerate(nodes) if j != k and reach & set(m["constants"])]
    cycles = [(k, j) for k in rests for j in rests[k] if k in rests[j] and k < j]
    if cycles:
        return [("SKEL-SPINE-CYCLE", nodes[k]["id"] + " " + nodes[j]["id"], "") for k, j in cycles]
    kept = _reduce(rests)
    links = [{"from": nodes[k]["id"], "in_reduction": j in kept[k], "to": nodes[j]["id"]} for k in sorted(rests) for j in rests[k]]
    # the direct mentions of each row
    src_cache, kind_errors = {}, []

    def lines_of(module):
        if module not in src_cache:
            try:
                src_cache[module] = _read_in(grh, os.path.join(grh, "src", *module.split(".")) + ".lean", SOURCE_READ_LIMIT).decode("utf-8").split("\n")
            except SourceError as e:
                src_cache[module] = e.reason
            except UnicodeDecodeError:
                src_cache[module] = "not-utf-8"
        return src_cache[module]
    path_to_fid = {p.replace("/", "."): i for p, i in ((q, fid[q]) for q in fid)}
    for number, n in enumerate(nodes, 1):
        best, no_pos = {}, set()
        for i, e in enumerate(n["constants"]):
            for c in uses_of.get(e, ()):
                if c in where and c not in n["constants"]:
                    if (e, c) not in first_pos:
                        no_pos.add(c)
                        continue
                    key = (i, first_pos[(e, c)])
                    if c not in best or key < best[c]:
                        best[c] = key
        kind_errors.extend(("SKEL-MENTION", f"{number} {c}", "no usage position") for c in sorted(no_pos - set(best)))
        others = {c for e in n["constants"] for c in uses_of.get(e, ()) if c not in where and c not in n["constants"]}
        mentions = []
        for c, (i, pos) in sorted(best.items(), key=lambda kv: (kv[1], kv[0])):
            module, entry = where[c]
            src = lines_of(module)
            if isinstance(src, str):
                kind_errors.append(("SKEL-KIND", c, src))
                continue
            try:
                kind, doc = _kind_and_doc(src, entry)
            except ValueError as e:
                kind_errors.append(("SKEL-KIND", c, str(e)))
                continue
            if kind is None:
                kind_errors.append(("SKEL-KIND", c, ""))
                continue
            rel = "grh/src/" + module.replace(".", "/") + ".lean"
            m = {"constant": c, "file_path": rel, "first_use": [pos[0] + 1, pos[1]], "kind": kind, "line": entry[4] + 1, "module": module}
            if doc is not None:
                m["doc"] = dict(doc, source=rel)
            if module in path_to_fid:
                m["file"] = path_to_fid[module]
            if c in consts:
                m["spine"] = consts[c]
            mentions.append(m)
        n["mentions"] = mentions
        n["counts"] = {"mentions": len(mentions), "no_doc": sum(1 for m in mentions if "doc" not in m), "other_constants": len(others)}
    if kind_errors:
        return kind_errors
    for n in nodes:
        step_extra.setdefault(n["file"], {})
    for n in nodes:
        step_extra[n["file"]].setdefault("spine_rows", []).append(n["id"])
    uses = report["uses"]
    used_by = {i: [] for i in uses}
    for f in sorted(uses):
        for e in uses[f]:
            used_by[e["id"]].append({"id": f, "names": e["names"], "same_group": e["same_group"]})
    parent = {r["id"]: r["parent"] for r in rows}

    def path_of(i):
        out, x = [], parent[i]
        while x != "root":
            out.append(x)
            x = parent[x]
        return out[::-1]
    report["spine"] = {"nodes": nodes, "links": links}
    report["step_extra"] = step_extra
    report["index"] = {"carried": carried, "lib_rows": len(lib_rows), "lib_files": list(dict.fromkeys(r["file"] for r in lib_rows))}
    report["lib_index_rows"] = lib_rows
    report["used_by"] = used_by
    report["titles"] = {r["id"]: {"kind": r["kind"], "path": path_of(r["id"]), "title": r["title"]} for r in rows}
    return []


def _spine_basis_errors(spine, strings):
    """[(code, key, reason)] for the `edge_basis` of a spine object: exactly the keys basis and words (SKEL-SPINE-BASIS), the basis not the index's, the words key not the index's
    (SKEL-SPINE-BASIS), and the words key a key of `strings` (GRAPH-STRINGS <key> missing). A spine without `edge_basis` has nothing to check."""
    eb = spine.get("edge_basis")
    if eb is None:
        return []
    if not isinstance(eb, dict) or set(eb) != {"basis", "words"} or not isinstance(eb["words"], str):
        return [("SKEL-SPINE-BASIS", "edge_basis", "must have exactly the keys basis and words")]
    if eb["words"] == EDGE_BASIS_WORDS:
        return [("SKEL-SPINE-BASIS", eb["words"], "is the index's words key")]
    if eb["basis"] == EDGE_BASIS_VALUE:
        return [("SKEL-SPINE-BASIS", eb["words"], "has the index's basis")]
    if eb["words"] not in strings:
        return [("GRAPH-STRINGS", eb["words"], "missing")]
    return []


def build_rows(grh, ilean_dir, source_prefix=SOURCE_PREFIX):
    """(errors, rows, report) from the folder `grh` and the folder of the .ilean files: SKEL-LINE, then SKEL-MISSING and SKEL-UNLISTED, then SKEL-NOTE (every source file with no
    usable note or that cannot be read, all reported), then SKEL-USES, then SKEL-USES-CYCLE,
    each stops the run before the next stage."""
    errors = _src_escapes(grh)
    if errors:
        return errors, [], {}
    text, errors = _read_contents(grh)
    if errors:
        return errors, [], {}
    sections, errors = parse_contents(text)
    if errors:
        return errors, [], {}
    listed = [f["path"] for s in sections for g in s["groups"] for f in g["files"]]
    disk, escapes = _disk_paths(grh)
    if escapes:
        return escapes, [], {}
    errors = [("SKEL-MISSING", p, "") for p in listed if p not in set(disk)] + [("SKEL-UNLISTED", p, "") for p in disk if p not in set(listed)]
    if errors:
        return errors, [], {}
    src, note_text = {}, {}
    for p in listed:
        try:
            raw = _read_in(grh, os.path.join(grh, "src", *p.split("/")) + ".lean", SOURCE_READ_LIMIT)
            note_text[p] = _module_note(raw)
            src[p] = raw.decode("utf-8")
        except (SourceError, NoteError) as e:
            errors.append(("SKEL-NOTE", p, e.reason))

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
    errors = _ilean_escapes(ilean_dir)
    if errors:
        return errors, [], {}
    module = {p: p.replace("/", ".") for p in listed}
    file_of = {m: p for p, m in module.items()}
    weight = {}   # file path -> {used file path: weight}
    bad_versions = []
    for p in listed:
        try:
            raw = _read_in(ilean_dir, os.path.join(ilean_dir, *p.split("/")) + ".ilean", ILEAN_READ_LIMIT)
            weight[p] = {file_of[m]: w for m, w in _ilean_uses(raw, module[p], set(file_of)).items()}
        except IleanVersionError as e:
            bad_versions.append(("SKEL-ILEAN-VERSION", p + ".ilean", e.reason))
        except SourceError as e:
            errors.append(("SKEL-USES", p, "missing-ilean" if e.reason == "missing" else e.reason))
    errors += sorted(bad_versions)   # the files with a bad version, sorted by path, after the other faults of the stage
    for r, _, fs in os.walk(os.path.join(ilean_dir, "New")):
        for n in fs:
            if n.endswith(".ilean"):
                q = os.path.relpath(os.path.join(r, n), ilean_dir)[:-len(".ilean")].replace(os.sep, "/")
                if q not in module:
                    errors.append(("SKEL-USES", q, "no-contents-line"))
    errors[:] = errors[:len(errors) - sum(1 for e in errors if e[2] == "no-contents-line")] + sorted(e for e in errors if e[2] == "no-contents-line")
    if errors:
        return errors, [], {}
    order = {p: i for i, p in enumerate(listed)}
    cycle = _find_cycle(listed, {p: sorted(weight[p], key=order.get) for p in listed})
    if cycle:
        return [("SKEL-USES-CYCLE", " ".join(fid[p] for p in cycle), "")], [], {}
    where = {}   # file path -> (section, group) it belongs to
    for si, s in enumerate(sections):
        for gi, g in enumerate(s["groups"]):
            for f in g["files"]:
                where[f["path"]] = (si, gi)
    drawn = total = reduction = 0
    premises, uses, imports, groups, link_info = {}, {}, {}, [], {}
    group_files = {}
    for p in listed:
        uses[fid[p]] = [{"id": fid[q], "names": weight[p][q], "same_group": where[q] == where[p]} for q in sorted(weight[p], key=lambda q: fid[q])]
        imports[fid[p]] = sorted({fid[file_of[m]] for m in _imports(src[p]) if m in file_of and m != module[p]})
        total += len(weight[p])
    for si, s in enumerate(sections):
        for gi, g in enumerate(s["groups"]):
            members = [f["path"] for f in g["files"]]
            adj = {p: sorted((q for q in weight[p] if where[q] == (si, gi)), key=members.index) for p in members}
            kept = _reduce(adj)
            drawn += sum(len(v) for v in adj.values())
            reduction += sum(len(v) for v in kept.values())
            premises.update({p: [fid[q] for q in v] for p, v in adj.items()})
            link_info.update({(fid[p], fid[q]): {"weight": weight[p][q], "in_reduction": q in kept[p]} for p in members for q in adj[p]})
            group_files[(si, gi)] = (members, adj, kept)
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
            members, adj, kept = group_files[(ti, gi)]
            for fi, f in enumerate(g["files"]):
                row(fid[f["path"]], gid, fi, premises[f["path"]], "file", f["title"])
            groups.append(_group_report(gid, members, adj, kept))
    report = _report(rows, drawn, total, reduction, groups, cut, uses, imports, link_info)
    report["notes"] = {fid[p]: {"review": {"state": "converter"}, "source": source_prefix + p + ".lean", "text": note_text[p]} for p in listed}
    errors = _spine_and_index(grh, ilean_dir, fid, rows, report)
    if errors:
        return errors, [], {}
    return [], rows, report


def _readme_quote(grh):
    """([(SKEL-README, what, reason)], quote): the quote of the repository's own words for key_scope_text: line 15 of grh/README.md minus its closing colon, read through the bounded,
    contained reader. Refused: the README missing, a symlink, unreadable, too large, not UTF-8, with no line 15, or a line 15 that does not end with a colon."""
    try:
        raw = _read_in(grh, os.path.join(grh, "README.md"), SOURCE_READ_LIMIT)
        text = raw.decode("utf-8")
    except SourceError as e:
        return [("SKEL-README", "README.md", e.reason)], ""
    except UnicodeDecodeError:
        return [("SKEL-README", "README.md", "not-utf-8")], ""
    lines = text.split("\n")
    if text.endswith("\n"):
        lines.pop()
    if len(lines) < 15:
        return [("SKEL-README", "README.md", "has no line 15")], ""
    if not lines[14].endswith(":"):
        return [("SKEL-README", "README.md", "line 15 does not end with a colon")], ""
    return [], lines[14][:-1]


def build(grh, pin, strings, live_ids=(), ilean_dir=None, source_prefix=SOURCE_PREFIX, open_scale_floor=None):
    """(errors, {relative name: bytes}, rows, report): the files only when there are no errors. `live_ids` are the ids of the repository's outline; `ilean_dir` (required) is
    the folder of the .ilean files of the build."""
    if ilean_dir is None:
        raise TypeError("ilean_dir is required")
    if open_scale_floor is not None:
        errors = bs._scale_floor_error(open_scale_floor)
        if errors:
            return errors, {}, [], {}
    errors, rows, rep = build_rows(grh, ilean_dir, source_prefix)
    if errors:
        return errors, {}, rows, rep
    step_ids, spine_ids = {r["id"] for r in rows}, [n["id"] for n in rep["spine"]["nodes"]]
    clash = (step_ids & set(live_ids)) | {i for i in spine_ids if i in step_ids or i in set(live_ids) or spine_ids.count(i) > 1}
    errors = [("SKEL-ID-CLASH", i, "") for i in sorted(clash)]
    if errors:
        return errors, {}, rows, rep
    missing = bs._graph_strings_errors({k: strings[k] for k in bs._graph_strings_keys(SYMBOLS) if k in strings}, SYMBOLS)   # only the missing ones: it holds a subset
    if missing:
        return missing, {}, rows, rep
    if "key_scope_text" in strings:   # the builder quotes the repository's words from its README, never from a typed copy
        value = strings["key_scope_text"]
        if value.count("{readme_quote}") != 1:
            return [("SKEL-README", "key_scope_text", "has no {readme_quote}" if "{readme_quote}" not in value else "has {readme_quote} twice")], {}, rows, rep
        errors, quote = _readme_quote(grh)
        if errors:
            return errors, {}, rows, rep
        filled = value.replace("{readme_quote}", quote)
        others = {n for names in bs.PLACEHOLDERS.values() for n in names} - {"readme_quote"}   # every name the format declares for another key
        found = sorted(set(bs._PLACEHOLDER.findall(filled)) & others)
        if found:   # the written value holds none: the quote (or the template) must not bring a placeholder of another key into it
            return [("SKEL-README", "key_scope_text", "placeholder " + n) for n in found], {}, rows, rep
        strings = dict(strings, key_scope_text=filled)
    errors, objs = bs._graph_files(rows, pin, strings, symbols=SYMBOLS, orders=MAP_ORDERS, layout="column", link_info=rep["link_info"], notes=rep["notes"], child_kinds=True,
                                    step_extra=rep["step_extra"], index_extra=dict(({"edge_basis": {"basis": EDGE_BASIS_VALUE, "words": EDGE_BASIS_WORDS}} if EDGE_BASIS_WORDS in strings else {}),
                                                     **({"open_scale_floor": open_scale_floor} if open_scale_floor is not None else {})) or None)
    if errors:
        return errors, {}, rows, rep
    objs["graph/uses.json"] = {"commit": pin, "format": USES_FORMAT, "imports": rep["imports"], "lib_index_rows": rep["lib_index_rows"], "titles": rep["titles"], "used_by": rep["used_by"],
                               "uses": rep["uses"]}
    objs["graph/spine.json"] = {"commit": pin, "format": SPINE_FORMAT, "links": rep["spine"]["links"], "nodes": rep["spine"]["nodes"]}
    if SPINE_EDGE_WORDS in strings:
        objs["graph/spine.json"]["edge_basis"] = {"basis": SPINE_EDGE_BASIS, "words": SPINE_EDGE_WORDS}
    errors = _spine_basis_errors(objs["graph/spine.json"], strings)
    if errors:
        return errors, {}, rows, rep
    return [], bs._graph_bytes(objs), rows, rep


USAGE = ("usage: build_grh_skeleton.py --grh DIR --pin COMMIT --strings strings.json --out OUT_DIR --ilean-dir DIR [--outline outline.json] [--strings-overlay overlay.json] [--strings-overlay-graph overlay.json] [--source-prefix PREFIX] [--open-scale-floor N]\n"
         "       build_grh_skeleton.py --selftest [--only ID,ID] [--grh DIR]")


def _parse(a):
    """{grh, pin, strings, out[, outline][, strings-overlay][, strings-overlay-graph]} or None: each option once, with a value; --pin not empty; nothing else."""
    opts, i = {}, 0
    while i < len(a):
        if a[i] in ("--grh", "--pin", "--strings", "--out", "--outline", "--strings-overlay", "--strings-overlay-graph", "--ilean-dir", "--source-prefix", "--open-scale-floor") and a[i][2:] not in opts and i + 1 < len(a):
            opts[a[i][2:]] = a[i + 1]
            i += 2
        else:
            return None
    return opts if {"grh", "pin", "strings", "out", "ilean-dir"} <= set(opts) and opts["pin"] else None


def report_lines(rep):
    cuts = [f"cut id {full} -> {final}" for full, final in rep["cut"]]
    table = [f"group {g['group']}: files {g['files']}, use edges {g['uses']}, reduction edges {g['reduction']}, linked {g['linked']}, unlinked {g['unlinked']}, longest {g['longest']}, "
             f"widest row depth {g['widest_depth']} ({g['widest_count']} files)" for g in rep["groups"]]
    return ([f"steps: {rep['steps']}", "kinds: " + ", ".join(f"{k} {rep['kinds'][k]}" for k in KINDS), "top: " + ", ".join(rep["top"]), f"widest: {rep['widest']}", f"depth: {rep['depth']}",
             f"uses: {rep['uses_total']}", f"links drawn (uses inside a group): {rep['drawn']}", f"uses not drawn (across groups): {rep['not_drawn']}",
             f"links in the transitive reduction: {rep['reduction']}",
             f"ids cut: {len(cuts)}"] + cuts + table)


def _run(opts):
    if not os.path.isdir(opts["grh"]):
        raise Unreadable(f"--grh is not a directory: {opts['grh']}")
    if not os.path.isdir(opts["ilean-dir"]):
        raise Unreadable(f"--ilean-dir is not a directory: {opts['ilean-dir']}")
    if os.path.exists(opts["out"]) and not os.path.isdir(opts["out"]):
        raise Unreadable(f"OUT_DIR is not a directory: {opts['out']}")
    try:
        strings = bs._read_json(opts["strings"], "strings file")
        outline = bs._read_json(opts.get("outline", OUTLINE), "outline")
        overlay = bs._read_json(opts.get("strings-overlay", OVERLAY), "strings overlay")
        graph = bs._read_json(opts["strings-overlay-graph"], "Graph strings overlay") if "strings-overlay-graph" in opts else {}   # no default: absent is a Cards-only build
    except bs._Unreadable as e:
        raise Unreadable(str(e))
    if not (isinstance(overlay, dict) and isinstance(graph, dict) and isinstance(strings, dict)):
        raise Unreadable("cannot read the strings overlay: it, the Graph overlay and the strings file must be JSON objects")
    strings = dict(strings, **overlay)   # the overlay's keys replace or add to the strings file, for this map only (no file is edited)
    if not (isinstance(outline, dict) and isinstance(outline.get("groups"), list) and all(isinstance(g, dict) and isinstance(g.get("id"), str) for g in outline["groups"])):
        raise Unreadable("cannot read the outline: no `groups` list of objects with an `id`")

    def refuse(errors):
        for code, where, msg in errors:
            print(f"{code} {where}" + (f" {msg}" if msg else ""))
        print("REFUSED: nothing written", file=sys.stderr)
        return 1
    clash = sorted(set(graph) & set(strings))   # `strings` holds the strings file and the Cards overlay here: a key lives in one class
    if clash:
        return refuse([("SKEL-OVERLAY-CLASH", k, "") for k in clash])
    page_keys = set(bs._graph_strings_keys(SYMBOLS)) | set(bs.GRAPH_OPTIONAL_KEYS)   # what _graph_files copies into index.json `strings`: anything else of an overlay would be dropped without a word
    unknown = sorted((os.path.basename(opts.get(opt, OVERLAY) if opt == "strings-overlay" else opts.get(opt, "")), k) for opt, obj in (("strings-overlay", overlay), ("strings-overlay-graph", graph)) for k in obj if k not in page_keys)
    if unknown:
        return refuse([("SKEL-OVERLAY-KEY", f"{name} {k}", "is not a key the page reads") for name, k in unknown])
    strings.update(graph)
    if os.path.isdir(opts["out"]) and os.listdir(opts["out"]):
        return refuse([("OUT-NOT-EMPTY", "OUT_DIR", "already holds files")])
    problems = bs._strings_problems(strings)
    if problems:
        return refuse(problems)
    errors, files, rows, rep = build(opts["grh"], opts["pin"], strings, [g["id"] for g in outline["groups"]], opts["ilean-dir"], opts.get("source-prefix", SOURCE_PREFIX),
                                       bs._scale_from_text(opts["open-scale-floor"]) if "open-scale-floor" in opts else None)
    if errors:
        return refuse([(c, opts["open-scale-floor"], r) if c == "GRAPH-SCALE-FLOOR" else (c, k, r) for c, k, r in errors])   # the floor is named as it was typed (`1e400`, not `inf`)
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
_ILEAN_FOR_SK13 = None   # the folder given to `--selftest --ilean-dir`; SK13 reads it with the one above


def _eq(actual, expected):
    return actual == expected, f"expected {expected!r}, got {actual!r}"


PIN = "0123456789abcdef0123456789abcdef01234567"
HEAD = "# Contents\n\nIntro.\n\n## New\n\n"   # the body of a fixture CONTENTS starts on line 7
TAIL = "\n## Lib\n\n- `Lib/Other/File` (1): Not read\n"
KIND_ROWS = {"part": {"card_words": "card_kind_part", "class": "kind-part", "words": "symbol_kind_part"},
             "group": {"card_words": "card_kind_group", "class": "kind-group", "count_words": {"many": "count_group_many", "one": "count_group_one"}, "words": "symbol_kind_group"},
             "file": {"card_words": "card_kind_file", "class": "kind-file", "count_words": {"many": "count_file_many", "one": "count_file_one"}, "words": "symbol_kind_file"}}
COUNT_WORDS = {"count_group_one": "{n} group", "count_group_many": "{n} groups", "count_file_one": "{n} file", "count_file_many": "{n} files"}   # the foot words, final
ORDERS = {"kinds": ["part", "group", "file"], "states": [], "proofs": []}
OVERLAY_WORDS = {"key_kinds_heading": "What a box is", "symbol_kind_part": "Part of the argument", "symbol_kind_group": "Group of files",
                 "symbol_kind_file": "Lean file", "card_kind_part": "Part", "card_kind_group": "Group", "card_kind_file": "File"}
OPTIONAL_WORDS = {"key_kinds_note": "Parts and groups follow the repository's own contents list (CONTENTS.md); the titles of parts, groups and files are copied from it word for word.",
                  "note_label": "The file's opening note, from the repository, unchanged",
                  "note_source": "Opening note of {source} \u00b7 version {commit} of lsernau/grh-lean"}   # the three optional page-drawn words, final
NOTE_WORDS = {"note_label_typeset": "The file's opening note, from the repository", "note_typeset_line": "Formulas set in maths type by us; every symbol is the repository's.",
              "note_exact_button": "Show the exact text", "note_render_button": "Show in maths type"}   # the note words, final


def _lean(decl="theorem t : True := trivial", note="n", imports=()):
    """A source file: the imports, then a module note (every file must have one), then the declaration."""
    return "".join(f"import {m}\n" for m in imports) + f"/-!\n{note}\n-/\n" + decl + "\n"


def _tree(root, body, srcs, ileans=None, index="default"):
    """Write <root>/grh/CONTENTS.md (HEAD, body, TAIL) and one src/<path>.lean per entry of `srcs` (path as in CONTENTS, e.g. New/A/B); return <root>/grh."""
    g = os.path.join(root, "grh")
    os.makedirs(g)
    with open(os.path.join(g, "CONTENTS.md"), "w", encoding="utf-8") as f:
        f.write(HEAD + body + TAIL)
    with open(os.path.join(g, "README.md"), "w", encoding="utf-8") as f:   # the repository's README: line 15 is quoted by key_scope_text
        f.write("".join("line %d\n" % i for i in range(1, 15)) + "line 15 of the README:\n")
    if index is not None:
        with open(os.path.join(g, "INDEX.md"), "wb") as f:
            f.write(_index() .encode("utf-8") if index == "default" else (index if isinstance(index, bytes) else index.encode("utf-8")))
    for p, text in list(srcs.items()) + [("Lib/Other/File", _lean())]:
        fp = os.path.join(g, "src", *p.split("/")) + ".lean"
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "wb") as f:
            f.write(text if isinstance(text, bytes) else text.encode("utf-8"))
    # one .ilean per New file: from its import lines (each imported module is used once, by the name n1) unless `ileans` gives the object, a raw string, or None (no file)
    ileans = dict(ileans or {})
    for p, text in srcs.items():
        if p.startswith("New/") and p not in ileans:
            refs = {}
            for m in re.findall(r"^import[ \t]+(\S+)", text if isinstance(text, str) else text.decode("utf-8", "replace"), re.M):
                refs.update(_ref(m, "n1"))
            ileans[p] = _ilean(p, refs)
    for p, obj in ileans.items():
        if obj is None:
            continue
        fp = os.path.join(root, "ilean", *p.split("/")) + ".ilean"
        os.makedirs(os.path.dirname(fp), exist_ok=True)
        with open(fp, "w", encoding="utf-8") as f:
            f.write(obj if isinstance(obj, str) else json.dumps(obj))
    return g


def _strings(extra=True):
    """The strings file of this checkout; with `extra` (the default) the overlay words of this map are in it, as the literals of OVERLAY_WORDS."""
    with open(os.path.join(_HERE, os.pardir, "site", "strings.json"), encoding="utf-8") as f:
        s = json.load(f)
    if extra:
        s.update(OVERLAY_WORDS)
        s.update(COUNT_WORDS)
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


def _ildir(g):
    return os.path.join(os.path.dirname(g), "ilean")


def _args(g, out, strings_path, outline, pin=PIN, overlay=None, graph=None):
    return (["--grh", g, "--pin", pin, "--strings", strings_path, "--out", out, "--outline", outline, "--ilean-dir", _ildir(g)]
            + (["--strings-overlay", overlay] if overlay else []) + (["--strings-overlay-graph", graph] if graph else []))


def bld(g, pin, strings, live_ids=()):
    return build(g, pin, strings, live_ids, _ildir(g))


def brows(g):
    return build_rows(g, _ildir(g))


def _ref(module, *names, usages=1, definition=None):
    """The `references` entries of an .ilean for the names of one module: {key: {definition, usages}}; `usages` is the number of usage records of each."""
    return {json.dumps({"c": {"m": module, "n": n}}, separators=(",", ":")): {"definition": definition, "usages": [[1, 1, 1, 2, "x"]] * usages} for n in names}


def _ilean(path, refs, module=None, decls=()):
    return {"decls": {n: [3, 0, 3, 28, 3, 8, 3, 9] for n in decls}, "directImports": [], "module": module or path.replace("/", "."), "references": refs, "version": 5}


def _use(module, name, enclosing=None):
    """One reference of an .ilean: a use of `name` (declared in `module`) with one usage record, inside the declaration `enclosing` (none: a 4-element record)."""
    return {json.dumps({"c": {"m": module, "n": name}}, separators=(",", ":")): {"definition": None, "usages": [[1, 1, 1, 2] + ([enclosing] if enclosing else [])]}}


def _index(spine=(), steps=()):
    """An INDEX.md: the two tables, each row a ready line; row lines of the first table start on line 9, a table row of the second on line 14 + the rows before it."""
    return ("# Index\n\n## The last step\n\nNames omit `New.`.\n\n| theorem | file | content |\n|---|---|---|\n" + "".join(l + "\n" for l in spine)
            + "\n## Steps of the argument\n\n| result | file | further files | related work |\n|---|---|---|---|\n" + "".join(l + "\n" for l in steps) + "\n## Known results\n\nx\n")


def _srow(a, b, c):
    return f"| {a} | {b} | {c} |"


def _trow(a, b, c="", d=""):
    return f"| {a} | {b} | {c} | {d} |"


def _flat(names):
    return "### S part\n\n**G**\n\n" + "".join(f"- `New/S/{n}` (1): {n}\n" for n in names)


EDGE_BASIS = {"basis": "names-written-in-source-from-compiled-index", "words": "key_lines_text"}   # index.json edge_basis: a pointer, the sentence is in strings
SCOPE_FULL = "The map holds the 306 Lean files of the argument itself (the folder New). Two short files at the top of the repository are not on it. In the repository's words (grh/README.md): \"`src/Statements.lean` states the theorems in Mathlib's terms. `src/Main.lean` proves five theorems\", the Riemann Hypothesis among them, each in a line or two from results on this map or from one another. (The map's file named Main is New/Main.lean, a different file.) The map also leaves out the repository's own 495 library files (the folder Lib) and Mathlib. A file's uses of those are not drawn."   # key_scope_text as the page prints it
SCOPE_TEMPLATE = "The map holds the 306 Lean files of the argument itself (the folder New). Two short files at the top of the repository are not on it. In the repository's words (grh/README.md): \"{readme_quote}\", the Riemann Hypothesis among them, each in a line or two from results on this map or from one another. (The map's file named Main is New/Main.lean, a different file.) The map also leaves out the repository's own 495 library files (the folder Lib) and Mathlib. A file's uses of those are not drawn."   # the same, with `{readme_quote}` where the repository's README line 15 (minus its colon) is quoted by the builder
LINES_WORDS = {"key_lines_heading": "What a line is",
               "key_lines_text": "A line joins two files of the same group: the upper file uses definitions or results from the lower one. Where a path of lines already connects two files, no direct line is drawn between them. Uses across groups are not drawn. Lean also uses results it fills in on its own without naming them; those uses are not counted.",
               "spine_lines_text": "A line means the upper result rests on the lower one, directly or through steps not drawn here. Lean also uses results it fills in on its own without naming "
                                   "them; those are not counted, so a result can rest on more than its lines show. Every line drawn is real."}   # final


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
            "New/S/B": _lean(imports=["New.S.C", "New.S.D"]), "New/S/C": _lean(), "New/S/D": _lean()}
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
            errs, files, rows, rep = bld(g, PIN, _strings())
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
                        sorted(files) == ["graph/index.json", "graph/spine.json"] + steps + ["graph/uses.json"],
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
            errs, files, rows, rep = bld(g, PIN, _strings())
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

    @case("SK3", "premises and links are USES, from the .ilean: a uses b, c and d, b uses c and d, d is in another group: the group's rests_on has the three in-group uses a->b, "
                 "a->c, b->c (the data is NOT reduced), each with weight 1 and in_reduction (a->c is false, the others true); the uses of another group are not drawn "
                 "(drawn 3, not drawn 2, reduction 2, 5 uses in all); a longer chain (a->b->c->d with a->c and a->d) has 5 links and 3 in the reduction")
    def _():
        with _tmp() as d:
            errs, files, rows, rep = bld(_tree(d, SK3_BODY, SK3_SRCS), PIN, _strings())
            grp = _j(files, "graph/step/lean-s--grp.json")
        with _tmp() as d:
            cerrs, cfiles, crows, crep = bld(_tree(d, CHAIN_BODY, CHAIN_SRCS), PIN, _strings())
            cgrp = _j(cfiles, "graph/step/lean-t--grp.json")
        pth = ["lean-s", "lean-s--grp"]
        link = lambda f, to, w, r: {"from": f"lean-s-{f}", "from_path": pth, "in_reduction": r, "to": f"lean-s-{to}", "to_path": pth, "weight": w}
        return _eq((errs, [(r["id"], r["premises"]) for r in rows if r["parent"] == "lean-s--grp"], grp["rests_on"], grp["children"][0]["parent_rests_on"],
                    (rep["drawn"], rep["not_drawn"], rep["reduction"], rep["uses_total"]),
                    cerrs, [(r["id"], r["premises"]) for r in crows if r["parent"] == "lean-t--grp"], [(l["from"][-1], l["to"][-1], l["in_reduction"]) for l in cgrp["rests_on"]],
                    (crep["drawn"], crep["not_drawn"], crep["reduction"])),
                   ([], [("lean-s-a", ["lean-s-b", "lean-s-c"]), ("lean-s-b", ["lean-s-c"]), ("lean-s-c", [])],
                    [link("a", "b", 1, True), link("a", "c", 1, False), link("b", "c", 1, True)], False, (3, 2, 2, 5),
                    [], [("lean-t-a", ["lean-t-b", "lean-t-c", "lean-t-d"]), ("lean-t-b", ["lean-t-c"]), ("lean-t-c", ["lean-t-d"]), ("lean-t-d", [])],
                    [("a", "b", True), ("a", "c", False), ("a", "d", False), ("b", "c", True), ("c", "d", True)], (5, 0, 3)))

    @case("SK4", "a cycle among the uses of files is refused `SKEL-USES-CYCLE <ids of the cycle>` (the ids in the order of the cycle, from its first file in CONTENTS), "
                 "also with a chord and across groups; nothing is returned")
    def _():
        body = "### S part\n\n**Grp**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n"
        srcs = {"New/S/A": _lean(imports=["New.S.B"]), "New/S/B": _lean(imports=["New.S.A"])}
        three = body + "- `New/S/C` (1): c\n"
        tsrcs = {"New/S/A": _lean(imports=["New.S.B", "New.S.C"]), "New/S/B": _lean(imports=["New.S.C"]), "New/S/C": _lean(imports=["New.S.A"])}
        cross = "### S part\n\n**G1**\n\n- `New/S/A` (1): a\n\n**G2**\n\n- `New/S/B` (1): b\n"
        with _tmp() as d:
            errs, files, rows, rep = bld(_tree(d, body, srcs), PIN, _strings())
        with _tmp() as d:
            e3, f3, r3, rep3 = bld(_tree(d, three, tsrcs), PIN, _strings())
        with _tmp() as d:
            e4, f4, r4, rep4 = bld(_tree(d, cross, srcs), PIN, _strings())
            rc, out, err = _cli(_args(os.path.join(d, "grh"), os.path.join(d, "out"), _strings_file(d), _outline_file(d)))
        return _eq((errs, files, e3, f3, e4, rc, out.splitlines()),
                   ([("SKEL-USES-CYCLE", "lean-s-a lean-s-b", "")], {}, [("SKEL-USES-CYCLE", "lean-s-a lean-s-b lean-s-c", "")], {}, [("SKEL-USES-CYCLE", "lean-s-a lean-s-b", "")],
                    1, ["SKEL-USES-CYCLE lean-s-a lean-s-b"]))

    @case("SK5", "kinds are read off CONTENTS: `part` for each `###` heading, `group` for each bold line (an anonymous group too), `file` for each file line; the table of "
                 "this tool has exactly the rows part, group, file (classes kind-part|kind-group|kind-file, words symbol_kind_part|group|file) and the three rows of the "
                 "states and of the proofs; order lists kinds [part, group, file], states [], proofs []; state and proof are `none` on every card; index.json `strings` is "
                 "27 keys (the 23 and the four count words) with the overlay words and has no symbol_kind_module; index.json has sibling_layout column; site/strings.json has no symbol_kind_module")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n\n### T part\n\n- `New/T/C` (1): c\n"
        srcs = {"New/S/A": _lean("theorem x : True := trivial"), "New/S/B": _lean(""), "New/T/C": _lean("-- nothing here")}
        with _tmp() as d:
            errs, files, rows, rep = bld(_tree(d, body, srcs), PIN, _strings())
            ix = _j(files, "graph/index.json")
        return _eq((errs, [r["kind"] for r in rows], rep["kinds"], sorted({(r["state"], r["proof"]) for r in rows}), ix["symbols"]["order"],
                    {k: v for k, v in ix["symbols"]["kinds"].items()}, sorted(ix["symbols"]["states"]), sorted(ix["symbols"]["proofs"]), len(ix["strings"]),
                    ix["strings"]["key_kinds_heading"], "symbol_kind_module" in ix["strings"], ix["sibling_layout"], "symbol_kind_module" in _strings(extra=False),
                    sorted({c["state"] for k, v in files.items() if k.startswith("graph/step/") for c in [json.loads(v.decode("utf-8"))["card"]]})),
                   ([], ["part", "group", "file", "file", "part", "group", "file"], {"part": 2, "group": 2, "file": 3}, [("none", "none")], ORDERS,
                    {"part": {"card_words": "card_kind_part", "class": "kind-part", "text": "Part of the argument", "words": "symbol_kind_part"},
                     "group": {"card_words": "card_kind_group", "class": "kind-group", "count_words": {"many": "count_group_many", "one": "count_group_one"},
                               "text": "Group of files", "words": "symbol_kind_group"},
                     "file": {"card_words": "card_kind_file", "class": "kind-file", "count_words": {"many": "count_file_many", "one": "count_file_one"},
                              "text": "Lean file", "words": "symbol_kind_file"}},
                    ["census", "none", "read"], ["none", "not_read", "read"], 27, "What a box is", False, "column", False, ["none"]))

    @case("SK6", "uses sidecar (format 3): graph/uses.json is {commit: the pin, format: 3, imports: {file id: [ids of the New files it imports, sorted]}, lib_index_rows: [...], used_by: "
                 "{file id: [{id, names, same_group}, ...]}, uses: {file id: [{id, names, same_group}, ... sorted by id]}} with all of imports, used_by and uses for every FILE step (empty "
                 "lists allowed) and none for a section or a group; an import outside New is not in it; a use across groups is in `uses` with same_group false; used_by is the exact "
                 "inverse of uses; it is not in index.json `steps`")
    def _():
        with _tmp() as d:
            errs, files, rows, rep = bld(_tree(d, SK3_BODY, SK3_SRCS), PIN, _strings())
        u = _j(files, "graph/uses.json")
        e = lambda i, n, g: {"id": f"lean-s-{i}", "names": n, "same_group": g}
        return _eq((errs, u, files["graph/uses.json"].endswith(b"\n"), _j(files, "graph/index.json")["steps"]),
                   ([], {"commit": PIN, "format": 3, "lib_index_rows": [],
                         "titles": {"lean-s": {"kind": "part", "path": [], "title": "S part"}, "lean-s--grp": {"kind": "group", "path": ["lean-s"], "title": "Grp"},
                                    "lean-s--other": {"kind": "group", "path": ["lean-s"], "title": "Other"},
                                    "lean-s-a": {"kind": "file", "path": ["lean-s", "lean-s--grp"], "title": "a"}, "lean-s-b": {"kind": "file", "path": ["lean-s", "lean-s--grp"], "title": "b"},
                                    "lean-s-c": {"kind": "file", "path": ["lean-s", "lean-s--grp"], "title": "c"}, "lean-s-d": {"kind": "file", "path": ["lean-s", "lean-s--other"], "title": "d"}},
                         "imports": {"lean-s-a": ["lean-s-b", "lean-s-c", "lean-s-d"], "lean-s-b": ["lean-s-c", "lean-s-d"], "lean-s-c": [], "lean-s-d": []},
                         "used_by": {"lean-s-a": [], "lean-s-b": [e("a", 1, True)], "lean-s-c": [e("a", 1, True), e("b", 1, True)], "lean-s-d": [e("a", 1, False), e("b", 1, False)]},
                         "uses": {"lean-s-a": [e("b", 1, True), e("c", 1, True), e("d", 1, False)], "lean-s-b": [e("c", 1, True), e("d", 1, False)], "lean-s-c": [], "lean-s-d": []}},
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
            errs = brows(g)[0]
            sp = _strings_file(d)
            rc, out, err = _cli(_args(g, os.path.join(d, "out"), sp, _outline_file(d)))
            absent = not os.path.exists(os.path.join(d, "out"))
        lines = []
        for b in (bad, folders, flat):
            with _tmp() as d2:
                lines.append(brows(_tree(d2, b, {}))[0])
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
            e41, f41, r41, _r = bld(_tree(d, *fx(41)), PIN, _strings())
        with _tmp() as d:
            e40, f40, r40, _r = bld(_tree(d, *fx(40)), PIN, _strings())
        return _eq((e41, f41, e40, len(f40), _j(f40, "graph/index.json")["steps"]),
                   ([("GRAPH-FANOUT", "lean-w--g", "has 41 children (more than 40)")], {}, [], 45, 42))

    @case("SK9", "ids: slug folds accents to ASCII (NFKD), lower-cases and turns every run of other characters into one `-`; two groups of one section whose titles "
                 "give one slug are GRAPH-DUP; a folder name that cannot make an id (a dot) is GRAPH-ID (nothing is corrected); kebab: a lower-case letter before an "
                 "upper-case one gets `-`, `_` becomes `-`")
    def _():
        body = "### S part\n\n**Alpha, beta**\n\n- `New/S/A` (1): a\n\n**Alpha beta!**\n\n- `New/S/B` (1): b\n"
        dot = "### U part\n\n**G**\n\n- `New/Bad.Dir/X` (1): x\n"
        with _tmp() as d:
            edup = bld(_tree(d, body, {"New/S/A": _lean(), "New/S/B": _lean()}), PIN, _strings())[0]
        with _tmp() as d:
            eid = bld(_tree(d, dot, {"New/Bad.Dir/X": _lean()}), PIN, _strings())[0]
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
                   (0, 0, True, ["graph/index.json", "graph/spine.json", "graph/step/lean-s--g.json", "graph/step/lean-s-a.json", "graph/step/lean-s-b.json", "graph/step/lean-s.json",
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
            errs3 = bld(g, PIN, s3)[0]
            s4 = _strings()
            del s4["symbol_kind_file"]
            errs4 = bld(g, PIN, s4)[0]
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
        info = {("lean-s-b", "lean-s-a"): {"weight": 1, "in_reduction": True}}
        notes = {i: {"source": f"grh/src/New/S/{i[-1].upper()}.lean", "text": "\nn\n", "review": {"state": "converter"}} for i in ("lean-s-a", "lean-s-b")}
        want_errs, want_objs = bs._graph_files(rows, PIN, dict(_strings(), **OPTIONAL_WORDS, **LINES_WORDS, **NOTE_WORDS, key_scope_text=SCOPE_TEMPLATE.replace("{readme_quote}", "line 15 of the README")), symbols=table, orders=ORDERS, layout="column", link_info=info, notes=notes, child_kinds=True, index_extra={"edge_basis": EDGE_BASIS})
        want = bs._graph_bytes(want_objs)
        with _tmp() as d:
            g = _tree(d, body, srcs)
            sp = _strings_file(d)
            out = os.path.join(d, "out")
            rc = _cli(_args(g, out, sp, _outline_file(d), graph=os.path.join(_HERE, os.pardir, "site", "strings-lean-graph.json")))[0]   # the Graph words are in the wanted strings above
            got = _tree_files(out)
        uses = got.pop("graph/uses.json")
        got.pop("graph/spine.json")
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
            errs, files, rows, rep = bld(_tree(d, body, {"New/S/A": _lean(), "New/S/B": _lean(), "New/S/C": _lean()}), PIN, _strings())
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
            clash = bld(g, PIN, _strings(), live_ids=["zeta", "lean-s-a", "lean-s"])[0]
            fine = bld(g, PIN, _strings(), live_ids=["zeta", "lean-sa"])[0]
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
            errs, files, rows, rep = bld(_tree(d, body, srcs), PIN, _strings())
        kids = lambda i: [c["id"] for c in _j(files, f"graph/step/{i}.json")["children"]]
        return _eq((errs, _j(files, "graph/index.json")["top"], kids("lean-zeta"), kids("lean-zeta--zed-group"), [r["order"] for r in rows]),
                   ([], ["lean-zeta", "lean-alpha"], ["lean-zeta--zed-group", "lean-zeta--abe-group"], ["lean-zeta-zz", "lean-zeta-aa"], [0, 0, 0, 1, 1, 0, 1, 0, 0]))

    @case("SK17", "edges: a section or a group has no premise ever; a section's step file and index.json hold `rests_on: []` (present, empty); a group's step file holds the "
                  "links among its own files (empty and present when it has none)")
    def _():
        with _tmp() as d:
            errs, files, rows, rep = bld(_tree(d, SK3_BODY, SK3_SRCS), PIN, _strings())
        return _eq((errs, [r["premises"] for r in rows if r["proof"] == "none" and r["id"] in ("lean-s", "lean-s--grp", "lean-s--other")],
                    _j(files, "graph/index.json")["rests_on"], _j(files, "graph/step/lean-s.json")["rests_on"],
                    _j(files, "graph/step/lean-s--other.json")["rests_on"], len(_j(files, "graph/step/lean-s--grp.json")["rests_on"]),
                    "rests_on" in _j(files, "graph/step/lean-s-d.json"), _j(files, "graph/step/lean-s-d.json")["rests_on"]),
                   ([], [[], [], []], [], [], [], 3, True, []))

    @case("SK18", "the per-group table of the report: files, use edges (in the group), reduction edges, files with at least one drawn link (either end), files with none, the "
                  "longest path of rests_on and the widest depth row (depth 0 = a file that rests on nothing; the smallest depth wins a tie)")
    def _():
        fan = "### F part\n\n**Fan**\n\n" + "".join(f"- `New/F/{n}` (1): {n}\n" for n in "XYZWV")
        fsrcs = {"New/F/X": _lean(), "New/F/Y": _lean(imports=["New.F.X"]), "New/F/Z": _lean(imports=["New.F.X"]), "New/F/W": _lean(imports=["New.F.X"]),
                 "New/F/V": _lean()}
        with _tmp() as d:
            fe, ff, fr, frep = bld(_tree(d, fan, fsrcs), PIN, _strings())
        with _tmp() as d:
            ce, cf, cr, crep = bld(_tree(d, CHAIN_BODY, CHAIN_SRCS), PIN, _strings())
        with _tmp() as d:
            se, sf, sr, srep = bld(_tree(d, SK3_BODY, SK3_SRCS), PIN, _strings())
        return _eq((fe, frep["groups"], ce, crep["groups"], se, srep["groups"]),
                   ([], [{"group": "lean-f--fan", "files": 5, "uses": 3, "reduction": 3, "linked": 4, "unlinked": 1, "longest": 1, "widest_depth": 1, "widest_count": 3}],
                    [], [{"group": "lean-t--grp", "files": 4, "uses": 5, "reduction": 3, "linked": 4, "unlinked": 0, "longest": 3, "widest_depth": 0, "widest_count": 1}],
                    [], [{"group": "lean-s--grp", "files": 3, "uses": 3, "reduction": 2, "linked": 3, "unlinked": 0, "longest": 2, "widest_depth": 0, "widest_count": 1},
                         {"group": "lean-s--other", "files": 1, "uses": 0, "reduction": 0, "linked": 0, "unlinked": 1, "longest": 0, "widest_depth": 0, "widest_count": 1}]))

    @case("SK3b", "a use across groups is never a link and never takes part in the reduction of a group: a uses b (same group), a uses x and x uses b (x in another group): "
                  "a still has the link to b, in_reduction true (drawn 1, not drawn 2); the uses across groups are in uses.json with same_group false")
    def _():
        body = "### S part\n\n**Grp**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n\n**Other**\n\n- `New/S/X` (1): x\n"
        srcs = {"New/S/A": _lean(imports=["New.S.B", "New.S.X"]), "New/S/B": _lean(), "New/S/X": _lean(imports=["New.S.B"])}
        with _tmp() as d:
            errs, files, rows, rep = bld(_tree(d, body, srcs), PIN, _strings())
        links = _j(files, "graph/step/lean-s--grp.json")["rests_on"]
        u = _j(files, "graph/uses.json")["uses"]
        return _eq((errs, [(r["id"], r["premises"]) for r in rows if r["parent"] == "lean-s--grp"], [(l["from"], l["to"], l["in_reduction"]) for l in links], rep["drawn"], rep["not_drawn"],
                    u["lean-s-a"], u["lean-s-x"]),
                   ([], [("lean-s-a", ["lean-s-b"]), ("lean-s-b", [])], [("lean-s-a", "lean-s-b", True)], 1, 2,
                    [{"id": "lean-s-b", "names": 1, "same_group": True}, {"id": "lean-s-x", "names": 1, "same_group": False}], [{"id": "lean-s-b", "names": 1, "same_group": False}]))

    @case("SK19", "titles are the CONTENTS text with no bound: a file title of 98 characters, a group title and a section heading of 60, both with a backtick span, are kept whole (no refusal, no cut, backticks kept)")
    def _():
        ft = "w" * 49 + " " + "z" * 48
        gt = "g" * 30 + " `" + "h" * 27 + "`"
        st = "s" * 30 + " `" + "t" * 27 + "`"
        body = f"### {st}\n\n**{gt}**\n\n- `New/S/A` (1): {ft}\n"
        with _tmp() as d:
            errs, files, rows, rep = bld(_tree(d, body, {"New/S/A": _lean()}), PIN, _strings())
        return _eq((errs, [len(r["title"]) for r in rows], [r["title"] for r in rows] == [st, gt, ft]), ([], [60, 60, 98], True))

    @case("SK20", "determinism of the sidecar: a file that uses six files has its uses and its imports listed in sorted order under hash seeds 0, 1 and 2 (graph/uses.json is "
                  "byte-identical and its lists are the sorted literals)")
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
        u = json.loads(got[0][1].decode("utf-8"))
        return _eq(([g[0] for g in got], got[0][1] == got[1][1] == got[2][1], [e["id"] for e in u["uses"]["lean-s-hub"]], u["imports"]["lean-s-hub"]),
                   ([0, 0, 0], True, [f"lean-s-{n}" for n in "abcdef"], [f"lean-s-{n}" for n in "abcdef"]))

    @case("SK21", "the strings overlay (`--strings-overlay FILE`): its keys replace or add to the strings file for this map only; with the overlay giving the three kind "
                  "words and a new heading the index holds exactly the 23 keys with those words (an overlay key the page does not read is refused, case OVK1); the strings file is not edited; an "
                  "overlay without one kind word is refused GRAPH-STRINGS (exit 1); a file that is not there, not JSON or not an object is exit 2; the overlay file of this "
                  "checkout (site/strings-lean.json) holds exactly nineteen words (the five note words final, the two lines words final; `spine_lines_text` is in the Graph overlay, case GO2): the two lines words (placeholders, marked), the four of COUNT_WORDS (final), the seven of OVERLAY_WORDS (the kinds heading, the three kind words and the three card words, "
                  "placeholders) and the three of OPTIONAL_WORDS (final)")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n"
        full = {"key_kinds_heading": "Replaced heading", "symbol_kind_part": "P words", "symbol_kind_group": "G words", "symbol_kind_file": "F words",
                "card_kind_part": "P", "card_kind_group": "G", "card_kind_file": "F", **COUNT_WORDS}   # no extra key: an overlay key the page does not read is refused, case OVK1
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
                   (0, 27, "Replaced heading", "F words", "card_kind_file", "F", False, True, 1, ["GRAPH-STRINGS symbol_kind_group missing"], 1,
                    ["GRAPH-STRINGS card_kind_group missing"], 2, 2, 2, [False] * 4, {k: v for k, v in dict(OVERLAY_WORDS, **OPTIONAL_WORDS, **COUNT_WORDS, **LINES_WORDS, **NOTE_WORDS, key_scope_text=SCOPE_TEMPLATE).items() if k != "spine_lines_text"}))

    @case("SK22", "a section of one file with no folder whose first bold line holds no file (`### X`, `**A**`, `**B**`, the file `New/Main`) is `SKEL-LINE <n>` for the empty bold line "
                  "(a named refusal, exit 1, no traceback), and the same section with its one bold line over the file builds")
    def _():
        bad = "### X\n**A**\n**B**\n- `New/Main` (1): m\n"
        good = "### X\n**B**\n- `New/Main` (1): m\n"
        with _tmp() as d:
            g = _tree(d, bad, {"New/Main": _lean()})
            errs = brows(g)[0]
            rc, out, err = _cli(_args(g, os.path.join(d, "out"), _strings_file(d), _outline_file(d)))
        with _tmp() as d:
            ok = bld(_tree(d, good, {"New/Main": _lean()}), PIN, _strings())
        return _eq((errs, rc, out.splitlines(), "Traceback" in err, ok[0], [r["id"] for r in ok[2]]), ([("SKEL-LINE", "8", "")], 1, ["SKEL-LINE 8"], False, [], ["lean-x", "lean-main"]))

    @case("SK23", "an id that is cut cannot hide a bad character: the UNCUT id is checked against the id pattern first, so a file name with a non-ASCII character past the 57th "
                  "character of an over-long id (`New/X/` + 60 `a` + `\u00e9`) is GRAPH-ID with the whole id, as it is at the front; an over-long id of good characters is still cut")
    def _():
        name = "a" * 60 + "\u00e9"
        body = f"### X part\n\n**G**\n\n- `New/X/{name}` (1): x\n"
        with _tmp() as d:
            errs = bld(_tree(d, body, {f"New/X/{name}": _lean()}), PIN, _strings())[0]
        good = "a" * 60 + "b"
        with _tmp() as d:
            ok = bld(_tree(d, f"### X part\n\n**G**\n\n- `New/X/{good}` (1): x\n", {f"New/X/{good}": _lean()}), PIN, _strings())
        return _eq(([(c, w) for c, w, _ in errs], ok[0], len(ok[3]["cut"]), [len(r["id"]) for r in ok[2]]), ([("GRAPH-ID", "lean-x-" + name)], [], 1, [6, 9, 64]))

    @case("SK24", "a source file is read through one bounded, non-blocking, non-following descriptor: a .lean that is a symlink (to a file outside the tree), a FIFO, a directory or "
                  "larger than 1 MiB, or not UTF-8, is `SKEL-NOTE <path> <reason>` (`symlink`, `not-a-regular-file`, `not-a-regular-file`, `too-large`, `not-utf-8`; all reported, "
                  "exit 1, OUT not written), and one of exactly 1 MiB is read. The case runs the CLI in a subprocess with a 60 second timeout, so a tool that blocked on the FIFO "
                  "would fail the case, not hang the self-test")
    def _():
        body = "### S part\n\n**G**\n\n" + "".join(f"- `New/S/{n}` (1): {n}\n" for n in "ABCDEFG")
        limit = 1048576
        srcs = {f"New/S/{n}": _lean() for n in "ABCDEFG"}
        srcs["New/S/D"] = "-" * (limit + 1)
        srcs["New/S/E"] = "/-!\nn\n-/\n" + "-" * (limit - 9)
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
                   (1, ["SKEL-NOTE New/S/A symlink", "SKEL-NOTE New/S/B not-a-regular-file", "SKEL-NOTE New/S/C not-a-regular-file", "SKEL-NOTE New/S/D too-large",
                        "SKEL-NOTE New/S/G not-utf-8"], False, True))

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
                out.append(brows(_tree(d, b, {}))[0])
        return _eq(out, [[("SKEL-LINE", "9", "")], [("SKEL-LINE", "8", "")], [("SKEL-LINE", "7", "")], [("SKEL-LINE", "8", "")]])

    @case("SK26", "the three optional page words (key_kinds_note, note_label, note_source; final, `{source}` and `{commit}` kept literal) are index.json `strings` keys when the strings "
                  "hold them: 27 keys with none, 29 with two, 30 with all three, the values exactly the literals of OPTIONAL_WORDS (typed in this case as well); the overlay file of "
                  "this checkout holds those three values")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n"
        typed = {"key_kinds_note": "Parts and groups follow the repository's own contents list (CONTENTS.md); the titles of parts, groups and files are copied from it word for word.", "note_label": "The file's opening note, from the repository, unchanged",
                 "note_source": "Opening note of {source} \u00b7 version {commit} of lsernau/grh-lean"}
        with _tmp() as d:
            g = _tree(d, body, {"New/S/A": _lean()})
            n = lambda extra: len(_j(bld(g, PIN, dict(_strings(), **extra))[1], "graph/index.json")["strings"])
            full = _j(bld(g, PIN, dict(_strings(), **OPTIONAL_WORDS))[1], "graph/index.json")["strings"]
            counts = (n({}), n({"note_label": "L", "note_source": "S"}), n(OPTIONAL_WORDS))
        with open(os.path.join(_HERE, os.pardir, "site", "strings-lean.json"), encoding="utf-8") as f:
            overlay = json.load(f)
        return _eq((counts, OPTIONAL_WORDS == typed, {k: full[k] for k in typed}, {k: overlay.get(k) for k in typed}), ((27, 29, 30), True, typed, typed))

    @case("U1", "a file's used set and its weights are what its .ilean says: references with usages to another New module count, the weight is the number of DISTINCT names of "
                "that module (two names count two; two usage records of one name count once); a reference with no usage (a definition only, or an empty list), a reference "
                "to the file's own module and references to modules outside New are not uses; a planted extra use and a planted missing use each change the result")
    def _():
        body = "### S part\n\n**Grp**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n- `New/S/C` (1): c\n\n**Other**\n\n- `New/S/X` (1): x\n"
        srcs = {f"New/S/{n}": _lean() for n in "ABCX"}

        def refs(**kw):
            r = {}
            r.update(_ref("New.S.B", "b1", "b2"))                                   # two names: weight 2
            r.update(_ref("New.S.B", "b3", usages=0, definition=[1, 1, 1, 2]))       # a definition only: not a use
            r.update(_ref("New.S.C", "c1", usages=2))                                # two usage records of one name: weight 1
            r.update(_ref("New.S.C", "c2", usages=0))                                # no usage at all: not a use
            r.update(_ref("New.S.X", "x1"))                                          # another group
            r.update(_ref("New.S.A", "a1", "a2"))                                    # the file's own module
            r.update(_ref("Mathlib.Data.Nat", "m1"))
            r.update(_ref("Lib.Foo", "l1"))
            for k, v in kw.items():
                r.update(v)
            return r

        def uses(refs_a):
            with _tmp() as d:
                errs, files, rows, rep = bld(_tree(d, body, srcs, {"New/S/A": _ilean("New/S/A", refs_a)}), PIN, _strings())
            return errs, _j(files, "graph/uses.json")["uses"]["lean-s-a"]
        base = uses(refs())
        extra = uses(refs(extra=_ref("New.S.C", "c3")))
        missing_refs = refs()
        del missing_refs[json.dumps({"c": {"m": "New.S.B", "n": "b2"}}, separators=(",", ":"))]
        missing = uses(missing_refs)
        e = lambda i, n, g: {"id": f"lean-s-{i}", "names": n, "same_group": g}
        return _eq((base, extra, missing),
                   (([], [e("b", 2, True), e("c", 1, True), e("x", 1, False)]), ([], [e("b", 2, True), e("c", 2, True), e("x", 1, False)]),
                    ([], [e("b", 1, True), e("c", 1, True), e("x", 1, False)])))

    @case("U2", "the options: `--ilean-dir` has NO default and is required like --pin, --grh, --strings and --out (a missing one is exit 2, nothing on stdout); an --ilean-dir that "
                "is not a folder is exit 2; with all of them the run is exit 0")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n"
        with _tmp() as d:
            g = _tree(d, body, {"New/S/A": _lean()})
            sp, ol = _strings_file(d), _outline_file(d)
            full = _args(g, os.path.join(d, "out"), sp, ol)

            def without(opt):
                i = full.index(opt)
                return full[:i] + full[i + 2:]
            missing = {o: _cli(without(o)) for o in ("--ilean-dir", "--pin", "--grh", "--strings", "--out")}
            nodir = _cli(full[:full.index("--ilean-dir") + 1] + [os.path.join(d, "nothing")] + full[full.index("--ilean-dir") + 2:])
            ok = _cli(full)
        return _eq(({o: (r[0], r[1]) for o, r in missing.items()}, nodir[0], nodir[1], ok[0]), ({o: (2, "") for o in missing}, 2, "", 0))

    @case("U3", "refusals `SKEL-USES <path> <reason>`, all of them, in CONTENTS order and then the unlisted .ilean files sorted: a New file with no .ilean (missing-ilean), an .ilean whose "
                "module is not the file's (module-mismatch), one that is not JSON (not-json), one whose top level is not an object with module and references (bad-ilean), one "
                "with a reference key of an unknown shape (unknown-reference-shape), and an .ilean with no CONTENTS line (no-contents-line); the CLI exits 1 with OUT not written")
    def _():
        body = "### S part\n\n**G**\n\n" + "".join(f"- `New/S/{n}` (1): {n}\n" for n in "ABCDEF")
        srcs = {f"New/S/{n}": _lean() for n in "ABCDEF"}
        bad_key = _ilean("New/S/D", {json.dumps({"x": 1}): {"definition": None, "usages": []}})
        ileans = {"New/S/A": None, "New/S/B": _ilean("New/S/B", {}, module="New.S.Other"), "New/S/C": "{not json", "New/S/D": bad_key, "New/S/E": [], "New/S/Z": _ilean("New/S/Z", {})}
        want = [("SKEL-USES", "New/S/A", "missing-ilean"), ("SKEL-USES", "New/S/B", "module-mismatch"), ("SKEL-USES", "New/S/C", "not-json"),
                ("SKEL-USES", "New/S/D", "unknown-reference-shape"), ("SKEL-USES", "New/S/E", "bad-ilean"), ("SKEL-USES", "New/S/Z", "no-contents-line")]
        with _tmp() as d:
            g = _tree(d, body, srcs, ileans)
            errs = brows(g)[0]
            rc, out, err = _cli(_args(g, os.path.join(d, "out"), _strings_file(d), _outline_file(d)))
            absent = not os.path.exists(os.path.join(d, "out"))
        return _eq((errs, rc, out.splitlines(), absent),
                   (want, 1, ["SKEL-USES New/S/A missing-ilean", "SKEL-USES New/S/B module-mismatch", "SKEL-USES New/S/C not-json", "SKEL-USES New/S/D unknown-reference-shape",
                              "SKEL-USES New/S/E bad-ilean", "SKEL-USES New/S/Z no-contents-line"], True))

    @case("U4", "an .ilean that is a symlink, a directory or a FIFO, or is larger than 16 MiB, is refused (`symlink`, `not-a-regular-file`, `not-a-regular-file`, `too-large`) "
                "without hanging, and one of exactly 16 MiB is read. The tool opens with O_NONBLOCK and O_NOFOLLOW, fstat's the descriptor and reads at most the limit plus one "
                "byte; the case runs the CLI in a subprocess with a 60 second timeout, so a tool that blocked on the FIFO would fail the case, not hang the self-test")
    def _():
        body = "### S part\n\n**G**\n\n" + "".join(f"- `New/S/{n}` (1): {n}\n" for n in "ABCDEF")
        srcs = {f"New/S/{n}": _lean() for n in "ABCDEF"}
        limit = 16 * 1024 * 1024
        pad = lambda n: json.dumps({"decls": [], "directImports": [], "module": "New.S.X", "references": {}, "version": 5}) + " " * n
        with _tmp() as d:
            g = _tree(d, body, srcs)
            base = os.path.join(d, "ilean", "New", "S")
            for n in "ABC":
                os.remove(os.path.join(base, n + ".ilean"))
            os.symlink(os.path.join(base, "F.ilean"), os.path.join(base, "A.ilean"))
            os.mkdir(os.path.join(base, "B.ilean"))
            os.mkfifo(os.path.join(base, "C.ilean"))
            for n, size in (("D", limit + 1), ("E", limit)):
                body_text = pad(0).replace("New.S.X", f"New.S.{n}")
                with open(os.path.join(base, n + ".ilean"), "w") as f:
                    f.write(body_text + " " * (size - len(body_text)))
            sizes = (os.path.getsize(os.path.join(base, "D.ilean")), os.path.getsize(os.path.join(base, "E.ilean")))
            out = os.path.join(d, "out")
            r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, out, _strings_file(d), _outline_file(d)), capture_output=True, text=True, timeout=60)
        return _eq((sizes, r.returncode, r.stdout.splitlines()),
                   ((limit + 1, limit), 1, ["SKEL-USES New/S/A symlink", "SKEL-USES New/S/B not-a-regular-file", "SKEL-USES New/S/C not-a-regular-file", "SKEL-USES New/S/D too-large"]))

    @case("U5", "the real source (give `--selftest --grh DIR --ilean-dir DIR`; otherwise SKIPPED): 2135 use edges in all, 733 inside groups (drawn) and 1402 across, 0 cycles, "
                "the weights over all edges sum to 12688, the transitive reduction of the groups' use relations has 325 edges (true on 325 links, false on 408); "
                "MainInequality uses 12 New files with weights AdmissibleData 7, ShortAndEnough 5, TwistedLattice 4, PrimeSums 3, Magnitudes 2, IntegralTargetForms 2, Rows 2 "
                "and five with 1, and has exactly 2 imports; the five densest groups have the files, edges and reduction edges pinned")
    def _():
        if _GRH_FOR_SK13 is None or _ILEAN_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh and --ilean-dir given to the self-test")
        errs, files, rows, rep = build(_GRH_FOR_SK13, "72fead102f663d5c7a407964a13dc0cf9d977207", _strings(), ilean_dir=_ILEAN_FOR_SK13)
        u = _j(files, "graph/uses.json")
        edges = [e for v in u["uses"].values() for e in v]
        main = {e["id"]: e["names"] for e in u["uses"]["lean-reduction-main-inequality"]}
        links = [l for k, v in files.items() if k.startswith("graph/step/") for l in json.loads(v.decode("utf-8"))["rests_on"]]
        dense = {g["group"]: (g["files"], g["uses"], g["reduction"]) for g in rep["groups"] if g["files"] >= 15}
        return _eq((errs, len(edges), sum(1 for e in edges if e["same_group"]), sum(1 for e in edges if not e["same_group"]), sum(e["names"] for e in edges),
                    rep["reduction"], sum(1 for l in links if l["in_reduction"]), sum(1 for l in links if not l["in_reduction"]), len(links),
                    sorted(main.values(), reverse=True), main["lean-reduction-data-admissible-data"], main["lean-reduction-short-and-enough"],
                    main["lean-reduction-lattices-twisted-lattice"], main["lean-reduction-prime-sums"], main["lean-upper-bound-objects-rows"],
                    len(u["imports"]["lean-reduction-main-inequality"]),
                    dense["lean-spanning--two-frames-at-one-place"], dense["lean-spanning--the-remaining-terms"],
                    dense["lean-spanning--unfolding-and-the-proof-of-the-moments"], dense["lean-congruences--anticyclotomic-twists-with-small-selmer-groups"],
                    dense["lean-upper-bound--the-seesaw-identity"], sum(g["uses"] for g in rep["groups"]), sum(g["reduction"] for g in rep["groups"])),
                   ([], 2135, 733, 1402, 12688, 325, 325, 408, 733, [7, 5, 4, 3, 2, 2, 2, 1, 1, 1, 1, 1], 7, 5, 4, 3, 2, 2,
                    (22, 114, 27), (23, 79, 32), (19, 72, 22), (16, 45, 22), (15, 42, 20), 733, 325))

    def note_of(raw):
        """('ok', text) or ('err', reason) of _module_note(raw)."""
        try:
            return ("ok", _module_note(raw))
        except NoteError as e:
            return ("err", e.reason)

    RAW1 = (b"import X.Y\n\n/-!\n# Title\r\nSome `code` and $x^2$ and *emph*,\ttab  \n    indented  \nlast line  \n-/\ndef f := 1\n")

    def slice1(raw):   # the second, simpler implementation: the first `/-!` and the first `-/` after it (valid when the note holds no nested comment)
        a = raw.index(b"/-!") + 3
        return raw[a:raw.index(b"-/", a)].decode("utf-8")

    @case("N1", "a module note with markdown, backticks, `$`, a CRLF, a tab, trailing spaces and a final newline comes through byte for byte: the step file's note.text equals the "
                "source slice read in the case, note.source is `grh/src/` + the CONTENTS path + `.lean`, the note has exactly the keys review, source and text (review is {state: converter}), and the CRLF and the "
                "trailing spaces are in the written JSON as escapes")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n"
        with _tmp() as d:
            errs, files, rows, rep = bld(_tree(d, body, {"New/S/A": RAW1}), PIN, _strings())
        note = _j(files, "graph/step/lean-s-a.json")["note"]
        want = slice1(RAW1)
        return _eq((errs, note["text"] == want, note["source"], sorted(note), len(want), want.count("\r\n"), b"Title\\r\\nSome `code`" in files["graph/step/lean-s-a.json"]),
                   ([], True, "grh/src/New/S/A.lean", ["review", "source", "text"], 77, 1, True))

    @case("N2", "the equality of N1 can fail: the fixture's note differs from its strip, rstrip, lstrip, CRLF-folded, line-normalised and one-character-shorter versions, so a "
                "tool that trims, folds a newline or loses a character is caught")
    def _():
        w = slice1(RAW1)
        return _eq([w != w.strip(), w != w.rstrip(), w != w.lstrip(), w != w.replace("\r\n", "\n"), w != "\n".join(w.splitlines()), w != w[:-1], w != w + " "],
                   [True] * 7)

    @case("N3", "_module_note: the inner text of the FIRST `/-!` ... `-/` block, nesting of `/-` and `-/` counted (a note holding `/- inner -/` is taken whole, also two levels "
                "deep); a first `-/` that comes before an inner opener closes the note by depth; an unterminated block, one whose inner opener is never closed, a file with no "
                "block and bytes that are not UTF-8 are refused with their reason")
    def _():
        return _eq([note_of(b"/-! a /- inner -/ b -/\ndef x"), note_of(b"/-! a /- b /- c -/ d -/ e -/ tail"), note_of(b"/-! one -/ two /- three -/"),
                    note_of(b"/-! never"), note_of(b"/-! a /- b -/"), note_of(b"def x\n"), note_of(b"/-! \xff -/"), note_of(b"/-!-/"), note_of(b"/-!\r\n-/")],
                   [("ok", " a /- inner -/ b "), ("ok", " a /- b /- c -/ d -/ e "), ("ok", " one "), ("err", "unterminated"), ("err", "unterminated"), ("err", "no-note"),
                    ("err", "not-utf-8"), ("ok", ""), ("ok", "\r\n")])

    @case("N4", "only blank lines and `import ...` lines may precede the block: other text (a comment line, a declaration, text on the line of the opener) is "
                "`SKEL-NOTE <path> text-before-note`; blank lines with spaces, tabs and CRLF, and several imports, are accepted")
    def _():
        ok = note_of(b"import A.B\r\n\n  \t\nimport C\n/-! n -/")
        bad = [note_of(b"-- c\n/-! n -/"), note_of(b"def x\n/-! n -/"), note_of(b"x /-! n -/"), note_of(b"/- copyright -/\n/-! n -/"), note_of(b"imports\n/-! n -/")]
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n"
        with _tmp() as d:
            errs = brows(_tree(d, body, {"New/S/A": b"def x\n/-! n -/\n"}))[0]
        return _eq((ok, bad, errs), (("ok", " n "), [("err", "text-before-note")] * 5, [("SKEL-NOTE", "New/S/A", "text-before-note")]))

    @case("N5", "all bad files are reported, each named with its reason, in CONTENTS order, and the CLI exits 1 with OUT not written: a file with no note, an unterminated "
                "one, one that is not UTF-8, one with text before the note (a good file is not named)")
    def _():
        body = "### S part\n\n**G**\n\n" + "".join(f"- `New/S/{n}` (1): {n}\n" for n in "ABCDE")
        srcs = {"New/S/A": b"def x\n", "New/S/B": b"/-! never closed\n", "New/S/C": _lean(), "New/S/D": b"/-! \xff -/\n", "New/S/E": b"-- hi\n/-! n -/\n"}
        want = [("SKEL-NOTE", "New/S/A", "no-note"), ("SKEL-NOTE", "New/S/B", "unterminated"), ("SKEL-NOTE", "New/S/D", "not-utf-8"),
                ("SKEL-NOTE", "New/S/E", "text-before-note")]
        with _tmp() as d:
            g = _tree(d, body, srcs)
            errs = brows(g)[0]
            rc, out, err = _cli(_args(g, os.path.join(d, "out"), _strings_file(d), _outline_file(d)))
            absent = not os.path.exists(os.path.join(d, "out"))
        return _eq((errs, rc, out.splitlines(), absent),
                   (want, 1, ["SKEL-NOTE New/S/A no-note", "SKEL-NOTE New/S/B unterminated", "SKEL-NOTE New/S/D not-utf-8", "SKEL-NOTE New/S/E text-before-note"], True))

    @case("N6", "a .lean that is a symlink, a directory or a FIFO, or is larger than 1 MiB, is refused (`symlink`, `not-a-regular-file`, `not-a-regular-file`, `too-large`) "
                "without hanging, and one of exactly 1 MiB is accepted. The tool opens with O_NONBLOCK and O_NOFOLLOW, fstat's the descriptor and reads at most the limit plus "
                "one byte; the case runs the CLI in a subprocess with a 60 second timeout, so a tool that blocked on the FIFO would fail the case, not hang the self-test")
    def _():
        body = "### S part\n\n**G**\n\n" + "".join(f"- `New/S/{n}` (1): {n}\n" for n in "ABCDEF")
        head = b"/-!\nn\n-/\n"
        limit = 1048576
        srcs = {"New/S/A": _lean(), "New/S/B": _lean(), "New/S/C": _lean(), "New/S/D": head + b"-" * (limit + 1 - len(head)), "New/S/E": head + b"-" * (limit - len(head)),
                "New/S/F": _lean()}
        with _tmp() as d:
            g = _tree(d, body, srcs)
            base = os.path.join(g, "src", "New", "S")
            os.remove(os.path.join(base, "A.lean"))
            os.symlink(os.path.join(base, "F.lean"), os.path.join(base, "A.lean"))
            os.remove(os.path.join(base, "B.lean"))
            os.mkdir(os.path.join(base, "B.lean"))
            os.remove(os.path.join(base, "C.lean"))
            os.mkfifo(os.path.join(base, "C.lean"))
            sizes = (os.path.getsize(os.path.join(base, "D.lean")), os.path.getsize(os.path.join(base, "E.lean")))
            out = os.path.join(d, "out")
            r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, out, _strings_file(d), _outline_file(d)), capture_output=True, text=True, timeout=60)
            absent = not os.path.exists(out)
            body_ok = body.replace("- `New/S/A` (1): A\n", "").replace("- `New/S/B` (1): B\n", "").replace("- `New/S/C` (1): C\n", "").replace("- `New/S/D` (1): D\n", "")
            for n in "ABCD":
                p = os.path.join(base, n + ".lean")
                (os.rmdir if os.path.isdir(p) and not os.path.islink(p) else os.remove)(p)
                os.remove(os.path.join(d, "ilean", "New", "S", n + ".ilean"))
            with open(os.path.join(g, "CONTENTS.md"), "w", encoding="utf-8") as f:
                f.write(HEAD + body_ok + TAIL)
            errs_ok, files_ok = bld(g, PIN, _strings())[:2]
        return _eq((sizes, r.returncode, r.stdout.splitlines(), absent, errs_ok, len(_j(files_ok, "graph/step/lean-s-e.json")["note"]["text"])),
                   ((limit + 1, limit), 1, ["SKEL-NOTE New/S/A symlink", "SKEL-NOTE New/S/B not-a-regular-file", "SKEL-NOTE New/S/C not-a-regular-file", "SKEL-NOTE New/S/D too-large"],
                    True, [], 3))

    @case("N7", "only FILE steps carry a note: a part and a group step file have no `note` key; the exact key set of a file step with a note is card, children, commit, "
                "format, id, note, path, rests_on; index.json and uses.json have no note")
    def _():
        with _tmp() as d:
            errs, files, rows, rep = bld(_tree(d, SK1_BODY, SK1_SRCS), PIN, _strings())
        keys = lambda n: sorted(_j(files, f"graph/step/{n}.json"))
        return _eq((errs, keys("lean-alpha"), keys("lean-alpha--first-group"), keys("lean-alpha-one"), sorted(_j(files, "graph/index.json")), sorted(_j(files, "graph/uses.json")),
                    sorted(k for k in files if k.startswith("graph/step/") and "note" in _j(files, k))),
                   ([], ["card", "children", "commit", "format", "id", "path", "rests_on"], ["card", "children", "commit", "format", "id", "path", "rests_on"],
                    ["card", "children", "commit", "format", "id", "note", "path", "rests_on"],
                    ["assets", "commit", "format", "max_children", "rests_on", "sibling_layout", "steps", "strings", "symbols", "top"], ["commit", "format", "imports", "lib_index_rows", "titles", "used_by", "uses"],
                    ["graph/step/lean-alpha-one.json", "graph/step/lean-alpha-three.json", "graph/step/lean-alpha-two-parts.json", "graph/step/lean-beta-four.json",
                     "graph/step/lean-beta-six.json", "graph/step/lean-beta-sub-five.json"]))

    @case("N8", "`<`, `>` and `&` in a note are written as \\u003c \\u003e \\u0026 (no raw one in any file), and the JSON parses back to the exact text")
    def _():
        text = " <img src=x onerror=alert(1)> & </script> \"quoted\" \\ back\u2028slash\n"
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n"
        with _tmp() as d:
            errs, files, rows, rep = bld(_tree(d, body, {"New/S/A": ("/-!" + text + "-/\n").encode("utf-8")}), PIN, _strings())
        raw = files["graph/step/lean-s-a.json"]
        return _eq((errs, _j(files, "graph/step/lean-s-a.json")["note"]["text"] == text, [any(c in data for c in (b"<", b">", b"&")) for data in files.values()].count(True),
                    b"\\u003cimg src=x onerror=alert(1)\\u003e \\u0026 \\u003c/script\\u003e" in raw, b"\\u2028" in raw),
                   ([], True, 0, True, True))

    @case("N9", "the static check passes on the output with notes (the fixture's notes hold markdown, backticks, `$`, a table, an indented block)")
    def _():
        raw = b"/-!\n# T\n| a | b |\n|---|---|\n| `x` | $y$ |\n\n    indented block\n-/\n"
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n"
        with _tmp() as d:
            errs, files, rows, rep = bld(_tree(d, body, {"New/S/A": raw, "New/S/B": RAW1}), PIN, _strings())
        return _eq((errs, bs._graph_static_problems(files), sorted(files)[:2], [b'"note"' in files[k] for k in ("graph/step/lean-s-a.json", "graph/step/lean-s-b.json")]),
                   ([], [], ["graph/index.json", "graph/spine.json"], [True, True]))

    @case("N11", "determinism with notes: the files, the notes included, are byte-identical under PYTHONHASHSEED 0, 1 and 2")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n"
        with _tmp() as d:
            g = _tree(d, body, {"New/S/A": RAW1, "New/S/B": _lean(imports=["New.S.A"])})
            sp, ol = _strings_file(d), _outline_file(d)
            runs = []
            for seed in ("0", "1", "2"):
                out = os.path.join(d, "out" + seed)
                r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, out, sp, ol), env=dict(os.environ, PYTHONHASHSEED=seed), capture_output=True, text=True)
                runs.append((r.returncode, _tree_files(out)))
        return _eq(([r[0] for r in runs], runs[0][1] == runs[1][1] == runs[2][1], b'"note"' in runs[0][1]["graph/step/lean-s-a.json"]), ([0, 0, 0], True, True))

    @case("N12", "the real source (give `--selftest --grh DIR --ilean-dir DIR`; otherwise SKIPPED): 306 of 306 file steps carry a note and no part or group does; the sum of the lengths of the "
                 "texts in UTF-8 bytes is 729752, the upper median (sorted[n // 2]) 2246, the largest 5386; every text equals the block read independently by the simpler "
                 "implementation (the first `/-!` and the first `-/` after it), and no note holds a nested comment (0); sources all start `grh/src/New/` and end `.lean`; "
                 "the static check passes")
    def _():
        if _GRH_FOR_SK13 is None or _ILEAN_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh and --ilean-dir given to the self-test")
        errs, files, rows, rep = build(_GRH_FOR_SK13, "72fead102f663d5c7a407964a13dc0cf9d977207", _strings(), ilean_dir=_ILEAN_FOR_SK13)
        steps = {k[len("graph/step/"):-len(".json")]: _j(files, k) for k in files if k.startswith("graph/step/")}
        with_note = {i: s for i, s in steps.items() if "note" in s}
        file_ids = {r["id"] for r in rows if r["kind"] == "file"}
        root = os.path.dirname(os.path.abspath(_GRH_FOR_SK13))
        same, nested, lens = 0, 0, []
        for i, s in with_note.items():
            with open(os.path.join(root, *s["note"]["source"].split("/")), "rb") as f:
                raw = f.read()
            if s["note"]["text"] == slice1(raw):
                same += 1
            nested += s["note"]["text"].count("/-")
            lens.append(len(s["note"]["text"].encode("utf-8")))
        lens.sort()
        sizes = [len(v) for k, v in files.items() if k.startswith("graph/step/")]
        return _eq((errs, len(with_note), set(with_note) == file_ids, len(steps), same, nested, sum(lens), lens[len(lens) // 2], lens[-1],
                    all(s["note"]["source"].startswith("grh/src/New/") and s["note"]["source"].endswith(".lean") for s in with_note.values()),
                    bs._graph_static_problems(files), max(sizes) > 0),
                   ([], 306, True, 353, 306, 0, 729752, 2246, 5386, True, [], True))
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

    @case("SK31", "the .ilean folder is contained by real path under its own root (--ilean-dir): `New` a symlink to a folder outside, a folder below it (`New/S`) a symlink to a folder "
                  "outside that holds valid files, and an .ilean file that is a symlink to a file outside are each a named refusal (`SKEL-ESCAPE ilean/New symlink`, `SKEL-ESCAPE "
                  "ilean/New/S symlink`, `SKEL-USES New/S/A symlink`; exit 1, no traceback, OUT not written)")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n"
        res = {}
        for kind in ("new", "sub", "file"):
            with _tmp() as d:
                g = _tree(d, body, {"New/S/A": _lean()})
                base = os.path.join(d, "ilean")
                if kind == "new":
                    shutil.move(os.path.join(base, "New"), os.path.join(d, "outside"))
                    os.symlink(os.path.join(d, "outside"), os.path.join(base, "New"))
                elif kind == "sub":
                    shutil.move(os.path.join(base, "New", "S"), os.path.join(d, "outside"))
                    os.symlink(os.path.join(d, "outside"), os.path.join(base, "New", "S"))
                else:
                    shutil.move(os.path.join(base, "New", "S", "A.ilean"), os.path.join(d, "real.ilean"))
                    os.symlink(os.path.join(d, "real.ilean"), os.path.join(base, "New", "S", "A.ilean"))
                r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, os.path.join(d, "out"), _strings_file(d), _outline_file(d)), capture_output=True, text=True, timeout=60)
                res[kind] = (r.returncode, r.stdout.splitlines(), "Traceback" in r.stderr, os.path.exists(os.path.join(d, "out")))
        return _eq(res, {"new": (1, ["SKEL-ESCAPE ilean/New symlink"], False, False), "sub": (1, ["SKEL-ESCAPE ilean/New/S symlink"], False, False),
                         "file": (1, ["SKEL-USES New/S/A symlink"], False, False)})

    @case("SK27", "child_kind on the cards of this map: a part whose children are groups has child_kind group (also with an anonymous group), the last part (its only child is the "
                  "file Main) has child_kind file, a group has child_kind file, a file has none; the step file's own card and the child entry in its parent's file agree; and "
                  "the kinds rows group and file carry count_words (group_one, group_many, file_one, file_many), the part row none")
    def _():
        with _tmp() as d:
            errs, files, rows, rep = bld(_tree(d, SK1_BODY, SK1_SRCS), PIN, _strings())
        body2 = "### Alpha part\n\n**G**\n\n- `New/Alpha/One` (1): One\n\n### The last file\n\n- `New/Main` (3): m\n"
        with _tmp() as d:
            e2, f2, r2, rep2 = bld(_tree(d, body2, {"New/Alpha/One": _lean(), "New/Main": _lean()}), PIN, _strings())
        ck = lambda fs, i: _j(fs, f"graph/step/{i}.json")["card"].get("child_kind")
        entry = lambda fs, parent, i: [c.get("child_kind") for c in _j(fs, f"graph/step/{parent}.json")["children"] if c["id"] == i]
        rows_ix = _j(files, "graph/index.json")["symbols"]["kinds"]
        return _eq((errs, e2, [ck(files, i) for i in ("lean-alpha", "lean-beta", "lean-alpha--first-group", "lean-beta--third-group", "lean-alpha-one", "lean-beta-six")],
                    [ck(f2, i) for i in ("lean-alpha", "lean-the-last-file", "lean-main")], entry(f2, "lean-the-last-file", "lean-main"),
                    entry(files, "lean-alpha", "lean-alpha--first-group"), entry(files, "lean-alpha--first-group", "lean-alpha-one"),
                    {k: rows_ix[k].get("count_words") for k in ("part", "group", "file")}, sorted(rows_ix["file"])),
                   ([], [], ["group", "group", "file", "file", None, None], ["group", "file", None], [None], ["file"], [None],
                    {"part": None, "group": {"many": "count_group_many", "one": "count_group_one"}, "file": {"many": "count_file_many", "one": "count_file_one"}},
                    ["card_words", "class", "count_words", "text", "words"]))

    @case("CK1", "the real source (give `--selftest --grh DIR --ilean-dir DIR`; otherwise SKIPPED): 8 parts have child_kind group and 1 (the last, with the file Main) has file, all 38 "
                 "groups have file, the 306 files have none; all 353 cards agree between the card in the step's own file and the child entry in its parent's file")
    def _():
        if _GRH_FOR_SK13 is None or _ILEAN_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh and --ilean-dir given to the self-test")
        errs, files, rows, rep = build(_GRH_FOR_SK13, "72fead102f663d5c7a407964a13dc0cf9d977207", _strings(), ilean_dir=_ILEAN_FOR_SK13)
        cards = {r["id"]: _j(files, f"graph/step/{r['id']}.json")["card"] for r in rows}
        entries = {}
        for r in rows:
            for c in _j(files, f"graph/step/{r['id']}.json")["children"]:
                entries[c["id"]] = c
        kinds = {k: {} for k in ("part", "group", "file")}
        for r in rows:
            v = cards[r["id"]].get("child_kind")
            kinds[r["kind"]][v] = kinds[r["kind"]].get(v, 0) + 1
        agree = sum(1 for i, c in cards.items() if i in entries and {k: entries[i].get(k) for k in c} == c and set(entries[i]) - set(c) <= {"parent_rests_on"})
        return _eq((errs, kinds, len(cards), agree, sum(1 for r in rows if r["parent"] == "root")), ([], {"part": {"group": 8, "file": 1}, "group": {"file": 38}, "file": {None: 306}}, 353, 344, 9))

    def sp_files(d, names, spine, steps=(), ileans=None, index=None, edge=None):
        g = _tree(d, _flat(names), {f"New/S/{n}": _lean() for n in names}, ileans, index if index is not None else _index([_srow(*s) for s in spine], [_trow(*s) for s in steps]))
        os.makedirs(os.path.join(g, "src", "Lib"), exist_ok=True)
        with open(os.path.join(g, "src", "Lib", "Foo.lean"), "w", encoding="utf-8") as f:
            f.write(_lean())
        return g

    F1_ILEANS = {
        "New/S/A": _ilean("New/S/A", {**_use("New.S.B", "New.gamma", "New.alpha"), **_use("New.S.E", "New.zeta"), **_use("New.S.A", "New.alpha", "New.alpha")}, decls=["New.alpha"]),
        "New/S/B": _ilean("New/S/B", {**_use("New.S.B", "New.helper", "New.gamma"), **_use("New.S.C", "New.delta", "New.helper")}, decls=["New.gamma", "New.helper"]),
        "New/S/C": _ilean("New/S/C", _use("Lib.Foo", "Lib.Foo.bar", "New.delta"), decls=["New.delta"]),
        "New/S/D": _ilean("New/S/D", {}, decls=["New.eps"]), "New/S/E": _ilean("New/S/E", {}, decls=["New.zeta"]),
        "Lib/Foo": _ilean("Lib/Foo", _use("New.S.D", "New.eps", "Lib.Foo.bar"), module="Lib.Foo", decls=["Lib.Foo.bar"])}
    F1_SPINE = [("`alpha`", "`New/S/A`", "c1"), ("`gamma`", "`New/S/B`", "c2"), ("`delta`", "`New/S/C`", "c3"), ("`eps`", "`New/S/D`", "c4"), ("`zeta`", "`New/S/E`", "c5")]

    @case("SP1", "a spine row is ONE node even with two names: its names as written, its constants resolved in the row's file (`D.alpha` is `New.Data.alpha`, `beta` is `New.beta`, a "
                 "name equal to a declaration `plain` resolves as it is), in name order; the node holds the first cell as `theorem` and the third as `content` byte for byte (backticks, "
                 "markdown, trailing spaces kept), the step id of its file, `spine-` + the slug of its first name, and source `grh/INDEX.md`; spine.json is {commit, format 1, links, nodes}")
    def _():
        spine = [("`D.alpha`, `beta`", "`New/S/A`", "Row one: **bold**, `code`.  "), ("`plain`", "`New/S/B`", "Two")]
        ile = {"New/S/A": _ilean("New/S/A", {}, decls=["New.Data.alpha", "New.beta", "New.unrelated"]), "New/S/B": _ilean("New/S/B", {}, decls=["plain", "New.other"])}
        with _tmp() as d:
            errs, files, rows, rep = bld(sp_files(d, "AB", spine, ileans=ile), PIN, _strings())
        sp = _j(files, "graph/spine.json")
        return _eq((errs, sorted(sp), sp["commit"], sp["format"], sp["links"], len(sp["nodes"]), sp["nodes"][0], sp["nodes"][1]["id"], sp["nodes"][1]["constants"]),
                   ([], ["commit", "format", "links", "nodes"], PIN, 1, [], 2,
                    {"constants": ["New.Data.alpha", "New.beta"], "content": "Row one: **bold**, `code`.  ", "counts": {"mentions": 0, "no_doc": 0, "other_constants": 0}, "file": "lean-s-a",
                     "id": "spine-d-alpha", "mentions": [], "names": ["D.alpha", "beta"], "source": "grh/INDEX.md", "theorem": "`D.alpha`, `beta`"}, "spine-plain", ["plain"]))

    @case("SP2", "links between spine rows: a one-hop use, a chain through an UNNAMED declaration and a chain through a declaration of Lib each give the edge; a usage with no enclosing "
                 "declaration gives none and a use of a declaration inside itself is ignored; every edge of the closed relation is kept with in_reduction (true on the three of the "
                 "transitive reduction a->b, b->c, c->d, false on the three others), in table order")
    def _():
        with _tmp() as d:
            errs, files, rows, rep = bld(sp_files(d, "ABCDE", F1_SPINE, ileans=F1_ILEANS), PIN, _strings())
        sp = _j(files, "graph/spine.json")
        l = lambda a, b, r: {"from": f"spine-{a}", "in_reduction": r, "to": f"spine-{b}"}
        return _eq((errs, [n["id"] for n in sp["nodes"]], sp["links"]),
                   ([], ["spine-alpha", "spine-gamma", "spine-delta", "spine-eps", "spine-zeta"],
                    [l("alpha", "gamma", True), l("alpha", "delta", False), l("alpha", "eps", False), l("gamma", "delta", True), l("gamma", "eps", False), l("delta", "eps", True)]))

    @case("SP3", "two rows that reach each other are refused `SKEL-SPINE-CYCLE <the spine ids>` (in table order), CLI exit 1, OUT not written")
    def _():
        ile = {"New/S/A": _ilean("New/S/A", {**_use("New.S.A", "New.gamma", "New.alpha"), **_use("New.S.A", "New.alpha", "New.gamma")}, decls=["New.alpha", "New.gamma"])}
        spine = [("`alpha`", "`New/S/A`", "c1"), ("`gamma`", "`New/S/A`", "c2")]
        with _tmp() as d:
            g = sp_files(d, "A", spine, ileans=ile)
            errs = bld(g, PIN, _strings())[0]
            rc, out, err = _cli(_args(g, os.path.join(d, "out"), _strings_file(d), _outline_file(d)))
            absent = not os.path.exists(os.path.join(d, "out"))
        return _eq((errs, rc, out.splitlines(), absent), ([("SKEL-SPINE-CYCLE", "spine-alpha spine-gamma", "")], 1, ["SKEL-SPINE-CYCLE spine-alpha spine-gamma"], True))

    @case("SP4", "a name that resolves to no declaration of the row's file and a name that resolves to two are each refused `SKEL-SPINE <row number> <name> <reason>` (rows counted from 1, "
                 "all reported, exit 1)")
    def _():
        ile = {"New/S/A": _ilean("New/S/A", {}, decls=["New.dup", "dup", "New.ok"])}
        spine = [("`nothing`", "`New/S/A`", "c"), ("`dup`", "`New/S/A`", "c"), ("`ok`", "`New/S/A`", "c")]
        with _tmp() as d:
            g = sp_files(d, "A", spine, ileans=ile)
            errs = bld(g, PIN, _strings())[0]
            rc, out, err = _cli(_args(g, os.path.join(d, "out"), _strings_file(d), _outline_file(d)))
        return _eq((errs, rc, out.splitlines()), ([("SKEL-SPINE", "1 nothing", "unresolved"), ("SKEL-SPINE", "2 dup", "ambiguous")], 1,
                                                   ["SKEL-SPINE 1 nothing unresolved", "SKEL-SPINE 2 dup ambiguous"]))

    @case("SP5", "the repository's sentences: each row of the steps table whose file is a New step is carried on that step's file as index_rows [{source `grh/INDEX.md`, text: the first "
                 "cell byte for byte}] in table order (the one space of padding removed, the rest kept: backticks, inner and trailing spaces); a row whose file is in Lib is carried on "
                 "NO step and listed in graph/uses.json `lib_index_rows` [{file, source, text}] in table order; a part, a group and a file with no row have no `index_rows`; the report "
                 "counts carried 3, Lib rows 1, Lib files 1")
    def _():
        steps = [("First `code` row  ", "`New/S/A`"), ("Lib   row `x`", "`Lib/X/Y`", "", "related"), ("Second row", "`New/S/A`"), ("B row", "`New/S/B`")]
        with _tmp() as d:
            errs, files, rows, rep = bld(sp_files(d, "ABC", [], steps), PIN, _strings())
        ir = lambda i: _j(files, f"graph/step/{i}.json").get("index_rows")
        s = lambda text: {"source": "grh/INDEX.md", "text": text}
        return _eq((errs, ir("lean-s-a"), ir("lean-s-b"), ir("lean-s-c"), ir("lean-s"), ir("lean-s--g"), _j(files, "graph/uses.json")["lib_index_rows"], rep["index"]),
                   ([], [s("First `code` row  "), s("Second row")], [s("B row")], None, None, None, [{"file": "Lib/X/Y", "source": "grh/INDEX.md", "text": "Lib   row `x`"}],
                    {"carried": 3, "lib_rows": 1, "lib_files": ["Lib/X/Y"]}))

    @case("SP6", "a table with the wrong number of cells is `SKEL-INDEX <line>` (the first table needs 3, the second 4; all reported); a row whose file is a New file that is not a step "
                 "of the map is `SKEL-INDEX <line> <path> is not a step`; a missing section is exit 2")
    def _():
        bad = _index([_srow("`a`", "`New/S/A`", "c"), "| `b` | `New/S/A` |"], [_trow("x", "`New/S/A`"), "| x | `New/S/A` | y |", _trow("z", "`New/S/Nope`")])
        with _tmp() as d:
            g = sp_files(d, "A", [], index=bad, ileans={"New/S/A": _ilean("New/S/A", {}, decls=["New.a"])})
            errs = brows(g)[0]
        with _tmp() as d:
            g = sp_files(d, "A", [], index="# Index\\n\\nnothing\\n")
            rc = _cli(_args(g, os.path.join(d, "out"), _strings_file(d), _outline_file(d)))[0]
        return _eq((errs, rc), ([("SKEL-INDEX", "10", ""), ("SKEL-INDEX", "17", ""), ("SKEL-INDEX", "18", "New/S/Nope is not a step")], 2))

    @case("SP7", "spine_rows: a file step has `spine_rows`, the ids of the spine rows whose row is in that file, in table order; absent when it has none; two rows in one file give two ids")
    def _():
        ile = {"New/S/A": _ilean("New/S/A", {}, decls=["New.alpha", "New.beta"]), "New/S/B": _ilean("New/S/B", {}, decls=["New.gamma"])}
        spine = [("`alpha`", "`New/S/A`", "c"), ("`gamma`", "`New/S/B`", "c"), ("`beta`", "`New/S/A`", "c")]
        with _tmp() as d:
            errs, files, rows, rep = bld(sp_files(d, "ABC", spine, ileans=ile), PIN, _strings())
        sr = lambda i: _j(files, f"graph/step/{i}.json").get("spine_rows")
        return _eq((errs, sr("lean-s-a"), sr("lean-s-b"), sr("lean-s-c"), sr("lean-s"), sr("lean-s--g")), ([], ["spine-alpha", "spine-beta"], ["spine-gamma"], None, None, None))

    @case("SP8", "edge_basis: index.json gets the top-level OBJECT {basis: `names-written-in-source-from-compiled-index`, words: `key_lines_text`} (exactly those two keys; the sentence is "
                 "NOT in index.json) when the strings carry key_lines_text, and none when they do not; the words key is in `strings` (the page's optional keys: 27 required + the "
                 "three note words + the three lines words = 33 keys, 30 with the lines words absent); `edge_basis` itself is not a key of `strings`")
    def _():
        with _tmp() as d:
            g = sp_files(d, "A", [])
            on = _j(bld(g, PIN, dict(_strings(), **OPTIONAL_WORDS, **LINES_WORDS))[1], "graph/index.json")
            off = _j(bld(g, PIN, dict(_strings(), **OPTIONAL_WORDS))[1], "graph/index.json")
            only = _j(bld(g, PIN, dict(_strings(), key_lines_text="x"))[1], "graph/index.json")
        return _eq((on.get("edge_basis"), sorted(on["edge_basis"]), "edge_basis" in off, len(on["strings"]), "edge_basis" in on["strings"], "key_lines_text" in on["strings"], len(off["strings"]),
                    only["edge_basis"]["words"], len(only["strings"])), (EDGE_BASIS, ["basis", "words"], False, 33, False, True, 30, "key_lines_text", 28))

    @case("SP9", "used_by is the exact inverse of uses with the same weights: A uses B with two names and C with one, B uses C with two names: used_by C is [A 1, B 2], used_by B is "
                 "[A 2], used_by A is []; the number of used_by entries equals the number of uses entries")
    def _():
        ile = {"New/S/A": _ilean("New/S/A", {**_ref("New.S.B", "b1", "b2"), **_ref("New.S.C", "c1")}), "New/S/B": _ilean("New/S/B", _ref("New.S.C", "c1", "c2")), "New/S/C": _ilean("New/S/C", {})}
        with _tmp() as d:
            errs, files, rows, rep = bld(sp_files(d, "ABC", [], ileans=ile), PIN, _strings())
        u = _j(files, "graph/uses.json")
        e = lambda i, n: {"id": f"lean-s-{i}", "names": n, "same_group": True}
        return _eq((errs, u["used_by"], sum(len(v) for v in u["used_by"].values()), sum(len(v) for v in u["uses"].values())),
                   ([], {"lean-s-a": [], "lean-s-b": [e("a", 2)], "lean-s-c": [e("a", 1), e("b", 2)]}, 3, 3))

    @case("SP10", "determinism: under hash seeds 0, 1 and 2 graph/spine.json and graph/uses.json are byte-identical and every object of spine.json has sorted keys")
    def _():
        with _tmp() as d:
            g = sp_files(d, "ABCDE", F1_SPINE, ileans=F1_ILEANS)
            sp, ol = _strings_file(d), _outline_file(d)
            got = []
            for seed in ("0", "1", "2"):
                out = os.path.join(d, "out" + seed)
                r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, out, sp, ol), env=dict(os.environ, PYTHONHASHSEED=seed), capture_output=True, text=True)
                fs = _tree_files(out)
                got.append((r.returncode, fs["graph/spine.json"], fs["graph/uses.json"]))
        ok = [True]

        def chk(pairs):
            ok[0] = ok[0] and [k for k, _ in pairs] == sorted(k for k, _ in pairs)
            return dict(pairs)
        json.loads(got[0][1].decode("utf-8"), object_pairs_hook=chk)
        return _eq(([x[0] for x in got], got[0][1] == got[1][1] == got[2][1], got[0][2] == got[1][2] == got[2][2], ok[0]), ([0, 0, 0], True, True, True))

    @case("SP11", "a spine id that is also a live outline id is `SKEL-ID-CLASH <id>`, and so are two spine rows with one id; ids are at most 64 characters (a long first name is cut by the id rule)")
    def _():
        ile = {"New/S/A": _ilean("New/S/A", {}, decls=["New.alpha"]), "New/S/B": _ilean("New/S/B", {}, decls=["New.alpha"])}
        spine = [("`alpha`", "`New/S/A`", "c"), ("`alpha`", "`New/S/B`", "c")]
        longname = "x" * 80
        ile2 = {"New/S/A": _ilean("New/S/A", {}, decls=["New." + longname])}
        with _tmp() as d:
            g = sp_files(d, "AB", spine, ileans=ile)
            dup = bld(g, PIN, _strings())[0]
        with _tmp() as d:
            g = sp_files(d, "A", [(f"`{longname}`", "`New/S/A`", "c")], ileans=ile2)
            live = bld(g, PIN, _strings(), live_ids=["spine-" + "x" * 58])
            fine = bld(g, PIN, _strings())
        return _eq((dup, [(c, w) for c, w, _ in live[0]], fine[0], [len(n["id"]) for n in _j(fine[1], "graph/spine.json")["nodes"]]),
                   ([("SKEL-ID-CLASH", "spine-alpha", "")], [], [], [64]))

    @case("SP12", "INDEX.md is read through the bounded reader: a symlink, a FIFO, a file over 1 MiB, bytes that are not UTF-8 and a missing file are each `SKEL-INDEX INDEX.md <reason>` "
                  "(symlink, not-a-regular-file, too-large, not-utf-8, missing; exit 1, no hang: the CLI runs in a subprocess with a 60 second timeout); the .ilean files outside New "
                  "(the walk of --ilean-dir that builds the spine) are bounded too: a symlinked one is `SKEL-USES Lib/Foo symlink`, a FIFO one `SKEL-USES Lib/Bar not-a-regular-file`")
    def _():
        out = []
        for kind in ("symlink", "fifo", "big", "bytes", "missing"):
            with _tmp() as d:
                g = sp_files(d, "A", [])
                path = os.path.join(g, "INDEX.md")
                os.remove(path)
                if kind == "symlink":
                    with open(os.path.join(d, "elsewhere.md"), "w") as f:
                        f.write(_index())
                    os.symlink(os.path.join(d, "elsewhere.md"), path)
                elif kind == "fifo":
                    os.mkfifo(path)
                elif kind == "big":
                    with open(path, "w") as f:
                        f.write(_index() + " " * (1048576 + 1 - len(_index())))
                elif kind == "bytes":
                    with open(path, "wb") as f:
                        f.write(b"\xff\xfe")
                r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, os.path.join(d, "out"), _strings_file(d), _outline_file(d)), capture_output=True, text=True, timeout=60)
                out.append((r.returncode, r.stdout.splitlines()))
        with _tmp() as d:
            g = sp_files(d, "A", [])
            base = os.path.join(d, "ilean", "Lib")
            os.makedirs(base)
            with open(os.path.join(d, "real.ilean"), "w") as f:
                f.write(json.dumps(_ilean("Lib/Foo", {}, module="Lib.Foo")))
            os.symlink(os.path.join(d, "real.ilean"), os.path.join(base, "Foo.ilean"))
            os.mkfifo(os.path.join(base, "Bar.ilean"))
            r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, os.path.join(d, "out"), _strings_file(d), _outline_file(d)), capture_output=True, text=True, timeout=60)
        return _eq((out, r.returncode, r.stdout.splitlines()),
                   ([(1, ["SKEL-INDEX INDEX.md symlink"]), (1, ["SKEL-INDEX INDEX.md not-a-regular-file"]), (1, ["SKEL-INDEX INDEX.md too-large"]), (1, ["SKEL-INDEX INDEX.md not-utf-8"]),
                     (1, ["SKEL-INDEX INDEX.md missing"])], 1, ["SKEL-USES Lib/Bar not-a-regular-file", "SKEL-USES Lib/Foo symlink"]))

    @case("SPN1", "the real source (give `--selftest --grh DIR --ilean-dir DIR`; otherwise SKIPPED): 9 spine nodes (rows read from INDEX.md in the case); the two rows of ShortAndEnough and "
                  "the two of OneSidedBound share a file, 7 distinct files hold spine rows; 19 links, 8 in the reduction, the longest chain of the reduction 5; the relation by name: "
                  "integral_forms_long rests on covolume; star_inequality on Theorem A, enough_forms, covolume, integral_forms_long (reduction A, enough, integral); the rpow row on those "
                  "and star_inequality and the abs row (reduction star, abs); grh on all eight others (reduction rpow, LFunction); the others on none; 57 index rows carried on 57 file "
                  "steps, 24 Lib rows (22 distinct files) in lib_index_rows in table order and on no step; used_by has as many entries as uses (2135), 112 for FieldsAndPlaces and 100 for "
                  "AdmissibleData; edge_basis the pointer object and not a key of strings")
    def _():
        if _GRH_FOR_SK13 is None or _ILEAN_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh and --ilean-dir given to the self-test")
        errs, files, rows, rep = build(_GRH_FOR_SK13, "72fead102f663d5c7a407964a13dc0cf9d977207", dict(_strings(), **LINES_WORDS), ilean_dir=_ILEAN_FOR_SK13)
        sp = _j(files, "graph/spine.json")
        u = _j(files, "graph/uses.json")
        with open(os.path.join(_GRH_FOR_SK13, "INDEX.md"), encoding="utf-8") as f:
            lines = f.read().split("\n")
        first = []   # the first name of each row of the first table, read by a simpler implementation
        i = lines.index("## The last step")
        for ln in lines[i:]:
            if ln.startswith("## ") and ln != "## The last step":
                break
            m = re.match(r"\| `([^`]+)`", ln)
            if m:
                first.append(m.group(1))
        steps_rows = []
        i = lines.index("## Steps of the argument")
        for ln in lines[i:]:
            if ln.startswith("## ") and ln != "## Steps of the argument":
                break
            m = re.match(r"\| (.*?) \| `([^`]+)` \|", ln)
            if m:
                steps_rows.append((m.group(2), m.group(1)))
        nm = {n["names"][0]: n["id"] for n in sp["nodes"]}
        rests, red = {}, {}
        for l in sp["links"]:
            rests.setdefault(l["from"], set()).add(l["to"])
            if l["in_reduction"]:
                red.setdefault(l["from"], set()).add(l["to"])
        byname = lambda n, table: {x for x in nm if nm[x] in table.get(nm[n], set())}
        A, E, C, I, ST = "D.span_short_integralRamified_eq_top", "D.enough_forms", "TwistedLattice.covolume_add_index_nonneg", "D.integral_forms_long", "star_inequality"
        P, R, L, G = "eventually_abs_primeRemainder_le", "eventually_primeRemainder_le_rpow", "LFunction_ne_zero_of_primeRemainder_le", "grh"
        depth = {}

        def longest(x):
            if x not in depth:
                depth[x] = 1 + max([longest(y) for y in red.get(x, ())] or [0])
            return depth[x]
        step_rows = {i: _j(files, f"graph/step/{i}.json").get("index_rows") for i in (r["id"] for r in rows if r["kind"] == "file")}
        carried = [v for v in step_rows.values() if v]
        libs = [(f, t) for f, t in steps_rows if f.startswith("Lib/")]
        spine_files = {}
        for n in sp["nodes"]:
            spine_files[n["file"]] = spine_files.get(n["file"], 0) + 1
        entries = sum(len(v) for v in u["used_by"].values())
        return _eq((errs, first == [n["names"][0] if len(n["names"]) == 1 else n["names"][0] for n in sp["nodes"]], len(sp["nodes"]), len(sp["links"]), sum(1 for l in sp["links"] if l["in_reduction"]),
                    max(longest(n["id"]) for n in sp["nodes"]),
                    sorted(spine_files.values()), len(spine_files), byname(ST, rests), byname(I, rests), byname(R, rests) == {A, E, C, I, ST, P}, byname(G, rests) == set(nm) - {G},
                    byname(ST, red), byname(R, red), byname(G, red), [byname(x, rests) for x in (A, E, C, P, L)],
                    sum(len(v or []) for v in step_rows.values()), len(carried), [(e["file"], e["text"]) for e in u["lib_index_rows"]] == libs, len(u["lib_index_rows"]), len({e["file"] for e in u["lib_index_rows"]}),
                    entries, sum(len(v) for v in u["uses"].values()), len(u["used_by"]["lean-reduction-data-fields-and-places"]), len(u["used_by"]["lean-reduction-data-admissible-data"]),
                    _j(files, "graph/index.json").get("edge_basis"), "edge_basis" in _j(files, "graph/index.json")["strings"]),
                   ([], True, 9, 19, 8, 5, [1, 1, 1, 1, 1, 2, 2], 7, {A, E, C, I}, {C}, True, True, {A, E, I}, {ST, P}, {R, L}, [set()] * 5, 57, 57, True, 24, 22, 2135, 2135, 112, 100, EDGE_BASIS, False))

    SRC_A = "\n".join([
        "/-!", "note", "-/",
        "/-- Doc for helper.", "", "Second para with `code` and trailing space ", "-/", "@[simp]",
        "lemma helper : True := trivial", "def d1 : Nat := 1", "abbrev ab : Nat := 2", "structure St where", "  x : Nat", "class Cl where", "  y : Nat",
        "instance inst : Inhabited Nat := ⟨0⟩", "inductive Ind where", "  | a", "theorem main : True := trivial", "@[simp] theorem attr_same_line : True := trivial", ""])
    SRC_L = "\n".join(["/-!", "lib note", "-/", "/-- Lib doc. -/", "theorem libthing : True := trivial", ""])

    def decl(sl, sc, el, ec, nl, nc, ne):
        return [sl, sc, el, ec, nl, nc, nl, nc + ne]

    A_DECLS = {"New.helper": decl(3, 0, 8, 30, 8, 6, 6), "New.d1": decl(9, 0, 9, 22, 9, 4, 2), "New.ab": decl(10, 0, 10, 24, 10, 7, 2), "New.St": decl(11, 0, 12, 10, 11, 10, 2),
               "New.Cl": decl(13, 0, 14, 10, 13, 6, 2), "New.inst": decl(15, 0, 15, 40, 15, 9, 4), "New.Ind": decl(16, 0, 17, 6, 16, 10, 3), "New.main": decl(18, 0, 18, 30, 18, 8, 4),
               "New.attr_same_line": decl(19, 0, 19, 40, 19, 16, 14)}

    def mref(module, name, *positions, enclosing="New.main"):
        return {json.dumps({"c": {"m": module, "n": name}}, separators=(",", ":")): {"definition": None, "usages": [[l, c, l, c + 1, enclosing] for l, c in positions]}}

    def mention_fixture(d, extra_decls=None, lib_src=SRC_L):
        refs = {}
        for name, pos in (("New.helper", [(18, 30), (18, 2)]), ("New.d1", [(18, 5)]), ("New.ab", [(18, 9)]), ("New.St", [(18, 14)]), ("New.Cl", [(18, 16)]), ("New.inst", [(18, 18)]),
                          ("New.Ind", [(18, 20)]), ("New.attr_same_line", [(18, 22)])):
            refs.update(mref("New.S.A", name, *pos))
        refs.update(mref("New.S.A", "New.St.x", (18, 24)))                 # a structure field: not a declaration of the index
        refs.update(mref("Mathlib.Nat", "Nat.add_comm", (18, 26)))         # outside New and Lib
        refs.update(mref("Lib.Foo", "Lib.libthing", (18, 28)))             # a declaration of Lib
        refs.update(mref("New.S.A", "New.main", (18, 1)))                  # its own constant
        ile = {"New/S/A": _ilean("New/S/A", refs, decls=[]), "Lib/Foo": _ilean("Lib/Foo", {}, module="Lib.Foo", decls=[])}
        ile["New/S/A"]["decls"] = dict(A_DECLS, **(extra_decls or {}))
        ile["Lib/Foo"]["decls"] = {"Lib.libthing": decl(3, 0, 4, 30, 4, 8, 8)}
        spine = [("`main`", "`New/S/A`", "row"), ("`d1`", "`New/S/A`", "row two")]
        g = _tree(d, _flat("A"), {"New/S/A": SRC_A}, ile, _index([_srow(*s) for s in spine]))
        os.makedirs(os.path.join(g, "src", "Lib"), exist_ok=True)
        with open(os.path.join(g, "src", "Lib", "Foo.lean"), "w", encoding="utf-8") as f:
            f.write(lib_src)
        return g

    @case("MN1", "the direct mentions of a spine row (one hop): the declarations of New or Lib that its declaration NAMES, in the reading order of the proof (the smallest (line, col) of "
                 "a usage inside the declaration, a constant named at two positions taking the smaller), each with its kind as the author wrote it (lemma stays lemma, abbrev "
                 "stays abbrev; theorem, def, structure, class, instance, inductive; an attribute on the same line skipped), its doc comment byte for byte (blank lines, a "
                 "backtick, a trailing space; from `/--` on an earlier line through the `-/` that closes it, nesting counted, also with an attribute line between it and the keyword) or no `doc` key, "
                 "line, module, file_path, first_use [line + 1, col], `file` for a New declaration and none for a Lib one, `spine` when it is itself a row; the row's own constants, "
                 "a Mathlib constant and a structure field are not mentions")
    def _():
        with _tmp() as d:
            errs, files, rows, rep = bld(mention_fixture(d), PIN, _strings())
        sp = _j(files, "graph/spine.json")
        ms = sp["nodes"][0]["mentions"]
        brief = [(m["constant"], m["kind"], m["line"], m["first_use"], m.get("file"), m.get("spine"), "doc" in m) for m in ms]
        src_a = "grh/src/New/S/A.lean"
        doc = [m for m in ms if m["constant"] == "New.helper"][0]
        return _eq((errs, brief, doc["doc"], doc["module"], doc["file_path"], [m for m in ms if m["constant"] == "New.Cl"][0]["file_path"], [m for m in ms if m["constant"] == "Lib.libthing"][0]),
                   ([], [("New.helper", "lemma", 9, [19, 2], "lean-s-a", None, True), ("New.d1", "def", 10, [19, 5], "lean-s-a", "spine-d1", False), ("New.ab", "abbrev", 11, [19, 9], "lean-s-a", None, False),
                         ("New.St", "structure", 12, [19, 14], "lean-s-a", None, False), ("New.Cl", "class", 14, [19, 16], "lean-s-a", None, False),
                         ("New.inst", "instance", 16, [19, 18], "lean-s-a", None, False), ("New.Ind", "inductive", 17, [19, 20], "lean-s-a", None, False),
                         ("New.attr_same_line", "theorem", 20, [19, 22], "lean-s-a", None, False), ("Lib.libthing", "theorem", 5, [19, 28], None, None, True)],
                    {"line": 4, "source": src_a, "text": "/-- Doc for helper.\n\nSecond para with `code` and trailing space \n-/"}, "New.S.A", src_a, src_a,
                    {"constant": "Lib.libthing", "doc": {"line": 4, "source": "grh/src/Lib/Foo.lean", "text": "/-- Lib doc. -/"}, "first_use": [19, 28], "kind": "theorem", "line": 5,
                     "module": "Lib.Foo", "file_path": "grh/src/Lib/Foo.lean"}))

    @case("MN2", "counts: {mentions, no_doc, other_constants}: the mentions of the row, those with no doc comment, and the DISTINCT constants named that are not declarations of New or "
                 "Lib (here a Mathlib constant and a structure field, whose kind is not guessed); the second row has none")
    def _():
        with _tmp() as d:
            errs, files, rows, rep = bld(mention_fixture(d), PIN, _strings())
        nodes = _j(files, "graph/spine.json")["nodes"]
        return _eq((errs, nodes[0]["counts"], nodes[1]["counts"], nodes[1]["mentions"]), ([], {"mentions": 9, "no_doc": 7, "other_constants": 2}, {"mentions": 0, "no_doc": 0, "other_constants": 0}, []))

    @case("MN3", "a two-declaration row orders by the table's name order first (all that p names, then what q names), then by first use; a constant named by both takes its position "
                 "from the first declaration that names it; no `file`/`spine` keys when they do not apply")
    def _():
        src = "\n".join(["/-!", "n", "-/", "theorem z1 : True := trivial", "theorem z0 : True := trivial", "theorem zb : True := trivial", "theorem p : True := trivial",
                         "theorem q : True := trivial", ""])
        dec = {"New.z1": decl(3, 0, 3, 28, 3, 8, 2), "New.z0": decl(4, 0, 4, 28, 4, 8, 2), "New.zb": decl(5, 0, 5, 28, 5, 8, 2), "New.p": decl(6, 0, 6, 26, 6, 8, 1), "New.q": decl(7, 0, 7, 26, 7, 8, 1)}
        refs = {**mref("New.S.A", "New.z1", (6, 20), enclosing="New.p"), **mref("New.S.A", "New.zb", (6, 25), enclosing="New.p"), **mref("New.S.A", "New.zb", (7, 3), enclosing="New.q"),
                **mref("New.S.A", "New.z0", (7, 10), enclosing="New.q")}
        # one reference key per constant: the usages of zb in p and in q are two records of one reference
        refs[json.dumps({"c": {"m": "New.S.A", "n": "New.zb"}}, separators=(",", ":"))]["usages"] = [[6, 25, 6, 26, "New.p"], [7, 3, 7, 4, "New.q"]]
        ile = {"New/S/A": dict(_ilean("New/S/A", refs), decls=dec)}
        with _tmp() as d:
            g = _tree(d, _flat("A"), {"New/S/A": src}, ile, _index([_srow("`p`, `q`", "`New/S/A`", "two names")]))
            errs, files, rows, rep = bld(g, PIN, _strings())
        node = _j(files, "graph/spine.json")["nodes"][0]
        return _eq((errs, [(m["constant"], m["first_use"]) for m in node["mentions"]], node["counts"], [sorted(m) for m in node["mentions"]][:1]),
                   ([], [("New.z1", [7, 20]), ("New.zb", [7, 25]), ("New.z0", [8, 10])], {"mentions": 3, "no_doc": 3, "other_constants": 0},
                    [["constant", "file", "file_path", "first_use", "kind", "line", "module"]]))

    @case("MN4", "a declaration whose keyword cannot be read (no theorem, lemma, def, abbrev, structure, class, inductive, instance, axiom, opaque or example before the name on its "
                 "line) refuses the build `SKEL-KIND <constant>`, all of them; so does a source that cannot be read through the bounded reader (a symlink), named the same way; "
                 "a Lib source is read through it too")
    def _():
        with _tmp() as d:
            g = mention_fixture(d, extra_decls={"New.d1": decl(9, 0, 9, 22, 9, 0, 2)})   # the name at the start of its line: nothing before it
            e1 = bld(g, PIN, _strings())[0]
        with _tmp() as d:
            g = mention_fixture(d)
            lib = os.path.join(g, "src", "Lib", "Foo.lean")
            os.rename(lib, os.path.join(d, "real.lean"))
            os.symlink(os.path.join(d, "real.lean"), lib)
            e2 = bld(g, PIN, _strings())[0]
        return _eq((e1, e2), ([("SKEL-KIND", "New.d1", "")], [("SKEL-KIND", "Lib.libthing", "symlink")]))

    @case("MN5", "determinism: the mentions, their order and spine.json are byte-identical under hash seeds 0, 1 and 2")
    def _():
        with _tmp() as d:
            g = mention_fixture(d)
            sp, ol = _strings_file(d), _outline_file(d)
            got = []
            for seed in ("0", "1", "2"):
                out = os.path.join(d, "out" + seed)
                r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, out, sp, ol), env=dict(os.environ, PYTHONHASHSEED=seed), capture_output=True, text=True)
                got.append((r.returncode, _tree_files(out)["graph/spine.json"]))
        return _eq(([x[0] for x in got], got[0][1] == got[1][1] == got[2][1], b'"mentions"' in got[0][1]), ([0, 0, 0], True, True))

    @case("MN6", "a row's own constants are never listed as mentions of the row, also when one declaration of a two-declaration row names the other (p names q: q is not a mention of the row)")
    def _():
        src = "\n".join(["/-!", "n", "-/", "theorem z1 : True := trivial", "theorem p : True := trivial", "theorem q : True := trivial", ""])
        dec = {"New.z1": decl(3, 0, 3, 28, 3, 8, 2), "New.p": decl(4, 0, 4, 26, 4, 8, 1), "New.q": decl(5, 0, 5, 26, 5, 8, 1)}
        refs = {**mref("New.S.A", "New.z1", (4, 20), enclosing="New.p"), **mref("New.S.A", "New.q", (4, 5), enclosing="New.p")}
        with _tmp() as d:
            g = _tree(d, _flat("A"), {"New/S/A": src}, {"New/S/A": dict(_ilean("New/S/A", refs), decls=dec)}, _index([_srow("`p`, `q`", "`New/S/A`", "two names")]))
            errs, files, rows, rep = bld(g, PIN, _strings())
        node = _j(files, "graph/spine.json")["nodes"][0]
        return _eq((errs, [m["constant"] for m in node["mentions"]], node["counts"]), ([], ["New.z1"], {"mentions": 1, "no_doc": 1, "other_constants": 0}))

    @case("SP13", "uses.json `titles`: {step id: {kind, path, title}} for EVERY step (parts with path [], groups, files), each equal to the step file's own card title, path and kind "
                  "(read from the written step files); a hostile title (`<img onerror>`, a backtick span) is escaped in the JSON and parses back exactly")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): <img src=x onerror=alert(1)> & `code`\n- `New/S/B` (1): plain\n"
        with _tmp() as d:
            errs, files, rows, rep = bld(_tree(d, body, {"New/S/A": _lean(), "New/S/B": _lean()}), PIN, _strings())
        u = _j(files, "graph/uses.json")
        step = lambda i: _j(files, f"graph/step/{i}.json")
        same = all(u["titles"][i] == {"kind": step(i)["card"]["kind"], "path": step(i)["card"]["path"], "title": step(i)["card"]["title"]} for i in u["titles"])
        return _eq((errs, sorted(u["titles"]), same, u["titles"]["lean-s-a"], u["titles"]["lean-s"], b"\\u003cimg src=x onerror=alert(1)\\u003e \\u0026 `code`" in files["graph/uses.json"],
                    any(c in files["graph/uses.json"] for c in (b"<", b">", b"&")), sorted(u["titles"]) == sorted(k[len("graph/step/"):-5] for k in files if k.startswith("graph/step/"))),
                   ([], ["lean-s", "lean-s--g", "lean-s-a", "lean-s-b"], True, {"kind": "file", "path": ["lean-s", "lean-s--g"], "title": "<img src=x onerror=alert(1)> & `code`"},
                    {"kind": "part", "path": [], "title": "S part"}, True, False, True))

    @case("MN7", "a mention with no usable usage position is loud: a constant named by a record whose line is not a number is `SKEL-MENTION <row> <constant> no usage position` (rows "
                 "counted from 1), never a default position")
    def _():
        refs = mref("New.S.A", "New.helper", (18, 2))
        refs[json.dumps({"c": {"m": "New.S.A", "n": "New.helper"}}, separators=(",", ":"))]["usages"] = [["x", 2, 18, 3, "New.main"]]
        with _tmp() as d:
            g = mention_fixture(d)
            ile = _j({"i": open(os.path.join(d, "ilean", "New", "S", "A.ilean"), "rb").read()}, "i")
            key = json.dumps({"c": {"m": "New.S.A", "n": "New.helper"}}, separators=(",", ":"))
            ile["references"][key]["usages"] = [["x", 2, 18, 3, "New.main"]]
            with open(os.path.join(d, "ilean", "New", "S", "A.ilean"), "w", encoding="utf-8") as f:
                f.write(json.dumps(ile))
            errs = bld(g, PIN, _strings())[0]
            rc, out, err = _cli(_args(g, os.path.join(d, "out"), _strings_file(d), _outline_file(d)))
        return _eq((errs, rc, out.splitlines()), ([("SKEL-MENTION", "1 New.helper", "no usage position")], 1, ["SKEL-MENTION 1 New.helper no usage position"]))

    def invariants(files):
        """The invariants of the page-facing files (docs/tools.md), each as a named boolean."""
        ix, sp, us = (_j(files, f"graph/{n}.json") for n in ("index", "spine", "uses"))
        steps = {k[len("graph/step/"):-5]: _j(files, k) for k in files if k.startswith("graph/step/")}
        file_ids = {i for i, s in steps.items() if s["card"]["kind"] == "file"}
        ids = {n["id"] for n in sp["nodes"]}
        ms = [m for n in sp["nodes"] for m in n["mentions"]]
        inv = {}
        inv["commit"] = ix["commit"] == sp["commit"] == us["commit"]
        inv["links"] = all(l["from"] in ids and l["to"] in ids for l in sp["links"])
        inv["node file"] = all(n["file"] in file_ids for n in sp["nodes"])
        inv["mention file"] = all(m["file"] in file_ids for m in ms if "file" in m)
        inv["mention spine"] = all(m["spine"] in ids for m in ms if "spine" in m)
        inv["counts"] = all(n["counts"]["mentions"] == len(n["mentions"]) and n["counts"]["no_doc"] == sum(1 for m in n["mentions"] if "doc" not in m) for n in sp["nodes"])
        inv["used_by"] = sorted((a, e["id"], e["names"], e["same_group"]) for a, v in us["used_by"].items() for e in v) == sorted((e["id"], a, e["names"], e["same_group"]) for a, v in us["uses"].items() for e in v)
        inv["spine basis"] = sp["edge_basis"]["words"] in ix["strings"] and sp["edge_basis"]["words"] != ix["edge_basis"]["words"]
        inv["titles"] = set(us["titles"]) == set(steps) and all(us["titles"][i] == {"kind": s["card"]["kind"], "path": s["card"]["path"], "title": s["card"]["title"]} for i, s in steps.items())
        return inv

    @case("OVL1", "the overlay of this checkout holds the page's optional words with these values, each equal to the literal typed here (and to the constants of the cases): note_label, "
                  "note_label_typeset, note_source, note_typeset_line, note_exact_button, note_render_button (final), key_kinds_note (final), and the three lines words, "
                  "which are FINAL too: no value starts with `[proposal]` or `[placeholder]`, and the word `edge` is in none of the page words (the data key edge_basis is not a page word); `{n}` appears only in the four count words; with the three old optional words `strings` is 30 keys, "
                  "with all seven new ones 37, with none of the optional 27")
    def _():
        typed = {"note_label": "The file's opening note, from the repository, unchanged", "note_label_typeset": "The file's opening note, from the repository",
                 "note_source": "Opening note of {source} · version {commit} of lsernau/grh-lean",
                 "note_typeset_line": "Formulas set in maths type by us; every symbol is the repository's.", "note_exact_button": "Show the exact text", "note_render_button": "Show in maths type", "key_lines_heading": "What a line is",
                 "key_lines_text": LINES_WORDS["key_lines_text"],   # the one literal of the test: LINES_WORDS
                 "spine_lines_text": "A line means the upper result rests on the lower one, directly or through steps not drawn here. Lean also uses results it fills in on its own without naming "
                                     "them; those are not counted, so a result can rest on more than its lines show. Every line drawn is real."}
        with open(os.path.join(_HERE, os.pardir, "site", "strings-lean.json"), encoding="utf-8") as f:
            ov = json.load(f)
        with open(os.path.join(_HERE, os.pardir, "site", "strings-lean-graph.json"), encoding="utf-8") as f:
            ov.update(json.load(f))   # the words of both overlay files are held to the same value rules
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n"
        with _tmp() as d:
            g = _tree(d, body, {"New/S/A": _lean()})
            n = lambda extra: len(_j(bld(g, PIN, dict(_strings(), **extra))[1], "graph/index.json")["strings"])
            counts = (n({}), n(OPTIONAL_WORDS), n(dict(OPTIONAL_WORDS, **LINES_WORDS, **NOTE_WORDS)), n(dict(OPTIONAL_WORDS, **NOTE_WORDS)))
        return _eq(({k: ov.get(k) for k in typed}, {**LINES_WORDS, **NOTE_WORDS, **{k: OPTIONAL_WORDS[k] for k in ("note_label", "note_source")}} == {k: typed[k] for k in
                                                                                                        list(LINES_WORDS) + list(NOTE_WORDS) + ["note_label", "note_source"]},
                    sorted(k for k, v in ov.items() if v.startswith(("[proposal]", "[placeholder]"))), sorted(k for k, v in ov.items() if re.search(r"\bedges?\b", v, re.I)),
                    sorted(k for k, v in ov.items() if "{n}" in v), counts),
                   (typed, True, [], [],
                    ["count_file_many", "count_file_one", "count_group_many", "count_group_one", ], (27, 30, 37, 34)))

    GO_CARDS = dict(OVERLAY_WORDS, **COUNT_WORDS, **OPTIONAL_WORDS, **NOTE_WORDS, key_lines_heading=LINES_WORDS["key_lines_heading"], key_lines_text=LINES_WORDS["key_lines_text"])   # every word but the Graph one
    GO_GRAPH = {"spine_lines_text": LINES_WORDS["spine_lines_text"]}

    def go_setup(d):
        g = _tree(d, "### S part\n\n**G**\n\n- `New/S/A` (1): a\n", {"New/S/A": _lean()})
        return g, _strings_file(d, _strings(extra=False)), _outline_file(d)

    def go_file(d, name, obj):
        path = os.path.join(d, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(obj if isinstance(obj, str) else json.dumps(obj))
        return path

    def go_run(d, g, sp, ol, name, **kw):
        """(exit code, stdout lines, stderr, whether OUT_DIR `name` exists) of one run."""
        r = _cli(_args(g, os.path.join(d, name), sp, ol, **kw))
        return r[0], r[1].splitlines(), r[2], os.path.exists(os.path.join(d, name))

    @case("GO1", "the Graph overlay (`--strings-overlay-graph FILE`, no default): WITHOUT the option none of the keys of the file is in index.json `strings` and spine.json has NO `edge_basis`, and every other byte "
                 "of the build is as it is with the option (only graph/index.json `strings` and graph/spine.json differ, by exactly those); WITH it every key of the file is in `strings` and spine.json carries "
                 "{basis: reaches-through-any-chain-of-uses, words: spine_lines_text}; and the build with the option is byte for byte the build in which the same key is in the Cards overlay (today's build); "
                 "a file with all three lines words as the Graph overlay has all three in `strings` with the option and none without; "
                 "the checkout's own build with no option at all has neither the key nor the `edge_basis`")
    def _():
        with _tmp() as d:
            g, sp, ol = go_setup(d)
            cards, cards_old = go_file(d, "c.json", GO_CARDS), go_file(d, "co.json", dict(GO_CARDS, **GO_GRAPH))
            gf = go_file(d, "g.json", GO_GRAPH)

            def run(name, **kw):
                return go_run(d, g, sp, ol, name, **kw)[0], _tree_files(os.path.join(d, name))
            (ra, a), (rb, b), (rc, c) = run("a", overlay=cards), run("b", overlay=cards, graph=gf), run("c", overlay=cards_old)
            three = go_file(d, "g3.json", {k: LINES_WORDS[k] for k in ("key_lines_heading", "key_lines_text", "spine_lines_text")})
            base = go_file(d, "c3.json", {k: v for k, v in GO_CARDS.items() if k not in LINES_WORDS})
            (r3, t3), (r4, t4) = run("t3", overlay=base, graph=three), run("t4", overlay=base)
            rd, dflt = run("d")   # no option at all, the checkout's own Cards overlay: a Cards-only build
        ia, ib = _j(a, "graph/index.json"), _j(b, "graph/index.json")
        sa, sb = _j(a, "graph/spine.json"), _j(b, "graph/spine.json")
        differ = sorted(n for n in set(a) | set(b) if a.get(n) != b.get(n))
        return _eq((ra, rb, rc, "spine_lines_text" in ia["strings"], "edge_basis" in sa, "spine_lines_text" in ib["strings"], sb.get("edge_basis"), differ,
                    {k: v for k, v in ib["strings"].items() if k != "spine_lines_text"} == ia["strings"], {k: v for k, v in sb.items() if k != "edge_basis"} == sa, b == c,
                    (r3, r4, sorted(k for k in LINES_WORDS if k in _j(t3, "graph/index.json")["strings"]), sorted(k for k in LINES_WORDS if k in _j(t4, "graph/index.json")["strings"]),
                     "edge_basis" in _j(t3, "graph/spine.json"), "edge_basis" in _j(t4, "graph/spine.json")),
                    (rd, "spine_lines_text" in _j(dflt, "graph/index.json")["strings"], "edge_basis" in _j(dflt, "graph/spine.json"))),
                   (0, 0, 0, False, False, True, {"basis": "reaches-through-any-chain-of-uses", "words": "spine_lines_text"}, ["graph/index.json", "graph/spine.json"], True, True, True,
                    (0, 0, sorted(LINES_WORDS), [], True, False), (0, False, False)))

    @case("GO2", "the files of this checkout: site/strings-lean.json (the Cards overlay) has 21 keys (19, key_scope_text and note_render_button) and no `spine_lines_text`; site/strings-lean-graph.json holds exactly that one key, with the value of "
                 "LINES_WORDS (the literal of this tool); the Graph overlay is not read by default (`OVERLAY` names only the Cards file)")
    def _():
        site = os.path.join(_HERE, os.pardir, "site")

        def rd(n):
            with open(os.path.join(site, n), encoding="utf-8") as f:
                return json.load(f)
        cards, graph = rd("strings-lean.json"), rd("strings-lean-graph.json")
        return _eq((len(cards), "spine_lines_text" in cards, graph, os.path.basename(OVERLAY)), (21, False, GO_GRAPH, "strings-lean.json"))

    @case("GO3", "a key in both overlay files, or in the Graph overlay and in the base strings, is refused by name `SKEL-OVERLAY-CLASH <key>` (one line per key, sorted), exit 1, nothing written; "
                 "a key in the Cards overlay and in the base strings is NOT a clash (the overlay replaces it, as before); a Graph overlay disjoint from both builds (exit 0)")
    def _():
        with _tmp() as d:
            g, sp, ol = go_setup(d)
            gf = go_file(d, "g.json", GO_GRAPH)
            both = go_run(d, g, sp, ol, "o1", overlay=go_file(d, "co.json", dict(GO_CARDS, **GO_GRAPH)), graph=gf)
            two = go_run(d, g, sp, ol, "o2", overlay=go_file(d, "co2.json", dict(GO_CARDS, **GO_GRAPH)), graph=go_file(d, "g2.json", dict(GO_GRAPH, key_lines_text="x")))
            sp2 = _strings_file(d, dict(_strings(extra=False), **GO_GRAPH), name="s2.json")
            base = go_run(d, g, sp2, ol, "o3", overlay=go_file(d, "c.json", GO_CARDS), graph=gf)
            repl = go_run(d, g, sp, ol, "o4", overlay=go_file(d, "c4.json", dict(GO_CARDS, key_kinds_heading="Replaced")), graph=gf)
        pick = lambda r: (r[0], r[1], r[3])
        return _eq((pick(both), pick(two), pick(base), repl[0], repl[3]),
                   ((1, ["SKEL-OVERLAY-CLASH spine_lines_text"], False), (1, ["SKEL-OVERLAY-CLASH key_lines_text", "SKEL-OVERLAY-CLASH spine_lines_text"], False),
                    (1, ["SKEL-OVERLAY-CLASH spine_lines_text"], False), 0, True))

    @case("GO4", "the Graph overlay is read as the Cards overlay is: a file that is not there, not JSON or not an object is exit 2 and nothing written; a key the page does not read in it is refused by name, "
                 "as for the Cards overlay (`SKEL-OVERLAY-KEY <file> <key> is not a key the page reads`, exit 1, nothing written; case OVK1); the value rules (no value starting `[proposal]` or `[placeholder]`, the word `edge` in none, `{n}` only in the count words) "
                 "are held on the real Graph file by OVL1")
    def _():
        with _tmp() as d:
            g, sp, ol = go_setup(d)
            cards = go_file(d, "c.json", GO_CARDS)
            ok = go_run(d, g, sp, ol, "o0", overlay=cards, graph=go_file(d, "ok.json", GO_GRAPH))
            gone = go_run(d, g, sp, ol, "o1", overlay=cards, graph=os.path.join(d, "nothing.json"))
            bad = go_run(d, g, sp, ol, "o2", overlay=cards, graph=go_file(d, "bad.json", "{x"))
            arr = go_run(d, g, sp, ol, "o3", overlay=cards, graph=go_file(d, "arr.json", "[1]"))
            extra = go_run(d, g, sp, ol, "o4", overlay=cards, graph=go_file(d, "ex.json", dict(GO_GRAPH, bogus="x")))
            extra_c = go_run(d, g, sp, ol, "o5", overlay=go_file(d, "cx.json", dict(GO_CARDS, bogus="x")), graph=go_file(d, "g5.json", GO_GRAPH))
        return _eq((ok[0], (gone[0], gone[3]), (bad[0], bad[3]), (arr[0], arr[3]), (extra[0], extra[1], extra[3]), (extra_c[0], extra_c[1], extra_c[3])),
                   (0, (2, False), (2, False), (2, False), (1, ["SKEL-OVERLAY-KEY ex.json bogus is not a key the page reads"], False),
                    (1, ["SKEL-OVERLAY-KEY cx.json bogus is not a key the page reads"], False)))

    @case("GO5", "the option is a usage error as every other option: twice, or last without a value, is exit 2 with the usage text on stderr and nothing written; once with a value it builds (exit 0); "
                 "the usage text (USAGE and the tool's docstring) names `--strings-overlay-graph`")
    def _():
        with _tmp() as d:
            g, sp, ol = go_setup(d)
            cards, gf = go_file(d, "c.json", GO_CARDS), go_file(d, "g.json", GO_GRAPH)
            ok = go_run(d, g, sp, ol, "o0", overlay=cards, graph=gf)[0]
            twice = _cli(_args(g, os.path.join(d, "o1"), sp, ol, overlay=cards, graph=gf) + ["--strings-overlay-graph", gf])
            novalue = _cli(_args(g, os.path.join(d, "o2"), sp, ol, overlay=cards) + ["--strings-overlay-graph"])
            absent = [os.path.exists(os.path.join(d, n)) for n in ("o1", "o2")]
        return _eq((ok, twice[0], twice[2].startswith("usage:"), novalue[0], novalue[2].startswith("usage:"), absent, "--strings-overlay-graph" in USAGE, "--strings-overlay-graph" in __doc__),
                   (0, 2, True, 2, True, [False, False], True, True))

    DOC_SRC = "\n".join(["/-!", "n", "-/",
                         "/-- Beta opens /- an inner comment -/ and then continues to its real end. -/", "theorem t1 : True := trivial",
                         "/-- Two /- levels /- deep -/ still -/ done. -/", "theorem t2 : True := trivial",
                         "/-- Plain doc. -/", "@[simp]", "theorem t3 : True := trivial", "theorem main : True := trivial", ""])
    DOC_T1 = "/-- Beta opens /- an inner comment -/ and then continues to its real end. -/"
    DOC_T2 = "/-- Two /- levels /- deep -/ still -/ done. -/"
    DOC_T3 = "/-- Plain doc. -/"

    def doc_fixture(d, src=DOC_SRC):
        dec = {"New.t1": decl(3, 0, 4, 28, 4, 8, 2), "New.t2": decl(5, 0, 6, 28, 6, 8, 2), "New.t3": decl(7, 0, 9, 28, 9, 8, 2), "New.main": decl(10, 0, 10, 30, 10, 8, 4)}
        refs = {**mref("New.S.A", "New.t1", (10, 5)), **mref("New.S.A", "New.t2", (10, 10)), **mref("New.S.A", "New.t3", (10, 15))}
        ile = _ilean("New/S/A", refs, decls=[])
        ile["decls"] = dec
        return _tree(d, _flat("A"), {"New/S/A": src}, {"New/S/A": ile}, _index([_srow("`main`", "`New/S/A`", "row")]))

    def source_end(lines, line_no):
        """The doc comment that starts on the 1-based line `line_no` (at its first `/--`), cut at its REAL end by a nesting counter written here, independently of the tool."""
        start_col = lines[line_no - 1].index("/--")
        text = lines[line_no - 1][start_col:] + "\n" + "\n".join(lines[line_no:])
        depth, i = 1, 3
        while i < len(text):
            if text.startswith("/-", i):
                depth += 1
                i += 2
            elif text.startswith("-/", i):
                depth -= 1
                i += 2
                if depth == 0:
                    return text[:i], text[i:i + 12]
            else:
                i += 1
        return None, ""

    @case("DOC1", "a doc comment is carried to its REAL end, nesting of `/-` and `-/` counted by the one counter the module note uses: a doc holding `/- an inner comment -/` is carried whole "
                  "(the full string typed here, byte for byte), so is one with two nested levels, and a plain doc is unchanged; the case asserts that its first fixture holds `/-` before "
                  "its end (so dropping the fixture reddens it); a doc that never closes (its inner comment is closed, its own is not) is `SKEL-KIND <constant> unterminated doc comment`")
    def _():
        assert "/-" in DOC_T1[3:-2] and "/-" in DOC_T2[3:-2]   # the discriminating fact: the fixture docs hold an inner opener before their end
        with _tmp() as d:
            errs, files, rows, rep = bld(doc_fixture(d), PIN, _strings())
        node = _j(files, "graph/spine.json")["nodes"][0]
        got = {m["constant"]: m["doc"]["text"] for m in node["mentions"]}
        bad_src = DOC_SRC.replace(DOC_T1, "/-- never closes /- inner -/")
        with _tmp() as d:
            e2 = bld(doc_fixture(d, bad_src), PIN, _strings())[0]
        return _eq((errs, got, e2), ([], {"New.t1": DOC_T1, "New.t2": DOC_T2, "New.t3": DOC_T3}, [("SKEL-KIND", "New.t1", "unterminated doc comment")]))

    @case("DOC2", "the END of every carried doc comment is checked against the source by a counter run independently in the case: doc.text equals the source from the doc's start line "
                  "through its closing delimiter (nesting counted), ends with `-/`, and what follows in the source is not a continuation of the comment; a doc cut at the first `-/` "
                  "(a PREFIX) or carried past its real end (over the attribute line that follows the last doc) fails it")
    def _():
        assert "/-" in DOC_T1[3:-2]
        with _tmp() as d:
            errs, files, rows, rep = bld(doc_fixture(d), PIN, _strings())
        lines = DOC_SRC.split("\n")
        node = _j(files, "graph/spine.json")["nodes"][0]
        res = []
        for m in node["mentions"]:
            text, after = source_end(lines, m["doc"]["line"])
            res.append((m["doc"]["text"] == text, m["doc"]["text"].endswith("-/"), "/-" in text[3:-2]))
        return _eq((errs, res), ([], [(True, True, True), (True, True, True), (True, True, False)]))

    @case("DOCR", "the real source (give `--selftest --grh DIR --ilean-dir DIR`; otherwise SKIPPED): the 149 doc comments carried in spine.json (the mention entries of the nine rows with a "
                  "doc) are unchanged by the nesting fix (their texts joined with line breaks have the sha256 the previous head's output had) and none of them holds `/-` before "
                  "its closing `-/` (0: the nesting bug is latent on this source); each equals the source from its start line through its real end by the independent counter")
    def _():
        if _GRH_FOR_SK13 is None or _ILEAN_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh and --ilean-dir given to the self-test")
        errs, files, rows, rep = build(_GRH_FOR_SK13, "72fead102f663d5c7a407964a13dc0cf9d977207", _strings(), ilean_dir=_ILEAN_FOR_SK13)
        docs = [m["doc"] for n in _j(files, "graph/spine.json")["nodes"] for m in n["mentions"] if "doc" in m]
        root = os.path.dirname(os.path.abspath(_GRH_FOR_SK13))
        cache, same = {}, 0
        for dc in docs:
            if dc["source"] not in cache:
                with open(os.path.join(root, *dc["source"].split("/")), encoding="utf-8") as f:
                    cache[dc["source"]] = f.read().split("\n")
            text, after = source_end(cache[dc["source"]], dc["line"])
            same += text == dc["text"]
        import hashlib
        return _eq((errs, len(docs), sum(1 for dc in docs if "/-" in dc["text"][3:-2]), same, hashlib.sha256("\n".join(dc["text"] for dc in docs).encode("utf-8")).hexdigest()),
                   ([], 149, 0, 149, "72edd208ea9da8204604c87411d537c6722c00f9631e910c6522e0c422ebf2f6"))

    @case("SPB1", "spine.json has its OWN top-level `edge_basis` = {basis: `reaches-through-any-chain-of-uses`, words: `spine_lines_text`} (exactly those two keys) when the strings carry "
                  "spine_lines_text, none when they do not; the spine's words key is a key of `strings` and is not the index's words key; the index's basis and the spine's are different values")
    def _():
        with _tmp() as d:
            g = sp_files(d, "A", [])
            full = bld(g, PIN, dict(_strings(), **OPTIONAL_WORDS, **LINES_WORDS))[1]
            only_cards = bld(g, PIN, dict(_strings(), key_lines_text="x"))[1]
        sp, ix = _j(full, "graph/spine.json"), _j(full, "graph/index.json")
        eb = sp.get("edge_basis")
        return _eq((eb, sorted(eb), eb["words"] in ix["strings"], eb["words"] != ix["edge_basis"]["words"], eb["basis"] != ix["edge_basis"]["basis"], sorted(sp),
                    "edge_basis" in _j(only_cards, "graph/spine.json"), ix["edge_basis"]),
                   ({"basis": "reaches-through-any-chain-of-uses", "words": "spine_lines_text"}, ["basis", "words"], True, True, True, ["commit", "edge_basis", "format", "links", "nodes"], False, EDGE_BASIS))

    @case("SPB2", "a spine edge basis is checked: one whose words key is the index's (`key_lines_text`) is refused `SKEL-SPINE-BASIS <key>`, one whose basis value is the index's, one with an "
                  "extra key or a missing one likewise, one whose words key is not in the strings `GRAPH-STRINGS <key> missing`; a good one gives no error; planted in a build (the "
                  "constant naming the spine's words key set to `key_lines_text`) the build is refused `SKEL-SPINE-BASIS` and writes nothing")
    def _():
        S = dict(_strings(), **LINES_WORDS)
        good = {"basis": "reaches-through-any-chain-of-uses", "words": "spine_lines_text"}
        chk = lambda eb, s=S: _spine_basis_errors({"edge_basis": eb}, s)
        with _tmp() as d:
            g = sp_files(d, "A", [])
            old = globals()["SPINE_EDGE_WORDS"]
            globals()["SPINE_EDGE_WORDS"] = "key_lines_text"
            try:
                planted = bld(g, PIN, S)
            finally:
                globals()["SPINE_EDGE_WORDS"] = old
        return _eq((chk(good), chk(dict(good, words="key_lines_text")), chk(dict(good, basis=EDGE_BASIS["basis"])), chk(dict(good, extra="x")), chk({"basis": good["basis"]}),
                    chk(dict(good, words="nope")), planted[0], planted[1]),
                   ([], [("SKEL-SPINE-BASIS", "key_lines_text", "is the index's words key")], [("SKEL-SPINE-BASIS", "spine_lines_text", "has the index's basis")],
                    [("SKEL-SPINE-BASIS", "edge_basis", "must have exactly the keys basis and words")], [("SKEL-SPINE-BASIS", "edge_basis", "must have exactly the keys basis and words")],
                    [("GRAPH-STRINGS", "nope", "missing")], [("SKEL-SPINE-BASIS", "key_lines_text", "is the index's words key")], {}))

    @case("INV1", "the invariants of docs/tools.md hold, each checked by name, on a fixture with a spine and mentions: commit equal in index, spine and uses; every link end is a node id; "
                  "every node file is a file step id; a mention's file and spine resolve; counts match; used_by is the exact inverse of uses; titles hold exactly the step ids; the spine's edge_basis words key is a strings key and not the index's")
    def _():
        with _tmp() as d:
            errs, files, rows, rep = bld(mention_fixture(d), PIN, dict(_strings(), **LINES_WORDS))
        inv = invariants(files)
        return _eq((errs, inv), ([], {k: True for k in ("commit", "links", "node file", "mention file", "mention spine", "counts", "used_by", "titles", "spine basis")}))

    @case("INVR", "the real source (give `--selftest --grh DIR --ilean-dir DIR`; otherwise SKIPPED): every invariant holds on the real output; titles has 353 entries: 9 parts, 38 groups, 306 "
                  "files; the first use of New.Parameters in the star_inequality row is [87, 29] (1-based line, 0-based column) and the mention's file key is `file_path`")
    def _():
        if _GRH_FOR_SK13 is None or _ILEAN_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh and --ilean-dir given to the self-test")
        errs, files, rows, rep = build(_GRH_FOR_SK13, "72fead102f663d5c7a407964a13dc0cf9d977207", dict(_strings(), **LINES_WORDS), ilean_dir=_ILEAN_FOR_SK13)
        titles = _j(files, "graph/uses.json")["titles"]
        kinds = {}
        for v in titles.values():
            kinds[v["kind"]] = kinds.get(v["kind"], 0) + 1
        star = [n for n in _j(files, "graph/spine.json")["nodes"] if n["names"][0] == "star_inequality"][0]
        par = [m for m in star["mentions"] if m["constant"] == "New.Parameters"][0]
        return _eq((errs, set(invariants(files).values()), len(titles), kinds, par["first_use"], par["file_path"], "path" in par), ([], {True}, 353, {"part": 9, "group": 38, "file": 306},
                                                                                                                                [87, 29], "grh/src/New/Reduction/Data/FieldsAndPlaces.lean", False))

    @case("MNR", "the real source (give `--selftest --grh DIR --ilean-dir DIR`; otherwise SKIPPED): the direct mentions per row (mentions / in New / without doc), in the table's row order: "
                 "42/38/0, 7/7/1, 15/14/1, 34/32/0, 29/28/1, 8/7/0, 6/6/0, 9/2/1, 4/3/1; 108 distinct declarations with kinds lemma 42, def 30, abbrev 17, theorem 12, structure 6, "
                 "class 1; star_inequality has 29 mentions and its other_constants count includes the structure fields New.Data.logB and New.Data.m; uses.json has 353 titles")
    def _():
        if _GRH_FOR_SK13 is None or _ILEAN_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh and --ilean-dir given to the self-test")
        errs, files, rows, rep = build(_GRH_FOR_SK13, "72fead102f663d5c7a407964a13dc0cf9d977207", _strings(), ilean_dir=_ILEAN_FOR_SK13)
        sp = _j(files, "graph/spine.json")
        per = [(n["counts"]["mentions"], sum(1 for m in n["mentions"] if "file" in m), n["counts"]["no_doc"]) for n in sp["nodes"]]
        allm = {m["constant"]: m["kind"] for n in sp["nodes"] for m in n["mentions"]}
        kinds = {}
        for k in allm.values():
            kinds[k] = kinds.get(k, 0) + 1
        star = [n for n in sp["nodes"] if n["names"][0] == "star_inequality"][0]
        return _eq((errs, per, len(allm), kinds, star["counts"]["mentions"], star["counts"]["other_constants"] >= 2, len(_j(files, "graph/uses.json")["titles"])),
                   ([], [(42, 38, 0), (7, 7, 1), (15, 14, 1), (34, 32, 0), (29, 28, 1), (8, 7, 0), (6, 6, 0), (9, 2, 1), (4, 3, 1)], 108,
                    {"lemma": 42, "def": 30, "abbrev": 17, "theorem": 12, "structure": 6, "class": 1}, 29, True, 353))

    @case("NR1", "note review: the note of EVERY file step has `review` equal to exactly {state: converter} (the converter's rendering, read by no one), the note keys are exactly review, source and text, "
                 "and a part or a group has no note; the review object is a fresh one per note (changing one in the report changes no other)")
    def _():
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n- `New/S/B` (1): b\n"
        with _tmp() as d:
            errs, files, rows, rep = bld(_tree(d, body, {"New/S/A": _lean(), "New/S/B": _lean()}), PIN, _strings())
        notes = {r["id"]: _j(files, f"graph/step/{r['id']}.json").get("note") for r in rows}
        return _eq((errs, {k: (None if v is None else (v["review"], sorted(v))) for k, v in notes.items()},
                    rep["notes"]["lean-s-a"]["review"] is not rep["notes"]["lean-s-b"]["review"]),
                   ([], {"lean-s": None, "lean-s--g": None, "lean-s-a": ({"state": "converter"}, ["review", "source", "text"]), "lean-s-b": ({"state": "converter"}, ["review", "source", "text"])}, True))

    @case("NRR", "the real source (give `--selftest --grh DIR --ilean-dir DIR`; otherwise SKIPPED): all 306 file steps have a note whose review is exactly {state: converter} (306 of 306, no other "
                 "value, no other key in review), the note keys are review, source and text on every one, and no part or group has a note")
    def _():
        if _GRH_FOR_SK13 is None or _ILEAN_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh and --ilean-dir given to the self-test")
        errs, files, rows, rep = build(_GRH_FOR_SK13, "72fead102f663d5c7a407964a13dc0cf9d977207", _strings(), ilean_dir=_ILEAN_FOR_SK13)
        steps = {r["id"]: (r["kind"], _j(files, f"graph/step/{r['id']}.json").get("note")) for r in rows}
        files_n = [n for k, n in steps.values() if k == "file"]
        return _eq((errs, len(files_n), sum(1 for n in files_n if n is not None and n.get("review") == {"state": "converter"}), sorted({tuple(sorted(n)) for n in files_n}),
                    sum(1 for k, n in steps.values() if k != "file" and n is not None)),
                   ([], 306, 306, [("review", "source", "text")], 0))

    def readme_fixture(d, line15, lines=None):
        g = _tree(d, "### S part\n\n**G**\n\n- `New/S/A` (1): a\n", {"New/S/A": _lean()})
        with open(os.path.join(g, "README.md"), "w", encoding="utf-8") as f:
            f.write("\n".join((["filler %d" % i for i in range(14)] if lines is None else lines) + ([line15] if line15 is not None else [])) + "\n")
        return g

    KS_T = 'Scope: "{readme_quote}", and no more.'

    @case("KS1", "key_scope_text: the value of the strings holds `{readme_quote}` and the builder fills it with line 15 of grh/README.md minus its closing colon, read from the file (a second fixture with "
                 "another line 15 gives another text, so the quote is never a constant of the builder), the rest of the value unchanged, the backticks kept; the key is in index.json `strings`; without the key the "
                 "README is not read (none needed) and the key is not there")
    def _():
        out = []
        for line15 in ("`a` and b:", "another line:"):
            with _tmp() as d:
                errs, files, rows, rep = bld(readme_fixture(d, line15), PIN, dict(_strings(), key_scope_text=KS_T))
            ix = _j(files, "graph/index.json")["strings"]
            out.append((errs, ix["key_scope_text"]))
        with _tmp() as d:
            g = _tree(d, "### S part\n\n**G**\n\n- `New/S/A` (1): a\n", {"New/S/A": _lean()})
            os.remove(os.path.join(g, "README.md"))   # no key and no README: the build must not look for one
            errs, files, rows, rep = bld(g, PIN, _strings())
        return _eq((out, errs, "key_scope_text" in _j(files, "graph/index.json")["strings"]),
                   ([([], 'Scope: "`a` and b", and no more.'), ([], 'Scope: "another line", and no more.')], [], False))

    @case("KS2", "key_scope_text refusals (`SKEL-README <what> <reason>`, nothing written): README.md missing (`README.md missing`), a README that is a symlink (`README.md symlink`), fewer than 15 lines "
                 "(`README.md has no line 15`), a line 15 that does not end with a colon (`README.md line 15 does not end with a colon`), and a value without `{readme_quote}` "
                 "(`key_scope_text has no {readme_quote}`), a value with it twice (`key_scope_text has {readme_quote} twice`)")
    def _():
        res = []
        for name, line15, lines in (("ok", "x:", None), ("short", "x:", ["a"] * 5), ("nocolon", "x", None)):
            with _tmp() as d:
                res.append(bld(readme_fixture(d, line15, lines), PIN, dict(_strings(), key_scope_text=KS_T))[:2])
        with _tmp() as d:
            g = _tree(d, "### S part\n\n**G**\n\n- `New/S/A` (1): a\n", {"New/S/A": _lean()})
            os.remove(os.path.join(g, "README.md"))
            res.append(bld(g, PIN, dict(_strings(), key_scope_text=KS_T))[:2])
        with _tmp() as d:
            g = readme_fixture(d, "x:")
            os.rename(os.path.join(g, "README.md"), os.path.join(d, "real.md"))
            os.symlink(os.path.join(d, "real.md"), os.path.join(g, "README.md"))
            res.append(bld(g, PIN, dict(_strings(), key_scope_text=KS_T))[:2])
        for tmpl in ("no placeholder", "{readme_quote} {readme_quote}"):
            with _tmp() as d:
                res.append(bld(readme_fixture(d, "x:"), PIN, dict(_strings(), key_scope_text=tmpl))[:2])
        return _eq([(r[0], r[1] == {}) for r in res[1:]] + [res[0][0]],
                   [([("SKEL-README", "README.md", "has no line 15")], True), ([("SKEL-README", "README.md", "line 15 does not end with a colon")], True),
                    ([("SKEL-README", "README.md", "missing")], True), ([("SKEL-README", "README.md", "symlink")], True),
                    ([("SKEL-README", "key_scope_text", "has no {readme_quote}")], True), ([("SKEL-README", "key_scope_text", "has {readme_quote} twice")], True), []])

    @case("KSR", "the real source (give `--selftest --grh DIR --ilean-dir DIR`; otherwise SKIPPED): with the strings of the Lean map (the wording file and the overlay of this checkout): the overlay's "
                 "key_scope_text is the template (the wording seat's text with `{readme_quote}` where the README is quoted), equal to the literal typed here; "
                 "the built index.json key_scope_text is the text with line 15 of the real grh/README.md minus its colon (read in the case, found once in it, byte for byte), equal to the literal; "
                 "index.json `strings` has 37 keys (the Cards overlay carries no spine_lines_text)")
    def _():
        if _GRH_FOR_SK13 is None or _ILEAN_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh and --ilean-dir given to the self-test")
        with open(os.path.join(_HERE, os.pardir, "site", "strings-lean.json"), encoding="utf-8") as f:
            ov = json.load(f)
        with open(os.path.join(_GRH_FOR_SK13, "README.md"), encoding="utf-8") as f:
            line15 = f.read().split("\n")[14]
        strings = dict(_strings(extra=False), **ov)
        errs, files, rows, rep = build(_GRH_FOR_SK13, "72fead102f663d5c7a407964a13dc0cf9d977207", strings, ilean_dir=_ILEAN_FOR_SK13)
        ix = _j(files, "graph/index.json")["strings"]
        full = ix["key_scope_text"]
        quote = line15[:-1]
        return _eq((errs, "front_scope_line" in ov, ov.get("key_scope_text"), full, line15.endswith(":"), full.count(quote), "{" in full, len(ix),
                    full.replace(quote, "{readme_quote}") == ov["key_scope_text"], bs._strings_problems(strings)),
                   ([], False, SCOPE_TEMPLATE, SCOPE_FULL, True, 1, False, 37, True, []))

    @case("NW1", "the maths-view note words of the Lean map: the overlay of this checkout holds note_label_typeset `The file's opening note, from the repository`, note_typeset_line `Formulas set in "
                 "maths type by us; every symbol is the repository's.`, note_exact_button `Show the exact text` and note_render_button `Show in maths type`, each equal to the literal typed here, with "
                 "no placeholder; a Lean build with the overlay's words carries all four in index.json `strings` with those values; the builder's own check takes each of the four as an optional page "
                 "key (a build that holds only three carries those three: whether the page shows the maths view without all four is the page's rule, not pinned here)")
    def _():
        four = {"note_label_typeset": "The file's opening note, from the repository", "note_typeset_line": "Formulas set in maths type by us; every symbol is the repository's.",
                "note_exact_button": "Show the exact text", "note_render_button": "Show in maths type"}
        with open(os.path.join(_HERE, os.pardir, "site", "strings-lean.json"), encoding="utf-8") as f:
            ov = json.load(f)
        body = "### S part\n\n**G**\n\n- `New/S/A` (1): a\n"
        with _tmp() as d:
            g = _tree(d, body, {"New/S/A": _lean()})
            full = _j(bld(g, PIN, dict(_strings(), **{k: ov[k] for k in four}))[1], "graph/index.json")["strings"]
            three = _j(bld(g, PIN, dict(_strings(), **{k: v for k, v in four.items() if k != "note_render_button"}))[1], "graph/index.json")["strings"]
        return _eq(({k: ov.get(k) for k in four}, {k: full.get(k) for k in four}, sorted(k for k in four if k in three), [k for k in four if "{" in four[k]]),
                   (four, four, sorted(k for k in four if k != "note_render_button"), []))

    @case("KKN1", "key_kinds_note of the Lean map: the overlay of this checkout holds exactly `Parts and groups follow the repository's own contents list (CONTENTS.md); the titles of parts, groups "
                  "and files are copied from it word for word.` (typed here; read back from the file) and a build with it carries that value in index.json `strings`")
    def _():
        want = "Parts and groups follow the repository's own contents list (CONTENTS.md); the titles of parts, groups and files are copied from it word for word."
        with open(os.path.join(_HERE, os.pardir, "site", "strings-lean.json"), encoding="utf-8") as f:
            ov = json.load(f)
        with _tmp() as d:
            g = _tree(d, "### S part\n\n**G**\n\n- `New/S/A` (1): a\n", {"New/S/A": _lean()})
            got = _j(bld(g, PIN, dict(_strings(), key_kinds_note=ov["key_kinds_note"]))[1], "graph/index.json")["strings"]["key_kinds_note"]
        return _eq((ov["key_kinds_note"], got), (want, want))

    def sc_build(d, **kw):
        g = _tree(d, "### S part\n\n**G**\n\n- `New/S/A` (1): a\n", {"New/S/A": _lean()})
        return g, build(g, PIN, _strings(), (), _ildir(g), **kw)

    @case("SC1", "`open_scale_floor`: index.json has the top-level key with the value given (1 is written `1`, not `1.0`; 1.5 is `1.5`; a float written 2.0 stays `2.0`), sorted between "
                 "max_children and rests_on; without the option the key is absent")
    def _():
        out = []
        for v in (None, 1, 1.5, 2.0):
            with _tmp() as d:
                g, res = sc_build(d, open_scale_floor=v)
                raw = res[1]["graph/index.json"].decode("utf-8")
                ix = json.loads(raw)
                out.append((res[0], ix.get("open_scale_floor"), re.findall(r'"open_scale_floor": ([^,\n]*)', raw), raw.find('"max_children"') < raw.find('"open_scale_floor"') < raw.find('"rests_on"')
                            if v is not None else "open_scale_floor" in raw))
        return _eq(out, [([], None, [], False), ([], 1, ["1"], True), ([], 1.5, ["1.5"], True), ([], 2.0, ["2.0"], True)])

    @case("SC2", "anything but a positive finite number is refused `GRAPH-SCALE-FLOOR <value>` and nothing is returned: zero, a negative, nan, inf, a non-numeric text, a bool, an empty "
                 "string, the text `1e400` (a number too large to be finite; the command line names it as given), an integer too large for a float (the number 10**400 as a function argument; the texts of 400 and of 5000 digits on the command line, the second beyond the 4300-digit limit of Python\'s integer parser) (the function), and the same texts on the command line (exit 1, OUT not written); a missing value after the option is exit 2; `1`, `1.5` and `1e3` are accepted "
                 "(and written 1, 1.5 and 1000.0)")
    def _():
        bad = [0, -1, float("nan"), float("inf"), "abc", True, False, "", "1e400", 10 ** 400]
        texts = ("0", "-1", "nan", "inf", "abc", "true", "", "1e400", "-0", "0.0", "1" * 400, "1" * 5000)
        with _tmp() as d:
            g = _tree(d, "### S part\n\n**G**\n\n- `New/S/A` (1): a\n", {"New/S/A": _lean()})
            fn = [(r[0], r[1]) for r in (build(g, PIN, _strings(), (), _ildir(g), open_scale_floor=v) for v in bad)]
            sp, ol = _strings_file(d), _outline_file(d)
            cli = {}
            for i, text in enumerate(texts):
                rc, out, err = _cli(_args(g, os.path.join(d, f"o{i}"), sp, ol) + ["--open-scale-floor", text])
                cli[text] = (rc, out.splitlines(), os.path.exists(os.path.join(d, f"o{i}")))
            miss = _cli(_args(g, os.path.join(d, "om"), sp, ol) + ["--open-scale-floor"])[0]
            ok = {}
            for text in ("1", "1.5", "1e3"):
                o = os.path.join(d, "ok" + text)
                rc = _cli(_args(g, o, sp, ol) + ["--open-scale-floor", text])[0]
                ok[text] = (rc, re.findall(r'"open_scale_floor": ([^,\n]*)', _tree_files(o)["graph/index.json"].decode("utf-8")))
        return _eq((fn, cli, miss, ok),
                   ([([("GRAPH-SCALE-FLOOR", s, "")], {}) for s in ("0", "-1", "nan", "inf", "abc", "True", "False", "", "1e400", str(10 ** 400))],
                    {text: (1, ["GRAPH-SCALE-FLOOR " + text], False) for text in texts}, 2, {"1": (0, ["1"]), "1.5": (0, ["1.5"]), "1e3": (0, ["1000.0"])}))

    @case("SC3", "the output with the option equals the output without it apart from that ONE key of index.json (every other file byte for byte, index.json equal once the key is "
                 "removed), and with the option the files are byte-identical under hash seeds 0 and 1")
    def _():
        with _tmp() as d:
            g, a = sc_build(d)
            runs = []
            for seed in ("0", "1"):
                out = os.path.join(d, "out" + seed)
                r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, out, _strings_file(d), _outline_file(d)) + ["--open-scale-floor", "1"],
                                   env=dict(os.environ, PYTHONHASHSEED=seed), capture_output=True, text=True)
                runs.append((r.returncode, _tree_files(out)))
        with _tmp() as d:
            g, b = sc_build(d, open_scale_floor=1)
        ia, ib = json.loads(a[1]["graph/index.json"]), json.loads(b[1]["graph/index.json"])
        ib.pop("open_scale_floor")
        return _eq((sorted(a[1]) == sorted(b[1]), all(a[1][k] == b[1][k] for k in a[1] if k != "graph/index.json"), ia == ib, runs[0][0], runs[1][0], runs[0][1] == runs[1][1]),
                   (True, True, True, 0, 0, True))

    @case("SCS", "the check of the floor has ONE implementation, the page's (build_site.py): this file defines neither `_scale_floor_error` nor `_scale_from_text` (read from its own syntax tree), has no "
                 "name of either, and calls the page's by lookup: with both of the page's replaced by ones that accept everything, `--open-scale-floor 0` builds (floor 0 written); with the page's own, "
                 "the same texts are refused `GRAPH-SCALE-FLOOR <text>` on this tool's command line exactly as the page's check names them; and the sequence text -> number -> check -> name as typed is the page's "
                 "`_scale_floor_from_text`, the only thing of the page's `_scale*` this file uses (neither primitive, no sequence of its own)")
    def _():
        import ast
        names = ("_scale_floor_error", "_scale_from_text")
        three = names + ("_scale_floor_from_text",)
        with open(os.path.abspath(__file__), encoding="utf-8") as f:
            tree = ast.parse(f.read())
        defined = sorted({n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and n.name in three}
                         | {t.id for n in ast.walk(tree) if isinstance(n, (ast.Assign, ast.AnnAssign)) for t in (n.targets if isinstance(n, ast.Assign) else [n.target])
                            if isinstance(t, ast.Name) and t.id in three})
        used = sorted({n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute) and isinstance(n.value, ast.Name) and n.value.id == "bs" and n.attr.startswith("_scale")})   # what this file takes from the page
        texts = ("0", "-0", "0.0", "-1", "nan", "inf", "-inf", "1e400", "abc", "true", "", "0x1", " 1", "1 ", "+1", "1_0", "\u0661\u0662\u0663", "\uff11", "1" * 400, "1" * 5000)
        real = {n: getattr(bs, n) for n in names}
        with _tmp() as d:
            g = _tree(d, "### S part\n\n**G**\n\n- `New/S/A` (1): a\n", {"New/S/A": _lean()})
            sp, ol = _strings_file(d), _outline_file(d)
            theirs = [bs._scale_floor_error(bs._scale_from_text(t)) != [] for t in texts]
            ours = [_cli(_args(g, os.path.join(d, f"o{i}"), sp, ol) + ["--open-scale-floor", t])[:2] for i, t in enumerate(texts)]
            try:
                bs._scale_floor_error, bs._scale_from_text = (lambda v: []), (lambda t: 0)
                lax = _cli(_args(g, os.path.join(d, "lax"), sp, ol) + ["--open-scale-floor", "0"])[0]
                written = re.findall(r'"open_scale_floor": ([^,\n]*)', _tree_files(os.path.join(d, "lax"))["graph/index.json"].decode("utf-8")) if lax == 0 else None
            finally:
                for n in names:
                    setattr(bs, n, real[n])
        return _eq((defined, [n in globals() for n in three], used, all(theirs), ours, lax, written),
                   ([], [False] * 3, ["_scale_floor_from_text"], True, [(1, "GRAPH-SCALE-FLOOR " + t + "\n") for t in texts], 0, ["0"]))

    @case("SCE", "the `=` form `--open-scale-floor=1` is a usage error like every unknown option: exit 2, nothing on stdout, OUT_DIR not written (the same in build_site.py, OSF4)")
    def _():
        with _tmp() as d:
            g = _tree(d, "### S part\n\n**G**\n\n- `New/S/A` (1): a\n", {"New/S/A": _lean()})
            rc, out, err = _cli(_args(g, os.path.join(d, "o"), _strings_file(d), _outline_file(d)) + ["--open-scale-floor=1"])
            return _eq((rc, out, os.path.exists(os.path.join(d, "o"))), (2, "", False))

    @case("SCR", "the real source (give `--selftest --grh DIR --ilean-dir DIR`; otherwise SKIPPED): the index has `open_scale_floor` 1 when the option is given, and none without")
    def _():
        if _GRH_FOR_SK13 is None or _ILEAN_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh and --ilean-dir given to the self-test")
        pin = "72fead102f663d5c7a407964a13dc0cf9d977207"
        on = build(_GRH_FOR_SK13, pin, _strings(), ilean_dir=_ILEAN_FOR_SK13, open_scale_floor=1)
        off = build(_GRH_FOR_SK13, pin, _strings(), ilean_dir=_ILEAN_FOR_SK13)
        return _eq((on[0], off[0], _j(on[1], "graph/index.json").get("open_scale_floor"), "open_scale_floor" in _j(off[1], "graph/index.json"), len(on[1]), len(off[1])), ([], [], 1, False, 356, 356))

    @case("SK13", "the real source (give `--selftest --grh DIR --ilean-dir DIR`; otherwise SKIPPED): 353 steps (parts 9, groups 38, files 306) with state and proof none, the three cut ids literally, top of 9 in CONTENTS order, widest 23, "
                  "depth 3, 733 links drawn (in-group uses) and 1402 uses not drawn, every id at most 64 characters with exactly 3 cut, the first 3 children of the first group of "
                  "lean-reduction are the first 3 file lines of that group in CONTENTS, the live outline's ids are disjoint from the build's, "
                  "every title (353 of 353, in the rows and in the step files) equals its CONTENTS text byte for byte and 22 of them hold a backtick, and the static check passes on the output")
    def _():
        if _GRH_FOR_SK13 is None or _ILEAN_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh and --ilean-dir given to the self-test")
        with open(os.path.join(_HERE, os.pardir, "outline", "outline.json"), encoding="utf-8") as f:
            live = [g["id"] for g in json.load(f)["groups"]]
        errs, files, rows, rep = build(_GRH_FOR_SK13, "72fead102f663d5c7a407964a13dc0cf9d977207", _strings(), live_ids=live, ilean_dir=_ILEAN_FOR_SK13)
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
                   ([], ORDERS, "column", 0, 27, 23, 353, {"part": 9, "group": 38, "file": 306}, [("none", "none")],
                    ["lean-reduction", "lean-derivatives", "lean-upper-bound", "lean-spanning", "lean-determinant", "lean-one-lift", "lean-congruences", "lean-appendix",
                     "lean-the-last-file"], 23, 3, 733, 1402, 64, 3,
                    ["lean-congruences--lifting-crystalline-extension-classes-i-07869b", "lean-congruences-galois-representations-rows-and-columns-7a36a5",
                     "lean-one-lift--hecke-l-values-as-squared-norms-and-their-25fb42"], True, 3, 356, True, True, 353, 22, []))

    @case("RB1", "structure of the tool above the self-test section (read with `ast` from this file's own text, everything before the self-test header): exactly ONE call of `os.open` and it is in `_read_bounded` "
                 "(no allow-list of other sites), no call of the builtin `open` (the tool's own writes go through build_site's `_publish`, which is another module; the writes of this file's fixtures are "
                 "below the header and are not counted), and no other way to open a file for reading (`io.open`, `Path.open`, `read_text`, `read_bytes`, `os.fdopen`)")
    def _():
        import ast
        with open(os.path.abspath(__file__), encoding="utf-8") as f:
            text = f.read()
        above = text[:text.index("# ---------------------------------------------------------------- self-test")]
        sites = {"os.open": [], "open": [], "other": []}

        def walk(node, fn):
            for child in ast.iter_child_nodes(node):
                name = child.name if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) else fn
                if isinstance(child, ast.Call):
                    f = child.func
                    if isinstance(f, ast.Name) and f.id == "open":
                        sites["open"].append(name)
                    elif isinstance(f, ast.Attribute) and f.attr == "open" and isinstance(f.value, ast.Name) and f.value.id == "os":
                        sites["os.open"].append(name)
                    elif isinstance(f, ast.Attribute) and f.attr in ("open", "read_text", "read_bytes", "fdopen"):
                        sites["other"].append(name)
                walk(child, name)
        walk(ast.parse(above), None)
        return _eq(sites, {"os.open": ["_read_bounded"], "open": [], "other": []})

    ILV_BODY = "### S part\n\n**G**\n\n- `New/S/B` (1): b\n- `New/S/A` (1): a\n"   # B is listed before A: sorted order is not the order of CONTENTS
    MISSING = object()   # a fixture version: the key is removed

    def ilv_ileans(**versions):
        """The .ilean objects of ILV_BODY (key: path as in CONTENTS) with the `version` of each given (MISSING removes the key)."""
        out = {}
        for n in "AB":
            obj = _ilean("New/S/" + n, {})
            if n in versions:
                if versions[n] is MISSING:
                    del obj["version"]
                else:
                    obj["version"] = versions[n]
            out["New/S/" + n] = obj
        return out

    def ilv_build(**versions):
        with _tmp() as d:
            g = _tree(d, ILV_BODY, {"New/S/A": _lean(), "New/S/B": _lean()}, ileans=ilv_ileans(**versions))
            r = bld(g, PIN, _strings())
        return r[0], r[1] == {}

    @case("ILV1", "an .ilean whose `version` is missing or is not exactly the integer 5 (`ILEAN_VERSIONS`) is refused `SKEL-ILEAN-VERSION <path under --ilean-dir> <the value as JSON text, or `missing`>`, nothing written: "
                  "4, 6, the string \"5\" (`\"5\"`), true (`true`), null (`null`), the float 5.0 (`5.0`; 5.0 == 5 in Python, so equality alone would take it) and a missing key (`missing`); a bool is told from an "
                  "int by `type(v) is int` (a bool is an int to isinstance); version 5 builds")
    def _():
        out = {}
        for label, v in (("4", 4), ("6", 6), ("str", "5"), ("true", True), ("null", None), ("5.0", 5.0), ("missing", MISSING), ("5", 5)):
            out[label] = ilv_build(A=v)
        return _eq(out, {"4": ([("SKEL-ILEAN-VERSION", "New/S/A.ilean", "4")], True), "6": ([("SKEL-ILEAN-VERSION", "New/S/A.ilean", "6")], True),
                         "str": ([("SKEL-ILEAN-VERSION", "New/S/A.ilean", '"5"')], True), "true": ([("SKEL-ILEAN-VERSION", "New/S/A.ilean", "true")], True),
                         "null": ([("SKEL-ILEAN-VERSION", "New/S/A.ilean", "null")], True), "5.0": ([("SKEL-ILEAN-VERSION", "New/S/A.ilean", "5.0")], True),
                         "missing": ([("SKEL-ILEAN-VERSION", "New/S/A.ilean", "missing")], True), "5": ([], False)})

    @case("ILV2", "every file with a bad version is reported, sorted by path (not in the order of CONTENTS: B is listed first and A is reported first); a bad version is named before any other fault of the same "
                  "file (a version-4 file whose module is also wrong is `SKEL-ILEAN-VERSION`, not `module-mismatch`) and is reported together with the other faults of the same stage (a missing .ilean); "
                  "on the command line: exit 1, the lines on stdout, OUT_DIR not written")
    def _():
        two = ilv_build(A=4, B="x")
        with _tmp() as d:
            ile = ilv_ileans(A=4)
            ile["New/S/A"]["module"] = "New.S.Other"
            ile["New/S/B"] = None
            g = _tree(d, ILV_BODY, {"New/S/A": _lean(), "New/S/B": _lean()}, ileans=ile)
            both = bld(g, PIN, _strings())[0]
        with _tmp() as d:
            g = _tree(d, ILV_BODY, {"New/S/A": _lean(), "New/S/B": _lean()}, ileans=ilv_ileans(A=4, B=MISSING))
            sp, ol = _strings_file(d), _outline_file(d)
            rc, out, err = _cli(_args(g, os.path.join(d, "out"), sp, ol))
            written = os.path.exists(os.path.join(d, "out"))
        return _eq((two, both, rc, out.splitlines(), "REFUSED" in err, written),
                   (([("SKEL-ILEAN-VERSION", "New/S/A.ilean", "4"), ("SKEL-ILEAN-VERSION", "New/S/B.ilean", '"x"')], True),
                    [("SKEL-USES", "New/S/B", "missing-ilean"), ("SKEL-ILEAN-VERSION", "New/S/A.ilean", "4")], 1,
                    ["SKEL-ILEAN-VERSION New/S/A.ilean 4", "SKEL-ILEAN-VERSION New/S/B.ilean missing"], True, False))

    @case("ILV3", "the other two places an .ilean is loaded check the version too: the index of declared names (`_ilean_index`, which reads every .ilean under --ilean-dir, a file of Lib as well) refuses a "
                  "Lib file of version 6 or with no version, all such files sorted; the spine's file load (`_spine_and_index`, reached on its own here because the uses stage refuses a bad file of New before it) "
                  "refuses the file a spine row names; a Lib file of version 5 builds")
    def _():
        with _tmp() as d:
            ile = ilv_ileans()
            ile["Lib/Z/Y"] = dict(_ilean("Lib/Z/Y", {}), version=6)
            ile["Lib/X/W"] = _ilean("Lib/X/W", {})
            del ile["Lib/X/W"]["version"]
            g = _tree(d, ILV_BODY, {"New/S/A": _lean(), "New/S/B": _lean()}, ileans=ile)
            lib = bld(g, PIN, _strings())[:2]
        with _tmp() as d:
            ile = ilv_ileans()
            ile["Lib/Z/Y"] = _ilean("Lib/Z/Y", {})
            g = _tree(d, ILV_BODY, {"New/S/A": _lean(), "New/S/B": _lean()}, ileans=ile)
            fine = bld(g, PIN, _strings())[0]
        with _tmp() as d:
            g = _tree(d, ILV_BODY, {"New/S/A": _lean(), "New/S/B": _lean()}, ileans=ilv_ileans(A=4), index=_index([_srow("`x`", "`New/S/A`", "c")]))
            spine = _spine_and_index(g, _ildir(g), {"New/S/A": "lean-s-a"}, [], {})
        return _eq((lib, fine, spine),
                   (([("SKEL-ILEAN-VERSION", "Lib/X/W.ilean", "missing"), ("SKEL-ILEAN-VERSION", "Lib/Z/Y.ilean", "6")], {}), [], [("SKEL-ILEAN-VERSION", "New/S/A.ilean", "4")]))

    @case("ILV4", "a bool is not an int for the version check, and a float is not an int: with ILEAN_VERSIONS set to (1,) for the case (the real tuple is (5,), and true == 1 != 5, so on it a "
                  "bool taken as an int would still be refused and the first assertion of ILV1 could not tell), `true` is refused `true`, `1.0` is refused `1.0`, and `1` builds; the tuple is restored")
    def _():
        global ILEAN_VERSIONS
        keep, out = ILEAN_VERSIONS, {}
        ILEAN_VERSIONS = (1,)
        try:
            for label, v in (("true", True), ("1.0", 1.0), ("1", 1)):
                out[label] = ilv_build(A=v, B=v)
        finally:
            ILEAN_VERSIONS = keep
        return _eq((out, ILEAN_VERSIONS),
                   ({"true": ([("SKEL-ILEAN-VERSION", "New/S/A.ilean", "true"), ("SKEL-ILEAN-VERSION", "New/S/B.ilean", "true")], True),
                     "1.0": ([("SKEL-ILEAN-VERSION", "New/S/A.ilean", "1.0"), ("SKEL-ILEAN-VERSION", "New/S/B.ilean", "1.0")], True), "1": ([], False)}, (5,)))

    @case("ILVR", "the real source (give `--selftest --grh DIR --ilean-dir DIR`; otherwise SKIPPED): all 803 .ilean files under --ilean-dir carry `version` 5 (read here, independently of the builder), so the "
                  "real build is not refused by the version check, and `ILEAN_VERSIONS` is (5,)")
    def _():
        if _GRH_FOR_SK13 is None or _ILEAN_FOR_SK13 is None:
            raise _SkipCase("SKIPPED: no --grh and --ilean-dir given to the self-test")
        seen = {}
        for r, _d, fs in os.walk(_ILEAN_FOR_SK13):
            for n in fs:
                if n.endswith(".ilean"):
                    with open(os.path.join(r, n), encoding="utf-8") as f:
                        v = json.load(f).get("version", "missing")
                    seen[repr(v)] = seen.get(repr(v), 0) + 1
        return _eq((seen, ILEAN_VERSIONS), ({"5": 803}, (5,)))

    @case("KSP", "after `{readme_quote}` is filled, a written key_scope_text that carries a placeholder name the format declares for another key (build_site's PLACEHOLDERS, the union of the declared names "
                 "without readme_quote) is refused `SKEL-README key_scope_text placeholder <name>`, nothing written: a README line 15 with `{source}`, with `{n}`, and with both (one line each, sorted); a "
                 "template of the wording seat that itself holds one is refused the same; a line 15 with no placeholder builds")
    def _():
        out = []
        for line15 in ("see {source}:", "{n} files:", "{source} and {n}:", "plain words:"):
            with _tmp() as d:
                r = bld(readme_fixture(d, line15), PIN, dict(_strings(), key_scope_text=KS_T))
            out.append((r[0], r[1] == {}))
        with _tmp() as d:
            r = bld(readme_fixture(d, "x:"), PIN, dict(_strings(), key_scope_text='Scope: "{readme_quote}" in {commit}'))
        out.append((r[0], r[1] == {}))
        return _eq(out, [([("SKEL-README", "key_scope_text", "placeholder source")], True), ([("SKEL-README", "key_scope_text", "placeholder n")], True),
                         ([("SKEL-README", "key_scope_text", "placeholder n"), ("SKEL-README", "key_scope_text", "placeholder source")], True), ([], False),
                         ([("SKEL-README", "key_scope_text", "placeholder commit")], True)])

    @case("KSB", "the README read of key_scope_text is bounded and contained, each reason by its name: a README of exactly the limit (1 MiB) with a good line 15 builds, one byte over is `too-large`; bytes that are "
                 "not UTF-8 are `not-utf-8`; a directory named README.md is `not-a-regular-file`; a FIFO named README.md is `not-a-regular-file` and the build does NOT block (the command line is run as a "
                 "child with a timeout; a hang is reported as such); a README that is a symlink to a file outside grh is `symlink` (also KS2). `outside` is not tested: a README that is not a symlink "
                 "cannot have a real path outside grh, so the reason cannot be reached through the README")
    def _():
        out = {}
        head = "".join("l%d\n" % i for i in range(2, 15))   # lines 2 to 14; line 1 is the filler that brings the file to the limit
        fill = SOURCE_READ_LIMIT - len((head + "ok:\n").encode("utf-8")) - 1
        at_limit = ("z" * fill + "\n" + head + "ok:\n").encode("utf-8")
        assert len(at_limit) == SOURCE_READ_LIMIT
        for label, data in (("at-limit", at_limit), ("over", at_limit + b"z"), ("not-utf-8", (head + "\xff\xfe:\n").encode("latin-1"))):
            with _tmp() as d:
                g = readme_fixture(d, "x:")
                with open(os.path.join(g, "README.md"), "wb") as f:
                    f.write(data)
                r = bld(g, PIN, dict(_strings(), key_scope_text=KS_T))
            out[label] = (r[0], r[1] == {})
        with _tmp() as d:
            g = readme_fixture(d, "x:")
            os.remove(os.path.join(g, "README.md"))
            os.mkdir(os.path.join(g, "README.md"))
            r = bld(g, PIN, dict(_strings(), key_scope_text=KS_T))
        out["directory"] = (r[0], r[1] == {})
        with _tmp() as d:
            g = readme_fixture(d, "x:")
            os.remove(os.path.join(g, "README.md"))
            os.mkfifo(os.path.join(g, "README.md"))
            sp, ol = _strings_file(d, dict(_strings(), key_scope_text=KS_T)), _outline_file(d)
            empty = os.path.join(d, "empty.json")
            with open(empty, "w") as f:
                f.write("{}")
            try:
                r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__)] + _args(g, os.path.join(d, "out"), sp, ol, overlay=empty), capture_output=True, text=True, timeout=30)
                out["fifo"] = (r.returncode, r.stdout.splitlines(), os.path.exists(os.path.join(d, "out")))
            except subprocess.TimeoutExpired:
                out["fifo"] = "HANG"
        with _tmp() as d:
            g = readme_fixture(d, "x:")
            os.rename(os.path.join(g, "README.md"), os.path.join(d, "real.md"))
            os.symlink(os.path.join(d, "real.md"), os.path.join(g, "README.md"))
            r = bld(g, PIN, dict(_strings(), key_scope_text=KS_T))
        out["symlink"] = (r[0], r[1] == {})
        return _eq(out, {"at-limit": ([], False), "over": ([("SKEL-README", "README.md", "too-large")], True), "not-utf-8": ([("SKEL-README", "README.md", "not-utf-8")], True),
                         "directory": ([("SKEL-README", "README.md", "not-a-regular-file")], True), "fifo": (1, ["SKEL-README README.md not-a-regular-file"], False),
                         "symlink": ([("SKEL-README", "README.md", "symlink")], True)})

    @case("ILV5", "the spine's file load reports a file once when two spine rows name it: two rows naming New/S/A, whose version is 4, give ONE `SKEL-ILEAN-VERSION New/S/A.ilean 4` (the file is "
                  "reported, not the row)")
    def _():
        with _tmp() as d:
            g = _tree(d, ILV_BODY, {"New/S/A": _lean(), "New/S/B": _lean()}, ileans=ilv_ileans(A=4),
                      index=_index([_srow("`x`", "`New/S/A`", "c"), _srow("`y`", "`New/S/A`", "d")]))
            spine = _spine_and_index(g, _ildir(g), {"New/S/A": "lean-s-a"}, [], {})
        return _eq(spine, [("SKEL-ILEAN-VERSION", "New/S/A.ilean", "4")])

    @case("OVK1", "a key of --strings-overlay or --strings-overlay-graph that the builder does not copy into index.json `strings` (the page's keys and GRAPH_OPTIONAL_KEYS) is refused by name "
                  "`SKEL-OVERLAY-KEY <overlay file basename> <key> is not a key the page reads`, all such keys reported sorted (by file name, then key), exit 1, OUT_DIR not written: an unknown key in "
                  "the Cards overlay, one in the Graph overlay, two in each (sorted); a key of the optional list and a required key still build; the two overlay files of this checkout build")
    def _():
        with _tmp() as d:
            g, sp, ol = go_setup(d)
            cards = go_file(d, "c.json", GO_CARDS)
            graph = go_file(d, "g.json", GO_GRAPH)
            one_c = go_run(d, g, sp, ol, "o1", overlay=go_file(d, "cx.json", dict(GO_CARDS, bogus="x")), graph=graph)
            one_g = go_run(d, g, sp, ol, "o2", overlay=cards, graph=go_file(d, "gx.json", dict(GO_GRAPH, bogus="x")))
            many = go_run(d, g, sp, ol, "o3", overlay=go_file(d, "cm.json", dict(GO_CARDS, zeta="x", alpha="x")), graph=go_file(d, "gm.json", dict(GO_GRAPH, mid="x", beta="x")))
            known = go_run(d, g, sp, ol, "o4", overlay=cards, graph=graph)
            real = go_run(d, g, sp, ol, "o5", overlay=os.path.join(_HERE, os.pardir, "site", "strings-lean.json"), graph=os.path.join(_HERE, os.pardir, "site", "strings-lean-graph.json"))
        line = lambda f, k: "SKEL-OVERLAY-KEY %s %s is not a key the page reads" % (f, k)
        return _eq(((one_c[0], one_c[1], one_c[3]), (one_g[0], one_g[1], one_g[3]), (many[0], many[1], many[3]), known[0], real[0]),
                   ((1, [line("cx.json", "bogus")], False), (1, [line("gx.json", "bogus")], False),
                    (1, [line("cm.json", "alpha"), line("cm.json", "zeta"), line("gm.json", "beta"), line("gm.json", "mid")], False), 0, 0))

    return cases


def selftest(verbose=True, only=None, grh=None, ilean=None):
    """Run the cases: 0 all pass (a skipped case does not fail), 4 one fails, 2 an unknown id in `only`. `grh` and `ilean` are the folders SK13 reads."""
    global _GRH_FOR_SK13, _ILEAN_FOR_SK13
    cases = _selftest_cases()
    if only is not None:
        bad = [i for i in only if i not in {c[0] for c in cases}]
        if bad or not only:
            print("unknown case id: " + ", ".join(bad) if bad else "no case id given", file=sys.stderr)
            return 2
        cases = [c for c in cases if c[0] in only]
    ok, skipped, before = True, 0, (_GRH_FOR_SK13, _ILEAN_FOR_SK13)
    _GRH_FOR_SK13, _ILEAN_FOR_SK13 = grh, ilean
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
        _GRH_FOR_SK13, _ILEAN_FOR_SK13 = before
    if verbose:
        print("SELFTEST " + ("PASS" if ok else "FAIL") + (f" ({skipped} skipped)" if ok and skipped else ""))
    return 0 if ok else 4


def _selftest_main(rest):
    """`--selftest [--only ID,ID] [--grh DIR] [--ilean-dir DIR]`, in any order, each once."""
    only = grh = ilean = None
    i = 0
    while i < len(rest):
        if rest[i] == "--only" and only is None and i + 1 < len(rest):
            only = [x for x in rest[i + 1].split(",") if x]
        elif rest[i] == "--grh" and grh is None and i + 1 < len(rest):
            grh = rest[i + 1]
        elif rest[i] == "--ilean-dir" and ilean is None and i + 1 < len(rest):
            ilean = rest[i + 1]
        else:
            return 2
        i += 2
    return selftest(only=only, grh=grh, ilean=ilean)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
