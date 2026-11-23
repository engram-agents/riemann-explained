#!/usr/bin/env python3
"""STUB: the shared anchor-format module (self-test first; the implementation follows in the next commit)."""
from __future__ import annotations

import contextlib
import io
import random
import re
import sys

NEEDS = ("callers", "route", "enclosing", "resolve", "fields_read", "uses", "hand_read", "full_build")
KINDS = ("machine_fact", "reading", "interpretation", "correction", "not_read", "argument")


# ---------------------------------------------------------------- the module (stub)
def parse_note(text):
    raise NotImplementedError


def format_comment(tag, data):
    raise NotImplementedError


def render_block(data):
    raise NotImplementedError


def render_header(data):
    raise NotImplementedError


def strip_anchor_lines(text):
    raise NotImplementedError


def block_id_ok(note_id, block_id):
    raise NotImplementedError


def problems(block, note_id=None):
    raise NotImplementedError


def header_problems(data):
    raise NotImplementedError


def target_at(text, line):
    raise NotImplementedError


def next_block_id(note_id, used_ids):
    raise NotImplementedError


def insert_after_line(text, line, comment_line):
    raise NotImplementedError


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


N = '<!-- rh-note {"id":"15"} -->'


def B(i, extra=""):
    return '<!-- rh-block {"id":"15.b%02d"%s} -->' % (i, extra)


def X(kind, first, last):
    return {"type": kind, "first_line": first, "last_line": last, "insert_after": last}


def T(first, last, ncols, nrows):
    return {"type": "table", "ncols": ncols, "nrows": nrows, "start_line": first,
            "first_line": first, "last_line": last, "insert_after": last}


# ---- A1 recognised lines
@case("A1a", "a valid rh-note line is one header, no problem")
def _():
    h, b, m = parse_note(N + "\n")
    eq((len(h), len(b), len(m)), (1, 0, 0), "counts")
    eq((h[0].line, h[0].data, h[0].canonical), (1, {"id": "15"}, True), "item")


@case("A1b", "a valid rh-block line is one block, no problem; an indented line is recognised but not canonical")
def _():
    h, b, m = parse_note("Text\n" + B(1) + "\n")
    eq((len(h), len(b), len(m)), (0, 1, 0), "counts")
    eq((b[0].line, b[0].data, b[0].canonical), (2, {"id": "15.b01"}, True), "item")
    h, b, m = parse_note("Text\n  " + B(1) + "  \n")
    eq((len(b), len(m), b[0].canonical), (1, 0, False), "indented")


@case("A1c", "every malformed rh- comment is a MALFORMED problem on its line and yields no item")
def _():
    bad = {
        "other tag": '<!-- rh-foo {"a":1} -->',
        "array": "<!-- rh-block [] -->",
        "string": '<!-- rh-block "x" -->',
        "number": "<!-- rh-block 5 -->",
        "not json": "<!-- rh-block {id:1} -->",
        "no close": '<!-- rh-block {"id":"1"} ',
        "close glued": '<!-- rh-block {"id":"1"}-->',
        "bare": "<!-- rh-note -->",
        "tag glued": '<!-- rh-block{"id":"1"} -->',
        "second comment": '<!-- rh-block {"id":"1"} --> <!-- rh-block {"id":"2"} -->',
        "second glued": '<!-- rh-block {"id":"1"} --><!-- rh-block {"id":"2"} -->',
        "text before": 'see <!-- rh-block {"id":"1"} -->',
        "text after": '<!-- rh-block {"id":"1"} --> tail',
    }
    for name, line in bad.items():
        h, b, m = parse_note("x\n" + line + "\ny\n")
        eq([(p.code, p.line) for p in m], [("MALFORMED", 2)], name)
        eq((len(h), len(b)), (0, 0), name + " items")
        ok("line 2" in m[0].message.lower(), name + " message names line")
    h, b, m = parse_note('<!-- rh-note {\n"id":"1"\n} -->\n')
    eq([(p.code, p.line) for p in m], [("MALFORMED", 1)], "spread over lines")
    eq((len(h), len(b)), (0, 0), "spread items")


@case("A1d", "a comment that is not rh- is ignored; a deep or very long line never raises")
def _():
    eq(parse_note("<!-- a note -->\n<!-- rhino -->\n"), ([], [], []), "plain comments")
    deep = "<!-- rh-block " + "[" * 100000 + "]" * 100000 + " -->\n"
    h, b, m = parse_note(deep)
    eq([(p.code, p.line) for p in m], [("MALFORMED", 1)], "deep")
    long = '<!-- rh-block {"id":"' + "x" * 1000000 + '"} -->\n'
    h, b, m = parse_note(long)
    eq((len(b), len(m)), (1, 0), "long line")


@case("A1e", "Problem fields have the named types")
def _():
    h, b, m = parse_note(N + "\n<!-- rh-foo {} -->\n")
    ok(isinstance(m[0].message, str) and isinstance(m[0].code, str) and isinstance(m[0].line, int), "problem types")
    ok(m[0].code.isupper(), "code upper-case")


# ---- A2 fenced code
@case("A2", "rh- comments inside a fence are text: not parsed, no problem; fence rules; unclosed fence")
def _():
    cases = [
        "```\n" + B(1) + "\n```\n",
        "~~~\n" + B(1) + "\n~~~\n",
        "````\n```\n" + B(1) + "\n```\n````\n",        # a shorter fence does not close a longer one
        "~~~\n```\n" + B(1) + "\n```\n~~~\n",          # the other character does not close
        "```lean\n<!-- rh-foo {} -->\n```\n",           # a malformed comment inside is not a problem either
        "```\n" + B(1) + "\n`````\n",                   # a longer closer closes
    ]
    for t in cases:
        eq(parse_note(t), ([], [], []), repr(t))
    h, b, m = parse_note("```\n" + B(1) + "\n```\n" + B(2) + "\n")
    eq([x.line for x in b], [4], "parsed again after the fence closes")
    h, b, m = parse_note("intro\n```lean\n" + B(1) + "\nmore\n")
    eq([(p.code, p.line) for p in m], [("UNCLOSED-FENCE", 2)], "unclosed")
    eq(len(b), 0, "unclosed: inside is text")
    h, b, m = parse_note("a ```not a fence``` here\n" + B(1) + "\n")
    eq((len(b), len(m)), (1, 0), "inline backticks are not a fence")


# ---- A3 canonical form
@case("A3a", "format_comment literals")
def _():
    eq(format_comment("rh-block", {"kind": "reading", "id": "15.b03"}), '<!-- rh-block {"id":"15.b03","kind":"reading"} -->', "sorted")
    eq(format_comment("rh-note", {"a": "<&>"}), '<!-- rh-note {"a":"\\u003c\\u0026\\u003e"} -->', "escapes")
    eq(format_comment("rh-note", {"t": "é→"}), '<!-- rh-note {"t":"é→"} -->', "non-ascii raw")
    eq(format_comment("rh-note", {"a": "x --> y"}), '<!-- rh-note {"a":"x --\\u003e y"} -->', "arrow")
    eq(format_comment("rh-note", {"b": True, "n": None, "l": [1, 2], "d": {"z": 0}}),
       '<!-- rh-note {"b":true,"d":{"z":0},"l":[1,2],"n":null} -->', "types")
    eq(format_comment("rh-note", {"a": "l1\nl2"}), '<!-- rh-note {"a":"l1\\nl2"} -->', "newline")


@case("A3b", "a recognised line that is not canonical is returned with canonical False")
def _():
    for line in ['<!-- rh-block {"kind":"reading","id":"15.b01"} -->',   # key order
                 '<!-- rh-block {"id": "15.b01"} -->',                  # spaces
                 '<!-- rh-block  {"id":"15.b01"} -->',                  # double space
                 '<!-- rh-block {"id":"15.b01"} -->  ',                 # trailing space
                 '<!-- rh-block {"id":"15.b01","t":"a < b"} -->',       # unescaped <
                 '<!-- rh-block {"id":"15.b01","t":"x --> y"} -->']:    # arrow in a string
        h, b, m = parse_note(line + "\n")
        eq((len(b), len(m)), (1, 0), line)
        eq(b[0].canonical, False, line)
    h, b, m = parse_note('<!-- rh-block {"id":"15.b01"} -->\r\n')
    eq((b[0].canonical, len(m)), (True, 0), "CRLF line is canonical")


# ---- A4 round trip
@case("A4", "format then parse returns the same data, canonical, no problem (hand cases and seeded random)")
def _():
    hand = [{}, {"id": "15.b01"}, {"t": "a<b>c&d"}, {"t": 'q"uo\\te'}, {"t": "x --> y <!-- z -->"},
            {"t": "l1\nl2\r\nl3\rl4"}, {"t": "é→\U0001f600 \x0b\x0c\x85\x00\x7f"},
            {"b": True, "n": None, "i": -12, "big": 10 ** 30, "l": [1, [2, {"k": []}]], "d": {"z": {}}},
            {"<": 1, "&": 2, "-->": 3}]
    rng = random.Random(20261123)
    alpha = ["<", ">", "&", '"', "\\", "é", "→", "\n", "\r", " ", "-->", "\x00", "\t", " ", "a", "0",
             "\U0001f600", "<!--"]

    def s():
        return "".join(rng.choice(alpha) for _ in range(rng.randint(0, 8)))

    def val(d):
        k = rng.randint(0, 6 if d < 3 else 3)
        if k == 0:
            return s()
        if k == 1:
            return rng.randint(-10 ** 12, 10 ** 12)
        if k == 2:
            return rng.choice([True, False])
        if k == 3:
            return None
        if k == 4:
            return [val(d + 1) for _ in range(rng.randint(0, 3))]
        return {s(): val(d + 1) for _ in range(rng.randint(0, 3))}

    rand = [{s(): val(0) for _ in range(rng.randint(0, 4))} for _ in range(300)]
    for d in hand + rand:
        for tag in ("rh-note", "rh-block"):
            h, b, m = parse_note(format_comment(tag, d) + "\n")
            items = h if tag == "rh-note" else b
            eq((len(items), len(m), len(h) + len(b)), (1, 0, 1), repr(d))
            eq(items[0].data, d, repr(d))
            eq(items[0].canonical, True, repr(d))
    h, b, m = parse_note(format_comment("rh-block", {"b": True}) + "\n")
    ok(b[0].data["b"] is True, "bool stays a bool")


# ---- A5 placement and B3 spans
@case("A5a", "paragraph, none, blank lines, header comment")
def _():
    eq(parse_note("Intro line\nsecond line\n" + B(1) + "\n")[1][0].target, X("paragraph", 1, 2), "paragraph")
    eq(parse_note("Para\n\n\n" + B(1) + "\n")[1][0].target, X("paragraph", 1, 1), "blank lines between")
    eq(parse_note(B(1) + "\n")[1][0].target, {"type": "none"}, "start of file")
    eq(parse_note("\n\n" + B(1) + "\n")[1][0].target, {"type": "none"}, "only blanks above")
    eq(parse_note(N + "\n" + B(1) + "\n")[1][0].target, {"type": "none"}, "only the header above")
    h, b, m = parse_note("P\n" + B(1) + "\n" + B(2) + "\n")
    eq([x.target for x in b], [X("paragraph", 1, 1)] * 2, "anchors after anchors")
    eq(parse_note("Intro\n" + B(1) + "\nmore\n" + B(2) + "\n")[1][1].target, X("paragraph", 3, 3), "an anchor ends a paragraph run")
    eq(parse_note(N + "\n")[0][0].target, None, "headers carry no target")


@case("A5b", "fenced blocks: lean, other, tilde")
def _():
    eq(parse_note("Text\n\n```lean\ndef x := 1\n```\n" + B(1) + "\n")[1][0].target, X("lean", 3, 5), "lean")
    eq(parse_note("```lean4\nx\n```\n" + B(1) + "\n")[1][0].target, X("lean", 1, 3), "lean4")
    eq(parse_note("~~~lean\nx\n~~~\n" + B(1) + "\n")[1][0].target, X("lean", 1, 3), "tilde lean")
    eq(parse_note("```text\nx\n```\n" + B(1) + "\n")[1][0].target, X("other", 1, 3), "other fence")
    eq(parse_note("```\nx\n```\n" + B(1) + "\n")[1][0].target, X("other", 1, 3), "no info")
    eq(parse_note("```lean\nx\n\ny\n```\n" + B(1) + "\n")[1][0].target, X("lean", 1, 5), "blank inside")


@case("A5c", "other: headings and list items; a pipe run without a separator is a paragraph")
def _():
    eq(parse_note("## H\n" + B(1) + "\n")[1][0].target, X("other", 1, 1), "heading")
    eq(parse_note("- item\n" + B(1) + "\n")[1][0].target, X("other", 1, 1), "list")
    eq(parse_note("| a | b |\n| 1 | 2 |\n" + B(1) + "\n")[1][0].target, X("paragraph", 1, 2), "pipes, no separator")


@case("A5d", "tables: size, start line, span, both anchors, alignment row, header only, escaped pipe")
def _():
    t = "# Title\n\n| a | b | c |\n|---|---|---|\n| 1 | 2 | 3 |\n| 4 | 5 | 6 |\n" + B(1, ',"row":1') + "\n" + B(2, ',"row":2') + "\n"
    h, b, m = parse_note(t)
    eq([x.target for x in b], [T(3, 6, 3, 2)] * 2, "table")
    eq(len(m), 0, "no problem")
    eq(parse_note("|a|b|\n|:--|--:|\n|1|2|\n" + B(1) + "\n")[1][0].target, T(1, 3, 2, 1), "alignment")
    eq(parse_note("| a |\n|---|\n" + B(1) + "\n")[1][0].target, T(1, 2, 1, 0), "header only")
    eq(parse_note("| a \\| b | c |\n|---|---|\n| 1 | 2 |\n" + B(1) + "\n")[1][0].target, T(1, 3, 2, 1), "escaped pipe")
    eq(parse_note("| a | b |\n|---|---|\n| 1 | 2 |\n\ntext\n" + B(1) + "\n")[1][0].target, X("paragraph", 5, 5), "table then prose")


# ---- A6 anchors inside tables
@case("A6", "a comment between two table rows is INSIDE-TABLE naming the line, and is still returned")
def _():
    t = "| a | b |\n|---|---|\n| 1 | 2 |\n" + B(1, ',"row":1') + "\n| 3 | 4 |\n" + B(2, ',"row":2') + "\n"
    h, b, m = parse_note(t)
    eq([(p.code, p.line) for p in m], [("INSIDE-TABLE", 4)], "problem")
    ok("line 4" in m[0].message.lower(), "names the line")
    eq([x.line for x in b], [4, 6], "still returned")
    eq((b[0].target["type"], b[0].target["insert_after"], b[1].target["insert_after"]), ("table", 5, 5), "insert after the table's last line")
    h, b, m = parse_note("| a |\n|---|\n| 1 |\n" + N + "\n| 2 |\n")
    eq(([(p.code, p.line) for p in m], len(h)), ([("INSIDE-TABLE", 4)], 1), "header comment inside a table")
    h, b, m = parse_note("| a |\n|---|\n| 1 |\n" + B(1) + "\n" + B(2) + "\n| 2 |\n")
    eq([(p.code, p.line) for p in m], [("INSIDE-TABLE", 4), ("INSIDE-TABLE", 5)], "two in a row")
    for t in ["| a |\n|---|\n| 1 |\n" + B(1) + "\n", "| a |\n|---|\n| 1 |\n" + B(1) + "\n\n| z |\n",
              "| a |\n|---|\n| 1 |\n" + B(1) + "\ntext\n", "text\n" + B(1) + "\n| a |\n|---|\n"]:
        eq(parse_note(t)[2], [], repr(t))


# ---- A7 header position
@case("A7", "every rh-note is a header with its line and before_first_h2")
def _():
    h, b, m = parse_note(N + "\n## A\n" + N + "\n")
    eq([(x.line, x.before_first_h2) for x in h], [(1, True), (3, False)], "two headers")
    eq([x.before_first_h2 for x in parse_note("# T\n" + N + "\n")[0]], [True], "no h2 at all")
    eq([x.before_first_h2 for x in parse_note("```\n## A\n```\n" + N + "\n")[0]], [True], "h2 in a fence does not count")
    eq([x.before_first_h2 for x in parse_note("### A\n" + N + "\n")[0]], [True], "### is not ##")
    eq([x.before_first_h2 for x in parse_note("##A\n" + N + "\n")[0]], [True], "## needs a space")
    eq([x.before_first_h2 for x in parse_note("## A\n" + N + "\n")[0]], [False], "after")
    eq(parse_note(B(1) + "\n")[1][0].before_first_h2, None, "blocks carry none")


# ---- A8 strip
@case("A8a", "strip is the exact inverse of inserting anchor lines (LF, CRLF, lone CR, no final newline, empty)")
def _():
    a = B(1)
    eq(strip_anchor_lines("x\n" + a + "\ny\n"), "x\ny\n", "LF")
    eq(strip_anchor_lines("x\r\n" + a + "\r\ny\r\n"), "x\r\ny\r\n", "CRLF")
    eq(strip_anchor_lines("x\r" + a + "\ry\r"), "x\ry\r", "lone CR")
    eq(strip_anchor_lines("x\n" + a + "\ny"), "x\ny", "no final newline, anchor before last line")
    eq(strip_anchor_lines(a + "\n"), "", "only an anchor")
    eq(strip_anchor_lines(""), "", "empty")
    eq(strip_anchor_lines(N + "\n" + a + "\n" + a + "\n"), "", "header, blocks and a duplicate")
    eq(strip_anchor_lines("té\x00\t \n" + a + "\n\n\nz"), "té\x00\t \n\n\nz", "other bytes kept")
    eq(strip_anchor_lines("x\n  " + a + "  \ny\n"), "x\ny\n", "indented anchor line is removed whole")


@case("A8b", "strip: a final anchor line without a line ending takes the line ending before it")
def _():
    eq(strip_anchor_lines("x\n" + B(1)), "x", "LF")
    eq(strip_anchor_lines("x\r\ny\r\n" + B(1)), "x\r\ny", "CRLF")
    eq(strip_anchor_lines("x\n" + B(1) + "\n" + B(2)), "x", "two anchors")
    eq(strip_anchor_lines(B(1)), "", "alone")
    eq(strip_anchor_lines("x\n" + B(1) + "\n"), "x\n", "a terminated final anchor leaves the ending")


@case("A8c", "strip leaves fenced anchor lines and malformed rh- lines alone")
def _():
    t = "```\n" + B(1) + "\n```\n"
    eq(strip_anchor_lines(t), t, "fenced")
    t = "~~~\n" + N + "\n~~~\ntext\n"
    eq(strip_anchor_lines(t), t, "tilde fenced")
    t = "x\n<!-- rh-foo {} -->\ny <!-- rh-block {} -->\n"
    eq(strip_anchor_lines(t), t, "malformed lines stay")
    eq(strip_anchor_lines("```\n" + B(1) + "\n```\n" + B(2) + "\nz\n"), "```\n" + B(1) + "\n```\nz\n", "after the fence")


# ---- A9 never raises
@case("A9", "300 seeded random strings: nothing raises, types right, line numbers in range")
def _():
    rng = random.Random(9)
    chars = list('<!-- rh-note block {}[]"\\ \n\r|`~#') + ["\x00", "é"]
    snippets = [N, B(1), B(2, ',"row":1'), '<!-- rh-block {"id":"1.b01"} -->', "```lean", "```", "~~~", "````",
                "## H", "| a | b |", "|---|---|", "<!-- rh-", " -->", "\r\n", "<!-- rh-foo {} -->", "[" * 50]
    for _i in range(300):
        pieces = [rng.choice(chars) if rng.random() < 0.6 else rng.choice(snippets) for _ in range(rng.randint(0, 60))]
        t = "".join(pieces)
        nlines = len(re.split(r"\r\n|\n|\r", t))
        h, b, m = parse_note(t)
        ok(isinstance(h, list) and isinstance(b, list) and isinstance(m, list), "types")
        for x in h + b:
            ok(isinstance(x.data, dict) and isinstance(x.canonical, bool) and 1 <= x.line <= nlines, "item " + repr(t))
            ok(0 <= x.offset < x.end <= len(t), "offsets " + repr(t))
        for p in m:
            ok(isinstance(p.code, str) and isinstance(p.message, str) and 1 <= p.line <= nlines, "problem " + repr(t))
        for x in b:
            ok(isinstance(x.target, dict) and "type" in x.target, "target " + repr(t))
        s = strip_anchor_lines(t)
        ok(isinstance(s, str) and len(s) <= len(t), "strip " + repr(t))
        for ln in (0, 1, nlines, nlines + 3):
            r = target_at(t, ln)
            ok(r is None or isinstance(r, dict), "target_at " + repr(t))


# ---- A10 duplicates
@case("A10", "the same content on two lines is two Items")
def _():
    h, b, m = parse_note("x\n" + B(1) + "\n" + B(1) + "\n")
    eq([x.line for x in b], [2, 3], "two blocks")
    eq(b[0].data, b[1].data, "same data")
    h, b, m = parse_note(N + "\n" + N + "\n")
    eq([x.line for x in h], [1, 2], "two headers")


# ---- A11 exit codes (the runner is exercised with injected case lists)
@case("A11", "selftest exit codes: 0 all pass, 1 any fail, 2 usage, 3 no case ran")
def _():
    quiet = lambda s: None  # noqa: E731
    eq(_run_cases([], quiet), 3, "no cases")
    eq(_run_cases([("p", "d", lambda: None)], quiet), 0, "pass")
    eq(_run_cases([("p", "d", lambda: None), ("f", "d", lambda: eq(1, 2))], quiet), 1, "one fails")
    eq(_run_cases([("c", "d", lambda: 1 / 0)], quiet), 1, "a crash is a failure")
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        eq(main([]), 2, "no args")
        eq(main(["--bogus"]), 2, "unknown")
        eq(main(["--selftest", "x"]), 2, "extra")
    ok("usage" in err.getvalue(), "usage text on stderr")


# ---- B1 writers
@case("B1", "render_block and render_header give the canonical line; render(parse(line).data) == line")
def _():
    eq(render_block({"kind": "reading", "id": "15.b03"}), '<!-- rh-block {"id":"15.b03","kind":"reading"} -->', "block")
    eq(render_header({"id": "15"}), '<!-- rh-note {"id":"15"} -->', "header")
    lines = ['<!-- rh-block {"id":"15.b01","t":"x \\u003e y \\u0026 \\u003c"} -->',
             '<!-- rh-block {"id":"15.b01","t":"x --\\u003e y","u":"é→"} -->',
             '<!-- rh-block {"id":"15.b01","t":"q\\"uo\\\\te\\nl2"} -->']
    for ln in lines:
        h, b, m = parse_note(ln + "\n")
        eq((len(b), len(m), b[0].canonical), (1, 0, True), ln)
        eq(render_block(b[0].data), ln, ln)
    h, b, m = parse_note('<!-- rh-note {"id":"15","t":"a<b"} -->\n')
    eq(render_header(h[0].data), '<!-- rh-note {"id":"15","t":"a\\u003cb"} -->', "header escape")


# ---- B2 validators
def vb(**kw):
    d = {"id": "15.b01", "kind": "reading"}
    d.update(kw)
    return d


def MF(**kw):
    d = {"id": "15.b01", "kind": "machine_fact", "check": "text", "tool": "decl_table.py", "tool_version": "abc1234", "options": ""}
    d.update(kw)
    return d


DECL = {"module": "A.B", "name": "n"}


def one(block, field, note_id=None, word=None):
    ps = problems(block, note_id)
    eq(len(ps), 1, f"{field}: {ps!r}")
    ok(ps[0].startswith(field), f"problem starts with {field!r}: {ps[0]!r}")
    if word:
        ok(word in ps[0], f"mentions {word!r}: {ps[0]!r}")


@case("B2a", "a valid block of each kind has no problems (defs_opened and conventions_checked are not required)")
def _():
    valid = [
        MF(), MF(check="index"), MF(check="proofterm", complete=True), MF(options="--x"),
        vb(), vb(kind="interpretation"), vb(kind="correction"),
        vb(decls=[DECL], file="F.lean", lines=[1, 2], reader="R", date="2026-11-23"),
        vb(kind="not_read", needs="callers"),
        vb(kind="argument", reader="R", date="2026-11-23", decls=[DECL]),
        vb(defs_opened=[{"module": "M", "name": "n", "lines": [1, 2]}], conventions_checked=["a", "d"]),
        vb(defs_opened=[], conventions_checked=[]),
        vb(row=1, col=2),
    ]
    for v in valid:
        eq(problems(v), [], repr(v))
        eq(problems(v, "15"), [], repr(v) + " with note")
    for n in NEEDS:
        eq(problems(vb(kind="not_read", needs=n)), [], n)
    eq(problems(vb(id="15.b123")), [], "three digits")


@case("B2b", "kind and id rules")
def _():
    one(vb(kind="nope"), "kind")
    one({"id": "15.b01"}, "kind")
    one(vb(id="15.b3"), "id")
    one(vb(id="15.bxx"), "id")
    one(vb(id="15"), "id")
    one({"kind": "reading"}, "id")
    one(vb(id=15), "id")
    one(vb(id="15.b01"), "id", note_id="16")
    one(vb(id="115.b01"), "id", note_id="15")
    eq(problems(vb(id="15.b01"), "15"), [], "right note")
    ps = problems("x")
    eq(len(ps), 1, "not an object")
    ok(ps[0].startswith("block"), "starts with block")


@case("B2c", "machine_fact rules, including: complete False can only be anchored as not_read")
def _():
    base = MF()
    for f in ("tool", "tool_version", "check", "options"):
        d = dict(base)
        del d[f]
        one(d, f)
    one(MF(tool=""), "tool")
    one(MF(tool_version=""), "tool_version")
    one(MF(check="other"), "check")
    one(MF(options=None), "options")
    one(MF(options=3), "options")
    one(MF(check="proofterm"), "complete")
    one(MF(check="proofterm", complete="yes"), "complete")
    one(MF(check="proofterm", complete=False), "complete", word="not_read")
    one(MF(check="text", complete=False), "complete", word="not_read")
    eq(problems(MF(check="text", complete=True)), [], "complete true is fine for text")


@case("B2d", "not_read and argument rules")
def _():
    one(vb(kind="not_read"), "needs")
    one(vb(kind="not_read", needs="other"), "needs")
    one(vb(kind="not_read", needs=None), "needs")
    arg = dict(kind="argument", reader="R", date="2026-11-23", decls=[DECL])
    eq(problems(vb(**arg)), [], "valid argument")
    for f in ("reader", "date", "decls"):
        d = dict(arg)
        del d[f]
        one(vb(**d), f)
    one(vb(**dict(arg, decls=[])), "decls")
    one(vb(**dict(arg, reader="")), "reader")


@case("B2e", "decls, defs_opened, conventions_checked, row and col shapes")
def _():
    one(vb(decls="x"), "decls")
    one(vb(decls=["x"]), "decls[0]")
    one(vb(decls=[{"module": "A", "name": 5}]), "decls[0].name")
    one(vb(decls=[{"module": 5, "name": "n"}]), "decls[0].module")
    one(vb(decls=[{"name": "n"}]), "decls[0].module")
    one(vb(decls=[DECL, {"module": "A"}]), "decls[1].name")
    one(vb(defs_opened="x"), "defs_opened")
    one(vb(defs_opened=["x"]), "defs_opened[0]")
    one(vb(defs_opened=[{"module": "M", "name": "n"}]), "defs_opened[0].lines")
    one(vb(defs_opened=[{"module": "M", "name": "n", "lines": [1]}]), "defs_opened[0].lines")
    one(vb(defs_opened=[{"module": "M", "name": "n", "lines": [1, "2"]}]), "defs_opened[0].lines")
    one(vb(defs_opened=[{"module": "M", "name": "n", "lines": [True, 2]}]), "defs_opened[0].lines")
    one(vb(defs_opened=[{"module": "M", "lines": [1, 2]}]), "defs_opened[0].name")
    one(vb(conventions_checked="a"), "conventions_checked")
    one(vb(conventions_checked=["f"]), "conventions_checked")
    one(vb(conventions_checked=["a", 1]), "conventions_checked")
    for f in ("row", "col"):
        one(vb(**{f: 0}), f)
        one(vb(**{f: "1"}), f)
        one(vb(**{f: True}), f)
        one(vb(**{f: 1.5}), f)
        one(vb(**{f: -1}), f)


@case("B2f", "header_problems")
def _():
    good = {"id": "15", "level": 2, "group": "g", "list_title": "T", "authors": ["H"], "readers": ["K"], "release": "rh-1"}
    eq(header_problems(good), [], "valid")
    for lv in (0, 1, 2):
        eq(header_problems(dict(good, level=lv)), [], f"level {lv}")
    for f in good:
        d = dict(good)
        del d[f]
        ps = header_problems(d)
        eq(len(ps), 1, f"missing {f}: {ps!r}")
        ok(ps[0].startswith(f), f"starts with {f}: {ps[0]!r}")
    for f, v in [("level", 3), ("level", "2"), ("level", True), ("level", -1), ("list_title", ""), ("list_title", 5),
                 ("authors", "H"), ("readers", "K"), ("group", ""), ("id", ""), ("release", ""), ("release", 5)]:
        ps = header_problems(dict(good, **{f: v}))
        eq(len(ps), 1, f"{f}={v!r}: {ps!r}")
        ok(ps[0].startswith(f), f"starts with {f}: {ps[0]!r}")
    eq(len(header_problems("x")), 1, "not an object")


# ---- B3 target_at and spans
@case("B3", "target_at: table body and separator rows, lean fence, paragraph, between elements, out of range")
def _():
    t = "Intro\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n```lean\ndef x := 1\n```\n\n"
    eq(target_at(t, 1), X("paragraph", 1, 1), "paragraph")
    eq(target_at(t, 5), T(3, 5, 2, 1), "table body row")
    eq(target_at(t, 4), T(3, 5, 2, 1), "separator row")
    eq(target_at(t, 3), T(3, 5, 2, 1), "header row")
    eq(target_at(t, 8), X("lean", 7, 9), "inside the lean fence")
    eq(target_at(t, 7), X("lean", 7, 9), "fence opener")
    eq(target_at(t, 2), None, "blank between")
    eq(target_at(t, 6), None, "blank between table and fence")
    eq(target_at(t, 0), None, "line 0")
    eq(target_at(t, 99), None, "past the end")
    eq(target_at("| a |\n|---|\n| 1 |\n" + B(1) + "\n| 2 |\n", 4), T(1, 5, 1, 2), "an anchor line inside a table is held by the table")
    eq(target_at("P\n" + B(1) + "\n", 2), None, "an anchor line after a paragraph is between elements")


# ---- B4 ids
@case("B4", "next_block_id: smallest number above the largest used for that note; holes are never reused")
def _():
    eq(next_block_id("15", []), "15.b01", "none used")
    eq(next_block_id("15", ["15.b01", "15.b02", "15.b05"]), "15.b06", "holes")
    eq(next_block_id("15", ["15.b03"]), "15.b04", "one")
    eq(next_block_id("15", ["15.b09"]), "15.b10", "ten")
    eq(next_block_id("15", ["15.b99"]), "15.b100", "three digits")
    eq(next_block_id("15", ["15.b100"]), "15.b101", "three digits used")
    eq(next_block_id("15", ["16.b09", "115.b07", "15.b2x", "15.b", "15.b٣"]), "15.b01", "other notes and odd ids ignored")
    eq(next_block_id("1", ["11.b05"]), "1.b01", "prefix of another note")
    eq(next_block_id("a.b", ["a.b.b04", "aXb.b09"]), "a.b.b05", "note id is not a pattern")
    eq(next_block_id("15", iter(["15.b02"])), "15.b03", "any iterable")


# ---- B5 offsets and insertion
@case("B5a", "Item.offset and Item.end are character offsets, the line ending kept")
def _():
    t = "ab\r\n" + N + "\nx"
    h, b, m = parse_note(t)
    eq((h[0].offset, h[0].end), (4, 4 + len(N) + 1), "LF after CRLF line")
    eq(t[h[0].offset:h[0].end], N + "\n", "slice")
    t = "x\n" + B(1) + "\r\n" + B(2)
    h, b, m = parse_note(t)
    eq(t[b[0].offset:b[0].end], B(1) + "\r\n", "CRLF kept")
    eq((b[1].offset, b[1].end), (len("x\n" + B(1) + "\r\n"), len(t)), "last line without ending")
    h, b, m = parse_note("a\r" + B(1) + "\r")
    eq((b[0].offset, b[0].end), (2, 2 + len(B(1)) + 1), "lone CR")


@case("B5b", "insert_after_line: that file's line ending; the final newline rule, literal")
def _():
    C = B(1)
    eq(insert_after_line("a\nb\n", 1, C), "a\n" + C + "\nb\n", "LF middle")
    eq(insert_after_line("a\nb\n", 2, C), "a\nb\n" + C + "\n", "LF last, terminated: comment is terminated too")
    eq(insert_after_line("a\r\nb\r\n", 1, C), "a\r\n" + C + "\r\nb\r\n", "CRLF middle")
    eq(insert_after_line("a\r\nb\r\n", 2, C), "a\r\nb\r\n" + C + "\r\n", "CRLF last")
    eq(insert_after_line("a\nb", 1, C), "a\n" + C + "\nb", "no final newline, middle")
    eq(insert_after_line("a\nb", 2, C), "a\nb\n" + C, "no final newline, last: one newline added before, none after")
    eq(insert_after_line("a", 1, C), "a\n" + C, "single unterminated line")
    eq(insert_after_line("a\r\nb", 2, C), "a\r\nb\r\n" + C, "CRLF file, last unterminated: CRLF before")
    eq(insert_after_line("a\rb\r", 1, C), "a\r" + C + "\nb\r", "lone CR line gets LF")


@case("B5c", "strip(insert(t)) == t for every line of LF, CRLF, no-final-newline, single-line and fenced texts")
def _():
    texts = ["a\nb\nc\n", "a\r\nb\r\nc\r\n", "a\nb\nc", "a\r\nb\r\nc", "a", "a\n", "a\r\n", "| h |\n|---|\n| 1 |\n",
             "x\n```lean\ny\n```\nz", "a\rb\rc", "\n\n", "té\x00\n"]
    C = B(1)
    for t in texts:
        n = len(re.split(r"\r\n|\n|\r", t))
        if t.endswith(("\n", "\r")):
            n -= 1
        for ln in range(1, n + 1):
            r = insert_after_line(t, ln, C)
            eq(strip_anchor_lines(r), t, f"{t!r} after {ln}")
            ok(C in r, "comment present")
    t = "a\nb"
    r = insert_after_line(insert_after_line(t, 2, B(1)), 3, B(2))
    eq((r, strip_anchor_lines(r)), ("a\nb\n" + B(1) + "\n" + B(2), t), "two insertions at the end")


@case("B5d", "insert_after_line refuses a line out of range and a comment with a line break")
def _():
    for t, ln in [("a\nb\n", 0), ("a\nb\n", 3), ("a\nb", 3), ("", 1), ("a", -1)]:
        try:
            insert_after_line(t, ln, B(1))
        except ValueError:
            continue
        raise AssertionError(f"no ValueError for {t!r}, {ln}")
    for c in ("a\nb", "a\rb", B(1) + "\n"):
        try:
            insert_after_line("a\n", 1, c)
        except ValueError:
            continue
        raise AssertionError(f"no ValueError for comment {c!r}")


@case("CONST", "the closed lists, in order")
def _():
    eq(NEEDS, ("callers", "route", "enclosing", "resolve", "fields_read", "uses", "hand_read", "full_build"), "NEEDS")
    eq(KINDS, ("machine_fact", "reading", "interpretation", "correction", "not_read", "argument"), "KINDS")


@case("IDOK", "block_id_ok: note id, '.b', two or more ASCII digits, nothing else")
def _():
    for n, b in [("15", "15.b01"), ("15", "15.b99"), ("15", "15.b100"), ("landau-step", "landau-step.b07")]:
        eq(block_id_ok(n, b), True, b)
    for n, b in [("15", "15.b1"), ("15", "15.b"), ("15", "16.b01"), ("15", "15.b01x"), ("15", "15.b0a"), ("15", "x15.b01"),
                 ("15", "15.B01"), ("15", "15.b01\n"), ("15", ""), ("15", "15b01"), ("15", "15.b٣٣"),
                 ("a.b", "aXb.b01"), ("15", "115.b01")]:
        eq(block_id_ok(n, b), False, repr(b))
    eq(block_id_ok("a.b", "a.b.b01"), True, "dot in the note id is literal")


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
    print("# cases range over: line recognition and malformed lines (A1), fences (A2), canonical form and the round trip")
    print("# (A3, A4), placement, spans and tables (A5, A6, B3), header position (A7), strip and insert (A8, B5), 300")
    print("# seeded random strings that must never raise (A9), duplicates (A10), exit codes (A11), writers (B1), format")
    print("# validators (B2), id numbering (B4), the closed lists and block_id_ok. Expected values are literals.")
    return _run_cases(_CASES, print)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--selftest"]:
        return selftest()
    print("usage: rh_anchor.py --selftest   (a library: import it, no other command line)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
