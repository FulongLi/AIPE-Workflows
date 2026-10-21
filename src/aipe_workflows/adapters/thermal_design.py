"""AIPE-Thermal-Design adapter: cooling comparison and Stage A heat-sink screening.

Uses the installed ``aipe_thermal`` package (cooling comparison, Stage A Pareto screening and the heat-sink
correlation model it contains). The devices are the ones selected by the semiconductor screening task: their
evaluated per-device loss at the design junction temperature and their database junction-to-case resistance.
One shared heat sink per bridge is compared under natural convection, forced air and a liquid cold plate
(assumed comparison geometries, parameterisable), then the worse bridge is screened with a seeded Pareto search
of plate-fin geometries under extrusion bounds. The knee candidate is mapped to the parametrised FEM heat-sink
model so that the field-simulation task can verify it (Stage B).

Everything here is an analytical correlation estimate; no CFD, FEM or measured value is produced by this task.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from ..engine.envelope import ExecutionEnvelope, now_iso
from ..engine.runner import TaskAdapter, TaskContext
from .common import run_suffix


def _q(value: float, unit: str) -> dict[str, Any]:
    return {"value": float(value), "unit": unit}


def _compact_row(row: dict) -> dict:
    return {k: row.get(k) for k in ("candidate_id", "material", "variables", "objectives", "junction_check", "distance_to_utopia",
                                    "fem_verification_recommended", "flag_reason", "performance_summary", "warnings")}


class CoolingDesignTask(TaskAdapter):
    id = "aipe.thermal-design.cooling-screening"
    version = "0.2.0"

    def requirements(self, environment: dict[str, Any]) -> list[str]:
        try:
            import aipe_thermal.cooling  # noqa: F401
            import aipe_thermal.heatsink  # noqa: F401
            import aipe_thermal.screening  # noqa: F401
        except ImportError:
            return ["python package aipe_thermal (AIPE-Thermal-Design) is not installed: pip install -e ../AIPE-Thermal-Design"]
        return []

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:
        import aipe_thermal
        import aipe_thermal.heatsink as hm
        from aipe_thermal import cooling, screening
        from aipe_thermal.cases import dab_10kw as dab_case

        started = now_iso()
        version = str(getattr(aipe_thermal, "__version__", "unknown"))
        model_version = str(getattr(hm, "__version__", "unknown"))
        p = ctx.task.parameters
        env_spec = ctx.inputs.get("environment_spec") or {}
        semis = ctx.inputs["semiconductors"]
        t_ambient_C = float(p.get("t_ambient_C", float(env_spec.get("ambient_temperature_K", 313.15)) - 273.15))
        per_sink = int(p.get("devices_per_sink", 4))
        r_cs = float(p.get("rth_case_sink_K_per_W", 0.1))
        footprint = float(p.get("footprint_area_m2", 16e-3 * 20e-3))
        tj_design_C = float(p.get("tj_design_C", 125.0))
        assumptions = [
            f"Device loss per switch = semiconductor-database evaluation at Tj = {semis.get('junction_temperature_K')} K (fixed, conservative: no electrothermal closure on the shared sink).",
            f"Case-to-sink interface {r_cs} K/W (TIDUES0 pad value, reference), TO-247 footprint {footprint * 1e6:.0f} mm^2 (generic outline), {per_sink} devices per sink (one sink per bridge).",
            f"Junction design limit {tj_design_C} degC (assumption), absolute limit from the database rating where available.",
            "Comparison option geometries, the generic 60 mm fan curve, fan efficiency 0.25, coolant inlet (ambient + 5 K) and pump efficiency 0.3 are assumptions for the comparison; fan/pump datasheets replace them.",
            "Stage A bounds restrict fin thickness/gap/height to typical extrusion limits (assumption); the search is seeded and reproducible.",
        ]
        devices_by_bridge: dict[str, list] = {}
        powers: dict[str, Optional[float]] = {}
        for bridge in ("primary", "secondary"):
            loss = semis.get(f"{bridge}_loss_W")
            r_jc = semis.get(f"{bridge}_rth_jc_K_per_W")
            tj_max_K = semis.get(f"{bridge}_tj_max_rating_K")
            powers[bridge] = float(loss) if isinstance(loss, (int, float)) else None
            if powers[bridge] is None or not isinstance(r_jc, (int, float)):
                continue
            part = semis.get(f"{bridge}_part_number") or semis.get(f"{bridge}_device_id") or bridge
            tj_max_C = float(tj_max_K) - 273.15 if isinstance(tj_max_K, (int, float)) else float(p.get("tj_max_C", 175.0))
            devices_by_bridge[bridge] = [cooling.CoolingDevice(name=f"{bridge}-{i + 1}", power_W=powers[bridge], r_jc=float(r_jc), r_cs=r_cs,
                                                               footprint_area_m2=footprint, tj_max_C=tj_max_C, tj_design_C=tj_design_C,
                                                               note=f"{part}: database loss at the evaluation Tj, database Rth(j-c)")
                                         for i in range(per_sink)]
        envelope = ExecutionEnvelope(task_id=ctx.task.id, task_version=self.version, capability_id="aipe.thermal-design",
                                     tool={"id": "aipe.thermal-design.cooling-screening", "version": version, "name": f"aipe_thermal {version} (heat-sink model {model_version})"},
                                     status="completed", started_at=started, finished_at=now_iso(), source_state_id=ctx.state.get("id", ""),
                                     source_state_sha256=ctx.state_sha256,
                                     inputs={"t_ambient_C": t_ambient_C, "devices_per_sink": per_sink, "device_powers_W": powers, "rth_case_sink_K_per_W": r_cs,
                                             "footprint_area_m2": footprint, "tj_design_C": tj_design_C, "stage_a": p.get("stage_a")},
                                     model={"id": "aipe-thermal-cooling-comparison-and-stage-a", "version": model_version,
                                            "validity_range": "analytical correlations (Elenbaas/Bar-Cohen natural convection, Teertstra-Yovanovich-Culham channels, "
                                                              "Lee spreading, Shah-London/Gnielinski cold plate) with the validity notes recorded per evaluation; no CFD/FEM/measurement"},
                                     environment={"aipe_thermal_version": version, "heatsink_model_version": model_version},
                                     evidence_kind="analytical", gate="analytical")
        if not devices_by_bridge:
            envelope.status = "failed"
            envelope.add_error("no-devices", "semiconductor screening provided no device loss / Rth(j-c) for either bridge")
            return envelope
        options = [cooling.option_from_dict(o) for o in p["options"]] if p.get("options") else dab_case.cooling_options()
        comparison: dict[str, Any] = {}
        tj_by_option: dict[str, dict[str, float]] = {}
        result_paths: dict[str, str] = {}
        for bridge, devices in devices_by_bridge.items():
            result = cooling.compare_cooling_options(devices, options, t_ambient_C, electrothermal=False)
            path = ctx.task_dir / f"cooling-comparison-{bridge}.json"
            path.write_text(json.dumps(result, indent=2, default=dab_case.json_default), encoding="utf-8")
            result_paths[f"cooling_comparison_{bridge}"] = str(path)
            envelope.artifacts.append(ctx.artifacts.add(path, "analysis_summary", f"cooling comparison, {bridge} bridge ({per_sink} x {powers[bridge]:.2f} W)", ctx.task.id))
            comparison[bridge] = {"summary_table": result["summary_table"], "ranking_by_tj": result["ranking_by_tj"], "method": result["method"]}
            tj_by_option[bridge] = {row["option"]: row["tj_max_C"] for row in result["summary_table"]}
        worst_bridge = max(devices_by_bridge, key=lambda b: min(tj_by_option[b].values()))
        best_option = comparison[worst_bridge]["ranking_by_tj"][0]
        best_row = next(r for r in comparison[worst_bridge]["summary_table"] if r["option"] == best_option)

        # Stage A screening of the worse bridge
        sa = dict(p.get("stage_a") or {})
        task_dict = {"devices": [d.to_dict() for d in devices_by_bridge[worst_bridge]], "t_ambient_C": t_ambient_C, "cooling": sa.get("cooling", "forced"),
                     "materials": sa.get("materials", ["Al-6063-T5"]), "bounds": sa.get("bounds") or {}, "flow_bounds": sa.get("flow_bounds"),
                     "volumetric_flow": sa.get("volumetric_flow"), "fan_curve": sa.get("fan_curve"), "n_fans": sa.get("n_fans", 1),
                     "objectives": sa.get("objectives", ["r_th", "mass"]), "seed": sa.get("seed", 1), "n_weights": sa.get("n_weights", 5),
                     "n_epsilon": sa.get("n_epsilon", 3), "maxiter": sa.get("maxiter", 25), "popsize": sa.get("popsize", 10), "n_flag": sa.get("n_flag", 3),
                     "tj_limit_C": tj_design_C, "label": f"stage-A-{worst_bridge}-bridge-{sa.get('cooling', 'forced')}"}
        stage_a = screening.run_stage_a(screening.StageATask.from_dict(task_dict))
        sa_path = ctx.task_dir / "stage-a-heatsink-screening.json"
        sa_path.write_text(json.dumps(stage_a, indent=2, default=dab_case.json_default), encoding="utf-8")
        result_paths["stage_a"] = str(sa_path)
        envelope.artifacts.append(ctx.artifacts.add(sa_path, "analysis_summary", f"Stage A heat-sink Pareto screening, {worst_bridge} bridge", ctx.task.id))
        rows = stage_a.get("pareto_set", [])
        flagged_ids = stage_a.get("flagged_candidates", [])
        flagged = [r for r in rows if r.get("candidate_id") in flagged_ids]
        knee = next((r for r in flagged if "knee" in str(r.get("flag_reason", ""))), flagged[0] if flagged else None)

        fem_candidate = None
        if knee:
            v = knee["variables"]
            material = hm.get_material(knee.get("material") or "Al-6063-T5")
            sink = hm.PlateFinHeatSink(v["length"], v["width"], v["fin_height"], v["fin_thickness"], v["fin_gap"], v["base_thickness"], material)
            perf = knee.get("performance_summary") or {}
            r_conv, r_spread = perf.get("r_convective"), perf.get("r_spreading_max")
            fem_candidate = {
                "candidate_id": knee["candidate_id"], "material": knee.get("material"), "cooling": task_dict["cooling"],
                "base_length_m": v["length"], "base_width_m": v["width"], "base_thickness_m": v["base_thickness"],
                "fin_count": int(sink.n_fins), "fin_thickness_m": v["fin_thickness"], "fin_height_m": v["fin_height"], "fin_gap_effective_m": float(sink.gap_effective),
                "k_W_per_m_K": float(material.conductivity), "density_kg_per_m3": float(material.density),
                "h_W_per_m2_K": perf.get("h"), "volumetric_flow_m3_per_s": perf.get("volumetric_flow"),
                "r_convective_K_per_W": r_conv, "r_spreading_max_K_per_W": r_spread,
                "r_th_analytical_hotspot_K_per_W": (r_conv + r_spread) if isinstance(r_conv, (int, float)) and isinstance(r_spread, (int, float)) else None,
                "objectives": knee.get("objectives"), "junction_check": knee.get("junction_check"), "regime": perf.get("regime"), "fin_efficiency": perf.get("fin_efficiency"),
            }
        envelope.outputs = {
            "worst_bridge": worst_bridge, "t_ambient_C": t_ambient_C, "devices_per_sink": per_sink, "device_powers_W": powers,
            "comparison": comparison, "best_option": best_option, "tj_max_best_option_C": best_row["tj_max_C"],
            "best_option_row": best_row, "tj_max_by_option_C": tj_by_option,
            "stage_a_summary": {k: stage_a.get(k) for k in ("label", "method", "objectives", "n_candidates", "n_feasible", "utopia", "nadir", "next_stage", "disclaimer")}
                               | {"materials": task_dict["materials"], "bounds": task_dict["bounds"], "flow_bounds": task_dict["flow_bounds"],
                                  "settings": {k: task_dict[k] for k in ("seed", "n_weights", "n_epsilon", "maxiter", "popsize")}},
            "stage_a_knee_candidate": _compact_row(knee) if knee else None, "stage_a_flagged": [_compact_row(r) for r in flagged],
            "fem_candidate_geometry": fem_candidate, "assumptions": assumptions, "result_paths": result_paths,
        }
        within_design = bool(best_row.get("within_design_limit"))
        envelope.verification = {"best_option_within_design_limit": within_design, "best_option_within_absolute_limit": bool(best_row.get("within_absolute_limit")),
                                 "stage_a_feasible": stage_a.get("n_feasible"), "stage_a_candidates": stage_a.get("n_candidates"),
                                 "knee_feasible": bool((knee or {}).get("junction_check", {}).get("feasible")) if knee else None}
        suffix = run_suffix(ctx.run_id)
        evidence_id = f"evidence.thermal-cooling-{suffix}"
        evidence = {
            "id": evidence_id, "kind": "analytical",
            "description": (f"Cooling comparison (aipe_thermal {version}) for {per_sink} devices per bridge at {t_ambient_C:.0f} degC ambient with database losses/Rth: worst bridge {worst_bridge} "
                            f"({powers[worst_bridge]:.2f} W per device); best option '{best_option}' Tj,max = {best_row['tj_max_C']:.1f} degC "
                            f"(natural/forced/liquid: {', '.join(f'{k} {v:.1f}' for k, v in tj_by_option[worst_bridge].items())} degC). "
                            f"Stage A {task_dict['cooling']} Pareto screening: {stage_a.get('n_feasible')}/{stage_a.get('n_candidates')} feasible, knee "
                            f"{(knee or {}).get('candidate_id')} flagged for FEM verification. Analytical correlations only."),
            "source": {"type": "repository", "reference": "https://github.com/FulongLi/AIPE-Thermal-Design", "locator": "src/aipe_thermal"},
            "provenance": {"created_at": started, "activity": "Shared-sink network with correlation-based sink models for three cooling options per bridge; seeded Pareto screening of plate-fin geometries under extrusion bounds.",
                           "tool": {"id": "aipe.thermal-design.cooling-screening", "version": version},
                           "agent": {"id": "aipe.workflows", "version": "0.1.0"}, "inputs": [e for e in ["evidence.specification", semis.get("evidence_id")] if e]},
            "artifacts": [a.to_core() for a in envelope.artifacts], "review_status": "unreviewed",
        }
        total_loss = sum((powers[b] or 0.0) * per_sink for b in ("primary", "secondary") if powers.get(b) is not None)
        thermal_block = {
            "ambient_temperature": _q(t_ambient_C + 273.15, "K"),
            "junction_temperature": _q(best_row["tj_max_C"] + 273.15, "K"),
            "thermal_resistance": _q(best_row["r_hottest_total_K_per_W"], "K/W"),
            "total_loss": _q(total_loss, "W"),
            "description": (f"Analytical shared-sink estimate: hottest junction of the {worst_bridge} bridge on '{best_option}' with {per_sink} devices per sink; "
                            f"total_loss = all semiconductor losses at the evaluation Tj; thermal_resistance = hottest device junction-to-fluid path. Not a CFD/FEM/measured value."),
            "evidence_refs": sorted(set((ctx.state.get("thermal") or {}).get("evidence_refs", [])) | {evidence_id}),
        }
        envelope.state_proposal = {
            "evidence": [evidence],
            "set": [{"path": "thermal", "value": thermal_block}],
            "append": [{"path": "validation.checks", "value": {"id": f"check.thermal-cooling-{suffix}", "kind": "analytical",
                                                               "status": "pass" if within_design else "fail",
                                                               "description": f"Best cooling option keeps every junction below the {tj_design_C:.0f} degC design limit with database losses and Rth(j-c); Stage A knee candidate feasible.",
                                                               "evidence_refs": [evidence_id]}}],
            "extensions": {"aipe.workflows.dab": {"thermal_design": {k: v for k, v in envelope.outputs.items() if k not in ("comparison", "stage_a_flagged", "assumptions", "best_option_row")}}},
            "updated_at": now_iso(),
        }
        if not within_design:
            envelope.state_proposal["status"] = {"validation": "failed"}
        return envelope
