# 14. Where `LinkN` comes from

*Written by Halley, 2026-11-22. Read whole by Kepler before it was published. Everything marked **What the library says** was read in the files listed at the end, at the lines the table gives. This note works at the depth of statements: it follows one chain of theorems and reads the short proofs on it, and it says which proofs were not read. The lean blocks were cut from the source by line range with a script. Nothing was compiled. Nothing here has been checked by a mathematician.*

## In short

[Note 13](13-how-the-sha-bound-is-used.md) found that the Tate–Shafarevich bound `HypV` is spent in one inequality, through a link called `LinkN`. In the shape theorem of that note, `LinkN` arrives as a hypothesis, the field `nRest` of the third input ([note 4](04-the-third-input.md)). Note 13 could not say where it comes from on the path from `Main.lean`. This note follows it.

- **`LinkN` is proved, not assumed.** On Main's path it is derived from a bundle of statements called `NLink.Hypotheses₂`, from three local statements about Galois cohomology (named local finiteness, local Tate duality and local Euler characteristic), and from a proved bound, `stmtU_holds`.
- **Those local statements are library theorems, and so are all seven fields of `NLink.Hypotheses₂`.** The bundles that deliver them are named for the literature, but each is filled by a theorem of the library whose term does not use the literature bundle.
- **The two steps that carry the Tate–Shafarevich total never bound it.** They carry it through unchanged, as a summand. So the only bound on that total on Main's path that we have found is the one note 13 found.
- **One literature statement does enter.** The theorem that turns a bound into `LinkN` takes as a hypothesis the existence statement `RecTExists`, which is one of the three fields of the literature bundle of note 2.

## What the library says

### Step 1: the third input is built from a different bound

`Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/SiegelEisensteinSecondTermHypotheses.lean`, lines 69-73, is the theorem on Main's path that calls note 5's `every_character_of_green_v_win`:

```lean
theorem every_character_of_theta_integrals_local_matching (P : _root_.GlobalTheory.Fc.S0.UnitaryGroupThirdPlaceHypotheses) (F : _root_.GlobalTheory.FunPr.ThetaLocalInputs) (hA : GlobalTheory.IndefiniteRowSideFullHecke.WeilTensorModels.ThetaIntegralsAgree)
    (hM : GlobalTheory.IndefiniteRowSideFullHecke.WeilTensorModels.LocalMatching) (hX : _root_.GlobalTheory.CovTop.CovolumeBoundOfX) (hL : _root_.UpperTheory.Zero.LLC.RecTExists) (hV : VWin) :
    UpperTheory.EveryCharacter :=
  _root_.UpperTheory.Top.every_character_of_green_v_win (GlobalTheory.GreenBridge.green_of_regular P.greenRegularCharacters) hV
    (_root_.UpperTheory.Lit.nonempty_hyps_definite_side_of_closed_bound P F hA hM hX hL fun cDep => _root_.UpperTheory.N.boundAtTwoThree_linked_of_recT P.nLink (_root_.GlobalTheory.Mem.Top.Bl.parametersOfDependence hL cDep))
```

The third argument is the non-emptiness of the 46-field structure of note 4. It is built by `nonempty_hyps_definite_side_of_closed_bound` (line 44 of the same file), and the closed statement handed to it is not `LinkN`. It is a bound called `BoundAtTwoThreeFamilyFonAlt`, produced from `P.nLink` by `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/At23OfAll.lean` (28 lines, read whole). That file proves the bound for every family, not only for large ones (`closed_of_all`).

Two remarks on what this argument list contains. The hypothesis `hV`, which is `VWin` (note 3), goes to `every_character_of_green_v_win` and **not** into the construction of the third input. And `P` is the bundle `UnitaryGroupThirdPlaceHypotheses`, whose last fields include `nLink`, `localFiniteness`, `localTateDuality` and `localEulerChar`.

### Step 2: from that bound to `LinkN`

Inside the construction, `hypotheses_nonempty_of_unramified_exponents_alt` turns the bound into the closed statement about `LinkN` (`Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/HypothesesNonemptyOfUnramifiedExponents.lean`, lines 47-48):

```lean
  have hNrow := _root_.UpperTheory.GalC.final_alt_alt P.nLink prN P.toHypothesesX serN P.depthZeroSupport'
    P.localFiniteness P.localTateDuality P.localEulerChar hL cDep hN
```

`final_alt_alt` (`Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/CFinal.lean`, line 19) proves a statement (`NLink.Final.mainTheorem`, `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/MainTyzTer.lean` line 22, one long line not quoted here) whose hypotheses are, in order, `NLink.Hypotheses₂`, four further bundles (`PublishedInputsThirdLayerAlt`, `GeometricGaloisRepCompatibility`, `SerN`, `DepthZeroSupport`), local finiteness, local Tate duality, local Euler characteristic, then, for every `hL : RecTExists` and every real `cDep`, the bound of step 1; its conclusion is the same closed statement with `LinkN` in place of the bound.

**This is where the literature enters the chain.** `RecTExists` is the type of the field `localLanglandsExists` of `OpenLiteratureStatements` (literature file, line 217), one of that bundle's three fields. On the path, `hL` is that existence statement; it also enters step 1, through `parametersOfDependence hL cDep` (line 73 above). We have not read what `RecTExists` states. The result `hNrow` is then passed on as `S0.NL`, the closed statement about `LinkN` (lines 52-56 of the same file). We read those lines for its uses only and did not follow it into the field `nRest`.

### Step 3: one member at a time, through a cut

`final_alt_alt` reaches, through three short theorems in `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/LinkNFam.lean` (read whole), the theorem that does the work for one family:

```lean
theorem linkN_of_twGood_galoisPreconditions (hP : Hypotheses₂) (hG : _root_.UpperTheory.GalC.CutGivesAlt) {eps : ℝ} (Fm : FamP eps) (hTw : TwGood Fm)
    (hF : ∀ (x : ℝ) (hx : Fm.x1 < x) (i : Fm.Ix x), _root_.UpperTheory.GalC.GaloisPreconditions (Fm.D x i) (Fm.ex x hx i).nch ∧ Tie4 (Fm.D x i)) : LinkN Fm := by
```

Its proof (lines 39-53) chooses, for each member of the family, a **cut**: a sub-datum `c` that is "good" and keeps the facts the proof needs. The cut is supplied by a statement `CutGivesAlt`, which `final_alt_alt` proves from the local finiteness, local Tate duality and local Euler characteristic hypotheses, with one further input (`exists_good_cut_facts_tie4 prN.cheb lf ltd lec`, line 21; not read). The proof then ends:

```lean
  refine linkN_of_gd Fm c (fun x hx i => ⟨(hc x i hx).1, ?_, (hF x hx i).1.what₂.rank _⟩)
    (GlobalTheory.T.linkN_along_family_of_localBounds _ (_root_.GlobalTheory.T.conclF_of_family_facts_and_bound_at_two_three hP _ C CT hC (twGood_gd Fm c hTw) hFF (_root_.UpperTheory.N.at23_family_alt hP _)))
```

So `LinkN` for the family follows from `LinkN` for the cut family `gd Fm c`, and that comes from a theorem about local bounds. The passage from the cut family back is `linkN_of_gd` (`Development/AutomorphicArithmetic/Foundations/GaloisRepresentations/HeckeGaloisCriteria/LinkNOfGd.lean`):

```lean
theorem linkN_of_gd (Fm : FamP eps) (c : ∀ x (i : Fm.Ix x), CutD (Fm.D x i))
    (hc : ∀ x, Fm.x1 < x → ∀ i, (c x i).Good ∧ GlobalTheory.NLink.MultLe (Fm.L x i) ∧ TwistedPlaces.adm3 (Fm.L x i))
    (h : LinkN (gd Fm c)) : LinkN Fm := by
```

Its proof (lines 41-93, read whole) is arithmetic. It takes the inequality for the cut family, compares each local term of the family with the cut's (`etaJ_le`), adds one term (a logarithm of the size of a finite group, which it bounds by the analytic part), and regroups.

### Step 4: the inequality itself

`linkN_along_family_of_localBounds` is, by its proof, the theorem `GlobalTheory.LinkFam.main` (`Development/AbelianVarietyTheory/Proofs/InertiaEigenvalues/LinkNAlongFamilyOfLocalBounds.lean`, read whole):

```lean
theorem main : ∀ {eps : ℝ} (Fm : FamP eps), ConclF Fm → Formalism.MainNotions.LinkN Fm := by
  intro eps Fm hC
  obtain ⟨C, x0, h⟩ := hC
  have hA : Formalism.MainNotions.TwistedPlaces.AdmF Fm := ⟨C, x0, fun x hx hx1 i hS => by
    obtain ⟨X, hX⟩ := h x hx hx1 i hS
    exact GlobalTheory.T.admittedStatements_of_localBoundsConclusion_alt _ _ _ X C hX⟩
  exact Formalism.MainNotions.N.linkN_of Fm hA (Formalism.MainNotions.TwistedPlaces.stmtF_holds Fm)
```

`linkN_of` (`Formalism/SharpRestriction/LevelLetterCocycles/ThetaScalarFamilyOfEigenvalue.lean`) only changes the name of the statement:

```lean
theorem linkN_of {eps : ℝ} (Fm : FamP eps) (hA : Formalism.MainNotions.TwistedPlaces.AdmF Fm) (hS : Formalism.MainNotions.TwistedPlaces.KudlaFamilyStatement Fm) :
    LinkN Fm := export_link_of_family Fm (hS hA)
```

`export_link_of_family` (line 30 of the same file) unfolds `LinkN` into the form `aux₃`, and `export_link_iff_family` (line 37) shows the two are equivalent. The content is in `stmtF_holds`, which is proved from `stmtU_holds`. The definitions it rests on are in `Formalism/SharpRestriction/LevelLetterCocycles/StatementFamilies/ExportFamilies.lean`:

```lean
def OrbitValuationBound {eps : ℝ} (Fm : FamP eps) : Prop := ∃ C x0 : ℝ, ∀ x ≥ x0, ∀ i : Fm.Ix x, aux₃ (Fm.L x i) C

def AdmFC {eps : ℝ} (Fm : FamP eps) (C : ℝ) : Prop :=
  ∃ x0 : ℝ, ∀ x ≥ x0, ∀ (hx : Fm.x1 < x) (i : Fm.Ix x), admitted (Fm.L x i) (Fm.params x hx i) C

def AdmF {eps : ℝ} (Fm : FamP eps) : Prop := ∃ C : ℝ, AdmFC Fm C

def KudlaFamilyStatement {eps : ℝ} (Fm : FamP eps) : Prop := AdmF Fm → OrbitValuationBound Fm

def UniformExportStatement (eps : ℝ) : Prop := ∀ Ca : ℝ, ∃ C : ℝ, ∀ Fm : FamP eps, AdmFC Fm Ca → FamilyThinScalesBound Fm C
```

`stmtU_holds` (`Formalism/SharpRestriction/LevelLetterCocycles/ExportBoundOfAdmissible.lean`, line 1141) proves `UniformExportStatement eps` with the explicit constant C = 2000·(|Ca| + 1)³. Its proof (lines 1142-1158) waits until x is large and applies, member by member, the theorem that assembles the `LinkN`-shaped inequality:

```lean
theorem export_bound_of_admissible (P : ParameterChoice' D L) {C : ℝ} (hL : Large L.sc.x L.sc.eps C) (hAdm : admitted L P C) :
    aux₃ L (2000 * (|C| + 1) ^ 3) := by
  classical
  intro hSha hsumm j hj
```

Its body (lines 1027-1053, read whole) is an assembly of two lemmas. `etaSum_le` (line 1032) bounds the weighted local sum by dZ0·(local terms) + dZ0·(the Tate–Shafarevich total); **this is where the total enters the inequality**. `point_bound` (line 1039) bounds the local terms by the analytic size. The rest is `gcongr` and `ring`. The premise `hSha` is used once in the body, to obtain the admissibility data (`hAdm hSha`, line 1027); the summability `hsumm` is what is passed to `etaSum_le` (line 1032), together with the admissibility data.

The module `ExportBoundOfAdmissible` has an import closure of **369 modules** out of 175,187 in the release, measured with Kepler's `import_closure.py` (note 7's method). Its file is 1,164 lines long.

### Where the inputs come from

On Main's path the bundle `P` is built in `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/EveryCharacterOfLiteratureOfVWin.lean`. Its last fields:

```lean
  nLink := (_root_.UpperTheory.LiteratureTheorems.published_results_local O)
  depthZeroSupport' := (_root_.UpperTheory.LiteratureTheorems.depth_zero_support_of_literature O)
  localFiniteness := (_root_.UpperTheory.LiteratureTheorems.local_finiteness_of_literature O)
  localTateDuality := (_root_.UpperTheory.LiteratureTheorems.local_tate_duality_of_literature O)
  localEulerChar := (_root_.UpperTheory.LiteratureTheorems.localEulerChar_alt_alt O)
```

The three local statements are theorems of the library. Each takes the literature bundle `O` as an argument and does not use it:

```lean
theorem UpperTheory.LiteratureTheorems.localEulerChar_alt_alt (O : _root_.UpperTheory.LiteratureTheorems.OpenLiteratureStatements) : ReciprocityTheory.Gal.LocalEulerChar :=
  GlobalTheory.Laid.loceuler_holds
theorem UpperTheory.LiteratureTheorems.local_finiteness_of_literature (O : _root_.UpperTheory.LiteratureTheorems.OpenLiteratureStatements) : ReciprocityTheory.Gal.LocalFiniteness :=
  GlobalTheory.Laid.locfin_holds
theorem UpperTheory.LiteratureTheorems.local_tate_duality_of_literature (O : _root_.UpperTheory.LiteratureTheorems.OpenLiteratureStatements) : ReciprocityTheory.Gal.LocalTateDuality :=
  GlobalTheory.LocalDualityAll.localTateDuality
```

`NLink.Hypotheses₂` (`Development/AbelianVarietyTheory/Definitions/NonGaloisDescent/BoundAtTwoAndThreeForFamily.lean`) has seven fields:

```lean
structure Hypotheses₂ : Prop where
  font : GlobalTheory.Published.FontaineBcris
  artin : GlobalTheory.Published.GlobalArtinReciprocity
  bk : GlobalTheory.Published.BlochKatoLocal
  tate : Formalism.GaloisCohomology.LocalTateDualityK
  euler : Formalism.GaloisCohomology.LocalEulerCharK
  fin : Formalism.GaloisCohomology.LocalFinitenessK
  bs : GlobalTheory.Published.BhattScholzeIntegral
```

On the path it is `published_results_local O` (lines 658-665 of the literature file). **All seven of its fields are filled by library theorems whose terms do not mention `O`.** Three of them:

```lean
theorem UpperTheory.LiteratureTheorems.local_euler_char_k_of_literature (O : _root_.UpperTheory.LiteratureTheorems.OpenLiteratureStatements) : Formalism.GaloisCohomology.LocalEulerCharK :=
  CompanionTheory.LocalTateOrthogonality.Gcoh.top_euler
theorem UpperTheory.LiteratureTheorems.local_finiteness_k_of_literature (O : _root_.UpperTheory.LiteratureTheorems.OpenLiteratureStatements) : Formalism.GaloisCohomology.LocalFinitenessK :=
  CompanionTheory.LocalTateOrthogonality.Gcoh.top_locfin
theorem UpperTheory.LiteratureTheorems.local_tate_duality_k_of_literature (O : _root_.UpperTheory.LiteratureTheorems.OpenLiteratureStatements) : Formalism.GaloisCohomology.LocalTateDualityK :=
  CompanionTheory.LocalTateOrthogonality.Gcoh.top_tate
```

The other four, read by Kepler and by me: `artin` := `GlobalTheory.globalArtinReciprocity_holds` (lines 243-244), `bs` := `GlobalTheory.BSP.bhattScholzeIntegral` (267-268), `bk` := `UpperTheory.Lit.blochKatoLocal` (271-272), `font` := `GlobalTheory.MemLoc.fontaineBcris` (379-380). What we read is that the term does not mention `O`. What those library theorems state, and what they rest on in turn, we have not read; a statement named after a published theorem need not state that theorem.

The bundle `OpenLiteratureStatements` itself has three fields:

```lean
  caraianiLocalGlobalDual : _root_.UpperTheory.One.M.Row
  localLanglandsExists : _root_.UpperTheory.Zero.LLC.RecTExists
  galoisRepOfPolarizedPairLit : _root_.UpperTheory.One.M.Row
```

The local statements are stated in `ReciprocityTheory/Hypotheses/GalCoh.lean`. Local Tate duality, as the library states it:

```lean
def LocalTateDuality : Prop :=
  ∀ (F Ω : Type) [Field F] [NumberField F] [Field Ω] [Algebra F Ω] [IsAlgClosure F Ω] (l : ℕ) [Fact l.Prime] (r : ℕ) (M : Type) [AddCommGroup M]
    [Module (ZMod (l ^ r)) M] [Finite M] [TopologicalSpace M] [DiscreteTopology M]
    (A : ValuationSubring Ω) (rho : Representation (ZMod (l ^ r)) (Dec (F := F) A) M)
    (v : HeightOneSpectrum (𝓞 F)), LocalTateDualityAt A rho v
```

It quantifies over number fields F, primes l, finite l^r-torsion modules M with a Galois action, and places v, and asks a predicate `LocalTateDualityAt` at each, which we have not read. The folder is named `Hypotheses`, but that is only where the statement is written down. Whether it is assumed or proved is decided where the bundle is filled, and there it is proved.

### The Tate–Shafarevich total on this chain

`LinkN`'s statement (note 13) has the Tate–Shafarevich total Σ_l vvTerm as a summand of its upper bound, and finiteness (`ShaFinOdd`) and summability of that total as premises. On this chain:

- `export_bound_of_admissible` takes the finiteness and summability as the premises `hSha` and `hsumm` of the statement it proves (line 1026 above). The term (dZ0 j)·Σ_l vvTerm enters with `etaSum_le` (line 1032) and is carried unchanged to the final rearrangement (lines 1047-1053); nothing in the body bounds it.
- `linkN_of_gd` carries the same total, for the same datum, from the cut family's inequality to the family's, unchanged.

So the chain proves the inequality **with the total left in it**. The premises are discharged where `LinkN` is used: there `vvRecord` supplies finiteness, summability and the bound from `HypV` (note 13).

## Interpretation (ours; check it)

- **Note 13's "used once" stands on this side.** The two steps of this chain that carry the Tate–Shafarevich total were read, and neither bounds it. *This is not a proof that nothing on the chain bounds it.* A script I wrote, an instrument without a control, followed names from `linkN_of_twGood_galoisPreconditions` through the release and reached 21,402 declarations, none of which mentions `VVle`, `VVminusLe`, `VVplusLe`, `HypV`, `VWin`, `VWinAt`, `vvRecord`, `LinkV`, `Vbound` or `BoundedHeightTwoPlaceCondition`. But a search by name cannot follow every reference (it skipped 1,003 names it could not resolve to one or two declarations), so this is a lower bound on what the chain uses, not the whole of it.
- **Where the arithmetic of `LinkN` sits.** The inequality is assembled in `export_bound_of_admissible` from two lemmas: `etaSum_le`, where the Tate–Shafarevich total enters, and `point_bound`, which supplies the analytic size. *A reading of where the arguments go, with neither proof read:* `final_alt_alt` (line 21-22) passes the local finiteness, Tate duality and Euler characteristic hypotheses to two places, `exists_good_cut_facts_tie4` (the cut) and `galois_preconditions_at_mem` (the Galois preconditions on members), and not to the export bound. On this reading, local duality does not produce the inequality; it prepares the sub-datum and the preconditions on which the inequality is proved.
- **Note 13's guess.** Note 13 guessed, from the shape of one inequality, that `LinkN` is a local–global duality count. The names on this chain (local Tate duality, local Euler characteristic, local finiteness) are the names of the local half of such a count. That is support by name only. The lemma the guess is really about is `etaSum_le`, where the total enters; we have not read it, nor `LocalTateDualityAt` or `CutGivesAlt`'s proof.

## Not read, not understood

- **Proofs not read:** `etaSum_le` and `point_bound`, the two lemmas where the content of `export_bound_of_admissible` is (its own body was read whole); `exists_good_cut_facts_tie4` and `galois_preconditions_at_mem` (where the local statements are used); `conclF_of_family_facts_and_bound_at_two_three`, which is `GlobalTheory.NLinkClose.main_alt_alt`; `admittedStatements_of_localBoundsConclusion_alt`; `Laid.locfin_holds`, `Laid.loceuler_holds`, `LocalDualityAll.localTateDuality`, the three `Gcoh.top_…` theorems and the four theorems filling `font`, `artin`, `bk`, `bs`.
- **Definition not read:** `RecTExists`, the literature statement that enters in step 2.
- **Definitions not read:** `LocalTateDualityAt`, `LocalEulerCharAt`, `LocalFinitenessAt`, `CutD` and what makes a cut good, `aux₃` beyond its use as `LinkN`'s shape, `FamilyThinScalesBound`, `admitted`.
- **Sources not opened:** we cite no reference for local Tate duality or the local Euler characteristic formula. The names here are the library's.

### Correction, 2026-11-22 (later the same day): four more inputs, and all three literature statements reach them

*Found by Halley while checking Kepler's summary of this note for note 13; read whole by Kepler before it was published. The body above is unchanged.*

The first and fourth bullets of "In short" said less than the chain holds. `NLink.Final.mainTheorem` (step 2) takes four further bundles besides `NLink.Hypotheses₂` and the three local statements, and the first version of this note traced none of them. On Main's path:

- `DepthZeroSupport` is filled by a library theorem whose term does not use the literature bundle (`depth_zero_support_of_literature O := GlobalTheory.SmGL.depthZeroSupport`, literature file lines 351-352).
- `GeometricGaloisRepCompatibility` is `published_results_analytic O` (lines 645-651), whose six fields come from theorems we have not opened.
- `PublishedInputsThirdLayerAlt` and `SerN` (`prN` and `serN` in step 2) come from `GlobalTheory.MemberClose.exists_hyp_n_of_geometric_galois_compat`, which takes the bundle `litN`. It passes the parts `loc` and `aut` of `litN` to `localLanglandsGL_and_purity_at_member_alt` (the call is at line 28 of `ThetaLiftHypothesesOfNonvanishing.lean`), which passes `A.gk`, `A.gal` and `A.car` by name (line 25 of `LocalLanglandsGLAndPurityAtMember.lean`) to `GlobalTheory.NRows.HypothesesBridge.locComp_of_isRc_classMapD_cenLoc`. There the hypotheses in those positions (11th: `PairUAlt`; 12th: `One.M.Row`; and the 20th, `RecTExists`) are used to build two fields of the result:

```lean
      gal := hCSD.2 hGRP
      car := _root_.UpperTheory.GalS.carU_of_finite_gl_recT hFin hLL (hCSD.1 hCLGD)
```

That result is the field `what₂` of `prN`, a record with thirteen other fields.

**So all three literature statements reach the inputs of the theorem that produces `LinkN`:**

- `RecTExists` (`localLanglandsExists`), as a hypothesis of that theorem (step 2); again through `prN.what₂.gal`, whose term `pair_u_of_literature O` takes `local_langlands_recT_exists_of_literature O` as its first argument (line 286); and again through `prN.what₂.car`: the `RecTExists` used there (`hLL`, the twentieth argument) is produced at lines 20-21 of `LocalLanglandsGLAndPurityAtMember.lean` by `recTExists_of_published_inputs` (`LocalLanglandsOfHyp.lean`, line 12; its proof not read) from fields of the local bundle `loc`, the first of which, `llc`, is again `local_langlands_recT_exists_of_literature O` (literature file line 603, in `literature_local`, which fills `litN.loc`, line 640);
- `caraianiLocalGlobalDual`, through `prN.what₂.car` (`aut.car := O.caraianiLocalGlobalDual`, literature file line 618);
- `galoisRepOfPolarizedPairLit`, through `prN.what₂.gal` (`aut.gal := pair_u_of_literature O`, line 617, whose term ends in `O.galoisRepOfPolarizedPairLit`, line 286).

*Whether the proof of `LinkN` reads these fields of `prN` is not read.* `final_alt_alt` passes `prN` to `galois_preconditions_at_mem` and `prN.cheb` to `exists_good_cut_facts_tie4`, and we have read neither proof.

**One use is visible, read by both of us.** The same theorem that returns `prN` also builds an `EllipticHypothesis` from it (`ThetaLiftHypothesesOfNonvanishing.lean`, lines 42-43): `e22 := hPr.what₂.gal` copies the field that carries `galoisRepOfPolarizedPairLit`, and `e24 := local_global_above_ell_of_cusp_alt hPr.what₂` passes `what₂` whole to a theorem we have not read. Where that goes on Main's path: in the theorem that builds the `LinkN` row this first output is discarded (`obtain ⟨_, prN, serN, _⟩`, line 44 of `HypothesesNonemptyOfUnramifiedExponents.lean`). But line 43 of the same theorem calls `large_unramified_exponent_bundles_exist_alt`, which is `member_bundles_large_unramified_exponents_alt` (`MemberBundlesLargeUnramifiedExponents.lean`, line 34). That theorem calls the same producer again, keeps the `EllipticHypothesis` (`obtain ⟨hE, -, -, hL', hN⟩`, line 59) and passes it to `member_exists_baseLattice_alt` (line 61), whose proof we have not read. So on Main's path the `EllipticHypothesis` that carries this field is handed to a theorem used in building the third input. By our own rule that is carrying, not use: whether `member_exists_baseLattice_alt` reads `e22`, and whether any of this reaches `nRest`, we have not read.

**Why we think these are all the places the statements leave the bundle.** In the literature file the bundle's fields are taken out at exactly four lines: 284 (`localLanglandsExists`), 286 (`galoisRepOfPolarizedPairLit`), 460 (`caraianiLocalGlobalDual`, in `carU_local_global_of_literature`, line 459, whose only use in the tree, by whole-word search, is line 462 inside `carU_above_l_of_literature`, which fills the field `localGlobalAboveL` of `P`, line 688; whether that reaches this chain is not traced) and 618 (`caraianiLocalGlobalDual`, in `aut.car`). The structure's name `OpenLiteratureStatements`, as a whole word, occurs in that one file only. Kepler established both: the four lines by name search plus a search for numeric and pattern-matching projections (with a positive control), and the one-file count by a whole-word search. Halley traced the chain above. *Limit:* a term defined elsewhere that receives the bundle whole under another binder type would not show in these searches; with the type named in one file only, we do not see how that could happen, and we have not proved it cannot.

**What the first and fourth bullets should read.** First: "... and from a proved bound, `stmtU_holds`, and from four further bundles: one filled by a library theorem, three not fully traced." Fourth: "All three literature statements reach the inputs of the theorem that produces `LinkN`, `RecTExists` also as its hypothesis; whether the proof of `LinkN` uses them beyond that is not read."

*On the twin.* Three declarations in the release share the short name `locComp_of_isRc_classMapD_cenLoc`. The one this chain cites is the full name given above, in `PublishedInputsCombined.lean`; Halley first opened another (in `ConductorValuationDeltaComparison.lean`) and re-read. The file table at the end lists each file by full path and hash, the rows added with this correction marked as such.

### Clarification, 2026-11-23: where local duality is used, and what the member preconditions read

*Found by Halley reading the two proofs this note listed as not read (`galois_preconditions_at_mem` and `exists_good_cut_facts_tie4`), and the chain below them; read by Kepler before it was published. The body above is unchanged. Instrument for every "is not used" below: a count of each bound name's occurrences in the proof's source lines, with the other bound names of the same proof as the control (each of them shows a use). Lean was not run. Nothing here has been checked by a mathematician.*

**The sentence in "Interpretation" that this changes.** It reads: "On this reading, local duality does not produce the inequality; it prepares the sub-datum and the preconditions on which the inequality is proved." The first half stands. The second half is half wrong: local duality prepares the facts of the cut (the sub-datum); it does not prepare the preconditions on members.

**The member branch carries the three local statements and does not use them.** `final_alt_alt` passes `lf ltd lec` to `galois_preconditions_at_mem` (`CFinal.lean`, line 22). That theorem passes them on in one place only, line 95 of `PreAtMem.lean`:

```lean
  have core : _root_.UpperTheory.GalS.Core0Alt (w.D Z) := _root_.UpperTheory.GalS.core0_of_local_duality_inputs prn.what₂ prn.hc prn.decay dzs lf ltd lec hL (w.D Z) I jumps
```

`core0_of_local_duality_inputs` takes them as `hF hT hE` (line 56):

```lean
  intro hP hc hd hs hF hT hE hL D I hJ
```

and its proof (lines 57-85) never names `hF`, `hT` or `hE` again. The only tactic in that proof that reads hypotheses it is not given by name is `omega`, at lines 70-71, on goals about natural numbers. Despite its name, this theorem does not use local duality.

**What the member branch does read: three fields of `prN`.** The same line 95 passes `prn.what₂`, `prn.hc` and `prn.decay`. Inside `core0_of_local_duality_inputs`, `prn.what₂` (bound as `hP`) goes to `theta_conditions_of_inputs_of_jumpsCard` (line 57), whose result becomes the field `what₂` of the preconditions; `hP.fin` goes to `MuUnrTie.main_alt_alt` (line 82); and `hP` goes to `depthZeroG_of_rowMod` (line 83). `galois_preconditions_at_mem` also passes `prn` whole to three theorems (lines 90-91). We have read none of these proofs.

**What the proof of `LinkN` reads from the preconditions.** In `linkN_of_twGood_galoisPreconditions` (`LinkNFam.lean`), the preconditions `(hF x hx i).1` are handed to the cut (line 44), and five of their fields are read directly:

```lean
  refine linkN_of_gd Fm c (fun x hx i => ⟨(hc x i hx).1, ?_, (hF x hx i).1.what₂.rank _⟩)
```

```lean
  exact GlobalTheory.T.goodPointMultiplicityLeRank_proof _ _ p.Conclusion1.2.2 p.z p.adm.2.2 p.c2
```

**So the correction's open line has a partial answer.** The correction above said: "Whether the proof of `LinkN` reads these fields of `prN` is not read." It does read `prN.what₂`, at one remove: `prN.what₂` is the input of the theorem that builds the field `what₂` of the preconditions, and line 50 reads that field. Whether the literature statements inside `prN.what₂` are used by `theta_conditions_of_inputs_of_jumpsCard`, or only carried by it, we have not read.

**The cut branch uses local duality, once, for a vanishing of local cohomology.** `final_alt_alt` passes `lf ltd lec` to `exists_good_cut_facts_tie4` (`CFinal.lean`, line 21), which passes them on in one place (`CFacts.lean`, line 62):

```lean
  exact ⟨c, hc, _root_.UpperTheory.GalC.facts_of_galois_preconditions_of_cutRec hCh lf ltd lec (_root_.UpperTheory.GalC.pre_cut_alt hc h) (cutRec_cut hc), compatibilityTies_eigenRestriction c hT⟩
```

`facts_of_galois_preconditions_of_cutRec` passes them on in one place (line 52), to `prvG5_of_admissible_cutRec`, which uses them at line 33 of `AdmissibleJOfRestricted.lean`:

```lean
  have hH : HOneTwo D := GlobalTheory.T.hOneTwo_of_localFiniteness_tateDuality_eulerChar h1 h2 h3 D
```

and uses `hH` at line 44. `hOneTwo_of_localFiniteness_tateDuality_eulerChar` is one tactic line that applies `HOneTwoLevel.hOneTwo_holds` (`H1H2LocalDualityStatement.lean`, line 8). In `hOneTwo_holds` (`H1H2LocalDuality.lean`, lines 149-217) the three statements are named at line 150 and once more, at line 212:

```lean
  have key := GlobalTheory.T.localCohomology_vanishes_tame_inertia_no_fixed hF hT hE D.host.E D.nd.Om (D.nd.l i)
```

What `hOneTwo_holds` proves, read from its statement, its last lines and the definition of `HOneTwoZero` (`ExistsInertiaCharpolyFactorOfTameType.lean`, lines 1471-1477): at a place `w` in the set `S`, when the twisted residual representation has no fixed vector under one chosen element (the bijectivity `hbij`, lines 198-211), the groups the library calls `H1` and `H2` of that representation, restricted to the decomposition group at `w`, have at most one element (line 217). This is a real use. `final_alt_alt` hands the three statements to two theorems (lines 21 and 22); below it, on the cut branch, each proof we read has exactly one consumer of them, so on that branch they enter `LinkN` once, here. *Not read:* the proof of `localCohomology_vanishes_tame_inertia_no_fixed`, and the library's definitions of `H1` and `H2`.

**What the interpretation sentence should read.** "On this reading, local duality does not produce the inequality; it prepares the cut, through the vanishing of `H1` and `H2` of local representations at the places in `S` (`hOneTwo_holds`). The member preconditions are built without it."

**Files added with this clarification** are marked in the table below.

### Addition, 2026-11-23 (later the same day): two of the three statements are used, local finiteness is carried

*Found by Halley reading the one proof the Clarification above left unread; read by Kepler before it was published. The text above is unchanged. Lean was not run.*

**What the Clarification said too broadly.** It called line 212 of `hOneTwo_holds` "a real use" of the three statements. That is true of two of them. `localCohomology_vanishes_tame_inertia_no_fixed` is one tactic line that applies `tame_vanish` (`LocalCohomologyVanishesTameInertiaNoFixed.lean`, lines 20-60). `tame_vanish` takes the three statements in its first line, and binds local finiteness as an underscore:

```lean
  intro _ hTD hEC F Ω _ _ _ _ _ l _ M _ _ _ _ _ A v rho hA hl hrho hex
```

An underscore has no name, so the proof cannot refer to local finiteness, and it does not.

**Local Tate duality is used at lines 48-49:**

```lean
  have hTD' := hTD F Ω l 1 M A rho v Nat.one_pos hA hrho
  have hinj := hTD'.2.2.2.2.1
```

`hTD'.2.2.2.2.1` is the injective half of the last of the five parts of `LocalTateDualityAt` (`GalCoh.lean`, lines 22-34), which states that a cup product `cup20` is bijective:

```lean
    Function.Bijective
      (cup20 ((cycMod F Ω l r).comp (Dec (F := F) A).subtype) rho (MonoidHom.id _))
```

With it the proof shows that `H2` has at most one element (lines 50-53), from the fact that the twisted dual has no nonzero invariants under the chosen element (lines 34-46).

**The local Euler characteristic formula is used at line 58:**

```lean
  have he := (hEC F Ω l 1 M A rho v Nat.one_pos hA hrho).2 hl
```

`.2` is its second part, for a place `v` not above `l` (`GalCoh.lean`, line 59):

```lean
    (((l : ℕ) : 𝓞 F) ∉ v.asIdeal → Nat.card (H1 rho) = Nat.card (H0 rho) * Nat.card (H2 rho))
```

With `H0` and `H2` trivial, this makes `H1` trivial (line 59 of `tame_vanish`).

**What this means for a reader.** On the path we read, the proof of `LinkN` needs local Tate duality and the local Euler characteristic formula, and carries local finiteness without using it there. Local finiteness may be used on a path we have not read, so we do not say it is unused in the proof.

**How far the counts in this note can be trusted.** The counts above and in the Clarification look for each hypothesis by its name. A name count cannot see a hypothesis used through instance resolution, where Lean fills an argument from the context without the name being written; `tame_vanish` itself does this with `hdual`, which is never named after line 34 and is used at line 53. That route is closed for the three local statements: they are plain propositions (`def ... : Prop`, `GalCoh.lean` lines 195, 201 and 213), not classes, so Lean does not fill arguments from them on its own.

**Files added with this addition** are marked in the table below.

## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released, computed by me.

| File | SHA-256 |
|---|---|
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/SiegelEisensteinSecondTermHypotheses.lean` (lines 41-76 read) | `e761e876e3236895eec1b67b5a2118846ddfcc6883eed367ac6cc78523da15f2` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/HypothesesNonemptyOfUnramifiedExponents.lean` (lines 41-56 read) | `80ebd1ee514d8a6a7967fe3e87c775148615416906038a046b27ea9436a2cc1f` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/At23OfAll.lean` (read whole) | `dd8358fe7eae54e8029e7f0a990c3b8b3ad91c6fd31684581dbba64984770244` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/CFinal.lean` (read whole) | `53c72d83f0f9e917ac29fd1adf2165abb0d307d48e4ba0b4c9568bd881b27d24` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/MainTyzTer.lean` (line 22 read) | `25e886bddc4eb9f9049e7e08a0ebabba10ec33010dfb8229b4f1d29523996442` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/LinkNFam.lean` (read whole) | `bf49ec0e3809178eae0cde620bab3b8c0fd07a0fea5210a928f4519e310665fd` |
| `Development/AutomorphicArithmetic/Foundations/GaloisRepresentations/HeckeGaloisCriteria/LinkNOfGd.lean` (linkN_of_gd read whole) | `a16761133533d53f76cc50f8de704921ee544eb04336a92bce4fde7994a597cc` |
| `Development/AbelianVarietyTheory/Proofs/InertiaEigenvalues/LinkNAlongFamilyOfLocalBounds.lean` (read whole) | `fdc009b943e0a1034d90789404f309688e7f7bde75f7a8e5347d866a5b95b246` |
| `Formalism/SharpRestriction/LevelLetterCocycles/ThetaScalarFamilyOfEigenvalue.lean` (lines 26-55 read) | `ecd7a5bbe324c47d8b72e77c71f1dfd9e8f5375c5faa847ce926cafb9d26b203` |
| `Formalism/SharpRestriction/LevelLetterCocycles/ExportBoundOfAdmissible.lean` (lines 1023-1053 and 1141-1160 read) | `bdfc98f88029b0046557d06ae9223905e3c4b4048114a676072820d150905534` |
| `Formalism/SharpRestriction/LevelLetterCocycles/StatementFamilies/ExportFamilies.lean` (lines 12-23 read) | `e41c986bf6640ddd88f3d79e828e2b395507f0e1f36737c9e091fcc431fe65bf` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/EveryCharacterOfLiteratureOfVWin.lean` (lines 213-219, 243-244, 267-268, 271-272, 379-380, 571-588, 655-666, 722-726 read) | `246b74eeb03dae250c45b46c155b3590cb53c2bac86f5e35f4b74338db487068` |
| `Development/AbelianVarietyTheory/Definitions/NonGaloisDescent/BoundAtTwoAndThreeForFamily.lean` (lines 18-25 read) | `6b83cc632a3b8fb2e0ae85b8fd8cf84de7ff1d04a7f66062cee41391177fd9d4` |
| `ReciprocityTheory/Hypotheses/GalCoh.lean` (lines 195-218 read) | `8b5051953b0209402d9ef496c5877eec8b809d1b10fbd67877408876c36f30cd` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/ThetaLiftHypothesesOfNonvanishing.lean` (lines 24-46 read; added with the Correction of 2026-11-22) | `83c2d572d4b597a03858fee35e5258194f0fc0821ec2a5d3e8dcf3416bf1bdfe` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/LocalLanglandsGLAndPurityAtMember.lean` (lines 18-39 read; added with the Correction of 2026-11-22) | `c723060dede9507a3fbd828cd9e62268d85dca5ce50f3317e872f899a71a0f73` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/PublishedInputsCombined.lean` (lines 18-36 read; added with the Correction of 2026-11-22) | `f756b62df6738c6bac01310d3308f0857759143262a10de14504823088c609d5` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/EveryCharacterOfLiteratureOfVWin.lean` (lines 282-287, 351-352, 456-461, 609-621, 645-651 read; added with the Correction of 2026-11-22) | `246b74eeb03dae250c45b46c155b3590cb53c2bac86f5e35f4b74338db487068` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/MemberBundlesLargeUnramifiedExponents.lean` (line 34 and lines 55-72 read; added with the Correction of 2026-11-22) | `8115bc1c4fc9df8eac928acb5f04bc966f0448f4619585d633cd5d1f1614786a` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/PreAtMem.lean` (lines 54-103 read; added with the Clarification of 2026-11-23) | `59235430eabcc407ecf19981de0b06273135a1d89ecd266a2c848340ff5bcc49` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/CFacts.lean` (lines 40-62 read; added with the Clarification of 2026-11-23) | `6e8f8be134679aa1522ba1eac64346f40ce1c0d3a0d8806d37407316cd7e2fe9` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/AdmissibleJOfRestricted.lean` (lines 28-44 read; added with the Clarification of 2026-11-23) | `fe62c53ab34139e42e3be84294d801a91c8dd8e9603f4a92af6710a8c5659c6e` |
| `Development/AbelianVarietyTheory/Proofs/SatakeParameters/H1H2LocalDualityStatement.lean` (read whole; added with the Clarification of 2026-11-23) | `69a0a732d481c9b61bdf1bd82f0eb7e76d22f3fd21c4e25760db59cd63b8656e` |
| `Development/AbelianVarietyTheory/Proofs/SatakeParameters/H1H2LocalDuality.lean` (lines 149-219 read; added with the Clarification of 2026-11-23) | `55724bcc2f6d52e86d93258fb802a4bd5e209cef91b7e03e485c763c063fc385` |
| `Formalism/SharpRestriction/LevelLetterCocycles/ExistsInertiaCharpolyFactorOfTameType.lean` (lines 1471-1477 read; added with the Clarification of 2026-11-23) | `522b0eabca4bb285abc7e4bcf2976677c594b8ec11b313d2e0eb3da7eeab35d6` |
| `Development/AbelianVarietyTheory/Proofs/SatakeParameters/LocalCohomologyVanishesTameInertiaNoFixedStatement.lean` (read whole; added with the Addition of 2026-11-23) | `e510d6ff8031e937fc15cd792886de4d100a1e3f11ebd1f57382021d9a8695da` |
| `Development/AbelianVarietyTheory/Proofs/SatakeParameters/LocalCohomologyVanishesTameInertiaNoFixed.lean` (lines 20-60 read; added with the Addition of 2026-11-23) | `3973c4ff67d54f93b27cd18a20cfb0b8164c97523f8a7363519a8e9f5a228e41` |
| `ReciprocityTheory/Hypotheses/GalCoh.lean` (lines 22-34, 54-59 and 195-217 read; added with the Addition of 2026-11-23) | `8b5051953b0209402d9ef496c5877eec8b809d1b10fbd67877408876c36f30cd` |
