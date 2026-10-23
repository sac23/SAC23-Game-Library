@echo off
setlocal
cd /d "%~dp0"
title SAC23 Game Library - Local Windows App
color 0B
echo.
echo  ==========================================
echo             SAC23 GAME LIBRARY
 echo      Your PS4 and PS5 games, beautifully.
echo  ==========================================
echo.
echo  Starting local game library...
echo  Your game files will NEVER be modified.
echo.
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 "%~dp0game_library.py"
) else (
  where python >nul 2>&1
  if %errorlevel%==0 (
    python "%~dp0game_library.py"
  ) else (
    echo.
    echo  ERROR: Python 3.10 or newer is required.
    echo  Install Python from https://www.python.org/downloads/windows/
    echo  Make sure to enable Add Python to PATH during setup.
  )
)
echo.
echo  SAC23 Game Library stopped.
pause
