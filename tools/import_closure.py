#!/usr/bin/env python3
"""Import closure of one Lean module inside the release's lean/src. Read-only unless OUT is given.

usage: import_closure.py SRC_ROOT Module.Name [OUT.txt]

It follows the `import X` lines at the head of each file, transitively. A module with no file under
SRC_ROOT (Mathlib, Lean core, Batteries) is counted as external and not followed.

WHAT THE NUMBER MEANS. The closure is every file that must be compiled before the start module. It is
an UPPER BOUND on what the start module's proofs use: a file may import more than its proofs need.
It says nothing about which declarations are used. With OUT, the closure is written one module per line.
"""

import sys
if sys.version_info[:2] < (3, 12):
    raise SystemExit("import_closure.py: needs Python 3.12 or newer (tested with 3.12); this is %d.%d.%d at %s" % (sys.version_info[0], sys.version_info[1], sys.version_info[2], sys.executable))

import collections, os, sys


def path(root, m):
    return os.path.join(root, *m.split(".")) + ".lean"


def imports(p):
    with open(p, encoding="utf-8") as f:
        text = f.read()
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)
    import scan_graph
    return scan_graph.header_imports(text)


def closure(root, start):
    seen, ext, stack = {start}, collections.Counter(), [start]
    while stack:
        for i in imports(path(root, stack.pop())):
            if os.path.isfile(path(root, i)):
                if i not in seen:
                    seen.add(i)
                    stack.append(i)
            else:
                ext[i.split(".")[0]] += 1
    # An "external" import whose first component is a folder or file of the release itself is a
    # release module that did not resolve to a file; following it silently would under-count.
    own = {n[:-5] if n.endswith(".lean") else n for n in os.listdir(root)}
    lost = sorted(k for k in ext if k in own)
    if lost:
        raise SystemExit(f"unresolved imports under release folders {lost}: closure would be under-counted")
    return seen, ext


def main(a):
    if len(a) < 3:
        print(__doc__.split("usage:")[1].split("\n")[0].strip(), file=sys.stderr)
        return 2
    root, start = a[1], a[2]
    if not os.path.isfile(path(root, start)):
        print(f"no file for module {start} under {root}", file=sys.stderr)
        return 2
    seen, ext = closure(root, start)
    total = sum(1 for _, _, fs in os.walk(root) for f in fs if f.endswith(".lean"))
    print(f"{start}: {len(seen)} modules in closure, of {total} .lean files under the root; "
          f"external import roots: {dict(ext.most_common(4))}")
    top = collections.Counter(m.split(".")[0] for m in seen)
    for k, n in sorted(top.items(), key=lambda kv: -kv[1]):
        print(f"  {n:7d}  {k}")
    if len(a) > 3:
        with open(a[3], "w") as f:
            f.write("\n".join(sorted(seen)) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
