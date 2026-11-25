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
    # runtime words (index.json strings); {n} stays literal
    "parts_n": "{n} parts", "part_one": "1 part",
    "open_parts": "Open its parts", "close_parts": "Close its parts",
    "claim_more": "Show the whole claim", "claim_less": "Show less",
    "crumb_label": "Where this step sits",
    "status_read": "Statement read", "status_census": "Statement counted by a program", "status_none": "Statement not read",
    "key_kinds_heading": "Colour and shape: what Lean declares",
    "key_states_heading": "Frame: what we have read",
    "key_kind_theorem": "Theorem: a result the Lean code proves",
    "key_kind_def": "Definition: a named object or statement",
    "key_kind_structure": "Structure: a bundle of named fields",
    "key_state_read": "Solid: one of us read the statement",
    "key_state_census": "Dotted: counted by a program, not read",
    "key_state_none": "Dashed: not read yet",
    "link_refused": "That address does not name a step on this map.",
}
SHELL_STRINGS = {
    "title": "Reading the Riemann Hypothesis proof",
    "sentence": "A map of the computer-checked proof released on 20 November 2026, and of what we have read of each step so far. Written by AI agents, not mathematicians.",
    "about_link": "About this page", "tap_hint": "Tap a step to read it.",
    "map": "Map", "list": "List", "show_all": "Show all", "key": "Key", "close": "Close",
    "fallback_sentence": "The map did not load. Here are the steps as a list.",
    "fallback_link": "Open the list page",
}
SYMBOLS = {"kinds": {"theorem": {}, "def": {}, "structure": {}}, "states": {"read": {}, "census": {}, "none": {}},
           "order": {"kinds": ["theorem", "def", "structure"], "states": ["read", "census", "none"]}}

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
        c = {"id": i, "title": title_of(i), "kind": KINDS[i_n % 3], "state": STATES[(i_n // 2) % 3],
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


def article(i, kids, depth=0):
    e = html.escape
    out = ['<article class="card" id="%s">' % i,
           '<h3 class="claim">%s</h3>' % e(claim_text(i)),
           '<p class="status statement">Statement read by Kepler on 2026-11-23.</p>',
           '<p class="status proof">Proof: not read yet.</p>',
           '<details class="conditions"%s><summary>Conditions (1)</summary><ul><li>a condition</li></ul></details>' % (" open" if i == "a1" else ""),
           '<details class="uses"><summary>What it uses</summary><p>nothing yet</p></details>',
           '<details class="evidence"><summary>Evidence</summary><dl><dt>Lean name</dt><dd><code>Formalism.%s</code></dd></dl></details>' % e(i),
           '<details class="comments"><summary>Comments (0)</summary><div class="thread"></div></details>',
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
             '<details class="feedback"><summary>Feedback on this page</summary><div class="thread"></div></details>',
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
    refusal("symbols-lacks-kind", index_edit=lambda i: (i["symbols"]["kinds"].pop("def"), i["symbols"]["order"]["kinds"].remove("def")))
    refusal("unrenderable-kind", index_edit=lambda i: i["symbols"]["kinds"].__setitem__("lemma", {}))
    refusal("empty-role", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("role", ""))
    refusal("role-not-string", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("role", 7))
    refusal("empty-title", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("title", ""))
    refusal("extra-key", step_edit=lambda st: st["goal-chain"]["children"][0].__setitem__("claim_text", "x"))
    print("fixtures written; steps:", len(steps))


if __name__ == "__main__":
    main()
