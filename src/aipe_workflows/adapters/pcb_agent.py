"""AIPE-PCB-Agent adapter: executed KiCad ERC/DRC on the generated DAB boards.

AIPE-PCB-Agent generates and routes the three DAB boards (primary power,
secondary power, control) with its own KiCad automation (`automation/dab_v1`).
This task does not re-generate anything: it runs `kicad-cli sch erc` on the
root schematic and `kicad-cli pcb drc --schematic-parity` on the board of every
listed design, stores the JSON reports as hashed artifacts, records the SHA-256
of the checked source files and counts violations by severity and type.

The `cad_pcb` gate requires zero ERC errors, zero DRC errors, zero unconnected
items and zero schematic-parity errors on every board; otherwise the task fails
with the counts, so the ledger shows the gate as not passed instead of hiding
unrouted connections behind a completed status.
"""

from __future__ import annotations

import collections
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Optional

from ..engine.envelope import ExecutionEnvelope, now_iso
from ..engine.runner import TaskAdapter, TaskContext
from .common import find_sibling_repo
from .design_agent import run_suffix


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def summarise_erc(report: dict) -> dict[str, Any]:
    """Counts from a kicad-cli ERC JSON report (sheets[].violations[])."""
    violations = [v for s in report.get("sheets", []) for v in s.get("violations", [])]
    by_sev = collections.Counter(v.get("severity") for v in violations)
    return {"sheets": len(report.get("sheets", [])), "errors": by_sev.get("error", 0), "warnings": by_sev.get("warning", 0),
            "excluded": by_sev.get("exclusion", 0), "total": len(violations),
            "types": dict(collections.Counter(v.get("type") for v in violations).most_common(8)),
            "kicad_version": report.get("kicad_version")}


def summarise_drc(report: dict) -> dict[str, Any]:
    """Counts from a kicad-cli DRC JSON report (violations[], unconnected_items[], schematic_parity[])."""
    out: dict[str, Any] = {"kicad_version": report.get("kicad_version")}
    for key in ("violations", "unconnected_items", "schematic_parity"):
        items = report.get(key, [])
        by_sev = collections.Counter(v.get("severity") for v in items)
        out[key] = {"total": len(items), "errors": by_sev.get("error", 0), "warnings": by_sev.get("warning", 0),
                    "types": dict(collections.Counter(v.get("type") for v in items).most_common(8))}
    return out


def board_is_clean(erc: dict, drc: dict) -> bool:
    return (erc["errors"] == 0 and drc["violations"]["errors"] == 0 and drc["unconnected_items"]["total"] == 0
            and drc["schematic_parity"]["errors"] == 0)


class KicadBoardChecksTask(TaskAdapter):
    id = "aipe.pcb-agent.kicad-erc-drc"
    version = "0.1.0"

    def _repo(self) -> Optional[Path]:
        return find_sibling_repo("AIPE-PCB-Agent", "AIPE_PCB_AGENT_DIR")

    def requirements(self, environment: dict[str, Any]) -> list[str]:
        problems = []
        if not environment.get("tools", {}).get("kicad-cli", {}).get("found"):
            problems.append("kicad-cli not found")
        if self._repo() is None:
            problems.append("AIPE-PCB-Agent checkout not found (the generated boards are read from it)")
        return problems

    def execute(self, ctx: TaskContext) -> ExecutionEnvelope:
        started = now_iso()
        p = ctx.task.parameters
        repo = self._repo()
        kicad = ctx.environment.get("tools", {}).get("kicad-cli", {})
        exe = kicad.get("path")
        example_dir = repo / str(p.get("example_dir", "examples/dab-10kw"))
        boards = p.get("boards") or [
            {"id": "primary-power", "schematic": "primary-power/dab-primary.kicad_sch", "pcb": "primary-power/dab-primary.kicad_pcb"},
            {"id": "secondary-power", "schematic": "secondary-power/dab-secondary.kicad_sch", "pcb": "secondary-power/dab-secondary.kicad_pcb"},
            {"id": "control", "schematic": "control/dab-control.kicad_sch", "pcb": "control/dab-control.kicad_pcb"},
        ]
        envelope = ExecutionEnvelope(task_id=ctx.task.id, task_version=self.version, capability_id="aipe.pcb-agent",
                                     tool={"id": "tool.kicad-cli", "version": str(kicad.get("version") or "unknown"), "name": "KiCad command line (ERC/DRC)"},
                                     status="completed", started_at=started, finished_at=now_iso(), source_state_id=ctx.state.get("id", ""),
                                     source_state_sha256=ctx.state_sha256, inputs={"example_dir": str(example_dir), "boards": boards},
                                     model={"id": "kicad-erc-drc", "version": str(kicad.get("version") or "unknown"),
                                            "validity_range": "electrical and design rule checks against the project's own rule set; no electrical, thermal or EMC performance claim; "
                                                              "board generation and routing are AIPE-PCB-Agent's, not this task's"},
                                     evidence_kind="analytical", gate="cad_pcb")
        results: dict[str, Any] = {}
        sources: dict[str, Any] = {}
        for board in boards:
            bid = board["id"]
            sch, pcb = example_dir / board["schematic"], example_dir / board["pcb"]
            if not sch.is_file() or not pcb.is_file():
                envelope.add_error("missing-board", f"{bid}: schematic or board file missing ({sch.name}, {pcb.name})")
                continue
            sources[bid] = {"schematic": str(sch), "schematic_sha256": _sha256(sch), "pcb": str(pcb), "pcb_sha256": _sha256(pcb)}
            erc_out, drc_out = (ctx.task_dir / f"erc-{bid}.json").resolve(), (ctx.task_dir / f"drc-{bid}.json").resolve()
            runs = [("erc", [exe, "sch", "erc", "--format", "json", "--severity-all", "--output", str(erc_out), str(sch)]),
                    ("drc", [exe, "pcb", "drc", "--format", "json", "--severity-all", "--schematic-parity", "--output", str(drc_out), str(pcb)])]
            logs = []
            ok = True
            for kind, cmd in runs:
                completed = subprocess.run(cmd, capture_output=True, text=True, timeout=float(p.get("timeout_s", 900)), check=False, errors="replace")
                logs.append(f"$ {' '.join(cmd)}\n{completed.stdout}\n{completed.stderr}")
                if completed.returncode != 0:
                    ok = False
                    envelope.add_error(f"kicad-{kind}", f"{bid}: exit code {completed.returncode}: {(completed.stderr or completed.stdout)[-300:]}")
            (ctx.task_dir / f"kicad-{bid}.log").write_text("\n".join(logs), encoding="utf-8")
            if not ok or not erc_out.is_file() or not drc_out.is_file():
                continue
            erc = summarise_erc(json.loads(erc_out.read_text(encoding="utf-8")))
            drc = summarise_drc(json.loads(drc_out.read_text(encoding="utf-8")))
            envelope.artifacts.append(ctx.artifacts.add(erc_out, "erc_report", f"{bid} ERC report (kicad-cli, JSON)", ctx.task.id))
            envelope.artifacts.append(ctx.artifacts.add(drc_out, "drc_report", f"{bid} DRC report with schematic parity (kicad-cli, JSON)", ctx.task.id))
            results[bid] = {"erc": erc, "drc": drc, "clean": board_is_clean(erc, drc)}
        # PCB-Agent's own verification records, if present
        verification_dir = example_dir / "verification"
        attached = []
        if verification_dir.is_dir():
            for f in sorted(verification_dir.glob("*")):
                if f.is_file() and f.suffix.lower() in (".json", ".md", ".txt") and f.stat().st_size < 2_000_000:
                    envelope.artifacts.append(ctx.artifacts.add(f, "pcb_verification_record", f"AIPE-PCB-Agent verification record {f.name}", ctx.task.id))
                    attached.append(f.name)
        totals = {"boards_checked": len(results), "boards_requested": len(boards),
                  "erc_errors": sum(r["erc"]["errors"] for r in results.values()), "erc_warnings": sum(r["erc"]["warnings"] for r in results.values()),
                  "drc_errors": sum(r["drc"]["violations"]["errors"] for r in results.values()), "drc_warnings": sum(r["drc"]["violations"]["warnings"] for r in results.values()),
                  "unconnected_items": sum(r["drc"]["unconnected_items"]["total"] for r in results.values()),
                  "schematic_parity_errors": sum(r["drc"]["schematic_parity"]["errors"] for r in results.values())}
        all_clean = len(results) == len(boards) and all(r["clean"] for r in results.values())
        envelope.outputs = {"boards": results, "sources": sources, "totals": totals, "all_clean": all_clean, "kicad_version": kicad.get("version"),
                            "pcb_agent_verification_records": attached, "example_dir": str(example_dir)}
        envelope.verification = {"all_boards_checked": len(results) == len(boards), "all_clean": all_clean, **totals}
        if not all_clean:
            envelope.status = "failed"
            unrouted = {b: r["drc"]["unconnected_items"]["total"] for b, r in results.items()}
            envelope.add_error("pcb-checks", f"boards not clean: ERC errors {totals['erc_errors']}, DRC errors {totals['drc_errors']}, unconnected items {unrouted}, "
                                             f"parity errors {totals['schematic_parity_errors']}; boards checked {len(results)}/{len(boards)}")
            return envelope
        suffix = run_suffix(ctx.run_id)
        evidence_id = f"evidence.pcb-erc-drc-{suffix}"
        evidence = {
            "id": evidence_id, "kind": "analytical",
            "description": (f"Executed kicad-cli {kicad.get('version')} ERC and DRC (with schematic parity) on {len(results)} AIPE-PCB-Agent DAB boards: "
                            f"no errors, no unconnected items; warnings ERC {totals['erc_warnings']}, DRC {totals['drc_warnings']}."),
            "source": {"type": "repository", "reference": "https://github.com/FulongLi/AIPE-PCB-Agent", "locator": str(p.get("example_dir", "examples/dab-10kw"))},
            "provenance": {"created_at": started, "activity": "Run kicad-cli sch erc and pcb drc --schematic-parity on each generated board; store JSON reports and source hashes.",
                           "tool": dict(envelope.tool), "agent": {"id": "aipe.workflows", "version": "0.1.0"}, "inputs": ["evidence.specification"]},
            "artifacts": [a.to_core() for a in envelope.artifacts], "review_status": "unreviewed",
        }
        envelope.state_proposal = {
            "evidence": [evidence],
            "append": [{"path": "validation.checks", "value": {"id": f"check.pcb-erc-drc-{suffix}", "kind": "analytical", "status": "pass",
                                                               "description": "KiCad ERC and DRC with schematic parity clean on every generated DAB board.", "evidence_refs": [evidence_id]}}],
            "extensions": {"aipe.workflows.dab": {"pcb_checks": {"totals": totals, "all_clean": all_clean, "kicad_version": kicad.get("version"),
                                                                 "boards": {b: {"clean": r["clean"], "erc_warnings": r["erc"]["warnings"], "drc_warnings": r["drc"]["violations"]["warnings"]} for b, r in results.items()},
                                                                 "sources": {b: {"pcb_sha256": s["pcb_sha256"], "schematic_sha256": s["schematic_sha256"]} for b, s in sources.items()}}}},
            "updated_at": now_iso(),
        }
        return envelope
