/* The face of a closed card: the role word (only when the builder gave one), at most three lines of the title as TEXT (a backtick span as <code>, dom.js titleChildren),
   and the foot '{n} parts' when the step has children. The title is the contract's `title` field and nothing else:
   the builder already resolved which line it is. Colour and frame come from the enumerated kind and state tables. */
import { el, titleChildren } from "./dom.js";
import { KIND_CLASS, STATE_CLASS, cueWordsOn } from "./data.js";

const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);

/* '{n}' is substituted as text, by a function so no replacement pattern in the number could matter. */
export function partsText(strings, n) {
  if (!Number.isFinite(n) || n < 0) throw new TypeError("childCount is not a count");
  return n === 1 ? strings.part_one : strings.parts_n.replace("{n}", () => String(n));
}

/* The foot of a card with children. PRECEDENCE: (1) the card names the kind of its children (data.childKind) and that kind's table row has count_words:
   that row's one word for a count of 1 and its many word otherwise; (2) else the card's OWN kind row has child_count_words (ownKind, and
   childCountWords = index.symbols.childCountWords): the same one/many rule; (3) else parts_n / part_one exactly. '{n}' is filled as TEXT (a function
   replacement, so no pattern in the words matters). No kind is named here: the table rows decide. countWords is index.symbols.countWords (kind -> {one, many}). */
export function footText(strings, countWords, childKind, n, ownKind, childCountWords = {}) {
  const words = (typeof childKind === "string" && own(countWords, childKind)) ? countWords[childKind]
    : (typeof ownKind === "string" && childCountWords && own(childCountWords, ownKind)) ? childCountWords[ownKind] : null;
  if (words) return strings[n === 1 ? words.one : words.many].replace("{n}", () => String(n));
  return partsText(strings, n);
}

/* The reading cue's text for a box (Ariadne's reading-cues note v1): a box with no children (a statement) says the tag word; a box above statements says the count, `1 AI reading`
   for one and the many word with '{n}' filled as TEXT otherwise. Only when the map holds the cue words and the card has a reading_count of 1 or more; otherwise null. */
export function cueText(strings, readingCount, childCount) {
  if (!cueWordsOn(strings) || !Number.isInteger(readingCount) || readingCount < 1) return null;
  if (!(childCount > 0)) return strings.face_reading_cue;
  return readingCount === 1 ? strings.count_reading_one : strings.count_reading_many.replace("{n}", () => String(readingCount));
}

/* makeRenderFace(strings, countWords, childCountWords) -> renderFace(nodeSpec) -> Element, the engine's one-argument face function. */
export function makeRenderFace(strings, countWords = {}, childCountWords = {}) {
  return function renderFace(spec) {
    const d = spec && spec.data;
    if (!d || !own(KIND_CLASS, d.kind) || !own(STATE_CLASS, d.state) || typeof d.title !== "string")
      throw new TypeError("a card without a drawable kind, state and title");
    const kids = [];
    if (typeof d.role === "string" && d.role !== "") kids.push(el("span", { class: "face-role" }, [d.role]));
    kids.push(el("div", { class: "face-title" }, titleChildren(d.title)));
    if (spec.childCount > 0) kids.push(el("div", { class: "face-foot" }, [footText(strings, countWords, d.childKind, spec.childCount, d.kind, childCountWords)]));
    const cue = cueText(strings, d.readingCount, spec.childCount);
    if (cue !== null) kids.push(el("div", { class: "face-reading" }, [cue]));
    return el("div", { class: "face " + KIND_CLASS[d.kind] + " " + STATE_CLASS[d.state] + (cue !== null ? " has-cue" : "") }, kids);
  };
}
