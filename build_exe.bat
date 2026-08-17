@echo off
REM ============================================================
REM Builds the standalone PlayListMaker executable with PyInstaller.
REM Run this on Windows with Python installed, from the project root
REM (the folder containing main.py).
REM ============================================================

echo Installing dependencies (if needed)...
pip install -r requirements.txt
pip install pyinstaller

echo.
echo Building the executable...

REM --noconsole         : no console window behind the app
REM --onefile           : a single .exe (slower to launch, simpler to distribute)
REM --icon              : icon for the .exe and its shortcuts
REM --add-data          : bundles the resources folder (style_template.qss, logo.svg/.ico)
REM                       inside the packaged .exe
REM --name              : final executable name
pyinstaller --noconsole --onefile ^
    --icon=resources\logo.ico ^
    --add-data "resources;resources" ^
    --name PlayListMaker ^
    main.py

echo.
echo Executable generated at: dist\PlayListMaker.exe
echo This is the file the Inno Setup script (installer\PlayListMaker.iss) expects to find.
pause
