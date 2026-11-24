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
     when there is no --strings, `blocks by kind:` with all seven kinds, what the in-file check (M5) and the byte
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
     a subsequence of the current when each base line (with its line ending) matches, in order, a current line; the unmatched
     current lines are the inserted runs (maximal gaps, one after the last base line too). Two alignments are tried, not all:
     the LEFT-greedy one (each base line takes the earliest equal line after the previous match) and the RIGHT-greedy one (each
     takes the latest equal line before the next match). The note is accepted when either gives only legal runs, and the runs of
     the first such alignment, the left one before the right one, are listed; when neither does, the BYTE-DIFF is the left
     alignment's. A base that is not a subsequence (a line removed or altered) is a BYTE-DIFF as before, under both. Each run,
     after its LEADING blank lines, must begin with a heading (1 to 6 `#`, a space, text) whose text holds a real calendar date
     YYYY-MM-DD; EVERY real date of the heading is not later than --today (default the UTC date of the clock) and not earlier
     than the date in the `release` of the BASE text's header (the published one) when it is `rh-YYYY-MM-DD` (a release with no
     such date, or none, gives no lower bound). A run inside a fence of the published text (opened by base lines before it and
     closed after, or never closed) fails. A run may not touch published text (F5): the line before its first non-blank line
     and the line after its last non-blank line, in the stripped current text, must each be blank or the edge of the text (a blank
     line inside the run counts), else the BYTE-DIFF message says `no blank line before it` or `no blank line after it` and names
     the run's line; an alignment whose runs fail this is not legal. A run above the first published non-blank line fails (F6).
     Fence state is kept (F1): for every base line matched to a current line, being inside a
     fence (rh_anchor's reading of each stripped text) must be the same in both texts, else the note is a BYTE-DIFF whose message
     names the run before that line. One failing run makes the whole note a BYTE-DIFF at the run's first line (a date
     outside the window adds its date and the window to the message). Each legal run is an ADDITION listing
     `ADDITION path:first_line N lines, heading TEXT` (first_line on disk, N in the text without anchors), a warning, never
     an error; the byte-check line ends `additions A` (runs). Cases ADD1 to ADD33.
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

 Root role and recognition (cases RR1 to RR4, REC1 to REC4, CIT1, WORD1 to WORD5, EST1 EST2, RUN1 RUN2, LIST1). A group may carry the
 optional keys `root_role` and `recognition`; any other key is still UNKNOWN-KEY, and a group without them is unchanged.
  F1 root_role is `result`, `named_statement` or `object` (any other value, or a non-string, is ROOT-ROLE) and belongs to a claim (on
     a null claim it is ROOT-ROLE). The role is compared with the kind of the group's one root in decls.tsv HERE (the builder only
     reads it): `result` if and only if the kind is theorem or lemma; every other kind, `inductive` and the empty kind included,
     takes `named_statement` or `object`; a mismatch either way is ROOT-ROLE naming the group, the role, the root and the kind.
     A group with a claim and no root_role is ROOT-ROLE-MISSING: a listing while REQUIRE_ROOT_ROLE is False, an error when True.
  F2 recognition (an object; BRIEF 18e: none on a null claim, RECOGNITION-NULL-CLAIM) has `form` (known, variant, not_recognised,
     open_in_literature), `reader`, `date` (required) and `result`, `citations`, `difference`, `established`. known and variant need
     `result` and a citation, variant also `difference`; not_recognised forbids result, citations and difference
     (RECOGNITION-FORBIDDEN); open_in_literature needs `result`, a citation, a citation with says_open true (OPEN-NO-SAYS-OPEN)
     and root_role `result` or `named_statement` (OPEN-ROLE on `object`, also when the role is absent). An unknown key, an unknown form and a missing key
     are UNKNOWN-KEY, BAD-VALUE and MISSING-KEY naming the group and the key.
  F3 A citation has source, where, opened_by, opened_on (non-empty strings) and optionally url (starts https://), source_date and
     says_open (exactly true or false); opened_on is a real YYYY-MM-DD date; source_date is a real YYYY, YYYY-MM or YYYY-MM-DD (year 0 refused, no padding: a year stays
     a year); says_open true needs source_date.
  F4 Words of `result` and `difference`, whole words in any case: novel and unprecedented are RECOGNITION-WORD-REFUSED (an error);
     new, original, first, assume, assumes, assumed are RECOGNITION-WORD listings, once per word per field.
  F5 `established` is the string `not_traced` or {by: {module, name}, reader, date}; by resolves to exactly one row (UNRESOLVED,
     AMBIGUOUS) whose kind is theorem or lemma (ESTABLISHED-KIND); on a group whose root_role is not `named_statement` it is
     ESTABLISHED-ROLE.
  F6 The run prints `recognition: K known, V variant, N not recognised, O open in literature, M not written, of G groups with a
     claim` after the `claim basis:` line; a group with a claim and no usable recognition counts M, a null claim counts in none;
     K + V + N + O + M = G is asserted from the counts (SUM-RECOGNITION).
 Sketches (F25a). A block belongs to the group named in its note's header and ANCHORS a root of that group when its decls
  include the root (matched by module and name); counts run over ALL the notes of the group. Cases SKC1 to SKC8, ARGNP.
  S1 SKETCH-NO-ARGUMENT: each root a sketch anchors needs an argument block that anchors it, by any reader, in any note of the group.
  S2 SKETCH-DUPLICATE: at most one sketch per group root; a later one is refused naming both block ids.
  S3 SKETCH-ROLE: each anchored root is judged by its own role: the group's root_role when it has a claim and a usable role (only
     `result`), else the kind of the root's one row (only theorem or lemma). A root with no row or several is not judged here
     (UNRESOLVED and AMBIGUOUS are the findings already coded).
  S4 SKETCH-ROOT: the decls of a sketch must include at least one root of its group, and need not list every root; a note whose
     group is not in the outline (or is `root`) anchors none.
  S5 SKETCH-RUN: the reason rh_anchor.run_at gives for the block's span (default 1), when span is a valid integer.
  S6 ARGUMENT-NO-PROOF (a listing, exit unchanged): an argument anchored on a root of its group whose kind is not theorem or
     lemma; a prompt to the reader, since a definition can carry small proofs inside.
  The note line and `blocks by kind:` count seven kinds.

LIMIT. The tool checks the SHAPE of the metadata and that every name resolves to a row; it does not read a claim or a
block and cannot say that it is right. Not checked: whether a claim follows the translation rules (whether a definition
was really opened, whether a convention was really checked: the peer reader's judgement); whether `date` is a date;
whether a note's header id matches its file name or is used by another note (only block ids are compared across
notes); the SHA-256 values of the file table, and whether a quoted lean block is verbatim (check_lean_blocks.py
does that). Title rules: only the two a script can check are checked, that a list_title is not only code spans
and does not end in a parenthetical `(...)`; every other rule on titles (plain words, saying what the note is
about, length, no status in the words) needs a reader. A group with no root_role and the form open_in_literature is OPEN-ROLE, because the role decides whether the form is
allowed (the spec is silent on that case; this is our reading, and a role added later clears it). `established` is for
a named statement only, also under open_in_literature. The line `sketches: S of P steps with a proof read` is NOT printed
here: what a step is belongs to the builder, so it counts there. note_cite.py is unchanged: its --kind takes its choices from
rh_anchor.KINDS, and a sketch cannot be valid through it for want of a basis flag (BAD-BLOCK). A sketch anchored on a list
is asked for `item` like any block on a list. Extra keys are UNKNOWN-KEY for the outline, a group and a
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
with no line, and the other notes are still compared. ADDITION (F27): the floor of the date window is the date of the `release` in the header of the BASE
text, not the note's own and not the current header's (a release deleted or reworded since REV does not lower it), and a base
without a header, or whose release carries no date or an impossible one such as `rh-2026-02-30`, has no floor; the upper bound
is the day of the run. Two alignments of the base into the current are tried (left-greedy, then right-greedy), not every
order-preserving one, so an addition that no other alignment reads as legal can still be a BYTE-DIFF (an inserted line that
repeats a base line can leave the original unmatched as a second run on both sides); a base whose last line has no line ending
cannot gain text after it (the line differs). The fence test compares the fence state of every matched base line in the two
texts, so an inserted marker that wraps or unwraps published text is a BYTE-DIFF; a fence opened in a run and never closed, at the
very end of the note, swallows no base line and is left to rh_anchor's UNCLOSED-FENCE error. Every real date in an added heading
must lie in the window; an impossible date beside a real one is skipped. The boundary rule reads blank lines only: a run that
carries its own blank line on each side and is placed between two rows of a published table, or between a list item and its
indented continuation, has a blank on each side and passes (the table or the list is split); a note that gains one is read by a
person. Blank means white space only, in the text without its anchor lines, so an anchor line between a run and a published line
is no blank line. --today is
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
Root role and recognition: the checker compares the role with the kind class and checks the shape of the recognition; it does not
read it. REQUIRE_ROOT_ROLE is False because the real outline carries no root_role yet: until it does, a claim without one is a listing,
and the constant is set to True in the step that adds the roles. RECOGNITION-WORD is a prompt to the signer and the reviewer, not a
proof, and real names hold "first" and "original"; the words are looked for in `result` and `difference` only, and a word inside a
single-backtick span IS checked (a span is code, but a person reads the words in it). A citation's `opened_on` (a full date) and `source_date` (a year, a year and month, or a full date;
year 0 is refused because the calendar the check uses starts at year 1) are checked as calendar dates; whether the source says what the citation says it says, and `says_open`, are the reader's claim. `established`
is allowed under any form, for a named statement only; the checker verifies that the declaration `by` exists and is a theorem or lemma,
and that its conclusion is the named statement is the reader's claim. A recognition whose form is missing or unknown counts as not
written in the run line (it is also its own finding). `reader`, `date`, `result`, `difference`, `source` and `where` need only be
non-empty strings here: the span rule, the source-leak check and the formula rule over these fields belong to the builder, which
reaches them through its output files (this tool compares no release line).
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
GROUP_OPTIONAL = ("recognition", "root_role")
ROOT_ROLES = ("result", "named_statement", "object")
RESULT_KINDS = ("theorem", "lemma")   # the kinds of the declaration table that take the role `result`; every other kind does not
# While False a group with a claim need not carry root_role (ROOT-ROLE-MISSING is then a listing). The real outline has no roles
# yet; once it carries one on every claim this constant is set to True and a claim without a role becomes an error.
REQUIRE_ROOT_ROLE = False
FORMS = ("known", "variant", "not_recognised", "open_in_literature")
REC_KEYS = ("form", "result", "citations", "difference", "reader", "date", "established")
FORM_REQUIRES = {"known": ("result", "citations"), "variant": ("result", "citations", "difference"), "not_recognised": (),
                 "open_in_literature": ("result", "citations")}
FORM_FORBIDS = {"not_recognised": ("result", "citations", "difference")}
CIT_REQUIRED = ("source", "where", "opened_by", "opened_on")
CIT_OPTIONAL = ("url", "source_date", "says_open")
EST_KEYS = ("by", "reader", "date")
REFUSED_WORDS = ("novel", "unprecedented")
LISTED_WORDS = ("new", "original", "first", "assume", "assumes", "assumed")
_REC_WORDS = re.compile(r"(?<![A-Za-z0-9_])(" + "|".join(REFUSED_WORDS + LISTED_WORDS) + r")(?![A-Za-z0-9_])", re.I)
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_SOURCE_DATE = re.compile(r"[0-9]{4}(-[0-9]{2}(-[0-9]{2})?)?")   # YYYY, YYYY-MM or YYYY-MM-DD (F24: a book's only date is its year)
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
    """({(module, name): [(first, last), ...]}, number of rows, {(module, name): [kind, ...]}); every row of a repeated pair is
    kept, and a pair's kinds are in the order of its (first, last) rows as read (an empty kind stays the empty string)."""
    try:
        with open(path, "rb") as fh:
            text = fh.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as e:
        raise _Unreadable(f"cannot read the decls table: {e}")
    index, kinds, n = {}, {}, 0
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
        kinds.setdefault((cells[0], cells[1]), []).append(cells[2])
        n += 1
    return index, n, kinds


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
        if k not in GROUP_KEYS and k not in GROUP_OPTIONAL:
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


# ---- root_role and recognition (F24): the role is compared with the kind class here, and the builder reads it
def _role_of(g):
    r = g.get("root_role")
    return r if isinstance(r, str) and r in ROOT_ROLES else None


def _is_date(v):
    if not (isinstance(v, str) and _DATE.fullmatch(v)):
        return False
    try:
        datetime.date(int(v[:4]), int(v[5:7]), int(v[8:]))
    except ValueError:
        return False
    return True


def _is_source_date(v):
    """A source_date: YYYY, YYYY-MM or YYYY-MM-DD, each a real date. Year 0 is refused (the calendar here starts at year 1)."""
    if not (isinstance(v, str) and _SOURCE_DATE.fullmatch(v)):
        return False
    y, m, d = int(v[:4]), int(v[5:7] or 1), int(v[8:10] or 1)
    try:
        datetime.date(y, m, d)
    except ValueError:
        return False
    return True


def _check_citation(c, where, path, out):
    if not isinstance(c, dict):
        out.append(_f("BAD-VALUE", path, None, f"{where}: must be an object"))
        return
    for k in sorted(c):
        if k not in CIT_REQUIRED and k not in CIT_OPTIONAL:
            out.append(_f("UNKNOWN-KEY", path, None, f"{where}: unknown key {k!r}"))
    for k in CIT_REQUIRED:
        if k not in c:
            out.append(_f("MISSING-KEY", path, None, f"{where}: missing key {k!r}"))
        elif not _str(c[k]):
            out.append(_f("BAD-VALUE", path, None, f"{where}: {k} must be a non-empty string"))
    if "opened_on" in c and _str(c["opened_on"]) and not _is_date(c["opened_on"]):
        out.append(_f("BAD-VALUE", path, None, f"{where}: opened_on must be a date YYYY-MM-DD"))
    if "source_date" in c and not _is_source_date(c["source_date"]):
        out.append(_f("BAD-VALUE", path, None, f"{where}: source_date must be a date YYYY, YYYY-MM or YYYY-MM-DD"))
    if "says_open" in c and not isinstance(c["says_open"], bool):
        out.append(_f("BAD-VALUE", path, None, f"{where}: says_open must be true or false"))
    if "url" in c and not (isinstance(c["url"], str) and c["url"].startswith("https://")):
        out.append(_f("BAD-VALUE", path, None, f"{where}: url must be a string starting https://"))
    if c.get("says_open") is True and "source_date" not in c:
        out.append(_f("MISSING-KEY", path, None, f"{where}: missing key 'source_date' (says_open is true)"))


def _words_of(text):
    """The refused and listed words of a text, each once, in the order of the text, lower-cased. Single-backtick spans are NOT
    skipped: a span is code, but a person reads the words in it."""
    return list(dict.fromkeys(m.group(1).lower() for m in _REC_WORDS.finditer(text)))


def _check_established(est, g, role, label, path, index, kinds, out):
    pre = f"{label} recognition established"
    if role != "named_statement":
        why = f"root_role is {role!r}" if role else "this group has no root_role: the role is needed"
        out.append(_f("ESTABLISHED-ROLE", path, None, f"{label} recognition: established is only for root_role 'named_statement' ({why})"))
    if est == "not_traced":
        return
    if not isinstance(est, dict):
        out.append(_f("BAD-VALUE", path, None, f"{pre}: must be the string 'not_traced' or an object"))
        return
    for k in sorted(est):
        if k not in EST_KEYS:
            out.append(_f("UNKNOWN-KEY", path, None, f"{pre}: unknown key {k!r}"))
    for k in EST_KEYS:
        if k not in est:
            out.append(_f("MISSING-KEY", path, None, f"{pre}: missing key {k!r}"))
    for k in ("reader", "date"):
        if k in est and not _str(est[k]):
            out.append(_f("BAD-VALUE", path, None, f"{pre}: {k} must be a non-empty string"))
    if "by" not in est:
        return
    if not _decl_entry_ok(est["by"]):
        out.append(_f("BAD-VALUE", path, None, f"{pre} by: must be an object with non-empty string module and name"))
        return
    m, n = est["by"]["module"], est["by"]["name"]
    fnd, _row = _resolve(index, f"{pre} by", path, None, m, n)
    if fnd:
        out.append(fnd)
        return
    kind = kinds[(m, n)][0]
    if kind not in RESULT_KINDS:
        out.append(_f("ESTABLISHED-KIND", path, None, f"{pre} by {m} {n} has kind {kind!r} (a theorem or lemma is needed)"))


def _check_recognition_object(rec, g, role, label, path, index, kinds, out):
    pre = f"{label} recognition"
    form = rec.get("form")
    for k in sorted(rec):
        if k not in REC_KEYS:
            out.append(_f("UNKNOWN-KEY", path, None, f"{pre}: unknown key {k!r}"))
    if "form" not in rec:
        out.append(_f("MISSING-KEY", path, None, f"{pre}: missing key 'form'"))
    elif not (isinstance(form, str) and form in FORMS):
        out.append(_f("BAD-VALUE", path, None, f"{pre}: form must be one of " + ", ".join(repr(x) for x in FORMS) + f", not {form!r}"))
        form = None
    for k in ("reader", "date"):
        if k not in rec:
            out.append(_f("MISSING-KEY", path, None, f"{pre}: missing key {k!r}"))
        elif not _str(rec[k]):
            out.append(_f("BAD-VALUE", path, None, f"{pre}: {k} must be a non-empty string"))
    suffix = f" (form {form!r})"
    for k in FORM_REQUIRES.get(form, ()):
        if k not in rec:
            out.append(_f("MISSING-KEY", path, None, f"{pre}: missing key {k!r}{suffix}"))
    for k in FORM_FORBIDS.get(form, ()):
        if k in rec:
            out.append(_f("RECOGNITION-FORBIDDEN", path, None, f"{pre}: key {k!r} is not allowed with form {form!r}"))
    for k in ("result", "difference"):
        if k in rec and not _str(rec[k]):
            out.append(_f("BAD-VALUE", path, None, f"{pre}: {k} must be a non-empty string"))
    cits = rec.get("citations")
    if "citations" in rec:
        if not isinstance(cits, list):
            out.append(_f("BAD-VALUE", path, None, f"{pre}: citations must be a list"))
        elif not cits and form in ("known", "variant", "open_in_literature"):
            out.append(_f("BAD-VALUE", path, None, f"{pre}: citations must hold at least one citation{suffix}"))
        else:
            for i, c in enumerate(cits):
                _check_citation(c, f"{pre} citations[{i}]", path, out)
    if form == "open_in_literature":
        if role not in ("result", "named_statement"):
            why = f"root_role is {role!r}" if role else "this group has no root_role: the role is needed"
            out.append(_f("OPEN-ROLE", path, None, f"{pre}: form 'open_in_literature' needs root_role 'result' or 'named_statement' ({why})"))
        if isinstance(cits, list) and cits and not any(isinstance(c, dict) and c.get("says_open") is True for c in cits):
            out.append(_f("OPEN-NO-SAYS-OPEN", path, None, f"{pre}: form 'open_in_literature' needs a citation with says_open true"))
    if "established" in rec:
        _check_established(rec["established"], g, role, label, path, index, kinds, out)
    for k in ("result", "difference"):
        if _str(rec.get(k)):
            for w in _words_of(rec[k]):
                if w in REFUSED_WORDS:
                    out.append(_f("RECOGNITION-WORD-REFUSED", path, None, f"{pre} {k}: {w!r} is never said of a statement"))
                else:
                    out.append(_f("RECOGNITION-WORD", path, None, f"{pre} {k}: {w!r} (a prompt to the signer and the reviewer, not a verdict)",
                                  LISTING))


def _check_recognition(data, path, index, kinds):
    """(findings of both classes, the form of each group with a claim: one of FORMS, or None when it has no usable recognition),
    for the root_role and the recognition of every group, in the order of the outline."""
    out, forms = [], []
    groups = data.get("groups") if isinstance(data, dict) and isinstance(data.get("groups"), list) else []
    for i, g in enumerate(groups):
        if not isinstance(g, dict):
            continue
        label = f"group {g.get('id')!r}" if _str(g.get("id")) else f"groups[{i}]"
        claim_null = "claim" in g and g["claim"] is None
        has_claim = isinstance(g.get("claim"), dict)
        role = _role_of(g)
        if "root_role" in g:
            if role is None:
                out.append(_f("ROOT-ROLE", path, None, f"{label}: root_role must be one of "
                              + ", ".join(repr(x) for x in ROOT_ROLES) + f", not {g['root_role']!r}"))
            elif claim_null:
                out.append(_f("ROOT-ROLE", path, None, f"{label}: root_role on a group with a null claim (a role belongs to a claim)"))
            elif has_claim:
                roots = g.get("roots")
                if isinstance(roots, list) and len(roots) == 1 and _decl_entry_ok(roots[0]) \
                        and len(index.get((roots[0]["module"], roots[0]["name"]), [])) == 1:
                    m, n = roots[0]["module"], roots[0]["name"]
                    kind = kinds[(m, n)][0]
                    if role == "result" and kind not in RESULT_KINDS:
                        out.append(_f("ROOT-ROLE", path, None, f"{label}: root_role 'result' but root {m} {n} has kind {kind!r} "
                                      "(only a theorem or lemma is a result)"))
                    elif role != "result" and kind in RESULT_KINDS:
                        out.append(_f("ROOT-ROLE", path, None, f"{label}: root_role {role!r} but root {m} {n} has kind {kind!r} "
                                      "(a theorem or lemma takes 'result')"))
        elif has_claim:
            out.append(_f("ROOT-ROLE-MISSING", path, None, f"{label}: no root_role (result, named_statement or object)",
                          ERROR if REQUIRE_ROOT_ROLE else LISTING))
        rec = g.get("recognition")
        usable = None
        if "recognition" in g:
            if claim_null:
                out.append(_f("RECOGNITION-NULL-CLAIM", path, None, f"{label}: recognition on a group with a null claim"))
            elif not isinstance(rec, dict):
                out.append(_f("BAD-VALUE", path, None, f"{label} recognition: must be an object"))
            else:
                _check_recognition_object(rec, g, role, label, path, index, kinds, out)
                usable = rec.get("form") if rec.get("form") in FORMS else None
        if has_claim:
            forms.append(usable)
    return out, forms


def _recognition_counts(forms):
    """(K known, V variant, N not recognised, O open in literature, M not written, G) over the list of forms of the groups with a
    claim: a form is one of FORMS or None (no usable recognition, counted as not written); any other value is counted
    nowhere, which is what SUM-RECOGNITION catches. G is the length of the list."""
    c = [sum(1 for x in forms if x == f) for f in FORMS]
    return c[0], c[1], c[2], c[3], sum(1 for x in forms if x is None), len(forms)


def _recognition_sum_finding(forms):
    """SUM-RECOGNITION when K + V + N + O + M is not G, counted from the forms given; else None."""
    k, v, n, o, m, g = _recognition_counts(forms)
    if k + v + n + o + m != g:
        return _f("SUM-RECOGNITION", "outline.json", None, f"{k} known + {v} variant + {n} not recognised + {o} open in literature "
                  f"+ {m} not written is {k + v + n + o + m}, not {g} groups with a claim")
    return None


def _recognition_line(c):
    k, v, n, o, m, g = c
    return (f"recognition: {k} known, {v} variant, {n} not recognised, {o} open in literature, {m} not written, "
            f"of {g} groups with a claim")


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


# ---- the sketch and argument cross-checks (F25a): a block belongs to the group of its note's header and ANCHORS a root of that group
# when its decls include the root; the counts run over all the notes of the group
def _group_map(data):
    out = {}
    groups = data.get("groups") if isinstance(data, dict) and isinstance(data.get("groups"), list) else []
    for g in groups:
        if isinstance(g, dict) and _str(g.get("id")) and g["id"] not in out:
            out[g["id"]] = g
    return out


def _anchored_roots(d, g):
    """The roots of the group g (module, name), each once, in the outline's order, that the decls of the block d include."""
    roots = g.get("roots") if isinstance(g.get("roots"), list) else []
    decls = d.get("decls") if isinstance(d.get("decls"), list) else []
    have = {(e["module"], e["name"]) for e in decls if _decl_entry_ok(e)}
    out = []
    for e in roots:
        r = (e["module"], e["name"]) if _decl_entry_ok(e) else None
        if r is not None and r in have and r not in out:
            out.append(r)
    return out


def _root_kind(ctx, root):
    """The kind of the root's one row in the declaration table, None when it has no row or several."""
    ks = ctx.kinds.get(root, [])
    return ks[0] if len(ks) == 1 else None


def _check_sketches(names, texts, odata, ctx):
    """{note name: findings}: SKETCH-NO-ARGUMENT, SKETCH-DUPLICATE, SKETCH-ROLE, SKETCH-ROOT, SKETCH-RUN and the listing
    ARGUMENT-NO-PROOF, in the order of the notes (by name) and of their blocks."""
    groups = _group_map(odata)
    found = {n: [] for n in names}
    argued, by_root, sketches = set(), {}, []
    args = []
    for n in names:
        headers, blocks, _probs = rh.parse_note(texts[n])
        gid = headers[0].data.get("group") if headers else None
        if not _str(gid):
            continue
        g = groups.get(gid)
        for b in blocks:
            kind = b.data.get("kind")
            if kind not in ("argument", "sketch"):
                continue
            roots = _anchored_roots(b.data, g) if g is not None else []
            if kind == "argument":
                argued.update((gid, r) for r in roots)
                args.append((n, b, roots))
            else:
                sketches.append((n, b, gid, g, roots))
                for r in roots:
                    by_root.setdefault((gid, r), []).append((n, b))
    for n, b, roots in args:   # a root that is not a theorem or lemma: the reader says which proof inside it was read
        bid = b.data.get("id")
        label = f"block {bid!r}" if isinstance(bid, str) else "block"
        for m, nm in roots:
            kind = _root_kind(ctx, (m, nm))
            if kind is not None and kind not in RESULT_KINDS:
                found[n].append(_f("ARGUMENT-NO-PROOF", n, b.line, f"{label}: root {m} {nm} has kind {kind!r}, not a theorem or lemma: "
                                   "say in the argument which proof inside it was read", LISTING))
    for n, b, gid, g, roots in sketches:
        d = b.data
        bid = d.get("id")
        label = f"block {bid!r}" if isinstance(bid, str) else "block"
        if g is None:
            found[n].append(_f("SKETCH-ROOT", n, b.line, f"{label}: group {gid!r} is not a group of the outline; "
                               "a sketch needs a group root in its decls"))
        elif not roots:
            have = [(e["module"], e["name"]) for e in g.get("roots", []) if _decl_entry_ok(e)] if isinstance(g.get("roots"), list) else []
            found[n].append(_f("SKETCH-ROOT", n, b.line, f"{label}: its decls include no root of group {gid!r} (roots: "
                               + ", ".join(f"{m} {nm}" for m, nm in have) + ")"))
        for m, nm in roots:
            if (gid, (m, nm)) not in argued:
                found[n].append(_f("SKETCH-NO-ARGUMENT", n, b.line, f"{label}: root {m} {nm} has no argument block in group {gid!r}"))
            first_n, first_b = by_root[(gid, (m, nm))][0]
            if first_b is not b:
                found[n].append(_f("SKETCH-DUPLICATE", n, b.line, f"{label}: root {m} {nm} already has the sketch "
                                   f"{first_b.data.get('id')!r} (at {first_n}:{first_b.line})"))
            role = _role_of(g) if isinstance(g.get("claim"), dict) else None
            if role is not None:
                if role != "result":
                    found[n].append(_f("SKETCH-ROLE", n, b.line, f"{label}: root {m} {nm}: root_role is {role!r}; a sketch is only for 'result'"))
            else:
                kind = _root_kind(ctx, (m, nm))
                if kind is not None and kind not in RESULT_KINDS:
                    found[n].append(_f("SKETCH-ROLE", n, b.line, f"{label}: root {m} {nm} has kind {kind!r}; "
                                       "a sketch is only for a theorem or lemma"))
        span = d.get("span", 1)
        if _int(span) and span >= 1:   # a bad value is the format problem, not a second finding
            why = rh.run_at(texts[n], b.line, span)
            if isinstance(why, str):
                found[n].append(_f("SKETCH-RUN", n, b.line, f"{label}: {why}"))
    return found


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


def _align(a, b, right=False):
    """F27 alignment: match each line of a, in order, to a line of b. From the left (the default) each line takes the EARLIEST equal
    line of b after the previous match; from the right each takes the LATEST equal line before the next one. The index in b of
    every line of a, or None when a is not a subsequence of b (that does not depend on the side)."""
    n = len(a)
    match = [None] * n
    if right:
        k = n - 1
        for j in range(len(b) - 1, -1, -1):
            if k >= 0 and a[k] == b[j]:
                match[k] = j
                k -= 1
        return match if k < 0 else None
    k = 0
    for j, line in enumerate(b):
        if k < n and a[k] == line:
            match[k] = j
            k += 1
    return match if k == n else None


def _insertion_runs(a, b, right=False):
    """The maximal gaps of b left by the alignment of a (see _align) as (start, end, index in a of the base line before the gap,
    -1 for none), in file order, including a gap after the last matched line; None when a is not a subsequence of b."""
    match = _align(a, b, right)
    if match is None:
        return None
    runs, pos = [], 0
    for k, j in enumerate(match):
        if j > pos:
            runs.append((pos, j, k - 1))
        pos = j + 1
    if pos < len(b):
        runs.append((pos, len(b), len(a) - 1))
    return runs


def _bytes_check(name, text, rel, ctx):
    """The findings of the byte check for one note: [] when equal, [NEW-NOTE], one BYTE-DIFF, or one ADDITION listing per run
    when the note only gained dated additions (F27)."""
    show = _vcs(ctx.top, "cat-file", "blob", f"{ctx.rev}:{rel}")
    if show.returncode != 0:
        return [_f("NEW-NOTE", name, None, f"is not present at {ctx.base}", LISTING)]
    try:   # both sides without their anchor lines (header and blocks), decoded the same way
        base_text = show.stdout.decode("utf-8")
        old_text = rh.strip_anchor_lines(base_text)
        old = old_text.encode("utf-8")
    except UnicodeDecodeError:
        return [_f("BYTE-DIFF", name, None, f"the note at {ctx.base} is not valid UTF-8 and cannot be compared")]
    new_text = rh.strip_anchor_lines(text)
    new = new_text.encode("utf-8")
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
    if _align(a, b) is None:   # a base line was removed or altered: as before, whatever the alignment
        return [bytediff(i)]
    rel_date = None   # the floor: the date of the PUBLISHED header's `release` (the base text's) when it is rh-YYYY-MM-DD and real, else none
    base_headers = rh.parse_note(base_text)[0]
    if base_headers and isinstance(base_headers[0].data.get("release"), str):
        m = _RELEASE_DATE.fullmatch(base_headers[0].data["release"])
        rel_date = _real_date(m.group(1)) if m else None
    window = (f"{rel_date.isoformat()} to {ctx.today.isoformat()}" if rel_date else f"up to {ctx.today.isoformat()} (no lower bound)")
    published = rh._Analysis(old_text)   # rh_anchor's reading of both texts, for their fences
    current = rh._Analysis(new_text)

    def blank(j):   # a line of the stripped current text with nothing on it but white space (its ending does not count)
        return not b[j].strip()
    first_text = next((k for k, x in enumerate(a) if x.strip()), None)   # the first published non-blank line, None when there is none

    def judge(right):
        """(ADDITION listings, None) when every run of this alignment is legal and no matched line changes its fence state, else (None, the BYTE-DIFF)."""
        match = _align(a, b, right)
        runs = _insertion_runs(a, b, right)
        adds = []
        for start, end, prev in runs:
            if prev >= 0:   # inside a fence of the published text: opened at or before the base line before the run, closed after it
                fi = published.fence_of[prev]
                if fi != -1 and (published.fences[fi]["close"] is None or published.fences[fi]["close"] > prev):
                    return None, bytediff(start)
            lines = [x.decode("utf-8") for x in b[start:end]]
            first = next((x for x in lines if x.strip()), None)   # the first line after the LEADING blank lines
            m = _HEADING.match(first.rstrip("\r\n")) if first is not None else None
            if not m:
                return None, bytediff(start)
            heading = m.group(1).strip()
            days = [d for d in map(_real_date, _DATE_TOKEN.findall(heading)) if d]   # every REAL date of the heading, in file order
            if not days:
                return None, bytediff(start)
            for day in days:
                if day > ctx.today or (rel_date is not None and day < rel_date):
                    return None, bytediff(start, f"; the added heading's date {day.isoformat()} is outside the window {window}")
            if first_text is not None and prev < first_text:   # F6: above the first published line of text
                return None, bytediff(start, f"; the inserted run at line {plain[start]} begins above the first published non-blank line")
            lit = [x for x in range(start, end) if not blank(x)]   # F5: the run may not touch published text on either side
            if lit[0] > 0 and not blank(lit[0] - 1):
                return None, bytediff(start, f"; the inserted run at line {plain[start]} has no blank line before it")
            if lit[-1] + 1 < len(b) and not blank(lit[-1] + 1):
                return None, bytediff(start, f"; the inserted run at line {plain[start]} has no blank line after it")
            adds.append(_f("ADDITION", name, plain[start], f"{end - start} lines, heading {heading}", LISTING))
        for k, j in enumerate(match):   # F1: a base line that was inside a fence must still be, and one that was outside must still be
            was, now = published.fence_of[k] != -1, current.fence_of[j] != -1
            if was != now:
                start = max((r[0] for r in runs if r[1] <= j), default=j)   # the run just before the line is the one that flipped it
                return None, bytediff(start, f"; the inserted run at line {plain[start]} changes whether line {k + 1} of the text without anchors "
                                             f"is inside a code fence ({'inside' if was else 'outside'} at {ctx.base}, {'inside' if now else 'outside'} now)")
        return adds, None

    first_failure = None   # two alignments are tried, left then right: the first all-legal one is listed, else the LEFT one's failure
    for right in (False, True):
        adds, failure = judge(right)
        if failure is None:
            return adds
        first_failure = first_failure or failure
    return [first_failure]


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
    ctx.index, nrows, ctx.kinds = _read_decls(decls)
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
    rec_found, rec_forms = _check_recognition(odata, os.path.basename(outline), ctx.index, ctx.kinds)
    rec_counts = _recognition_counts(rec_forms)
    sum_f = _recognition_sum_finding(rec_forms)
    rec_found += [sum_f] if sum_f else []
    found = found + rec_found   # findings of both classes: the outline's errors, then those of the roles and the recognitions
    lines = [_render(f) for f in found + words]
    errors = sum(1 for f in found if f[4] == ERROR)
    warnings = len(words) + sum(1 for f in found if f[4] == LISTING)
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
    cross = _check_sketches(names, texts, odata, ctx)
    for n in names:
        fs, hdr_ok, label, counts, invalid, nblocks = _check_note(n, texts[n], ctx)
        if n in dup_at:
            fs.append(_f("NOTE-ID-DUPLICATE", n, hline[n], dup_at[n]))
        fs += cross[n]
        if n in dup_at or cross[n]:
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
    lines.append(_recognition_line(rec_counts))
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


_FIXTURE_ROLE = {("A.C", "baz"): "named_statement"}   # the kind of the fixture's roots decides the role a claim carries by default


def G(i, level=1, parent="root", order=1, roots=None, claim=None, premises=None):
    roots = [R("A.B", "foo")] if roots is None else roots
    g = {"id": i, "level": level, "parent": parent, "order": order, "roots": roots,
         "claim": claim, "premises": [] if premises is None else premises}
    if claim is not None:   # a claim carries a role, so the older cases stay about their own subject
        one = roots[0] if len(roots) == 1 and _decl_entry_ok(roots[0]) else {}
        g["root_role"] = _FIXTURE_ROLE.get((one.get("module"), one.get("name")), "result")
    return g


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
                 "recognition: 0 known, 0 variant, 0 not recognised, 0 open in literature, 0 not written, of 0 groups with a claim",
                 "blocks by kind: machine_fact=0 reading=1 interpretation=0 correction=0 not_read=1 argument=0 sketch=0",
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
       ["BLOCK-PROBLEM 01-a.md:7 block '01.b01': kind: must be one of machine_fact, reading, interpretation, correction, not_read, argument, sketch"], 1)
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
        "BLOCK-PROBLEM 01-a.md:7 block '01.b01': kind: must be one of machine_fact, reading, interpretation, correction, not_read, argument, sketch"], 1)


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


# ---- root_role and recognition (F24): the role is compared with the kind class here; the builder reads the role
DECLS_K = DECLS + ("A.E\tstru\tstructure\t1\t2\ttext-extent\n"
                   "A.E\tind\tinductive\t3\t4\ttext-extent\n"
                   "A.E\tlem\tlemma\t5\t6\ttext-extent\n"
                   "A.E\tabb\tabbrev\t7\t8\ttext-extent\n"
                   "A.E\tmys\t\t9\t10\ttext-extent\n")
CIT = {"source": "S", "where": "W", "opened_by": "R", "opened_on": "2026-11-23"}
REC = {"form": "known", "result": "Prime number theorem", "citations": [CIT], "reader": "R", "date": "2026-11-23"}
OPENCIT = dict(CIT, says_open=True, source_date="2020-01-31")


def _rg(role="result", rec=None, root=("A.B", "foo"), claim=CLAIM, gid="g1", order=1, **extra):
    g = drop(G(gid, order=order, roots=[R(*root)], claim=claim), "root_role")
    if role is not None:
        g["root_role"] = role
    if rec is not None:
        g["recognition"] = rec
    g.update(extra)
    return g


def _ro(*groups, decls=DECLS_K):
    return go(outline=OL(*groups), decls=decls)


def _fl(code, text, gid="g1"):
    return f"{code} outline.json group {gid!r}{text}"


@case("RR1", "root_role is one of result, named_statement, object; any other value or a non-string is ROOT-ROLE naming the group; "
             "a group without the key is unchanged; any other group key is still UNKNOWN-KEY")
def _():
    clean(_ro(_rg("result")))
    clean(_ro(_rg("named_statement", root=("A.C", "baz"))))
    clean(_ro(_rg("object", root=("A.C", "baz"))))
    msg = ": root_role must be one of 'result', 'named_statement', 'object', not "
    fe(_ro(_rg("theorem")), [_fl("ROOT-ROLE", msg + "'theorem'")], 1)
    fe(_ro(_rg(3)), [_fl("ROOT-ROLE", msg + "3")], 1)
    fe(_ro(_rg(["result"])), [_fl("ROOT-ROLE", msg + "['result']")], 1)
    fe(_ro(_rg(True)), [_fl("ROOT-ROLE", msg + "True")], 1)
    fe(_ro(_rg("result", roleish=1)), [_fl("UNKNOWN-KEY", ": unknown key 'roleish'")], 1)
    clean(_ro(G("g1")))


@case("RR2", "root_role on a group whose claim is null is ROOT-ROLE; control: the same role with a claim is clean")
def _():
    fe(_ro(_rg("result", claim=None)), [_fl("ROOT-ROLE", ": root_role on a group with a null claim (a role belongs to a claim)")], 1)
    clean(_ro(_rg("result")))


@case("RR3", "the role is compared with the kind of the group's root in the CHECKER: result iff theorem or lemma; every other kind "
             "(def, structure, abbrev, inductive, empty) takes named_statement or object and is refused with result; a mismatch "
             "either way names group, role, root and kind")
def _():
    res = ": root_role 'result' but root {} {} has kind {!r} (only a theorem or lemma is a result)"
    for root, kind in ((("A.C", "baz"), "def"), (("A.E", "stru"), "structure"), (("A.E", "abb"), "abbrev"),
                       (("A.E", "ind"), "inductive"), (("A.E", "mys"), "")):
        fe(_ro(_rg("result", root=root)), [_fl("ROOT-ROLE", res.format(root[0], root[1], kind))], 1)
        clean(_ro(_rg("named_statement", root=root)))
        clean(_ro(_rg("object", root=root)))
    for root, kind in ((("A.E", "cls"), "class"), (("A.E", "inst"), "instance")):   # the two kinds of the table the list above left out
        d = _ro(_rg("result", root=root), decls=DECLS_K + f"{root[0]}\t{root[1]}\t{kind}\t11\t12\ttext-extent\n")
        fe(d, [_fl("ROOT-ROLE", res.format(root[0], root[1], kind))], 1)
        for role in ("named_statement", "object"):
            clean(_ro(_rg(role, root=root), decls=DECLS_K + f"{root[0]}\t{root[1]}\t{kind}\t11\t12\ttext-extent\n"))
    for root, kind in ((("A.B", "foo"), "theorem"), (("A.E", "lem"), "lemma")):
        clean(_ro(_rg("result", root=root)))
        for role in ("named_statement", "object"):
            fe(_ro(_rg(role, root=root)), [_fl("ROOT-ROLE", f": root_role {role!r} but root {root[0]} {root[1]} has kind {kind!r} "
                                                          "(a theorem or lemma takes 'result')")], 1)


@case("RR4", "a claim with no root_role is a ROOT-ROLE-MISSING listing (exit 0) while REQUIRE_ROOT_ROLE is False, an ERROR when it "
             "is True; a null claim needs no role; control: with the role it is clean")
def _():
    miss = _fl("ROOT-ROLE-MISSING", ": no root_role (result, named_statement or object)")
    r = _ro(_rg(None))
    fe(r, [miss], 0)
    eq(r.lines[-1], "1 notes, 0 findings, 1 warnings", "a listing is a warning")
    eq(REQUIRE_ROOT_ROLE, False, "default")
    saved = REQUIRE_ROOT_ROLE
    try:
        globals()["REQUIRE_ROOT_ROLE"] = True
        r = _ro(_rg(None))
        fe(r, [miss], 1)
        eq(r.lines[-1], "1 notes, 1 findings, 0 warnings", "an error")
        clean(_ro(_rg("result")))
        clean(_ro(G("g1")))
    finally:
        globals()["REQUIRE_ROOT_ROLE"] = saved
    eq(REQUIRE_ROOT_ROLE, False, "restored")


@case("REC1", "recognition on a group whose claim is null is RECOGNITION-NULL-CLAIM (BRIEF 18e); control: with a claim it is clean")
def _():
    fe(_ro(_rg("result", rec=REC, claim=None, root=("A.B", "foo"))),
       [_fl("ROOT-ROLE", ": root_role on a group with a null claim (a role belongs to a claim)"),
        _fl("RECOGNITION-NULL-CLAIM", ": recognition on a group with a null claim")], 1)
    fe(_ro(_rg(None, rec=REC, claim=None)), [_fl("RECOGNITION-NULL-CLAIM", ": recognition on a group with a null claim")], 1)
    clean(_ro(_rg("result", rec=REC)))


@case("REC2", "recognition keys: an unknown key, an unknown form, a non-object, a missing form, reader or date, and an empty reader "
              "are each refused naming the group and the key")
def _():
    p = " recognition: "
    fe(_ro(_rg(rec="known")), [_fl("BAD-VALUE", p + "must be an object")], 1)
    fe(_ro(_rg(rec=dict(REC, extra=1))), [_fl("UNKNOWN-KEY", p + "unknown key 'extra'")], 1)
    fe(_ro(_rg(rec=dict(REC, form="novel_form"))),
       [_fl("BAD-VALUE", p + "form must be one of 'known', 'variant', 'not_recognised', 'open_in_literature', not 'novel_form'")], 1)
    for k in ("form", "reader", "date"):
        fe(_ro(_rg(rec=drop(REC, k))), [_fl("MISSING-KEY", p + f"missing key {k!r}")] if k != "form" else
           [_fl("MISSING-KEY", p + "missing key 'form'")], 1)
    fe(_ro(_rg(rec=dict(REC, reader=""))), [_fl("BAD-VALUE", p + "reader must be a non-empty string")], 1)
    fe(_ro(_rg(rec=dict(REC, date=5))), [_fl("BAD-VALUE", p + "date must be a non-empty string")], 1)


@case("REC3", "per form: known and variant need result and a citation (variant also difference; known may carry one); "
              "not_recognised forbids result, citations and difference; control per form")
def _():
    p = " recognition: "
    clean(_ro(_rg(rec=REC)))
    clean(_ro(_rg(rec=dict(REC, difference="It differs in the hypothesis."))))
    var = dict(REC, form="variant", difference="It differs in the hypothesis.")
    clean(_ro(_rg(rec=var)))
    for k in ("result", "citations"):
        fe(_ro(_rg(rec=drop(REC, k))), [_fl("MISSING-KEY", p + f"missing key {k!r} (form 'known')")], 1)
        fe(_ro(_rg(rec=drop(var, k))), [_fl("MISSING-KEY", p + f"missing key {k!r} (form 'variant')")], 1)
    fe(_ro(_rg(rec=drop(var, "difference"))), [_fl("MISSING-KEY", p + "missing key 'difference' (form 'variant')")], 1)
    fe(_ro(_rg(rec=dict(REC, citations=[]))), [_fl("BAD-VALUE", p + "citations must hold at least one citation (form 'known')")], 1)
    fe(_ro(_rg(rec=dict(REC, citations="x"))), [_fl("BAD-VALUE", p + "citations must be a list")], 1)
    fe(_ro(_rg(rec=dict(REC, result=""))), [_fl("BAD-VALUE", p + "result must be a non-empty string")], 1)
    fe(_ro(_rg(rec=dict(var, difference=""))), [_fl("BAD-VALUE", p + "difference must be a non-empty string")], 1)
    nr = {"form": "not_recognised", "reader": "R", "date": "2026-11-23"}
    clean(_ro(_rg(rec=nr)))
    for k, v in (("result", "x"), ("citations", [CIT]), ("difference", "d")):
        fe(_ro(_rg(rec=dict(nr, **{k: v}))), [_fl("RECOGNITION-FORBIDDEN", p + f"key {k!r} is not allowed with form 'not_recognised'")], 1)


@case("REC4", "open_in_literature: needs result, a citation and a citation that says open; difference is optional; only for a "
              "result or named_statement (refused on object and when root_role is absent, which says the role is needed)")
def _():
    p = " recognition: "
    op = dict(REC, form="open_in_literature", citations=[OPENCIT])
    root = ("A.C", "baz")
    clean(_ro(_rg("named_statement", rec=op, root=root)))
    clean(_ro(_rg("named_statement", rec=dict(op, difference="Stated as a problem."), root=root)))
    clean(_ro(_rg("result", rec=op, root=("A.B", "foo"))))
    clean(_ro(_rg("result", rec=dict(op, difference="Stated as a problem."), root=("A.B", "foo"))))
    fe(_ro(_rg("object", rec=op, root=root)),
       [_fl("OPEN-ROLE", p + "form 'open_in_literature' needs root_role 'result' or 'named_statement' (root_role is 'object')")], 1)
    fe(_ro(_rg(None, rec=op, root=root)),
       [_fl("ROOT-ROLE-MISSING", ": no root_role (result, named_statement or object)"),
        _fl("OPEN-ROLE", p + "form 'open_in_literature' needs root_role 'result' or 'named_statement' (this group has no root_role: the role is needed)")], 1)
    fe(_ro(_rg("named_statement", rec=dict(op, citations=[CIT]), root=root)),
       [_fl("OPEN-NO-SAYS-OPEN", p + "form 'open_in_literature' needs a citation with says_open true")], 1)
    fe(_ro(_rg("named_statement", rec=dict(op, citations=[dict(CIT, says_open=False, source_date="2020-01-31")]), root=root)),
       [_fl("OPEN-NO-SAYS-OPEN", p + "form 'open_in_literature' needs a citation with says_open true")], 1)
    for k in ("result", "citations"):
        fe(_ro(_rg("named_statement", rec=drop(op, k), root=root)), [_fl("MISSING-KEY", p + f"missing key {k!r} (form 'open_in_literature')")], 1)


@case("REC4b", "open_in_literature on a result keeps the other rules: a citation that says open is still needed, result and citations are "
               "still needed, and `established` stays for a named statement only (a result carrying it is ESTABLISHED-ROLE)")
def _():
    p = " recognition: "
    op = dict(REC, form="open_in_literature", citations=[OPENCIT])
    root = ("A.B", "foo")
    fe(_ro(_rg("result", rec=dict(op, citations=[CIT]), root=root)),
       [_fl("OPEN-NO-SAYS-OPEN", p + "form 'open_in_literature' needs a citation with says_open true")], 1)
    for k in ("result", "citations"):
        fe(_ro(_rg("result", rec=drop(op, k), root=root)), [_fl("MISSING-KEY", p + f"missing key {k!r} (form 'open_in_literature')")], 1)
    fe(_ro(_rg("result", rec=dict(op, established="not_traced"), root=root)),
       [_fl("ESTABLISHED-ROLE", p + "established is only for root_role 'named_statement' (root_role is 'result')")], 1)


SD_MSG = "source_date must be a date YYYY, YYYY-MM or YYYY-MM-DD"


@case("NUL1", "a null result or difference is refused like an empty one, on every form that takes the key; on not_recognised the key's "
              "presence is the offence (RECOGNITION-FORBIDDEN) whatever the value, null, empty string or empty list; for a null or empty "
              "result or difference the BAD-VALUE finding co-fires and is pinned, in that order")
def _():
    p = " recognition: "
    bad = lambda k: [_fl("BAD-VALUE", p + f"{k} must be a non-empty string")]
    var = dict(REC, form="variant", difference="d")
    op = dict(REC, form="open_in_literature", citations=[OPENCIT])
    for form_rec, role, root in ((REC, "result", ("A.B", "foo")), (var, "result", ("A.B", "foo")),
                                 (op, "named_statement", ("A.C", "baz")), (op, "result", ("A.B", "foo"))):
        fe(_ro(_rg(role, rec=dict(form_rec, result=None), root=root)), bad("result"), 1)
        fe(_ro(_rg(role, rec=dict(form_rec, result=""), root=root)), bad("result"), 1)
    for form_rec, role, root in ((REC, "result", ("A.B", "foo")), (var, "result", ("A.B", "foo")),
                                 (op, "named_statement", ("A.C", "baz"))):
        fe(_ro(_rg(role, rec=dict(form_rec, difference=None), root=root)), bad("difference"), 1)
        fe(_ro(_rg(role, rec=dict(form_rec, difference=""), root=root)), bad("difference"), 1)
    nr = {"form": "not_recognised", "reader": "R", "date": "2026-11-23"}
    for k, vals in (("result", (None, "")), ("citations", ([],)), ("difference", (None, ""))):
        for v in vals:
            forb = _fl("RECOGNITION-FORBIDDEN", p + f"key {k!r} is not allowed with form 'not_recognised'")
            bv = _fl("BAD-VALUE", p + f"{k} must be a non-empty string")
            # BAD-VALUE co-fires with the FORBIDDEN finding when the value is null or empty (result, difference); a list has no such check
            fe(_ro(_rg(rec=dict(nr, **{k: v}))), [forb] if k == "citations" else [forb, bv], 1)


@case("NUL2", "a null in a citation: source, where, opened_by and opened_on are refused as BAD-VALUE (a non-empty string is needed), "
              "and so are a null url, source_date and says_open (the key is present, so its value is checked, not skipped)")
def _():
    c = " recognition citations[1]: "

    def two(cit):
        return _ro(_rg(rec=dict(REC, citations=[CIT, cit])))
    for k in ("source", "where", "opened_by", "opened_on"):
        fe(two(dict(CIT, **{k: None})), [_fl("BAD-VALUE", c + f"{k} must be a non-empty string")], 1)
    fe(two(dict(CIT, url=None)), [_fl("BAD-VALUE", c + "url must be a string starting https://")], 1)
    fe(two(dict(CIT, source_date=None)), [_fl("BAD-VALUE", c + SD_MSG)], 1)
    fe(two(dict(CIT, says_open=None)), [_fl("BAD-VALUE", c + "says_open must be true or false")], 1)


@case("RUN3", "the recognition line counts the groups at every depth, not the level-1 steps: a chain of levels 1 to 4 with a claim and a "
              "recognition of a different form at each depth, and a null-claim group beside it (counted in none); K+V+N+O+M = G")
def _():
    nr = {"form": "not_recognised", "reader": "R", "date": "2026-11-23"}
    var = dict(REC, form="variant", difference="d")
    op = dict(REC, form="open_in_literature", citations=[OPENCIT])
    L = lambda gid, level, parent, order, **kw: dict(_rg(gid=gid, order=order, **kw), level=level, parent=parent)
    groups = [L("g1", 1, "root", 1, rec=REC),
              L("g2", 2, "g1", 1, rec=var),
              L("g3", 3, "g2", 1, role="named_statement", root=("A.C", "baz"), rec=nr),
              L("g4", 4, "g3", 1, role="named_statement", root=("A.C", "baz"), rec=op),
              dict(G("g5", level=4, parent="g3", order=2), claim=None),
              L("g6", 4, "g3", 3)]   # a claim with no recognition: not written
    r = _ro(*groups)
    fe(r, [], 0)
    ok(_rl(1, 1, 1, 1, 1, 5) in r.lines, r.out)
    k, v, n, o, m, g = 1, 1, 1, 1, 1, 5
    eq(k + v + n + o + m, g, "the sum")


@case("SKC5", "the same root in two groups: an argument block in g2 does NOT satisfy g1's sketch (SKETCH-NO-ARGUMENT for g1), and each "
              "group may keep its own sketch on that root (no SKETCH-DUPLICATE across groups)")
def _():
    two = OL(G("g1"), G("g2", order=2))
    note1 = lambda body: NOTE(body=body)
    note2 = lambda body: NOTE(nid="02", group="g2", body=body)
    fe(go(notes={"01-a.md": note1("Sketch.\n" + _SB("01.b01") + "\n"),
                 "02-b.md": note2("Idea.\n" + _AB("02.b01") + "\n")}, outline=two, decls=DECLS_K),
       ["SKETCH-NO-ARGUMENT 01-a.md:7 block '01.b01': root A.B foo has no argument block in group 'g1'"], 1)
    clean(go(notes={"01-a.md": note1(_AS),
                    "02-b.md": note2("Idea.\n" + _AB("02.b01") + "\n\nSketch.\n" + _SB("02.b02") + "\n")}, outline=two, decls=DECLS_K))


@case("CIT1b", "source_date accepts YYYY, YYYY-MM and YYYY-MM-DD, each a real date (month 01-12, a day that exists, year 0 refused: "
               "Python's calendar starts at year 1, and the spec does not say otherwise); 2006-13, 2006-02-30, 06, 20061124, an empty "
               "string and non-strings are refused naming the key; 2024-02-29 is accepted and 2023-02-29 refused; opened_on stays a "
               "full date, a year or a year-month there is refused; says_open true needs a source_date and a year is enough")
def _():
    c = " recognition citations[1]: "

    def two(cit):
        return _ro(_rg(rec=dict(REC, citations=[CIT, cit])))
    for good in ("2006", "2006-11", "2006-11-24", "2024-02-29", "0001", "0001-01", "9999-12"):
        clean(two(dict(CIT, source_date=good)))
        clean(two(dict(CIT, source_date=good, says_open=True)))
    for bad in ("2006-13", "2006-00", "2006-02-30", "2023-02-29", "2006-11-00", "06", "20061124", "200611", "", "0000", "0000-01",
                "0000-01-01", "2006-1", "2006-11-2", " 2006", "2006 ", "2006-", "2006/11", 2006, None, True):
        fe(two(dict(CIT, source_date=bad)), [_fl("BAD-VALUE", c + SD_MSG)], 1)
    for bad in ("2006", "2006-11", "06", "0000-01-01"):
        fe(two(dict(CIT, opened_on=bad)), [_fl("BAD-VALUE", c + "opened_on must be a date YYYY-MM-DD")], 1)
    fe(two(dict(CIT, says_open=True)), [_fl("MISSING-KEY", c + "missing key 'source_date' (says_open is true)")], 1)
    op = dict(REC, form="open_in_literature")
    for sd in ("2006", "2006-11", "2006-11-24"):
        clean(_ro(_rg("named_statement", rec=dict(op, citations=[dict(OPENCIT, source_date=sd)]), root=("A.C", "baz"))))
    fe(_ro(_rg("named_statement", rec=dict(op, citations=[drop(OPENCIT, "source_date")]), root=("A.C", "baz"))),
       [_fl("MISSING-KEY", " recognition citations[0]: missing key 'source_date' (says_open is true)")], 1)


@case("CIT1", "a citation: source, where, opened_by, opened_on are required non-empty strings; opened_on is a real full "
              "YYYY-MM-DD date and source_date a real date that may also be a year or a year-month (CIT1b); says_open exactly true or false; url starts https://; an unknown key is refused; each names the "
              "group, the citation index and the key")
def _():
    c = " recognition citations[1]: "

    def two(cit):
        return _ro(_rg(rec=dict(REC, citations=[CIT, cit])))
    clean(two(dict(CIT, url="https://example.org/x", source_date="2019-12-31", says_open=False)))
    fe(two("x"), [_fl("BAD-VALUE", " recognition citations[1]: must be an object")], 1)
    fe(two(dict(CIT, extra=1)), [_fl("UNKNOWN-KEY", c + "unknown key 'extra'")], 1)
    for k in ("source", "where", "opened_by", "opened_on"):
        fe(two(drop(CIT, k)), [_fl("MISSING-KEY", c + f"missing key {k!r}")], 1)
        fe(two(dict(CIT, **{k: ""})), [_fl("BAD-VALUE", c + f"{k} must be a non-empty string")], 1)
        fe(two(dict(CIT, **{k: 4})), [_fl("BAD-VALUE", c + f"{k} must be a non-empty string")], 1)
    for bad in ("2026-02-30", "2026-2-3", "26-11-23", "2026/11/23", "2026-13-01", "2026-11-23 ", "٢026-11-23"):
        fe(two(dict(CIT, opened_on=bad)), [_fl("BAD-VALUE", c + "opened_on must be a date YYYY-MM-DD")], 1)
        fe(two(dict(CIT, source_date=bad)), [_fl("BAD-VALUE", c + SD_MSG)], 1)
    clean(two(dict(CIT, opened_on="2024-02-29")))
    for bad in (1, "true", None, "yes"):
        fe(two(dict(CIT, says_open=bad)), [_fl("BAD-VALUE", c + "says_open must be true or false")], 1)
    for bad in ("http://example.org", "example.org", "", 5):
        fe(two(dict(CIT, url=bad)), [_fl("BAD-VALUE", c + "url must be a string starting https://")], 1)
    fe(two(dict(CIT, says_open=True)), [_fl("MISSING-KEY", c + "missing key 'source_date' (says_open is true)")], 1)
    clean(two(dict(CIT, says_open=False)))


@case("WORD1", "novel and unprecedented, whole words in any case, in result or difference, are refused naming group, field and word; "
               "once per word per field")
def _():
    def line(field, w):
        return _fl("RECOGNITION-WORD-REFUSED", f" recognition {field}: {w!r} is never said of a statement")
    var = dict(REC, form="variant", difference="d")
    for w in ("novel", "unprecedented"):
        fe(_ro(_rg(rec=dict(REC, result=f"A {w} result"))), [line("result", w)], 1)
        fe(_ro(_rg(rec=dict(var, difference=f"It is {w.upper()}."))), [line("difference", w)], 1)
        fe(_ro(_rg(rec=dict(REC, result=f"{w.capitalize()}, and {w} again"))), [line("result", w)], 1)
    fe(_ro(_rg(rec=dict(var, result="Novel", difference="Unprecedented"))), [line("result", "novel"), line("difference", "unprecedented")], 1)


@case("WORD2", "near misses are not refused: novelty, novels, unprecedentedly, and a word joined to others by an underscore or digit")
def _():
    for t in ("The novelty of it", "Novels", "unprecedentedly", "a_novel", "novel2", "2novel", "x_unprecedented"):
        clean(_ro(_rg(rec=dict(REC, result=t))))


@case("WORD3", "new, original, first, assume, assumes, assumed (whole words, any case) in result or difference are RECOGNITION-WORD "
               "listings: exit 0, counted as warnings, naming group, field and word, once per word per field")
def _():
    def line(field, w):
        return _fl("RECOGNITION-WORD", f" recognition {field}: {w!r} (a prompt to the signer and the reviewer, not a verdict)")
    var = dict(REC, form="variant", difference="d")
    for w in ("new", "original", "first", "assume", "assumes", "assumed"):
        r = _ro(_rg(rec=dict(REC, result=f"The {w} statement")))
        fe(r, [line("result", w)], 0)
        eq(r.lines[-1], "1 notes, 0 findings, 1 warnings", w)
        fe(_ro(_rg(rec=dict(var, difference=f"{w.upper()} here, {w} again"))), [line("difference", w)], 0)
    fe(_ro(_rg(rec=dict(var, result="New and first", difference="First, then new"))),
       [line("result", "new"), line("result", "first"), line("difference", "first"), line("difference", "new")], 0)
    fe(_ro(_rg(rec=dict(REC, result="Assumes, assume and assumed"))),
       [line("result", "assumes"), line("result", "assume"), line("result", "assumed")], 0)


@case("WORD4", "near misses are not listed: Newton, renewal, news, firstly, originality, original_x, assumption, reassumes, unassumed, "
               "newer; a hyphen or an apostrophe is a word boundary")
def _():
    for t in ("Newton", "renewal", "news", "firstly", "originality", "original_x", "assumption", "reassumes", "unassumed", "newer",
              "3new", "first2"):
        clean(_ro(_rg(rec=dict(REC, result=t))))
    fe(_ro(_rg(rec=dict(REC, result="a non-new thing"))), [_fl("RECOGNITION-WORD", " recognition result: 'new' (a prompt to the signer and the reviewer, not a verdict)")], 0)
    fe(_ro(_rg(rec=dict(REC, result="Hardy's first"))), [_fl("RECOGNITION-WORD", " recognition result: 'first' (a prompt to the signer and the reviewer, not a verdict)")], 0)


@case("WORD5", "a word inside a single-backtick span IS checked (a span is code, but a person reads the word): `new` lists, `novel` "
               "refuses; the words are looked for only in result and difference, not in source, where or reader")
def _():
    fe(_ro(_rg(rec=dict(REC, result="The `new` lemma"))),
       [_fl("RECOGNITION-WORD", " recognition result: 'new' (a prompt to the signer and the reviewer, not a verdict)")], 0)
    fe(_ro(_rg(rec=dict(REC, result="The `novel` lemma"))),
       [_fl("RECOGNITION-WORD-REFUSED", " recognition result: 'novel' is never said of a statement")], 1)
    clean(_ro(_rg(rec=dict(REC, citations=[dict(CIT, source="New novel original", where="First, assumed")], reader="New", date="2026-11-23"))))


@case("EST1", "established is 'not_traced' or an object {by, reader, date}; by resolves to exactly one row whose kind is theorem or "
              "lemma; an unknown key, a missing key, a bad by, an unresolved or ambiguous by and a wrong kind are refused; it is "
              "allowed under any form, for a named_statement only")
def _():
    root = ("A.C", "baz")
    p = " recognition established: "
    est = {"by": R("A.B", "foo"), "reader": "R", "date": "2026-11-23"}
    nr = {"form": "not_recognised", "reader": "R", "date": "2026-11-23"}
    clean(_ro(_rg("named_statement", rec=dict(REC, established="not_traced"), root=root)))
    clean(_ro(_rg("named_statement", rec=dict(REC, established=est), root=root)))
    clean(_ro(_rg("named_statement", rec=dict(REC, established=dict(est, by=R("A.E", "lem"))), root=root)))
    for form_rec in (dict(nr, established="not_traced"), dict(nr, established=est),
                     dict(REC, form="variant", difference="d", established=est)):
        clean(_ro(_rg("named_statement", rec=form_rec, root=root)))
    fe(_ro(_rg("named_statement", rec=dict(REC, established="traced"), root=root)),
       [_fl("BAD-VALUE", p + "must be the string 'not_traced' or an object")], 1)
    fe(_ro(_rg("named_statement", rec=dict(REC, established=3), root=root)),
       [_fl("BAD-VALUE", p + "must be the string 'not_traced' or an object")], 1)
    fe(_ro(_rg("named_statement", rec=dict(REC, established=dict(est, extra=1)), root=root)),
       [_fl("UNKNOWN-KEY", p + "unknown key 'extra'")], 1)
    for k in ("by", "reader", "date"):
        fe(_ro(_rg("named_statement", rec=dict(REC, established=drop(est, k)), root=root)), [_fl("MISSING-KEY", p + f"missing key {k!r}")], 1)
    fe(_ro(_rg("named_statement", rec=dict(REC, established=dict(est, reader="")), root=root)),
       [_fl("BAD-VALUE", p + "reader must be a non-empty string")], 1)
    fe(_ro(_rg("named_statement", rec=dict(REC, established=dict(est, by="A.B.foo")), root=root)),
       [_fl("BAD-VALUE", " recognition established by: must be an object with non-empty string module and name")], 1)
    fe(_ro(_rg("named_statement", rec=dict(REC, established=dict(est, by=R("A.B", "nope"))), root=root)),
       [_fl("UNRESOLVED", " recognition established by A.B nope: no row in decls.tsv")], 1)
    fe(_ro(_rg("named_statement", rec=dict(REC, established=dict(est, by=R("A.D", "dup"))), root=root)),
       [_fl("AMBIGUOUS", " recognition established by A.D dup: 2 rows; candidates (first_line, last_line): (1, 3), (7, 9)")], 1)
    for by, kind in ((R("A.C", "baz"), "def"), (R("A.E", "stru"), "structure"), (R("A.E", "ind"), "inductive"), (R("A.E", "mys"), "")):
        fe(_ro(_rg("named_statement", rec=dict(REC, established=dict(est, by=by)), root=root)),
           [_fl("ESTABLISHED-KIND", f" recognition established by {by['module']} {by['name']} has kind {kind!r} (a theorem or lemma is needed)")], 1)


@case("EST2", "established on a group whose root_role is not named_statement is refused (result, object, or absent: the role is needed)")
def _():
    p = " recognition: established is only for root_role 'named_statement' ("
    est = {"by": R("A.B", "foo"), "reader": "R", "date": "2026-11-23"}
    fe(_ro(_rg("result", rec=dict(REC, established="not_traced"))), [_fl("ESTABLISHED-ROLE", p + "root_role is 'result')")], 1)
    fe(_ro(_rg("object", rec=dict(REC, established=est), root=("A.C", "baz"))), [_fl("ESTABLISHED-ROLE", p + "root_role is 'object')")], 1)
    fe(_ro(_rg(None, rec=dict(REC, established="not_traced"))),
       [_fl("ROOT-ROLE-MISSING", ": no root_role (result, named_statement or object)"),
        _fl("ESTABLISHED-ROLE", p + "this group has no root_role: the role is needed)")], 1)


def _rl(k, v, n, o, m, g):
    return f"recognition: {k} known, {v} variant, {n} not recognised, {o} open in literature, {m} not written, of {g} groups with a claim"


@case("RUN1", "the run prints `recognition: K known, V variant, N not recognised, O open in literature, M not written, of G groups "
              "with a claim`, counted by the tool, right after the `claim basis:` line; a claim with no recognition counts M; "
              "a null claim counts in none")
def _():
    nr = {"form": "not_recognised", "reader": "R", "date": "2026-11-23"}
    var = dict(REC, form="variant", difference="d")
    op = dict(REC, form="open_in_literature", citations=[OPENCIT])
    r = _ro(_rg(rec=REC), _rg(rec=var, gid="g2", order=2), _rg("named_statement", rec=nr, gid="g3", order=3, root=("A.C", "baz")),
            _rg("named_statement", rec=op, gid="g4", order=4, root=("A.C", "baz")), _rg(gid="g5", order=5), _rg(rec=REC, gid="g6", order=6),
            G("g7", order=7))
    fe(r, [], 0)
    ok(_rl(2, 1, 1, 1, 1, 6) in r.lines, r.out)
    i = r.lines.index(_rl(2, 1, 1, 1, 1, 6))
    ok(r.lines[i - 1].startswith("claim basis: "), r.out)
    r = _ro(G("g1"))
    ok(_rl(0, 0, 0, 0, 0, 0) in r.lines, r.out)
    r = _ro(_rg(None))
    ok(_rl(0, 0, 0, 0, 1, 1) in r.lines, r.out)
    r = _ro(_rg(rec=dict(REC, form="nonsense")))
    ok(_rl(0, 0, 0, 0, 1, 1) in r.lines, "an unusable form counts as not written: " + r.out)


@case("RUN2", "the sum K + V + N + O + M = G is asserted: a count that does not add up is SUM-RECOGNITION, exit 1, planted through the "
              "counting function's input; the counting function counts each of the five forms")
def _():
    eq(_recognition_counts(["known", "variant", "not_recognised", "open_in_literature", None, None]), (1, 1, 1, 1, 2, 6), "counts")
    eq(_recognition_sum_finding(["known", "open_in_literature", None]), None, "an honest list")
    f = _recognition_sum_finding(["known", "bogus", None])
    eq(f and (f[0], f[4]), ("SUM-RECOGNITION", ERROR), "planted")
    eq(f and f[3], "1 known + 0 variant + 0 not recognised + 0 open in literature + 1 not written is 2, not 3 groups with a claim", "text")
    eq(_recognition_sum_finding([]), None, "empty")


@case("LIST1", "a listing (ROOT-ROLE-MISSING, RECOGNITION-WORD) never changes the exit code and an error beside it still exits 1; "
               "the note-level and per-note lines are unchanged")
def _():
    r = _ro(_rg(None, rec=dict(REC, result="The new thing")))
    eq((r.rc, [x.split(" ")[0] for x in r.f]), (0, ["ROOT-ROLE-MISSING", "RECOGNITION-WORD"]), "listings")
    eq(r.lines[-1], "1 notes, 0 findings, 2 warnings", "count")
    ok("note 01 header ok, blocks 0" in r.lines, r.out)
    r = _ro(_rg("result", rec=dict(REC, result="The new thing"), root=("A.B", "nope")))
    eq((r.rc, [x.split(" ")[0] for x in r.f]), (1, ["UNRESOLVED", "RECOGNITION-WORD"]), "an error beside a listing")


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
    r = _add("Some text.\n\n## 2026-11-21 First add\nA.\n\nMore text.\n\n### 2026-11-22 Second add\nB.\n")
    eq((r.f, r.rc), (["ADDITION 01-a.md:7 4 lines, heading 2026-11-21 First add",
                      "ADDITION 01-a.md:12 3 lines, heading 2026-11-22 Second add"], 0), r.out)
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


@case("ADD12", "lower bound: the date of the BASE header's `release` (F3: the published one) when it is `rh-YYYY-MM-DD` and real; a date before "
               "it is a BYTE-DIFF naming the window, a date equal to it is accepted; the upper bound still applies")
def _():
    rel = dict(release="rh-2026-11-20", base=NOTE(body="Some text.\nMore text.\n", release="rh-2026-11-20"))
    r = _add("Some text.\nMore text.\n\n## 2026-11-19 Added\nX.\n", **rel)
    eq((r.f, r.rc), ([_bdt(8, 7, "<no line>", "'\\n'",
                           "; the added heading's date 2026-11-19 is outside the window 2026-11-20 to 2026-11-24")], 1), r.out)
    r = _add("Some text.\nMore text.\n\n## 2026-11-20 Added\nX.\n", **rel)
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-20 Added"], 0), "equal to the release date: " + r.out)
    r = _add("Some text.\nMore text.\n\n## 2026-11-25 Added\nX.\n", **rel)
    eq((r.f, r.rc), ([_bdt(8, 7, "<no line>", "'\\n'",
                           "; the added heading's date 2026-11-25 is outside the window 2026-11-20 to 2026-11-24")], 1), r.out)


@case("ADD13", "a BASE release that does not parse as rh-YYYY-MM-DD with a real date gives NO lower bound: a date far in the past is accepted "
               "for rel-1, rh-1, rh-2026-13-45, rh-2026-02-30, a prefix-only and a suffixed release")
def _():
    for rel in ("rel-1", "rh-1", "rh-2026-13-45", "rh-2026-02-30", "x-rh-2026-11-20", "rh-2026-11-20-b", "RH-2026-11-20"):
        r = _add("Some text.\nMore text.\n\n## 2001-01-01 Added\nX.\n", release=rel,
                 base=NOTE(body="Some text.\nMore text.\n", release=rel))
        eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2001-01-01 Added"], 0), rel + " " + r.out)


@case("ADD14", "a CRLF note with an addition: CRLF endings are part of the line compare, the heading text and count carry no carriage return")
def _():
    crlf = T0.replace("\n", "\r\n")
    cur = NOTE(body="Some text.\nMore text.\n\n## 2026-11-22 Added\nNew words.\n").replace("\n", "\r\n")
    r = go(notes={"01-a.md": cur}, committed={"01-a.md": crlf}, base="HEAD", today=TODAY)
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-22 Added"], 0), r.out)
    r = go(notes={"01-a.md": cur.replace("Some text.\r\n", "Some text.\n", 1)}, committed={"01-a.md": crlf}, base="HEAD", today=TODAY)
    eq(r.rc, 1, "a line ending changed in a base line is not an addition: " + r.out)


@case("ADD15", "alignment (F2): the LEFT-greedy alignment (a repeated base line takes its EARLIEST match) is tried first, so an addition whose "
               "last line repeats a base line is a legal run when the repeat comes after the original; the same words before the original "
               "leave it unmatched as a second run without a heading on the left; the RIGHT-greedy alignment, which takes the LATEST "
               "match, reads one run whose last line touches the published line after it (F5), so both fail and the LEFT message is shown")
def _():
    r = _add("Some text.\nMore text.\n\n## 2026-11-22 Extra\nMore text.\n")
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-22 Extra"], 0), r.out)
    r = _add("Some text.\n\n## 2026-11-22 Extra\nMore text.\nMore text.\n")
    eq((r.f, r.rc), ([_bd(7, 6, "'More text.\\n'", "'\\n'") + "; the inserted run at line 7 has no blank line after it"], 1), r.out)


@case("ADD16", "one bad run makes the whole note BYTE-DIFF even beside a legal one, and no ADDITION line is printed for that note; "
               "the first bad run is the one named")
def _():
    r = _add("Some text.\n\n## 2026-11-21 Good\nA.\n\nMore text.\n\nNo heading here.\n")
    eq((r.f, r.rc), ([_bd(12, 11, "<no line>", "'\\n'")], 1), r.out)
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


@case("ADD24", "F1: an inserted unbalanced fence marker may not wrap published text in a code block. The probe (a dated heading run and an opening "
               "fence line, the published lines unchanged, then a dated heading run and a closing fence) is a BYTE-DIFF whose message names "
               "the run that flipped the fence state of a published line; a fence BALANCED inside one run is still an ADDITION; a closing "
               "marker inserted before a published fence flips the other way (inside at HEAD, outside now)")
def _():
    base = "# Note\n\n## Body\n\nintro\nsecret claim\nmore\n"
    wrap = "intro\n\n## 2026-11-10 x\n```\n\nsecret claim\nmore\n\n## 2026-11-11 y\n```\n"
    r = _add(wrap, base=base)
    eq((r.f, r.rc), ([_bdt(7, 6, "'secret claim\\n'", "'\\n'",
                           "; the inserted run at line 7 changes whether line 6 of the text without anchors is inside a code fence "
                           "(outside at HEAD, inside now)")], 1), r.out)
    ok("byte check: 0 notes equal to HEAD, 0 new, 0 additions" in r.lines, r.out)
    r = _add("intro\n\n## 2026-11-10 x\n```\ncode\n```\n\nsecret claim\nmore\n", base=base)
    eq((r.f, r.rc), (["ADDITION 01-a.md:7 6 lines, heading 2026-11-10 x"], 0), "balanced inside one run: " + r.out)
    fbase = "# Note\n\n## Body\n\n````\nsecret\n`````\n"   # a 4-tick opener and a 5-tick closer: every line is unique
    r = _add("## 2026-11-10 x\n```\n\n````\nsecret\n`````\n", base=fbase)   # the inserted 3-tick opener is closed by the published opener
    ok(_bdt(6, 5, "'````\\n'", "'## 2026-11-10 x\\n'",
            "; the inserted run at line 6 changes whether line 6 of the text without anchors is inside a code fence "
            "(inside at HEAD, outside now)") in r.f, r.out)
    ok(not any(x.startswith("ADDITION") for x in r.f), "no ADDITION: " + r.out)
    eq(r.rc, 1, "exit code")


@case("ADD25", "F1: a fence opened in a run and never closed. Followed by published lines it swallows them: BYTE-DIFF naming the run. At the very end "
               "of the note no published line is swallowed, so the byte check lists the run as before and the unclosed fence is "
               "the UNCLOSED-FENCE error of rh_anchor (exit 1 either way)")
def _():
    base = "# Note\n\n## Body\n\nintro\nsecret claim\nmore\n"
    r = _add("intro\n\n## 2026-11-10 x\n```\n\nsecret claim\nmore\n", base=base)
    ok(_bdt(7, 6, "'secret claim\\n'", "'\\n'",
            "; the inserted run at line 7 changes whether line 6 of the text without anchors is inside a code fence "
            "(outside at HEAD, inside now)") in r.f, r.out)
    ok(not any(x.startswith("ADDITION") for x in r.f), "no ADDITION: " + r.out)
    eq(r.rc, 1, "exit code")
    r = _add("intro\nsecret claim\nmore\n\n## 2026-11-10 x\n```\ncode\n", base=base)
    ok("UNCLOSED-FENCE 01-a.md:11 The code fence opened on line 11 is never closed." in r.f, r.out)
    ok("ADDITION 01-a.md:9 4 lines, heading 2026-11-10 x" in r.f, r.out)
    eq(r.rc, 1, "exit code at the end")


@case("ADD26", "F2: any order-preserving alignment of the base into the current may make every run legal. Two published blank lines with the run "
               "inserted between them: the left-greedy match gives the second blank to the blank that ends the run and leaves a lone blank "
               "line as a headingless run; the right-greedy alignment reads one legal run (a blank, the heading, a line). The first two probes "
               "(an inserted heading directly after `A`, then the blank the left match takes from the base; the same at the end of a base "
               "that ends in a blank line) have no blank line before the heading, so F5 refuses them on both alignments. "
               "When both alignments are legal the LEFT one is listed")
def _():
    b1 = "# Note\n\n## Body\n\nA\n\nB\n"
    r = _add("A\n## 2026-11-10 add\n\nbody\n\nB\n", base=b1)
    eq((r.f, r.rc), ([_bd(7, 6, "'\\n'", "'## 2026-11-10 add\\n'") + "; the inserted run at line 7 has no blank line before it"], 1), "probe 1: " + r.out)
    r = _add("A\n\nB\n## 2026-11-10 add\n\nbody\n\n", base="# Note\n\n## Body\n\nA\n\nB\n\n")
    eq((r.f, r.rc), ([_bd(9, 8, "'\\n'", "'## 2026-11-10 add\\n'") + "; the inserted run at line 9 has no blank line before it"], 1), "probe 3: " + r.out)
    r = _add("A\n\n## 2026-11-10 d\nx\n\n\nB\n", base="# Note\n\n## Body\n\nA\n\n\nB\n")
    eq((r.f, r.rc), (["ADDITION 01-a.md:7 3 lines, heading 2026-11-10 d"], 0), "two blanks, right alignment: " + r.out)
    ok("byte check: 0 notes equal to HEAD, 0 new, 1 additions" in r.lines, r.out)
    r = _add("A\n\n## 2026-11-10 d\n\nx\n\nB\n", base=b1)
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 4 lines, heading 2026-11-10 d"], 0), "both legal, left listed: " + r.out)


@case("ADD27", "F2: a true removal is a BYTE-DIFF under both alignments (the base is not a subsequence of the current), at the first positional "
               "difference as before; and a headingless run stays a BYTE-DIFF when NEITHER alignment makes it legal")
def _():
    r = _add("A\n## 2026-11-10 add\n\nbody\n", base="# Note\n\n## Body\n\nA\n\nB\n")
    eq((r.f, r.rc), ([_bd(7, 6, "'\\n'", "'## 2026-11-10 add\\n'")], 1), "removal: " + r.out)
    r = _add("A\n\nB\nx\n", base="# Note\n\n## Body\n\nA\n\nB\n")
    eq((r.f, r.rc), ([_bd(9, 8, "<no line>", "'x\\n'")], 1), "no heading in either alignment: " + r.out)


@case("ADD28", "F3: the floor of the date window is read from the BASE text's header (the published one), not from the current header: "
               "a release edited in the current note to an early date leaves the base's later floor; a base with no release date "
               "(or no header at all, or an impossible date) has no floor whatever the current header says")
def _():
    body = "Some text.\nMore text.\n\n## 2026-11-10 Added\nX.\n"
    low = "; the added heading's date 2026-11-10 is outside the window 2026-11-20 to 2026-11-24"
    r = go(notes={"01-a.md": NOTE(body=body, release="rh-2026-11-01")},
           committed={"01-a.md": NOTE(body="Some text.\nMore text.\n", release="rh-2026-11-20")}, base="HEAD", today=TODAY)
    eq((r.f, r.rc), ([_bdt(8, 7, "<no line>", "'\\n'", low)], 1), "edited early: " + r.out)
    r = go(notes={"01-a.md": NOTE(body=body, release="rel-1")},
           committed={"01-a.md": NOTE(body="Some text.\nMore text.\n", release="rh-2026-11-20")}, base="HEAD", today=TODAY)
    eq((r.f, r.rc), ([_bdt(8, 7, "<no line>", "'\\n'", low)], 1), "reworded: " + r.out)
    for base_rel in ("rel-1", "rh-2026-02-30"):
        r = go(notes={"01-a.md": NOTE(body=body, release="rh-2026-11-20")},
               committed={"01-a.md": NOTE(body="Some text.\nMore text.\n", release=base_rel)}, base="HEAD", today=TODAY)
        eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-10 Added"], 0), "base release " + base_rel + ": " + r.out)
    r = _add(body, release="rh-2026-11-20")
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-10 Added"], 0), "base with no header: " + r.out)


@case("ADD29", "F4: EVERY real calendar date in the heading must lie in the window, not only the first: a later date, an earlier one, or a "
               "middle one outside it is a BYTE-DIFF naming the first date (in file order) that is outside; an impossible date beside a "
               "real one is still skipped (ADDITION), before or after it")
def _():
    far = "; the added heading's date 2099-01-01 is outside the window up to 2026-11-24 (no lower bound)"
    for h in ("2026-11-10 and 2099-01-01", "2099-01-01 and 2026-11-10", "2026-11-10 then 2099-01-01 then 2026-11-11"):
        r = _add("Some text.\nMore text.\n\n## " + h + "\nX.\n")
        eq((r.f, r.rc), ([_bdt(8, 7, "<no line>", "'\\n'", far)], 1), h + " " + r.out)
    r = go(notes={"01-a.md": NOTE(body="Some text.\nMore text.\n\n## 2026-11-22 and 2026-11-01\nX.\n", release="rh-2026-11-20")},
           committed={"01-a.md": NOTE(body="Some text.\nMore text.\n", release="rh-2026-11-20")}, base="HEAD", today=TODAY)
    eq((r.f, r.rc), ([_bdt(8, 7, "<no line>", "'\\n'",
                           "; the added heading's date 2026-11-01 is outside the window 2026-11-20 to 2026-11-24")], 1), "below the floor: " + r.out)
    for h in ("2026-13-45 then 2026-11-10", "2026-11-10 then 2026-13-45"):
        r = _add("Some text.\nMore text.\n\n## " + h + "\nX.\n")
        eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading " + h], 0), h + " " + r.out)


F5BODY = ("| File | SHA |\n|---|---|\n| a | 1 |\n| b | 2 |\n\n- item one\n  continued\n- item two\n\nPara one\nPara two\n")
F5BASE = "# Note\n\n## Body\n\n" + F5BODY   # a table (lines 6 to 9 on disk), a list with an indented continuation, a paragraph


def _f5(after_line, crlf=False):
    """The current note: F5BODY with a dated run (heading and one line) inserted after its `after_line`-th line, against F5BASE."""
    lines = F5BODY.splitlines(True)
    cur, base = NOTE(body="".join(lines[:after_line]) + "## 2026-11-10 x\nbody\n" + "".join(lines[after_line:])), F5BASE
    if crlf:
        cur, base = cur.replace("\n", "\r\n"), base.replace("\n", "\r\n")
    return go(notes={"01-a.md": cur}, committed={"01-a.md": base}, base="HEAD", today=TODAY)


@case("ADD30", "F5: a dated run may not touch published text: the line before its first non-blank line and the line after its last one must "
               "each be blank or the edge of the text. Probes: a run between two table rows, a run between a list item and its indented "
               "continuation (no blank line BEFORE), a run with no blank line after it right before a published paragraph")
def _():
    r = _f5(3)
    eq((r.f, r.rc), ([_bd(9, 8, "'| b | 2 |\\n'", "'## 2026-11-10 x\\n'") + "; the inserted run at line 9 has no blank line before it"], 1), "table: " + r.out)
    r = _f5(6)
    eq((r.f, r.rc), ([_bd(12, 11, "'  continued\\n'", "'## 2026-11-10 x\\n'") + "; the inserted run at line 12 has no blank line before it"], 1),
       "list: " + r.out)
    r = _f5(9)
    eq((r.f, r.rc), ([_bd(15, 14, "'Para one\\n'", "'## 2026-11-10 x\\n'") + "; the inserted run at line 15 has no blank line after it"], 1),
       "paragraph: " + r.out)


@case("ADD31", "F5: the same probes with CRLF line endings are refused the same way (the blank test reads the line without its ending)")
def _():
    r = _f5(3, crlf=True)
    eq((r.f, r.rc), ([_bd(9, 8, "'| b | 2 |\\r\\n'", "'## 2026-11-10 x\\r\\n'") + "; the inserted run at line 9 has no blank line before it"], 1),
       "table: " + r.out)
    r = _f5(9, crlf=True)
    eq((r.f, r.rc), ([_bd(15, 14, "'Para one\\r\\n'", "'## 2026-11-10 x\\r\\n'") + "; the inserted run at line 15 has no blank line after it"], 1),
       "paragraph: " + r.out)


@case("ADD32", "F5 controls: a run with a blank line on both sides between two paragraphs, a run at the end of the note, a run whose own last line "
               "is blank (the next published line follows a blank) are ADDITIONs; a run right after the last published line with no blank "
               "before it is a BYTE-DIFF; an anchor line between a run and a published line does not count as the blank line between them")
def _():
    r = _add("First.\n\n## 2026-11-22 Added\nExtra.\n\nSecond.\n", base=T2)
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-22 Added"], 0), "between paragraphs: " + r.out)
    r = _add("Some text.\nMore text.\n\n## 2026-11-22 Added\nX.\n")
    eq((r.f, r.rc), (["ADDITION 01-a.md:8 3 lines, heading 2026-11-22 Added"], 0), "at the end: " + r.out)
    r = _add("Some text.\n\n## 2026-11-22 d\nX.\n\nMore text.\n")
    eq((r.f, r.rc), (["ADDITION 01-a.md:7 4 lines, heading 2026-11-22 d"], 0), "own last line blank: " + r.out)
    r = _add("Some text.\nMore text.\n## 2026-11-22 Added\nX.\n")
    eq((r.f, r.rc), ([_bd(8, 7, "<no line>", "'## 2026-11-22 Added\\n'") + "; the inserted run at line 8 has no blank line before it"], 1),
       "no blank before: " + r.out)
    tail = go(notes={"01-a.md": NOTE(body="Some text.\nMore text.\n\n## 2026-11-22 Added\nX.\n" + BL() + "\nTail.\n")},
              committed={"01-a.md": "# Note\n\n## Body\n\nSome text.\nMore text.\nTail.\n"}, base="HEAD", today=TODAY)
    ok(_bd(8, 7, "'Tail.\\n'", "'\\n'") + "; the inserted run at line 8 has no blank line after it" in tail.f, "anchor between: " + tail.out)
    ok(not any(x.startswith("ADDITION") for x in tail.f), "no ADDITION: " + tail.out)


@case("ADD33", "F6: a run that begins above the first published non-blank line (above the H1 title) is a BYTE-DIFF whose message names it")
def _():
    r = go(notes={"01-a.md": "## 2026-11-10 x\nbody\n\n" + NOTE(body="Some text.\nMore text.\n")}, committed={"01-a.md": T0},
           base="HEAD", today=TODAY)
    ok(_bd(1, 1, "'# Note\\n'", "'## 2026-11-10 x\\n'") + "; the inserted run at line 1 begins above the first published non-blank line" in r.f, r.out)
    ok(not any(x.startswith("ADDITION") for x in r.f), "no ADDITION: " + r.out)
    eq(r.rc, 1, "exit code")
    r = go(notes={"01-a.md": "\n" + NOTE(body="Some text.\nMore text.\n")}, committed={"01-a.md": T0}, base="HEAD", today=TODAY)
    eq(r.rc, 1, "a lone blank line above the title is not a dated run: " + r.out)


@case("ORDER", "notes are checked in name order whatever the directory order; each note's findings come before its note line, "
               "in line order")
def _():
    bad = NOTE(level=3)
    r = go(notes={"02-b.md": bad.replace('"id":"01"', '"id":"02"'), "01-a.md": bad})
    eq(r.lines[:4], ["HEADER-PROBLEM 01-a.md:2 level: must be 0, 1 or 2", "note 01 header FAILED, blocks 0",
                     "HEADER-PROBLEM 02-b.md:2 level: must be 0, 1 or 2", "note 02 header FAILED, blocks 0"], "order")
    r = go(notes={"01-a.md": NOTE(level=3, body="Some text.\n<!-- rh-block {bad} -->\n")})
    eq([x.split(" ")[0] + " " + x.split(" ")[1] for x in r.f], ["HEADER-PROBLEM 01-a.md:2", "MALFORMED 01-a.md:7"], "by line")


# ---- F25a: the sketch kind in the cross-checks; an argument on a root that is not a theorem or lemma is listed
# Notes made by NOTE() have the first body line on line 6, so a block anchored after one-line paragraphs sits on a literal line.
def _AB(bid="01.b01", decls=None, reader="R"):
    return BL(bid, kind="argument", reader=reader, date="2026-11-23", decls=[R("A.B", "foo")] if decls is None else decls)


def _SB(bid="01.b02", decls=None, **kw):
    d = dict(kind="sketch", reader="R", date="2026-11-23", decls=[R("A.B", "foo")] if decls is None else decls, basis="source")
    d.update(kw)
    return BL(bid, **d)


_AS = "Idea.\n" + _AB() + "\n\nSketch.\n" + _SB() + "\n"   # the argument is on line 7, the sketch on line 10
FOO, BAR, BAZ = R("A.B", "foo"), R("A.B", "bar"), R("A.C", "baz")


def _sx(body, outline=None, decls=DECLS_K, **hdr):
    return go(notes={"01-a.md": NOTE(body=body, **hdr)}, outline=OL(G("g1")) if outline is None else outline, decls=decls)


NOPROOF = "ARGUMENT-NO-PROOF 01-a.md:{} block '01.b01': root {} has kind {!r}, not a theorem or lemma: say in the argument which proof inside it was read"


@case("SKC1", "a sketch with an argument on its root passes: with or without a claim, with more decls than the root, with a run of two, "
              "and when the argument is in another note of the group by another reader")
def _():
    clean(_sx(_AS))
    clean(_sx(_AS, outline=OL(G("g1", claim=CLAIM))))
    clean(_sx("Idea.\n" + _AB() + "\n\nSketch.\n" + _SB(decls=[FOO, BAR]) + "\n"))
    clean(_sx("Idea.\n" + _AB() + "\n\nOne.\n\nTwo.\n" + _SB(span=2) + "\n"))
    clean(go(notes={"01-a.md": NOTE(body="Idea.\n" + _AB(reader="X") + "\n"),
                    "02-b.md": NOTE(nid="02", body="Sketch.\n" + _SB("02.b01") + "\n")}, outline=OL(G("g1")), decls=DECLS_K))


@case("SKC2", "SKETCH-NO-ARGUMENT: a sketch whose root has no argument block in its group is refused; an argument of another group, or one "
              "whose decls do not hold the root, does not count")
def _():
    msg = "SKETCH-NO-ARGUMENT 01-a.md:7 block '01.b01': root A.B foo has no argument block in group 'g1'"
    fe(_sx("Sketch.\n" + _SB("01.b01") + "\n"), [msg], 1)
    two = OL(G("g1"), G("g2", order=2, roots=[BAR]))
    fe(go(notes={"01-a.md": NOTE(body="Sketch.\n" + _SB("01.b01") + "\n"),
                 "02-b.md": NOTE(nid="02", group="g2", body="Idea.\n" + _AB("02.b01") + "\n")}, outline=two, decls=DECLS_K), [msg], 1)
    fe(_sx("Idea.\n" + _AB(decls=[BAR]) + "\n\nSketch.\n" + _SB() + "\n"),
       ["SKETCH-NO-ARGUMENT 01-a.md:10 block '01.b02': root A.B foo has no argument block in group 'g1'"], 1)


@case("SKC3", "SKETCH-DUPLICATE: a second sketch on one root, in the same note or another, is refused naming both block ids; "
              "two roots of one group may each have one; a sketch on two roots both taken gives one finding per root")
def _():
    body = "Idea.\n" + _AB() + "\n\nS1.\n" + _SB("01.b02") + "\n\nS2.\n" + _SB("01.b03") + "\n"
    fe(_sx(body), ["SKETCH-DUPLICATE 01-a.md:13 block '01.b03': root A.B foo already has the sketch '01.b02' (at 01-a.md:10)"], 1)
    fe(go(notes={"01-a.md": NOTE(body=_AS), "02-b.md": NOTE(nid="02", body="S.\n" + _SB("02.b01") + "\n")},
          outline=OL(G("g1")), decls=DECLS_K),
       ["SKETCH-DUPLICATE 02-b.md:7 block '02.b01': root A.B foo already has the sketch '01.b02' (at 01-a.md:10)"], 1)
    two = OL(G("g1", roots=[FOO, BAR]))
    arg = "Idea.\n" + _AB(decls=[FOO, BAR]) + "\n\nS1.\n" + _SB("01.b02", decls=[FOO]) + "\n\nS2.\n" + _SB("01.b03", decls=[BAR]) + "\n"
    clean(_sx(arg, outline=two))
    both = "Idea.\n" + _AB(decls=[FOO, BAR]) + "\n\nS1.\n" + _SB("01.b02", decls=[FOO, BAR]) + "\n\nS2.\n" + _SB("01.b03", decls=[FOO, BAR]) + "\n"
    fe(_sx(both, outline=two),
       ["SKETCH-DUPLICATE 01-a.md:13 block '01.b03': root A.B foo already has the sketch '01.b02' (at 01-a.md:10)",
        "SKETCH-DUPLICATE 01-a.md:13 block '01.b03': root A.B bar already has the sketch '01.b02' (at 01-a.md:10)"], 1)


@case("SKC4", "SKETCH-ROLE: the role of the group decides when it has one (only result), else the kind of the root (only theorem or lemma), "
              "each root of a null-claim group by its own kind; the argument on a definition is listed beside it")
def _():
    arg_baz = "Idea.\n" + _AB(decls=[BAZ]) + "\n\nSketch.\n" + _SB(decls=[BAZ]) + "\n"
    kind = "SKETCH-ROLE 01-a.md:10 block '01.b02': root {} has kind {!r}; a sketch is only for a theorem or lemma"
    fe(_sx(arg_baz, outline=OL(G("g1", roots=[BAZ]))),
       [NOPROOF.format(7, "A.C baz", "def"), kind.format("A.C baz", "def")], 1)
    stru = "Idea.\n" + _AB(decls=[R("A.E", "stru")]) + "\n\nSketch.\n" + _SB(decls=[R("A.E", "stru")]) + "\n"
    fe(_sx(stru, outline=OL(G("g1", roots=[R("A.E", "stru")]))),
       [NOPROOF.format(7, "A.E stru", "structure"), kind.format("A.E stru", "structure")], 1)
    lem = "Idea.\n" + _AB(decls=[R("A.E", "lem")]) + "\n\nSketch.\n" + _SB(decls=[R("A.E", "lem")]) + "\n"
    clean(_sx(lem, outline=OL(G("g1", roots=[R("A.E", "lem")]))))
    clean(_sx(lem, outline=OL(_rg("result", root=("A.E", "lem")))))
    for role in ("named_statement", "object"):
        fe(_sx(arg_baz, outline=OL(_rg(role, root=("A.C", "baz")))),
           [NOPROOF.format(7, "A.C baz", "def"),
            f"SKETCH-ROLE 01-a.md:10 block '01.b02': root A.C baz: root_role is {role!r}; a sketch is only for 'result'"], 1)
    multi = OL(G("g1", roots=[FOO, BAZ]))
    both = "Idea.\n" + _AB(decls=[FOO, BAZ]) + "\n\nSketch.\n" + _SB(decls=[FOO, BAZ]) + "\n"
    fe(_sx(both, outline=multi), [NOPROOF.format(7, "A.C baz", "def"), kind.format("A.C baz", "def")], 1)
    clean(_sx("Idea.\n" + _AB(decls=[FOO]) + "\n\nSketch.\n" + _SB(decls=[FOO]) + "\n", outline=multi))


@case("SKC5", "SKETCH-ROOT: the sketch's decls must include a root of its group (one is enough, more decls are fine); a note whose group is not "
              "in the outline anchors none; an unresolved or ambiguous decl is only the finding already coded")
def _():
    fe(_sx("Idea.\n" + _AB() + "\n\nSketch.\n" + _SB(decls=[BAR]) + "\n"),
       ["SKETCH-ROOT 01-a.md:10 block '01.b02': its decls include no root of group 'g1' (roots: A.B foo)"], 1)
    clean(_sx("Idea.\n" + _AB() + "\n\nSketch.\n" + _SB(decls=[BAR, FOO]) + "\n"))
    fe(_sx("Sketch.\n" + _SB("01.b01") + "\n", group="gx"),
       ["UNKNOWN-GROUP 01-a.md:2 group 'gx' is not in the outline",
        "SKETCH-ROOT 01-a.md:7 block '01.b01': group 'gx' is not a group of the outline; a sketch needs a group root in its decls"], 1)
    dup = R("A.D", "dup")
    amb = "(first_line, last_line): (1, 3), (7, 9)"
    fe(_sx("Idea.\n" + _AB(decls=[dup]) + "\n\nSketch.\n" + _SB(decls=[dup]) + "\n", outline=OL(G("g1", roots=[dup]))),
       [f"AMBIGUOUS outline.json group 'g1' roots[0] A.D dup: 2 rows; candidates {amb}",
        f"AMBIGUOUS 01-a.md:7 block '01.b01' decls[0] A.D dup: 2 rows; candidates {amb}",
        f"AMBIGUOUS 01-a.md:10 block '01.b02' decls[0] A.D dup: 2 rows; candidates {amb}"], 1)
    fe(_sx("Idea.\n" + _AB() + "\n\nSketch.\n" + _SB(decls=[R("A.B", "nope"), FOO]) + "\n"),
       ["UNRESOLVED 01-a.md:10 block '01.b02' decls[0] A.B nope: no row in decls.tsv"], 1)


@case("SKC6", "SKETCH-RUN: the reason of run_at for the block's span, naming the block; an anchor, a heading or a table in the run, a span past "
              "the start of the note; a bad span value is only the format problem")
def _():
    run = "SKETCH-RUN 01-a.md:{} block '01.b02': {}"
    fe(_sx("Idea.\n" + _AB() + "\n\nSketch.\n" + _SB(span=3) + "\n"), [run.format(10, "the run holds another rh anchor line (line 7)")], 1)
    fe(_sx("Idea.\n" + _AB() + "\n\n### Sub\n\nSketch.\n" + _SB(span=2) + "\n"), [run.format(12, "the run holds a heading at line 9")], 1)
    fe(_sx("Idea.\n" + _AB() + "\n\n| a |\n|---|\n| 1 |\n" + _SB() + "\n"), [run.format(12, "the run holds a table at lines 9-11")], 1)
    fe(_sx("Idea.\n" + _AB() + "\n\nSketch.\n" + _SB(span=0) + "\n"),
       ["BLOCK-PROBLEM 01-a.md:10 block '01.b02': span: must be an integer of 1 or more"], 1)
    head = NOTE().split("\n")[1]   # a note with no heading, so a span can pass the start of it
    r = go(notes={"01-a.md": head + "\nSketch.\n" + _SB("01.b01", span=2) + "\n",
                  "02-b.md": NOTE(nid="02", body="Idea.\n" + _AB("02.b01") + "\n")}, outline=OL(G("g1")), decls=DECLS_K)
    fe(r, ["SKETCH-RUN 01-a.md:3 block '01.b01': span 2 asks for more elements than the note has before this anchor (only 1)"], 1)


@case("SKC7", "the format problems of a sketch and of span come through as BLOCK-PROBLEM: span on an argument, a bad basis, compiled "
              "without a build, source with a build")
def _():
    bp = "BLOCK-PROBLEM 01-a.md:{} block '{}': {}"
    fe(_sx("Idea.\n" + BL("01.b01", kind="argument", reader="R", date="2026-11-23", decls=[FOO], span=1) + "\n"),
       [bp.format(7, "01.b01", "span: only a sketch carries span")], 1)
    for kw, why in ((dict(basis="x"), "basis: must be source or compiled"),
                    (dict(basis="compiled"), "build: basis compiled needs a non-empty string"),
                    (dict(build="lake build"), "build: not allowed when basis is source")):
        fe(_sx("Idea.\n" + _AB() + "\n\nSketch.\n" + _SB(**kw) + "\n"), [bp.format(10, "01.b02", why)], 1)
    clean(_sx("Idea.\n" + _AB() + "\n\nSketch.\n" + _SB(basis="compiled", build="lake build", unexpanded=["x"]) + "\n"))


@case("SKC8", "the note line and the `blocks by kind:` line count sketches as a seventh kind; the checker prints no `sketches:` line (the "
              "builder counts proofs read)")
def _():
    r = _sx(_AS)
    ok("note 01 header ok, blocks 2 (argument=1 sketch=1)" in r.lines, "note line\n" + r.out)
    ok("blocks by kind: machine_fact=0 reading=0 interpretation=0 correction=0 not_read=0 argument=1 sketch=1" in r.lines, "kinds\n" + r.out)
    ok(not any(x.startswith("sketches:") for x in r.lines), "no sketches line\n" + r.out)


@case("ARGNP", "ARGUMENT-NO-PROOF is a listing (exit unchanged) for an argument anchored on a root of its group whose kind is not theorem or "
               "lemma: def and structure listed, theorem and lemma not; a def that is not a root of the group is not listed")
def _():
    one = "Idea.\n" + _AB(decls=[BAZ]) + "\n"
    r = _sx(one, outline=OL(G("g1", roots=[BAZ])))
    fe(r, [NOPROOF.format(7, "A.C baz", "def")], 0)
    eq(r.lines[-1], "1 notes, 0 findings, 1 warnings", "a listing is a warning, not a finding")
    fe(_sx("Idea.\n" + _AB(decls=[R("A.E", "stru")]) + "\n", outline=OL(G("g1", roots=[R("A.E", "stru")]))),
       [NOPROOF.format(7, "A.E stru", "structure")], 0)
    clean(_sx("Idea.\n" + _AB() + "\n"))
    clean(_sx("Idea.\n" + _AB(decls=[R("A.E", "lem")]) + "\n", outline=OL(G("g1", roots=[R("A.E", "lem")]))))
    clean(_sx("Idea.\n" + _AB(decls=[FOO, BAZ]) + "\n"))
    fe(_sx(one, outline=OL(_rg("named_statement", root=("A.C", "baz")))), [NOPROOF.format(7, "A.C baz", "def")], 0)


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
