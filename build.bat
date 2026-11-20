@echo off
REM EveryDL onefile build - run as .\build.bat from repo root
setlocal

.\.venv\Scripts\python --version || (echo No venv python & exit /b 1)

if not exist ffmpeg.exe (
  echo MISSING ffmpeg.exe - download gyan.dev essentials zip and put ffmpeg.exe here
  exit /b 1
)

uv pip install --python "%CD%\.venv\Scripts\python.exe" -U pyinstaller pillow yt-dlp textual pyperclip || exit /b 1

if not exist EveryDL.ico (
  .\.venv\Scripts\python -c "from PIL import Image; Image.open('EveryDL.png').save('EveryDL.ico', sizes=[(256,256),(128,128),(64,64),(48,48),(32,32),(16,16)])" || exit /b 1
)

if exist build rmdir /s /q build
if exist dist rmdir /s /q dist
if exist EveryDL.spec del EveryDL.spec

.\.venv\Scripts\python -m PyInstaller --onefile --name EveryDL --console ^
  --exclude-module tkinter --exclude-module unittest --exclude-module pydoc --exclude-module test ^
  --add-binary "ffmpeg.exe;." ^
  --icon EveryDL.ico ^
  app.py || exit /b 1

dir dist\EveryDL.exe
echo BUILD DONE - test with dist\EveryDL.exe
pause
