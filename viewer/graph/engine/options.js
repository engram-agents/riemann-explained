// The options and their defaults: data, not constants scattered through the code. Pure: no DOM.

const deepFreeze = (o) => { for (const v of Object.values(o)) if (v && typeof v === "object") deepFreeze(v); return Object.freeze(o); };

export const DEFAULTS = deepFreeze({
  roots: [],                       // the top-level NodeSpecs
  loadChildren: null,              // (nodeId) -> Promise<NodeSpec[]>; null = nothing ever has children
  renderFace: null,                // (nodeSpec) -> Element; null = an empty face
  sizes: {
    nodeW: 300, nodeH: 190,        // a closed node
    gapX: 44, gapY: 76,            // between siblings, across and between rows
    pad: 32,                       // inside an open node, around its children
    head: 160, top: 34,            // an open node's face height, and the space below it before the first row
    topInset: 0,                   // space reserved above the first row of the top level
    stroke: 2, arrow: 8, arrowGap: 10,   // link drawing: bar thickness, arrowhead size, gap before the target
  },
  zoom: {
    min: 0.06, max: 3,
    fitMax: 1.1, fitPad: 20,       // fit(): the largest scale, and the margin
    frameMaxOpen: 1.25, frameMaxClosed: 1.15, framePadOpen: 24, framePadClosed: 60,   // reveal / semantic-open framing
  },
  semantic: {
    openPx: 400, closePx: 220,     // open when a node is at least openPx wide on screen; close below closePx
    reArmShare: 0.8,               // a node the reader closed may open by zoom again once below this share of openPx
    frameOpenShare: 0.9, frameClosedShare: 0.85,   // framing keeps a closed node below this share of openPx
  },
  input: { tapSlopPx: 8, tapMs: 300, wheelStep: 0.0016, wheelCtrlStep: 0.01, keyZoom: 1.25, keyPanPx: 60 },
  maxChildren: 40,                 // the fan-out the layout is designed for; more is refused
  maxHeld: 16,                     // closed one-level subtrees kept in the LRU cache
  fitOnStart: true,
  onListenerError: null,           // (error, eventType) -> void; null = rethrow outside the engine's call
});

const GROUPS = ["sizes", "zoom", "semantic", "input"];
const fail = (m) => { throw new TypeError("graph options: " + m); };
const num = (g, k, v, min) => { if (!Number.isFinite(v) || v < min) fail(g + "." + k + " must be a finite number >= " + min); };

export function normalizeOptions(raw) {
  if (raw === undefined || raw === null) raw = {};
  if (typeof raw !== "object" || Array.isArray(raw)) fail("options must be an object");
  for (const k of Object.keys(raw)) if (!Object.hasOwn(DEFAULTS, k)) fail("unknown option " + k);
  const o = {};
  for (const k of Object.keys(DEFAULTS)) {
    if (GROUPS.includes(k)) {
      const r = raw[k] === undefined ? {} : raw[k];
      if (r === null || typeof r !== "object" || Array.isArray(r)) fail(k + " must be an object");
      for (const sub of Object.keys(r)) if (!Object.hasOwn(DEFAULTS[k], sub)) fail("unknown option " + k + "." + sub);
      o[k] = { ...DEFAULTS[k], ...r };
      for (const [sub, v] of Object.entries(o[k])) num(k, sub, v, 0);
    } else o[k] = raw[k] === undefined ? DEFAULTS[k] : raw[k];
  }
  if (!Array.isArray(o.roots)) fail("roots must be an array");
  if (o.loadChildren === null) o.loadChildren = () => Promise.resolve([]);
  if (typeof o.loadChildren !== "function") fail("loadChildren must be a function");
  if (o.renderFace !== null && typeof o.renderFace !== "function") fail("renderFace must be a function");
  if (o.onListenerError !== null && typeof o.onListenerError !== "function") fail("onListenerError must be a function");
  if (!Number.isInteger(o.maxChildren) || o.maxChildren < 1) fail("maxChildren must be an integer >= 1");
  if (!Number.isInteger(o.maxHeld) || o.maxHeld < 0) fail("maxHeld must be an integer >= 0");
  if (typeof o.fitOnStart !== "boolean") fail("fitOnStart must be a boolean");
  for (const k of ["nodeW", "nodeH", "head"]) if (!(o.sizes[k] > 0)) fail("sizes." + k + " must be > 0");
  if (!(o.zoom.min > 0 && o.zoom.max > o.zoom.min)) fail("zoom.min must be > 0 and below zoom.max");
  if (!(o.semantic.closePx > 0 && o.semantic.openPx > o.semantic.closePx)) fail("semantic.openPx must be above semantic.closePx (the gap is what stops flicker)");
  return o;
}
