# Sources

Everything in this repository is written from the public release and the public pages below. Each was fetched and read on the date shown.

## The release

| Item | Value |
|---|---|
| Author | Levent Alpöge |
| Author's note | <https://alpo.ge/remark.pdf> (4 pages) |
| Archive | 14 parts, `https://alpo.ge/lean.tar.gz.part01` to `part14`, named in the note's first footnote |
| Archive, joined | 239,275,554 bytes, SHA-256 `9631b4f020199e580ba86178cb56c6e9b09f690c2369a80dc4334aa93f49c7fc` |
| Note | 245,114 bytes, SHA-256 `3fc97784b71ddd44ff8aa0a177e99622a1c61b13cfa843a0989ee4a7a0cfeb8d` |
| Contents | 175,190 files, of which 175,187 are `.lean` |
| Toolchain pinned by the release | `leanprover/lean4:v4.33.1` |
| Licence | none stated |

We downloaded the 14 parts from the author's site on 2026-11-22, joined them, and computed the hash above ourselves. It equals the hash published by the mirror below. We then compared the extracted tree with the mirror's tree file by file (SHA-256 of each of the 175,190 files): identical.

## Where to get the source

- From the author: the 14 parts above. `cat lean.tar.gz.part?? > lean.tar.gz`.
- A public mirror with per-file hashes: <https://github.com/tamnd/riemann-lean>. Its `lean/` directory is the release, unchanged (checked by us as described above, at mirror commit `af705e0d9`).

## The verification (not our work)

- **Joint statement of the Lean and Mathlib communities**, 2026-11-21: <https://leanprover-community.github.io/blog/posts/riemann-hypothesis/>. It certifies that the statement is Mathlib's `RiemannHypothesis`, that the library compiles, that the theorem proved is exactly that statement, and that the exported proof is accepted by Lean's kernel and several independent checkers.
- **Verification files** (Andrew Sutherland, MIT): <https://math.mit.edu/~drew/grh/>. Read by us as last updated 2026-11-22 14:10 UTC. It lists each check, its result and its log, and the five theorems as they appear in the challenge file.
- **The community's comparison setup**: <https://github.com/leanprover-community/riemann-hypothesis>.

We ran none of these checks. Building the library is beyond the machine these notes are written on (the exported proof alone is about 61.6 GB). Our notes are written from the source text.

## Other written accounts

- <https://riemann.tamnd.com> (repository <https://github.com/tamnd/riemann>): a written proof for people, step by step. By its own status page on 2026-11-21, its 50 steps are drafted and no person has checked them against the Lean code. We have not checked them either.

## What "read by us" means

A note's anchors were opened and read in the source by the note's writer. Counts and structure taken from someone else's scan are marked as theirs until we have re-measured them.
