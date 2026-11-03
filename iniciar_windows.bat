@echo off
REM Demonstração local com 10 controladores simulados. Requer Python 3.10+.
cd /d "%~dp0"
if not exist .venv ( py -m venv .venv )
call .venv\Scripts\activate
python -m pip install -q -r requirements.txt
python iniciar.py
