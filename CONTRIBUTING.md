# Contributing

Corrections are the most useful contribution: open an issue that names the note and the sentence (see the README).

## Before pushing a note (for writers)

Every note is read whole by the other writer before it is pushed, and a correction to a published note is a dated paragraph in that note, never a silent edit.

Run the code-block checker on every note you change, with the path to the release's `lean/src/` as the first argument:

```
python3 tools/check_lean_blocks.py <path-to-release>/lean/src docs/*.md
```

It tests every fenced `lean` block against the files listed in that note's "Files this note was written from" table. It prints, per note, how many blocks were checked, found verbatim, found only up to whitespace, not found, and acknowledged. A block that is not verbatim counts as acknowledged only if a line directly above it reads `*Not verbatim; see the correction dated YYYY-MM-DD below for the exact text.*` and the note has a `### Correction, YYYY-MM-DD` section with the same date. The checker runs its own self-test first and refuses to report if that fails.

**What exit 0 does not mean.** It means only that every fenced `lean` block is an exact quotation of a listed file, or is marked as not exact. It does not check paraphrases of statements in prose, inline code, the quoted text of the author's note, whether a block's file is the right one to cite, or whether any interpretation is correct. Those need a reader.
