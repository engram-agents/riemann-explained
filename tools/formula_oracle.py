#!/usr/bin/env python3
"""A measurement, not a build step: how the formula converter of `build_site.py` compares with pandoc's MathML on a list of formulas.

Each formula (one per line, with its `$` marks) goes through the converter of `build_site.py` (`formula_to_mathml`) and through
`pandoc -f markdown -t html --mathml`, and the two STRUCTURES are compared: the tag tree with every attribute and every text dropped,
pandoc's `<semantics>` wrapper and its `<annotation>` removed, and an `<mrow>` that holds a single child replaced by that child. (Neither
side merges adjacent `<mn>` or `<mi>`.) The run prints the number of formulas for which the structures agree, and EVERY formula that
differs, with a one-line diagnosis and which side is right. It always exits 0: a table to read, never a gate, never a build dependency.

usage: formula_oracle.py --run FORMULAS_FILE [FORMULAS_FILE ...]   (needs pandoc on the path; the formulas of the files are merged, sorted, once each)
       formula_oracle.py --selftest                               (no pandoc: built-in formulas and a recorded pandoc output)
"""
import html.parser
import importlib.util
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("build_site_for_oracle", os.path.join(HERE, "build_site.py"))
bs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(bs)

PANDOC = ["pandoc", "-f", "markdown", "-t", "html", "--mathml"]


def tree(markup):
    """The nested tag tree of the first <math> of `markup`: (tag, [children]), attributes and text dropped."""
    root = ("#root", [])
    stack = [root]

    class P(html.parser.HTMLParser):
        def handle_starttag(self, tag, attrs):
            node = (tag, [])
            stack[-1][1].append(node)
            stack.append(node)

        def handle_endtag(self, tag):
            if len(stack) > 1 and stack[-1][0] == tag:
                stack.pop()

    P(convert_charrefs=True).feed(markup)
    found = [n for n in _walk(root) if n[0] == "math"]
    return found[0] if found else None


def _walk(node):
    for ch in node[1]:
        yield ch
        yield from _walk(ch)


def normalise(node, drop=()):
    """The structure to compare: pandoc's <semantics> replaced by its first child and every <annotation> removed, an <mrow> with ONE child
    replaced by that child (the children are normalised first), and the tags in `drop` removed with their children."""
    tag, kids = node
    out = []
    for k in kids:
        if k[0] == "annotation" or k[0] in drop:
            continue
        n = normalise(k, drop)
        out.append(n)
    if tag == "semantics":
        return out[0] if out else ("mrow", [])
    if tag == "mrow" and len(out) == 1:
        return out[0]
    return (tag, out)


def flat(node):
    tag, kids = node
    return tag if not kids else tag + "(" + ",".join(flat(k) for k in kids) + ")"


def ours_structure(body, drop=()):
    ml = bs.formula_to_mathml(body)
    return None if ml is None else normalise(tree(ml), drop)


def pandoc_markup(formula):
    r = subprocess.run(PANDOC, input=formula, capture_output=True, text=True, check=True)
    return r.stdout


def pandoc_version():
    return subprocess.run(["pandoc", "--version"], capture_output=True, text=True, check=True).stdout.splitlines()[0]


# One line per KIND of difference, each with the side that is right. The kinds a formula has are found from its source text.
# (substring of the source, diagnosis)
RULES = (
    ("\\operatorname", "\\operatorname: pandoc <mo>Re</mo>, ours <mi mathvariant=normal> (function names are identifiers in MathML): ours right"),
    ("\\max", "named function: pandoc <mo>, ours <mi mathvariant=normal> (MathML writes function names as identifiers): ours right"),
    ("\\min", "named function: pandoc <mo>, ours <mi mathvariant=normal>: ours right"),
    ("\\log", "named function: pandoc <mo>, ours <mi mathvariant=normal>: ours right"),
    ("\\cos", "named function: pandoc <mo>, ours <mi mathvariant=normal>: ours right"),
    ("\\mathrm", "\\mathrm: pandoc one <mi> per letter, ours one <mi mathvariant=normal> per word (F26B choice): ours right"),
    ("'", "prime: pandoc writes the prime as a sibling <mi>, ours as the script of an <msup> (F26B): ours right"),
    ("\\infty", "\\infty: pandoc <mi>, F26B says <mo>; MathML practice is <mi>: pandoc right, F26B text to be revisited"),
    ("(", "fences: pandoc groups `( .. )` in an <mrow>, so a script after `)` sits on the whole group; ours is flat (the script sits on `)`, as TeX "
          "sets it, and our brackets are not stretchy): same rendering, pandoc's tree richer, ours chosen"),
    ("|", "bars: pandoc groups `| .. |` in an <mrow>, ours is flat (our bars are not stretchy): same rendering, pandoc's tree richer, ours chosen"),
)


EXTRA_RULES = (
    (lambda f: "/" in f, "`/`: pandoc <mi>/</mi>, ours <mo> (a division slash is an infix operator, F26B): ours right"),
    (lambda f: "!" in f.replace("\\!", ""), "`!`: pandoc <mi>!</mi>, ours <mo> (the factorial sign is a postfix operator, F26B): ours right"),
    (lambda f: "\\dots" in f, "\\dots: pandoc <mi>, F26B says <mo>: MathML 3 writes an ellipsis as an identifier, so pandoc is closer; F26B text to be revisited"),
)


def diagnose(formula):
    labels = [d for sub, d in RULES if sub in formula] + [d for pred, d in EXTRA_RULES if pred(formula)]
    return "; ".join(dict.fromkeys(labels)) or "structures differ, no known cause: look"


def compare(formulas, pandoc_of):
    """(rows, agree, both, agree_no_space, ours_unsupported): a row per formula: (formula, ours, pandoc, agrees). `pandoc_of(formula)` gives the
    pandoc markup. A formula the converter does not hold is counted apart and listed."""
    rows, agree, both, agree_ns, unsup = [], 0, 0, 0, []
    for f in formulas:
        body = f[1:-1] if f.startswith("$") and f.endswith("$") else f
        ours = ours_structure(body)
        if ours is None:
            unsup.append(f)
            continue
        theirs = normalise(tree(pandoc_of(f)))
        both += 1
        ok = ours == theirs
        agree += ok
        agree_ns += normalise(tree(bs.formula_to_mathml(body)), ("mspace",)) == normalise(tree(pandoc_of(f)), ("mspace",))
        rows.append((f, ours, theirs, ok))
    return rows, agree, both, agree_ns, unsup


def report(formulas, pandoc_of, version):
    rows, agree, both, agree_ns, unsup = compare(formulas, pandoc_of)
    out = [f"oracle: {version}; converter own-subset-{bs.FORMULA_VERSION} ({len(bs.FORMULA_COMMANDS)} commands); corpus {len(formulas)} formulas",
           f"converted by ours: {both} of {len(formulas)}; unsupported by ours: {len(unsup)}",
           f"agree {agree} of {both} (structure: tags only, attributes and text dropped); agree {agree_ns} of {both} with <mspace> ignored on both sides"]
    for f in unsup:
        out.append(f"UNSUPPORTED {f}")
    for f, ours, theirs, ok in rows:
        if not ok:
            out.append(f"DIFF {f}")
            out.append(f"  ours:   {flat(ours)}")
            out.append(f"  pandoc: {flat(theirs)}")
            out.append(f"  why:    {diagnose(f)}")
    return out


def read_formulas(paths):
    seen = set()
    for p in paths:
        with open(p, encoding="utf-8") as fh:
            seen.update(ln.rstrip("\n") for ln in fh if ln.strip())
    return sorted(seen)


# ---------------------------------------------------------------- self-test: no pandoc, a recorded output

def _fake(formula):
    """What pandoc 3.1.3 wrote for these formulas (recorded; attributes and annotation as it writes them)."""
    wrap = lambda inner, tex: ('<p><math display="inline" xmlns="http://www.w3.org/1998/Math/MathML"><semantics>' + inner
                               + f'<annotation encoding="application/x-tex">{tex}</annotation></semantics></math></p>')
    rec = {
        "$x$": wrap("<mi>x</mi>", "x"),
        "$x^2$": wrap("<msup><mi>x</mi><mn>2</mn></msup>", "x^2"),
        "$a + b$": wrap("<mrow><mi>a</mi><mo>+</mo><mi>b</mi></mrow>", "a + b"),
        "$\\max(a)$": wrap('<mrow><mo>max</mo><mrow><mo stretchy="true" form="prefix">(</mo><mi>a</mi><mo stretchy="true" form="postfix">)</mo></mrow></mrow>',
                           "\\max(a)"),
        "$\\foo$": None,
    }
    return rec[formula]


def selftest():
    ok = True

    def check(name, got, want):
        nonlocal ok
        if got != want:
            ok = False
            print(f"FAIL {name}\n  got  {got!r}\n  want {want!r}")
        else:
            print(f"PASS {name}")

    p = tree(_fake("$a + b$"))
    check("tree of a recorded pandoc output keeps the tags and drops attributes", flat(p), "math(semantics(mrow(mi,mo,mi),annotation))")
    check("normalise removes semantics and annotation", flat(normalise(p)), "math(mrow(mi,mo,mi))")
    check("an mrow with one child is replaced by it", flat(normalise(("math", [("mrow", [("mi", [])])]))), "math(mi)")
    check("an mrow with no child stays", flat(normalise(("math", [("mrow", [])]))), "math(mrow)")
    check("attributes do not count: <mi> and <mi mathvariant> are the same structure",
          flat(normalise(tree('<math><mi mathvariant="normal">x</mi></math>'))), "math(mi)")
    check("ours: x^2", flat(ours_structure("x^2")), "math(msup(mi,mn))")
    fs = ["$x$", "$x^2$", "$a + b$", "$\\max(a)$", "$\\foo$"]
    out = report(fs, _fake, "recorded pandoc output")
    check("summary: 4 converted of 5, agree 3 of 4", out[1:3], [
        "converted by ours: 4 of 5; unsupported by ours: 1",
        "agree 3 of 4 (structure: tags only, attributes and text dropped); agree 3 of 4 with <mspace> ignored on both sides"])
    body = [ln for ln in out[3:] if not ln.startswith("  ours") and not ln.startswith("  pandoc")]
    check("the unsupported formula and the differing one are listed, each with a reason (a named function and fences)",
          (body[:2], "named function" in body[2] and "fences" in body[2] and body[2].startswith("  why:    ")),
          (["UNSUPPORTED $\\foo$", "DIFF $\\max(a)$"], True))
    check("a formula with no known cause says so", diagnose("$x$"), "structures differ, no known cause: look")
    print("SELFTEST " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 4


def main(argv):
    if argv[1:] == ["--selftest"]:
        return selftest()
    if len(argv) >= 3 and argv[1] == "--run":
        formulas = read_formulas(argv[2:])
        cache = {}

        def pandoc_of(f):
            if f not in cache:
                cache[f] = pandoc_markup(f)
            return cache[f]
        print("\n".join(report(formulas, pandoc_of, pandoc_version())))
        return 0   # a measurement: never a gate
    print(__doc__.split("usage:")[1].strip(), file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
