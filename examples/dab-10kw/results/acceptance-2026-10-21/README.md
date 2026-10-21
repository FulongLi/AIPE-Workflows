# Clean-checkout acceptance run, 2026-10-21 (task §16)

Executed with `tools/acceptance/run_acceptance.ps1` in a fresh workspace (`D:\aipe-acceptance`, Windows 11, Python 3.10.11,
fresh venv), 15:36–15:39 UTC. Nothing from the developer's checkouts was used; the repositories were cloned from
github.com/FulongLi at the commits listed in `acceptance.log` (PR heads where the stabilisation PRs are still open, see
`sources-used.json`).

| File | Content |
| --- | --- |
| `acceptance.log` | every command with its exit code; clone commits; pip list; doctor output; Core unittest (23 OK) and example validation; Registry validate (18 manifests, 13 warnings, 0 errors), `build_registry.py --check`, pytest (43 passed); plan/run/verify/report/status output |
| `doctor.json` | tool qualification: ngspice 47, KiCad 10.0.6, FreeCAD 1.1.4, Gmsh 4.15.2, Elmer 9.0 all qualified by known-answer cases; Python packages incl. aipe_electrical 0.2.0, aipe_thermal 0.2.0 |
| `plan.json`, `run.json` | 14 tasks planned, 13 completed, `pcb-erc-drc` failed by design (status `completed_with_failed_optional`, exit 2) |
| `verification.json` | gates analytical / software / circuit_simulation / field_simulation pass, cad_pcb fail, engineering_review / experimental / hardware_qualification not run; no artifact problems, no Engineering-State errors |
| `report.md` | the generated engineering review package of the run |
| `comparison-with-workspace-run.txt` | leaf-by-leaf comparison with `runs/wf-dab-10kw-stab`: 3 415 task leaves, 1 798 Engineering-State leaves; only run-specific evidence ids and the PCB counts differ (the acceptance checked the remediated PR #8 boards) |

Large artefacts (waveform HDF5, meshes, STEP/FCStd, KiCad reports) stay in the acceptance workspace; their SHA-256 hashes are
in `run.json` / the task envelopes referenced by `report.md`.
