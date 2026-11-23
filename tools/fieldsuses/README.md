# fields/uses: which hypotheses and fields a Lean proof term uses

> **Read this before citing a verdict.** A report with `complete: false` supports **no** `unused` claim, and no `in_types_only` claim either: the walk stopped (term budget or depth limit), and a binder it did not reach is labelled `not_reached`. A note may cite an `unused` verdict only from a report with `complete: true`, and should say which tool version and options produced it.

A small Lean 4 program that reads the **elaborated proof terms** of a compiled release and answers, for one declaration:

- **`uses DECL`**: for each binder (hypothesis or argument) of `DECL`, one or more labels:
  - `unused`: the proof term makes no use of the binder. This includes `have h2 := h` when `h2` is never used: a renaming is read through, so an unused renaming is no use.
  - `direct`: the body projects it (`h.2`, `h.right`), takes it apart (`obtain ⟨a, b⟩ := h`, `match`), or applies it as a function. The report gives the read path, positionally (`.2.2`) and by field name (`.right.right`).
  - `passed_whole`: it is an explicit argument to another constant. The report names the callee and the argument position. With `--follow N`, the tool reads what the callee does with that argument, up to depth N, and says where it stopped.
  - `instance_only`: it fills only instance-implicit slots (found by instance search). Source text never shows these uses.
  - `returned`: it is the body itself, or a field of the structure the body builds.
  - `in_types_only`: it occurs only inside types (binder types, eliminator motives) or in implicit and strict-implicit argument slots. It is shown only when no other label applies. An implicit slot gets this label even when the callee's own proof uses that argument, so `in_types_only` does not mean "does not matter for the proof".
- **`flows_into`** (in the same report): which fields of the structure a declaration builds contain the binder.
- **`who_reads S.field`**: every declaration of the modules given with `--module` (widened with `--scan-prefix P`) whose term reads that field: through `Expr.proj`, the projection function, or `casesOn` (directly or inside a `match`) with the field's variable used. Generated declarations (matchers, `noConfusion`, internal helpers) are counted, not listed.

Two facts the notes keep separate: **"Lean's proof term uses h"**, which this tool reports, and **"the source names h"**, which is text. Tactics can make them differ in either direction.

Auxiliary declarations made by elaboration (`DECL._proof_N`, `match_N` matchers, `_simp_N`) are followed and named under `followed`, never reported as callees. Local renamings (`have h2 := h; exact h2.2`) are read through.

## Running it

It needs a prebuilt tree: the release compiled with its toolchain, plus Mathlib's prebuilt `.lake` build. It never calls `lake`, and it writes nothing into that tree.

```
LEAN_PATH=<release build>:<mathlib .lake/build/lib/lean>:<each package's .lake/build/lib/lean> \
PATH=<toolchain>/bin:$PATH \
lean --run FieldsUses.lean -- --module Some.Module [--follow N] uses Full.Decl.Name [More.Decls ...]
```

The output is JSON. It starts with a scope header: the Lean version, the modules requested, the module count loaded, the query and the options. Each `uses` report says `complete` and how many subterms it visited.

**Memory.** Run every `lean` inside a memory-capped scope, e.g. `systemd-run --user --scope -q -p MemoryMax=10G -p MemorySwapMax=0 nice -n 15 lean …`; `run_controls.py` does this for every call. `--budget N` (default 2,000,000) caps the subterms one `uses` query visits: past it the walk stops, the report says `complete: false` with a note, and no label is claimed for the unread part.

Errors are loud:
- exit 3: a requested module has no `.olean` (not compiled yet);
- exit 2: the declaration is not in the loaded environment;
- `no_body`: the declaration is an axiom, opaque, or similar;
- `complete: false`: the term budget was reached, and the labels cover only what was read; a binder the walk never reached is `not_reached`, never `unused`;
- `not_followed`: a `--follow` stopped (depth, not loaded, no body).

## Tests: controls first, then a mutation check

`controls/Controls.lean` holds small Mathlib-only theorems in pairs (C1-C21), and `controls/expected.json` gives what the tool must report for each (41 cases, including `who_reads`, a budget stop and the depth limit). C1-C10 were written before the classifier; C11-C19 were added after a reviewer's mutants survived the first set, each written before the code change it tests. **A control counts only after its pair has been printed as elaborated terms and seen to differ in the way its row says.** Three first drafts failed that check (C2, C8, C10) and were rewritten. The runner refuses to run if `Controls.lean` no longer matches the hash recorded in `expected.json`.

```
python3 run_controls.py --root <prebuilt tree>                    # 41 cases
python3 run_controls.py --root <prebuilt tree> --mutation-check   # four planted bugs
```

The mutation check plants four bugs, one at a time, with `--mutate`, and requires each to fail exactly the cases named in `expected.json`:
1. instance slots treated as explicit: fails only C2a;
2. projections read without their index: fails every case that reads a path, and only those, with C3a and C3b together;
3. no reading through local renamings (`have`, beta): fails only C9a and the beta cases C13a/C13f;
4. no reading of positional destructuring (`casesOn`, `match`): fails only C3a.
`expected.json` records which of these lists were written before a run and which were set from one.

**What passing does not mean.** The classifier was written against these controls, so 41/41 shows agreement with them, not correctness on release terms. The planted bugs show the controls can fail; they do not show that every plausible wrong implementation fails (a reviewer's 14 one-line mutants of the first version left 11 survivors; on the current controls 10 of the 13 that still apply are killed, and the three survivors are listed below; a second reviewer's 13 mutants of the who_reads and callee code left 9 survivors, also listed below). Declarations of the release, run when their modules are compiled, are the first test the code was not written against.

## Known limits of v1

- Destructuring is read through `casesOn` only, not through `.rec`.
- An occurrence in an implicit argument slot counts as "in types".
- Extra arguments that a dependent eliminator receives after its minor premises are read as `passed_whole` to that eliminator.
- Type binders passed explicitly to type formers (`TensorProduct.tmul K …`) get `passed_whole`. This is correct by the rules above, but it is noise.
- Terms carry no source positions. The report gives term paths, not line numbers.
- Paths through a type with several constructors (`Or`) do not name the constructor, so `inl` field 1 and `inr` field 1 print alike.
- `flows_into` sees a constructor only in result position; one inside an `if` branch or another non-constructor call is not seen, which under-reports.
- The walk inlines auxiliary declarations and reduces redexes with no sharing, so a large proof can exhaust the budget; this is why the budget exists.
- No control yet (deferred to the next version, which rewrites the traversal): the `who_reads` module scope and `--scan-prefix`, its list of skipped generated declarations, its single visit of head and arguments, and the filter that keeps pseudo-callees out of `passed`.
- `who_reads` misses a reader declared `partial def`: a reviewer's probe found it neither listed nor counted. The cause is not traced yet (likely the opaque constant plus an internal helper that is skipped), so treat `partial def` readers as unseen.
- `--follow` reads a callee by its printed name, so a private callee (`_private.…`) is reported "not loaded".
- A declaration whose value is eta-reduced (`theorem f : p → q := g`) has fewer leading binders than its type; the report lists only the value's binders and does not say so.
- Under `--follow`, the top-level `complete` covers the declaration's own walk only; each followed callee has its own `complete`, which can be false under a true top-level flag.
- Untested branches: an `Expr.proj` node and its field-name lookup. Source-written projections elaborate to projection-function applications, so no control here produces an `Expr.proj`; it appears in elaborated helpers.
- Callees named `<local function>`, `<lambda>` and `let y` stay in the occurrence list but are not reported under `passed` and are never followed.
