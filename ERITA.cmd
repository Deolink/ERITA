@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

if defined ERPTBR_NONINTERACTIVE set "ERPTBR_ONECLICK_CALLER_NONINTERACTIVE=1"

if not defined SystemRoot goto :windows_environment_missing
if not defined LOCALAPPDATA goto :windows_environment_missing
set "ERPT_POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
if not exist "%ERPT_POWERSHELL%" goto :windows_environment_missing

rem Un mutex di Windows impedisce a due clic simultanei di ricreare lo stesso venv.
if defined ERPTBR_ONECLICK_MUTEX_HELD goto :main
set "ERPTBR_ONECLICK_SELF=%~f0"
set "ERPTBR_ONECLICK_MUTEX_HELD=1"
"%ERPT_POWERSHELL%" -NoLogo -NoProfile -NonInteractive -Command "$sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value.Replace('-','_'); $mutex=[Threading.Mutex]::new($false,('Local\ERITA_Installer_'+$sid)); $owned=$false; $code=1; try { try { $owned=$mutex.WaitOne(0,$false) } catch [Threading.AbandonedMutexException] { $owned=$true }; if(-not $owned) { Write-Host 'Un''altra installazione di ERITA e'' gia'' in corso.'; $code=75 } else { & $env:ERPTBR_ONECLICK_SELF; $code=$LASTEXITCODE } } finally { if($owned) { [void]$mutex.ReleaseMutex() }; $mutex.Dispose() }; exit $code"
exit /b %ERRORLEVEL%

:main
echo ERITA - hotfix di recupero
echo ---------------------------
echo Questo script prepara il Python ufficiale nel tuo profilo, se necessario,
echo installa l'interfaccia con le dipendenze offline e apre il ripristino.
echo L'installazione del doppiaggio su Elden Ring 1.17.1 e' sospesa.
echo Nessun eseguibile proprio del progetto viene usato.
echo.

rem Rifiuta lo ZIP automatico di GitHub e le release incomplete prima di installare Python.
set "ERPT_PACKAGE_ROOT=%~dp0"
"%ERPT_POWERSHELL%" -NoLogo -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; Import-Module -Name (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -Force -ErrorAction Stop; $root=$env:ERPT_PACKAGE_ROOT; $required=@('interno\INSTALAR_AMBIENTE.cmd','interno\ABRIR_INTERFACE.cmd','docs\INCIDENTE-0.9.1.md','patcher\__init__.py','patcher\bnk.py','patcher\engine.py','patcher\diagnostics.py','patcher\patch_data.py','patcher\patcher_gui.py','patcher\patcher.ico','patcher\requirements-win64.lock'); $wheels=@{'wheelhouse\customtkinter-5.2.2-py3-none-any.whl'='14ad3e7cd3cb3b9eb642b9d4e8711ae80d3f79fb82545ad11258eeffb2e6b37c';'wheelhouse\darkdetect-0.8.0-py3-none-any.whl'='a7509ccf517eaad92b31c214f593dbcf138ea8a43b2935406bbd565e15527a85';'wheelhouse\packaging-26.3-py3-none-any.whl'='d7193f7c8e4e93f444fde0262bf90af30e16fa0ad0ad44cb553c87339b23cd1c';'wheelhouse\pycryptodome-3.23.0-cp37-abi3-win_amd64.whl'='c75b52aacc6c0c260f204cbdd834f76edc9fb0d8e0da9fbf8352ef58202564e2'}; foreach($relative in $required+$wheels.Keys) { $path=Join-Path $root $relative; $item=Get-Item -LiteralPath $path -Force -ErrorAction Stop; if($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw ('File mancante o non sicuro: '+$relative) } }; foreach($entry in $wheels.GetEnumerator()) { $actual=(Microsoft.PowerShell.Utility\Get-FileHash -LiteralPath (Join-Path $root $entry.Key) -Algorithm SHA256).Hash; if($actual -ne $entry.Value) { throw ('Wheel mancante o alterato: '+$entry.Key) } }" >nul 2>&1
if errorlevel 1 goto :invalid_package

call :find_python
if not errorlevel 1 goto :python_ready

set "ERPT_WINGET=%LOCALAPPDATA%\Microsoft\WindowsApps\winget.exe"
if not exist "%ERPT_WINGET%" goto :install_direct

echo CPython 3.13.15 x64 o una manutenzione piu' recente non trovato.
echo Installazione tramite WinGet Microsoft solo per questo utente...
"%ERPT_WINGET%" install --exact --id Python.Python.3.13 --version 3.13.15 --source winget --scope user --architecture x64 --silent --disable-interactivity --accept-package-agreements --accept-source-agreements --override "/passive InstallAllUsers=0 Include_exe=1 Include_lib=1 Include_dev=1 Include_launcher=1 InstallLauncherAllUsers=0 Include_pip=1 Include_tcltk=1 Include_freethreaded=0 Include_test=0 Include_doc=0 Include_debug=0 Include_symbols=0 PrependPath=0 AppendPath=0 AssociateFiles=0 Shortcuts=0"
if errorlevel 1 goto :winget_failed
call :find_python
if errorlevel 1 goto :python_install_invalid
goto :python_ready

:install_direct
set "ERPT_CURL=%SystemRoot%\System32\curl.exe"
if not exist "%ERPT_CURL%" goto :no_safe_downloader
set "ERPT_BOOTSTRAP_ROOT=%LOCALAPPDATA%\ERITA\bootstrap"
"%ERPT_POWERSHELL%" -NoLogo -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; $p=$env:ERPT_BOOTSTRAP_ROOT; $parent=Split-Path -Parent $p; foreach($candidate in @($parent,$p)) { if(Test-Path -LiteralPath $candidate) { $item=Get-Item -LiteralPath $candidate -Force; if(-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw ('Percorso di bootstrap non sicuro: '+$candidate) } } else { New-Item -ItemType Directory -Path $candidate -ErrorAction Stop | Out-Null } }"
if errorlevel 1 goto :unsafe_bootstrap

for /f "delims=" %%G in ('%ERPT_POWERSHELL% -NoLogo -NoProfile -NonInteractive -Command "[Guid]::NewGuid().ToString('N')"') do set "ERPT_BOOTSTRAP_GUID=%%G"
if not defined ERPT_BOOTSTRAP_GUID goto :download_failed
set "ERPT_BOOTSTRAP_FILE=%ERPT_BOOTSTRAP_ROOT%\python-3.13.15-amd64-%ERPT_BOOTSTRAP_GUID%.download"

echo WinGet non e' disponibile in questa installazione di Windows.
echo Download di 29.452.944 byte dell'installer ufficiale da python.org...
"%ERPT_CURL%" --fail --show-error --progress-bar --proto "=https" --tlsv1.2 --retry 2 --connect-timeout 20 --output "%ERPT_BOOTSTRAP_FILE%" "https://www.python.org/ftp/python/3.13.15/python-3.13.15-amd64.exe"
if errorlevel 1 goto :download_failed

echo Verifica di dimensione, SHA-256, firma digitale ed editore in corso...
"%ERPT_POWERSHELL%" -NoLogo -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; Import-Module -Name (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Utility\Microsoft.PowerShell.Utility.psd1') -Force -ErrorAction Stop; Import-Module -Name (Join-Path $PSHOME 'Modules\Microsoft.PowerShell.Security\Microsoft.PowerShell.Security.psd1') -Force -ErrorAction Stop; $path=$env:ERPT_BOOTSTRAP_FILE; $expected='EDEC09C4853AEAE9AC36EFB8C9F95B6B8E2FEE65EEE56D9767A8B7C69C574403'; $publisher='CN=Python Software Foundation, O=Python Software Foundation, L=Beaverton, S=Oregon, C=US'; $item=Get-Item -LiteralPath $path -Force; if($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or $item.Length -ne 29452944) { throw 'Dimensione o tipo dell''installer non valido.' }; $hash=(Microsoft.PowerShell.Utility\Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash; if($hash -ne $expected) { throw 'SHA-256 dell''installer non valido.' }; $signature=Microsoft.PowerShell.Security\Get-AuthenticodeSignature -LiteralPath $path; if($signature.Status -ne 'Valid' -or $null -eq $signature.SignerCertificate -or $signature.SignerCertificate.Subject -ne $publisher) { throw 'Firma o editore dell''installer non valido.' }; $executable=[IO.Path]::ChangeExtension($path,'.exe'); [IO.File]::Move($path,$executable); $path=$executable; $stream=[IO.FileStream]::new($path,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read,4096,[IO.FileOptions]::DeleteOnClose); try { if($stream.Length -ne 29452944) { throw 'L''installer e'' cambiato prima dell''esecuzione.' }; $sha=[Security.Cryptography.SHA256]::Create(); try { $handleHash=[BitConverter]::ToString($sha.ComputeHash($stream)).Replace('-','') } finally { $sha.Dispose() }; if($handleHash -ne $expected) { throw 'L''installer e'' cambiato prima dell''esecuzione.' }; $local=[Environment]::GetFolderPath('LocalApplicationData'); $target=Join-Path $local 'Programs\Python\Python313'; $log=Join-Path (Split-Path -Parent $path) 'python-3.13.15-install.log'; $q=[char]34; $arguments=@('/passive',('/log '+$q+$log+$q),'InstallAllUsers=0',('TargetDir='+$q+$target+$q),'Include_exe=1','Include_lib=1','Include_dev=1','Include_launcher=1','InstallLauncherAllUsers=0','Include_pip=1','Include_tcltk=1','Include_freethreaded=0','Include_test=0','Include_doc=0','Include_debug=0','Include_symbols=0','PrependPath=0','AppendPath=0','AssociateFiles=0','Shortcuts=0'); $process=Start-Process -FilePath $path -ArgumentList $arguments -Wait -PassThru; if($process.ExitCode -ne 0 -and $process.ExitCode -ne 3010) { throw ('L''installer ufficiale ha restituito '+$process.ExitCode+'.') } } finally { $stream.Dispose() }"
if errorlevel 1 goto :direct_install_failed
call :find_python
if errorlevel 1 goto :python_install_invalid

:python_ready
echo CPython 3.13 x64 compatibile convalidato.
echo Preparazione o apertura di ERITA in corso...
set "ERPTBR_NONINTERACTIVE=1"
set "ERPTBR_INTERNAL_CALL=1"
call "%~dp0interno\ABRIR_INTERFACE.cmd"
if errorlevel 1 goto :launcher_failed
if defined ERPTBR_INSTALL_ONLY goto :success_install_only
exit /b 0

:success_install_only
echo Installazione con un clic convalidata senza aprire l'interfaccia.
exit /b 0

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
set "ERPT_FILE_TO_CHECK=%ERPT_CANDIDATE%"
"%ERPT_POWERSHELL%" -NoLogo -NoProfile -NonInteractive -Command "$item=Get-Item -LiteralPath $env:ERPT_FILE_TO_CHECK -Force -ErrorAction SilentlyContinue; if($null -eq $item -or $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { exit 1 }"
if errorlevel 1 exit /b 1
"%ERPT_CANDIDATE%" %ERPT_CANDIDATE_SWITCH% -I -S -c "import struct,sys,sysconfig,tkinter; raise SystemExit(0 if sys.implementation.name == 'cpython' and sys.version_info[:2] == (3,13) and sys.version_info[2] >= 15 and sys.version_info.releaselevel == 'final' and struct.calcsize('P') == 8 and sysconfig.get_platform().lower() == 'win-amd64' and not sysconfig.get_config_var('Py_GIL_DISABLED') else 1)" >nul 2>&1
if errorlevel 1 exit /b 1
set "ERPT_PY=%ERPT_CANDIDATE%"
set "ERPT_PY_SWITCH=%ERPT_CANDIDATE_SWITCH%"
exit /b 0

:winget_failed
echo.
echo ERRORE: WinGet esiste, ma ha rifiutato o non ha completato l'installazione ufficiale.
echo Il fallback diretto non e' stato attivato per non aggirare policy, antivirus o annullamento.
echo Ripara App Installer/WinGet oppure installa manualmente dall'indirizzo qui sotto:
echo https://www.python.org/downloads/release/python-31315/
goto :failed

:download_failed
echo.
echo ERRORE: impossibile completare il download HTTPS dell'installer ufficiale.
goto :failed

:direct_install_failed
echo.
echo ERRORE: l'installer scaricato non ha superato l'autenticazione o non si e' concluso.
echo Nessun file non autenticato e' stato eseguito.
goto :failed

:unsafe_bootstrap
echo.
echo ERRORE: la cartella di bootstrap ha un link, reparse point o tipo inatteso.
echo E' stata preservata per la revisione: "%ERPT_BOOTSTRAP_ROOT%"
goto :failed

:no_safe_downloader
echo.
echo ERRORE: WinGet e il curl di Windows non sono disponibili.
echo Installa manualmente il Python ufficiale 3.13.15 x64 da:
echo https://www.python.org/downloads/release/python-31315/
goto :failed

:python_install_invalid
echo.
echo ERRORE: l'installazione e' terminata, ma il CPython 3.13 x64 compatibile con Tkinter non e' stato convalidato.
goto :failed

:launcher_failed
echo.
echo ERRORE: impossibile preparare o aprire l'interfaccia di ERITA.
goto :failed

:windows_environment_missing
echo.
echo ERRORE: l'ambiente predefinito di Windows non e' stato individuato in sicurezza.
goto :failed

:invalid_package
echo.
echo ERRORE: questo pacchetto e' incompleto oppure una dipendenza non ha superato la verifica SHA-256.
echo Usa ERITA-v0.9.3-source-win64.zip dalla pagina Releases, estratto per intero.
echo Non usare lo ZIP automatico chiamato semplicemente Source code.
goto :failed

:failed
echo Nessun file del gioco Elden Ring e' stato modificato.
if not defined ERPTBR_ONECLICK_CALLER_NONINTERACTIVE pause
exit /b 1
