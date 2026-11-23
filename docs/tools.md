# Text tools for reading the Lean source

These are text tools; they find where to read, they do not prove a dependency. Python 3, standard library
only. Each one runs its own self-test first and refuses (exit 4) if it fails. `--selftest` shows the cases.

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
- `in_closure.py`: 0 only if every site is INSIDE or OUTSIDE; 1 for an AMBIGUOUS or NOT A MODULE site, or no site; 2 usage or input error, or a control equal to the start; 3 a broken control.
- `import_closure.py`: 0 printed; 1 unresolved imports under the root's own folders (closure would be under-counted); 2 usage error or no file for the start module.
