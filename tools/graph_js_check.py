#!/usr/bin/env python3
"""Grep gate for the graph view's shipped sources (Borges, 2026-11-25; rules R1-R7 of F65).

Refuses any file under viewer/graph/ that contains one of the tokens that would let a data string become markup,
code or an address. A file under a directory named `test` is not shipped and is not read.

CONTRACT
 G1 Every file under DIR (default: viewer/graph next to this tool's repo), except under a directory named
    `test` or `__pycache__`, is read as UTF-8 (undecodable bytes are replaced, never skipped) and checked.
 G2 In ANY file these are refused: innerHTML, outerHTML, insertAdjacentHTML, document.write, DOMParser,
    createContextualFragment, `eval(`, `new Function`, `http:`, `https:`, and setTimeout / setInterval whose first
    argument is a string literal.
 G3 In a .html file these are also refused: an `on...=` attribute, `<style`, and `style=`.
 G4 Each refusal prints `REFUSED path:line TOKEN`. The run ends with `N files checked, M refused`.
 G5 Exit 0 only if at least one file was checked and none refused. Exit 1 on a refusal, or on `CHECKED NOTHING`
    (no file to read: a gate over nothing must not pass). Exit 2 usage / DIR is not a directory.
 G6 A normal run first runs its own self-test and refuses (exit 4) if it fails. --selftest plants each token
    in a temporary tree and expects its refusal, a clean file to pass, a token under test/ to be ignored, and an
    empty tree to be CHECKED NOTHING.
 LIMIT: substring and line-pattern checks over text. A token split across lines or built from pieces is not seen;
 that is why the engine's own boundary test also forbids the APIs by name in each file. Comments count: a comment
 that names a forbidden token is refused too.

usage: graph_js_check.py [DIR]
       graph_js_check.py --selftest
"""
import os, re, sys, tempfile

ANY = ["innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "DOMParser", "createContextualFragment",
       "eval(", "new Function", "http:", "https:"]
ANY_RE = [("setTimeout/setInterval with a string", re.compile(r"set(?:Timeout|Interval)\s*\(\s*[\"'`]"))]
HTML_RE = [("on...= attribute", re.compile(r"<[^>]*\son[a-z]+\s*=", re.I)),
           ("<style", re.compile(r"<style", re.I)),
           ("style=", re.compile(r"\sstyle\s*=", re.I))]
SKIP_DIRS = {"test", "__pycache__"}


def default_dir():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "viewer", "graph")


def files_under(d):
    for base, dirs, names in os.walk(d):
        dirs[:] = sorted(x for x in dirs if x not in SKIP_DIRS)
        for n in sorted(names):
            yield os.path.join(base, n)


def check_file(path):
    """Return [(line, token)] for every refusal in one file."""
    text = open(path, "rb").read().decode("utf8", errors="replace")
    hits = []
    for i, line in enumerate(text.split("\n"), 1):
        for t in ANY:
            if t in line:
                hits.append((i, t))
        for name, rx in ANY_RE:
            if rx.search(line):
                hits.append((i, name))
        if path.endswith(".html"):
            for name, rx in HTML_RE:
                if rx.search(line):
                    hits.append((i, name))
    return hits


def run(d, out):
    n = refused = 0
    for p in files_under(d):
        n += 1
        for line, tok in check_file(p):
            refused += 1
            print("REFUSED %s:%d %s" % (os.path.relpath(p, d), line, tok), file=out)
    if n == 0:
        print("CHECKED NOTHING: no file under " + d, file=out)
        return 1
    print("%d files checked, %d refused" % (n, refused), file=out)
    return 1 if refused else 0


# literals, written here and never read back from the tool: (file name, planted text, token the refusal must name)
PLANTS = [
    ("a.js", "x.innerHTML = s;", "innerHTML"),
    ("a.js", "x.outerHTML = s;", "outerHTML"),
    ("a.js", "x.insertAdjacentHTML('beforeend', s);", "insertAdjacentHTML"),
    ("a.js", "document.write(s);", "document.write"),
    ("a.js", "new DOMParser();", "DOMParser"),
    ("a.js", "r.createContextualFragment(s);", "createContextualFragment"),
    ("a.js", "eval(s);", "eval("),
    ("a.js", "const f = new Function('return 1');", "new Function"),
    ("a.js", "const u = 'http://example.org/';", "http:"),
    ("a.js", "const u = 'https://example.org/';", "https:"),
    ("a.js", "setTimeout('go()', 10);", "setTimeout/setInterval with a string"),
    ("a.js", "setInterval(\"go()\", 10);", "setTimeout/setInterval with a string"),
    ("a.css", "a { background: url(http://example.org/x.png); }", "http:"),
    ("p.html", "<button onclick=\"go()\">x</button>", "on...= attribute"),
    ("p.html", "<div onmouseover = \"go()\">x</div>", "on...= attribute"),
    ("p.html", "<style>a{}</style>", "<style"),
    ("p.html", "<div style=\"color:red\">x</div>", "style="),
    ("sub/deep/b.js", "x.innerHTML = s;", "innerHTML"),
]
CLEAN = [
    ("ok.js", "el.style.transform = 'none'; setTimeout(() => go(), 10); const s = el.textContent;"),
    ("ok.html", "<!doctype html><script type=\"module\" src=\"app.js\"></script><link rel=\"stylesheet\" href=\"a.css\"><p class=\"x\">done</p>"),
    ("ok.css", ".a { color: red; }"),
    ("a.js", "x.style='nothing here'; // style= in a .js is not a refusal"),
]


def selftest():
    import io
    ok, notes = True, []
    for name, text, token in PLANTS:
        d = tempfile.mkdtemp()
        p = os.path.join(d, name)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(text + "\n")
        buf = io.StringIO()
        rc = run(d, buf)
        good = rc == 1 and ("REFUSED " + name + ":1 " + token) in buf.getvalue()
        if not good:
            ok = False
            notes.append("not refused: %s in %s -> rc %d %r" % (token, name, rc, buf.getvalue()))
    d = tempfile.mkdtemp()
    for name, text in CLEAN:
        open(os.path.join(d, name), "w").write(text + "\n")
    buf = io.StringIO()
    rc = run(d, buf)
    if rc != 0 or "4 files checked, 0 refused" not in buf.getvalue():
        ok = False
        notes.append("clean files were refused or miscounted: " + buf.getvalue())
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "engine", "test"))
    open(os.path.join(d, "engine", "test", "t.js"), "w").write("x.innerHTML = 1; fetch('http://x')\n")
    open(os.path.join(d, "engine", "i.js"), "w").write("export const a = 1;\n")
    buf = io.StringIO()
    if run(d, buf) != 0 or "1 files checked, 0 refused" not in buf.getvalue():
        ok = False
        notes.append("a token under test/ was read: " + buf.getvalue())
    d = tempfile.mkdtemp()
    buf = io.StringIO()
    if run(d, buf) != 1 or "CHECKED NOTHING" not in buf.getvalue():
        ok = False
        notes.append("an empty tree was not CHECKED NOTHING")
    for n in notes:
        print(n)
    print("SELFTEST " + ("PASS: %d planted tokens each refused, clean files pass, test/ is not read, an empty tree is CHECKED NOTHING" % len(PLANTS) if ok else "FAIL"))
    return 0 if ok else 4


def selftest_quiet():
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        return selftest()


def main(a):
    if a[1:] == ["--selftest"]:
        return selftest()
    if len(a) > 2 or (len(a) == 2 and a[1].startswith("-")):
        print(__doc__.split("usage:")[1].strip(), file=sys.stderr)
        return 2
    d = a[1] if len(a) == 2 else default_dir()
    if not os.path.isdir(d):
        print("not a directory: " + d, file=sys.stderr)
        return 2
    if selftest_quiet() != 0:
        print("REFUSED: selftest failed; no result reported", file=sys.stderr)
        return 4
    return run(d, sys.stdout)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
