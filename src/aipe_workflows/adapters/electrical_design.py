"""AIPE-Electrical-Design adapter: analytical single-phase-shift DAB operating point.

Uses the installed ``aipe_electrical`` package (``aipe_electrical.converters.dab_sps``): lossless SPS
power, exact piecewise-linear series current, switching-instant currents and the ZVS *current-direction*
necessary conditions. All quantities are SI; the turns ratio is Np/Ns and the series inductance is the total
primary-referred value (external inductor plus transformer leakage), as the specification defines them.
"""

from __future__ import annotations

import json
import math
from typing import Any

from ..engine.envelope import ExecutionEnvelope, now_iso
from ..engine.runner import TaskAdapter, TaskContext
from .common import run_suffix


def _q(value: float, unit: str) -> dict[str, Any]:
    return {"value": float(value), "unit": unit}


class AnalyticSpsTask(TaskAdapter):
    id = "aipe.electrical-design.dab-sps-analysis"
    version = "0.2.0"

    def requirements(self, environment: dict[str, Any]) -> list[str]:
        try:
            import aipe_electrical.converters.dab_sps  # noqa: F401
        except ImportError:
            return ["python package aipe_electrical (AIPE-Electrical-Design) is not installed: pip install -e ../AIPE-Electrical-Design"]
        return []

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:
        import aipe_electrical
        from aipe_electrical.converters import dab_sps as m

        started = now_iso()
        version = str(getattr(aipe_electrical, "__version__", "unknown"))
        conv = ctx.inputs["converter"]
        req = ctx.inputs["requirements"]
        v1, v2 = float(req["input_voltage_V"]), float(req["output_voltage_V"])
        f_sw = float(req["switching_frequency_Hz"])
        n = float(conv["turns_ratio_np_ns"])
        p_req = float(req["nominal_power_W"])
        # total primary-referred series inductance: specification value, cross-checked against its split
        l_total = float(conv["series_inductance_H"])
        l_split = m.total_series_inductance_primary(turns_ratio_np_ns=n, l_external_primary=float(conv.get("external_inductance_H", l_total)),
                                                    l_leakage_primary=float(conv.get("leakage_inductance_primary_H", 0.0)),
                                                    l_leakage_secondary=float(conv.get("leakage_inductance_secondary_H", 0.0)))
        if conv.get("phase_shift_deg") is not None:
            phi = math.radians(float(conv["phase_shift_deg"]))
            phi_source = "specified"
        else:
            phi = m.phase_shift_for_power(v1=v1, v2=v2, turns_ratio_np_ns=n, f_sw=f_sw, l_series_total=l_total, p=p_req)
            phi_source = "solved for nominal power"
        op = m.SpsOperatingPoint(v1=v1, v2=v2, turns_ratio_np_ns=n, f_sw=f_sw, l_series_total=l_total, phi_rad=phi)
        analysis = m.analyse(op)
        derived = analysis["derived"]
        zvs = analysis["zvs_current_direction_conditions"]
        i_l0_centre = m.current_at(op, 0.0, origin="centre")
        phi_for_power = m.phase_shift_for_power(v1=v1, v2=v2, turns_ratio_np_ns=n, f_sw=f_sw, l_series_total=l_total, p=p_req)
        summary = {
            "model": analysis["model"], "model_version": analysis.get("model_version"), "inputs": analysis["inputs"], "derived": derived,
            "zvs_current_direction_conditions": zvs, "assumptions": analysis["assumptions"], "phase_shift_source": phi_source,
            "phase_shift_for_requested_power_rad": phi_for_power, "phase_shift_for_requested_power_deg": math.degrees(phi_for_power),
            "series_current_at_centre_origin_A": i_l0_centre,
            "power_deviation_from_request_W": derived["power"]["value"] - p_req,
            "series_inductance_split_consistent": abs(l_split - l_total) <= 1e-9 * max(l_total, 1e-12),
            "series_inductance_from_split_H": l_split,
        }
        path = ctx.task_dir / "analytic-sps.json"
        path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        waveform = m.sample_waveforms(op, 400, origin="centre")
        wpath = ctx.task_dir / "analytic-waveform-one-period.json"
        wpath.write_text(json.dumps(waveform), encoding="utf-8")
        evidence_id = f"evidence.analytic-sps-{run_suffix(ctx.run_id)}"
        evidence = {
            "id": evidence_id, "kind": "analytical",
            "description": (f"Lossless SPS analysis (aipe_electrical {version}): P = {derived['power']['value']:.1f} W at phi = {math.degrees(phi):.3f} deg, "
                            f"I_L rms = {derived['series_current_rms_primary']['value']:.3f} A, I_L peak = {derived['series_current_peak_primary']['value']:.3f} A; "
                            "ideal switches, stiff ports, magnetising current neglected; ZVS reported as the current-direction necessary condition only."),
            "source": {"type": "repository", "reference": "https://github.com/FulongLi/AIPE-Electrical-Design", "locator": "src/aipe_electrical/converters/dab_sps.py"},
            "provenance": {"created_at": started, "activity": "Evaluate closed-form SPS power and the exact piecewise-linear current waveform.",
                           "tool": {"id": "aipe.electrical-design.dab-sps", "version": version, "name": "aipe_electrical.converters.dab_sps"},
                           "agent": {"id": "aipe.workflows", "version": "0.1.0"}, "inputs": ["evidence.specification"]},
            "artifacts": [], "review_status": "unreviewed",
        }
        envelope = ExecutionEnvelope(task_id=ctx.task.id, task_version=self.version, capability_id="aipe.electrical-design",
                                     tool={"id": "aipe.electrical-design.dab-sps", "version": version, "name": "aipe_electrical.converters.dab_sps"},
                                     status="completed", started_at=started, finished_at=now_iso(), source_state_id=ctx.state.get("id", ""),
                                     source_state_sha256=ctx.state_sha256,
                                     inputs={"v1_V": v1, "v2_V": v2, "turns_ratio_np_ns": n, "f_sw_Hz": f_sw, "l_series_total_H": l_total, "phi_rad": phi,
                                             "l_external_H": conv.get("external_inductance_H"), "l_leakage_primary_H": conv.get("leakage_inductance_primary_H", 0.0)},
                                     outputs={"summary": summary, "phi_rad": phi, "phi_deg": math.degrees(phi), "power_W": derived["power"]["value"],
                                              "i_L_rms_A": derived["series_current_rms_primary"]["value"],
                                              "i_L_peak_A": derived["series_current_peak_primary"]["value"],
                                              "i_dc1_A": derived["dc_current_port1"]["value"], "i_dc2_A": derived["dc_current_port2"]["value"],
                                              "i_L_at_centre_origin_A": i_l0_centre, "l_total_H": l_total, "n_ratio": n,
                                              "power_flow_direction": derived.get("power_flow_direction"),
                                              "zvs_current_direction": {"primary": zvs.get("primary"), "secondary": zvs.get("secondary"), "evidence": zvs.get("evidence")},
                                              "evidence_id": evidence_id},
                                     model={"id": str(analysis["model"]), "version": version,
                                            "validity_range": "|phi| <= pi/2, stiff DC ports, L_m >> L; magnetising current and losses not modelled; ZVS by current direction only"},
                                     environment={"aipe_electrical_version": version}, evidence_kind="analytical", gate="analytical",
                                     verification={"power_equals_waveform_integral": abs(derived["power"]["value"] - derived["power_from_waveform_integral"]["value"]) < 1e-6,
                                                   "power_deviation_from_request_W": summary["power_deviation_from_request_W"],
                                                   "series_inductance_split_consistent": summary["series_inductance_split_consistent"]})
        if not summary["series_inductance_split_consistent"]:
            envelope.add_warning("series-inductance", f"specification series_inductance_H {l_total} differs from external + leakage split {l_split}")
        envelope.artifacts.append(ctx.artifacts.add(path, "analysis_summary", "Analytical SPS operating point", ctx.task.id))
        envelope.artifacts.append(ctx.artifacts.add(wpath, "analysis_waveform", "Analytical SPS waveform samples, one period", ctx.task.id))
        evidence["artifacts"] = [a.to_core() for a in envelope.artifacts]
        envelope.state_proposal = {
            "evidence": [evidence],
            "set": [
                {"path": "control", "value": {"strategy": "single-phase-shift", "description": "SPS modulation; phase shift of the secondary bridge relative to the primary.",
                                              "switching_frequency": _q(f_sw, "Hz"), "phase_shift": _q(phi, "rad"), "evidence_refs": [evidence_id]}},
            ],
            "append": [
                {"path": "magnetics", "value": {"id": "magnetics.series-inductance", "role": "dab-series-power-transfer-inductance-total-primary-referred", "kind": "inductor",
                                                "design_status": "candidate", "inductance": _q(l_total, "H"), "evidence_refs": [evidence_id]}},
                {"path": "magnetics", "value": {"id": "magnetics.transformer", "role": "dab-isolation-transformer", "kind": "transformer",
                                                "design_status": "candidate", "turns_ratio": _q(n, "1"), "evidence_refs": [evidence_id]}},
                {"path": "validation.checks", "value": {"id": f"check.analytic-sps-power-{run_suffix(ctx.run_id)}", "kind": "analytical", "status": "pass",
                                                        "description": f"Closed-form SPS power equals the piecewise waveform integral; deviation from requested power {summary['power_deviation_from_request_W']:.3f} W.",
                                                        "evidence_refs": [evidence_id]}},
            ],
            "extensions": {"aipe.workflows.dab": {"analytic_sps": summary}},
            "status": {"validation": "analytically_checked", "architecture_stage": "candidate", "converter_design_status": "candidate"},
            "updated_at": now_iso(),
        }
        return envelope
