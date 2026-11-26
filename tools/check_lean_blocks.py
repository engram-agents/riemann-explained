#!/usr/bin/env python3
"""Read-only checker for riemann-explained notes (Halley, 2026-11-22, with Kepler).

For each note, every fenced ```lean block is tested against the source files the note's own
"Files this note was written from" table lists (paths relative to the release's lean/src/).

CONTRACT
 C1 A block is VERBATIM when its text (without the fences) is an exact substring of one listed file.
 C2 Otherwise it is WHITESPACE-ONLY when it matches after collapsing every run of whitespace to one
    space in both texts; this is reported separately and does NOT count as verbatim.
 C3 Otherwise it is NOT FOUND, and the block's first line and the note line it starts on are printed.
 C4 Blocks inside dated Correction or Clarification paragraphs are checked like any other block.
 C4a A block that is not verbatim is ACKNOWLEDGED (not NOT FOUND or WHITESPACE-ONLY) only when its
    preceding non-blank line starts with '*Not verbatim; see the correction dated YYYY-MM-DD' AND the
    note contains a heading starting '### Correction, YYYY-MM-DD' with the same date (rule agreed with Kepler).
    A marker without a matching heading leaves the block NOT FOUND / WHITESPACE-ONLY. A marker on a
    verbatim block changes nothing (it counts verbatim).
 C5 Per note it prints: checked N / verbatim V / whitespace-only W / not found F / acknowledged A, so a
    zero is distinguishable from "checked nothing". A note with no lean block prints checked 0.
 C6 A listed file that does not exist under the source root is reported as MISSING and the note
    fails; a note with lean blocks but no parsable file table fails (exit 2).
 C7 Exit 0 only if every block in every note is verbatim or acknowledged; exit 1 if any block is whitespace-only or
    not found or any listed file is missing; exit 2 on usage errors or a note with blocks but no table.
 C8 --selftest plants a one-character change into a copy of a verbatim block and must report it
    NOT FOUND, and an unchanged block VERBATIM; an acknowledged block with a matching dated heading must
    count ACKNOWLEDGED and the same marker with no matching heading must stay NOT FOUND; if not, it
    exits 4 and nothing else runs.
 LIMIT: it sees only fenced ```lean blocks. Inline code, other fenced blocks and quoted prose (for
 example the author's note) are outside it. It checks only against the files a note's table lists.
 It never writes anywhere except a temporary directory during --selftest.

usage: check_lean_blocks.py SRC_ROOT NOTE.md [NOTE.md ...]
       check_lean_blocks.py --selftest
"""
import os, re, sys, tempfile

FENCE = re.compile(r"^```lean[ \t]*\n(.*?)^```[ \t]*$", re.S | re.M)
MARK = re.compile(r"^\*Not verbatim; see the correction dated (\d{4}-\d{2}-\d{2})")
ROW = re.compile(r"^\|\s*`([^`]+\.lean)`")


def ws(s):
    return re.sub(r"\s+", " ", s).strip()


def listed_files(note_text):
    i = note_text.find("## Files this note was written from")
    if i < 0:
        return None
    out = []
    for line in note_text[i:].splitlines():
        m = ROW.match(line)
        if m:
            out.append(m.group(1))
    return out


def check_note(src_root, path):
    text = open(path, encoding="utf-8").read()
    blocks = []
    for m in FENCE.finditer(text):
        before = [l for l in text[:m.start()].splitlines() if l.strip()]
        mk = MARK.match(before[-1]) if before else None
        date = mk.group(1) if mk else None
        acked = bool(date) and re.search(r"(?m)^### Correction, " + re.escape(date), text) is not None
        blocks.append((text.count("\n", 0, m.start()) + 2, m.group(1), acked))
    files = listed_files(text)
    name = os.path.basename(path)
    if blocks and not files:
        print(f"{name}: {len(blocks)} lean blocks but no parsable file table")
        return 2
    srcs, missing = {}, []
    for f in files or []:
        p = os.path.join(src_root, f)
        if os.path.isfile(p):
            srcs[f] = open(p, encoding="utf-8").read()
        else:
            missing.append(f)
    v = w = nf = ack = 0
    for line_no, b, acked in blocks:
        body = b.rstrip("\n")
        if any(body in s for s in srcs.values()):
            v += 1
        elif acked:
            ack += 1
            print(f"  ACKNOWLEDGED {name}:{line_no}: {body.splitlines()[0][:100]}")
        elif any(ws(body) in ws(s) for s in srcs.values()):
            w += 1
            print(f"  WHITESPACE-ONLY {name}:{line_no}: {body.splitlines()[0][:100]}")
        else:
            nf += 1
            print(f"  NOT FOUND {name}:{line_no}: {body.splitlines()[0][:100]}")
    for f in missing:
        print(f"  MISSING listed file {name}: {f}")
    print(f"{name}: checked {len(blocks)} / verbatim {v} / whitespace-only {w} / not found {nf} / acknowledged {ack}"
          f" (against {len(srcs)} listed files{', %d missing' % len(missing) if missing else ''})")
    return 0 if (w == 0 and nf == 0 and not missing) else 1


def selftest():
    d = tempfile.mkdtemp()
    os.makedirs(os.path.join(d, "src", "A"))
    src = "theorem foo (n : Nat) : n = n := by\n  rfl\n\ntheorem bar : True := trivial\n"
    open(os.path.join(d, "src", "A", "F.lean"), "w").write(src)
    good = "theorem foo (n : Nat) : n = n := by\n  rfl"
    bad = "theorem foo (n : Nat) : n = m := by\n  rfl"      # one character planted
    wsonly = "theorem foo (n : Nat) : n = n := by rfl"
    acked_bad = "theorem bar : True := trivial2"          # not verbatim, marked, heading present
    orphan_bad = "theorem bar : True := trivial3"         # not verbatim, marked, NO matching heading
    note = ("# t\n\n```lean\n" + good + "\n```\n\n*Not verbatim; see the correction dated 2026-11-22 below.*\n\n```lean\n" + acked_bad +
            "\n```\n\n*Not verbatim; see the correction dated 2026-01-01 below.*\n\n```lean\n" + orphan_bad +
            "\n```\n\n### Correction, 2026-11-22\n\n```lean\n" + bad +
            "\n```\n\n```lean\n" + wsonly + "\n```\n\n## Files this note was written from\n\n"
            "| File | SHA-256 |\n|---|---|\n| `A/F.lean` | `x` |\n")
    np = os.path.join(d, "n.md")
    open(np, "w").write(note)
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = check_note(os.path.join(d, "src"), np)
    out = buf.getvalue()
    ok = (rc == 1 and "checked 5 / verbatim 1 / whitespace-only 1 / not found 2 / acknowledged 1" in out
          and "NOT FOUND n.md:" in out and "n = m" in out and "ACKNOWLEDGED n.md:" in out
          and "trivial2" in out.split("ACKNOWLEDGED")[1] and "trivial3" in out)
    # all-acknowledged note exits 0
    np3 = os.path.join(d, "n3.md")
    open(np3, "w").write("# t\n\n*Not verbatim; see the correction dated 2026-11-22 below.*\n\n```lean\n" + acked_bad +
                         "\n```\n\n### Correction, 2026-11-22\n\n```lean\n" + good + "\n```\n\n## Files this note was written from\n\n"
                         "| File | SHA-256 |\n|---|---|\n| `A/F.lean` | `x` |\n")
    buf3 = io.StringIO()
    with contextlib.redirect_stdout(buf3):
        rc3 = check_note(os.path.join(d, "src"), np3)
    ok = ok and rc3 == 0 and "acknowledged 1" in buf3.getvalue()
    # a note with no blocks reports checked 0 and passes
    np2 = os.path.join(d, "n2.md")
    open(np2, "w").write("# t\n\nno blocks\n")
    buf2 = io.StringIO()
    with contextlib.redirect_stdout(buf2):
        rc2 = check_note(os.path.join(d, "src"), np2)
    ok = ok and rc2 == 0 and "checked 0 / verbatim 0" in buf2.getvalue()
    print(out + buf2.getvalue(), end="")
    print("SELFTEST " + ("PASS: planted change caught, verbatim and whitespace-only classed, zero case distinct, acknowledged only with matching dated heading"
                         if ok else "FAIL"))
    return 0 if ok else 4


def _leak_check():
    """`--selftest` must leave its temporary folder EMPTY (a folder left behind by it was one more entry in /tmp per run). Two runs, each in a TMPDIR made here
    (`rh-tmp1-...`): the self-test as a child process of this file, and, in this process, the self-test with `check_note` made to raise (the failure path
    must clean too). A run whose TMPDIR starts `rh-tmp1-` is itself the child of this check and does not run it again (the recursion guard). 0 clean, 4 a
    leftover (named, at most 20) or a child that did not finish."""
    import shutil, subprocess
    if os.path.basename(tempfile.gettempdir()).startswith("rh-tmp1-"):
        return 0
    bad = []
    child, inproc = tempfile.mkdtemp(prefix="rh-tmp1-"), tempfile.mkdtemp(prefix="rh-tmp1-")
    try:
        try:
            r = subprocess.run([sys.executable, "-I", os.path.abspath(__file__), "--selftest"], env=dict(os.environ, TMPDIR=child),
                               capture_output=True, text=True, timeout=300)
            if r.returncode != 0:
                bad.append("the child self-test exited %d" % r.returncode)
        except subprocess.TimeoutExpired:
            bad.append("the child self-test timed out")
        left = sorted(os.listdir(child))
        if left:
            bad.append("self-test left %d in its TMPDIR: %s" % (len(left), ", ".join(left[:20])))
        real_run, real_dir = globals()["check_note"], tempfile.tempdir
        def boom(*args, **kw):
            raise RuntimeError("planted")
        globals()["check_note"], tempfile.tempdir = boom, inproc
        try:
            selftest()
            bad.append("a `check_note` that raises did not make the self-test raise")
        except RuntimeError:
            pass
        finally:
            globals()["check_note"], tempfile.tempdir = real_run, real_dir
        left = sorted(os.listdir(inproc))
        if left:
            bad.append("a failing self-test left %d in its TMPDIR: %s" % (len(left), ", ".join(left[:20])))
    finally:
        shutil.rmtree(child, ignore_errors=True)
        shutil.rmtree(inproc, ignore_errors=True)
    for b in bad:
        print("TMPDIR " + b)
    return 4 if bad else 0


def main(a):
    if a[1:] == ["--selftest"]:
        return selftest() or _leak_check()
    if len(a) < 3:
        print(__doc__.split("usage:")[1].strip(), file=sys.stderr)
        return 2
    if selftest_quiet() != 0:
        print("REFUSED: selftest failed; no result reported", file=sys.stderr)
        return 4
    rc = 0
    for p in a[2:]:
        rc = max(rc, check_note(a[1], p))
    return rc


def selftest_quiet():
    import io, contextlib
    with contextlib.redirect_stdout(io.StringIO()):
        return selftest()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
