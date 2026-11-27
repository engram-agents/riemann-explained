#!/usr/bin/env python3
"""Cases of smoke_tree.py, the one-command acceptance test of a BUILT site tree. Each case builds a tree with assemble.assemble() into a
temp dir (never anything else), runs the tool as a subprocess and reads its exit code and its lines.

Run:  python3 viewer/graph/page/test/test_smoke_tree.py [--only TEXT] [--no-browser]   (a Python with playwright; --no-browser runs only the
      cases that need none, so any Python 3 runs them: the containment cases must pass on every Python the team uses)

Contract under test (the spec's S1..S5 and the amendments A1..A3):
  exit 0 only if every check passed; 1 if any FAILED; 2 if the folder is neither tree shape. Lines are
  `PASS|FAIL|SKIP <viewport> <check> <detail>`, `TREE flat|graph/`, three `ID <what> <id> (<rule>)` lines, and a last line
  `SMOKE PASS` (naming any skip and a partial run) or `SMOKE FAIL (<n> failed)`.
Never shipped (lives under test/).
"""
import contextlib, glob, json, os, re, shutil, subprocess, sys, tempfile, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import assemble  # noqa: E402

TOOL = os.path.join(HERE, "smoke_tree.py")


class Skip(Exception):
    """Raised by a case that could not run on this base: the runner reports it as SKIP and counts it apart, never as a pass."""


def run_tool(site, *args):
    p = subprocess.run([sys.executable, TOOL, site, *args], capture_output=True, text=True, timeout=240)
    return p.returncode, p.stdout + p.stderr


def build(tmp, name="t", **kw):
    out = os.path.join(tmp, name)
    assemble.assemble(out, **kw)
    return out


def flatten(out):
    """The Lean map assembler's shape: the contents of graph/ moved up one level, index.html beside index.json."""
    g = os.path.join(out, "graph")
    for n in os.listdir(g):
        shutil.move(os.path.join(g, n), os.path.join(out, n))
    os.rmdir(g)
    return out


def lines(text, kind, check=None):
    return [l for l in text.splitlines() if l.startswith(kind + " ") and (check is None or (" " + check + " ") in (l + " "))]


def last(text):
    return text.strip().splitlines()[-1]


def edit_json(path, fn):
    d = json.load(open(path, encoding="utf-8"))
    fn(d)
    json.dump(d, open(path, "w", encoding="utf-8"), sort_keys=True, indent=1, ensure_ascii=False)


def sub_once(old, new):
    """A mutation of shipped source text that refuses to apply silently: a changed base makes the case fail loudly instead of pass vacuously."""
    def f(src):
        assert old in src, "mutation anchor not found (the page changed; rewrite this case): " + old[:60]
        return src.replace(old, new, 1)
    return f


# A page whose open sheet offers no parts button (the sheet's `canParts` block is never reached), and a page whose open-parts route opens nothing.
NO_PARTS_BUTTON = sub_once("    if (info.canParts) {", "    if (false && info.canParts) {")
PARTS_NEVER_OPEN = sub_once("if (m && await viaRoute(t, path, () => handle.open(id))) {", "if (false && m && await viaRoute(t, path, () => handle.open(id))) {")
# A page whose sheet draws no note (the note section is never built), whatever the data carries.
NO_NOTE_BODY = sub_once("    if (info.note) {\n      const n = info.note, t", "    if (false && info.note) {\n      const n = info.note, t")


def t1_real_fixture(tmp):
    out = build(tmp)
    code, o = run_tool(out, "--no-note")
    assert code == 0, (code, o)
    assert last(o).startswith("SMOKE PASS"), o
    assert len(lines(o, "ID")) == 3, o
    assert "TREE graph/" in o, o
    for chk in ("boot", "console", "requests", "csp-header", "open-part", "open-group", "open-file"):
        assert lines(o, "PASS", chk), (chk, o)
    assert lines(o, "PASS", "boot")[0].split()[1] in ("390x844", "1280x900"), o
    assert {l.split()[1] for l in lines(o, "PASS", "boot")} == {"390x844", "1280x900"}, o


def t1b_flat_shape(tmp):
    out = flatten(build(tmp))
    assert os.path.isfile(os.path.join(out, "index.html")) and not os.path.isdir(os.path.join(out, "graph"))
    code, o = run_tool(out, "--no-note")
    assert code == 0 and last(o).startswith("SMOKE PASS") and "TREE flat" in o, (code, o)


def t1c_neither_shape(tmp):
    d = os.path.join(tmp, "empty")
    os.makedirs(os.path.join(d, "step"))
    open(os.path.join(d, "index.json"), "w").write("{}")      # an index but no index.html: neither shape
    code, o = run_tool(d)
    assert code == 2, (code, o)
    assert "SMOKE PASS" not in o, o


def t2_extra_string(tmp):
    out = build(tmp, index_edit=lambda i: i["strings"].update({"extra-string": "x"}))
    code, o = run_tool(out, "--no-note")
    assert code == 1, (code, o)
    assert lines(o, "FAIL", "boot"), o
    assert "extra-string" in o, o
    assert re.fullmatch(r"SMOKE FAIL \(\d+ failed\)", last(o)), o


def t3_deleted_step(tmp):
    out = build(tmp)
    os.remove(os.path.join(out, "graph", "step", "a1.json"))        # the group the S3 path opens (first child of the part)
    code, o = run_tool(out, "--no-note")
    assert code == 1, (code, o)
    assert [l for l in lines(o, "FAIL") if "a1" in l], o


def t4_symlink_out_of_tree(tmp):
    out = build(tmp)
    outside = os.path.join(tmp, "outside-app.js")
    shutil.copyfile(os.path.join(out, "graph", "page", "app.js"), outside)
    p = os.path.join(out, "graph", "page", "app.js")
    os.remove(p)
    os.symlink(outside, p)
    got, outs = sweep(out, ["/graph/page/app.js"])
    assert got[("GET", "/graph/page/app.js")][0] == 403 and got[("HEAD", "/graph/page/app.js")][0] == 403 and outs, (got, outs)
    no_leak(got, ["/graph/page/app.js"])


def t4c_symlink_out_of_tree_end_to_end(tmp):
    """T4's tree through the whole tool (a browser run): FAIL containment, exit 1."""
    out = build(tmp)
    outside = os.path.join(tmp, "outside-app.js")
    shutil.copyfile(os.path.join(out, "graph", "page", "app.js"), outside)
    p = os.path.join(out, "graph", "page", "app.js")
    os.remove(p)
    os.symlink(outside, p)
    code, o = run_tool(out, "--no-note")
    assert code == 1, (code, o)
    assert lines(o, "FAIL", "containment"), o


def t4b_symlink_read_by_tool(tmp):
    """The tool's own reads of step files stay inside SITE_DIR too."""
    out = build(tmp)
    outside = os.path.join(tmp, "outside-step.json")
    p = os.path.join(out, "graph", "step", "a1-b.json")
    shutil.copyfile(p, outside)
    os.remove(p)
    os.symlink(outside, p)
    code, o = run_tool(out, "--no-note")
    assert code == 1, (code, o)
    assert lines(o, "FAIL", "containment"), o


def t5_note_fixture_or_skip(tmp):
    have = [f for f in glob.glob(os.path.join(HERE, "fixtures", "*", "step", "*.json")) if '"note"' in open(f, encoding="utf-8").read()]
    if not have:
        raise Skip("no committed fixture on this base carries a note (PR 97 adds them); the positive note PASS is not exercised")
    names = sorted({f.split(os.sep)[-3] for f in have})
    out = build(tmp, fix=names[0])
    code, o = run_tool(out)
    assert code == 0 and lines(o, "PASS", "note"), (code, o)


def t5b_no_notes_in_data_is_a_skip(tmp):
    out = build(tmp, fix="skeleton")
    code, o = run_tool(out)
    assert code == 0, (code, o)
    assert [l for l in lines(o, "SKIP", "note") if "no file step carries a note" in l], o
    assert not lines(o, "PASS", "note"), o


def t5c_missing_note_section_fails(tmp):
    """The data carries notes (the `notes` fixture: a file step has a note) and a COPY of the page draws no note on its sheet (the line that builds
    the `.note-body` is never reached): FAIL note, never a pass (A2). The same data on the real page passes the note check (the positive half)."""
    out = build(tmp, fix="notes", mutate={"page/sheet.js": NO_NOTE_BODY})
    code, o = run_tool(out, "--only-viewport", "1280x900")
    assert code == 1, (code, o)
    assert [l for l in lines(o, "FAIL", "note") if "no .note-body" in l], o
    assert lines(o, "PASS", "boot"), o         # the page booted: this is the note check alone
    good = build(tmp, name="notes-real", fix="notes")
    code, o = run_tool(good, "--only-viewport", "1280x900")
    assert lines(o, "PASS", "note") and not lines(o, "FAIL", "note"), (code, o)


def t6_console_error_alone_fails_s2(tmp):
    """K1's discriminating case: the page boots and opens everything, but logs a console error. Only the console check can see it."""
    out = build(tmp, mutate={"page/app.js": lambda s: s + "\nconsole.error('smoke-test noise');\n"})
    code, o = run_tool(out, "--no-note")
    assert code == 1, (code, o)
    assert lines(o, "FAIL", "console"), o
    assert lines(o, "PASS", "boot"), o


def t7_second_fixture_different_ids(tmp):
    """K2's case: ids come from the data. The skeleton has a part, a group and a file that the real fixture has not."""
    out = build(tmp, fix="skeleton")
    code, o = run_tool(out, "--no-note")
    assert code == 0 and last(o).startswith("SMOKE PASS"), (code, o)
    ids = {l.split()[1]: l.split()[2] for l in lines(o, "ID")}
    assert ids["part"] == "sk-part" and ids["group"] == "sk-group-a" and ids["file"] == "sk-file-1", ids
    real = build(tmp, name="real")
    _, o2 = run_tool(real, "--no-note")
    assert {l.split()[2] for l in lines(o2, "ID")}.isdisjoint(ids.values()), o2


def t8_csp_header_is_checked(tmp):
    """K3's case: the tool's server sends the suite's Content-Security-Policy and says so. Pins that the header is sent and reported."""
    out = build(tmp)
    code, o = run_tool(out, "--no-note", "--only-viewport", "1280x900")
    assert lines(o, "PASS", "csp-header"), o
    assert "default-src 'none'" in "".join(lines(o, "PASS", "csp-header")), o


def t9b_base_refuses_unknown_index_key(tmp):
    """A tree whose index carries a key no page file reads (`no_such_index_key`) is refused at boot, and the tool fails it (the ruling: correct behaviour)."""
    out = build(tmp, index_edit=lambda i: i.update({"no_such_index_key": 1}))
    code, o = run_tool(out, "--no-note")
    assert code == 1 and lines(o, "FAIL", "boot"), (code, o)


def t10_only_viewport(tmp):
    out = build(tmp)
    code, o = run_tool(out, "--no-note", "--only-viewport", "390x844")
    assert code == 0, (code, o)
    assert not [l for l in o.splitlines() if "1280x900" in l.split(" ")[:2]], o
    assert lines(o, "PASS", "boot"), o


def t11_empty_heading_fails(tmp):
    """P1: a card title that is empty after plain() (a single backtick) must FAIL the heading check, not pass as '' == ''."""
    def blank(x):        # every place the page can take the part's and the group's title from: card, children list, path
        if isinstance(x, dict):
            return {k: blank(v) for k, v in x.items()}
        if isinstance(x, list):
            return [blank(v) for v in x]
        return "`" if x in ("Title of step goal-chain", "Title of step a1") else x
    def step_edit(steps):
        for i in list(steps):
            steps[i] = blank(steps[i])
    out = build(tmp, step_edit=step_edit)
    code, o = run_tool(out, "--no-note")
    assert code == 1, (code, o)
    assert [l for l in lines(o, "FAIL", "open-part") if "empty" in l], o
    assert [l for l in lines(o, "FAIL", "open-group") if "empty" in l], o
    assert not [l for l in lines(o, "PASS", "open-part") + lines(o, "PASS", "open-group")], o
    assert lines(o, "PASS", "open-file"), o        # the file's title was left alone: the failure is the empty headings alone


def t12_skips_named_in_last_line(tmp):
    """P2: a SKIP is named in the verdict line; a tree with no notes and no credits/ skips both, and the framed check (which runs here) is not among them."""
    def no_notes(steps):
        for st in steps.values():
            st.pop("note", None)
    out = build(tmp, fix="skeleton", step_edit=no_notes)       # each skip's condition is built here, not read off the fixture
    code, o = run_tool(out)
    assert code == 0, (code, o)
    assert lines(o, "SKIP", "note") and not lines(o, "SKIP", "framed") and lines(o, "PASS", "framed"), o
    assert last(o) == "SMOKE PASS (2 skipped: credits, note)", o        # the skeleton tree has no credits/ either


def t12b_verdict_line_unit(tmp):
    """P2 + P3 on the verdict function: plain only when nothing was skipped and the run was whole; both notes combine."""
    import smoke_tree as S
    assert S.verdict(0, [], None) == "SMOKE PASS"
    assert S.verdict(0, ["note"], None) == "SMOKE PASS (1 skipped: note)"
    assert S.verdict(0, ["note", "framed"], None) == "SMOKE PASS (2 skipped: framed, note)"      # framed is named in the skipped list as any check is
    assert S.verdict(0, [], "390x844") == "SMOKE PASS (partial: 390x844 only)"
    assert S.verdict(0, ["note"], "1280x900") == "SMOKE PASS (partial: 1280x900 only; 1 skipped: note)"
    assert S.verdict(2, ["note"], "390x844") == "SMOKE FAIL (2 failed)"


def t13_require_note(tmp):
    """P2: --require-note turns the note SKIP into a FAIL that says why; without it the same tree skips and exits 0."""
    out = build(tmp, fix="skeleton")
    code, o = run_tool(out)
    assert code == 0 and lines(o, "SKIP", "note"), (code, o)
    code, o = run_tool(out, "--require-note")
    assert code == 1, (code, o)
    assert [l for l in lines(o, "FAIL", "note") if "no file step carries a note" in l], o
    assert not lines(o, "SKIP", "note"), o
    assert re.fullmatch(r"SMOKE FAIL \(\d+ failed\)", last(o)), o
    code, o = run_tool(out, "--require-note", "--no-note")        # asking for the check and for it to be skipped is a usage error
    assert code == 2, (code, o)


def t14_partial_run_says_so(tmp):
    """P3: --only-viewport ends in a line that says the run was partial (the framed check is phone-only, so it neither runs nor skips here; only the note and credits skip)."""
    out = build(tmp)
    code, o = run_tool(out, "--no-note", "--only-viewport", "1280x900")
    assert code == 0, (code, o)
    assert last(o) == "SMOKE PASS (partial: 1280x900 only; 2 skipped: credits, note)", o


def t15_head_is_contained_like_get(tmp):
    """P4: the server's guard covers HEAD as it covers GET: a symlink pointing outside answers 403 to both; a file inside answers 200 to both."""
    import http.client, smoke_tree as S
    out = build(tmp)
    outside = os.path.join(tmp, "outside-app.js")
    shutil.copyfile(os.path.join(out, "graph", "page", "app.js"), outside)
    p = os.path.join(out, "graph", "page", "app.js")
    os.remove(p)
    os.symlink(outside, p)
    srv, base = S.serve(out)
    try:
        port = srv.server_address[1]
        got = {}
        for method, path in (("GET", "/graph/page/app.js"), ("HEAD", "/graph/page/app.js"), ("GET", "/graph/index.json"), ("HEAD", "/graph/index.json")):
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
            c.request(method, path)
            got[(method, path)] = c.getresponse().status
            c.close()
    finally:
        srv.shutdown()
        srv.server_close()
    assert got[("GET", "/graph/page/app.js")] == 403, got
    assert got[("HEAD", "/graph/page/app.js")] == 403, got
    assert got[("GET", "/graph/index.json")] == 200 and got[("HEAD", "/graph/index.json")] == 200, got
    swept, outs = sweep(out, ["/graph/page/app.js", "/graph/index.json"])        # D2: every spelling of both, GET and HEAD
    assert swept[("GET", "/graph/index.json")][0] == 200 and swept[("HEAD", "/graph/index.json")][0] == 200 and swept[("GET", "/graph/page/app.js")][0] == 403, swept
    no_leak(swept, ["/graph/page/app.js"])
    assert outs, outs


def t16_runner_counts_skips_apart(tmp):
    """P5: the case runner reports a skipping case as SKIP and counts it apart from the passes."""
    import contextlib, io
    def ok(t): pass
    def sk(t): raise Skip("no fixture")
    def bad(t): assert False, "boom"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        results = run_cases([("A ok", ok), ("B skips", sk), ("C fails", bad)], None)
    text = buf.getvalue()
    assert [r[1] for r in results] == ["pass", "skip", "fail"], results
    assert "SKIP B skips" in text and "PASS B skips" not in text, text
    assert "3 cases, 1 passed, 1 skipped, 1 failed" in text, text


def fetch(site, reqs):
    """Serve `site` in-process and answer each (method, raw path) with (status, body); returns (answers, the OUTSIDE list as it ended)."""
    import http.client, smoke_tree as S
    S.OUTSIDE.clear()
    srv, base = S.serve(site)
    got = {}
    try:
        for method, path in reqs:
            c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=10)
            c.putrequest(method, path, skip_accept_encoding=True)
            c.endheaders()
            try:
                r = c.getresponse()
                got[(method, path)] = (r.status, r.read())
            except Exception as e:  # noqa: BLE001
                got[(method, path)] = ("ERR", repr(e))
            c.close()
    finally:
        srv.shutdown()
        srv.server_close()
    return got, list(S.OUTSIDE)


REFUSED = (301, 403, 404)      # what a request that must not reach a byte outside the folder may answer
LEAK_MARKERS = (b"SECRET", b"OUTINDEX", b"OUTHTM", b"Directory listing", b"secret.txt", b"x.htm", b"entry-name-xyz")


def canon(spelling):
    """The path the server decodes a spelling to (translate_path's view: decoded once, `.` and `..` and empty parts dropped, a trailing slash kept)."""
    u = urllib.parse.unquote(spelling.split("?")[0])
    n = "/" + "/".join(x for x in u.split("/") if x not in ("", ".", ".."))
    return n + "/" if u.rstrip().endswith("/") and not n.endswith("/") else n


def spellings(path):
    """D2: the equivalent request spellings of one path, ONE list that every containment case runs: the literal form; `%2f` and `%2F` for each
    `/` (singly, and all together) and appended as a trailing slash; `.`, `%2e`, `..` and `%2e%2e` in front; a doubled `//`; and the
    double-encoded `%252f`, which the server's single decode reads as the characters `%2f` inside a name, so it names no directory."""
    idx = [i for i, ch in enumerate(path) if ch == "/" and i > 0]
    out = [path]
    for enc in ("%2f", "%2F"):
        out += [path[:i] + enc + path[i + 1:] for i in idx]
        if len(idx) > 1:
            out.append(path[0] + path[1:].replace("/", enc))
        out.append(path + enc)
    for dots in ("..", "%2e%2e", ".", "%2e"):
        out += ["/" + dots + path, "/" + dots + "%2f" + path[1:]]
    out.append(path.replace("/", "//"))
    out += [path[:i] + "%252f" + path[i + 1:] for i in idx]
    if len(idx) > 1:
        out.append(path[0] + path[1:].replace("/", "%252f"))
    out.append(path + "%252f")
    return list(dict.fromkeys(out))


def sweep(site, paths):
    """Every spelling of every path, GET and HEAD, plus the path each decodes to. A spelling must be answered exactly as that decoded path is
    (status and body); a double-encoded one names no real entry, so it is a 404. Returns (answers, OUTSIDE as it ended)."""
    reqs = []
    for p in paths:
        for s in spellings(p):
            for m in ("GET", "HEAD"):
                reqs.append((m, s))
                if "%25" not in s:
                    reqs.append((m, canon(s)))
    got, outside = fetch(site, list(dict.fromkeys(reqs)))
    for p in paths:
        for s in spellings(p):
            for m in ("GET", "HEAD"):
                if "%25" in s:
                    assert got[(m, s)][0] in (403, 404), ("a double-encoded slash is a literal name, not a slash: a refusal, never a 200", m, s, got[(m, s)])
                else:
                    assert got[(m, s)] == got[(m, canon(s))], ("a spelling is answered unlike the path the server decodes it to", m, s, canon(s), got[(m, s)], got[(m, canon(s))])
    return got, outside


def no_leak(got, paths):
    """No spelling of these paths is ever answered 200, and none carries an outside byte or a directory listing, in GET or HEAD."""
    for p in paths:
        for s in spellings(p):
            for m in ("GET", "HEAD"):
                for key in ((m, s),) + (((m, canon(s)),) if "%25" not in s else ()):
                    status, body = got[key]
                    assert status in REFUSED, ("an answer that is not a refusal", key, got[key])
                    assert not [x for x in LEAK_MARKERS if x in body], ("an outside byte or a listing", key, got[key])


@contextlib.contextmanager
def no_delegation():
    """D1: while open, the stdlib's own send_head answers 500 and is recorded, so a request the tool hands to it is seen (the list it yields)."""
    import http.server
    calls = []
    orig = http.server.SimpleHTTPRequestHandler.send_head

    def trap(self):
        calls.append(self.path)
        self.send_error(500, "handed to the stdlib's send_head")
        return None
    http.server.SimpleHTTPRequestHandler.send_head = trap
    try:
        yield calls
    finally:
        http.server.SimpleHTTPRequestHandler.send_head = orig


def secret_outside(tmp):
    d = os.path.join(tmp, "elsewhere")
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, "secret.html")
    open(p, "w").write("<p>SECRET</p>")
    return p


def t17_root_index_linked_out(tmp):
    """C2a: `GET /` and `HEAD /` where the root index.html is a symlink out: 403, recorded as containment; and the tool exits 1 on a flat tree."""
    site = os.path.join(tmp, "site")
    os.makedirs(site)
    os.symlink(secret_outside(tmp), os.path.join(site, "index.html"))
    got, outside = fetch(site, [("GET", "/"), ("HEAD", "/")])
    assert got[("GET", "/")][0] == 403 and got[("HEAD", "/")][0] == 403, got
    assert b"SECRET" not in got[("GET", "/")][1], got
    assert outside, outside
    swept, outs = sweep(site, ["/"])                                          # D2: `/%2f`, `/%2F`, `/..%2f`, `//` ... all stay refused
    assert swept[("GET", "/")][0] == 403 and outs, (swept, outs)
    no_leak(swept, ["/"])


def t17c_root_index_linked_out_end_to_end(tmp):
    """T17's flat tree through the whole tool (a browser run): exit 1 naming containment."""
    os.makedirs(os.path.join(tmp, "elsewhere"), exist_ok=True)
    flat = flatten(build(tmp, name="flat"))
    real = os.path.join(flat, "index.html")
    shutil.copyfile(real, os.path.join(tmp, "elsewhere", "copy.html"))
    os.remove(real)
    os.symlink(os.path.join(tmp, "elsewhere", "copy.html"), real)
    code, o = run_tool(flat, "--no-note", "--only-viewport", "1280x900")
    assert code == 1 and lines(o, "FAIL", "containment"), (code, o)
    assert "SMOKE PASS" not in o, o


def t18_subdir_index_linked_out(tmp):
    """C2b: the reviewer's case: `GET /d/` and `HEAD /d/` where d/index.html is a symlink out: 403 and recorded (the explicit /d/index.html too)."""
    site = os.path.join(tmp, "site")
    os.makedirs(os.path.join(site, "d"))
    os.symlink(secret_outside(tmp), os.path.join(site, "d", "index.html"))
    got, outside = fetch(site, [(m, p) for m in ("GET", "HEAD") for p in ("/d/", "/d/index.html")])
    for k, (status, body) in got.items():
        assert status == 403 and b"SECRET" not in body, (k, got)
    assert outside, outside
    swept, outs = sweep(site, ["/d/", "/d", "/d/index.html"])                 # D2
    assert swept[("GET", "/d/")][0] == 403 and swept[("GET", "/d")][0] == 301 and swept[("GET", "/d/index.html")][0] == 403 and outs, (swept, outs)
    no_leak(swept, ["/d/", "/d", "/d/index.html"])


def t19_end_to_end_graph_index_linked_out(tmp):
    """C2c: the real tree with graph/index.html linked outside: the tool exits 1 naming containment, never SMOKE PASS."""
    out = build(tmp)
    real = os.path.join(out, "graph", "index.html")
    outside = os.path.join(tmp, "outside-index.html")
    shutil.copyfile(real, outside)
    os.remove(real)
    os.symlink(outside, real)
    swept, outs = sweep(out, ["/graph/", "/graph", "/graph/index.html"])      # D2: the page's own entry URL in every spelling
    assert swept[("GET", "/graph/")][0] == 403 and swept[("GET", "/graph/index.html")][0] == 403 and outs, (swept, outs)
    no_leak(swept, ["/graph/", "/graph", "/graph/index.html"])


def t19c_end_to_end_graph_index_linked_out_tool(tmp):
    """T19's tree through the whole tool (a browser run): exit 1 naming containment, never SMOKE PASS."""
    out = build(tmp)
    real = os.path.join(out, "graph", "index.html")
    outside = os.path.join(tmp, "outside-index.html")
    shutil.copyfile(real, outside)
    os.remove(real)
    os.symlink(outside, real)
    code, o = run_tool(out, "--no-note", "--only-viewport", "1280x900")
    assert code == 1, (code, o)
    assert lines(o, "FAIL", "containment"), o
    assert "SMOKE PASS" not in o, o


def t20_prefix_boundary(tmp):
    """C2d: a sibling folder whose name extends the site folder's name (site, site2) is outside: a link into it is refused. A string-prefix
    test without a separator would call it inside."""
    site = os.path.join(tmp, "site")
    os.makedirs(site)
    sib = os.path.join(tmp, "site2")
    os.makedirs(sib)
    open(os.path.join(sib, "x.txt"), "w").write("SIBLING")
    os.symlink(os.path.join(sib, "x.txt"), os.path.join(site, "x.txt"))
    open(os.path.join(site, "ok.txt"), "w").write("INSIDE")
    got, outside = fetch(site, [(m, p) for m in ("GET", "HEAD") for p in ("/x.txt", "/ok.txt")])
    assert got[("GET", "/x.txt")][0] == 403 and got[("HEAD", "/x.txt")][0] == 403, got
    assert got[("GET", "/ok.txt")] == (200, b"INSIDE") and got[("HEAD", "/ok.txt")][0] == 200, got
    assert outside, outside
    swept, outs = sweep(site, ["/x.txt", "/ok.txt"])                          # D2
    assert swept[("GET", "/x.txt")][0] == 403 and swept[("GET", "/ok.txt")] == (200, b"INSIDE") and outs, (swept, outs)
    no_leak(swept, ["/x.txt"])


def t21_require_framed_needs_phone_viewport(tmp):
    """C8 (e): --require-framed with --only-viewport 1280x900 never checks anything (the framed check runs at phone sizes only): a usage error, exit 2, saying so."""
    out = build(tmp)
    code, o = run_tool(out, "--no-note", "--require-framed", "--only-viewport", "1280x900")
    assert code == 2, (code, o)
    assert "phone sizes only" in o, o
    assert "SMOKE PASS" not in o and not lines(o, "PASS"), o


def t21b_require_floor_is_a_usage_error_naming_the_new_flag(tmp):
    """C8 (d): the old flag is never silently ignored: --require-floor is a usage error, exit 2, whose message names --require-framed."""
    out = build(tmp)
    code, o = run_tool(out, "--no-note", "--require-floor")
    assert code == 2, (code, o)
    assert "--require-floor" in o and "--require-framed" in o, o
    assert "SMOKE PASS" not in o and not lines(o, "PASS"), o


def t22_blank_note_text_fails(tmp):
    """C4: a note whose text is empty after whitespace collapse FAILs ('note text empty') even when the sheet draws some .note-body; never a pass on an empty want."""
    import contextlib, io, smoke_tree as S
    class V:
        def ev(self, expr):
            return "a body the sheet drew"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        S.note_check(V(), "390x844", {"id": "f1", "note": {"text": "  \n\t  "}}, False, True, False)
    text = buf.getvalue()
    assert lines(text, "FAIL", "note") and "note text empty" in text, text
    assert not lines(text, "PASS", "note"), text


def t23_state_reset_per_run(tmp):
    """C5: module state is reset at the start of each run (main calls the one reset function): leftovers from an earlier run do not leak."""
    import contextlib, io, smoke_tree as S
    S.OUTSIDE.append("/left-over")
    S.FAILED[0] = 3
    S.SKIPPED.append("note")
    S.OPENED.add("a1")
    d = os.path.join(tmp, "neither")
    os.makedirs(d)
    with contextlib.redirect_stdout(io.StringIO()):
        code = S.main(["smoke_tree.py", d])
    assert code == 2, code
    assert S.OUTSIDE == [] and S.FAILED == [0] and S.SKIPPED == [] and S.OPENED == set(), (S.OUTSIDE, S.FAILED, S.SKIPPED, S.OPENED)
    assert not hasattr(S, "LINES"), "the dead LINES list is gone"


def t24_nul_in_path_is_400(tmp):
    """C5: a NUL in the request path answers 400 (GET and HEAD) without a traceback in the handler thread, and the server keeps serving."""
    import contextlib, io
    site = os.path.join(tmp, "site")
    os.makedirs(site)
    open(os.path.join(site, "s.txt"), "w").write("S")
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        got, _ = fetch(site, [("GET", "/s.txt%00.js"), ("HEAD", "/s.txt%00.js"), ("GET", "/s.txt")])
    assert got[("GET", "/s.txt%00.js")][0] == 400 and got[("HEAD", "/s.txt%00.js")][0] == 400, got
    assert got[("GET", "/s.txt")] == (200, b"S"), got
    assert "Traceback" not in err.getvalue(), err.getvalue()


def t25_ordinary_tree_served(tmp):
    """C2e: an ordinary tree is served whole: both entry directories and a file answer 200 to GET and HEAD, nothing recorded as outside, and
    a link that stays inside is served."""
    site = os.path.join(tmp, "site")
    os.makedirs(os.path.join(site, "d"))
    open(os.path.join(site, "index.html"), "w").write("ROOT")
    open(os.path.join(site, "d", "index.html"), "w").write("SUB")
    open(os.path.join(site, "a.txt"), "w").write("A")
    os.symlink(os.path.join(site, "a.txt"), os.path.join(site, "back.txt"))
    got, outside = fetch(site, [(m, p) for m in ("GET", "HEAD") for p in ("/", "/d/", "/a.txt", "/back.txt")])
    for (m, p), (status, body) in got.items():
        assert status == 200, (m, p, got)
    assert got[("GET", "/")][1] == b"ROOT" and got[("GET", "/d/")][1] == b"SUB" and got[("GET", "/back.txt")][1] == b"A", got
    assert outside == [], outside


def t25c_ordinary_tree_through_the_tool(tmp):
    """T25's ordinary tree through the whole tool (a browser run)."""
    code, o = run_tool(build(tmp, name="whole"), "--no-note", "--only-viewport", "1280x900")      # the tool's end to end on an ordinary tree: T1 covers both viewports
    assert code == 0 and lines(o, "PASS", "containment"), (code, o)


def t26_no_directory_listing(tmp):
    """C1: a directory with no index file is never listed: 403 or 404 to GET and HEAD, with no entry name in the body."""
    site = os.path.join(tmp, "site")
    os.makedirs(os.path.join(site, "bare"))
    open(os.path.join(site, "bare", "entry-name-xyz.txt"), "w").write("E")
    got, _ = fetch(site, [(m, p) for m in ("GET", "HEAD") for p in ("/bare/", "/bare")])
    for k, (status, body) in got.items():
        assert status in (301, 403, 404) and b"entry-name-xyz" not in body, (k, got)
    assert got[("GET", "/bare/")][0] in (403, 404) and got[("HEAD", "/bare/")][0] in (403, 404), got
    swept, _ = sweep(site, ["/bare/", "/bare"])                               # D2: a directory is never listed in any spelling
    assert swept[("GET", "/bare/")][0] == 403 and swept[("GET", "/bare")][0] == 301, swept
    no_leak(swept, ["/bare/", "/bare"])


def t27_encoded_slash_spellings_never_reach_the_stdlib(tmp):
    """D1/D3 (round 3's blocker): a directory asked for with an ENCODED slash (`/d1%2f`) is decided from the decoded path the server opens, so
    an index linked out is a 403 recorded as containment, a directory linked out or a root with no index is never listed, a double-encoded
    slash is a literal name, and no request is ever handed to the stdlib's send_head."""
    out = os.path.join(tmp, "out")
    os.makedirs(os.path.join(out, "dir"))
    open(os.path.join(out, "secret.txt"), "w").write("SECRET")
    open(os.path.join(out, "x.htm"), "w").write("OUTHTM")
    open(os.path.join(out, "dir", "index.html"), "w").write("OUTINDEX")
    site = os.path.join(tmp, "site")
    for d in ("d1", "d2", "d4", "ok", "okd"):
        os.makedirs(os.path.join(site, d))
    os.symlink(os.path.join(out, "secret.txt"), os.path.join(site, "d1", "index.html"))       # an index linked out
    os.symlink(os.path.join(out, "dir"), os.path.join(site, "d2", "sub"))                     # a directory linked out, with an index in it
    os.symlink(os.path.join(out, "x.htm"), os.path.join(site, "d4", "index.htm"))             # the .htm index linked out
    os.symlink(out, os.path.join(site, "outdir"))                                             # a directory linked out, with no index
    open(os.path.join(site, "ok", "a.txt"), "w").write("A")
    open(os.path.join(site, "okd", "index.html"), "w").write("OKD")                           # an ordinary directory with its index
    open(os.path.join(site, "p%2fq.txt"), "w").write("INSIDE")                                # a file whose NAME holds the characters %2f
    leaks = ["/d1%2f", "/d1%2F", "/d1/%2f", "/d2/sub%2f", "/d4%2f"]
    lists = ["/outdir%2f", "/%2f"]
    with no_delegation() as calls:
        got, outs = fetch(site, [(m, p) for m in ("GET", "HEAD") for p in leaks + lists])
        for m in ("GET", "HEAD"):
            for p in leaks:
                assert got[(m, p)][0] == 403 and b"SECRET" not in got[(m, p)][1] and b"OUTHTM" not in got[(m, p)][1] and b"OUTINDEX" not in got[(m, p)][1], (m, p, got[(m, p)])
            for p in lists:
                assert got[(m, p)][0] == 403 and b"Directory listing" not in got[(m, p)][1] and b"secret.txt" not in got[(m, p)][1], (m, p, got[(m, p)])
        assert [p for p in leaks if p not in outs] == [], ("each refused request is recorded as containment", outs)
        leak_bases = ["/d1/", "/d1", "/d2/sub/", "/d2/sub", "/d4/", "/d4", "/outdir/", "/outdir", "/", "/ok/", "/ok"]
        swept, _ = sweep(site, leak_bases)
        no_leak(swept, leak_bases)
        good, _ = sweep(site, ["/okd/", "/okd", "/ok/a.txt"])
        assert good[("GET", "/okd/")] == (200, b"OKD") and good[("GET", "/okd%2f")] == (200, b"OKD") and good[("GET", "/ok/a.txt")] == (200, b"A"), good
        name, _ = fetch(site, [(m, p) for m in ("GET", "HEAD") for p in ("/p%252fq.txt", "/p%2fq.txt")])
        assert name[("GET", "/p%252fq.txt")] == (200, b"INSIDE") and name[("HEAD", "/p%252fq.txt")][0] == 200, name
        assert name[("GET", "/p%2fq.txt")][0] == 404 and name[("HEAD", "/p%2fq.txt")][0] == 404, name
    assert calls == [], ("a request was handed to the stdlib's send_head", calls)



def translate_like(kind):
    """A translate_path with the stdlib's body and one choice of trailing slash: `raw` = the check on the raw text (3.12 and 3.9, measured), `decoded` =
    after the unquote (3.14, measured), `never`, `always`. The tool must give one answer under every one of them: the slash is its own call."""
    import posixpath

    def tp(self, path):
        path = path.split("?", 1)[0].split("#", 1)[0]
        raw_slash = path.rstrip().endswith("/")
        path = urllib.parse.unquote(path, errors="surrogatepass")
        slash = {"raw": raw_slash, "decoded": path.endswith("/"), "never": False, "always": True}[kind]
        path = posixpath.normpath(path)
        out = self.directory
        for word in filter(None, path.split("/")):
            if os.path.dirname(word) or word in (os.curdir, os.pardir):
                continue
            out = os.path.join(out, word)
        return out + "/" if slash else out
    return tp


def t28_slash_is_the_tools_call_whatever_translate_path_does(tmp):
    """V1: the tool decodes the request path once and decides slash-or-not from that text, so the answer to `/d%2f` is the same under every
    translate_path trailing-slash rule the stdlib has had (raw text: 3.12; decoded text: 3.14; and the two extremes)."""
    import http.server
    out = os.path.join(tmp, "out")
    os.makedirs(out)
    open(os.path.join(out, "secret.txt"), "w").write("SECRET")
    site = os.path.join(tmp, "site")
    for d in ("okd", "ok", "d1", "bare"):
        os.makedirs(os.path.join(site, d))
    open(os.path.join(site, "okd", "index.html"), "w").write("OKD")
    open(os.path.join(site, "ok", "a.txt"), "w").write("A")
    open(os.path.join(site, "bare", "entry-name-xyz.txt"), "w").write("E")
    os.symlink(os.path.join(out, "secret.txt"), os.path.join(site, "d1", "index.html"))
    orig = http.server.SimpleHTTPRequestHandler.translate_path
    paths = ["/okd/", "/okd%2f", "/okd%2F", "/okd", "/ok/a.txt", "/ok/a.txt%2f", "/ok/a.txt/", "/d1%2f", "/d1/", "/d1", "/bare%2f", "/bare/", "/bare", "/okd%252f"]
    try:
        for kind in ("raw", "decoded", "never", "always"):
            http.server.SimpleHTTPRequestHandler.translate_path = translate_like(kind)
            got, outs = fetch(site, [(m, p) for m in ("GET", "HEAD") for p in paths])
            for m in ("GET", "HEAD"):
                for p in ("/okd/", "/okd%2f", "/okd%2F", "/ok/a.txt"):
                    assert got[(m, p)][0] == 200, (kind, m, p, got[(m, p)])
                for p in ("/okd", "/d1", "/bare"):
                    assert got[(m, p)][0] == 301, (kind, m, p, got[(m, p)])
                for p in ("/ok/a.txt%2f", "/ok/a.txt/", "/okd%252f"):
                    assert got[(m, p)][0] == 404, (kind, m, p, got[(m, p)])
                for p in ("/d1%2f", "/d1/", "/bare%2f", "/bare/"):
                    assert got[(m, p)][0] == 403, (kind, m, p, got[(m, p)])
                    assert b"SECRET" not in got[(m, p)][1] and b"entry-name-xyz" not in got[(m, p)][1], (kind, m, p, got[(m, p)])
            assert got[("GET", "/okd%2f")] == got[("GET", "/okd/")] == (200, b"OKD"), (kind, got[("GET", "/okd%2f")])
            assert "/d1%2f" in outs and "/d1/" in outs, (kind, outs)
    finally:
        http.server.SimpleHTTPRequestHandler.translate_path = orig


def t29_runner_no_browser_mode(tmp):
    """V2: the runner has a mode that runs only the cases needing no browser, and says how many it left out; every case it leaves out is a real case."""
    import contextlib, io
    def ok(t): pass
    def br(t): raise AssertionError("a browser case ran in --no-browser mode")
    NEEDS_BROWSER.add(br)
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            results = run_cases([("A ok", ok), ("B browser", br)], None, no_browser=True)
    finally:
        NEEDS_BROWSER.discard(br)
    text = buf.getvalue()
    assert [r[1] for r in results] == ["pass"], results
    assert "PASS A ok" in text and "B browser" not in text.split("\n\n")[0], text
    assert "1 case needing a browser not run (--no-browser)" in text, text
    assert NEEDS_BROWSER <= {fn for _, fn in CASES}, "every browser-marked case is a case"
    assert len(NEEDS_BROWSER) < len(CASES), "some cases need no browser"
    p = subprocess.run([sys.executable, os.path.join(HERE, "test_smoke_tree.py"), "--no-browser", "--only", "T16"], capture_output=True, text=True, timeout=120)
    assert p.returncode == 0 and "PASS T16" in p.stdout and "1 cases, 1 passed" in p.stdout, (p.returncode, p.stdout, p.stderr)


def t30_tool_imports_and_refuses_cleanly_without_playwright(tmp):
    """V2: with no playwright importable the module still imports (the containment cases need its server), and a run that needs the browser
    ends in a FAIL line and SMOKE FAIL, exit 1, naming the missing package; it never ends in a traceback or a PASS."""
    out = build(tmp)
    code = ("import sys; sys.modules['playwright'] = None; sys.path.insert(0, %r); import smoke_tree as S; "
            "assert callable(S.serve); sys.exit(S.main(['smoke_tree.py', %r, '--no-note']))" % (HERE, out))
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=120)
    o = p.stdout + p.stderr
    assert p.returncode == 1, (p.returncode, o)
    assert [l for l in lines(o, "FAIL") if "exception RuntimeError" in l and "playwright" in l], o
    assert last(o) == "SMOKE FAIL (1 failed)", o
    assert "Traceback" not in o and "SMOKE PASS" not in o, o


def t31_csp_header_says_what_it_is(tmp):
    """V3a: the csp-header line says it is the harness sending the suite's policy; the module says where real CSP coverage is and when it holds."""
    import contextlib, io, smoke_tree as S
    S.reset_state()
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        S.csp_header_check("1280x900", S.T.CSP)
        S.csp_header_check("390x844", None)
    o = buf.getvalue()
    good, bad = lines(o, "PASS", "csp-header"), lines(o, "FAIL", "csp-header")
    assert len(good) == 1 and "the harness sends the suite's policy" in good[0] and "default-src 'none'" in good[0], o
    assert len(bad) == 1 and "390x844" in bad[0], o
    assert S.FAILED == [1], S.FAILED
    S.reset_state()
    doc = " ".join(S.__doc__.split())
    assert "real CSP coverage is the console and securitypolicyviolation checks" in doc, doc
    assert "valid only while T.CSP equals the deployed policy" in doc, doc


def t32_opened_line_unit(tmp):
    """V3b: the line says how many distinct steps were opened of how many the index has; the count follows its arguments."""
    import smoke_tree as S
    assert S.opened_line({"a1", "b2", "c3"}, 353) == "opened 3 of 353 steps", S.opened_line({"a1", "b2", "c3"}, 353)
    assert S.opened_line({"a1", "b2"}, 23) == "opened 2 of 23 steps"
    assert S.opened_line(set(), 23) == "opened 0 of 23 steps"
    assert S.opened_line({"a1"}, None) == "opened 1 of ? steps"


def opened_numbers(o, tree):
    m = re.search(r"opened (\d+) of (\d+) steps", o)
    assert m, o
    ids = {l.split()[1]: l.split()[2] for l in lines(o, "ID")}
    passed = {ids[l.split()[2][5:]] for l in lines(o, "PASS") if l.split()[2].startswith("open-")}
    total = json.load(open(os.path.join(tree, "graph", "index.json")))["steps"]
    return int(m.group(1)), int(m.group(2)), len(passed), total


def t33_opened_count_end_to_end(tmp):
    """V3b: on the real fixture the run prints 'opened 3 of <the index's steps> steps'; with the group's step file gone it prints the number that really
    opened (the open-* PASS lines say which), not a fixed 3."""
    out = build(tmp)
    code, o = run_tool(out, "--no-note", "--only-viewport", "1280x900")
    n, m, want_n, want_m = opened_numbers(o, out)
    assert code == 0 and (n, m) == (3, want_m) and want_n == 3, (n, m, want_n, want_m, o)
    out2 = build(tmp, name="gone")
    os.remove(os.path.join(out2, "graph", "step", "a1.json"))
    code, o = run_tool(out2, "--no-note", "--only-viewport", "1280x900")
    n, m, want_n, want_m = opened_numbers(o, out2)
    assert code == 1 and n == want_n and n < 3 and m == want_m, (n, m, want_n, want_m, o)


class _Browser:
    def close(self): pass


class _Chromium:
    def launch(self, *a, **k): return _Browser()


class _PW:
    chromium = _Chromium()
    def __enter__(self): return self
    def __exit__(self, *a): return False


def t34_exception_in_a_viewport_is_a_fail_line_and_a_verdict(tmp):
    """V3d: an exception inside run_viewport prints `FAIL <viewport> exception <type>: <first line of the message, escaped>` for each viewport,
    the run still ends on `SMOKE FAIL (<n> failed)`, and main returns 1."""
    import contextlib, io, smoke_tree as S
    site = build(tmp)
    def boom(browser, vp, *a, **k):
        raise ValueError("bad\x1b[31m thing\nsecond line SECONDLINE")
    saved = (S.sync_playwright, S.run_viewport)
    S.sync_playwright, S.run_viewport = (lambda: _PW()), boom
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            code = S.main(["smoke_tree.py", site, "--no-note"])
    finally:
        S.sync_playwright, S.run_viewport = saved
        S.reset_state()
    o = buf.getvalue()
    assert code == 1, (code, o)
    for vp in ("390x844", "1280x900"):
        assert "FAIL %s exception ValueError: bad\\x1b[31m thing" % vp in o.splitlines(), (vp, o)
    assert "SECONDLINE" not in o, o
    assert last(o) == "SMOKE FAIL (2 failed)", o
    assert "SMOKE PASS" not in o, o


CREDITS_OK = ('<!doctype html><html><head><meta charset="utf-8"><title>Credits</title></head><body><h1>Credits</h1>'
              '<p><a href="%s">The map</a></p></body></html>')


def with_credits(site, body):
    os.makedirs(os.path.join(site, "credits"), exist_ok=True)
    open(os.path.join(site, "credits", "index.html"), "w", encoding="utf-8").write(body)
    return site


def t35_credits_page_answers_and_links_back_to_the_map(tmp):
    """V3c: a tree with credits/index.html: the page answers 200 at 1280x900 with a clean console, and its own link to the map resolves to the map's
    index and loads, on the flat shape (`../`) and the graph/ shape (`../graph/`), whichever viewport was asked for."""
    flat = with_credits(flatten(build(tmp, name="flat")), CREDITS_OK % "../")
    code, o = run_tool(flat, "--no-note", "--only-viewport", "1280x900")
    assert code == 0 and [l for l in lines(o, "PASS", "credits") if "1280x900" in l], (code, o)
    assert last(o) == "SMOKE PASS (partial: 1280x900 only; 1 skipped: note)", o
    g = with_credits(build(tmp, name="graph"), CREDITS_OK % "../graph/")
    code, o = run_tool(g, "--no-note", "--only-viewport", "390x844")
    assert code == 0 and [l for l in lines(o, "PASS", "credits") if "1280x900" in l], (code, o)       # the credits page is visited at 1280x900 whichever viewport was asked for


def t35b_credits_link_that_does_not_reach_the_map_fails(tmp):
    """V3c: a credits page whose links do not lead to the map's index is a FAIL credits (exit 1), also on the graph/ shape, where `../` is the folder
    above the map and not the map."""
    flat = with_credits(flatten(build(tmp, name="flat")), CREDITS_OK % "../nowhere/")
    code, o = run_tool(flat, "--no-note", "--only-viewport", "1280x900")
    assert code == 1 and [l for l in lines(o, "FAIL", "credits") if "link" in l], (code, o)
    assert not lines(o, "PASS", "credits"), o
    g = with_credits(build(tmp, name="graph"), CREDITS_OK % "../")
    code, o = run_tool(g, "--no-note", "--only-viewport", "1280x900")
    assert code == 1 and lines(o, "FAIL", "credits"), (code, o)


def t35c_credits_console_error_fails(tmp):
    """V3c: a console error on the credits page is a FAIL credits."""
    flat = with_credits(flatten(build(tmp, name="flat")), CREDITS_OK.replace("</body>", '<script src="n.js"></script></body>') % "../")
    open(os.path.join(flat, "credits", "n.js"), "w").write("console.error('credits noise');\n")
    code, o = run_tool(flat, "--no-note", "--only-viewport", "1280x900")
    assert code == 1 and [l for l in lines(o, "FAIL", "credits") if "credits noise" in l], (code, o)


def t36_credits_absent_is_a_named_skip_or_a_required_fail(tmp):
    """V3c: no credits/ in the tree: SKIP credits (no credits/ in tree), named in the verdict; --require-credits makes it a FAIL; with credits/ the flag passes."""
    flat = flatten(build(tmp, name="flat"))
    code, o = run_tool(flat, "--no-note", "--only-viewport", "1280x900")
    assert code == 0 and [l for l in lines(o, "SKIP", "credits") if "credits (no credits/ in tree)" in l], (code, o)
    assert last(o) == "SMOKE PASS (partial: 1280x900 only; 2 skipped: credits, note)", o
    code, o = run_tool(flat, "--no-note", "--only-viewport", "1280x900", "--require-credits")
    assert code == 1 and [l for l in lines(o, "FAIL", "credits") if "--require-credits" in l], (code, o)
    assert not lines(o, "SKIP", "credits"), o
    with_credits(flat, CREDITS_OK % "../")
    code, o = run_tool(flat, "--no-note", "--only-viewport", "1280x900", "--require-credits")
    assert code == 0 and lines(o, "PASS", "credits"), (code, o)



SHEET_PAGE = ('<!doctype html><html><head><meta charset="utf-8"><title>sheet</title></head><body><div id="graph-sheet"><div id="graph-sheet-body">%s</div></div></body></html>')


def t37_open_check_accepts_a_markup_card_or_a_made_card(tmp):
    """F1: the sheet is open on <id> when its body holds the markup's `article#<id>`, OR a card the page MADE from the data (the body's single child is
    a `.card` whose `.claim` is the step's card title, backticks dropped, whitespace collapsed). A made card of another step, a single child that is not
    a `.card`, two children, and an article of another id are each a FAIL. Run through open_check on hand-built sheet pages (the check in isolation;
    the whole-tree made-card case is T38)."""
    import contextlib, io, smoke_tree as S
    from playwright.sync_api import sync_playwright
    title = "Title of `step` a1"
    pages = {
        "made-ok": ('<div class="card"><h3 class="claim">Title  of step\n a1</h3></div>', True),
        "made-other-step": ('<div class="card"><h3 class="claim">Title of step b2</h3></div>', False),
        "made-not-a-card": ('<div class="other"><h3 class="claim">Title of step a1</h3></div>', False),
        "made-two-children": ('<div class="card"><h3 class="claim">Title of step a1</h3></div><div class="card"><h3 class="claim">Title of step a1</h3></div>', False),
        "article-ok": ('<article id="a1"><div class="claim">Title of step a1</div></article>', True),
        "article-other-id": ('<article id="zz"><div class="claim">Title of step a1</div></article>', False),
    }
    site = os.path.join(tmp, "site")
    os.makedirs(site)
    for name, (body, _) in pages.items():
        open(os.path.join(site, name + ".html"), "w", encoding="utf-8").write(SHEET_PAGE % body)
    srv, base = S.serve(site)
    saved = S.OPEN_TIMEOUT_MS
    S.OPEN_TIMEOUT_MS = 1500
    got = {}
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=S.T.SHELL[0], args=S.LAUNCH_ARGS) if S.T.SHELL else pw.chromium.launch(args=S.LAUNCH_ARGS)
            for name in pages:
                v = S.View(browser, base + name + ".html", "1280x900", {"console": [], "requests": []})
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    ok = S.open_check(v, "1280x900", "part", {"id": "a1", "title": title})
                v.close()
                got[name] = (ok, buf.getvalue())
            browser.close()
    finally:
        S.OPEN_TIMEOUT_MS = saved
        srv.shutdown()
        srv.server_close()
        S.reset_state()
    for name, (_, want) in pages.items():
        ok, text = got[name]
        assert ok is want, (name, got[name])
        assert bool(lines(text, "PASS", "open-part")) is want and bool(lines(text, "FAIL", "open-part")) is (not want), (name, text)


def t38_made_card_tree_opens(tmp):
    """F1: the real tree with its card block emptied (the About section kept): the page makes each card from the data, and the part, the group and the file
    open. A made-card regression reads FAIL here (there is no skip: main's page makes cards)."""
    def about_only(cards):
        m = re.search(r'<section id="graph-about">.*?</section>', cards, re.S)
        assert m, "the fixture's About section"
        return m.group(0) + "\n"
    out = build(tmp, cards_edit=about_only)
    html = open(os.path.join(out, "graph", "index.html"), encoding="utf-8").read()
    assert "<article" not in html and 'id="graph-about"' in html, "the card block is empty and About is kept"
    code, o = run_tool(out, "--no-note", "--only-viewport", "1280x900")
    assert code == 0, (code, o)
    for what in ("open-part", "open-group", "open-file"):
        assert [l for l in lines(o, "PASS", what) if "1280x900" in l], (what, o)


def t39_note_compared_on_what_survives_rendering(tmp):
    """F2: the note check lowercases both sides, keeps letters and digits, and requires the rendered body to CONTAIN the first 30 such characters of the
    source note: a leading '# heading', a backticked span and list marks do not break a match; another step's note, and a note with nothing to compare,
    fail."""
    import contextlib, io, smoke_tree as S
    def run(text, rendered):
        class V:
            def ev(self, expr):
                return rendered
        S.reset_state()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            S.note_check(V(), "390x844", {"id": "f1", "note": {"text": text}}, False, True, False)
        S.reset_state()
        return buf.getvalue()
    heading = run("# Title of the note\n\nBody words follow here and go on and on.", "Title of the note Body words follow here and go on and on.")
    assert lines(heading, "PASS", "note") and not lines(heading, "FAIL", "note"), heading
    code = run("Use `foo_bar` to call the thing in Lean now, and more words follow.", "Use foo_bar to call the thing in Lean now, and more words follow.")
    assert lines(code, "PASS", "note"), code
    items = run("- First item here\n- Second item here\n- Third item here and more", "First item here Second item here Third item here and more")
    assert lines(items, "PASS", "note"), items
    short = run("**Short** note.", "Short note.")
    assert lines(short, "PASS", "note"), short
    other = run("# Title of the note\n\nBody words follow here and go on and on.", "Completely other words about another step entirely, nothing alike.")
    assert lines(other, "FAIL", "note") and not lines(other, "PASS", "note"), other
    nothing = run("### ---", "anything the sheet drew")
    assert lines(nothing, "FAIL", "note") and "note text empty" in nothing and not lines(nothing, "PASS", "note"), nothing



def real_top(fix_dir=None):
    return json.load(open(os.path.join(HERE, "fixtures", "real", "index.json")))["top"]


def childless(*ids):
    """step_edit: each id becomes a step with no children (a part that is a leaf)."""
    def edit(steps):
        for i in ids:
            steps[i]["children"] = []
            steps[i]["card"]["child_count"] = 0
            steps[i]["card"].pop("child_kind", None)
    return edit


def t41_framed_check_names_a_missing_parts_button(tmp):
    """C3 (g): the part the framed check opens has parts, but its open sheet offers no parts button (a COPY of the page never builds it): at each phone
    size FAIL `framed no parts button on <id>`, by name, never a crash and never a pass."""
    out = build(tmp, mutate={"page/sheet.js": NO_PARTS_BUTTON})
    part = real_top()[0]
    code, o = run_tool(out, "--no-note", "--only-viewport", "390x844")
    assert code == 1, (code, o)
    for vp in ("390x844", "360x640"):
        assert [l for l in lines(o, "FAIL", "framed") if l.startswith("FAIL %s framed no parts button on %s" % (vp, part))], (vp, o)
    assert not lines(o, "PASS", "framed") and "Traceback" not in o, o


def t41b_framed_check_names_parts_that_did_not_open(tmp):
    """C3: the button is pressed and no part opens within the timeout (a COPY of the page's open-parts route opens nothing): FAIL
    `framed parts did not open on <id>`, by name."""
    out = build(tmp, mutate={"page/app.js": PARTS_NEVER_OPEN})
    part = real_top()[0]
    code, o = run_tool(out, "--no-note", "--only-viewport", "390x844")
    assert code == 1, (code, o)
    assert [l for l in lines(o, "FAIL", "framed") if l.startswith("FAIL 390x844 framed parts did not open on %s" % part)], o
    assert not lines(o, "PASS", "framed") and "Traceback" not in o, o


def t41c_part_is_the_first_top_part_with_children(tmp):
    """F3: the part the checks open is the first top part that HAS children (a parts button to open), so a leaf in front of it does not end the run.
    (Decided from the data files by pick_ids, in process: a real-fixture tree with a leaf made of its first top part does not boot in the page, so
    the tool's whole run is not the instrument here.)"""
    import contextlib, io, smoke_tree as S
    top = real_top()
    out = build(tmp, step_edit=childless(top[0]))
    base_dir = os.path.join(out, "graph")
    index = json.load(open(os.path.join(base_dir, "index.json"), encoding="utf-8"))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        part, group, _file = S.pick_ids(base_dir, index, True)        # the choice reads data files only: no page, no browser
    assert part["id"] == top[1] and part["rule"] == "first id of index top that has children", (part, top)
    assert [l for l in lines(buf.getvalue(), "ID") if l.startswith("ID part %s (first id of index top that has children)" % top[1])], buf.getvalue()
    assert group["id"] in [c["id"] for c in json.load(open(os.path.join(base_dir, "step", top[1] + ".json")))["children"]], group
    ok = build(tmp, name="plain")                                    # when the first top part has children the rule text is the old one
    with contextlib.redirect_stdout(io.StringIO()):
        part0, _g, _f = S.pick_ids(os.path.join(ok, "graph"), json.load(open(os.path.join(ok, "graph", "index.json"))), True)
    assert part0["id"] == top[0] and part0["rule"] == "first id of index top", part0


def t41d_no_top_part_with_children_is_a_named_fail(tmp):
    """F3: a tree in which no top part has children has no box to open and no group to open either: the run FAILs by name at the ids (it cannot reach the
    framed check, so no framed line is printed here at all), never a crash and never a pass."""
    out = build(tmp, step_edit=childless(*real_top()))
    code, o = run_tool(out, "--no-note", "--only-viewport", "390x844")
    assert code == 1 and [l for l in lines(o, "FAIL", "ids") if "no top part has children" in l], (code, o)
    assert "Traceback" not in o and "SMOKE PASS" not in o, o
    assert not lines(o, "PASS", "framed") and not lines(o, "FAIL", "framed"), o
    code, o = run_tool(out, "--no-note", "--require-framed", "--only-viewport", "390x844")      # required or not, the run ends at the ids: exit 1
    assert code == 1 and lines(o, "FAIL", "ids") and "SMOKE PASS" not in o, (code, o)


# ---- the framed check (R2): the opened box, title included, inside the visible map stage, at two phone sizes ----
PHONES = ("390x844", "360x640")
FLOOR_1_2 = lambda index: index.update({"open_scale_floor": 1.2})        # 1.2: the largest floor the engine still accepts (its open-framing cap), so the map boots
# A fixed banner over the upper-middle of the window, outside #graph: it moves nothing (the box rect is unchanged) and covers the box's top corners
# and its title at 390x844 (the box sits well below the stage's own first 40 px on this fixture, so a strip there would cover nothing).
OVERLAY_BANNER = '<div id="smoke-overlay" style="position:fixed;left:0;right:0;top:25%;height:30%;z-index:9999;background:#c00"></div>'


def framed_lines(o, vp):
    return [l for l in o.splitlines() if (l.startswith("PASS %s framed " % vp) or l.startswith("FAIL %s framed " % vp) or l.startswith("SKIP %s framed " % vp))]


def t42_framed_passes_on_the_real_fixture_without_a_floor_key(tmp):
    """(a): the real fixture carries no floor key in its index; the opened box is framed whole inside the stage at both phone sizes, with the line's fields; no
    framed line at 1280x900; at 360x640 nothing but the framed line is run."""
    out = build(tmp)
    code, o = run_tool(out, "--no-note")
    assert code == 0, (code, o)
    for vp in PHONES:
        got = framed_lines(o, vp)
        assert len(got) == 1 and got[0].startswith("PASS %s framed %s scale=" % (vp, real_top()[0])), (vp, o)
        assert re.search(r" folded=n/a box=[-0-9.]+,[-0-9.]+,[-0-9.]+,[-0-9.]+ stage=[-0-9.]+,[-0-9.]+,[-0-9.]+,[-0-9.]+ viewport=%s$" % vp, got[0]), got[0]
    assert not framed_lines(o, "1280x900"), o
    assert not [l for l in o.splitlines() if len(l.split(" ")) > 2 and l.split(" ")[1] == "360x640" and l.split(" ")[2] != "framed"], o      # no boot/open/note/console line there
    assert "framed" not in last(o), o


def t42b_a_floor_the_engine_accepts_but_the_stage_cannot_hold_fails_framed_alone(tmp):
    """(b) THE DISCRIMINATING CONTROL: the identical tree with ONE key, the index floor set to 1.2 (the largest floor that still boots), frames the opened box at
    scale 1.2, far wider than the phone: FAIL framed at 360x640 with `box outside stage`, while boot, open and console stay PASS."""
    out = build(tmp, index_edit=FLOOR_1_2)
    code, o = run_tool(out, "--no-note")
    assert code == 1, (code, o)
    bad = framed_lines(o, "360x640")
    assert len(bad) == 1 and bad[0].startswith("FAIL 360x640 framed ") and "box outside stage" in bad[0] and "scale=1.2" in bad[0], o
    for chk in ("boot", "open-part", "open-group", "open-file", "console", "requests", "csp"):
        assert {l.split()[1] for l in lines(o, "PASS", chk)} == {"390x844", "1280x900"}, (chk, o)
    fails = [l for l in o.splitlines() if l.startswith("FAIL ")]
    assert fails and all(" framed " in l for l in fails), o      # the failure is the framed check's alone


def t42c_an_overlay_the_rect_math_cannot_see_fails_the_probe(tmp):
    """(c) OVERLAY CONTROL: a copy of the fixture whose shell adds a fixed banner over the box: the box rect is inside the stage (no `box outside stage`),
    yet the check FAILs, naming the covering element by what elementFromPoint returned."""
    out = build(tmp, shell_edit=sub_once("</body>", OVERLAY_BANNER + "</body>"))
    code, o = run_tool(out, "--no-note", "--only-viewport", "390x844")
    assert code == 1, (code, o)
    for vp in PHONES:
        got = framed_lines(o, vp)
        assert len(got) == 1 and got[0].startswith("FAIL %s framed " % vp), (vp, o)
        assert "overlaid at" in got[0] and "div#smoke-overlay" in got[0] and "box outside stage" not in got[0], got[0]


def t42f_no_part_to_open_is_a_skip_or_a_required_fail(tmp):
    """(f) C7: the framed runner given no part SKIPs `framed (no part with parts to open)` (named in the verdict's skipped list), and FAILs when the check
    is required; it touches no browser. (Through the whole tool a tree with no part with children ends at the ids, t41d, before any viewport runs.)"""
    import contextlib, io, smoke_tree as S
    for required in (False, True):
        S.reset_state()
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                S.run_framed(None, "http://127.0.0.1:1/", None, required)
            o, failed, skipped = buf.getvalue(), S.FAILED[0], list(S.SKIPPED)
        finally:
            S.reset_state()
        if required:
            assert failed == 1 and not skipped and [l for l in lines(o, "FAIL", "framed") if "no part with parts to open" in l and "--require-framed" in l], o
        else:
            assert failed == 0 and skipped == ["framed"] and "SKIP all framed (no part with parts to open)" in o.splitlines(), (o, skipped)
            assert S.verdict(0, skipped, None) == "SMOKE PASS (1 skipped: framed)"


def t42h_only_viewport_phone_runs_framed_at_both_phone_sizes(tmp):
    """(h) C2: --only-viewport 390x844 runs the framed check at 390x844 AND 360x640 (nothing else at 360x640), none at 1280x900, and the verdict says partial."""
    out = build(tmp)
    code, o = run_tool(out, "--no-note", "--only-viewport", "390x844")
    assert code == 0, (code, o)
    for vp in PHONES:
        assert len(framed_lines(o, vp)) == 1 and framed_lines(o, vp)[0].startswith("PASS "), (vp, o)
    assert not [l for l in o.splitlines() if "1280x900" in l.split(" ")[:2]], o
    assert "partial: 390x844 only" in last(o) and "framed" not in last(o), o
    code, o = run_tool(out, "--no-note", "--only-viewport", "1280x900")
    assert code == 0 and not [l for l in o.splitlines() if " framed " in l], (code, o)


CASES = [
    ("T1 the real fixture (--no-note): exit 0, SMOKE PASS, three ids, the checks named", t1_real_fixture),
    ("T1b the flat shape (A1): TREE flat, exit 0", t1b_flat_shape),
    ("T1c neither shape: exit 2", t1c_neither_shape),
    ("T2 an extra strings key: exit 1, the boot check FAILs, extra-string in the output", t2_extra_string),
    ("T3 a step file the path needs is deleted: exit 1, the failure names it", t3_deleted_step),
    ("T4 a request outside SITE_DIR (symlinked page file): refused, FAIL containment", t4_symlink_out_of_tree),
    ("T4b a step file symlinked out is refused when the tool reads it too", t4b_symlink_read_by_tool),
    ("T5 a committed fixture with notes passes the note check, or a printed skip", t5_note_fixture_or_skip),
    ("T5b no note in the data and no --no-note: SKIP note, never a pass (A2)", t5b_no_notes_in_data_is_a_skip),
    ("T5c a note in the data and no .note-body on the sheet: FAIL note (A2)", t5c_missing_note_section_fails),
    ("T6 K1: a console error alone fails the console check", t6_console_error_alone_fails_s2),
    ("T7 K2: a second fixture with different ids passes and its ids are the data's", t7_second_fixture_different_ids),
    ("T8 K3: the Content-Security-Policy header is sent and reported", t8_csp_header_is_checked),
    ("T9b a tree with an unknown index key is refused at boot and the tool fails it", t9b_base_refuses_unknown_index_key),
    ("T10 --only-viewport runs one viewport", t10_only_viewport),
    ("T11 P1: an empty card title fails the heading check", t11_empty_heading_fails),
    ("T12 P2: the verdict line names every skip", t12_skips_named_in_last_line),
    ("T12b P2/P3: the verdict function: plain only with no skip and a whole run", t12b_verdict_line_unit),
    ("T13 P2: --require-note turns the note skip into a fail", t13_require_note),
    ("T14 P3: a one-viewport run says it was partial", t14_partial_run_says_so),
    ("T15 P4: HEAD is refused outside the folder as GET is", t15_head_is_contained_like_get),
    ("T16 P5: the case runner counts a skip apart from a pass", t16_runner_counts_skips_apart),
    ("T17 C2a: a root index.html linked outside: GET / and HEAD / refused, the tool exits 1 (flat)", t17_root_index_linked_out),
    ("T18 C2b: a sub-directory's index.html linked outside: GET /d/ and HEAD /d/ refused", t18_subdir_index_linked_out),
    ("T19 C2c: graph/index.html linked outside: the tool exits 1 naming containment, never SMOKE PASS", t19_end_to_end_graph_index_linked_out),
    ("T20 C2d: a sibling folder named like the site plus a suffix is outside (the prefix boundary)", t20_prefix_boundary),
    ("T21 C8 (e): --require-framed with --only-viewport 1280x900 is a usage error", t21_require_framed_needs_phone_viewport),
    ("T21b C8 (d): --require-floor is a usage error that names --require-framed", t21b_require_floor_is_a_usage_error_naming_the_new_flag),
    ("T22 C4: a note whose text is blank after collapse FAILs, never passes on an empty want", t22_blank_note_text_fails),
    ("T23 C5: module state is reset at the start of each run", t23_state_reset_per_run),
    ("T24 C5: a NUL in the request path answers 400 with no traceback", t24_nul_in_path_is_400),
    ("T25 C2e: an ordinary tree is served whole and passes", t25_ordinary_tree_served),
    ("T26 C1: a directory with no index is never listed", t26_no_directory_listing),
    ("T27 D1/D3: an encoded-slash directory request is decided from the decoded path: no outside byte, no listing, no stdlib hand-off", t27_encoded_slash_spellings_never_reach_the_stdlib),
    ("T4c the symlinked page file through the whole tool: FAIL containment", t4c_symlink_out_of_tree_end_to_end),
    ("T17c the root index linked outside through the whole tool (flat): exit 1", t17c_root_index_linked_out_end_to_end),
    ("T19c graph/index.html linked outside through the whole tool: exit 1", t19c_end_to_end_graph_index_linked_out_tool),
    ("T25c an ordinary tree through the whole tool passes", t25c_ordinary_tree_through_the_tool),
    ("T28 V1: the slash is the tool's call under every translate_path trailing-slash rule", t28_slash_is_the_tools_call_whatever_translate_path_does),
    ("T29 V2: the runner's --no-browser mode runs the cases that need none", t29_runner_no_browser_mode),
    ("T30 V2: no playwright: the module imports, a browser run ends in FAIL and SMOKE FAIL", t30_tool_imports_and_refuses_cleanly_without_playwright),
    ("T31 V3a: csp-header says what it is; the module says where real CSP coverage is", t31_csp_header_says_what_it_is),
    ("T32 V3b: the opened line follows its arguments", t32_opened_line_unit),
    ("T33 V3b: the opened count is what really opened, of the index's steps", t33_opened_count_end_to_end),
    ("T34 V3d: an exception in a viewport is a FAIL line and a SMOKE FAIL verdict", t34_exception_in_a_viewport_is_a_fail_line_and_a_verdict),
    ("T35 V3c: credits/ answers and links back to the map", t35_credits_page_answers_and_links_back_to_the_map),
    ("T35b V3c: a credits link that does not reach the map fails", t35b_credits_link_that_does_not_reach_the_map_fails),
    ("T35c V3c: a console error on the credits page fails", t35c_credits_console_error_fails),
    ("T36 V3c: no credits/ is a named skip, a fail with --require-credits", t36_credits_absent_is_a_named_skip_or_a_required_fail),
    ("T37 F1: the sheet is open on a markup card of the id or a made card of the title; anything else fails", t37_open_check_accepts_a_markup_card_or_a_made_card),
    ("T38 F1: a tree with no card articles opens its part, group and file on the cards the page makes from the data", t38_made_card_tree_opens),
    ("T39 F2: the note is compared on lowercase letters and digits, contained in the rendered body", t39_note_compared_on_what_survives_rendering),
    ("T41 (g): a sheet with no parts button is a named FAIL of the framed check", t41_framed_check_names_a_missing_parts_button),
    ("T41b: parts that do not open are a named FAIL of the framed check", t41b_framed_check_names_parts_that_did_not_open),
    ("T41c F3: the part opened is the first top part that has children", t41c_part_is_the_first_top_part_with_children),
    ("T41d F3: no top part with children is a named FAIL at the ids", t41d_no_top_part_with_children_is_a_named_fail),
    ("T42 (a): the real fixture without a floor key is framed at both phone sizes, and nowhere else", t42_framed_passes_on_the_real_fixture_without_a_floor_key),
    ("T42b (b): a floor of 1.2 the stage cannot hold fails the framed check alone", t42b_a_floor_the_engine_accepts_but_the_stage_cannot_hold_fails_framed_alone),
    ("T42c (c): an overlay the rect math cannot see fails the probe and is named", t42c_an_overlay_the_rect_math_cannot_see_fails_the_probe),
    ("T42f (f): no part to open is a SKIP, a FAIL when required", t42f_no_part_to_open_is_a_skip_or_a_required_fail),
    ("T42h (h): --only-viewport 390x844 runs framed at both phone sizes", t42h_only_viewport_phone_runs_framed_at_both_phone_sizes),
]

# The cases that start a browser (the tool's whole run, or the page suite's). The rest speak plain HTTP to the tool's server or call its functions,
# and pass on a Python with no playwright: `test_smoke_tree.py --no-browser`.
NEEDS_BROWSER = {t1_real_fixture, t1b_flat_shape, t2_extra_string, t3_deleted_step, t4c_symlink_out_of_tree_end_to_end, t5_note_fixture_or_skip,
                 t5b_no_notes_in_data_is_a_skip, t5c_missing_note_section_fails, t6_console_error_alone_fails_s2, t7_second_fixture_different_ids,
                 t8_csp_header_is_checked, t9b_base_refuses_unknown_index_key, t10_only_viewport, t11_empty_heading_fails,
                 t12_skips_named_in_last_line, t13_require_note, t14_partial_run_says_so, t17c_root_index_linked_out_end_to_end,
                 t19c_end_to_end_graph_index_linked_out_tool, t25c_ordinary_tree_through_the_tool, t33_opened_count_end_to_end,
                 t35_credits_page_answers_and_links_back_to_the_map, t35b_credits_link_that_does_not_reach_the_map_fails, t35c_credits_console_error_fails,
                 t36_credits_absent_is_a_named_skip_or_a_required_fail,
                 t37_open_check_accepts_a_markup_card_or_a_made_card, t38_made_card_tree_opens,
                 t41_framed_check_names_a_missing_parts_button, t41b_framed_check_names_parts_that_did_not_open,
                 t41d_no_top_part_with_children_is_a_named_fail, t42_framed_passes_on_the_real_fixture_without_a_floor_key,
                 t42b_a_floor_the_engine_accepts_but_the_stage_cannot_hold_fails_framed_alone, t42c_an_overlay_the_rect_math_cannot_see_fails_the_probe,
                 t42h_only_viewport_phone_runs_framed_at_both_phone_sizes}


def run_cases(cases, only, no_browser=False):
    """Run each case in a fresh temp dir. Returns [(name, "pass"|"skip"|"fail")]; prints one line per case and the summary line.
    no_browser leaves out the cases in NEEDS_BROWSER and says how many it left out."""
    results = []
    left_out = 0
    for name, fn in cases:
        if only and only not in name:
            continue
        if no_browser and fn in NEEDS_BROWSER:
            left_out += 1
            continue
        tmp = tempfile.mkdtemp(prefix="smoke-test-")
        try:
            fn(tmp)
            results.append((name, "pass"))
            print("PASS " + name)
        except Skip as e:
            results.append((name, "skip"))
            print("SKIP " + name + ": " + str(e))
        except Exception as e:  # noqa: BLE001
            results.append((name, "fail"))
            print("FAIL " + name + ": " + repr(e)[:900])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    n = lambda k: len([r for r in results if r[1] == k])
    print("\n%d cases, %d passed, %d skipped, %d failed" % (len(results), n("pass"), n("skip"), n("fail")))
    if left_out:
        print("%d case%s needing a browser not run (--no-browser)" % (left_out, "" if left_out == 1 else "s"))
    return results


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    results = run_cases(CASES, only, no_browser="--no-browser" in sys.argv)
    return 1 if [r for r in results if r[1] == "fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
