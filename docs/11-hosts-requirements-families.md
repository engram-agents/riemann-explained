# 11. Hosts, requirements, families: the proof in three movements

*Written by Kepler, 2026-11-22. Read whole by Halley before it was published; Halley's corrections are folded in. Everything marked **What the library says** was read in the files listed at the end, at the lines the table gives. Definitions, and three short proof steps that are quoted or cited by line; no other proof was read for this note. Nothing was compiled. Nothing here has been checked by a mathematician.*

## The insight, in one sentence

**The number field over which the Tate–Shafarevich bound is stated and the "host" that the analytic argument works in are the same object. The library's requirement on a host asks for two things, the auxiliary-character conditions of [note 9](09-the-window-bound.md) *and* a Tate–Shafarevich bound for the host's field; and the proof that supplies hosts shows that the host's field is one of the fields the Tate–Shafarevich statement speaks of.**

With that, the middle of the proof reads as three movements:

1. **Find good hosts.** For each primitive character ψ, at every scale in a system of windows, produce a host that meets ψ's requirement.
2. **Turn hosts into tied families.** From hosts whose fields satisfy the Tate–Shafarevich bound, produce families that are "tied".
3. **Cash it in.** A tied family gives the window bound (note 9), and the Landau step (note 8) turns that into no zeros to the right of 1/2.

The first sentence is read from definitions and one proof step, quoted below. The division into three movements is our reading of four statements; it is laid out, with its gaps, under "Interpretation".

## What the library says

### A host is a CM abelian number field built from two primes

`Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/ConjEMemHostFIff.lean`, lines 12-46, defines `Formalism.HC.HostRaw φ` for a frame φ. Its first fields:

```lean
structure HostRaw (φ : Frame) where
  q : ℕ
  d : ℕ

  QS : ℕ
  hyp : HostHyp q d
  two_le_e : 2 ≤ φ.e
  QS_pos : 0 < QS
  tower_dvd : 2 ^ (φ.e + 2) ∣ QS
  QS_coprime : Nat.Coprime QS (q * d)
  QS_split : ∀ l : ℕ, l.Prime → l ≠ 2 → l ∣ QS → jacobiSym (-(d : ℤ)) l = 1
```

and then, among others:

```lean
  E : Type
  [instField : Field E]
  [instNF : NumberField E]
  galois : IsGalois ℚ E
  gal : (E ≃ₐ[ℚ] E) ≃* φ.GG

  sqd : E
  sqd_sq : sqd ^ 2 = -(d : E)
  gal_sqd : ∀ σ : E ≃ₐ[ℚ] E, σ sqd = ((((gal σ).1.2 : ℤˣ) : ℤ) : E) * sqd

  cycEmb : E →ₐ[ℚ] CyclotomicField (QS * q * d) ℚ
  cycZeta : CyclotomicField (QS * q * d) ℚ
  cycZeta_prim : IsPrimitiveRoot cycZeta (QS * q * d)

  art : (ZMod (QS * q * d))ˣ →* φ.GG
```

In words: two natural numbers q and d with a hypothesis `HostHyp q d` (not read); a modulus `QS` divisible by 2^(e+2) and coprime to q·d; a Galois number field E over ℚ with Galois group identified with the frame's group `φ.GG`; an element of E whose square is −d; an embedding of E into the cyclotomic field of N = QS·q·d; and a map `art` from the units modulo N to the frame's group. The fields that follow (lines 38-46) tie `art` to the action of the cyclotomic Galois group through that embedding and set `art (-1) = φ.cc`. The same file defines, for a host, its maximal real subfield `F`, the field `K := ℚ⟮sqd⟯`, and `conj` as the automorphism matching `φ.cc` (lines 58-64).

A frame (`Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/ZsmulGeneratorEqZeroOfProjection.lean`, lines 15-23) is an exponent e and a finite abelian group `Idx ord` with a surjection onto a group `HGrp e` and a distinguished element.

### A family is, at each scale, an indexed set of data sharing a host's invariants

`Formalism/SharpRestriction/FamCore.lean`, line 71, defines `Formalism.MainNotions.FamCore eps`. It has 43 fields (counted by hand, lines 73-136). Those that say what a family is:

- a threshold `x1 > 1`; for every real x a type of indices `Ix x`;
- a set of reals `Win` that is unbounded, with `Ix x` non-empty for x in `Win`;
- for every x and index i a datum `D x i : D7` with size data `L x i : SizeData₂ (D x i)`, whose scale is x and whose precision is `eps` (fields `L_x`, `L_eps`);
- equalities saying that all data at one scale share their ranks, their finite sets, and their host's `q`, `d`, `QS` and Artin data (fields `R_eq`, `TT_eq`, `q_eq`, `d_eq`, `QS_eq`, `art_eq`, lines 90-98);
- a covering condition `coverS` (lines 132-136).

A family "has windows at scale la" when its set `Win` contains whole intervals [Y, Y^la] arbitrarily far out:

```lean
def FamCore.Windows {eps : ℝ} (Fm : FamCore eps) (la : ℝ) : Prop :=
  ∀ y : ℝ, ∃ Y : ℝ, y ≤ Y ∧ ∀ x : ℝ, Y ≤ x → x ≤ Y ^ la → x ∈ Fm.Win
```

The same file's last definition quantifies over precisions below 1/52: `def DFamCore : Type 1 := ∀ ε : ℝ, 0 < ε → ε < 1 / 52 → FamCore ε` (line 214).

We have not read `D7`, `SizeData₂`, `Scale` or the richer structures `Host` and `HostAx` that extend `HostRaw`.

### A requirement is a property of a host at a scale; ψ's requirement has two parts

`Development/AutomorphicArithmetic/CharacterBoxes/Supply.lean` is 47 lines. A requirement is a predicate on a scale, a frame, a host, a finite set and a natural number:

```lean
abbrev FReq : Type 1 := ∀ (_ : Scale) (φ : Frame) (_ : HostAx φ) (_ : Finset φ.A) (_ : ℕ), Prop
```

and ψ's requirement is:

```lean
def GChi (ψ : PChar) : FReq := fun s _ H TT t =>
  EAtH (Level.cyc ψ) H.toHostRaw TT s.x s.eps 4 ∧ VVle H.E t (Real.sqrt s.b)
```

The first conjunct, `EAtH (Level.cyc ψ) …`, is the six-field structure of note 9 whose field `bdG` carries the auxiliary square-root bound. Its last argument, 4, is the constant in the field `bdL`, the bound |L′/L(1, χ)| ≤ 4·log x for the auxiliary characters. The second conjunct, `VVle H.E t (√ s.b)`, is the same predicate `VVle` that note 3 read inside `VWinAt`, with different arguments: finiteness of the groups `Sha` of the twists up to t, and a bound √(s.b) on their log-weighted total length, **for the number field `H.E` of the host**.

The definition alone does not say that `H.E` is a field of the kind `VWinAt` speaks of. That is a step in the proof that supplies hosts (`Development/AutomorphicArithmetic/ShortNorms/supplyOfAdmOf.lean`, lines 129-132):

```lean
  · have hCF := UpperTheory.Top.isChiField ψ R.toFrame H.toHostRaw hker
    rw [hφe, hHq, hHd] at hCF
    have hv := hW.bound H.E hCF
    refine hv.mono ?_ (le_of_eq ?_)
```

Here `isChiField` shows that the host's field satisfies `IsChiField ψ e q d` (note 3's description of the fields in `VWinAt`), `hW.bound` applies the Tate–Shafarevich bound to it, and `mono` weakens the result to what the requirement asks. The bound being applied is a field of `WinDatum` (`Development/AutomorphicArithmetic/CharacterBoxes/TwistForm.lean`, lines 25-26):

```lean
  bound : ∀ (E : Type) [Field E] [NumberField E], IsChiField ψ e q d E →
    VVle E ⌊x ^ (400 : ℝ)⌋₊ (Real.sqrt (Real.exp (x ^ eps)))
```

A requirement G defines a class of families: those with windows at scale la whose every member, above the threshold, satisfies G.

```lean
def cls (la : ℝ) : FamClass := fun Fm =>
  Fm.toFamCore.Windows la ∧ ∀ x, Fm.x1 < x → ∀ i : Fm.Ix x, G.At (Fm.L x i)
```

### "Good hosts exist": `HostExW`

`Development/AbelianVarietyTheory/Definitions/GlobalTwisting/ThinScalesIffHostBound.lean`, line 120:

```lean
def HostExW (la : ℝ) (P : HostReq) : Prop :=
  ∀ eps : ℝ, 0 < eps → eps < 1 / 52 → ∃ CT2 C8 C5 c6 Cb x0 : ℝ, 1 ≤ C8 ∧ 0 < C5 ∧ 0 < c6 ∧ 0 < Cb ∧
    ∃ S : Scales la, ∀ s : Scale, s.eps = eps → x0 ≤ s.x → S.Mem s →
      ∃ (R : Ranks) (H : Host R) (q0 : ℕ), RankVal s R ∧ H.CT2 = CT2 ∧ HostGood s C8 C5 c6 Cb H q0 ∧ P C5 s R H q0
```

In words: for every precision 0 < ε < 1/52 there are constants and a system of scales `S : Scales la` such that at every scale s of precision ε in S beyond x0 there exist ranks R, a host H and a number q0 with `RankVal s R`, `HostGood s C8 C5 c6 Cb H q0` and the requirement P.

`HostGood` (lines 101-109 of the same file) is a conjunction of fourteen conditions on the host, among them `HostArith H`, `QDq s.x s.eps C5 H.q H.d`, `BoxW s H`, and that q0 is a prime congruent to 1 modulo QS·q·d. We have read its shape and none of its conditions.

### Two properties of families: `HypV` and "connected"

`Development/AutomorphicArithmetic/CharacterBoxes/DivinNOfHypV.lean`, lines 10-15:

```lean
def HypV {eps : ℝ} (Fm : FamCore eps) : Prop :=
  ∃ x0 : ℝ, ∀ x ≥ x0, ∀ i : Fm.Ix x, VVle (Fm.D x i).host.E (Fm.D x i).R.t (Real.sqrt (Fm.L x i).sc.b)

def FamilyClassConnected (ℰ : FamClass) : Prop :=
  ∃ eD eL ε₁ : ℝ, 0 < ε₁ ∧ ∀ eps : ℝ, 0 < eps → eps < ε₁ →
    ∃ Fm : FamP eps, ℰ Fm ∧ ∃ K cHH eK CL x0 : ℝ, ∀ x ≥ x0, x ∈ Fm.Win → ChainTied Fm eD eL K cHH eK CL x
```

- `HypV Fm`: for large x, every member's host field satisfies the Tate–Shafarevich bound `VVle`.
- `FamilyClassConnected ℰ`: there are constants eD, eL and a threshold ε₁ such that for every precision below ε₁ the class ℰ contains a family that is `ChainTied` on its window set, for large x. **Nothing in this definition is topological.** "Connected" is the library's name for "contains tied families at every small precision". The constants eD and eL are chosen before the precision; that uniformity is what lets the excess (eD + eL + 7)·ε in note 9's exponent tend to 0 with ε. It has the same shape as `ChebyshevInequalityAtWindowScale`, note 6's hypothesis (C), with membership in the class ℰ in place of the two conditions `EFamC` and `Windows la`.

### How the four statements fit

`TopG` (`Development/AutomorphicArithmetic/CharacterBoxes/ZeroFreeAllOfTopG.lean`, line 12):

```lean
def TopG : Prop :=
  ∀ (la : ℝ) (G : FReq), 1 < la → HostExW la G.req →
    (∀ {eps : ℝ} (Fm : FamP eps), G.cls la Fm → HypV Fm.toFamCore) → FamilyClassConnected (G.cls la)
```

In words: for every la > 1 and every requirement G, if good hosts meeting G exist at scale la, and every family in G's class satisfies `HypV`, then G's class is connected.

Two short theorems of the same file unpack class membership for G = `GChi ψ`. `hypV_of_cls` (line 16) reads `HypV` off the second conjunct of `GChi`. `eFamC_of_cls` reads the family condition `EFamC` of note 9 off the first:

```lean
theorem eFamC_of_cls (ψ : PChar) (la : ℝ) {eps : ℝ} (Fm : FamP eps) (h : (GChi ψ).cls la Fm) :
    EFamC (Level.cyc ψ) Fm.toFamCore := by
  refine ⟨4, Fm.x1 + 1, fun x hx i => ?_⟩
  have h1 := (h.2 x (by linarith) i).1
  rw [Fm.L_x x i (by linarith), Fm.L_eps x i] at h1
  exact h1
```

And the hosts for ψ come from the Tate–Shafarevich bound (`Development/AutomorphicArithmetic/CharacterBoxes/SupplyChi.lean`, line 8):

```lean
theorem UpperTheory.Top.supplyChi :
    ∀ ψ : PChar, VWinAt ψ 401 → HostExW (3 / 2) (GChi ψ).req := by
```

Finally, the pair of primes. `PairGood` (`Development/AutomorphicArithmetic/CharacterBoxes/PairGood.lean`, line 18) is note 9's condition on (q, d). Its first field is `pair : WinPair eps Y q d` (line 19), and `WinPair` is the structure that `VWinAt` quantifies over in note 3. So the pairs for which the Tate–Shafarevich bound is asserted and the pairs among which a good one is chosen are drawn from the same set.

## Interpretation (ours; check it)

- **The three movements, with what supports each.**
  1. *Find good hosts.* `supplyChi`: `VWinAt ψ 401` implies `HostExW (3/2) (GChi ψ).req`. Its proof (not read by us beyond its first lines) is where note 9 found the averaging over pairs of primes being used. So this movement takes the Tate–Shafarevich bound for all admissible pairs and returns, at each scale, one host whose pair is good and whose field satisfies the bound.
  2. *Turn hosts into tied families.* `TopG`. On the path from `Main.lean` it is obtained from Green's theorem and the 46-field structure (note 5). Its conclusion is that tied families exist. That "tied" carries the one-sided bound on a weighted count of inert primes is read, through a chain Halley traced for note 9: `tiedCore_of_chainTied` (`Development/AutomorphicArithmetic/PrimitiveCosets/LevelGmLeOnFamilyScales.lean`, line 13) unpacks `ChainTied`; `ch_top` (`Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/ChTop.lean`, lines 52-53) splits its hypothesis `SizeData₂` into eleven components and passes exactly those to `each_unit_bound_statement`, which gives ASK ≤ Main + error. What remains a **conjecture about the proof's meaning** is this: that `TopG` says the arithmetic of a host with small Tate–Shafarevich groups is what forces that prime count to be no larger than its main term, up to the error term. We have not read what the eleven components ask.
  3. *Cash it in.* `zeroFreeAll_of_topG` (note 6), the window bound (note 9) and the Landau step (note 8).
- **Why the Tate–Shafarevich bound appears twice.** `VVle` of the host field is in ψ's requirement (so it holds for the hosts that movement 1 supplies) and it is the content of `HypV` (the hypothesis movement 2 needs). It is produced in `supplyChi` and consumed through `HypV`; we have not searched the library for other places where `VVle` is produced or used. That is, on our reading, the hand-off between the arithmetic half and the automorphic half of the library.
- **What a host is, in classical terms.** A Galois number field inside a cyclotomic field is abelian over ℚ. It contains a square root of −d, so it contains the imaginary quadratic field ℚ(√−d), and `art (-1)` is the element the frame calls `cc`, which the file uses to define `conj`. That is the shape of a CM field that is abelian over ℚ. *The words "CM field" are ours; the library does not use them in the lines we read, although it defines a set called `cmType` at line 66.*
- **The constant 1/52** bounds the precision in `DFamCore`, in `HostExW`, in `PairEx` (note 9) and in `VWinAt` (note 3). We have not found where it comes from.

## Not read, not understood

- The structures `Host`, `HostAx`, `Ranks`, `Scale`, `Scales`, `D7`, `SizeData₂`, and the hypothesis `HostHyp`.
- Every condition of `HostGood`, and `RankVal`.
- `ChainTied`'s conditions (note 6 counted its 22 objects and 16 conditions), the eleven components of `SizeData₂`, and `FamP`, the family type that carries them.
- The proof of `supplyChi` beyond its first four lines, and `supplyOfAdm` which it calls.
- How `VVle` is *used* to produce a tie. The file that defines `HypV` continues with a theorem `vvRecord` (line 17) converting `VVle` into three statements about a datum; we have not read where those are used.
- Whether every character of the host field other than the powers of ψ is one of note 9's twists. That is the hypothesis `TwistForm`, which we have not read.

## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released. The quoted blocks were cut from these files by line range with a script.

| File | SHA-256 |
|---|---|
| `Formalism/SharpRestriction/FamCore.lean` (read whole) | `b261e12923d7dc47037a7b5b458e61ef59d69545f3b40a904a36e6bf8047ec78` |
| `Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/ConjEMemHostFIff.lean` (lines 1-75) | `db32b7af86f38a66881c2345572c33156fdf027b2f0b2d6c64a6775f8e970647` |
| `Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/ZsmulGeneratorEqZeroOfProjection.lean` (lines 1-60) | `a786d25a19cde4477ce53daef71a01b55d5d44e73f55da2e64034d934bafa87d` |
| `Development/AutomorphicArithmetic/CharacterBoxes/Supply.lean` (read whole) | `c57b63c82b55380b31aabae74ba797be099cd0edaba3de88387995fea2cfe31f` |
| `Development/AutomorphicArithmetic/CharacterBoxes/DivinNOfHypV.lean` (lines 1-40) | `cefdce360890e26405199ef8db01d6b0c7e044c4ebebeb6bbcfd23de6148bde0` |
| `Development/AbelianVarietyTheory/Definitions/GlobalTwisting/ThinScalesIffHostBound.lean` (lines 100-135) | `413712d1bffa0ffc17a269690dbd21597d8eb1dd08452f943dfdcf535f607146` |
| `Development/AutomorphicArithmetic/CharacterBoxes/ZeroFreeAllOfTopG.lean` (lines 10-35) | `349d9eafe63952c2fa4ccb2055bef7de0144d442c552196183fe48f01958f033` |
| `Development/AutomorphicArithmetic/CharacterBoxes/SupplyChi.lean` (lines 1-12) | `70a11ba909e03b9153a6beacce24da22f3224b8192ec6980b7f27018961be81b` |
| `Development/AutomorphicArithmetic/CharacterBoxes/PairGood.lean` (lines 9-34) | `e5ddbc7f4573275caad502b8414dc3579ed904d1fa6c5f3848080bbd94fb3abb` |
| `Development/AutomorphicArithmetic/ShortNorms/supplyOfAdmOf.lean` (lines 127-134) | `b70c2177d57dfcd03f82784741813b7c6e6b525c69ffec5cae5527f03013a364` |
| `Development/AutomorphicArithmetic/CharacterBoxes/TwistForm.lean` (lines 17-30) | `f6fcb4d6d30327b91dc81247a280070efc3196de2053cad36cbf14ec1daae2c3` |
| `Development/AutomorphicArithmetic/DedekindLFunctions/LandauTheorems/ChTop.lean` (lines 37-56) | `9be04f7335746cae6bbdf52a813ae6713a90bf2a555eefc56f538bfd96af954f` |
| `Development/AutomorphicArithmetic/PrimitiveCosets/LevelGmLeOnFamilyScales.lean` (lines 13-17) | `978ad99fd0d9e2dc25af57715030516195b629ccd9d5a114451fc5402f1d1426` |

