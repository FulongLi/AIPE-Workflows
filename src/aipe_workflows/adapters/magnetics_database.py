"""AIPE-Magnetics-Database adapter: waveform-informed DAB transformer design.

Feeds the executed ngspice waveform dataset (HDF5) into
``aipe_magnetics.api.design_transformer_from_waveforms`` and maps the ranked
candidates, the leakage/external-inductance split, the actual integer turns
ratio and the material comparison into the Engineering State. The selected
candidate's turns ratio and leakage are exposed as outputs so that a workflow
iteration can feed them back into the circuit simulation (task 18, example A).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..engine.envelope import ExecutionEnvelope, now_iso
from ..engine.runner import TaskAdapter, TaskContext
from .common import run_suffix


def _q(value: float, unit: str) -> dict[str, Any]:
    return {"value": float(value), "unit": unit}


def _first(d: dict, *keys, default=None):
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return default


class WaveformInformedTransformerTask(TaskAdapter):
    id = "aipe.magnetics-database.waveform-informed-transformer-design"
    version = "0.1.2"

    def requirements(self, environment: dict[str, Any]) -> list[str]:
        problems = []
        try:
            import aipe_magnetics.api  # noqa: F401
        except ImportError:
            problems.append("python package aipe_magnetics (AIPE-Magnetics-Database) is not installed: pip install -e ../AIPE-Magnetics-Database[hdf5]")
        try:
            import h5py  # noqa: F401
        except ImportError:
            problems.append("python package h5py is not installed (needed to read the waveform dataset): pip install h5py")
        return problems

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:
        import aipe_magnetics
        from aipe_magnetics import api as mag_api

        started = now_iso()
        p = ctx.task.parameters
        sim = ctx.inputs["simulation"]
        analytic = ctx.inputs["analytic"]
        req = ctx.inputs["requirements"]
        dataset = Path(sim["dataset"])
        summary = json.loads(Path(sim["summary_path"]).read_text(encoding="utf-8"))
        window = summary["window"]
        request = {
            "frequency": {"value": float(req["switching_frequency_Hz"]), "unit": "Hz"},
            "turns_ratio_target": float(analytic["n_ratio"]),
            "turns_ratio_tolerance": float(p.get("turns_ratio_tolerance", 0.05)),
            "series_inductance_total": {"value": float(analytic["l_total_H"]), "unit": "H"},
            "waveforms": {"kind": "hdf5", "path": str(dataset),
                          "channels": {"primary_current": "i_L", "secondary_current": "i_s", "primary_voltage": "v_tp", "magnetising_current": "i_m"},
                          "window": {"t0": {"value": window["t0"], "unit": "s"}, "t1": {"value": window["t1"], "unit": "s"}}},
            "materials": p.get("materials"),
            "temperature": {"value": float(p.get("design_temperature_K", 373.15)), "unit": "K"},
            "loss_density_target": {"value": float(p.get("loss_density_target_W_per_m3", 300e3)), "unit": "W/m^3"},
            "max_candidates": int(p.get("max_candidates", 12)),
        }
        if p.get("flux_limit"):
            request["flux_limit"] = p["flux_limit"]
        if p.get("thermal"):
            request["thermal"] = p["thermal"]
        if p.get("windings"):
            request["windings"] = p["windings"]
        result = mag_api.design_transformer_from_waveforms(request, created_at=started, export_state=True)
        envelope = ExecutionEnvelope(task_id=ctx.task.id, task_version=self.version, capability_id="aipe.magnetics-database",
                                     tool={"id": "aipe.magnetics-database.waveform-informed-design", "version": str(getattr(aipe_magnetics, "__version__", "unknown")),
                                           "name": "aipe_magnetics"},
                                     status="completed", started_at=started, finished_at=now_iso(), source_state_id=ctx.state.get("id", ""),
                                     source_state_sha256=ctx.state_sha256, inputs={"request": request, "dataset_sha256": sim.get("dataset_sha256")},
                                     model={"id": "aipe-magnetics-waveform-informed-transformer", "version": str(getattr(aipe_magnetics, "__version__", "unknown")),
                                            "validity_range": "analytical: exact harmonics, per-layer Dowell, iGSE on the actual flux, 1-D leakage, lumped/network thermal; no FEA, no insulation design"},
                                     evidence_kind="analytical", gate="analytical")
        payload = result.to_json_dict() if hasattr(result, "to_json_dict") else {"status": str(result)}
        out_path = ctx.task_dir / "magnetics-design-result.json"
        out_path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
        envelope.artifacts.append(ctx.artifacts.add(out_path, "analysis_summary", "waveform-informed transformer design result (aipe_magnetics)", ctx.task.id))
        if getattr(result, "status", "ok") != "ok":
            envelope.status = "failed"
            for error in getattr(result, "errors", []):
                envelope.add_error("magnetics", str(getattr(error, "message", error)))
            return envelope
        data = result.data
        candidates = data.get("candidates", [])
        if not candidates:
            envelope.status = "failed"
            envelope.add_error("magnetics-no-feasible-candidate", json.dumps(data.get("infeasible_summary", []))[:500])
            return envelope
        best = candidates[0]
        turns = best.get("turns")
        n1 = n2 = None
        if isinstance(turns, (list, tuple)) and len(turns) >= 2:
            n1, n2 = int(turns[0]), int(turns[1])
        elif isinstance(turns, dict):
            n1, n2 = _first(turns, "primary", "n1", "N1"), _first(turns, "secondary", "n2", "N2")
        actual_ratio = (float(n1) / float(n2)) if (n1 and n2) else float(_first(best, "turns_ratio", "turns_ratio_actual", default=analytic["n_ratio"]))
        l_leak = float(_first(best, "leakage_inductance_H", default=0.0))
        l_ext_req = float(_first(best, "external_inductance_required_H", default=float(analytic["l_total_H"]) - l_leak))
        l_m_raw = _first(best, "magnetising_inductance_H", "magnetising_inductance")
        l_m = None
        if isinstance(l_m_raw, (int, float)):
            l_m = float(l_m_raw)
        elif isinstance(l_m_raw, dict):
            for key in ("value", "reluctance_model_H", "inductance_H", "H", "datasheet_al_H", "estimate_H"):
                if isinstance(l_m_raw.get(key), (int, float)):
                    l_m = float(l_m_raw[key])
                    break
            if l_m is None:
                numeric = [v for k, v in l_m_raw.items() if isinstance(v, (int, float)) and k.endswith("_H")]
                l_m = float(numeric[0]) if numeric else None
        excitation = data.get("excitation", {})
        for warning in getattr(result, "warnings", [])[:10]:
            envelope.add_warning("magnetics", str(getattr(warning, "message", warning)))
        envelope.outputs = {
            "selected_core": data.get("selected_core") or data.get("selected"),
            "selected_candidate": best, "candidates_top": candidates[:5], "candidate_counts": data.get("candidate_counts"),
            "turns_primary": n1, "turns_secondary": n2, "turns_ratio_actual": actual_ratio,
            "leakage_inductance_H": l_leak, "external_inductance_required_H": l_ext_req, "magnetising_inductance_H": l_m,
            "core_loss_W": _first(best, "core_loss_W"), "copper_loss_W": _first(best, "copper_loss_W", "winding_loss_W"),
            "total_loss_W": _first(best, "total_loss_W"), "flux_density_peak_T": _first(best, "flux_density_peak_T"),
            "hot_spot_temperature_rise_K": _first(best, "hot_spot_temperature_rise_K", "temperature_rise_K", "dT_hot_spot_K"),
            "excitation": {k: excitation.get(k) for k in ("basis", "flux_linkage_peak_to_peak_Vs", "series_inductance_total_H", "throughput_power_W") if k in excitation},
            "square_current_comparison": data.get("square_current_comparison"),
            "material_comparison_summary": {"reference_core": (data.get("material_comparison") or {}).get("reference_core"),
                                            "rows": (data.get("material_comparison") or {}).get("rows", [])[:12]},
            "measurement_requests_count": len((data.get("measurement_requests") or {}).get("requests", [])) if isinstance(data.get("measurement_requests"), dict) else None,
            "loss_model_verification": data.get("loss_model_verification"), "result_path": str(out_path),
        }
        envelope.verification = {"feasible_candidates": (data.get("candidate_counts") or {}).get("feasible"),
                                 "evaluated_candidates": (data.get("candidate_counts") or {}).get("evaluated"),
                                 "external_inductance_consistent": abs(l_ext_req - (float(analytic["l_total_H"]) - l_leak)) < 1e-9,
                                 "core_state_export_valid": "engineering_state" in data}
        suffix = run_suffix(ctx.run_id)
        evidence_id = f"evidence.magnetics-design-{suffix}"
        sim_evidence = sim.get("evidence_id")
        inputs_ev = ["evidence.specification", analytic.get("evidence_id")] + ([sim_evidence] if sim_evidence else [])
        evidence = {
            "id": evidence_id, "kind": "analytical",
            "description": (f"Waveform-informed transformer design from the executed Level 1 dataset: selected {envelope.outputs['selected_core']} "
                            f"{n1}:{n2} turns, L_leak = {l_leak*1e6:.2f} uH, external inductance required {l_ext_req*1e6:.2f} uH, "
                            f"total loss {envelope.outputs['total_loss_W']} W at the design temperature; analytical models only (1-D Dowell, iGSE, 1-D leakage)."),
            "source": {"type": "repository", "reference": "https://github.com/FulongLi/AIPE-Magnetics-Database", "locator": "src/aipe_magnetics/design/transformers/waveform_informed.py"},
            "provenance": {"created_at": started, "activity": "Design transformer candidates from imported winding waveforms; rank feasible candidates by total loss.",
                           "tool": {"id": "aipe.magnetics-database.waveform-informed-design", "version": str(getattr(aipe_magnetics, "__version__", "unknown"))},
                           "agent": {"id": "aipe.workflows", "version": "0.1.0"}, "inputs": [e for e in inputs_ev if e]},
            "artifacts": [a.to_core() for a in envelope.artifacts], "review_status": "unreviewed",
        }
        transformer_entry = {"id": "magnetics.transformer-design", "role": "dab-isolation-transformer-candidate", "kind": "transformer",
                             "design_status": "candidate", "turns_ratio": _q(actual_ratio, "1"), "leakage_inductance": _q(l_leak, "H"),
                             "evidence_refs": [evidence_id]}
        if l_m:
            transformer_entry["inductance"] = _q(float(l_m), "H")
        if isinstance(envelope.outputs["selected_core"], str):
            transformer_entry["database_ref"] = f"aipe-magnetics:{envelope.outputs['selected_core']}"
        envelope.state_proposal = {
            "evidence": [evidence],
            "append": [
                {"path": "magnetics", "value": transformer_entry},
                {"path": "magnetics", "value": {"id": "magnetics.external-series-inductor", "role": "dab-external-series-inductance-required",
                                                "kind": "inductor", "design_status": "candidate", "inductance": _q(l_ext_req, "H"), "evidence_refs": [evidence_id]}},
                {"path": "validation.checks", "value": {"id": f"check.magnetics-design-{suffix}", "kind": "analytical", "status": "pass",
                                                        "description": "Waveform-informed transformer candidates found with saturation, fill and thermal constraints satisfied; L_total - L_leak split recorded.",
                                                        "evidence_refs": [evidence_id]}},
            ],
            "extensions": {"aipe.workflows.dab": {"magnetics_design": {k: v for k, v in envelope.outputs.items() if k not in ("candidates_top", "selected_candidate")} | {"selected_candidate": best}}},
            "updated_at": now_iso(),
        }
        return envelope
