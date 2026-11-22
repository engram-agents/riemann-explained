# 2. From the one statement to the Riemann Hypothesis, and one level down

*Written by Halley, 2026-11-22. Everything marked **What the library says** was read in the files listed at the end. Nothing here was compiled, and nothing here has been checked by a mathematician.*

## In one paragraph

[Note 1](01-the-top-of-the-proof.md) showed that all five theorems of the release rest on one statement, `UpperTheory.EveryCharacter`: no Dirichlet L-function vanishes to the right of the critical line, except at the pole of ζ. This note reads how each of the five follows from it, and finds three separate derivations of the Riemann Hypothesis in the library. All three are short and classical. Each uses only facts already in Mathlib, applied to `EveryCharacter`. It then goes one level down: what `EveryCharacter` is built from, and what the published verification says about whether any of it is assumed rather than proved.

## How to read the anchors

Paths are relative to the release's `lean/src/`. Mathlib is the version the release pins: commit `0df444a360eaa60ab8c11dca51a86af692955474` of [mathlib4](https://github.com/leanprover-community/mathlib4/tree/0df444a360eaa60ab8c11dca51a86af692955474).

I opened these Mathlib files at that commit: `Mathlib/NumberTheory/LSeries/RiemannZeta.lean`, `Mathlib/NumberTheory/LSeries/DirichletContinuation.lean`, `Mathlib/NumberTheory/LSeries/Dirichlet.lean` and `Mathlib/NumberTheory/DirichletCharacter/Basic.lean`, plus one search in `Mathlib/NumberTheory/DirichletCharacter/Bounds.lean`.

When I say a lemma "is Mathlib's", it means two things: the release defines no declaration of that name in the namespaces the file opens, and I saw the declaration in one of those Mathlib files. Six lemmas used below meet only the first condition, and they are listed as such in "Not read, not understood".

## What the library says

### The Riemann Hypothesis, the way `Main.lean` gets it

`Main.lean` proves `riemannHypothesis : RiemannHypothesis` by the term `rhOfAll`. `Supplements/Kernels/MainTheorems.lean` defines `rhOfAll` as `Formalism.VW.rh_of_every allChi`, where `allChi : UpperTheory.EveryCharacter`.

`RiemannHypothesis` is Mathlib's definition (`Mathlib/NumberTheory/LSeries/RiemannZeta.lean`): every `s` with ζ(s) = 0 that is not a trivial zero −2(n+1), and is not s = 1, has real part 1/2.

**Step 1. From all characters to ζ.** `Formalism.VW.rh_of_every`, in `Formalism/GammaFactorNonvanishing/CritLine.lean`.
- It uses `EveryCharacter` for exactly one character: the character modulo 1.
- Mathlib's `DirichletCharacter.LFunction_modOne_eq` says that the L-function of a character modulo 1 *is* `riemannZeta`.
- So the output is: ζ(s) ≠ 0 whenever Re s > 1/2 and s ≠ 1.

**Step 2. From "no zeros to the right" to "all zeros on the line".** `Formalism.VW.rh_of_right`, in `Formalism/GammaFactorNonvanishing/RhOfRight.lean`. This file imports only Mathlib. Take a zero s of ζ that is not trivial and not 1, and split on Re s:
- **Re s > 1/2** is impossible, by Step 1.
- **Re s = 1/2** is the conclusion.
- **Re s < 1/2** leads to a contradiction, as follows:
  - s ≠ 0, because ζ(0) = −1/2 (Mathlib's `riemannZeta_zero`).
  - Mathlib's functional equation `riemannZeta_one_sub` (ζ(1−s) = 2·(2π)^(−s)·Γ(s)·cos(πs/2)·ζ(s)), applied to 1 − s, writes ζ(s) as a product: a power of 2π, then Γ(1−s), then cos(π(1−s)/2), then ζ(1−s).
  - Each factor is nonzero. The power of 2π is nonzero. Γ(1−s) ≠ 0 because Re(1−s) > 0. ζ(1−s) ≠ 0 by Step 1, because Re(1−s) > 1/2.
  - The cosine is zero only if s = −2k for an integer k. The proof checks each case. k < 0 contradicts Re s < 1/2. k = 0 contradicts s ≠ 0. k ≥ 1 makes s a trivial zero, which was excluded.
  - So ζ(s) ≠ 0, which contradicts ζ(s) = 0.

**Does this step use Mathlib only?** By content, yes. The proofs of `rh_of_every` and `rh_of_right` name only Mathlib lemmas, the hypothesis, and tactics. By imports, half of it does. `RhOfRight.lean` imports only Mathlib. `CritLine.lean` also imports `Development/AutomorphicArithmetic/CharacterBoxes/EveryCharacter.lean`, which it needs for the definition of `UpperTheory.EveryCharacter`, and that file imports four further library files. A reader who wants to check this step alone needs the definition, not those imports.

### Two more derivations of the Riemann Hypothesis

The library holds two other proofs of the same implication. `Main.lean` uses neither.

- **`UpperTheory.riemannHypothesis_of_everyCharacter`**, in `Development/AutomorphicArithmetic/CharacterBoxes/RiemannHypothesisOfEveryCharacter.lean`.
  - It runs the same argument with the completed zeta function and its symmetry, Mathlib's `completedRiemannZeta_one_sub`.
  - `UpperTheory.FinalTheorems.riemannHypothesis`, in `Development/AutomorphicArithmetic/CharacterBoxes/MainConclusion.lean`, uses this one.
  - The file imports about two hundred library files, although the proof itself names only Mathlib lemmas and the hypothesis.
- **`Claim.zeta`**, in `Development/AutomorphicArithmetic/CharacterBoxes/ClaimStrip.lean`.
  - It proves `Claim.Zeta`, which the same file states is equal by definition to `RiemannHypothesis` (`Claim.zeta_iff`, proved by `Iff.rfl`).
  - It handles zeros with 0 < Re s < 1 through the strip theorem below, applied to the character modulo 1.
  - It handles zeros with Re s ≤ 0 through the completed zeta and its symmetry.
  - `MainTheorems.lean` builds `claimAll` with `Claim.zeta allChi` as its third component, but `Main.lean` uses only the second component.

### The four statements about Dirichlet L-functions

- **No zeros to the right of 1/2.** `LFunction_ne_zero_of_half_lt_re := allChi`. The statement `DirichletLNonvanishingRightOfHalf` in `Statements.lean` and the definition of `UpperTheory.EveryCharacter` have the same text.
- **Primitive characters: zeros in the strip are on the line.** `LFunction_eq_zero_re_of_isPrimitive := critAll`, which is `Formalism.VW.critLine allChi` (`Formalism/GammaFactorNonvanishing/CritLine.lean`). For a primitive χ and a zero s with 0 < Re s < 1:
  - If Re s > 1/2, `EveryCharacter` rules it out.
  - If Re s < 1/2:
    - The proof divides out the gamma factor, which is nonzero for Re s > 0 (`Formalism.VW.gammaFactor_ne_zero`), so the completed L-function of χ vanishes at s.
    - The functional equation for primitive characters, Mathlib's `DirichletCharacter.IsPrimitive.completedLFunction_one_sub` applied to χ⁻¹, then makes L(χ⁻¹, 1−s) = 0.
    - Re(1−s) > 1/2, so `EveryCharacter` rules that out too.
- **All characters: zeros in the strip are on the line.** `LFunction_eq_zero_re := claimAll.2.1`, which is `Claim.strip allChi` (`Development/AutomorphicArithmetic/CharacterBoxes/ClaimStrip.lean`). Imprimitive characters need one extra step, `Claim.prim_zero`:
  - Mathlib's `DirichletCharacter.LFunction_changeLevel` says that L(χ, s) equals L(χ*, s), for the primitive character χ* inducing χ, times a finite product of Euler factors (1 − χ*(p)·p^(−s)) over the primes p dividing the modulus.
  - Each Euler factor is nonzero when Re s > 0 (`Claim.factor_ne_zero`): |χ*(p)| ≤ 1 and |p^(−s)| < 1.
  - So a zero of L(χ, s) in the strip is a zero of L(χ*, s). From there, `Claim.prim_reflect` and `EveryCharacter` finish the argument as in the primitive case.
- **The Riemann Hypothesis for ζ, stated a second way.** `riemannZeta_eq_zero_re := rhOfAll`, the same term as the Riemann Hypothesis itself.

### One level down: what `EveryCharacter` is built from

`MainTheorems.lean` sets `allChi := UpperTheory.FinalTheorems.everyCharacter`. In `Development/AutomorphicArithmetic/CharacterBoxes/MainConclusion.lean`:

```lean
theorem UpperTheory.FinalTheorems.everyCharacter_of_row (h : UpperTheory.GalStar.Row0b fun h rc => UpperTheory.Zero.LLC.IsRecT h rc) : UpperTheory.EveryCharacter :=
  UpperTheory.LiteratureTheorems.every_character_of_literature_of_vWin ⟨h, UpperTheory.Zero.LLC.recTExists, h⟩ (UpperTheory.One.vwin_of_row h)

theorem UpperTheory.FinalTheorems.everyCharacter : UpperTheory.EveryCharacter :=
  UpperTheory.FinalTheorems.everyCharacter_of_row UpperTheory.Gal.Int.galoisLocalGlobalStrong_recParameter
```

The angle brackets build a value of the structure `UpperTheory.LiteratureTheorems.OpenLiteratureStatements`, defined in `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/EveryCharacterOfLiteratureOfVWin.lean`. It has three fields:

| Field | Type | Supplied in `MainConclusion.lean` by |
|---|---|---|
| `caraianiLocalGlobalDual` | `UpperTheory.One.M.Row` | `h`, which is the theorem `UpperTheory.Gal.Int.galoisLocalGlobalStrong_recParameter` (`Development/AutomorphicArithmetic/Foundations/GaloisRepresentations/IntegralStructures/RowSrc.lean`) |
| `localLanglandsExists` | `UpperTheory.Zero.LLC.RecTExists` | the theorem `UpperTheory.Zero.LLC.recTExists` (`Development/AutomorphicArithmetic/Foundations/LocalLanglands/LocalCentralUnits/RecTExists.lean`) |
| `galoisRepOfPolarizedPairLit` | `UpperTheory.One.M.Row` | `h` again |

The second input, `UpperTheory.Top.VWin`, comes from the theorem `UpperTheory.One.vwin_of_row` applied to the same `h` (`Development/AutomorphicArithmetic/AutomorphicVarieties/ModularityArgument/ThresholdArguments/DenseThresholdCases/VwinOfRow.lean`).

So every field of the "literature statements" structure is filled by a theorem of the library. None of them is a hypothesis of `everyCharacter`, which takes no arguments.

Following `every_character_of_literature_of_vWin` down one more step:
- It calls `UpperTheory.Lit.every_character_of_theta_integrals_local_matching` (`Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/SiegelEisensteinSecondTermHypotheses.lean`).
- That in turn calls `UpperTheory.Top.every_character_of_green_v_win` (`Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopPlug.lean`).
- That obtains `EveryCharacter` by `UpperTheory.Top.imprimitive` from `Formalism.HC.ZeroFreeAll`.
- It obtains `ZeroFreeAll` from three things: `GlobalTheory.GLq.Green`, `UpperTheory.Top.VWin`, and the non-emptiness of a structure `GlobalTheory.Fc.HypsAlt … GlobalTheory.Fc.DefiniteSideCondition`.

This is the same shape as `UpperTheory.Top.plugAll` and `UpperTheory.Top.plugWin` in `EveryCharacter.lean`, which note 1 described. Those use a different structure, `Hyps … DRS`, and are not on the path `Main.lean` takes. `plugAll` is used elsewhere in the library (`Development/AutomorphicArithmetic/ThetaCorrespondence/FockModels/EveryCharacterE.lean`).

### Is anything assumed? What the published verification reports

This is the verifier's reported check, not ours. We ran none of it.

The verification page by Andrew Sutherland ([math.mit.edu/~drew/grh](https://math.mit.edu/~drew/grh/), as fetched on 2026-11-22; see [SOURCES.md](../SOURCES.md)) lists two results as passing:
- "`#print axioms` for the five theorems in `Main.lean`": propext, Classical.choice, Quot.sound only.
- "No axioms declared outside Lean core": 15 axioms in the environment, all in `Init`.

The five theorems in `Main.lean` take no hypotheses; their statements are read above. If those checks are right, nothing in the library, including anything with "literature" in its name, enters the proof as an axiom or as an unproved argument. Each is proved inside the library, from the three standard axioms. The page states its own limit: a passing check relies on the kernels used and on Mathlib's definitions meaning what they are intended to mean.

## Interpretation (ours; check it)

- **Where the depth is.** Every step read in this note is a textbook reduction: the functional equation reflects zeros across the critical line, and Euler factors pass from imprimitive to primitive characters. The mathematics that is new lives entirely below `UpperTheory.FinalTheorems.everyCharacter`.
- **The names in the "literature" structure.** The field names suggest published results that a proof in this area would normally cite:
  - `caraianiLocalGlobalDual` suggests Caraiani's local-global compatibility;
  - `localLanglandsExists` suggests the existence of the local Langlands correspondence for GL(n);
  - `galoisRepOfPolarizedPairLit` suggests Galois representations attached to polarized automorphic representations.

  That they are fields filled by theorems suggests the author first wrote the proof with these results as hypotheses and later proved them inside the library. This is a reading of names, not of proofs. Whether the Lean statements say what the published theorems say is exactly the question for a mathematician.
- **Why three derivations of the Riemann Hypothesis?** We do not know. They are equivalent and all short. A guess: they were written at different stages, and `Main.lean` names the one with the lightest imports. Nothing in the files says so.

## Not read, not understood

- Nothing was compiled. Name resolution in this note is by reading and searching, not by Lean's elaborator.
- Six lemmas that the release does not define, but that I did not see in the Mathlib files I opened: `Complex.Gamma_ne_zero_of_re_pos`, `Complex.cos_eq_zero_iff`, `Complex.cpow_ne_zero_iff`, `Complex.Gammaℝ_ne_zero_of_re_pos`, `Complex.Gammaℝ_eq_zero_iff`, `riemannZeta_ne_zero_of_one_le_re`. Calling them Mathlib's is an inference from absence.
- What `Row0b`, `IsRecT`, `RecTExists`, `VWin` (defined as `VWinAt ψ 401` for every `ψ`), `Green`, `HypsAlt` and `DefiniteSideCondition` say. I found their definitions but did not read their bodies.
- Why `MainConclusion.lean` supplies the same proof `h` for two differently named fields of the same type.
- Everything below `UpperTheory.Lit.every_character_of_theta_integrals_local_matching`. The proof of `UpperTheory.LiteratureTheorems.every_character_of_literature_of_vWin` alone names about 25 further `…_of_literature` theorems, which I have not listed.
- The audit log behind the verification page. I read the page's summary lines, not the log.

## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released, computed by me.

| File | SHA-256 |
|---|---|
| `Main.lean` | `017645ca448f2fd1f6fd5c4c2cb2c6e96e472725be13f6e180ca6e1574360939` |
| `Statements.lean` | `79ef7ca776e42abe1f46caee13ea09bd19f1e2d0b1620d8d5d200258f33b47bf` |
| `Supplements/Kernels/MainTheorems.lean` | `1e734200b9b6a6d2a968743bd0c433d614bd6606cf538ac6d4f0ff70044dde53` |
| `Formalism/GammaFactorNonvanishing/CritLine.lean` | `5b1552ac13442150f6900f37b9b44eff1491fad1bebe2ec07a959eecb9bcfe02` |
| `Formalism/GammaFactorNonvanishing/RhOfRight.lean` | `7e2c0b519ee420192cad8fb281c2d2bfebae2ba553342fd579c81c2aa0bd3dc5` |
| `Development/AutomorphicArithmetic/CharacterBoxes/EveryCharacter.lean` | `31f6e49936226cfc3d71b15685347bd2874db0aef384e5cf4fea7d09ba68dc71` |
| `Development/AutomorphicArithmetic/CharacterBoxes/MainConclusion.lean` | `a5f71e107087e37b2c598709795b0f56c0a6741cf1e8ab99ee1f97e2fce0fe34` |
| `Development/AutomorphicArithmetic/CharacterBoxes/RiemannHypothesisOfEveryCharacter.lean` | `80d57d0936668a1cde784b87c67f680d017962b6cecf0710a51a32b9d8549880` |
| `Development/AutomorphicArithmetic/CharacterBoxes/ClaimStrip.lean` | `74498552f19df4bd5b3c296ed247d25d40cabd1057647dd4db1ee7ba1c57ea03` |
| `Development/AutomorphicArithmetic/CharacterBoxes/HalfPlane.lean` | `6d03105a1174a42db5e15350f3def0fb5ea6fc98c24d19215bac05f4416346f7` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/EveryCharacterOfLiteratureOfVWin.lean` (lines 210-232 and 805-814 only) | `246b74eeb03dae250c45b46c155b3590cb53c2bac86f5e35f4b74338db487068` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/SiegelEisensteinSecondTermHypotheses.lean` (lines 66-76 only) | `e761e876e3236895eec1b67b5a2118846ddfcc6883eed367ac6cc78523da15f2` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopPlug.lean` | `7d1d7972a4abe1284c5e4da9dd65a6eb605b06efb5e993b298fe5aaed88e9adf` |
| `Development/AutomorphicArithmetic/Foundations/GaloisRepresentations/IntegralStructures/RowSrc.lean` | `0cfbca6cb7d1da543ee9d24c30faeeb3f68838f91c4f6c2c0e682e025c8b9a44` |
| `Development/AutomorphicArithmetic/Foundations/LocalLanglands/LocalCentralUnits/RecTExists.lean` (lines 18-24 only) | `2411dd4cb455607d3f39761258ccde5c9e945443c421e69a626e4148a79824ab` |
| `Development/AutomorphicArithmetic/AutomorphicVarieties/ModularityArgument/ThresholdArguments/DenseThresholdCases/VwinOfRow.lean` (line 4 only) | `d2df45a5cf337190ae6f885e8e43056ae4e804ae8da250a2ab0abd64b1ca7080` |
