#!/usr/bin/env python3
"""The page of the new map: the data tree of the skeleton builder, plus the shell, the engine, the page layer and the stylesheet, plus a manifest, as ONE flat tree.

usage: assemble_grh_site.py --data DIR --pin COMMIT --strings strings.json --shell shell.html --out OUT_DIR [--graph-src DIR]
       assemble_grh_site.py --selftest [--only ID,ID]

PHASE 1 (this file as committed first): the command line, the constants, a STUB `run` and the self-test CASES, written BEFORE the behaviour (contract-first tests). `run` raises
NotImplementedError("phase 2") for a well-formed command line and does nothing else, so every case that reaches the behaviour is RED because the behaviour is absent. Phase 2 writes
`run` against the cases; the nine mutation controls (M-a .. M-i) are written down as exact specifications and are SKIPPED until phase 2 turns each into a live check.

The tool will write, from the data of `build_grh_skeleton.py` (index.json, spine.json, uses.json, step/<id>.json; DATA holds nothing else), the graph assets of `build_site._graph_assets`,
and a page made by `build_site._graph_page`, the tree below, FLAT (the page loads its data and scripts relative to its own address):
    index.html  index.json  spine.json  uses.json  step/<id>.json  engine/...  page/...  graph.css  manifest.json
It never opens OUT_DIR unless every check has passed, writes nothing on a refusal (exit 1, one `ASM-<CODE> <what> <reason>` line per refusal), and imports every function it needs from
build_site.py and build_grh_skeleton.py: it has no second implementation of any of them. The contract is /Users/leishi/luria-desk/assembler-contract-DRAFT.md, clauses A1 to A17
(one self-test case each) and the controls M-a to M-i.

PATH CONVENTION of the refusal lines (the contract writes `<path>` and does not say which; the cases pin this reading): a file or folder INSIDE DATA is named relative to DATA with
`/` (`index.json`, `step/lean-main.json`); `--strings` and `--shell` are named as given on the command line; `ASM-OUT` names OUT_DIR as given; `ASM-ASSET` and `ASM-PAGE` carry the
builder's own words.

THE THREE DEPENDENCIES ON PR C (a separate change to build_site.py by another agent; NOT in this base, and this file does not implement or stub them):
  (a) `_graph_page(shell, assets, strings, about, cards, shell_keys=GRAPH_SHELL_KEYS, section_attrs=())`: `section_attrs` is a tuple of (name, value) pairs written on the
      `<section id="graph-about">`, escaped, in order; a name the allow-list does not permit is a named refusal, never a silent drop; live output byte-identical;
  (b) `data-page-feedback` allowed on `section` in the graph page's element table (`graph_element_problems`);
  (c) `_manifest_bytes(files, commits, counts, release_id=None, archive=None)`, extracted from `_output_files`; the keys release_id and release_archive_sha are OMITTED when None.
A case that needs one of them detects it (`hasattr(bs, "_manifest_bytes")`, the signature of `_graph_page`, `graph_element_problems` on a `section` that carries the attribute) and
reports SKIP with the reason; it never passes and never fails for the want of it.

Exit codes: 0 built, 1 refused (OUT_DIR not created and not touched), 2 usage. --selftest: 0 all pass (a skipped case does not fail), 4 one fails, 2 an unknown id after --only or a bad
self-test command line.
"""
import importlib.util
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    """A module of this folder, loaded by file path (never through sys.path), under a private name (the method of build_grh_skeleton.py)."""
    key = "_asm_grh_" + name
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
sk = _load("build_grh_skeleton")

_FROM_BUILD_SITE = ("_graph_assets", "_graph_sink_errors", "_graph_asset_errors", "_graph_page", "GRAPH_SHELL_KEYS", "_graph_bytes", "_dump", "_sha",
                    "graph_element_problems", "static_problems", "head_meta_problems", "surface_scan")
_FROM_SKELETON = ("_read_in", "_contained")
_UNRESOLVED = [f"build_site.{n}" for n in _FROM_BUILD_SITE if not hasattr(bs, n)] + [f"build_grh_skeleton.{n}" for n in _FROM_SKELETON if not hasattr(sk, n)]
if _UNRESOLVED:   # something the contract imports cannot be imported as it stands: stop, never copy it
    raise ImportError("assemble_grh_site: cannot import " + ", ".join(_UNRESOLVED))
_graph_assets, _graph_sink_errors, _graph_asset_errors, _graph_page, GRAPH_SHELL_KEYS, _graph_bytes, _dump, _sha = (getattr(bs, n) for n in _FROM_BUILD_SITE[:8])
graph_element_problems, static_problems, head_meta_problems, surface_scan = (getattr(bs, n) for n in _FROM_BUILD_SITE[8:])
_read_in, _contained = sk._read_in, sk._contained   # not used yet: phase 2

TOP_READ_LIMIT = 4 * 1024 * 1024    # index.json, spine.json, uses.json, the strings file, the shell: the most bytes of each read (A1)
STEP_READ_LIMIT = 1024 * 1024       # one step file (A1)
MAX_STEP_FILES = 2000               # the most step files (A1)
DATA_FIXED = ("index.json", "spine.json", "uses.json")   # DATA holds these, step/<id>.json, and nothing else (A2)
ABOUT_KEY = "about_text"            # the strings key whose text fills #graph-about (contract, Open 3: the default; `ASM-STRINGS about_text missing` when absent)
SCOPE_KEY = "front_scope_line"      # the shell key PR C lets the page carry besides GRAPH_SHELL_KEYS (A7)
PAGE_SECTION_ATTRS = (("data-page-feedback", "off"),)   # A7, A8
CODES = ("ASM-DATA", "ASM-PIN", "ASM-OUT", "ASM-ASSET", "ASM-SINK", "ASM-PAGE", "ASM-STRINGS")   # the codes of a refusal line: `<CODE> <what> <reason>`
DATA_REASONS = ("symlink", "not-regular", "too-large", "encoding", "unexpected", "missing")   # the reasons of ASM-DATA

_OPTIONS = ("--data", "--pin", "--strings", "--shell", "--out", "--graph-src")
_PIN = re.compile(r"[0-9a-f]{40}")
USAGE = ("usage: assemble_grh_site.py --data DIR --pin COMMIT --strings strings.json --shell shell.html --out OUT_DIR [--graph-src DIR]\n"
         "       assemble_grh_site.py --selftest [--only ID,ID]")


def _parse(a):
    """{data, pin, strings, shell, out, graph-src} or None: each option once, with a value; --pin a 40-hex string (lower case); nothing else; --graph-src defaults to build_site.GRAPH_SRC."""
    opts, i = {}, 0
    while i < len(a):
        if a[i] in _OPTIONS and a[i][2:] not in opts and i + 1 < len(a):
            opts[a[i][2:]] = a[i + 1]
            i += 2
        else:
            return None
    if not {"data", "pin", "strings", "shell", "out"} <= set(opts) or not _PIN.fullmatch(opts["pin"]):
        return None
    opts.setdefault("graph-src", bs.GRAPH_SRC)
    return opts


def run(opts):
    """PHASE 1 STUB: the behaviour of A1 to A17 is not written. Phase 2 replaces this body."""
    raise NotImplementedError("phase 2")


def main(argv):
    """argv with the program name first."""
    if argv[1:2] == ["--selftest"]:
        return _selftest_main(argv[2:])
    opts = _parse(argv[1:])
    if opts is None:
        print(USAGE, file=sys.stderr)
        return 2
    return run(opts)


# ==== self-test ====
# Everything above this marker is the tool; everything below is the self-test. Case A16 reads the text above the marker (and only that) for anything that could execute what the tool reads.
import ast
import hashlib
import inspect
import json
import shutil
import subprocess
import tempfile
from html.parser import HTMLParser


class _SkipCase(Exception):
    pass


class _Absent(Exception):
    """The stub answered NotImplementedError("phase 2"): the case is red because the behaviour is not written, and for no other reason."""


class _FixtureError(Exception):
    """A fixture of the self-test is not what it claims to be (a bug of the case, never a finding about the tool)."""


TOOL = os.path.abspath(__file__)
PIN = "0123456789abcdef0123456789abcdef01234567"
BAD_PIN = "f" * 40
BAD_PIN_2 = "e" * 40


def _eq(actual, expected):
    return actual == expected, f"expected {expected!r}, got {actual!r}"


def _tmp():
    return tempfile.TemporaryDirectory(prefix="grh-asm-")


# ---------------------------------------------------------------- fixtures: every one is built in a temp folder from literals and from the skeleton builder's own machinery

SMALL_BODY = "### The last file\n\n- `New/Main` (1): From non-vanishing in Re s > 1/2 to zeros on the critical line\n"   # builds exactly the smallest step file of the real data
SMALL_SRCS = {"New/Main": sk._lean()}
TEMPLATE_STEP = ('{"card":{"child_count":1,"child_kind":"file","id":"lean-the-last-file","kind":"part","path":[],"proof":"none","state":"none","title":"The last file"},'
                 '"children":[{"child_count":0,"id":"lean-main","kind":"file","parent_rests_on":false,"path":["lean-the-last-file"],"proof":"none","state":"none",'
                 '"title":"From non-vanishing in Re s > 1/2 to zeros on the critical line"}],"commit":"72fead102f663d5c7a407964a13dc0cf9d977207","format":1,'
                 '"id":"lean-the-last-file","path":[],"rests_on":[]}')   # the smallest step file of the real data (the template of every extra step file below)
INDEX_KEYS = ["assets", "commit", "edge_basis", "format", "max_children", "rests_on", "sibling_layout", "steps", "strings", "symbols", "top"]   # the keys of the real index.json

GRAPH_SRC_FILES = {"engine/index.js": b"export const engine = 1;\n", "page/app.js": b"export const page = 2;\n", "graph.css": b"body { margin: 0; }\n"}   # scanner-clean, and NO .html

SHELL = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>{{S:title}}</title>
<link rel="stylesheet" href="graph.css">
</head>
<body>
<header class="intro">
<h1>{{S:title}}</h1>
<p class="sentence">{{S:sentence}}</p>
<p class="links"><button type="button" id="graph-about-open" class="linkbtn">{{S:about_link}}</button><span class="hint">{{S:tap_hint}}</span></p>
</header>
<div id="graph-layer" hidden>
<nav class="toolbar">
<span class="seg"><span class="seg-here">{{S:map}}</span></span>
<button type="button" id="graph-show-all" class="tool">{{S:show_all}}</button>
<button type="button" id="graph-key" class="tool">{{S:key}}</button>
</nav>
<div id="graph" class="stage"></div>
<aside id="graph-sheet" class="graph-sheet" role="dialog" hidden>
<div class="sheet-bar"><div id="graph-crumbs" class="crumb-slot"></div><button type="button" id="graph-sheet-close" class="tool">{{S:close}}</button><div id="graph-sheet-tools" class="sheet-tools"></div></div>
<div id="graph-sheet-body" class="graph-sheet-body"></div>
</aside>
</div>
<div id="graph-fallback" class="fallback">
<p>{{S:fallback_sentence}}</p>
</div>
<p id="graph-notice" class="notice" role="status" hidden></p>
<div id="graph-cards" class="cards">
{{CARDS}}
</div>
<script type="module" src="page/app.js"></script>
</body>
</html>
"""   # the live viewer/graph/shell.html minus its two `list/` links and the engine.css link (this graph-src stand-in has no engine.css)
SHELL_SCOPE = SHELL.replace('<p class="sentence">{{S:sentence}}</p>\n', '<p class="sentence">{{S:sentence}}</p>\n<p class="sentence">{{S:front_scope_line}}</p>\n')   # the variant that holds the PR C key
ABOUT_TEXT = "About this map: one plain sentence."
SCOPE_TEXT = "Scope: the Lean files of the last step."


def _skel_strings():
    """The strings the skeleton build used for the fixtures: the repository's own strings, the overlay words, the lines words and the note words."""
    return dict(sk._strings(), **sk.OPTIONAL_WORDS, **sk.LINES_WORDS, **sk.NOTE_WORDS)


def _asm_strings(**over):
    """The `--strings` file of the assembler: the skeleton strings plus the keys the contract needs (about_text, front_scope_line; root_only_note_single is in the repository's own file)."""
    s = dict(_skel_strings(), **{ABOUT_KEY: ABOUT_TEXT, SCOPE_KEY: SCOPE_TEXT})
    s.update(over)
    return {k: v for k, v in s.items() if v is not None}


def _data_files(pin=PIN, big=False):
    """{relative name: bytes} of a DATA tree in the REAL shape, made by the skeleton builder (`sk.bld`) from a literal CONTENTS tree: the smallest (2 steps, the real template) or, with `big`, 11 steps."""
    body, srcs = (sk.SK1_BODY, sk.SK1_SRCS) if big else (SMALL_BODY, SMALL_SRCS)
    with _tmp() as t:
        errs, files, _rows, _rep = sk.bld(sk._tree(t, body, srcs), pin, _skel_strings())
    if errs:
        raise _FixtureError(f"the skeleton builder refused the fixture: {errs[:3]}")
    out = {k[len("graph/"):]: v for k, v in files.items()}
    ix = json.loads(out["index.json"])
    if sorted(ix) != INDEX_KEYS:
        raise _FixtureError(f"the fixture index.json has the keys {sorted(ix)}, the real one has {INDEX_KEYS}")
    if not big:
        want = dict(json.loads(TEMPLATE_STEP), commit=pin)
        if json.loads(out["step/lean-the-last-file.json"]) != want:
            raise _FixtureError("the fixture step file is not the real template with the commit changed")
    return out


def _step_bytes(step_id, commit):
    """An extra step file: the real template, with only id and commit changed, serialised by the builder's own writer."""
    obj = dict(json.loads(TEMPLATE_STEP), id=step_id, commit=commit)
    obj["card"] = dict(obj["card"], id=step_id)
    return _graph_bytes({"step/x.json": obj})["step/x.json"]


def _recommit(data, commit):
    """The same JSON file with only its `commit` changed, in the builder's serialisation."""
    obj = json.loads(data.decode("utf-8"))
    obj["commit"] = commit
    return _graph_bytes({"x.json": obj})["x.json"]


def _write_tree(root, files):
    for rel, data in files.items():
        p = os.path.join(root, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def _read_tree(root):
    """{relative path: bytes} of every file under root (`/` separated), and the list of folders that hold nothing."""
    res, empty = {}, []
    for r, dirs, fs in os.walk(root):
        if not dirs and not fs and os.path.abspath(r) != os.path.abspath(root):
            empty.append(os.path.relpath(r, root).replace(os.sep, "/"))
        for n in fs:
            p = os.path.join(r, n)
            with open(p, "rb") as f:
                res[os.path.relpath(p, root).replace(os.sep, "/")] = f.read()
    return res, empty


def _world(d, big=False, scope=False, strings=None, shell=None, pin=PIN):
    """The paths of one case: a DATA tree, a graph-src stand-in, a shell stand-in, a strings file, and an OUT_DIR that does not exist. Checks its own fixtures (a bad one is a _FixtureError)."""
    w = {k: os.path.join(d, v) for k, v in (("data", "data"), ("gsrc", "gsrc"), ("shell", "shell.html"), ("strings", "strings.json"), ("out", "out"))}
    w["files"] = _data_files(pin, big)
    _write_tree(w["data"], w["files"])
    _write_tree(w["gsrc"], GRAPH_SRC_FILES)
    with open(w["shell"], "w", encoding="utf-8") as f:
        f.write(SHELL_SCOPE if scope else SHELL if shell is None else shell)
    with open(w["strings"], "w", encoding="utf-8") as f:
        json.dump(_asm_strings() if strings is None else strings, f)
    errs, assets, shell_in_src = _graph_assets(w["gsrc"])
    if errs or sorted(assets) != sorted(GRAPH_SRC_FILES) or shell_in_src is not None:
        raise _FixtureError(f"the graph-src stand-in is not clean: {errs} {sorted(assets)} {shell_in_src}")
    w["assets"] = assets
    return w


def _argv(w, pin=PIN, drop=(), **over):
    pairs = [("--data", w["data"]), ("--pin", pin), ("--strings", w["strings"]), ("--shell", w["shell"]), ("--out", w["out"]), ("--graph-src", w["gsrc"])]
    return [x for k, v in pairs if k not in drop for x in (k, over.get(k[2:], v))]


def _cli(argv, env=None, cwd=None, preexec=None):
    """(exit code, stdout lines, stderr) of the tool run in a SUBPROCESS (`-I`, 60 s timeout: a tool that blocks on a FIFO fails the case, it does not hang the self-test).
    The stub's NotImplementedError is `_Absent`: the case is red because the behaviour is absent."""
    r = subprocess.run([sys.executable, "-I", TOOL] + argv, capture_output=True, text=True, timeout=60, env=env, cwd=cwd, preexec_fn=preexec)
    if "NotImplementedError: phase 2" in r.stderr:
        raise _Absent("behaviour absent: the stub raised NotImplementedError('phase 2')")
    return r.returncode, r.stdout.splitlines(), r.stderr


def _refused(w, argv, want, what, out_state="absent"):
    """(ok, why): the run exits 1 with exactly the lines `want` (compared as sorted lists: the order of lines is only A13's business), no traceback, and OUT_DIR as it was."""
    rc, lines, err = _cli(argv)
    state = "absent" if not os.path.exists(w["out"]) else sorted(os.listdir(w["out"]))
    ok, why = _eq((rc, sorted(lines), "Traceback" in err, state), (1, sorted(want), False, out_state))
    return ok, f"{what}: {why}"


def _refused_like(w, argv, check, what):
    """(ok, why): the run exits 1, every stdout line is an ASM- line, `check(lines)` is true, OUT_DIR is absent. For a refusal whose exact words the contract does not give."""
    rc, lines, err = _cli(argv)
    good = rc == 1 and bool(lines) and all(ln.split(" ", 1)[0] in CODES for ln in lines) and "Traceback" not in err and not os.path.exists(w["out"]) and check(lines)
    return good, f"{what}: exit {rc}, lines {lines!r}, absent {not os.path.exists(w['out'])}, stderr {err[-200:]!r}"


def _step_names(files):
    return sorted(k for k in files if k.startswith("step/"))


def _pr_c_gaps():
    gaps = []
    if not hasattr(bs, "_manifest_bytes"):
        gaps.append("build_site._manifest_bytes")
    params = inspect.signature(bs._graph_page).parameters
    gaps += [f"build_site._graph_page(..., {p}=)" for p in ("shell_keys", "section_attrs") if p not in params]
    if bs.graph_element_problems('<section data-page-feedback="off"></section>'):
        gaps.append("data-page-feedback allowed on section")
    return gaps


def _need_pr_c():
    gaps = _pr_c_gaps()
    if gaps:
        raise _SkipCase("needs PR C, which is not in this base: " + ", ".join(gaps))


def _ok_run(w, argv=None, **kw):
    """Run the tool on a world that must build; returns the tree it wrote ({rel: bytes}, no empty folders asserted here)."""
    rc, lines, err = _cli(_argv(w) if argv is None else argv, **kw)
    if rc != 0 or len(lines) != 1 or err:
        raise AssertionError(f"a clean world must build: exit {rc}, stdout {lines!r}, stderr {err[-300:]!r}")
    return _read_tree(w["out"])


def _expected_page(w, shell_text, strings):
    """The page the builder's own function makes (the contract's A7 call), for the comparison of the written index.html."""
    errs, page = _graph_page(shell_text.encode("utf-8"), set(w["assets"]), strings, bs._e(strings[ABOUT_KEY]), "",
                             shell_keys=GRAPH_SHELL_KEYS + (SCOPE_KEY,), section_attrs=PAGE_SECTION_ATTRS)
    if errs:
        raise _FixtureError(f"the builder refuses the fixture page: {errs}")
    return page


def _limit_writes(n):
    """A preexec function: no file of the child may exceed n bytes (SIGXFSZ ignored, so a write fails with EFBIG instead of killing the child)."""
    def f():
        import resource
        import signal
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        resource.setrlimit(resource.RLIMIT_FSIZE, (n, n))
    return f


# ---------------------------------------------------------------- the mutation controls: exact specifications, for phase 2 to turn into live checks

CLAUSES = tuple(f"A{i}" for i in range(1, 18))
MUTATIONS = {
    "M-a": ("A3", "in the pin stage, skip the comparison of `commit` with --pin for every step/<id>.json (index.json, spine.json and uses.json are still compared)", ("A3",)),
    "M-b": ("A1", "in the data stage, read a step/<id>.json that is a symlink as if it were a regular file (follow it; no `symlink` refusal for it). Every other symlink refusal "
                  "(index/spine/uses, folders, --strings, --shell) is unchanged", ("A1",)),
    "M-c": ("A9", "write index.json with the right `assets` but through `json.dumps({**{k: v for k, v in obj.items() if k != 'assets'}, 'assets': new_assets}, indent=1, "
                  "ensure_ascii=False) + '\\n'` (`assets` LAST, no sort_keys, no `_graph_bytes`, so no \\u003c escapes): the parsed object is the same, its key order and bytes are not", ("A9",)),
    "M-d": ("A12", "build the manifest `files` map from every written file EXCEPT index.html", ("A12",)),
    "M-e": ("A12", "write the manifest with `\"release_id\": null` present (build the manifest object by hand with release_id None instead of omitting the key)", ("A12",)),
    "M-f": ("A13", "list the step files (for reading and for the order of the refusal lines) in ascending st_mtime order instead of sorted by name", ("A13",)),
    "M-g": ("A4", "skip the not-empty check: a non-empty OUT_DIR is written into, no `ASM-OUT <path> not-empty`", ("A4",)),
    "M-h": ("A7", "call `_graph_page` with `section_attrs=()` so the section carries no `data-page-feedback`", ("A7", "A8")),
    "M-i": ("A5", "take the shell bytes from the third return value of `_graph_assets(graph_src)` when it is not None (and from --shell only when it is None)", ("A5",)),
}


def _mutation_case(mid):
    primary, change, red = MUTATIONS[mid]
    green = tuple(c for c in CLAUSES if c not in red)
    bad = [c for c in red if c not in CLAUSES]
    if bad or primary not in red or not red or set(red) | set(green) != set(CLAUSES):
        return False, f"the specification of {mid} is malformed: {bad}"
    raise _SkipCase(f"phase 2 turns this into a live check. WRONG IMPLEMENTATION: {change}. MUST GO RED (and only these): {', '.join(red)}. MUST STAY GREEN: {', '.join(green)}")


# ---------------------------------------------------------------- the cases

def _selftest_cases():
    cases = []

    def case(cid, desc):
        def deco(fn):
            cases.append((cid, desc, fn))
            return fn
        return deco

    @case("A1", "inputs are read bounded and contained: --data, --strings and --shell are read through one descriptor opened O_NOFOLLOW|O_NONBLOCK, fstat-checked regular, at most the limit "
                "plus one byte (4 MiB index/spine/uses/strings/shell, 1 MiB a step file, at most 2000 step files); a symlink (file or folder, anywhere under DATA), a FIFO, a directory where a "
                "file is expected, a file over its limit, bytes that are not UTF-8 are `ASM-DATA <path> symlink|not-regular|too-large|encoding`, all reported, exit 1, OUT_DIR not created; a "
                "file of exactly the limit is read; a FIFO never hangs (the CLI runs in a subprocess with a 60 s timeout)")
    def _():
        step_limit = STEP_READ_LIMIT
        with _tmp() as d:   # 1: every fault of the read kind in one run, all reported
            w = _world(d, big=True)
            outside = os.path.join(d, "outside.json")
            with open(outside, "w") as f:
                f.write("{}")
            s_sym, s_enc, s_big = _step_names(w["files"])[:3]
            for rel in (s_sym, "spine.json", "uses.json"):
                os.remove(os.path.join(w["data"], rel))
            os.symlink(outside, os.path.join(w["data"], s_sym))
            os.mkdir(os.path.join(w["data"], "spine.json"))
            os.mkfifo(os.path.join(w["data"], "uses.json"))
            _write_tree(w["data"], {s_enc: b"\xff\xfe", s_big: b"x" * (step_limit + 1), "index.json": b" " * (TOP_READ_LIMIT + 1)})
            good, why = _refused(w, _argv(w), ["ASM-DATA index.json too-large", "ASM-DATA spine.json not-regular", "ASM-DATA uses.json not-regular", f"ASM-DATA {s_sym} symlink",
                                              f"ASM-DATA {s_enc} encoding", f"ASM-DATA {s_big} too-large"], "every read fault of DATA in one run")
            if not good:
                return good, why
        with _tmp() as d:   # 2: --strings a symlink, --shell a FIFO: named as given
            w = _world(d)
            real = w["strings"] + ".real"
            os.rename(w["strings"], real)
            os.symlink(real, w["strings"])
            os.remove(w["shell"])
            os.mkfifo(w["shell"])
            good, why = _refused(w, _argv(w), [f"ASM-DATA {w['strings']} symlink", f"ASM-DATA {w['shell']} not-regular"], "--strings a symlink and --shell a FIFO")
            if not good:
                return good, why
        with _tmp() as d:   # 3: a symlinked FOLDER anywhere under DATA (the root, and inside step/)
            w = _world(d)
            elsewhere = os.path.join(d, "elsewhere")
            os.mkdir(elsewhere)
            os.symlink(elsewhere, os.path.join(w["data"], "extra"))
            os.symlink(elsewhere, os.path.join(w["data"], "step", "sub"))
            good, why = _refused_like(w, _argv(w), lambda ls: "ASM-DATA extra symlink" in ls and "ASM-DATA step/sub symlink" in ls and all(ln.startswith("ASM-DATA ") for ln in ls),
                                      "a symlinked folder under DATA")
            if not good:
                return good, why
        with _tmp() as d:   # 4: the step/ folder itself a symlink to a folder that holds the real step files: never followed
            w = _world(d)
            real = os.path.join(d, "real-step")
            os.rename(os.path.join(w["data"], "step"), real)
            os.symlink(real, os.path.join(w["data"], "step"))
            good, why = _refused_like(w, _argv(w), lambda ls: "ASM-DATA step symlink" in ls and all(ln.startswith("ASM-DATA ") for ln in ls), "the step folder a symlink")
            if not good:
                return good, why
        with _tmp() as d:   # 5: a step file of exactly the limit is READ (its `id` that is not its file name is then a refusal of the pin stage, not a data refusal)
            w = _world(d)
            rel = _step_names(w["files"])[0]
            raw = json.dumps(dict(json.loads(w["files"][rel]), id="lean-other")).encode("utf-8")
            _write_tree(w["data"], {rel: raw + b" " * (step_limit - len(raw))})
            if os.path.getsize(os.path.join(w["data"], rel)) != step_limit:
                raise _FixtureError("the padded step file is not exactly the limit")
            good, why = _refused_like(w, _argv(w), lambda ls: len(ls) == 1 and rel in ls[0] and not ls[0].startswith("ASM-DATA "), "a step file of exactly 1 MiB is read")
            if not good:
                return good, why
        with _tmp() as d:   # 6: more than 2000 step files: refused as a DATA fault (the reason word of this one is not in the contract)
            w = _world(d)
            _write_tree(w["data"], {f"step/lean-x{i:04d}.json": _step_bytes(f"lean-x{i:04d}", PIN) for i in range(MAX_STEP_FILES - 1)})
            n = len(os.listdir(os.path.join(w["data"], "step")))
            if n != MAX_STEP_FILES + 1:
                raise _FixtureError(f"{n} step files, wanted {MAX_STEP_FILES + 1}")
            return _refused_like(w, _argv(w), lambda ls: all(ln.startswith("ASM-DATA ") for ln in ls), "2001 step files")
        return True, ""

    @case("A2", "exactly the data set: DATA holds index.json, spine.json, uses.json and step/<id>.json and nothing else (an extra file or folder: `ASM-DATA <path> unexpected`; a missing "
                "one: `ASM-DATA <path> missing`); step ids are slugs, the file name is the id plus .json; every fault of the stage is reported together")
    def _():
        with _tmp() as d:
            w = _world(d)
            _write_tree(w["data"], {"notes.txt": b"x", "step/readme.txt": b"x"})
            os.mkdir(os.path.join(w["data"], "extra"))
            os.mkdir(os.path.join(w["data"], "step", "sub"))
            os.remove(os.path.join(w["data"], "uses.json"))
            good, why = _refused(w, _argv(w), ["ASM-DATA notes.txt unexpected", "ASM-DATA extra unexpected", "ASM-DATA step/readme.txt unexpected", "ASM-DATA step/sub unexpected",
                                              "ASM-DATA uses.json missing"], "extra files and folders and a missing file, all reported")
            if not good:
                return good, why
        with _tmp() as d:
            w = _world(d)
            os.remove(os.path.join(w["data"], "index.json"))
            os.remove(os.path.join(w["data"], "spine.json"))
            good, why = _refused(w, _argv(w), ["ASM-DATA index.json missing", "ASM-DATA spine.json missing"], "two missing files")
            if not good:
                return good, why
        with _tmp() as d:
            w = _world(d)
            _write_tree(w["data"], {"step/Bad_Id.json": _step_bytes("lean-bad", PIN)})
            return _refused_like(w, _argv(w), lambda ls: any(ln.startswith("ASM-DATA step/Bad_Id.json ") for ln in ls), "a step file whose id is not a slug")

    @case("A3", "the pin: index.json, spine.json, uses.json and every step file carry `commit` equal to --pin; otherwise `ASM-PIN <file> <found>` naming each file that differs, exit 1, "
                "nothing written; every step file's `id` equals its file name; index.json `steps` equals the number of step files")
    def _():
        with _tmp() as d:
            w = _world(d, big=True)
            steps = _step_names(w["files"])
            bad_step = steps[3]
            _write_tree(w["data"], {"index.json": _recommit(w["files"]["index.json"], BAD_PIN), "spine.json": _recommit(w["files"]["spine.json"], BAD_PIN_2),
                                    "uses.json": _recommit(w["files"]["uses.json"], BAD_PIN), bad_step: _recommit(w["files"][bad_step], BAD_PIN_2)})
            good, why = _refused(w, _argv(w), [f"ASM-PIN index.json {BAD_PIN}", f"ASM-PIN spine.json {BAD_PIN_2}", f"ASM-PIN uses.json {BAD_PIN}", f"ASM-PIN {bad_step} {BAD_PIN_2}"],
                                 "a wrong commit in index, spine, uses and ONE step file: exactly those four, each with the value found")
            if not good:
                return good, why
        with _tmp() as d:
            w = _world(d)
            rel = _step_names(w["files"])[0]
            obj = dict(json.loads(w["files"][rel]), id="lean-other")
            _write_tree(w["data"], {rel: _graph_bytes({"x": obj})["x"]})
            good, why = _refused_like(w, _argv(w), lambda ls: len(ls) == 1 and rel in ls[0], "a step file whose `id` is not its file name (one line naming the file)")
            if not good:
                return good, why
        with _tmp() as d:
            w = _world(d)
            obj = dict(json.loads(w["files"]["index.json"]), steps=len(_step_names(w["files"])) + 1)
            _write_tree(w["data"], {"index.json": _graph_bytes({"x": obj})["x"]})
            return _refused_like(w, _argv(w), lambda ls: len(ls) == 1 and "index.json" in ls[0], "index.json `steps` not the number of step files (one line naming index.json)")

    @case("A4", "EMPTY OUT: OUT_DIR is created by the tool and must NOT exist, or must exist and be empty; a non-empty OUT_DIR is `ASM-OUT <path> not-empty`, exit 1, nothing written "
                "(its files untouched); writes go to files inside OUT_DIR only (nothing is left beside it). A name with `..` or a leading `/` (`ASM-OUT <name> name`) cannot be reached "
                "from the command line, because every name comes from a source that is already checked, so no case drives it")
    def _():
        _need_pr_c()
        with _tmp() as d:
            w = _world(d)
            tree, _empty = _ok_run(w)
            if sorted(os.listdir(d)) != sorted(["data", "gsrc", "shell.html", "strings.json", "out"]) or not tree:
                return False, f"an absent OUT_DIR: wrote {sorted(os.listdir(d))}"
        with _tmp() as d:
            w = _world(d)
            os.mkdir(w["out"])
            if not _ok_run(w)[0]:
                return False, "an existing empty OUT_DIR was not written"
        with _tmp() as d:
            w = _world(d)
            os.mkdir(w["out"])
            _write_tree(w["out"], {"keep.txt": b"mine", "sub/keep2.txt": b"also mine"})
            before = _read_tree(w["out"])
            rc, lines, err = _cli(_argv(w))
            return _eq((rc, lines, "Traceback" in err, _read_tree(w["out"]) == before), (1, [f"ASM-OUT {w['out']} not-empty"], False, True))

    @case("A5", "assets by the builder's own function: `_graph_assets(graph_src)` supplies the assets; its errors are `ASM-ASSET <path> <reason>` (the function's own reasons) and stop the "
                "run; the shell is the file read through --shell, NOT the shell `_graph_assets` returns; an absent or empty asset set is `ASM-ASSET graph no-assets`")
    def _():
        with _tmp() as d:
            w = _world(d)
            os.symlink(os.path.join(w["gsrc"], "graph.css"), os.path.join(w["gsrc"], "engine", "link.js"))
            _write_tree(w["gsrc"], {"extra.html": b"<p>x</p>"})
            want = ["ASM-ASSET " + " ".join(e[1:]) for e in _graph_assets(w["gsrc"])[0]]
            if len(want) != 2:
                raise _FixtureError(f"the builder's own asset errors for the fixture: {want}")
            good, why = _refused(w, _argv(w), want, "the builder's asset errors, reported as ASM-ASSET with its own paths and reasons")
            if not good:
                return good, why
        with _tmp() as d:
            w = _world(d)
            shutil.rmtree(w["gsrc"])
            os.mkdir(w["gsrc"])
            good, why = _refused(w, _argv(w), ["ASM-ASSET graph no-assets"], "an empty graph-src")
            if not good:
                return good, why
        with _tmp() as d:   # the shell of graph-src is clean, the one of --shell is not: the gate must read --shell
            dirty = SHELL.replace("<body>", "<body>\n<!-- https://example.invalid/x -->")
            w = _world(d, shell=dirty)
            _write_tree(w["gsrc"], {"shell.html": SHELL.replace("{{CARDS}}", "")})
            _errs, assets, in_src = _graph_assets(w["gsrc"])
            want = ["ASM-SINK " + e[2] for e in _graph_sink_errors(assets, dirty.encode("utf-8"))]
            if not want or _graph_sink_errors(assets, in_src):
                raise _FixtureError("the dirty --shell must be refused by the sink gate and the graph-src shell must not")
            return _refused(w, _argv(w), want, "the sink gate reads the shell of --shell, not the one of graph-src")

    @case("A6", "the sink gate: `_graph_sink_errors(assets, shell)` runs over exactly the assets plus the Lean shell; its lines are reported `ASM-SINK <line>`, exit 1, nothing written")
    def _():
        with _tmp() as d:
            w = _world(d)
            _write_tree(w["gsrc"], {"page/app.js": b"x.innerHTML = s;\n"})
            _errs, assets, _sh = _graph_assets(w["gsrc"])
            want = ["ASM-SINK " + e[2] for e in _graph_sink_errors(assets, SHELL.encode("utf-8"))]
            if not want:
                raise _FixtureError("the builder's own sink gate accepts a file that holds innerHTML")
            return _refused(w, _argv(w), want, "a sink in an asset: the builder's own lines, each as ASM-SINK <line>")

    @case("A7", "the page is the builder's function: `_graph_page(shell, set(assets), strings, about, \"\", shell_keys=GRAPH_SHELL_KEYS + (\"front_scope_line\",), section_attrs=((\"data-page-feedback\", "
                "\"off\"),))` with `cards` the empty string and `about` the escaped text of the strings key about_text (`ASM-STRINGS about_text missing` when absent); its errors are `ASM-PAGE <what> "
                "<reason>`; the assembled page then passes the element, static, head and surface checks `_run` applies (failures `ASM-PAGE`); the written page holds exactly one `<section "
                "id=\"graph-about\" data-page-feedback=\"off\">` and the byte-for-byte shell outside the replaced tokens")
    def _():
        _need_pr_c()
        special = _asm_strings(**{ABOUT_KEY: 'About <b>this</b> & "that"', SCOPE_KEY: "Scope: <a href=x>all</a> & more"})
        with _tmp() as d:
            w = _world(d, scope=True, strings=special)
            tree = _ok_run(w)[0]
            page = tree["index.html"].decode("utf-8")
            want = _expected_page(w, SHELL_SCOPE, special)
            pieces = [p for p in re.split(r"\{\{(?:S:[A-Za-z0-9_]+|CARDS)\}\}", SHELL_SCOPE) if p]
            at, in_order = 0, True
            for p in pieces:
                i = page.find(p, at)
                in_order = in_order and i >= 0
                at = i + len(p) if i >= 0 else at
            ok, why = _eq((page, page.count('<section id="graph-about" data-page-feedback="off">'), page.count("<section"), bs._e(special[SCOPE_KEY]) in page,
                           "<b>this</b>" in page, "<a href=x>" in page, in_order), (want, 1, 1, True, False, False, True))
            if not ok:
                return ok, why
        with _tmp() as d:   # about_text absent
            w = _world(d, strings=_asm_strings(**{ABOUT_KEY: None}))
            good, why = _refused(w, _argv(w), ["ASM-STRINGS about_text missing"], "about_text absent")
            if not good:
                return good, why
        with _tmp() as d:   # the builder's own refusal of the shell: no {{CARDS}}
            w = _world(d, shell=SHELL.replace("{{CARDS}}", ""))
            errs, _p = _graph_page(SHELL.replace("{{CARDS}}", "").encode("utf-8"), set(w["assets"]), _asm_strings(), bs._e(ABOUT_TEXT), "")
            want = ["ASM-PAGE " + " ".join(e[1:]) for e in errs]
            if not want:
                raise _FixtureError("the builder accepts a shell without {{CARDS}}")
            good, why = _refused(w, _argv(w), want, "the builder's own page errors as ASM-PAGE")
            if not good:
                return good, why
        with _tmp() as d:   # a check `_run` applies to the assembled page, which `_graph_page` does not make: the static check
            w = _world(d, strings=_asm_strings(**{ABOUT_KEY: "call fetch(x) here"}))
            problem = static_problems(_expected_page(w, SHELL, _asm_strings(**{ABOUT_KEY: "call fetch(x) here"})), "")
            if not problem:
                raise _FixtureError("the static check does not refuse the planted text")
            return _refused_like(w, _argv(w), lambda ls: all(ln.startswith("ASM-PAGE ") for ln in ls) and any(problem[0] in ln for ln in ls), "a static-check failure on the page")

    @case("A8", "no page thread: the page carries NO `article` element with class `card`, and the About block carries `data-page-feedback=\"off\"` (so the comment script creates no comment "
                "section on this page)")
    def _():
        _need_pr_c()

        class P(HTMLParser):
            def __init__(self):
                super().__init__()
                self.articles, self.about = [], None

            def handle_starttag(self, tag, attrs):
                a = dict(attrs)
                if tag == "article":
                    self.articles.append(a.get("class", ""))
                if tag == "section" and a.get("id") == "graph-about":
                    self.about = a
        with _tmp() as d:
            w = _world(d)
            page = _ok_run(w)[0]["index.html"].decode("utf-8")
            p = P()
            p.feed(page)
            return _eq((p.articles, (p.about or {}).get("data-page-feedback")), ([], "off"))

    @case("A9", "index.json: `index.json` is the builder's index with ONLY `assets` replaced by {path: sha256 of the asset} for every asset, serialised by `_graph_bytes`; with `assets` removed "
                "from both the objects are equal; `_graph_asset_errors(assets_map, files)` is empty; every other key (even one the tool has never heard of) is carried unchanged")
    def _():
        _need_pr_c()
        with _tmp() as d:
            w = _world(d)
            src = dict(json.loads(w["files"]["index.json"]), assets={"stale.js": "0" * 64}, zz_unknown_key={"b": [1, 2], "a": "x<y&z>"})
            _write_tree(w["data"], {"index.json": _graph_bytes({"x": src})["x"]})
            tree = _ok_run(w)[0]
            got = json.loads(tree["index.json"])
            amap = {rel: _sha(data) for rel, data in w["assets"].items()}
            want = dict(src, assets=amap)
            return _eq(({k: v for k, v in got.items() if k != "assets"}, got["assets"], tree["index.json"], _graph_asset_errors(amap, {"graph/" + k: v for k, v in tree.items()})),
                       ({k: v for k, v in src.items() if k != "assets"}, amap, _graph_bytes({"x": want})["x"], []))

    @case("A10", "everything else byte for byte: spine.json, uses.json and every step/<id>.json are written exactly as read (their bytes, even where they are not in the builder's own "
                 "serialisation), the assets exactly as `_graph_assets` returned them")
    def _():
        _need_pr_c()
        with _tmp() as d:
            w = _world(d, big=True)
            odd = {rel: json.dumps(json.loads(data), separators=(",", ":")).encode("utf-8") + b"\n" for rel, data in w["files"].items() if rel != "index.json"}
            _write_tree(w["data"], odd)
            _write_tree(w["gsrc"], {"graph.css": b"body { margin: 0; }  \r\n"})
            assets = _graph_assets(w["gsrc"])[1]
            tree = _ok_run(w)[0]
            return _eq(({rel: tree.get(rel) for rel in odd}, {rel: tree.get(rel) for rel in assets}), (odd, assets))

    @case("A11", "layout: the tree is FLAT, the shape of the live kept copy plus the page at its root: index.html, index.json, spine.json, uses.json, step/<id>.json, the assets at their own "
                 "paths (engine/..., page/..., graph.css), manifest.json; no other file, no empty folder, no `graph/` prefix, nothing beside OUT_DIR; every relative src and href of the page "
                 "names a file of the tree. (Two inputs mapping to one path, `ASM-OUT <path> twice`, cannot be reached from the command line: an asset is .js/.mjs/.css and every other "
                 "name is fixed or under step/, so no case drives it)")
    def _():
        _need_pr_c()
        with _tmp() as d:
            w = _world(d, big=True)
            tree, empty = _ok_run(w)
            want = {"index.html", "index.json", "spine.json", "uses.json", "manifest.json"} | set(GRAPH_SRC_FILES) | set(_step_names(w["files"]))
            page = tree["index.html"].decode("utf-8")
            refs = [r for r in re.findall(r'(?:src|href)="([^"#]*)"', page) if r and "://" not in r and not r.startswith("/")]
            return _eq((sorted(tree), empty, sorted(os.listdir(d)), [r for r in refs if r not in tree], bool(refs)),
                       (sorted(want), [], sorted(["data", "gsrc", "shell.html", "strings.json", "out"]), [], True))

    @case("A12", "manifest: manifest.json is `_manifest_bytes(files, {\"notes\": pin}, {\"steps\": n}, None, None)`: `files` = sha256 of EVERY other written file, index.html included; `commits` "
                 "= {notes: pin} and nothing else; `counts` = {steps: <step files>}; no `release_id` and no `release_archive_sha` key; a case re-hashes every file independently")
    def _():
        _need_pr_c()
        with _tmp() as d:
            w = _world(d, big=True)
            tree = _ok_run(w)[0]
            m = json.loads(tree["manifest.json"])
            want_files = {rel: hashlib.sha256(data).hexdigest() for rel, data in sorted(tree.items()) if rel != "manifest.json"}
            return _eq((sorted(m), m.get("files"), m.get("commits"), m.get("counts"), "index.html" in m.get("files", {}), tree["manifest.json"] == (_dump(m) + "\n").encode("utf-8")),
                       (["commits", "counts", "files"], want_files, {"notes": PIN}, {"steps": len(_step_names(w["files"]))}, True, True))

    @case("A13", "determinism: two runs into two fresh folders give byte-identical trees, with no clock, random, environment or order dependence (dict order sorted, file list sorted); the "
                 "lines of a refusal come out in sorted file order whatever the modification times of the step files")
    def _():
        with _tmp() as d:   # refusal lines: three step files that cannot be read, modification times in the REVERSE of their names
            w = _world(d, big=True)
            names = _step_names(w["files"])[:3]
            for i, rel in enumerate(names):
                p = os.path.join(w["data"], rel)
                with open(p, "wb") as f:
                    f.write(b"\xff\xfe")
                os.utime(p, (1_000_000_000 + (10 - i) * 1000, 1_000_000_000 + (10 - i) * 1000))
            rc, lines, err = _cli(_argv(w))
            ok, why = _eq((rc, lines, "Traceback" in err), (1, [f"ASM-DATA {rel} encoding" for rel in names], False))
            if not ok:
                return ok, why
        _need_pr_c()
        trees = []
        for k, tz in enumerate(("UTC", "Pacific/Auckland")):
            with _tmp() as d:
                w = _world(d, big=True)
                for i, rel in enumerate(_step_names(w["files"])):   # the second world has the modification times the other way round
                    t = 1_000_000_000 + (i if k == 0 else 20 - i) * 1000
                    os.utime(os.path.join(w["data"], rel), (t, t))
                os.mkdir(os.path.join(d, "cwd"))
                trees.append(_ok_run(w, env=dict(os.environ, TZ=tz), cwd=os.path.join(d, "cwd")))
        return _eq(sorted(k for k in set(trees[0][0]) | set(trees[1][0]) if trees[0][0].get(k) != trees[1][0].get(k)) + trees[0][1] + trees[1][1], [])

    @case("A14", "atomic: either the whole tree is written or OUT_DIR is left as it was (empty or absent): every check runs before the first write, so a refusal leaves OUT_DIR as it was and "
                 "no temporary folder beside it; a failure WHILE writing (a write that fails on its way, here by a size limit on one file) removes what this run wrote")
    def _():
        with _tmp() as d:   # a refusal, OUT_DIR absent
            w = _world(d)
            before = sorted(os.listdir(d))
            _write_tree(w["data"], {"index.json": _recommit(w["files"]["index.json"], BAD_PIN)})
            good, why = _refused(w, _argv(w), [f"ASM-PIN index.json {BAD_PIN}"], "a refusal with OUT_DIR absent")
            if not good or sorted(os.listdir(d)) != before:
                return False, why + f" / folder listing {sorted(os.listdir(d))} vs {before}"
        with _tmp() as d:   # a refusal, OUT_DIR empty
            w = _world(d)
            os.mkdir(w["out"])
            before = sorted(os.listdir(d))
            _write_tree(w["gsrc"], {"engine/bad.js": b"x"})
            os.symlink(os.path.join(w["gsrc"], "graph.css"), os.path.join(w["gsrc"], "engine", "link.js"))
            want = ["ASM-ASSET " + " ".join(e[1:]) for e in _graph_assets(w["gsrc"])[0]]
            good, why = _refused(w, _argv(w), want, "a refusal with OUT_DIR empty", out_state=[])
            if not good or sorted(os.listdir(d)) != before:
                return False, why + f" / folder listing {sorted(os.listdir(d))} vs {before}"
        _need_pr_c()
        with _tmp() as d:   # a write that fails on its way
            w = _world(d)
            tree = _ok_run(w)[0]
            shutil.rmtree(w["out"])
            size = {rel: len(data) for rel, data in tree.items()}
            limit = len(w["files"]["index.json"]) + 100
            if size["index.json"] <= limit or max(v for k, v in size.items() if k != "index.json") >= limit:
                raise _FixtureError(f"the size limit {limit} does not single out index.json: {size}")
            before = sorted(os.listdir(d))
            rc, _lines, _err = _cli(_argv(w), preexec=_limit_writes(limit))
            ok, why = _eq((rc != 0, os.path.exists(w["out"]), sorted(os.listdir(d))), (True, False, before))
            if not ok:
                return ok, "a failed write, OUT_DIR absent before: " + why
            os.mkdir(w["out"])
            rc, _lines, _err = _cli(_argv(w), preexec=_limit_writes(limit))
            return _eq((rc != 0, os.listdir(w["out"]), sorted(os.listdir(d))), (True, [], sorted(before + ["out"])))

    @case("A15", "refusal order: usage (2) -> data A1/A2 (every error reported) -> pin A3 -> assets A5 -> sink A6 -> page A7 -> out A4; the first failing stage reports all its refusals and "
                 "stops the run, so a later stage's faults are never shown with it")
    def _():
        with _tmp() as d:   # usage: exit 2, usage on stderr, nothing on stdout, nothing written (the stub implements this)
            w = _world(d)
            for what, argv in (("a missing option", _argv(w, drop=("--out",))), ("a short pin", _argv(w, pin="abc")), ("an option twice", _argv(w) + ["--out", w["out"]]),
                               ("a stray word", _argv(w) + ["x"])):
                rc, lines, err = _cli(argv)
                if (rc, lines, err.startswith("usage: assemble_grh_site.py"), os.path.exists(w["out"])) != (2, [], True, False):
                    return False, f"usage ({what}): exit {rc}, stdout {lines!r}, stderr {err[:60]!r}"
        with _tmp() as d:   # every stage has a fault at once
            w = _world(d)
            dirty = SHELL.replace("<body>", "<body>\n<!-- https://example.invalid/x -->")
            with open(w["shell"], "w", encoding="utf-8") as f:
                f.write(dirty)
            os.symlink(os.path.join(w["gsrc"], "graph.css"), os.path.join(w["gsrc"], "engine", "link.js"))
            asset_lines = ["ASM-ASSET " + " ".join(e[1:]) for e in _graph_assets(w["gsrc"])[0]]
            sink_lines = ["ASM-SINK " + e[2] for e in _graph_sink_errors(_graph_assets(w["gsrc"])[1], dirty.encode("utf-8"))]
            if not asset_lines or not sink_lines:
                raise _FixtureError("the staged faults of A15 are not faults")
            _write_tree(w["data"], {"notes.txt": b"x", "index.json": _recommit(w["files"]["index.json"], BAD_PIN)})
            good, why = _refused(w, _argv(w), ["ASM-DATA notes.txt unexpected"], "data faults hide the pin, asset and sink faults")
            if not good:
                return good, why
            os.remove(os.path.join(w["data"], "notes.txt"))
            good, why = _refused(w, _argv(w), [f"ASM-PIN index.json {BAD_PIN}"], "pin faults hide the asset and sink faults")
            if not good:
                return good, why
            _write_tree(w["data"], {"index.json": w["files"]["index.json"]})
            good, why = _refused(w, _argv(w), asset_lines, "asset faults hide the sink faults")
            if not good:
                return good, why
            os.remove(os.path.join(w["gsrc"], "engine", "link.js"))
            good, why = _refused(w, _argv(w), sink_lines, "sink faults are what is left")
            if not good:
                return good, why
        _need_pr_c()
        with _tmp() as d:   # a page fault and a non-empty OUT_DIR: the page stage answers, the out stage is never reached
            w = _world(d, strings=_asm_strings(**{ABOUT_KEY: None}))
            _write_tree(w["out"], {"keep.txt": b"mine"})
            return _refused(w, _argv(w), ["ASM-STRINGS about_text missing"], "a page fault hides a non-empty OUT_DIR", out_state=["keep.txt"])

    @case("A16", "never executes anything it reads: no import, eval, subprocess or shell on DATA, strings, shell or assets: the text of the tool above the self-test marker holds no call of "
                 "eval, exec, compile, __import__, os.system, os.popen, os.exec*, os.spawn*, subprocess, runpy, ctypes, pickle or marshal and imports no module of that kind (importlib only "
                 "inside `_load`, which loads the two builders of this folder); and lures in every input (code that would create a file) create no file")
    def _():
        with _tmp() as d:
            w = _world(d)
            canary = os.path.join(d, "CANARY")
            lure = f"__import__('os').system('touch {canary}'); $(touch {canary}); `touch {canary}`"
            bad = json.loads(w["files"]["index.json"])
            bad["commit"] = BAD_PIN
            bad["zz_lure"] = lure
            _write_tree(w["data"], {"index.json": _graph_bytes({"x": bad})["x"]})
            with open(w["shell"], "w", encoding="utf-8") as f:
                f.write(SHELL.replace("<body>", f"<body>\n<!-- {lure} -->"))
            with open(w["strings"], "w", encoding="utf-8") as f:
                json.dump(_asm_strings(**{ABOUT_KEY: lure}), f)
            good, why = _refused(w, _argv(w), [f"ASM-PIN index.json {BAD_PIN}"], "lures in every input")
            if not good or os.path.exists(canary):
                return False, why + f" / canary created: {os.path.exists(canary)}"
        with open(TOOL, encoding="utf-8") as f:
            src = f.read()
        marker = "\n# ==== self-test" + " ====\n"
        if src.count(marker) != 1:
            raise _FixtureError("the self-test marker must appear once in the tool")
        tree = ast.parse(src[:src.index(marker)])
        found = []

        def dotted(n):
            parts = []
            while isinstance(n, ast.Attribute):
                parts.append(n.attr)
                n = n.value
            return ".".join(([n.id] if isinstance(n, ast.Name) else []) + parts[::-1])

        loader = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "_load")
        inside_loader = {id(x) for x in ast.walk(loader)}
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                name = dotted(n.func)
                if name in ("eval", "exec", "compile", "__import__") or re.match(r"os\.(system|popen|exec\w*|spawn\w*|posix_spawn\w*)$", name) \
                        or re.match(r"(subprocess|runpy|ctypes|pickle|marshal)\.", name) or (name.startswith("importlib.") and id(n) not in inside_loader):
                    found.append(f"line {n.lineno}: call {name}")
            elif isinstance(n, (ast.Import, ast.ImportFrom)):
                mods = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""]
                found += [f"line {n.lineno}: import {m}" for m in mods if m.split(".")[0] in ("subprocess", "runpy", "ctypes", "pickle", "marshal", "code", "codeop")
                          or (m.split(".")[0] == "importlib" and m != "importlib.util")]
        return _eq(found, [])

    @case("A17", "the live map is untouched: importing this module has no side effect and sets no global (environment, working folder, sys.path, umask, the byte-code flag, build_site's own "
                 "globals): a fresh process imports it and a snapshot taken before and after is identical; the snapshot is shown to be able to see a planted change. (The builder's own live "
                 "build on the real data is the maintainers' gate, not run here)")
    def _():
        probe = r'''
import importlib.util, json, os, sys
sys.dont_write_bytecode = True
tool, here = sys.argv[1], sys.argv[2]
def load(path, key):
    spec = importlib.util.spec_from_file_location(key, path); m = importlib.util.module_from_spec(spec); sys.modules[key] = m; spec.loader.exec_module(m); return m
def vars_of(m):
    out = {}
    for k, v in vars(m).items():
        if k.startswith("__") or callable(v) or isinstance(v, type(sys)):
            continue
        r = repr(sorted(v, key=repr) if isinstance(v, (set, frozenset)) else v)
        if " at 0x" not in r:
            out[k] = r
    return out
def snap():
    return {"environ": dict(os.environ), "cwd": os.getcwd(), "path": list(sys.path), "umask": (lambda u: (os.umask(u), u)[1])(os.umask(0)), "bytecode": sys.dont_write_bytecode,
            "bare": [n for n in ("build_site", "build_grh_skeleton", "assemble_grh_site") if n in sys.modules]}
before = snap()
os.environ["ASM_PLANTED"] = "1"
planted = snap() != before
del os.environ["ASM_PLANTED"]
mod = load(tool, "assemble_under_test")
after = snap()
fresh = load(os.path.join(here, "build_site.py"), "fresh_build_site")
diffs = [k for k in before if before[k] != after[k]]
bs_diff = sorted(k for k in set(vars_of(fresh)) | set(vars_of(mod.bs)) if vars_of(fresh).get(k) != vars_of(mod.bs).get(k))
print(json.dumps({"planted_seen": planted, "diffs": diffs, "build_site_diffs": bs_diff}))
'''
        r = subprocess.run([sys.executable, "-I", "-c", probe, TOOL, _HERE], capture_output=True, text=True, timeout=120)
        if r.returncode != 0:
            return False, f"the probe failed: {r.stderr[-300:]}"
        got = json.loads(r.stdout)
        return _eq((got["planted_seen"], got["diffs"], got["build_site_diffs"]), (True, [], []))

    for mid in MUTATIONS:
        case(mid, f"mutation control for {MUTATIONS[mid][0]}: {MUTATIONS[mid][1]}; red set {', '.join(MUTATIONS[mid][2])}; every other A-case stays green (SKIPPED until phase 2)")(
            (lambda m: lambda: _mutation_case(m))(mid))
    return cases


def selftest(verbose=True, only=None):
    """Run the cases: 0 all pass (a skipped case does not fail), 4 one fails, 2 an unknown id in `only`."""
    cases = _selftest_cases()
    if only is not None:
        bad = [i for i in only if i not in {c[0] for c in cases}]
        if bad or not only:
            print("unknown case id: " + ", ".join(bad) if bad else "no case id given", file=sys.stderr)
            return 2
        cases = [c for c in cases if c[0] in only]
    ok, skipped = True, 0
    for cid, desc, fn in cases:
        try:
            good, detail = fn()
        except _SkipCase as e:
            skipped += 1
            if verbose:
                print(f"CASE {cid} SKIP {e}")
            continue
        except _Absent as e:   # the stub: red because the behaviour is absent
            good, detail = False, str(e)
        except _FixtureError as e:   # a bug of the case itself, named so it is never read as a finding about the tool
            good, detail = False, f"FIXTURE INVALID: {e}"
        except Exception as e:   # a crash is a failed case, not a skipped one
            good, detail = False, f"{type(e).__name__}: {e}"
        ok = ok and bool(good)
        if verbose:
            print(f"CASE {cid} {'PASS' if good else 'FAIL'} {desc}")
            if not good:
                print(f"  detail: {detail}")
    if verbose:
        print("SELFTEST " + ("PASS" if ok else "FAIL") + (f" ({skipped} skipped)" if ok and skipped else ""))
    return 0 if ok else 4


def _selftest_main(rest):
    """`--selftest [--only ID,ID]`, each once."""
    only = None
    i = 0
    while i < len(rest):
        if rest[i] == "--only" and only is None and i + 1 < len(rest):
            only = [x for x in rest[i + 1].split(",") if x]
        else:
            return 2
        i += 2
    return selftest(only=only)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
