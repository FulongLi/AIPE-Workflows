"""AIPE-Semiconductor-Database adapter: waveform-driven device screening and loss evaluation.

Calls the database's own command line (``aipe_devices.cli dab-screen`` and
``dab-losses``) so that the evidence tiers, interpolation-envelope policy and
coverage reporting of the specialist repository are used unchanged. The
per-switch stresses come from the executed ngspice summary (Level 2 by
default); the full waveform dataset (HDF5) is passed for the conduction-loss
integral of the selected devices.

Selection rule (recorded in the envelope): the database ranking (confidence
tier A before B, then estimated total loss) is kept; an optional
``preferred_integration`` parameter restricts the pick to ``discrete`` or
``module`` packages because the downstream thermal, CAD and PCB stages of this
workflow are laid out for one package style. Alternatives stay in the ranked
list of the outputs.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

from ..engine.envelope import ExecutionEnvelope, now_iso
from ..engine.runner import TaskAdapter, TaskContext
from .common import find_sibling_repo
from .design_agent import run_suffix


def _q(value: float, unit: str) -> dict[str, Any]:
    return {"value": float(value), "unit": unit}


def _run_cli(args: list[str], cwd: Path, timeout: float = 900.0) -> tuple[int, str, str]:
    completed = subprocess.run([sys.executable, "-m", "aipe_devices.cli", *args], cwd=str(cwd), capture_output=True, text=True,
                               timeout=timeout, check=False, errors="replace")
    return completed.returncode, completed.stdout, completed.stderr


def _bridge_block(screening: dict, bridge: str) -> dict:
    for block in screening.get("bridges", []):
        if block.get("bridge") == bridge:
            return block
    return {}


def _pick(ranked: list[dict], preferred_integration: Optional[str]) -> Optional[dict]:
    """First ranked device with a canonical record and a complete loss evaluation, honouring the package preference."""
    for require_complete in (True, False):
        for item in ranked:
            if preferred_integration and item.get("integration") != preferred_integration:
                continue
            if not item.get("canonical_id"):
                continue
            if require_complete and not (item.get("loss") or {}).get("complete"):
                continue
            return item
    return None


def _compact(item: Optional[dict]) -> Optional[dict]:
    if not item:
        return None
    loss = item.get("loss") or {}
    thermal = item.get("thermal") or {}
    return {"candidate_id": item.get("candidate_id"), "canonical_id": item.get("canonical_id"), "manufacturer": item.get("manufacturer"),
            "part_number": item.get("part_number"), "package": item.get("package"), "integration": item.get("integration"),
            "vds_rating_V": (item.get("electrical") or {}).get("vds_rating"), "id_rating_A": (item.get("electrical") or {}).get("id_rating"),
            "loss_evidence": loss.get("evidence"), "loss_total_W_at_tj": loss.get("total"), "loss_conduction_W": loss.get("conduction"),
            "loss_turn_off_W": loss.get("turn_off"), "loss_complete": loss.get("complete"), "loss_flags": loss.get("flags"),
            "rth_junction_to_case_K_per_W": thermal.get("rth_junction_to_case"), "tj_max_rating_K": thermal.get("tj_max_rating"),
            "tj_at_fixed_loss_K": thermal.get("tj_at_fixed_loss"),
            "fixed_point": {k: (thermal.get("fixed_point") or {}).get(k) for k in ("converged", "junction_temperature", "loss")}}


class DabDeviceScreeningTask(TaskAdapter):
    id = "aipe.semiconductor-database.dab-screening"
    version = "0.1.0"

    def _repo(self) -> Optional[Path]:
        return find_sibling_repo("AIPE-Semiconductor-Database", "AIPE_SEMICONDUCTOR_DB_DIR")

    def requirements(self, environment: dict[str, Any]) -> list[str]:
        problems = []
        try:
            import aipe_devices  # noqa: F401
        except ImportError:
            problems.append("python package aipe_devices (AIPE-Semiconductor-Database) is not installed: pip install -e ../AIPE-Semiconductor-Database")
        if self._repo() is None:
            problems.append("AIPE-Semiconductor-Database checkout not found (canonical and candidate records are read from it)")
        return problems

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:
        import aipe_devices

        started = now_iso()
        p = ctx.task.parameters
        repo = self._repo()
        version = str(getattr(aipe_devices, "__version__", "unknown"))
        sim = ctx.inputs["simulation"]
        req = ctx.inputs["requirements"]
        # run-relative artifact paths are resolved against the engine's working directory before the CLI runs in the database checkout
        summary_path = Path(sim["summary_path"]).resolve()
        dataset_path = Path(sim["dataset"]).resolve()
        tj = float(p.get("junction_temperature_K", 398.15))
        rth_cs = float(p.get("rth_case_sink_K_per_W", 0.1))
        rth_sa = float(p.get("rth_sink_ambient_K_per_W", 0.5))
        ambient = float(p.get("ambient_K", 313.15))
        rg_on, rg_off = float(p.get("rg_on_Ohm", 2.5)), float(p.get("rg_off_Ohm", 2.5))
        preferred = p.get("preferred_integration")
        common = ["--tj", str(tj), "--fsw", str(float(req["switching_frequency_Hz"])), "--rg-on", str(rg_on), "--rg-off", str(rg_off),
                  "--rth-cs", str(rth_cs), "--rth-sa", str(rth_sa), "--ambient", str(ambient)]
        if p.get("allow_extrapolation"):
            common.append("--allow-extrapolation")
        screen_out = (ctx.task_dir / "screening.json").resolve()  # absolute: the CLI runs with the database checkout as cwd
        args = ["dab-screen", "--summary", str(summary_path), "--repository", str(repo / "data" / "canonical"),
                "--candidates", str(repo / "data" / "candidates" / "records"), "--derating", str(p.get("derating", 0.70)),
                "--tj-limit", str(p.get("tj_limit_K", 398.15)), "--output", str(screen_out), *common]
        code, out, err = _run_cli(args, repo)
        envelope = ExecutionEnvelope(task_id=ctx.task.id, task_version=self.version, capability_id="aipe.semiconductor-database",
                                     tool={"id": "aipe.semiconductor-database.dab-screening", "version": version, "name": "aipe_devices"},
                                     status="completed", started_at=started, finished_at=now_iso(), source_state_id=ctx.state.get("id", ""),
                                     source_state_sha256=ctx.state_sha256,
                                     inputs={"summary": str(summary_path), "dataset_sha256": sim.get("dataset_sha256"), "junction_temperature_K": tj,
                                             "rth_case_sink_K_per_W": rth_cs, "rth_sink_ambient_K_per_W": rth_sa, "ambient_K": ambient,
                                             "gate_resistance_Ohm": [rg_on, rg_off], "derating": p.get("derating", 0.70), "preferred_integration": preferred},
                                     model={"id": "aipe-devices-dab-screening", "version": version,
                                            "validity_range": "manufacturer PLECS loss tensors (tier A) and datasheet points scaled linearly in V and I (tier B); "
                                                              "no Coss/Eoss data, ZVS by current condition only; no measured evidence"},
                                     evidence_kind="analytical", gate="analytical")
        (ctx.task_dir / "dab-screen.log").write_text(out + "\n" + err, encoding="utf-8")
        if code != 0 or not screen_out.is_file():
            envelope.status = "failed"
            envelope.add_error("dab-screen", (err or out)[-800:])
            return envelope
        screening = json.loads(screen_out.read_text(encoding="utf-8"))
        envelope.artifacts.append(ctx.artifacts.add(screen_out, "analysis_summary", "device screening report (aipe_devices dab-screen)", ctx.task.id))

        bridges = {b: _bridge_block(screening, b) for b in ("primary", "secondary")}
        ranked = {b: list(block.get("ranked") or []) for b, block in bridges.items()}
        selected = {b: _pick(ranked[b], preferred) for b in ranked}
        bus = {"primary": float(req["input_voltage_V"]), "secondary": float(req["output_voltage_V"])}
        losses: dict[str, Any] = {}
        for bridge, best in selected.items():
            if not best:
                continue
            device_id = best["canonical_id"]
            switch = bridges[bridge].get("worst_case_switch") or ("S1" if bridge == "primary" else "S5")
            vdc = (bridges[bridge].get("dc_bus_voltage") or bus[bridge])
            out_path = (ctx.task_dir / f"losses-{bridge}-{switch}.json").resolve()
            args = ["dab-losses", "--device", device_id, "--summary", str(summary_path), "--switch", switch, "--vdc", str(vdc),
                    "--repository", str(repo / "data" / "canonical"), "--output", str(out_path), *common]
            if dataset_path.is_file():
                args += ["--waveforms", str(dataset_path)]
            code, out, err = _run_cli(args, repo)
            (ctx.task_dir / f"dab-losses-{bridge}.log").write_text(out + "\n" + err, encoding="utf-8")
            if code == 0 and out_path.is_file():
                payload = json.loads(out_path.read_text(encoding="utf-8"))
                result, thermal = payload.get("result", {}), payload.get("thermal", {})
                fixed = thermal.get("electro_thermal_fixed_point") or {}
                losses[bridge] = {
                    "device_id": device_id, "switch": switch, "dc_bus_voltage_V": vdc, "path": str(out_path),
                    "total_loss_W_at_tj": result.get("total_loss"), "complete": result.get("complete"),
                    "components": [{k: c.get(k) for k in ("name", "kind", "value", "unit", "method", "evidence")} for c in (result.get("components") or []) if isinstance(c, dict)],
                    "stress_source": (result.get("stress") or {}).get("source"), "warnings": result.get("warnings"),
                    "coverage_gaps": [c.get("item") or c.get("name") or c for c in (result.get("coverage") or []) if not (isinstance(c, dict) and c.get("status") in ("covered", "evaluated"))][:20],
                    "rth_junction_to_case_K_per_W": thermal.get("rth_junction_to_case"),
                    "fixed_point_converged": fixed.get("converged"), "fixed_point_tj_K": fixed.get("junction_temperature"), "fixed_point_loss_W": fixed.get("loss"),
                    "evidence_origins": result.get("evidence_origins"),
                }
                envelope.artifacts.append(ctx.artifacts.add(out_path, "analysis_summary", f"{bridge} device loss evaluation ({device_id}, {switch})", ctx.task.id))
            else:
                envelope.add_warning("dab-losses", f"{bridge} {device_id}: {(err or out)[-300:]}")

        def per_device_loss(bridge: str) -> Optional[float]:
            block = losses.get(bridge)
            if block and isinstance(block.get("total_loss_W_at_tj"), (int, float)):
                return float(block["total_loss_W_at_tj"])
            best = selected.get(bridge)
            value = ((best or {}).get("loss") or {}).get("total")
            return float(value) if isinstance(value, (int, float)) else None

        outputs = {
            "screening_path": str(screen_out), "dataset_sha256": screening.get("dataset_sha256"),
            "settings": screening.get("settings"), "pool": screening.get("pool"), "notes": screening.get("notes"),
            "preferred_integration": preferred,
        }
        for bridge in ("primary", "secondary"):
            best = selected[bridge]
            outputs[f"{bridge}_worst_case_switch"] = bridges[bridge].get("worst_case_switch")
            outputs[f"{bridge}_stress"] = {k: (bridges[bridge].get("stress") or {}).get(k) for k in
                                           ("switch_id", "current_rms", "current_avg", "current_peak_forward", "current_peak_reverse", "conduction_fraction")}
            outputs[f"{bridge}_ranked"] = [_compact(r) for r in ranked[bridge][:10]]
            outputs[f"{bridge}_excluded_count"] = len(bridges[bridge].get("excluded") or [])
            outputs[f"{bridge}_selected"] = _compact(best)
            outputs[f"{bridge}_device_id"] = (best or {}).get("canonical_id")
            outputs[f"{bridge}_part_number"] = (best or {}).get("part_number")
            outputs[f"{bridge}_loss_W"] = per_device_loss(bridge)
            outputs[f"{bridge}_rth_jc_K_per_W"] = ((best or {}).get("thermal") or {}).get("rth_junction_to_case")
            outputs[f"{bridge}_tj_max_rating_K"] = ((best or {}).get("thermal") or {}).get("tj_max_rating")
            outputs[f"{bridge}_loss_evaluation"] = losses.get(bridge)
            outputs[f"{bridge}_top_ranked_overall"] = _compact(ranked[bridge][0]) if ranked[bridge] else None
        p_bridge = {b: (outputs[f"{b}_loss_W"] or 0.0) * 4 for b in ("primary", "secondary")}
        outputs["semiconductor_loss_total_W_at_tj"] = sum(p_bridge.values()) if all(outputs[f"{b}_loss_W"] is not None for b in p_bridge) else None
        outputs["junction_temperature_K"] = tj
        envelope.outputs = outputs
        envelope.verification = {"primary_candidates": len(ranked["primary"]), "secondary_candidates": len(ranked["secondary"]),
                                 "loss_evaluations": sorted(losses), "selection_complete": all(selected.values()),
                                 "loss_evaluation_complete": all((losses.get(b) or {}).get("complete") for b in ("primary", "secondary"))}
        suffix = run_suffix(ctx.run_id)
        evidence_id = f"evidence.semiconductor-screening-{suffix}"
        sim_evidence = sim.get("evidence_id")
        desc_parts = []
        for bridge in ("primary", "secondary"):
            desc_parts.append(f"{bridge} {outputs[f'{bridge}_part_number']} ({outputs[f'{bridge}_loss_W']:.2f} W per device at Tj = {tj:.0f} K)"
                              if outputs[f"{bridge}_loss_W"] is not None else f"{bridge}: no device selected")
        evidence = {
            "id": evidence_id, "kind": "analytical",
            "description": (f"Device screening on the executed Level {sim.get('level', '?')} waveform stresses (dataset sha256 {str(sim.get('dataset_sha256'))[:12]}...): "
                            + "; ".join(desc_parts) + f". Ranking by confidence tier then estimated loss; package preference '{preferred}'. "
                            "Manufacturer PLECS/datasheet data only; no laboratory measurement."),
            "source": {"type": "repository", "reference": "https://github.com/FulongLi/AIPE-Semiconductor-Database", "locator": "src/aipe_devices/services/selection/dab.py"},
            "provenance": {"created_at": started, "activity": "Screen canonical and candidate SiC devices against derating, current margin, ZVS condition and junction headroom; evaluate losses of the selected devices on the sampled waveforms.",
                           "tool": {"id": "aipe.semiconductor-database.dab-screening", "version": version},
                           "agent": {"id": "aipe.workflows", "version": "0.1.0"}, "inputs": [e for e in ["evidence.specification", sim_evidence] if e]},
            "artifacts": [a.to_core() for a in envelope.artifacts], "review_status": "unreviewed",
        }
        append = []
        for bridge, role in (("primary", "primary-bridge-switch"), ("secondary", "secondary-bridge-switch")):
            best = selected[bridge]
            if not best:
                continue
            entry = {"id": f"semiconductor.{role}", "role": role, "selection_status": "candidate", "technology": "SiC",
                     "manufacturer": str(best.get("manufacturer") or "unknown"), "part_number": str(best.get("part_number") or best["canonical_id"]),
                     "database_ref": f"urn:aipe:semiconductor:{best['canonical_id']}", "evidence_refs": [evidence_id]}
            vds = (best.get("electrical") or {}).get("vds_rating")
            if isinstance(vds, (int, float)):
                entry["ratings"] = {"voltage": _q(vds, "V")}
                ids = (best.get("electrical") or {}).get("id_rating")
                if isinstance(ids, (int, float)):
                    entry["ratings"]["current"] = _q(ids, "A")
            if outputs[f"{bridge}_loss_W"] is not None:
                entry["extensions"] = {"aipe.workflows.dab": {"estimated_loss_W_at_tj": outputs[f"{bridge}_loss_W"], "evaluation_tj_K": tj,
                                                              "rth_junction_to_case_K_per_W": outputs[f"{bridge}_rth_jc_K_per_W"]}}
            append.append({"path": "semiconductors", "value": entry})
        append.append({"path": "validation.checks", "value": {"id": f"check.semiconductor-screening-{suffix}", "kind": "analytical",
                                                               "status": "pass" if all(selected.values()) else "fail",
                                                               "description": "Devices found for both bridges within derating, current margin and junction-temperature headroom; losses evaluated from manufacturer data on the executed waveforms.",
                                                               "evidence_refs": [evidence_id]}})
        extension = {k: v for k, v in outputs.items() if not k.endswith("_ranked") and k not in ("pool", "notes")}
        envelope.state_proposal = {"evidence": [evidence], "append": append,
                                   "extensions": {"aipe.workflows.dab": {"semiconductor_screening": extension}}, "updated_at": now_iso()}
        if not all(selected.values()):
            envelope.status = "failed"
            envelope.add_error("no-device", "screening found no eligible device with a canonical record for at least one bridge")
        return envelope
