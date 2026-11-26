#!/usr/bin/env python3
"""The one-command acceptance test of a BUILT site tree: the merge seat's check before any deploy of the Lean map.

  ~/.engram/venv/bin/python3 viewer/graph/page/test/smoke_tree.py SITE_DIR [--no-note] [--only-viewport 390x844|1280x900]

SITE_DIR is the folder a web server would serve. Either shape is accepted and the one found is printed:
  `TREE flat`     index.html beside index.json, step/, engine/, page/ at the folder's root (the Lean map assembler's)
  `TREE graph/`   graph/index.html, graph/index.json, graph/step/ (the live build's)
A folder with neither is refused with exit 2.

The tool serves SITE_DIR read-only on 127.0.0.1 (a random port) with the page browser suite's own server class, so the
Content-Security-Policy and the other headers are the suite's, never a copy. Every request, and every file the tool itself reads, is
resolved and must stay inside SITE_DIR; one that leaves it (a symlink pointing out) is a FAIL named `containment`.

In Chromium, for each viewport (390x844 mobile with touch; 1280x900):
  boot          #graph-layer visible, #graph-fallback and #graph-notice hidden, within 15 s (S1)
  console       no console error and no uncaught exception (S2)
  csp           no securitypolicyviolation event and no console line naming the Content Security Policy (S2)
  requests      no response with status >= 400 and no failed request for a file the page asked for (S2)
  csp-header    the page's own response carries the suite's Content-Security-Policy, exactly
  open-part / open-group / open-file
                ids picked FROM THE DATA (printed with the rule that picked each); opened by deep link `#<id>`: the sheet opens and
                its heading equals the card title in the step file (S3, S4)
  note          for the file: the sheet's .note-body holds the first 40 characters of THAT step's note.text, whitespace collapsed
                (A2). An absent or empty .note-body is a FAIL; no file step carries a note, or --no-note, is a SKIP, never a pass.
  scale-floor   390x844 only: after the part is opened, the engine world's rendered scale is >= index.json open_scale_floor (A3).
                No such key in the data: SKIP, never a pass. (Opened by deep link, the path every tree has; a tap on the card needs
                the engine's pointer path, which a tree without its engine cannot offer.)

The heading of a sheet is the title shown in its breadcrumb's current entry (the .crumb-here, role word left out) when the sheet has
one, else the card's own .claim line (a skeleton card says its title there). Both sides are compared as TEXT with backticks dropped
(a backtick span is a <code> element in the page) and whitespace collapsed.

Output: one line per check `PASS|FAIL|SKIP <viewport> <check> <detail>`, and a last line `SMOKE PASS` or `SMOKE FAIL (<n> failed)`.
Exit 0 only if every check passed in every viewport; 1 if any failed; 2 if SITE_DIR is neither tree shape.
When the page's fallback ran, its reason is not exposed by the page (start() returns it and nothing keeps it, and nothing is logged),
so the tool re-runs the page's own data layer (page/data.js loadIndex) in that page and prints the DataError code it gets; a refusal
that comes from a step file rather than the index is named by the failed request and the deep-link checks instead.

Never shipped (lives under test/).
"""
import json, os, re, sys, threading, time, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import test_page_browser as T  # noqa: E402  (the suite's server class and its CSP constant: the one copy)
from playwright.sync_api import sync_playwright  # noqa: E402

VIEWPORTS = {"390x844": (390, 844, True), "1280x900": (1280, 900, False)}
BOOT_TIMEOUT_MS = 15000
OUTSIDE = []                      # every request path or tool read that resolved outside SITE_DIR
LINES = []
FAILED = [0]


def out(kind, vp, check, detail=""):
    if kind == "FAIL":
        FAILED[0] += 1
    LINES.append(kind)
    print(("%s %s %s %s" % (kind, vp, check, detail)).rstrip(), flush=True)


def collapse(s):
    return re.sub(r"\s+", " ", s or "").strip()


def plain(s):
    """A title or heading as text: backticks dropped (the page draws a span as <code>), whitespace collapsed."""
    return collapse((s or "").replace("`", ""))


def inside(root_real, path):
    real = os.path.realpath(path)
    return real == root_real or real.startswith(root_real + os.sep)


class Contained(Exception):
    pass


def tree_shape(site):
    for sub, name in (("", "flat"), ("graph", "graph/")):
        d = os.path.join(site, sub) if sub else site
        if os.path.isfile(os.path.join(d, "index.html")) and os.path.isfile(os.path.join(d, "index.json")):
            return sub, name
    return None, None


class SmokeHandler(T.Handler):
    """The suite's own handler (its headers come from its end_headers), plus: a request whose path resolves outside the root is refused."""
    def do_GET(self):
        path = self.path.split("?")[0].split("#")[0]
        if not inside(self.root_real, self.translate_path(path)):
            OUTSIDE.append(path)
            self.send_error(403)
            return
        super().do_GET()


def serve(site):
    import http.server
    root = os.path.abspath(site)
    h = type("H", (SmokeHandler,), {"root": root, "root_real": os.path.realpath(root)})
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, "http://127.0.0.1:%d/" % srv.server_address[1]


def read_json(site, rel):
    p = os.path.join(site, rel)
    if not inside(os.path.realpath(site), p):
        OUTSIDE.append(rel)
        raise Contained(rel)
    with open(p, encoding="utf-8") as f:
        return json.load(f)


class View:
    """One page in one viewport with its console, failed requests and CSP events collected into the viewport's shared lists."""
    def __init__(self, browser, url, vp, shared):
        w, h, mobile = VIEWPORTS[vp]
        self.ctx = browser.new_context(viewport={"width": w, "height": h}, is_mobile=mobile, has_touch=mobile, device_scale_factor=1)
        self.page = self.ctx.new_page()
        self.shared, self.url = shared, url
        self.page.on("console", lambda m: shared["console"].append(m.text) if m.type == "error" else None)
        self.page.on("pageerror", lambda e: shared["console"].append("uncaught: " + str(e)))
        self.page.on("response", lambda r: shared["requests"].append("%d %s" % (r.status, r.url)) if r.status >= 400 else None)
        self.page.on("requestfailed", lambda r: shared["requests"].append("failed %s (%s)" % (r.url, r.failure)))
        self.cdp = self.ctx.new_cdp_session(self.page)
        self.page.add_init_script("window.__csp = []; document.addEventListener('securitypolicyviolation', "
                                  "e => window.__csp.push(e.violatedDirective + ' ' + e.blockedURI));")
        self.response = self.page.goto(url)

    def ev(self, expr):
        r = self.cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in r:
            raise RuntimeError("page threw: " + json.dumps(r["exceptionDetails"])[:300])
        return r["result"].get("value")

    def wait(self, expr, timeout_ms):
        waited = 0
        while waited <= timeout_ms:
            try:
                if self.ev("!!(" + expr + ")"):
                    return True
            except RuntimeError:        # the page is mid-load or its DOM is not as the shell promises: not yet
                pass
            self.page.wait_for_timeout(50)
            waited += 50
        return False

    def close(self):
        self.ctx.close()


BOOTED = ("(() => { const l = document.getElementById('graph-layer'), f = document.getElementById('graph-fallback'), n = document.getElementById('graph-notice');"
          " return !!l && !l.hidden && l.getBoundingClientRect().width > 0 && !!f && f.hidden && !!n && n.hidden; })()")
SETTLED = "(" + BOOTED + " || !document.getElementById('graph-layer'))"       # booted, or the fallback removed the layer: no need to wait the rest


def diagnose(v):
    """The page keeps no record of why its fallback ran; re-run its own data layer on the index to get the DataError code."""
    try:
        return v.ev("""(async () => { try { const m = await import(new URL('page/data.js', location.href.split('#')[0]).href);
            await m.createData((a) => fetch(a)).loadIndex(); return 'the index validates; the refusal is not in the index'; }
            catch (e) { return (e && e.code ? e.code : 'no code') + ': ' + (e && e.message ? e.message : String(e)).slice(0, 160); } })()""")
    except Exception as e:  # noqa: BLE001
        return "diagnosis failed: " + repr(e)[:120]


def pick_ids(site, index, no_note):
    """S3: ids FROM THE DATA. Returns (part, group, file) as dicts {id, title, rule, note} and prints them."""
    top = index["top"]
    part = top[0]
    pstep = read_json(site, "step/%s.json" % part)
    kids = pstep["children"]
    if not kids:
        raise ValueError("the part %s has no children" % part)
    nonfile = [c for c in kids if c.get("kind") != "file"]
    gchild = nonfile[0] if nonfile else kids[0]
    grule = "first child of the part whose kind is not file" if nonfile else "first child of the part (every child is a file)"
    ids = sorted(f[:-5] for f in os.listdir(os.path.join(site, "step")) if f.endswith(".json"))
    steps = {i: read_json(site, "step/%s.json" % i) for i in ids}
    files = [i for i in ids if steps[i]["card"].get("kind") == "file"]
    frule_base = "file step"
    if not files:
        files = [i for i in ids if steps[i]["card"].get("child_count") == 0]
        frule_base = "leaf step"
    if not files:
        raise ValueError("no file step and no leaf step in the data")
    with_note = [i for i in files if isinstance(steps[i].get("note"), dict) and steps[i]["note"].get("text")]
    if with_note and not no_note:
        fid, frule = with_note[0], "first %s in step-id order that carries note" % frule_base
    else:
        fid, frule = files[0], "first %s in step-id order%s" % (frule_base, " (--no-note)" if no_note else " (none carries note)")
    picked = (
        {"id": part, "title": pstep["card"]["title"], "rule": "first id of index top"},
        {"id": gchild["id"], "title": gchild["title"], "rule": grule},
        {"id": fid, "title": steps[fid]["card"]["title"], "rule": frule, "note": steps[fid].get("note") if not no_note else None},
    )
    for what, p in zip(("part", "group", "file"), picked):
        print("ID %s %s (%s)" % (what, p["id"], p["rule"]), flush=True)
    return picked


def open_check(v, vp, what, p):
    """S4: the sheet opens on the deep link and its heading is the card's title."""
    ok = v.wait("!(document.getElementById('graph-sheet') || {hidden: true}).hidden && document.querySelector('#graph-sheet-body article')?.id === %s" % json.dumps(p["id"]), 10000)
    check = "open-" + what
    if not ok:
        state = v.ev("""(() => ({sheet: !!document.getElementById('graph-sheet') && !document.getElementById('graph-sheet').hidden, shown: (document.querySelector('#graph-sheet-body article')||{}).id || null,
          fallback: !!document.getElementById('graph-fallback') && !document.getElementById('graph-fallback').hidden, notice: (document.getElementById('graph-notice')||{}).textContent || ''}))()""")
        out("FAIL", vp, check, "#%s: the sheet did not open (%s)" % (p["id"], json.dumps(state)))
        return False
    head = v.ev("""(() => { const c = document.querySelector('#graph-sheet .crumb-here');
        if (c) { const k = c.cloneNode(true); k.querySelectorAll('.crumb-role').forEach((e) => e.remove()); return {from: 'crumb', text: k.textContent}; }
        const q = document.querySelector('#graph-sheet-body .claim'); return {from: 'claim', text: q ? q.textContent : ''}; })()""")
    if plain(head["text"]) != plain(p["title"]):
        out("FAIL", vp, check, "#%s: heading %r (%s) is not the card title %r" % (p["id"], collapse(head["text"]), head["from"], collapse(p["title"])))
        return False
    out("PASS", vp, check, "#%s heading %r" % (p["id"], plain(head["text"])))
    return True


def note_check(v, vp, p, no_note):
    n = p.get("note")
    if no_note:
        out("SKIP", vp, "note", "(--no-note)")
        return
    if not n:
        out("SKIP", vp, "note", "(no file step carries note)")
        return
    want = collapse(n["text"])[:40]
    got = v.ev("(() => { const b = document.querySelector('#graph-sheet-body .note-body'); return b ? b.textContent : null; })()")
    if got is None:
        out("FAIL", vp, "note", "#%s carries a note but the sheet has no .note-body" % p["id"])
    elif collapse(got) == "":
        out("FAIL", vp, "note", "#%s: the sheet's .note-body is empty" % p["id"])
    elif want not in collapse(got):
        out("FAIL", vp, "note", "#%s: .note-body does not contain %r" % (p["id"], want))
    else:
        out("PASS", vp, "note", "#%s .note-body holds %r" % (p["id"], want))


def scale_check(v, vp, index):
    if "open_scale_floor" not in index:
        out("SKIP", vp, "scale-floor", "(not in data)")
        return
    floor = index["open_scale_floor"]
    v.page.wait_for_timeout(900)           # the engine's camera settles after the open
    k = v.ev("""(() => { const w = document.querySelector('.ge-world'); if (!w) return null;
        const m = /scale\\(([-0-9.e]+)\\)/.exec(w.getAttribute('style') || ''); return m ? parseFloat(m[1]) : null; })()""")
    if k is None:
        out("FAIL", vp, "scale-floor", "no .ge-world with a scale() to read (via deep link)")
    elif k + 1e-9 < floor:
        out("FAIL", vp, "scale-floor", "world scale %.3f < open_scale_floor %s (part opened by deep link)" % (k, floor))
    else:
        out("PASS", vp, "scale-floor", "world scale %.3f >= open_scale_floor %s (part opened by deep link)" % (k, floor))


def run_viewport(browser, vp, base, site, index, picked, no_note):
    shared = {"console": [], "requests": []}
    csp_events = []
    boot = View(browser, base, vp, shared)
    booted = boot.wait(SETTLED, BOOT_TIMEOUT_MS) and boot.ev(BOOTED)
    if booted:
        out("PASS", vp, "boot", "#graph-layer visible, #graph-fallback and #graph-notice hidden")
    else:
        st = boot.ev("""(() => { const g = (i) => document.getElementById(i); return {layer: !!g('graph-layer') && !g('graph-layer').hidden,
          fallback: !!g('graph-fallback') && !g('graph-fallback').hidden, notice: !!g('graph-notice') && !g('graph-notice').hidden}; })()""")
        out("FAIL", vp, "boot", "%s; page's refusal re-run through its own data layer: %s" % (json.dumps(st), diagnose(boot)))
    boot.page.wait_for_timeout(300)
    csp_events += boot.ev("window.__csp || []") or []
    hdr = boot.response.headers.get("content-security-policy") if boot.response else None
    if hdr == T.CSP:
        out("PASS", vp, "csp-header", hdr)
    else:
        out("FAIL", vp, "csp-header", "the page's response carries %r, not the suite's policy" % hdr)
    boot.close()
    names = ("part", "group", "file")
    for what, p in zip(names, picked):
        v = View(browser, base + "#" + p["id"], vp, shared)
        opened = open_check(v, vp, what, p)
        if what == "file" and opened:
            note_check(v, vp, p, no_note)
        elif what == "file":
            if not no_note and p.get("note"):
                out("FAIL", vp, "note", "#%s: the sheet did not open, so its note was not checked" % p["id"])
            else:
                note_check(v, vp, p, no_note)
        if what == "part" and vp == "390x844":
            scale_check(v, vp, index)
        v.page.wait_for_timeout(200)
        csp_events += v.ev("window.__csp || []") or []
        v.close()
    cons = [c for c in shared["console"] if "Content Security Policy" not in c]
    cspc = [c for c in shared["console"] if "Content Security Policy" in c] + csp_events
    out("FAIL" if cons else "PASS", vp, "console", "; ".join(cons)[:300] if cons else "no console error, no uncaught exception")
    out("FAIL" if cspc else "PASS", vp, "csp", "; ".join(cspc)[:300] if cspc else "no securitypolicyviolation")
    out("FAIL" if shared["requests"] else "PASS", vp, "requests", "; ".join(shared["requests"])[:300] if shared["requests"] else "no response >= 400, no failed request")


def main(argv):
    args = argv[1:]
    only = None
    if "--only-viewport" in args:
        i = args.index("--only-viewport")
        only = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
        if only not in VIEWPORTS:
            print("--only-viewport takes 390x844 or 1280x900", file=sys.stderr)
            return 2
    no_note = "--no-note" in args
    args = [a for a in args if a != "--no-note"]
    if len(args) != 1 or args[0].startswith("-"):
        print("usage: smoke_tree.py SITE_DIR [--no-note] [--only-viewport 390x844|1280x900]", file=sys.stderr)
        return 2
    site = os.path.abspath(args[0])
    sub, shape = tree_shape(site)
    if shape is None:
        print("SMOKE REFUSED: %s holds neither index.html + index.json (flat) nor graph/index.html + graph/index.json" % site)
        return 2
    print("TREE " + shape, flush=True)
    base_dir = os.path.join(site, sub) if sub else site
    try:
        index = read_json(site, os.path.join(sub, "index.json") if sub else "index.json")
        picked = pick_ids(base_dir, index, no_note)
    except Contained as e:
        out("FAIL", "all", "containment", "the tool's own read of %s leaves SITE_DIR" % e)
        print("SMOKE FAIL (%d failed)" % FAILED[0])
        return 1
    except Exception as e:  # noqa: BLE001
        out("FAIL", "all", "ids", "the data does not give a part, a group and a file: %r" % (e,))
        print("SMOKE FAIL (%d failed)" % FAILED[0])
        return 1
    srv, host = serve(site)
    base = host + (sub + "/" if sub else "")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=T.SHELL[0]) if T.SHELL else p.chromium.launch()
            for vp in ([only] if only else list(VIEWPORTS)):
                run_viewport(browser, vp, base, base_dir, index, picked, no_note)
            browser.close()
    finally:
        srv.shutdown()
    if OUTSIDE:
        out("FAIL", "all", "containment", "request outside SITE_DIR refused: " + ", ".join(sorted(set(OUTSIDE)))[:300])
    else:
        out("PASS", "all", "containment", "every request and read stayed inside SITE_DIR")
    print("SMOKE PASS" if FAILED[0] == 0 else "SMOKE FAIL (%d failed)" % FAILED[0])
    return 0 if FAILED[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
