@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ============================================
echo  Claude Usage Tracker - Build Script
echo ============================================

REM Cleanup
echo [1/3] Cleaning previous build...
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build
if exist *.spec del /q *.spec

REM PyInstaller build
echo [2/3] Building with PyInstaller...
python -m PyInstaller -y ^
    --noconsole ^
    --icon=icons\app.ico ^
    --name "ClaudeUsageTracker" ^
    --add-data "icons;icons" ^
    --add-data "locale;locale" ^
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
    echo [ERROR] PyInstaller build failed
    pause
    exit /b 1
)

echo [3/3] Build complete
echo.
echo Output: dist\ClaudeUsageTracker\ClaudeUsageTracker.exe
echo.
pause
