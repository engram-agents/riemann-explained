#!/usr/bin/env python3
"""Gate: every Python tool of tools/ refuses an interpreter older than 3.12, with one line, before it does anything else.

Why: a Mac's system Python 3.9.6 ran `build_site.py --selftest` as 181 pass / 401 fail, where 3.12 passes everything.
The cause is untested (3.10 and 3.11 were not available to bracket it). The honest floor is 3.12, the tested version,
and a tool says so instead of failing hundreds of cases.

CONTRACT (cases, prefix PYF-)
 PYF-ALL    Every tools/*.py has a module docstring and carries the guard as its first executable statements: after
            the docstring and any `from __future__` imports come, in this order, `import sys` and an `if` that raises SystemExit with the
            wording below, written as the three lines of GUARD (the file's own name in place of NAME). Read with `ast`,
            compared as text; a `from __future__` import after the guard is refused too (it would not compile). A tool added later without it turns this case red and the case names the file.
 PYF-REFUSE Each tool, run with sys.version_info faked to (3, 9, 6, 'final', 0) and again to (3, 11, 9, 'final', 0)
            (the second so that a floor of 3.11 is told from 3.12) and argv [tool, '--selftest']: exit
            status 1, stdout empty, stderr exactly ONE line,
            `NAME: needs Python 3.12 or newer (tested with 3.12); this is 3.9.6 at <sys.executable>` (3.11.9 for the second),
            and nothing written (the run's working and temporary folder stays empty).
 PYF-PASS   Each tool, run with sys.version_info faked to (3, 12, 0, 'final', 0) and then (3, 13, 1, 'final', 0) and
            argv [tool, '--help'] (the cheapest harmless mode; every tool answers it with a usage line or nothing, none
            runs its self-test for it): the refusal line is NOT printed, and nothing is written.
 PYF-ORDER  The guard runs before anything else: with the faked old version and arguments that would otherwise fail
            (an input path that does not exist, an output path that must not appear), the stderr is the version line
            alone, not the tool's own error, and nothing is written.
 A library (a tool that others load by file path: decl_table.py, lean_decls.py, rh_anchor.py) carries the guard too;
 when it is imported on an old interpreter the guard raises SystemExit(1) carrying the line, so the importer stops
 with that line instead of a stack trace (an importer that catches Exception does not catch SystemExit, which is
 what we want here: the refusal is not an error to recover from).
 Exit 0 if every case passes, 1 if one fails, 2 usage, 4 if the checker's own self-test fails (a normal run does
 that first). --selftest plants a small tools folder (one good file, one with no guard, one with the guard after an
 import, one with other wording, one that refuses 3.12 itself) and expects the cases to name exactly the right files.
 LIMIT: a faked sys.version_info, not another interpreter; the real old-interpreter proof is a run on 3.9.

usage: check_python_floor.py [TOOLS_DIR]     (default: the folder of this file)
       check_python_floor.py --selftest
"""
import ast
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile

# The guard, as three lines. NAME is the tool's own file name. Old-interpreter syntax on purpose (no walrus, no match,
# no f-string): it has to parse where the rest of the file may not.
GUARD = (
    "import sys\n"
    "if sys.version_info[:2] < (3, 12):\n"
    "    raise SystemExit(\"NAME: needs Python 3.12 or newer (tested with 3.12); this is %d.%d.%d at %s\" % "
    "(sys.version_info[0], sys.version_info[1], sys.version_info[2], sys.executable))\n"
)
OLD = (3, 9, 6, "final", 0)
OLDS = [OLD, (3, 11, 9, "final", 0)]
NEW_OK = [(3, 12, 0, "final", 0), (3, 13, 1, "final", 0)]
TIMEOUT = 15


def tool_files(tools_dir):
    return sorted(n for n in os.listdir(tools_dir) if n.endswith(".py") and os.path.isfile(os.path.join(tools_dir, n)))


def guard_problem(tools_dir, name):
    """None if the file carries the guard first; else a short reason."""
    src = open(os.path.join(tools_dir, name), encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        return "does not parse (%s)" % e
    body = tree.body
    if not (body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str)):
        return "no module docstring first"
    i = 1
    while i < len(body) and isinstance(body[i], ast.ImportFrom) and body[i].module == "__future__":
        i += 1
    if i + 1 >= len(body) or not isinstance(body[i], ast.Import) or not isinstance(body[i + 1], ast.If):
        return "the guard is not the first executable statement"
    lines = src.split("\n")
    text = "\n".join(lines[body[i].lineno - 1:body[i + 1].end_lineno]) + "\n"
    if text != GUARD.replace("NAME", name):
        return "the guard text differs from the standard one"
    for st in body[i + 2:]:
        if isinstance(st, ast.ImportFrom) and st.module == "__future__":
            return "a __future__ import comes after the guard"
    return None


def case_all(tools_dir):
    out = []
    for n in tool_files(tools_dir):
        p = guard_problem(tools_dir, n)
        if p:
            out.append("%s: %s" % (n, p))
    return out


def run_faked(tool, ver, args, work):
    """Run `tool` as __main__ with sys.version_info faked; returns (rc, stdout, stderr). `work` is cwd and TMPDIR."""
    code = ("import sys, runpy; sys.version_info = %r; tool = sys.argv[1]; sys.argv = [tool] + sys.argv[2:]; "
            "runpy.run_path(tool, run_name='__main__')" % (ver,))
    env = dict(os.environ)
    env["TMPDIR"] = work
    pr = subprocess.Popen([sys.executable, "-I", "-c", code, tool] + list(args), cwd=work, env=env, stdin=subprocess.DEVNULL,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, start_new_session=True)
    try:
        o, e = pr.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        os.killpg(pr.pid, signal.SIGKILL)  # our own child's group, by the id we were given
        pr.communicate()
        return None, "", ""
    return pr.returncode, o, e


def fresh(base):
    return tempfile.mkdtemp(prefix="w-", dir=base)


def refusal_line(name, ver3):
    return "%s: needs Python 3.12 or newer (tested with 3.12); this is %d.%d.%d at %s\n" % (name, ver3[0], ver3[1], ver3[2], sys.executable)


def check_refusal(tools_dir, base, args, what):
    out = []
    for n in tool_files(tools_dir):
        for ver in OLDS:
            work = fresh(base)
            rc, o, e = run_faked(os.path.join(tools_dir, n), ver, args, work)
            if rc is None:
                out.append("%s: %s %d.%d: no refusal within %d s" % (n, what, ver[0], ver[1], TIMEOUT))
                continue
            want = refusal_line(n, ver)
            if e != want:
                out.append("%s: %s %d.%d: stderr is %r, wanted %r" % (n, what, ver[0], ver[1], e[:200], want))
            elif rc != 1:
                out.append("%s: %s %d.%d: exit status %r, wanted 1" % (n, what, ver[0], ver[1], rc))
            elif o != "":
                out.append("%s: %s %d.%d: stdout is not empty: %r" % (n, what, ver[0], ver[1], o[:100]))
            elif os.listdir(work):
                out.append("%s: %s %d.%d: wrote %r" % (n, what, ver[0], ver[1], sorted(os.listdir(work))))
    return out


def case_refuse(tools_dir, base):
    return check_refusal(tools_dir, base, ["--selftest"], "old version")


def case_order(tools_dir, base):
    out = []
    for n in tool_files(tools_dir):
        work = fresh(base)
        args = [os.path.join(work, "no-such-input"), os.path.join(work, "no-such-input-2"), os.path.join(work, "out-must-not-appear")]
        rc, o, e = run_faked(os.path.join(tools_dir, n), OLD, args, work)
        if rc is None:
            out.append("%s: order: no refusal within %d s" % (n, TIMEOUT))
        elif e != refusal_line(n, OLD) or rc != 1 or o != "":
            out.append("%s: order: the stderr is %r (exit %r), not the version line alone" % (n, e[:200], rc))
        elif os.listdir(work):
            out.append("%s: order: wrote %r" % (n, sorted(os.listdir(work))))
    return out


def case_pass(tools_dir, base):
    out = []
    for n in tool_files(tools_dir):
        for ver in NEW_OK:
            work = fresh(base)
            rc, o, e = run_faked(os.path.join(tools_dir, n), ver, ["--help"], work)
            if rc is None:
                out.append("%s: %d.%d: --help did not finish in %d s" % (n, ver[0], ver[1], TIMEOUT))
            elif "needs Python 3.12" in o + e:
                out.append("%s: %d.%d: the refusal line is printed" % (n, ver[0], ver[1]))
            elif os.listdir(work):
                out.append("%s: %d.%d: wrote %r" % (n, ver[0], ver[1], sorted(os.listdir(work))))
    return out


CASES = [("PYF-ALL", lambda d, b: case_all(d)), ("PYF-REFUSE", case_refuse), ("PYF-ORDER", case_order), ("PYF-PASS", case_pass)]


def run_cases(tools_dir, base):
    bad = 0
    for cid, fn in CASES:
        problems = fn(tools_dir, base)
        if problems:
            bad += 1
            print("FAIL %s" % cid)
            for p in problems:
                print("  " + p)
        else:
            print("ok   %s" % cid)
    print("%d cases, %d failed" % (len(CASES), bad))
    return 1 if bad else 0


# --- the self-test: a planted tools folder, with the expected answers written out as literals ---
_G = "import sys\nif sys.version_info[:2] < (3, 12):\n    raise SystemExit(\"%s: needs Python 3.12 or newer (tested with 3.12); this is %%d.%%d.%%d at %%s\" %% (sys.version_info[0], sys.version_info[1], sys.version_info[2], sys.executable))\n"
PLANTED = {
    "good.py": '"""doc"""\n' + _G % "good.py" + 'print("ran")\n',
    "good_future.py": '"""doc"""\nfrom __future__ import annotations\n' + _G % "good_future.py" + 'print("ran")\n',
    "noguard.py": '"""doc"""\nprint("ran")\n',
    "late.py": '"""doc"""\nimport pyf_no_such_module_xyz\n' + _G % "late.py" + 'print("ran")\n',
    "words.py": '"""doc"""\n' + (_G % "words.py").replace("or newer", "or later") + 'print("ran")\n',
    "nodoc.py": _G % "nodoc.py" + '"""doc"""\nprint("ran")\n',
    "futlate.py": '"""doc"""\n' + _G % "futlate.py" + 'from __future__ import annotations\nprint("ran")\n',
    "le311.py": '"""doc"""\n' + (_G % "le311.py").replace("< (3, 12)", "< (3, 11)") + 'print("ran")\n',
    "le312.py": '"""doc"""\n' + (_G % "le312.py").replace("< (3, 12)", "<= (3, 12)") + 'print("ran")\n',
}
# expected: file names each case must name, exactly
PLANTED_WANT = {
    "PYF-ALL": ["futlate.py", "late.py", "le311.py", "le312.py", "nodoc.py", "noguard.py", "words.py"],
    "PYF-REFUSE": ["futlate.py", "late.py", "le311.py", "noguard.py", "words.py"],
    "PYF-ORDER": ["futlate.py", "late.py", "noguard.py", "words.py"],
    "PYF-PASS": ["le312.py"],
}


def selftest():
    base = tempfile.mkdtemp(prefix="pyf-self-")
    try:
        d = os.path.join(base, "tools")
        os.mkdir(d)
        for n, t in PLANTED.items():
            with open(os.path.join(d, n), "w", encoding="utf-8") as f:
                f.write(t)
        ok = True
        for cid, fn in CASES:
            got = sorted(set(p.split(":")[0] for p in fn(d, base)))
            if got != PLANTED_WANT[cid]:
                ok = False
                print("SELFTEST FAIL %s: named %r, wanted %r" % (cid, got, PLANTED_WANT[cid]))
        print("SELFTEST PASS" if ok else "SELFTEST FAIL")
        return 0 if ok else 4
    finally:
        shutil.rmtree(base, ignore_errors=True)


def main(argv):
    if argv[1:] == ["--selftest"]:
        return selftest()
    if len(argv) > 2:
        print(__doc__.split("usage:")[1], file=sys.stderr)
        return 2
    tools_dir = argv[1] if len(argv) == 2 else os.path.dirname(os.path.abspath(__file__))
    if not os.path.isdir(tools_dir):
        print("%s is not a folder" % tools_dir, file=sys.stderr)
        return 2
    if selftest() != 0:
        return 4
    base = tempfile.mkdtemp(prefix="pyf-run-")
    try:
        return run_cases(tools_dir, base)
    finally:
        shutil.rmtree(base, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
