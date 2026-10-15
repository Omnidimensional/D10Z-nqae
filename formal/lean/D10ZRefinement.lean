import D10ZCore

namespace D10Z.Refinement

structure AbstractState (n : Nat) where
  ids : Fin n → String
  value : Fin n → Nat
  edge : Fin n → Fin n → Bool
  version : Nat
  idsInjective : Function.Injective ids

structure ConcreteView (n : Nat) where
  ids : Fin n → String
  value : Fin n → Nat
  edge : Fin n → Fin n → Bool
  version : Nat
  idsInjective : Function.Injective ids

def Represents {n : Nat} (a : AbstractState n) (c : ConcreteView n) : Prop :=
  a.ids = c.ids ∧ a.value = c.value ∧ a.edge = c.edge ∧ a.version = c.version

def abstractSetValue {n : Nat} (s : AbstractState n) (i : Fin n) (v : Nat) : AbstractState n :=
  { s with value := fun j => if j = i then v else s.value j,
           version := s.version + 1 }

def concreteSetValue {n : Nat} (s : ConcreteView n) (i : Fin n) (v : Nat) : ConcreteView n :=
  { s with value := fun j => if j = i then v else s.value j,
           version := s.version + 1 }

def abstractAddEdge {n : Nat} (s : AbstractState n) (src dst : Fin n) : AbstractState n :=
  { s with edge := fun x y => if x = src ∧ y = dst then true else s.edge x y,
           version := s.version + 1 }

def concreteAddEdge {n : Nat} (s : ConcreteView n) (src dst : Fin n) : ConcreteView n :=
  { s with edge := fun x y => if x = src ∧ y = dst then true else s.edge x y,
           version := s.version + 1 }

def abstractRemoveEdge {n : Nat} (s : AbstractState n) (src dst : Fin n) : AbstractState n :=
  { s with edge := fun x y => if x = src ∧ y = dst then false else s.edge x y,
           version := s.version + 1 }

def concreteRemoveEdge {n : Nat} (s : ConcreteView n) (src dst : Fin n) : ConcreteView n :=
  { s with edge := fun x y => if x = src ∧ y = dst then false else s.edge x y,
           version := s.version + 1 }

theorem setValue_refines {n : Nat} (a : AbstractState n) (c : ConcreteView n)
    (h : Represents a c) (i : Fin n) (v : Nat) :
    Represents (abstractSetValue a i v) (concreteSetValue c i v) := by
  rcases h with ⟨hid, hv, he, hver⟩
  constructor
  · exact hid
  constructor
  · funext j
    simp [abstractSetValue, concreteSetValue, hv]
  constructor
  · exact he
  · simp [abstractSetValue, concreteSetValue, hver]

theorem addEdge_refines {n : Nat} (a : AbstractState n) (c : ConcreteView n)
    (h : Represents a c) (src dst : Fin n) :
    Represents (abstractAddEdge a src dst) (concreteAddEdge c src dst) := by
  rcases h with ⟨hid, hv, he, hver⟩
  constructor
  · exact hid
  constructor
  · exact hv
  constructor
  · funext x
    funext y
    simp [abstractAddEdge, concreteAddEdge, he]
  · simp [abstractAddEdge, concreteAddEdge, hver]

theorem removeEdge_refines {n : Nat} (a : AbstractState n) (c : ConcreteView n)
    (h : Represents a c) (src dst : Fin n) :
    Represents (abstractRemoveEdge a src dst) (concreteRemoveEdge c src dst) := by
  rcases h with ⟨hid, hv, he, hver⟩
  constructor
  · exact hid
  constructor
  · exact hv
  constructor
  · funext x
    funext y
    simp [abstractRemoveEdge, concreteRemoveEdge, he]
  · simp [abstractRemoveEdge, concreteRemoveEdge, hver]

inductive StepResult (S : Type) where
  | accepted (next : S)
  | rejected (prior : S) (code : String)
  deriving Repr

def recoverResult {S : Type} (prior : S) (r : StepResult S) : S :=
  match r with
  | .accepted next => next
  | .rejected _ _ => prior

theorem rejection_preserves_prior {S : Type} (s : S) (code : String) :
    recoverResult s (.rejected s code) = s := by
  rfl

end D10Z.Refinement
