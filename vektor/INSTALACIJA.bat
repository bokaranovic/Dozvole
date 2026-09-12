@echo off
chcp 65001 >nul
echo Instalacija biblioteka za PNG/JPEG -^> SVG (Pillow, VTracer, Potrace, Scour)...
py -3 -m pip install --upgrade pip
py -3 -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 (
  echo.
  echo Ako 'py' nije prepoznat: instaliraj Python sa https://www.python.org/downloads/ i ukljuci "Add python.exe to PATH".
)
echo.
pause
