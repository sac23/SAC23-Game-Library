@echo off
setlocal
cd /d "%~dp0"
title SAC23 Game Library - Repair Cached Covers
color 0B
echo.
echo   SAC23 - Offline Cover Repair
 echo   Uses your EXISTING downloaded artwork (no redownloads).
echo   Please CLOSE the Game Library before running this repair.
echo.
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 "%~dp0repair_missing_covers.py"
) else (
  where python >nul 2>&1
  if %errorlevel%==0 (
    python "%~dp0repair_missing_covers.py"
  ) else (
    echo Python 3.10 or later is required.
  )
)
echo.
pause
