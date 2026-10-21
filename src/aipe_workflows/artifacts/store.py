"""Artifact store: records every file a task produced with role, media type and SHA-256.

Files stay where the producing tool wrote them (inside the run directory);
the store keeps an index so reports and Engineering State evidence can
reference artifacts by relative path and hash without copying large data.
"""

from __future__ import annotations

import hashlib
import json
import mimetypes
from pathlib import Path
from typing import Optional, Union

from ..engine.envelope import ArtifactRef, now_iso

_MEDIA = {".h5": "application/x-hdf5", ".cir": "text/x-spice", ".raw": "application/octet-stream", ".log": "text/plain",
          ".json": "application/json", ".yaml": "application/yaml", ".yml": "application/yaml", ".md": "text/markdown",
          ".png": "image/png", ".svg": "image/svg+xml", ".step": "model/step", ".stp": "model/step", ".msh": "model/gmsh",
          ".sif": "text/plain", ".vtu": "application/xml", ".csv": "text/csv", ".kicad_pcb": "application/x-kicad-pcb",
          ".kicad_sch": "application/x-kicad-schematic", ".pdf": "application/pdf"}


def sha256_file(path: Union[str, Path]) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def media_type_for(path: Union[str, Path]) -> str:
    suffix = Path(path).suffix.lower()
    if suffix in _MEDIA:
        return _MEDIA[suffix]
    guess, _ = mimetypes.guess_type(str(path))
    return guess or "application/octet-stream"


class ArtifactStore:
    def __init__(self, directory: Union[str, Path]):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.index_path = self.directory / "index.json"
        self.index: list[dict] = json.loads(self.index_path.read_text(encoding="utf-8")) if self.index_path.is_file() else []

    def add(self, path: Union[str, Path], role: str, description: str = "", task_id: str = "",
            media_type: Optional[str] = None) -> ArtifactRef:
        path = Path(path)
        if not path.is_file():
            raise FileNotFoundError(path)
        run_root = self.directory.parent
        try:
            uri = path.resolve().relative_to(run_root.resolve()).as_posix()
        except ValueError:
            uri = path.resolve().as_posix()
        ref = ArtifactRef(uri=uri, media_type=media_type or media_type_for(path), sha256=sha256_file(path), description=description, role=role)
        entry = {**ref.__dict__, "task_id": task_id, "size_bytes": path.stat().st_size, "recorded_at": now_iso()}
        self.index = [e for e in self.index if e["uri"] != uri] + [entry]
        self.index_path.write_text(json.dumps(self.index, indent=2, sort_keys=True), encoding="utf-8")
        return ref

    def verify(self) -> list[str]:
        """Return descriptions of artifacts whose hash no longer matches."""
        problems = []
        run_root = self.directory.parent
        for entry in self.index:
            path = run_root / entry["uri"]
            if not path.is_file():
                problems.append(f"missing artifact: {entry['uri']}")
            elif sha256_file(path) != entry["sha256"]:
                problems.append(f"hash mismatch: {entry['uri']}")
        return problems
