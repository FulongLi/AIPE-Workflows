# Clean-checkout acceptance harness (task §16)

`run_acceptance.ps1` clones the official AIPE repositories listed in `sources.json` (default branches, or the PR heads named
there while stabilisation PRs are open), creates a fresh virtual environment, installs every package exactly as its README
says (`requirements`, `install`, `extras`), qualifies the engineering tools with `aipe-workflows doctor --qualify`, runs the
Core and Registry contract checks with their own documented test commands and then executes the DAB workflow: `plan`,
`run`, `verify`, `report`, `status`. Every command and exit code is logged to `<workspace>\acceptance.log` (UTF-8). The run
step tolerates exit 2 (`completed_with_blocked` / `completed_with_failed_optional`), records it and leaves the judgement to
the report; every other non-zero exit stops the harness.

```powershell
powershell -ExecutionPolicy Bypass -File tools\acceptance\run_acceptance.ps1 -Workspace D:\aipe-acceptance -ToolsDir D:\aipe-tools
```

Windows PowerShell 5.1, Python 3.10+, git and the engineering tools (ngspice, KiCad 10, FreeCAD 1.1, Gmsh, Elmer) are
required; tools that are not on PATH are found through `-ToolsDir` / `tools_dir` (`AIPE_TOOLS_DIR`). Remove the `ref`
entries from `sources.json` once the PRs are merged so that the default branches are tested. The executed result of
2026-10-21 is recorded in `examples/dab-10kw/results/acceptance-2026-10-21/`.
