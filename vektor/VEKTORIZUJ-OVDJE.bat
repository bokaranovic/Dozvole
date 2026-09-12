@echo off
chcp 65001 >nul
rem Prevuci sliku ili folder na ovaj fajl -> SVG nastaje pored slike.
cd /d "%~dp0"
if "%~1"=="" (
  echo Prevuci sliku ili folder na ovaj .bat fajl.
  pause & exit /b
)
py -3 vektorizuj.py %* --preset auto --bg white
pause
