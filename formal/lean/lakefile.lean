import Lake
open Lake DSL

package d10zCore where
  version := v!"2.4.0"

lean_lib D10ZCore where
  roots := #[`D10ZCore, `D10ZRefinement, `D10ZSystems, `D10ZSystemsExtra, `D10ZPythonBoundary]
