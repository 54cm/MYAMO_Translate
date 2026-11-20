@echo off
cd /d "%~dp0"
title MYAMO Translate - build

echo [1/3] Installing dependencies...
python -m pip install pywebview requests pyinstaller
if errorlevel 1 goto fail

echo [2/3] Building the exe...
python -m PyInstaller --noconfirm --clean --onedir --windowed --name "MYAMO Translate" --icon icon.ico --add-data "index.html;." --add-data "BfadtOi.png;." --add-data "FCTYZANCE.png;." --add-data "myamoquiregardemale.png;." app.py
if errorlevel 1 goto fail

echo [3/3] Building the installer...
if exist "dist\MYAMO-Translate-Setup.exe" del /f /q "dist\MYAMO-Translate-Setup.exe"
if exist "%ProgramFiles(x86)%\NSIS\makensis.exe" (
  "%ProgramFiles(x86)%\NSIS\makensis.exe" installer.nsi
) else if exist "%ProgramFiles%\NSIS\makensis.exe" (
  "%ProgramFiles%\NSIS\makensis.exe" installer.nsi
) else (
  echo NSIS not found, skipping the installer.
)

echo.
echo Done. Check the dist folder.
pause
exit /b 0

:fail
echo.
echo Something went wrong. Read the message above.
pause
exit /b 1
