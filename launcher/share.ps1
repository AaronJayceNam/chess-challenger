$ErrorActionPreference = "SilentlyContinue"
$host.UI.RawUI.WindowTitle = "Chess Challenger - Public Link"

# locate cloudflared (PATH first, then winget install dir)
$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) {
  $cf = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe\cloudflared.exe"
}
if (-not (Test-Path $cf)) {
  Write-Host "cloudflared 가 설치되어 있지 않습니다. 설치: winget install Cloudflare.cloudflared" -ForegroundColor Red
  Read-Host "엔터를 누르면 종료"; exit
}

# make sure the app is running
try { Invoke-WebRequest 'http://127.0.0.1:8000/api/health' -UseBasicParsing -TimeoutSec 2 | Out-Null }
catch {
  Write-Host "앱이 꺼져 있습니다. 먼저 바탕화면의 'Chess Challenger' 아이콘으로 앱을 켠 뒤 다시 실행하세요." -ForegroundColor Red
  Read-Host "엔터를 누르면 종료"; exit
}

$log = Join-Path $env:TEMP "cc_tunnel.log"
Remove-Item $log -ErrorAction SilentlyContinue
$p = Start-Process -FilePath $cf -ArgumentList "tunnel","--url","http://localhost:8000" -RedirectStandardError $log -PassThru -WindowStyle Hidden

Write-Host ""
Write-Host "공개 주소를 만드는 중입니다... 잠시만 기다리세요." -ForegroundColor Cyan

$url = $null
for ($i = 0; $i -lt 45; $i++) {
  Start-Sleep -Milliseconds 700
  $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($m) { $url = $m.Matches[0].Value; break }
}

Clear-Host
Write-Host ""
if ($url) {
  Set-Clipboard -Value $url
  Write-Host "  ============================================================" -ForegroundColor Green
  Write-Host "    공개 주소가 만들어졌습니다!  아래 주소를 친구에게 보내세요" -ForegroundColor Green
  Write-Host "  ============================================================" -ForegroundColor Green
  Write-Host ""
  Write-Host "      $url" -ForegroundColor Yellow
  Write-Host ""
  Write-Host "    (이 주소는 클립보드에 복사되었습니다 - 바로 붙여넣기 가능)" -ForegroundColor DarkGray
  Write-Host ""
  Write-Host "    * 이 창을 열어 두는 동안에만 주소가 작동합니다." -ForegroundColor DarkGray
  Write-Host "    * 공유를 끝내려면 이 창을 닫으세요." -ForegroundColor DarkGray
  Write-Host "  ============================================================" -ForegroundColor Green
} else {
  Write-Host "  주소 생성에 실패했습니다. 인터넷 연결을 확인하고 다시 시도하세요." -ForegroundColor Red
}
Write-Host ""
Wait-Process -Id $p.Id -ErrorAction SilentlyContinue
