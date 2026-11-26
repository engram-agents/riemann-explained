# Text copied from lsernau/grh-lean

A few files of this repository copy text from the readable edition of the proof: the repository
[lsernau/grh-lean](https://github.com/lsernau/grh-lean/tree/72fead102f663d5c7a407964a13dc0cf9d977207),
at version `72fead102f663d5c7a407964a13dc0cf9d977207`. That repository is released under the Apache License 2.0.

This page is ours. The three files beside it are the repository's, copied byte for byte from that version, because its
licence asks whoever passes its text on to pass these on too:

| File here | Copied from | sha256 |
|---|---|---|
| `LICENSE` | `grh/LICENSE` (the same bytes as the root `LICENSE`) | `c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4` |
| `NOTICE` | `grh/NOTICE` | `addbc1704aa68328c99cae493118f6f18d8f3b83af8facdb9f150dce81e1a65c` |
| `ATTRIBUTION.md` | `grh/ATTRIBUTION.md`, the list the notice points to | `b282f31534ec2ca1c500b4a87ba50282e442c49298e5fec97e444348d3f58d13` |

## Which of our files copy from it

All of them are test data or expected values in tests.

- `viewer/graph/page/test/fixtures/backtick-real-titles.json`: titles of parts, groups and files, from the repository's contents list.
- `viewer/graph/page/test/fixtures/note-linecoordinates.txt` and `note-onesidedbound.txt`: text from the opening notes of two files.
- `viewer/graph/page/test/fixtures/note-spans-classes.json`: the code spans of the files' opening notes, each once.
- `tools/build_grh_skeleton.py`: one sentence of `grh/README.md`, as an expected value in a test.

What we changed: we selected. Each of these files holds pieces cut out of the repository's text and stored in a format of ours
for a test. Every copied character is the repository's; the selection, the file format and anything around the copied text are ours.

A change that adds text copied from that repository adds its file to this list in the same change.

## What is not copied here

The map of the proof is built by the tools of this repository from a checkout of lsernau/grh-lean at build time. The proof's
files, and the notes the map shows, are not stored in this repository.
