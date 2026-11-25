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
    assert pg.page.get_attribute("#graph-fallback a", "href") == "../list/"
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
    assert pg.page.get_attribute(".seg-link", "href") == "../list/"
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
    # text size at the first fit: font size times the camera's scale (measured from the title's rendered height)
    m = pg.ev("""(() => { const t = document.querySelector('[data-node="goal-chain"] .face-title'); const r = t.getBoundingClientRect();
        return [parseFloat(getComputedStyle(t).fontSize), r.height / t.offsetHeight]; })()""")
    eff = m[0] * m[1]
    print("   first-fit text: font %.1f px x scale %.3f = %.1f px" % (m[0], m[1], eff))
    assert eff >= 15 - 0.5, "closed-card text is %.1f CSS px at the first fit (spec: at least 15)" % eff
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
        assert pg.ev("document.querySelector('#graph-sheet-body .sheet-status').textContent").startswith("«status_read»")
        tools = pg.ev("[...document.querySelectorAll('#graph-sheet-tools .sheet-tool')].map(x => x.textContent)")
        assert "«open_parts»" in tools, tools
        pg.csp_clean()
        pg.close()
    finally:
        S2.stop()


def build_hostile(root, payload, mutate=None):
    def idx(i):
        i["strings"]["parts_n"] = payload + " {n}"
        i["strings"]["key_state_none"] = payload
        i["strings"]["status_read"] = payload

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
        if (q("#graph-sheet-body .sheet-status") or "").split(" · ")[0] != payload:
            fails.append(cell + ": status word is not the payload as text")
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
                run("List link reaches ../list/", c_list_link)
                run("phone layout at 390: intro <= 200, targets >= 44, no h-scroll, sheet <= 85%", c_phone_layout)
                run("claim clamp: the six long claims clamp, the others do not", c_clamp)
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
            case("sheet MUTANTS: each plausible-wrong sheet turns its case red; the first-frame case stays green", c_sheet_mutants, br)
        if only is None or "markers" in only:
            case("markers: every runtime word on the page comes from index.json strings", c_hidden_strings_are_text, br)
        br.close()
    bad = [r for r in RESULTS if not r[1]]
    print("\n%d cases, %d passed, %d failed" % (len(RESULTS), len(RESULTS) - len(bad), len(bad)))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
