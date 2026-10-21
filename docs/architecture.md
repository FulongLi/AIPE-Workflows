# AIPE-Workflows architecture

## Responsibility boundary

AIPE-Workflows owns *how* engineering work is sequenced, checked and recorded;
it never owns *what* a specialist computes. The split follows the AIPE v0.1
architecture freeze:

| Concern | Owner | Workflows' role (adapter) |
| --- | --- | --- |
| Engineering State schema, SI units, evidence | AIPE-Core | loads states, runs Core's validator, applies provenance-preserving proposals |
| Capability metadata | AIPE-Registry | reads `generated/aipe.json` and sibling `aipe.yaml` as data; matches task capabilities |
| Converter mathematics (lossless SPS analysis) | AIPE-Electrical-Design `aipe_electrical.converters.dab_sps` | `adapters/electrical_design.py` imports the installed package |
| Cooling comparison, Stage A heat-sink screening | AIPE-Thermal-Design `aipe_thermal` (cooling, screening, heat-sink correlation model) | `adapters/thermal_design.py` imports the installed package |
| Circuit simulation, waveform analysis, SPS control baseline | AIPE-Simulation-Skills `aipe_simulation` | `adapters/simulation_skills.py` (ngspice levels 1-2), `adapters/control_baseline.py` |
| Device screening and losses on executed waveforms | AIPE-Semiconductor-Database `aipe_devices` CLI | `adapters/semiconductor_database.py` |
| Waveform-informed transformer design | AIPE-Magnetics-Database `aipe_magnetics.api` | `adapters/magnetics_database.py` |
| 2-D window magnetostatics, 3-D heat-sink conduction (Gmsh + Elmer) | AIPE-Field-Simulation `aipe_fieldsim` | `adapters/field_simulation.py` |
| Parametric FreeCAD geometry and geometric checks | AIPE-CAD-Agent `aipe-cad` CLI | `adapters/cad_agent.py` |
| PCB generation (KiCad automation) and ERC/DRC | AIPE-PCB-Agent | `adapters/pcb_agent.py` runs `kicad-cli` ERC/DRC on the boards AIPE-PCB-Agent generated; generation and routing stay in that repository |

Every adapter maps the specialist's native result into the common
`ExecutionEnvelope` (`docs/execution-envelope.md`): tool and model identity with
validity range, hashed artifacts, verification metrics, a Core-valid
`state_proposal` (evidence, appended records, `aipe.workflows.dab` extension
keys defined in `schemas/dab-extension.schema.json`) and the gate the result
belongs to.

## Packages

```
engine/        TaskGraph (versioned workflow.yaml, bindings, acyclicity), WorkflowRunner (checkpoints, reuse,
               stale-downstream re-execution, blocked/failed propagation, stored-proposal replay), ExecutionEnvelope
engineering_state/  Core checkout discovery, canonical validation, apply_proposal, build_initial_state
artifacts/     hashed artifact index (uri, media type, sha256, role, producing task)
environment/   doctor: tool detection in PATH / env vars / workspace tools / per-user locations, real qualification tests
capability_discovery/  Registry index + sibling manifests -> capability lookup
adapters/      requirements, electrical_design, simulation_skills, control_baseline, magnetics_database,
               semiconductor_database, thermal_design, field_simulation, cad_agent, pcb_agent
optimisation/  iterate: child runs with changed inputs, observable comparison, accept/reject ledger;
               reconcile: circuit-model parameters versus magnetics/FEM results, derives the iterate child
verification/  gate ledger: analytical, software, circuit_simulation, field_simulation, cad_pcb, engineering_review,
               experimental, hardware_qualification (never implied by earlier gates)
reporting/     report.json + report.md + AIPE-Doc styled report.html with executed numbers, figures, gate statuses,
               blocked items, reproduction
```

## Execution model

1. `plan` resolves the task graph, finds the Registry entry for each task capability, loads the adapter and
   collects blockers (missing tools, missing packages, unregistered capability). Nothing is executed.
2. `run` executes tasks in topological order. Each task's inputs are resolved from bindings
   (`$spec`, `$state`, `$env`, `$task.<id>[.<output>]`), hashed together with the adapter version and
   parameters, and compared with the stored checkpoint. Unchanged tasks are reused; any change (including a
   new adapter version) re-executes the task and everything downstream. A failed or blocked task blocks its
   dependants. Specialist command lines run with their own checkout as working directory, so adapters pass
   absolute artifact paths.
3. A completed envelope's `state_proposal` is applied to the current Engineering State, validated with the
   sibling AIPE-Core validator and committed as a new `state/state-NNN.json`; earlier versions are never
   modified. Reused checkpoints replay their stored proposal so the state chain is rebuilt deterministically.
4. `verify` rebuilds the gate ledger, re-hashes every indexed artifact and re-validates the final state.
5. `report` assembles the review package from the run directory only (no recomputation).
6. `iterate` derives a child run with changed specification values, re-executes only what the change
   invalidates, compares observables with the parent and records accept/reject with reasons.

## Cross-module data flow in the DAB workflow

```
specification -> requirements -> analytic-sps -> circuit-sim-level1 -> circuit-sim-level1-convergence
                                      |               |      \-> magnetics-transformer-design -> fem-transformer-window
                                      |               |                 \-> cad-transformer
                                      |               \-> circuit-sim-level2 -> semiconductor-screening -> thermal-cooling-design
                                      |                                                     \                 |-> fem-heatsink
                                      \-> control-baseline (plant law vs ngspice)            \-> cad-heatsink <-/
```

Waveform datasets (HDF5) produced by the ngspice tasks are consumed by the
magnetics design (harmonics, flux integral) and by the device screening
(per-switch RMS, turn-off, ZVS condition, conduction integral). The device
losses and junction-to-case resistances feed the cooling comparison; the Stage A
knee candidate feeds the heat-sink FEM and CAD; the selected core record and the
magnetics parametric layout feed the window FEM and the transformer CAD.

## What a completed run proves

A `completed` run with the `circuit_simulation` gate at `pass` means: the specification was turned into a
Core-valid state, the analytical model agrees with its own waveform integral, and executed ngspice runs reached
periodic steady state and matched the analytical reference within the declared tolerance. The
`field_simulation` gate at `pass` means the Gmsh/Elmer models executed at two mesh levels with their internal
consistency checks satisfied; the `cad_pcb` gate at `pass` means the FreeCAD geometry built without
interference or fit failures (clearance items may still be `review`) and every generated KiCad board passed ERC and
DRC with schematic parity and no unconnected items. None of this validates the converter:
engineering review, measurement and hardware qualification are separate gates that stay `not_run` until human
records exist, and no software result ever sets them.
