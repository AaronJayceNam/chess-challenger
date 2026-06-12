$ErrorActionPreference = "SilentlyContinue"
$host.UI.RawUI.WindowTitle = "Chess Challenger - Public Link"
$proj = "C:\Users\jayce\chess-coach"
$pyw  = "$proj\.venv\Scripts\pythonw.exe"
$url  = "http://127.0.0.1:8000"

function App-Up {
  try { Invoke-WebRequest "$url/api/health" -UseBasicParsing -TimeoutSec 2 | Out-Null; return $true }
  catch { return $false }
}

# locate cloudflared
$cf = (Get-Command cloudflared -ErrorAction SilentlyContinue).Source
if (-not $cf) { $cf = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Cloudflare.cloudflared_Microsoft.Winget.Source_8wekyb3d8bbwe\cloudflared.exe" }
if (-not (Test-Path $cf)) {
  Write-Host "cloudflared 가 설치되어 있지 않습니다. 설치: winget install Cloudflare.cloudflared" -ForegroundColor Red
  Read-Host "엔터를 누르면 종료"; exit
}

# 1) make sure the app is running; if not, start it (so the link never shows a Cloudflare error)
if (-not (App-Up)) {
  Write-Host "앱 서버를 켜는 중입니다..." -ForegroundColor Cyan
  $env:PORT = "8000"
  Start-Process -FilePath $pyw -ArgumentList @("-m","webapp.run_bg") -WorkingDirectory $proj -WindowStyle Hidden
  for ($i = 0; $i -lt 25; $i++) { Start-Sleep -Milliseconds 600; if (App-Up) { break } }
}
if (-not (App-Up)) {
  Write-Host "앱 서버를 켜지 못했습니다. 먼저 'Chess Challenger' 아이콘으로 앱을 켠 뒤 다시 시도하세요." -ForegroundColor Red
  Read-Host "엔터를 누르면 종료"; exit
}

# 2) start the tunnel and wait for the public address
$log = Join-Path $env:TEMP "cc_tunnel.log"
Remove-Item $log -ErrorAction SilentlyContinue
$tunnel = Start-Process -FilePath $cf -ArgumentList "tunnel","--url",$url -RedirectStandardError $log -PassThru -WindowStyle Hidden

Write-Host ""
Write-Host "공개 주소를 만드는 중입니다... (10~30초 정도 걸릴 수 있어요)" -ForegroundColor Cyan
$public = $null
for ($i = 0; $i -lt 60; $i++) {
  Start-Sleep -Milliseconds 700
  $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($m) { $public = $m.Matches[0].Value; break }
  if ($i % 5 -eq 0) { Write-Host "." -NoNewline -ForegroundColor DarkGray }
}

if ($public) {
  # The trycloudflare address takes a few seconds to become reachable. Wait for
  # it to actually answer before opening the browser, so you never see a
  # "this page can't be reached" error.
  Write-Host ""
  Write-Host "주소를 활성화하는 중입니다... (몇 초 더 걸립니다)" -ForegroundColor Cyan
  $ready = $false
  for ($i = 0; $i -lt 40; $i++) {
    try { $r = Invoke-WebRequest "$public/api/health" -UseBasicParsing -TimeoutSec 4; if ($r.StatusCode -eq 200) { $ready = $true; break } } catch {}
    Start-Sleep 1
    if ($i % 4 -eq 0) { Write-Host "." -NoNewline -ForegroundColor DarkGray }
  }

  $public | clip
  Set-Clipboard -Value $public
  if ($ready) { Start-Process $public }   # only open once it actually works

  Clear-Host
  Write-Host ""
  Write-Host "  ============================================================" -ForegroundColor Green
  Write-Host "    공개 주소가 만들어졌습니다!  아래 주소를 친구에게 보내세요" -ForegroundColor Green
  Write-Host "  ============================================================" -ForegroundColor Green
  Write-Host ""
  Write-Host "      $public" -ForegroundColor Yellow
  Write-Host ""
  if ($ready) {
    Write-Host "    - 방금 이 주소가 브라우저에 열렸습니다 (정상 작동 확인됨)" -ForegroundColor DarkGray
  } else {
    Write-Host "    - 주소가 아직 준비 중일 수 있습니다. 안 열리면 10초 뒤 새로고침하세요." -ForegroundColor Yellow
  }
  Write-Host "    - 이 주소가 클립보드에 복사되었습니다 (카톡 등에 바로 붙여넣기)" -ForegroundColor DarkGray
  Write-Host ""
  Write-Host "    [중요] 이 창을 닫으면 주소도 즉시 사라집니다." -ForegroundColor Yellow
  Write-Host "           매번 새로 실행하면 주소가 바뀌니, 예전 주소는 쓰지 마세요." -ForegroundColor Yellow
  Write-Host "  ============================================================" -ForegroundColor Green
} else {
  Write-Host "  공개 주소 생성에 실패했습니다." -ForegroundColor Red
  Write-Host "  - 인터넷 연결을 확인하고 이 창을 닫은 뒤 다시 실행해 주세요." -ForegroundColor Gray
  Write-Host "  - (이전에 복사해 둔 다른 링크가 클립보드에 남아 있을 수 있으니," -ForegroundColor Gray
  Write-Host "     주소가 위에 노란색으로 안 보이면 아직 만들어지지 않은 것입니다.)" -ForegroundColor Gray
  Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue
  Read-Host "엔터를 누르면 종료"; exit
}
Write-Host ""
Wait-Process -Id $tunnel.Id -ErrorAction SilentlyContinue
