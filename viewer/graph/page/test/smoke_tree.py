#!/usr/bin/env python3
"""The one-command acceptance test of a BUILT site tree: the merge seat's check before any deploy of the Lean map.

  python3 viewer/graph/page/test/smoke_tree.py SITE_DIR [--no-note | --require-note] [--require-floor] [--require-credits] [--only-viewport 390x844|1280x900]
  (run it with a Python that has playwright; the module itself imports without one, so the containment cases of test_smoke_tree.py
  run on any Python 3: `python3 test_smoke_tree.py --no-browser`)

SITE_DIR is the folder a web server would serve. Either shape is accepted and the one found is printed:
  `TREE flat`     index.html beside index.json, step/, engine/, page/ at the folder's root (the Lean map assembler's)
  `TREE graph/`   graph/index.html, graph/index.json, graph/step/ (the live build's)
A folder with neither is refused with exit 2.

The tool serves SITE_DIR read-only on 127.0.0.1 (a random port) with the page browser suite's own server class, so the
Content-Security-Policy and the other headers are the suite's, never a copy. Every file the server sends (GET and HEAD share one open
function) is the file whose real path was resolved and checked just before it was opened, after the stdlib chose any directory index, so a
`/d/` that serves a linked-out index.html is caught; every file the tool itself reads is checked the same way. One that leaves SITE_DIR
(a symlink pointing out) is a FAIL named `containment`. A directory is never listed (403).

In Chromium, for each viewport (390x844 mobile with touch; 1280x900):
  boot          #graph-layer visible, #graph-fallback and #graph-notice hidden, within 15 s (S1)
  console       no console error and no uncaught exception (S2)
  csp           no securitypolicyviolation event and no console line naming the Content Security Policy (S2)
  requests      no response with status >= 400 and no failed request for a file the page asked for (S2)
  csp-header    the page's own response carries the suite's Content-Security-Policy, exactly. This compares the header with T.CSP on the
                suite's OWN server, which writes T.CSP itself, so it cannot fail: it says what it is ('the harness sends the suite's policy').
                The real CSP coverage is the console and securitypolicyviolation checks, valid only while T.CSP equals the deployed policy
                (the host's headers for the page; compare them when either changes).
  open-part / open-group / open-file
                ids picked FROM THE DATA (printed with the rule that picked each); opened by deep link `#<id>`: the sheet opens on that step
                and its heading equals the card title in the step file (S3, S4). The sheet is on that step when its body holds the markup's
                `article#<id>`, OR a card the page made from the data: the body's single child is a `.card` whose `.claim` is the step's
                card title (backticks dropped, whitespace collapsed).
  note          for the file: the sheet's .note-body contains the first 30 letters and digits of THAT step's note.text, both sides lowercased
                and cut to letters and digits (the renderer drops markdown markers: a leading '# ', backticks, list marks) (A2). An absent or empty .note-body is a FAIL; no file step carries a note, or --no-note, is a SKIP, never a pass
                (and a FAIL with --require-note: the merge seat's run that must have the real check).
  scale-floor   390x844 only: after the part is opened, the engine world's rendered scale is >= index.json open_scale_floor (A3).
                No such key in the data: SKIP, never a pass (a FAIL with --require-floor, which is a usage error, exit 2, with --only-viewport 1280x900: the floor runs at 390x844 only). (Opened by deep link, the path every tree has; a tap on the card needs
                the engine's pointer path, which a tree without its engine cannot offer.)

  credits       if SITE_DIR holds credits/index.html: at 1280x900 it answers 200, its console and requests are clean, and a link ON THE PAGE
                (read from the page, never guessed) resolves to the map's index (the folder of the tree's index.html) and that loads and boots.
                No credits/ in the tree: SKIP `credits (no credits/ in tree)`, a FAIL with --require-credits. Visited whichever viewport was asked for.

The heading of a sheet is the title shown in its breadcrumb's current entry (the .crumb-here, role word left out) when the sheet has
one, else the card's own .claim line (a skeleton card says its title there). Both sides are compared as TEXT with backticks dropped
(a backtick span is a <code> element in the page) and whitespace collapsed. An empty heading, or an empty card title, is a FAIL.

Output: one line per check `PASS|FAIL|SKIP <viewport> <check> <detail>`, a line `INFO all opened N of M steps` (N distinct steps the deep links
really opened, M the index's step count: one part, one group and one file are opened, not the tree), and a last line `SMOKE FAIL (<n> failed)` or
`SMOKE PASS`. An exception in a viewport, or anywhere after the server is up, prints `FAIL <viewport> exception <type>: <first line of the message>`
and the run still ends on the verdict line and exits 1.
The PASS line names what the run did not do: `SMOKE PASS (2 skipped: note, scale-floor)` when any check skipped, `(partial: 390x844 only)`
with --only-viewport, the two joined by `;`. A plain `SMOKE PASS` means a whole run with nothing skipped.
Exit 0 only if every check passed in every viewport; 1 if any failed; 2 if SITE_DIR is neither tree shape, or on a usage error.
When the page's fallback ran, its reason is not exposed by the page (start() returns it and nothing keeps it, and nothing is logged),
so the tool re-runs the page's own data layer (page/data.js loadIndex) in that page and prints the DataError code it gets; a refusal
that comes from a step file rather than the index is named by the failed request and the deep-link checks instead.

Never shipped (lives under test/).
"""
import json, os, re, sys, threading, time, types, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
try:
    import playwright.sync_api  # noqa: F401
except ImportError:
    # No playwright in this Python: the server and its containment need none, and the suite module imports it at the top. A stand-in whose
    # sync_playwright() raises keeps the import working; a run that needs the browser then ends in `FAIL all exception RuntimeError: ...`.
    def _no_playwright():
        raise RuntimeError("playwright is not installed in this Python: the browser checks need one that has it")
    _pkg, _api = types.ModuleType("playwright"), types.ModuleType("playwright.sync_api")
    _api.sync_playwright = _no_playwright
    _pkg.sync_api = _api
    sys.modules["playwright"], sys.modules["playwright.sync_api"] = _pkg, _api
import test_page_browser as T  # noqa: E402  (the suite's server class and its CSP constant: the one copy)
from playwright.sync_api import sync_playwright  # noqa: E402

LAUNCH_ARGS = ["--no-sandbox"]       # the page browser suite's own launch args (its main() writes them inline, so they are copied here)
VIEWPORTS = {"390x844": (390, 844, True), "1280x900": (1280, 900, False)}
BOOT_TIMEOUT_MS = 15000
OPEN_TIMEOUT_MS = 10000
OUTSIDE = []                      # every request path or tool read that resolved outside SITE_DIR
FAILED = [0]
SKIPPED = []                      # the check name of every SKIP, once each (the verdict line sorts them)
OPENED = set()                    # the step ids the deep links really opened (an open-* check that passed), in any viewport


def out(kind, vp, check, detail=""):
    if kind == "FAIL":
        FAILED[0] += 1
    if kind == "SKIP" and check not in SKIPPED:
        SKIPPED.append(check)
    print(("%s %s %s %s" % (kind, vp, check, detail)).rstrip(), flush=True)


def skip_or_fail(vp, check, why, required, flag):
    """A check that cannot run: a SKIP, or a FAIL when the run was told (by `flag`) that this check must happen."""
    if required:
        out("FAIL", vp, check, "%s (%s: the check is required)" % (why, flag))
    else:
        out("SKIP", vp, check, "(%s)" % why)


def verdict(failed, skipped, only):
    """The last line. FAIL names the count; PASS names what the run did not do, so a partial or skipping run cannot read as a whole one."""
    if failed:
        return "SMOKE FAIL (%d failed)" % failed
    notes = []
    if only:
        notes.append("partial: %s only" % only)
    if skipped:
        notes.append("%d skipped: %s" % (len(skipped), ", ".join(sorted(skipped))))
    return "SMOKE PASS" + (" (%s)" % "; ".join(notes) if notes else "")


def csp_header_check(vp, hdr):
    """The one line about the page's Content-Security-Policy header. It compares with T.CSP on a server that writes T.CSP itself, so it says that."""
    if hdr == T.CSP:
        out("PASS", vp, "csp-header", "the harness sends the suite's policy: " + hdr)
    else:
        out("FAIL", vp, "csp-header", "the page's response carries %r, not the suite's policy" % hdr)


def opened_line(opened, total):
    """How much of the tree the run opened: distinct steps opened of the steps the index says it has (`?` when it says none)."""
    return "opened %d of %s steps" % (len(opened), total if total is not None else "?")


def exception_detail(e):
    """`<type>: <first line of the message>` with control characters escaped, so one exception is one line a wrapper can read."""
    first = (str(e).splitlines() or [""])[0]
    return "%s: %s" % (type(e).__name__, first.encode("unicode_escape").decode("ascii"))


def collapse(s):
    return re.sub(r"\s+", " ", s or "").strip()


def letters_digits(s):
    """A note as it survives rendering: lowercase, letters and digits only (the renderer drops '# ', backticks, list marks and re-wraps the lines)."""
    return "".join(c for c in (s or "").lower() if c.isalnum())


def plain(s):
    """A title or heading as text: backticks dropped (the page draws a span as <code>), whitespace collapsed."""
    return collapse((s or "").replace("`", ""))


def reset_state():
    """Module state of one run, cleared in place (main calls this first, so a second run in one process starts clean)."""
    OUTSIDE.clear()
    SKIPPED.clear()
    OPENED.clear()
    FAILED[0] = 0


def inside(root_real, path):
    real = os.path.realpath(path)
    try:
        return os.path.commonpath([root_real, real]) == root_real       # component-wise: /x/site2 is not inside /x/site
    except ValueError:                                                  # a different drive, or a mix of absolute and relative
        return False


class Contained(Exception):
    pass


def tree_shape(site):
    for sub, name in (("", "flat"), ("graph", "graph/")):
        d = os.path.join(site, sub) if sub else site
        if os.path.isfile(os.path.join(d, "index.html")) and os.path.isfile(os.path.join(d, "index.json")):
            return sub, name
    return None, None


def decode_once(raw):
    """The request path as the stdlib decodes it, once (`%2f` becomes a slash, `%252f` the three characters `%2f`)."""
    try:
        return urllib.parse.unquote(raw, errors="surrogatepass")
    except UnicodeDecodeError:
        return urllib.parse.unquote(raw)


class SmokeHandler(T.Handler):
    """The suite's own handler (its headers come from its end_headers), with ONE choke point at the open: send_head, which GET and HEAD
    share, resolves the real path of the exact file it is about to open (after the stdlib's rule has chosen any index file) and opens that
    resolved path, so what was checked is what is read. The request path is decoded ONCE, here, with the stdlib's own single decode, and the one
    decision the text decides (a slash or not) is made from that string; translate_path only maps the path to the filesystem and its own
    trailing-slash rule, which differs between Python versions, is never consulted. The stdlib's send_head is never called. A file whose real path is
    outside the root is a 403 recorded in OUTSIDE; a directory is never listed (403)."""
    INDEX_NAMES = ("index.html", "index.htm")        # the stdlib's own choice of a directory's page; containment is checked on whatever is chosen

    def send_head(self):
        try:
            return self._open_contained()
        except ValueError:                           # an embedded NUL in the path: a bad request, answered cleanly
            self.send_error(400)
            return None

    def _redirect_to_slash(self):
        """The stdlib's own redirect for a directory asked for without its slash (Location from the request's own path, query kept); reads no file."""
        parts = urllib.parse.urlsplit(self.path)
        self.send_response(301)
        self.send_header("Location", urllib.parse.urlunsplit(parts._replace(path=parts.path + "/")))
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _open_contained(self):
        raw = self.path.split("?")[0].split("#")[0]
        decoded = decode_once(raw)                   # our one decoding: every decision from the text is made from this string
        slash = decoded.endswith("/")                # never from translate_path's trailing slash (it differs by Python) and never from `raw` (`/d%2f`)
        path = self.translate_path(raw).rstrip("/") or "/"      # the filesystem path only; its slash, present or not, is ignored
        if os.path.isdir(path):
            if not slash:
                self._redirect_to_slash()            # the tool's own 301: no directory is ever handed to the stdlib's send_head
                return None
            for name in self.INDEX_NAMES:
                if os.path.isfile(os.path.join(path, name)):
                    path = os.path.join(path, name)
                    break
            else:
                self.send_error(403, "No permission to list directory")
                return None
        elif slash:
            self.send_error(404, "File not found")
            return None
        real = os.path.realpath(path)
        if not inside(self.root_real, real):
            OUTSIDE.append(raw)
            self.send_error(403)
            return None
        try:
            f = open(real, "rb")
        except OSError:
            self.send_error(404, "File not found")
            return None
        try:
            st = os.fstat(f.fileno())
            self.send_response(200)
            self.send_header("Content-type", self.guess_type(path))
            self.send_header("Content-Length", str(st.st_size))
            self.send_header("Last-Modified", self.date_time_string(st.st_mtime))
            self.end_headers()
            return f
        except BaseException:
            f.close()
            raise


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
    # open on THIS step: the markup's article carries its id, or the page made the card from the data (a single `.card` child, no id) and its .claim is the title
    made = ("((b) => !!b && b.children.length === 1 && b.children[0].classList.contains('card') && "
            "((b.children[0].querySelector('.claim') || {}).textContent || '').replace(/`/g, '').replace(/\\s+/g, ' ').trim() === %s)(document.getElementById('graph-sheet-body'))"
            % json.dumps(plain(p["title"])))
    ok = v.wait("!(document.getElementById('graph-sheet') || {hidden: true}).hidden && (document.querySelector('#graph-sheet-body article')?.id === %s || %s)"
                % (json.dumps(p["id"]), made), OPEN_TIMEOUT_MS)
    check = "open-" + what
    if not ok:
        state = v.ev("""(() => ({sheet: !!document.getElementById('graph-sheet') && !document.getElementById('graph-sheet').hidden, shown: (document.querySelector('#graph-sheet-body article')||{}).id || null,
          fallback: !!document.getElementById('graph-fallback') && !document.getElementById('graph-fallback').hidden, notice: (document.getElementById('graph-notice')||{}).textContent || ''}))()""")
        out("FAIL", vp, check, "#%s: the sheet did not open (%s)" % (p["id"], json.dumps(state)))
        return False
    head = v.ev("""(() => { const c = document.querySelector('#graph-sheet .crumb-here');
        if (c) { const k = c.cloneNode(true); k.querySelectorAll('.crumb-role').forEach((e) => e.remove()); return {from: 'crumb', text: k.textContent}; }
        const q = document.querySelector('#graph-sheet-body .claim'); return {from: 'claim', text: q ? q.textContent : ''}; })()""")
    if plain(p["title"]) == "" or plain(head["text"]) == "":
        out("FAIL", vp, check, "#%s: empty heading (the sheet's is %r from the %s, the card title in the step file is %r)" % (p["id"], collapse(head["text"]), head["from"], collapse(p["title"])))
        return False
    if plain(head["text"]) != plain(p["title"]):
        out("FAIL", vp, check, "#%s: heading %r (%s) is not the card title %r" % (p["id"], collapse(head["text"]), head["from"], collapse(p["title"])))
        return False
    out("PASS", vp, check, "#%s heading %r" % (p["id"], plain(head["text"])))
    return True


def note_check(v, vp, p, no_note, opened, require_note):
    """The one decision about the file's note: skipped (--no-note, or no step carries one), failed (required and none; or the sheet did not
    open; or the sheet shows none), or passed."""
    n = p.get("note")
    if no_note:
        out("SKIP", vp, "note", "(--no-note)")
        return
    if not n:
        skip_or_fail(vp, "note", "no file step carries a note", require_note, "--require-note")
        return
    if not opened:
        out("FAIL", vp, "note", "#%s: the sheet did not open, so its note was not checked" % p["id"])
        return
    want = letters_digits(n["text"])[:30]
    if want == "":
        out("FAIL", vp, "note", "#%s: the note text is empty after dropping everything but letters and digits (note text empty), so there is nothing to look for" % p["id"])
        return
    got = v.ev("(() => { const b = document.querySelector('#graph-sheet-body .note-body'); return b ? b.textContent : null; })()")
    if got is None:
        out("FAIL", vp, "note", "#%s carries a note but the sheet has no .note-body" % p["id"])
    elif collapse(got) == "":
        out("FAIL", vp, "note", "#%s: the sheet's .note-body is empty" % p["id"])
    elif want not in letters_digits(got):
        out("FAIL", vp, "note", "#%s: .note-body does not contain the first 30 letters and digits of the note, %r" % (p["id"], want))
    else:
        out("PASS", vp, "note", "#%s .note-body holds the first 30 letters and digits of the note, %r" % (p["id"], want))


def scale_check(v, vp, index, require_floor):
    if "open_scale_floor" not in index:
        skip_or_fail(vp, "scale-floor", "the index has no open_scale_floor", require_floor, "--require-floor")
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


def run_viewport(browser, vp, base, site, index, picked, no_note, require_note, require_floor):
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
    csp_header_check(vp, hdr)
    boot.close()
    names = ("part", "group", "file")
    for what, p in zip(names, picked):
        v = View(browser, base + "#" + p["id"], vp, shared)
        opened = open_check(v, vp, what, p)
        if opened:
            OPENED.add(p["id"])
        if what == "file":
            note_check(v, vp, p, no_note, opened, require_note)
        if what == "part" and vp == "390x844":
            scale_check(v, vp, index, require_floor)
        v.page.wait_for_timeout(200)
        csp_events += v.ev("window.__csp || []") or []
        v.close()
    cons = [c for c in shared["console"] if "Content Security Policy" not in c]
    cspc = [c for c in shared["console"] if "Content Security Policy" in c] + csp_events
    out("FAIL" if cons else "PASS", vp, "console", "; ".join(cons)[:300] if cons else "no console error, no uncaught exception")
    out("FAIL" if cspc else "PASS", vp, "csp", "; ".join(cspc)[:300] if cspc else "no securitypolicyviolation")
    out("FAIL" if shared["requests"] else "PASS", vp, "requests", "; ".join(shared["requests"])[:300] if shared["requests"] else "no response >= 400, no failed request")


CREDITS_LINKS = "[...document.querySelectorAll('a[href]')].map((a) => a.href)"


def credits_check(browser, site, base, map_path, required):
    """The credits page, at 1280x900: it answers 200, its console and requests are clean, and a link on the page reaches the map's index, which loads.
    `base` is the URL of the tree's server root, `map_path` the folder (relative to it) that holds the map's index.html ('' flat, 'graph/')."""
    vp, check = "1280x900", "credits"
    if not os.path.isfile(os.path.join(site, "credits", "index.html")):
        skip_or_fail("all", check, "no credits/ in tree", required, "--require-credits")
        return
    shared = {"console": [], "requests": []}
    url = base + "credits/"
    v = View(browser, url, vp, shared)
    status = v.response.status if v.response else None
    v.page.wait_for_timeout(300)
    csp_events = v.ev("window.__csp || []") or []
    links = v.ev(CREDITS_LINKS) or []
    v.close()
    problems = shared["console"] + shared["requests"] + csp_events
    if status != 200:
        out("FAIL", vp, check, "credits/ answers %s, not 200" % status)
        return
    if problems:
        out("FAIL", vp, check, "the credits page is not clean: " + "; ".join(problems)[:300])
        return
    want = urllib.parse.urlsplit(base).path + map_path
    hits = [l for l in links if urllib.parse.urlsplit(l).path in (want, want + "index.html")]
    if not hits:
        out("FAIL", vp, check, "no link on the credits page leads to the map's index (%s); its links: %s" % (want, ", ".join(links)[:200] or "none"))
        return
    mshared = {"console": [], "requests": []}
    m = View(browser, hits[0], vp, mshared)
    mstatus = m.response.status if m.response else None
    loaded = m.wait(SETTLED, BOOT_TIMEOUT_MS) and m.ev(BOOTED)
    m.close()
    if mstatus != 200 or not loaded or mshared["console"] or mshared["requests"]:
        out("FAIL", vp, check, "the credits page's link %s answers %s, and the map %s" % (hits[0], mstatus, "booted" if loaded else "did not boot"))
        return
    out("PASS", vp, check, "answers 200, clean, and its link %s reaches the map's index, which loads" % hits[0])


def main(argv):
    reset_state()
    args = argv[1:]
    only = None
    if "--only-viewport" in args:
        i = args.index("--only-viewport")
        only = args[i + 1] if i + 1 < len(args) else None
        del args[i:i + 2]
        if only not in VIEWPORTS:
            print("--only-viewport takes 390x844 or 1280x900", file=sys.stderr)
            return 2
    flags = ("--no-note", "--require-note", "--require-floor", "--require-credits")
    no_note, require_note, require_floor, require_credits = (f in args for f in flags)
    args = [a for a in args if a not in flags]
    if len(args) != 1 or args[0].startswith("-") or (no_note and require_note):
        print("usage: smoke_tree.py SITE_DIR [--no-note | --require-note] [--require-floor] [--require-credits] [--only-viewport 390x844|1280x900]", file=sys.stderr)
        return 2
    if require_floor and only == "1280x900":
        print("--require-floor cannot be combined with --only-viewport 1280x900: the floor check runs only at 390x844", file=sys.stderr)
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
            browser = p.chromium.launch(executable_path=T.SHELL[0], args=LAUNCH_ARGS) if T.SHELL else p.chromium.launch(args=LAUNCH_ARGS)
            for vp in ([only] if only else list(VIEWPORTS)):
                try:
                    run_viewport(browser, vp, base, base_dir, index, picked, no_note, require_note, require_floor)
                except Exception as e:  # noqa: BLE001  (a page that throws in View.ev, a closed browser: a FAIL line, then the verdict like any other run)
                    out("FAIL", vp, "exception", exception_detail(e))
            try:
                credits_check(browser, site, host, (sub + "/" if sub else ""), require_credits)
            except Exception as e:  # noqa: BLE001
                out("FAIL", "1280x900", "exception", exception_detail(e))
            browser.close()
    except Exception as e:  # noqa: BLE001  (no playwright, no browser to launch)
        out("FAIL", "all", "exception", exception_detail(e))
    finally:
        srv.shutdown()
    if OUTSIDE:
        out("FAIL", "all", "containment", "request outside SITE_DIR refused: " + ", ".join(sorted(set(OUTSIDE)))[:300])
    else:
        out("PASS", "all", "containment", "every request and read stayed inside SITE_DIR")
    print("INFO all " + opened_line(OPENED, index.get("steps")), flush=True)
    print(verdict(FAILED[0], SKIPPED, only))
    return 0 if FAILED[0] == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
