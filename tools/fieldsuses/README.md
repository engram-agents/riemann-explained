# fields/uses: which hypotheses and fields a Lean proof term uses

A small Lean 4 program that reads the **elaborated proof terms** of a compiled release and answers, for one declaration:

- **`uses DECL`**: for each binder (hypothesis or argument) of `DECL`, one or more labels:
  - `unused`: the binder does not occur in the body.
  - `direct`: the body projects it (`h.2`, `h.right`), takes it apart (`obtain ⟨a, b⟩ := h`, `match`), or applies it as a function. The report gives the read path, positionally (`.2.2`) and by field name (`.right.right`).
  - `passed_whole`: it is an explicit argument to another constant. The report names the callee and the argument position. With `--follow N`, the tool reads what the callee does with that argument, up to depth N, and says where it stopped.
  - `instance_only`: it fills only instance-implicit slots (found by instance search). Source text never shows these uses.
  - `returned`: it is the body itself, or a field of the structure the body builds.
  - `in_types_only`: it occurs only inside types: binder types, implicit arguments, eliminator motives. It is shown only when no other label applies.
- **`flows_into`** (in the same report): which fields of the structure a declaration builds contain the binder.
- **`who_reads S.field`**: every loaded declaration whose term reads that field, through `Expr.proj`, the projection function, or `casesOn` with the field's variable used.

Two facts the notes keep separate: **"Lean's proof term uses h"**, which this tool reports, and **"the source names h"**, which is text. Tactics can make them differ in either direction.

Auxiliary declarations made by elaboration (`DECL._proof_N`, `match_N` matchers, `_simp_N`) are followed and named under `followed`, never reported as callees. Local renamings (`have h2 := h; exact h2.2`) are read through.

## Running it

It needs a prebuilt tree: the release compiled with its toolchain, plus Mathlib's prebuilt `.lake` build. It never calls `lake`, and it writes nothing into that tree.

```
LEAN_PATH=<release build>:<mathlib .lake/build/lib/lean>:<each package's .lake/build/lib/lean> \
PATH=<toolchain>/bin:$PATH \
lean --run FieldsUses.lean -- --module Some.Module [--follow N] uses Full.Decl.Name [More.Decls ...]
```

The output is JSON. It starts with a scope header: the Lean version, the modules requested, the module count loaded, the query and the options.

Errors are loud:
- exit 3: a requested module has no `.olean` (not compiled yet);
- exit 2: the declaration is not in the loaded environment;
- `no_body`: the declaration is an axiom, opaque, or similar;
- `not_followed`: a `--follow` stopped (depth, not loaded, no body).

## Tests: controls first, then a mutation check

`controls/Controls.lean` holds ten pairs of small theorems (C1-C10), Mathlib only. Each pair differs in one way. `controls/expected.json` gives the labels the tool must report for each. Both were written before the classifier. **A control counts only after its pair has been printed as elaborated terms and seen to differ in the way its row says.** Three first drafts failed that check (C2, C8, C10) and were rewritten before any classifier code existed.

```
python3 run_controls.py --root <prebuilt tree>                    # 20 cases
python3 run_controls.py --root <prebuilt tree> --mutation-check   # three planted bugs
```

The mutation check plants three bugs, one at a time, with `--mutate`, and requires each to fail exactly the cases named in `expected.json`:
1. instance slots treated as explicit: fails only C2a;
2. projections read without their index: fails every case that reads a path, and only those, with C3a and C3b together. This shows that destructuring and projection are read by the same rule;
3. no reading through local renamings: fails only C9a.

**What passing does not mean.** The classifier was written against these controls, so 20/20 shows agreement with them, not correctness on release terms. The planted bugs show the controls can fail; they do not show that every plausible wrong implementation fails. Release cases (in the spec) are the first test the code was not written against.

## Known limits of v1

- Destructuring is read through `casesOn` only, not through `.rec`.
- An occurrence in an implicit argument slot counts as "in types".
- Extra arguments that a dependent eliminator receives after its minor premises are read as `passed_whole` to that eliminator.
- Type binders passed explicitly to type formers (`TensorProduct.tmul K …`) get `passed_whole`. This is correct by the rules above, but it is noise.
- Terms carry no source positions. The report gives term paths, not line numbers.
