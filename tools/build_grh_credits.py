#!/usr/bin/env python3
"""The Licence and credits page of the Lean map: ONE static file, credits/index.html, built from the repository's own files at the pin.

usage: build_grh_credits.py --grh-repo DIR --pin COMMIT --strings site/strings.json --credits-strings site/strings-lean-credits.json --out FILE
       build_grh_credits.py --selftest

DIR is a checkout of lsernau/grh-lean (the repository root, which holds grh/). The tool refuses unless DIR's HEAD is COMMIT and COMMIT is the pin this
tool was written for (PIN), and unless every file it reads has the SHA-256 recorded in SOURCES: a repository file is never retyped, and a changed byte is a
refusal, not a silent new page. Read through build_grh_skeleton's bounded, contained reader (1 MiB, no symlink, regular file), decoded as strict UTF-8.

The page, in order (headings and our lines are strings; every byte of the repository is escaped with build_site._e and shown as preformatted text):
  title; a link back to the map (../);
  The repository's licence (LICENSE, whole); its NOTICE file (grh/NOTICE, whole); its ATTRIBUTION file (grh/ATTRIBUTION.md, whole, after our one introducing
  line, which links the file at the pin); who made the proof, in the repository's words (grh/README.md lines 5, 6 and 10; README.md lines 9 to 11, each
  under the name of its file); our map (licence of our code and text, the credit line, the pin with a link to the repository at the pin); not an endorsement.
It holds no script, no external resource and no form; its links are ../ and https links to the repository at the pin (class `citation`, the one kind the
static check lets stand). The tool runs build_site's static_problems, element_problems (the document table), head_meta_problems and link_problems on the page
and refuses on any finding. Our words pass build_site._strings_problems (R3, the forbidden words, the percent sign, `of the proof`, placeholders) with the
placeholders of CREDITS_PLACEHOLDERS added to the builder's table for the call.

Exit codes: 0 written, 1 refused (one `CREDITS-<CODE> <what>` line per refusal, nothing written), 2 usage. --selftest: 0 all pass, 4 one fails.
"""
import argparse
import hashlib
import html.parser
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    key = "_credits_" + name
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


bs = _load("build_site")
sk = _load("build_grh_skeleton")

PIN = "72fead102f663d5c7a407964a13dc0cf9d977207"
REPO = "lsernau/grh-lean"
# Every file the page shows, with its SHA-256 at PIN (measured on a checkout at PIN, 2026-11-26).
SOURCES = {
    "LICENSE": "c71d239df91726fc519c6eb72d318ec65820627232b2f796219e87dcf35d0ab4",
    "grh/NOTICE": "addbc1704aa68328c99cae493118f6f18d8f3b83af8facdb9f150dce81e1a65c",
    "grh/ATTRIBUTION.md": "b282f31534ec2ca1c500b4a87ba50282e442c49298e5fec97e444348d3f58d13",
    "grh/README.md": "2b4950f6495cd801359292328c932a0cb8aaf3e6deafd67460e85825e5de6a7a",
    "README.md": "64013d96486fb6b91793cfb522f9ab0b221ed8c81e96690a4f4c41ca5b8a7851",
}
QUOTES = (("grh/README.md", (5, 6, 10)), ("README.md", (9, 10, 11)))   # 1-based line numbers, as ruled (Kepler 38876)
CREDITS_PLACEHOLDERS = {"credits_attribution_after": {"commit", "repo"}, "credits_pin_link": {"commit", "repo"}, "credits_from_file": {"file"}}
CREDITS_KEYS = ("credits_title", "credits_back", "credits_h_licence", "credits_h_notice", "credits_h_attribution", "credits_attribution_before",
                "credits_attribution_after", "credits_h_who", "credits_from_file", "credits_h_ours", "credits_ours_licence", "credits_credit_line",
                "credits_pin_before", "credits_pin_link", "credits_pin_after", "credits_h_endorse", "credits_endorse", "credits_files_note")
MIN_PYTHON = (3, 12)   # the version the page checks were run under (Linux and macOS); 3.9 refuses the page falsely (Luria 38895)
LIMIT = 1 << 20
# The one string of the page not passed through build_site._e: a module constant, never input. Keep it a constant.
CSS = ("body{font-family:system-ui,sans-serif;line-height:1.5;margin:0 auto;max-width:44rem;padding:1rem}"
       "div.verbatim{font-family:ui-monospace,monospace;font-size:.85rem;white-space:pre-wrap;overflow-wrap:anywhere;border-left:3px solid;padding-left:.75rem}"
       "p.from{margin-bottom:.25rem}")


class Refused(Exception):
    pass


def _head(repo):
    """The HEAD commit of the checkout `repo` (git with safe.directory for this path only, hooks and fsmonitor off)."""
    r = subprocess.run(["git", "-c", "safe.directory=" + os.path.realpath(repo), "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null",
                        "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True,
                       env={k: v for k, v in os.environ.items() if not k.startswith("GIT_")})   # an inherited GIT_DIR would override -C
    return r.stdout.strip() if r.returncode == 0 else None


def read_sources(repo, sources=SOURCES):
    """{name: text} of the files of `sources`, each bounded, contained, strict UTF-8 and of its recorded SHA-256; refusals collected, then raised."""
    out, bad = {}, []
    for name, want in sources.items():
        try:
            data = sk._read_in(repo, os.path.join(repo, name), LIMIT)
        except Exception as e:   # SourceError: missing, symlink, outside, not-a-regular-file, too-large, unreadable
            bad.append(f"CREDITS-SOURCE {name} {e.args[0] if e.args else type(e).__name__}")
            continue
        got = hashlib.sha256(data).hexdigest()
        if got != want:
            bad.append(f"CREDITS-SOURCE {name} sha256 {got[:12]} is not the recorded {want[:12]}")
            continue
        try:
            out[name] = data.decode("utf-8", "strict")
        except UnicodeDecodeError:
            bad.append(f"CREDITS-SOURCE {name} not-utf-8")
    if bad:
        raise Refused(bad)
    return out


def quotes(texts, spec=QUOTES):
    """[(file, [line, ...])] copied by line number; a line number past the end or an empty line is a refusal."""
    out, bad = [], []
    for name, nums in spec:
        lines = texts[name].split("\n")
        got = []
        for n in nums:
            if n < 1 or n > len(lines) or lines[n - 1].strip() == "":
                bad.append(f"CREDITS-QUOTE {name} line {n} missing or empty")
            else:
                got.append(lines[n - 1])
        out.append((name, got))
    if bad:
        raise Refused(bad)
    return out


def check_strings(base, credits):
    """Our words: every CREDITS_KEYS key present, no other key, and build_site's strings rules on the merged file (findings on credits_ keys kept)."""
    bad = [f"CREDITS-STRINGS {k} missing" for k in CREDITS_KEYS if not isinstance(credits.get(k), str) or credits.get(k) == ""]
    bad += [f"CREDITS-STRINGS {k} not read" for k in credits if k not in CREDITS_KEYS]
    bad += [f"CREDITS-STRINGS {k} clashes with the strings file" for k in credits if k in base]
    if bad:
        raise Refused(bad)
    keep = bs.PLACEHOLDERS
    bs.PLACEHOLDERS = dict(keep, **CREDITS_PLACEHOLDERS)
    try:
        found = bs._strings_problems(dict(base, **credits))
    finally:
        bs.PLACEHOLDERS = keep
    bad = [f"CREDITS-STRINGS {path} {msg}" for _code, path, msg in found if str(path).startswith("credits_")]
    if bad:
        raise Refused(bad)


def _fill(s, **kw):
    for k, v in kw.items():
        s = s.replace("{" + k + "}", v)
    return s


def render(texts, q, w, pin=PIN, repo=REPO):
    """The page, as a str. `w` our words; every repository byte and every word of ours goes through build_site._e."""
    e = bs._e
    short = pin[:8]
    base = f"https://github.com/{repo}/blob/{pin}/"
    verbatim = lambda t: f'<div class="verbatim">{e(t)}</div>'
    parts = [
        "<!doctype html>", '<html lang="en">', "<head>", '<meta charset="utf-8">', bs.META_VIEWPORT, bs.META_ROBOTS,
        # style BEFORE title: on Python 3.9 html.parser does not read title as raw text, so build_site's opening run ends at it and a later style
        # is refused as `element style outside head` (Luria 38895); MIN_PYTHON refuses such a Python by name anyway
        f"<style>{CSS}</style>", f"<title>{e(w['credits_title'])}</title>", "</head>", "<body>",
        f'<header><p><a href="../">{e(w["credits_back"])}</a></p><h1>{e(w["credits_title"])}</h1></header>', "<main>",
        # order (Kepler 38897): who made the proof, our map, not an endorsement, then the repository's three files whole
        f'<section class="who"><h2>{e(w["credits_h_who"])}</h2>'
        + "".join(f'<p class="from">{e(_fill(w["credits_from_file"], file=name))}</p>{verbatim(chr(10).join(lines))}' for name, lines in q)
        + "</section>",
        f'<section class="ours"><h2>{e(w["credits_h_ours"])}</h2><p>{e(w["credits_ours_licence"])}</p><p>{e(w["credits_credit_line"])}</p>'
        f'<p>{e(w["credits_pin_before"])}<a class="citation" href="{e(f"https://github.com/{repo}/tree/{pin}")}">'
        f'{e(_fill(w["credits_pin_link"], commit=short, repo=repo))}</a>{e(w["credits_pin_after"])}</p></section>',
        f'<section class="endorse"><h2>{e(w["credits_h_endorse"])}</h2><p>{e(w["credits_endorse"])}</p></section>',
        f'<p class="files-note">{e(w["credits_files_note"])}</p>',
        f'<section class="licence"><h2>{e(w["credits_h_licence"])}</h2>{verbatim(texts["LICENSE"])}</section>',
        f'<section class="notice"><h2>{e(w["credits_h_notice"])}</h2>{verbatim(texts["grh/NOTICE"])}</section>',
        f'<section class="attribution"><h2>{e(w["credits_h_attribution"])}</h2><p>{e(w["credits_attribution_before"])}'
        f'<a class="citation" href="{e(base + "grh/ATTRIBUTION.md")}">grh/ATTRIBUTION.md</a>'
        f'{e(_fill(w["credits_attribution_after"], commit=short, repo=repo))}</p>{verbatim(texts["grh/ATTRIBUTION.md"])}</section>',
        "</main>", "</body>", "</html>", ""]
    return "\n".join(parts)


class _Hrefs(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.found = []

    def handle_starttag(self, tag, attrs):
        self.found += [v for k, v in attrs if k in ("href", "src", "action", "formaction", "xlink:href")]


def href_problems(page, repo=REPO, pin=PIN):
    """Every link target of the page must be `../` or https://github.com/<repo>/(blob|tree)/<pin>... : the page checks of build_site do not judge a
    URL's scheme (Zephyr's read of PR 108: a citation-classed javascript: href passes all four), so this one does, on the page as parsed."""
    p = _Hrefs()
    p.feed(page)
    ok = lambda v: v == "../" or v.startswith(f"https://github.com/{repo}/blob/{pin}/") or v == f"https://github.com/{repo}/tree/{pin}"
    return [f"CREDITS-PAGE href {v!r} is not ../ or the repository at the pin" for v in p.found if not (isinstance(v, str) and ok(v))]


def page_problems(page):
    return href_problems(page) + ([f"CREDITS-PAGE static {p}" for p in bs.static_problems(page, "")] + [f"CREDITS-PAGE element {p}" for p in bs.element_problems(page)]
            + [f"CREDITS-PAGE head {p}" for p in bs.head_meta_problems(page)] + [f"CREDITS-PAGE link {p}" for p in bs.link_problems(page)])


def build(repo, pin, base_strings, credits_strings, sources=SOURCES, head=_head, version=None):
    v = tuple((version or sys.version_info)[:2])
    if v < MIN_PYTHON:
        raise Refused([f"CREDITS-PYTHON {v[0]}.{v[1]} is older than {MIN_PYTHON[0]}.{MIN_PYTHON[1]}: its html.parser reads the page differently, so a page check would be false"])
    if pin != PIN:
        raise Refused([f"CREDITS-PIN {pin} is not the pin this tool records ({PIN})"])
    h = head(repo)
    if h != pin:
        raise Refused([f"CREDITS-PIN checkout HEAD is {h} not {pin}"])
    check_strings(base_strings, credits_strings)
    texts = read_sources(repo, sources)
    page = render(texts, quotes(texts), credits_strings, pin)
    bad = page_problems(page)
    if bad:
        raise Refused(bad)
    return page


def _json(path):
    data = sk._read_bounded(path, LIMIT)
    return json.loads(data.decode("utf-8", "strict"))


def main(argv=None):
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--grh-repo"); ap.add_argument("--pin"); ap.add_argument("--strings"); ap.add_argument("--credits-strings"); ap.add_argument("--out")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not all((a.grh_repo, a.pin, a.strings, a.credits_strings, a.out)):
        ap.print_usage(sys.stderr)
        return 2
    if os.path.lexists(a.out):
        print(f"CREDITS-OUT {a.out} exists")
        return 1
    try:
        page = build(a.grh_repo, a.pin, _json(a.strings), _json(a.credits_strings))
    except Refused as r:
        print("\n".join(r.args[0]))
        return 1
    if os.path.lexists(a.out):
        print(f"CREDITS-OUT {a.out} exists")
        return 1
    with open(a.out, "x", encoding="utf-8", newline="\n") as f:
        f.write(page)
    print(f"credits page written: {a.out} ({len(page.encode())} bytes, {len(SOURCES)} repository files at {a.pin[:8]})")
    return 0


# ---- self-test: fixture repositories in a temporary folder; the real sha table is replaced by the fixture's own.

def selftest():
    fails, n = [], 0
    base = _json(os.path.join(_HERE, os.pardir, "site", "strings.json"))
    words = _json(os.path.join(_HERE, os.pardir, "site", "strings-lean-credits.json"))

    def fixture(tmp, extra=None):
        files = {"LICENSE": "Apache License\n<script>alert(1)</script>\n", "grh/NOTICE": "NOTICE & </div> text\nSee ATTRIBUTION.md.\n",
                 "grh/ATTRIBUTION.md": "| a | b |\n|---|---|\n| `x` | <b>y</b> |\n",
                 "grh/README.md": "# t\n\nR\n\nFixture line five.\nFixture line six.\n\n\n\nFixture line ten.\n",
                 "README.md": "# r\n\n1\n2\n3\n4\n5\n\nFixture line nine.\nFixture line ten.\nFixture line eleven.\n"}
        files.update(extra or {})
        for k, v in files.items():
            p = os.path.join(tmp, k)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(v)
        return {k: hashlib.sha256(v.encode()).hexdigest() for k, v in files.items()}

    def case(cid, fn):
        nonlocal n
        n += 1
        try:
            fn()
            print(f"PASS {cid}")
        except Exception as x:   # an assertion, or anything the case did not expect (a Refused from a build that should pass): a failure, never a crash
            fails.append(cid)
            print(f"FAIL {cid} {type(x).__name__}: {x}")

    def refused(fn, needle):
        try:
            fn()
        except Refused as r:
            assert any(needle in line for line in r.args[0]), f"refused, but not with {needle!r}: {r.args[0]}"
            return
        raise AssertionError(f"not refused (wanted {needle!r})")

    with tempfile.TemporaryDirectory() as tmp:
        sha = fixture(tmp)
        good = lambda: build(tmp, PIN, base, words, sources=sha, head=lambda r: PIN)

        def c1():
            page = good()
            assert page_problems(page) == [], page_problems(page)
            assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page and "<script" not in page, "repository bytes escaped"
            assert "NOTICE &amp; &lt;/div&gt; text" in page
            assert page.count('class="verbatim"') == 5, "LICENSE, NOTICE, ATTRIBUTION, two README blocks"
            assert "Fixture line five.\nFixture line six.\nFixture line ten." in page, "grh/README lines 5, 6, 10"
            assert "Fixture line nine.\nFixture line ten.\nFixture line eleven." in page, "README lines 9-11"
            assert f'href="https://github.com/{REPO}/tree/{PIN}"' in page and f'href="https://github.com/{REPO}/blob/{PIN}/grh/ATTRIBUTION.md"' in page
            assert 'href="../"' in page
            order = [page.index(f'<section class="{c}">') for c in ("who", "ours", "endorse", "licence", "notice", "attribution")]
            assert order == sorted(order), "the order ruled: who made the proof, our map, not an endorsement, then the three files"
            assert page.index('class="files-note"') < page.index('<section class="licence">'), "our note on the files precedes them"
        case("CR1 a fixture builds; the four page checks pass; repository bytes escaped; quotes by line number; links at the pin", c1)
        case("CR2 a pin other than the recorded one is refused", lambda: refused(lambda: build(tmp, "0" * 40, base, words, sources=sha, head=lambda r: "0" * 40), "CREDITS-PIN"))
        case("CR3 a checkout whose HEAD is not the pin is refused", lambda: refused(lambda: build(tmp, PIN, base, words, sources=sha, head=lambda r: "f" * 40), "CREDITS-PIN checkout HEAD"))
        case("CR4 a changed byte in a source file is refused by its sha256", lambda: refused(
            lambda: build(tmp, PIN, base, words, sources=dict(sha, LICENSE="0" * 64), head=lambda r: PIN), "CREDITS-SOURCE LICENSE sha256"))
        case("CR5 a missing words key is refused", lambda: refused(
            lambda: build(tmp, PIN, base, {k: v for k, v in words.items() if k != "credits_endorse"}, sources=sha, head=lambda r: PIN), "CREDITS-STRINGS credits_endorse missing"))
        case("CR6 a words value with 'of the proof' is refused by build_site's R3", lambda: refused(
            lambda: build(tmp, PIN, base, dict(words, credits_endorse="All of the proof."), sources=sha, head=lambda r: PIN), "CREDITS-STRINGS credits_endorse holds a percent sign or `of the proof`"))
        case("CR7 an undeclared placeholder in our words is refused", lambda: refused(
            lambda: build(tmp, PIN, base, dict(words, credits_endorse="Built {when}."), sources=sha, head=lambda r: PIN), "CREDITS-STRINGS credits_endorse has an unknown placeholder {when}"))
        case("CR8 a words key the tool does not read is refused", lambda: refused(
            lambda: build(tmp, PIN, base, dict(words, credits_extra="x"), sources=sha, head=lambda r: PIN), "CREDITS-STRINGS credits_extra not read"))

        def c9():
            os.remove(os.path.join(tmp, "grh/NOTICE"))
            os.symlink(os.path.join(tmp, "LICENSE"), os.path.join(tmp, "grh/NOTICE"))
            try:
                refused(lambda: build(tmp, PIN, base, words, sources=sha, head=lambda r: PIN), "CREDITS-SOURCE grh/NOTICE symlink")
            finally:
                os.remove(os.path.join(tmp, "grh/NOTICE"))
                fixture(tmp)
        case("CR9 a source that is a symlink is refused", c9)

    with tempfile.TemporaryDirectory() as tmp:
        blank = fixture(tmp, {"grh/README.md": "# t\n\nR\n\n\nFixture line six.\n\n\n\nFixture line ten.\n"})
        case("CR16 a quoted line that is empty is refused", lambda: refused(
            lambda: build(tmp, PIN, base, words, sources=blank, head=lambda r: PIN), "CREDITS-QUOTE grh/README.md line 5 missing or empty"))

    with tempfile.TemporaryDirectory() as tmp:
        short = fixture(tmp, {"grh/README.md": "# only\n"})
        case("CR10 a quoted line past the end of its file is refused", lambda: refused(
            lambda: build(tmp, PIN, base, words, sources=short, head=lambda r: PIN), "CREDITS-QUOTE grh/README.md line 5"))

    def c12():
        root = os.path.join(_HERE, os.pardir, "third-party", "grh-lean")
        for ours, theirs in (("LICENSE", "LICENSE"), ("grh/NOTICE", "NOTICE"), ("grh/ATTRIBUTION.md", "ATTRIBUTION.md")):
            with open(os.path.join(root, theirs), "rb") as f:
                assert hashlib.sha256(f.read()).hexdigest() == SOURCES[ours], f"third-party/grh-lean/{theirs} is not the file SOURCES records for {ours}"
    case("CR12 the recorded hashes of LICENSE, NOTICE and ATTRIBUTION.md equal those of the copies in third-party/grh-lean/", c12)

    def c13():
        r = render({"LICENSE": "L", "grh/NOTICE": "N", "grh/ATTRIBUTION.md": "A", "grh/README.md": "", "README.md": ""}, [("f", ["q"])],
                   dict(words, credits_endorse="<b>x</b>"), pin=PIN, repo='a"b<c')
        assert "&lt;b&gt;x&lt;/b&gt;" in r and "<b>" not in r, "our words are escaped"
        assert 'a&quot;b&lt;c' in r and 'a"b<c' not in r, "the repository name is escaped in the hrefs and the link text"
    case("CR13 our words and the repository name in the hrefs are escaped", c13)

    def c14():
        keep = bs.PLACEHOLDERS
        check_strings(base, words)
        assert bs.PLACEHOLDERS is keep, "restored after a pass"
        try:
            check_strings(base, dict(words, credits_endorse="Built {when}."))
        except Refused:
            pass
        assert bs.PLACEHOLDERS is keep, "restored after a refusal"
    case("CR14 build_site's placeholder table is restored after the check, pass or refusal", c14)
    case("CR15 a Python older than MIN_PYTHON is refused by name", lambda: refused(
        lambda: build("/nonexistent", PIN, base, words, version=(3, 9)), "CREDITS-PYTHON 3.9"))

    def c18():
        if (os.environ.get("RH_TMP1_NESTED") == "1" and os.path.basename(tempfile.gettempdir()).startswith("rh-tmp1-")):   # the recursion guard: this run is the child of a CR18
            return
        t = tempfile.mkdtemp(prefix="rh-tmp1-")
        try:
            r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--selftest"], env=dict(os.environ, TMPDIR=t, RH_TMP1_NESTED="1"),
                               capture_output=True, text=True, timeout=300)
            left = sorted(os.listdir(t))
        finally:
            shutil.rmtree(t, ignore_errors=True)
        assert not left and r.returncode == 0, "exit %d, %d left in its TMPDIR: %s" % (r.returncode, len(left), ", ".join(left[:20]))
    case("CR18 the self-test leaves nothing in its temporary folder (a child run under its own fresh TMPDIR; a run whose TMPDIR starts rh-tmp1- runs no CR18)", c18)

    def c11():
        page = render({"LICENSE": "L", "grh/NOTICE": "N", "grh/ATTRIBUTION.md": "A", "grh/README.md": "", "README.md": ""}, [("f", ["q"])], words)
        bad = page.replace('<a class="citation" href="https://github.com', '<a href="https://github.com', 1)
        assert page_problems(page) == [] and any("static href=http" in p for p in page_problems(bad)), "an external link without class citation is caught"
        assert any("element script" in p for p in page_problems(page.replace("</main>", "<script></script></main>"))), "a script is caught"
    case("CR11 controls: the page checks catch an unclassed external link and a script", c11)

    def c17():
        page = render({"LICENSE": "L", "grh/NOTICE": "N", "grh/ATTRIBUTION.md": "A", "grh/README.md": "", "README.md": ""}, [("f", ["q"])], words)
        assert href_problems(page) == [], href_problems(page)
        for bad in ('javascript:alert(1)', 'https://example.org/x', 'https://github.com/lsernau/grh-lean/tree/main', '/x'):
            mut = page.replace('href="../"', f'class="citation" href="{bad}"', 1)
            assert any("CREDITS-PAGE href" in x for x in page_problems(mut)), f"{bad} not caught"
    case("CR17 every link target is ../ or the repository at the pin: a citation-classed javascript:, another site, another ref and a root path are refused", c17)

    print(f"selftest: {n - len(fails)} of {n} passed")
    return 4 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
