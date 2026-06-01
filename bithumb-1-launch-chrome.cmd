@echo off
setlocal

pushd "%~dp0" >nul

 echo ========================================
 echo  Bithumb address bot - Chrome launcher
 echo ========================================
 echo.
 echo This opens a dedicated Chrome profile on port 9222.
 echo Log in to Bithumb manually and open the address book page.
 echo Keep the Chrome window open until calibration/bot run is finished.
 echo.
 echo Profile: %LOCALAPPDATA%\AddressRegBot\bithumb-profile
 echo CDP:     http://127.0.0.1:9222
 echo.
 powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\launch_chrome_debug.ps1" -Port 9222 -Address "127.0.0.1" -ProfileDir "%LOCALAPPDATA%\AddressRegBot\bithumb-profile"

if errorlevel 1 (
  echo.
  echo [ERROR] Failed to launch Chrome.
  echo Check scripts\launch_chrome_debug.ps1 or your Chrome installation.
  echo.
  pause
  popd >nul
  exit /b 1
)

 echo.
 echo If Chrome opened, log in and verify manually in that Chrome window.
 echo Address book: https://www.bithumb.com/react/inout/address
 echo.
 echo After login, run "bithumb-2-inspect-calibration.cmd".
 echo.
 pause
 popd >nul
