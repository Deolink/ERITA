@echo off
setlocal EnableExtensions DisableDelayedExpansion
if not defined ERPTBR_INTERNAL_CALL (
  echo Questo e' un componente interno. Usa ERITA.cmd nella cartella principale.
  if not defined ERPTBR_NONINTERACTIVE pause
  exit /b 2
)
for %%I in ("%~dp0..") do set "ERPT_PACKAGE_ROOT=%%~fI\"
cd /d "%ERPT_PACKAGE_ROOT%"

echo ERITA - installazione trasparente in codice sorgente
echo -------------------------------------------------
echo Questo script crea un ambiente Python locale e installa solo i
echo quattro pacchetti verificati che accompagnano questa release.
echo.

if not defined LOCALAPPDATA set "LOCALAPPDATA=%ERPT_PACKAGE_ROOT%.localdata"
call :find_python
if errorlevel 1 goto :python_missing

set "ERPT_ROOT=%LOCALAPPDATA%\ERITA"
set "ERPT_VENV=%ERPT_ROOT%\venv-0.9.1"
set "ERPT_SITE=%ERPT_VENV%\Lib\site-packages"

"%ERPT_PY%" %ERPT_PY_SWITCH% -I -S -c "import os,stat; rp=getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0); paths=(os.environ['ERPT_ROOT'],os.environ['ERPT_VENV']); roots_bad=[p for p in paths if os.path.lexists(p) and (not stat.S_ISDIR(os.lstat(p).st_mode) or bool(getattr(os.lstat(p),'st_file_attributes',0)&rp))]; walk=list(os.walk(paths[1],followlinks=False,onerror=lambda error: (_ for _ in ()).throw(error))) if not roots_bad and os.path.isdir(paths[1]) else []; nested=[os.path.join(base,name) for base,dirs,files in walk for name in dirs+files]; bad=roots_bad+[p for p in nested if bool(getattr(os.lstat(p),'st_file_attributes',0)&rp)]; raise SystemExit(1 if bad else 0)" >nul 2>&1
if errorlevel 1 goto :unsafe_environment

if not exist "%ERPT_PACKAGE_ROOT%wheelhouse\" (
  echo ERRORE: la cartella wheelhouse non e' stata trovata.
  echo Scarica ed estrai il file source-win64.zip completo dalla pagina Releases.
  goto :failed
)

echo Ricreazione dell'ambiente isolato in "%ERPT_VENV%" in corso...
"%ERPT_PY%" %ERPT_PY_SWITCH% -I -S -m venv --clear --copies "%ERPT_VENV%"
if errorlevel 1 goto :failed

"%ERPT_PY%" %ERPT_PY_SWITCH% -I -S -c "import os,stat; rp=getattr(stat,'FILE_ATTRIBUTE_REPARSE_POINT',0); root=os.environ['ERPT_VENV']; paths=((root,1),(os.path.join(root,'Scripts'),1),(os.path.join(root,'Scripts','python.exe'),0),(os.path.join(root,'Scripts','pythonw.exe'),0),(os.environ['ERPT_SITE'],1)); bad=[p for p,want_dir in paths if not os.path.lexists(p) or bool(stat.S_ISDIR(os.lstat(p).st_mode)) != bool(want_dir) or bool(getattr(os.lstat(p),'st_file_attributes',0)&rp)]; raise SystemExit(1 if bad else 0)" >nul 2>&1
if errorlevel 1 goto :unsafe_environment

echo Installazione delle dipendenze verificate offline in corso...
"%ERPT_VENV%\Scripts\python.exe" -I -S -c "import runpy,sys; sys.prefix=sys.exec_prefix=sys.argv[1]; sys.path.append(sys.argv[2]); sys.argv=['pip']+sys.argv[3:]; runpy.run_module('pip',run_name='__main__')" "%ERPT_VENV%" "%ERPT_SITE%" --isolated install ^
  --disable-pip-version-check ^
  --no-input ^
  --no-index ^
  --find-links "%ERPT_PACKAGE_ROOT%wheelhouse" ^
  --require-hashes ^
  --only-binary=:all: ^
  -r "%ERPT_PACKAGE_ROOT%patcher\requirements-win64.lock"
if errorlevel 1 goto :failed

"%ERPT_VENV%\Scripts\python.exe" -I -S -c "import runpy,sys; sys.prefix=sys.exec_prefix=sys.argv[1]; sys.path.append(sys.argv[2]); sys.argv=['pip']+sys.argv[3:]; runpy.run_module('pip',run_name='__main__')" "%ERPT_VENV%" "%ERPT_SITE%" --isolated check
if errorlevel 1 goto :failed

"%ERPT_VENV%\Scripts\python.exe" -I -S -c "import sys; sys.path.append(sys.argv[1]); import tkinter,customtkinter; from Crypto.Cipher import AES" "%ERPT_SITE%"
if errorlevel 1 goto :failed

echo.
echo Ambiente di ERITA preparato con successo.
if not defined ERPTBR_NONINTERACTIVE pause
exit /b 0

:python_missing
echo.
echo ERRORE: CPython 3.13 x64 compatibile con Tkinter non e' stato trovato.
echo Installalo dal sito https://www.python.org/downloads/release/python-31315/
echo Scarica "Windows installer (64-bit)" e mantieni selezionati Python Launcher e Tcl/Tk.
echo Non e' necessario installarlo per tutti gli utenti. Poi esegui di nuovo ERITA.cmd.
goto :failed

:find_python
set "ERPT_PY="
set "ERPT_PY_SWITCH="
set "ERPT_CANDIDATE=%LOCALAPPDATA%\Programs\Python\Launcher\py.exe"
set "ERPT_CANDIDATE_SWITCH=-3.13"
call :check_python
if not errorlevel 1 exit /b 0
set "ERPT_CANDIDATE=%SystemRoot%\py.exe"
set "ERPT_CANDIDATE_SWITCH=-3.13"
call :check_python
if not errorlevel 1 exit /b 0
set "ERPT_CANDIDATE=%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
set "ERPT_CANDIDATE_SWITCH="
call :check_python
if not errorlevel 1 exit /b 0
exit /b 1

:check_python
if not exist "%ERPT_CANDIDATE%" exit /b 1
"%ERPT_CANDIDATE%" %ERPT_CANDIDATE_SWITCH% -I -S -c "import struct,sys,sysconfig,tkinter; raise SystemExit(0 if sys.implementation.name == 'cpython' and sys.version_info[:2] == (3,13) and sys.version_info[2] >= 15 and sys.version_info.releaselevel == 'final' and struct.calcsize('P') == 8 and sysconfig.get_platform().lower() == 'win-amd64' and not sysconfig.get_config_var('Py_GIL_DISABLED') else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
set "ERPT_PY=%ERPT_CANDIDATE%"
set "ERPT_PY_SWITCH=%ERPT_CANDIDATE_SWITCH%"
exit /b 0

:unsafe_environment
echo.
echo ERRORE: l'ambiente isolato ha un link, reparse point o tipo inatteso.
echo E' stato preservato e nessun file del gioco e' stato modificato.
echo Non eliminare "%ERPT_ROOT%", perche' potrebbe contenere backup del gioco.
echo Controlla questo percorso e sposta solo l'elemento inatteso prima di riprovare.
goto :failed

:failed
echo.
echo Nessun file del gioco Elden Ring e' stato modificato.
if not defined ERPTBR_NONINTERACTIVE pause
exit /b 1
