"""Verification ledger with separate statuses per engineering gate.

Gates (in order of physical commitment): analytical, software,
circuit_simulation, field_simulation, cad_pcb, engineering_review,
experimental, hardware_qualification. Passing an earlier gate never implies a
later one; each gate's status is derived only from envelopes that declared
that gate and from explicit review records.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

GATE_ORDER = ("analytical", "software", "circuit_simulation", "field_simulation", "cad_pcb", "engineering_review", "experimental",
              "hardware_qualification")


@dataclass
class GateStatus:
    gate: str
    status: str = "not_run"  # not_run | pass | fail | blocked | partial
    checks: list[dict[str, Any]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class GateLedger:
    run_id: str
    gates: dict[str, GateStatus]

    def to_dict(self) -> dict:
        return {"run_id": self.run_id, "gates": {k: asdict(v) for k, v in self.gates.items()}, "gate_order": list(GATE_ORDER)}


def build_ledger(run_dir: str | Path) -> GateLedger:
    run_dir = Path(run_dir)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    ledger = GateLedger(run_id=run["run_id"], gates={g: GateStatus(g) for g in GATE_ORDER})
    for task_id, record in run["tasks"].items():
        envelope_path = record.get("envelope_path")
        gate = None
        envelope = None
        if envelope_path and Path(envelope_path).is_file():
            envelope = json.loads(Path(envelope_path).read_text(encoding="utf-8"))
            gate = envelope.get("gate")
        if gate is None:
            workflow = json.loads((run_dir / "workflow.json").read_text(encoding="utf-8"))
            gate = next((t["gate"] for t in workflow["tasks"] if t["id"] == task_id), "software")
        status = record["status"]
        check = {"task": task_id, "status": status, "message": record.get("message", ""),
                 "verification": (envelope or {}).get("verification", {}),
                 "errors": [d["message"] for d in (envelope or {}).get("diagnostics", []) if d["severity"] == "error"]}
        ledger.gates[gate].checks.append(check)
    for gate_status in ledger.gates.values():
        statuses = {c["status"] for c in gate_status.checks}
        if not statuses:
            gate_status.status = "not_run"
        elif "failed" in statuses:
            gate_status.status = "fail"
        elif statuses <= {"completed", "reused"}:
            gate_status.status = "pass"
        elif "blocked" in statuses and statuses & {"completed", "reused"}:
            gate_status.status = "partial"
        elif "blocked" in statuses:
            gate_status.status = "blocked"
        else:
            gate_status.status = "not_run"
    for gate in ("engineering_review", "experimental", "hardware_qualification"):
        if ledger.gates[gate].status == "not_run":
            ledger.gates[gate].notes.append("no record: requires human review / laboratory measurement / hardware qualification outside this workflow")
    (run_dir / "verification.json").write_text(json.dumps(ledger.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return ledger
