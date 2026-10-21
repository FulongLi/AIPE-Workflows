"""Load the AIPE Registry index and discover sibling repository manifests.

Two sources are combined, in this precedence:

1. ``generated/aipe.json`` of an AIPE-Registry checkout (hash-pinned, reviewed);
2. sibling checkouts' ``aipe.yaml`` manifests (``--checkouts``), which may be
   newer than the published Registry during coordinated multi-repository work.

Manifests are data. Nothing in them is executed; capability strings are only
matched against workflow task declarations.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Optional

import yaml


def find_registry_index(explicit: Optional[str | Path] = None, start: Optional[Path] = None) -> Optional[Path]:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    if os.environ.get("AIPE_REGISTRY_DIR"):
        candidates.append(Path(os.environ["AIPE_REGISTRY_DIR"]) / "generated" / "aipe.json")
    here = (start or Path.cwd()).resolve()
    for parent in [here, *here.parents]:
        candidates.append(parent / "AIPE-Registry" / "generated" / "aipe.json")
        candidates.append(parent / "repos" / "AIPE-Registry" / "generated" / "aipe.json")
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    return None


def load_registry_index(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "capabilities"} or payload["schema_version"] != "0.1.0":
        raise ValueError("unsupported Registry index envelope")
    return payload


def find_sibling_manifests(checkouts: str | Path) -> list[dict[str, Any]]:
    """Read ``aipe.yaml`` of every repository directory below ``checkouts`` (data only)."""
    manifests = []
    for repo in sorted(Path(checkouts).iterdir()):
        manifest = repo / "aipe.yaml"
        if manifest.is_file():
            try:
                data = yaml.safe_load(manifest.read_text(encoding="utf-8-sig"))
            except yaml.YAMLError as exc:
                data = {"id": f"invalid.{repo.name.lower()}", "error": str(exc)}
            if isinstance(data, dict) and "id" in data:
                data = dict(data)
                data["_source"] = str(manifest)
                manifests.append(data)
    return manifests


def discover_capabilities(registry_index: Optional[str | Path] = None, checkouts: Optional[str | Path] = None) -> dict[str, Any]:
    """Merge the published index with sibling manifests (siblings override by id)."""
    merged: dict[str, dict[str, Any]] = {}
    sources: dict[str, str] = {}
    index_path = find_registry_index(registry_index)
    if index_path:
        for manifest in load_registry_index(index_path)["capabilities"]:
            merged[manifest["id"]] = manifest
            sources[manifest["id"]] = f"registry:{index_path}"
    if checkouts:
        for manifest in find_sibling_manifests(checkouts):
            merged[manifest["id"]] = {k: v for k, v in manifest.items() if not k.startswith("_")}
            sources[manifest["id"]] = f"checkout:{manifest['_source']}"
    capabilities = sorted(merged.values(), key=lambda m: m["id"])
    by_capability: dict[str, list[str]] = {}
    for manifest in capabilities:
        for capability in manifest.get("capabilities", []):
            by_capability.setdefault(capability, []).append(manifest["id"])
    return {"schema_version": "0.1.0", "capabilities": capabilities, "sources": sources,
            "registry_index": str(index_path) if index_path else None, "by_capability": by_capability}
