@echo off
chcp 65001 >nul
setlocal

pushd "%~dp0" >nul

echo ========================================
echo  빗썸 주소등록봇 - 전용 Chrome 접속
echo ========================================
echo.
echo 이 창은 빗썸 전용 Chrome을 9222 포트로 엽니다.
echo 열린 Chrome에서 직접 빗썸 로그인 후 주소록 화면으로 이동하세요.
echo Chrome 창은 캘리브레이션/봇 실행이 끝날 때까지 닫지 마세요.
echo.
echo Profile: %LOCALAPPDATA%\AddressRegBot\bithumb-profile
echo CDP:     http://127.0.0.1:9222
echo.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "scripts\launch_chrome_debug.ps1" -Port 9222 -Address "127.0.0.1" -ProfileDir "%LOCALAPPDATA%\AddressRegBot\bithumb-profile"

if errorlevel 1 (
  echo.
  echo [오류] Chrome 실행에 실패했습니다.
  echo scripts\launch_chrome_debug.ps1 파일 또는 Chrome 설치를 확인하세요.
  echo.
  pause
  popd >nul
  exit /b 1
)

echo.
echo Chrome이 열렸으면 그 창에서 빗썸 로그인/인증을 직접 진행하세요.
echo 주소록: https://www.bithumb.com/react/inout/address
echo.
echo 로그인 후에는 "bithumb-2-inspect-calibration.cmd"를 실행하면 됩니다.
echo.
pause
popd >nul
