/* The page layer's entry. It creates the engine on the stage, wires the engine's events to the sheet and the toolbar,
   builds the key from the contract's closed lists, handles deep links and the fallback. One-way: this page imports the
   engine; the engine imports nothing of the page.

   FAILURES split by class (data.js isTransportCode is the one allow-list): a TRANSPORT failure (a rejected fetch, a non-2xx status) is a
   notice and the reader may tap again; data that ARRIVED and is invalid, and anything unclassified, is the fallback. No string from
   an exception or a server reaches the page.

   THE SEAM: start(doc, {createGraph, fetch}) takes the engine's createGraph and a fetch-like as arguments. The last
   lines of this module call it with the real ones; a test calls it with a stand-in engine. Nothing else is injected. */
import { createGraph } from "../engine/index.js";
import { el, isId } from "./dom.js";
import { createData, DataError, isTransportCode, KIND_CLASS, STATE_CLASS, SHEET_PROOF_CLASS } from "./data.js";
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
   census frame). 140 leaves 2 px. At a 390 x 844 phone the first fit is limited by the HEIGHT of the three stacked top cards
   (3 x nodeH + 2 x gapY against the stage), so with the engine's default row gap (76) the fit scale was 0.966 and the title
   14.49 px at fit. gapY 56 (still room for the link arrow, 20 px) takes the world from 572 to 532 px high and the scale to
   1.038. The engine's other sizes stay at its defaults. */
const CARD_SIZES = Object.freeze({ nodeH: 140, gapY: 56 });

const SHELL = ["graph-layer", "graph", "graph-sheet", "graph-crumbs", "graph-sheet-tools", "graph-sheet-body", "graph-sheet-close",
  "graph-show-all", "graph-key", "graph-about-open", "graph-fallback", "graph-cards", "graph-notice", "graph-about"];

function hashId(doc) {
  const h = doc.defaultView.location.hash;
  if (!h || h === "#") return null;
  try { return decodeURIComponent(h.slice(1)); } catch (e) { return ""; }
}

/* The key: one row per kind, then per state, as the builder's symbols.order lists them (the rows that occur on this map), each
   with its label strings[row.words]. A states section whose order is empty is absent whole, heading included: the builder says
   what the key shows. (Proofs have no section in the key: a proof shows only in the sheet's status line.) */
function buildKey(index) {
  const s = index.strings, w = index.symbols.words;
  const kindRows = index.symbols.order.kinds.map((k) => el("li", {}, [el("span", { class: "swatch " + KIND_CLASS[k] }), el("span", {}, [s[w.kinds[k]]])]));
  const stateRows = index.symbols.order.states.map((st) => el("li", {}, [el("span", { class: "swatch k-theorem " + STATE_CLASS[st] }), el("span", {}, [s[w.states[st]]])]));
  const parts = [el("h2", {}, [s.key_kinds_heading]), el("ul", {}, kindRows)];
  if (typeof s.key_kinds_note === "string") parts.push(el("p", { class: "key-note" }, [s.key_kinds_note]));   // optional: one plain line under the kind rows
  if (stateRows.length > 0) parts.push(el("h2", {}, [s.key_states_heading]), el("ul", {}, stateRows));
  return el("div", { class: "key-content" }, parts);
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
      const w = index.symbols.words;
      /* The sheet's one line. A kind whose table row has `card_words` (a folder or file asserts nothing) shows that word and nothing from
         state or proof; every other kind shows the state and the proof, as before. The TABLE's row decides, never the kind's name. The same
         condition ends the breadcrumb at the PARENT (the open card is not listed; the sheet heading carries its title). */
      const cardWord = index.symbols.cardWords[m.kind];
      const status = cardWord !== undefined ? strings[cardWord] : [strings[w.states[m.state]], strings[w.proofs[m.proof]]].join(" · ");
      const ok = sheet.showCard(art, {
        id, status, canParts: m.childCount > 0, partsOpen: openIds.has(id), sheetClass: SHEET_PROOF_CLASS[m.proof],
        currentListed: cardWord === undefined,
        crumbs: (cardWord !== undefined ? anc : anc.concat(m)).map((x) => ({ id: x.id, title: x.title, role: x.role })),
      });
      if (ok) { hush(); handle.select(id); }
      return ok;
    }

    /* The one rule for a route that fails (the data layer's DataError reaches it directly). After the fallback nothing is said or
       done. A 4xx names no step: the refused-link notice. Any other TRANSPORT failure (an allow-list of known codes, data.js
       isTransportCode) is the parts notice: the reader may try again, nothing is retried for them. Everything else, data that
       arrived and is invalid, a code not on the list, a plain exception, is the fallback. No string from the exception or the server
       is ever written: the notices are page constants (strings.*). */
    function failed(e) {
      if (dead) return false;
      const code = e instanceof DataError ? e.code : null;
      if (isTransportCode(code) && code.startsWith("http-4")) { say(strings.link_refused); return false; }
      if (isTransportCode(code)) { say(strings.parts_failed_notice); return false; }
      fallback(e && e.message);
      return false;
    }

    /* The step is loaded (and validated) BEFORE the open card is touched, and that ordering is the retry story: a failed load,
       transport or data, has changed nothing yet, so the reader's open card is still open and intact, the map is as it was, and
       a tap or an address again is a clean second attempt (data.js drops a failed load from its cache). After every await, a
       dead page does nothing. */
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
    /* What the engine tells us about a failed load is a string; the class of the failure is decided here, from the exception itself:
       id -> the DataError code of the last failed load of that node's parts, or null for anything that was not a DataError. */
    const loadFailures = new Map();
    handle = deps.createGraph(q["graph"], {
      roots, maxChildren: index.maxChildren, sizes: { ...CARD_SIZES },
      zoom: { fitMin: 1 },      // the first view never zooms below scale 1 (text at its size); 'Show all' (handle.fit()) still shows all
      loadChildren: (id) => data.loadChildren(id).catch((e) => { loadFailures.set(id, e instanceof DataError ? e.code : null); throw e; }),
      renderFace: makeRenderFace(strings, index.symbols.countWords),
    });
    const guard = (fn) => (...a) => { if (dead) return; try { fn(...a); } catch (e) { fallback(e && e.message); } };
    offs.push(handle.on("tap", guard((node) => { if (node) routes["open-card"](node.id); else routes["tap-outside"](); })));
    offs.push(handle.on("open", guard((node) => { openIds.add(node.id); sheet.setPartsOpen(node.id, true); })));
    offs.push(handle.on("close", guard((node) => { openIds.delete(node.id); sheet.setPartsOpen(node.id, false); })));
    offs.push(handle.on("error", guard((node, reason) => {
      const code = node ? loadFailures.get(node.id) : undefined;
      if (node) loadFailures.delete(node.id);
      if (reason === "path-not-found") say(strings.link_refused);
      else if (reason === "load-failed" && isTransportCode(code)) say(strings.parts_failed_notice);    // the node stays closed; the reader taps again
      else fallback("engine error " + reason);
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
