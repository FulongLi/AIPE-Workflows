# AIPE — Workflows

AIPE-Workflows is the system-level engineering workflow engine of the AIPE ecosystem. It turns the
specialist repositories (electrical and thermal design, circuit and field simulation, device and
magnetics databases, CAD and PCB agents) into one coordinated, reproducible task graph with
checkpoints, provenance and verification gates. It owns *how* engineering work is sequenced, checked
and recorded; every computation is performed by a specialist repository behind a thin adapter and
enters the AIPE-Core Engineering State with evidence. The first benchmark is the simulation-driven
10 kW dual active bridge (800 V → 400 V, 100 kHz, single phase shift).

## Features

- Versioned `workflow.yaml` task graphs with typed bindings, dependency ordering and JSON-Schema validation
- Checkpointed execution: input-hash reuse, stale-downstream re-execution, hashed artifacts, execution envelopes
- Engineering State proposals validated with AIPE-Core's own validator; every state version preserved
- Local tool detection and numerical qualification (ngspice, KiCad, FreeCAD, Gmsh, Elmer)
- Verification gate ledger from software to hardware qualification; later gates are never implied by earlier ones
- Feedback loops: `iterate` child runs and `reconcile` of circuit parameters with magnetics/FEM results
- JSON, Markdown and HTML review packages (AIPE-Doc template)

## Installation

```sh
python -m pip install -e .            # the engine (Python ≥ 3.10)
aipe-workflows doctor --qualify       # detect and qualify the local engineering tools
```

Specialist stages need their sibling repositories installed (`docs/usage.md`); a missing tool or package
blocks the affected tasks and is reported, never faked.

## Usage

```sh
aipe-workflows plan examples/dab-10kw/specification.yaml --checkouts ..
aipe-workflows run  examples/dab-10kw/specification.yaml --checkouts ..
aipe-workflows verify <run-id> && aipe-workflows report <run-id>
aipe-workflows reconcile <run-id> --apply --checkouts ..     # re-simulate with the magnetics/FEM parameters
```

The executed 10 kW DAB review package (report, envelopes, FEM/CAD results, measurement requests) is in
`examples/dab-10kw/results/`.

## Project Information

- Version: 0.1.0
- Status: Prototype (software, circuit-simulation and field-simulation gates executed on the benchmark; PCB
  checks executed, boards not finished; no measurement or hardware qualification)
- Developer: Fulong Li
- Organisation: Spirit Connect / AIPE Labs
- License: MIT (specialist repositories keep their own licences; vendor data is referenced, never redistributed)

## Documentation

- [Usage and installation of the specialist stack](docs/usage.md)
- [Architecture](docs/architecture.md) · [Execution envelope](docs/execution-envelope.md)
- [DAB workflow definition](workflows/converter_dab/README.md) · [10 kW DAB example and results](examples/dab-10kw/README.md)
- [Capability matrix](docs/capability-matrix.md) · [Status report 2026-10-21](docs/status-report-2026-10-21.md)
