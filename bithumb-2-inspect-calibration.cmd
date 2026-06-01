@echo off
setlocal

pushd "%~dp0" >nul

 echo ========================================
 echo  Bithumb address bot - calibration check
 echo ========================================
 echo.
 echo First open Chrome with "bithumb-1-launch-chrome.cmd".
 echo Then log in to Bithumb and open the address book page.
 echo.
 echo This check is read-only. It does not click, type, or register addresses.
 echo CDP: http://127.0.0.1:9222
 echo.

if not exist ".win_site\playwright" (
  echo [SETUP] Installing Windows Python packages into .win_site. This is needed only once.
  python -m pip install --target .win_site playwright openpyxl
  if errorlevel 1 goto setup_failed
)

set "PYTHONPATH=%CD%\src;%CD%\.win_site"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
python -m address_bot.cli inspect-bithumb --cdp http://127.0.0.1:9222 --out .localdata\calibration\bithumb_inspection.json --screenshot .localdata\calibration\bithumb_inspection.png

if errorlevel 1 (
  echo.
  echo [WARN] Calibration did not pass or CDP connection failed.
  echo - Check that Chrome is open on the CDP address above.
  echo - Check that the Bithumb address book page is open.
  echo - If OTP/SMS/email verification is shown, complete it manually and rerun.
  echo.
  pause
  popd >nul
  exit /b 1
)

 echo.
 echo [DONE] Calibration result saved:
 echo %CD%\.localdata\calibration\bithumb_inspection.json
 echo %CD%\.localdata\calibration\bithumb_inspection.png
 echo.
 pause
 popd >nul
 exit /b 0

:setup_failed
 echo.
 echo [ERROR] Failed to prepare Windows Python packages.
 echo - Check that python/pip is available on Windows.
 echo - Check your internet connection or pip error output.
 echo.
 pause
 popd >nul
 exit /b 1
