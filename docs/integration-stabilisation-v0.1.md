# AIPE Ecosystem Stabilisation & Integration V0.1 — consolidated report

Date: 2026-10-21. Coordinator: the AIPE-Workflows integration session. Scope: the stabilisation task "AIPE Ecosystem
Stabilisation & Integration V0.1" (repair, refactoring and verification across the AIPE repositories after the first
10 kW DAB development cycle). Every statement below is backed by a file in the referenced repository branch, pull request
or run directory; no number was produced by anything other than an executed tool or test.

Legend — **merged**: on the default branch; **open PR**: delivered from the MrCoconut616 fork and awaiting the
maintainer (the automation account has push access only on AIPE-Electrical-Design and did not merge anything: every PR
is left for review, as the safeguards require when a repository permission is unavailable); **blocked**: cannot be
finished from this side.

## A. Repository updates

| Repository | What changed and why | Delivery |
| --- | --- | --- |
| AIPE-Electrical-Design (renamed from AIPE-Design-Agent) | Legacy PEA application removed (LangChain agent, RAG/knowledge base, Streamlit and static UIs, desktop launcher, component catalogue with 412 vendor SPICE JSON files, magnetics tables, untested calculators, candidate optimiser, CAD envelope, orchestration prototype — 473 files, archived at tag `legacy-pea-v0.1`); new installable `aipe_electrical` 0.2.0 with zero runtime dependencies (SPS DAB model with explicit semantics, waveform metrics, CCM sizing, first-order buck losses, Pareto helper, JSON/CLI interfaces); manifest id `aipe.electrical-design`; CI matrix 3.10–3.12; template README; `docs/models.md`, `docs/migration.md` | open PR [#3](https://github.com/FulongLi/AIPE-Electrical-Design/pull/3), CI pass |
| AIPE-Thermal-Design (renamed from HeatSinkOptimisation) | `heatsink_model.py` and the former `pea.thermal` modules consolidated into `aipe_thermal` 0.2.0 (heat-sink correlation model, networks with Foster/Cauer, electrothermal loop, cooling comparison, Stage A screening, DAB case, CLI, unit validation); no `HeatSinkOptimisation` / `HEATSINK_OPT_DIR` dependency left; per-file licence table (CC BY 4.0 model, MIT migrated modules); manifest `aipe.thermal-design`; CI; template README | open PR [#2](https://github.com/FulongLi/AIPE-Thermal-Design/pull/2), CI green on the fork (fork-PR workflow awaits maintainer approval upstream) |
| AIPE-CAD-Agent | Official repository held only an initial README; the developed implementation (72285a6) merged onto it with history, CI added, template README, docs split | open PR [#1](https://github.com/FulongLi/AIPE-CAD-Agent/pull/1) |
| AIPE-Workflows | CI without `\|\| true` (explicit Registry validation of the dependency manifests, task-graph/capability contract check); adapters migrated to `aipe_electrical` / `aipe_thermal`; new `reconcile` command; failed optional tasks no longer fail a run; control-adapter bookkeeping fix; template README; this report | open PRs [#2](https://github.com/FulongLi/AIPE-Workflows/pull/2) (CI) and [#3](https://github.com/FulongLi/AIPE-Workflows/pull/3) (stabilisation, includes #2), CI pass |
| AIPE-Registry | Every merged source pinned to an immutable commit through `refresh.py --remote`; `aipe.electrical-design` and `aipe.thermal-design` registered from their PR heads, `aipe.cad-agent` from its PR head, legacy `aipe.design-agent` kept as a migration alias; renames documented; index rebuilt (18 capabilities) | open PR [#3](https://github.com/FulongLi/AIPE-Registry/pull/3), CI pass |
| AIPE-Simulation-Skills | "Skills Validation" workflow repaired (it ran tests with a bare interpreter); package tests on 3.10–3.12 with ngspice, solver-execution proof, executed DAB example | open PR [#3](https://github.com/FulongLi/AIPE-Simulation-Skills/pull/3), all checks pass |
| AIPE-Field-Simulation | GitHub Actions added (unit matrix, executed-solver job with explicit "did not run" reporting) | open PR [#2](https://github.com/FulongLi/AIPE-Field-Simulation/pull/2) |
| AIPE-Doc | GitHub Actions running the template checker | open PR [#2](https://github.com/FulongLi/AIPE-Doc/pull/2) |
| Spirit-Connect-AIPE-Labs | Registry mirror resynced; hub cards for Electrical-Design and Thermal-Design, legacy identity placed without a card | open PR [#22](https://github.com/FulongLi/Spirit-Connect-AIPE-Labs/pull/22) |
| README standardisation (Core, Registry, Field-Simulation, Simulation-Skills, Semiconductor-Database, Magnetics-Database, Sketcher, Doc, Academy, IEEE-Paper-Agent, Spirit-Connect) | READMEs rewritten to the template; detailed content moved to `docs/`; every command executed; every test suite run | open PRs: Core [#2](https://github.com/FulongLi/AIPE-Core/pull/2), Registry [#4](https://github.com/FulongLi/AIPE-Registry/pull/4), Field-Simulation [#3](https://github.com/FulongLi/AIPE-Field-Simulation/pull/3), Simulation-Skills [#4](https://github.com/FulongLi/AIPE-Simulation-Skills/pull/4), Semiconductor [#4](https://github.com/FulongLi/AIPE-Semiconductor-Database/pull/4), Magnetics [#4](https://github.com/FulongLi/AIPE-Magnetics-Database/pull/4), Sketcher [#4](https://github.com/FulongLi/AIPE-Sketcher/pull/4), Doc [#3](https://github.com/FulongLi/AIPE-Doc/pull/3), Academy [#3](https://github.com/FulongLi/AIPE-Academy/pull/3), IEEE-Paper-Agent [#3](https://github.com/FulongLi/AIPE-IEEE-Paper-Agent/pull/3), Spirit-Connect [#21](https://github.com/FulongLi/Spirit-Connect-AIPE-Labs/pull/21) |
| AIPE-PCB-Agent | DAB-V1 board remediation (Task C) | see section F |

Not changed: AIPE-Core code (only its README and `docs/validation.md`), AIPE-Semiconductor-Database and
AIPE-Magnetics-Database code (README/docs only), awesome-open-source-power-electronics (archived catalogue).

## B. Refactoring outcomes

**Removed from AIPE-Electrical-Design** (archived at `legacy-pea-v0.1`, reversible): `pea/agent` (LangChain),
`pea/knowledge` + `data/raw` (RAG), `app.py`, `.streamlit/`, `index.html`, `pea/desktop.py`, `run_pea_desktop.bat`,
`pea/components` and 412 vendor SPICE JSON records, `pea/tools/magnetics_data.py` and the untested calculators,
`pea/optimization.py`, `pea/cad.py`, `pea/orchestration`, `pea/registry`, `pea/state`, `pea/adapters`, scripts,
`requirements*.txt`, `TESTING.md`, legacy tests, and `pea/thermal` (after `aipe_thermal` was importable).

**Retained / migrated:** the validated SPS DAB model → `aipe_electrical.converters.dab_sps` (typed `SpsOperatingPoint`,
`turns_ratio_np_ns` and derived `turns_ratio_ns_np`, `total_series_inductance_primary()` for external + leakage parts,
rad/deg helpers, `|phi| ≤ π/2` enforced, signed power with `power_flow_direction`, `design_for_power` replacing
`dab_design` with `series_inductance_total_uH` instead of the misnamed `leakage_inductance_uH`, ZVS only as
`*_zvs_current_direction_ok` with an evidence label); exact waveform metrics and CCM sizing → `aipe_electrical.analysis`;
a generic Pareto helper and the lossless SPS sweep → `aipe_electrical.optimisation` (no fabricated loss models);
JSON helpers and the `aipe-electrical` CLI → `aipe_electrical.interfaces`. 116 tests; the 10 kW benchmark reproduces
exactly (φ = 22.5°, P_max = 22 857.14 W, I_rms = 13.6775 A, I_peak = 14.2857 A), plus reverse flow, d ≠ 1, 0/±90°
limits and invalid inputs.

**Thermal:** `aipe_thermal.heatsink` (the corrected correlation model, `git mv` history kept, CC BY 4.0),
`network`, `electrothermal`, `cooling`, `screening`, `cases.dab_10kw`, `cli`, `units` (MIT). 84 tests including
bit-for-bit regression against the recorded run numbers (cooling 63.040 / 64.291 / 79.230 °C; Stage A knee A-001
0.4405 K/W, 0.2783 kg; heat-sink model 1.426012 K/W, 1.609200 kg). `_sibling.py` and the sibling lookup are gone.

**CAD:** the parametric FreeCAD implementation now lives in the official AIPE-CAD-Agent repository (PR #1), 63 tests
(53 pure-Python, 8 FreeCAD, 2 CadQuery).

**Where capabilities reside now:** electrical analysis — AIPE-Electrical-Design (`aipe.electrical-design`); thermal —
AIPE-Thermal-Design (`aipe.thermal-design`); CAD — AIPE-CAD-Agent (`aipe.cad-agent`); AIPE-Workflows holds only
adapters and orchestration.

## C. Resolved bugs

| Issue | Root cause | Change | Test evidence | Status |
| --- | --- | --- | --- | --- |
| Simulation-Skills "Skills Validation" red on every push | `readme-freshness.yml` ran `unittest discover` with a bare interpreter (no package, pytest, h5py): 13 import errors | job limited to README/skill validation; installed matrix job runs the tests, proves solver tests executed, runs an executed DAB example | PR #3: validate-skills pass, pytest 3.10/3.11/3.12 pass | open PR |
| Workflows CI could not fail on Registry validation | `validate.py … \|\| true`; explicit mode needs the complete manifest set | dependency repositories checked out; explicit complete set validated; plan/capability contract asserted | Workflows #2 CI pass (first attempts caught two real problems: blocker phrasing, missing CAD manifest upstream) | open PR |
| Registry pointed at merged PR heads, stale branches, old repository names | sources never re-pinned after merges/renames | `refresh.py --remote` pinning, renames documented, new ids registered | Registry #3 CI pass, 43 tests | open PR |
| Workflows adapters imported `pea.*` through a sibling-directory lookup of `AIPE-Design-Agent` / `HeatSinkOptimisation` | pre-rename integration | adapters import the installed `aipe_electrical` / `aipe_thermal`; capability ids `dab-sps-analysis`, `cooling-concept-comparison` | migrated run reproduces every compared value of the baseline (`examples/dab-10kw/results/migration-check-2026-10-21.json`) | open PR (Workflows #3) |
| Leakage-inductance mismatch between the circuit model and magnetics/FEM | circuit model kept the initial assumption (all 35 µH external, L_m 1 mH); no feedback path | `aipe-workflows reconcile` compares and derives the iterate child run | child it03 accepted: Level 2 loss 131.7 → 127.2 W, I_m,peak 2.03 → 0.40 A, secondary device loss 17.45 → 16.18 W, Tj 63.0 → 61.7 °C; child consistent (exit 0) | open PR (Workflows #3) |
| Every iteration child was "rejected" while the PCB check fails by design | a failed optional task set the run status `failed` | failed optional task → `completed_with_failed_optional` (exit 2), gate still `fail`, decision records a note | engine test `test_failed_optional_task_does_not_fail_the_run` | open PR (Workflows #3) |
| Control adapter `UnboundLocalError` on fresh execution | scenario-expectation table computed after it was referenced | computed first | child run it03 control-baseline completed (PM 55.4°, plant law 0.07 %) | open PR (Workflows #3) |
| `dab_design()` output `leakage_inductance_uH` named a total series inductance; ZVS reported as "achievable" from current direction | historic PEA semantics | `design_for_power` → `series_inductance_total_uH`; ZVS evidence label "necessary current-direction condition" | Electrical-Design tests (61 SPS tests) | open PR |
| Thermal package depended on a directory name | `_sibling.py` searched `../HeatSinkOptimisation` / `HEATSINK_OPT_DIR` | bundled `aipe_thermal.heatsink`; env var only warns | Thermal-Design `test_compat` | open PR |
| HeatSinkOptimisation first-run CI failure | validator needs `jsonschema[format]` | installed in the manifest job | Thermal CI run 39583151444 green | open PR |
| Workflows CI YAML (first commits) | unquoted `:` in step names, dict literal in a plain scalar | quoted names, block scalars | PR #2 run pass | open PR |

## D. CI status (observed on GitHub, 2026-10-21)

| Repository | Workflow | Result |
| --- | --- | --- |
| AIPE-Simulation-Skills | Package tests (3.10/3.11/3.12 + ngspice), Skills Validation | pass on PR #3 |
| AIPE-Electrical-Design | tests (3.10/3.11/3.12) | pass on PR #3 |
| AIPE-Thermal-Design | pytest 3.10/3.11/3.12 + manifest | green on the fork; upstream fork-PR run awaits approval |
| AIPE-Workflows | Validate AIPE-Workflows | pass on PR #2 and PR #3 |
| AIPE-Registry | Validate Registry | pass on PR #3 |
| AIPE-CAD-Agent | Tests (new) | no run yet: fork-PR workflows need maintainer approval in a repository that had none |
| AIPE-Field-Simulation, AIPE-Doc | new workflows | no run yet (same reason) |
| AIPE-Core, Semiconductor-Database, Magnetics-Database, Sketcher, Academy, IEEE-Paper-Agent, Spirit-Connect | existing workflows | success on main and on the README PRs (handover-D) |
| AIPE-PCB-Agent | — | see section F |

## E. DAB verification results

Baseline reference run (`runs/wf-dab-10kw-first`, legacy adapters): 13 tasks completed, PCB check failed by design;
gates analytical/software/circuit_simulation/field_simulation pass, cad_pcb fail. Migrated-adapter run
(`runs/wf-dab-10kw-stab`): every compared value identical (analytic operating point, Level 1/2 ngspice, control
margins, magnetics, device losses, cooling, FEM, CAD).

Reconciliation (task §11.1): `aipe-workflows reconcile runs/wf-dab-10kw-first --apply` → child `it03`, accepted.

| Quantity | parent (leakage 0, L_m 1 mH) | child it03 (leakage 1.48 µH FEM, L_m 5.18 mH FEM) |
| --- | --- | --- |
| Level 2 total loss | 131.7 W | 127.2 W |
| Level 2 magnetising current peak | 2.03 A | 0.40 A |
| Level 2 secondary RMS current | 27.11 A | 26.76 A |
| Secondary device loss (C3M0025065K) | 17.45 W | 16.18 W |
| Primary device loss (C4MS047120K) | 9.04 W | 9.05 W |
| Hottest junction, best cooling option | 63.0 °C | 61.7 °C |
| Heat-sink FEM hotspot | 332.8 K | 331.2 K |
| Level 1 power / RMS / ZVS, control margins, plant law | 9 996.8 W, 13.678 A, all ZVS; PM 55.4°; 0.07 % | unchanged |

Consistency checks (§11.3): input/output power balance of Level 2 (P1 9 694 → P2 9 608 W, loss 131.7 W, drift-corrected),
RMS/peak currents (13.68 / 14.32 A), switching timing (measured phase shift 22.21° at 22.5° command, dead time 200 ns),
device stresses (per-switch RMS 9.4 / 19.2 A, 810 / 412 V), device temperature assumptions (125 °C evaluation,
fixed points 48 / 57 °C), turns ratio (20:10 = 2.0 exactly), leakage (1.483 µH FEM vs 1.551 µH 1-D, −4.4 %), core and
copper losses (19.1 / 15.9 W), cooling (liquid 63.0, forced 64.3, natural 79.2 °C), CAD mass attribution (transformer
0.864 kg with ferrite 0.550 and copper 0.234; sink 0.275 kg vs 0.278 correlation), artifact hashes (verify reports no
problems) — all recorded in the run directories and `examples/dab-10kw/results/`.

Clean-checkout acceptance (§16): see section J; the executed result is appended there when the run finishes.

## F. PCB status

Baseline (kicad-cli on the merged boards): ERC 0 on all three boards; DRC errors 22 (primary: 20 clearance, 2 hole
clearance) / 2 (secondary: hole clearance) / 0 (control); unconnected items 82 / 81 / 499 (control placed, never
routed); schematic parity 0. Known causes: 0.5 mm pre-routed capacitor stubs against the 4 mm bus rule, via-to-net-tie
hole clearances, gate-driver bias/sense fan-outs on the 0.65 mm module rows, AC_B pour continuity, control router
exceeding the time box. Task C (branch `fix/dab-v1-routing`) is remediating the generator and re-routing; its result is
recorded in `stabilisation/handover-C.md` and in the final section of this report when delivered. Nothing has been
fabricated or energised; Gerbers are not manufacturing-ready while routing is incomplete.

## G. README standardisation

Template applied (purpose, Features, Installation, Usage, Project Information with version/status/developer Fulong
Li/organisation/licence, Documentation). Coordinator: AIPE-Workflows (376 words with commands), AIPE-CAD-Agent (354).
Task A: AIPE-Electrical-Design (274 core words). Task B: AIPE-Thermal-Design (298). Task D (handover-D): Core 376→343,
Registry 824→327, Field-Simulation 2579→407, Simulation-Skills 903→641 (generated, 13-row skill table), Semiconductor
1343→416, Magnetics 1209→461, Sketcher 551→449, Doc 583→388, Academy 1992→461, IEEE-Paper-Agent 1012→414,
Spirit-Connect 1338→376 (raw word counts). Every README command was executed in this environment; versions and licences
quoted from package metadata and licence files (several repositories declare no code licence — stated as such, never
invented); detailed material moved to `docs/*.md`; Chinese documentation preserved and linked. PCB-Agent README: Task C.

## H. GitHub delivery

All branches pushed to the MrCoconut616 forks; PRs opened against `FulongLi/<repo>` `main`. The automation account
has no write access (except AIPE-Electrical-Design, where the coordinator deliberately left PR #3 for review as well),
so **no PR was merged by the automation**; merge status: awaiting maintainer for every PR listed in section A.
Branch-level evidence: AIPE-Electrical-Design `legacy-pea-v0.1` tag on the fork; commit SHAs in the handover files.

## I. Outstanding issues

| Severity | Issue | Next action |
| --- | --- | --- |
| high | PCB boards not routed to completion (see F) | finish Task C's routing pass; re-run `pcb-erc-drc`; keep the gate `fail` until clean |
| high | 22 PRs await maintainer merge; Registry/Hub reference PR heads until then | merge in order: Electrical #3, Thermal #2, CAD #1 → Registry #3 (re-pin to merged commits) → Workflows #2/#3 → Spirit-Connect #21/#22 → README PRs |
| medium | fork-PR workflows in CAD, Thermal, Field-Simulation, Doc need a maintainer's approval to run | approve the first runs |
| medium | legacy id `aipe.design-agent` still in the index as alias | remove after Workflows #3 and Spirit-Connect #22 are merged |
| medium | manifests of the README-standardised repositories do not list the new `docs/*.md` files | add them in a follow-up (documentation_drift is only checked for listed files) |
| low | several repositories declare no code licence (Simulation-Skills, Semiconductor-Database, Magnetics-Database, PCB-Agent, Doc, IEEE-Paper-Agent) | owner decision |
| low | CFD not executed (OpenFOAM unavailable on this Windows host); film coefficients remain correlation inputs | run the recorded job spec on a Linux host |

## J. Reproduction

Clean-checkout acceptance harness: `stabilisation/acceptance/run_acceptance.ps1` with `sources.json` (official
repositories; PR heads while the stabilisation PRs are open) — clones, fresh venv, `pip install -e` per README,
`aipe-workflows doctor --qualify`, Core and Registry contract validation, `plan`, `run`, `verify`, `report`.

Developer workspace equivalent:

```sh
aipe-workflows doctor --qualify --workspace .
aipe-workflows run repos/AIPE-Workflows/examples/dab-10kw/specification.yaml --checkouts repos --run-dir runs/dab
aipe-workflows verify runs/dab --core repos/AIPE-Core
aipe-workflows reconcile runs/dab --apply --checkouts repos      # closes the magnetics/FEM -> circuit loop
aipe-workflows report runs/dab
```

Executed acceptance result: appended below when the clean-checkout run completes.
