@echo off
setlocal
title Web-Rapfish Build Tool

echo =======================================================
echo   WEB-RAPFISH DESKTOP BUILDER (Senior Architect Ver)
echo =======================================================
echo.

:: 1. Pembersihan Folder
echo [*] Cleaning old builds...
if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
echo [✓] Clean completed.
echo.

:: 2. Cek Python & Dependencies
echo [*] Checking Environment...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] Python not found. Please install Python.
    pause
    exit /b 1
)

:: 3. Jalankan PyInstaller
echo [*] Starting PyInstaller Build...
echo     This may take several minutes (Compiling MDS & Data Engines)
echo.
python -m PyInstaller build_windows.spec --clean --noconfirm

if %errorlevel% neq 0 (
    echo.
    echo [!] BUILD FAILED!
    echo     Please check the error logs above.
    pause
    exit /b 1
)

echo.
echo =======================================================
echo   BUILD SUCCESSFUL!
echo =======================================================
echo   Executable is located in: dist/Web-Rapfish.exe
echo =======================================================
echo.
pause
