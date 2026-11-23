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
their anchor lines removed, are equal byte for byte after that rule (this needs the `git` program; `--repo DIR` names the repository when it is not the one around
NOTES_DIR), `--glob PATTERN` changes which files are notes (default `[0-9][0-9]-*.md`, so this folder's
`tools.md` is not one). The format of the comments is read only through `rh_anchor.py`. A finding is one line,
`CODE path:line message`; `EXTENT-WARNING`, `FRAME-NOTE` and `NEW-NOTE` are listings and never fail the run. Each
note prints `note <id> header ok, blocks N (kind=count ...)`, and the run ends with the counts by kind, what the
in-file and byte checks did or did not do, and `N notes, M findings, K warnings`. It checks shape and resolution;
it does not judge whether a claim is right, and the LIMIT paragraph in the file lists the title rules and the
translation rules that need a reader. Every group needs at least one root; a group with a null claim and no root passed
in the first version and is now a ROOT-COUNT error. The title rules the script applies are heuristics, named in the LIMIT. A byte difference is reported at its line in the current file as it is on disk (and its index without anchors), so a reader
opens the file at that line; where text is missing from the current file the number points past the end of the text: the line after the
last non-anchor line, which is an anchor line when anchors trail it and otherwise one past the last line of the file (not a line
that exists), or 1 when the file has no non-anchor line. The strip rule is `rh_anchor`'s: a last anchor line with
no line ending of its own also removes the line ending before it, so adding or removing such a hand-typed last line can read as a
one-line-ending difference; anchors written by the helper carry their own ending. An anchor-looking line counts as text only inside
a fence, and a malformed `rh-` line is kept as text, so fixing it since REV is a byte difference. A block anchored to a list must name its top-level
item (`item`, 1-based, counted across blank lines: a loose list is one list; nested items are not numbered); shapes of list a renderer may show differently are refused through a table
that is empty until the renderer control is in. The run prints a count line for the outline (and for the strings file and the
byte check when they ran); a header's group may be `root` only at level 0.
`python3 tools/notes_meta.py NOTES_DIR outline.json decls.tsv [--src SRC_ROOT] [--strings strings.json] [--base REV]`

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
- `in_closure.py`: 0 only if every site is INSIDE or OUTSIDE; 1 for an AMBIGUOUS or NOT A MODULE site, or no site; 2 usage or input error, or a control equal to the start; 3 a broken control.
- `import_closure.py`: 0 printed; 1 unresolved imports under the root's own folders (closure would be under-counted); 2 usage error or no file for the start module.
