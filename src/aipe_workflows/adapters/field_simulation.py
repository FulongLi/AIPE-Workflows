"""AIPE-Field-Simulation adapters: executed Gmsh + Elmer models.

``TransformerLeakageFemTask`` solves the 2-D E-core window magnetostatics with
the turns of the selected magnetics candidate at the executed peak primary
current and compares the FEM leakage and magnetising inductances with the
analytical magnetics estimates (feedback example C). ``HeatSinkFemTask``
solves the 3-D finned heat sink of the Stage A knee candidate (or the package
default geometry) with two selected devices at their evaluated losses and the
candidate's correlation film coefficient (Stage B verification of the
screening). Both run two mesh levels and record the convergence change. Mesh
and solver files stay in the task directory with hashes.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from ..engine.envelope import ExecutionEnvelope, now_iso
from ..engine.runner import TaskAdapter, TaskContext
from .common import run_suffix


def _requirements(environment: dict[str, Any]) -> list[str]:
    problems = []
    try:
        import aipe_fieldsim  # noqa: F401
    except ImportError:
        problems.append("python package aipe_fieldsim (AIPE-Field-Simulation) is not installed: pip install -e ../AIPE-Field-Simulation")
    for tool in ("gmsh", "elmer"):
        info = environment.get("tools", {}).get(tool, {})
        if not info.get("found"):
            problems.append(f"{tool} not found")
    return problems


def _value(results: dict, key: str) -> Optional[float]:
    v = results.get(key)
    if isinstance(v, dict):
        v = v.get("value")
    return float(v) if isinstance(v, (int, float)) else None


def _tool_version(ctx: TaskContext, name: str) -> str:
    return str(ctx.environment.get("tools", {}).get(name, {}).get("version") or "unknown")


def _export_elmer_path(ctx: TaskContext) -> None:
    """Make aipe_fieldsim use the ElmerSolver the doctor found and qualified.

    aipe_fieldsim discovers Elmer on its own (AIPE_ELMERSOLVER, ELMER_HOME, PATH, <workspace>/tools/ElmerFEM*); it does
    not know the doctor's AIPE_TOOLS_DIR lookup or per-user locations, so the qualified path is exported for this process.
    An explicitly set AIPE_ELMERSOLVER is left untouched."""
    import os

    info = ctx.environment.get("tools", {}).get("elmer", {})
    path = info.get("path") if info.get("found") else None
    if path and not os.environ.get("AIPE_ELMERSOLVER"):
        os.environ["AIPE_ELMERSOLVER"] = str(path)


def _collect_case_files(ctx: TaskContext, envelope: ExecutionEnvelope, workdir, names=("case.sif", "elmersolver.log", "results.json", "case.json"), max_each=2):
    for name in names:
        for path in sorted(workdir.rglob(name))[:max_each]:
            envelope.artifacts.append(ctx.artifacts.add(path, "fem_case_file", f"{path.parent.name}/{name}", ctx.task.id))
    for fig in sorted(workdir.rglob("*.png"))[:6]:
        envelope.artifacts.append(ctx.artifacts.add(fig, "figure", f"FEM plot {fig.stem}", ctx.task.id))


def _run_entry(envelope: ExecutionEnvelope, run_id: str, started: str, evidence_id: str) -> dict:
    return {"id": run_id, "status": "completed", "tool": dict(envelope.tool),
            "model": next(a.to_core() for a in envelope.artifacts if a.role == "fem_summary"),
            "outputs": [a.to_core() for a in envelope.artifacts if a.role in ("fem_case_file", "fem_summary")],
            "started_at": started, "completed_at": now_iso(), "evidence_refs": [evidence_id]}


def _parse_strand_diameter(conductor: str) -> Optional[float]:
    """'litz 436 x 0.1 mm' -> 1e-4 m."""
    import re
    m = re.search(r"x\s*([0-9.]+)\s*mm", str(conductor))
    return float(m.group(1)) * 1e-3 if m else None


def load_core_dimensions(core_id: str) -> tuple[dict[str, float], str]:
    """Catalogue core record (AIPE-Magnetics-Database) -> outline dimensions in metres and the record name."""
    from aipe_magnetics.data.catalog import Catalog
    record = Catalog.default().get(core_id)
    dims = {k: float(v["value"]) for k, v in record.properties["dimensions"]["values"].items()}
    return dims, str(getattr(record, "name", core_id))


def window_params_from_magnetics(mag: dict) -> tuple[dict[str, Any], list[str]]:
    """Map the selected catalogue core and the candidate's parametric layout onto the FEM window model parameters.

    Returns (params, notes); params is empty when the record cannot be loaded (the model then keeps its defaults).
    """
    notes: list[str] = []
    params: dict[str, Any] = {}
    candidate = mag.get("selected_candidate") or {}
    core_id = candidate.get("core") or mag.get("selected_core")
    if not core_id:
        return params, ["no core id in the magnetics result; FEM uses the package default window"]
    try:
        dims, core_name = load_core_dimensions(core_id)
    except Exception as exc:  # noqa: BLE001 - any catalogue problem falls back to the default geometry
        return params, [f"core record {core_id} not loadable ({exc}); FEM uses the package default window"]
    wc = dims["centre_leg_width"]
    window_width = (dims["window_width_total"] - wc) / 2
    window_height = 2 * dims["window_height_half"]
    params.update({"centre_leg_width_m": wc, "window_width_m": window_width, "window_height_m": window_height,
                   "outer_leg_width_m": (dims["length_a"] - dims["window_width_total"]) / 2,
                   "yoke_thickness_m": dims["height_b_half"] - dims["window_height_half"], "core_depth_m": dims["depth_c"]})
    notes.append(f"core window from catalogue record {core_id} ({core_name}): centre leg {wc * 1e3:.1f} mm, window "
                 f"{window_width * 1e3:.1f} x {window_height * 1e3:.1f} mm, depth {dims['depth_c'] * 1e3:.1f} mm")
    layout = candidate.get("layout") or {}
    layers = layout.get("layers") or []
    pri = [l for l in layers if l.get("winding") == "primary"]
    sec = [l for l in layers if l.get("winding") == "secondary"]
    if pri and sec:
        params["primary_width_m"] = sum(l["d_out_m"] - l["d_in_m"] for l in pri)
        params["secondary_width_m"] = sum(l["d_out_m"] - l["d_in_m"] for l in sec)
        ordered = sorted(layers, key=lambda l: l["d_in_m"])
        gaps = [b["d_in_m"] - a["d_out_m"] for a, b in zip(ordered, ordered[1:])]
        params["insulation_gap_m"] = max(min(gaps), 1e-4) if gaps else 1.5e-3
        params["clearance_centre_m"] = ordered[0]["d_in_m"]
        if layout.get("winding_height_m"):
            params["winding_margin_m"] = max((window_height - float(layout["winding_height_m"])) / 2, 0.0)
        windings = candidate.get("windings") or {}
        copper = 0.0
        for l in layers:
            area = float((windings.get(l.get("winding")) or {}).get("copper_area_m2") or 0.0)
            copper += area * float(l["turns"])
        block_area = sum((l["d_out_m"] - l["d_in_m"]) for l in layers) * float(layout.get("winding_height_m") or window_height)
        if copper > 0 and block_area > 0:
            params["fill_factor"] = min(max(copper / block_area, 0.05), 0.9)
        d_strand = _parse_strand_diameter((windings.get("primary") or {}).get("conductor", ""))
        if d_strand:
            params["strand_diameter_m"] = d_strand
        notes.append(f"winding blocks from the magnetics parametric layout: primary build {params['primary_width_m'] * 1e3:.2f} mm in {len(pri)} section(s), "
                     f"secondary build {params['secondary_width_m'] * 1e3:.2f} mm, section gap {params['insulation_gap_m'] * 1e3:.2f} mm, "
                     f"bobbin/clearance {params['clearance_centre_m'] * 1e3:.2f} mm, axial margin {params.get('winding_margin_m', 0) * 1e3:.2f} mm, "
                     f"copper fill {params.get('fill_factor', 0):.2f}")
    return params, notes


class TransformerLeakageFemTask(TaskAdapter):
    id = "aipe.field-simulation.transformer-window-2d"
    version = "0.1.1"

    def requirements(self, environment: dict[str, Any]) -> list[str]:
        return _requirements(environment)

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:
        import aipe_fieldsim
        from aipe_fieldsim.models.transformer_window import TransformerWindowModel

        started = now_iso()
        p = ctx.task.parameters
        mag = ctx.inputs["magnetics"]
        req = ctx.inputs["requirements"]
        sim = ctx.inputs.get("simulation", {})
        n1, n2 = int(mag.get("turns_primary") or 20), int(mag.get("turns_secondary") or 10)
        arrangement = str((mag.get("selected_candidate") or {}).get("arrangement", ""))
        i1 = float(sim.get("i_L_peak_A") or 14.3)
        params = {"N1": n1, "N2": n2, "I1_A": i1, "frequency_Hz": float(req["switching_frequency_Hz"]),
                  "interleaved": bool(p.get("interleaved", "P-S-P" in arrangement))}
        geometry_notes: list[str] = []
        if p.get("geometry_from_magnetics", True):
            mapped, geometry_notes = window_params_from_magnetics(mag)
            params.update(mapped)
        params.update(p.get("geometry") or {})
        geometry_source = geometry_notes[0] if (geometry_notes and "catalogue record" in geometry_notes[0]) else "aipe_fieldsim package default E-core window"
        workdir = ctx.task_dir / "fem"
        _export_elmer_path(ctx)
        model = TransformerWindowModel(workdir, params=params, plots=bool(p.get("figures", True)))
        summary = model.run(harmonic=bool(p.get("harmonic", False)), levels=tuple(p.get("levels", (0, 1))))
        envelope = ExecutionEnvelope(task_id=ctx.task.id, task_version=self.version, capability_id="aipe.field-simulation",
                                     tool={"id": "tool.elmer", "version": _tool_version(ctx, "elmer"), "name": "Elmer FEM (ElmerGrid/ElmerSolver) with Gmsh meshing"},
                                     status="completed", started_at=started, finished_at=now_iso(), source_state_id=ctx.state.get("id", ""),
                                     source_state_sha256=ctx.state_sha256, inputs={"params": params, "geometry_source": geometry_source, "geometry_notes": geometry_notes},
                                     model={"id": "fieldsim-transformer-window-2d", "version": str(getattr(aipe_fieldsim, "__version__", "unknown")),
                                            "validity_range": "2-D planar window magnetostatics with homogenised winding blocks on the selected core's window and the "
                                                              "magnetics parametric layout (package default window when the record is unavailable); no 3-D end effects, "
                                                              "no core loss; proximity factor is a strand-level estimate"},
                                     environment={"gmsh": _tool_version(ctx, "gmsh"), "elmer": _tool_version(ctx, "elmer")},
                                     evidence_kind="simulation", gate="field_simulation")
        summary_path = workdir / "summary.json"
        if not summary_path.is_file():
            summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        envelope.artifacts.append(ctx.artifacts.add(summary_path, "fem_summary", "transformer window FEM summary (levels, results, checks, limitations)", ctx.task.id))
        _collect_case_files(ctx, envelope, workdir, names=("case.sif", "mesh.msh", "elmersolver.log", "results.json", "case.json"))
        if summary.get("status") not in ("ok", "completed", "passed", "executed"):
            envelope.status = "failed"
            envelope.add_error("fem-status", f"model status {summary.get('status')}: {summary.get('status_note', '')}")
            return envelope
        results = summary.get("results", {})
        l_leak_fem = _value(results, "L_leakage_primary_H")
        l_leak_1d = _value(results, "L_leakage_primary_1d_estimate_H")
        l_m_fem = _value(results, "L_magnetising_primary_H")
        l_leak_mag = float(mag.get("leakage_inductance_H") or 0.0)
        conv = summary.get("leakage_convergence") or []
        levels = summary.get("leakage_levels") or []
        checks = summary.get("checks") or []
        checks_passed = all(c.get("passed", True) for c in checks)
        envelope.outputs = {
            "L_leakage_primary_H_fem": l_leak_fem, "L_leakage_primary_H_1d_estimate": l_leak_1d, "L_magnetising_primary_H_fem": l_m_fem,
            "L_magnetising_primary_H_reluctance_estimate": _value(results, "L_magnetising_reluctance_estimate_H"),
            "L_leakage_primary_H_magnetics_design": l_leak_mag,
            "leakage_fem_vs_magnetics_relative": ((l_leak_fem - l_leak_mag) / l_leak_mag) if (l_leak_fem and l_leak_mag) else None,
            "leakage_fem_vs_1d_relative": ((l_leak_fem - l_leak_1d) / l_leak_1d) if (l_leak_fem and l_leak_1d) else None,
            "max_B_window_T": _value(results, "max_B_window_T"), "F_R_litz_proximity_estimate": _value(results, "F_R_litz_proximity_estimate"),
            "turns": [n1, n2], "interleaved": params["interleaved"], "I1_A": i1,
            "convergence": conv, "mesh_levels": [{k: r.get(k) for k in ("level", "h", "elements", "nodes", "L_leakage_H")} for r in levels],
            "checks": checks, "limitations": summary.get("limitations"), "summary_path": str(summary_path),
            "geometry_source": geometry_source, "geometry_notes": geometry_notes,
            "window_geometry": {k: params.get(k) for k in ("centre_leg_width_m", "window_width_m", "window_height_m", "core_depth_m", "primary_width_m",
                                                            "secondary_width_m", "insulation_gap_m", "clearance_centre_m", "winding_margin_m", "fill_factor",
                                                            "strand_diameter_m")},
            "geometry_note": geometry_source + "; homogenised rectangular winding blocks (no individual turns); 2-D planar approximation of the E-core window",
        }
        conv_change = None
        if len(conv) >= 2 and isinstance(conv[-1], dict):
            conv_change = conv[-1].get("rel_change_vs_previous") or conv[-1].get("relative_change") or conv[-1].get("change_vs_finest")
        envelope.verification = {"status": summary.get("status"), "checks_passed": checks_passed, "mesh_levels": len(levels),
                                 "finest_level_relative_change": conv_change,
                                 "leakage_fem_vs_magnetics_relative": envelope.outputs["leakage_fem_vs_magnetics_relative"]}
        suffix = run_suffix(ctx.run_id)
        evidence_id = f"evidence.fem-transformer-window-{suffix}"
        evidence = {
            "id": evidence_id, "kind": "simulation",
            "description": (f"Executed Elmer 2-D window magnetostatics for {n1}:{n2} turns ({'interleaved' if params['interleaved'] else 'non-interleaved'}) at I1 = {i1:.2f} A: "
                            f"L_leak = {l_leak_fem} H (1-D estimate on the same layout {l_leak_1d} H; magnetics-database 1-D design value {l_leak_mag} H), "
                            f"L_m = {l_m_fem} H; {len(levels)} mesh levels; geometry: {geometry_source}."),
            "source": {"type": "repository", "reference": "https://github.com/FulongLi/AIPE-Field-Simulation", "locator": "src/aipe_fieldsim/models/transformer_window.py"},
            "provenance": {"created_at": started, "activity": "Mesh the window with Gmsh, solve MgDyn2D with Elmer at two refinement levels, extract energies and inductances, run energy/ampere-turn checks.",
                           "tool": dict(envelope.tool), "agent": {"id": "aipe.workflows", "version": "0.1.0"},
                           "inputs": [e for e in ["evidence.specification", mag.get("evidence_id"), sim.get("evidence_id")] if e]},
            "artifacts": [a.to_core() for a in envelope.artifacts], "review_status": "unreviewed",
        }
        envelope.state_proposal = {
            "evidence": [evidence],
            "append": [{"path": "simulation.runs", "value": _run_entry(envelope, f"run.fem-transformer-window-{suffix}", started, evidence_id)},
                       {"path": "validation.checks", "value": {"id": f"check.fem-transformer-window-{suffix}", "kind": "simulation",
                                                               "status": "pass" if checks_passed else "fail",
                                                               "description": "2-D window FEM executed at two mesh levels with energy and ampere-turn consistency checks; leakage compared with the analytical magnetics design.",
                                                               "evidence_refs": [evidence_id]}}],
            "extensions": {"aipe.workflows.dab": {"fem_transformer_window": {k: v for k, v in envelope.outputs.items() if k not in ("checks", "limitations", "mesh_levels")}}},
            "updated_at": now_iso(),
        }
        return envelope


class HeatSinkFemTask(TaskAdapter):
    id = "aipe.field-simulation.heatsink-3d"
    version = "0.1.0"

    def requirements(self, environment: dict[str, Any]) -> list[str]:
        return _requirements(environment)

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:
        import aipe_fieldsim
        from aipe_fieldsim.models.heatsink import HeatSinkModel

        started = now_iso()
        p = ctx.task.parameters
        semis = ctx.inputs.get("semiconductors") or {}
        thermal = ctx.inputs.get("thermal") or {}
        env_spec = ctx.inputs.get("environment_spec") or {}
        candidate = thermal.get("fem_candidate_geometry") or {}
        worst = thermal.get("worst_bridge") or "secondary"
        device_power = float(p.get("device_power_W") or semis.get(f"{worst}_loss_W") or semis.get("secondary_loss_W") or 20.0)
        if p.get("T_ambient_K") is not None:
            t_amb = float(p["T_ambient_K"])
        elif isinstance(thermal.get("t_ambient_C"), (int, float)):
            t_amb = float(thermal["t_ambient_C"]) + 273.15
        else:
            t_amb = float(env_spec.get("ambient_temperature_K", 313.15))
        params: dict[str, Any] = {"device_power_W": device_power, "T_ambient_K": t_amb}
        geometry_source = "aipe_fieldsim package default plate-fin sink"
        if candidate:
            for key in ("base_length_m", "base_width_m", "base_thickness_m", "fin_count", "fin_thickness_m", "fin_height_m", "k_W_per_m_K", "density_kg_per_m3"):
                if candidate.get(key) is not None:
                    params[key] = candidate[key]
            if isinstance(candidate.get("h_W_per_m2_K"), (int, float)):
                params["h_W_per_m2_K"] = float(candidate["h_W_per_m2_K"])
            geometry_source = f"Stage A knee candidate {candidate.get('candidate_id')} ({candidate.get('material')}, {candidate.get('cooling')} cooling)"
        if p.get("h_W_per_m2_K") is not None:
            params["h_W_per_m2_K"] = float(p["h_W_per_m2_K"])
        params.update(p.get("geometry") or {})
        workdir = ctx.task_dir / "fem"
        _export_elmer_path(ctx)
        model = HeatSinkModel(workdir, params=params, plots=bool(p.get("figures", True)))
        summary = model.run(levels=tuple(p.get("levels", (0, 1))))
        envelope = ExecutionEnvelope(task_id=ctx.task.id, task_version=self.version, capability_id="aipe.field-simulation",
                                     tool={"id": "tool.elmer", "version": _tool_version(ctx, "elmer"), "name": "Elmer FEM (ElmerGrid/ElmerSolver) with Gmsh meshing"},
                                     status="completed", started_at=started, finished_at=now_iso(), source_state_id=ctx.state.get("id", ""),
                                     source_state_sha256=ctx.state_sha256, inputs={"params": dict(model.params), "geometry_source": geometry_source},
                                     model={"id": "fieldsim-heatsink-3d-conduction", "version": str(getattr(aipe_fieldsim, "__version__", "unknown")),
                                            "validity_range": "3-D steady conduction in a plate-fin sink with a uniform convective film coefficient supplied as input (from the Stage A correlation); "
                                                              "no CFD, no TIM, no package spreading; two footprints only"},
                                     environment={"gmsh": _tool_version(ctx, "gmsh"), "elmer": _tool_version(ctx, "elmer")},
                                     evidence_kind="simulation", gate="field_simulation")
        summary_path = workdir / "summary.json"
        if not summary_path.is_file():
            summary_path.write_text(json.dumps(summary, indent=2, default=str), encoding="utf-8")
        envelope.artifacts.append(ctx.artifacts.add(summary_path, "fem_summary", "heat sink FEM summary (levels, results, checks, limitations)", ctx.task.id))
        _collect_case_files(ctx, envelope, workdir)
        if summary.get("status") not in ("ok", "completed", "passed", "executed"):
            envelope.status = "failed"
            envelope.add_error("fem-status", f"model status {summary.get('status')}: {summary.get('status_note', '')}")
            return envelope
        results = summary.get("results", {})
        t_max = _value(results, "T_max_K")
        r_fem = _value(results, "R_th_hotspot_K_per_W")
        r_analytical = candidate.get("r_th_analytical_hotspot_K_per_W") if isinstance(candidate.get("r_th_analytical_hotspot_K_per_W"), (int, float)) else None
        q_conv = _value(results, "Q_convective_W")
        balance_ok = q_conv is not None and abs(q_conv - 2 * device_power) / (2 * device_power) < 1e-3
        checks = summary.get("checks") or []
        checks_passed = all(c.get("passed", True) for c in checks)
        envelope.outputs = {
            "device_power_W": device_power, "h_W_per_m2_K": float(model.params["h_W_per_m2_K"]), "T_ambient_K": t_amb, "T_max_K": t_max,
            "T_rise_hotspot_K": _value(results, "T_rise_hotspot_K"), "R_th_hotspot_K_per_W": r_fem, "R_th_footprint_mean_K_per_W": _value(results, "R_th_footprint_mean_K_per_W"),
            "Q_convective_W": q_conv, "convective_area_m2": _value(results, "convective_area_m2"),
            "R_th_analytical_candidate_K_per_W": r_analytical,
            "R_th_fem_vs_analytical_relative": ((r_fem - r_analytical) / r_analytical) if (r_fem is not None and r_analytical) else None,
            "geometry": {k: model.params.get(k) for k in ("base_length_m", "base_width_m", "base_thickness_m", "fin_count", "fin_thickness_m", "fin_height_m", "k_W_per_m_K")},
            "geometry_source": geometry_source, "candidate_id": candidate.get("candidate_id"),
            "convergence": summary.get("convergence_T_max"), "mesh_levels": [{k: r.get(k) for k in ("level", "h", "elements", "nodes", "T_max_K")} for r in (summary.get("levels") or [])],
            "checks": checks, "limitations": summary.get("limitations"), "summary_path": str(summary_path),
            "geometry_note": f"{geometry_source}; two TO-247 footprints at the model's fixed positions; film coefficient is the Stage A correlation value, not a CFD result",
        }
        envelope.verification = {"status": summary.get("status"), "energy_balance_ok": balance_ok, "checks_passed": checks_passed,
                                 "convergence": summary.get("convergence_T_max"), "R_th_fem_vs_analytical_relative": envelope.outputs["R_th_fem_vs_analytical_relative"]}
        suffix = run_suffix(ctx.run_id)
        evidence_id = f"evidence.fem-heatsink-{suffix}"
        evidence = {
            "id": evidence_id, "kind": "simulation",
            "description": (f"Executed Elmer 3-D heat-sink conduction of {geometry_source} with two {device_power:.2f} W TO-247 sources, h = {model.params['h_W_per_m2_K']} W/m^2/K, "
                            f"ambient {t_amb:.1f} K: T_max = {t_max} K, R_th(hotspot) = {r_fem} K/W versus analytical candidate {r_analytical} K/W; "
                            f"film coefficient is an input from the correlation, not a CFD result."),
            "source": {"type": "repository", "reference": "https://github.com/FulongLi/AIPE-Field-Simulation", "locator": "src/aipe_fieldsim/models/heatsink.py"},
            "provenance": {"created_at": started, "activity": "Mesh the finned sink with Gmsh, solve steady conduction with convective boundaries in Elmer at two refinement levels, check the energy balance, compare with the Stage A correlation.",
                           "tool": dict(envelope.tool), "agent": {"id": "aipe.workflows", "version": "0.1.0"},
                           "inputs": [e for e in ["evidence.specification", semis.get("evidence_id"), thermal.get("evidence_id")] if e]},
            "artifacts": [a.to_core() for a in envelope.artifacts], "review_status": "unreviewed",
        }
        existing_thermal = dict(ctx.state.get("thermal") or {})
        proposal: dict[str, Any] = {
            "evidence": [evidence],
            "append": [{"path": "simulation.runs", "value": _run_entry(envelope, f"run.fem-heatsink-{suffix}", started, evidence_id)},
                       {"path": "validation.checks", "value": {"id": f"check.fem-heatsink-{suffix}", "kind": "simulation",
                                                               "status": "pass" if (balance_ok and checks_passed) else "fail",
                                                               "description": "3-D heat-sink conduction executed at two mesh levels; convective heat equals the injected device losses; hotspot resistance compared with the Stage A correlation.",
                                                               "evidence_refs": [evidence_id]}}],
            "extensions": {"aipe.workflows.dab": {"fem_heatsink": {k: v for k, v in envelope.outputs.items() if k not in ("checks", "limitations", "mesh_levels")}}},
            "updated_at": now_iso(),
        }
        if existing_thermal:
            existing_thermal["evidence_refs"] = sorted(set(existing_thermal.get("evidence_refs", [])) | {evidence_id})
            proposal["set"] = [{"path": "thermal", "value": existing_thermal}]
        envelope.state_proposal = proposal
        return envelope
