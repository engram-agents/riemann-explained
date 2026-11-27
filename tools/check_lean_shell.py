#!/usr/bin/env python3
"""The Lean map's shell and its words agree: site/shell-lean.html and site/strings-lean-shell.json, the --shell and --strings of the assembler.

usage: check_lean_shell.py [--shell FILE] [--strings FILE] [--pin COMMIT]
       check_lean_shell.py --selftest

Checks, each a `LEAN-SHELL <what> <reason>` line on failure (exit 1; 0 when clean, 2 usage):
  S1 every `{{S:key}}` token of the shell is one the assembler lets a shell hold (build_site.GRAPH_SHELL_KEYS plus front_scope_line and readings_front);
  S2 every token has a word in the strings file, and every word of the strings file is a token of the shell or one of the keys the assembler reads
     itself (ASSEMBLER_KEYS): no token without a word, no word without a reader;
  S3 every word is a non-empty string, and no word holds a word of the forbidden list (build_site.FROZEN_WORDS and site/strings.json's
     forbidden_words, as whole words, any case), `of the proof` in its fraction sense, or a percent sign;
  S4 every ref of the shell (href, src, srcset; read by html.parser, quoted or not) is an asset of viewer/graph or `credits/`, the Licence and
     credits page that the assembler's --page run puts in the tree: the names the assembler's own ref check (PR 103, A11b) resolves against
     on a --page run. No `list/`: this map has no list page. (Without --page the assembler refuses `credits/ missing`, correctly.)
  S5 every run of 7 to 40 hex digits in the words (any case, standing alone) is a prefix of the pin (--pin, default build_grh_credits.PIN, the
     pin the credits page is built for), so a version the words name cannot drift from it. Deliberately loose: an ordinary word made only of
     the letters a to f (`defaced`) or a 7-digit number is refused too, loudly, and the fix is rewording; a run of 41 or more is not looked at;
  S6 the page the assembler would write passes: build_site._graph_page over the shell and the words, called as the assembler calls it (the
     About block: the escaped about_text paragraph, then the credits paragraph `<p>BEFORE<a href="credits/">LINK</a>AFTER</p>` as Luria's
     --page change writes it; the section carrying data-page-feedback="off"; cards empty), then build_site's static, element and head checks
     over that page, and the code-on-surface check only when build_site.CODE_ON_SURFACE_REFUSES is set, as the assembler does. With inputs
     limited to a shell and escaped words, the element and head checks cannot find what _graph_page's own shell checks did not; they are run
     because the assembler runs them, and no case can tell them apart (said here so it is not mistaken for coverage).
It reads the shell and the strings file and imports build_site and build_grh_credits; it writes nothing.
"""
import argparse
import html.parser
import importlib.util
import json
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)


def _load(name):
    key = "_leanshell_" + name
    if key not in sys.modules:
        spec = importlib.util.spec_from_file_location(key, os.path.join(_HERE, name + ".py"))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[key] = mod
        spec.loader.exec_module(mod)
    return sys.modules[key]


bs = _load("build_site")
cr = _load("build_grh_credits")

SHELL = os.path.join(_ROOT, "site", "shell-lean.html")
STRINGS = os.path.join(_ROOT, "site", "strings-lean-shell.json")
REPO_STRINGS = os.path.join(_ROOT, "site", "strings.json")
SHELL_KEYS = bs.GRAPH_SHELL_KEYS + ("front_scope_line", "readings_front")   # the tokens the assembler lets a shell hold (PR 103, SHELL_KEYS)
CREDITS_KEYS = ("about_credits_before", "about_credits_link", "about_credits_after")   # the About credits words the assembler's --page change reads (Luria, 39195)
ASSEMBLER_KEYS = ("about_text", "root_only_note_single") + CREDITS_KEYS   # words the assembler reads itself, not through a token
SECTION_ATTRS = (("data-page-feedback", "off"),)
CREDITS_REF = "credits/"
_TOKEN = re.compile(r"\{\{S:([A-Za-z0-9_]+)\}\}")
_HEX = re.compile(r"(?<![0-9A-Za-z])[0-9A-Fa-f]{7,40}(?![0-9A-Za-z])")


def _refs(text):
    """Every value of href, src and each srcset candidate in `text`, as html.parser reads it (quoted or not)."""
    found = []

    class P(html.parser.HTMLParser):
        def handle_starttag(self, tag, attrs):
            for k, v in attrs:
                if v is not None and k in ("href", "src"):
                    found.append(v.strip())
                elif v is not None and k == "srcset":
                    found.extend(c.split()[0] for c in v.split(",") if c.split())

    p = P()
    p.feed(text)
    p.close()
    return found


def about_markup(words):
    """The About block's inner html as the assembler writes it with --page: the about_text paragraph, then the credits paragraph, with nothing
    between them. Compared byte for byte with a real assembly by PR 119 at f26f81ec (the pinned data, 353 steps): equal."""
    e = bs._e
    return ("<p>" + e(words["about_text"]) + "</p><p>" + e(words["about_credits_before"]) + f'<a href="{CREDITS_REF}">'
            + e(words["about_credits_link"]) + "</a>" + e(words["about_credits_after"]) + "</p>")


def problems(shell_text, words, pin, forbidden):
    """[str]: one `LEAN-SHELL <what> <reason>` per finding of S1 to S6."""
    out = []
    tokens = list(dict.fromkeys(_TOKEN.findall(shell_text)))
    out += [f"LEAN-SHELL {{{{S:{t}}}}} is not a key the assembler lets a shell hold" for t in tokens if t not in SHELL_KEYS]        # S1
    out += [f"LEAN-SHELL {t} has no word in the strings file" for t in tokens if t not in words]                                      # S2
    out += [f"LEAN-SHELL {k} is a word no token or assembler key reads" for k in words if k not in tokens and k not in ASSEMBLER_KEYS]
    out += [f"LEAN-SHELL {k} missing (the assembler reads it)" for k in ASSEMBLER_KEYS if k not in words]
    for k, v in words.items():                                                                                                      # S3
        if not (isinstance(v, str) and v):
            out.append(f"LEAN-SHELL {k} must be a non-empty string")
            continue
        for w in forbidden:
            if re.search(r"(?<![A-Za-z])" + re.escape(w) + r"(?![A-Za-z])", v, re.I):
                out.append(f"LEAN-SHELL {k} holds the forbidden word {w!r}")
        if bs._FRACTION.search(v):
            out.append(f"LEAN-SHELL {k} holds 'of the proof' as a fraction")
        elif "%" in v:
            out.append(f"LEAN-SHELL {k} holds a percent sign")
        out += [f"LEAN-SHELL {k} names {h}, which is not a prefix of the pin {pin}" for h in _HEX.findall(v) if not pin.startswith(h.lower())]   # S5
    errs, assets, _src_shell = bs._graph_assets(bs.GRAPH_SRC)
    if errs:
        return out + [f"LEAN-SHELL graph assets {e}" for e in errs]
    names = set(assets) | {CREDITS_REF}
    out += [f"LEAN-SHELL ref {r!r} is not an asset or {CREDITS_REF}" for r in dict.fromkeys(_refs(shell_text)) if r not in names]          # S4
    if out:
        return out
    errs, page = bs._graph_page(shell_text.encode("utf-8"), set(assets), words, about_markup(words), "",                               # S6
                                shell_keys=SHELL_KEYS, section_attrs=SECTION_ATTRS)
    if errs:
        return ["LEAN-SHELL page " + " ".join(e[1:]) for e in errs]
    found = bs.static_problems(page, "") + bs.graph_element_problems(page) + bs.head_meta_problems(page)
    out += [f"LEAN-SHELL page {f}" for f in found]
    if bs.CODE_ON_SURFACE_REFUSES:   # read at the call, as the assembler does
        out += [f"LEAN-SHELL page code on the surface: {text[:60]} x{k}" for _card, text, k in bs.code_spans(bs.surface_scan(page)[1])]
    return out


def _forbidden():
    with open(REPO_STRINGS, encoding="utf-8") as f:
        return list(dict.fromkeys(list(bs.FROZEN_WORDS) + [w for w in json.load(f)["forbidden_words"] if w]))


def _read(shell, strings):
    with open(shell, encoding="utf-8") as f:
        shell_text = f.read()
    with open(strings, encoding="utf-8") as f:
        words = json.load(f)
    if not isinstance(words, dict):
        raise ValueError("the strings file is not a JSON object")
    return shell_text, words


# ---------------------------------------------------------------- self-test: the real pair passes; each one wrong change is the one named finding
def _selftest():
    shell_text, words = _read(SHELL, STRINGS)
    pin, fw = cr.PIN, _forbidden()
    results = []

    def case(cid, desc, got, want):
        ok = want(got) if callable(want) else got == want
        results.append(ok)
        print(f"{'PASS' if ok else 'FAIL'} {cid} {desc}" + ("" if ok else f"\n  got: {got}"))

    def run(sh=shell_text, w=words, p=pin):
        return problems(sh, w, p, fw)

    case("L1", "the real shell and words are clean", run(), [])
    case("L2", "a token without a word (S2)", run(sh=shell_text.replace("{{S:key}}", "{{S:key}}{{S:list}}")), ["LEAN-SHELL list has no word in the strings file"])
    case("L3", "a word without a token (S2)", run(w=dict(words, list="List")), ["LEAN-SHELL list is a word no token or assembler key reads"])
    case("L4", "a token the assembler does not allow (S1)", run(sh=shell_text.replace("{{S:key}}", "{{S:key}}{{S:labels}}"), w=dict(words, labels="x")),
         lambda g: g[:1] == ["LEAN-SHELL {{S:labels}} is not a key the assembler lets a shell hold"])
    case("L5", "an assembler key missing (S2)", run(w={k: v for k, v in words.items() if k != "root_only_note_single"}),
         ["LEAN-SHELL root_only_note_single missing (the assembler reads it)"])
    case("L6", "a link to list/ (S4)", run(sh=shell_text.replace('href="credits/"', 'href="list/"')), ["LEAN-SHELL ref 'list/' is not an asset or credits/"])
    case("L6b", "an unquoted link to list/ (S4)", run(sh=shell_text.replace('href="credits/"', 'href=list/')), ["LEAN-SHELL ref 'list/' is not an asset or credits/"])
    case("L6c", "a stylesheet that is not an asset (S4: no blanket .css pass)", run(sh=shell_text.replace('href="graph.css"', 'href="list/x.css"')),
         ["LEAN-SHELL ref 'list/x.css' is not an asset or credits/"])
    other = "0" * 40
    case("L7", "the words name a version that is not the pin (S5)", run(p=other),
         [f"LEAN-SHELL {k} names {pin[:8]}, which is not a prefix of the pin {other}" for k in words if pin[:8] in words[k]])
    for cid, text, hexrun in (("L7b", "version 72fead11", "72fead11"), ("L7c", "Version DEADBEEF", "DEADBEEF"), ("L7d", "version deadbeef01", "deadbeef01")):
        case(cid, f"a drifted version {text!r} (S5: any case, any length 7 to 40)", run(w=dict(words, close=f"Close ({text})")),
             [f"LEAN-SHELL close names {hexrun}, which is not a prefix of the pin {pin}"])
    case("L6d", "a script src that is not an asset (S4 reads src)", run(sh=shell_text.replace('src="page/app.js"', 'src="list/x.js"')),
         ["LEAN-SHELL ref 'list/x.js' is not an asset or credits/"])
    case("L6e", "a srcset candidate that is not an asset (S4 reads srcset)", run(sh=shell_text.replace("</header>", '<img srcset="list/a.png 1x" alt="">\n</header>')),
         ["LEAN-SHELL ref 'list/a.png' is not an asset or credits/"])
    case("L7f", "a 7-digit run that is not a prefix of the pin (S5 starts at 7)", run(w=dict(words, close="Close 1234567")),
         [f"LEAN-SHELL close names 1234567, which is not a prefix of the pin {pin}"])
    case("L7g", "a run inside the pin but not at its start (S5 wants a prefix)", run(w=dict(words, close=f"Close {pin[8:16]}")),
         [f"LEAN-SHELL close names {pin[8:16]}, which is not a prefix of the pin {pin}"])
    case("L7e", "the full 40-hex pin and a longer prefix pass (S5)", run(w=dict(words, close=f"Close {pin} {pin[:12]}")), [])
    case("L8", "a forbidden word (S3)", run(w=dict(words, close="Close (verified)")), ["LEAN-SHELL close holds the forbidden word 'verified'"])
    case("L8b", "a forbidden word inside a longer word is not a match (S3: whole words)", run(w=dict(words, close="Close (unverified)")), [])
    case("L8c", "a forbidden word in capitals (S3: any case)", run(w=dict(words, close="Close (VERIFIED)")), ["LEAN-SHELL close holds the forbidden word 'verified'"])
    case("L9", "an empty word (S3)", run(w=dict(words, close="")), ["LEAN-SHELL close must be a non-empty string"])
    case("L10", "a script in the shell is refused by the builder's page checks (S6)",
         run(sh=shell_text.replace("</body>", '<script>alert(1)</script>\n</body>')), lambda g: bool(g) and all(x.startswith("LEAN-SHELL page") for x in g))
    case("L11", "markup in a word is escaped, not refused, and the page stays clean (S6)", run(w=dict(words, close="<b>Close</b>")), [])
    case("L12", "the real words name the pin at least once (S5 is not vacuous)", sum(len(_HEX.findall(v)) for v in words.values()) >= 1, True)
    case("L13", "a percent sign (S3)", run(w=dict(words, close="5% done")), ["LEAN-SHELL close holds a percent sign"])
    case("L14", "'of the proof' as a fraction (S3)", run(w=dict(words, close="half of the proof")), ["LEAN-SHELL close holds 'of the proof' as a fraction"])
    case("L15", "a word that reads as code is refused by the static check after the page is made (S6)", run(w=dict(words, close="call fetch(x) here")),
         lambda g: bool(g) and all(x.startswith("LEAN-SHELL page") and "fetch(" in x for x in g))
    case("L16", "the About block carries the credits link as the assembler writes it (S6)",
         about_markup(words).count('<a href="credits/">Licence and credits</a>'), 1)
    keep = bs.CODE_ON_SURFACE_REFUSES
    bs.CODE_ON_SURFACE_REFUSES = True
    try:
        coded = shell_text.replace('<p class="sentence">', '<p class="sentence"><code>x = f(1)</code> ', 1)
        case("L17", "with the builder's code-on-surface flag set, a code span on the page is found (S6)", run(sh=coded),
             ["LEAN-SHELL page code on the surface: x = f(1) x1"])
        case("L17b", "with the flag set, the real pair stays clean (S6)", run(), [])
    finally:
        bs.CODE_ON_SURFACE_REFUSES = keep
    print(f"{sum(results)}/{len(results)} pass")
    return 0 if all(results) else 4


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--shell", default=SHELL)
    ap.add_argument("--strings", default=STRINGS)
    ap.add_argument("--pin", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()
    pin = a.pin or cr.PIN
    if not re.fullmatch(r"[0-9a-f]{40}", pin):
        print("LEAN-SHELL --pin must be 40 lower-case hex characters")
        return 2
    shell_text, words = _read(a.shell, a.strings)
    found = problems(shell_text, words, pin, _forbidden())
    print("\n".join(found) if found else f"LEAN-SHELL clean: {len(_TOKEN.findall(shell_text))} tokens, {len(words)} words, pin {pin[:8]}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
