# AIPE Ecosystem Capability Matrix for the 10 kW DAB Workflow

Status: evidence-based audit record, 2026-10-21. Target design: 10 kW, 800 V to 400 V, 100 kHz single-phase-shift dual active bridge (`repos/AIPE-Core/examples/dab-10kw/engineering-state.json`). All paths are relative to the workspace root `D:/Cursor Workspace/AIPE-Full-Ecosystem-Integration/`.

## 1. Purpose and method

Seventeen repository checkouts were audited on 2026-10-21 by read-only, offline agents that inventoried entry points, ran or statically traced the code, and recorded capabilities, data, defects and licences with file:line evidence (`audit/ecosystem-audit-full.json`). Each audit was then checked by an independent adversarial verifier that re-executed the cited code paths and graded every claim confirmed, partially correct or refuted; where a claim was refuted or corrected this document uses the verifier's correction and marks it "(verifier-corrected)". AIPE-Core (commit 4e664f0) and AIPE-Registry (f419260) were audited directly by the orchestrator: Core is a JSON Schema 2020-12 Engineering State v0.1.0 with an offline validator and an immutable synthetic 10 kW DAB example; the Registry publishes a deterministic index of 11 manifests pinned to pending-PR snapshots. AIPE-Workflows (2f5448b) and AIPE-Field-Simulation (3db0c1f) were README-only and AIPE-CAD-Agent had no commits, so they have no audit records. The local engineering environment had no solver at the start of the day; ngspice 47 (portable), KiCad 10.0.6 and FreeCAD 1.1.4 (winget, per user), Gmsh 4.15.2 (pip) and Elmer 26.1 (portable zip) were installed and each passed a numerical qualification test (RC step response 1-e^-1; `kicad-cli version`; 10x20x30 mm box volume 6000 mm^3 plus STEP export; unit-cube tetrahedral mesh; 2-D conduction slab T_max 305 K against the analytic value). OpenFOAM, Xyce and LTspice are not installed; OpenFOAM is not available through winget on Windows.

## 2. Repository summary

| Repository | HEAD | Licence (SPDX or NOASSERTION) | Maturity (audited) | Registry status | Verifier reliability |
|---|---|---|---|---|---|
| AIPE-Core | 4e664f0 | MIT | usable: schemas, validator, DAB example | aipe.core, indexed | orchestrator audit |
| AIPE-Registry | f419260 | MIT | usable: schema, 11-manifest index | aipe.registry | orchestrator audit |
| AIPE-Workflows | 2f5448b | none (README only) | scaffold | not registered | n/a |
| AIPE-Field-Simulation | 3db0c1f | none (README only) | scaffold | not registered | n/a |
| AIPE-CAD-Agent | no commits | none | empty | not registered | n/a |
| awesome-open-source-power-electronics | e5f9c45 | NOASSERTION; 27 third-party screenshots | scaffold as capability (static README catalogue, 36 entries) | aipe.open-source-catalogue pinned to unmerged PR commit 2ff81b2, unreachable in clone | medium |
| AIPE-Doc | f7c74e5 | NOASSERTION; AIPE/Spirit Connect logos unlicensed | prototype (static HTML template kit) | not registered | high |
| HeatSinkOptimisation | f9ae29a | CC-BY-4.0 (content licence, no copyright line) | prototype, archived; single 138-line script | not registered; Core audit: research-experiment | medium |
| AIPE-Academy | f4d8d4d | CC-BY-4.0 | prototype (buck labs only) | aipe.academy, pinned to PR ref f8ad52f, not HEAD | high |
| AIPE-Solid-State-Transformer | 6c98d5e | CC-BY-4.0 | prototype, archived | not registered | medium |
| AIPE-Converter-Optimisation-Agent | 3b68298 | NOASSERTION | prototype (buck VSI research port) | not registered; Core audit: research-experiment | medium |
| AIPE-Simulation-Skills | 454738f | NOASSERTION | prototype (8 prose skills, 2 prototype, 3 scaffold) | aipe.simulation-skills, pinned a964edb pending_pr | high |
| AIPE-Sketcher | 3e005d0 (v0.2.0+2) | LicenseRef-AIPE-Sketcher-Personal-NonCommercial-0.1 AND CC0-1.0 (draft, non-commercial) | usable | aipe.sketch stale: AIPE-Sketch URL, NOASSERTION, pinned pre-rename 19c8379 | high |
| AIPE-Magnetics-Agnet-Inductor-Design-Example | 78f44ad | CC-BY-4.0 | scaffold (6 PNG, 3 Altium 3D PDF), archived | not registered | medium |
| AIPE-IEEE-Paper-Agent | 9bac59b | NOASSERTION (release-config.json claims MIT) | usable engine / scaffold AIPE layer | aipe.ieee-paper-agent | high |
| AIPE-MOSFET-ANN-Modelling | 7205756 | MIT code; device data and glTF NOASSERTION | prototype | not registered; Core audit: research-experiment | medium |
| Spirit-Connect-AIPE-Labs | 3ed4f52 | CC-BY-4.0 (legal/terms.md contradicts) | usable (manifest says prototype) | aipe.presentation | high |
| AIPE-Design-Agent | 2d9c45f | MIT code; bundled vendor and textbook data not MIT | prototype | aipe.design-agent (experimental) | high |
| AIPE-Semiconductor-Database | 52ec17d | NOASSERTION code; Wolfspeed data rights null | usable data layer / scaffold loss engine | aipe.semiconductor-database | high |
| PowerElectronicsDeviceLibrary | 8366047 | GPL-3.0-only (pyproject MIT classifier wrong) | prototype (upstream v0.5.1 fork, no functional change) | not registered; Core audit: migration-source | high |
| AIPE-Magnetics-Database | 59eff8b (branch feat/dab-10kw-workflow) | NOASSERTION | usable v0.2 engine / scaffold untested v0.3 layer | aipe.magnetics-database (integration native) | high |
| AIPE-PCB-Agent | 4b9d1a8 | NOASSERTION (only KiCad footprint CC-BY-SA-4.0 notices) | usable tooling, Windows and KiCad 10.0.7 only | not registered | high |

## 3. Existing usable capabilities (runnable code with tests)

| Repository | Capability | Evidence | Test evidence |
|---|---|---|---|
| AIPE-Core | Engineering State schemas (14 files), `scripts/validate.py` offline validator, DAB example | `repos/AIPE-Core/schemas/`, `examples/dab-10kw/` | `tests/test_contract.py`, CI validate.yml |
| AIPE-Registry | Manifest schema, `scripts/validate.py`, `build_registry.py`, tamper and determinism tests | `repos/AIPE-Registry/schema/capability-manifest.schema.json` | `tests/test_registry.py` |
| AIPE-Academy | Ideal buck analytical and switching labs, catalogue builder, tutor CLI `academy.py` | `labs/buck_open.py`, `labs/power-electronics/buck_switching.py` | 293 unittest OK locally; CI runs labs |
| AIPE-Simulation-Skills | Real ngspice buck netlist run with timestep-halving check; skill catalogue validator | `pe-ngspice-switching-validation/assets/ideal-buck.cir`, `tests/test_open_examples.py:35-53` | 6 tests; ngspice test runs in Ubuntu CI (apt); locally 23.569 V reproduced with ngspice-47 (verifier) |
| AIPE-Sketcher | Circuit IR, electrical validation, automatic schematic with connectivity read-back, SVG, CLI, Core state adapter; DAB reference renders score 97 | `aipe_sketch/pipeline.py`, `validate.py`, `state.py`, `topologies.py:111-131` | 244 tests, 5-job CI (3 OS, Python 3.9 floor, wheel, manifest) |
| AIPE-IEEE-Paper-Agent | Venue-aware LaTeX workspace init (6 venues), static LaTeX and citation audits, reference index, release packaging | `scripts/create-manuscript.py`, `check-latex.py`, `check-citations.py` | 21 tests; 20 pass locally, 1 Windows long-path error (verifier) |
| Spirit-Connect-AIPE-Labs | Registry mirror and hub placement validation, hash-locked ecosystem sync, content checks | `tools/hub_data.py`, `tools/sync_ecosystem.py` | 60 tests OK; CI adds Jekyll build (Ruby not local) |
| AIPE-Design-Agent | 8 DC-DC calculators, deterministic Pareto optimiser, reference component search, Core/Registry capability selection and one adapter (P/V, Vout/Vin) | `pea/tools/calculator.py:30-371`, `pea/optimization.py`, `pea/adapters/__init__.py` | 105 tests, 104 pass (1 needs jsonschema[format]); tests check signs and ratios, not physics |
| AIPE-Semiconductor-Database | PLECS XML import/export, 163-record repository, SI validation, DAB coverage policy, 1-D interpolation, Rth sum, Core candidate export | `src/aipe_devices/importers/plecs/`, `services/coverage/gaps.py:32`, `exporters/core.py` | 14 files / 67 functions expanding to 579 passing cases on Python 3.10 with a StrEnum shim (verifier-corrected from 18/79) |
| AIPE-Magnetics-Database (v0.2) | Transformer and inductor sizing, Steinmetz/iGSE/Bertotti, fundamental Dowell, validation, catalogue, Core round trip, MCP server | `src/aipe_magnetics/engineering/transformer.py`, `models/empirical/igse.py` | 545 tests, 58 bundled checks; DAB demo reproduced bit-for-bit (E65, 21:10, 39.2218 W) |
| AIPE-PCB-Agent | KiCad schematic generation, kicad-cli ERC/DRC and export wrappers, grid router, layout and routing checkers, ngspice ctypes runner, BM25 knowledge base | `automation/kicad_tools/project_schematic.py`, `grid_router.py`, `automation/simulation/ngspice_runner.py` | 373 unittest functions (log only, no CI); V3 DRC 0 violations |
| AIPE-Doc | HTML/CSS document and slide templates, `check.mjs` validator | `scripts/check.mjs` | runnable, no tests |
| HeatSinkOptimisation | Natural-convection plate-fin Rha and mass model, DE optimisation; whole script runs in about 7 s (verifier-corrected) | `HS_main.py:19-58` | no tests |
| AIPE-Solid-State-Transformer | Krismer SPS RMS current and SPS power kernel, verified to 4 decimals against time-domain integration | `code/DAB_inductor_selection.py:25-52, 82-87` | no tests |
| AIPE-Converter-Optimisation-Agent | Buck VSI loss and volume model, SLSQP weighted sweep | `src/cardiff_converter_opt/physics.py`, `optimization.py` | 2 range tests, pass only with `src/` on `sys.path` |
| AIPE-MOSFET-ANN-Modelling | Eon/Eoff, Vds and Zth inference for C2M0080120D | `app.py:17-72`, `models/c2m0080120d_*.pth/.pkl` | no tests; accuracy measured by verifier (Section 8) |
| PowerElectronicsDeviceLibrary | JSON device load, Eoss/Qoss integration, PLECS/MATLAB export | `transistordatabase/transistor.py:469-491, 2079-2365` | suite cannot run as committed (missing fixtures, gitignored expected files, network default) |

## 4. Partially implemented capabilities

| Repository | Capability | What is missing |
|---|---|---|
| AIPE-Design-Agent | DAB mathematics | `pea/tools/calculator.py:377-441` is wrong (Section 13); correct SPS model exists only in untracked `pea/converters/dab_sps.py` (verifier), untested and not in `_TOOL_REGISTRY`, `aipe.yaml` or any adapter |
| AIPE-Design-Agent | Multi-objective optimiser | no DAB in `SUPPORTED_TOPOLOGIES`; LLC bias from loss fudges; no device-rating constraint (recommends a 30 V part for an 800 V bus, verifier); pymoo never exercised; variables x[2], x[6] reused |
| AIPE-Design-Agent | Thermal and device loss | constant K/W per topology (`pea/optimization.py:806-809`), 1800 mm^3/W heat sink; no Eon/Eoff, Coss, Qrr, Tj |
| AIPE-Magnetics-Database | v0.3 FEA, thermal, geometry, optimisation, workflow | zero tests, not in API/CLI/MCP/aipe.yaml; design space N87 x E65/E70 only (verifier: 3C90/3C94 pass filters but produce no candidates under the default offer policy); `mes_to_core_state` has no `base_state` merge |
| AIPE-Magnetics-Database | Public transformer design | current from P/V square approximation, Dowell at fundamental only; no phase shift, series inductance, waveform or leakage inputs |
| AIPE-Semiconductor-Database | Loss evaluation | `services/loss/__init__.py` is a Protocol; interpolation 1-D only; PLECS guard rows retained; no Coss/Eoss; ratings empty (legacy v2 holds unverified values) |
| AIPE-Simulation-Skills | ngspice as reusable tool; KiCad, FreeCAD, FEA skills | at HEAD no netlist generator, runner or raw parser; untracked `src/aipe_simulation/` (DAB spec, gating, netlist, runner) in flight (verifier); KiCad/FreeCAD/FEA folders are prose scaffolds |
| AIPE-Sketcher | Design schematic | attrs stored but never drawn; reference DAB has no series inductor; 16 drawable kinds; Core adapter read-only with exact schema_version and exact-key checks |
| AIPE-PCB-Agent | Converter-independent pipeline | models, templates, floorplan tables, deck builder and stability matrices are buck-specific; placement hand-coded; 8-direction router opt-in and left opens on V2.1; transformer not an anchor kind |
| AIPE-Solid-State-Transformer | DAB inductor sizing | ZVS criterion disabled by `Coss_pri/10000`; conduction-only "efficiency"; interactive `input()`; `sst_analysis.py` DC-link and THD errors |
| HeatSinkOptimisation | Heat-sink optimisation | natural convection only; dT fixed 40 K; no spreading, TIM, radiation, forced air; 100 repeats of one weighted problem, not a Pareto front |
| AIPE-Converter-Optimisation-Agent | Pareto optimisation and ANN surrogate | buck only; f_sw frozen (unscaled SLSQP); all 21 "successes" spurious (verifier); ANN trained on 21 degenerate points |
| AIPE-MOSFET-ANN-Modelling | Device loss surrogate | one device; hard switching only; Eoff median error 18 %, up to 150 %; Zth floor 0.009 K/W below 1e-5 s and divergence past 1 s (verifier) |
| AIPE-IEEE-Paper-Agent | Core evidence mapping | no evidence-ID column or state ingestion; no PDF compile; two cited keys missing |
| AIPE-Doc | Report generation | no renderer; PDF via browser only (headless Chrome already paginates correctly, needs a wrapper, verifier-corrected); no 19-section DAB skeleton |
| AIPE-Academy | DAB lesson or lab | none; labs must be stdlib Python; ngspice netlist LTspice-flavoured and never executed |
| Spirit-Connect-AIPE-Labs | Workflow listing | no workflow page template; `resources/prototypes/dab.md:18-40` describes automation that does not exist |
| PowerElectronicsDeviceLibrary | Device modelling | virtual datasheet, Simulink export, PLECS import and test suite broken; SiC switching data at 25 degC only (verifier) |
| awesome-open-source-power-electronics | Tool catalogue | no licence, version or activity fields; 8 brief-named tools absent; Registry pin unreachable |
| AIPE-Magnetics-Agnet-Inductor-Design-Example | Inductor reference | no inductance, turns, material or source CAD; geometry recoverable from U3D only (verifier-corrected) |

## 5. Available numerical models and data

| Item | Path | Units and fields | Source and rights |
|---|---|---|---|
| DAB baseline state | `repos/AIPE-Core/examples/dab-10kw/engineering-state.json` | 10000 W, 800 V, 400 V, 100000 Hz, SI {value, unit}; semiconductors, magnetics, control, thermal absent | MIT, synthetic, immutable |
| 163 Wolfspeed SiC MOSFET records (119 discrete, 44 module) | `repos/AIPE-Semiconductor-Database/data/canonical/*.json` | Eon/Eoff in J over [Tj K, Vdc V, I A]; voltage_drop V; 90 four-D Rg tables in 45 devices; Cauer R K/W, C J/K; guard rows 1173.15/1273.15 K | PLECS XML, provenance manufacturer_model; access.license null |
| Legacy screening ratings | `repos/AIPE-Semiconductor-Database/legacy/v2/*.json` | vds_max for 58 devices, tj_max 175 degC (injected), rds_on for 95, package strings | unverified, flagged legacy (verifier) |
| C2M0080120D ANN and tables | `repos/AIPE-MOSFET-ANN-Modelling/models/` | Eon/Eoff uJ (I, V, Tj, Rgon, Rgoff); Vds(I, Tj); Zth(t) 0-1 s; 400/600 V rows synthetic 2x/3x | Wolfspeed datasheet Rev D; data NOASSERTION, code MIT |
| Wolfspeed SPICE libraries (412 JSON) | `repos/AIPE-Design-Agent/data/spice_models_json/files/` | electro-thermal subckts `d g s Tj Tc`; C2M/C3M 650-1700 V | vendor disclaimers; Schottky set organisation-only |
| 25 digitised device records | `repos/PowerElectronicsDeviceLibrary/transistordatabase/examples/tdb_example/` | channel V-I (degC), Eon/Eoff vs I (SiC at 25 degC only), Coss(V), Eoss in 9/25, Foster 24/25 | datasheet traces, NOASSERTION; code GPL-3.0 |
| Magnetics catalogue (22 real, 3 synthetic) | `repos/AIPE-Magnetics-Database/src/aipe_magnetics/data/catalog/` | N87 Bsat 0.49/0.39 T, 6 Steinmetz sets; E65 Ae 535 mm^2, AN 426 mm^2; MagNet fits | TDK/Ferroxcube transcriptions NOASSERTION; MagNet fits MIT |
| Core and material tables | `repos/AIPE-Design-Agent/pea/tools/magnetics_data.py` | 33 cores Ae/le/Ve/Aw/Al; 7 ferrites with Steinmetz about 100x too high | unreferenced, MIT |
| SPS DAB kernels | `repos/AIPE-Solid-State-Transformer/code/DAB_inductor_selection.py:25-52`; `repos/AIPE-Magnetics-Database/src/aipe_magnetics/design/transformers/dab.py`; `repos/AIPE-Design-Agent/pea/converters/dab_sps.py` (untracked) | at spec: L 44.44 uH (30 deg), Irms 14.14 A, Ipk 15.0 A; Krismer form with D1, D2 verified | CC-BY-4.0 / NOASSERTION / MIT |
| Plate-fin heat-sink correlations | `repos/HeatSinkOptimisation/HS_main.py:7-53` | Elenbaas, Bar-Cohen-Rohsenow, fin efficiency; air at about 320 K, BETA at 300 K | CC-BY-4.0; literature |
| TI TIDA-010054 analysis | `repos/AIPE-PCB-Agent/knowledge/references/ti/tida-010054/`; `repos/AIPE-Workflows/examples/dab-10kw/references/tida-010054-fact-sheet.md` | Ls 35 uH, n 1.6, 200 ns dead time; EC-010..013 (Pmax 22.85 kW, phi 23 deg) | TI copyright; redistribution prohibited, analysis only |
| Buck ngspice decks | `repos/AIPE-Simulation-Skills/pe-ngspice-switching-validation/assets/ideal-buck.cir`; `repos/AIPE-PCB-Agent/automation/simulation/buck_stage.py` | ideal SW models; 23.57 V mean verified | NOASSERTION |
| DAB teaching constants (100 W cell) | `repos/Spirit-Connect-AIPE-Labs/_posts/2026-09-10-dab-*.md` | 48 V, n 1, 50 kHz, 20 uH; phi 0.3016767 rad, Irms 2.22965 A, pole 14.70 Hz | CC-BY-4.0 (terms page conflicts) |
| Planar PCB inductor geometry | `repos/AIPE-Magnetics-Agnet-Inductor-Design-Example/images/*.pdf` | U3D meshes; core body 31.75x20.32x9.525 mm (ELP32 class), board 23.92x46.67 mm; 13 A and 21 A | CC-BY-4.0; Altium 18 export (verifier-recovered) |
| V3 buck PCB evidence | `repos/AIPE-PCB-Agent/examples/sic-buck-400v-200v-5kw-v3/` | DRC 0; DC mesh 1.167 mOhm; projected isolation 8.027 mm; 24 stability corners | NOASSERTION; 27 vendor PDFs cached outside git |
| Bibliographic index | `repos/AIPE-IEEE-Paper-Agent/PE_IEEE_reference/references-index.json` | 4758 records, 67 unique DAB keys (verifier-corrected) | Xplore metadata, rights unresolved |

## 6. Missing engineering algorithms by DAB stage

| Stage | Present | Missing |
|---|---|---|
| Circuit simulation | ngspice buck runs (Simulation-Skills test; PCB-Agent `buck_stage.py`); untracked DAB netlist generator in Simulation-Skills; Design-Agent `index.html:1127-1179` DAB template is electrically disconnected (verifier) | tracked, tested DAB netlist generator with vendor models and dead time; `.meas` or raw extraction of power, RMS, ZVS; convergence protocol applied to DAB |
| Waveform analysis | `PiecewiseLinear` algebra (`AIPE-Magnetics-Database/.../engineering/periodic.py`); three SPS current implementations | import of SPICE or CSV waveforms; ZVS detection from waveforms; EPS/DPS/TPS modulation |
| Semiconductor loss and thermal | Eon/Eoff tensors, Cauer networks (Semiconductor-DB); ANN for one part; Eoss integrals (PEDL, GPL) | `LossEvaluator` implementation; N-D interpolation with guard-row filter; Rg formula evaluator; Cauer transient solver; Rth_jc-Rth_cs-Rth_sa network; loss-Tj fixed point |
| Magnetics design | v0.2 transformer sizing, iGSE, fundamental Dowell; v0.3 harmonic Dowell, 1-D leakage, FEA (untested) | waveform-informed design in public API; leakage design to a target Ls; DC bias (i2GSE); insulation design; series-inductor path (`design/inductors/gapped.py` is DC plus ripple) |
| FEM and CFD | Magnetics-DB internal 2-D P1 FEM and 2.5-D thermal FE (untested); Gmsh and Elmer qualified locally | any repository that generates Gmsh geometry or Elmer SIF; CalculiX use; CFD (OpenFOAM absent) |
| CAD | E-core STEP (Magnetics-DB, E65/E70); box envelope (`AIPE-Design-Agent/pea/cad.py`) | heat-sink fin builder; enclosure and assembly; AIPE-CAD-Agent empty |
| PCB automation | full KiCad pipeline for buck (PCB-Agent) | DAB schematic template, transformer anchor, insulation standards engine, automatic placement |
| Control | averaged buck models (Academy, Simulation-Skills); buck ZOH stability (PCB-Agent); 100 W DAB PI design (Labs posts) | DAB plant model at 10 kW; controller tuning; digital delay and sampling |
| Optimisation | `pareto_front`, NSGA-II hook (Design-Agent); multi-fidelity engine (Magnetics-DB, untested) | DAB variable set (n, Ls, fsw, phi, devices, core, cooling); hard constraints (ZVS, ratings, Tj, saturation); consistent loss models |

## 7. Missing solver integrations

| Solver | Local status (2026-10-21) | Repository integration |
|---|---|---|
| ngspice 47 | installed (portable), RC test passed | Simulation-Skills test guard `shutil.which('ngspice')` misses `ngspice_con.exe` (verifier); PCB-Agent uses the KiCad DLL via ctypes; no tracked DAB deck |
| KiCad 10.0.6 | installed, `kicad-cli version` passed | PCB-Agent validated only with 10.0.7 SWIG pcbnew; Simulation-Skills docs cite "KiCad 9 CLI baseline" |
| FreeCAD 1.1.4 | installed, box and STEP test passed | no code calls it (Simulation-Skills prose; Design-Agent uses CadQuery) |
| Gmsh 4.15.2 | installed, tet mesh passed | optional mesher in Magnetics-DB with non-existent `[mesh]` extra |
| Elmer 26.1 | installed, slab T_max 305 K passed | no repository generates SIF; AIPE-Field-Simulation README-only |
| CalculiX | bundled with FreeCAD | none |
| OpenFOAM | not installed, not on winget | none |
| Xyce, LTspice | not installed | LTspice only as desktop launch bridge (`AIPE-Design-Agent/pea/desktop.py`); `.cir` assets LTspice-flavoured, never executed |
| PLECS, MATLAB | commercial, absent | export-only (Semiconductor-DB, PEDL); never validated in tool |
| pymoo, python-control, jsonschema[format] | not installed | Design-Agent NSGA-II unexercised; Simulation-Skills `buck_control.py` fails import; Core validator and Magnetics-DB fail closed |

## 8. Missing parameter ranges and device characteristics

Semiconductors: the canonical corpus has no ratings at all (Vds max, Id max, Tj max, package), no Coss, Eoss, Qoss, Qrr or Qg for any device (the Wolfspeed PLECS guide confirms the models carry none), no gate voltage on any curve, and Rg dependence as 4-D tables for only 45 of 163 devices; the other 118 carry PLECS formula strings whose validity range starts at the default Rg (5 ohm for C2M parts), so lower gate resistances are out of range. Eon/Eoff are tabulated at 800 V (sometimes 600 V) with Tj axes such as 25/125/900/1000 degC, so 150 degC is absent and naive interpolation spans the 900 degC guard row (demonstrated by the verifier at `services/interpolation`). No 650 V parts exist in the canonical corpus for the 400 V side (legacy v2 has 19 unverified 650 V ratings). PEDL SiC switching data exist at 25 degC only and Eoss curves in 9 of 25 records; the ANN training Rg range 1-30 ohm exceeds the vendor's 0-20 ohm, and its Eoff row labelled 150 degC is vendor 25 degC data on a remapped current axis (verifier). The Design-Agent Python library has no 1200 V MOSFET; Rth_cs, TIM and heat-sink data exist in no dataset (PCB-Agent `mechanical/thermal_interface.md` records a Fischer SK 56 basis of about 0.30 K/W). Vendor SPICE libraries have unverified ngspice compatibility.

Magnetics: Bsat, density and mu_i exist only for N87, 3C90 and 3C94; N87 has four datasheet loss points and temperature-specific Steinmetz sets (datasheet fit 95-105 degC); no DC-bias data; no litz, wire or bobbin catalogue; E-outline dimensions only for E65 and E70; no planar cores although the v0.2 schema supports `planar_E` and `pcb_trace`; thermal conductivities are generic class values with wide bounds; no measured (L3) data anywhere.

Cooling: air properties at one film temperature; no fan curves, heat-sink catalogue or coolant data.

## 9. Missing CAD and PCB automation

AIPE-CAD-Agent has no commits and AIPE-Field-Simulation is README-only, so there is no owner for mechanical CAD or FEM set-up. Mechanical geometry exists only as heuristic boxes (`AIPE-Design-Agent/pea/cad.py:25-41`), a faceted E-core STEP writer (`AIPE-Magnetics-Database/src/aipe_magnetics/geometry/export.py`) and a matplotlib `bar3d` picture (HeatSinkOptimisation); there is no plate-fin STEP builder, enclosure or assembly, and the Altium U3D models of the inductor example have no importer. AIPE-PCB-Agent is the only PCB automation: generic layers (schematic emitter, router, checkers, exports) are reusable, but every design-level element is buck-specific (`sic_buck_power_model.py`, `schematic_templates.py` single `buck_half_bridge` template, fixed poses in `automation/sic_v3/floorplan.py`, `buck_stage.build_deck`, buck plant matrices in `sic_v3/simulation.py`); transformers are not anchor kinds, no planar-transformer or busbar footprint generator exists, the functional clearance table is hard-coded twice rather than derived from IEC 60664-1, the 8-direction router is opt-in and slow, the toolchain is Windows plus KiCad 10.0.7 SWIG pcbnew only, and the repository has no packaging, CI or licence, embeds workstation paths in 931 tracked files and omits the `.aipe/v3` checkpoints needed to re-run V3 end to end (verifier). AIPE-Sketcher has no KiCad or SPICE export.

## 10. Integration incompatibilities

| Area | Incompatibility | Where |
|---|---|---|
| Schema URLs and pins | Core v0.1.0 `$ref` URLs do not resolve (no tag); consumers must vendor schemas; Magnetics-DB pins Core 4e664f0 and Registry f419260 by SHA-256; Sketcher requires schema_version exactly 0.1.0 and an exact-key extension (Core itself is looser) | `AIPE-Core/schemas/*.json`, `aipe_sketch/state.py:22,29` |
| Units | PEA flat dicts in uH/kHz/mOhm/mT/degC; SST kW/kHz/degC with phi normalised to phi/2pi; Semiconductor-DB K and J with `C` meaning coulomb; PEDL degC; ANN uJ/degC; Simulation-Skills `1/V` not in Core unit enum; Magnetics `duty` is not a phase shift | Core requires SI {value, unit} with evidence_refs |
| Turns-ratio convention | n = V2/V1 (`pea/tools/calculator.py`, `index.html`) versus n = Np/Ns (`pea/converters/dab_sps.py`, SST, Magnetics-DB): reciprocal | must be stated per contract |
| Core validation rules | `extensions` payloads are skipped by `validate.py:64-66`; every quantity needs non-rejected evidence_refs; evidence kind enum has no `reference`; `runs[].status` is configured, completed or failed; all 14 sections required, so fragments do not validate | `AIPE-Core/scripts/validate.py` |
| Registry | all sources required, no partial index; all 11 records pinned to pending-PR snapshots rather than merged commits; catalogue pin 2ff81b2 unreachable so `validate.py --checkouts` aborts; `aipe.sketch` record stale (AIPE-Sketch URL, NOASSERTION, pre-rename commit); lock sha256 computed on CRLF bytes (Simulation-Skills); manifest capability names differ from runtime ids (Magnetics-DB) | `AIPE-Registry/sources/repositories.yaml`, `snapshots.lock.json` |
| Rename AIPE-Sketch to AIPE-Sketcher | id `aipe.sketch`, extension key and provenance tool id are unchanged; update name, repository URL, licence, `aipe.core` optional true, outputs, tools and evidence in place, do not mint a new id; Labs `tools/generate_blog_circuits.py` defaults to `../AIPE-Sketch` and pins 5efe98c versus checkout 3e005d0 | `AIPE-Sketcher/aipe.yaml:2-3`, `tests/test_plugin_packaging.py:192-204` |
| Runtimes | Semiconductor-DB needs Python 3.11 for one `StrEnum` import; PEDL needs 3.11 plus PyQt5 and bson at import; AIPE-Doc is Node 18; Labs needs Ruby 3.3; Magnetics MCP needs mcp 2.x | mixed toolchains |
| Hashes and line endings | Sketcher writes SVG with CRLF on Windows so artifact hashes are OS-dependent; IEEE validation rewrites the tracked index each run; PCB-Agent regeneration changes KIIDs | provenance must key on canonical IR or source hashes |
| Namespaces | PCB-Agent flat top-level package `automation`; Converter-Opt `cardiff_*` names; PEDL fork shadows the upstream PyPI name | collisions when combined |
| Website | every Registry capability must be placed once in `_data/hub.yml` with a reviewed `zh_summary`; label enums accept only validation.status `tested`; sync needs the Academy fork at the locked revision | `Spirit-Connect-AIPE-Labs/tools/hub_data.py:221-241` |

## 11. Repository maturity and validation evidence

| Repository | Automated tests | CI | Real solvers versus mocks |
|---|---|---|---|
| AIPE-Core, AIPE-Registry | contract and registry tests | GitHub Actions | schema validation only |
| AIPE-Academy | 293 unittest, run locally | yes | pure Python labs; ngspice only detected, never run |
| AIPE-Simulation-Skills | 6 unittest (module errors without python-control) | yes, apt ngspice | one real ngspice run in CI; KiCad, FreeCAD, FEA never executed |
| AIPE-Sketcher | 244 unittest | 5 jobs | engine is the SVG pipeline itself; `check_manifest.py` fails on Windows autocrlf checkouts (verifier) |
| AIPE-IEEE-Paper-Agent | 21 unittest | yes | no LaTeX compile; index rewritten by tests |
| Spirit-Connect-AIPE-Labs | 60 unittest | yes, Jekyll | no solver; downloads marked "execution pending" |
| AIPE-Design-Agent | 105 pytest, sign/ratio assertions | yes | no solver; pymoo and cadquery tested through ImportError only |
| AIPE-Semiconductor-Database | 579 cases (local shim) | yes, 3.11 and 3.12 (remote run not confirmed) | PLECS/MATLAB export never executed in the tools |
| AIPE-Magnetics-Database | 545 pytest plus 58 checks; v0.3 layer 0 tests | yes, 3-OS matrix (no green run recorded) | internal ODE and FEM solvers run in tests; Gmsh optional |
| AIPE-PCB-Agent | 373 unittest (log) | none | real kicad-cli ERC/DRC and ngspice DLL when present; "skip is never a pass" |
| AIPE-Doc, HeatSinkOptimisation, AIPE-Solid-State-Transformer, AIPE-MOSFET-ANN-Modelling, inductor example, catalogue | none | none | n/a |
| AIPE-Converter-Optimisation-Agent | 2 pytest | none | scipy SLSQP only |
| PowerElectronicsDeviceLibrary | 18 pytest, not runnable | workflow exists, no evidence | artefacts from one manual export |

## 12. Licensing restrictions

| Class | Repositories or items | Constraint |
|---|---|---|
| NOASSERTION | catalogue, AIPE-Doc, Converter-Opt, Simulation-Skills, IEEE-Paper-Agent, Semiconductor-DB, Magnetics-DB, PCB-Agent (8 of 17) | all rights reserved by default; code cannot be vendored into MIT repositories; Registry accepts the value by convention only |
| Conflicting declarations | IEEE `release-config.json:8` MIT written into the Codex plugin manifest (verifier: only that ZIP); PEDL `pyproject.toml:12` MIT classifier versus GPL LICENSE; Labs `legal/terms.md:14` "do not reproduce" versus CC BY 4.0 | resolve before redistribution |
| CC-BY-4.0 | HeatSinkOptimisation, Academy, SST, inductor example, Labs | attribution, licence link and change notice per Section 3(a); patents and trademarks excluded (Section 2(b)(2)); content licence applied to code |
| GPL-3.0-only | PEDL code; Paderborn materialdatabase (never bundled); rfc3987 pulled in by Magnetics-DB `jsonschema[format]` (verifier); Gmsh GPL-2.0-or-later as CLI | no vendoring into MIT or NOASSERTION repositories; use data-format adapters or optional isolated bridges |
| Source-available non-commercial | Sketcher draft licence excludes paid employment (LICENSE:66-70); contributor ownership of `state.py` unresolved (LICENSE:24-32) | written permission needed for commercial or employer use |
| Vendor models | Wolfspeed SPICE and PLECS files (Design-Agent, Semiconductor-DB, MOSFET-ANN); Schottky libraries "may not be distributed outside your organization"; Wolfspeed logo in `TO247-3.gltf` | provenance must travel with values; no redistribution of derived datasets without clearance |
| Textbook extracts | Erickson PDF 65.8 MB tracked (`AIPE-IEEE-Paper-Agent/books/`); 2.1 MB text extraction tracked (`AIPE-Design-Agent/data/raw/`); chapter notes derivative | strip before any mirror; never expand |
| Manufacturer documents | TI TIDA-010054 redistribution prohibited; Wolfspeed references not verified (verifier-corrected); 27 cached PDFs outside git | link and analyse only |
| Educational and brand assets | MIT OCW CC BY-NC-SA (link only); AIPE and Spirit Connect logos without trademark licence (AIPE-Doc, Labs, Sketcher video) | no copying or implied endorsement |
| KiCad footprints | CC-BY-SA-4.0 with design exception | keep LICENSE.md, NOTICE.md beside copies |

## 13. Defects found

| Repository | File:line | Defect |
|---|---|---|
| HeatSinkOptimisation | `HS_main.py:66-69` | objective 0.5*Rha[K/W] + 0.5*mass[kg] un-normalised since commit 45004a0 removed /10 and /5 (confirmed) |
| HeatSinkOptimisation | `HS_main.py:83-87, 104` | "Pareto front" is 100 repeats of one fixed-weight DE; `optimal_params` is the last run; unseeded; design vectors discarded (confirmed) |
| HeatSinkOptimisation | `HS_main.py:39-53` | `t_bp` accepted but unused: no base conduction or spreading resistance (confirmed) |
| HeatSinkOptimisation | `HS_main.py:63, 85, 106` | dT fixed at 40 K; no heat load, ambient or fixed-point solve (confirmed) |
| HeatSinkOptimisation | `HS_main.py:7-16` | air properties at about 320 K with BETA at 300 K (about 7 %); undocumented 0.97 copper density factor; aluminium constants dead |
| HeatSinkOptimisation | `HS_main.py:32-36, 33` | fin tips, end faces and radiation omitted; `int()` fin count makes the objective discontinuous; verifier: eta spans 0.88-1.00, not >= 0.978, and the script runs in about 7 s, not minutes (refuted) |
| HeatSinkOptimisation | `heat_sink_optimization_summary.html:137, 160, 167, 181, 220-223` | stale normalised equation and 0.20 m bounds; reference placed after `</body>`; MathJax from CDN |
| AIPE-Design-Agent | `pea/tools/calculator.py:408` | leakage inductance uses `v1*n*v1` (= V1*V2); under-estimated by factor n (22.22 uH vs 44.44 uH at spec) (confirmed) |
| AIPE-Design-Agent | `pea/tools/calculator.py:412-415` | I_pk uses (pi - phi); RMS not the SPS result: 150 A and 52.4 A vs 15.0 A and 14.1 A at spec; README example 400 V to 48 V is 42x off (verifier) |
| AIPE-Design-Agent | `pea/tools/calculator.py:421, 399` | `ZVS_status` constant "Achievable"; phi accepted to 180 deg |
| AIPE-Design-Agent | `pea/tools/magnetics_data.py:98-141` | Steinmetz coefficients about 100x high (N87 7.57e6 W/m^3 at 100 kHz, 100 mT); `transformer_design(800, 400, 10000)` reports 4.4 kW core loss with no warning (verifier) |
| AIPE-Design-Agent | `pea/optimization.py:587-591, 682-683` | 0.08/0.015 loss fudges and LLC admission for P >= 200 W bias recommendations; verifier could not reproduce the audit's exact run figures |
| AIPE-Design-Agent | `pea/optimization.py` `_eligible_mosfets`, `_eligible_diodes` | fallback to the whole library: 30 V BSC0902NS recommended for an 800 V bus with 99.83 % efficiency and 311 % window fill (verifier) |
| AIPE-Design-Agent | `pea/optimization.py:430-437, 806-809` | x[2] and x[6] each drive two choices; constant K/W thermal model |
| AIPE-Design-Agent | `pea/components/schema.py:156-165` | Rth placeholders 45/65/55 K/W presented as device data; field never read (HeatSink verifier) |
| AIPE-Design-Agent | `index.html:1127-1179`; `pea/cli.py:138-199`; `pea/desktop.py:48-57` | DAB netlist transformer secondary never reaches the secondary bridge (verifier); `all([...])` treats 0.0 as missing; desktop server exposes `.env` |
| AIPE-Solid-State-Transformer | `code/DAB_inductor_selection.py:19, 86-87, 338, 317-430` | `Coss_pri = 92e-12/10000` disables ZVS bound; `np.roots` silently returns 0.25 above Pmax; bare `input()`; micro sign in prints crashes on cp936 consoles (verifier); `plt.show(block=False)` at 331 is non-blocking (verifier-corrected) |
| AIPE-Solid-State-Transformer | `code/sst_analysis.py:75-77, 151-152, 233-235` | DC link 1.35*V*sqrt(2) gives 763.7 V for 400 V (should be 540 V); THD >= 100 % always; 0.5 "K/kW" placeholder |
| AIPE-Converter-Optimisation-Agent | `optimization.py:73-102`; `physics.py:51, 57`; `parameters.py:88-90` | unscaled SLSQP freezes f_sw at 175 kHz; `n` means legs in losses but devices in volume (verifier-corrected); s*V term; heat-sink volume 800 m^3 |
| AIPE-MOSFET-ANN-Modelling | `C2Mseries_Full_Model_Test.py:29-40, 77-80`; `C2MSeries_ANN_full_model.py:31` | layer widths 16/25 vs shipped 32; CWD paths; default input file deleted in 503cffe |
| AIPE-MOSFET-ANN-Modelling | `models/C2M0080120D.json`; `app.py:171-181, 259-261` | Eoff 150 degC row is vendor 25 degC data (verifier); transposed Eon/Eoff surfaces; unsanitised pickle load in debug server |
| AIPE-Semiconductor-Database | `importers/plecs/__init__.py:134, 157, 202`; `cli.py:86`; `services/validation/__init__.py:89-90` | non-rounded Kelvin (218.14999999999998) breaks exact lookups in 83-109 records; Rg and Vgs conditions dropped; `import-library` defaults into `data/canonical`; monotonic check non-strict (6 modules with duplicate 473.15 K) |
| AIPE-Magnetics-Database | `database/loss.py:211-216`; `state/schema.py:15`; `pyproject.toml`; `workflows/dab_transformer.py:341-353`; `design/common.py:24-32` | range warnings wrong in both branches (verifier); packaged MES schema missing; `[viz]/[mesh]/[cad]` extras do not exist; self-asserted verification levels; Bsat clamped non-conservatively; version 0.2.0 vs 0.3.0 |
| AIPE-Sketcher | `aipe_sketch/netlist.py:64-73, 190`; `router.py:193-199`; `sketch.py:153-157`; `circuit_io.py:38` | attrs `label/sub/italic` silently consumed; `from_dict` requires `ports` while the CLI treats it optional (verifier); junction dots order-dependent; CRLF SVG on Windows (verifier); `version: true` accepted |
| AIPE-Simulation-Skills | `tests/test_open_examples.py:11-13, 35, 43`; `tests/test_metadata.py:19`; `scripts/update_readme.py:55-56` | module-level python-control import; `which('ngspice')` misses the Windows console binary; `.tran` replace unchecked; hard-coded 13 skills; KeyError before validator message |
| AIPE-PCB-Agent | `automation/sic_v3/calculations.py:43`; `schematics.py:65` and `floorplan.py:33`; `power_copper.py:99-100`; `simulation.py:294-296` | HS switching loss uses DC current, fixed k_RG 2.5; clearance table duplicated; hard-coded board coordinates; absolute host paths (931 files) (all sic_v3 lines verifier-corrected) |
| AIPE-IEEE-Paper-Agent | `PE_IEEE_reference/AIPE_intro_with_refs.tex:1`; `release-config.json:8`; `artifacts/evidence-matrix.md:3`; `scripts/package-release.py:136-138` | keys 11424256 and 10751872 missing; MIT claim; no evidence-ID column; every validation run rewrites the tracked index (verifier) |
| AIPE-Doc | `assets/template.js:38-59`; `scripts/check.mjs:10, 27, 43-51` | null dereference without controls nav (fails at line 57 first, verifier); output/ skipped; double-quoted attributes only; 4 hard-coded pair files; blank-page claims untested (verifier-refuted) |
| PowerElectronicsDeviceLibrary | `transistor.py:400, 1468, 2299-2302`; `database_manager.py:135, 146-148, 697`; `helper_functions.py:24-37, 272-278`; `templates/PLECS_Exporter_template_Diode.txt:15,30` | missing call parentheses; template absent; Tau fabricated equal to R (renders `Tau=""` when scalar, verifier-corrected); overwrite check never fires; PLECS import TypeError; name regex matches everything; Simulink NameError; diode curve off by one |
| Spirit-Connect-AIPE-Labs | `resources/prototypes/dab.md:18-40`; `zh/resources/prototypes/dab.md:13`; `_includes/hub-project-card.html:19,27,38`; `_data/i18n.yml:36,250`; `legal/terms.md:14` | unbacked automation claims; "2 kW" claim; internal URL treated as GitHub link; "All rights reserved" and terms page contradict CC BY |
| AIPE-Academy | `docs/architecture.md:39`; `index.html:133`; `assets/migrated/buck/buck_open_loop.cir:2,18` | 26 vs 27 tracks; "SPICE labs" advertised; LTspice-only netlist never executed |
| awesome-open-source-power-electronics | `README.md:8,12,52,25`; Registry `snapshots.lock.json:70` | capitalised TOC anchors (portability only); OpenMagnetics titled "OM"; transistordatabase under circuit simulation; unreachable pin; Horizon row is not a parser defect (verifier-corrected) |
| AIPE-Magnetics-Agnet-Inductor-Design-Example | `README.md:23,33,40`; `images/inductor2.pdf`, `inductor3.pdf` | "dimensional view" has no dimensions; PDF numbering swapped (v3 and v2.1); inductor3 is a bare board (verifier) |

## 14. Recommended extension points and "extend, do not duplicate" decisions

| Repository | Extend here | Do not duplicate |
|---|---|---|
| AIPE-Design-Agent | fix `pea/tools/calculator.py:377-441` in place (keep output keys) by delegating to `pea/converters/dab_sps.py` once tracked and tested; add `DAB` to `pea/optimization.py:40` and the `_run_topology_design`, `_run_magnetics_design`, `_estimate_total_loss`, `_eligible_*` branches with rating constraints; new `pea/thermal.py` wired to `optimization.py:575, 737, 806`; adapters beside `pea/adapters/__init__.py` and a dispatch dict at `pea/orchestration/__main__.py:37`; declare capabilities in `aipe.yaml` and `examples/ecosystem/assessments.json` | SPS equations (three copies exist); Steinmetz tables (load from Magnetics-DB); device data (load from Semiconductor-DB) |
| AIPE-Semiconductor-Database | implement `services/loss/__init__.py` (for example `services/loss/dab.py`) with provenance; add N-D interpolation and envelope policy in `services/interpolation/__init__.py`; Cauer transient in `services/thermal/__init__.py`; safe Rg-formula evaluator; back-port `StrEnum` in `schema/enums.py:1`; clean-room TDB JSON adapter under `importers/legacy/` | PLECS parsers (exist here and in PEDL); TDB GPL code |
| AIPE-Magnetics-Database | register a waveform-informed `design_dab_transformer` in `api/__init__.py` so CLI and MCP inherit it; extend `api/types.py` with current waveform, phase shift and series inductance routed to `engineering/winding_harmonic.py`; add tests and `@check` functions for the v0.3 layer; add the missing extras and MES schema; widen `tools/build_catalog.py` core and material data; add `base_state` merging to `state/core_adapter.py` | a second magnetics engine or Steinmetz table in Design-Agent |
| AIPE-Simulation-Skills | land the untracked `src/aipe_simulation/` (ngspice locate, runner, rawfile, DAB spec, gating, netlist) with tests under `tests/`, a skills.json entry, `aipe.yaml` capability and README regeneration; fix the test guard to find `ngspice_con.exe`; add Gmsh/Elmer problem decks to `pe-open-fea-problem-setup/` | a parallel ngspice runner (PCB-Agent has a ctypes one for the KiCad DLL; keep both documented, share decks) |
| HeatSinkOptimisation | none in-repo (archived, CC BY): port corrected formulas (`HS_main.py:19-58`) into the Design-Agent thermal module with attribution, adding spreading, TIM, forced convection and a dT fixed point; use `heat_sink_geometry.png` parameters as the shared fin geometry for CAD | the `fitness`/100-run loop; Design-Agent `pareto_front` already exists |
| AIPE-Solid-State-Transformer | reuse only the Krismer D1/D2 RMS form (`DAB_inductor_selection.py:25-52`) and the modulator-resolution Lmin (`:259-300`) with CC BY attribution; fix `Coss_pri` before any ZVS use | SPS power and ZVS limits (MIT versions exist in `dab_sps.py`) |
| AIPE-PCB-Agent | add `dab_full_bridge` in `schematic_templates.py`; transformer as anchor in `schematic_presentation.py:60`; `dab_common.py` beside `sic_buck_common.py`; `automation/simulation/dab_stage.py` reusing `ngspice_runner.py`; new `layout_spec_<board>.json` for `check_sic_layout.py`; parameterise `freeze_release.py` and `verify_package.py`; add `aipe.yaml`, LICENSE, pyproject, CI, LFS | forking `grid_router.py`/`pairwise_router.py` (drive them with plan dicts) |
| AIPE-Sketcher | `aipe_sketch/presentation.py` to draw attrs; relax `state.py:29`; new kinds in `electrical.py`/`pins.py`/`parts.py`; DAB variants in `topologies.py`; round junction coordinates in `router.py:193-199`; binary SVG write in `sketch.py:153-157`; add `.gitattributes` | a second schematic renderer |
| AIPE-Core | no schema change: report and CAD artefacts as `evidence[].artifacts[]`; heat-sink and DAB operating data under namespaced `extensions` reusing `common.schema.json` mass/volume/area defs; keep the example immutable | parallel state schemas (Magnetics MES must map, not replace) |
| AIPE-Registry | re-point `sources/repositories.yaml` entries from PR refs to merged commits; refresh `aipe.sketch` in place; add manifests for PCB-Agent, Workflows, Field-Simulation, CAD-Agent only once `aipe.yaml` files exist; record HeatSink, SST, Converter-Opt, PEDL, ANN only as deprecated/experimental research sources | bulk-importing catalogue entries as capabilities |
| AIPE-Workflows | `src/aipe_workflows/reporting/` renders Core state into AIPE-Doc classes (pinned to f7c74e5) and headless-Chrome PDF; orchestration composes Design-Agent, Simulation-Skills, Semiconductor-DB, Magnetics-DB, PCB-Agent by Registry id | re-implementing any solver wrapper |
| AIPE-Doc | add `templates/report.html` with the 19 required sections and provenance slots; `scripts/export-pdf.mjs`; root argument and null guards in `check.mjs` and `template.js`; `aipe.yaml` | a second brand or CSS system |
| AIPE-IEEE-Paper-Agent | evidence-ID columns in `artifacts/evidence-matrix.md`; `--evidence` option in `create-manuscript.py`; `check-evidence.py`; keyword `tags` in `build-reference-index.py`; resolve licence; remove `books/` from history | a second bibliography store |
| AIPE-Academy | `labs/power-electronics/dab_sps.py` (stdlib) with `tests/test_lab_dab_sps.py`, lesson from `templates/lesson-template.md`, catalogue record under `pe.isolated` | numpy-based engines as labs |
| Spirit-Connect-AIPE-Labs | `site.dab-engineering-workflow` card in `_data/hub.yml` after line 339; rewrite `resources/prototypes/dab.md` (EN and ZH) as the workflow page; fix the "2 kW" wording; resolve `legal/terms.md` | restating Registry metadata on cards |
| PowerElectronicsDeviceLibrary, AIPE-MOSFET-ANN-Modelling, AIPE-Converter-Optimisation-Agent, inductor example, catalogue | treat as read-only data or pattern sources; ANN recipe may be re-trained from Semiconductor-DB curves; catalogue needs a machine-readable sidecar and `aipe.yaml` on main | importing GPL code; growing the Cardiff buck port into the DAB optimiser; parsing Altium images for dimensions |

Decisions: the DAB optimiser and thermal screening belong in AIPE-Design-Agent; device data and loss evaluation in AIPE-Semiconductor-Database; magnetics in AIPE-Magnetics-Database; circuit simulation in AIPE-Simulation-Skills; PCB in AIPE-PCB-Agent; report assembly in AIPE-Workflows using AIPE-Doc. Research repositories (HeatSinkOptimisation, SST, Converter-Opt, ANN, PEDL) are sources to port from with attribution, never runtime dependencies.

## 15. Update after the integrated reference run (2026-10-21, later the same day)

The gaps recorded above were closed as follows; every row is backed by an executed task in
`examples/dab-10kw/results/` (envelope, tool version, hashed artifacts) and by tests in the repository named.

| Capability | Repository (branch `feat/dab-10kw-workflow`) | Executed evidence | Tests |
|---|---|---|---|
| Workflow engine: task graph, checkpoints, envelopes, gate ledger, iterate, HTML/MD/JSON report | AIPE-Workflows (new package) | 13-task reference run, 12 Core-valid state versions, two accepted iterations | `tests/` (18) |
| Lossless SPS analysis shared by calculator and workflow | AIPE-Design-Agent `pea/converters/dab_sps.py` | analytic-sps task | `tests/test_dab_sps.py` |
| Thermal networks, electrothermal loop, cooling comparison, Stage A Pareto | AIPE-Design-Agent `pea/thermal/` + corrected `HeatSinkOptimisation/heatsink_model.py` (12 defects fixed, CC BY 4.0 kept) | thermal-cooling-design task | `tests/test_thermal_*.py` (31), HeatSinkOptimisation `tests/` (27) |
| ngspice DAB generator (Levels 1-2), raw-file reader, waveform analysis engine, SPS control baseline | AIPE-Simulation-Skills `src/aipe_simulation/` (new package, console `aipe-sim`) | circuit-sim-level1/-convergence/-level2, control-baseline | `tests/` (236) |
| DAB device screening, loss evaluation on waveforms, measurement requests, candidate import | AIPE-Semiconductor-Database `src/aipe_devices/services/{selection,loss}/dab.py`, `cli_dab.py` | semiconductor-screening task | `tests/` (632) |
| Waveform-informed transformer design, measurement requests, Core state export | AIPE-Magnetics-Database `aipe_magnetics.api.design_transformer_from_waveforms` | magnetics-transformer-design task | `tests/` (1044) |
| Gmsh + Elmer window magnetostatics and heat-sink conduction with analytic benchmarks | AIPE-Field-Simulation `aipe_fieldsim` (new package) | fem-transformer-window, fem-heatsink tasks | `tests/` (37) |
| Parametric FreeCAD transformer / heat sink / cold plate / assembly with checks | AIPE-CAD-Agent (first commit) | cad-transformer, cad-heatsink tasks | `tests/` (63) |
| Registry: Workflows, Doc, Field-Simulation, CAD-Agent registered; Sketcher rename; index rebuilt | AIPE-Registry | `generated/aipe.json` | `tests/` (43) |
| Hub website mirror and cards | Spirit-Connect-AIPE-Labs | `_data/registry.json` = `aipe.json` | 60 checks |

Still open after this run: PCB generation as a workflow task (AIPE-PCB-Agent produces the three KiCad boards and ERC/DRC in
its own repository), CFD (OpenFOAM not installable on this Windows host through winget; job specification only), manufacturer
SPICE models (Level 3, vendor files not redistributable), measurement and hardware qualification (human records only).

## 16. Stabilisation V0.1 (2026-10-21, later the same day)

AIPE-Design-Agent was renamed **AIPE-Electrical-Design** and refactored into the installable `aipe_electrical` package
(legacy PEA application archived at tag `legacy-pea-v0.1`); HeatSinkOptimisation was renamed **AIPE-Thermal-Design** and
consolidated with the former `pea.thermal` modules into `aipe_thermal`. The workflow adapters import these packages
directly (no sibling-directory lookup), the capability ids are `aipe.electrical-design` and `aipe.thermal-design`, and
the new `reconcile` command closes the magnetics/FEM → circuit-model parameter loop. The Design-Agent rows above are
historical audit records.

## Audit limitations

The agents worked offline and read-only: no GitHub CI results, upstream repositories, Xplore terms, vendor licence pages or GitHub redirects for the renamed Sketcher repository were checked. Several suites were not executed in the audit environment: PEDL (PyQt5 and bson absent), Semiconductor-DB and Magnetics-DB under their declared Python or `jsonschema[format]` extras (verifiers used in-process shims), Sketcher and PCB-Agent full suites (they write into the working tree), IEEE and Labs Jekyll builds. pymoo, cadquery, torch, python-control and the MCP SDK were not installed, so NSGA-II, STEP, ANN training, averaged control and MCP paths are unverified. Audit line numbers are unreliable for `AIPE-PCB-Agent/automation/sic_v3/*` (corrected above) and off by small offsets in Academy and Sketcher. Untracked work observed during the audit (`AIPE-Design-Agent/pea/converters/`, `AIPE-Simulation-Skills/src/aipe_simulation/`, a Magnetics-DB branch switch) was not frozen, so its state may have changed. Two verifiers recorded the local Elmer binary as "9.0" while the installation record says Elmer 26.1; the version string should be reconciled before it is cited as evidence. Nothing in the ecosystem has measured (L3) validation; no claim here should be read as hardware-verified.
