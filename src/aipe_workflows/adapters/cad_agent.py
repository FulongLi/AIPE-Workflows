"""AIPE-CAD-Agent adapters: parametric FreeCAD geometry generated from the Engineering State.

``TransformerCadTask`` builds the selected magnetics candidate (catalogue core
outline, the parametric winding layout as concentric litz windings in the same
radial order, barriers, pins, clips, base plate) and ``HeatSinkCadTask`` builds
the Stage A knee heat-sink candidate with two selected TO-247 devices. Both call
the ``aipe-cad build`` command line (FreeCAD console mode) and record the STEP /
FCStd / metadata / check-report artefacts plus the geometric check summary.
Required clearance/creepage values are caller inputs labelled illustrative; no
standard compliance, DFM, thermal or electromagnetic claim is made.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from ..engine.envelope import ExecutionEnvelope, now_iso
from ..engine.runner import TaskAdapter, TaskContext
from .design_agent import run_suffix
from .field_simulation import load_core_dimensions

ILLUSTRATIVE_NOTE = "illustrative caller-supplied value; not a standard assertion"


def _requirements(environment: dict[str, Any]) -> list[str]:
    problems = []
    try:
        import aipe_cad  # noqa: F401
    except ImportError:
        problems.append("python package aipe_cad (AIPE-CAD-Agent) is not installed: pip install -e ../AIPE-CAD-Agent")
    if not environment.get("tools", {}).get("freecad", {}).get("found"):
        problems.append("freecad (freecadcmd) not found")
    return problems


def _cad_cli() -> list[str]:
    exe = shutil.which("aipe-cad")
    return [exe] if exe else [sys.executable, "-m", "aipe_cad.cli"]


def _run_build(kind: str, params_path: Path, out_dir: Path, name: str, timeout: float, log_path: Path) -> tuple[int, str]:
    cmd = [*_cad_cli(), "build", kind, str(params_path), "--out-dir", str(out_dir), "--name", name, "--timeout", str(timeout)]
    completed = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 60, check=False, errors="replace")
    log_path.write_text(" ".join(cmd) + "\n\n" + completed.stdout + "\n" + completed.stderr, encoding="utf-8")
    return completed.returncode, completed.stdout + completed.stderr


def _collect(ctx: TaskContext, envelope: ExecutionEnvelope, out_dir: Path, name: str) -> dict[str, Any]:
    files = {"fcstd": out_dir / f"{name}.FCStd", "step": out_dir / f"{name}.step", "step_keepouts": out_dir / f"{name}.keepouts.step",
             "metadata": out_dir / f"{name}.metadata.json", "checks": out_dir / f"{name}.checks.json", "render": out_dir / "renders" / f"{name}.png"}
    roles = {"fcstd": "cad_fcstd", "step": "cad_step", "step_keepouts": "cad_step", "metadata": "cad_metadata", "checks": "cad_check_report", "render": "figure"}
    for key, path in files.items():
        if path.is_file():
            envelope.artifacts.append(ctx.artifacts.add(path, roles[key], f"{name} {key}", ctx.task.id))
    metadata = json.loads(files["metadata"].read_text(encoding="utf-8")) if files["metadata"].is_file() else {}
    checks = json.loads(files["checks"].read_text(encoding="utf-8")) if files["checks"].is_file() else {}
    return {"metadata": metadata, "checks": checks, "paths": {k: str(v) for k, v in files.items() if v.is_file()}}


def _check_status(checks: dict) -> tuple[str, bool]:
    summary = checks.get("summary") or {}
    pairs = summary.get("clearance_pairs") or {}
    hard_fail = (summary.get("interference_count") or 0) > 0 or (summary.get("fit_failures") or 0) > 0 or (pairs.get("fail") or 0) > 0 \
        or (summary.get("keepout_violation_count") or 0) > 0
    return str(summary.get("status", "unknown")), not hard_fail


def _parse_litz(conductor: str) -> tuple[Optional[int], Optional[float]]:
    m = re.search(r"litz\s*(\d+)\s*x\s*([0-9.]+)\s*mm", str(conductor))
    return (int(m.group(1)), float(m.group(2)) * 1e-3) if m else (None, None)


class TransformerCadTask(TaskAdapter):
    id = "aipe.cad-agent.transformer"
    version = "0.1.0"

    def requirements(self, environment: dict[str, Any]) -> list[str]:
        return _requirements(environment)

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:
        import aipe_cad

        started = now_iso()
        p = ctx.task.parameters
        mag = ctx.inputs["magnetics"]
        candidate = mag.get("selected_candidate") or {}
        core_id = candidate.get("core") or mag.get("selected_core")
        envelope = ExecutionEnvelope(task_id=ctx.task.id, task_version=self.version, capability_id="aipe.cad-agent",
                                     tool={"id": "tool.freecad", "version": str(ctx.environment.get("tools", {}).get("freecad", {}).get("version") or "unknown"), "name": "FreeCAD (console) via aipe-cad"},
                                     status="completed", started_at=started, finished_at=now_iso(), source_state_id=ctx.state.get("id", ""),
                                     source_state_sha256=ctx.state_sha256, inputs={"core": core_id},
                                     model={"id": "aipe-cad-parametric-transformer", "version": str(getattr(aipe_cad, "__version__", "unknown")),
                                            "validity_range": "illustrative parametric geometry: homogenised concentric windings, plain pin terminals, no DFM, thermal or EM claim; "
                                                              "clearance checks use straight/one-bend air paths with caller-supplied required values"},
                                     evidence_kind="analytical", gate="cad_pcb")
        try:
            dims, core_name = load_core_dimensions(core_id)
        except Exception as exc:  # noqa: BLE001
            envelope.status = "failed"
            envelope.add_error("core-record", f"cannot load core record {core_id}: {exc}")
            return envelope
        layout = candidate.get("layout") or {}
        layers = sorted(layout.get("layers") or [], key=lambda l: l["d_in_m"])
        windings_info = candidate.get("windings") or {}
        if not layers:
            envelope.status = "failed"
            envelope.add_error("layout", "magnetics candidate has no parametric layout layers")
            return envelope
        window_height = 2 * dims["window_height_half"]
        # The CAD bobbin flanges and window clearance already consume part of the window height; the remaining axial margin
        # is what keeps the magnetics layout's turns-per-layer (the magnetics layout reserves 1.7 mm per side for the former).
        flange, window_clearance = float(p.get("flange_thickness_m", 0.0015)), float(p.get("window_clearance_m", 0.0005))
        winding_height = float(layout.get("winding_height_m") or window_height)
        margin = max((window_height - 2 * window_clearance - 2 * flange - winding_height) / 2, 0.0)
        gaps = [b["d_in_m"] - a["d_out_m"] for a, b in zip(layers, layers[1:])]
        barrier = max(min(gaps), 1e-4) if gaps else 0.0005
        core_clearance = float(p.get("core_clearance_m", 0.0003))
        wall = max(float(layers[0]["d_in_m"]) - core_clearance, 0.0008)
        windings = []
        seen_nets: set[str] = set()
        for l in layers:
            w = l["winding"]
            count, d_strand = _parse_litz((windings_info.get(w) or {}).get("conductor", ""))
            od = float(l["d_out_m"] - l["d_in_m"])
            conductor: dict[str, Any] = {"type": "litz", "outer_diameter": od, "insulation_thickness": float(p.get("strand_insulation_m", 5e-5)),
                                         "fill_factor": float(p.get("litz_fill_factor", 0.4))}
            if count and d_strand:
                conductor.update({"strand_count": count, "strand_diameter": d_strand})
            # Interleaved sections of one winding are connected in series inside the former; only the first section carries
            # the two external pins (a second pair on the same flange side would occupy the same positions).
            windings.append({"name": f"{w}-{l['section']}", "turns": int(l["turns"]), "net": w, "margin": margin,
                             "terminal_count": 0 if w in seen_nets else 2, "terminal_side": "-y" if w == "primary" else "+y", "conductor": conductor})
            seen_nets.add(w)
        reference = f"AIPE-Magnetics-Database catalogue record {core_id} ({core_name}); outline letters A/B/C/D/E/F from the record's datasheet transcription"
        params = {
            "kind": "transformer", "name": p.get("name", "dab_transformer"),
            "description": (f"DAB transformer from the workflow Engineering State: {core_name} core set, {candidate.get('turns')} turns, "
                            f"{candidate.get('arrangement')} arrangement from the magnetics design; illustrative parametric model, not a manufacturable design."),
            "core": {"shape": "E", "total_width": dims["length_a"], "half_height": dims["height_b_half"], "depth": dims["depth_c"],
                     "window_height": dims["window_height_half"], "inner_width": dims["window_width_total"], "centre_leg_width": dims["centre_leg_width"],
                     "air_gap": 0.0, "material": "ferrite_n87", "net": "pe", "reference": reference},
            "bobbin": {"wall_thickness": wall, "flange_thickness": flange, "core_clearance": core_clearance, "window_clearance": window_clearance,
                       "pin_strip_width": 0.006, "corner_radius": 0.001, "material": "bobbin_pet_gf"},
            "windings": windings,
            "insulation": {"inter_winding_barrier": barrier, "outer_wrap": 0.0003, "fill_margins": True, "material": "kapton"},
            "terminals": {"style": "pin", "diameter": 0.0015, "length": 0.012, "pitch": 0.005, "flange": "top", "direction": "+z", "material": "brass"},
            "mounting": {"clips": True, "clip_thickness": 0.0008, "clip_width": 0.010, "clip_inset": 0.002, "clip_material": "stainless_steel",
                         "base_plate": True, "plate_thickness": 0.002, "plate_margin_x": 0.012, "hole_diameter": 0.0045, "hole_inset": 0.006,
                         "plate_material": "aluminium_6063", "net": "pe"},
            "clearance_envelope_margin": 0.005,
            "checks": {"interference": {"enabled": True, "min_overlap_volume": 1e-12},
                       "clearance_pairs": p.get("clearance_pairs") or [
                           {"net_a": "primary", "net_b": "secondary", "required_clearance": 0.0055, "required_creepage": 0.008, "note": ILLUSTRATIVE_NOTE + " (800 V primary to 400 V secondary)"},
                           {"net_a": "primary", "net_b": "pe", "required_clearance": 0.002, "required_creepage": 0.004, "note": ILLUSTRATIVE_NOTE + " (functional insulation to earthed parts)"},
                           {"net_a": "secondary", "net_b": "pe", "required_clearance": 0.002, "required_creepage": 0.004, "note": ILLUSTRATIVE_NOTE}]},
        }
        out_dir = ctx.task_dir / "cad"
        out_dir.mkdir(parents=True, exist_ok=True)
        params_path = out_dir / "transformer.params.json"
        params_path.write_text(json.dumps(params, indent=2), encoding="utf-8")
        envelope.inputs["params_path"] = str(params_path)
        envelope.artifacts.append(ctx.artifacts.add(params_path, "cad_parameters", "transformer CAD parameters derived from the Engineering State", ctx.task.id))
        code, output = _run_build("transformer", params_path.resolve(), out_dir.resolve(), params["name"], float(p.get("timeout_s", 900)), ctx.task_dir / "aipe-cad.log")
        if code != 0:
            envelope.status = "failed"
            envelope.add_error("aipe-cad", output[-1200:])
            return envelope
        got = _collect(ctx, envelope, out_dir, params["name"])
        totals = (got["metadata"].get("totals") or {})
        status, no_hard_fail = _check_status(got["checks"])
        if not no_hard_fail:
            envelope.status = "failed"
            envelope.add_error("geometry-check", "interference/fit/keep-out or clearance failure: " + json.dumps(got["checks"].get("summary"))[:600]
                               + " interference=" + json.dumps(got["checks"].get("interference"))[:600])
            return envelope
        clearance_rows = [{k: r.get(k) for k in ("net_a", "net_b", "required_clearance_m", "required_creepage_m", "status", "message")} for r in (got["checks"].get("clearance") or [])]
        analytic = got["metadata"].get("analytic") or {}
        envelope.outputs = {
            "core": core_id, "core_name": core_name, "windings": [{k: w[k] for k in ("name", "turns", "net")} | {"outer_diameter_m": w["conductor"]["outer_diameter"]} for w in windings],
            "barrier_m": barrier, "margin_m": margin, "bbox_m": totals.get("bbox_m"), "size_m": totals.get("size_m"), "volume_m3": totals.get("volume_m3"),
            "mass_kg": totals.get("mass_kg"), "mass_by_material_kg": totals.get("mass_by_material_kg"), "body_count": totals.get("body_count"),
            "magnetics_mass_kg": candidate.get("mass_kg"), "magnetics_copper_mass_kg": candidate.get("copper_mass_kg"),
            "check_status": status, "check_summary": got["checks"].get("summary"), "clearance": clearance_rows,
            "step_reimport": {k: v for k, v in (got["metadata"].get("step_reimport") or {}).items() if not isinstance(v, (list, dict))},
            "analytic_vs_cad": analytic, "files": got["paths"], "warnings": got["metadata"].get("warnings"),
            "limitations": ["homogenised concentric windings in the radial order of the magnetics layout (interleave represented as separate winding bodies)",
                            "required clearance/creepage values are illustrative inputs; creepage along surfaces and multi-bend paths are not traced (review status)",
                            "no DFM, thermal or electromagnetic claim"],
        }
        envelope.verification = {"build_ok": True, "check_status": status, "no_hard_failures": no_hard_fail,
                                 "interference_count": (got["checks"].get("summary") or {}).get("interference_count"),
                                 "clearance_pairs": (got["checks"].get("summary") or {}).get("clearance_pairs")}
        for w in got["metadata"].get("warnings") or []:
            envelope.add_warning("aipe-cad", str(w))
        suffix = run_suffix(ctx.run_id)
        evidence_id = f"evidence.cad-transformer-{suffix}"
        evidence = {
            "id": evidence_id, "kind": "analytical",
            "description": (f"Parametric FreeCAD transformer of the selected magnetics candidate ({core_name}, {candidate.get('turns')} turns, {candidate.get('arrangement')}): "
                            f"{totals.get('body_count')} bodies, {totals.get('mass_kg')} kg (magnetics estimate {candidate.get('mass_kg')} kg), geometric checks '{status}' "
                            f"(interference {(got['checks'].get('summary') or {}).get('interference_count')}, clearance pairs {(got['checks'].get('summary') or {}).get('clearance_pairs')}); "
                            "illustrative geometry, clearance requirements are caller inputs."),
            "source": {"type": "repository", "reference": "https://github.com/FulongLi/AIPE-CAD-Agent", "locator": "src/aipe_cad/freecad/build_transformer.py"},
            "provenance": {"created_at": started, "activity": "Derive CAD parameters from the magnetics candidate and catalogue core record; build FCStd/STEP in FreeCAD console mode; run interference, fit and clearance checks.",
                           "tool": dict(envelope.tool), "agent": {"id": "aipe.workflows", "version": "0.1.0"},
                           "inputs": [e for e in ["evidence.specification", mag.get("evidence_id")] if e]},
            "artifacts": [a.to_core() for a in envelope.artifacts], "review_status": "unreviewed",
        }
        envelope.state_proposal = {
            "evidence": [evidence],
            "append": [{"path": "validation.checks", "value": {"id": f"check.cad-transformer-{suffix}", "kind": "analytical", "status": "pass",
                                                               "description": f"Transformer CAD built from the Engineering State; no interference or fit failure; clearance pairs {(got['checks'].get('summary') or {}).get('clearance_pairs')} (review items need an insulation-system design).",
                                                               "evidence_refs": [evidence_id]}}],
            "extensions": {"aipe.workflows.dab": {"cad_transformer": {k: v for k, v in envelope.outputs.items() if k not in ("clearance", "files", "warnings", "limitations", "analytic_vs_cad")}}},
            "updated_at": now_iso(),
        }
        return envelope


class HeatSinkCadTask(TaskAdapter):
    id = "aipe.cad-agent.heatsink"
    version = "0.1.0"

    def requirements(self, environment: dict[str, Any]) -> list[str]:
        return _requirements(environment)

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:
        import aipe_cad

        started = now_iso()
        p = ctx.task.parameters
        thermal = ctx.inputs["thermal"]
        semis = ctx.inputs.get("semiconductors") or {}
        cand = thermal.get("fem_candidate_geometry") or {}
        worst = thermal.get("worst_bridge") or "secondary"
        envelope = ExecutionEnvelope(task_id=ctx.task.id, task_version=self.version, capability_id="aipe.cad-agent",
                                     tool={"id": "tool.freecad", "version": str(ctx.environment.get("tools", {}).get("freecad", {}).get("version") or "unknown"), "name": "FreeCAD (console) via aipe-cad"},
                                     status="completed", started_at=started, finished_at=now_iso(), source_state_id=ctx.state.get("id", ""),
                                     source_state_sha256=ctx.state_sha256, inputs={"candidate": cand.get("candidate_id"), "bridge": worst},
                                     model={"id": "aipe-cad-plate-fin-heatsink", "version": str(getattr(aipe_cad, "__version__", "unknown")),
                                            "validity_range": "illustrative parametric geometry of the Stage A candidate with two TO-247 devices on isolation pads; no DFM or thermal claim"},
                                     evidence_kind="analytical", gate="cad_pcb")
        if not cand:
            envelope.status = "failed"
            envelope.add_error("no-candidate", "thermal task provided no Stage A candidate geometry")
            return envelope
        length, width = float(cand["base_length_m"]), float(cand["base_width_m"])
        fin_t, fin_gap = float(cand["fin_thickness_m"]), float(cand.get("fin_gap_effective_m") or 0.004)
        pitch = fin_t + fin_gap
        count = int(cand.get("fin_count") or (int((width - fin_t) / pitch) + 1))
        part = semis.get(f"{worst}_part_number") or "TO-247"
        spacing = float(p.get("device_spacing_m", 0.024))
        devices = [{"name": f"Q{i + 1}", "package": "to247_4l", "position": [0.0, y], "rotation_deg": 0, "net": worst,
                    "pad": {"thickness": 0.00025, "oversize": 0.0025, "material": "alumina"}, "screw_hole_diameter": 0.0032,
                    "lead_form": {"horizontal": 0.003, "vertical": 0.014}} for i, y in enumerate((-spacing / 2, spacing / 2))]
        params = {
            "kind": "heatsink", "name": p.get("name", "dab_heatsink"),
            "description": (f"Plate-fin heat sink from the Stage A knee candidate {cand.get('candidate_id')} ({cand.get('material')}, {cand.get('cooling')} cooling) of the "
                            f"{worst} bridge with two {part} devices on alumina pads; illustrative model."),
            "base": {"length": length, "width": width, "thickness": float(cand["base_thickness_m"]), "material": "aluminium_6063" if "Al" in str(cand.get("material")) else "copper"},
            "fins": {"thickness": fin_t, "height": float(cand["fin_height_m"]), "pitch": pitch, "count": count, "length": length},
            "devices": devices,
            "mounting_holes": {"diameter": 0.0045, "inset": 0.005},
            "net": "pe", "clearance_envelope_margin": 0.003,
            "checks": {"interference": {"enabled": True, "min_overlap_volume": 1e-12},
                       "clearance_pairs": p.get("clearance_pairs") or [
                           {"net_a": worst, "net_b": "pe", "required_clearance": 0.002, "required_creepage": 0.004, "note": ILLUSTRATIVE_NOTE + " (device tabs/leads to the earthed sink)"}]},
        }
        out_dir = ctx.task_dir / "cad"
        out_dir.mkdir(parents=True, exist_ok=True)
        params_path = out_dir / "heatsink.params.json"
        params_path.write_text(json.dumps(params, indent=2), encoding="utf-8")
        envelope.inputs["params_path"] = str(params_path)
        envelope.artifacts.append(ctx.artifacts.add(params_path, "cad_parameters", "heat-sink CAD parameters derived from the Stage A candidate", ctx.task.id))
        code, output = _run_build("heatsink", params_path.resolve(), out_dir.resolve(), params["name"], float(p.get("timeout_s", 900)), ctx.task_dir / "aipe-cad.log")
        if code != 0:
            envelope.status = "failed"
            envelope.add_error("aipe-cad", output[-1200:])
            return envelope
        got = _collect(ctx, envelope, out_dir, params["name"])
        totals = got["metadata"].get("totals") or {}
        status, no_hard_fail = _check_status(got["checks"])
        if not no_hard_fail:
            envelope.status = "failed"
            envelope.add_error("geometry-check", "interference/fit/keep-out or clearance failure: " + json.dumps(got["checks"].get("summary"))[:600]
                               + " interference=" + json.dumps(got["checks"].get("interference"))[:600])
            return envelope
        mass_sink_cad = (totals.get("mass_by_material_kg") or {}).get(params["base"]["material"])
        mass_analytical = (cand.get("objectives") or {}).get("mass")
        envelope.outputs = {
            "candidate_id": cand.get("candidate_id"), "bridge": worst, "device_part_number": part,
            "geometry": {"base_length_m": length, "base_width_m": width, "base_thickness_m": params["base"]["thickness"], "fin_thickness_m": fin_t,
                         "fin_height_m": params["fins"]["height"], "fin_pitch_m": pitch, "fin_count": count, "material": params["base"]["material"]},
            "bbox_m": totals.get("bbox_m"), "size_m": totals.get("size_m"), "volume_m3": totals.get("volume_m3"), "mass_kg": totals.get("mass_kg"),
            "mass_by_material_kg": totals.get("mass_by_material_kg"), "body_count": totals.get("body_count"),
            "sink_mass_cad_kg": mass_sink_cad, "sink_mass_analytical_kg": mass_analytical,
            "sink_mass_cad_vs_analytical_relative": ((mass_sink_cad - mass_analytical) / mass_analytical) if (isinstance(mass_sink_cad, (int, float)) and mass_analytical) else None,
            "check_status": status, "check_summary": got["checks"].get("summary"),
            "clearance": [{k: r.get(k) for k in ("net_a", "net_b", "required_clearance_m", "required_creepage_m", "status", "message")} for r in (got["checks"].get("clearance") or [])],
            "step_reimport": {k: v for k, v in (got["metadata"].get("step_reimport") or {}).items() if not isinstance(v, (list, dict))},
            "analytic_vs_cad": got["metadata"].get("analytic"), "files": got["paths"], "warnings": got["metadata"].get("warnings"),
        }
        envelope.verification = {"build_ok": True, "check_status": status, "no_hard_failures": no_hard_fail,
                                 "sink_mass_cad_vs_analytical_relative": envelope.outputs["sink_mass_cad_vs_analytical_relative"]}
        for w in got["metadata"].get("warnings") or []:
            envelope.add_warning("aipe-cad", str(w))
        suffix = run_suffix(ctx.run_id)
        evidence_id = f"evidence.cad-heatsink-{suffix}"
        evidence = {
            "id": evidence_id, "kind": "analytical",
            "description": (f"Parametric FreeCAD heat sink of Stage A candidate {cand.get('candidate_id')} ({length * 1e3:.0f} x {width * 1e3:.0f} mm base, {count} fins x {fin_t * 1e3:.1f} mm, "
                            f"{params['fins']['height'] * 1e3:.0f} mm high) with two {part}: sink mass {mass_sink_cad} kg (correlation model {mass_analytical} kg), "
                            f"geometric checks '{status}'; illustrative geometry."),
            "source": {"type": "repository", "reference": "https://github.com/FulongLi/AIPE-CAD-Agent", "locator": "src/aipe_cad/freecad/build_heatsink.py"},
            "provenance": {"created_at": started, "activity": "Derive CAD parameters from the Stage A candidate; build FCStd/STEP in FreeCAD console mode; run interference and clearance checks.",
                           "tool": dict(envelope.tool), "agent": {"id": "aipe.workflows", "version": "0.1.0"},
                           "inputs": [e for e in ["evidence.specification", thermal.get("evidence_id"), semis.get("evidence_id")] if e]},
            "artifacts": [a.to_core() for a in envelope.artifacts], "review_status": "unreviewed",
        }
        envelope.state_proposal = {
            "evidence": [evidence],
            "append": [{"path": "validation.checks", "value": {"id": f"check.cad-heatsink-{suffix}", "kind": "analytical", "status": "pass",
                                                               "description": "Heat-sink CAD built from the Stage A candidate; no interference or fit failure; CAD mass compared with the correlation model mass.",
                                                               "evidence_refs": [evidence_id]}}],
            "extensions": {"aipe.workflows.dab": {"cad_heatsink": {k: v for k, v in envelope.outputs.items() if k not in ("clearance", "files", "warnings", "analytic_vs_cad")}}},
            "updated_at": now_iso(),
        }
        return envelope
