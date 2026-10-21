"""Detect and qualify local engineering software (``aipe-workflows doctor``).

Nothing is installed here. For each tool the doctor records whether it was
found, where, which version it reports and, when ``qualify=True``, whether a
minimal real numerical test passed. Search locations cover PATH, explicit
environment variables, the workspace ``tools/`` folder (portable installs) and
the usual per-user Windows locations, because none of these solvers are on
PATH after a default Windows installation.

Installation guidance for missing tools is reported as *recommendations*
(official channel, licence, admin requirement); executing an installer is a
separate, approved step.
"""

from __future__ import annotations

import importlib
import json
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

from ..engine.envelope import now_iso


@dataclass
class ToolSpec:
    id: str
    name: str
    executables: list[str]
    version_args: list[str]
    version_regex: str
    licence: str
    env_var: Optional[str] = None
    workspace_relative: list[str] = field(default_factory=list)
    windows_locations: list[str] = field(default_factory=list)
    install_hint: str = ""
    qualify: Optional[Callable[[str, Path], dict]] = None
    python_module: Optional[str] = None
    required_for: list[str] = field(default_factory=list)


def _local(*parts: str) -> str:
    base = os.environ.get("LOCALAPPDATA", "")
    return str(Path(base, *parts)) if base else ""


def _programs(*parts: str) -> list[str]:
    out = []
    for base in (os.environ.get("ProgramFiles"), os.environ.get("ProgramFiles(x86)")):
        if base:
            out.append(str(Path(base, *parts)))
    return out


# ----------------------------------------------------------------- qualifiers

def _run(cmd: list[str], cwd: Optional[Path] = None, timeout: float = 180, env: Optional[dict] = None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, timeout=timeout, check=False,
                          errors="replace", env=env)


def qualify_ngspice(exe: str, workdir: Path) -> dict:
    netlist = workdir / "rc.cir"
    netlist.write_text("* RC step, tau=1ms\nV1 in 0 PULSE(0 1 0 1n 1n 10m 20m)\nR1 in out 1k\nC1 out 0 1u\n"
                       ".tran 10u 5m 0 10u\n.meas tran v_1tau FIND v(out) AT=1m\n.end\n", encoding="utf-8")
    completed = _run([exe, "-b", "-o", "rc.log", "rc.cir"], cwd=workdir)
    text = completed.stdout + completed.stderr + ((workdir / "rc.log").read_text(encoding="utf-8", errors="replace") if (workdir / "rc.log").is_file() else "")
    match = re.search(r"v_1tau\s*=\s*([-+0-9.eE]+)", text)
    measured = float(match.group(1)) if match else None
    expected = 1 - math.exp(-1)
    ok = completed.returncode == 0 and measured is not None and abs(measured - expected) / expected < 2e-3
    return {"test": "RC step response at one time constant", "expected": expected, "measured": measured, "passed": ok,
            "returncode": completed.returncode}


def qualify_kicad_cli(exe: str, workdir: Path) -> dict:
    completed = _run([exe, "version", "--format", "plain"], cwd=workdir, timeout=60)
    ok = completed.returncode == 0 and bool(re.search(r"\d+\.\d+", completed.stdout))
    return {"test": "kicad-cli version query (no project checks)", "output": completed.stdout.strip()[:200], "passed": ok,
            "returncode": completed.returncode}


def qualify_freecad(exe: str, workdir: Path) -> dict:
    workdir = workdir.resolve()  # freecadcmd resolves the script path against its own cwd
    script = workdir / "box.py"
    step_path = (workdir / "box.step").as_posix()
    script.write_text("import FreeCAD, Part\nb = Part.makeBox(10, 20, 30)\nprint('VOLUME_MM3', b.Volume)\n"
                      "import Import\nd = FreeCAD.newDocument('q')\no = d.addObject('Part::Feature', 'Box')\no.Shape = b\nd.recompute()\n"
                      f"Import.export([o], r'{step_path}')\nprint('STEP_OK')\n", encoding="utf-8")
    completed = _run([exe, str(script)], cwd=workdir, timeout=300)
    text = completed.stdout + completed.stderr
    match = re.search(r"VOLUME_MM3\s+([-+0-9.eE]+)", text)
    volume = float(match.group(1)) if match else None
    ok = volume is not None and abs(volume - 6000.0) < 1e-6 and "STEP_OK" in text and (workdir / "box.step").is_file()
    return {"test": "Part box 10x20x30 mm volume and STEP export", "expected_volume_mm3": 6000.0, "measured_volume_mm3": volume,
            "step_written": (workdir / "box.step").is_file(), "passed": ok, "returncode": completed.returncode}


def qualify_gmsh_python(_: str, workdir: Path) -> dict:
    try:
        import gmsh  # type: ignore
    except ImportError as exc:
        return {"test": "gmsh python module unit cube mesh", "passed": False, "error": str(exc)}
    try:
        gmsh.initialize()
        gmsh.option.setNumber("General.Terminal", 0)
        gmsh.model.add("cube")
        gmsh.model.occ.addBox(0, 0, 0, 1, 1, 1)
        gmsh.model.occ.synchronize()
        gmsh.option.setNumber("Mesh.CharacteristicLengthMax", 0.25)
        gmsh.model.mesh.generate(3)
        _, tags, _ = gmsh.model.mesh.getElements(3)
        n_tets = int(sum(len(t) for t in tags))
        gmsh.write(str(workdir / "cube.msh"))
        gmsh.finalize()
        return {"test": "gmsh python module unit cube tetrahedral mesh", "tetrahedra": n_tets, "passed": n_tets > 0}
    except Exception as exc:  # gmsh raises generic exceptions
        try:
            gmsh.finalize()
        except Exception:
            pass
        return {"test": "gmsh python module unit cube tetrahedral mesh", "passed": False, "error": str(exc)}


def qualify_elmer(exe: str, workdir: Path) -> dict:
    """1-D steady conduction: T(x) = 300 + q x / k; expect T_max = 305 K."""
    grid_exe = Path(exe).with_name("ElmerGrid.exe" if exe.lower().endswith(".exe") else "ElmerGrid")
    if not grid_exe.is_file():
        return {"test": "Elmer heat conduction slab", "passed": False, "error": f"ElmerGrid not found next to {exe}"}
    (workdir / "plate.grd").write_text("""***** ElmerGrid input file for structured grid generation *****
Version = 210903
Coordinate System = Cartesian 2D
Subcell Divisions in 2D = 1 1
Subcell Limits 1 = 0 0.1
Subcell Limits 2 = 0 0.02
Material Structure in 2D
  1
End
Materials Interval = 1 1
Boundary Definitions
! type     out      int
  1        -1       1       1
  2        -2       1       1
  3        -3       1       1
  4        -4       1       1
End
Numbering = Horizontal
Element Degree = 1
Element Innernodes = False
Triangles = False
Surface Elements = 200
Element Ratios 1 = 1
Element Ratios 2 = 1
Element Densities 1 = 1
Element Densities 2 = 1
""", encoding="utf-8")
    env = {**os.environ, "ELMER_HOME": str(Path(exe).resolve().parent.parent)}
    grid = _run([str(grid_exe), "1", "2", "plate.grd", "-out", "plate"], cwd=workdir, env=env)
    (workdir / "case.sif").write_text("""Header
  Mesh DB "." "plate"
End
Simulation
  Coordinate System = Cartesian 2D
  Simulation Type = Steady State
  Steady State Max Iterations = 1
End
Body 1
  Equation = 1
  Material = 1
End
Equation 1
  Active Solvers(2) = 1 2
End
Solver 1
  Equation = Heat Equation
  Variable = Temperature
  Procedure = "HeatSolve" "HeatSolver"
  Linear System Solver = Direct
  Linear System Direct Method = UMFPack
  Steady State Convergence Tolerance = 1.0e-8
End
Solver 2
  Exec Solver = After All
  Equation = SaveScalars
  Procedure = "SaveData" "SaveScalars"
  Filename = "scalars.dat"
  Variable 1 = Temperature
  Operator 1 = max
  Operator 2 = min
End
Material 1
  Heat Conductivity = 200.0
  Density = 2700.0
  Heat Capacity = 900.0
End
Boundary Condition 1
  Target Boundaries(1) = 4
  Temperature = 300.0
End
Boundary Condition 2
  Target Boundaries(1) = 2
  Heat Flux = 10000.0
End
""", encoding="utf-8")
    solve = _run([exe, "case.sif"], cwd=workdir, timeout=300, env=env)
    scalars = workdir / "scalars.dat"
    t_max = t_min = None
    if scalars.is_file():
        values = scalars.read_text(encoding="utf-8", errors="replace").split()
        if len(values) >= 2:
            t_max, t_min = float(values[0]), float(values[1])
    ok = grid.returncode == 0 and solve.returncode == 0 and t_max is not None and abs(t_max - 305.0) < 1e-3 and abs(t_min - 300.0) < 1e-6
    return {"test": "2-D slab steady heat conduction, analytic T_max = 305 K", "expected_t_max_K": 305.0, "measured_t_max_K": t_max,
            "measured_t_min_K": t_min, "passed": ok, "returncode_grid": grid.returncode, "returncode_solver": solve.returncode}


TOOL_SPECS: list[ToolSpec] = [
    ToolSpec("python", "Python", [sys.executable], ["--version"], r"Python (\d+\.\d+\.\d+)", "PSF", install_hint="https://www.python.org/downloads/"),
    ToolSpec("git", "Git", ["git"], ["--version"], r"git version (\S+)", "GPL-2.0", install_hint="winget install Git.Git"),
    ToolSpec("ngspice", "ngspice", ["ngspice_con", "ngspice"], ["--version"], r"ngspice-(\d+[\w.+-]*)", "BSD-3-Clause (with some GPL/LGPL components; see COPYING)",
             env_var="AIPE_NGSPICE", workspace_relative=["tools/Spice64/bin/ngspice_con.exe", "tools/Spice64/bin/ngspice"],
             windows_locations=["C:/Spice64/bin/ngspice_con.exe", *_programs("Spice64", "bin", "ngspice_con.exe"), _local("Programs", "Spice64", "bin", "ngspice_con.exe")],
             install_hint="Official release archives: https://sourceforge.net/projects/ngspice/files/ng-spice-rework/ (portable 7z, no admin); not in winget",
             qualify=qualify_ngspice, required_for=["circuit_simulation"]),
    ToolSpec("kicad-cli", "KiCad command line", ["kicad-cli"], ["version", "--format", "plain"], r"(\d+\.\d+\.\d+)", "GPL-3.0-or-later",
             env_var="AIPE_KICAD_CLI", workspace_relative=[],
             windows_locations=[_local("Programs", "KiCad", "10.0", "bin", "kicad-cli.exe"), _local("Programs", "KiCad", "9.0", "bin", "kicad-cli.exe"),
                                *_programs("KiCad", "10.0", "bin", "kicad-cli.exe"), *_programs("KiCad", "9.0", "bin", "kicad-cli.exe")],
             install_hint="winget install KiCad.KiCad --scope user (per-user, no admin) or https://www.kicad.org/download/",
             qualify=qualify_kicad_cli, required_for=["cad_pcb"]),
    ToolSpec("freecad", "FreeCAD (headless)", ["freecadcmd", "FreeCADCmd"], ["--version"], r"(\d+\.\d+\.\d+|\d+\.\d+)", "LGPL-2.1-or-later",
             env_var="AIPE_FREECADCMD",
             windows_locations=[_local("Programs", "FreeCAD 1.1", "bin", "freecadcmd.exe"), _local("Programs", "FreeCAD 1.0", "bin", "freecadcmd.exe"),
                                *_programs("FreeCAD 1.1", "bin", "freecadcmd.exe"), *_programs("FreeCAD 1.0", "bin", "freecadcmd.exe")],
             install_hint="winget install FreeCAD.FreeCAD --scope user or portable release from https://github.com/FreeCAD/FreeCAD/releases",
             qualify=qualify_freecad, required_for=["cad_pcb"]),
    ToolSpec("gmsh", "Gmsh (python SDK)", [], [], "", "GPL-2.0-or-later", python_module="gmsh",
             install_hint="python -m pip install gmsh (bundles the Gmsh library; GPL applies to redistribution)", qualify=qualify_gmsh_python,
             required_for=["field_simulation"]),
    ToolSpec("elmer", "Elmer FEM (ElmerSolver)", ["ElmerSolver"], ["-v"], r"ELMER SOLVER \(v ([\d.]+)\)", "GPL-2.0-or-later / LGPL-2.1 (library parts)",
             env_var="AIPE_ELMERSOLVER", workspace_relative=["tools/ElmerFEM-nogui-nompi-Windows-AMD64/bin/ElmerSolver.exe"],
             windows_locations=[*_programs("Elmer 9.0-Release", "bin", "ElmerSolver.exe"), *_programs("Elmer", "bin", "ElmerSolver.exe")],
             install_hint="Portable Windows zip from https://www.nic.funet.fi/pub/sci/physics/elmer/bin/windows/ (no admin) or Windows installer",
             qualify=qualify_elmer, required_for=["field_simulation"]),
    ToolSpec("openfoam", "OpenFOAM", ["blockMesh", "simpleFoam"], ["-help"], r"(v\d+|\d+\.\d+)", "GPL-3.0-or-later",
             install_hint="Windows: WSL2 + openfoam.com packages or docker; not provided by winget", required_for=["field_simulation"]),
    ToolSpec("xyce", "Xyce", ["Xyce"], ["-v"], r"Xyce.*?(\d+\.\d+)", "GPL-3.0-or-later", install_hint="https://xyce.sandia.gov/downloads/", required_for=[]),
    ToolSpec("ltspice", "LTspice (optional free proprietary)", ["LTspice", "XVIIx64"], [], "", "Analog Devices EULA (free, proprietary)",
             windows_locations=[_local("Programs", "ADI", "LTspice", "LTspice.exe"), *_programs("ADI", "LTspice", "LTspice.exe"), *_programs("LTC", "LTspiceXVII", "XVIIx64.exe")],
             install_hint="winget install AnalogDevices.LTspice (optional validation route only)", required_for=[]),
    ToolSpec("node", "Node.js", ["node"], ["--version"], r"v(\d+\.\d+\.\d+)", "MIT", install_hint="https://nodejs.org/", required_for=[]),
]

PYTHON_PACKAGES = ["numpy", "scipy", "h5py", "matplotlib", "yaml", "jsonschema", "gmsh", "pydantic", "aipe_simulation", "pea", "cadquery"]


@dataclass
class EnvironmentManifest:
    created_at: str
    platform: dict[str, Any]
    python: dict[str, Any]
    tools: dict[str, dict[str, Any]]
    python_packages: dict[str, Optional[str]]
    workspace_root: Optional[str]
    recommendations: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _find_executable(spec: ToolSpec, workspace_root: Optional[Path]) -> tuple[Optional[str], str]:
    if spec.env_var and os.environ.get(spec.env_var) and Path(os.environ[spec.env_var]).is_file():
        return os.environ[spec.env_var], spec.env_var
    for exe in spec.executables:
        if exe == sys.executable:
            return exe, "interpreter"
        found = shutil.which(exe)
        if found:
            return found, "PATH"
    tools_dir = os.environ.get("AIPE_TOOLS_DIR")
    roots = [Path(tools_dir).parent] if tools_dir else []
    if workspace_root:
        roots.append(workspace_root)
    here = Path.cwd().resolve()
    roots.extend([here, *here.parents])
    for root in roots:
        for rel in spec.workspace_relative:
            candidate = root / rel
            if candidate.is_file():
                return str(candidate), "workspace-tools"
    for location in spec.windows_locations:
        if location and Path(location).is_file():
            return location, "per-user-or-program-files"
    return None, ""


def _version(exe: str, spec: ToolSpec) -> tuple[str, str]:
    if not spec.version_args:
        return "unknown", ""
    try:
        env = dict(os.environ)
        if spec.id == "elmer":
            env["ELMER_HOME"] = str(Path(exe).resolve().parent.parent)
        completed = _run([exe, *spec.version_args], timeout=60, env=env)
        text = (completed.stdout or "") + (completed.stderr or "")
    except (OSError, subprocess.SubprocessError) as exc:
        return "unknown", f"{type(exc).__name__}: {exc}"
    match = re.search(spec.version_regex, text) if spec.version_regex else None
    return (match.group(1) if match else "unknown"), text.strip()[:300]


def inspect_environment(workspace_root: Optional[str | Path] = None, qualify: bool = False, tools: Optional[list[str]] = None,
                        qualification_dir: Optional[str | Path] = None) -> EnvironmentManifest:
    workspace_root = Path(workspace_root).resolve() if workspace_root else None
    results: dict[str, dict[str, Any]] = {}
    recommendations: list[str] = []
    qual_root = Path(qualification_dir) if qualification_dir else Path(tempfile.mkdtemp(prefix="aipe-doctor-"))
    for spec in TOOL_SPECS:
        if tools and spec.id not in tools:
            continue
        info: dict[str, Any] = {"id": spec.id, "name": spec.name, "licence": spec.licence, "required_for": spec.required_for,
                                "found": False, "path": None, "version": None, "source": None, "qualified": None, "qualification": None,
                                "install_hint": spec.install_hint}
        if spec.python_module:
            try:
                module = importlib.import_module(spec.python_module)
                info.update(found=True, path=getattr(module, "__file__", None), version=getattr(module, "__version__", "unknown"), source="python-module")
            except ImportError:
                recommendations.append(f"{spec.name} missing: {spec.install_hint}")
        else:
            exe, source = _find_executable(spec, workspace_root)
            if exe:
                version, raw = _version(exe, spec)
                info.update(found=True, path=exe, version=version, source=source, version_output=raw)
                if spec.id == "elmer":
                    # ElmerSolver prints the solver core version (9.0) for every modern release; the release
                    # label (e.g. rel26.1) is only visible in the distribution folder name.
                    folder = Path(exe).resolve().parent.parent.name
                    info["release_label"] = folder
                    info["note"] = "ElmerSolver reports the core version; the release label comes from the install folder name"
            else:
                recommendations.append(f"{spec.name} missing: {spec.install_hint}")
        if qualify and info["found"] and spec.qualify:
            workdir = qual_root / spec.id
            workdir.mkdir(parents=True, exist_ok=True)
            try:
                info["qualification"] = spec.qualify(info["path"] or "", workdir)
                info["qualified"] = bool(info["qualification"].get("passed"))
            except Exception as exc:  # a crashing qualifier is a failed qualification
                info["qualification"] = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}
                info["qualified"] = False
            info["qualification_dir"] = str(workdir)
        results[spec.id] = info
    packages: dict[str, Optional[str]] = {}
    for name in PYTHON_PACKAGES:
        try:
            module = importlib.import_module(name)
            packages[name] = str(getattr(module, "__version__", "installed"))
        except Exception:
            packages[name] = None
    manifest = EnvironmentManifest(
        created_at=now_iso(),
        platform={"system": platform.system(), "release": platform.release(), "version": platform.version(), "machine": platform.machine(),
                  "node": platform.node()},
        python={"executable": sys.executable, "version": platform.python_version(), "implementation": platform.python_implementation()},
        tools=results, python_packages=packages, workspace_root=str(workspace_root) if workspace_root else None,
        recommendations=recommendations)
    return manifest


def write_manifest(manifest: EnvironmentManifest, path: str | Path) -> str:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(manifest.to_dict(), indent=2, sort_keys=True, default=str), encoding="utf-8")
    return str(path)
