@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Pokrecem lokalni prozor (otvara se u pregledniku)...
py -3 vektor_web.py
if errorlevel 1 pause
