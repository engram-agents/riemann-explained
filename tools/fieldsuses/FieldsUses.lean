/-
fields/uses classifier, v1 (Halley, 2026-11-23). What it reports: README.md. Tests, written first: controls/expected.json.

Reads elaborated terms (`ConstantInfo.value?`) of compiled modules. Read-only. Run with the toolchain `lean` binary:
  LEAN_PATH=<module dirs> lean --run FieldsUses.lean -- --module M uses DECL [--follow N]
  LEAN_PATH=<module dirs> lean --run FieldsUses.lean -- --module M who_reads S.field
Never `lake`.

Labels for each leading binder of the declaration's value:
  unused, direct, passed_whole, instance_only, returned, in_types_only.
`in_types_only` is shown only when no value label applies (spec Q1).

`--mutate i|ii|iii` plants the spec's three bugs, for the mutation check only.
-/
import Lean
open Lean

namespace FU

structure Bug where
  instAsExplicit : Bool := false   -- (i)  instance-implicit slots treated as explicit
  projNoIndex    : Bool := false   -- (ii) projections / destructuring do not read the index
  noRenaming     : Bool := false   -- (iii) no reduction through `have`/let/beta renamings

inductive Label | unused | direct | passedWhole | instanceOnly | returned | inTypesOnly
  deriving BEq, Inhabited

def Label.str : Label → String
  | .unused => "unused" | .direct => "direct" | .passedWhole => "passed_whole"
  | .instanceOnly => "instance_only" | .returned => "returned" | .inTypesOnly => "in_types_only"

/-- A local that stands for a component of one tracked binder. `pos`/`named` are the path components. -/
structure Alias where
  binder : Nat
  pos    : Array String := #[]
  named  : Array String := #[]
  isRoot : Bool := true

structure Occ where
  binder : Nat
  label  : Label
  pos    : Array String := #[]
  named  : Array String := #[]
  callee : String := ""
  argPos : Int := -1
  kind   : String := ""
  field  : String := ""

structure Ctx where
  inType    : Bool := false
  resultPos : Bool := false
  field     : String := ""
  enclosing : String := ""
  encPos    : Int := -1
  depth     : Nat := 0

structure Cfg where
  env  : Environment
  bug  : Bug
  decl : Name

structure St where
  next     : Nat := 0
  aliases  : Std.HashMap FVarId Alias := {}
  occs     : Array Occ := #[]
  followed : Array Name := #[]
  notes    : Array String := #[]

abbrev M := ReaderT Cfg (StateM St)

def fresh (a : Option Alias) : M Expr := do
  let s ← get
  let id : FVarId := ⟨Name.mkNum `_fu s.next⟩
  let aliases := match a with
    | some al => s.aliases.insert id al
    | none => s.aliases
  set { s with next := s.next + 1, aliases := aliases }
  return .fvar id

def record (o : Occ) : M Unit := modify fun s => { s with occs := s.occs.push o }

def note (msg : String) : M Unit := modify fun s =>
  if s.notes.contains msg then s else { s with notes := s.notes.push msg }

/-- One path step. Bug (ii) drops the index: the path does not grow. -/
def extend (al : Alias) (idx : Nat) (fname : String) : M Alias := do
  if (← read).bug.projNoIndex then
    return { al with isRoot := false }
  return { al with pos := al.pos.push (toString (idx + 1)), named := al.named.push fname, isRoot := false }

def lastComponent (n : Name) : String :=
  match n with
  | .str _ s => s
  | .num _ k => toString k
  | .anonymous => "?"

/-- Binder names of a constructor's fields (after its parameters). -/
def ctorFieldNames (env : Environment) (ctor : Name) : Array String := Id.run do
  let some (.ctorInfo cv) := env.find? ctor | return #[]
  let mut t := cv.type
  let mut i := 0
  let mut out := #[]
  while true do
    match t with
    | .forallE n _ b _ =>
      if i ≥ cv.numParams then out := out.push (lastComponent n)
      i := i + 1
      t := b
    | .mdata _ b => t := b
    | _ => break
  return out

def structFieldName (env : Environment) (sname : Name) (idx : Nat) : String :=
  match env.find? sname with
  | some (.inductInfo iv) =>
    match iv.ctors with
    | [c] => (ctorFieldNames env c)[idx]?.getD (toString (idx + 1))
    | _ => toString (idx + 1)
  | _ => toString (idx + 1)

/-- Binder infos of a constant's type, in order. -/
def binderInfos (env : Environment) (c : Name) : Array BinderInfo := Id.run do
  let some ci := env.find? c | return #[]
  let mut t := ci.type
  let mut out := #[]
  while true do
    match t with
    | .forallE _ _ b bi => out := out.push bi; t := b
    | .mdata _ b => t := b
    | _ => break
  return out

def isCtor (env : Environment) (c : Name) : Bool :=
  match env.find? c with
  | some (.ctorInfo _) => true
  | _ => false

/-- Auxiliary declarations made by elaboration, which the tool follows instead of reporting. -/
def isAux (env : Environment) (decl c : Name) : Bool :=
  Lean.Meta.isMatcherCore env c ||
  (decl.isPrefixOf c && c != decl && c.isInternal)

/-- Resolve an expression to a component of a tracked binder: the alias itself, `Expr.proj`,
    or a structure projection function applied to exactly its structure argument. -/
partial def resolve (e : Expr) : M (Option Alias) := do
  let cfg ← read
  match e with
  | .fvar id => return (← get).aliases.get? id
  | .mdata _ b => resolve b
  | .proj sn i s =>
    match ← resolve s with
    | some al => return some (← extend al i (structFieldName cfg.env sn i))
    | none => return none
  | .app .. =>
    match e.getAppFn with
    | .const c _ =>
      match cfg.env.getProjectionFnInfo? c with
      | some info =>
        let args := e.getAppArgs
        if args.size == info.numParams + 1 then
          match ← resolve args[info.numParams]! with
          | some al => return some (← extend al info.i (lastComponent c))
          | none => return none
        else return none
      | none => return none
    | _ => return none
  | _ => return none

def occOf (al : Alias) (lab : Label) (ctx : Ctx) (kind : String) : Occ :=
  { binder := al.binder, label := lab, pos := al.pos, named := al.named, kind := kind, field := ctx.field,
    callee := ctx.enclosing, argPos := ctx.encPos }

mutual

/-- Record one occurrence of a resolved alias at a position with no argument slot of its own. -/
partial def useAlias (al : Alias) (ctx : Ctx) (kind : String) : M Unit := do
  if ctx.inType then record (occOf al .inTypesOnly ctx kind)
  else if !al.isRoot then record (occOf al .direct ctx kind)
  else if ctx.resultPos then record (occOf al .returned ctx kind)
  else record (occOf al .passedWhole ctx kind)

partial def go (e : Expr) (ctx : Ctx) : M Unit := do
  if ctx.depth > 200 then note "depth limit 200 reached; a subterm was not read"; return
  -- A whole expression that is a component of a tracked binder.
  if let some al ← resolve e then
    useAlias al ctx (if al.isRoot then "occurs" else "proj")
    scanChainParams e ctx
    return
  match e with
  | .mdata _ b => go b ctx
  | .proj _ _ s => go s { ctx with resultPos := false }
  | .lam _ t b _ =>
    go t { ctx with inType := true }
    let x ← fresh none
    go (b.instantiate1 x) ctx
  | .forallE _ t b _ =>
    go t { ctx with inType := true }
    let x ← fresh none
    go (b.instantiate1 x) { ctx with inType := true }
  | .letE n t v b _ => goLet n t v b ctx
  | .app .. => goApp e ctx
  | _ => pure ()

/-- The parameter arguments along a resolved projection chain (e.g. `p q` in `@And.right p q h`) occur in types. -/
partial def scanChainParams (e : Expr) (ctx : Ctx) : M Unit := do
  let cfg ← read
  match e with
  | .mdata _ b => scanChainParams b ctx
  | .proj _ _ s => scanChainParams s ctx
  | .app .. =>
    match e.getAppFn with
    | .const c _ =>
      if let some info := cfg.env.getProjectionFnInfo? c then
        let args := e.getAppArgs
        for k in [0:info.numParams] do
          if h : k < args.size then go args[k] { ctx with inType := true, resultPos := false }
        if h : info.numParams < args.size then scanChainParams args[info.numParams] ctx
    | _ => pure ()
  | _ => pure ()

partial def goLet (n : Name) (t v b : Expr) (ctx : Ctx) : M Unit := do
  go t { ctx with inType := true }
  if !(← read).bug.noRenaming then
    if let some al ← resolve v then
      -- `have h2 := h` (or `h.2`): h2 stands for the same component.
      let x ← fresh (some al)
      go (b.instantiate1 x) ctx
      return
  go v { ctx with resultPos := false, enclosing := s!"let {n}", encPos := -1 }
  let x ← fresh none
  go (b.instantiate1 x) ctx

partial def goArgs (callee : String) (infos : Array BinderInfo) (args : Array Expr) (start : Nat)
    (ctx : Ctx) (ctorRes : Option Name) : M Unit := do
  let cfg ← read
  let fieldNames := match ctorRes with
    | some c => ctorFieldNames cfg.env c
    | none => #[]
  let nParams := match ctorRes with
    | some c => match cfg.env.find? c with
      | some (.ctorInfo cv) => cv.numParams
      | _ => 0
    | none => 0
  for k in [start:args.size] do
    let a := args[k]!
    let bi := infos[k]?.getD .default
    let bi := if cfg.bug.instAsExplicit && bi == .instImplicit then .default else bi
    let fieldHere := match ctorRes with
      | some _ => if ctx.field == "" && k ≥ nParams then (fieldNames[k - nParams]?.getD "") else ctx.field
      | none => ctx.field
    let sub : Ctx := { ctx with
      resultPos := ctx.resultPos && ctorRes.isSome,
      field := fieldHere, enclosing := callee, encPos := k, depth := ctx.depth + 1 }
    match ← resolve a with
    | some al =>
      if ctx.inType || bi == .implicit || bi == .strictImplicit then
        record (occOf al .inTypesOnly sub "implicit slot")
      else if !al.isRoot then
        record (occOf al .direct sub "proj")
      else if bi == .instImplicit then
        record (occOf al .instanceOnly sub "instance slot")
      else if sub.resultPos then
        record (occOf al .returned sub "constructor field")
      else
        record (occOf al .passedWhole sub "argument")
    | none =>
      let inT := ctx.inType || bi == .implicit || bi == .strictImplicit
      go a { sub with inType := inT }

partial def goApp (e : Expr) (ctx : Ctx) : M Unit := do
  let cfg ← read
  let fn := e.getAppFn
  let args := e.getAppArgs
  match fn with
  | .lam .. =>
    if cfg.bug.noRenaming then
      go fn { ctx with resultPos := false }
      goArgs "<lambda>" #[] args 0 ctx none
    else
      go (e.headBeta) ctx
  | .mdata _ b => go (mkAppN b args) ctx
  | .fvar id =>
    match (← get).aliases.get? id with
    | some al =>
      -- the binder (or a component) applied as a function
      record (occOf al (if ctx.inType then .inTypesOnly else .direct) ctx "applied")
      goArgs s!"<applied {al.binder}>" #[] args 0 { ctx with resultPos := false } none
    | none => goArgs "<local function>" #[] args 0 { ctx with resultPos := false } none
  | .const c us =>
    -- `letFun v f` (older `have` encoding)
    if c == ``letFun && args.size ≥ 4 then
      match args[3]! with
      | .lam n t b _ => goLet n t args[2]! b ctx; for a in args[4:] do go a { ctx with resultPos := false }
      | _ => goArgs (toString c) (binderInfos cfg.env c) args 0 ctx none
      return
    -- auxiliary declarations: inline their value and keep reading
    if isAux cfg.env cfg.decl c then
      match cfg.env.find? c with
      | some ci =>
        match ci.value? (allowOpaque := true) with
        | some v =>
          modify fun s => if s.followed.contains c then s else { s with followed := s.followed.push c }
          let v := v.instantiateLevelParams ci.levelParams us
          go (v.beta args) { ctx with depth := ctx.depth + 1 }
          return
        | none => pure ()
      | none => pure ()
    -- projection function applied to its structure argument and more
    if let some info := cfg.env.getProjectionFnInfo? c then
      if args.size > info.numParams + 1 then
        let pre := mkAppN fn (args.extract 0 (info.numParams + 1))
        if let some al ← resolve pre then
          useAlias al { ctx with resultPos := false } "proj applied"
          goArgs (toString c) #[] args (info.numParams + 1) { ctx with resultPos := false } none
          return
    -- casesOn on a tracked binder: fields become aliases of the binder's components
    if isCasesOnRecursor cfg.env c then
      if let some (.inductInfo iv) := cfg.env.find? c.getPrefix then
        let majorIdx := iv.numParams + 1 + iv.numIndices
        if h : majorIdx < args.size then
          if let some al ← resolve args[majorIdx] then
            record (occOf al (if ctx.inType then .inTypesOnly else .direct) ctx "cases")
            for k in [0:majorIdx] do go args[k]! { ctx with inType := true, resultPos := false }
            let mut j := 0
            for ctor in iv.ctors do
              let mi := majorIdx + 1 + j
              if hm : mi < args.size then
                let some (.ctorInfo cv) := cfg.env.find? ctor | pure ()
                let names := ctorFieldNames cfg.env ctor
                let mut body := args[mi]
                for f in [0:cv.numFields] do
                  match body with
                  | .lam _ _ b _ =>
                    let al' ← extend al f (names[f]?.getD (toString (f + 1)))
                    let x ← fresh (some al')
                    body := b.instantiate1 x
                  | _ => pure ()
                go body ctx
              j := j + 1
            let afterMinors := majorIdx + 1 + iv.ctors.length
            for k in [afterMinors:args.size] do go args[k]! { ctx with resultPos := false }
            return
    let ctorRes := if ctx.resultPos && isCtor cfg.env c then some c else none
    goArgs (toString c) (binderInfos cfg.env c) args 0 ctx ctorRes
  | _ =>
    go fn { ctx with resultPos := false }
    goArgs "<expr>" #[] args 0 { ctx with resultPos := false } none

end

structure BinderReport where
  idx     : Nat
  name    : String
  bi      : String
  labels  : Array String
  paths   : Array (String × String)   -- maximal read paths: (positional, named)
  passed  : Array (String × Int)
  flows   : Array String
  occs    : Array Occ

def isPrefixArr (a b : Array String) : Bool :=
  a.size < b.size && (List.range a.size).all (fun i => a[i]! == b[i]!)

def summarize (idx : Nat) (name : String) (bi : BinderInfo) (occs : Array Occ) : BinderReport :=
  let mine := occs.filter (·.binder == idx)
  let value := mine.filter (·.label != .inTypesOnly)
  let labs : Array Label :=
    if value.isEmpty then (if mine.isEmpty then #[.unused] else #[.inTypesOnly])
    else value.foldl (fun acc o => if acc.contains o.label then acc else acc.push o.label) #[]
  let direct := value.filter (·.label == .direct)
  let maximal := direct.filter (fun o => !direct.any (fun o' => isPrefixArr o.pos o'.pos))
  let paths := maximal.foldl (fun acc o =>
    let p := ("." ++ ".".intercalate o.pos.toList, "." ++ ".".intercalate o.named.toList)
    let p := if o.pos.isEmpty then ("", "") else p
    if acc.contains p then acc else acc.push p) #[]
  let passed := value.filter (fun o => o.label == .passedWhole || o.label == .instanceOnly)
    |>.foldl (fun acc o => if acc.contains (o.callee, o.argPos) then acc else acc.push (o.callee, o.argPos)) #[]
  let flows := value.foldl (fun acc o => if o.field != "" && !acc.contains o.field then acc.push o.field else acc) #[]
  let biStr := match bi with
    | .default => "explicit" | .implicit => "implicit" | .strictImplicit => "strict_implicit" | .instImplicit => "inst_implicit"
  { idx, name, bi := biStr, labels := labs.map Label.str, paths, passed, flows, occs := mine }

structure DeclReport where
  binders  : Array BinderReport
  followed : Array Name
  notes    : Array String

def analyze (env : Environment) (bug : Bug) (decl : Name) (v : Expr) : DeclReport := Id.run do
  let cfg : Cfg := { env, bug, decl }
  let act : M (Array (Nat × String × BinderInfo)) := do
    let mut e := v
    let mut bs := #[]
    let mut i := 0
    while true do
      match e with
      | .lam n t b bi =>
        -- a binder's own type can mention earlier binders (`hf : f n h`): those are in-type occurrences
        go t { inType := true }
        let x ← fresh (some { binder := i })
        -- anonymous binders (`[Field K]`) carry macro scopes; show them as `inst✝<index>`
        let shown := if n.hasMacroScopes then s!"{lastComponent n.eraseMacroScopes}✝{i}" else lastComponent n
        bs := bs.push (i, shown, bi)
        e := b.instantiate1 x
        i := i + 1
      | .mdata _ b => e := b
      | _ => break
    go e { resultPos := true }
    return bs
  let (bs, st) := (act.run cfg).run {}
  let reps := bs.map (fun (i, n, bi) => summarize i n bi st.occs)
  return { binders := reps, followed := st.followed, notes := st.notes }

-- JSON rendering

def occJson (o : Occ) : Json :=
  Json.mkObj [("label", o.label.str), ("kind", o.kind),
    ("path", "." ++ ".".intercalate o.pos.toList), ("named", "." ++ ".".intercalate o.named.toList),
    ("callee", o.callee), ("pos", o.argPos), ("field", o.field)]

def binderJson (b : BinderReport) (follow : Array Json) : Json :=
  Json.mkObj [("index", b.idx), ("name", b.name), ("binder_info", b.bi),
    ("labels", toJson b.labels),
    ("paths", Json.arr (b.paths.map fun (p, n) => Json.mkObj [("path", p), ("named", n)])),
    ("passed", Json.arr (b.passed.map fun (c, k) => Json.mkObj [("callee", c), ("pos", k)])),
    ("flows_into", toJson b.flows),
    ("follow", Json.arr follow),
    ("occurrences", Json.arr (b.occs.map occJson))]

partial def followJson (env : Environment) (bug : Bug) (b : BinderReport) (depth : Nat) : Array Json := Id.run do
  let mut out := #[]
  for (callee, k) in b.passed do
    let calleeName := callee.toName
    if depth == 0 then
      out := out.push (Json.mkObj [("callee", callee), ("pos", k), ("not_followed", "depth")])
      continue
    match env.find? calleeName with
    | none => out := out.push (Json.mkObj [("callee", callee), ("pos", k), ("not_followed", "not loaded")])
    | some ci =>
      match ci.value? (allowOpaque := true) with
      | none => out := out.push (Json.mkObj [("callee", callee), ("pos", k), ("not_followed", "no body")])
      | some v =>
        let r := analyze env bug calleeName v
        match r.binders[k.toNat]? with
        | none => out := out.push (Json.mkObj [("callee", callee), ("pos", k), ("not_followed", "position beyond the value's binders")])
        | some cb =>
          out := out.push (Json.mkObj [("callee", callee), ("pos", k), ("binder", cb.name),
            ("labels", toJson cb.labels),
            ("paths", Json.arr (cb.paths.map fun (p, n) => Json.mkObj [("path", p), ("named", n)])),
            ("follow", Json.arr (followJson env bug cb (depth - 1)))])
  return out

-- who_reads S.field over the loaded environment

partial def readsField (env : Environment) (sname : Name) (idx : Nat) (projFn : Name) (e : Expr) : Bool :=
  let rec visit (e : Expr) : Bool :=
    match e with
    | .proj sn i s => (sn == sname && i == idx) || visit s
    | .const c _ => c == projFn
    | .app f a =>
      let fn := e.getAppFn
      let casesHit := match fn with
        | .const c _ =>
          if c == sname ++ `casesOn then
            match env.find? sname with
            | some (.inductInfo iv) =>
              let args := e.getAppArgs
              let mi := iv.numParams + 1 + iv.numIndices + 1
              match args[mi]? with
              | some minor => fieldVarUsed minor idx
              | none => false
            | _ => false
          else false
        | _ => false
      casesHit || visit f || visit a
    | .lam _ t b _ | .forallE _ t b _ => visit t || visit b
    | .letE _ t v b _ => visit t || visit v || visit b
    | .mdata _ b => visit b
    | _ => false
  visit e
where
  /-- In a minor premise `fun f0 f1 ... => body`, does field `idx`'s variable occur in the body? -/
  fieldVarUsed (minor : Expr) (idx : Nat) : Bool := Id.run do
    let mut m := minor
    let mut n := 0
    let mut binders : Nat := 0
    while true do
      match m with
      | .lam _ _ b _ => m := b; binders := binders + 1; n := n + 1
      | _ => break
    if idx < binders then m.hasLooseBVar (binders - 1 - idx) else false

end FU

open FU in
def usage : String :=
  "usage: lean --run FieldsUses.lean -- --module M [--module M2 ...] [--follow N] [--mutate i|ii|iii] (uses DECL | who_reads S.field)"

open FU in
unsafe def main (argv : List String) : IO UInt32 := do
  let mut mods : Array Name := #[]
  let mut follow : Nat := 0
  let mut bug : Bug := {}
  let mut rest : List String := []
  let mut as := argv
  while !as.isEmpty do
    match as with
    | "--module" :: m :: t => mods := mods.push m.toName; as := t
    | "--follow" :: n :: t => follow := n.toNat!; as := t
    | "--mutate" :: "i" :: t => bug := { bug with instAsExplicit := true }; as := t
    | "--mutate" :: "ii" :: t => bug := { bug with projNoIndex := true }; as := t
    | "--mutate" :: "iii" :: t => bug := { bug with noRenaming := true }; as := t
    | "--" :: t => as := t
    | x :: t => rest := rest ++ [x]; as := t
    | [] => as := []
  if mods.isEmpty || rest.length < 2 then
    IO.eprintln usage; return 1
  initSearchPath (← findSysroot)
  -- a missing .olean is exit 3, naming the module; never an empty answer
  for m in mods do
    let sp ← searchPathRef.get
    match ← (sp.findWithExt "olean" m) with
    | some _ => pure ()
    | none => IO.eprintln s!"error: module {m} has no compiled .olean on LEAN_PATH (not compiled yet?)"; return 3
  enableInitializersExecution
  let env ← importModules (mods.map fun m => { module := m }) {} (loadExts := true)
  let query := rest[0]!
  let targets := (rest.drop 1).map String.toName
  let target := targets.head!
  let header := Json.mkObj [("lean_version", Lean.versionString), ("modules_requested", toJson (mods.map toString)),
    ("modules_loaded", env.header.moduleNames.size), ("query", query), ("targets", toJson (targets.map toString)),
    ("follow", follow),
    ("mutation", toJson ((if bug.instAsExplicit then #["i"] else #[]) ++ (if bug.projNoIndex then #["ii"] else #[]) ++ (if bug.noRenaming then #["iii"] else #[])))]
  match query with
  | "uses" =>
   let mut outs : Array Json := #[]
   for target in targets do
    match env.find? target with
    | none =>
      IO.eprintln s!"error: declaration {target} not found in the loaded environment (modules: {mods.toList})"; return 2
    | some ci =>
      match ci.value? (allowOpaque := true) with
      | none =>
        let why := match ci with
          | .axiomInfo _ => "axiom" | .opaqueInfo _ => "opaque without value" | .quotInfo _ => "quotient primitive"
          | .inductInfo _ => "inductive type" | .ctorInfo _ => "constructor" | .recInfo _ => "recursor"
          | _ => "no value"
        outs := outs.push (Json.mkObj [("scope", header), ("decl", toString target), ("no_body", why)])
      | some v =>
        let r := analyze env bug target v
        let sorryNote := if v.hasSorry then #["the body contains sorry"] else #[]
        let bs := r.binders.map fun b => binderJson b (followJson env bug b follow)
        outs := outs.push (Json.mkObj [("scope", header), ("decl", toString target),
          ("binders", Json.arr bs), ("followed", toJson (r.followed.map toString)),
          ("notes", toJson (r.notes ++ sorryNote))])
   IO.println (if outs.size == 1 then outs[0]! else Json.arr outs).pretty
   return 0
  | "who_reads" =>
    let sname := target.getPrefix
    let fname := lastComponent target
    let some (.inductInfo iv) := env.find? sname | IO.eprintln s!"error: structure {sname} not found"; return 2
    let [ctor] := iv.ctors | IO.eprintln s!"error: {sname} is not a structure"; return 2
    let names := ctorFieldNames env ctor
    let some idx := names.findIdx? (· == fname) | IO.eprintln s!"error: {sname} has no field {fname}"; return 2
    let mut hits : Array Json := #[]
    let mut scanned : Nat := 0
    for (n, ci) in env.constants.toList do
      match ci.value? (allowOpaque := true) with
      | some v =>
        scanned := scanned + 1
        if n != target && FU.readsField env sname idx target v then
          let modIdx := env.getModuleIdxFor? n
          let modName := match modIdx with
            | some i => toString (env.header.moduleNames[i.toNat]!)
            | none => "(this file)"
          hits := hits.push (Json.mkObj [("decl", toString n), ("module", modName)])
      | none => pure ()
    IO.println (Json.mkObj [("scope", header), ("field", toString target), ("index", idx),
      ("declarations_scanned", scanned), ("readers", Json.arr hits)]).pretty
    return 0
  | _ => IO.eprintln usage; return 1
