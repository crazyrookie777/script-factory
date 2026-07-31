@echo off
chcp 65001 >nul 2>&1
setlocal
cd /d "%~dp0"

echo.
echo ==================================================
echo    대본 도구 업데이트
echo ==================================================
echo.

where git >nul 2>&1
if errorlevel 1 (
    echo  [X] Git이 설치되어 있지 않습니다.
    echo.
    echo      https://git-scm.com/download/win 에서 설치한 뒤
    echo      이 파일을 다시 실행하세요.
    echo.
    pause
    exit /b 1
)

if not exist ".git" (
    echo  [X] 올바른 작업 폴더가 아닙니다.
    echo      script-factory 폴더 안에서 실행하세요.
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%i in ('git rev-parse --short HEAD') do set BEFORE=%%i
for /f "delims=" %%i in ('git rev-parse --short origin/master 2^>nul') do set REMOTE_BEFORE=%%i

echo  도구 파일을 최신으로 맞추는 중...
echo.

git checkout -- . >nul 2>&1
git clean -fd --exclude="brief.md" --exclude="brief_*.md" --exclude="대본.txt" --exclude="대본_*.txt" --exclude="TTS용_대본.txt" --exclude="TTS용_대본_*.txt" --exclude="검증로그.tsv" --exclude="합격.txt" --exclude="_scripts/" --exclude="업로드_메타데이터.txt" --exclude="output.html" >nul 2>&1

git pull --ff-only 2>&1
if errorlevel 1 (
    echo.
    echo  [X] 업데이트에 실패했습니다.
    echo      이 화면을 캡처해서 관리자에게 보내 주세요.
    echo.
    pause
    exit /b 1
)

for /f "delims=" %%i in ('git rev-parse --short HEAD') do set AFTER=%%i

echo.
if "%BEFORE%"=="%AFTER%" (
    echo  [O] 이미 최신 버전입니다. 받을 게 없습니다.
) else (
    echo  [O] 업데이트 완료. 바뀐 파일은 아래와 같습니다.
    echo.
    git diff --stat %BEFORE% %AFTER%
    echo.
    echo  ------------------------------------------------
    echo   시작하기.md 를 다시 읽어 보세요.
    echo   대본 만드는 법이나 규칙이 바뀌었을 수 있습니다.
    echo  ------------------------------------------------
)

echo.
echo  여러분의 brief.md, 대본.txt 등은 그대로 있습니다.
echo.
pause
