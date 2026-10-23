@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"
title SAC23 Game Library - GitHub Publisher
color 0B
set "REPO_NAME=SAC23-Game-Library"
set "RELEASE_ZIP=dist\SAC23_Game_Library_v2.4.0_Windows.zip"
echo.
echo =====================================================
echo     SAC23 GAME LIBRARY - PUBLIC GITHUB PUBLISHER
echo =====================================================
echo.
echo Your app source will be public on GitHub.
echo Game files, cached artwork, personal data and API keys are NOT included.
echo.
if not exist "game_library.py" goto missing_app
if not exist "%RELEASE_ZIP%" goto missing_release
where git >nul 2>&1
if errorlevel 1 goto missing_git
where gh >nul 2>&1
if errorlevel 1 goto missing_gh
gh auth status >nul 2>&1
if errorlevel 1 (
  echo GitHub authentication is needed. Opening browser login...
  gh auth login --web --git-protocol https
  if errorlevel 1 goto failed
)
echo.
echo Repository: %REPO_NAME%
echo Visibility: PUBLIC
echo Release: v2.4.0
echo.
set "CONFIRM="
set /p "CONFIRM=Type PUBLISH to approve public uploading: "
if /I not "%CONFIRM%"=="PUBLISH" goto cancelled

gh repo view "%REPO_NAME%" --json name >nul 2>&1
if not errorlevel 1 (
  echo A repository with this name already exists in your account.
  echo No changes made. Inspect your existing repository first.
  goto failed
)
git rev-parse --is-inside-work-tree >nul 2>&1
if errorlevel 1 (
  git init -b main
  if errorlevel 1 goto failed
) else (
  git remote get-url origin >nul 2>&1
  if not errorlevel 1 (
    echo Existing Git remote detected; refusing to overwrite.
    goto failed
  )
)
for /f "delims=" %%U in ('gh api user --jq .login 2^>nul') do set "GH_LOGIN=%%U"
for /f "delims=" %%I in ('gh api user --jq .id 2^>nul') do set "GH_ID=%%I"
if not defined GH_LOGIN goto failed
if not defined GH_ID goto failed
git config --get user.name >nul 2>&1
if errorlevel 1 git config user.name "!GH_LOGIN!"
git config --get user.email >nul 2>&1
if errorlevel 1 git config user.email "!GH_ID!+!GH_LOGIN!@users.noreply.github.com"
echo.
echo Preparing approved app files only...
git add -- .gitignore .github README.md README_FIRST.txt LICENSE CHANGELOG.md CONTRIBUTING.md SECURITY.md RELEASE_NOTES.md PUBLISHING.md TIPS_FOR_LARGE_LIBRARIES.txt Start_SAC23_Game_Library.bat Repair_Missing_Covers_Offline.bat Publish_To_GitHub.bat game_library.py metadata.py pkg_art.py archive_art.py artwork_rescue.py repair_missing_covers.py web tests docs
if errorlevel 1 goto failed
git diff --cached --quiet
if errorlevel 1 (
  git commit -m "SAC23 Game Library v2.4.0 public release"
  if errorlevel 1 goto failed
)
echo.
echo Creating public GitHub repository and pushing source...
gh repo create "%REPO_NAME%" --public --source=. --remote=origin --push --description "Visual PS4 and PS5 game library with cover art and YouTube previews"
if errorlevel 1 goto failed
echo.
echo Creating downloadable v2.4.0 Windows Release...
gh release create v2.4.0 "%RELEASE_ZIP%" --title "SAC23 Game Library v2.4.0" --notes-file RELEASE_NOTES.md
if errorlevel 1 goto release_failed
echo.
echo SUCCESS - public source and Windows release published!
gh repo view --json url --jq .url
goto end
:missing_app
echo ERROR: Open the extracted GitHub-ready folder, then retry.
goto end
:missing_release
echo ERROR: Windows release ZIP missing in the dist folder.
goto end
:missing_git
echo ERROR: Install Git for Windows from https://git-scm.com/downloads/win
goto end
:missing_gh
echo ERROR: Install GitHub CLI from https://cli.github.com/
goto end
:cancelled
echo Cancelled. No files published.
goto end
:release_failed
echo GitHub source was uploaded, but release creation failed.
echo Add the ZIP in dist/ as a GitHub Release manually (tag v2.4.0).
goto end
:failed
echo Publishing stopped. Review the message above and retry safely.
:end
echo.
pause
