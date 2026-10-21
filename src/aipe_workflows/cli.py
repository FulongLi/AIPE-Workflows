"""``aipe-workflows`` command line.

    aipe-workflows doctor [--qualify] [--json]
    aipe-workflows capabilities [--registry PATH] [--checkouts DIR]
    aipe-workflows plan SPEC [--workflow PATH] [--run-dir DIR]
    aipe-workflows run SPEC [--workflow PATH] [--run-dir DIR] [--resume] [--force] [--only TASK ...]
    aipe-workflows status RUN
    aipe-workflows verify RUN
    aipe-workflows iterate RUN --set converter.turns_ratio_np_ns=2.1 converter.phase_shift_deg=null --reason "..."
    aipe-workflows report RUN [--out DIR]

``RUN`` is a run directory or a run id below ``./runs``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Optional

import yaml

from . import __version__
from .capability_discovery.registry import discover_capabilities
from .engine.envelope import now_iso
from .engine.graph import load_workflow_definition
from .engine.runner import RunState, WorkflowRunner
from .engineering_state.state import build_initial_state, find_core_dir
from .environment.doctor import inspect_environment, write_manifest
from .reporting.report import build_report
from .verification.gates import build_ledger

PACKAGE_ROOT = Path(__file__).resolve().parents[2]


def _load_spec(path: str) -> dict:
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text) if path.lower().endswith((".yaml", ".yml")) else json.loads(text)
    if not isinstance(data, dict) or data.get("schema_version") != "0.1.0":
        raise SystemExit("specification must be a mapping with schema_version 0.1.0")
    return data


def _workflow_path(spec: dict, explicit: Optional[str]) -> Path:
    if explicit:
        return Path(explicit)
    workflow_id = spec.get("workflow", "")
    candidates = [PACKAGE_ROOT / "workflows" / workflow_id.split(".")[-1].replace("-", "_") / "workflow.yaml",
                  PACKAGE_ROOT / "workflows" / "converter_dab" / "workflow.yaml"]
    for candidate in candidates:
        if candidate.is_file():
            data = yaml.safe_load(candidate.read_text(encoding="utf-8"))
            if data.get("id") == workflow_id or not workflow_id:
                return candidate
    raise SystemExit(f"no workflow definition found for {workflow_id!r}; pass --workflow")


def _resolve_run(run: str) -> Path:
    path = Path(run)
    if path.is_dir():
        return path
    candidate = Path("runs") / run
    if candidate.is_dir():
        return candidate
    raise SystemExit(f"run directory not found: {run}")


def _run_id(spec: dict, spec_path: str) -> str:
    digest = hashlib.sha256(json.dumps(spec, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:6]
    stamp = now_iso().replace(":", "").replace("-", "")[:15]
    return f"{Path(spec_path).stem}-{stamp}-{digest}"


def cmd_doctor(args: argparse.Namespace) -> int:
    manifest = inspect_environment(workspace_root=args.workspace, qualify=args.qualify, qualification_dir=args.qualification_dir)
    out = Path(args.out) if args.out else Path("runs") / "environment" / f"environment-{now_iso().replace(':', '')}.json"
    write_manifest(manifest, out)
    if args.json:
        print(json.dumps(manifest.to_dict(), indent=2, default=str))
    else:
        print(f"AIPE-Workflows {__version__} doctor — {manifest.platform['system']} {manifest.platform['release']} / Python {manifest.python['version']}")
        for tid, tool in manifest.tools.items():
            status = "found" if tool["found"] else "missing"
            qual = "" if tool["qualified"] is None else (" qualified" if tool["qualified"] else " QUALIFICATION FAILED")
            print(f"  {tid:12s} {status:8s} {tool.get('version') or '':14s}{qual}  {tool.get('path') or tool['install_hint']}")
        print("  python packages: " + ", ".join(f"{k}={v}" for k, v in manifest.python_packages.items()))
        print(f"  manifest written to {out}")
    return 0


def cmd_capabilities(args: argparse.Namespace) -> int:
    discovered = discover_capabilities(args.registry, args.checkouts)
    if args.json:
        print(json.dumps(discovered, indent=2, default=str))
        return 0
    print(f"{len(discovered['capabilities'])} capability manifests (registry index: {discovered['registry_index']})")
    for manifest in discovered["capabilities"]:
        print(f"  {manifest['id']:32s} {manifest.get('type', ''):16s} {manifest.get('maturity', ''):10s} validation={manifest.get('validation', {}).get('status', '')}")
        print(f"      capabilities: {', '.join(manifest.get('capabilities', []))}")
    return 0


def _make_runner(args: argparse.Namespace, spec: dict, run_dir: Path, run_id: str) -> WorkflowRunner:
    definition = load_workflow_definition(_workflow_path(spec, args.workflow))
    env_path = run_dir / "environment.json"
    if env_path.is_file() and (run_dir / "run.json").is_file():
        environment = json.loads(env_path.read_text(encoding="utf-8"))
    else:
        environment = inspect_environment(workspace_root=args.workspace, qualify=not args.no_qualify).to_dict()
    registry = discover_capabilities(args.registry, args.checkouts)
    core_dir = find_core_dir(args.core)
    initial_state = None if (run_dir / "run.json").is_file() else build_initial_state(spec, now_iso())
    return WorkflowRunner(definition, spec, run_dir, environment, registry=registry, core_dir=core_dir, run_id=run_id,
                          initial_state=initial_state, log=lambda m: print(m, file=sys.stderr))


def cmd_plan(args: argparse.Namespace) -> int:
    spec = _load_spec(args.spec)
    run_id = args.run_id or _run_id(spec, args.spec)
    run_dir = Path(args.run_dir) if args.run_dir else Path("runs") / run_id
    runner = _make_runner(args, spec, run_dir, run_id)
    plan = runner.plan()
    print(json.dumps(plan, indent=2, default=str) if args.json else _plan_text(plan))
    return 0 if all(t["runnable"] for t in plan["tasks"] if not t["optional"]) else 2


def _plan_text(plan: dict) -> str:
    lines = [f"Plan for {plan['workflow']} (run {plan['run_id']})"]
    for level, tasks in enumerate(plan["levels"]):
        lines.append(f"  level {level}: {', '.join(tasks)}")
    for t in plan["tasks"]:
        reg = t["registry"]
        reg_text = f"{reg['id']} ({reg['maturity']}, validation {reg['validation']})" if reg else "NOT REGISTERED"
        lines.append(f"  - {t['id']:24s} gate={t['gate']:18s} capability={t['capability']} -> {reg_text}")
        if t["blockers"]:
            for b in t["blockers"]:
                lines.append(f"      BLOCKER: {b}")
    return "\n".join(lines)


def cmd_run(args: argparse.Namespace) -> int:
    spec = _load_spec(args.spec)
    run_id = args.run_id or _run_id(spec, args.spec)
    run_dir = Path(args.run_dir) if args.run_dir else Path("runs") / run_id
    runner = _make_runner(args, spec, run_dir, run_id)
    runner.plan()
    state = runner.run(resume=not args.no_resume, force=args.force, only=set(args.only) if args.only else None)
    build_ledger(run_dir)
    print(json.dumps({"run_id": state.run_id, "run_dir": str(run_dir), "status": state.status,
                      "tasks": {k: v.status for k, v in state.tasks.items()}, "state_versions": len(state.state_versions)}, indent=2))
    return 0 if state.status == "completed" else (2 if state.status == "completed_with_blocked" else 1)


def cmd_status(args: argparse.Namespace) -> int:
    run_dir = _resolve_run(args.run)
    state = RunState.load(run_dir)
    print(json.dumps({"run_id": state.run_id, "workflow": state.workflow_id, "status": state.status, "created_at": state.created_at,
                      "updated_at": state.updated_at, "tasks": {k: v.to_dict() for k, v in state.tasks.items()},
                      "state_versions": state.state_versions, "messages": state.messages}, indent=2, default=str))
    return 0


def cmd_verify(args: argparse.Namespace) -> int:
    run_dir = _resolve_run(args.run)
    ledger = build_ledger(run_dir)
    from .artifacts.store import ArtifactStore

    problems = ArtifactStore(run_dir / "artifacts").verify()
    core_dir = find_core_dir(args.core)
    state_errors = []
    state = RunState.load(run_dir)
    if core_dir and state.current_state_path:
        from .engineering_state.state import load_state, validate_state

        state_errors = validate_state(load_state(state.current_state_path), core_dir)
    result = {"run_id": ledger.run_id, "gates": {g: s.status for g, s in ledger.gates.items()}, "artifact_problems": problems,
              "engineering_state_errors": state_errors, "core_dir": str(core_dir) if core_dir else None}
    print(json.dumps(result, indent=2))
    return 0 if not problems and not state_errors else 1


def _iteration_run_factory(args: argparse.Namespace):
    """Child-run factory shared by `iterate` and `reconcile --apply`."""

    def run_factory(spec, child_dir, child_id):
        definition = load_workflow_definition(_workflow_path(spec, args.workflow))
        environment = json.loads((child_dir / "environment.json").read_text(encoding="utf-8"))
        registry = discover_capabilities(args.registry, args.checkouts)
        runner = WorkflowRunner(definition, spec, child_dir, environment, registry=registry, core_dir=find_core_dir(args.core),
                                run_id=child_id, log=lambda m: print(m, file=sys.stderr))
        runner.plan()
        state = runner.run(resume=True)
        build_ledger(child_dir)
        return state

    return run_factory


def cmd_iterate(args: argparse.Namespace) -> int:
    from .optimisation.iterate import iterate_run, parse_change

    parent = _resolve_run(args.run)
    changes = dict(parse_change(c) for c in args.set)
    record = iterate_run(parent, changes, args.reason, _iteration_run_factory(args), child_run_id=args.child_id)
    print(json.dumps(record.to_dict(), indent=2, default=str))
    return 0 if record.status == "accepted" else (2 if record.status == "rejected" else 1)


def cmd_reconcile(args: argparse.Namespace) -> int:
    """Compare the circuit model's converter parameters with the magnetics/FEM results; optionally re-run through iterate."""
    from .optimisation.reconcile import reconcile, reconcile_and_iterate

    run_dir = _resolve_run(args.run)
    if args.apply:
        result, record = reconcile_and_iterate(run_dir, _iteration_run_factory(args), tolerance=args.tolerance, prefer=args.prefer,
                                               child_run_id=args.child_id)
        print(json.dumps(result, indent=2, default=str))
        if record is None:
            return 0
        return 0 if record.status == "accepted" else (2 if record.status == "rejected" else 1)
    result = reconcile(run_dir, tolerance=args.tolerance, prefer=args.prefer)
    print(json.dumps(result, indent=2, default=str))
    return 0 if result["consistent"] else 3


def cmd_report(args: argparse.Namespace) -> int:
    run_dir = _resolve_run(args.run)
    paths = build_report(run_dir, args.out)
    print(json.dumps(paths, indent=2))
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="aipe-workflows", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--version", action="version", version=f"aipe-workflows {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> None:
        p.add_argument("--workspace", help="workspace root holding tools/ and repos/ (default: search upwards from cwd)")
        p.add_argument("--registry", help="path to AIPE-Registry generated/aipe.json")
        p.add_argument("--checkouts", help="directory with sibling AIPE repository checkouts (their aipe.yaml override the index)")
        p.add_argument("--core", help="path to an AIPE-Core checkout (schemas + validator)")
        p.add_argument("--workflow", help="workflow.yaml path (default: resolved from the specification's workflow id)")
        p.add_argument("--run-dir", help="run directory (default runs/<run-id>)")
        p.add_argument("--run-id")
        p.add_argument("--no-qualify", action="store_true", help="skip tool qualification tests when inspecting the environment")
        p.add_argument("--json", action="store_true")

    p = sub.add_parser("doctor", help="detect and qualify engineering software")
    p.add_argument("--qualify", action="store_true", help="run minimal numerical tests on every found tool")
    p.add_argument("--workspace")
    p.add_argument("--qualification-dir")
    p.add_argument("--out")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_doctor)
    p = sub.add_parser("capabilities", help="list discovered specialist capabilities")
    p.add_argument("--registry")
    p.add_argument("--checkouts")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_capabilities)
    p = sub.add_parser("plan", help="resolve the task graph, capabilities and blockers without executing")
    p.add_argument("spec")
    common(p)
    p.set_defaults(func=cmd_plan)
    p = sub.add_parser("run", help="execute the workflow with checkpoints")
    p.add_argument("spec")
    common(p)
    p.add_argument("--no-resume", action="store_true", help="ignore existing checkpoints in the run directory")
    p.add_argument("--force", action="store_true", help="re-run every task even if inputs are unchanged")
    p.add_argument("--only", nargs="*", help="run only these tasks (and whatever they invalidate downstream)")
    p.set_defaults(func=cmd_run)
    p = sub.add_parser("status", help="show the checkpoint state of a run")
    p.add_argument("run")
    p.set_defaults(func=cmd_status)
    p = sub.add_parser("verify", help="rebuild the verification ledger, re-hash artifacts and re-validate the Engineering State")
    p.add_argument("run")
    p.add_argument("--core")
    p.set_defaults(func=cmd_verify)
    p = sub.add_parser("iterate", help="derive a new run from an existing one with changed inputs; re-run what changed and record accept/reject")
    p.add_argument("run")
    p.add_argument("--set", nargs="+", required=True, metavar="PATH=VALUE", help="dotted specification path and YAML value (null removes the key)")
    p.add_argument("--reason", required=True)
    p.add_argument("--child-id")
    p.add_argument("--workflow")
    p.add_argument("--registry")
    p.add_argument("--checkouts")
    p.add_argument("--core")
    p.set_defaults(func=cmd_iterate)
    p = sub.add_parser("reconcile", help="compare the circuit model's series inductance, magnetising inductance and turns ratio with the "
                                         "magnetics/FEM results of a run; exit 3 when they disagree; --apply derives the child run that re-simulates")
    p.add_argument("run")
    p.add_argument("--tolerance", type=float, default=0.02, help="relative tolerance below which a quantity counts as consistent (default 2 %%)")
    p.add_argument("--prefer", choices=["fem", "magnetics"], default="fem", help="which result wins when both exist (default: executed FEM)")
    p.add_argument("--apply", action="store_true", help="run `iterate` with the proposed changes (re-executes the affected tasks in a child run)")
    p.add_argument("--child-id")
    p.add_argument("--workflow")
    p.add_argument("--registry")
    p.add_argument("--checkouts")
    p.add_argument("--core")
    p.set_defaults(func=cmd_reconcile)

    p = sub.add_parser("report", help="assemble the JSON and Markdown review package")
    p.add_argument("run")
    p.add_argument("--out")
    p.set_defaults(func=cmd_report)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
