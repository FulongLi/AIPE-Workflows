"""AIPE-Simulation-Skills control adapter: SPS digital control baseline.

Designs the cascaded current/voltage loops for the actual converter parameters,
runs the host closed-loop scenarios (soft start, load step, current limit,
power reversal, fault latching) and verifies the cycle-averaged plant law
against executed ngspice Level 1 runs at three phase shifts.
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any, Optional

from ..engine.envelope import ExecutionEnvelope, now_iso
from ..engine.runner import TaskAdapter, TaskContext
from .common import run_suffix


def _num(value: Any) -> Optional[float]:
    return float(value) if isinstance(value, (int, float)) else None


class SpsControlBaselineTask(TaskAdapter):
    id = "aipe.simulation-skills.sps-control-baseline"
    version = "0.1.0"

    def requirements(self, environment: dict[str, Any]) -> list[str]:
        try:
            import aipe_simulation.control  # noqa: F401
        except ImportError:
            return ["python package aipe_simulation.control (AIPE-Simulation-Skills >= 0.2) is not installed: pip install -e ../AIPE-Simulation-Skills"]
        return []

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:
        from aipe_simulation import __version__ as sim_version
        from aipe_simulation.control.plant import DabSpsPlantParameters
        from aipe_simulation.control.simulate import ControlDesign, run_baseline
        from aipe_simulation.control.verify import compare_power_with_ngspice, format_comparison_table
        from aipe_simulation.ngspice.locate import NgspiceInfo

        started = now_iso()
        p = ctx.task.parameters
        req, analytic = ctx.inputs["requirements"], ctx.inputs["analytic"]
        plant = DabSpsPlantParameters()
        names = {f.name for f in dataclasses.fields(plant)}
        overrides = {"v1": float(req["input_voltage_V"]), "n_ratio": float(analytic["n_ratio"]), "f_sw": float(req["switching_frequency_Hz"]),
                     "l_total": float(analytic["l_total_H"]), "r_load": float(req["output_voltage_V"]) ** 2 / float(req["nominal_power_W"])}
        overrides.update({k: v for k, v in (p.get("plant") or {}).items() if k in names})
        plant = dataclasses.replace(plant, **{k: v for k, v in overrides.items() if k in names})
        design_kwargs = {"plant": plant, "v_ref": float(req["output_voltage_V"]), "nominal_power_W": float(req["nominal_power_W"]),
                         "dead_time_s": float(p.get("dead_time_s", 200e-9))}
        design_names = {f.name for f in dataclasses.fields(ControlDesign)}
        design_kwargs.update({k: v for k, v in (p.get("design") or {}).items() if k in design_names})
        design = ControlDesign(**{k: v for k, v in design_kwargs.items() if k in design_names})
        problems = design.validate()
        envelope = ExecutionEnvelope(task_id=ctx.task.id, task_version=self.version, capability_id="aipe.simulation-skills",
                                     tool={"id": "aipe.simulation-skills.control", "version": sim_version, "name": "aipe_simulation.control"},
                                     status="completed", started_at=started, finished_at=now_iso(), source_state_id=ctx.state.get("id", ""),
                                     source_state_sha256=ctx.state_sha256, inputs={"design": design.to_dict()},
                                     model={"id": "dab-sps-cycle-averaged-plant-with-discrete-controllers", "version": sim_version,
                                            "validity_range": "cycle-averaged lossless plant with one computation and one measurement sample of delay; "
                                                              "no switching dynamics, sensor, ADC or firmware model"},
                                     evidence_kind="analytical", gate="analytical")
        if problems:
            envelope.status = "failed"
            for problem in problems:
                envelope.add_error("design-invalid", str(problem))
            return envelope
        out_dir = ctx.task_dir / "control"
        scenarios = tuple(p.get("scenarios", ("nominal", "fault", "input_sag")))
        baseline = run_baseline(design, out_dir, scenarios=scenarios, figures=bool(p.get("figures", True)))
        controllers = baseline.get("controllers", {})
        scenario_summaries = baseline.get("scenarios", {})
        verification = None
        tool_info = ctx.environment.get("tools", {}).get("ngspice", {})
        if tool_info.get("found") and p.get("verify_with_ngspice", True):
            ng = NgspiceInfo(path=tool_info["path"], version=str(tool_info.get("version")), version_output="", source=str(tool_info.get("source") or ""))
            verification = compare_power_with_ngspice(tuple(p.get("verification_phase_shifts_deg", (10.0, 22.5, 35.0))), ctx.task_dir / "plant-verification",
                                                      ngspice=ng, cycles=int(p.get("verification_cycles", 12)), params=plant, v2=float(req["output_voltage_V"]))
            (ctx.task_dir / "plant-verification.md").write_text(format_comparison_table(verification), encoding="utf-8")
            (ctx.task_dir / "plant-verification.json").write_text(json.dumps(verification, indent=2, default=str), encoding="utf-8")
            envelope.artifacts.append(ctx.artifacts.add(ctx.task_dir / "plant-verification.json", "comparison", "cycle-averaged plant versus executed ngspice Level 1 runs", ctx.task.id))
        summary_path = out_dir / "summary.json"
        if summary_path.is_file():
            envelope.artifacts.append(ctx.artifacts.add(summary_path, "analysis_summary", "control baseline summary (design, controllers, scenarios)", ctx.task.id))
        for h5 in sorted(out_dir.glob("traces_*.h5")):
            envelope.artifacts.append(ctx.artifacts.add(h5, "waveform_dataset", f"closed-loop host traces {h5.stem[7:]}", ctx.task.id))
        for fig in sorted(out_dir.glob("*.png")):
            envelope.artifacts.append(ctx.artifacts.add(fig, "figure", f"control baseline figure {fig.stem}", ctx.task.id))

        loops = controllers.get("loops", {})

        def loop(name: str, key: str) -> Optional[float]:
            return _num((loops.get(name) or {}).get(key))

        rows = (verification or {}).get("rows") or []
        scenario_overview = {}
        for name, entry in scenario_summaries.items():
            metrics = entry.get("metrics") or {}
            scenario_overview[name] = {"final_mode": entry.get("final_mode"), "trips": entry.get("trips"), "duration_s": entry.get("duration_s"),
                                       "metrics": {k: v for k, v in metrics.items() if isinstance(v, (int, float, str, bool)) or v is None}}
        # Scenario expectations: the canonical 'fault' and 'input_sag' scenarios are designed to end in a latched protection trip;
        # 'nominal' must not trip. Overridable through parameters.scenario_expectations: {name: "trip" | "no_trip"}.
        expectations = {"nominal": "no_trip", "fault": "trip", "input_sag": "trip"}
        expectations.update(p.get("scenario_expectations") or {})
        scenario_results = {}
        for name, entry in scenario_summaries.items():
            tripped = bool(entry.get("trips"))
            expected = expectations.get(name)
            scenario_results[name] = {"tripped": tripped, "expected": expected, "final_mode": entry.get("final_mode"),
                                      "as_expected": (expected is None) or (expected == "trip") == tripped}
        no_unexpected_trips = all(r["as_expected"] for r in scenario_results.values())
        envelope.outputs = {
            "design_sha256": baseline.get("design_sha256"), "operating_point": controllers.get("operating_point"),
            "sampling": controllers.get("sampling"),
            "current_loop": {k: v for k, v in (controllers.get("current_loop") or {}).items() if k != "pi"},
            "voltage_loop": {k: v for k, v in (controllers.get("voltage_loop") or {}).items() if k not in ("df22",)},
            "loop_margins": loops,
            "current_loop_crossover_Hz": loop("current_loop_nominal", "gain_crossover_hz"),
            "current_loop_phase_margin_deg": loop("current_loop_nominal", "phase_margin_deg"),
            "current_loop_gain_margin_dB": loop("current_loop_nominal", "gain_margin_db"),
            "voltage_loop_crossover_Hz": loop("voltage_loop_full_load", "gain_crossover_hz"),
            "voltage_loop_phase_margin_deg": loop("voltage_loop_full_load", "phase_margin_deg"),
            "voltage_loop_gain_margin_dB": loop("voltage_loop_full_load", "gain_margin_db"),
            "worst_phase_margin_deg": min((m for m in (_num(s.get("phase_margin_deg")) for s in loops.values()) if m is not None), default=None),
            "scenarios": scenario_overview, "scenario_results": scenario_results,
            "plant_verification_rows": [{k: r.get(k) for k in ("phi_deg", "p_plant_W", "p2_ngspice_W", "rel_err_p2", "p1_ngspice_W", "rel_err_p1", "valid")} for r in rows],
            "plant_verification_max_abs_rel_err_p2": (verification or {}).get("max_abs_rel_err_p2"),
            "plant_verification_all_valid": (verification or {}).get("all_valid"),
            "model_assumptions": baseline.get("model_assumptions"), "limitations": baseline.get("limitations"),
            "summary_path": str(summary_path),
        }
        margins_ok = all(m is None or m >= float(p.get("min_phase_margin_deg", 40.0)) for m in (_num(s.get("phase_margin_deg")) for s in loops.values()))
        plant_ok = verification is None or (verification.get("all_valid") and (verification.get("max_abs_rel_err_p2") or 0.0) <= float(p.get("plant_verification_tolerance", 0.03)))
        envelope.verification = {"design_valid": True, "phase_margins_ok": margins_ok, "min_phase_margin_deg": p.get("min_phase_margin_deg", 40.0),
                                 "plant_verification_rows": len(rows), "plant_verification_ok": plant_ok,
                                 "plant_verification_max_abs_rel_err_p2": (verification or {}).get("max_abs_rel_err_p2"), "scenarios_as_expected": no_unexpected_trips,
                                 "scenario_results": scenario_results}
        suffix = run_suffix(ctx.run_id)
        evidence_id = f"evidence.control-baseline-{suffix}"
        evidence = {
            "id": evidence_id, "kind": "analytical",
            "description": (f"SPS digital control baseline: discrete PI current loop (f_c target {envelope.outputs['current_loop'].get('f_c_target_Hz')} Hz, "
                            f"PM {envelope.outputs['current_loop_phase_margin_deg']} deg) and 2P2Z voltage loop (f_c target "
                            f"{envelope.outputs['voltage_loop'].get('f_c_target_Hz')} Hz, PM {envelope.outputs['voltage_loop_phase_margin_deg']} deg) on the cycle-averaged "
                            f"lossless plant; host scenarios {list(scenario_summaries)}; plant law versus executed ngspice Level 1 at "
                            f"{[r.get('phi_deg') for r in rows]} deg: max |dP2/P2| = {envelope.outputs['plant_verification_max_abs_rel_err_p2']}."),
            "source": {"type": "repository", "reference": "https://github.com/FulongLi/AIPE-Simulation-Skills", "locator": "src/aipe_simulation/control"},
            "provenance": {"created_at": started, "activity": "Design the controllers, run the host closed-loop scenarios, compare the plant law with ngspice.",
                           "tool": {"id": "aipe.simulation-skills.control", "version": sim_version},
                           "agent": {"id": "aipe.workflows", "version": "0.1.0"}, "inputs": [e for e in ["evidence.specification", analytic.get("evidence_id")] if e]},
            "artifacts": [a.to_core() for a in envelope.artifacts], "review_status": "unreviewed",
        }
        status = "pass" if (margins_ok and plant_ok and no_unexpected_trips) else "fail"
        envelope.state_proposal = {
            "evidence": [evidence],
            "append": [{"path": "validation.checks", "value": {"id": f"check.control-baseline-{suffix}", "kind": "analytical", "status": status,
                                                               "description": "Controller design valid with phase margins above the minimum; cycle-averaged plant matches executed ngspice Level 1 power within tolerance; host scenarios end in the expected modes.",
                                                               "evidence_refs": [evidence_id]}}],
            "extensions": {"aipe.workflows.dab": {"control_baseline": {k: v for k, v in envelope.outputs.items() if k not in ("loop_margins", "model_assumptions", "limitations")}}},
            "updated_at": now_iso(),
        }
        if status == "fail":
            envelope.add_warning("control-check", "one of the control checks did not pass; see verification")
        return envelope
