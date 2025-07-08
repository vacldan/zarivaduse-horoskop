@echo off
REM Přejde do složky, kde je bat soubor i app.py
cd /d "%~dp0"

REM Aktivuje virtuální prostředí
call venv\Scripts\activate

REM Spustí Streamlit aplikaci
streamlit run app.py

REM Po ukončení nechá otevřené okno pro chybové hlášky
pause
