# 15. Where do the three literature statements enter the proof of `LinkN`, and what do they do there?
<!-- rh-note {"authors":["Halley"],"group":"literature-statements","id":"15","level":2,"list_title":"Where do the three literature statements enter the proof of `LinkN`, and what do they do there?","readers":["Kepler"],"release":"rh-2026-11-20"} -->

*Written by Halley, 2026-11-23. Read line by line by Kepler, in his own copy of the source, before it was published. Everything marked **What the library says** was read in the files listed at the end, at the lines given. The lean blocks were cut from the source by line range with a script. Nothing was compiled. Nothing here has been checked by a mathematician.*

## In short

[Note 14](14-where-linkn-comes-from.md) found that the literature bundle `OpenLiteratureStatements` has three fields, and that all three reach the inputs of the theorem that produces `LinkN`. Its Correction of 2026-11-22 said where: `localLanglandsExists` (type `RecTExists`) is a hypothesis of that theorem, and it and the other two, `caraianiLocalGlobalDual` and `galoisRepOfPolarizedPairLit`, are built into the field `what₂` of the bundle `prN`, as `what₂.car` and `what₂.gal`. Note 14 left open whether the proof of `LinkN` reads them. This note follows each one until it is used or the reading stops.

We use four labels. **USED**: the proof applies the hypothesis or takes it apart. **PASSED ON**: it is given whole to another theorem. **DROPPED**: it is bound as an underscore, or never named again. **STILL OPEN**: what was read does not settle it. A label covers only the sites named next to it.

| Statement | Where it is USED | By which chain | Does what it gives reach `LinkN`'s conclusion? |
|---|---|---|---|
| `localLanglandsExists` (`RecTExists`) | `locParT`, the local parameters, is defined by choosing from it; `galRep_rankTwo_alt` uses `locParT` | `locParT` (`IsRecTLocRecT.lean` 25-26) → `galRep_rankTwo_alt` (lines 57, 63); every datum on the chain is also indexed by it | It is a hypothesis of the theorem that produces `LinkN` (note 14, step 2). Which uses of `locParT` matter for the conclusion: STILL OPEN |
| `caraianiLocalGlobalDual` (`what₂.car`) | `galRep_rankTwo_alt`, line 54: it produces a Galois representation for rank two and up | `galClose_alt` → `automorphic_galois_admissible_of_theta_local_inputs` → `galRep_rankTwo_alt` | Its result becomes part of the field `a2` of each member's conditions; the cut keeps that part; the cut's facts pass `a2` whole to two theorems we did not open. STILL OPEN |
| `galoisRepOfPolarizedPairLit` (`what₂.gal`) | `exists_aw_alt`, line 49: it produces a Galois representation from a cuspidal one | site (a): the member preconditions → `galois_side_at_place_alt` → `galLoc_triple_with_localization_alt` → `isTriple_of_sideB_alt` | It goes into the field `evidence` of a Galois triple. The member preconditions take from that triple only its field `vec`, which is built without it. So by this route, NO. Other routes: STILL OPEN |

Our first reading, before this note was published, said that `galoisRepOfPolarizedPairLit` reaches `LinkN`'s conclusion. Every step of that route was read by name, and every step holds. But at one step the route takes one field out of a structure, and the field it takes is not the one this statement built. "Read by name" is not enough; at each step the reader has to say which field is read out. Section 3 shows the step.

## What the library says

### 1. `RecTExists`: used by definition

`Development/AbelianVarietyTheory/Definitions/Divisors/IsRecTLocRecT.lean`, lines 25-26:

```lean
def locParT (hT : UpperTheory.Zero.LLC.RecTExists) (π : CG E a) (h : IsPlaceOver A w) : WD h :=
  locRecT hT h ⟨a, ParLaws.toCl (π.loc w)⟩
```

`locRecT hT h` is the choice from `hT` (line 21 of the same file, `(hT E Ω A w h).choose_spec`), so the local parameters `locParT` exist only through `RecTExists`. On the path read, `galRep_rankTwo_alt` (section 2) uses `locParT hL` at lines 57 and 63. `GalRepRankTwo.lean` also uses it at line 30, inside `core_data_of_point`, which `galRep_rankTwo_alt` calls at line 60 with `hL`; we have not read that proof (see Not read). `RecTExists` also indexes the data on the chain (`CharacterChoiceData hL D`). It is DROPPED in `mergeP'_alt` (section 2).

*Twin.* My text search finds two declarations named `RecTExists` (`def RecTExists` at the start of a line). The chain uses the one in `UpperTheory.Zero.LLC` (`Development/AutomorphicArithmetic/Foundations/LocalLanglands/IsRecTOfIsRec.lean`, line 78); the other is in `Development/AbelianVarietyTheory/Definitions/NonGaloisDescent/RecTExists.lean`, line 77. We have not read what `RecTExists` states beyond its first line.

### 2. `caraianiLocalGlobalDual` (`car`): used once on the path read

`galClose_alt` (`Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/SClose.lean`, line 22) hands both `gal` and `car` to `mergeP'_alt`:

```lean
  fun hP hL D P => _root_.UpperTheory.GalS.Prod.automorphic_galois_admissible_of_theta_local_inputs hP (_root_.UpperTheory.GalS.mergeP'_alt hP.fin hL hP.gal hP.car hP.clo) hL D P
```

`mergeP'_alt` (`.../ThirdPlaceSeries/WeightsConj.lean`, lines 81-82) returns `car` and drops the rest, `gal` included:

```lean
theorem mergeP'_alt (_ : GlobalTheory.Published.AutomorphicFormsFiniteGL) (_ : _root_.UpperTheory.Zero.LLC.RecTExists) (_ : _root_.UpperTheory.GalS.CuspUAlt) (h : _root_.UpperTheory.GalS.CarUAlt)
    (_ : GlobalTheory.Published.RegularAlgebraicPurity) : _root_.UpperTheory.GalS.CarUAlt := h
```

`automorphic_galois_admissible_of_theta_local_inputs` (`.../ThirdPlaceSeries/GalRepRankTwo.lean`, lines 133-146) passes it on to `galRep_rankTwo_alt` in the branch for rank two and up (line 144), and `galRep_rankTwo_alt` USES it at line 54:

```lean
  obtain ⟨r, wt, HT, H, hLG⟩ := hC D.host.E D.nd.Om (D.nd.l i) (D.naut.iotaQC i) a ha π₀ hc₀ hr₀
```

The result is the first component of `AutomorphicGaloisAdmissible`. `SClose.lean` names it `ha2` at line 39 and puts it in the member's conditions at line 41, where it is the field `a2`. The cut keeps that component: `galois_admissible_of_restricted_cmDatum` (`Development/AutomorphicArithmetic/Foundations/GaloisRepresentations/TypeConditions/GaloisAdmissibleOfRestrictedCmDatum.lean`, line 11) reads it out of the member's `a2`:

```lean
    obtain ⟨ρ, c1, s, o, u, e⟩ := (h i.1).1 a ha π hc hr
```

and `rsA_cut_of_aux41` (`.../ThirdPlaceSeries/AdmissibleSevenRestrict.lean`, line 23) makes that the cut's `a2`. The cut's facts then pass `h.what₂.a.a2` whole to `de_rham_points_weight_jumps_alt` and `admJ_of_admPar` (`.../ThirdPlaceSeries/CFacts.lean`, lines 50 and 54), and `LinkN`'s proof consumes those facts (`.../ThirdPlaceSeries/LinkNFam.lean`, lines 48-49). We have not opened those two theorems, so whether they read the component that `car` built is STILL OPEN.

### 3. `galoisRepOfPolarizedPairLit` (`gal`): used, into a field the route does not take out

**Two by-name sites drop it.** `mergeP'_alt` (above) and `allCuspidalOpenBound_of_cuspU_character_choice` (`.../ThirdPlaceSeries/NOProd.lean`, line 38; `gal` is the underscore in `fun hF _ hL D P`):

```lean
  fun hF _ hL D P => _root_.UpperTheory.GalN.tempered_of_true_cuspidal_alt hF P.cg (_root_.GlobalTheory.TempGal.rankOneUnitary_of_charSide hF hL D P)
```

**Where to look next.** My text search found `what₂.gal` at 14 sites in the release. Kepler's import closure of `CFinal` (a necessary condition only) left 2 of them inside it; we followed one, site (a), by hand.

**Site (a), where it is used.** `galois_preconditions_at_mem` passes `prn` whole to `finiteTriples_satisfy_condition_alt` (`.../ThirdPlaceSeries/PreAtMem.lean`, line 91). Through a `first` wrapper (`.../ThirdPlaceSeries/GalLocTripleWithLocalization.lean`, lines 133-134), `galois_side_at_place_alt` (115-126) and `galLoc_triple_at_place_alt` (110), the chain reaches `galLoc_triple_with_localization_alt`, whose line 57 takes `gal` out of the bundle:

```lean
  have hg := _root_.GlobalTheory.GalAway.galoisReps_of_cgTrue_alt_alt hL hP.what₂.fin hP.what₂.gal _ T cg
```

`galoisReps_of_cgTrue_alt_alt` (`.../ThirdPlaceSeries/GaloisRepsOfCgTrue.lean`, line 52) passes it on to `exists_aw_alt`, which USES it (`.../ThirdPlaceSeries/UnrRecOfHasSat.lean`, line 49):

```lean
  obtain ⟨r, wt, HT, H⟩ := hG.of_isCsd Ω ι ha (π := π) hr hc
```

**What it builds.** The result `hg` goes, at line 61 of `GalLocTripleWithLocalization.lean`, to `side_eigen_export_alt`, a `first` wrapper (`.../ThirdPlaceSeries/IsTripleOfSideBStatement.lean`, line 17) over `isTriple_of_sideB_alt` (`.../ThirdPlaceSeries/IsTripleOfSideB.lean`, lines 28-50). That proof builds a Galois triple, a structure with four fields (`.../ThirdPlaceSeries/IsTripleAtOfConj.lean`, lines 41-46):

```lean
structure IsGaloisTripleForExpansion (Y : NExp D.R D.host D.what₂ D.LL0 D.nd X) : Prop where
  artin : IsGlobalArtin art
  evidence : ∀ i, X.NonzeroIndexPlace i → ∀ b : Bool, ∃ ρ : Reading X i b, IsChars C art ρ ∧
    ∀ s : X.Sig i, X.side i s = b → _root_.GlobalTheory.Triple.IsGaloisTripleAtSignature C art ρ s
  vec : ∀ i, X.NonzeroIndexPlace i → ∀ s : X.Sig i, Formalism.MainNotions.BlochKatoReduction.Gen.goodE Y i s
  all : Y.sig_all
```

It fills them at lines 31-32 of `IsTripleOfSideB.lean`:

```lean
  refine ⟨cf, art, ha, fun i hi b => ?_,
    fun i _ s => GlobalTheory.T.twistTriple_eigenvector_in_good_part D cf Rw low Pq S hL eig θ Bs Sb hSb hks hEO i s, hall⟩
```

The hypothesis that carries `gal` is `hGR` (by position: `hg` is the argument in its place at line 61). It is used at line 39, inside the proof of the field `evidence`:

```lean
  obtain ⟨r, hr⟩ := hGR π hpar.1.csd hpar.1.ralg (D.ntw.l i) ρ.ι
```

The field `vec` is built at line 32 by `twistTriple_eigenvector_in_good_part`, and `hGR` is not among its arguments.

**What the route takes out.** The triple becomes the field `triple` of a `GalSideAlt` (`.../ThirdPlaceSeries/HkOfBuilt.lean`, line 87). `finiteTriples_satisfy_condition_alt` reads it at line 28:

```lean
  exact ⟨s, hs, (_root_.GlobalTheory.Triple.adm8_allGood_sig_of_isTriple _ G.triple).2.1 _ (hW a) s⟩
```

and `.2.1` of `adm8_allGood_sig_of_isTriple` (`.../ThirdPlaceSeries/SatakeIdentityOfIsTriple.lean`, line 108) is `allGood`, which takes out `vec` only (`IsTripleAtOfConj.lean`, line 93):

```lean
theorem IsGaloisTripleOfExpansion.allGood (h : _root_.GlobalTheory.Triple.IsGaloisTripleOfExpansion Y) : GlobalTheory.TwSys.AllGood Y := let ⟨_, _, h⟩ := h; h.vec
```

That is the field `trip` of the member preconditions (`PreAtMem.lean`, lines 93 and 101).

**Where `trip` goes.** By name, every step read: the cut carries it (`CFacts.lean`, lines 42 and 57); `NLinkClose.main_alt_alt` (`.../ThirdPlaceSeries/ImportsFurtherTail.lean`, lines 22-109) passes the facts whole to `exists_hubData_admJ_setup` (line 49), a `first` wrapper (`.../ThirdPlaceSeries/ExistsSetupLargeStatement.lean`, line 13) over `exists_setup_large_alt`, which reads `trip` out at line 38:

```lean
  have h6 := GlobalTheory.JointSix.main GlobalTheory.Published.cheb_holds (Fm.D x i) (Fm.ex x hx1 i).nch X.r X.ρ hcan.fam hfa.nct hfa.trip
```

`JointSix.main` (`Development/AbelianVarietyTheory/Proofs/InertiaEigenvalues/PsiAtPsiAt.lean`, line 29) passes it to `selCore`, which passes it to `sel_at` (`.../InertiaEigenvalues/SameCharEqOne.lean`, line 72), which USES it at line 40:

```lean
  obtain ⟨s, htr, hgood⟩ := hT a σ Sg hrow hW
```

The result becomes `hkill` (`ExistsSetupLarge.lean`, line 40) and then the field `kill` of the conclusion (`ImportsFurtherTail.lean`, line 94), and that conclusion is what `LinkN`'s proof receives at `LinkNFam.lean` line 51. So `trip` reaches the conclusion. But what `trip` carries is `vec`, and on this route `vec` was built without `gal`.

**So:** on site (a), `gal` is USED, and what it gives goes into `evidence`. Whether anything on `LinkN`'s path reads the `evidence` of a triple is STILL OPEN.

## A second local Tate duality enters `LinkN`

Note 14 already lists the seven fields of `NLink.Hypotheses₂` and shows that the field `tate` is filled by a library theorem (its "Where the inputs come from", the block with `top_tate`). What is new here is where that field is used. Note 14's sentences about "the three local statements" are about the three hypotheses of `final_alt_alt` (local finiteness, local Tate duality, local Euler characteristic). They are not the whole story. `NLinkClose.main_alt_alt`, which proves the conclusion `LinkN` is built from, opens with:

```lean
  obtain ⟨C₀, h03⟩ := GlobalTheory.T.theoremE_corollaryA_closing_all_data hP.bk hP.tate hP.euler
```

`hP` is the bundle `Hypotheses₂` (`Development/AbelianVarietyTheory/Definitions/NonGaloisDescent/BoundAtTwoAndThreeForFamily.lean`, line 22):

```lean
  tate : Formalism.GaloisCohomology.LocalTateDualityK
```

By its name, that is local Tate duality for local fields (`K`); we have not read its definition. On Main's path it is filled by a library theorem (`.../ThirdPlaceSeries/EveryCharacterOfLiteratureOfVWin.lean`, line 662; note 14 found the term does not use the literature bundle):

```lean
  tate := (_root_.UpperTheory.LiteratureTheorems.local_tate_duality_k_of_literature O)
```

The result `h03` is used at line 65 of `ImportsFurtherTail.lean`. We have not read `theoremE_corollaryA_closing_all_data`. My text search for `structure Hypotheses₂` finds nine in the release, in nine namespaces; this one is in `GlobalTheory.NLink`.

## How the sites were found, and which instrument settled what

- **Kepler's statement table** (a text match, so a lower bound) named the file that `LinkN`'s statement resolves to (`ImportsFurtherTail.lean`), and two of the `trip` sites among the statements that file names.
- **Kepler's import closure** (a necessary condition only) removed 12 of the 14 `what₂.gal` sites. For the 16 files with a `trip` site, it removed 1 from `CFinal`'s closure and 2 from `LinkNFam`'s, so there it hardly narrowed.
- **The hand read is the finding**, and it can still stop too early. My first read followed `gal` by name, step by step, to `LinkN`'s conclusion. At one step the name stood for a whole structure, the Galois triple. Its fields were built from different inputs, and the next step took out only one field. A name that arrives at the conclusion does not show that the content arrives. So each step in this note says which field is read out, and a step that passes a whole structure on is labelled PASSED ON until the reader of that structure has been opened.

## Not read

- Site (b) of `what₂.gal` (`Development/AbelianVarietyTheory/Proofs/InertiaEigenvalues/ExistsGaloisSide.lean`, line 57), and the 12 sites outside the import closure.
- Any reader of a triple's `evidence` field on `LinkN`'s path.
- The other `trip` site on Kepler's list (`.../ThirdPlaceSeries/EtaLocLeRhs.lean`, line 30).
- `hCT`'s side of `LinkN`'s facts (`exists_bound_tieChi_of_prints`).
- `de_rham_points_weight_jumps_alt` and `admJ_of_admPar`, which receive `a2` whole (section 2).
- `twistTriple_eigenvector_in_good_part`, which builds `vec`.
- `IsGaloisTripleOfExpansion.adm8`, the first component of `adm8_allGood_sig_of_isTriple` (`SatakeIdentityOfIsTriple.lean`, line 108): a reader of the whole triple that we have not opened, and the nearest place where `evidence` could be read.
- `core_data_of_point` (`GalRepRankTwo.lean`, lines 23-39), which `galRep_rankTwo_alt` calls at line 60 with `hL`.
- `theoremE_corollaryA_closing_all_data`.
- What `RecTExists`, `CarUAlt` and `CuspUAlt` state beyond their names and first lines.
- Every proof on these routes that was passed a whole structure and that we name above only as passing it on.

### Addition, 2026-11-23 (later the same day): who reads a triple's `evidence`

*Read by Kepler before it was published. The body above is unchanged.* Section 3 left open whether anything on `LinkN`'s path reads the field `evidence` of a Galois triple. **By a text search of the whole release, every by-name reader of `evidence` in the family of theorems that `Main`'s route uses is either outside the import closure of `CFinal` or ends at a component the route drops. This is not a proof that nothing reads it.** Kepler ran the whole-tree search; I reproduced its counts with my own commands and re-read each line cited here.

- **The reader on the route.** `IsGaloisTripleForExpansion.triple` (`IsTripleAtOfConj.lean`, lines 89-92) takes `evidence` apart at line 91. It is called by `unrRho` and `hkFrob` (`SatakeIdentityOfIsTriple.lean`, lines 79 and 83), and those by `IsGaloisTripleOfExpansion.adm8` (lines 85-105). `unrRho` then uses the field `gal` of the reduction it finds (line 29). That field says that one Galois representation is attached to one automorphic representation; on the route of section 3 it is filled, through `isTripleAt_of_conj_alt` (`IsTripleAtOfConj.lean`, line 76), from the hypothesis that carries `galoisRepOfPolarizedPairLit` (`IsTripleOfSideB.lean`, lines 39 and 45). `adm8` is named only where it is declared and at line 108, as the first component of `adm8_allGood_sig_of_isTriple`. That theorem has two callers: `finiteTriples_satisfy_condition_alt` (`FiniteTriplesSatisfyCondition.lean`, line 28), which takes the second component, `AllGood`, which `allGood` gets from the field `vec` (`IsTripleAtOfConj.lean`, line 93); and `galois_inputs_alt` (`ThirdPlaceSeries/GaloisInputs.lean`, line 25), which is outside the import closure of `CFinal`.
- **The other uses of the triple on the route.** Inside that closure, the field `triple` of a `GalSideAlt` is used by the name `G.triple` at two places in this family: `FiniteTriplesSatisfyCondition.lean` line 28 (the component from `vec`, above) and `CompatibleSystemTripleLayerInputs.lean` line 54 (`sig_all`, which comes from the field `all`, `IsTripleAtOfConj.lean` line 94).
- **The other readers in this family are outside.** Twelve files name the triple types `IsGaloisTriple`, `IsGaloisTripleOfExpansion` or `IsGaloisTripleForExpansion` as a whole word; eight are inside the closure, and the four outside are `Adm2OfIsTriple.lean`, `GaloisHypothesesOfIsTriple.lean`, `SetHypOfIsTripleOfGalHodge.lean` and `TripleAttOfIsTriple.lean`, all in `ThirdPlaceSeries`. `Adm2OfIsTriple.lean` line 89 reads `evidence` and drops its third part.
- **The twin family is not on Main's route.** The release has a second, parallel family of theorems with its own triple type, `IsTriple`, and its own readers of `evidence` inside the closure (`IsTripleFor.triple`, `Development/AbelianVarietyTheory/Definitions/NonGaloisDescent/CharpolySmulOfProd.lean` line 422; `Development/AbelianVarietyTheory/Proofs/InertiaEigenvalues/MemMaximalIdealIff.lean` line 369, which drops the third part). Site (b) of section 3 (`ExistsGaloisSide.lean`, line 57) belongs to it. That family proves its own version of the closed statement about `LinkN`, `GlobalTheory.NLink.Final.main` (`Development/AbelianVarietyTheory/Proofs/InertiaEigenvalues/LinkOfClosedAtFamily.lean`, lines 68-70, which calls the twin of the member preconditions, `facts_at_membership`). Followed by name upward, it is called only by `nonempty_hyps_of_classicalTheoremsUE` (`Development/AbelianVarietyTheory/Proofs/DivisorProofs/NonemptyHypsOfPublishedUE.lean`, line 36), which is called only inside `hypsE₂` (`Development/AutomorphicArithmetic/ThetaCorrespondence/FockModels/EveryCharacterE.lean`, line 65), and neither `hypsE₂` nor `everyE₂` is named in any other file. `Main`'s route uses the other family: `final_alt_alt` (`CFinal.lean`, lines 19-22, which calls `galois_preconditions_at_mem`), called at `HypothesesNonemptyOfUnramifiedExponents.lean` line 47, which is reached from `SiegelEisensteinSecondTermHypotheses.lean` line 68 and `EveryCharacterOfLiteratureOfVWin.lean` line 811. Two file names occur in both families: `GaloisInputs.lean` and `SetHypOfIsTripleOfGalHodge.lean` exist in `ThirdPlaceSeries` and in `Development/AbelianVarietyTheory/Proofs/InertiaEigenvalues`; the copies in `ThirdPlaceSeries` are outside the closure, and the copy of `SetHypOfIsTripleOfGalHodge.lean` in `InertiaEigenvalues` is inside it (it takes the twin type, line 27).

*Scope.* This is a text search: 23 lines in the release match `.evidence`, 9 match `.triple hi s`, and the import closure of `CFinal` (computed from the `import` lines, by Kepler and by me separately, 48,123 files each) says only what may be used, never what is used. A proof can take a `GalSideAlt` or a triple apart by position, without writing `evidence` or `triple`; `GalSideAlt` is named in 12 files, which we counted and did not read. `G.triple` was searched under that variable name only. Lean was not run.

## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released, computed by me.

| File | SHA-256 |
|---|---|
| `Development/AbelianVarietyTheory/Definitions/Divisors/IsRecTLocRecT.lean` (lines 19-26 read) | `cf5c6ea675fe48794e34d8a221fd64c29a95712acf6154de005f3394f7b3a006` |
| `Development/AutomorphicArithmetic/Foundations/LocalLanglands/IsRecTOfIsRec.lean` (line 78 read) | `4054d69535a55b8df339dee1ed766d38cb271ae87ce6033a8e0195ac577d9931` |
| `Development/AbelianVarietyTheory/Definitions/NonGaloisDescent/RecTExists.lean` (line 77 read) | `dcda8fc275cc47fadff03b062e870ae83dd6cbeae43d774ac3b7fd6b5c78202a` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/SClose.lean` (lines 21-22 and 36-42 read) | `c07163b8d888afece5631e57c1ec901ab9dceb770ba60e69b57bf99a54744130` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/WeightsConj.lean` (lines 81-82 read) | `f990fcf0264e72e3f449f7feaae03c3fcd9cb7680ad3b40edebb999bdd84f1df` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/GalRepRankTwo.lean` (lines 40-58 and 133-146 read) | `b9f80734800ac23e3b71165628c6759df66c325cf27022617467e93bd12d01db` |
| `Development/AutomorphicArithmetic/Foundations/GaloisRepresentations/TypeConditions/GaloisAdmissibleOfRestrictedCmDatum.lean` (read whole) | `94f92952e917bc686e073e09fe9471bf0fa06b8754eeddb561dbe69b77be15ea` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/AdmissibleSevenRestrict.lean` (lines 18-28 read) | `569761444e2c9592256146d7ba70d6a52a621cdbd5a1cf300918875c27b7951c` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/CFacts.lean` (lines 40-62 read) | `6e8f8be134679aa1522ba1eac64346f40ce1c0d3a0d8806d37407316cd7e2fe9` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/LinkNFam.lean` (lines 39-53 read) | `bf49ec0e3809178eae0cde620bab3b8c0fd07a0fea5210a928f4519e310665fd` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/NOProd.lean` (lines 36-38 read) | `c0e013adf97ac0ba3a728bbd04828dd396ef169123c334ce4c29c1f4364970c2` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/PreAtMem.lean` (lines 89-103 read) | `59235430eabcc407ecf19981de0b06273135a1d89ecd266a2c848340ff5bcc49` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/FiniteTriplesSatisfyCondition.lean` (lines 21-29 read) | `cf354308de36b9d2be737c373254bab8c4853c8d8e37d8c840d22b32a4e12c02` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/GalLocTripleWithLocalization.lean` (lines 35-62 and 108-136 read) | `baf44e45286b304318c2703b1795145331224f95912d53d7976b9aa2897a65ea` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/GaloisRepsOfCgTrue.lean` (lines 44-66 read) | `3bd2bae3e4a533c0bed4a632bd19125c76ecfb46029635ed988f15ef184b7f18` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/UnrRecOfHasSat.lean` (lines 44-50 read) | `d200e0e2993e0c74d2e7ce0004904e424071581b8cefd89d043029f5e41ea79e` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/IsTripleOfSideBStatement.lean` (lines 16-17 read) | `d043f214c9c0987f8f7e0e205afcdd9ed36c25ee34a740fa451c694c6a5e9cbb` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/IsTripleOfSideB.lean` (lines 28-50 read) | `dbbb7511b8013e1b11659605e2ee61190fa60c1ee10fda786174e576bde6be59` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/IsTripleAtOfConj.lean` (lines 41-50 and 93 read) | `aa526702f8d616582faffdea6dbf82bd85656b839d85329e5bf116f07c7040ca` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/HkOfBuilt.lean` (lines 83-87 read) | `89a89620ec12c705effe6aff22e55f0d1a8cf4ce1c5813ff5152b34070a4de7c` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/GalSide.lean` (lines 19-29 read) | `b076ed9c479a05dae7202dd0d8f48cfaddab50a0f9d59e8d945e3b80c5901d47` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/SatakeIdentityOfIsTriple.lean` (lines 106-108 read) | `6882e361565837820f66e9cee8b27df51b2692df579118509500a6152f415260` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/ImportsFurtherTail.lean` (lines 22-26, 47-66 and 90-96 read) | `9aaa90b980a269a04441a7319558b3efb816c1453be2e346ef14d42e1e2799a3` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/ExistsSetupLargeStatement.lean` (lines 12-13 read) | `9aad4e069dcf4d1ba909a0d0fbaf386c39aa872b189bdf705afdab6058f79279` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/ExistsSetupLarge.lean` (lines 14-41 read) | `ef48825ffd19b12fceac9f941405c20b22e06ad821e633f8db2391441d7f7d1a` |
| `Development/AbelianVarietyTheory/Proofs/InertiaEigenvalues/PsiAtPsiAt.lean` (lines 23-33 read) | `7df1e12c10f68e96b86a8a10a3ccc0c8279e3b5ccf7a7a6d385908bf2227a08c` |
| `Development/AbelianVarietyTheory/Proofs/InertiaEigenvalues/SameCharEqOne.lean` (lines 27-42 and 66-74 read) | `f08ed1c16553486eeac98581d5eec9c0e446a38d709b4960126e10911bff8d46` |
| `Development/AbelianVarietyTheory/Definitions/NonGaloisDescent/BoundAtTwoAndThreeForFamily.lean` (lines 18-25 read) | `6b83cc632a3b8fb2e0ae85b8fd8cf84de7ff1d04a7f66062cee41391177fd9d4` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/EveryCharacterOfLiteratureOfVWin.lean` (lines 213-219 and 655-666 read) | `246b74eeb03dae250c45b46c155b3590cb53c2bac86f5e35f4b74338db487068` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/SatakeIdentityOfIsTriple.lean` (lines 24-32 and 77-105 read; added with the Addition of 2026-11-23) | `6882e361565837820f66e9cee8b27df51b2692df579118509500a6152f415260` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/IsTripleAtOfConj.lean` (lines 66-80 and 89-94 read; added with the Addition of 2026-11-23) | `aa526702f8d616582faffdea6dbf82bd85656b839d85329e5bf116f07c7040ca` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/CompatibleSystemTripleLayerInputs.lean` (line 54 read; added with the Addition of 2026-11-23) | `fc218db7864b430d14497506b50fae07aecb8c5a5189a3d426085c0250997a53` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/GaloisInputs.lean` (lines 19-29 read; added with the Addition of 2026-11-23) | `725797f6c8f825349fd8fdb8b35a31ed939cfa4d24fdd4fe7d4fb34520955e76` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/Adm2OfIsTriple.lean` (lines 86-89 read; added with the Addition of 2026-11-23) | `c6d9eb2e56929a5957dc3887bdd38e0f615b557975bdee4fba4edf436ab3076d` |
| `Development/AbelianVarietyTheory/Proofs/InertiaEigenvalues/ExistsGaloisSide.lean` (lines 35-61 read; added with the Addition of 2026-11-23) | `84e611444a10ff82ef6b607962e249c0dc25c4ea568856216bae60c3b97bd66d` |
| `Development/AbelianVarietyTheory/Definitions/NonGaloisDescent/CharpolySmulOfProd.lean` (lines 420-422 read; added with the Addition of 2026-11-23) | `be2c5fc0e7e21254681bac1e77e7f532eae2e44afab00d7e3eae6227ec692ae7` |
| `Development/AbelianVarietyTheory/Proofs/InertiaEigenvalues/MemMaximalIdealIff.lean` (lines 368-369 read; added with the Addition of 2026-11-23) | `b721a1e3d6b4fef7e00eb6b42fe62dfd58b98c36f8dc8432c279761999c7ea4b` |
| `Development/AbelianVarietyTheory/Proofs/InertiaEigenvalues/SetHypOfIsTripleOfGalHodge.lean` (line 27 read; added with the Addition of 2026-11-23) | `964f965c508d705df6b09f2926b1bc689bcb1596a781d14d64f876dfc44aadfb` |
| `Development/AbelianVarietyTheory/Proofs/InertiaEigenvalues/LinkOfClosedAtFamily.lean` (lines 68-70 read; added with the Addition of 2026-11-23) | `c02daab71ab9b06641e2ee80619d5dcdd8e6f0f979624fa8c3743fefddee8f67` |
| `Development/AbelianVarietyTheory/Proofs/SatakeParameters/FactsAtMembershipStatement.lean` (lines 14-15 read; added with the Addition of 2026-11-23) | `addc941dc62761c282826e3791143a627c3f757e88016e6b05157e852fc72624` |
| `Development/AbelianVarietyTheory/Proofs/DivisorProofs/NonemptyHypsOfPublishedUE.lean` (lines 30 and 36 read; added with the Addition of 2026-11-23) | `5e5b726c75a4cb71c8004b161839d4fc27972ff6aad6aaceebd534e28759e411` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/FockModels/EveryCharacterE.lean` (lines 41 and 65-67 read; added with the Addition of 2026-11-23) | `87518b975cbf7675d19cc619bf7422c43d7e2f010f6769d2b8ec1b9e852ca6d1` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/HypothesesNonemptyOfUnramifiedExponents.lean` (line 47 read; added with the Addition of 2026-11-23) | `80ebd1ee514d8a6a7967fe3e87c775148615416906038a046b27ea9436a2cc1f` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/SiegelEisensteinSecondTermHypotheses.lean` (lines 68-69 read; added with the Addition of 2026-11-23) | `e761e876e3236895eec1b67b5a2118846ddfcc6883eed367ac6cc78523da15f2` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/EveryCharacterOfLiteratureOfVWin.lean` (line 811 read; added with the Addition of 2026-11-23) | `246b74eeb03dae250c45b46c155b3590cb53c2bac86f5e35f4b74338db487068` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/CFinal.lean` (lines 19-22 read; added with the Addition of 2026-11-23) | `53c72d83f0f9e917ac29fd1adf2165abb0d307d48e4ba0b4c9568bd881b27d24` |
