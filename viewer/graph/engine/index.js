// The graph engine. Everything a caller may use is exported here and documented in INTERFACE.md; anything not
// in that file is private. The engine imports nothing outside this folder and knows nothing about any page.
import { createController } from "./controller.js";
import { createView } from "./view.js";
import { attachInput } from "./input.js";
import { normalizeOptions, DEFAULTS } from "./options.js";
import { EVENTS } from "./emitter.js";

export { DEFAULTS, EVENTS };
export const VERSION = "0.1.0";

export function createGraph(container, options) {
  if (!container || container.nodeType !== 1) throw new TypeError("createGraph needs a container element");
  const o = normalizeOptions(options);
  let ctl = null;
  const view = createView(container, o, { faceError: (n, reason) => ctl.faceError(n, reason) });
  ctl = createController(o, view);
  attachInput(view, ctl, o);
  return Object.freeze({
    open: ctl.open, close: ctl.close, reveal: ctl.reveal, fit: ctl.fit, select: ctl.select, destroy: ctl.destroy,
    on: ctl.on, off: ctl.off, ready: ctl.ready,
  });
}
