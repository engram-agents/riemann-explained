/* The juxtaposition list (ruling D): every SET formula span of fixtures/note-spans-classes.json (read only) in which a script's base word is
   preceded by another word and a space, like `3 s ^ 7`: the setting draws only the last word's script, and a reader should be able to see
   which spans read that way. Prints one span per line, then a count line. Run by hand: node maths_juxtaposition.mjs > <a file OUTSIDE the repo>.
   Test-only tool; it prints the real spans, so its output is never committed. */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { scriptParts, spanClass } from "../note.js";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SPANS = JSON.parse(readFileSync(path.join(HERE, "fixtures", "note-spans-classes.json"), "utf8")).spans;
const WORD = /[\p{L}\p{N}′'’]/u;

/* the span has a script whose base word (the run of word characters before it, spaces before a ^ skipped) follows a space that follows a word. */
function juxtaposed(span) {
  const cs = [...span];
  for (let k = 0; k < cs.length; k++) {
    if (cs[k] !== "^" && cs[k] !== "_") continue;
    let p = k - 1;
    if (cs[k] === "^") while (p >= 0 && cs[p] === " ") p--;
    let s = p;
    while (s >= 0 && WORD.test(cs[s])) s--;
    if (s >= 1 && cs[s] === " " && WORD.test(cs[s - 1]) && s < p) return true;
  }
  return false;
}

let n = 0;
for (const row of SPANS) {
  if (row.class !== "formula" || spanClass(row.span) !== "formula" || !/[\^_]/.test(row.span)) continue;
  if (scriptParts(row.span) === null || !juxtaposed(row.span)) continue;
  n++;
  console.log(row.span);
}
console.log("# %d set formula spans where a script's base word follows another word and a space", n);
