@echo off
title Push to GitHub (Private Repo)
cd /d "%~dp0"
echo ========================================================
echo  Pushing Thunderobot RGB Keyboard Suite to GitHub...
echo ========================================================
echo.
git push -u origin main
echo.
echo ========================================================
echo  Done! Press any key to exit.
echo ========================================================
pause
