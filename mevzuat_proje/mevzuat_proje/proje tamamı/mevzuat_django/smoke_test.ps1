param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [int]$CompanyId = 1,
  [int]$ObligationId = 1
)

# UTF-8 çıktıyı garantiye al
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()
$OutputEncoding = [Console]::OutputEncoding

function Invoke-ApiJsonUtf8 {
  param(
    [Parameter(Mandatory=$true)][ValidateSet("GET","POST","PATCH","PUT","DELETE")]$Method,
    [Parameter(Mandatory=$true)][string]$Uri,
    [string]$JsonBody = $null
  )
  $tmp = Join-Path $env:TEMP "resp.json"

  if ($null -ne $JsonBody) {
    Invoke-WebRequest -Method $Method -Uri $Uri -ContentType "application/json" -Body $JsonBody -OutFile $tmp | Out-Null
  } else {
    Invoke-WebRequest -Method $Method -Uri $Uri -OutFile $tmp | Out-Null
  }

  (Get-Content $tmp -Raw -Encoding utf8) | ConvertFrom-Json
}

function Ok($msg){ Write-Host "[OK]  $msg" }
function Fail($msg){ Write-Host "[FAIL] $msg"; exit 1 }

try {
  # 1) GET eski dashboard JSON
  $u1 = "$BaseUrl/api/companies/$CompanyId/dashboard/"
  $dash = Invoke-ApiJsonUtf8 GET $u1
  if(-not $dash.sirket){ Fail "dashboard JSON: sirket yok ($u1)" }
  Ok "dashboard JSON geliyor: $($dash.sirket.name)"

  # 2) GET SPA dashboard JSON
  $u2 = "$BaseUrl/api/companies-spa/$CompanyId/dashboard/"
  $spa = Invoke-ApiJsonUtf8 GET $u2
  if(-not $spa.sirket){ Fail "spa dashboard JSON: sirket yok ($u2)" }
  Ok "spa dashboard JSON geliyor: $($spa.sirket.name)"

  # 3) PATCH obligation toggle -> true
  $u3 = "$BaseUrl/api/obligations/$ObligationId/status/"
  $afterTrue = Invoke-ApiJsonUtf8 PATCH $u3 '{"is_compliant": true}'
  if(-not $afterTrue.sirket){ Fail "PATCH true: response sirket yok ($u3)" }
  Ok "PATCH true çalıştı (company=$($afterTrue.sirket.name))"

  # 4) PATCH obligation toggle -> false
  $afterFalse = Invoke-ApiJsonUtf8 PATCH $u3 '{"is_compliant": false}'
  if(-not $afterFalse.sirket){ Fail "PATCH false: response sirket yok ($u3)" }
  Ok "PATCH false çalıştı (company=$($afterFalse.sirket.name))"

  # 5) Basit anahtar kontrolü
  $needKeys = @("uyum_skoru","stats","todo","completed")
  foreach($k in $needKeys){
    if(-not ($dash.PSObject.Properties.Name -contains $k)){ Fail "dashboard JSON key eksik: $k" }
  }
  Ok "dashboard JSON key seti tamam"

  Write-Host ""
  Write-Host "ALL GREEN ✅"
}
catch {
  Fail $_.Exception.Message
}
