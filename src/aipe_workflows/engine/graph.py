"""Versioned machine-readable workflow definition and task graph.

A workflow definition (``workflow.yaml``) declares::

    schema_version: 0.1.0
    id: aipe.workflow.converter-dab
    name: ...
    description: ...
    engineering_state: { schema_version: 0.1.0 }
    tasks:
      - id: analytic-sps
        capability: converter-concept-calculation     # Registry capability string
        adapter: aipe_workflows.adapters.design_agent:AnalyticSpsTask
        depends_on: []
        inputs:  { specification: $spec }             # typed input bindings
        outputs: [analytic_summary]                   # names of produced outputs
        gate: analytical                              # verification category produced
        optional: false
        tools: []                                     # external tools required (ids)

Bindings use ``$spec`` for the workflow specification, ``$state`` for the
current Engineering State, ``$task.<task-id>.<output>`` for one upstream
output and ``$task.<task-id>`` for the complete output dictionary of a task.
The graph is validated for unknown dependencies and cycles at load time.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional, Union

import yaml

SCHEMA_VERSION = "0.1.0"
_ID = re.compile(r"^[a-z][a-z0-9-]*$")
_REF = re.compile(r"^\$(spec|state|env|task\.[a-z][a-z0-9-]*(\.[a-z][a-z0-9_-]*)?)(\.[A-Za-z0-9_.-]+)?$")


class WorkflowDefinitionError(ValueError):
    """The workflow definition is not usable."""


@dataclass
class TaskSpec:
    id: str
    capability: str
    adapter: str
    depends_on: list[str] = field(default_factory=list)
    inputs: dict[str, Any] = field(default_factory=dict)
    outputs: list[str] = field(default_factory=list)
    gate: str = "software"
    optional: bool = False
    tools: list[str] = field(default_factory=list)
    description: str = ""
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "capability": self.capability, "adapter": self.adapter, "depends_on": list(self.depends_on),
                "inputs": dict(self.inputs), "outputs": list(self.outputs), "gate": self.gate, "optional": self.optional,
                "tools": list(self.tools), "description": self.description, "parameters": dict(self.parameters)}


@dataclass
class WorkflowDefinition:
    id: str
    name: str
    description: str
    tasks: list[TaskSpec]
    schema_version: str = SCHEMA_VERSION
    engineering_state_version: str = "0.1.0"
    source_path: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"schema_version": self.schema_version, "id": self.id, "name": self.name, "description": self.description,
                "engineering_state": {"schema_version": self.engineering_state_version},
                "tasks": [t.to_dict() for t in self.tasks], "metadata": dict(self.metadata)}


GATES = ("analytical", "software", "circuit_simulation", "field_simulation", "cad_pcb", "engineering_review",
         "experimental", "hardware_qualification")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise WorkflowDefinitionError(message)


_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "workflow-definition.schema.json"


def validate_definition_schema(data: dict) -> list[str]:
    """Validate a raw workflow definition against the versioned JSON Schema (draft 2020-12)."""
    import json

    from jsonschema import Draft202012Validator

    schema = json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return [f"{'/'.join(str(x) for x in e.absolute_path) or '$'}: {e.message}"
            for e in sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.absolute_path))]


def parse_workflow_definition(data: dict, source_path: Optional[str] = None) -> WorkflowDefinition:
    _require(isinstance(data, dict), "workflow definition must be a mapping")
    schema_errors = validate_definition_schema(data)
    _require(not schema_errors, "workflow definition schema violation: " + "; ".join(schema_errors[:5]))
    _require(data.get("schema_version") == SCHEMA_VERSION, f"unsupported workflow schema_version {data.get('schema_version')!r}; expected {SCHEMA_VERSION}")
    for key in ("id", "name", "description", "tasks"):
        _require(key in data, f"workflow definition missing {key!r}")
    _require(re.fullmatch(r"^[a-z][a-z0-9-]*(\.[a-z][a-z0-9-]*)+$", data["id"]) is not None, f"invalid workflow id {data['id']!r}")
    state = data.get("engineering_state", {"schema_version": "0.1.0"})
    _require(isinstance(state, dict) and state.get("schema_version") == "0.1.0", "engineering_state.schema_version must be 0.1.0")
    tasks: list[TaskSpec] = []
    seen = set()
    for raw in data["tasks"]:
        _require(isinstance(raw, dict), "each task must be a mapping")
        for key in ("id", "capability", "adapter"):
            _require(key in raw, f"task missing {key!r}: {raw}")
        _require(_ID.fullmatch(raw["id"]) is not None, f"invalid task id {raw['id']!r}")
        _require(raw["id"] not in seen, f"duplicate task id {raw['id']!r}")
        seen.add(raw["id"])
        _require(":" in raw["adapter"], f"adapter must be module:Class for task {raw['id']}")
        gate = raw.get("gate", "software")
        _require(gate in GATES, f"task {raw['id']}: unknown gate {gate!r}; allowed {GATES}")
        inputs = raw.get("inputs", {}) or {}
        for name, binding in inputs.items():
            if isinstance(binding, str) and binding.startswith("$"):
                _require(_REF.fullmatch(binding) is not None, f"task {raw['id']}: invalid binding {binding!r} for input {name!r}")
        tasks.append(TaskSpec(id=raw["id"], capability=raw["capability"], adapter=raw["adapter"],
                              depends_on=list(raw.get("depends_on", []) or []), inputs=dict(inputs),
                              outputs=list(raw.get("outputs", []) or []), gate=gate, optional=bool(raw.get("optional", False)),
                              tools=list(raw.get("tools", []) or []), description=raw.get("description", ""),
                              parameters=dict(raw.get("parameters", {}) or {})))
    definition = WorkflowDefinition(id=data["id"], name=data["name"], description=data["description"], tasks=tasks,
                                    engineering_state_version=state["schema_version"], source_path=source_path,
                                    metadata=dict(data.get("metadata", {}) or {}))
    TaskGraph(definition)  # validates dependencies and acyclicity
    return definition


def load_workflow_definition(path: Union[str, Path]) -> WorkflowDefinition:
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return parse_workflow_definition(data, str(path))


class TaskGraph:
    """Dependency graph with deterministic topological order."""

    def __init__(self, definition: WorkflowDefinition):
        self.definition = definition
        self.tasks = {t.id: t for t in definition.tasks}
        for task in definition.tasks:
            for dep in task.depends_on:
                _require(dep in self.tasks, f"task {task.id} depends on unknown task {dep!r}")
            for name, binding in task.inputs.items():
                if isinstance(binding, str) and binding.startswith("$task."):
                    ref_task = binding.split(".")[1]
                    _require(ref_task in self.tasks, f"task {task.id}: input {name} references unknown task {ref_task!r}")
                    _require(ref_task in task.depends_on, f"task {task.id}: input {name} references {ref_task} which is not in depends_on")
        self.order = self._topological_order()

    def _topological_order(self) -> list[str]:
        indegree = {tid: len(set(t.depends_on)) for tid, t in self.tasks.items()}
        dependants: dict[str, list[str]] = {tid: [] for tid in self.tasks}
        for tid, t in self.tasks.items():
            for dep in set(t.depends_on):
                dependants[dep].append(tid)
        ready = sorted(tid for tid, d in indegree.items() if d == 0)
        order: list[str] = []
        while ready:
            current = ready.pop(0)
            order.append(current)
            for nxt in sorted(dependants[current]):
                indegree[nxt] -= 1
                if indegree[nxt] == 0:
                    ready.append(nxt)
                    ready.sort()
        if len(order) != len(self.tasks):
            remaining = sorted(set(self.tasks) - set(order))
            raise WorkflowDefinitionError(f"dependency cycle among tasks: {remaining}")
        return order

    def downstream(self, task_id: str) -> set[str]:
        """All tasks that transitively depend on ``task_id``."""
        result: set[str] = set()
        frontier = [task_id]
        while frontier:
            current = frontier.pop()
            for tid, t in self.tasks.items():
                if current in t.depends_on and tid not in result:
                    result.add(tid)
                    frontier.append(tid)
        return result

    def upstream(self, task_id: str) -> set[str]:
        result: set[str] = set()
        frontier = [task_id]
        while frontier:
            current = frontier.pop()
            for dep in self.tasks[current].depends_on:
                if dep not in result:
                    result.add(dep)
                    frontier.append(dep)
        return result

    def levels(self) -> list[list[str]]:
        """Tasks grouped by dependency depth (tasks within a level are independent)."""
        depth: dict[str, int] = {}
        for tid in self.order:
            deps = self.tasks[tid].depends_on
            depth[tid] = 1 + max((depth[d] for d in deps), default=-1)
        groups: dict[int, list[str]] = {}
        for tid, d in depth.items():
            groups.setdefault(d, []).append(tid)
        return [sorted(groups[d]) for d in sorted(groups)]
