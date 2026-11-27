/* The header fold (Lei's phone requirement, 2026-11-26): on a phone the Lean map's header is compact, and it folds into one bar as soon as the reader works in the
   graph, so the map has the window. It exists only where the shell carries the bar (#graph-intro-bar, after header.intro): the live map's shell has none, and then
   createFold returns null and the page does not change. Nothing here reads data, builds an element or sets text: it hides and shows the two elements the shell holds.

   THE STATES: open (the header, compact by the CSS on a phone), folded (the bar; the header hidden) and FULL (the header opened again by the bar's button: all of it,
   the scope line too, at most 60 percent of the window and scrollable; the CSS knows it by data-full). It never opens by itself, except that a window made wider than
   a phone puts everything back, and a window shorter than 520 px starts folded.

   WHEN IT FOLDS. The layout moves when it folds (the toolbar and the stage go up by the header's height), and a tap is a pointerdown and a pointerup on the SAME
   place: folding at the pointerdown would move the box or the button from under the finger and the tap would open a neighbour or nothing. So: a wheel and a key fold at
   once (no tap is under way); a pan folds when the pointer has moved by PAN_PX with a button down (the engine pans by deltas, so the map follows); a tap or a press
   (anything that ends in a click inside the layer) folds right AFTER its click has been handled (a timeout of 0 set in the capture phase runs after the target's own
   handlers). The engine has no resize handling, so a press on Show all or on the view switch that caused the fold has `afterFold(target)` called, and the page frames
   the whole map again on the larger stage. */
const PAN_PX = 10;
export function createFold({ doc, layer, signal, afterFold }) {
  const header = doc.querySelector("header.intro"), bar = doc.getElementById("graph-intro-bar"), show = doc.getElementById("graph-intro-show");
  if (!header || !bar || !show) return null;
  const win = doc.defaultView;
  const phone = win.matchMedia("(max-width: 600px), (max-height: 519px)");
  const short = win.matchMedia("(max-height: 519px)");
  let folded = false, disposed = false;

  function set(f) {
    folded = f;
    header.hidden = f;
    bar.hidden = !f;
    header.removeAttribute("data-full");
  }
  function fold(target) {
    if (disposed || folded || !phone.matches) return;
    set(true);
    if (target && afterFold) afterFold(target);
  }
  function reopen() {
    set(false);
    header.setAttribute("data-full", "");
    const first = header.querySelector("button");
    if (first) first.focus();
  }
  function putBack() { if (folded || header.hasAttribute("data-full") || header.hidden) set(false); }

  if (short.matches) set(true);
  show.addEventListener("click", reopen, { signal });
  let down = null;
  layer.addEventListener("wheel", () => fold(null), { capture: true, passive: true, signal });
  layer.addEventListener("keydown", () => fold(null), { capture: true, signal });
  layer.addEventListener("pointerdown", (e) => { down = { x: e.clientX, y: e.clientY }; }, { capture: true, signal });
  layer.addEventListener("pointermove", (e) => { if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) > PAN_PX) { down = null; fold(null); } }, { capture: true, signal });
  layer.addEventListener("pointerup", () => { down = null; }, { capture: true, signal });
  layer.addEventListener("pointercancel", () => { down = null; }, { capture: true, signal });
  layer.addEventListener("click", (e) => { const t = e.target; win.setTimeout(() => fold(t), 0); }, { capture: true, signal });
  /* A SHEET OPEN FOLDS THE HEADER (Kepler 39429): a reader who arrives by a link to a step (the address carries #id on load, or the hash changes) has touched nothing in the
     layer, yet is reading the note, not the introduction. So whenever the sheet is shown on a phone the header folds, and closing the sheet leaves it folded. */
  const sheet = doc.getElementById("graph-sheet");
  let watch = null;
  if (sheet && win.MutationObserver) {
    watch = new win.MutationObserver(() => { if (!sheet.hidden) fold(null); });
    watch.observe(sheet, { attributes: true, attributeFilter: ["hidden"] });
    if (!sheet.hidden) fold(null);
  }
  phone.addEventListener("change", () => { if (!phone.matches) putBack(); }, { signal });
  /* THE ABOUT PANEL (contract (c): what the header does not show on a phone is also in About). On a phone the panel gets COPIES of the header's own sentence and
     scope line, put first and marked data-fold-copy; they are taken out again whenever the panel is opened on a window that is not a phone. The nodes are the shell's
     own, cloned: no text is written here. */
  function syncAbout(aboutEl) {
    if (!aboutEl) return;
    for (const old of [...aboutEl.querySelectorAll("[data-fold-copy]")]) old.remove();
    if (!phone.matches) return;
    const copies = ["p.sentence", "p.front-line"].map((q) => header.querySelector(q)).filter(Boolean).map((n) => {
      const c = n.cloneNode(true);
      c.removeAttribute("class");
      c.setAttribute("data-fold-copy", "");
      return c;
    });
    for (const c of copies.reverse()) aboutEl.insertBefore(c, aboutEl.firstChild);
  }
  return { dispose: () => { disposed = true; if (watch) watch.disconnect(); putBack(); }, folded: () => folded, syncAbout };
}
