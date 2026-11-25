#!/usr/bin/env python3
"""Browser cases of the graph engine: real Chromium (the bundled headless shell), the files served locally with a
Content-Security-Policy header of  default-src 'none'; script-src 'self'; style-src 'self'.

Run with Playwright's Python:   ~/.engram/venv/bin/python3 viewer/graph/engine/test/browser/test_engine_browser.py
Cases: two engines on one page driven independently; destroy() leaves zero listeners and zero nodes; pinch by
CDP touch events zooms and semantic-opens; a drag emits no tap; a tap emits one; the handle's methods equal
INTERFACE.md's list; an invalid id leaves nothing in the DOM; no CSP violation, no console error.
Exit 0 only if every case passes. Nothing is written outside a temporary directory.
"""
import glob, http.server, json, os, re, sys, threading, time
from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
ENGINE = os.path.abspath(os.path.join(HERE, "..", ".."))
CSP = "default-src 'none'; script-src 'self'; style-src 'self'"
SHELL = glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"))


class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=ENGINE, **k)

    def end_headers(self):
        self.send_header("Content-Security-Policy", CSP)
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *a):
        pass


RESULTS = []


def case(name, fn):
    try:
        fn()
        RESULTS.append((name, True, ""))
        print("PASS " + name)
    except Exception as e:  # noqa: BLE001  (a failed assertion is the point)
        RESULTS.append((name, False, repr(e)))
        print("FAIL " + name + ": " + repr(e))


def interface_list(heading):
    md = open(os.path.join(ENGINE, "INTERFACE.md"), encoding="utf8").read()
    m = re.search(r"^## " + heading + r"\s*$(.*?)(?=^## |\Z)", md, re.S | re.M)
    assert m, "INTERFACE.md has no section " + heading
    return re.findall(r"^- `([A-Za-z0-9_]+)`", m.group(1), re.M)


def main():
    if not SHELL:
        print("no headless shell under ~/.cache/ms-playwright")
        return 2
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d/test/browser/page.html" % srv.server_address[1]
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=SHELL[0], args=["--no-sandbox"])
        ctx = br.new_context(viewport={"width": 800, "height": 600}, has_touch=True)
        page = ctx.new_page()
        console = []
        page.on("console", lambda m: console.append((m.type, m.text)))
        page.on("pageerror", lambda e: console.append(("pageerror", str(e))))
        cdp = ctx.new_cdp_session(page)

        def ev(expr, arg=None):
            """Evaluate through the DevTools protocol: Playwright's own evaluate compiles strings with eval, which
            the page's Content-Security-Policy (no unsafe-eval) rightly blocks; the protocol is not subject to it."""
            if arg is not None:
                expr = "(" + expr + ")(" + json.dumps(arg) + ")"
            r = cdp.send("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
            if "exceptionDetails" in r:
                raise AssertionError("page threw: " + json.dumps(r["exceptionDetails"])[:300])
            return r["result"].get("value")

        page.goto(url)
        for _ in range(100):
            if ev("window.__booted === true"):
                break
            time.sleep(0.05)
        else:
            raise AssertionError("the test page did not boot: " + repr(console))

        def settle(ms=60):
            time.sleep(ms / 1000)

        def center(sel):
            r = ev("(s) => { const e = document.querySelector(s); const r = e.getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2, r.width, r.height]; }", sel)
            return r

        base_listeners = ev("window.__ls.live()")
        ev("T.create('a')")
        methods_a = ev("T.create('b')")
        assert ev("T.ready('a')") is True and ev("T.ready('b')") is True
        settle()

        def c_handle():
            assert sorted(methods_a) == sorted(interface_list("Handle")), (sorted(methods_a), interface_list("Handle"))
        case("handle methods equal INTERFACE.md", c_handle)

        def c_booted():
            assert ev("T.nodes('a')") == 1 and ev("T.nodes('b')") == 1
            ca, cb = ev("T.cam('a')"), ev("T.cam('b')")
            assert ca and cb and abs(ca["k"] - 1.1) < 1e-9, (ca, cb)   # first fit: one card, fitMax 1.1
            assert ev("window.__ls.live()") > base_listeners
            st = ev("(() => { const s = document.querySelector('#a .ge-stage'); return [s.style.touchAction, s.getAttribute('tabindex')]; })()")
            assert st[0] == "none", st    # touch-action: none on the stage
        case("two engines start independently, fit, touch-action none on the stage", c_booted)

        def c_independent():
            b0, a0 = ev("T.cam('b')"), ev("T.cam('a')")
            x, y = 190, 250
            page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x + 20, y + 15, steps=4); page.mouse.move(x + 60, y + 40, steps=4); page.mouse.up()
            a1, b1 = ev("T.cam('a')"), ev("T.cam('b')")
            assert abs(a1["tx"] - a0["tx"] - 60) < 1.5 and abs(a1["ty"] - a0["ty"] - 40) < 1.5, (a0, a1)
            assert b1 == b0, ("B moved when A was dragged", b0, b1)
            page.mouse.move(590, 250); page.mouse.wheel(0, -100); settle()
            a2, b2 = ev("T.cam('a')"), ev("T.cam('b')")
            assert b2["k"] > b1["k"] and a2 == a1, (a1, a2, b1, b2)
            # the world point under the cursor stayed put: B's zoom started from B's own camera, not from A's
            left = ev("document.querySelector('#b .ge-stage').getBoundingClientRect().left")
            sx = 590 - left
            assert abs((sx - b1["tx"]) / b1["k"] - (sx - b2["tx"]) / b2["k"]) < 0.3, ("B's wheel zoom did not start from B's camera", b1, b2)
            # an open on one engine adds nodes only there
            before_b = ev("T.nodes('b')")
            assert ev("T.open('a', 'n0')") is True
            assert ev("T.nodes('a')") == 5 and ev("T.nodes('b')") == before_b
            assert ev("document.querySelectorAll('#a svg, #a canvas').length") == 0, "the engine draws no vector graphics"
            assert ev("document.querySelectorAll('#a .ge-link').length") > 0 and ev("document.querySelectorAll('#a .ge-link:not(div)').length") == 0, "links are div strokes"
            assert ev("T.reveal('a', ['n0', 'n1'])") is True      # frame n1 so the next cases can press it
        case("two engines on one page: drag, wheel and open on one leave the other untouched", c_independent)

        def c_drag_no_tap():
            ev("T.log.length = 0")
            r = center("#a [data-node='n1']")
            page.mouse.move(r[0], r[1]); page.mouse.down(); page.mouse.move(r[0] + 40, r[1] + 30, steps=5); page.mouse.up(); settle()
            assert ev("T.taps()") == [], ev("T.taps()")
            page.mouse.move(r[0] + 40, r[1] + 30)
            # then a plain click on the node (same spot, no movement, short) is one tap
            r = center("#a [data-node='n1']")
            page.mouse.move(r[0], r[1]); page.mouse.down(); page.mouse.up(); settle()
            assert ev("T.taps()") == ["a:n1"], ev("T.taps()")
            # a press held longer than 300 ms is not a tap
            ev("T.log.length = 0")
            page.mouse.move(r[0], r[1]); page.mouse.down(); time.sleep(0.45); page.mouse.up(); settle()
            assert ev("T.taps()") == [], ev("T.taps()")
            # a tap on the empty stage is tap(null)
            page.mouse.move(30, 480); page.mouse.down(); page.mouse.up(); settle()
            assert ev("T.taps()") == ["a:None"] or ev("T.taps()") == ["a:null"] or ev("T.log.filter(e => e[1] === 'tap' && e[2] === null).length") == 1, ev("T.log")
        case("a drag emits no tap; a short press is one tap; a long press is none; empty stage taps null", c_drag_no_tap)

        def touch(kind, pts):
            cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [{"x": x, "y": y, "id": i} for i, (x, y) in enumerate(pts)]})

        def c_touch_tap():
            ev("T.log.length = 0")
            r = center("#a [data-node='n1']")
            touch("touchStart", [(r[0], r[1])]); touch("touchEnd", []); settle(120)
            assert ev("T.taps()") == ["a:n1"], ev("T.log")
            touch("touchStart", [(r[0], r[1])]); touch("touchMove", [(r[0] + 30, r[1] + 5)]); touch("touchEnd", []); settle(120)
            assert ev("T.taps()") == ["a:n1"], ("a touch drag must not tap", ev("T.log"))
        case("touch: a quick touch is a tap, a touch drag is not", c_touch_tap)

        def c_pinch():
            ev("T.log.length = 0"); ev("T.fit('b')")
            k0 = ev("T.cam('b')")["k"]
            r = center("#b [data-node='n0']")
            cx, cy = r[0], r[1]
            d = 40
            touch("touchStart", [(cx - d / 2, cy), (cx + d / 2, cy)])
            kmax, opened = k0, False
            for step in range(1, 60):
                d = 40 + step * 4
                touch("touchMove", [(cx - d / 2, cy), (cx + d / 2, cy)]); settle(15)
                kmax = max(kmax, ev("T.cam('b')")["k"])
                if ev("T.log.some(e => e[1] === 'open')"):
                    opened = True; break
            touch("touchEnd", []); settle(120)
            assert kmax > k0 * 1.05, ("the pinch did not zoom", k0, kmax)
            assert opened, ("the pinch did not semantic-open", ev("T.log"))
            log = ev("T.log")
            assert ["b", "load", "n0"] in log and ["b", "open", "n0", None] in log, log
            assert ev("T.nodes('b')") == 5, ev("T.nodes('b')")
            assert ev("T.taps()") == [], "a pinch emits no tap"
        case("pinch by CDP touch events zooms and semantic-opens, loading the node's children", c_pinch)

        def c_invalid():
            ev("T.create('c', { roots: [{ id: 'Bad Id', childCount: 0, links: [], parentLinksTo: false, path: ['x'], data: null }] })")
            assert ev("T.ready('c')") is False
            assert ev("T.nodes('c')") == 0
            assert ev("T.log.filter(e => e[0] === 'c' && e[1] === 'refused').map(e => e[3])") == ["invalid-id"]
            assert ev("document.getElementById('c').querySelectorAll('[data-node]').length") == 0
            ev("T.destroy('c')")
        case("an invalid id leaves nothing in the DOM and emits refused", c_invalid)

        def c_fitmin():
            # host #c is a 70px strip: the natural fit of the one card is far below 1
            try:
                ev("T.create('c', { zoom: { fitMin: 1 } })")
                assert ev("T.ready('c')") is True
                settle()
                cam = ev("T.cam('c')")
                assert cam and abs(cam["k"] - 1) < 1e-9 and abs(cam["ty"] - 20) < 1e-6, cam   # start scale 1, top at fitPad
                host_top = ev("document.getElementById('c').getBoundingClientRect().top")
                node_top = ev("document.querySelector('#c [data-node]').getBoundingClientRect().top")
                assert 0 <= node_top - host_top <= 30, (host_top, node_top)    # the top node is in view at the top
                ev("T.fit('c')")
                assert ev("T.cam('c')")["k"] < 1, ev("T.cam('c')")
            finally:
                ev("T.destroy('c')")
        case("zoom.fitMin 1: the start camera is scale 1 with the top node in view; fit() then goes below 1", c_fitmin)

        def c_foreign_attr():
            assert ev("T.foreign('c')") is True
            settle(120)
            r = center("#c .t-inner")
            assert r[2] > 0 and r[3] > 0, ("the inner button has no size", r)
            ev("T.taps2.length = 0")
            page.mouse.move(r[0], r[1]); page.mouse.down(); page.mouse.up(); settle()
            taps = ev("T.taps2")
            assert taps == [{"id": "n0", "target": "t-inner", "key": None}], ("a tap on a face's own data-node element taps the OWNING node", taps)
            ev("T.taps2.length = 0")
            ev("document.querySelector('#c .t-inner').focus()")
            page.keyboard.press("Enter"); page.keyboard.press("Space"); settle()
            assert ev("T.taps2") == [], ("a key press on the face's own button is not node navigation", ev("T.taps2"))
            # the engine's own node element still takes Enter: key handling acts on what the engine made
            ev("document.querySelector('#c [data-node=n0]').focus()")
            page.keyboard.press("Enter"); settle()
            keyed = ev("T.taps2")
            assert len(keyed) == 1 and keyed[0]["id"] == "n0" and keyed[0]["key"] == "Enter", keyed
            # G2: pan/zoom keys pressed on a control inside the face are the face's own: the camera does not move, no tap
            for sel in ("#c .t-inner", "#c .t-plain"):
                ev("T.taps2.length = 0")
                ev("document.querySelector('" + sel + "').focus()")
                cam0 = ev("T.cam('c')")
                for key in ("ArrowLeft", "ArrowUp", "+", "-", "0"):
                    page.keyboard.press(key); settle(30)
                    assert ev("T.cam('c')") == cam0, ("a key on the face's own control moved the camera", sel, key, cam0, ev("T.cam('c')"))
                assert ev("T.taps2") == [], ("no tap from keys on the face's own control", sel, ev("T.taps2"))
            # and the same keys on the engine's own focused stage DO pan and zoom
            ev("document.querySelector('#c .ge-stage').focus()")
            before = ev("T.cam('c')")
            page.keyboard.press("ArrowLeft"); settle(30)
            after = ev("T.cam('c')")
            assert after["tx"] != before["tx"] and after["k"] == before["k"], ("ArrowLeft on the stage pans", before, after)
            page.keyboard.press("ArrowUp"); settle(30)
            assert ev("T.cam('c')")["ty"] != after["ty"], "ArrowUp on the stage pans"
            before = ev("T.cam('c')")
            page.keyboard.press("+"); settle(30)
            plus = ev("T.cam('c')")
            assert plus["k"] > before["k"], ("+ on the stage zooms in", before, plus)
            page.keyboard.press("-"); settle(30)
            minus = ev("T.cam('c')")
            assert minus["k"] < plus["k"], ("- on the stage zooms out", plus, minus)
            page.keyboard.press("ArrowRight"); page.keyboard.press("ArrowRight"); settle(30)
            moved = ev("T.cam('c')")
            page.keyboard.press("0"); settle(30)
            assert ev("T.cam('c')") != moved, ("0 on the stage fits", moved, ev("T.cam('c')"))
            ev("T.destroy('c')")
        case("a face's own data-node attribute never names a node: a tap taps the owner, a key press on its button is not navigation", c_foreign_attr)

        def c_destroy():
            ev("T.create('c')")
            n_live = ev("window.__ls.live()")
            ev("T.destroy('a')")
            assert ev("T.under('a')") == 0, "nodes left under the container of a"
            assert ev("window.__ls.live()") < n_live
            # B still works after A is gone
            tb = ev("T.cam('b')")
            page.mouse.move(590, 250); page.mouse.wheel(0, 120); settle()
            assert ev("T.cam('b')") != tb, "B did not respond after A was destroyed"
            ev("T.destroy('b')"); ev("T.destroy('c')")
            assert ev("T.under('b')") == 0 and ev("T.under('c')") == 0
            live = ev("window.__ls.live()")
            assert live == base_listeners, ("listeners left", live, base_listeners, ev("window.__ls.types()"))
            ev("T.destroy('a')")   # a second destroy is a no-op
            # after destroy the handle does not throw and does nothing
            assert ev("T.open('a', 'n0')") is False
            assert ev("T.under('a')") == 0
        case("destroy() leaves zero listeners and zero nodes under the container (and is safe twice)", c_destroy)

        def c_clean():
            assert ev("window.__csp") == [], ev("window.__csp")
            bad = [c for c in console if c[0] in ("error", "pageerror", "warning")]
            assert bad == [], bad
        case("no CSP violation and no console error or warning", c_clean)
        br.close()
    srv.shutdown()
    failed = [r for r in RESULTS if not r[1]]
    print("BROWSER CASES: %d passed, %d failed" % (len(RESULTS) - len(failed), len(failed)))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
