#!/usr/bin/env python3
"""Cases of smoke_tree.py, the one-command acceptance test of a BUILT site tree. Each case builds a tree with assemble.assemble() into a
temp dir (never anything else), runs the tool as a subprocess and reads its exit code and its lines.

Run:  ~/.engram/venv/bin/python3 viewer/graph/page/test/test_smoke_tree.py [--only TEXT]

Contract under test (the spec's S1..S5 and the amendments A1..A3):
  exit 0 only if every check passed; 1 if any FAILED; 2 if the folder is neither tree shape. Lines are
  `PASS|FAIL|SKIP <viewport> <check> <detail>`, `TREE flat|graph/`, three `ID <what> <id> (<rule>)` lines, and a last line
  `SMOKE PASS` or `SMOKE FAIL (<n> failed)`.
Never shipped (lives under test/).
"""
import glob, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import assemble  # noqa: E402

TOOL = os.path.join(HERE, "smoke_tree.py")
RESULTS = []


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
    assert last(o) == "SMOKE PASS", o
    assert len(lines(o, "ID")) == 3, o
    assert "TREE graph/" in o, o
    for chk in ("boot", "console", "requests", "csp-header", "open-part", "open-group", "open-file"):
        assert lines(o, "PASS", chk), (chk, o)
    assert lines(o, "PASS", "boot")[0].split()[1] in ("390x844", "1280x900"), o
    assert {l.split()[1] for l in lines(o, "PASS", "boot")} == {"390x844", "1280x900"}, o
    assert lines(o, "SKIP", "scale-floor") and "scale-floor (not in data)" in o, o      # A3 without the key is a SKIP
    assert not lines(o, "PASS", "scale-floor"), o


def t1b_flat_shape(tmp):
    out = flatten(build(tmp))
    assert os.path.isfile(os.path.join(out, "index.html")) and not os.path.isdir(os.path.join(out, "graph"))
    code, o = run_tool(out, "--no-note")
    assert code == 0 and last(o) == "SMOKE PASS" and "TREE flat" in o, (code, o)


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
        print("   T5 SKIP: no committed fixture on this base carries a note (PR 97 adds them); the tool must not depend on it")
        return
    names = sorted({f.split(os.sep)[-3] for f in have})
    out = build(tmp, fix=names[0])
    code, o = run_tool(out)
    assert code == 0 and lines(o, "PASS", "note"), (code, o)


def t5b_no_notes_in_data_is_a_skip(tmp):
    out = build(tmp, fix="skeleton")
    code, o = run_tool(out)
    assert code == 0, (code, o)
    assert "SKIP note (no file step carries note)" in o or [l for l in lines(o, "SKIP", "note") if "no file step carries note" in l], o
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
    assert code == 0 and last(o) == "SMOKE PASS", (code, o)
    ids = {l.split()[1]: l.split()[2] for l in lines(o, "ID")}
    assert ids["part"] == "sk-part" and ids["group"] == "sk-group-a" and ids["file"] == "sk-file-1", ids
    real = build(tmp, name="real")
    _, o2 = run_tool(real, "--no-note")
    assert {l.split()[2] for l in lines(o2, "ID")}.isdisjoint(ids.values()), o2


def t8_csp_header_is_checked(tmp):
    """K3's case: the tool's server sends the suite's Content-Security-Policy and says so; a server without it fails the check."""
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
]


def main():
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    for name, fn in CASES:
        if only and only not in name:
            continue
        tmp = tempfile.mkdtemp(prefix="smoke-test-")
        try:
            fn(tmp)
            RESULTS.append((name, True))
            print("PASS " + name)
        except Exception as e:  # noqa: BLE001
            RESULTS.append((name, False))
            print("FAIL " + name + ": " + repr(e)[:900])
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    bad = [r for r in RESULTS if not r[1]]
    print("\n%d cases, %d passed, %d failed" % (len(RESULTS), len(RESULTS) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
