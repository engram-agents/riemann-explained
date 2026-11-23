#!/usr/bin/env python3
"""The metadata check of the notes: the outline, the header and the anchors of every note, against the declaration table.

It reads the notes as text. It never writes anywhere except a temporary directory during --selftest, and it runs no Lean.
The format of the comments is not defined here: `rh_anchor.py` is the one place that knows it (parse_note, problems,
header_problems, strip_anchor_lines, format_comment, KINDS, NEEDS), loaded by file path from the folder of this file.

CONTRACT (each line is a self-test case, written before the code)
 Command, output, exit codes
  X1 Notes are the files of NOTES_DIR (not below it) whose name matches `[0-9][0-9]-*.md`; --glob PATTERN replaces
     the pattern. No note matching, an outline whose `groups` is an empty list, or a decls.tsv with no row: one
     `CHECKED NOTHING: <reason>` line per reason on stdout, exit 3, nothing else checked. Cases X1a X1b X1c.
  X2 Exit 0: every note passed. Exit 1: any finding of class ERROR. Exit 2: usage, or an input that cannot be read
     (a message on stderr, nothing on stdout). Exit 3: see X1. Exit 4: the self-test failed (REFUSED, nothing else).
     A listing (EXTENT-WARNING, FRAME-NOTE, NEW-NOTE) never changes the exit code. Cases X2a X2b X2c EXIT4.
  X3 One line per finding, `CODE path:line message` (`CODE path message` when it has no line); path is the file's
     name (a note: its name in NOTES_DIR). Per note, after its findings: `note <id> header ok|FAILED, blocks N
     (kind=count ...)` (the breakdown is left out when N is 0). Then the run's lines: the FRAME-NOTE skip notice
     when there is no --strings, `blocks by kind:` with all six kinds, what the in-file check (M5) and the byte
     check did or did not do, and `N notes, M findings, K warnings` (K = listings). Case SUM.
  X4 --selftest: exit 0 all pass, 1 any fails, 2 usage, 3 no case ran. A normal run does the self-test quietly first
     and refuses with exit 4 if it fails. Case RUNNER.
 Outline
  O1 `groups` ids are unique, non-empty strings; `level` an int >= 1; `order` an int; `roots` a list of {module,
     name} (non-empty strings); `premises` a list of ids. The outline has exactly the keys `groups` and `release`
     (a non-empty string) and every group exactly the keys id, level, parent, order, roots, claim, premises (all
     required): any other key is UNKNOWN-KEY naming the group and the key. Cases O1a O1b O1c O1d.
  O2 `parent` is "root" or an existing group id; a child's level is its parent's plus one; a group under root has
     level 1; `order` is unique among siblings. No maximum depth (a case with depth 6). Cases O2a O2b O2c O2d.
  O3 Every premise exists; a group is not its own premise; the premises relation has no cycle. A premise may be the
     group's own child or a group of any depth. The check is over premises only, never over parent. Cases O3a O3b O3c O3d.
  O4 A group with a non-null claim has exactly one root; a null claim may have any number. Case O4.
  O5 A claim has exactly the keys text, reader, date, defs_opened, conventions_checked (all required; text, reader,
     date non-empty strings; defs_opened a list of {module, name, lines:[a,b]}, may be empty; conventions_checked a
     list of letters a to e) and the optional `conditions` (non-empty strings) and `mathlib_read` (strings). Any
     other claim key is UNKNOWN-KEY. Cases O5a O5b O5c.
  O6 Every `roots` and `defs_opened` entry resolves to exactly one row of decls.tsv: none is UNRESOLVED, two or
     more AMBIGUOUS with the candidates' (first_line, last_line). Case O6.
 Notes
  M1 Exactly one rh-note header per note, before the first `## ` heading: none NO-HEADER, two or more SECOND-HEADER
     naming the lines, one after the first `## ` heading HEADER-AFTER-H2. Case M1.
  M2 header_problems() findings; the group exists in the outline; list_title is not only code spans and does not end
     in a parenthetical. Cases M2a M2b.
  M3 Every block: rh_anchor.problems(block, header id); block ids unique across all notes, DUPLICATE-ID naming both
     places. Cases M3a M3b.
  M4 Every `decls` entry resolves to exactly one row (UNRESOLVED, AMBIGUOUS). Case M4.
  M5 With --src: `file` is listed in the note's file table and is a file under SRC_ROOT, `lines` are inside it.
     Lines outside the text extent of every row the block's decls resolve to are an EXTENT-WARNING listing. Without
     --src the in-file check is skipped and the run says so. Cases M5a M5b M5c.
  M6 Every MALFORMED, UNCLOSED-FENCE and INSIDE-TABLE problem of rh_anchor.parse_note is an ERROR naming the line; a
     line that is not canonical is NONCANONICAL and prints the canonical form. Cases M6a M6b.
  M7 A block with `row` or `col` must follow a table (NOT-A-TABLE), `row` <= body rows, `col` <= columns. Case M7.
  F12 With --strings, an argument or interpretation block whose text opens with the frame of another kind is a
     FRAME-NOTE listing; without it one line says the check was skipped. Cases F12a F12b.
  BYTES With --base REV: the note at REV equals the current note without its anchor lines, byte for byte (BYTE-DIFF
     names the first differing line); a note not at REV is NEW-NOTE. Without --base the run says it did not run.
     Cases B1a B1b B1c B1d.
 Real shape: an outline in the shape the pilot uses (depth 4, premises that name a child) passes; the same with a
 draft-only key added fails UNKNOWN-KEY. Cases REAL1 REAL2.

usage: notes_meta.py NOTES_DIR OUTLINE DECLS_TSV [--base REV] [--repo DIR] [--strings PATH] [--src SRC_ROOT]
                     [--glob PATTERN]
       notes_meta.py --selftest
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_GLOB = "[0-9][0-9]-*.md"


def _load_sibling(name):
    """A module of this folder, loaded by file path (never through sys.path), under a private name."""
    key = "_notes_meta_" + name
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, os.path.join(_HERE, name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            sys.modules.pop(key, None)
            raise
    return sys.modules[key]


rh = _load_sibling("rh_anchor")
clb = _load_sibling("check_lean_blocks")


# ---------------------------------------------------------------- the tool (stub: nothing is checked yet)

def run(notes_dir, outline, decls, base=None, repo=None, strings=None, src=None, glob=DEFAULT_GLOB):
    return 99


# ---------------------------------------------------------------- self-test
_CASES = []


def case(cid, what):
    def deco(fn):
        _CASES.append((cid, what, fn))
        return fn
    return deco


def eq(got, want, what=""):
    if got != want:
        raise AssertionError(f"{what}: got {got!r}, want {want!r}")


def ok(cond, what):
    if not cond:
        raise AssertionError(what)


# ---- fixtures: tiny notes, outlines and tables built from literals in a temporary directory
DECLS = ("# decls fixture\n"
         "module\tname\tkind\tfirst_line\tlast_line\tbasis\n"
         "A.B\tfoo\ttheorem\t10\t20\ttext-extent\n"
         "A.B\tbar\ttheorem\t30\t40\ttext-extent\n"
         "A.C\tbaz\tdef\t5\t9\ttext-extent\n"
         "A.D\tdup\ttheorem\t1\t3\ttext-extent\n"
         "A.D\tdup\ttheorem\t7\t9\ttext-extent\n")
CLAIM = {"text": "T", "reader": "R", "date": "2026-11-23", "defs_opened": [], "conventions_checked": ["a"]}
FILES = "\n## Files this note was written from\n\n| File | SHA-256 |\n|---|---|\n| `A/B.lean` | `x` |\n"
SRC40 = "".join(f"line {i}\n" for i in range(1, 41))
NOCODE = "CHECKED NOTHING"


def G(i, level=1, parent="root", order=1, roots=None, claim=None, premises=None):
    return {"id": i, "level": level, "parent": parent, "order": order, "roots": [] if roots is None else roots,
            "claim": claim, "premises": [] if premises is None else premises}


def R(module, name):
    return {"module": module, "name": name}


def OL(*groups, **top):
    d = {"groups": list(groups), "release": "rel-1"}
    d.update(top)
    return d


def drop(d, key):
    return {k: v for k, v in d.items() if k != key}


def NOTE(nid="01", group="g1", title="A title", body="Some text.\n", **hdr):
    h = {"authors": ["H"], "group": group, "id": nid, "level": 2, "list_title": title, "readers": ["K"], "release": "rel-1"}
    h.update(hdr)
    return "# Note\n" + rh.format_comment("rh-note", h) + "\n\n## Body\n\n" + body


def BL(bid="01.b01", **kw):
    d = {"id": bid, "kind": "reading"}
    d.update(kw)
    return rh.format_comment("rh-block", d)


def ARG(bid="01.b01", **kw):
    return BL(bid, kind="argument", reader="R", date="2026-11-23", decls=[R("A.B", "foo")], **kw)


class Res:
    def __init__(self, rc, out, err):
        self.rc, self.out, self.err = rc, out, err
        self.lines = out.splitlines()
        self.f = [x for x in self.lines if x[:1].isupper() and x.split(" ")[0].replace("-", "").isalpha()
                  and x.split(" ")[0].isupper() and not x.startswith((NOCODE, "FRAME-NOTE skipped", "REFUSED"))]


def _git(cwd, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
                       cwd=cwd, capture_output=True, env=env)
    if r.returncode != 0:
        raise AssertionError(f"git {args}: {r.stderr!r}")
    return r.stdout


def _put(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(text if isinstance(text, bytes) else text.encode("utf-8"))


def go(notes=None, outline=None, decls=DECLS, strings=None, src=None, base=None, committed=None, glob=None,
       raw_outline=None, repo_arg=False, check_dirs=None):
    """Plant a fixture and call run(); (rc, stdout, stderr) as a Res. `committed` names files of NOTES_DIR that exist
    at the commit called HEAD of a throwaway git repository around the fixture (BYTES)."""
    notes = {"01-a.md": NOTE()} if notes is None else notes
    outline = OL(G("g1"), G("g2", order=2, premises=["g1"])) if outline is None else outline
    with tempfile.TemporaryDirectory() as d:
        nd = os.path.join(d, "notes")
        os.makedirs(nd)
        if committed is not None:
            _git(d, "init", "-q")
            for k, v in committed.items():
                _put(os.path.join(nd, k), v)
            _git(d, "add", "-A")
            _git(d, "commit", "-q", "-m", "base")
        for k, v in notes.items():
            _put(os.path.join(nd, k), v)
        op, dp = os.path.join(d, "outline.json"), os.path.join(d, "decls.tsv")
        _put(op, raw_outline if raw_outline is not None else json.dumps(outline))
        _put(dp, decls)
        kw = {}
        if strings is not None:
            sp = os.path.join(d, "strings.json")
            _put(sp, strings if isinstance(strings, str) else json.dumps(strings))
            kw["strings"] = sp
        if src is not None:
            sd = os.path.join(d, "src")
            os.makedirs(sd)
            for k, v in src.items():
                _put(os.path.join(sd, k), v)
            kw["src"] = sd
        if base is not None:
            kw["base"] = base
        if repo_arg:
            kw["repo"] = d
        if glob is not None:
            kw["glob"] = glob
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = run(nd, op, dp, **kw)
        return Res(rc, buf.getvalue(), err.getvalue())


def fe(res, lines, rc):
    """The finding lines are exactly `lines` and the exit code is rc."""
    eq((res.f, res.rc), (lines, rc), "findings and exit code\n" + res.out + res.err)


def clean(res):
    fe(res, [], 0)


# ---- command, output, exit codes
@case("X1a", "no note matches the default pattern: CHECKED NOTHING, exit 3; a file named like docs/tools.md is not a note; "
             "--glob changes the pattern; control: a note matches")
def _():
    r = go(notes={})
    eq((r.rc, r.lines), (3, ["CHECKED NOTHING: no note matches [0-9][0-9]-*.md in NOTES_DIR"]), "empty dir")
    r = go(notes={"tools.md": NOTE(), "1-a.md": NOTE(), "01-a.txt": NOTE()})
    eq((r.rc, r.lines), (3, ["CHECKED NOTHING: no note matches [0-9][0-9]-*.md in NOTES_DIR"]), "names that do not match")
    r = go(notes={"tools.md": NOTE()}, glob="*.md")
    eq(r.rc, 0, "--glob")
    clean(go(notes={"01-a.md": NOTE()}))


@case("X1b", "an outline with an empty groups list: CHECKED NOTHING, exit 3; control: one group")
def _():
    r = go(outline=OL())
    eq((r.rc, r.lines), (3, ["CHECKED NOTHING: the outline has no groups"]), "no groups")
    r = go(outline=OL(G("g1")))
    eq(r.rc, 0, "one group")


@case("X1c", "a decls.tsv with no row: CHECKED NOTHING, exit 3; with two reasons both are printed, one per line")
def _():
    only_head = "# c\nmodule\tname\tkind\tfirst_line\tlast_line\tbasis\n"
    r = go(decls=only_head)
    eq((r.rc, r.lines), (3, ["CHECKED NOTHING: decls.tsv has no rows"]), "no rows")
    r = go(decls=only_head, outline=OL())
    eq((r.rc, r.lines), (3, ["CHECKED NOTHING: the outline has no groups", "CHECKED NOTHING: decls.tsv has no rows"]), "two")
    eq(go(decls="").rc, 3, "an empty file")


@case("X2a", "exit codes: 0 clean, 1 an error finding, 2 an unreadable input with nothing on stdout; a listing leaves it 0")
def _():
    eq(go().rc, 0, "clean")
    eq(go(notes={"01-a.md": "# T\n"}).rc, 1, "no header is an error")
    r = go(notes={"01-a.md": NOTE(body="Some text.\n" + BL(decls=[R("A.B", "foo")], file="A/B.lean", lines=[12, 25]) + "\n" + FILES)},
           src={"A/B.lean": SRC40})
    eq((r.rc, len(r.f), r.f[0][:14]), (0, 1, "EXTENT-WARNING"), "a listing alone")


@case("X2b", "exit 2 with `notes_meta: ` on stderr and nothing on stdout for every unreadable input")
def _():
    bad = [
        ("a note that is not UTF-8", dict(notes={"01-a.md": b"# T\n\xff\n"}), "01-a.md"),
        ("an outline that is not JSON", dict(raw_outline="{"), "outline"),
        ("a decls row with five fields", dict(decls="module\tname\tkind\tfirst_line\tlast_line\tbasis\nA\tb\tc\t1\t2\n"), "decls"),
        ("a decls row whose line is not a number", dict(decls="A\tb\ttheorem\tx\t2\ttext-extent\n"), "decls"),
        ("a strings file that is not JSON", dict(strings="{"), "strings"),
        ("a strings file with no frames key", dict(strings={"x": 1}), "frames"),
        ("a base that is not a revision", dict(base="no-such-rev", committed={"01-a.md": NOTE()}), "--base"),
    ]
    for what, kw, word in bad:
        r = go(**kw)
        eq((r.rc, r.out), (2, ""), what)
        ok(r.err.startswith("notes_meta: ") and word in r.err, what + ": " + r.err)
    with tempfile.TemporaryDirectory() as d:
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = run(os.path.join(d, "nope"), os.path.join(d, "o.json"), os.path.join(d, "d.tsv"))
        eq((rc, buf.getvalue()), (2, ""), "NOTES_DIR missing")
        ok(err.getvalue().startswith("notes_meta: ") and "NOTES_DIR" in err.getvalue(), err.getvalue())
        _put(os.path.join(d, "n", "01-a.md"), NOTE())
        _put(os.path.join(d, "o.json"), json.dumps(OL(G("g1"))))
        _put(os.path.join(d, "d.tsv"), DECLS)
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = run(os.path.join(d, "n"), os.path.join(d, "o.json"), os.path.join(d, "d.tsv"), src=os.path.join(d, "nope"))
        eq((rc, buf.getvalue()), (2, ""), "--src not a directory")
        ok(err.getvalue().startswith("notes_meta: ") and "--src" in err.getvalue(), err.getvalue())


@case("X2c", "usage errors are exit 2 with the usage text: no arguments, too few, an unknown option, an option without value")
def _():
    for argv in ([], ["a"], ["a", "b"], ["a", "b", "c", "--bogus"], ["a", "b", "c", "--base"], ["a", "b", "c", "d"],
                 ["--selftest", "x"]):
        err = io.StringIO()
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            rc = main(argv, check=lambda: 0)
        eq(rc, 2, repr(argv))
        ok("usage" in err.getvalue(), "usage text on stderr for " + repr(argv))


@case("EXIT4", "a failing self-test makes a normal run exit 4 with REFUSED on stderr and nothing on stdout; control: a passing one runs")
def _():
    with tempfile.TemporaryDirectory() as d:
        nd = os.path.join(d, "notes")
        _put(os.path.join(nd, "01-a.md"), NOTE())
        _put(os.path.join(d, "o.json"), json.dumps(OL(G("g1"))))
        _put(os.path.join(d, "d.tsv"), DECLS)
        argv = [nd, os.path.join(d, "o.json"), os.path.join(d, "d.tsv")]
        for check, want in ((lambda: 1, 4), (lambda: 0, 0)):
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = main(argv, check=check)
            eq(rc, want, "exit")
            if want == 4:
                eq(out.getvalue(), "", "nothing on stdout")
                ok(err.getvalue().startswith("REFUSED: selftest failed"), err.getvalue())
            else:
                ok(out.getvalue().startswith("note 01 header ok, blocks 0"), out.getvalue())


@case("SUM", "the whole output of a small run, literal: note lines, FRAME-NOTE skip notice, counts by kind, what did not run, totals")
def _():
    body = "Some text.\n" + BL("01.b01") + "\n" + BL("01.b02", kind="not_read", needs="callers") + "\n"
    notes = {"01-a.md": NOTE(body=body), "02-b.md": NOTE(nid="02", body="Plain.\n"), "03-c.md": "# T\n"}
    r = go(notes=notes)
    eq(r.lines, ["note 01 header ok, blocks 2 (reading=1 not_read=1)",
                 "note 02 header ok, blocks 0",
                 "NO-HEADER 03-c.md: no rh-note header",
                 "note 03-c header FAILED, blocks 0",
                 "FRAME-NOTE skipped: no strings file",
                 "blocks by kind: machine_fact=0 reading=1 interpretation=0 correction=0 not_read=1 argument=0",
                 "in-file check (M5): skipped, no --src given",
                 "byte check: did not run, no --base given",
                 "3 notes, 1 findings, 0 warnings"], "output")
    eq(r.rc, 1, "exit")


@case("RUNNER", "selftest exit codes: 0 all pass, 1 any fail, 3 no case ran; a crash is a failure")
def _():
    quiet = lambda s: None  # noqa: E731
    eq(_run_cases([], quiet), 3, "no cases")
    eq(_run_cases([("p", "d", lambda: None)], quiet), 0, "pass")
    eq(_run_cases([("p", "d", lambda: None), ("f", "d", lambda: eq(1, 2))], quiet), 1, "one fails")
    eq(_run_cases([("c", "d", lambda: 1 / 0)], quiet), 1, "a crash is a failure")
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        eq(main(["--selftest", "x"]), 2, "extra")
    ok("usage" in err.getvalue(), "usage text")


# ---- outline
@case("O1a", "group ids are unique: a repeated id is DUPLICATE-ID naming the group; control: distinct ids")
def _():
    fe(go(outline=OL(G("g1"), G("g1", order=2))), ["DUPLICATE-ID outline.json group 'g1': id is used by more than one group"], 1)
    clean(go(outline=OL(G("g1"), G("g2", order=2))))


@case("O1b", "an id that is empty or not a string is BAD-VALUE on the group's position")
def _():
    fe(go(outline=OL(G("g1"), G("", order=2), G(5, order=3))),
       ["BAD-VALUE outline.json groups[1]: id must be a non-empty string",
        "BAD-VALUE outline.json groups[2]: id must be a non-empty string"], 1)


@case("O1c", "level, order, parent, roots and premises of the wrong type are BAD-VALUE naming the field; a group that is not an object too")
def _():
    g = "BAD-VALUE outline.json group 'g1': "
    table = [
        (dict(G("g1"), level=0), g + "level must be an integer of 1 or more"),
        (dict(G("g1"), level="1"), g + "level must be an integer of 1 or more"),
        (dict(G("g1"), level=True), g + "level must be an integer of 1 or more"),
        (dict(G("g1"), level=1.5), g + "level must be an integer of 1 or more"),
        (dict(G("g1"), order="x"), g + "order must be an integer"),
        (dict(G("g1"), order=True), g + "order must be an integer"),
        (dict(G("g1"), parent=5), g + "parent must be a non-empty string"),
        (dict(G("g1"), roots="x"), g + "roots must be a list"),
        (dict(G("g1"), roots=[R("A.B", "")]), g + "roots[0] must be an object with non-empty string module and name"),
        (dict(G("g1"), roots=[{"module": "A.B"}]), g + "roots[0] must be an object with non-empty string module and name"),
        (dict(G("g1"), roots=["A.B"]), g + "roots[0] must be an object with non-empty string module and name"),
        (dict(G("g1"), premises="x"), g + "premises must be a list"),
        (dict(G("g1"), premises=[5]), g + "premises[0] must be a string id"),
    ]
    for grp, want in table:
        fe(go(outline=OL(grp)), [want], 1)
    fe(go(outline=OL(G("g1"), "x")), ["BAD-VALUE outline.json groups[1]: must be a JSON object"], 1)


@case("O1d", "unknown and missing keys: the draft-only keys of the pilot outline fail until stripped; every required key is required")
def _():
    fe(go(outline=OL(G("g1"), _draft="x")), ["UNKNOWN-KEY outline.json top level: unknown key '_draft'"], 1)
    fe(go(outline=OL(dict(G("g1"), premises_basis="p"))), ["UNKNOWN-KEY outline.json group 'g1': unknown key 'premises_basis'"], 1)
    fe(go(outline=OL(dict(G("g1"), draft_todo="t", premises_basis="p"))),
       ["UNKNOWN-KEY outline.json group 'g1': unknown key 'draft_todo'",
        "UNKNOWN-KEY outline.json group 'g1': unknown key 'premises_basis'"], 1)
    fe(go(outline={"groups": [G("g1")]}), ["MISSING-KEY outline.json top level: missing key 'release'"], 1)
    fe(go(outline={"groups": [G("g1")], "release": ""}), ["BAD-VALUE outline.json top level: release must be a non-empty string"], 1)
    nog = "UNKNOWN-GROUP 01-a.md:2 group 'g1' is not in the outline"   # the notes then have no group to belong to
    fe(go(outline={"release": "r"}), ["MISSING-KEY outline.json top level: missing key 'groups'", nog], 1)
    fe(go(outline={"groups": "x", "release": "r"}), ["BAD-VALUE outline.json top level: groups must be a list", nog], 1)
    fe(go(outline=["x"]), ["BAD-VALUE outline.json top level: must be a JSON object", nog], 1)
    fe(go(outline=OL(G("g1"), drop(G("g2", order=2), "premises"))), ["MISSING-KEY outline.json group 'g2': missing key 'premises'"], 1)
    fe(go(outline=OL(G("g1"), drop(G("g2", order=2), "claim"))), ["MISSING-KEY outline.json group 'g2': missing key 'claim'"], 1)
    fe(go(outline=OL(G("g1"), drop(G("g2", order=2), "roots"))), ["MISSING-KEY outline.json group 'g2': missing key 'roots'"], 1)


@case("O2a", "a child's level is its parent's plus one; a deeper or equal level is BAD-LEVEL; control: plus one")
def _():
    msg = "BAD-LEVEL outline.json group 'c': level %d, but parent 'g1' has level 1 (a child is one deeper than its parent)"
    fe(go(outline=OL(G("g1"), G("c", level=3, parent="g1"))), [msg % 3], 1)
    fe(go(outline=OL(G("g1"), G("c", level=1, parent="g1"))), [msg % 1], 1)
    clean(go(outline=OL(G("g1"), G("c", level=2, parent="g1"))))


@case("O2b", "a group under root has level 1; a parent that is neither root nor a group id is BAD-PARENT and nothing more")
def _():
    fe(go(outline=OL(G("g1", level=2))),
       ["BAD-LEVEL outline.json group 'g1': level 2, but its parent is 'root' (a group under root has level 1)"], 1)
    fe(go(outline=OL(G("g1"), G("c", level=2, parent="zz"))),
       ["BAD-PARENT outline.json group 'c': parent 'zz' is neither 'root' nor a group id"], 1)


@case("O2c", "order is unique among siblings only: the same order under two parents is fine")
def _():
    fe(go(outline=OL(G("g1"), G("b", order=1))),
       ["DUPLICATE-ORDER outline.json group 'b': order 1 is also used by group 'g1' under parent 'root'"], 1)
    fe(go(outline=OL(G("g1"), G("c1", level=2, parent="g1"), G("c2", level=2, parent="g1"))),
       ["DUPLICATE-ORDER outline.json group 'c2': order 1 is also used by group 'c1' under parent 'g1'"], 1)
    clean(go(outline=OL(G("g1"), G("g2", order=2), G("c1", level=2, parent="g1"), G("c2", level=2, parent="g2"))))


@case("O2d", "no maximum depth: a chain of six levels passes")
def _():
    chain = [G("g1"), G("d2", level=2, parent="g1"), G("d3", level=3, parent="d2"), G("d4", level=4, parent="d3"),
             G("d5", level=5, parent="d4"), G("d6", level=6, parent="d5")]
    clean(go(outline=OL(*chain)))


@case("O3a", "a premise that is not a group id is BAD-PREMISE; a group that is its own premise too")
def _():
    fe(go(outline=OL(G("g1", premises=["zz"]))), ["BAD-PREMISE outline.json group 'g1': premise 'zz' is not a group id"], 1)
    fe(go(outline=OL(G("g1", premises=["g1"]))), ["BAD-PREMISE outline.json group 'g1': premise 'g1' is the group itself"], 1)


@case("O3b", "a cycle through premises is PREMISE-CYCLE naming it once: a -> b -> c -> a")
def _():
    fe(go(outline=OL(G("g1"), G("a", order=2, premises=["b"]), G("b", order=3, premises=["c"]), G("c", order=4, premises=["a"]))),
       ["PREMISE-CYCLE outline.json premises form a cycle: a -> b -> c -> a"], 1)
    clean(go(outline=OL(G("g1"), G("a", order=2, premises=["b"]), G("b", order=3, premises=["c"]), G("c", order=4))))


@case("O3c", "a premise may be the group's own child or a group of any depth")
def _():
    clean(go(outline=OL(G("g1", premises=["c1"]), G("c1", level=2, parent="g1", premises=["d1"]),
                        G("d1", level=3, parent="c1"), G("g2", order=2, premises=["g1", "d1"]))))


@case("O3d", "the check is over premises only: a parent edge that would close a cycle with a premise edge is legal")
def _():
    clean(go(outline=OL(G("g1", premises=["c1"]), G("c1", level=2, parent="g1"))))
    fe(go(outline=OL(G("g1", premises=["c1"]), G("c1", level=2, parent="g1", premises=["g1"]))),
       ["PREMISE-CYCLE outline.json premises form a cycle: g1 -> c1 -> g1"], 1)


@case("O4", "a non-null claim needs exactly one root (0 and 2 are ROOT-COUNT); a null claim may have 0, 1 or 3")
def _():
    one = [R("A.B", "foo")]
    clean(go(outline=OL(G("g1", roots=one, claim=CLAIM))))
    fe(go(outline=OL(G("g1", roots=one + [R("A.C", "baz")], claim=CLAIM))),
       ["ROOT-COUNT outline.json group 'g1': a group with a claim has exactly one root, not 2"], 1)
    fe(go(outline=OL(G("g1", roots=[], claim=CLAIM))),
       ["ROOT-COUNT outline.json group 'g1': a group with a claim has exactly one root, not 0"], 1)
    for roots in ([], one, one + [R("A.C", "baz"), R("A.B", "bar")]):
        clean(go(outline=OL(G("g1", roots=roots, claim=None))))


@case("O5a", "a claim with every optional key passes; defs_opened may be empty")
def _():
    full = dict(CLAIM, conditions=["c1", "c2"], mathlib_read=["Mathlib.X", ""], conventions_checked=["a", "b", "c", "d", "e"],
                defs_opened=[{"module": "A.C", "name": "baz", "lines": [5, 9]}])
    clean(go(outline=OL(G("g1", roots=[R("A.B", "foo")], claim=full))))
    clean(go(outline=OL(G("g1", roots=[R("A.B", "foo")], claim=dict(CLAIM, defs_opened=[], conventions_checked=[])))))


@case("O5b", "an unknown claim key is UNKNOWN-KEY; each of the five required keys is required; a claim that is not an object")
def _():
    one = [R("A.B", "foo")]
    pre = "outline.json group 'g1' claim: "
    fe(go(outline=OL(G("g1", roots=one, claim=dict(CLAIM, notes="x")))), ["UNKNOWN-KEY " + pre + "unknown key 'notes'"], 1)
    for k in ("text", "reader", "date", "defs_opened", "conventions_checked"):
        fe(go(outline=OL(G("g1", roots=one, claim=drop(CLAIM, k)))), ["MISSING-KEY " + pre + "missing key '" + k + "'"], 1)
    fe(go(outline=OL(G("g1", roots=one, claim="x"))), ["BAD-VALUE outline.json group 'g1': claim must be an object or null"], 1)


@case("O5c", "claim values of the wrong shape are BAD-VALUE naming the field")
def _():
    one = [R("A.B", "foo")]
    pre = "BAD-VALUE outline.json group 'g1' claim: "
    entry = "defs_opened[0] must be an object with non-empty string module and name and lines [first, last] of two integers"
    table = [
        (dict(CLAIM, text=""), pre + "text must be a non-empty string"),
        (dict(CLAIM, reader=5), pre + "reader must be a non-empty string"),
        (dict(CLAIM, date=""), pre + "date must be a non-empty string"),
        (dict(CLAIM, defs_opened="x"), pre + "defs_opened must be a list"),
        (dict(CLAIM, defs_opened=[{"module": "A.C", "name": "baz", "lines": [1]}]), pre + entry),
        (dict(CLAIM, defs_opened=[{"module": "A.C", "name": "baz"}]), pre + entry),
        (dict(CLAIM, defs_opened=[{"module": "A.C", "name": "baz", "lines": [1, True]}]), pre + entry),
        (dict(CLAIM, conventions_checked=["f"]), pre + "conventions_checked must be a list of letters a to e"),
        (dict(CLAIM, conventions_checked="a"), pre + "conventions_checked must be a list of letters a to e"),
        (dict(CLAIM, conditions=[""]), pre + "conditions must be a list of non-empty strings"),
        (dict(CLAIM, conditions="x"), pre + "conditions must be a list of non-empty strings"),
        (dict(CLAIM, mathlib_read=[1]), pre + "mathlib_read must be a list of strings"),
        (dict(CLAIM, mathlib_read="x"), pre + "mathlib_read must be a list of strings"),
    ]
    for claim, want in table:
        fe(go(outline=OL(G("g1", roots=one, claim=claim))), [want], 1)
    clean(go(outline=OL(G("g1", roots=one, claim=dict(CLAIM, defs_opened=[{"module": "A.C", "name": "baz", "lines": [9, 5]}])))))


@case("O6", "a roots or defs_opened entry must resolve to exactly one row: UNRESOLVED, AMBIGUOUS with the candidates; control: resolves")
def _():
    fe(go(outline=OL(G("g1", roots=[R("A.B", "nope")]))), ["UNRESOLVED outline.json group 'g1' roots[0] A.B nope: no row in decls.tsv"], 1)
    fe(go(outline=OL(G("g1", roots=[R("A.B", "foo"), R("A.D", "dup")]))),
       ["AMBIGUOUS outline.json group 'g1' roots[1] A.D dup: 2 rows; candidates (first_line, last_line): (1, 3), (7, 9)"], 1)
    d = [{"module": "A.C", "name": "nope", "lines": [1, 2]}, {"module": "A.D", "name": "dup", "lines": [1, 2]}]
    fe(go(outline=OL(G("g1", roots=[R("A.B", "foo")], claim=dict(CLAIM, defs_opened=d)))),
       ["UNRESOLVED outline.json group 'g1' claim defs_opened[0] A.C nope: no row in decls.tsv",
        "AMBIGUOUS outline.json group 'g1' claim defs_opened[1] A.D dup: 2 rows; candidates (first_line, last_line): (1, 3), (7, 9)"], 1)
    clean(go(outline=OL(G("g1", roots=[R("A.B", "foo"), R("A.C", "baz")]))))


# ---- notes
@case("M1", "exactly one header, before the first ## heading: NO-HEADER, SECOND-HEADER naming both lines, HEADER-AFTER-H2; a fenced one does not count")
def _():
    r = go(notes={"01-a.md": "# T\n\ntext\n"})
    fe(r, ["NO-HEADER 01-a.md: no rh-note header"], 1)
    ok("note 01-a header FAILED, blocks 0" in r.lines, "the note line uses the file name when there is no id")
    two = NOTE(body="Text.\n" + rh.format_comment("rh-note", {"id": "01"}) + "\n")
    fe(go(notes={"01-a.md": two}), ["SECOND-HEADER 01-a.md:7 2 rh-note headers, on lines 2, 7"], 1)
    late = "# T\n\n## Body\n\n" + rh.format_comment("rh-note", {"authors": ["H"], "group": "g1", "id": "01", "level": 2,
                                                                  "list_title": "A title", "readers": ["K"], "release": "r"}) + "\n"
    fe(go(notes={"01-a.md": late}), ["HEADER-AFTER-H2 01-a.md:5 the rh-note header comes after the first '## ' heading"], 1)
    fenced = "# T\n\n```\n" + rh.format_comment("rh-note", {"id": "01"}) + "\n```\n"
    fe(go(notes={"01-a.md": fenced}), ["NO-HEADER 01-a.md: no rh-note header"], 1)


@case("M2a", "header_problems() findings, level 0 to 2, and a group that is not in the outline")
def _():
    fe(go(notes={"01-a.md": NOTE(level=3)}), ["HEADER-PROBLEM 01-a.md:2 level: must be 0, 1 or 2"], 1)
    fe(go(notes={"01-a.md": NOTE(readers=None)}), ["HEADER-PROBLEM 01-a.md:2 readers: missing or not a list"], 1)
    fe(go(notes={"01-a.md": NOTE(group="zz")}), ["UNKNOWN-GROUP 01-a.md:2 group 'zz' is not in the outline"], 1)
    for lv in (0, 1, 2):
        clean(go(notes={"01-a.md": NOTE(level=lv)}))


@case("M2b", "list_title: not only code spans, no trailing parenthetical; titles with code inside or a parenthetical inside are fine")
def _():
    for t in ("`foo`", "`a` `b`", "``a`b``"):
        fe(go(notes={"01-a.md": NOTE(title=t)}), ["TITLE-BACKTICK-ONLY 01-a.md:2 list_title is only code: " + repr(t)], 1)
    for t in ("Title (draft)", "Title (a (b))", "Title (x)  "):
        fe(go(notes={"01-a.md": NOTE(title=t)}), ["TITLE-PARENTHETICAL 01-a.md:2 list_title ends with a parenthetical: " + repr(t)], 1)
    for t in ("Plain title", "A `code` title", "A (mid) title", "Ends with a bracket)", "(Opens) and goes on", "`a` and b", "A `lone"):
        clean(go(notes={"01-a.md": NOTE(title=t)}))


@case("M3a", "every block goes through rh_anchor.problems with the header id: a wrong note prefix, no kind, a missing field")
def _():
    n = lambda b: {"01-a.md": NOTE(body="Some text.\n" + b + "\n")}  # noqa: E731
    fe(go(notes=n(BL("02.b01"))), ["BLOCK-PROBLEM 01-a.md:7 block '02.b01': id: '02.b01' is not <note id>.b<nn> for note '01'"], 1)
    fe(go(notes=n(rh.format_comment("rh-block", {"id": "01.b01"}))),
       ["BLOCK-PROBLEM 01-a.md:7 block '01.b01': kind: must be one of machine_fact, reading, interpretation, correction, not_read, argument"], 1)
    fe(go(notes=n(BL(kind="not_read"))),
       ["BLOCK-PROBLEM 01-a.md:7 block '01.b01': needs: must be one of callers, route, enclosing, resolve, fields_read, uses, hand_read, full_build"], 1)
    fe(go(notes=n(BL(kind="machine_fact", check="text", tool_version="v", options=""))),
       ["BLOCK-PROBLEM 01-a.md:7 block '01.b01': tool: a machine_fact needs a non-empty string"], 1)
    fe(go(notes=n(BL(second_readers=[{"reader": "K"}]))),
       ["BLOCK-PROBLEM 01-a.md:7 block '01.b01': second_readers[0].date: must be a non-empty string"], 1)
    clean(go(notes=n(BL(second_readers=[{"reader": "K", "date": "2026-11-23"}]))))


@case("M3b", "a block id used twice, in one note or in two, is DUPLICATE-ID naming both places")
def _():
    two = NOTE(body="Some text.\n" + BL() + "\n" + BL() + "\n")
    fe(go(notes={"01-a.md": two}), ["DUPLICATE-ID 01-a.md:8 block id '01.b01' is also used at 01-a.md:7"], 1)
    one = NOTE(body="Some text.\n" + BL() + "\n")
    fe(go(notes={"01-a.md": one, "02-b.md": one}), ["DUPLICATE-ID 02-b.md:7 block id '01.b01' is also used at 01-a.md:7"], 1)
    clean(go(notes={"01-a.md": one, "02-b.md": NOTE(nid="02", body="Some text.\n" + BL("02.b01") + "\n")}))


@case("M4", "a decls entry resolves to exactly one row: UNRESOLVED, AMBIGUOUS with the candidates; control: resolves")
def _():
    n = lambda *d: {"01-a.md": NOTE(body="Some text.\n" + BL(decls=list(d)) + "\n")}  # noqa: E731
    fe(go(notes=n(R("A.B", "nope"))), ["UNRESOLVED 01-a.md:7 block '01.b01' decls[0] A.B nope: no row in decls.tsv"], 1)
    fe(go(notes=n(R("A.B", "foo"), R("A.D", "dup"))),
       ["AMBIGUOUS 01-a.md:7 block '01.b01' decls[1] A.D dup: 2 rows; candidates (first_line, last_line): (1, 3), (7, 9)"], 1)
    clean(go(notes=n(R("A.B", "foo"), R("A.C", "baz"))))


def _m5(**kw):
    return {"01-a.md": NOTE(body="Some text.\n" + BL(file="A/B.lean", **kw) + "\n" + FILES)}


@case("M5a", "with --src: a file the table does not list is FILE-NOT-LISTED; a listed file that is absent is FILE-MISSING; "
             "lines past the end are LINES-OUTSIDE-FILE; control: inside passes")
def _():
    src = {"A/B.lean": SRC40}
    clean(go(notes=_m5(lines=[12, 15]), src=src))
    fe(go(notes={"01-a.md": NOTE(body="Some text.\n" + BL(file="A/Z.lean", lines=[1, 2]) + "\n" + FILES)}, src=src),
       ["FILE-NOT-LISTED 01-a.md:7 block '01.b01' file A/Z.lean is not in the note's file table"], 1)
    fe(go(notes=_m5(lines=[12, 15]), src={"A/Other.lean": "x\n"}),
       ["FILE-MISSING 01-a.md:7 block '01.b01' file A/B.lean is listed but not found under --src"], 1)
    fe(go(notes=_m5(lines=[30, 45]), src=src), ["LINES-OUTSIDE-FILE 01-a.md:7 block '01.b01' lines [30, 45] but A/B.lean has 40 lines"], 1)
    clean(go(notes=_m5(lines=[40, 40]), src=src))
    fe(go(notes={"01-a.md": NOTE(body="Some text.\n" + BL(file="A/B.lean", lines=[1, 2]) + "\n")}, src=src),
       ["FILE-NOT-LISTED 01-a.md:7 block '01.b01' file A/B.lean is not in the note's file table"], 1)


@case("M5b", "lines outside the text extent of every resolved row are an EXTENT-WARNING listing (exit unchanged); inside one row is fine")
def _():
    src = {"A/B.lean": SRC40}
    r = go(notes=_m5(lines=[12, 25], decls=[R("A.B", "foo")]), src=src)
    fe(r, ["EXTENT-WARNING 01-a.md:7 block '01.b01' lines [12, 25] are outside the text extent of every resolved row: A.B foo (10, 20)"], 0)
    ok(r.lines[-1] == "1 notes, 0 findings, 1 warnings", r.lines[-1])
    clean(go(notes=_m5(lines=[10, 20], decls=[R("A.B", "foo")]), src=src))
    clean(go(notes=_m5(lines=[31, 35], decls=[R("A.B", "foo"), R("A.B", "bar")]), src=src))
    fe(go(notes=_m5(lines=[1, 2], decls=[R("A.B", "foo"), R("A.B", "bar")]), src=src),
       ["EXTENT-WARNING 01-a.md:7 block '01.b01' lines [1, 2] are outside the text extent of every resolved row: "
        "A.B foo (10, 20); A.B bar (30, 40)"], 0)
    clean(go(notes=_m5(lines=[1, 2]), src=src))


@case("M5c", "without --src the in-file check is skipped and the summary says so; the extent listing still runs; with --src the summary says it ran")
def _():
    r = go(notes=_m5(lines=[30, 45]))
    ok("in-file check (M5): skipped, no --src given" in r.lines, r.out)
    eq(r.f, [], "no in-file finding without --src")
    r = go(notes=_m5(lines=[12, 15]), src={"A/B.lean": SRC40})
    ok("in-file check (M5): ran" in r.lines, r.out)
    r = go(notes=_m5(lines=[12, 25], decls=[R("A.B", "foo")]))
    eq([x[:14] for x in r.f], ["EXTENT-WARNING"], "extent listing without --src")


@case("M6a", "MALFORMED, UNCLOSED-FENCE and INSIDE-TABLE from the parser are errors naming the line")
def _():
    fe(go(notes={"01-a.md": NOTE(body="Some text.\n<!-- rh-block {bad} -->\n")}),
       ["MALFORMED 01-a.md:7 Line 7 starts an rh- comment that is not one complete `<!-- rh-note {...} -->` or "
        "`<!-- rh-block {...} -->` line with a JSON object."], 1)
    fe(go(notes={"01-a.md": NOTE(body="```lean\nx\n")}), ["UNCLOSED-FENCE 01-a.md:6 The code fence opened on line 6 is never closed."], 1)
    tab = "| a | b |\n|---|---|\n| 1 | 2 |\n" + BL(row=1) + "\n| 3 | 4 |\n"
    fe(go(notes={"01-a.md": NOTE(body=tab)}), ["INSIDE-TABLE 01-a.md:9 Line 9 puts an rh- comment between two table rows."], 1)


@case("M6b", "a line that is not canonical is NONCANONICAL and prints the canonical form; a header too")
def _():
    loose = '<!-- rh-block {"id": "01.b01", "kind": "reading"} -->'
    fe(go(notes={"01-a.md": NOTE(body="Some text.\n" + loose + "\n")}),
       ['NONCANONICAL 01-a.md:7 not the canonical form; canonical: <!-- rh-block {"id":"01.b01","kind":"reading"} -->'], 1)
    h = rh.format_comment("rh-note", {"authors": ["H"], "group": "g1", "id": "01", "level": 2, "list_title": "A title",
                                       "readers": ["K"], "release": "rel-1"})
    spaced = "# Note\n" + h.replace('{"authors"', '{ "authors"') + "\n\n## Body\n\nText.\n"
    r = go(notes={"01-a.md": spaced})
    eq(len(r.f), 1, r.out)
    ok(r.f[0].startswith("NONCANONICAL 01-a.md:2 not the canonical form; canonical: <!-- rh-note {"), r.f[0])


@case("M7", "row and col: the target must be a table, row <= body rows, col <= columns; the block of a whole table has neither")
def _():
    tab = "| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |\n"
    n = lambda *b: {"01-a.md": NOTE(body=tab + "\n".join(b) + "\n")}  # noqa: E731
    clean(go(notes=n(BL("01.b01", row=1), BL("01.b02", row=2, col=3), BL("01.b03"))))
    fe(go(notes=n(BL(row=3))), ["ROW-OUT-OF-RANGE 01-a.md:10 block '01.b01' row 3 but the table has 2 body rows"], 1)
    fe(go(notes=n(BL(row=1, col=4))), ["COL-OUT-OF-RANGE 01-a.md:10 block '01.b01' col 4 but the table has 3 columns"], 1)
    fe(go(notes={"01-a.md": NOTE(body="Some text.\n" + BL(row=1) + "\n")}),
       ["NOT-A-TABLE 01-a.md:7 block '01.b01' carries row/col but its target is of type 'paragraph', not a table"], 1)
    fe(go(notes={"01-a.md": NOTE(body="```lean\nx\n```\n" + BL(row=1, col=1) + "\n")}),
       ["NOT-A-TABLE 01-a.md:9 block '01.b01' carries row/col but its target is of type 'lean', not a table"], 1)


FR = {"frames": {"claim": ["From"], "argument": ["How this is proved, as"], "interpretation": ["We think", "Our reading is that"]}}


@case("F12a", "an argument whose text opens with another kind's frame is a FRAME-NOTE listing; its own frame, a reading block and case/emphasis")
def _():
    n = lambda text, b: {"01-a.md": NOTE(body=text + "\n" + b + "\n")}  # noqa: E731
    r = go(notes=n("We think this works.", ARG()), strings=FR)
    fe(r, ["FRAME-NOTE 01-a.md:7 block '01.b01' (argument): the text opens with a frame of kind 'interpretation' ('We think')"], 0)
    ok(r.lines[-1] == "1 notes, 0 findings, 1 warnings", r.lines[-1])
    fe(go(notes=n("*We THINK* this works.", ARG()), strings=FR),
       ["FRAME-NOTE 01-a.md:7 block '01.b01' (argument): the text opens with a frame of kind 'interpretation' ('We think')"], 0)
    fe(go(notes=n("From A and B it follows that X.", ARG()), strings=FR),
       ["FRAME-NOTE 01-a.md:7 block '01.b01' (argument): the text opens with a frame of kind 'claim' ('From')"], 0)
    clean(go(notes=n("How this is proved, as K read it: A then B.", ARG()), strings=FR))
    clean(go(notes=n("We think this works.", BL()), strings=FR))
    ib = BL(kind="interpretation", reader="R", date="2026-11-23")
    fe(go(notes=n("How this is proved, as K read it.", ib), strings=FR),
       ["FRAME-NOTE 01-a.md:7 block '01.b01' (interpretation): the text opens with a frame of kind 'argument' ('How this is proved, as')"], 0)
    clean(go(notes=n("Our reading is that it works.", ib), strings=FR))
    fe(go(notes=n("How this is proved, as K read it.", ib), strings={"frames": {"argument": ["How this is proved, as {reader} read it"]}}),
       ["FRAME-NOTE 01-a.md:7 block '01.b01' (interpretation): the text opens with a frame of kind 'argument' ('How this is proved, as')"], 0)


@case("F12b", "without --strings one line says the check was skipped and no FRAME-NOTE is made; a block on a table is not read for frames")
def _():
    r = go(notes={"01-a.md": NOTE(body="We think this works.\n" + ARG() + "\n")})
    ok("FRAME-NOTE skipped: no strings file" in r.lines, r.out)
    eq((r.f, r.rc), ([], 0), "no finding")
    tab = "| We think | b |\n|---|---|\n| 1 | 2 |\n"
    clean(go(notes={"01-a.md": NOTE(body=tab + ARG() + "\n")}, strings=FR))
    r = go(strings=FR)
    ok("FRAME-NOTE skipped: no strings file" not in r.lines, "with a strings file there is no skip notice")


# ---- bytes
T0 = "# Note\n\n## Body\n\nSome text.\nMore text.\n"      # a note as published: no anchor lines
CUR = NOTE(body="Some text.\nMore text.\n")    # the same note with its header comment


@case("B1a", "with --base: the note at REV equals the current note without its anchor lines; control: the summary says the check ran")
def _():
    cur = NOTE(body="Some text.\n" + BL() + "\nMore text.\n" + BL("01.b02") + "\n")
    r = go(notes={"01-a.md": cur}, committed={"01-a.md": T0}, base="HEAD")
    eq((r.f, r.rc), ([], 0), r.out)
    ok("byte check: ran against HEAD" in r.lines, r.out)
    r = go(notes={"01-a.md": cur}, committed={"01-a.md": T0}, base="HEAD", repo_arg=True)
    eq((r.f, r.rc), ([], 0), "--repo given")


@case("B1b", "BYTE-DIFF names the note and the first differing line, in the published text; a line ending is a difference")
def _():
    cur = NOTE(body="Some texts.\n" + BL() + "\nMore text.\n")
    fe(go(notes={"01-a.md": cur}, committed={"01-a.md": T0}, base="HEAD"),
       ["BYTE-DIFF 01-a.md:5 line 5 of the published text differs: published 'Some text.\\n', without anchors 'Some texts.\\n'"], 1)
    crlf = T0.replace("\n", "\r\n")
    fe(go(notes={"01-a.md": CUR}, committed={"01-a.md": crlf}, base="HEAD"),
       ["BYTE-DIFF 01-a.md:1 line 1 of the published text differs: published '# Note\\r\\n', without anchors '# Note\\n'"], 1)
    short = "# Note\n\n## Body\n\nSome text.\n"
    fe(go(notes={"01-a.md": NOTE(body="Some text.\n")}, committed={"01-a.md": T0}, base="HEAD"),
       ["BYTE-DIFF 01-a.md:6 line 6 of the published text differs: published 'More text.\\n', without anchors <no line>"], 1)
    fe(go(notes={"01-a.md": CUR}, committed={"01-a.md": short}, base="HEAD"),
       ["BYTE-DIFF 01-a.md:6 line 6 of the published text differs: published <no line>, without anchors 'More text.\\n'"], 1)


@case("B1c", "CRLF notes compare by bytes: anchors added with CRLF endings leave the note equal to the commit")
def _():
    crlf = T0.replace("\n", "\r\n")
    cur = NOTE(body="Some text.\n" + BL() + "\nMore text.\n").replace("\n", "\r\n")
    r = go(notes={"01-a.md": cur}, committed={"01-a.md": crlf}, base="HEAD")
    eq((r.f, r.rc), ([], 0), r.out)


@case("B1d", "a note not present at REV is NEW-NOTE (a listing, exit unchanged); without --base the summary says the byte check did not run")
def _():
    r = go(notes={"01-a.md": CUR, "02-b.md": NOTE(nid="02")}, committed={"01-a.md": T0}, base="HEAD")
    eq((r.f, r.rc), (["NEW-NOTE 02-b.md: not present at HEAD"], 0), r.out)
    ok(r.lines[-1] == "2 notes, 0 findings, 1 warnings", r.lines[-1])
    r = go(notes={"01-a.md": CUR})
    ok("byte check: did not run, no --base given" in r.lines, r.out)


# ---- the shape of the pilot outline
def _real():
    d = [{"module": "A.C", "name": "baz", "lines": [5, 9]}]
    c1 = dict(CLAIM, conditions=["No exception at s = 1."], mathlib_read=["Mathlib.NumberTheory.X"], defs_opened=d,
              conventions_checked=["a", "d"])
    return [
        G("g1", level=1, order=1, roots=[R("A.B", "foo")], claim=c1, premises=["g2", "d1"]),
        G("g2", level=1, order=2, roots=[R("A.B", "bar")], claim=dict(CLAIM), premises=["g3"]),
        G("g3", level=1, order=3, roots=[R("A.C", "baz")], claim=None, premises=[]),
        G("c1", level=2, parent="g3", order=1, roots=[R("A.B", "foo")], claim=dict(CLAIM), premises=[]),
        G("c2", level=2, parent="g3", order=2, roots=[], claim=None, premises=["c1"]),
        G("d1", level=3, parent="c2", order=1, roots=[R("A.B", "bar")], claim=None, premises=[]),
        G("d2", level=4, parent="d1", order=1, roots=[R("A.D", "dup"), R("A.C", "baz")], claim=None, premises=["g3"]),
    ]


@case("REAL1", "an outline in the pilot's shape (depth 4, a step whose premises name a deeper group, null and non-null claims) passes")
def _():
    clean(go(outline=OL(*_real())))


@case("REAL2", "the same outline with the draft-only keys added fails UNKNOWN-KEY on each: the top-level _draft, premises_basis, draft_todo")
def _():
    gs = _real()
    gs[0] = dict(gs[0], premises_basis="p")
    gs[5] = dict(gs[5], draft_todo="t")
    r = go(outline=OL(*gs, _draft="v0.3"))
    fe(r, ["UNKNOWN-KEY outline.json top level: unknown key '_draft'",
           "UNKNOWN-KEY outline.json group 'g1': unknown key 'premises_basis'",
           "UNKNOWN-KEY outline.json group 'd1': unknown key 'draft_todo'"], 1)


@case("ORDER", "notes are checked in name order whatever the directory order; each note's findings come before its note line")
def _():
    bad = NOTE(level=3)
    r = go(notes={"02-b.md": bad.replace('"id":"01"', '"id":"02"'), "01-a.md": bad})
    eq(r.lines[:4], ["HEADER-PROBLEM 01-a.md:2 level: must be 0, 1 or 2", "note 01 header FAILED, blocks 0",
                     "HEADER-PROBLEM 02-b.md:2 level: must be 0, 1 or 2", "note 02 header FAILED, blocks 0"], "order")


def _run_cases(cases, write):
    """Run (id, what, fn) cases; write(line) for each report line. Exit code: 0, 1 (a failure), 3 (none ran)."""
    failed = 0
    for cid, what, fn in cases:
        try:
            fn()
            write(f"CASE {cid} PASS {what}")
        except Exception as e:  # a crash is a failed case
            failed += 1
            write(f"CASE {cid} FAIL {what}")
            write(f"  detail: {type(e).__name__}: {e}")
    write(f"{len(cases)} cases, {failed} failed")
    if not cases:
        write("CHECKED NOTHING: no case ran")
        return 3
    return 1 if failed else 0


def selftest():
    print("# cases range over: the command line and exit codes (X), the outline (O1 to O6), the notes (M1 to M7), frames (F12),")
    print("# the byte check (B1), the pilot outline's shape (REAL) and the output order. Expected values are literals.")
    return _run_cases(_CASES, print)


def selftest_quiet():
    with contextlib.redirect_stdout(io.StringIO()):
        return selftest()


def main(argv=None, check=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--selftest"]:
        return selftest()
    return 99   # stub: the command line is not written yet


if __name__ == "__main__":
    sys.exit(main())
