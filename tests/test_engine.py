"""Unit tests for the workflow engine: graph, bindings, envelope, state proposals, checkpoints."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from aipe_workflows.engine.envelope import ExecutionEnvelope, envelope_hash, now_iso
from aipe_workflows.engine.graph import TaskGraph, WorkflowDefinitionError, parse_workflow_definition
from aipe_workflows.engine.runner import TaskAdapter, TaskContext, WorkflowRunner, resolve_binding
from aipe_workflows.engineering_state.state import StateError, apply_proposal, build_initial_state, find_core_dir, state_sha256, validate_state

ROOT = Path(__file__).resolve().parents[1]
SPEC = {
    "schema_version": "0.1.0", "workflow": "aipe.workflow.test", "state_id": "aipe.test.state",
    "project": {"id": "project.test", "name": "Test", "purpose": "example"},
    "requirements": {"nominal_power_W": 10000, "input_voltage_V": 800, "output_voltage_V": 400, "switching_frequency_Hz": 100000},
    "converter": {"turns_ratio_np_ns": 2.0, "series_inductance_H": 35e-6, "phase_shift_deg": 22.5},
    "environment": {"ambient_temperature_K": 313.15},
    "constraints": [{"id": "input-range", "description": "700 to 800 V", "basis": "source: TIDUES0"}],
}


def definition(tasks):
    return parse_workflow_definition({"schema_version": "0.1.0", "id": "aipe.workflow.test", "name": "t", "description": "d",
                                      "engineering_state": {"schema_version": "0.1.0"}, "tasks": tasks})


def task(tid, deps=(), **extra):
    base = {"id": tid, "capability": "cap-" + tid, "adapter": "tests.test_engine:EchoAdapter", "depends_on": list(deps), "gate": "software"}
    base.update(extra)
    return base


def _calls(run_dir: Path) -> list[str]:
    """Execution log shared between the test and the adapter (the engine imports adapters by module path,
    which may yield a second copy of this module, so class attributes cannot be used as a shared record)."""
    log = run_dir / "calls.log"
    return log.read_text(encoding="utf-8").split() if log.is_file() else []


class EchoAdapter(TaskAdapter):
    id = "test.echo"
    version = "1.0"

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:
        with open(ctx.run_dir / "calls.log", "a", encoding="utf-8") as handle:
            handle.write(ctx.task.id + "\n")
        value = ctx.inputs.get("value", 0)
        return ExecutionEnvelope(task_id=ctx.task.id, task_version="1", capability_id="aipe.test", tool={"id": "tool.echo", "version": "1"},
                                 status="completed", started_at=now_iso(), finished_at=now_iso(), source_state_id=ctx.state.get("id", ""),
                                 source_state_sha256=ctx.state_sha256, inputs=dict(ctx.inputs), outputs={"value": value + 1, "doubled": 2 * (value + 1)},
                                 gate="software")


class FailingAdapter(TaskAdapter):
    id = "test.fail"
    version = "1.0"

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:
        raise RuntimeError("boom")


class BlockedAdapter(TaskAdapter):
    id = "test.blocked"
    version = "1.0"

    def requirements(self, environment):
        return ["tool missing"]

    def execute(self, ctx):  # pragma: no cover
        raise AssertionError("must not run")


# ------------------------------------------------------------------ graph

def test_topological_order_and_levels():
    d = definition([task("c", ["a", "b"]), task("a"), task("b", ["a"])])
    g = TaskGraph(d)
    assert g.order == ["a", "b", "c"]
    assert g.levels() == [["a"], ["b"], ["c"]]
    assert g.downstream("a") == {"b", "c"} and g.upstream("c") == {"a", "b"}


def test_cycle_unknown_dependency_and_binding_errors():
    with pytest.raises(WorkflowDefinitionError, match="cycle"):
        definition([task("a", ["b"]), task("b", ["a"])])
    with pytest.raises(WorkflowDefinitionError, match="unknown task"):
        definition([task("a", ["zzz"])])
    with pytest.raises(WorkflowDefinitionError, match="not in depends_on"):
        definition([task("a"), task("b", inputs={"x": "$task.a.value"})])
    with pytest.raises(WorkflowDefinitionError, match="invalid binding|schema violation"):
        definition([task("a", inputs={"x": "$nonsense.y"})])
    with pytest.raises(WorkflowDefinitionError, match="unknown gate|schema violation"):
        definition([task("a", gate="magic")])
    with pytest.raises(WorkflowDefinitionError, match="schema_version"):
        parse_workflow_definition({"schema_version": "9", "id": "aipe.x", "name": "n", "description": "d", "tasks": []})


def test_resolve_bindings():
    outputs = {"a": {"value": 3, "nested": {"k": [10, 20]}}}
    assert resolve_binding("$spec.requirements.input_voltage_V", SPEC, {}, {}, outputs) == 800
    assert resolve_binding("$task.a.value", SPEC, {}, {}, outputs) == 3
    assert resolve_binding("$task.a", SPEC, {}, {}, outputs) == outputs["a"]
    assert resolve_binding("$task.a.nested.k.1", SPEC, {}, {}, outputs) == 20
    assert resolve_binding(42, SPEC, {}, {}, outputs) == 42
    with pytest.raises(KeyError):
        resolve_binding("$task.a.missing", SPEC, {}, {}, outputs)


# --------------------------------------------------------------- envelope

def test_envelope_hash_and_status():
    h1 = envelope_hash({"a": 1}, {"m": 1}, {"t": 1}, {})
    assert h1 == envelope_hash({"a": 1}, {"m": 1}, {"t": 1}, {}) and h1 != envelope_hash({"a": 2}, {"m": 1}, {"t": 1}, {})
    with pytest.raises(ValueError):
        ExecutionEnvelope(task_id="t", task_version="1", capability_id="c", tool={}, status="weird", started_at="", finished_at="",
                          source_state_id="", source_state_sha256="")
    env = ExecutionEnvelope(task_id="t", task_version="1", capability_id="c", tool={}, status="completed", started_at="", finished_at="",
                            source_state_id="", source_state_sha256="")
    assert env.ok
    env.add_error("x", "bad")
    assert not env.ok and ExecutionEnvelope.from_dict(env.to_dict()).diagnostics[0].code == "x"


# ------------------------------------------------------------------ state

@pytest.fixture
def core_dir():
    core = find_core_dir(start=ROOT)
    if core is None:
        pytest.skip("AIPE-Core checkout not available")
    return core


def test_initial_state_is_core_valid(core_dir):
    state = build_initial_state(SPEC, "2026-10-21T12:00:00Z")
    assert validate_state(state, core_dir) == []
    assert state["requirements"]["constraints"][0]["evidence_refs"] == ["evidence.specification", "evidence.reference-designs"]
    assert state["thermal"]["ambient_temperature"] == {"value": 313.15, "unit": "K"}


def test_apply_proposal_rules(core_dir):
    state = build_initial_state(SPEC, "2026-10-21T12:00:00Z")
    evidence = {"id": "evidence.test-analytic", "kind": "analytical", "description": "d",
                "source": {"type": "repository", "reference": "https://example.com/x"},
                "provenance": {"created_at": "2026-10-21T12:00:00Z", "activity": "a", "inputs": ["evidence.specification"],
                               "tool": {"id": "tool.test", "version": "1"}}, "artifacts": [], "review_status": "unreviewed"}
    proposal = {"evidence": [evidence],
                "set": [{"path": "control", "value": {"strategy": "sps", "phase_shift": {"value": 0.39, "unit": "rad"}, "evidence_refs": ["evidence.test-analytic"]}}],
                "append": [{"path": "magnetics", "value": {"id": "magnetics.l", "role": "r", "kind": "inductor", "design_status": "candidate",
                                                            "inductance": {"value": 35e-6, "unit": "H"}, "evidence_refs": ["evidence.test-analytic"]}}],
                "extensions": {"aipe.test": {"k": 1}}, "status": {"architecture_stage": "candidate"}}
    new = apply_proposal(state, proposal)
    assert validate_state(new, core_dir) == []
    assert len(state["evidence"]) == 2 and len(new["evidence"]) == 3  # input untouched, evidence preserved
    assert new["architecture"]["stage"] == "candidate" and new["extensions"]["aipe.test"] == {"k": 1}
    with pytest.raises(StateError, match="already exists"):
        apply_proposal(new, {"evidence": [evidence]})
    with pytest.raises(StateError, match="unknown evidence"):
        apply_proposal(state, {"set": [{"path": "control", "value": {"evidence_refs": ["evidence.nope"]}}]})
    with pytest.raises(StateError, match="namespaced"):
        apply_proposal(state, {"extensions": {"plain": {}}})
    with pytest.raises(StateError, match="already exists"):
        apply_proposal(new, {"append": [{"path": "magnetics", "value": {"id": "magnetics.l", "role": "r", "kind": "inductor", "design_status": "candidate", "evidence_refs": ["evidence.test-analytic"]}}]})
    assert state_sha256(state) != state_sha256(new)


# ----------------------------------------------------------------- runner

def _runner(tmp_path, tasks, env=None):
    d = definition(tasks)
    return WorkflowRunner(d, SPEC, tmp_path / "run", env or {"tools": {}}, registry={"capabilities": []}, core_dir=None,
                          initial_state={"id": "aipe.test.state", "evidence": []})


def test_runner_executes_in_order_reuses_checkpoints_and_reruns_downstream(tmp_path):
    tasks = [task("a", inputs={"value": "$spec.converter.turns_ratio_np_ns"}), task("b", ["a"], inputs={"value": "$task.a.value"}),
             task("c", ["b"], inputs={"value": "$task.b.doubled"})]
    runner = _runner(tmp_path, tasks)
    run_dir = tmp_path / "run"
    state = runner.run()
    assert state.status == "completed" and _calls(run_dir) == ["a", "b", "c"]
    outputs = json.loads(Path(state.tasks["c"].envelope_path).read_text())["outputs"]
    assert outputs["value"] == 2 * (2.0 + 1 + 1) + 1
    # Second run: everything reused.
    (run_dir / "calls.log").unlink()
    runner2 = WorkflowRunner(runner.definition, SPEC, run_dir, {"tools": {}}, registry={"capabilities": []})
    state2 = runner2.run()
    assert _calls(run_dir) == [] and all(r.status == "reused" for r in state2.tasks.values())
    # Force re-run of b: c must re-run too (stale downstream results are never reused).
    runner3 = WorkflowRunner(runner.definition, SPEC, run_dir, {"tools": {}}, registry={"capabilities": []})
    runner3.state.tasks["b"].input_hash = "changed"
    state3 = runner3.run()
    assert _calls(run_dir) == ["b", "c"] and state3.tasks["a"].status == "reused"
    assert (tmp_path / "run" / "run.json").is_file() and (tmp_path / "run" / "tasks" / "c" / "envelope.json").is_file()


def test_failed_task_blocks_downstream_and_blocked_requirements(tmp_path):
    tasks = [task("a"), {**task("f", ["a"]), "adapter": "tests.test_engine:FailingAdapter"}, task("c", ["f"]),
             {**task("blk"), "adapter": "tests.test_engine:BlockedAdapter"}, task("d", ["blk"])]
    state = _runner(tmp_path, tasks).run()
    assert state.status == "failed"
    assert state.tasks["f"].status == "failed" and "boom" in state.tasks["f"].message
    assert state.tasks["c"].status == "blocked" and state.tasks["blk"].status == "blocked" and state.tasks["d"].status == "blocked"
    assert state.tasks["a"].status == "completed"


def test_plan_reports_blockers_and_registry(tmp_path):
    d = definition([{**task("blk"), "adapter": "tests.test_engine:BlockedAdapter", "tools": ["ngspice"]}])
    runner = WorkflowRunner(d, SPEC, tmp_path / "run", {"tools": {"ngspice": {"found": False}}},
                            registry={"capabilities": [{"id": "aipe.x", "capabilities": ["cap-blk"], "maturity": "prototype", "status": "active",
                                                        "validation": {"status": "tested"}, "repository": "https://github.com/x/y"}]})
    plan = runner.plan()
    t = plan["tasks"][0]
    assert t["registry"]["id"] == "aipe.x" and not t["runnable"]
    assert any("tool missing" in b for b in t["blockers"]) and any("ngspice" in b for b in t["blockers"])


def test_workflow_schema_and_dab_extension_contract():
    from aipe_workflows.engine.graph import validate_definition_schema
    from aipe_workflows.engineering_state.state import validate_dab_extension
    good = {"schema_version": "0.1.0", "id": "aipe.workflow.x", "name": "n", "description": "d",
            "tasks": [{"id": "a", "capability": "cap-a", "adapter": "m:C"}]}
    assert validate_definition_schema(good) == []
    bad = dict(good, tasks=[{"id": "A", "capability": "cap", "adapter": "noclass"}])
    assert validate_definition_schema(bad)
    with pytest.raises(WorkflowDefinitionError, match="schema violation"):
        parse_workflow_definition(bad)
    assert validate_dab_extension({"analytic_sps": {"model": "m", "inputs": {}, "derived": {}, "assumptions": []}}) == []
    assert validate_dab_extension({"simulation_x": {"run_dir": "r"}})  # missing required keys
    assert validate_dab_extension({"unexpected": {}})


def test_shipped_dab_workflow_and_results_satisfy_the_contracts():
    from aipe_workflows.engine.graph import load_workflow_definition
    from aipe_workflows.engineering_state.state import validate_dab_extension
    definition = load_workflow_definition(ROOT / "workflows" / "converter_dab" / "workflow.yaml")
    assert [t.id for t in definition.tasks][:3] == ["requirements", "analytic-sps", "circuit-sim-level1"]
    final = ROOT / "examples" / "dab-10kw" / "results" / "engineering-state-final.json"
    if final.is_file():
        state = json.loads(final.read_text(encoding="utf-8"))
        assert validate_dab_extension(state["extensions"]["aipe.workflows.dab"]) == []


def test_iteration_helpers_apply_changes_and_parse():
    from aipe_workflows.optimisation.iterate import apply_changes, parse_change
    spec = {"converter": {"turns_ratio_np_ns": 2.0, "phase_shift_deg": 22.5}, "requirements": {"nominal_power_W": 10000}}
    changes = dict(parse_change(c) for c in ["converter.turns_ratio_np_ns=2.1", "converter.phase_shift_deg=null", "requirements.note=hello"])
    new = apply_changes(spec, changes)
    assert new["converter"] == {"turns_ratio_np_ns": 2.1}  # null removes the key
    assert new["requirements"]["note"] == "hello" and spec["converter"]["phase_shift_deg"] == 22.5  # input untouched
    with pytest.raises(ValueError):
        parse_change("no-equals-sign")


def test_iteration_reruns_changed_inputs_and_records_decision(tmp_path):
    from aipe_workflows.optimisation.iterate import iterate_run
    tasks = [task("a", inputs={"value": "$spec.converter.turns_ratio_np_ns"}), task("b", ["a"], inputs={"value": "$task.a.value"})]
    runner = _runner(tmp_path, tasks)
    runner.run()
    parent = tmp_path / "run"

    def factory(spec, child_dir, child_id):
        child = WorkflowRunner(runner.definition, spec, child_dir, {"tools": {}}, registry={"capabilities": []}, run_id=child_id)
        return child.run()

    def decide(state, comparison, spec):
        return ("accepted" if state.status == "completed" else "rejected"), ["test rule"]

    record = iterate_run(parent, {"converter.turns_ratio_np_ns": 3.0}, "test change", factory, decide=decide)
    assert record.status == "accepted" and set(record.tasks_rerun) == {"a", "b"} and record.tasks_reused == []
    child = Path(record.child_run)
    assert json.loads((child / "specification.json").read_text())["converter"]["turns_ratio_np_ns"] == 3.0
    assert (child / "iteration.json").is_file() and (parent / "iterations.json").is_file()
    outputs = json.loads((child / "tasks" / "b" / "envelope.json").read_text())["outputs"]
    assert outputs["value"] == 3.0 + 1 + 1
    # An unchanged iteration reuses every checkpoint.
    record2 = iterate_run(parent, {}, "no change", factory, decide=decide)
    assert record2.tasks_rerun == [] and set(record2.tasks_reused) == {"a", "b"}
