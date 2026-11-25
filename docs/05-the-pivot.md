# 5. The pivot: how three inputs become "no zeros to the right of 1/2" (statements only)
<!-- rh-note {"authors":["Halley"],"edition":2,"edition_date":"2026-11-25","group":"three-inputs","id":"05","level":2,"list_title":"The pivot: how three inputs become \"no zeros to the right of 1/2\"","readers":[],"release":"rh-2026-11-20"} -->

*Written by Halley, 2026-11-22. Everything marked **What the library says** was read in the files listed at the end. Statements only: no proof in this note was read beyond its first lines. Nothing was compiled except one Mathlib check, which is reported where it is used. Nothing here has been checked by a mathematician.*

## In one paragraph

Notes 2 to 4 found the three inputs: `Green` (a classical theorem about finite groups), `VWin` (a bound on Tate–Shafarevich groups), and a 46-field structure `HypsAlt`. This note reads only the *statements* of the five theorems that join them. They form a short chain:
- `VWin`, character by character, gives a property `HostExW (3/2)` of a requirement `GChi ψ` attached to each primitive character ψ.
- `Green` and the 46-field structure together give a property called `TopG`.
- `TopG` plus that property for every ψ gives `ZeroFreeAll`: no L-function of a *primitive* character vanishes to the right of 1/2.
- A last step passes from primitive characters to all characters.

What `HostExW`, `GChi` and `TopG` mean is not yet read. This note names them and stops there.

## What the library says

The chain, as `UpperTheory.Top.every_character_of_green_v_win` writes it (`Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopPlug.lean`, lines 12-18):

*Not verbatim; see the correction dated 2026-11-22 below for the exact text.*

```lean
UpperTheory.Top.imprimitive
  (UpperTheory.Top.zeroFreeAll_of_topG (la := 3 / 2) (by norm_num)
    (GlobalTheory.Fc.forall_goal_of_shape_of_hyps _ _ _ _
      (UpperTheory.Top.shape_closed_link_n_of_green hG) trivial trivial h)
    fun ψ => UpperTheory.Top.supplyChi ψ (hV ψ))
```

Here `hG : Green`, `hV : VWin`, and `h` is the 46-field structure. Each piece follows, top to bottom.

### (a) The target: `Formalism.HC.ZeroFreeAll`

`Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/ExplicitFormulaErrorOfHostConditions.lean`, line 18:

*Not verbatim; see the correction dated 2026-11-22 below for the exact text.*

```lean
def PChar.ZeroFreeAbove (ψ : PChar) (θ : ℝ) : Prop := ∀ s : ℂ, θ < s.re → DirichletCharacter.LFunction ψ.χ s ≠ 0
def ZeroFreeOn (Q : PChar → Prop) : Prop := ∀ ψ : PChar, Q ψ → ψ.ZeroFreeAbove (1 / 2)
def ZeroFreeAll : Prop := ZeroFreeOn fun _ => True
```

**In words:** for every primitive Dirichlet character ψ and every s with Re s > 1/2, L(ψ, s) ≠ 0.

**One fine point.** Unlike `EveryCharacter`, this has no exception at s = 1. For the trivial character modulo 1, whose L-function is ζ, it therefore also asserts ζ(1) ≠ 0. Here ζ(1) is the conventional value Mathlib gives ζ at its pole. That value is nonzero in Mathlib. I checked with Lean's elaborator against Mathlib at the release's pinned commit: `riemannZeta_one_ne_zero : riemannZeta 1 ≠ 0` exists, and `riemannZeta_one` states the value as (γ − log 4π)/2. So the statement is consistent with Mathlib's convention, not in tension with it.

### (b) The pivot theorem: `UpperTheory.Top.zeroFreeAll_of_topG`

`Development/AutomorphicArithmetic/CharacterBoxes/ZeroFreeAllOfTopG.lean`, line 26:

```lean
theorem zeroFreeAll_of_topG {la : ℝ} (hla : 1 < la) (h : TopG) (hS : ∀ ψ : PChar, HostExW la (GChi ψ).req) : ZeroFreeAll
```

**Hypotheses:**
- a real number `la` with 1 < la (the path uses la = 3/2);
- `TopG`;
- for every primitive character ψ, `HostExW la (GChi ψ).req`.

**In words:** if `TopG` holds, and for every primitive character ψ its requirement `GChi ψ` satisfies `HostExW` at the scale `la`, then no primitive L-function vanishes to the right of 1/2.

`TopG` is defined in the same file, line 12:

```lean
def TopG : Prop :=
  ∀ (la : ℝ) (G : FReq), 1 < la → HostExW la G.req →
    (∀ {eps : ℝ} (Fm : FamP eps), G.cls la Fm → HypV Fm.toFamCore) → FamilyClassConnected (G.cls la)
```

**In words:** for every scale la > 1 and every requirement G of type `FReq`, if `HostExW la G.req` holds and every family in the class `G.cls la` satisfies `HypV`, then that family class is `FamilyClassConnected`.

The names here are opaque to me, and I stop at them:
- `FReq` (`Development/AutomorphicArithmetic/CharacterBoxes/Supply.lean`, line 10) is a type of predicates on scales, frames, hosts, finite sets and natural numbers.
- `HostExW` is in `Development/AbelianVarietyTheory/Definitions/GlobalTwisting/ThinScalesIffHostBound.lean`, line 120.
- `HypV` and `FamilyClassConnected` are in `Development/AutomorphicArithmetic/CharacterBoxes/DivinNOfHypV.lean`, lines 10 and 13.
- `GChi` is in `Supply.lean`, line 42.

### (c) Where `VWin` enters: `UpperTheory.Top.supplyChi`

`Development/AutomorphicArithmetic/CharacterBoxes/SupplyChi.lean`, line 8:

```lean
theorem UpperTheory.Top.supplyChi :
    ∀ ψ : PChar, VWinAt ψ 401 → HostExW (3 / 2) (GChi ψ).req
```

**In words:** for each primitive character ψ, the Tate–Shafarevich bound `VWinAt ψ 401` of note 3 implies the property `HostExW (3/2)` for that character's requirement. This is exactly the hypothesis `hS` of (b) at la = 3/2. The constant 3/2 here is the `la` that `TopPlug.lean` passes to (b).

### (d) Where `Green` and the 46 fields enter

**`UpperTheory.Top.shape_closed_link_n_of_green`**, `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopShape.lean`, line 33:

*Not verbatim; see the correction dated 2026-11-22 below for the exact text.*

```lean
theorem UpperTheory.Top.shape_closed_link_n_of_green : GlobalTheory.GLq.Green →
    GlobalTheory.Fc.TopShapeAlt True True (fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm) UpperTheory.Top.TopG
```

**In words:** Green's theorem implies a "shape" statement whose goal is `TopG`.

**`GlobalTheory.Fc.forall_goal_of_shape_of_hyps`**, `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/ShapeOf.lean`, line 31:

*Not verbatim; see the correction dated 2026-11-22 below for the exact text.*

```lean
theorem GlobalTheory.Fc.forall_goal_of_shape_of_hyps : ∀ (V NR : Prop) (N : FamClass → Prop) (G : Prop),
    GlobalTheory.Fc.TopShapeAlt V NR N G → V → NR → GlobalTheory.Fc.HypsAlt N GlobalTheory.Fc.DefiniteSideCondition → G
```

**In words:** a shape statement for a goal G, together with its two side propositions V and NR and an instance of the 46-field structure, yields G.

**Joined.** On the path, V and NR are both `True` (supplied by `trivial`), N is the closure condition `fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm`, and G is `TopG`. So: Green's theorem plus the 46-field structure gives `TopG`.

The shape notion `GlobalTheory.Fc.TopShapeAlt` is defined in `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopShapeAlt.lean`, line 24, and is opaque to me. The proof of `shape_closed_link_n_of_green` begins with one `intro` of 59 names (line 34, counted with `wc -w`). They run `hGreen`, then names matching the fields of `HypsAlt` and its selection functions, then `la G hla hH hV`. That is consistent with `TopShapeAlt` being "for every way of filling the fields, the goal holds", but I have not read its definition.

### (e) From primitive to all characters: `UpperTheory.Top.imprimitive`

`Development/AutomorphicArithmetic/CharacterBoxes/Imprimitive.lean`, line 5:

```lean
theorem UpperTheory.Top.imprimitive :
    ZeroFreeAll → ∀ (N : ℕ) [NeZero N] (χ : DirichletCharacter ℂ N) (s : ℂ), 1 / 2 < s.re → (χ ≠ 1 ∨ s ≠ 1) →
      DirichletCharacter.LFunction χ s ≠ 0
```

**In words:** if no primitive L-function vanishes to the right of 1/2, then no Dirichlet L-function does, apart from the pole. The conclusion is word for word the body of `UpperTheory.EveryCharacter`.

The proof's first lines (9-10) apply `ZeroFreeAll` to `PChar.of χ` to get L(χ*, s) ≠ 0 for the primitive character χ* inducing χ. This replaces the guess in note 1's interpretation section with a reading of the statement and of those two lines. That the rest of the proof passes through the finitely many Euler factors, as `Claim.prim_zero` in note 2 does for the strip, is still not read.

## Interpretation (ours; check it)

- **The architecture, as these statements show it.** The deep part splits into two independent halves:
  - A **character-by-character arithmetic half.** For each primitive ψ, the Tate–Shafarevich bound `VWinAt ψ 401` (note 3) supplies a "host" property `HostExW (3/2) (GChi ψ).req`.
  - A **uniform automorphic half.** Green's theorem and the 46 conditions of the theta-lift structure (note 4) supply `TopG`, a statement that holds for *every* requirement G at *every* scale la > 1.

  `zeroFreeAll_of_topG` then instantiates `TopG` at G = `GChi ψ` and la = 3/2 for each ψ. If this reading is right, the per-character input is only the host property; everything else is uniform in ψ.
- **What `TopG` concludes.** Its conclusion is `FamilyClassConnected`, not a statement about zeros. So the step from "the family class of ψ is connected" to "L(ψ, s) ≠ 0 for Re s > 1/2" is made inside the proof of `zeroFreeAll_of_topG`, which this note did not read. That proof is where the analytic number theory meets the rest. It is the natural next place to read.
- **The author's items.** Item 8 of the author's note ("Iterated theta lifts U(X₀) → U(X₁) → ⋯ → U(X_m) between totally definite unitary groups…") and item 17 (the Vandiver-type statement, note 3) fit the two halves above. This is a reading of names and file paths against the note, not a demonstration.

## Not read, not understood

- The definitions of `HostExW`, `GChi`, `FReq`, `HypV`, `FamilyClassConnected`, `TopShapeAlt` and `LinkN`.
- The proofs of all five theorems beyond the lines cited, in particular `zeroFreeAll_of_topG`, where the zeros appear.
- Why the scale is la = 3/2, and whether any la > 1 would do on the uniform half. `TopG` quantifies over all la > 1, while `supplyChi` fixes 3/2.

### Correction, 2026-11-22 (later the same day): the code block under "The chain" is a composition, not a quotation

The code block at the start of "What the library says" is labelled as how `UpperTheory.Top.every_character_of_green_v_win` writes the chain in `TopPlug.lean`, lines 12-18. It is not verbatim. Those lines hold TWO theorems, and the block showed them inlined into one term, without `h.elim` and without the `_root_` prefixes. The mathematics the block conveys is unchanged. Kepler found this while re-reading the file for the outline. The two theorems, verbatim:

```lean
theorem UpperTheory.Top.zero_free_all_of_green_v_win (hG : GlobalTheory.GLq.Green) (hV : UpperTheory.Top.VWin)
    (h : Nonempty (_root_.GlobalTheory.Fc.HypsAlt (fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm) _root_.GlobalTheory.Fc.DefiniteSideCondition)) : Formalism.HC.ZeroFreeAll :=
  h.elim fun h => UpperTheory.Top.zeroFreeAll_of_topG (la := 3 / 2) (by norm_num)
    (_root_.GlobalTheory.Fc.forall_goal_of_shape_of_hyps _ _ _ _ (_root_.UpperTheory.Top.shape_closed_link_n_of_green hG) trivial trivial h) fun ψ => UpperTheory.Top.supplyChi ψ (hV ψ)
theorem UpperTheory.Top.every_character_of_green_v_win (hG : GlobalTheory.GLq.Green) (hV : UpperTheory.Top.VWin)
    (h : Nonempty (_root_.GlobalTheory.Fc.HypsAlt (fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm) _root_.GlobalTheory.Fc.DefiniteSideCondition)) : UpperTheory.EveryCharacter :=
  UpperTheory.Top.imprimitive (_root_.UpperTheory.Top.zero_free_all_of_green_v_win hG hV h)
```

So `h` is a proof that the 46-field structure is *non-empty*, unpacked by `h.elim`. The sentence under the block, "`h` is the 46-field structure", should be read that way.


### Correction, 2026-11-22 (later the same day): three more code blocks were not verbatim

A read-only checker, written after the correction above, tests every `lean` block in these notes against the files each note lists. In this note it found three more blocks that are not exact quotations, besides the composed block corrected above. I wrote all three:
- the block under (a) joins three definitions and leaves out `ZeroFreeEven`, which sits between them in the file;
- the blocks under (d) drop the `_root_.` prefixes the source writes, and re-wrap the lines.

None changes what the statements say. Here they are verbatim. Each of the four original blocks (the composed one above and these three) now carries a one-line marker directly above it, pointing here, so a reader who lands on it sees that it is not exact; the blocks themselves are unchanged.

(a), `ExplicitFormulaErrorOfHostConditions.lean`, lines 11-18:

```lean
def PChar.ZeroFreeAbove (ψ : PChar) (θ : ℝ) : Prop :=
  ∀ s : ℂ, θ < s.re → DirichletCharacter.LFunction ψ.χ s ≠ 0

def ZeroFreeOn (Q : PChar → Prop) : Prop := ∀ ψ : PChar, Q ψ → ψ.ZeroFreeAbove (1 / 2)

def ZeroFreeEven : Prop := ZeroFreeOn fun ψ => ψ.χ.Even

def ZeroFreeAll : Prop := ZeroFreeOn fun _ => True
```

(d), `TopShape.lean`, line 33:

```lean
theorem UpperTheory.Top.shape_closed_link_n_of_green : GlobalTheory.GLq.Green → _root_.GlobalTheory.Fc.TopShapeAlt True True (fun 𝒞 => Closed 𝒞 fun Fm _ => LinkN Fm) UpperTheory.Top.TopG := by
```

(d), `ShapeOf.lean`, line 31:

```lean
theorem GlobalTheory.Fc.forall_goal_of_shape_of_hyps : ∀ (V NR : Prop) (N : FamClass → Prop) (G : Prop), _root_.GlobalTheory.Fc.TopShapeAlt V NR N G → V → NR → _root_.GlobalTheory.Fc.HypsAlt N _root_.GlobalTheory.Fc.DefiniteSideCondition → G :=
```


### Added 2026-11-24: how the three inputs give "no zeros to the right of 1/2"

In short: the three inputs supply, for each primitive character, families of windows, and two results the release proves for every level turn those windows into no zeros to the right of 1/2. The three inputs supply, for each primitive character and each small $\varepsilon$, families of hosts whose windows reach scale 3/2 and on whose windows a tied inequality holds; two results the release proves for every level then rule out zeros: an inequality bounding the level's weighted error term $E_\Lambda$ by $x^{1/2 + c\varepsilon}$, with $c = c_D + c_L + 7$, on the windows of any such family, and a Landau-type property (if $E_\Lambda(x) \le x^\theta$ on windows $[Y, Y^{\lambda}]$ lying beyond every point, with $0 < \theta < 1$, no $L$-function of the level vanishes for $\mathrm{Re}\ s > \theta$). In detail, the library's proofs of this step and of the pivot (step 3) name nine earlier results. Input 1, the window supply and the hypothesis package enter through three of them: two give the statement about classes of families from Input 1 and the package (step 1), and one gives each primitive character its host requirement at $\lambda = 3/2$ from the window supply (step 2). The pivot then checks the three hypotheses of the zero-free step for every primitive character: the window inequality and the Landau property, both proved for every level (see [note 6](06-where-the-zeros-enter.md), "The two supplied inputs"); the third, that such families exist, comes from the statement about classes of families: given the hosts and the fact that every family in the class satisfies the statement's condition, it supplies for each small $\varepsilon$ a family with windows at scale 3/2 and the tied inequality on them, and a second fact about every family in the class supplies the remaining condition on the family. The argument then works one point at a time (step 5): for $s$ with $\mathrm{Re}\ s > 1/2$ it sets $m = \min(\mathrm{Re}\ s - 1/2,\ 1/2)$, takes $\varepsilon$ so small that $(c_D + c_L + 7)\ \varepsilon \le m/2$, takes a family at that $\varepsilon$, and applies the Landau-type property with $\theta = 1/2 + m/2$ on the windows beyond $\max(x_1, 1)$, where $x_1$ is the point from which the window inequality holds. We read in full the proofs of this step and of the pivot, of the zero-free step and of the result it calls, of the Landau property, of the two facts about every family in the class and of the lemma that combines shape and package, and of the lemma that gives the shape from Input 1 and of the result that the combining lemma calls. We read the one-line proof of the window inequality and the proof of the result it calls, which applies the window bound ([note 9](09-the-window-bound.md)). We read the proof of the one-point argument and of the lemma that picks $\varepsilon$. We have not read the proof of the lemma that gives each character its host requirement beyond its first lines, or of the lemma that reduces the claim to one level at a time (step 4), the other result that the zero-free step's inner result applies.
<!-- rh-block {"date":"2026-11-23","decls":[{"module":"Development.AutomorphicArithmetic.ThetaCorrespondence.ThetaPairLifts.ThirdPlaceSeries.TopPlug","name":"UpperTheory.Top.zero_free_all_of_green_v_win"}],"file":"Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopPlug.lean","id":"05.b01","kind":"argument","lines":[12,15],"reader":"Halley","second_readers":[{"date":"2026-11-23","reader":"Kepler"}]} -->

### Added 2026-11-24: how `imprimitive` is proved, in one paragraph (Kepler)

In short: the $L$-function of any character is the $L$-function of the primitive character that induces it, times finitely many factors $1 - \chi^{\ast}(p)\ p^{-s}$, and none of these factors is zero when $\mathrm{Re}\ s > 1/2$. The library's proof of this step takes a character $\chi$ of modulus $N$ and $s$ with $\mathrm{Re}\ s > 1/2$, where $\chi \ne 1$ or $s \ne 1$. Let $\chi^{\ast}$ be the primitive character that induces $\chi$, as Mathlib constructs it; the library packs it, with the conductor of $\chi$ as its modulus, into its type of primitive characters, the type this step's hypothesis speaks about, and the hypothesis gives $L(s, \chi^{\ast}) \ne 0$. The exception carries over: if $\chi \ne 1$ then $\chi^{\ast} \ne 1$, because the trivial character raised to modulus $N$ is trivial, and otherwise $s \ne 1$. Under that condition Mathlib's lemma for a change of modulus gives $L(s, \chi) = L(s, \chi^{\ast}) \prod_{p \mid N} \bigl(1 - \chi^{\ast}(p)\ p^{-s}\bigr)$. A factor could be zero only if $\chi^{\ast}(p)\ p^{-s} = 1$, but $|\chi^{\ast}(p)| \le 1$ and $|p^{-s}| = p^{-\mathrm{Re}\ s} < 1$ (this bound needs only $\mathrm{Re}\ s > 0$; the proof has $\mathrm{Re}\ s > 1/2$). So the product is not zero, and $L(s, \chi) \ne 0$. The proof was read whole (the note's file table records less, from the note's first reading), and of the Mathlib lemmas this paragraph relies on, at the commit the release pins, the statements were read, not the proofs: the lemma for a change of modulus and three lemmas behind the two inequalities and the trivial character. The other Mathlib lemmas the proof names were not opened.
<!-- rh-block {"date":"2026-11-24","decls":[{"module":"Development.AutomorphicArithmetic.CharacterBoxes.Imprimitive","name":"UpperTheory.Top.imprimitive"}],"file":"Development/AutomorphicArithmetic/CharacterBoxes/Imprimitive.lean","id":"05.b02","kind":"argument","lines":[5,35],"reader":"Kepler","second_readers":[{"date":"2026-11-24","reader":"Halley"}]} -->

### Added 2026-11-24: the proof in order, a sketch (Halley)

The hypotheses are Input 1, the window supply for every primitive character, and one instance of the hypothesis package $\mathcal{H}$ (taken closed under links and with the definite side condition). The conclusion: for every primitive Dirichlet character $\chi$, $L(s,\chi) \ne 0$ when $\mathrm{Re}\ s > 1/2$. More of the library's files was read for this sketch than the note's file table records.

1. **A statement about classes of families, from Input 1 and the package.** Input 1 gives a shape closed under links, and that shape together with the instance of $\mathcal{H}$ gives a statement of this form: for every scale $\lambda > 1$ and every requirement, if the requirement is met at scale $\lambda$ (in the sense stated on the card that draws the conclusion from this statement and the hosts), and every family in the requirement's class satisfies a condition (note 11 states its definition), then the class has a certain property (note 11 states its definition; step 3 (c) says what it gives). The lemma that combines shape and package has two further side conditions; on this path both hold trivially.
2. **A host for each character, from the window supply.** For each primitive $\psi$, the window supply of $\psi$ gives that the requirement of $\psi$ is met at scale $\lambda = 3/2$. We read the statement of this lemma, not its proof.
3. **From that statement to the conclusion.** With $\lambda = 3/2$, the argument passes to the level $\Lambda_\psi$ of each primitive $\psi$ (the level that contains $\psi$). It needs three facts about that level, in which $E_\Lambda$ is the level's weighted error term:
   - **(a) the window inequality**, proved for every level: for a family that satisfies a condition on the family at the level (note 9 states what it requires) and the tied inequality with constants $c_D$ and $c_L$ (a condition on the family that holds at every large $x$ in its windows, for some further constants; note 13 states its definition and does not read the seven conditions it names), there is $x_1$ with $E_\Lambda(x) \le x^{1/2 + (c_D + c_L + 7)\varepsilon}$ for $x \ge x_1$ in the windows;
   - **(b) the Landau property**, proved for every level: for every $\lambda > 1$, if $E_\Lambda(x) \le x^\theta$ on windows $[Y, Y^{\lambda}]$ beyond every point, with $0 < \theta < 1$, then no $L$-function of the level vanishes for $\mathrm{Re}\ s > \theta$;
   - **(c) families at scale $3/2$**, from the statement of step 1: given step 2, and the fact that every family in the class satisfies the condition of step 1, it returns constants $c_D$, $c_L$ and $\varepsilon_1 > 0$ such that for each $\varepsilon < \varepsilon_1$ there is a family in the class, with windows at scale $3/2$ and the tied inequality on them. Every family in the class also satisfies the condition of (a).
4. **One level at a time.** The claim for all primitive characters reduces to: for each primitive $\psi$, the level $\Lambda_\psi$ is free of zeros to the right of $1/2$. We did not read the lemma that makes this reduction.
5. **One point at a time.** Fix $\psi$ in the level and $s$ with $\mathrm{Re}\ s > 1/2$, and let $m = \min(\mathrm{Re}\ s - 1/2,\ 1/2) > 0$.
   - Choose $\varepsilon$ with $0 < \varepsilon < \varepsilon_1$ and $(c_D + c_L + 7)\ \varepsilon \le m/2$; the proof takes $\varepsilon = \min(\varepsilon_1/2,\ (m/2)/(|C| + 1))$ with $C = c_D + c_L + 7$.
   - Fact (c) at that $\varepsilon$ gives a family; fact (a) gives $x_1$.
   - For $x \ge \max(x_1, 1)$ in the family's windows, $E_\Lambda(x) \le x^{1/2 + (c_D + c_L + 7)\varepsilon} \le x^{1/2 + m/2}$, because $x \ge 1$ and the exponent only grew.
   - The family's windows at scale $3/2$ give windows $[Y, Y^{3/2}]$ beyond $\max(x_1, 1)$, so fact (b) applies with $\theta = 1/2 + m/2$. Here $0 < \theta \le 3/4 < 1$, and $\theta < 1/2 + m \le \mathrm{Re}\ s$, so $L(s, \psi) \ne 0$.
<!-- rh-block {"basis":"source","date":"2026-11-24","decls":[{"module":"Development.AutomorphicArithmetic.ThetaCorrespondence.ThetaPairLifts.ThirdPlaceSeries.TopPlug","name":"UpperTheory.Top.zero_free_all_of_green_v_win"},{"module":"Development.AutomorphicArithmetic.CharacterBoxes.ZeroFreeAllOfTopG","name":"UpperTheory.Top.zeroFreeAll_of_topG"},{"module":"Formalism.SharpRestriction.RamificationFrobenius.TotientGaloisClasses.TopWin","name":"Formalism.HC.zeroFreeOn_of_tiedWin_cyc"},{"module":"Formalism.SharpRestriction.RamificationFrobenius.TotientGaloisClasses.TopWin","name":"Formalism.HC.zeroFreeOn_of_tiedWin"},{"module":"Formalism.SharpRestriction.RamificationFrobenius.TotientGaloisClasses.TopWin","name":"Formalism.HC.level_of_tiedWin"},{"module":"Formalism.SharpRestriction.RamificationFrobenius.TotientGaloisClasses.TopWin","name":"Formalism.HC.exists_small_eps"},{"module":"Development.AutomorphicArithmetic.CharacterBoxes.ZeroFreeAllOfTopG","name":"UpperTheory.Top.hypV_of_cls"},{"module":"Development.AutomorphicArithmetic.CharacterBoxes.ZeroFreeAllOfTopG","name":"UpperTheory.Top.eFamC_of_cls"}],"file":"Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopPlug.lean","id":"05.b03","kind":"sketch","lines":[12,15],"reader":"Halley","second_readers":[{"date":"2026-11-24","reader":"Kepler"}],"span":2,"unexpanded":["Step 3: that $1 \u003c 3/2$.","Step 3 (c): that a point $x \\ge x_1 + 1$ meets the family's bound $x_1$, in the two facts about every family of the class.","Step 5: that $0 \u003c m$; that $0 \u003c \\theta$ and $\\theta \u003c 1$; that $\\theta \u003c \\mathrm{Re}\\ s$; the exponent comparison $1/2 + (c_D + c_L + 7)\\varepsilon \\le 1/2 + m/2$, which is \"the exponent only grew\"; and the choice of $\\varepsilon$."],"unexpanded_detail":["`TopPlug.lean`, step 3: that $1 \u003c 3/2$ (`norm_num`, line 14)","`TopWin.lean`, step 5: in `level_of_tiedWin`, $0 \u003c m$ (`linarith` and `norm_num`, line 74), $0 \u003c \\theta$ and $\\theta \u003c 1$ (`linarith`, line 78), $\\theta \u003c \\mathrm{Re}\\ s$ (line 79) and the exponent comparison $1/2 + (\\mathrm{eD}+\\mathrm{eL}+7)\\varepsilon \\le 1/2 + m/2$ (line 81), which is \"the exponent only grew\"; in `exists_small_eps`, the choice of $\\varepsilon$ (`positivity`, line 60; `linarith`, lines 61-62; `nlinarith`, line 66)","`ZeroFreeAllOfTopG.lean`, step 3 (c): in `hypV_of_cls` and `eFamC_of_cls`, that a point $x \\ge x_1 + 1$ meets the family's bound $x_1$ (`linarith`, lines 17, 22 and 23)"]} -->

## Files this note was written from

Paths are relative to the release's `lean/src/`. Hashes are SHA-256 of the files as released, computed by me. Rows marked "location only" were opened only to find a definition's line, not read.

| File | SHA-256 |
|---|---|
| `Formalism/SharpRestriction/RamificationFrobenius/TotientGaloisClasses/ExplicitFormulaErrorOfHostConditions.lean` (lines 1-30) | `d6b12bcbdc15c1b717c33a712474f9fca18c577a65c41fff2b2937534e5447ba` |
| `Development/AutomorphicArithmetic/CharacterBoxes/ZeroFreeAllOfTopG.lean` (lines 1-27) | `349d9eafe63952c2fa4ccb2055bef7de0144d442c552196183fe48f01958f033` |
| `Development/AutomorphicArithmetic/CharacterBoxes/SupplyChi.lean` (lines 1-14) | `70a11ba909e03b9153a6beacce24da22f3224b8192ec6980b7f27018961be81b` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/ShapeOf.lean` (lines 25-33) | `c37a51fd244c4812302bf5d816a248e119ec9ed84089869752267ae741a61705` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopShape.lean` (lines 30-35) | `9647d4cbe444f79de90c7a5371801e83c58a040499bf03fd61faf37be9e6eaa3` |
| `Development/AutomorphicArithmetic/CharacterBoxes/Imprimitive.lean` (lines 1-10) | `8de85415d0d139f23b2b50ba56c18ab3b3e29740f41e2d86eaf99b95765f512e` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopPlug.lean` | `7d1d7972a4abe1284c5e4da9dd65a6eb605b06efb5e993b298fe5aaed88e9adf` |
| `Development/AutomorphicArithmetic/CharacterBoxes/Supply.lean` (location only) | `c57b63c82b55380b31aabae74ba797be099cd0edaba3de88387995fea2cfe31f` |
| `Development/AbelianVarietyTheory/Definitions/GlobalTwisting/ThinScalesIffHostBound.lean` (location only) | `413712d1bffa0ffc17a269690dbd21597d8eb1dd08452f943dfdcf535f607146` |
| `Development/AutomorphicArithmetic/ThetaCorrespondence/ThetaPairLifts/ThirdPlaceSeries/TopShapeAlt.lean` (location only) | `e72d8ae82e3c239cf46cf4bfb11fa82c9e16383a50ead1c1c8a8ba717ebe89fb` |
| `Development/AutomorphicArithmetic/CharacterBoxes/DivinNOfHypV.lean` (location only) | `cefdce360890e26405199ef8db01d6b0c7e044c4ebebeb6bbcfd23de6148bde0` |

The Mathlib check used Lean 4.33.1 and Mathlib at commit `0df444a3` with its prebuilt files, and no release file. Output: `riemannZeta_one : riemannZeta 1 = (↑Real.eulerMascheroniConstant - Complex.log (4 * ↑Real.pi)) / 2` and `riemannZeta_one_ne_zero : riemannZeta 1 ≠ 0`.
