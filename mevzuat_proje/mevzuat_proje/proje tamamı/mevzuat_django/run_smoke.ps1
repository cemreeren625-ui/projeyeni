# ============================================================
# RegTech run_smoke.ps1
# Amaç:
# - Django server ayakta mı kontrol et
# - /api/companies/<id>/dashboard/ ile
#   /api/companies-spa/<id>/dashboard/ payload'ları birebir aynı mı bak
# - obligation PATCH (true/false) çalışıyor mu kontrol et
# - todo/completed/stats tutarlılığını (invariant) doğrula
# - İstersen smoke_report.json raporu yaz
# - İstersen server kapalıysa otomatik aç, iş bitince (sadece kendisi açtıysa) kapat
# ============================================================

# NOT: -StopServerAfter sadece bu script -AutoStartServer ile actiysa kapatir.
[CmdletBinding()]
param(
  # Django base URL (sonunda / olmasa da olur)
  [string] $BaseUrl         = "http://127.0.0.1:8000",

  # Test edilecek şirket id
  [int]    $CompanyId       = 1,

  # PATCH ile tamamla/geri al denemesi yapılacak obligation id
  [int]    $ObligationId    = 1,

  # HTTP isteği zaman aşımı (ms)
  [int]    $TimeoutMs       = 3000,

  # AutoStartServer ile runserver açılırsa bekleme süresi (ms)
  [int]    $StartWaitMs     = 12000,

  # Terminali susturur (OK logları basılmaz)
  [switch] $Quiet,

  # Eğer doluysa her response JSON'u bu klasöre dump eder (debug)
  [string] $DumpJsonDir     = "",

  # Server kapalıysa script runserver ile otomatik açmayı dener
  [switch] $AutoStartServer,

  # Server'i script açtıysa, iş bitince kapatır
  [switch] $StopServerAfter,

  # Rapor JSON yazılacak path (boşsa rapor yazmaz)
  [string] $ReportPath  = "",

  # (Şu an bu scriptte aktif kullanılmıyor; ileride append/log için bırakılmış)
  [string] $AppendPath = ""
)

# ------------------------------
# UTF-8 konsol / çıktı düzeltmesi (PS 5.1 uyumlu)
# Türkçe karakter bozulmalarını azaltır
# ------------------------------
try { chcp 65001 | Out-Null } catch {}
try {
  [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
  $OutputEncoding = [Console]::OutputEncoding
} catch {}

# Hata olunca stopla (try/catch içinde yakalanacak)
$ErrorActionPreference = "Stop"

# Kısa log helpers
function Write-Ok([string]$msg){ if(-not $Quiet){ Write-Host "[OK]  $msg" } }
function Fail([string]$msg){ throw "[FAIL] $msg" }

# Bu script server başlattı mı? Başlattıysa PID vs takip ediyoruz
$script:StartedByThisScript = $false
$script:StartedPid = $null

# ------------------------------------------------------------
# Django env değişkenlerini garanti altına al
# - DJANGO_DEBUG
# - DJANGO_ALLOWED_HOSTS
# - DJANGO_SECRET_KEY (yoksa python ile otomatik üret)
# ------------------------------------------------------------
function Ensure-DjangoEnv {
  if([string]::IsNullOrWhiteSpace($env:DJANGO_DEBUG)){
    $env:DJANGO_DEBUG = "1"
  }

  if([string]::IsNullOrWhiteSpace($env:DJANGO_ALLOWED_HOSTS)){
    $env:DJANGO_ALLOWED_HOSTS = "127.0.0.1,localhost"
  }

  if([string]::IsNullOrWhiteSpace($env:DJANGO_SECRET_KEY)){

    $code = 'from django.core.management.utils import get_random_secret_key as g; print(g())'

    # Önce python (conda env) dene
    $py = Get-Command python -ErrorAction SilentlyContinue
    if($py){
      try {
        $sk = & $py.Source -c $code
        $env:DJANGO_SECRET_KEY = ($sk | Select-Object -First 1).Trim()
        return
      } catch {
        # python denemesi başarısız oldu, py launcher'a düşeceğiz
      }
    }

    # python yoksa py -3 dene (Windows python launcher)
    $pyLauncher = Get-Command py -ErrorAction SilentlyContinue
    if($pyLauncher){
      try {
        $sk = & $pyLauncher.Source -3 -c $code
        $env:DJANGO_SECRET_KEY = ($sk | Select-Object -First 1).Trim()
        return
      } catch {
        Fail "SECRET_KEY uretilmedi. Ortami aktif ettigine emin ol (conda env) ve django kurulu mu kontrol et."
      }
    }

    Fail "SECRET_KEY uretilmedi: python/py bulunamadi. Once conda env aktif mi kontrol et."
  }
}

# BaseUrl normalize et (http ekle, sondaki / kaldır)
function Normalize-BaseUrl([string]$u){
  if([string]::IsNullOrWhiteSpace($u)){ $u = "http://127.0.0.1:8000" }
  $u = $u.Trim()
  if($u -notmatch '^https?://'){ $u = "http://$u" }
  if($u.EndsWith("/")){ $u = $u.TrimEnd("/") }
  return $u
}

# Uri portunu çıkar (belirtilmemişse http/https default)
function Get-UriPort([Uri]$u){
  if($u.Port -ge 1){ return $u.Port }
  if($u.Scheme -eq "https"){ return 443 }
  return 80
}

# Not: Bu fonksiyon sadece “sunucu cevap veriyor mu?” gibi bir kontrol için yazılmış.
# 404 bile gelse "response geldi" demektir -> true dönüyor.
function Test-HttpReachable([string]$url, [int]$timeoutMs){
  try{
    $req = [System.Net.HttpWebRequest]::Create($url)
    $req.Method = "GET"
    $req.Timeout = $timeoutMs
    $req.AllowAutoRedirect = $false
    $resp = $req.GetResponse()
    $resp.Close()
    return $true
  } catch {
    if($_.Exception -and $_.Exception.Response){
      try { $_.Exception.Response.Close() } catch {}
      return $true
    }
    return $false
  }
}

# TCP port açık mı? belli bir süre bekleyerek kontrol eder
function Wait-ServerReady([string]$BaseUrl, [int]$TimeoutMs=60000, [int]$IntervalMs=400){
  $u = [Uri]$BaseUrl
  $port = Get-UriPort $u

  $deadline = (Get-Date).AddMilliseconds($TimeoutMs)
  while((Get-Date) -lt $deadline){
    $ok = (Test-NetConnection -ComputerName $u.Host -Port $port -WarningAction SilentlyContinue).TcpTestSucceeded
    if($ok){ return $true }
    Start-Sleep -Milliseconds $IntervalMs
  }
  return $false
}

# (Legacy/ek helper) Eğer SECRET_KEY boşsa bir kez daha denemek için bırakılmış
function Ensure-DjangoSecretKey(){
  if([string]::IsNullOrWhiteSpace($env:DJANGO_SECRET_KEY)){
    try {
      $env:DJANGO_SECRET_KEY = (python -c "from django.core.management.utils import get_random_secret_key as g; print(g())")
    } catch {}
  }
}

# ------------------------------
# Server process tracking
# ------------------------------
$script:StartedServer = $false
$script:ServerProc    = $null
$script:ServerOut     = $null
$script:ServerErr     = $null

# Django dev server başlatır (manage.py runserver)
function Start-DjangoServer([string]$BaseUrl){
  Ensure-DjangoEnv   # env'ler server başlamadan önce set edilsin

  $u = [Uri]$BaseUrl
  $port = Get-UriPort $u
  $hostname = $u.Host
  $bind = "{0}:{1}" -f $hostname, $port

  # Scriptin bulunduğu klasörü root kabul ediyoruz (manage.py burada olmalı)
  $root = $PSScriptRoot
  if([string]::IsNullOrWhiteSpace($root)){
    $root = Split-Path -Parent $MyInvocation.MyCommand.Path
  }

  # python (conda env) varsa onu kullan
  $pyCmd = Get-Command python -ErrorAction SilentlyContinue
  if($pyCmd){
    $pyPath = $pyCmd.Source
    $args = @("manage.py","runserver",$bind,"--noreload")
  } else {
    # yoksa py launcher kullan
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if(-not $pyCmd){ Fail "python/py bulunamadi. Once conda env aktif mi kontrol et." }
    $pyPath = $pyCmd.Source
    $args = @("-3","manage.py","runserver",$bind,"--noreload")
  }

  # stdout/stderr loglarını temp'e al (debug için)
  $script:ServerOut = Join-Path $env:TEMP ("runserver_{0}_out.log" -f ([Guid]::NewGuid().ToString("N")))
  $script:ServerErr = Join-Path $env:TEMP ("runserver_{0}_err.log" -f ([Guid]::NewGuid().ToString("N")))

  Write-Ok "Server yok, runserver baslatiliyor..."

  # Arka planda başlat
  $p = Start-Process -FilePath $pyPath -ArgumentList $args -WorkingDirectory $root `
        -PassThru -WindowStyle Hidden -RedirectStandardOutput $script:ServerOut -RedirectStandardError $script:ServerErr

  $script:StartedByThisScript = $true
  $script:StartedPid = $p.Id
  $script:StartedServer = $true
  $script:ServerProc = $p

  # Port hazır olana kadar bekle
  if(-not (Wait-ServerReady $BaseUrl 60000 400)){
    Write-Host "[INFO] runserver stdout (tail):"
    if(Test-Path $script:ServerOut){ Get-Content $script:ServerOut -Tail 40 | ForEach-Object { Write-Host $_ } }
    Write-Host "[INFO] runserver stderr (tail):"
    if(Test-Path $script:ServerErr){ Get-Content $script:ServerErr -Tail 80 | ForEach-Object { Write-Host $_ } }
    Fail "Server basladi ama hazir hale gelmedi (timeout)."
  }

  Start-Sleep -Milliseconds 400
  if($p.HasExited){
    Write-Host "[INFO] runserver stdout (tail):"
    if(Test-Path $script:ServerOut){ Get-Content $script:ServerOut -Tail 40 | ForEach-Object { Write-Host $_ } }
    Write-Host "[INFO] runserver stderr (tail):"
    if(Test-Path $script:ServerErr){ Get-Content $script:ServerErr -Tail 80 | ForEach-Object { Write-Host $_ } }
    Fail "Server otomatik baslatilamadi. Manuel: python manage.py runserver"
  }
}

# Server up olana kadar kısa süre bekleme (StartWaitMs için)
function Wait-ServerUp([string]$BaseUrl, [int]$WaitMs){
  $u = [Uri]$BaseUrl
  $port = Get-UriPort $u
  $deadline = (Get-Date).AddMilliseconds($WaitMs)

  while((Get-Date) -lt $deadline){
    $ok = $false
    try {
      $ok = (Test-NetConnection -ComputerName $u.Host -Port $port -WarningAction SilentlyContinue).TcpTestSucceeded
    } catch { $ok = $false }

    if($ok){ return $true }
    Start-Sleep -Milliseconds 250
  }
  return $false
}

# Server açık mı? Kapalıysa AutoStartServer ile açmayı dener.
function Assert-ServerUp([string]$BaseUrl){
  $u = [Uri]$BaseUrl
  $port = Get-UriPort $u

  $ok = $false
  try { $ok = (Test-NetConnection -ComputerName $u.Host -Port $port -WarningAction SilentlyContinue).TcpTestSucceeded } catch {}

  # Kapalıysa ve AutoStartServer verildiyse kendisi açar
  if(-not $ok -and $AutoStartServer){
    Start-DjangoServer $BaseUrl
    $ok = Wait-ServerUp $BaseUrl $StartWaitMs
  }

  # Hâlâ kapalıysa fail
  if(-not $ok){
    if($script:StartedServer){
      Write-Host "[INFO] runserver stdout (tail):"
      if(Test-Path $script:ServerOut){ Get-Content $script:ServerOut -Tail 40 | ForEach-Object { Write-Host $_ } }
      Write-Host "[INFO] runserver stderr (tail):"
      if(Test-Path $script:ServerErr){ Get-Content $script:ServerErr -Tail 80 | ForEach-Object { Write-Host $_ } }
    }
    Fail "Server kapali gibi gorunuyor. Once: python manage.py runserver"
  }

  Write-Ok "Server ayakta: $BaseUrl"
  return $null
}

# Eğer StopServerAfter true ise ve server'i script açtıysa kapatır
function Stop-ServerIfStarted(){
  if(-not $StopServerAfter){ return }

  if(-not $script:StartedServer -or $null -eq $script:ServerProc){
    Write-Ok "Stop atlandi (sunucu bu script tarafindan acilmadi)"
    return
  }

  try {
    Stop-Process -Id $script:ServerProc.Id -Force -ErrorAction Stop
    Write-Ok ("Server durduruldu (pid={0})" -f $script:ServerProc.Id)
  } catch {
    Write-Host ("[WARN] Server durdurulemedi: {0}" -f $_.Exception.Message)
  }
}

# (Legacy) İstersen rapor yazma helper (aşağıda Save-Report zaten var)
function Write-ReportIfRequested([object]$obj){
  if([string]::IsNullOrWhiteSpace($ReportPath)){ return }

  $dir = Split-Path -Parent $ReportPath
  if(-not [string]::IsNullOrWhiteSpace($dir)){
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
  }

  ($obj | ConvertTo-Json -Depth 100 3>$null) | Set-Content -Encoding utf8 -Path $ReportPath
  Write-Host "[INFO] Report yazildi: $ReportPath"
}

# ------------------------------------------------------------
# API çağrısı (UTF-8 garantili):
# - response'u temp dosyaya indir
# - ConvertFrom-Json ile objeye çevir
# - DumpJsonDir verilirse ayrıca dump et
# ------------------------------------------------------------
function Invoke-ApiJsonUtf8([string]$method, [string]$uri, [string]$jsonBody=$null){
  $tmp = Join-Path $env:TEMP ("resp_{0}.json" -f ([Guid]::NewGuid().ToString("N")))

  # PS sürümüne göre TimeoutSec parametresi var mı kontrol et
  $hasTimeout = $false
  try { $hasTimeout = (Get-Command Invoke-WebRequest).Parameters.ContainsKey("TimeoutSec") } catch {}

  if($jsonBody){
    if($hasTimeout){
      Invoke-WebRequest -Method $method -Uri $uri -ContentType "application/json" -Body $jsonBody -OutFile $tmp -TimeoutSec ([Math]::Ceiling($TimeoutMs/1000)) | Out-Null
    } else {
      Invoke-WebRequest -Method $method -Uri $uri -ContentType "application/json" -Body $jsonBody -OutFile $tmp | Out-Null
    }
  } else {
    if($hasTimeout){
      Invoke-WebRequest -Method $method -Uri $uri -OutFile $tmp -TimeoutSec ([Math]::Ceiling($TimeoutMs/1000)) | Out-Null
    } else {
      Invoke-WebRequest -Method $method -Uri $uri -OutFile $tmp | Out-Null
    }
  }

  # JSON’u objeye çevir
  $obj = (Get-Content $tmp -Raw -Encoding utf8) | ConvertFrom-Json

  # Debug dump istenirse response'u sakla
  if($DumpJsonDir){
    New-Item -ItemType Directory -Force -Path $DumpJsonDir | Out-Null
    $stamp = Get-Date -Format "yyyyMMdd_HHmmss_fff"
    $safe = ($method + "_" + ($uri -replace '[^\w\-]+','_')).Trim('_')
    $outp = Join-Path $DumpJsonDir ("{0}_{1}.json" -f $stamp, $safe)
    (Get-Content $tmp -Raw -Encoding utf8) | Set-Content -Encoding utf8 -Path $outp
  }

  return $obj
}

# ------------------------------------------------------------
# Canonical JSON:
# Property sırası farklı olsa bile iki payload aynı mı diye karşılaştırabilmek için
# ------------------------------------------------------------
function Canonicalize($o){
  if($null -eq $o){ return $null }
  if($o -is [string]){ return $o }

  # Array/list ise elemanları canonicalize et
  if($o -is [System.Collections.IEnumerable] -and -not ($o -is [psobject])){
    return @($o | ForEach-Object { Canonicalize $_ })
  }

  # PSObject ise property'leri alfabetik sıraya sokup ordered hash yap
  if($o -is [psobject]){
    $h = [ordered]@{}
    foreach($name in ($o.PSObject.Properties.Name | Sort-Object)){
      $h[$name] = Canonicalize $o.$name
    }
    return $h
  }

  return $o
}

# Canonical JSON string (tek satır) üretir
function CanonicalJson($o){
  (Canonicalize $o | ConvertTo-Json -Depth 100 -Compress 3>$null)
}

# Beklenen key'ler var mı?
function Assert-Keys($obj, [string[]]$keys){
  foreach($k in $keys){
    if(-not ($obj.PSObject.Properties.Name -contains $k)){ Fail "Eksik alan: $k" }
  }
}

# todo/completed listelerinde verilen obligation var mı bul
function Find-Obl($arr, [int]$id){
  if($null -eq $arr){ return $null }
  return ($arr | Where-Object { $_.obligation_id -eq $id } | Select-Object -First 1)
}

# PATCH sonrası obligation doğru listeye geçti mi?
function Assert-Moved([object]$payload, [int]$oblId, [bool]$shouldBeCompleted){
  $inTodo = (Find-Obl $payload.todo $oblId) -ne $null
  $inComp = (Find-Obl $payload.completed $oblId) -ne $null

  if($shouldBeCompleted){
    if(-not $inComp){ Fail "Beklenen: obligation $oblId completed listesinde olmali" }
    if($inTodo){      Fail "Beklenmeyen: obligation $oblId todo listesinde kaldi" }
  } else {
    if(-not $inTodo){ Fail "Beklenen: obligation $oblId todo listesinde olmali" }
    if($inComp){      Fail "Beklenmeyen: obligation $oblId completed listesinde kaldi" }
  }
}

# Stats invariant:
# total == todoCount + completedCount
# open  == todoCount
function Assert-StatsInvariant([object]$payload){
  $todoCount = @($payload.todo).Count
  $compCount = @($payload.completed).Count
  $total = $payload.stats.total_obligations
  $open  = $payload.stats.open_obligations

  if($total -ne ($todoCount + $compCount)){ Fail "Stats tutarsiz: total != todo+completed" }
  if($open -ne $todoCount){                 Fail "Stats tutarsiz: open != todoCount" }
}

# ------------------------------------------------------------
# Report / Step tracking
# ------------------------------------------------------------
function Init-Report {
  $script:Report = [ordered]@{
    started_at    = (Get-Date).ToString("o")
    base_url      = $BaseUrl
    company_id    = $CompanyId
    obligation_id = $ObligationId
    ok            = $false
    steps         = @()
    error         = $null
    payload       = $null
  }
  $script:AllSw = [System.Diagnostics.Stopwatch]::StartNew()
}

function Add-ReportStep([string]$name, [bool]$ok, [int]$ms, $extra=$null){
  $script:Report.steps += [pscustomobject]@{
    name  = $name
    ok    = $ok
    ms    = $ms
    extra = $extra
  }
}

# ReportPath verilmişse raporu yazar
function Save-Report {
  if([string]::IsNullOrWhiteSpace($ReportPath)){ return }  # ReportPath yoksa hiç yazma

  $script:AllSw.Stop()
  $script:Report.total_ms    = [int]$script:AllSw.ElapsedMilliseconds
  $script:Report.finished_at = (Get-Date).ToString("o")

  $dir = Split-Path -Parent $ReportPath
  if(-not [string]::IsNullOrWhiteSpace($dir) -and $dir -ne "."){
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
  }

  ($script:Report | ConvertTo-Json -Depth 100 3>$null) | Set-Content -Encoding utf8 -Path $ReportPath
  Write-Host "[INFO] Report yazildi: $ReportPath"
}

# ============================
# MAIN
# ============================
$BaseUrl = Normalize-BaseUrl $BaseUrl
Init-Report

try {
  # 1) Server kontrol (gerekirse AutoStart)
  $sw = [System.Diagnostics.Stopwatch]::StartNew()
  Assert-ServerUp $BaseUrl | Out-Null
  $sw.Stop()
  Add-ReportStep "server_check" $true ([int]$sw.ElapsedMilliseconds)

  Write-Ok "Smoke basliyor..."

  # Endpointler
  $dashUrl  = "$BaseUrl/api/companies/$CompanyId/dashboard/"
  $spaUrl   = "$BaseUrl/api/companies-spa/$CompanyId/dashboard/"
  $patchUrl = "$BaseUrl/api/obligations/$ObligationId/status/"

  # Beklenen minimum anahtarlar
  $expected = @("sirket","uyum_skoru","stats","todo","completed")

  # 2) GET dashboard
  $sw.Restart()
  $dash = Invoke-ApiJsonUtf8 GET $dashUrl
  Assert-Keys $dash $expected
  if($dash.sirket.id -ne $CompanyId){ Fail "Yanlis sirket geldi: beklenen id=$CompanyId, gelen id=$($dash.sirket.id)" }
  Assert-StatsInvariant $dash
  $sw.Stop()
  Add-ReportStep "get_dashboard" $true ([int]$sw.ElapsedMilliseconds) @{ company_name = $dash.sirket.name }
  Write-Ok ("dashboard JSON geliyor: {0}" -f $dash.sirket.name)

  # 3) GET SPA dashboard + canonical compare
  $sw.Restart()
  $spa = Invoke-ApiJsonUtf8 GET $spaUrl

  # dashboard ve spa dashboard aynı payload mı?
  if((CanonicalJson $dash) -ne (CanonicalJson $spa)){
    Fail "dashboard ile spa dashboard farkli payload donuyor"
  }
  Write-Ok "dashboard ile spa dashboard ayni"

  Assert-Keys $spa $expected
  if($spa.sirket.id -ne $CompanyId){ Fail "Yanlis sirket geldi (SPA): beklenen id=$CompanyId, gelen id=$($spa.sirket.id)" }
  Assert-StatsInvariant $spa

  $sw.Stop()
  Add-ReportStep "get_spa_dashboard" $true ([int]$sw.ElapsedMilliseconds) @{ company_name = $spa.sirket.name }
  Write-Ok ("spa dashboard JSON geliyor: {0}" -f $spa.sirket.name)

  # 4) PATCH true (tamamlandı yap)
  $sw.Restart()
  $afterTrue = Invoke-ApiJsonUtf8 PATCH $patchUrl '{"is_compliant": true}'
  Assert-Keys $afterTrue $expected
  Assert-Moved $afterTrue $ObligationId $true
  Assert-StatsInvariant $afterTrue
  $sw.Stop()
  Add-ReportStep "patch_true" $true ([int]$sw.ElapsedMilliseconds)
  Write-Ok ("PATCH true calisti (company={0})" -f $afterTrue.sirket.name)

  # 5) PATCH false (geri al)
  $sw.Restart()
  $afterFalse = Invoke-ApiJsonUtf8 PATCH $patchUrl '{"is_compliant": false}'
  Assert-Keys $afterFalse $expected
  Assert-Moved $afterFalse $ObligationId $false
  Assert-StatsInvariant $afterFalse
  $sw.Stop()
  Add-ReportStep "patch_false" $true ([int]$sw.ElapsedMilliseconds)
  Write-Ok ("PATCH false calisti (company={0})" -f $afterFalse.sirket.name)

  Write-Ok "dashboard JSON key seti tamam"

  # Rapor payload (istersen raporda ham jsonları da tutuyor)
  $report = [ordered]@{
    timestamp     = (Get-Date).ToString("o")
    base_url      = $BaseUrl
    company_id    = $CompanyId
    obligation_id = $ObligationId
    dash          = $dash
    spa           = $spa
    after_true    = $afterTrue
    after_false   = $afterFalse
  }

  $script:Report.payload = $report

  if(-not $Quiet){
    $check = [char]0x2705
    Write-Host ("ALL GREEN {0}" -f $check)
  }

  $script:Report.ok = $true
}
catch {
  # Hata olursa rapora yaz + exit 1
  $script:Report.ok = $false
  $script:Report.error = $_.ToString()
  Write-Host $_
  exit 1
}
finally {
  # Raporu yaz + server'i (şartlı) kapat
  Save-Report
  Stop-ServerIfStarted
}
