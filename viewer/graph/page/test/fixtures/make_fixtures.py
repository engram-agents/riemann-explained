#!/usr/bin/env python3
"""Writes the literal fixture files under this directory. The OUTPUT is committed; this script is how it was made.

real/        a small build shaped like the contract's section 6 measurement: 23 steps, 3 top, depth 5, widest 6,
             2 top-level rests_on, 5 step-file rests_on, 7 parent_rests_on true. Plus the card markup (nested like the
             list page: a child's article sits inside its parent's details.children) and the shell's word table.
refusals/    one tiny build per refusal.

Test-only. Never shipped (lives under test/).
"""
import json, os, shutil, html

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
def _rows(table):
    # `class` and `text` are the builder's own (the page validates them as strings and ignores them); `words` is a key of strings
    return {name: {"class": "builder-" + name, "text": STRINGS[words], "words": words} for name, words in table}


SYMBOLS = {
    "order": {"kinds": ["theorem", "def", "structure"], "proofs": ["read", "not_read", "none"], "states": ["read", "census", "none"]},
    "kinds": _rows([("theorem", "key_kind_theorem"), ("def", "key_kind_def"), ("structure", "key_kind_structure")]),
    "proofs": _rows([("read", "sheet_proof_read"), ("not_read", "sheet_proof_not_read"), ("none", "sheet_proof_none")]),
    "states": _rows([("read", "sheet_statement_read"), ("census", "sheet_statement_census"), ("none", "sheet_statement_not_read")]),
}

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
    return {"none": [], "not_read": ['<p class="status proof">Proof: not read yet.</p>'],
            "read": ['<p class="status proof">Proof read by Kepler on 2026-11-23.</p>']}[proof_of(i)]


def article(i, kids, depth=0):
    e = html.escape
    out = ['<article class="card" id="%s">' % i,
           '<h3 class="claim">%s</h3>' % e(claim_text(i)),
           '<p class="status statement">Statement read by Kepler on 2026-11-23.</p>',
           ] + _proof_line(i) + [
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
    for sub in ("real", "refusals"):
        shutil.rmtree(os.path.join(HERE, sub), ignore_errors=True)
    index, steps, kids, parent, num = build()
    write_json(os.path.join(HERE, "real", "index.json"), index)
    for i, s in steps.items():
        write_json(os.path.join(HERE, "real", "step", i + ".json"), s)
    open(os.path.join(HERE, "real", "cards.html"), "w", encoding="utf-8").write(cards_html(index["top"], kids))
    write_json(os.path.join(HERE, "real", "shell-strings.json"), SHELL_STRINGS)

    def s_(k): return lambda st: st["goal-chain"].__setitem__(*k)

    refusal("bad-id", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("id", "Bad Id"))
    refusal("bad-id-in-top", index_edit=lambda i: i.__setitem__("top", ["goal-chain", "../x"]))
    refusal("unknown-kind", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("kind", "lemma"))
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

    def lemma(i):
        i["symbols"]["kinds"]["lemma"] = {"class": "x", "text": "x", "words": "key_kind_theorem"}
        i["symbols"]["order"]["kinds"].append("lemma")
    refusal("unrenderable-kind", index_edit=lemma)

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
    refusal("order-not-permutation", index_edit=lambda i: i["symbols"]["order"].__setitem__("kinds", ["theorem", "def"]))
    refusal("order-repeats", index_edit=lambda i: i["symbols"]["order"].__setitem__("states", ["read", "read", "none"]))
    refusal("class-not-string", index_edit=lambda i: i["symbols"]["kinds"]["theorem"].__setitem__("class", 7))
    refusal("words-not-string", index_edit=lambda i: i["symbols"]["states"]["read"].__setitem__("words", 5))
    refusal("symbols-old-shape", index_edit=lambda i: i.__setitem__("symbols", {"kinds": ["theorem", "def", "structure"], "states": ["read", "census", "none"]}))
    refusal("empty-role", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("role", ""))
    refusal("role-not-string", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("role", 7))
    refusal("empty-title", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("title", ""))
    refusal("extra-key", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("claim_text", "x"))
    print("fixtures written; steps:", len(steps))


if __name__ == "__main__":
    main()
