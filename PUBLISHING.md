# Publish on GitHub

The prepared source bundle contains application source, docs, tests and a clean Windows release ZIP in `dist/`. It deliberately **does not contain your game library, API keys, cached cover art or original console files**.

## One-click setup on Windows

1. Install [Git for Windows](https://git-scm.com/downloads/win) and [GitHub CLI](https://cli.github.com/).
2. Extract the full GitHub-ready ZIP to an empty folder.
3. Double-click `Publish_To_GitHub.bat` from inside the `SAC23-Game-Library` folder.
4. Sign in to GitHub if prompted, then type **PUBLISH** when asked.
5. The script publishes a **public** `SAC23-Game-Library` repository, pushes the original source, and creates a **v2.4.0 GitHub Release** with the Windows download ZIP.

The publishing script **stages an explicit allowlist** of source/docs/tests/screenshots, not your personal files. `dist/` is kept outside Git history, and its clean ZIP is attached to GitHub Releases separately. It refuses to overwrite an existing Git remote or repository.

## Manual alternative

Create an **empty** public GitHub repository named `SAC23-Game-Library` (do not create a second README/LICENSE there). In this extracted folder:

```powershell
git init -b main
git add .gitignore .github README.md README_FIRST.txt LICENSE CHANGELOG.md CONTRIBUTING.md SECURITY.md RELEASE_NOTES.md PUBLISHING.md TIPS_FOR_LARGE_LIBRARIES.txt Start_SAC23_Game_Library.bat Repair_Missing_Covers_Offline.bat Publish_To_GitHub.bat game_library.py metadata.py pkg_art.py archive_art.py artwork_rescue.py repair_missing_covers.py web tests docs
git commit -m "SAC23 Game Library v2.4.0 public release"
git remote add origin https://github.com/YOUR_USERNAME/SAC23-Game-Library.git
git push -u origin main
```

In the repository choose **Releases → Draft a new release**, tag `v2.4.0`, and attach `dist/SAC23_Game_Library_v2.4.0_Windows.zip` from your extracted bundle. Use `RELEASE_NOTES.md` as the release description.

MIT covers only original app source; neither downloadable proprietary game content nor copyrighted artwork is included.
