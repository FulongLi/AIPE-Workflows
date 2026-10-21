"""Requirements task: build and validate the initial Engineering State from the specification."""

from __future__ import annotations

import hashlib
import json

from ..engine.envelope import ExecutionEnvelope, now_iso
from ..engine.runner import TaskAdapter, TaskContext
from ..engineering_state.state import build_initial_state, validate_state


class RequirementsTask(TaskAdapter):
    id = "aipe.workflows.requirements"
    version = "0.1.0"

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:
        started = now_iso()
        spec = ctx.inputs.get("specification") or ctx.spec
        state = ctx.state or build_initial_state(spec, started)
        errors = validate_state(state, ctx.core_dir) if ctx.core_dir else ["Core checkout not available; state not validated"]
        envelope = ExecutionEnvelope(task_id=ctx.task.id, task_version=self.version, capability_id="aipe.core",
                                     tool={"id": "aipe.core.validate", "version": "0.1.0"}, status="completed", started_at=started,
                                     finished_at=now_iso(), source_state_id=state.get("id", ""), source_state_sha256=ctx.state_sha256,
                                     inputs={"specification_sha256": hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode("utf-8")).hexdigest()}, evidence_kind="assumption", gate="software",
                                     outputs={"state_id": state["id"], "operating_point_id": "operating-point.nominal",
                                              "requirements": spec["requirements"], "converter": spec.get("converter", {}),
                                              "constraints": spec.get("constraints", []), "environment": spec.get("environment", {})},
                                     verification={"core_schema_validation": {"errors": errors, "passed": not errors}})
        path = ctx.task_dir / "initial-state.json"
        path.write_text(json.dumps(state, indent=2), encoding="utf-8")
        envelope.artifacts.append(ctx.artifacts.add(path, "engineering_state", "Initial Engineering State built from the specification", ctx.task.id))
        if errors:
            envelope.status = "failed"
            for error in errors:
                envelope.add_error("core-validation", error)
        if not ctx.core_dir:
            envelope.add_warning("core-missing", "AIPE-Core checkout not found; schema validation skipped")
        return envelope
