import D10ZSystems

namespace D10Z.PythonBoundary

/--
The executable Python boundary distinguishes contract rejections from unexpected
exceptions. Contract rejections are recoverable by the core loop; unexpected
exceptions escape the loop and must not be silently converted into rejection.
-/
inductive PythonOutcome (S : Type) where
  | committed (next : S)
  | contractRejected (prior : S) (code : String)
  | unexpectedException (prior : S) (kind : String)
  deriving Repr

def recoverContractViolation {S : Type} (prior : S) (outcome : PythonOutcome S) :
    PythonOutcome S :=
  match outcome with
  | .committed next => .committed next
  | .contractRejected _ code => .committed prior
  | .unexpectedException _ kind => .unexpectedException prior kind

theorem rejected_operation_keeps_prior_state {S : Type} (prior : S) (code : String) :
    recoverContractViolation prior (.contractRejected prior code) = .committed prior := by
  rfl

theorem unexpected_exception_propagates {S : Type} (prior : S) (kind : String) :
    recoverContractViolation prior (.unexpectedException prior kind) =
      .unexpectedException prior kind := by
  rfl

theorem committed_operation_keeps_candidate {S : Type} (prior next : S) :
    recoverContractViolation prior (.committed next) = .committed next := by
  rfl

/-- An abstraction relation for Python tuples/sets after canonical ID indexing. -/
structure PythonAbstractState (n : Nat) where
  ids : Fin n → String
  value : Fin n → Nat
  edge : Fin n → Fin n → Bool
  version : Nat
  idsInjective : Function.Injective ids

structure PythonConcreteView (n : Nat) where
  ids : Fin n → String
  value : Fin n → Nat
  edge : Fin n → Fin n → Bool
  version : Nat
  idsInjective : Function.Injective ids

def RepresentsPython {n : Nat} (a : PythonAbstractState n) (c : PythonConcreteView n) : Prop :=
  a.ids = c.ids ∧ a.value = c.value ∧ a.edge = c.edge ∧ a.version = c.version

def abstractUpdate {n : Nat} (s : PythonAbstractState n) (i : Fin n) (v : Nat) :
    PythonAbstractState n :=
  { s with value := fun j => if j = i then v else s.value j,
           version := s.version + 1 }

def concreteUpdate {n : Nat} (s : PythonConcreteView n) (i : Fin n) (v : Nat) :
    PythonConcreteView n :=
  { s with value := fun j => if j = i then v else s.value j,
           version := s.version + 1 }

theorem python_update_simulation {n : Nat} (a : PythonAbstractState n)
    (c : PythonConcreteView n) (h : RepresentsPython a c) (i : Fin n) (v : Nat) :
    RepresentsPython (abstractUpdate a i v) (concreteUpdate c i v) := by
  rcases h with ⟨hid, hv, he, hver⟩
  constructor
  · exact hid
  constructor
  · funext j
    simp [abstractUpdate, concreteUpdate, hv]
  constructor
  · exact he
  · simp [abstractUpdate, concreteUpdate, hver]

/--
This is a semantic contract for the Python recovery boundary, not a proof that
CPython itself or an arbitrary Python function is compiled into this model.
-/
end D10Z.PythonBoundary
