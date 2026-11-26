#!/usr/bin/env python3
"""Cases of smoke_tree.py, the one-command acceptance test of a BUILT site tree. Each case builds a tree with assemble.assemble() into a
temp dir (never anything else), runs the tool as a subprocess and reads its exit code and its lines.

Run:  python3 viewer/graph/page/test/test_smoke_tree.py [--only TEXT]   (a Python with playwright)

Contract under test (the spec's S1..S5 and the amendments A1..A3):
  exit 0 only if every check passed; 1 if any FAILED; 2 if the folder is neither tree shape. Lines are
  `PASS|FAIL|SKIP <viewport> <check> <detail>`, `TREE flat|graph/`, three `ID <what> <id> (<rule>)` lines, and a last line
  `SMOKE PASS` (naming any skip and a partial run) or `SMOKE FAIL (<n> failed)`.
Never shipped (lives under test/).
"""
import glob, json, os, re, shutil, subprocess, sys, tempfile

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


ACCEPT_FLOOR = sub_once('"assets", "strings"], [], "index")', '"assets", "strings", "open_scale_floor"], [], "index")')
ACCEPT_NOTE = sub_once('"children", "rests_on"], [], "step")', '"children", "rests_on"], ["note"], "step")')


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
    assert lines(o, "SKIP", "scale-floor") and "scale-floor (the index has no open_scale_floor)" in o, o      # A3 without the key is a SKIP
    assert not lines(o, "PASS", "scale-floor"), o


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
    """The data has a note on a file step and the page accepts the key but draws no .note-body: FAIL, never a pass (A2)."""
    def step_edit(steps):
        steps["sk-file-4"]["note"] = {"text": "A note of the repository, long enough to have its first forty characters taken.", "source": "Formalism/Basic.lean"}
    out = build(tmp, fix="skeleton", step_edit=step_edit, mutate={"page/data.js": ACCEPT_NOTE})
    code, o = run_tool(out)
    assert code == 1, (code, o)
    assert lines(o, "FAIL", "note"), o
    assert lines(o, "PASS", "boot"), o         # the page booted: this is the note check alone
    assert [l for l in lines(o, "ID") if "sk-file-4" in l], o     # the file with a note is the one picked


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


def t9_scale_floor(tmp):
    """A3 mechanics (the positive case on the real data v3 is deferred to once PR 98 is on main): the base refuses an index key it
    does not know, so these trees run a page whose data.js has been taught the key, which stands in for PR 98's acceptance only."""
    ok = build(tmp, name="floor-low", index_edit=lambda i: i.update({"open_scale_floor": 0.01}), mutate={"page/data.js": ACCEPT_FLOOR})
    code, o = run_tool(ok, "--no-note")
    assert code == 0, (code, o)
    assert [l for l in lines(o, "PASS", "scale-floor") if "390x844" in l], o
    assert not [l for l in lines(o, "PASS", "scale-floor") + lines(o, "FAIL", "scale-floor") if "1280x900" in l], o     # phone only
    bad = build(tmp, name="floor-high", index_edit=lambda i: i.update({"open_scale_floor": 100}), mutate={"page/data.js": ACCEPT_FLOOR})
    code, o = run_tool(bad, "--no-note")
    assert code == 1 and [l for l in lines(o, "FAIL", "scale-floor") if "390x844" in l], (code, o)


def t9b_base_refuses_unknown_index_key(tmp):
    """On this base a tree whose index carries open_scale_floor is refused at boot, and the tool fails it (the ruling: correct behaviour)."""
    out = build(tmp, index_edit=lambda i: i.update({"open_scale_floor": 1}))
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
    """P2: a SKIP is named in the verdict line; a tree with no notes and no scale floor skips both."""
    out = build(tmp, fix="skeleton")
    code, o = run_tool(out)
    assert code == 0, (code, o)
    assert lines(o, "SKIP", "note") and lines(o, "SKIP", "scale-floor"), o
    assert last(o) == "SMOKE PASS (2 skipped: note, scale-floor)", o


def t12b_verdict_line_unit(tmp):
    """P2 + P3 on the verdict function: plain only when nothing was skipped and the run was whole; both notes combine."""
    import smoke_tree as S
    assert S.verdict(0, [], None) == "SMOKE PASS"
    assert S.verdict(0, ["note"], None) == "SMOKE PASS (1 skipped: note)"
    assert S.verdict(0, ["note", "scale-floor"], None) == "SMOKE PASS (2 skipped: note, scale-floor)"
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


def t13b_require_floor(tmp):
    """P2: --require-floor turns the scale-floor SKIP into a FAIL that says why; a tree that has the key still passes with it."""
    out = build(tmp, fix="skeleton")
    code, o = run_tool(out, "--no-note")
    assert code == 0 and lines(o, "SKIP", "scale-floor"), (code, o)
    code, o = run_tool(out, "--no-note", "--require-floor")
    assert code == 1, (code, o)
    assert [l for l in lines(o, "FAIL", "scale-floor") if "no open_scale_floor" in l], o
    assert not lines(o, "SKIP", "scale-floor"), o
    ok = build(tmp, name="floor-low", index_edit=lambda i: i.update({"open_scale_floor": 0.01}), mutate={"page/data.js": ACCEPT_FLOOR})
    code, o = run_tool(ok, "--no-note", "--require-floor")
    assert code == 0 and [l for l in lines(o, "PASS", "scale-floor") if "390x844" in l], (code, o)


def t14_partial_run_says_so(tmp):
    """P3: --only-viewport ends in a line that says the run was partial (the floor is phone-only, so only the note skips here)."""
    out = build(tmp)
    code, o = run_tool(out, "--no-note", "--only-viewport", "1280x900")
    assert code == 0, (code, o)
    assert last(o) == "SMOKE PASS (partial: 1280x900 only; 1 skipped: note)", o


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


def t19_end_to_end_graph_index_linked_out(tmp):
    """C2c: the real tree with graph/index.html linked outside: the tool exits 1 naming containment, never SMOKE PASS."""
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


def t21_require_floor_needs_phone_viewport(tmp):
    """C3: --require-floor with --only-viewport 1280x900 never checks the floor (it runs at 390x844 only): a usage error, exit 2, saying so."""
    out = build(tmp)
    code, o = run_tool(out, "--no-note", "--require-floor", "--only-viewport", "1280x900")
    assert code == 2, (code, o)
    assert "390x844" in o and "floor" in o, o
    assert "SMOKE PASS" not in o, o


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
    d = os.path.join(tmp, "neither")
    os.makedirs(d)
    with contextlib.redirect_stdout(io.StringIO()):
        code = S.main(["smoke_tree.py", d])
    assert code == 2, code
    assert S.OUTSIDE == [] and S.FAILED == [0] and S.SKIPPED == [], (S.OUTSIDE, S.FAILED, S.SKIPPED)
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
    ("T9 A3: the scale floor is read at 390x844 only; a low floor passes and an impossible one fails", t9_scale_floor),
    ("T9b the base refuses an unknown index key at boot and the tool fails it", t9b_base_refuses_unknown_index_key),
    ("T10 --only-viewport runs one viewport", t10_only_viewport),
    ("T11 P1: an empty card title fails the heading check", t11_empty_heading_fails),
    ("T12 P2: the verdict line names every skip", t12_skips_named_in_last_line),
    ("T12b P2/P3: the verdict function: plain only with no skip and a whole run", t12b_verdict_line_unit),
    ("T13 P2: --require-note turns the note skip into a fail", t13_require_note),
    ("T13b P2: --require-floor turns the scale-floor skip into a fail", t13b_require_floor),
    ("T14 P3: a one-viewport run says it was partial", t14_partial_run_says_so),
    ("T15 P4: HEAD is refused outside the folder as GET is", t15_head_is_contained_like_get),
    ("T16 P5: the case runner counts a skip apart from a pass", t16_runner_counts_skips_apart),
    ("T17 C2a: a root index.html linked outside: GET / and HEAD / refused, the tool exits 1 (flat)", t17_root_index_linked_out),
    ("T18 C2b: a sub-directory's index.html linked outside: GET /d/ and HEAD /d/ refused", t18_subdir_index_linked_out),
    ("T19 C2c: graph/index.html linked outside: the tool exits 1 naming containment, never SMOKE PASS", t19_end_to_end_graph_index_linked_out),
    ("T20 C2d: a sibling folder named like the site plus a suffix is outside (the prefix boundary)", t20_prefix_boundary),
    ("T21 C3: --require-floor with --only-viewport 1280x900 is a usage error", t21_require_floor_needs_phone_viewport),
    ("T22 C4: a note whose text is blank after collapse FAILs, never passes on an empty want", t22_blank_note_text_fails),
    ("T23 C5: module state is reset at the start of each run", t23_state_reset_per_run),
    ("T24 C5: a NUL in the request path answers 400 with no traceback", t24_nul_in_path_is_400),
    ("T25 C2e: an ordinary tree is served whole and passes", t25_ordinary_tree_served),
    ("T26 C1: a directory with no index is never listed", t26_no_directory_listing),
]


def run_cases(cases, only):
    """Run each case in a fresh temp dir. Returns [(name, "pass"|"skip"|"fail")]; prints one line per case and the summary line."""
    results = []
    for name, fn in cases:
        if only and only not in name:
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
    return results


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    results = run_cases(CASES, only)
    return 1 if [r for r in results if r[1] == "fail"] else 0


if __name__ == "__main__":
    sys.exit(main())
