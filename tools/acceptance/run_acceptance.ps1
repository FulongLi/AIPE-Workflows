# AIPE clean-checkout acceptance test (Windows, PowerShell 5.1) -- task-update.txt section 16.
#
# Clones the official repositories (default branches, or the PR heads listed in sources.json while the stabilisation PRs
# are unmerged), creates a fresh virtual environment, installs the packages exactly as their READMEs say, qualifies the
# engineering tools (ngspice, FreeCAD, KiCad, Elmer), validates the Core and Registry contracts with their own documented
# test commands and runs the full DAB workflow with verify and report. Nothing from the developer's repos/ checkouts is
# used. Every command and its exit code is written to <Workspace>\acceptance.log (UTF-8).
#
#   powershell -ExecutionPolicy Bypass -File tools\acceptance\run_acceptance.ps1 -Workspace D:\aipe-acceptance [-ToolsDir <dir>]
#
# -ToolsDir (or "tools_dir" in sources.json) points at the portable engineering tools that are not on PATH (ngspice, Elmer);
# KiCad, FreeCAD and Gmsh are located by `aipe-workflows doctor` itself. The same file lives at tools/acceptance/ in
# AIPE-Workflows and at stabilisation/acceptance/ in the integration workspace.
#
param(
    [string]$Workspace = "D:\aipe-acceptance",
    [string]$SourcesPath = "$PSScriptRoot\sources.json",
    [string]$ToolsDir = "",
    [switch]$SkipClone,
    [switch]$DryRun
)
$ErrorActionPreference = "Stop"
$env:PYTHONUTF8 = "1"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$log = Join-Path $Workspace "acceptance.log"
New-Item -ItemType Directory -Force $Workspace | Out-Null
$script:lastExit = 0
function Log($text) { Write-Host $text; Add-Content -Path $log -Value $text -Encoding UTF8 }
function Step($name) { Log ""; Log "=== [$(Get-Date -Format HH:mm:ss)] $name ===" }
function Run($cmd, [int[]]$AllowExit = @(0), [string]$Cwd = "") {
    Log "> $cmd"
    if ($DryRun) { $script:lastExit = 0; return }
    $prev = Get-Location
    if ($Cwd) { Set-Location -LiteralPath $Cwd }
    try { cmd /c "$cmd 2>&1" | ForEach-Object { Log "$_" }; $code = $LASTEXITCODE } finally { Set-Location $prev }
    $script:lastExit = $code
    Log "[exit $code]"
    if ($AllowExit -notcontains $code) { throw "command failed ($code): $cmd" }
}

$sourcesObj = Get-Content -LiteralPath $SourcesPath -Raw | ConvertFrom-Json
$repos = @($sourcesObj.repositories | ForEach-Object { $_ })
$toolsDir = if ($ToolsDir) { $ToolsDir } else { [string]$sourcesObj.tools_dir }
$today = Get-Date -Format yyyy-MM-dd
if ($repos.Count -lt 2 -or -not $repos[0].name) { throw "sources file $SourcesPath did not parse into a repository list" }
foreach ($s in $repos) { if (-not $s.name -or -not $s.url) { throw "sources entry without name/url: $($s | ConvertTo-Json -Compress)" } }
Step "0. Sources: $SourcesPath ($($repos.Count) repositories, tools $toolsDir)"

Step "1. Clone repositories into $Workspace"
foreach ($s in $repos) {
    $dest = Join-Path $Workspace $s.name
    if ($SkipClone -and (Test-Path $dest)) {
        Log "(kept existing checkout $dest)"
    } else {
        if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
        Run "git clone -q $($s.url) `"$dest`""
        if ($s.ref) { Run "git -C `"$dest`" fetch -q origin $($s.ref)"; Run "git -C `"$dest`" checkout -q FETCH_HEAD" }
    }
    if (-not $DryRun) {
        $sha = (git -C $dest rev-parse HEAD).Trim()
        $refText = if ($s.ref) { $s.ref } else { "default branch" }
        Log "$($s.name) @ $sha (ref: $refText)"
    }
}

Step "2. Fresh virtual environment and README install commands"
$venv = Join-Path $Workspace ".venv"
if (-not (Test-Path $venv)) { Run "python -m venv `"$venv`"" }
$py = Join-Path $venv "Scripts\python.exe"
$pyq = "`"$py`""
Run "$pyq -m pip install --upgrade pip --quiet"
foreach ($s in $repos) {
    $dest = Join-Path $Workspace $s.name
    if ($s.requirements) { Run "$pyq -m pip install --quiet -r `"$(Join-Path $dest $s.requirements)`"" }
    if ($s.install) { Run "$pyq -m pip install --quiet $($s.install) `"$dest$($s.extras)`"" }
}
Run "$pyq -m pip list --format=freeze"

Step "3. Tool qualification (ngspice, FreeCAD, KiCad, Elmer known-answer cases)"
$env:AIPE_TOOLS_DIR = $toolsDir
Run "$pyq -m aipe_workflows.cli doctor --qualify --workspace `"$Workspace`" --json --out `"$Workspace\doctor.json`""

Step "4. Core and Registry contracts (each repository's documented test commands)"
foreach ($s in $repos) {
    if ($s.tests) {
        $dest = Join-Path $Workspace $s.name
        foreach ($t in @($s.tests)) { Run ($t.Replace("{py}", $pyq).Replace("{today}", $today)) -Cwd $dest }
    }
}

Step "5-16. DAB workflow: plan, run, verify, report"
$spec = Join-Path $Workspace "AIPE-Workflows\examples\dab-10kw\specification.yaml"
$wf = Join-Path $Workspace "AIPE-Workflows\workflows\converter_dab\workflow.yaml"
$run = Join-Path $Workspace "runs\dab-acceptance"
Run "$pyq -m aipe_workflows.cli plan `"$spec`" --checkouts `"$Workspace`" --workflow `"$wf`" --run-dir `"$run`" --json"
# exit 2 = completed_with_blocked / completed_with_failed_optional (an optional task such as pcb-erc-drc fails by design
# while boards still have open connections); the status is recorded and judged in the report, never hidden.
Run "$pyq -m aipe_workflows.cli run `"$spec`" --checkouts `"$Workspace`" --workflow `"$wf`" --run-dir `"$run`"" -AllowExit 0,2
$runExit = $script:lastExit
Run "$pyq -m aipe_workflows.cli verify `"$run`" --core `"$Workspace\AIPE-Core`""
Run "$pyq -m aipe_workflows.cli report `"$run`""
Run "$pyq -m aipe_workflows.cli status `"$run`""
Step "done: workflow run exit $runExit (0 = completed, 2 = completed with blocked or failed optional tasks); see $log, $run\report\report.md and $run\verification.json"
