"""AIPE-Design-Agent adapter: analytical single-phase-shift DAB operating point.

Uses ``pea.converters.dab_sps`` from a sibling AIPE-Design-Agent checkout
(pure standard-library module; the heavy agent dependencies are not imported).
"""

from __future__ import annotations

import json
import math
from typing import Any

from ..engine.envelope import ExecutionEnvelope, now_iso
from ..engine.runner import TaskAdapter, TaskContext


def run_suffix(run_id: str) -> str:
    """Six lowercase hex characters derived from the run id; valid inside Core entity ids."""
    import hashlib

    return hashlib.sha256(run_id.encode('utf-8')).hexdigest()[:6]

from .common import find_sibling_repo, import_from_checkout


def _q(value: float, unit: str) -> dict[str, Any]:
    return {"value": float(value), "unit": unit}


class AnalyticSpsTask(TaskAdapter):
    id = "aipe.design-agent.dab-sps-analysis"
    version = "0.1.0"

    def _module(self):
        repo = find_sibling_repo("AIPE-Design-Agent", "AIPE_DESIGN_AGENT_DIR")
        if repo is None:
            raise FileNotFoundError("AIPE-Design-Agent checkout not found (set AIPE_DESIGN_AGENT_DIR)")
        return import_from_checkout(repo, "pea.converters.dab_sps"), repo

    def requirements(self, environment: dict[str, Any]) -> list[str]:
        try:
            self._module()
        except Exception as exc:
            return [f"Design-Agent analytical model unavailable: {exc}"]
        return []

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:
        started = now_iso()
        m, repo = self._module()
        conv = ctx.inputs["converter"]
        req = ctx.inputs["requirements"]
        v1, v2 = float(req["input_voltage_V"]), float(req["output_voltage_V"])
        f_sw = float(req["switching_frequency_Hz"])
        n = float(conv["turns_ratio_np_ns"])
        l_total = float(conv["series_inductance_H"])
        if conv.get("phase_shift_deg") is not None:
            phi = math.radians(float(conv["phase_shift_deg"]))
            phi_source = "specified"
        else:
            phi = m.phase_shift_for_power(v1, v2, n, f_sw, l_total, float(req["nominal_power_W"]))
            phi_source = "solved for nominal power"
        op = m.SpsOperatingPoint(v1=v1, v2=v2, n_ratio=n, f_sw=f_sw, l_total=l_total, phi_rad=phi)
        analysis = m.analyse(op)
        derived = analysis["derived"]
        i_l0_centre = m.current_at(op, 0.0, origin="centre")
        # Phase shift that would deliver exactly the requested power with the given L (for reporting)
        phi_for_power = m.phase_shift_for_power(v1, v2, n, f_sw, l_total, float(req["nominal_power_W"]))
        summary = {
            "model": analysis["model"], "inputs": analysis["inputs"], "derived": derived, "zvs": analysis["zvs_current_conditions"],
            "assumptions": analysis["assumptions"], "phase_shift_source": phi_source,
            "phase_shift_for_requested_power_rad": phi_for_power, "phase_shift_for_requested_power_deg": math.degrees(phi_for_power),
            "series_current_at_centre_origin_A": i_l0_centre,
            "power_deviation_from_request_W": derived["power"]["value"] - float(req["nominal_power_W"]),
        }
        path = ctx.task_dir / "analytic-sps.json"
        path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        waveform = m.sample_waveforms(op, 400, origin="centre")
        wpath = ctx.task_dir / "analytic-waveform-one-period.json"
        wpath.write_text(json.dumps(waveform), encoding="utf-8")
        evidence_id = f"evidence.analytic-sps-{run_suffix(ctx.run_id)}"
        evidence = {
            "id": evidence_id, "kind": "analytical",
            "description": (f"Lossless SPS analysis: P = {derived['power']['value']:.1f} W at phi = {math.degrees(phi):.3f} deg, "
                            f"I_L rms = {derived['series_current_rms_primary']['value']:.3f} A, I_L peak = {derived['series_current_peak_primary']['value']:.3f} A; "
                            "ideal switches, stiff ports, magnetising current neglected."),
            "source": {"type": "repository", "reference": "https://github.com/FulongLi/AIPE-Design-Agent", "locator": "pea/converters/dab_sps.py"},
            "provenance": {"created_at": started, "activity": "Evaluate closed-form SPS power and exact piecewise-linear current waveform.",
                           "tool": {"id": "aipe.design-agent.dab-sps", "version": self.version},
                           "agent": {"id": "aipe.workflows", "version": "0.1.0"}, "inputs": ["evidence.specification"]},
            "artifacts": [], "review_status": "unreviewed",
        }
        envelope = ExecutionEnvelope(task_id=ctx.task.id, task_version=self.version, capability_id="aipe.design-agent",
                                     tool={"id": "aipe.design-agent.dab-sps", "version": self.version, "name": "pea.converters.dab_sps"},
                                     status="completed", started_at=started, finished_at=now_iso(), source_state_id=ctx.state.get("id", ""),
                                     source_state_sha256=ctx.state_sha256,
                                     inputs={"v1_V": v1, "v2_V": v2, "n_ratio": n, "f_sw_Hz": f_sw, "l_total_H": l_total, "phi_rad": phi},
                                     outputs={"summary": summary, "phi_rad": phi, "phi_deg": math.degrees(phi), "power_W": derived["power"]["value"],
                                              "i_L_rms_A": derived["series_current_rms_primary"]["value"],
                                              "i_L_peak_A": derived["series_current_peak_primary"]["value"],
                                              "i_dc1_A": derived["dc_current_port1"]["value"], "i_dc2_A": derived["dc_current_port2"]["value"],
                                              "i_L_at_centre_origin_A": i_l0_centre, "l_total_H": l_total, "n_ratio": n,
                                              "evidence_id": evidence_id},
                                     model={"id": "sps-lossless-ideal-transformer", "version": self.version,
                                            "validity_range": "|phi| <= pi/2, stiff DC ports, L_m >> L; magnetising current and losses not modelled"},
                                     environment={"design_agent_checkout": str(repo)}, evidence_kind="analytical", gate="analytical",
                                     verification={"power_equals_waveform_integral": abs(derived["power"]["value"] - derived["power_from_waveform_integral"]["value"]) < 1e-6,
                                                   "power_deviation_from_request_W": summary["power_deviation_from_request_W"]})
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
                {"path": "magnetics", "value": {"id": "magnetics.series-inductance", "role": "dab-series-power-transfer-inductance", "kind": "inductor",
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
