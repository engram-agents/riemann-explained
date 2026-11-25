// Pointer, touch, wheel and key input on the stage. Calls the controller (pan, zoom, tap) and nothing else.
// Tap: ONE pointer, moved at most tapSlopPx, released within tapMs. A drag never taps; a pinch never taps.
// The stage has touch-action: none (set in view.js), so the browser leaves the gestures to this file.

export function attachInput(view, ctl, o) {
  const I = o.input, stage = view.stage;
  const pts = new Map();            // pointerId -> last {x, y}
  let press = null;                 // the candidate tap: {id, x0, y0, t0, target, moved}
  let drag = null;                  // a pan in progress: {id, lx, ly}
  let pinch = null;                 // {d, mx, my}
  let multi = false;                // a second pointer joined this gesture: no tap from it

  const local = (e) => { const r = stage.getBoundingClientRect(); return { x: e.clientX - r.left, y: e.clientY - r.top }; };
  const two = () => { const [a, b] = [...pts.values()]; return { d: Math.hypot(a.x - b.x, a.y - b.y), mx: (a.x + b.x) / 2, my: (a.y + b.y) / 2 }; };
  const nodeIdOf = (t) => view.nodeIdOf(t);          // through the view's own element -> node map; never an attribute

  view.listen(stage, "pointerdown", (e) => {
    if (e.pointerType === "mouse" && e.button !== 0) return;
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pts.size === 1) {
      multi = false; drag = null;
      press = { id: e.pointerId, x0: e.clientX, y0: e.clientY, t0: e.timeStamp, target: e.target, moved: false };
    } else if (pts.size === 2) {
      multi = true; press = null; drag = null; pinch = two();
    }
  });

  view.listen(stage, "pointermove", (e) => {
    if (!pts.has(e.pointerId)) return;
    pts.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pts.size === 2 && pinch) {
      const now = two(), r = stage.getBoundingClientRect();
      ctl.panBy(now.mx - pinch.mx, now.my - pinch.my);
      if (pinch.d > 0 && now.d > 0) ctl.zoomAt(now.mx - r.left, now.my - r.top, now.d / pinch.d, true);
      pinch = now;
    } else if (pts.size === 1 && press && press.id === e.pointerId) {
      if (!press.moved && Math.hypot(e.clientX - press.x0, e.clientY - press.y0) > I.tapSlopPx) {
        press.moved = true;
        drag = { id: e.pointerId, lx: press.x0, ly: press.y0 };
        try { stage.setPointerCapture(e.pointerId); } catch (err) { /* capture is optional */ }
        view.setPanning(true);
      }
      if (drag) { ctl.panBy(e.clientX - drag.lx, e.clientY - drag.ly); drag.lx = e.clientX; drag.ly = e.clientY; }
    } else if (pts.size === 1 && drag && drag.id === e.pointerId) {
      ctl.panBy(e.clientX - drag.lx, e.clientY - drag.ly); drag.lx = e.clientX; drag.ly = e.clientY;
    }
  });

  function end(e, cancelled) {
    if (!pts.has(e.pointerId)) return;
    const was = press;
    pts.delete(e.pointerId);
    if (!cancelled && !multi && was && was.id === e.pointerId && !was.moved && pts.size === 0
        && Math.hypot(e.clientX - was.x0, e.clientY - was.y0) <= I.tapSlopPx && e.timeStamp - was.t0 <= I.tapMs) {
      ctl.tap(nodeIdOf(was.target), { target: was.target, clientX: e.clientX, clientY: e.clientY, pointerType: e.pointerType });
    }
    if (pts.size === 0) { press = null; drag = null; pinch = null; multi = false; view.setPanning(false); }
    else if (pts.size === 1) {
      const [id, p] = [...pts.entries()][0];
      press = null; pinch = null; drag = { id, lx: p.x, ly: p.y };       // one finger left after a pinch: it pans on
    }
  }
  view.listen(stage, "pointerup", (e) => end(e, false));
  view.listen(stage, "pointercancel", (e) => end(e, true));

  view.listen(stage, "wheel", (e) => {
    e.preventDefault();
    const p = local(e), unit = e.deltaMode === 1 ? 16 : 1;
    ctl.zoomAt(p.x, p.y, Math.exp(-e.deltaY * unit * (e.ctrlKey ? I.wheelCtrlStep : I.wheelStep)), true);
  }, { passive: false });

  view.listen(stage, "keydown", (e) => {
    // keys act only on what the engine made: the stage or one of its node elements. A key pressed in a caller's face
    // (a button, a text field) is the face's own and is left alone.
    if (e.target !== stage && !view.isNodeEl(e.target)) return;
    const id = view.isNodeEl(e.target) ? nodeIdOf(e.target) : null;
    if (id && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); ctl.tap(id, { target: e.target, key: e.key }); return; }
    const v = view.viewport(), cx = v.w / 2, cy = v.h / 2;
    if (e.key === "+" || e.key === "=") ctl.zoomAt(cx, cy, I.keyZoom, true);
    else if (e.key === "-" || e.key === "_") ctl.zoomAt(cx, cy, 1 / I.keyZoom, true);
    else if (e.key === "0") ctl.fit();
    else if (e.key.indexOf("Arrow") === 0) {
      e.preventDefault();
      ctl.panBy(e.key === "ArrowLeft" ? I.keyPanPx : e.key === "ArrowRight" ? -I.keyPanPx : 0, e.key === "ArrowUp" ? I.keyPanPx : e.key === "ArrowDown" ? -I.keyPanPx : 0);
    }
  });
}
