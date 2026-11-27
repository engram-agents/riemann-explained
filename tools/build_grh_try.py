#!/usr/bin/env python3
"""The "What to try" page of the Lean map: ONE static file, try/index.html, in our words only.

usage: build_grh_try.py --strings site/strings.json --try-strings site/strings-lean-try.json --out FILE
       build_grh_try.py --selftest

(RED STATE: the implementation is a stub; the self-test below states the contract.)
"""
import argparse
import contextlib
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

_HERE = os.path.dirname(os.path.abspath(__file__))


def _load(name):
    key = "_try_" + name
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

MIN_PYTHON = (3, 12)
LIMIT = 1 << 20
TRY_KEYS = ()
TRY_TARGETS = ()
CSS = ""


class Refused(Exception):
    pass


def target_problems(targets):
    raise NotImplementedError("target_problems")


def check_strings(base, words):
    raise NotImplementedError("check_strings")


def render(words, targets=None):
    raise NotImplementedError("render")


def href_problems(page, targets=None):
    raise NotImplementedError("href_problems")


def page_problems(page, targets=None):
    raise NotImplementedError("page_problems")


def build(base, words, targets=None, version=None):
    raise NotImplementedError("build")


def _json(path):
    data = sk._read_bounded(path, LIMIT)
    return json.loads(data.decode("utf-8", "strict"))


def main(argv=None):
    if "--selftest" in (sys.argv[1:] if argv is None else argv):
        return selftest()
    raise NotImplementedError("main")


# ---- self-test

NOTE_PATH = "/home/agents-shared/ariadne/rh-viewer/what-to-try-design-v2.md"   # Ariadne's words; read when present
WANT_KEYS = (["try_title", "try_intro"] + [f"try_{i}_{p}" for i in range(1, 6) for p in ("head", "text", "link")] + ["try_ask_heading"]
             + [f"try_ask_{i}" for i in range(1, 5)] + ["try_tell_heading", "try_tell_text", "try_keep_heading"] + [f"try_keep_{i}" for i in range(1, 4)])
WANT_TARGETS = ("", "lean-reduction-from-a-one-sided-bound-to-the-zeros", "lean-reduction-zeros-criterion-new-lfunction-ne-zero-of-p-301c28",
                "lean-reduction-zeros-prime-number-theorem-new-eventually-999988", "lean-reduction-zeros-prime-error-new-integral-primeremainder")
ID_SHAPE = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")   # the test's own copy of the shape, so a change of the tool's is seen


class _Outline(html.parser.HTMLParser):
    """The text of the page as (innermost tag, text) in document order, and every <a href>."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack, self.seq, self.hrefs = [], [], []

    def handle_starttag(self, tag, attrs):
        if tag not in ("meta", "link", "br", "img", "hr", "input"):
            self.stack.append(tag)
        if tag == "a":
            self.hrefs.append(dict(attrs).get("href"))

    def handle_endtag(self, tag):
        while self.stack and self.stack[-1] != tag:
            self.stack.pop()
        if self.stack:
            self.stack.pop()

    def handle_data(self, data):
        if data.strip() and self.stack and self.stack[-1] in ("title", "h1", "h2", "p", "a", "li"):
            self.seq.append((self.stack[-1], data))


class _Everything(html.parser.HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags, self.attrs = [], []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        self.attrs += [(tag, k, v) for k, v in attrs]


def _outline(page):
    p = _Outline()
    p.feed(page)
    return p


def _expected(w):
    seq = [("title", w["try_title"]), ("h1", w["try_title"]), ("p", w["try_intro"])]
    for i in range(1, 6):
        seq += [("h2", w[f"try_{i}_head"]), ("p", w[f"try_{i}_text"]), ("a", w[f"try_{i}_link"])]
    seq += [("h2", w["try_ask_heading"])] + [("li", w[f"try_ask_{i}"]) for i in range(1, 5)]
    seq += [("h2", w["try_tell_heading"]), ("p", w["try_tell_text"]), ("h2", w["try_keep_heading"])] + [("li", w[f"try_keep_{i}"]) for i in range(1, 4)]
    return seq


def selftest():
    fails, n = [], 0
    shipped = os.path.join(_HERE, os.pardir, "site", "strings-lean-try.json")
    base = _json(os.path.join(_HERE, os.pardir, "site", "strings.json"))
    words = _json(shipped)
    strings_path = os.path.join(_HERE, os.pardir, "site", "strings.json")

    def case(cid, fn):
        nonlocal n
        n += 1
        try:
            fn()
            print(f"PASS {cid}")
        except Exception as x:   # an assertion, or anything the case did not expect: a failure, never a crash
            fails.append(cid)
            print(f"FAIL {cid} {type(x).__name__}: {x}")

    def refused(fn, needle):
        try:
            fn()
        except Refused as r:
            assert any(needle in line for line in r.args[0]), f"refused, but not with {needle!r}: {r.args[0]}"
            return
        raise AssertionError(f"not refused (wanted {needle!r})")

    def run(args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                code = main(args)
            except SystemExit as x:
                code = x.code
        return code, out.getvalue(), err.getvalue()

    good = lambda: build(base, words)

    def ok1():
        page = good()
        assert page_problems(page) == [], page_problems(page)
        assert good() == page, "same inputs, same page"
        b = page.encode("utf-8")
        assert b.endswith(b"\n") and not b.endswith(b"\n\n") and b"\r" not in b, "LF, one final newline"
    case("TRY-OK-1 the shipped strings build a page that passes the checks; twice the same; LF, UTF-8, one final newline", ok1)

    def ok2():
        o = _outline(good())
        assert o.seq == _expected(words), "the page's text, in order, is the words in the fixed structure"
        assert o.hrefs == ["../"] + [f"../#{t}" for t in WANT_TARGETS[1:]], o.hrefs
    case("TRY-OK-2 the page holds the five items in order, each with its own link words and its address, then the four questions, the tell paragraph, the three keep lines", ok2)

    def ok3():
        w = {k: "Words for " + k.replace("_", " ") for k in WANT_KEYS}   # every value distinct, so a value taken from the wrong key shows
        o = _outline(build(base, w))
        assert o.seq == _expected(w), "every value stands at its own place"
    case("TRY-OK-3 with every value distinct, each stands at its own place (no value is taken from another key)", ok3)

    base_missing = lambda k: {a: b for a, b in words.items() if a != k}
    case("TRY-LAYOUT-1 a missing key is refused by name", lambda: refused(lambda: build(base, base_missing("try_3_link")), "TRY-LAYOUT try_3_link missing"))
    case("TRY-LAYOUT-2 an unknown key is refused by name", lambda: refused(lambda: build(base, dict(words, try_extra="x")), "TRY-LAYOUT try_extra unknown"))
    case("TRY-LAYOUT-3 a value that is not a string is refused by name", lambda: refused(lambda: build(base, dict(words, try_ask_2=7)), "TRY-LAYOUT try_ask_2 not-a-string"))
    case("TRY-LAYOUT-4 an empty value is refused by name", lambda: refused(lambda: build(base, dict(words, try_keep_3="")), "TRY-LAYOUT try_keep_3 empty"))
    case("TRY-LAYOUT-5 a file that is not an object is refused", lambda: refused(lambda: build(base, ["x"]), "TRY-LAYOUT (top level)"))

    forbidden = base["forbidden_words"][0]
    case("TRY-STR-1 a forbidden word in a value is refused", lambda: refused(
        lambda: build(base, dict(words, try_intro=f"This is {forbidden} so.")), "TRY-STRINGS try_intro"))
    case("TRY-STR-2 a percent sign in a value is refused", lambda: refused(
        lambda: build(base, dict(words, try_keep_1="Half of it, 50% done.")), "TRY-STRINGS try_keep_1"))
    case("TRY-STR-3 a placeholder in a value is refused", lambda: refused(
        lambda: build(base, dict(words, try_tell_text="Tell {who}.")), "TRY-STRINGS try_tell_text"))

    def esc():
        raw, shown = '<b>&"\'x', "&lt;b&gt;&amp;&quot;&#x27;x"
        for k in WANT_KEYS:
            page = build(base, dict(words, **{k: raw + k}))
            want = 2 if k == "try_title" else 1   # the title is the title element and the h1
            assert page.count(shown + k) == want, f"{k}: the escaped text stands {page.count(shown + k)} times, wanted {want}"
            assert raw + k not in page and "<b>" not in page, f"{k}: raw text reached the page"
    case("TRY-ESC-1 a value with <, & and quotes is escaped wherever it stands; no value of the 28 reaches the page raw", esc)

    def static1():
        page = good()
        p = _Everything()
        p.feed(page)
        assert not {"script", "form", "link", "img", "iframe", "input", "button", "object", "embed", "svg", "video", "audio", "base"} & set(p.tags), set(p.tags)
        assert {k for _t, k, _v in p.attrs} <= {"charset", "name", "content", "lang", "class", "href"}, p.attrs
        allowed = {"../"} | {f"../#{t}" for t in WANT_TARGETS[1:]}
        assert all(v in allowed for t, k, v in p.attrs if k == "href"), p.attrs
        low = page.lower()
        for bad in ("http", "mailto", "url(", "@import", "javascript:", "<script", "<form"):
            assert bad not in low, bad
    case("TRY-STATIC-1 the written page, parsed: no script, form or external resource; no http, mailto or url(; every href is ../ or ../#id of the constant ids", static1)

    def static2():
        page = good()
        for bad in ("javascript:alert(1)", "https://example.org/", "mailto:a@b.c", "../credits/", "../#", "../#unknown-id", "../#" + WANT_TARGETS[1] + "x",
                    "/x", "//example.org/", "../index.html", "", " ../ ", "..\\#x"):
            mut = page.replace('href="../"', f'href="{bad}"', 1)
            assert mut != page and href_problems(mut) and any(x.startswith("TRY-PAGE") for x in page_problems(mut)), f"{bad!r} not caught"
    case("TRY-STATIC-2 controls: every other address (script, other site, mailto, the credits, a bare # or an unknown id, a root or empty one) is refused", static2)

    def targets1():
        t = TRY_TARGETS
        assert tuple(t) == WANT_TARGETS, "the table is the ruled one"
        assert len(t) == 5 and t[0] == "" and all(ID_SHAPE.fullmatch(x) and len(x) <= 64 for x in t[1:])
    case("TRY-TARGETS-1 the constant table holds five entries: the map, then four ids of the right shape, the ruled ones", targets1)

    def targets2():
        for bad in (WANT_TARGETS[:4], WANT_TARGETS + ("x",), ("",) + ("Upper",) + WANT_TARGETS[2:], ("", "a_b") + WANT_TARGETS[2:],
                    ("", "a--b") + WANT_TARGETS[2:], ("", "-a") + WANT_TARGETS[2:], ("", "a-") + WANT_TARGETS[2:], ("", "a b") + WANT_TARGETS[2:],
                    ("", "../x") + WANT_TARGETS[2:], ("", "a" * 65) + WANT_TARGETS[2:], ("", None) + WANT_TARGETS[2:], ("", 5) + WANT_TARGETS[2:]):
            refused(lambda: build(base, words, targets=bad), "TRY-TARGETS")
        assert target_problems(("",) + ("a" * 64,) + WANT_TARGETS[2:]) == [], "64 characters is allowed"
        build(base, words, targets=("", "a" * 64) + WANT_TARGETS[2:])
    case("TRY-TARGETS-2 a table of the wrong size or with an id of the wrong shape or length is refused; 64 characters is allowed", targets2)

    def doc():
        page = good()
        assert page_problems(page) == []
        assert any("element script" in p for p in page_problems(page.replace("</main>", "<script></script></main>"))), "element check"
        assert any("static" in p for p in page_problems(page.replace("</main>", '<img src="http://x/y.png"></main>'))), "static check"
        assert any("head" in p and "viewport" in p for p in page_problems(page.replace(bs.META_VIEWPORT, ""))), "head check"
        assert any("link" in p and "#nope" in p for p in page_problems(page.replace("</main>", '<a href="#nope">x</a></main>'))), "link check"
    case("TRY-DOC the four checks of build_site run on the page: a script, an external image, a missing viewport and a dead # link are each found", doc)

    def wordsfile():
        assert list(words) == WANT_KEYS, "exactly the 28 keys, in the design's order"
        assert tuple(TRY_KEYS) == tuple(WANT_KEYS), "the tool reads exactly those keys"
        if not os.path.isfile(NOTE_PATH):
            print(f"     (note not readable at {NOTE_PATH}: the comparison with it is skipped)")
            return
        with open(NOTE_PATH, encoding="utf-8") as f:
            lines = f.read().split("\n")
        a = next(i for i, l in enumerate(lines) if l.startswith("## Words"))
        b = next(i for i in range(a + 1, len(lines)) if lines[i].startswith("## "))
        note = {}
        for l in lines[a + 1:b]:
            m = re.match(r"^- (try_[a-z0-9_]+): `(.*?)`(?:\s.*)?$", l)
            if m:
                note[m.group(1)] = m.group(2)
        assert note == words, "the shipped file equals the values of the note: " + ", ".join(k for k in WANT_KEYS if note.get(k) != words.get(k))
    case("TRY-WORDS the shipped strings file has exactly the 28 keys and equals Ariadne's note when the note is readable", wordsfile)

    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "o.html")
        opts = {"--strings": strings_path, "--try-strings": shipped, "--out": out}
        argv = lambda drop=None, extra=(): [x for k, v in opts.items() if k != drop for x in (k, v)] + list(extra)

        def usage1():
            for k in opts:
                code, _o, _e = run(argv(drop=k))
                assert code == 2, f"without {k}: exit {code}"
            assert run([])[0] == 2
            assert not os.path.lexists(out)
        case("TRY-USAGE-1 a missing option is exit 2 and writes nothing", usage1)

        def usage2():
            assert run(argv(extra=["--bogus", "x"]))[0] == 2, "unknown option"
            assert run(argv(extra=["stray"]))[0] == 2, "stray argument"
            assert run(["--strings", strings_path, "--try", shipped, "--out", out])[0] == 2, "an abbreviation is not an option"
            assert not os.path.lexists(out)
        case("TRY-USAGE-2 an unknown option, a stray argument and an abbreviated option are exit 2", usage2)

        def usage3():
            for k in opts:
                code, _o, _e = run(argv(extra=[k, opts[k]]))
                assert code == 2, f"{k} twice: exit {code}"
            assert not os.path.lexists(out)
        case("TRY-USAGE-3 an option given twice is exit 2 and writes nothing", usage3)

        def mainok():
            code, o, _e = run(argv())
            assert code == 0, (code, o)
            assert sorted(os.listdir(tmp)) == ["o.html"], "one file"
            with open(out, "rb") as f:
                got = f.read()
            assert got == good().encode("utf-8"), "the file is the page"
            assert o.startswith("try page written: ") and o.count("\n") == 1, o
            os.remove(out)
        case("TRY-MAIN-OK a run writes ONE file holding the page, exit 0, one report line", mainok)

        def nothing1():
            bad = os.path.join(tmp, "bad.json")
            with open(bad, "w", encoding="utf-8") as f:
                json.dump(base_missing("try_2_head"), f)
            code, o, _e = run(["--strings", strings_path, "--try-strings", bad, "--out", out])
            assert code == 1 and o.startswith("TRY-LAYOUT try_2_head missing"), (code, o)
            assert not os.path.lexists(out) and sorted(os.listdir(tmp)) == ["bad.json"], "nothing written"
            os.remove(bad)
        case("TRY-NOTHING-1 a refusal of the words prints its TRY- line, exit 1, and the output path stays absent", nothing1)

        def nothing2():
            global TRY_TARGETS
            keep = TRY_TARGETS
            TRY_TARGETS = ("", "Bad Id") + tuple(keep[2:])
            try:
                code, o, _e = run(argv())
            finally:
                TRY_TARGETS = keep
            assert code == 1 and o.startswith("TRY-TARGETS"), (code, o)
            assert not os.path.lexists(out), "nothing written after the page check refused"
        case("TRY-NOTHING-2 a refusal that comes after the page is rendered also leaves the output path absent", nothing2)

        def exists():
            with open(out, "w", encoding="utf-8") as f:
                f.write("mine\n")
            code, o, _e = run(argv())
            with open(out, encoding="utf-8") as f:
                kept = f.read()
            os.remove(out)
            assert code == 1 and o.startswith("TRY-OUT ") and kept == "mine\n", (code, o, kept)
        case("TRY-OUT-EXISTS an output path that exists is refused (TRY-OUT) and left as it was", exists)

        def readfail():
            gone = os.path.join(tmp, "gone.json")
            code, o, _e = run(["--strings", strings_path, "--try-strings", gone, "--out", out])
            assert code == 1 and o.startswith("TRY-READ "), (code, o)
            junk = os.path.join(tmp, "junk.json")
            with open(junk, "w", encoding="utf-8") as f:
                f.write("{not json")
            code, o, _e = run(["--strings", strings_path, "--try-strings", junk, "--out", out])
            os.remove(junk)
            assert code == 1 and o.startswith("TRY-READ ") and not os.path.lexists(out), (code, o)
        case("TRY-READ an unreadable or invalid words file is refused (TRY-READ), exit 1, nothing written", readfail)

    case("TRY-PYTHON a Python older than MIN_PYTHON is refused by name", lambda: refused(lambda: build(base, words, version=(3, 9)), "TRY-PYTHON 3.9"))

    def leak():
        if (os.environ.get("RH_TMP1_NESTED") == "1" and os.path.basename(tempfile.gettempdir()).startswith("rh-tmp1-")):   # the recursion guard: this run is the child of a LEAK case
            return
        t = tempfile.mkdtemp(prefix="rh-tmp1-")
        try:
            r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--selftest"], env=dict(os.environ, TMPDIR=t, RH_TMP1_NESTED="1"),
                               capture_output=True, text=True, timeout=300)
            left = sorted(os.listdir(t))
        finally:
            shutil.rmtree(t, ignore_errors=True)
        assert not left and r.returncode == 0, "exit %d, %d left in its TMPDIR: %s" % (r.returncode, len(left), ", ".join(left[:20]))
    case("TRY-LEAK the self-test leaves nothing in its temporary folder (a child run under its own fresh TMPDIR; a run whose TMPDIR starts rh-tmp1- runs no LEAK case)", leak)

    print(f"selftest: {n - len(fails)} of {n} passed")
    return 4 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
