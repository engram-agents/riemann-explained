#!/usr/bin/env python3
"""Run the fields/uses classifier against controls/expected.json, and the mutation check.

Usage: run_controls.py --root DIR [--mutate i|ii|iii|iv] [--mutation-check]
  DIR is a prebuilt release tree: it holds elan/toolchains/<toolchain>/, the release's build/ folder,
  and mathlib4/ with its .lake build. The root can also be given as RH_LEAN_ROOT in the environment.
Compiles controls/Controls.lean into controls/build/ (the caller's folder), then runs the tool.
Exit 0 only if every case passes (or, with --mutation-check, every planted bug fails exactly the cases it must).
Never calls lake. Writes nothing under DIR.
"""
import glob, hashlib, json, os, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
R = None
CTRL_BUILD = os.path.join(HERE, "controls", "build")


CAP = ["systemd-run", "--user", "--scope", "-q", "-p", "MemoryMax=10G", "-p", "MemorySwapMax=0", "nice", "-n", "15"]


def lean_env():
    tcs = sorted(glob.glob(f"{R}/elan/toolchains/*/"))
    if len(tcs) != 1:
        raise SystemExit(f"expected exactly one toolchain under {R}/elan/toolchains/, found {len(tcs)}")
    tc = tcs[0]
    lp = [CTRL_BUILD, f"{R}/build", f"{R}/mathlib4/.lake/build/lib/lean"]
    lp += sorted(glob.glob(f"{R}/mathlib4/.lake/packages/*/.lake/build/lib/lean"))
    env = dict(os.environ)
    env["LEAN_PATH"] = ":".join(lp)
    env["PATH"] = tc + "bin:" + env.get("PATH", "")
    return env


def build_controls():
    os.makedirs(CTRL_BUILD, exist_ok=True)
    src = os.path.join(HERE, "controls", "Controls.lean")
    out = os.path.join(CTRL_BUILD, "Controls.olean")
    p = subprocess.run(CAP + ["lean", src, "-o", out], env=lean_env(), capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"Controls.lean did not compile: {p.stdout[-2000:]}{p.stderr[-2000:]}")


def run_tool(decls, mutate=None, follow=1, query="uses", budget=None):
    cmd = CAP + ["lean", "--run", os.path.join(HERE, "FieldsUses.lean"), "--", "--module", "Controls",
           "--follow", str(follow)]
    if mutate:
        cmd += ["--mutate", mutate]
    if budget is not None:
        cmd += ["--budget", str(budget)]
    cmd += [query] + decls
    p = subprocess.run(cmd, env=lean_env(), capture_output=True, text=True)
    if p.returncode != 0:
        raise SystemExit(f"tool exit {p.returncode}: {p.stderr[-2000:]}")
    # `lean --run` prints the tool's own compile warnings first; the JSON starts at the first line opening with { or [
    lines = p.stdout.splitlines()
    start = next(i for i, l in enumerate(lines) if l.startswith("{") or l.startswith("["))
    out = json.loads("\n".join(lines[start:]))
    if query == "who_reads":
        return out
    if isinstance(out, dict):
        out = [out]
    return {o["decl"]: o for o in out}


def find_binder(rep, sel):
    for b in rep["binders"]:
        if (isinstance(sel, int) and b["index"] == sel) or b["name"] == sel:
            return b
    return None


def check(case, rep):
    """Return a list of failure strings (empty = pass)."""
    fails = []
    b = find_binder(rep, case["binder"])
    if b is None:
        return [f"binder {case['binder']!r} not in report"]
    labels = set(b["labels"])
    if case["query"] == "flows_into":
        if set(b["flows_into"]) != set(case["fields"]):
            fails.append(f"flows_into {b['flows_into']} != {case['fields']}")
        return fails
    if "labels" in case and labels != set(case["labels"]):
        fails.append(f"labels {sorted(labels)} != {case['labels']}")
    for bad in case.get("must_not", []):
        if bad in labels:
            fails.append(f"label {bad} present (must_not)")
    if "path" in case:
        ps = b["paths"]
        if len(ps) != 1 or case["path"] not in (ps[0]["path"], ps[0]["named"]):
            fails.append(f"paths {ps} != [{case['path']}]")
    if "named" in case:
        ps = b["paths"]
        if len(ps) != 1 or ps[0]["named"] != case["named"]:
            fails.append(f"named paths {[p['named'] for p in ps]} != [{case['named']}]")
    if "callee" in case:
        hits = [x for x in b["passed"] if x["callee"] == case["callee"]]
        if not hits:
            fails.append(f"no passed occurrence to {case['callee']} (passed: {b['passed']})")
        elif "pos" in case and not any(x["pos"] == case["pos"] for x in hits):
            fails.append(f"callee {case['callee']} at pos {[x['pos'] for x in hits]} != {case['pos']}")
    if "must_not_callee" in case and any(x["callee"] == case["must_not_callee"] for x in b["passed"]):
        fails.append(f"reported as passed to {case['must_not_callee']} (must be followed instead)")
    for f in case.get("followed", []):
        if f not in rep["followed"]:
            fails.append(f"auxiliary {f} not followed (followed: {rep['followed']})")
    if "follow1" in case:
        fl = [x for x in b["follow"] if x.get("callee") == case.get("callee")]
        if not fl or fl[0].get("labels") != [case["follow1"]]:
            fails.append(f"follow 1 at {case.get('callee')}: {fl} != labels [{case['follow1']}]")
    return fails


def check_who_reads(case, out):
    readers = {r["decl"] for r in out.get("readers", [])}
    fails = [f"{n} missing from readers" for n in case.get("readers_include", []) if n not in readers]
    fails += [f"{n} wrongly listed as a reader" for n in case.get("readers_exclude", []) if n in readers]
    return fails


def check_budget(case, out):
    rep = out[case["decl"]]
    fails = []
    if rep.get("complete") is not case["expect_complete"]:
        fails.append(f"complete={rep.get('complete')!r}, expected {case['expect_complete']!r}")
    if "no_binder_label" in case:
        bad = [b["name"] for b in rep["binders"] if case["no_binder_label"] in b["labels"]]
        if bad:
            fails.append(f"binders {bad} labelled {case['no_binder_label']!r} on an incomplete walk")
    if not any(case["note_contains"] in n for n in rep.get("notes", [])):
        fails.append(f"no note mentioning {case['note_contains']!r} (notes: {rep.get('notes')})")
    return fails


def run_all(mutate=None):
    exp = json.load(open(os.path.join(HERE, "controls", "expected.json")))
    have = hashlib.sha256(open(os.path.join(HERE, "controls", "Controls.lean"), "rb").read()).hexdigest()
    if have != exp["controls_sha256"]:
        raise SystemExit(f"Controls.lean sha256 {have[:12]} does not match expected.json controls_sha256 "
                         f"{exp['controls_sha256'][:12]}: the controls changed without their expectations")
    uses = [c for c in exp["cases"] if c["query"] in ("uses", "flows_into")]
    reps = run_tool(sorted({c["decl"] for c in uses}), mutate)
    results = {}
    for c in exp["cases"]:
        try:
            if c["query"] in ("uses", "flows_into"):
                results[c["id"]] = check(c, reps[c["decl"]])
            elif c["query"] == "who_reads":
                results[c["id"]] = check_who_reads(c, run_tool([c["field"]], mutate, follow=0, query="who_reads"))
            elif c["query"] == "budget":
                results[c["id"]] = check_budget(c, run_tool([c["decl"]], mutate, follow=0, budget=c["budget"]))
            else:
                results[c["id"]] = [f"unknown query {c['query']!r}"]
        except SystemExit as e:
            results[c["id"]] = [f"tool failed: {str(e)[:300]}"]
    return exp, results


def main():
    global R
    args = sys.argv[1:]
    if "--root" in args and args.index("--root") + 1 >= len(args):
        raise SystemExit("--root needs a directory")
    if "--mutate" in args and args.index("--mutate") + 1 >= len(args):
        raise SystemExit("--mutate needs i, ii, iii or iv")
    R = args[args.index("--root") + 1] if "--root" in args else os.environ.get("RH_LEAN_ROOT")
    if not R or not os.path.isdir(R):
        raise SystemExit("give the prebuilt tree with --root DIR or RH_LEAN_ROOT (see the docstring)")
    build_controls()
    if "--mutation-check" in args:
        exp, base = run_all()
        ok = not any(base.values())
        print(f"baseline: {sum(1 for v in base.values() if not v)}/{len(base)} pass")
        for k, v in base.items():
            if v:
                print(f"  FAIL {k}: {'; '.join(v)}")
        for m in exp["mutation_check"]:
            bug = m["id"]
            _, res = run_all(bug)
            failed = sorted(k for k, v in res.items() if v)
            want = sorted(m["must_fail_exactly"])
            good = failed == want
            ok = ok and good
            print(f"bug ({bug}) {m['bug']}: failed {failed}; expected exactly {want}: {'OK' if good else 'MISMATCH'}")
            for k in failed:
                print(f"    {k}: {'; '.join(res[k])}")
        sys.exit(0 if ok else 1)
    mutate = args[args.index("--mutate") + 1] if "--mutate" in args else None
    _, res = run_all(mutate)
    for k, v in res.items():
        print(f"{'ok  ' if not v else 'FAIL'} {k}" + ("" if not v else ": " + "; ".join(v)))
    n = sum(1 for v in res.values() if not v)
    print(f"{n}/{len(res)} pass")
    sys.exit(0 if n == len(res) else 1)


if __name__ == "__main__":
    main()
