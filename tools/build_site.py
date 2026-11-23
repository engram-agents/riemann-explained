#!/usr/bin/env python3
"""The site builder of the proof map: the zoom levels 0 and 1 as JSON, and one static page, from the notes, the outline and
the declaration table.

It reads the notes as text, runs no Lean and makes no network request. It refuses to build unless `notes_meta` passes on the
same inputs (its library function is called, not a subprocess; its listings do not block). Everything it writes goes under
OUT_DIR, and nothing is written, not even OUT_DIR, unless every check passed. The format of the note comments is read only
through `rh_anchor.py`, the check of the notes only through `notes_meta.py`, both loaded by file path from the folder of
this file.

Outputs under OUT_DIR (JSON: sorted keys, 1-space indent, LF, UTF-8, one final newline)
  level0.json   the level-1 steps of the chain in `order`, the facts counts, the notes about the whole (level 0), totals
  level1.json   the same steps, each with its child groups nested under it to any depth
  group/<id>.json  one per group: its roots, the blocks that anchor them, the open `not_read` items, the notes
  manifest.json sha256 of every other output file, the three commit ids, the release id and archive hash, the counts
  data.js       `window.RH_DATA = {...};` with level0, level1 and every group file (nothing reads it yet)
  index.html    ONE static page: plain semantic HTML, readable without JavaScript, no request of any kind
Every JSON file carries `commits`: {notes, release, tools} (B5). A group id is used verbatim as the anchor id of its card.
The group objects inside level0.json and level1.json (the steps and, in level1.json, their `children`) have: `claim`, which
is {text, reader, date, basis (read or census), conditions, premises (group ids)} or null; `lean_name`, the name of the first
root; `claim_label`, the strings file's `no_claim_label` when the claim is null; `statement_read` and `proof_read`, true when
EVERY root of the group has the fact; `unread`, true when no root has either fact; `counts`, {roots, roots_statement_read,
roots_proof_read, roots_open_items, open_items}; `notes`, a list of {note, list_title, link}. group/<id>.json has none of
`claim`, `counts`, `statement_read` and `proof_read`: it has `id`, `level`, `parent`, `roots`, `blocks`, `open_items`, `notes`
and `commits`, and each root of it has the booleans `statement_read` and `proof_read`. level0.json has `facts` ({steps,
statement_read, statement_not_read, proof_read, proof_not_read}, counted over the level-1 steps) and `totals`, which holds
`open_items`, the number of distinct open not_read blocks of the whole outline.

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
  X5 A group id that is not safe as a file name (letters, digits, `.`, `_`, `-`, not starting with `.`, at most 100
     characters; no two ids that differ only in case) is GROUP-ID-UNSAFE. Cases ID1 ID2 W1.
  X7 The build is written into a temporary sibling directory of OUT_DIR and renamed into place at the end: a failure before
     the rename leaves OUT_DIR absent (fresh run) or the old build and every other file in it untouched (--force), and no
     temporary directory behind. A failure to write (OSError) is exit 2 with ONE line, no traceback; a JSON too deep to
     write is exit 2 with the line `outline too deep to write`; the parent of OUT_DIR must exist. Cases W2 W3 W4 W5.
  X8 Two notes with the same header id are refused by the checker (notes_meta, NOTE-ID-DUPLICATE, one line naming every file),
     exit 1, nothing written; the builder has no rule of its own for it. Case DUP1.
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
  L2 A level-0 note (header level 0) is listed above the chain, under no step and in no group's list, and counted once in
     totals. Case U1.
  B5 Three commit ids in every JSON file: the notes commit (--notes-commit REV, else `unknown`), the release id (the
     outline's), the tools commit. A tree whose notes, outline, declaration table or strings differ from the commit, or
     whose tools differ from their commit, stamps `dirty` in all three, and the page says so in the first screen. Cases B5a
     B5b B5c B5d.
  B5x Per root TWO FACTS (F19): statement_read = the group carries a claim whose basis is `read` (a claim with no basis key
     counts as `read` until the checker requires one) or a reading block anchors the root; proof_read = an argument block
     anchors the root. Nothing else sets either: an interpretation, a correction, a not_read and a machine_fact block
     set neither, a claim with basis `census` does not set statement_read. Cases F1a F1b S1.
  F2 JSON: group/<id>.json per root `statement_read` and `proof_read` (booleans); level files per group `counts` {roots,
     roots_statement_read, roots_proof_read, roots_open_items, open_items} (no key of it holds `not_read`) and `claim.basis`
     (the effective value); `unread` = neither fact on any root; there is no `coverage` key. Case F2a.
  F3 There is no coverage word: a strings file that carries a `coverage` key, or a key whose name holds `not_read` other
     than statement_not_read_line and proof_not_read_line (not_read_yet, roots_not_read, roots_not_read_note), is refused
     naming the key (a stale file cannot ship a word scale); a value holding `Read by us`, `Partly read` or `Not read yet` is
     STRINGS-FORBIDDEN; the built page has none of the three. A stale `no_argument` is ignored and never printed.
     Cases F3a F3b.
  F4 The build asserts for each fact read + not read = total over the level-1 steps and over the roots of each group (a pure
     function, fact_pairs, counts them) and prints `facts check: statements read A + not read B = N steps; proofs read C +
     not read D = N steps`; a mismatch planted through the function's input is SUM-STATEMENT or SUM-PROOF, nothing written;
     a group with no root has no fact claim and is an error (FACTS-NO-ROOT), never counted as read. Cases R1a R1b.
  F9 The run prints the builder's own line `claim basis: R read, C census, M without (treated as read)` (without the
     parenthesis when M is 0), counted over the non-null claims of the outline, beside the checker's line of the same
     counts. Case BAS1.
 Page
  P1 The first screen comes from strings.json (`first_screen`), then the chain of level-1 steps in order. No sentence the
     reader sees is typed in code: a missing key is STRINGS-KEY naming it, and a build with every value a distinct
     marker shows only markers and data. Cases P1a P1b.
  P2 A card, open, in order: the claim (a bare declarative) or the null-claim heading, the conditions directly under it, the
     premises each a link to the premise's card, the statement line, the proof line, the open-items line, the idea (the first
     sentence of the argument inside its frame, when an argument block exists); all outside the closed section. Text from
     the data is escaped. Cases P2a P2b.
  P3 Evidence (Lean name, file, lines, hash, blocks, open items) is a closed `<details>` per card. A null claim shows the Lean
     name and the strings file's `no_claim_label` in the heading, then its status lines (H1). Case P3.
  C1 The two status lines come from the strings keys: statement_read_line ({reader} {date} of the claim, or of the first
     reading block of the root when the claim is null, or when its basis is census), statement_census_line ({reader} {date}
     of the claim; it does not count), statement_not_read_line; proof_read_line, proof_not_read_line. A group with several
     roots shows statement_count_line and proof_count_line ({n} {m}) instead. The line open_items_line ({n}) is always shown.
     Cases C1 C2 B7c.
  OI Open items are DISTINCT open not_read blocks, each once: the card's n counts the blocks anchored to its roots (a shared
     block counts on both cards), totals.open_items counts each once; counts.roots_open_items is the number of roots with at
     least one. Cases OI1 OI2 OI3.
  HR A reaction href template must be an https URL (STRINGS-KEY naming it otherwise); the hrefs (note_href and every reaction
     href) are exempt from the forbidden-word rule, every label and every other value is not. Cases HREF1 HREF2.
  P5 Three reaction links per card, plain anchors, href built from the strings template with the card id filled
     (URL-encoded). Case P5.
  P6 Every number on the page appears in the JSON or the strings file; the page computes no sum. number_problems. Case P6.
  P7 index.html and data.js hold none of fetch(, XMLHttpRequest, WebSocket, sendBeacon, import(, `src=`/`href=` to http(s)
     except in a reaction anchor, url(; the builder refuses (PAGE-STATIC) when one does. static_problems. Cases P7a P7b.
  R2 The first screen counts steps per fact with steps_statement_line and steps_proof_line ({n} {m}: a step is read for a fact
     when EVERY root of it has it; m is the number of level-1 steps) and the open blocks with steps_open_items_line ({n});
     a card of a group with several roots counts declarations with statement_count_line and proof_count_line; the page has
     no percent sign and no "of the proof". Case R2.
  R3 The builder's own sentences never contain a word of `forbidden_words` (and verified, explained, understood always),
     a percent sign or `of the proof` (the strings file is refused, STRINGS-FORBIDDEN naming the key; the href templates
     may hold `%`). Text from the notes and the outline (claims, conditions, note titles, argument and interpretation
     text) is only LISTED when it does: one line `WORD-NOTE <where> <word>` per text and word (`of the proof` stands for
     that phrase or a percent sign) on stdout, exit unchanged, the count in the `built:` line; the text is never edited.
     Cases R3a R3b WN1 WN2 WN3.
  H1 A group whose claim is null shows its root's Lean name and the strings file's `no_claim_label` in the heading (not a
     status), and its status lines tell the facts: a null claim whose root has a reading block says the statement is read.
     Case H1.
  E1 The premises of a card are linked in the order of the outline. Case ORD1.
  D1 Whatever data or strings reach the page is escaped there (text and attributes), and data.js writes `<`, `>`, `&`,
     U+2028 and U+2029 as \\uXXXX. Cases ESC1 JS1.
  G1 --release-archive-sha is stored in lower case; PAGE-STATIC names where the token came from; the frame of a block
     shows its lines with its file name (`lines_missing` for a block with no file or no lines). Cases SHA1 B7a B7f.
  R4 No CSS animation or transition keyword in the page; an unread card (neither fact on any root) is present, full size, outlined and labelled, never
     hidden or faded. Cases R4a R4b.
  R5 Every card says its counts are for the roots only (`roots_only_note`); a declaration that is a root of two groups is
     marked shared with the other group's id and counted once in totals. Case R5.
  R6 A `correction` block anchored to a root is shown on that root's card with kind, reader and date, outside the closed
     section. Case R6.
  B7 Every argument block is shown in ONE element with its frame first, drawn from strings.json plus the block's reader,
     date, lines and second readers; a step with an argument block shows its first sentence under the claim, a step
     without one the fixed sentence `no_argument`; an interpretation is shown apart in its own frame; every `#` link
     resolves to an id of the page (link_problems); a reading, argument, interpretation or correction block with no
     reader (BLOCK-NO-READER) or no date
     (BLOCK-NO-DATE) refuses the build. Cases B7a B7b B7c B7d B7e B7f.
  B1 --source-check SRC_ROOT: no output file holds a line of the release: stripped lines of at least 20 non-space
     characters of the release against the text lines of every output file (string values of the JSON except the
     name and id fields, text of the page except `<code>`). The run says what it ranged over. A planted shard that
     leaks a line is SOURCE-LEAK; an ids-only control stays green, on the page too. Cases B1a B1b B1c B1d B1e.
  K1 B1 is also run on the SOURCE lines of every copied note text BEFORE they are joined: each stripped line of at least 20
     non-space characters of a copied paragraph (the text of an argument or interpretation block that reaches an output)
     and of every note title is looked up in the release. A hit is SOURCE-LEAK naming the note and the block (or the
     field), never the line, exit 1, OUT_DIR absent. Without it a release line that stood on its own line of a paragraph
     is joined into a longer output line and is not seen. Cases PJ1 PJ2 PJ3 (a control builds in each).
  K2 The text values of the outline (claims, conditions) are checked line by line as well, split at newlines: a multi-line
     claim whose second line is a release line is a leak. Case PJ4.
  K3 The run says what the second check ranged over: a line `source check (copied note text): K copied source lines, L
     leaked; ...` with K counted by the tool (the non-empty source lines examined). Case PJ5.
  K4 The claim is narrow, and the run line, the LIMIT and the docs say so: no output line equals a release line and no
     line of copied note text equals one; a release line quoted INSIDE a longer sentence is not detected. A source line
     of fewer than 20 non-space characters is not compared. Case PJ6.

LIMIT. The page is a first draft of a real page: plain HTML, no script, no style beyond borders; the wording is the
strings file's, and the strings file's shape is PROVISIONAL (the table under `coverage` and every key named in this file
belong to whoever owns the wording; the fixtures of the self-test carry their own sentences, not the real ones). The
builder does not read a claim or a block and cannot say it is right; it copies no Lean text and no list item or table
cell text, and copies the first sentence and the paragraph of an `argument` or `interpretation` block whose target is a
paragraph, which are prose of the notes (an argument whose target is a list, table or lean block shows its frame and a link).
A first sentence is the text up to the first `.`, `!` or `?` followed by a space or the end. A reading block is the only
block that sets statement_read on a root without a claim; only an argument block sets proof_read. A level-0 note is under no group, and its
blocks feed no group. Coverage is for the roots only: members of a group that a root uses are not mapped, there is no
compiled data in this slice, and off-route marks (with their basis) are not built. B1 compares a release line with a
whole text line of an output file, and the source lines of the copied note text before they are joined (K1): a release
line quoted inside a longer sentence of the notes, or split across two lines, is not seen; the names and
ids that are excluded are the keys id, module, name, lean_name, file, note, block, parent, premises, sha256, link,
commits, files, release_id, release_archive_sha. P6's check is that each run of digits in the page text outside <code> appears among the digits
of the JSON (its hash fields left out) or the strings file: it cannot say the number is the right one. `dirty` is judged for the files of NOTES_DIR,
the outline and the strings file against the notes commit, and for tracked files of this folder against the tools
commit; an untracked file of the tools folder is not seen, and without --notes-commit the notes commit is `unknown` and
the notes are not judged. The sha256 of a root's file needs --source-check; a hash table in a note is not read. There is no
coverage word: the strings file's keys for the two facts are PROVISIONAL names (their wording is another seat's), the eleven
of them: statement_read_line, statement_census_line, statement_not_read_line, proof_read_line, proof_not_read_line,
statement_count_line, proof_count_line, open_items_line, steps_statement_line, steps_proof_line, steps_open_items_line;
`coverage`, `not_read_yet`, `route_count`, `no_argument`, `roots_read` and `roots_not_read` are gone. A claim whose basis is
missing is read as `read` until the checker requires it (the run line says how many). The page shows the claim's reader and
date in the statement line; for a null claim with a reading block the first reading block in note and block order. A claimed
group has one root, so the count lines appear only for null-claim groups. NOTE-ID-DUPLICATE belongs to the checker of the
notes; the builder has no rule of its own for it (the checker refuses first). WORD-NOTE reads the
claim, the conditions, the note titles and the text of argument and interpretation blocks, not the strings file's
hrefs; it lists, it does not judge. The block of an argument is framed with its lines and file name together; a block with
lines and no file shows `lines_missing`, because the lines name no file. The notes are the files NOTES_DIR matches by notes_meta's default pattern. The page's
note links are the strings file's `note_href` with the note's file name filled in.

usage: build_site.py NOTES_DIR OUTLINE DECLS_TSV STRINGS OUT_DIR [--source-check SRC_ROOT] [--release-archive-sha HEX]
                     [--notes-commit REV --repo DIR] [--force]
       build_site.py --selftest [--only ID,ID]
"""
import contextlib
import fnmatch
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

NAME_KEYS = frozenset(["id", "module", "name", "lean_name", "file", "note", "block", "parent", "premises", "sha256", "link",
                       "commits", "files", "release_id", "release_archive_sha"])


# ---------------------------------------------------------------- the tool

TEXT_KEYS = ("page_title", "mapped_line", "no_claim_label", "statement_read_line", "statement_census_line",
             "statement_not_read_line", "proof_read_line", "proof_not_read_line", "statement_count_line", "proof_count_line",
             "open_items_line", "steps_statement_line", "steps_proof_line", "steps_open_items_line", "argument_frame",
             "second_reader_frame", "interpretation_frame", "evidence_label", "roots_only_note", "dirty_note", "shared_note",
             "note_href")
PLACEHOLDERS = {"statement_read_line": {"reader", "date"}, "statement_census_line": {"reader", "date"},
                "statement_count_line": {"n", "m"}, "proof_count_line": {"n", "m"}, "open_items_line": {"n"},
                "steps_statement_line": {"n", "m"}, "steps_proof_line": {"n", "m"}, "steps_open_items_line": {"n"},
                "argument_frame": {"reader", "date", "lines"}, "second_reader_frame": {"reader", "date"},
                "interpretation_frame": {"reader", "date"}, "shared_note": {"groups"}, "note_href": {"file"}}
NOT_READ_KEYS = ("statement_not_read_line", "proof_not_read_line")   # the only keys whose name may hold `not_read`
RETIRED_WORDS = ("Read by us", "Partly read", "Not read yet")        # the coverage scale F19 removed
LABEL_KEYS = ("chain", "level0_notes", "premises", "notes", "go_deeper", "blocks", "open_items", "file", "lines", "sha256",
              "read_more", "lines_missing")
FROZEN_WORDS = ("verified", "explained", "understood")
READER_KINDS = ("reading", "argument", "interpretation", "correction")
SAFE_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*")
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_LINE_SPLIT = re.compile(r"\r\n|\n|\r")
_API = ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "import(", "@import")
_OUT_NAMES = ("level0.json", "level1.json", "manifest.json", "data.js", "index.html")


class _Unreadable(Exception):
    """An input that cannot be read: exit 2, the message goes to stderr, nothing to stdout."""


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _dump(obj):
    return json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False)


def _js_safe(text):
    """JSON text with `<`, `>`, `&`, U+2028 and U+2029 written as \\uXXXX (they occur only inside strings), like the comments."""
    for ch, esc in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        text = text.replace(ch, esc)
    return text


def _fill(template, **kw):
    """The template with each known {name} replaced in one pass; a name that is not given stays as written."""
    return _PLACEHOLDER.sub(lambda m: str(kw[m.group(1)]) if m.group(1) in kw else m.group(0), template)


def _first_sentence(text):
    m = re.match(r"(.+?[.!?])(?=\s|$)", text, re.S)
    return m.group(1) if m else text


def _nonspace(s):
    return len("".join(s.split()))


# ---- the coverage word

def fact_pairs(flags):
    """(how many flags are True, how many are False): anything else (None) is counted in neither, so a sum that does not add up
    to the total is visible."""
    return sum(1 for f in flags if f is True), sum(1 for f in flags if f is False)


def _fact_flags(items, key):
    """The flags of one fact over steps or over the root rows of a group."""
    return [x[key] for x in items]


# ---- the checks of the page

def static_problems(page, js):
    """What the page or data.js holds that could make a request: a sorted list of ids from fetch(, XMLHttpRequest, WebSocket,
    sendBeacon, import(, @import, src=http, href=http (a reaction anchor excepted), url( to a URL."""
    found = set()
    for text in (page, js):
        found.update(tok for tok in _API if tok in text)
        if re.search(r"url\(\s*['\"]?\s*(?:https?:)?//", text, re.I):
            found.add("url(")

    class P(html.parser.HTMLParser):
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            for k, v in attrs:
                if not isinstance(v, str) or not re.match(r"\s*(?:https?:)?//", v, re.I):
                    continue
                if k in ("src", "srcset", "poster"):
                    found.add("src=http")
                elif k in ("href", "action", "formaction", "xlink:href") and not (
                        tag == "a" and "reaction" in (a.get("class") or "").split()):
                    found.add("href=http")

    P(convert_charrefs=True).feed(page)
    return sorted(found)


def link_problems(page):
    """Every `#` link that has no element of that id on the page (as `#id`), then every id used twice (`duplicate id X`)."""
    ids, links = [], []

    class P(html.parser.HTMLParser):
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if a.get("id") is not None:
                ids.append(a["id"])
            h = a.get("href")
            if tag in ("a", "area") and isinstance(h, str) and h.startswith("#") and len(h) > 1:
                links.append(urllib.parse.unquote(h[1:]))

    P(convert_charrefs=True).feed(page)
    known = set(ids)
    out = ["#" + h for h in dict.fromkeys(links) if h not in known]
    out += ["duplicate id " + i for i in sorted({i for i in ids if ids.count(i) > 1})]
    return out


def _page_text(page, skip=("style", "script")):
    """The text nodes of the page outside the tags in `skip`, as one list of strings."""
    out, depth = [], {t: 0 for t in skip}

    class P(html.parser.HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag in depth:
                depth[tag] += 1

        def handle_endtag(self, tag):
            if tag in depth and depth[tag]:
                depth[tag] -= 1

        def handle_data(self, data):
            if not any(depth.values()):
                out.append(data)

    P(convert_charrefs=True).feed(page)
    return out


HASH_KEYS = frozenset(["sha256", "files", "release_archive_sha", "commits"])


def number_pool(objs):
    """The text whose runs of digits the numbers of the page may come from: the JSON of the build with the fields that hold
    hashes (hex digits) left out, so that a hash cannot vouch for a small number."""
    def strip(v):
        if isinstance(v, dict):
            return {k: strip(x) for k, x in v.items() if k not in HASH_KEYS}
        if isinstance(v, list):
            return [strip(x) for x in v]
        return v
    return "\n".join(json.dumps(strip(o), sort_keys=True, ensure_ascii=False) for o in objs)


def number_problems(page, json_text, strings_text):
    """The runs of digits in the text of the page (outside <code>, which holds names, ids and hashes) that are in neither the
    JSON nor the strings file."""
    allowed = set(re.findall(r"\d+", json_text)) | set(re.findall(r"\d+", strings_text))
    seen = set(re.findall(r"\d+", " ".join(_page_text(page, skip=("style", "script", "code")))))
    return sorted(seen - allowed, key=lambda d: (len(d), d))


# ---- B1: no release text

def _value_lines(obj):
    """Every line of every string value of a parsed JSON, except the values under a key of NAME_KEYS (names and ids)."""
    if isinstance(obj, str):
        yield from obj.split("\n")
    elif isinstance(obj, list):
        for x in obj:
            yield from _value_lines(x)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k not in NAME_KEYS:
                yield from _value_lines(v)


def _output_lines(rel, data):
    text = data.decode("utf-8")
    if rel.endswith(".json"):
        return list(_value_lines(json.loads(text)))
    if rel == "data.js":
        return list(_value_lines(json.loads(text[len("window.RH_DATA = "):-len(";\n")])))
    if rel.endswith(".html"):
        return [ln for chunk in _page_text(text, skip=("style", "script", "code")) for ln in chunk.split("\n")]
    return text.split("\n")


def leak_check(files, src_root, copied=None):
    """(the files that hold a line of the release, what was ranged over). `files` maps a relative path to bytes. A line counts
    when it has at least 20 non-space characters, compared stripped, as a whole line of a text of an output file (a string
    value of the JSON outside the name and id fields, a text node of the page outside <code>). `copied`, when given, is a list
    of (note id, what, source lines) for the note text that is copied into the outputs: its lines are compared as they stand in
    the note, before they are joined; the stats then also hold `copied_lines` (the non-empty source lines examined) and
    `copied_leaks` (the sorted (note id, what) that hold a line of the release). A release line quoted inside a longer line is
    not seen."""
    candidates, n_out = {}, 0
    copied_cand, n_copied = {}, 0
    for note, what, lines in copied or []:
        for ln in lines:
            t = ln.strip()
            if t:
                n_copied += 1
                if _nonspace(t) >= 20:
                    copied_cand.setdefault(t, set()).add((note, what))
    for rel in sorted(files):
        for ln in _output_lines(rel, files[rel]):
            s = ln.strip()
            if s:
                n_out += 1
                if _nonspace(s) >= 20:
                    candidates.setdefault(s, set()).add(rel)
    mods = sg.walk_lean(src_root)
    leaked, copied_leaked, n_lines, bad = set(), set(), 0, []
    for _module, path in mods:
        text, ok = sg.read_text(path)
        if not ok:
            bad.append(os.path.relpath(path, src_root).replace(os.sep, "/"))
            continue
        n_lines += text.count("\n") + (0 if text == "" or text.endswith("\n") else 1)
        for ln in text.split("\n"):
            s = ln.strip()
            if s in candidates:
                leaked.update(candidates[s])
            if s in copied_cand:
                copied_leaked.update(copied_cand[s])
    if bad:
        raise ValueError("cannot read: " + ", ".join(bad))
    stats = {"release_files": len(mods), "release_lines": n_lines, "output_files": len(files), "output_lines": n_out}
    if copied is not None:
        stats["copied_lines"] = n_copied
        stats["copied_leaks"] = sorted(copied_leaked)
    return sorted(leaked), stats


# ---- the strings file

def _walk_strings(v, path):
    if isinstance(v, str):
        yield path, v
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from _walk_strings(x, f"{path}[{i}]")
    elif isinstance(v, dict):
        for k, x in v.items():
            if not (path == "" and k == "forbidden_words"):
                yield from _walk_strings(x, f"{path}.{k}" if path else k)


def _strings_problems(s):
    """[(code, path, message)] for the strings file: every key the builder reads must be there with its shape; a word of the
    forbidden list (and verified, explained, understood) must not occur in any value."""
    out = []

    def bad(path, msg, code="STRINGS-KEY"):
        out.append((code, path, msg))

    def need_str(path, v):
        if not (isinstance(v, str) and v != ""):
            bad(path, "must be a non-empty string")
            return False
        return True

    def holders(path, v, allowed):
        for name in _PLACEHOLDER.findall(v):
            if name not in allowed:
                bad(path, "has an unknown placeholder {" + name + "}")

    if not isinstance(s, dict):
        return [("STRINGS-KEY", "(top level)", "must be a JSON object")]
    for k in TEXT_KEYS:
        if k not in s:
            bad(k, "missing")
        elif need_str(k, s[k]) and k in PLACEHOLDERS:
            holders(k, s[k], PLACEHOLDERS[k])
    for k in s:
        if k == "coverage":
            bad(k, "is retired: the strings file no longer carries a word scale")
        elif "not_read" in k and k not in NOT_READ_KEYS:
            bad(k, "is refused: only statement_not_read_line and proof_not_read_line may carry not_read in their name")
    if isinstance(s.get("labels"), dict):
        for k in s["labels"]:
            if "not_read" in k:
                bad(f"labels.{k}", "is refused: a label's name may not carry not_read")
    fs = s.get("first_screen", None)
    if "first_screen" not in s:
        bad("first_screen", "missing")
    elif not (isinstance(fs, list) and fs and all(isinstance(x, str) and x for x in fs)):
        bad("first_screen", "must be a non-empty list of non-empty strings")
    if "frames" not in s:
        bad("frames", "missing")
    elif not isinstance(s["frames"], dict):
        bad("frames", "must be an object")
    else:
        for k in ("argument", "interpretation", "claim"):
            if k not in s["frames"]:
                bad(f"frames.{k}", "missing")
            elif not (isinstance(s["frames"][k], list) and all(isinstance(x, str) for x in s["frames"][k])):
                bad(f"frames.{k}", "must be a list of strings")
    if "reactions" not in s:
        bad("reactions", "missing")
    elif not (isinstance(s["reactions"], list) and len(s["reactions"]) == 3):
        bad("reactions", "must be a list of three {label, href}")
    else:
        for i, r in enumerate(s["reactions"]):
            if not (isinstance(r, dict) and set(r) == {"label", "href"}):
                bad(f"reactions[{i}]", "must be an object with exactly the keys label and href")
                continue
            need_str(f"reactions[{i}].label", r["label"])
            if need_str(f"reactions[{i}].href", r["href"]):
                holders(f"reactions[{i}].href", r["href"], {"card"})
                if not r["href"].startswith("https://"):
                    bad(f"reactions[{i}].href", "must be an https URL")
    fw = s.get("forbidden_words")
    if "forbidden_words" not in s:
        bad("forbidden_words", "missing")
    elif not (isinstance(fw, list) and all(isinstance(x, str) and x for x in fw)):
        bad("forbidden_words", "must be a list of non-empty strings")
    if "labels" not in s:
        bad("labels", "missing")
    elif not isinstance(s["labels"], dict):
        bad("labels", "must be an object")
    else:
        lab = s["labels"]
        for k in LABEL_KEYS:
            if k not in lab:
                bad(f"labels.{k}", "missing")
            else:
                need_str(f"labels.{k}", lab[k])
        if "kinds" not in lab:
            bad("labels.kinds", "missing")
        elif not isinstance(lab["kinds"], dict):
            bad("labels.kinds", "must be an object")
        else:
            for k in rh.KINDS:
                if k not in lab["kinds"]:
                    bad(f"labels.kinds.{k}", "missing")
                else:
                    need_str(f"labels.kinds.{k}", lab["kinds"][k])
    words = list(FROZEN_WORDS) + [w for w in (fw if isinstance(fw, list) else []) if isinstance(w, str) and w]
    for path, v in _walk_strings(s, ""):
        if path == "note_href" or re.fullmatch(r"reactions\[\d+\]\.href", path):
            continue   # an address, not a sentence of the page
        for w in words:
            if re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", v, re.I):
                bad(path, f"holds the word {w!r}, which the page never says", "STRINGS-FORBIDDEN")
                break
        else:
            old = next((x for x in RETIRED_WORDS if re.search(r"(?<![A-Za-z])" + re.escape(x) + r"(?![A-Za-z])", v)), None)
            if old:
                bad(path, f"holds {old!r}, a word of the coverage scale that the page no longer has", "STRINGS-FORBIDDEN")
            elif "%" in v or re.search(r"of\s+the\s+proof", v, re.I):
                bad(path, "holds a percent sign or `of the proof`, which the page never says in its own sentences",
                    "STRINGS-FORBIDDEN")
    return out


# ---- commit ids

def _vcs(top, *args):
    try:
        return subprocess.run(["git", "-c", "safe.directory=*", "-C", top, *args], capture_output=True, text=True, timeout=60,
                              env=dict(os.environ, LC_ALL="C", LANG="C"))
    except (OSError, subprocess.SubprocessError):
        return None


def _tools_state():
    """(commit of the folder of this file or `unknown`, whether a tracked file of it differs from that commit)."""
    head = _vcs(_HERE, "rev-parse", "HEAD")
    if head is None or head.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40,64}", head.stdout.strip()):
        return "unknown", False
    st = _vcs(_HERE, "status", "--porcelain", "--untracked-files=no", "--", ".")
    return head.stdout.strip(), bool(st is None or st.returncode != 0 or st.stdout.strip())


def _notes_state(repo, rev, paths):
    """(the commit REV names, whether any of `paths` that lie in the repository differs from it or has untracked files)."""
    repo = repo if repo is not None else os.path.dirname(os.path.abspath(paths[0]))
    if not os.path.isdir(repo):
        raise _Unreadable(f"--repo is not a directory: {repo}")
    top = _vcs(repo, "rev-parse", "--show-toplevel")
    if top is None or top.returncode != 0:
        raise _Unreadable("--repo is not inside a git work tree (or git cannot be run)")
    top = os.path.realpath(top.stdout.strip())
    commit = _vcs(top, "rev-parse", "--verify", "--quiet", rev + "^{commit}")
    if commit.returncode != 0:
        raise _Unreadable(f"cannot resolve --notes-commit {rev} to a commit")
    rel = []
    for p in paths:
        r = os.path.relpath(os.path.realpath(p), top)
        if not r.startswith(".."):
            rel.append(r)
    if not rel:
        return commit.stdout.strip(), False
    st, df = _vcs(top, "status", "--porcelain", "--", *rel), _vcs(top, "diff", "--name-only", commit.stdout.strip(), "--", *rel)
    dirty = any(x is None or x.returncode != 0 or x.stdout.strip() for x in (st, df))
    return commit.stdout.strip(), dirty


# ---- the model: the outline, the notes and the table, joined

def _read_json(path, what):
    try:
        with open(path, "rb") as fh:
            return json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError, RecursionError) as e:
        raise _Unreadable(f"cannot read the {what}: {e}")


def _decl_rows(path):
    rows = {}
    with open(path, encoding="utf-8") as fh:
        for raw in fh.read().split("\n"):
            c = raw.rstrip("\r").split("\t")
            if len(c) == 6 and c != nm.DECL_COLS and not raw.startswith("#"):
                rows.setdefault((c[0], c[1]), (c[2], int(c[3]), int(c[4])))
    return rows


def _paragraph(lines, target):
    return " ".join(x.strip() for x in lines[target["first_line"] - 1:target["last_line"]])


def _load_notes(notes_dir, strings):
    """The notes in name order: id, title, level, group, link, and each block's record (its decls kept apart)."""
    notes = []
    for name in sorted(n for n in os.listdir(notes_dir) if fnmatch.fnmatchcase(n, nm.DEFAULT_GLOB)
                       and os.path.isfile(os.path.join(notes_dir, n))):
        with open(os.path.join(notes_dir, name), "rb") as fh:
            text = fh.read().decode("utf-8")
        headers, blocks, _bad = rh.parse_note(text)
        h = headers[0].data
        lines = _LINE_SPLIT.split(text)
        note = {"name": name, "id": h["id"], "title": h["list_title"], "level": h["level"], "group": h["group"],
                "link": _fill(strings["note_href"], file=urllib.parse.quote(name, safe="")), "blocks": []}
        for b in blocks:
            d, t = b.data, b.target or {}
            rec = {"block": d["id"], "kind": d["kind"], "note": h["id"], "reader": d.get("reader"), "date": d.get("date")}
            for k in ("item", "row", "col", "file", "lines", "needs", "second_readers"):
                if k in d:
                    rec[k] = d[k]
            if d["kind"] in ("argument", "interpretation"):
                para = _paragraph(lines, t) if t.get("type") == "paragraph" else None
                rec["text"] = para
                rec["first_sentence"] = _first_sentence(para) if para else None
                rec["_src"] = lines[t["first_line"] - 1:t["last_line"]] if para else None
            rec["_decls"] = [(e["module"], e["name"]) for e in d.get("decls", [])]
            note["blocks"].append(rec)
        notes.append(note)
    notes.sort(key=lambda n: (n["id"], n["name"]))
    return notes


def _block_key(rec):
    return rec["note"], int(rec["block"].rsplit(".b", 1)[1])


def _note_ref(n):
    return {"link": n["link"], "list_title": n["title"], "note": n["id"]}


class _Model:
    pass


def _model(notes_dir, odata, rows, strings, src_root, errors):
    m = _Model()
    m.release = odata["release"]
    m.notes = _load_notes(notes_dir, strings)
    groups = {}
    for g in odata["groups"]:
        groups.setdefault(g["id"], g)
    m.order = sorted(groups, key=lambda i: (groups[i]["level"], groups[i]["order"], i))
    children = {}
    for gid, g in groups.items():
        children.setdefault(g["parent"], []).append(gid)
    for k in children:
        children[k].sort(key=lambda i: groups[i]["order"])
    m.children, m.groups = children, groups
    anchored = {}
    for n in m.notes:
        if n["level"] != 0:
            for rec in n["blocks"]:
                for dm in rec["_decls"]:
                    anchored.setdefault(dm, []).append(rec)
    owners = {}
    for gid, g in groups.items():
        for r in g["roots"]:
            owners.setdefault((r["module"], r["name"]), []).append(gid)
    by_note = {n["id"]: n for n in m.notes}
    m.files, m.summary, m.copied, seen_blocks, open_blocks = {}, {}, [], set(), set()
    for gid, g in groups.items():
        roots = [(r["module"], r["name"]) for r in g["roots"]]
        blocks = {}
        for r in roots:
            for rec in anchored.get(r, []):
                blocks.setdefault(rec["block"], rec)
        brecs = []
        for rec in sorted(blocks.values(), key=_block_key):
            out = {k: v for k, v in rec.items() if k not in ("_decls", "_src")}
            if rec.get("_src") and rec["block"] not in seen_blocks:
                seen_blocks.add(rec["block"])
                m.copied.append((rec["note"], "block " + rec["block"], rec["_src"]))
            out["roots"] = [{"module": a, "name": b} for a, b in roots if (a, b) in rec["_decls"]]
            brecs.append(out)
        root_rows = []
        for mod, name in roots:
            kind, first, last = rows[(mod, name)]
            rel = mod.replace(".", "/") + ".lean"
            sha = None
            if src_root is not None and os.path.isfile(os.path.join(src_root, *rel.split("/"))):
                with open(os.path.join(src_root, *rel.split("/")), "rb") as fh:
                    sha = _sha(fh.read())
            root_rows.append({"module": mod, "name": name, "kind": kind, "file": rel, "lines": [first, last], "sha256": sha,
                              "shared_with": sorted(o for o in owners[(mod, name)] if o != gid)})
        claim = g["claim"]
        claim_read = claim is not None and claim.get("basis", "read") == "read"
        for row, r in zip(root_rows, roots):
            kinds = {x["kind"] for x in anchored.get(r, [])}
            row["statement_read"] = claim_read or "reading" in kinds
            row["proof_read"] = "argument" in kinds
        by = None
        if len(roots) == 1:   # one root: who read the statement (the claim, else the first reading block of the root)
            first = sorted((x for x in anchored.get(roots[0], []) if x["kind"] == "reading"), key=_block_key)
            if claim_read:
                by = {"source": "claim", "reader": claim["reader"], "date": claim["date"]}
            elif first:
                by = {"source": "block", "reader": first[0]["reader"], "date": first[0]["date"]}
            elif claim is not None:
                by = {"source": "census", "reader": claim["reader"], "date": claim["date"]}
        open_here = [b["block"] for b in brecs if b["kind"] == "not_read"]
        open_blocks.update(open_here)
        roots_open = sum(1 for r in roots if any(x["kind"] == "not_read" for x in anchored.get(r, [])))
        ids = {n["id"] for n in m.notes if n["level"] != 0 and n["group"] == gid} | {b["note"] for b in brecs}
        notes = [_note_ref(by_note[i]) for i in sorted(ids)]
        if not roots:
            errors.append(("FACTS-NO-ROOT", gid, "group has no root, so no fact claim"))
        m.summary[gid] = {
            "id": gid, "level": g["level"], "order": g["order"], "parent": g["parent"],
            "claim": None if claim is None else {"text": claim["text"], "reader": claim["reader"], "date": claim["date"],
                                                 "basis": claim.get("basis", "read"), "conditions": claim.get("conditions", []),
                                                 "premises": list(g["premises"])},
            "lean_name": g["roots"][0]["name"] if roots else None,
            "claim_label": strings["no_claim_label"] if claim is None else None,
            "statement_read": bool(roots) and all(r["statement_read"] for r in root_rows),
            "proof_read": bool(roots) and all(r["proof_read"] for r in root_rows),
            "statement_by": by,
            "unread": not any(r["statement_read"] or r["proof_read"] for r in root_rows),
            "counts": {"roots": len(roots), "roots_statement_read": sum(1 for r in root_rows if r["statement_read"]),
                       "roots_proof_read": sum(1 for r in root_rows if r["proof_read"]), "roots_open_items": roots_open,
                       "open_items": len(open_here)},
            "notes": notes, "roots_only": True}
        m.files[gid] = {"id": gid, "level": g["level"], "parent": g["parent"], "roots": root_rows, "blocks": brecs,
                        "open_items": [{"block": b["block"], "needs": b["needs"], "note": b["note"], "roots": b["roots"]}
                                       for b in brecs if b["kind"] == "not_read"], "notes": notes}
    m.steps = [i for i in children.get("root", [])]
    m.header_notes = [_note_ref(n) for n in m.notes if n["level"] == 0]
    m.totals = {"blocks": sum(len(n["blocks"]) for n in m.notes), "groups": len(groups), "notes": len(m.notes),
                "open_items": len(open_blocks), "roots": len(owners)}
    return m


# `of the proof` after a number, a percent sign or a quantity word (the word list is PROVISIONAL; its owner rules it)
_FRACTION = re.compile(r"(?:\d+(?:\.\d+)?\s*%\s*|\d+(?:\.\d+)?\s+|%\s*|\b(?:half|third|quarter|most|part|fraction|portion|share|"
                       r"majority|all)\s+)of\s+the\s+proof", re.I)


def _word_notes(m, s):
    """[(where, word)]: the forbidden words, and `of the proof` (a phrase or a percent sign), in the text of the claims, the
    conditions, the note titles and the argument and interpretation blocks. Only a listing."""
    words = list(dict.fromkeys(list(FROZEN_WORDS) + [w for w in s["forbidden_words"] if w]))

    def hits(text):
        out = [w for w in words if re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", text, re.I)]
        if _FRACTION.search(text):
            out.append("of the proof")
        elif "%" in text:
            out.append("%")
        return out

    found = []
    for gid in sorted(m.groups):
        claim = m.groups[gid]["claim"]
        if claim:
            found += [(f"{gid}.claim", w) for w in hits(claim["text"])]
            for i, c in enumerate(claim.get("conditions", [])):
                found += [(f"{gid}.conditions[{i}]", w) for w in hits(c)]
    for n in m.notes:
        found += [(f"note:{n['id']}.list_title", w) for w in hits(n["title"])]
        for b in n["blocks"]:
            if b.get("text"):
                found += [(f"block:{b['block']}.text", w) for w in hits(b["text"])]
    return found


def _nest(m, gid):
    out = dict(m.summary[gid])
    out["children"] = [_nest(m, c) for c in m.children.get(gid, [])]
    return out


# ---- the page

CSS = ("body { max-width: 50rem; margin: 1rem auto; padding: 0 1rem; font-family: serif; line-height: 1.45; }\n"
       ".card { border: 2px solid; padding: 0.5rem 0.75rem; margin: 0.75rem 0; }\n"
       ".unread { border-style: dashed; }\n"
       ".frame { font-style: italic; }\n"
       "ul.chain, ul.children { list-style: none; padding-left: 0; }\n"
       "aside { border-left: 4px double; padding-left: 0.5rem; }")


def _e(x):
    return html.escape(str(x), quote=True)


def _render_page(m, s, facts, dirty):
    lab, kinds = s["labels"], s["labels"]["kinds"]
    files = m.files
    out = ["<!DOCTYPE html>", '<html lang="en">', "<head>", '<meta charset="utf-8">', f"<title>{_e(s['page_title'])}</title>",
           "<style>", CSS, "</style>", "</head>", "<body>", "<header>", f"<h1>{_e(s['page_title'])}</h1>"]
    out += [f"<p>{_e(x)}</p>" for x in s["first_screen"]]
    if dirty:
        out.append(f'<p class="dirty">{_e(s["dirty_note"])}</p>')
    out += ['<ul class="facts">',
            f"<li>{_e(_fill(s['steps_statement_line'], n=facts['statement_read'], m=facts['steps']))}</li>",
            f"<li>{_e(_fill(s['steps_proof_line'], n=facts['proof_read'], m=facts['steps']))}</li>",
            f"<li>{_e(_fill(s['steps_open_items_line'], n=m.totals['open_items']))}</li>", "</ul>",
            f'<p class="mapped">{_e(s["mapped_line"])}</p>']
    if m.header_notes:
        out += ['<section class="whole">', f"<h2>{_e(lab['level0_notes'])}</h2>", "<ul>"]
        out += [f'<li><a href="{_e(n["link"])}">{_e(n["list_title"])}</a></li>' for n in m.header_notes]
        out += ["</ul>", "</section>"]
    out += ["</header>", "<main>", f"<h2>{_e(lab['chain'])}</h2>", '<ul class="chain">']

    def frames(b):
        lines = f"{b['file']} {b['lines'][0]}-{b['lines'][1]}" if b.get("lines") and b.get("file") else lab["lines_missing"]
        first = _fill(s["argument_frame"], reader=b["reader"], date=b["date"], lines=lines)
        more = [_fill(s["second_reader_frame"], reader=r["reader"], date=r["date"]) for r in b.get("second_readers", [])]
        return f'<span class="frame">{_e(first)}</span>' + "".join(f' <span class="frame second">{_e(x)}</span>' for x in more)

    def title_of(gid):
        sm = m.summary[gid]
        return _e(sm["claim"]["text"]) if sm["claim"] else f"<code>{_e(sm['lean_name'])}</code>"

    def card(gid):
        sm, fl = m.summary[gid], files[gid]
        o = [f'<article class="card{" unread" if sm["unread"] else ""}" id="{_e(gid)}">']
        if sm["claim"]:
            o.append(f'<h3 class="claim">{_e(sm["claim"]["text"])}</h3>')
            if sm["claim"]["conditions"]:
                o.append('<ul class="conditions">' + "".join(f"<li>{_e(c)}</li>" for c in sm["claim"]["conditions"]) + "</ul>")
            if sm["claim"]["premises"]:
                links = ", ".join(f'<a href="#{_e(urllib.parse.quote(p, safe=""))}">{title_of(p)}</a>'
                                  for p in sm["claim"]["premises"])
                o.append(f'<p class="premises">{_e(lab["premises"])} {links}</p>')
        else:
            o.append(f'<h3 class="claim unread-claim"><code>{_e(sm["lean_name"])}</code> '
                     f'<span class="label">{_e(sm["claim_label"])}</span></h3>')
        c, by = sm["counts"], sm["statement_by"]
        if c["roots"] > 1:   # several roots (a null claim): counts with their denominators
            st = _fill(s["statement_count_line"], n=c["roots_statement_read"], m=c["roots"])
            pf = _fill(s["proof_count_line"], n=c["roots_proof_read"], m=c["roots"])
        else:
            if sm["statement_read"]:
                st = _fill(s["statement_read_line"], reader=by["reader"], date=by["date"])
            elif by and by["source"] == "census":
                st = _fill(s["statement_census_line"], reader=by["reader"], date=by["date"])
            else:
                st = s["statement_not_read_line"]
            pf = s["proof_read_line"] if sm["proof_read"] else s["proof_not_read_line"]
        o.append(f'<p class="status statement">{_e(st)}</p>')
        o.append(f'<p class="status proof">{_e(pf)}</p>')
        o.append(f'<p class="open-items">{_e(_fill(s["open_items_line"], n=c["open_items"]))}</p>')
        if sm["roots_only"]:
            o.append(f'<p class="roots-only">{_e(s["roots_only_note"])}</p>')
        args = [b for b in fl["blocks"] if b["kind"] == "argument"]
        if args:
            b = args[0]
            link = next(n["link"] for n in sm["notes"] if n["note"] == b["note"])
            sent = f" {_e(b['first_sentence'])}" if b.get("first_sentence") else ""
            o.append(f'<p class="argument">{frames(b)}{sent} <a href="{_e(link)}">{_e(lab["read_more"])}</a></p>')
        corr = [b for b in fl["blocks"] if b["kind"] == "correction"]
        if corr:
            o.append('<ul class="corrections">')
            for b in corr:
                n = next(n for n in sm["notes"] if n["note"] == b["note"])
                o.append(f'<li><span class="kind">{_e(kinds["correction"])}</span> <span class="reader">{_e(b["reader"])}</span> '
                         f'<time>{_e(b["date"])}</time> <a href="{_e(n["link"])}">{_e(n["list_title"])}</a></li>')
            o.append("</ul>")
        if sm["notes"]:
            o.append(f'<p class="notes">{_e(lab["notes"])}</p><ul class="notes">'
                     + "".join(f'<li><a href="{_e(n["link"])}">{_e(n["list_title"])}</a></li>' for n in sm["notes"]) + "</ul>")
        o.append('<ul class="reactions">')
        for r in s["reactions"]:
            href = _fill(r["href"], card=urllib.parse.quote(gid, safe=""))
            o.append(f'<li><a class="reaction" href="{_e(href)}">{_e(r["label"])}</a></li>')
        o.append("</ul>")
        o += ['<details class="evidence">', f"<summary>{_e(s['evidence_label'])}</summary>"]
        for r in fl["roots"]:
            o.append(f'<div class="root"><p><code>{_e(r["module"])}</code> <code>{_e(r["name"])}</code> '
                     f'<span class="kind">{_e(r["kind"])}</span></p>')
            o.append(f'<dl><dt>{_e(lab["file"])}</dt><dd><code>{_e(r["file"])}</code></dd>'
                     f'<dt>{_e(lab["lines"])}</dt><dd>{r["lines"][0]}-{r["lines"][1]}</dd>'
                     + (f'<dt>{_e(lab["sha256"])}</dt><dd><code>{r["sha256"]}</code></dd>' if r["sha256"] else "") + "</dl>")
            if r["shared_with"]:
                o.append(f'<p class="shared">{_e(_fill(s["shared_note"], groups=", ".join(r["shared_with"])))}</p>')
            o.append("</div>")
        if fl["blocks"]:
            o += [f'<p class="label">{_e(lab["blocks"])}</p>', '<ul class="blocks">']
            for b in fl["blocks"]:
                n = next(n for n in sm["notes"] if n["note"] == b["note"])
                who = " ".join(_e(x) for x in (b.get("reader"), b.get("date")) if x)
                o.append(f'<li><a href="{_e(n["link"])}"><code>{_e(b["note"])}</code></a> <code>{_e(b["block"])}</code> '
                         f'<span class="kind">{_e(kinds[b["kind"]])}</span> {who}')
                if b["kind"] == "argument" and b.get("text"):
                    o.append(f'<p class="argument">{frames(b)} {_e(b["text"])}</p>')
                if b["kind"] == "interpretation" and b.get("text"):
                    fr = _fill(s["interpretation_frame"], reader=b["reader"], date=b["date"])
                    o.append(f'<aside><p class="interpretation"><span class="frame">{_e(fr)}</span> {_e(b["text"])}</p></aside>')
                o.append("</li>")
            o.append("</ul>")
        if fl["open_items"]:
            o += [f'<p class="label">{_e(lab["open_items"])}</p>', '<ul class="open">']
            for it in fl["open_items"]:
                o.append(f'<li><code>{_e(it["note"])}</code> <code>{_e(it["block"])}</code> <code>{_e(it["needs"])}</code></li>')
            o.append("</ul>")
        o.append("</details>")
        kids = m.children.get(gid, [])
        if kids:
            o += ['<details class="children">', f"<summary>{_e(lab['go_deeper'])}</summary>", '<ul class="children">']
            for k in kids:
                o += ["<li>"] + card(k) + ["</li>"]
            o += ["</ul>", "</details>"]
        o.append("</article>")
        return o

    for gid in m.steps:
        out += ["<li>"] + card(gid) + ["</li>"]
    out += ["</ul>", "</main>", "</body>", "</html>"]
    return "\n".join(out) + "\n"


# ---- the build

def _json_strings(v, path=""):
    if isinstance(v, str):
        yield path, v
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from _json_strings(x, f"{path}[{i}]")
    elif isinstance(v, dict):
        for k, x in v.items():
            yield from _json_strings(x, f"{path}.{k}" if path else k)


def _origin(token, sj, level0, level1, groups):
    """Where a token that PAGE-STATIC found came from: a strings key, a group and field, a level file; else the two files."""
    needles = {"src=http": ("http://", "https://", "//"), "href=http": ("http://", "https://", "//"), "url(": ("url(",)}
    needles = needles.get(token, (token,))
    for path, v in _walk_strings(sj, ""):
        if any(n in v for n in needles):
            return f"strings key {path}"
    for gid in sorted(groups):
        for path, v in _json_strings({k: x for k, x in groups[gid].items() if k != "commits"}):
            if any(n in v for n in needles):
                return f"group {gid} field {path}"
    for name, obj in (("level0", level0), ("level1", level1)):
        for path, v in _json_strings({k: x for k, x in obj.items() if k != "commits"}):
            if any(n in v for n in needles):
                return f"{name} field {path}"
    return "index.html or data.js"


def _refuse(lines, code=1):
    for code_, where, msg in lines:
        print(f"BUILD-ERROR {code_} {where} {msg}")
    print("REFUSED: nothing written", file=sys.stderr)
    return code


def _assemble(m, s, commits):
    """(errors, the facts check line, level0, level1, the group files, the facts over the steps)."""
    errors = []
    steps = [m.summary[i] for i in m.steps]
    pairs = {}
    for fact, code in (("statement_read", "SUM-STATEMENT"), ("proof_read", "SUM-PROOF")):
        a, b = fact_pairs(_fact_flags(steps, fact))
        pairs[fact] = (a, b)
        if a + b != len(steps):
            errors.append((code, "steps:", f"read {a} + not read {b} = {a + b}, but there are {len(steps)} steps"))
    for gid in sorted(m.groups):
        rows = m.files[gid]["roots"]
        for fact, code in (("statement_read", "SUM-STATEMENT"), ("proof_read", "SUM-PROOF")):
            a, b = fact_pairs(_fact_flags(rows, fact))
            if a + b != len(rows):
                errors.append((code, f"group {gid} roots:", f"read {a} + not read {b} = {a + b}, but there are {len(rows)} roots"))
    (sa, sb), (pa, pb) = pairs["statement_read"], pairs["proof_read"]
    line = f"statements read {sa} + not read {sb} = {sa + sb} steps; proofs read {pa} + not read {pb} = {pa + pb} steps"
    facts = {"steps": len(steps), "statement_read": sa, "statement_not_read": sb, "proof_read": pa, "proof_not_read": pb}
    level0 = {"commits": commits, "header_notes": m.header_notes, "level": 0, "facts": facts, "steps": steps,
              "totals": m.totals}
    level1 = {"commits": commits, "level": 1, "steps": [_nest(m, i) for i in m.steps]}
    groups = {gid: dict(m.files[gid], commits=commits) for gid in m.groups}
    return errors, line, level0, level1, groups, facts


def _output_files(level0, level1, groups, page, commits, m, release_id, archive):
    """Every file of the build as bytes, the manifest last (it holds the hash of all the others)."""
    files = {"level0.json": level0, "level1.json": level1}
    files.update({f"group/{gid}.json": g for gid, g in groups.items()})
    data = "window.RH_DATA = " + _js_safe(_dump({"groups": groups, "level0": level0, "level1": level1})) + ";\n"
    out = {k: (_dump(v) + "\n").encode("utf-8") for k, v in files.items()}
    out["data.js"] = data.encode("utf-8")
    out["index.html"] = page.encode("utf-8")
    manifest = {"commits": commits, "counts": {"blocks": m.totals["blocks"], "groups": m.totals["groups"],
                                               "notes": m.totals["notes"]},
                "files": {k: _sha(v) for k, v in sorted(out.items())}, "release_archive_sha": archive,
                "release_id": release_id}
    out["manifest.json"] = (_dump(manifest) + "\n").encode("utf-8")
    return out


def _write_files(dirpath, files):
    for rel, data in files.items():
        p = os.path.join(dirpath, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(data)


def _publish(out, files):
    """Write the build into a temporary sibling of `out` and rename it into place. With an existing `out` (empty, or --force)
    the files that are not a build file are copied into the new tree first and the old tree is set aside, so a failure at any
    step leaves `out` as it was (absent, or the old build) and no temporary directory behind."""
    out = os.path.abspath(out)
    parent, base = os.path.split(out)
    tmp = tempfile.mkdtemp(prefix=base + ".tmp-", dir=parent)
    um = os.umask(0)
    os.umask(um)
    os.chmod(tmp, 0o777 & ~um)
    backup = None
    try:
        _write_files(tmp, files)
        if os.path.isdir(out):
            for name in os.listdir(out):
                if name in _OUT_NAMES or name == "group":
                    continue
                src, dst = os.path.join(out, name), os.path.join(tmp, name)
                if os.path.isdir(src) and not os.path.islink(src):
                    shutil.copytree(src, dst, symlinks=True)
                else:
                    shutil.copy2(src, dst, follow_symlinks=False)
            backup = tmp + ".old"
            os.rename(out, backup)
        os.rename(tmp, out)
        tmp = None
    except BaseException:
        if backup is not None and not os.path.exists(out):
            os.rename(backup, out)
            backup = None
        raise
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)


def _run(notes_dir, outline, decls, strings, out, source_check, archive_sha, notes_commit, repo, force, tools_state):
    if source_check is not None and not os.path.isdir(source_check):
        raise _Unreadable(f"SRC_ROOT is not a directory: {source_check}")
    if os.path.exists(out) and not os.path.isdir(out):
        raise _Unreadable(f"OUT_DIR is not a directory: {out}")
    sj = _read_json(strings, "strings file")
    if os.path.isdir(out) and os.listdir(out) and not force:
        return _refuse([("OUT-NOT-EMPTY", "OUT_DIR", "already holds files; a fresh build would mix two builds; "
                         "use --force to remove the files of an earlier build first")])
    probs = _strings_problems(sj)
    if probs:
        return _refuse(probs)
    if tools_state is None:
        tools_state = _tools_state()
    n_commit, n_dirty = ("unknown", False)
    if notes_commit is not None:   # asked of git before anything is printed: an unreadable --repo is exit 2 with no stdout
        n_commit, n_dirty = _notes_state(repo, notes_commit, [notes_dir, outline, strings, decls])
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        rc = nm.run(notes_dir, outline, decls, strings=strings)
    if rc == 2:
        print(e.getvalue().strip(), file=sys.stderr)
        return 2
    if rc != 0:
        print(o.getvalue().rstrip("\n"))
        if rc == 3:
            return 3
        print("REFUSED: notes_meta found errors; nothing written", file=sys.stderr)
        return rc
    print(next(ln for ln in o.getvalue().splitlines() if ln.startswith("outline: ")))
    print(next(ln for ln in o.getvalue().splitlines() if ln.startswith("claim basis: ")))
    odata = _read_json(outline, "outline")
    bases = [g["claim"].get("basis") for g in odata["groups"] if isinstance(g.get("claim"), dict)]
    n_read, n_census = bases.count("read"), bases.count("census")
    n_without = len(bases) - n_read - n_census
    print(f"claim basis: {n_read} read, {n_census} census, {n_without} without" + (" (treated as read)" if n_without else ""))
    errors = []
    ids = [g["id"] for g in odata["groups"]]
    low = {}
    for i in ids:
        low.setdefault(i.lower(), set()).add(i)
        if not SAFE_ID.fullmatch(i) or len(i) > 100:
            errors.append(("GROUP-ID-UNSAFE", i, "is not usable as a file name (letters, digits, `.`, `_`, `-`; not first `.`; "
                                                 "at most 100 characters)"))
    for k, v in sorted(low.items()):
        if len(v) > 1:
            errors.append(("GROUP-ID-UNSAFE", ", ".join(sorted(v)), "differ only in case, so they could share a file"))
    if errors:
        return _refuse(errors)
    dirty = n_dirty or tools_state[1]
    commits = {"notes": n_commit, "release": odata["release"], "tools": tools_state[0]}
    if dirty:
        commits = {k: "dirty" for k in commits}
    m = _model(notes_dir, odata, _decl_rows(decls), sj, source_check, errors)
    word_notes = _word_notes(m, sj)
    for where, word in word_notes:
        print(f"WORD-NOTE {where} {word}")
    for n in m.notes:
        for b in n["blocks"]:
            for what in ("reader", "date"):
                if b["kind"] in READER_KINDS and not (isinstance(b.get(what), str) and b[what]):
                    errors.append(("BLOCK-NO-READER" if what == "reader" else "BLOCK-NO-DATE", b["block"],
                                   f"{b['kind']} block has no {what}"))
    e2, check_line, level0, level1, groups, facts = _assemble(m, sj, commits)
    errors += e2
    if errors:
        return _refuse(errors)
    page = _render_page(m, sj, facts, dirty)
    files = _output_files(level0, level1, groups, page, commits, m, odata["release"], archive_sha)
    for pb in static_problems(page, files["data.js"].decode("utf-8")):
        errors.append(("PAGE-STATIC", pb, "found in " + _origin(pb, sj, level0, level1, groups)))
    for pb in link_problems(page):
        errors.append(("PAGE-LINK", pb, "does not resolve on the page"))
    for pb in number_problems(page, number_pool([level0, level1] + list(groups.values())), json.dumps(sj, ensure_ascii=False)):
        errors.append(("PAGE-NUMBER", pb, "is on the page and in no JSON file or strings file"))
    if errors:
        return _refuse(errors)
    print("facts check: " + check_line)
    if source_check is not None:
        if not sg.walk_lean(source_check):
            print("CHECKED NOTHING: no .lean file under SRC_ROOT")
            return 3
        copied = m.copied + [(n["id"], "field list_title", n["title"].split("\n")) for n in m.notes]
        try:
            leaks, st = leak_check(files, source_check, copied)
        except ValueError as ex:
            return _refuse([("SOURCE-UNREADABLE", "SRC_ROOT", str(ex))])
        print(f"source check: {st['release_files']} release files, {st['release_lines']} release lines, "
              f"{st['output_files']} output files, {st['output_lines']} output lines, {len(leaks)} leaked")
        print(f"source check (copied note text): {st['copied_lines']} copied source lines, {len(st['copied_leaks'])} leaked; "
              "no output line equals a release line and no line of copied note text equals one; "
              "a release line quoted inside a longer sentence is not detected")
        found = [("SOURCE-LEAK", f"note {n} {w}", "holds a line of the release") for n, w in st["copied_leaks"]]
        found += [("SOURCE-LEAK", f, "holds a line of the release") for f in leaks]
        if found:
            return _refuse(found)
    try:
        _publish(out, files)
    except OSError as ex:
        raise _Unreadable(f"cannot write the site: {ex.strerror or ex}")
    print(f"built: {m.totals['groups']} groups, {m.totals['notes']} notes, {m.totals['blocks']} blocks, {len(files)} files, "
          f"{len(word_notes)} word notes")
    return 0


def run(notes_dir, outline, decls, strings, out, source_check=None, archive_sha=None, notes_commit=None, repo=None,
        force=False, tools_state=None):
    """Build the site into `out` and return the exit code 0, 1, 2 or 3 (see the contract). `tools_state` is (commit, dirty)
    for the folder of this file; None asks git."""
    archive_sha = archive_sha.lower() if archive_sha else archive_sha
    buf = io.StringIO()   # nothing reaches stdout on exit 2
    try:
        with contextlib.redirect_stdout(buf):
            rc = _run(notes_dir, outline, decls, strings, out, source_check, archive_sha, notes_commit, repo, force, tools_state)
    except _Unreadable as ex:
        print("build_site: " + str(ex), file=sys.stderr)
        return 2
    except RecursionError:
        print("build_site: outline too deep to write", file=sys.stderr)
        return 2
    except OSError as ex:
        print(f"build_site: cannot read an input: {ex.strerror or ex}", file=sys.stderr)
        return 2
    sys.stdout.write(buf.getvalue())
    return rc


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
HOST = '</script><img src=x onerror=alert(1)>"\'&`<b>%41\u2028'
HOST_S = HOST.replace("%41", "")   # the strings file may not hold a percent sign (outside its hrefs)
ESC = '&lt;/script&gt;&lt;img src=x onerror=alert(1)&gt;&quot;&#x27;&amp;`&lt;b&gt;%41\u2028'
ESC_S = ESC.replace("%41", "")


def _n01(arg_text=ARG_TEXT, drop_reader=False, host=None, interp_text="We think this is the key step."):
    """Note one; with `host` every title, reader and date the page shows is that string."""
    rd = {} if drop_reader else {"reader": host or "Reader One"}
    d1, d2, d3 = (host, host, host) if host else ("2026-11-23", "2026-11-24", "2026-11-22")
    r1, r2 = host or "Reader One", host or "Reader Two"
    return ("# Note one\n" + _h(id="01", group="g1", list_title="T " + host if host else "Note one") + "\n\n## Body\n\n"
            "Reading paragraph.\n"
            + _b(id="01.b01", kind="reading", decls=[FOO], file="A/B.lean", lines=[12, 14], date=d1, **rd) + "\n\n"
            + arg_text + "\n"
            + _b(id="01.b02", kind="argument", decls=[FOO], file="A/B.lean", lines=[15, 18], reader=r1,
                 date=d1, second_readers=[{"reader": r2, "date": d2}]) + "\n\n"
            + interp_text + "\n"
            + _b(id="01.b03", kind="interpretation", decls=[FOO], reader=r2, date=d2) + "\n\n"
            "- ListItemTextXYZ one\n- ListItemTextXYZ two\n"
            + _b(id="01.b04", kind="reading", decls=[BAR], item=2, reader=r1, date=d1) + "\n\n"
            "| a | b |\n|---|---|\n| TableCellTextXYZ | y |\n"
            + _b(id="01.b05", kind="not_read", decls=[QUUX], needs="hand_read", row=1) + "\n\n"
            "Correction paragraph.\n"
            + _b(id="01.b06", kind="correction", decls=[FOO], reader=r2, date=d3)
            + "\n" + FILES)


N02 = ("# Note two\n" + _h(id="02", group="g2", list_title="Note two") + "\n\n## Body\n\n"
       "Note two reading qux.\n" + _b(id="02.b01", kind="reading", decls=[QUX], reader="Reader Two", date="2026-11-23") + "\n\n"
       "Note two reading foo.\n" + _b(id="02.b02", kind="reading", decls=[FOO], reader="Reader Two", date="2026-11-23") + "\n")
N03 = "# Note three\n" + _h(id="03", group="g3", list_title="Note three") + "\n\n## Body\n\nNote three text.\n"
N00 = ("# Whole\n" + _h(id="00", group="root", list_title="Whole one", level=0) + "\n\n## Body\n\nWhole text.\n")


def _notes(**kw):
    return {"00-whole.md": N00, "01-one.md": _n01(**kw), "02-two.md": N02, "03-three.md": N03}


def _claim(text, date="2026-11-20", **kw):
    return dict({"text": text, "reader": "Reader One", "date": date, "defs_opened": [], "conventions_checked": ["a"]}, **kw)


def _g(gid, level, parent, order, roots, claim=None, premises=()):
    return {"id": gid, "level": level, "parent": parent, "order": order, "roots": roots, "claim": claim,
            "premises": list(premises)}


def _outline():
    return {"release": "rel-1", "groups": [
        _g("g3", 1, "root", 2, [CORGE], _claim("Claim four with é", basis="census"), ["g1", "g2"]),
        _g("g1a1x", 4, "g1a1", 1, [QUX]),
        _g("g1", 1, "root", 1, [FOO], _claim("Claim one", conditions=["Condition one holds."], basis="read"), ["g1a"]),
        _g("g2", 1, "root", 3, [QUUX, QUX]),
        _g("g1a", 2, "g1", 1, [BAR]),
        _g("g1a1", 3, "g1a", 1, [BAZ], _claim("Claim three & <more>"))]}


def _strings():
    return {
        "page_title": "Page title",
        "first_screen": ["First screen paragraph one.", "First screen paragraph two."],
        "mapped_line": "Mapped by machine line.",
        "no_claim_label": "No plain statement yet",
        "statement_read_line": "Statement read by {reader} on {date}.",
        "statement_census_line": "Statement counted by a script, not read ({reader}, {date}).",
        "statement_not_read_line": "Statement: not read yet.",
        "proof_read_line": "Proof read.",
        "proof_not_read_line": "Proof: not read yet.",
        "statement_count_line": "Statements read: {n} of {m} declarations.",
        "proof_count_line": "Proofs read: {n} of {m} declarations.",
        "open_items_line": "Questions written down: {n}.",
        "steps_statement_line": "Statements read: {n} of {m} steps.",
        "steps_proof_line": "Proofs read: {n} of {m} steps.",
        "steps_open_items_line": "Questions written down in these notes: {n}.",
        "frames": {"argument": ["How this is proved, as {reader} read it"], "interpretation": ["We think"], "claim": []},
        "argument_frame": "How this is proved, as {reader} read it on {date} (lines {lines}):",
        "second_reader_frame": "Read again by {reader} on {date}.",
        "interpretation_frame": "Our interpretation, by {reader} on {date}:",
        "evidence_label": "Evidence: where this sits in the Lean code, and who read what",
        "reactions": [{"label": "This makes sense", "href": "https://example.invalid/react?card={card}&kind=sense"},
                      {"label": "This looks wrong to me", "href": "https://example.invalid/react?card={card}&kind=wrong"},
                      {"label": "I can't follow yet: I need more detail",
                       "href": "https://example.invalid/react?card={card}&kind=detail"}],
        "roots_only_note": "Counts are for the named declarations only.",
        "dirty_note": "This page was built from changes not yet committed.",
        "shared_note": "Also a root of: {groups}",
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
        return ("https://" if path.endswith(".href") and path.startswith("reactions") else "") + "MARK-" + path
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


@contextlib.contextmanager
def _patched(name, value):
    real = globals()[name]
    globals()[name] = value
    try:
        yield
    finally:
        globals()[name] = real


def _full_disk(dirpath, files):
    """A writer that writes one file and then fails like a full disk."""
    rel = sorted(files)[0]
    _put(os.path.join(dirpath, *rel.split("/")), files[rel])
    raise OSError(28, "No space left on device")


def _go(p, **kw):
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        rc = run(p["notes"], p["outline"], p["decls"], p["strings"], p["out"], tools_state=TOOLS_OK, **kw)
    return rc, o.getvalue(), e.getvalue()


def _left(d):
    return sorted(set(os.listdir(d)) - {"notes", "outline.json", "decls.tsv", "strings.json", "src", "out", "args.json"})


def _hostile(v, path=""):
    """The strings fixture with the hostile text added to every string (the href templates get the one with `%`)."""
    if isinstance(v, str):
        return v + HOST if (path == "note_href" or path.endswith(".href")) else v + " " + HOST_S
    if isinstance(v, list):
        return [_hostile(x, f"{path}.{i}") for i, x in enumerate(v)]
    if isinstance(v, dict):
        return {k: (x if k in ("when", "forbidden_words") else _hostile(x, f"{path}.{k}" if path else k)) for k, x in v.items()}
    return v


def _raw(node):
    return "".join(node.pieces())


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


STRING_KEYS = ["page_title", "first_screen", "mapped_line", "no_claim_label", "statement_read_line", "statement_census_line",
               "statement_not_read_line", "proof_read_line", "proof_not_read_line", "statement_count_line", "proof_count_line",
               "open_items_line", "steps_statement_line", "steps_proof_line", "steps_open_items_line", "frames",
               "argument_frame", "second_reader_frame", "interpretation_frame", "evidence_label", "reactions",
               "roots_only_note", "dirty_note", "shared_note", "note_href", "forbidden_words",
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
    @case("X1a", "usage: no argument, four positionals, an unknown option, --notes-commit without --repo, a bad archive hash, a REV that is no commit: exit 2, stdout empty, "
                 "nothing written; control: the same call with five positionals builds")
    def _():
        got = []
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            five = [p["notes"], p["outline"], p["decls"], p["strings"], p["out"]]
            for argv in ([], five[:4], five + ["--bogus"], five + ["--notes-commit", "HEAD"], five + ["--release-archive-sha", "zz"],
                         five + ["--notes-commit", "no-such-rev", "--repo", d]):
                o, e = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                    rc = main(["build_site.py"] + argv, check=lambda: 0)
                got.append((rc, o.getvalue(), os.path.exists(p["out"])))
            o, e = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                rc = main(["build_site.py"] + five, check=lambda: 0)
        return _eq(got + [rc], [(2, "", False)] * 6 + [0])

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
            o["groups"][1]["id"] = bad   # g1a1x: no child, no premise, no note names it
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
            selftest(only=["X2a", "B7d"])
        with contextlib.redirect_stdout(bad_out), contextlib.redirect_stderr(bad_err):
            rc = selftest(only=["X2a", "NOPE"])
        ran = [ln.split(" ")[1] for ln in ok_out.getvalue().splitlines() if ln.startswith("CASE ")]
        return _eq((ran, rc, "NOPE" in bad_err.getvalue(), bad_out.getvalue()), (["X2a", "B7d"], 2, True, ""))

    # ---- data
    @case("L0", "level0.json: the level-1 steps g1 g3 g2 in `order` (the outline lists g3 first, and `order` is not the id order), each with its "
                "facts (statement_read and proof_read when EVERY root has them, unread) and counts; `facts` counts the steps per fact "
                "(statements 1 read + 2 not, proofs 1 + 2); the level-0 note is in header_notes; the totals hold open_items")
    def _():
        l0 = _base().js("level0.json")
        steps = l0["steps"]
        got = ([s["id"] for s in steps], [s["statement_read"] for s in steps], [s["proof_read"] for s in steps],
               [s["unread"] for s in steps], [s["lean_name"] for s in steps], [s["claim_label"] for s in steps],
               steps[0]["claim"], [n["note"] for n in steps[0]["notes"]], steps[0]["notes"][0],
               l0["facts"], l0["header_notes"], l0["totals"], l0["level"])
        want = (["g1", "g3", "g2"], [True, False, False], [True, False, False], [False, True, False],
                ["foo", "corge", "quux"], [None, None, "No plain statement yet"],
                {"basis": "read", "conditions": ["Condition one holds."], "date": "2026-11-20", "premises": ["g1a"],
                 "reader": "Reader One", "text": "Claim one"},
                ["01", "02"], {"link": "notes/01-one.md", "list_title": "Note one", "note": "01"},
                {"proof_not_read": 2, "proof_read": 1, "statement_not_read": 2, "statement_read": 1, "steps": 3},
                [{"link": "notes/00-whole.md", "list_title": "Whole one", "note": "00"}],
                {"blocks": 8, "groups": 6, "notes": 4, "open_items": 1, "roots": 6}, 0)
        return _eq(got, want)

    @case("L1", "level1.json nests child groups to depth 4: g1 > g1a > g1a1 > g1a1x, leaves have no children; steps in `order`, not in id order")
    def _():
        l1 = _base().js("level1.json")
        g1 = l1["steps"][0]
        chain = [g1["id"], g1["children"][0]["id"], g1["children"][0]["children"][0]["id"],
                 g1["children"][0]["children"][0]["children"][0]["id"]]
        leaf = g1["children"][0]["children"][0]["children"][0]
        return _eq((chain, leaf["children"], [s["id"] for s in l1["steps"]], l1["steps"][1]["children"], l1["level"]),
                   (["g1", "g1a", "g1a1", "g1a1x"], [], ["g1", "g3", "g2"], [], 1))

    @case("G1", "group/g1.json holds exactly its keys, its root with kind, file and lines, and its five blocks in id order with "
                "second_readers, text and first sentence; group/g2.json holds the open not_read item and the shared root")
    def _():
        g1, g2, g1a = _base().js("group/g1.json"), _base().js("group/g2.json"), _base().js("group/g1a.json")
        arg = g1["blocks"][1]
        got = (sorted(g1), g1["roots"], [b["block"] for b in g1["blocks"]], arg,
               g2["open_items"], g2["roots"][1], g1a["blocks"], sorted(_base().files))
        want = (["blocks", "commits", "id", "level", "notes", "open_items", "parent", "roots"],
                [{"file": "A/B.lean", "kind": "theorem", "lines": [10, 20], "module": "A.B", "name": "foo", "sha256": None,
                  "shared_with": [], "statement_read": True, "proof_read": True}],
                ["01.b01", "01.b02", "01.b03", "01.b06", "02.b02"],
                {"block": "01.b02", "date": "2026-11-23", "file": "A/B.lean", "first_sentence": "First argument sentence.",
                 "kind": "argument", "lines": [15, 18], "note": "01", "reader": "Reader One",
                 "roots": [{"module": "A.B", "name": "foo"}],
                 "second_readers": [{"date": "2026-11-24", "reader": "Reader Two"}],
                 "text": "First argument sentence. Second argument sentence."},
                [{"block": "01.b05", "needs": "hand_read", "note": "01", "roots": [{"module": "A.F", "name": "quux"}]}],
                {"file": "A/E.lean", "kind": "theorem", "lines": [1, 4], "module": "A.E", "name": "qux", "sha256": None,
                 "shared_with": ["g1a1x"], "statement_read": True, "proof_read": False},
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
                   (True, {"blocks": 8, "groups": 6, "notes": 4}, "rel-1", "ab" * 32, None))

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
                "once in the totals; note 01 under g1, g1a (its list block) and g2 (its not_read block); note 03 has a header "
                "group g3 and no block: it is listed under g3 alone (no coverage claim is made for a note)")
    def _():
        b = _base()
        under = {g: [n["note"] for n in b.js(f"group/{g}.json")["notes"]] for g in ("g1", "g1a", "g1a1", "g1a1x", "g2", "g3")}
        return _eq((under, b.js("level0.json")["totals"]["notes"]),
                   ({"g1": ["01", "02"], "g1a": ["01"], "g1a1": [], "g1a1x": ["02"], "g2": ["01", "02"], "g3": ["03"]}, 4))

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

    @case("R1a", "F4 planted: a flag that is neither true nor false is fed to the fact function for the steps: SUM-STATEMENT (or "
                 "SUM-PROOF) `steps: read 0 + not read 2 = 2, but there are 3 steps`, exit 1, nothing written; planted on the roots "
                 "of g2: `group g2 roots: read 1 + not read 0 = 1, but there are 2 roots` (statement) and `read 0 + not read 1 = 1, ...` "
                 "(proof); the sums guard a MISSING flag, not a wrong one; fact_pairs counts only true and false")
    def _():
        real = globals()["_fact_flags"]
        res = []
        for key, n_items in (("statement_read", 3), ("proof_read", 3), ("statement_read", 2), ("proof_read", 2)):
            def plant(items, k, key=key, n_items=n_items, real=real):
                flags = real(items, k)
                return [None] + flags[1:] if k == key and len(items) == n_items else flags
            with _patched("_fact_flags", plant):
                b = _build()
            res.append((b.rc, [ln for ln in b.out.splitlines() if ln.startswith("BUILD-ERROR SUM-")], b.existed))
        err = "read 0 + not read 2 = 2, but there are 3 steps"
        return _eq((res, fact_pairs([True, False, None, True]), fact_pairs([])),
                   ([(1, ["BUILD-ERROR SUM-STATEMENT steps: " + err], False), (1, ["BUILD-ERROR SUM-PROOF steps: " + err], False),
                     (1, ["BUILD-ERROR SUM-STATEMENT group g2 roots: read 1 + not read 0 = 1, but there are 2 roots"], False),
                     (1, ["BUILD-ERROR SUM-PROOF group g2 roots: read 0 + not read 1 = 1, but there are 2 roots"], False)],
                    (2, 1), (0, 0)))

    @case("R1b", "a good build prints `facts check: statements read 1 + not read 2 = 3 steps; proofs read 1 + not read 2 = 3 steps`")
    def _():
        return _eq("facts check: statements read 1 + not read 2 = 3 steps; proofs read 1 + not read 2 = 3 steps"
                   in _base().out.splitlines(), True)

    # ---- page
    @case("P1a", "a missing key of the strings file (each of the 46 keys in turn) is a build error that names it, exit 1, nothing "
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
        return _eq((bad, len(STRING_KEYS)), ([], 46))

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

    @case("P2a", "a card, in order: the claim, the conditions directly under it, the premises, the statement line, the proof line, the "
                 "open-items line, the idea; all direct children of the card, before the closed evidence section")
    def _():
        c = _card(_base(), "g1")
        names = [(k.tag, k.cls[-1] if k.cls else "") for k in c.elems()]
        want = [("h3", "claim"), ("ul", "conditions"), ("p", "premises"), ("p", "statement"), ("p", "proof"), ("p", "open-items"),
                ("p", "argument"), ("details", "evidence")]
        pos = {n: names.index(n) for n in want}
        return _eq(([n for n in sorted(pos, key=pos.get)], c.find("ul", "conditions")[0].text(), c.find("h3", "claim")[0].text(),
                    c.find("ul", "conditions")[0].inside("details")), (want, "Condition one holds.", "Claim one", False))

    @case("P2b", "text from the data is escaped (`Claim three & <more>` shows as text, the raw page has &amp; and &lt;more&gt;), "
                 "and a premise is a link to the premise's card: g3 rests on `Claim one` (#g1) and `quux` (#g2, null claim)")
    def _():
        b = _base()
        prem = _card(b, "g3").find("p", "premises")[0]
        links = [(a.attrs["href"], a.text()) for a in prem.find("a")]
        return _eq((_card(b, "g1a1").find("h3", "claim")[0].text(), "Claim three &amp; &lt;more&gt;" in b.page, links),
                   ("Claim three & <more>", True, [("#g1", "Claim one"), ("#g2", "quux")]))

    @case("P3", "a null claim shows the Lean name of its first root and the no_claim_label in the heading; evidence is a closed "
                "<details> (no `open`) whose summary is the evidence label and which holds the root's file, lines and open item")
    def _():
        c = _card(_base(), "g2")
        ev = c.find("details", "evidence")[0]
        return _eq((c.find("h3", "claim")[0].text(), "open" in ev.attrs, ev.find("summary")[0].text(),
                    "A/F.lean" in ev.text(), "1-3" in ev.text(), "hand_read" in ev.text(),
                    all("open" not in d.attrs for d in _dom(_base().page).find("details"))),
                   ("quux No plain statement yet", False, "Evidence: where this sits in the Lean code, and who read what",
                    True, True, True, True))

    @case("P4", "the child groups of a step are nested in its closed `go deeper` <details>, to depth 4; the three steps stay "
                "in the chain list in `order`")
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
                   (["g1", "g3", "g2"], ["g1a1", "g1a", "g1"], False, "Go deeper: the parts of this step"))

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

    @case("P6b", "number_pool leaves the hash fields out (sha256, files, commits, release_archive_sha), so a hash cannot vouch for a "
                 "small number; and the builder applies number_problems: a page with an invented number (injected here) is "
                 "refused as PAGE-NUMBER, exit 1, nothing written")
    def _():
        pool = number_pool([{"sha256": "ab7cd", "files": {"x": "9"}, "commits": {"t": "77"}, "release_archive_sha": "55", "n": 3}])
        real = globals()["_render_page"]
        globals()["_render_page"] = lambda *a: real(*a).replace("<h1>", "<h1>99999 ", 1)
        try:
            b = _build()
        finally:
            globals()["_render_page"] = real
        return _eq((number_problems("<p>3 7 9 77 55</p>", pool, ""), b.rc, "BUILD-ERROR PAGE-NUMBER 99999 " in b.out, b.existed),
                   (["7", "9", "55", "77"], 1, True, False))

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
        return _eq((static_problems(_base().page, _base().text("data.js")), b.rc, "BUILD-ERROR PAGE-STATIC fetch( found in strings key first_screen[0]" in b.out, b.existed),
                    ([], 1, True, False))

    @case("P7c", "data.js is scanned as well as the page: a token that only the JSON holds (a block's `file`, which the page does "
                 "not show: `A/fetch(1).lean`) is refused as PAGE-STATIC fetch(, exit 1, nothing written")
    def _():
        n = _n01().replace("A/B.lean", "A/fetch(1).lean")
        b = _build(notes=_notes() | {"01-one.md": n})
        return _eq((b.rc, "BUILD-ERROR PAGE-STATIC fetch( found in group g1 field blocks[0].file" in b.out, b.existed), (1, True, False))

    @case("P7d", "a `#` link with no target on the page is refused (PAGE-LINK naming it), exit 1, nothing written: here a reaction "
                 "note_href `#nowhere` from the strings file (a reaction href must be https)")
    def _():
        st = _strings()
        st["note_href"] = "#nowhere"
        b = _build(strings=st)
        return _eq((b.rc, "BUILD-ERROR PAGE-LINK #nowhere " in b.out, b.existed), (1, True, False))

    @case("R2", "the first screen counts steps per fact (`Statements read: 1 of 3 steps.`, `Proofs read: 1 of 3 steps.`) and the open "
                "blocks once (`Questions written down in these notes: 1.`); a card of a group with several roots (g2) counts "
                "declarations; no percent sign and no `of the proof` anywhere on the page")
    def _():
        dom = _dom(_base().page)
        facts = [li.text() for li in dom.find("ul", "facts")[0].find("li")]
        g2 = _card(_base(), "g2")
        return _eq((facts, g2.find("p", "statement")[0].text(), g2.find("p", "proof")[0].text(),
                    g2.find("p", "open-items")[0].text(), "%" in _base().page, "of the proof" in _base().page),
                   (["Statements read: 1 of 3 steps.", "Proofs read: 1 of 3 steps.", "Questions written down in these notes: 1."],
                    "Statements read: 1 of 2 declarations.", "Proofs read: 0 of 2 declarations.", "Questions written down: 1.",
                    False, False))

    @case("R3a", "a strings value holding verified, explained or understood (or a word of forbidden_words) is refused naming "
                 "its key: STRINGS-FORBIDDEN, exit 1, nothing written; a word added to forbidden_words is refused too, and `unverified` "
                 "and `misunderstood` are not the forbidden words")
    def _():
        res = []
        for key, val in (("mapped_line", "This was verified."), ("proof_not_read_line", "Fully Explained here."),
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

    @case("R4b", "a card is `unread` when neither fact holds on any root: g3 (census claim, no block) carries the class and is present; "
                 "g1 (both), g1a1 (claim read, statement only), g2 (one root has the statement) do not; the JSON `unread` agrees")
    def _():
        b = _base()
        steps = {x["id"]: x["unread"] for x in b.js("level0.json")["steps"]}
        return _eq(([("unread" in _card(b, g).cls) for g in ("g3", "g1", "g1a1", "g2")], steps),
                   ([True, False, False, False], {"g1": False, "g3": True, "g2": False}))

    @case("R5", "every card carries the roots_only_note; qux is a root of g2 and of g1a1x: each card marks it shared with the other "
                "group, the JSON says shared_with, and the totals count it once (6 distinct roots)")
    def _():
        b = _base()
        dom = _dom(b.page)
        notes = [c.find("p", "roots-only")[0].text() == "Counts are for the named declarations only." for c in dom.find("article")]
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
                   ("How this is proved, as Reader One read it on 2026-11-23 (lines A/B.lean 15-18): Read again by Reader Two on "
                    "2026-11-24. First argument sentence. Read the note", ["frame"],
                    "How this is proved, as Reader One read it on 2026-11-23 (lines A/B.lean 15-18): Read again by Reader Two on "
                    "2026-11-24. First argument sentence. Second argument sentence.",
                    "Our interpretation, by Reader Two on 2026-11-24: We think this is the key step.", False, True))

    @case("B7b", "the first sentence of the argument is under the claim of the step, outside every closed section, and the second "
                 "sentence is not there")
    def _():
        c = _card(_base(), "g1")
        idea = _direct(c, "p", "argument")[0].text()
        return _eq(("First argument sentence." in idea, "Second argument sentence." in idea, idea.startswith("How this is proved")),
                   (True, False, True))

    @case("B7c", "a step with no argument block shows only the proof status line (`Proof: not read yet.`), no frame and no second "
                 "sentence about the proof; a stale `no_argument` key in the strings file is ignored and never printed; control: "
                 "the step with an argument block shows `Proof read.` and its idea")
    def _():
        c = _card(_base(), "g3")
        st = _strings()
        st["no_argument"] = "We have not read how this is proved."
        b = _build(strings=st)
        return _eq(([p.text() for p in c.find("p", "proof")], len(_direct(c, "p", "argument")), len(_direct(c, "p", "no-argument")),
                    b.rc, "We have not read how this is proved." in b.page,
                    [p.text() for p in _card(_base(), "g1").find("p", "proof")][:1]),
                   (["Proof: not read yet."], 0, 0, 0, False, ["Proof read."]))

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
                   (0, "How this is proved, as Reader Two read it on 2026-11-23 (lines not given): Read the note", False, False))

    @case("U2", "a block anchored to a list carries its `item` and a table block its `row` in the group JSON, as data only")
    def _():
        b = _base()
        return _eq((b.js("group/g1a.json")["blocks"][0]["item"], b.js("group/g2.json")["blocks"][0]["row"],
                    "item" in b.js("group/g1.json")["blocks"][0]), (2, 1, False))

    @case("S1", "statement_read is set only by a claim of basis read or a reading block; proof_read only by an argument block: on the "
                "census-claim root corge (g3) a reading block alone gives (1, 0), an argument block alone (0, 1), an interpretation, "
                "a correction, a not_read and a machine_fact block (0, 0) (the not_read block is one open item); the facts check "
                "still holds")
    def _():
        extra = {"reading": dict(reader="Reader Two", date="2026-11-23"), "argument": dict(reader="Reader Two", date="2026-11-23"),
                 "interpretation": dict(reader="Reader Two", date="2026-11-23"),
                 "correction": dict(reader="Reader Two", date="2026-11-23"), "not_read": dict(needs="hand_read"),
                 "machine_fact": dict(tool="t", tool_version="v", check="text", options="")}
        got = {}
        for kind, kw in extra.items():
            n03 = N03 + _b(id="03.b01", kind=kind, decls=[CORGE], **kw) + "\n"
            b = _build(notes=_notes() | {"03-three.md": n03})
            c = [x for x in b.js("level0.json")["steps"] if x["id"] == "g3"][0]["counts"]
            got[kind] = (b.rc, c["roots_statement_read"], c["roots_proof_read"], c["open_items"])
        want = {k: (0, 1 if k == "reading" else 0, 1 if k == "argument" else 0, 1 if k == "not_read" else 0) for k in extra}
        return _eq(got, want)

    @case("S2", "the first sentence is cut at the first `.`, `!` or `?` that is followed by white space or the end: a decimal or an "
                "abbreviation dot inside a word does not end it (`The constant 1.5 is used. Then more.` gives `The constant 1.5 is "
                "used.`); the group JSON carries it")
    def _():
        t = "The constant 1.5 is used. Then more."
        b = _build(notes=_notes(arg_text=t))
        fs = _first_sentence
        return _eq((fs(t), fs("See e.g.x and 3.2 now"), fs("Is it so? Yes."), fs("Done."), fs("Stop!\nNext."),
                    b.js("group/g1.json")["blocks"][1]["first_sentence"]),
                   ("The constant 1.5 is used.", "See e.g.x and 3.2 now", "Is it so?", "Done.", "Stop!", "The constant 1.5 is used."))

    @case("F1a", "the two facts per root in the base build: g1 (claim read + reading + argument) both; g1a (null claim, reading block) "
                 "statement only; g1a1 (claim without basis, read by default) statement only; g1a1x (null claim, reading block "
                 "on qux) statement only; g2 roots [quux, qux] = [neither, statement only]; g3 (claim census, no block) neither")
    def _():
        b = _base()
        st = lambda g: [(r["statement_read"], r["proof_read"]) for r in b.js(f"group/{g}.json")["roots"]]
        return _eq([st(g) for g in ("g1", "g1a", "g1a1", "g1a1x", "g2", "g3")],
                   [[(True, True)], [(True, False)], [(True, False)], [(True, False)], [(False, False), (True, False)],
                    [(False, False)]])

    @case("F1b", "a census claim with an argument block on its root: proof only; a census claim plus a reading block on its root: "
                 "statement read by the BLOCK (the statement line names the block's reader and date); a claim without basis "
                 "alone, a claim with basis read alone: statement only")
    def _():
        arg = N03 + _b(id="03.b01", kind="argument", decls=[CORGE], reader="Reader Two", date="2026-11-23") + "\n"
        rd = N03 + _b(id="03.b01", kind="reading", decls=[CORGE], reader="Reader Two", date="2026-11-23") + "\n"
        ba = _build(notes=_notes() | {"03-three.md": arg})
        br = _build(notes=_notes() | {"03-three.md": rd})
        f = lambda b_: [(r["statement_read"], r["proof_read"]) for r in b_.js("group/g3.json")["roots"]]
        line = lambda b_: _card(b_, "g3").find("p", "statement")[0].text()
        return _eq((f(ba), line(ba), f(br), line(br)),
                   ([(False, True)], "Statement counted by a script, not read (Reader One, 2026-11-20).",
                    [(True, False)], "Statement read by Reader Two on 2026-11-23."))

    @case("W1", "a group id that is safe but longer than 100 characters is GROUP-ID-UNSAFE; 100 characters build")
    def _():
        res = []
        for n in (100, 101):
            o = _outline()
            o["groups"][1]["id"] = "a" * n   # g1a1x: no child, no premise, no note names it
            b = _build(outline=o)
            res.append((b.rc, f"BUILD-ERROR GROUP-ID-UNSAFE {'a' * n} " in b.out, b.existed))
        return _eq(res, [(0, False, True), (1, True, False)])

    @case("W2", "a failure while writing (a full disk, injected) in a fresh run: exit 2, ONE line on stderr and no traceback, nothing "
                "on stdout, OUT_DIR absent and no temporary directory left beside it")
    def _():
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            with _patched("_write_files", _full_disk):
                rc, out, err = _go(p)
            return _eq((rc, out, err, os.path.exists(p["out"]), _left(d)),
                       (2, "", "build_site: cannot write the site: No space left on device\n", False, []))

    @case("W3", "the same failure under --force keeps the old build and the foreign file byte-identical and leaves no temporary "
                "directory; control: the --force run without the failure replaces the old build")
    def _():
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            rc0 = _go(p)[0]
            _put(os.path.join(p["out"], "keep.txt"), "k")
            old = _tree(p["out"])
            with _patched("_write_files", _full_disk):
                rc, out, err = _go(p, force=True)
            same = _tree(p["out"]) == old
            rc2 = _go(p, force=True)[0]
            return _eq((rc0, rc, out, err.count("\n"), same, _left(d), rc2, sorted(_tree(p["out"]))[:2]),
                       (0, 2, "", 1, True, [], 0, ["data.js", "group/g1.json"]))

    @case("W6", "the last step fails (the rename of the new tree into place, injected once) under --force, after the old tree was set "
                "aside: the old build and the foreign file are back byte-identical, no temporary directory is left, exit 2 with one line")
    def _():
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            _go(p)
            _put(os.path.join(p["out"], "keep.txt"), "k")
            old = _tree(p["out"])
            target, real, calls = os.path.abspath(p["out"]), os.rename, []

            def fake(a, b, *k, **kw):
                if os.path.abspath(b) == target and not calls:
                    calls.append(1)
                    raise OSError(5, "Input/output error")
                return real(a, b, *k, **kw)
            os.rename = fake
            try:
                rc, out, err = _go(p, force=True)
            finally:
                os.rename = real
            return _eq((rc, out, err, _tree(p["out"]) == old, _left(d), len(calls)),
                       (2, "", "build_site: cannot write the site: Input/output error\n", True, [], 1))

    @case("W4", "an unwritable parent of OUT_DIR: exit 2, one line, no traceback, nothing left behind (SKIPPED when running as root, "
                "which a directory mode does not stop)")
    def _():
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            raise _SkipCase("running as root: a directory mode does not stop root, so the unwritable parent cannot fail here")
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            ro = os.path.join(d, "ro")
            os.makedirs(ro)
            os.chmod(ro, 0o555)
            try:
                rc, out, err = _go(dict(p, out=os.path.join(ro, "out")))
                left = os.listdir(ro)
            finally:
                os.chmod(ro, 0o755)
            return _eq((rc, out, err.count("\n"), "Traceback" in err, left), (2, "", 1, False, []))

    @case("W5", "an outline 1500 groups deep cannot be written as nested JSON: exit 2 with the one line `outline too deep to write`, "
                "nothing on stdout, nothing written")
    def _():
        groups = [_g(f"d{k}", k, "root" if k == 1 else f"d{k - 1}", 1, [FOO]) for k in range(1, 1501)]
        b = _build(notes={"00-whole.md": N00}, outline={"release": "rel-1", "groups": groups})
        return _eq((b.rc, b.out, b.err, b.existed), (2, "", "build_site: outline too deep to write\n", False))

    @case("DUP1", "two notes with the same header id (02, no blocks): the checker's NOTE-ID-DUPLICATE line names both files, exit 1, "
                  "nothing written (the builder has no rule of its own)")
    def _():
        dup = N03.replace('"id":"03"', '"id":"02"')
        b = _build(notes=_notes() | {"04-dup.md": dup})
        lines = [ln for ln in b.out.splitlines() if ln.startswith("NOTE-ID-DUPLICATE ")]
        return _eq((b.rc, len(lines), "02-two.md" in lines[0] and "04-dup.md" in lines[0], "BUILD-ERROR NOTE-ID-DUPLICATE" in b.out,
                    b.existed), (1, 1, True, False, False))

    @case("WN1", "a claim holding `verified` and `50% of the proof` builds (exit 0) and is LISTED: two WORD-NOTE lines naming the "
                 "claim's group, the count in the built line; control: the base build lists none")
    def _():
        o = _outline()
        o["groups"][0]["claim"]["text"] = "A verified claim covering 50% of the proof"
        b = _build(outline=o)
        notes = [ln for ln in b.out.splitlines() if ln.startswith("WORD-NOTE")]
        return _eq((b.rc, notes, "built: 6 groups, 4 notes, 8 blocks, 11 files, 2 word notes" in b.out.splitlines(),
                    "A verified claim covering 50% of the proof" in b.page,
                    [ln for ln in _base().out.splitlines() if ln.startswith("WORD-NOTE")],
                    "built: 6 groups, 4 notes, 8 blocks, 11 files, 0 word notes" in _base().out.splitlines()),
                   (0, ["WORD-NOTE g3.claim verified", "WORD-NOTE g3.claim of the proof"], True, True, [], True))

    @case("WN2", "the other texts of the notes and the outline are listed too, never edited: a condition (g1), a claim with only a "
                 "percent sign (g1a1), the text of an argument block (01.b02) and a note title (02), in that order")
    def _():
        o = _outline()
        o["groups"][2]["claim"]["conditions"] = ["Condition understood here."]
        o["groups"][5]["claim"]["text"] = "Half 50% done"
        n01 = _n01(arg_text="First argument was verified. Second argument sentence.")
        n02 = N02.replace('"list_title":"Note two"', '"list_title":"Explained at once"')
        b = _build(outline=o, notes=_notes() | {"01-one.md": n01, "02-two.md": n02})
        notes = [ln for ln in b.out.splitlines() if ln.startswith("WORD-NOTE")]
        return _eq((b.rc, notes, "Explained at once" in b.page),
                   (0, ["WORD-NOTE g1.conditions[0] understood", "WORD-NOTE g1a1.claim %", "WORD-NOTE block:01.b02.text verified",
                        "WORD-NOTE note:02.list_title explained"], True))

    @case("WN3", "the strings file is refused for a percent sign and for `of the proof` in the builder's own sentences (steps_statement_line, "
                 "mapped_line, first_screen), naming the key, exit 1, nothing written; the href templates may hold `%` (control)")
    def _():
        res = []
        for key, val in (("mapped_line", "A hundred % sure."), ("steps_statement_line", "{n} of the {m} steps, part of the proof"),
                         ("first_screen", ["It is 50% done."])):
            st = _strings()
            st[key] = val
            b = _build(strings=st)
            res.append((b.rc, f"BUILD-ERROR STRINGS-FORBIDDEN {key}" in b.out, b.existed))
        st = _strings()
        st["reactions"][0]["href"] = "https://example.invalid/react?card={card}&t=%20x"
        st["note_href"] = "notes/{file}?x=%20"
        return _eq((res, _build(strings=st).rc), ([(1, True, False)] * 3, 0))

    @case("H1", "a null claim with a reading block (g1a, root bar): the heading shows the Lean name and the no_claim_label (`bar No "
                "plain statement yet`), the statement line tells the fact (`Statement read by Reader One on 2026-11-23.`, the "
                "reading block's reader and date), the proof line `Proof: not read yet.`; the JSON carries the label")
    def _():
        b = _base()
        c = _card(b, "g1a")
        step = b.js("level1.json")["steps"][0]["children"][0]
        return _eq((c.find("h3", "claim")[0].text(), c.find("p", "statement")[0].text(), c.find("p", "proof")[0].text(),
                    step["claim_label"], step["statement_read"], step["proof_read"], "coverage" in step),
                   ("bar No plain statement yet", "Statement read by Reader One on 2026-11-23.", "Proof: not read yet.",
                    "No plain statement yet", True, False, False))

    @case("ORD1", "the premises of a card are linked in the order of the outline (g2 then g1), not sorted")
    def _():
        o = _outline()
        o["groups"][0]["premises"] = ["g2", "g1"]
        b = _build(outline=o)
        return _eq((b.rc, [a.attrs["href"] for a in _card(b, "g3").find("p", "premises")[0].find("a")]), (0, ["#g2", "#g1"]))

    @case("SHA1", "--release-archive-sha is stored in lower case: an upper-case input gives the same manifest as the lower-case one")
    def _():
        up, lo = _build(archive="AB" * 32), _build(archive="ab" * 32)
        return _eq((up.rc, up.files["manifest.json"] == lo.files["manifest.json"], up.js("manifest.json")["release_archive_sha"]),
                   (0, True, "ab" * 32))

    @case("JS1", "data.js writes < > & U+2028 U+2029 as \\uXXXX like the canonical comment: a claim holding `</script>` appears "
                 "escaped in data.js, none of the five characters is raw in it, and it parses back equal")
    def _():
        o = _outline()
        o["groups"][2]["claim"]["text"] = "Claim </script> & more\u2028 x\u2029"
        b = _build(outline=o)
        js = b.text("data.js")
        data = json.loads(js[len("window.RH_DATA = "):-2])
        return _eq((b.rc, "Claim \\u003c/script\\u003e \\u0026 more\\u2028 x\\u2029" in js, [c in js for c in "<>&\u2028\u2029"],
                    data["level0"]["steps"][0]["claim"]["text"], data["level0"] == b.js("level0.json")),
                   (0, True, [False] * 5, "Claim </script> & more\u2028 x\u2029", True))

    @case("DIRTY2", "an uncommitted edit of decls.tsv alone stamps `dirty` in all three ids (the table is judged as the notes, "
                    "the outline and the strings are); the unedited tree has the commit")
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
                    with open(p["decls"], "a", encoding="utf-8") as f:
                        f.write("# an edit\n")
                shutil.rmtree(p["out"], ignore_errors=True)
                rc, _o, _e = _go(p, notes_commit="HEAD", repo=d)
                res.append((rc, json.load(open(os.path.join(p["out"], "level0.json")))["commits"]["notes"]))
            return _eq(res, [(0, head), (0, "dirty")])

    @case("ESC1", "the hostile text `</script><img src=x onerror=alert(1)>\"'&`<b>%41` + U+2028 in every place data or strings reach "
                  "the page (claim, condition, premise title, note title, reader, date, second reader and date, a declaration name, "
                  "argument text, every strings key and label, the href templates): the built page has no script, img or b element, "
                  "no attribute named on..., no raw `</script`, `<img`, `<b>`; the escaped form is there and each place reads back as "
                  "the hostile text; data.js has none of < > & U+2028 U+2029 raw and parses back equal")
    def _():
        quux = _d("A.F", "quux" + HOST)
        with _patched("QUUX", quux):
            o = _outline()
            n = _notes()
            n["01-one.md"] = _n01(arg_text="Hostile text " + HOST + " ends here. More.", host=HOST)
        o["groups"][2]["claim"]["text"] = "Claim " + HOST
        o["groups"][2]["claim"]["conditions"] = [HOST]
        decls = DECLS.replace("A.F\tquux\t", "A.F\tquux" + HOST + "\t")
        b = _build(outline=o, notes=n, decls=decls, strings=_hostile(_strings()))
        if b.rc != 0:
            return False, b.out + b.err
        dom = _dom(b.page)
        g1, g3 = _card(b, "g1"), _card(b, "g3")
        prem = [(a.attrs["href"], _raw(a)) for a in g3.find("p", "premises")[0].find("a")]
        full = g1.find("details", "evidence")[0].find("p", "argument")[0]
        corr = _direct(g1, "ul", "corrections")[0].find("li")[0]
        react = g1.find("a", "reaction")[0].attrs["href"]
        js = b.text("data.js")
        got = (sorted({n_.tag for n_ in dom.nodes()} & {"script", "img", "b"}),
               [k for n_ in dom.nodes() for k in n_.attrs if k.startswith("on")],
               [t in b.page for t in ("</script", "<img", "<b>")], ESC in b.page, ESC_S in b.page,
               _raw(g1.find("h3", "claim")[0]), [_raw(li) for li in g1.find("ul", "conditions")[0].find("li")], prem,
               [_raw(a) for a in _direct(g1, "ul", "notes")[0].find("a")], _raw(full).count(HOST), _raw(corr).count(HOST),
               react, _raw(dom.find("header")[0].find("p")[0]), _raw(_card(b, "g2").find("h3", "claim")[0]).count("quux" + HOST),
               [c in js for c in "<>&\u2028\u2029"],
               json.loads(js[len("window.RH_DATA = "):-2])["groups"]["g1"] == b.js("group/g1.json"))
        want = ([], [], [False, False, False], True, True, "Claim " + HOST, [HOST],
                [("#g1", "Claim " + HOST), ("#g2", "quux" + HOST)], ["T " + HOST, "Note two"], 5, 3,
                "https://example.invalid/react?card=g1&kind=sense" + HOST, "First screen paragraph one. " + HOST_S, 1,
                [False] * 5, True)
        return _eq(got, want)

    # ---- F19: the two facts
    @case("F2a", "level0.json per step: counts {roots, roots_statement_read, roots_proof_read, roots_open_items, open_items} (g1: 1, 1, 1, "
                 "0, 0; g3: 1, 0, 0, 0, 0; g2: 2, 1, 0, 1, 1) with no key that holds `not_read`; claim.basis is the effective value "
                 "(g1 `read` as written, g3 `census`, g1a1 `read` although the file has none); no `coverage` key; level0 `facts`")
    def _():
        b = _base()
        l0 = b.js("level0.json")
        steps = {x["id"]: x for x in l0["steps"]}
        g1a1 = b.js("level1.json")["steps"][0]["children"][0]["children"][0]
        return _eq(([steps[g]["counts"] for g in ("g1", "g3", "g2")], [k for x in steps.values() for k in x["counts"] if "not_read" in k],
                    [steps["g1"]["claim"]["basis"], steps["g3"]["claim"]["basis"], g1a1["claim"]["basis"]],
                    ["coverage" in x for x in steps.values()], l0["facts"], "route" in l0),
                   ([{"roots": 1, "roots_statement_read": 1, "roots_proof_read": 1, "roots_open_items": 0, "open_items": 0},
                     {"roots": 1, "roots_statement_read": 0, "roots_proof_read": 0, "roots_open_items": 0, "open_items": 0},
                     {"roots": 2, "roots_statement_read": 1, "roots_proof_read": 0, "roots_open_items": 1, "open_items": 1}],
                    [], ["read", "census", "read"], [False] * 3,
                    {"proof_not_read": 2, "proof_read": 1, "statement_not_read": 2, "statement_read": 1, "steps": 3}, False))

    @case("F3a", "a stale strings file is refused naming the key: `coverage`, `not_read_yet`, `roots_not_read`, `roots_not_read_note`; the "
                 "two status keys (statement_not_read_line, proof_not_read_line) are allowed (the base builds)")
    def _():
        res = []
        for key, val in (("coverage", [{"when": {"read_all": True}, "word": "All"}]), ("not_read_yet", "x"), ("roots_not_read", "{N}"),
                         ("roots_not_read_note", "x")):
            st = _strings()
            st[key] = val
            b = _build(strings=st)
            res.append((b.rc, f"BUILD-ERROR STRINGS-KEY {key} " in b.out, b.existed))
        return _eq((res, _base().rc), ([(1, True, False)] * 4, 0))

    @case("F3b", "a strings value holding one of the retired words `Read by us`, `Partly read`, `Not read yet` is STRINGS-FORBIDDEN naming "
                 "the key; the built page and data.js hold none of the three")
    def _():
        res = []
        for w in ("Read by us", "Partly read", "Not read yet"):
            st = _strings()
            st["first_screen"] = [f"The page says {w} here."]
            b = _build(strings=st)
            res.append((b.rc, "BUILD-ERROR STRINGS-FORBIDDEN first_screen[0] " in b.out, b.existed))
        every = _base().page + _base().text("data.js")
        return _eq((res, [w in every for w in ("Read by us", "Partly read", "Not read yet")]), ([(1, True, False)] * 3, [False] * 3))

    @case("C1", "the status lines of the cards (statement, proof, open items): g1 `Statement read by Reader One on 2026-11-20.` (the "
                "claim's reader and date, not the reading block's), `Proof read.`, 0; g1a `Statement read by Reader One on "
                "2026-11-23.` (the reading block), proof not read; g1a1x `Statement read by Reader Two on 2026-11-23.`; g3 the census "
                "line, `Proof: not read yet.`, 0")
    def _():
        b = _base()
        line = lambda g: [c.text() for c in (_card(b, g).find("p", "statement")[0], _card(b, g).find("p", "proof")[0],
                                            _card(b, g).find("p", "open-items")[0])]
        return _eq([line(g) for g in ("g1", "g1a", "g1a1x", "g3")],
                   [["Statement read by Reader One on 2026-11-20.", "Proof read.", "Questions written down: 0."],
                    ["Statement read by Reader One on 2026-11-23.", "Proof: not read yet.", "Questions written down: 0."],
                    ["Statement read by Reader Two on 2026-11-23.", "Proof: not read yet.", "Questions written down: 0."],
                    ["Statement counted by a script, not read (Reader One, 2026-11-20).", "Proof: not read yet.",
                     "Questions written down: 0."]])

    @case("C2", "the line open_items_line comes from its key and shows the number and never `not read` (the fixture value holds none): "
                "on g2 `Questions written down: 1.`; a build whose key says `Open: {n} questions` shows `Open: 1 questions` on g2")
    def _():
        st = _strings()
        st["open_items_line"] = "Open: {n} questions"
        b = _build(strings=st)
        return _eq(("not read" in _strings()["open_items_line"].lower(), _card(_base(), "g2").find("p", "open-items")[0].text(),
                    _card(b, "g2").find("p", "open-items")[0].text()), (False, "Questions written down: 1.", "Open: 1 questions"))

    @case("PRO1", "a null-claim step with three roots (quux, qux, corge) and argument blocks on two of them: the step does NOT count for "
                  "the proof (a step counts when EVERY root has the fact), the card counts `Proofs read: 2 of 3 declarations.`, "
                  "roots_proof_read is 2 and facts.proof_read stays 1 (g1)")
    def _():
        o = _outline()
        o["groups"][3]["roots"] = [QUUX, QUX, CORGE]
        n03 = (N03 + "\nArgues quux.\n" + _b(id="03.b01", kind="argument", decls=[QUUX], reader="Reader Two", date="2026-11-23")
               + "\n\nArgues qux.\n" + _b(id="03.b02", kind="argument", decls=[QUX], reader="Reader Two", date="2026-11-23") + "\n")
        b = _build(outline=o, notes=_notes() | {"03-three.md": n03})
        g2 = [x for x in b.js("level0.json")["steps"] if x["id"] == "g2"][0]
        return _eq((b.rc, g2["proof_read"], g2["counts"]["roots_proof_read"], b.js("level0.json")["facts"]["proof_read"],
                    _card(b, "g2").find("p", "proof")[0].text()), (0, False, 2, 1, "Proofs read: 2 of 3 declarations."))

    @case("ZERO1", "the model with a group that has NO root (called directly: the checker refuses it first in a run): it is never "
                   "counted as read (statement_read and proof_read False, unread True, counts roots 0) and FACTS-NO-ROOT names it; "
                   "the guard is redundant by design")
    def _():
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            odata = json.load(open(p["outline"]))
            odata["groups"].append(_g("gz", 1, "root", 9, []))
            errors = []
            m = _model(p["notes"], odata, _decl_rows(p["decls"]), _strings(), None, errors)
            z = m.summary["gz"]
            return _eq((z["statement_read"], z["proof_read"], z["unread"], z["counts"]["roots"], z["lean_name"], errors),
                       (False, False, True, 0, None, [("FACTS-NO-ROOT", "gz", "group has no root, so no fact claim")]))

    @case("RET1", "the retired-word check is an exact-case, single-space match: `not read yet.` ships, `Not read yet.` is refused "
                  "and the refusal says `exact-case match; the lowercase phrase `not read yet` is allowed inside status wording`")
    def _():
        ok_ = _strings()
        ok_["statement_not_read_line"] = "not read yet."
        bad_ = _strings()
        bad_["statement_not_read_line"] = "Not read yet."
        a, b = _build(strings=ok_), _build(strings=bad_)
        msg = ("BUILD-ERROR STRINGS-FORBIDDEN statement_not_read_line holds 'Not read yet', a word of the retired coverage scale "
               "(exact-case match; the lowercase phrase `not read yet` is allowed inside status wording)")
        return _eq((a.rc, b.rc, msg in b.out.splitlines(), b.existed), (0, 1, True, False))

    @case("RDR1", "a root with two reading blocks in different notes: the statement reader is the first by NOTE ID then block number, "
                  "not by date: g1a (root bar) has 01.b04 (Reader One, 2026-11-23) and 03.b01 (Reader Three, 2026-11-01); the "
                  "line names Reader One on 2026-11-23 although the other date is earlier")
    def _():
        n03 = N03 + "\nAlso read.\n" + _b(id="03.b01", kind="reading", decls=[BAR], reader="Reader Three", date="2026-11-01") + "\n"
        b = _build(notes=_notes() | {"03-three.md": n03})
        return _eq((b.rc, _card(b, "g1a").find("p", "statement")[0].text(), b.js("level1.json")["steps"][0]["children"][0]["statement_by"]),
                   (0, "Statement read by Reader One on 2026-11-23.",
                    {"date": "2026-11-23", "reader": "Reader One", "source": "block"}))

    @case("ORG1", "a PAGE-STATIC finding is attributed to the strings key that holds the offending token: note_href `http://...` "
                  "(a plain link to a URL) is named, not the first https value (reactions[0].href)")
    def _():
        st = _strings()
        st["note_href"] = "http://example.invalid/{file}"
        b = _build(strings=st)
        return _eq((b.rc, "BUILD-ERROR PAGE-STATIC href=http found in strings key note_href" in b.out.splitlines(), b.existed),
                   (1, True, False))

    @case("OI1", "one not_read block that anchors two groups (03.b01 on foo in g1 and bar in g1a): each card counts 1, totals.open_items "
                 "counts it once (2 with 01.b05); roots_open_items 1 on each")
    def _():
        n03 = N03 + "\nShared question.\n" + _b(id="03.b01", kind="not_read", decls=[FOO, BAR], needs="hand_read") + "\n"
        b = _build(notes=_notes() | {"03-three.md": n03})
        c = {g: [x for x in b.js("level0.json")["steps"] if x["id"] == g][0]["counts"] for g in ("g1",)}
        g1a = b.js("level1.json")["steps"][0]["children"][0]["counts"]
        return _eq((c["g1"]["open_items"], c["g1"]["roots_open_items"], g1a["open_items"], g1a["roots_open_items"],
                    b.js("level0.json")["totals"]["open_items"], _card(b, "g1").find("p", "open-items")[0].text(),
                    "Questions written down in these notes: 2." in b.page), (1, 1, 1, 1, 2, "Questions written down: 1.", True))

    @case("OI2", "two not_read blocks on one root (corge, g3): the card counts 2 blocks, roots_open_items is 1, totals.open_items 3")
    def _():
        n03 = (N03 + "\nFirst question.\n" + _b(id="03.b01", kind="not_read", decls=[CORGE], needs="hand_read")
               + "\n\nSecond question.\n" + _b(id="03.b02", kind="not_read", decls=[CORGE], needs="callers") + "\n")
        b = _build(notes=_notes() | {"03-three.md": n03})
        c = [x for x in b.js("level0.json")["steps"] if x["id"] == "g3"][0]["counts"]
        return _eq((c["open_items"], c["roots_open_items"], b.js("level0.json")["totals"]["open_items"],
                    _card(b, "g3").find("p", "open-items")[0].text()), (2, 1, 3, "Questions written down: 2."))

    @case("OI3", "the base build: totals.open_items 1 (01.b05 on quux), g2's card 1 and its roots_open_items 1, g1's card shows 0 "
                 "(a zero is printed as zero); an argument block is not an open item")
    def _():
        b = _base()
        l0 = b.js("level0.json")
        return _eq((l0["totals"]["open_items"], [x for x in l0["steps"] if x["id"] == "g2"][0]["counts"]["roots_open_items"],
                    _card(b, "g1").find("p", "open-items")[0].text(), _card(b, "g2").find("p", "open-items")[0].text()),
                   (1, 1, "Questions written down: 0.", "Questions written down: 1."))

    @case("BAS1", "the builder's line `claim basis: 1 read, 1 census, 1 without (treated as read)` and the checker's line `claim basis: 1 "
                  "read, 1 census, 1 without` agree on the counts; with every basis written the builder's line has no parenthesis "
                  "and the two lines are the same")
    def _():
        a = _base().out.splitlines()
        o = _outline()
        o["groups"][5]["claim"]["basis"] = "read"
        b2 = _build(outline=o).out.splitlines()
        nums = lambda ln: re.findall(r"\d+", ln)
        la = [ln for ln in a if ln.startswith("claim basis:")]
        lb = [ln for ln in b2 if ln.startswith("claim basis:")]
        return _eq((la, nums(la[0]) == nums(la[1]), lb), (["claim basis: 1 read, 1 census, 1 without",
                                                           "claim basis: 1 read, 1 census, 1 without (treated as read)"], True,
                                                          ["claim basis: 2 read, 1 census, 0 without"] * 2))

    @case("HREF1", "a reaction href template that is not an https URL (http, mailto:, javascript:, a bare path) is refused naming "
                   "reactions[1].href, exit 1, nothing written; control: https builds")
    def _():
        res = []
        for h in ("http://example.invalid/r?c={card}", "mailto:x@example.invalid?subject={card}", "javascript:alert({card})",
                  "/issues/new?title={card}"):
            st = _strings()
            st["reactions"][1]["href"] = h
            b = _build(strings=st)
            res.append((b.rc, "BUILD-ERROR STRINGS-KEY reactions[1].href " in b.out, b.existed))
        return _eq((res, _base().rc), ([(1, True, False)] * 4, 0))

    @case("HREF2", "the hrefs are exempt from the forbidden words: an href holding `riemann-explained` builds; a reaction LABEL holding "
                   "`explained` and a first_screen paragraph holding `explained` are still refused naming their key")
    def _():
        st = _strings()
        st["reactions"][0]["href"] = "https://example.invalid/riemann-explained/issues/new?title={card}"
        st["note_href"] = "notes/{file}?from=riemann-explained"
        ok_ = _build(strings=st)
        st2 = _strings()
        st2["reactions"][0]["label"] = "This is explained"
        st3 = _strings()
        st3["first_screen"] = ["It is explained here."]
        b2, b3 = _build(strings=st2), _build(strings=st3)
        return _eq((ok_.rc, b2.rc, "BUILD-ERROR STRINGS-FORBIDDEN reactions[0].label " in b2.out, b3.rc,
                    "BUILD-ERROR STRINGS-FORBIDDEN first_screen[0] " in b3.out), (0, 1, True, 1, True))

    # ---- K: the source lines of copied text, before they are joined
    other = "theorem not_in_the_release_at_all : 2 + 2 = 4 := rfl"
    srcs = {"A/B.lean": "x = 1\n" + LEAK + "\n"}
    narrow = "no output line equals a release line and no line of copied note text equals one; a release line quoted inside a longer sentence is not detected"
    leak_line = lambda where: f"BUILD-ERROR SOURCE-LEAK {where} holds a line of the release"

    @case("PJ1", "the defect: an argument block's paragraph of two lines whose SECOND line is a line of the release is joined into "
                 "one longer output line that B1 does not see; the source lines are checked before the join: SOURCE-LEAK naming "
                 "note 01 and block 01.b02 (not the line), exit 1, OUT_DIR absent; control: the same paragraph with another "
                 "second line builds")
    def _():
        planted = _build(notes=_notes(arg_text="First argument sentence.\n" + LEAK), src=srcs)
        control = _build(notes=_notes(arg_text="First argument sentence.\n" + other), src=srcs)
        found = [ln for ln in planted.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK")]
        return _eq((planted.rc, found, LEAK in planted.out, planted.existed, control.rc, control.existed),
                   (1, [leak_line("note 01 block 01.b02")], False, False, 0, True))

    @case("PJ2", "the same for an INTERPRETATION block (01.b03): SOURCE-LEAK naming note 01 and block 01.b03; control builds")
    def _():
        planted = _build(notes=_notes() | {"01-one.md": _n01(interp_text="We think this holds.\n" + LEAK)}, src=srcs)
        control = _build(notes=_notes() | {"01-one.md": _n01(interp_text="We think this holds.\n" + other)}, src=srcs)
        found = [ln for ln in planted.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK")]
        return _eq((planted.rc, found, planted.existed, control.rc, control.existed),
                   (1, [leak_line("note 01 block 01.b03")], False, 0, True))

    @case("PJ3", "a note title (a header field) whose second line is a release line: SOURCE-LEAK naming note 02 and the field "
                 "list_title, exit 1; control builds")
    def _():
        t = N02.replace('"list_title":"Note two"', '"list_title":"Note two\\n' + LEAK + '"')
        c = N02.replace('"list_title":"Note two"', '"list_title":"Note two\\n' + other + '"')
        planted = _build(notes=_notes() | {"02-two.md": t}, src=srcs)
        control = _build(notes=_notes() | {"02-two.md": c}, src=srcs)
        found = [ln for ln in planted.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK note ")]
        return _eq((planted.rc, found, planted.existed, control.rc), (1, [leak_line("note 02 field list_title")], False, 0))

    @case("PJ4", "a claim with a newline whose second line is a release line is a leak, found line by line in level0.json, "
                 "level1.json, data.js and index.html (the split at newlines is what finds it); the same claim without a release "
                 "line builds")
    def _():
        res = []
        for second in (LEAK, other):
            o = _outline()
            o["groups"][0]["claim"]["text"] = "Claim four\n" + second
            b = _build(outline=o, src=srcs)
            res.append((b.rc, sorted(ln.split(" ")[2] for ln in b.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK "))))
        return _eq(res, [(1, ["data.js", "index.html", "level0.json", "level1.json"]), (0, [])])

    @case("PJ5", "the run says what the second check ranged over: `source check (copied note text): K copied source lines, L "
                 "leaked; <the narrow claim>`, K counted by the tool (the base build: 4 titles + 1 argument line + 1 "
                 "interpretation line = 6; the two-line argument paragraph, planted or control: 7); the first source-check line "
                 "is unchanged")
    def _():
        line = lambda k, n: f"source check (copied note text): {k} copied source lines, {n} leaked; {narrow}"
        planted = _build(notes=_notes(arg_text="First argument sentence.\n" + LEAK), src=srcs)
        control = _build(notes=_notes(arg_text="First argument sentence.\n" + other), src=srcs)
        return _eq((line(6, 0) in _base_src().out.splitlines(), line(7, 1) in planted.out.splitlines(),
                    line(7, 0) in control.out.splitlines(),
                    any(ln.startswith("source check: 1 release files, ") for ln in planted.out.splitlines())),
                   (True, True, True, True))

    @case("PJ6", "a source line of fewer than 20 non-space characters that is also a release line (`x = 1`) is not a leak: the "
                 "paragraph builds")
    def _():
        b = _build(notes=_notes(arg_text="First argument sentence.\nx = 1"), src=srcs)
        return _eq((b.rc, b.existed), (0, True))

    @case("WN4", "`of the proof` in the notes' own text is listed only after a number, a percent sign or a quantity word: titles "
                 "`The shape of the proof` and `The top of the proof` are not listed; a claim `Most of the proof is routine` and a "
                 "condition `Only 50 of the proof steps` are; the strings file is still refused for `The shape of the proof`")
    def _():
        o = _outline()
        o["groups"][0]["claim"]["text"] = "Most of the proof is routine"
        o["groups"][2]["claim"]["conditions"] = ["Only 50 of the proof steps"]
        n02 = N02.replace('"list_title":"Note two"', '"list_title":"The shape of the proof"')
        n03 = N03.replace('"list_title":"Note three"', '"list_title":"The top of the proof"')
        b = _build(outline=o, notes=_notes() | {"02-two.md": n02, "03-three.md": n03})
        st = _strings()
        st["mapped_line"] = "The shape of the proof"
        refused = _build(strings=st)
        return _eq((b.rc, [ln for ln in b.out.splitlines() if ln.startswith("WORD-NOTE")], refused.rc,
                    "BUILD-ERROR STRINGS-FORBIDDEN mapped_line" in refused.out),
                   (0, ["WORD-NOTE g1.conditions[0] of the proof", "WORD-NOTE g3.claim of the proof"], 1, True))

    # ---- B1: no release text
    @case("B1a", "leak_check: a planted shard whose `text` value is a line of the release (>= 20 non-space characters) is named "
                 "(SOURCE-LEAK data); a short release line and a line of other text are not")
    def _():
        with tempfile.TemporaryDirectory() as d:
            _put(os.path.join(d, "A", "B.lean"), "import A.C\n\n    " + LEAK + "  \nshort\n")
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
        got = sorted(ln.split(" ")[2] for ln in b.out.splitlines()
                     if ln.startswith("BUILD-ERROR SOURCE-LEAK ") and not ln.startswith("BUILD-ERROR SOURCE-LEAK note "))
        return _eq((b.rc, got, b.existed, _base_src().rc), (1, ["data.js", "group/g1.json", "index.html"], False, 0))

    @case("B1d", "the run says what it ranged over: `source check: 1 release files, 40 release lines, 11 output files, N output "
                 "lines, 0 leaked`")
    def _():
        m = re.findall(r"^source check: 1 release files, 40 release lines, 11 output files, (\d+) output lines, 0 leaked$",
                       _base_src().out, re.M)
        return _eq((len(m), bool(m) and int(m[0]) > 20), (1, True))

    @case("B1e", "names are not compared (by construction): a release with a line equal to a declaration's full name (>= 20 "
                 "characters) and a build whose root has that name builds clean, 0 leaked, although the name is in the JSON "
                 "and in <code> on the page; control: the same text as a claim is a leak (level0.json, level1.json, "
                 "data.js, index.html)")
    def _():
        name = "Development.Long.Module.theorem_name_long"
        decls = DECLS.replace("A.G\tcorge", "A.G\t" + name)
        src = {"A/B.lean": "x\n" + name + "\n"}
        o = _outline()
        o["groups"][0]["roots"] = [_d("A.G", name)]
        named = _build(outline=o, decls=decls, src=src)
        o2 = _outline()
        o2["groups"][0]["claim"]["text"] = name
        claimed = _build(outline=o2, src=src)
        got = sorted(ln.split(" ")[2] for ln in claimed.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK "))
        return _eq((named.rc, name in named.page, ", 0 leaked" in named.out, claimed.rc, got),
                   (0, True, True, 1, ["data.js", "index.html", "level0.json", "level1.json"]))

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
