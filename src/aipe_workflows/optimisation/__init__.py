"""Parameter iteration and optimisation coordination.

``iterate`` derives a new run from an existing one by changing specification
inputs (for example a transformer turns ratio proposed by the magnetics
design), re-executes exactly the tasks whose inputs changed and everything
downstream of them, compares the key observables with the parent run and
records an accept/reject decision with its reasons in an iteration ledger.
Nothing is overwritten: every iteration is a new run directory that points at
its parent.
"""

from .iterate import IterationRecord, apply_changes, compare_runs, iterate_run  # noqa: F401
