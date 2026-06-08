@echo off
title NeuralVibe TradingAgents Server Manager

:menu
cls
echo ========================================================================
echo    ★ NEURALVIBE TRADINGAGENTS : 풀스택 서버 통합 관리 포털
echo ========================================================================
echo    [시스템 상태를 실시간 감지하여 가동 및 제어를 원클릭으로 지원합니다]
echo.

:: 1. 가상환경 및 모듈 유효성 검사
set "VENV_OK=● 감지됨"
if not exist ".venv\Scripts\python.exe" set "VENV_OK=○ 미설치 [설치 필요]"

set "NODE_OK=● 감지됨"
if not exist "frontend\node_modules" set "NODE_OK=○ 미설치 [npm install 필요]"

:: 2. 포트 감지를 통해 실시간 가동 상태 조회
set "BACKEND_STATUS=○ OFFLINE"
netstat -ano | findstr :8080 | findstr LISTENING >nul
if %errorlevel% equ 0 set "BACKEND_STATUS=● ONLINE [Port: 8080]"

set "FRONTEND_STATUS=○ OFFLINE"
netstat -ano | findstr :5173 | findstr LISTENING >nul
if %errorlevel% equ 0 set "FRONTEND_STATUS=● ONLINE [Port: 5173]"

echo   [서버 실시간 상태 대시보드]
echo   - 백엔드 서버 [FastAPI]   : %BACKEND_STATUS%
echo   - 프론트엔드 웹 [React/Vite]: %FRONTEND_STATUS%
echo.
echo   [시스템 환경 의존성 검사]
echo   - Python 가상환경 [.venv]     : %VENV_OK%
echo   - 프론트엔드 모듈 [node_modules]: %NODE_OK%
echo ------------------------------------------------------------------------
echo   [메뉴를 선택해 주세요]
echo   [1] [실행] 양쪽 서버 모두 가동 [동시 켜기]
echo   [2] [실행] 백엔드 서버만 가동
echo   [3] [실행] 프론트엔드 웹만 가동
echo.
echo   [4] [종료] 양쪽 서버 모두 종료 [동시 끄기]
echo   [5] [종료] 백엔드 서버만 종료
echo   [6] [종료] 프론트엔드 웹만 종료
echo.
echo   [7] [재시작] 양쪽 서버 재부팅 [껐다 켜기]
echo   [8] [설정] 의존성 설치 및 가상환경 초기 세팅
echo   [9] [종료] 관리 포털 나가기
echo ========================================================================
echo.

set "choice="
set /p choice=선택 [1-9] ≫ 

if "%choice%"=="1" goto start_all
if "%choice%"=="2" goto start_back
if "%choice%"=="3" goto start_front
if "%choice%"=="4" goto stop_all
if "%choice%"=="5" goto stop_back
if "%choice%"=="6" goto stop_front
if "%choice%"=="7" goto restart_all
if "%choice%"=="8" goto setup_env
if "%choice%"=="9" goto exit_script

echo ★ 잘못된 입력입니다. 1에서 9 사이의 숫자를 입력해주세요.
timeout /t 2 >nul
goto menu

:start_all
echo.
echo [실행] 서버 전체 통합 기동을 시작합니다...
call :start_backend_internal
call :start_frontend_internal
echo.
echo * 실행 명령이 완료되었습니다. 서버가 가동될 때까지 대기합니다...
timeout /t 3 >nul
goto menu

:start_back
echo.
call :start_backend_internal
timeout /t 2 >nul
goto menu

:start_front
echo.
call :start_frontend_internal
timeout /t 2 >nul
goto menu

:stop_all
echo.
echo [종료] 서버 전체 통합 강제 종료를 시작합니다...
call :stop_backend_internal
call :stop_frontend_internal
echo.
echo * 전체 종료 작업이 완료되었습니다.
timeout /t 2 >nul
goto menu

:stop_back
echo.
call :stop_backend_internal
timeout /t 2 >nul
goto menu

:stop_front
echo.
call :stop_frontend_internal
timeout /t 2 >nul
goto menu

:restart_all
echo.
echo [재부팅] 서버 재부팅 프로세스를 시작합니다...
call :stop_backend_internal
call :stop_frontend_internal
echo 대기 중... [2초]
timeout /t 2 >nul
call :start_backend_internal
call :start_frontend_internal
echo.
echo * 재부팅 완료! 서버 가동을 대기합니다...
timeout /t 3 >nul
goto menu

:setup_env
echo.
echo ========================================================================
echo    [설정] 의존성 설치 및 환경 구축 지원 도구
echo ========================================================================
echo.
echo [1] Python 가상환경 생성 및 백엔드 라이브러리 설치 [pip install -e .]
echo [2] 프론트엔드 모듈 설치 [npm install]
echo [3] 메인 메뉴로 돌아가기
echo.
set "setup_choice="
set /p setup_choice=선택 [1-3] ≫ 

if "%setup_choice%"=="1" (
    echo.
    echo [단계 1] Python 가상환경 생성 중...
    where py >nul 2>&1
    if %errorlevel% equ 0 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    echo [단계 2] 라이브러리 및 의존성 주입 중 [몇 분 정도 소요될 수 있습니다]...
    .venv\Scripts\python -m pip install --upgrade pip
    .venv\Scripts\python -m pip install -e .
    .venv\Scripts\python -m pip install -r backend\requirements.txt pytest
    echo * Python 환경 구축이 완료되었습니다!
    pause
    goto setup_env
)
if "%setup_choice%"=="2" (
    echo.
    echo [프론트엔드] npm 패키지 설치를 시작합니다...
    cd frontend
    if exist package-lock.json (
        npm ci
    ) else (
        npm install
    )
    cd ..
    echo * 프론트엔드 모듈 설치가 완료되었습니다!
    pause
    goto setup_env
)
if "%setup_choice%"=="3" goto menu

echo ★ 잘못된 선택입니다.
timeout /t 2 >nul
goto setup_env

:exit_script
echo.
echo NeuralVibe TradingAgents 서버 관리 포털을 이용해 주셔서 감사합니다.
echo 종료합니다...
timeout /t 2 >nul
exit

:: ========================================================================
:: 내부 모듈 - 백엔드 기동
:: ========================================================================
:start_backend_internal
netstat -ano | findstr :8080 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo * [백엔드] 이미 8080 포트에서 백엔드가 가동 중입니다.
) else (
    if not exist ".venv\Scripts\python.exe" (
        echo * [백엔드 에러] .venv 가상환경이 존재하지 않습니다. 메뉴 8번을 통해 구축해 주세요.
    ) else (
        echo * [백엔드] uvicorn 서버를 백그라운드 창에서 가동합니다...
        start "TradingAgents Backend" cmd /c "title TradingAgents Backend && .venv\Scripts\python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8080 --reload"
        echo * [백엔드] 기동 명령을 전송했습니다 - Port: 8080.
    )
)
exit /b

:: ========================================================================
:: 내부 모듈 - 프론트엔드 기동
:: ========================================================================
:start_frontend_internal
netstat -ano | findstr :5173 | findstr LISTENING >nul
if %errorlevel% equ 0 (
    echo * [프론트엔드] 이미 5173 포트에서 프론트엔드가 가동 중입니다.
) else (
    if not exist "frontend\node_modules" (
        echo * [프론트엔드 에러] node_modules가 존재하지 않습니다. 메뉴 8번을 통해 구축해 주세요.
    ) else (
        echo * [프론트엔드] Vite 개발 서버를 백그라운드 창에서 가동합니다...
        start "TradingAgents Frontend" cmd /c "title TradingAgents Frontend && cd frontend && npm run dev"
        echo * [프론트엔드] 기동 명령을 전송했습니다 - Port: 5173.
    )
)
exit /b

:: ========================================================================
:: 내부 모듈 - 백엔드 종료
:: ========================================================================
:stop_backend_internal
set "FOUND_BACKEND=0"
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :8080 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
    set "FOUND_BACKEND=1"
)
taskkill /fi "windowtitle eq TradingAgents Backend" /f >nul 2>&1
if "%FOUND_BACKEND%"=="1" (
    echo * [백엔드] 8080 포트의 백엔드 서버를 강제 종료하고 터미널 창을 닫았습니다.
) else (
    echo * [백엔드] 실행 중인 백엔드 서버가 없습니다.
)
exit /b

:: ========================================================================
:: 내부 모듈 - 프론트엔드 종료
:: ========================================================================
:stop_frontend_internal
set "FOUND_FRONTEND=0"
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :5173 ^| findstr LISTENING') do (
    taskkill /f /pid %%a >nul 2>&1
    set "FOUND_FRONTEND=1"
)
taskkill /fi "windowtitle eq TradingAgents Frontend" /f >nul 2>&1
if "%FOUND_FRONTEND%"=="1" (
    echo * [프론트엔드] 5173 포트의 프론트엔드 서버를 강제 종료하고 터미널 창을 닫았습니다.
) else (
    echo * [프론트엔드] 실행 중인 프론트엔드 서버가 없습니다.
)
exit /b

