#!/usr/bin/env python3
"""The site builder of the proof map: the zoom levels 0 and 1 as JSON, and one static page, from the notes, the outline and
the declaration table.

It reads the notes as text, runs no Lean and makes no network request. It refuses to build unless `notes_meta` passes on the
same inputs (its library function is called, not a subprocess; its listings do not block). Everything it writes goes under
OUT_DIR, and nothing is written, not even OUT_DIR, unless every check passed. The format of the note comments is read only
through `rh_anchor.py`, the check of the notes only through `notes_meta.py`, both loaded by file path from the folder of
this file.

Outputs under OUT_DIR (JSON: sorted keys, 1-space indent, LF, UTF-8, one final newline)
  level0.json   the level-1 steps of the chain in `order`, the facts counts, the notes about the whole (level 0), totals
  level1.json   the same steps, each with its child groups nested under it to any depth
  group/<id>.json  one per group: its roots, the blocks that anchor them, the open `not_read` items, the notes
  manifest.json sha256 of every other output file, the three commit ids, the release id and archive hash, the counts
  data.js       `window.RH_DATA = {...};` with level0, level1 and every group file (nothing reads it yet)
  index.html    ONE static page: plain semantic HTML, readable without JavaScript, no request of any kind
Every JSON file carries `commits`: {notes, release, tools} (B5). A group id is used verbatim as the anchor id of its card.
The group objects inside level0.json and level1.json (the steps and, in level1.json, their `children`) have: `claim`, which
is {text, reader, date, basis (read or census), conditions} or null; `premises`, the group ids the group rests on, in the order
of the outline (a field of the GROUP, null-claim groups included; [] when none); `lean_name`, the name of the first root; `claim_label`, the strings file's `no_claim_label` when the claim is null; `statement_read` and `proof_read`, true when
EVERY root of the group has the fact (the proof_read of a group whose roots have no proof is null, F22); `unread`, true when no root has either fact; `counts`, {roots, roots_statement_read,
roots_proof_read, roots_proof_applicable, roots_open_items, open_items}; `notes`, a list of {note, list_title, link}. group/<id>.json has none of
`claim`, `counts`, `statement_read` and `proof_read`: it has `id`, `level`, `parent`, `premises`, `roots`, `blocks`,
`open_items`, `notes` and `commits`, and each root of it has `statement_read` (a boolean) and `proof_read` (a boolean, or null for a root without a proof). level0.json has `facts` ({steps,
statement_read, statement_not_read, proof_read, proof_not_read, proof_not_applicable, proof_applicable}, counted over the level-1 steps) and `totals`, which holds
`open_items`, the number of distinct open not_read blocks of the whole outline.

CONTRACT (each line is a self-test case, written before the code; an expected value in a case is a literal)
 Command, output, exit codes
  X1 Exit 2: usage, an input that cannot be read, OUT_DIR that is a file, a SRC_ROOT that is not a directory, a
     --release-archive-sha that is not 64 hex digits, --notes-commit without --repo (or the reverse), a REV that is not a
     commit; the message goes to stderr, nothing to stdout, nothing is written. Cases X1a X1b.
  X2 Exit 3: `CHECKED NOTHING: <reason>` on stdout and nothing written, when notes_meta checked nothing (no note) or
     --source-check finds no .lean file under SRC_ROOT. Cases X2a X2b.
  X3 Exit 1 REFUSED, and OUT_DIR does not exist afterwards: any ERROR finding of notes_meta (its output is printed), or a
     build rule that failed (`BUILD-ERROR <CODE> <message>` on stdout). The builder prints notes_meta's count line `outline:
     G groups, C claimed, Z null, R roots resolved, D defs_opened resolved, P premise links` on a build. Cases X3a X3b X3c.
  X4 A fresh run into a non-empty OUT_DIR says OUT-NOT-EMPTY and refuses (exit 1) unless --force; --force removes only
     what a build writes (the five files and the folder `group`), never another file. Cases OUT1 OUT2.
  X5 A group id that is not safe as a file name (letters, digits, `.`, `_`, `-`, not starting with `.`, at most 100
     characters; no two ids that differ only in case) is GROUP-ID-UNSAFE. Cases ID1 ID2 W1.
  X6 A normal run first runs the self-test quietly and refuses with exit 4 if it fails; `--selftest` runs it (0 pass, 4
     fail); `--selftest --only ID,ID` runs exactly those cases and an unknown id exits 2. Cases EXIT4 SEL1.
  X7 The build is written into a temporary sibling directory of OUT_DIR and renamed into place at the end: a failure before
     the rename leaves OUT_DIR absent (fresh run) or the old build and every other file in it untouched (--force), and no
     temporary directory behind. A failure to write (OSError) is exit 2 with ONE line, no traceback; a JSON too deep to
     write is exit 2 with the line `outline too deep to write`; the parent of OUT_DIR must exist. Cases W2 W3 W4 W5.
  X8 Two notes with the same header id are refused by the checker (notes_meta, NOTE-ID-DUPLICATE, one line naming every file),
     exit 1, nothing written; the builder has no rule of its own for it. Case DUP1.
 Data
  L0 level0.json: the level-1 steps in `order` whatever the order in the outline file; per step the fields above; `route`
     counts the steps per coverage word; `header_notes` lists the level-0 notes; `totals` counts groups, notes, blocks and
     distinct roots, each once. Case L0.
  L1 level1.json nests child groups under their parent to any depth (a case with depth 4), siblings by `order`. Case L1.
  G1 group/<id>.json for every group: roots (module, name, kind, file, lines, sha256, shared_with), the blocks that anchor
     them (note, block, kind, reader, date, second_readers, item, row, col, file, lines, needs when present; text and
     first_sentence for an argument or interpretation whose target is a paragraph), the open not_read items, the notes.
     A block anchored to a list carries its `item`, a table block its `row`; the text of a list item or a table cell is
     never written. Cases G1 U2.
  G2 sha256 of a root's file when --source-check gives the release, else null. Case G2.
  M1 manifest.json: sha256 of every output file but itself, counts of groups, notes and blocks, the release id and the
     --release-archive-sha (or null). Case M1.
  F1 JSON as stated above, non-ASCII kept; data.js holds level0, level1 and groups. Cases FMT1 DJS.
  B2 DETERMINISM: two builds in child processes under PYTHONHASHSEED=1 and =2 give byte-identical OUT_DIR. Case B2.
  B3 A note is listed under every group whose root one of its blocks anchors, and under its header's group; in totals
     it is counted once. Case B3.
  L2 A level-0 note (header level 0) is listed above the chain, under no step and in no group's list, and counted once in
     totals. Case U1.
  B5 Three commit ids in every JSON file: the notes commit (--notes-commit REV, else `unknown`), the release id (the
     outline's), the tools commit. A tree whose notes, outline, declaration table or strings differ from the commit, or
     whose tools differ from their commit, stamps `dirty` in all three, and the page says so in the first screen. Cases B5a
     B5b B5c B5d.
  B5x Per root TWO FACTS (F19): statement_read = the group carries a claim whose basis is `read` (a claim with no basis key
     counts as `read` until the checker requires one) or a reading block anchors the root; proof_read = an argument block
     anchors a root that has a proof (F22; null for a root that has none). Nothing else sets either: an interpretation, a correction, a not_read and a machine_fact block
     set neither, a claim with basis `census` does not set statement_read. Cases F1a F1b S1.
  F2 JSON: group/<id>.json per root `statement_read` and `proof_read` (boolean, or null for a root without a proof); level files per group `counts` {roots,
     roots_statement_read, roots_proof_read, roots_proof_applicable, roots_open_items, open_items} (no key of it holds `not_read`) and `claim.basis`
     (the effective value); `unread` = neither fact on any root; there is no `coverage` key; the proof_read of a root without a
     proof is null (F22). Case F2a.
  F3 There is no coverage word: a strings file that carries a `coverage` key, or a key whose name holds `not_read` other
     than statement_not_read_line and proof_not_read_line (not_read_yet, roots_not_read, roots_not_read_note), is refused
     naming the key (a stale file cannot ship a word scale); a value holding `Read by us`, `Partly read` or `Not read yet` is
     STRINGS-FORBIDDEN; the built page has none of the three. A stale `no_argument` is ignored and never printed.
     Cases F3a F3b.
  F4 The build asserts for the statement read + not read = total, and for the proof read + not read + not applicable = total,
     over the level-1 steps and over the roots of each group (the pure functions fact_pairs and fact_triples count them) and
     prints `facts check: statements read A + not read B = N steps; proofs read C + not read D + not applicable E = N steps`;
     a mismatch planted through the function's input is SUM-STATEMENT or SUM-PROOF, nothing written; a null on a proof flag is
     not a mismatch; a group with no root has no fact claim and is an error (FACTS-NO-ROOT), never counted as read. Cases R1a
     R1b.
  F22 A DEFINITION HAS NO PROOF TO READ. The kind column of the declaration table decides, for the row of the root: `theorem`
     and `lemma` have a proof, any other kind (def, structure, instance, abbrev, class, inductive) has none, and a kind that is
     none of those eight, or is empty, is treated as having none AND is listed (`KIND-NOTE <group> <module>.<name> kind '<kind>'`
     on stdout, exit unchanged). For a root without a proof proof_read is null (written `null`, never `false`). A step or group
     has proof_read true when every root that HAS a proof has it read (the roots without a proof are left out of that test),
     null when no root has a proof, false otherwise; counts.roots_proof_applicable is the number of roots that have a proof. A
     card that has no proof to read shows the strings key proof_not_applicable_line, or proof_none_other_line when any of its roots has a kind outside the
     eight (no placeholders in either; also for a several-root card none of whose roots has a proof); a several-root card counts proof_count_line over the roots that have a proof. A
     card is `unread` when its statement is not read and its proof is not read or not applicable. level0 `facts` carry
     proof_applicable (the steps that have a proof) and proof_not_applicable; the first-screen steps_proof_line counts over
     the steps that have a proof, and when no step has one the first screen shows steps_proof_not_applicable_line (no placeholders) in its place
     (as a card does; never `of 0 steps`). Cases PRK1 PRK2 DEF1 DEF2 DEF3 DEF4 NAL1 NAL2 NAL3 NONE1 (NAL2 reads the strings file of the checkout).
  F23 ONE SPAN RULE FOR EVERY AUTHOR-WRITTEN LINE. A note's list_title is rendered by the same rule as a claim (a span between
     single backticks on one line is <code>, escaped; nothing else is markup) wherever a title is shown: the level-0 list, the
     notes list and the corrections list of a card. The JSON keeps the title as written. The source check compares what a
     reader sees: before the whole-line compare the backticks of a span are removed (each span replaced by its content) from
     the text of a claim, the conditions, the list titles, the text of a block and a block's first sentence, on the JSON and data.js side and on the copied title lines; the
     page is not compared inside <code>, so a wrapped release line is found in the JSON files, not on the page. Doubled
     backticks, an unpaired backtick and a pair over a line break are not spans and are compared as written. Cases TITLE1
     TITLE2 SPAN1 SPAN2 SPAN3 SPAN4.
  F28 BLOCK TEXT GOES THROUGH THE SAME RULE. The text of an argument or interpretation block (the evidence list) and the first
     sentence of an argument block (the card) are rendered by the span rule, the frame staying escaped text. The block text is
     ONE paragraph, its source lines joined by spaces before the rule is applied, so a span that runs over a source line break
     is a span to the reader (an unpaired backtick, doubled backticks and an empty pair stay literal). The JSON and data.js keep
     the text and the first sentence as written. The source check removes span backticks from the `text` of a block and from a
     `first_sentence` on the JSON and data.js side, as for a claim (doubled backticks compare as written). A block whose text,
     once the content of its single-backtick spans is taken out, holds `$`, `\\(`, `\\[` or `\\begin{` is LISTED, one line
     `FORMULA-RAW <block id>` per block in note order, on stdout after KIND-NOTE; exit unchanged, nothing written. Formulas
     are not converted here (F26 will). Cases BT1 BT2 BT3 BT4 BT5 BT6 BT7 BT8 FR1 FR2 FR3 FR4.
  F24 THE RECOGNITION (F24b). group/<id>.json and the step summaries carry `root_role`, `root_kind`, `recognition` (null for a
     group with no claim; never in `counts`). A card with a claim shows, between its premises line and its status lines, the form
     line `recognition_<role>_<form>_line` (role: root_role, else the class of the root's kind), the difference, a line per citation
     (an `<a class=citation>` with an https url, the one external anchor besides a reaction anchor), `established_by_line` or
     `established_not_traced_line` (a named statement only), and `recognition_label_line`; no recognition shows the not-written line;
     a named statement also shows `named_statement_use_line` directly after its claim and conditions, before the premises line and the recognition block (F36). An open form prints the newest source_date of the says_open citations
     (compared as written). The run prints `recognition: K known, V variant, N not recognised, O open in literature, M not written,
     of G groups with a claim` over every group with a claim at every depth (SUM-RECOGNITION). Cases RJ1 RC1 RF1 RD1 RD2 RL1 RU1 RE1
     RE2 RS1 RS2 RS3 P7e PHR5 PHR6 MK1. F31: a `note` of a not_recognised recognition follows its form line (span rule only). Cases
     FN1 FN2 FN3 FN4.
  F25 THE SKETCH (F25b). group/<id>.json has `sketches`; the card shows the sketch after the argument, or the missing-sketch line
     when its proof is read and it has none; a sketch never sets proof_read; the run prints `sketches: S of P steps with a proof read`
     (level-1 steps; SUM-SKETCH). FORMULA-RAW covers sketch text. Cases SK1 to SK8 FR3 FR5.
  F35 BOLD AND NESTED ITEMS IN BLOCK TEXT. Where block text is rendered with links (argument, interpretation, the first sentence, sketch
     paragraphs, items and sub-items; not claims, conditions, titles or `unexpanded`), a pair of `**` on one line around text is
     <strong>, its content through the span rule; a span wins, links are taken out first; empty pairs, runs of three or more
     asterisks and pairs over a line break that remains after the paragraph join (source lines are joined by spaces first, as for
     spans, F28) stay literal. A leftover `**` is listed `BOLD-UNPAIRED <block id>` (once per block, after
     FORMULA-RAW; exit unchanged). In a sketch list the indented `- ` or `* ` lines of an item are one nested <ul> in its <li>; the
     JSON item is {text, items}; a deeper level is flat and listed `NEST-DEPTH <block id>`. The source check removes the asterisks
     of a pair. CSS `code { overflow-wrap: anywhere; }`. Cases BD1 to BD8 NS1 to NS4 LB1 CW1.
  F37 PROVENANCE OFF THE READER'S SURFACE (a to c). No sentence of the card names a reader, a date of ours, a file, lines or a build:
     the status lines say the fact (`statement_read_line`, `proof_read_line`, `statement_census_line`, the not-read lines), the argument,
     no-proof and interpretation frames and the sketch frame name nobody (the sketch frame names its basis only), a citation line is
     `{source}, {where}` (and `, dated {source_date}` of a source that says open), the established line names the statement only, and
     the label line is ONE standing sentence at the end of each recognition block (none on a card with the not-written line). The
     second readers' line is not on the card nor in the closed card's first sentence. What left the card is in the card's closed
     <details class="evidence">, which has no `open`: after the root blocks and before the block list, `<ul class="provenance">` with
     in this order the statement line (`evidence_statement_read_line`, or `evidence_statement_census_line`; only a card with one root
     or none, as the card's own status lines), the proof line (`evidence_proof_read_line`; the first argument block), the recognition
     (`evidence_recognition_line`), one line per citation (`evidence_citation_line`: source, opened_by, opened_on, the source through
     the span rule) and the established line of a named statement (`evidence_established_line`; none for `not_traced`); in each
     block `<li>` of the block list, after its text: for an argument or sketch block a `<dl class="block-source">` with the File
     (base name) and Lines labels (`not given` when it has none), then one `<p class="second-reader">` per second reader of the block
     (any kind) and, for a sketch built from a compiled part, `<p class="sketch-build">`. The data (group files, level files,
     data.js) is unchanged: every reader, date, second reader, file and line range stays. A correction on a card shows its kind and its
     title only; its reader and date are in the Evidence block list (the who-span of its block). Cases PV1 to PV12, and the cases that
     moved with it (R6 B7a B7c B7f F1b H1 C1 C1b RDR1 PRF1 PRF2 PH1 PHR1 PHR2 PHR4 PHR5 PHR6 PHR7 BT2 RD1 RD2 RD3 RL1 RE1 RS3 PB1 PB3 DF1
     DF3 DF4 SK2 SK8 LK1 LK2 LK3 ESC1 MK1).
  F26B-E THE ELEMENTS OF THE PAGE. One module-level list, ALLOWED_ELEMENTS (41 elements, 49 element-attribute pairs), names every element the
     built page may hold and the attributes of each: the 29 elements the builder emits (measured over the self-test fixtures and a build of
     the notes of the repository) and the 12 of MathML (math mrow mi mn mo msub msup msubsup mover munder munderover mspace; attributes
     mathvariant, stretchy, form on those only). `element_problems(page)` reads the BUILT page with html.parser; an element or an
     attribute outside the list is `PAGE-STATIC element <name>` or `PAGE-STATIC attribute <name> on <element>` (exit 1, nothing written),
     the same code as the request-making findings. Cases EL1 EL2 EL3.
  F22b A block anchored only on roots that are no theorem or lemma is framed by `argument_frame_no_proof`; the not-applicable line
     stays and proof_read stays null. Cases PB1 PB2.
  F29 The base name of the block's file and the range of its lines are shown in the Evidence section (F37 moved them out of the frame;
     the labels are File and Lines, `not given` for a missing file or lines); the second readers follow the block's text there.
     Cases DF1 DF3 DF4 PHR7.
  F30 A link `[text](target)` in block text is shown as its text, no anchor; the run prints `links in block text: N shown as text`
     and `LINK-OUTSIDE <block id> <target>` (a listing). Cases LK1 to LK5.
 F9 The run prints the builder's own line `claim basis: R read, C census, M without (treated as read)` (without the
     parenthesis when M is 0), counted over the non-null claims of the outline, beside the checker's line of the same
     counts. Case BAS1.
 Page
  P1 The first screen comes from strings.json (`first_screen`), then the chain of level-1 steps in order. No sentence the
     reader sees is typed in code: a missing key is STRINGS-KEY naming it, and a build with every value a distinct
     marker shows only markers and data. Cases P1a P1b.
  P2 A card, open, in order: the claim (a bare declarative) or the null-claim heading, the conditions directly under it, the
     premises each a link to the premise's card (for a null-claim step too; a card with no premises has no premises heading
     and no paragraph), the statement line, the proof line, the open-items line (only when its count is above zero), the idea
     (the first sentence of the argument inside its frame, when an argument block exists); all outside the closed section.
     Text from the data is escaped. Cases P2a P2b PRM1 PRM2 PRM3 OPN1.
  P3 Evidence (Lean module and name and kind, file, lines, hash, blocks, open items) is a closed `<details>` per card; its
     labels for module, name and kind are the strings keys evidence_module_label, evidence_name_label and evidence_kind_label
     (like the labels File and Lines; a missing one is STRINGS-KEY). Cases EVD1 EVD2. A null claim shows the Lean
     name and the strings file's `no_claim_label` in the heading, then its status lines (H1). Case P3.
  PH Every string value of the strings file, at any depth, may hold only the placeholders its key declares: a `{name}` the
     key does not declare is STRINGS-KEY naming the key and the token, and a key that declares none may hold no brace at
     all (the check is built from the declared sets, so a new key is covered by default). evidence_proof_read_line declares {reader}
     and {date} and the Evidence section fills them from the first argument block of the root, by note id then block number. Cases PRF1
     PRF2 PH1 PH2.
  PHR The keys that must hold EVERY placeholder they declare (the check is a value that lacks one: STRINGS-KEY naming the key and
     `is missing the placeholder {name}`) are the counts (statement_count_line, proof_count_line, steps_statement_line and
     steps_proof_line ({n} {m}), open_items_line and steps_open_items_line ({n})), the recognition lines, the citation lines
     (`{source}` `{where}`, and `{source_date}` on the open one), established_by_line ({name}), sketch_frame ({basis}) and the eight
     Evidence keys of F37 (`{reader}` `{date}`; `{source}` `{opened_by}` `{opened_on}`; `{name}`; `{build}`). The read lines, the frames
     (argument_frame, argument_frame_no_proof, interpretation_frame), the label line and sketch_basis_compiled declare no placeholder
     since F37 (second_reader_frame is no key any more, and no longer required); frames.argument is the detector `How this is proved`
     (it was `How this is proved, as`; the frame has no `, as` any more); shared_note, note_href and the reaction hrefs may omit
     theirs. Cases PHR1 PHR2 PHR3 PHR4 PHR5 PHR6 PHR7 PV2 (the 27 keys declare exactly the placeholders they must hold).
  CODE In a claim text and in a condition a span between single backticks on one line is rendered as <code>...</code>, its
     content escaped like all data; nothing else is markup (no bold, link, heading or raw HTML: a `<b>` in the data stays
     escaped text). An unpaired backtick, an empty pair, doubled backticks and a pair over a line break (LF or CR) stay literal text.
     In the JSON and in data.js the text stays as written, backticks included. The span is notes_meta's `_BACKTICK_SPAN`, the one
     definition the checker uses for CLAIM-LIBRARY-WORD too, so the page and the checker agree on what is code. Cases CODE1 CODE2
     CODE3 CODE4 AGR1.
  C1 The two status lines come from the strings keys, and since F37 name nobody: statement_read_line (the claim is read, or a reading
     block anchors the root; the Evidence line names the reader and date of the claim, or of the first reading block of the root
     when the claim is null, or when its basis is census), statement_census_line (a census claim; it does not count; the Evidence
     line names the claim's reader and date), statement_not_read_line; proof_read_line, proof_not_read_line, proof_not_applicable_line and proof_none_other_line (a root that has no proof,
     no placeholders). A group with several
     roots shows statement_count_line and proof_count_line ({n} {m}) instead. The line open_items_line ({n}) is shown on a
     card only when n is above zero (a zero is not said there); the first-screen line steps_open_items_line is ALWAYS shown, zero
     included. The JSON counts are unchanged. Cases C1 C2 B7c OPN1 OPN2.
  Z1 A group with no root is never counted as read (the model, called directly, since the checker refuses it first; the guard is
     redundant by design). Case ZERO1. A step with arguments on some roots of several does not count for the proof. Case PRO1.
  S6 The statement reader of a root with several reading blocks is the first by note id, then block number, not by date.
     Case RDR1. A PAGE-STATIC finding names the strings key that holds the token (case ORG1); the retired words are an
     exact-case match and the refusal says so (case RET1).
  OI Open items are DISTINCT open not_read blocks, each once: the card's n counts the blocks anchored to its roots (a shared
     block counts on both cards), totals.open_items counts each once; counts.roots_open_items is the number of roots with at
     least one. Cases OI1 OI2 OI3.
  HR A reaction href template must be an https URL (STRINGS-KEY naming it otherwise); the hrefs (note_href and every reaction
     href) are exempt from the forbidden-word rule, every label and every other value is not. Cases HREF1 HREF2.
  P5 Three reaction links per card, plain anchors, href built from the strings template with the card id filled
     (URL-encoded). Case P5.
  P6 Every number on the page appears in the JSON or the strings file; the page computes no sum. number_problems. Case P6.
  P7 index.html and data.js hold none of fetch(, XMLHttpRequest, WebSocket, sendBeacon, import(, `src=`/`href=` to http(s)
     except in a reaction anchor, url(; the builder refuses (PAGE-STATIC) when one does. static_problems. Cases P7a P7b.
  R2 The first screen counts steps per fact with steps_statement_line and steps_proof_line ({n} {m}: a step is read for a fact
     when EVERY root of it has it; m is the number of level-1 steps, for the proof the number of those that have a proof, F22) and the open blocks with steps_open_items_line ({n});
     a card of a group with several roots counts declarations with statement_count_line and proof_count_line; the page has
     no percent sign and no "of the proof". Case R2.
  R3 The builder's own sentences never contain a word of `forbidden_words` (and verified, explained, understood always),
     a percent sign or `of the proof` (the strings file is refused, STRINGS-FORBIDDEN naming the key; the href templates
     may hold `%`). Text from the notes and the outline (claims, conditions, note titles, argument and interpretation
     text) is only LISTED when it does: one line `WORD-NOTE <where> <word>` per text and word (`of the proof` stands for
     that phrase or a percent sign) on stdout, exit unchanged, the count in the `built:` line; the text is never edited.
     Cases R3a R3b WN1 WN2 WN3.
  H1 A group whose claim is null shows its root's Lean name and the strings file's `no_claim_label` in the heading (not a
     status), and its status lines tell the facts: a null claim whose root has a reading block says the statement is read.
     Case H1.
  E1 The premises of a card are linked in the order of the outline, for a null-claim step as for a claimed one. Cases ORD1 PRM2.
  D1 Whatever data or strings reach the page is escaped there (text and attributes), and data.js writes `<`, `>`, `&`,
     U+2028 and U+2029 as \\uXXXX. Cases ESC1 JS1.
  G1 --release-archive-sha is stored in lower case; PAGE-STATIC names where the token came from; the frame of a block
     shows its lines with its file name (`lines_missing` for a block with no file or no lines). Cases SHA1 B7a B7f.
  R4 No CSS animation or transition keyword in the page; an unread card (neither fact on any root) is present, full size, outlined and labelled, never
     hidden or faded. Cases R4a R4b.
  R5 Every card says its counts are for the roots only (`roots_only_note`); a declaration that is a root of two groups is
     marked shared with the other group's id and counted once in totals. Case R5.
  R6 A `correction` block anchored to a root is shown on that root's card with kind, reader and date, outside the closed
     section. Case R6.
  B7 Every argument block is shown in ONE element with its frame first, drawn from strings.json plus the block's reader,
     date, lines and second readers; a step with an argument block shows its first sentence under the claim, a step
     without one the fixed sentence `no_argument`; an interpretation is shown apart in its own frame; every `#` link
     resolves to an id of the page (link_problems); a reading, argument, interpretation or correction block with no
     reader (BLOCK-NO-READER) or no date
     (BLOCK-NO-DATE) refuses the build. Cases B7a B7b B7c B7d B7e B7f.
  B1 --source-check SRC_ROOT: no output file holds a line of the release: stripped lines of at least 20 non-space
     characters of the release against the text lines of every output file (string values of the JSON except the
     name and id fields, text of the page except `<code>`). The run says what it ranged over. A planted shard that
     leaks a line is SOURCE-LEAK; an ids-only control stays green, on the page too. Cases B1a B1b B1c B1d B1e.
  K1 B1 is also run on the SOURCE lines of every copied note text BEFORE they are joined: each stripped line of at least 20
     non-space characters of a copied paragraph (the text of an argument or interpretation block that reaches an output)
     and of every note title is looked up in the release. A hit is SOURCE-LEAK naming the note and the block (or the
     field), never the line, exit 1, OUT_DIR absent. Without it a release line that stood on its own line of a paragraph
     is joined into a longer output line and is not seen. Cases PJ1 PJ2 PJ3 (a control builds in each).
  K2 The text values of the outline (claims, conditions) are checked line by line as well, split at newlines: a multi-line
     claim whose second line is a release line is a leak. Case PJ4.
  K3 The run says what the second check ranged over: a line `source check (copied note text): K copied source lines, L
     leaked; ...` with K counted by the tool (the non-empty source lines examined). Case PJ5.
  K4 The claim is narrow, and the run line, the LIMIT and the docs say so: no output line equals a release line and no
     line of copied note text equals one; a release line quoted INSIDE a longer sentence is not detected. A source line
     of fewer than 20 non-space characters is not compared. Case PJ6.

LIMIT. The page is a first draft of a real page: plain HTML, no script, no style beyond borders; the wording is the
strings file's, and the strings file's shape is PROVISIONAL (the table under `coverage` and every key named in this file
belong to whoever owns the wording; the fixtures of the self-test carry their own sentences, not the real ones). The
builder does not read a claim or a block and cannot say it is right; it copies no Lean text and no list item or table
cell text, and copies the first sentence and the paragraph of an `argument` or `interpretation` block whose target is a
paragraph, which are prose of the notes (an argument whose target is a list, table or lean block shows its frame and a link).
A first sentence is the text up to the first `.`, `!` or `?` followed by a space or the end. A reading block is the only
block that sets statement_read on a root without a claim; only an argument block sets proof_read. A level-0 note is under no group, and its
blocks feed no group. Coverage is for the roots only: members of a group that a root uses are not mapped, there is no
compiled data in this slice, and off-route marks (with their basis) are not built. B1 compares a release line with a
whole text line of an output file, and the source lines of the copied note text before they are joined (K1): a release
line quoted inside a longer sentence of the notes, or split across two lines, is not seen; the names and
ids that are excluded are the keys id, module, name, lean_name, file, note, block, parent, premises, sha256, link,
commits, files, release_id, release_archive_sha. P6's check is that each run of digits in the page text outside <code> appears among the digits
of the JSON (its hash fields left out) or the strings file: it cannot say the number is the right one. `dirty` is judged for the files of NOTES_DIR,
the outline and the strings file against the notes commit, and for tracked files of this folder against the tools
commit; an untracked file of the tools folder is not seen, and without --notes-commit the notes commit is `unknown` and
the notes are not judged. The sha256 of a root's file needs --source-check; a hash table in a note is not read. There is no
coverage word: the strings file's keys for the two facts are PROVISIONAL names (their wording is another seat's), the fourteen
of them: statement_read_line, statement_census_line, statement_not_read_line, proof_read_line, proof_not_read_line,
proof_not_applicable_line, proof_none_other_line, steps_proof_not_applicable_line, statement_count_line, proof_count_line, open_items_line, steps_statement_line, steps_proof_line, steps_open_items_line
(and the three labels of the evidence block, evidence_module_label, evidence_name_label, evidence_kind_label);
`coverage`, `not_read_yet`, `route_count`, `no_argument`, `roots_read` and `roots_not_read` are gone. A claim whose basis is
missing is read as `read` until the checker requires it (the run line says how many). The Evidence section shows the claim's reader and
date in its statement line (the card says only that the statement is read); for a null claim with a reading block the first reading block in note and block order. Its proof line names the reader and date of the first argument block of the root, by note id and then block number (the same
rule as the statement reader, not by date). Placeholders are checked in every value of the strings file at any depth from the
declared sets: a key that is not in the table declares none, so a new key is covered by default, and an `{name}` outside a value
that declares it, or a brace in a value that declares none, refuses the build. A claimed
group has one root, so the count lines appear only for null-claim groups. THE KIND decides whether a root has a proof: an
instance, or a def whose value is a proof term, does not count as having a proof for the page, whatever its body is; the builder
reads the kind from the table row of the root and does not look at the Lean text. A step with some roots that are theorems and
some that are definitions is read for the proof when every theorem root is: the definition roots are left out of the every-root
test, and the card counts over the theorem roots. A kind outside the eight the table holds is treated as no proof and listed as
KIND-NOTE; it is never refused. A card that shows a no-proof line uses proof_none_other_line when ANY of its proof-less roots
has such a kind (a step with several roots too), and proof_not_applicable_line otherwise; the first screen does not
distinguish: it shows steps_proof_not_applicable_line whenever no step has a proof, and a root of an unknown kind among the
top-level steps is not reachable on a real table (the table holds the eight kinds only). The source check ranges over what a reader sees: the text of claims, conditions and note titles
with the backticks of a span removed (on the JSON and data.js side, and on the copied title lines; the page skips <code>), the
other values as written, except the text of a block and a block's first sentence, which are compared BOTH as written and with the
backticks removed (so a release line that itself holds a span is still seen there); a release line that is inside a longer sentence
(of a claim, of block text or of a first sentence), or that is split by a span in its middle, is still not seen. The first sentence
is cut at the first `.`, `!` or `?` followed by white space even inside a span (`We apply `f. g` here.` gives `We apply `f.`, the
backtick left literal on the card); that cut is a known limit and is not changed here (case BT8). FORMULA-RAW ranges over argument, interpretation and sketch text (not a sketch's `unexpanded` entries). It is a mark detector, not a formula parser: a dollar amount, or any `$`, `\\(`, `\\[` or `\\begin{` outside a code
span, is listed too, and a formula inside a code span is not; F26 will convert formulas. A K1 source line is compared as it
stands in the note, so a release line wrapped in backticks within a longer line is found only on the JSON side. A code span (CODE) is the one place the page turns
claim or condition text into markup (F35 adds <strong> and a nested <ul> for block text; the static check has no list of allowed elements), and the only new element for those is <code>: the page's B1 and P6 checks skip the text inside <code>
(the JSON still holds the text with its backticks, and B1 checks that), so a release line or a number written inside backticks is
seen in the JSON and not on the page. The keys of PHR must hold their placeholders, so an Evidence value that says the fact without
the reader or the count is refused rather than printed without it. The sum assertions of F4 guard a MISSING flag, not a
WRONG one. A not_read block in a level-0 note is anchored to no group: it is not counted in totals.open_items and is shown on no card. NOTE-ID-DUPLICATE belongs to the checker of the
notes; the builder has no rule of its own for it (the checker refuses first). WORD-NOTE reads the
claim, the conditions, the note titles and the text of argument and interpretation blocks, not the strings file's
hrefs; it lists, it does not judge. The Evidence section shows a block's lines and file name together; a block with
lines and no file shows `lines_missing` for both, because the lines name no file. The notes are the files NOTES_DIR matches by notes_meta's default pattern. The page's
note links are the strings file's `note_href` with the note's file name filled in.

LIMIT (F24b). The page trusts the checker's rules on roles and forms: a model that breaks them (open_in_literature on an object, an
established on a result) is not guarded and may raise. A group with no root_role takes the class of its root's kind for the page.
The source check ranges, besides what is stated above, over the recognition's result, difference, note, citation source and where, a
sketch's paragraphs, list items and unexpanded entries (as written, span backticks removed and, for sketch text, each link as its text
and each link target as a line); WORD-NOTE does not read them. A link is `[text](target)` with a text of no bracket and a target of no
parenthesis or white space; a link text that holds `. ` is cut by the first-sentence rule (a known limit). Links in the recognition and
in the `unexpanded` entries are not rewritten. The strings rule R3 refuses `of the proof` in any value, so a wording that holds it (a
compiled part of the proof) is refused until the rule or the wording changes. A sketch belongs to the group named in its note's header, the group notes_meta checks it against (SKETCH-NO-ARGUMENT, SKETCH-DUPLICATE), and
shows on that group's card and in its JSON only: a root of another group among the sketch's further decls does not give that group the
sketch, and the sketch block is not in that group's block list either. A sketch whose header names a group that does not own a root of its
decls is refused by the checker (SKETCH-ROOT) and never reaches the page. A block's frame uses the roots of the card it is shown
on, by ruling (F34): a card speaks about its own root, so one block can be framed as a definition on one card and as a proof on another.
The static check's exemption for an <a class=citation> (and for a reaction anchor) is by class TOKEN: `citation extra` passes, `citationx` does
not, and the citation exemption holds for `href` alone.

LIMIT (F37). The card names nobody, but two places still can: the author's own text (a sketch or an argument that says who read what,
or a seat's name) and the first screen. A correction stays on the card with its kind and its title (what was wrong: a doubt a reader should
see); its reader and date are in the Evidence block list, in the who-span beside the block's kind (the existing line, no key of its own). The Evidence section is closed, not hidden: it is in the page and in the JSON for whoever opens it. The
order and the markup of the Evidence lines are stated above (F37); the card of several roots has no statement or proof line there, as
none on the card. The recognition's citations are listed with their opener for every citation (not only the ones with a url), the
source through the span rule like on the card. The wording of the Evidence keys is the wording seat's; this tool checks only the
placeholders and the builder-sentence rules (R3: forbidden words, no percent sign, no `of the proof`). `frames.interpretation` still
declares {reader} and {date} (a detector list that may use them; the real file holds none). (d), a record of the publishing commit
written by the builder, is not done here.

usage: build_site.py NOTES_DIR OUTLINE DECLS_TSV STRINGS OUT_DIR [--source-check SRC_ROOT] [--release-archive-sha HEX]
                     [--notes-commit REV --repo DIR] [--force]
       build_site.py --selftest [--only ID,ID]
"""
import contextlib
import copy
import fnmatch
import functools
import hashlib
import html
import html.parser
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import types
import urllib.parse

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load_sibling(name):
    """A module of this folder, loaded by file path (never through sys.path), under a private name."""
    key = "_build_site_" + name
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, os.path.join(_HERE, name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        keep, sys.dont_write_bytecode = sys.dont_write_bytecode, True
        try:
            spec.loader.exec_module(mod)
        except BaseException:
            sys.modules.pop(key, None)
            raise
        finally:
            sys.dont_write_bytecode = keep
    return sys.modules[key]


nm = _load_sibling("notes_meta")
rh = _load_sibling("rh_anchor")
sg = _load_sibling("scan_graph")

NAME_KEYS = frozenset(["id", "module", "name", "lean_name", "file", "note", "block", "parent", "premises", "sha256", "link",
                       "commits", "files", "release_id", "release_archive_sha"])


# ---------------------------------------------------------------- the tool

TEXT_KEYS = ("page_title", "mapped_line", "no_claim_label", "statement_read_line", "statement_census_line",
             "statement_not_read_line", "proof_read_line", "proof_not_read_line", "proof_not_applicable_line", "proof_none_other_line",
             "steps_proof_not_applicable_line", "statement_count_line",
             "proof_count_line", "open_items_line", "steps_statement_line", "steps_proof_line", "steps_open_items_line", "argument_frame",
             "interpretation_frame", "evidence_label", "evidence_module_label", "evidence_name_label", "evidence_kind_label",
             "roots_only_note", "dirty_note", "shared_note", "note_href",
             "recognition_result_known_line", "recognition_result_variant_line", "recognition_result_not_recognised_line",
             "recognition_result_open_line", "recognition_named_statement_known_line",
             "recognition_named_statement_variant_line", "recognition_named_statement_not_recognised_line",
             "recognition_named_statement_open_line", "recognition_object_known_line", "recognition_object_variant_line",
             "recognition_object_not_recognised_line", "recognition_not_written_line", "recognition_label_line",
             "recognition_citation_line", "recognition_citation_dated_line", "recognition_citation_open_line",
             "named_statement_use_line", "established_by_line", "established_not_traced_line", "sketch_frame",
             "sketch_basis_source", "sketch_basis_compiled", "sketch_note", "sketch_missing_line", "unexpanded_heading",
             "argument_frame_no_proof", "evidence_statement_read_line", "evidence_statement_census_line", "evidence_proof_read_line",
             "evidence_second_reader_line", "evidence_recognition_line", "evidence_citation_line", "evidence_established_line",
             "evidence_sketch_build_line")
# F37: the sentences of the card name nobody (no reader, date, file, lines or build); the keys of the Evidence section carry them
PLACEHOLDERS = {"evidence_statement_read_line": {"reader", "date"}, "evidence_statement_census_line": {"reader", "date"},
                "evidence_proof_read_line": {"reader", "date"}, "evidence_second_reader_line": {"reader", "date"},
                "evidence_recognition_line": {"reader", "date"}, "evidence_citation_line": {"source", "opened_by", "opened_on"},
                "evidence_established_line": {"name", "reader", "date"}, "evidence_sketch_build_line": {"build"},
                "statement_count_line": {"n", "m"}, "proof_count_line": {"n", "m"}, "open_items_line": {"n"},
                "steps_statement_line": {"n", "m"}, "steps_proof_line": {"n", "m"}, "steps_open_items_line": {"n"},
                "shared_note": {"groups"}, "note_href": {"file"},
                # a value nested in a list or object is declared under its path without the list indexes
                "frames.interpretation": {"reader", "date"},
                "recognition_result_known_line": {"result"},
                "recognition_result_variant_line": {"result"},
                "recognition_result_open_line": {"result", "source_date"},
                "recognition_named_statement_known_line": {"result"},
                "recognition_named_statement_variant_line": {"result"},
                "recognition_named_statement_open_line": {"result", "source_date"},
                "recognition_object_known_line": {"result"},
                "recognition_object_variant_line": {"result"},
                "recognition_citation_line": {"source", "where"},
                "recognition_citation_dated_line": {"source", "where"},
                "recognition_citation_open_line": {"source", "source_date", "where"},
                "established_by_line": {"name"},
                "sketch_frame": {"basis"},
                "reactions.href": {"card"}}
# the keys whose value must hold EVERY placeholder it declares (the notes' hrefs and the reaction hrefs may omit theirs)
REQUIRED_PLACEHOLDERS = {"evidence_statement_read_line": ("reader", "date"), "evidence_statement_census_line": ("reader", "date"),
                         "evidence_proof_read_line": ("reader", "date"), "evidence_second_reader_line": ("reader", "date"),
                         "evidence_recognition_line": ("reader", "date"), "evidence_citation_line": ("source", "opened_by", "opened_on"),
                         "evidence_established_line": ("name", "reader", "date"), "evidence_sketch_build_line": ("build",),
                         "statement_count_line": ("n", "m"), "proof_count_line": ("n", "m"),
                         "steps_statement_line": ("n", "m"), "steps_proof_line": ("n", "m"), "open_items_line": ("n",),
                         "steps_open_items_line": ("n",),
                         "recognition_result_known_line": ("result",),
                         "recognition_result_variant_line": ("result",),
                         "recognition_result_open_line": ("result", "source_date"),
                         "recognition_named_statement_known_line": ("result",),
                         "recognition_named_statement_variant_line": ("result",),
                         "recognition_named_statement_open_line": ("result", "source_date"),
                         "recognition_object_known_line": ("result",),
                         "recognition_object_variant_line": ("result",),
                         "recognition_citation_line": ("source", "where"),
                         "recognition_citation_dated_line": ("source", "where"),
                         "recognition_citation_open_line": ("source", "where", "source_date"),
                         "established_by_line": ("name",),
                         "sketch_frame": ("basis",)}
PROOF_KINDS = frozenset(["theorem", "lemma"])   # the table kinds that HAVE a proof; any other kind has none (F22)
KNOWN_KINDS = frozenset(["theorem", "lemma", "def", "structure", "instance", "abbrev", "class", "inductive"])   # the eight the table holds
NOT_READ_KEYS = ("statement_not_read_line", "proof_not_read_line")   # the only keys whose name may hold `not_read`
RETIRED_WORDS = ("Read by us", "Partly read", "Not read yet")        # the coverage scale F19 removed
LABEL_KEYS = ("chain", "level0_notes", "premises", "notes", "go_deeper", "blocks", "open_items", "file", "lines", "sha256",
              "read_more", "lines_missing")
FROZEN_WORDS = ("verified", "explained", "understood")
READER_KINDS = ("reading", "argument", "interpretation", "correction")
FORMS = ("known", "variant", "not_recognised", "open_in_literature")   # the forms of a recognition (F24)
SAFE_ID = re.compile(r"[A-Za-z0-9_][A-Za-z0-9._-]*")
_PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
_LINE_SPLIT = re.compile(r"\r\n|\n|\r")
_API = ("fetch(", "XMLHttpRequest", "WebSocket", "sendBeacon", "import(", "@import")
_OUT_NAMES = ("level0.json", "level1.json", "manifest.json", "data.js", "index.html")


class _Unreadable(Exception):
    """An input that cannot be read: exit 2, the message goes to stderr, nothing to stdout."""


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _dump(obj):
    return json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False)


def _js_safe(text):
    """JSON text with `<`, `>`, `&`, U+2028 and U+2029 written as \\uXXXX (they occur only inside strings), like the comments."""
    for ch, esc in (("<", "\\u003c"), (">", "\\u003e"), ("&", "\\u0026"), ("\u2028", "\\u2028"), ("\u2029", "\\u2029")):
        text = text.replace(ch, esc)
    return text


def _fill(template, **kw):
    """The template with each known {name} replaced in one pass; a name that is not given stays as written."""
    return _PLACEHOLDER.sub(lambda m: str(kw[m.group(1)]) if m.group(1) in kw else m.group(0), template)


def _first_sentence(text):
    m = re.match(r"(.+?[.!?])(?=\s|$)", text, re.S)
    return m.group(1) if m else text


def _nonspace(s):
    return len("".join(s.split()))


# ---- the coverage word

def fact_pairs(flags):
    """(how many flags are True, how many are False): anything else (None) is counted in neither, so a sum that does not add up
    to the total is visible."""
    return sum(1 for f in flags if f is True), sum(1 for f in flags if f is False)


def fact_triples(flags):
    """(how many flags are True, how many are False, how many are None = not applicable): anything else is counted in none of the
    three, so a sum that does not add up to the total is visible."""
    return (sum(1 for f in flags if f is True), sum(1 for f in flags if f is False), sum(1 for f in flags if f is None))


def _fact_flags(items, key):
    """The flags of one fact over steps or over the root rows of a group."""
    return [x[key] for x in items]


# ---- the checks of the page

def static_problems(page, js):
    """What the page or data.js holds that could make a request: a sorted list of ids from fetch(, XMLHttpRequest, WebSocket,
    sendBeacon, import(, @import, src=http, href=http (a reaction anchor excepted, and an <a class=citation> whose href starts
    `https://`, a source the reader may open), url( to a URL."""
    found = set()
    for text in (page, js):
        found.update(tok for tok in _API if tok in text)
        if re.search(r"url\(\s*['\"]?\s*(?:https?:)?//", text, re.I):
            found.add("url(")

    class P(html.parser.HTMLParser):
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            classes = (a.get("class") or "").split()
            for k, v in attrs:
                if not isinstance(v, str) or not re.match(r"\s*(?:https?:)?//", v, re.I):
                    continue
                if k in ("src", "srcset", "poster"):
                    found.add("src=http")
                elif k in ("href", "action", "formaction", "xlink:href") and not (
                        tag == "a" and ("reaction" in classes or (k == "href" and "citation" in classes and v.startswith("https://")))):
                    found.add("href=http")

    P(convert_charrefs=True).feed(page)
    return sorted(found)


_HTML_ELEMENTS = {"a": ("class", "href"), "article": ("class", "id"), "aside": (), "body": (), "code": (), "dd": (), "details": ("class",),
                  "div": ("class",), "dl": (), "dt": (), "h1": (), "h2": (), "h3": ("class",), "head": (), "header": (), "html": ("lang",),
                  "li": (), "main": (), "meta": ("charset",), "ol": (), "p": ("class",), "section": ("class",), "span": ("class",),
                  "strong": (), "style": (), "summary": (), "time": (), "title": (), "ul": ("class",)}
_MATHML_ELEMENTS = ("math", "mrow", "mi", "mn", "mo", "msub", "msup", "msubsup", "mover", "munder", "munderover", "mspace")
_MATHML_ATTRIBUTES = ("mathvariant", "stretchy", "form")
# Every element the built page may hold, with the attributes each may carry: the 29 elements the builder emits (measured over the
# self-test fixtures and a build of the notes of the repository, not guessed) and the 12 of MathML Core that the formula converter writes
# (F26B), with mathvariant, stretchy and form on the MathML elements only. 41 elements, 49 element-attribute pairs.
ALLOWED_ELEMENTS = dict(_HTML_ELEMENTS, **{t: _MATHML_ATTRIBUTES for t in _MATHML_ELEMENTS})


def element_problems(page):
    """What the page holds outside ALLOWED_ELEMENTS: a sorted list of `element <name>` for each start tag of an element not in the list
    and `attribute <name> on <element>` for each attribute an allowed element may not carry. The BUILT page is read with html.parser;
    an end tag, a comment and the doctype are not looked at."""
    found = set()

    class P(html.parser.HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag not in ALLOWED_ELEMENTS:
                found.add("element " + tag)
                return
            found.update(f"attribute {k} on {tag}" for k, _v in attrs if k not in ALLOWED_ELEMENTS[tag])

    P(convert_charrefs=True).feed(page)
    return sorted(found)


def link_problems(page):
    """Every `#` link that has no element of that id on the page (as `#id`), then every id used twice (`duplicate id X`)."""
    ids, links = [], []

    class P(html.parser.HTMLParser):
        def handle_starttag(self, tag, attrs):
            a = dict(attrs)
            if a.get("id") is not None:
                ids.append(a["id"])
            h = a.get("href")
            if tag in ("a", "area") and isinstance(h, str) and h.startswith("#") and len(h) > 1:
                links.append(urllib.parse.unquote(h[1:]))

    P(convert_charrefs=True).feed(page)
    known = set(ids)
    out = ["#" + h for h in dict.fromkeys(links) if h not in known]
    out += ["duplicate id " + i for i in sorted({i for i in ids if ids.count(i) > 1})]
    return out


def _page_text(page, skip=("style", "script")):
    """The text nodes of the page outside the tags in `skip`, as one list of strings."""
    out, depth = [], {t: 0 for t in skip}

    class P(html.parser.HTMLParser):
        def handle_starttag(self, tag, attrs):
            if tag in depth:
                depth[tag] += 1

        def handle_endtag(self, tag):
            if tag in depth and depth[tag]:
                depth[tag] -= 1

        def handle_data(self, data):
            if not any(depth.values()):
                out.append(data)

    P(convert_charrefs=True).feed(page)
    return out


HASH_KEYS = frozenset(["sha256", "files", "release_archive_sha", "commits"])


def number_pool(objs):
    """The text whose runs of digits the numbers of the page may come from: the JSON of the build with the fields that hold
    hashes (hex digits) left out, so that a hash cannot vouch for a small number."""
    def strip(v):
        if isinstance(v, dict):
            return {k: strip(x) for k, x in v.items() if k not in HASH_KEYS}
        if isinstance(v, list):
            return [strip(x) for x in v]
        return v
    return "\n".join(json.dumps(strip(o), sort_keys=True, ensure_ascii=False) for o in objs)


def number_problems(page, json_text, strings_text):
    """The runs of digits in the text of the page (outside <code>, which holds names, ids and hashes) that are in neither the
    JSON nor the strings file."""
    allowed = set(re.findall(r"\d+", json_text)) | set(re.findall(r"\d+", strings_text))
    seen = set(re.findall(r"\d+", " ".join(_page_text(page, skip=("style", "script", "code")))))
    return sorted(seen - allowed, key=lambda d: (len(d), d))


# ---- B1: no release text

def _unspan(text):
    """The text as a reader sees it: each span between single backticks (notes_meta's _BACKTICK_SPAN, the one definition) replaced by
    its content. Doubled backticks, an unpaired one and a pair over a line break are not spans and stay as written."""
    return nm._BACKTICK_SPAN.sub(lambda mt: mt.group(1), text)


def _masked(text):
    """(the text with each single-backtick span replaced by a private-use character, the index and the character again; the contents
    of the spans in order; that character). The character is one that the text does not hold."""
    tok = next(chr(c) for c in range(0xE000, 0xF900) if chr(c) not in text)
    spans = []

    def take(mt):
        spans.append(mt.group(1))
        return f"{tok}{len(spans) - 1}{tok}"
    return nm._BACKTICK_SPAN.sub(take, text), spans, tok


@functools.lru_cache(maxsize=None)
def _link_pattern(tok):
    """A markdown link `[text](target)` in masked text: a text of one or more characters with no bracket, then a target with no
    parenthesis, no white space and no mask character (a span binds tighter than a link, so a link never starts or ends in one); not
    an image (`![a](b)`: the bracket pair follows a `!`)."""
    return re.compile(r"(?<!!)\[([^\[\]]+)\]\(([^()\s" + re.escape(tok) + r"]*)\)")


def _delink(masked, tok):
    """(the masked text with each link replaced by its text, the targets in order)."""
    targets = []

    def one(mt):
        targets.append(mt.group(2))
        return mt.group(1)
    return _link_pattern(tok).sub(one, masked), targets


def _link_targets(text):
    """The targets of the links of a block's text that lie outside its code spans, in order."""
    masked, _spans, tok = _masked(text)
    return _delink(masked, tok)[1]


_BOLD = re.compile(r"(?<!\*)\*\*(?!\*)([^\r\n]+?)(?<!\*)\*\*(?!\*)")


def _bold_pieces(masked):
    """[(is bold, text)] for masked text: a pair of double asterisks on one line (no LF or CR between) around text that is not only
    white space, neither pair next to a third asterisk, is a bold piece holding the text between them; every other stretch is a plain
    piece, its asterisks as written. Run on text with the spans masked and the links taken out, so an asterisk in a span is not seen
    and a link text may be bold."""
    out, pos = [], 0
    for mt in _BOLD.finditer(masked):
        if not mt.group(1).strip():
            continue
        if mt.start() > pos:
            out.append((False, masked[pos:mt.start()]))
        out.append((True, mt.group(1)))
        pos = mt.end()
    if pos < len(masked):
        out.append((False, masked[pos:]))
    return out


def _bold_unpaired(text):
    """True when a `**` is left in the block text once its code spans, its links and its bold pairs are taken out (the text a reader
    sees with a literal `**` in it)."""
    masked, _spans, tok = _masked(text)
    return any("**" in t for bold, t in _bold_pieces(_delink(masked, tok)[0]) if not bold)


def _shown(text):
    """The block text as a reader sees it: each link as its text, each bold pair as its content (no asterisks) and each span as its
    content (no backticks)."""
    masked, spans, tok = _masked(text)
    shown = "".join(t for _bold, t in _bold_pieces(_delink(masked, tok)[0]))
    return re.sub(re.escape(tok) + r"(\d+)" + re.escape(tok), lambda mt: spans[int(mt.group(1))], shown)


def _value_lines(obj, seen=False, key=None):
    """Every line of every string value of a parsed JSON, except the values under a key of NAME_KEYS (names and ids). The values a
    reader sees through the span rule (the text of a claim, a condition, a note's list_title) are compared with the backticks
    of their spans removed (`seen` is True); the text of a block, a first sentence and a paragraph or item of a sketch are compared
    as written, with the backticks removed, as the reader sees them (each link as its text) and by each link target as a line
    (`seen` is "block"); the other author text of the F24b outputs (the recognition's result, difference, citation source and
    where, a sketch's unexpanded entries) as written and with the backticks removed (`seen` is "both"), because a release line may
    itself hold a span; the JSON itself keeps them."""
    if isinstance(obj, str):
        if seen in ("both", "block"):
            yield from obj.split("\n")
        yield from (_unspan(obj) if seen else obj).split("\n")
        if seen == "block":
            yield from _shown(obj).split("\n")
            yield from _link_targets(obj)
    elif isinstance(obj, list):
        for x in obj:
            yield from _value_lines(x, seen, key)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            if k not in NAME_KEYS or (k == "note" and key == "recognition"):
                if k == "first_sentence" or (k in ("text", "items") and key in ("blocks", "items")):
                    mode = "block"
                elif (k in ("result", "difference", "note") and key == "recognition") or (k in ("source", "where") and key == "citations") \
                        or k == "unexpanded":
                    mode = "both"
                else:
                    mode = k in ("conditions", "list_title") or (k == "text" and key == "claim")
                yield from _value_lines(v, mode, k)


def _output_lines(rel, data):
    text = data.decode("utf-8")
    if rel.endswith(".json"):
        return list(_value_lines(json.loads(text)))
    if rel == "data.js":
        return list(_value_lines(json.loads(text[len("window.RH_DATA = "):-len(";\n")])))
    if rel.endswith(".html"):
        return [ln for chunk in _page_text(text, skip=("style", "script", "code")) for ln in chunk.split("\n")]
    return text.split("\n")


def leak_check(files, src_root, copied=None):
    """(the files that hold a line of the release, what was ranged over). `files` maps a relative path to bytes. A line counts
    when it has at least 20 non-space characters, compared stripped, as a whole line of a text of an output file (a string
    value of the JSON outside the name and id fields, a text node of the page outside <code>). `copied`, when given, is a list
    of (note id, what, source lines) for the note text that is copied into the outputs: its lines are compared as they stand in
    the note, before they are joined; the stats then also hold `copied_lines` (the non-empty source lines examined) and
    `copied_leaks` (the sorted (note id, what) that hold a line of the release). A release line quoted inside a longer line is
    not seen."""
    candidates, n_out = {}, 0
    copied_cand, n_copied = {}, 0
    for note, what, lines in copied or []:
        for ln in lines:
            t = ln.strip()
            if t:
                n_copied += 1
                if _nonspace(t) >= 20:
                    copied_cand.setdefault(t, set()).add((note, what))
    for rel in sorted(files):
        for ln in _output_lines(rel, files[rel]):
            s = ln.strip()
            if s:
                n_out += 1
                if _nonspace(s) >= 20:
                    candidates.setdefault(s, set()).add(rel)
    mods = sg.walk_lean(src_root)
    leaked, copied_leaked, n_lines, bad = set(), set(), 0, []
    for _module, path in mods:
        text, ok = sg.read_text(path)
        if not ok:
            bad.append(os.path.relpath(path, src_root).replace(os.sep, "/"))
            continue
        n_lines += text.count("\n") + (0 if text == "" or text.endswith("\n") else 1)
        for ln in text.split("\n"):
            s = ln.strip()
            if s in candidates:
                leaked.update(candidates[s])
            if s in copied_cand:
                copied_leaked.update(copied_cand[s])
    if bad:
        raise ValueError("cannot read: " + ", ".join(bad))
    stats = {"release_files": len(mods), "release_lines": n_lines, "output_files": len(files), "output_lines": n_out}
    if copied is not None:
        stats["copied_lines"] = n_copied
        stats["copied_leaks"] = sorted(copied_leaked)
    return sorted(leaked), stats


# ---- the strings file

def _walk_strings(v, path):
    if isinstance(v, str):
        yield path, v
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from _walk_strings(x, f"{path}[{i}]")
    elif isinstance(v, dict):
        for k, x in v.items():
            if not (path == "" and k == "forbidden_words"):
                yield from _walk_strings(x, f"{path}.{k}" if path else k)


def _strings_problems(s):
    """[(code, path, message)] for the strings file: every key the builder reads must be there with its shape; a word of the
    forbidden list (and verified, explained, understood) must not occur in any value."""
    out = []

    def bad(path, msg, code="STRINGS-KEY"):
        out.append((code, path, msg))

    def need_str(path, v):
        if not (isinstance(v, str) and v != ""):
            bad(path, "must be a non-empty string")
            return False
        return True

    if not isinstance(s, dict):
        return [("STRINGS-KEY", "(top level)", "must be a JSON object")]
    for k in TEXT_KEYS:
        if k not in s:
            bad(k, "missing")
        else:
            need_str(k, s[k])
    for k in s:
        if k == "coverage":
            bad(k, "is retired: the strings file no longer carries a word scale")
        elif "not_read" in k and k not in NOT_READ_KEYS:
            bad(k, "is refused: only statement_not_read_line and proof_not_read_line may carry not_read in their name")
    if isinstance(s.get("labels"), dict):
        for k in s["labels"]:
            if "not_read" in k:
                bad(f"labels.{k}", "is refused: a label's name may not carry not_read")
    fs = s.get("first_screen", None)
    if "first_screen" not in s:
        bad("first_screen", "missing")
    elif not (isinstance(fs, list) and fs and all(isinstance(x, str) and x for x in fs)):
        bad("first_screen", "must be a non-empty list of non-empty strings")
    if "frames" not in s:
        bad("frames", "missing")
    elif not isinstance(s["frames"], dict):
        bad("frames", "must be an object")
    else:
        for k in ("argument", "interpretation", "claim"):
            if k not in s["frames"]:
                bad(f"frames.{k}", "missing")
            elif not (isinstance(s["frames"][k], list) and all(isinstance(x, str) for x in s["frames"][k])):
                bad(f"frames.{k}", "must be a list of strings")
    if "reactions" not in s:
        bad("reactions", "missing")
    elif not (isinstance(s["reactions"], list) and len(s["reactions"]) == 3):
        bad("reactions", "must be a list of three {label, href}")
    else:
        for i, r in enumerate(s["reactions"]):
            if not (isinstance(r, dict) and set(r) == {"label", "href"}):
                bad(f"reactions[{i}]", "must be an object with exactly the keys label and href")
                continue
            need_str(f"reactions[{i}].label", r["label"])
            if need_str(f"reactions[{i}].href", r["href"]):
                if not r["href"].startswith("https://"):
                    bad(f"reactions[{i}].href", "must be an https URL")
    fw = s.get("forbidden_words")
    if "forbidden_words" not in s:
        bad("forbidden_words", "missing")
    elif not (isinstance(fw, list) and all(isinstance(x, str) and x for x in fw)):
        bad("forbidden_words", "must be a list of non-empty strings")
    if "labels" not in s:
        bad("labels", "missing")
    elif not isinstance(s["labels"], dict):
        bad("labels", "must be an object")
    else:
        lab = s["labels"]
        for k in LABEL_KEYS:
            if k not in lab:
                bad(f"labels.{k}", "missing")
            else:
                need_str(f"labels.{k}", lab[k])
        if "kinds" not in lab:
            bad("labels.kinds", "missing")
        elif not isinstance(lab["kinds"], dict):
            bad("labels.kinds", "must be an object")
        else:
            for k in rh.KINDS:
                if k not in lab["kinds"]:
                    bad(f"labels.kinds.{k}", "missing")
                else:
                    need_str(f"labels.kinds.{k}", lab["kinds"][k])
    words = list(FROZEN_WORDS) + [w for w in (fw if isinstance(fw, list) else []) if isinstance(w, str) and w]
    for path, v in _walk_strings(s, ""):   # placeholders: every value, at any depth, holds only what its key declares
        allowed = PLACEHOLDERS.get(re.sub(r"\[\d+\]", "", path), set())   # a key that is not in the table declares none
        unknown = [t for t in dict.fromkeys(_PLACEHOLDER.findall(v)) if t not in allowed]
        for t in unknown:
            bad(path, "has an unknown placeholder {" + t + "}")
        if not unknown and not allowed and ("{" in v or "}" in v):
            bad(path, "holds a brace, and this key declares no placeholder")
        for t in REQUIRED_PLACEHOLDERS.get(path, ()):
            if "{" + t + "}" not in v:
                bad(path, "is missing the placeholder {" + t + "}")
    for path, v in _walk_strings(s, ""):
        if path == "note_href" or re.fullmatch(r"reactions\[\d+\]\.href", path):
            continue   # an address, not a sentence of the page
        for w in words:
            if re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", v, re.I):
                bad(path, f"holds the word {w!r}, which the page never says", "STRINGS-FORBIDDEN")
                break
        else:
            old = next((x for x in RETIRED_WORDS if re.search(r"(?<![A-Za-z])" + re.escape(x) + r"(?![A-Za-z])", v)), None)
            if old:
                bad(path, f"holds {old!r}, a word of the retired coverage scale (exact-case match; the lowercase phrase "
                          "`not read yet` is allowed inside status wording)", "STRINGS-FORBIDDEN")
            elif "%" in v or re.search(r"of\s+the\s+proof", v, re.I):
                bad(path, "holds a percent sign or `of the proof`, which the page never says in its own sentences",
                    "STRINGS-FORBIDDEN")
    return out


# ---- commit ids

def _vcs(top, *args):
    try:
        return subprocess.run(["git", "-c", "safe.directory=*", "-C", top, *args], capture_output=True, text=True, timeout=60,
                              env=dict(os.environ, LC_ALL="C", LANG="C"))
    except (OSError, subprocess.SubprocessError):
        return None


def _tools_state():
    """(commit of the folder of this file or `unknown`, whether a tracked file of it differs from that commit)."""
    head = _vcs(_HERE, "rev-parse", "HEAD")
    if head is None or head.returncode != 0 or not re.fullmatch(r"[0-9a-f]{40,64}", head.stdout.strip()):
        return "unknown", False
    st = _vcs(_HERE, "status", "--porcelain", "--untracked-files=no", "--", ".")
    return head.stdout.strip(), bool(st is None or st.returncode != 0 or st.stdout.strip())


def _notes_state(repo, rev, paths):
    """(the commit REV names, whether any of `paths` that lie in the repository differs from it or has untracked files)."""
    repo = repo if repo is not None else os.path.dirname(os.path.abspath(paths[0]))
    if not os.path.isdir(repo):
        raise _Unreadable(f"--repo is not a directory: {repo}")
    top = _vcs(repo, "rev-parse", "--show-toplevel")
    if top is None or top.returncode != 0:
        raise _Unreadable("--repo is not inside a git work tree (or git cannot be run)")
    top = os.path.realpath(top.stdout.strip())
    commit = _vcs(top, "rev-parse", "--verify", "--quiet", rev + "^{commit}")
    if commit.returncode != 0:
        raise _Unreadable(f"cannot resolve --notes-commit {rev} to a commit")
    rel = []
    for p in paths:
        r = os.path.relpath(os.path.realpath(p), top)
        if not r.startswith(".."):
            rel.append(r)
    if not rel:
        return commit.stdout.strip(), False
    st, df = _vcs(top, "status", "--porcelain", "--", *rel), _vcs(top, "diff", "--name-only", commit.stdout.strip(), "--", *rel)
    dirty = any(x is None or x.returncode != 0 or x.stdout.strip() for x in (st, df))
    return commit.stdout.strip(), dirty


# ---- the model: the outline, the notes and the table, joined

def _read_json(path, what):
    try:
        with open(path, "rb") as fh:
            return json.loads(fh.read().decode("utf-8"))
    except (OSError, ValueError, RecursionError) as e:
        raise _Unreadable(f"cannot read the {what}: {e}")


def _decl_rows(path):
    rows = {}
    with open(path, encoding="utf-8") as fh:
        for raw in fh.read().split("\n"):
            c = raw.rstrip("\r").split("\t")
            if len(c) == 6 and c != nm.DECL_COLS and not raw.startswith("#"):
                rows.setdefault((c[0], c[1]), (c[2], int(c[3]), int(c[4])))
    return rows


def _paragraph(lines, target):
    return " ".join(x.strip() for x in lines[target["first_line"] - 1:target["last_line"]])


_ITEM_MARK = re.compile(r"[ \t]*(?:[-*+]|\d{1,9}[.)])[ \t]+")
_SUB_MARK = re.compile(r"[-*][ \t]+\S")   # a sub-item starts (on its stripped line) with `- ` or `* ` and a text


def _indent(line):
    return len(line.expandtabs(4)) - len(line.expandtabs(4).lstrip(" "))


def _sketch(text, lines, anchor_line, d):
    """({basis, build, unexpanded, blocks}, the source lines it copies) for a sketch block: its blocks are the elements rh_anchor.run_at
    gives for the anchor on `anchor_line`, a paragraph as its lines joined by spaces and a list as its items, each item its lines joined
    by spaces with the list marker taken off its first (the anchor lines of the note left out). A run the checker would refuse is empty."""
    run = rh.run_at(text, anchor_line, d.get("span", 1))
    blocks, src, depth = [], [], False
    for kind, first, last in (run if isinstance(run, list) else []):
        if kind == "paragraph":
            blocks.append({"type": "paragraph", "text": _paragraph(lines, {"first_line": first, "last_line": last})})
            src += lines[first - 1:last]
            continue
        items = []
        spans = rh.target_at(text, first)["items"]
        for f, l in spans:
            parts = [_ITEM_MARK.sub("", lines[f - 1], count=1)] + lines[f:l]
            parts = [x.strip() for x in parts if x.strip() and not x.lstrip().startswith("<!-- rh-")]
            src += parts
            own, subs, sub_ind, base = [_ITEM_MARK.sub("", lines[f - 1], count=1).strip()], [], None, _indent(lines[f - 1])
            for ln in lines[f:l]:
                st = ln.strip()
                if not st or st.startswith("<!-- rh-"):
                    continue
                ind = _indent(ln)
                if _SUB_MARK.match(st) and ind > base:
                    if sub_ind is None or ind <= sub_ind:
                        sub_ind = ind if sub_ind is None else sub_ind
                        subs.append([st[1:].strip()])
                        continue
                    depth = True   # a deeper level: its text, marker kept, joins its parent sub-item as it did before
                (subs[-1] if subs else own).append(st)
            own = " ".join(x for x in own if x)
            items.append({"text": own, "items": [" ".join(x) for x in subs]} if subs else " ".join(parts))
        blocks.append({"type": "list", "ordered": re.match(r"[ \t]*\d{1,9}[.)]", lines[spans[0][0] - 1]) is not None, "items": items})
    return {"basis": d.get("basis"), "build": d.get("build"), "unexpanded": list(d.get("unexpanded", [])), "blocks": blocks,
            "_depth": depth}, src


def _load_notes(notes_dir, strings):
    """The notes in name order: id, title, level, group, link, and each block's record (its decls kept apart)."""
    notes = []
    for name in sorted(n for n in os.listdir(notes_dir) if fnmatch.fnmatchcase(n, nm.DEFAULT_GLOB)
                       and os.path.isfile(os.path.join(notes_dir, n))):
        with open(os.path.join(notes_dir, name), "rb") as fh:
            text = fh.read().decode("utf-8")
        headers, blocks, _bad = rh.parse_note(text)
        h = headers[0].data
        lines = _LINE_SPLIT.split(text)
        note = {"name": name, "id": h["id"], "title": h["list_title"], "level": h["level"], "group": h["group"],
                "link": _fill(strings["note_href"], file=urllib.parse.quote(name, safe="")), "blocks": []}
        for b in blocks:
            d, t = b.data, b.target or {}
            rec = {"block": d["id"], "kind": d["kind"], "note": h["id"], "reader": d.get("reader"), "date": d.get("date")}
            for k in ("item", "row", "col", "file", "lines", "needs", "second_readers"):
                if k in d:
                    rec[k] = d[k]
            if d["kind"] in ("argument", "interpretation"):
                para = _paragraph(lines, t) if t.get("type") == "paragraph" else None
                rec["text"] = para
                rec["first_sentence"] = _first_sentence(para) if para else None
                rec["_src"] = lines[t["first_line"] - 1:t["last_line"]] if para else None
            if d["kind"] == "sketch":
                rec["_sk"], rec["_src"] = _sketch(text, lines, b.line, d)
            rec["_decls"] = [(e["module"], e["name"]) for e in d.get("decls", [])]
            note["blocks"].append(rec)
        notes.append(note)
    notes.sort(key=lambda n: (n["id"], n["name"]))
    return notes


def _block_key(rec):
    return rec["note"], int(rec["block"].rsplit(".b", 1)[1])


def _note_ref(n):
    return {"link": n["link"], "list_title": n["title"], "note": n["id"]}


class _Model:
    pass


def _model(notes_dir, odata, rows, strings, src_root, errors):
    m = _Model()
    m.release = odata["release"]
    m.notes = _load_notes(notes_dir, strings)
    groups = {}
    for g in odata["groups"]:
        groups.setdefault(g["id"], g)
    m.order = sorted(groups, key=lambda i: (groups[i]["level"], groups[i]["order"], i))
    children = {}
    for gid, g in groups.items():
        children.setdefault(g["parent"], []).append(gid)
    for k in children:
        children[k].sort(key=lambda i: groups[i]["order"])
    m.children, m.groups = children, groups
    anchored = {}
    for n in m.notes:
        if n["level"] != 0:
            for rec in n["blocks"]:
                for dm in rec["_decls"]:
                    anchored.setdefault(dm, []).append(rec)
    owners = {}
    for gid, g in groups.items():
        for r in g["roots"]:
            owners.setdefault((r["module"], r["name"]), []).append(gid)
    by_note = {n["id"]: n for n in m.notes}
    m.files, m.summary, m.copied, seen_blocks, open_blocks = {}, {}, [], set(), set()
    m.kind_notes = []
    for gid, g in groups.items():
        roots = [(r["module"], r["name"]) for r in g["roots"]]
        blocks = {}
        for r in roots:
            for rec in anchored.get(r, []):
                blocks.setdefault(rec["block"], rec)
        brecs, sketches = [], []
        for rec in sorted(blocks.values(), key=_block_key):
            if rec["kind"] == "sketch" and by_note[rec["note"]]["group"] != gid:
                continue   # a sketch is of the group its note's header names (as notes_meta assigns it), whatever else its decls list
            out = {k: v for k, v in rec.items() if k not in ("_decls", "_src", "_sk")}
            if rec.get("_src") and rec["block"] not in seen_blocks:
                seen_blocks.add(rec["block"])
                m.copied.append((rec["note"], "block " + rec["block"], rec["_src"]))
            out["roots"] = [{"module": a, "name": b} for a, b in roots if (a, b) in rec["_decls"]]
            brecs.append(out)
            if rec["kind"] == "sketch":
                sk = rec["_sk"]
                sketches.append({"note": rec["note"], "block": rec["block"], "reader": rec["reader"], "date": rec["date"],
                                 "basis": sk["basis"], "build": sk["build"], "unexpanded": list(sk["unexpanded"]),
                                 "roots": out["roots"], "blocks": sk["blocks"]})
        root_rows = []
        for mod, name in roots:
            kind, first, last = rows[(mod, name)]
            rel = mod.replace(".", "/") + ".lean"
            sha = None
            if src_root is not None and os.path.isfile(os.path.join(src_root, *rel.split("/"))):
                with open(os.path.join(src_root, *rel.split("/")), "rb") as fh:
                    sha = _sha(fh.read())
            root_rows.append({"module": mod, "name": name, "kind": kind, "file": rel, "lines": [first, last], "sha256": sha,
                              "shared_with": sorted(o for o in owners[(mod, name)] if o != gid)})
        claim = g["claim"]
        claim_read = claim is not None and claim.get("basis", "read") == "read"
        for row, r in zip(root_rows, roots):
            kinds = {x["kind"] for x in anchored.get(r, [])}
            row["statement_read"] = claim_read or "reading" in kinds
            if row["kind"] in PROOF_KINDS:
                row["proof_read"] = "argument" in kinds
            else:   # a definition, a structure, an instance ...: no proof to read, so the fact is not applicable (null)
                row["proof_read"] = None
                if row["kind"] not in KNOWN_KINDS:
                    m.kind_notes.append((gid, f"{row['module']}.{row['name']}", row["kind"]))
        applicable = [r["proof_read"] for r in root_rows if r["proof_read"] is not None]
        by = None
        if len(roots) == 1:   # one root: who read the statement (the claim, else the first reading block of the root)
            first = sorted((x for x in anchored.get(roots[0], []) if x["kind"] == "reading"), key=_block_key)
            if claim_read:
                by = {"source": "claim", "reader": claim["reader"], "date": claim["date"]}
            elif first:
                by = {"source": "block", "reader": first[0]["reader"], "date": first[0]["date"]}
            elif claim is not None:
                by = {"source": "census", "reader": claim["reader"], "date": claim["date"]}
        open_here = [b["block"] for b in brecs if b["kind"] == "not_read"]
        open_blocks.update(open_here)
        roots_open = sum(1 for r in roots if any(x["kind"] == "not_read" for x in anchored.get(r, [])))
        ids = {n["id"] for n in m.notes if n["level"] != 0 and n["group"] == gid} | {b["note"] for b in brecs}
        notes = [_note_ref(by_note[i]) for i in sorted(ids)]
        if not roots:
            errors.append(("FACTS-NO-ROOT", gid, "group has no root, so no fact claim"))
        role = g.get("root_role") if claim is not None and isinstance(g.get("root_role"), str) else None
        root_kind = root_rows[0]["kind"] if claim is not None and len(root_rows) == 1 else None
        recognition = copy.deepcopy(g["recognition"]) if claim is not None and isinstance(g.get("recognition"), dict) else None
        m.summary[gid] = {
            "id": gid, "level": g["level"], "order": g["order"], "parent": g["parent"],
            "claim": None if claim is None else {"text": claim["text"], "reader": claim["reader"], "date": claim["date"],
                                                 "basis": claim.get("basis", "read"), "conditions": claim.get("conditions", [])},
            "premises": list(g["premises"]),
            "root_role": role, "root_kind": root_kind, "recognition": recognition,
            "lean_name": g["roots"][0]["name"] if roots else None,
            "claim_label": strings["no_claim_label"] if claim is None else None,
            "statement_read": bool(roots) and all(r["statement_read"] for r in root_rows),
            # true when every root that HAS a proof has it read (a root without a proof is left out of the test), null when no
            # root has a proof, false otherwise (and for a group with no root: never counted as read)
            "proof_read": False if not roots else (all(applicable) if applicable else None),
            "statement_by": by,
            "unread": not any(r["statement_read"] is True or r["proof_read"] is True for r in root_rows),
            "counts": {"roots": len(roots), "roots_statement_read": sum(1 for r in root_rows if r["statement_read"]),
                       "roots_proof_read": sum(1 for r in root_rows if r["proof_read"] is True),
                       "roots_proof_applicable": len(applicable), "roots_open_items": roots_open,
                       "open_items": len(open_here)},
            "notes": notes, "roots_only": True}
        m.files[gid] = {"id": gid, "level": g["level"], "parent": g["parent"], "premises": list(g["premises"]), "roots": root_rows,
                        "root_role": role, "root_kind": root_kind, "recognition": copy.deepcopy(recognition), "sketches": sketches,
                        "blocks": brecs,
                        "open_items": [{"block": b["block"], "needs": b["needs"], "note": b["note"], "roots": b["roots"]}
                                       for b in brecs if b["kind"] == "not_read"], "notes": notes}
    m.steps = [i for i in children.get("root", [])]
    m.header_notes = [_note_ref(n) for n in m.notes if n["level"] == 0]
    m.totals = {"blocks": sum(len(n["blocks"]) for n in m.notes), "groups": len(groups), "notes": len(m.notes),
                "open_items": len(open_blocks), "roots": len(owners)}
    return m


# `of the proof` after a number, a percent sign or a quantity word (the word list is PROVISIONAL; its owner rules it)
_FRACTION = re.compile(r"(?:\d+(?:\.\d+)?\s*%\s*|\d+(?:\.\d+)?\s+|%\s*|\b(?:half|third|quarter|most|part|fraction|portion|share|"
                       r"majority|all)\s+)of\s+the\s+proof", re.I)


def _word_notes(m, s):
    """[(where, word)]: the forbidden words, and `of the proof` (a phrase or a percent sign), in the text of the claims, the
    conditions, the note titles and the argument and interpretation blocks. Only a listing."""
    words = list(dict.fromkeys(list(FROZEN_WORDS) + [w for w in s["forbidden_words"] if w]))

    def hits(text):
        out = [w for w in words if re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", text, re.I)]
        if _FRACTION.search(text):
            out.append("of the proof")
        elif "%" in text:
            out.append("%")
        return out

    found = []
    for gid in sorted(m.groups):
        claim = m.groups[gid]["claim"]
        if claim:
            found += [(f"{gid}.claim", w) for w in hits(claim["text"])]
            for i, c in enumerate(claim.get("conditions", [])):
                found += [(f"{gid}.conditions[{i}]", w) for w in hits(c)]
    for n in m.notes:
        found += [(f"note:{n['id']}.list_title", w) for w in hits(n["title"])]
        for b in n["blocks"]:
            if b.get("text"):
                found += [(f"block:{b['block']}.text", w) for w in hits(b["text"])]
    return found


_FORMULA_MARK = re.compile(r"\$|\\\(|\\\[|\\begin\{")


def _sketch_texts(sk):
    """The texts of a sketch (its `_sk` record): each paragraph, each list item and each sub-item."""
    out = []
    for blk in sk.get("blocks", []):
        if blk["type"] == "paragraph":
            out.append(blk["text"])
        for x in blk.get("items", []):
            out += [x] if isinstance(x, str) else [x["text"]] + list(x["items"])
    return out


def _block_texts(b):
    """The author texts of a block that the page shows as block text: the paragraph of an argument or interpretation, the paragraphs
    and list items of a sketch, nothing for any other kind."""
    if b["kind"] in ("argument", "interpretation"):
        return [b["text"]] if b.get("text") else []
    return _sketch_texts(b.get("_sk") or {}) if b["kind"] == "sketch" else []


def _formula_raw(m):
    """[block id]: the argument, interpretation and sketch blocks, in note order, whose text (a sketch's paragraphs and list items)
    outside its single-backtick spans holds a formula mark (`$`, `\\(`, `\\[` or `\\begin{`), once per block. A mark detector, not a
    formula parser. Only a listing."""
    return [b["block"] for n in m.notes for b in n["blocks"]
            if any(_FORMULA_MARK.search(nm._BACKTICK_SPAN.sub(" ", x)) for x in _block_texts(b))]


def _bold_unpaired_blocks(m):
    """[block id]: the argument, interpretation and sketch blocks, in note order, whose text (a sketch's paragraphs, items and sub-items,
    an argument's first sentence too, which is cut at its own) holds a `**` that is no pair, once per block. Only a listing."""
    return [b["block"] for n in m.notes for b in n["blocks"]
            if any(_bold_unpaired(x) for x in _block_texts(b) + ([b["first_sentence"]] if b.get("first_sentence") else []))]


def _nest_depth_blocks(m):
    """[block id]: the sketch blocks, in note order, with a list item nested deeper than one level (shown flat). Only a listing."""
    return [b["block"] for n in m.notes for b in n["blocks"] if b["kind"] == "sketch" and (b.get("_sk") or {}).get("_depth")]


def recognition_counts(forms):
    """(K known, V variant, N not recognised, O open in literature, M not written, G) over the list of the forms of the groups with a
    claim: a form is one of FORMS, or None for a group with no recognition (counted as not written). The function itself counts any
    other value nowhere, so K + V + N + O + M would fall short of G; the sum assertion is a guard on this function (a case plants a
    miscount through it). From the outline, `_count_lines` maps a form that is none of FORMS to None, so a bad form is counted as not
    written and is the checker's to refuse (BAD-VALUE), not this assertion's. G is the length of the list."""
    c = [sum(1 for x in forms if x == f) for f in FORMS]
    return c[0], c[1], c[2], c[3], sum(1 for x in forms if x is None), len(forms)


def sketch_counts(rows):
    """(S, P) over the level-1 steps given as (proof_read, has a sketch): P the steps whose proof is read, S those of them that carry a
    sketch. A step whose proof is not read does not count, sketch or no sketch."""
    read = [r for r in rows if r[0] is True]
    return sum(1 for r in read if r[1]), len(read)


def _count_lines(m):
    """([(code, where, message)], the two run lines): the recognition counts over ALL groups with a claim, at every depth, and the
    sketches over the level-1 steps, each asserted (K + V + N + O + M = G; S <= P)."""
    errors = []
    forms = []
    for gid in sorted(m.groups):
        sm = m.summary[gid]
        if sm["claim"] is not None:
            rec = sm["recognition"]
            forms.append(rec.get("form") if isinstance(rec, dict) and rec.get("form") in FORMS else None)
    k, v, n, o, nw, g = recognition_counts(forms)
    if k + v + n + o + nw != g:
        errors.append(("SUM-RECOGNITION", "groups", f"{k} known + {v} variant + {n} not recognised + {o} open in literature + "
                                                     f"{nw} not written is {k + v + n + o + nw}, not {g} groups with a claim"))
    s, p = sketch_counts([(m.summary[i]["proof_read"], bool(m.files[i]["sketches"])) for i in m.steps])
    if s > p:
        errors.append(("SUM-SKETCH", "steps", f"{s} steps with a sketch, but only {p} steps have a proof read"))
    return errors, [f"recognition: {k} known, {v} variant, {n} not recognised, {o} open in literature, {nw} not written, of {g} "
                    "groups with a claim", f"sketches: {s} of {p} steps with a proof read"]


def _link_listing(m):
    """(how many links are shown as text, [(block id, target)] of those whose target is not a note of the build): the links of the text
    of the argument, interpretation and sketch blocks that reach a card (once per block), a target being a note when its part before
    any `#fragment` is the file name of a note of the build."""
    shown = {b["block"] for fl in m.files.values() for b in fl["blocks"]}
    names = {n["name"] for n in m.notes}
    count, outside = 0, []
    for n in m.notes:
        for b in n["blocks"]:
            if b["block"] in shown:
                for text in _block_texts(b):
                    for target in _link_targets(text):
                        count += 1
                        if target.split("#", 1)[0] not in names:
                            outside.append((b["block"], target))
    return count, outside


def _nest(m, gid):
    out = dict(m.summary[gid])
    out["children"] = [_nest(m, c) for c in m.children.get(gid, [])]
    return out


# ---- the page

CSS = ("body { max-width: 50rem; margin: 1rem auto; padding: 0 1rem; font-family: serif; line-height: 1.45; }\n"
       ".card { border: 2px solid; padding: 0.5rem 0.75rem; margin: 0.75rem 0; }\n"
       ".unread { border-style: dashed; }\n"
       ".frame { font-style: italic; }\n"
       "ul.chain, ul.children { list-style: none; padding-left: 0; }\n"
       "aside { border-left: 4px double; padding-left: 0.5rem; }\n"
       "code { overflow-wrap: anywhere; }")


def _e(x):
    return html.escape(str(x), quote=True)


def _rich(text, links=False):
    """Escaped text in which a span between single backticks on one line is a <code> element (its content escaped too). The span is
    notes_meta's _BACKTICK_SPAN, the one definition the checker uses too. Nothing else is markup: an unpaired backtick, an empty
    pair, doubled backticks and a pair over a line break (LF or CR) stay literal. With `links` (the text of a block and its first
    sentence, F30) a markdown link `[text](target)` outside a span is shown as its text, escaped, and no anchor is made: neither bracket,
    parenthesis nor target is shown; an image `![a](b)`, a bare bracket pair, a link with no closing parenthesis, one with a space
    in its target and one with no text stay as written. `links` also turns on the bold rule (F35), since both belong to the Markdown of a
    note's block text: a pair of double asterisks on one line around text is <strong>, its content through the span rule (the links
    are taken out first, so a link text may be bold); see `_bold_pieces` for what stays literal."""
    masked, spans, tok = _masked(text)
    pieces = [(False, masked)]
    if links:
        pieces = _bold_pieces(_delink(masked, tok)[0])
    out = []
    for bold, piece in pieces:
        pos = 0
        out.append("<strong>" if bold else "")
        for mt in re.finditer(re.escape(tok) + r"(\d+)" + re.escape(tok), piece):
            out.append(_e(piece[pos:mt.start()]))
            out.append("<code>" + _e(spans[int(mt.group(1))]) + "</code>")
            pos = mt.end()
        out.append(_e(piece[pos:]))
        out.append("</strong>" if bold else "")
    return "".join(out)


def _fillh(template, rich=(), **kw):
    """The HTML of a template of the strings file with each known {name} replaced in one pass by its value, escaped (through the span
    rule for the names in `rich`); a name that is not given stays as written. The template's own text is escaped."""
    out, pos = [], 0
    for mt in _PLACEHOLDER.finditer(template):
        out.append(_e(template[pos:mt.start()]))
        name = mt.group(1)
        out.append((_rich(str(kw[name])) if name in rich else _e(kw[name])) if name in kw else _e(mt.group(0)))
        pos = mt.end()
    out.append(_e(template[pos:]))
    return "".join(out)


def _render_page(m, s, facts, dirty):
    lab, kinds = s["labels"], s["labels"]["kinds"]
    files = m.files
    out = ["<!DOCTYPE html>", '<html lang="en">', "<head>", '<meta charset="utf-8">', f"<title>{_e(s['page_title'])}</title>",
           "<style>", CSS, "</style>", "</head>", "<body>", "<header>", f"<h1>{_e(s['page_title'])}</h1>"]
    out += [f"<p>{_e(x)}</p>" for x in s["first_screen"]]
    if dirty:
        out.append(f'<p class="dirty">{_e(s["dirty_note"])}</p>')
    out += ['<ul class="facts">',
            f"<li>{_e(_fill(s['steps_statement_line'], n=facts['statement_read'], m=facts['steps']))}</li>",
            f"<li>{_e(_fill(s['steps_proof_line'], n=facts['proof_read'], m=facts['proof_applicable']) if facts['proof_applicable'] else s['steps_proof_not_applicable_line'])}</li>",
            f"<li>{_e(_fill(s['steps_open_items_line'], n=m.totals['open_items']))}</li>", "</ul>",
            f'<p class="mapped">{_e(s["mapped_line"])}</p>']
    if m.header_notes:
        out += ['<section class="whole">', f"<h2>{_e(lab['level0_notes'])}</h2>", "<ul>"]
        out += [f'<li><a href="{_e(n["link"])}">{_rich(n["list_title"])}</a></li>' for n in m.header_notes]
        out += ["</ul>", "</section>"]
    out += ["</header>", "<main>", f"<h2>{_e(lab['chain'])}</h2>", '<ul class="chain">']

    def where(b):
        """(the base name of the block's file, the range of its lines) as the Evidence section shows them (F29, moved there by F37):
        `not given` for the file with no file, and for the lines with no lines or no file for them to name."""
        fname = (b["file"].replace("\\", "/").rsplit("/", 1)[-1] if b.get("file") else "") or lab["lines_missing"]
        lines = f"{b['lines'][0]}-{b['lines'][1]}" if b.get("lines") and b.get("file") else lab["lines_missing"]
        return fname, lines

    def frames(b, rows):
        """The frame of a block (F37: it names nobody, no date, no file and no lines; the second readers, the file and the lines are
        in the Evidence section). A block anchored only on roots whose kind is not a theorem or a lemma is framed by
        argument_frame_no_proof (`rows` are the root rows of the card)."""
        kind_of = {(r["module"], r["name"]): r["kind"] for r in rows}
        proofless = bool(b.get("roots")) and not any(kind_of.get((x["module"], x["name"])) in PROOF_KINDS for x in b["roots"])
        return f'<span class="frame">{_e(s["argument_frame_no_proof" if proofless else "argument_frame"])}</span>'

    def recognition(sm, role):
        """The recognition block of a card with a claim: the form line, the difference, the citations, the established line (a named
        statement only) and the label line; or the not-written line. {source_date} of an open form is the newest source_date among
        the citations that say open, compared as the strings as written."""
        rec = sm["recognition"]
        if rec is None:
            return ['<div class="recognition">', f'<p class="recognition-form">{_e(s["recognition_not_written_line"])}</p>', "</div>"]
        cits = rec.get("citations") or []
        if rec["form"] == "open_in_literature":
            line = _fillh(s[f"recognition_{role}_open_line"], ("result",), result=rec["result"],
                          source_date=max(c["source_date"] for c in cits if c.get("says_open") is True))
        else:
            line = _fillh(s[f"recognition_{role}_{rec['form']}_line"], ("result",), result=rec.get("result", ""))
        o = ['<div class="recognition">', f'<p class="recognition-form">{line}</p>']
        if rec.get("difference"):
            o.append(f'<p class="recognition-difference">{_rich(rec["difference"])}</p>')
        if rec["form"] == "not_recognised" and rec.get("note"):   # F31: the note of a reading that found nothing (span rule only)
            o.append(f'<p class="recognition-note">{_rich(rec["note"])}</p>')
        if cits:
            o.append('<ul class="recognition-citations">')
            for c in cits:
                key = "recognition_citation_open_line" if rec["form"] == "open_in_literature" and c.get("says_open") is True \
                    else "recognition_citation_dated_line"
                text = _fillh(s[key], ("source", "where"), source=c["source"], where=c["where"], source_date=c.get("source_date", ""))
                if c.get("url"):
                    text = f'<a class="citation" href="{_e(c["url"])}">{text}</a>'
                o.append(f"<li>{text}</li>")
            o.append("</ul>")
        est = rec.get("established")
        if role == "named_statement" and est is not None:
            line = (_e(s["established_not_traced_line"]) if est == "not_traced" else
                    _fillh(s["established_by_line"], name=f"{est['by']['module']}.{est['by']['name']}"))
            o.append(f'<p class="recognition-established">{line}</p>')
        o.append(f'<p class="recognition-label">{_e(s["recognition_label_line"])}</p>')   # F37: one standing sentence, no name and no date
        o.append("</div>")
        return o

    def sketch(sk):
        """The sketch of a root: its frame (the basis string filled first, then the frame), its paragraphs and lists, the places
        Lean finishes by automation when there are any, and the note that it is a sketch."""
        basis = s["sketch_basis_compiled"] if sk["basis"] == "compiled" else s["sketch_basis_source"]   # F37: the build string is in Evidence
        frame = _fill(s["sketch_frame"], basis=basis)
        o = ['<div class="sketch">', f'<p class="frame sketch-frame">{_e(frame)}</p>']
        item = lambda x: (f"<li>{_rich(x, links=True)}</li>" if isinstance(x, str) else
                          f"<li>{_rich(x['text'], links=True)}<ul>" + "".join(f"<li>{_rich(y, links=True)}</li>" for y in x["items"]) + "</ul></li>")
        for blk in sk["blocks"]:
            if blk["type"] == "paragraph":
                o.append(f'<p>{_rich(blk["text"], links=True)}</p>')
            else:
                tag = "ol" if blk["ordered"] else "ul"
                o.append(f"<{tag}>" + "".join(item(x) for x in blk["items"]) + f"</{tag}>")
        if sk["unexpanded"]:
            o.append(f'<p class="unexpanded-heading">{_e(s["unexpanded_heading"])}</p><ul class="unexpanded">'
                     + "".join(f"<li>{_rich(x)}</li>" for x in sk["unexpanded"]) + "</ul>")
        o.append(f'<p class="sketch-note">{_e(s["sketch_note"])}</p>')
        o.append("</div>")
        return o

    def title_of(gid):
        sm = m.summary[gid]
        return _rich(sm["claim"]["text"]) if sm["claim"] else f"<code>{_e(sm['lean_name'])}</code>"

    def card(gid):
        sm, fl = m.summary[gid], files[gid]
        o = [f'<article class="card{" unread" if sm["unread"] else ""}" id="{_e(gid)}">']
        if sm["claim"]:
            o.append(f'<h3 class="claim">{_rich(sm["claim"]["text"])}</h3>')
            if sm["claim"]["conditions"]:
                o.append('<ul class="conditions">' + "".join(f"<li>{_rich(c)}</li>" for c in sm["claim"]["conditions"]) + "</ul>")
        else:
            o.append(f'<h3 class="claim unread-claim"><code>{_e(sm["lean_name"])}</code> '
                     f'<span class="label">{_e(sm["claim_label"])}</span></h3>')
        role = sm["root_role"] or ("result" if sm["root_kind"] in PROOF_KINDS else "named_statement") if sm["claim"] else None   # no role: the class of the kind
        if role == "named_statement":   # F36: what kind of step this is, directly after the claim and its conditions
            o.append(f'<p class="named-statement-use">{_e(s["named_statement_use_line"])}</p>')
        if sm["premises"]:   # a step with a null claim rests on premises as well
            links = ", ".join(f'<a href="#{_e(urllib.parse.quote(p, safe=""))}">{title_of(p)}</a>' for p in sm["premises"])
            o.append(f'<p class="premises">{_e(lab["premises"])} {links}</p>')
        if sm["claim"]:   # the recognition of the statement: after the premises line, before the two status lines (F24)
            o += recognition(sm, role)
        c, by = sm["counts"], sm["statement_by"]
        # the line of a card with no proof: the builder does not know what a declaration of an unknown kind is
        none_line = (s["proof_none_other_line"] if any(r["kind"] not in KNOWN_KINDS for r in fl["roots"])
                     else s["proof_not_applicable_line"])
        args = [b for b in fl["blocks"] if b["kind"] == "argument"]   # blocks are in note id, then block number, order
        if c["roots"] > 1:   # several roots (a null claim): counts with their denominators
            st = _fill(s["statement_count_line"], n=c["roots_statement_read"], m=c["roots"])
            pf = (_fill(s["proof_count_line"], n=c["roots_proof_read"], m=c["roots_proof_applicable"])
                  if c["roots_proof_applicable"] else none_line)   # counted over the roots that HAVE a proof
        else:
            if sm["statement_read"]:
                st = s["statement_read_line"]
            elif by and by["source"] == "census":
                st = s["statement_census_line"]
            else:
                st = s["statement_not_read_line"]
            pf = (none_line if sm["proof_read"] is None
                  else s["proof_read_line"] if sm["proof_read"]
                  else s["proof_not_read_line"])
        o.append(f'<p class="status statement">{_e(st)}</p>')
        o.append(f'<p class="status proof">{_e(pf)}</p>')
        if c["open_items"] > 0:   # a zero is not said on a card (the first screen always says it)
            o.append(f'<p class="open-items">{_e(_fill(s["open_items_line"], n=c["open_items"]))}</p>')
        if sm["roots_only"]:
            o.append(f'<p class="roots-only">{_e(s["roots_only_note"])}</p>')
        if args:
            b = args[0]
            link = next(n["link"] for n in sm["notes"] if n["note"] == b["note"])
            sent = f" {_rich(b['first_sentence'], links=True)}" if b.get("first_sentence") else ""
            o.append(f'<p class="argument">{frames(b, fl["roots"])}{sent} <a href="{_e(link)}">{_e(lab["read_more"])}</a></p>')
        for sk in fl["sketches"]:
            o += sketch(sk)
        if not fl["sketches"] and sm["proof_read"] is True:   # a card whose proof is read and that has no sketch says so
            o.append(f'<p class="sketch-missing">{_e(s["sketch_missing_line"])}</p>')
        corr = [b for b in fl["blocks"] if b["kind"] == "correction"]
        if corr:
            o.append('<ul class="corrections">')
            for b in corr:
                n = next(n for n in sm["notes"] if n["note"] == b["note"])
                # F37: the kind and the title (what was wrong) stay; the reader and the date are in the Evidence block list
                o.append(f'<li><span class="kind">{_e(kinds["correction"])}</span> <a href="{_e(n["link"])}">{_rich(n["list_title"])}</a></li>')
            o.append("</ul>")
        if sm["notes"]:
            o.append(f'<p class="notes">{_e(lab["notes"])}</p><ul class="notes">'
                     + "".join(f'<li><a href="{_e(n["link"])}">{_rich(n["list_title"])}</a></li>' for n in sm["notes"]) + "</ul>")
        o.append('<ul class="reactions">')
        for r in s["reactions"]:
            href = _fill(r["href"], card=urllib.parse.quote(gid, safe=""))
            o.append(f'<li><a class="reaction" href="{_e(href)}">{_e(r["label"])}</a></li>')
        o.append("</ul>")
        o += ['<details class="evidence">', f"<summary>{_e(s['evidence_label'])}</summary>"]
        for r in fl["roots"]:
            o.append('<div class="root">')
            o.append(f'<dl><dt>{_e(s["evidence_module_label"])}</dt><dd><code>{_e(r["module"])}</code></dd>'
                     f'<dt>{_e(s["evidence_name_label"])}</dt><dd><code>{_e(r["name"])}</code></dd>'
                     f'<dt>{_e(s["evidence_kind_label"])}</dt><dd><span class="kind">{_e(r["kind"])}</span></dd>'
                     f'<dt>{_e(lab["file"])}</dt><dd><code>{_e(r["file"])}</code></dd>'
                     f'<dt>{_e(lab["lines"])}</dt><dd>{r["lines"][0]}-{r["lines"][1]}</dd>'
                     + (f'<dt>{_e(lab["sha256"])}</dt><dd><code>{r["sha256"]}</code></dd>' if r["sha256"] else "") + "</dl>")
            if r["shared_with"]:
                o.append(f'<p class="shared">{_e(_fill(s["shared_note"], groups=", ".join(r["shared_with"])))}</p>')
            o.append("</div>")
        # F37: who read what, and when, the sentences that left the card; in a fixed order: the statement, the proof, the recognition,
        # each citation, the established line (the second readers, the file and the lines and the build of a sketch follow their block)
        reads = []
        if c["roots"] <= 1:   # a card with counts (several roots) names nobody, as before
            if sm["statement_read"] and by:
                reads.append(("statement", _e(_fill(s["evidence_statement_read_line"], reader=by["reader"], date=by["date"]))))
            elif by and by["source"] == "census":
                reads.append(("statement", _e(_fill(s["evidence_statement_census_line"], reader=by["reader"], date=by["date"]))))
            if sm["proof_read"]:
                reads.append(("proof", _e(_fill(s["evidence_proof_read_line"], reader=args[0]["reader"], date=args[0]["date"]))))
        rec = sm["recognition"]
        if sm["claim"] and rec is not None:
            reads.append(("recognition", _e(_fill(s["evidence_recognition_line"], reader=rec["reader"], date=rec["date"]))))
            for ct in rec.get("citations") or []:
                reads.append(("citation", _fillh(s["evidence_citation_line"], ("source",), source=ct["source"], opened_by=ct["opened_by"],
                                                 opened_on=ct["opened_on"])))
            est = rec.get("established")
            if role == "named_statement" and isinstance(est, dict):
                reads.append(("established", _fillh(s["evidence_established_line"], name=f"{est['by']['module']}.{est['by']['name']}",
                                                    reader=est["reader"], date=est["date"])))
        if reads:
            o.append('<ul class="provenance">' + "".join(f'<li class="{k}">{v}</li>' for k, v in reads) + "</ul>")
        if fl["blocks"]:
            o += [f'<p class="label">{_e(lab["blocks"])}</p>', '<ul class="blocks">']
            for b in fl["blocks"]:
                n = next(n for n in sm["notes"] if n["note"] == b["note"])
                who = " ".join(_e(x) for x in (b.get("reader"), b.get("date")) if x)
                o.append(f'<li><a href="{_e(n["link"])}"><code>{_e(b["note"])}</code></a> <code>{_e(b["block"])}</code> '
                         f'<span class="kind">{_e(kinds[b["kind"]])}</span> {who}')
                if b["kind"] == "argument" and b.get("text"):
                    o.append(f'<p class="argument">{frames(b, fl["roots"])} {_rich(b["text"], links=True)}</p>')
                if b["kind"] in ("argument", "sketch"):   # F37: the file and the lines left the frame of the block
                    fname, lines = where(b)
                    o.append(f'<dl class="block-source"><dt>{_e(lab["file"])}</dt><dd><code>{_e(fname)}</code></dd>'
                             f'<dt>{_e(lab["lines"])}</dt><dd>{_e(lines)}</dd></dl>')
                for sr in b.get("second_readers", []):
                    o.append(f'<p class="second-reader">{_e(_fill(s["evidence_second_reader_line"], reader=sr["reader"], date=sr["date"]))}</p>')
                if b["kind"] == "sketch":
                    sk = next(x for x in fl["sketches"] if x["block"] == b["block"])
                    if sk["basis"] == "compiled":
                        o.append(f'<p class="sketch-build">{_e(_fill(s["evidence_sketch_build_line"], build=sk["build"]))}</p>')
                if b["kind"] == "interpretation" and b.get("text"):
                    fr = s["interpretation_frame"]
                    o.append(f'<aside><p class="interpretation"><span class="frame">{_e(fr)}</span> {_rich(b["text"], links=True)}</p></aside>')
                o.append("</li>")
            o.append("</ul>")
        if fl["open_items"]:
            o += [f'<p class="label">{_e(lab["open_items"])}</p>', '<ul class="open">']
            for it in fl["open_items"]:
                o.append(f'<li><code>{_e(it["note"])}</code> <code>{_e(it["block"])}</code> <code>{_e(it["needs"])}</code></li>')
            o.append("</ul>")
        o.append("</details>")
        kids = m.children.get(gid, [])
        if kids:
            o += ['<details class="children">', f"<summary>{_e(lab['go_deeper'])}</summary>", '<ul class="children">']
            for k in kids:
                o += ["<li>"] + card(k) + ["</li>"]
            o += ["</ul>", "</details>"]
        o.append("</article>")
        return o

    for gid in m.steps:
        out += ["<li>"] + card(gid) + ["</li>"]
    out += ["</ul>", "</main>", "</body>", "</html>"]
    return "\n".join(out) + "\n"


# ---- the build

def _json_strings(v, path=""):
    if isinstance(v, str):
        yield path, v
    elif isinstance(v, list):
        for i, x in enumerate(v):
            yield from _json_strings(x, f"{path}[{i}]")
    elif isinstance(v, dict):
        for k, x in v.items():
            yield from _json_strings(x, f"{path}.{k}" if path else k)


_URL_START = re.compile(r"\s*(?:https?:)?//", re.I)


def _origin(token, sj, level0, level1, groups):
    """Where a token that PAGE-STATIC found came from: the strings key (or group and field, or level file) that holds the
    offending token. For a link or source finding (`href=http`, `src=http`) that is a value that starts with an address, a
    reaction template only when no other value does (a reaction anchor may hold one); else the two files."""
    link = token in ("src=http", "href=http")
    needles = {"url(": ("url(",)}.get(token, (token,))

    def hit(v):
        return bool(_URL_START.match(v)) if link else any(n in v for n in needles)

    strings = list(_walk_strings(sj, ""))
    if link:   # the reaction templates are the legal holders of an address: look at the other values first
        strings.sort(key=lambda pv: bool(re.fullmatch(r"reactions\[\d+\]\.href", pv[0])))
    for path, v in strings:
        if hit(v):
            return f"strings key {path}"
    for gid in sorted(groups):
        for path, v in _json_strings({k: x for k, x in groups[gid].items() if k != "commits"}):
            if hit(v):
                return f"group {gid} field {path}"
    for name, obj in (("level0", level0), ("level1", level1)):
        for path, v in _json_strings({k: x for k, x in obj.items() if k != "commits"}):
            if hit(v):
                return f"{name} field {path}"
    return "index.html or data.js"


def _refuse(lines, code=1):
    for code_, where, msg in lines:
        print(f"BUILD-ERROR {code_} {where} {msg}")
    print("REFUSED: nothing written", file=sys.stderr)
    return code


def _assemble(m, s, commits):
    """(errors, the facts check line, level0, level1, the group files, the facts over the steps)."""
    errors = []
    steps = [m.summary[i] for i in m.steps]
    def check(items, where, noun):
        """The two sums over `items` (steps or the root rows of a group): read + not read = total for the statement, read + not
        read + not applicable = total for the proof."""
        a, b = fact_pairs(_fact_flags(items, "statement_read"))
        if a + b != len(items):
            errors.append(("SUM-STATEMENT", where, f"read {a} + not read {b} = {a + b}, but there are {len(items)} {noun}"))
        c, d, e = fact_triples(_fact_flags(items, "proof_read"))
        if c + d + e != len(items):
            errors.append(("SUM-PROOF", where, f"read {c} + not read {d} + not applicable {e} = {c + d + e}, but there are "
                                               f"{len(items)} {noun}"))
        return (a, b), (c, d, e)

    (sa, sb), (pa, pb, pn) = check(steps, "steps:", "steps")
    for gid in sorted(m.groups):
        check(m.files[gid]["roots"], f"group {gid} roots:", "roots")
    line = (f"statements read {sa} + not read {sb} = {sa + sb} steps; "
            f"proofs read {pa} + not read {pb} + not applicable {pn} = {pa + pb + pn} steps")
    facts = {"steps": len(steps), "statement_read": sa, "statement_not_read": sb, "proof_read": pa, "proof_not_read": pb,
             "proof_not_applicable": pn, "proof_applicable": pa + pb}
    level0 = {"commits": commits, "header_notes": m.header_notes, "level": 0, "facts": facts, "steps": steps,
              "totals": m.totals}
    level1 = {"commits": commits, "level": 1, "steps": [_nest(m, i) for i in m.steps]}
    groups = {gid: dict(m.files[gid], commits=commits) for gid in m.groups}
    return errors, line, level0, level1, groups, facts


def _output_files(level0, level1, groups, page, commits, m, release_id, archive):
    """Every file of the build as bytes, the manifest last (it holds the hash of all the others)."""
    files = {"level0.json": level0, "level1.json": level1}
    files.update({f"group/{gid}.json": g for gid, g in groups.items()})
    data = "window.RH_DATA = " + _js_safe(_dump({"groups": groups, "level0": level0, "level1": level1})) + ";\n"
    out = {k: (_dump(v) + "\n").encode("utf-8") for k, v in files.items()}
    out["data.js"] = data.encode("utf-8")
    out["index.html"] = page.encode("utf-8")
    manifest = {"commits": commits, "counts": {"blocks": m.totals["blocks"], "groups": m.totals["groups"],
                                               "notes": m.totals["notes"]},
                "files": {k: _sha(v) for k, v in sorted(out.items())}, "release_archive_sha": archive,
                "release_id": release_id}
    out["manifest.json"] = (_dump(manifest) + "\n").encode("utf-8")
    return out


def _write_files(dirpath, files):
    for rel, data in files.items():
        p = os.path.join(dirpath, *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as fh:
            fh.write(data)


def _publish(out, files):
    """Write the build into a temporary sibling of `out` and rename it into place. With an existing `out` (empty, or --force)
    the files that are not a build file are copied into the new tree first and the old tree is set aside, so a failure at any
    step leaves `out` as it was (absent, or the old build) and no temporary directory behind."""
    out = os.path.abspath(out)
    parent, base = os.path.split(out)
    tmp = tempfile.mkdtemp(prefix=base + ".tmp-", dir=parent)
    um = os.umask(0)
    os.umask(um)
    os.chmod(tmp, 0o777 & ~um)
    backup = None
    try:
        _write_files(tmp, files)
        if os.path.isdir(out):
            for name in os.listdir(out):
                if name in _OUT_NAMES or name == "group":
                    continue
                src, dst = os.path.join(out, name), os.path.join(tmp, name)
                if os.path.isdir(src) and not os.path.islink(src):
                    shutil.copytree(src, dst, symlinks=True)
                else:
                    shutil.copy2(src, dst, follow_symlinks=False)
            backup = tmp + ".old"
            os.rename(out, backup)
        os.rename(tmp, out)
        tmp = None
    except BaseException:
        if backup is not None and not os.path.exists(out):
            os.rename(backup, out)
            backup = None
        raise
    finally:
        if tmp is not None:
            shutil.rmtree(tmp, ignore_errors=True)
        if backup is not None:
            shutil.rmtree(backup, ignore_errors=True)


def _run(notes_dir, outline, decls, strings, out, source_check, archive_sha, notes_commit, repo, force, tools_state):
    if source_check is not None and not os.path.isdir(source_check):
        raise _Unreadable(f"SRC_ROOT is not a directory: {source_check}")
    if os.path.exists(out) and not os.path.isdir(out):
        raise _Unreadable(f"OUT_DIR is not a directory: {out}")
    sj = _read_json(strings, "strings file")
    if os.path.isdir(out) and os.listdir(out) and not force:
        return _refuse([("OUT-NOT-EMPTY", "OUT_DIR", "already holds files; a fresh build would mix two builds; "
                         "use --force to remove the files of an earlier build first")])
    probs = _strings_problems(sj)
    if probs:
        return _refuse(probs)
    if tools_state is None:
        tools_state = _tools_state()
    n_commit, n_dirty = ("unknown", False)
    if notes_commit is not None:   # asked of git before anything is printed: an unreadable --repo is exit 2 with no stdout
        n_commit, n_dirty = _notes_state(repo, notes_commit, [notes_dir, outline, strings, decls])
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        rc = nm.run(notes_dir, outline, decls, strings=strings)
    if rc == 2:
        print(e.getvalue().strip(), file=sys.stderr)
        return 2
    if rc != 0:
        print(o.getvalue().rstrip("\n"))
        if rc == 3:
            return 3
        print("REFUSED: notes_meta found errors; nothing written", file=sys.stderr)
        return rc
    print(next(ln for ln in o.getvalue().splitlines() if ln.startswith("outline: ")))
    print(next(ln for ln in o.getvalue().splitlines() if ln.startswith("claim basis: ")))
    odata = _read_json(outline, "outline")
    bases = [g["claim"].get("basis") for g in odata["groups"] if isinstance(g.get("claim"), dict)]
    n_read, n_census = bases.count("read"), bases.count("census")
    n_without = len(bases) - n_read - n_census
    print(f"claim basis: {n_read} read, {n_census} census, {n_without} without" + (" (treated as read)" if n_without else ""))
    errors = []
    ids = [g["id"] for g in odata["groups"]]
    low = {}
    for i in ids:
        low.setdefault(i.lower(), set()).add(i)
        if not SAFE_ID.fullmatch(i) or len(i) > 100:
            errors.append(("GROUP-ID-UNSAFE", i, "is not usable as a file name (letters, digits, `.`, `_`, `-`; not first `.`; "
                                                 "at most 100 characters)"))
    for k, v in sorted(low.items()):
        if len(v) > 1:
            errors.append(("GROUP-ID-UNSAFE", ", ".join(sorted(v)), "differ only in case, so they could share a file"))
    if errors:
        return _refuse(errors)
    dirty = n_dirty or tools_state[1]
    commits = {"notes": n_commit, "release": odata["release"], "tools": tools_state[0]}
    if dirty:
        commits = {k: "dirty" for k in commits}
    m = _model(notes_dir, odata, _decl_rows(decls), sj, source_check, errors)
    word_notes = _word_notes(m, sj)
    for where, word in word_notes:
        print(f"WORD-NOTE {where} {word}")
    for gid, name, kind in m.kind_notes:   # a kind outside the eight: no proof (null), and listed, never refused
        print(f"KIND-NOTE {gid} {name} kind {kind!r}")
    for bid in _formula_raw(m):   # a formula mark outside a code span: no conversion yet (F26), and listed, never refused
        print(f"FORMULA-RAW {bid}")
    for bid in _bold_unpaired_blocks(m):   # a `**` that is no pair stays literal on the page, and is listed, never refused (F35)
        print(f"BOLD-UNPAIRED {bid}")
    for bid in _nest_depth_blocks(m):   # a sub-item nested deeper than one level is shown flat, and is listed, never refused (F35)
        print(f"NEST-DEPTH {bid}")
    n_links, outside = _link_listing(m)   # a link in block text is shown as its text; a target that is no note of the build is listed
    print(f"links in block text: {n_links} shown as text")
    for bid, target in outside:
        print(f"LINK-OUTSIDE {bid} {target}".rstrip())
    for n in m.notes:
        for b in n["blocks"]:
            for what in ("reader", "date"):
                if b["kind"] in READER_KINDS and not (isinstance(b.get(what), str) and b[what]):
                    errors.append(("BLOCK-NO-READER" if what == "reader" else "BLOCK-NO-DATE", b["block"],
                                   f"{b['kind']} block has no {what}"))
    e2, check_line, level0, level1, groups, facts = _assemble(m, sj, commits)
    e3, count_lines = _count_lines(m)
    errors += e2 + e3
    if errors:
        return _refuse(errors)
    page = _render_page(m, sj, facts, dirty)
    files = _output_files(level0, level1, groups, page, commits, m, odata["release"], archive_sha)
    for pb in static_problems(page, files["data.js"].decode("utf-8")):
        errors.append(("PAGE-STATIC", pb, "found in " + _origin(pb, sj, level0, level1, groups)))
    for pb in element_problems(page):
        errors.append(("PAGE-STATIC", pb, "found in index.html"))
    for pb in link_problems(page):
        errors.append(("PAGE-LINK", pb, "does not resolve on the page"))
    for pb in number_problems(page, number_pool([level0, level1] + list(groups.values())), json.dumps(sj, ensure_ascii=False)):
        errors.append(("PAGE-NUMBER", pb, "is on the page and in no JSON file or strings file"))
    if errors:
        return _refuse(errors)
    print("facts check: " + check_line)
    for ln in count_lines:
        print(ln)
    if source_check is not None:
        if not sg.walk_lean(source_check):
            print("CHECKED NOTHING: no .lean file under SRC_ROOT")
            return 3
        copied = m.copied + [(n["id"], "field list_title", _unspan(n["title"]).split("\n")) for n in m.notes]
        try:
            leaks, st = leak_check(files, source_check, copied)
        except ValueError as ex:
            return _refuse([("SOURCE-UNREADABLE", "SRC_ROOT", str(ex))])
        print(f"source check: {st['release_files']} release files, {st['release_lines']} release lines, "
              f"{st['output_files']} output files, {st['output_lines']} output lines, {len(leaks)} leaked")
        print(f"source check (copied note text): {st['copied_lines']} copied source lines, {len(st['copied_leaks'])} leaked; "
              "no output line equals a release line and no line of copied note text equals one; "
              "a release line quoted inside a longer sentence is not detected")
        found = [("SOURCE-LEAK", f"note {n} {w}", "holds a line of the release") for n, w in st["copied_leaks"]]
        found += [("SOURCE-LEAK", f, "holds a line of the release") for f in leaks]
        if found:
            return _refuse(found)
    try:
        _publish(out, files)
    except OSError as ex:
        raise _Unreadable(f"cannot write the site: {ex.strerror or ex}")
    print(f"built: {m.totals['groups']} groups, {m.totals['notes']} notes, {m.totals['blocks']} blocks, {len(files)} files, "
          f"{len(word_notes)} word notes")
    return 0


def run(notes_dir, outline, decls, strings, out, source_check=None, archive_sha=None, notes_commit=None, repo=None,
        force=False, tools_state=None):
    """Build the site into `out` and return the exit code 0, 1, 2 or 3 (see the contract). `tools_state` is (commit, dirty)
    for the folder of this file; None asks git."""
    archive_sha = archive_sha.lower() if archive_sha else archive_sha
    buf = io.StringIO()   # nothing reaches stdout on exit 2
    try:
        with contextlib.redirect_stdout(buf):
            rc = _run(notes_dir, outline, decls, strings, out, source_check, archive_sha, notes_commit, repo, force, tools_state)
    except _Unreadable as ex:
        print("build_site: " + str(ex), file=sys.stderr)
        return 2
    except RecursionError:
        print("build_site: outline too deep to write", file=sys.stderr)
        return 2
    except OSError as ex:
        print(f"build_site: cannot read an input: {ex.strerror or ex}", file=sys.stderr)
        return 2
    sys.stdout.write(buf.getvalue())
    return rc


# ---------------------------------------------------------------- self-test: fixtures, built from literals

def _b(**kw):
    return rh.format_comment("rh-block", kw)


def _h(**kw):
    return rh.format_comment("rh-note", dict({"authors": ["Author One"], "readers": ["Reader One"], "release": "rel-1",
                                              "level": 2}, **kw))


def _d(module, name):
    return {"module": module, "name": name}


FOO, BAR, BAZ, QUX, QUUX, CORGE = (_d("A.B", "foo"), _d("A.B", "bar"), _d("A.C", "baz"), _d("A.E", "qux"),
                                   _d("A.F", "quux"), _d("A.G", "corge"))
DECLS = ("# decls fixture\n"
         "module\tname\tkind\tfirst_line\tlast_line\tbasis\n"
         "A.B\tfoo\ttheorem\t10\t20\ttext-extent\n"
         "A.B\tbar\ttheorem\t30\t40\ttext-extent\n"
         "A.C\tbaz\tdef\t5\t9\ttext-extent\n"
         "A.E\tqux\ttheorem\t1\t4\ttext-extent\n"
         "A.F\tquux\ttheorem\t1\t3\ttext-extent\n"
         "A.G\tcorge\ttheorem\t1\t2\ttext-extent\n")


def _decls_kinds(kinds):
    """DECLS with the kind column of the named declarations changed (name -> kind)."""
    out = []
    for ln in DECLS.splitlines(True):
        c = ln.split("\t")
        if len(c) == 6 and c[1] in kinds:
            c[2] = kinds[c[1]]
        out.append("\t".join(c))
    return "".join(out)


FILES = "\n## Files this note was written from\n\n| File | SHA-256 |\n|---|---|\n| `A/B.lean` | `x` |\n"
ARG_TEXT = "First argument sentence. Second argument sentence."
LEAK = "theorem leak_example_long_name : 1 + 1 = 2 := rfl"
SRC40 = "".join(f"line {i}\n" for i in range(1, 41))
SRC40_SHA = "abf1f49fd0950dcb863dd5555604f8fb05035e5c03393da0ead0616d32bd6578"
TOOLS_OK = ("tools0", False)
HOST = '</script><img src=x onerror=alert(1)>"\'&`<b>%41\u2028'
HOST_S = HOST.replace("%41", "")   # the strings file may not hold a percent sign (outside its hrefs)
ESC = '&lt;/script&gt;&lt;img src=x onerror=alert(1)&gt;&quot;&#x27;&amp;`&lt;b&gt;%41\u2028'
ESC_S = ESC.replace("%41", "")


def _n01(arg_text=ARG_TEXT, drop_reader=False, host=None, interp_text="We think this is the key step."):
    """Note one; with `host` every title, reader and date the page shows is that string."""
    rd = {} if drop_reader else {"reader": host or "Reader One"}
    d1, d2, d3 = (host, host, host) if host else ("2026-11-23", "2026-11-24", "2026-11-22")
    r1, r2 = host or "Reader One", host or "Reader Two"
    return ("# Note one\n" + _h(id="01", group="g1", list_title="T " + host if host else "Note one") + "\n\n## Body\n\n"
            "Reading paragraph.\n"
            + _b(id="01.b01", kind="reading", decls=[FOO], file="A/B.lean", lines=[12, 14], date=d1, **rd) + "\n\n"
            + arg_text + "\n"
            + _b(id="01.b02", kind="argument", decls=[FOO], file="A/B.lean", lines=[15, 18], reader=r1,
                 date=d1, second_readers=[{"reader": r2, "date": d2}]) + "\n\n"
            + interp_text + "\n"
            + _b(id="01.b03", kind="interpretation", decls=[FOO], reader=r2, date=d2) + "\n\n"
            "- ListItemTextXYZ one\n- ListItemTextXYZ two\n"
            + _b(id="01.b04", kind="reading", decls=[BAR], item=2, reader=r1, date=d1) + "\n\n"
            "| a | b |\n|---|---|\n| TableCellTextXYZ | y |\n"
            + _b(id="01.b05", kind="not_read", decls=[QUUX], needs="hand_read", row=1) + "\n\n"
            "Correction paragraph.\n"
            + _b(id="01.b06", kind="correction", decls=[FOO], reader=r2, date=d3)
            + "\n" + FILES)


N02 = ("# Note two\n" + _h(id="02", group="g2", list_title="Note two") + "\n\n## Body\n\n"
       "Note two reading qux.\n" + _b(id="02.b01", kind="reading", decls=[QUX], reader="Reader Two", date="2026-11-23") + "\n\n"
       "Note two reading foo.\n" + _b(id="02.b02", kind="reading", decls=[FOO], reader="Reader Two", date="2026-11-23") + "\n")
N03 = "# Note three\n" + _h(id="03", group="g3", list_title="Note three") + "\n\n## Body\n\nNote three text.\n"
N00 = ("# Whole\n" + _h(id="00", group="root", list_title="Whole one", level=0) + "\n\n## Body\n\nWhole text.\n")


def _notes(**kw):
    return {"00-whole.md": N00, "01-one.md": _n01(**kw), "02-two.md": N02, "03-three.md": N03}


def _claim(text, date="2026-11-20", **kw):
    return dict({"text": text, "reader": "Reader One", "date": date, "defs_opened": [], "conventions_checked": ["a"]}, **kw)


def _g(gid, level, parent, order, roots, claim=None, premises=()):
    return {"id": gid, "level": level, "parent": parent, "order": order, "roots": roots, "claim": claim,
            "premises": list(premises)}


def _outline():
    return {"release": "rel-1", "groups": [
        _g("g3", 1, "root", 2, [CORGE], _claim("Claim four with é", basis="census"), ["g1", "g2"]),
        _g("g1a1x", 4, "g1a1", 1, [QUX]),
        _g("g1", 1, "root", 1, [FOO], _claim("Claim one", conditions=["Condition one holds."], basis="read"), ["g1a"]),
        _g("g2", 1, "root", 3, [QUUX, QUX]),
        _g("g1a", 2, "g1", 1, [BAR]),
        _g("g1a1", 3, "g1a", 1, [BAZ], _claim("Claim three & <more>"))]}


# the wording of the recognition, the established line and the sketch: a fixture copy of the wording file's values
WORDING = {
    "recognition_result_known_line": "Our reading: this is a well-known result in mathematics ({result}).",
    "recognition_result_variant_line": "Our reading: this is a version of a well-known result ({result}), changed to fit this proof.",
    "recognition_result_not_recognised_line": "Our reading: we do not recognise this as a known result. It may come from this proof, or it may be known and we have not found it.",
    "recognition_result_open_line": "Our reading: this result's statement is {result}, an open problem as of {source_date} according to the dated source below.",
    "recognition_named_statement_known_line": "Our reading: the statement named here is a well-known result in mathematics ({result}).",
    "recognition_named_statement_variant_line": "Our reading: the statement named here is a version of a well-known result ({result}), changed to fit this proof.",
    "recognition_named_statement_not_recognised_line": "Our reading: we do not recognise the statement named here as a known result. It may come from this proof, or it may be known and we have not found it.",
    "recognition_named_statement_open_line": "Our reading: the statement named here is {result}, an open problem as of {source_date} according to the dated source below.",
    "recognition_object_known_line": "Our reading: this is the standard definition of {result}.",
    "recognition_object_variant_line": "Our reading: this is a version of the standard definition of {result}, changed to fit this proof.",
    "recognition_object_not_recognised_line": "Our reading: we do not recognise this as a standard definition. It may be made for this proof, or it may be standard and we have not found it.",
    "recognition_not_written_line": "Our reading of this statement: not written yet.",
    "recognition_label_line": "No mathematician has checked our reading yet. If you think we have it wrong, or you know more, please tell us.",
    "recognition_citation_line": "{source}, {where}",
    "recognition_citation_dated_line": "{source}, {where}",
    "recognition_citation_open_line": "{source}, {where}, dated {source_date}",
    "named_statement_use_line": "This step gives a name to a statement. Steps that use the name take the statement as a hypothesis.",
    "established_by_line": "Where it is proved: the release proves this statement as {name}.",
    "established_not_traced_line": "Where it is proved: we have not yet traced where in the release this statement is proved.",
    "sketch_frame": "The proof in order, {basis}:",
    "sketch_basis_source": "from reading the Lean source",
    "sketch_basis_compiled": "from the goals Lean shows when this part of the release is compiled",
    "sketch_note": "A sketch for a reader, not a proof: it leaves steps out and may hide the hard part.",
    "sketch_missing_line": "Proof sketch: not written yet.",
    "unexpanded_heading": "Places where Lean finishes the proof by automation we have not opened up:",
}
NO_PROOF_FRAME = "What this definition contains:"

# F37: the wording of provenance off the reader's surface (the wording seat's file, the CARD and EVIDENCE sections, copied as written)
F37_CARD = {
    "statement_read_line": "We have read this statement.",
    "statement_not_read_line": "We have not read this statement yet.",
    "statement_census_line": "We have not read this statement: what it says here comes from a program's count of its parts.",
    "proof_read_line": "We have read this proof.",
    "proof_not_read_line": "We have not read this proof yet.",
    "argument_frame": "How this is proved:",
    "argument_frame_no_proof": "What this definition contains:",
    "interpretation_frame": "What we think it means:",
    "sketch_frame": "The proof in order, {basis}:",
    "sketch_basis_source": "from reading the Lean source",
    "sketch_basis_compiled": "from the goals Lean shows when this part of the release is compiled",
    "recognition_label_line": "No mathematician has checked our reading yet. If you think we have it wrong, or you know more, please tell us.",
    "recognition_citation_dated_line": "{source}, {where}",
    "recognition_citation_open_line": "{source}, {where}, dated {source_date}",
    "established_by_line": "Where it is proved: the release proves this statement as {name}.",
}
F37_EVIDENCE = {
    "evidence_statement_read_line": "Statement read by {reader} on {date}.",
    "evidence_statement_census_line": "Statement counted by a program, not read, recorded by {reader} on {date}.",
    "evidence_proof_read_line": "Proof read by {reader} on {date}.",
    "evidence_second_reader_line": "Read again by {reader} on {date}.",
    "evidence_recognition_line": "Our reading of where this statement stands: written by {reader} on {date}.",
    "evidence_citation_line": "{source}: opened by {opened_by} on {opened_on}.",
    "evidence_established_line": "Where it is proved: traced to {name} by {reader} on {date}.",
    "evidence_sketch_build_line": "Proof sketch from a compiled part of the release: {build}.",
}
# the keys the wording file says stay as they were on the card (their values at the head of F35, the real file's)
F37_UNCHANGED = {
    "proof_not_applicable_line": "Proof: none needed. This step is a definition, not a theorem: it gives a name to a statement (or to a kind of object) and does not claim that the statement is true, so there is no proof to read.",
    "proof_none_other_line": "Proof: none to read. Our table of the release's declarations does not list this step as a theorem or a lemma, so the page shows no proof for it.",
    "established_not_traced_line": "Where it is proved: we have not yet traced where in the release this statement is proved.",
    "recognition_citation_line": "{source}, {where}",
    "recognition_result_known_line": "Our reading: this is a well-known result in mathematics ({result}).",
    "recognition_result_variant_line": "Our reading: this is a version of a well-known result ({result}), changed to fit this proof.",
    "recognition_result_not_recognised_line": "Our reading: we do not recognise this as a known result. It may come from this proof, or it may be known and we have not found it.",
    "recognition_result_open_line": "Our reading: this result's statement is {result}, an open problem as of {source_date} according to the dated source below.",
    "recognition_named_statement_known_line": "Our reading: the statement named here is a well-known result in mathematics ({result}).",
    "recognition_named_statement_variant_line": "Our reading: the statement named here is a version of a well-known result ({result}), changed to fit this proof.",
    "recognition_named_statement_not_recognised_line": "Our reading: we do not recognise the statement named here as a known result. It may come from this proof, or it may be known and we have not found it.",
    "recognition_named_statement_open_line": "Our reading: the statement named here is {result}, an open problem as of {source_date} according to the dated source below.",
    "recognition_object_known_line": "Our reading: this is the standard definition of {result}.",
    "recognition_object_variant_line": "Our reading: this is a version of the standard definition of {result}, changed to fit this proof.",
    "recognition_object_not_recognised_line": "Our reading: we do not recognise this as a standard definition. It may be made for this proof, or it may be standard and we have not found it.",
    "recognition_not_written_line": "Our reading of this statement: not written yet.",
    "named_statement_use_line": "This step gives a name to a statement. Steps that use the name take the statement as a hypothesis.",
    "sketch_note": "A sketch for a reader, not a proof: it leaves steps out and may hide the hard part.",
    "sketch_missing_line": "Proof sketch: not written yet.",
    "unexpanded_heading": "Places where Lean finishes the proof by automation we have not opened up:",
    "evidence_label": "Evidence: where this sits in the Lean code, and who read what",
    "mapped_line": "Each step below names results in the Lean code; a program located each one in the code and linked it. Under each step, two lines say whether one of us has read what it states and how it is proved.",
}


def _strings():
    s = {
        "page_title": "Page title",
        "first_screen": ["First screen paragraph one.", "First screen paragraph two."],
        "mapped_line": "Mapped by machine line.",
        "no_claim_label": "No plain statement yet",
        "statement_read_line": "We have read this statement.",
        "statement_census_line": "We have not read this statement: what it says here comes from a program's count of its parts.",
        "statement_not_read_line": "We have not read this statement yet.",
        "proof_read_line": "We have read this proof.",
        "proof_not_read_line": "We have not read this proof yet.",
        "proof_not_applicable_line": "Proof: none to read, this is not a theorem.",
        "proof_none_other_line": "Proof: none to read, and this declaration is of a kind we do not know.",
        "steps_proof_not_applicable_line": "No step here has a proof to read.",
        "statement_count_line": "Statements read: {n} of {m} declarations.",
        "proof_count_line": "Proofs read: {n} of {m} declarations.",
        "open_items_line": "Questions written down: {n}.",
        "steps_statement_line": "Statements read: {n} of {m} steps.",
        "steps_proof_line": "Proofs read: {n} of {m} steps.",
        "steps_open_items_line": "Questions written down in these notes: {n}.",
        "frames": {"argument": ["How this is proved"], "interpretation": ["We think"], "claim": []},
        "argument_frame": "How this is proved:",
        "interpretation_frame": "What we think it means:",
        "evidence_label": "Evidence: where this sits in the Lean code, and who read what",
        "evidence_module_label": "Module", "evidence_name_label": "Name", "evidence_kind_label": "Kind",
        "reactions": [{"label": "This makes sense", "href": "https://example.invalid/react?card={card}&kind=sense"},
                      {"label": "This looks wrong to me", "href": "https://example.invalid/react?card={card}&kind=wrong"},
                      {"label": "I can't follow yet: I need more detail",
                       "href": "https://example.invalid/react?card={card}&kind=detail"}],
        "roots_only_note": "Counts are for the named declarations only.",
        "dirty_note": "This page was built from changes not yet committed.",
        "shared_note": "Also a root of: {groups}",
        "note_href": "notes/{file}",
        "forbidden_words": ["verified", "explained", "understood"],
        "labels": {"chain": "The chain of steps", "level0_notes": "Notes about the whole", "premises": "Rests on",
                   "notes": "Notes", "go_deeper": "Go deeper: the parts of this step", "blocks": "Blocks",
                   "open_items": "Open items", "file": "File", "lines": "Lines", "sha256": "SHA-256",
                   "read_more": "Read the note", "lines_missing": "not given",
                   "kinds": {"machine_fact": "Machine fact", "reading": "Reading", "interpretation": "Interpretation",
                             "correction": "Correction", "not_read": "Not read", "argument": "Argument",
                             "sketch": "Proof sketch"}}}
    s.update(WORDING)
    s["argument_frame_no_proof"] = NO_PROOF_FRAME
    s.update(F37_EVIDENCE)
    return s


N06 = ("# Note six\n" + _h(id="06", group="g3", list_title="Note six") + "\n\n## Body\n\n"
       "Corge argument sentence. Second corge sentence.\n"
       + _b(id="06.b01", kind="argument", decls=[CORGE], reader="Reader One", date="2026-11-23") + "\n")
N05 = ("# Note five\n" + _h(id="05", group="g1a", list_title="Note five") + "\n\n## Body\n\n"
       "Bar argument sentence. Second bar sentence.\n"
       + _b(id="05.b01", kind="argument", decls=[BAR], reader="Reader Two", date="2026-11-23") + "\n\n"
       "Opening paragraph of the bar sketch.\n\n- Bullet one.\n- Bullet two.\n\nClosing paragraph of the bar sketch.\n"
       + _b(id="05.b02", kind="sketch", decls=[BAR], reader="Reader Two", date="2026-11-24", basis="source", span=3) + "\n")
N07 = ("# Note seven\n" + _h(id="07", group="g1a1", list_title="Note seven") + "\n\n## Body\n\n"
       "Def argument sentence. Second def sentence.\n"
       + _b(id="07.b01", kind="argument", decls=[BAZ], reader="Reader One", date="2026-11-23", file="A/C.lean", lines=[5, 9]) + "\n\n"
       "Mixed argument sentence. Second mixed sentence.\n"
       + _b(id="07.b02", kind="argument", decls=[BAZ, QUUX], reader="Reader Two", date="2026-11-24", file="A/Deep/TopPlug.lean") + "\n"
       "\n## Files this note was written from\n\n| File | SHA-256 |\n|---|---|\n| `A/C.lean` | `x` |\n| `A/Deep/TopPlug.lean` | `x` |\n")


def _n04(para="First sketch paragraph with `a span`.", item="Ordered item `two` here.",
         last="Last sketch paragraph, see [note 6](06-x.md).", unexpanded=("Closed by `omega` automation.", "A last `simp` call."),
         build="lake build A.B", decls=None):
    """Note four: a sketch of three elements (a paragraph, an ordered list, a paragraph) for the root of g1."""
    return ("# Note four\n" + _h(id="04", group="g1", list_title="Note four") + "\n\n## Body\n\n"
            + para + "\n\n1) Ordered item one.\n2) " + item + "\n\n" + last + "\n"
            + _b(id="04.b01", kind="sketch", decls=decls or [FOO], reader="Reader Two", date="2026-11-24", basis="compiled", build=build,
                 unexpanded=list(unexpanded), span=3) + "\n")


def _notes_s(**kw):
    """The notes with a sketch on g1 (compiled) and on g1a (source), and an argument on g3: note six is 06-x.md."""
    return _notes() | {"04-sketch.md": _n04(**kw), "05-bar.md": N05, "06-x.md": N06}


def _notes_e(**kw):
    """The notes with a note named 06-x.md, so that a link to it is a link to a note of the build."""
    return _notes(**kw) | {"06-x.md": N06}


def _notes_corr():
    """The notes with a correction on the definition g1a1 in two notes (eight and nine), and one on the theorem g3 (ten): each has its
    own reader and date (g1 has the one of note one, 01.b06)."""
    def note(i, group, root, who, date):
        return (f"# Note {i}\n" + _h(id=i, group=group, list_title="Note " + {"08": "eight", "09": "nine", "10": "ten"}[i]) + "\n\n## Body\n\n"
                "What was wrong here.\n" + _b(id=f"{i}.b01", kind="correction", decls=[root], reader=who, date=date) + "\n")
    return _notes() | {"08-corr.md": note("08", "g1a1", BAZ, "Reader Three", "2026-11-26"),
                       "09-corr.md": note("09", "g1a1", BAZ, "Reader Four", "2026-11-27"),
                       "10-corr.md": note("10", "g3", CORGE, "Reader Five", "2026-11-28")}


CITA = {"source": "The Source Book", "where": "Theorem 2.1", "opened_by": "Reader Two", "opened_on": "2026-11-21",
        "url": "https://example.invalid/book"}
CITB = {"source": "Other `Paper`", "where": "Section 3", "opened_by": "Reader One", "opened_on": "2026-11-22"}
EST = {"by": {"module": "A.B", "name": "foo"}, "reader": "Reader Two", "date": "2026-11-23"}


def _oc(source, date, says=True):
    return {"source": source, "where": "Problem 7", "opened_by": "Reader Two", "opened_on": "2026-11-22", "says_open": says,
            "source_date": date}


def _rec(form, **kw):
    return dict({"form": form, "reader": "Reader One", "date": "2026-11-22"}, **kw)


_ZOO = [
    ("zrk", FOO, "result", _rec("known", result="the `prime` counting formula", citations=[CITA])),
    ("zrv", FOO, "result", _rec("variant", result="Foo's theorem", difference="Here the bound is `n`, not `2n`.", citations=[CITA, CITB])),
    ("zrn", FOO, "result", _rec("not_recognised")),
    ("zro", FOO, "result", _rec("open_in_literature", result="the Foo conjecture",
                                citations=[_oc("List A", "2007-01"), _oc("List B", "2004-05-17"), _oc("List C", "2010-03"),
                                           _oc("List D", "2020-01", False)])),
    ("zry", FOO, "result", _rec("open_in_literature", result="the Bar conjecture", citations=[_oc("List Y", "2006")])),
    ("znk", BAZ, "named_statement", _rec("known", result="res-znk", citations=[CITB], established=EST)),
    ("znv", BAZ, "named_statement", _rec("variant", result="res-znv", difference="It differs.", citations=[CITB],
                                         established="not_traced")),
    ("znn", BAZ, "named_statement", _rec("not_recognised")),
    ("zno", BAZ, "named_statement", _rec("open_in_literature", result="res-zno", citations=[_oc("List E", "2006"), _oc("List F", "2006-11")])),
    ("zok", BAZ, "object", _rec("known", result="res-zok", citations=[CITB], reader="Reader Two", date="2026-11-23")),
    ("zov", BAZ, "object", _rec("variant", result="res-zov", difference="It differs here.", citations=[CITB, _oc("List G", "2015")])),
    ("zon", BAZ, "object", _rec("not_recognised")),
    ("zkr", FOO, None, _rec("known", result="res-zkr", citations=[CITB])),
    ("zkn", BAZ, None, _rec("known", result="res-zkn", citations=[CITB])),
    ("zw", FOO, "result", None),
    ("zwn", BAZ, "named_statement", None),
]


def _zoo():
    """The outline with sixteen claimed groups under g1 (level 2), one for each role and form of the recognition, the roles and
    forms the page tells apart (zkr and zkn carry no root_role); each group dict is written with its keys in reverse order."""
    o = _outline()
    for i, (gid, root, role, rec) in enumerate(_ZOO):
        g = _g(gid, 2, "g1", 10 + i, [root], _claim("Zoo " + gid))
        if role:
            g["root_role"] = role
        if rec is not None:
            g["recognition"] = rec
        o["groups"].append(dict(reversed(list(g.items()))))
    return o


def _outline_b():
    """The outline with g2 resting on a theorem and a definition (QUUX and BAZ)."""
    o = _outline()
    next(g for g in o["groups"] if g["id"] == "g2")["roots"] = [QUUX, BAZ]
    return o


def _notes_b():
    return _notes() | {"07-def.md": N07}


def _outline_r(field, value):
    """The outline with g1 a result whose recognition (a variant) holds `value` as its `field`."""
    o = _outline()
    g = next(g for g in o["groups"] if g["id"] == "g1")
    g["root_role"] = "result"
    cit = {"source": "A source", "where": "A place", "opened_by": "Reader One", "opened_on": "2026-11-22"}
    rec = _rec("variant", result="A result", difference="A difference.", citations=[cit])
    if field in ("source", "where"):
        cit[field] = value
    else:
        rec[field] = value
    g["recognition"] = rec
    return o


_REQ2 = (("recognition_result_known_line", ("result",)), ("recognition_result_variant_line", ("result",)),
         ("recognition_result_open_line", ("result", "source_date")),
         ("recognition_named_statement_known_line", ("result",)), ("recognition_named_statement_variant_line", ("result",)),
         ("recognition_named_statement_open_line", ("result", "source_date")),
         ("recognition_object_known_line", ("result",)), ("recognition_object_variant_line", ("result",)),
         ("recognition_citation_line", ("source", "where")),
         ("recognition_citation_dated_line", ("source", "where")),
         ("recognition_citation_open_line", ("source", "where", "source_date")),
         ("established_by_line", ("name",)), ("sketch_frame", ("basis",)),
         ("evidence_statement_read_line", ("reader", "date")), ("evidence_statement_census_line", ("reader", "date")),
         ("evidence_proof_read_line", ("reader", "date")), ("evidence_second_reader_line", ("reader", "date")),
         ("evidence_recognition_line", ("reader", "date")), ("evidence_citation_line", ("source", "opened_by", "opened_on")),
         ("evidence_established_line", ("name", "reader", "date")),
         ("evidence_sketch_build_line", ("build",)))   # the keys of the recognition, the established line, the sketch and the Evidence that must hold their placeholders


def _marked(v, path=""):
    """The strings fixture with every string value replaced by a distinct marker naming its key."""
    if isinstance(v, str):   # a key that must hold its placeholders keeps them behind the marker (they are filled with data)
        return (("https://" if path.endswith(".href") and path.startswith("reactions") else "") + "MARK-" + path
                + "".join(" {" + t + "}" for t in REQUIRED_PLACEHOLDERS.get(path, ())))
    if isinstance(v, list):
        return [_marked(x, f"{path}.{i}") for i, x in enumerate(v)]
    if isinstance(v, dict):
        return {k: (x if k == "when" else _marked(x, f"{path}.{k}" if path else k)) for k, x in v.items()}
    return v


def _put(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data if isinstance(data, bytes) else data.encode("utf-8"))


def _with_roles(outline, decls):
    """The outline with a root_role on every group that has a claim and none: `result` when the kind of its one root in the table `decls`
    is theorem or lemma, else `named_statement`, as notes_meta compares them. A group that already has one, and one whose root has no
    row, is left as it is. The fixtures are role-complete, so the selftest passes whatever REQUIRE_ROOT_ROLE says."""
    kinds = {}
    for ln in decls.splitlines():
        c = ln.split("\t")
        if len(c) == 6 and c != nm.DECL_COLS and not ln.startswith("#"):
            kinds.setdefault((c[0], c[1]), c[2])
    out = json.loads(json.dumps(outline))
    for g in out["groups"]:
        if isinstance(g.get("claim"), dict) and "root_role" not in g and len(g.get("roots", [])) == 1:
            kind = kinds.get((g["roots"][0]["module"], g["roots"][0]["name"]))
            if kind is not None:
                g["root_role"] = "result" if kind in PROOF_KINDS else "named_statement"
    return out


def _plant(d, notes=None, outline=None, decls=DECLS, strings=None, src=None, roles=True):
    """The fixture under directory d; the paths run() takes. `roles` False leaves the outline as given (for a case that needs a claim
    with no root_role and calls the model directly)."""
    for k, v in (_notes() if notes is None else notes).items():
        _put(os.path.join(d, "notes", k), v)
    p = {"notes": os.path.join(d, "notes"), "outline": os.path.join(d, "outline.json"),
         "decls": os.path.join(d, "decls.tsv"), "strings": os.path.join(d, "strings.json"), "out": os.path.join(d, "out")}
    os.makedirs(p["notes"], exist_ok=True)
    o = _outline() if outline is None else outline
    _put(p["outline"], json.dumps(_with_roles(o, decls) if roles and isinstance(decls, str) else o))
    _put(p["decls"], decls)
    s = _strings() if strings is None else strings
    _put(p["strings"], s if isinstance(s, (str, bytes)) else json.dumps(s))
    p["src"] = None
    if src is not None:
        p["src"] = os.path.join(d, "src")
        os.makedirs(p["src"])
        for k, v in src.items():
            _put(os.path.join(p["src"], k), v)
    return p


class _B:
    """A finished build: exit code, stdout, stderr, whether OUT_DIR exists, and every file under it."""

    def __init__(self, rc, out, err, existed, files):
        self.rc, self.out, self.err, self.existed, self.files = rc, out, err, existed, files

    def text(self, rel):
        return self.files[rel].decode("utf-8")

    def js(self, rel):
        return json.loads(self.text(rel))

    @property
    def page(self):
        return self.text("index.html")


def _tree(out):
    files = {}
    for d, _dirs, fs in os.walk(out):
        for f in fs:
            p = os.path.join(d, f)
            with open(p, "rb") as fh:
                files[os.path.relpath(p, out).replace(os.sep, "/")] = fh.read()
    return files


def _build(state=TOOLS_OK, pre=None, force=False, archive=None, notes_commit=None, repo=None, **plant):
    with tempfile.TemporaryDirectory() as d:
        p = _plant(d, **plant)
        if pre:
            pre(p["out"])
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            rc = run(p["notes"], p["outline"], p["decls"], p["strings"], p["out"], source_check=p["src"],
                     archive_sha=archive, notes_commit=notes_commit, repo=repo, force=force, tools_state=state)
        return _B(rc, buf.getvalue(), err.getvalue(), os.path.exists(p["out"]), _tree(p["out"]) if os.path.isdir(p["out"]) else {})


@contextlib.contextmanager
def _patched(name, value):
    real = globals()[name]
    globals()[name] = value
    try:
        yield
    finally:
        globals()[name] = real


def _full_disk(dirpath, files):
    """A writer that writes one file and then fails like a full disk."""
    rel = sorted(files)[0]
    _put(os.path.join(dirpath, *rel.split("/")), files[rel])
    raise OSError(28, "No space left on device")


def _go(p, **kw):
    o, e = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
        rc = run(p["notes"], p["outline"], p["decls"], p["strings"], p["out"], tools_state=TOOLS_OK, **kw)
    return rc, o.getvalue(), e.getvalue()


def _left(d):
    return sorted(set(os.listdir(d)) - {"notes", "outline.json", "decls.tsv", "strings.json", "src", "out", "args.json"})


def _hostile(v, path=""):
    """The strings fixture with the hostile text added to every string (the href templates get the one with `%`)."""
    if isinstance(v, str):
        return v + HOST if (path == "note_href" or path.endswith(".href")) else v + " " + HOST_S
    if isinstance(v, list):
        return [_hostile(x, f"{path}.{i}") for i, x in enumerate(v)]
    if isinstance(v, dict):
        return {k: (x if k in ("when", "forbidden_words") else _hostile(x, f"{path}.{k}" if path else k)) for k, x in v.items()}
    return v


def _raw(node):
    return "".join(node.pieces())


@functools.lru_cache(maxsize=None)
def _base():
    return _build()


@functools.lru_cache(maxsize=None)
def _zbase():
    return _build(outline=_zoo())


@functools.lru_cache(maxsize=None)
def _sbase():
    return _build(notes=_notes_s())


@functools.lru_cache(maxsize=None)
def _bbase():
    return _build(outline=_outline_b(), notes=_notes_b())


@functools.lru_cache(maxsize=None)
def _base_src():
    return _build(src={"A/B.lean": SRC40})


def _eq(actual, expected):
    return actual == expected, f"expected {expected!r}, got {actual!r}"


# ---- a small DOM, so a case reads the page as a tree

class _Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.kids = tag, dict(attrs), parent, []

    @property
    def cls(self):
        return (self.attrs.get("class") or "").split()

    def nodes(self):
        for k in self.kids:
            if isinstance(k, _Node):
                yield k
                yield from k.nodes()

    def pieces(self):
        for k in self.kids:
            if isinstance(k, _Node):
                yield from k.pieces()
            else:
                yield k

    def text(self):
        return " ".join(" ".join(self.pieces()).split())

    def elems(self):
        return [k for k in self.kids if isinstance(k, _Node)]

    def find(self, tag=None, cls=None, id=None):
        return [n for n in self.nodes() if (tag is None or n.tag == tag) and (cls is None or cls in n.cls)
                and (id is None or n.attrs.get("id") == id)]

    def inside(self, tag, cls=None):
        n = self.parent
        while n is not None:
            if n.tag == tag and (cls is None or cls in n.cls):
                return True
            n = n.parent
        return False


def _dom(page):
    root = _Node("#root", [], None)
    stack = [root]
    void = {"meta", "br", "hr", "img", "link", "input"}

    class P(html.parser.HTMLParser):
        def handle_starttag(self, tag, attrs):
            n = _Node(tag, attrs, stack[-1])
            stack[-1].kids.append(n)
            if tag not in void:
                stack.append(n)

        def handle_endtag(self, tag):
            if tag in void:
                return
            while len(stack) > 1 and stack[-1].tag != tag:
                stack.pop()
            if len(stack) > 1:
                stack.pop()

        def handle_data(self, data):
            stack[-1].kids.append(data)

    P(convert_charrefs=True).feed(page)
    return root


def _card(b, gid):
    return _dom(b.page).find("article", id=gid)[0]


def _direct(card, tag, cls=None):
    return [k for k in card.elems() if k.tag == tag and (cls is None or cls in k.cls)]


def _words(text):
    return set(re.findall(r"[A-Za-z]+", text))


def _git(cwd, *args):
    env = dict(os.environ, GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_SYSTEM=os.devnull)
    r = subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", "-c", "commit.gpgsign=false", *args],
                       cwd=cwd, capture_output=True, env=env)
    if r.returncode != 0:
        raise AssertionError(f"git {args}: {r.stderr!r}")
    return r.stdout.decode().strip()


def _child(args_file, out, seed):
    """One build in a child interpreter under PYTHONHASHSEED=seed (the module is loaded by file path)."""
    code = ("import importlib.util, json, sys\n"
            "s = importlib.util.spec_from_file_location('bs', sys.argv[1]); m = importlib.util.module_from_spec(s)\n"
            "s.loader.exec_module(m)\n"
            "a = json.load(open(sys.argv[2]))\n"
            "sys.exit(m.run(a['notes'], a['outline'], a['decls'], a['strings'], sys.argv[3], tools_state=('tools0', False)))\n")
    r = subprocess.run([sys.executable, "-c", code, os.path.abspath(__file__), args_file, out], capture_output=True, text=True,
                       timeout=120, env=dict(os.environ, PYTHONHASHSEED=str(seed)))
    return r.returncode, r.stdout + r.stderr


STRING_KEYS = ["page_title", "first_screen", "mapped_line", "no_claim_label", "statement_read_line", "statement_census_line",
               "statement_not_read_line", "proof_read_line", "proof_not_read_line", "proof_not_applicable_line", "proof_none_other_line",
               "steps_proof_not_applicable_line", "statement_count_line",
               "proof_count_line", "open_items_line", "steps_statement_line", "steps_proof_line", "steps_open_items_line", "frames",
               "argument_frame", "interpretation_frame", "evidence_label",
               "evidence_module_label", "evidence_name_label", "evidence_kind_label", "reactions",
               "roots_only_note", "dirty_note", "shared_note", "note_href", "forbidden_words",
               "labels", "labels.chain", "labels.level0_notes", "labels.premises", "labels.notes", "labels.go_deeper",
               "labels.blocks", "labels.open_items", "labels.file", "labels.lines", "labels.sha256", "labels.read_more",
               "labels.lines_missing", "labels.kinds", "labels.kinds.machine_fact", "labels.kinds.reading",
               "labels.kinds.interpretation", "labels.kinds.correction", "labels.kinds.not_read", "labels.kinds.argument",
               "labels.kinds.sketch", "argument_frame_no_proof"] + list(WORDING) + list(F37_EVIDENCE)


def _real_strings_facts(path):
    """(the problems `_strings_problems` finds in the strings file at `path`, whether it carries the key proof_not_applicable_line,
    whether that value is free of braces)."""
    with open(path, encoding="utf-8") as f:
        real = json.load(f)
    v = real.get("proof_not_applicable_line") if isinstance(real, dict) else None
    return _strings_problems(real), isinstance(v, str), isinstance(v, str) and "{" not in v and "}" not in v


def _selftest_cases():
    cases = []

    def case(cid, desc):
        def deco(fn):
            cases.append((cid, desc, fn))
            return fn
        return deco

    # ---- helpers for the cases that read the Evidence section (F37)
    def surface(node):
        """The text of a node outside every closed Evidence section (F37: the corrections list is read too)."""
        out = []
        for k in node.kids:
            if isinstance(k, _Node):
                if k.tag == "details" and "evidence" in k.cls:
                    continue
                out.append(surface(k))
            else:
                out.append(k)
        return " ".join(out)

    evd = lambda b_, g: _card(b_, g).find("details", "evidence")[0]
    prov = lambda b_, g: [_raw(li) for li in _direct(evd(b_, g), "ul", "provenance")[0].elems()] if _direct(evd(b_, g), "ul", "provenance") else None
    blk = lambda b_, g, bid: next(li for li in evd(b_, g).find("ul", "blocks")[0].elems() if bid in [c.text() for c in li.find("code")])
    pairs = lambda li: [[(t.text(), d.text()) for t, d in zip(dl.find("dt"), dl.find("dd"))] for dl in li.find("dl", "block-source")]

    # ---- X: command, output, exit codes
    @case("X1a", "usage: no argument, four positionals, an unknown option, --notes-commit without --repo, a bad archive hash, a REV that is no commit: exit 2, stdout empty, "
                 "nothing written; control: the same call with five positionals builds")
    def _():
        got = []
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            five = [p["notes"], p["outline"], p["decls"], p["strings"], p["out"]]
            for argv in ([], five[:4], five + ["--bogus"], five + ["--notes-commit", "HEAD"], five + ["--release-archive-sha", "zz"],
                         five + ["--notes-commit", "no-such-rev", "--repo", d]):
                o, e = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                    rc = main(["build_site.py"] + argv, check=lambda: 0)
                got.append((rc, o.getvalue(), os.path.exists(p["out"])))
            o, e = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                rc = main(["build_site.py"] + five, check=lambda: 0)
        return _eq(got + [rc], [(2, "", False)] * 6 + [0])

    @case("X1b", "an input that cannot be read: strings.json that is not JSON, a missing outline, SRC_ROOT that is not a "
                 "directory, OUT_DIR that is a file: exit 2, stdout empty, nothing written; control: a good call is exit 0")
    def _():
        bad_strings = _build(strings="{not json")
        got = [(bad_strings.rc, bad_strings.out, bad_strings.existed)]
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            _put(os.path.join(d, "afile"), "x")
            for key, val in (("outline", os.path.join(d, "none.json")), ("source_check", os.path.join(d, "nodir")),
                             ("out", os.path.join(d, "afile"))):
                args = dict(notes_dir=p["notes"], outline=p["outline"], decls=p["decls"], strings=p["strings"], out=p["out"],
                            tools_state=TOOLS_OK)
                args[key] = val
                o, e = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                    rc = run(**args)
                got.append((rc, o.getvalue(), os.path.isdir(args["out"]) and key != "out"))
        return _eq(got + [(_base().rc,)], [(2, "", False)] * 4 + [(0,)])

    @case("X2a", "no note in NOTES_DIR: `CHECKED NOTHING: ...` on stdout, exit 3, nothing written; control: a note present builds")
    def _():
        b = _build(notes={"readme.md": "x\n"})
        return _eq((b.rc, "CHECKED NOTHING" in b.out, b.existed, _base().rc), (3, True, False, 0))

    @case("X2b", "--source-check on a SRC_ROOT with no .lean file: `CHECKED NOTHING: no .lean file under SRC_ROOT`, exit 3, nothing "
                 "written; control: a .lean file under it builds")
    def _():
        b = _build(src={"readme.txt": "x"})
        return _eq((b.rc, "CHECKED NOTHING: no .lean file under SRC_ROOT" in b.out.splitlines(), b.existed, _base_src().rc),
                   (3, True, False, 0))

    @case("X3a", "a name that resolves to no row of decls.tsv: notes_meta's UNRESOLVED line is printed, exit 1, OUT_DIR does not "
                 "exist; control: the table with the row builds (exit 0) and prints the count line")
    def _():
        short = DECLS.replace("A.G\tcorge\ttheorem\t1\t2\ttext-extent\n", "")
        b = _build(decls=short)
        want = "outline: 6 groups, 3 claimed, 3 null, 7 roots resolved, 0 defs_opened resolved, 3 premise links"
        return _eq((b.rc, any(ln.startswith("UNRESOLVED") for ln in b.out.splitlines()), b.existed, _base().rc,
                    want in _base().out.splitlines()), (1, True, False, 0, True))

    @case("X3b", "a note with no header: NO-HEADER printed, exit 1, nothing written")
    def _():
        notes = _notes()
        notes["02-two.md"] = "# Note two\n\n## Body\n\nText.\n"
        b = _build(notes=notes)
        return _eq((b.rc, any(ln.startswith("NO-HEADER") for ln in b.out.splitlines()), b.existed), (1, True, False))

    @case("X3c", "an argument block with no reader is refused through notes_meta (BLOCK-PROBLEM), exit 1, nothing written")
    def _():
        bad = _n01().replace('"reader":"Reader One","second_readers"', '"second_readers"')
        b = _build(notes=_notes(arg_text="x") | {"01-one.md": bad})
        return _eq((b.rc, "BLOCK-PROBLEM" in b.out, b.existed), (1, True, False))

    @case("OUT1", "a non-empty OUT_DIR: OUT-NOT-EMPTY, exit 1, the files already there untouched; control: an empty OUT_DIR "
                  "that exists builds")
    def _():
        b = _build(pre=lambda out: _put(os.path.join(out, "keep.txt"), "old"))
        c = _build(pre=lambda out: os.makedirs(out))
        return _eq((b.rc, "OUT-NOT-EMPTY" in b.out, sorted(b.files), c.rc), (1, True, ["keep.txt"], 0))

    @case("OUT2", "--force removes only what a build writes: an old group/zz.json and an old level0.json go, keep.txt stays and "
                  "the fresh build is there")
    def _():
        def pre(out):
            _put(os.path.join(out, "keep.txt"), "old")
            _put(os.path.join(out, "group", "zz.json"), "{}")
            _put(os.path.join(out, "level0.json"), "old")
        b = _build(pre=pre, force=True)
        return _eq((b.rc, "group/zz.json" in b.files, "keep.txt" in b.files, b.files.get("level0.json") != b"old",
                    "group/g1.json" in b.files), (0, False, True, True, True))

    @case("ID1", "a group id that is not safe as a file name (`a/b`, `..x`): GROUP-ID-UNSAFE naming it, exit 1, nothing written")
    def _():
        res = []
        for bad in ("a/b", "..x"):
            o = _outline()
            o["groups"][1]["id"] = bad   # g1a1x: no child, no premise, no note names it
            b = _build(outline=o)
            res.append((b.rc, f"BUILD-ERROR GROUP-ID-UNSAFE {bad} " in b.out, b.existed))
        return _eq(res, [(1, True, False)] * 2)

    @case("ID2", "two group ids that differ only in case (`G1`, `g1`) would share a file on some systems: GROUP-ID-UNSAFE, exit 1")
    def _():
        o = _outline()
        o["groups"].append(_g("G1", 1, "root", 4, [CORGE]))
        b = _build(outline=o)
        return _eq((b.rc, "GROUP-ID-UNSAFE" in b.out, b.existed), (1, True, False))

    @case("EXIT4", "a failing self-test: a normal run is REFUSED, exit 4, nothing on stdout and nothing written")
    def _():
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            o, e = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                rc = main(["build_site.py", p["notes"], p["outline"], p["decls"], p["strings"], p["out"]], check=lambda: 4)
            return _eq((rc, o.getvalue(), "REFUSED" in e.getvalue(), os.path.exists(p["out"])), (4, "", True, False))

    @case("SEL1", "`--selftest --only ID,ID` runs exactly the named cases; an unknown id exits 2 naming it and runs nothing")
    def _():
        ok_out, bad_out, bad_err = io.StringIO(), io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(ok_out):
            selftest(only=["X2a", "B7d"])
        with contextlib.redirect_stdout(bad_out), contextlib.redirect_stderr(bad_err):
            rc = selftest(only=["X2a", "NOPE"])
        ran = [ln.split(" ")[1] for ln in ok_out.getvalue().splitlines() if ln.startswith("CASE ")]
        return _eq((ran, rc, "NOPE" in bad_err.getvalue(), bad_out.getvalue()), (["X2a", "B7d"], 2, True, ""))

    # ---- data
    @case("L0", "level0.json: the level-1 steps g1 g3 g2 in `order` (the outline lists g3 first, and `order` is not the id order), each with its "
                "facts (statement_read and proof_read when EVERY root has them, unread) and counts; `facts` counts the steps per fact "
                "(statements 1 read + 2 not, proofs 1 + 2); the level-0 note is in header_notes; the totals hold open_items; premises is a field "
                "of the group (g1 [g1a], g3 [g1, g2], g2 []), not of the claim")
    def _():
        l0 = _base().js("level0.json")
        steps = l0["steps"]
        got = ([s["id"] for s in steps], [s["statement_read"] for s in steps], [s["proof_read"] for s in steps],
               [s["unread"] for s in steps], [s["lean_name"] for s in steps], [s["claim_label"] for s in steps],
               steps[0]["claim"], [n["note"] for n in steps[0]["notes"]], steps[0]["notes"][0],
               l0["facts"], l0["header_notes"], l0["totals"], l0["level"], [s["premises"] for s in steps])
        want = (["g1", "g3", "g2"], [True, False, False], [True, False, False], [False, True, False],
                ["foo", "corge", "quux"], [None, None, "No plain statement yet"],
                {"basis": "read", "conditions": ["Condition one holds."], "date": "2026-11-20",
                 "reader": "Reader One", "text": "Claim one"},
                ["01", "02"], {"link": "notes/01-one.md", "list_title": "Note one", "note": "01"},
                {"proof_applicable": 3, "proof_not_applicable": 0, "proof_not_read": 2, "proof_read": 1, "statement_not_read": 2,
                 "statement_read": 1, "steps": 3},
                [{"link": "notes/00-whole.md", "list_title": "Whole one", "note": "00"}],
                {"blocks": 8, "groups": 6, "notes": 4, "open_items": 1, "roots": 6}, 0, [["g1a"], ["g1", "g2"], []])
        return _eq(got, want)

    @case("L1", "level1.json nests child groups to depth 4: g1 > g1a > g1a1 > g1a1x, leaves have no children; steps in `order`, not in id order")
    def _():
        l1 = _base().js("level1.json")
        g1 = l1["steps"][0]
        chain = [g1["id"], g1["children"][0]["id"], g1["children"][0]["children"][0]["id"],
                 g1["children"][0]["children"][0]["children"][0]["id"]]
        leaf = g1["children"][0]["children"][0]["children"][0]
        return _eq((chain, leaf["children"], [s["id"] for s in l1["steps"]], l1["steps"][1]["children"], l1["level"]),
                   (["g1", "g1a", "g1a1", "g1a1x"], [], ["g1", "g3", "g2"], [], 1))

    @case("G1", "group/g1.json holds exactly its keys (premises among them, a field of the group; root_role, root_kind, recognition and "
                "sketches, F24b), its root with kind, file and lines, and its five blocks in id order with "
                "second_readers, text and first sentence; group/g2.json holds the open not_read item and the shared root")
    def _():
        g1, g2, g1a = _base().js("group/g1.json"), _base().js("group/g2.json"), _base().js("group/g1a.json")
        arg = g1["blocks"][1]
        got = (sorted(g1), g1["roots"], [b["block"] for b in g1["blocks"]], arg,
               g2["open_items"], g2["roots"][1], g1a["blocks"], sorted(_base().files))
        want = (["blocks", "commits", "id", "level", "notes", "open_items", "parent", "premises", "recognition", "root_kind", "root_role",
                 "roots", "sketches"],
                [{"file": "A/B.lean", "kind": "theorem", "lines": [10, 20], "module": "A.B", "name": "foo", "sha256": None,
                  "shared_with": [], "statement_read": True, "proof_read": True}],
                ["01.b01", "01.b02", "01.b03", "01.b06", "02.b02"],
                {"block": "01.b02", "date": "2026-11-23", "file": "A/B.lean", "first_sentence": "First argument sentence.",
                 "kind": "argument", "lines": [15, 18], "note": "01", "reader": "Reader One",
                 "roots": [{"module": "A.B", "name": "foo"}],
                 "second_readers": [{"date": "2026-11-24", "reader": "Reader Two"}],
                 "text": "First argument sentence. Second argument sentence."},
                [{"block": "01.b05", "needs": "hand_read", "note": "01", "roots": [{"module": "A.F", "name": "quux"}]}],
                {"file": "A/E.lean", "kind": "theorem", "lines": [1, 4], "module": "A.E", "name": "qux", "sha256": None,
                 "shared_with": ["g1a1x"], "statement_read": True, "proof_read": False},
                [{"block": "01.b04", "date": "2026-11-23", "item": 2, "kind": "reading", "note": "01", "reader": "Reader One",
                  "roots": [{"module": "A.B", "name": "bar"}]}],
                ["data.js", "group/g1.json", "group/g1a.json", "group/g1a1.json", "group/g1a1x.json", "group/g2.json",
                 "group/g3.json", "index.html", "level0.json", "level1.json", "manifest.json"])
        return _eq(got, want)

    @case("G2", "with --source-check a root's sha256 is the hash of its file under SRC_ROOT (a file the release lacks: null)")
    def _():
        b = _base_src()
        return _eq((b.js("group/g1.json")["roots"][0]["sha256"], b.js("group/g1a.json")["roots"][0]["sha256"],
                    b.js("group/g3.json")["roots"][0]["sha256"]), (SRC40_SHA, SRC40_SHA, None))

    @case("M1", "manifest.json: the sha256 of every output file but itself (hashed here, independently), the counts, the release "
                "id, the archive hash given on the command line (control: null without it)")
    def _():
        b = _build(archive="ab" * 32)
        m = b.js("manifest.json")
        want_files = {k: hashlib.sha256(v).hexdigest() for k, v in b.files.items() if k != "manifest.json"}
        return _eq((m["files"] == want_files, m["counts"], m["release_id"], m["release_archive_sha"],
                    _base().js("manifest.json")["release_archive_sha"]),
                   (True, {"blocks": 8, "groups": 6, "notes": 4}, "rel-1", "ab" * 32, None))

    @case("FMT1", "every .json file is sorted keys, 1-space indent, LF only, UTF-8 with the non-ASCII character kept, one final newline")
    def _():
        bad = []
        for k, v in _base().files.items():
            if k.endswith(".json"):
                t = v.decode("utf-8")
                if t != json.dumps(json.loads(t), sort_keys=True, indent=1, ensure_ascii=False) + "\n" or "\r" in t:
                    bad.append(k)
        return _eq((bad, "Claim four with é" in _base().text("level0.json")), ([], True))

    @case("DJS", "data.js is `window.RH_DATA = ` then the JSON of level0, level1 and groups, then `;` and a newline")
    def _():
        t = _base().text("data.js")
        pre, post = "window.RH_DATA = ", ";\n"
        data = json.loads(t[len(pre):-len(post)])
        return _eq((t.startswith(pre), t.endswith(post), sorted(data), sorted(data["groups"]),
                    data["level0"] == _base().js("level0.json"), data["groups"]["g1"] == _base().js("group/g1.json")),
                   (True, True, ["groups", "level0", "level1"], ["g1", "g1a", "g1a1", "g1a1x", "g2", "g3"], True, True))

    @case("B2", "two builds under PYTHONHASHSEED=1 and =2 give byte-identical OUT_DIR (every file, the manifest included)")
    def _():
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            _put(os.path.join(d, "args.json"), json.dumps({k: p[k] for k in ("notes", "outline", "decls", "strings")}))
            r1 = _child(os.path.join(d, "args.json"), os.path.join(d, "o1"), 1)
            r2 = _child(os.path.join(d, "args.json"), os.path.join(d, "o2"), 2)
            t1, t2 = _tree(os.path.join(d, "o1")), _tree(os.path.join(d, "o2"))
            return _eq((r1[0], r2[0], len(t1), t1 == t2), (0, 0, 11, True))

    @case("B3", "note 02 (header group g2, a block anchoring foo and one anchoring qux) is listed under g1, g1a1x and g2 and counted "
                "once in the totals; note 01 under g1, g1a (its list block) and g2 (its not_read block); note 03 has a header "
                "group g3 and no block: it is listed under g3 alone (no coverage claim is made for a note)")
    def _():
        b = _base()
        under = {g: [n["note"] for n in b.js(f"group/{g}.json")["notes"]] for g in ("g1", "g1a", "g1a1", "g1a1x", "g2", "g3")}
        return _eq((under, b.js("level0.json")["totals"]["notes"]),
                   ({"g1": ["01", "02"], "g1a": ["01"], "g1a1": [], "g1a1x": ["02"], "g2": ["01", "02"], "g3": ["03"]}, 4))

    @case("U1", "a level-0 note (header group `root`) is in header_notes and on the page above the chain, in no group's list; "
                "control: a level-0 note that names a real group (g1) is also under no group")
    def _():
        b = _base()
        listed = [n["note"] for g in ("g1", "g1a", "g1a1", "g1a1x", "g2", "g3") for n in b.js(f"group/{g}.json")["notes"]]
        notes = _notes()
        notes["00-whole.md"] = N00.replace('"group":"root"', '"group":"g1"')
        c = _build(notes=notes)
        c_listed = [n["note"] for n in c.js("group/g1.json")["notes"]]
        page = _dom(b.page)
        top = [a.text() for a in page.find("header")[0].find("a")]
        return _eq(("00" in listed, top, c.rc, c_listed, c.js("level0.json")["header_notes"][0]["note"]),
                   (False, ["Whole one"], 0, ["01", "02"], "00"))

    @case("B5a", "every JSON file (and the payload of data.js) carries commits {notes, release, tools}: `unknown`, the outline's "
                 "release id and the tools id given")
    def _():
        b = _base()
        want = {"notes": "unknown", "release": "rel-1", "tools": "tools0"}
        got = {k: v for k, v in ((k, json.loads(b.text(k))["commits"]) for k in b.files if k.endswith(".json"))}
        data = json.loads(b.text("data.js")[len("window.RH_DATA = "):-2])
        return _eq((all(v == want for v in got.values()), len(got), data["level0"]["commits"], data["groups"]["g2"]["commits"]),
                   (True, 9, want, want))

    @case("B5b", "a dirty tools tree stamps `dirty` in all three ids of every JSON file and the page says so in its first screen "
                 "(the strings file's dirty_note, inside the header); control: the clean page does not")
    def _():
        b = _build(state=("tools0", True))
        ids = {json.dumps(json.loads(v)["commits"], sort_keys=True) for k, v in b.files.items() if k.endswith(".json")}
        note = "This page was built from changes not yet committed."
        in_header = [p.text() for p in _dom(b.page).find("header")[0].find("p")]
        return _eq((ids, note in in_header, note in _base().page), ({'{"notes": "dirty", "release": "dirty", "tools": "dirty"}'},
                                                                    True, False))

    @case("B5c", "--notes-commit HEAD --repo DIR: the notes id is the repository's HEAD commit (asked of git here); after an "
                 "uncommitted edit of a note all three ids are `dirty` and the page says so")
    def _():
        if shutil.which("git") is None:
            raise _SkipCase("no git program")
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            _git(d, "init", "-q")
            _git(d, "add", "-A")
            _git(d, "commit", "-q", "-m", "base")
            head = _git(d, "rev-parse", "HEAD")
            res = []
            for edit in (False, True):
                if edit:
                    with open(os.path.join(p["notes"], "02-two.md"), "a", encoding="utf-8") as f:
                        f.write("\nMore.\n")
                shutil.rmtree(p["out"], ignore_errors=True)
                o, e = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(o), contextlib.redirect_stderr(e):
                    rc = run(p["notes"], p["outline"], p["decls"], p["strings"], p["out"], notes_commit="HEAD", repo=d,
                             tools_state=TOOLS_OK)
                res.append((rc, json.load(open(os.path.join(p["out"], "level0.json")))["commits"],
                            "built from changes" in open(os.path.join(p["out"], "index.html")).read()))
            return _eq(res, [(0, {"notes": head, "release": "rel-1", "tools": "tools0"}, False),
                             (0, {"notes": "dirty", "release": "dirty", "tools": "dirty"}, True)])

    @case("R1a", "F4 planted: a flag that is not a true, a false or (for the proof) a null is fed to the fact function for the steps: "
                 "SUM-STATEMENT `steps: read 0 + not read 2 = 2, but there are 3 steps`, SUM-PROOF `steps: read 0 + not read 2 + not "
                 "applicable 0 = 2, but there are 3 steps`, exit 1, nothing written; planted on the roots of g2: `group g2 roots: read 1 "
                 "+ not read 0 = 1, but there are 2 roots` (statement) and `read 0 + not read 1 + not applicable 0 = 1, ...` (proof); "
                 "a null on a proof flag is NOT a mismatch (not applicable: the build passes and the line counts it); the sums guard a "
                 "MISSING flag, not a wrong one; fact_pairs counts only true and false, fact_triples true, false and null")
    def _():
        real = globals()["_fact_flags"]
        res = []
        for key, n_items in (("statement_read", 3), ("proof_read", 3), ("statement_read", 2), ("proof_read", 2)):
            def plant(items, k, key=key, n_items=n_items, real=real):
                flags = real(items, k)
                return [("?" if k == "proof_read" else None)] + flags[1:] if k == key and len(items) == n_items else flags
            with _patched("_fact_flags", plant):
                b = _build()
            res.append((b.rc, [ln for ln in b.out.splitlines() if ln.startswith("BUILD-ERROR SUM-")], b.existed))

        def plant_none(items, k, real=real):
            flags = real(items, k)
            return [None] + flags[1:] if k == "proof_read" and len(items) == 3 else flags
        with _patched("_fact_flags", plant_none):
            ok_ = _build()
        err = "read 0 + not read 2 = 2, but there are 3 steps"
        err_p = "read 0 + not read 2 + not applicable 0 = 2, but there are 3 steps"
        return _eq((res, fact_pairs([True, False, None, True]), fact_pairs([]), fact_triples([True, False, None, "?", None]),
                    fact_triples([]), ok_.rc, [ln for ln in ok_.out.splitlines() if ln.startswith("facts check: ")]),
                   ([(1, ["BUILD-ERROR SUM-STATEMENT steps: " + err], False), (1, ["BUILD-ERROR SUM-PROOF steps: " + err_p], False),
                     (1, ["BUILD-ERROR SUM-STATEMENT group g2 roots: read 1 + not read 0 = 1, but there are 2 roots"], False),
                     (1, ["BUILD-ERROR SUM-PROOF group g2 roots: read 0 + not read 1 + not applicable 0 = 1, but there are 2 roots"],
                      False)],
                    (2, 1), (0, 0), (1, 1, 2), (0, 0, 0), 0,
                    ["facts check: statements read 1 + not read 2 = 3 steps; proofs read 0 + not read 2 + not applicable 1 = 3 steps"]))

    @case("R1b", "a good build prints `facts check: statements read 1 + not read 2 = 3 steps; proofs read 1 + not read 2 + not applicable 0 "
                 "= 3 steps`")
    def _():
        return _eq("facts check: statements read 1 + not read 2 = 3 steps; proofs read 1 + not read 2 + not applicable 0 = 3 steps"
                   in _base().out.splitlines(), True)

    # ---- page
    @case("P1a", "a missing key of the strings file (each of the 86 keys in turn) is a build error that names it, exit 1, nothing "
                 "written; control: the full file builds")
    def _():
        bad = []
        for key in STRING_KEYS:
            s = _strings()
            node, path = s, key.split(".")
            for part in path[:-1]:
                node = node[part]
            del node[path[-1]]
            b = _build(strings=s)
            if not (b.rc == 1 and f"BUILD-ERROR STRINGS-KEY {key} " in b.out and not b.existed):
                bad.append((key, b.rc, b.out[:120]))
        return _eq((bad, len(STRING_KEYS)), ([], 86))

    @case("P1b", "every strings value a distinct marker: the page shows only markers and data (every word on it is in the "
                 "marker tokens or the fixture's own data), the markers of first_screen come first, and no typed sentence")
    def _():
        b = _build(strings=_marked(_strings()))
        if b.rc != 0:
            return False, b.out + b.err
        dom = _dom(b.page)
        text = " ".join(dom.find("body")[0].pieces())
        text = re.sub(r"MARK-[A-Za-z0-9_.]*[A-Za-z0-9_]", " ", text)
        data = json.dumps(_outline()) + DECLS + " ".join(_notes().values())
        stray = sorted(_words(text) - _words(data))
        first = [p.text() for p in dom.find("header")[0].find("p")][:2]
        return _eq((stray, first), ([], ["MARK-first_screen.0", "MARK-first_screen.1"]))

    @case("P2a", "a card, in order: the claim, the conditions directly under it, the premises, the statement line, the proof line, the "
                 "idea (the open-items line is absent here: g1 has no open item); all direct children of the card, before the closed evidence section")
    def _():
        c = _card(_base(), "g1")
        names = [(k.tag, k.cls[-1] if k.cls else "") for k in c.elems()]
        want = [("h3", "claim"), ("ul", "conditions"), ("p", "premises"), ("p", "statement"), ("p", "proof"),
                ("p", "argument"), ("details", "evidence")]
        pos = {n: names.index(n) for n in want}
        return _eq(([n for n in sorted(pos, key=pos.get)], c.find("ul", "conditions")[0].text(), c.find("h3", "claim")[0].text(),
                    c.find("ul", "conditions")[0].inside("details"), _direct(c, "p", "open-items")),
                   (want, "Condition one holds.", "Claim one", False, []))

    @case("P2b", "text from the data is escaped (`Claim three & <more>` shows as text, the raw page has &amp; and &lt;more&gt;), "
                 "and a premise is a link to the premise's card: g3 rests on `Claim one` (#g1) and `quux` (#g2, null claim)")
    def _():
        b = _base()
        prem = _card(b, "g3").find("p", "premises")[0]
        links = [(a.attrs["href"], a.text()) for a in prem.find("a")]
        return _eq((_card(b, "g1a1").find("h3", "claim")[0].text(), "Claim three &amp; &lt;more&gt;" in b.page, links),
                   ("Claim three & <more>", True, [("#g1", "Claim one"), ("#g2", "quux")]))

    @case("P3", "a null claim shows the Lean name of its first root and the no_claim_label in the heading; evidence is a closed "
                "<details> (no `open`) whose summary is the evidence label and which holds the root's file, lines and open item")
    def _():
        c = _card(_base(), "g2")
        ev = c.find("details", "evidence")[0]
        return _eq((c.find("h3", "claim")[0].text(), "open" in ev.attrs, ev.find("summary")[0].text(),
                    "A/F.lean" in ev.text(), "1-3" in ev.text(), "hand_read" in ev.text(),
                    all("open" not in d.attrs for d in _dom(_base().page).find("details"))),
                   ("quux No plain statement yet", False, "Evidence: where this sits in the Lean code, and who read what",
                    True, True, True, True))

    @case("P4", "the child groups of a step are nested in its closed `go deeper` <details>, to depth 4; the three steps stay "
                "in the chain list in `order`")
    def _():
        dom = _dom(_base().page)
        chain = [li.elems()[0].attrs["id"] for li in dom.find("ul", "chain")[0].elems()]
        leaf = dom.find("article", id="g1a1x")[0]
        anc, n = [], leaf.parent
        while n is not None:
            if n.tag == "article":
                anc.append(n.attrs["id"])
            n = n.parent
        det = dom.find("article", id="g1")[0].find("details", "children")[0]
        return _eq((chain, anc, "open" in det.attrs, det.find("summary")[0].text()),
                   (["g1", "g3", "g2"], ["g1a1", "g1a", "g1"], False, "Go deeper: the parts of this step"))

    @case("P5", "three reaction anchors on every card (6 cards, 18 anchors), plain links whose href is the template with the card "
                "id filled (the `&` decoded), in the strings file's order")
    def _():
        dom = _dom(_base().page)
        mine = dom.find("article", id="g1")[0].find("ul", "reactions")[0].find("a")
        return _eq(([(a.attrs["href"], a.text()) for a in mine], len(dom.find("a", "reaction")), len(dom.find("ul", "reactions"))),
                   ([("https://example.invalid/react?card=g1&kind=sense", "This makes sense"),
                     ("https://example.invalid/react?card=g1&kind=wrong", "This looks wrong to me"),
                     ("https://example.invalid/react?card=g1&kind=detail", "I can't follow yet: I need more detail")], 18, 6))

    @case("P6", "number_problems: a number on the page that is in neither the JSON nor the strings file is named; a number in the "
                "JSON, in the strings, a date, an id: none. And the built page has none")
    def _():
        b = _base()
        alljson = "\n".join(v.decode() for k, v in b.files.items() if k.endswith(".json") or k == "data.js")
        return _eq((number_problems("<p>Total 7 and 12</p>", '{"a": 7}', ""), number_problems("<p>7 and 12</p>", '{"a": 7}', "12"),
                    number_problems("<p>2026-11-23 g1a1</p>", '{"a": "2026-11-23", "b": "g1a1"}', ""),
                    number_problems(b.page, alljson, json.dumps(_strings()))),
                   (["12"], [], [], []))

    @case("P6b", "number_pool leaves the hash fields out (sha256, files, commits, release_archive_sha), so a hash cannot vouch for a "
                 "small number; and the builder applies number_problems: a page with an invented number (injected here) is "
                 "refused as PAGE-NUMBER, exit 1, nothing written")
    def _():
        pool = number_pool([{"sha256": "ab7cd", "files": {"x": "9"}, "commits": {"t": "77"}, "release_archive_sha": "55", "n": 3}])
        real = globals()["_render_page"]
        globals()["_render_page"] = lambda *a: real(*a).replace("<h1>", "<h1>99999 ", 1)
        try:
            b = _build()
        finally:
            globals()["_render_page"] = real
        return _eq((number_problems("<p>3 7 9 77 55</p>", pool, ""), b.rc, "BUILD-ERROR PAGE-NUMBER 99999 " in b.out, b.existed),
                   (["7", "9", "55", "77"], 1, True, False))

    @case("P7a", "static_problems: each forbidden thing is named, one planted at a time (fetch(, XMLHttpRequest, WebSocket, "
                 "sendBeacon, import(, @import, src= to http, href= to http, url( to a URL); controls: a reaction anchor to http, "
                 "a local src and href, a # link: none")
    def _():
        sp = static_problems
        planted = [("<script>fetch('a')</script>", "", ["fetch("]), ("<p>x</p>", "var r = new XMLHttpRequest();", ["XMLHttpRequest"]),
                   ("<p>x</p>", "new WebSocket('a')", ["WebSocket"]), ("<p>x</p>", "navigator.sendBeacon('a')", ["sendBeacon"]),
                   ("<p>x</p>", "import('a')", ["import("]), ('<img src="http://x.invalid/a.png">', "", ["src=http"]),
                   ('<script src="https://x.invalid/a.js"></script>', "", ["src=http"]),
                   ('<link rel="stylesheet" href="https://x.invalid/a.css">', "", ["href=http"]),
                   ('<a href="https://x.invalid/">x</a>', "", ["href=http"]),
                   ('<p style="background:url(http://x.invalid/a.png)">x</p>', "", ["url("]),
                   ('<style>body{background:url("https://x.invalid/a.png")}</style>', "", ["url("]),
                   ('<style>@import "https://x.invalid/a.css";</style>', "", ["@import"])]
        controls = ['<a class="reaction" href="https://x.invalid/?card=g1">x</a>', '<img src="local.png"><a href="notes/01.md">x</a>',
                    '<a href="#g1">x</a><p id="g1"></p>']
        return _eq(([sp(h, j) for h, j, _w in planted], [sp(h, "") for h in controls]),
                   ([w for _h, _j, w in planted], [[], [], []]))

    @case("P7b", "the built page and data.js are clean; a strings file whose first_screen holds `fetch(` is refused (PAGE-STATIC), "
                 "exit 1, nothing written")
    def _():
        s = _strings()
        s["first_screen"] = ["Call fetch( now."]
        b = _build(strings=s)
        return _eq((static_problems(_base().page, _base().text("data.js")), b.rc, "BUILD-ERROR PAGE-STATIC fetch( found in strings key first_screen[0]" in b.out, b.existed),
                    ([], 1, True, False))

    @case("P7c", "data.js is scanned as well as the page: a token that only the JSON holds (a block's `file`, which the page does "
                 "not show: `A/fetch(1).lean`) is refused as PAGE-STATIC fetch(, exit 1, nothing written")
    def _():
        n = _n01().replace("A/B.lean", "A/fetch(1).lean")
        b = _build(notes=_notes() | {"01-one.md": n})
        return _eq((b.rc, "BUILD-ERROR PAGE-STATIC fetch( found in group g1 field blocks[0].file" in b.out, b.existed), (1, True, False))

    @case("P7d", "a `#` link with no target on the page is refused (PAGE-LINK naming it), exit 1, nothing written: here a reaction "
                 "note_href `#nowhere` from the strings file (a reaction href must be https)")
    def _():
        st = _strings()
        st["note_href"] = "#nowhere"
        b = _build(strings=st)
        return _eq((b.rc, "BUILD-ERROR PAGE-LINK #nowhere " in b.out, b.existed), (1, True, False))

    @case("R2", "the first screen counts steps per fact (`Statements read: 1 of 3 steps.`, `Proofs read: 1 of 3 steps.`) and the open "
                "blocks once (`Questions written down in these notes: 1.`); a card of a group with several roots (g2) counts "
                "declarations; no percent sign and no `of the proof` anywhere on the page")
    def _():
        dom = _dom(_base().page)
        facts = [li.text() for li in dom.find("ul", "facts")[0].find("li")]
        g2 = _card(_base(), "g2")
        return _eq((facts, g2.find("p", "statement")[0].text(), g2.find("p", "proof")[0].text(),
                    g2.find("p", "open-items")[0].text(), "%" in _base().page, "of the proof" in _base().page),
                   (["Statements read: 1 of 3 steps.", "Proofs read: 1 of 3 steps.", "Questions written down in these notes: 1."],
                    "Statements read: 1 of 2 declarations.", "Proofs read: 0 of 2 declarations.", "Questions written down: 1.",
                    False, False))

    @case("R3a", "a strings value holding verified, explained or understood (or a word of forbidden_words) is refused naming "
                 "its key: STRINGS-FORBIDDEN, exit 1, nothing written; a word added to forbidden_words is refused too, and `unverified` "
                 "and `misunderstood` are not the forbidden words")
    def _():
        res = []
        for key, val in (("mapped_line", "This was verified."), ("proof_not_read_line", "Fully Explained here."),
                         ("evidence_label", "Not understood")):
            s = _strings()
            s[key] = val
            b = _build(strings=s)
            res.append((b.rc, f"BUILD-ERROR STRINGS-FORBIDDEN {key} " in b.out, b.existed))
        s = _strings()
        s["forbidden_words"] = ["unverifiable"]
        s["mapped_line"] = "A word: unverifiable."
        s2 = _strings()
        s2["first_screen"] = ["Not unverified and misunderstood."]
        return _eq((res, _build(strings=s).rc, _build(strings=s2).rc), ([(1, True, False)] * 3, 1, 0))

    @case("R3b", "the built page and the JSON contain none of verified, explained, understood")
    def _():
        t = " ".join(v.decode().lower() for v in _base().files.values())
        return _eq([w in t for w in ("verified", "explained", "understood")], [False, False, False])

    @case("R4a", "no CSS animation or transition keyword in the page (animation, transition, @keyframes), and no opacity, display: "
                 "none or hidden attribute: unread parts are never faded or hidden")
    def _():
        p = _base().page.lower()
        return _eq([w in p for w in ("animation", "transition", "@keyframes", "opacity", "display:none", "display: none", "hidden")],
                   [False] * 7)

    @case("R4b", "a card is `unread` when neither fact holds on any root: g3 (census claim, no block) carries the class and is present; "
                 "g1 (both), g1a1 (claim read, statement only), g2 (one root has the statement) do not; the JSON `unread` agrees")
    def _():
        b = _base()
        steps = {x["id"]: x["unread"] for x in b.js("level0.json")["steps"]}
        return _eq(([("unread" in _card(b, g).cls) for g in ("g3", "g1", "g1a1", "g2")], steps),
                   ([True, False, False, False], {"g1": False, "g3": True, "g2": False}))

    @case("R5", "every card carries the roots_only_note; qux is a root of g2 and of g1a1x: each card marks it shared with the other "
                "group, the JSON says shared_with, and the totals count it once (6 distinct roots)")
    def _():
        b = _base()
        dom = _dom(b.page)
        notes = [c.find("p", "roots-only")[0].text() == "Counts are for the named declarations only." for c in dom.find("article")]
        sh = lambda g: [p.text() for p in _card(b, g).find("details", "evidence")[0].find("p", "shared")]
        return _eq((all(notes), len(notes), sh("g2"), sh("g1a1x"), sh("g1"),
                    b.js("group/g1a1x.json")["roots"][0]["shared_with"], b.js("level0.json")["totals"]["roots"]),
                   (True, 6, ["Also a root of: g1a1x"], ["Also a root of: g2"], [], ["g2"], 6))

    @case("R6", "the correction block on foo is shown on g1's card, outside the closed sections, with its kind and its title and (F37) no reader "
                "and no date, see PV12; "
                "a card with none has no corrections list")
    def _():
        c = _card(_base(), "g1")
        li = _direct(c, "ul", "corrections")
        return _eq(([x.text() for x in li[0].find("li")], len(_direct(_card(_base(), "g3"), "ul", "corrections"))),
                   (["Correction Note one"], 0))

    @case("B7a", "an argument is shown in ONE element, frame first: `How this is proved:` (F37: no reader, no date, no file, no lines) "
                 "then the first sentence and the link, no second reader's line; the full text with the frame is in the evidence (the second "
                 "reader's line follows it there, see PV7); an interpretation is in its own aside with its own frame, apart from the argument")
    def _():
        c = _card(_base(), "g1")
        idea = _direct(c, "p", "argument")[0]
        full = c.find("details", "evidence")[0].find("p", "argument")[0]
        interp = c.find("aside")[0]
        return _eq((idea.text(), idea.elems()[0].cls, full.text(), interp.find("p", "interpretation")[0].text(),
                    full.inside("aside"), interp.inside("details", "evidence")),
                   ("How this is proved: First argument sentence. Read the note", ["frame"],
                    "How this is proved: First argument sentence. Second argument sentence.",
                    "What we think it means: We think this is the key step.", False, True))

    @case("B7b", "the first sentence of the argument is under the claim of the step, outside every closed section, and the second "
                 "sentence is not there")
    def _():
        c = _card(_base(), "g1")
        idea = _direct(c, "p", "argument")[0].text()
        return _eq(("First argument sentence." in idea, "Second argument sentence." in idea, idea.startswith("How this is proved")),
                   (True, False, True))

    @case("B7c", "a step with no argument block shows only the proof status line (`We have not read this proof yet.`), no frame and no second "
                 "sentence about the proof; a stale `no_argument` key in the strings file is ignored and never printed; control: "
                 "the step with an argument block shows `We have read this proof.` and its idea")
    def _():
        c = _card(_base(), "g3")
        st = _strings()
        st["no_argument"] = "We have not read how this is proved."
        b = _build(strings=st)
        return _eq(([p.text() for p in c.find("p", "proof")], len(_direct(c, "p", "argument")), len(_direct(c, "p", "no-argument")),
                    b.rc, "We have not read how this is proved." in b.page,
                    [p.text() for p in _card(_base(), "g1").find("p", "proof")][:1]),
                   (["We have not read this proof yet."], 0, 0, 0, False, ["We have read this proof."]))

    @case("B7d", "link_problems: a # link with no id of that name is named, a repeated id is named; controls: resolving links "
                 "(also one with percent-encoding): none; the built page has none")
    def _():
        lp = link_problems
        return _eq((lp('<a href="#a">x</a><p id="a"></p><a href="#b">y</a>'), lp('<p id="a"></p><p id="a"></p>'),
                    lp('<a href="#a%20b">x</a><p id="a b"></p>'), lp(_base().page)),
                   (["#b"], ["duplicate id a"], [], []))

    @case("B7e", "a reading block with no reader refuses the build (BLOCK-NO-READER naming the block), exit 1, nothing written; "
                 "control: the same note with its reader builds")
    def _():
        b = _build(notes=_notes(drop_reader=True))
        return _eq((b.rc, "BUILD-ERROR BLOCK-NO-READER 01.b01 " in b.out, b.existed, _base().rc), (1, True, False, 0))

    @case("B7f", "an argument block whose target is a list shows its frame (F37: the frame only) and a "
                 "link and no list text; the page never shows the "
                 "text of a list item or a table cell (ListItemTextXYZ, TableCellTextXYZ), nor does any output file")
    def _():
        arg_list = ("- ListItemTextXYZ one\n- ListItemTextXYZ two\n"
                    + _b(id="02.b03", kind="argument", decls=[QUX], item=1, reader="Reader Two", date="2026-11-23", lines=[1, 2])
                    + "\n")
        notes = _notes()
        notes["02-two.md"] = N02 + "\n" + arg_list
        b = _build(notes=notes)
        c = _card(b, "g1a1x")
        idea = _direct(c, "p", "argument")[0].text()
        every = " ".join(v.decode() for v in b.files.values()) + " ".join(v.decode() for v in _base().files.values())
        return _eq((b.rc, idea, "ListItemTextXYZ" in every, "TableCellTextXYZ" in every),
                   (0, "How this is proved: Read the note", False, False))

    @case("U2", "a block anchored to a list carries its `item` and a table block its `row` in the group JSON, as data only")
    def _():
        b = _base()
        return _eq((b.js("group/g1a.json")["blocks"][0]["item"], b.js("group/g2.json")["blocks"][0]["row"],
                    "item" in b.js("group/g1.json")["blocks"][0]), (2, 1, False))

    @case("S1", "statement_read is set only by a claim of basis read or a reading block; proof_read only by an argument block: on the "
                "census-claim root corge (g3) a reading block alone gives (1, 0), an argument block alone (0, 1), an interpretation, "
                "a correction, a not_read and a machine_fact block (0, 0) (the not_read block is one open item); the facts check "
                "still holds")
    def _():
        extra = {"reading": dict(reader="Reader Two", date="2026-11-23"), "argument": dict(reader="Reader Two", date="2026-11-23"),
                 "interpretation": dict(reader="Reader Two", date="2026-11-23"),
                 "correction": dict(reader="Reader Two", date="2026-11-23"), "not_read": dict(needs="hand_read"),
                 "machine_fact": dict(tool="t", tool_version="v", check="text", options="")}
        got = {}
        for kind, kw in extra.items():
            n03 = N03 + _b(id="03.b01", kind=kind, decls=[CORGE], **kw) + "\n"
            b = _build(notes=_notes() | {"03-three.md": n03})
            c = [x for x in b.js("level0.json")["steps"] if x["id"] == "g3"][0]["counts"]
            got[kind] = (b.rc, c["roots_statement_read"], c["roots_proof_read"], c["open_items"])
        want = {k: (0, 1 if k == "reading" else 0, 1 if k == "argument" else 0, 1 if k == "not_read" else 0) for k in extra}
        return _eq(got, want)

    @case("S2", "the first sentence is cut at the first `.`, `!` or `?` that is followed by white space or the end: a decimal or an "
                "abbreviation dot inside a word does not end it (`The constant 1.5 is used. Then more.` gives `The constant 1.5 is "
                "used.`); the group JSON carries it")
    def _():
        t = "The constant 1.5 is used. Then more."
        b = _build(notes=_notes(arg_text=t))
        fs = _first_sentence
        return _eq((fs(t), fs("See e.g.x and 3.2 now"), fs("Is it so? Yes."), fs("Done."), fs("Stop!\nNext."),
                    b.js("group/g1.json")["blocks"][1]["first_sentence"]),
                   ("The constant 1.5 is used.", "See e.g.x and 3.2 now", "Is it so?", "Done.", "Stop!", "The constant 1.5 is used."))

    @case("F1a", "the two facts per root in the base build: g1 (claim read + reading + argument) both; g1a (null claim, reading block) "
                 "statement only; g1a1 (claim without basis, read by default; its root baz is a def, so no proof: None) statement only; g1a1x (null claim, reading block "
                 "on qux) statement only; g2 roots [quux, qux] = [neither, statement only]; g3 (claim census, no block) neither")
    def _():
        b = _base()
        st = lambda g: [(r["statement_read"], r["proof_read"]) for r in b.js(f"group/{g}.json")["roots"]]
        return _eq([st(g) for g in ("g1", "g1a", "g1a1", "g1a1x", "g2", "g3")],
                   [[(True, True)], [(True, False)], [(True, None)], [(True, False)], [(False, False), (True, False)],
                    [(False, False)]])

    @case("F1b", "a census claim with an argument block on its root: proof only; a census claim plus a reading block on its root: "
                 "statement read by the BLOCK (the Evidence line names the block's reader and date; the card only says it is read); a claim "
                 "without basis alone, a claim with basis read alone: statement only")
    def _():
        arg = N03 + _b(id="03.b01", kind="argument", decls=[CORGE], reader="Reader Two", date="2026-11-23") + "\n"
        rd = N03 + _b(id="03.b01", kind="reading", decls=[CORGE], reader="Reader Two", date="2026-11-23") + "\n"
        ba = _build(notes=_notes() | {"03-three.md": arg})
        br = _build(notes=_notes() | {"03-three.md": rd})
        f = lambda b_: [(r["statement_read"], r["proof_read"]) for r in b_.js("group/g3.json")["roots"]]
        line = lambda b_: (_card(b_, "g3").find("p", "statement")[0].text(), prov(b_, "g3")[:1])   # the card, then the Evidence line (F37)
        return _eq((f(ba), line(ba), f(br), line(br)),
                   ([(False, True)], ("We have not read this statement: what it says here comes from a program's count of its parts.",
                                      ["Statement counted by a program, not read, recorded by Reader One on 2026-11-20."]),
                    [(True, False)], ("We have read this statement.", ["Statement read by Reader Two on 2026-11-23."])))

    @case("W1", "a group id that is safe but longer than 100 characters is GROUP-ID-UNSAFE; 100 characters build")
    def _():
        res = []
        for n in (100, 101):
            o = _outline()
            o["groups"][1]["id"] = "a" * n   # g1a1x: no child, no premise, no note names it
            b = _build(outline=o)
            res.append((b.rc, f"BUILD-ERROR GROUP-ID-UNSAFE {'a' * n} " in b.out, b.existed))
        return _eq(res, [(0, False, True), (1, True, False)])

    @case("W2", "a failure while writing (a full disk, injected) in a fresh run: exit 2, ONE line on stderr and no traceback, nothing "
                "on stdout, OUT_DIR absent and no temporary directory left beside it")
    def _():
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            with _patched("_write_files", _full_disk):
                rc, out, err = _go(p)
            return _eq((rc, out, err, os.path.exists(p["out"]), _left(d)),
                       (2, "", "build_site: cannot write the site: No space left on device\n", False, []))

    @case("W3", "the same failure under --force keeps the old build and the foreign file byte-identical and leaves no temporary "
                "directory; control: the --force run without the failure replaces the old build")
    def _():
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            rc0 = _go(p)[0]
            _put(os.path.join(p["out"], "keep.txt"), "k")
            old = _tree(p["out"])
            with _patched("_write_files", _full_disk):
                rc, out, err = _go(p, force=True)
            same = _tree(p["out"]) == old
            rc2 = _go(p, force=True)[0]
            return _eq((rc0, rc, out, err.count("\n"), same, _left(d), rc2, sorted(_tree(p["out"]))[:2]),
                       (0, 2, "", 1, True, [], 0, ["data.js", "group/g1.json"]))

    @case("W6", "the last step fails (the rename of the new tree into place, injected once) under --force, after the old tree was set "
                "aside: the old build and the foreign file are back byte-identical, no temporary directory is left, exit 2 with one line")
    def _():
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            _go(p)
            _put(os.path.join(p["out"], "keep.txt"), "k")
            old = _tree(p["out"])
            target, real, calls = os.path.abspath(p["out"]), os.rename, []

            def fake(a, b, *k, **kw):
                if os.path.abspath(b) == target and not calls:
                    calls.append(1)
                    raise OSError(5, "Input/output error")
                return real(a, b, *k, **kw)
            os.rename = fake
            try:
                rc, out, err = _go(p, force=True)
            finally:
                os.rename = real
            return _eq((rc, out, err, _tree(p["out"]) == old, _left(d), len(calls)),
                       (2, "", "build_site: cannot write the site: Input/output error\n", True, [], 1))

    @case("W4", "an unwritable parent of OUT_DIR: exit 2, one line, no traceback, nothing left behind (SKIPPED when running as root, "
                "which a directory mode does not stop)")
    def _():
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            raise _SkipCase("running as root: a directory mode does not stop root, so the unwritable parent cannot fail here")
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            ro = os.path.join(d, "ro")
            os.makedirs(ro)
            os.chmod(ro, 0o555)
            try:
                rc, out, err = _go(dict(p, out=os.path.join(ro, "out")))
                left = os.listdir(ro)
            finally:
                os.chmod(ro, 0o755)
            return _eq((rc, out, err.count("\n"), "Traceback" in err, left), (2, "", 1, False, []))

    @case("W5", "an outline 1500 groups deep cannot be written as nested JSON: exit 2 with the one line `outline too deep to write`, "
                "nothing on stdout, nothing written")
    def _():
        groups = [_g(f"d{k}", k, "root" if k == 1 else f"d{k - 1}", 1, [FOO]) for k in range(1, 1501)]
        b = _build(notes={"00-whole.md": N00}, outline={"release": "rel-1", "groups": groups})
        return _eq((b.rc, b.out, b.err, b.existed), (2, "", "build_site: outline too deep to write\n", False))

    @case("DUP1", "two notes with the same header id (02, no blocks): the checker's NOTE-ID-DUPLICATE line names both files, exit 1, "
                  "nothing written (the builder has no rule of its own)")
    def _():
        dup = N03.replace('"id":"03"', '"id":"02"')
        b = _build(notes=_notes() | {"04-dup.md": dup})
        lines = [ln for ln in b.out.splitlines() if ln.startswith("NOTE-ID-DUPLICATE ")]
        return _eq((b.rc, len(lines), "02-two.md" in lines[0] and "04-dup.md" in lines[0], "BUILD-ERROR NOTE-ID-DUPLICATE" in b.out,
                    b.existed), (1, 1, True, False, False))

    @case("WN1", "a claim holding `verified` and `50% of the proof` builds (exit 0) and is LISTED: two WORD-NOTE lines naming the "
                 "claim's group, the count in the built line; control: the base build lists none")
    def _():
        o = _outline()
        o["groups"][0]["claim"]["text"] = "A verified claim covering 50% of the proof"
        b = _build(outline=o)
        notes = [ln for ln in b.out.splitlines() if ln.startswith("WORD-NOTE")]
        return _eq((b.rc, notes, "built: 6 groups, 4 notes, 8 blocks, 11 files, 2 word notes" in b.out.splitlines(),
                    "A verified claim covering 50% of the proof" in b.page,
                    [ln for ln in _base().out.splitlines() if ln.startswith("WORD-NOTE")],
                    "built: 6 groups, 4 notes, 8 blocks, 11 files, 0 word notes" in _base().out.splitlines()),
                   (0, ["WORD-NOTE g3.claim verified", "WORD-NOTE g3.claim of the proof"], True, True, [], True))

    @case("WN2", "the other texts of the notes and the outline are listed too, never edited: a condition (g1), a claim with only a "
                 "percent sign (g1a1), the text of an argument block (01.b02) and a note title (02), in that order")
    def _():
        o = _outline()
        o["groups"][2]["claim"]["conditions"] = ["Condition understood here."]
        o["groups"][5]["claim"]["text"] = "Half 50% done"
        n01 = _n01(arg_text="First argument was verified. Second argument sentence.")
        n02 = N02.replace('"list_title":"Note two"', '"list_title":"Explained at once"')
        b = _build(outline=o, notes=_notes() | {"01-one.md": n01, "02-two.md": n02})
        notes = [ln for ln in b.out.splitlines() if ln.startswith("WORD-NOTE")]
        return _eq((b.rc, notes, "Explained at once" in b.page),
                   (0, ["WORD-NOTE g1.conditions[0] understood", "WORD-NOTE g1a1.claim %", "WORD-NOTE block:01.b02.text verified",
                        "WORD-NOTE note:02.list_title explained"], True))

    @case("WN3", "the strings file is refused for a percent sign and for `of the proof` in the builder's own sentences (steps_statement_line, "
                 "mapped_line, first_screen), naming the key, exit 1, nothing written; the href templates may hold `%` (control)")
    def _():
        res = []
        for key, val in (("mapped_line", "A hundred % sure."), ("steps_statement_line", "{n} of the {m} steps, part of the proof"),
                         ("first_screen", ["It is 50% done."])):
            st = _strings()
            st[key] = val
            b = _build(strings=st)
            res.append((b.rc, f"BUILD-ERROR STRINGS-FORBIDDEN {key}" in b.out, b.existed))
        st = _strings()
        st["reactions"][0]["href"] = "https://example.invalid/react?card={card}&t=%20x"
        st["note_href"] = "notes/{file}?x=%20"
        return _eq((res, _build(strings=st).rc), ([(1, True, False)] * 3, 0))

    @case("H1", "a null claim with a reading block (g1a, root bar): the heading shows the Lean name and the no_claim_label (`bar No "
                "plain statement yet`), the statement line tells the fact (`We have read this statement.`; the Evidence line names the "
                "reading block's reader and date), the proof line `We have not read this proof yet.`; the JSON carries the label")
    def _():
        b = _base()
        c = _card(b, "g1a")
        step = b.js("level1.json")["steps"][0]["children"][0]
        return _eq((c.find("h3", "claim")[0].text(), c.find("p", "statement")[0].text(), c.find("p", "proof")[0].text(),
                    step["claim_label"], step["statement_read"], step["proof_read"], "coverage" in step, prov(b, "g1a")),
                   ("bar No plain statement yet", "We have read this statement.", "We have not read this proof yet.",
                    "No plain statement yet", True, False, False, ["Statement read by Reader One on 2026-11-23."]))

    @case("ORD1", "the premises of a card are linked in the order of the outline (g2 then g1), not sorted")
    def _():
        o = _outline()
        o["groups"][0]["premises"] = ["g2", "g1"]
        b = _build(outline=o)
        return _eq((b.rc, [a.attrs["href"] for a in _card(b, "g3").find("p", "premises")[0].find("a")]), (0, ["#g2", "#g1"]))

    # ---- F20: premises belong to the group; F21: open items, evidence labels, code spans; the required placeholders
    def _outline_g2_premises():
        o = _outline()
        next(g for g in o["groups"] if g["id"] == "g2")["premises"] = ["g1a", "g1"]   # outline order; sorted would be g1, g1a
        return o

    @case("PRM1", "premises is a field of the GROUP in level0.json, level1.json and group/<id>.json (a list of group ids in outline order, "
                  "[] when none), and the claim object no longer carries it: g2 (a null claim) has [g1a, g1], g1 [g1a], g3 [g1, g2], g1a [], "
                  "and the keys of g1's claim are basis, conditions, date, reader, text")
    def _():
        b = _build(outline=_outline_g2_premises())
        l0 = {x["id"]: x for x in b.js("level0.json")["steps"]}
        l1 = {x["id"]: x for x in b.js("level1.json")["steps"]}
        gf = {g: b.js(f"group/{g}.json")["premises"] for g in ("g1", "g1a", "g2", "g3")}
        return _eq((b.rc, [l0[g]["premises"] for g in ("g1", "g3", "g2")], [l1[g]["premises"] for g in ("g1", "g3", "g2")],
                    l1["g1"]["children"][0]["premises"], gf, sorted(l0["g1"]["claim"]), sorted(l1["g3"]["claim"]), l0["g2"]["claim"]),
                   (0, [["g1a"], ["g1", "g2"], ["g1a", "g1"]], [["g1a"], ["g1", "g2"], ["g1a", "g1"]], [],
                    {"g1": ["g1a"], "g1a": [], "g2": ["g1a", "g1"], "g3": ["g1", "g2"]},
                    ["basis", "conditions", "date", "reader", "text"], ["basis", "conditions", "date", "reader", "text"], None))

    @case("PRM2", "the premises heading and links show on a null-claim step too: g2 (premises [g1a, g1]) has the `Rests on` paragraph "
                  "right after its heading, with links #g1a (`bar`, a null claim) and #g1 (`Claim one`) in outline order; a card with "
                  "no premises has no premises paragraph, heading included (g2 in the base build, a claimed card g1a1)")
    def _():
        b = _build(outline=_outline_g2_premises())
        c = _card(b, "g2")
        prem = _direct(c, "p", "premises")[0]
        base = _base()
        return _eq(([k.cls[0] for k in c.elems()][:3], _raw(prem), [(a.attrs["href"], a.text()) for a in prem.find("a")],
                    _direct(_card(base, "g2"), "p", "premises"), _direct(_card(base, "g1a1"), "p", "premises")),
                   (["claim", "premises", "status"], "Rests on bar, Claim one", [("#g1a", "bar"), ("#g1", "Claim one")], [], []))

    @case("PRM3", "every premise link of every card, null-claim steps included, resolves to a card of the page; a premise link to an id "
                  "that has no card is a link problem")
    def _():
        b = _build(outline=_outline_g2_premises())
        dom = _dom(b.page)
        ids = {a.attrs["id"] for a in dom.find("article")}
        hrefs = [a.attrs["href"][1:] for p in dom.find("p", "premises") for a in p.find("a")]
        return _eq((b.rc, sorted(hrefs), all(h in ids for h in hrefs), link_problems(b.page),
                    link_problems(b.page.replace('<a href="#g1a">', '<a href="#zzz">', 1))),
                   (0, ["g1", "g1", "g1a", "g1a", "g2"], True, [], ["#zzz"]))

    @case("OPN1", "the card's open-items line is shown only above zero: g2 (one open item) has `Questions written down: 1.`, g1 (none) has no "
                  "such line, and the JSON counts are unchanged (g1 counts open_items 0 and roots_open_items 0, g2 1 and 1)")
    def _():
        b = _base()
        steps = {x["id"]: x["counts"] for x in b.js("level0.json")["steps"]}
        return _eq(([x.text() for x in _card(b, "g2").find("p", "open-items")], _card(b, "g1").find("p", "open-items") != [],
                    len(_dom(b.page).find("p", "open-items")), steps["g1"]["open_items"], steps["g1"]["roots_open_items"],
                    steps["g2"]["open_items"], steps["g2"]["roots_open_items"]),
                   (["Questions written down: 1."], False, 1, 0, 0, 1, 1))

    @case("OPN2", "the first-screen open-items line is ALWAYS shown, zero included: with the one not_read block turned into a reading "
                  "block no card has an open-items line, and the first screen says `Questions written down in these notes: 0.`; "
                  "the JSON totals say 0")
    def _():
        n = _notes()
        n["01-one.md"] = _n01().replace(_b(id="01.b05", kind="not_read", decls=[QUUX], needs="hand_read", row=1),
                                        _b(id="01.b05", kind="reading", decls=[QUUX], reader="Reader One", date="2026-11-23", row=1))
        b = _build(notes=n)
        dom = _dom(b.page)
        return _eq((b.rc, [li.text() for li in dom.find("ul", "facts")[0].find("li")][2], len(dom.find("p", "open-items")),
                    b.js("level0.json")["totals"]["open_items"]), (0, "Questions written down in these notes: 0.", 0, 0))

    @case("EVD1", "the evidence block labels module, name and kind from the strings file like File and Lines: on g1 the labels Module, "
                  "Name, Kind, File, Lines with A.B, foo, theorem, A/B.lean, 10-20; a build whose three keys say other words shows "
                  "those words; with every value a marker the labels are the markers evidence_module_label, evidence_name_label, "
                  "evidence_kind_label")
    def _():
        def pairs(b):
            dl = _card(b, "g1").find("details", "evidence")[0].find("dl")[0]
            return [(t.text(), d.text()) for t, d in zip(dl.find("dt"), dl.find("dd"))]
        st = _strings()
        st["evidence_module_label"], st["evidence_name_label"], st["evidence_kind_label"] = "Lean module", "Declaration", "Sort"
        return _eq((pairs(_base()), pairs(_build(strings=st))[:3], [t for t, _d in pairs(_build(strings=_marked(_strings())))][:3]),
                   ([("Module", "A.B"), ("Name", "foo"), ("Kind", "theorem"), ("File", "A/B.lean"), ("Lines", "10-20")],
                    [("Lean module", "A.B"), ("Declaration", "foo"), ("Sort", "theorem")],
                    ["MARK-evidence_module_label", "MARK-evidence_name_label", "MARK-evidence_kind_label"]))

    @case("EVD2", "a strings file without evidence_module_label, evidence_name_label or evidence_kind_label (or with an empty one) is "
                  "refused as STRINGS-KEY naming the key, exit 1, nothing written")
    def _():
        res = []
        for key in ("evidence_module_label", "evidence_name_label", "evidence_kind_label"):
            st = _strings()
            del st[key]
            b = _build(strings=st)
            e = _strings()
            e[key] = ""
            be = _build(strings=e)
            res.append((b.rc, [x for x in b.out.splitlines() if x.startswith("BUILD-ERROR")], b.existed,
                        be.rc, [x for x in be.out.splitlines() if x.startswith("BUILD-ERROR")]))
        return _eq(res, [(1, [f"BUILD-ERROR STRINGS-KEY {k} missing"], False, 1,
                          [f"BUILD-ERROR STRINGS-KEY {k} must be a non-empty string"])
                         for k in ("evidence_module_label", "evidence_name_label", "evidence_kind_label")])

    def _code_outline(g1_text, g1_cond, g3_text, g1a1_text):
        o = _outline()
        gs = {g["id"]: g for g in o["groups"]}
        gs["g1"]["claim"]["text"], gs["g1"]["claim"]["conditions"] = g1_text, g1_cond
        gs["g3"]["claim"]["text"], gs["g1a1"]["claim"]["text"] = g3_text, g1a1_text
        return o

    @case("CODE1", "in a claim text and in a condition a span between single backticks is rendered as <code>, its content escaped; the "
                   "same claim text as the title of a premise link; in level0.json and data.js the text stays as written, backticks "
                   "included")
    def _():
        o = _code_outline("Use `Foo.bar` and `x < y & z` here.", ["Needs `HypSalt` to hold, and `a` or `b`."], "Claim four with é",
                          "Claim three")
        b = _build(outline=o)
        c = _card(b, "g1")
        got = (b.rc, '<h3 class="claim">Use <code>Foo.bar</code> and <code>x &lt; y &amp; z</code> here.</h3>' in b.page,
               [_raw(x) for x in c.find("h3", "claim")[0].find("code")],
               '<li>Needs <code>HypSalt</code> to hold, and <code>a</code> or <code>b</code>.</li>' in b.page,
               '<a href="#g1">Use <code>Foo.bar</code> and <code>x &lt; y &amp; z</code> here.</a>' in b.page,
               b.js("level0.json")["steps"][0]["claim"]["text"], b.js("level0.json")["steps"][0]["claim"]["conditions"],
               "Use `Foo.bar` and `x \\u003c y \\u0026 z` here." in b.text("data.js"))
        return _eq(got, (0, True, ["Foo.bar", "x < y & z"], True, True, "Use `Foo.bar` and `x < y & z` here.",
                         ["Needs `HypSalt` to hold, and `a` or `b`."], True))

    @case("CODE2", "backticks make code and nothing else: an unpaired backtick, an empty pair, a pair of doubled backticks and a pair "
                   "over a line break stay literal text; `<b>`, `**bold**`, a markdown link and a heading mark in data stay escaped "
                   "text; control: a real span in the same build is code; the built page has no element that the base page has not (so no b, "
                   "strong, em, h1 or new link)")
    def _():
        o = _code_outline("An unpaired `backtick here", ["<b>bold</b> **bold** [l](x) # head", "A `` x `` pair and an empty `` pair"],
                          "Over a line `x\ny` ends", "Bold <b>x</b> and **y** with `ok`")
        b = _build(outline=o)
        dom, base = _dom(b.page), _dom(_base().page)
        t = lambda g: _card(b, g).find("h3", "claim")[0].text()
        return _eq((b.rc, t("g1"), [x.text() for x in _card(b, "g1").find("ul", "conditions")[0].find("li")], t("g3"), t("g1a1"),
                    sorted({n.tag for n in dom.nodes()} - {n.tag for n in base.nodes()}), "<b>" in b.page, "&lt;b&gt;bold&lt;/b&gt;" in b.page,
                    [len(_card(b, g).find("h3", "claim")[0].find("code")) for g in ("g1", "g3", "g1a1")]),
                   (0, "An unpaired `backtick here", ["<b>bold</b> **bold** [l](x) # head", "A `` x `` pair and an empty `` pair"],
                    "Over a line `x y` ends", "Bold <b>x</b> and **y** with ok", [], False, True, [0, 0, 1]))

    @case("CODE3", "the two ends of a span are each decided by a neighbour: a backtick that follows a backtick opens no span "
                   "(`` + a + ` + space + b stays literal, and so does x + two backticks + a + a backtick), and a backtick that "
                   "is followed by a backtick closes none (a backtick, a, two backticks, tail stays literal); control: a real "
                   "span in the same build is code")
    def _():
        o = _code_outline("``a` b", ["A real `ok` span."], "x``a`", "`a`` tail")
        b = _build(outline=o)
        t = lambda g: _card(b, g).find("h3", "claim")[0].text()
        return _eq((b.rc, t("g1"), t("g3"), t("g1a1"), [len(_card(b, g).find("h3", "claim")[0].find("code")) for g in ("g1", "g3", "g1a1")],
                    [x.text() for x in _card(b, "g1").find("ul", "conditions")[0].find("code")],
                    '<h3 class="claim">``a` b</h3>' in b.page, '<h3 class="claim">x``a`</h3>' in b.page,
                    '<h3 class="claim">`a`` tail</h3>' in b.page),
                   (0, "``a` b", "x``a`", "`a`` tail", [0, 0, 0], ["ok"], True, True, True))

    @case("CODE4", "a span does not cross a carriage return either: the claim `a `Foo.bar` + CR + `baz` b` is literal text on the page "
                   "(no <code>), as it is for the checker (it lists Foo.bar); the JSON keeps the text as written")
    def _():
        o = _code_outline("a `Foo.bar\rbaz` b", ["a `x\r\ny` b"], "Claim four with é", "Claim three")
        b = _build(outline=o)
        c = _card(b, "g1")
        return _eq((b.rc, c.find("h3", "claim")[0].text(), len(c.find("h3", "claim")[0].find("code")),
                    [x.text() for x in c.find("ul", "conditions")[0].find("li")], len(c.find("ul", "conditions")[0].find("code")),
                    b.js("level0.json")["steps"][0]["claim"]["text"]),
                   (0, "a `Foo.bar baz` b", 0, ["a `x y` b"], 0, "a `Foo.bar\rbaz` b"))

    @case("AGR1", "the page and the checker agree on which backtick spans are code: for each of ten texts the page puts Foo.bar inside a <code> "
                  "element exactly when notes_meta does not list Foo.bar")
    def _():
        texts = ("`Foo.bar`", "a `Foo.bar` b", "``Foo.bar``", "``Foo.bar` x", "x `Foo.bar`` y", "an unpaired `Foo.bar here",
                 "a `Foo.bar\nbaz` b", "a `Foo.bar\rbaz` b", "`a` and Foo.bar", "`x Foo.bar y`")
        got = [(t, re.search(r"<code>[^<]*Foo\.bar[^<]*</code>", _rich(t)) is not None, "Foo.bar" in nm._library_words(t))
               for t in texts]
        return _eq(got, [("`Foo.bar`", True, False), ("a `Foo.bar` b", True, False), ("``Foo.bar``", False, True),
                         ("``Foo.bar` x", False, True), ("x `Foo.bar`` y", False, True), ("an unpaired `Foo.bar here", False, True),
                         ("a `Foo.bar\nbaz` b", False, True), ("a `Foo.bar\rbaz` b", False, True), ("`a` and Foo.bar", False, True),
                         ("`x Foo.bar y`", True, False)])

    @case("PHR4", "the keys that must hold their placeholders (the counts and the open-items lines, the recognition lines, the citation lines, "
                  "established_by_line, sketch_frame and the eight Evidence keys of F37) are exactly the 27 listed, each declares exactly the "
                  "placeholders it must hold; the card keys of F37 (the read lines, the frames, the label line, the compiled basis) and the "
                  "retired second_reader_frame declare none and require none")
    def _():
        keys = ["statement_count_line", "proof_count_line", "steps_statement_line", "steps_proof_line", "open_items_line", "steps_open_items_line"]
        new = [k for k, _n in _REQ2]
        none_keys = ["statement_read_line", "statement_census_line", "proof_read_line", "argument_frame", "argument_frame_no_proof",
                     "interpretation_frame", "recognition_label_line", "sketch_basis_compiled", "second_reader_frame", "frames.argument"]
        return _eq((sorted(REQUIRED_PLACEHOLDERS), [set(REQUIRED_PLACEHOLDERS[k]) == PLACEHOLDERS[k] for k in keys + new],
                    [PLACEHOLDERS.get(k, set()) for k in none_keys], [k in REQUIRED_PLACEHOLDERS for k in none_keys]),
                   (sorted(keys + new), [True] * 27, [set()] * 10, [False] * 10))

    _REQ = (("statement_count_line", ("n", "m")), ("proof_count_line", ("n", "m")),
            ("steps_statement_line", ("n", "m")), ("steps_proof_line", ("n", "m")), ("open_items_line", ("n",)),
            ("steps_open_items_line", ("n",)))

    @case("PHR1", "each of the six keys statement_count_line, proof_count_line, steps_statement_line, steps_proof_line, open_items_line, "
                  "steps_open_items_line that lacks one of its placeholders ({n} {m}, or {n}) is refused as STRINGS-KEY naming the key "
                  "and the placeholder (10 cases), exit 1, nothing written; control: the fixture with every placeholder builds")
    def _():
        res = []
        for key, names in _REQ:
            for name in names:
                st = _strings()
                st[key] = st[key].replace("{" + name + "}", "")
                b = _build(strings=st)
                res.append((key, name, b.rc, [x for x in b.out.splitlines() if x.startswith("BUILD-ERROR")], b.existed))
        want = [(k, n, 1, [f"BUILD-ERROR STRINGS-KEY {k} is missing the placeholder {{{n}}}"], False) for k, ns in _REQ for n in ns]
        return _eq((res, len(res), _base().rc), (want, 10, 0))

    @case("PHR2", "the placeholders of the other keys stay optional: shared_note, note_href and reactions[0].href with no placeholder at all "
                  "build (the frames and the read lines of the card declare none since F37, see PHR4)")
    def _():
        res = []
        for path, value in (("shared_note", "Also a root elsewhere."), ("note_href", "notes/index.md"),
                            ("reactions[0].href", "https://example.invalid/react?kind=sense")):
            st = _strings()
            node = st
            parts = re.findall(r"[^.\[\]]+", path)
            for part in parts[:-1]:
                node = node[int(part)] if part.isdigit() else node[part]
            node[int(parts[-1]) if parts[-1].isdigit() else parts[-1]] = value
            b = _build(strings=st)
            res.append((path, b.rc, [x for x in b.out.splitlines() if x.startswith("BUILD-ERROR")]))
        return _eq(res, [(p_, 0, []) for p_ in ("shared_note", "note_href", "reactions[0].href")])

    @case("PHR3", "the strings file of this checkout (site/strings.json) has none of the nine required placeholders missing")
    def _():
        path = os.path.join(_HERE, os.pardir, "site", "strings.json")
        if not os.path.isfile(path):
            raise _SkipCase("no real strings file in this checkout")
        with open(path, encoding="utf-8") as f:
            real = json.load(f)
        return _eq([x for x in _strings_problems(real) if "is missing the placeholder" in x[2]], [])

    @case("SHA1", "--release-archive-sha is stored in lower case: an upper-case input gives the same manifest as the lower-case one")
    def _():
        up, lo = _build(archive="AB" * 32), _build(archive="ab" * 32)
        return _eq((up.rc, up.files["manifest.json"] == lo.files["manifest.json"], up.js("manifest.json")["release_archive_sha"]),
                   (0, True, "ab" * 32))

    @case("JS1", "data.js writes < > & U+2028 U+2029 as \\uXXXX like the canonical comment: a claim holding `</script>` appears "
                 "escaped in data.js, none of the five characters is raw in it, and it parses back equal")
    def _():
        o = _outline()
        o["groups"][2]["claim"]["text"] = "Claim </script> & more\u2028 x\u2029"
        b = _build(outline=o)
        js = b.text("data.js")
        data = json.loads(js[len("window.RH_DATA = "):-2])
        return _eq((b.rc, "Claim \\u003c/script\\u003e \\u0026 more\\u2028 x\\u2029" in js, [c in js for c in "<>&\u2028\u2029"],
                    data["level0"]["steps"][0]["claim"]["text"], data["level0"] == b.js("level0.json")),
                   (0, True, [False] * 5, "Claim </script> & more\u2028 x\u2029", True))

    @case("DIRTY2", "an uncommitted edit of decls.tsv alone stamps `dirty` in all three ids (the table is judged as the notes, "
                    "the outline and the strings are); the unedited tree has the commit")
    def _():
        if shutil.which("git") is None:
            raise _SkipCase("no git program")
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            _git(d, "init", "-q")
            _git(d, "add", "-A")
            _git(d, "commit", "-q", "-m", "base")
            head = _git(d, "rev-parse", "HEAD")
            res = []
            for edit in (False, True):
                if edit:
                    with open(p["decls"], "a", encoding="utf-8") as f:
                        f.write("# an edit\n")
                shutil.rmtree(p["out"], ignore_errors=True)
                rc, _o, _e = _go(p, notes_commit="HEAD", repo=d)
                res.append((rc, json.load(open(os.path.join(p["out"], "level0.json")))["commits"]["notes"]))
            return _eq(res, [(0, head), (0, "dirty")])

    @case("ESC1", "the hostile text `</script><img src=x onerror=alert(1)>\"'&`<b>%41` + U+2028 in every place data or strings reach "
                  "the page (claim, condition, premise title, note title, reader, date, second reader and date, a declaration name, "
                  "argument text, every strings key and label, the href templates): the built page has no script, img or b element, "
                  "no attribute named on..., no raw `</script`, `<img`, `<b>`; the escaped form is there and each place reads back as "
                  "the hostile text; data.js has none of < > & U+2028 U+2029 raw and parses back equal")
    def _():
        quux = _d("A.F", "quux" + HOST)
        with _patched("QUUX", quux):
            o = _outline()
            n = _notes()
            n["01-one.md"] = _n01(arg_text="Hostile text " + HOST + " ends here. More.", host=HOST)
        o["groups"][2]["claim"]["text"] = "Claim " + HOST
        o["groups"][2]["claim"]["conditions"] = [HOST]
        decls = DECLS.replace("A.F\tquux\t", "A.F\tquux" + HOST + "\t")
        b = _build(outline=o, notes=n, decls=decls, strings=_hostile(_strings()))
        if b.rc != 0:
            return False, b.out + b.err
        dom = _dom(b.page)
        g1, g3 = _card(b, "g1"), _card(b, "g3")
        prem = [(a.attrs["href"], _raw(a)) for a in g3.find("p", "premises")[0].find("a")]
        ev_ = g1.find("details", "evidence")[0]
        full = next(li for li in ev_.find("ul", "blocks")[0].elems() if "01.b02" in _raw(li))   # F37: the reader, date and second reader moved here
        corr = _direct(g1, "ul", "corrections")[0].find("li")[0]
        react = g1.find("a", "reaction")[0].attrs["href"]
        js = b.text("data.js")
        got = (sorted({n_.tag for n_ in dom.nodes()} & {"script", "img", "b"}),
               [k for n_ in dom.nodes() for k in n_.attrs if k.startswith("on")],
               [t in b.page for t in ("</script", "<img", "<b>")], ESC in b.page, ESC_S in b.page,
               _raw(g1.find("h3", "claim")[0]), [_raw(li) for li in g1.find("ul", "conditions")[0].find("li")], prem,
               [_raw(a) for a in _direct(g1, "ul", "notes")[0].find("a")], _raw(full).count(HOST), _raw(corr).count(HOST),
               react, _raw(dom.find("header")[0].find("p")[0]), _raw(_card(b, "g2").find("h3", "claim")[0]).count("quux" + HOST),
               [c in js for c in "<>&\u2028\u2029"],
               json.loads(js[len("window.RH_DATA = "):-2])["groups"]["g1"] == b.js("group/g1.json"),
               _raw(ev_.find("ul", "provenance")[0]).count(HOST),
               _raw(next(li for li in ev_.find("ul", "blocks")[0].elems() if "01.b06" in _raw(li))).count(HOST))
        want = ([], [], [False, False, False], True, True, "Claim " + HOST, [HOST],
                [("#g1", "Claim " + HOST), ("#g2", "quux" + HOST)], ["T " + HOST, "Note two"], 5, 1,
                "https://example.invalid/react?card=g1&kind=sense" + HOST, "First screen paragraph one. " + HOST_S, 1,
                [False] * 5, True, 2, 2)
        return _eq(got, want)

    # ---- F19: the two facts
    @case("F2a", "level0.json per step: counts {roots, roots_statement_read, roots_proof_read, roots_proof_applicable, roots_open_items, "
                 "open_items} (g1: 1, 1, 1, 1, 0, 0; g3: 1, 0, 0, 1, 0, 0; g2: 2, 1, 0, 2, 1, 1) with no key that holds `not_read`; claim.basis is the effective value "
                 "(g1 `read` as written, g3 `census`, g1a1 `read` although the file has none); no `coverage` key; level0 `facts`")
    def _():
        b = _base()
        l0 = b.js("level0.json")
        steps = {x["id"]: x for x in l0["steps"]}
        g1a1 = b.js("level1.json")["steps"][0]["children"][0]["children"][0]
        return _eq(([steps[g]["counts"] for g in ("g1", "g3", "g2")], [k for x in steps.values() for k in x["counts"] if "not_read" in k],
                    [steps["g1"]["claim"]["basis"], steps["g3"]["claim"]["basis"], g1a1["claim"]["basis"]],
                    ["coverage" in x for x in steps.values()], l0["facts"], "route" in l0),
                   ([{"roots": 1, "roots_statement_read": 1, "roots_proof_read": 1, "roots_proof_applicable": 1, "roots_open_items": 0,
                      "open_items": 0},
                     {"roots": 1, "roots_statement_read": 0, "roots_proof_read": 0, "roots_proof_applicable": 1, "roots_open_items": 0,
                      "open_items": 0},
                     {"roots": 2, "roots_statement_read": 1, "roots_proof_read": 0, "roots_proof_applicable": 2, "roots_open_items": 1,
                      "open_items": 1}],
                    [], ["read", "census", "read"], [False] * 3,
                    {"proof_applicable": 3, "proof_not_applicable": 0, "proof_not_read": 2, "proof_read": 1, "statement_not_read": 2,
                     "statement_read": 1, "steps": 3}, False))

    @case("F3a", "a stale strings file is refused naming the key: `coverage`, `not_read_yet`, `roots_not_read`, `roots_not_read_note`; the "
                 "two status keys (statement_not_read_line, proof_not_read_line) are allowed (the base builds)")
    def _():
        res = []
        for key, val in (("coverage", [{"when": {"read_all": True}, "word": "All"}]), ("not_read_yet", "x"), ("roots_not_read", "{N}"),
                         ("roots_not_read_note", "x")):
            st = _strings()
            st[key] = val
            b = _build(strings=st)
            res.append((b.rc, f"BUILD-ERROR STRINGS-KEY {key} " in b.out, b.existed))
        return _eq((res, _base().rc), ([(1, True, False)] * 4, 0))

    @case("F3b", "a strings value holding one of the retired words `Read by us`, `Partly read`, `Not read yet` is STRINGS-FORBIDDEN naming "
                 "the key; the built page and data.js hold none of the three")
    def _():
        res = []
        for w in ("Read by us", "Partly read", "Not read yet"):
            st = _strings()
            st["first_screen"] = [f"The page says {w} here."]
            b = _build(strings=st)
            res.append((b.rc, "BUILD-ERROR STRINGS-FORBIDDEN first_screen[0] " in b.out, b.existed))
        every = _base().page + _base().text("data.js")
        return _eq((res, [w in every for w in ("Read by us", "Partly read", "Not read yet")]), ([(1, True, False)] * 3, [False] * 3))

    @case("C1", "the status lines of the cards (statement, proof; the open-items line is absent at 0) say the fact and name nobody (F37): g1 "
                "`We have read this statement.`, `We have read this proof.`; g1a the statement read (by its reading block), proof not read; g1a1x the "
                "statement read, proof not read; g3 the census line, `We have not read this proof yet.`; the Evidence line of each says who and "
                "when: g1 the claim's reader and date (not the reading block's) and the first argument block's, g1a and g1a1x the reading block's, "
                "g3 the claim's, counted by a program")
    def _():
        b = _base()
        line = lambda g: [c.text() for c in (_card(b, g).find("p", "statement")[0], _card(b, g).find("p", "proof")[0])]
        return _eq(([line(g) for g in ("g1", "g1a", "g1a1x", "g3")],
                    [len(_card(b, g).find("p", "open-items")) for g in ("g1a", "g1a1x", "g3")]),
                   ([["We have read this statement.", "We have read this proof."],
                     ["We have read this statement.", "We have not read this proof yet."],
                     ["We have read this statement.", "We have not read this proof yet."],
                     ["We have not read this statement: what it says here comes from a program's count of its parts.",
                      "We have not read this proof yet."]], [0, 0, 0]))

    @case("C1b", "F37: the Evidence section says who read what and when for the cards of C1: g1 `Statement read by Reader One on 2026-11-20.` "
                 "and `Proof read by Reader One on 2026-11-23.`; g1a and g1a1x the reading block's reader and date; g3 the census line")
    def _():
        b = _base()
        return _eq([prov(b, g) for g in ("g1", "g1a", "g1a1x", "g3")],
                   [["Statement read by Reader One on 2026-11-20.", "Proof read by Reader One on 2026-11-23."],
                    ["Statement read by Reader One on 2026-11-23."], ["Statement read by Reader Two on 2026-11-23."],
                    ["Statement counted by a program, not read, recorded by Reader One on 2026-11-20."]])

    @case("C2", "the line open_items_line comes from its key and shows the number and never `not read` (the fixture value holds none): "
                "on g2 `Questions written down: 1.`; a build whose key says `Open: {n} questions` shows `Open: 1 questions` on g2")
    def _():
        st = _strings()
        st["open_items_line"] = "Open: {n} questions"
        b = _build(strings=st)
        return _eq(("not read" in _strings()["open_items_line"].lower(), _card(_base(), "g2").find("p", "open-items")[0].text(),
                    _card(b, "g2").find("p", "open-items")[0].text()), (False, "Questions written down: 1.", "Open: 1 questions"))

    @case("PRO1", "a null-claim step with three roots (quux, qux, corge) and argument blocks on two of them: the step does NOT count for "
                  "the proof (a step counts when EVERY root has the fact), the card counts `Proofs read: 2 of 3 declarations.`, "
                  "roots_proof_read is 2 and facts.proof_read stays 1 (g1)")
    def _():
        o = _outline()
        o["groups"][3]["roots"] = [QUUX, QUX, CORGE]
        n03 = (N03 + "\nArgues quux.\n" + _b(id="03.b01", kind="argument", decls=[QUUX], reader="Reader Two", date="2026-11-23")
               + "\n\nArgues qux.\n" + _b(id="03.b02", kind="argument", decls=[QUX], reader="Reader Two", date="2026-11-23") + "\n")
        b = _build(outline=o, notes=_notes() | {"03-three.md": n03})
        g2 = [x for x in b.js("level0.json")["steps"] if x["id"] == "g2"][0]
        return _eq((b.rc, g2["proof_read"], g2["counts"]["roots_proof_read"], b.js("level0.json")["facts"]["proof_read"],
                    _card(b, "g2").find("p", "proof")[0].text()), (0, False, 2, 1, "Proofs read: 2 of 3 declarations."))

    @case("ZERO1", "the model with a group that has NO root (called directly: the checker refuses it first in a run): it is never "
                   "counted as read (statement_read and proof_read False, unread True, counts roots 0) and FACTS-NO-ROOT names it; "
                   "the guard is redundant by design")
    def _():
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d)
            odata = json.load(open(p["outline"]))
            odata["groups"].append(_g("gz", 1, "root", 9, []))
            errors = []
            m = _model(p["notes"], odata, _decl_rows(p["decls"]), _strings(), None, errors)
            z = m.summary["gz"]
            return _eq((z["statement_read"], z["proof_read"], z["unread"], z["counts"]["roots"], z["lean_name"], errors),
                       (False, False, True, 0, None, [("FACTS-NO-ROOT", "gz", "group has no root, so no fact claim")]))

    @case("RET1", "the retired-word check is an exact-case, single-space match: `not read yet.` ships, `Not read yet.` is refused "
                  "and the refusal says `exact-case match; the lowercase phrase `not read yet` is allowed inside status wording`")
    def _():
        ok_ = _strings()
        ok_["statement_not_read_line"] = "not read yet."
        bad_ = _strings()
        bad_["statement_not_read_line"] = "Not read yet."
        a, b = _build(strings=ok_), _build(strings=bad_)
        msg = ("BUILD-ERROR STRINGS-FORBIDDEN statement_not_read_line holds 'Not read yet', a word of the retired coverage scale "
               "(exact-case match; the lowercase phrase `not read yet` is allowed inside status wording)")
        return _eq((a.rc, b.rc, msg in b.out.splitlines(), b.existed), (0, 1, True, False))

    @case("RDR1", "a root with two reading blocks in different notes: the statement reader is the first by NOTE ID then block number, "
                  "not by date: g1a (root bar) has 01.b04 (Reader One, 2026-11-23) and 03.b01 (Reader Three, 2026-11-01); the "
                  "Evidence line names Reader One on 2026-11-23 although the other date is earlier (the card line names nobody)")
    def _():
        n03 = N03 + "\nAlso read.\n" + _b(id="03.b01", kind="reading", decls=[BAR], reader="Reader Three", date="2026-11-01") + "\n"
        b = _build(notes=_notes() | {"03-three.md": n03})
        return _eq((b.rc, prov(b, "g1a"), b.js("level1.json")["steps"][0]["children"][0]["statement_by"]),
                   (0, ["Statement read by Reader One on 2026-11-23."],
                    {"date": "2026-11-23", "reader": "Reader One", "source": "block"}))

    @case("ORG1", "a PAGE-STATIC finding is attributed to the strings key that holds the offending token: note_href `http://...` "
                  "(a plain link to a URL) is named, not the first https value (reactions[0].href)")
    def _():
        st = _strings()
        st["note_href"] = "http://example.invalid/{file}"
        b = _build(strings=st)
        return _eq((b.rc, "BUILD-ERROR PAGE-STATIC href=http found in strings key note_href" in b.out.splitlines(), b.existed),
                   (1, True, False))

    @case("PRF1", "the proof line says `We have read this proof.` and the Evidence line is filled from the argument block of the root: g1 "
                  "`Proof read by Reader One on 2026-11-23.` (01.b02) and, with an argument block by Reader Two on 2026-11-23 on qux, g1a1x "
                  "`Proof read by Reader Two on 2026-11-23.`; no brace character from the strings file is anywhere in the page text")
    def _():
        n03 = N03 + "\nArgues qux.\n" + _b(id="03.b01", kind="argument", decls=[QUX], reader="Reader Two", date="2026-11-23") + "\n"
        b = _build(notes=_notes() | {"03-three.md": n03})
        text = " ".join(_page_text(b.page))
        return _eq((b.rc, _card(b, "g1a1x").find("p", "proof")[0].text(), prov(b, "g1a1x")[1], prov(b, "g1")[1],
                    "{" in text, "}" in text),
                   (0, "We have read this proof.", "Proof read by Reader Two on 2026-11-23.", "Proof read by Reader One on 2026-11-23.",
                    False, False))

    @case("PRF2", "two argument blocks on one root in different notes where the note order disagrees with the date order: g1 (root foo) has "
                  "01.b02 (Reader One, 2026-11-23) and 03.b01 (Reader Three, 2026-11-01); the Evidence proof line names the "
                  "first by note id then block number, Reader One on 2026-11-23, not the earlier date, and the idea is that block's")
    def _():
        n03 = N03 + "\nArgues foo.\n" + _b(id="03.b01", kind="argument", decls=[FOO], reader="Reader Three", date="2026-11-01") + "\n"
        b = _build(notes=_notes() | {"03-three.md": n03})
        c = _card(b, "g1")
        return _eq((b.rc, prov(b, "g1")[1], _direct(c, "p", "argument")[0].text().startswith("How this is proved: First argument sentence.")),
                   (0, "Proof read by Reader One on 2026-11-23.", True))

    @case("PH1", "a `{bogus}` planted in statement_not_read_line, in a frames phrase, in a reactions label, in a first_screen paragraph "
                 "and in a reaction href is refused naming the key and the token (`has an unknown placeholder {bogus}`); a key that "
                 "declares none (mapped_line) refuses any brace; a brace-free value builds; an evidence_proof_read_line with only {reader} "
                 "is refused (it lacks {date}) and so is one with none (it lacks both), see PHR1")
    def _():
        res = []
        for path in ("statement_not_read_line", "frames.argument[0]", "reactions[0].label", "first_screen[0]", "reactions[0].href"):
            st = _strings()
            node = st
            parts = re.findall(r"[^.\[\]]+", path)
            for part in parts[:-1]:
                node = node[int(part)] if part.isdigit() else node[part]
            last = int(parts[-1]) if parts[-1].isdigit() else parts[-1]
            node[last] = node[last] + " {bogus}"
            b = _build(strings=st)
            res.append((b.rc, f"BUILD-ERROR STRINGS-KEY {path} has an unknown placeholder {{bogus}}" in b.out.splitlines(), b.existed))
        brace = _strings()
        brace["mapped_line"] = "A set { x } line."
        bb = _build(strings=brace)
        one, none = _strings(), _strings()
        one["evidence_proof_read_line"], none["evidence_proof_read_line"] = "Proof read by {reader}.", "Proof read."
        b1, b0 = _build(strings=one), _build(strings=none)
        err = lambda b: [x for x in b.out.splitlines() if x.startswith("BUILD-ERROR")]
        return _eq((res, bb.rc, "BUILD-ERROR STRINGS-KEY mapped_line holds a brace" in bb.out, _base().rc, err(b1), err(b0)),
                   ([(1, True, False)] * 5, 1, True, 0,
                    ["BUILD-ERROR STRINGS-KEY evidence_proof_read_line is missing the placeholder {date}"],
                    ["BUILD-ERROR STRINGS-KEY evidence_proof_read_line is missing the placeholder {reader}",
                     "BUILD-ERROR STRINGS-KEY evidence_proof_read_line is missing the placeholder {date}"]))

    @case("PH2", "the built page text (tags stripped, script and style removed) holds no `{name}` token from the strings file, in the base "
                 "build and in a build whose notes give every status line a reader")
    def _():
        n03 = N03 + "\nArgues qux.\n" + _b(id="03.b01", kind="argument", decls=[QUX], reader="Reader Two", date="2026-11-23") + "\n"
        pat = re.compile(r"\{[A-Za-z_]\w*\}")
        texts = [" ".join(_page_text(_base().page)), " ".join(_page_text(_build(notes=_notes() | {"03-three.md": n03}).page))]
        return _eq([pat.search(t) for t in texts], [None, None])

    @case("OI1", "one not_read block that anchors two groups (03.b01 on foo in g1 and bar in g1a): each card counts 1, totals.open_items "
                 "counts it once (2 with 01.b05); roots_open_items 1 on each")
    def _():
        n03 = N03 + "\nShared question.\n" + _b(id="03.b01", kind="not_read", decls=[FOO, BAR], needs="hand_read") + "\n"
        b = _build(notes=_notes() | {"03-three.md": n03})
        c = {g: [x for x in b.js("level0.json")["steps"] if x["id"] == g][0]["counts"] for g in ("g1",)}
        g1a = b.js("level1.json")["steps"][0]["children"][0]["counts"]
        return _eq((c["g1"]["open_items"], c["g1"]["roots_open_items"], g1a["open_items"], g1a["roots_open_items"],
                    b.js("level0.json")["totals"]["open_items"], _card(b, "g1").find("p", "open-items")[0].text(),
                    "Questions written down in these notes: 2." in b.page), (1, 1, 1, 1, 2, "Questions written down: 1.", True))

    @case("OI2", "two not_read blocks on one root (corge, g3): the card counts 2 blocks, roots_open_items is 1, totals.open_items 3")
    def _():
        n03 = (N03 + "\nFirst question.\n" + _b(id="03.b01", kind="not_read", decls=[CORGE], needs="hand_read")
               + "\n\nSecond question.\n" + _b(id="03.b02", kind="not_read", decls=[CORGE], needs="callers") + "\n")
        b = _build(notes=_notes() | {"03-three.md": n03})
        c = [x for x in b.js("level0.json")["steps"] if x["id"] == "g3"][0]["counts"]
        return _eq((c["open_items"], c["roots_open_items"], b.js("level0.json")["totals"]["open_items"],
                    _card(b, "g3").find("p", "open-items")[0].text()), (2, 1, 3, "Questions written down: 2."))

    @case("OI3", "the base build: totals.open_items 1 (01.b05 on quux), g2's card 1 and its roots_open_items 1, g1's card has no open-items "
                 "line (a zero is not printed on a card); an argument block is not an open item")
    def _():
        b = _base()
        l0 = b.js("level0.json")
        return _eq((l0["totals"]["open_items"], [x for x in l0["steps"] if x["id"] == "g2"][0]["counts"]["roots_open_items"],
                    len(_card(b, "g1").find("p", "open-items")), _card(b, "g2").find("p", "open-items")[0].text()),
                   (1, 1, 0, "Questions written down: 1."))

    @case("BAS1", "the builder's line `claim basis: 1 read, 1 census, 1 without (treated as read)` and the checker's line `claim basis: 1 "
                  "read, 1 census, 1 without` agree on the counts; with every basis written the builder's line has no parenthesis "
                  "and the two lines are the same")
    def _():
        a = _base().out.splitlines()
        o = _outline()
        o["groups"][5]["claim"]["basis"] = "read"
        b2 = _build(outline=o).out.splitlines()
        nums = lambda ln: re.findall(r"\d+", ln)
        la = [ln for ln in a if ln.startswith("claim basis:")]
        lb = [ln for ln in b2 if ln.startswith("claim basis:")]
        return _eq((la, nums(la[0]) == nums(la[1]), lb), (["claim basis: 1 read, 1 census, 1 without",
                                                           "claim basis: 1 read, 1 census, 1 without (treated as read)"], True,
                                                          ["claim basis: 2 read, 1 census, 0 without"] * 2))

    @case("HREF1", "a reaction href template that is not an https URL (http, mailto:, javascript:, a bare path) is refused naming "
                   "reactions[1].href, exit 1, nothing written; control: https builds")
    def _():
        res = []
        for h in ("http://example.invalid/r?c={card}", "mailto:x@example.invalid?subject={card}", "javascript:alert({card})",
                  "/issues/new?title={card}"):
            st = _strings()
            st["reactions"][1]["href"] = h
            b = _build(strings=st)
            res.append((b.rc, "BUILD-ERROR STRINGS-KEY reactions[1].href " in b.out, b.existed))
        return _eq((res, _base().rc), ([(1, True, False)] * 4, 0))

    @case("HREF2", "the hrefs are exempt from the forbidden words: an href holding `riemann-explained` builds; a reaction LABEL holding "
                   "`explained` and a first_screen paragraph holding `explained` are still refused naming their key")
    def _():
        st = _strings()
        st["reactions"][0]["href"] = "https://example.invalid/riemann-explained/issues/new?title={card}"
        st["note_href"] = "notes/{file}?from=riemann-explained"
        ok_ = _build(strings=st)
        st2 = _strings()
        st2["reactions"][0]["label"] = "This is explained"
        st3 = _strings()
        st3["first_screen"] = ["It is explained here."]
        b2, b3 = _build(strings=st2), _build(strings=st3)
        return _eq((ok_.rc, b2.rc, "BUILD-ERROR STRINGS-FORBIDDEN reactions[0].label " in b2.out, b3.rc,
                    "BUILD-ERROR STRINGS-FORBIDDEN first_screen[0] " in b3.out), (0, 1, True, 1, True))

    # ---- K: the source lines of copied text, before they are joined
    other = "theorem not_in_the_release_at_all : 2 + 2 = 4 := rfl"
    srcs = {"A/B.lean": "x = 1\n" + LEAK + "\n"}
    narrow = "no output line equals a release line and no line of copied note text equals one; a release line quoted inside a longer sentence is not detected"
    leak_line = lambda where: f"BUILD-ERROR SOURCE-LEAK {where} holds a line of the release"

    @case("PJ1", "the defect: an argument block's paragraph of two lines whose SECOND line is a line of the release is joined into "
                 "one longer output line that B1 does not see; the source lines are checked before the join: SOURCE-LEAK naming "
                 "note 01 and block 01.b02 (not the line), exit 1, OUT_DIR absent; control: the same paragraph with another "
                 "second line builds")
    def _():
        planted = _build(notes=_notes(arg_text="First argument sentence.\n" + LEAK), src=srcs)
        control = _build(notes=_notes(arg_text="First argument sentence.\n" + other), src=srcs)
        found = [ln for ln in planted.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK")]
        return _eq((planted.rc, found, LEAK in planted.out, planted.existed, control.rc, control.existed),
                   (1, [leak_line("note 01 block 01.b02")], False, False, 0, True))

    @case("PJ2", "the same for an INTERPRETATION block (01.b03): SOURCE-LEAK naming note 01 and block 01.b03; control builds")
    def _():
        planted = _build(notes=_notes() | {"01-one.md": _n01(interp_text="We think this holds.\n" + LEAK)}, src=srcs)
        control = _build(notes=_notes() | {"01-one.md": _n01(interp_text="We think this holds.\n" + other)}, src=srcs)
        found = [ln for ln in planted.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK")]
        return _eq((planted.rc, found, planted.existed, control.rc, control.existed),
                   (1, [leak_line("note 01 block 01.b03")], False, 0, True))

    @case("PJ3", "a note title (a header field) whose second line is a release line: SOURCE-LEAK naming note 02 and the field "
                 "list_title, exit 1; control builds")
    def _():
        t = N02.replace('"list_title":"Note two"', '"list_title":"Note two\\n' + LEAK + '"')
        c = N02.replace('"list_title":"Note two"', '"list_title":"Note two\\n' + other + '"')
        planted = _build(notes=_notes() | {"02-two.md": t}, src=srcs)
        control = _build(notes=_notes() | {"02-two.md": c}, src=srcs)
        found = [ln for ln in planted.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK note ")]
        return _eq((planted.rc, found, planted.existed, control.rc), (1, [leak_line("note 02 field list_title")], False, 0))

    @case("PJ4", "a claim with a newline whose second line is a release line is a leak, found line by line in level0.json, "
                 "level1.json, data.js and index.html (the split at newlines is what finds it); the same claim without a release "
                 "line builds")
    def _():
        res = []
        for second in (LEAK, other):
            o = _outline()
            o["groups"][0]["claim"]["text"] = "Claim four\n" + second
            b = _build(outline=o, src=srcs)
            res.append((b.rc, sorted(ln.split(" ")[2] for ln in b.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK "))))
        return _eq(res, [(1, ["data.js", "index.html", "level0.json", "level1.json"]), (0, [])])

    @case("PJ5", "the run says what the second check ranged over: `source check (copied note text): K copied source lines, L "
                 "leaked; <the narrow claim>`, K counted by the tool (the base build: 4 titles + 1 argument line + 1 "
                 "interpretation line = 6; the two-line argument paragraph, planted or control: 7); the first source-check line "
                 "is unchanged")
    def _():
        line = lambda k, n: f"source check (copied note text): {k} copied source lines, {n} leaked; {narrow}"
        planted = _build(notes=_notes(arg_text="First argument sentence.\n" + LEAK), src=srcs)
        control = _build(notes=_notes(arg_text="First argument sentence.\n" + other), src=srcs)
        return _eq((line(6, 0) in _base_src().out.splitlines(), line(7, 1) in planted.out.splitlines(),
                    line(7, 0) in control.out.splitlines(),
                    any(ln.startswith("source check: 1 release files, ") for ln in planted.out.splitlines())),
                   (True, True, True, True))

    @case("PJ6", "a source line of fewer than 20 non-space characters that is also a release line (`x = 1`) is not a leak: the "
                 "paragraph builds")
    def _():
        b = _build(notes=_notes(arg_text="First argument sentence.\nx = 1"), src=srcs)
        return _eq((b.rc, b.existed), (0, True))

    @case("WN4", "`of the proof` in the notes' own text is listed only after a number, a percent sign or a quantity word: titles "
                 "`The shape of the proof` and `The top of the proof` are not listed; a claim `Most of the proof is routine` and a "
                 "condition `Only 50 of the proof steps` are; the strings file is still refused for `The shape of the proof`")
    def _():
        o = _outline()
        o["groups"][0]["claim"]["text"] = "Most of the proof is routine"
        o["groups"][2]["claim"]["conditions"] = ["Only 50 of the proof steps"]
        n02 = N02.replace('"list_title":"Note two"', '"list_title":"The shape of the proof"')
        n03 = N03.replace('"list_title":"Note three"', '"list_title":"The top of the proof"')
        b = _build(outline=o, notes=_notes() | {"02-two.md": n02, "03-three.md": n03})
        st = _strings()
        st["mapped_line"] = "The shape of the proof"
        refused = _build(strings=st)
        return _eq((b.rc, [ln for ln in b.out.splitlines() if ln.startswith("WORD-NOTE")], refused.rc,
                    "BUILD-ERROR STRINGS-FORBIDDEN mapped_line" in refused.out),
                   (0, ["WORD-NOTE g1.conditions[0] of the proof", "WORD-NOTE g3.claim of the proof"], 1, True))

    # ---- F22: a definition has no proof to read (a proof needs a theorem or a lemma)
    NA_LINE = "Proof: none to read, this is not a theorem."
    ARG_QUX = N03 + "\nArgues qux.\n" + _b(id="03.b01", kind="argument", decls=[QUX], reader="Reader Two", date="2026-11-23") + "\n"
    ARG_CORGE = N03 + "\nArgues corge.\n" + _b(id="03.b01", kind="argument", decls=[CORGE], reader="Reader Two", date="2026-11-23") + "\n"
    facts_line = lambda b_: [li.text() for li in _dom(b_.page).find("ul", "facts")[0].find("li")]
    step_of = lambda b_, g: [x for x in b_.js("level0.json")["steps"] if x["id"] == g][0]

    @case("PRK1", "the kind of the root decides whether there is a proof: a root whose table kind is `theorem` or `lemma` has one, any "
                  "other kind (def, structure, instance, abbrev, class, inductive) has none; with an argument block on the root (which "
                  "would read the proof if there were one) the root's proof_read and the step's are true for theorem and lemma and NULL "
                  "(not false) for the six others; the build passes and lists nothing for a known kind")
    def _():
        res = []
        for kind in ("theorem", "lemma", "def", "structure", "instance", "abbrev", "class", "inductive"):
            b = _build(decls=_decls_kinds({"corge": kind}), notes=_notes() | {"03-three.md": ARG_CORGE})
            r = b.js("group/g3.json")["roots"][0]
            res.append((kind, b.rc, r["kind"], r["proof_read"], step_of(b, "g3")["proof_read"],
                        [ln for ln in b.out.splitlines() if ln.startswith("KIND-NOTE")]))
        return _eq(res, [(k, 0, k, v, v, []) for k, v in (("theorem", True), ("lemma", True), ("def", None), ("structure", None),
                                                          ("instance", None), ("abbrev", None), ("class", None), ("inductive", None))])

    @case("PRK2", "a root whose kind is not one of the eight the table holds (`axiom`) or is empty has no proof (null) AND is listed: one "
                  "`KIND-NOTE g3 A.G.corge kind 'axiom'` (or `kind ''`) line on stdout, exit unchanged, nothing refused; the group "
                  "and the step carry null")
    def _():
        res = []
        for kind in ("axiom", ""):
            b = _build(decls=_decls_kinds({"corge": kind}), notes=_notes() | {"03-three.md": ARG_CORGE})
            res.append((kind, b.rc, b.js("group/g3.json")["roots"][0]["proof_read"], step_of(b, "g3")["proof_read"],
                        [ln for ln in b.out.splitlines() if ln.startswith("KIND-NOTE")]))
        return _eq(res, [("axiom", 0, None, None, ["KIND-NOTE g3 A.G.corge kind 'axiom'"]),
                         ("", 0, None, None, ["KIND-NOTE g3 A.G.corge kind ''"])])

    @case("DEF1", "a top-level step that is a definition (corge, g3) has no proof: its proof_read is null in level0.json, level1.json and "
                  "group/g3.json (written `null`, never `false`), its counts say roots_proof_applicable 0, its card shows the not-applicable "
                  "line, the card is still `unread` (statement not read AND proof not applicable); the facts count it apart (proof read 1 + "
                  "not read 1 + not applicable 1 = 3, applicable 2), the run prints the three-term check line, and the first screen counts "
                  "over the steps that have a proof: `Proofs read: 1 of 2 steps.`; in the base build g1a1 (baz, a def) shows the "
                  "not-applicable line too")
    def _():
        b = _build(decls=_decls_kinds({"corge": "def"}))
        l0, g3 = b.js("level0.json"), step_of(b, "g3")
        l1 = {x["id"]: x for x in b.js("level1.json")["steps"]}
        return _eq((b.rc, [step_of(b, g)["proof_read"] for g in ("g1", "g3", "g2")], [step_of(b, g)["unread"] for g in ("g1", "g3", "g2")],
                    g3["counts"], l0["facts"], "facts check: statements read 1 + not read 2 = 3 steps; proofs read 1 + not read 1 + not "
                    "applicable 1 = 3 steps" in b.out.splitlines(), facts_line(b), _card(b, "g3").find("p", "proof")[0].text(),
                    "unread" in _card(b, "g3").cls, b.js("group/g3.json")["roots"][0]["proof_read"], l1["g3"]["proof_read"],
                    '"proof_read": null' in b.text("group/g3.json"), '"proof_read": false' in b.text("group/g3.json"),
                    _card(_base(), "g1a1").find("p", "proof")[0].text()),
                   (0, [True, None, False], [False, True, False],
                    {"roots": 1, "roots_statement_read": 0, "roots_proof_read": 0, "roots_proof_applicable": 0, "roots_open_items": 0,
                     "open_items": 0},
                    {"proof_applicable": 2, "proof_not_applicable": 1, "proof_not_read": 1, "proof_read": 1, "statement_not_read": 2,
                     "statement_read": 1, "steps": 3}, True,
                    ["Statements read: 1 of 3 steps.", "Proofs read: 1 of 2 steps.", "Questions written down in these notes: 1."],
                    NA_LINE, True, None, None, True, False, NA_LINE))

    @case("DEF2", "a step with some roots that are theorems and some that are defs (g2: quux a def, qux a theorem): the roots without a proof "
                  "are left out of the `every root` test, so with an argument block on qux the step's proof_read is TRUE (rows null, true), "
                  "the card counts over the roots that have a proof (`Proofs read: 1 of 1 declarations.`), roots_proof_applicable is 1 "
                  "and the facts and the first screen count it read (2 of 3 steps); without that block it is false (`Proofs read: 0 of "
                  "1 declarations.`, 1 of 3 steps)")
    def _():
        k = _decls_kinds({"quux": "def"})
        a, c = _build(decls=k, notes=_notes() | {"03-three.md": ARG_QUX}), _build(decls=k)

        def show(b):
            return (b.rc, step_of(b, "g2")["proof_read"], [r["proof_read"] for r in b.js("group/g2.json")["roots"]],
                    step_of(b, "g2")["counts"]["roots_proof_read"], step_of(b, "g2")["counts"]["roots_proof_applicable"],
                    _card(b, "g2").find("p", "proof")[0].text(), b.js("level0.json")["facts"]["proof_read"],
                    b.js("level0.json")["facts"]["proof_not_applicable"], facts_line(b)[1], "unread" in _card(b, "g2").cls)
        return _eq((show(a), show(c), "facts check: statements read 1 + not read 2 = 3 steps; proofs read 2 + not read 1 + not applicable "
                    "0 = 3 steps" in a.out.splitlines()),
                   ((0, True, [None, True], 1, 1, "Proofs read: 1 of 1 declarations.", 2, 0, "Proofs read: 2 of 3 steps.", False),
                    (0, False, [None, False], 0, 1, "Proofs read: 0 of 1 declarations.", 1, 0, "Proofs read: 1 of 3 steps.", False),
                    True))

    @case("DEF3", "a step whose every root is a def (g2: quux and qux) has no proof: proof_read null, roots_proof_applicable 0, and the card "
                  "shows the not-applicable line instead of the count line (never `Proofs read: 0 of 0 declarations.`); g1a1x (qux alone) "
                  "shows it too; the facts count the step apart (1 + 1 + 1 = 3)")
    def _():
        b = _build(decls=_decls_kinds({"quux": "def", "qux": "def"}))
        g2 = step_of(b, "g2")
        return _eq((b.rc, g2["proof_read"], g2["counts"]["roots_proof_applicable"], g2["counts"]["roots_proof_read"],
                    [r["proof_read"] for r in b.js("group/g2.json")["roots"]], _card(b, "g2").find("p", "proof")[0].text(),
                    _card(b, "g1a1x").find("p", "proof")[0].text(), "0 of 0" in b.page,
                    "facts check: statements read 1 + not read 2 = 3 steps; proofs read 1 + not read 1 + not applicable 1 = 3 steps"
                    in b.out.splitlines(), facts_line(b)[1]),
                   (0, None, 0, 0, [None, None], NA_LINE, NA_LINE, False, True, "Proofs read: 1 of 2 steps."))

    @case("DEF4", "when NO top-level step has a proof (every root of the table a def) the first screen shows steps_proof_not_applicable_line "
                  "in place of steps_proof_line (never `of 0 steps`): the second line of the facts list is that line, `of 0` is "
                  "nowhere on the page, the facts count 0 + 0 + 3 and the run prints the three-term check line; with every strings value a "
                  "marker the line is `MARK-steps_proof_not_applicable_line`; control: one step with a proof keeps steps_proof_line")
    def _():
        alld = _decls_kinds({ln.split("\t")[1]: "def" for ln in DECLS.splitlines() if len(ln.split("\t")) == 6 and
                             not ln.startswith("#") and ln.split("\t")[2] != "kind"})
        b = _build(decls=alld)
        m = _build(decls=alld, strings=_marked(_strings()))
        one = _build(decls=_decls_kinds({"corge": "def", "quux": "def", "qux": "def"}))
        return _eq((b.rc, facts_line(b), "of 0" in b.page, b.js("level0.json")["facts"]["proof_applicable"],
                    "facts check: statements read 1 + not read 2 = 3 steps; proofs read 0 + not read 0 + not applicable 3 = 3 steps"
                    in b.out.splitlines(), facts_line(m)[1], one.rc, facts_line(one)[1]),
                   (0, ["Statements read: 1 of 3 steps.", "No step here has a proof to read.", "Questions written down in these notes: 1."],
                    False, 0, True, "MARK-steps_proof_not_applicable_line", 0, "Proofs read: 1 of 1 steps."))

    @case("NAL1", "the strings key proof_not_applicable_line is required and holds no placeholder: a value with `{n}` is refused as an unknown "
                  "placeholder, a value with `{ x }` as a brace, an empty value as `must be a non-empty string`, a value with a forbidden "
                  "word as STRINGS-FORBIDDEN, each naming the key, exit 1, nothing written; with every strings value a marker the not-"
                  "applicable card shows `MARK-proof_not_applicable_line` and the first screen `MARK-steps_proof_line 1 2`")
    def _():
        res = []
        for v in ("None {n}", "A set { x } line.", "", "This was verified."):
            st = _strings()
            st["proof_not_applicable_line"] = v
            b = _build(strings=st)
            res.append((b.rc, [x for x in b.out.splitlines() if x.startswith("BUILD-ERROR")], b.existed))
        m = _build(decls=_decls_kinds({"corge": "def"}), strings=_marked(_strings()))
        return _eq((res, m.rc, _card(m, "g3").find("p", "proof")[0].text(), facts_line(m)[1]),
                   ([(1, ["BUILD-ERROR STRINGS-KEY proof_not_applicable_line has an unknown placeholder {n}"], False),
                     (1, ["BUILD-ERROR STRINGS-KEY proof_not_applicable_line holds a brace, and this key declares no placeholder"], False),
                     (1, ["BUILD-ERROR STRINGS-KEY proof_not_applicable_line must be a non-empty string"], False),
                     (1, ["BUILD-ERROR STRINGS-FORBIDDEN proof_not_applicable_line holds the word 'verified', which the page never says"],
                      False)], 0, "MARK-proof_not_applicable_line", "MARK-steps_proof_line 1 2"))

    @case("NAL3", "the two strings keys proof_none_other_line and steps_proof_not_applicable_line are required and hold no placeholder: a "
                  "value with `{n}` is an unknown placeholder, a value with `{ x }` a brace, an empty value `must be a non-empty string`, a "
                  "forbidden word STRINGS-FORBIDDEN, each naming the key, exit 1, nothing written")
    def _():
        res = []
        for key in ("proof_none_other_line", "steps_proof_not_applicable_line"):
            for v in ("None {n}", "A set { x } line.", "", "This was verified."):
                st = _strings()
                st[key] = v
                b = _build(strings=st)
                res.append((b.rc, [x for x in b.out.splitlines() if x.startswith("BUILD-ERROR")], b.existed))
        want = []
        for key in ("proof_none_other_line", "steps_proof_not_applicable_line"):
            want += [(1, [f"BUILD-ERROR STRINGS-KEY {key} has an unknown placeholder {{n}}"], False),
                     (1, [f"BUILD-ERROR STRINGS-KEY {key} holds a brace, and this key declares no placeholder"], False),
                     (1, [f"BUILD-ERROR STRINGS-KEY {key} must be a non-empty string"], False),
                     (1, [f"BUILD-ERROR STRINGS-FORBIDDEN {key} holds the word 'verified', which the page never says"], False)]
        return _eq(res, want)

    @case("NONE1", "a card with no proof says what it can: a root whose kind is outside the eight (`axiom`) shows proof_none_other_line "
                   "(`MARK-proof_none_other_line`, not the not-applicable one), a def keeps proof_not_applicable_line, a step with several "
                   "roots (g2, null claim) shows proof_none_other_line when ANY of its proof-less roots has an unknown kind (def + axiom, "
                   "either order) and proof_not_applicable_line when all are known (def + def); with the fixture wording an axiom card "
                   "shows `Proof: none to read, and this declaration is of a kind we do not know.`")
    def _():
        mk = _marked(_strings())
        line = lambda kinds, g, strings=mk: _card(_build(decls=_decls_kinds(kinds), strings=strings), g).find("p", "proof")[0].text()
        return _eq((line({"corge": "axiom"}, "g3"), line({"corge": "def"}, "g3"), line({"quux": "def", "qux": "axiom"}, "g2"),
                    line({"quux": "axiom", "qux": "def"}, "g2"), line({"quux": "def", "qux": "def"}, "g2"),
                    line({"corge": "axiom"}, "g3", _strings())),
                   ("MARK-proof_none_other_line", "MARK-proof_not_applicable_line", "MARK-proof_none_other_line",
                    "MARK-proof_none_other_line", "MARK-proof_not_applicable_line",
                    "Proof: none to read, and this declaration is of a kind we do not know."))

    @case("NAL2", "the strings file of this checkout (site/strings.json) passes the builder's own check (`_strings_problems` returns []), "
                  "carries the key proof_not_applicable_line, and that value holds no brace")
    def _():
        path = os.path.join(_HERE, os.pardir, "site", "strings.json")
        if not os.path.isfile(path):
            raise _SkipCase("no real strings file in this checkout")
        return _eq(_real_strings_facts(path), ([], True, True))

    # ---- F23: a note title is rendered like a claim, and the source check compares what a reader sees
    def _titled(t00, t01, t02):
        n = _notes()
        n["00-whole.md"] = N00.replace('"list_title":"Whole one"', '"list_title":' + _js_safe(json.dumps(t00)))
        n["01-one.md"] = _n01().replace('"list_title":"Note one"', '"list_title":' + _js_safe(json.dumps(t01)))
        n["02-two.md"] = N02.replace('"list_title":"Note two"', '"list_title":' + _js_safe(json.dumps(t02)))
        return n

    show_links = lambda node: [(a.text(), [c.text() for c in a.find("code")]) for a in node.find("a")]

    @case("TITLE1", "a note title is rendered by the same span rule as a claim: a span between single backticks on one line is <code> (its "
                    "content escaped) in the level-0 list (`Whole `one``), in the notes list of a card (g1: `Note `one``, `Note `x < y` two``) "
                    "and in the corrections list of g1 (`Note `one``), and no literal backtick is left on the page; the JSON and data.js "
                    "keep the title as written")
    def _():
        b = _build(notes=_titled("Whole `one`", "Note `one`", "Note `x < y` two"))
        g1 = _card(b, "g1")
        l0 = b.js("level0.json")
        return _eq((b.rc, show_links(_dom(b.page).find("header")[0]), show_links(_direct(g1, "ul", "notes")[0]),
                    show_links(_direct(g1, "ul", "corrections")[0]), "`" in b.page, "Note <code>x &lt; y</code> two</a>" in b.page,
                    l0["header_notes"][0]["list_title"], [n["list_title"] for n in l0["steps"][0]["notes"]],
                    "Note `x \\u003c y` two" in b.text("data.js")),
                   (0, [("Whole one", ["one"])], [("Note one", ["one"]), ("Note x < y two", ["x < y"])], [("Note one", ["one"])],
                    False, True, "Whole `one`", ["Note `one`", "Note `x < y` two"], True))

    @case("TITLE2", "in a title doubled backticks, an unpaired backtick and an empty pair stay literal text, with no <code> (the level-0 `Whole "
                    "``one``` and `Note `one` in g1's list); control: a real span in the same build is code (`Note `ok` two`)")
    def _():
        b = _build(notes=_titled("Whole ``one``", "Note `one", "Note `ok` two"))
        g1 = _card(b, "g1")
        return _eq((b.rc, show_links(_dom(b.page).find("header")[0]), show_links(_direct(g1, "ul", "notes")[0]),
                    ">Whole ``one``</a>" in b.page, ">Note `one</a>" in b.page),
                   (0, [("Whole ``one``", [])], [("Note `one", []), ("Note ok two", ["ok"])], True, True))

    @case("SPAN1", "the source check compares what a reader sees: a claim that is a release line inside single backticks is refused "
                   "(SOURCE-LEAK naming data.js, level0.json and level1.json: the text of the JSON with the backticks of the span removed; "
                   "the page skips <code>), exit 1, OUT_DIR absent; the same line unwrapped is refused as before (those three and "
                   "index.html)")
    def _():
        res = []
        for text in ("`" + LEAK + "`", LEAK):
            o = _outline()
            o["groups"][0]["claim"]["text"] = text
            b = _build(outline=o, src=srcs)
            res.append((b.rc, sorted(ln for ln in b.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK ")), b.existed))
        return _eq(res, [(1, [leak_line(w) for w in ("data.js", "level0.json", "level1.json")], False),
                         (1, [leak_line(w) for w in ("data.js", "index.html", "level0.json", "level1.json")], False)])

    @case("SPAN2", "the same for a condition: a condition that is a release line inside single backticks is refused (data.js, level0.json, "
                   "level1.json), exit 1, OUT_DIR absent; unwrapped, also index.html")
    def _():
        res = []
        for text in ("`" + LEAK + "`", LEAK):
            o = _outline()
            o["groups"][2]["claim"]["conditions"] = [text]
            b = _build(outline=o, src=srcs)
            res.append((b.rc, sorted(ln for ln in b.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK ")), b.existed))
        return _eq(res, [(1, [leak_line(w) for w in ("data.js", "level0.json", "level1.json")], False),
                         (1, [leak_line(w) for w in ("data.js", "index.html", "level0.json", "level1.json")], False)])

    @case("SPAN3", "the same for a note title: a title that is a release line inside single backticks is refused, naming the note and the "
                   "field (`note 02 field list_title`, the source line with the span removed) and the JSON files that list the note "
                   "(data.js, group/g1.json, group/g1a1x.json, group/g2.json, level0.json, level1.json), exit 1, OUT_DIR absent; unwrapped, "
                   "also index.html")
    def _():
        res = []
        files = ("data.js", "group/g1.json", "group/g1a1x.json", "group/g2.json", "level0.json", "level1.json")
        for text in ("`" + LEAK + "`", LEAK):
            b = _build(notes=_titled("Whole one", "Note one", "Note two\n" + text), src=srcs)
            res.append((b.rc, sorted(ln for ln in b.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK ")), b.existed))
        return _eq(res, [(1, sorted(leak_line(w) for w in files + ("note 02 field list_title",)), False),
                         (1, sorted(leak_line(w) for w in files + ("index.html", "note 02 field list_title")), False)])

    @case("SPAN4", "what is NOT a span is compared as written: a release line inside DOUBLED backticks in a claim, a condition and a title "
                   "builds (exit 0); a wrapped line that is not a release line builds and the JSON keeps it as written (backticks "
                   "included); a release line inside a longer sentence (a span in the middle of it) is not seen (the narrow claim); the "
                   "ids-only control (the base build under --source-check) stays green")
    def _():
        o1 = _outline()
        o1["groups"][0]["claim"]["text"] = "``" + LEAK + "``"
        o1["groups"][2]["claim"]["conditions"] = ["``" + LEAK + "``"]
        dbl = _build(outline=o1, notes=_titled("Whole one", "Note one", "Note two\n``" + LEAK + "``"), src=srcs)
        o2 = _outline()
        o2["groups"][0]["claim"]["text"] = "`" + other + "`"
        o2["groups"][2]["claim"]["conditions"] = ["`" + other + "`"]
        wrapped = _build(outline=o2, notes=_titled("Whole one", "Note one", "Note two\n`" + other + "`"), src=srcs)
        o3 = _outline()
        o3["groups"][0]["claim"]["text"] = "See `" + LEAK + "` here"
        inside = _build(outline=o3, src=srcs)
        s3 = [x for x in wrapped.js("level0.json")["steps"] if x["id"] == "g3"][0]["claim"]["text"]
        return _eq((dbl.rc, dbl.existed, wrapped.rc, s3, wrapped.js("level0.json")["steps"][0]["claim"]["conditions"],
                    [n["list_title"] for n in wrapped.js("level0.json")["steps"][0]["notes"]], inside.rc, _base_src().rc),
                   (0, True, 0, "`" + other + "`", ["`" + other + "`"], ["Note one", "Note two\n`" + other + "`"], 0, 0))

    # ---- F28: the text of an argument or interpretation block goes through the one span rule
    _nosecond = lambda h: re.sub(r' <span class="frame second">.*?</span>', "", h)   # F29: the second readers follow the text

    def _para(page, cls):
        """The text after the frame of the last `<p class=cls>` of the page (the evidence list's paragraph, not the card's)."""
        return _nosecond(re.findall(r'<p class="' + cls + r'">(.*?)</p>', page, re.S)[-1]).rsplit("</span> ", 1)[1]

    BT_TEXTS = ["See `a<b` here", "`one` and `two` end", "a ` b", "a ``x`` b", "a `` b", "a `x\ny` b", "Plain text only"]
    BT_WANT = ["See <code>a&lt;b</code> here", "<code>one</code> and <code>two</code> end", "a ` b", "a ``x`` b", "a `` b",
               "a <code>x y</code> b", "Plain text only"]

    @case("BT1", "an ARGUMENT block's text is rendered by the span rule on the evidence list: a span between single backticks is <code> "
                 "with its content escaped (`a<b` gives a&lt;b); two spans in one block; an unpaired backtick, doubled backticks, an "
                 "empty pair stay literal; a span over a SOURCE line break is a span (the paragraph is joined by spaces first: `a `x` + `y` b` gives "
                 "<code>x y</code>); a block with no backtick is as before")
    def _():
        got = [_para(_build(notes=_notes(arg_text=t)).page, "argument") for t in BT_TEXTS]
        return _eq(got, BT_WANT)

    @case("BT2", "the same for an INTERPRETATION block (the frame stays escaped text)")
    def _():
        got = [_para(_build(notes=_notes(interp_text=t)).page, "interpretation") for t in BT_TEXTS]
        frame = '<span class="frame">What we think it means:</span> '
        whole = re.findall(r'<p class="interpretation">(.*?)</p>', _build(notes=_notes(interp_text="Plain text only")).page, re.S)
        return _eq((got, whole), (BT_WANT, [frame + "Plain text only"]))

    @case("BT3", "the JSON and data.js keep the block text and the first sentence as written, backticks included")
    def _():
        b = _build(notes=_notes(arg_text="See `a<b` here", interp_text="We `think` so"))
        blk = {x["block"]: x for x in b.js("group/g1.json")["blocks"] if x["kind"] in ("argument", "interpretation")}
        return _eq(({k: (v["text"], v["first_sentence"]) for k, v in blk.items()},
                    "See `a\\u003cb` here" in b.text("data.js"), "We `think` so" in b.text("data.js")),
                   ({"01.b02": ("See `a<b` here", "See `a<b` here"), "01.b03": ("We `think` so", "We `think` so")}, True, True))

    CARD_TEXTS = ["See `a<b` here. More `x` text.", "a ` b. c", "a ``x`` b. c", "a `` b. c", "Plain only. More.", "A `x` and `y<z` end. More."]
    CARD_WANT = ["See <code>a&lt;b</code> here.", "a ` b.", "a ``x`` b.", "a `` b.", "Plain only.", "A <code>x</code> and <code>y&lt;z</code> end."]

    @case("BT5", "the first sentence of an argument block on the CARD is rendered by the span rule too (a span is <code>, content "
                 "escaped; two spans are both code; an unpaired backtick, doubled backticks and an empty pair stay literal; no backtick as before)")
    def _():
        got = []
        for t in CARD_TEXTS:
            card = re.findall(r'<p class="argument">(.*?)</p>', _build(notes=_notes(arg_text=t)).page, re.S)[0]
            got.append(_nosecond(card).rsplit("</span> ", 1)[1].split(' <a href=')[0])
        return _eq(got, CARD_WANT)

    R1 = "Zq release text one sentence here. And the second sentence of it."   # leaks through the block `text` only when wrapped whole
    R2 = "Zq release first sentence words here."   # leaks through the `first_sentence` only when its span is unwrapped
    R4 = "Zq release text two spans one sentence here. And more words follow here."   # two spans; the first sentence cannot carry it
    srcs2 = {"A/B.lean": "x = 1\n" + LEAK + "\n" + R1 + "\n" + R2 + "\n" + R4 + "\n"}
    LEAKFILES = [leak_line(w) for w in ("data.js", "group/g1.json")]
    BT4_PLANTS = [("`" + LEAK + "`", "text and first sentence"), ("`" + R1 + "`", "text only"),
                  ("`" + R2[:-1] + "`. More text after it.", "first sentence only"),
                  ("`Zq release text` two `spans one` sentence here. And more words follow here.", "two spans, text only")]

    @case("BT4", "the source check compares block text and first sentence as a reader sees them: a release line inside single backticks "
                 "as an ARGUMENT block is refused (SOURCE-LEAK naming data.js and group/g1.json), as an INTERPRETATION block too; "
                 "four plants: the whole text and first sentence, the text only (a two-sentence release line), the first sentence "
                 "only, the text only with TWO spans (every span is removed, not the first); exit 1, OUT_DIR absent")
    def _():
        res = []
        for field in ("arg_text", "interp_text"):
            for plant, _what in BT4_PLANTS:
                b = _build(notes=_notes(**{field: plant}), src=srcs2)
                res.append((b.rc, sorted(ln for ln in b.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK ")), b.existed))
        return _eq(res, [(1, LEAKFILES, False)] * 8)

    @case("BT6", "what is NOT a span is compared as written: the same four plants in DOUBLED backticks (two doubled pairs in the last) build (exit 0) as argument and "
                 "as interpretation; a wrapped line that is no release line builds; the ids-only base build stays green")
    def _():
        res = []
        for field in ("arg_text", "interp_text"):
            for plant, _what in BT4_PLANTS:
                dbl = plant.replace("`", "``")
                b = _build(notes=_notes(**{field: dbl}), src=srcs2)
                res.append((b.rc, b.existed))
        ok = _build(notes=_notes(arg_text="`" + other + "`", interp_text="`" + other + "`"), src=srcs2)
        return _eq((res, ok.rc, _base_src().rc), ([(0, True)] * 8, 0, 0))

    R3 = "const t : `bar` = 1 holds true."   # a release line that itself holds a span
    srcs3 = {"A/B.lean": "x = 1\n" + R3 + "\n"}

    @case("BT7", "a release line that itself holds a single-backtick span, as the FIRST SENTENCE of an argument block and of an "
                 "interpretation block, is refused (SOURCE-LEAK naming data.js and group/g1.json: the raw first sentence is compared as "
                 "well as the unspanned one); exit 1, OUT_DIR absent. The same text as a claim keeps its behaviour: it builds (a claim is "
                 "compared unspanned only)")
    def _():
        res = []
        for field in ("arg_text", "interp_text"):
            b = _build(notes=_notes(**{field: R3 + " More words after it here."}), src=srcs3)
            res.append((b.rc, sorted(ln for ln in b.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK ")), b.existed))
        o = _outline()
        o["groups"][0]["claim"]["text"] = R3
        claim = _build(outline=o, src=srcs3)
        return _eq((res, claim.rc), ([(1, LEAKFILES, False)] * 2, 0))

    @case("BT8", "KNOWN LIMIT, pinned: the first sentence is cut at the first `.`, `!` or `?` followed by white space even inside a span: "
                 "`We apply `f. g` here. More.` has the first sentence `We apply `f.` (JSON and card, the backtick left literal), while "
                 "the evidence list shows the whole text with its span as code")
    def _():
        b = _build(notes=_notes(arg_text="We apply `f. g` here. More."))
        card = _nosecond(re.findall(r'<p class="argument">(.*?)</p>', b.page, re.S)[0]).rsplit("</span> ", 1)[1].split(' <a href=')[0]
        first = [x for x in b.js("group/g1.json")["blocks"] if x["block"] == "01.b02"][0]["first_sentence"]
        return _eq((first, card, _para(b.page, "argument")), ("We apply `f.", "We apply `f.", "We apply <code>f. g</code> here. More."))

    @case("FR4", "FORMULA-RAW: the span is taken out as ONE SPACE, so characters on either side are not joined into a mark: a backslash, "
                 "a span, then an open parenthesis is not listed; a backslash and a parenthesis with no span between them is")
    def _():
        return _eq([_fr(arg_text="Take \\`x`(y) here"), _fr(arg_text="Take \\(y) here")],
                   [(0, []), (0, ["FORMULA-RAW 01.b02"])])

    def _fr(**kw):
        b = _build(notes=_notes(**kw))
        return b.rc, [ln for ln in b.out.splitlines() if ln.startswith("FORMULA-RAW")]

    @case("FR1", "a block whose text, outside its single-backtick spans, holds `$`, `\\(`, `\\[` or `\\begin{` is LISTED as one line "
                 "`FORMULA-RAW <block id>` and the build exits 0; the same mark inside a span is not listed; a plain `5` is not; "
                 "a block with two marks is listed once")
    def _():
        res = [_fr(arg_text=t) for t in ("Take $x$ here", "Take `$x$` here", "Take \\(x\\) here", "Take \\[x\\] here",
                                         "Take \\begin{align} x", "Take 5 here", "Cost $5 and $6", "A `$x$` and then $y$")]
        return _eq(res, [(0, ["FORMULA-RAW 01.b02"]), (0, []), (0, ["FORMULA-RAW 01.b02"]), (0, ["FORMULA-RAW 01.b02"]),
                         (0, ["FORMULA-RAW 01.b02"]), (0, []), (0, ["FORMULA-RAW 01.b02"]), (0, ["FORMULA-RAW 01.b02"])])

    @case("FR2", "an INTERPRETATION block is listed the same way; two blocks of one note give one line each in output order, one "
                 "block listed alone gives one line; the base build lists none")
    def _():
        res = [_fr(interp_text="We think $x$ here"), _fr(arg_text="Take $x$", interp_text="We \\(y\\) too"),
               _fr(arg_text="Take $x$"), _fr(interp_text="We `$y$` too")]
        return _eq((res, [ln for ln in _base().out.splitlines() if ln.startswith("FORMULA-RAW")]),
                   ([(0, ["FORMULA-RAW 01.b03"]), (0, ["FORMULA-RAW 01.b02", "FORMULA-RAW 01.b03"]), (0, ["FORMULA-RAW 01.b02"]),
                     (0, [])], []))

    @case("FR3", "FORMULA-RAW ranges over argument, interpretation and sketch blocks only: `_formula_raw` on a model whose blocks of every other "
                 "kind (reading, correction, not_read, machine_fact) carry a text with a mark lists none of them; the sketch is read from its "
                 "paragraphs and list items (a block of the kind with no sketch elements is not listed)")
    def _():
        kinds = ("reading", "correction", "not_read", "machine_fact", "sketch", "argument", "interpretation")
        note = {"id": "n", "blocks": [{"block": "n.b" + k, "kind": k, "text": "Take $x$ here"} for k in kinds]}
        for b_ in note["blocks"]:
            if b_["kind"] == "sketch":
                b_["_sk"] = {"blocks": [{"type": "paragraph", "text": "No mark."}, {"type": "list", "ordered": False, "items": ["Take $x$ here"]}]}
        bare = {"id": "n", "blocks": [{"block": "n.bsketch", "kind": "sketch", "_sk": {"blocks": []}}]}
        got = _formula_raw(types.SimpleNamespace(notes=[note]))
        return _eq((got, _formula_raw(types.SimpleNamespace(notes=[bare]))), (["n.bsketch", "n.bargument", "n.binterpretation"], []))

    # ---- B1: no release text
    @case("B1a", "leak_check: a planted shard whose `text` value is a line of the release (>= 20 non-space characters) is named "
                 "(SOURCE-LEAK data); a short release line and a line of other text are not")
    def _():
        with tempfile.TemporaryDirectory() as d:
            _put(os.path.join(d, "A", "B.lean"), "import A.C\n\n    " + LEAK + "  \nshort\n")
            files = {"group/x.json": json.dumps({"id": "x", "text": LEAK}).encode(),
                     "group/y.json": json.dumps({"id": "y", "text": "short"}).encode(),
                     "group/z.json": json.dumps({"id": "z", "text": "A sentence of ours that is long enough to count."}).encode()}
            leaks, stats = leak_check(files, d)
        return _eq((leaks, stats), (["group/x.json"], {"release_files": 1, "release_lines": 4, "output_files": 3, "output_lines": 3}))

    @case("B1b", "leak_check, the ids-only control: a release that has a line equal to a declaration name (>= 20 characters) and "
                 "an output that has only that name in its id and name fields is green; the same text under `text` is a leak")
    def _():
        name = "Development.Long.Module.theorem_name_long"
        with tempfile.TemporaryDirectory() as d:
            _put(os.path.join(d, "A.lean"), name + "\n")
            ids = {"group/y.json": json.dumps({"id": name, "roots": [{"module": name, "name": name}], "lean_name": name}).encode()}
            txt = {"group/y.json": json.dumps({"id": "y", "text": name}).encode()}
            return _eq((leak_check(ids, d), leak_check(txt, d)),
                       (([], {"release_files": 1, "release_lines": 1, "output_files": 1, "output_lines": 0}),
                        (["group/y.json"], {"release_files": 1, "release_lines": 1, "output_files": 1, "output_lines": 1})))

    @case("B1c", "a build whose argument text is a release line is refused: SOURCE-LEAK for data.js, group/g1.json and index.html, "
                 "exit 1, nothing written; the page text in <code> (names) is not compared; control: the default note builds")
    def _():
        b = _build(notes=_notes(arg_text=LEAK), src={"A/B.lean": "x\n" + LEAK + "\n"})
        got = sorted(ln.split(" ")[2] for ln in b.out.splitlines()
                     if ln.startswith("BUILD-ERROR SOURCE-LEAK ") and not ln.startswith("BUILD-ERROR SOURCE-LEAK note "))
        return _eq((b.rc, got, b.existed, _base_src().rc), (1, ["data.js", "group/g1.json", "index.html"], False, 0))

    @case("B1d", "the run says what it ranged over: `source check: 1 release files, 40 release lines, 11 output files, N output "
                 "lines, 0 leaked`")
    def _():
        m = re.findall(r"^source check: 1 release files, 40 release lines, 11 output files, (\d+) output lines, 0 leaked$",
                       _base_src().out, re.M)
        return _eq((len(m), bool(m) and int(m[0]) > 20), (1, True))

    @case("B1e", "names are not compared (by construction): a release with a line equal to a declaration's full name (>= 20 "
                 "characters) and a build whose root has that name builds clean, 0 leaked, although the name is in the JSON "
                 "and in <code> on the page; control: the same text as a claim is a leak (level0.json, level1.json, "
                 "data.js, index.html)")
    def _():
        name = "Development.Long.Module.theorem_name_long"
        decls = DECLS.replace("A.G\tcorge", "A.G\t" + name)
        src = {"A/B.lean": "x\n" + name + "\n"}
        o = _outline()
        o["groups"][0]["roots"] = [_d("A.G", name)]
        named = _build(outline=o, decls=decls, src=src)
        o2 = _outline()
        o2["groups"][0]["claim"]["text"] = name
        claimed = _build(outline=o2, src=src)
        got = sorted(ln.split(" ")[2] for ln in claimed.out.splitlines() if ln.startswith("BUILD-ERROR SOURCE-LEAK "))
        return _eq((named.rc, name in named.page, ", 0 leaked" in named.out, claimed.rc, got),
                   (0, True, True, 1, ["data.js", "index.html", "level0.json", "level1.json"]))

    # ---- F24b: the recognition of a statement, on the card and in the JSON
    zd = {z[0]: z[3] for z in _ZOO}
    rcn = lambda b_, g: _direct(_card(b_, g), "div", "recognition")[0]
    lead = lambda node: [(k.tag, k.cls[-1] if k.cls else "") for k in node.elems()]
    ext = lambda b_: sorted(a.attrs["href"] for a in _dom(b_.page).find("a") if a.attrs.get("href", "").startswith("http"))

    @case("RJ1", "A1: group/<id>.json and the step summaries of level0.json and level1.json (nested too) carry root_role (the group's "
                 "string, null when the group has no claim or no role), root_kind (the table's kind of the one root of a group with a "
                 "claim, else null) and recognition (the object as written, else null); the outline is written with its keys in "
                 "reverse order; none of them is in counts: zrv is (result, theorem, its object), g1 has a claim and a role the fixture gave it "
                 "(result, theorem, null), g1a1 a definition (named_statement, def, null), g2 no claim (null, null, null), zkr a recognition")
    def _():
        b = _zbase()
        pick = lambda o: (o["root_role"], o["root_kind"], o["recognition"])
        l0 = {s["id"]: s for s in b.js("level0.json")["steps"]}
        kid = next(c for c in next(s for s in b.js("level1.json")["steps"] if s["id"] == "g1")["children"] if c["id"] == "zrv")
        got = (pick(b.js("group/zrv.json")), pick(kid), pick(b.js("group/g1.json")), pick(l0["g1"]), pick(b.js("group/g1a1.json")),
               pick(b.js("group/g2.json")), pick(l0["g2"]), pick(b.js("group/zkr.json")), sorted(l0["g1"]["counts"]),
               b.js("group/zrv.json") == json.loads(b.text("data.js")[len("window.RH_DATA = "):-len(";\n")])["groups"]["zrv"])
        want = (("result", "theorem", zd["zrv"]), ("result", "theorem", zd["zrv"]), ("result", "theorem", None), ("result", "theorem", None),
                ("named_statement", "def", None), (None, None, None), (None, None, None), ("result", "theorem", zd["zkr"]),
                ["open_items", "roots", "roots_open_items", "roots_proof_applicable", "roots_proof_read", "roots_statement_read"], True)
        return _eq(got, want)

    @case("RC1", "A2: a card shows, in order, the claim, the conditions, the premises line, THEN the recognition block, THEN the two "
                 "status lines (all direct children of the card); a group with no claim (g2, g1a1x) shows no recognition block and no "
                 "named-statement line; a claimed group with no recognition shows the block with the not-written line")
    def _():
        o = _outline()
        g1 = next(g for g in o["groups"] if g["id"] == "g1")
        g1["root_role"], g1["recognition"] = "result", _rec("known", result="R", citations=[CITB])
        b = _build(outline=o)
        names = lead(_card(b, "g1"))
        want = [("h3", "claim"), ("ul", "conditions"), ("p", "premises"), ("div", "recognition"), ("p", "statement"), ("p", "proof"),
                ("p", "argument"), ("details", "evidence")]
        pos = {n: names.index(n) for n in want}
        null = [(len(_card(b, g).find("div", "recognition")), len(_card(b, g).find("p", "named-statement-use"))) for g in ("g2", "g1a1x")]
        unwritten = [_raw(_direct(rcn(_base(), "g1"), "p", "recognition-form")[0])]
        return _eq(([n for n in sorted(pos, key=pos.get)], null, unwritten),
                   (want, [(0, 0), (0, 0)], ["Our reading of this statement: not written yet."]))

    @case("RF1", "A3: the form line is the key for the role and the form, with {result} filled (through the span rule: `prime` is <code>) "
                 "and, for an open form, {source_date} the NEWEST source_date among the says_open citations compared as the strings as "
                 "written (2010-03 of three dates in no order; the year-month 2006-11 over the year 2006 listed first; a lone year reads "
                 "`as of 2006`; a says_open false citation of 2020-01 is not counted); the role of a group with no root_role is the "
                 "class of its root's kind (zkr theorem: result, zkn def: named statement); no recognition: the not-written line")
    def _():
        b = _zbase()
        got = {z[0]: _raw(_direct(rcn(b, z[0]), "p", "recognition-form")[0]) for z in _ZOO}
        nr = "It may come from this proof, or it may be known and we have not found it."
        want = {
            "zrk": "Our reading: this is a well-known result in mathematics (the prime counting formula).",
            "zrv": "Our reading: this is a version of a well-known result (Foo's theorem), changed to fit this proof.",
            "zrn": "Our reading: we do not recognise this as a known result. " + nr,
            "zro": "Our reading: this result's statement is the Foo conjecture, an open problem as of 2010-03 according to the dated source below.",
            "zry": "Our reading: this result's statement is the Bar conjecture, an open problem as of 2006 according to the dated source below.",
            "znk": "Our reading: the statement named here is a well-known result in mathematics (res-znk).",
            "znv": "Our reading: the statement named here is a version of a well-known result (res-znv), changed to fit this proof.",
            "znn": "Our reading: we do not recognise the statement named here as a known result. " + nr,
            "zno": "Our reading: the statement named here is res-zno, an open problem as of 2006-11 according to the dated source below.",
            "zok": "Our reading: this is the standard definition of res-zok.",
            "zov": "Our reading: this is a version of the standard definition of res-zov, changed to fit this proof.",
            "zon": "Our reading: we do not recognise this as a standard definition. It may be made for this proof, or it may be standard "
                   "and we have not found it.",
            "zkr": "Our reading: this is a well-known result in mathematics (res-zkr).",
            "zkn": "Our reading: the statement named here is a well-known result in mathematics (res-zkn).",
            "zw": "Our reading of this statement: not written yet.", "zwn": "Our reading of this statement: not written yet."}
        return _eq(got, want)

    @case("RD1", "A4: after the form line comes the difference as a paragraph through the span rule (zrv: `n` and `2n` are <code>), then each "
                 "citation as a line of a list (the dated line, the source through the span rule), then the label line: zrv is "
                 "(form, difference, citations, label), zrk (no difference) is (form, citations, label); a citation with a url is an "
                 "<a class=citation> to that https address around its line, one without a url is no link")
    def _():
        b = _zbase()
        v, k = rcn(b, "zrv"), rcn(b, "zrk")
        lis = _direct(v, "ul", "recognition-citations")[0].elems()
        got = (lead(v), lead(k), _raw(_direct(v, "p", "recognition-difference")[0]),
               [c.text() for c in _direct(v, "p", "recognition-difference")[0].find("code")],
               [(a.cls, a.attrs["href"], _raw(a)) for a in lis[0].find("a")], [a for a in lis[1].find("a")] == [],
               [_raw(li) for li in lis], [c.text() for c in lis[1].find("code")], [c.text() for c in k.find("p", "recognition-form")[0].find("code")])
        want = ([("p", "recognition-form"), ("p", "recognition-difference"), ("ul", "recognition-citations"), ("p", "recognition-label")],
                [("p", "recognition-form"), ("ul", "recognition-citations"), ("p", "recognition-label")],
                "Here the bound is n, not 2n.", ["n", "2n"],
                [(["citation"], "https://example.invalid/book", "The Source Book, Theorem 2.1")], True,
                ["The Source Book, Theorem 2.1", "Other Paper, Section 3"],
                ["Paper"], ["prime"])
        return _eq(got, want)

    @case("RD2", "A4: a citation that says_open on an open card uses the open line with ITS OWN source_date as written (2007-01, 2004-05-17, "
                 "2010-03, the year 2006 alone, 2006-11), a citation that does not say open (List D, 2020-01) uses the dated line; a "
                 "says_open citation on a card that is not an open one (zov, a variant) uses the dated line too")
    def _():
        b = _zbase()
        cits = lambda g: [_raw(li) for li in _direct(rcn(b, g), "ul", "recognition-citations")[0].elems()]
        return _eq([cits(g) for g in ("zro", "zry", "zno", "zov")],
                   [["List A, Problem 7, dated 2007-01", "List B, Problem 7, dated 2004-05-17",
                     "List C, Problem 7, dated 2010-03", "List D, Problem 7"],
                    ["List Y, Problem 7, dated 2006"],
                    ["List E, Problem 7, dated 2006", "List F, Problem 7, dated 2006-11"],
                    ["Other Paper, Section 3", "List G, Problem 7"]])

    @case("RL1", "A5, as F37 left it: the label line is one standing sentence with no reader and no date (the reader and date of the RECOGNITION "
                 "are in the Evidence section: zrk Reader One 2026-11-22, zok Reader Two 2026-11-23), the block adds no link of its own (zrn has "
                 "none, zrk only the citation anchor), and the three reaction links at the foot of the card are unchanged (zrk's hrefs; 22 cards "
                 "give 66 reaction anchors)")
    def _():
        b = _zbase()
        lab = lambda g: _raw(_direct(rcn(b, g), "p", "recognition-label")[0])
        tail = "No mathematician has checked our reading yet. If you think we have it wrong, or you know more, please tell us."
        return _eq((lab("zrk"), lab("zok"), len(rcn(b, "zrn").find("a")), [a.cls for a in rcn(b, "zrk").find("a")],
                    [a.attrs["href"] for a in _card(b, "zrk").find("ul", "reactions")[0].find("a")], len(_dom(b.page).find("a", "reaction"))),
                   (tail, tail, 0, [["citation"]],
                    ["https://example.invalid/react?card=zrk&kind=sense", "https://example.invalid/react?card=zrk&kind=wrong",
                     "https://example.invalid/react?card=zrk&kind=detail"], 66))

    @case("RU1", "A6: the named-statement line shows on every card whose role is named_statement, with a recognition or without (zwn, g1a1: a "
                 "definition with no role and no recognition), by the role or by the kind (zkn), directly after the claim (F36: BEFORE the recognition block, "
                 "also when it is the not-written line) and before the status lines, and on no card of another role or of no claim")
    def _():
        b = _zbase()
        dom = _dom(b.page)
        ids = sorted(a.attrs["id"] for a in dom.find("article") if _direct(a, "p", "named-statement-use"))
        line = "This step gives a name to a statement. Steps that use the name take the statement as a hypothesis."
        return _eq((ids, _raw(_direct(_card(b, "znk"), "p", "named-statement-use")[0]), lead(_card(b, "zwn"))[:4], lead(_card(b, "znk"))[:4],
                    lead(_card(b, "g1a1"))[:5]),
                   (["g1a1", "zkn", "znk", "znn", "zno", "znv", "zwn"], line,
                    [("h3", "claim"), ("p", "named-statement-use"), ("div", "recognition"), ("p", "statement")],
                    [("h3", "claim"), ("p", "named-statement-use"), ("div", "recognition"), ("p", "statement")],
                    [("h3", "claim"), ("p", "named-statement-use"), ("div", "recognition"), ("p", "statement"), ("p", "proof")]))

    @case("RU2", "F36 (b): on a named-statement card the use line comes directly after the claim and its conditions, BEFORE the premises line "
                 "and the recognition block (the choice where the spec is silent on the premises line: the use line is the first thing after "
                 "the claim and conditions), also when the recognition is not written (zwn: the use line, then the not-written line); a "
                 "result card (zrk) and an object card (zok) with the same conditions and premises have no use line")
    def _():
        o = _zoo()
        for g in o["groups"]:
            if g["id"] in ("znk", "zwn", "zrk", "zok"):
                g["claim"]["conditions"], g["premises"] = ["Condition holds."], ["g1a"]
        b = _build(outline=o)
        return _eq([[k[1] for k in lead(_card(b, g))][:6] for g in ("znk", "zwn", "zrk", "zok")],
                   [["claim", "conditions", "named-statement-use", "premises", "recognition", "statement"],
                    ["claim", "conditions", "named-statement-use", "premises", "recognition", "statement"],
                    ["claim", "conditions", "premises", "recognition", "statement", "proof"],
                    ["claim", "conditions", "premises", "recognition", "statement", "proof"]])

    @case("RE1", "A7: `established` of a named statement shows after the citations and before the label line: by -> `Where it is proved: the "
                 "release proves this statement as A.B.foo.` (the name is module.name; the reader and date are in Evidence), not_traced -> "
                 "the not-traced line; only znk and znv have one")
    def _():
        b = _zbase()
        dom = _dom(b.page)
        ids = sorted(a.attrs["id"] for a in dom.find("article") if any(_direct(d_, "p", "recognition-established") for d_ in _direct(a, "div", "recognition")))
        est = lambda g: _raw(_direct(rcn(b, g), "p", "recognition-established")[0])
        return _eq((ids, est("znk"), est("znv"), lead(rcn(b, "znk")), lead(rcn(b, "znv"))),
                   (["znk", "znv"], "Where it is proved: the release proves this statement as A.B.foo.",
                    "Where it is proved: we have not yet traced where in the release this statement is proved.",
                    [("p", "recognition-form"), ("ul", "recognition-citations"), ("p", "recognition-established"), ("p", "recognition-label")],
                    [("p", "recognition-form"), ("p", "recognition-difference"), ("ul", "recognition-citations"),
                     ("p", "recognition-established"), ("p", "recognition-label")]))

    @case("RE2", "A7: established is for a named statement only: the model of the outline with `established` put on a RESULT (zrk; the "
                 "checker refuses it first in a run, so the model is called directly) shows no established line on that card; control: "
                 "znk, a named statement, shows its line")
    def _():
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d, outline=_zoo())
            odata = json.load(open(p["outline"]))
            next(g for g in odata["groups"] if g["id"] == "zrk")["recognition"]["established"] = "not_traced"
            sj, errors = _strings(), []
            m = _model(p["notes"], odata, _decl_rows(p["decls"]), sj, None, errors)
            _e2, _line, _l0, _l1, _groups, facts = _assemble(m, sj, {"notes": "n", "release": "r", "tools": "t"})
            page = _render_page(m, sj, facts, False)
        return _eq((errors, [len(_card(types.SimpleNamespace(page=page), g).find("p", "recognition-established")) for g in ("zrk", "znk")]),
                   ([], [0, 1]))

    @case("RS1", "A8: the run prints `recognition: K known, V variant, N not recognised, O open in literature, M not written, of G groups "
                 "with a claim` after the facts check, counted over ALL groups with a claim at every depth (the zoo is nested at level 2: "
                 "5, 3, 3, 3, 5 of 19, with g1, g1a1 and g3 not written; the base fixture 0, 0, 0, 0, 3 of 3); the pure function "
                 "recognition_counts counts the four forms and None and nothing else (a value that is none of them is counted nowhere)")
    def _():
        z, base = _zbase().out.splitlines(), _base().out.splitlines()
        zl = "recognition: 5 known, 3 variant, 3 not recognised, 3 open in literature, 5 not written, of 19 groups with a claim"
        bl = "recognition: 0 known, 0 variant, 0 not recognised, 0 open in literature, 3 not written, of 3 groups with a claim"
        return _eq((zl in z, bl in base, z.index(zl) > min(i for i, ln in enumerate(z) if ln.startswith("facts check: ")),
                    recognition_counts(["known", None, "open_in_literature", "weird", "known"]), recognition_counts([])),
                   (True, True, True, (2, 0, 0, 1, 1, 5), (0, 0, 0, 0, 0, 0)))

    @case("RS2", "A8: the sum K + V + N + O + M = G is asserted (SUM-RECOGNITION, nothing written): a count fed wrong through the pure "
                 "function recognition_counts (one group too many in M) refuses the build, exit 1, OUT_DIR absent; the zoo, which has "
                 "three open groups, builds (a sum that left O out would refuse it)")
    def _():
        real = globals()["recognition_counts"]

        def plant(forms):
            k, v, n, o, m_, g = real(forms)
            return k, v, n, o, m_ + 1, g
        with _patched("recognition_counts", plant):
            b = _build()
        return _eq(([ln for ln in b.out.splitlines() if ln.startswith("BUILD-ERROR SUM-")], b.rc, b.existed, _zbase().rc),
                   (["BUILD-ERROR SUM-RECOGNITION groups 0 known + 0 variant + 0 not recognised + 0 open in literature + 4 not written "
                     "is 4, not 3 groups with a claim"], 1, False, 0))

    @case("RS3", "the first screen and the closed card do not change with a recognition: the facts list and the first-screen text of the "
                 "zoo build are those of the base build, and the evidence section of zrv holds no form line of the recognition (`Our reading: ...`) "
                 "but, since F37, its reader and date (`Our reading of where this statement stands: written by ...`) and its citation's opener")
    def _():
        zf = [li.text() for li in _dom(_zbase().page).find("ul", "facts")[0].find("li")]
        bf = [li.text() for li in _dom(_base().page).find("ul", "facts")[0].find("li")]
        ev = _card(_zbase(), "zrv").find("details", "evidence")[0].text()
        return _eq((zf[:2], zf[2], bf[:2], [p_.text() for p_ in _dom(_zbase().page).find("header")[0].find("p")][:2],
                    "Our reading:" in ev, "Our reading of where this statement stands: written by Reader One on 2026-11-22." in ev),
                   (["Statements read: 1 of 3 steps.", "Proofs read: 1 of 3 steps."], "Questions written down in these notes: 1.",
                    ["Statements read: 1 of 3 steps.", "Proofs read: 1 of 3 steps."],
                    ["First screen paragraph one.", "First screen paragraph two."], False, True))

    @case("P7e", "static_problems and the citation anchor (RULED: an <a class=citation> whose href starts https://, and nothing else): "
                 "controls (https citation anchor, an http reaction anchor): none; planted (an http citation anchor, an https anchor of "
                 "another class, one with no class, a protocol-relative citation href, a href with a space before https, a citation "
                 "class on an img src and on a link href) are each named; the zoo page holds exactly the two https citation anchors "
                 "and the reaction anchors as addresses, and builds")
    def _():
        sp = static_problems
        planted = [('<a class="citation" href="http://x.invalid/">x</a>', ["href=http"]),
                   ('<a class="other" href="https://x.invalid/">x</a>', ["href=http"]),
                   ('<a href="https://x.invalid/">x</a>', ["href=http"]),
                   ('<a class="citation" href="//x.invalid/">x</a>', ["href=http"]),
                   ('<a class="citation" href=" https://x.invalid/">x</a>', ["href=http"]),
                   ('<img class="citation" src="https://x.invalid/a.png">', ["src=http"]),
                   ('<link class="citation" href="https://x.invalid/a.css">', ["href=http"])]
        controls = ['<a class="citation" href="https://x.invalid/">x</a>', '<a class="reaction" href="http://x.invalid/">x</a>',
                    '<a class="citation reaction" href="http://x.invalid/">x</a>']
        return _eq(([sp(h, "") for h, _w in planted], [sp(h, "") for h in controls], ext(_zbase()).count("https://example.invalid/book"),
                    _zbase().rc, static_problems(_zbase().page, _zbase().text("data.js"))),
                   ([w for _h, w in planted], [[], [], []], 2, 0, []))

    # ---- F24b: the strings of the recognition, the sketch and the frames
    def _set(st, path, value):
        node, parts = st, re.findall(r"[^.\[\]]+", path)
        for part in parts[:-1]:
            node = node[int(part)] if part.isdigit() else node[part]
        node[int(parts[-1]) if parts[-1].isdigit() else parts[-1]] = value
        return st

    errs = lambda b_: [x for x in b_.out.splitlines() if x.startswith("BUILD-ERROR")]

    @case("PHR5", "A9: each of the 21 keys that must hold their placeholders (the recognition lines, the three citation lines, "
                  "established_by_line, sketch_frame and the eight Evidence keys) that lacks one of them is "
                  "refused as STRINGS-KEY naming the key and the placeholder (36 cases), exit 1, nothing written; the fixture builds")
    def _():
        res = []
        for key, names in _REQ2:
            for name in names:
                st = _strings()
                st[key] = st[key].replace("{" + name + "}", "")
                b = _build(strings=st)
                res.append((key, name, b.rc, errs(b), b.existed))
        want = [(k, n, 1, [f"BUILD-ERROR STRINGS-KEY {k} is missing the placeholder {{{n}}}"], False) for k, ns in _REQ2 for n in ns]
        return _eq((res, len(res), _base().rc), (want, 36, 0))

    @case("PHR6", "A9: a placeholder the key does not declare is refused naming key and token (`has an unknown placeholder {zzz}`): {zzz} "
                  "added to each of the new keys in turn (the eight Evidence keys too); and each key declares only its own (a {source_date} on "
                  "a known line, on an object line and on the dated citation line, {build} on the source basis, {result} on the label, "
                  "{opened_by} on the undated citation line, {file} on a sketch frame)")
    def _():
        res, want = [], []
        for key in list(WORDING) + ["argument_frame_no_proof"] + list(F37_EVIDENCE):
            st = _strings()
            st[key] = st[key] + " {zzz}"
            b = _build(strings=st)
            res.append((key, b.rc, errs(b), b.existed))
            want.append((key, 1, [f"BUILD-ERROR STRINGS-KEY {key} has an unknown placeholder {{zzz}}"], False))
        for key, tok in (("recognition_result_known_line", "source_date"), ("recognition_object_variant_line", "source_date"),
                         ("recognition_citation_dated_line", "source_date"), ("sketch_basis_source", "build"),
                         ("recognition_label_line", "result"), ("recognition_citation_line", "opened_by"), ("sketch_frame", "file")):
            st = _strings()
            st[key] = st[key] + " {" + tok + "}"
            b = _build(strings=st)
            res.append((key, b.rc, errs(b), b.existed))
            want.append((key, 1, [f"BUILD-ERROR STRINGS-KEY {key} has an unknown placeholder {{{tok}}}"], False))
        return _eq((res, len(res)), (want, 41))

    @case("PHR7", "D1, as F37 left it: argument_frame and argument_frame_no_proof declare NO placeholder: a value with {reader}, {date}, {file} "
                  "or {lines} is refused naming key and token (8 cases); a value with none builds")
    def _():
        bad, ok_ = [], []
        for key in ("argument_frame", "argument_frame_no_proof"):
            for tok in ("reader", "date", "file", "lines"):
                b = _build(strings=_set(_strings(), key, "Frame {" + tok + "}:"))
                bad.append((key, tok, b.rc, errs(b), b.existed))
            b = _build(strings=_set(_strings(), key, "A frame."))
            ok_.append((key, b.rc, errs(b)))
        return _eq((bad, ok_),
                   ([(k, t, 1, [f"BUILD-ERROR STRINGS-KEY {k} has an unknown placeholder {{{t}}}"], False)
                     for k in ("argument_frame", "argument_frame_no_proof") for t in ("reader", "date", "file", "lines")],
                    [("argument_frame", 0, []), ("argument_frame_no_proof", 0, [])]))

    @case("MK1", "A9: with every strings value a distinct marker, a build that shows every new line (the zoo: every role and form, a "
                 "citation anchor, the named-statement line, the established lines; the notes with sketches, both bases, the unexpanded "
                 "list, the missing line; a definition with an argument) builds, and the page shows only markers and data")
    def _():
        o = _zoo()
        notes = _notes_s() | {"07-def.md": N07}
        b = _build(outline=o, notes=notes, strings=_marked(_strings()))
        if b.rc != 0:
            return False, b.out + b.err
        text = " ".join(_dom(b.page).find("body")[0].pieces())
        text = re.sub(r"MARK-[A-Za-z0-9_.]*[A-Za-z0-9_]", " ", text)
        data = json.dumps(o) + DECLS + " ".join(notes.values())
        used = {m_ for m_ in re.findall(r"MARK-[A-Za-z0-9_.]*[A-Za-z0-9_]", b.page)}
        keys = ["MARK-" + k for k in list(WORDING) + ["argument_frame_no_proof"] + list(F37_EVIDENCE)]
        unused = sorted(k for k in keys if k not in used and k != "MARK-recognition_citation_line")
        return _eq((sorted(_words(text) - _words(data)), unused), ([], []))

    # ---- F24b: the argument of a definition
    @case("PB1", "B1: an argument block anchored only on roots that are not a theorem or a lemma is shown under argument_frame_no_proof "
                 "(`What this definition contains:`), never under argument_frame; a block that also anchors a theorem root keeps "
                 "argument_frame (g2 rests on QUUX and BAZ: 07.b01 anchors BAZ only, 07.b02 anchors both); the card's idea is the first "
                 "block; the file and the lines are in the Evidence section, see PV7")
    def _():
        b = _bbase()
        ev = lambda g: [p_.text() for p_ in _card(b, g).find("details", "evidence")[0].find("p", "argument")]
        idea = lambda g: _direct(_card(b, g), "p", "argument")[0].text()
        what1 = "What this definition contains: Def argument sentence."
        what2 = "What this definition contains: Mixed argument sentence."
        return _eq((idea("g1a1"), ev("g1a1"), idea("g2"), ev("g2")),
                   (what1 + " Read the note", [what1 + " Second def sentence.", what2 + " Second mixed sentence."],
                    what1 + " Read the note",
                    [what1 + " Second def sentence.",
                     "How this is proved: Mixed argument sentence. Second mixed sentence."]))

    @case("PB3", "B1, ruled per card (F34): a card speaks about its OWN root. The one block 07.b02 anchors a definition (BAZ) and a theorem "
                 "(QUUX): on g1a1, whose root is the definition, it is shown under argument_frame_no_proof, and on g2, which rests on both, "
                 "under argument_frame, in the same build; the definition's card never says `How this is proved`")
    def _():
        b = _bbase()
        mixed = lambda g: [p_.text() for p_ in _card(b, g).find("details", "evidence")[0].find("p", "argument")
                           if "Mixed argument sentence." in p_.text()]
        d_card = _card(b, "g1a1")
        own = [p_.text() for p_ in d_card.find("details", "evidence")[0].find("p", "argument")] + [_direct(d_card, "p", "argument")[0].text()]
        return _eq((mixed("g1a1"), mixed("g2"), any("How this is proved" in x for x in own)),
                   (["What this definition contains: Mixed argument sentence. Second mixed sentence."],
                    ["How this is proved: Mixed argument sentence. Second mixed sentence."], False))

    @case("SK10", "C1/F25: a sketch belongs to the group named in its note's HEADER (the group notes_meta checks it against), never to another "
                  "group whose root is only among its further `decls`: the note headed g1 whose sketch lists FOO (the root of g1) and CORGE (the "
                  "root of g3) shows on g1's card and in group/g1.json only; g3, whose proof is read, shows its own missing-sketch line and "
                  "no sketch, and its JSON has none and no sketch block; the page holds one sketch; `sketches: 1 of 2 steps with a proof read`")
    def _():
        b = _build(notes=_notes_s(decls=[FOO, CORGE]))
        dom = _dom(b.page)
        g3 = _card(b, "g3")
        return _eq((b.rc, [a.attrs["id"] for a in dom.find("article") if _direct(a, "div", "sketch")], len(dom.find("div", "sketch")),
                    [x["block"] for x in b.js("group/g1.json")["sketches"]], b.js("group/g3.json")["sketches"],
                    [x["block"] for x in b.js("group/g3.json")["blocks"]], len(_direct(g3, "div", "sketch")), len(_direct(g3, "p", "sketch-missing")),
                    "sketches: 1 of 2 steps with a proof read" in b.out.splitlines()),
                   (0, ["g1", "g1a"], 2, ["04.b01"], [], ["06.b01"], 0, 1, True))

    @case("PB2", "B2: the not-applicable line STAYS on a card whose root is a definition with an argument block (`Proof: none to read, this is "
                 "not a theorem.`), and proof_read stays null for it (the root, the group summary, the counts: 0 read of 0 that have a "
                 "proof): an argument block there sets nothing; the theorem root of g2 is read by the block that anchors it")
    def _():
        b = _bbase()
        g1a1 = b.js("level1.json")["steps"][0]["children"][0]["children"][0]
        return _eq((_card(b, "g1a1").find("p", "proof")[0].text(), b.js("group/g1a1.json")["roots"][0]["proof_read"], g1a1["id"],
                    g1a1["proof_read"], g1a1["counts"]["roots_proof_read"], g1a1["counts"]["roots_proof_applicable"], g1a1["unread"],
                    [r["proof_read"] for r in b.js("group/g2.json")["roots"]], _card(b, "g2").find("p", "proof")[0].text()),
                   ("Proof: none to read, this is not a theorem.", None, "g1a1", None, 0, 0, False, [True, None],
                    "Proofs read: 1 of 1 declarations."))

    # ---- F29: the frame of a block
    @case("DF1", "D1, as F37 left it: the file is shown by its BASE NAME and the lines as the range only, in the Evidence section and not in the "
                 "frame: a block whose file is `A/Deep/Nest.lean` shows `Nest.lean` and `15-18` there and never the directory, the card and the "
                 "frame show neither, while the JSON keeps the path as written; a block with a file and no lines shows `TopPlug.lean` and "
                 "`not given` through lines_missing")
    def _():
        b = _build(notes=_notes() | {"01-one.md": _n01().replace("A/B.lean", "A/Deep/Nest.lean")})
        c = _card(b, "g1")
        idea = _direct(c, "p", "argument")[0].text()
        full = c.find("details", "evidence")[0].find("p", "argument")[0].text()
        g2 = _bbase()
        pin = pairs(blk(g2, "g2", "07.b02"))
        return _eq((idea, full, b.js("group/g1.json")["blocks"][1]["file"], b.js("group/g1.json")["blocks"][1]["lines"],
                    pairs(blk(b, "g1", "01.b02")), "Deep" in surface(_dom(b.page)), pin),
                   ("How this is proved: First argument sentence. Read the note",
                    "How this is proved: First argument sentence. Second argument sentence.",
                    "A/Deep/Nest.lean", [15, 18], [[("File", "Nest.lean"), ("Lines", "15-18")]], False,
                    [[("File", "TopPlug.lean"), ("Lines", "not given")]]))

    @case("DF3", "D2, as F37 left it: the second-reader line is in the Evidence section only, AFTER the block's text and its file and lines "
                 "(evidence: the paragraph frame + both sentences, then the file and lines, then `Read again by Reader Two on 2026-11-24.`; "
                 "card: frame, the first sentence, the link, no second-reader line); a block without a second reader and without a file shows "
                 "`not given` twice; a block with no text (an argument on a list) still shows its file, its lines and its second-reader "
                 "line in Evidence, and on the card the frame and the link only")
    def _():
        c = _card(_base(), "g1")
        li = blk(_base(), "g1", "01.b02")
        full = li.find("p", "argument")[0].text()
        g3 = blk(_sbase(), "g3", "06.b01")
        g3 = (g3.find("p", "argument")[0].text(), pairs(g3), [p_.text() for p_ in g3.find("p", "second-reader")])
        arg_list = ("- ListItemTextXYZ one\n- ListItemTextXYZ two\n"
                    + _b(id="02.b03", kind="argument", decls=[QUX], item=1, reader="Reader Two", date="2026-11-23",
                         file="A/Deep/TopPlug.lean", second_readers=[{"reader": "Reader Three", "date": "2026-11-25"}]) + "\n"
                    "\n## Files this note was written from\n\n| File | SHA-256 |\n|---|---|\n| `A/Deep/TopPlug.lean` | `x` |\n")
        b = _build(notes=_notes() | {"02-two.md": N02 + "\n" + arg_list})
        x = _card(b, "g1a1x")
        xl = next(l_ for l_ in x.find("details", "evidence")[0].find("ul", "blocks")[0].elems() if "02.b03" in _raw(l_))
        order = [(k.tag, k.cls[-1] if k.cls else "") for k in li.elems()][3:]
        return _eq((order, full, g3, b.rc, _direct(x, "p", "argument")[0].text(), len(x.find("details", "evidence")[0].find("p", "argument")),
                    pairs(xl), [p_.text() for p_ in xl.find("p", "second-reader")]),
                   ([("p", "argument"), ("dl", "block-source"), ("p", "second-reader")],
                    "How this is proved: First argument sentence. Second argument sentence.",
                    ("How this is proved: Corge argument sentence. Second corge sentence.", [[("File", "not given"), ("Lines", "not given")]], []), 0,
                    "How this is proved: Read the note", 0, [[("File", "TopPlug.lean"), ("Lines", "not given")]],
                    ["Read again by Reader Three on 2026-11-25."]))

    # ---- F25b: the sketch
    skd = lambda c: [(k.tag, " ".join(k.cls), [_raw(li) for li in k.elems()] if k.tag in ("ul", "ol") else _raw(k))
                     for k in _direct(c, "div", "sketch")[0].elems()]
    note_line = "A sketch for a reader, not a proof: it leaves steps out and may hide the hard part."

    @case("SK1", "C1: group/<id>.json has `sketches`, a list (empty when none), one entry per sketch block in note id then block order, with "
                 "note, block, reader, date, basis, build (null when the basis is source), unexpanded (a list, empty when absent), roots "
                 "and blocks: a paragraph {type, text}, a list {type, ordered, items} (ordered for `1)`, not for `-`), every text as written "
                 "(backticks and the link kept); the step summaries have no `sketches`; the sketch is also a block of the group (kind sketch)")
    def _():
        b = _sbase()
        g1, g1a = b.js("group/g1.json"), b.js("group/g1a.json")
        want1 = [{"basis": "compiled", "block": "04.b01", "build": "lake build A.B", "date": "2026-11-24", "note": "04",
                  "reader": "Reader Two", "roots": [{"module": "A.B", "name": "foo"}],
                  "unexpanded": ["Closed by `omega` automation.", "A last `simp` call."],
                  "blocks": [{"type": "paragraph", "text": "First sketch paragraph with `a span`."},
                             {"type": "list", "ordered": True, "items": ["Ordered item one.", "Ordered item `two` here."]},
                             {"type": "paragraph", "text": "Last sketch paragraph, see [note 6](06-x.md)."}]}]
        want2 = [{"basis": "source", "block": "05.b02", "build": None, "date": "2026-11-24", "note": "05", "reader": "Reader Two",
                  "roots": [{"module": "A.B", "name": "bar"}], "unexpanded": [],
                  "blocks": [{"type": "paragraph", "text": "Opening paragraph of the bar sketch."},
                             {"type": "list", "ordered": False, "items": ["Bullet one.", "Bullet two."]},
                             {"type": "paragraph", "text": "Closing paragraph of the bar sketch."}]}]
        return _eq((g1["sketches"], g1a["sketches"], b.js("group/g2.json")["sketches"], b.js("group/g3.json")["sketches"],
                    [b_["block"] for b_ in g1["blocks"]], g1["blocks"][-1],
                    ["sketches" in s for s in b.js("level0.json")["steps"]], _base().js("group/g1.json")["sketches"]),
                   (want1, want2, [], [], ["01.b01", "01.b02", "01.b03", "01.b06", "02.b02", "04.b01"],
                    {"block": "04.b01", "date": "2026-11-24", "kind": "sketch", "note": "04", "reader": "Reader Two",
                     "roots": [{"module": "A.B", "name": "foo"}]}, [False] * 3, []))

    @case("SK2", "C2: the card shows the sketch after the argument: the frame (F37: the basis only, `from the goals Lean shows when this part of "
                 "the release is compiled` or `from reading the Lean source`, no reader, no date, no build), the paragraphs as <p> and the lists "
                 "as <ol> or <ul> with <li> (the span rule on every text, the link as its text), the unexpanded heading and list when there "
                 "are entries, the sketch note; a build string that holds `{date}` is shown as written in the Evidence line (one pass)")
    def _():
        b = _sbase()
        c, a = _card(b, "g1"), _card(b, "g1a")
        frame = "The proof in order, "
        names = lead(c)
        two = blk(_build(notes=_notes_s(build="lake build {date}")), "g1", "04.b01").find("p", "sketch-build")[0].text()
        return _eq((skd(c), skd(a), [c_.text() for c_ in _direct(c, "div", "sketch")[0].find("code")],
                    names.index(("p", "argument")) < names.index(("div", "sketch")) < names.index(("ul", "reactions")), two),
                   ([("p", "frame sketch-frame", frame + "from the goals Lean shows when this part of the release is compiled:"),
                     ("p", "", "First sketch paragraph with a span."), ("ol", "", ["Ordered item one.", "Ordered item two here."]),
                     ("p", "", "Last sketch paragraph, see note 6."),
                     ("p", "unexpanded-heading", "Places where Lean finishes the proof by automation we have not opened up:"),
                     ("ul", "unexpanded", ["Closed by omega automation.", "A last simp call."]), ("p", "sketch-note", note_line)],
                    [("p", "frame sketch-frame", frame + "from reading the Lean source:"),
                     ("p", "", "Opening paragraph of the bar sketch."), ("ul", "", ["Bullet one.", "Bullet two."]),
                     ("p", "", "Closing paragraph of the bar sketch."), ("p", "sketch-note", note_line)],
                    ["a span", "two", "omega", "simp"], True,
                    "Proof sketch from a compiled part of the release: lake build {date}."))

    @case("SK3", "C2: with no sketch the card shows `Proof sketch: not written yet.` ONLY when its proof is read (base: g1; with the sketch "
                 "notes: g3, since g1 and g1a have sketches); a card whose proof is not read (g3, g2, g1a, g1a1x) or not applicable (g1a1, a "
                 "definition) shows nothing for it")
    def _():
        ids = lambda b_: sorted(a.attrs["id"] for a in _dom(b_.page).find("article") if _direct(a, "p", "sketch-missing"))
        return _eq((ids(_base()), ids(_sbase()), _raw(_direct(_card(_base(), "g1"), "p", "sketch-missing")[0])),
                   (["g1"], ["g3"], "Proof sketch: not written yet."))

    @case("SK4", "C2: a sketch NEVER sets proof_read, the argument block does: the model of a note with a sketch on the root of g1a and no "
                 "argument (the checker refuses that first in a run, so the model is called directly) has proof_read False for the root and "
                 "the group, and still lists the sketch; control: with the argument block (the notes with sketches) proof_read is True")
    def _():
        n05 = ("# Note five\n" + _h(id="05", group="g1a", list_title="Note five") + "\n\n## Body\n\n"
               "Opening paragraph of the bar sketch.\n\n- Bullet one.\n- Bullet two.\n\nClosing paragraph of the bar sketch.\n"
               + _b(id="05.b02", kind="sketch", decls=[BAR], reader="Reader Two", date="2026-11-24", basis="source", span=3) + "\n")
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d, notes=_notes() | {"05-bar.md": n05})
            m = _model(p["notes"], json.load(open(p["outline"])), _decl_rows(p["decls"]), _strings(), None, [])
        return _eq((m.files["g1a"]["roots"][0]["proof_read"], m.summary["g1a"]["proof_read"], len(m.files["g1a"]["sketches"]),
                    _sbase().js("group/g1a.json")["roots"][0]["proof_read"]), (False, False, 1, True))

    @case("SK5", "C3: the run prints `sketches: S of P steps with a proof read`, P the level-1 steps with a proof read and S those that "
                 "carry a sketch (the nested g1a has a sketch and a proof read and is NOT counted: 1 of 2 with the sketch notes, 0 of 1 "
                 "in the base); the pure function sketch_counts counts a sketch only on a step whose proof is read; S <= P is asserted "
                 "(SUM-SKETCH, nothing written): fed 3 of 2 through the function the build is refused, exit 1, OUT_DIR absent")
    def _():
        with _patched("sketch_counts", lambda rows: (3, 2)):
            bad = _build(notes=_notes_s())
        return _eq(("sketches: 1 of 2 steps with a proof read" in _sbase().out.splitlines(),
                    "sketches: 0 of 1 steps with a proof read" in _base().out.splitlines(),
                    sketch_counts([(True, True), (True, False), (False, True), (None, True)]), sketch_counts([]),
                    [ln for ln in bad.out.splitlines() if ln.startswith("BUILD-ERROR SUM-")], bad.rc, bad.existed),
                   (True, True, (1, 2), (0, 0),
                    ["BUILD-ERROR SUM-SKETCH steps 3 steps with a sketch, but only 2 steps have a proof read"], 1, False))

    @case("SK6", "C4: the source check compares what a reader sees in the new places: a release line inside single backticks as the "
                 "recognition's result, difference, a citation's source or where (files data.js, group/g1.json, level0.json, level1.json) or "
                 "as a sketch paragraph, list item or unexpanded entry (data.js, group/g1.json) is SOURCE-LEAK, exit 1, OUT_DIR absent; "
                 "doubled backticks (compared as written) and an unrelated text build, exit 0")
    def _():
        src = {"A/B.lean": "x\n" + LEAK + "\n"}
        states = (("wrapped", "`" + LEAK + "`"), ("doubled", "``" + LEAK + "``"), ("plain", "An unrelated sentence of ours here."))
        files = lambda b_: sorted(ln.split(" ")[2] for ln in b_.out.splitlines()
                                  if ln.startswith("BUILD-ERROR SOURCE-LEAK ") and not ln.startswith("BUILD-ERROR SOURCE-LEAK note "))
        res, want = [], []
        for field in ("result", "difference", "source", "where"):
            for name, v in states:
                b = _build(outline=_outline_r(field, v), src=src)
                res.append((field, name, b.rc, files(b), b.existed))
                want.append((field, name, *((1, ["data.js", "group/g1.json", "level0.json", "level1.json"], False) if name == "wrapped"
                                            else (0, [], True))))
        for field in ("para", "item", "unexpanded"):
            for name, v in states:
                b = _build(notes=_notes_s(**{field: (v,) if field == "unexpanded" else v}), src=src)
                res.append((field, name, b.rc, files(b), b.existed))
                want.append((field, name, *((1, ["data.js", "group/g1.json"], False) if name == "wrapped" else (0, [], True))))
        return _eq(res, want)

    @case("SK7", "C5: the page with sketches is static: static_problems is empty on the page and data.js, there is no <script>, the "
                 "sketch holds only the elements p, ol, ul, li and code, and the only addresses on the page are the reaction anchors")
    def _():
        b = _sbase()
        sk = _direct(_card(b, "g1"), "div", "sketch")[0]
        hrefs = ext(b)
        return _eq((static_problems(b.page, b.text("data.js")), len(_dom(b.page).find("script")), sorted({n.tag for n in sk.nodes()}),
                    len(hrefs), all(h.startswith("https://example.invalid/react?") for h in hrefs), b.rc),
                   ([], 0, ["code", "li", "ol", "p", "ul"], 18, True, 0))

    @case("SK8", "C6: the evidence list of a card names a sketch block by labels.kinds.sketch (`Proof sketch`) beside the other kinds, and "
                 "shows no text of the sketch for it (the sketch is on the card; F37: only the build line, a paragraph of its own)")
    def _():
        items = _card(_sbase(), "g1").find("details", "evidence")[0].find("ul", "blocks")[0].elems()
        return _eq(([li.find("span", "kind")[0].text() for li in items], [p_.cls for p_ in items[-1].find("p")], len(items[-1].find("aside"))),
                   (["Reading", "Argument", "Interpretation", "Correction", "Reading", "Proof sketch"], [["sketch-build"]], 0))

    @case("FR5", "FORMULA-RAW covers the sketch: a `$`, `\\(` or `\\[` in a sketch paragraph or list item outside a code span lists the block, "
                 "once (`FORMULA-RAW 04.b01`), exit 0; the same inside a code span, and a plain `5`, do not; the default sketch does not")
    def _():
        res = []
        for kw in ({"para": "Cost is $5 here."}, {"item": "It uses \\(x\\) here."}, {"para": "`$5` and 5 only."},
                   {"last": "Ends with \\[y\\] and $z$."}, {}):
            b = _build(notes=_notes_s(**kw))
            res.append((b.rc, [ln for ln in b.out.splitlines() if ln.startswith("FORMULA-RAW")]))
        return _eq(res, [(0, ["FORMULA-RAW 04.b01"]), (0, ["FORMULA-RAW 04.b01"]), (0, []), (0, ["FORMULA-RAW 04.b01"]), (0, [])])

    # ---- F30: a link inside block text is shown as its text
    lk = lambda b_: [ln for ln in b_.out.splitlines() if ln.startswith("links in block text") or ln.startswith("LINK-OUTSIDE")]

    @case("LK1", "E1 E2: `[note 6](06-x.md)` and `[site](https://example.org)` in an argument show `note 6` and `site` only: neither bracket, "
                 "parenthesis nor target on the card's first sentence or in the evidence, NO anchor is made (the evidence paragraph has no "
                 "<a>, the card's idea only its read-more link, no address example.org anywhere on the page), the JSON and data.js keep "
                 "the text and the first sentence as written; the run prints `links in block text: 2 shown as text` and lists "
                 "`LINK-OUTSIDE 01.b02 https://example.org` (the target is not a note of the build), exit 0")
    def _():
        text = "See [note 6](06-x.md) now. Then [site](https://example.org) too."
        b = _build(notes=_notes_e(arg_text=text))
        c = _card(b, "g1")
        idea = _direct(c, "p", "argument")[0]
        full = c.find("details", "evidence")[0].find("p", "argument")[0]
        blk = b.js("group/g1.json")["blocks"][1]
        junk = lambda p_: [x for x in ("[", "]", "06-x.md", "example.org") if x in _raw(p_)]
        return _eq((b.rc, idea.text(), full.text(), junk(idea), junk(full), len(idea.find("a")), len(full.find("a")), "example.org" in b.page,
                    blk["text"], blk["first_sentence"], "See [note 6](06-x.md) now." in b.text("data.js"), lk(b)),
                   (0, "How this is proved: See note 6 now. Read the note",
                    "How this is proved: See note 6 now. Then site too.", [], [], 1, 0, False, text, "See [note 6](06-x.md) now.", True,
                    ["links in block text: 2 shown as text", "LINK-OUTSIDE 01.b02 https://example.org"]))

    @case("LK2", "E1 E2: what is a link, pinned: `[a](06-x.md#sec)` is a link to a note (the part before # is the file name, not listed), "
                 "`[b](99-missing.md)`, `[d](https://example.org/p#f)` and `[e]()` are links listed LINK-OUTSIDE in text order; a bare `[x]` "
                 "stays, a link inside single backticks stays and is not counted, an image `![img](06-x.md)` is not touched (left as written "
                 "text, not counted, no anchor): 4 shown as text")
    def _():
        text = ("First [a](06-x.md#sec) and [b](99-missing.md) and [x] and `[c](06-x.md)` and [d](https://example.org/p#f) and [e]() "
                "and ![img](06-x.md) end. Last.")
        b = _build(notes=_notes_e(arg_text=text))
        c = _card(b, "g1")
        idea = _direct(c, "p", "argument")[0]
        return _eq((b.rc, idea.text(), [x.text() for x in idea.find("code")], len(idea.find("a")), lk(b)),
                   (0, "How this is proved: First a and b and [x] and [c](06-x.md) and d and e and ![img](06-x.md) end. Read the note",
                    ["[c](06-x.md)"], 1,
                    ["links in block text: 4 shown as text", "LINK-OUTSIDE 01.b02 99-missing.md",
                     "LINK-OUTSIDE 01.b02 https://example.org/p#f", "LINK-OUTSIDE 01.b02"]))

    @case("LK3", "E1 E2: the rule is for argument, interpretation and sketch text alike (an interpretation with two links, a sketch paragraph "
                 "and a sketch list item with one each: 4 shown as text, only `https://x.example` listed, with its block id 01.b03), and "
                 "not for a claim: a claim holding `[cl](06-x.md)` is shown as written and not counted")
    def _():
        o = _outline()
        next(g for g in o["groups"] if g["id"] == "g1")["claim"]["text"] = "Claim one [cl](06-x.md)"
        notes = _notes_s(item="Item with [list link](06-x.md#s) here.")
        notes["01-one.md"] = _n01(interp_text="We think [n](06-x.md) and [o](https://x.example) hold.")
        b = _build(outline=o, notes=notes)
        c = _card(b, "g1")
        aside = c.find("aside")[0].find("p", "interpretation")[0]
        return _eq((b.rc, aside.text(), c.find("h3", "claim")[0].text(), [x[2] for x in skd(c) if x[0] == "ol"], lk(b)),
                   (0, "What we think it means: We think n and o hold.", "Claim one [cl](06-x.md)",
                    [["Ordered item one.", "Item with list link here."]],
                    ["links in block text: 4 shown as text", "LINK-OUTSIDE 01.b03 https://x.example"]))

    @case("LK4", "E3: the source check still sees a release line placed in a link: the compare runs on the text as written, on the text with "
                 "its span backticks removed and on the SHOWN text (each link as its text), and each link target is compared as a line too: "
                 "a release line as the text of a link is SOURCE-LEAK (data.js, group/g1.json, index.html), as the target of a link "
                 "(a single token of 20 characters or more) in data.js and group/g1.json only; control: a link to a note builds")
    def _():
        tok = "leak_token_of_the_release_x1"
        res = []
        for text, line in (("[" + LEAK + "](06-x.md)", LEAK), ("Look at [here](" + tok + ") now.", tok), ("See [note](06-x.md) now.", LEAK)):
            b = _build(notes=_notes_e(arg_text=text), src={"A/B.lean": "x\n" + line + "\n"})
            res.append((b.rc, sorted(ln.split(" ")[2] for ln in b.out.splitlines()
                                     if ln.startswith("BUILD-ERROR SOURCE-LEAK ") and not ln.startswith("BUILD-ERROR SOURCE-LEAK note ")),
                        b.existed))
        return _eq(res, [(1, ["data.js", "group/g1.json", "index.html"], False), (1, ["data.js", "group/g1.json"], False), (0, [], True)])

    @case("LK5", "E1: the one rule `_rich(text, links=True)`: a link is its text (escaped), a code span is code, and a link never starts inside "
                 "one (a span binds tighter: `[a `b](c)` d` is text and a span); a link text may hold a span; a bare pair, an unclosed "
                 "link, an image, a target with a space, an empty text, a link of a link stay as written; without links=True a link is "
                 "text as written (claims, titles); _link_targets lists the targets of the links outside code spans, in order")
    def _():
        got = [_rich(t, links=True) for t in ("[note 6](06-x.md)", "x [a `b` c](d.md) y", "`[a](b)`", "[a `b](c)` d", "[x]", "[a](b",
                                              "![a](b)", "[a](b c)", "[](x)", "[a](b)(c)", "[a [b] c](d)", "[<i>](x)", "a & b")]
        return _eq((got, _rich("[a](b)"), _link_targets("see [a](b.md) and `[c](d)` and [e](f#g) and ![i](j)")),
                   (["note 6", "x a <code>b</code> c y", "<code>[a](b)</code>", "[a <code>b](c)</code> d", "[x]", "[a](b", "![a](b)",
                     "[a](b c)", "[](x)", "a(c)", "[a [b] c](d)", "&lt;i&gt;", "a &amp; b"], "[a](b)", ["b.md", "f#g"]))

    # ---- F35: bold and nested items in block text, and the code wrap rule
    def _bn(arg="First argument sentence. Second argument sentence.", interp="We think this is the key step.", **sk):
        return _notes(arg_text=arg, interp_text=interp) | {"04-sketch.md": _n04(**sk), "05-bar.md": N05, "06-x.md": N06}

    def _skn(body, span=3):
        n = ("# Note four\n" + _h(id="04", group="g1", list_title="Note four") + "\n\n## Body\n\n" + body
             + _b(id="04.b01", kind="sketch", decls=[FOO], reader="Reader Two", date="2026-11-24", basis="source", span=span) + "\n")
        return _notes() | {"04-sketch.md": n}

    own = lambda li: "".join(k for k in li.kids if isinstance(k, str)).strip()
    listing = lambda b_: [ln for ln in b_.out.splitlines() if ln.split(" ")[0] in ("FORMULA-RAW", "BOLD-UNPAIRED", "NEST-DEPTH")]

    @case("BD1", "F35 B1: `_rich(text, links=True)` shows a pair of double asterisks on one line around text as <strong>, its content through "
                 "the span rule (`**a `b` c**` is <strong>a <code>b</code> c</strong>); an asterisk in a code span is code; an empty pair, a "
                 "run of three or more asterisks, a pair of blanks and a pair over a line break stay literal; single asterisks and underscores "
                 "stay text; two pairs are two <strong>; a link is shown first (`[**a**](x)` and `**see [a](b)**` are <strong>); the text of "
                 "a claim or a title (no links=True) keeps its asterisks")
    def _():
        got = [_rich(t, links=True) for t in ("a **b** c", "**a `b` c**", "`**x**`", "****", "a **** b", "**a\nb**", "**a\rb**", "*a* _b_ a * b",
                                              "**a** and **b**", "**x", "x**", "**a** **b", "[**a**](x.md)", "**see [a](b.md)**", "**a & b**",
                                              "****a****", "***a***", "** **", "**a*b**")]
        return _eq((got, _rich("**a**"), _rich("a **b**")),
                   (["a <strong>b</strong> c", "<strong>a <code>b</code> c</strong>", "<code>**x**</code>", "****", "a **** b", "**a\nb**",
                     "**a\rb**", "*a* _b_ a * b", "<strong>a</strong> and <strong>b</strong>", "**x", "x**", "<strong>a</strong> **b",
                     "<strong>a</strong>", "<strong>see a</strong>", "<strong>a &amp; b</strong>", "****a****", "***a***", "** **",
                     "<strong>a*b</strong>"], "**a**", "a **b**"))

    @case("BD2", "F35 B2: `_bold_unpaired(text)` is True when a `**` is left over once the code spans, the links and the bold pairs are taken "
                 "out (`**x`, `x **`, `**a** **b`, `****`), False for a text with only pairs, one with single asterisks, and one whose `**` is "
                 "inside a code span")
    def _():
        t = ("**x", "x **", "**a** **b", "****", "**a** b", "*a* b", "`**` ok", "a `**x` b", "[**a**](x.md)", "no marks")
        return _eq([_bold_unpaired(x) for x in t], [True, True, True, True, False, False, False, False, False, False])

    @case("BD3", "F35 B1: bold is <strong> on the page in every place block text is shown: the first sentence on the closed card, the full text "
                 "of an argument and of an interpretation (evidence list), a sketch paragraph, a sketch item, a sub-item; a sketch's "
                 "`unexpanded` entry keeps its asterisks; the JSON and data.js keep the text as written")
    def _():
        arg = "First **argument** sentence. Second **one** sentence."
        b = _build(notes=_bn(arg=arg, interp="We **think** so.", para="First **bold** para.", item="Item **two** here.\n   - sub **s**",
                             last="Last **end**.", unexpanded=("Closed by **omega** automation.",)))
        c = _card(b, "g1")
        st = lambda node: [s.text() for s in node.find("strong")]
        ev = c.find("details", "evidence")[0]
        sk = _direct(c, "div", "sketch")[0]
        return _eq((b.rc, st(_direct(c, "p", "argument")[0]), st(ev.find("p", "argument")[0]), st(ev.find("p", "interpretation")[0]),
                    [st(p) for p in sk.find("p") if "frame" not in p.cls and "sketch-note" not in p.cls and "unexpanded-heading" not in p.cls],
                    st(sk.find("ol")[0]), st(sk.find("ul", "unexpanded")[0]), [li.text() for li in sk.find("ul", "unexpanded")[0].find("li")],
                    "First **bold** para." in b.text("data.js"), b.js("group/g1.json")["sketches"][0]["blocks"][0]["text"]),
                   (0, ["argument"], ["argument", "one"], ["think"], [["bold"], ["end"]], ["two", "s"], [], ["Closed by **omega** automation."],
                    True, "First **bold** para."))

    @case("BD8", "F35 B1: bold is <strong> in a plain sketch item, in the own text of an item with sub-items and in a sub-item, each in its "
                 "own <li>")
    def _():
        body = "Opening.\n\n- Plain **one** item\n- Step **two**\n  - sub **s** and `c`\n- Plain three\n\nClosing.\n"
        ul = _direct(_direct(_card(_build(notes=_skn(body)), "g1"), "div", "sketch")[0], "ul")[0]
        return _eq([[x.text() for x in li.find("strong")] for li in ul.find("li")], [["one"], ["two", "s"], ["s"], []])

    @case("BD4", "F35 B2: an unpaired `**` stays literal on the page and is listed, once per block, `BOLD-UNPAIRED <block id>`, after the "
                 "FORMULA-RAW lines (note order), exit 0, nothing refused; a `**` inside a code span, a pair and single asterisks are not "
                 "listed; a first sentence cut inside a pair (`**one. Two**`) shows a literal `**` and lists the block")
    def _():
        res = []
        for kw in ({"arg": "Cost $5 and **x and y."}, {"para": "Also **y here."}, {"last": "A `**` code and *one* and **two**."},
                   {"arg": "Take **one. Two** steps."}, {}):
            b = _build(notes=_bn(**kw))
            res.append((b.rc, listing(b), b.existed))
        lit = _build(notes=_bn(para="Also **y here."))
        return _eq((res, "Also **y here." in [p.text() for p in _direct(_card(lit, "g1"), "div", "sketch")[0].find("p")]),
                   ([(0, ["FORMULA-RAW 01.b02", "BOLD-UNPAIRED 01.b02"], True), (0, ["BOLD-UNPAIRED 04.b01"], True), (0, [], True),
                     (0, ["BOLD-UNPAIRED 01.b02"], True), (0, [], True)], True))

    @case("BD5", "F35 B1/B2: bold inside a link text (the link text is shown first, then the bold) is <strong> and the link target is "
                 "not bold; the same in a sketch item")
    def _():
        b = _build(notes=_bn(para="See [**note**](06-x.md) and **[note](06-x.md)** now."))
        p = [x for x in _direct(_card(b, "g1"), "div", "sketch")[0].find("p") if x.text().startswith("See")][0]
        return _eq((b.rc, [s.text() for s in p.find("strong")], p.text(), [ln for ln in b.out.splitlines() if ln.startswith("LINK-OUTSIDE")]),
                   (0, ["note", "note"], "See note and note now.", []))

    @case("BD6", "F35 E1: <strong> and the nested <ul> are the only elements a sketch holds beyond p, ol, ul, li and code (SK7's list plus strong "
                 "on a fixture with bold and sub-items); static_problems is empty on the page and data.js, there is no <script>, the only "
                 "addresses are the reaction anchors; static_problems still refuses a planted `<script>fetch(`")
    def _():
        b = _build(notes=_bn(para="First **bold** para.", item="Item two.\n   - sub one\n   - sub `two`"))
        sk = _direct(_card(b, "g1"), "div", "sketch")[0]
        hrefs = ext(b)
        return _eq((static_problems(b.page, b.text("data.js")), len(_dom(b.page).find("script")), sorted({n.tag for n in sk.nodes()}),
                    all(h.startswith("https://example.invalid/react?") for h in hrefs), b.rc,
                    static_problems("<script>fetch('a')</script><strong>x</strong><ul><li>a<ul><li>b</li></ul></li></ul>", "")),
                   ([], 0, ["code", "li", "ol", "p", "strong", "ul"], True, 0, ["fetch("]))

    @case("BD7", "F35: <strong> is emitted only where a bold pair is: the page of a sketch with `**bold**` is, once its <strong> tags are "
                 "taken out, byte-equal to the page of the same sketch with the asterisks removed; a bold-free page (the sketch base) holds "
                 "no <strong> and no <ul> inside an <li>")
    def _():
        a = _build(notes=_bn(para="First **bold** para.", arg="First **argument** sentence."))
        z = _build(notes=_bn(para="First bold para.", arg="First argument sentence."))
        strip = lambda p: p.replace("<strong>", "").replace("</strong>", "")
        base = _dom(_sbase().page)
        return _eq((strip(a.page) == z.page, "<strong>" in a.page, "<strong>" in _sbase().page, "<strong>" in z.page,
                    len([u for u in base.find("ul") if u.parent is not None and u.parent.tag == "li"])),
                   (True, True, False, False, 0))

    @case("NS1", "F35 N1: in a sketch run the indented `- ` or `* ` lines of a list item are its sub-items: the JSON item is {text, items} "
                 "(items without sub-items stay plain strings, no `items` key), the text before the first sub-item is the item's own, a "
                 "continuation line joins the item or the sub-item it follows, an indented numbered line is not special (a continuation, as "
                 "today); the page shows ONE nested <ul> inside that item's <li>, after its own text, each sub-item through the span rule and "
                 "the bold rule; the other item has no <ul>")
    def _():
        body = ("Opening paragraph.\n\n- Step one\n  continues here\n  - sub a **bold** with `c`\n  * sub b\n    cont b\n  1) numbered line\n"
                "- Step two\n\nClosing paragraph.\n")
        b = _build(notes=_skn(body))
        blocks = b.js("group/g1.json")["sketches"][0]["blocks"]
        ul = _direct(_direct(_card(b, "g1"), "div", "sketch")[0], "ul")[0]
        lis = ul.elems()
        subs = lis[0].find("ul")
        return _eq((b.rc, blocks[1], [own(li) for li in lis], len(subs), [li.text() for li in subs[0].elems()], [s.text() for s in lis[0].find("strong")],
                    [c.text() for c in lis[0].find("code")], len(lis[1].find("ul")), [k.tag for k in lis[0].elems()]),
                   (0, {"type": "list", "ordered": False,
                        "items": [{"text": "Step one continues here", "items": ["sub a **bold** with `c`", "sub b cont b 1) numbered line"]},
                                  "Step two"]},
                    ["Step one continues here", "Step two"], 1, ["sub a bold with c", "sub b cont b 1) numbered line"], ["bold"], ["c"], 0,
                    ["ul"]))

    @case("NS2", "F35 N1: a sub-item of a numbered item is nested too (`   - ` under `2)`); a list whose items have no sub-items has the same JSON "
                 "and page as before: plain string items, no nested <ul> (the base sketch)")
    def _():
        b = _build(notes=_bn(item="Item two here.\n   - sub one\n   - sub two"))
        blocks = b.js("group/g1.json")["sketches"][0]["blocks"]
        ol = _direct(_direct(_card(b, "g1"), "div", "sketch")[0], "ol")[0]
        base = _sbase().js("group/g1.json")["sketches"][0]["blocks"][1]
        return _eq((blocks[1], [len(li.find("ul")) for li in ol.elems()], base,
                    [type(x).__name__ for x in base["items"]]),
                   ({"type": "list", "ordered": True, "items": ["Ordered item one.", {"text": "Item two here.", "items": ["sub one", "sub two"]}]},
                    [0, 1], {"type": "list", "ordered": True, "items": ["Ordered item one.", "Ordered item `two` here."]}, ["str", "str"]))

    @case("NS3", "F35 N1: a deeper level (a line indented further than the first sub-item and starting with a marker) is shown flat, joined into "
                 "its parent sub-item, and LISTED `NEST-DEPTH <block id>` once per block (two deep lines in two items: one line); no nested "
                 "<ul> at depth 2; exit 0; a list with one level only is not listed")
    def _():
        deep = ("Opening.\n\n- Step one\n  - a\n    - deep one\n    - deep two\n  - b\n- Step two\n  - c\n    - deeper\n\nClosing.\n")
        flat = "Opening.\n\n- Step one\n  - a\n  - b\n\nClosing.\n"
        d, f = _build(notes=_skn(deep)), _build(notes=_skn(flat))
        ul = _direct(_direct(_card(d, "g1"), "div", "sketch")[0], "ul")[0]
        return _eq((d.rc, listing(d), d.js("group/g1.json")["sketches"][0]["blocks"][1]["items"],
                    len(_direct(_card(d, "g1"), "div", "sketch")[0].find("ul")), [len(li.find("ul")) for li in ul.elems()], f.rc, listing(f)),
                   (0, ["NEST-DEPTH 04.b01"],
                    [{"text": "Step one", "items": ["a - deep one - deep two", "b"]}, {"text": "Step two", "items": ["c - deeper"]}],
                    3, [1, 1], 0, []))

    @case("NS4", "F35 N1: the lines of a sketch and S, P are unchanged: a sketch with sub-items still counts as one sketch of the step "
                 "(`sketches: 1 of 2 steps with a proof read`), and the formula mark in a sub-item is listed (`FORMULA-RAW 04.b01`)")
    def _():
        b = _build(notes=_bn(item="Item two here.\n   - sub costs $5"))
        return _eq((b.rc, "sketches: 1 of 2 steps with a proof read" in b.out.splitlines(), listing(b)), (0, True, ["FORMULA-RAW 04.b01"]))

    @case("LB1", "F35 L1: the source check compares what a reader sees, the asterisks removed as backticks are: a release line inside `**...**` "
                 "as a sketch paragraph, as the text of an argument block, and as a sub-item, and the line plain as a sub-item "
                 "is SOURCE-LEAK, exit 1, OUT_DIR absent; `****` + the line + `****` (compared as written) and an unrelated bold text "
                 "(and an id in bold) build, exit 0")
    def _():
        src = {"A/B.lean": "x\n" + LEAK + "\n"}
        three = ["data.js", "group/g1.json", "index.html"]
        files = lambda b_: sorted(ln.split(" ")[2] for ln in b_.out.splitlines()
                                  if ln.startswith("BUILD-ERROR SOURCE-LEAK ") and not ln.startswith("BUILD-ERROR SOURCE-LEAK note "))
        res, want = [], []
        vals = (("wrapped", "**" + LEAK + "**"), ("doubled", "****" + LEAK + "****"), ("plain", "Take **three** steps."),
                ("id", "See **01.b02** now."))
        for where, mk, extra in (("para", lambda v: _bn(para=v), ()), ("arg", lambda v: _bn(arg=v), ()),
                                 ("sub", lambda v: _bn(item="Item two.\n   - " + v), (("bare", LEAK),))):
            for name, v in vals + extra:
                b = _build(notes=mk(v), src=src)
                res.append((where, name, b.rc, files(b), b.existed))
                want.append((where, name, *((1, three, False) if name in ("wrapped", "bare") else (0, [], True))))
        return _eq(res, want)

    @case("LB2", "F35 L1: a release line split by two and by three bold pairs (`**theorem** leak_example_long_name **:** 1 + 1 = 2 := rfl`) "
                 "is SOURCE-LEAK in a sketch paragraph, a sketch item and a sub-item (data.js and group/g1.json; the page's own text nodes are "
                 "cut by the <strong> tags, so index.html does not hold the line), exit 1, OUT_DIR absent; control: the same text with "
                 "one word changed builds")
    def _():
        src = {"A/B.lean": "x\n" + LEAK + "\n"}
        files = lambda b_: sorted(ln.split(" ")[2] for ln in b_.out.splitlines()
                                  if ln.startswith("BUILD-ERROR SOURCE-LEAK ") and not ln.startswith("BUILD-ERROR SOURCE-LEAK note "))
        two = "**theorem** leak_example_long_name **:** 1 + 1 = 2 := rfl"
        three = "**theorem** leak_example_long_name **:** 1 + 1 **=** 2 := rfl"
        ctl = "**theorem** leak_example_other_name **:** 1 + 1 = 2 := rfl"
        res, want = [], []
        for where, mk in (("para", lambda v: _bn(para=v)), ("item", lambda v: _bn(item=v)),
                          ("sub", lambda v: _bn(item="Item two.\n   - " + v))):
            for name, v in (("two", two), ("three", three), ("control", ctl)):
                b = _build(notes=mk(v), src=src)
                res.append((where, name, b.rc, files(b), b.existed))
                want.append((where, name, *((0, [], True) if name == "control" else (1, ["data.js", "group/g1.json"], False))))
        return _eq(res, want)

    @case("CW1", "F35 P1: the page CSS holds `code { overflow-wrap: anywhere; }`, so long code in the evidence list wraps on a narrow screen "
                 "(the browser read of the page is the check that it does); the page still passes the static check, with no url( and no @import")
    def _():
        b = _sbase()
        return _eq(("code { overflow-wrap: anywhere; }" in CSS, "code { overflow-wrap: anywhere; }" in b.page, static_problems(b.page, b.text("data.js")),
                    "url(" in CSS, "@import" in CSS, CSS.startswith("body { max-width: 50rem;")), (True, True, [], False, False, True))

    # ---- F31: the note of a recognition that is not recognised (the checker of the notes does not know the key yet, so these cases
    # call the model and the page directly, as the builder reads the outline object as written)
    def _noted(form="not_recognised", note="We looked in `Foo.bar` and found [nothing](x.md)."):
        o = _outline()
        g = next(g for g in o["groups"] if g["id"] == "g1")
        g["root_role"] = "result"
        g["recognition"] = _rec(form, note=note, **({"result": "R", "citations": [CITB]} if form == "known" else {}))
        return o

    def _direct_build(outline, src=None, roles=True):
        """(the page, every output file, the files that hold a release line, the model) with no checker run."""
        with tempfile.TemporaryDirectory() as d:
            p = _plant(d, outline=outline, src=src, roles=roles)
            sj, errors, commits = _strings(), [], {"notes": "n", "release": "r", "tools": "t"}
            m = _model(p["notes"], json.load(open(p["outline"])), _decl_rows(p["decls"]), sj, None, errors)
            _e2, _line, l0, l1, groups, facts = _assemble(m, sj, commits)
            page = _render_page(m, sj, facts, False)
            files = _output_files(l0, l1, groups, page, commits, m, "r", None)
            leaks = leak_check(files, p["src"], m.copied)[0] if p["src"] else None
        return types.SimpleNamespace(page=page, files=files, leaks=leaks, m=m)

    @case("FN1", "F2: a not_recognised recognition with a `note` shows the form line, THEN the note as one paragraph through the span rule "
                 "(`Foo.bar` is <code>) and NOT through the link rule (the link stays as written, no anchor), THEN the label line; the "
                 "JSON carries the note inside recognition and nothing in counts; a not_recognised card without a note (zrn) is the form "
                 "line and the label line only")
    def _():
        b = _direct_build(_noted())
        rc = rcn(b, "g1")
        note = _direct(rc, "p", "recognition-note")[0]
        l0 = json.loads(b.files["level0.json"].decode("utf-8"))
        return _eq((lead(rc), _raw(note), [c.text() for c in note.find("code")], len(rc.find("a")),
                    json.loads(b.files["group/g1.json"].decode("utf-8"))["recognition"]["note"],
                    sorted(next(s for s in l0["steps"] if s["id"] == "g1")["counts"]), lead(rcn(_zbase(), "zrn"))),
                   ([("p", "recognition-form"), ("p", "recognition-note"), ("p", "recognition-label")],
                    "We looked in Foo.bar and found [nothing](x.md).", ["Foo.bar"], 0,
                    "We looked in `Foo.bar` and found [nothing](x.md).",
                    ["open_items", "roots", "roots_open_items", "roots_proof_applicable", "roots_proof_read", "roots_statement_read"],
                    [("p", "recognition-form"), ("p", "recognition-label")]))

    @case("FN2", "F2: a note on any other form is not printed (the checker refuses it; the builder ignores the key): a known recognition with a "
                 "note shows no note paragraph")
    def _():
        b = _direct_build(_noted("known"))
        return _eq([k[1] for k in lead(rcn(b, "g1"))], ["recognition-form", "recognition-citations", "recognition-label"])

    @case("FN3", "F3: the source check compares the note as written and with its span backticks removed: a release line inside single "
                 "backticks as the note is a leak (data.js, group/g1.json, level0.json, level1.json); doubled backticks and an unrelated note "
                 "are not")
    def _():
        src = {"A/B.lean": "x\n" + LEAK + "\n"}
        got = [_direct_build(_noted(note=v), src=src).leaks for v in ("`" + LEAK + "`", "``" + LEAK + "``", "An unrelated note of ours.")]
        return _eq(got, [["data.js", "group/g1.json", "level0.json", "level1.json"], [], []])

    @case("FN4", "F4: a note changes no count: the run line of a model with one noted not_recognised group counts it as not recognised only")
    def _():
        return _eq(_count_lines(_direct_build(_noted()).m)[1][0],
                   "recognition: 0 known, 0 variant, 1 not recognised, 0 open in literature, 2 not written, of 3 groups with a claim")

    @case("FN5", "F2 end to end: the checker of the notes accepts a `note` on a not_recognised recognition, so a full run (the checker included, "
                 "exit 0) shows it after the form line and before the label line and keeps it as written in group/g1.json; a note on a known "
                 "recognition is refused by the checker (exit 1, nothing written)")
    def _():
        b = _build(outline=_noted())
        bad = _build(outline=_noted("known"))
        return _eq((b.rc, [k[1] for k in lead(rcn(b, "g1"))], b.js("group/g1.json")["recognition"]["note"], bad.rc, bad.existed),
                   (0, ["recognition-form", "recognition-note", "recognition-label"],
                    "We looked in `Foo.bar` and found [nothing](x.md).", 1, False))

    @case("FB1", "A3: the role of a claimed group with NO root_role is the class of its root's kind, pinned through the model and the page with "
                 "no checker run (a claim with no role is ROOT-ROLE-MISSING, an error once REQUIRE_ROOT_ROLE is True, so a run cannot carry "
                 "one): the zoo with the roles of zkr, zkn and g1a1 left off has root_role null in their summaries, the form lines of "
                 "a result (zkr, theorem) and of a named statement (zkn, def), and the named-statement line on zkn and g1a1 only")
    def _():
        o = _zoo()
        for g in o["groups"]:
            if g["id"] in ("zkr", "zkn", "g1a1"):
                g.pop("root_role", None)
        b = _direct_build(o, roles=False)
        sm = b.m.summary
        form = lambda g: _raw(_direct(rcn(b, g), "p", "recognition-form")[0])
        use = [g for g in ("zkr", "zkn", "g1a1") if _direct(_card(b, g), "p", "named-statement-use")]
        return _eq(([sm[g]["root_role"] for g in ("zkr", "zkn", "g1a1")], form("zkr"), form("zkn"), use),
                   ([None, None, None], "Our reading: this is a well-known result in mathematics (res-zkr).",
                    "Our reading: the statement named here is a well-known result in mathematics (res-zkn).", ["zkn", "g1a1"]))

    # ---- the reviewer round on F24b: survivors of 64 plausible-wrong mutants, pinned
    def _open_g1(cits):
        o = _outline()
        g = next(g for g in o["groups"] if g["id"] == "g1")
        g["root_role"] = "result"
        g["recognition"] = _rec("open_in_literature", result="R", citations=cits)
        return o

    @case("SK9", "C1: every list marker the checker's list reading takes is pinned: a sketch whose lists open with `1.` (also `2.` and `10.` "
                 "after it), `2)`, `-`, `*` and `+` has the first two as ordered (<ol>, ordered true) and the other three as bulleted (<ul>, "
                 "ordered false), in the JSON and on the card")
    def _():
        marks = (("1. A\n2. B\n10. C", "p1"), ("2) D\n3) E", "p2"), ("- F\n- G", "p3"), ("* H\n* I", "p4"), ("+ J\n+ K", "p5"))
        body = "".join(lst + "\n\n" + par + " text.\n\n" for lst, par in marks)
        n = ("# Note four\n" + _h(id="04", group="g1", list_title="Note four") + "\n\n## Body\n\n" + body + "Last paragraph.\n"
             + _b(id="04.b01", kind="sketch", decls=[FOO], reader="Reader Two", date="2026-11-24", basis="source", span=11) + "\n")
        b = _build(notes=_notes() | {"04-sketch.md": n})
        sk = b.js("group/g1.json")["sketches"][0]["blocks"]
        lists = [x for x in sk if x["type"] == "list"]
        card = _direct(_card(b, "g1"), "div", "sketch")[0]
        return _eq((b.rc, [x["ordered"] for x in lists], [x["items"] for x in lists][:2], [k.tag for k in card.elems() if k.tag in ("ol", "ul")]),
                   (0, [True, True, False, False, False], [["A", "B", "C"], ["D", "E"]], ["ol", "ol", "ul", "ul", "ul"]))

    @case("RD3", "A4: the citation's `where` goes through the span rule like its source (a code span in it is <code>, content escaped): "
                 "`Section `3.1`` shows `Section 3.1` with `3.1` as code")
    def _():
        b = _build(outline=_outline_r("where", "Section `3.1`"))
        li = _direct(rcn(b, "g1"), "ul", "recognition-citations")[0].elems()[0]
        return _eq((b.rc, _raw(li), [c.text() for c in li.find("code")]), (0, "A source, Section 3.1", ["3.1"]))

    @case("RD4", "A3: a year and a year-month of the same year, the LONGER first, are compared as the strings as written in either order "
                 "(2006-11 then 2006, and 2006 then 2006-11, both read `as of 2006-11`): the newest by the strings, never the last cited")
    def _():
        got = []
        for cits in ([_oc("L1", "2006-11"), _oc("L2", "2006")], [_oc("L1", "2006"), _oc("L2", "2006-11")]):
            b = _build(outline=_open_g1(cits))
            got.append((b.rc, _raw(_direct(rcn(b, "g1"), "p", "recognition-form")[0])))
        line = "Our reading: this result's statement is R, an open problem as of 2006-11 according to the dated source below."
        return _eq(got, [(0, line)] * 2)

    @case("P7f", "static_problems, the class of a citation anchor is a TOKEN of its class list (`citation extra` passes, as `reaction extra` "
                 "does) and the exemption is for `href` alone: `citationx`, `xcitation`, a citation anchor with `xlink:href`, `action` or "
                 "`formaction` to an https address, and `xreaction`, are each refused")
    def _():
        sp = static_problems
        planted = [('<a class="citationx" href="https://x.invalid/">x</a>', ["href=http"]),
                   ('<a class="xcitation" href="https://x.invalid/">x</a>', ["href=http"]),
                   ('<a class="citation" xlink:href="https://x.invalid/">x</a>', ["href=http"]),
                   ('<a class="citation" action="https://x.invalid/">x</a>', ["href=http"]),
                   ('<a class="citation" formaction="https://x.invalid/">x</a>', ["href=http"]),
                   ('<a class="xreaction" href="http://x.invalid/">x</a>', ["href=http"])]
        controls = ['<a class="citation extra" href="https://x.invalid/">x</a>', '<a class="extra reaction" href="http://x.invalid/">x</a>']
        return _eq(([sp(h, "") for h, _w in planted], [sp(h, "") for h in controls]), ([w for _h, w in planted], [[], []]))

    @case("EL1", "element_problems, planted: `<script>`, `<annotation>`, `<iframe>` and an unknown element are `element <name>`; an `onclick` on a "
                 "<p>, a `style` on a <p> (the builder has none), an `href` on a <mi> and a `mathvariant` on a <p> are `attribute <name> on <element>`; "
                 "controls: <strong>, a nested <ul>/<li>, and a MathML tree with mathvariant, stretchy and form on its elements are clean")
    def _():
        ep = element_problems
        planted = [("<script>x</script>", ["element script"]), ("<math><annotation>x</annotation></math>", ["element annotation"]),
                   ("<iframe></iframe>", ["element iframe"]), ("<p onclick=\"x\">a</p>", ["attribute onclick on p"]),
                   ("<p style=\"color:red\">a</p>", ["attribute style on p"]), ("<math><mi href=\"#a\">x</mi></math>", ["attribute href on mi"]),
                   ("<p mathvariant=\"normal\">a</p>", ["attribute mathvariant on p"]), ("<blink>a</blink>", ["element blink"]),
                   ("<math><mi width=\"1em\">x</mi></math>", ["attribute width on mi"]), ("<p width=\"1em\">a</p>", ["attribute width on p"]),
                   ("<p>a</p><script></script><iframe></iframe>", ["element iframe", "element script"])]
        controls = ["<p>a <strong>b</strong></p>", "<ul><li>a<ul><li>b</li></ul></li></ul>",
                    '<math><mrow><mi mathvariant="normal">f</mi><mo stretchy="false" form="prefix">(</mo><msubsup><mi>x</mi><mn>1</mn><mn>2</mn></msubsup>'
                    '<mover><mi>x</mi><mo>&#175;</mo></mover><munder><mi>a</mi><mi>b</mi></munder><munderover><mo>&#8721;</mo><mi>a</mi><mi>b</mi></munderover>'
                    '<msub><mi>a</mi><mi>b</mi></msub><msup><mi>a</mi><mi>b</mi></msup><mspace></mspace><mspace width="0.167em"></mspace></mrow></math>']
        return _eq(([ep(h) for h, _w in planted], [ep(h) for h in controls]), ([w for _h, w in planted], [[]] * 3))

    @case("EL2", "the allow-list: 41 elements (the 29 the builder emits today and the 12 of MathML) and 50 element-attribute pairs (`width` on <mspace> too); the built page of "
                 "the base fixture, the zoo, the sketch fixture, the definition fixture and one with bold and a nested sub-item is clean under it")
    def _():
        bold = _build(notes=_notes_s(para="A **bold** word.", item="Item two.\n   - a sub item"))
        pages = [_base().page, _zbase().page, _sbase().page, _bbase().page, bold.page]
        return _eq(([element_problems(x) for x in pages], len(ALLOWED_ELEMENTS), sum(len(v) for v in ALLOWED_ELEMENTS.values()),
                     "<strong>" in bold.page, "<ul><li>" in bold.page.replace("\n", "")),
                   ([[]] * 5, 41, 50, True, True))

    @case("EL3", "the check runs on the BUILT page and refuses like the other static findings: a page with an <iframe> added is "
                 "`BUILD-ERROR PAGE-STATIC element iframe found in index.html`, one with an `onclick` on a <p> is `attribute onclick on p`; "
                 "exit 1, OUT_DIR absent; the same build without the addition passes")
    def _():
        real = _render_page
        res = []
        for old, new in (("</main>", "<iframe></iframe></main>"), ('<p class="mapped">', '<p onclick="x" class="mapped">'), ("</main>", "</main>")):
            with _patched("_render_page", lambda *a, _o=old, _n=new: real(*a).replace(_o, _n, 1)):
                b = _build()
            res.append((b.rc, sorted(ln for ln in b.out.splitlines() if ln.startswith("BUILD-ERROR PAGE-STATIC")), b.existed))
        return _eq(res, [(1, ["BUILD-ERROR PAGE-STATIC element iframe found in index.html"], False),
                         (1, ["BUILD-ERROR PAGE-STATIC attribute onclick on p found in index.html"], False), (0, [], True)])

    @case("DF4", "D1: a Windows-style path in a block's file gives the base name in the Evidence section (`A\\Deep\\Nest.lean` shows `Nest.lean`), "
                 "the JSON keeps the path as written")
    def _():
        n = _n01().replace('"file":"A/B.lean"', '"file":"A\\\\Deep\\\\Nest.lean"').replace("| `A/B.lean` |", "| `A\\Deep\\Nest.lean` |")
        b = _build(notes=_notes() | {"01-one.md": n})
        return _eq((b.rc, pairs(blk(b, "g1", "01.b02")), "Deep" in _raw(blk(b, "g1", "01.b02")), b.js("group/g1.json")["blocks"][1]["file"]),
                   (0, [[("File", "Nest.lean"), ("Lines", "15-18")]], False, "A\\Deep\\Nest.lean"))

    # ---- F37 (a) to (c): provenance (who read what, and when) is off the card and in the closed Evidence section
    f37 = lambda **kw: _build(strings=_strings(), **kw)
    _surface_bad = re.compile(r"Reader|2026-\d\d-\d\d|\.lean|[Rr]ead by|Read again|counted by|recorded by|understanding|lake build")

    LABEL = "No mathematician has checked our reading yet. If you think we have it wrong, or you know more, please tell us."

    @case("PV1", "F37 S1: site/strings.json takes the wording file's CARD value on each of its 15 keys, has the 8 EVIDENCE keys as written, "
                 "keeps the 22 values the wording file says stay (UNCHANGED_ON_CARD) byte-equal, has no second_reader_frame, and holds "
                 "frames.argument `How this is proved`; the file passes the builder's own strings check")
    def _():
        path = os.path.join(_HERE, os.pardir, "site", "strings.json")
        if not os.path.isfile(path):
            raise _SkipCase("no real strings file in this checkout")
        with open(path, encoding="utf-8") as f:
            real = json.load(f)
        diff = lambda want: [k for k in want if real.get(k) != want[k]]
        return _eq((diff(F37_CARD), diff(F37_EVIDENCE), diff(F37_UNCHANGED), len(F37_CARD), len(F37_EVIDENCE), len(F37_UNCHANGED),
                    "second_reader_frame" in real, real["frames"]["argument"], _strings_problems(real)),
                   ([], [], [], 15, 8, 22, False, ["How this is proved"], []))

    @case("PV2", "F37 S1: placeholders as the new values hold them: each of the 8 EVIDENCE keys that lacks one it requires is refused "
                 "(`is missing the placeholder`, key and token named, 17 cases), a CARD key that holds a reader, date, file, lines, build or "
                 "opened_by token it does not declare is refused (`has an unknown placeholder`), sketch_frame without {basis}, "
                 "established_by_line without {name} and the citation lines without {source}, {where} or {source_date} are refused; the "
                 "fixture (no second_reader_frame at all) builds, so that key is no longer required")
    def _():
        req = (("evidence_statement_read_line", ("reader", "date")), ("evidence_statement_census_line", ("reader", "date")),
               ("evidence_proof_read_line", ("reader", "date")), ("evidence_second_reader_line", ("reader", "date")),
               ("evidence_recognition_line", ("reader", "date")), ("evidence_citation_line", ("source", "opened_by", "opened_on")),
               ("evidence_established_line", ("name", "reader", "date")), ("evidence_sketch_build_line", ("build",)),
               ("sketch_frame", ("basis",)), ("established_by_line", ("name",)),
               ("recognition_citation_dated_line", ("source", "where")), ("recognition_citation_open_line", ("source", "where", "source_date")))
        extra = (("statement_read_line", "reader"), ("statement_census_line", "date"), ("proof_read_line", "reader"),
                 ("argument_frame", "file"), ("argument_frame", "lines"), ("argument_frame", "reader"), ("argument_frame_no_proof", "date"),
                 ("interpretation_frame", "reader"), ("sketch_frame", "reader"), ("sketch_basis_compiled", "build"),
                 ("recognition_label_line", "reader"), ("recognition_citation_dated_line", "opened_by"),
                 ("recognition_citation_open_line", "opened_on"), ("established_by_line", "reader"))
        err = lambda b_: [x for x in b_.out.splitlines() if x.startswith("BUILD-ERROR")]
        res, want = [], []
        for key, names in req:
            for name in names:
                st = _strings()
                st[key] = st[key].replace("{" + name + "}", "")
                b = _build(strings=st)
                res.append((key, name, b.rc, err(b), b.existed))
                want.append((key, name, 1, [f"BUILD-ERROR STRINGS-KEY {key} is missing the placeholder {{{name}}}"], False))
        for key, name in extra:
            st = _strings()
            st[key] = st[key] + " {" + name + "}"
            b = _build(strings=st)
            res.append((key, name, b.rc, err(b), b.existed))
            want.append((key, name, 1, [f"BUILD-ERROR STRINGS-KEY {key} has an unknown placeholder {{{name}}}"], False))
        return _eq((res, len(res), f37().rc), (want, 38, 0))

    @case("PV3", "F37 S2: no card shows a reader, a date of ours, a file or lines, a build or `read by` outside its closed Evidence section (the "
                 "corrections list is read too): the base, the sketch, the definition and the "
                 "recognition pages; the status lines are the quiet ones (g1 read/read, g3 census/not read, g1a read/not read)")
    def _():
        pages = [f37(), f37(notes=_notes_s()), f37(outline=_outline_b(), notes=_notes_b()), f37(outline=_zoo())]
        bad = [[m_.group(0) for m_ in _surface_bad.finditer(surface(_dom(b_.page)))] for b_ in pages]
        b = pages[0]
        st = lambda g: [p.text() for p in _card(b, g).find("p", "status")][:2]
        return _eq((bad, [b_.rc for b_ in pages], st("g1"), st("g3"), st("g1a"), st("g1a1x")),
                   ([[]] * 4, [0] * 4, ["We have read this statement.", "We have read this proof."],
                    ["We have not read this statement: what it says here comes from a program's count of its parts.",
                     "We have not read this proof yet."],
                    ["We have read this statement.", "We have not read this proof yet."],
                    ["We have read this statement.", "We have not read this proof yet."]))

    @case("PV4", "F37 S2: the argument frame, the first sentence and the link on the closed card carry no name, date, file or lines (`How this is "
                 "proved: First argument sentence. Read the note`), there is no second-reader span on any card, a step whose roots are no "
                 "theorem or lemma is framed `What this definition contains:` and a mixed one `How this is proved:`; the sketch frame says its "
                 "basis only (`from the goals Lean shows ...` for a compiled one, `from reading the Lean source`), the build string is not "
                 "in the sketch")
    def _():
        b, bb, bs = f37(), f37(outline=_outline_b(), notes=_notes_b()), f37(notes=_notes_s())
        arg = lambda b_, g: _direct(_card(b_, g), "p", "argument")[0]
        frame = lambda b_, g: _direct(_card(b_, g), "div", "sketch")[0].find("p", "sketch-frame")[0].text()
        return _eq((arg(b, "g1").text(), arg(b, "g1").elems()[0].cls, len(_dom(bb.page).find("span", "second")),
                    arg(bb, "g1a1").text(), arg(bb, "g2").text(), blk(bb, "g2", "07.b02").find("p", "argument")[0].text(),
                    frame(bs, "g1"), frame(bs, "g1a"), "lake build" in _direct(_card(bs, "g1"), "div", "sketch")[0].text()),
                   ("How this is proved: First argument sentence. Read the note", ["frame"], 0,
                    "What this definition contains: Def argument sentence. Read the note",
                    "What this definition contains: Def argument sentence. Read the note",
                    "How this is proved: Mixed argument sentence. Second mixed sentence.",
                    "The proof in order, from the goals Lean shows when this part of the release is compiled:",
                    "The proof in order, from reading the Lean source:", False))

    @case("PV5", "F37 S2: the recognition block shows its citation lines with source and place only (`List D, Problem 7`, and `, dated 2007-01` "
                 "for a source that says open on an open card), the established line with the name only, and the label line (no name, no date) "
                 "ONCE at the end of the block of each of the 14 cards that show a recognition, never on the two that show the not-written line")
    def _():
        b = f37(outline=_zoo())
        cits = lambda g: [_raw(li) for li in _direct(rcn(b, g), "ul", "recognition-citations")[0].elems()]
        est = lambda g: _raw(_direct(rcn(b, g), "p", "recognition-established")[0])
        has = [z[0] for z in _ZOO if z[3] is not None]
        labels = {g: [p.text() for p in rcn(b, g).find("p", "recognition-label")] for g in has}
        last = {g: lead(rcn(b, g))[-1] for g in has}
        return _eq((cits("zrk"), cits("zrv"), cits("zro"), cits("zno"), cits("zov"), est("znk"), est("znv"), labels == {g: [LABEL] for g in has},
                    len(has), set(last.values()), len(_dom(b.page).find("p", "recognition-label")),
                    [len(rcn(b, g).find("p", "recognition-label")) for g in ("zw", "zwn")]),
                   (["The Source Book, Theorem 2.1"], ["The Source Book, Theorem 2.1", "Other Paper, Section 3"],
                    ["List A, Problem 7, dated 2007-01", "List B, Problem 7, dated 2004-05-17", "List C, Problem 7, dated 2010-03",
                     "List D, Problem 7"], ["List E, Problem 7, dated 2006", "List F, Problem 7, dated 2006-11"],
                    ["Other Paper, Section 3", "List G, Problem 7"], "Where it is proved: the release proves this statement as A.B.foo.",
                    "Where it is proved: we have not yet traced where in the release this statement is proved.", True, 14,
                    {("p", "recognition-label")}, 14, [0, 0]))

    @case("PV6", "F37 S3: the Evidence section is a <details> closed by default on every card (no `open`), and holds, after the roots and before "
                 "`What we wrote about it`, a list of the readings in a fixed order: statement, proof, the recognition, each citation, the "
                 "established line (g1: statement and proof; g3, a census claim: the census line; zrv: statement, proof, recognition, two "
                 "citations; znk: statement, recognition, citation, established; znv, not traced: no established line; zw, no recognition: "
                 "statement and proof)")
    def _():
        b, bz = f37(), f37(outline=_zoo())
        dets = _dom(bz.page).find("details", "evidence")
        return _eq((all("open" not in d.attrs for d in dets), len(dets), bz.page.count('<details class="evidence">'),
                    [(k.tag, k.cls[-1] if k.cls else "") for k in evd(b, "g1").elems()],
                    prov(b, "g1"), prov(b, "g3"), prov(b, "g1a"), prov(b, "g2"), prov(bz, "zrv"), prov(bz, "znk"), prov(bz, "znv"),
                    prov(bz, "zw"), prov(bz, "zok")),
                   (True, 22, 22, [("summary", ""), ("div", "root"), ("ul", "provenance"), ("p", "label"), ("ul", "blocks")],
                    ["Statement read by Reader One on 2026-11-20.", "Proof read by Reader One on 2026-11-23."],
                    ["Statement counted by a program, not read, recorded by Reader One on 2026-11-20."],
                    ["Statement read by Reader One on 2026-11-23."], None,
                    ["Statement read by Reader One on 2026-11-20.", "Proof read by Reader One on 2026-11-23.",
                     "Our reading of where this statement stands: written by Reader One on 2026-11-22.",
                     "The Source Book: opened by Reader Two on 2026-11-21.", "Other Paper: opened by Reader One on 2026-11-22."],
                    ["Statement read by Reader One on 2026-11-20.",
                     "Our reading of where this statement stands: written by Reader One on 2026-11-22.",
                     "Other Paper: opened by Reader One on 2026-11-22.",
                     "Where it is proved: traced to A.B.foo by Reader Two on 2026-11-23."],
                    ["Statement read by Reader One on 2026-11-20.",
                     "Our reading of where this statement stands: written by Reader One on 2026-11-22.",
                     "Other Paper: opened by Reader One on 2026-11-22."],
                    ["Statement read by Reader One on 2026-11-20.", "Proof read by Reader One on 2026-11-23."],
                    ["Statement read by Reader One on 2026-11-20.",
                     "Our reading of where this statement stands: written by Reader Two on 2026-11-23.",
                     "Other Paper: opened by Reader One on 2026-11-22."]))

    @case("PV7", "F37 S3: in the blocks list of the Evidence section an argument block carries, after its text, its file (base name) and lines "
                 "(the labels File and Lines, `not given` when it has none) and one line per second reader (g1, 01.b02: `B.lean`, `15-18`, "
                 "`Read again by Reader Two on 2026-11-24.`; the frame in the text carries no name); a sketch block carries its file and "
                 "lines and, when compiled, the build line (g1: `lake build A.B`; g1a, from the source: none); a block of another kind "
                 "carries neither; the interpretation keeps its own aside and frame")
    def _():
        b, bs, bb = f37(), f37(notes=_notes_s()), f37(outline=_outline_b(), notes=_notes_b())
        a = blk(b, "g1", "01.b02")
        sk = blk(bs, "g1", "04.b01")
        ska = blk(bs, "g1a", "05.b02")
        return _eq(([(k.tag, k.cls[-1] if k.cls else "") for k in a.elems()][3:], a.find("p", "argument")[0].text(), pairs(a),
                    [p.text() for p in a.find("p", "second-reader")],
                    pairs(sk), [p.text() for p in sk.find("p", "sketch-build")], pairs(ska), [p.text() for p in ska.find("p", "sketch-build")],
                    pairs(blk(b, "g1", "01.b01")), [p.text() for p in blk(b, "g1", "01.b03").find("p", "interpretation")],
                    [p.text() for p in blk(bb, "g1a1", "07.b02").find("p", "argument")],
                    pairs(blk(bb, "g1a1", "07.b01")), pairs(blk(bb, "g1a1", "07.b02"))),
                   ([("p", "argument"), ("dl", "block-source"), ("p", "second-reader")],
                    "How this is proved: First argument sentence. Second argument sentence.", [[("File", "B.lean"), ("Lines", "15-18")]],
                    ["Read again by Reader Two on 2026-11-24."],
                    [[("File", "not given"), ("Lines", "not given")]], ["Proof sketch from a compiled part of the release: lake build A.B."],
                    [[("File", "not given"), ("Lines", "not given")]], [], [],
                    ["What we think it means: We think this is the key step."],
                    ["What this definition contains: Mixed argument sentence. Second mixed sentence."],
                    [[("File", "C.lean"), ("Lines", "5-9")]], [[("File", "TopPlug.lean"), ("Lines", "not given")]]))

    @case("PV8", "F37 S3: a card with nothing to say in Evidence keeps today's section: g2 (two roots, no claim, so no reading to name) has no "
                 "provenance list, its children are the same summary, root divs, label, blocks list and open-items list as on the head of F35")
    def _():
        b = f37()
        return _eq(([(k.tag, k.cls[-1] if k.cls else "") for k in evd(b, "g2").elems()], prov(b, "g2")),
                   ([("summary", ""), ("div", "root"), ("div", "root"), ("p", "label"), ("ul", "blocks"), ("p", "label"), ("ul", "open")],
                    None))

    @case("PV9", "F37 S4: the group files, the level files and data.js are byte-equal to what the head of F35 wrote, on five fixture builds "
                 "(base, recognition zoo, sketches, definition, zoo with sketches and the definition note): one digest over every file but "
                 "index.html and manifest.json, pinned from that head; the same fields are in the JSON (the reader, date, second_readers, "
                 "file and lines of 01.b02 and the recognition's reader, date and citations' opened_by and opened_on)")
    def _():
        def dig(b_):
            h = hashlib.sha256()
            for k in sorted(b_.files):
                if k not in ("index.html", "manifest.json"):
                    h.update(k.encode() + b"\0" + hashlib.sha256(b_.files[k]).digest())
            return h.hexdigest()
        outs = [f37(), f37(outline=_zoo()), f37(notes=_notes_s()), f37(outline=_outline_b(), notes=_notes_b()),
                f37(outline=_zoo(), notes=_notes_s() | {"07-def.md": N07})]
        g1, zrv = outs[0].js("group/g1.json"), outs[1].js("group/zrv.json")
        arg = next(x for x in g1["blocks"] if x["block"] == "01.b02")
        return _eq(([b_.rc for b_ in outs], [dig(b_) for b_ in outs],
                    (arg["reader"], arg["date"], arg["second_readers"], arg["file"], arg["lines"]),
                    (zrv["recognition"]["reader"], zrv["recognition"]["date"],
                     [(c["opened_by"], c["opened_on"]) for c in zrv["recognition"]["citations"]])),
                   ([0] * 5, ["be90b01739a84e20e61d6925401b6fa3e256e858c2aa0336d07eee6750649bc5",
                              "94f4db15211979dd993fe33b7580510b73d0ae09fe2cf623656d3459050a5da7",
                              "0d4bf044dfadbf07c8b1a24788b6b246437d2285759d1ba2449e19b952314baa",
                              "9ff0b5317fcb3ae718a054f590ab6f1da16c4f86ac48c0784c4d96a2590a526b",
                              "0019287171c05bb06a9c1e524d491c68506cc8f03d6fc739822d5a7716efe67c"],
                    ("Reader One", "2026-11-23", [{"reader": "Reader Two", "date": "2026-11-24"}], "A/B.lean", [15, 18]),
                    ("Reader One", "2026-11-22", [("Reader Two", "2026-11-21"), ("Reader One", "2026-11-22")])))

    @case("PV10", "F37 S5: the builder's own rules for its sentences hold for the 8 new keys: a forbidden word, a percent sign or `of the proof` "
                  "in any of them is refused as STRINGS-FORBIDDEN naming the key (24 cases); control: the fixture builds")
    def _():
        res = []
        for key in F37_EVIDENCE:
            for bad in (" This is verified.", " It is 50% done.", " It is a part of the proof."):
                st = _strings()
                st[key] = st[key] + bad
                b = _build(strings=st)
                res.append((key, b.rc, [x.split(" ")[1:3] for x in b.out.splitlines() if x.startswith("BUILD-ERROR")]))
        return _eq((res, f37().rc), ([(k, 1, [["STRINGS-FORBIDDEN", k]]) for k in F37_EVIDENCE for _i in range(3)], 0))

    @case("PV12", "F37 corrections: a correction on a card keeps its kind and its title on the card (`Correction` and the link to the note) "
                  "and shows neither its reader nor its date there; its reader and date are in the Evidence section, in the block list "
                  "beside the block's kind (the existing who-span, no new string). One correction (g1: 01.b06), two on one card (g1a1: "
                  "08.b01 and 09.b01, a definition) and one on a theorem with a census claim (g3: 10.b01); a card with none has no list; the "
                  "JSON is byte-equal to what the builder wrote before this change (pinned digest) and holds each reader and date")
    def _():
        b = f37(notes=_notes_corr())
        lis = lambda g: [li.text() for li in _direct(_card(b, g), "ul", "corrections")[0].find("li")]
        ev = lambda g, bid: blk(b, g, bid).text()
        h = hashlib.sha256()
        for k in sorted(b.files):
            if k not in ("index.html", "manifest.json"):
                h.update(k.encode() + b"\0" + hashlib.sha256(b.files[k]).digest())
        js = lambda g, bid: next((x["reader"], x["date"]) for x in b.js(f"group/{g}.json")["blocks"] if x["block"] == bid)
        return _eq((b.rc, lis("g1"), lis("g1a1"), lis("g3"), len(_direct(_card(b, "g1a"), "ul", "corrections")),
                    _surface_bad.findall(surface(_dom(b.page))),
                    ev("g1", "01.b06"), ev("g1a1", "08.b01"), ev("g1a1", "09.b01"), ev("g3", "10.b01"),
                    h.hexdigest(), js("g1", "01.b06"), js("g1a1", "08.b01"), js("g1a1", "09.b01"), js("g3", "10.b01")),
                   (0, ["Correction Note one"], ["Correction Note eight", "Correction Note nine"], ["Correction Note ten"], 0, [],
                    "01 01.b06 Correction Reader Two 2026-11-22", "08 08.b01 Correction Reader Three 2026-11-26",
                    "09 09.b01 Correction Reader Four 2026-11-27", "10 10.b01 Correction Reader Five 2026-11-28",
                    "1bea6d12fa8779f32724591755e4fa62c663e37c4a4df0561b46c72def23734a",
                    ("Reader Two", "2026-11-22"), ("Reader Three", "2026-11-26"), ("Reader Four", "2026-11-27"), ("Reader Five", "2026-11-28")))

    @case("PV13", "F37 review P1: a second reader of a block that is NOT an argument is in the Evidence section too, one `Read again by ...` "
                  "line after that block (a reading block 01.b01 and an interpretation block 01.b03 with a second reader each, the argument "
                  "01.b02 as before); none of them is on the card")
    def _():
        n = (_n01().replace('"kind":"reading","lines":[12,14],"reader":"Reader One"}',
                            '"kind":"reading","lines":[12,14],"reader":"Reader One","second_readers":[{"date":"2026-11-25","reader":"Reader Seven"}]}')
                   .replace('"kind":"interpretation","reader":"Reader Two"}',
                            '"kind":"interpretation","reader":"Reader Two","second_readers":[{"date":"2026-11-26","reader":"Reader Eight"}]}'))
        b = f37(notes=_notes() | {"01-one.md": n})
        sec = lambda bid: [p_.text() for p_ in blk(b, "g1", bid).find("p", "second-reader")]
        return _eq((b.rc, sec("01.b01"), sec("01.b02"), sec("01.b03"), _surface_bad.findall(surface(_card(b, "g1")))),
                   (0, ["Read again by Reader Seven on 2026-11-25."], ["Read again by Reader Two on 2026-11-24."],
                    ["Read again by Reader Eight on 2026-11-26."], []))

    @case("PV14", "F37 review P2: a card with several roots names nobody in Evidence either: g2 with two theorem roots (quux, qux) whose proofs are "
                  "both read by Reader Six shows the counts on the card (`Proofs read: 2 of 2 declarations.`), no provenance list, and the name "
                  "Reader Six only in the block list; control: a card of one root (g1) has its proof line")
    def _():
        o = _outline()
        o["groups"][3]["roots"] = [QUUX, QUX]
        n03 = (N03 + "\nArgues quux.\n" + _b(id="03.b01", kind="argument", decls=[QUUX], reader="Reader Six", date="2026-11-29")
               + "\n\nArgues qux.\n" + _b(id="03.b02", kind="argument", decls=[QUX], reader="Reader Six", date="2026-11-29") + "\n")
        b = f37(outline=o, notes=_notes() | {"03-three.md": n03})
        c = _card(b, "g2")
        return _eq((b.rc, c.find("p", "proof")[0].text(), prov(b, "g2"), "Reader Six" in surface(c), "Reader Six" in evd(b, "g2").text(),
                    prov(b, "g1")[1]),
                   (0, "Proofs read: 2 of 2 declarations.", None, False, True, "Proof read by Reader One on 2026-11-23."))

    @case("PV15", "F37 review P3: hostile text (<b>, &, quotes, a backtick span, **bold**, $, `</details><script>`) in the recognition's reader, a "
                  "citation's opened_by and the established reader is escaped in the Evidence lines: no <script> or <strong> on the page, the "
                  "escaped form is there, a backtick span in opened_by stays literal text (no <code> from it) while the citation's source "
                  "keeps its span")
    def _():
        h = "<b>&\"' `x` **bold** $ </details><script>alert(1)</script>"
        o = _zoo()
        g = next(g_ for g_ in o["groups"] if g_["id"] == "znk")
        g["recognition"]["reader"] = h
        g["recognition"]["citations"] = [dict(CITB, opened_by=h)]
        g["recognition"]["established"] = dict(EST, reader=h)
        b = f37(outline=o)
        dom = _dom(b.page)
        li = _direct(evd(b, "znk"), "ul", "provenance")[0].elems()
        return _eq((b.rc, len(dom.find("script")), len(dom.find("strong")), "<script" in b.page, html.escape(h) in b.page,
                    [_raw(x) for x in li][1:],
                    [c_.text() for c_ in li[2].find("code")]),
                   (0, 0, 0, False, True,
                    [f"Our reading of where this statement stands: written by {h} on 2026-11-22.",
                     f"Other Paper: opened by {h} on 2026-11-22.",
                     f"Where it is proved: traced to A.B.foo by {h} on 2026-11-23."], ["Paper"]))

    @case("PV16", "F37 review P4 (the rule of F29, as main had it): the lines are shown only with a file: a block with lines and NO file shows "
                  "`not given` for the File and `not given` for the Lines; a file and no lines shows the base name and `not given`; both show "
                  "the file and the range (the data keeps the lines as written)")
    def _():
        n = _n01().replace('"file":"A/B.lean","id":"01.b02"', '"id":"01.b02"')
        b = f37(notes=_notes() | {"01-one.md": n})
        arg = next(x for x in b.js("group/g1.json")["blocks"] if x["block"] == "01.b02")
        return _eq((b.rc, pairs(blk(b, "g1", "01.b02")), arg["lines"], "file" in arg, pairs(blk(f37(), "g1", "01.b02")),
                    pairs(blk(f37(outline=_outline_b(), notes=_notes_b()), "g1a1", "07.b02"))),
                   (0, [[("File", "not given"), ("Lines", "not given")]], [15, 18], False, [[("File", "B.lean"), ("Lines", "15-18")]],
                    [[("File", "TopPlug.lean"), ("Lines", "not given")]]))

    @case("PV11", "F37 S1: the argument detector is `How this is proved` (no `, as`): an interpretation block whose text opens `How this is "
                  "proved: ...` is listed as FRAME-NOTE with that detector, and not with the old `How this is proved, as`")
    def _():
        def listed(detector):
            st = _strings()
            st["frames"]["argument"] = detector
            with tempfile.TemporaryDirectory() as d:
                p = _plant(d, notes=_notes(interp_text="How this is proved: it holds by the first step."), strings=st)
                o = io.StringIO()
                with contextlib.redirect_stdout(o):
                    rc = nm.run(p["notes"], p["outline"], p["decls"], strings=p["strings"])
            return rc, [x for x in o.getvalue().splitlines() if x.startswith("FRAME-NOTE")]
        return _eq((listed(["How this is proved"]), listed(["How this is proved, as"])),
                   ((0, ["FRAME-NOTE 01-one.md:13 block '01.b03' (interpretation): the text opens with a frame of kind 'argument' "
                         "('How this is proved')"]), (0, [])))

    return cases


class _SkipCase(Exception):
    """Raised by a case that cannot set up its plant on this system; the case is reported SKIP."""


def selftest(verbose=True, only=None):
    """A case returns (True|False, detail). `only` is a list of case ids: exactly those cases run (an unknown id returns 2)."""
    ok, skipped = True, 0
    cases = _selftest_cases()
    if only is not None:
        known = {c[0] for c in cases}
        bad = [i for i in only if i not in known]
        if bad or not only:
            print("unknown case id: " + ", ".join(bad) if bad else "no case id given", file=sys.stderr)
            return 2
        cases = [c for c in cases if c[0] in only]
    for cid, desc, fn in cases:
        try:
            good, detail = fn()
        except _SkipCase as e:
            good, detail = None, str(e)
        except Exception as e:  # a crash is a failed case, not a skipped one
            good, detail = False, f"{type(e).__name__}: {e}"
        if good is None:
            skipped += 1
            if verbose:
                print(f"CASE {cid} SKIP {detail}")
            continue
        ok = ok and bool(good)
        if verbose:
            print(f"CASE {cid} {'PASS' if good else 'FAIL'} {desc}")
            if not good:
                print(f"  detail: {detail}")
    if verbose:
        print("SELFTEST " + ("PASS" if ok else "FAIL") + (f" ({skipped} skipped)" if ok and skipped else ""))
    return 0 if ok else 4


def selftest_quiet():
    with contextlib.redirect_stdout(io.StringIO()):
        return selftest(verbose=False)


_VALUE_OPTIONS = {"--source-check": "source_check", "--release-archive-sha": "archive_sha", "--notes-commit": "notes_commit",
                  "--repo": "repo"}


def _parse(argv):
    """(positionals, options) or None for a usage error: five positionals, each option at most once, a value for each."""
    pos, opts, i = [], {}, 0
    while i < len(argv):
        x = argv[i]
        if x in _VALUE_OPTIONS:
            if _VALUE_OPTIONS[x] in opts or i + 1 >= len(argv):
                return None
            opts[_VALUE_OPTIONS[x]] = argv[i + 1]
            i += 2
        elif x == "--force":
            if "force" in opts:
                return None
            opts["force"] = True
            i += 1
        elif x.startswith("--"):
            return None
        else:
            pos.append(x)
            i += 1
    if len(pos) != 5 or ("notes_commit" in opts) != ("repo" in opts):
        return None
    if "archive_sha" in opts and not re.fullmatch(r"[0-9a-fA-F]{64}", opts["archive_sha"]):
        return None
    return pos, opts


def main(a, check=None):
    """a is argv with the program name first."""
    if a[1:] == ["--selftest"]:
        return selftest()
    if len(a) == 4 and a[1] == "--selftest" and a[2] == "--only":   # selector, kept out of the usage block
        return selftest(only=[i for i in a[3].split(",") if i])
    parsed = _parse(a[1:])
    if parsed is None:
        print(__doc__.split("usage:")[1].strip(), file=sys.stderr)
        return 2
    if (selftest_quiet if check is None else check)() != 0:
        print("REFUSED: selftest failed; no result reported", file=sys.stderr)
        return 4
    pos, opts = parsed
    return run(*pos, **opts)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
