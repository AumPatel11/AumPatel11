@echo off
cd /d "%~dp0"
echo Installing Lumora requirements...
python -m pip install -r requirements.txt || py -m pip install -r requirements.txt
start "" http://localhost:8787
python server.py || py server.py
pause
