"""Assemble JSON and Markdown engineering review packages from a run directory."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from ..verification.gates import GATE_ORDER, build_ledger


def _fmt(value: Any, digits: int = 4) -> str:
    if isinstance(value, float):
        return f"{value:.{digits}g}"
    return str(value)


def build_report(run_dir: str | Path, out_dir: str | Path | None = None) -> dict[str, str]:
    run_dir = Path(run_dir)
    out_dir = Path(out_dir) if out_dir else run_dir / "report"
    out_dir.mkdir(parents=True, exist_ok=True)
    run = json.loads((run_dir / "run.json").read_text(encoding="utf-8"))
    spec = json.loads((run_dir / "specification.json").read_text(encoding="utf-8"))
    environment = json.loads((run_dir / "environment.json").read_text(encoding="utf-8"))
    workflow = json.loads((run_dir / "workflow.json").read_text(encoding="utf-8"))
    plan = json.loads((run_dir / "plan.json").read_text(encoding="utf-8")) if (run_dir / "plan.json").is_file() else {}
    ledger = build_ledger(run_dir)
    envelopes: dict[str, dict] = {}
    for task_id, record in run["tasks"].items():
        path = record.get("envelope_path")
        if path and Path(path).is_file():
            envelopes[task_id] = json.loads(Path(path).read_text(encoding="utf-8"))
    final_state = json.loads(Path(run["state_versions"][-1]["path"]).read_text(encoding="utf-8")) if run.get("state_versions") else None
    figures = []
    fig_dir = out_dir / "figures"
    for task_id, envelope in envelopes.items():
        for artifact in envelope.get("artifacts", []):
            if artifact.get("role") == "figure":
                src = run_dir / artifact["uri"] if not Path(artifact["uri"]).is_absolute() else Path(artifact["uri"])
                if src.is_file():
                    fig_dir.mkdir(exist_ok=True)
                    dst = fig_dir / f"{task_id}-{src.name}"
                    shutil.copyfile(src, dst)
                    figures.append({"task": task_id, "path": f"figures/{dst.name}", "sha256": artifact.get("sha256")})
    report_json = {
        "schema": "aipe-workflows-report/0.1", "run": {k: run[k] for k in ("run_id", "workflow_id", "status", "created_at", "updated_at", "spec_sha256")},
        "specification": spec, "environment": {"platform": environment["platform"], "python": environment["python"],
                                                "tools": {k: {kk: v.get(kk) for kk in ("found", "path", "version", "qualified")} for k, v in environment["tools"].items()}},
        "tasks": {tid: {"status": r["status"], "message": r.get("message", ""), "outputs": envelopes.get(tid, {}).get("outputs", {}),
                        "verification": envelopes.get(tid, {}).get("verification", {}), "diagnostics": envelopes.get(tid, {}).get("diagnostics", []),
                        "artifacts": envelopes.get(tid, {}).get("artifacts", []), "tool": envelopes.get(tid, {}).get("tool"),
                        "model": envelopes.get(tid, {}).get("model")} for tid, r in run["tasks"].items()},
        "verification_gates": ledger.to_dict(), "figures": figures,
        "engineering_state": {"versions": run.get("state_versions", []), "final": final_state},
        "blocked_items": [{"task": tid, "reason": r.get("message", "")} for tid, r in run["tasks"].items() if r["status"] == "blocked"],
        "failed_items": [{"task": tid, "reason": r.get("message", "")} for tid, r in run["tasks"].items() if r["status"] == "failed"],
    }
    (out_dir / "report.json").write_text(json.dumps(report_json, indent=2, sort_keys=True, default=str), encoding="utf-8")
    md = _markdown(report_json, workflow, plan)
    (out_dir / "report.md").write_text(md, encoding="utf-8")
    from .html import render_html

    html_path = render_html(report_json, workflow, out_dir)
    return {"json": str(out_dir / "report.json"), "markdown": str(out_dir / "report.md"), "html": html_path, "figures": [f["path"] for f in figures]}


def _markdown(report: dict, workflow: dict, plan: dict) -> str:
    run = report["run"]
    spec = report["specification"]
    lines = [f"# {workflow.get('name', run['workflow_id'])} — engineering review package", "",
             f"Run `{run['run_id']}` · workflow `{run['workflow_id']}` · status **{run['status']}** · created {run['created_at']} · specification hash `{run['spec_sha256'][:16]}`", "",
             "## 1. Requirements and specification", ""]
    req = spec.get("requirements", {})
    lines += ["| Quantity | Value |", "| --- | --- |"]
    for key, value in req.items():
        lines.append(f"| {key} | {value} |")
    lines.append("")
    if spec.get("constraints"):
        lines += ["### Constraints, ranges and assumptions (with basis)", "", "| Id | Description | Basis |", "| --- | --- | --- |"]
        for c in spec["constraints"]:
            lines.append(f"| {c['id']} | {c['description']} | {c.get('basis', 'assumption')} |")
        lines.append("")
    lines += ["## 2. Environment", "", f"Platform: {report['environment']['platform']['system']} {report['environment']['platform']['release']} ({report['environment']['platform']['machine']}); "
              f"Python {report['environment']['python']['version']}", "", "| Tool | Found | Version | Qualified | Path |", "| --- | --- | --- | --- | --- |"]
    for tid, t in report["environment"]["tools"].items():
        lines.append(f"| {tid} | {t['found']} | {t.get('version') or ''} | {t.get('qualified') if t.get('qualified') is not None else 'not tested'} | `{t.get('path') or ''}` |")
    lines += ["", "## 3. Task execution", "", "| Task | Gate | Status | Tool | Message |", "| --- | --- | --- | --- | --- |"]
    gate_of = {t["id"]: t["gate"] for t in workflow["tasks"]}
    for tid, t in report["tasks"].items():
        tool = t.get("tool") or {}
        lines.append(f"| {tid} | {gate_of.get(tid, '')} | **{t['status']}** | {tool.get('id', '')} {tool.get('version', '')} | {t.get('message', '')} |")
    lines.append("")
    for tid, t in report["tasks"].items():
        if not t.get("outputs"):
            continue
        lines += [f"### {tid}", ""]
        outputs = t["outputs"]
        scalar = {k: v for k, v in outputs.items() if isinstance(v, (int, float, str, bool)) or v is None}
        if scalar:
            lines += ["| Output | Value |", "| --- | --- |"]
            for k, v in scalar.items():
                lines.append(f"| {k} | {_fmt(v, 6)} |")
            lines.append("")
        if outputs.get("switches"):
            lines += ["| Switch | I rms (A) | I avg (A) | I turn-off mean |A| (A) | I peak fwd (A) | I peak rev (A) | V_ds max (V) | ZVS current condition | conduction |",
                      "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
            for sid, s in outputs["switches"].items():
                i_off = s["i_turn_off_mean_abs_A"]
                i_off_text = "n/a" if i_off is None else f"{i_off:.3f}"
                lines.append(f"| {sid} | {s['i_rms_A']:.3f} | {s['i_avg_A']:.3f} | {i_off_text} | {s['i_peak_fwd_A']:.3f} | {s['i_peak_rev_A']:.3f} | {s['v_ds_max_V']:.1f} | {s['zvs_current_condition_all_events']} | {s['conduction_fraction']:.3f} |")
            lines.append("")
        if outputs.get("comparison_vs_analytic"):
            cmp = outputs["comparison_vs_analytic"]
            lines += [f"Comparison with analytical SPS reference (tolerance {cmp['tolerance']:.1%}): **{'pass' if cmp['pass'] else 'fail'}**", "",
                      "| Quantity | Expected | Simulated | Relative error |", "| --- | --- | --- | --- |"]
            for k, v in cmp["items"].items():
                lines.append(f"| {k} | {_fmt(v['expected'], 6)} | {_fmt(v['actual'], 6)} | {v['relative_error']:.2e} |")
            lines.append("")
        if t.get("verification"):
            lines += ["Verification metrics:", ""]
            for k, v in t["verification"].items():
                lines.append(f"- {k}: {_fmt(v, 4)}")
            lines.append("")
        if t.get("model"):
            lines.append(f"Model: `{t['model'].get('id')}` v{t['model'].get('version')} — validity: {t['model'].get('validity_range', '')}")
            lines.append("")
    if report["figures"]:
        lines += ["## 4. Figures", ""]
        for fig in report["figures"]:
            lines += [f"![{fig['task']}]({fig['path']})", "", f"`{fig['path']}` (sha256 {str(fig.get('sha256'))[:16]}, task {fig['task']})", ""]
    lines += ["## 5. Verification gates", "", "| Gate | Status | Checks |", "| --- | --- | --- |"]
    for gate in GATE_ORDER:
        g = report["verification_gates"]["gates"][gate]
        lines.append(f"| {gate} | **{g['status']}** | {', '.join(c['task'] + ':' + c['status'] for c in g['checks']) or '—'} {' '.join(g['notes'])} |")
    lines += ["", "Passing an earlier gate does not imply a later one has passed. Experimental measurement and hardware qualification are outside this software workflow.", ""]
    if report["blocked_items"] or report["failed_items"]:
        lines += ["## 6. Blocked and failed items", ""]
        for item in report["blocked_items"]:
            lines.append(f"- BLOCKED `{item['task']}`: {item['reason']}")
        for item in report["failed_items"]:
            lines.append(f"- FAILED `{item['task']}`: {item['reason']}")
        lines.append("")
    final = report["engineering_state"]["final"]
    if final:
        lines += ["## 7. Engineering State", "", f"Final state id `{final['id']}`, validation status **{final['validation']['status']}**, simulation status **{final['simulation']['status']}**, "
                  f"architecture stage **{final['architecture']['stage']}**; {len(final['evidence'])} evidence records, {len(report['engineering_state']['versions'])} state versions (all preserved under `state/`).", ""]
        for limitation in final["validation"].get("limitations", []):
            lines.append(f"- Limitation: {limitation}")
        lines.append("")
    lines += ["## 8. Reproduction", "", "```", "aipe-workflows doctor --qualify", f"aipe-workflows run <specification.yaml> --run-dir <run-dir>", f"aipe-workflows verify {run['run_id']}", f"aipe-workflows report {run['run_id']}", "```", ""]
    return "\n".join(lines)
