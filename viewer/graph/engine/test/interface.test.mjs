// INTERFACE.md's export list equals the module's actual exports (and its options and events lists equal the code's).
// The handle's method list is compared in the browser case, where a handle can be made.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import * as mod from "../index.js";

const md = readFileSync(new URL("../INTERFACE.md", import.meta.url), "utf8");
/* the names listed under "## <heading>": lines that start with "- `name`" */
function listed(heading) {
  const m = md.match(new RegExp("^## " + heading + "\\s*$([\\s\\S]*?)(?=^## |(?![\\s\\S]))", "m"));
  assert.ok(m, "INTERFACE.md has a section: " + heading);
  return [...m[1].matchAll(/^- `([A-Za-z0-9_]+)`/gm)].map((x) => x[1]);
}
const sorted = (a) => [...a].sort();

test("INTERFACE.md's export list equals the module's exports", () => {
  const doc = listed("Exports");
  assert.ok(doc.length >= 3, "the export list is not empty: " + doc);
  assert.deepEqual(sorted(Object.keys(mod)), sorted(doc));
});
test("every option and every event the code has is documented, and nothing else", () => {
  assert.deepEqual(sorted(Object.keys(mod.DEFAULTS)), sorted(listed("Options")));
  assert.deepEqual(sorted(mod.EVENTS), sorted(listed("Events")));
  assert.deepEqual(sorted(mod.EVENTS), sorted(["tap", "open", "close", "visible", "loading", "error", "refused"]));
});
test("the handle's documented methods are the contract's", () => {
  assert.deepEqual(sorted(listed("Handle")), sorted(["open", "close", "reveal", "fit", "select", "destroy", "on", "off", "ready"]));
});
test("a name that INTERFACE.md does not list is not exported (the check can fail)", () => {
  const withExtra = sorted([...Object.keys(mod), "helper"]);
  assert.notDeepEqual(withExtra, sorted(listed("Exports")));
});

/* the sub-keys an option group's table row names: the backticked names in the row's list, which ends at the first ". " */
function rowKeys(group) {
  const m = md.match(new RegExp("^\\| `" + group + "` \\| (.*) \\|$", "m"));
  assert.ok(m, "INTERFACE.md has a table row for " + group);
  const list = m[1].split(/\.\s/)[0];
  return [...list.matchAll(/`([A-Za-z0-9_]+)`/g)].map((x) => x[1]);
}
test("each option group's row names exactly the sub-keys DEFAULTS has (sizes, zoom, semantic, input, layout)", () => {
  for (const g of ["sizes", "zoom", "semantic", "input", "layout"]) {
    assert.deepEqual(sorted(new Set(rowKeys(g))), sorted(Object.keys(mod.DEFAULTS[g])), "row " + g);
  }
});
test("the sub-key check can fail: a row missing a key does not equal DEFAULTS", () => {
  const missing = rowKeys("zoom").filter((k) => k !== "fitMin");
  assert.notDeepEqual(sorted(missing), sorted(Object.keys(mod.DEFAULTS.zoom)));
});
