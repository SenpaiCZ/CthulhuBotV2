@echo off
setlocal
cd /d "%~dp0"

echo ========================================================
echo          CthulhuBotV2 Auto-Updater
echo ========================================================
echo.
echo This script will:
echo 1. Backup your current bot files (excluding soundboard/cache).
echo 2. Download the latest code from GitHub (Master branch).
echo 3. Update files (Preserving config.json).
echo 4. Update dependencies and start the bot.
echo.
echo IMPORTANT: PLEASE CLOSE THE BOT WINDOW BEFORE CONTINUING.
echo.
pause

REM Define paths
set "PSFile=%~dp0update_temp_script.ps1"

REM Create PowerShell script content
echo $ErrorActionPreference = "Stop" > "%PSFile%"
echo. >> "%PSFile%"
echo # Paths >> "%PSFile%"
echo $RepoUrl = "https://github.com/SenpaiCZ/CthulhuBotV2/archive/refs/heads/master.zip" >> "%PSFile%"
echo $ZipFile = "update_pkg.zip" >> "%PSFile%"
echo $ExtractDir = "update_extract_temp" >> "%PSFile%"
echo $BackupDir = "backups" >> "%PSFile%"
echo $Timestamp = Get-Date -Format "yyyyMMdd_HHmmss" >> "%PSFile%"
echo. >> "%PSFile%"
echo # 1. Backup >> "%PSFile%"
echo Write-Host "Starting backup..." -ForegroundColor Cyan >> "%PSFile%"
echo if (!(Test-Path $BackupDir)) { New-Item -ItemType Directory -Path $BackupDir ^| Out-Null } >> "%PSFile%"
echo $TempBackup = "$BackupDir\temp_$Timestamp" >> "%PSFile%"
echo New-Item -ItemType Directory -Path $TempBackup ^| Out-Null >> "%PSFile%"
echo. >> "%PSFile%"
echo $Exclude = @("venv", ".git", "__pycache__", "soundboard", "backups", $ZipFile, $ExtractDir, ".vscode", ".idea", "*.log") >> "%PSFile%"
echo Get-ChildItem -Path . -Exclude $Exclude ^| ForEach-Object { >> "%PSFile%"
echo     if ($_.Name -ne $BackupDir -and $_.Name -ne $ZipFile -and $_.Name -ne $ExtractDir) { >> "%PSFile%"
echo         Copy-Item -Path $_.FullName -Destination $TempBackup -Recurse -Force >> "%PSFile%"
echo     } >> "%PSFile%"
echo } >> "%PSFile%"
echo. >> "%PSFile%"
echo $BackupZip = "$BackupDir\backup_$Timestamp.zip" >> "%PSFile%"
echo Compress-Archive -Path "$TempBackup\*" -DestinationPath $BackupZip >> "%PSFile%"
echo Remove-Item -Path $TempBackup -Recurse -Force >> "%PSFile%"
echo Write-Host "Backup saved to: $BackupZip" -ForegroundColor Green >> "%PSFile%"
echo. >> "%PSFile%"
echo # 2. Download >> "%PSFile%"
echo Write-Host "Downloading latest version..." -ForegroundColor Cyan >> "%PSFile%"
echo [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12 >> "%PSFile%"
echo Invoke-WebRequest -Uri $RepoUrl -OutFile $ZipFile >> "%PSFile%"
echo. >> "%PSFile%"
echo # 3. Extract >> "%PSFile%"
echo Write-Host "Extracting..." -ForegroundColor Cyan >> "%PSFile%"
echo Expand-Archive -Path $ZipFile -DestinationPath $ExtractDir -Force >> "%PSFile%"
echo $SourceRoot = Join-Path $ExtractDir (Get-ChildItem -Path $ExtractDir ^| Select-Object -First 1).Name >> "%PSFile%"
echo. >> "%PSFile%"
echo # 4. Infodata Prompt >> "%PSFile%"
echo $UpdateInfo = $null >> "%PSFile%"
echo while ($UpdateInfo -eq $null) { >> "%PSFile%"
echo     $ans = Read-Host "Do you want to update the 'infodata' folder? (Overwrite custom data? Y/N)" >> "%PSFile%"
echo     if ($ans -match "^[Yy]") { $UpdateInfo = $true } >> "%PSFile%"
echo     elseif ($ans -match "^[Nn]") { $UpdateInfo = $false } >> "%PSFile%"
echo } >> "%PSFile%"
echo. >> "%PSFile%"
echo # 5. Apply Updates >> "%PSFile%"
echo Write-Host "Applying updates..." -ForegroundColor Cyan >> "%PSFile%"
echo Get-ChildItem -Path $SourceRoot ^| ForEach-Object { >> "%PSFile%"
echo     if ($_.Name -eq "config.json") { >> "%PSFile%"
echo         Write-Host "Skipping config.json" -ForegroundColor Yellow >> "%PSFile%"
echo         return >> "%PSFile%"
echo     } >> "%PSFile%"
echo     if ($_.Name -eq "infodata" -and !$UpdateInfo) { >> "%PSFile%"
echo         Write-Host "Skipping infodata folder" -ForegroundColor Yellow >> "%PSFile%"
echo         return >> "%PSFile%"
echo     } >> "%PSFile%"
echo     Copy-Item -Path $_.FullName -Destination "." -Recurse -Force >> "%PSFile%"
echo } >> "%PSFile%"
echo. >> "%PSFile%"
echo # 6. Cleanup >> "%PSFile%"
echo Remove-Item -Path $ZipFile -Force >> "%PSFile%"
echo Remove-Item -Path $ExtractDir -Recurse -Force >> "%PSFile%"
echo Write-Host "Update finished successfully." -ForegroundColor Green >> "%PSFile%"

REM Run the PowerShell script
PowerShell -NoProfile -ExecutionPolicy Bypass -File "%PSFile%"
if %errorlevel% neq 0 (
    echo.
    echo Error encountered during update.
    pause
    if exist "%PSFile%" del "%PSFile%"
    exit /b
)

REM Delete the temporary PowerShell script
if exist "%PSFile%" del "%PSFile%"

echo.
echo --------------------------------------------------------
echo Updating Dependencies and Starting Bot
echo --------------------------------------------------------
echo.

if not exist "venv\Scripts\activate.bat" (
    echo Error: Virtual environment not found in 'venv'.
    echo Please run setup.bat to create the environment first.
    pause
    exit /b
)

call venv\Scripts\activate.bat
echo Installing dependencies...
pip install -r requirements.txt

echo.
echo Starting CthulhuBotV2...
python bot.py

pause
