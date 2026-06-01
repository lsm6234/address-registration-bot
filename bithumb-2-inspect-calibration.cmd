@echo off
chcp 65001 >nul
setlocal

pushd "%~dp0" >nul

echo ========================================
echo  빗썸 주소등록봇 - 캘리브레이션 검사
echo ========================================
echo.
echo 먼저 "bithumb-1-launch-chrome.cmd"로 열린 Chrome에서
echo 빗썸 로그인 후 주소록 화면을 열어둬야 합니다.
echo.
echo 이 검사는 읽기 전용입니다. 클릭/입력/등록을 하지 않습니다.
echo CDP: http://127.0.0.1:9222
echo.

if not exist ".win_site\playwright" (
  echo [준비] Windows Python용 패키지를 프로젝트 안 .win_site에 설치합니다. 최초 1회만 시간이 걸립니다.
  python -m pip install --target .win_site playwright openpyxl
  if errorlevel 1 goto setup_failed
)

set "PYTHONPATH=%CD%\src;%CD%\.win_site"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
python -m address_bot.cli inspect-bithumb --cdp http://127.0.0.1:9222 --out .localdata\calibration\bithumb_inspection.json --screenshot .localdata\calibration\bithumb_inspection.png

if errorlevel 1 (
  echo.
  echo [주의] 검사 결과가 안전 조건을 통과하지 못했거나 CDP 연결에 실패했습니다.
  echo - 빗썸 주소록 화면인지 확인
  echo - OTP/SMS/이메일 인증 화면이면 직접 처리 후 다시 실행
  echo.
  pause
  popd >nul
  exit /b 1
)

echo.
echo [완료] 캘리브레이션 결과 저장:
echo %CD%\.localdata\calibration\bithumb_inspection.json
echo %CD%\.localdata\calibration\bithumb_inspection.png
echo.
pause
popd >nul
exit /b 0

:setup_failed
echo.
echo [오류] Windows Python 패키지 준비에 실패했습니다.
echo - Windows에서 python/pip 명령이 실행되는지 확인하세요.
echo - 인터넷 연결 또는 pip 설치 오류가 아닌지 확인하세요.
echo.
pause
popd >nul
exit /b 1
