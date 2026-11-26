/* The Graph view: the Lean map's main results, nine boxes and the links between them, drawn by a SECOND instance of the engine on its own stage, beside
   the Cards view the page has always been. It exists only when the index carries BOTH view words (data.js validateIndex; the page checks nothing else to
   know). Its data is graph/spine.json, read ONCE, at the first switch to it (never at start, so a reader who stays in Cards pays nothing), validated by
   spine.js, and drawn from its links in the reduction.

   A refusal at the switch (a failed read, a refused file, the engine refusing the roots) leaves the page as it was: Cards stays standing, the stage stays
   hidden and empty, one page-constant notice is shown, the code is kept in memory (failure.graph) and told to the world as ONE event, FAILURE_EVENT, with a
   code from a FIXED set (FAILURE_CODES) and nothing else. A second press of Graph tries again; after a refusal, the retry's success is told as the same event
   with code null. Nothing in the page listens to the event, so it can never become a control path. Any script in this page's realm can hear it; today the
   only script is ours, by the page's CSP, and that is why the detail carries a code and nothing else.

   Every element is built by dom.js el() (the one allow-list): the two switch buttons and the stage are found by class and data-id, not by id. Text from the
   data (content, names, the file's title) goes in only as text nodes or through dom.js titleChildren; no markup is parsed. */
import { el, titleChildren } from "./dom.js";
import { DataError, fetchJson, isTransportCode } from "./data.js";
import { validateSpine, spineRoots } from "./spine.js";

/* THE EVENT. One name for the whole page ('graphpage-failure', namespaced so a bare generic name on document cannot be fired or clobbered by another script),
   detail {stage: 'graph', code}; the start failure's {stage: 'start', code} is the smoke test's own stacked change. `code` is a member of FAILURE_CODES or null. */
export const FAILURE_EVENT = "graphpage-failure";
export const FAILURE_CODES = Object.freeze(["fetch-failed", "not-json", "http-error", "bad-type", "missing-key", "extra-key", "bad-format", "bad-commit",
  "bad-edge-basis", "bad-spine-node", "bad-spine-link", "engine-refused", "graph-failed"]);

/* The code of a failure: the DataError's own code when it is one of the fixed set, `http-error` for any HTTP status code (the number is data), and
   `graph-failed` for everything else (an engine exception, a plain error). No text of an exception, and no text of the data, ever becomes a code. */
export function failureCode(e) {
  const code = e instanceof DataError ? e.code : null;
  if (code !== null && FAILURE_CODES.includes(code)) return code;
  if (code !== null && isTransportCode(code) && code.startsWith("http-")) return "http-error";
  return "graph-failed";
}

/* The spine boxes' sizes: wider and shorter than a step card, because the face is one sentence. Measured in the browser at 390 x 844 (docs/tools.md says how). */
export const SPINE_SIZES = Object.freeze({ nodeW: 220, nodeH: 112, gapX: 20, gapY: 36 });
/* The first fit may go below scale 1 (the whole graph is nine boxes in five rows): the floor is lower than the Cards view's. */
export const SPINE_ZOOM = Object.freeze({ fitMin: 0.4 });

/* The face of a spine box: the row's `content` sentence alone, as text (a backtick span as <code>), cut to the card's three lines by the CSS. */
export function renderSpineFace(spec) {
  const d = spec && spec.data;
  if (!d || typeof d.content !== "string" || d.content === "") throw new TypeError("a spine box without its sentence");
  return el("div", { class: "face spine-face" }, [el("div", { class: "face-title" }, titleChildren(d.content))]);
}

/* The Graph view's key: what a box is, then the heading of the lines section and the spine's sentence about them (the key `words` of the spine's edge_basis
   names, found by spine.js: this module never names it). */
export function buildGraphKey(strings, headingKey, sentence) {
  const kids = [el("p", { class: "key-scope" }, [strings.graph_nodes_text])];
  if (typeof strings[headingKey] === "string" && strings[headingKey] !== "") kids.push(el("h2", {}, [strings[headingKey]]));
  kids.push(el("p", { class: "key-lines" }, [sentence]));
  return el("div", { class: "key-content" }, kids);
}

/* The sheet panel of a spine box: the names (the row's first cell, as code), the label and the sentence, the line telling where the box lives (the template with
   {title} filled by the file's own title, as text), and the button to the file's sheet in Cards. `titleKids` is titleChildren of the file's card title. */
export function buildSpinePanel(strings, data, titleKids, onShowFile, signal) {
  const names = [];
  data.names.forEach((n, i) => { if (i > 0) names.push(", "); names.push(el("code", {}, [n])); });
  const lives = String(strings.spine_lives_in).split("{title}");
  const livesKids = [];
  lives.forEach((part, i) => { if (i > 0) livesKids.push(...titleKids); if (part !== "") livesKids.push(part); });
  const button = el("button", { type: "button", class: "sheet-tool spine-show-file", "data-id": data.file }, [strings.spine_show_file]);
  button.addEventListener("click", () => onShowFile(data.file), { signal });
  return el("div", { class: "spine-panel" }, [
    el("h2", { class: "spine-names" }, names),
    el("p", { class: "spine-label" }, [strings.spine_content_label]),
    el("p", { class: "spine-content" }, titleChildren(data.content)),
    el("p", { class: "spine-lives" }, livesKids),
    button,
  ]);
}

/* createGraphView(deps): builds the switch and the stage and returns the view's handle. deps:
   doc, layer (#graph-layer), cardsStage (the Cards view's stage, #graph), strings, index (validateIndex's record), fetch (fetch-like),
   createGraph, checkOptions, checkedOptions (the engine and data.js's own rule), say / hush (the page's one notice), failure (the page's record),
   current(ticket) (the page's navigation ticket check), onSwitch(which) (the button routes), onTap(node) (a box tapped, null for empty stage), signal. */
export function createGraphView(deps) {
  const { doc, layer, cardsStage, strings, index, createGraph, checkOptions, checkedOptions, say, hush, failure, current, signal } = deps;
  const toolbar = layer.querySelector(".toolbar");
  if (!toolbar) throw new Error("the shell lacks its toolbar");
  const stage = el("div", { class: "stage graph-spine", hidden: "" });
  stage.hidden = true;
  layer.insertBefore(stage, cardsStage.nextSibling);
  const bCards = el("button", { type: "button", class: "view-btn", "data-id": "cards", "aria-pressed": "true" }, [strings.view_cards]);
  const bGraph = el("button", { type: "button", class: "view-btn", "data-id": "graph", "aria-pressed": "false" }, [strings.view_graph]);
  const sw = el("span", { class: "seg view-switch" }, [bCards, bGraph]);
  toolbar.insertBefore(sw, toolbar.firstChild);
  bCards.addEventListener("click", () => deps.onSwitch("cards"), { signal });
  bGraph.addEventListener("click", () => deps.onSwitch("graph"), { signal });

  let view = "cards", spine = null, handle = null, refused = false, keyEl = null;
  const offs = [];     // the unsubscribe function of every engine subscription (the page's one teardown rule)
  function release() {
    for (const off of offs.splice(0)) { try { off(); } catch (e) { /* the stage is being put back */ } }
    if (handle) { try { handle.destroy(); } catch (e) { /* the same */ } handle = null; }
  }

  function pressed() {
    bCards.setAttribute("aria-pressed", view === "cards" ? "true" : "false");
    bGraph.setAttribute("aria-pressed", view === "graph" ? "true" : "false");
  }
  function report(code) {
    try {
      doc.dispatchEvent(new doc.defaultView.CustomEvent(FAILURE_EVENT, { detail: { stage: "graph", code }, bubbles: false, cancelable: false, composed: false }));
    } catch (e) { /* the event is for a test's listener; nothing here depends on it */ }
  }
  function flipTo(which) {
    stage.hidden = which !== "graph";
    cardsStage.hidden = which === "graph";
  }
  function rollback() {
    flipTo("cards");
    release();
  }

  /* Draw the spine, once. Throws on any refusal; the caller has put the page back by then. */
  async function draw() {
    flipTo("graph");     // the engine needs a stage with a size
    const options = {
      roots: spineRoots(spine), maxChildren: index.maxChildren, sizes: { ...SPINE_SIZES }, zoom: { ...SPINE_ZOOM },
      loadChildren: () => Promise.resolve([]), renderFace: renderSpineFace,
    };
    checkedOptions(checkOptions, options, undefined);
    handle = deps.createGraph(stage, options);
    offs.push(handle.on("tap", (node) => deps.onTap(node)));
    if (!(await handle.ready)) throw new DataError("engine-refused", "the engine refused the spine's roots");
    await new Promise((r) => doc.defaultView.requestAnimationFrame(() => r()));
  }

  /* THE SWITCH TO GRAPH, a route body (the page gives it its navigation ticket `t`). true when the Graph view is showing on return. */
  async function show(t) {
    if (view === "graph") return true;
    try {
      if (!spine) {
        const raw = await fetchJson(deps.fetch, "spine.json");
        if (!current(t)) return false;
        spine = validateSpine(raw, index);
      }
      if (!handle) await draw();
      else { flipTo("graph"); handle.fit(); }
      if (!current(t)) { flipTo(view); return false; }
    } catch (e) {
      rollback();
      if (!current(t)) return false;
      say(strings.graph_failed_notice);
      failure.graph = String(e && e.message ? e.message : "graph failed");
      refused = true;
      report(failureCode(e));
      return false;
    }
    view = "graph";
    pressed();
    hush();
    failure.graph = null;
    if (refused) { refused = false; report(null); }
    return true;
  }
  function hide() {
    view = "cards";
    flipTo("cards");
    pressed();
  }
  function destroy() {
    release();
    if (stage.parentNode) stage.parentNode.removeChild(stage);
    if (sw.parentNode) sw.parentNode.removeChild(sw);
  }
  return {
    show, hide, destroy,
    view: () => view,
    select: (id) => { if (handle) handle.select(id); },
    /* The Graph view's key, made once the spine is known (the toolbar's Key button is the page's; it asks the view that is showing). */
    key: (headingKey) => {
      if (!spine) return null;
      if (!keyEl) keyEl = buildGraphKey(strings, headingKey, strings[spine.words]);
      return keyEl;
    },
    node: (id) => (spine ? spine.nodes.find((n) => n.id === id) || null : null),
  };
}
