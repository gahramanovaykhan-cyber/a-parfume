@echo off
title A PARFUME
cd /d "%~dp0"
echo =====================================
echo          A PARFUME SISTEMI
echo =====================================
where py >nul 2>nul
if errorlevel 1 (
  echo Python tapilmadi. Python 3.11 ve ya 3.12 qurasdirin.
  echo Qurasdirarken "Add Python to PATH" secimini aktiv edin.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  echo Virtual muhit yaradilir...
  py -m venv .venv
  if errorlevel 1 goto error
)
call ".venv\Scripts\activate.bat"
echo Lazimi paketler yoxlanilir...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto error
echo.
echo A PARFUME acilir. Bu pencereyi baglamayin.
echo Brauzerde http://127.0.0.1:5000 acin.
python app.py
goto end
:error
echo.
echo Xeta bas verdi. Yuxaridaki xeta metninin seklini cekib gonderin.
pause
:end
pause
