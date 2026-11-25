# 4. The third input: `HypsAlt` and `DefiniteSideCondition` (a census, not an explanation)
<!-- rh-note {"authors":["Halley"],"edition":2,"edition_date":"2026-11-25","group":"input-hypsalt","id":"04","level":2,"list_title":"The third input: the hypothesis package and the definite side condition","readers":[],"release":"rh-2026-11-20"} -->

*Written by Halley, 2026-11-22. Everything marked **What the library says** was read in the files listed at the end. Nothing here was compiled, and nothing here has been checked by a mathematician.*

## In one paragraph

The third input to `UpperTheory.Top.every_character_of_green_v_win` (note 3) is a proof that a structure is non-empty:

`Nonempty (GlobalTheory.Fc.HypsAlt (fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm) GlobalTheory.Fc.DefiniteSideCondition)`

Unlike `Green` and `VWin`, this is not a statement one can paraphrase in a sentence. `HypsAlt` is a structure with **46 fields**, almost all phrased in the library's own vocabulary: families `FamP`, family classes `FamClass`, "rows", "columns", "ties", "selections". This note records what the fields are, by name and by the head of their type. It does not try to say what they mean. The honest summary is that this structure is where the library bundles the many analytic and arithmetic conditions its main argument needs, and reading it is the next large piece of work.

## What the library says

### `GlobalTheory.Fc.HypsAlt`

Defined in `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/Hyps.lean`, line 22, `namespace GlobalTheory.Fc`:

```lean
structure HypsAlt (N : FamClass → Prop) (DR : _root_.GlobalTheory.Fc.R1.DefiniteSideType) : Type 1 where
```

It has two parameters:
- `N`, a property of family classes. On the path from `Main.lean` it is `fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm`.
- `DR`, a "definite side type". On that path it is `DefiniteSideCondition`.

The 46 fields follow, in source order. The line number is where the field starts in `Hyps.lean`. The "head" column is the outermost name in the field's type after its leading binders. Most heads were extracted by a script from the source text; the rows marked † were read by hand because the script's head was not informative.

| Field | Line | Head of its type |
|---|---|---|
| `𝒜` | 23 | `FamClass` |
| `σ` | 24 | `RawSel` |
| `cT` | 25 | `ℝ → ℝ → ℝ` † |
| `hEx` | 26 | `MinkDiv → UpperTheory.Top.ExS 𝒜 cT` † |
| `hduty` | 27 | `Duty Fm` (for every family `Fm` in `𝒜`) † |
| `hRB` | 28 | `Formalism.IndefR.IndefiniteRealisationBoundedRows` |
| `hTw` | 30 | `Formalism.L2.DIV.TieTwRec` |
| `hPA` | 32 | `Formalism.IndefR.Links.PrimRows3` (and `TypesSep3`) |
| `hLamP` | 34 | `Formalism.L2.Rows.RowsHoldLam3` |
| `hDivG` | 36 | `DivRows3G` |
| `hDcPtG` | 38 | `DcPtG` |
| `hTu` | 40 | `Closed` |
| `hn4` | 41 | `Closed` (of `StandardLattice.ClassNumberFormula₂`) † |
| `hLit` | 43 | `LitThin` |
| `hWu` | 44 | `Formalism.L2.SG.Pf.WuDecayOfGap` |
| `hRF` | 45 | `Formalism.L2.SG.RowsDef.RowsFinDim` |
| `hTF` | 46 | `Closed` (of `Formalism.MainNotions.PX.TFrame`) † |
| `c30` | 47 | `List ℝ → Formalism.MainNotions.S.CountingConstants` † |
| `hc30` | 48 | inequalities `0 ≤ … ∧ … ≤ …` on `c30` † |
| `sTy` | 49 | `Formalism.L2.SG.RowsPos.TypeP` |
| `sNG` | 50 | `Formalism.L2.SG.RowsPos.RowNGP` |
| `sM` | 51 | `Formalism.L2.SG.RowsPos.RowMainEqP` |
| `sLp` | 52 | `Formalism.L2.SG.ThmSOwn.LoopRowS` |
| `sO` | 53 | `Closed` (of `TheoremSSelected`) † |
| `h30` | 55 | `Closed` (of `CountAllPointsClass`) † |
| `hInstR` | 57 | `Formalism.L2.GlobalTheoryTheory.GenusMassVolumes.VolSigIndep` (and `ClassItemsAt`) |
| `selJ` | 59 | `Formalism.L2.SG.JoinSI.IndefiniteRealisationJoin` |
| `jOn` | 61 | `Closed` |
| `hMt` | 62 | an `∃ x0, ∀ x ≥ x0, …` closure condition on a module `Mtilde` † |
| `rRows` | 64 | `GlobalTheory.Fc.R1.SelectionDefiniteRows DR 𝒜 σ` |
| `aPt0` | 65 | `Closed` |
| `aPtTw` | 66 | `Closed` (of `TwistedPointIntegral`) † |
| `aPer0` | 68 | `Closed` (of `PeriodClassSumWeyl`) † |
| `aPerTw` | 69 | `Closed` (of `TwistedPeriodAdmissible`) † |
| `aP10` | 71 | `Closed` |
| `aAtG` | 73 | `Closed` |
| `aC2` | 75 | `Closed` |
| `hServ` | 76 | `GlobalTheory.Cp.SelectionServed` |
| `cIc` | 77 | `ℝ` |
| `hcI` | 78 | `0 < cIc` † |
| `irrC` | 79 | `Closed` |
| `zL` | 82 | `Closed` (a surjectivity statement) † |
| `tie` | 87 | `Closed` (of `RealPlaceSecondLayerConditions`) † |
| `hU` | 88 | `∀ D, MassRatioUnderVolume D` † |
| `hG` | 89 | `∀ D, GenusMassVolumes.GenusMassAt D 2` † |
| `nRest` | 90 | `N (D3 3 𝒜)`, the parameter `N` applied † |

Counts, from the table:
- 16 fields have head `Closed`, counted by `grep` on the source: a property required to hold on a family class built from `𝒜`, mostly `D3 3 𝒜`.
- 5 fields are data rather than proofs: `𝒜`, `σ`, the functions `cT` and `c30`, and the number `cIc`.
- One field, `rRows`, is where the parameter `DR`, and so `DefiniteSideCondition`, enters.

### `GlobalTheory.Fc.DefiniteSideCondition`

Defined in `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/DefiniteSideCondition.lean`, line 25, as a function of `D O c b C CH` (values of the type `GlobalTheory.Fc.R1.DefiniteSideType`). Its shape:
- For all hypotheses `hok1`, `hsep`, a `CovolumeOntoIsometryConditions` hypothesis `hP`, a `PassIn3` hypothesis `hI`, real constants `lam0 C0 ce Sw C1`, a family of `NumFacts` `H`, submodules `NuC`, and `DivisionCompatibilityDataThreeSided` data `I` that satisfies `DivTied3`,
- if `I` equals (`HEq`) the bundle's own `b.P.I`, then for every `u`, `RowsU …` holds.

It is a single implication, phrased in the library's own notions. I have read none of those notions.

### How the path gets it

On the path from `Main.lean`, `UpperTheory.Lit.every_character_of_theta_integrals_local_matching` supplies this input as `UpperTheory.Lit.nonempty_hyps_definite_side_of_closed_bound P F hA hM hX hL …` (note 2). I have not read that theorem.

## Interpretation (ours; check it)

- **The words in the names.** Several of them point at standard objects:
  - class number formula (`hn4`);
  - genus mass at 2 (`hG`) and mass ratio (`hU`);
  - Weyl sums of period classes (`aPer0`);
  - twisted point integrals and periods (`aPtTw`, `aPerTw`);
  - covolume and isometry conditions (`DefiniteSideCondition`);
  - counting points (`h30`).

  Together with the file path (`ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries`) and the author's items 8, 9, 12 and 18, they suggest that this structure collects the inputs of the iterated theta-lift argument. The author's items mention theta lifts between definite unitary groups, Siegel mass, Bessel periods and covolumes. This is a reading of names against the author's note, nothing more.
- **`hLit : LitThin`** is the one field whose name says "literature". Like the fields in note 2, on the path from `Main.lean` it is supplied by the library: by the axiom report, nothing on that path is assumed. I have not traced where.

## Not read, not understood

- Every notion named in the table, beyond its name.
- The construction `nonempty_hyps_definite_side_of_closed_bound`, which is where each of the 46 fields gets its value.
- The sibling structure `Hyps` used by `plugAll` (note 1's correction), and how it differs from `HypsAlt`.
- Why the structure has `Type 1`.

## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released, computed by me.

| File | SHA-256 |
|---|---|
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/Hyps.lean` | `7c2e3cf200c8adb32d232bf97122dca648fd4e19de132f6d1f07f620171fa8cb` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/DefiniteSideCondition.lean` | `4f1a7a434565fda3b4199f25bc0a4d932a6ecdc0dcb32250035c8731c3b693a4` |
