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
     A listing (EXTENT-WARNING, FRAME-NOTE, NEW-NOTE, ADDITION, CLAIM-LIBRARY-WORD) never changes the exit code. Cases X2a X2b X2c EXIT4.
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
  O4 Every group has at least one root; a group with a non-null claim has exactly one; a null claim may have any
     number from one up. Case O4.
  O5 A claim has exactly the keys text, reader, date, defs_opened, conventions_checked (all required; text, reader,
     date non-empty strings; defs_opened a list of {module, name, lines:[a,b]}, may be empty; conventions_checked a
     list of letters a to e) and the optional `conditions` (non-empty strings) and `mathlib_read` (strings). Any
     other claim key is UNKNOWN-KEY. Cases O5a O5b O5c.
  O6 Every `roots` and `defs_opened` entry resolves to exactly one row of decls.tsv: none is UNRESOLVED, two or
     more AMBIGUOUS with the candidates' (first_line, last_line). Case O6.
 Notes
  M1 Exactly one rh-note header per note, before the first `## ` heading: none NO-HEADER, two or more SECOND-HEADER
     naming the lines, one after the first `## ` heading HEADER-AFTER-H2. Case M1.
  M2 header_problems() findings; the group exists in the outline; the title rules (TITLE-CODE-FIRST, TITLE-PARENTHETICAL
     as errors, TITLE-NOTE as a listing). Cases M2a TITLE1 TITLE2 TITLE3 TITLE4.
  M3 Every block: rh_anchor.problems(block, header id); block ids unique across all notes, DUPLICATE-ID naming both
     places; two notes whose headers carry the same id are NOTE-ID-DUPLICATE (one finding, on the first, naming every
     file that uses it). Cases M3a M3b ID1 to ID4.
  M4 Every `decls` entry resolves to exactly one row (UNRESOLVED, AMBIGUOUS). Case M4.
  M5 `file` is listed in the note's file table (always); with --src it is also a file under SRC_ROOT and `lines` are
     inside it.
     Lines outside the text extent of every row the block's decls resolve to are an EXTENT-WARNING listing. Without
     --src the existence and line-count halves are skipped and the run says so. Cases M5a to M5f.
  M6 Every MALFORMED, UNCLOSED-FENCE and INSIDE-TABLE problem of rh_anchor.parse_note is an ERROR naming the line; a
     line that is not canonical is NONCANONICAL and prints the canonical form. Cases M6a M6b.
  M7 A block with `row` or `col` must follow a table (NOT-A-TABLE), `row` <= body rows, `col` <= columns. Case M7.
  F12 With --strings, an argument or interpretation block whose text opens with the frame of another kind is a
     FRAME-NOTE listing; without it one line says the check was skipped. Cases F12a F12b.
  BYTES With --base REV: the note at REV and the current note, each without its anchor lines (header and blocks), are equal
     byte for byte after the strip rule of rh_anchor (BYTE-DIFF names the first differing line as a line of the current file on disk and as an index of the stripped texts; a base that is not UTF-8 is a
     BYTE-DIFF with no line); a note not at REV is NEW-NOTE. Without --base the run says it did not run.
     Cases B1a to B1e, Y1 to Y6, Z1, Z2a to Z2d, BL1 to BL6.
  ADD A pure insertion of dated text is an ADDITION, not a BYTE-DIFF (F27). With the same two stripped texts: the base is
     a subsequence of the current when each base line (with its line ending) matches, in order and GREEDILY from the left (the
     earliest equal line after the previous match), a current line; the unmatched current lines are the inserted runs (maximal
     gaps, one after the last base line too). A base that is not a subsequence (a line removed or altered) is a BYTE-DIFF as
     before. Each run, after its LEADING blank lines, must begin with a heading (1 to 6 `#`, a space, text) whose text holds a
     real calendar date YYYY-MM-DD (the first real one is the heading's date); that date is not later than --today (default
     the UTC date of the clock) and not earlier than the date in the header's `release` when it is `rh-YYYY-MM-DD` (a release
     with no such date gives no lower bound). A run inside a fence of the published text (opened by base lines before it and
     closed after, or never closed) fails. One failing run makes the whole note a BYTE-DIFF at the run's first line (a date
     outside the window adds its date and the window to the message). Each legal run is an ADDITION listing
     `ADDITION path:first_line N lines, heading TEXT` (first_line on disk, N in the text without anchors), a warning, never
     an error; the byte-check line ends `additions A` (runs). Cases ADD1 to ADD22.
 Added after review (cases REC1 M5d M5e M5f DEFS1 ORPH1 F12c GIT1 B1e and the changed O4):
  R1 JSON nested too deep is unreadable input (exit 2), like any other. R2 A block's `defs_opened` resolves like its
  `decls`. R3 A block whose target is none or other (a heading, a list item, a quote, a non-lean fence) is ORPHAN-BLOCK.
  R4 Every group has at least one root; a null claim with no root, once accepted, is now a ROOT-COUNT error.
  R5 A strings file with no phrase at all is announced. R6 Without the git program a normal run is refused (exit 4).
 List items (cases ITEM1 ITEM2 CONST2 LSH1; rh_anchor L1a to L5):
  I1 A block whose target is a list must carry `item` (ITEM-REQUIRED); `item` above the number of top-level items is
  ITEM-OUT-OF-RANGE; `item` that is not an integer of 1 or more is ITEM-BAD-VALUE; `item` on a target that is not a list is
  NOT-A-LIST. Nested items are not numbered. A heading, quote, HTML line or non-lean fence is still ORPHAN-BLOCK.
  I2 A list target whose shape has every key of an entry of REFUSED_LIST_SHAPES (empty by default) is LIST-SHAPE-REFUSED.
 Summary lines (cases N5a N5b N5c): `outline: G groups, C claimed, Z null, R roots resolved, D defs_opened resolved, P
 premise links` always, counted over the whole outline; `strings: F frame phrases loaded for K kinds` and `byte check:
 N notes equal to REV, M new` when those ran. Header group (cases HROOT1 to HROOT3): `root` only at level 0.
 Claim basis (cases BAS1 to BAS5): a claim may carry `basis`, exactly "read" or "census"; any other value is BAD-VALUE naming
 the group and the type of the value; REQUIRE_CLAIM_BASIS (False) makes a claim without it CLAIM-BASIS-MISSING; the line
 `claim basis: R read, C census, M without` counts the non-null claims that are objects (a claim that is not an
 object is its own BAD-VALUE and is counted in none of the three).
  Claim words (cases CLW1 to CLW8): a claim `text` or a `conditions` entry that holds, OUTSIDE single-backtick spans, a dotted token
 (identifier parts joined by a dot, each starting with a letter or `_`: Foo.bar, A.b_c.d) or a CamelCase word (a lower-case letter
 directly followed by a capital inside a word of letters, digits and `_`: getValue, HypSalt) is a `CLAIM-LIBRARY-WORD` listing
 naming the group, `claim text` or `conditions[i]`, and the token, once per token per text, in the order of the text; it never
 changes the exit code and counts in the warnings. Doubled backticks are literal text, so a token inside them is outside a span
 and is listed; a span does not cross a line break of any kind (LF, CR or both). The span is `_BACKTICK_SPAN`, which build_site.py
 uses too to render <code>, so the page and the checker cannot disagree on what is code.
 Real shape: an outline in the shape the pilot uses (depth 4, premises that name a child) passes; the same with a
 draft-only key added fails UNKNOWN-KEY. Cases REAL1 REAL2.

LIMIT. The tool checks the SHAPE of the metadata and that every name resolves to a row; it does not read a claim or a
block and cannot say that it is right. Not checked: whether a claim follows the translation rules (whether a definition
was really opened, whether a convention was really checked: the peer reader's judgement); whether `date` is a date;
whether a note's header id matches its file name or is used by another note (only block ids are compared across
notes); the SHA-256 values of the file table, and whether a quoted lean block is verbatim (check_lean_blocks.py
does that). Title rules: only the two a script can check are checked, that a list_title is not only code spans
and does not end in a parenthetical `(...)`; every other rule on titles (plain words, saying what the note is
about, length, no status in the words) needs a reader. Extra keys are UNKNOWN-KEY for the outline, a group and a
claim only; a roots or defs_opened entry with extra keys is accepted, and a JSON key repeated in the outline keeps
its last value. Notes are the files directly in NOTES_DIR that match the pattern, so docs/tools.md, which sits
beside the notes, is not a note; a finding names a note by its name in NOTES_DIR and the outline and the table by
their file names, so no finding carries a path of the host. An outline finding has no line. The header must come
before the first `## ` heading outside a fence (HEADER-AFTER-H2 otherwise); only the first header is read when
there are two. An unreadable input is exit 2 and prints nothing to stdout: a note or the strings file that is not
UTF-8, an outline or strings file that is not JSON, a decls.tsv row that is not six columns with numeric lines, a
--base that is not a commit. M5 runs only with --src, both halves of it (the file must be listed AND be a file
under SRC_ROOT with the line count in range); the file table is read by check_lean_blocks.listed_files (rows of
backticked `.lean` paths after the heading "Files this note was written from", to the end of the note). Lines are
counted as an editor shows them, a final newline not starting a line. The extent check compares the block's lines
with EVERY row its decls resolve to, whatever module the row is in and whatever the block's file is, and a block
whose lines only partly overlap a row is outside it; a block with `lines` and no `file` is not checked for extent.
The text extent is the text rule's (decl_table.py), not Lean's. FRAME-NOTE reads `frames` (kind -> list of opening
phrases) from the strings file; that key is PROVISIONAL and its shape is not final. A phrase is cut at its first `{`
or `<` (a placeholder), the match is case-blind, ignores leading `*`, `_` and `>`, ends at a word boundary, and only
the first other kind that matches is named; only a block whose target is a paragraph is read. The byte check
compares at the path the note has in the repository, so a note renamed since REV is NEW-NOTE, and BYTE-DIFF's line
number after the note name is the 1-based line in the CURRENT file as it is on disk, anchor lines included (the i-th line that is
not an anchor line of the note, the anchor lines being those rh_anchor.parse_note reports; a malformed rh- line is text and
is not one), and the message gives the index in the text without anchors too. When the current file has a line at the first
differing index (extra text) the number is that line's own number; when it has NO line there (text missing, `<no line>` on the
now side) there is no line to point at, and the number points at the first line PAST the text, "past the end": the line
after the last non-anchor line of the current file, which is an anchor line when anchors trail the text and otherwise one
past the last line of the file (a line that is not there, so do not look for it), or 1 when there is no non-anchor line
(an empty file, or one that holds only anchor lines). Trailing anchor lines do not shift either number. Both sides are
stripped, so a header or an anchor added OR removed since REV is not a text change (the checker's other rules judge the
result); a line that looks like an anchor inside a fence is text and is compared. A base that is not UTF-8 is a BYTE-DIFF
with no line, and the other notes are still compared. ADDITION (F27): the floor of the date window is the date of the header's
`release`, not the note's own, and a note whose release carries no date has no floor; the upper bound is the day of the run.
The alignment is greedy, so an inserted line that repeats a base line can leave the original unmatched as a second run (a
BYTE-DIFF unless that run is itself a dated addition); a base whose last line has no line ending cannot gain text after it
(the line differs). The fence test reads the published text only: an inserted fence marker that changes how later base lines
read as fenced is not detected. A heading with an impossible date beside a real one is read by the real one. --today is
a test hook and a value that is not a real date is a usage error (exit 2). "Byte for byte" means byte for byte AFTER the strip rule of rh_anchor: a
last anchor line with no line ending of its own also removes the line ending before it, so adding or removing such a
hand-typed last line can read as a one-line-ending difference (anchors written by the helper carry their own ending; case
Z1). An anchor-looking line is kept as text only inside a fence: an indented code block or a list item is not tracked, as in
rh_anchor's LIMIT. A malformed rh- line is kept as text, so fixing it since REV is a BYTE-DIFF. The self-test builds its repositories
with the user's own configuration switched off and needs the `git` program.
NOTE-ID-DUPLICATE compares ids as exact strings (letter case counts; no trimming, no Unicode normalisation) and only for notes
that have a header with a non-empty id; it reads each note's FIRST header only (a second header is reported as SECOND-HEADER and
its id is not compared); it is one finding on the first file in name order, which names every file, so a reader of a later file's
own findings does not see it.
Claim basis: optional while REQUIRE_CLAIM_BASIS is False. The next step of the sequence (the outline carries basis on every
claim) comes first, then that constant is set to True and a claim without basis becomes an error. The summary counts a claim
whose basis value is not read or census as without (it is also a BAD-VALUE), and counts neither null claims nor a claim that is not an object (that is its own BAD-VALUE).
List items: a nested item is not numbered; a citation in a nested item anchors to its parent item, and the precision lives in
the block's decls and lines (a future optional `subitem` could number nested items). A list whose last line is nested, a
loose list (one list, numbered across its blank lines), an ordered list and a list directly followed by a paragraph may render
differently from the source; REFUSED_LIST_SHAPES says which are refused, and it is EMPTY until the renderer control's result
is in. A citation inside a quote stays unanchored. The summary counts: premise links are the premises that name a group of
the outline (not the group itself); roots and defs_opened resolved are those with exactly one decls row; strings' kinds are
those with at least one phrase; a group id that is repeated is counted in the groups but only its first is resolved. A header
group of `root` is not looked up in the outline; a group literally named root is not supported.
CLAIM-LIBRARY-WORD is a prompt to the signer, not a proof, and its rule is exactly this: a single-backtick span is a backtick, then
one or more characters that are neither a backtick nor a line break (LF or CR), then a backtick, with no backtick directly outside
either end (`_BACKTICK_SPAN`, the span the page renders as code; doubled backticks and a pair over a line break are not spans, so a
token inside doubled backticks IS listed); outside spans, a dotted token has at least two
parts, each a letter or `_` followed by letters, digits and `_`, with no letter, digit, `_` or `.` directly before it and no letter,
digit or `_` directly after it (so a number like 3.5, a sentence-final period and `end. Next` are not listed, and `e.g.` is: it reads
as a dotted token); a CamelCase word is a run of ASCII letters, digits and `_` (outside dotted tokens) holding a lower-case letter
directly followed by a capital (so `RH`, `Riemann` and `LEAN` are not listed and `McDonald` is). ASCII letters only: a name with a
non-ASCII letter may be listed as a fragment, because the word is cut at the letter (naïveThing is listed as 'veThing', GröbnerBasis as
'bnerBasis'). The outline has no line numbers, so a finding names the file, the group and the place, no line.
Title rules in the script are heuristics. A trailing parenthetical is allowed when it holds only code spans, commas and
`and`, or only a one-letter or number argument (so a function argument like `(s)` or `(12)` passes and `(draft)` fails);
a math argument longer than that is called a status. TITLE-NOTE listings (a math symbol or `Re s` outside code; `proved`
or `proves` with no `Lean` directly before it) are heuristics too and never fail a note. Left to a human reader: plain
words, no definite reference to something defined in another note, no interpretation stated as fact (other than
`proved`), and the group-title rules (restate the root's statement, same vocabulary as the notes). The element types of
`authors` and `readers` are not checked. A block's `defs_opened` lines are not order-checked. A strings file that
holds no phrase is announced with one line and is not an error.

usage: notes_meta.py NOTES_DIR OUTLINE DECLS_TSV [--base REV] [--repo DIR] [--strings PATH] [--src SRC_ROOT]
                     [--glob PATTERN] [--today YYYY-MM-DD]
       notes_meta.py --selftest
"""
import contextlib
import datetime
import fnmatch
import importlib.util
import io
import json
import os
import re
import shutil
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


# ---------------------------------------------------------------- the tool
ERROR, LISTING = "error", "listing"
NOCODE = "CHECKED NOTHING"
TOP_KEYS = ("groups", "release")
GROUP_KEYS = ("id", "level", "parent", "order", "roots", "claim", "premises")
CLAIM_REQUIRED = ("text", "reader", "date", "defs_opened", "conventions_checked")
CLAIM_OPTIONAL = ("conditions", "mathlib_read", "basis")
CLAIM_BASIS = ("read", "census")
# While False a claim need not carry basis. The step that makes the outline carry it on every claim comes first; then this
# constant is set to True and a claim without basis is CLAIM-BASIS-MISSING.
REQUIRE_CLAIM_BASIS = False
DECL_COLS = ["module", "name", "kind", "first_line", "last_line", "basis"]
FRAME_ONLY = ("argument", "interpretation")
# Shapes of a list that a renderer shows differently from the source: a tuple of frozensets of shape keys (loose,
# last_nested, ordered, followed_by_paragraph). A block whose list target has every key of an entry true is
# LIST-SHAPE-REFUSED. Empty until the renderer control's result is in.
REFUSED_LIST_SHAPES = ()
_CODESPAN = re.compile(r"(`+)(?!`).+?(?<!`)\1(?!`)")
_LINE_SPLIT = re.compile(r"\r\n|\n|\r")
# The ONE definition of a code span, used by this checker and by build_site.py (which renders the span as <code>): a backtick, one or
# more characters that are no backtick and no line break (LF or CR), a backtick, with no backtick directly outside either end.
# Group 1 is the content.
_BACKTICK_SPAN = re.compile(r"(?<!`)`([^`\r\n]+)`(?!`)")
_DOTTED = re.compile(r"(?<![A-Za-z0-9_.])[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+(?![A-Za-z0-9_])")
_WORD = re.compile(r"[A-Za-z0-9_]+")


class _Unreadable(Exception):
    """An input that cannot be read: exit 2, the message goes to stderr, nothing to stdout."""


def _int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _str(v):
    return isinstance(v, str) and v != ""


def _f(code, path, line, msg, cls=ERROR):
    return (code, path, line, msg, cls)


def _render(f):
    code, path, line, msg, _ = f
    return f"{code} {path}:{line} {msg}" if line else f"{code} {path} {msg}"


def _read_decls(path):
    """({(module, name): [(first, last), ...]}, number of rows); every row of a repeated pair is kept."""
    try:
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise _Unreadable(f"cannot read the decls table: {e}")
    index, n = {}, 0
    for k, raw in enumerate(text.split("\n"), 1):
        raw = raw.rstrip("\r")
        if raw == "" or raw.startswith("#"):
            continue
        cells = raw.split("\t")
        if cells == DECL_COLS:
            continue
        good = len(cells) == 6 and cells[0] != "" and cells[1] != ""
        if good:
            try:
                first, last = int(cells[3]), int(cells[4])
            except ValueError:
                good = False
        if not good:
            raise _Unreadable(f"cannot read the decls table: line {k} is not a row of six columns with numeric lines")
        index.setdefault((cells[0], cells[1]), []).append((first, last))
        n += 1
    return index, n


def _resolve(index, where, path, line, module, name):
    """(finding, None) when the pair has no row or several, else (None, the one row)."""
    rows = sorted(index.get((module, name), []))
    if len(rows) == 1:
        return None, rows[0]
    if not rows:
        return _f("UNRESOLVED", path, line, f"{where} {module} {name}: no row in decls.tsv"), None
    cand = ", ".join(f"({a}, {b})" for a, b in rows)
    return _f("AMBIGUOUS", path, line, f"{where} {module} {name}: {len(rows)} rows; "
              f"candidates (first_line, last_line): {cand}"), None


def _decl_entry_ok(e):
    return isinstance(e, dict) and _str(e.get("module")) and _str(e.get("name"))


# ---- the outline
def _jtype(v):
    return ("null" if v is None else "boolean" if isinstance(v, bool) else "number" if isinstance(v, (int, float))
            else "string" if isinstance(v, str) else "list" if isinstance(v, list) else "object")


def _check_claim(claim, label, path, out):
    pre = f"{label} claim"
    if "basis" in claim:
        if not (isinstance(claim["basis"], str) and claim["basis"] in CLAIM_BASIS):
            out.append(_f("BAD-VALUE", path, None, f"{pre}: basis must be 'read' or 'census' (the value is of type {_jtype(claim['basis'])})"))
    elif REQUIRE_CLAIM_BASIS:
        out.append(_f("CLAIM-BASIS-MISSING", path, None, f"{pre}: no basis (read or census)"))
    for k in sorted(claim):
        if k not in CLAIM_REQUIRED and k not in CLAIM_OPTIONAL:
            out.append(_f("UNKNOWN-KEY", path, None, f"{pre}: unknown key {k!r}"))
    for k in CLAIM_REQUIRED:
        if k not in claim:
            out.append(_f("MISSING-KEY", path, None, f"{pre}: missing key {k!r}"))
    for k in ("text", "reader", "date"):
        if k in claim and not _str(claim[k]):
            out.append(_f("BAD-VALUE", path, None, f"{pre}: {k} must be a non-empty string"))
    if "defs_opened" in claim:
        d = claim["defs_opened"]
        if not isinstance(d, list):
            out.append(_f("BAD-VALUE", path, None, f"{pre}: defs_opened must be a list"))
        else:
            for k, e in enumerate(d):
                ln = e.get("lines") if isinstance(e, dict) else None
                if not (_decl_entry_ok(e) and isinstance(ln, list) and len(ln) == 2 and all(_int(x) for x in ln)):
                    out.append(_f("BAD-VALUE", path, None, f"{pre}: defs_opened[{k}] must be an object with non-empty "
                                  "string module and name and lines [first, last] of two integers"))
    if "conventions_checked" in claim:
        c = claim["conventions_checked"]
        if not (isinstance(c, list) and all(isinstance(x, str) and x in ("a", "b", "c", "d", "e") for x in c)):
            out.append(_f("BAD-VALUE", path, None, f"{pre}: conventions_checked must be a list of letters a to e"))
    if "conditions" in claim:
        c = claim["conditions"]
        if not (isinstance(c, list) and all(_str(x) for x in c)):
            out.append(_f("BAD-VALUE", path, None, f"{pre}: conditions must be a list of non-empty strings"))
    if "mathlib_read" in claim:
        c = claim["mathlib_read"]
        if not (isinstance(c, list) and all(isinstance(x, str) for x in c)):
            out.append(_f("BAD-VALUE", path, None, f"{pre}: mathlib_read must be a list of strings"))


def _library_words(text):
    """The library-looking tokens of a text outside single-backtick spans, in the order of the text, each once: a dotted token
    (identifier parts joined by a dot, each part starting with a letter or `_`: Foo.bar) and a CamelCase word (a lower-case letter
    directly followed by a capital inside a word of letters, digits and `_`: getValue). It is a prompt to the signer, not a proof."""
    found = []
    for line in _LINE_SPLIT.split(text):
        line = _BACKTICK_SPAN.sub(lambda m: " " * len(m.group(0)), line)
        hits = [(m.start(), m.group(0)) for m in _DOTTED.finditer(line)]
        rest = _DOTTED.sub(lambda m: " " * len(m.group(0)), line)
        hits += [(m.start(), m.group(0)) for m in _WORD.finditer(rest) if re.search(r"[a-z][A-Z]", m.group(0))]
        found += [t for _pos, t in sorted(hits)]
    return list(dict.fromkeys(found))


def _claim_word_listings(data, path):
    """CLAIM-LIBRARY-WORD listings for the claim text and each condition of every non-null claim, in the order of the outline."""
    out = []
    for g in data.get("groups", []) if isinstance(data, dict) and isinstance(data.get("groups"), list) else []:
        claim = g.get("claim") if isinstance(g, dict) else None
        if not isinstance(claim, dict):
            continue
        where = [("claim text", claim.get("text"))]
        if isinstance(claim.get("conditions"), list):
            where += [(f"conditions[{i}]", c) for i, c in enumerate(claim["conditions"])]
        for label, text in where:
            for tok in _library_words(text) if isinstance(text, str) else []:
                out.append(_f("CLAIM-LIBRARY-WORD", path, None, f"group {g.get('id')!r} {label}: {tok!r} looks like a library name "
                              "outside backticks (write it in backticks, or in plain words)", LISTING))
    return out


def _check_group_shape(g, label, path, out):
    def bad(what):
        out.append(_f("BAD-VALUE", path, None, f"{label}: {what}"))
    for k in sorted(g):
        if k not in GROUP_KEYS:
            out.append(_f("UNKNOWN-KEY", path, None, f"{label}: unknown key {k!r}"))
    for k in GROUP_KEYS:
        if k not in g:
            out.append(_f("MISSING-KEY", path, None, f"{label}: missing key {k!r}"))
    if "id" in g and not _str(g["id"]):
        bad("id must be a non-empty string")
    if "level" in g and not (_int(g["level"]) and g["level"] >= 1):
        bad("level must be an integer of 1 or more")
    if "order" in g and not _int(g["order"]):
        bad("order must be an integer")
    if "parent" in g and not _str(g["parent"]):
        bad("parent must be a non-empty string")
    if "roots" in g:
        if not isinstance(g["roots"], list):
            bad("roots must be a list")
        else:
            for k, e in enumerate(g["roots"]):
                if not _decl_entry_ok(e):
                    bad(f"roots[{k}] must be an object with non-empty string module and name")
    if "premises" in g:
        if not isinstance(g["premises"], list):
            bad("premises must be a list")
        else:
            for k, p in enumerate(g["premises"]):
                if not _str(p):
                    bad(f"premises[{k}] must be a string id")
    if "claim" in g and g["claim"] is not None:
        if isinstance(g["claim"], dict):
            _check_claim(g["claim"], label, path, out)
        else:
            bad("claim must be an object or null")


def _premise_cycles(graph, path, out):
    """One PREMISE-CYCLE finding per cycle of the premises relation (iterative, so depth is no limit)."""
    state, reported = {}, set()
    for start in graph:
        if state.get(start):
            continue
        stack, trail = [(start, iter(graph[start]))], [start]
        state[start] = 1
        while stack:
            node, it = stack[-1]
            nxt = next(it, None)
            if nxt is None:
                state[node] = 2
                stack.pop()
                trail.pop()
            elif state.get(nxt) == 1:
                cyc = trail[trail.index(nxt):]
                if frozenset(cyc) not in reported:
                    reported.add(frozenset(cyc))
                    out.append(_f("PREMISE-CYCLE", path, None, "premises form a cycle: " + " -> ".join(cyc + [nxt])))
            elif not state.get(nxt):
                state[nxt] = 1
                stack.append((nxt, iter(graph[nxt])))
                trail.append(nxt)


def _check_outline(data, path, index):
    """(findings, the ids of the groups that have a usable id)."""
    out = []
    stats = {"groups": 0, "claimed": 0, "null": 0, "roots": 0, "defs": 0, "premises": 0, "read": 0, "census": 0, "without": 0}
    if not isinstance(data, dict):
        return [_f("BAD-VALUE", path, None, "top level: must be a JSON object")], set(), stats
    for k in sorted(data):
        if k not in TOP_KEYS:
            out.append(_f("UNKNOWN-KEY", path, None, f"top level: unknown key {k!r}"))
    for k in TOP_KEYS:
        if k not in data:
            out.append(_f("MISSING-KEY", path, None, f"top level: missing key {k!r}"))
    if "release" in data and not _str(data["release"]):
        out.append(_f("BAD-VALUE", path, None, "top level: release must be a non-empty string"))
    groups = []
    if "groups" in data:
        if isinstance(data["groups"], list):
            groups = data["groups"]
        else:
            out.append(_f("BAD-VALUE", path, None, "top level: groups must be a list"))
    # pass 1: the shape of each group, and the ids
    by_id, labels, dup_seen = {}, {}, set()
    for i, g in enumerate(groups):
        if not isinstance(g, dict):
            out.append(_f("BAD-VALUE", path, None, f"groups[{i}]: must be a JSON object"))
            continue
        gid = g.get("id")
        stats["groups"] += 1
        stats["claimed"] += isinstance(g.get("claim"), dict)
        stats["null"] += "claim" in g and g["claim"] is None
        if isinstance(g.get("claim"), dict):   # claim basis, counted over the non-null claims; a bad value is "without"
            b = g["claim"].get("basis")
            stats["read"] += b == "read"
            stats["census"] += b == "census"
            stats["without"] += not (isinstance(b, str) and b in CLAIM_BASIS)
        labels[i] = f"group {gid!r}" if _str(gid) else f"groups[{i}]"
        _check_group_shape(g, labels[i], path, out)
        if _str(gid):
            if gid not in by_id:
                by_id[gid] = g
            elif gid not in dup_seen:
                dup_seen.add(gid)
                out.append(_f("DUPLICATE-ID", path, None, f"{labels[i]}: id is used by more than one group"))
    # pass 2: the relations between groups, and the resolution of roots and opened definitions
    siblings, graph = {}, {}
    for i, g in enumerate(groups):
        if i not in labels or not _str(g.get("id")) or by_id[g["id"]] is not g:
            continue
        gid, label, level, parent = g["id"], labels[i], g.get("level"), g.get("parent")
        level_ok = _int(level) and level >= 1
        if _str(parent):
            if parent == "root":
                if level_ok and level != 1:
                    out.append(_f("BAD-LEVEL", path, None, f"{label}: level {level}, but its parent is 'root' "
                                  "(a group under root has level 1)"))
            elif parent in by_id:
                pl = by_id[parent].get("level")
                if level_ok and _int(pl) and pl >= 1 and level != pl + 1:
                    out.append(_f("BAD-LEVEL", path, None, f"{label}: level {level}, but parent {parent!r} has level {pl} "
                                  "(a child is one deeper than its parent)"))
            else:
                out.append(_f("BAD-PARENT", path, None, f"{label}: parent {parent!r} is neither 'root' nor a group id"))
            if _int(g.get("order")):
                seen = siblings.setdefault(parent, {})
                if g["order"] in seen:
                    out.append(_f("DUPLICATE-ORDER", path, None, f"{label}: order {g['order']} is also used by group "
                                  f"{seen[g['order']]!r} under parent {parent!r}"))
                else:
                    seen[g["order"]] = gid
        graph[gid] = []
        for p in g.get("premises") if isinstance(g.get("premises"), list) else []:
            if not _str(p):
                continue
            if p == gid:
                out.append(_f("BAD-PREMISE", path, None, f"{label}: premise {p!r} is the group itself"))
            elif p not in by_id:
                out.append(_f("BAD-PREMISE", path, None, f"{label}: premise {p!r} is not a group id"))
            else:
                graph[gid].append(p)
        claim, roots = g.get("claim"), g.get("roots")
        if isinstance(roots, list) and not roots:
            out.append(_f("ROOT-COUNT", path, None, f"{label}: a group needs at least one root"))
        elif isinstance(claim, dict) and isinstance(roots, list) and len(roots) != 1:
            out.append(_f("ROOT-COUNT", path, None, f"{label}: a group with a claim has exactly one root, not {len(roots)}"))
        entries = [("roots", f"{label} roots[{k}]", e) for k, e in enumerate(roots)] if isinstance(roots, list) else []
        if isinstance(claim, dict) and isinstance(claim.get("defs_opened"), list):
            entries += [("defs", f"{label} claim defs_opened[{k}]", e) for k, e in enumerate(claim["defs_opened"])]
        for which, where, e in entries:
            if _decl_entry_ok(e):
                fnd, _row = _resolve(index, where, path, None, e["module"], e["name"])
                if fnd:
                    out.append(fnd)
                else:
                    stats[which] += 1
    stats["premises"] = sum(len(v) for v in graph.values())
    _premise_cycles(graph, path, out)   # premises only, never parent
    return out, set(by_id), stats


# ---- the notes
_ARG = re.compile(r"\s*(?:\w|\d+)(?:\s*,\s*(?:\w|\d+))*\s*")   # a math argument: one letter or number, or a list of them
_MATH_SYMBOLS = "\u2264\u2265<>=^\u221a\u2211"
_PROVED = re.compile(r"\b(proved|proves)\b", re.I)


def _trailing_parenthetical(title):
    """The text inside a trailing `(...)` of the title (brackets balanced), else None."""
    s = title.rstrip()
    if not s.endswith(")"):
        return None
    depth = 0
    for i in range(len(s) - 1, -1, -1):
        if s[i] == ")":
            depth += 1
        elif s[i] == "(":
            depth -= 1
            if depth == 0:
                return s[i + 1:-1]
    return None


def _status_parenthetical(content):
    """True unless the bracket holds only code spans, commas and `and`, or a one-letter or number argument."""
    if _ARG.fullmatch(content):
        return False
    if _CODESPAN.search(content) and not re.sub(r"\band\b|,", "", _CODESPAN.sub("", content)).strip():
        return False
    return True


def _title_findings(name, line, t):
    out = []
    s = t.strip()
    plain = _CODESPAN.sub("", s)
    if s.startswith("`") or not re.search(r"\w", plain):
        out.append(_f("TITLE-CODE-FIRST", name, line, f"list_title starts with code or has no word outside code: {t!r}"))
    inner = _trailing_parenthetical(t)
    if inner is not None and _status_parenthetical(inner):
        out.append(_f("TITLE-PARENTHETICAL", name, line, f"list_title ends with a parenthetical: {t!r}"))
    sym = next((ch for ch in _MATH_SYMBOLS if ch in plain), None) or ("Re s" if re.search(r"\bRe s\b", plain) else None)
    if sym:
        out.append(_f("TITLE-NOTE", name, line, f"list_title has math outside code ({sym!r}): {t!r}", LISTING))
    for m in _PROVED.finditer(plain):
        if not plain[:m.start()].endswith("Lean "):
            out.append(_f("TITLE-NOTE", name, line, f"list_title says {m.group(0)!r} without 'Lean' directly before it: {t!r}", LISTING))
            break
    return out


def _norm(s):
    return " ".join(s.lower().split())


def _frame_hit(text, frames, kind):
    """(kind of the frame, the phrase) of the first OTHER kind's opening phrase the text starts with, else None.
    A phrase is cut at its first placeholder, `{` or `<`; the match is case-blind and ends at a word boundary."""
    t = _norm(text.lstrip("*_> \t"))
    for other, phrases in frames.items():
        if other == kind:
            continue
        for ph in phrases:
            cut = ph.split("{")[0].split("<")[0].strip()
            p = _norm(cut)
            if p and t.startswith(p) and not (len(t) > len(p) and t[len(p)].isalnum()):
                return other, cut
    return None


def _count_lines(text):
    return text.count("\n") + (0 if text == "" or text.endswith("\n") else 1)


def _canon(tag, data):
    try:
        return rh.format_comment(tag, data)
    except Exception:
        return "(not printable)"


class _Ctx:
    """What the checks of one run share: the decls index, the groups, the ids seen, the options."""


def _check_header(name, headers, ctx):
    out = []
    if not headers:
        return [_f("NO-HEADER", name, None, "has no rh-note header")], None
    h = headers[0]
    if len(headers) > 1:
        out.append(_f("SECOND-HEADER", name, headers[1].line, f"{len(headers)} rh-note headers, on lines "
                      + ", ".join(str(x.line) for x in headers)))
    elif not h.before_first_h2:
        out.append(_f("HEADER-AFTER-H2", name, h.line, "the rh-note header comes after the first '## ' heading"))
    d = h.data
    out += [_f("HEADER-PROBLEM", name, h.line, p) for p in rh.header_problems(d)]
    if not h.canonical:
        out.append(_f("NONCANONICAL", name, h.line, "not the canonical form; canonical: " + _canon("rh-note", d)))
    g, lv = d.get("group"), d.get("level")
    if g == "root":   # not a group id: only a level-0 note may name it
        if not (_int(lv) and lv == 0):
            out.append(_f("GROUP-ROOT-LEVEL", name, h.line, f"group 'root' is for level 0 only (this note has level {lv!r})"))
    elif _str(g) and g not in ctx.groups:
        out.append(_f("UNKNOWN-GROUP", name, h.line, f"group {g!r} is not in the outline"))
    if _str(d.get("list_title")):
        out += _title_findings(name, h.line, d["list_title"])
    return out, (d["id"] if _str(d.get("id")) else None)


def _check_block(name, b, note_id, listed, lines, ctx, out):
    d = b.data
    bid = d.get("id")
    label = f"block {bid!r}" if isinstance(bid, str) else "block"
    if not b.canonical:
        out.append(_f("NONCANONICAL", name, b.line, "not the canonical form; canonical: " + _canon("rh-block", d)))
    out += [_f("ITEM-BAD-VALUE" if p.startswith("item: must be an integer") else "BLOCK-PROBLEM", name, b.line, f"{label}: {p}")
            for p in rh.problems(d, note_id)]
    if isinstance(bid, str):
        if bid in ctx.ids:
            out.append(_f("DUPLICATE-ID", name, b.line, f"block id {bid!r} is also used at {ctx.ids[bid][0]}:{ctx.ids[bid][1]}"))
        else:
            ctx.ids[bid] = (name, b.line)
    rows = []   # M4: the resolved rows, as (module, name, (first, last))
    for k, e in enumerate(d.get("decls") if isinstance(d.get("decls"), list) else []):
        if _decl_entry_ok(e):
            fnd, row = _resolve(ctx.index, f"{label} decls[{k}]", name, b.line, e["module"], e["name"])
            if fnd:
                out.append(fnd)
            else:
                rows.append((e["module"], e["name"], row))
    for k, e in enumerate(d.get("defs_opened") if isinstance(d.get("defs_opened"), list) else []):
        if _decl_entry_ok(e):
            fnd, _row = _resolve(ctx.index, f"{label} defs_opened[{k}]", name, b.line, e["module"], e["name"])
            if fnd:
                out.append(fnd)
    kind_of_target = (b.target or {}).get("type")   # a block anchors a paragraph, a table or a lean block
    if kind_of_target in ("none", "other"):
        out.append(_f("ORPHAN-BLOCK", name, b.line, f"{label} anchors nothing: its target is of type '{kind_of_target}', "
                      "not a paragraph, table or lean block"))
    f, ln = d.get("file"), d.get("lines")   # M5: the table half always, the existence and line-count halves with --src
    lines_ok = isinstance(ln, list) and len(ln) == 2 and all(_int(x) for x in ln)
    if _str(f):
        if f not in (listed or []):
            out.append(_f("FILE-NOT-LISTED", name, b.line, f"{label} file {f} is not in the note's file table"))
        elif ctx.src is not None:
            n = ctx.file_lines(f)
            if n is None:
                out.append(_f("FILE-MISSING", name, b.line, f"{label} file {f} is listed but not found under --src"))
            elif n == -1:
                out.append(_f("FILE-UNREADABLE", name, b.line, f"{label} file {f} under --src is not valid UTF-8"))
            elif lines_ok and ln[1] > n:
                out.append(_f("LINES-OUTSIDE-FILE", name, b.line, f"{label} lines {ln} but {f} has {n} lines"))
        if lines_ok and rows and not any(r[0] <= ln[0] and ln[1] <= r[1] for _m, _n, r in rows):
            where = "; ".join(f"{m} {n} ({r[0]}, {r[1]})" for m, n, r in rows)
            out.append(_f("EXTENT-WARNING", name, b.line,
                          f"{label} lines {ln} are outside the text extent of every resolved row: {where}", LISTING))
    if "row" in d or "col" in d:   # M7
        t = b.target or {}
        if t.get("type") != "table":
            out.append(_f("NOT-A-TABLE", name, b.line,
                          f"{label} carries row/col but its target is of type '{t.get('type')}', not a table"))
        else:
            if _int(d.get("row")) and d["row"] > t["nrows"]:
                out.append(_f("ROW-OUT-OF-RANGE", name, b.line, f"{label} row {d['row']} but the table has {t['nrows']} body rows"))
            if _int(d.get("col")) and d["col"] > t["ncols"]:
                out.append(_f("COL-OUT-OF-RANGE", name, b.line, f"{label} col {d['col']} but the table has {t['ncols']} columns"))
    ttype = (b.target or {}).get("type")   # list items: a list needs item, item needs a list
    if "item" in d:
        if ttype != "list":
            out.append(_f("NOT-A-LIST", name, b.line, f"{label} carries item but its target is of type '{ttype}', not a list"))
        elif _int(d["item"]) and d["item"] >= 1 and d["item"] > b.target["nitems"]:
            out.append(_f("ITEM-OUT-OF-RANGE", name, b.line,
                          f"{label} item {d['item']} but the list has {b.target['nitems']} top-level items"))
    elif ttype == "list":
        out.append(_f("ITEM-REQUIRED", name, b.line, f"{label}: a list needs 'item' (1-based, like 'row')"))
    if ttype == "list":
        on = {k for k, v in b.target["shape"].items() if v}
        for entry in REFUSED_LIST_SHAPES:
            if entry and entry <= on:
                out.append(_f("LIST-SHAPE-REFUSED", name, b.line,
                              f"{label} anchors a list whose shape the renderer shows differently: {', '.join(sorted(entry))}"))
    kind = d.get("kind")   # F12
    if ctx.strings is not None and kind in FRAME_ONLY and (b.target or {}).get("type") == "paragraph":
        t = b.target
        hit = _frame_hit(" ".join(lines[t["first_line"] - 1:t["last_line"]]), ctx.strings, kind)
        if hit:
            out.append(_f("FRAME-NOTE", name, b.line,
                          f"{label} ({kind}): the text opens with a frame of kind {hit[0]!r} ({hit[1]!r})", LISTING))
    return kind


def _check_note(name, text, ctx):
    """(findings, header ok, id or file stem for the note line, counts by kind, invalid kinds, number of blocks)."""
    headers, blocks, malformed = rh.parse_note(text)
    out = [_f(p.code, name, p.line, p.message) for p in malformed]
    hdr, note_id = _check_header(name, headers, ctx)
    out += hdr
    lines = _LINE_SPLIT.split(text) if ctx.strings is not None else None
    listed = clb.listed_files(text)
    counts, invalid = {k: 0 for k in rh.KINDS}, 0
    for b in blocks:
        kind = _check_block(name, b, note_id, listed, lines, ctx, out)
        if kind in counts:
            counts[kind] += 1
        else:
            invalid += 1
    out.sort(key=lambda x: x[2] or 0)
    return out, not any(f[4] == ERROR for f in hdr), note_id or os.path.splitext(name)[0], counts, invalid, len(blocks)


def _note_line(label, hdr_ok, counts, invalid, nblocks):
    parts = [f"{k}={counts[k]}" for k in rh.KINDS if counts[k]] + ([f"invalid={invalid}"] if invalid else [])
    return f"note {label} header {'ok' if hdr_ok else 'FAILED'}, blocks {nblocks}" + (f" ({' '.join(parts)})" if nblocks else "")


# ---- the byte check
def _vcs(top, *args):
    try:
        return subprocess.run(["git", "-C", top, *args], capture_output=True)
    except OSError:
        raise _Unreadable("git is needed for --base but could not be run")


_HEADING = re.compile(r"#{1,6} (.+)\Z")   # F27: 1 to 6 marks, a space, text; at column 0, on the line without its ending
_DATE_TOKEN = re.compile(r"(?<![0-9])[0-9]{4}-[0-9]{2}-[0-9]{2}(?![0-9])")
_RELEASE_DATE = re.compile(r"rh-([0-9]{4}-[0-9]{2}-[0-9]{2})")   # matched with fullmatch


def _real_date(s):
    """The datetime.date of a YYYY-MM-DD string, None when it is not a real calendar date."""
    try:
        return datetime.date(int(s[:4]), int(s[5:7]), int(s[8:10]))
    except ValueError:
        return None


def _insertion_runs(a, b):
    """F27 alignment: match each line of a, in order and greedily from the left, to the earliest equal line of b after the
    previous match. None when a is not a subsequence of b; else the maximal gaps of b as (start, end, index in a of the
    base line before the gap, -1 for none), in file order, including a gap after the last matched line."""
    runs, k, start = [], 0, None
    for j, line in enumerate(b):
        if k < len(a) and a[k] == line:
            if start is not None:
                runs.append((start, j, k - 1))
                start = None
            k += 1
        elif start is None:
            start = j
    if k < len(a):
        return None
    if start is not None:
        runs.append((start, len(b), k - 1))
    return runs


def _bytes_check(name, text, rel, ctx):
    """The findings of the byte check for one note: [] when equal, [NEW-NOTE], one BYTE-DIFF, or one ADDITION listing per run
    when the note only gained dated additions (F27)."""
    show = _vcs(ctx.top, "cat-file", "blob", f"{ctx.rev}:{rel}")
    if show.returncode != 0:
        return [_f("NEW-NOTE", name, None, f"is not present at {ctx.base}", LISTING)]
    try:   # both sides without their anchor lines (header and blocks), decoded the same way
        old_text = rh.strip_anchor_lines(show.stdout.decode("utf-8"))
        old = old_text.encode("utf-8")
    except UnicodeDecodeError:
        return [_f("BYTE-DIFF", name, None, f"the note at {ctx.base} is not valid UTF-8 and cannot be compared")]
    new = rh.strip_anchor_lines(text).encode("utf-8")
    if old == new:
        return []
    a, b = old.splitlines(True), new.splitlines(True)
    i = next((k for k in range(min(len(a), len(b))) if a[k] != b[k]), min(len(a), len(b)))

    # the line in the CURRENT file as it is on disk: the i-th line that is not an anchor line of this note (the anchor lines are
    # the ones parse_note reports, the set strip_anchor_lines removes); at the end it is the line after the last non-anchor line
    headers, blocks, _problems = rh.parse_note(text)
    anchors = {x.line for x in headers + blocks}
    parts = _LINE_SPLIT.split(text)
    plain = [k for k in range(1, len(parts) - (parts[-1] == "") + 1) if k not in anchors]

    def bytediff(i, extra=""):
        def fmt(ls):
            return repr(ls[i].decode("utf-8", "replace")) if i < len(ls) else "<no line>"
        line = plain[i] if i < len(b) and i < len(plain) else (plain[-1] + 1 if plain else 1)
        return _f("BYTE-DIFF", name, line, f"line {line} differs (line {i + 1} of the text without anchors): "
                  f"at {ctx.base} (without anchors) {fmt(a)}, now (without anchors) {fmt(b)}{extra}")
    runs = _insertion_runs(a, b)
    if runs is None:   # a base line was removed or altered: as before
        return [bytediff(i)]
    rel_date = None   # the floor: the date of the header's `release` when it is rh-YYYY-MM-DD and real, else none
    if headers and isinstance(headers[0].data.get("release"), str):
        m = _RELEASE_DATE.fullmatch(headers[0].data["release"])
        rel_date = _real_date(m.group(1)) if m else None
    window = (f"{rel_date.isoformat()} to {ctx.today.isoformat()}" if rel_date else f"up to {ctx.today.isoformat()} (no lower bound)")
    published = None   # rh_anchor's reading of the published text, for its fences
    adds = []
    for start, end, prev in runs:
        if prev >= 0:   # inside a fence of the published text: opened at or before the base line before the run, closed after it
            if published is None:
                published = rh._Analysis(old_text)
            fi = published.fence_of[prev]
            if fi != -1 and (published.fences[fi]["close"] is None or published.fences[fi]["close"] > prev):
                return [bytediff(start)]
        lines = [x.decode("utf-8") for x in b[start:end]]
        first = next((x for x in lines if x.strip()), None)   # the first line after the LEADING blank lines
        m = _HEADING.match(first.rstrip("\r\n")) if first is not None else None
        if not m:
            return [bytediff(start)]
        heading = m.group(1).strip()
        day = next((d for d in map(_real_date, _DATE_TOKEN.findall(heading)) if d), None)   # the first REAL date in the heading
        if day is None:
            return [bytediff(start)]
        if day > ctx.today or (rel_date is not None and day < rel_date):
            return [bytediff(start, f"; the added heading's date {day.isoformat()} is outside the window {window}")]
        adds.append(_f("ADDITION", name, plain[start], f"{end - start} lines, heading {heading}", LISTING))
    return adds


# ---- the run
def _read_json(path, what):
    try:
        with open(path, "rb") as fh:
            return json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError, RecursionError) as e:   # RecursionError: JSON nested too deep to parse
        raise _Unreadable(f"cannot read the {what}: {e}")


def _read_frames(path):
    data = _read_json(path, "strings file")
    fr = data.get("frames") if isinstance(data, dict) else None
    if not (isinstance(fr, dict) and all(isinstance(v, list) and all(isinstance(x, str) for x in v) for v in fr.values())):
        raise _Unreadable("the strings file has no usable `frames` key (kind -> list of opening phrases)")
    return fr


def _source_lines(src):
    cache = {}

    def file_lines(rel):   # the line count, None when there is no such file, -1 when it is not UTF-8
        if rel not in cache:
            p = os.path.join(src, rel)
            if not os.path.isfile(p):
                cache[rel] = None
            else:
                try:
                    with open(p, "rb") as fh:
                        cache[rel] = _count_lines(fh.read().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n"))
                except (OSError, UnicodeDecodeError):
                    cache[rel] = -1
        return cache[rel]
    return file_lines


def _setup_git(ctx, notes_dir, names, base, repo):
    rdir = repo if repo is not None else notes_dir
    if not os.path.isdir(rdir):
        raise _Unreadable(f"--repo is not a directory: {rdir}")
    top = _vcs(rdir, "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        raise _Unreadable(f"--repo {rdir} is not inside a git work tree")
    ctx.top = os.path.realpath(top.stdout.decode("utf-8", "replace").strip())
    rev = _vcs(ctx.top, "rev-parse", "--verify", "--quiet", base + "^{commit}")
    if rev.returncode != 0:
        raise _Unreadable(f"cannot resolve --base {base} to a commit")
    ctx.rev, ctx.base, rels = rev.stdout.decode().strip(), base, {}
    for n in names:
        rel = os.path.relpath(os.path.realpath(os.path.join(notes_dir, n)), ctx.top)
        if rel.startswith(".."):
            raise _Unreadable(f"note {n} is outside the repository of --repo")
        rels[n] = rel.replace(os.sep, "/")
    return rels


def _parse_today(today):
    if today is None:
        return datetime.datetime.now(datetime.timezone.utc).date()
    d = _real_date(today) if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", today) else None
    if d is None:
        raise _Unreadable(f"--today must be a real date written YYYY-MM-DD, got {today!r}")
    return d


def _run(notes_dir, outline, decls, base, repo, strings, src, glob, today=None):
    ctx = _Ctx()
    ctx.today = _parse_today(today)
    if not os.path.isdir(notes_dir):
        raise _Unreadable(f"NOTES_DIR is not a directory: {notes_dir}")
    odata = _read_json(outline, "outline")
    ctx.index, nrows = _read_decls(decls)
    ctx.strings = _read_frames(strings) if strings is not None else None
    ctx.src = src
    if src is not None:
        if not os.path.isdir(src):
            raise _Unreadable(f"--src is not a directory: {src}")
        ctx.file_lines = _source_lines(src)
    names = sorted(n for n in os.listdir(notes_dir) if fnmatch.fnmatchcase(n, glob) and os.path.isfile(os.path.join(notes_dir, n)))
    texts = {}
    for n in names:
        try:
            with open(os.path.join(notes_dir, n), "rb") as fh:
                texts[n] = fh.read().decode("utf-8")
        except (OSError, UnicodeDecodeError) as e:
            raise _Unreadable(f"cannot read note {n}: {e}")
    rels = _setup_git(ctx, notes_dir, names, base, repo) if base is not None else {}
    stop = []
    if not names:
        stop.append(f"{NOCODE}: no note matches {glob} in NOTES_DIR")
    if isinstance(odata, dict) and isinstance(odata.get("groups"), list) and not odata["groups"]:
        stop.append(f"{NOCODE}: the outline has no groups")
    if nrows == 0:
        stop.append(f"{NOCODE}: decls.tsv has no rows")
    if stop:
        return 3, stop
    found, ctx.groups, st = _check_outline(odata, os.path.basename(outline), ctx.index)
    words = _claim_word_listings(odata, os.path.basename(outline))
    lines, errors, warnings = [_render(f) for f in found + words], len(found), len(words)
    ctx.ids = {}
    hid, hline = {}, {}   # note ids: which notes carry each header id (a note with no header carries none)
    for n in names:
        hs = rh.parse_note(texts[n])[0]
        nid = hs[0].data.get("id") if hs else None
        if _str(nid):
            hid.setdefault(nid, []).append(n)
            hline[n] = hs[0].line
    dup_at = {}
    for nid, files in hid.items():
        if len(files) > 1:
            dup_at[files[0]] = f"note id {nid!r} is used by {len(files)} notes: " + ", ".join(files)
    totals, invalid_total, n_equal, n_new, n_add = {k: 0 for k in rh.KINDS}, 0, 0, 0, 0
    for n in names:
        fs, hdr_ok, label, counts, invalid, nblocks = _check_note(n, texts[n], ctx)
        if n in dup_at:
            fs.append(_f("NOTE-ID-DUPLICATE", n, hline[n], dup_at[n]))
            fs.sort(key=lambda x: x[2] or 0)
        bfs = _bytes_check(n, texts[n], rels[n], ctx) if base is not None else []
        fs += bfs
        if base is not None:
            n_new += any(f[0] == "NEW-NOTE" for f in bfs)
            n_equal += not bfs
            n_add += sum(1 for f in bfs if f[0] == "ADDITION")
        lines += [_render(f) for f in fs]
        errors += sum(1 for f in fs if f[4] == ERROR)
        warnings += sum(1 for f in fs if f[4] == LISTING)
        lines.append(_note_line(label, hdr_ok, counts, invalid, nblocks))
        for k in rh.KINDS:
            totals[k] += counts[k]
        invalid_total += invalid
    if ctx.strings is None:
        lines.append("FRAME-NOTE skipped: no strings file")
    elif not any(ctx.strings.values()):
        lines.append("FRAME-NOTE skipped: no frame phrases were loaded from the strings file")
    else:
        lines.append(f"strings: {sum(len(v) for v in ctx.strings.values())} frame phrases loaded for "
                     f"{sum(1 for v in ctx.strings.values() if v)} kinds")
    lines.append(f"outline: {st['groups']} groups, {st['claimed']} claimed, {st['null']} null, {st['roots']} roots resolved, "
                 f"{st['defs']} defs_opened resolved, {st['premises']} premise links")
    lines.append(f"claim basis: {st['read']} read, {st['census']} census, {st['without']} without")
    lines.append("blocks by kind: " + " ".join(f"{k}={totals[k]}" for k in rh.KINDS) + (f" invalid={invalid_total}" if invalid_total else ""))
    lines.append("in-file check (M5): ran" if src is not None else "in-file check (M5): table membership ran; existence and line count skipped, no --src given")
    lines.append(f"byte check: {n_equal} notes equal to {base}, {n_new} new, {n_add} additions" if base is not None else "byte check: did not run, no --base given")
    lines.append(f"{len(names)} notes, {errors} findings, {warnings} warnings")
    return (1 if errors else 0), lines


def run(notes_dir, outline, decls, base=None, repo=None, strings=None, src=None, glob=DEFAULT_GLOB, today=None):
    """Check the notes and print the report; return the exit code 0, 1, 2 or 3. Exit 2 prints nothing to stdout."""
    try:
        rc, lines = _run(notes_dir, outline, decls, base, repo, strings, src, glob, today)
    except _Unreadable as e:
        print("notes_meta: " + str(e), file=sys.stderr)
        return 2
    print("\n".join(lines))
    return rc


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


def G(i, level=1, parent="root", order=1, roots=None, claim=None, premises=None):
    return {"id": i, "level": level, "parent": parent, "order": order, "roots": [R("A.B", "foo")] if roots is None else roots,
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
        self.f = [x for x in self.lines if re.match(r"[A-Z][A-Z0-9-]+ ", x)
                  and not x.startswith((NOCODE, "FRAME-NOTE skipped", "REFUSED"))]


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
       raw_outline=None, repo_arg=False, check_dirs=None, today=None):
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
        if today is not None:
            kw["today"] = today
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
                 "NO-HEADER 03-c.md has no rh-note header",
                 "note 03-c header FAILED, blocks 0",
                 "FRAME-NOTE skipped: no strings file",
                 "outline: 2 groups, 0 claimed, 2 null, 2 roots resolved, 0 defs_opened resolved, 1 premise links",
                 "claim basis: 0 read, 0 census, 0 without",
                 "blocks by kind: machine_fact=0 reading=1 interpretation=0 correction=0 not_read=1 argument=0",
                 "in-file check (M5): table membership ran; existence and line count skipped, no --src given",
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


@case("U1", "an unknown key that starts with an underscore is refused in a group, in a claim and at the top level; "
            "a roots entry may carry extra keys (LIMIT)")
def _():
    one = [R("A.B", "foo")]
    fe(go(outline=OL(dict(G("g1"), _x=1))), ["UNKNOWN-KEY outline.json group 'g1': unknown key '_x'"], 1)
    fe(go(outline=OL(G("g1", roots=one, claim=dict(CLAIM, _x=1)))),
       ["UNKNOWN-KEY outline.json group 'g1' claim: unknown key '_x'"], 1)
    fe(go(outline=OL(G("g1"), _draft="v")), ["UNKNOWN-KEY outline.json top level: unknown key '_draft'"], 1)
    clean(go(outline=OL(G("g1", roots=[dict(R("A.B", "foo"), _x=1)]))))


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


@case("O4", "every group needs at least one root (0 is ROOT-COUNT, claim or not: a flipped case); a non-null claim needs exactly one "
             "(2 is ROOT-COUNT); a null claim may have 1 or 3")
def _():
    one = [R("A.B", "foo")]
    clean(go(outline=OL(G("g1", roots=one, claim=CLAIM))))
    fe(go(outline=OL(G("g1", roots=one + [R("A.C", "baz")], claim=CLAIM))),
       ["ROOT-COUNT outline.json group 'g1': a group with a claim has exactly one root, not 2"], 1)
    none = ["ROOT-COUNT outline.json group 'g1': a group needs at least one root"]
    fe(go(outline=OL(G("g1", roots=[], claim=CLAIM))), none, 1)
    fe(go(outline=OL(G("g1", roots=[], claim=None))), none, 1)
    for roots in (one, one + [R("A.C", "baz"), R("A.B", "bar")]):
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
    fe(r, ["NO-HEADER 01-a.md has no rh-note header"], 1)
    ok("note 01-a header FAILED, blocks 0" in r.lines, "the note line uses the file name when there is no id")
    two = NOTE(body="Text.\n" + rh.format_comment("rh-note", {"id": "01"}) + "\n")
    fe(go(notes={"01-a.md": two}), ["SECOND-HEADER 01-a.md:7 2 rh-note headers, on lines 2, 7"], 1)
    late = "# T\n\n## Body\n\n" + rh.format_comment("rh-note", {"authors": ["H"], "group": "g1", "id": "01", "level": 2,
                                                                  "list_title": "A title", "readers": ["K"], "release": "r"}) + "\n"
    fe(go(notes={"01-a.md": late}), ["HEADER-AFTER-H2 01-a.md:5 the rh-note header comes after the first '## ' heading"], 1)
    fenced = "# T\n\n```\n" + rh.format_comment("rh-note", {"id": "01"}) + "\n```\n"
    fe(go(notes={"01-a.md": fenced}), ["NO-HEADER 01-a.md has no rh-note header"], 1)


@case("M2a", "header_problems() findings, level 0 to 2, and a group that is not in the outline")
def _():
    fe(go(notes={"01-a.md": NOTE(level=3)}), ["HEADER-PROBLEM 01-a.md:2 level: must be 0, 1 or 2"], 1)
    fe(go(notes={"01-a.md": NOTE(readers=None)}), ["HEADER-PROBLEM 01-a.md:2 readers: missing or not a list"], 1)
    fe(go(notes={"01-a.md": NOTE(group="zz")}), ["UNKNOWN-GROUP 01-a.md:2 group 'zz' is not in the outline"], 1)
    for lv in (0, 1, 2):
        clean(go(notes={"01-a.md": NOTE(level=lv)}))


def _title(t, **kw):
    return go(notes={"01-a.md": NOTE(title=t)}, **kw)


@case("TITLE1", "a trailing parenthetical is allowed only when it holds code spans, commas and `and`, or a one-letter or number argument; "
                "any other (a status, a note) is TITLE-PARENTHETICAL")
def _():
    for t in ("Statement (draft)", "(statements only)", "(a census, not an explanation)", "Title (a (b))", "Title (`x` draft)",
              "Title (and)", "Title (x y)"):
        fe(_title(t), ["TITLE-PARENTHETICAL 01-a.md:2 list_title ends with a parenthetical: " + repr(t)], 1)
    for t in ("Statements (`VWin`, `Green`)", "The zeta function \u03b6(s)", "Pair (`a` and `b`)", "Value at f(12)", "Pair p(x, y)",
              "A (mid) title", "Ends with a bracket)", "(Opens) and goes on"):
        clean(_title(t))


@case("TITLE2", "a title that starts with a code span, or has no word outside code spans, is TITLE-CODE-FIRST")
def _():
    for t in ("`foo`", "`a` `b`", "``a`b``", "`VWin` and Green", "`x` is a bound", "`lone"):
        fe(_title(t), ["TITLE-CODE-FIRST 01-a.md:2 list_title starts with code or has no word outside code: " + repr(t)], 1)
    for t in ("The `VWin` bound", "A `lone", "Plain title", "Bounds on `x`"):
        clean(_title(t))


@case("TITLE3", "a math symbol or `Re s` outside code spans in a title is a TITLE-NOTE listing (exit unchanged); inside code it is fine")
def _():
    for t, sym in (("Bound x \u2264 3", "\u2264"), ("Bound x \u2265 3", "\u2265"), ("Bound x < 3", "<"), ("Bound x > 3", ">"),
                   ("Bound x = 3", "="), ("Bound x ^ 3", "^"), ("The \u221a bound", "\u221a"), ("The \u2211 bound", "\u2211"),
                   ("Zeros with Re s large", "Re s")):
        r = _title(t)
        fe(r, ["TITLE-NOTE 01-a.md:2 list_title has math outside code (" + repr(sym) + "): " + repr(t)], 0)
        ok("note 01 header ok, blocks 0" in r.lines and r.lines[-1] == "1 notes, 0 findings, 1 warnings", r.out)
    for t in ("Bound on `x \u2264 3`", "The zeta function \u03b6(s)", "Zeros with `Re s` large", "Plain title"):
        clean(_title(t))


@case("TITLE4", "proved or proves not directly after `Lean` in a title is a TITLE-NOTE listing; `Lean proved` is fine")
def _():
    for t, w in (("The bound is proved here", "proved"), ("It proves the bound", "proves"), ("Proved bounds", "Proved"),
                 ("Lean has it and proved it", "proved")):
        fe(_title(t), ["TITLE-NOTE 01-a.md:2 list_title says " + repr(w) + " without 'Lean' directly before it: " + repr(t)], 0)
    for t in ("Lean proved the bound", "Lean proves the bound", "Statements about primes"):
        clean(_title(t))


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


@case("ID1", "two notes whose headers carry the same id: NOTE-ID-DUPLICATE on the first, naming both files")
def _():
    fe(go(notes={"01-a.md": NOTE(), "02-b.md": NOTE()}), ["NOTE-ID-DUPLICATE 01-a.md:2 note id '01' is used by 2 notes: 01-a.md, 02-b.md"], 1)
    fe(go(notes={"01-a.md": NOTE(nid="07"), "02-b.md": NOTE(nid="08"), "03-c.md": NOTE(nid="07")}),
       ["NOTE-ID-DUPLICATE 01-a.md:2 note id '07' is used by 2 notes: 01-a.md, 03-c.md"], 1)


@case("ID2", "distinct ids are clean, and ids that differ only in letter case are distinct")
def _():
    clean(go(notes={"01-a.md": NOTE(nid="01"), "02-b.md": NOTE(nid="02")}))
    clean(go(notes={"01-a.md": NOTE(nid="ab"), "02-b.md": NOTE(nid="AB")}))


@case("ID3", "a note with no header is not a duplicate of anything, not even of a note whose id is its own file stem")
def _():
    fe(go(notes={"01-a.md": NOTE(), "02-b.md": "# T\n"}), ["NO-HEADER 02-b.md has no rh-note header"], 1)
    fe(go(notes={"01-a.md": NOTE(nid="02-b"), "02-b.md": "# T\n"}), ["NO-HEADER 02-b.md has no rh-note header"], 1)


@case("ID4", "three notes with one id: one finding on the first, naming all three")
def _():
    fe(go(notes={"01-a.md": NOTE(), "02-b.md": NOTE(), "03-c.md": NOTE()}),
       ["NOTE-ID-DUPLICATE 01-a.md:2 note id '01' is used by 3 notes: 01-a.md, 02-b.md, 03-c.md"], 1)


@case("ID5", "two notes with an empty header id: the two HEADER-PROBLEMs and no NOTE-ID-DUPLICATE")
def _():
    fe(go(notes={"01-a.md": NOTE(nid=""), "02-b.md": NOTE(nid="")}),
       ["HEADER-PROBLEM 01-a.md:2 id: missing or not a non-empty string", "HEADER-PROBLEM 02-b.md:2 id: missing or not a non-empty string"], 1)


@case("ID6", "the duplicate finding is in line order among the first note's findings: line 2 before a block problem at line 7")
def _():
    first = NOTE(body="Some text.\n" + BL(kind="nope") + "\n")
    fe(go(notes={"01-a.md": first, "02-b.md": NOTE()}),
       ["NOTE-ID-DUPLICATE 01-a.md:2 note id '01' is used by 2 notes: 01-a.md, 02-b.md",
        "BLOCK-PROBLEM 01-a.md:7 block '01.b01': kind: must be one of machine_fact, reading, interpretation, correction, not_read, argument"], 1)


@case("ID7", "ids compare as exact strings: a trailing space makes another id, and so do two Unicode forms of one accented letter")
def _():
    clean(go(notes={"01-a.md": NOTE(nid="01"), "02-b.md": NOTE(nid="01 ")}))
    clean(go(notes={"01-a.md": NOTE(nid="café"), "02-b.md": NOTE(nid="café")}))


@case("ID8", "only a note's first header counts: a second header that reuses another note's id gets SECOND-HEADER and no NOTE-ID-DUPLICATE")
def _():
    second = NOTE(nid="02", body="Text.\n" + rh.format_comment("rh-note", {"id": "01"}) + "\n")
    fe(go(notes={"01-a.md": NOTE(nid="01"), "02-b.md": second}), ["SECOND-HEADER 02-b.md:7 2 rh-note headers, on lines 2, 7"], 1)


@case("M3b", "a block id used twice, in one note or in two, is DUPLICATE-ID naming both places")
def _():
    two = NOTE(body="Some text.\n" + BL() + "\n" + BL() + "\n")
    fe(go(notes={"01-a.md": two}), ["DUPLICATE-ID 01-a.md:8 block id '01.b01' is also used at 01-a.md:7"], 1)
    one = NOTE(body="Some text.\n" + BL() + "\n")
    fe(go(notes={"01-a.md": one, "02-b.md": one}),
       ["NOTE-ID-DUPLICATE 01-a.md:2 note id '01' is used by 2 notes: 01-a.md, 02-b.md",
        "DUPLICATE-ID 02-b.md:7 block id '01.b01' is also used at 01-a.md:7"], 1)
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
    ok("in-file check (M5): table membership ran; existence and line count skipped, no --src given" in r.lines, r.out)
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
    clean(go(notes=n("Fromage is not a frame.", ARG()), strings=FR))   # a phrase ends at a word boundary
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
    ok("byte check: 1 notes equal to HEAD, 0 new, 0 additions" in r.lines, r.out)
    r = go(notes={"01-a.md": cur}, committed={"01-a.md": T0}, base="HEAD", repo_arg=True)
    eq((r.f, r.rc), ([], 0), "--repo given")


@case("B1b", "BYTE-DIFF names the note and the first differing line of the text without anchors (FLIPPED wording: at REV, now); a line ending is a difference")
def _():
    cur = NOTE(body="Some texts.\n" + BL() + "\nMore text.\n")
    fe(go(notes={"01-a.md": cur}, committed={"01-a.md": T0}, base="HEAD"),
       ["BYTE-DIFF 01-a.md:6 line 6 differs (line 5 of the text without anchors): at HEAD (without anchors) 'Some text.\\n', now (without anchors) 'Some texts.\\n'"], 1)
    crlf = T0.replace("\n", "\r\n")
    fe(go(notes={"01-a.md": CUR}, committed={"01-a.md": crlf}, base="HEAD"),
       ["BYTE-DIFF 01-a.md:1 line 1 differs (line 1 of the text without anchors): at HEAD (without anchors) '# Note\\r\\n', now (without anchors) '# Note\\n'"], 1)
    short = "# Note\n\n## Body\n\nSome text.\n"
    fe(go(notes={"01-a.md": NOTE(body="Some text.\n")}, committed={"01-a.md": T0}, base="HEAD"),
       ["BYTE-DIFF 01-a.md:7 line 7 differs (line 6 of the text without anchors): at HEAD (without anchors) 'More text.\\n', now (without anchors) <no line>"], 1)
    fe(go(notes={"01-a.md": CUR}, committed={"01-a.md": short}, base="HEAD"),
       ["BYTE-DIFF 01-a.md:7 line 7 differs (line 6 of the text without anchors): at HEAD (without anchors) <no line>, now (without anchors) 'More text.\\n'"], 1)


@case("B1e", "a blank line at the end of one side is a BYTE-DIFF: the comparison is exact, not trimmed")
def _():
    fe(go(notes={"01-a.md": CUR}, committed={"01-a.md": T0 + "\n"}, base="HEAD"),
       ["BYTE-DIFF 01-a.md:8 line 8 differs (line 7 of the text without anchors): at HEAD (without anchors) '\\n', now (without anchors) <no line>"], 1)
    fe(go(notes={"01-a.md": CUR + "\n"}, committed={"01-a.md": T0}, base="HEAD"),
       ["BYTE-DIFF 01-a.md:8 line 8 differs (line 7 of the text without anchors): at HEAD (without anchors) <no line>, now (without anchors) '\\n'"], 1)


@case("B1c", "CRLF notes compare by bytes: anchors added with CRLF endings leave the note equal to the commit")
def _():
    crlf = T0.replace("\n", "\r\n")
    cur = NOTE(body="Some text.\n" + BL() + "\nMore text.\n").replace("\n", "\r\n")
    r = go(notes={"01-a.md": cur}, committed={"01-a.md": crlf}, base="HEAD")
    eq((r.f, r.rc), ([], 0), r.out)


# base and current are both compared WITHOUT their anchor lines (header and block anchors)
BASEH = NOTE(body="Some text.\n" + BL() + "\nMore text.\n")     # at REV: a header and one anchor


@case("Y1", "a base that already carries a header and an anchor, and a current note with one more anchor, are equal")
def _():
    cur = NOTE(body="Some text.\n" + BL() + "\nMore text.\n" + BL("01.b02") + "\n")
    r = go(notes={"01-a.md": cur}, committed={"01-a.md": BASEH}, base="HEAD")
    eq((r.f, r.rc), ([], 0), r.out)
    ok("byte check: 1 notes equal to HEAD, 0 new, 0 additions" in r.lines, r.out)
    r = go(notes={"01-a.md": BASEH}, committed={"01-a.md": BASEH}, base="HEAD")
    eq((r.f, r.rc), ([], 0), "unchanged")
    r = go(notes={"01-a.md": NOTE(body="Some text.\nMore text.\n")}, committed={"01-a.md": BASEH}, base="HEAD")
    eq((r.f, r.rc), ([], 0), "an anchor removed since REV is not a text change")


@case("Y2", "a base with no header and a current note that adds the header are equal")
def _():
    r = go(notes={"01-a.md": CUR}, committed={"01-a.md": T0}, base="HEAD")
    eq((r.f, r.rc), ([], 0), r.out)
    ok("byte check: 1 notes equal to HEAD, 0 new, 0 additions" in r.lines, r.out)


@case("Y3", "a base with header and anchor and a current note with one word of the body changed: BYTE-DIFF, the line counted without anchors")
def _():
    cur = NOTE(body="Some texts.\n" + BL() + "\nMore text.\n")
    r = go(notes={"01-a.md": cur}, committed={"01-a.md": BASEH}, base="HEAD")
    eq((r.f, r.rc), (["BYTE-DIFF 01-a.md:6 line 6 differs (line 5 of the text without anchors): at HEAD (without anchors) 'Some text.\\n', now (without anchors) 'Some texts.\\n'"], 1), r.out)
    ok("byte check: 0 notes equal to HEAD, 0 new, 0 additions" in r.lines, r.out)


@case("Y4", "an anchor-looking line inside a fence is text on both sides: it is compared, and a change to it is a BYTE-DIFF")
def _():
    fenced = lambda bid: NOTE(body="```text\n" + BL(bid) + "\n```\n")  # noqa: E731
    r = go(notes={"01-a.md": fenced("01.b09")}, committed={"01-a.md": fenced("01.b09")}, base="HEAD")
    eq((r.f, r.rc), ([], 0), "unchanged")
    r = go(notes={"01-a.md": fenced("01.b08")}, committed={"01-a.md": fenced("01.b09")}, base="HEAD")
    eq((r.f, r.rc), (["BYTE-DIFF 01-a.md:7 line 7 differs (line 6 of the text without anchors): at HEAD (without anchors) '<!-- rh-block {\"id\":\"01.b09\",\"kind\":\"reading\"} -->\\n', "
                      "now (without anchors) '<!-- rh-block {\"id\":\"01.b08\",\"kind\":\"reading\"} -->\\n'"], 1), r.out)


@case("Y5", "a base that is not UTF-8 is a BYTE-DIFF without a line (not a crash, not exit 2: the other notes are still compared)")
def _():
    bad = b"# Note\n\xff\n"
    r = go(notes={"01-a.md": CUR, "02-b.md": NOTE(nid="02")}, committed={"01-a.md": bad, "02-b.md": T0.replace("More text.\n", "")}, base="HEAD")
    eq((r.f, r.rc), (["BYTE-DIFF 01-a.md the note at HEAD is not valid UTF-8 and cannot be compared"], 1), r.out)
    ok("byte check: 1 notes equal to HEAD, 0 new, 0 additions" in r.lines, r.out)


@case("Y6", "CRLF notes and notes without a final newline strip the same way on both sides")
def _():
    crlf = lambda t: t.replace("\n", "\r\n")  # noqa: E731
    r = go(notes={"01-a.md": crlf(NOTE(body="Some text.\n" + BL() + "\nMore text.\n" + BL("01.b02") + "\n"))},
           committed={"01-a.md": crlf(BASEH)}, base="HEAD")
    eq((r.f, r.rc), ([], 0), "CRLF: " + r.out)
    nofinal = NOTE(body="Some text.\nMore text.\n" + BL())   # the last line is an anchor with no line ending
    two = NOTE(body="Some text.\nMore text.\n" + BL() + "\n" + BL("01.b02"))
    r = go(notes={"01-a.md": two}, committed={"01-a.md": nofinal}, base="HEAD")
    eq((r.f, r.rc), ([], 0), "anchor at the end, no final newline: " + r.out)
    plain = NOTE(body="Some text.\nMore text.")   # no final newline, no anchor
    r = go(notes={"01-a.md": plain + "\n" + BL()}, committed={"01-a.md": plain}, base="HEAD")
    eq((r.f, r.rc), ([], 0), "an anchor added after a last line with no newline: " + r.out)


@case("Z1", "a last anchor line with no line ending of its own also takes the line ending before it (rh_anchor's strip rule): the note reads as a one-line-ending "
            "difference; with a final newline after the anchor it is equal")
def _():
    base = NOTE(body="Text.\n")
    fe(go(notes={"01-a.md": NOTE(body="Text.\n" + BL())}, committed={"01-a.md": base}, base="HEAD"),
       ["BYTE-DIFF 01-a.md:6 line 6 differs (line 5 of the text without anchors): at HEAD (without anchors) 'Text.\\n', now (without anchors) 'Text.'"], 1)
    r = go(notes={"01-a.md": NOTE(body="Text.\n" + BL() + "\n")}, committed={"01-a.md": base}, base="HEAD")
    eq((r.f, r.rc), ([], 0), r.out)


def _z2(now_body):
    return go(notes={"01-a.md": NOTE(body=now_body)}, committed={"01-a.md": NOTE(body="Some text.\nMore text.\n")}, base="HEAD")


@case("Z2a", "a change confined to the last line, the line count the same, is a BYTE-DIFF at that line")
def _():
    fe(_z2("Some text.\nMore texts.\n"),
       ["BYTE-DIFF 01-a.md:7 line 7 differs (line 6 of the text without anchors): at HEAD (without anchors) 'More text.\\n', now (without anchors) 'More texts.\\n'"], 1)


@case("Z2b", "a trailing space on a line is a BYTE-DIFF")
def _():
    fe(_z2("Some text. \nMore text.\n"),
       ["BYTE-DIFF 01-a.md:6 line 6 differs (line 5 of the text without anchors): at HEAD (without anchors) 'Some text.\\n', now (without anchors) 'Some text. \\n'"], 1)


@case("Z2c", "a leading space on a line is a BYTE-DIFF")
def _():
    fe(_z2(" Some text.\nMore text.\n"),
       ["BYTE-DIFF 01-a.md:6 line 6 differs (line 5 of the text without anchors): at HEAD (without anchors) 'Some text.\\n', now (without anchors) ' Some text.\\n'"], 1)


@case("Z2d", "a change of letter case on a line is a BYTE-DIFF")
def _():
    fe(_z2("some text.\nMore text.\n"),
       ["BYTE-DIFF 01-a.md:6 line 6 differs (line 5 of the text without anchors): at HEAD (without anchors) 'Some text.\\n', now (without anchors) 'some text.\\n'"], 1)


# the number after the file name is the line in the file as it is on disk (anchor lines included); the stripped index is named too
def _bd(l, sidx, a, b):
    return f"BYTE-DIFF 01-a.md:{l} line {l} differs (line {sidx} of the text without anchors): at HEAD (without anchors) {a}, now (without anchors) {b}"


BASE3 = "# Note\n\n## Body\n\nFirst.\nSecond.\nThird.\n"   # at REV: no anchor lines; Third. is line 7


@case("BL1", "a changed line under the header and two blocks: the line is the stripped index plus 3")
def _():
    cur = NOTE(body="First.\n" + BL("01.b01") + "\nSecond.\n" + BL("01.b02") + "\nThirds.\n")
    fe(go(notes={"01-a.md": cur}, committed={"01-a.md": BASE3}, base="HEAD"), [_bd(10, 7, "'Third.\\n'", "'Thirds.\\n'")], 1)


@case("BL2", "a changed line before every anchor: the two numbers are equal and both are printed")
def _():
    cur = CUR.replace("# Note\n", "# Notes\n", 1)
    fe(go(notes={"01-a.md": cur}, committed={"01-a.md": T0}, base="HEAD"), [_bd(1, 1, "'# Note\\n'", "'# Notes\\n'")], 1)


@case("BL3", "a changed line between two blocks: only the header and the first block are above it (plus 2)")
def _():
    cur = NOTE(body="First.\n" + BL("01.b01") + "\nSeconds.\n" + BL("01.b02") + "\nThird.\n")
    fe(go(notes={"01-a.md": cur}, committed={"01-a.md": BASE3}, base="HEAD"), [_bd(8, 6, "'Second.\\n'", "'Seconds.\\n'")], 1)


@case("BL4", "the now side has no line (text missing): the line after the last non-anchor line of the current file, trailing anchors not shifting it; "
             "the now side has a line the base lacks (extra text): that line's own number, trailing anchors not shifting it")
def _():
    trailing = NOTE(body="Some text.\n" + BL() + "\n")
    fe(go(notes={"01-a.md": trailing}, committed={"01-a.md": T0}, base="HEAD"), [_bd(7, 6, "'More text.\\n'", "<no line>")], 1)
    two = NOTE(body="Some text.\n" + BL() + "\n" + BL("01.b02") + "\n")
    fe(go(notes={"01-a.md": two}, committed={"01-a.md": T0}, base="HEAD"), [_bd(7, 6, "'More text.\\n'", "<no line>")], 1)
    plain = NOTE(body="Some text.\n")
    fe(go(notes={"01-a.md": plain}, committed={"01-a.md": T0}, base="HEAD"), [_bd(7, 6, "'More text.\\n'", "<no line>")], 1)
    short = "# Note\n\n## Body\n\nSome text.\n"
    fe(go(notes={"01-a.md": CUR}, committed={"01-a.md": short}, base="HEAD"), [_bd(7, 6, "<no line>", "'More text.\\n'")], 1)
    extra = NOTE(body="Some text.\nMore text.\n" + BL() + "\n" + BL("01.b02") + "\n")
    fe(go(notes={"01-a.md": extra}, committed={"01-a.md": short}, base="HEAD"), [_bd(7, 6, "<no line>", "'More text.\\n'")], 1)


@case("BL5", "a malformed rh- line is text for the mapping: it is not counted as an anchor line")
def _():
    bad = "<!-- rh-block {bad} -->"
    base = "# Note\n\n## Body\n\nSome text.\n" + bad + "\nMore text.\n"
    cur = NOTE(body="Some text.\n" + bad + "\nMore texts.\n")
    fe(go(notes={"01-a.md": cur}, committed={"01-a.md": base}, base="HEAD"),
       ["MALFORMED 01-a.md:7 Line 7 starts an rh- comment that is not one complete `<!-- rh-note {...} -->` or "
        "`<!-- rh-block {...} -->` line with a JSON object.", _bd(8, 7, "'More text.\\n'", "'More texts.\\n'")], 1)


@case("BL6", "CRLF and a last line without an ending: only the number changes")
def _():
    cur = NOTE(body="Some texts.\n" + BL() + "\nMore text.\n").replace("\n", "\r\n")
    fe(go(notes={"01-a.md": cur}, committed={"01-a.md": T0.replace("\n", "\r\n")}, base="HEAD"),
       [_bd(6, 5, "'Some text.\\r\\n'", "'Some texts.\\r\\n'")], 1)
    fe(go(notes={"01-a.md": NOTE(body="Some text.\nMore texts.")}, committed={"01-a.md": "# Note\n\n## Body\n\nSome text.\nMore text."}, base="HEAD"),
       [_bd(7, 6, "'More text.'", "'More texts.'")], 1)


@case("BL7", "a current file with no non-anchor line (empty, or only a header and blocks) against a base with text: the number is 1")
def _():
    first = "BYTE-DIFF 01-a.md:1 line 1 differs (line 1 of the text without anchors): at HEAD (without anchors) '# Note\\n', now (without anchors) <no line>"
    r = go(notes={"01-a.md": ""}, committed={"01-a.md": T0}, base="HEAD")
    eq((r.f, r.rc), (["NO-HEADER 01-a.md has no rh-note header", first], 1), "empty file: " + r.out)
    hdr = rh.format_comment("rh-note", {"authors": ["H"], "group": "g1", "id": "01", "level": 2, "list_title": "A title",
                                        "readers": ["K"], "release": "rel-1"})
    r = go(notes={"01-a.md": hdr + "\n" + BL() + "\n"}, committed={"01-a.md": T0}, base="HEAD")
    eq((r.f, r.rc), (["ORPHAN-BLOCK 01-a.md:2 block '01.b01' anchors nothing: its target is of type 'none', "
                      "not a paragraph, table or lean block", first], 1), "only anchor lines: " + r.out)


@case("B1d", "a note not present at REV is NEW-NOTE (a listing, exit unchanged); without --base the summary says the byte check did not run")
def _():
    r = go(notes={"01-a.md": CUR, "02-b.md": NOTE(nid="02")}, committed={"01-a.md": T0}, base="HEAD")
    eq((r.f, r.rc), (["NEW-NOTE 02-b.md is not present at HEAD"], 0), r.out)
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
        G("c2", level=2, parent="g3", order=2, roots=[R("A.C", "baz")], claim=None, premises=["c1"]),
        G("d1", level=3, parent="c2", order=1, roots=[R("A.B", "bar")], claim=None, premises=[]),
        G("d2", level=4, parent="d1", order=1, roots=[R("A.B", "foo"), R("A.C", "baz")], claim=None, premises=["g3"]),
    ]


@case("REC1", "an outline or a strings file nested 100000 deep is unreadable input: exit 2, nothing on stdout, a notes_meta message, no traceback")
def _():
    deep = "[" * 100000 + "]" * 100000
    r = go(raw_outline=deep)
    eq((r.rc, r.out), (2, ""), "outline")
    ok(r.err.startswith("notes_meta: cannot read the outline: "), r.err)
    r = go(strings=deep)
    eq((r.rc, r.out), (2, ""), "strings")
    ok(r.err.startswith("notes_meta: cannot read the strings file: "), r.err)


@case("M5d", "the table half of M5 runs without --src: a file the note's table does not list is FILE-NOT-LISTED (with or without lines)")
def _():
    n = lambda **kw: {"01-a.md": NOTE(body="Some text.\n" + BL(file="A/Z.lean", **kw) + "\n" + FILES)}  # noqa: E731
    fe(go(notes=n(lines=[1, 2])), ["FILE-NOT-LISTED 01-a.md:7 block '01.b01' file A/Z.lean is not in the note's file table"], 1)
    fe(go(notes=n()), ["FILE-NOT-LISTED 01-a.md:7 block '01.b01' file A/Z.lean is not in the note's file table"], 1)
    clean(go(notes=_m5(lines=[12, 15])))
    clean(go(notes=_m5()))


@case("M5e", "a source file that is not UTF-8 is FILE-UNREADABLE; lines without a file are not checked for extent")
def _():
    fe(go(notes=_m5(lines=[1, 2]), src={"A/B.lean": b"\xff\xfe\n"}),
       ["FILE-UNREADABLE 01-a.md:7 block '01.b01' file A/B.lean under --src is not valid UTF-8"], 1)
    nofile = {"01-a.md": NOTE(body="Some text.\n" + BL(lines=[1, 2], decls=[R("A.B", "foo")]) + "\n" + FILES)}
    clean(go(notes=nofile))
    clean(go(notes=nofile, src={"A/B.lean": SRC40}))


@case("M5f", "a source file's lines are counted as an editor does: CRLF, lone CR, no final newline")
def _():
    for what, text in (("crlf", "x\r\n" * 40), ("lone cr", "x\r" * 40), ("no final newline", "x\n" * 39 + "x")):
        clean(go(notes=_m5(lines=[40, 40]), src={"A/B.lean": text}))
        fe(go(notes=_m5(lines=[41, 41]), src={"A/B.lean": text}),
           ["LINES-OUTSIDE-FILE 01-a.md:7 block '01.b01' lines [41, 41] but A/B.lean has 40 lines"], 1)


@case("DEFS1", "a block's defs_opened entries resolve like its decls: UNRESOLVED, AMBIGUOUS with the candidates; their lines are not order-checked")
def _():
    n = lambda d: {"01-a.md": NOTE(body="Some text.\n" + BL(defs_opened=d) + "\n")}  # noqa: E731
    bad = [{"module": "A.B", "name": "nope", "lines": [1, 2]}, {"module": "A.D", "name": "dup", "lines": [1, 2]}]
    fe(go(notes=n(bad)),
       ["UNRESOLVED 01-a.md:7 block '01.b01' defs_opened[0] A.B nope: no row in decls.tsv",
        "AMBIGUOUS 01-a.md:7 block '01.b01' defs_opened[1] A.D dup: 2 rows; candidates (first_line, last_line): (1, 3), (7, 9)"], 1)
    clean(go(notes=n([{"module": "A.C", "name": "baz", "lines": [9, 5]}])))
    clean(go(notes=n([])))


@case("ORPH1", "a block whose target is none or other (file start, after a heading, list item, quote, non-lean fence) is ORPHAN-BLOCK; "
               "after a paragraph, a table or a lean block it is fine")
def _():
    msg = "ORPHAN-BLOCK 01-a.md:%d block '01.b01' anchors nothing: its target is of type '%s', not a paragraph, table or lean block"
    fe(go(notes={"01-a.md": BL() + "\n" + NOTE()}), [msg % (1, "none")], 1)
    fe(go(notes={"01-a.md": NOTE(body=BL() + "\n")}), [msg % (6, "other")], 1)
    fe(go(notes={"01-a.md": NOTE(body="- item\n" + BL() + "\n")}),
       ["ITEM-REQUIRED 01-a.md:7 block '01.b01': a list needs 'item' (1-based, like 'row')"], 1)   # flipped: a list item is a list now
    fe(go(notes={"01-a.md": NOTE(body="<div>x</div>\n" + BL() + "\n")}), [msg % (7, "other")], 1)
    fe(go(notes={"01-a.md": NOTE(body="> quote\n" + BL() + "\n")}), [msg % (7, "other")], 1)
    fe(go(notes={"01-a.md": NOTE(body="```text\nx\n```\n" + BL() + "\n")}), [msg % (9, "other")], 1)
    clean(go(notes={"01-a.md": NOTE(body="Some text.\n" + BL() + "\n")}))
    clean(go(notes={"01-a.md": NOTE(body="| a |\n|---|\n| 1 |\n" + BL() + "\n")}))
    clean(go(notes={"01-a.md": NOTE(body="```lean\nx\n```\n" + BL() + "\n")}))


@case("F12c", "--strings with no phrase at all (empty lists for every kind, or an empty frames) says so in one line; exit unchanged; "
              "control: a table with phrases says nothing")
def _():
    line = "FRAME-NOTE skipped: no frame phrases were loaded from the strings file"
    for fr in ({"frames": {"argument": [], "interpretation": []}}, {"frames": {}}):
        r = go(notes={"01-a.md": NOTE(body="We think this works.\n" + ARG() + "\n")}, strings=fr)
        ok(line in r.lines, r.out)
        eq((r.f, r.rc), ([], 0), "no finding")
    ok(line not in go(strings=FR).lines, "phrases loaded: no notice")


@case("GIT1", "with the git program missing, a normal run is refused with exit 4 and a message that names this tool and git")
def _():
    saved = os.environ.get("PATH")
    out, err = io.StringIO(), io.StringIO()
    with tempfile.TemporaryDirectory() as d:
        os.environ["PATH"] = d
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = main([d, d, d])
        finally:
            os.environ["PATH"] = saved
    eq((rc, out.getvalue()), (4, ""), "exit and stdout")
    ok(err.getvalue().startswith("REFUSED: the self-test of notes_meta.py needs the git program, which was not found on PATH"), err.getvalue())


@case("ITEM1", "a block on a list must carry item; item above the number of top-level items is out of range; the last item is fine; "
               "nested items are not numbered")
def _():
    lst = "- a\n- b\n"
    n = lambda body, **kw: {"01-a.md": NOTE(body=body + BL(**kw) + "\n")}  # noqa: E731
    clean(go(notes=n(lst, item=1)))
    clean(go(notes=n(lst, item=2)))
    fe(go(notes=n(lst, item=3)), ["ITEM-OUT-OF-RANGE 01-a.md:8 block '01.b01' item 3 but the list has 2 top-level items"], 1)
    fe(go(notes=n(lst)), ["ITEM-REQUIRED 01-a.md:8 block '01.b01': a list needs 'item' (1-based, like 'row')"], 1)
    clean(go(notes=n("1. a\n2. b\n", item=2)))
    clean(go(notes=n("- a\n  - b\n", item=1)))
    fe(go(notes=n("- a\n  - b\n", item=2)), ["ITEM-OUT-OF-RANGE 01-a.md:8 block '01.b01' item 2 but the list has 1 top-level items"], 1)


@case("ITEM3", "a loose list is numbered across its blank lines: item 2 of a two-item loose list is fine, item 3 is out of range")
def _():
    n = lambda **kw: {"01-a.md": NOTE(body="- a\n\n- b\n" + BL(**kw) + "\n")}  # noqa: E731
    clean(go(notes=n(item=2)))
    fe(go(notes=n(item=3)), ["ITEM-OUT-OF-RANGE 01-a.md:9 block '01.b01' item 3 but the list has 2 top-level items"], 1)


@case("ITEM2", "item on a target that is not a list is NOT-A-LIST naming the type; a bad item value is ITEM-BAD-VALUE and nothing else on a list; "
               "item with row is a block problem")
def _():
    n = lambda body, **kw: {"01-a.md": NOTE(body=body + BL(**kw) + "\n")}  # noqa: E731
    fe(go(notes=n("Some text.\n", item=1)), ["NOT-A-LIST 01-a.md:7 block '01.b01' carries item but its target is of type 'paragraph', not a list"], 1)
    fe(go(notes=n("```lean\nx\n```\n", item=1)), ["NOT-A-LIST 01-a.md:9 block '01.b01' carries item but its target is of type 'lean', not a list"], 1)
    bad = "ITEM-BAD-VALUE 01-a.md:8 block '01.b01': item: must be an integer of 1 or more"
    for v in (0, -1, "1", True, 1.5):
        fe(go(notes=n("- a\n- b\n", item=v)), [bad], 1)
    fe(go(notes=n("| a |\n|---|\n| 1 |\n", item=1, row=1)),
       ["BLOCK-PROBLEM 01-a.md:9 block '01.b01': item: cannot be combined with row or col (a block anchors a list item or a table row)",
        "NOT-A-LIST 01-a.md:9 block '01.b01' carries item but its target is of type 'table', not a list"], 1)


@case("CONST2", "the refusal table of list shapes is empty by default")
def _():
    eq(REFUSED_LIST_SHAPES, (), "empty")


@case("LSH1", "a list whose shape has every key of a refused entry is LIST-SHAPE-REFUSED naming the shape; the same note with the empty table is clean")
def _():
    loose = {"01-a.md": NOTE(body="- a\n\n- b\n" + BL(item=1) + "\n")}
    ordered_loose = {"01-a.md": NOTE(body="1. a\n\n2. b\n" + BL(item=1) + "\n")}
    msg = "LIST-SHAPE-REFUSED 01-a.md:9 block '01.b01' anchors a list whose shape the renderer shows differently: "
    saved = globals()["REFUSED_LIST_SHAPES"]
    try:
        clean(go(notes=loose))
        globals()["REFUSED_LIST_SHAPES"] = (frozenset({"loose"}),)
        fe(go(notes=loose), [msg + "loose"], 1)
        fe(go(notes=ordered_loose), [msg + "loose"], 1)
        clean(go(notes={"01-a.md": NOTE(body="- a\n- b\n" + BL(item=1) + "\n")}))
        globals()["REFUSED_LIST_SHAPES"] = (frozenset({"loose", "ordered"}),)
        fe(go(notes=ordered_loose), [msg + "loose, ordered"], 1)
        clean(go(notes=loose))
        globals()["REFUSED_LIST_SHAPES"] = (frozenset({"loose", "last_nested"}),)
        clean(go(notes=loose))
    finally:
        globals()["REFUSED_LIST_SHAPES"] = saved
    clean(go(notes=loose))
    eq(REFUSED_LIST_SHAPES, (), "restored")


@case("N5a", "the outline summary line on the pilot-shape fixture, literal; every number counted")
def _():
    ok("outline: 7 groups, 3 claimed, 4 null, 8 roots resolved, 1 defs_opened resolved, 5 premise links" in go(outline=OL(*_real())).lines, "REAL1")


@case("N5b", "the outline summary line still prints, with the numbers of what resolved, when the outline has findings")
def _():
    d = [{"module": "A.C", "name": "baz", "lines": [5, 9]}, {"module": "A.B", "name": "nope", "lines": [1, 2]}]
    ol = OL(G("g1", roots=[R("A.B", "foo")], claim=dict(CLAIM, defs_opened=d)),
            G("g2", order=2, roots=[R("A.D", "dup"), R("A.C", "baz")], premises=["g1", "zz"]))
    r = go(outline=ol)
    eq(r.f, ["UNRESOLVED outline.json group 'g1' claim defs_opened[1] A.B nope: no row in decls.tsv",
             "BAD-PREMISE outline.json group 'g2': premise 'zz' is not a group id",
             "AMBIGUOUS outline.json group 'g2' roots[0] A.D dup: 2 rows; candidates (first_line, last_line): (1, 3), (7, 9)"], "findings")
    ok("outline: 2 groups, 1 claimed, 1 null, 2 roots resolved, 1 defs_opened resolved, 1 premise links" in r.lines, r.out)
    eq(r.rc, 1, "exit")


@case("N5c", "positive lines for the strings file and the byte check when they ran: phrases and kinds that hold one; notes equal and new")
def _():
    fr = {"frames": {"claim": ["From"], "argument": ["How this is proved, as", "Next"], "interpretation": []}}
    other = NOTE(nid="02", body="Other.\n")
    r = go(notes={"01-a.md": CUR, "02-b.md": other, "03-c.md": NOTE(nid="03")}, committed={"01-a.md": T0, "02-b.md": T0},
           base="HEAD", strings=fr)
    ok("strings: 3 frame phrases loaded for 2 kinds" in r.lines, r.out)
    ok("byte check: 1 notes equal to HEAD, 1 new, 0 additions" in r.lines, r.out)
    eq((r.rc, [x[:9] for x in r.f]), (1, ["BYTE-DIFF", "NEW-NOTE "]), "findings")
    ok(not any(x.startswith("FRAME-NOTE skipped") for x in r.lines), "no skip notice when phrases loaded")


@case("HROOT1", "a header's group may be root when its level is 0; a level-0 note may name a real group; an unknown group is still UNKNOWN-GROUP")
def _():
    clean(go(notes={"01-a.md": NOTE(group="root", level=0)}))
    clean(go(notes={"01-a.md": NOTE(group="g1", level=0)}))
    fe(go(notes={"01-a.md": NOTE(group="zz", level=0)}), ["UNKNOWN-GROUP 01-a.md:2 group 'zz' is not in the outline"], 1)
    fe(go(notes={"01-a.md": NOTE(group="zz", level=1)}), ["UNKNOWN-GROUP 01-a.md:2 group 'zz' is not in the outline"], 1)


@case("HROOT2", "group root with level 1 is an error naming the line and saying root is for level 0 only")
def _():
    fe(go(notes={"01-a.md": NOTE(group="root", level=1)}), ["GROUP-ROOT-LEVEL 01-a.md:2 group 'root' is for level 0 only (this note has level 1)"], 1)


@case("HROOT3", "group root with level 2 is the same error")
def _():
    fe(go(notes={"01-a.md": NOTE(group="root", level=2)}), ["GROUP-ROOT-LEVEL 01-a.md:2 group 'root' is for level 0 only (this note has level 2)"], 1)


@case("BAS1", "a claim may carry basis, exactly read or census; absent is clean")
def _():
    one = [R("A.B", "foo")]
    clean(go(outline=OL(G("g1", roots=one, claim=dict(CLAIM, basis="read")))))
    clean(go(outline=OL(G("g1", roots=one, claim=dict(CLAIM, basis="census")))))
    clean(go(outline=OL(G("g1", roots=one, claim=dict(CLAIM)))))


@case("BAS2", "any other basis value is BAD-VALUE naming the group and the type of the value, not the value")
def _():
    one = [R("A.B", "foo")]
    pre = "BAD-VALUE outline.json group 'g1' claim: basis must be 'read' or 'census' (the value is of type "
    for v, t in (("", "string"), ("Read", "string"), ("CENSUS", "string"), ("reading", "string"), (" read", "string"),
                 ("read ", "string"), ("read\n", "string"), (None, "null"), (["read"], "list"),
                 (1, "number"), (1.5, "number"), (True, "boolean"), ({"a": 1}, "object")):
        fe(go(outline=OL(G("g1", roots=one, claim=dict(CLAIM, basis=v)))), [pre + t + ")"], 1)


@case("BAS3", "REQUIRE_CLAIM_BASIS is False by default; when True a claim without basis is CLAIM-BASIS-MISSING naming the group and a null claim is not flagged")
def _():
    eq(REQUIRE_CLAIM_BASIS, False, "the default")
    one = [R("A.B", "foo")]
    nob = OL(G("g1", roots=one, claim=dict(CLAIM)), G("g2", order=2, roots=one, claim=None))
    withb = OL(G("g1", roots=one, claim=dict(CLAIM, basis="census")), G("g2", order=2, roots=one, claim=None))
    saved = globals()["REQUIRE_CLAIM_BASIS"]
    try:
        clean(go(outline=nob))
        globals()["REQUIRE_CLAIM_BASIS"] = True
        fe(go(outline=nob), ["CLAIM-BASIS-MISSING outline.json group 'g1' claim: no basis (read or census)"], 1)
        clean(go(outline=withb))
        fe(go(outline=OL(G("g1", roots=one, claim=dict(CLAIM, basis="x")))),
           ["BAD-VALUE outline.json group 'g1' claim: basis must be 'read' or 'census' (the value is of type string)"], 1)
    finally:
        globals()["REQUIRE_CLAIM_BASIS"] = saved
    clean(go(outline=nob))
    eq(REQUIRE_CLAIM_BASIS, False, "restored")


@case("BAS4", "basis is a claim key only: at group level it is still UNKNOWN-KEY, and another unknown claim key still fires beside it")
def _():
    one = [R("A.B", "foo")]
    fe(go(outline=OL(dict(G("g1", roots=one), basis="read"))), ["UNKNOWN-KEY outline.json group 'g1': unknown key 'basis'"], 1)
    fe(go(outline=OL(G("g1", roots=one, claim=dict(CLAIM, basis="read", notes="x")))),
       ["UNKNOWN-KEY outline.json group 'g1' claim: unknown key 'notes'"], 1)


@case("BAS5", "the summary line claim basis: R read, C census, M without, counted over non-null claims; a bad value counts as without")
def _():
    ok("claim basis: 0 read, 0 census, 3 without" in go(outline=OL(*_real())).lines, "the pilot-shape fixture, no basis")
    gs = _real()
    gs[0] = dict(gs[0], claim=dict(gs[0]["claim"], basis="read"))
    gs[1] = dict(gs[1], claim=dict(gs[1]["claim"], basis="census"))
    r = go(outline=OL(*gs))
    eq((r.f, r.rc), ([], 0), r.out)
    ok("claim basis: 1 read, 1 census, 1 without" in r.lines, r.out)
    gs[3] = dict(gs[3], claim=dict(gs[3]["claim"], basis="Read"))
    r = go(outline=OL(*gs))
    ok("claim basis: 1 read, 1 census, 1 without" in r.lines and len(r.f) == 1, r.out)
    ok("claim basis: 0 read, 0 census, 0 without" in go(outline=OL(G("g1"), G("g2", order=2))).lines, "null claims are not counted")


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


# ---- CLAIM-LIBRARY-WORD: a library-looking name outside backticks, in a claim text or a condition (a listing)
def _clw(text=None, conditions=None, gid="g1"):
    claim = dict(CLAIM, text="T" if text is None else text)
    if conditions is not None:
        claim["conditions"] = conditions
    return go(outline=OL(G(gid, claim=claim)))


def _clw_line(where, token, gid="g1"):
    return (f"CLAIM-LIBRARY-WORD outline.json group {gid!r} {where}: {token!r} looks like a library name outside backticks "
            "(write it in backticks, or in plain words)")


@case("CLW1", "a dotted token (Foo.bar, A.b_c.d) or a CamelCase token (getValue, HypSalt) in a claim text outside backticks is a "
              "CLAIM-LIBRARY-WORD listing naming the group and the token, in the order of the text, once per token; exit 0, and the "
              "last line counts them as warnings")
def _():
    r = _clw("Uses Foo.bar and getValue, then HypSalt and Foo.bar again, and A.b_c.d.")
    fe(r, [_clw_line("claim text", "Foo.bar"), _clw_line("claim text", "getValue"), _clw_line("claim text", "HypSalt"),
           _clw_line("claim text", "A.b_c.d")], 0)
    eq(r.lines[-1], "1 notes, 0 findings, 4 warnings", "count line")


@case("CLW2", "a `conditions` entry is read the same way and named by its index; the same token in two groups lists once per group")
def _():
    fe(_clw("Plain words.", ["Fine here.", "Needs Real.analysis to hold."]), [_clw_line("conditions[1]", "Real.analysis")], 0)
    r = go(outline=OL(G("g1", claim=dict(CLAIM, text="Uses Foo.bar")), G("g2", order=2, claim=dict(CLAIM, text="Uses Foo.bar"))))
    fe(r, [_clw_line("claim text", "Foo.bar", "g1"), _clw_line("claim text", "Foo.bar", "g2")], 0)


@case("CLW3", "a token inside a pair of single backticks on one line does not list; an unpaired backtick, a backtick pair that spans "
              "a line, and a token outside the span still do")
def _():
    clean(_clw("Uses `Foo.bar` and `getValue` and `HypSalt`.", ["Needs `Real.analysis`."]))
    fe(_clw("Uses `Foo.bar` and HypSalt."), [_clw_line("claim text", "HypSalt")], 0)
    fe(_clw("An unpaired `Foo.bar here."), [_clw_line("claim text", "Foo.bar")], 0)
    r = _clw("A pair over a line `getValue\nrest` ends.")
    fe(r, [_clw_line("claim text", "getValue")], 0)


@case("CLW4", "prose does not list: plain words and capitalised names, all-capital words, a number like 3.5, a sentence-final period "
              "(`end.`), a period then a space, a version like v1.2; control: the same text with Foo.bar added lists only that")
def _():
    clean(_clw("Every Riemann zero lies on the line. The value is 3.5 or 0.25, and RH holds at the end."))
    clean(_clw("A sentence ends. Another one ends.", ["It holds for v1.2 of the bound.", "A bound of 10.", "Value 2.5."]))
    fe(_clw("The end. Foo.bar is 3.5."), [_clw_line("claim text", "Foo.bar")], 0)


@case("CLW5", "the listing never changes the exit code: an error elsewhere still exits 1 beside it, and a listing alone exits 0; "
              "a null claim has nothing to list")
def _():
    r = go(outline=OL(G("g1", claim=dict(CLAIM, text="Uses Foo.bar")), G("g2", order=2, roots=[R("A.B", "nope")])))
    eq((r.rc, [x.split(" ")[0] for x in r.f]), (1, ["UNRESOLVED", "CLAIM-LIBRARY-WORD"]), "error and listing")
    eq(r.lines[-1], "1 notes, 1 findings, 1 warnings", "count line")
    clean(go(outline=OL(G("g1"))))


@case("CLW6", "doubled backticks are literal text, so a token inside them is outside a span and IS listed; so is a token next to a "
              "backtick pair that a neighbour backtick spoils (a backtick, then a span's opening backtick; a closing backtick followed by "
              "another); control: a real span beside them does not list")
def _():
    fe(_clw("A ``Foo.bar`` here."), [_clw_line("claim text", "Foo.bar")], 0)
    fe(_clw("A ``getValue`` here."), [_clw_line("claim text", "getValue")], 0)
    fe(_clw("Opens ``Foo.bar` x."), [_clw_line("claim text", "Foo.bar")], 0)
    fe(_clw("Closes x `Foo.bar`` y."), [_clw_line("claim text", "Foo.bar")], 0)
    clean(_clw("A `Foo.bar` and `getValue` here."))


@case("CLW7", "a span does not cross a line break of any kind: a token in a pair of backticks split by a line feed, a carriage return "
              "or both is outside a span and is listed")
def _():
    for br in ("\n", "\r", "\r\n"):
        fe(_clw("a `Foo.bar" + br + "baz` b"), [_clw_line("claim text", "Foo.bar")], 0)


@case("CLW8", "what the rule lists beside a name: `e.g.` is listed as 'e.g', McDonald is listed, and a name with a non-ASCII letter is "
              "listed as a fragment (naïveThing as 'veThing', GröbnerBasis as 'bnerBasis')")
def _():
    fe(_clw("Such as e.g. this."), [_clw_line("claim text", "e.g")], 0)
    fe(_clw("The McDonald bound."), [_clw_line("claim text", "McDonald")], 0)
    fe(_clw("The naïveThing bound."), [_clw_line("claim text", "veThing")], 0)
    fe(_clw("The GröbnerBasis bound."), [_clw_line("claim text", "bnerBasis")], 0)


# ---- F27: a dated pure insertion is an ADDITION (a listing), not a BYTE-DIFF
TODAY = "2026-11-24"
T2 = "# Note\n\n## Body\n\nFirst.\n\nSecond.\n"   # two paragraphs, no anchors; the body starts on line 6 of the file on disk


def _add(body, base=T0, today=TODAY, **hdr):
    return go(notes={"01-a.md": NOTE(body=body, **hdr)}, committed={"01-a.md": base}, base="HEAD", today=today)


def _bdt(l, sidx, a, b, extra=""):
    return _bd(l, sidx, a, b) + extra


@case("ADD1", "an insert-only dated addition at the end (a blank line, then a heading with a date): no finding, one ADDITION line, "
              "exit 0, counted in the warnings and in the byte-check summary; the base note is not 'equal' and not 'new'")
def _():
    r = _add("Some text.\nMore text.\n\n## 2026-11-22 Added\nNew words.\n")
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-22 Added"], 0), r.out)
    ok("byte check: 0 notes equal to HEAD, 0 new, 1 additions" in r.lines, r.out)
    eq(r.lines[-1], "1 notes, 0 findings, 1 warnings", "count line")


@case("ADD2", "the same insertion with the date removed from its heading is a BYTE-DIFF at the first line of the run (today's message)")
def _():
    r = _add("Some text.\nMore text.\n\n## Added\nNew words.\n")
    eq((r.f, r.rc), ([_bd(8, 7, "<no line>", "'\\n'")], 1), r.out)
    ok("byte check: 0 notes equal to HEAD, 0 new, 0 additions" in r.lines, r.out)


@case("ADD3", "an insertion plus one altered earlier line is a BYTE-DIFF naming the altered line, as before")
def _():
    r = _add("Some texts.\nMore text.\n\n## 2026-11-22 Added\nNew words.\n")
    eq((r.f, r.rc), ([_bd(6, 5, "'Some text.\\n'", "'Some texts.\\n'")], 1), r.out)


@case("ADD4", "two additions in one note: two ADDITION lines in file order, each with its own first line, count and heading; "
              "both count in the warnings and in `additions`")
def _():
    r = _add("Some text.\n\n## 2026-11-21 First add\nA.\nMore text.\n\n### 2026-11-22 Second add\nB.\n")
    eq((r.f, r.rc), (["ADDITION 01-a.md:7 3 lines, heading 2026-11-21 First add",
                      "ADDITION 01-a.md:11 3 lines, heading 2026-11-22 Second add"], 0), r.out)
    ok("byte check: 0 notes equal to HEAD, 0 new, 2 additions" in r.lines, r.out)
    eq(r.lines[-1], "1 notes, 0 findings, 2 warnings", "count line")


@case("ADD5", "an addition inside a fenced block of the published text is a BYTE-DIFF; control: the same addition after the closing "
              "fence is an ADDITION; an unclosed published fence swallows an addition too")
def _():
    base = "# Note\n\n## Body\n\n```text\nline a\nline b\n```\n"
    ins = NOTE(body="```text\nline a\n## 2026-11-22 Added\nline b\n```\n")
    r = go(notes={"01-a.md": ins}, committed={"01-a.md": base}, base="HEAD", today=TODAY)
    eq((r.f, r.rc), ([_bd(8, 7, "'line b\\n'", "'## 2026-11-22 Added\\n'")], 1), r.out)
    after = NOTE(body="```text\nline a\nline b\n```\n\n## 2026-11-22 Added\nX.\n")
    r = go(notes={"01-a.md": after}, committed={"01-a.md": base}, base="HEAD", today=TODAY)
    eq((r.f, r.rc), (["ADDITION 01-a.md:10 3 lines, heading 2026-11-22 Added"], 0), "after the fence: " + r.out)
    open_base = "# Note\n\n## Body\n\n```text\nline a\n"
    r = go(notes={"01-a.md": NOTE(body="```text\nline a\n## 2026-11-22 Added\n")}, committed={"01-a.md": open_base},
           base="HEAD", today=TODAY)
    eq(r.rc, 1, "unclosed fence: " + r.out)
    ok(not any(x.startswith("ADDITION") for x in r.f), "no ADDITION inside an unclosed fence: " + r.out)


@case("ADD6", "an addition between two paragraphs: the run begins with the heading itself (no blank line to skip), and the blank line "
              "after it is part of the run")
def _():
    r = _add("First.\n\n## 2026-11-22 Added\nExtra.\n\nSecond.\n", base=T2)
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-22 Added"], 0), r.out)


@case("ADD7", "the heading is the first line of the run after its LEADING blank lines only: several blank lines then a heading is "
              "legal and the run counts them; text then a heading (the heading is the SECOND line) is a BYTE-DIFF at the run's first line")
def _():
    r = _add("Some text.\nMore text.\n\n\n\n## 2026-11-22 Added\nX.\n")
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 5 lines, heading 2026-11-22 Added"], 0), r.out)
    r = _add("Some text.\nMore text.\n\nIntro.\n## 2026-11-22 Added\nX.\n")
    eq((r.f, r.rc), ([_bd(8, 7, "<no line>", "'\\n'")], 1), r.out)
    r = _add("Some text.\nMore text.\nIntro.\n## 2026-11-22 Added\n")
    eq((r.f, r.rc), ([_bd(8, 7, "<no line>", "'Intro.\\n'")], 1), "text first, no blank: " + r.out)


@case("ADD8", "the heading is 1 to 6 `#`, a space, then text with a date: levels 1, 2, 4 and 6 are accepted; seven `#`, no space after "
              "the marks, and indented are not headings (BYTE-DIFF)")
def _():
    for marks in ("#", "##", "####", "######"):
        r = _add("Some text.\nMore text.\n\n" + marks + " 2026-11-22 Added\nX.\n")
        eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-22 Added"], 0), marks + " " + r.out)
    for bad in ("####### 2026-11-22 Added", "##2026-11-22 Added", " ## 2026-11-22 Added", "2026-11-22 Added", "## "):
        r = _add("Some text.\nMore text.\n\n" + bad + "\nX.\n")
        eq((r.f, r.rc), ([_bd(8, 7, "<no line>", "'\\n'")], 1), repr(bad) + " " + r.out)


@case("ADD9", "the heading text of the listing has no `#` marks and no surrounding spaces; the date may sit anywhere in the heading")
def _():
    r = _add("Some text.\nMore text.\n\n##   Notes of 2026-11-22, a day later   \nX.\n")
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading Notes of 2026-11-22, a day later"], 0), r.out)


@case("ADD10", "the date must be a real calendar date: 2026-13-45, 2026-02-30 and 2026-00-10 are BYTE-DIFF (today's message, no suffix); "
               "a heading with an impossible date and later a real one is read by its first REAL date; 2028-02-29 is real")
def _():
    for bad in ("2026-13-45", "2026-02-30", "2026-00-10", "2026-11-31"):
        r = _add("Some text.\nMore text.\n\n## " + bad + " Added\nX.\n")
        eq((r.f, r.rc), ([_bd(8, 7, "<no line>", "'\\n'")], 1), bad + " " + r.out)
    r = _add("Some text.\nMore text.\n\n## 2026-13-45 then 2026-11-22\nX.\n")
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-13-45 then 2026-11-22"], 0), r.out)
    r = _add("Some text.\nMore text.\n\n## 2028-02-29 leap\nX.\n", today="2028-03-01")
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2028-02-29 leap"], 0), r.out)


@case("ADD11", "upper bound: a date later than --today is a BYTE-DIFF whose message names the date and the window (no lower bound "
               "when the release has no date); a date equal to --today is accepted")
def _():
    r = _add("Some text.\nMore text.\n\n## 2026-11-25 Added\nX.\n")
    eq((r.f, r.rc), ([_bdt(8, 7, "<no line>", "'\\n'",
                           "; the added heading's date 2026-11-25 is outside the window up to 2026-11-24 (no lower bound)")], 1), r.out)
    r = _add("Some text.\nMore text.\n\n## 2026-11-24 Added\nX.\n")
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-24 Added"], 0), "equal to today: " + r.out)


@case("ADD12", "lower bound: the date of the header's `release` when it is `rh-YYYY-MM-DD` and real; a date before it is a BYTE-DIFF "
               "naming the window, a date equal to it is accepted; the upper bound still applies")
def _():
    rel = dict(release="rh-2026-11-20")
    r = _add("Some text.\nMore text.\n\n## 2026-11-19 Added\nX.\n", **rel)
    eq((r.f, r.rc), ([_bdt(8, 7, "<no line>", "'\\n'",
                           "; the added heading's date 2026-11-19 is outside the window 2026-11-20 to 2026-11-24")], 1), r.out)
    r = _add("Some text.\nMore text.\n\n## 2026-11-20 Added\nX.\n", **rel)
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-20 Added"], 0), "equal to the release date: " + r.out)
    r = _add("Some text.\nMore text.\n\n## 2026-11-25 Added\nX.\n", **rel)
    eq((r.f, r.rc), ([_bdt(8, 7, "<no line>", "'\\n'",
                           "; the added heading's date 2026-11-25 is outside the window 2026-11-20 to 2026-11-24")], 1), r.out)


@case("ADD13", "a release that does not parse as rh-YYYY-MM-DD with a real date gives NO lower bound: a date far in the past is accepted "
               "for rel-1, rh-1, rh-2026-13-45, a prefix-only and a suffixed release")
def _():
    for rel in ("rel-1", "rh-1", "rh-2026-13-45", "x-rh-2026-11-20", "rh-2026-11-20-b", "RH-2026-11-20"):
        r = _add("Some text.\nMore text.\n\n## 2001-01-01 Added\nX.\n", release=rel)
        eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2001-01-01 Added"], 0), rel + " " + r.out)


@case("ADD14", "a CRLF note with an addition: CRLF endings are part of the line compare, the heading text and count carry no carriage return")
def _():
    crlf = T0.replace("\n", "\r\n")
    cur = NOTE(body="Some text.\nMore text.\n\n## 2026-11-22 Added\nNew words.\n").replace("\n", "\r\n")
    r = go(notes={"01-a.md": cur}, committed={"01-a.md": crlf}, base="HEAD", today=TODAY)
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-22 Added"], 0), r.out)
    r = go(notes={"01-a.md": cur.replace("Some text.\r\n", "Some text.\n", 1)}, committed={"01-a.md": crlf}, base="HEAD", today=TODAY)
    eq(r.rc, 1, "a line ending changed in a base line is not an addition: " + r.out)


@case("ADD15", "greedy alignment is pinned: a repeated base line takes its EARLIEST match, so an addition whose last line repeats a base "
               "line is a legal run when the repeat comes after the original, and the same words before it leave the original unmatched "
               "as a second run without a heading (BYTE-DIFF at that run)")
def _():
    r = _add("Some text.\nMore text.\n\n## 2026-11-22 Extra\nMore text.\n")
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-22 Extra"], 0), r.out)
    r = _add("Some text.\n\n## 2026-11-22 Extra\nMore text.\nMore text.\n")
    eq((r.f, r.rc), ([_bd(10, 9, "<no line>", "'More text.\\n'")], 1), r.out)


@case("ADD16", "one bad run makes the whole note BYTE-DIFF even beside a legal one, and no ADDITION line is printed for that note; "
               "the first bad run is the one named")
def _():
    r = _add("Some text.\n\n## 2026-11-21 Good\nA.\nMore text.\n\nNo heading here.\n")
    eq((r.f, r.rc), ([_bd(11, 10, "<no line>", "'\\n'")], 1), r.out)
    ok("byte check: 0 notes equal to HEAD, 0 new, 0 additions" in r.lines, r.out)


@case("ADD17", "removed or altered base lines are never additions: a deleted line beside a legal addition and a replaced line are "
               "BYTE-DIFF at the first positional difference, as before")
def _():
    r = _add("Some text.\n\n## 2026-11-22 Added\nX.\n")
    eq((r.f, r.rc), ([_bd(7, 6, "'More text.\\n'", "'\\n'")], 1), "deleted: " + r.out)
    r = _add("Some text.\nOther text.\n\n## 2026-11-22 Added\nX.\n")
    eq((r.f, r.rc), ([_bd(7, 6, "'More text.\\n'", "'Other text.\\n'")], 1), "replaced: " + r.out)


@case("ADD18", "the byte check runs per note: one note with an addition lists it, another with an altered line is BYTE-DIFF, exit 1; "
               "the counts say one finding and one warning")
def _():
    a = NOTE(body="Some text.\nMore text.\n\n## 2026-11-22 Added\nX.\n")
    b = NOTE(nid="02", group="g2", body="Some texts.\nMore text.\n")
    r = go(notes={"01-a.md": a, "02-b.md": b}, committed={"01-a.md": T0, "02-b.md": T0}, base="HEAD", today=TODAY)
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-22 Added",
                      "BYTE-DIFF 02-b.md:6 line 6 differs (line 5 of the text without anchors): at HEAD (without anchors) "
                      "'Some text.\\n', now (without anchors) 'Some texts.\\n'"], 1), r.out)
    eq(r.lines[-1], "2 notes, 1 findings, 1 warnings", "count line")
    ok("byte check: 0 notes equal to HEAD, 0 new, 1 additions" in r.lines, r.out)


@case("ADD19", "a note with an addition and another finding reports both: the other finding first (line order), then the ADDITION; "
               "the exit code is the other finding's")
def _():
    r = _add("Some text.\nMore text.\n\n## 2026-11-22 Added\nX.\n", level=3)
    eq((r.f, r.rc), (["HEADER-PROBLEM 01-a.md:2 level: must be 0, 1 or 2",
                      "ADDITION 01-a.md:8 3 lines, heading 2026-11-22 Added"], 1), r.out)
    eq(r.lines[-1], "1 notes, 1 findings, 1 warnings", "count line")


@case("ADD20", "anchor lines in the current file shift the line numbers of the listing and of a BYTE-DIFF, as for any difference: "
               "an addition after a block anchor is numbered on disk")
def _():
    cur = NOTE(body="Some text.\n" + BL() + "\nMore text.\n\n## 2026-11-22 Added\nX.\n")
    r = go(notes={"01-a.md": cur}, committed={"01-a.md": T0}, base="HEAD", today=TODAY)
    eq((r.f, r.rc), (["ADDITION 01-a.md:9 3 lines, heading 2026-11-22 Added"], 0), r.out)
    bad = NOTE(body="Some text.\n" + BL() + "\nMore text.\n\n## Added\nX.\n")
    r = go(notes={"01-a.md": bad}, committed={"01-a.md": T0}, base="HEAD", today=TODAY)
    eq((r.f, r.rc), ([_bd(9, 7, "<no line>", "'\\n'")], 1), r.out)


@case("ADD21", "--today: the clock's UTC date is the default (a far-future heading date is refused without --today, a past one "
               "accepted), a value that is not a real YYYY-MM-DD date is exit 2 with nothing on stdout, and the option parses once with a value")
def _():
    r = go(notes={"01-a.md": NOTE(body="Some text.\nMore text.\n\n## 2999-01-01 Added\nX.\n")}, committed={"01-a.md": T0}, base="HEAD")
    eq(r.rc, 1, "future: " + r.out)
    ok("is outside the window up to " in r.out and "2999-01-01" in r.out, r.out)
    r = go(notes={"01-a.md": NOTE(body="Some text.\nMore text.\n\n## 2001-01-01 Added\nX.\n")}, committed={"01-a.md": T0}, base="HEAD")
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2001-01-01 Added"], 0), "past: " + r.out)
    for bad in ("2026-13-45", "yesterday", "2026-1-1", ""):
        r = _add("Some text.\nMore text.\n\n## 2026-11-22 Added\nX.\n", today=bad)
        eq((r.rc, r.out), (2, ""), repr(bad))
        ok("--today" in r.err, r.err)
    eq(_parse(["a", "b", "c", "--today", "2026-11-24"]), (["a", "b", "c"], {"today": "2026-11-24"}), "parse")
    eq(_parse(["a", "b", "c", "--today", "2026-11-24", "--today", "2026-11-25"]), None, "twice")
    eq(_parse(["a", "b", "c", "--today"]), None, "no value")


@case("ADD22", "without --base nothing is compared: an addition-shaped note is not listed and the summary says the check did not run")
def _():
    r = go(notes={"01-a.md": NOTE(body="Some text.\nMore text.\n\n## 2026-11-22 Added\nX.\n")}, today=TODAY)
    eq((r.f, r.rc), ([], 0), r.out)
    ok("byte check: did not run, no --base given" in r.lines, r.out)


@case("ADD23", "a published note whose text BEGINS with a fenced block: a dated insertion right after the opening line (the base line "
               "before the run is the first line of the note) is inside the fence, so a BYTE-DIFF; control: the same insertion after "
               "the closing fence is an ADDITION")
def _():
    base = "```text\nline a\nline b\n```\n"
    hdr = rh.format_comment("rh-note", {"authors": ["H"], "group": "g1", "id": "01", "level": 2, "list_title": "A title",
                                        "readers": ["K"], "release": "rel-1"}) + "\n"
    r = go(notes={"01-a.md": hdr + "```text\n## 2026-11-22 Added\nline a\nline b\n```\n"}, committed={"01-a.md": base},
           base="HEAD", today=TODAY)
    ok("BYTE-DIFF 01-a.md:3 line 3 differs (line 2 of the text without anchors): at HEAD (without anchors) 'line a\\n', "
       "now (without anchors) '## 2026-11-22 Added\\n'" in r.lines, r.out)
    ok(not any(x.startswith("ADDITION") for x in r.lines), "no ADDITION inside the fence: " + r.out)
    eq(r.rc, 1, "exit code")
    r = go(notes={"01-a.md": hdr + "```text\nline a\nline b\n```\n\n## 2026-11-22 Added\nX.\n"}, committed={"01-a.md": base},
           base="HEAD", today=TODAY)
    ok("ADDITION 01-a.md:6 3 lines, heading 2026-11-22 Added" in r.lines, "after the fence: " + r.out)


@case("ORDER", "notes are checked in name order whatever the directory order; each note's findings come before its note line, "
               "in line order")
def _():
    bad = NOTE(level=3)
    r = go(notes={"02-b.md": bad.replace('"id":"01"', '"id":"02"'), "01-a.md": bad})
    eq(r.lines[:4], ["HEADER-PROBLEM 01-a.md:2 level: must be 0, 1 or 2", "note 01 header FAILED, blocks 0",
                     "HEADER-PROBLEM 02-b.md:2 level: must be 0, 1 or 2", "note 02 header FAILED, blocks 0"], "order")
    r = go(notes={"01-a.md": NOTE(level=3, body="Some text.\n<!-- rh-block {bad} -->\n")})
    eq([x.split(" ")[0] + " " + x.split(" ")[1] for x in r.f], ["HEADER-PROBLEM 01-a.md:2", "MALFORMED 01-a.md:7"], "by line")


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


_OPTIONS = {"--base": "base", "--repo": "repo", "--strings": "strings", "--src": "src", "--glob": "glob", "--today": "today"}
USAGE = ("usage: notes_meta.py NOTES_DIR OUTLINE DECLS_TSV [--base REV] [--repo DIR] [--strings PATH] [--src SRC_ROOT]\n"
         "                     [--glob PATTERN] [--today YYYY-MM-DD]\n"
         "       notes_meta.py --selftest")


def _parse(argv):
    """(positionals, options) or None for a usage error: three positionals, each option at most once with a value."""
    pos, opts, i = [], {}, 0
    while i < len(argv):
        a = argv[i]
        if a in _OPTIONS:
            if _OPTIONS[a] in opts or i + 1 >= len(argv):
                return None
            opts[_OPTIONS[a]] = argv[i + 1]
            i += 2
        elif a.startswith("--"):
            return None
        else:
            pos.append(a)
            i += 1
    return (pos, opts) if len(pos) == 3 else None


def main(argv=None, check=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--selftest"]:
        return selftest()
    parsed = _parse(argv)
    if parsed is None:
        print(USAGE, file=sys.stderr)
        return 2
    if check is None and shutil.which("git") is None:
        print("REFUSED: the self-test of notes_meta.py needs the git program, which was not found on PATH; no result reported",
              file=sys.stderr)
        return 4
    if (selftest_quiet if check is None else check)() != 0:
        print("REFUSED: selftest failed; no result reported", file=sys.stderr)
        return 4
    pos, opts = parsed
    return run(pos[0], pos[1], pos[2], **opts)


if __name__ == "__main__":
    sys.exit(main())
