@echo off
setlocal

if not exist venv (
    py -3 -m venv venv
)

call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt

pyinstaller --noconfirm --onefile --windowed --name KirkaBot --add-data "templates;templates" BOT.py

echo.
echo Build complete. EXE is here: dist\KirkaBot.exe
pause
