#!/usr/bin/env python3
"""The page of the new map: the data tree of the skeleton builder, plus the shell, the engine, the page layer and the stylesheet, plus a manifest, as ONE flat tree.

usage: assemble_grh_site.py --data DIR --pin COMMIT --strings strings.json --shell shell.html --out OUT_DIR [--graph-src DIR]
       assemble_grh_site.py --selftest [--only ID,ID]

The tool writes, from the data of `build_grh_skeleton.py` (index.json, spine.json, uses.json, step/<id>.json; DATA holds nothing else), the graph assets of `build_site._graph_assets`,
and a page made by `build_site._graph_page`, the tree below, FLAT (the page loads its data and scripts relative to its own address):
    index.html  index.json  spine.json  uses.json  step/<id>.json  engine/...  page/...  graph.css  manifest.json
It never opens OUT_DIR unless every check has passed, writes nothing on a refusal (exit 1, one `ASM-<CODE> <what> <reason>` line per refusal), and imports every function it needs from
build_site.py and build_grh_skeleton.py: it has no second implementation of any of them. Its contract is the set of clauses A1 to A27 (A7b and A11b included), one self-test case each (A7b is four, A11b and A19 two), and the
mutation controls M-a to M-r, each of which runs the cases on a wrong copy of the tool and compares the red cases both ways; docs/tools.md says what the tool does.

PATH CONVENTION of the refusal lines (the contract writes `<path>` and does not say which; the cases pin this reading): a file or folder INSIDE DATA is named relative to DATA with
`/` (`index.json`, `step/lean-main.json`); `--strings` and `--shell` are named as given on the command line; `ASM-OUT` names OUT_DIR as given; `ASM-ASSET` and `ASM-PAGE` carry the
builder's own words.

THE THREE DEPENDENCIES ON PR C (a separate change to build_site.py by another agent, in this base as PR 100; this file does not implement or stub them):
  (a) `_graph_page(shell, assets, strings, about, cards, shell_keys=GRAPH_SHELL_KEYS, section_attrs=())`: `section_attrs` is a tuple of (name, value) pairs written on the
      `<section id="graph-about">`, escaped, in order; a name the allow-list does not permit is a named refusal, never a silent drop; live output byte-identical;
  (b) `data-page-feedback` allowed on `section` in the graph page's element table (`graph_element_problems`);
  (c) `_manifest_bytes(files, commits, counts, release_id=None, archive=None)`, extracted from `_output_files`; the keys release_id and release_archive_sha are OMITTED when None.
A case that needs one of them detects it (`hasattr(bs, "_manifest_bytes")`, the signature of `_graph_page`, `graph_element_problems` on a `section` that carries the attribute) and
reports SKIP with the reason; it never passes and never fails for the want of it.

WHAT THE A16 SCAN CLAIMS AND DOES NOT: the claim "the tool never executes what it reads" is checked two ways. The DYNAMIC half (lures in every input create no file, the run builds) is the real
check. The STATIC half is a LINT over the text above the self-test marker: it flags the imports, names, attributes and `os` uses it models, each with a positive control and a negative control,
and it is not a closed set. It does not see, for example, `sys.modules['builtins'].eval`, a subscript of a namespace dict, a `shutil`-style write reached under another name, or `os` bound
to another name by assignment; passing it is evidence about the routes it models, never proof that no route exists.

Exit codes: 0 built, 1 refused (OUT_DIR not created and not touched), 2 usage. --selftest: 0 all pass (a skipped case does not fail), 4 one fails, 2 an unknown id after --only or a bad
self-test command line.
"""
import importlib.util
import json
import os
import re
import sys
from html.parser import HTMLParser

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
                    "graph_element_problems", "static_problems", "head_meta_problems", "surface_scan",
                    "_manifest_bytes", "_e", "code_spans", "GRAPH_ID", "_publish", "_graph_static_problems", "element_problems", "link_problems")
_FROM_SKELETON = ("_read_in", "_contained")
_UNRESOLVED = [f"build_site.{n}" for n in _FROM_BUILD_SITE if not hasattr(bs, n)] + [f"build_grh_skeleton.{n}" for n in _FROM_SKELETON if not hasattr(sk, n)]
if _UNRESOLVED:   # something the contract imports cannot be imported as it stands: stop, never copy it
    raise ImportError("assemble_grh_site: cannot import " + ", ".join(_UNRESOLVED))
_graph_assets = bs._graph_assets   # one name, one line: the binding does not depend on the order of the tuple above
_graph_sink_errors = bs._graph_sink_errors
_graph_asset_errors = bs._graph_asset_errors
_graph_page = bs._graph_page
GRAPH_SHELL_KEYS = bs.GRAPH_SHELL_KEYS
_graph_bytes = bs._graph_bytes
_dump = bs._dump
_sha = bs._sha
graph_element_problems = bs.graph_element_problems
static_problems = bs.static_problems
head_meta_problems = bs.head_meta_problems
surface_scan = bs.surface_scan
_manifest_bytes = bs._manifest_bytes
_e = bs._e
code_spans = bs.code_spans
GRAPH_ID = bs.GRAPH_ID
_publish = bs._publish
_graph_static_problems = bs._graph_static_problems
element_problems = bs.element_problems
link_problems = bs.link_problems
_read_in, _contained = sk._read_in, sk._contained

TOP_READ_LIMIT = 4 * 1024 * 1024    # index.json, spine.json, uses.json, the strings file, the shell: the most bytes of each read (A1)
STEP_READ_LIMIT = 1024 * 1024       # one step file (A1)
MAX_STEP_FILES = 2000               # the most step files (A1)
DATA_FIXED = ("index.json", "spine.json", "uses.json")   # DATA holds these, step/<id>.json, and nothing else (A2)
ABOUT_KEY = "about_text"            # the strings key whose text fills #graph-about (contract, Open 3: the default; `ASM-STRINGS about_text missing` when absent)
CREDITS_REL = "credits/index.html"  # the one path `--page` may name: the page the website's place.mjs requires beside the map (A20)
CREDITS_DIR = "credits/"            # its folder: the href of the About link (A24) and the base its refs resolve against (A23)
CREDITS_REPO = "https://github.com/lsernau/grh-lean/"   # the one repository the credits page may link to (A27), at the run's own --pin
ABOUT_CREDITS_KEYS = ("about_credits_before", "about_credits_link", "about_credits_after")   # the three strings keys of the About link, required when --page is given (A24)
NO_PAGE_NOTE = "note: no credits page (--page credits/index.html=PATH); place.mjs refuses a tree without it"   # the second line of the success report of a run without --page (A20)
SCOPE_KEY = "front_scope_line"      # the shell key PR C lets the page carry besides GRAPH_SHELL_KEYS (A7)
READINGS_FRONT_KEY = "readings_front"   # the shell key whose strings value is the template of the readings front line (A18)
READINGS_KEY = "readings"           # the key of index.json that holds the list of reading notes, one row per note (A18; the real name is still being asked: ONE constant, used everywhere)
SHELL_KEYS = bs.GRAPH_SHELL_KEYS + ("front_scope_line", "readings_front")   # the `{{S:key}}` tokens the shell may hold: the builder's eleven, the scope line (A7), the readings front line (A18)
PAGE_SECTION_ATTRS = (("data-page-feedback", "off"),)   # A7, A8
CODES = ("ASM-DATA", "ASM-PIN", "ASM-OUT", "ASM-ASSET", "ASM-SINK", "ASM-PAGE", "ASM-STRINGS", "ASM-READINGS", "ASM-STATIC")   # the codes of a refusal line: `<CODE> <what> <reason>`
DATA_REASONS = ("symlink", "not-regular", "too-large", "encoding", "unexpected", "missing")   # the reasons of ASM-DATA

_OPTIONS = ("--data", "--pin", "--strings", "--shell", "--out", "--graph-src", "--page")
_PIN = re.compile(r"[0-9a-f]{40}")
USAGE = ("usage: assemble_grh_site.py --data DIR --pin COMMIT --strings strings.json --shell shell.html --out OUT_DIR [--graph-src DIR] [--page credits/index.html=PATH]\n"
         "       assemble_grh_site.py --selftest [--only ID,ID]")


def _parse(a):
    """{data, pin, strings, shell, out, graph-src[, page]} or None: each option once, with a value; --pin a 40-hex string (lower case); --page `credits/index.html=PATH` with a non-empty PATH
    (`page` is the PATH); nothing else; --graph-src defaults to build_site.GRAPH_SRC."""
    opts, i = {}, 0
    while i < len(a):
        if a[i] in _OPTIONS and a[i][2:] not in opts and i + 1 < len(a):
            opts[a[i][2:]] = a[i + 1]
            if a[i] == "--page":   # REL=PATH: REL exactly CREDITS_REL, PATH not empty (split at the first `=`)
                rel, eq, path = a[i + 1].partition("=")
                if rel != CREDITS_REL or not eq or not path:
                    return None
                opts["page"] = path
            i += 2
        else:
            return None
    if not {"data", "pin", "strings", "shell", "out"} <= set(opts) or not _PIN.fullmatch(opts["pin"]):
        return None
    opts.setdefault("graph-src", bs.GRAPH_SRC)
    return opts


_REASON = {"not-a-regular-file": "not-regular"}   # `_read_in`'s word -> the contract's word


def _other(path):
    """The reason of an entry of DATA that the data set does not name: a symlink is a symlink, anything else is unexpected."""
    return "symlink" if os.path.islink(path) else "unexpected"


def _data_read(root, path, limit, name, lines):
    """The bytes of one input, read bounded and contained (`_read_in`) and checked UTF-8; None, and one `ASM-DATA <name> <reason>` line in `lines`, when it cannot be taken."""
    try:
        raw = _read_in(root, path, limit)
    except sk.SourceError as e:
        lines.append(f"ASM-DATA {name} {_REASON.get(e.reason, e.reason)}")
        return None
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        lines.append(f"ASM-DATA {name} encoding")
        return None
    return raw


def _data_steps(data, path, raws, lines):
    """The step/ folder of DATA: every entry is a step file `<slug>.json` or a refusal line; at most MAX_STEP_FILES entries."""
    if os.path.islink(path):
        lines.append("ASM-DATA step symlink")
    elif not os.path.lexists(path):
        lines.append("ASM-DATA step missing")
    elif not os.path.isdir(path):
        lines.append("ASM-DATA step unexpected")
    else:
        try:
            names = sorted(os.listdir(path))
        except OSError:
            lines.append("ASM-DATA step unreadable")
            return
        if len(names) > MAX_STEP_FILES:
            lines.append("ASM-DATA step too-many")
            return
        for n in names:
            rel, q = "step/" + n, os.path.join(path, n)
            if not (n.endswith(".json") and GRAPH_ID.fullmatch(n[:-5])) or (os.path.isdir(q) and not os.path.islink(q)):
                lines.append(f"ASM-DATA {rel} {_other(q)}")
            else:
                raws[rel] = _data_read(data, q, STEP_READ_LIMIT, rel, lines)


def _stage_data(opts):
    """(lines, raws, objs): A1 and A2. `raws` {name: bytes} holds every input that could be read (the three fixed files, `step/<id>.json`, and `strings` and `shell` by those names),
    `objs` {name: object} the parsed JSON of all but the shell. Every fault of the stage is a line."""
    data, lines, raws = opts["data"], [], {}
    try:
        entries = sorted(set(os.listdir(data)) | set(DATA_FIXED) | {"step"})
    except OSError:
        lines.append(f"ASM-DATA {data} missing")
        entries = []
    for name in entries:
        path = os.path.join(data, name)
        if name in DATA_FIXED:
            if os.path.lexists(path):
                raws[name] = _data_read(data, path, TOP_READ_LIMIT, name, lines)
            else:
                lines.append(f"ASM-DATA {name} missing")
        elif name == "step":
            _data_steps(data, path, raws, lines)
        else:
            lines.append(f"ASM-DATA {name} {_other(path)}")
    for key in ("strings", "shell") + (("page",) if "page" in opts else ()):   # named as given on the command line
        p = opts[key]
        raws[key] = _data_read(os.path.dirname(os.path.abspath(p)), p, TOP_READ_LIMIT, p, lines)
    objs = {}
    for name, raw in raws.items():
        if raw is None or name in ("shell", "page"):
            continue
        try:
            obj = json.loads(raw.decode("utf-8"))
        except (ValueError, RecursionError):
            obj = None
        if isinstance(obj, dict):
            objs[name] = obj
        else:
            lines.append(f"ASM-DATA {opts[name] if name == 'strings' else name} not-json")
    return lines, raws, objs


def _found(v):
    """How a `commit` that is not the pin is shown in an ASM-PIN line."""
    return v if isinstance(v, str) else json.dumps(v)


def _stage_pin(pin, objs):
    """The lines of A3: `commit` of index, spine, uses and every step file equals the pin; every step's `id` is its file name; index `steps` is the number of step files."""
    lines = []
    for rel in sorted(k for k in objs if k != "strings"):
        found = objs[rel].get("commit", "missing")
        if found != pin:
            lines.append(f"ASM-PIN {rel} {_found(found)}")
    steps = sorted(k for k in objs if k.startswith("step/"))
    for rel in steps:
        if objs[rel].get("id") != rel[len("step/"):-len(".json")]:
            lines.append(f"ASM-PIN {rel} id={_found(objs[rel].get('id', 'missing'))}")
    if objs["index.json"].get("steps") != len(steps):
        lines.append(f"ASM-PIN index.json steps={_found(objs['index.json'].get('steps', 'missing'))}/files={len(steps)}")
    return lines


REF_ATTRS = ("href", "src", "action", "srcset", "poster", "data")   # the attributes of the written page whose value is an address (A11b)


def _ref_reason(ref, names, base=""):
    """None when `ref` resolves inside the tree whose file names are `names`, else `absolute`, `escapes` or `missing` (A11b). The part from the first `?` or `#` is dropped; an empty path
    (a bare #fragment or ?query) passes; a leading `/` or `//`, or a scheme (a `:` in the first segment), is `absolute`; a `..` segment is `escapes`; a path that is not a name of the tree
    (a trailing-slash folder holds one when some name lies under it) is `missing`. A backslash counts as `/`, as a browser reads it.
    `base` is the folder of the page the ref is on (A23): "" for index.html (the rules above, unchanged); for credits/index.html it is `credits/`, and the ref is resolved from there: a `..` that stays
    inside the tree resolves, one that leaves it is `escapes`, `.` and an empty segment stay in the folder, and a ref that names a folder (a trailing `/`, or a last segment `.` or `..`) passes when
    some name lies under that folder (the tree's root holds names)."""
    path = re.split(r"[?#]", "".join(ch for ch in ref if ch not in "\t\n\r").strip().replace("\\", "/"), maxsplit=1)[0]
    if not path:
        return None
    if path.startswith("/") or ":" in path.split("/")[0]:
        return "absolute"
    if base:
        stack = [seg for seg in base.split("/") if seg]
        for seg in path.split("/"):
            if seg == "..":
                if not stack:
                    return "escapes"
                stack.pop()
            elif seg not in ("", "."):
                stack.append(seg)
        target = "/".join(stack)
        if path.endswith("/") or path.split("/")[-1] in (".", ".."):
            return None if any(n.startswith(target + "/") for n in names) or (not target and names) else "missing"
        return None if target in names else "missing"
    if ".." in path.split("/"):
        return "escapes"
    if path in names or (path.endswith("/") and any(n.startswith(path) for n in names)):
        return None
    return "missing"


def _credits_link_ok(ref, pin):
    """A27: True when `ref` (as shown: control whitespace dropped) is exactly `CREDITS_REPO` + `tree/<pin>`, or begins with `CREDITS_REPO` + `tree/<pin>/` or `blob/<pin>/`. An exact string compare, no
    URL parsing: `<pin>x`, `<pin>?x`, `<pin>#x`, another commit, another letter case and a missing commit are all not it. A27b: a tail with a `.` or `..` segment, an empty segment, a backslash, a control
    character or an encoded dot, slash or backslash is not it either (the path would leave the pinned repository)."""
    for kind in ("tree/", "blob/"):
        head = CREDITS_REPO + kind
        if ref.startswith(head):
            commit, sep, rest = ref[len(head):].partition("/")
            if not (commit == pin and (sep == "/" or kind == "tree/")):
                return False
            if not sep:
                return True
            # A27b: the tail may not climb out of the pinned repository: no backslash, encoded dot, slash or backslash, control character, `.`/`..` or empty segment in the path (before `?`/`#`)
            if "\\" in rest or any(ord(c) < 32 or ord(c) == 127 for c in rest) or any(e in rest.lower() for e in ("%2e", "%2f", "%5c")):
                return False
            segs = rest.split("?", 1)[0].split("#", 1)[0].split("/")
            return not any(g in (".", "..") for g in segs) and "" not in segs[:-1]
    return False


def _ref_problems(page, names, base="", label=None, link_pin=None):
    """[`ASM-PAGE <ref> absolute|escapes|missing`] (with `label`, the page's name: `ASM-PAGE <label>: <ref> <reason>`) for every ref of the written page (the values of REF_ATTRS; each candidate of a srcset), a repeated (ref, reason) once, ordered by the
    place of its first occurrence in the page, then by ref. The ref is shown as the page holds it (control whitespace dropped). With `link_pin` (the run's --pin; only the credits page passes it, A27) the
    `href` of an `<a>` that `_credits_link_ok` accepts is not a ref of the tree and is skipped; any other attribute or element is read as before."""
    seen = {}

    class P(HTMLParser):
        def handle_starttag(self, tag, attrs):
            for k, v in attrs:
                if k not in REF_ATTRS or v is None:
                    continue
                for ref in ([c.split()[0] for c in v.split(",") if c.split()] if k == "srcset" else [v]):
                    shown = "".join(ch for ch in ref if ch not in "\t\n\r").strip()
                    if link_pin is not None and tag == "a" and k == "href" and _credits_link_ok(shown, link_pin):
                        continue
                    reason = _ref_reason(shown, names, base)
                    if reason:
                        seen.setdefault((shown, reason), (self.getpos(), shown))

    parser = P()
    parser.feed(page)
    parser.close()
    return [f"ASM-PAGE {label + ': ' if label else ''}{ref} {reason}" for (ref, reason), _where in sorted(seen.items(), key=lambda kv: kv[1])]


def _stage_page(shell_bytes, assets, strings, index, names, credits=None, pin=None):
    """(lines, page): A7 and A18. The page is the builder's `_graph_page` over the Lean shell, `cards` empty, `about` the escaped about_text in one paragraph, the section carrying
    `data-page-feedback="off"`; then the builder's own element, static, head and surface checks over the assembled page. With `credits` (the bytes of the credits page, A21) the About block holds a
    second paragraph, the link to it (A24), and the credits page is checked (A22, A23) in the same stage: its lines come after the index.html lines."""
    lines = []
    for key in (ABOUT_KEY, "root_only_note_single") + (ABOUT_CREDITS_KEYS if credits is not None else ()):
        if key not in strings:
            lines.append(f"ASM-STRINGS {key} missing")
        elif not isinstance(strings[key], str):
            lines.append(f"ASM-STRINGS {key} not-a-string")
        elif key in ABOUT_CREDITS_KEYS and not strings[key]:
            lines.append(f"ASM-STRINGS {key} missing")
    if "{{S:" + READINGS_FRONT_KEY + "}}" in shell_bytes.decode("utf-8"):   # A18: the key is used only when the shell holds the token
        template, rows = strings.get(READINGS_FRONT_KEY), index.get(READINGS_KEY)
        bad_template = not (isinstance(template, str) and template.count("{n}") == 1)
        bad_rows = not (isinstance(rows, list) and all(isinstance(r, dict) for r in rows))
        if bad_template:
            lines.append(f"ASM-READINGS {READINGS_FRONT_KEY} template")
        if bad_rows:
            lines.append(f"ASM-READINGS {READINGS_KEY} shape")
        if not (bad_template or bad_rows):
            strings = dict(strings, **{READINGS_FRONT_KEY: template.replace("{n}", str(len(rows)))})
    if lines:
        return lines, None
    about = "<p>" + _e(strings[ABOUT_KEY]) + "</p>"
    if credits is not None:   # A24: the href is the folder of REL, never a strings value
        before, link, after = (strings[k] for k in ABOUT_CREDITS_KEYS)
        about += "<p>" + _e(before) + '<a href="' + CREDITS_DIR + '">' + _e(link) + "</a>" + _e(after) + "</p>"
    errors, page = _graph_page(shell_bytes, set(assets), strings, about, "", shell_keys=SHELL_KEYS, section_attrs=PAGE_SECTION_ATTRS)
    if errors:
        return ["ASM-PAGE " + " ".join(e[1:]) for e in errors], None
    found = static_problems(page, "") + graph_element_problems(page) + head_meta_problems(page)
    lines = [f"ASM-PAGE {pb} found in index.html" for pb in found]
    if bs.CODE_ON_SURFACE_REFUSES:   # read at the call, as `_run` does
        lines += [f"ASM-PAGE CODE-ON-SURFACE index.html:{card} {text[:60]} x{k}" for card, text, k in code_spans(surface_scan(page)[1])]
    lines += _ref_problems(page, names)   # A11b: after the builder's checks, which do not look at `..` or at a ref to a file that is not in the tree
    if credits is not None:   # A22, A23: the credits page is a plain document (the DOCUMENT table, not the graph page's), its refs resolve from its own folder
        cpage = credits.decode("utf-8")
        lines += [f"ASM-PAGE {pb} found in {CREDITS_REL}" for pb in static_problems(cpage, "") + element_problems(cpage) + head_meta_problems(cpage) + link_problems(cpage)]
        lines += _ref_problems(cpage, names, CREDITS_DIR, CREDITS_REL, link_pin=pin)   # A27: the run's own pin, for the one repository the page may link to
    return lines, (None if lines else page)


def run(opts):
    """The whole of A1 to A18: every check before the first write; one `ASM-<CODE> <what> <reason>` line per refusal of the first stage that fails, exit 1; 0 built."""
    pin, out = opts["pin"], opts["out"]
    lines, raws, objs = _stage_data(opts)
    if not lines:
        lines = _stage_pin(pin, objs)
    if lines:
        print("\n".join(lines))
        return 1
    errors, assets, _graph_src_shell = _graph_assets(opts["graph-src"])   # READ here (the index of the written tree carries the assets' hashes); the asset faults are reported after the static stage
    steps = sorted(k for k in raws if k.startswith("step/"))
    index = dict(objs["index.json"], assets={rel: _sha(data) for rel, data in assets.items()})
    index_bytes = _graph_bytes({"x": index})["x"]
    json_files = {"graph/" + rel: data for rel, data in [("index.json", index_bytes), ("spine.json", raws["spine.json"]), ("uses.json", raws["uses.json"])] + [(rel, raws[rel]) for rel in steps]}
    lines = ["ASM-STATIC " + " ".join(e[1:]) for e in _graph_static_problems(json_files)]   # A19: after the pin stage, before the asset faults are reported; the builder's function, as `_run` calls it
    if lines:
        print("\n".join(lines))
        return 1
    if errors:
        print("\n".join("ASM-ASSET " + " ".join(e[1:]) for e in errors))
        return 1
    if not assets:
        print("ASM-ASSET graph no-assets")
        return 1
    shell_bytes = raws["shell"]
    errors = _graph_sink_errors(assets, shell_bytes)
    if errors:
        print("\n".join("ASM-SINK " + e[2] for e in errors))
        return 1
    names = set(DATA_FIXED) | set(steps) | set(assets) | {"index.html", "manifest.json"} | ({CREDITS_REL} if "page" in raws else set())   # the names the tree will hold (manifest.json is written after the page, and is a file of the tree)
    lines, page = _stage_page(shell_bytes, assets, objs["strings"], objs["index.json"], names, raws.get("page"), pin=pin)
    if lines:
        print("\n".join(lines))
        return 1
    pairs = ([("index.json", index_bytes), ("spine.json", raws["spine.json"]), ("uses.json", raws["uses.json"])] + [(rel, raws[rel]) for rel in steps]
             + ([(CREDITS_REL, raws["page"])] if "page" in raws else []) + sorted(assets.items()) + [("index.html", page.encode("utf-8"))])
    names = [rel for rel, _data in pairs]
    lines = ["ASM-ASSET " + " ".join(e[1:]) for e in _graph_asset_errors(index["assets"], {"graph/" + rel: data for rel, data in pairs})]   # empty by construction
    lines += [f"ASM-OUT {rel} twice" for rel in sorted(set(r for r in names if names.count(r) > 1))]
    lines += [f"ASM-OUT {rel} name" for rel in names if not rel or rel.startswith("/") or "" in rel.split("/") or ".." in rel.split("/")
              or not _contained(out, os.path.join(out, *rel.split("/")))]
    if os.path.islink(out):
        lines.append(f"ASM-OUT {out} symlink")
    elif os.path.exists(out) and not os.path.isdir(out):
        lines.append(f"ASM-OUT {out} not-a-directory")
    elif os.path.isdir(out) and os.listdir(out):
        lines.append(f"ASM-OUT {out} not-empty")
    if lines:
        print("\n".join(lines))
        return 1
    files = dict(sorted(pairs))
    manifest = _manifest_bytes(files, {"notes": pin}, {"steps": len(steps)}, None, None)
    files["manifest.json"] = manifest
    try:
        _publish(out, files)
    except OSError as e:
        print(f"ASM-OUT {out} {e.strerror or type(e).__name__}")
        return 1
    print(f"assembled {len(steps)} steps, {len(files)} files, into {out}")
    if "page" not in raws:   # A20
        print(NO_PAGE_NOTE)
    return 0


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
import contextlib
import hashlib
import io
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

SMALL_BODY = "### The last file\n\n- `New/Main` (1): Plum breadcrumbs with Ox q > 3/4 for ducks at a bright doorway\n"   # a synthetic step file of the same size as the smallest real one
SMALL_SRCS = {"New/Main": sk._lean()}
TEMPLATE_STEP = ('{"card":{"child_count":1,"child_kind":"file","id":"lean-the-last-file","kind":"part","path":[],"proof":"none","state":"none","title":"The last file"},'
                 '"children":[{"child_count":0,"id":"lean-main","kind":"file","parent_rests_on":false,"path":["lean-the-last-file"],"proof":"none","state":"none",'
                 '"title":"Plum breadcrumbs with Ox q > 3/4 for ducks at a bright doorway"}],"commit":"72fead102f663d5c7a407964a13dc0cf9d977207","format":1,'
                 '"id":"lean-the-last-file","path":[],"rests_on":[]}')   # a synthetic step file of the same size as the smallest real one (the template of every extra step file below)
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
SHELL_READINGS = SHELL.replace('<p class="sentence">{{S:sentence}}</p>\n', '<p class="sentence">{{S:sentence}}</p>\n<p class="sentence">{{S:readings_front}}</p>\n')   # the variant that holds the A18 key
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
    return [x for k, v in pairs if k not in drop for x in (k, over.get(k[2:], v))] + list(w.get("page_argv", ()))   # a world made by `_page_world` also passes --page (A20 on)


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
    argv = _argv(w) if argv is None else argv
    rc, lines, err = _cli(argv, **kw)
    if rc != 0 or err or len(lines) != (1 if "--page" in argv else 2) or (len(lines) == 2 and lines[1] != NO_PAGE_LINE):   # A20: no --page, the second line is the note; --page, the one line
        raise AssertionError(f"a clean world must build: exit {rc}, stdout {lines!r}, stderr {err[-300:]!r}")
    return _read_tree(w["out"])


def _expected_page(w, shell_text, strings):
    """The page the builder's own function makes (the contract's A7 call), for the comparison of the written index.html."""
    errs, page = _graph_page(shell_text.encode("utf-8"), set(w["assets"]), strings, "<p>" + bs._e(strings[ABOUT_KEY]) + "</p>", "",
                             shell_keys=SHELL_KEYS, section_attrs=PAGE_SECTION_ATTRS)
    if errs:
        raise _FixtureError(f"the builder refuses the fixture page: {errs}")
    return page


NO_PAGE_LINE = "note: no credits page (--page credits/index.html=PATH); place.mjs refuses a tree without it"   # the second line of a run without --page (A20), pinned as a literal
TEST_REL = "credits/index.html"
CREDITS_KEYS = ("about_credits_before", "about_credits_link", "about_credits_after")
CREDITS_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Synthetic credits page</title>
<style>body { margin: 2em; }</style>
</head>
<body>
<main>
<h1>Synthetic credits page</h1>
<p>Invented words only: zorble, quenta, plimmish.</p>
</main>
</body>
</html>
"""   # SYNTHETIC (invented words), scanner-clean, no ref at all (a page with a `..` ref would go red under M-q in every case that builds)
VIEWPORT_LINE = '<meta name="viewport" content="width=device-width, initial-scale=1">\n'


def _page_strings(**over):
    """The `--strings` file of a run with --page: the skeleton strings, about_text, and the three keys of the About link (A24)."""
    return _asm_strings(**dict({"about_credits_before": "Licence and credits: ", "about_credits_link": "the credits page", "about_credits_after": " (synthetic)."}, **over))


def _page_world(d, text=CREDITS_PAGE, rel=TEST_REL, strings_over=None, **kw):
    """`_world` plus a credits page file `credits.html` in the case's folder and the three About-link keys in the strings; `_argv(w)` then passes `--page REL=PATH`."""
    w = _world(d, strings=_page_strings(**(strings_over or {})), **kw)
    w["page"] = os.path.join(d, "credits.html")
    _put(w["page"], text)
    w["page_argv"] = ["--page", rel + "=" + w["page"]]
    return w


def _put(path, text):
    with open(path, "wb") as f:
        f.write(text if isinstance(text, bytes) else text.encode("utf-8"))


def _unlink(path):
    if os.path.isdir(path) and not os.path.islink(path):
        shutil.rmtree(path)
    elif os.path.lexists(path):
        os.remove(path)


def _expected_credits_page(w, strings, with_link=True):
    """The index.html the contract (A24) makes, from the builder's own function: about_text in one paragraph, then (with a page) a second paragraph with the escaped BEFORE, `<a href="credits/">`, the
    escaped LINK, `</a>` and the escaped AFTER. Built with `section_attrs=()` (compare through `_no_feedback`), so it does not depend on the A7/A8 attribute."""
    about = "<p>" + _e(strings[ABOUT_KEY]) + "</p>"
    if with_link:
        about += "<p>" + _e(strings[CREDITS_KEYS[0]]) + '<a href="credits/">' + _e(strings[CREDITS_KEYS[1]]) + "</a>" + _e(strings[CREDITS_KEYS[2]]) + "</p>"
    errs, page = _graph_page(SHELL.encode("utf-8"), set(w["assets"]), strings, about, "", shell_keys=SHELL_KEYS, section_attrs=())
    if errs:
        raise _FixtureError(f"the builder refuses the fixture page: {errs}")
    return page


def _no_feedback(page):
    return page.replace(' data-page-feedback="off"', "")


def _limit_writes(n):
    """A preexec function: no file of the child may exceed n bytes (SIGXFSZ ignored, so a write fails with EFBIG instead of killing the child)."""
    def f():
        import resource
        import signal
        signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
        resource.setrlimit(resource.RLIMIT_FSIZE, (n, n))
    return f


# ---------------------------------------------------------------- the mutation controls: exact specifications, for phase 2 to turn into live checks

CLAUSES = tuple(f"A{i}" for i in range(1, 19)) + ("A7b-element", "A7b-static", "A7b-head", "A7b-surface", "A11b", "A11b-attrs", "A19", "A19-call") + tuple(f"A{i}" for i in range(20, 28))   # A7b is four cases, one per check the builder's `_run` applies; A11b and A19 are two
MUTATIONS = {
    "M-a": ("A3", "in the pin stage, skip the comparison of `commit` with --pin for every step/<id>.json (index.json, spine.json and uses.json are still compared)", ("A3",)),
    "M-b": ("A1", "in the data stage, read a step/<id>.json that is a symlink as if it were a regular file (follow it; no `symlink` refusal for it). Every other symlink refusal "
                  "(index/spine/uses, folders, --strings, --shell) is unchanged", ("A1",)),
    "M-c": ("A9", "write index.json with the right `assets` but through `json.dumps({**{k: v for k, v in obj.items() if k != 'assets'}, 'assets': new_assets}, indent=1, "
                  "ensure_ascii=False) + '\\n'` (`assets` LAST, no sort_keys, no `_graph_bytes`, so no \\u003c escapes): the parsed object is the same, its key order and bytes are not", ("A9",)),
    "M-d": ("A12", "build the manifest `files` map from every written file EXCEPT index.html", ("A12",)),
    "M-e": ("A12", "write the manifest with `\"release_id\": null` present (build the manifest object by hand with release_id None instead of omitting the key)", ("A12",)),
    "M-f": ("A13", "list the step files (for reading and for the order of the refusal lines) in REVERSE name order instead of ascending name order", ("A13",)),
    "M-g": ("A4", "skip the not-empty check: a non-empty OUT_DIR is written into, no `ASM-OUT <path> not-empty`", ("A4",)),
    "M-h": ("A7", "call `_graph_page` with `section_attrs=()` so the section carries no `data-page-feedback`", ("A7", "A8")),
    "M-i": ("A5", "take the shell bytes from the third return value of `_graph_assets(graph_src)` when it is not None (and from --shell only when it is None)", ("A5",)),
    "M-j": ("A18", "fill the readings front line with the list's length plus one (`str(len(rows) + 1)` instead of `str(len(rows))`): the written line is then not `template.replace(\"{n}\", str(len(list)))`", ("A18",)),
    "M-k": ("A7b-element", "skip `graph_element_problems` on the assembled page (the call is dropped from the checks of `_stage_page`; static, head and surface checks stay): the element call-site case "
                           "A7b-element is red, A7b-static, A7b-head and A7b-surface and every other A-case stay green", ("A7b-element",)),
    "M-l": ("A19", "skip the static check of the data files (no call of `_graph_static_problems` over the JSON files about to be written): both A19 cases are red (the refusal of a token in "
                   "index, spine, uses and a step file, and the call-site case), every other A-case stays green", ("A19", "A19-call")),
    "M-m": ("A11b", "skip the ref check of the written page (the call that scans the assembled page's `href`, `src`, `action`, `srcset`, `poster` and `data` values for an absolute, `..` or "
                    "missing ref is dropped from `_stage_page`; the builder's own checks stay): the A11b case is red (a shell holding `../x.html` or `nothere.html` builds, exit 0), every "
                    "other A-case stays green except A11b-attrs, which reads the same call through a stand-in page and goes red with it", ("A11b", "A11b-attrs")),
    "M-n": ("A11b-attrs", "cut `src` from REF_ATTRS (the one-token edit: `REF_ATTRS = (\"href\", \"action\", \"srcset\", \"poster\", \"data\")`): a script whose src is `../x.js`, `nothere.js` or `/x.js` "
                          "is no longer refused by the ref check, so the A11b-attrs case is red; A11b (a shell with `href` refs) and every other A-case stay green, A11b-attrs being the only case that reads `src`",
           ("A11b-attrs",)),
    "M-o": ("A24", "take the href of the About link from the strings (`strings.get(\"about_credits_href\", \"credits/\")`) instead of deriving it from the folder of REL: a strings file that carries an extra "
                   "`about_credits_href` key changes the written link, so A24 is red; every other A-case (their strings carry no such key) stays green", ("A24",)),
    "M-p": ("A25", "leave credits/index.html out of the manifest `files` map (the page is still written to the tree and still counted in the report): A25 is red (the manifest has no entry for it); A12 "
                   "(a run without --page) and every other A-case stay green", ("A25",)),
    "M-q": ("A23", "resolve the credits page's refs with base \"\" (the index.html rules) instead of its own folder: `../graph.css`, `../index.html`, `../` are then `escapes` and `./` is `missing`, so A23 is red; "
                   "no other case builds with a page that holds a `..` ref, so every other A-case stays green", ("A23",)),
    "M-r": ("A22", "do not apply `element_problems` to the credits page (the call is dropped from its checks; static, head and link checks stay): a page with a `<script>`, an inline handler or a `<base>` builds, "
                   "so A22 is red; every other A-case stays green", ("A22",)),
    "M-s": ("A27", "ignore the pin in the credits page's outbound-link check (the commit after `tree/` or `blob/` is accepted when it is any 40-hex commit, not the run's --pin): a link at another commit is then "
                   "allowed, so A27 is red; no other case builds a page with such a link, so every other A-case stays green", ("A27",)),
    "M-t": ("A27", "loosen the repository constant of the credits page's outbound-link check to `https://github.com/` (the repository is no longer the one `lsernau/grh-lean`): the allowed set is no longer the "
                   "one repository's, so A27 is red; no other case builds a page with an outbound link, so every other A-case stays green", ("A27",)),
}


# The wrong implementation of each control as ONE textual change: (the exact text in the tool above the self-test marker, which must occur once; its replacement). Applied to a TEMPORARY COPY of
# the tools/ folder, never to the committed file.
MUTATION_EDITS = {
    "M-a": ('        if found != pin:\n', '        if found != pin and not rel.startswith("step/"):\n'),
    "M-b": ('        raw = _read_in(root, path, limit)\n',
            '        raw = sk._read_bounded(path, limit, guards=()) if name.startswith("step/") and os.path.islink(path) else _read_in(root, path, limit)\n'),
    "M-c": ('    index_bytes = _graph_bytes({"x": index})["x"]\n',
            '    index_bytes = (json.dumps({**{k: v for k, v in index.items() if k != "assets"}, "assets": index["assets"]}, indent=1, ensure_ascii=False) + "\\n").encode("utf-8")\n'),
    "M-d": ('    manifest = _manifest_bytes(files, {"notes": pin}, {"steps": len(steps)}, None, None)\n',
            '    manifest = _manifest_bytes({k: v for k, v in files.items() if k != "index.html"}, {"notes": pin}, {"steps": len(steps)}, None, None)\n'),
    "M-e": ('    manifest = _manifest_bytes(files, {"notes": pin}, {"steps": len(steps)}, None, None)\n',
            '    manifest = (_dump(dict(json.loads(_manifest_bytes(files, {"notes": pin}, {"steps": len(steps)}, None, None)), release_id=None)) + "\\n").encode("utf-8")\n'),
    "M-f": ('names = sorted(os.listdir(path))', 'names = sorted(os.listdir(path), reverse=True)'),   # the step files are read in REVERSE name order
    "M-g": ('    elif os.path.isdir(out) and os.listdir(out):\n', '    elif False:\n'),
    "M-h": ('shell_keys=SHELL_KEYS, section_attrs=PAGE_SECTION_ATTRS)', 'shell_keys=SHELL_KEYS, section_attrs=())'),   # (A24 builds `about` on its own line before this call, so the edit no longer includes the about text)
    "M-i": ('    shell_bytes = raws["shell"]\n', '    shell_bytes = _graph_src_shell if _graph_src_shell is not None else raws["shell"]\n'),
    "M-j": ('**{READINGS_FRONT_KEY: template.replace("{n}", str(len(rows)))}', '**{READINGS_FRONT_KEY: template.replace("{n}", str(len(rows) + 1))}'),
    "M-k": ('static_problems(page, "") + graph_element_problems(page) + head_meta_problems(page)', 'static_problems(page, "") + [] + head_meta_problems(page)'),
    "M-l": ('    lines = ["ASM-STATIC " + " ".join(e[1:]) for e in _graph_static_problems(json_files)]', '    lines = []'),
    "M-m": ('    lines += _ref_problems(page, names)', '    lines += []'),
    "M-n": ('REF_ATTRS = ("href", "src", "action", "srcset", "poster", "data")', 'REF_ATTRS = ("href", "action", "srcset", "poster", "data")'),
    "M-o": ("""'<a href="' + CREDITS_DIR + '">'""", """'<a href="' + strings.get("about_credits_href", CREDITS_DIR) + '">'"""),
    "M-p": ('    manifest = _manifest_bytes(files, {"notes": pin}, {"steps": len(steps)}, None, None)\n',
            '    manifest = _manifest_bytes({k: v for k, v in files.items() if k != "credits/index.html"}, {"notes": pin}, {"steps": len(steps)}, None, None)\n'),
    "M-q": ('_ref_problems(cpage, names, CREDITS_DIR, CREDITS_REL, link_pin=pin)', '_ref_problems(cpage, names, "", CREDITS_REL, link_pin=pin)'),   # (A27 added the keyword; the same wrong implementation)
    "M-r": ('static_problems(cpage, "") + element_problems(cpage) + head_meta_problems(cpage)', 'static_problems(cpage, "") + [] + head_meta_problems(cpage)'),
    "M-s": ('return commit == pin and (sep == "/" or kind == "tree/")', 'return bool(_PIN.fullmatch(commit)) and (sep == "/" or kind == "tree/")'),
    "M-t": ('CREDITS_REPO = "https://github.com/lsernau/grh-lean/"', 'CREDITS_REPO = "https://github.com/"'),
}
MUTATION_TIMEOUT = 120   # seconds, for the self-test of one mutated copy


def _mutation_case(mid):
    """The live check of one control: the self-test's A-cases (not the M-cases: no recursion) run in a SUBPROCESS on a mutated COPY of the tools/ folder; the set of red cases must be exactly
    the set the control specifies (the new case red AND every other A-case green). Prints the observed red set; a mutation that reddens something extra, or nothing, fails."""
    primary, change, red = MUTATIONS[mid]
    green = tuple(c for c in CLAUSES if c not in red)
    bad = [c for c in red if c not in CLAUSES]
    if bad or primary not in red or not red or set(red) | set(green) != set(CLAUSES) or set(MUTATION_EDITS) - set(MUTATIONS):
        return False, f"the specification of {mid} is malformed: {bad}"
    if mid not in MUTATION_EDITS:   # a specification written before its live check (the cases come first)
        raise _SkipCase(f"not yet a live check. WRONG IMPLEMENTATION: {change}. MUST GO RED (and only these): {', '.join(red)}. MUST STAY GREEN: {', '.join(green)}")
    old, new = MUTATION_EDITS[mid]
    with open(TOOL, encoding="utf-8") as f:
        src = f.read()
    marker = "\n# ==== self-test" + " ====\n"
    if src.count(marker) != 1:
        raise _FixtureError("the self-test marker must appear once in the tool")
    head, tail = src[:src.index(marker)], src[src.index(marker):]
    if head.count(old) != 1:
        raise _FixtureError(f"the text mutated by {mid} occurs {head.count(old)} times in the tool, not once")
    with _tmp() as d:
        copy = os.path.join(d, "repo", "tools")   # the fixtures read the repository's own site/strings.json beside tools/, so the copy keeps that layout
        shutil.copytree(_HERE, copy, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        shutil.copytree(os.path.join(os.path.dirname(_HERE), "site"), os.path.join(d, "repo", "site"))
        with open(os.path.join(copy, os.path.basename(TOOL)), "w", encoding="utf-8") as f:
            f.write(head.replace(old, new) + tail)
        try:
            r = subprocess.run([sys.executable, "-I", os.path.join(copy, os.path.basename(TOOL)), "--selftest", "--only", ",".join(CLAUSES)], capture_output=True, text=True,
                               timeout=MUTATION_TIMEOUT)
        except subprocess.TimeoutExpired:
            return False, f"{mid}: the self-test of the mutated copy did not finish in {MUTATION_TIMEOUT} s"
    seen = {m.group(1): m.group(2) for m in re.finditer(r"^CASE (\S+) (PASS|FAIL|SKIP)", r.stdout, re.M)}
    if sorted(seen) != sorted(CLAUSES):
        return False, f"{mid}: the mutated copy reported {sorted(seen)}, not every A-case; stderr {r.stderr[-300:]!r}"
    observed = sorted((c for c in CLAUSES if seen[c] != "PASS"), key=CLAUSES.index)
    print(f"  {mid} ({change[:70]}...): red set observed {observed}, specified {list(red)}")
    return _eq(observed, sorted(red, key=CLAUSES.index))


# ---------------------------------------------------------------- the A16 scan: an ALLOWLIST LINT over the text of the tool above the marker. It flags the routes it models (below) and claims nothing about
# the others (`sys.modules['builtins'].eval`, subscripting a namespace dict, a write through a helper reached by another name, ...): the dynamic half of case A16 is the real check.

A16_IMPORTS = ("importlib.util", "json", "os", "re", "sys")   # `import X`, unaliased, for exactly these modules and no others
A16_FROM = {"html.parser": ("HTMLParser",)}                    # `from M import N`, unaliased, for exactly these and no others
A16_OS = ("listdir", "path")                                   # the attributes of `os` the tool uses today
A16_OS_PATH = ("abspath", "dirname", "exists", "isdir", "islink", "join", "lexists")   # and of `os.path`
A16_NAMES = ("eval", "exec", "compile", "__import__", "getattr", "setattr", "delattr", "vars", "globals", "locals", "open", "__builtins__")   # names that reach anything by a string, or write a file the tool does not name (it opens files only through `_read_in` and `_publish`), in any use
A16_MODULES = ("os", "subprocess", "sys", "ctypes", "pickle", "runpy", "marshal", "importlib")   # the restricted modules: reached only as the plain names imported at the top, never as an attribute of another object
A16_DUNDER = ("__dict__", "__globals__", "__builtins__", "__class__", "__subclasses__", "__code__")   # attribute names that walk from an object to the namespaces and classes around it, on any base
A16_ATTRS = re.compile(r"system|popen|exec\w*|spawn\w*|posix_spawn\w*|fork\w*|Popen|check_output|check_call|getoutput|getstatusoutput")   # attribute names that run a program, on any base


def _scan_source(src, loader="_load"):
    """The findings of the A16 allowlist over the Python text `src`: an import that is not one of A16_IMPORTS / A16_FROM (or is aliased), a use of a name of A16_NAMES, an attribute that runs
    a program or one of A16_DUNDER, an attribute of `os` or `os.path` the tool does not use, `importlib` used outside the function `loader`. [] means clean."""
    tree = ast.parse(src)
    inside = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.FunctionDef) and n.name == loader:
            inside |= {id(x) for x in ast.walk(n)}
    found = []
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            found += [f"line {n.lineno}: import {a.name}" + (f" as {a.asname}" if a.asname else "") for a in n.names if a.asname is not None or a.name not in A16_IMPORTS]
        elif isinstance(n, ast.ImportFrom):
            if n.level or n.module not in A16_FROM or any(a.asname is not None or a.name not in A16_FROM[n.module] for a in n.names):
                found.append(f"line {n.lineno}: from {'.' * n.level}{n.module or ''} import {', '.join(a.name for a in n.names)}")
        elif isinstance(n, ast.Name):
            if n.id in A16_NAMES:
                found.append(f"line {n.lineno}: name {n.id}")
        elif isinstance(n, ast.Attribute):
            base = n.value
            if n.attr == "exec_module" and id(n) in inside:   # the one place a module of this folder is executed: `_load`, which loads the two builders
                continue
            if A16_ATTRS.fullmatch(n.attr):
                found.append(f"line {n.lineno}: attribute .{n.attr}")
            elif n.attr in A16_DUNDER:
                found.append(f"line {n.lineno}: attribute .{n.attr}")
            elif n.attr in A16_MODULES:
                found.append(f"line {n.lineno}: module {n.attr} reached as an attribute")
            elif isinstance(base, ast.Name) and base.id == "os" and n.attr not in A16_OS:
                found.append(f"line {n.lineno}: os.{n.attr}")
            elif isinstance(base, ast.Attribute) and isinstance(base.value, ast.Name) and (base.value.id, base.attr) == ("os", "path") and n.attr not in A16_OS_PATH:
                found.append(f"line {n.lineno}: os.path.{n.attr}")
            elif isinstance(base, ast.Name) and base.id == "importlib" and id(n) not in inside:
                found.append(f"line {n.lineno}: importlib.{n.attr} outside {loader}")
    return list(dict.fromkeys(found))


A16_LURES = (   # (what, source): each must be FLAGGED by the scan, or the scan is blind to it and the case fails
    ("bs.os.system(...)", "bs.os.system('x')\n"), ("sk.os.remove(p)", "sk.os.remove(p)\n"), ("bs.subprocess.run(...)", "bs.subprocess.run(['x'])\n"),
    ("bs.os.path.getsize(p) (an os attribute reached through another module)", "bs.os.path.getsize(p)\n"), ("x = bs.os; x.system(...)", "x = bs.os\nx.system('y')\n"),
    ("getattr(bs, 'os')", "getattr(bs, 'os')\n"), ("bs.sys.modules", "bs.sys.modules\n"),
    ("import subprocess", "import subprocess\n"), ("import subprocess as sp", "import subprocess as sp\n"), ("from subprocess import run", "from subprocess import run\n"),
    ("from os import system", "from os import system\n"), ("from os import popen", "from os import popen\n"), ("from os import execv", "from os import execv\n"),
    ("from os import spawnl", "from os import spawnl\n"), ("from os import posix_spawn", "from os import posix_spawn\n"), ("from os import path", "from os import path\n"),
    ("alias: import os as o; o.system(...)", "import os as o\no.system('x')\n"), ("os.system(...)", "import os\nos.system('x')\n"), ("os.popen(...)", "import os\nos.popen('x')\n"),
    ("os.execv(...)", "import os\nos.execv('/bin/sh', [])\n"), ("os.spawnl(...)", "import os\nos.spawnl(0, '/bin/sh')\n"), ("os.fork()", "import os\nos.fork()\n"),
    ("os.remove (an os attribute the tool does not use)", "import os\nos.remove('x')\n"), ("os.path.getsize (an os.path attribute the tool does not use)", "import os\nos.path.getsize('x')\n"),
    ("getattr(os, 'system')", "import os\ngetattr(os, 'system')('x')\n"), ("sys.modules['os'].system", "import sys\nsys.modules['os'].system('x')\n"),
    ("eval", "eval('1')\n"), ("exec", "exec('x = 1')\n"), ("compile", "compile('1', 'x', 'eval')\n"), ("__import__", "__import__('os')\n"), ("a name bound to eval", "f = eval\n"),
    ("__dict__ (a chain from a function to its globals)", "x = f.__dict__\n"), ("__globals__", "g = f.__globals__\n"), ("__builtins__ as an attribute", "b = f.__builtins__\n"),
    ("__class__", "c = x.__class__\n"), ("__subclasses__", "s = object.__subclasses__()\n"), ("__code__", "c = f.__code__\n"),
    ("the name __builtins__ (subscripted)", "__builtins__['eval']('1')\n"), ("the name open (a write)", "open('x', 'w').write('y')\n"), ("the name open (bound)", "f = open\n"),
    ("import shutil", "import shutil\n"), ("from shutil import copy", "from shutil import copy\n"), ("import tempfile", "import tempfile\n"), ("import builtins", "import builtins\n"),
    ("from builtins import eval", "from builtins import eval\n"), ("import os as o (the alias alone)", "import os as o\n"),
    ("import ctypes", "import ctypes\n"), ("import pickle", "import pickle\n"), ("import runpy", "import runpy\n"), ("import marshal", "import marshal\n"), ("bare import importlib", "import importlib\n"),
    ("exec_module outside _load", "def f(spec, mod):\n    spec.loader.exec_module(mod)\n"), ("from importlib import import_module", "from importlib import import_module\n"), ("importlib used outside _load", "import importlib.util\nimportlib.util.module_from_spec(1)\n"),
)
A16_CLEAN = (   # (what, source): each must be NOT flagged (the scan is an allowlist, not a ban on everything)
    ("os.path and os.listdir", "import os\nos.path.join('a', 'b')\nos.listdir('.')\nos.path.lexists('x')\n"), ("json, re, sys", "import json\nimport re\nimport sys\njson.loads('1')\nre.compile('x')\nsys.exit(0)\n"),
    ("HTMLParser", "from html.parser import HTMLParser\n\n\nclass P(HTMLParser):\n    pass\n"),
    ("bs.<function> and sk.<function> uses", "x = bs._graph_assets(1)\ny = sk._read_in(1, 2, 3)\nz = sk.SourceError\n"), ("bs.CODE_ON_SURFACE_REFUSES", "if bs.CODE_ON_SURFACE_REFUSES:\n    pass\n"),
    ("dunder names and attributes the tool does use", "x = __file__\nif __name__ == '__main__':\n    pass\ny = f.__name__\n"),
    ("names that merely contain `open`", "def reopen(p):\n    return p\n\n\nreopen(1)\nbs.open_page\nsk.is_open\n"),
    ("exec_module inside _load", "def _load(spec, mod):\n    spec.loader.exec_module(mod)\n"), ("importlib inside _load", "import importlib.util\n\n\ndef _load(p):\n    return importlib.util.spec_from_file_location('k', p)\n"),
)


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
                "(its files untouched); an OUT_DIR that is a symlink (to a folder) is `ASM-OUT <out> symlink`, one that is an existing file `ASM-OUT <out> not-a-directory`, neither touched; writes go "
                "to files inside OUT_DIR only (nothing is left beside it). A name with `..` or a leading `/` (`ASM-OUT <name> name`) and two inputs mapping to one path (`ASM-OUT <path> twice`) cannot "
                "be reached from the command line, because every name comes from a source that is already checked: an IN-PROCESS case (a stand-in `_graph_assets`) drives each")
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
            ok, why = _eq((rc, lines, "Traceback" in err, _read_tree(w["out"]) == before), (1, [f"ASM-OUT {w['out']} not-empty"], False, True))
            if not ok:
                return ok, why
        with _tmp() as d:   # OUT is a symlink to a folder: refused, the folder it points to is untouched and still holds only what it held
            w = _world(d)
            target = os.path.join(d, "target")
            _write_tree(target, {"keep.txt": b"mine"})
            os.symlink(target, w["out"])
            rc, lines, err = _cli(_argv(w))
            ok, why = _eq((rc, lines, "Traceback" in err, os.path.islink(w["out"]), os.readlink(w["out"]) == target, _read_tree(target)), (1, [f"ASM-OUT {w['out']} symlink"], False, True, True,
                                                                                                                                            ({"keep.txt": b"mine"}, [])))
            if not ok:
                return ok, "OUT a symlink to a folder: " + why
        with _tmp() as d:   # OUT is an existing FILE: refused, the file is untouched
            w = _world(d)
            with open(w["out"], "wb") as f:
                f.write(b"mine")
            before = sorted(os.listdir(d))
            rc, lines, err = _cli(_argv(w))
            with open(w["out"], "rb") as f:
                kept = f.read()
            ok, why = _eq((rc, lines, "Traceback" in err, kept, sorted(os.listdir(d))), (1, [f"ASM-OUT {w['out']} not-a-directory"], False, b"mine", before))
            if not ok:
                return ok, "OUT an existing file: " + why
        # the two refusals the command line cannot reach, `name` and `twice`: IN-PROCESS (the A7b pattern), stand-ins for `_graph_assets` (one more asset) and the sink gate (which re-reads graph-src)
        for what, extra, want in (("a name with `..`", "../evil.js", "ASM-OUT ../evil.js name"), ("a name that is also a fixed file", "index.json", "ASM-OUT index.json twice")):
            with _tmp() as d:
                w = _world(d)
                before = sorted(os.listdir(d))
                real = tool_module()._graph_assets

                def fake(src, extra=extra, real=real):
                    errs, assets, shell = real(src)
                    return errs, dict(assets, **{extra: b"export const extra = 1;\n"}), shell
                rc, lines = inproc(w, {"_graph_assets": fake, "_graph_sink_errors": lambda assets, shell: []})   # the real sink gate re-reads graph-src and counts its files: the extra asset is not there
                ok, why = _eq((rc, lines, os.path.exists(w["out"]), sorted(os.listdir(d))), (1, [want], False, before))
                if not ok:
                    return ok, f"in-process, {what}: " + why
        return True, ""

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
        with _tmp() as d:   # the pin stage hides the static stage: a bad pin AND a static-check token in a data file, only the pin line is printed
            w = _world(d, big=True)
            spine = with_token(w["files"]["spine.json"])
            if not _graph_static_problems({"graph/spine.json": spine}):   # fixture control, on the builder's own function: the planted token IS a static refusal
                raise _FixtureError("the builder's static check accepts the planted token")
            _write_tree(w["data"], {"index.json": _recommit(w["files"]["index.json"], BAD_PIN), "spine.json": spine})   # (index.json, not a step file: M-a skips the step pins and must redden A3 only)
            good, why = _refused(w, _argv(w), [f"ASM-PIN index.json {BAD_PIN}"], "a bad pin hides the static token of the data files")
            if not good:
                return good, why
        _need_pr_c()
        with _tmp() as d:   # a page fault and a non-empty OUT_DIR: the page stage answers, the out stage is never reached
            w = _world(d, strings=_asm_strings(**{ABOUT_KEY: None}))
            _write_tree(w["out"], {"keep.txt": b"mine"})
            return _refused(w, _argv(w), ["ASM-STRINGS about_text missing"], "a page fault hides a non-empty OUT_DIR", out_state=["keep.txt"])

    @case("A16", "never executes anything it reads: no import, eval, subprocess or shell on DATA, strings, shell or assets. STATIC (a LINT over the routes it models, not a closed set: it does not claim that no other route to execution or to a write exists, e.g. "
                 "`sys.modules['builtins'].eval`, a subscript of a namespace dict, `shutil`-style helpers reached by another name; the DYNAMIC half below is the real check): the text of the tool "
                 "above the self-test marker passes the scan (imports exactly importlib.util, json, os, re, sys and `from html.parser import HTMLParser`, unaliased; no use of the names eval, exec, "
                 "compile, __import__, getattr, setattr, delattr, vars, globals, locals, open or __builtins__; no attribute that runs a program; none of the attributes __dict__, __globals__, "
                 "__builtins__, __class__, __subclasses__ or __code__; no attribute of os or os.path beyond the ones the tool uses; importlib and `exec_module` only inside `_load`), and "
                 "the scan has its own positive controls (small sources, each of which it must FLAG: a scan that flags nothing fails here; shutil, tempfile, builtins and an aliased os among them) and negative controls (the sources it must pass). "
                 "DYNAMIC: lures (code that would create a file) in the strings values, the shell and a step file of a world with a VALID pin create no file, the run reaches the page stage "
                 "and builds, and its tree differs from the same world without lures only where the lures are text")
    def _():
        with _tmp() as d:   # DYNAMIC, the pin stage: lures in every input and a bad pin
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
        _need_pr_c()
        with _tmp() as d:   # DYNAMIC, a VALID pin: the lures are in a strings value (and an unused strings key), the shell text and a step file; the run reaches the page stage and builds
            with _tmp() as d0:
                base = _ok_run(_world(d0, big=True))[0]
            w = _world(d, big=True)
            canary = os.path.join(d, "CANARY")
            lure = f"__import__('os').system('touch {canary}'); $(touch {canary}); `touch {canary}`"
            step = _step_names(w["files"])[0]
            lured_step = _graph_bytes({"x": dict(json.loads(w["files"][step]), zz_lure=lure)})["x"]
            _write_tree(w["data"], {step: lured_step})
            lured_shell = SHELL.replace("</header>", f'<p class="hint">{lure}</p>\n</header>')   # shell TEXT (the builder refuses a comment)
            lured_strings = _asm_strings(**{ABOUT_KEY: lure, "zz_lure": lure})
            with open(w["shell"], "w", encoding="utf-8") as f:
                f.write(lured_shell)
            with open(w["strings"], "w", encoding="utf-8") as f:
                json.dump(lured_strings, f)
            rc, lines, err = _cli(_argv(w))
            if rc != 0 or os.path.exists(canary):
                return False, f"lures with a valid pin: exit {rc}, stdout {lines!r}, canary created {os.path.exists(canary)}, stderr {err[-200:]!r}"
            tree = _read_tree(w["out"])[0]
            changed = sorted(k for k in set(base) | set(tree) if base.get(k) != tree.get(k))
            ok, why = _eq((changed, tree[step], tree["index.html"].decode("utf-8").replace(' data-page-feedback="off"', "")),   # the section attribute is A7's and A8's business (M-h removes it)
                          (sorted([step, "index.html", "manifest.json"]), lured_step, _expected_page(w, lured_shell, lured_strings).replace(' data-page-feedback="off"', "")))
            if not ok:
                return ok, "lures with a valid pin, the tree against the same world without lures: " + why
        with open(TOOL, encoding="utf-8") as f:
            src = f.read()
        marker = "\n# ==== self-test" + " ====\n"
        if src.count(marker) != 1:
            raise _FixtureError("the self-test marker must appear once in the tool")
        blind = [what for what, text in A16_LURES if not _scan_source(text)]   # the scan's own positive controls
        if blind:
            return False, f"the scan is blind to: {blind}"
        wrong = [what for what, text in A16_CLEAN if _scan_source(text)]       # and its negative controls
        if wrong:
            return False, f"the scan flags what it must pass: {wrong}"
        return _eq(_scan_source(src[:src.index(marker)]), [])

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

    @case("A18", "the readings front line: the shell may hold `{{S:readings_front}}` (a SHELL key); its strings value is a template with exactly one `{n}`, filled with the decimal length of the "
                 "list `index.json[READINGS_KEY]` by a function replacement (no pattern in the words matters) and then handed to `_graph_page`, which escapes it: the written line equals "
                 "`template.replace(\"{n}\", str(len(list)))`, escaped, for lengths 0, 1, 10 and 100; refusals by name, nothing written: the value missing or with no `{n}` or with two "
                 "(`ASM-READINGS readings_front template`), the list missing, not a list or with a row that is not an object (`ASM-READINGS <key> shape`); a shell WITHOUT the token needs "
                 "neither the template nor the list; the tool never reads or changes readings_heading, readings_about or readings_byline")
    def _():
        _need_pr_c()
        template = 'Notes \\1 <b>{n}</b> & \\g<0>.'   # words a pattern replacement would read as a group reference, and markup the page must escape

        def make(d, rows, shell=SHELL_READINGS, strings=None, index_over=None):
            w = _world(d, shell=shell, strings=_asm_strings(**{READINGS_FRONT_KEY: template}) if strings is None else strings)
            idx = json.loads(w["files"]["index.json"])
            if rows is not None:
                idx[READINGS_KEY] = rows
            if index_over is not None:
                idx.update(index_over(idx))
            _write_tree(w["data"], {"index.json": _graph_bytes({"x": idx})["x"]})
            return w, idx

        def carried(tree):
            return {k: v for k, v in json.loads(tree["index.json"]).items() if k != "assets"}

        def norm(page):   # the section attribute is A7's and A8's business (M-h removes it): this case is about the front line, so it compares pages without it
            return page.replace(' data-page-feedback="off"', "")

        for n in (0, 1, 10, 100):   # the written line is the template with {n} the list's length, escaped, whatever the words
            with _tmp() as d:
                rows = [{"id": f"r{i}", "title": f"Note {i}"} for i in range(n)]
                w, idx = make(d, rows)
                tree = _ok_run(w)[0]
                page = tree["index.html"].decode("utf-8")
                line = template.replace("{n}", str(len(rows)))
                ok, why = _eq((norm(page), bs._e(line) in page, line in page, f"<b>{n}</b>" in page, carried(tree)),
                              (norm(_expected_page(w, SHELL_READINGS, _asm_strings(**{READINGS_FRONT_KEY: line}))), True, False, False, {k: v for k, v in idx.items() if k != "assets"}))
                if not ok:
                    return ok, f"a list of {n} rows: " + why
        for what, over in (("no value", None), ("no {n}", "Our reading notes. The key lists them."), ("two {n}", "{n} notes and {n} more"), ("an empty value", "")):   # the template refusals
            with _tmp() as d:
                w, _idx = make(d, [{"id": "r"}], strings=_asm_strings(**{READINGS_FRONT_KEY: over}))
                good, why = _refused(w, _argv(w), [f"ASM-READINGS {READINGS_FRONT_KEY} template"], f"the strings value of the front line: {what}")
                if not good:
                    return good, why
        for what, rows in (("no list", None), ("a dict", {"id": "r"}), ("a string", "r1,r2"), ("a number", 3), ("a number as a row", [{"id": "r"}, 3]), ("a list as a row", [[1]]),
                           ("null as a row", [None, None])):   # the shape refusals: ONE line, whatever the number of bad rows
            with _tmp() as d:
                w, _idx = make(d, rows)
                good, why = _refused(w, _argv(w), [f"ASM-READINGS {READINGS_KEY} shape"], f"the readings list is {what}")
                if not good:
                    return good, why
        with _tmp() as d:   # both faults of the stage at once: both reported
            w, _idx = make(d, "x", strings=_asm_strings(**{READINGS_FRONT_KEY: "no braces"}))
            good, why = _refused(w, _argv(w), [f"ASM-READINGS {READINGS_FRONT_KEY} template", f"ASM-READINGS {READINGS_KEY} shape"], "a bad template and a bad list together")
            if not good:
                return good, why
        for rows, strings in ((None, _asm_strings()), ("not a list", _asm_strings(**{READINGS_FRONT_KEY: "no braces"})), ([1, 2], _asm_strings(**{READINGS_FRONT_KEY: "{n} {n}"}))):
            with _tmp() as d:   # a shell WITHOUT the token: neither the template nor the list is needed, and a bad one is not looked at
                w, idx = make(d, rows, shell=SHELL, strings=strings)
                tree = _ok_run(w)[0]
                ok, why = _eq((norm(tree["index.html"].decode("utf-8")), carried(tree)), (norm(_expected_page(w, SHELL, strings)), {k: v for k, v in idx.items() if k != "assets"}))
                if not ok:
                    return ok, f"a shell without the token, list {rows!r}: " + why
        odd = {"readings_heading": "{n} {n}", "readings_about": "<b>{n}</b>", "readings_byline": 7}
        for in_strings in (odd, {}):
            with _tmp() as d:   # the three PAGE keys of the overlay: carried in index.json's strings, never read: odd values change nothing, absent values are no fault
                strings = _asm_strings(**{READINGS_FRONT_KEY: template, **in_strings})
                w, idx = make(d, [{"id": "r"}] * 3, strings=strings, index_over=lambda ix: {"strings": dict(ix["strings"], **odd)})
                tree = _ok_run(w)[0]
                line = template.replace("{n}", "3")
                ok, why = _eq((norm(tree["index.html"].decode("utf-8")), carried(tree)),
                              (norm(_expected_page(w, SHELL_READINGS, _asm_strings(**{READINGS_FRONT_KEY: line, **in_strings}))), {k: v for k, v in idx.items() if k != "assets"}))
                if not ok:
                    return ok, f"the readings_* page keys, strings file holds {sorted(in_strings)}: " + why
        return True, ""

    # ---- phase 3: A7b (the four checks are CALLED), A11b (no absolute refs), A19 (the static check over the data files). IN-PROCESS: the tool is loaded as a module under a private name, the
    # names it binds at import (`graph_element_problems`, ...) are replaced on THAT module for the length of one `run(opts)` call and restored after.
    tool_mod = []

    def tool_module():
        if not tool_mod:
            key = "_asm_under_test"
            spec = importlib.util.spec_from_file_location(key, TOOL)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[key] = mod
            keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True
            try:
                spec.loader.exec_module(mod)
            finally:
                sys.dont_write_bytecode = keep
            tool_mod.append(mod)
        return tool_mod[0]

    def inproc(w, patch, flag=False):
        """(exit code, stdout lines) of `run(opts)` called in this process with the module-level names in `patch` replaced by stand-ins (and CODE_ON_SURFACE_REFUSES forced to `flag`), all restored."""
        m = tool_module()
        absent = [k for k in patch if not hasattr(m, k)]
        if absent:
            raise _Absent("behaviour absent: the tool binds no name " + ", ".join(absent))
        opts = m._parse(_argv(w))
        saved, flag_was, buf = {k: getattr(m, k) for k in patch}, m.bs.CODE_ON_SURFACE_REFUSES, io.StringIO()
        try:
            for k, v in patch.items():
                setattr(m, k, v)
            m.bs.CODE_ON_SURFACE_REFUSES = flag
            with contextlib.redirect_stdout(buf):
                rc = m.run(opts)
        finally:
            for k, v in saved.items():
                setattr(m, k, v)
            m.bs.CODE_ON_SURFACE_REFUSES = flag_was
        return rc, buf.getvalue().splitlines()

    def a7b_refuses(fname, stand_in, want, flag=False):
        """(a) a stand-in returning one problem: `run` returns 1, prints one ASM-PAGE line carrying it, writes nothing (no OUT_DIR, no sibling folder)."""
        _need_pr_c()
        with _tmp() as d:
            w = _world(d)
            before = sorted(os.listdir(d))
            rc, lines = inproc(w, {fname: stand_in}, flag)
            return _eq((rc, len(lines), bool(lines) and lines[0].startswith("ASM-PAGE ") and want in lines[0], os.path.exists(w["out"]), sorted(os.listdir(d))), (1, 1, True, False, before))

    def a7b_records(fname, flag=False):
        """(b) a recording stand-in (the real function inside) is handed, once, the page that is written: the FULL page, not the shell."""
        with _tmp() as d:
            w = _world(d)
            m, seen = tool_module(), []
            real = getattr(m, fname)

            def rec(*a, **k):
                seen.append(a[0])
                return real(*a, **k)
            rc, lines = inproc(w, {fname: rec}, flag)
            if rc != 0:
                return False, f"{fname} recording run: exit {rc}, lines {lines!r}"
            page = open(os.path.join(w["out"], "index.html"), encoding="utf-8").read()
            return _eq((seen == [page], '<section id="graph-about"' in page, ABOUT_TEXT in page, page == SHELL), (True, True, True, False))   # the attribute itself is A7's and A8's business

    @case("A7b-element", "A7b, the element check is CALLED (in-process call-site case): a stand-in `graph_element_problems` that returns one problem makes `run` return 1 with one `ASM-PAGE` line "
                         "carrying it and nothing written (no OUT_DIR, no sibling folder); a recording stand-in is handed the FULL assembled page that is written, never the shell")
    def _():
        ok, why = a7b_refuses("graph_element_problems", lambda page: ["ZZ-ELEMENT"], "ZZ-ELEMENT")
        return (ok, "a stand-in that returns one problem: " + why) if not ok else a7b_records("graph_element_problems")

    @case("A7b-static", "A7b, the static check is CALLED on the page: a stand-in `static_problems` that returns one problem makes `run` return 1 with one `ASM-PAGE` line carrying it, nothing written; a "
                        "recording stand-in is handed the FULL assembled page that is written, never the shell")
    def _():
        ok, why = a7b_refuses("static_problems", lambda page, js: ["ZZ-STATIC"], "ZZ-STATIC")
        return (ok, "a stand-in that returns one problem: " + why) if not ok else a7b_records("static_problems")

    @case("A7b-head", "A7b, the head check is CALLED: a stand-in `head_meta_problems` that returns one problem makes `run` return 1 with one `ASM-PAGE` line carrying it, nothing written; a recording "
                      "stand-in is handed the FULL assembled page that is written, never the shell")
    def _():
        ok, why = a7b_refuses("head_meta_problems", lambda page: ["ZZ-HEAD"], "ZZ-HEAD")
        return (ok, "a stand-in that returns one problem: " + why) if not ok else a7b_records("head_meta_problems")

    @case("A7b-surface", "A7b, the code-on-surface path is CALLED (`surface_scan` then `code_spans`, CODE_ON_SURFACE_REFUSES forced True and restored): a stand-in `code_spans` that returns one span makes "
                         "`run` return 1 with one `ASM-PAGE CODE-ON-SURFACE` line carrying it, nothing written; a recording `surface_scan` is handed the FULL assembled page that is written, and "
                         "the recording `code_spans` is handed what `surface_scan` returned for it")
    def _():
        ok, why = a7b_refuses("code_spans", lambda codes: [("zz-card", "ZZ-CODE", 2)], "CODE-ON-SURFACE index.html:zz-card ZZ-CODE x2", flag=True)
        if not ok:
            return ok, "a stand-in that returns one span: " + why
        ok, why = a7b_records("surface_scan", flag=True)
        if not ok:
            return ok, why
        with _tmp() as d:
            w = _world(d)
            m, spans = tool_module(), []
            real_scan, real_spans = m.surface_scan, m.code_spans

            def rec_spans(codes):
                spans.append(codes)
                return real_spans(codes)
            rc, lines = inproc(w, {"code_spans": rec_spans}, flag=True)
            if rc != 0:
                return False, f"recording run with the flag True: exit {rc}, lines {lines!r}"
            page = open(os.path.join(w["out"], "index.html"), encoding="utf-8").read()
            return _eq(spans == [real_scan(page)[1]], True)

    @case("A11b", "every ref of the written page resolves inside the tree: every `href`, `src`, `action`, `srcset`, `poster` and `data` value of the written index.html, after the part from the "
                  "first `?` or `#` is dropped, is empty (a bare #fragment or ?query passes), or a path that names a file the tree holds (a trailing-slash folder ref holds a file under it); a "
                  "`..` segment is `ASM-PAGE <ref> escapes`, a ref that is not a file of the tree (the shared shell's `list/`) is `ASM-PAGE <ref> missing`, every violation of the page is reported "
                  "together in the order of its first occurrence, exit 1, nothing written; an absolute ref in a shell is refused first, by the builder's own page function (`ASM-PAGE ... is not "
                  "a relative path or #fragment`: that line is the one accepted here, the tool's `absolute` word is for what the builder does not scan)")
    def _():
        _need_pr_c()
        fails = []

        class R(HTMLParser):
            def __init__(self):
                super().__init__()
                self.refs = []

            def handle_starttag(self, tag, attrs):
                self.refs += [(tag, k, v) for k, v in attrs if k in ("href", "src", "action")]

        def link(*refs):   # the shared shell stand-in with only the refs changed: one anchor per ref, after the sentence
            return SHELL.replace('<p class="sentence">{{S:sentence}}</p>\n', '<p class="sentence">{{S:sentence}}</p>\n' + "".join(f'<p class="sentence"><a href="{r}">x</a></p>\n' for r in refs))

        def note(name, ok_why):
            if not ok_why[0]:
                fails.append(f"[{name}] {ok_why[1]}")

        def refused_in_order(name, refs, want):   # exit 1, exactly these lines IN THIS ORDER, nothing written
            with _tmp() as d:
                w = _world(d, shell=link(*refs))
                rc, lines, err = _cli(_argv(w))
                note(name, _eq((rc, lines, "Traceback" in err, os.path.exists(w["out"])), (1, want, False, False)))

        with _tmp() as d:   # a clean world still builds; the refs of its written page all resolve in the tree
            w = _world(d, big=True)
            tree = _ok_run(w)[0]
            p = R()
            p.feed(tree["index.html"].decode("utf-8"))
            bad = [(t, k, v) for t, k, v in p.refs if v and not v.startswith("#") and re.split(r"[?#]", v, maxsplit=1)[0] not in tree]
            note("clean world", _eq((bad, ("link", "href", "graph.css") in p.refs, ("script", "src", "page/app.js") in p.refs), ([], True, True)))
        refused_in_order("../x.html escapes", ["../x.html"], ["ASM-PAGE ../x.html escapes"])
        refused_in_order("a .. segment inside a path escapes", ["step/../../x.json"], ["ASM-PAGE step/../../x.json escapes"])
        refused_in_order("nothere.html is missing", ["nothere.html"], ["ASM-PAGE nothere.html missing"])
        refused_in_order("the shared shell's list/ is missing", ["list/"], ["ASM-PAGE list/ missing"])
        refused_in_order("the query stays in the ref shown", ["nothere.html?v=1"], ["ASM-PAGE nothere.html?v=1 missing"])
        refused_in_order("every violation together, first occurrence order, a repeated ref once", ["nothere.html", "../x.html", "list/", "#top", "list/", "graph.css", "../x.html"],
                         ["ASM-PAGE nothere.html missing", "ASM-PAGE ../x.html escapes", "ASM-PAGE list/ missing"])
        with _tmp() as d:   # refs that pass: a query on an asset, a bare fragment, a file of the tree (a step file), a folder with files under it
            step = _step_names(_data_files())[0]
            refs = ["engine/index.js?v=1", "#top", step, "graph.css#x", "step/", "engine/", "?v=2", "page/app.js"]
            w = _world(d, shell=link(*refs))
            tree = _ok_run(w)[0]
            page = tree["index.html"].decode("utf-8")
            note("refs that pass", _eq([f'<a href="{r}">' in page for r in refs], [True] * len(refs)))
        with _tmp() as d:   # an absolute ref in a shell: the builder's own refusal, as ASM-PAGE, nothing written
            shell = link("/abs.html")
            w = _world(d, shell=shell)
            errs, _p = _graph_page(shell.encode("utf-8"), set(w["assets"]), _asm_strings(), "<p>" + bs._e(ABOUT_TEXT) + "</p>", "", shell_keys=SHELL_KEYS, section_attrs=PAGE_SECTION_ATTRS)
            want = ["ASM-PAGE " + " ".join(e[1:]) for e in errs]
            if not want:
                raise _FixtureError("the builder accepts a shell with an absolute anchor")
            note("/abs.html: the builder's own line", _refused(w, _argv(w), want, "an absolute anchor"))
        with _tmp() as d:
            shell = SHELL.replace('src="page/app.js"', 'src="/page/app.js"')
            w = _world(d, shell=shell)
            errs, _p = _graph_page(shell.encode("utf-8"), set(w["assets"]), _asm_strings(), "<p>" + bs._e(ABOUT_TEXT) + "</p>", "", shell_keys=SHELL_KEYS, section_attrs=PAGE_SECTION_ATTRS)
            want = ["ASM-PAGE " + " ".join(e[1:]) for e in errs]
            if not want:
                raise _FixtureError("the builder accepts a shell with an absolute script src")
            note("an absolute script src: the builder's own line", _refused(w, _argv(w), want, "an absolute script src"))
        return (not fails, "; ".join(fails))

    @case("A11b-attrs", "A11b, every ref attribute is READ (in-process stand-in case, the A7b pattern): the builder's own page function refuses a script whose `src` is not an asset and has no "
                        "`form`, `img`, `video` or `object` in its element table, so the attributes that name a ref are reached only by a stand-in `_graph_page` that returns the real page with one "
                        "element added or changed. `src` (a `<script type=\"module\">`, the real element check left on): `../x.js` is `ASM-PAGE ../x.js escapes`, `nothere.js` is "
                        "`ASM-PAGE nothere.js missing`, `/x.js` is `absolute`; `action`, `srcset` (each candidate), `poster` and `data` (element check stood in) are each refused the same way; every "
                        "sub-check: `run` returns 1, exactly the one expected line, nothing written (no OUT_DIR, no sibling folder). Of these only `href` (an `<a>`) and the `src` of a listed asset can "
                        "be produced by the builder; the other four cannot appear in any page the builder accepts, so this case is their only pin")
    def _():
        _need_pr_c()
        m = tool_module()
        real = m._graph_page
        fails = []

        def page_with(edit):   # a stand-in `_graph_page`: the real page, then one text edit
            def fake(*a, **k):
                errors, page = real(*a, **k)
                return errors, edit(page)
            return fake

        def add(extra):
            return lambda page: page.replace("</body>", extra + "</body>")

        def sub(name, edit, want, element_check=True):
            patch = {"_graph_page": page_with(edit)}
            if not element_check:
                patch["graph_element_problems"] = lambda page: []   # the element table has no form, img, video or object: the ref check is what is under test
            with _tmp() as d:
                w = _world(d)
                before = sorted(os.listdir(d))
                rc, lines = inproc(w, patch)
                ok, why = _eq((rc, lines, os.path.exists(w["out"]), sorted(os.listdir(d))), (1, want, False, before))
                if not ok:
                    fails.append(f"[{name}] {why}")

        script = lambda ref: (lambda page: page.replace('src="page/app.js"', f'src="{ref}"'))
        sub("script src ../x.js", script("../x.js"), ["ASM-PAGE ../x.js escapes"])
        sub("script src nothere.js", script("nothere.js"), ["ASM-PAGE nothere.js missing"])
        sub("script src /x.js", script("/x.js"), ["ASM-PAGE /x.js absolute"])
        sub("form action", add('<form action="../x.cgi"></form>'), ["ASM-PAGE ../x.cgi escapes"], element_check=False)
        sub("img srcset, every candidate", add('<img srcset="graph.css 1x, ../x.png 2x, nothere.png 3x" alt="">'), ["ASM-PAGE ../x.png escapes", "ASM-PAGE nothere.png missing"], element_check=False)
        sub("video poster", add('<video poster="../x.png"></video>'), ["ASM-PAGE ../x.png escapes"], element_check=False)
        sub("object data", add('<object data="nothere.swf"></object>'), ["ASM-PAGE nothere.swf missing"], element_check=False)
        return (not fails, "; ".join(fails))

    def with_token(raw):
        """The same JSON file with one more key whose text the static check refuses (the token is the builder's own: `fetch(`, from its `_API` table), in the builder's serialisation."""
        obj = json.loads(raw.decode("utf-8"))
        obj["zz_note"] = "call fetch(x) here"
        return _graph_bytes({"x": obj})["x"]

    @case("A19", "the static check over the DATA files: a token the static check refuses (the builder's own `fetch(`), placed in index.json, spine.json, uses.json and a step file in turn, is refused "
                 "`ASM-STATIC <token> found in graph/<file>` (the builder's own words, keyed as the builder keys them) naming its file, exit 1, nothing written; every file's problems are reported "
                 "together; this stage comes after the pin stage and BEFORE the assets stage (a token and an asset fault together: only the token is reported); the clean world still builds")
    def _():
        _need_pr_c()
        problem = static_problems("", '"call fetch(x) here"')
        if problem != ["fetch("]:
            raise _FixtureError(f"the static check's refusal of the planted text is {problem!r}, not ['fetch(']")
        with _tmp() as d:
            w = _world(d)
            step = _step_names(w["files"])[0]
            four = ("index.json", "spine.json", "uses.json", step)
            for rel in four:   # one file in turn
                _write_tree(w["data"], {rel: with_token(w["files"][rel])})
                good, why = _refused(w, _argv(w), [f"ASM-STATIC fetch( found in graph/{rel}"], f"the token in {rel} alone")
                if not good:
                    return good, why
                _write_tree(w["data"], {rel: w["files"][rel]})
            for rel in four:   # all four together: every file's problems reported; and an asset fault, which this stage hides
                _write_tree(w["data"], {rel: with_token(w["files"][rel])})
            os.symlink(os.path.join(w["gsrc"], "graph.css"), os.path.join(w["gsrc"], "engine", "link.js"))
            if not _graph_assets(w["gsrc"])[0]:
                raise _FixtureError("the planted asset fault is not a fault")
            good, why = _refused(w, _argv(w), [f"ASM-STATIC fetch( found in graph/{rel}" for rel in four], "the token in all four files, and an asset fault that the static stage hides")
            if not good:
                return good, why
        with _tmp() as d:   # the clean world still builds
            w = _world(d, big=True)
            return (True, "") if _ok_run(w)[0] else (False, "a clean world did not build")

    @case("A19-call", "the static check over the data files is CALLED (in-process call-site case): a stand-in `_graph_static_problems` that returns one problem makes `run` return 1 with exactly "
                      "`ASM-STATIC <token> <where>` of that problem and nothing written; a recording stand-in is handed, once, exactly the JSON files that are written (index.json WITH its assets, "
                      "spine.json, uses.json, every step file), keyed `graph/<name>` -> bytes")
    def _():
        _need_pr_c()
        with _tmp() as d:
            w = _world(d)
            before = sorted(os.listdir(d))
            rc, lines = inproc(w, {"_graph_static_problems": lambda files: [("PAGE-STATIC", "ZZ-TOKEN", "found in graph/zz")]})
            ok, why = _eq((rc, lines, os.path.exists(w["out"]), sorted(os.listdir(d))), (1, ["ASM-STATIC ZZ-TOKEN found in graph/zz"], False, before))
            if not ok:
                return ok, "a stand-in that returns one problem: " + why
        with _tmp() as d:
            w = _world(d, big=True)
            m, seen = tool_module(), []
            real = m._graph_static_problems

            def rec(files):
                seen.append(dict(files))
                return real(files)
            rc, lines = inproc(w, {"_graph_static_problems": rec})
            if rc != 0:
                return False, f"recording run: exit {rc}, lines {lines!r}"
            tree = _read_tree(w["out"])[0]
            want = {"graph/" + rel: data for rel, data in tree.items() if rel.endswith(".json") and rel != "manifest.json"}
            return _eq((seen == [want], len(want), b'"assets"' in want["graph/index.json"]), (True, 3 + len(_step_names(w["files"])), True))

    # ---- phase 4: --page (A20 to A26): the credits page of the map. ALL page bytes below are SYNTHETIC (invented words); nothing is read from any real page.
    def page_of(add_body="", add_head="", drop_viewport=False):
        t = CREDITS_PAGE.replace("</main>", add_body + "</main>").replace("</head>", add_head + "</head>")
        return t.replace(VIEWPORT_LINE, "") if drop_viewport else t

    def tree_names(w, extra=()):
        return sorted({"index.html", "index.json", "spine.json", "uses.json", "manifest.json"} | set(GRAPH_SRC_FILES) | set(_step_names(w["files"])) | set(extra))

    @case("A20", "the option: `--page REL=PATH`, at most once; REL exactly `credits/index.html` (anything else, no `=`, an empty PATH, a repeat, a bare `--page`: usage on stderr, exit 2, nothing written); the usage "
                 "text shows it; with it the success line is `assembled N steps, M files, into OUT` (M counts the page) and nothing else; WITHOUT it the same line, byte for byte, and then a SECOND line "
                 "`note: no credits page (--page credits/index.html=PATH); place.mjs refuses a tree without it`")
    def _():
        _need_pr_c()
        with _tmp() as d:
            w = _page_world(d)
            rc, lines, err = _cli(_argv(w))
            tree = _read_tree(w["out"])[0] if os.path.isdir(w["out"]) else {}
            n = len(_step_names(w["files"]))
            ok, why = _eq((rc, lines, err, "credits/index.html" in tree), (0, [f"assembled {n} steps, {len(tree)} files, into {w['out']}"], "", True))
            if not ok:
                return ok, "with --page: " + why
        with _tmp() as d:
            w = _world(d)
            rc, lines, err = _cli(_argv(w))
            tree = _read_tree(w["out"])[0] if os.path.isdir(w["out"]) else {}
            ok, why = _eq((rc, lines, err, "credits/index.html" in tree), (0, [f"assembled {len(_step_names(w['files']))} steps, {len(tree)} files, into {w['out']}", NO_PAGE_LINE], "", False))
            if not ok:
                return ok, "without --page: " + why
        with _tmp() as d:
            w = _page_world(d)
            P, good = w["page"], TEST_REL + "=" + w["page"]
            base = _argv(dict(w, page_argv=()))
            bad = {"no `=`": [TEST_REL], "empty PATH": [TEST_REL + "="], "empty REL": ["=" + P], "other REL": ["credits/other.html=" + P], "index.html": ["index.html=" + P],
                   "a folder deeper": ["x/credits/index.html=" + P], "doubled slash": ["credits//index.html=" + P], "leading slash": ["/credits/index.html=" + P],
                   "case": ["Credits/index.html=" + P]}
            for what, val in bad.items():
                rc, lines, err = _cli(base + ["--page"] + val)
                ok, why = _eq((rc, lines, err.startswith("usage:"), os.path.exists(w["out"])), (2, [], True, False))
                if not ok:
                    return ok, f"--page with {what}: " + why
            for what, extra in {"a repeat": ["--page", good, "--page", good], "bare --page at the end": ["--page"]}.items():
                rc, lines, err = _cli(base + extra)
                ok, why = _eq((rc, lines, err.startswith("usage:"), os.path.exists(w["out"])), (2, [], True, False))
                if not ok:
                    return ok, f"{what}: " + why
            rc, lines, err = _cli([])
            ok, why = _eq((rc, lines, "[--page credits/index.html=PATH]" in err), (2, [], True))
            if not ok:
                return ok, "the usage text shows the option: " + why
        return True, ""

    @case("A21", "the page file is read like --strings and --shell: bounded 4 MiB (a file of exactly the limit is read), a symlink, a directory, a FIFO, a file over the bound, bytes that are not UTF-8, a "
                 "missing file are `ASM-DATA <path as given> symlink|not-regular|too-large|encoding|missing`, reported with the other data refusals, exit 1, OUT_DIR not created; a FIFO never hangs")
    def _():
        _need_pr_c()
        with _tmp() as d:
            w = _page_world(d)
            p, argv = w["page"], _argv(w)
            outside = os.path.join(d, "outside.html")
            _put(outside, CREDITS_PAGE)
            kinds = []
            kinds.append(("a symlink", "symlink", lambda: os.symlink(outside, p)))
            kinds.append(("a directory", "not-regular", lambda: os.mkdir(p)))
            kinds.append(("a FIFO", "not-regular", lambda: os.mkfifo(p)))
            kinds.append(("over the bound", "too-large", lambda: _put(p, CREDITS_PAGE.encode("utf-8") + b" " * (TOP_READ_LIMIT + 1 - len(CREDITS_PAGE)))))
            kinds.append(("not UTF-8", "encoding", lambda: _put(p, b"\xff\xfe<p>x</p>")))
            kinds.append(("missing", "missing", lambda: None))
            for what, reason, make in kinds:
                _unlink(p)
                make()
                good, why = _refused(w, argv, [f"ASM-DATA {p} {reason}"], f"the page {what}")
                if not good:
                    return good, why
            _unlink(p)   # reported WITH the other data refusals
            os.remove(os.path.join(w["data"], "spine.json"))
            good, why = _refused(w, argv, [f"ASM-DATA {p} missing", "ASM-DATA spine.json missing"], "a missing page and a missing spine.json together")
            if not good:
                return good, why
        with _tmp() as d:   # exactly the limit is read
            pad = CREDITS_PAGE.encode("utf-8")
            w = _page_world(d, text=pad + b" " * (TOP_READ_LIMIT - len(pad)))
            if os.path.getsize(w["page"]) != TOP_READ_LIMIT:
                raise _FixtureError("the padded page is not exactly the limit")
            tree = _ok_run(w)[0]
            ok, why = _eq(tree.get("credits/index.html") == open(w["page"], "rb").read(), True)
            if not ok:
                return ok, "a page of exactly 4 MiB: " + why
        return True, ""

    @case("A22", "the page checks, as the builder applies them to a document page: `static_problems(page, \"\")`, `element_problems(page)` (the DOCUMENT table: no script, no inline handler, no base, no link), "
                 "`head_meta_problems(page)` and `link_problems(page)` (a `#link` with no id, a duplicate id: it fits a standalone page); each problem is one `ASM-PAGE <problem> found in credits/index.html` "
                 "line, every one reported, exit 1, nothing written; a page that carries `<script>`, an inline handler or `<base>` is refused (the element check bites)")
    def _():
        _need_pr_c()
        runs = (("a script", page_of(add_body="<script>var a = 1;</script>\n"), ["element script"]),
                ("an inline handler", page_of(add_body='<p onclick="a()">x</p>\n'), ["attribute onclick on p"]),
                ("a base element", page_of(add_head='<base target="_top">\n'), ["element base"]),
                ("no viewport meta", page_of(drop_viewport=True), ["viewport missing"]),
                ("a static token", page_of(add_body="<p>call fetch(x) here</p>\n"), ["fetch("]),
                ("a #link with no id", page_of(add_body='<p><a href="#nowhere">x</a></p>\n'), ["#nowhere"]),
                ("a duplicate id", page_of(add_body='<article id="a"></article><article id="a"></article>\n'), ["duplicate id a"]),
                ("four problems together", page_of(add_body='<script></script><p>call fetch(x) here</p><a href="#nowhere">x</a>', drop_viewport=True),
                 ["element script", "fetch(", "#nowhere", "viewport missing"]))
        with _tmp() as d:
            w = _page_world(d)
            for what, text, probs in runs:
                _put(w["page"], text)
                good, why = _refused(w, _argv(w), [f"ASM-PAGE {pb} found in credits/index.html" for pb in probs], what)
                if not good:
                    return good, why
        return True, ""

    @case("A23", "the page's refs (`href`, `src`, `action`, `srcset` candidates, `poster`, `data`) are checked by the index.html logic but resolved against the page's OWN folder: from credits/index.html a "
                 "`..` that stays inside the tree resolves (`../graph.css`, `../index.html`, `../`, `../step/<id>.json`; `./` and `index.html` are the folder and the page itself); `../../x` escapes, a "
                 "leading `/` or `//` or a scheme is absolute, a name not in the tree (`nothere.html` is credits/nothere.html) is missing; the line is `ASM-PAGE credits/index.html: <ref> "
                 "absolute|escapes|missing`, a repeated ref once, every violation reported, exit 1, nothing written")
    def _():
        _need_pr_c()
        step = _step_names(_data_files())[0]
        anchors = lambda *refs: page_of(add_body="".join(f'<p><a href="{r}">x</a></p>\n' for r in refs))
        fine = ["../graph.css", "../index.html", "../", "./", "./index.html", "index.html", "../" + step, "../engine/index.js?v=1", "../page/app.js#x", "../manifest.json", "../credits/index.html",
                "../credits/", "../step/../graph.css", "?v=2", "../engine/"]
        with _tmp() as d:
            w = _page_world(d, text=anchors(*fine))
            tree = _ok_run(w)[0]
            ok, why = _eq(tree.get("credits/index.html") == anchors(*fine).encode("utf-8"), True)
            if not ok:
                return ok, "refs that resolve inside the tree: " + why
            _unlink(w["out"])   # the clean build above wrote OUT_DIR; the refusals below need it absent
            refused = [("../../x.html", "escapes"), ("../../", "escapes"), ("../../../x", "escapes"), ("../x/../../y", "escapes"), ("/x.html", "absolute"), ("mailto:a@b.c", "absolute"),
                       ("nothere.html", "missing"), ("../nothere.css", "missing"), ("../list/", "missing"), ("credits/index.html", "missing"), ("../" + step.replace("lean", "zzzz"), "missing")]
            _put(w["page"], anchors(*(r for r, _why in refused), "nothere.html", "../graph.css"))
            good, why = _refused(w, _argv(w), [f"ASM-PAGE credits/index.html: {r} {reason}" for r, reason in refused], "every refused ref of the page, a repeated one once")
            if not good:
                return good, why
            _put(w["page"], anchors("//host/x"))   # the static check refuses `//host` too (its own line)
            good, why = _refused(w, _argv(w), ["ASM-PAGE href=http found in credits/index.html", "ASM-PAGE credits/index.html: //host/x absolute"], "a protocol-relative ref")
            if not good:
                return good, why
        return True, ""

    @case("A24", "the About link: with --page the three strings keys about_credits_before, about_credits_link, about_credits_after are ALL required, each a non-empty string (`ASM-STRINGS <key> missing|not-a-string`, an "
                 "empty one is `missing`); the About block of index.html is the existing `<p>` + escaped about_text + `</p>` followed by `<p>` + escaped BEFORE + `<a href=\"credits/\">` + escaped LINK + `</a>` + "
                 "escaped AFTER + `</p>`; the href is DERIVED from the folder of REL, never from the strings; without --page the three keys are ignored (any value) and the page is byte-identical to the "
                 "page of a run that never heard of them; the link resolves (the credits file is a name of the tree)")
    def _():
        _need_pr_c()
        special = _page_strings(**{CREDITS_KEYS[0]: 'Licence & <b>credits</b>: "', CREDITS_KEYS[1]: "a <i>link</i>", CREDITS_KEYS[2]: " & \"done\".", "about_credits_href": "elsewhere/"})
        with _tmp() as d:
            w = _page_world(d, strings_over={k: special[k] for k in (*CREDITS_KEYS, "about_credits_href")})
            tree = _ok_run(w)[0]
            page = tree["index.html"].decode("utf-8")
            ok, why = _eq((_no_feedback(page), page.count('<a href="credits/">'), "<b>credits</b>" in page, "elsewhere/" in page), (_expected_credits_page(w, special), 1, False, False))
            if not ok:
                return ok, "with --page: " + why
        with _tmp() as d:   # without --page the keys are ignored, whatever they hold
            odd = _page_strings(**{CREDITS_KEYS[0]: 7, CREDITS_KEYS[1]: "", CREDITS_KEYS[2]: "x<y"})
            w = _world(d, strings=odd)
            page = _ok_run(w)[0]["index.html"].decode("utf-8")
            ok, why = _eq((_no_feedback(page), "credits/" in page), (_expected_credits_page(w, _page_strings(), with_link=False), False))
            if not ok:
                return ok, "without --page: " + why
        with _tmp() as d:   # each fault alone, then all three
            w = _page_world(d)
            argv = _argv(w)
            good_vals = {k: _page_strings()[k] for k in CREDITS_KEYS}
            faults = ((CREDITS_KEYS[0], None, "missing"), (CREDITS_KEYS[1], 7, "not-a-string"), (CREDITS_KEYS[2], "", "missing"), (CREDITS_KEYS[1], "", "missing"), (CREDITS_KEYS[0], ["x"], "not-a-string"))
            for key, val, reason in faults:
                _put(w["strings"], json.dumps({k: v for k, v in _page_strings(**dict(good_vals, **{key: val})).items()}))
                good, why = _refused(w, argv, [f"ASM-STRINGS {key} {reason}"], f"{key} {reason}")
                if not good:
                    return good, why
            _put(w["strings"], json.dumps({k: v for k, v in _page_strings(**{CREDITS_KEYS[0]: None, CREDITS_KEYS[1]: 7, CREDITS_KEYS[2]: ""}).items()}))
            return _refused(w, argv, [f"ASM-STRINGS {CREDITS_KEYS[0]} missing", f"ASM-STRINGS {CREDITS_KEYS[1]} not-a-string", f"ASM-STRINGS {CREDITS_KEYS[2]} missing"], "all three keys faulty")

    @case("A25", "the tree: credits/index.html is copied BYTE FOR BYTE (CRLF and non-ASCII kept) to that path (a file under a `credits/` folder that `_publish` creates), listed in manifest.json `files` with the "
                 "sha256 of its bytes, `counts.steps` unchanged, nothing else new (the write set is closed), no empty folder; the name set of the ref check includes it (a shell link to `credits/index.html` "
                 "resolves); a collision of `credits/index.html` with a data or asset name is `ASM-OUT credits/index.html twice` (in-process, a stand-in `_graph_assets`)")
    def _():
        _need_pr_c()
        odd = CREDITS_PAGE.replace("\n", "\r\n").replace("plimmish", "plimmish é").encode("utf-8")
        with _tmp() as d:
            w = _page_world(d, text=odd, big=True)
            tree, empty = _ok_run(w)
            m = json.loads(tree["manifest.json"])
            others = {rel: hashlib.sha256(data).hexdigest() for rel, data in tree.items() if rel not in ("manifest.json", "index.html")}   # index.html in the manifest is A12's business
            ok, why = _eq((sorted(tree), empty, tree.get("credits/index.html") == odd, os.path.isdir(os.path.join(w["out"], "credits")), sorted(os.listdir(d)),
                           m["files"].get("credits/index.html"), {k: v for k, v in m["files"].items() if k != "index.html"}, m["counts"], m["commits"]),
                          (tree_names(w, ["credits/index.html"]), [], True, True, sorted(["data", "gsrc", "shell.html", "strings.json", "credits.html", "out"]),
                           hashlib.sha256(odd).hexdigest(), others, {"steps": len(_step_names(w["files"]))}, {"notes": PIN}))
            if not ok:
                return ok, why
        with _tmp() as d:   # a shell link to the credits file resolves because the name set includes it
            shell = SHELL.replace('<p class="sentence">{{S:sentence}}</p>\n', '<p class="sentence">{{S:sentence}}</p>\n<p class="sentence"><a href="credits/index.html">x</a></p>\n')
            w = _page_world(d, shell=shell)
            if "credits/index.html" not in _ok_run(w)[0]:
                return False, "a run whose shell links credits/index.html did not write the file"
        with _tmp() as d:
            w = _page_world(d)
            before = sorted(os.listdir(d))
            real = tool_module()._graph_assets

            def fake(src):
                errs, assets, shell = real(src)
                return errs, dict(assets, **{TEST_REL: b"export const extra = 1;\n"}), shell
            rc, lines = inproc(w, {"_graph_assets": fake, "_graph_sink_errors": lambda assets, shell: []})
            return _eq((rc, lines, os.path.exists(w["out"]), sorted(os.listdir(d))), (1, ["ASM-OUT credits/index.html twice"], False, before))

    @case("A26", "refusal order and atomicity: the page stage (A21 data, A22, A23, and the three keys of A24, which join the strings checks of the page stage) runs after the existing stages and before the first write: an "
                 "earlier stage that fails (pin, sink) is reported ALONE, the page problems not shown; a strings fault is reported alone (the page checks do not run); a fault of index.html and a fault of "
                 "the credits page are reported together; a refusal leaves OUT_DIR as it was (absent, or an existing empty folder) and nothing beside it. (A16, the lint of the tool's own text, and "
                 "A11b-attrs are their own cases and stay green)")
    def _():
        _need_pr_c()
        bad = page_of(add_body="<p>call fetch(x) here</p>", drop_viewport=True)   # no element problem: M-r (element check skipped) must not redden A26
        with _tmp() as d:
            w = _page_world(d, text=bad)
            _put(os.path.join(w["data"], "index.json"), _recommit(w["files"]["index.json"], BAD_PIN))
            good, why = _refused(w, _argv(w), [f"ASM-PIN index.json {BAD_PIN}"], "a pin fault and a bad page: the pin fault alone")
            if not good:
                return good, why
        with _tmp() as d:
            w = _page_world(d, text=bad)
            _write_tree(w["gsrc"], {"page/app.js": b"x.innerHTML = s;\n"})
            _errs, assets, _sh = _graph_assets(w["gsrc"])
            want = ["ASM-SINK " + e[2] for e in _graph_sink_errors(assets, SHELL.encode("utf-8"))]
            if not want:
                raise _FixtureError("the builder's own sink gate accepts a file that holds innerHTML")
            good, why = _refused(w, _argv(w), want, "a sink fault and a bad page: the sink lines alone")
            if not good:
                return good, why
        with _tmp() as d:
            w = _page_world(d, text=bad, strings_over={CREDITS_KEYS[1]: None})
            good, why = _refused(w, _argv(w), [f"ASM-STRINGS {CREDITS_KEYS[1]} missing"], "a missing key and a bad page: the strings fault alone")
            if not good:
                return good, why
        with _tmp() as d:
            w = _page_world(d, text=page_of(drop_viewport=True), strings_over={ABOUT_KEY: "call fetch(x) here"})
            good, why = _refused(w, _argv(w), ["ASM-PAGE fetch( found in index.html", "ASM-PAGE viewport missing found in credits/index.html"], "a fault of index.html and of the credits page, together")
            if not good:
                return good, why
        with _tmp() as d:   # atomic: an existing EMPTY OUT_DIR stays empty, nothing is left beside it
            w = _page_world(d, text=bad)
            os.mkdir(w["out"])
            before = sorted(os.listdir(d))
            good, why = _refused(w, _argv(w), ["ASM-PAGE fetch( found in credits/index.html", "ASM-PAGE viewport missing found in credits/index.html"], "a refusal into an existing empty OUT_DIR", out_state=[])
            if not good:
                return good, why
            return _eq(sorted(os.listdir(d)), before)

    @case("A27", "outbound links of the credits page: on credits/index.html ONLY, an `<a href>` whose value is exactly `https://github.com/lsernau/grh-lean/tree/<PIN>`, or begins with `.../tree/<PIN>/` or "
                 "`.../blob/<PIN>/` (PIN the run's own --pin, compared as a string after the control whitespace is dropped) is not an `absolute` refusal and the tree is built; everything else is still "
                 "`ASM-PAGE credits/index.html: <ref> absolute`, exit 1, nothing written: another host, `http:`, another repository, the same repository at another commit or with none (`tree/main`, the bare "
                 "repository, `<PIN>x`, `<PIN>#frag`), a scheme-relative value, another letter case, the allowed URL in any attribute but `href` of an `a` (driven in-process through `_ref_problems`, the "
                 "A7b pattern: `data`, `poster`, `action`, `srcset`, and `a data`/`a action`; `src` is A11b-attrs' pin and stays out of this case) or in the `href` of another element; and the same "
                 "URL in index.html stays `absolute` (in-process, the page string of `_ref_problems` with its default)")
    def _():
        _need_pr_c()
        fails = []
        repo, other = "https://github.com/lsernau/grh-lean/", "a" * 40   # the repository is a literal here, not read from the tool: a loosened constant must redden this case
        anchors = lambda *refs: page_of(add_body="".join(f'<p><a class="note-link" href="{r}">x</a></p>\n' for r in refs))   # class note-link: the builder's static check lets an https `a` with it through, so only the ref check is under test

        def note(name, ok_why):
            if not ok_why[0]:
                fails.append(f"[{name}] {ok_why[1]}")

        allowed = [repo + "tree/" + PIN, repo + "tree/" + PIN + "/grh", repo + "blob/" + PIN + "/grh/ATTRIBUTION.md"]
        with _tmp() as d:
            w = _page_world(d, text=anchors(*allowed))
            rc, lines, err = _cli(_argv(w))
            tree = _read_tree(w["out"])[0] if os.path.isdir(w["out"]) else {}
            note("allowed links build", _eq((rc, lines, err, tree.get(TEST_REL) == anchors(*allowed).encode("utf-8")),
                                            (0, [f"assembled {len(_step_names(w['files']))} steps, {len(tree)} files, into {w['out']}"], "", True)))
        static = "ASM-PAGE href=http found in credits/index.html"   # the builder's own line for an `http:`, `//` or upper-case `HTTPS://` value, which its static check refuses first
        refused = [("another host", "https://example.org/lsernau/grh-lean/tree/" + PIN, False), ("http:", "http://github.com/lsernau/grh-lean/tree/" + PIN, True),
                   ("another repository", "https://github.com/lsernau/other/tree/" + PIN, False), ("another commit", repo + "tree/" + other, False), ("a branch", repo + "tree/main", False),
                   ("the bare repository", repo, False), ("the commit and one more character", repo + "tree/" + PIN + "x", False), ("the commit and a fragment", repo + "tree/" + PIN + "#frag", False),
                   ("the commit and a query", repo + "tree/" + PIN + "?x", False), ("blob with no path", repo + "blob/" + PIN, False), ("blob at another commit", repo + "blob/" + other + "/x", False),
                   ("scheme-relative", "//github.com/lsernau/grh-lean/tree/" + PIN, True), ("upper-case scheme and host", "HTTPS://GITHUB.COM/lsernau/grh-lean/tree/" + PIN, True),
                   ("upper-case owner", "https://github.com/LSERNAU/grh-lean/tree/" + PIN, False)]
        with _tmp() as d:
            w = _page_world(d)
            for what, ref, flagged in refused:
                _put(w["page"], anchors(ref))
                note("refused: " + what, _refused(w, _argv(w), ([static] if flagged else []) + [f"ASM-PAGE credits/index.html: {ref} absolute"], what))
        m = tool_module()
        url, names = repo + "tree/" + PIN, {"index.html", "graph.css"}
        note("index.html: the allowed URL stays absolute", _eq(m._ref_problems(f'<p><a href="{url}">x</a></p>', names), [f"ASM-PAGE {url} absolute"]))   # the page of the shell: the call without the allowance
        if "link_pin" not in inspect.signature(m._ref_problems).parameters:
            fails.append("[in-process] behaviour absent: `_ref_problems` has no `link_pin` keyword")
        else:
            refs = lambda page, pin=PIN: m._ref_problems(page, names, "credits/", TEST_REL, link_pin=pin)
            want = [f"ASM-PAGE credits/index.html: {url} absolute"]
            note("a link allowed with the pin", _eq(refs(f'<p><a href="{url}">x</a></p>'), []))
            note("the same link with no pin given is absolute", _eq(m._ref_problems(f'<p><a href="{url}">x</a></p>', names, "credits/", TEST_REL), want))
            note("the same link with another pin is absolute", _eq(refs(f'<p><a href="{url}">x</a></p>', other), want))
            for what, tag in (("a: data", f'<a data="{url}">x</a>'), ("a: action", f'<a action="{url}">x</a>'), ("a: poster", f'<a poster="{url}">x</a>'), ("form action", f'<form action="{url}"></form>'),
                              ("object data", f'<object data="{url}"></object>'), ("video poster", f'<video poster="{url}"></video>'), ("img srcset", f'<img srcset="{url} 1x">'),
                              ("link href", f'<link rel="x" href="{url}">'), ("p href", f'<p href="{url}">x</p>')):
                note("in-process refused: " + what, _eq(refs("<p>" + tag + "</p>"), want))
            # A27b: the tail of an allowed link cannot climb out of the pinned repository (in-process through the same call)
            for what, ref in (("tail: dot-dot", repo + "tree/" + PIN + "/.."), ("tail: dot-dot then a name", repo + "tree/" + PIN + "/../x"),
                              ("tail: blob climbing out", repo + "blob/" + PIN + "/a/../../../other/x"), ("tail: dot segment", repo + "tree/" + PIN + "/./x"),
                              ("tail: encoded dots", repo + "tree/" + PIN + "/%2e%2e/x"), ("tail: encoded dots, upper case", repo + "tree/" + PIN + "/%2E%2E/x"),
                              ("tail: encoded slash", repo + "tree/" + PIN + "/a%2fb"), ("tail: encoded backslash", repo + "tree/" + PIN + "/a%5cb"),
                              ("tail: backslash dots", repo + "tree/" + PIN + "/..\\..\\x"), ("tail: empty segment", repo + "tree/" + PIN + "//x"),
                              ("tail: dot-dot then a query", repo + "tree/" + PIN + "/..?q=1"), ("tail: dot-dot then a fragment", repo + "tree/" + PIN + "/..#f")):
                note("in-process refused: " + what, _eq(refs(f'<p><a href="{ref}">x</a></p>'), [f"ASM-PAGE credits/index.html: {ref} absolute"]))
            for what, ref in (("blob file", repo + "blob/" + PIN + "/grh/ATTRIBUTION.md"), ("blob file and a fragment", repo + "blob/" + PIN + "/grh/ATTRIBUTION.md#L10"),
                              ("tree path and a query", repo + "tree/" + PIN + "/grh?x=1"), ("the exact tree URL", repo + "tree/" + PIN),
                              ("dots inside a segment", repo + "blob/" + PIN + "/a.b/c..d/e")):
                note("in-process allowed: " + what, _eq(refs(f'<p><a href="{ref}">x</a></p>'), []))
        return (not fails, "; ".join(fails))

    for mid in MUTATIONS:
        case(mid, f"mutation control for {MUTATIONS[mid][0]}: {MUTATIONS[mid][1]}; red set {', '.join(MUTATIONS[mid][2])}; every other A-case stays green (live: the A-cases run on a mutated copy of tools/)")(
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
