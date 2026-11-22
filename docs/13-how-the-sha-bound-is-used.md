# 13. How the Tate–Shafarevich bound is used: one error term in a chain of links

*Written by Kepler, 2026-11-22. Read whole by Halley before it was published; Halley's corrections are folded in, the largest being that the first draft read an off-path twin of the file that matters (see "Where the nine closed statements come from"). Everything marked **What the library says** was read in the files listed at the end, at the lines the table gives. This note reads definitions, one assembly proof of nine lines, and one short arithmetic proof; the proofs of the individual links were not read. Nothing was compiled. Nothing here has been checked by a mathematician.*

## The insight, in one sentence

**The hypothesis `HypV`, the Tate–Shafarevich bound for the hosts' fields, is consumed once by name, and there it is an additive error term: a link called `LinkN` bounds a weighted sum of local quantities by a rank times (an analytic size + the log-weighted total length of the Tate–Shafarevich groups), and the bound of [note 3](03-vwin-and-green.md) makes that total no larger than the analytic size. Everything else that "tied" needs comes from eight other links, none of which mentions the Tate–Shafarevich groups in its statement.**

Two limits on that sentence. A search by name cannot see a use that unfolds a definition; we found none, and the instrument could not show one. And `LinkN` itself, which has the Tate–Shafarevich total in its statement, is not proved on this chain: it is an assumption carried in from the third input of [note 4](04-the-third-input.md), and whatever establishes it may use bounds on Tate–Shafarevich groups of its own. So "used once" is a statement about the consuming side of `TopG`.

[Note 11](11-hosts-requirements-families.md) left open how `VVle` is *used* to produce a tie. This note answers that at the level of statements: which statement takes it in, what comes out, and where the result goes next.

## What the library says

### A scale

`Formalism/LocalRingCardinality/DataParams₂.lean`, lines 9-45. A `Scale` is a real x > 1 and a precision 0 < ε < 1/52 (the bound is a field of the structure, `eps_lt`), with a further real J ≥ 1. The derived quantities used below:

```lean
def L : ℝ := s.x ^ s.eps

def b : ℝ := Real.exp s.L

def a : ℝ := s.x * s.b
```

So L = x^ε, b = exp(x^ε) and a = x·b. The same block defines `def A : ℝ := 26` (line 41).

### "Tied" is an existence statement with four ties and seven conditions

`Formalism/SharpRestriction/GlobalSchurBounds/TieGlobal.lean`, lines 97-114:

```lean
def ChainTied {eps : ℝ} (Fm : FamP eps) (eD eL K cHH eK CL x : ℝ) : Prop :=
  ∃ (i0 : Fm.Ix x) (m f : ℕ) (pt : (Fm.D x i0).R.A → Fm.Ix x) (av bv : ℕ → ℤ)
    (Top : Type) (_ : Fintype Top)
    (Dd : Data (Fm.D x i0).R.A (fun u0 => (Fm.D x (pt u0)).what₂.Word) Top m f) (C : Consts) (Xpp : ℝ)
    (ell : AddChar (E0 × (Fm.D x i0).R.A) ℂ → ℂ) (N : ℕ) (TT T2 : Finset (Fm.D x i0).R.A) (a : (Fm.D x i0).R.A → ℝ)
    (w : (Fm.D x i0).R.A → Fin m → E0 × (Fm.D x i0).R.A → ℝ) (eT : Top ≃ TT)
    (eP : Fin f ≃ PhiSet (H := (Fm.D x i0).R.A)) (η X' θ : ℝ),
    TiePts Fm x (Fm.D x i0).R.toFrame m f (Fm.D x i0).host.q (Fm.D x i0).host.d pt av bv ∧
    TieGlobal Fm x pt Dd Xpp η X' ∧ TieLocal Fm x pt Dd ∧
    TieArith Fm x pt av (arithOf (Fm.D x i0).host.toHostRaw) ell TT T2 a w ∧
    Dd.x = x ∧ Dd.ε = eps ∧ C.eDiv ≤ eD ∧ C.eLoss ≤ eL ∧ C.cHH ≤ cHH ∧
    Ident Dd (arithOf (Fm.D x i0).host.toHostRaw) N ell TT a w eT eP ∧
    Formalism.LFunctionChainParameters.LChain.SizeData₂ Dd C Xpp ∧
    ErrWindows Dd C Xpp eK K ∧
    BNBounds Dd T2 ∧
    GrowthInequalityRemainingHyps (arithOf (Fm.D x i0).host.toHostRaw) ell N TT T2 a w x eps Dd.b Dd.b' η X' θ CL ∧
    CostWindows x (fPl (Fm.D x i0).R.A) Dd.b η θ ∧
    RestSize eps x (Fintype.card (Fm.D x i0).R.A) TT.card T2.card m Dd.b Dd.k Dd.a
```

In words: at the scale x there exist a base member i0 of the family, a map `pt` from the frame's group to members, an abstract data object `Dd` (of the type `Data` from `Formalism/RankGapBounds/MeanBoundSecondForm.lean`, not read), constants and auxiliary objects, such that

- four **ties** hold (`TiePts`, `TieGlobal`, `TieLocal`, `TieArith`, lines 39-93 of the same file): each is a list of equalities saying that a field of the abstract object `Dd`, or of the arithmetic data, *equals* a quantity read off the family's members. For example `TieGlobal` says `Dd.a`, `Dd.b`, `Dd.L` are the scale's a, b, L, and `Dd.LpL` is the member's `logDerivativeAtOne`;
- the constants are bounded by the outer ones (`C.eDiv ≤ eD`, `C.eLoss ≤ eL`, `C.cHH ≤ cHH`);
- seven **conditions** hold of the abstract object: `Ident`, `SizeData₂ Dd C Xpp`, `ErrWindows`, `BNBounds`, `GrowthInequalityRemainingHyps`, `CostWindows`, `RestSize` (all defined in `Formalism/SizeWindowBrackets/`, not read here).

So the word "tied" names the equalities: an abstract inequality machine (`Dd` with its seven conditions) is tied to a concrete family. `ChainTied.core_of` (lines 116-123) forgets the family and keeps the abstract statement `ChainCore`.

### Five inputs and one implication give "tied"

`Formalism/SharpRestriction/GlobalTheoremInputs.lean`, lines 158-164:

```lean
def GlobalTheoremInputs {eps : ℝ} (Fm : FamP eps) (Cabs CH C0 : ℝ) : Prop :=
  LinkG Fm ∧ LinkS Fm C0 ∧ LinkIRR Fm ∧ LinkDIV Fm Cabs CH ∧
  LinkMu Fm

def LinkGLOBAL {eps : ℝ} (Fm : FamP eps) (Cabs CH C0 eD eL : ℝ) : Prop :=
  ChosenE Fm C0 CH → GlobalTheoremInputs Fm Cabs CH C0 →
    ∃ K cHH eK CL x0 : ℝ, ∀ x ≥ x0, x ∈ Fm.Win → ChainTied Fm eD eL K cHH eK CL x
```

`LinkGLOBAL` is the implication: a family that is "chosen" and satisfies the five inputs is tied on its windows for large x.

### The assembly: `topDesWin`

`Development/AutomorphicArithmetic/CharacterBoxes/DesWin.lean` is 35 lines; its one theorem:

```lean
theorem topDesWin (𝒞 𝒞' ℰ : FamClass) (Cabs C0 eD eL : ℝ) (hEx : DesignExists (WithTw (WithSm 𝒞')) C0)
    (h1 : ∀ {eps : ℝ} (Fm : FamP eps), 𝒞' Fm → 𝒞 Fm) (h2 : ∀ {eps : ℝ} (Fm : FamP eps), 𝒞' Fm → ℰ Fm)
    (hV : ∀ {eps : ℝ} (Fm : FamP eps), ℰ Fm → HypV Fm.toFamCore)
    (hN : Closed (Des 𝒞 C0) fun Fm _ => LinkN Fm)
    (hEta : Closed (Des 𝒞 C0) fun Fm _ => LinkEta Fm)
    (hIRR : Closed (Des 𝒞 C0) fun Fm _ => LinkIRR Fm)
    (hZ : Closed (Des 𝒞 C0) fun Fm _ => SmallLevelRankEq Fm)
    (hDIV : Closed (Des 𝒞 C0) fun Fm CH => TuSize Fm → DGamSize Fm → LinkDIVt Fm Cabs CH)
    (hRk : Closed (Des 𝒞 C0) fun Fm CH => ChosenE Fm C0 CH → NuFullF Fm ∧ J.MuRank Fm)
    (hG : Closed (Des 𝒞 C0) fun Fm _ => LinkG Fm)
    (hS : Closed (Des 𝒞 C0) fun Fm _ => TuSize Fm → LinkS Fm C0)
    (hGL : Closed (Des 𝒞 C0) fun Fm CH => TuSize Fm → DGamSize Fm → LinkGLOBAL Fm Cabs CH C0 eD eL) : FamilyClassConnected ℰ := by
```

Its hypotheses, in words. A **design exists**: for every small precision and every threshold K there is a family in the class 𝒞′ that is large beyond K, chosen, and has two size properties (`DesignExists`, `Formalism/SharpRestriction/ParamsHeightRankConstant.lean` lines 187-190). Families in ℰ satisfy `HypV`, the Tate–Shafarevich bound of note 11. And nine statements hold **closedly** on the class of designs, where "closed" means: for every small precision there is a threshold K beyond which every large family of the class has the property (`Formalism/SharpRestriction/ParamsHeightRankConstant.lean`, lines 159-161):

```lean
def Closed (𝒞 : FamClass) (P : ∀ {eps : ℝ}, FamP eps → ℝ → Prop) : Prop :=
  ∃ ε1 : ℝ, 0 < ε1 ∧ ∀ eps : ℝ, 0 < eps → eps ≤ ε1 → ∃ K : TransportedAlt, ∀ (Fm : FamP eps) (CH : ℝ),
    𝒞 Fm → Fm.Large K CH → P Fm CH
```

The proof is nine lines (23-31). Line 23 joins the nine closed statements in the order `hN.and (hDIV.and (hEta.and (hIRR.and (hZ.and (hRk.and (hG.and (hS.and hGL)))))))`, which fixes the order of the nine names `aN, aD, aE, aI, aZ, aR, aG, aS, aGL` on line 28. Its content, read from lines 26-31:

```lean
  obtain ⟨K, hK⟩ := hA ε h0 (le_of_lt (lt_of_lt_of_le hlt (min_le_left _ _)))
  obtain ⟨Fm, CH, hc, -, hL, hCh, hT, hDG⟩ := hEx ε h0 (le_of_lt (lt_of_lt_of_le hlt (min_le_right _ _))) K
  obtain ⟨aN, aD, aE, aI, aZ, aR, aG, aS, aGL⟩ := hK Fm CH ⟨⟨⟨h1 Fm hc.1.1, hc.1.2⟩, hc.2⟩, ⟨CH, hCh⟩, hT, hDG⟩ hL
  have hD := aD hT hDG aE (divinN_of_hypV Fm h0 (hV Fm (h2 Fm hc.1.1)) aN aZ)
  exact ⟨Fm, h2 Fm hc.1.1, aGL hT hDG hCh ⟨aG, aS hT, aI, hD,
    J.linkMu_of_linkDIV Fm hD (aR hCh).1 (aR hCh).2 (muTu_of_tuSize Fm h0 hT) (J.muDGam_of_fact Fm hDG)⟩⟩
```

Step by step:

1. Take the design family `Fm`, large beyond the joint threshold of the nine closed statements (lines 26-28). All nine now hold of `Fm`.
2. `divinN_of_hypV` turns `HypV`, `LinkN` (`aN`) and `SmallLevelRankEq` (`aZ`) into `DIVinN Fm` (line 29, inner term).
3. `aD`, the closed statement `LinkDIVt`, turns `LinkEta` (`aE`) and `DIVinN` into `LinkDIV` (line 29). `LinkDIVt` is by definition that implication (`Formalism/SharpRestriction/GlobalTheoremInputs.lean`, lines 94-95).
4. `J.linkMu_of_linkDIV` turns `LinkDIV` and the rank statements into `LinkMu` (line 31).
5. `aGL`, the closed statement `LinkGLOBAL`, is applied to the five inputs `⟨LinkG, LinkS, LinkIRR, LinkDIV, LinkMu⟩` (lines 30-31) and returns that `Fm` is tied on its windows.

### The one place the Tate–Shafarevich groups enter

`Formalism/SharpRestriction/GlobalTheoremInputs.lean` defines, for a datum D and a prime l, the term

```lean
def vvTerm (D : D7) (l : ℕ) : ℝ :=
  if l.Prime then ((∑ e ∈ Finset.Ico 1 D.R.t, D.what₂.shaLen l e : ℚ) : ℝ) * Real.log l else 0
```

that is, log l times the total over 1 ≤ e < t of `shaLen l e`. `vvRecord` (`Development/AutomorphicArithmetic/CharacterBoxes/DivinNOfHypV.lean`, lines 17-18) converts the bound `VVle` of the host's field into statements about this term:

```lean
theorem vvRecord (D : D7) (B : ℝ) (h : VVle D.host.E D.R.t B) :
    ShaFinOdd D ∧ Summable (vvTerm D) ∧ ∑' l, vvTerm D l ≤ B := by
```

The link that takes it in (`Formalism/SharpRestriction/GlobalTheoremInputs.lean`, lines 36-43):

```lean
def etaSum {D : D7} (L : SizeData₂ D) (j : ℕ) : ℝ :=
  ∑ w ∈ L.supp.filter (fun w => D.what₂.muAt w ≠ D.what₂.mu0),
    SizeData₂.lwP w * (D.what₂.places.ramIdx w : ℝ) * (D.what₂.etaJ j w : ℝ)

def LinkN_at {D : D7} (L : SizeData₂ D) (j : ℕ) (C : ℝ) : Prop :=
  Summable (vvTerm D) →
    etaSum L j ≤ (L.dZ0 j : ℝ) * (C * ((D.R.f : ℝ) * D.R.m * L.sc.b * L.sc.L ^ 2 +
      Real.log L.sc.x ^ 2 * L.Nc) + ∑' l, vvTerm D l)
```

In words: `etaSum L j` is a sum, over those places w of the support at which a local invariant `muAt w` differs from a reference value `mu0`, of a weight `lwP w` times a ramification index times an integer `etaJ j w`. `LinkN_at` says: if the Tate–Shafarevich terms are summable, then this sum is at most the rank-like number `dZ0 j` times

  C·(f·m·b·L² + (log x)²·Nc)  +  Σ_l vvTerm D l.

The output (`Formalism/SharpRestriction/GlobalTheoremInputs.lean`, lines 59-60):

```lean
def DIVinN_at {D : D7} (L : SizeData₂ D) (j : ℕ) (C : ℝ) : Prop :=
  etaSum L j ≤ (D.what₂.D0 : ℝ) * (C * L.sc.x ^ L.sc.eps * (L.B0 + L.Nc))
```

`divinN_at` (`Development/AutomorphicArithmetic/CharacterBoxes/DivinNOfHypV.lean`, lines 76-115) passes from one to the other, and its proof is elementary arithmetic. It uses: `dZ0 j = D0` (that is `SmallLevelRankEq`); B0 = f·m·b·x^ε (line 92, by `rfl`); (log x)² ≤ x^ε for large x (`log_sq_le_rpow`, lines 59-74); and Σ_l vvTerm ≤ b. The last is where `HypV` is spent: `HypV` gives the total ≤ √b, and line 128 weakens √b to b because b ≥ 1. With y = x^ε the computation is

  C·(y·B0 + (log x)²·Nc) + b  ≤  |C|·y·(B0 + Nc) + y·(B0 + Nc)  =  (|C| + 1)·y·(B0 + Nc),

using b ≤ B0 ≤ y·(B0 + Nc) (lines 100-115). We checked this by hand.

Whole-word searches of the release, run by each of us separately: `vvRecord` has its definition and this one use (line 126 of the same file); `divinN_of_hypV` has its definition and the one use in `topDesWin`. Halley also searched for `HypV` and `VVle`: besides the files above, every hit is on the producing side (the files that establish the bound for a host's field, [note 11](11-hosts-requirements-families.md)), or is an unrelated declaration of the same name.

### Where the nine closed statements come from: `shape_closed_link_n_of_green`

`topDesWin` has two callers in the release, in two files that are near-copies of each other. **Only one is on the path from `Main.lean`.** [Note 5](05-the-pivot.md) traced that path through `TopPlug.lean`, and `TopPlug.lean` line 15 uses `shape_closed_link_n_of_green`, which is in `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopShape.lean` (57 lines), line 33:

```lean
theorem UpperTheory.Top.shape_closed_link_n_of_green : GlobalTheory.GLq.Green → _root_.GlobalTheory.Fc.TopShapeAlt True True (fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm) UpperTheory.Top.TopG := by
```

The other caller, `shapeWin` in `Development/AutomorphicArithmetic/CharacterBoxes/ShapeWin.lean`, has the same shape with differently named lemmas; its only use is `plugWin` in `CharacterBoxes/EveryCharacter.lean`, which is not on that path. The first draft of this note was written from `shapeWin`; Halley's whole read caught it, and this section is re-based on the on-path file.

`TopShapeAlt V NR N G` (`Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopShapeAlt.lean`, lines 24-99) is the statement "for every family class 𝒜 and 52 further hypotheses, G" (53 binders, counted by script). By a comparison of names, also by script: 45 of the 53 binder names are field names of `HypsAlt`, the 46-field structure of [note 4](04-the-third-input.md) (`Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/Hyps.lean`); the other eight are `sel selS selP selDH selC selB hVC nR`; and the one field of `HypsAlt` that is not a binder is `σ`. How the two fit is read (first by Halley, then by Kepler): `goal_of_shape_of_hyps` (`Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/ShapeOf.lean`, lines 24-30), which the `forall_goal_of_shape_of_hyps` that `TopPlug.lean` line 15 applies simply calls, fills the six `sel…` binders with functions of the field `σ` (`familySelection h.σ`, `spectralConditionOfRawSelection h.σ`, and so on), fills `hVC` and `nR` with the proofs of the slots `V` and `NR` (both `True` here), and passes the other 45 fields across by name, three of them (`hDivG`, `rRows`, `hServ`) through a converter. So the names match exactly, and the statements match for all but those three.

So `shape_closed_link_n_of_green` says: given Green's theorem, and given those hypotheses with `LinkN` among them, `TopG` holds. Its proof ends by calling `topDesWin` (lines 52-55):

```lean
  exact UpperTheory.Top.topDesWin (WithChN 𝒜) (WithChN fun Fm => 𝒜 Fm ∧ G.cls la Fm) (G.cls la) 2 3 2 0 hE
    (fun _ hc => ⟨hc.1.1, hc.2⟩) (fun _ hc => hc.1.2) hV nRest (_root_.GlobalTheory.Top.closed_linkEta_of_duty 𝒜 sel hduty)
    (_root_.GlobalTheory.Top.Irr.closed_linkIRR_of_join_count hGreen 𝒜 sel cIc hcI irrC) (_root_.GlobalTheory.Top.link_alt_alt_alt 𝒜 sel selS selP selDH selC selB hPA hLamP hDivG zL) hDIV hgl.1 (_root_.GlobalTheory.Top.closed_linkG_of_duty 𝒜 sel hduty)
    (_root_.GlobalTheory.Top.link_alt_alt_bis 𝒜 sel selS hWu hRF hTF c30 hc30 sTy sNG sM sLp sO h30 hInstR) hgl.2
```

Reading the arguments off in order:

| Input of `topDesWin` | Supplied by |
|---|---|
| constants `Cabs C0 eD eL` | `2 3 2 0` |
| `DesignExists` | `designExists_of_tuSize_aux4n_litThin`, from the hypothesis `hEx` and `HostExW` (lines 50-51) |
| `HypV` | `hV`, the hypothesis of `TopG` |
| `LinkN` | `nRest`, **a hypothesis of `TopShapeAlt`** (its parameter `N`) and a field of `HypsAlt`; not proved here |
| `LinkEta` | `closed_linkEta_of_duty` |
| `LinkIRR` | `Irr.closed_linkIRR_of_join_count hGreen …` |
| `SmallLevelRankEq` | `link_alt_alt_alt` |
| `LinkDIVt` | `closed_linkDIVt_of_closed_bridge_kernel` (line 47), from a closed statement `hBR` assembled in lines 42-46 |
| `NuFullF ∧ MuRank` | first half of `link_gl` (line 35) |
| `LinkG` | `closed_linkG_of_duty` |
| `LinkS` | `link_alt_alt_bis` |
| `LinkGLOBAL` | second half of `link_gl` |

Two facts read from this proof term:

- **Green's theorem is used once in this proof**, as the first argument of `closed_linkIRR_of_join_count` (the name `hGreen` occurs on line 34, where it is introduced, and on line 54). So within this proof Green's theorem serves the link `LinkIRR` and no other.
- **The constants are eD = 2 and eL = 0.** `FamilyClassConnected` is an existence statement in eD and eL; `topDesWin` witnesses it with the values it was given (`Development/AutomorphicArithmetic/CharacterBoxes/DesWin.lean` line 25), so on this path the witnesses are 2 and 0. [Note 9](09-the-window-bound.md) read the window bound as Gm x ≤ x^(1/2 + (eD + eL + 7)·ε), proved for *all* eD and eL; with these witnesses the exponent unfolds to 1/2 + 9ε. Nothing downstream uses the particular values (Halley's reading of `zeroFreeAll_of_topG`, which takes the pair out of the existence statement and hands it on).

### What the links say, as far as their statements were read

All in `Formalism/SharpRestriction/GlobalTheoremInputs.lean`.

- **`LinkN`** (lines 45-47, with `LinkN_at` at 40-43): above. For every member with finite Tate–Shafarevich groups, the bound on `etaSum` with the Tate–Shafarevich total as a summand.
- **`SmallLevelRankEq`** (lines 52-53): `dZ0 j = D0` for every lift index j.
- **`LinkEta`** (lines 49-50): `N.LocsCoverTw` for every member (definition not read).
- **`LinkIRR`** (lines 55-57): a quantity `delp` of each member is non-negative and at most exp(−x^(ez/7)).
- **`LinkDIV`** (lines 77-92): nine conjuncts per member. The seventh is an inequality with a named main term: `D.div.RR.muDual + D.div.h u - L.Fo ≤ L.MAIN u + …` with two error terms, the second being C·m·(B0 + Nc)·x^(Cabs·ε), the same B0 + Nc that `DIVinN` is measured in.
- **`LinkMu`** (lines 74-75, with `NprimeMuR` at 69-70): for every word u, |μ(N_u) − μ(N^H_u) − Σ_w sz(…)| ≤ C·X″.
- **`LinkG`** (lines 122-140): per member, five conjuncts. The third concerns places whose residue characteristic p is of class "signal" or "inert" for the host (`InertK`, lines 97-98) and at most X″: there a quantity `gain j w` lies between 0 and 4·|TT|·a/p, and a sum of `vonMangoldtClassSum j t p` minus explicit losses `loG`, `flG` is at most Σ_j gain − τ(w).
- **`LinkS`** (lines 145-156): for distinct words u ≠ u′ a squared Hilbert–Schmidt norm `hsSq u u′` is at most (1 + η0)·d_u·d_u′/D*, with η0 ≤ exp(−x^(ε/8)); a near-orthogonality statement.

## Interpretation (ours; check it)

- **The Tate–Shafarevich bound buys one inequality, `DIVinN`, and `DIVinN` is a premise of `LinkDIV`.** That is read (steps 2-3 above). Beyond `topDesWin`, the name `DIVinN` occurs in 33 files of the release (67 lines, by a whole-word search), most of them in the abelian-variety and theta-correspondence parts, where the lines we saw have it as a hypothesis; we have not read those files. So the picture "movement 2 turns small Tate–Shafarevich groups into a tie" (note 11) should be sharpened: small Tate–Shafarevich groups give `DIVinN`; `DIVinN` and `LinkEta` give `LinkDIV`; and `LinkDIV` is one of five inputs to the tie, the other four (`LinkG`, `LinkS`, `LinkIRR`, and `LinkMu` through the ranks) having their own sources.
- **How large the allowed Tate–Shafarevich total is.** The total that `divinN_at` needs is b = exp(x^ε), and what is supplied is √b = exp(x^ε/2). Here x is the scale and the host's conductor is a quantity we have not related to x in this note. We therefore do not say how weak this is as a bound in terms of the field; note 3's phrase, the author's "significant weakening of Vandiver", is the author's.
- **A guess at the meaning of `LinkN`.** Its shape, (a sum of local defects at the places where a local invariant is not generic) ≤ rank × (analytic size + total length of Tate–Shafarevich groups), is the shape of a local–global duality count, in which the failure of local conditions to be met globally is measured by a Tate–Shafarevich group. **This is a guess from the shape of one inequality.** We have not read `etaJ`, `muAt`, `lwP` or any proof of `LinkN`. On this chain `LinkN` is not proved at all: it arrives as `nRest`, a field of the third input. So the guess is about an assumption of the theorem as it is stated here, not about something this chain proves. Halley found two theorems elsewhere in the library whose conclusion is `LinkN` (`linkN_of_gd` in a file `LinkNOfGd.lean`, and `export_link_of_family` in `Formalism/SharpRestriction/LevelLetterCocycles/ThetaScalarFamilyOfEigenvalue.lean`, line 30); neither of us has traced them.
- **Where the inert primes of note 9 sit.** Note 11 reported that the condition `SizeData₂ Dd C Xpp` inside `ChainTied` feeds the one-sided bound on a weighted count of inert primes. Of the five inputs, the one whose statement speaks of inert primes and of a von Mangoldt class sum is `LinkG`. We conjecture that `LinkG` is the source of that condition; we have not read `link_gl`, whose second half is `LinkGLOBAL`, where this would be decided.
- **Two links that are defined and not used.** The file also defines `LinkV` (lines 16-23: the Tate–Shafarevich total is at most an explicit bound `Vbound`) and `LinkShaFin`. A structure `AllLinks` (`Formalism/SharpRestriction/MuTuOfTuSize.lean`, line 13) bundles them with the nine; a whole-word search finds no use of `AllLinks`, and `LinkV` occurs only in its definition and there. So a second, direct link for the Tate–Shafarevich total exists in the library and is not on any path we found.
- **The constant 1/52.** Note 11 could not say where 1/52 comes from. It is a field of `Scale`, so every scale has ε < 1/52 by construction; and the same structure sets A = 26, with 1/52 = 1/(2A). We have not found a line that derives one from the other.

## Not read, not understood

- The proofs of all the links: `closed_linkEta_of_duty`, `closed_linkIRR_of_join_count`, `closed_linkG_of_duty`, `link_alt_alt_alt`, `link_alt_alt_bis`, `link_gl`, `designExists_of_tuSize_aux4n_litThin`, `closed_linkDIVt_of_closed_bridge_kernel`, `J.linkMu_of_linkDIV`.
- Where `LinkN` is proved, if it is: on this chain it is the field `nRest` of the third input.
- What the 53 hypotheses of `TopShapeAlt` say, beyond their names.
- `etaJ`, `muAt`, `mu0`, `lwP`, `dZ0`, `D0`, `Nc`, `shaLen`, `delp`, `MAIN`, `gain`, `vonMangoldtClassSum`, `hsSq`: every quantity the links are stated in.
- The seven conditions of `ChainTied` and the type `Data`.
- `ChosenE` beyond its shape (seven "chosen" properties with three positive constants, `Formalism/SharpRestriction/GlobalSchurBounds/Chosen.lean` lines 79-84), `TuSize`, `DGamSize`, `Fm.Large`.
- The off-path twin `CharacterBoxes/ShapeWin.lean`, beyond what the first draft read of it (whole; same constants `2 3 2 0`, Green's theorem likewise used once). Nothing in this note now rests on it.

## Added 2026-11-22: where `LinkN` comes from (note 14)

*A dated addition by Kepler, read by Halley before it was published. Nothing above is changed.*

This note says that `LinkN` "is not proved on this chain: it is an assumption carried in from the third input", and that "whatever establishes it may use bounds on Tate–Shafarevich groups of its own". That is true of the shape theorem, and it says nothing about the path from `Main.lean`. [Note 14](14-where-linkn-comes-from.md), by Halley, follows that path. On it `LinkN` is not assumed: note 14 traces it to a statement, `GlobalTheory.NLink.Final.mainTheorem` (a `Prop`, `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/MainTyzTer.lean`, line 22), which the library proves as `final_alt_alt` (`CFinal.lean` in the same folder, line 19; both lines opened by Kepler, the proof read by Halley in note 14). What that statement takes as inputs, which of them are filled by theorems of the library (we read only that their terms do not use the literature bundle), and how the three statements taken from the literature reach them, is in note 14 **as corrected on 2026-11-22**. Take the list from its "Correction" section, not from here: the first version of note 14 gave a shorter list, and an earlier draft of this paragraph repeated it.

On the question this note left open, at the strength note 14 states it:

- The two steps of that chain that carry the Tate–Shafarevich total, `export_bound_of_admissible` and `linkN_of_gd`, were read (both by Halley, the first also by Kepler). Neither bounds the total; both carry it through as a summand. The total enters in a lemma, `etaSum_le`, that neither of us has read.
- A search by name from `linkN_of_twGood_galoisPreconditions` (note 14, step 3) reached 21,402 declarations and found no use of `HypV`, `VVle` or `VWin` among them. Halley, who wrote the script, calls it an instrument without a control; it skipped 1,003 names it could not resolve. It is a lower bound on what the chain uses, not a proof that nothing on it bounds the total.

So the second limit stated under "The insight" can be narrowed to this: on the two steps that were read, nothing bounds the Tate–Shafarevich total a second time. The guess under "Interpretation", that `LinkN` is a local–global duality count, is still a guess; the lemma it is really about is `etaSum_le`.

## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released. The quoted blocks were cut from these files by line range with a script.

| File | SHA-256 |
|---|---|
| `Formalism/LocalRingCardinality/DataParams₂.lean` (lines 9-45) | `39d84d7e7db5196715f955ac44f45e61a23fcf4ebd5065ca41444f836efd3099` |
| `Formalism/SharpRestriction/GlobalSchurBounds/TieGlobal.lean` (read whole) | `065799d1ade7de2b196ce5fc384596059f85f5ea952b5582f5040b2807c65b6d` |
| `Formalism/SharpRestriction/GlobalTheoremInputs.lean` (read whole) | `4d51ccc0586441a159ad6d09ebc0a46b3c462e3c5b296d5a5bd7613266e17bfb` |
| `Development/AutomorphicArithmetic/CharacterBoxes/DesWin.lean` (read whole) | `655762e90a0d7aae940774b631286a6cb942e59f68d7a3c350c05274487bf6ec` |
| `Development/AutomorphicArithmetic/CharacterBoxes/DivinNOfHypV.lean` (read whole) | `cefdce360890e26405199ef8db01d6b0c7e044c4ebebeb6bbcfd23de6148bde0` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopShape.lean` (lines 28-57 read, the whole of its one theorem) | `9647d4cbe444f79de90c7a5371801e83c58a040499bf03fd61faf37be9e6eaa3` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopShapeAlt.lean` (read whole by Halley; by Kepler the binder names by script, and the twin statement in GlobalTwisting/TopShape.lean) | `e72d8ae82e3c239cf46cf4bfb11fa82c9e16383a50ead1c1c8a8ba717ebe89fb` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/Hyps.lean` (field names extracted by script; see note 4) | `7c2e3cf200c8adb32d232bf97122dca648fd4e19de132f6d1f07f620171fa8cb` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/ShapeOf.lean` (lines 20-33) | `c37a51fd244c4812302bf5d816a248e119ec9ed84089869752267ae741a61705` |
| `Formalism/SharpRestriction/ParamsHeightRankConstant.lean` (lines 150-200) | `444928b34f52db021ec70d340afcdee5d2478292b880d7a04d333ac6948b1416` |

