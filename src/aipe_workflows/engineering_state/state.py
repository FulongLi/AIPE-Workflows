"""Engineering State (AIPE Core v0.1) helpers.

The canonical schemas and semantic checker live in AIPE-Core. This module
never defines a competing schema: it locates a Core checkout, runs Core's own
``scripts/validate.py`` and applies *proposals* produced by adapters in a way
that keeps every previous evidence record and never overwrites values without
new evidence.

A proposal is a plain dictionary::

    {
      "evidence": [ <Core evidence records to append> ],
      "set": [ {"path": "control.phase_shift", "value": {"value": 0.39, "unit": "rad"}}, ... ],
      "append": [ {"path": "magnetics", "value": {...}}, {"path": "simulation.runs", "value": {...}},
                  {"path": "validation.checks", "value": {...}} ],
      "extensions": { "aipe.workflows.dab": {...} },
      "status": { "simulation": "completed", "validation": "simulated", "architecture_stage": "candidate",
                  "converter_design_status": "candidate" }
    }

Rules enforced here (Core enforces the rest): every ``set``/``append`` target
object must carry ``evidence_refs`` that exist; evidence IDs must be new;
``extensions`` keys must be namespaced; existing evidence is never removed.
"""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import re
from pathlib import Path
from typing import Any, Optional

_ID = re.compile(r"^[a-z][a-z0-9]*(?:[.:-][a-z0-9]+(?:-[a-z0-9]+)*)+$")


class StateError(ValueError):
    """The Engineering State or a proposal is not acceptable."""


def state_sha256(state: Any) -> str:
    return hashlib.sha256(json.dumps(state, sort_keys=True, separators=(",", ":"), default=str, allow_nan=False).encode("utf-8")).hexdigest()


def load_state(path: str | Path) -> dict[str, Any]:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise StateError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    def reject(value):
        raise StateError(f"nonfinite JSON number: {value}")

    return json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=unique, parse_constant=reject)


def find_core_dir(explicit: Optional[str | Path] = None, start: Optional[Path] = None) -> Optional[Path]:
    """Locate an AIPE-Core checkout: explicit path, AIPE_CORE_DIR, or a sibling ``AIPE-Core``."""
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("AIPE_CORE_DIR"):
        candidates.append(Path(os.environ["AIPE_CORE_DIR"]))
    here = (start or Path.cwd()).resolve()
    for parent in [here, *here.parents]:
        candidates.append(parent / "AIPE-Core")
        candidates.append(parent / "repos" / "AIPE-Core")
    for candidate in candidates:
        if (candidate / "scripts" / "validate.py").is_file() and (candidate / "schemas" / "engineering-state.schema.json").is_file():
            return candidate.resolve()
    return None


_validator_cache: dict[str, Any] = {}


def validate_state(state: dict[str, Any], core_dir: str | Path) -> list[str]:
    """Run AIPE-Core's canonical validator from a reviewed local checkout."""
    core_dir = Path(core_dir).resolve()
    key = str(core_dir)
    if key not in _validator_cache:
        script = core_dir / "scripts" / "validate.py"
        if not script.is_file():
            raise StateError(f"Core checkout {core_dir} has no scripts/validate.py")
        spec = importlib.util.spec_from_file_location("_aipe_core_validate", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)  # type: ignore[union-attr]
        _validator_cache[key] = module
    module = _validator_cache[key]
    return module.validate_state(state, core_dir / "schemas")


def _get(node: Any, path: str) -> Any:
    for part in path.split("."):
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def _set(node: Any, path: str, value: Any) -> None:
    parts = path.split(".")
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node.setdefault(part, {})
    last = parts[-1]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value


def apply_proposal(state: dict[str, Any], proposal: dict[str, Any], envelope: Any = None) -> dict[str, Any]:
    """Return a new state with the proposal applied; the input is not mutated."""
    new_state = copy.deepcopy(state)
    existing_ids = {item["id"] for item in new_state.get("evidence", [])}
    added_ids: set[str] = set()
    for record in proposal.get("evidence", []):
        if not isinstance(record, dict) or "id" not in record:
            raise StateError("evidence record without id")
        if record["id"] in existing_ids or record["id"] in added_ids:
            raise StateError(f"evidence id already exists: {record['id']}")
        if not _ID.match(record["id"]):
            raise StateError(f"invalid evidence id: {record['id']}")
        new_state.setdefault("evidence", []).append(copy.deepcopy(record))
        added_ids.add(record["id"])
    known = existing_ids | added_ids

    def check_refs(obj: Any, where: str) -> None:
        if isinstance(obj, dict):
            refs = obj.get("evidence_refs")
            if refs is not None:
                for ref in refs:
                    if ref not in known:
                        raise StateError(f"{where}: unknown evidence reference {ref}")
            for key, value in obj.items():
                if key != "extensions":
                    check_refs(value, f"{where}.{key}")
        elif isinstance(obj, list):
            for index, item in enumerate(obj):
                check_refs(item, f"{where}[{index}]")

    for item in proposal.get("set", []):
        value = copy.deepcopy(item["value"])
        check_refs(value, item["path"])
        _set(new_state, item["path"], value)
    for item in proposal.get("append", []):
        value = copy.deepcopy(item["value"])
        check_refs(value, item["path"])
        target = _get(new_state, item["path"])
        if not isinstance(target, list):
            raise StateError(f"append target {item['path']} is not a list")
        if isinstance(value, dict) and "id" in value:
            if any(isinstance(existing, dict) and existing.get("id") == value["id"] for existing in target):
                raise StateError(f"entity id already exists in {item['path']}: {value['id']}")
        target.append(value)
    for namespace, payload in proposal.get("extensions", {}).items():
        if not re.match(r"^[a-z][a-z0-9-]*[.][a-z][a-z0-9_.-]*$", namespace):
            raise StateError(f"extension namespace must be namespaced: {namespace}")
        extensions = new_state.setdefault("extensions", {})
        current = extensions.get(namespace)
        if isinstance(current, dict) and isinstance(payload, dict):
            merged = dict(current)
            merged.update(copy.deepcopy(payload))
            extensions[namespace] = merged
        else:
            extensions[namespace] = copy.deepcopy(payload)
    # Versioned contract for this workflow's own extension namespace.
    dab_ext = new_state.get("extensions", {}).get("aipe.workflows.dab")
    if dab_ext is not None:
        errors = validate_dab_extension(dab_ext)
        if errors:
            raise StateError("aipe.workflows.dab extension violates its schema: " + "; ".join(errors[:5]))
    status = proposal.get("status", {})
    if "simulation" in status:
        new_state["simulation"]["status"] = status["simulation"]
    if "validation" in status:
        new_state["validation"]["status"] = status["validation"]
    if "architecture_stage" in status:
        new_state["architecture"]["stage"] = status["architecture_stage"]
    if "converter_design_status" in status:
        new_state["converter"]["design_status"] = status["converter_design_status"]
    if proposal.get("updated_at"):
        new_state["project"]["updated_at"] = proposal["updated_at"]
    return new_state


_DAB_EXT_SCHEMA = Path(__file__).resolve().parents[1] / "schemas" / "dab-extension.schema.json"


def validate_dab_extension(payload: Any) -> list[str]:
    """Validate extensions['aipe.workflows.dab'] against the versioned extension schema."""
    from jsonschema import Draft202012Validator

    schema = json.loads(_DAB_EXT_SCHEMA.read_text(encoding="utf-8"))
    return [f"{'/'.join(str(x) for x in e.absolute_path) or '$'}: {e.message}"
            for e in sorted(Draft202012Validator(schema).iter_errors(payload), key=lambda e: list(e.absolute_path))]


def quantity(value: float, unit: str) -> dict[str, Any]:
    return {"value": float(value), "unit": unit}


def build_initial_state(spec: dict[str, Any], created_at: str, evidence_id: str = "evidence.specification") -> dict[str, Any]:
    """Create a Core v0.1 Engineering State from a workflow specification.

    Only requested ratings and documented assumptions are recorded; no component,
    loss, simulation or measurement is claimed. Ranges and limits in the
    specification become constraint records whose descriptions cite their basis.
    """
    req = spec["requirements"]
    project = spec.get("project", {})
    ids = {"spec": evidence_id, "refs": "evidence.reference-designs"}
    constraints = []
    for index, item in enumerate(spec.get("constraints", [])):
        refs = [ids["spec"]] + ([ids["refs"]] if item.get("basis", "").startswith("source") else [])
        constraints.append({"id": f"constraint.{item['id']}", "description": f"{item['description']} [basis: {item.get('basis', 'assumption')}]",
                            "evidence_refs": refs})
    ambient_k = spec.get("environment", {}).get("ambient_temperature_K")
    state = {
        "id": spec.get("state_id", "aipe.workflow.dab-10kw-run"),
        "schema_version": "0.1.0",
        "project": {"id": project.get("id", "project.dab-10kw"), "name": project.get("name", "AIPE 10 kW DAB benchmark"),
                    "description": project.get("description", "Simulation-driven engineering workflow benchmark."),
                    "purpose": project.get("purpose", "engineering"), "created_at": created_at, "updated_at": created_at,
                    "evidence_refs": [ids["spec"]]},
        "requirements": {
            "nominal_power": quantity(req["nominal_power_W"], "W"),
            "input_voltage": quantity(req["input_voltage_V"], "V"),
            "output_voltage": quantity(req["output_voltage_V"], "V"),
            "switching_frequency": quantity(req["switching_frequency_Hz"], "Hz"),
            "operating_points": [{
                "id": "operating-point.nominal", "description": "Requested nominal operating point (design input, not a measurement).",
                "input_voltage": quantity(req["input_voltage_V"], "V"), "output_voltage": quantity(req["output_voltage_V"], "V"),
                "output_power": quantity(req["nominal_power_W"], "W"), "switching_frequency": quantity(req["switching_frequency_Hz"], "Hz"),
                **({"ambient_temperature": quantity(ambient_k, "K")} if ambient_k else {}),
                "evidence_refs": [ids["spec"]]}],
            "constraints": constraints,
            "evidence_refs": [ids["spec"]],
        },
        "architecture": {"stage": "concept", "description": spec.get("converter", {}).get("description", "Single-phase isolated bidirectional dual active bridge, two full bridges, eight controlled switches."),
                         "evidence_refs": [ids["spec"]]},
        "converter": {"id": "converter.dab", "topology": "dual-active-bridge", "isolation": "isolated", "design_status": "concept",
                      "description": "10 kW bidirectional isolated DAB; initial single-phase-shift modulation.", "evidence_refs": [ids["spec"]]},
        "semiconductors": [], "magnetics": [], "passives": [],
        "control": {"evidence_refs": []},
        "thermal": ({"ambient_temperature": quantity(ambient_k, "K"), "evidence_refs": [ids["spec"], ids["refs"]]} if ambient_k else {"evidence_refs": []}),
        "simulation": {"status": "not_run", "runs": [], "evidence_refs": []},
        "validation": {"status": "not_run", "checks": [], "limitations": [
            "Initial state: requested ratings and documented assumptions only; no component, loss, simulation or measurement claimed."],
            "evidence_refs": []},
        "evidence": [
            {"id": ids["spec"], "kind": "assumption",
             "description": "Workflow specification: requested ratings, operating envelope assumptions and design limits with their stated basis.",
             "source": {"type": "user_requirement", "reference": spec.get("source_reference", "AIPE 10 kW DAB engineering task (task211026)")},
             "provenance": {"created_at": created_at, "activity": "Record requested design inputs and explicitly labelled assumptions; no calculation performed.", "inputs": []},
             "artifacts": [], "review_status": "unreviewed"},
            {"id": ids["refs"], "kind": "source",
             "description": "Reference designs consulted for operating ranges and component stresses: TI TIDA-010054 design guide TIDUES0 (700-800 V input, 250-500 V output, 100 kHz, 35 uH, 200 ns dead time, 40 degC ambient assumption).",
             "source": {"type": "document", "reference": "https://www.ti.com/lit/pdf/tidues0", "locator": "TIDUES0 Rev F, Tables 1-1, 2-1, 2-2, section 2.3.5.6"},
             "provenance": {"created_at": created_at, "activity": "Collect published reference-design parameters; values are TI's, not AIPE results.", "inputs": []},
             "artifacts": [], "review_status": "unreviewed"},
        ],
    }
    return state
