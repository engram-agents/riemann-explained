#!/usr/bin/env python3
"""Browser cases of the Graph page layer: real Chromium (the bundled headless shell), the assembled page served
locally with the graph page's Content-Security-Policy header (spec R8):
  default-src 'none'; script-src 'self'; style-src 'self' 'unsafe-inline'; connect-src 'self'; img-src 'self';
  font-src 'self'; form-action 'none'

Run:  ~/.engram/venv/bin/python3 viewer/graph/page/test/test_page_browser.py [--engine double|real|both] [--only TEXT]
Browser: by default the bundled headless shell under ~/.cache/ms-playwright (as before). If the environment variable
RH_PLAYWRIGHT_CHANNEL is set to a Playwright channel name (for example `chrome`), the browser of that channel installed on the
machine is launched instead and the headless shell is not looked for. `--check-browser-choice` runs the choice's own five checks.

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


def browser_launch(env, shell):
    """The keyword arguments of `chromium.launch` for this machine, or None when there is no browser to launch: with RH_PLAYWRIGHT_CHANNEL set
    (not empty) the named channel, otherwise the first bundled headless shell exactly as before, otherwise None."""
    channel = env.get("RH_PLAYWRIGHT_CHANNEL", "")
    if channel:
        return {"channel": channel, "args": ["--no-sandbox"]}
    if shell:
        return {"executable_path": shell[0], "args": ["--no-sandbox"]}
    return None


def check_browser_choice():
    shell = ["/x/first-headless-shell", "/x/second-headless-shell"]
    first = {"executable_path": "/x/first-headless-shell", "args": ["--no-sandbox"]}
    chrome = {"channel": "chrome", "args": ["--no-sandbox"]}
    got = [browser_launch({}, shell), browser_launch({}, []), browser_launch({"RH_PLAYWRIGHT_CHANNEL": ""}, shell), browser_launch({"RH_PLAYWRIGHT_CHANNEL": "chrome"}, []),
           browser_launch({"RH_PLAYWRIGHT_CHANNEL": "chrome"}, shell)]
    want = [first, None, first, chrome, chrome]
    print("browser choice: " + ("PASS" if got == want else "FAIL " + repr(got)))
    return 0 if got == want else 1


HOSTILE = ["<img src=x onerror=alert(1)>", "</script><script>alert(1)</script>", "javascript:alert(1)", '" onmouseover="x',
           "a b", "x" * 10000]
LONG_CLAIMS = {"a1", "a3", "a1-a", "b1", "c1", "a1-a-1"}
ALL_IDS = ["goal-chain", "inputs", "bounds", "a1", "a2", "a3", "a4", "topg", "a6", "a1-a", "a1-b", "a1-c", "a1-d", "a1-a-1", "a1-a-2",
           "a1-a-1-x", "b1", "b2", "b3", "b1-a", "b1-b", "c1", "linkn"]


class Handler(http.server.SimpleHTTPRequestHandler):
    blocked = set()
    garbage = set()     # paths answered 200 with a body that is not JSON
    delay = {}          # path -> threading.Event: the response waits until the event is set (at most 15 s)
    status = {}         # path -> int: after any delay, the response is that error status (a slow-then-failing step file)
    seen = []

    def __init__(self, *a, **k):
        super().__init__(*a, directory=self.root, **k)

    def do_GET(self):
        Handler.seen.append(self.path)
        path = self.path.split("?")[0]
        if path in Handler.delay:
            Handler.delay[path].wait(15)
        if path in Handler.status:
            self.send_error(Handler.status[path])
            return
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

    def __init__(self, browser, url, width=1024, height=800, js=True, mobile=False, init=None):
        self.ctx = browser.new_context(viewport={"width": width, "height": height}, java_script_enabled=js,
                                       is_mobile=mobile, has_touch=mobile, device_scale_factor=1)
        if init:
            self.ctx.add_init_script(init)     # runs before any script of the page: a listener registered here cannot miss an early event
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


# ------------------------------------------------------------------------------- ONE navigation ticket (the latest route wins)

def hold_step(step_id, status=None):
    """The server holds ONE step file until the returned event is set; with a status, it then answers that error."""
    gate = threading.Event()
    path = "/graph/step/%s.json" % step_id
    Handler.delay[path] = gate
    if status is not None:
        Handler.status[path] = status
    Handler.seen.clear()
    return gate, path


def held_arrived(pg, path):
    waited = 0
    while path not in Handler.seen and waited < 5000:
        pg.page.wait_for_timeout(50)
        waited += 50
    assert path in Handler.seen, "the held request never arrived: " + path


def nav_page(b, S, prep=True):
    """A settled page. The page's own start fetches the three top step files, so a tap on a top card is served from the cache and has no
    load in flight. With prep, the address #a1 is followed first: that opens a1's sheet (card C) and puts its siblings a2 and a3 on the
    map with their step files NOT yet fetched, which is what a slow tap needs."""
    pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
    if prep:
        at_hash(pg, "a1")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a1'", 6000)
    return pg


def carry_notes(index):
    """index_edit: the two words that make a map one that carries notes (the live fixture has neither; none of its steps carries a note)."""
    index["strings"]["note_label"] = "Note label (synthetic)"
    index["strings"]["note_source"] = "Note source {source} {commit} (synthetic)"


def nav_clear():
    Handler.delay = {}
    Handler.status = {}


def click_by_id(pg, i):
    pg.ev("document.getElementById(%s).click()" % json.dumps(i))


def c_nav_r1(b, S, engine):
    """R1: tap A (slow, then a 500), then tap B (fast): B's sheet is open, no notice, no fallback, also after A answers."""
    gate = threading.Event()   # the hold is placed AFTER the page settles (the page's own start reads step files); set in finally
    try:
        pg = nav_page(b, S)
        gate, path = hold_step("a2", 500)
        tap(pg, "a2")
        held_arrived(pg, path)
        tap(pg, "a3")
        wait_sheet(pg, True)
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a3'", 5000)
        gate.set()
        pg.page.wait_for_timeout(700)
        assert shown_id(pg) == "a3" and sheet_open(pg), "B's sheet is the open one"
        assert notice_text(pg) is None, "no notice for a card the reader left: %r" % notice_text(pg)
        assert pg.ev("!!document.getElementById('graph-layer')") and pg.ev("document.getElementById('graph-fallback').hidden"), "no fallback"
        pg.csp_clean()
        pg.close()
    finally:
        gate.set()
        nav_clear()


def c_nav_r2(b, S, engine, how):
    """R2: tap A (slow), then Escape (or the close button): when A resolves the sheet stays closed."""
    gate = threading.Event()   # the hold is placed AFTER the page settles (the page's own start reads step files); set in finally
    try:
        pg = nav_page(b, S)
        gate, path = hold_step("a2")
        tap(pg, "a2")
        held_arrived(pg, path)
        if how == "escape":
            pg.page.keyboard.press("Escape")
        else:
            click_by_id(pg, "graph-sheet-close")
        gate.set()
        pg.page.wait_for_timeout(700)
        assert not sheet_open(pg), "the close was undone by the load that resolved after it (%s)" % how
        assert shown_id(pg) is None
        pg.csp_clean()
        pg.close()
    finally:
        gate.set()
        nav_clear()


def c_nav_r3(b, S, engine):
    """R3: tap A (slow), then the toolbar key: when A resolves the key panel is still the one shown."""
    gate = threading.Event()   # the hold is placed AFTER the page settles (the page's own start reads step files); set in finally
    try:
        pg = nav_page(b, S)
        gate, path = hold_step("a2")
        tap(pg, "a2")
        held_arrived(pg, path)
        click_by_id(pg, "graph-key")
        wait_sheet(pg, True)
        assert pg.ev("document.querySelector('#graph-sheet-body .key-content') !== null")
        gate.set()
        pg.page.wait_for_timeout(700)
        assert pg.ev("document.querySelector('#graph-sheet-body .key-content') !== null"), "the key panel was replaced by the late card"
        assert shown_id(pg) is None
        pg.csp_clean()
        pg.close()
    finally:
        gate.set()
        nav_clear()


def c_nav_r4(b, S, engine):
    """R4: deep link #A (slow) then #B (fast): the page ends on B (the sheet shows B; the address is #B)."""
    gate = threading.Event()   # the hold is placed AFTER the page settles (the page's own start reads step files); set in finally
    try:
        pg = nav_page(b, S, False)
        gate, path = hold_step("a1")
        at_hash(pg, "a1")
        held_arrived(pg, path)
        at_hash(pg, "a2")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a2'", 6000)
        gate.set()
        pg.page.wait_for_timeout(900)
        assert shown_id(pg) == "a2", "the page ended on %r, not on the later address" % shown_id(pg)
        assert pg.ev("location.hash") == "#a2"
        pg.csp_clean()
        pg.close()
    finally:
        gate.set()
        nav_clear()


def c_nav_r5(b, S, engine):
    """R5: card C open; tap A (slow); an in-sheet close request: when A resolves the sheet stays closed."""
    gate = threading.Event()   # the hold is placed AFTER the page settles (the page's own start reads step files); set in finally
    try:
        pg = nav_page(b, S)
        gate, path = hold_step("a2")
        tap(pg, "a2")
        held_arrived(pg, path)
        pg.ev("document.getElementById('a1').dispatchEvent(new CustomEvent('sheetcloserequest', {bubbles: true}))")
        wait_sheet(pg, False)
        gate.set()
        pg.page.wait_for_timeout(700)
        assert not sheet_open(pg), "an in-sheet close was undone by the load that resolved after it"
        pg.csp_clean()
        pg.close()
    finally:
        gate.set()
        nav_clear()


def c_nav_r6(b, S, engine):
    """R6 control, unchanged: a single slow tap opens its sheet; a single failed load shows the parts notice; a 4xx the refused-link notice."""
    gate = threading.Event()
    try:
        for code, want in ((None, None), (500, PARTS_FAILED), (404, LINK_REFUSED)):
            nav_clear()
            pg = nav_page(b, S)
            gate, path = hold_step("a2", code)
            tap(pg, "a2")
            held_arrived(pg, path)
            gate.set()
            if code is None:
                pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a2'", 5000)
                assert sheet_open(pg)
            else:
                pg.wait("!document.getElementById('graph-notice').hidden", 5000)
                assert notice_text(pg) == want, (code, notice_text(pg))
                assert shown_id(pg) == "a1" and pg.ev("!!document.getElementById('graph-layer')"), "a single failure is a notice, the open card stays, no fallback"
            pg.close()
    finally:
        gate.set()
        nav_clear()


# ------------------------------- round 4: no visible effect from a superseded route, through ANY channel (reviewer round 2, S1 and S2)

def c_nav_b1_b3(b, S, engine, how):
    """B1/B3 (and the About half of B2): tap A (slow), then a route that closes or replaces the sheet that is not Escape, the close button or the key:
    tap-outside (a tap on blank map), toolbar About, toolbar Show all. When A resolves, its sheet does not open over what the reader did."""
    gate = threading.Event()
    try:
        pg = nav_page(b, S)
        gate, path = hold_step("a2")
        tap(pg, "a2")
        held_arrived(pg, path)
        if how == "tap-outside":
            assert CLOSE_DRIVERS["tap-outside"](pg), "no blank map to tap"
            wait_sheet(pg, False)
        elif how == "toolbar-about":
            click_by_id(pg, "graph-about-open")
            wait_sheet(pg, True)
            assert pg.ev("document.getElementById('graph-about').parentElement === document.getElementById('graph-sheet-body')")
        else:
            click_by_id(pg, "graph-show-all")
            wait_sheet(pg, False)
        gate.set()
        pg.page.wait_for_timeout(700)
        if how == "toolbar-about":
            assert pg.ev("document.getElementById('graph-about').parentElement === document.getElementById('graph-sheet-body')"), "About was replaced by the late card"
        else:
            assert not sheet_open(pg), "the late card opened over %s" % how
        assert shown_id(pg) is None, "the late card's article is in the sheet (%s)" % how
        assert notice_text(pg) is None
        pg.csp_clean()
        pg.close()
    finally:
        gate.set()
        nav_clear()


HOLD_KIDS_JS = "(() => { const h = { fail: false }; h.p = new Promise((r) => { window.__releaseKids = (fail) => { h.fail = !!fail; r(); }; }); window.__holdKids = { a1: h }; return true; })()"


def hold_kids_root(engine):
    """A served copy of the page whose data layer (the copy only) waits on window.__holdKids[id] before it answers loadChildren(id): the step of a
    card on the sheet is cached, so its parts load is otherwise instant and there is no window to put a tap in. Released with a true argument it then
    fails the way a transport failure does (a DataError 'http-500', the class the page shows as the parts notice)."""
    def mut(text):
        old = "  async function loadChildren(id) {\n"
        assert old in text
        hold = ("    const h = globalThis.__holdKids && globalThis.__holdKids[id];\n"
                "    if (h) { await h.p; if (h.fail) throw new DataError(\"http-500\", \"held, then failed\"); }\n")
        return text.replace(old, old + hold)
    root = tempfile.mkdtemp(prefix="pg-b4-")
    assemble.assemble(root, engine, mutate={os.path.join("page", "data.js"): mut}, index_edit=carry_notes)
    return Served(root)


def world_style(pg):
    """The real engine's camera: the transform on its world element (the world's own width and height change when a node opens, so they are not compared)."""
    return pg.ev("(() => { const w = document.querySelector('#graph .ge-world'); const m = w && /transform:([^;]*);/.exec(w.getAttribute('style') || ''); return m ? m[1] : null; })()")


def c_nav_b4(b, S0, engine):
    """B4: open-parts on card C (its children's load slow), then tap card D: when C's load resolves D's sheet is untouched and the camera is
    not moved to C (the double's call log has no new reveal; the real engine's world keeps its transform); D stays the selected card."""
    S = hold_kids_root(engine)
    try:
        pg = nav_page(b, S)
        assert pg.ev(HOLD_KIDS_JS)
        pg.page.click("#graph-sheet-tools .sheet-tool")                 # open C's parts: the route waits on the held load
        wait_sheet(pg, False)
        tap(pg, "a2")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a2'", 5000)
        log0 = len(pg.ev("document.getElementById('graph').__log")) if engine == "double" else 0
        style0 = world_style(pg)
        pg.ev("(() => { window.__releaseKids(false); return true; })()")
        pg.page.wait_for_timeout(700)
        assert shown_id(pg) == "a2" and sheet_open(pg), "D's sheet was replaced or closed by C's late load"
        if engine == "double":
            late = [e for e in pg.ev("document.getElementById('graph').__log")[log0:] if e[0] == "reveal"]
            assert not late, "the camera was moved by the superseded open-parts: %r" % late
        else:
            assert style0 and world_style(pg) == style0, "the camera moved after D's sheet opened: %r -> %r" % (style0, world_style(pg))
        assert pg.ev("document.querySelector('[data-node=\"a2\"]').classList.contains('ge-selected')"), "D is no longer the selected card"
        assert notice_text(pg) is None
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_nav_b4b(b, S, engine):
    """B4b: tap A (slow), then open-parts on the card still shown: the open-parts route takes its own ticket, so when A resolves the sheet stays closed."""
    gate = threading.Event()
    try:
        pg = nav_page(b, S)
        gate, path = hold_step("a2")
        tap(pg, "a2")
        held_arrived(pg, path)
        pg.page.click("#graph-sheet-tools .sheet-tool")
        wait_sheet(pg, False)
        gate.set()
        pg.page.wait_for_timeout(700)
        assert not sheet_open(pg) and shown_id(pg) is None, "the late card opened over the reader's open-parts"
        pg.csp_clean()
        pg.close()
    finally:
        gate.set()
        nav_clear()


def c_nav_b5_b6(b, S, engine, mode, then_tap):
    """B5 (then_tap) / B6 (the control, no tap): deep link #a1-a, whose reveal must open a1's parts: a1's step file is held, then fails ('500': a
    transport failure, the engine's error event is the parts notice; 'garbage': data that arrived invalid, the engine's error event is the
    fallback). B5: before it fails the reader taps card a2: a2's sheet is open and when the failure arrives there is NO notice and NO fallback.
    B6: nothing follows. The failure shows exactly what it showed before this round: the fallback for data that arrived invalid; for a transport failure
    the engine's notice is cleared at once by the deep link's own card opening (go() goes on into openCard, which hushes), so the observable end is the
    open sheet of the target and no notice, which is also what the page did before this round."""
    gate = threading.Event()
    try:
        pg = nav_page(b, S, False)
        gate, path = hold_step("a1", 500 if mode == "500" else None)
        if mode == "garbage":
            Handler.garbage = {path}
        at_hash(pg, "a1-a")
        held_arrived(pg, path)
        if then_tap:
            pg.wait("document.querySelector('[data-node=\"a2\"]') !== null", 5000)        # the reveal opened goal-chain on its way to a1
            tap(pg, "a2")
            pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a2'", 5000)
        gate.set()
        pg.page.wait_for_timeout(900)
        if then_tap:
            assert pg.ev("!!document.getElementById('graph-layer')") and pg.ev("document.getElementById('graph-fallback').hidden"), "the page fell back for a route the reader left"
            assert notice_text(pg) is None, "a notice from the route the reader left: %r" % notice_text(pg)
            assert shown_id(pg) == "a2" and sheet_open(pg), "a2's sheet is the open one"
        elif mode == "500":
            assert pg.ev("!!document.getElementById('graph-layer')") and pg.ev("document.getElementById('graph-fallback').hidden")
            assert shown_id(pg) == "a1-a" and sheet_open(pg) and notice_text(pg) is None, (shown_id(pg), notice_text(pg))
        else:
            assert pg.ev("!document.getElementById('graph-layer')") and pg.page.is_visible("#graph-fallback"), "arrived invalid data is the fallback"
        assert not [c for c in pg.console if c[0] == "pageerror"]
        pg.close()
    finally:
        gate.set()
        Handler.garbage = set()
        nav_clear()


def c_nav_b5b_b6b(b, S0, engine, then_tap):
    """B5b (then_tap) / B6b (the control): open-parts on card C whose parts load is held, then fails as a transport failure. B5b: before it fails the
    reader taps card D: D's sheet is open and there is NO notice when C's failure arrives. B6b: nothing follows: the parts notice appears as before
    (an open-parts route that fails keeps its notice: nothing after it hushes it)."""
    S = hold_kids_root(engine)
    try:
        pg = nav_page(b, S)
        assert pg.ev(HOLD_KIDS_JS)
        pg.page.click("#graph-sheet-tools .sheet-tool")
        wait_sheet(pg, False)
        if then_tap:
            tap(pg, "a2")
            pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a2'", 5000)
        pg.ev("(() => { window.__releaseKids(true); return true; })()")
        pg.page.wait_for_timeout(700)
        assert pg.ev("!!document.getElementById('graph-layer')") and pg.ev("document.getElementById('graph-fallback').hidden")
        if then_tap:
            assert notice_text(pg) is None, "a notice from the route the reader left: %r" % notice_text(pg)
            assert shown_id(pg) == "a2" and sheet_open(pg)
        else:
            assert notice_text(pg) == PARTS_FAILED, notice_text(pg)
        assert not [c for c in pg.console if c[0] == "pageerror"]
        pg.close()
    finally:
        S.stop()


def c_nav_b7(b, S0, engine):
    """B7 control: the READER opens a node's parts on the map (a pinch on the real engine), the load is slow and then fails, with no route awaiting it:
    the parts notice is shown exactly as before."""
    root = tempfile.mkdtemp(prefix="pg-b7-")
    assemble.assemble(root, engine, index_edit=carry_notes)
    S = Served(root)
    gate = threading.Event()
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        tap(pg, "goal-chain")
        wait_sheet(pg, True)
        pg.page.click("#graph-sheet-tools .sheet-tool")                  # goal-chain's parts (a route, finished)
        wait_sheet(pg, False)
        pg.wait("document.querySelector('[data-node=\"a1\"]') !== null", 6000)
        gate, path = hold_step("a1", 500)
        if engine == "double":     # open_on_map's evaluate would wait for the held promise (the test hook returns it); start the open without waiting
            pg.ev("(() => { document.getElementById('graph').__open('a1'); return true; })()")
        else:
            open_on_map(pg, engine, "a1", "a1-a", wait=False)
        held_arrived(pg, path)
        assert notice_text(pg) is None
        gate.set()
        pg.wait("!document.getElementById('graph-notice').hidden", 6000)
        assert notice_text(pg) == PARTS_FAILED, notice_text(pg)
        assert pg.ev("!!document.getElementById('graph-layer')") and pg.ev("document.getElementById('graph-fallback').hidden")
        assert not [c for c in pg.console if c[0] == "pageerror"]
        pg.close()
    finally:
        gate.set()
        nav_clear()
        S.stop()


def c_nav_c1(b, S0, engine):
    """C1: suppression is scoped to the pending call's nodes. Open-parts on card C (node X = a1) is pending (its children's load is held); the reader
    taps card D (a2), which supersedes it; then the reader's OWN gesture opens the parts of an UNRELATED node Y (inputs, not on X's path) whose
    load is slow and then fails (http-500, held in the page's data-layer copy like X's: the top step's file is cached, so the server cannot hold
    it): Y's parts notice APPEARS even though a superseded call is still pending. The reader then taps card a3 (clears the notice, so a
    later notice could only be new), X's load is released as a failure: no notice and no fallback come from it. Discriminates a `supersededCall`
    that ignores the node filter, or that looks only at the newest pending call."""
    S = hold_kids_root(engine)
    try:
        pg = nav_page(b, S)
        assert pg.ev(HOLD_KIDS_JS)
        assert pg.ev("(() => { const h = { fail: false }; h.p = new Promise((r) => { window.__releaseY = (fail) => { h.fail = !!fail; r(); }; }); window.__holdKids.inputs = h; return true; })()")
        pg.page.click("#graph-sheet-tools .sheet-tool")                 # X's parts: the route waits on the held load
        wait_sheet(pg, False)
        tap(pg, "a2")                                                    # supersedes it
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a2'", 5000)
        if engine == "double":
            pg.ev("(() => { document.getElementById('graph').__open('inputs'); return true; })()")
        else:
            pg.page.click("#graph-show-all")       # Y is below the fold on the real map: the reader shows all (a route that closes D's sheet and fits the camera; X's call is still pending)
            wait_sheet(pg, False)
            pg.page.wait_for_timeout(800)
            open_on_map(pg, engine, "inputs", "b1", wait=False)
        pg.page.wait_for_timeout(300)
        assert notice_text(pg) is None, "Y's load is still held"
        pg.ev("(() => { window.__releaseY(true); return true; })()")
        pg.wait("!document.getElementById('graph-notice').hidden", 6000)
        assert notice_text(pg) == PARTS_FAILED, "Y's own failed load was swallowed by an unrelated superseded call: %r" % notice_text(pg)
        tap(pg, "a3")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a3'", 5000)
        assert notice_text(pg) is None, "the card opening clears the notice"
        pg.ev("(() => { window.__releaseKids(true); return true; })()")
        pg.page.wait_for_timeout(700)
        assert notice_text(pg) is None, "a notice from the superseded call: %r" % notice_text(pg)
        assert pg.ev("!!document.getElementById('graph-layer')") and pg.ev("document.getElementById('graph-fallback').hidden"), "the page fell back"
        assert shown_id(pg) == "a3" and sheet_open(pg)
        assert not [c for c in pg.console if c[0] == "pageerror"]
        pg.close()
    finally:
        S.stop()


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


# ------------------------------------------- a map that carries no notes opens a card exactly as main does (PR 97 round 6)
# A map "carries notes" iff its index strings hold BOTH note_label and note_source. On any other map (the live one) a tap or an address opens
# the sheet at once from the markup, with no step load in its path: no fetch result can delay it or prevent it.

def c_live_open_fetch_fails(b, S, engine):
    """C1: on the live map a tap on a card whose step fetch FAILS (500) still opens the sheet, and no notice shows."""
    try:
        pg = nav_page(b, S)                                    # a1 is open; a2 and a3 are on the map with their step files not fetched
        Handler.status["/graph/step/a2.json"] = 500
        tap(pg, "a2")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a2'", 3000)
        pg.page.wait_for_timeout(500)
        assert shown_id(pg) == "a2" and sheet_open(pg), "the sheet opens although a2's step file answers 500"
        assert notice_text(pg) is None, "no notice on the live map: %r" % notice_text(pg)
        assert pg.ev("!!document.getElementById('graph-layer')") and pg.ev("document.getElementById('graph-fallback').hidden"), "no fallback"
        pg.csp_clean()
        pg.close()
    finally:
        nav_clear()


def c_live_open_fetch_held(b, S, engine):
    """C2: on the live map a tap on a card whose step fetch never settles (held) has the sheet open BEFORE it settles."""
    gate = threading.Event()
    try:
        pg = nav_page(b, S)
        gate, path = hold_step("a2")
        tap(pg, "a2")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'a2'", 3000)
        assert sheet_open(pg) and shown_id(pg) == "a2", "the sheet is open while a2's step file is still held"
        gate.set()
        pg.page.wait_for_timeout(500)
        assert shown_id(pg) == "a2" and notice_text(pg) is None
        pg.csp_clean()
        pg.close()
    finally:
        gate.set()
        nav_clear()


def c_live_sheets_match_main(b, S, engine):
    """C3: the sheet of each of the 23 live cards (opened by its address) and of the three top cards opened by a TAP (26 snapshots), the
    crumbs, the tools, the body, the class and the notice, are byte-equal to what main's page drew. fixtures/live-sheets-main.json holds only the
    SHA-256 of each snapshot (canonical JSON), generated from origin/main's page code on the same fixture, so no text is copied into the tests."""
    import hashlib
    with open(os.path.join(HERE, "fixtures", "live-sheets-main.json"), encoding="utf-8") as f:
        want = json.load(f)
    assert sorted(want) == sorted(ALL_IDS) and len(want) == 23, "the golden covers the 23 live cards"
    snap_js = """(() => { const s = document.getElementById('graph-sheet');
      return { hidden: s.hidden, cls: s.className, crumbs: document.getElementById('graph-crumbs').innerHTML,
               tools: document.getElementById('graph-sheet-tools').innerHTML, body: document.getElementById('graph-sheet-body').innerHTML,
               notice: document.getElementById('graph-notice').hidden }; })()"""
    digest = lambda v: hashlib.sha256(json.dumps(v, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    n = 0
    for card in ALL_IDS:
        pg = Pg(b, S.base + "graph/index.html#" + card, 1280, 900).settled()
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === %s" % json.dumps(card), 6000)
        assert digest(pg.ev(snap_js)) == want[card], "by address: " + card
        n += 1
        pg.close()
    for card in ("goal-chain", "inputs", "bounds"):
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        tap(pg, card)
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === %s" % json.dumps(card), 6000)
        assert digest(pg.ev(snap_js)) == want[card], "by tap: " + card
        n += 1
        pg.close()
    assert n == 26


def c_note_one_key_refused(b, S0, engine):
    """A map holding only ONE of note_label and note_source is refused at START: the page's usual fallback, the code bad-note-strings recorded as the
    failure reason, and no card opens (round 7)."""
    for drop in ("note_source", "note_label"):
        root = tempfile.mkdtemp(prefix="pg-notes1-")
        assemble.assemble(root, engine, fix="notes", index_edit=lambda i, d=drop: i["strings"].pop(d),
                          mutate={os.path.join("page", "app.js"): expose_failure})
        S = Served(root)
        try:
            pg = Pg(b, S.base + "graph/index.html#sk-file-3", 1280, 900)
            pg.wait("document.documentElement.hasAttribute('data-failure')", 6000)
            assert pg.ev("document.documentElement.getAttribute('data-failure')").startswith("bad-note-strings"), drop
            assert pg.page.is_visible("#graph-fallback") and pg.page.is_visible("#graph-cards"), drop
            assert not pg.ev("!!document.querySelector('#graph-sheet-body article')"), drop
            pg.close()
        finally:
            S.stop()


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
        assert heads == ["What a box is", "What a line is"], heads          # PR 98 round 2: the edge basis adds the key's last section
        assert rows == ["Part of the argument", "Group of files", "Lean file"], rows
        assert sw == ["swatch k-part", "swatch k-group", "swatch k-file"], sw
        # F3: the optional note is ONE plain line directly under the kind rows (the key now also holds the scope paragraph and the line paragraph)
        note = pg.ev("""(() => { const c = document.querySelector('#graph-sheet-body .key-content'), p = [...c.querySelectorAll('p.key-note')];
          return { n: p.length, text: p[0] && p[0].textContent, prev: p[0] && p[0].previousElementSibling.tagName, items: c.querySelectorAll('li').length }; })()""")
        assert note == {"n": 1, "text": "Parts and groups follow the repository's own contents list (CONTENTS.md).", "prev": "UL", "items": 3}, note
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


KEY_CHILDREN_JS = """(() => { const c = document.querySelector('#graph-sheet-body .key-content');
  return { kids: [...c.children].map(e => ({ tag: e.tagName, cls: e.className, text: e.textContent, nodes: [...e.childNodes].map(n => n.nodeType) })),
           bad: document.querySelectorAll('#graph-sheet-body img, #graph-sheet-body [onerror], #graph-sheet-body code').length,
           scripts: document.querySelectorAll('script').length }; })()"""

# The live map's key, as the base page (before the edge basis and key_scope_text) drew it, captured from a run on that head: both engines.
LIVE_KEY_HTML = ('<div class="key-content"><h2>Colour and shape: what Lean declares</h2><ul><li><span class="swatch k-theorem"></span><span>Theorem: a result the Lean code proves</span></li>'
                 '<li><span class="swatch k-def"></span><span>Definition: a named object or statement</span></li><li><span class="swatch k-structure"></span><span>Structure: a bundle of named fields</span></li></ul>'
                 '<h2>Frame: what we have read</h2><ul><li><span class="swatch k-theorem s-read"></span><span>Statement read</span></li>'
                 '<li><span class="swatch k-theorem s-census"></span><span>Statement counted by a program</span></li>'
                 '<li><span class="swatch k-theorem s-none"></span><span>Statement not read</span></li></ul></div>')


def key_of(b, engine, fix, edit=None):
    """Opens the Key sheet on a fixture (optionally edited) and returns the key's children, as {tag, cls, text, nodes} rows."""
    root = tempfile.mkdtemp(prefix="pg-key98-")
    assemble.assemble(root, engine, fix=fix, index_edit=edit)
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        pg.page.click("#graph-key")
        wait_sheet(pg, True)
        got = pg.ev(KEY_CHILDREN_JS)
        html = pg.ev("document.querySelector('#graph-sheet-body .key-content').outerHTML")
        pg.csp_clean()
        pg.close()
        return got, html
    finally:
        S.stop()


def skeleton_words():
    return json.load(open(os.path.join(assemble.HERE, "fixtures", "skeleton", "index.json"), encoding="utf-8"))["strings"]


def c_key_edge_basis(b, S0, engine):
    """E3, K1 on the skeleton: the key's FIRST child is the scope paragraph (class key-scope, one text node, backticks kept as characters), and
    AFTER everything it shows today comes an h2 with key_lines_heading and one p with the strings key edge_basis.words names, one text node each."""
    w = skeleton_words()
    got, _ = key_of(b, engine, "skeleton")
    kids = got["kids"]
    assert [k["tag"] for k in kids] == ["P", "H2", "UL", "P", "H2", "P"], [k["tag"] for k in kids]
    assert kids[0]["cls"] == "key-scope" and kids[0]["text"] == w["key_scope_text"] and kids[0]["nodes"] == [3], kids[0]
    assert "`src/Statements.lean`" in kids[0]["text"], "the backticks stay characters"
    assert kids[3]["cls"] == "key-note", kids[3]
    assert kids[4]["text"] == w["key_lines_heading"] == "What a line is" and kids[4]["nodes"] == [3], kids[4]
    assert kids[5]["text"] == w["key_lines_text"] and kids[5]["nodes"] == [3], kids[5]
    assert got["bad"] == 0, "no code element, image or handler in the key"
    # the page prints strings[words], never a key it names itself: words names ANOTHER key here, and key_lines_text is gone
    def other(i):
        i["strings"]["test_words"] = "The words of a test key"
        del i["strings"]["key_lines_text"]
        i["edge_basis"]["words"] = "test_words"
    got2, _ = key_of(b, engine, "skeleton", other)
    assert got2["kids"][-1]["tag"] == "P" and got2["kids"][-1]["text"] == "The words of a test key", got2["kids"][-1]


def c_key_edge_basis_after_states(b, S0, engine):
    """The line section comes AFTER the states section: a map with a non-empty symbols.order.states AND edge_basis (+ key_scope_text, key_kinds_note)
    has the key's children, in order, scope p, kinds h2, kinds ul, kinds note p, states h2, states ul, lines h2, lines p."""
    w = skeleton_words()
    def edit(i):
        i["symbols"]["order"]["states"] = ["read", "census", "none"]
    got, _ = key_of(b, engine, "skeleton", edit)
    kids = got["kids"]
    assert [k["tag"] for k in kids] == ["P", "H2", "UL", "P", "H2", "UL", "H2", "P"], [k["tag"] for k in kids]
    assert kids[0]["cls"] == "key-scope" and kids[3]["cls"] == "key-note", [k["cls"] for k in kids]
    assert kids[4]["text"] == w["key_states_heading"], kids[4]
    assert kids[6]["text"] == w["key_lines_heading"] and kids[7]["text"] == w["key_lines_text"], (kids[6], kids[7])


def c_key_absent_keys(b, S0, engine):
    """No edge_basis, no key_scope_text, no key_lines_*: nothing is drawn for them (the key is the kinds section and the optional note only)."""
    def edit(i):
        del i["edge_basis"]
        for k in ("key_scope_text", "key_lines_heading", "key_lines_text"):
            del i["strings"][k]
    got, _ = key_of(b, engine, "skeleton", edit)
    assert [k["tag"] for k in got["kids"]] == ["H2", "UL", "P"], got["kids"]
    assert [k["cls"] for k in got["kids"]] == ["", "", "key-note"], got["kids"]
    # key_scope_text alone (no edge_basis): the scope paragraph only, first
    def scope_only(i):
        del i["edge_basis"]
        del i["strings"]["key_lines_heading"]
        del i["strings"]["key_lines_text"]
    got2, _ = key_of(b, engine, "skeleton", scope_only)
    assert [k["tag"] for k in got2["kids"]] == ["P", "H2", "UL", "P"] and got2["kids"][0]["cls"] == "key-scope", got2["kids"]


def c_key_live_unchanged(b, S0, engine):
    """The live map carries none of the new keys: its key's DOM is byte-identical to the base head's (the literal above)."""
    _got, html = key_of(b, engine, None)
    assert html == LIVE_KEY_HTML, html


def c_key_hostile(b, S0, engine):
    """key_scope_text and the words value hold markup: both are text in the key, never elements."""
    payload = "<img src=x onerror=1>"
    def edit(i):
        i["strings"]["key_scope_text"] = payload
        i["strings"]["key_lines_text"] = payload
    got, _ = key_of(b, engine, "skeleton", edit)
    kids = got["kids"]
    assert kids[0]["text"] == payload and kids[0]["nodes"] == [3], kids[0]
    assert kids[-1]["text"] == payload and kids[-1]["nodes"] == [3], kids[-1]
    assert got["bad"] == 0 and got["scripts"] == 1, got


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


START_CALL = "start(document, { createGraph, fetch: (address) => fetch(address) });"


def expose_failure(src):
    """Test-only: the page keeps the reason of a failed start in the object start() returns, and nothing reads it; hang it on <html> so a case can."""
    assert START_CALL in src, "the page's last line is not the one this case rewrites"
    return src.replace(START_CALL, START_CALL[:-1] + ".then((f) => { if (f.reason !== null) document.documentElement.setAttribute('data-failure', f.reason); });")


def spoil_card_height(src):
    """Test-only: make another option bad (the card height), so the engine refuses for a reason that is not the floor."""
    assert "nodeH: 140, gapY: 56" in src, "CARD_SIZES edit did not match"
    return src.replace("nodeH: 140, gapY: 56", "nodeH: -1, gapY: 56")


def floor_run(b, engine, floor, spoil=False):
    """Boot the skeleton with an open_scale_floor of `floor`; returns the failure reason the page recorded ('' when it booted)."""
    root = tempfile.mkdtemp(prefix="pg-v3f-")
    mut = (lambda src: spoil_card_height(expose_failure(src))) if spoil else expose_failure
    assemble.assemble(root, engine, fix="skeleton", index_edit=lambda i: i.__setitem__("open_scale_floor", floor), mutate={os.path.join("page", "app.js"): mut})
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900)
        pg.wait("document.documentElement.hasAttribute('data-failure') || document.querySelector('[data-node=\"sk-part\"]') !== null", 6000)
        if pg.ev("document.documentElement.hasAttribute('data-failure')"):
            reason = pg.ev("document.documentElement.getAttribute('data-failure')")
            assert pg.page.is_visible("#graph-fallback") and pg.page.is_visible("#graph-cards")
        else:
            reason = ""
        pg.close()
        return reason
    finally:
        S.stop()


def c_v3_floor_named(b, S0, engine):
    """98 round 4 (real engine only; the double does not check options): an open_scale_floor below zoom.min (0.01, 0.05) or above the open-framing cap
    (1.3, 2) is the fallback with the reason `bad-scale-floor` recorded, the page's own refusal made by the engine's own rule (checkOptions); never the
    engine's TypeError text. A floor of 1 is the control and boots."""
    if engine != "real":
        return
    for f in (0.01, 0.05, 1.3, 2):
        r = floor_run(b, engine, f)
        assert r.startswith("bad-scale-floor: ") and str(f) in r, (f, r)
        assert "graph options" not in r, r
    assert floor_run(b, engine, 1) == ""


def c_v3_floor_valid_other_bad(b, S0, engine):
    """98 round 4 (real engine only): a VALID floor (1) beside another bad option (the card height, made -1 by a test-only edit of app.js) is a plain
    start failure with the engine's own text, never bad-scale-floor: the floor is blamed only when taking it away makes the engine accept."""
    if engine != "real":
        return
    r = floor_run(b, engine, 1, spoil=True)
    assert r != "" and not r.startswith("bad-scale-floor"), r
    assert "sizes.nodeH" in r, r


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

def open_on_map(pg, engine, node_id, child_id, wait=True):
    """Open a node on the MAP while the sheet is up: the double does what a semantic zoom does; the real engine is zoomed with
    ctrl + wheel over the node until it opens itself. wait=False returns without waiting for the child (a load that is meant to fail)."""
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
    if wait:
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
    """B's parts are opened ON THE MAP (the engine loads B's step, which no card opening has fetched yet: a card opened on the sheet loads its own
    step file, so the sheet's parts button always finds it cached): same split, through the engine's load-failed event."""
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
        pat = fail_step(pg, "a1", mode)
        open_on_map(pg, engine, "a1", "a1-a", wait=False)               # open a1's parts on the map: its step file is fetched now
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


# ---------------------------------------------------------------- the repository's note on the sheet (fixtures/notes)

NOTE_KIDS_JS = """(() => { const a = document.querySelector('#graph-sheet-body article');
  return [...a.children].map(e => e.tagName + '.' + e.className); })()"""
NOTE_BODY_JS = """(() => { const b = document.querySelector('#graph-sheet-body .note-body'); if (!b) return null;
  const all = [...b.querySelectorAll('*')], sheet = document.getElementById('graph-sheet-body');
  return { tags: [...new Set(all.map(e => e.tagName))].sort(),
           attrs: [...new Set(all.flatMap(e => [...e.attributes].map(a => e.tagName + ':' + a.name)))].sort(),
           text: b.textContent, kids: [...b.children].map(e => e.tagName),
           stray: sheet.querySelectorAll('img, script, a, iframe, b, u, i, em, strong, style, svg').length,
           handlers: [...sheet.querySelectorAll('*')].filter(e => [...e.attributes].some(a => /^on/i.test(a.name))).length }; })()"""


def _notes_site(engine, **edits):
    root = tempfile.mkdtemp(prefix="pg-notes-")
    assemble.assemble(root, engine, fix="notes", **edits)
    return Served(root)


def c_note_sheet(b, S0, engine):
    """N12/N14/N2: opening a file card with a note shows, after the kind word line, the label, the source line ({source} as text, {commit} the
    first 8 characters of the step's commit) and then the rendered note, in that order; the note's first '# ' line is kept (as an h3.note-h)
    even though it equals the card title; a card without a note shows none of them; closing puts the card's markup back."""
    S = _notes_site(engine)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        before = pg.ev("document.getElementById('graph-cards').outerHTML")
        at_hash(pg, "sk-file-1")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'sk-file-1'", 6000)
        pg.wait("document.querySelector('#graph-sheet-body .note-body')", 6000)
        kids = pg.ev(NOTE_KIDS_JS)
        assert kids[:5] == ["H3.claim", "P.sheet-status", "P.note-label", "P.note-source", "DIV.note-body"], kids
        assert kids[5] == "P.note", kids          # the builder's own line is still there, after ours
        assert pg.ev("document.querySelector('#graph-sheet-body .note-label').textContent") == "From the repository, unchanged"
        src = pg.ev("document.querySelector('#graph-sheet-body .note-source').textContent")
        assert src == "Source file: grh/src/New/Reduction/OneSidedBound.lean \u00b7 version 01234567 of lsernau/grh-lean", src
        assert pg.ev("document.querySelectorAll('#graph-sheet-body .note-source *, #graph-sheet-body .note-label *').length") == 0, "text only, never a link"
        body = pg.ev(NOTE_BODY_JS)
        assert body["kids"] == ["H3", "P", "P", "UL"], body["kids"]
        assert body["tags"] == ["CODE", "H3", "LI", "P", "UL"], body["tags"]
        assert body["attrs"] == ["H3:class"], body["attrs"]
        assert "Here \u03bb(n) = \u039b(n) (1 - chiK d n) for n \u2261 1 modulo q and 0 otherwise" in body["text"], body["text"][-400:]
        assert body["stray"] == 0 and body["handlers"] == 0, body
        # N14: the first '# ' line equals the card title and is KEPT, with the note heading class
        h = pg.ev("""(() => { const hs = [...document.querySelectorAll('#graph-sheet-body h3')];
          return hs.map(e => [e.className, e.textContent]); })()""")
        title = "The one-sided bound, and the theorem in half-plane form"
        assert h == [["claim", title], ["note-h", title]], h
        # a card without a note shows none of it
        at_hash(pg, "sk-file-3")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'sk-file-3'", 6000)
        kids3 = pg.ev(NOTE_KIDS_JS)
        assert kids3[:3] == ["H3.claim", "P.sheet-status", "P.note"], kids3
        assert pg.ev("document.querySelectorAll('.note-label, .note-source, .note-body, .note-h').length") == 0
        # closing puts the markup back: no note element is left in any article
        at_hash(pg, "sk-file-1")
        pg.wait("document.querySelector('#graph-sheet-body .note-body')", 6000)
        pg.page.click("#graph-sheet-close")
        wait_sheet(pg, False)
        assert pg.ev("document.querySelectorAll('.note-label, .note-source, .note-body, .note-h').length") == 0
        after = pg.ev("document.getElementById('graph-cards').outerHTML")
        assert after.replace(' open=""', "") == before.replace(' open=""', ""), "closing must put the markup back"
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_note_tap_and_hostile(b, S0, engine):
    """N9 in the browser, and the TAP route: a tap on a card whose step file has not been fetched yet loads it, then shows its note. The
    hostile note renders as visible text: only the allowed elements, the only attributes are the heading class and `start`, no element
    from the payloads exists, no dialog, no CSP violation."""
    S = _notes_site(engine)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        at_hash(pg, "sk-file-1")
        pg.wait("document.querySelector('#graph-sheet-body .note-body')", 6000)
        Handler.seen.clear()
        tap(pg, "sk-file-2")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'sk-file-2'", 6000)
        pg.wait("document.querySelector('#graph-sheet-body .note-body')", 6000)
        assert "/graph/step/sk-file-2.json" in Handler.seen, Handler.seen
        assert pg.ev("document.querySelectorAll('#graph-sheet-body .note-body').length") == 1
        body = pg.ev(NOTE_BODY_JS)
        assert body["tags"] == ["CODE", "H3", "LI", "OL", "P", "PRE", "TABLE", "TBODY", "TD", "TH", "THEAD", "TR", "UL"], body["tags"]
        assert body["attrs"] == ["H3:class", "OL:start"], body["attrs"]
        assert body["stray"] == 0 and body["handlers"] == 0, body
        for want in ("<script>alert(1)</script>", "<img src=x onerror=1> &amp;lt; javascript:alert(1) [x](javascript:y) <b>bold</b>", "<img src=x onerror=2>",
                     "javascript:void(0)", "[y](javascript:z)", "<iframe src=javascript:alert(3)></iframe>", "<b>h</b>", "&lt;"):
            assert want in body["text"], (want, body["text"])
        assert pg.ev("document.querySelector('#graph-sheet-body .note-body ol').getAttribute('start')") == "3"
        assert pg.ev("document.querySelector('#graph-sheet-body .note-source').textContent") == \
            "Source file: grh/src/New/Hostile.lean \u00b7 version 01234567 of lsernau/grh-lean"
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_note_strings(b, S0, engine):
    """N13 in the browser: a map lacking the note keys (both: one alone is refused at start, round 7) whose reader opens a step carrying a note gets the page's usual failure (the
    fallback; no half-filled label); a note_source template with markup in it is text; the live map's sheet carries none of it."""
    def no_note_words(i):
        i["strings"].pop("note_source")
        i["strings"].pop("note_label")
    for drop in ("neither",):
        S = _notes_site(engine, index_edit=no_note_words)
        try:
            pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
            at_hash(pg, "sk-file-1")
            pg.wait("!document.getElementById('graph-layer')", 6000)
            assert pg.page.is_visible("#graph-fallback") and pg.page.is_visible("#graph-cards")
            assert pg.ev("document.querySelectorAll('.note-label, .note-source, .note-body').length") == 0
            pg.close()
        finally:
            S.stop()
    # the same map with a card that has no note: no failure at all
    S = _notes_site(engine, index_edit=no_note_words)
    try:
        pg = Pg(b, S.base + "graph/index.html#sk-file-3", 1280, 900).settled()
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'sk-file-3'", 6000)
        assert pg.ev("document.getElementById('graph-fallback').hidden")
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()
    # a template with markup: filled and shown as text
    S = _notes_site(engine, index_edit=lambda i: i["strings"].__setitem__("note_source", "<b>Source</b> {commit} &amp; {source} {source}"))
    try:
        pg = Pg(b, S.base + "graph/index.html#sk-file-1", 1280, 900).settled()
        pg.wait("document.querySelector('#graph-sheet-body .note-source')", 6000)
        t = pg.ev("document.querySelector('#graph-sheet-body .note-source').textContent")
        assert t == "<b>Source</b> 01234567 &amp; grh/src/New/Reduction/OneSidedBound.lean grh/src/New/Reduction/OneSidedBound.lean", t
        assert pg.ev("document.querySelectorAll('#graph-sheet-body .note-source *').length") == 0
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_note_load_failure(b, S0, engine):
    """A tap on a card whose step file cannot be loaded leaves the reader's open card exactly as it was and shows the page's notice
    (the step is loaded BEFORE the open card is touched)."""
    S = _notes_site(engine)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        at_hash(pg, "sk-file-1")
        pg.wait("document.querySelector('#graph-sheet-body .note-body')", 6000)
        Handler.blocked = {"/graph/step/sk-file-2.json"}
        tap(pg, "sk-file-2")
        pg.wait("!document.getElementById('graph-notice').hidden", 6000)
        assert shown_id(pg) == "sk-file-1" and sheet_open(pg)
        assert pg.ev("document.querySelectorAll('#graph-sheet-body .note-body').length") == 1
        assert pg.ev("document.getElementById('graph-fallback').hidden")
        pg.csp_clean()
        pg.close()
    finally:
        Handler.blocked = set()
        S.stop()


def c_note_open_throws(b, S0, engine):
    """A card opening whose sheet THROWS after the step loaded (a plain exception, not a data refusal) is the page's fallback and an
    unhandled rejection is not left behind: the tap route is now asynchronous, so its exception must be caught inside it."""
    def mut(text):
        old = "    const rec = adopt(article, true);\n"
        assert text.count(old) == 1
        return text.replace(old, old + '    throw new Error("the sheet failed after the load");\n')
    root = tempfile.mkdtemp(prefix="pg-open-throws-")
    assemble.assemble(root, engine, mutate={os.path.join("page", "sheet.js"): mut})
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        tap(pg, "goal-chain")
        pg.wait("!document.getElementById('graph-layer')", 6000)
        assert pg.page.is_visible("#graph-fallback") and pg.ev("document.querySelectorAll('#graph-cards article').length") == 23
        assert not [c for c in pg.console if c[0] == "pageerror"], pg.console
        pg.close()
    finally:
        S.stop()


def c_note_live_unchanged(b, S, engine):
    """N11: on the live real fixture no step carries a note, so a card's sheet holds no note label, source line or body, and its children
    are the claim, the status line and the builder's own lines as before."""
    for card in ("goal-chain", "a1-a-1-x"):
        pg = Pg(b, S.base + "graph/index.html#" + card, 1280, 900).settled()
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === %s" % json.dumps(card), 6000)
        assert pg.ev("document.querySelectorAll('.note-label, .note-source, .note-body, .note-h').length") == 0, card
        kids = pg.ev(NOTE_KIDS_JS)
        assert kids[0] == "H3.claim" and kids[1] == "P.sheet-status", kids
        assert not any(k.startswith(("DIV.note", "P.note-")) for k in kids), kids
        pg.csp_clean()
        pg.close()



# ---------------------------------------------------------------- the maths face on the sheet (fixtures/typeset)

TYPESET_NEW = ("note_label_typeset", "note_typeset_line", "note_exact_button", "note_render_button")
LABEL_TYPESET = "The file's opening note, from the repository"
LABEL_EXACT = "The file's opening note, from the repository, unchanged"
LINE_WORDS = "Formulas are set in maths type by us from the repository's text, so some signs (such as ^ for a power) look different. Tap Show the exact text to see it as written."
BUTTON_EXACT = "Show the exact text"
BUTTON_RENDER = "Show the note with formulas set in maths type"
TYPESET_KIDS = ["H3.claim", "P.sheet-status", "P.note-label", "P.note-source", "P.note-typeset-line", "BUTTON.note-toggle", "DIV.note-body", "P.note"]
TYPESET_STATE_JS = """(() => { const b = document.querySelector('#graph-sheet-body .note-body'), t = document.querySelector('#graph-sheet-body .note-toggle');
  const l = document.querySelector('#graph-sheet-body .note-label'), ln = document.querySelector('#graph-sheet-body .note-typeset-line');
  return { label: l && l.textContent, line: ln ? ln.textContent : null, button: t ? t.textContent : null, pressed: t ? t.getAttribute('aria-pressed') : null,
           type: t ? t.getAttribute('type') : null, body: b ? b.innerHTML : null, text: b ? b.textContent : null,
           kids: b ? [...b.children].map(e => e.tagName) : null, maths: b ? b.querySelectorAll('span.m').length : null,
           pres: b ? b.querySelectorAll('pre').length : null }; })()"""


def _typeset_site(engine, **edits):
    root = tempfile.mkdtemp(prefix="pg-typeset-")
    assemble.assemble(root, engine, fix="typeset", **edits)
    return Served(root)


def _fixture_note(step):
    with open(os.path.join(HERE, "fixtures", "typeset", "step", step + ".json"), encoding="utf-8") as f:
        return json.load(f)["note"]["text"]


def _open_note(pg, card):
    at_hash(pg, card)
    pg.wait("document.querySelector('#graph-sheet-body article')?.id === %s" % json.dumps(card), 6000)
    pg.wait("document.querySelector('#graph-sheet-body .note-body')", 6000)


def c_typeset_sheet(b, S0, engine):
    """L1/T4/T6: with all four strings present a note's sheet shows label (typeset words), source line, the maths-type line, the button and the
    note, in that order; formula and one-letter spans are span.m (m1 for one letter) in a serif, upright, unboxed face at the paragraph's size;
    names stay code. The button (aria-pressed false) replaces the rendering with ONE pre holding the note's text verbatim, backticks included, under
    the exact-view label, with the render words and aria-pressed true; pressing it again returns the rendering unchanged. Escape closes the sheet and
    the next opening starts on the rendering."""
    S = _typeset_site(engine)
    try:
        pg = Pg(b, S.base + "graph/index.html", 390, 844).settled()
        _open_note(pg, "sk-file-3")
        assert pg.ev(NOTE_KIDS_JS) == TYPESET_KIDS, pg.ev(NOTE_KIDS_JS)
        st = pg.ev(TYPESET_STATE_JS)
        assert st["label"] == LABEL_TYPESET and st["line"] == LINE_WORDS and st["button"] == BUTTON_EXACT, st
        assert st["pressed"] == "false" and st["type"] == "button", st
        assert pg.ev("document.querySelector('#graph-sheet-body .note-source').textContent") == \
            "Opening note of grh/src/New/OneLift/ComparisonOperator/LineCoordinates.lean · version 01234567 of lsernau/grh-lean"
        body = pg.ev(NOTE_BODY_JS)
        assert body["tags"] == ["CODE", "H3", "H4", "LI", "P", "SPAN", "SUP", "UL"], body["tags"]
        assert body["attrs"] == ["H3:class", "H4:class", "SPAN:class"], body["attrs"]
        assert body["stray"] == 0 and body["handlers"] == 0, body
        assert st["maths"] >= 10, st["maths"]
        # the face: serif, upright, the paragraph's size, no box
        look = pg.ev("""(() => { const m = document.querySelector('#graph-sheet-body .note-body p span.m'), p = m.parentElement;
          const cm = getComputedStyle(m), cp = getComputedStyle(p), cc = getComputedStyle(document.querySelector('#graph-sheet-body .note-body code'));
          return { family: cm.fontFamily, style: cm.fontStyle, size: cm.fontSize, psize: cp.fontSize, bg: cm.backgroundColor, bw: cm.borderTopWidth,
                   pad: cm.paddingLeft, codefamily: cc.fontFamily, pfamily: cp.fontFamily, kids: m.childNodes.length, cls: m.className }; })()""")
        assert look["style"] == "normal" and look["size"] == look["psize"] and look["bw"] == "0px" and look["bg"] == "rgba(0, 0, 0, 0)", look
        assert "monospace" not in look["family"] and look["family"] == look["pfamily"] and look["family"] != look["codefamily"], look
        assert look["kids"] == 1 and look["cls"].split()[0] == "m", look
        assert pg.ev("document.querySelectorAll('#graph-sheet-body .note-body span.m1').length") >= 1
        assert all(c == "m m1" for c in pg.ev("[...document.querySelectorAll('#graph-sheet-body .note-body span.m1')].map(e => e.className)"))
        assert pg.ev("document.documentElement.scrollWidth <= window.innerWidth"), "no horizontal overflow at 390"
        rendered = st
        # the button: the exact text, verbatim
        pg.page.click("#graph-sheet-body .note-toggle")
        ex = pg.ev(TYPESET_STATE_JS)
        assert ex["pressed"] == "true" and ex["button"] == BUTTON_RENDER and ex["label"] == LABEL_EXACT, ex
        assert ex["kids"] == ["PRE"] and ex["pres"] == 1 and ex["maths"] == 0, ex
        assert ex["text"] == _fixture_note("sk-file-3") and "`" in ex["text"], "the exact text, every character, backticks included"
        assert pg.ev("document.querySelector('#graph-sheet-body .note-body pre').childNodes.length") == 1, "one text node"
        assert ex["line"] is None, "the maths-type line is told only of the maths-type view"
        assert pg.ev(NOTE_KIDS_JS)[:4] == ["H3.claim", "P.sheet-status", "P.note-label", "P.note-source"]
        assert pg.ev("document.querySelector('#graph-sheet-body .note-source').textContent").startswith("Opening note of grh/src/New/")
        # and back
        pg.page.click("#graph-sheet-body .note-toggle")
        back = pg.ev(TYPESET_STATE_JS)
        assert back == rendered, (back["pressed"], back["button"], back["label"])
        assert pg.ev(NOTE_KIDS_JS) == TYPESET_KIDS
        # Escape (not Back) closes the sheet from the exact view; the next opening starts on the rendering; nothing of the note is left behind
        pg.page.click("#graph-sheet-body .note-toggle")
        assert pg.ev(TYPESET_STATE_JS)["pressed"] == "true"
        pg.page.keyboard.press("Escape")
        wait_sheet(pg, False)
        assert pg.ev("document.querySelectorAll('.note-label, .note-source, .note-body, .note-toggle, .note-typeset-line, .m').length") == 0
        _open_note(pg, "sk-file-1")
        again = pg.ev(TYPESET_STATE_JS)
        assert again["pressed"] == "false" and again["label"] == LABEL_TYPESET and again["button"] == BUTTON_EXACT and again["pres"] == 0, again
        # a card without a note has none of it; the button is gone with the sheet's content
        at_hash(pg, "sk-file-4")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'sk-file-4'", 6000)
        assert pg.ev("document.querySelectorAll('.note-label, .note-source, .note-body, .note-toggle, .note-typeset-line').length") == 0
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_typeset_hostile(b, S0, engine):
    """T4 in the browser: formula-class spans whose characters would be markup (`<b>x</b>`, `a<i>b`, `x&y`) are span.m text; no b, i or other element
    comes of them; in the exact view they are the characters of one pre."""
    S = _typeset_site(engine)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        _open_note(pg, "sk-file-2")
        body = pg.ev(NOTE_BODY_JS)
        assert body["stray"] == 0 and body["handlers"] == 0, body
        assert body["tags"] == ["CODE", "H3", "LI", "OL", "P", "PRE", "SPAN", "SUB", "SUP", "TABLE", "TBODY", "TD", "TH", "THEAD", "TR", "UL"], body["tags"]
        assert body["attrs"] == ["H3:class", "OL:start", "SPAN:class"], body["attrs"]
        spans = pg.ev("[...document.querySelectorAll('#graph-sheet-body .note-body span.m')].map(e => [e.className, e.childNodes.length, e.textContent])")
        assert ["m", 1, "<b>x</b>"] in spans and ["m", 1, "a<i>b"] in spans and ["m", 1, "x&y"] in spans, spans
        assert pg.ev("document.querySelectorAll('#graph-sheet-body .note-body b, #graph-sheet-body .note-body i, #graph-sheet-body .note-body img, #graph-sheet-body .note-body script').length") == 0
        pg.page.click("#graph-sheet-body .note-toggle")
        ex = pg.ev(TYPESET_STATE_JS)
        assert ex["kids"] == ["PRE"] and ex["text"] == _fixture_note("sk-file-2"), ex["kids"]
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_typeset_scripts(b, S0, engine):
    """The maths face sets scripts: on the synthetic note of sk-file-2 a set span (`y ^ 12`, `P_d^N`, `x^{a_i}` written with a Greek a) holds a <sup> or <sub> and no
    `.m` text holds ^ or _; a refused span (`x^-1`, `a ^ b ^ c`) is <code> with its characters as typed; sup and sub carry no attribute; the exact
    view is byte-equal to the note."""
    S = _typeset_site(engine)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
        _open_note(pg, "sk-file-2")
        got = pg.ev("""(() => { const b = document.querySelector('#graph-sheet-body .note-body');
          const ms = [...b.querySelectorAll('span.m')];
          const scr = [...b.querySelectorAll('sup, sub')];
          return { mathsText: ms.map(e => e.textContent), badMaths: ms.filter(e => /[\\^_]/.test(e.textContent)).length,
                   sets: ms.filter(e => e.querySelector('sup, sub')).map(e => [e.textContent, e.innerHTML]),
                   attrs: scr.flatMap(e => [...e.attributes].map(a => e.tagName + ':' + a.name)),
                   codes: [...b.querySelectorAll('code')].map(e => e.textContent), supInCode: b.querySelectorAll('code sup, code sub').length }; })()""")
        assert got["badMaths"] == 0, got["mathsText"]
        assert ["y12", "y<sup>12</sup>"] in got["sets"], got["sets"]
        assert ["PδN", "P<sub>δ</sub><sup>N</sup>"] in got["sets"], got["sets"]
        assert ["xαi", "x<sup>α<sub>i</sub></sup>"] in got["sets"], got["sets"]
        assert got["attrs"] == [] and got["supInCode"] == 0, got
        assert "x^-1" in got["codes"] and "a ^ b ^ c" in got["codes"], got["codes"]
        assert not any(("x^-1" in t or "a ^ b ^ c" in t) for t in got["mathsText"]), got["mathsText"]
        pg.page.click("#graph-sheet-body .note-toggle")
        ex = pg.ev(TYPESET_STATE_JS)
        assert ex["kids"] == ["PRE"] and ex["text"] == _fixture_note("sk-file-2") and "y ^ 12" in ex["text"], ex["kids"]
        pg.csp_clean()
        pg.close()
    finally:
        S.stop()


def c_typeset_gate(b, S0, engine):
    """T5/L1 in the browser: a map that has note_label and note_source but lacks ANY ONE of the four maths-face strings renders the note exactly as the
    round-1 page does (same words, same body markup as the notes map): no span.m, no line, no button, the exact-view label."""
    S1 = _notes_site(engine)
    try:
        pg = Pg(b, S1.base + "graph/index.html", 1280, 900).settled()
        _open_note(pg, "sk-file-1")
        round1 = pg.ev(TYPESET_STATE_JS)
        kids1 = pg.ev(NOTE_KIDS_JS)
        pg.close()
    finally:
        S1.stop()
    assert round1["button"] is None and round1["line"] is None and round1["maths"] == 0 and round1["label"] == "From the repository, unchanged", round1
    for drop in TYPESET_NEW:
        S = _typeset_site(engine, index_edit=lambda i, d=drop: i["strings"].pop(d))
        try:
            pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
            _open_note(pg, "sk-file-1")
            st = pg.ev(TYPESET_STATE_JS)
            assert st["button"] is None and st["line"] is None and st["maths"] == 0 and st["pressed"] is None, (drop, st)
            assert st["label"] == LABEL_EXACT, (drop, st["label"])
            assert st["body"] == round1["body"], drop
            assert pg.ev(NOTE_KIDS_JS) == kids1, (drop, pg.ev(NOTE_KIDS_JS))
            assert pg.ev("document.querySelectorAll('#graph-sheet-body .note-body code').length") == round1["body"].count("<code>")
            pg.csp_clean()
            pg.close()
        finally:
            S.stop()


def c_typeset_review(b, S0, engine):
    """L2 in the browser: a note carrying review {"state": "converter"} draws exactly what the same note without it draws (the sheet's whole body)."""
    got = []
    for strip in (False, True):
        edit = (lambda steps: steps["sk-file-3"]["note"].pop("review")) if strip else None
        S = _typeset_site(engine, step_edit=edit)
        try:
            pg = Pg(b, S.base + "graph/index.html", 1280, 900).settled()
            _open_note(pg, "sk-file-3")
            got.append(pg.ev("document.getElementById('graph-sheet-body').innerHTML"))
            assert "review" not in got[-1] and "converter" not in got[-1]
            pg.csp_clean()
            pg.close()
        finally:
            S.stop()
    assert got[0] == got[1], "a review field changed what is drawn"


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


# ---------------------------------------------------------------------------------------------------------- made cards
# The assembler writes an EMPTY card block (its clause A7: the page has no card articles): the cards block of the page is the
# graph-about section and nothing else. A card the markup lacks is MADE from the data (app.js madeCard); a card the markup has is
# used as it is. The tree is the skeleton map with notes (fixtures/notes), its titles and its one note made SYNTHETIC at assembly time.
MADE_VIEWS = [(390, 844, True), (1280, 900, False)]
MADE_ABOUT_BLOCK = ('<section id="graph-about" data-page-feedback="off">\n<p>Synthetic about words for the made-card cases.</p>\n'
                    '<p class="roots-only">Synthetic roots-only sentence.</p>\n</section>\n')
MADE_TITLES = {"sk-file-1": "Synthetic file one with a `code span` in it", "sk-file-4": "Synthetic file four with `two words`",
               "sk-file-5": "Synthetic file five", "sk-group-b": "Synthetic group b"}
MADE_FILE1_PLAIN = "Synthetic file one with a code span in it"
MADE_NOTE = {"text": "# Synthetic note heading\n\nA synthetic paragraph of the note.\n", "source": "synthetic/FileOne.lean"}


def made_steps(steps):
    for sid, title in MADE_TITLES.items():
        steps[sid]["card"]["title"] = title
        for s in steps.values():
            for c in s["children"]:
                if c["id"] == sid:
                    c["title"] = title
    steps["sk-file-1"]["note"] = dict(MADE_NOTE)


def made_served(engine, cards):
    root = tempfile.mkdtemp(prefix="pg-made-")
    assemble.assemble(root, engine, fix="notes", cards_edit=lambda c: cards, step_edit=made_steps)
    return Served(root)


MADE_STATE_JS = """(() => { const b = document.getElementById('graph-sheet-body'), c = b.firstElementChild;
  if (!c) return null;
  const cl = c.querySelector('.claim'), nl = c.querySelector('.note-label'), ns = c.querySelector('.note-source'), nb = c.querySelector('.note-body');
  return { n: b.childElementCount, tag: c.tagName, cls: c.className, id: c.getAttribute('id'), dataId: c.getAttribute('data-id'),
    claim: cl && cl.textContent, codes: cl ? cl.querySelectorAll('code').length : -1, visible: !!cl && cl.offsetHeight > 0 && !document.getElementById('graph-sheet').hidden,
    kids: [...c.children].map(e => e.tagName + '.' + e.className), status: cl && cl.nextElementSibling && cl.nextElementSibling.textContent,
    note: nb ? { label: nl.textContent, source: ns.textContent, body: nb.textContent } : null }; })()"""


def made_wait_claim(pg, text):
    pg.wait("document.querySelector('#graph-sheet-body .claim')?.textContent === %s" % json.dumps(text), 6000)


def made_healthy(pg):
    assert pg.ev("document.getElementById('graph-fallback').hidden === true && !document.getElementById('graph-layer').hidden"), "the page fell back"
    pg.csp_clean()


def made_expect(pg, sid, tag, claim, word, with_note=False, codes=0, markup_id=None):
    made_wait_claim(pg, claim)
    st = pg.ev(MADE_STATE_JS)
    assert st["n"] == 1 and st["tag"] == tag and st["id"] == markup_id and st["dataId"] is None, (sid, st)
    assert st["cls"] == "card" and st["claim"] == claim and st["codes"] == codes and st["visible"], (sid, st)
    if tag == "DIV":      # a made card holds nothing but what the sheet puts in it
        assert st["kids"][:2] == ["H3.claim", "P.sheet-status"] and st["status"] == word, (sid, st)
        want = ["H3.claim", "P.sheet-status", "P.note-label", "P.note-source", "DIV.note-body"] if with_note else ["H3.claim", "P.sheet-status"]
        assert st["kids"] == want, (sid, st["kids"])
    if with_note:
        assert st["note"]["label"] == "From the repository, unchanged" and "A synthetic paragraph of the note." in st["note"]["body"], (sid, st["note"])
        assert st["note"]["source"].startswith("Source file: synthetic/FileOne.lean"), st["note"]
    else:
        assert st["note"] is None, (sid, st["note"])


def c_made_deep_link(b, S0, engine, w, h, mobile):
    """B1: on a tree whose card block is the assembler's (no articles), a deep link to a part, a group and a file opens the sheet, the title is the
    .claim (a backtick span a code element), the status line follows it, the note section shows for a file with a note and not for one without."""
    S = made_served(engine, MADE_ABOUT_BLOCK)
    try:
        pg = Pg(b, S.base + "graph/index.html#sk-part", w, h, mobile=mobile).settled()
        made_expect(pg, "sk-part", "DIV", "Part sk-part", "Part")
        for sid, claim, word, note, codes in (("sk-group-a", "Group sk-group-a", "Group", False, 0), ("sk-file-1", MADE_FILE1_PLAIN, "File", True, 1),
                                              ("sk-file-3", "File sk-file-3", "File", False, 0)):
            at_hash(pg, sid)
            made_expect(pg, sid, "DIV", claim, word, note, codes)
        made_healthy(pg)
        pg.close()
    finally:
        S.stop()


# ---- the Graph view (graphview.js): the switch, the lazy read of spine.json, the spine drawn by a second engine, the failure event ----
GV_INIT = ("window.__gp = []; window.__gpmeta = []; document.addEventListener('graphpage-failure', function (e) { window.__gp.push(e.detail); "
           "window.__gpmeta.push({ cancelable: e.cancelable, composed: e.composed, bubbles: e.bubbles, type: e.type, isTrusted: e.isTrusted }); });")
GV_PATH = "/graph/spine.json"


def gv(b, engine, spine_edit=None, index_edit=None, fix="graphview", width=390, height=844, wait_for="graph", cards_edit=None):
    """The graphview fixture (made-up text) served, a listener for the failure event registered BEFORE the page loads, the page open at `width`."""
    root = tempfile.mkdtemp(prefix="pg-gv-")
    assemble.assemble(root, engine, fix=fix, spine_edit=spine_edit, index_edit=index_edit, cards_edit=cards_edit)
    Handler.seen.clear()
    S = Served(root)
    pg = Pg(b, S.base + "graph/index.html", width, height, init=GV_INIT)
    if wait_for == "graph":
        pg.settled()
    return S, pg


def gv_clean():
    Handler.blocked.clear(); Handler.garbage.clear(); Handler.status.clear(); Handler.delay.clear()


def gv_spine_requests():
    return len([x for x in Handler.seen if x.split("?")[0] == GV_PATH])


def gv_state(pg):
    return pg.ev("""(() => { const q = (s) => document.querySelector(s);
      return { cards: q('#graph').hidden === false, spine: q('.graph-spine') ? q('.graph-spine').hidden === false : null, notice: q('#graph-notice').hidden === false,
        noticeText: q('#graph-notice').textContent, nodes: document.querySelectorAll('.graph-spine .ge-node').length, cardNodes: document.querySelectorAll('#graph .ge-node').length,
        pressed: [...document.querySelectorAll('button.view-btn')].map((x) => x.getAttribute('data-id') + ':' + x.getAttribute('aria-pressed')), events: window.__gp }; })()""")


def gv_press(pg, which):
    pg.page.click('button.view-btn[data-id="%s"]' % which)
    pg.page.wait_for_timeout(250)


def c_gv_live_silent(b, S0, engine):
    """GV1: on the live map (no view words) there is no switch, no Graph stage, no request for spine.json and not one event, through taps, a key, the About
    block and deep links."""
    root = tempfile.mkdtemp(prefix="pg-gv-live-")
    assemble.assemble(root, engine)
    Handler.seen.clear()
    S = Served(root)
    try:
        pg = Pg(b, S.base + "graph/index.html", 1024, 800, init=GV_INIT).settled()
        tap(pg, "goal-chain")
        wait_sheet(pg, True)
        pg.page.click("#graph-key")
        pg.page.click("#graph-about-open")
        at_hash(pg, "a1")
        pg.page.wait_for_timeout(400)
        st = gv_state(pg)
        assert st["spine"] is None and pg.ev("document.querySelectorAll('button.view-btn').length") == 0, st
        assert pg.ev("document.querySelectorAll('.view-switch').length") == 0
        assert st["events"] == [], st["events"]
        assert gv_spine_requests() == 0, Handler.seen
        pg.csp_clean(); pg.close()
    finally:
        S.stop()


def c_made_tap(b, S0, engine, w, h, mobile):
    """B2: a tap on a drawn box opens the same card; the parts button on a part with children opens its parts."""
    S = made_served(engine, MADE_ABOUT_BLOCK)
    try:
        pg = Pg(b, S.base + "graph/index.html", w, h, mobile=mobile).settled()
        tap(pg, "sk-part-2")
        made_expect(pg, "sk-part-2", "DIV", "Part sk-part-2", "Part")
        tap(pg, "sk-part")
        made_expect(pg, "sk-part", "DIV", "Part sk-part", "Part")
        assert pg.ev("document.querySelector('#graph-sheet-tools .sheet-tool').textContent") == "Open its parts"
        pg.page.click("#graph-sheet-tools .sheet-tool")
        wait_sheet(pg, False)
        pg.wait("document.querySelector('[data-node=\"sk-group-a\"]')")
        tap(pg, "sk-group-a")
        made_expect(pg, "sk-group-a", "DIV", "Group sk-group-a", "Group")
        pg.page.click("#graph-sheet-tools .sheet-tool")
        wait_sheet(pg, False)
        pg.wait("document.querySelector('[data-node=\"sk-file-1\"]')")
        tap(pg, "sk-file-1")
        made_expect(pg, "sk-file-1", "DIV", MADE_FILE1_PLAIN, "File", True, 1)
        made_healthy(pg)
        pg.close()
    finally:
        S.stop()


MADE_TRACE_JS = ("document.querySelectorAll('.card, .claim, .sheet-status, .note-label, .note-source, .note-body').length === 0 && "
                 "document.getElementById('graph-sheet-body').childNodes.length === 0 && document.getElementById('graph-sheet').hidden === true")


def c_made_close_reopen(b, S0, engine, w, h, mobile):
    """B3 (M3): closing a made card leaves no trace (no placeholder, nothing in #graph-cards or the sheet, the card is out of the page); a reopen shows
    the SAME card again (the same element, made once and kept), identical, twice over."""
    S = made_served(engine, MADE_ABOUT_BLOCK)
    try:
        pg = Pg(b, S.base + "graph/index.html", w, h, mobile=mobile).settled()
        cards = pg.ev("document.getElementById('graph-cards').outerHTML")
        assert pg.ev(MADE_TRACE_JS), "a clean start"
        at_hash(pg, "sk-file-1")
        pg.wait("document.querySelector('#graph-sheet-body .claim')", 6000)
        pg.ev("(() => { const c = document.getElementById('graph-sheet-body').firstElementChild; window.__c = c; window.__html = c.outerHTML; })()")
        assert pg.ev("window.__c.querySelectorAll('.note-body').length") == 1
        pg.page.click("#graph-sheet-close")
        wait_sheet(pg, False)
        assert pg.ev(MADE_TRACE_JS), "close leaves a trace"
        assert pg.ev("window.__c.parentNode === null && !window.__c.isConnected"), "the made card is out of the page"
        assert pg.ev("document.getElementById('graph-cards').outerHTML") == cards, "#graph-cards changed"
        assert pg.ev("window.__c.querySelectorAll('.sheet-status, .note-label, .note-source, .note-body').length") == 0, "what the sheet added went with it"
        for how in ("tap", "escape"):
            tap(pg, "sk-file-1")
            pg.wait("document.getElementById('graph-sheet-body').firstElementChild", 6000)
            assert pg.ev("document.getElementById('graph-sheet-body').firstElementChild === window.__c"), "a reopen made a new card"
            assert pg.ev("document.getElementById('graph-sheet-body').firstElementChild.outerHTML === window.__html"), "a reopen is not identical"
            assert pg.ev("document.getElementById('graph-sheet-body').childElementCount") == 1
            if how == "tap":
                pg.page.click("#graph-sheet-close")
            else:
                pg.page.keyboard.press("Escape")
            wait_sheet(pg, False)
            assert pg.ev(MADE_TRACE_JS), "close leaves a trace (" + how + ")"
            assert pg.ev("document.getElementById('graph-cards').outerHTML") == cards
        made_healthy(pg)
        pg.close()
    finally:
        S.stop()


def c_made_unknown(b, S0, engine, w, h, mobile):
    """B4: an id the data does not know is still link_refused and opens nothing; a card that was open stays open; a known id still opens made."""
    S = made_served(engine, MADE_ABOUT_BLOCK)
    try:
        pg = Pg(b, S.base + "graph/index.html", w, h, mobile=mobile).settled()
        refused = "That address does not name a step on this map."
        at_hash(pg, "no-such-step")
        pg.wait("!document.getElementById('graph-notice').hidden", 6000)
        assert pg.ev("document.getElementById('graph-notice').textContent") == refused
        assert pg.ev("document.getElementById('graph-sheet').hidden") and pg.ev(MADE_TRACE_JS)
        at_hash(pg, "Bad Id")
        pg.page.wait_for_timeout(300)
        assert pg.ev("document.getElementById('graph-sheet').hidden") and pg.ev("!document.getElementById('graph-notice').hidden")
        at_hash(pg, "sk-part-2")
        made_expect(pg, "sk-part-2", "DIV", "Part sk-part-2", "Part")
        assert pg.ev("document.getElementById('graph-notice').hidden"), "a card that opens hushes the notice"
        at_hash(pg, "sk-nope")
        pg.wait("!document.getElementById('graph-notice').hidden", 6000)
        assert pg.ev("document.getElementById('graph-notice').textContent") == refused
        made_expect(pg, "sk-part-2", "DIV", "Part sk-part-2", "Part")      # the open card stays open
        made_healthy(pg)
        pg.close()
    finally:
        S.stop()


MADE_LOOK_JS = """(() => { const b = document.getElementById('graph-sheet-body'), c = b.firstElementChild, cl = c.querySelector('.claim'), st = c.querySelector('.sheet-status'),
  nl = c.querySelector('.note-label'), ns = c.querySelector('.note-source'), nb = c.querySelector('.note-body'), B = b.getBoundingClientRect(), cs = getComputedStyle(cl);
  const at = (e) => { const r = e.getBoundingClientRect(); return [Math.round(r.left - B.left), Math.round(r.top - B.top), Math.round(r.width), Math.round(r.height)]; };
  const card = c.getBoundingClientRect();
  return { tag: c.tagName, id: c.getAttribute('id'), kids: [...c.children].map(e => e.tagName + '.' + e.className).filter(k => k !== 'P.note'),
    claimStyle: [cs.fontSize, cs.fontWeight, cs.lineHeight, cs.display, cs.color, cs.marginTop, cs.marginBottom], claimHTML: cl.innerHTML,
    claim: at(cl), status: [st.textContent, at(st)], label: [nl.textContent, at(nl)], source: [ns.textContent, at(ns)], noteBody: [nb.textContent, at(nb)],
    card: [Math.round(card.left - B.left), Math.round(card.width)] }; })()"""

MADE_MARKUP_FILE1 = ('<article class="card" id="sk-file-1"><h3 class="claim">Synthetic file one with a <code>code span</code> in it</h3>'
                     '<p class="note">Synthetic markup note.</p></article>\n')


def c_made_looks_like_markup(b, S0, engine, w, h, mobile):
    """B5: a made card's sheet looks the same as a markup card's for the same step: the .claim (its style and box), the status line directly under
    it, the note section in the same place. (The markup tree is a precondition: its card is the article with its id.)"""
    sig = {}
    for name, cards in (("made", MADE_ABOUT_BLOCK), ("markup", MADE_ABOUT_BLOCK + MADE_MARKUP_FILE1)):
        S = made_served(engine, cards)
        try:
            pg = Pg(b, S.base + "graph/index.html#sk-file-1", w, h, mobile=mobile).settled()
            made_wait_claim(pg, MADE_FILE1_PLAIN)
            pg.wait("document.querySelector('#graph-sheet-body .note-body')", 6000)
            sig[name] = pg.ev(MADE_LOOK_JS)
            made_healthy(pg)
            pg.close()
        finally:
            S.stop()
    assert (sig["markup"]["tag"], sig["markup"]["id"]) == ("ARTICLE", "sk-file-1"), ("the markup tree must show the markup's article", sig["markup"])
    assert (sig["made"]["tag"], sig["made"]["id"]) == ("DIV", None), sig["made"]
    for k in ("kids", "claimStyle", "claimHTML", "claim", "status", "label", "source", "noteBody", "card"):
        assert sig["made"][k] == sig["markup"][k], (k, sig["made"][k], sig["markup"][k])
    assert sig["made"]["kids"] == ["H3.claim", "P.sheet-status", "P.note-label", "P.note-source", "DIV.note-body"], sig["made"]["kids"]


def c_made_markup_wins(b, S0, engine, w, h, mobile):
    """B6 (M2): a page WITH an article for an id shows that article (as today: moved in, and home again byte for byte); the made card is for the ids it
    has none for, in the same page."""
    marked = '<article class="card" id="sk-part"><h3 class="claim">Synthetic marked claim</h3></article>\n'
    S = made_served(engine, MADE_ABOUT_BLOCK + marked)
    try:
        pg = Pg(b, S.base + "graph/index.html", w, h, mobile=mobile).settled()
        cards = pg.ev("document.getElementById('graph-cards').outerHTML")
        at_hash(pg, "sk-part")
        made_expect(pg, "sk-part", "ARTICLE", "Synthetic marked claim", "Part", markup_id="sk-part")
        assert pg.ev("document.getElementById('sk-part').parentElement === document.getElementById('graph-sheet-body')"), "the markup's article is moved in"
        pg.ev("window.__m = document.getElementById('sk-part')")
        pg.page.click("#graph-sheet-close")
        wait_sheet(pg, False)
        assert pg.ev("document.getElementById('graph-cards').outerHTML") == cards, "the markup is not back byte for byte"
        at_hash(pg, "sk-group-a")
        made_expect(pg, "sk-group-a", "DIV", "Group sk-group-a", "Group")
        pg.page.click("#graph-sheet-close")
        wait_sheet(pg, False)
        assert pg.ev("document.getElementById('graph-cards').outerHTML") == cards
        assert pg.ev("document.getElementById('graph-sheet-body').childNodes.length === 0 && document.getElementById('graph-sheet').hidden === true "
                     "&& document.querySelectorAll('.card').length === 1"), "a made card left a trace (the markup's one card is the only .card)"
        tap(pg, "sk-part")
        pg.wait("document.getElementById('graph-sheet-body').firstElementChild === window.__m", 6000)
        made_healthy(pg)
        pg.close()
    finally:
        S.stop()


def c_gv_switch_present(b, S0, engine):
    """GV2: with both view words the switch is two buttons in span.seg.view-switch inside nav.toolbar (data-id cards and graph, aria-pressed on Cards), the
    Graph stage exists hidden and empty, and spine.json has NOT been requested."""
    S, pg = gv(b, engine)
    try:
        assert pg.ev("[...document.querySelectorAll('nav.toolbar > span.seg.view-switch > button.view-btn')].map((x) => x.getAttribute('data-id') + ':' + x.textContent)") == ["cards:Cards", "graph:Graph"]
        st = gv_state(pg)
        assert st["pressed"] == ["cards:true", "graph:false"] and st["spine"] is False and st["nodes"] == 0 and st["cards"] is True, st
        assert gv_spine_requests() == 0
        pg.csp_clean(); pg.close()
    finally:
        S.stop(); gv_clean()


def c_gv_draw(b, S0, engine):
    """GV3 + GV4: pressing Graph reads spine.json ONCE and draws one box per node of the file (the count is the file's, not a literal) in the second stage; Cards is
    hidden, the notice hidden, the pressed button follows; pressing Graph again does nothing more; Cards returns and back is no new request. The links drawn are
    the ones in the reduction: the same page without the non-reduction link has the same number of link strokes, and a control that flags it in_reduction draws more."""
    counts = {}
    for name, edit in (("full", None), ("without", lambda s: s.__setitem__("links", [l for l in s["links"] if l["in_reduction"]])),
                       ("flagged", lambda s: [l.__setitem__("in_reduction", True) for l in s["links"]])):
        S, pg = gv(b, engine, spine_edit=edit)
        try:
            n = pg.ev("fetch('/graph/spine.json').then((r) => r.json()).then((j) => j.nodes.length)")
            Handler.seen.clear()
            gv_press(pg, "graph")
            pg.wait("document.querySelectorAll('.graph-spine .ge-node').length > 0", 6000)
            st = gv_state(pg)
            assert st["nodes"] == n == 4 and st["spine"] is True and st["cards"] is False and st["notice"] is False, st
            assert st["pressed"] == ["cards:false", "graph:true"] and st["events"] == [], st
            counts[name] = pg.ev("document.querySelectorAll('.graph-spine .ge-link').length")
            if name == "full":
                assert gv_spine_requests() == 1, Handler.seen
                gv_press(pg, "graph")
                assert gv_spine_requests() == 1 and gv_state(pg)["nodes"] == 4
                gv_press(pg, "cards")
                st = gv_state(pg)
                assert st["cards"] is True and st["spine"] is False and st["pressed"] == ["cards:true", "graph:false"], st
                gv_press(pg, "graph")
                assert gv_state(pg)["spine"] is True and gv_spine_requests() == 1, Handler.seen
            pg.csp_clean(); pg.close()
        finally:
            S.stop(); gv_clean()
    assert counts["full"] == counts["without"] and counts["flagged"] > counts["full"] and counts["full"] > 0, counts


def c_gv_faces_and_sheet(b, S0, engine):
    """GV5 + GV6: a box's face is the row's sentence alone, as text (hostile content stays text: no element from it); a tap opens the sheet with the names as code, the
    label, the sentence, the line 'Lives in: <the file's title>' and the button; the button switches to Cards and opens THAT file's sheet there."""
    hostile = "<img src=x onerror=alert(1)> and `<b>code</b>` text"

    def edit(s):
        s["nodes"][0]["content"] = hostile
        s["nodes"][0]["names"] = ["<i>x</i>", "Made.second"]
    S, pg = gv(b, engine, spine_edit=edit)
    try:
        gv_press(pg, "graph")
        pg.wait("document.querySelectorAll('.graph-spine .ge-node').length === 4", 6000)
        faces = pg.ev("[...document.querySelectorAll('.graph-spine .ge-node')].map((n) => n.getAttribute('data-node') + '|' + n.querySelector('.face-title').textContent)")
        assert faces[0] == "spine-made-a|" + hostile.replace("`", ""), faces[0]
        assert faces[1:] == ["spine-made-b|Made-up sentence of box b.", "spine-made-c|Made-up sentence of box c.", "spine-made-d|Made-up sentence of box d."], faces
        assert pg.ev("document.querySelectorAll('.graph-spine img, .graph-spine i, .graph-spine b').length") == 0
        assert pg.ev("document.querySelectorAll('.graph-spine .face-title code').length") == 1
        tap(pg, "spine-made-a")
        pg.wait("document.querySelector('#graph-sheet-body .spine-panel')", 6000)
        panel = pg.ev("""(() => { const p = document.querySelector('#graph-sheet-body .spine-panel');
          return { names: [...p.querySelectorAll('h2 code')].map((c) => c.textContent), label: p.querySelector('.spine-label').textContent,
                   content: p.querySelector('.spine-content').textContent, lives: p.querySelector('.spine-lives').textContent,
                   button: p.querySelector('button').textContent, file: p.querySelector('button').getAttribute('data-id'), img: p.querySelectorAll('img, b, i').length }; })()""")
        assert panel["names"] == ["<i>x</i>", "Made.second"] and panel["label"] == "In the repository's words", panel
        assert panel["content"] == hostile.replace("`", "") and panel["lives"] == "Lives in: File sk-file-1" and panel["button"] == "Show its file in Cards", panel
        assert panel["file"] == "sk-file-1" and panel["img"] == 0, panel
        pg.page.click("#graph-sheet-body .spine-show-file")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'sk-file-1'", 8000)
        st = gv_state(pg)
        assert st["cards"] is True and st["spine"] is False and st["pressed"] == ["cards:true", "graph:false"], st
        pg.csp_clean(); pg.close()
    finally:
        S.stop(); gv_clean()


def c_gv_key(b, S0, engine):
    """GV7: in the Graph view the Key says what a box is and prints the spine's own sentence (the key the spine's edge_basis names); in Cards it is the index's key as before."""
    S, pg = gv(b, engine)
    try:
        pg.page.click("#graph-key")
        wait_sheet(pg, True)
        cards_key = pg.ev("document.querySelector('#graph-sheet-body .key-content').textContent")
        assert "Each box is one of the main results" not in cards_key and "Made-up words of the fixture" not in cards_key
        pg.page.click("#graph-sheet-close")
        gv_press(pg, "graph")
        pg.wait("document.querySelectorAll('.graph-spine .ge-node').length === 4", 6000)
        pg.page.click("#graph-key")
        wait_sheet(pg, True)
        key = pg.ev("[...document.querySelectorAll('#graph-sheet-body .key-content > *')].map((e) => e.tagName + ':' + e.textContent)")
        assert key[0] == "P:Each box is one of the main results the repository names in its last step.", key
        assert key[-1] == "P:A line means the upper result rests on the lower one. Made-up words of the fixture.", key
        pg.csp_clean(); pg.close()
    finally:
        S.stop(); gv_clean()


def c_gv_refusals(b, S0, engine):
    """GV8 + GV9 + GV10: each way the spine can fail at the switch leaves Cards standing (its nodes drawn, shown), the Graph stage hidden and EMPTY, one page-constant
    notice, and ONE event {stage: graph, code} whose code is a member of the fixed set and nothing else (a hostile value in the refused file never reaches it);
    pressing Graph again after the cause is gone draws the view, hides the notice and fires {stage: graph, code: null} once."""
    CODES = ["fetch-failed", "not-json", "http-error", "bad-type", "missing-key", "extra-key", "bad-format", "bad-commit", "bad-edge-basis", "bad-spine-node", "bad-spine-link",
             "engine-refused", "graph-failed"]
    hostile = "<img src=x onerror=alert(1)> SECRET-DATA-VALUE"
    cases = [("a missing file", lambda s: Handler.blocked.add(GV_PATH), None, "http-error"),
             ("a failing server", lambda s: Handler.status.__setitem__(GV_PATH, 500), None, "http-error"),
             ("not JSON", lambda s: Handler.garbage.add(GV_PATH), None, "not-json"),
             ("a hostile edge_basis words", None, lambda sp: sp["edge_basis"].__setitem__("words", hostile), "bad-edge-basis"),
             ("a cycle in the reduction", None, lambda sp: sp["links"].append({"from": "spine-made-d", "in_reduction": True, "to": "spine-made-a"}), "bad-spine-link"),
             ("a wrong commit", None, lambda sp: sp.__setitem__("commit", "f" * 40), "bad-commit"),
             ("an unknown key", None, lambda sp: sp.__setitem__("extra", 1), "extra-key")]
    for name, serve, edit, code in cases:
        S, pg = gv(b, engine, spine_edit=edit)
        try:
            if serve:
                serve(S)
            gv_press(pg, "graph")
            pg.wait("document.getElementById('graph-notice').hidden === false", 6000)
            st = gv_state(pg)
            assert st["notice"] and st["noticeText"] == "The graph could not be opened; tap Graph to try again.", (name, st)
            assert st["nodes"] == 0 and st["spine"] is False and st["cards"] is True and st["cardNodes"] > 0, (name, st)
            assert st["pressed"] == ["cards:true", "graph:false"], (name, st)
            assert len(st["events"]) == 1 and sorted(st["events"][0]) == ["code", "stage"] and st["events"][0]["stage"] == "graph", (name, st["events"])
            assert st["events"][0]["code"] == code and st["events"][0]["code"] in CODES, (name, st["events"])
            assert "SECRET-DATA-VALUE" not in json.dumps(st["events"]), name
            assert all(isinstance(e["code"], str) and 0 < len(e["code"]) <= 32 for e in st["events"]), (name, st["events"])      # a string of the fixed set, bounded
            # Zephyr's conditions on the event itself: not cancelable, not composed, named for this page only
            assert pg.ev("window.__gpmeta") == [{"cancelable": False, "composed": False, "bubbles": False, "type": "graphpage-failure", "isTrusted": False}], name
            assert pg.ev("document.getElementById('graph-fallback').hidden") is True, name      # Cards still standing: no fallback of the whole page
            # the cause goes away: the next press draws the view, clears the notice and tells the clearing once
            gv_clean()
            if edit:
                open(os.path.join(S.srv.RequestHandlerClass.root, "graph", "spine.json"), "w").write(open(os.path.join(assemble.HERE, "fixtures", "graphview", "spine.json")).read())
            gv_press(pg, "graph")
            pg.wait("document.querySelectorAll('.graph-spine .ge-node').length === 4", 6000)
            st = gv_state(pg)
            assert st["notice"] is False and st["spine"] is True and st["cards"] is False, (name, st)
            assert len(st["events"]) == 2 and st["events"][1] == {"stage": "graph", "code": None}, (name, st["events"])
            pg.csp_clean(); pg.close()
        finally:
            S.stop(); gv_clean()


def c_gv_ticket(b, S0, engine):
    """GV11: a press of Graph whose spine is still loading, then a press of Cards: the late answer changes nothing (Cards stays, the stage stays hidden and empty,
    no notice, no event); the route's ticket was superseded."""
    S, pg = gv(b, engine)
    try:
        ev = threading.Event()
        Handler.delay[GV_PATH] = ev
        pg.page.click('button.view-btn[data-id="graph"]')
        pg.page.wait_for_timeout(200)
        pg.page.click('button.view-btn[data-id="cards"]')
        ev.set()
        pg.page.wait_for_timeout(600)
        st = gv_state(pg)
        assert st["cards"] is True and st["spine"] is False and st["nodes"] == 0 and st["notice"] is False and st["events"] == [], st
        assert st["pressed"] == ["cards:true", "graph:false"], st
        pg.csp_clean(); pg.close()
    finally:
        S.stop(); gv_clean()


def c_gv_one_view_word(b, S0, engine):
    """GV12: a map with only ONE of the two view words is refused at start (bad-view-words): the fallback shows and Cards' markup stays, as for any refused index."""
    for drop in ("view_cards", "view_graph"):
        S, pg = gv(b, engine, index_edit=lambda i, d=drop: i["strings"].pop(d), wait_for="load")
        try:
            pg.wait("document.getElementById('graph-fallback').hidden === false", 6000)
            assert pg.ev("document.querySelectorAll('button.view-btn').length") == 0 and pg.ev("document.getElementById('graph-cards').hidden") is False
            assert gv_spine_requests() == 0
            pg.csp_clean(); pg.close()
        finally:
            S.stop(); gv_clean()


def c_gv_engine_refused(b, S0, engine):
    """GV13: the engine itself refuses the spine's roots (more boxes than the map's max_children): this happens AFTER the stage was shown, so the page must put
    itself back: Cards shown and drawn, the Graph stage hidden and empty, the one notice, one event with the code engine-refused, the pressed button back on Cards."""
    S, pg = gv(b, engine, index_edit=lambda i: i.__setitem__("max_children", 3))
    try:
        gv_press(pg, "graph")
        pg.wait("document.getElementById('graph-notice').hidden === false", 6000)
        st = gv_state(pg)
        assert st["noticeText"] == "The graph could not be opened; tap Graph to try again." and st["cards"] is True and st["spine"] is False and st["nodes"] == 0 and st["cardNodes"] > 0, st
        assert st["events"] == [{"stage": "graph", "code": "engine-refused"}] and st["pressed"] == ["cards:true", "graph:false"], st
        pg.csp_clean(); pg.close()
    finally:
        S.stop(); gv_clean()


def c_gv_unknown_file(b, S0, engine):
    """GV14: a spine box whose file is no step the page can load: the tap shows the page's refused-link notice, opens no panel, and leaves the Graph view as it is."""
    S, pg = gv(b, engine, spine_edit=lambda sp: sp["nodes"][0].__setitem__("file", "no-such-step"))
    try:
        gv_press(pg, "graph")
        pg.wait("document.querySelectorAll('.graph-spine .ge-node').length === 4", 6000)
        tap(pg, "spine-made-a")
        pg.wait("document.getElementById('graph-notice').hidden === false", 6000)
        st = gv_state(pg)
        assert st["noticeText"] == "That address does not name a step on this map." and st["spine"] is True and st["cards"] is False and st["nodes"] == 4, st
        assert pg.ev("document.querySelectorAll('#graph-sheet-body .spine-panel').length") == 0 and not sheet_open(pg)
        assert st["events"] == [], st["events"]      # a bad box is not a failure of the view: no event
        pg.csp_clean(); pg.close()
    finally:
        S.stop(); gv_clean()


def c_gv_show_file_made_card(b, S0, engine):
    """GV18: on a tree whose card block is the assembler's (no articles, as on the real map), 'Show its file in Cards' switches to Cards and opens THAT file's sheet
    as a card the page MADE from the data (a div, no markup id): the Graph view is hidden, the claim is the file's title, the sheet is open and the page is healthy."""
    S, pg = gv(b, engine, cards_edit=lambda c: MADE_ABOUT_BLOCK)
    try:
        gv_press(pg, "graph")
        pg.wait("document.querySelectorAll('.graph-spine .ge-node').length === 4", 6000)
        assert pg.ev("document.querySelectorAll('#graph-about ~ article, article.card').length") == 0, "the tree has a markup card"
        tap(pg, "spine-made-a")
        pg.wait("document.querySelector('#graph-sheet-body .spine-panel')", 6000)
        pg.page.click("#graph-sheet-body .spine-show-file")
        made_expect(pg, "sk-file-1", "DIV", "File sk-file-1", "File")
        st = gv_state(pg)
        assert st["cards"] is True and st["spine"] is False and st["pressed"] == ["cards:true", "graph:false"] and st["notice"] is False, st
        assert st["events"] == [], st["events"]
        made_healthy(pg)
        pg.close()
    finally:
        S.stop(); gv_clean()


def c_gv_showall_and_address(b, S0, engine):
    """GV15: in the Graph view 'Show all' frames the spine (its boxes stay) and an address (#id) shows that card in CARDS: the view switches back first, the card's sheet opens."""
    S, pg = gv(b, engine)
    try:
        gv_press(pg, "graph")
        pg.wait("document.querySelectorAll('.graph-spine .ge-node').length === 4", 6000)
        pg.page.click("#graph-show-all")
        pg.page.wait_for_timeout(300)
        st = gv_state(pg)
        assert st["nodes"] == 4 and st["spine"] is True and st["cards"] is False and not sheet_open(pg), st
        pg.ev("location.hash = '#sk-file-1'")
        pg.wait("document.querySelector('#graph-sheet-body article')?.id === 'sk-file-1'", 8000)
        st = gv_state(pg)
        assert st["cards"] is True and st["spine"] is False and st["pressed"] == ["cards:true", "graph:false"], st
        pg.csp_clean(); pg.close()
    finally:
        S.stop(); gv_clean()


def c_gv_view_routes_close(b, S0, engine):
    """GV16: the Graph view's routes begin with the sheet's one close function: with a listener that cancels `sheetclose` on the shown panel, pressing Cards, tapping another
    box, pressing 'Show its file' and pressing Graph each leave the panel and the view exactly as they were. The route names are the module's own VIEW_ROUTES."""
    S, pg = gv(b, engine)
    try:
        assert sorted(pg.ev("import('./page/app.js').then(m => [...m.VIEW_ROUTES])")) == ["spine-open", "spine-show-file", "view-cards", "view-graph"]
        gv_press(pg, "graph")
        pg.wait("document.querySelectorAll('.graph-spine .ge-node').length === 4", 6000)
        tap(pg, "spine-made-a")
        pg.wait("document.querySelector('#graph-sheet-body .spine-panel')", 6000)
        pg.ev("document.querySelector('#graph-sheet-body .spine-panel').addEventListener('sheetclose', (e) => e.preventDefault())")
        names = lambda: pg.ev("[...document.querySelectorAll('#graph-sheet-body .spine-panel h2 code')].map((c) => c.textContent)")
        for what, act in (("Cards", lambda: pg.page.click('button.view-btn[data-id="cards"]')), ("another box", lambda: tap(pg, "spine-made-b")),
                          ("Show its file", lambda: pg.page.click("#graph-sheet-body .spine-show-file")), ("Graph", lambda: pg.page.click('button.view-btn[data-id="graph"]'))):
            act()
            pg.page.wait_for_timeout(300)
            st = gv_state(pg)
            assert names() == ["Made.a"] and st["spine"] is True and st["cards"] is False and st["pressed"] == ["cards:false", "graph:true"], (what, names(), st)
        pg.csp_clean(); pg.close()
    finally:
        S.stop(); gv_clean()


def c_gv_stale_spine_open(b, S0, engine):
    """GV17: a tap on a box whose file is still loading, then a tap on another box: the second box's panel is shown, and the first one's late answer changes nothing."""
    S, pg = gv(b, engine)
    try:
        gv_press(pg, "graph")
        pg.wait("document.querySelectorAll('.graph-spine .ge-node').length === 4", 6000)
        ev = threading.Event()
        Handler.delay["/graph/step/sk-file-2.json"] = ev
        tap(pg, "spine-made-b")
        pg.page.wait_for_timeout(200)
        tap(pg, "spine-made-c")
        pg.wait("document.querySelector('#graph-sheet-body .spine-panel h2 code')?.textContent === 'Made.c'", 6000)
        ev.set()
        pg.page.wait_for_timeout(500)
        assert pg.ev("[...document.querySelectorAll('#graph-sheet-body .spine-panel h2 code')].map((c) => c.textContent)") == ["Made.c"]
        assert gv_state(pg)["notice"] is False
        pg.csp_clean(); pg.close()
    finally:
        S.stop(); gv_clean()


GV_CASES = [
    ("GV1: the live map has no switch, no Graph stage, no spine request and no event", c_gv_live_silent),
    ("GV2: with both view words the switch is two buttons (Cards pressed), the stage hidden and empty, spine.json not requested", c_gv_switch_present),
    ("GV3/GV4: Graph reads spine.json once, draws one box per node, only the reduction's links, and switches back and forth without a new request", c_gv_draw),
    ("GV5/GV6: a box's face is its sentence as text, its sheet holds names, label, sentence, 'Lives in' and the button, which opens the file's sheet in Cards", c_gv_faces_and_sheet),
    ("GV7: the Graph view's key says what a box is and prints the spine's own sentence; Cards' key is unchanged", c_gv_key),
    ("GV8/GV9/GV10: seven ways the spine fails each leave Cards standing, one notice, one event with a fixed-set code only, and a retry draws it and tells the clearing once", c_gv_refusals),
    ("GV11: a press of Graph superseded by a press of Cards changes nothing when the spine arrives late", c_gv_ticket),
    ("GV12: one view word without the other is refused at start", c_gv_one_view_word),
    ("GV14: a box whose file is no loadable step shows the refused-link notice and no panel, and leaves the Graph view as it is", c_gv_unknown_file),
    ("GV15: in the Graph view 'Show all' frames the spine and an address shows its card in Cards", c_gv_showall_and_address),
    ("GV16: the Graph view's routes honour a cancelled sheetclose: Cards, another box, 'Show its file' and Graph change nothing", c_gv_view_routes_close),
    ("GV17: a box tapped while its file loads, then another box: the first one's late answer changes nothing", c_gv_stale_spine_open),
    ("GV18: on a tree with an empty card block, 'Show its file in Cards' opens the file's made card in Cards", c_gv_show_file_made_card),
    ("GV13: the engine refusing the spine's roots after the stage was shown puts the page back and tells engine-refused", c_gv_engine_refused),
]


def main():
    only = None
    engines = ["double", "real"]
    argv = sys.argv[1:]
    if "--only" in argv:
        only = argv[argv.index("--only") + 1]
    if "--engine" in argv:
        e = argv[argv.index("--engine") + 1]
        engines = ["double", "real"] if e == "both" else [e]
    if "--check-browser-choice" in argv:
        return check_browser_choice()
    launch = browser_launch(os.environ, SHELL)
    if launch is None:
        print("no headless shell under ~/.cache/ms-playwright")
        return 2
    with sync_playwright() as p:
        br = p.chromium.launch(**launch)
        for eng in engines:
            root = tempfile.mkdtemp(prefix="pg-" + eng + "-")
            assemble.assemble(root, eng)
            S = Served(root)
            # The navigation-ticket cases hold a card's STEP FETCH, so they need a map whose open waits for one: a map that carries notes. The live
            # fixture with the two note words added is that map (no step carries a note; the live map itself opens at once, round 6).
            rootn = tempfile.mkdtemp(prefix="pg-nav-" + eng + "-")
            assemble.assemble(rootn, eng, index_edit=carry_notes)
            SN = Served(rootn)
            try:
                def run(name, fn, *a):
                    if only is None or only in name:
                        case(eng + ": " + name, fn, br, SN if name.startswith("nav ") else S, *a)
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
                run("98: the key's first child is the scope paragraph and its last section is the edge basis's line paragraph (text nodes; the page prints strings[words])", c_key_edge_basis, eng)
                run("98: with a states section too, the line section comes after it (P, H2, UL, P, H2, UL, H2, P)", c_key_edge_basis_after_states, eng)
                run("98: without edge_basis and key_scope_text nothing is drawn for them", c_key_absent_keys, eng)
                run("98: the live map's key DOM is byte-identical to the base head's", c_key_live_unchanged, eng)
                run("98: hostile key_scope_text and words value are text in the key", c_key_hostile, eng)
                run("v3: the live map passes createGraph no layout and no frameMin (zoom is {fitMin: 1}); main's options", c_v3_options_live, eng)
                run("v3: the skeleton passes layout column and zoom {fitMin: 1, frameMin: 1}; the engine gets the reduction's links only", c_v3_options_skeleton, eng)
                run("v3: a bad sibling_layout or open_scale_floor is the fallback; a floor above the engine's cap throws a TypeError at start and is the fallback too", c_v3_refusals, eng)
                run("98 r4: a floor below zoom.min or above the open cap is the fallback with bad-scale-floor recorded (the engine's rule, named); a floor of 1 boots", c_v3_floor_named, eng)
                run("98 r4: a valid floor beside another bad option is the engine's plain start failure, not bad-scale-floor", c_v3_floor_valid_other_bad, eng)
                run("module: A6 a backtick span in a title is a code element on the face (inside the clamp) and in the breadcrumb, no backtick shown", c_backtick_title, eng)
                run("module: P7 the sheet builds .sheet-status only for a non-empty status", c_sheet_status_level, eng)
                run("module: P6/F1 part, group and file told by bar position over s-none and s-census; swatches match; the selection ring gap is 3 px", c_look_override, eng)
                run("note: N12/N14/N2 the sheet shows the label, the source line and the rendered note in order; the first heading is kept; a card without a note shows none", c_note_sheet, eng)
                run("note: N9 a tap loads the step file and shows its note; the hostile note is visible text and only allowed elements", c_note_tap_and_hostile, eng)
                run("note: N13 a map lacking a note key is the page's failure when a note step opens; a template with markup is text", c_note_strings, eng)
                run("note: a failed step load on a tap leaves the open card untouched", c_note_load_failure, eng)
                run("note: N11 the live map's sheet carries no note", c_note_live_unchanged, eng)
                run("note: a sheet that throws after the step loaded is the fallback, with no unhandled rejection", c_note_open_throws, eng)
                run("note: L1/T4/T6 with the four maths-face strings: label, source, line, button, note in order; formulas in the maths face; the button toggles to the exact text and back; Escape closes", c_typeset_sheet, eng)
                run("note: T4 formula spans that would be markup are span.m text, no element comes of them", c_typeset_hostile, eng)
                run("note: the maths face sets scripts (sup, sub; no ^ or _ in a .m span; a refused span is code as typed; the exact view is byte-equal)", c_typeset_scripts, eng)
                run("note: T5 a map lacking any one of the four maths-face strings renders the note exactly as round 1", c_typeset_gate, eng)
                run("note: L2 a review {state: converter} changes nothing drawn", c_typeset_review, eng)
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
                run("nav R1: tap A (slow, then 500) then tap B (fast): B's sheet is open, no notice, no fallback", c_nav_r1, eng)
                run("nav R2: tap A (slow) then Escape: when A resolves the sheet stays closed", c_nav_r2, eng, "escape")
                run("nav R2: tap A (slow) then the close button: when A resolves the sheet stays closed", c_nav_r2, eng, "button")
                run("nav R3: tap A (slow) then the toolbar key: the key panel is still the one shown", c_nav_r3, eng)
                run("nav R4: deep link #A (slow) then #B (fast): the page ends on B", c_nav_r4, eng)
                run("nav R5: card C open, tap A (slow), an in-sheet close request: the sheet stays closed", c_nav_r5, eng)
                run("nav R6 control: a single slow tap opens; a single 500 is the parts notice; a 4xx the refused-link notice", c_nav_r6, eng)
                run("nav B1: tap A (slow) then a tap on blank map: when A resolves no sheet opens", c_nav_b1_b3, eng, "tap-outside")
                run("nav B2: tap A (slow) then toolbar About: when A resolves About is still the one shown", c_nav_b1_b3, eng, "toolbar-about")
                run("nav B3: tap A (slow) then toolbar Show all: when A resolves no sheet opens", c_nav_b1_b3, eng, "toolbar-show-all")
                run("nav B4: open-parts on C (its children's load slow) then tap D: when C's load resolves D's sheet is untouched and the camera is not moved to C", c_nav_b4, eng)
                run("nav B4b: tap A (slow) then open-parts on the shown card: when A resolves the sheet stays closed", c_nav_b4b, eng)
                for mode in ("500", "garbage"):
                    run("nav B5: deep link whose reveal fails (%s, slow), the reader taps another card first: that card's sheet is open and no notice, no fallback when the failure arrives" % mode, c_nav_b5_b6, eng, mode, True)
                    run("nav B6 control: the same failing deep link with nothing after it (%s): the notice or the fallback, exactly as before" % mode, c_nav_b5_b6, eng, mode, False)
                run("nav B5b: open-parts whose load fails (slow), the reader taps another card first: that card's sheet is open and no notice when the failure arrives", c_nav_b5b_b6b, eng, True)
                run("nav B6b control: the same failing open-parts with nothing after it: the parts notice appears, as before", c_nav_b5b_b6b, eng, False)
                run("nav B7 control: the reader's own open of a node's parts that fails to load (slow, 500) is still the parts notice", c_nav_b7, eng)
                run("nav C1: a superseded open-parts is pending on one node, the reader's own open of an unrelated node fails to load: its parts notice appears; the superseded load's failure later says nothing", c_nav_c1, eng)
                run("round 6 C1: on the live map a tap whose step fetch FAILS (500) opens the sheet, no notice", c_live_open_fetch_fails, eng)
                run("round 6 C2: on the live map a tap whose step fetch never settles (held) has the sheet open before it settles", c_live_open_fetch_held, eng)
                run("round 6 C3: the 26 live sheet snapshots (23 by address, 3 by tap) equal what main's page drew", c_live_sheets_match_main, eng)
                run("round 7: a map with only ONE of note_label and note_source is refused at start: the fallback, bad-note-strings recorded, no card opens", c_note_one_key_refused, eng)
                for mw, mh, mm in MADE_VIEWS:
                    vw = " @%dx%d" % (mw, mh)
                    run("made B1: an empty card block: a deep link to a part, a group and a file opens the sheet, the title is the .claim, the note section shows for a file with a note" + vw, c_made_deep_link, eng, mw, mh, mm)
                    run("made B2: an empty card block: a tap on a drawn box opens the same card; the parts button on a part with children works" + vw, c_made_tap, eng, mw, mh, mm)
                    run("made B3: a made card's close leaves no trace; a reopen shows the same card, identical" + vw, c_made_close_reopen, eng, mw, mh, mm)
                    run("made B4: an unknown id is still link_refused and opens nothing" + vw, c_made_unknown, eng, mw, mh, mm)
                    run("made B5: a made card's sheet looks the same as a markup card's (claim, status and note placement)" + vw, c_made_looks_like_markup, eng, mw, mh, mm)
                    run("made B6: a page with an article shows it, byte for byte as today; a made card only for an id it has none for" + vw, c_made_markup_wins, eng, mw, mh, mm)
                run(GV_CASES[0][0], GV_CASES[0][1], eng)
                if eng == "real":
                    for gname, gfn in GV_CASES[1:]:
                        run(gname, gfn, eng)
                    run("REAL: a drag opens no sheet, a short click does", c_real_drag)
                    run("REAL: first frame at 390: the top steps only, inside the stage, text >= 15 px", c_real_first_frame_390)
                    run("REAL: pinch semantic-opens a step and loads its step file; no sheet", c_real_pinch)
            finally:
                S.stop()
                SN.stop()
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
