# Text copied from lsernau/grh-lean

Some test files of this repository copy text from
[lsernau/grh-lean](https://github.com/lsernau/grh-lean/tree/72fead102f663d5c7a407964a13dc0cf9d977207),
at version `72fead102f663d5c7a407964a13dc0cf9d977207`: a separate repository that holds a shorter rewriting of the proof, as Lean text.
What we copy comes from its folder `grh/`, which that repository calls its readable edition (it has a compact one beside it; both are
Lean). That repository is released under the Apache License 2.0; its `NOTICE`, copied here, names its copyright holder.

This page is ours. The three files beside it are the repository's, copied byte for byte from that version. Its
licence asks whoever passes its text on to pass on the licence and the notices; the attribution list comes with them because the
notice points to it:

| File here | Copied from | sha256 |
|---|---|---|
| `LICENSE` | `grh/LICENSE` (the same bytes as that repository's root `LICENSE`) | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` |
| `NOTICE` | `grh/NOTICE` | `addbc1704aa68328c99cae493118f6f18d8f3b83af8facdb9f150dce81e1a65c` |
| `ATTRIBUTION.md` | `grh/ATTRIBUTION.md`, the list the notice points to | `b282f31534ec2ca1c500b4a87ba50282e442c49298e5fec97e444348d3f58d13` |

## Where our files copy from it

Only in tests, in two places:

- **`viewer/graph/page/test/`**: the page's test programs, the fixture generator (`fixtures/make_fixtures.py`) and the fixtures
  it writes. Between them they hold titles of parts, groups and files from the repository's contents list; two sentences from line 15 of
  `grh/README.md` (the second cut before its colon); the opening notes of two files (`grh/src/New/Reduction/OneSidedBound.lean` and
  `grh/src/New/OneLift/ComparisonOperator/LineCoordinates.lean`); and the code spans of the opening notes of the 306 files under
  `grh/src/New`, each span once (`fixtures/note-spans-classes.json`). A fixture is often written in several copies, so one piece of text can sit in many files.
- **The self-tests inside `tools/build_site.py` and `tools/build_grh_skeleton.py`**: the same two sentences of `grh/README.md`, as test
  data (in `tools/build_grh_skeleton.py` they sit in a constant that one self-test expects).

Names of that repository's files and declarations also appear in our tests and notes, as names. Names are not listed here.

Nothing under `docs/`, `outline/` or `site/` is copied from that repository. One theorem statement that our notes quote from the Lean
release also stands, unchanged, in that repository (its `NOTICE` says so); the notes' source for it is the release.

What we changed: we selected. For the code spans we also removed repeats, sorted them, and put a count and a class label of ours on
each. Each of these files holds pieces cut out of the repository's text and stored in a format of ours
for a test. Every copied character is the repository's; the selection, the file format and anything around the copied text are ours.

A change that copies text from that repository into any other place, or adds a kind of text not named above, says so here in
the same change.

## What is not copied here

The map of the proof is built by the tools of this repository from a checkout of lsernau/grh-lean at build time. The proof's
files, and the notes the map shows, are not stored in this repository.
