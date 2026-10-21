"""Reconcile the circuit model's electrical parameters with the magnetics and FEM results of a run.

The DAB circuit model is parametrised by the specification's converter block: total primary-referred series
inductance, the part of it attributed to transformer leakage, the external inductor, the magnetising inductance and
the transformer turns ratio. The magnetics design and the window FEM produce their own values for leakage,
magnetising inductance and the integer turns ratio. ``reconcile`` compares both sides, labels every quantity with
its source and evidence id, and proposes the specification changes that an ``iterate`` child run needs so the
affected electrical simulations are re-executed with the updated parameters. Nothing is changed unless ``apply`` is
requested; the comparison itself is recorded as JSON next to the run.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .iterate import IterationRecord, iterate_run, task_outputs


@dataclass
class Proposal:
    path: str                       # dotted specification path, e.g. converter.leakage_inductance_primary_H
    quantity: str
    current: Any                    # value used by the run (from specification.json)
    proposed: Any                   # value from the specialist result
    relative_change: Optional[float]
    source_task: str
    evidence_id: Optional[str]
    within_tolerance: bool
    note: str = ""


def _evidence_id(run_dir: Path, task_id: str) -> Optional[str]:
    path = run_dir / "tasks" / task_id / "envelope.json"
    if not path.is_file():
        return None
    envelope = json.loads(path.read_text(encoding="utf-8"))
    evidence = (envelope.get("state_proposal") or {}).get("evidence") or []
    return evidence[0].get("id") if evidence else None


def _rel(current: Optional[float], proposed: Optional[float]) -> Optional[float]:
    if current is None or proposed is None:
        return None
    if current == 0:
        return None if proposed == 0 else float("inf")
    return (proposed - current) / abs(current)


def reconcile(run_dir: str | Path, tolerance: float = 0.02, prefer: str = "fem") -> dict[str, Any]:
    """Compare the converter parameters of a run with the magnetics/FEM results and propose specification changes."""
    run_dir = Path(run_dir)
    spec = json.loads((run_dir / "specification.json").read_text(encoding="utf-8"))
    conv = spec.get("converter", {})
    outputs = task_outputs(run_dir)
    mag = outputs.get("magnetics-transformer-design", {}) or {}
    fem = outputs.get("fem-transformer-window", {}) or {}
    proposals: list[Proposal] = []

    def consider(path: str, quantity: str, current: Optional[float], proposed: Optional[float], source: str, note: str = "") -> Optional[Proposal]:
        if proposed is None:
            return None
        rel = _rel(current, proposed)
        within = rel is not None and abs(rel) <= tolerance
        prop = Proposal(path, quantity, current, float(proposed), rel, source, _evidence_id(run_dir, source), within, note)
        proposals.append(prop)
        return prop

    l_total = conv.get("series_inductance_H")
    l_total = float(l_total) if l_total is not None else None
    # --- transformer leakage (primary referred) ------------------------------------------------------------------
    leak_fem, leak_mag = fem.get("L_leakage_primary_H_fem"), mag.get("leakage_inductance_H")
    if prefer == "fem" and leak_fem is not None:
        leak_src, leak_val, leak_note = "fem-transformer-window", leak_fem, "executed 2-D window FEM of the selected core and layout"
    elif leak_mag is not None:
        leak_src, leak_val, leak_note = "magnetics-transformer-design", leak_mag, "1-D leakage estimate of the magnetics design"
    else:
        leak_src, leak_val, leak_note = "", None, ""
    leak_prop = consider("converter.leakage_inductance_primary_H", "transformer leakage inductance, primary referred",
                         conv.get("leakage_inductance_primary_H", 0.0), leak_val, leak_src, leak_note)
    if leak_mag is not None and leak_fem is not None:
        # record the FEM-vs-1-D agreement as information (not a specification change)
        proposals.append(Proposal("(information)", "leakage: FEM versus magnetics 1-D", float(leak_mag), float(leak_fem), _rel(leak_mag, leak_fem),
                                  "fem-transformer-window", _evidence_id(run_dir, "fem-transformer-window"),
                                  _rel(leak_mag, leak_fem) is not None and abs(_rel(leak_mag, leak_fem)) <= max(tolerance, 0.05),
                                  "agreement check between the 1-D design estimate and the executed FEM"))
    # --- external inductor keeps the total series inductance -----------------------------------------------------
    if leak_prop is not None and l_total is not None:
        consider("converter.external_inductance_H", "external series inductor (total minus transformer leakage)",
                 conv.get("external_inductance_H", l_total), l_total - leak_prop.proposed, leak_src,
                 f"total primary-referred series inductance {l_total:.4g} H kept constant")
    # --- magnetising inductance ----------------------------------------------------------------------------------
    lm_fem, lm_mag = fem.get("L_magnetising_primary_H_fem"), mag.get("magnetising_inductance_H")
    if prefer == "fem" and lm_fem is not None:
        consider("converter.magnetising_inductance_H", "magnetising inductance, primary referred", conv.get("magnetising_inductance_H"), lm_fem,
                 "fem-transformer-window", "executed FEM, secondary open; depends on the assumed core permeability")
    elif lm_mag is not None:
        consider("converter.magnetising_inductance_H", "magnetising inductance, primary referred", conv.get("magnetising_inductance_H"), lm_mag,
                 "magnetics-transformer-design", "reluctance model of the magnetics design")
    # --- actual integer turns ratio ------------------------------------------------------------------------------
    ratio = mag.get("turns_ratio_actual")
    if ratio is not None:
        prop = consider("converter.turns_ratio_np_ns", "transformer turns ratio Np/Ns (integer turns of the selected design)",
                        conv.get("turns_ratio_np_ns"), ratio, "magnetics-transformer-design",
                        f"turns {mag.get('turns_primary')}:{mag.get('turns_secondary')}")
        if prop is not None and not prop.within_tolerance:
            proposals.append(Proposal("converter.phase_shift_deg", "nominal phase shift (re-solved for rated power when the ratio changes)",
                                      conv.get("phase_shift_deg"), None, None, "analytic-sps", None, False,
                                      "set to null so the analytical task re-solves the phase shift"))
    changes = {p.path: p.proposed for p in proposals if not p.within_tolerance and not p.path.startswith("(")}
    result = {
        "run": str(run_dir), "tolerance": tolerance, "prefer": prefer,
        "proposals": [asdict(p) for p in proposals],
        "changes": changes, "consistent": not changes,
        "reason": ("series-inductance / turns-ratio reconciliation: " + "; ".join(
            f"{p.quantity} {p.current} -> {p.proposed} ({p.source_task})" for p in proposals if p.path in changes)) if changes else
                  "circuit model already consistent with the magnetics and FEM results within tolerance",
    }
    (run_dir / "reconciliation.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result


def reconcile_and_iterate(run_dir: str | Path, run_factory: Callable[[dict, Path, str], Any], tolerance: float = 0.02, prefer: str = "fem",
                          child_run_id: Optional[str] = None) -> tuple[dict[str, Any], Optional[IterationRecord]]:
    """Reconcile and, when the circuit model is inconsistent, derive the child run that re-executes the affected tasks."""
    result = reconcile(run_dir, tolerance, prefer)
    if result["consistent"]:
        return result, None
    record = iterate_run(Path(run_dir), result["changes"], result["reason"], run_factory, child_run_id=child_run_id)
    result["iteration"] = record.to_dict()
    (Path(run_dir) / "reconciliation.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return result, record
