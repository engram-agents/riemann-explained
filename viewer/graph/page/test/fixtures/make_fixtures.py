#!/usr/bin/env python3
"""Writes the literal fixture files under this directory. The OUTPUT is committed; this script is how it was made.

real/        a small build shaped like the contract's section 6 measurement: 23 steps, 3 top, depth 5, widest 6,
             2 top-level rests_on, 5 step-file rests_on, 7 parent_rests_on true. Plus the card markup (nested like the
             list page: a child's article sits inside its parent's details.children) and the shell's word table.
refusals/    one tiny build per refusal.
notes/       the skeleton map plus the two optional strings `note_label` and `note_source`, and a top-level `note` on two file steps:
             sk-file-1 carries the REAL note of OneSidedBound.lean (a committed input, note-onesidedbound.txt, the text between the first
             /-! and -/ verbatim) under a card title equal to the note's own first heading; sk-file-2 carries a hostile note. sk-file-3 has none.
typeset/     the notes map plus the four optional strings of the maths-face step (note_label_typeset, note_typeset_line, note_exact_button,
             note_render_button; note_label and note_source carry the final words): sk-file-1 the OneSidedBound note, sk-file-2 the hostile note
             with three formula-class hostile spans and the synthetic script spans (MATHS_SCRIPTS: three set, two refused), sk-file-3 the REAL LineCoordinates note carrying `review` {"state": "converter"}.
note-spans-classes.json   Sol's span classes (6,459 distinct real spans, cls3's class and one_letter), a committed input copied BYTE FOR BYTE
             by `--import-host` and checked here against its pinned sha256; note-linecoordinates.txt and note-onesidedbound.txt likewise.
skeleton/    the map of a Lean repository's parts, groups and files (data v3: sibling_layout, open_scale_floor, link flags on one group, index_rows and spine_rows on two files): kinds part, group, file, each a table row with `words` (the key's label)
             and `card_words` (the sheet's one line), the group and file rows with `count_words` (the foot's one/many); state "none", proof "none", no role on every step; symbols.order lists only
             the rows that occur (kinds [part, group, file], states [], proofs []) while the tables keep every row.
statements/  the statement-level sample (PR statements): one group, two files, the first file with three statements (theorem, lemma, def) in source order.
             Field names exactly as the data contract's section 31 amended; the words are read from site/strings-lean-statements.json (the one source).

Test-only. Never shipped (lives under test/).
"""
import copy, hashlib, importlib.util, json, os, shutil, html, sys

HERE = os.path.dirname(os.path.abspath(__file__))
COMMIT = "0123456789abcdef0123456789abcdef01234567"

STRINGS = {
    # runtime words (index.json strings); {n} stays literal. EXACTLY the fixed list plus the `words` key of every symbols row
    # (contract section 8): no key the page does not read.
    "parts_n": "{n} parts", "part_one": "1 part",
    "open_parts": "Open its parts", "close_parts": "Close its parts",
    "claim_more": "Show the whole claim", "claim_less": "Show less",
    "crumb_label": "Where this step sits",
    "key_kinds_heading": "Colour and shape: what Lean declares",
    "key_states_heading": "Frame: what we have read",
    "link_refused": "That address does not name a step on this map.",
    "parts_failed_notice": "The parts of this step could not be opened; tap it to try again.",
    "key_kind_theorem": "Theorem: a result the Lean code proves",
    "key_kind_def": "Definition: a named object or statement",
    "key_kind_structure": "Structure: a bundle of named fields",
    "sheet_statement_read": "Statement read",
    "sheet_statement_census": "Statement counted by a program",
    "sheet_statement_not_read": "Statement not read",
    "sheet_proof_read": "Proof read",
    "sheet_proof_not_read": "Proof: not read yet.",
    "sheet_proof_none": "No proof to read",
}
SHELL_STRINGS = {
    "title": "Reading the Riemann Hypothesis proof",
    "sentence": "A map of the computer-checked proof released on 20 November 2026, and of what we have read of each step so far. Written by AI agents, not mathematicians.",
    "about_link": "About this page", "tap_hint": "Tap a step to read it.",
    "map": "Map", "list": "List", "show_all": "Show all", "key": "Key", "close": "Close",
    "fallback_sentence": "The map did not load. Here are the steps as a list.",
    "fallback_link": "Open the list page",
}
SKELETON_WORDS = {
    "symbol_kind_part": "Part of the argument", "symbol_kind_group": "Group of files", "symbol_kind_file": "Lean file",
    "card_kind_part": "Part", "card_kind_group": "Group", "card_kind_file": "File",
    "count_group_one": "{n} group", "count_group_many": "{n} groups", "count_file_one": "{n} file", "count_file_many": "{n} files",
    "key_kinds_heading": "What a box is",
    "key_kinds_note": "Parts and groups follow the repository's own contents list (CONTENTS.md).",
    # PR 98 round 2 (data v3, edge basis): the key's first paragraph and the section that says what a line is. The words are the Lean map's
    # own, copied by hand as literals (never read from a host path at run time).
    "key_scope_text": ("The map holds the 306 Lean files of the proof's own argument (the folder New). Two short files at the top of the repository are not on it. "
                       "In the repository's words (grh/README.md): \"`src/Statements.lean` states the theorems in Mathlib's terms. `src/Main.lean` proves five theorems\", "
                       "the Riemann Hypothesis among them, each in a line or two from results on this map or from one another. "
                       "(The map's file named Main is New/Main.lean, a different file.) The map also leaves out the repository's own 495 library files (the folder Lib) and Mathlib. "
                       "A file's uses of those are not drawn."),
    "key_lines_heading": "What a line is",
    "key_lines_text": ("A line joins two files of the same group: the upper file uses definitions or results from the lower one. "
                       "Where a path of lines already connects two files, no direct line is drawn between them. Uses across groups are not drawn. "
                       "Lean also uses results it fills in on its own without naming them; those uses are not counted."),
}
SKELETON_STRINGS = {k: v for k, v in STRINGS.items() if not k.startswith("key_kind_") or k == "key_kinds_heading"}
SKELETON_STRINGS.update(SKELETON_WORDS)   # 11 fixed + 3 kind labels + 3 card words + 4 count words + 3 states + 3 proofs = 27, plus the optional key_kinds_note and key_scope_text, and the edge-basis pair key_lines_heading and key_lines_text


def _rows(table, strings=STRINGS, card_words=None, count_words=None):
    # `class` and `text` are the builder's own (the page validates them as strings and ignores them); `words` is a key of strings
    rows = {name: {"class": "builder-" + name, "text": strings[words], "words": words} for name, words in table}
    for name, cw in (card_words or {}).items():
        rows[name]["card_words"] = cw
    for name, cw in (count_words or {}).items():
        rows[name]["count_words"] = cw
    return rows


SYMBOLS = {
    "order": {"kinds": ["theorem", "def", "structure"], "proofs": ["read", "not_read", "none"], "states": ["read", "census", "none"]},
    "kinds": _rows([("theorem", "key_kind_theorem"), ("def", "key_kind_def"), ("structure", "key_kind_structure")]),
    "proofs": _rows([("read", "sheet_proof_read"), ("not_read", "sheet_proof_not_read"), ("none", "sheet_proof_none")]),
    "states": _rows([("read", "sheet_statement_read"), ("census", "sheet_statement_census"), ("none", "sheet_statement_not_read")]),
}

SYMBOLS_SKELETON = {
    "order": {"kinds": ["part", "group", "file"], "proofs": [], "states": []},
    "kinds": _rows([("part", "symbol_kind_part"), ("group", "symbol_kind_group"), ("file", "symbol_kind_file")], SKELETON_STRINGS,
                   {"part": "card_kind_part", "group": "card_kind_group", "file": "card_kind_file"},
                   {"group": {"one": "count_group_one", "many": "count_group_many"}, "file": {"one": "count_file_one", "many": "count_file_many"}}),
    "proofs": SYMBOLS["proofs"], "states": SYMBOLS["states"],
}
# the skeleton map: id -> (parent id or None, parent_rests_on, kind). One part holds two groups (an edgeless sibling set of groups);
# sk-group-a holds three files with a sibling link between two of them; sk-group-b holds an edgeless sibling set of two files, one
# of them with the 98-character title below (the clamp case). A second part holds ONE file (the "1 file" foot).
LONG_TITLE = "Lean file holding the definitions and the first lemmas of the zeta function on the critical strip."
assert len(LONG_TITLE) == 98 and LONG_TITLE.isascii()
SK_TREE = [("sk-part", None, False, "part"),
           ("sk-group-a", "sk-part", False, "group"), ("sk-group-b", "sk-part", True, "group"),
           ("sk-file-1", "sk-group-a", False, "file"), ("sk-file-2", "sk-group-a", True, "file"), ("sk-file-3", "sk-group-a", False, "file"),
           ("sk-file-4", "sk-group-b", False, "file"), ("sk-file-5", "sk-group-b", False, "file"),
           ("sk-part-2", None, False, "part"), ("sk-file-6", "sk-part-2", False, "file")]
REAL_SPAN_TITLE = "The second moments of the operators `P* s P`, and good forms"
SK_TITLES = {"sk-file-5": LONG_TITLE, "sk-file-4": REAL_SPAN_TITLE, "sk-group-b": "Files under `Formalism/Basic`"}
# (parent, from, to, weight, in_reduction). Data v3 (contract section 20): the links of a step file carry `weight` and `in_reduction`.
# sk-group-a: 1 -> 2 and 2 -> 3 are in the reduction, 1 -> 3 is not (it is the shortcut), so the page draws two of the three.
SK_LINKS = [("sk-group-a", "sk-file-1", "sk-file-2", 3, True), ("sk-group-a", "sk-file-2", "sk-file-3", 1, True),
            ("sk-group-a", "sk-file-1", "sk-file-3", 2, False)]
# Data v3 file-step rows (section 22): `index_rows` [{source, text}] and `spine_rows` [spine ids], on two file steps. Not drawn by the page layer.
SK_INDEX_ROWS = {"sk-file-1": [{"source": "grh/INDEX.md", "text": "The first file: the definitions the later files rest on."}],
                 "sk-file-4": [{"source": "grh/INDEX.md", "text": "The fourth file: the first lemma of the argument."},
                               {"source": "grh/INDEX.md", "text": "The fourth file, again: a second sentence about it."}]}
SK_SPINE_ROWS = {"sk-file-1": ["spine-theorem-a"], "sk-file-4": ["spine-theorem-b", "spine-theorem-c"]}

# id -> (parent id or None, parent_rests_on)
TREE = [
    ("goal-chain", None, False), ("inputs", None, False), ("bounds", None, False),
    ("a1", "goal-chain", True), ("a2", "goal-chain", False), ("a3", "goal-chain", True), ("a4", "goal-chain", False),
    ("topg", "goal-chain", False), ("a6", "goal-chain", False),
    ("a1-a", "a1", True), ("a1-b", "a1", False), ("a1-c", "a1", False), ("a1-d", "a1", True),
    ("a1-a-1", "a1-a", True), ("a1-a-2", "a1-a", False), ("a1-a-1-x", "a1-a-1", False),
    ("b1", "inputs", True), ("b2", "inputs", False), ("b3", "inputs", False),
    ("b1-a", "b1", False), ("b1-b", "b1", False),
    ("c1", "bounds", True), ("linkn", "bounds", False),
]
# links: (parent id or None for the top level, from, to)
LINKS = [(None, "goal-chain", "inputs"), (None, "inputs", "bounds"),
         ("goal-chain", "a1", "a2"), ("goal-chain", "a2", "a3"), ("goal-chain", "a4", "topg"),
         ("a1", "a1-b", "a1-a"), ("a1", "a1-c", "a1-d")]
ROLELESS = {"topg", "linkn"}
LONG = {"a1", "a3", "a1-a", "b1", "c1", "a1-a-1"}   # six long claims
KINDS = ["theorem", "def", "structure"]
STATES = ["read", "census", "none"]


def proof_of(i):
    """The proof state of a fixture card, derived from the card the way the builder derives it from proof_read: a definition or a
    structure has no proof to read; a theorem is read or not, alternating along the outline."""
    n = [t[0] for t in TREE].index(i)
    return "none" if KINDS[n % 3] != "theorem" else ("not_read" if n % 2 == 0 else "read")


def title_of(i):
    return "Title of step " + i


def build():
    ids = [t[0] for t in TREE]
    parent = {t[0]: t[1] for t in TREE}
    pro = {t[0]: t[2] for t in TREE}
    kids = {i: [t[0] for t in TREE if t[1] == i] for i in ids}

    def ancestors(i):
        out, p = [], parent[i]
        while p:
            out.insert(0, p)
            p = parent[p]
        return out

    def card(i, i_n):
        c = {"id": i, "title": title_of(i), "kind": KINDS[i_n % 3], "state": STATES[(i_n // 2) % 3], "proof": proof_of(i),
             "child_count": len(kids[i]), "path": ancestors(i)}
        if i not in ROLELESS:   # `role` is optional: absent on a role-less step (no role word anywhere)
            c["role"] = {"theorem": "Theorem", "def": "Definition", "structure": "Structure"}[c["kind"]]
        return c

    num = {i: n for n, i in enumerate(ids)}
    steps = {}
    for i in ids:
        ch = []
        for c in kids[i]:
            d = card(c, num[c]); d["parent_rests_on"] = pro[c]; ch.append(d)
        rests = [{"from": f, "to": t, "from_path": ancestors(i) + [i], "to_path": ancestors(i) + [i]}
                 for (p, f, t) in LINKS if p == i]
        steps[i] = {"format": 1, "commit": COMMIT, "id": i, "path": ancestors(i), "card": card(i, num[i]),
                    "children": ch, "rests_on": rests}
    top = [i for i in ids if parent[i] is None]
    index = {"format": 1, "commit": COMMIT, "max_children": 40, "top": top,
             "rests_on": [{"from": f, "to": t, "from_path": [], "to_path": []} for (p, f, t) in LINKS if p is None],
             "steps": len(ids), "symbols": SYMBOLS, "assets": {}, "strings": STRINGS}
    return index, steps, kids, parent, num


def build_skeleton(titles=None):
    ids = [t[0] for t in SK_TREE]
    parent = {t[0]: t[1] for t in SK_TREE}
    pro = {t[0]: t[2] for t in SK_TREE}
    kind = {t[0]: t[3] for t in SK_TREE}
    kids = {i: [t[0] for t in SK_TREE if t[1] == i] for i in ids}

    def ancestors(i):
        out, p = [], parent[i]
        while p:
            out.insert(0, p)
            p = parent[p]
        return out

    def title(i):
        return (SK_TITLES if titles is None else titles).get(i, kind[i].capitalize() + " " + i)

    def card(i):
        # a part, group or file asserts nothing: state none, proof none, and no role; a card with children names their kind
        c = {"id": i, "title": title(i), "kind": kind[i], "state": "none", "proof": "none", "child_count": len(kids[i]), "path": ancestors(i)}
        if kids[i]:
            ck = {kind[k] for k in kids[i]}
            assert len(ck) == 1, "the children of one step share a kind"
            c["child_kind"] = ck.pop()
        return c

    steps = {}
    for i in ids:
        ch = []
        for c in kids[i]:
            d = card(c); d["parent_rests_on"] = pro[c]; ch.append(d)
        rests = [{"from": f, "to": t, "from_path": ancestors(i) + [i], "to_path": ancestors(i) + [i], "weight": w, "in_reduction": red}
                 for (p, f, t, w, red) in SK_LINKS if p == i]
        steps[i] = {"format": 1, "commit": COMMIT, "id": i, "path": ancestors(i), "card": card(i), "children": ch, "rests_on": rests}
        if i in SK_INDEX_ROWS:
            steps[i]["index_rows"] = SK_INDEX_ROWS[i]
        if i in SK_SPINE_ROWS:
            steps[i]["spine_rows"] = SK_SPINE_ROWS[i]
    top = [i for i in ids if parent[i] is None]
    index = {"format": 1, "commit": COMMIT, "max_children": 40, "top": top, "rests_on": [], "steps": len(ids),
             "symbols": SYMBOLS_SKELETON, "assets": {}, "strings": SKELETON_STRINGS,
             "sibling_layout": "column", "open_scale_floor": 1,      # data v3 (sections 15 and 24): both optional, both absent on the live map
             "edge_basis": {"basis": "names-written-in-source-from-compiled-index", "words": "key_lines_text"}}   # data v3 (section 25): `words` names the strings key the key's line paragraph prints
    return index, steps, kids, title


NOTE_LABEL = "From the repository, unchanged"
NOTE_SOURCE = "Source file: {source} \u00b7 version {commit} of lsernau/grh-lean"
REAL_NOTE_FILE = os.path.join(HERE, "note-onesidedbound.txt")     # a committed static input: the inner text of the first /-! ... -/ block, verbatim
REAL_NOTE_SOURCE = "grh/src/New/Reduction/OneSidedBound.lean"
REAL_NOTE_TITLE = "The one-sided bound, and the theorem in half-plane form"     # the note's own first heading, so the card title equals it (N14)
HOSTILE_NOTE = (
    "# <script>alert(1)</script>\n\n"
    "<img src=x onerror=1> &amp;lt; javascript:alert(1) [x](javascript:y) <b>bold</b>\n\n"
    "* <script>alert(2)</script>\n"
    "* `<img src=x onerror=2>`\n\n"
    "3. javascript:void(0)\n"
    "4. [y](javascript:z)\n\n"
    "    <iframe src=javascript:alert(3)></iframe>\n\n"
    "| <b>h</b> | `<i>` |\n|---|---|\n| <u> | &lt; |\n")


# ---- the committed static inputs of the maths-face step. They are read ONLY from this directory; the one function that touches a host path is
# import_host() below, run by hand with explicit paths (`--import-host SPANS_JSON NEW_DIR`), never by a test and never by a default run.
SPANS_FILE = os.path.join(HERE, "note-spans-classes.json")
SPANS_SHA256 = "026713972092ac9784949e83cd77743525c97a213090d328a5ed5db2135ae8e2"
SPANS_BYTES = 585259
SPANS_ROWS = 6459
LC_NOTE_FILE = os.path.join(HERE, "note-linecoordinates.txt")
LC_NOTE_SOURCE = "grh/src/New/OneLift/ComparisonOperator/LineCoordinates.lean"
LC_NOTE_TITLE = "The polynomial map \u03b6, the datum \u03a8^add and the series \u03a5; norm, degree and denominator of \u03b6"
NOTE_FILES = [("note-onesidedbound.txt", REAL_NOTE_SOURCE), ("note-linecoordinates.txt", LC_NOTE_SOURCE)]
TYPESET_STRINGS = {
    "note_label": "The file's opening note, from the repository, unchanged",
    "note_label_typeset": "The file's opening note, from the repository",
    "note_source": "Opening note of {source} \u00b7 version {commit} of lsernau/grh-lean",
    "note_typeset_line": "Formulas are set in maths type by us from the repository's text, so some signs (such as ^ for a power) look different. Tap Show the exact text to see it as written.",
    "note_exact_button": "Show the exact text",
    "note_render_button": "Show the note with formulas set in maths type",
}
# two formula-class spans whose characters would be markup if they ever reached an HTML parser (tokens of one letter only: class formula)
HOSTILE_FORMULAS = "\n\n`<b>x</b>` and `a<i>b` and `x&y`\n"
# synthetic formula-class spans with scripts (sk-file-2, typeset map only): the first three are set (sup, sub and sup, a group with a sub),
# the last two are refused and stay code as typed. No real note text.
MATHS_SCRIPTS = "\nA power `y ^ 12`, a pair `P_\u03b4^N`, a group `x^{\u03b1_i}`, and two refused: `x^-1` and `a ^ b ^ c`.\n"


def note_of_file(path):
    """The inner text of a file's first /-! ... -/ block, verbatim (the same rule the builder and Sol's script use)."""
    with open(path, encoding="utf-8", newline="") as f:
        s = f.read()
    i = s.index("/-!")
    j = s.index("-/", i)
    return s[i + 3:j]


def import_host(spans_json, new_dir):
    """THE ONLY HOST READ. Copies Sol's span classes byte for byte and cuts the two real notes out of the Lean files, into this directory.
    Run by hand once; the result is committed and every other run (and every test) reads only the committed copies."""
    with open(spans_json, "rb") as f:
        raw = f.read()
    assert hashlib.sha256(raw).hexdigest() == SPANS_SHA256 and len(raw) == SPANS_BYTES, "not the pinned span classes file"
    with open(SPANS_FILE, "wb") as f:
        f.write(raw)
    for name, source in NOTE_FILES:
        text = note_of_file(os.path.join(new_dir, source.split("/src/New/", 1)[1]))
        assert "\r" not in text
        with open(os.path.join(HERE, name), "w", encoding="utf-8", newline="") as f:
            f.write(text)


def check_inputs():
    """The committed inputs are what the page's cases assume; a wrong one fails loud here, before any fixture is written."""
    with open(SPANS_FILE, "rb") as f:
        raw = f.read()
    assert hashlib.sha256(raw).hexdigest() == SPANS_SHA256 and len(raw) == SPANS_BYTES, "note-spans-classes.json is not the pinned file"
    meta = json.loads(raw.decode("utf-8"))
    assert meta["distinct"] == SPANS_ROWS == len(meta["spans"]), "the span classes file does not hold 6,459 rows"
    with open(LC_NOTE_FILE, encoding="utf-8", newline="") as f:
        lc = f.read()
    assert lc.startswith("\n# " + LC_NOTE_TITLE + "\n") and "\r" not in lc, "note-linecoordinates.txt is not the LineCoordinates note"
    return lc


def notes_build(typeset=False):
    """The skeleton map with notes: (index, steps, kids, title). typeset=True: the maths-face map (fixtures/typeset)."""
    with open(REAL_NOTE_FILE, encoding="utf-8", newline="") as f:
        real = f.read()
    assert real.startswith("\n# " + REAL_NOTE_TITLE + "\n") and "\r" not in real
    titles = dict(SK_TITLES, **{"sk-file-1": REAL_NOTE_TITLE})
    index, steps, kids, title = build_skeleton(titles)
    index = copy.deepcopy(index)
    if not typeset:
        index["strings"]["note_label"] = NOTE_LABEL
        index["strings"]["note_source"] = NOTE_SOURCE
        steps["sk-file-1"]["note"] = {"text": real, "source": REAL_NOTE_SOURCE}
        steps["sk-file-2"]["note"] = {"text": HOSTILE_NOTE, "source": "grh/src/New/Hostile.lean"}
        return index, steps, kids, title
    index["strings"].update(TYPESET_STRINGS)
    steps["sk-file-1"]["note"] = {"text": real, "source": REAL_NOTE_SOURCE}
    steps["sk-file-2"]["note"] = {"text": HOSTILE_NOTE + HOSTILE_FORMULAS + MATHS_SCRIPTS, "source": "grh/src/New/Hostile.lean"}
    steps["sk-file-3"]["note"] = {"text": check_inputs(), "source": LC_NOTE_SOURCE, "review": {"state": "converter"}}
    steps["sk-file-3"]["card"]["title"] = LC_NOTE_TITLE
    return index, steps, kids, title


def skeleton_article(i, kids, title):
    e = html.escape
    out = ['<article class="card" id="%s">' % i,
           '<h3 class="claim">%s</h3>' % e(title(i)),
           '<p class="note">The repository\'s own note for %s: what this entry holds.</p>' % e(i)]
    if kids[i]:
        out.append('<details class="children"><summary>Go deeper: the parts of this step</summary><ul class="children">')
        for c in kids[i]:
            out.append("<li>")
            out.append(skeleton_article(c, kids, title))
            out.append("</li>")
        out.append("</ul></details>")
    out.append("</article>")
    return "\n".join(out)


def _backtick_span():
    """The builder's ONE definition of a code span, imported from tools/notes_meta.py (never re-typed here)."""
    root = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", ".."))
    spec = importlib.util.spec_from_file_location("notes_meta_for_fixtures", os.path.join(root, "tools", "notes_meta.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod._BACKTICK_SPAN


EDGE_TITLES = ["a `x` b", "``", "``x``", "`a``b`", "a `b", "` `", "`a`b`", "x\n`y`", "x\r`y`", "`<b>&`", "no backtick at all",
               "`one` and `two`", "`x`", "``` `x` ```", "a ` b ` c", REAL_SPAN_TITLE]
REAL_TITLES_FILE = os.path.join(HERE, "backtick-real-titles.json")   # a committed static input: the real map's span titles, verbatim


def real_span_titles():
    """The real span titles, read ONLY from the committed input file. A missing or malformed file fails loud (no fallback, no skip)."""
    with open(REAL_TITLES_FILE, encoding="utf-8") as f:
        data = json.load(f)
    titles = data["titles"]
    assert titles and all(isinstance(t, str) and "`" in t for t in titles), "backtick-real-titles.json holds no span titles"
    return titles


def segments_of(span, title):
    """The expected segments, computed by the builder's own regex with re.sub semantics: [["text", s] | ["code", s], ...]."""
    out, pos = [], 0
    for m in span.finditer(title):
        if m.start() > pos:
            out.append(["text", title[pos:m.start()]])
        out.append(["code", m.group(1)])
        pos = m.end()
    if pos < len(title):
        out.append(["text", title[pos:]])
    return out


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, sort_keys=True, indent=1, ensure_ascii=False) + "\n")


def claim_text(i):
    base = "Claim of step %s: for every s with Re s > 1/2 the function does not vanish." % i
    if i in LONG:
        base += " " + " ".join("This sentence adds length to the claim of the step so that it needs many lines on a narrow screen (%d)." % k for k in range(1, 9))
    return base


def _proof_line(i):
    # the list page's own line (the graph page never reads it)
    return {"none": ['<p class="status proof">No proof to read: this step states a definition or a structure.</p>'],
            "not_read": ['<p class="status proof">Proof: not read yet.</p>'],
            "read": ['<p class="status proof">Proof read by Kepler on 2026-11-23.</p>']}[proof_of(i)]


def article(i, kids, depth=0):
    e = html.escape
    out = ['<article class="card" id="%s">' % i,
           '<h3 class="claim">%s</h3>' % e(claim_text(i)),
           '<p class="status statement">Statement read by Kepler on 2026-11-23.</p>',
           ] + _proof_line(i) + [
           '<p class="roots-only">Only the Lean roots of this step are listed here.</p>',
           '<details class="conditions"%s><summary>Conditions (1)</summary><ul><li>a condition</li></ul></details>' % (" open" if i == "a1" else ""),
           '<details class="uses"><summary>What it uses</summary><p>nothing yet</p></details>',
           '<details class="evidence"><summary>Evidence</summary><dl><dt>Lean name</dt><dd><code>Formalism.%s</code></dd></dl></details>' % e(i),
           '<ul class="reactions"><li><a class="reaction" href="#%s">This makes sense</a></li></ul>' % i]
    if kids[i]:
        out.append('<details class="children"><summary>Go deeper: the parts of this step</summary><ul class="children">')
        for c in kids[i]:
            out.append("<li>")
            out.append(article(c, kids, depth + 1))
            out.append("</li>")
        out.append("</ul></details>")
    out.append("</article>")
    return "\n".join(out)


def cards_html(top, kids):
    parts = ['<section id="graph-about"><h2>About this page</h2>',
             '<p>The zeta function and the Riemann Hypothesis paragraph.</p>',
             '<p>Each step names results in the Lean code.</p>',
             "</section>", '<ul class="chain">']
    for t in top:
        parts.append("<li>")
        parts.append(article(t, kids))
        parts.append("</li>")
    parts.append("</ul>")
    return "\n".join(parts) + "\n"


GRAPHVIEW_WORDS = {
    "view_cards": "Cards", "view_graph": "Graph",
    "graph_nodes_text": "Each box is one of the main results the repository names in its last step.",
    "spine_content_label": "In the repository's words", "spine_lives_in": "Lives in: {title}",
    "spine_show_file": "Show its file in Cards", "graph_failed_notice": "The graph could not be opened; tap Graph to try again.",
    "spine_lines_text": "A line means the upper result rests on the lower one. Made-up words of the fixture.",
}
# the made-up spine of the graphview fixture: four boxes over four files of the skeleton map; a rests on b and c, b and c on d, and a on d too (not in the reduction)
GV_SPINE = [("a", "sk-file-1", "Made-up sentence of box a."), ("b", "sk-file-2", "Made-up sentence of box b."),
            ("c", "sk-file-3", "Made-up sentence of box c."), ("d", "sk-file-4", "Made-up sentence of box d.")]
GV_LINKS = [("a", "b", True), ("a", "c", True), ("b", "d", True), ("c", "d", True), ("a", "d", False)]


def graphview_build():
    """The skeleton map with the Graph view's seven words, the spine's sentence key and a four-box spine.json (all made-up text)."""
    index, steps, kids, title = build_skeleton()
    index = json.loads(json.dumps(index))
    index["strings"] = dict(index["strings"], **GRAPHVIEW_WORDS)
    spine = {"commit": COMMIT, "format": 1, "edge_basis": {"basis": "reaches-through-any-chain-of-uses", "words": "spine_lines_text"},
             "nodes": [{"constants": ["New.Made.%s" % k], "content": text, "counts": {"mentions": 1, "no_doc": 1, "other_constants": 0}, "file": f,
                        "id": "spine-made-%s" % k, "mentions": [{"constant": "New.Made.other"}], "names": ["Made.%s" % k], "source": "grh/INDEX.md", "theorem": "`Made.%s`" % k}
                       for (k, f, text) in GV_SPINE],
             "links": [{"from": "spine-made-%s" % a, "in_reduction": red, "to": "spine-made-%s" % b} for (a, b, red) in GV_LINKS]}
    return index, steps, kids, title, spine


# ---------------------------------------------------------------------------------------------------------- statements/
STATEMENT_WORDS_FILE = os.path.join(HERE, "..", "..", "..", "..", "..", "site", "strings-lean-statements.json")
STMT_FILE_SOURCE = "grh/src/New/Fx/File.lean"
FX_PROMPT = "You are helping me read one statement. <b>x</b> and {page_url} stay literal.\nSecond line: &amp; <script>alert(1)</script>\n"
FX_HEADING = "### Section on the bounds\n\nThe lemmas of this section bound `f`."
FX_DOC = "The theorem `foo_bar`: for every `n` the bound holds.\n\nSecond paragraph of the repository's own comment."
FX_NOTE_SOURCE = "grh/src/New/Fx/File.lean"
HOSTILE_STATEMENT = "lemma baz (n : \u2115) : n \u2264 n + 1 := <script>alert(1)</script> {page_url}"


def statements_words():
    with open(STATEMENT_WORDS_FILE, encoding="utf-8") as f:
        return json.load(f)


def statements_build():
    """(index, steps): the statement sample. fx-group (kind group) holds fx-stmt-file and fx-file-2 (kind file); fx-stmt-file holds three statements."""
    W = statements_words()
    fixed = ["parts_n", "part_one", "open_parts", "close_parts", "claim_more", "claim_less", "crumb_label", "link_refused", "parts_failed_notice",
             "key_kinds_heading", "key_states_heading", "sheet_statement_read", "sheet_statement_census", "sheet_statement_not_read",
             "sheet_proof_read", "sheet_proof_not_read", "sheet_proof_none"]
    strings = {k: STRINGS[k] for k in fixed}
    strings.update({"symbol_kind_group": "Group of files", "symbol_kind_file": "Lean file", "symbol_kind_theorem": "Theorem", "symbol_kind_lemma": "Lemma",
                    "symbol_kind_def": "Definition", "card_kind_group": "Group", "card_kind_file": "File", "count_file_one": "{n} file", "count_file_many": "{n} files",
                    "spine_content_label": "In the repository's words", "note_label": NOTE_LABEL, "note_source": NOTE_SOURCE})
    strings.update(TYPESET_STRINGS)
    wanted = ["open_statements", "close_statements", "count_statement_one", "count_statement_many", "decl_kind_theorem", "decl_kind_lemma", "decl_kind_def",
              "decl_show_lean", "decl_hide_lean", "decl_lean_note", "decl_uses_here", "decl_uses_elsewhere", "decl_no_note", "key_statements_heading",
              "key_statements_text", "decl_heading_label", "decl_prompt_button", "decl_prompt_copied", "decl_prompt_note"]
    strings.update({k: W[k] for k in wanted})
    rows = _rows([("group", "symbol_kind_group"), ("file", "symbol_kind_file"), ("theorem", "symbol_kind_theorem"), ("lemma", "symbol_kind_lemma"), ("def", "symbol_kind_def")],
                 strings,
                 {"group": "card_kind_group", "file": "card_kind_file", "theorem": "decl_kind_theorem", "lemma": "decl_kind_lemma", "def": "decl_kind_def"},
                 {"file": {"one": "count_file_one", "many": "count_file_many"}})
    rows["group"]["open_words"] = {"open": "open_parts", "close": "close_parts"}
    rows["file"]["open_words"] = {"open": "open_statements", "close": "close_statements"}
    rows["file"]["child_count_words"] = {"one": "count_statement_one", "many": "count_statement_many"}
    symbols = {"order": {"kinds": ["group", "file", "theorem", "lemma", "def"], "proofs": [], "states": []}, "kinds": rows,
               "proofs": SYMBOLS["proofs"], "states": SYMBOLS["states"]}

    def card(i, title, kind, path, n=0, child_kind=None):
        c = {"id": i, "title": title, "kind": kind, "state": "none", "proof": "none", "child_count": n, "path": path}
        if child_kind:
            c["child_kind"] = child_kind
        return c

    def child(c, pro=False):
        d = dict(c); d["parent_rests_on"] = pro; return d

    here = ["fx-group", "fx-stmt-file"]
    g = card("fx-group", "Group `Fx`", "group", [], 2, "file")
    f1 = card("fx-stmt-file", "Lean file `Fx.File`", "file", ["fx-group"], 3)
    f2 = card("fx-file-2", "Lean file `Fx.Other`", "file", ["fx-group"])
    t1 = card("fx-thm-a", "`foo_bar`", "theorem", here)
    t2 = card("fx-lem-b", "`baz`", "lemma", here)
    t3 = card("fx-def-c", "`Fx.qux`", "def", here)
    base = {"format": 1, "commit": COMMIT}
    link = lambda a, b: {"from": a, "to": b, "from_path": here, "to_path": here, "weight": 1, "in_reduction": True}
    decl = lambda name, kw, text, var, uh, ue, heading=None: dict(
        name=name, source_path="src/New/Fx/File.lean", statement={"keyword": kw, "text": text}, variables=var, uses_here=uh, uses_elsewhere=ue, prompt=FX_PROMPT, **({"heading": heading} if heading else {}))
    steps = {
        "fx-group": dict(base, id="fx-group", path=[], card=g, children=[child(f1), child(f2, True)], rests_on=[]),
        "fx-stmt-file": dict(base, id="fx-stmt-file", path=["fx-group"], card=f1, children=[child(t1), child(t2), child(t3)],
                             rests_on=[link("fx-thm-a", "fx-lem-b"), link("fx-lem-b", "fx-def-c")]),
        "fx-file-2": dict(base, id="fx-file-2", path=["fx-group"], card=f2, children=[], rests_on=[]),
        "fx-thm-a": dict(base, id="fx-thm-a", path=here, card=t1, children=[], rests_on=[], note={"text": FX_DOC, "source": FX_NOTE_SOURCE},
                         **decl("Fx.foo_bar", "theorem", "theorem foo_bar (n : \u2115) : n \u2264 n + 1", False, [], [], FX_HEADING)),
        "fx-lem-b": dict(base, id="fx-lem-b", path=here, card=t2, children=[], rests_on=[],
                         **decl("Fx.baz", "lemma", HOSTILE_STATEMENT, True, [], [])),
        "fx-def-c": dict(base, id="fx-def-c", path=here, card=t3, children=[], rests_on=[], note={"text": "The definition `qux` of the file.", "source": FX_NOTE_SOURCE},
                         **decl("Fx.qux", "def", "def qux (n : \u2115) : \u2115 := n", False, ["fx-lem-b"], [{"name": "New.Other.helper", "step": "fx-file-2"}, {"name": "Mathlib.Foo.bar"}])),
    }
    index = {"format": 1, "commit": COMMIT, "max_children": 40, "top": ["fx-group"], "rests_on": [], "steps": len(steps),
             "symbols": symbols, "assets": {}, "strings": strings, "sibling_layout": "column", "open_scale_floor": 1}
    return index, steps


def refusal(name, index_edit=None, step_edit=None, raw_step=None, raw_index=None):
    index, steps, _k, _p, _n = build()
    # a small build: one top step with its children
    steps = json.loads(json.dumps(steps))
    keep = {"goal-chain": steps["goal-chain"]}
    for c in steps["goal-chain"]["children"]:
        keep[c["id"]] = steps[c["id"]]
    idx = json.loads(json.dumps(index))
    idx["top"] = ["goal-chain"]
    idx["rests_on"] = []
    idx["steps"] = len(keep)
    if index_edit:
        index_edit(idx)
    if step_edit:
        step_edit(keep)
    d = os.path.join(HERE, "refusals", name)
    write_json(os.path.join(d, "index.json"), idx)
    for sid, s in keep.items():
        write_json(os.path.join(d, "step", sid + ".json"), s)
    if raw_index is not None:
        open(os.path.join(d, "index.json"), "w", encoding="utf-8").write(raw_index)
    if raw_step is not None:
        for sid, text in raw_step.items():
            open(os.path.join(d, "step", sid + ".json"), "w", encoding="utf-8").write(text)


def main():
    check_inputs()
    for sub in ("real", "refusals", "skeleton", "notes", "typeset", "statements"):
        shutil.rmtree(os.path.join(HERE, sub), ignore_errors=True)
    index, steps, kids, parent, num = build()
    write_json(os.path.join(HERE, "real", "index.json"), index)
    for i, s in steps.items():
        write_json(os.path.join(HERE, "real", "step", i + ".json"), s)
    open(os.path.join(HERE, "real", "cards.html"), "w", encoding="utf-8").write(cards_html(index["top"], kids))
    write_json(os.path.join(HERE, "real", "shell-strings.json"), SHELL_STRINGS)

    sindex, ssteps, skids, stitle = build_skeleton()
    write_json(os.path.join(HERE, "skeleton", "index.json"), sindex)
    for i, st in ssteps.items():
        write_json(os.path.join(HERE, "skeleton", "step", i + ".json"), st)
    parts = ["<ul class=\"chain\">"] + ["<li>\n%s\n</li>" % skeleton_article(t, skids, stitle) for t in sindex["top"]] + ["</ul>"]
    open(os.path.join(HERE, "skeleton", "cards.html"), "w", encoding="utf-8").write(
        "\n".join(['<section id="graph-about"><h2>About this page</h2>', "<p>A map of the Lean repository.</p>", "</section>"] + parts) + "\n")

    gindex, gsteps, gkids, gtitle, gspine = graphview_build()
    write_json(os.path.join(HERE, "graphview", "index.json"), gindex)
    write_json(os.path.join(HERE, "graphview", "spine.json"), gspine)
    for i, st in gsteps.items():
        write_json(os.path.join(HERE, "graphview", "step", i + ".json"), st)
    gparts = ["<ul class=\"chain\">"] + ["<li>\n%s\n</li>" % skeleton_article(t, gkids, gtitle) for t in gindex["top"]] + ["</ul>"]
    open(os.path.join(HERE, "graphview", "cards.html"), "w", encoding="utf-8").write(
        "\n".join(['<section id="graph-about"><h2>About this page</h2>', "<p>A map of the Lean repository.</p>", "</section>"] + gparts) + "\n")

    nindex, nsteps, nkids, ntitle = notes_build()
    write_json(os.path.join(HERE, "notes", "index.json"), nindex)
    for i, st in nsteps.items():
        write_json(os.path.join(HERE, "notes", "step", i + ".json"), st)
    nparts = ["<ul class=\"chain\">"] + ["<li>\n%s\n</li>" % skeleton_article(t, nkids, ntitle) for t in nindex["top"]] + ["</ul>"]
    open(os.path.join(HERE, "notes", "cards.html"), "w", encoding="utf-8").write(
        "\n".join(['<section id="graph-about"><h2>About this page</h2>', "<p>A map of the Lean repository.</p>", "</section>"] + nparts) + "\n")

    tindex, tsteps, tkids, ttitle = notes_build(typeset=True)
    write_json(os.path.join(HERE, "typeset", "index.json"), tindex)
    for i, st in tsteps.items():
        write_json(os.path.join(HERE, "typeset", "step", i + ".json"), st)
    tparts = ["<ul class=\"chain\">"] + ["<li>\n%s\n</li>" % skeleton_article(t, tkids, ttitle) for t in tindex["top"]] + ["</ul>"]
    open(os.path.join(HERE, "typeset", "cards.html"), "w", encoding="utf-8").write(
        "\n".join(['<section id="graph-about"><h2>About this page</h2>', "<p>A map of the Lean repository.</p>", "</section>"] + tparts) + "\n")

    xindex, xsteps = statements_build()
    write_json(os.path.join(HERE, "statements", "index.json"), xindex)
    for i, st in xsteps.items():
        write_json(os.path.join(HERE, "statements", "step", i + ".json"), st)
    open(os.path.join(HERE, "statements", "cards.html"), "w", encoding="utf-8").write(
        "\n".join(['<section id="graph-about"><h2>About this page</h2>', "<p>A map of the Lean repository.</p>", "</section>"]) + "\n")

    def s_(k): return lambda st: st["goal-chain"].__setitem__(*k)

    refusal("bad-id", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("id", "Bad Id"))
    refusal("bad-id-in-top", index_edit=lambda i: i.__setitem__("top", ["goal-chain", "../x"]))
    refusal("unknown-kind", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("kind", "conjecture"))
    refusal("unknown-state", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("state", "half"))
    refusal("child-count-mismatch", step_edit=lambda st: st["goal-chain"]["card"].__setitem__("child_count", 5))
    refusal("path-invalid-id", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("path", ["Not Valid"]))
    refusal("non-json", raw_step={"goal-chain": "this is not json {"})
    refusal("non-json-index", raw_index="<html>not json</html>")

    def drop(st):
        pass
    refusal("missing-string", index_edit=lambda i: i["strings"].pop("open_parts"))
    refusal("empty-strings", index_edit=lambda i: i.__setitem__("strings", {}))
    refusal("bad-format", index_edit=lambda i: i.__setitem__("format", 2))
    refusal("link-not-sibling", step_edit=lambda st: st["goal-chain"]["rests_on"].append(
        {"from": "a1", "to": "elsewhere", "from_path": ["goal-chain"], "to_path": ["goal-chain"]}))
    refusal("commit-mismatch", step_edit=lambda st: st["goal-chain"].__setitem__("commit", "f" * 40))
    refusal("symbols-lacks-kind", index_edit=lambda i: (i["symbols"]["kinds"].pop("def"), i["symbols"]["order"]["kinds"].remove("def"), i["strings"].pop("key_kind_def")))

    def conjecture(i):      # a kind the page has no table entry for (`lemma` was one before the statement level)
        i["symbols"]["kinds"]["conjecture"] = {"class": "x", "text": "x", "words": "key_kind_theorem"}
        i["symbols"]["order"]["kinds"].append("conjecture")
    refusal("unrenderable-kind", index_edit=conjecture)

    def lemma_proof(i):
        i["symbols"]["proofs"]["maybe"] = {"class": "x", "text": "x", "words": "sheet_proof_read"}
        i["symbols"]["order"]["proofs"].append("maybe")
    refusal("unrenderable-proof", index_edit=lemma_proof)
    refusal("bad-proof-value", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("proof", "maybe"))
    refusal("missing-proof", step_edit=lambda st: st["goal-chain"]["children"][0].pop("proof"))
    refusal("missing-parts-failed-notice", index_edit=lambda i: i["strings"].pop("parts_failed_notice"))
    refusal("missing-words-string", index_edit=lambda i: i["strings"].pop("sheet_proof_read"))
    refusal("extra-string", index_edit=lambda i: i["strings"].__setitem__("bonus_word", "a word the page never reads"))
    refusal("extra-string-proofs-heading", index_edit=lambda i: i["strings"].__setitem__("key_proofs_heading", "Proof: what we have read of it"))
    # P3 (order is a subset of the table's names): the four refusals, one each. A shorter list is NOT one (it is a subset).
    # the kinds row's optional `card_words`: a strings key, non-empty
    refusal("card-words-missing-key", index_edit=lambda i: i["symbols"]["kinds"]["theorem"].__setitem__("card_words", "no_such_card_word"))
    refusal("card-words-empty", index_edit=lambda i: i["symbols"]["kinds"]["theorem"].__setitem__("card_words", ""))
    # F2: a card's optional `child_kind` and a kinds row's optional `count_words`
    refusal("child-kind-unknown", step_edit=lambda st: st["goal-chain"]["card"].__setitem__("child_kind", "nonsense"))
    refusal("child-kind-on-leaf", step_edit=lambda st: st["goal-chain"]["children"][1].__setitem__("child_kind", "theorem"))
    refusal("count-words-missing-key", index_edit=lambda i: i["symbols"]["kinds"]["theorem"].__setitem__("count_words", {"one": "no_such_count_word", "many": "parts_n"}))
    refusal("count-words-bad-shape", index_edit=lambda i: i["symbols"]["kinds"]["theorem"].__setitem__("count_words", {"one": "part_one", "many": "parts_n", "few": "parts_n"}))
    refusal("order-not-array", index_edit=lambda i: i["symbols"]["order"].__setitem__("kinds", "theorem"))
    refusal("order-unknown-name", index_edit=lambda i: i["symbols"]["order"].__setitem__("kinds", ["theorem", "lemma"]))
    refusal("order-kinds-empty", index_edit=lambda i: i["symbols"]["order"].__setitem__("kinds", []))
    refusal("order-repeats", index_edit=lambda i: i["symbols"]["order"].__setitem__("states", ["read", "read", "none"]))
    refusal("class-not-string", index_edit=lambda i: i["symbols"]["kinds"]["theorem"].__setitem__("class", 7))
    refusal("words-not-string", index_edit=lambda i: i["symbols"]["states"]["read"].__setitem__("words", 5))
    refusal("symbols-old-shape", index_edit=lambda i: i.__setitem__("symbols", {"kinds": ["theorem", "def", "structure"], "states": ["read", "census", "none"]}))
    refusal("empty-role", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("role", ""))
    refusal("role-not-string", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("role", 7))
    refusal("empty-title", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("title", ""))
    refusal("extra-key", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("claim_text", "x"))
    span = _backtick_span()
    titles = EDGE_TITLES + [t for t in real_span_titles() if t not in EDGE_TITLES]
    write_json(os.path.join(HERE, "backtick-titles.json"),
               {"definition": "tools/notes_meta.py _BACKTICK_SPAN", "cases": [{"title": t, "segments": segments_of(span, t)} for t in titles]})
    print("fixtures written; steps:", len(steps), "; backtick titles:", len(titles))


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--import-host":
        import_host(sys.argv[2], sys.argv[3])
        print("inputs imported from the host paths given; now run this script without arguments")
    else:
        assert len(sys.argv) == 1, "usage: make_fixtures.py [--import-host SPANS_JSON NEW_DIR]"
        main()
