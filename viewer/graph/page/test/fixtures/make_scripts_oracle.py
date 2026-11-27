#!/usr/bin/env python3
"""Writes fixtures/note-spans-scripts.json, the ORACLE for the maths face's superscripts and subscripts (note.js `scriptParts`).

The population: every distinct code span of the opening notes of the 306 files under `grh/src/New` that the page's classifier calls a formula
(`fixtures/note-spans-classes.json`, class "formula") and that holds a `^` or a `_`: 454 spans. For each, the expected structure written by
the REFERENCE BELOW, an independent implementation of the grammar G1 to G5 of note.js (it was written from the grammar's text, not from note.js's
code; the two agree on all 454, and the cases that disagreed while it was written were all faults of the reference, listed in the pull request).
An expected structure is a list of parts: a string, or ["sup" | "sub", [parts]]; a span the grammar refuses is `"expected": null` with the reason
the reference gives (the first rule that refuses it): it stays code, as typed.

  python3 make_scripts_oracle.py          write the fixture
  python3 make_scripts_oracle.py --check  compare the committed fixture with what this reference makes; prints `identical` or the first difference

Test-only. Never shipped (lives under test/). The spans are short fragments (at most 50 characters) of the repository's notes, each once, taken
from the committed fixtures/note-spans-classes.json; no whole note and no built data.
"""
import json
import os
import sys
import unicodedata

SUBDIG = "₀₁₂₃₄₅₆₇₈₉"
PRIMES = "′'’"
OPS = "*×+-∨∞⊥"
CLOSERS = ")]}"
OPEN = {"(": ")", "[": "]", "{": "}"}


def is_letter(c): return unicodedata.category(c).startswith("L")
def is_mark(c): return unicodedata.category(c).startswith("M")
def is_nd(c): return unicodedata.category(c) == "Nd"
def is_wordc(c): return is_letter(c) or is_nd(c) or c in SUBDIG or c in PRIMES


class Refuse(Exception):
    pass


def match_close(cs, i):
    """cs[i] is an opening bracket; the index of its matching close, brackets of all three kinds nested properly; Refuse on crossing or unmatched."""
    stack = []
    for j in range(i, len(cs)):
        c = cs[j]
        if c in OPEN:
            stack.append(OPEN[c])
        elif c in CLOSERS:
            if not stack or stack.pop() != c:
                raise Refuse("crossing bracket")
            if not stack:
                return j
    raise Refuse("unmatched bracket")


def base_index(cs, i, start):
    """G1: the index of the base char of the script at cs[i]; Refuse when none. For _ the char right before, for ^ the nearest non-space before."""
    p = i - 1
    if cs[i] == "^":
        while p >= start and cs[p] == " ":
            p -= 1
    if p < start:
        raise Refuse("no base")
    c = cs[p]
    if is_mark(c):
        q = p
        while q >= start and is_mark(cs[q]):
            q -= 1
        if q < start or not is_letter(cs[q]):
            raise Refuse("mark run without a letter")
        return p
    if is_letter(c) or is_nd(c) or c in SUBDIG or c in PRIMES or c in CLOSERS:
        return p
    raise Refuse("no base")


def word_before(cs, p, start):
    """The index where the run of word characters (and their marks) that ends at p begins."""
    q = p
    while q >= start and (is_wordc(cs[q]) or is_mark(cs[q])):
        q -= 1
    return q + 1


def parse(cs, depth, start=0, end=None):
    """The parts of cs[start:end] under the grammar; Refuse when it does not parse. depth = script levels already open."""
    if end is None:
        end = len(cs)
    out, buf = [], ""
    i = start
    run = None                   # the run of scripts on one base: {"base": index of the base char, "used": set of script chars, "lo": start of the last operand, "hi": index after it}
    i = start
    while i < end:
        c = cs[i]
        if c not in "^_":
            buf += c
            i += 1
            continue
        if depth >= 2:
            raise Refuse("deeper than two levels")
        b = base_index(cs, i, start)
        in_run = run is not None and run["lo"] <= b < run["hi"]
        if in_run:
            # the nearest base is the last operand of a script on the same base: the script joins that run
            if c in run["used"]:
                raise Refuse("second " + c + " on one run (a ^ b ^ c)")
            base_for_checks = run["base"]
        else:
            run = None
            base_for_checks = b
        # G4: a ^ whose base WORD follows another word or a closing bracket and a space; a base carrying a subscript: the word before its _
        if c == "^":
            pb = base_for_checks
            w0 = word_before(cs, pb, start) if (is_wordc(cs[pb]) or is_mark(cs[pb])) else None
            if w0 is not None and w0 >= start + 2 and cs[w0 - 1] == " ":
                k = w0 - 2
                while k >= start and cs[k] == " ":
                    k -= 1
                if k >= start and (is_wordc(cs[k]) or is_mark(cs[k]) or cs[k] in CLOSERS):
                    raise Refuse("juxtaposed base")
        # operand
        j = i + 1
        spaced_before_word = False
        if c == "^":
            k = j
            while k < end and cs[k] == " ":
                k += 1
            spaced = k > j
        else:
            k, spaced = j, False
        operand, nxt = None, None
        if j < end and cs[j] == "{":
            m = match_close(cs, j)
            if m >= end:
                raise Refuse("group crosses the end")
            inner = cs[j + 1:m]
            if not inner:
                raise Refuse("empty group")
            if is_mark(inner[0]):
                raise Refuse("mark after the opening brace")
            operand, nxt = parse(cs, depth + 1, j + 1, m), m + 1
        elif c == "^" and k < end and cs[k] == "(":
            m = match_close(cs, k)
            if m >= end:
                raise Refuse("group crosses the end")
            inner = cs[k + 1:m]
            if not inner:
                raise Refuse("empty group")
            if is_mark(inner[0]):
                raise Refuse("mark after the opening paren")
            operand, nxt = parse(cs, depth + 1, k + 1, m), m + 1
        elif k < end and is_wordc(cs[k]):
            e = k
            while e < end and is_wordc(cs[e]):
                e += 1
            if e < end and is_mark(cs[e]):
                raise Refuse("mark after the operand")
            if c == "^" and spaced:
                # exponent side: spaces before a WORD operand followed by spaces and a word or an opening bracket, or directly by a _
                t = e
                while t < end and cs[t] == " ":
                    t += 1
                if (t > e and t < end and (is_wordc(cs[t]) or cs[t] in "([{")) or (e < end and cs[e] == "_"):
                    raise Refuse("juxtaposed exponent")
            operand, nxt = [cs[k:e] and "".join(cs[k:e])], e
        elif j < end and cs[j] in OPS:
            e = j + 1
            if e < end and cs[e] not in " " and cs[e] not in CLOSERS:
                raise Refuse("operator operand not followed by end, space or closer")
            operand, nxt = [cs[j]], e
        else:
            raise Refuse("no operand")
        # emit
        if c == "^":
            buf = buf.rstrip(" ")
        if buf:
            out.append(buf)
            buf = ""
        out.append(("sup" if c == "^" else "sub", operand))
        if run is None:
            run = {"base": base_for_checks, "used": set(), "lo": 0, "hi": 0}
        run["used"].add(c)
        run["lo"], run["hi"] = j + 1, nxt
        i = nxt
    if buf:
        out.append(buf)
    return out


def expected_with_reason(span):
    """(tree, None) when the span is set, (None, reason) when it is left as typed; the reason is the first rule that refuses it."""
    cs = list(span)
    try:
        t = parse(cs, 0)
    except Refuse as e:
        return None, str(e)
    return norm(t), None


def expected(span):
    return expected_with_reason(span)[0]


def norm(parts):
    out = []
    for p in parts:
        if isinstance(p, str):
            if out and isinstance(out[-1], str):
                out[-1] += p
            else:
                out.append(p)
        else:
            out.append([p[0], norm(p[1])])
    return out


HERE = os.path.dirname(os.path.abspath(__file__))
CLASSES = os.path.join(HERE, "note-spans-classes.json")
FIXTURE = os.path.join(HERE, "note-spans-scripts.json")


def build():
    with open(CLASSES, encoding="utf-8") as f:
        fx = json.load(f)
    spans = {}
    for r in fx["spans"]:
        if r["class"] == "formula" and ("^" in r["span"] or "_" in r["span"]):
            spans[r["span"]] = spans.get(r["span"], 0) + r["count"]
    rows = []
    for span in sorted(spans):
        tree, reason = expected_with_reason(span)
        row = {"span": span, "count": spans[span], "expected": tree}
        if tree is None:
            row["reason"] = reason
        rows.append(row)
    return {"pin": fx["pin"], "source": fx["source"], "rule": "formula-class code spans with ^ or _; expected by the reference of make_scripts_oracle.py (grammar G1-G5 of viewer/graph/page/note.js)",
            "distinct": len(rows), "set": sum(1 for r in rows if r["expected"] is not None), "left": sum(1 for r in rows if r["expected"] is None), "spans": rows}


if __name__ == "__main__":
    made = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    if sys.argv[1:] == ["--check"]:
        with open(FIXTURE, encoding="utf-8") as f:
            have = f.read()
        if have == made:
            print("identical")
        else:
            a, b = have.split("\n"), made.split("\n")
            k = next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b)))
            print("DIFFERENT at line", k + 1, "| committed:", a[k][:80] if k < len(a) else "(end)", "| made:", b[k][:80] if k < len(b) else "(end)")
            sys.exit(1)
    else:
        with open(FIXTURE, "w", encoding="utf-8", newline="") as f:
            f.write(made)
        print("wrote", FIXTURE)
