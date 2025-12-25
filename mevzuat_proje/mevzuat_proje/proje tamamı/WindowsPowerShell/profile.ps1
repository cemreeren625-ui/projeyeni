#region conda initialize
# !! Contents within this block are managed by 'conda init' !!
$global:REGTECH_ROOT = "C:\Users\cemre\OneDrive\Desktop\ollamak\mevzuat_django"
$condaExe = "$env:USERPROFILE\miniconda3\Scripts\conda.exe"
if (Test-Path $condaExe) {
    (& $condaExe "shell.powershell" "hook") | Out-String | Where-Object { $_ } | Invoke-Expression
} else {
    Write-Verbose "conda.exe not found at $condaExe — skipping conda hook." -Verbose:$false
}
#endregion

#region mamba initialize (optional, guarded)
# !! Contents within this block are managed by 'mamba shell init' !!
$Env:MAMBA_ROOT_PREFIX = "$env:USERPROFILE\.local\share\mamba"
$Env:MAMBA_EXE        = "$env:USERPROFILE\miniconda3\Library\bin\mamba.exe"

if (Test-Path $Env:MAMBA_EXE) {
    (& $Env:MAMBA_EXE 'shell' 'hook' -s 'powershell' -r $Env:MAMBA_ROOT_PREFIX) | Out-String | Where-Object { $_ } | Invoke-Expression
} else {
    # mamba yoksa sessizce geç
    Remove-Item Env:\MAMBA_EXE -ErrorAction SilentlyContinue
    Remove-Item Env:\MAMBA_ROOT_PREFIX -ErrorAction SilentlyContinue
    # Write-Verbose "mamba.exe not found — skipping mamba hook." -Verbose:$false
}
# --- RegTech helpers'ı yükle (ayrı dosyada) ---
$rt = Join-Path $PSScriptRoot "regtech_profile.ps1"
if (Test-Path $rt) { . $rt }

#endregion
function regcheck {
  param(
    [switch]$AutoStartServer,
    [switch]$StopServerAfter,
    [string]$ReportPath = ".\smoke_report.json"
  )

  Use-RegTechRoot {
    Ensure-RegTechEnv
    python manage.py test mevzuat_parca -v 2
    if($LASTEXITCODE -ne 0){ throw "Unit testler FAIL. Smoke calistirmadim." }

    run_smoke -AutoStartServer:$AutoStartServer -StopServerAfter:$StopServerAfter -ReportPath $ReportPath
  }
}
function regdaily {
  param(
    [string]$ReportPath = ".\smoke_report.json",
    [switch]$CopyToClipboard,
    [string]$AppendPath = ".\bughunler.md"
  )

  Use-RegTechRoot {
    regcheck -AutoStartServer -StopServerAfter -ReportPath $ReportPath
    gunluk_smoke -ReportPath $ReportPath -CopyToClipboard:$CopyToClipboard -AppendPath $AppendPath
  }
}
function regnote {
  param(
    [switch]$CopyToClipboard,
    [string]$AppendPath = ".\bughunler.md",
    [switch]$Show,
    [switch]$Open,
    [string]$SavePath = ".\last_regnote.txt"
  )

  Use-RegTechRoot {
    regdaily -CopyToClipboard:$CopyToClipboard -AppendPath $AppendPath

    if($Show){
      gunluk_smoke -ReportPath ".\smoke_report.json" -Show
    }

    $note = Get-Clipboard -Raw
    if(-not [string]::IsNullOrWhiteSpace($note)){
      $dir = Split-Path -Parent $SavePath
      if(-not [string]::IsNullOrWhiteSpace($dir) -and $dir -ne "." -and -not (Test-Path $dir)){
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
      }

      $note | Set-Content -Encoding utf8 -Path $SavePath
      Write-Host "[OK] regnote: not kaydedildi -> $SavePath"

      $stamp = Get-Date -Format "yyyy-MM-dd_HHmm"
      $archiveDir = ".\notes"
      if(-not (Test-Path $archiveDir)){ New-Item -ItemType Directory -Force -Path $archiveDir | Out-Null }
      $archivePath = Join-Path $archiveDir ("regnote_{0}.txt" -f $stamp)
      $note | Set-Content -Encoding utf8 -Path $archivePath
      Write-Host "[OK] regnote: arsiv -> $archivePath"

      if($Open){ notepad $SavePath }
    } else {
      Write-Warning "Clipboard bos geldi. regnote'u -CopyToClipboard ile calistir: regnote -CopyToClipboard -Show -Open"
    }
  }
}
# =========================
# RegTech shortcuts (START)
# =========================

$rt = "$HOME\OneDrive\Belgeler\WindowsPowerShell\regtech_profile.ps1"
if (Test-Path $rt) { . $rt }

