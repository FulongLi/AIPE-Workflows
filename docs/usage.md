# Usage

## Install

Python 3.10 or newer. The engine contains no specialist solver or database; every engineering computation
is performed by a sibling AIPE repository behind a thin adapter. Clone the repositories next to each other (or
under one `repos/` folder) and install the packages you need:

```sh
python -m pip install -e ../AIPE-Simulation-Skills       # ngspice runner, DAB generator, waveform analysis, control baseline
python -m pip install -e ../AIPE-Electrical-Design       # aipe_electrical: lossless SPS analysis
python -m pip install -e ../AIPE-Thermal-Design          # aipe_thermal: cooling comparison, heat-sink screening
python -m pip install -e ../AIPE-Semiconductor-Database ../AIPE-Magnetics-Database[hdf5]
python -m pip install -e ../AIPE-Field-Simulation ../AIPE-CAD-Agent   # Gmsh/Elmer models, FreeCAD geometry
python -m pip install -e .                                # this engine
aipe-workflows doctor --qualify                           # detect and numerically qualify ngspice, KiCad, FreeCAD, Gmsh, Elmer
```

The doctor searches `PATH`, the `AIPE_*` environment variables, a workspace `tools/` folder (portable installs) and
the usual per-user Windows locations; missing tools are reported with their official download channel and licence,
and nothing is installed automatically. Stages whose tool or package is missing are reported as blocked, never faked.

## Run the DAB benchmark

```sh
aipe-workflows capabilities --checkouts ..                        # what the Registry and sibling manifests offer
aipe-workflows plan examples/dab-10kw/specification.yaml --checkouts ..
aipe-workflows run  examples/dab-10kw/specification.yaml --checkouts ..
aipe-workflows status <run-id>
aipe-workflows verify <run-id>
aipe-workflows report <run-id>
```

`run` creates `runs/<run-id>/` with the specification, environment manifest, plan, one execution envelope per task,
hashed artifacts (netlists, solver logs, HDF5 waveform datasets, FEM case files, CAD metadata, figures), every
Engineering State version and a verification ledger. Running again reuses completed checkpoints whose inputs are
unchanged and re-executes everything downstream of a changed input or adapter version; stale results are never
reused. `report` writes JSON, Markdown and an AIPE-Doc styled HTML review package.

## Feedback loops

```sh
aipe-workflows reconcile <run-id>                                  # compare the circuit model with magnetics/FEM results (exit 3 if inconsistent)
aipe-workflows reconcile <run-id> --apply --checkouts ..           # derive the child run that re-simulates with the updated parameters
aipe-workflows iterate <run-id> --set converter.turns_ratio_np_ns=2.1 converter.phase_shift_deg=null \
    --reason "magnetics proposes 21:10 turns"                      # any specification change as a recorded iteration
```

`reconcile` labels every quantity with its source task and evidence id (transformer leakage, external inductor,
magnetising inductance, turns ratio) and writes `reconciliation.json`; `iterate` derives a child run with changed
inputs, re-executes only what the change invalidates, compares the key observables with the parent and records an
accept/reject decision with reasons in `iterations.json`.

## Stages of the DAB workflow

| Stage | Specialist | Gate |
| --- | --- | --- |
| Requirements → Engineering State | AIPE-Core validator | software |
| Analytical SPS design | AIPE-Electrical-Design | analytical |
| Level 1 ideal and Level 2 behavioural ngspice simulation, time-step convergence | AIPE-Simulation-Skills | circuit_simulation |
| SPS digital control baseline, plant law vs ngspice | AIPE-Simulation-Skills | analytical |
| Waveform-informed transformer design | AIPE-Magnetics-Database | analytical |
| Device screening and losses on the executed waveforms | AIPE-Semiconductor-Database | analytical |
| Cooling comparison and Stage A heat-sink screening | AIPE-Thermal-Design | analytical |
| Window magnetostatics and heat-sink conduction FEM | AIPE-Field-Simulation (Gmsh + Elmer) | field_simulation |
| Transformer and heat-sink geometry with checks | AIPE-CAD-Agent (FreeCAD) | cad_pcb |
| ERC/DRC of the generated boards | AIPE-PCB-Agent boards, kicad-cli | cad_pcb |

Engineering review, laboratory measurement and hardware qualification are separate gates that no software result
ever sets. See `docs/architecture.md`, `docs/execution-envelope.md`, `workflows/converter_dab/README.md` and
`examples/dab-10kw/README.md` for the executed results and their reproduction.
