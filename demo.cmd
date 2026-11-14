@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
where uv >nul 2>&1
if errorlevel 1 (
  echo Outil manquant : uv. Installez-le selon le README, puis rouvrez cette fenetre.
  pause
  exit /b 1
)
uv run --project backend python scripts/demo.py %*
if errorlevel 1 (
  echo La demo a rencontre une erreur. Consultez le message ci-dessus et runtime\logs.
  pause
  exit /b 1
)
