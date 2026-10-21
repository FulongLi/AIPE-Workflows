"""AIPE-Workflows: system-level engineering workflow execution.

The engine owns the directed acyclic task graph, dependency ordering, typed
inputs/outputs, checkpoints and resumability, execution logs and artifact
management, capability discovery against the AIPE Registry, local tool
qualification, verification gates and report assembly. Specialist solvers and
databases stay in their own repositories and are reached through thin adapters.

Package layout::

    engine/               task graph, run state, checkpointed execution
    scheduler/            dependency ordering and selective re-execution
    capability_discovery/ Registry index and sibling-manifest discovery
    environment/          tool detection, qualification tests, environment manifest
    adapters/             specialist capability adapters (Design-Agent, Simulation-Skills, ...)
    engineering_state/    Core Engineering State loading, validation and provenance-preserving updates
    artifacts/            hashed artifact store and references
    verification/         engineering validation gates and status ledger
    optimisation/         candidate iteration bookkeeping
    reporting/            Markdown/JSON report assembly
"""

__version__ = "0.1.0"
