# AIPE-Workflows

**AI for Power Engineering — system-level engineering workflow engine.**

AIPE-Workflows turns the AIPE specialist repositories (databases, solvers,
design agents) into one coordinated, reproducible engineering workflow. It owns
the task graph, dependency ordering, capability discovery, local tool
qualification, typed inputs/outputs, checkpoints and resumability, artifact
management, verification gates and report assembly. It contains **no**
specialist solver or device database of its own: every engineering computation
is performed by a specialist repository behind a thin adapter, and every result
enters the AIPE-Core Engineering State with evidence and provenance.

The first benchmark is the simulation-driven **10 kW dual active bridge (DAB)**:
800 V to 400 V, 100 kHz, single phase shift. The ideal benchmark reproduces the
analytical SPS solution with an executed ngspice transient before any higher
fidelity modelling proceeds; the reference run then chains thirteen tasks across
seven specialist repositories (circuit simulation, control, magnetics, devices,
thermal, FEM, CAD) with every number traceable to an executed tool.

## Install (Windows or Linux, Python 3.10+)

```sh
# sibling checkouts next to this repository (or under repos/):
#   AIPE-Core  AIPE-Registry  AIPE-Design-Agent  AIPE-Simulation-Skills  ...
python -m pip install -e ../AIPE-Simulation-Skills      # ngspice runner, DAB generator, waveform analysis, control
python -m pip install -e ../AIPE-Design-Agent ../AIPE-Semiconductor-Database ../AIPE-Magnetics-Database[hdf5]
python -m pip install -e ../AIPE-Field-Simulation ../AIPE-CAD-Agent   # Gmsh/Elmer models, FreeCAD geometry (optional stages)
python -m pip install -e .                               # this engine
aipe-workflows doctor --qualify                          # detect and numerically qualify solvers
```

The doctor searches PATH, `AIPE_*` environment variables, a workspace `tools/`
folder (portable installs) and the usual per-user Windows locations, because
ngspice, KiCad, FreeCAD and Elmer are not on PATH after a default Windows
installation. Missing tools are reported with their official download channel
and licence; nothing is installed automatically.

## Run the DAB benchmark

```sh
aipe-workflows capabilities --checkouts ..                       # what the Registry/siblings offer
aipe-workflows plan examples/dab-10kw/specification.yaml --checkouts ..
aipe-workflows run  examples/dab-10kw/specification.yaml --checkouts ..
aipe-workflows status <run-id>
aipe-workflows verify <run-id>
aipe-workflows report <run-id>
```

`run` creates `runs/<run-id>/` with the specification, environment manifest,
plan, one execution envelope per task, hashed artifacts (netlists, solver logs,
HDF5 waveform datasets, figures), every Engineering State version and a
verification ledger. Running again reuses completed checkpoints whose inputs
are unchanged and re-executes everything downstream of a changed input; stale
results are never reused. `report` writes JSON, Markdown and an AIPE-Doc styled
HTML review package.

```sh
aipe-workflows iterate <run-id> --set converter.turns_ratio_np_ns=2.1 converter.phase_shift_deg=null \
    --reason "magnetics proposes 21:10 turns"          # cross-module feedback loop
```

`iterate` derives a child run with changed inputs, re-executes only what the
change invalidates, compares the key observables with the parent and records an
accept/reject decision with reasons in `iterations.json`. Workflow definitions
and the `aipe.workflows.dab` state extension are validated against versioned
JSON Schemas in `src/aipe_workflows/schemas/`.

In Claude Code or Codex, opening this repository and asking "Design and
optimise a 10 kW DAB converter using AIPE, run the available simulations, and
generate the engineering review package" should lead the agent to
`aipe-workflows doctor`, `plan`, `run` and `report` on the example above.

## What exists and what does not

| Stage | Status (2026-10-21, reference run `examples/dab-10kw/results/`) | Where |
| --- | --- | --- |
| Requirements → Engineering State | executed, Core-validated (12 state versions) | adapters/requirements.py |
| Analytical SPS design | executed, exact closed forms | AIPE-Design-Agent `pea.converters.dab_sps` |
| Level 1 ideal ngspice simulation + waveform metrics | executed; matches analytic within 0.03 % power, 0.003 % RMS current | AIPE-Simulation-Skills `aipe_simulation` |
| Time-step convergence study | executed (T/400 vs T/1600) | task `circuit-sim-level1-convergence` |
| Level 2 behavioural simulation (dead time, Coss, body diode, ESR/ESL, RC port) | executed with datasheet-sourced parameters, 160 cycles | task `circuit-sim-level2` |
| SPS digital control baseline (PI + 2P2Z, scenarios, plant law vs ngspice) | executed; worst phase margin 55°, plant law within 0.07 % | AIPE-Simulation-Skills `aipe_simulation.control` |
| Waveform-informed transformer design | executed on the Level 1 HDF5 dataset; E 70/33/32, 20:10 | AIPE-Magnetics-Database |
| Device screening and losses on executed waveforms | executed on the Level 2 dataset; C4MS047120K / C3M0025065K | AIPE-Semiconductor-Database |
| Cooling comparison + Stage A heat-sink Pareto | executed (analytical correlations) | AIPE-Design-Agent `pea.thermal` + HeatSinkOptimisation |
| Window magnetostatics and heat-sink conduction FEM | executed with Gmsh + Elmer at two mesh levels | AIPE-Field-Simulation |
| Parametric CAD (transformer, heat sink) with geometric checks | executed with FreeCAD console | AIPE-CAD-Agent |
| KiCad boards, ERC/DRC | boards generated by AIPE-PCB-Agent; task `pcb-erc-drc` executed: ERC clean, routing unfinished (82/81/499 unconnected items), so gate cad_pcb = fail | AIPE-PCB-Agent + adapters/pcb_agent.py |
| CFD, manufacturer SPICE models (Level 3), measurement, hardware qualification | **not executed / never asserted by software**; separate gate statuses | verification ledger |

See `docs/architecture.md`, `docs/execution-envelope.md` (the common
specialist execution envelope compatible with AIPE-Core), `docs/capability-matrix.md`,
`workflows/converter_dab/README.md` and `examples/dab-10kw/README.md` for the
executed results and reproduction.

## Licence

MIT for this repository's code. Specialist repositories keep their own
licences; manufacturer datasheets and models are referenced by URL, never
redistributed.
