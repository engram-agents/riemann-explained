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
  S4 the shell links to nothing but `credits/` (no `list/`: this map has no list page);
  S5 every `version <8 hex>` in the words is the first eight characters of the pin (--pin, default build_grh_credits.PIN, the pin the credits page
     is built for), so the version the words name cannot drift from it;
  S6 the page the assembler would write passes: build_site._graph_page over the shell and the words (the About block the escaped about_text, the
     section carrying data-page-feedback="off", cards empty), then build_site's static, element, head and code-on-surface checks over that page.
It reads the shell and the strings file and imports build_site and build_grh_credits; it writes nothing.
"""
import argparse
import importlib.util
import json
import os
import re
import sys
import tempfile

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
CREDITS_KEYS = ()   # the about_credits words the assembler's --page change reads (Luria); filled when that change names them
ASSEMBLER_KEYS = ("about_text", "root_only_note_single") + CREDITS_KEYS   # words the assembler reads itself, not through a token
SECTION_ATTRS = (("data-page-feedback", "off"),)
LINKS = ("credits/",)
_TOKEN = re.compile(r"\{\{S:([A-Za-z0-9_]+)\}\}")
_HREF = re.compile(r"""\bhref\s*=\s*["']([^"']*)["']""", re.I)
_VERSION = re.compile(r"\bversion ([0-9a-f]{8})\b")


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
        out += [f"LEAN-SHELL {k} names version {h}, not the pin's {pin[:8]}" for h in _VERSION.findall(v) if h != pin[:8]]           # S5
    out += [f"LEAN-SHELL href {h!r} is not one of {', '.join(LINKS)}" for h in _HREF.findall(shell_text) if h not in LINKS and not h.endswith(".css")]   # S4
    if out:
        return out
    errs, assets, _src_shell = bs._graph_assets(bs.GRAPH_SRC)                                                                        # S6
    if errs:
        return [f"LEAN-SHELL graph assets {e}" for e in errs]
    errs, page = bs._graph_page(shell_text.encode("utf-8"), set(assets), words, "<p>" + bs._e(words["about_text"]) + "</p>", "",
                                shell_keys=SHELL_KEYS, section_attrs=SECTION_ATTRS)
    if errs:
        return ["LEAN-SHELL page " + " ".join(e[1:]) for e in errs]
    found = bs.static_problems(page, "") + bs.graph_element_problems(page) + bs.head_meta_problems(page)
    out += [f"LEAN-SHELL page {f}" for f in found]
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
    case("L6", "a link to list/ (S4)", run(sh=shell_text.replace('href="credits/"', 'href="list/"')), ["LEAN-SHELL href 'list/' is not one of credits/"])
    other = "0" * 40
    case("L7", "the words name a version that is not the pin (S5)", run(p=other),
         [f"LEAN-SHELL {k} names version {pin[:8]}, not the pin's 00000000" for k in words if _VERSION.search(words[k])])
    case("L8", "a forbidden word (S3)", run(w=dict(words, close="Close (verified)")), ["LEAN-SHELL close holds the forbidden word 'verified'"])
    case("L9", "an empty word (S3)", run(w=dict(words, close="")), ["LEAN-SHELL close must be a non-empty string"])
    case("L10", "a script in the shell is refused by the builder's page checks (S6)",
         run(sh=shell_text.replace("</body>", '<script>alert(1)</script>\n</body>')), lambda g: bool(g) and all(x.startswith("LEAN-SHELL page") for x in g))
    case("L11", "markup in a word is escaped, not refused, and the page stays clean (S6)", run(w=dict(words, close="<b>Close</b>")), [])
    case("L12", "the real words name the pin at least once (S5 is not vacuous)", sum(len(_VERSION.findall(v)) for v in words.values()) >= 1, True)
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
