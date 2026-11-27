/* The page layer's entry. It creates the engine on the stage, wires the engine's events to the sheet and the toolbar,
   builds the key from the contract's closed lists, handles deep links and the fallback. One-way: this page imports the
   engine; the engine imports nothing of the page.

   FAILURES split by class (data.js isTransportCode is the one allow-list): a TRANSPORT failure (a rejected fetch, a non-2xx status) is a
   notice and the reader may tap again; data that ARRIVED and is invalid, and anything unclassified, is the fallback. No string from
   an exception or a server reaches the page.

   THE SEAM: start(doc, {createGraph, fetch}) takes the engine's createGraph and a fetch-like as arguments. The last
   lines of this module call it with the real ones; a test calls it with a stand-in engine. Nothing else is injected. */
import { createGraph, checkOptions } from "../engine/index.js";
import { el, isId, titleChildren } from "./dom.js";
import { createData, DataError, checkedOptions, isTransportCode, KIND_CLASS, STATE_CLASS, SHEET_PROOF_CLASS, EDGE_BASIS_HEADING, TYPESET_STRINGS } from "./data.js";
import { makeRenderFace } from "./face.js";
import { templateParts } from "./note.js";
import { createSheet } from "./sheet.js";
import { createGraphView, buildSpinePanel } from "./graphview.js";

/* Every way the sheet can close. Each one is a function in `routes` below that begins with the sheet's one close
   function; a case drives each of these with a cancelling listener installed. */
export const CLOSE_ROUTES = Object.freeze([
  "close-button", "tap-outside", "escape", "open-card", "deep-link", "toolbar-show-all", "toolbar-key", "toolbar-about", "open-parts",
]);
/* The routes of the Graph view (graphview.js); they exist on every map but do something only on one that carries the view. Each begins with the sheet's close
   function like the routes above, so the same cancelling-listener case drives them on a map that has the view. */
export const VIEW_ROUTES = Object.freeze(["view-graph", "view-cards", "spine-open", "spine-show-file"]);

/* ONE fixed closed size, chosen by measuring in the browser (the browser case "one fixed closed size"): a 50-character title of
   the widest glyphs takes three lines at 15 px in the engine's default 300 px width, and with the role word and the foot at
   14 px the face needs 138 px for every kind and state frame (measured on both engines; 136 clips the title in the thicker
   census frame). 140 leaves 2 px. At a 390 x 844 phone the first fit is limited by the HEIGHT of the three stacked top cards
   (3 x nodeH + 2 x gapY against the stage), so with the engine's default row gap (76) the fit scale was 0.966 and the title
   14.49 px at fit. gapY 56 (still room for the link arrow, 20 px) takes the world from 572 to 532 px high and the scale to
   1.038. The engine's other sizes stay at its defaults. */
const CARD_SIZES = Object.freeze({ nodeH: 140, gapY: 56 });

/* THE MADE CARD. The builder's card block may hold no card articles at all (the Lean map's assembler writes the About section only); a card the
   markup lacks for an id the data knows is MADE here, from the step's title alone: a div.card holding one h3.claim (the title through titleChildren,
   so a backtick span is a code element and nothing in a title is markup). Nothing else is invented: no paragraph, no list of parts, and no id of any
   kind on it (the page keys cards by its own Map, never by a DOM id). The sheet adds the status line and the note, as for any card. */
export function madeCard(title, elFn = el) {
  return elFn("div", { class: "card" }, [elFn("h3", { class: "claim" }, titleChildren(title, elFn))]);
}

const SHELL = ["graph-layer", "graph", "graph-sheet", "graph-crumbs", "graph-sheet-tools", "graph-sheet-body", "graph-sheet-close",
  "graph-show-all", "graph-key", "graph-about-open", "graph-fallback", "graph-cards", "graph-notice", "graph-about"];

function hashId(doc) {
  const h = doc.defaultView.location.hash;
  if (!h || h === "#") return null;
  try { return decodeURIComponent(h.slice(1)); } catch (e) { return ""; }
}

/* The key: one row per kind, then per state, as the builder's symbols.order lists them (the rows that occur on this map), each
   with its label strings[row.words]. A states section whose order is empty is absent whole, heading included: the builder says
   what the key shows. (Proofs have no section in the key: a proof shows only in the sheet's status line.) Two optional additions, each absent
   on the live map: `key_scope_text` is the key's FIRST child (one paragraph), and when the index carries `edge_basis` the key ends with a
   section after everything else: an h2 with `key_lines_heading` and one paragraph holding strings[edge_basis.words]. The page prints the
   key `words` names and never names that key itself. Every one of them is a single text node, backticks and all. */
function buildKey(index) {
  const s = index.strings, w = index.symbols.words;
  const kindRows = index.symbols.order.kinds.map((k) => el("li", {}, [el("span", { class: "swatch " + KIND_CLASS[k] }), el("span", {}, [s[w.kinds[k]]])]));
  const stateRows = index.symbols.order.states.map((st) => el("li", {}, [el("span", { class: "swatch k-theorem " + STATE_CLASS[st] }), el("span", {}, [s[w.states[st]]])]));
  const parts = [];
  if (typeof s.key_scope_text === "string") parts.push(el("p", { class: "key-scope" }, [s.key_scope_text]));   // optional: the key's first paragraph
  parts.push(el("h2", {}, [s.key_kinds_heading]), el("ul", {}, kindRows));
  if (typeof s.key_kinds_note === "string") parts.push(el("p", { class: "key-note" }, [s.key_kinds_note]));   // optional: one plain line under the kind rows
  if (stateRows.length > 0) parts.push(el("h2", {}, [s.key_states_heading]), el("ul", {}, stateRows));
  if (index.edgeBasis) parts.push(el("h2", {}, [s[EDGE_BASIS_HEADING]]), el("p", { class: "key-lines" }, [s[index.edgeBasis.words]]));
  return el("div", { class: "key-content" }, parts);
}

export async function start(doc, deps) {
  const failure = { reason: null };
  let handle = null, sheet = null, layer = null, fallbackEl = null, cardsEl = null, view = null;

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
    try { if (view) view.destroy(); } catch (e) { /* the same */ }
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

    /* The cards: id -> the builder's own <article>, read once. Keys are checked ids; a lookup never builds a selector. A card the markup lacks is
       made on its first open (openCard) and kept in this same Map, so a reopen shows the same element. */
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

    /* A MAP CARRIES NOTES iff its index strings hold BOTH note_label and note_source (data the page has at start; the live map has neither).
       On a map that carries notes, the step's own file is loaded (it is cached when the card's parents or a deep link already loaded it) BEFORE
       the sheet is touched, because the repository's note lives in that file: a failed load changes nothing (the open card stays open) and goes
       through failed(). On a map that does not, there is no note to fetch, so openCard touches the sheet exactly as it always did: at once, from
       the markup, with no step load in its path, and no fetch result can delay it or prevent it.

       ONE NAVIGATION TICKET. `nav` is bumped by EVERY route the reader can take (the `routes` table is wrapped once, below, so each entry takes
       a ticket; an in-sheet close request takes one too). An async route (openCard, go, open-parts) captures its ticket at entry and
       asks `current(t)` after every await and at the top of its catch: a superseded route does nothing (no sheet change, no camera move,
       no notice, no failed(), no fallback). A route that continues into another (go into openCard) hands its own ticket on, so the
       continuation is the same navigation and is not refused by it. */
    let nav = 0;
    const current = (t) => !dead && t === nav;
    /* THE ENGINE'S EVENTS ARE A CHANNEL TOO. The engine says `error` / `refused` BEFORE the promise a route awaits settles (and `invalid-path` inside
       the call itself), so by the time the route's own post-await check could run, the handler has already spoken. So a route's engine call is
       recorded here, with the route's ticket and the node ids the call works on, for exactly as long as the call is pending; the handlers ask
       `supersededCall(node)`: an event is the effect of a superseded route when at least one pending route call covers its node (a null node, as in
       `path-not-found`, is covered by any) and none of those calls belongs to the current ticket. An event with no route call pending, which is a
       gesture the reader made on the map, is not covered: it is shown exactly as before. This is the ticket again, not a second sequence. */
    const engineCalls = new Set();
    /* THE INVARIANT: a route starts an engine call only while its ticket is current, checked synchronously before each viaRoute. */
    async function viaRoute(t, ids, call) {
      const rec = { t, ids: new Set(ids) };
      engineCalls.add(rec);
      try { return await call(); } finally { engineCalls.delete(rec); }
    }
    function supersededCall(node) {
      let covered = false;
      for (const rec of engineCalls) {
        if (node && !rec.ids.has(node.id)) continue;
        if (current(rec.t)) return false;
        covered = true;
      }
      return covered;
    }
    /* The maths-face view of a note (formulas in the maths face, the line, the button) is on only when the data carries ALL FOUR of its words; the page
       draws exactly those words. With any one missing it is null and the note renders as it always did. */
    const typesetWords = TYPESET_STRINGS.every((k) => typeof strings[k] === "string" && strings[k] !== "")
      ? { label: strings.note_label_typeset, line: strings.note_typeset_line, exactButton: strings.note_exact_button, renderButton: strings.note_render_button }
      : null;
    const hasOwn = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
    const carriesNotes = hasOwn(strings, "note_label") && hasOwn(strings, "note_source");
    /* The sheet's one open. `step` is the loaded step on a map that carries notes; on one that does not it is undefined and no `note` key is passed. */
    function showOpenCard(id, art, m, anc, step) {
      const w = index.symbols.words;
      /* The sheet's one line. A kind whose table row has `card_words` (a folder or file asserts nothing) shows that word and nothing from
         state or proof; every other kind shows the state and the proof, as before. The TABLE's row decides, never the kind's name. The same
         condition ends the breadcrumb at the PARENT (the open card is not listed; the sheet heading carries its title). */
      const cardWord = index.symbols.cardWords[m.kind];
      const status = cardWord !== undefined ? strings[cardWord] : [strings[w.states[m.state]], strings[w.proofs[m.proof]]].join(" · ");
      const ok = sheet.showCard(art, {
        id, status, canParts: m.childCount > 0, partsOpen: openIds.has(id), sheetClass: SHEET_PROOF_CLASS[m.proof],
        currentListed: cardWord === undefined,
        ...(step === undefined ? {} : {
          note: step.note ? { label: strings.note_label, text: step.note.text, typeset: typesetWords,
            sourceParts: templateParts(strings.note_source, { source: step.note.source, commit: step.note.commit.slice(0, 8) }) } : null }),
        crumbs: (cardWord !== undefined ? anc : anc.concat(m)).map((x) => ({ id: x.id, title: x.title, role: x.role })),
      });
      if (ok) { hush(); handle.select(id); }
      return ok;
    }
    /* Not async, on purpose: on a map that carries no notes it returns the boolean at once, as it always did, and an exception from the sheet reaches
       the caller synchronously (a tap's guard, or go's catch). On a map that carries notes it returns the promise of the open. */
    function openCard(t, id) {
      const m = data.meta(id);
      const anc = m ? m.path.map((a) => data.meta(a)) : [];
      if (!m || anc.some((a) => !a)) { say(strings.link_refused); return false; }
      let art = articles.get(id);       // the markup's own card wins; only an id it has none for gets a made one
      if (!art) { art = madeCard(m.title); articles.set(id, art); }
      if (!carriesNotes) return showOpenCard(id, art, m, anc, undefined);
      return openCardWithNote(t, id, art, m, anc);
    }
    async function openCardWithNote(t, id, art, m, anc) {
      try {
        const step = await data.loadStep(id);
        if (!current(t)) return false;
        return showOpenCard(id, art, m, anc, step);
      } catch (e) {
        if (!current(t)) return false;
        return failed(e);
      }
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
    async function go(t, id) {
      if (!current(t)) return false;
      if (!isId(id)) { say(strings.link_refused); return false; }
      try {
        const step = await data.loadStep(id);
        if (!current(t)) return false;
        if (!sheet.close()) return false;
        if (view && view.view() === "graph") view.hide();      // an address names a card: it is shown in Cards, the view the cards live in
        const path = step.path.concat(id);
        await viaRoute(t, path, () => handle.reveal(path));
        if (!current(t)) return false;
        return openCard(t, id);        // the same ticket: one navigation, not a second one
      } catch (e) {
        if (!current(t)) return false;
        return failed(e);
      }
    }

    routes["close-button"] = () => sheet.close();
    routes["tap-outside"] = () => sheet.close();
    routes["escape"] = () => sheet.close();
    routes["open-card"] = (t, id) => openCard(t, id);
    routes["deep-link"] = go;
    routes["toolbar-show-all"] = () => { if (sheet.close()) { if (view && view.view() === "graph") view.fit(); else handle.fit(); } };
    routes["toolbar-key"] = () => {
      const k = view && view.view() === "graph" ? view.key(EDGE_BASIS_HEADING) : keyEl;     // the Graph view's key says what its boxes and lines are
      if (sheet.shown() === k) sheet.close(); else sheet.showPanel(k, false);
    };
    routes["toolbar-about"] = () => { if (sheet.shown() === aboutEl) sheet.close(); else sheet.showPanel(aboutEl, true); };
    routes["open-parts"] = async (t, id) => {
      try {
        if (!current(t) || !sheet.close()) return;
        const m = data.meta(id);
        const path = m ? m.path.concat(id) : [];
        if (m && await viaRoute(t, path, () => handle.open(id))) {
          if (!current(t)) return;
          await viaRoute(t, path, () => handle.reveal(path));
        }
      } catch (e) {
        if (!current(t)) return;
        failed(e);
      }
    };
    /* THE GRAPH VIEW's routes (graphview.js). They exist on every map and do nothing on one without the view (`view` stays null: no switch is drawn, no
       request is made). Each begins with the sheet's close function and takes its ticket like the routes above. */
    routes["view-graph"] = async (t) => {
      if (!view || !current(t) || !sheet.close()) return false;
      return view.show(t);
    };
    routes["view-cards"] = (t) => {
      if (!view || !current(t) || !sheet.close()) return false;
      view.hide();
      return true;
    };
    /* A spine box tapped: the file's own title is wanted for the sheet's line, so the step is loaded BEFORE the sheet is touched (a failed load changes nothing:
       the retry story of go). The sheet shows the box's names, its sentence, where it lives and the button to the file's sheet in Cards. */
    routes["spine-open"] = async (t, id) => {
      if (!view || !current(t)) return false;
      const node = view.node(id);
      if (!node) { say(strings.link_refused); return false; }
      try {
        const step = await data.loadStep(node.file);
        if (!current(t)) return false;
        if (!sheet.close()) return false;
        const panel = buildSpinePanel(strings, node, titleChildren(step.card.title), (file) => routes["spine-show-file"](file), signal);
        if (!sheet.showPanel(panel, false)) return false;
        hush();
        view.select(id);
        return true;
      } catch (e) {
        if (!current(t)) return false;
        return failed(e);
      }
    };
    /* 'Show its file': switch to Cards and open that file's sheet there. The file's step is loaded first, so an id that is no step the page can load is the
       refused-link notice and leaves the Graph view as it is; then the one navigation continues into go with the same ticket. */
    routes["spine-show-file"] = async (t, id) => {
      if (!view || !current(t)) return false;
      try {
        await data.loadStep(id);
        if (!current(t)) return false;
        if (!sheet.close()) return false;
        view.hide();
        return await go(t, id);
      } catch (e) {
        if (!current(t)) return false;
        return failed(e);
      }
    };
    /* The one place a route takes its ticket: every entry above is wrapped here, so a route added later cannot forget it. */
    for (const name of Object.keys(routes)) {
      const run = routes[name];
      routes[name] = (...a) => run(++nav, ...a);
    }
    /* The in-sheet close request closes through the sheet's own listener, not through a route: it takes a ticket here, so a card still loading
       cannot open over a close the reader asked for. */
    q["graph-sheet"].addEventListener("sheetcloserequest", () => { nav++; }, { signal });
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
    const options = {
      roots, maxChildren: index.maxChildren, sizes: { ...CARD_SIZES },
      // the first view never zooms below scale 1 (text at its size); 'Show all' (handle.fit()) still shows all. A map's open_scale_floor
      // (data v3; absent on the live map, and then there is no frameMin key) is merged in as the floor of an opened node's framing.
      zoom: { fitMin: 1, ...(index.openScaleFloor !== undefined ? { frameMin: index.openScaleFloor } : {}) },
      // the map's sibling_layout (data v3; absent on the live map, and then there is no `layout` key at all): "column"
      ...(index.siblingLayout !== undefined ? { layout: { siblings: index.siblingLayout } } : {}),
      loadChildren: (id) => data.loadChildren(id).catch((e) => { loadFailures.set(id, e instanceof DataError ? e.code : null); throw e; }),
      renderFace: makeRenderFace(strings, index.symbols.countWords),
    };
    /* The engine's own rule, asked BEFORE createGraph on the exact options it will get: a floor outside the engine's range is this page's
       bad-scale-floor (the fallback, through the setup catch), any other refusal is the engine's TypeError as before (data.js checkedOptions). */
    checkedOptions(checkOptions, options, index.openScaleFloor);
    handle = deps.createGraph(q["graph"], options);
    const guard = (fn) => (...a) => { if (dead) return; try { fn(...a); } catch (e) { fallback(e && e.message); } };
    offs.push(handle.on("tap", guard((node) => { if (node) routes["open-card"](node.id); else routes["tap-outside"](); })));
    offs.push(handle.on("open", guard((node) => { openIds.add(node.id); sheet.setPartsOpen(node.id, true); })));
    offs.push(handle.on("close", guard((node) => { openIds.delete(node.id); sheet.setPartsOpen(node.id, false); })));
    offs.push(handle.on("error", guard((node, reason) => {
      const code = node ? loadFailures.get(node.id) : undefined;
      if (node) loadFailures.delete(node.id);
      if (supersededCall(node)) return;       // the effect of a route the reader has moved on from: no notice, no fallback
      if (reason === "path-not-found") say(strings.link_refused);
      else if (reason === "load-failed" && isTransportCode(code)) say(strings.parts_failed_notice);    // the node stays closed; the reader taps again
      else fallback("engine error " + reason);
    })));
    offs.push(handle.on("refused", guard((node, reason) => {
      if (supersededCall(node)) return;
      if (reason === "invalid-path") say(strings.link_refused); else fallback("engine refused " + reason);
    })));

    const ready = await handle.ready;
    if (dead) return failure;
    if (!ready) { fallback("the engine refused the roots"); return failure; }
    await new Promise((r) => doc.defaultView.requestAnimationFrame(() => r()));
    if (dead) return failure;
    fallbackEl.hidden = true;     // only after the first graph frame is drawn
    cardsEl.hidden = true;
    /* The Graph view, only on a map whose index carries both view words (validateIndex says so in index.graphView): the switch and the view's stage are made
       now, and nothing is requested until the reader presses Graph. */
    if (index.graphView) {
      failure.graph = null;
      view = createGraphView({
        doc, layer, cardsStage: q["graph"], strings, index, fetch: deps.fetch, createGraph: deps.createGraph, checkOptions, checkedOptions, say, hush, failure, current: (t) => current(t),
        onSwitch: (which) => routes[which === "graph" ? "view-graph" : "view-cards"](),
        onTap: (node) => { if (node) routes["spine-open"](node.id); else routes["tap-outside"](); },
        signal,
      });
    }
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
