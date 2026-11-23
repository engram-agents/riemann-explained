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
- `in_closure.py`: 0 only if every site is INSIDE or OUTSIDE; 1 for an AMBIGUOUS or NOT A MODULE site, or no site; 2 usage or input error, or a control equal to the start; 3 a broken control.
- `import_closure.py`: 0 printed; 1 unresolved imports under the root's own folders (closure would be under-counted); 2 usage error or no file for the start module.
