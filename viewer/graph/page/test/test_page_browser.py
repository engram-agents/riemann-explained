#!/usr/bin/env python3
"""Browser cases of the Graph page layer: real Chromium (the bundled headless shell), the assembled page served
locally with the graph page's Content-Security-Policy header (spec R8):
  default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self';
  font-src 'self'; form-action 'none'

Run:  ~/.engram/venv/bin/python3 viewer/graph/page/test/test_page_browser.py [--engine double|real|both] [--only TEXT]

Every case runs on the ENGINE TEST DOUBLE (test/double_engine.js, written to INTERFACE.md); cases marked REAL also run on
the real engine (viewer/graph/engine/), which is where pinch, camera and layout are decided. Exit 0 only if every
case that ran passed. Nothing is written outside a temporary directory.
"""
import glob, http.server, json, os, sys, tempfile, threading, urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import assemble  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

CSP = ("default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; "
       "img-src 'self'; font-src 'self'; form-action 'none'")
SHELL = glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"))
HOSTILE = ["<img src=x onerror=alert(1)>", "</script><script>alert(1)</script>", "javascript:alert(1)", '" onmouseover="x',
           "a b", "x" * 10000]
LONG_CLAIMS = {"a1", "a3", "a1-a", "b1", "c1", "a1-a-1"}
ALL_IDS = ["goal-chain", "inputs", "bounds", "a1", "a2", "a3", "a4", "topg", "a6", "a1-a", "a1-b", "a1-c", "a1-d", "a1-a-1", "a1-a-2",
           "a1-a-1-x", "b1", "b2", "b3", "b1-a", "b1-b", "c1", "linkn"]


class Handler(http.server.SimpleHTTPRequestHandler):
    blocked = set()
    garbage = set()     # paths answered 200 with a body that is not JSON
    delay = {}          # path -> threading.Event: the response waits until the event is set (at most 15 s)
    seen = []

    def __init__(self, *a, **k):
        super().__init__(*a, directory=self.root, **k)

    def do_GET(self):
        Handler.seen.append(self.path)
        path = self.path.split("?")[0]
        if path in Handler.delay:
            Handler.delay[path].wait(15)
        if path in Handler.blocked:
            self.send_error(404)
            return
        if path in Handler.garbage:
            body = b"this is not json"
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def end_headers(self):
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


class Served:
    def __init__(self, root):
        self.srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), type("H", (Handler,), {"root": root}))
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.base = "http://127.0.0.1:%d/" % self.srv.server_address[1]

    def stop(self):
        self.srv.shutdown()


class Pg:
    """A page with its console, errors and dialogs collected; ev() evaluates through DevTools (Playwright's own evaluate
    compiles strings with eval, which this CSP rightly blocks)."""

    def __init__(self, browser, url, width=1024, height=800, js=True, mobile=False):
        self.ctx = browser.new_context(viewport={"width": width, "height": height}, java_script_enabled=js,
                                       is_mobile=mobile, has_touch=mobile, device_scale_factor=1)
        self.page = self.ctx.new_page()
        self.console, self.dialogs = [], []
        self.page.on("console", lambda m: self.console.append((m.type, m.text)))
        self.page.on("pageerror", lambda e: self.console.append(("pageerror", str(e))))
        self.page.on("dialog", lambda d: (self.dialogs.append(d.message), d.dismiss()))
        self.cdp = self.ctx.new_cdp_session(self.page) if js else None
        self.page.goto(url)

    def ev(self, expr):
        r = self.cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in r:
            raise AssertionError("page threw: " + json.dumps(r["exceptionDetails"])[:400])
        return r["result"].get("value")

    def wait(self, expr, timeout=6000):
        """Poll an expression through DevTools until it is truthy (page.wait_for_function would eval under the CSP)."""
        waited = 0
        while waited <= timeout:
            if self.ev("!!(" + expr + ")"):
                return self
            self.page.wait_for_timeout(50)
            waited += 50
        raise AssertionError("timed out waiting for: " + expr[:120])

    def settled(self, timeout=8000):
        return self.wait("document.getElementById('graph-cards').hidden === true || !document.getElementById('graph-layer')", timeout)

    def csp_clean(self):
        bad = [c for c in self.console if "Content Security Policy" in c[1] or c[0] == "pageerror"]
        assert not bad, bad
        assert not self.dialogs, self.dialogs

    def close(self):
        self.ctx.close()


RESULTS = []


def case(name, fn, *a):
    try:
        fn(*a)
        RESULTS.append((name, True, ""))
        print("PASS " + name)
    except Exception as e:  # noqa: BLE001
        RESULTS.append((name, False, repr(e)[:600]))
        print("FAIL " + name + ": " + repr(e)[:600])


def tap(pg, node_id):
    """A tap on a card's face: pointerdown, pointerup and click, dispatched at its centre (works for the double, which
    listens for click, and for the real engine, which listens for pointer events)."""
    pg.ev("""(() => { const f = document.querySelector('[data-node="%s"] .face') || document.querySelector('[data-node="%s"]');
      const r = f.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + Math.min(r.height / 2, 30);
      const o = { bubbles: true, cancelable: true, clientX: x, clientY: y, pointerId: 1, pointerType: 'mouse', isPrimary: true, button: 0 };
      f.dispatchEvent(new PointerEvent('pointerdown', o)); f.dispatchEvent(new PointerEvent('pointerup', o)); f.dispatchEvent(new MouseEvent('click', o)); })()""" % (node_id, node_id))


def sheet_open(pg):
    return pg.ev("!document.getElementById('graph-sheet').hidden")


def shown_id(pg):
    return pg.ev("(() => { const a = document.getElementById('graph-sheet-body').querySelector('article'); return a ? a.id : null; })()")


def wait_sheet(pg, want):
    pg.wait("(!document.getElementById('graph-sheet').hidden) === %s" % ("true" if want else "false"), 5000)


def at_hash(pg, h):
    pg.ev("location.hash = %s" % json.dumps(h))


# ---------------------------------------------------------------------------------------------------------------- cases

def c_first_frame(b, S, mobile):
    pg = Pg(b, S.base + "graph/index.html", 390 if mobile else 1024, 844 if mobile else 800, mobile=mobile).settled()
    assert pg.ev("!document.getElementById('graph-layer').hidden")
    assert pg.ev("document.getElementById('graph-cards').hidden") and pg.ev("document.getElementById('graph-fallback').hidden")
    assert pg.ev("document.querySelectorAll('#graph .face').length") == 3
    assert pg.ev("document.getElementById('graph-sheet').hidden"), "no sheet on load"
    assert pg.ev("document.querySelector('#graph-sheet-body').childElementCount") == 0, "the key is closed on load"
    foot = pg.ev("document.querySelector('[data-node=\"goal-chain\"] .face-foot').textContent")
    assert foot == "6 parts", foot
    assert pg.ev("document.querySelector('[data-node=\"goal-chain\"] .face-role').textContent") == "Theorem"
    assert pg.ev("document.body.innerText.includes('undefined')") is False
    assert pg.ev("document.querySelector('meta[name=viewport]').content") == "width=device-width, initial-scale=1"
    pg.csp_clean()
    pg.close()


def c_role_less(b, S):
    pg = Pg(b, S.base + "graph/index.html#topg").settled()
    pg.wait("document.querySelector('#graph-sheet-body article')", 5000)
    assert shown_id(pg) == "topg"
    assert pg.ev("document.querySelectorAll('[data-node=\"topg\"] .face-role').length") == 0, "no role element on a role-less face"
    assert pg.ev("document.querySelector('[data-node=\"topg\"] .face-title').textContent") == "Title of step topg"
    assert pg.ev("document.querySelector('[data-node=\"topg\"] .face').children.length") == 1, "title only (no foot: a leaf)"
    items = pg.ev("[...document.querySelectorAll('#graph-crumbs li')].map(li => li.textContent)")
    assert items == ["Theorem" + "Title of step goal-chain", "Title of step topg"], items
    assert pg.ev("document.querySelectorAll('#graph-crumbs li:last-child .crumb-role').length") == 0
    # a step WITH a role shows it, in the face and in the breadcrumb
    at_hash(pg, "a1")
    pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a1'", 5000)
    assert pg.ev("document.querySelector('[data-node=\"a1\"] .face-role').textContent") == "Theorem"  # a1 is a theorem in the fixture
    assert pg.ev("document.querySelector('#graph-crumbs li:last-child .crumb-role').textContent") == "Theorem"
    pg.csp_clean()
    pg.close()


def c_sheet_r2(b, S):
    pg = Pg(b, S.base + "graph/index.html").settled()
    before = pg.ev("document.getElementById('graph-cards').outerHTML")
    assert len(before) > 1000
    tap(pg, "goal-chain")
    wait_sheet(pg, True)
    assert shown_id(pg) == "goal-chain"
    assert pg.ev("document.getElementById('goal-chain').parentElement === document.getElementById('graph-sheet-body')"), "moved in by appendChild"
    assert pg.ev("document.getElementById('graph-sheet-body').querySelectorAll('details[open]').length") == 0, "every details closed"
    assert pg.ev("document.querySelector('#graph-sheet-body .sheet-status').previousElementSibling.classList.contains('claim')"), "status line follows the claim"
    st = pg.ev("document.querySelector('#graph-sheet-body .sheet-status').textContent")
    assert st == "Statement read · Proof: not read yet.", st
    assert pg.ev("document.querySelector('#graph-sheet-body .claim').offsetHeight") > 0, "the claim is visible"
    assert pg.ev("document.querySelector('#graph-sheet').classList.contains('graph-sheet')")
    pg.page.click("#graph-sheet-close")
    wait_sheet(pg, False)
    after = pg.ev("document.getElementById('graph-cards').outerHTML")
    assert after == before, "the List markup is byte-equal after close"
    assert pg.ev("document.getElementById('goal-chain').closest('li') !== null")
    # a card whose details was OPEN in the list (a1, nested in goal-chain's parts): reached by taps (not by a fragment
    # navigation: Chromium itself opens the ancestor <details> of a #fragment target before any script runs).
    tap(pg, "goal-chain")
    wait_sheet(pg, True)
    pg.page.click("#graph-sheet-tools .sheet-tool")          # Open its parts: closes the sheet, opens the step
    wait_sheet(pg, False)
    pg.wait("document.querySelector('[data-node=\"a1\"]')")
    tap(pg, "a1")
    wait_sheet(pg, True)
    assert shown_id(pg) == "a1"
    assert pg.ev("document.querySelectorAll('#graph-sheet-body details[open]').length") == 0
    pg.page.click("#graph-sheet-close")
    wait_sheet(pg, False)
    assert pg.ev("document.getElementById('graph-cards').outerHTML") == before, "restored, the open details included"
    pg.csp_clean()
    pg.close()


def c_about_key(b, S):
    pg = Pg(b, S.base + "graph/index.html").settled()
    before = pg.ev("document.getElementById('graph-cards').outerHTML")
    assert pg.ev("document.getElementById('graph-sheet').hidden")
    pg.page.click("#graph-key")
    wait_sheet(pg, True)
    assert pg.ev("document.querySelectorAll('#graph-sheet-body .key-content li').length") == 6, "3 kinds + 3 states, generated"
    assert pg.ev("document.querySelectorAll('#graph-sheet-body .key-content h2').length") == 2
    assert pg.ev("[...document.querySelectorAll('#graph-sheet-body .key-content li')].map(l => l.textContent)[0]") == "Theorem: a result the Lean code proves"
    pg.page.click("#graph-key")          # a second tap on Key closes it
    wait_sheet(pg, False)
    assert pg.ev("document.getElementById('graph-sheet-body').childElementCount") == 0
    pg.page.click("#graph-about-open")
    wait_sheet(pg, True)
    assert pg.ev("document.getElementById('graph-about').parentElement === document.getElementById('graph-sheet-body')")
    assert pg.ev("document.querySelectorAll('#graph-sheet-body details[open]').length") == 0
    pg.page.click("#graph-sheet-close")
    wait_sheet(pg, False)
    assert pg.ev("document.getElementById('graph-cards').outerHTML") == before
    pg.csp_clean()
    pg.close()


CLOSE_DRIVERS = {
    "close-button": lambda pg: pg.page.click("#graph-sheet-close"),
    "tap-outside": lambda pg: pg.ev("""(() => { const s = document.getElementById('graph'); const r = s.getBoundingClientRect();
        for (let y = r.top + 6; y < r.bottom; y += 14) for (let x = r.left + 6; x < r.right; x += 14) {
          const e = document.elementFromPoint(x, y);
          if (e && e.closest('.ge-stage') && !e.closest('[data-node]')) { const o = { bubbles: true, cancelable: true, clientX: x, clientY: y, pointerId: 1, pointerType: 'mouse', isPrimary: true, button: 0 };
            e.dispatchEvent(new PointerEvent('pointerdown', o)); e.dispatchEvent(new PointerEvent('pointerup', o)); e.dispatchEvent(new MouseEvent('click', o)); return true; } }
        return false; })()"""),
    "escape": lambda pg: pg.page.keyboard.press("Escape"),
    "open-card": lambda pg: tap(pg, "inputs"),
    # alternate the target: setting the same fragment twice fires no hashchange
    "deep-link": lambda pg: at_hash(pg, "inputs" if pg.ev("location.hash") == "#bounds" else "bounds"),
    "toolbar-show-all": lambda pg: pg.page.click("#graph-show-all"),
    "toolbar-key": lambda pg: pg.page.click("#graph-key"),
    "toolbar-about": lambda pg: pg.page.click("#graph-about-open"),
    "open-parts": lambda pg: pg.page.click("#graph-sheet-tools .sheet-tool"),
}
CANCEL = "document.addEventListener('sheetclose', window.__cancel = (e) => e.preventDefault(), true)"
UNCANCEL = "document.removeEventListener('sheetclose', window.__cancel, true)"


def start_subject(pg, subject):
    """Open the thing under test; return the id of its moved root."""
    if subject == "card":
        tap(pg, "goal-chain")
        wait_sheet(pg, True)
        return "goal-chain"
    pg.page.click("#graph-about-open")
    wait_sheet(pg, True)
    return "graph-about"


def c_close_routes(b, S, engine, subject):
    """For EACH route in the module's own CLOSE_ROUTES, on a card and on the About block: a cancelling sheetclose listener on the
    moved root keeps the sheet open and moves nothing; with no listener the route closes (or replaces) it and the root returns home."""
    pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
    routes = pg.ev("import('./page/app.js').then(m => [...m.CLOSE_ROUTES])")
    assert sorted(routes) == sorted(CLOSE_DRIVERS), ("the driver table is generated from CLOSE_ROUTES; missing/extra:", set(routes) ^ set(CLOSE_DRIVERS))
    before = pg.ev("document.getElementById('graph-cards').outerHTML")
    ran = []
    for name in routes:
        if subject == "about" and name == "open-parts":
            continue        # the About block has no parts to open
        root = start_subject(pg, subject)
        pg.ev(CANCEL)
        fired = CLOSE_DRIVERS[name](pg)
        assert fired is not False, name + ": the driver found nothing to press (a vacuous pass otherwise)"
        pg.page.wait_for_timeout(250)
        assert sheet_open(pg), name + ": a cancelling listener keeps the sheet open"
        assert pg.ev("document.getElementById(%s).parentElement === document.getElementById('graph-sheet-body')" % json.dumps(root)), name + ": nothing moved"
        assert pg.ev("document.getElementById('graph-sheet-body').childElementCount") == 1, name + ": the body's single child is the moved root"
        pg.ev(UNCANCEL)
        CLOSE_DRIVERS[name](pg)
        pg.page.wait_for_timeout(250)
        if name in ("toolbar-key", "toolbar-about"):
            # these REPLACE the sheet's content (or toggle About off): the root is home when it is not what is shown
            if name == "toolbar-about" and subject == "about":
                assert not sheet_open(pg), name
            else:
                assert pg.ev("document.getElementById(%s).closest('#graph-cards') !== null" % json.dumps(root)), name + ": root home"
                pg.page.click("#graph-sheet-close")
        elif name == "open-card":
            assert shown_id(pg) == "inputs", "opening another card replaced it"
            pg.page.click("#graph-sheet-close")
        elif name == "deep-link":
            pg.wait("document.querySelector('#graph-sheet-body article')?.id === location.hash.slice(1)", 5000)
            pg.page.click("#graph-sheet-close")
        elif name == "open-parts":
            assert not sheet_open(pg), name
        else:
            assert not sheet_open(pg), name + ": with no listener the route closes"
        wait_sheet(pg, False)
        assert pg.ev("document.getElementById('graph-cards').outerHTML") == before, name + ": every root is home, markup byte-equal"
        pg.ev("location.hash = ''")
        ran.append(name)
    assert len(ran) >= len(routes) - 1
    pg.csp_clean()
    pg.close()


def c_close_request(b, S):
    pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
    before = pg.ev("document.getElementById('graph-cards').outerHTML")
    tap(pg, "goal-chain")
    wait_sheet(pg, True)
    pg.ev(CANCEL)
    pg.ev("document.getElementById('goal-chain').dispatchEvent(new CustomEvent('sheetcloserequest', {bubbles: true}))")
    pg.page.wait_for_timeout(200)
    assert sheet_open(pg), "the request runs the same close function, which a cancelling listener still stops"
    pg.ev(UNCANCEL)
    pg.ev("document.getElementById('goal-chain').dispatchEvent(new CustomEvent('sheetcloserequest', {bubbles: true}))")
    wait_sheet(pg, False)
    assert pg.ev("document.getElementById('graph-cards').outerHTML") == before
    # the class the comment script sets is honoured and left alone by the graph code
    tap(pg, "goal-chain")
    wait_sheet(pg, True)
    pg.ev("document.getElementById('graph-sheet').classList.add('comments-editing')")
    h = pg.ev("document.getElementById('graph-sheet').getBoundingClientRect().height")
    assert abs(h - 900) < 2, "comments-editing makes the sheet full height: %s" % h
    pg.page.click("#graph-sheet-close")
    wait_sheet(pg, False)
    pg.csp_clean()
    pg.close()


def c_deep_link(b, S, engine):
    pg = Pg(b, S.base + "graph/index.html#a1-a-1-x").settled()
    pg.wait("document.querySelector('#graph-sheet-body article')", 6000)
    assert shown_id(pg) == "a1-a-1-x"
    items = pg.ev("[...document.querySelectorAll('#graph-crumbs li')].map(li => li.textContent)")
    assert len(items) == 5, items
    if engine == "double":
        log = pg.ev("document.getElementById('graph').__log")
        assert ["reveal", ["goal-chain", "a1", "a1-a", "a1-a-1", "a1-a-1-x"]] in log, log
    assert ("/graph/step/a1-a-1-x.json" in " ".join(Handler.seen)), "the step file of the id was requested"
    pg.csp_clean()
    pg.close()


def c_deep_link_refused(b, S):
    for h in ["<img src=x onerror=alert(1)>", "</script><script>alert(1)</script>", "javascript:alert(1)", '" onmouseover="x', "a b",
              "x" * 10000, "Bad Id", "../index", "%E0%A4%A", "nope-1"]:
        pg = Pg(b, S.base + "graph/index.html").settled()
        n0 = pg.ev("document.querySelectorAll('*').length")
        pg.page.goto(S.base + "graph/index.html#" + (h if "%" in h else urllib.parse.quote(h, safe="")))
        pg.wait("!document.getElementById('graph-notice').hidden", 6000)
        note = pg.ev("document.getElementById('graph-notice').textContent")
        assert note == "That address does not name a step on this map.", repr(note)
        assert pg.ev("document.getElementById('graph-sheet').hidden"), "no sheet for a refused id"
        assert pg.ev("document.getElementById('graph-notice').childElementCount") == 0
        assert pg.ev("document.querySelectorAll('*').length") == n0, "the refused id made no element: " + h[:20]
        assert pg.ev("document.getElementById('graph-fallback').hidden"), "a refused id is a notice, not the fallback"
        pg.csp_clean()
        pg.close()


def c_fallback(b, S, engine, build):
    # scripts disabled: the fallback sentence and the cards, visibly
    pg = Pg(b, S.base + "graph/index.html", js=False)
    vis = pg.page.eval_on_selector_all("#graph-fallback p, #graph-cards article", "els => els.filter(e => e.offsetParent !== null).length")
    assert vis >= 24, vis   # 2 fallback paragraphs + the 23 cards (nested ones sit in closed details: counted when shown)
    assert pg.page.is_visible("#graph-fallback")
    assert pg.page.is_visible("#graph-cards")
    assert not pg.page.is_visible("#graph-layer")
    assert pg.page.inner_text("#graph-fallback").startswith("The map did not load")
    assert pg.page.get_attribute("#graph-fallback a", "href") == "list/"
    pg.close()


def c_fallback_404(b, S):
    Handler.blocked = {"/graph/step/inputs.json"}
    try:
        pg = Pg(b, S.base + "graph/index.html")
        pg.wait("!document.getElementById('graph-layer')", 6000)
        assert pg.page.is_visible("#graph-fallback") and pg.page.is_visible("#graph-cards")
        assert pg.ev("document.querySelectorAll('#graph-cards article').length") == 23
        assert pg.ev("document.querySelector('#graph-fallback p').textContent").startswith("The map did not load")
        pg.close()
    finally:
        Handler.blocked = set()


def c_list_link(b, S):
    pg = Pg(b, S.base + "graph/index.html").settled()
    assert pg.page.get_attribute(".seg-link", "href") == "list/"
    pg.page.click(".seg-link")
    pg.page.wait_for_url("**/list/")
    assert pg.page.is_visible("#list-page")
    pg.close()


def c_phone_layout(b, S):
    pg = Pg(b, S.base + "graph/index.html", 390, 844, mobile=True).settled()
    h = pg.ev("document.querySelector('.intro').getBoundingClientRect().height")
    assert h <= 200, "the block above the graph is %s px" % h
    assert pg.ev("document.documentElement.scrollWidth") <= 390, "no horizontal page scroll"
    for sel in ["#graph-show-all", "#graph-key", ".seg-here", ".seg-link", "#graph-about-open"]:
        r = pg.ev("(() => { const r = document.querySelector('%s').getBoundingClientRect(); return [r.width, r.height]; })()" % sel)
        assert r[0] >= 44 and r[1] >= 44, (sel, r)
    assert pg.ev("document.getElementById('graph-sheet').hidden"), "key closed"
    tap(pg, "goal-chain")
    wait_sheet(pg, True)
    sh = pg.ev("document.getElementById('graph-sheet').getBoundingClientRect().height")
    assert sh <= 0.85 * 844 + 1, "the sheet is at most 85%% of the height: %s" % sh
    pg.csp_clean()
    pg.close()


def c_clamp(b, S):
    pg = Pg(b, S.base + "graph/index.html", 390, 844, mobile=True).settled()
    clamped = set()
    for i in ALL_IDS:
        at_hash(pg, i)
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === %s" % json.dumps(i), 6000)
        on = pg.ev("document.getElementById('graph-sheet-body').classList.contains('claim-clamped')")
        btn = pg.ev("[...document.querySelectorAll('#graph-sheet-tools .sheet-tool')].some(x => x.textContent === 'Show the whole claim')")
        if on and btn:
            clamped.add(i)
            lines = pg.ev("(() => { const c = document.querySelector('#graph-sheet-body .claim'); return Math.round(c.clientHeight / parseFloat(getComputedStyle(c).lineHeight)); })()")
            assert lines <= 10, lines
        assert on == btn, i
    assert clamped == LONG_CLAIMS, sorted(clamped ^ LONG_CLAIMS)
    # 'Show the whole claim' then 'Show less'
    at_hash(pg, "a3")
    pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a3'", 6000)
    pg.page.click("text=Show the whole claim")
    assert pg.ev("document.getElementById('graph-sheet-body').classList.contains('claim-clamped')") is False
    assert pg.ev("[...document.querySelectorAll('#graph-sheet-tools .sheet-tool')].some(x => x.textContent === 'Show less')")
    pg.close()


# ---------------------------------------------------------------------------------------- after a fallback, nothing acts (B1)

def snapshot(pg):
    return pg.ev("""({cards: document.getElementById('graph-cards').outerHTML,
        n: document.querySelectorAll('#graph-cards article').length,
        fb: document.getElementById('graph-fallback').outerHTML,
        gone: document.getElementById('graph-layer') === null})""")


def errors_of(pg):
    return [c for c in pg.console if c[0] in ("error", "pageerror")]


def c_dead_after_fallback(b, S, engine):
    """Force a fallback AFTER setup (a non-JSON step file reached by a deep link), then try every way the page used to
    still act: a hash change to a valid id, a click on an in-article premise link, the keys the page handles. Every card
    stays exactly where the fallback left it."""
    Handler.garbage = {"/graph/step/a1.json"}
    try:
        pg = Pg(b, S.base + "graph/index.html").settled()
        at_hash(pg, "a1")
        pg.wait("!document.getElementById('graph-layer')", 6000)
        pg.page.wait_for_timeout(300)
        before = snapshot(pg)
        assert before["n"] == 23 and before["gone"], before["n"]
        assert pg.page.is_visible("#graph-fallback") and pg.page.is_visible("#graph-cards")
        at_hash(pg, "inputs")                                           # (i) a valid id in the address
        pg.page.wait_for_timeout(500)
        assert snapshot(pg) == before, "a hash change moved or changed something after the fallback"
        pg.ev("document.querySelector('#graph-cards a[href=\"#bounds\"]').click()")      # (ii) an in-article premise link
        pg.page.wait_for_timeout(500)
        assert snapshot(pg) == before, "a premise link click moved or changed something after the fallback"
        for k in ("Escape", "Tab", "Enter", "Space", "ArrowLeft", "ArrowRight", "+", "-", "0", "f"):       # (iii) keys
            pg.page.keyboard.press(k)
        pg.page.wait_for_timeout(300)
        assert snapshot(pg) == before, "a key press moved or changed something after the fallback"
        assert pg.ev("document.querySelectorAll('#graph-cards article').length") == 23
        assert not errors_of(pg), errors_of(pg)
        pg.csp_clean()
        pg.close()
    finally:
        Handler.garbage = set()


def c_dead_inflight(b, S, engine):
    """A step load in flight when the fallback happens resolves afterwards: it must not move anything."""
    gate = threading.Event()
    Handler.garbage = {"/graph/step/a1.json"}
    Handler.delay = {"/graph/step/a2.json": gate}
    try:
        pg = Pg(b, S.base + "graph/index.html").settled()
        at_hash(pg, "a2")                                               # in flight: the response is held
        waited = 0
        while "/graph/step/a2.json" not in Handler.seen and waited < 5000:
            pg.page.wait_for_timeout(50)
            waited += 50
        assert "/graph/step/a2.json" in Handler.seen, "the held request never arrived"
        at_hash(pg, "a1")                                               # the fallback, by another path
        pg.wait("!document.getElementById('graph-layer')", 6000)
        before = snapshot(pg)
        assert before["n"] == 23
        gate.set()                                                      # now the held load resolves
        pg.page.wait_for_timeout(700)
        assert snapshot(pg) == before, "a step load that resolved after the fallback moved or changed something"
        assert pg.ev("document.querySelectorAll('#graph-cards article').length") == 23
        assert not errors_of(pg), errors_of(pg)
        pg.close()
    finally:
        gate.set()
        Handler.garbage = set()
        Handler.delay = {}


# ---------------------------------------------------------------------------------------------- the open-parts route (S1)

def c_open_parts_rejects(b):
    """The engine's open() rejects: the route handles it as go() does (a fallback for anything but a 4xx), never an
    unhandled rejection."""
    def mut(text):
        old = '    log.push(["open", id]);\n'
        assert old in text
        return text.replace(old, old + '    if (id === "goal-chain") throw new Error("the open was rejected");\n')
    root = tempfile.mkdtemp(prefix="pg-s1-")
    assemble.assemble(root, "double", mutate={os.path.join("engine", "index.js"): mut})
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        tap(pg, "goal-chain")
        wait_sheet(pg, True)
        pg.page.click("#graph-sheet-tools .sheet-tool")
        pg.wait("!document.getElementById('graph-layer')", 4000)
        assert pg.page.is_visible("#graph-fallback") and pg.page.is_visible("#graph-cards")
        assert pg.ev("document.querySelectorAll('#graph-cards article').length") == 23
        assert not errors_of(pg), errors_of(pg)
        pg.close()
    finally:
        S.stop()


# --------------------------------------------------------------------- a failed load leaves the open card open (S2)

def c_failed_load_keeps_card(b, S):
    pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
    tap(pg, "goal-chain")
    wait_sheet(pg, True)
    at_hash(pg, "nope-1")                                              # a valid id with no step file: 404
    pg.wait("!document.getElementById('graph-notice').hidden", 6000)
    assert pg.ev("document.getElementById('graph-notice').textContent") == "That address does not name a step on this map."
    assert sheet_open(pg), "the reader's open card stays open when the load fails"
    assert shown_id(pg) == "goal-chain"
    assert pg.ev("document.getElementById('graph-fallback').hidden"), "a 404 is a notice, not the fallback"
    pg.page.click("#graph-sheet-close")
    wait_sheet(pg, False)
    pg.csp_clean()
    pg.close()


# ---------------------------------------------------------------- face text sizes and one fixed closed size (A1, R1')

FACE_TEXT_JS = """(() => { const out = [];
  for (const f of document.querySelectorAll('#graph .face')) {
    const w = document.createTreeWalker(f, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) {
      if (!n.textContent.trim()) continue;
      const e = n.parentElement;
      out.push({cls: e.className, size: parseFloat(getComputedStyle(e).fontSize), title: !!e.closest('.face-title'), text: n.textContent.slice(0, 16)});
    }
  }
  return out; })()"""


def assert_face_text_sizes(pg):
    """Generated from the faces on the page: every text node inside every face. The title is at least 15 px, every other
    face text (the role word, the 'N parts' foot) at least 14 px."""
    texts = pg.ev(FACE_TEXT_JS)
    assert len(texts) >= 3, texts
    for t in texts:
        assert t["size"] >= (15 if t["title"] else 14), ("a face text is too small", t)
    return texts


def c_face_text_sizes(b, S, engine):
    pg = Pg(b, S.base + "graph/index.html", 390, 844, mobile=True).settled()
    texts = assert_face_text_sizes(pg)
    kinds = {("title" if t["title"] else t["cls"]) for t in texts}
    assert {"title", "face-role", "face-foot"} <= kinds, kinds        # all three kinds of face text were looked at
    pg.csp_clean()
    pg.close()


WIDE_TITLE = "WMWMW MWMWM WMWMW MWMWM WMWMW MWMWM WMWMW MWMWM WM"      # 50 characters of the widest glyphs
PLAIN_TITLE = "No zero of the zeta function lies off the line yet"      # 50 characters of ordinary prose
assert len(WIDE_TITLE) == 50 and len(PLAIN_TITLE) == 50


FIT_JS = """(() => { const n = document.querySelector('[data-node="goal-chain"]'), f = n.querySelector('.face');
  const nr = n.getBoundingClientRect(), fr = f.getBoundingClientRect();
  const texts = [...f.querySelectorAll('.face-role, .face-title, .face-foot')].map(e => ({cls: e.className, sh: e.scrollHeight, ch: e.clientHeight, sw: e.scrollWidth, cw: e.clientWidth,
    size: parseFloat(getComputedStyle(e).fontSize), text: e.textContent}));
  return {node: [nr.left, nr.top, nr.right, nr.bottom], face: [fr.left, fr.top, fr.right, fr.bottom], fsh: f.scrollHeight, fch: f.clientHeight, fsw: f.scrollWidth, fcw: f.clientWidth,
    texts, sw: document.documentElement.scrollWidth}; })()"""


def c_face_fits(b, engine, title, mutate=None, kind=None, state=None):
    """A closed face with a 50-character title, its role word and a two-digit parts count: nothing is clipped (so the
    guard clamp on the title never fires), the face is inside its node box, text sizes hold."""
    def steps(st):
        g = st["goal-chain"]
        g["card"]["title"] = title
        if kind:
            g["card"]["kind"] = kind
        if state:
            g["card"]["state"] = state
        for k in range(6):                       # 6 children + 6 = 12: a two-digit '12 parts' foot
            c = json.loads(json.dumps(g["children"][0]))
            c["id"] = "pad-%d" % k
            g["children"].append(c)
        g["card"]["child_count"] = len(g["children"])
    root = tempfile.mkdtemp(prefix="pg-fit-")
    assemble.assemble(root, engine, step_edit=steps, mutate=mutate)
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 390, 844, mobile=True).settled()
        r = pg.ev(FIT_JS)
        kinds = [t["cls"] for t in r["texts"]]
        assert kinds == ["face-role", "face-title", "face-foot"], kinds
        assert r["texts"][1]["text"] == title and r["texts"][2]["text"] == "12 parts", r["texts"]
        e = 1.5
        nr, fr = r["node"], r["face"]
        assert fr[0] >= nr[0] - e and fr[2] <= nr[2] + e and fr[1] >= nr[1] - e and fr[3] <= nr[3] + e, ("the face is outside its node box", r["node"], r["face"])
        assert r["fsh"] <= r["fch"] and r["fsw"] <= r["fcw"], ("the face's content overflows it", r["fsh"], r["fch"], r["fsw"], r["fcw"])
        for t in r["texts"]:
            assert t["sh"] <= t["ch"] and t["sw"] <= t["cw"], ("a face text is clipped", t)
            assert t["size"] >= (15 if t["cls"] == "face-title" else 14), t
        assert r["sw"] <= 390, "no horizontal scroll"
        assert_face_text_sizes(pg)
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_face_fits_both(b, S0, engine):
    c_face_fits(b, engine, PLAIN_TITLE)
    for kind, state in (("theorem", "read"), ("def", "census"), ("structure", "none")):      # the frames differ: border widths, corners
        c_face_fits(b, engine, WIDE_TITLE, kind=kind, state=state)


# ------------------------------------------------------------------------- the sheet's tools sit in the bar, beside Close (A5)

def c_tools_in_bar(b, S):
    pg = Pg(b, S.base + "graph/index.html", 390, 844, mobile=True).settled()
    # the control still does its job: tapping it opens the parts
    tap(pg, "goal-chain")
    wait_sheet(pg, True)
    pg.page.click("#graph-sheet-tools .sheet-tool")
    wait_sheet(pg, False)
    pg.wait("document.querySelector('[data-node=\"a1\"]')", 6000)
    for card, want_parts, want_more in (("goal-chain", True, False), ("a3", False, True)):
        at_hash(pg, card)
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === %s" % json.dumps(card), 6000)
        r = pg.ev("""(() => { const sh = document.getElementById('graph-sheet'), bar = sh.querySelector('.sheet-bar'), body = document.getElementById('graph-sheet-body');
          const tools = [...document.querySelectorAll('#graph-sheet-tools .sheet-tool')];
          const br = body.getBoundingClientRect(), kr = bar.getBoundingClientRect(), cr = document.getElementById('graph-crumbs').getBoundingClientRect();
          return {kids: [...sh.children].map(c => c.classList[0]), bodyKids: body.children.length, first: body.firstElementChild.id,
            firstChild: body.firstElementChild.firstElementChild.className,
            toolsInBar: tools.length > 0 && tools.every(t => bar.contains(t)), toolBottoms: tools.map(t => t.getBoundingClientRect().bottom), bodyTop: br.top, barBottom: kr.bottom,
            texts: tools.map(t => t.textContent), crumbsBottom: cr.bottom}; })()""")
        assert r["kids"] == ["sheet-bar", "graph-sheet-body"], ("the sheet is the bar, then the body", r["kids"])
        assert r["bodyKids"] == 1 and r["first"] == card, "the moved article is the body's one child"
        assert r["firstChild"] == "claim", ("the claim comes first inside the article", r["firstChild"])
        assert r["toolsInBar"], ("the tools are in the bar", r)
        assert all(x <= r["bodyTop"] + 1 for x in r["toolBottoms"]), ("a tool sits below the top of the article", r)
        if want_parts:
            assert "Open its parts" in r["texts"] or any("parts" in t.lower() for t in r["texts"]), r["texts"]
        if want_more:
            assert "Show the whole claim" in r["texts"], r["texts"]
        pg.page.click("#graph-sheet-close")
        wait_sheet(pg, False)
        pg.ev("location.hash = ''")
    pg.csp_clean()
    pg.close()


# -------------------------------------------------- the comment script's row is the real shape, an ordinary sheet row (A6)

def c_rc_section_row(b, S0, engine):
    """The builder emits no comment row; the comment script adds details.rc-section[data-comments-target]. In the sheet it is
    an ordinary closed 44 px row, and it goes home with the article."""
    def cards(text):
        old = '<ul class="reactions">'
        i = text.index('id="goal-chain"')
        j = text.index(old, i)
        row = '<details class="rc-section" data-comments-target="goal-chain"><summary>Comments (0)</summary><div class="thread"></div></details>\n'
        return text[:j] + row + text[j:]
    root = tempfile.mkdtemp(prefix="pg-rc-")
    assemble.assemble(root, engine, cards_edit=cards)
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 390, 844, mobile=True).settled()
        before = pg.ev("document.getElementById('graph-cards').outerHTML")
        assert 'class="rc-section"' in before and "class=\"comments\"" not in before and "class=\"feedback\"" not in before
        tap(pg, "goal-chain")
        wait_sheet(pg, True)
        r = pg.ev("""(() => { const d = document.querySelector('#graph-sheet-body details.rc-section'), s = d.querySelector('summary');
          const o = document.querySelector('#graph-sheet-body details.conditions summary').getBoundingClientRect().height;
          return {open: d.open, h: s.getBoundingClientRect().height, other: o, shown: d.getBoundingClientRect().height > 0}; })()""")
        assert r["open"] is False and r["shown"], r
        assert r["h"] >= 44 and abs(r["h"] - r["other"]) < 1, ("the row is the same 44 px closed row as the others", r)
        pg.page.click("#graph-sheet-close")
        wait_sheet(pg, False)
        assert pg.ev("document.getElementById('graph-cards').outerHTML") == before, "the row went home with the article"
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_face_mutant(b):
    """Control: a fixed closed height 30 px shorter turns the fit case red (a plausible-wrong size, not the old code)."""
    import re

    def mut(text):
        m = re.search(r"nodeH: (\d+)", text)
        assert m, "nodeH not found"
        return text.replace(m.group(0), "nodeH: %d" % (int(m.group(1)) - 30))
    for engine in ("double", "real"):
        red = False
        try:
            c_face_fits(b, engine, WIDE_TITLE, mutate={os.path.join("page", "app.js"): mut})
        except Exception as e:  # noqa: BLE001
            red = True
            print("   face mutant red (%s): %s" % (engine, repr(e)[:110]))
        assert red, "MUTANT SURVIVED: a 30 px shorter face (%s)" % engine


# ------------------------------------------------- the first fit: every face text at its size AT FIT, no allowance (P1)

FIT_CAMERA_JS = """(() => { const stage = document.getElementById('graph');
  /* the engine's own camera: it writes `scale(k)` on its world element (the handle exposes no camera; the engine's files are
     not ours to change). The test double has no camera: its scale is 1 by construction. */
  const worlds = [...stage.querySelectorAll('.ge-world')];
  let k = 1, from = 'none (the double draws at scale 1)';
  if (worlds.length) { const m = /scale\\(([-0-9.e]+)\\)/.exec(worlds[0].getAttribute('style') || ''); if (!m) throw new Error('the world has no scale'); k = parseFloat(m[1]); from = 'ge-world style'; }
  const texts = [];
  for (const f of stage.querySelectorAll('.face')) {
    const w = document.createTreeWalker(f, NodeFilter.SHOW_TEXT); let n;
    while ((n = w.nextNode())) { if (!n.textContent.trim()) continue; const e = n.parentElement;
      texts.push({cls: e.className, title: !!e.closest('.face-title'), size: parseFloat(getComputedStyle(e).fontSize)}); }
  }
  const nodes = [...stage.querySelectorAll('[data-node]')].map(n => { const r = n.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; });
  const strokes = [...stage.querySelectorAll('.ge-link, .ge-head')].map(n => { const r = n.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; });
  return {k, from, texts, nodes, strokes}; })()"""


def overlaps(a, b, e=0.5):
    return min(a[2], b[2]) - max(a[0], b[0]) > e and min(a[3], b[3]) - max(a[1], b[1]) > e


def c_first_fit_size(b, S0, engine, tol=0.0, mutate=None, print_it=True):
    """At the first fit, 390 x 844: effective size = computed font-size x the engine's camera scale. The title >= 15, every other
    face text >= 14, with NO allowance (tol is 0 except in the control that shows what an allowance hides). No node overlaps another,
    and no link stroke runs through a node."""
    root = tempfile.mkdtemp(prefix="pg-fit1-")
    assemble.assemble(root, engine, mutate=mutate)
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 390, 844, mobile=True).settled()
        r = pg.ev(FIT_CAMERA_JS)
        assert len(r["nodes"]) == 3, r["nodes"]
        low = []
        for t in r["texts"]:
            eff = t["size"] * r["k"]
            need = 15.0 if t["title"] else 14.0
            if print_it and t["title"]:
                print("   first fit (%s): title font %.1f px x camera %.3f (%s) = %.2f px" % (engine, t["size"], r["k"], r["from"], eff))
            if eff < need - tol:
                low.append((t["cls"], round(eff, 2), need))
        assert not low, ("face text below its size at the first fit", low, r["k"])
        for i, a in enumerate(r["nodes"]):
            for c in r["nodes"][i + 1:]:
                assert not overlaps(a, c), ("two cards overlap", a, c)
            for st in r["strokes"]:
                assert not overlaps(a, st), ("a link stroke runs through a card", a, st)
        if engine == "real":
            assert r["strokes"], "the links were drawn (the overlap check is not vacuous)"
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_first_view_mutant(b):
    """Control for the small-viewport cases: when the page does NOT pass zoom.fitMin the strict first-view case goes red at the three
    small viewports (the engine zooms out to fit, scale below 1), and stays green at 390 x 844, where the fit is above 1 anyway. The
    same build is red whichever way the size is measured (camera scale or the rendered ratio), so the case discriminates either way."""
    def no_fitmin(text):
        old = "      zoom: { fitMin: 1,"      # the whole line goes (it also carries the optional frameMin merge, which this mutant has no use for)
        assert old in text, "fitMin line not found"
        i = text.index(old)
        j = text.index("\n", i)
        return text[:i] + text[j + 1:]
    mut = {os.path.join("page", "app.js"): no_fitmin}
    for measure in ("camera", "rendered"):
        for vw, vh in ((375, 667), (360, 640), (320, 568)):
            red = False
            try:
                c_first_view(b, None, "real", vw, vh, mutate=mut, measure=measure)
            except Exception as e:  # noqa: BLE001
                red = True
                print("   fitMin-not-passed mutant red (%s, %dx%d): %s" % (measure, vw, vh, repr(e)[:90]))
            assert red, "MUTANT SURVIVED: fitMin not passed, %s measure, %dx%d" % (measure, vw, vh)
    c_first_view(b, None, "real", 390, 844, mutate=mut)        # a tall phone fits above scale 1 anyway: unaffected
    for vw, vh in ((375, 667), (320, 568)):                    # with fitMin passed the rendered measure agrees with the camera one
        c_first_view(b, None, "real", vw, vh, measure="rendered")



def c_status_from_data(b, S0, engine):
    """The sheet's status line is strings[states[state].words] and strings[proofs[proof].words], joined; the list's own
    `p.status.proof` line is never read: a sentinel in it does not reach the sheet, and a card whose list line is absent
    (proof none) still gets its proof words from the data."""
    def cards(text):
        old = "Proof: not read yet."
        assert old in text
        return text.replace(old, "SENTINEL from the list page", 1)

    def steps(st):
        for s in st.values():
            for c in [s["card"]] + s["children"]:
                if c["id"] == "a2":
                    c["proof"] = "none"
                if c["id"] == "a3":
                    c["proof"] = "read"
    root = tempfile.mkdtemp(prefix="pg-status-")
    assemble.assemble(root, engine, cards_edit=cards, step_edit=steps)
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        st = lambda: pg.ev("document.querySelector('#graph-sheet-body .sheet-status').textContent")
        for card, want in (("goal-chain", "Statement read · Proof: not read yet."), ("a2", None), ("a3", None)):
            at_hash(pg, card)
            pg.wait("document.querySelector('#graph-sheet-body article')?.id === %s" % json.dumps(card), 6000)
            text = st()
            assert "SENTINEL" not in text, text
            if want:
                assert text == want, text
        at_hash(pg, "a2")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a2'", 6000)
        assert st().endswith(" · No proof to read"), st()
        at_hash(pg, "a3")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a3'", 6000)
        assert st().endswith(" · Proof read"), st()
        # the key lists kinds then states, in symbols.order order, with the states' words (no proofs section)
        pg.page.click("#graph-sheet-close")
        wait_sheet(pg, False)
        pg.page.click("#graph-key")
        wait_sheet(pg, True)
        heads = pg.ev("[...document.querySelectorAll('#graph-sheet-body .key-content h2')].map(e => e.textContent)")
        rows = pg.ev("[...document.querySelectorAll('#graph-sheet-body .key-content li')].map(e => e.textContent)")
        assert heads == ["Colour and shape: what Lean declares", "Frame: what we have read"], heads
        assert rows == ["Theorem: a result the Lean code proves", "Definition: a named object or statement", "Structure: a bundle of named fields",
                        "Statement read", "Statement counted by a program", "Statement not read"], rows
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_key_order(b, S0, engine):
    """symbols.order sets the key's row order; the labels come from strings[row.words]."""
    def idx(i):
        i["symbols"]["order"]["kinds"] = ["structure", "def", "theorem"]
        i["symbols"]["order"]["states"] = ["none", "census", "read"]
    root = tempfile.mkdtemp(prefix="pg-order-")
    assemble.assemble(root, engine, index_edit=idx)
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        pg.page.click("#graph-key")
        wait_sheet(pg, True)
        rows = pg.ev("[...document.querySelectorAll('#graph-sheet-body .key-content li')].map(e => e.textContent)")
        assert rows == ["Structure: a bundle of named fields", "Definition: a named object or statement", "Theorem: a result the Lean code proves",
                        "Statement not read", "Statement counted by a program", "Statement read"], rows
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_skeleton_map(b, S0, engine):
    """P1, P5, P7 on the skeleton fixture: each face carries its kind class (and its s-none); a card's sheet has exactly one
    .sheet-status, the kind's card word, with no state or proof word, directly under the title; the key has the three kind rows in
    order and no states section; closing puts the markup back."""
    root = tempfile.mkdtemp(prefix="pg-skeleton-")
    assemble.assemble(root, engine, fix="skeleton")
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        assert pg.ev("document.querySelector('[data-node=\"sk-part\"] .face').className") == "face k-part s-none"
        before = pg.ev("document.getElementById('graph-cards').outerHTML")
        foot = lambda i: pg.ev("document.querySelector('[data-node=\"%s\"] .face-foot')?.textContent" % i)
        assert foot("sk-part") == "2 groups" and foot("sk-part-2") == "1 file", (foot("sk-part"), foot("sk-part-2"))   # F2: the kind's word, one/many
        crumbs_want = {"sk-part": [], "sk-group-a": ["Part sk-part"], "sk-file-1": ["Part sk-part", "Group sk-group-a"],
                       "sk-file-5": ["Part sk-part", "Files under Formalism/Basic"]}
        for card, word in (("sk-part", "Part"), ("sk-group-a", "Group"), ("sk-file-1", "File"), ("sk-file-5", "File")):
            at_hash(pg, card)
            pg.wait("document.querySelector('#graph-sheet-body article')?.id === %s" % json.dumps(card), 6000)
            assert pg.ev("document.querySelectorAll('.sheet-status').length") == 1, card
            text = pg.ev("document.querySelector('#graph-sheet-body .sheet-status').textContent")
            assert text == word, (card, text)
            assert not any(w in text for w in ("Statement", "Proof", "statement", "proof")), text
            nxt = pg.ev("document.querySelector('#graph-sheet-body .claim').nextElementSibling.className")
            assert nxt == "sheet-status", (card, nxt)
            # F4: the breadcrumb stops at the PARENT: the current card is not listed (the sheet heading carries its title)
            crumbs = pg.ev("[...document.querySelectorAll('#graph-crumbs li')].map(e => e.textContent)")
            assert crumbs == crumbs_want[card], (card, crumbs)
            assert pg.ev("document.querySelectorAll('#graph-crumbs .crumb-here').length") == 0, card
            assert pg.ev("document.querySelectorAll('#graph-crumbs button.crumb').length") == len(crumbs_want[card]), card    # every listed ancestor is a link
            # R2: no ancestor, no landmark: a top-level card draws no breadcrumb nav at all (never an empty labelled one)
            assert pg.ev("document.querySelectorAll('#graph-crumbs nav').length") == (1 if crumbs_want[card] else 0), card
        assert foot("sk-group-a") == "3 files", foot("sk-group-a")
        pg.page.click("#graph-sheet-close")
        wait_sheet(pg, False)
        # a deep link reveals its parents, which opens their parts on the List page's details (the live map does the same): only that attribute may differ
        after = pg.ev("document.getElementById('graph-cards').outerHTML")
        assert after.replace(' open=""', "") == before.replace(' open=""', ""), "closing must put the markup back"
        pg.page.click("#graph-key")
        wait_sheet(pg, True)
        heads = pg.ev("[...document.querySelectorAll('#graph-sheet-body .key-content h2')].map(e => e.textContent)")
        rows = pg.ev("[...document.querySelectorAll('#graph-sheet-body .key-content li')].map(e => e.textContent)")
        sw = pg.ev("[...document.querySelectorAll('#graph-sheet-body .key-content li .swatch')].map(e => e.className)")
        assert heads == ["What a box is"], heads
        assert rows == ["Part of the argument", "Group of files", "Lean file"], rows
        assert sw == ["swatch k-part", "swatch k-group", "swatch k-file"], sw
        # F3: the optional note is ONE plain line directly under the kind rows
        note = pg.ev("""(() => { const c = document.querySelector('#graph-sheet-body .key-content'), p = [...c.querySelectorAll('p')];
          return { n: p.length, text: p[0] && p[0].textContent, prev: p[0] && p[0].previousElementSibling.tagName, items: c.querySelectorAll('li').length }; })()""")
        assert note == {"n": 1, "text": "Parts and groups follow the repository's own contents list (CONTENTS.md).", "prev": "UL", "items": 3}, note
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def options_seen(pg):
    """What the page handed to createGraph (the double keeps it on the container): its key list, and the two groups the v3 keys reach."""
    return pg.ev("""(() => { const o = document.getElementById('graph').__options;
      return { keys: Object.keys(o).sort(), zoom: o.zoom, layout: 'layout' in o ? o.layout : null, maxChildren: o.maxChildren, sizes: o.sizes }; })()""")


def c_v3_options_live(b, S0, engine):
    """D1/D2: the live map has no v3 key, so the options createGraph gets are those of main: no `layout` key, no `frameMin`, the zoom group
    is exactly {fitMin: 1}, and the other options are the same keys."""
    if engine != "double":
        return                       # the real engine does not keep its arguments; the double is the seam that records them
    pg = Pg(b, S0.base + "graph/index.html", 1280, 900).settled()
    o = options_seen(pg)
    assert o["keys"] == ["loadChildren", "maxChildren", "renderFace", "roots", "sizes", "zoom"], o["keys"]
    assert o["layout"] is None, o["layout"]
    assert o["zoom"] == {"fitMin": 1}, o["zoom"]
    assert o["maxChildren"] == 40, o["maxChildren"]
    pg.csp_clean()
    pg.close()


def c_v3_options_skeleton(b, S0, engine):
    """D1/D2/D3 on the skeleton (data v3): createGraph gets layout {siblings: column} and zoom {fitMin: 1, frameMin: 1} (the page's own
    fitMin kept, frameMin merged in); the links the engine is handed for sk-group-a are the two in the reduction, not the shortcut."""
    if engine != "double":
        return
    root = tempfile.mkdtemp(prefix="pg-v3-")
    assemble.assemble(root, engine, fix="skeleton")
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        o = options_seen(pg)
        assert o["keys"] == ["layout", "loadChildren", "maxChildren", "renderFace", "roots", "sizes", "zoom"], o["keys"]
        assert o["layout"] == {"siblings": "column"}, o["layout"]
        assert o["zoom"] == {"fitMin": 1, "frameMin": 1}, o["zoom"]
        links = pg.ev("document.getElementById('graph').__options.loadChildren('sk-group-a').then(ks => ks.map(k => [k.id, k.links.map(l => l.to)]))")
        assert links == [["sk-file-1", ["sk-file-2"]], ["sk-file-2", ["sk-file-3"]], ["sk-file-3", []]], links
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_v3_refusals(b, S0, engine):
    """D1/D2: a bad sibling_layout is a refusal (the fallback) on either engine; and (real engine only) open_scale_floor 2, above the
    engine's open-framing cap, makes createGraph throw a TypeError, which the page's one setup catch turns into the same fallback as its other
    start failures (the cases 'fallback on a 404 step file' and 'K2 ... unclassified' end the same way); a floor of 1 is a control that opens the map."""
    def run(edit, want_map):
        root = tempfile.mkdtemp(prefix="pg-v3r-")
        assemble.assemble(root, engine, fix="skeleton", index_edit=edit)
        S = Served(root)
        try:
            pg = Pg(b, S.base + "graph/index.html", 1280, 900)
            if want_map:
                pg.settled()
                assert pg.ev("!!document.getElementById('graph-layer')") and pg.ev("document.querySelector('[data-node=\"sk-part\"]') !== null")
            else:
                pg.wait("!document.getElementById('graph-layer')", 6000)
                assert pg.page.is_visible("#graph-fallback") and pg.page.is_visible("#graph-cards")
                assert pg.ev("document.querySelectorAll('#graph-cards article').length") == 10
            pg.close()
        finally:
            S.stop()
    run(lambda i: i.__setitem__("sibling_layout", "rows"), False)
    run(lambda i: i.__setitem__("open_scale_floor", 0), False)
    run(lambda i: i.__setitem__("open_scale_floor", 1), True)
    if engine == "real":
        run(lambda i: i.__setitem__("open_scale_floor", 2), False)


def c_backtick_title(b, S0, engine):
    """A6 in the browser: the skeleton fixture's sk-file-4 is titled with a backtick span. Its face shows a <code> element INSIDE the
    3-line clamp (the span is in view and the title has no backtick character), at the title's size, and the breadcrumb shows a span in an ancestor's title the same way."""
    root = tempfile.mkdtemp(prefix="pg-bt-")
    assemble.assemble(root, engine, fix="skeleton")
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        at_hash(pg, "sk-file-4")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'sk-file-4'", 6000)
        r = pg.ev("""(() => {
          const t = document.querySelector('[data-node="sk-file-4"] .face-title'), c = t.querySelector('code');
          const tr = t.getBoundingClientRect(), cr = c.getBoundingClientRect();
          const bc = document.querySelector('#graph-crumbs .crumb-here'), lis = [...document.querySelectorAll('#graph-crumbs li')];
          const gc = lis[lis.length - 1].querySelector('code');
          return { text: t.textContent, code: c.textContent, n: t.querySelectorAll('code').length, size: parseFloat(getComputedStyle(c).fontSize),
                   tsize: parseFloat(getComputedStyle(t).fontSize), inside: cr.top >= tr.top - 1 && cr.bottom <= tr.bottom + 1 && cr.right <= tr.right + 1,
                   ch: t.clientHeight, sh: t.scrollHeight, crumb: bc && bc.textContent, crumbs: lis.map(e => e.textContent), crumbCode: gc && gc.textContent };
        })()""")
        assert r["text"] == "The second moments of the operators P* s P, and good forms", r
        assert r["code"] == "P* s P" and r["n"] == 1 and r["inside"], r
        assert r["size"] >= 15 and r["size"] == r["tsize"], r
        assert r["sh"] <= r["ch"] + 1, ("the title is clipped", r)
        # the breadcrumb stops at the parent, and its group title carries a span as code too
        assert r["crumb"] is None, r
        assert r["crumbs"] == ["Part sk-part", "Files under Formalism/Basic"] and r["crumbCode"] == "Formalism/Basic", r
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_sheet_status_level(b, S, engine):
    """P7 at the sheet's own level: showCard with status null (or empty) builds no .sheet-status; a non-empty status builds exactly
    today's element, directly after the claim; close() removes it, and with none it still puts the article home."""
    pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
    js = """import('./page/sheet.js').then(m => {
      const d = document, mk = (t, c) => { const e = d.createElement(t); if (c) e.className = c; d.body.appendChild(e); return e; };
      const out = {};
      for (const [label, status] of [['null', null], ['empty', ''], ['text', 'Statement read \\u00b7 Proof read']]) {
        const parts = { root: mk('div'), crumbs: mk('div'), tools: mk('div'), body: mk('div'), closeButton: mk('button') };
        parts.root.hidden = true;
        const strings = { open_parts: 'o', close_parts: 'c', claim_more: 'm', claim_less: 'l', crumb_label: 'x' };
        const hooks = { closeButton() {}, go() {}, openParts() {}, closeParts() {} };
        const sheet = m.createSheet(parts, strings, hooks, new AbortController().signal);
        const home = mk('div');
        const art = d.createElement('article'); art.id = 'z-' + label;
        art.innerHTML = '<h3 class="claim">T</h3><p class="note">n</p>';
        home.appendChild(art);
        const ok = sheet.showCard(art, { id: art.id, status, canParts: false, partsOpen: false, sheetClass: '', crumbs: [{ id: art.id, title: 'T' }] });
        const claim = art.querySelector('.claim'), st = art.querySelectorAll('.sheet-status');
        const r = { ok, count: st.length, next: claim.nextElementSibling.className, tag: st[0] ? st[0].tagName : null, text: st[0] ? st[0].textContent : null };
        r.closed = sheet.close();
        r.after = art.querySelectorAll('.sheet-status').length;
        r.home = art.parentNode === home;
        out[label] = r;
      }
      return out;
    })"""
    r = pg.ev(js)
    for label in ("null", "empty"):
        assert r[label]["ok"] and r[label]["count"] == 0 and r[label]["next"] == "note", (label, r[label])
        assert r[label]["closed"] and r[label]["home"], (label, r[label])
    t = r["text"]
    assert t["ok"] and t["count"] == 1 and t["next"] == "sheet-status" and t["tag"] == "P" and t["text"] == "Statement read \u00b7 Proof read", t
    assert t["closed"] and t["after"] == 0 and t["home"], t
    pg.csp_clean()
    pg.close()


def c_look_override(b, S, engine):
    """P6/F1: part, group and file keep their marks over s-none and s-census whatever the source order; the three are told apart by BAR
    POSITION, never by ring count (part: solid 2 px with a 6 px TOP bar; group: solid 2 px, no bar; file: solid 1 px with a 4 px LEFT bar),
    none dashed; the key's swatches carry the same marks as their faces; each kind SELECTED has a ring gap of 3 px so the ring never
    touches the box border; a theorem with s-none is still dashed and a selected live-map card keeps the engine's own gap (control)."""
    root = tempfile.mkdtemp(prefix="pg-look-")
    assemble.assemble(root, engine, fix="skeleton")
    S2 = Served(root)
    pg = Pg(b, S2.base + "graph/index.html", 1280, 900).settled()
    js = """(() => {
      const mk = (c) => { const e = document.createElement('div'); e.className = c; e.style.cssText = 'position:absolute;left:-999px;top:0;width:50px;height:50px'; document.body.appendChild(e); return e; };
      const g = (c) => { const s = getComputedStyle(mk(c)); return { style: s.borderTopStyle, w: [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth], bg: s.backgroundColor, radius: s.borderTopLeftRadius }; };
      const out = { plain: g('face k-theorem s-read'), thmNone: g('face k-theorem s-none'), thmCensus: g('face k-theorem s-census') };
      for (const k of ['part', 'group', 'file']) for (const s of ['', ' s-none', ' s-census']) out[k + s] = g('face k-' + k + s);
      return out;
    })()"""
    r = pg.ev(js)
    want = {"part": ["6px", "2px", "2px", "2px"], "group": ["2px", "2px", "2px", "2px"], "file": ["1px", "1px", "1px", "4px"]}
    for k, w in want.items():
        for s in ("", " s-none", " s-census"):
            f = r[k + s]
            assert f["style"] == "solid" and f["w"] == w, (k + s, f)
            assert f["bg"] == r["plain"]["bg"] and f["radius"] == "0px", (k + s, f, r["plain"])
    bars = {tuple(r[k + " s-none"]["w"]) for k in want}
    assert len(bars) == 3, bars
    assert r["thmNone"]["style"] == "dashed" and r["thmNone"]["bg"] != r["plain"]["bg"], r["thmNone"]
    assert r["thmCensus"]["style"] == "dotted" and r["thmCensus"]["w"][0] == "3px", r["thmCensus"]
    # the key's swatches show the same marks as the faces
    pg.page.click("#graph-key")
    wait_sheet(pg, True)
    sw = pg.ev("""[...document.querySelectorAll('#graph-sheet-body .key-content .swatch')].map(e => { const s = getComputedStyle(e);
      return { cls: e.className, style: s.borderTopStyle, w: [s.borderTopWidth, s.borderRightWidth, s.borderBottomWidth, s.borderLeftWidth] }; })""")
    assert [x["cls"] for x in sw] == ["swatch k-part", "swatch k-group", "swatch k-file"], sw
    for x, k in zip(sw, ("part", "group", "file")):
        f = r[k + " s-none"]
        assert (x["style"], x["w"]) == (f["style"], f["w"]), (k, x, f)
    pg.page.click("#graph-sheet-close")
    wait_sheet(pg, False)
    # the selection ring: 3 px gap for each of the three kinds, on a really selected node
    for card, kind in (("sk-part", "part"), ("sk-group-a", "group"), ("sk-file-1", "file")):
        at_hash(pg, card)
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === %s" % json.dumps(card), 6000)
        pg.wait("document.querySelectorAll('.ge-selected').length === 1", 4000)
        got = pg.ev("""(() => { const n = document.querySelector('.ge-selected'); return [n.getAttribute('data-node'), getComputedStyle(n).outlineOffset, getComputedStyle(n).outlineStyle, n.querySelector('.face').className]; })()""")
        assert got[0] == card and got[1] == "3px" and ("k-" + kind) in got[3], got
        assert got[2] == ("solid" if engine == "real" else "none"), got       # the real engine's own 3 px ring; the double has no stylesheet
    pg.csp_clean()
    pg.close()
    S2.stop()


def c_live_controls(b, S0, engine):
    """The live map is unchanged (F1, F2, F4 controls): a selected card keeps the ring gap an unselected node has (the engine's own: 2 px
    from engine.css on the real engine, 0 on the double, which has no stylesheet), a closed card with children keeps the '{n} parts' foot,
    and the breadcrumb lists the open card itself as its last entry, after its ancestors."""
    pg = Pg(b, S0.base + "graph/index.html", 1280, 900).settled()
    assert pg.ev("document.querySelector('[data-node=\"goal-chain\"] .face-foot').textContent") == "6 parts"
    gap = pg.ev("getComputedStyle(document.querySelector('[data-node=\"goal-chain\"]')).outlineOffset")
    assert gap == ("2px" if engine == "real" else "0px"), gap
    at_hash(pg, "a1-a-1")
    pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a1-a-1'", 6000)
    pg.wait("document.querySelectorAll('.ge-selected').length === 1", 4000)
    sel = pg.ev("(() => { const n = document.querySelector('.ge-selected'); return [n.getAttribute('data-node'), getComputedStyle(n).outlineOffset]; })()")
    assert sel == ["a1-a-1", gap], sel
    crumbs = pg.ev("[...document.querySelectorAll('#graph-crumbs li')].map(e => e.textContent)")
    assert len(crumbs) == 4 and [c.endswith(t) for c, t in zip(crumbs, ["goal-chain", "a1", "a1-a", "a1-a-1"])] == [True] * 4, crumbs
    assert pg.ev("document.querySelectorAll('#graph-crumbs .crumb-here').length") == 1
    assert pg.ev("document.querySelector('#graph-crumbs .crumb-here').textContent") == crumbs[-1]
    pg.csp_clean()
    pg.close()


def c_key_real_rows(b, S0, engine):
    """P4: the live map's key is what it was: both headings, the three kinds then the three states, in the file's order."""
    pg = Pg(b, S0.base + "graph/index.html", 1280, 900).settled()
    pg.page.click("#graph-key")
    wait_sheet(pg, True)
    heads = pg.ev("[...document.querySelectorAll('#graph-sheet-body .key-content h2')].map(e => e.textContent)")
    rows = pg.ev("[...document.querySelectorAll('#graph-sheet-body .key-content li')].map(e => e.textContent)")
    assert heads == ["Colour and shape: what Lean declares", "Frame: what we have read"], heads
    assert rows == ["Theorem: a result the Lean code proves", "Definition: a named object or statement", "Structure: a bundle of named fields",
                    "Statement read", "Statement counted by a program", "Statement not read"], rows
    assert pg.ev("document.querySelectorAll('#graph-sheet-body .key-content p').length") == 0, "the live map has no key note"
    pg.csp_clean()
    pg.close()


# ----------------------------------------------------------------- the parts button follows the SHOWN card, not the engine's events (K1)

def open_on_map(pg, engine, node_id, child_id):
    """Open a node on the MAP while the sheet is up: the double does what a semantic zoom does; the real engine is zoomed with
    ctrl + wheel over the node until it opens itself."""
    if engine == "double":
        pg.ev("document.getElementById('graph').__open(%s)" % json.dumps(node_id))
    else:
        x, y, w, h = center(pg, '[data-node="%s"] .face' % node_id)
        under = pg.ev("(() => { const e = document.elementFromPoint(%f, %f); return !!(e && e.closest('.ge-stage')); })()" % (x, y))
        assert under, "the node to zoom is not reachable on the map (covered by the sheet)"
        pg.page.mouse.move(x, y)
        pg.page.keyboard.down("Control")
        try:
            for _ in range(60):
                pg.page.mouse.wheel(0, -160)
                pg.page.wait_for_timeout(40)
                if pg.ev("document.querySelector('[data-node=\"%s\"]') !== null" % child_id):
                    break
        finally:
            pg.page.keyboard.up("Control")
    pg.wait("document.querySelector('[data-node=\"%s\"]') !== null" % child_id, 6000)


def c_parts_button_follows_shown(b, S, engine):
    """A's sheet is open (the map stays visible), B is opened on the map: A's button still reads 'Open its parts' and its click
    opens A's parts. (An engine open or close event for another id changes nothing in the sheet.)"""
    pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
    label = lambda: pg.ev("(() => { const t = document.querySelector('#graph-sheet-tools .sheet-tool'); return t ? t.textContent : null; })()")
    tap(pg, "goal-chain")
    wait_sheet(pg, True)
    assert shown_id(pg) == "goal-chain" and label() == "Open its parts", label()
    open_on_map(pg, engine, "inputs", "b1")
    assert shown_id(pg) == "goal-chain", "the sheet still shows A"
    assert label() == "Open its parts", ("B's open flipped A's button", label())
    assert pg.ev("document.querySelector('[data-node=\"a1\"]') === null"), "A's parts are not open yet"
    pg.page.click("#graph-sheet-tools .sheet-tool")
    pg.wait("document.querySelector('[data-node=\"a1\"]') !== null", 6000)
    assert pg.ev("document.querySelector('[data-node=\"b1\"]') !== null"), "B stayed open"
    # and A's button now reads 'Close its parts' when A is shown again; closing B on the map (double) leaves it alone
    tap(pg, "goal-chain")
    wait_sheet(pg, True)
    assert label() == "Close its parts", label()
    if engine == "double":
        pg.ev("document.getElementById('graph').__close('inputs')")
        pg.page.wait_for_timeout(150)
        assert label() == "Close its parts", ("B's close flipped A's button", label())
    pg.csp_clean()
    pg.close()


# ------------------------------------------------------------ a failure to load a step's parts, split by CLASS (K2)

PARTS_FAILED = "The parts of this step could not be opened; tap it to try again."
LINK_REFUSED = "That address does not name a step on this map."
SECRET = "SECRET-BODY-12345"


def fail_step(pg, step_id, mode):
    """Make the step file fail from the browser's side: 'abort' (transport: the fetch rejects), an int (that status, with a body that
    must never reach the page), 'garbage' (200, not JSON), 'invalid' (200, JSON that breaks the contract)."""
    pat = "**/graph/step/%s.json" % step_id

    def handler(route):
        if mode == "abort":
            route.abort()
        elif mode == "garbage":
            route.fulfill(status=200, content_type="application/json", body="this is not json " + SECRET)
        elif mode == "invalid":
            route.fulfill(status=200, content_type="application/json", body=json.dumps({"format": 2, "note": SECRET}))
        else:
            route.fulfill(status=int(mode), content_type="text/plain", body="server says " + SECRET)
    pg.page.route(pat, handler)
    return pat


def notice_text(pg):
    return pg.ev("(() => { const n = document.getElementById('graph-notice'); return n.hidden ? null : n.textContent; })()")


def no_leak(pg):
    assert SECRET not in pg.ev("document.documentElement.outerHTML"), "a server-supplied string reached the page"


def c_load_failure_go(b, S0, engine, mode):
    """B is reached by an address (the load happens in go()). Transport (an aborted fetch, a 5xx) is a notice, the open card A stays
    open and intact, B stays closed; a retry once the server answers opens B. A 4xx stays the refused-link notice. Data that
    ARRIVED and is invalid is the fallback."""
    root = tempfile.mkdtemp(prefix="pg-k2go-")
    assemble.assemble(root, engine)
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        tap(pg, "goal-chain")
        wait_sheet(pg, True)
        pat = fail_step(pg, "a1", mode)
        at_hash(pg, "a1")
        if mode in ("garbage", "invalid"):
            pg.wait("!document.getElementById('graph-layer')", 6000)
            assert pg.page.is_visible("#graph-fallback") and pg.ev("document.querySelectorAll('#graph-cards article').length") == 23
            no_leak(pg)
        else:
            pg.wait("!document.getElementById('graph-notice').hidden", 6000)
            want = LINK_REFUSED if mode == 404 else PARTS_FAILED
            assert notice_text(pg) == want, (mode, notice_text(pg))
            assert pg.ev("document.getElementById('graph-notice').childElementCount") == 0
            assert pg.ev("!!document.getElementById('graph-layer')") and pg.ev("document.getElementById('graph-fallback').hidden"), "no fallback for a transport failure"
            assert sheet_open(pg) and shown_id(pg) == "goal-chain", "A's sheet is still open"
            assert pg.ev("document.getElementById('graph-sheet-body').childElementCount") == 1
            assert pg.ev("document.querySelector('#graph-sheet-body .sheet-status') !== null"), "A's status line is intact"
            assert pg.ev("document.querySelector('[data-node=\"a1\"]') === null"), "B stays closed (nothing was revealed)"
            no_leak(pg)
            pg.page.unroute(pat)                                         # the server answers now; the retry is the reader's
            pg.ev("location.hash = ''")
            at_hash(pg, "a1")
            pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a1'", 6000)
            assert pg.ev("document.getElementById('graph-notice').hidden")
            assert pg.ev("document.querySelector('[data-node=\"a1\"]') !== null")
        assert not [c for c in pg.console if c[0] == "pageerror"]
        pg.close()
    finally:
        S.stop()


def c_load_failure_engine(b, S0, engine, mode):
    """B's parts are opened from the sheet (the engine loads B's step): same split, through the engine's load-failed event."""
    root = tempfile.mkdtemp(prefix="pg-k2eng-")
    assemble.assemble(root, engine)
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        tap(pg, "goal-chain")
        wait_sheet(pg, True)
        pg.page.click("#graph-sheet-tools .sheet-tool")                  # goal-chain's parts (already loaded)
        wait_sheet(pg, False)
        pg.wait("document.querySelector('[data-node=\"a1\"]') !== null", 6000)
        tap(pg, "a1")
        wait_sheet(pg, True)
        assert shown_id(pg) == "a1"
        pat = fail_step(pg, "a1", mode)
        pg.page.click("#graph-sheet-tools .sheet-tool")                  # open a1's parts: its step file is fetched now
        if mode in ("garbage", "invalid"):
            pg.wait("!document.getElementById('graph-layer')", 6000)
            assert pg.page.is_visible("#graph-fallback") and pg.ev("document.querySelectorAll('#graph-cards article').length") == 23
            no_leak(pg)
        else:
            pg.wait("!document.getElementById('graph-notice').hidden", 6000)
            assert notice_text(pg) == PARTS_FAILED, (mode, notice_text(pg))
            assert pg.ev("document.getElementById('graph-notice').childElementCount") == 0
            assert pg.ev("!!document.getElementById('graph-layer')") and pg.ev("document.getElementById('graph-fallback').hidden")
            assert pg.ev("document.querySelector('[data-node=\"a1\"]') !== null and document.querySelector('[data-node=\"a1-a\"]') === null".replace(" and ", " && ")), "a1 stays closed"
            no_leak(pg)
            pg.page.unroute(pat)
            tap(pg, "a1")                                                # tapped again, by the reader
            wait_sheet(pg, True)
            assert pg.ev("document.getElementById('graph-notice').hidden"), "the card opening clears the notice"
            pg.page.click("#graph-sheet-tools .sheet-tool")
            pg.wait("document.querySelector('[data-node=\"a1-a\"]') !== null", 6000)
        assert not [c for c in pg.console if c[0] == "pageerror"]
        pg.close()
    finally:
        S.stop()


def c_load_failure_unclassified(b, S0, engine, which):
    """Anything the allow-list does not name is the fallback: a DataError with an unknown code, and a plain Error whose message
    imitates a transport code."""
    throw = {"unknown-code": 'throw new DataError("weird-code", "x");', "plain-error": 'throw new Error("fetch-failed: imitation");'}[which]

    def mut(text):
        old = "    const f = await loadStep(id);\n    return f.children.map("
        assert old in text
        return text.replace(old, '    if (id === "a1") { ' + throw + " }\n" + old)
    root = tempfile.mkdtemp(prefix="pg-k2un-")
    assemble.assemble(root, engine, mutate={os.path.join("page", "data.js"): mut})
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        tap(pg, "goal-chain")
        wait_sheet(pg, True)
        pg.page.click("#graph-sheet-tools .sheet-tool")
        wait_sheet(pg, False)
        pg.wait("document.querySelector('[data-node=\"a1\"]') !== null", 6000)
        tap(pg, "a1")
        wait_sheet(pg, True)
        pg.page.click("#graph-sheet-tools .sheet-tool")
        pg.wait("!document.getElementById('graph-layer')", 6000)
        assert pg.page.is_visible("#graph-fallback") and pg.ev("document.querySelectorAll('#graph-cards article').length") == 23
        pg.close()
    finally:
        S.stop()


# ------------------------------------------------------ the sheet is outside the scaled map: its text is at reading size (K3)

def c_sheet_text_unscaled(b, S, engine):
    """375 x 667, Show all (the map shrinks), tap a card: the moved article's claim is >= 15 px and rendered at scale 1, and the sheet bar
    (crumbs, Close) is rendered at scale 1 too. The sheet is not inside the engine's scaled world."""
    pg = Pg(b, S.base + "graph/index.html", 375, 667, mobile=True).settled()
    pg.page.click("#graph-show-all")
    pg.page.wait_for_timeout(400)
    k = pg.ev("""(() => { const w = document.querySelector('#graph .ge-world'); if (!w) return 1;
        const m = /scale\\(([-0-9.e]+)\\)/.exec(w.getAttribute('style') || ''); return m ? parseFloat(m[1]) : 1; })()""")
    print("   show all at 375 x 667 (%s): map scale %.3f" % (engine, k))
    if engine == "real":
        assert k < 1, ("the map did not shrink, so this case would pin nothing", k)
    tap(pg, "goal-chain")
    wait_sheet(pg, True)
    r = pg.ev("""(() => { const sc = (e) => { const r = e.getBoundingClientRect(); return e.offsetHeight ? r.height / e.offsetHeight : 1; };
        const claim = document.querySelector('#graph-sheet-body .claim'), close = document.getElementById('graph-sheet-close');
        const crumb = document.querySelector('#graph-crumbs .crumb-here'), bar = document.querySelector('.sheet-bar');
        return {claimPx: parseFloat(getComputedStyle(claim).fontSize), claimScale: sc(claim), closeScale: sc(close), crumbScale: sc(crumb), barScale: sc(bar),
          sheetInWorld: !!document.getElementById('graph-sheet').closest('.ge-world'), closeH: close.getBoundingClientRect().height}; })()""")
    assert r["claimPx"] >= 15 and abs(r["claimScale"] - 1) < 0.02, r
    assert abs(r["closeScale"] - 1) < 0.02 and abs(r["crumbScale"] - 1) < 0.02 and abs(r["barScale"] - 1) < 0.02, r
    assert not r["sheetInWorld"] and r["closeH"] >= 44, r
    pg.csp_clean()
    pg.close()


# ------------------------------------------------ the first view never zooms below scale 1; a cue says the map goes on (R3a)

VIEWPORTS = [(390, 844), (375, 667), (360, 640), (320, 568)]

FIRST_VIEW_JS = """(() => { const stage = document.getElementById('graph'), sr = stage.getBoundingClientRect();
  const w = stage.querySelector('.ge-world'); let k = 1, from = 'none (the double has no camera)';
  if (w) { const m = /scale\\(([-0-9.e]+)\\)/.exec(w.getAttribute('style') || ''); if (!m) throw new Error('no scale'); k = parseFloat(m[1]); from = 'ge-world'; }
  const box = (e) => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; };
  const texts = [];
  for (const f of stage.querySelectorAll('.face')) {
    const tw = document.createTreeWalker(f, NodeFilter.SHOW_TEXT); let n;
    while ((n = tw.nextNode())) { if (!n.textContent.trim()) continue; const e = n.parentElement, r = e.getBoundingClientRect();
      texts.push({cls: e.className, title: !!e.closest('.face-title'), size: parseFloat(getComputedStyle(e).fontSize), rendered: e.offsetHeight ? r.height / e.offsetHeight : 1}); }
  }
  return {k, from, stage: [sr.left, sr.top, sr.right, sr.bottom], texts,
    nodes: [...stage.querySelectorAll('[data-node]')].map((n) => [n.getAttribute('data-node')].concat(box(n))),
    strokes: [...stage.querySelectorAll('.ge-link')].map(box), heads: [...stage.querySelectorAll('.ge-head')].map(box)}; })()"""


def first_view_numbers(pg):
    return pg.ev(FIRST_VIEW_JS)


def cue_form(stage, nodes, strokes, heads=(), count_heads=False):
    """The continuation cue (the reader seat's rule 3a): exactly TWO forms; returns which one holds, or None.
      'card'    a card box crosses the stage's bottom edge;
      'stroke'  a link STROKE box (the `.ge-link` bars) crosses the bottom edge.
    The arrowhead square (`.ge-head`) is not a cue: the engine draws it as a directionless square under the card above. A clean gap
    at the bottom, or a head square alone near the edge, is None. (`count_heads` exists only for the control that shows the negative
    control catches a predicate which lets a head square count.)
    stage = [l, t, r, b]; every other box is [l, t, r, b]."""
    sb = stage[3]
    crosses = lambda x: x[1] < sb - 1 and x[3] > sb + 1
    if any(crosses(n) for n in nodes):
        return "card"
    if any(crosses(x) for x in strokes):
        return "stroke"
    if count_heads and any(x[3] > sb - 12 and x[1] < sb for x in heads):
        return "head square (a mutant)"
    return None


# Viewports where NO cue form holds, stated and asserted as such until the engine has an option that guarantees a peek of what lies
# below. Key = (engine, width, height). If the geometry changes and a cue appears there, or any other viewport loses its cue, a
# case goes red and this list must be edited on purpose.
KNOWN_NO_CUE = {
    ("real", 360, 640): "frame bottom lands 2 px below the last visible link head; peek guarantee is a later engine option",
}


def c_first_view(b, S0, engine, w, h, mutate=None, measure="camera", exceptions=None):
    """The first frame at w x h, on the real fixture. Every face text at its size EFFECTIVE at the first fit (computed font-size x the
    engine's camera scale, read from the world element, no allowance; measure='rendered' reads the rendered ratio instead): the title
    >= 15 px, every other >= 14. The top of the drawing is in view. Whenever a top step is not wholly in view, a continuation cue sits
    inside the frame touching the bottom edge: part of a card or a link stroke whose box crosses the stage's bottom edge. The named
    exceptions (KNOWN_NO_CUE) are asserted the other way round."""
    known = KNOWN_NO_CUE if exceptions is None else exceptions
    root = tempfile.mkdtemp(prefix="pg-view-")
    assemble.assemble(root, engine, mutate=mutate)
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", w, h, mobile=True).settled()
        r = first_view_numbers(pg)
        sl, st, sr_, sb = r["stage"]
        title = [t for t in r["texts"] if t["title"]][0]
        scale = r["k"] if measure == "camera" else title["rendered"]
        print("   first view %dx%d (%s): scale %.3f; title %.2f px, other text %.2f px effective" % (
            w, h, engine, scale, title["size"] * scale, min(t["size"] for t in r["texts"] if not t["title"]) * scale))
        low = []
        for t in r["texts"]:
            eff = t["size"] * (r["k"] if measure == "camera" else t["rendered"])
            if eff < (15.0 if t["title"] else 14.0):
                low.append((t["cls"], round(eff, 2)))
        assert not low, ("face text below its size at the first fit", low)
        nodes = {n[0]: n[1:] for n in r["nodes"]}
        assert sorted(nodes) == ["bounds", "goal-chain", "inputs"], sorted(nodes)
        top = nodes["goal-chain"]
        assert top[1] >= st - 1 and top[1] < sb - 20, ("the top of the drawing is not in view", top, r["stage"])
        inside = lambda n: n[1] >= st - 1 and n[3] <= sb + 1
        all_in = all(inside(n) for n in nodes.values())
        form = None if all_in else cue_form(r["stage"], list(nodes.values()), r["strokes"])
        if (engine, w, h) in known:
            assert not all_in and form is None, ("a KNOWN EXCEPTION no longer holds: a cue appeared or every top step is in view; edit KNOWN_NO_CUE on purpose", engine, w, h, form, r["stage"])
            print("   cue (%s %dx%d): KNOWN EXCEPTION, no cue form holds (%s)" % (engine, w, h, known[(engine, w, h)]))
        elif all_in:
            print("   cue (%s %dx%d): none needed, every top step is in view" % (engine, w, h))
        else:
            print("   cue (%s %dx%d): %s" % (engine, w, h, form))
            assert form, ("a top step is out of view and no cue crosses the bottom edge (not a named exception): a clean gap reads as the end of the map", r["stage"], nodes, r["heads"][-2:])
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_cue_predicate_control(b=None, S0=None, predicate=None):
    """Controls for the cue predicate, on synthetic frames (no browser). Negative: a clean gap below the last visible card; a head square
    alone near (or across) the edge; a stroke that only starts at the edge. Positive: a card crossing, a stroke crossing."""
    f = predicate or cue_form
    stage = [0, 0, 360, 640]
    card = lambda top, bottom: [30, top, 330, bottom]
    assert f(stage, [card(300, 600), card(100, 240)], [[180, 240, 182, 300]], [[176, 590, 184, 598]]) is None, "a clean gap is not a cue"
    assert f(stage, [card(100, 240)], [], [[176, 240, 184, 248]]) is None, "a head square far above the edge is not a cue"
    assert f(stage, [card(100, 630)], [], [[176, 630, 184, 638]]) is None, "a head square alone, 2 px above the edge, is not a cue"
    assert f(stage, [card(100, 630)], [], [[176, 628, 184, 643]]) is None, "a head square alone, across the edge, is not a cue"
    assert f(stage, [card(100, 240)], [[180, 640, 182, 658]], []) is None, "a stroke that only starts at the edge does not cross it"
    assert f(stage, [card(500, 700)], [], []) == "card"
    assert f(stage, [card(100, 240)], [[180, 600, 182, 680]], []) == "stroke"
    assert f(stage, [card(100, 630)], [[180, 630, 182, 660]], [[176, 630, 184, 638]]) == "stroke"


def c_cue_mutant(b=None):
    """Control for the control: a predicate that lets a head square count is caught by the negative control."""
    lenient = lambda stage, nodes, strokes, heads: cue_form(stage, nodes, strokes, heads, count_heads=True)
    caught = False
    try:
        c_cue_predicate_control(predicate=lenient)
    except AssertionError as e:
        caught = True
        print("   head-square predicate caught by the negative control: %s" % str(e)[:80])
    assert caught, "MUTANT SURVIVED: the negative control accepts a head square as a cue"


def c_exception_list_mutant(b):
    """With the exception list emptied the 360 x 640 first view on the real engine is red (no cue form holds there); and with the list as
    it is, a viewport that is not listed but loses its cue would be red too (the other viewports assert a cue)."""
    red = False
    try:
        c_first_view(b, None, "real", 360, 640, exceptions={})
    except Exception as e:  # noqa: BLE001
        red = True
        print("   exception list emptied: 360x640 red: %s" % repr(e)[:100])
    assert red, "MUTANT SURVIVED: an empty exception list still passes 360 x 640"
    red = False
    try:
        c_first_view(b, None, "real", 375, 667, exceptions={("real", 375, 667): "wrongly listed"})
    except Exception as e:  # noqa: BLE001
        red = True
        print("   a viewport that has a cue, wrongly listed: red: %s" % repr(e)[:100])
    assert red, "MUTANT SURVIVED: a listed viewport that has a cue passes"


def c_show_all_whole_top_level(b, S, engine):
    """360 x 640: Show all frames the whole top level (the scale may go below 1)."""
    pg = Pg(b, S.base + "graph/index.html", 360, 640, mobile=True).settled()
    pg.page.click("#graph-show-all")
    pg.page.wait_for_timeout(500)
    r = first_view_numbers(pg)
    st, sb = r["stage"][1], r["stage"][3]
    nodes = {n[0]: n[1:] for n in r["nodes"]}
    print("   show all 360x640 (%s): scale %.3f" % (engine, r["k"]))
    for name, n in nodes.items():
        assert n[1] >= st - 1 and n[3] <= sb + 1, ("a top step is out of view after Show all", name, n, r["stage"])
    if engine == "real":
        assert r["k"] < 1, r["k"]
    pg.csp_clean()
    pg.close()


# ------------------------------------------- the sheet shows one status line of its own, not the list page's three (S5)

def disp(pg, sel):
    return pg.ev("""(() => { const a = document.querySelector('#graph-sheet-body article'); const e = a.querySelector(':scope > ' + %s);
        return e ? getComputedStyle(e).display : 'absent'; })()""" % json.dumps(sel))


def c_sheet_duplicates(b, S, engine):
    pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
    # (card, proof): a1 is proof read, a4 not read, a2 none (a definition)
    for card, proof in (("a1", "read"), ("a4", "not_read"), ("a2", "none"), ("a1", "read")):
        at_hash(pg, "")
        at_hash(pg, card)
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === %s" % json.dumps(card), 6000)
        got = (disp(pg, "p.status.statement"), disp(pg, "p.status.proof"), disp(pg, "p.roots-only"))
        assert disp(pg, "p.status.statement") == "none" and disp(pg, "p.roots-only") == "none", (card, proof, got)
        if proof == "none":
            assert disp(pg, "p.status.proof") not in ("none", "absent"), ("a proof-none card keeps the line that says why", card, got)
        else:
            assert disp(pg, "p.status.proof") == "none", (card, proof, got)
        assert pg.ev("getComputedStyle(document.querySelector('#graph-sheet-body .sheet-status')).display") != "none", "the page's own status line shows"
        assert pg.ev("document.getElementById('graph-sheet').classList.contains('sheet-proof-none')") == (proof == "none")
    pg.csp_clean()
    pg.close()


def c_fallback_keeps_lines(b, S0, engine):
    """The fallback page (after a failure) shows all three lines on every card."""
    root = tempfile.mkdtemp(prefix="pg-s5fb-")
    assemble.assemble(root, engine)
    S = Served(root)
    Handler.garbage = {"/graph/step/a1.json"}
    try:
        pg = Pg(b, S.base + "graph/index.html").settled()
        tap(pg, "a1") if False else None
        at_hash(pg, "a1")
        pg.wait("!document.getElementById('graph-layer')", 6000)
        for sel in ("p.status.statement", "p.status.proof", "p.roots-only"):
            shown = pg.ev("[...document.querySelectorAll('#graph-cards %s')].map(e => getComputedStyle(e).display)" % sel)
            assert len(shown) == 23 and all(d != "none" for d in shown), (sel, len(shown), set(shown))
        pg.close()
    finally:
        Handler.garbage = set()
        S.stop()


def c_scripts_off_keeps_lines(b, S):
    pg = Pg(b, S.base + "graph/index.html", js=False)
    for sel in ("p.status.statement", "p.status.proof", "p.roots-only"):
        shown = pg.page.eval_on_selector_all("#graph-cards " + sel, "els => els.map(e => getComputedStyle(e).display)")
        assert len(shown) == 23 and all(d != "none" for d in shown), (sel, len(shown), set(shown))
    pg.close()


# ------------------------------------------------------------------------- cases that need the REAL engine (camera, gestures)

def center(pg, sel):
    return pg.ev("(() => { const r = document.querySelector(%s).getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2, r.width, r.height]; })()" % json.dumps(sel))


def touch(pg, kind, pts):
    pg.cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [{"x": x, "y": y, "id": i} for i, (x, y) in enumerate(pts)]})


def c_real_drag(b, S):
    pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
    x, y, w, h = center(pg, '[data-node="goal-chain"] .face')
    pg.page.mouse.move(x, y)
    pg.page.mouse.down()
    pg.page.mouse.move(x + 60, y + 20, steps=6)
    pg.page.mouse.up()
    pg.page.wait_for_timeout(300)
    assert not sheet_open(pg), "a drag does not open a sheet"
    x, y, w, h = center(pg, '[data-node="goal-chain"] .face')
    pg.page.mouse.click(x, y)                       # a real, short click is one tap
    wait_sheet(pg, True)
    assert shown_id(pg) == "goal-chain"
    pg.csp_clean()
    pg.close()


def c_real_first_frame_390(b, S):
    pg = Pg(b, S.base + "graph/index.html", 390, 844, mobile=True).settled()
    stage = pg.ev("(() => { const r = document.getElementById('graph').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })()")
    assert stage[3] - stage[1] > 300, stage
    nodes = pg.ev("[...document.querySelectorAll('#graph [data-node]')].map(n => { const r = n.getBoundingClientRect(); return [n.getAttribute('data-node'), r.left, r.top, r.right, r.bottom]; })")
    ids = sorted(n[0] for n in nodes)
    assert ids == ["bounds", "goal-chain", "inputs"], ("no level opened by default: the top steps only", ids)
    for f in nodes:
        assert f[1] >= stage[0] - 1 and f[3] <= stage[2] + 1 and f[2] >= stage[1] - 1 and f[4] <= stage[3] + 1, ("a top card is not inside the first frame", f, stage)
    assert pg.ev("document.documentElement.scrollWidth") <= 390
    pg.csp_clean()
    pg.close()


def c_real_pinch(b, S):
    Handler.seen.clear()
    pg = Pg(b, S.base + "graph/index.html", 390, 844, mobile=True).settled()

    def pinch_on(sel, want):
        x, y, w, h = center(pg, sel)
        d = 40
        touch(pg, "touchStart", [(x - d / 2, y), (x + d / 2, y)])
        for step in range(1, 90):
            d = 40 + step * 4
            touch(pg, "touchMove", [(max(1, x - d / 2), y), (min(389, x + d / 2), y)])
            pg.page.wait_for_timeout(15)
            if pg.ev(want):
                break
        touch(pg, "touchEnd", [])
        pg.page.wait_for_timeout(200)
        return pg.ev(want)
    assert pinch_on('[data-node="goal-chain"] .face', "document.querySelector('[data-node=\"a1\"]') !== null"), "the pinch semantic-opened goal-chain"
    assert not sheet_open(pg), "a pinch opens no sheet"
    # pinch further into a child: its step file is requested by the semantic open
    Handler.seen.clear()
    assert pinch_on('[data-node="a1"] .face', "document.querySelector('[data-node=\"a1-a\"]') !== null"), "the pinch semantic-opened a1"
    assert any(u.startswith("/graph/step/a1.json") for u in Handler.seen), ("the step file was requested", Handler.seen)
    assert not sheet_open(pg)
    pg.csp_clean()
    pg.close()


SHEET = os.path.join("page", "sheet.js")
SHEET_MUTANTS = [
    ("close ignores a cancelling sheetclose", SHEET, "    if (ev.defaultPrevented) return false;\n", "", lambda b, S: c_close_routes(b, S, "double", "card")),
    ("close does not restore the details the list had open", SHEET, "    for (const x of rec.details) x.d.open = x.open;\n", "", c_sheet_r2),
    ("close leaves the status line in the article", SHEET, "    if (rec.status && rec.status.parentNode) rec.status.parentNode.removeChild(rec.status);\n", "", c_sheet_r2),
    ("close does not move the article home", SHEET, "        rec.home.parentNode.insertBefore(rec.node, rec.home);\n", "", c_sheet_r2),
    ("sheetcloserequest is not listened for", SHEET, '  root.addEventListener("sheetcloserequest", () => close(), { signal });\n', "", c_close_request),
]


def c_sheet_mutants(b):
    """Controls: a plausible-WRONG sheet (not the old code) must turn its own case red, while an unrelated case (first frame)
    stays green on the same build."""
    for name, rel, old, new, fn in SHEET_MUTANTS:
        def mut(text, old=old, new=new):
            assert old in text, "mutation site not found: " + old
            return text.replace(old, new)
        root = tempfile.mkdtemp(prefix="pg-mut-")
        assemble.assemble(root, "double", mutate={rel: mut})
        S = Served(root)
        try:
            red = False
            try:
                fn(b, S)
            except Exception:  # noqa: BLE001
                red = True
            assert red, "MUTANT SURVIVED: " + name
            c_first_frame(b, S, False)      # the unrelated case stays green on the mutated build
            print("   mutant red as required: " + name)
        finally:
            S.stop()


def c_hidden_strings_are_text(b):
    """No reader-facing word is a literal in the page code: every runtime word is replaced by a marker, and every text node
    the page code adds (faces, key, crumbs, status, buttons) is a marker or data."""
    def idx(i):
        for k in list(i["strings"]):
            i["strings"][k] = "«" + k + "»"
    root = tempfile.mkdtemp(prefix="pg-markers-")
    assemble.assemble(root, "double", index_edit=idx)
    S2 = Served(root)
    try:
        pg = Pg(b, S2.base + "graph/index.html", 1280, 900).settled()
        foot = pg.ev("document.querySelector('[data-node=\"goal-chain\"] .face-foot').textContent")
        assert foot == "«parts_n»".replace("{n}", "6"), foot
        pg.page.click("#graph-key")
        wait_sheet(pg, True)
        words = pg.ev("[...document.querySelectorAll('#graph-sheet-body .key-content h2, #graph-sheet-body .key-content li')].map(e => e.textContent)")
        assert all(w.startswith("«") and w.endswith("»") for w in words), words
        pg.page.click("#graph-sheet-close")
        tap(pg, "goal-chain")
        wait_sheet(pg, True)
        assert pg.ev("document.querySelector('#graph-crumbs nav').getAttribute('aria-label')") == "«crumb_label»"
        assert pg.ev("document.querySelector('#graph-sheet-body .sheet-status').textContent").startswith("«sheet_statement_read» · «sheet_proof_not_read»")
        tools = pg.ev("[...document.querySelectorAll('#graph-sheet-tools .sheet-tool')].map(x => x.textContent)")
        assert "«open_parts»" in tools, tools
        pg.csp_clean()
        pg.close()
    finally:
        S2.stop()


def build_hostile(root, payload, mutate=None):
    def idx(i):
        i["strings"]["parts_n"] = payload + " {n}"
        i["strings"]["sheet_statement_not_read"] = payload      # the last key row (states, in order)
        i["strings"]["sheet_statement_read"] = payload          # the sheet status of goal-chain: statement
        i["strings"]["sheet_proof_not_read"] = payload          # ... and proof

    def steps(st):
        for s in st.values():
            s["card"]["title"] = payload
            s["card"]["role"] = payload
            for c in s["children"]:
                c["title"] = payload
                c["role"] = payload
    return assemble.assemble(root, "double", index_edit=idx, step_edit=steps, mutate=mutate)


def run_hostile(b, mutate=None):
    fails = []
    for n, payload in enumerate(HOSTILE):
        root = tempfile.mkdtemp(prefix="pg-hostile-")
        build_hostile(root, payload, mutate)
        S = Served(root)
        try:
            f = hostile_cell(b, S, n, payload)
            fails.extend(f)
        finally:
            S.stop()
    return fails


def hostile_cell(b, S, n, payload):
    fails = []
    cell = "payload %d" % n
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900)
        pg.wait("document.getElementById('graph-cards').hidden === true || !document.getElementById('graph-layer')", 8000)
        q = lambda s: pg.ev("(() => { const e = document.querySelector(%s); return e ? e.textContent : null; })()" % json.dumps(s))
        if q('[data-node="goal-chain"] .face-title') != payload:
            fails.append(cell + ": face title is not the payload as text")
        if q('[data-node="goal-chain"] .face-role') != payload:
            fails.append(cell + ": face role is not the payload as text")
        if q('[data-node="goal-chain"] .face-foot') != payload + " 6":
            fails.append(cell + ": runtime word is not the payload as text")
        pg.page.click("#graph-key")
        last = pg.ev("(() => { const l = document.querySelectorAll('#graph-sheet-body .key-content li'); return l.length ? l[l.length - 1].textContent : null; })()")
        if last != payload:
            fails.append(cell + ": key word is not the payload as text")
        pg.page.click("#graph-sheet-close")
        tap(pg, "goal-chain")
        pg.page.wait_for_timeout(250)
        if q("#graph-crumbs .crumb-here") != payload + payload:
            fails.append(cell + ": breadcrumb is not role+title as text")
        if pg.ev("document.querySelectorAll('#graph-crumbs *').length") != 5:
            fails.append(cell + ": the breadcrumb has a different number of elements than the 5 it is built from")
        if (q("#graph-sheet-body .sheet-status") or "").split(" · ") != [payload, payload]:
            fails.append(cell + ": status words are not the payloads as text")
        if pg.ev("document.querySelectorAll('img, iframe, object, embed, [onerror], [onmouseover], [onclick], [onload]').length") != 0:
            fails.append(cell + ": an element or event handler appeared")
        if pg.ev("document.querySelectorAll('script').length") != 1:
            fails.append(cell + ": a script element appeared")
        if pg.dialogs:
            fails.append(cell + ": a dialog opened")
        if [c for c in pg.console if "Content Security Policy" in c[1] or c[0] == "pageerror"]:
            fails.append(cell + ": CSP violation or page error")
        pg.close()
    except Exception as e:  # noqa: BLE001
        fails.append(cell + ": threw " + repr(e)[:150])
    return fails


def c_hostile(b):
    fails = run_hostile(b)
    assert not fails, fails


def c_hostile_kind_state(b):
    """A hostile kind or state is a refusal (the fallback), never a class name, never markup."""
    for field in ("kind", "state"):
        for payload in HOSTILE:
            root = tempfile.mkdtemp(prefix="pg-hk-")

            def steps(st, f=field, p=payload):
                st["goal-chain"]["children"][0][f] = p
            assemble.assemble(root, "double", step_edit=steps)
            S = Served(root)
            try:
                pg = Pg(b, S.base + "graph/index.html")
                pg.wait("!document.getElementById('graph-layer')", 6000)
                assert pg.page.is_visible("#graph-fallback") and pg.page.is_visible("#graph-cards")
                assert pg.ev("document.querySelectorAll('img, [onerror], [onmouseover]').length") == 0
                assert pg.ev("document.querySelectorAll('script').length") == 1
                pg.csp_clean()
                pg.close()
            finally:
                S.stop()


def c_mutant(b):
    """R7 MUTANT: a copy of dom.js whose text path uses innerHTML. The hostile cells must go red."""
    def mut(text):
        old = "node.appendChild(d.createTextNode(c));"
        assert old in text
        return text.replace(old, "node.innerHTML += c;")
    fails = run_hostile(b, mutate={os.path.join("page", "dom.js"): mut})
    print("MUTANT: %d hostile cells red" % len(fails))
    for f in fails[:40]:
        print("   RED " + f[:150])
    assert fails, "the mutant survived: the hostile cells did not go red"
    c_mutant.fails = fails


def main():
    only = None
    engines = ["double", "real"]
    argv = sys.argv[1:]
    if "--only" in argv:
        only = argv[argv.index("--only") + 1]
    if "--engine" in argv:
        e = argv[argv.index("--engine") + 1]
        engines = ["double", "real"] if e == "both" else [e]
    if not SHELL:
        print("no headless shell under ~/.cache/ms-playwright")
        return 2
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=SHELL[0], args=["--no-sandbox"])
        for eng in engines:
            root = tempfile.mkdtemp(prefix="pg-" + eng + "-")
            assemble.assemble(root, eng)
            S = Served(root)
            try:
                def run(name, fn, *a):
                    if only is None or only in name:
                        case(eng + ": " + name, fn, br, S, *a)
                run("first frame at 1024", c_first_frame, False)
                run("first frame at 390", c_first_frame, True)
                run("role-less step: no role element, title-only crumb; role shown when present", c_role_less)
                run("sheet: article moves in, details closed, comes home, List markup byte-equal", c_sheet_r2)
                run("About and Key sheets", c_about_key)
                run("EVERY close path honours a cancelling sheetclose (card); with none it closes", c_close_routes, eng, "card")
                run("EVERY close path honours a cancelling sheetclose (About root); with none it closes", c_close_routes, eng, "about")
                run("sheetcloserequest closes through the same function; comments-editing is full height", c_close_request)
                run("deep link to a depth-5 id", c_deep_link, eng)
                run("deep link ids refused visibly (R3)", c_deep_link_refused)
                run("fallback with scripts off", c_fallback, eng, None)
                run("fallback on a 404 step file", c_fallback_404)
                run("List link reaches list/", c_list_link)
                run("phone layout at 390: intro <= 200, targets >= 44, no h-scroll, sheet <= 85%", c_phone_layout)
                run("claim clamp: the six long claims clamp, the others do not", c_clamp)
                run("face text sizes: the title >= 15 px, every other face text >= 14 px (generated over every text node)", c_face_text_sizes, eng)
                run("one fixed closed size: a 50-character title (wide glyphs, then plain), role word and a two-digit parts count all fit, nothing clipped", c_face_fits_both, eng)
                run("the sheet's tools sit in the bar beside Close; the article is the body's one child and starts with its claim", c_tools_in_bar)
                run("the comment script's details.rc-section row is an ordinary closed 44 px sheet row and goes home", c_rc_section_row, eng)
                run("first fit at 390 x 844: title >= 15 px and other face text >= 14 px at the engine's camera scale, no allowance; nothing overlaps", c_first_fit_size, eng)
                run("the sheet status line is the data's words (states and proofs); the list's proof line is never read; the key shows kinds then states", c_status_from_data, eng)
                run("symbols.order sets the key's order", c_key_order, eng)
                run("module: P4 the live map's key rows are unchanged", c_key_real_rows, eng)
                run("module: F1/F2/F4 controls on the live map: ring gap, the parts foot, the breadcrumb with the open card", c_live_controls, eng)
                run("module: P1/P5/P7 the skeleton map (face classes, the card word as the one sheet line, the key has three kind rows and no states section)", c_skeleton_map, eng)
                run("v3: the live map passes createGraph no layout and no frameMin (zoom is {fitMin: 1}); main's options", c_v3_options_live, eng)
                run("v3: the skeleton passes layout column and zoom {fitMin: 1, frameMin: 1}; the engine gets the reduction's links only", c_v3_options_skeleton, eng)
                run("v3: a bad sibling_layout or open_scale_floor is the fallback; a floor above the engine's cap throws a TypeError at start and is the fallback too", c_v3_refusals, eng)
                run("module: A6 a backtick span in a title is a code element on the face (inside the clamp) and in the breadcrumb, no backtick shown", c_backtick_title, eng)
                run("module: P7 the sheet builds .sheet-status only for a non-empty status", c_sheet_status_level, eng)
                run("module: P6/F1 part, group and file told by bar position over s-none and s-census; swatches match; the selection ring gap is 3 px", c_look_override, eng)
                run("K3: at 375 x 667 after Show all, the sheet's claim and bar are at reading size, not scaled with the map", c_sheet_text_unscaled, eng)
                run("R3a cue predicate: a clean gap and a head square alone are not a cue; a card or a stroke crossing the edge is", lambda b, S, *a: c_cue_predicate_control())
                for vw, vh in VIEWPORTS:
                    run("R3a first view at %dx%d: text at its size at the first fit (camera scale, no allowance), the top in view, a cue at the bottom edge" % (vw, vh), c_first_view, eng, vw, vh)
                if eng == "real":       # the double draws a plain flow and has no Show all
                    run("R3a Show all at 360x640 frames the whole top level", c_show_all_whole_top_level, eng)
                run("S5: the sheet hides the list's statement and roots-only lines, and the proof line unless there is no proof", c_sheet_duplicates, eng)
                run("S5: the fallback page keeps all three lines on every card", c_fallback_keeps_lines, eng)
                run("S5: with scripts off all three lines stay", c_scripts_off_keeps_lines)
                run("K1: a parts button follows the SHOWN card: B opened on the map leaves A's button alone and A's click opens A's parts", c_parts_button_follows_shown, eng)
                for mode in ("abort", 500, 404, "garbage", "invalid"):
                    run("K2 via an address, %s: transport is a notice (A stays open, B closed, retry works); 4xx a refused link; arrived data the fallback" % mode, c_load_failure_go, eng, mode)
                for mode in ("abort", 500, 404, "garbage", "invalid"):
                    run("K2 via the engine's open, %s: transport is a notice (B stays closed, tapped again it opens); arrived data the fallback" % mode, c_load_failure_engine, eng, mode)
                for which in ("unknown-code", "plain-error"):
                    run("K2: %s defaults to the fallback" % which, c_load_failure_unclassified, eng, which)
                run("after a fallback: a hash change, a premise link click and the keys move nothing", c_dead_after_fallback, eng)
                run("after a fallback: a step load that was in flight moves nothing when it resolves", c_dead_inflight, eng)
                run("a failed load (404) leaves the reader's open card open and shows the notice", c_failed_load_keeps_card)
                if eng == "real":
                    run("REAL: a drag opens no sheet, a short click does", c_real_drag)
                    run("REAL: first frame at 390: the top steps only, inside the stage, text >= 15 px", c_real_first_frame_390)
                    run("REAL: pinch semantic-opens a step and loads its step file; no sheet", c_real_pinch)
            finally:
                S.stop()
        if only is None or "open-parts" in only:
            case("open-parts: a rejecting open() is a fallback, not an unhandled rejection", c_open_parts_rejects, br)
        if only is None or "hostile" in only or "mutant" in only:
            case("hostile: 6 payloads x title, role, runtime words, key, crumb, status", c_hostile, br)
            case("hostile: kind and state payloads are refusals", c_hostile_kind_state, br)
            case("R7 MUTANT (innerHTML text path) turns the hostile cells red", c_mutant, br)
            case("cue MUTANT: a predicate that lets a head square count is caught by the negative control", c_cue_mutant, br)
            case("cue MUTANT: the exception list emptied turns 360x640 red; a listed viewport that has a cue turns red", c_exception_list_mutant, br)
            case("first-view MUTANT: without zoom.fitMin the strict small-viewport cases go red (camera and rendered measures)", c_first_view_mutant, br)
            case("face MUTANT: a fixed closed height 30 px shorter turns the fit case red", c_face_mutant, br)
            case("sheet MUTANTS: each plausible-wrong sheet turns its case red; the first-frame case stays green", c_sheet_mutants, br)
        if only is None or "markers" in only:
            case("markers: every runtime word on the page comes from index.json strings", c_hidden_strings_are_text, br)
        br.close()
    bad = [r for r in RESULTS if not r[1]]
    print("\n%d cases, %d passed, %d failed" % (len(RESULTS), len(RESULTS) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
