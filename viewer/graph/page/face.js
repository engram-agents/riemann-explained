/* The face of a closed card: the role word (only when the builder gave one), at most three lines of the title as TEXT (a backtick span as <code>, dom.js titleChildren),
   and the foot '{n} parts' when the step has children. The title is the contract's `title` field and nothing else:
   the builder already resolved which line it is. Colour and frame come from the enumerated kind and state tables. */
import { el, titleChildren } from "./dom.js";
import { KIND_CLASS, STATE_CLASS } from "./data.js";

const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

/* '{n}' is substituted as text, by a function so no replacement pattern in the number could matter. */
export function partsText(strings, n) {
  if (!Number.isFinite(n) || n < 0) throw new TypeError("childCount is not a count");
  return n === 1 ? strings.part_one : strings.parts_n.replace("{n}", () => String(n));
}

/* makeRenderFace(strings) -> renderFace(nodeSpec) -> Element, the engine's one-argument face function. */
export function makeRenderFace(strings) {
  return function renderFace(spec) {
    const d = spec && spec.data;
    if (!d || !own(KIND_CLASS, d.kind) || !own(STATE_CLASS, d.state) || typeof d.title !== "string")
      throw new TypeError("a card without a drawable kind, state and title");
    const kids = [];
    if (typeof d.role === "string" && d.role !== "") kids.push(el("span", { class: "face-role" }, [d.role]));
    kids.push(el("div", { class: "face-title" }, titleChildren(d.title)));
    if (spec.childCount > 0) kids.push(el("div", { class: "face-foot" }, [partsText(strings, spec.childCount)]));
    return el("div", { class: "face " + KIND_CLASS[d.kind] + " " + STATE_CLASS[d.state] }, kids);
  };
}
