@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ============================================
echo  Claude Usage Tracker - ビルドスクリプト
echo ============================================

REM バックアップ
echo [1/4] main.py バックアップ...
for /f "tokens=1-3 delims=/ " %%a in ('date /t') do set TODAY=%%a%%b%%c
copy /y main.py "main_backup_%TODAY%.py" >nul 2>&1

REM クリーンアップ
echo [2/4] 前回ビルドのクリーンアップ...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist *.spec del /q *.spec

REM PyInstaller ビルド
echo [3/4] PyInstaller ビルド中...
pyinstaller ^
    --noconsole ^
    --name "ClaudeUsageTracker" ^
    --add-data "icons;icons" ^
    --hidden-import pystray ^
    --hidden-import PIL ^
    --hidden-import PIL._tkinter_finder ^
    --hidden-import matplotlib ^
    --hidden-import matplotlib.backends.backend_tkagg ^
    --hidden-import tkcalendar ^
    --hidden-import babel.numbers ^
    --collect-data tkcalendar ^
    main.py

if errorlevel 1 (
    echo [エラー] PyInstaller ビルド失敗
    pause
    exit /b 1
)

echo [4/4] ビルド完了
echo.
echo 出力先: dist\ClaudeUsageTracker\ClaudeUsageTracker.exe
echo.

REM バックアップ削除
del /q "main_backup_%TODAY%.py" >nul 2>&1

pause
