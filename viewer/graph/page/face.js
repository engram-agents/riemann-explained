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

/* The foot of a card with children. When the card names the kind of its children (data.childKind) and that kind's table row has
   count_words, the foot is that row's one word for a count of 1 and its many word otherwise, with '{n}' filled as TEXT (a function
   replacement, so no pattern in the words matters). Every other card keeps parts_n / part_one exactly. No kind is named here: the
   table row decides. countWords is index.symbols.countWords (kind -> {one, many}). */
export function footText(strings, countWords, childKind, n) {
  if (typeof childKind === "string" && own(countWords, childKind)) {
    const w = countWords[childKind];
    return strings[n === 1 ? w.one : w.many].replace("{n}", () => String(n));
  }
  return partsText(strings, n);
}

/* makeRenderFace(strings, countWords) -> renderFace(nodeSpec) -> Element, the engine's one-argument face function. */
export function makeRenderFace(strings, countWords = {}) {
  return function renderFace(spec) {
    const d = spec && spec.data;
    if (!d || !own(KIND_CLASS, d.kind) || !own(STATE_CLASS, d.state) || typeof d.title !== "string")
      throw new TypeError("a card without a drawable kind, state and title");
    const kids = [];
    if (typeof d.role === "string" && d.role !== "") kids.push(el("span", { class: "face-role" }, [d.role]));
    kids.push(el("div", { class: "face-title" }, titleChildren(d.title)));
    if (spec.childCount > 0) kids.push(el("div", { class: "face-foot" }, [footText(strings, countWords, d.childKind, spec.childCount)]));
    return el("div", { class: "face " + KIND_CLASS[d.kind] + " " + STATE_CLASS[d.state] }, kids);
  };
}
