"""Reconciliation of the circuit model's converter parameters with magnetics/FEM results (no solver needed)."""

from __future__ import annotations

import json
from pathlib import Path

from aipe_workflows.optimisation.reconcile import reconcile


def _envelope(run: Path, task: str, outputs: dict, evidence_id: str) -> None:
    d = run / "tasks" / task
    d.mkdir(parents=True, exist_ok=True)
    (d / "envelope.json").write_text(json.dumps({"task_id": task, "status": "completed", "outputs": outputs,
                                                 "state_proposal": {"evidence": [{"id": evidence_id}]}}), encoding="utf-8")


def _run(tmp_path: Path, converter: dict) -> Path:
    run = tmp_path / "run"
    run.mkdir()
    (run / "specification.json").write_text(json.dumps({"converter": converter}), encoding="utf-8")
    tasks = {t: {"task_id": t, "status": "completed", "envelope_path": str(run / "tasks" / t / "envelope.json")}
             for t in ("magnetics-transformer-design", "fem-transformer-window")}
    (run / "run.json").write_text(json.dumps({"run_id": "run", "workflow_id": "aipe.workflow.converter-dab", "workflow_source": None,
                                               "run_dir": str(run), "spec_sha256": "0" * 64, "created_at": "2026-10-21T00:00:00Z",
                                               "status": "completed", "tasks": tasks}), encoding="utf-8")
    return run


BASE = {"series_inductance_H": 35e-6, "external_inductance_H": 35e-6, "leakage_inductance_primary_H": 0.0,
        "magnetising_inductance_H": 1e-3, "turns_ratio_np_ns": 2.0, "phase_shift_deg": 22.5}


def test_reconcile_proposes_fem_leakage_and_keeps_total_inductance(tmp_path):
    run = _run(tmp_path, BASE)
    _envelope(run, "magnetics-transformer-design", {"leakage_inductance_H": 1.55e-6, "magnetising_inductance_H": 3.9e-3,
                                                   "turns_ratio_actual": 2.0, "turns_primary": 20, "turns_secondary": 10}, "evidence.magnetics-design-abc")
    _envelope(run, "fem-transformer-window", {"L_leakage_primary_H_fem": 1.483e-6, "L_magnetising_primary_H_fem": 5.18e-3}, "evidence.fem-transformer-window-abc")
    result = reconcile(run, tolerance=0.02)
    assert not result["consistent"]
    changes = result["changes"]
    assert changes["converter.leakage_inductance_primary_H"] == 1.483e-6
    assert abs(changes["converter.external_inductance_H"] - (35e-6 - 1.483e-6)) < 1e-15
    assert changes["converter.magnetising_inductance_H"] == 5.18e-3
    assert "converter.turns_ratio_np_ns" not in changes            # 20:10 is exactly the specified 2.0
    by_path = {p["path"]: p for p in result["proposals"]}
    assert by_path["converter.leakage_inductance_primary_H"]["evidence_id"] == "evidence.fem-transformer-window-abc"
    info = by_path["(information)"]
    assert abs(info["relative_change"] - (1.483e-6 - 1.55e-6) / 1.55e-6) < 1e-9      # FEM vs 1-D agreement recorded
    assert (run / "reconciliation.json").is_file()


def test_reconcile_is_consistent_within_tolerance_and_prefers_magnetics_on_request(tmp_path):
    run = _run(tmp_path, {**BASE, "leakage_inductance_primary_H": 1.5e-6, "external_inductance_H": 33.5e-6, "magnetising_inductance_H": 3.9e-3})
    _envelope(run, "magnetics-transformer-design", {"leakage_inductance_H": 1.51e-6, "magnetising_inductance_H": 3.95e-3, "turns_ratio_actual": 2.0}, "evidence.m")
    result = reconcile(run, tolerance=0.02, prefer="magnetics")
    assert result["consistent"] and result["changes"] == {}
    assert all(p["within_tolerance"] for p in result["proposals"] if not p["path"].startswith("("))


def test_turns_ratio_change_re_solves_the_phase_shift(tmp_path):
    run = _run(tmp_path, BASE)
    _envelope(run, "magnetics-transformer-design", {"leakage_inductance_H": 0.0, "turns_ratio_actual": 2.1, "turns_primary": 21, "turns_secondary": 10}, "evidence.m")
    result = reconcile(run, tolerance=0.02)
    assert result["changes"]["converter.turns_ratio_np_ns"] == 2.1
    assert "converter.phase_shift_deg" in result["changes"] and result["changes"]["converter.phase_shift_deg"] is None
