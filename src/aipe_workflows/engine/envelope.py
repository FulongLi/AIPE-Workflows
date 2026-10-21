"""Common specialist execution envelope (compatible with AIPE Core evidence).

Every adapter returns an :class:`ExecutionEnvelope`. The envelope is what the
workflow stores as a checkpoint, hashes for selective re-execution, and turns
into Core evidence/simulation records. Full numerical arrays and large files
stay in artifacts; the envelope carries validated summaries and references.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

STATUSES = ("completed", "failed", "blocked", "skipped", "not_run")


@dataclass
class ArtifactRef:
    uri: str
    media_type: str
    sha256: Optional[str] = None
    description: str = ""
    role: str = ""  # e.g. netlist, solver_log, waveform_dataset, summary, figure, cad_step, mesh

    def to_core(self) -> dict:
        ref = {"uri": self.uri, "media_type": self.media_type}
        if self.sha256:
            ref["sha256"] = self.sha256
        if self.description:
            ref["description"] = self.description
        return ref


@dataclass
class Diagnostic:
    severity: str  # error | warning | info
    code: str
    message: str


@dataclass
class ExecutionEnvelope:
    task_id: str
    task_version: str
    capability_id: str  # Registry capability (repository) id, e.g. aipe.simulation-skills
    tool: dict  # {id, version, name?}
    status: str  # completed | failed | blocked | skipped
    started_at: str
    finished_at: str
    source_state_id: str
    source_state_sha256: str
    inputs: dict[str, Any] = field(default_factory=dict)  # SI quantities / references actually used
    outputs: dict[str, Any] = field(default_factory=dict)  # validated summary values (small)
    model: dict[str, Any] = field(default_factory=dict)  # {id, version, validity_range, assumptions}
    environment: dict[str, Any] = field(default_factory=dict)  # tool/library versions, platform
    verification: dict[str, Any] = field(default_factory=dict)  # numerical checks (convergence, balances)
    evidence_kind: str = "analytical"  # assumption | analytical | simulation | measurement | source
    gate: str = "software"
    artifacts: list[ArtifactRef] = field(default_factory=list)
    diagnostics: list[Diagnostic] = field(default_factory=list)
    approval_required: list[str] = field(default_factory=list)
    state_proposal: dict[str, Any] = field(default_factory=dict)  # proposed Engineering State changes
    input_hash: str = ""

    def __post_init__(self) -> None:
        if self.status not in STATUSES:
            raise ValueError(f"invalid envelope status {self.status!r}")

    @property
    def ok(self) -> bool:
        return self.status == "completed" and not any(d.severity == "error" for d in self.diagnostics)

    def to_dict(self) -> dict:
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ExecutionEnvelope":
        data = dict(data)
        data["artifacts"] = [ArtifactRef(**a) for a in data.get("artifacts", [])]
        data["diagnostics"] = [Diagnostic(**d) for d in data.get("diagnostics", [])]
        return cls(**data)

    def add_error(self, code: str, message: str) -> None:
        self.diagnostics.append(Diagnostic("error", code, message))

    def add_warning(self, code: str, message: str) -> None:
        self.diagnostics.append(Diagnostic("warning", code, message))


def now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False)


def envelope_hash(inputs: dict[str, Any], model: dict[str, Any], tool: dict[str, Any], parameters: dict[str, Any]) -> str:
    """Hash of everything that determines a task's result; used for selective re-execution."""
    return hashlib.sha256(canonical_json({"inputs": inputs, "model": model, "tool": tool, "parameters": parameters}).encode("utf-8")).hexdigest()
