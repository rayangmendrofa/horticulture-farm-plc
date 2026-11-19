# Upload GH-1 to the OpenPLC Runtime v4 on this PC with the Editor's CLI, without typing the
# login on the command line. Adapted from plc-batch-station.
#
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\openplc_runtime.ps1 upload -CreateUser   # first upload on a new runtime: creates the login
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\openplc_runtime.ps1 upload               # later uploads
#   powershell -NoProfile -ExecutionPolicy Bypass -File tools\openplc_runtime.ps1 upload -PlantPort 5021
#
# The project is regenerated from plc/greenhouse.st first, so the upload always matches the
# tested program. The username and password are read from the keyboard (the password hidden),
# handed to openplc-cli through environment variables of this process only, and cleared afterwards.
param(
    [Parameter(Position = 0)][ValidateSet("upload")][string]$Action = "upload",
    [string]$RuntimeHost = "127.0.0.1",
    [int]$PlantPort = 5020,
    [switch]$CreateUser
)
$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
$project = Join-Path $repo "openplc\GH1_Greenhouse"
$target = "OpenPLC Runtime v4"

$py = (Get-Command py -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command python -ErrorAction Stop).Source }
& $py (Join-Path $repo "tools\make_openplc_project.py") --plant-port $PlantPort
if ($LASTEXITCODE -ne 0) { throw "project generation failed" }

$cli = (Get-Command openplc-cli -ErrorAction SilentlyContinue).Source
if (-not $cli) { $cli = Join-Path $env:LOCALAPPDATA "Programs\openplc-cli\openplc-cli.cmd" }
if (-not (Test-Path $cli)) { throw "openplc-cli not found. Start OpenPLC Editor once so it installs the CLI." }

$cliArgs = @("upload", $project, "--host", $RuntimeHost, "--target", $target, "-y", "--no-json")
if ($CreateUser) { $cliArgs += "--create-user" }

$user = Read-Host "Runtime username"
$secure = Read-Host "Runtime password" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $env:OPENPLC_USER = $user
    $env:OPENPLC_PASSWORD = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
    & $cli @cliArgs
    $code = $LASTEXITCODE
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    Remove-Item Env:OPENPLC_USER, Env:OPENPLC_PASSWORD -ErrorAction SilentlyContinue
}
$meaning = @{ 0 = "OK"; 2 = "usage error"; 3 = "project not found"; 4 = "compile error"; 5 = "cannot reach the runtime";
              6 = "login rejected"; 7 = "target error"; 8 = "timeout" }
$text = if ($meaning.ContainsKey($code)) { $meaning[$code] } else { "see output above" }
Write-Host "openplc-cli exit code ${code}: $text"
exit $code
