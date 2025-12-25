# VSCode terminali açılınca ortak profili yükle
if (Test-Path $PROFILE.CurrentUserAllHosts) { . $PROFILE.CurrentUserAllHosts }
$rt = "$HOME\OneDrive\Belgeler\PowerShell\regtech_profile.ps1"
if (Test-Path $rt) { . $rt }
