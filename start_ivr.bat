@echo off
title TOPH-IVR Gujarati Doctor Appointment System
color 0A
echo ==============================================================================
echo    TOPH-IVR: Trinay Orthopedic Hospital Doctor Appointment System
echo ==============================================================================
echo.

echo [1/4] Checking for conflicting Asterisk containers...
for /f %%i in ('docker ps -q -f name=asterisk_ivr_pbx 2^>nul') do (
    echo Stopping conflicting container asterisk_ivr_pbx...
    docker stop asterisk_ivr_pbx >nul 2>&1
)

echo [2/4] Initializing Database...
python scripts\seed_db.py

echo [3/4] Starting Asterisk & FastAGI IVR Container...
docker compose up -d

echo.
echo [4/4] Verifying Asterisk PBX Status...
timeout /t 3 /nobreak >nul
docker exec asterisk-gujarati-ivr asterisk -rx "core show uptime"
docker exec asterisk-gujarati-ivr asterisk -rx "pjsip show endpoints"

echo.
echo ==============================================================================
echo  SYSTEM READY! CONNECT VIA MICROSIP
echo ==============================================================================
echo  In MicroSIP:
echo    1. Go to Menu -^> Add Account:
echo       - Account Name: Asterisk IVR
echo       - SIP Server:   127.0.0.1
echo       - SIP Proxy:    (leave blank)
echo       - Username:     100
echo       - Domain:       127.0.0.1
echo       - Login:        100
echo       - Password:     secretpassword123
echo       - Transport:    TCP  (or UDP)
echo    2. Click Save. The bottom-left status should show 'Online' (Green).
echo    3. In the dialer, type 1000 and click Call!
echo ==============================================================================
echo.
pause
