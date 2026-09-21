Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "   TOPH-IVR: Trinay Orthopedic Hospital Doctor Appointment System" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

Write-Host "[1/4] Checking for conflicting Asterisk containers..." -ForegroundColor Yellow
$conflicting = docker ps -q -f "name=asterisk_ivr_pbx" 2>$null
if ($conflicting) {
    Write-Host "Stopping conflicting container asterisk_ivr_pbx..." -ForegroundColor DarkYellow
    docker stop asterisk_ivr_pbx | Out-Null
}

Write-Host "[2/4] Initializing Database..." -ForegroundColor Yellow
python scripts/seed_db.py

Write-Host "[3/4] Starting Asterisk & FastAGI IVR Container..." -ForegroundColor Yellow
docker compose up -d

Write-Host ""
Write-Host "[4/4] Verifying Asterisk PBX Status..." -ForegroundColor Yellow
Start-Sleep -Seconds 3
docker exec asterisk-gujarati-ivr asterisk -rx "core show uptime"
docker exec asterisk-gujarati-ivr asterisk -rx "pjsip show endpoints"

Write-Host ""
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host " SYSTEM READY! CONNECT VIA MICROSIP" -ForegroundColor Green
Write-Host "==============================================================================" -ForegroundColor Green
Write-Host " In MicroSIP:" -ForegroundColor White
Write-Host "   1. Go to Menu -> Add Account:" -ForegroundColor White
Write-Host "      - Account Name: Asterisk IVR" -ForegroundColor Gray
Write-Host "      - SIP Server:   127.0.0.1" -ForegroundColor Gray
Write-Host "      - SIP Proxy:    (leave blank)" -ForegroundColor Gray
Write-Host "      - Username:     100" -ForegroundColor Gray
Write-Host "      - Domain:       127.0.0.1" -ForegroundColor Gray
Write-Host "      - Login:        100" -ForegroundColor Gray
Write-Host "      - Password:     secretpassword123" -ForegroundColor Gray
Write-Host "      - Transport:    TCP (or UDP)" -ForegroundColor Gray
Write-Host "   2. Click Save. The bottom-left status should show 'Online' (Green)." -ForegroundColor White
Write-Host "   3. In the dialer, type 1000 and click Call!" -ForegroundColor White
Write-Host "==============================================================================" -ForegroundColor Green
