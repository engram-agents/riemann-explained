/* The file neighbourhood (G2): one file's closed card in the middle, ABOVE it the files that use it ("Built on it (m)", uses.json used_by), BELOW it the files it
   uses ("It uses (n)", uses.json uses), as lists of ROWS, no lines drawn. Nothing here loads data: graphview.js hands it the validated record (uses.js) and the
   centre's face, and it returns a root element. Every element is built by dom.js el(); titles go in through titleChildren, numbers and words as text nodes.

   A side's rows are HEAVIEST BY NAMES FIRST (names, then title, then id), as many as fit the stage at scale 1 and at least MIN_ROWS; when more exist the last row is
   `nb_more` ("+ n more"), which asks for the whole side as a list in the sheet. A tap on a row asks to make that file the centre; the line at the top goes back
   (`nb_back` with the title of the file the reader came from, or `nb_back_spine` when the reader came from the main results). */
import { el, titleChildren } from "./dom.js";

/* Sizes in px, matched by the CSS (.nb-row min-height, the gaps and the headings). */
export const NB_SIZES = Object.freeze({ rowH: 48, gap: 4, headH: 30, backH: 44, centreH: 120, padY: 12 });
export const MIN_ROWS = 2;

/* Heaviest first: more names first, then the title (plain code-unit order, so the result does not depend on a locale), then the id. `titles` is a Map of id to {title}. */
export function orderRows(rows, titles) {
  const t = (id) => { const r = titles.get(id); return r ? r.title : id; };
  return rows.slice().sort((a, b) => (b.names - a.names) || (t(a.id) < t(b.id) ? -1 : t(a.id) > t(b.id) ? 1 : 0) || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));
}

/* How many rows a side shows: what fits the stage's height beside the centre, the two headings and the back line, but at least MIN_ROWS. A side that has more rows
   than that gives its last place to the `nb_more` row, so the shown rows plus that one fit. */
export function rowsPerSide(stageH, total, sizes = NB_SIZES) {
  const room = stageH - sizes.backH - sizes.centreH - 2 * sizes.headH - sizes.padY;
  const fit = Math.max(MIN_ROWS, Math.floor(room / 2 / (sizes.rowH + sizes.gap)));
  return total <= fit ? total : Math.max(MIN_ROWS, fit - 1);
}

const fill = (template, key, value) => String(template).split("{" + key + "}").join(String(value));

/* One row: the kind word, the title (two lines at most by the CSS, the whole title in the bytes) and the number of names. */
function rowOf(strings, kindWord, row, titles, onMove, signal) {
  const names = row.names === 1 ? strings.nb_names_one : fill(strings.nb_names_many, "n", row.names);
  const info = titles.get(row.id);
  const b = el("button", { type: "button", class: "nb-row", "data-id": row.id }, [
    el("span", { class: "nb-kind" }, [kindWord(info ? info.kind : "")]),
    el("span", { class: "nb-title" }, titleChildren(info ? info.title : row.id)),
    el("span", { class: "nb-names" }, [names]),
  ]);
  b.addEventListener("click", () => onMove(row.id), { signal });
  return b;
}

/* buildSide(...) is one side: its heading (with the side's total), then its rows, then the more row; an empty side says so in its own word. */
function sideOf(strings, cls, headKey, emptyKey, rows, titles, shown, kindWord, onMove, onMore, signal) {
  const kids = [el("h2", { class: "nb-heading" }, [fill(strings[headKey], "n", rows.length)])];
  if (rows.length === 0) kids.push(el("p", { class: "nb-empty" }, [strings[emptyKey]]));
  for (const r of rows.slice(0, shown)) kids.push(rowOf(strings, kindWord, r, titles, onMove, signal));
  if (rows.length > shown) {
    const more = el("button", { type: "button", class: "nb-row nb-more" }, [fill(strings.nb_more, "n", rows.length - shown)]);
    more.addEventListener("click", () => onMore(), { signal });
    kids.push(more);
  }
  return el("section", { class: "nb-side " + cls }, kids);
}

/* buildNeighbourhood(deps) returns {root, shown: {above, below}}. deps:
   strings, titles (Map), kindWord(kind) -> text, record = {id, builtOn: rows, uses: rows} (rows as validateUses gives them), stageH,
   centre (the closed card's face element, made by the page's own renderFace), back = {title} or null (null: back to the main results),
   onMove(id), onMore(side), onCentre(), onBack(); signal for the listeners. */
export function buildNeighbourhood(deps) {
  const { strings, titles, kindWord, record, stageH, centre, back, onMove, onMore, onCentre, onBack, signal } = deps;
  const builtOn = orderRows(record.builtOn, titles), uses = orderRows(record.uses, titles);
  const above = rowsPerSide(stageH, builtOn.length), below = rowsPerSide(stageH, uses.length);
  const backText = back ? fill(strings.nb_back, "title", back.title) : strings.nb_back_spine;
  const backBtn = el("button", { type: "button", class: "nb-back" }, [backText]);
  backBtn.addEventListener("click", () => onBack(), { signal });
  const centreBtn = el("button", { type: "button", class: "nb-centre", "data-id": record.id }, [centre]);
  centreBtn.addEventListener("click", () => onCentre(), { signal });
  const side = (cls, head, empty, rows, shown, which) => sideOf(strings, cls, head, empty, rows, titles, shown, kindWord, onMove, () => onMore(which), signal);
  const root = el("div", { class: "nb-root" }, [
    backBtn,
    side("nb-above", "nb_built_on", "nb_empty_built_on", builtOn, above, "built_on"),
    el("div", { class: "nb-centre-wrap" }, [centreBtn]),
    side("nb-below", "nb_uses", "nb_empty_uses", uses, below, "uses"),
  ]);
  return { root, shown: { above: Math.min(above, builtOn.length), below: Math.min(below, uses.length) } };
}
