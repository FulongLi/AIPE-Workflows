"""Checkpointed workflow execution with selective re-execution.

Run directory layout::

    runs/<run-id>/
        run.json                 RunState checkpoint (rewritten after every task)
        specification.json       the workflow specification as received
        plan.json                execution plan (capabilities, tools, blockers)
        environment.json         environment manifest used for the run
        state/state-000.json     initial Engineering State
        state/state-NNN.json     state after each accepted proposal (never overwritten)
        tasks/<task-id>/         adapter working directory, envelope.json, log.txt
        artifacts/index.json     hashed artifact index

Re-execution rule: a task is re-run when it has no completed envelope, when its
input hash changed, or when any upstream task was re-run in this invocation
(stale downstream results are never reused). ``force`` re-runs everything.
"""

from __future__ import annotations

import importlib
import json
import traceback
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from ..artifacts.store import ArtifactStore
from ..engineering_state.state import StateError, apply_proposal, state_sha256, validate_state
from .envelope import ExecutionEnvelope, envelope_hash, now_iso
from .graph import TaskGraph, TaskSpec, WorkflowDefinition

TASK_STATUSES = ("pending", "running", "completed", "failed", "blocked", "skipped", "reused")


@dataclass
class TaskRecord:
    task_id: str
    status: str = "pending"
    input_hash: str = ""
    envelope_path: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    attempts: int = 0
    message: str = ""
    state_version_after: Optional[int] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RunState:
    run_id: str
    workflow_id: str
    workflow_source: Optional[str]
    run_dir: str
    spec_sha256: str
    created_at: str
    status: str = "created"  # created | running | completed | completed_with_blocked | failed
    tasks: dict[str, TaskRecord] = field(default_factory=dict)
    state_versions: list[dict] = field(default_factory=list)  # [{version, path, sha256, task_id}]
    updated_at: str = ""
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["tasks"] = {k: v.to_dict() for k, v in self.tasks.items()}
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "RunState":
        data = dict(data)
        data["tasks"] = {k: TaskRecord(**v) for k, v in data.get("tasks", {}).items()}
        return cls(**data)

    @property
    def current_state_path(self) -> Optional[str]:
        return self.state_versions[-1]["path"] if self.state_versions else None

    def save(self) -> None:
        self.updated_at = now_iso()
        path = Path(self.run_dir) / "run.json"
        path.write_text(json.dumps(self.to_dict(), indent=2, sort_keys=True, default=str), encoding="utf-8")

    @classmethod
    def load(cls, run_dir: str | Path) -> "RunState":
        return cls.from_dict(json.loads((Path(run_dir) / "run.json").read_text(encoding="utf-8")))


@dataclass
class TaskContext:
    task: TaskSpec
    inputs: dict[str, Any]
    spec: dict[str, Any]
    state: dict[str, Any]
    state_sha256: str
    run_dir: Path
    task_dir: Path
    environment: dict[str, Any]
    registry_entry: Optional[dict]
    artifacts: ArtifactStore
    core_dir: Optional[Path]
    log: Callable[[str], None]
    run_id: str


class TaskAdapter:
    """Base class for specialist adapters (see adapters/)."""

    id = "aipe.workflows.adapter"
    version = "0.1.0"

    def requirements(self, environment: dict[str, Any]) -> list[str]:
        """Return human-readable blockers (missing tools, missing packages); empty when runnable."""
        return []

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:  # pragma: no cover - interface
        raise NotImplementedError


def load_adapter(path: str) -> TaskAdapter:
    module_name, _, class_name = path.partition(":")
    module = importlib.import_module(module_name)
    cls = getattr(module, class_name)
    adapter = cls()
    if not isinstance(adapter, TaskAdapter):
        raise TypeError(f"{path} is not a TaskAdapter")
    return adapter


def resolve_binding(binding: Any, spec: dict, state: dict, environment: dict, outputs: dict[str, dict]) -> Any:
    """Resolve ``$spec...``, ``$state...``, ``$env...`` and ``$task.<id>.<output>...`` bindings."""
    if not (isinstance(binding, str) and binding.startswith("$")):
        return binding
    parts = binding[1:].split(".")
    root = parts[0]
    if root == "spec":
        node: Any = spec
        rest = parts[1:]
    elif root == "state":
        node = state
        rest = parts[1:]
    elif root == "env":
        node = environment
        rest = parts[1:]
    elif root == "task":
        if len(parts) < 2:
            raise KeyError(f"binding {binding} needs $task.<id>[.<output>]")
        task_id = parts[1]
        if task_id not in outputs:
            raise KeyError(f"binding {binding}: task {task_id} produced no outputs")
        if len(parts) == 2:
            node = outputs[task_id]
            rest = []
        else:
            output = parts[2]
            if output not in outputs[task_id]:
                raise KeyError(f"binding {binding}: output {output!r} not produced by {task_id}; available {sorted(outputs[task_id])}")
            node = outputs[task_id][output]
            rest = parts[3:]
    else:
        raise KeyError(f"unknown binding root in {binding}")
    for key in rest:
        if isinstance(node, list):
            node = node[int(key)]
        elif isinstance(node, dict):
            if key not in node:
                raise KeyError(f"binding {binding}: key {key!r} missing")
            node = node[key]
        else:
            raise KeyError(f"binding {binding}: cannot descend into {type(node).__name__} with {key!r}")
    return node


class WorkflowRunner:
    def __init__(self, definition: WorkflowDefinition, spec: dict[str, Any], run_dir: str | Path, environment: dict[str, Any],
                 registry: Optional[dict[str, Any]] = None, core_dir: Optional[str | Path] = None, run_id: Optional[str] = None,
                 initial_state: Optional[dict[str, Any]] = None, log: Optional[Callable[[str], None]] = None):
        self.definition = definition
        self.graph = TaskGraph(definition)
        self.spec = spec
        self.run_dir = Path(run_dir)
        self.environment = environment
        self.registry = registry or {"capabilities": []}
        self.core_dir = Path(core_dir) if core_dir else None
        self.log = log or (lambda message: None)
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "tasks").mkdir(exist_ok=True)
        (self.run_dir / "state").mkdir(exist_ok=True)
        self.artifacts = ArtifactStore(self.run_dir / "artifacts")
        spec_hash = state_sha256(spec)
        run_json = self.run_dir / "run.json"
        if run_json.is_file():
            self.state = RunState.load(self.run_dir)
            if self.state.spec_sha256 != spec_hash:
                self.state.messages.append(f"specification changed ({self.state.spec_sha256[:12]} -> {spec_hash[:12]}); all tasks will be re-evaluated")
                self.state.spec_sha256 = spec_hash
        else:
            self.state = RunState(run_id=run_id or self.run_dir.name, workflow_id=definition.id, workflow_source=definition.source_path,
                                  run_dir=str(self.run_dir), spec_sha256=spec_hash, created_at=now_iso())
            (self.run_dir / "specification.json").write_text(json.dumps(spec, indent=2, sort_keys=True, default=str), encoding="utf-8")
            (self.run_dir / "environment.json").write_text(json.dumps(environment, indent=2, sort_keys=True, default=str), encoding="utf-8")
            (self.run_dir / "workflow.json").write_text(json.dumps(definition.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
            if initial_state is not None:
                self._commit_state(initial_state, "initial", validate=True)
            self.state.save()

    # ------------------------------------------------------------------ state
    def _commit_state(self, state: dict[str, Any], task_id: str, validate: bool = True) -> int:
        if validate and self.core_dir is not None:
            errors = validate_state(state, self.core_dir)
            if errors:
                raise StateError("proposed Engineering State rejected by Core validator: " + "; ".join(errors[:10]))
        version = len(self.state.state_versions)
        digest = state_sha256(state)
        # State files are immutable: reuse an existing file with identical content, otherwise write a new one.
        existing = next((f for f in self._all_state_files() if f["sha256"] == digest), None)
        if existing:
            path = Path(existing["path"])
        else:
            chain = getattr(self, "_chain", 0)
            name = f"state-{version:03d}.json" if chain == 0 else f"state-c{chain:02d}-{version:03d}.json"
            path = self.run_dir / "state" / name
            path.write_text(json.dumps(state, indent=2, sort_keys=False, default=str), encoding="utf-8")
        self.state.state_versions.append({"version": version, "path": str(path), "sha256": digest, "task_id": task_id, "created_at": now_iso()})
        return version

    def _all_state_files(self) -> list[dict]:
        files = []
        for path in sorted((self.run_dir / "state").glob("state-*.json")):
            try:
                files.append({"path": str(path), "sha256": state_sha256(json.loads(path.read_text(encoding="utf-8")))})
            except (OSError, ValueError):
                continue
        return files

    def current_state(self) -> Optional[dict[str, Any]]:
        path = self.state.current_state_path
        if path is None:
            return None
        return json.loads(Path(path).read_text(encoding="utf-8"))

    # ------------------------------------------------------------------- plan
    def registry_entry_for(self, capability: str) -> Optional[dict]:
        matches = [m for m in self.registry.get("capabilities", []) if capability in m.get("capabilities", [])]
        matches.sort(key=lambda m: m["id"])
        return matches[0] if matches else None

    def plan(self) -> dict:
        tasks = []
        for task_id in self.graph.order:
            task = self.graph.tasks[task_id]
            entry = self.registry_entry_for(task.capability)
            blockers: list[str] = []
            adapter_info: dict[str, Any] = {}
            try:
                adapter = load_adapter(task.adapter)
                adapter_info = {"id": adapter.id, "version": adapter.version}
                blockers.extend(adapter.requirements(self.environment))
            except Exception as exc:  # adapter import problems are blockers, not crashes
                blockers.append(f"adapter unavailable: {type(exc).__name__}: {exc}")
            for tool in task.tools:
                info = self.environment.get("tools", {}).get(tool)
                if not info or not info.get("found"):
                    blockers.append(f"tool {tool} not found")
                elif info.get("qualified") is False:
                    blockers.append(f"tool {tool} failed qualification")
            tasks.append({"id": task.id, "capability": task.capability, "adapter": task.adapter, "adapter_info": adapter_info,
                          "depends_on": task.depends_on, "gate": task.gate, "optional": task.optional, "tools": task.tools,
                          "registry": ({"id": entry["id"], "maturity": entry.get("maturity"), "status": entry.get("status"),
                                        "validation": entry.get("validation", {}).get("status"), "repository": entry.get("repository")}
                                       if entry else None),
                          "capability_registered": entry is not None, "blockers": blockers, "runnable": not blockers,
                          "previous": self.state.tasks.get(task.id).to_dict() if task.id in self.state.tasks else None})
        plan = {"workflow": self.definition.id, "run_id": self.state.run_id, "order": self.graph.order, "levels": self.graph.levels(),
                "tasks": tasks, "created_at": now_iso()}
        (self.run_dir / "plan.json").write_text(json.dumps(plan, indent=2, sort_keys=True, default=str), encoding="utf-8")
        return plan

    # -------------------------------------------------------------------- run
    def _load_outputs(self) -> dict[str, dict]:
        outputs: dict[str, dict] = {}
        for task_id, record in self.state.tasks.items():
            if record.status in ("completed", "reused") and record.envelope_path and Path(record.envelope_path).is_file():
                env = json.loads(Path(record.envelope_path).read_text(encoding="utf-8"))
                outputs[task_id] = env.get("outputs", {})
        return outputs

    def run(self, resume: bool = True, force: bool = False, only: Optional[set[str]] = None) -> RunState:
        self.state.status = "running"
        # Each invocation rebuilds the Engineering State chain from the initial state by replaying the
        # proposals of reused tasks and applying those of executed tasks; earlier chains stay on disk.
        initial = self.state.state_versions[0] if self.state.state_versions else None
        chains = len(list((self.run_dir / "state").glob("state-c*-001.json")))
        self._chain = chains + (1 if (self.run_dir / "state" / "state-001.json").exists() else 0)
        if initial is not None:
            self.state.state_versions = [initial]
        self.state.save()
        outputs = self._load_outputs() if resume else {}
        rerun_this_invocation: set[str] = set()
        blocked: set[str] = set()
        any_failed = False
        for task_id in self.graph.order:
            task = self.graph.tasks[task_id]
            record = self.state.tasks.get(task_id) or TaskRecord(task_id=task_id)
            self.state.tasks[task_id] = record
            if only is not None and task_id not in only and not (set(task.depends_on) & rerun_this_invocation):
                if record.status in ("completed", "reused") and task_id in outputs:
                    continue
            upstream_blocked = [d for d in task.depends_on if d in blocked or self.state.tasks.get(d, TaskRecord(d)).status in ("failed", "blocked")]
            if upstream_blocked:
                record.status, record.message = "blocked", f"upstream not completed: {upstream_blocked}"
                blocked.add(task_id)
                self.log(f"[{task_id}] blocked: {record.message}")
                self.state.save()
                continue
            state = self.current_state() or {}
            try:
                inputs = {name: resolve_binding(binding, self.spec, state, self.environment, outputs) for name, binding in task.inputs.items()}
            except KeyError as exc:
                record.status, record.message = "blocked", f"unresolved input: {exc}"
                blocked.add(task_id)
                self.log(f"[{task_id}] blocked: {record.message}")
                self.state.save()
                continue
            adapter = load_adapter(task.adapter)
            blockers = adapter.requirements(self.environment)
            if blockers:
                record.status, record.message = "blocked", "; ".join(blockers)
                blocked.add(task_id)
                self.log(f"[{task_id}] blocked: {record.message}")
                self.state.save()
                continue
            input_hash = envelope_hash(inputs, {"adapter": adapter.id, "version": adapter.version}, {"task": task.to_dict()}, task.parameters)
            upstream_changed = bool(set(task.depends_on) & rerun_this_invocation)
            if (resume and not force and record.status in ("completed", "reused") and record.input_hash == input_hash
                    and not upstream_changed and record.envelope_path and Path(record.envelope_path).is_file()):
                stored = ExecutionEnvelope.from_dict(json.loads(Path(record.envelope_path).read_text(encoding="utf-8")))
                if stored.state_proposal and state:
                    try:
                        state = apply_proposal(state, stored.state_proposal, stored)
                        record.state_version_after = self._commit_state(state, task_id)
                    except StateError as exc:
                        record.status, record.message = "failed", f"replaying stored state proposal failed: {exc}"
                        any_failed = True
                        blocked.add(task_id)
                        self.state.save()
                        continue
                record.status = "reused"
                self.log(f"[{task_id}] reused checkpoint (input hash unchanged)")
                self.state.save()
                continue
            task_dir = self.run_dir / "tasks" / task_id
            task_dir.mkdir(parents=True, exist_ok=True)
            log_path = task_dir / "log.txt"

            def task_log(message: str, _path=log_path, _tid=task_id) -> None:
                stamp = now_iso()
                with open(_path, "a", encoding="utf-8") as handle:
                    handle.write(f"{stamp} {message}\n")
                self.log(f"[{_tid}] {message}")

            record.status, record.started_at, record.attempts = "running", now_iso(), record.attempts + 1
            record.input_hash = input_hash
            self.state.save()
            ctx = TaskContext(task=task, inputs=inputs, spec=self.spec, state=state, state_sha256=state_sha256(state) if state else "",
                              run_dir=self.run_dir, task_dir=task_dir, environment=self.environment,
                              registry_entry=self.registry_entry_for(task.capability), artifacts=self.artifacts,
                              core_dir=self.core_dir, log=task_log, run_id=self.state.run_id)
            try:
                envelope = adapter.execute(ctx)
                envelope.input_hash = input_hash
            except Exception as exc:
                task_log("adapter raised " + traceback.format_exc())
                record.status, record.finished_at, record.message = "failed", now_iso(), f"{type(exc).__name__}: {exc}"
                any_failed = True
                if not task.optional:
                    blocked.add(task_id)
                self.state.save()
                continue
            envelope_path = task_dir / "envelope.json"
            envelope_path.write_text(json.dumps(envelope.to_dict(), indent=2, sort_keys=True, default=str), encoding="utf-8")
            record.envelope_path = str(envelope_path)
            record.finished_at = now_iso()
            if envelope.status == "completed" and envelope.ok:
                if envelope.state_proposal and state:
                    try:
                        new_state = apply_proposal(state, envelope.state_proposal, envelope)
                        version = self._commit_state(new_state, task_id)
                        record.state_version_after = version
                        task_log(f"Engineering State version {version} committed")
                    except StateError as exc:
                        record.status, record.message = "failed", f"state proposal rejected: {exc}"
                        task_log(record.message)
                        any_failed = True
                        blocked.add(task_id)
                        self.state.save()
                        continue
                record.status, record.message = "completed", ""
                outputs[task_id] = envelope.outputs
                rerun_this_invocation.add(task_id)
                task_log("completed")
            elif envelope.status == "blocked":
                record.status = "blocked"
                record.message = "; ".join(d.message for d in envelope.diagnostics if d.severity == "error") or "blocked by adapter"
                blocked.add(task_id)
                task_log("blocked: " + record.message)
            else:
                record.status = "failed"
                record.message = "; ".join(d.message for d in envelope.diagnostics if d.severity == "error") or envelope.status
                any_failed = True
                blocked.add(task_id)
                task_log("failed: " + record.message)
            self.state.save()
        if any_failed:
            self.state.status = "failed"
        elif blocked:
            self.state.status = "completed_with_blocked"
        else:
            self.state.status = "completed"
        self.state.save()
        return self.state
