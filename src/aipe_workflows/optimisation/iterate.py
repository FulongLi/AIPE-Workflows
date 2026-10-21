"""Derive, execute and judge an iteration of a workflow run."""

from __future__ import annotations

import copy
import json
import shutil
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

import yaml

from ..engine.envelope import now_iso
from ..engine.runner import RunState

KEY_OBSERVABLES = {
    "p_out_W": ("circuit-sim-level1", "p_out_W"),
    "loss_W_level1": ("circuit-sim-level1", "loss_W"),
    "i_L_rms_A": ("circuit-sim-level1", "i_L_rms_A"),
    "i_L_peak_A": ("circuit-sim-level1", "i_L_peak_A"),
    "i_s_rms_A": ("circuit-sim-level1", "i_s_rms_A"),
    "phi_deg": ("analytic-sps", "phi_deg"),
    "analytic_power_W": ("analytic-sps", "power_W"),
}


@dataclass
class IterationRecord:
    iteration_id: str
    parent_run: str
    child_run: str
    reason: str
    changes: dict[str, Any]
    created_at: str
    status: str = "pending"  # pending | accepted | rejected | failed
    decision_reasons: list[str] = field(default_factory=list)
    observables_parent: dict[str, Any] = field(default_factory=dict)
    observables_child: dict[str, Any] = field(default_factory=dict)
    tasks_rerun: list[str] = field(default_factory=list)
    tasks_reused: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _set_path(data: dict, dotted: str, value: Any) -> None:
    parts = dotted.split(".")
    node = data
    for part in parts[:-1]:
        node = node.setdefault(part, {})
    if value is None:
        node.pop(parts[-1], None)
    else:
        node[parts[-1]] = value


def apply_changes(spec: dict, changes: dict[str, Any]) -> dict:
    """Return a copy of ``spec`` with dotted-path changes applied (``None`` removes a key)."""
    new = copy.deepcopy(spec)
    for key, value in changes.items():
        _set_path(new, key, value)
    return new


def parse_change(text: str) -> tuple[str, Any]:
    """Parse ``path=value`` where value is YAML (``null`` removes the key)."""
    if "=" not in text:
        raise ValueError(f"change must be path=value: {text}")
    key, _, raw = text.partition("=")
    return key.strip(), yaml.safe_load(raw)


def task_outputs(run_dir: Path) -> dict[str, dict]:
    state = RunState.load(run_dir)
    out: dict[str, dict] = {}
    for tid, record in state.tasks.items():
        if record.envelope_path and Path(record.envelope_path).is_file():
            out[tid] = json.loads(Path(record.envelope_path).read_text(encoding="utf-8")).get("outputs", {})
    return out


def observables(run_dir: Path) -> dict[str, Any]:
    outputs = task_outputs(run_dir)
    result: dict[str, Any] = {}
    for name, (tid, key) in KEY_OBSERVABLES.items():
        value = outputs.get(tid, {}).get(key)
        if value is not None:
            result[name] = value
    sims = {tid: o for tid, o in outputs.items() if tid.startswith("circuit-sim") and o}
    for tid, o in sims.items():
        if o.get("comparison_vs_analytic") is not None:
            result[f"{tid}:comparison_pass"] = o["comparison_vs_analytic"]["pass"]
        if o.get("zvs_overview"):
            result[f"{tid}:all_zvs"] = all(bool(v) for v in o["zvs_overview"].values())
        if o.get("efficiency") is not None:
            result[f"{tid}:efficiency"] = o["efficiency"]
    return result


def compare_runs(parent: Path, child: Path) -> dict[str, Any]:
    a, b = observables(parent), observables(child)
    rows = {}
    for key in sorted(set(a) | set(b)):
        va, vb = a.get(key), b.get(key)
        row: dict[str, Any] = {"parent": va, "child": vb}
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and not isinstance(va, bool) and va:
            row["relative_change"] = (vb - va) / abs(va)
        rows[key] = row
    return rows


def default_decision(child_state: RunState, comparison: dict[str, Any], spec: dict) -> tuple[str, list[str]]:
    """Accept when the child run completed, every simulation matched its analytic reference, ZVS held
    and the rated power is met within 2 %; otherwise reject with explicit reasons."""
    reasons: list[str] = []
    if child_state.status != "completed":
        reasons.append(f"child run status {child_state.status}")
    for key, row in comparison.items():
        if key.endswith(":comparison_pass") and row.get("child") is False:
            reasons.append(f"{key.split(':')[0]} does not match the analytical reference")
        if key.endswith(":all_zvs") and row.get("child") is False:
            reasons.append(f"{key.split(':')[0]} loses the ZVS current condition on at least one switch")
    rated = float(spec["requirements"]["nominal_power_W"])
    p_out = comparison.get("p_out_W", {}).get("child")
    if isinstance(p_out, (int, float)) and abs(p_out - rated) / rated > 0.02:
        reasons.append(f"rated power not met: {p_out:.1f} W versus {rated:.0f} W")
    return ("rejected" if reasons else "accepted"), reasons or ["completed; simulations match their analytical references; ZVS retained; rated power within 2 %"]


def iterate_run(parent_run_dir: Path, changes: dict[str, Any], reason: str, run_factory: Callable[[dict, Path, str], Any],
                child_run_id: Optional[str] = None, decide: Callable = default_decision) -> IterationRecord:
    parent_run_dir = Path(parent_run_dir)
    parent_state = RunState.load(parent_run_dir)
    spec = json.loads((parent_run_dir / "specification.json").read_text(encoding="utf-8"))
    new_spec = apply_changes(spec, changes)
    if child_run_id:
        child_id = child_run_id
        iteration_id = child_id.rsplit("-", 1)[-1]
        child_dir = parent_run_dir.parent / child_id
        if child_dir.exists():
            raise FileExistsError(child_dir)
    else:
        n = 1
        while True:  # first free iteration number
            iteration_id = f"it{n:02d}"
            child_id = f"{parent_state.run_id}-{iteration_id}"
            child_dir = parent_run_dir.parent / child_id
            if not child_dir.exists():
                break
            n += 1
    # Seed the child with the parent's checkpoints so unchanged tasks are reused, not recomputed.
    shutil.copytree(parent_run_dir, child_dir, ignore=shutil.ignore_patterns("report", "iterations.json"))
    child_state = RunState.load(child_dir)
    child_state.run_id = child_id
    child_state.run_dir = str(child_dir)
    child_state.messages.append(f"iteration {iteration_id} of {parent_state.run_id}: {reason}; changes {json.dumps(changes)}")
    for record in child_state.tasks.values():
        if record.envelope_path:
            record.envelope_path = str(child_dir / Path(record.envelope_path).relative_to(parent_run_dir)) if Path(record.envelope_path).is_relative_to(parent_run_dir) else record.envelope_path
    for version in child_state.state_versions:
        p = Path(version["path"])
        if p.is_relative_to(parent_run_dir):
            version["path"] = str(child_dir / p.relative_to(parent_run_dir))
    # The initial Engineering State is a function of the specification: rebuild it for the child.
    from ..engineering_state.state import build_initial_state, state_sha256
    initial = build_initial_state(new_spec, now_iso())
    for stale in (child_dir / "state").glob("state-*.json"):
        stale.unlink()
    initial_path = child_dir / "state" / "state-000.json"
    initial_path.write_text(json.dumps(initial, indent=2, default=str), encoding="utf-8")
    child_state.state_versions = [{"version": 0, "path": str(initial_path), "sha256": state_sha256(initial), "task_id": "initial", "created_at": now_iso()}]
    child_state.save()
    (child_dir / "specification.json").write_text(json.dumps(new_spec, indent=2, sort_keys=True, default=str), encoding="utf-8")
    record = IterationRecord(iteration_id=iteration_id, parent_run=str(parent_run_dir), child_run=str(child_dir), reason=reason,
                             changes=changes, created_at=now_iso(), observables_parent=observables(parent_run_dir))
    before = {tid: r.status for tid, r in child_state.tasks.items()}
    try:
        final_state = run_factory(new_spec, child_dir, child_id)
    except Exception as exc:  # the iteration itself failed to execute
        record.status, record.decision_reasons = "failed", [f"{type(exc).__name__}: {exc}"]
        _append_ledger(parent_run_dir, record)
        return record
    record.tasks_rerun = [tid for tid, r in final_state.tasks.items() if r.status in ("completed", "failed")]
    record.tasks_reused = [tid for tid, r in final_state.tasks.items() if r.status == "reused"]
    record.observables_child = observables(child_dir)
    comparison = compare_runs(parent_run_dir, child_dir)
    record.status, record.decision_reasons = decide(final_state, comparison, new_spec)
    (child_dir / "iteration.json").write_text(json.dumps({**record.to_dict(), "comparison": comparison}, indent=2, default=str), encoding="utf-8")
    _append_ledger(parent_run_dir, record)
    return record


def _append_ledger(parent_run_dir: Path, record: IterationRecord) -> None:
    ledger_path = parent_run_dir / "iterations.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8")) if ledger_path.is_file() else []
    ledger.append(record.to_dict())
    ledger_path.write_text(json.dumps(ledger, indent=2, default=str), encoding="utf-8")
