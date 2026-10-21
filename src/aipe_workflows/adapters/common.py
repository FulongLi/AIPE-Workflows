"""Shared helpers for adapters: sibling repository lookup and guarded imports."""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import Any, Optional


def find_sibling_repo(name: str, env_var: Optional[str] = None, start: Optional[Path] = None) -> Optional[Path]:
    """Locate a sibling AIPE repository checkout by directory name."""
    candidates = []
    if env_var and os.environ.get(env_var):
        candidates.append(Path(os.environ[env_var]))
    here = (start or Path.cwd()).resolve()
    for parent in [here, *here.parents]:
        candidates.append(parent / name)
        candidates.append(parent / "repos" / name)
    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return None


def import_from_checkout(repo: Path, module: str, sys_path_entry: Optional[Path] = None) -> Any:
    """Import ``module`` with the checkout (or a sub-directory) prepended to ``sys.path``.

    Only reviewed sibling checkouts should be supplied; this executes their code.
    """
    entry = str(sys_path_entry or repo)
    if entry not in sys.path:
        sys.path.insert(0, entry)
    return importlib.import_module(module)
