# Workflow `aipe.workflow.converter-dab`

Versioned task graph (`workflow.yaml`, schema 0.1.0) for the simulation-driven
design of a dual active bridge DC/DC converter. Each task names the Registry
capability it needs, the adapter that calls the specialist repository, the
external tools it depends on and the verification gate its result belongs to.

| Task | Capability (Registry) | Specialist | Gate | Status 2026-10-21 |
| --- | --- | --- | --- | --- |
| `requirements` | engineering-state-schema (aipe.core) | Core validator | software | executed |
| `analytic-sps` | converter-concept-calculation (aipe.design-agent) | `pea.converters.dab_sps` | analytical | executed |
| `circuit-sim-level1` | switching-circuit-simulation (aipe.simulation-skills) | `aipe_simulation.dab` Level 1 + ngspice | circuit_simulation | executed, matches analytic |
| `circuit-sim-level1-convergence` | switching-circuit-simulation | same, t_max = T/1600 | circuit_simulation | executed |
| `circuit-sim-level2` | switching-circuit-simulation | `aipe_simulation.dab` Level 2 behavioural | circuit_simulation | executed |
| `control-baseline` | averaged-control-analysis (aipe.simulation-skills) | `aipe_simulation.control` + ngspice plant cross-check | analytical | executed |
| `magnetics-transformer-design` | magnetics-waveform-informed-transformer-design (aipe.magnetics-database) | `aipe_magnetics.api.design_transformer_from_waveforms` on the Level 1 HDF5 dataset | analytical | executed |
| `semiconductor-screening` | semiconductor-dab-screening (aipe.semiconductor-database) | `aipe_devices dab-screen` / `dab-losses` on the Level 2 summary and HDF5 dataset | analytical | executed |
| `thermal-cooling-design` | thermal-cooling-screening (aipe.design-agent) | `pea.thermal` cooling comparison + Stage A Pareto (HeatSinkOptimisation correlations) | analytical | executed |
| `fem-transformer-window` | fem-magnetostatics-2d (aipe.field-simulation) | `aipe_fieldsim` TransformerWindowModel, Gmsh + Elmer, selected core window and layout | field_simulation | executed, two mesh levels |
| `fem-heatsink` | fem-thermal-conduction (aipe.field-simulation) | `aipe_fieldsim` HeatSinkModel on the Stage A knee candidate, Gmsh + Elmer | field_simulation | executed, two mesh levels |
| `cad-transformer` | parametric-transformer-cad (aipe.cad-agent) | `aipe-cad build transformer` (FreeCAD console) from the core record and winding layout | cad_pcb | executed |
| `cad-heatsink` | heat-sink-cad (aipe.cad-agent) | `aipe-cad build heatsink` from the Stage A knee candidate | cad_pcb | executed |
| PCB boards, ERC/DRC | AIPE-PCB-Agent | KiCad automation (`automation/dab_v1`) | cad_pcb | executed in that repository; not yet a workflow task |
| measurement, hardware qualification | — | human records | experimental, hardware_qualification | never asserted by software |

## Data flow

```
specification.yaml ──requirements──► state v0 (Core-valid; ratings + labelled assumptions)
        │
        └── analytic-sps ──► phi, I_L(0), currents, evidence ─┬─► circuit-sim-level1 ──► HDF5 dataset, per-switch metrics
                              │                               │        ├─► circuit-sim-level1-convergence (T/1600)
                              │                               │        ├─► circuit-sim-level2 (behavioural, 160 cycles) ──► semiconductor-screening
                              │                               │        │                                                        │  losses, Rth(j-c), Tj rating
                              │                               │        │                                                        ▼
                              │                               │        │                                            thermal-cooling-design ──► knee candidate
                              │                               │        │                                                        │                 │
                              │                               │        │                                                 fem-heatsink      cad-heatsink
                              │                               │        └─► magnetics-transformer-design ──► core record, turns, layout, L_leak(1-D)
                              │                               │                   ├─► fem-transformer-window (L_leak FEM vs 1-D)
                              │                               │                   └─► cad-transformer
                              └── control-baseline (plant law vs ngspice at 10, 22.5, 35 deg)
```

Bindings: `$task.requirements.requirements`, `$task.requirements.converter` and
`$task.requirements.environment` carry the specification into every task;
`$task.analytic-sps` passes the complete analytical output (phase shift,
currents, evidence id) to the simulation and control tasks; the simulation
tasks expose `dataset`, `dataset_sha256` and `summary_path` so that magnetics
and device screening read the executed waveforms; `semiconductor-screening`
exposes per-bridge losses and junction-to-case resistances for the thermal
task; `thermal-cooling-design` exposes `fem_candidate_geometry` for the FEM and
CAD heat-sink tasks; `magnetics-transformer-design` exposes the selected core id
and the parametric layout for the window FEM and the transformer CAD.

## Adding a stage

1. Implement the capability in its specialist repository (API/CLI/tests) and register it in that
   repository's `aipe.yaml`.
2. Write an adapter under `src/aipe_workflows/adapters/` returning an `ExecutionEnvelope` with a
   Core-compatible `state_proposal` (see `docs/execution-envelope.md`) and add its extension keys to
   `src/aipe_workflows/schemas/dab-extension.schema.json`.
3. Append a task to `workflow.yaml` with its `capability`, `adapter`, `depends_on`, `inputs`, `tools`,
   `parameters` and `gate`. The graph is validated at load time; `aipe-workflows plan` shows blockers.
4. Specialist command lines run with their own checkout as working directory: pass absolute paths for
   artifacts the adapter reads or writes.

## Re-execution rules

A task re-runs when its inputs, parameters or adapter version changed, or when any upstream task
re-ran in the same invocation; otherwise its checkpoint is reused and its stored state proposal is
replayed. Failed or blocked tasks block their dependants; optional tasks do not fail the run when blocked.
A specialist result whose own hard checks fail (for example CAD interference) fails the task; a result
with soft "review" items completes with the items recorded in the envelope and the report.
