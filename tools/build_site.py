#!/usr/bin/env python3
"""The site builder of the proof map: the zoom levels 0 and 1 as JSON, and one static page, from the notes, the outline and
the declaration table.

It reads the notes as text, runs no Lean and makes no network request. It refuses to build unless `notes_meta` passes on the
same inputs (its library function is called, not a subprocess; its listings do not block). Everything it writes goes under
OUT_DIR, and nothing is written, not even OUT_DIR, unless every check passed. The format of the note comments is read only
through `rh_anchor.py`, the check of the notes only through `notes_meta.py`, both loaded by file path from the folder of
this file.

Outputs under OUT_DIR (JSON: sorted keys, 1-space indent, LF, UTF-8, one final newline)
  level0.json   the level-1 steps of the chain in `order`, the route counts, the notes about the whole (level 0), totals
  level1.json   the same steps, each with its child groups nested under it to any depth
  group/<id>.json  one per group: its roots, the blocks that anchor them, the open `not_read` items, the notes
  manifest.json sha256 of every other output file, the three commit ids, the release id and archive hash, the counts
  data.js       `window.RH_DATA = {...};` with level0, level1 and every group file (nothing reads it yet)
  index.html    ONE static page: plain semantic HTML, readable without JavaScript, no request of any kind
Every JSON file carries `commits`: {notes, release, tools} (B5). A group id is used verbatim as the anchor id of its card.
Group JSON: `claim` is {text, reader, date, conditions, premises (group ids)} or null; `lean_name` is the name of the first
root; `claim_label` is the strings file's `not_read_yet` when the claim is null; `coverage` is the word of `coverage_word`;
`counts` is {roots, roots_read, roots_not_read}; `notes` lists {note, list_title, link}.

CONTRACT (each line is a self-test case, written before the code; an expected value in a case is a literal)
 Command, output, exit codes
  X1 Exit 2: usage, an input that cannot be read, OUT_DIR that is a file, a SRC_ROOT that is not a directory, a
     --release-archive-sha that is not 64 hex digits, --notes-commit without --repo (or the reverse), a REV that is not a
     commit; the message goes to stderr, nothing to stdout, nothing is written. Cases X1a X1b.
  X2 Exit 3: `CHECKED NOTHING: <reason>` on stdout and nothing written, when notes_meta checked nothing (no note) or
     --source-check finds no .lean file under SRC_ROOT. Cases X2a X2b.
  X3 Exit 1 REFUSED, and OUT_DIR does not exist afterwards: any ERROR finding of notes_meta (its output is printed), or a
     build rule that failed (`BUILD-ERROR <CODE> <message>` on stdout). The builder prints notes_meta's count line `outline:
     G groups, C claimed, Z null, R roots resolved, D defs_opened resolved, P premise links` on a build. Cases X3a X3b X3c.
  X4 A fresh run into a non-empty OUT_DIR says OUT-NOT-EMPTY and refuses (exit 1) unless --force; --force removes only
     what a build writes (the five files and the folder `group`), never another file. Cases OUT1 OUT2.
  X5 A group id that is not safe as a file name (letters, digits, `.`, `_`, `-`, not starting with `.`; no two ids that differ
     only in case) is GROUP-ID-UNSAFE. Cases ID1 ID2.
  X6 A normal run first runs the self-test quietly and refuses with exit 4 if it fails; `--selftest` runs it (0 pass, 4
     fail); `--selftest --only ID,ID` runs exactly those cases and an unknown id exits 2. Cases EXIT4 SEL1.
 Data
  L0 level0.json: the level-1 steps in `order` whatever the order in the outline file; per step the fields above; `route`
     counts the steps per coverage word; `header_notes` lists the level-0 notes; `totals` counts groups, notes, blocks and
     distinct roots, each once. Case L0.
  L1 level1.json nests child groups under their parent to any depth (a case with depth 4), siblings by `order`. Case L1.
  G1 group/<id>.json for every group: roots (module, name, kind, file, lines, sha256, shared_with), the blocks that anchor
     them (note, block, kind, reader, date, second_readers, item, row, col, file, lines, needs when present; text and
     first_sentence for an argument or interpretation whose target is a paragraph), the open not_read items, the notes.
     A block anchored to a list carries its `item`, a table block its `row`; the text of a list item or a table cell is
     never written. Cases G1 U2.
  G2 sha256 of a root's file when --source-check gives the release, else null. Case G2.
  M1 manifest.json: sha256 of every output file but itself, counts of groups, notes and blocks, the release id and the
     --release-archive-sha (or null). Case M1.
  F1 JSON as stated above, non-ASCII kept; data.js holds level0, level1 and groups. Cases FMT1 DJS.
  B2 DETERMINISM: two builds in child processes under PYTHONHASHSEED=1 and =2 give byte-identical OUT_DIR. Case B2.
  B3 A note is listed under every group whose root one of its blocks anchors, and under its header's group; in totals
     it is counted once. Case B3.
  B14 A level-0 note (header level 0) is listed above the chain, under no step and in no group's list, and counted once in
     totals. Case U1.
  B5 Three commit ids in every JSON file: the notes commit (--notes-commit REV, else `unknown`), the release id (the
     outline's), the tools commit. A tree whose notes, outline or strings differ from the commit, or whose tools differ from
     their commit, stamps `dirty` in all three, and the page says so in the first screen. Cases B5a B5b B5c.
  B6 coverage_word(counts, table): the first entry of the ordered table whose `when` holds; `read_all` = every root has a
     reading block, `read_some` = some but not all, `read_none` = none. A group with zero roots has no coverage claim:
     None, never "Read by us". Cases B6a B6b.
  R1 read + partly + not read = steps is asserted at build time and printed with its three numbers; a table that drops a
     state is COVERAGE-SUM. Cases R1a R1b.
 Page
  P1 The first screen comes from strings.json (`first_screen`), then the chain of level-1 steps in order. No sentence the
     reader sees is typed in code: a missing key is STRINGS-KEY naming it, and a build with every value a distinct
     marker shows only markers and data. Cases P1a P1b.
  P2 A card: claim (a bare declarative), conditions directly under it, premises each a link to the premise's card, the
     coverage word, then the idea; all outside the closed section. Text from the data is escaped. Cases P2a P2b.
  P3 Evidence (Lean name, file, lines, hash, blocks, open items) is a closed `<details>` per card. A null claim shows the
     Lean name and the strings file's `not_read_yet`. Case P3.
  P4 A step's child groups are nested under it in a closed `<details>`, each a full card; the chain stays visible. Case P4.
  P5 Three reaction links per card, plain anchors, href built from the strings template with the card id filled. Case P5.
  P6 Every number on the page appears in the JSON or the strings file; the page computes no sum. number_problems. Case P6.
  P7 index.html and data.js hold none of fetch(, XMLHttpRequest, WebSocket, sendBeacon, import(, `src=`/`href=` to http(s)
     except in a reaction anchor, url(; the builder refuses (PAGE-STATIC) when one does. static_problems. Cases P7a P7b.
  R2 Level 0 counts steps with the template `route_count`; lower levels count declarations with `roots_read` and
     `roots_not_read`; the page has no percent sign and no "of the proof". Case R2.
  R3 A word of `forbidden_words` (and verified, explained, understood always) in the strings file refuses the build
     naming the key (STRINGS-FORBIDDEN); the built page has none of them. Cases R3a R3b.
  R4 No CSS animation or transition keyword in the page; an unread card is present, full size, outlined and labelled, never
     hidden or faded. Cases R4a R4b.
  R5 Every card says its coverage counts roots only (`roots_only_note`); a declaration that is a root of two groups is
     marked shared with the other group's id and counted once in totals. Case R5.
  R6 A `correction` block anchored to a root is shown on that root's card with kind, reader and date, outside the closed
     section. Case R6.
  B7 Every argument block is shown in ONE element with its frame first, drawn from strings.json plus the block's reader,
     date, lines and second readers; a step with an argument block shows its first sentence under the claim, a step
     without one the fixed sentence `no_argument`; an interpretation is shown apart in its own frame; every `#` link
     resolves to an id of the page (link_problems); a reading, argument, interpretation or correction block with no
     reader or no date refuses the build (BLOCK-NO-READER). Cases B7a B7b B7c B7d B7e B7f.
  B1 --source-check SRC_ROOT: no output file holds a line of the release: stripped lines of at least 20 non-space
     characters of the release against the text lines of every output file (string values of the JSON except the
     name and id fields, text of the page except `<code>`). The run says what it ranged over. A planted shard that
     leaks a line is SOURCE-LEAK; an ids-only control stays green. Cases B1a B1b B1c B1d.

LIMIT. The page is a first draft of a real page: plain HTML, no script, no style beyond borders; the wording is the
strings file's, and the strings file's shape is PROVISIONAL (the table under `coverage` and every key named in this file
belong to whoever owns the wording; the fixtures of the self-test carry their own sentences, not the real ones). The
builder does not read a claim or a block and cannot say it is right; it copies no Lean text and no list item or table
cell text, and copies the first sentence and the paragraph of an `argument` or `interpretation` block whose target is a
paragraph, which are prose of the notes (an argument whose target is a list, table or lean block shows its frame and a link).
A first sentence is the text up to the first `.`, `!` or `?` followed by a space or the end. A reading block is the only
block that makes a root "read": an argument or interpretation alone does not. A level-0 note is under no group, and its
blocks feed no group. Coverage is for the roots only: members of a group that a root uses are not mapped, there is no
compiled data in this slice, and off-route marks (with their basis) are not built. B1 compares a release line with a
whole text line of an output file: a release line inside a longer line, or split across two, is not seen; the names and
ids that are excluded are the keys id, module, name, lean_name, file, note, block, parent, premises, sha256, link,
commits, files, release_id, release_archive_sha. B4's check is that each run of digits on the page appears among the digits
of the JSON or the strings file: it cannot say the number is the right one. `dirty` is judged for the files of NOTES_DIR,
the outline and the strings file against the notes commit, and for tracked files of this folder against the tools
commit; an untracked file of the tools folder is not seen, and without --notes-commit the notes commit is `unknown` and
the notes are not judged. The sha256 of a root's file needs --source-check; a hash table in a note is not read. The
coverage table is read as: an entry matches by exactly one of read_all, read_some, read_none, so the order of the entries
does not change the result. The notes are the files NOTES_DIR matches by notes_meta's default pattern. The page's
note links are the strings file's `note_href` with the note's file name filled in.

usage: build_site.py NOTES_DIR OUTLINE DECLS_TSV STRINGS OUT_DIR [--source-check SRC_ROOT] [--release-archive-sha HEX]
                     [--notes-commit REV --repo DIR] [--force]
       build_site.py --selftest [--only ID,ID]
"""
import contextlib
import functools
import hashlib
import html
import html.parser
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_sibling(name):
    """A module of this folder, loaded by file path (never through sys.path), under a private name."""
    key = "_build_site_" + name
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


nm = _load_sibling("notes_meta")
rh = _load_sibling("rh_anchor")
sg = _load_sibling("scan_graph")

COVERAGE_KEYS = ("read_all", "read_some", "read_none")
NAME_KEYS = frozenset(["id", "module", "name", "lean_name", "file", "note", "block", "parent", "premises", "sha256", "link",
                       "commits", "files", "release_id", "release_archive_sha"])


# ---------------------------------------------------------------- the tool (stub: the cases below are written first)

def _todo(what):
    raise NotImplementedError(what)


def coverage_word(counts, table):
    _todo("coverage_word")


def static_problems(page, js):
    _todo("static_problems")


def link_problems(page):
    _todo("link_problems")


def number_problems(page, json_text, strings_text):
    _todo("number_problems")


def leak_check(files, src_root):
    _todo("leak_check")


def run(notes_dir, outline, decls, strings, out, source_check=None, archive_sha=None, notes_commit=None, repo=None,
        force=False, tools_state=None):
    _todo("run")


# ---------------------------------------------------------------- self-test: fixtures, built from literals

def _b(**kw):
    return rh.format_comment("rh-block", kw)


def _h(**kw):
    return rh.format_comment("rh-note", dict({"authors": ["Author One"], "readers": ["Reader One"], "release": "rel-1",
                                              "level": 2}, **kw))


def _d(module, name):
    return {"module": module, "name": name}


FOO, BAR, BAZ, QUX, QUUX, CORGE = (_d("A.B", "foo"), _d("A.B", "bar"), _d("A.C", "baz"), _d("A.E", "qux"),
                                   _d("A.F", "quux"), _d("A.G", "corge"))
DECLS = ("# decls fixture\n"
         "module\tname\tkind\tfirst_line\tlast_line\tbasis\n"
         "A.B\tfoo\ttheorem\t10\t20\ttext-extent\n"
         "A.B\tbar\ttheorem\t30\t40\ttext-extent\n"
         "A.C\tbaz\tdef\t5\t9\ttext-extent\n"
         "A.E\tqux\ttheorem\t1\t4\ttext-extent\n"
         "A.F\tquux\ttheorem\t1\t3\ttext-extent\n"
         "A.G\tcorge\ttheorem\t1\t2\ttext-extent\n")
FILES = "\n## Files this note was written from\n\n| File | SHA-256 |\n|---|---|\n| `A/B.lean` | `x` |\n"
ARG_TEXT = "First argument sentence. Second argument sentence."
LEAK = "theorem leak_example_long_name : 1 + 1 = 2 := rfl"
SRC40 = "".join(f"line {i}\n" for i in range(1, 41))
SRC40_SHA = "abf1f49fd0950dcb863dd5555604f8fb05035e5c03393da0ead0616d32bd6578"
TOOLS_OK = ("tools0", False)


def _n01(arg_text=ARG_TEXT, drop_reader=False):
    rd = {} if drop_reader else {"reader": "Reader One"}
    return ("# Note one\n" + _h(id="01", group="g1", list_title="Note one") + "\n\n## Body\n\n"
            "Reading paragraph.\n"
            + _b(id="01.b01", kind="reading", decls=[FOO], file="A/B.lean", lines=[12, 14], date="2026-11-23", **rd) + "\n\n"
            + arg_text + "\n"
            + _b(id="01.b02", kind="argument", decls=[FOO], file="A/B.lean", lines=[15, 18], reader="Reader One",
                 date="2026-11-23", second_readers=[{"reader": "Reader Two", "date": "2026-11-24"}]) + "\n\n"
            "We think this is the key step.\n"
            + _b(id="01.b03", kind="interpretation", decls=[FOO], reader="Reader Two", date="2026-11-24") + "\n\n"
            "- ListItemTextXYZ one\n- ListItemTextXYZ two\n"
            + _b(id="01.b04", kind="reading", decls=[BAR], item=2, reader="Reader One", date="2026-11-23") + "\n\n"
            "| a | b |\n|---|---|\n| TableCellTextXYZ | y |\n"
            + _b(id="01.b05", kind="not_read", decls=[QUUX], needs="hand_read", row=1) + "\n\n"
            "Correction paragraph.\n"
            + _b(id="01.b06", kind="correction", decls=[FOO], reader="Reader Two", date="2026-11-22")
            + "\n" + FILES)


N02 = ("# Note two\n" + _h(id="02", group="g2", list_title="Note two") + "\n\n## Body\n\n"
       "Note two reading qux.\n" + _b(id="02.b01", kind="reading", decls=[QUX], reader="Reader Two", date="2026-11-23") + "\n\n"
       "Note two reading foo.\n" + _b(id="02.b02", kind="reading", decls=[FOO], reader="Reader Two", date="2026-11-23") + "\n")
N00 = ("# Whole\n" + _h(id="00", group="root", list_title="Whole one", level=0) + "\n\n## Body\n\nWhole text.\n")


def _notes(**kw):
    return {"00-whole.md": N00, "01-one.md": _n01(**kw), "02-two.md": N02}


def _claim(text, date="2026-11-20", **kw):
    return dict({"text": text, "reader": "Reader One", "date": date, "defs_opened": [], "conventions_checked": ["a"]}, **kw)


def _g(gid, level, parent, order, roots, claim=None, premises=()):
    return {"id": gid, "level": level, "parent": parent, "order": order, "roots": roots, "claim": claim,
            "premises": list(premises)}


def _outline():
    return {"release": "rel-1", "groups": [
        _g("g3", 1, "root", 3, [CORGE], _claim("Claim four with é"), ["g1", "g2"]),
        _g("g1a1x", 4, "g1a1", 1, [QUX]),
        _g("g1", 1, "root", 1, [FOO], _claim("Claim one", conditions=["Condition one holds."]), ["g1a"]),
        _g("g2", 1, "root", 2, [QUUX, QUX]),
        _g("g1a", 2, "g1", 1, [BAR]),
        _g("g1a1", 3, "g1a", 1, [BAZ], _claim("Claim three & <more>"))]}


def _strings():
    return {
        "page_title": "Page title",
        "first_screen": ["First screen paragraph one.", "First screen paragraph two."],
        "route_count": "{N} of the {M} steps on our route",
        "coverage": [{"when": {"read_all": True}, "word": "Read by us"},
                     {"when": {"read_some": True}, "word": "Partly read"},
                     {"when": {"read_none": True}, "word": "Not read yet"}],
        "mapped_line": "Mapped by machine line.",
        "not_read_yet": "Not read yet",
        "no_argument": "We have not read how this is proved.",
        "frames": {"argument": ["How this is proved, as {reader} read it"], "interpretation": ["We think"], "claim": []},
        "argument_frame": "How this is proved, as {reader} read it on {date} (lines {lines}):",
        "second_reader_frame": "Read again by {reader} on {date}.",
        "interpretation_frame": "Our interpretation, by {reader} on {date}:",
        "evidence_label": "Evidence: where this sits in the Lean code, and who read what",
        "reactions": [{"label": "This makes sense", "href": "https://example.invalid/react?card={card}&kind=sense"},
                      {"label": "This looks wrong to me", "href": "https://example.invalid/react?card={card}&kind=wrong"},
                      {"label": "I can't follow yet: I need more detail",
                       "href": "https://example.invalid/react?card={card}&kind=detail"}],
        "roots_only_note": "Coverage counts the named declarations only.",
        "dirty_note": "This page was built from changes not yet committed.",
        "shared_note": "Also a root of: {groups}",
        "roots_read": "{N} of the {M} declarations we looked at have a reading",
        "roots_not_read": "{N} of the {M} declarations we looked at have an open item",
        "note_href": "notes/{file}",
        "forbidden_words": ["verified", "explained", "understood"],
        "labels": {"chain": "The chain of steps", "level0_notes": "Notes about the whole", "premises": "Rests on",
                   "notes": "Notes", "go_deeper": "Go deeper: the parts of this step", "blocks": "Blocks",
                   "open_items": "Open items", "file": "File", "lines": "Lines", "sha256": "SHA-256",
                   "read_more": "Read the note", "lines_missing": "not given",
                   "kinds": {"machine_fact": "Machine fact", "reading": "Reading", "interpretation": "Interpretation",
                             "correction": "Correction", "not_read": "Not read", "argument": "Argument"}}}


def _marked(v, path=""):
    """The strings fixture with every string value replaced by a distinct marker naming its key."""
    if isinstance(v, str):
        return "MARK-" + path
    if isinstance(v, list):
        return [_marked(x, f"{path}.{i}") for i, x in enumerate(v)]
    if isinstance(v, dict):
        return {k: (x if k == "when" else _marked(x, f"{path}.{k}" if path else k)) for k, x in v.items()}
    return v


def _put(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def _plant(d, notes=None, outline=None, decls=DECLS, strings=None, src=None):
    """The fixture under directory d; the paths run() takes."""
    for k, v in (_notes() if notes is None else notes).items():
        _put(os.path.join(d, "notes", k), v)
    p = {"notes": os.path.join(d, "notes"), "outline": os.path.join(d, "outline.json"),
         "decls": os.path.join(d, "decls.tsv"), "strings": os.path.join(d, "strings.json"), "out": os.path.join(d, "out")}
    os.makedirs(p["notes"], exist_ok=True)
    _put(p["outline"], json.dumps(_outline() if outline is None else outline))
    _put(p["decls"], decls)
    s = _strings() if strings is None else strings
    _put(p["strings"], s if isinstance(s, (str, bytes)) else json.dumps(s))
    p["src"] = None
    if src is not None:
        p["src"] = os.path.join(d, "src")
        os.makedirs(p["src"])
        for k, v in src.items():
            _put(os.path.join(p["src"], k), v)
    return p


class _B:
    """A finished build: exit code, stdout, stderr, whether OUT_DIR exists, and every file under it."""

    def __init__(self, rc, out, err, existed, files):
        self.rc, self.out, self.err, self.existed, self.files = rc, out, err, existed, files

    def text(self, rel):
        return self.files[rel].decode("utf-8")

    def js(self, rel):
        return json.loads(self.text(rel))

    @property
    def page(self):
        return self.text("index.html")


def _tree(out):
    files = {}
    for d, _dirs, fs in os.walk(out):
        for f in fs:
            p = os.path.join(d, f)
            with open(p, "rb") as fh:
                files[os.path.relpath(p, out).replace(os.sep, "/")] = fh.read()
    return files


def _build(state=TOOLS_OK, pre=None, force=False, archive=None, notes_commit=None, repo=None, **plant):
    with tempfile.TemporaryDirectory() as d:
        p = _plant(d, **plant)
        if pre:
            pre(p["out"])
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = run(p["notes"], p["outline"], p["decls"], p["strings"], p["out"], source_check=p["src"],
                     archive_sha=archive, notes_commit=notes_commit, repo=repo, force=force, tools_state=state)
        return _B(rc, buf.getvalue(), err.getvalue(), os.path.exists(p["out"]), _tree(p["out"]) if os.path.isdir(p["out"]) else {})


@functools.lru_cache(maxsize=None)
def _base():
    return _build()


@functools.lru_cache(maxsize=None)
def _base_src():
    return _build(src={"A/B.lean": SRC40})


def _eq(actual, expected):
    return actual == expected, f"expected {expected!r}, got {actual!r}"


# ---- a small DOM, so a case reads the page as a tree

class _Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.kids = tag, dict(attrs), parent, []

    @property
    def cls(self):
        return (self.attrs.get("class") or "").split()

    def nodes(self):
        for k in self.kids:
            if isinstance(k, _Node):
                yield k
                yield from k.nodes()

    def pieces(self):
        for k in self.kids:
            if isinstance(k, _Node):
                yield from k.pieces()
            else:
                yield k

    def text(self):
        return " ".join(" ".join(self.pieces()).split())

    def elems(self):
        return [k for k in self.kids if isinstance(k, _Node)]

    def find(self, tag=None, cls=None, id=None):
        return [n for n in self.nodes() if (tag is None or n.tag == tag) and (cls is None or cls in n.cls)
                and (id is None or n.attrs.get("id") == id)]

    def inside(self, tag, cls=None):
        n = self.parent
        while n is not None:
            if n.tag == tag and (cls is None or cls in n.cls):
                return True
            n = n.parent
        return False


def _dom(page):
    root = _Node("#root", [], None)
    stack = [root]
    void = {"meta", "br", "hr", "img", "link", "input"}

    class P(html.parser.HTMLParser):
        def handle_starttag(self, tag, attrs):
            n = _Node(tag, attrs, stack[-1])
            stack[-1].kids.append(n)
            if tag not in void:
                stack.append(n)

        def handle_endtag(self, tag):
            if tag in void:
                return
            while len(stack) > 1 and stack[-1].tag != tag:
                stack.pop()
            if len(stack) > 1:
                stack.pop()

        def handle_data(self, data):
            stack[-1].kids.append(data)

    P(convert_charrefs=True).feed(page)
    return root


def _card(b, gid):
    return _dom(b.page).find("article", id=gid)[0]


def _direct(card, tag, cls=None):
    return [k for k in card.elems() if k.tag == tag and (cls is None or cls in k.cls)]


def _words(text):
    return set(re.findall(r"[A-Za-z]+", text))


def _git(cwd, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
                       cwd=cwd, capture_output=True, env=env)
    if r.returncode != 0:
        raise AssertionError(f"git {args}: {r.stderr!r}")
    return r.stdout.decode().strip()


def _child(args_file, out, seed):
    """One build in a child interpreter under PYTHONHASHSEED=seed (the module is loaded by file path)."""
    code = ("import importlib.util, json, sys\n"
            "s = importlib.util.spec_from_file_location('bs', sys.argv[1]); m = importlib.util.module_from_spec(s)\n"
            "s.loader.exec_module(m)\n"
            "a = json.load(open(sys.argv[2]))\n"
            "sys.exit(m.run(a['notes'], a['outline'], a['decls'], a['strings'], sys.argv[3], tools_state=('tools0', False)))\n")
    r = subprocess.run([sys.executable, "-c", code, os.path.abspath(__file__), args_file, out], capture_output=True, text=True,
                       timeout=120, env=dict(os.environ, PYTHONHASHSEED=str(seed)))
    return r.returncode, r.stdout + r.stderr


STRING_KEYS = ["page_title", "first_screen", "route_count", "coverage", "mapped_line", "not_read_yet", "no_argument", "frames",
               "argument_frame", "second_reader_frame", "interpretation_frame", "evidence_label", "reactions",
               "roots_only_note", "dirty_note", "shared_note", "roots_read", "roots_not_read", "note_href", "forbidden_words",
               "labels", "labels.chain", "labels.level0_notes", "labels.premises", "labels.notes", "labels.go_deeper",
               "labels.blocks", "labels.open_items", "labels.file", "labels.lines", "labels.sha256", "labels.read_more",
               "labels.lines_missing", "labels.kinds", "labels.kinds.machine_fact", "labels.kinds.reading",
               "labels.kinds.interpretation", "labels.kinds.correction", "labels.kinds.not_read", "labels.kinds.argument"]


def _selftest_cases():
    cases = []

    def case(cid, desc):
        def deco(fn):
            cases.append((cid, desc, fn))
            return fn
        return deco

    # ---- X: command, output, exit codes
    @case("X1a", "usage: no argument, four positionals, an unknown option, --notes-commit without --repo: exit 2, stdout empty, "
                 "nothing written; control: the same call with five positionals builds")
    def _():
        out, err = io.StringIO(), io.StringIO()
        got = []
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            five = [p["notes"], p["outline"], p["decls"], p["strings"], p["out"]]
            for argv in ([], five[:4], five + ["--bogus"], five + ["--notes-commit", "HEAD"], five + ["--release-archive-sha", "zz"]):
                o, e = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                    rc = main(["build_site.py"] + argv, check=lambda: 0)
                got.append((rc, o.getvalue(), os.path.exists(p["out"])))
            o, e = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                rc = main(["build_site.py"] + five, check=lambda: 0)
        return _eq(got + [rc], [(2, "", False)] * 5 + [0])

    @case("X1b", "an input that cannot be read: strings.json that is not JSON, a missing outline, SRC_ROOT that is not a "
                 "directory, OUT_DIR that is a file: exit 2, stdout empty, nothing written; control: a good call is exit 0")
    def _():
        bad_strings = _build(strings="{not json")
        got = [(bad_strings.rc, bad_strings.out, bad_strings.existed)]
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            _put(os.path.join(d, "afile"), "x")
            for key, val in (("outline", os.path.join(d, "none.json")), ("source_check", os.path.join(d, "nodir")),
                             ("out", os.path.join(d, "afile"))):
                args = dict(notes_dir=p["notes"], outline=p["outline"], decls=p["decls"], strings=p["strings"], out=p["out"],
                            tools_state=TOOLS_OK)
                args[key] = val
                o, e = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                    rc = run(**args)
                got.append((rc, o.getvalue(), os.path.isdir(args["out"]) and key != "out"))
        return _eq(got + [(_base().rc,)], [(2, "", False)] * 4 + [(0,)])

    @case("X2a", "no note in NOTES_DIR: `CHECKED NOTHING: ...` on stdout, exit 3, nothing written; control: a note present builds")
    def _():
        b = _build(notes={"readme.md": "x\n"})
        return _eq((b.rc, "CHECKED NOTHING" in b.out, b.existed, _base().rc), (3, True, False, 0))

    @case("X2b", "--source-check on a SRC_ROOT with no .lean file: `CHECKED NOTHING: no .lean file under SRC_ROOT`, exit 3, nothing "
                 "written; control: a .lean file under it builds")
    def _():
        b = _build(src={"readme.txt": "x"})
        return _eq((b.rc, "CHECKED NOTHING: no .lean file under SRC_ROOT" in b.out.splitlines(), b.existed, _base_src().rc),
                   (3, True, False, 0))

    @case("X3a", "a name that resolves to no row of decls.tsv: notes_meta's UNRESOLVED line is printed, exit 1, OUT_DIR does not "
                 "exist; control: the table with the row builds (exit 0) and prints the count line")
    def _():
        short = DECLS.replace("A.G\tcorge\ttheorem\t1\t2\ttext-extent\n", "")
        b = _build(decls=short)
        want = "outline: 6 groups, 3 claimed, 3 null, 7 roots resolved, 0 defs_opened resolved, 3 premise links"
        return _eq((b.rc, any(ln.startswith("UNRESOLVED") for ln in b.out.splitlines()), b.existed, _base().rc,
                    want in _base().out.splitlines()), (1, True, False, 0, True))

    @case("X3b", "a note with no header: NO-HEADER printed, exit 1, nothing written")
    def _():
        notes = _notes()
        notes["02-two.md"] = "# Note two\n\n## Body\n\nText.\n"
        b = _build(notes=notes)
        return _eq((b.rc, any(ln.startswith("NO-HEADER") for ln in b.out.splitlines()), b.existed), (1, True, False))

    @case("X3c", "an argument block with no reader is refused through notes_meta (BLOCK-PROBLEM), exit 1, nothing written")
    def _():
        bad = _n01().replace('"reader":"Reader One","second_readers"', '"second_readers"')
        b = _build(notes=_notes(arg_text="x") | {"01-one.md": bad})
        return _eq((b.rc, "BLOCK-PROBLEM" in b.out, b.existed), (1, True, False))

    @case("OUT1", "a non-empty OUT_DIR: OUT-NOT-EMPTY, exit 1, the files already there untouched; control: an empty OUT_DIR "
                  "that exists builds")
    def _():
        b = _build(pre=lambda out: _put(os.path.join(out, "keep.txt"), "old"))
        c = _build(pre=lambda out: os.makedirs(out))
        return _eq((b.rc, "OUT-NOT-EMPTY" in b.out, sorted(b.files), c.rc), (1, True, ["keep.txt"], 0))

    @case("OUT2", "--force removes only what a build writes: an old group/zz.json and an old level0.json go, keep.txt stays and "
                  "the fresh build is there")
    def _():
        def pre(out):
            _put(os.path.join(out, "keep.txt"), "old")
            _put(os.path.join(out, "group", "zz.json"), "{}")
            _put(os.path.join(out, "level0.json"), "old")
        b = _build(pre=pre, force=True)
        return _eq((b.rc, "group/zz.json" in b.files, "keep.txt" in b.files, b.files.get("level0.json") != b"old",
                    "group/g1.json" in b.files), (0, False, True, True, True))

    @case("ID1", "a group id that is not safe as a file name (`a/b`, `..x`): GROUP-ID-UNSAFE naming it, exit 1, nothing written")
    def _():
        res = []
        for bad in ("a/b", "..x"):
            o = _outline()
            o["groups"][0]["id"] = bad   # g3: no child and no group names it as a premise
            b = _build(outline=o)
            res.append((b.rc, f"BUILD-ERROR GROUP-ID-UNSAFE {bad} " in b.out, b.existed))
        return _eq(res, [(1, True, False)] * 2)

    @case("ID2", "two group ids that differ only in case (`G1`, `g1`) would share a file on some systems: GROUP-ID-UNSAFE, exit 1")
    def _():
        o = _outline()
        o["groups"].append(_g("G1", 1, "root", 4, [CORGE]))
        b = _build(outline=o)
        return _eq((b.rc, "GROUP-ID-UNSAFE" in b.out, b.existed), (1, True, False))

    @case("EXIT4", "a failing self-test: a normal run is REFUSED, exit 4, nothing on stdout and nothing written")
    def _():
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            o, e = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                rc = main(["build_site.py", p["notes"], p["outline"], p["decls"], p["strings"], p["out"]], check=lambda: 4)
            return _eq((rc, o.getvalue(), "REFUSED" in e.getvalue(), os.path.exists(p["out"])), (4, "", True, False))

    @case("SEL1", "`--selftest --only ID,ID` runs exactly the named cases; an unknown id exits 2 naming it and runs nothing")
    def _():
        ok_out, bad_out, bad_err = io.StringIO(), io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(ok_out):
            selftest(only=["X2a", "B6b"])
        with contextlib.redirect_stdout(bad_out), contextlib.redirect_stderr(bad_err):
            rc = selftest(only=["X2a", "NOPE"])
        ran = [ln.split(" ")[1] for ln in ok_out.getvalue().splitlines() if ln.startswith("CASE ")]
        return _eq((ran, rc, "NOPE" in bad_err.getvalue(), bad_out.getvalue()), (["X2a", "B6b"], 2, True, ""))

    # ---- data
    @case("L0", "level0.json: the level-1 steps g1 g2 g3 in `order` (the outline lists g3 first), each with its coverage word and "
                "counts; the route counts one step per word; the level-0 note is in header_notes; the totals")
    def _():
        l0 = _base().js("level0.json")
        steps = l0["steps"]
        got = ([s["id"] for s in steps], [s["coverage"] for s in steps], [s["counts"] for s in steps],
               [s["lean_name"] for s in steps], [s["claim_label"] for s in steps],
               steps[0]["claim"], [n["note"] for n in steps[0]["notes"]], steps[0]["notes"][0],
               l0["route"], l0["header_notes"], l0["totals"], l0["level"])
        want = (["g1", "g2", "g3"], ["Read by us", "Partly read", "Not read yet"],
                [{"roots": 1, "roots_read": 1, "roots_not_read": 0}, {"roots": 2, "roots_read": 1, "roots_not_read": 1},
                 {"roots": 1, "roots_read": 0, "roots_not_read": 0}],
                ["foo", "quux", "corge"], [None, "Not read yet", None],
                {"conditions": ["Condition one holds."], "date": "2026-11-20", "premises": ["g1a"], "reader": "Reader One",
                 "text": "Claim one"},
                ["01", "02"], {"link": "notes/01-one.md", "list_title": "Note one", "note": "01"},
                {"counts": [{"steps": 1, "when": "read_all", "word": "Read by us"},
                            {"steps": 1, "when": "read_some", "word": "Partly read"},
                            {"steps": 1, "when": "read_none", "word": "Not read yet"}], "steps": 3},
                [{"link": "notes/00-whole.md", "list_title": "Whole one", "note": "00"}],
                {"blocks": 8, "groups": 6, "notes": 3, "roots": 6}, 0)
        return _eq(got, want)

    @case("L1", "level1.json nests child groups to depth 4: g1 > g1a > g1a1 > g1a1x, leaves have no children; steps in order")
    def _():
        l1 = _base().js("level1.json")
        g1 = l1["steps"][0]
        chain = [g1["id"], g1["children"][0]["id"], g1["children"][0]["children"][0]["id"],
                 g1["children"][0]["children"][0]["children"][0]["id"]]
        leaf = g1["children"][0]["children"][0]["children"][0]
        return _eq((chain, leaf["children"], [s["id"] for s in l1["steps"]], l1["steps"][1]["children"], l1["level"]),
                   (["g1", "g1a", "g1a1", "g1a1x"], [], ["g1", "g2", "g3"], [], 1))

    @case("G1", "group/g1.json holds exactly its keys, its root with kind, file and lines, and its five blocks in id order with "
                "second_readers, text and first sentence; group/g2.json holds the open not_read item and the shared root")
    def _():
        g1, g2, g1a = _base().js("group/g1.json"), _base().js("group/g2.json"), _base().js("group/g1a.json")
        arg = g1["blocks"][1]
        got = (sorted(g1), g1["roots"], [b["block"] for b in g1["blocks"]], arg,
               g2["open_items"], g2["roots"][1], g1a["blocks"], sorted(_base().files))
        want = (["blocks", "commits", "id", "level", "notes", "open_items", "parent", "roots"],
                [{"file": "A/B.lean", "kind": "theorem", "lines": [10, 20], "module": "A.B", "name": "foo", "sha256": None,
                  "shared_with": []}],
                ["01.b01", "01.b02", "01.b03", "01.b06", "02.b02"],
                {"block": "01.b02", "date": "2026-11-23", "file": "A/B.lean", "first_sentence": "First argument sentence.",
                 "kind": "argument", "lines": [15, 18], "note": "01", "reader": "Reader One",
                 "roots": [{"module": "A.B", "name": "foo"}],
                 "second_readers": [{"date": "2026-11-24", "reader": "Reader Two"}],
                 "text": "First argument sentence. Second argument sentence."},
                [{"block": "01.b05", "needs": "hand_read", "note": "01", "roots": [{"module": "A.F", "name": "quux"}]}],
                {"file": "A/E.lean", "kind": "theorem", "lines": [1, 4], "module": "A.E", "name": "qux", "sha256": None,
                 "shared_with": ["g1a1x"]},
                [{"block": "01.b04", "date": "2026-11-23", "item": 2, "kind": "reading", "note": "01", "reader": "Reader One",
                  "roots": [{"module": "A.B", "name": "bar"}]}],
                ["data.js", "group/g1.json", "group/g1a.json", "group/g1a1.json", "group/g1a1x.json", "group/g2.json",
                 "group/g3.json", "index.html", "level0.json", "level1.json", "manifest.json"])
        return _eq(got, want)

    @case("G2", "with --source-check a root's sha256 is the hash of its file under SRC_ROOT (a file the release lacks: null)")
    def _():
        b = _base_src()
        return _eq((b.js("group/g1.json")["roots"][0]["sha256"], b.js("group/g1a.json")["roots"][0]["sha256"],
                    b.js("group/g3.json")["roots"][0]["sha256"]), (SRC40_SHA, SRC40_SHA, None))

    @case("M1", "manifest.json: the sha256 of every output file but itself (hashed here, independently), the counts, the release "
                "id, the archive hash given on the command line (control: null without it)")
    def _():
        b = _build(archive="ab" * 32)
        m = b.js("manifest.json")
        want_files = {k: hashlib.sha256(v).hexdigest() for k, v in b.files.items() if k != "manifest.json"}
        return _eq((m["files"] == want_files, m["counts"], m["release_id"], m["release_archive_sha"],
                    _base().js("manifest.json")["release_archive_sha"]),
                   (True, {"blocks": 8, "groups": 6, "notes": 3}, "rel-1", "ab" * 32, None))

    @case("FMT1", "every .json file is sorted keys, 1-space indent, LF only, UTF-8 with the non-ASCII character kept, one final newline")
    def _():
        bad = []
        for k, v in _base().files.items():
            if k.endswith(".json"):
                t = v.decode("utf-8")
                if t != json.dumps(json.loads(t), sort_keys=True, indent=1, ensure_ascii=False) + "\n" or "\r" in t:
                    bad.append(k)
        return _eq((bad, "Claim four with é" in _base().text("level0.json")), ([], True))

    @case("DJS", "data.js is `window.RH_DATA = ` then the JSON of level0, level1 and groups, then `;` and a newline")
    def _():
        t = _base().text("data.js")
        pre, post = "window.RH_DATA = ", ";\n"
        data = json.loads(t[len(pre):-len(post)])
        return _eq((t.startswith(pre), t.endswith(post), sorted(data), sorted(data["groups"]),
                    data["level0"] == _base().js("level0.json"), data["groups"]["g1"] == _base().js("group/g1.json")),
                   (True, True, ["groups", "level0", "level1"], ["g1", "g1a", "g1a1", "g1a1x", "g2", "g3"], True, True))

    @case("B2", "two builds under PYTHONHASHSEED=1 and =2 give byte-identical OUT_DIR (every file, the manifest included)")
    def _():
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            _put(os.path.join(d, "args.json"), json.dumps({k: p[k] for k in ("notes", "outline", "decls", "strings")}))
            r1 = _child(os.path.join(d, "args.json"), os.path.join(d, "o1"), 1)
            r2 = _child(os.path.join(d, "args.json"), os.path.join(d, "o2"), 2)
            t1, t2 = _tree(os.path.join(d, "o1")), _tree(os.path.join(d, "o2"))
            return _eq((r1[0], r2[0], len(t1), t1 == t2), (0, 0, 11, True))

    @case("B3", "note 02 (header group g2, a block anchoring foo and one anchoring qux) is listed under g1, g1a1x and g2 and counted "
                "once in the totals; note 01 under g1, g1a (its list block) and g2 (its not_read block)")
    def _():
        b = _base()
        under = {g: [n["note"] for n in b.js(f"group/{g}.json")["notes"]] for g in ("g1", "g1a", "g1a1", "g1a1x", "g2", "g3")}
        return _eq((under, b.js("level0.json")["totals"]["notes"]),
                   ({"g1": ["01", "02"], "g1a": ["01"], "g1a1": [], "g1a1x": ["02"], "g2": ["01", "02"], "g3": []}, 3))

    @case("U1", "a level-0 note (header group `root`) is in header_notes and on the page above the chain, in no group's list; "
                "control: a level-0 note that names a real group (g1) is also under no group")
    def _():
        b = _base()
        listed = [n["note"] for g in ("g1", "g1a", "g1a1", "g1a1x", "g2", "g3") for n in b.js(f"group/{g}.json")["notes"]]
        notes = _notes()
        notes["00-whole.md"] = N00.replace('"group":"root"', '"group":"g1"')
        c = _build(notes=notes)
        c_listed = [n["note"] for n in c.js("group/g1.json")["notes"]]
        page = _dom(b.page)
        top = [a.text() for a in page.find("header")[0].find("a")]
        return _eq(("00" in listed, top, c.rc, c_listed, c.js("level0.json")["header_notes"][0]["note"]),
                   (False, ["Whole one"], 0, ["01", "02"], "00"))

    @case("B5a", "every JSON file (and the payload of data.js) carries commits {notes, release, tools}: `unknown`, the outline's "
                 "release id and the tools id given")
    def _():
        b = _base()
        want = {"notes": "unknown", "release": "rel-1", "tools": "tools0"}
        got = {k: v for k, v in ((k, json.loads(b.text(k))["commits"]) for k in b.files if k.endswith(".json"))}
        data = json.loads(b.text("data.js")[len("window.RH_DATA = "):-2])
        return _eq((all(v == want for v in got.values()), len(got), data["level0"]["commits"], data["groups"]["g2"]["commits"]),
                   (True, 9, want, want))

    @case("B5b", "a dirty tools tree stamps `dirty` in all three ids of every JSON file and the page says so in its first screen "
                 "(the strings file's dirty_note, inside the header); control: the clean page does not")
    def _():
        b = _build(state=("tools0", True))
        ids = {json.dumps(json.loads(v)["commits"], sort_keys=True) for k, v in b.files.items() if k.endswith(".json")}
        note = "This page was built from changes not yet committed."
        in_header = [p.text() for p in _dom(b.page).find("header")[0].find("p")]
        return _eq((ids, note in in_header, note in _base().page), ({'{"notes": "dirty", "release": "dirty", "tools": "dirty"}'},
                                                                    True, False))

    @case("B5c", "--notes-commit HEAD --repo DIR: the notes id is the repository's HEAD commit (asked of git here); after an "
                 "uncommitted edit of a note all three ids are `dirty` and the page says so")
    def _():
        if shutil.which("git") is None:
            raise _SkipCase("no git program")
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            _git(d, "init", "-q")
            _git(d, "add", "-A")
            _git(d, "commit", "-q", "-m", "base")
            head = _git(d, "rev-parse", "HEAD")
            res = []
            for edit in (False, True):
                if edit:
                    with open(os.path.join(p["notes"], "02-two.md"), "a", encoding="utf-8") as f:
                        f.write("\nMore.\n")
                shutil.rmtree(p["out"], ignore_errors=True)
                o, e = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                    rc = run(p["notes"], p["outline"], p["decls"], p["strings"], p["out"], notes_commit="HEAD", repo=d,
                             tools_state=TOOLS_OK)
                res.append((rc, json.load(open(os.path.join(p["out"], "level0.json")))["commits"],
                            "built from changes" in open(os.path.join(p["out"], "index.html")).read()))
            return _eq(res, [(0, {"notes": head, "release": "rel-1", "tools": "tools0"}, False),
                             (0, {"notes": "dirty", "release": "dirty", "tools": "dirty"}, True)])

    @case("B6a", "coverage_word: every root read -> the read_all word; some but not all -> the read_some word; none -> the "
                 "read_none word; two roots with one read is partly; the table's order does not matter")
    def _():
        t = _strings()["coverage"]
        w = lambda r, k, table=t: coverage_word({"roots": r, "read": k, "not_read": 0}, table)
        return _eq([w(3, 3), w(1, 1), w(3, 1), w(2, 1), w(3, 0), w(1, 0), w(3, 3, t[::-1]), w(3, 1, t[::-1]), w(3, 0, t[::-1])],
                   ["Read by us", "Read by us", "Partly read", "Partly read", "Not read yet", "Not read yet", "Read by us",
                    "Partly read", "Not read yet"])

    @case("B6b", "coverage_word: a group with zero roots has no coverage claim (None), never `Read by us` (0 of 0 is not all); a "
                 "table with no entry for the state gives None")
    def _():
        t = _strings()["coverage"]
        return _eq((coverage_word({"roots": 0, "read": 0, "not_read": 0}, t),
                    coverage_word({"roots": 2, "read": 0, "not_read": 0}, t[:2])), (None, None))

    @case("R1a", "a coverage table that drops the read_none state: COVERAGE-SUM with the three numbers `read 1 + partly 1 + not "
                 "read 0 = 2, but there are 3 steps`, exit 1, nothing written")
    def _():
        s = _strings()
        s["coverage"] = s["coverage"][:2]
        b = _build(strings=s)
        return _eq((b.rc, "BUILD-ERROR COVERAGE-SUM read 1 + partly 1 + not read 0 = 2, but there are 3 steps" in b.out.splitlines(),
                    b.existed), (1, True, False))

    @case("R1b", "a good build prints `coverage check: read 1 + partly 1 + not read 1 = 3 steps`")
    def _():
        return _eq("coverage check: read 1 + partly 1 + not read 1 = 3 steps" in _base().out.splitlines(), True)

    # ---- page
    @case("P1a", "a missing key of the strings file (each of the 40 keys in turn) is a build error that names it, exit 1, nothing "
                 "written; control: the full file builds")
    def _():
        bad = []
        for key in STRING_KEYS:
            s = _strings()
            node, path = s, key.split(".")
            for part in path[:-1]:
                node = node[part]
            del node[path[-1]]
            b = _build(strings=s)
            if not (b.rc == 1 and f"BUILD-ERROR STRINGS-KEY {key} " in b.out and not b.existed):
                bad.append((key, b.rc, b.out[:120]))
        return _eq((bad, len(STRING_KEYS)), ([], 40))

    @case("P1b", "every strings value a distinct marker: the page shows only markers and data (every word on it is in the "
                 "marker tokens or the fixture's own data), the markers of first_screen come first, and no typed sentence")
    def _():
        b = _build(strings=_marked(_strings()))
        if b.rc != 0:
            return False, b.out + b.err
        dom = _dom(b.page)
        text = " ".join(dom.find("body")[0].pieces())
        text = re.sub(r"MARK-[A-Za-z0-9_.]*[A-Za-z0-9_]", " ", text)
        data = json.dumps(_outline()) + DECLS + " ".join(_notes().values())
        stray = sorted(_words(text) - _words(data))
        first = [p.text() for p in dom.find("header")[0].find("p")][:2]
        return _eq((stray, first), ([], ["MARK-first_screen.0", "MARK-first_screen.1"]))

    @case("P2a", "a card, in order: the claim, the conditions directly under it, the premises, the coverage word, the idea; "
                 "all direct children of the card, before the closed evidence section")
    def _():
        c = _card(_base(), "g1")
        names = [(k.tag, k.cls[0] if k.cls else "") for k in c.elems()]
        pos = {n: names.index(n) for n in (("h3", "claim"), ("ul", "conditions"), ("p", "premises"), ("p", "coverage"),
                                           ("p", "argument"), ("details", "evidence"))}
        order = sorted(pos, key=pos.get)
        return _eq((order, c.find("ul", "conditions")[0].text(), c.find("h3", "claim")[0].text(),
                    c.find("ul", "conditions")[0].inside("details")),
                   ([("h3", "claim"), ("ul", "conditions"), ("p", "premises"), ("p", "coverage"), ("p", "argument"),
                     ("details", "evidence")], "Condition one holds.", "Claim one", False))

    @case("P2b", "text from the data is escaped (`Claim three & <more>` shows as text, the raw page has &amp; and &lt;more&gt;), "
                 "and a premise is a link to the premise's card: g3 rests on `Claim one` (#g1) and `quux` (#g2, null claim)")
    def _():
        b = _base()
        prem = _card(b, "g3").find("p", "premises")[0]
        links = [(a.attrs["href"], a.text()) for a in prem.find("a")]
        return _eq((_card(b, "g1a1").find("h3", "claim")[0].text(), "Claim three &amp; &lt;more&gt;" in b.page, links),
                   ("Claim three & <more>", True, [("#g1", "Claim one"), ("#g2", "quux")]))

    @case("P3", "a null claim shows the Lean name of its first root and the not_read_yet label in the heading; evidence is a closed "
                "<details> (no `open`) whose summary is the evidence label and which holds the root's file, lines and open item")
    def _():
        c = _card(_base(), "g2")
        ev = c.find("details", "evidence")[0]
        return _eq((c.find("h3", "claim")[0].text(), "open" in ev.attrs, ev.find("summary")[0].text(),
                    "A/F.lean" in ev.text(), "1-3" in ev.text(), "hand_read" in ev.text(),
                    all("open" not in d.attrs for d in _dom(_base().page).find("details"))),
                   ("quux Not read yet", False, "Evidence: where this sits in the Lean code, and who read what",
                    True, True, True, True))

    @case("P4", "the child groups of a step are nested in its closed `go deeper` <details>, to depth 4; the three steps stay "
                "in the chain list in order")
    def _():
        dom = _dom(_base().page)
        chain = [li.elems()[0].attrs["id"] for li in dom.find("ul", "chain")[0].elems()]
        leaf = dom.find("article", id="g1a1x")[0]
        anc, n = [], leaf.parent
        while n is not None:
            if n.tag == "article":
                anc.append(n.attrs["id"])
            n = n.parent
        det = dom.find("article", id="g1")[0].find("details", "children")[0]
        return _eq((chain, anc, "open" in det.attrs, det.find("summary")[0].text()),
                   (["g1", "g2", "g3"], ["g1a1", "g1a", "g1"], False, "Go deeper: the parts of this step"))

    @case("P5", "three reaction anchors on every card (6 cards, 18 anchors), plain links whose href is the template with the card "
                "id filled (the `&` decoded), in the strings file's order")
    def _():
        dom = _dom(_base().page)
        mine = dom.find("article", id="g1")[0].find("ul", "reactions")[0].find("a")
        return _eq(([(a.attrs["href"], a.text()) for a in mine], len(dom.find("a", "reaction")), len(dom.find("ul", "reactions"))),
                   ([("https://example.invalid/react?card=g1&kind=sense", "This makes sense"),
                     ("https://example.invalid/react?card=g1&kind=wrong", "This looks wrong to me"),
                     ("https://example.invalid/react?card=g1&kind=detail", "I can't follow yet: I need more detail")], 18, 6))

    @case("P6", "number_problems: a number on the page that is in neither the JSON nor the strings file is named; a number in the "
                "JSON, in the strings, a date, an id: none. And the built page has none")
    def _():
        b = _base()
        alljson = "\n".join(v.decode() for k, v in b.files.items() if k.endswith(".json") or k == "data.js")
        return _eq((number_problems("<p>Total 7 and 12</p>", '{"a": 7}', ""), number_problems("<p>7 and 12</p>", '{"a": 7}', "12"),
                    number_problems("<p>2026-11-23 g1a1</p>", '{"a": "2026-11-23", "b": "g1a1"}', ""),
                    number_problems(b.page, alljson, json.dumps(_strings()))),
                   (["12"], [], [], []))

    @case("P7a", "static_problems: each forbidden thing is named, one planted at a time (fetch(, XMLHttpRequest, WebSocket, "
                 "sendBeacon, import(, @import, src= to http, href= to http, url( to a URL); controls: a reaction anchor to http, "
                 "a local src and href, a # link: none")
    def _():
        sp = static_problems
        planted = [("<script>fetch('a')</script>", "", ["fetch("]), ("<p>x</p>", "var r = new XMLHttpRequest();", ["XMLHttpRequest"]),
                   ("<p>x</p>", "new WebSocket('a')", ["WebSocket"]), ("<p>x</p>", "navigator.sendBeacon('a')", ["sendBeacon"]),
                   ("<p>x</p>", "import('a')", ["import("]), ('<img src="http://x.invalid/a.png">', "", ["src=http"]),
                   ('<script src="https://x.invalid/a.js"></script>', "", ["src=http"]),
                   ('<link rel="stylesheet" href="https://x.invalid/a.css">', "", ["href=http"]),
                   ('<a href="https://x.invalid/">x</a>', "", ["href=http"]),
                   ('<p style="background:url(http://x.invalid/a.png)">x</p>', "", ["url("]),
                   ('<style>body{background:url("https://x.invalid/a.png")}</style>', "", ["url("]),
                   ('<style>@import "https://x.invalid/a.css";</style>', "", ["@import"])]
        controls = ['<a class="reaction" href="https://x.invalid/?card=g1">x</a>', '<img src="local.png"><a href="notes/01.md">x</a>',
                    '<a href="#g1">x</a><p id="g1"></p>']
        return _eq(([sp(h, j) for h, j, _w in planted], [sp(h, "") for h in controls]),
                   ([w for _h, _j, w in planted], [[], [], []]))

    @case("P7b", "the built page and data.js are clean; a strings file whose first_screen holds `fetch(` is refused (PAGE-STATIC), "
                 "exit 1, nothing written")
    def _():
        s = _strings()
        s["first_screen"] = ["Call fetch( now."]
        b = _build(strings=s)
        return _eq((static_problems(_base().page, _base().text("data.js")), b.rc, "BUILD-ERROR PAGE-STATIC fetch(" in b.out, b.existed),
                    ([], 1, True, False))

    @case("R2", "level 0 counts steps with the route_count template (`1 of the 3 steps on our route`, once per word) and each card "
                "counts declarations with roots_read and roots_not_read; no percent sign and no `of the proof` anywhere on the page")
    def _():
        dom = _dom(_base().page)
        route = [(d.find("dt")[0].text() if d.find("dt") else "") for d in dom.find("dl", "route")]
        dl = dom.find("dl", "route")[0]
        dts, dds = [x.text() for x in dl.find("dt")], [x.text() for x in dl.find("dd")]
        cov = _card(_base(), "g2").find("p", "coverage")[0].text()
        return _eq((dts, dds, cov, "%" in _base().page, "of the proof" in _base().page, len(route)),
                   (["Read by us", "Partly read", "Not read yet"], ["1 of the 3 steps on our route"] * 3,
                    "Partly read 1 of the 2 declarations we looked at have a reading 1 of the 2 declarations we looked at "
                    "have an open item Coverage counts the named declarations only.", False, False, 1))

    @case("R3a", "a strings value holding verified, explained or understood (or a word of forbidden_words) is refused naming "
                 "its key: STRINGS-FORBIDDEN, exit 1, nothing written; a word added to forbidden_words is refused too, and `unverified` "
                 "and `misunderstood` are not the forbidden words")
    def _():
        res = []
        for key, val in (("mapped_line", "This was verified."), ("no_argument", "Fully Explained here."),
                         ("evidence_label", "Not understood")):
            s = _strings()
            s[key] = val
            b = _build(strings=s)
            res.append((b.rc, f"BUILD-ERROR STRINGS-FORBIDDEN {key} " in b.out, b.existed))
        s = _strings()
        s["forbidden_words"] = ["unverifiable"]
        s["mapped_line"] = "A word: unverifiable."
        s2 = _strings()
        s2["first_screen"] = ["Not unverified and misunderstood."]
        return _eq((res, _build(strings=s).rc, _build(strings=s2).rc), ([(1, True, False)] * 3, 1, 0))

    @case("R3b", "the built page and the JSON contain none of verified, explained, understood")
    def _():
        t = " ".join(v.decode().lower() for v in _base().files.values())
        return _eq([w in t for w in ("verified", "explained", "understood")], [False, False, False])

    @case("R4a", "no CSS animation or transition keyword in the page (animation, transition, @keyframes), and no opacity, display: "
                 "none or hidden attribute: unread parts are never faded or hidden")
    def _():
        p = _base().page.lower()
        return _eq([w in p for w in ("animation", "transition", "@keyframes", "opacity", "display:none", "display: none", "hidden")],
                   [False] * 7)

    @case("R4b", "an unread step (no reading: g3, g1a1) carries the class `unread` and its coverage word `Not read yet` and is "
                 "present on the page; a read one (g1) does not carry the class")
    def _():
        b = _base()
        return _eq(([("unread" in _card(b, g).cls) for g in ("g3", "g1a1", "g1", "g2")],
                    _card(b, "g3").find("p", "coverage")[0].find("strong")[0].text(), _card(b, "g1a1").find("p", "coverage")[0]
                    .find("strong")[0].text()), ([True, True, False, False], "Not read yet", "Not read yet"))

    @case("R5", "every card carries the roots_only_note; qux is a root of g2 and of g1a1x: each card marks it shared with the other "
                "group, the JSON says shared_with, and the totals count it once (6 distinct roots)")
    def _():
        b = _base()
        dom = _dom(b.page)
        notes = [c.find("p", "coverage")[0].text().endswith("Coverage counts the named declarations only.")
                 for c in dom.find("article")]
        sh = lambda g: [p.text() for p in _card(b, g).find("details", "evidence")[0].find("p", "shared")]
        return _eq((all(notes), len(notes), sh("g2"), sh("g1a1x"), sh("g1"),
                    b.js("group/g1a1x.json")["roots"][0]["shared_with"], b.js("level0.json")["totals"]["roots"]),
                   (True, 6, ["Also a root of: g1a1x"], ["Also a root of: g2"], [], ["g2"], 6))

    @case("R6", "the correction block on foo is shown on g1's card, outside the closed sections, with its kind, reader and date; "
                "a card with none has no corrections list")
    def _():
        c = _card(_base(), "g1")
        li = _direct(c, "ul", "corrections")
        return _eq(([x.text() for x in li[0].find("li")], len(_direct(_card(_base(), "g3"), "ul", "corrections"))),
                   (["Correction Reader Two 2026-11-22 Note one"], 0))

    @case("B7a", "an argument is shown in ONE element, frame first: `How this is proved, as Reader One read it on 2026-11-23 "
                 "(lines 15-18):` then the second reader's frame then the first sentence; the full text with the frame is in the "
                 "evidence; an interpretation is in its own aside with its own frame, apart from the argument")
    def _():
        c = _card(_base(), "g1")
        idea = _direct(c, "p", "argument")[0]
        full = c.find("details", "evidence")[0].find("p", "argument")[0]
        interp = c.find("aside")[0]
        return _eq((idea.text(), idea.elems()[0].cls, full.text(), interp.find("p", "interpretation")[0].text(),
                    full.inside("aside"), interp.inside("details", "evidence")),
                   ("How this is proved, as Reader One read it on 2026-11-23 (lines 15-18): Read again by Reader Two on "
                    "2026-11-24. First argument sentence. Read the note", ["frame"],
                    "How this is proved, as Reader One read it on 2026-11-23 (lines 15-18): Read again by Reader Two on "
                    "2026-11-24. First argument sentence. Second argument sentence.",
                    "Our interpretation, by Reader Two on 2026-11-24: We think this is the key step.", False, True))

    @case("B7b", "the first sentence of the argument is under the claim of the step, outside every closed section, and the second "
                 "sentence is not there")
    def _():
        c = _card(_base(), "g1")
        idea = _direct(c, "p", "argument")[0].text()
        return _eq(("First argument sentence." in idea, "Second argument sentence." in idea, idea.startswith("How this is proved")),
                   (True, False, True))

    @case("B7c", "a step with no argument block shows the fixed sentence `We have not read how this is proved.` and no frame; "
                 "control: the step with one does not show it")
    def _():
        c = _card(_base(), "g3")
        return _eq(([p.text() for p in _direct(c, "p", "no-argument")], len(_direct(c, "p", "argument")),
                    len(_direct(_card(_base(), "g1"), "p", "no-argument"))),
                   (["We have not read how this is proved."], 0, 0))

    @case("B7d", "link_problems: a # link with no id of that name is named, a repeated id is named; controls: resolving links "
                 "(also one with percent-encoding): none; the built page has none")
    def _():
        lp = link_problems
        return _eq((lp('<a href="#a">x</a><p id="a"></p><a href="#b">y</a>'), lp('<p id="a"></p><p id="a"></p>'),
                    lp('<a href="#a%20b">x</a><p id="a b"></p>'), lp(_base().page)),
                   (["#b"], ["duplicate id a"], [], []))

    @case("B7e", "a reading block with no reader refuses the build (BLOCK-NO-READER naming the block), exit 1, nothing written; "
                 "control: the same note with its reader builds")
    def _():
        b = _build(notes=_notes(drop_reader=True))
        return _eq((b.rc, "BUILD-ERROR BLOCK-NO-READER 01.b01 " in b.out, b.existed, _base().rc), (1, True, False, 0))

    @case("B7f", "an argument block whose target is a list shows its frame and a link and no list text; the page never shows the "
                 "text of a list item or a table cell (ListItemTextXYZ, TableCellTextXYZ), nor does any output file")
    def _():
        arg_list = ("- ListItemTextXYZ one\n- ListItemTextXYZ two\n"
                    + _b(id="02.b03", kind="argument", decls=[QUX], item=1, reader="Reader Two", date="2026-11-23", lines=[1, 2])
                    + "\n")
        notes = _notes()
        notes["02-two.md"] = N02 + "\n" + arg_list
        b = _build(notes=notes)
        c = _card(b, "g1a1x")
        idea = _direct(c, "p", "argument")[0].text()
        every = " ".join(v.decode() for v in b.files.values()) + " ".join(v.decode() for v in _base().files.values())
        return _eq((b.rc, idea, "ListItemTextXYZ" in every, "TableCellTextXYZ" in every),
                   (0, "How this is proved, as Reader Two read it on 2026-11-23 (lines 1-2): Read the note", False, False))

    @case("U2", "a block anchored to a list carries its `item` and a table block its `row` in the group JSON, as data only")
    def _():
        b = _base()
        return _eq((b.js("group/g1a.json")["blocks"][0]["item"], b.js("group/g2.json")["blocks"][0]["row"],
                    "item" in b.js("group/g1.json")["blocks"][0]), (2, 1, False))

    # ---- B1: no release text
    @case("B1a", "leak_check: a planted shard whose `text` value is a line of the release (>= 20 non-space characters) is named "
                 "(SOURCE-LEAK data); a short release line and a line of other text are not")
    def _():
        with tempfile.TemporaryDirectory() as d:
            _put(os.path.join(d, "A", "B.lean"), "import A.C\n\n" + LEAK + "\nshort\n")
            files = {"group/x.json": json.dumps({"id": "x", "text": LEAK}).encode(),
                     "group/y.json": json.dumps({"id": "y", "text": "short"}).encode(),
                     "group/z.json": json.dumps({"id": "z", "text": "A sentence of ours that is long enough to count."}).encode()}
            leaks, stats = leak_check(files, d)
        return _eq((leaks, stats), (["group/x.json"], {"release_files": 1, "release_lines": 4, "output_files": 3, "output_lines": 3}))

    @case("B1b", "leak_check, the ids-only control: a release that has a line equal to a declaration name (>= 20 characters) and "
                 "an output that has only that name in its id and name fields is green; the same text under `text` is a leak")
    def _():
        name = "Development.Long.Module.theorem_name_long"
        with tempfile.TemporaryDirectory() as d:
            _put(os.path.join(d, "A.lean"), name + "\n")
            ids = {"group/y.json": json.dumps({"id": name, "roots": [{"module": name, "name": name}], "lean_name": name}).encode()}
            txt = {"group/y.json": json.dumps({"id": "y", "text": name}).encode()}
            return _eq((leak_check(ids, d), leak_check(txt, d)),
                       (([], {"release_files": 1, "release_lines": 1, "output_files": 1, "output_lines": 0}),
                        (["group/y.json"], {"release_files": 1, "release_lines": 1, "output_files": 1, "output_lines": 1})))

    @case("B1c", "a build whose argument text is a release line is refused: SOURCE-LEAK for data.js, group/g1.json and index.html, "
                 "exit 1, nothing written; the page text in <code> (names) is not compared; control: the default note builds")
    def _():
        b = _build(notes=_notes(arg_text=LEAK), src={"A/B.lean": "x\n" + LEAK + "\n"})
        got = sorted(ln.split(" ")[2] for ln in b.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK "))
        return _eq((b.rc, got, b.existed, _base_src().rc), (1, ["data.js", "group/g1.json", "index.html"], False, 0))

    @case("B1d", "the run says what it ranged over: `source check: 1 release files, 40 release lines, 11 output files, N output "
                 "lines, 0 leaked`")
    def _():
        m = re.findall(r"^source check: 1 release files, 40 release lines, 11 output files, (\d+) output lines, 0 leaked$",
                       _base_src().out, re.M)
        return _eq((len(m), bool(m) and int(m[0]) > 20), (1, True))

    return cases


class _SkipCase(Exception):
    """Raised by a case that cannot set up its plant on this system; the case is reported SKIP."""


def selftest(verbose=True, only=None):
    """A case returns (True|False, detail). `only` is a list of case ids: exactly those cases run (an unknown id returns 2)."""
    ok, skipped = True, 0
    cases = _selftest_cases()
    if only is not None:
        known = {c[0] for c in cases}
        bad = [i for i in only if i not in known]
        if bad or not only:
            print("unknown case id: " + ", ".join(bad) if bad else "no case id given", file=sys.stderr)
            return 2
        cases = [c for c in cases if c[0] in only]
    for cid, desc, fn in cases:
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


_VALUE_OPTIONS = {"--source-check": "source_check", "--release-archive-sha": "archive_sha", "--notes-commit": "notes_commit",
                  "--repo": "repo"}


def _parse(argv):
    """(positionals, options) or None for a usage error: five positionals, each option at most once, a value for each."""
    pos, opts, i = [], {}, 0
    while i < len(argv):
        x = argv[i]
        if x in _VALUE_OPTIONS:
            if _VALUE_OPTIONS[x] in opts or i + 1 >= len(argv):
                return None
            opts[_VALUE_OPTIONS[x]] = argv[i + 1]
            i += 2
        elif x == "--force":
            if "force" in opts:
                return None
            opts["force"] = True
            i += 1
        elif x.startswith("--"):
            return None
        else:
            pos.append(x)
            i += 1
    if len(pos) != 5 or ("notes_commit" in opts) != ("repo" in opts):
        return None
    if "archive_sha" in opts and not re.fullmatch(r"[0-9a-fA-F]{64}", opts["archive_sha"]):
        return None
    return pos, opts


def main(a, check=None):
    """a is argv with the program name first."""
    if a[1:] == ["--selftest"]:
        return selftest()
    if len(a) == 4 and a[1] == "--selftest" and a[2] == "--only":   # selector, kept out of the usage block
        return selftest(only=[i for i in a[3].split(",") if i])
    parsed = _parse(a[1:])
    if parsed is None:
        print(__doc__.split("usage:")[1].strip(), file=sys.stderr)
        return 2
    if (selftest_quiet if check is None else check)() != 0:
        print("REFUSED: selftest failed; no result reported", file=sys.stderr)
        return 4
    pos, opts = parsed
    return run(*pos, **opts)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
