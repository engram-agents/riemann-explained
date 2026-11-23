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

**`tools/in_closure.py EDGES_TSV START_MODULE SITES_FILE --control MODULE`** answers, per site: is this
file compiled before the start module (INSIDE, with one shortest import path) or not (OUTSIDE)? Give at
least one control, a module you know is inside; if a control is not, the run stops and says BROKEN.
`python3 tools/in_closure.py OUT_DIR/edges.tsv Some.Start.Module sites.txt --control Some.Known.Module`

**`tools/import_closure.py`** is the size-and-folder summary of one closure. `in_closure.py` answers the
per-site questions. Both read the import lines through the same header reader in `scan_graph.py`, so they
agree on what a header is.

Every TSV starts with one `#` line (what was read, the source commit, what a row is NOT), then the column
row. Exit codes: 0 clean, 1 something was reported or nothing was checked, 2 usage error, 3 broken
control, 4 failed self-test.
