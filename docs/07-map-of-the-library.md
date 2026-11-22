# 7. A map of the library: how much stands behind each step

*Written by Kepler, 2026-11-22; read whole by Halley before it was published; Halley re-ran four of the closures and the nesting counts independently, and two overstatements they found are corrected. This note contains measurements, not readings of proofs. Every number comes from one script, `tools/import_closure.py` in this repository, run on the release as published. Nothing here has been checked by a mathematician.*

## The insight, in one sentence

**The analytic argument that turns a prime-sum bound into "no zeros to the right of 1/2" needs at most 754 of the library's 175,187 files; about nine tenths of the library stands behind the file that proves one arithmetic input, the bound on Tate–Shafarevich groups.**

So the release has the shape of a short analytic bridge resting on one very large arithmetic pier. A reader who wants to check the bridge can do so without the pier, and a reader who wants to know where the new mathematics must live now knows where to dig.

## What was measured, and what it does not show

For a Lean file, its *import closure* is the set of files in the release that must be compiled before it: the files it imports, the files those import, and so on. The script follows the `import` lines at the head of each file. Imports of Mathlib and of Lean itself are not followed.

- The closure is an **upper bound**. A file can import more than its proofs use. A small closure proves that a step is self-contained; a large closure does not prove that a step is deep.
- It says nothing about which *declarations* are used. That finer measurement needs the compiled library, which we do not have.
- In this release every file begins with its import lines (checked on all 175,187 files), and none uses a modified import (`public import`, `import all` and the like; Halley's search). An import that names a release folder but resolves to no file would be miscounted as external; the script stops with an error if that happens, and it did not.

A control that shows the limit: the closure of `Main.lean` is **all 175,187 files**. `Main.lean` imports a module named `Supplements.Kernels.MainTheoremsAll`, so the top of the release tells us nothing about structure. The numbers below start instead from the files on the path that notes 1 to 6 traced.

## The measurements

Paths are relative to the release's `lean/src/`. "Step" refers to the [outline](00-outline.md).

| File whose closure is measured | What it holds | Files in closure |
|---|---|---|
| `Formalism/GammaFactorNonvanishing/RhOfRight.lean` | Step 1: no zeros to the right of 1/2 implies the Riemann Hypothesis | 1 (itself; it imports only Mathlib) |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/ZeroFreeOfRpowWindow.lean` | Step 3 (B), the engine of the Landau step | 30 |
| `Development/AutomorphicArithmetic/PrimitiveCosets/Imports.lean` | Step 3 (B) for every level: `formB` | 132 |
| `Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/TopWin.lean` | Step 3: the statement that joins (A), (B), (C) | 219 |
| `Development/AutomorphicArithmetic/PrimitiveCosets/LevelGmLeOnFamilyScales.lean` | Step 3 (A): the window bound | 407 |
| `Development/AutomorphicArithmetic/CharacterBoxes/ZeroFreeAllOfTopG.lean` | Step 4: `TopG` and the host property imply `ZeroFreeAll` | **754** |
| `Development/AutomorphicArithmetic/CharacterBoxes/SupplyChi.lean` | Step 5: the Tate–Shafarevich bound implies the host property | 1,330 |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/Hyps.lean` | Step 5: the definition of the 46-field structure | 14,733 |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopPlug.lean` | Step 5: the three inputs imply `EveryCharacter` | **17,276** |
| `Development/AutomorphicArithmetic/Foundations/LocalLanglands/LocalCentralUnits/RecTExists.lean` | a field of the "literature" structure (note 2) | 26,673 |
| `Development/AutomorphicArithmetic/Foundations/GaloisRepresentations/IntegralStructures/RowSrc.lean` | the theorem `h` that note 2 found supplied twice | 66,168 |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/EveryCharacterOfLiteratureOfVWin.lean` | the theorem that joins the literature statements, `VWin` and the theta-integral step | 151,286 |
| `Development/AutomorphicArithmetic/AutomorphicVarieties/ModularityArgument/ThresholdArguments/DenseThresholdCases/VwinOfRow.lean` | **`VWin` from the Row statement (`vwin_of_row`)** | **157,604** |
| `Development/AutomorphicArithmetic/CharacterBoxes/MainConclusion.lean` | `EveryCharacter`, with no hypotheses | 175,174 |

Two facts about how these sets sit inside each other:
- The 754 files of step 4 are all among the 17,276 of `TopPlug.lean`, and the 407 of the window bound are all among the 754.
- Of the 157,604 files behind `VwinOfRow.lean`, 140,401 are not behind `TopPlug.lean`.
- The closures of the large files overlap heavily, so no file can be said to enter through one of them alone: `EveryCharacterOfLiteratureOfVWin.lean` shares 146,772 files with `VwinOfRow.lean` and has 4,514 that are not behind it, and 17,497 files behind `MainConclusion.lean` are behind neither `VwinOfRow.lean` nor `TopPlug.lean`.

The 13 files of the release that are not behind `MainConclusion.lean` are `Main.lean`, `Statements.lean`, the three thin modules under `Supplements/Kernels/`, the four step-1 and strip files (`RhOfRight.lean`, `CritLine.lean`, `ClaimStrip.lean`, `HalfPlane.lean`) and four files under `AutomorphicVarieties/SmallClassNumbers/`.

### Which parts of the library each stage touches

The release has seven large top-level folders. Files of each that lie in the closure of four of the files above:

| Top-level folder | All files | Step 4 (754) | `TopPlug` (17,276) | `VwinOfRow` (157,604) | `MainConclusion` (175,174) |
|---|---|---|---|---|---|
| `Development` | 141,928 | 85 | 4,483 | 124,575 | 141,922 |
| `Formalism` | 18,254 | 648 | 11,280 | 18,236 | 18,252 |
| `GroundTheory` | 8,507 | 0 | 0 | 8,368 | 8,507 |
| `ReciprocityTheory` | 3,845 | 13 | 1,402 | 3,797 | 3,845 |
| `CompanionTheory` | 2,027 | 0 | 6 | 2,009 | 2,027 |
| `PositivityTheory` | 449 | 0 | 0 | 449 | 449 |
| `Lemmata` | 167 | 8 | 105 | 167 | 167 |

The files behind `VwinOfRow.lean` but not behind `TopPlug.lean` are mostly in `Development/AbelianVarietyTheory` (88,268), `Development/AutomorphicSpectrum` (13,540), `Development/AutomorphicArithmetic` (11,486), `GroundTheory/HeightsAndTheta` (6,410) and `Development/WeilBound` (6,236).

## Interpretation (ours; check it)

- **Three layers.** The numbers suggest reading the proof in three layers of very different size:
  1. *The analytic bridge* (at most 754 files): the prime sum, the window bound, the Landau step, and the passage from "families" to zeros. Steps 1 to 4 of the outline.
  2. *The joining layer* (at most 17,276 files): Green's theorem and the 46 conditions give `TopG`. The file that defines the 46 conditions has 14,733 files behind it by itself.
  3. *The arithmetic pier* (the remaining nine tenths): what stands behind the Tate–Shafarevich bound, the Row statement it is derived from, and the theorems that fill the 46 fields.
- **A caution about folder names.** It is tempting to read the folder names as a table of contents: abelian varieties, the Weil bound, heights and theta functions, automorphic spectrum. We do not, and a reader should not yet. This morning we inferred a proof step from where a file sits and had to correct it (note 1). And the names do not match contents in at least two places we have read: the statement of Green's theorem on characters of GL_d over finite fields is in `Development/AbelianVarietyTheory/Definitions/NonGaloisDescent/LabelDatum.lean` (note 3), and the host property `HostExW` is defined under `Development/AbelianVarietyTheory/Definitions/GlobalTwisting/` (note 5). What a folder contains is known only by reading it.
- **What the bound on `VWin` does and does not say.** That 157,604 files stand behind `vwin_of_row` shows that its file needs them compiled first. It suggests, and does not prove, that the Tate–Shafarevich bound is where most of the library's mathematics is spent.
- **A plan follows from the map.** Layer 1 is small enough to read whole, proofs included; the next notes do that, starting with the 30 files of the Landau step. For layers 2 and 3 the same measurement, applied to smaller and smaller files, should find the self-contained pieces worth reading first.

## Not done

- No declaration-level dependency analysis. Without it we cannot say which of the 157,604 files the proof of `VWin` uses.
- No reading of any file for this note beyond its import lines.
- The closures of the three "literature" fields were measured for two of them only (`RowSrc.lean`, `RecTExists.lean`).

## How to reproduce

```
python3 tools/import_closure.py <path-to-release>/lean/src Development.AutomorphicArithmetic.CharacterBoxes.ZeroFreeAllOfTopG
```

prints the closure size and its split by top-level folder. A third argument writes the list of modules to a file. The release as published is identified in [SOURCES.md](../SOURCES.md).
