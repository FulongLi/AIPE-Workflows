# Example: 10 kW dual active bridge (800 V → 400 V, 100 kHz, SPS)

`specification.yaml` is the benchmark input. Nominal values come from the AIPE
task; ranges, limits and environmental assumptions are labelled with their basis
(`assumption` or `source: TIDUES0`, the TI TIDA-010054 design guide, see
`references/tida-010054-fact-sheet.md`). The AIPE operating point (n = 2,
400 V) differs from TI's (n = 1.6, 500 V nominal); TI figures inform ranges and
component choices only.

## Reproduce

```sh
aipe-workflows doctor --qualify
aipe-workflows run examples/dab-10kw/specification.yaml --checkouts .. --run-dir runs/dab-10kw
aipe-workflows verify runs/dab-10kw
aipe-workflows report runs/dab-10kw
```

Requires sibling checkouts of AIPE-Core, AIPE-Registry, AIPE-Electrical-Design,
AIPE-Thermal-Design, AIPE-Simulation-Skills, AIPE-Semiconductor-Database,
AIPE-Magnetics-Database, AIPE-Field-Simulation and AIPE-CAD-Agent (the Python
packages installed with `pip install -e`), plus ngspice, Gmsh, Elmer and
FreeCAD found by `aipe-workflows doctor` (portable builds through
`AIPE_TOOLS_DIR`, `AIPE_NGSPICE`, or the per-user Windows locations). Without a
tool or package the corresponding tasks are reported as blocked; nothing is
fabricated in their place. The reference run (14 tasks, 12 Engineering State
versions) takes about 25 minutes on a laptop, most of it in the 160-cycle
Level 2 ngspice transient, the Stage A heat-sink search and the two FEM models.

## Executed results (2026-10-21, Windows 11, Python 3.10.11)

Tools: ngspice 47, Gmsh 4.15.2, Elmer 9.0 (release 26.1), FreeCAD 1.1.4,
KiCad 10.0.6 (not used by the task graph). The complete review package of the
reference run is stored under `results/` (report in Markdown, JSON and AIPE-Doc
HTML, one execution envelope per task, summaries, netlists, screening and loss
reports, cooling comparison and Pareto set, FEM summaries and solver input
files, CAD parameters, metadata and check reports, figures, the final
Engineering State and the environment manifest). Large raw data (HDF5
datasets, raw solver output, meshes, STEP/FCStd) stays in the run directory and
is referenced by path and SHA-256.

### Analytical SPS operating point (AIPE-Electrical-Design)

| Quantity | Value |
| --- | --- |
| Phase shift for 10 kW with L = 35 µH, n = 2 | 22.5° exactly |
| DC currents port 1 / port 2 | 12.5 A / 25.0 A |
| Series current RMS / peak (primary) | 13.6775 A / 14.2857 A |
| SPS maximum power at φ = 90° | 22 857 W (matches TI's 22.85 kW for the same L and V1·V2') |
| ZVS current condition | met on both bridges at the nominal point |

### Level 1 ideal switching simulation versus analytic

| Quantity | Analytic | ngspice (T/400) | ngspice (T/1600) |
| --- | --- | --- | --- |
| Output power | 10 000 W | 9 996.8 W | 9 996.9 W |
| Port 1 / port 2 DC current | 12.500 / 25.000 A | 12.503 / 24.992 A | — |
| Series current RMS | 13.6775 A | 13.6779 A | 13.6771 A |
| Measured phase shift | 22.5° | 22.5000° | 22.5000° |
| Periodicity error | — | 1.8e-6 | 7.4e-5 |
| ZVS current condition (8 switches) | met | met | met |

The 5 W difference is the modelled series resistance (3.7 W) and switch
on-resistance (1.9 W); the unaccounted remainder is below 1e-4 of rated power.
A zero-initial-condition run reaches the same steady state after 34 cycles
(`results/figures/dab-l1-zero-ic-settling.png`); the time-step study
(`results/timestep-convergence-table.json`) shows output power changing by
8e-6 between T/400 and T/1600.

### Level 2 behavioural simulation (datasheet-sourced parameters)

Model: 200 ns dead time (TIDUES0), on-resistance 58.7 mΩ at 125 °C (linear
interpolation of C3M0040120K datasheet typical values, applied to all eight
switches, pessimistic for the 650 V secondary devices), energy-equivalent Coss
187 pF with 1 Ω damping, body-diode single-point fit (VSD 5.5 V at 20 A),
2 µH leakage split from the 35 µH, 30 µF input DC link with 6.6 µF ceramic
decoupling and 50 mΩ / 1 µH source impedance, 60 µF / 16 Ω RC output port.

| Quantity | Value |
| --- | --- |
| Total loss (capacitor drift corrected) | ≈130 W |
| Switch-pair dissipation from v_ds·i | ≈123 W (conduction, dead-time body-diode conduction, Coss damping) |
| Efficiency | ≈0.986 drift-corrected (0.991 raw P2/P1; the RC port is still settling slowly at fixed phase shift) |
| Per-switch RMS current primary / secondary | 9.4 A / 19.2 A |
| Peak drain-source voltage primary / secondary | 810 V / 412 V |
| Turn-off currents primary / secondary | 14.2 A / 30.6 A |
| Drain-source voltage just before turn-on | −0.9 V (primary), −3.6 V (secondary): body diode conducting, i.e. ZVS |
| Open-loop output voltage | ≈392 V (losses reduce the transferred power at fixed φ; closed-loop control restores 400 V) |

Exact values, per-switch tables and solver diagnostics are in
`results/circuit-sim-level2/summary.json` and `results/report.md`.

### SPS digital control baseline (AIPE-Simulation-Skills `control`)

Cycle-averaged lossless plant with one computation and one measurement sample
of delay (10 µs update); discrete PI current loop and 2P2Z voltage loop;
protection acts within one period on quasi-static currents. No firmware was
built; coefficients are host-side design values.

| Quantity | Value |
| --- | --- |
| Plant gain dI2/dφ at the nominal point (range φ → 0 … 45°) | 54.6 A/rad (36.4 … 72.8 A/rad) |
| Current loop: crossover / phase margin / gain margin | 2.0 kHz / 93.6° / 10.0 dB (92.6–94.4° over the plant-gain range) |
| Voltage loop: crossover / phase margin / gain margin | 300 Hz / 60.0° / 28.4 dB (55.4° at no load, 62.4° at maximum inner-loop gain) |
| Plant law versus executed ngspice Level 1 at φ = 10°, 22.5°, 35° | max \|ΔP2/P2\| = 0.07 % |
| Scenarios | nominal: soft start, load steps, reversal, orderly shutdown, no trip; fault: under-voltage trip latched then IDLE; input sag 800 → 450 V: phase shift saturates at 43.9°, series-peak over-current trip latched (designed behaviour) |

Evidence: `results/control-baseline/` (summary with controller coefficients and
margins, plant verification table, closed-loop traces as HDF5 in the run
directory, figures in `results/figures/control-baseline-*.png`).

### Waveform-informed transformer design (AIPE-Magnetics-Database)

The Level 1 HDF5 dataset (primary and secondary currents, transformer voltage,
magnetising current over the steady-state window) drives exact harmonics, the
flux integral, iGSE core loss, per-layer harmonic Dowell copper loss with litz
strand sub-layers, 1-D leakage and a lumped thermal network.

| Quantity | Value |
| --- | --- |
| Selected core / material | TDK E 70/33/32 set, N87 (catalogue record `core.tdk-e70-33-32`) |
| Turns | 20 : 10, P-S-P interleaved, litz 436 × 0.1 mm primary, 889 × 0.1 mm secondary |
| Peak flux density | 0.146 T |
| Core / copper / total loss at 100 °C | 19.1 W / 15.9 W / 35.0 W |
| Hot-spot temperature rise (lumped network, forced convection h = 40 W/m²K assumed) | 63 K |
| Leakage inductance (1-D) / external inductance still required | 1.55 µH / 33.4 µH |
| Magnetising inductance (reluctance model) | 3.9 mH |
| Mass (core + copper) | 0.70 kg |

### Window FEM of the selected core and layout (AIPE-Field-Simulation, Gmsh + Elmer)

2-D magnetostatics of the E 70/33/32 window (centre leg 22 mm, window 13 × 43.8 mm,
depth 32 mm) with the magnetics layout as homogenised blocks (primary 2 × 2.61 mm,
secondary 3.73 mm, 0.2 mm section gaps, 1.6 mm bobbin/clearance, copper fill
0.38) at the executed peak primary current 14.3 A.

| Quantity | Level 0 (h = 1 mm, 7 662 elements) | Level 1 (h = 0.5 mm, 26 920 elements) |
| --- | --- | --- |
| Leakage inductance, FEM energy method | 1.440 µH | 1.483 µH |
| 1-D MMF estimate on the same layout | 1.551 µH | 1.551 µH |
| Magnetics-database 1-D design value | 1.551 µH | 1.551 µH |
| FEM versus 1-D | — | −4.4 % |
| Magnetising inductance FEM / reluctance estimate | — | 5.18 mH / 4.18 mH (μr = 2000 assumed) |
| Ampere-turn balance, Elmer vs numpy energy | 8e-16, 5e-8 | checks pass |

The FEM confirms the database's 1-D leakage within 4.4 % for this interleaved
layout (feedback example C). No 3-D end effects, core loss or individual turns
are modelled; the P-S-P interleaving is why the leakage is far below the 2 µH
assumed in the Level 2 circuit model.

### Device screening and losses on the executed Level 2 waveforms (AIPE-Semiconductor-Database)

Per-switch RMS, average, peak and turn-off currents of the Level 2 dataset
(worst-case switches S3 and S8) against the canonical and candidate SiC records;
derating 0.70, junction-temperature headroom at Tj = 125 °C, Rg = 2.5 Ω (lowest
value inside the PLECS Eoff model range), 0.1 K/W pad and 0.5 K/W sink from the
TI design (reference). Discrete packages were preferred because the thermal, CAD
and PCB stages are laid out for TO-247; the loss-ranked overall winner for both
bridges is the WolfPACK half-bridge module CBB021M12FM3 (6.9 W / 14.6 W per
switch position), kept in the ranked lists.

| Bridge | Selected device | Evidence tier | Conduction / turn-off / total loss per device at 125 °C | Rth(j-c) | Electro-thermal fixed point (0.6 K/W chain) |
| --- | --- | --- | --- | --- | --- |
| Primary (800 V, 9.4 A rms, 14.2 A turn-off) | Wolfspeed C4MS047120K (1200 V, TO-247-4) | A: manufacturer PLECS tensors | 6.93 / 2.11 / 9.04 W | 0.635 K/W | 48 °C, 6.6 W |
| Secondary (400 V, 19.2 A rms, 30.6 A turn-off) | Wolfspeed C3M0025065K (650 V, TO-247-4) | A: manufacturer PLECS tensors | 13.18 / 4.27 / 17.45 W | 0.458 K/W | 57 °C, 16.1 W |

Eight devices: 106 W at the 125 °C evaluation temperature (conservative; the
converged fixed points are lower). Turn-on loss is zero because every switch
meets the ZVS current condition; a charge-based ZVS check needs Coss/Eoss data
the records do not contain (coverage gaps are listed per evaluation). No
laboratory measurement backs any value.

### Cooling comparison and Stage A heat-sink screening (AIPE-Thermal-Design `aipe_thermal`)

Four devices per bridge on one shared sink at 40 °C ambient, device losses and
Rth(j-c) from the screening, 0.1 K/W pads, generic TO-247 footprint, 125 °C
design limit. Analytical correlations (Elenbaas/Bar-Cohen, Teertstra-Yovanovich-
Culham, Lee spreading, Shah-London/Gnielinski cold plate) with their validity
notes; option geometries, fan curve and coolant inlet are labelled assumptions.

| Option (secondary bridge, 4 × 17.4 W) | Tj,max | T sink | R sink→fluid | Mass | Volume | Auxiliary power |
| --- | --- | --- | --- | --- | --- | --- |
| Liquid cold plate Al 100 × 100 mm, 16 mini-channels, water 2 L/min | 63.0 °C | 50.4 °C | 0.077 K/W | 0.27 kg | 0.12 L | ≈0 W (pump; loop excluded) |
| Forced air Al 100 × 100 × 46 mm, two 60 mm fans | 64.3 °C | 52.2 °C | 0.174 K/W | 0.58 kg | 0.57 L | 1.4 W |
| Natural convection Al 200 × 200 × 88 mm | 79.2 °C | 66.4 °C | 0.378 K/W | 2.59 kg | 3.52 L | 0 |

Primary bridge: 54.2 / 56.0 / 65.5 °C. Stage A seeded Pareto screening of
forced-air plate-fin geometries under extrusion bounds (fin 2–4 mm, gap 4–12 mm,
height 15–50 mm, flow 3–15 L/s; objectives R_th, mass, fan power): 8
non-dominated candidates, 6 feasible; knee **A-001**: Al 81 × 65 mm base,
4.1 mm thick, 11 fins × 2.0 mm, 45 mm high, 6.4 L/s laminar channel flow,
R_th 0.44 K/W, 0.28 kg, 0.29 W fan power, Tj 80.5 °C. Flagged for FEM
verification: A-001 (knee), A-004, A-007 (lowest R_th).

### Heat-sink FEM of the knee candidate (Gmsh + Elmer)

3-D steady conduction of A-001 with two 17.4 W TO-247 footprints and the
candidate's correlation film coefficient h = 31.1 W/m²K at 40 °C.

| Quantity | Level 0 (h = 3 mm, 37 805 el.) | Level 1 (h = 2 mm, 84 666 el.) |
| --- | --- | --- |
| Hotspot temperature | 59.6 °C | 59.6 °C (+0.07 K) |
| R_th hotspot (T_max − T_amb)/2P | — | 0.562 K/W |
| R_th footprint mean | — | 0.544 K/W |
| Analytical candidate (r_convective + max spreading) | — | 0.518 K/W (FEM +8.6 %) |
| Convective heat / injected | — | 34.89 W / 34.89 W |

The film coefficient is an input from the correlation, not a CFD result; the
8.6 % gap is the resolved conduction and spreading in the 4.1 mm base and fins
versus the fin-efficiency model.

### Parametric CAD (AIPE-CAD-Agent, FreeCAD 1.1.4 console)

| Model | Content | Mass (CAD) | Comparison | Checks |
| --- | --- | --- | --- | --- |
| Transformer | E 70/33/32 outline from the catalogue record, 20:10 litz windings in the magnetics radial order (primary 10 + secondary 10 + primary 10), 0.2 mm barriers, pins, clips, base plate | 0.864 kg (ferrite 0.550, copper 0.234) | magnetics estimate 0.696 kg (core + copper 0.732 in CAD; the rest is bobbin, barriers, clips, plate) | no interference, fit 3/3 pass; primary/pe and secondary/pe pass (16.8 mm); primary/secondary **review**: 0.2 mm solid barrier only, creepage not traced |
| Heat sink | Stage A A-001 geometry with two C3M0025065K on alumina pads | 0.290 kg (sink 0.275) | correlation model 0.278 kg (−1.3 %) | no interference; secondary/pe **review** (tab-to-screw through 0.29 mm bushing) |

STEP re-import volume error 3e-14. Clearance requirements are illustrative
caller inputs; the transformer's inter-winding insulation system has not been
designed, so the review item is a genuine open point.

### KiCad boards and executed ERC/DRC (AIPE-PCB-Agent, KiCad 10.0.6)

AIPE-PCB-Agent generated the three DAB boards from requirement files
(`automation/dab_v1`, `examples/dab-10kw` in that repository: primary power,
secondary power, control; hierarchical schematics, insulation-coordination
rules, placement, pairwise grid routing, hashed manufacturing exports) and an
architecture review of gate drive, protection, sensing and isolation. The
workflow task `pcb-erc-drc` re-runs `kicad-cli sch erc` and `pcb drc
--schematic-parity` on the boards as committed and **fails while any board is
not clean**, so the `cad_pcb` gate reads `fail` for this run:

| Board | ERC errors / warnings | DRC errors / warnings | Unconnected items | Schematic parity |
| --- | --- | --- | --- | --- |
| primary-power | 0 / 0 | 22 (20 clearance, 2 hole clearance) / 35 dangling tracks and vias | 82 | 0 |
| secondary-power | 0 / 0 | 2 (hole clearance) / 35 dangling | 81 | 0 |
| control | 0 / 0 | 0 / 0 | 499 (placed, not routed) | 0 |

The power boards stopped after two 20-minute routing iterations at the
session's cut-off (about 80 open connections each, mostly gate-driver bias and
sense fan-outs); the control-board router did not finish. The clearance errors
come from 0.5 mm pre-routed capacitor stubs against the 4.0 mm bus rule; the
generator fixes (0.3 mm stubs, via keep-outs at net-tie pads) are in place but
not re-run. Reports: `results/pcb-erc-drc/` (ERC/DRC JSON per board, source
file SHA-256, the agent's verification summaries). Nothing has been fabricated.

## Adapter migration check (2026-10-21)

The analytical and thermal stages moved from the legacy `pea` modules (sibling checkout) to the installed
`aipe_electrical` 0.2.0 and `aipe_thermal` 0.2.0 packages. A complete re-run (`runs/wf-dab-10kw-stab`) reproduces
every compared value of the reference run exactly — analytic operating point, Level 1 and Level 2 ngspice results,
control margins, magnetics, device losses, cooling, FEM and CAD — see `results/migration-check-2026-10-21.json`.
The analytical envelope now also records the power-flow direction and the ZVS current-direction evidence label.

## Cross-module feedback example A (executed)

The magnetics design proposes 21:10 actual turns instead of the nominal 2:1.
`aipe-workflows iterate` derives a child run from the reference run, removes the
fixed phase shift so the analytical task re-solves it for rated power, re-runs
exactly the invalidated tasks and records the decision:

```sh
aipe-workflows iterate runs/wf-dab-10kw-first --checkouts .. \
  --set converter.turns_ratio_np_ns=2.1 converter.phase_shift_deg=null \
  --reason "magnetics design proposes 21:10 actual turns"
```

| Observable | parent (n = 2.0) | child (n = 2.1) |
| --- | --- | --- |
| Phase shift for 10 kW | 22.50° | 21.26° |
| Level 1 series current RMS / peak | 13.678 / 14.315 A | 13.379 / 16.381 A |
| Level 1 secondary current RMS | 27.93 A | 29.00 A |
| Level 1 output power | 9 996.8 W | 9 994.1 W |
| Level 2 ZVS on all switches | yes | yes |
| Decision | — | accepted: simulations match their analytical references, ZVS retained, rated power within 2 % |

Evidence: `results/iteration-example-a/` (iteration record, ledger, re-solved
analytical envelope, Level 1 summary, Level 2 comparison). The mismatched
voltage ratio (d = 1.05) raises the peak current by 14 %, a quantity the
magnetics and semiconductor stages consume on the next pass. The iterations
were run on the six-task graph of the time; the parent run has since been
extended in place (checkpoints reused, new stages appended), so the ledger
remains valid for the tasks it names.

## Cross-module feedback example D (executed): magnetics and FEM parameters back into the circuit model

```sh
aipe-workflows reconcile runs/wf-dab-10kw-first                        # exit 3: circuit model inconsistent
aipe-workflows reconcile runs/wf-dab-10kw-first --apply --checkouts ..  # child run wf-dab-10kw-first-it03
aipe-workflows reconcile runs/wf-dab-10kw-first-it03                    # exit 0: consistent
```

`reconcile` compared the converter parameters of the reference run (all 35 µH external, L_m = 1 mH placeholder,
2:1) with the magnetics design and the executed window FEM, proposed `leakage_inductance_primary_H = 1.483e-6`
(FEM), `external_inductance_H = 33.517e-6` (total kept) and `magnetising_inductance_H = 5.18e-3` (FEM), found the
20:10 turns ratio consistent, and derived the child run. Decision: accepted (simulations match their analytical
references, ZVS retained, rated power within 2 %; the optional PCB check fails on the unfinished boards and is recorded
in its gate).

| Quantity | parent (leakage 0, L_m 1 mH) | child it03 (leakage 1.48 µH, L_m 5.18 mH) |
| --- | --- | --- |
| Level 2 total loss | 131.7 W | 127.2 W |
| Level 2 magnetising current peak | 2.03 A | 0.40 A |
| Level 2 secondary RMS current | 27.11 A | 26.76 A |
| Secondary device loss (C3M0025065K) | 17.45 W | 16.18 W |
| Hottest junction, best cooling option | 63.0 °C | 61.7 °C |
| Heat-sink FEM hotspot | 332.8 K | 331.2 K |
| Level 1 power, ZVS, control margins | unchanged |  |

Evidence: `results/iteration-reconcile-it03/` (iteration record, both reconciliation reports, child envelopes, Level 2
summary, child verification ledger).

## Open feedback items recorded by the run

- The circuit model started with all 35 µH external and a 1 mH magnetising placeholder; the magnetics design
  and the window FEM give 1.5 µH leakage and 5.2 mH; example D above feeds them back (loss 131.7 → 127.2 W).
- The screening ranks a half-bridge module above the discrete devices for both
  bridges; the module route changes the thermal, CAD and PCB layout and was not
  followed here.
- Transformer insulation (0.2 mm barrier) and the heat-sink bushing path are
  CAD review items, not failures.

## What is not claimed

The PCB boards are not finished: the `cad_pcb` gate is `fail` because of the
unrouted connections and DRC errors listed above (the FreeCAD tasks of the same
gate passed). No CFD, no manufacturer SPICE model run (Level 3), no measurement
and no hardware qualification. The verification ledger
(`results/verification.json`) keeps `engineering_review`, `experimental` and
`hardware_qualification` at `not_run`. Device and material
parameters are manufacturer-specified datasheet or model values or labelled
assumptions, not measurements; the behavioural switch model is not a
manufacturer SPICE model; thermal and FEM film coefficients are correlation
inputs, not CFD results.
