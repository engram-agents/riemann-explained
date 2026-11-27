/* The Graph view's words in index.json `strings`: the page reads them only when the map carries BOTH view_cards and view_graph (one alone is refused by name),
   then requires the other words the view reads, and takes exactly ONE more key, the spine's sentence, whose name the page does not hard-wire: spine.json's own
   edge_basis names it, and validateSpine checks it is that key. Without the two view words nothing of the view is read and any extra key is refused as before.
   Written before the implementation. */
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { DataError, validateIndex, GRAPH_VIEW_STRINGS, NEIGHBOURHOOD_STRINGS } from "../data.js";
import { validateSpine } from "../spine.js";

const FIX = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures");
const skIndex = () => JSON.parse(readFileSync(path.join(FIX, "skeleton", "index.json"), "utf8"));
const clone = (o) => JSON.parse(JSON.stringify(o));
const WORDS = {
  view_cards: "Cards", view_graph: "Graph", graph_nodes_text: "made-up what a box is", spine_content_label: "made-up label",
  spine_lives_in: "made-up lives in {title}", spine_show_file: "made-up show file", graph_failed_notice: "made-up notice",
};
const SPINE_SENTENCE = "made-up spine lines sentence";
const withView = (fn) => { const i = skIndex(); Object.assign(i.strings, WORDS, { spine_made_up_sentence: SPINE_SENTENCE }); if (fn) fn(i); return i; };
const refuses = (fn, code, mention) => assert.throws(fn, (e) => {
  assert.ok(e instanceof DataError, "not a DataError: " + e);
  assert.equal(e.code, code, e.message);
  if (mention !== undefined) assert.ok(e.reason.includes(mention), "the reason " + JSON.stringify(e.reason) + " does not name " + mention);
  return true;
});

test("V1 the closed list of the view's words is exactly the seven the page reads by name", () => {
  assert.deepEqual([...GRAPH_VIEW_STRINGS].sort(), Object.keys(WORDS).sort());
});

test("V2 both view words and the other six, plus exactly one more key: validates; the record names that key as the spine's words", () => {
  const r = validateIndex(withView());
  assert.deepEqual(r.graphView, { spineWords: "spine_made_up_sentence", neighbourhood: false });
  for (const k of Object.keys(WORDS)) assert.equal(r.strings[k], WORDS[k]);
});

test("V3 without the two view words there is no graphView in the record, and none of the view's words is read", () => {
  assert.equal(validateIndex(skIndex()).graphView, undefined);
  for (const k of Object.keys(WORDS).filter((x) => !x.startsWith("view_"))) {
    const i = skIndex(); i.strings[k] = "x";
    refuses(() => validateIndex(i), "extra-string", k);
  }
  const i = skIndex(); i.strings.spine_made_up_sentence = "x";
  refuses(() => validateIndex(i), "extra-string", "spine_made_up_sentence");
});

test("V4 one view word without the other is refused by name", () => {
  for (const [keep, drop] of [["view_cards", "view_graph"], ["view_graph", "view_cards"]]) {
    refuses(() => validateIndex(withView((i) => { delete i.strings[drop]; })), "bad-view-words", drop);
    void keep;
  }
});

test("V5 with both view words, each of the other six is required and not empty", () => {
  for (const k of Object.keys(WORDS)) {
    refuses(() => validateIndex(withView((i) => { delete i.strings[k]; })), k.startsWith("view_") ? "bad-view-words" : "missing-string", k);
    refuses(() => validateIndex(withView((i) => { i.strings[k] = ""; })), k.startsWith("view_") ? "bad-view-words" : "empty-string", k);
  }
});

test("V6 with both view words the spine's sentence key is required: none, or two, is refused", () => {
  refuses(() => validateIndex(withView((i) => { delete i.strings.spine_made_up_sentence; })), "bad-view-words", "spine");
  refuses(() => validateIndex(withView((i) => { i.strings.another_extra = "x"; })), "extra-string", "another_extra");
  refuses(() => validateIndex(withView((i) => { i.strings.spine_made_up_sentence = ""; })), "empty-string", "spine_made_up_sentence");
});

test("V7 the spine must name the key the index carries: any other key of the strings is refused by validateSpine", () => {
  const idx = validateIndex(withView((i) => { i.strings.key_lines_heading = "h"; i.strings.key_lines_text = "t"; i.edge_basis = { basis: "names-written-in-source-from-compiled-index", words: "key_lines_text" }; }));
  const COMMIT = idx.commit;
  const spine = (words) => ({ commit: COMMIT, edge_basis: { basis: "reaches-through-any-chain-of-uses", words }, format: 1, links: [],
    nodes: [{ constants: [], content: "c", counts: { mentions: 0, no_doc: 0, other_constants: 0 }, file: "f1", id: "spine-a", mentions: [], names: ["n"], source: "grh/INDEX.md", theorem: "t" }] });
  assert.equal(validateSpine(spine("spine_made_up_sentence"), idx).words, "spine_made_up_sentence");
  assert.throws(() => validateSpine(spine("view_cards"), idx), (e) => e instanceof DataError && e.code === "bad-edge-basis" && e.reason.includes("carries"));
});

/* ---- the file neighbourhood's words (G2): nine, all or none, only beside the view words ---- */
const NB = {
  nb_built_on: "made-up built on ({n})", nb_uses: "made-up uses ({n})", nb_names_one: "made-up 1 name", nb_names_many: "made-up {n} names", nb_more: "made-up + {n} more",
  nb_back: "made-up back to {title}", nb_back_spine: "made-up back to the main results", nb_empty_uses: "made-up uses none", nb_empty_built_on: "made-up used by none",
};
const withNb = (fn) => withView((i) => { Object.assign(i.strings, NB); if (fn) fn(i); });

test("V8 the closed list of the neighbourhood's words is exactly the nine the page reads by name", () => {
  assert.deepEqual([...NEIGHBOURHOOD_STRINGS].sort(), Object.keys(NB).sort());
});

test("V9 the view words and all nine neighbourhood words: validates; the record says the map has the neighbourhood and still names the spine's key", () => {
  const r = validateIndex(withNb());
  assert.deepEqual(r.graphView, { spineWords: "spine_made_up_sentence", neighbourhood: true });
  for (const k of Object.keys(NB)) assert.equal(r.strings[k], NB[k]);
});

test("V10 with any neighbourhood word, each of the nine is required and not empty; the spine's key is still the one key more", () => {
  for (const k of Object.keys(NB)) {
    refuses(() => validateIndex(withNb((i) => { delete i.strings[k]; })), "missing-string", k);
    refuses(() => validateIndex(withNb((i) => { i.strings[k] = ""; })), "empty-string", k);
  }
  refuses(() => validateIndex(withNb((i) => { delete i.strings.spine_made_up_sentence; })), "bad-view-words");
  refuses(() => validateIndex(withNb((i) => { i.strings.another_key = "x"; })), "extra-string");
});

test("V11 neighbourhood words without the two view words are refused by name, whatever else the map holds", () => {
  for (const k of Object.keys(NB)) {
    const i = skIndex();
    i.strings[k] = NB[k];
    refuses(() => validateIndex(i), "bad-view-words", "neighbourhood");
  }
  const j = skIndex();
  Object.assign(j.strings, NB);
  refuses(() => validateIndex(j), "bad-view-words");
});
