function run_smoke {
  param(
    [string]$BaseUrl="http://127.0.0.1:8000",
    [int]$CompanyId=1,
    [int]$ObligationId=1,
    [switch]$AutoStartServer,
    [switch]$StopServerAfter,
    [switch]$Quiet,
    [string]$DumpJsonDir="",
    [int]$TimeoutMs=3000
  )

  $root = Get-RegTechRoot
  $p = Join-Path $root "run_smoke.ps1"
  if(-not (Test-Path $p)){ throw "run_smoke.ps1 bulunamadi: $p" }

  & $p -BaseUrl $BaseUrl -CompanyId $CompanyId -ObligationId $ObligationId `
      -AutoStartServer:$AutoStartServer -StopServerAfter:$StopServerAfter `
      -Quiet:$Quiet -DumpJsonDir $DumpJsonDir -TimeoutMs $TimeoutMs
}

$rt = "$HOME\OneDrive\Belgeler\PowerShell\regtech_profile.ps1"
if (Test-Path $rt) { . $rt }
