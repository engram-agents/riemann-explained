#!/usr/bin/env python3
"""The text rule for reading Lean declarations: the regexes and `parse_decls`, shared by the tools that read them."""
import re


DECL_QUICK = re.compile(r"\b(?:theorem|lemma|def|abbrev|structure|class|inductive|instance)\b")
DECL = re.compile(r"[ \t]*(?:@\[[^\]]*\][ \t]*)*(?:(?:private|protected|noncomputable|nonrec|unsafe|partial)[ \t]+)*"
                  r"(theorem|lemma|def|abbrev|structure|class|inductive|instance)[ \t]+([^\s:({\[]*)")
BOUND = re.compile(r"(?:(?:theorem|lemma|def|abbrev|structure|class|inductive|instance|end|namespace|section|open|"
                   r"set_option|attribute|variable|universe|noncomputable|private|protected|nonrec|unsafe|partial|mutual|"
                   r"example|axiom|opaque|macro|syntax|notation|local|scoped|export|deriving|initialize)"
                   r"(?![\w'.])|@\[|#(?:check|print|eval)(?![\w'.]))")
NS = re.compile(r"namespace[ \t]+(\S+)")
SEC = re.compile(r"(?:noncomputable[ \t]+)?section(?:[ \t]+(\S+))?[ \t]*$")
END = re.compile(r"end(?:[ \t]+(\S+))?[ \t]*$")
MUT = re.compile(r"mutual[ \t]*$")


def parse_decls(raw, masked):
    """[(line_no, kind, full_name, end_idx, namespaces)] for every declaration with a name. Structure comes from
    the masked text; end_idx is the 0-based index of the first line after the declaration's extent; namespaces
    is the tuple of enclosing namespace components at the declaration (a `_root_.` in its own name does not
    change it)."""
    if not DECL_QUICK.search(masked):
        return []
    ml, rl = masked.split("\n"), raw.split("\n")
    n = len(ml)
    nxt = [n] * (n + 1)
    for k in range(n - 1, -1, -1):
        m = ml[k]
        is_b = bool(m) and m[0] not in " \t" and BOUND.match(m) is not None
        nxt[k] = k if (is_b or rl[k].startswith("/-")) else nxt[k + 1]
    stack, found = [], []
    for k in range(n):
        line = ml[k]
        if not line.strip():
            continue
        if line[0] not in " \t":
            m = NS.match(line)
            if m:
                stack.extend(("namespace", c) for c in m.group(1).split("."))
                continue
            m = SEC.match(line)
            if m:
                stack.append(("section", m.group(1)))
                continue
            if MUT.match(line):
                stack.append(("section", None))
                continue
            m = END.match(line)
            if m:
                want = m.group(1)
                if want is None:
                    if stack and stack[-1][0] == "section":
                        stack.pop()
                else:
                    del stack[max(0, len(stack) - len(want.split("."))):]
                continue
        m = DECL.match(line)
        if not m:
            continue
        name = m.group(2).rstrip(".")
        if not name:
            continue
        if name.startswith("_root_."):
            full = name[len("_root_."):]
        else:
            prefix = ".".join(nm for kind, nm in stack if kind == "namespace")
            full = prefix + "." + name if prefix else name
        found.append((k + 1, m.group(1), full, nxt[k + 1], tuple(nm for kind, nm in stack if kind == "namespace")))
    return found
