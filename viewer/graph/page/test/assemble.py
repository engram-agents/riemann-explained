#!/usr/bin/env python3
"""A stand-in for the builder, for tests only: writes a Graph page build into a directory.

  graph/index.html   the pinned shell with {{S:key}} filled (escaped, text positions only) and {{CARDS}} replaced
  graph/graph.css, graph/page/*.js     copied byte for byte from viewer/graph/ (nothing under test/)
  graph/engine/*     the REAL engine's shipped files, or the test double (engine="double")
  graph/index.json, graph/step/*.json   a fixture build (optionally edited by the caller)
  graph/list/index.html   a stand-in list page, so the List link (the relative address `list/`) has somewhere to go

Never shipped (lives under test/).
"""
import html, json, os, re, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
GRAPH = os.path.abspath(os.path.join(HERE, "..", ".."))           # viewer/graph
FIX = os.path.join(HERE, "fixtures", "real")


def shipped(root):
    """Every .js and .css under root whose path has no test/ segment, relative path kept (the builder's rule)."""
    out = []
    for base, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != "test"]
        for n in names:
            if n.endswith((".js", ".css")):
                out.append(os.path.relpath(os.path.join(base, n), root))
    return sorted(out)


def fill_shell(shell, cards, words):
    def rep(m):
        k = m.group(1)
        if k not in words:
            raise KeyError("shell word without a value: " + k)
        return html.escape(words[k], quote=False)
    out = re.sub(r"\{\{S:([a-z_]+)\}\}", rep, shell)
    assert out.count("{{CARDS}}") == 1
    return out.replace("{{CARDS}}", cards)


def assemble(out, engine="real", mutate=None, index_edit=None, step_edit=None, words_edit=None, cards_edit=None, shell_edit=None, fix=None):
    """fix: the fixture directory under fixtures/ (default "real"; "modules" is the Lean-repository map); the shell words are always real's.
    mutate: {relative path under graph/: function(text)->text}, applied to the copied files (used for mutants)."""
    g = os.path.join(out, "graph")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(os.path.join(g, "page"))
    for rel in shipped(GRAPH):
        if rel.startswith("engine" + os.sep):
            continue
        dst = os.path.join(g, rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(os.path.join(GRAPH, rel), dst)
    os.makedirs(os.path.join(g, "engine"))
    if engine == "double":
        shutil.copyfile(os.path.join(HERE, "double_engine.js"), os.path.join(g, "engine", "index.js"))
        open(os.path.join(g, "engine", "engine.css"), "w").write("/* the double has no stylesheet of its own */\n")
    else:
        for rel in shipped(os.path.join(GRAPH, "engine")):
            shutil.copyfile(os.path.join(GRAPH, "engine", rel), os.path.join(g, "engine", rel))
    for rel, fn in (mutate or {}).items():
        p = os.path.join(g, rel)
        src = open(p, encoding="utf-8").read()      # read BEFORE opening for write (which truncates)
        open(p, "w", encoding="utf-8").write(fn(src))
    # data
    D = FIX if fix is None else os.path.join(HERE, "fixtures", fix)
    index = json.load(open(os.path.join(D, "index.json"), encoding="utf-8"))
    steps = {f[:-5]: json.load(open(os.path.join(D, "step", f), encoding="utf-8")) for f in os.listdir(os.path.join(D, "step"))}
    if index_edit:
        index_edit(index)
    if step_edit:
        step_edit(steps)
    json.dump(index, open(os.path.join(g, "index.json"), "w", encoding="utf-8"), sort_keys=True, indent=1, ensure_ascii=False)
    os.makedirs(os.path.join(g, "step"))
    for i, s in steps.items():
        json.dump(s, open(os.path.join(g, "step", i + ".json"), "w", encoding="utf-8"), sort_keys=True, indent=1, ensure_ascii=False)
    # the page
    words = json.load(open(os.path.join(FIX, "shell-strings.json"), encoding="utf-8"))
    if words_edit:
        words_edit(words)
    cards = open(os.path.join(D, "cards.html"), encoding="utf-8").read()
    if cards_edit:
        cards = cards_edit(cards)
    shell = open(os.path.join(GRAPH, "shell.html"), encoding="utf-8").read()
    if shell_edit:
        shell = shell_edit(shell)
    open(os.path.join(g, "index.html"), "w", encoding="utf-8").write(fill_shell(shell, cards, words))
    os.makedirs(os.path.join(g, "list"))
    open(os.path.join(g, "list", "index.html"), "w", encoding="utf-8").write(
        "<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>list</title></head><body><main id=\"list-page\">" + cards + "</main></body></html>\n")
    return g


if __name__ == "__main__":
    import sys
    assemble(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "real")
    print("assembled", sys.argv[1])
