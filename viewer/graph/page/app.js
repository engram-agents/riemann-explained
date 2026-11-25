/* The page layer's entry. It creates the engine on the stage, wires the engine's events to the sheet and the toolbar,
   builds the key from the contract's closed lists, handles deep links and the fallback. One-way: this page imports the
   engine; the engine imports nothing of the page.

   THE SEAM: start(doc, {createGraph, fetch}) takes the engine's createGraph and a fetch-like as arguments. The last
   lines of this module call it with the real ones; a test calls it with a stand-in engine. Nothing else is injected. */
import { createGraph } from "../engine/index.js";
import { el, isId } from "./dom.js";
import { createData, DataError, KIND_CLASS, STATE_CLASS } from "./data.js";
import { makeRenderFace } from "./face.js";
import { createSheet } from "./sheet.js";

/* Every way the sheet can close. Each one is a function in `routes` below that begins with the sheet's one close
   function; a case drives each of these with a cancelling listener installed. */
export const CLOSE_ROUTES = Object.freeze([
  "close-button", "tap-outside", "escape", "open-card", "deep-link", "toolbar-show-all", "toolbar-key", "toolbar-about", "open-parts",
]);

/* ONE fixed closed size, chosen by measuring in the browser (the browser case "one fixed closed size"): a 50-character title of
   the widest glyphs takes three lines at 15 px in the engine's default 300 px width, and with the role word and the foot at
   14 px the face needs 138 px for every kind and state frame (measured on both engines; 136 clips the title in the thicker
   census frame). 140 leaves 2 px. Taller faces lower the first fit's scale (text 14.67 px at 140). The engine's other sizes
   stay at its defaults. */
const CARD_SIZES = Object.freeze({ nodeH: 140 });

const SHELL = ["graph-layer", "graph", "graph-sheet", "graph-crumbs", "graph-sheet-tools", "graph-sheet-body", "graph-sheet-close",
  "graph-show-all", "graph-key", "graph-about-open", "graph-fallback", "graph-cards", "graph-notice", "graph-about"];

function hashId(doc) {
  const h = doc.defaultView.location.hash;
  if (!h || h === "#") return null;
  try { return decodeURIComponent(h.slice(1)); } catch (e) { return ""; }
}

/* The key: one row per kind and per state in the contract's closed lists, each with its words from index.json strings. */
function buildKey(index) {
  const s = index.strings;
  const kindRows = index.symbols.kinds.map((k) => el("li", {}, [el("span", { class: "swatch " + KIND_CLASS[k] }), el("span", {}, [s["key_kind_" + k]])]));
  const stateRows = index.symbols.states.map((st) => el("li", {}, [el("span", { class: "swatch k-theorem " + STATE_CLASS[st] }), el("span", {}, [s["key_state_" + st]])]));
  return el("div", { class: "key-content" }, [
    el("h2", {}, [s.key_kinds_heading]), el("ul", {}, kindRows),
    el("h2", {}, [s.key_states_heading]), el("ul", {}, stateRows),
  ]);
}

export async function start(doc, deps) {
  const failure = { reason: null };
  let handle = null, sheet = null, layer = null, fallbackEl = null, cardsEl = null;

  /* THE ONE TEARDOWN. `signal` goes to EVERY addEventListener in page code (the sheet's too), `offs` holds the unsubscribe
     function of EVERY engine subscription, and `dead` is the mark each async continuation checks after an await. The
     fallback runs all of it first, so once it has run no listener fires and no continuation touches the page again; the
     builder's cards and the one fallback sentence stay exactly as it left them. (sources.test.mjs scans for a listener
     without the signal.) */
  const ctl = new AbortController();
  const signal = ctl.signal;
  const offs = [];
  let dead = false;

  function fallback(reason) {
    if (dead) return;
    dead = true;
    failure.reason = String(reason);
    ctl.abort();
    for (const off of offs.splice(0)) { try { off(); } catch (e) { /* the page is being put back; carry on */ } }
    try { if (handle) handle.destroy(); } catch (e) { /* the same */ }
    try { if (sheet) sheet.dispose(); } catch (e) { /* the same */ }
    if (layer && layer.parentNode) layer.parentNode.removeChild(layer);
    if (fallbackEl) fallbackEl.hidden = false;
    if (cardsEl) cardsEl.hidden = false;
  }

  try {
    const q = {};
    for (const id of SHELL) {
      q[id] = doc.getElementById(id);
      if (!q[id]) throw new Error("the shell lacks " + id);
    }
    layer = q["graph-layer"]; fallbackEl = q["graph-fallback"]; cardsEl = q["graph-cards"];
    const data = createData(deps.fetch);
    const index = await data.loadIndex();
    const strings = index.strings;
    const roots = await data.loadRoots();

    /* The cards: id -> the builder's own <article>, read once. Keys are checked ids; a lookup never builds a selector. */
    const articles = new Map();
    cardsEl.querySelectorAll("article[id]").forEach((a) => { if (isId(a.id) && !articles.has(a.id)) articles.set(a.id, a); });
    const aboutEl = q["graph-about"];
    const keyEl = buildKey(index);

    const openIds = new Set();
    const routes = {};
    sheet = createSheet(
      { root: q["graph-sheet"], crumbs: q["graph-crumbs"], tools: q["graph-sheet-tools"], body: q["graph-sheet-body"], closeButton: q["graph-sheet-close"] },
      strings,
      {
        closeButton: () => routes["close-button"](),
        go: (id) => routes["deep-link"](id),
        openParts: (id) => routes["open-parts"](id),
        closeParts: (id) => { if (handle) handle.close(id); },
      },
      signal,
    );

    const notice = q["graph-notice"];
    function say(text) { if (dead) return; notice.replaceChildren(doc.createTextNode(text)); notice.hidden = false; }
    function hush() { notice.hidden = true; }

    function openCard(id) {
      const art = articles.get(id), m = data.meta(id);
      const anc = m ? m.path.map((a) => data.meta(a)) : [];
      if (!art || !m || anc.some((a) => !a)) { say(strings.link_refused); return false; }
      const proof = art.querySelector(":scope > p.status.proof");
      const status = [strings["status_" + m.state]].concat(proof ? [proof.textContent] : []).join(" · ");
      const ok = sheet.showCard(art, {
        id, status, canParts: m.childCount > 0, partsOpen: openIds.has(id),
        crumbs: anc.concat(m).map((x) => ({ id: x.id, title: x.title, role: x.role })),
      });
      if (ok) { hush(); handle.select(id); }
      return ok;
    }

    /* The one rule for a route that fails: after the fallback nothing is said or done; a 4xx is a notice; anything else is the fallback. */
    function failed(e) {
      if (dead) return false;
      if (e instanceof DataError && /^http-4/.test(e.code)) { say(strings.link_refused); return false; }
      fallback(e && e.message);
      return false;
    }

    /* The step is loaded (and validated) BEFORE the open card is touched: a failed load leaves it open. After every await,
       a dead page does nothing. */
    async function go(id) {
      if (dead) return false;
      if (!isId(id)) { say(strings.link_refused); return false; }
      try {
        const step = await data.loadStep(id);
        if (dead) return false;
        if (!sheet.close()) return false;
        await handle.reveal(step.path.concat(id));
        if (dead) return false;
        return openCard(id);
      } catch (e) {
        return failed(e);
      }
    }

    routes["close-button"] = () => sheet.close();
    routes["tap-outside"] = () => sheet.close();
    routes["escape"] = () => sheet.close();
    routes["open-card"] = (id) => openCard(id);
    routes["deep-link"] = go;
    routes["toolbar-show-all"] = () => { if (sheet.close()) handle.fit(); };
    routes["toolbar-key"] = () => { if (sheet.shown() === keyEl) sheet.close(); else sheet.showPanel(keyEl, false); };
    routes["toolbar-about"] = () => { if (sheet.shown() === aboutEl) sheet.close(); else sheet.showPanel(aboutEl, true); };
    routes["open-parts"] = async (id) => {
      try {
        if (dead || !sheet.close()) return;
        const m = data.meta(id);
        if (m && await handle.open(id)) {
          if (dead) return;
          await handle.reveal(m.path.concat(id));
        }
      } catch (e) {
        failed(e);
      }
    };
    for (const name of CLOSE_ROUTES) if (typeof routes[name] !== "function") throw new Error("no route for " + name);

    q["graph-show-all"].addEventListener("click", () => routes["toolbar-show-all"](), { signal });
    q["graph-key"].addEventListener("click", () => routes["toolbar-key"](), { signal });
    q["graph-about-open"].addEventListener("click", () => routes["toolbar-about"](), { signal });
    doc.addEventListener("keydown", (e) => { if (e.key === "Escape") routes["escape"](); }, { signal });
    doc.defaultView.addEventListener("hashchange", () => { const id = hashId(doc); if (id !== null) routes["deep-link"](id); }, { signal });

    layer.hidden = false;
    handle = deps.createGraph(q["graph"], {
      roots, maxChildren: index.maxChildren, sizes: { ...CARD_SIZES },
      loadChildren: (id) => data.loadChildren(id),
      renderFace: makeRenderFace(strings),
    });
    const guard = (fn) => (...a) => { if (dead) return; try { fn(...a); } catch (e) { fallback(e && e.message); } };
    offs.push(handle.on("tap", guard((node) => { if (node) routes["open-card"](node.id); else routes["tap-outside"](); })));
    offs.push(handle.on("open", guard((node) => { openIds.add(node.id); sheet.setPartsOpen(node.id, true); })));
    offs.push(handle.on("close", guard((node) => { openIds.delete(node.id); sheet.setPartsOpen(node.id, false); })));
    offs.push(handle.on("error", guard((node, reason) => {
      if (reason === "path-not-found") say(strings.link_refused); else fallback("engine error " + reason);
    })));
    offs.push(handle.on("refused", guard((node, reason) => {
      if (reason === "invalid-path") say(strings.link_refused); else fallback("engine refused " + reason);
    })));

    const ready = await handle.ready;
    if (dead) return failure;
    if (!ready) { fallback("the engine refused the roots"); return failure; }
    await new Promise((r) => doc.defaultView.requestAnimationFrame(() => r()));
    if (dead) return failure;
    fallbackEl.hidden = true;     // only after the first graph frame is drawn
    cardsEl.hidden = true;
    const first = hashId(doc);
    if (first !== null) await routes["deep-link"](first);
  } catch (e) {
    fallback(e && e.message ? e.message : "setup failed");
  }
  return failure;
}

if (typeof document !== "undefined") {
  start(document, { createGraph, fetch: (address) => fetch(address) });
}
