@echo off
REM ========================================
REM Web-Rapfish Windows Executable Builder
REM ========================================

echo.
echo ========================================
echo   RAPFISH MDS - Windows Build Script
echo ========================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH!
    echo Please install Python 3.8+ from https://www.python.org/
    pause
    exit /b 1
)

echo [1/4] Installing PyInstaller...
python -m pip install pyinstaller --quiet

echo [2/4] Installing project dependencies...
python -m pip install -r requirements.txt --quiet

echo [3/4] Building Windows executable...
echo This may take 3-5 minutes. Please wait...
pyinstaller build_windows.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [ERROR] Build failed! Check the error messages above.
    pause
    exit /b 1
)

echo.
echo [4/4] Build completed successfully!
echo.
echo ========================================
echo   Executable Location:
echo   dist\Rapfish_MDS_Analysis.exe
echo ========================================
echo.
echo You can now distribute this .exe file to users.
echo No Python installation required on target machines!
echo.
pause
