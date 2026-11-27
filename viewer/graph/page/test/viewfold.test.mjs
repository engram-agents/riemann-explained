/* page/viewfold.js under plain node, with a hand-made stand-in for the document (no jsdom): the fold's timer after a click must not outlive dispose().
   Luria's finding on PR 122: a click in the same task as a synchronous failure into the fallback left a pending timer that folded the header again after
   dispose had put it back, and the bar's Show button was dead. Every element here is made-up. */
import test from "node:test";
import assert from "node:assert/strict";
import { createFold } from "../viewfold.js";

function stand(phone = true) {
  const timers = [];
  const listeners = {};
  const el = (extra = {}) => ({ hidden: false, attrs: {}, listeners: {}, addEventListener(t, f) { this.listeners[t] = f; }, removeAttribute(k) { delete this.attrs[k]; },
    setAttribute(k, v) { this.attrs[k] = v; }, hasAttribute(k) { return k in this.attrs; }, querySelector: () => null, querySelectorAll: () => [], focus() {}, ...extra });
  const header = el(), bar = el({ hidden: true }), show = el(), layer = el(), sheet = el({ hidden: true });
  const byId = { "graph-intro-bar": bar, "graph-intro-show": show, "graph-sheet": sheet };
  const win = {
    matchMedia: (q) => ({ matches: q === "(max-height: 519px)" ? false : phone, addEventListener() {} }),
    setTimeout: (f) => { timers.push(f); return timers.length; },
    MutationObserver: class { observe() {} disconnect() {} },
  };
  const doc = { defaultView: win, querySelector: (q) => (q === "header.intro" ? header : null), getElementById: (i) => byId[i] || null };
  return { doc, header, bar, show, layer, sheet, timers };
}
const click = (s, target = {}) => s.layer.listeners.click({ target });

test("W1 a click on a phone folds the header after the click, by a timer set in the capture phase", () => {
  const s = stand();
  const f = createFold({ doc: s.doc, layer: s.layer, signal: undefined });
  click(s);
  assert.equal(s.header.hidden, false, "folded before the timer ran");
  s.timers.forEach((t) => t());
  assert.equal(s.header.hidden, true);
  assert.equal(s.bar.hidden, false);
  assert.equal(f.folded(), true);
});

test("W2 a click, then dispose in the same task, then the timer: the header stays as dispose left it (open) and nothing folds", () => {
  const s = stand();
  const f = createFold({ doc: s.doc, layer: s.layer, signal: undefined });
  click(s);
  f.dispose();
  s.timers.forEach((t) => t());
  assert.equal(s.header.hidden, false, "the pending timer folded the header after dispose");
  assert.equal(s.bar.hidden, true);
  assert.equal(f.folded(), false);
});

test("W3 after dispose a wheel, a key and a pan fold nothing either", () => {
  const s = stand();
  const f = createFold({ doc: s.doc, layer: s.layer, signal: undefined });
  f.dispose();
  s.layer.listeners.wheel(); s.layer.listeners.keydown();
  s.layer.listeners.pointerdown({ clientX: 0, clientY: 0 }); s.layer.listeners.pointermove({ clientX: 50, clientY: 50 });
  assert.equal(s.header.hidden, false);
});

test("W4 on a window that is not a phone nothing folds, timer or not; with no bar in the shell there is no fold at all", () => {
  const s = stand(false);
  createFold({ doc: s.doc, layer: s.layer, signal: undefined });
  click(s); s.timers.forEach((t) => t());
  assert.equal(s.header.hidden, false);
  const live = stand();
  live.doc.getElementById = () => null;
  assert.equal(createFold({ doc: live.doc, layer: live.layer, signal: undefined }), null);
});
