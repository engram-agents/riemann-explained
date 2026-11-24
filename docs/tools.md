# Text tools for reading the Lean source

These are text tools; they find where to read, they do not prove a dependency. Python 3, standard library
only. Each one runs its own self-test first and refuses (exit 4) if it fails. `--selftest` shows the cases.

A run that checks nothing (no `.lean` file under SRC_ROOT) writes nothing. If OUT_DIR already holds a file that run
would have written, an earlier result looks like this run's to the next tool; so `scan_graph.py`, `alias_edges.py`
and `decl_table.py` print one more line after `CHECKED NOTHING`, `OUT_DIR holds files from an earlier run: <names>;
this run wrote nothing`, and keep exit 1. They do not delete the files.

For whoever writes the next self-test: **the expected value in a case is a literal, never read back from the tool.**
A case that computes its expectation with the code under test, or with a helper the tool exports, passes whatever
the tool does. Write the number, the line or the list into the case, and run a wrong version of the tool (a copy)
to see the case go red.

**`tools/scan_graph.py SRC_ROOT OUT_DIR`** answers: which files exist, how big, what do they import?
It writes `files.tsv` (one row per file, with word counts) and `edges.tsv` (one row per internal import).
`python3 tools/scan_graph.py SRC_ROOT OUT_DIR`

**`tools/alias_edges.py SRC_ROOT OUT_DIR`** answers: which theorems are only a wrapper around another
theorem, where is the target declared, and where are the names written out in full? It never picks
between two declarations with the same full name; it lists both.
`python3 tools/alias_edges.py SRC_ROOT OUT_DIR`

**`tools/decl_table.py SRC_ROOT OUT_DIR`** answers: which named declarations are in each file, on which lines?
It writes `decls.tsv` (module, name, kind, first line, last line, basis) and `decls_dup.tsv` (every row whose
module and full name occur more than once; it never picks one). The lines are the text rule's extent, not Lean's;
the rule lives in `tools/lean_decls.py`, which `alias_edges.py` also uses. `example` lines and instances with no
name are not rows; they are counted on the second summary line.
`python3 tools/decl_table.py SRC_ROOT OUT_DIR`

**`tools/rh_anchor.py`** is a small library, not a command: the one place that knows the anchor format of the
notes. A note carries its metadata in one-line comments, `<!-- rh-note {...} -->` (the header) and
`<!-- rh-block {...} -->` (a block anchor, on its own line after the paragraph, table or lean block it anchors),
so the rendered page does not change. The checker and the helper that writes anchors both import it. It reads and
writes the lines (`parse_note`, `format_comment`, `strip_anchor_lines`), says which element an anchor follows and
where a new one goes (`target`, `target_at`, `insert_after_line`; a new anchor goes at `append_after`, after any anchors already there), checks the shape of a block or header
(`problems`, `header_problems`, `block_id_ok`) and numbers new ids (`next_block_id`). It checks shape only: not the
outline, not the declaration table, not whether a table row exists. Markdown is approximated by three rules (fences,
tables, one comment per line), not CommonMark; the LIMIT paragraph in the file lists what is not recognised.
`python3 tools/rh_anchor.py --selftest`

**`tools/notes_meta.py NOTES_DIR OUTLINE DECLS_TSV`** answers: is the metadata of the notes well formed, and does every
name in it resolve to one row of `decls.tsv`? It reads the outline (every group, its parent, level, order,
premises, roots and claim), each note's header and anchors, and, with options, more: `--src SRC_ROOT` checks that
a block's `file` is in the note's file table and its `lines` are inside the file, `--strings PATH` lists blocks
whose text opens with another kind's frame, `--base REV` checks that the note at REV and the current note, both with
their anchor lines removed, are equal byte for byte after that rule, except that text the note only GAINED as dated additions is listed, not refused (see below; this needs the `git` program; `--repo DIR` names the repository when it is not the one around
NOTES_DIR), `--today YYYY-MM-DD` sets the day the additions are checked against (a test hook; default the UTC date of the clock), `--glob PATTERN` changes which files are notes (default `[0-9][0-9]-*.md`, so this folder's
`tools.md` is not one). The format of the comments is read only through `rh_anchor.py`. A finding is one line,
`CODE path:line message`; `EXTENT-WARNING`, `FRAME-NOTE`, `NEW-NOTE`, `ADDITION` and `CLAIM-LIBRARY-WORD` are listings and never fail the run. Each
note prints `note <id> header ok, blocks N (kind=count ...)`, and the run ends with the counts by kind, what the
in-file and byte checks did or did not do, and `N notes, M findings, K warnings`. It checks shape and resolution;
it does not judge whether a claim is right, and the LIMIT paragraph in the file lists the title rules and the
translation rules that need a reader. Every group needs at least one root; a group with a null claim and no root passed
in the first version and is now a ROOT-COUNT error. The title rules the script applies are heuristics, named in the LIMIT. A dotted token (`Foo.bar`) or a CamelCase word (`getValue`) in a claim `text` or a `conditions` entry outside single backticks is listed as `CLAIM-LIBRARY-WORD` (once per token and text; a prompt to write it in backticks or in plain words, not a proof; the rule is exact in the LIMIT). A claim may carry `basis` (`read` or `census`), optional for now; a summary line counts the non-null claims that are objects by basis (a claim that is not an object is its own BAD-VALUE and is counted in none). Two notes whose headers carry the same `id` (exact strings, first header of each note) are `NOTE-ID-DUPLICATE`. **Dated additions.** A note may gain text after publication without a byte difference when every base line is still there, unchanged and in order, and each run of new lines begins, after any blank lines, with a heading (one to six `#`, a space, text) whose text holds a real date `YYYY-MM-DD`. The base is matched into the current text from the left (a repeated line is taken at its first match) and, if that leaves an illegal run, from the right (taken at its last match); the note is accepted when either gives only legal runs, and the runs of the first that does (left first) are listed. Two alignments are tried, not every possible one. Every real date in the heading may not be later than the day of the run and may not be earlier than the date in `release` of the note header **as published** (the text at `--base`, so editing or deleting `release` since then does not lower the limit) when that is written `rh-YYYY-MM-DD`; a published release with no date, or an impossible one such as `rh-2026-02-30`, gives no earlier limit, and the limit is the release's date, not the note's own. A run may not touch published text: the line before its first non-blank line and the line after its last one must each be blank or the edge of the note (a blank line inside the run counts; anchor lines are not text), otherwise it is a byte difference naming the run and the side; a run above the first published non-blank line (above the title) is one too. Fence state is kept: a published line that is inside a fenced block in one text and not in the other (an inserted marker that wraps published text in a code block, or ends a published block early) makes the note a byte difference, and the message names the inserted run. Each such run is printed as `ADDITION path:LINE N lines, heading TEXT` (the line in the file as it is on disk, N the lines of the run), is counted among the warnings, and never changes the exit code; the byte-check line ends `additions A`. Everything else stays a byte difference: a removed or altered base line, a run with no dated heading first, a date outside the window (the message names the date and the window), an impossible date such as `2026-13-45`, and a run inside a fenced block of the published text. One run that fails makes the whole note a byte difference. Two limits: a line that repeats an earlier base line can leave the original unmatched as a second run on both alignments, which then fails unless it is itself a dated addition; and a note whose last line has no line ending cannot gain text after it. The boundary rule looks at blank lines only, so a run that brings its own blank line on each side and sits between two table rows, or inside a list item, is accepted and splits that table or list. A byte difference is reported at its line in the current file as it is on disk (and its index without anchors), so a reader opens the file at that line; where text is missing from the current file the number points past the end of the text: the line after the last non-anchor line, which is an anchor line when anchors trail it and otherwise one past the last line of the file (not a line that exists), or 1 when the file has no non-anchor line. The strip rule is `rh_anchor`'s: a last anchor line with
no line ending of its own also removes the line ending before it, so adding or removing such a hand-typed last line can read as a
one-line-ending difference; anchors written by the helper carry their own ending. An anchor-looking line counts as text only inside
a fence, and a malformed `rh-` line is kept as text, so fixing it since REV is a byte difference. A block anchored to a list must name its top-level
item (`item`, 1-based, counted across blank lines: a loose list is one list; nested items are not numbered); shapes of list a renderer may show differently are refused through a table
that is empty until the renderer control is in. The run prints a count line for the outline (and for the strings file and the
byte check when they ran); a header's group may be `root` only at level 0.
`python3 tools/notes_meta.py NOTES_DIR outline.json decls.tsv [--src SRC_ROOT] [--strings strings.json] [--base REV] [--today YYYY-MM-DD]`

**`tools/note_cite.py NOTE DECLS_TSV --at LINE --decl FULL.NAME --kind KIND`** writes one block anchor, so nobody
types the JSON. It finds the declaration's module in `decls.tsv` (`--module` picks one when the name is in several),
takes the element of the note that holds line `--at` (a paragraph, table, list or lean block, or the anchor lines just
after one), and puts the comment after that element and after any anchors already there, so a second anchor on one
element lands below the first. For a table it fills `row` (and `col` if given), for a list `item`, from the line or
from `--row`/`--item`. It refuses, with one line `REFUSED CODE message` and nothing written, when the name does not
resolve to one row, when `--lines` cross the declaration's text extent, when the file is not in the note's file table,
when the line is in a heading, quote or non-lean fence, when the note has no header or a comment the parser cannot
read, when a kind that needs `--reader` and `--date` lacks one (it never fills either by default, and an empty value is
refused too), and when a flag belongs to another kind (`--needs` outside `not_read`, the tool fields outside
`machine_fact`: STRAY-FLAG). The block is
checked with `rh_anchor.problems` before it is placed, and the result with the same parser the checker uses: the note
without its anchor lines must not change. By default it only prints the comment and the line it would go after;
`--write` writes the note, keeping its file mode, and through a symlink writes the link's target. `--src SRC_ROOT`
(with `--lines`) also prints the cited lines from your local copy of the release, so you see the statement while you
cite it. It does not judge whether the cited lines support the sentence, or whether the kind
is right: that is the reader's and the peer's job, and `notes_meta.py` is the check of what it writes.
`python3 tools/note_cite.py docs/13-how-the-sha-bound-is-used.md decls.tsv --at 214 --decl UpperTheory.Top.topDesWin --lines 25-25 --kind reading --reader NAME --date YYYY-MM-DD --src SRC_ROOT`

**`tools/build_site.py NOTES_DIR OUTLINE DECLS_TSV STRINGS OUT_DIR`** answers: what do the first two zoom levels
of the proof map look like, built from the notes, the outline and the declaration table alone? It first runs the
check of `notes_meta.py` on the same inputs (its library function, not a subprocess) and refuses to build, writing
nothing, not even OUT_DIR, if that finds an error. Then it writes, under OUT_DIR: `level0.json` (the steps of the
chain in `order`, the counts of the two facts, the notes about the whole, the number of open questions), `level1.json` (each step with its child groups
nested under it to any depth), one `group/<id>.json` per group (its `premises`, its roots with file, lines and, with
`--source-check`, the hash of the file, and per root the two facts `statement_read` and `proof_read`; the blocks that anchor them; the open `not_read` items), `manifest.json`
(the hash of every other file, the three commit ids, the release id and archive hash, the counts), `data.js` (the
same data as one assignment) and `index.html`. The page is one static file of plain HTML: each step is a card (claim,
conditions, premises as links (for a step with a null claim too), two status lines, a line counting the open questions (on a card only above zero; the first screen always says it), the first sentence of the argument inside
its frame (rendered by the span rule below), three reaction links; a span between single backticks on one line in a claim, a condition, a note's title or the text of an argument or interpretation block is shown as code, by the same span rule `notes_meta.py` uses, and nothing else in them is markup; block text is one paragraph joined by spaces first, so a span over a source line break is a span, and formulas in it are not converted), evidence is a closed `<details>`, child groups open in place, and nothing on it needs JavaScript or
makes a request. Every FIXED sentence on the page comes from the strings file, whose shape is provisional (the fixtures of the self-test carry their own wording, not the real one; the keys for the status
lines are provisional names, the owner of the wording may rename them: `statement_read_line`, `statement_census_line`,
`statement_not_read_line`, `proof_read_line`, `proof_not_read_line`, `proof_not_applicable_line`, `proof_none_other_line`, `steps_proof_not_applicable_line` (no placeholders in these three), `statement_count_line`, `proof_count_line`,
`open_items_line`, `steps_statement_line`, `steps_proof_line`, `steps_open_items_line`, besides `no_claim_label` and the three labels of the evidence block, `evidence_module_label`, `evidence_name_label`, `evidence_kind_label`); a
missing key stops the build and names itself, and a stale key (`coverage`, `not_read_yet`, `roots_not_read`, any other
top-level key, or key directly under `labels`, whose name holds `not_read`) is refused. There is no coverage word. Per root there are two facts: the statement is
read when the group's claim has basis `read` (a claim without a basis counts as `read` until the checker requires one) or
a reading block anchors the root; the proof is read when an argument block anchors it, and only a root that has a proof can have it read: the kind column of the declaration table decides, `theorem` and `lemma` have a proof and every other kind (a definition, a structure, an instance, an abbreviation, a class, an inductive type) has none, so an instance or a definition with a proof term does not count as having a proof for the page. For such a root the proof fact is not applicable (`null` in the JSON, never `false`), and the card shows `proof_not_applicable_line`. A kind that is none of the eight the table holds, or is empty, is treated the same way, the card shows `proof_none_other_line` instead (also for a step with several roots when ANY of its proof-less roots has such a kind), and it is listed as `KIND-NOTE <group> <module>.<name> kind '<kind>'`. A claim of basis `census` does not
count. A step counts for a fact when every root of it has it (for the proof, every root that has a proof: the definition roots of a step are left out of that test, and a step none of whose roots has a proof counts as not applicable; the card counts over the roots that have a proof; a group with no root is never counted as read; that guard is redundant by
design, the checker refuses such a group first). The build asserts read + not read = total for the statement and read + not read + not applicable = total for the proof, and prints the numbers; these sums guard a
MISSING flag, not a WRONG one. The first-screen proof line counts over the steps that have a proof, and when no step has one it shows `steps_proof_not_applicable_line` in its place (the first screen does not distinguish an unknown kind; none is reachable among top-level steps on a real table). For a null claim or a census claim the statement reader is the first reading block of the root by
note id and then block number, not by date.
A group whose claim is null shows its root's Lean name and the `no_claim_label` in the heading, then the status lines.
Open questions are the distinct open `not_read` blocks, each counted once. The proof line names the reader and date of the first
argument block of the root, by note id and then block number (the rule of the statement reader, not by date). Every value of the
strings file, at any depth, may hold only the `{placeholders}` its key declares (`proof_read_line` declares `{reader}` and `{date}`);
an undeclared one is refused naming the key and the token, nine keys must hold every placeholder they declare (the status, count and open-items lines named above; the frames, `shared_note`, `note_href` and the reaction hrefs may omit theirs; the refusal names the key and the missing placeholder), a key that declares none may hold no brace, and a new key
is covered by default. The build also stops for: the words
verified, explained, understood (or any word of `forbidden_words`), a percent sign or `of the proof` in the strings file
(the builder's own sentences never contain them; its href templates may hold `%`; the words `Read by us`, `Partly read`
and `Not read yet` are refused too, the scale is gone; that match is exact-case and single-space, so the lowercase phrase
`not read yet` is allowed inside status wording); a reading, argument,
interpretation or correction block with no reader or no date; a fact whose read and not-read counts do not add up to
the total (SUM-STATEMENT, SUM-PROOF); a reaction target that is not an https URL (the hrefs may hold any word, a label
may not); a link on the page with no target; a number
on the page that is in no JSON file; a group id that is not safe as a file name. `--source-check SRC_ROOT` compares
the text lines of every output (what a reader sees: the backticks of a span are removed from claim text, conditions, note titles, block text and a block's first sentence first, on the JSON side; the page itself is not compared inside `<code>`), and the source lines of every copied note text (an argument or interpretation
paragraph, a note title) before they are joined, with the lines of the release (at least 20 non-space characters), and
says what it ranged over; names and ids are left out by construction. What it shows is narrow: no output line equals a
release line and no line of copied note text equals one; a release line quoted inside a longer sentence (of a claim, of block text or of a first sentence) is not
detected. Block text and a block's first sentence are compared both as written and with span backticks removed, so a release line that itself holds a span is still seen there. The first sentence of an argument block is cut at the first `.`, `!` or `?` followed by white space even inside a span (a span holding `f. g` gives the sentence ending in `f.`, its backtick left literal on the card): a known limit, not changed. `--notes-commit REV --repo DIR` stamps the notes commit; a
tree whose notes, outline or strings differ from it, or whose tools differ from their commit, stamps `dirty` in every
commit id and on the page. A fresh run into a non-empty OUT_DIR refuses unless `--force`, which removes only what a
build writes. The site is written into a temporary directory beside OUT_DIR and renamed into place, so a failure
leaves OUT_DIR absent or the old build as it was; a failure to write is exit 2 with one line. Text from the notes and
the outline (claims, conditions, note titles, argument and interpretation text) is not refused for those words: each
hit is listed as `WORD-NOTE <where> <word>` on stdout, the exit code is unchanged and the text is never edited. A block whose argument or interpretation text, outside its single-backtick spans, holds `$`, `\(`, `\[` or `\begin{` is listed as `FORMULA-RAW <block id>` (once per block, in note order, after any KIND-NOTE lines): exit unchanged, nothing written. Blocks of other kinds are not scanned (the `sketch` kind joins with F24b). It is a mark detector, not a formula parser (a dollar amount is listed too), and a formula inside a code span is not; formulas are not converted yet (F26 will). For
`of the proof` the listing is narrower than the refusal in the strings file (which takes any occurrence): in the notes'
text only a number, a percent sign or a quantity word (half, third, quarter, most, part, fraction, portion, share,
majority, all; the list is provisional) immediately before it is listed, so a title like `the top of the proof` is not. A `not_read` block in a level-0 note is anchored to no group: it is not counted in the number of open questions and is shown on no
card. The
LIMIT paragraph in the file lists what is not checked.
`python3 tools/build_site.py NOTES_DIR outline.json decls.tsv strings.json OUT_DIR [--source-check SRC_ROOT] [--release-archive-sha HEX] [--notes-commit REV --repo DIR] [--force]`

**`tools/in_closure.py EDGES_TSV START_MODULE SITES_FILE --control MODULE`** answers, per site: is this
file compiled before the start module (INSIDE, with one shortest import path) or not (OUTSIDE)? Give at
least one control, a module you know is inside; if a control is not, the run stops and says BROKEN.
`python3 tools/in_closure.py OUT_DIR/edges.tsv Some.Start.Module sites.txt --control Some.Known.Module`

**`tools/import_closure.py`** is the size-and-folder summary of one closure. `in_closure.py` answers the
per-site questions. Both read the import lines through the same header reader in `scan_graph.py`, so they
agree on what a header is.

The header reader ends the header at the first line that is not blank, `import`, `module` or `prelude`, so Lean's `public import` and `meta import` forms would end it early and hide what follows (none was found in the release read; a later release must be checked).

Every TSV starts with one `#` line (what was read, the source commit, what a row is NOT), then the column
row. Exit codes, tool by tool (4 always means the self-test failed and nothing was reported):

- `scan_graph.py`: 0 clean; 1 an unresolved import under a folder of the root, an undecodable or unreadable file, or no `.lean` file; 2 usage error or SRC_ROOT not a directory.
- `alias_edges.py`: 0 even when unresolved or ambiguous targets or odd-shape rows are printed; 1 only for an undecodable or unreadable file or no `.lean` file; 2 usage error or SRC_ROOT not a directory.
- `decl_table.py`: 0 even when duplicate (module, name) pairs are written; 1 only for an undecodable or unreadable file or no `.lean` file; 2 usage error or SRC_ROOT not a directory.
- `rh_anchor.py --selftest`: 0 all cases pass; 1 any case fails; 2 usage error (it has no other command line); 3 no case ran. (It has no exit 4: it has no normal run to refuse.)
- `notes_meta.py`: 0 every note passed (listings do not count); 1 any finding of class ERROR; 2 usage error or an input that cannot be read (a note or strings file that is not UTF-8, an outline or strings file that is not JSON, a decls row that is not six columns, a `--base` that is not a commit), nothing on stdout; 3 CHECKED NOTHING (no note matches, the outline has no groups, or decls.tsv has no rows); 4 the self-test failed. `--selftest`: 0 all pass, 1 any fails, 2 usage, 3 no case ran.
- `note_cite.py`: 0 done (or a dry run printed); 2 usage error, an input that cannot be read (also a `--src` file that is not UTF-8), or a note that cannot be written; 4 the self-test failed, nothing done; 5 REFUSED (the one-line reason on stdout), nothing written; 6 a post-condition failed (a bug in the helper), nothing written. `--selftest`: 0 all pass, 1 any fails, 3 no case ran.
- `build_site.py`: 0 built; 1 refused, nothing written (an error of `notes_meta.py`, a strings key missing or a forbidden word, a build rule that failed, a non-empty OUT_DIR without `--force`, a release line found in an output); 2 usage error, an input that cannot be read or a site that cannot be written (one line, nothing on stdout, nothing left behind); 3 checked nothing (no note matches, or no `.lean` file under SRC_ROOT); 4 the self-test failed. `--selftest`: 0 all pass, 4 any fails, 2 an unknown id after `--only`.
- `in_closure.py`: 0 only if every site is INSIDE or OUTSIDE; 1 for an AMBIGUOUS or NOT A MODULE site, or no site; 2 usage or input error, or a control equal to the start; 3 a broken control.
- `import_closure.py`: 0 printed; 1 unresolved imports under the root's own folders (closure would be under-counted); 2 usage error or no file for the start module.
