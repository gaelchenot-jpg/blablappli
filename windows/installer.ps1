# Installation de blablappli (Windows)
# Double-clique sur "installer.bat" plutôt que sur ce fichier.

$ErrorActionPreference = "Continue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = "SilentlyContinue"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

function Etape($texte) { Write-Host ""; Write-Host "==> $texte" -ForegroundColor Cyan }

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "       Installation de blablappli" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# 1. Python ------------------------------------------------------------------
Etape "Recherche de Python"
function Find-Python {
    $hasPy = [bool](Get-Command py -ErrorAction SilentlyContinue)
    foreach ($v in @("3.12", "3.11", "3.13", "3.10")) {
        if (-not $hasPy) { break }
        try {
            $exe = & py "-$v" -c "import sys; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $exe) { return ([string]$exe).Trim() }
        } catch {}
    }
    foreach ($p in @("$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
                     "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe")) {
        if (Test-Path $p) { return $p }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Write-Host "Python n'est pas installé : installation de Python 3.12 (gratuit)..."
    try {
        if (-not (Get-Command winget -ErrorAction SilentlyContinue)) { throw "winget absent" }
        winget install -e --id Python.Python.3.12 --scope user --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) { throw "winget a échoué" }
    } catch {
        Write-Host "Impossible d'installer Python automatiquement." -ForegroundColor Red
        Write-Host "Installe-le depuis https://www.python.org/downloads/ (coche 'Add python.exe to PATH'), puis relance installer.bat."
        exit 1
    }
    $python = Find-Python
    if (-not $python) {
        Write-Host "Python vient d'être installé. Ferme cette fenêtre et relance installer.bat." -ForegroundColor Yellow
        exit 1
    }
}
Write-Host "Python trouvé : $python"

# 2. Environnement de l'appli --------------------------------------------------
Etape "Préparation de l'environnement de l'appli"
if (-not (Test-Path "$here\.venv\Scripts\python.exe")) {
    & $python -m venv "$here\.venv"
}
$py = "$here\.venv\Scripts\python.exe"
& $py -m pip install --upgrade pip --quiet

Etape "Installation des composants (quelques minutes)"
& $py -m pip install -r "$here\requirements.txt"
if ($LASTEXITCODE -ne 0) { Write-Host "L'installation des composants a échoué." -ForegroundColor Red; exit 1 }

# 3. Grammalecte (correcteur) ---------------------------------------------------
Etape "Installation du correcteur Grammalecte"
$tmp = Join-Path $env:TEMP "blablappli-install"
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$gVersion = "2.1.1"
$gZip = Join-Path $tmp "grammalecte.zip"
$gDir = Join-Path $tmp "grammalecte"
try {
    Invoke-WebRequest -Uri "https://grammalecte.net/zip/Grammalecte-fr-v$gVersion.zip" -OutFile $gZip -UseBasicParsing -ErrorAction Stop
    if (Test-Path $gDir) { Remove-Item -Recurse -Force $gDir }
    Expand-Archive -Path $gZip -DestinationPath $gDir -Force -ErrorAction Stop
    $setup = Get-ChildItem -Path $gDir -Recurse -Filter "setup.py" | Select-Object -First 1
    & $py -m pip install $setup.DirectoryName --quiet
    if ($LASTEXITCODE -ne 0) { throw "pip a échoué" }
    Write-Host "Grammalecte installé."
} catch {
    Write-Host "Grammalecte n'a pas pu être installé ($_). L'appli utilisera une correction plus simple." -ForegroundColor Yellow
}

# 4. Dictionnaire des synonymes ----------------------------------------------------
Etape "Téléchargement du dictionnaire des synonymes"
$thes = Join-Path $here "data\thes_fr.dat"
if (-not (Test-Path $thes)) {
    try {
        Invoke-WebRequest -Uri "https://raw.githubusercontent.com/LibreOffice/dictionaries/master/fr_FR/thes_fr.dat" -OutFile $thes -UseBasicParsing -ErrorAction Stop
        Write-Host "Dictionnaire des synonymes installé."
    } catch {
        Write-Host "Le dictionnaire des synonymes n'a pas pu être téléchargé ($_)." -ForegroundColor Yellow
    }
} else { Write-Host "Déjà présent." }

# 5. Modèle de reconnaissance vocale -------------------------------------------------
Etape "Téléchargement du modèle de reconnaissance vocale (environ 500 Mo, une seule fois)"
$modeles = Join-Path $env:APPDATA "blablappli\modeles"
New-Item -ItemType Directory -Force -Path $modeles | Out-Null
& $py -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8', download_root=r'$modeles'); print('Modèle prêt.')"

# 6. Raccourcis ------------------------------------------------------------------------
Etape "Création des raccourcis (Bureau et menu Démarrer)"
$shell = New-Object -ComObject WScript.Shell
$cibles = @(
    [Environment]::GetFolderPath("Desktop"),
    (Join-Path ([Environment]::GetFolderPath("StartMenu")) "Programs")
)
foreach ($dossier in $cibles) {
    $lnk = $shell.CreateShortcut((Join-Path $dossier "blablappli.lnk"))
    $lnk.TargetPath = "$env:WINDIR\System32\wscript.exe"
    $lnk.Arguments = "`"$here\lancer.vbs`""
    $lnk.WorkingDirectory = $here
    $lnk.IconLocation = "$here\data\blablappli.ico"
    $lnk.Description = "Dictée vocale en français"
    $lnk.Save()
}

Write-Host ""
Write-Host "==========================================" -ForegroundColor Green
Write-Host " blablappli est installé !" -ForegroundColor Green
Write-Host " Lance-le avec l'icône 'blablappli' du Bureau." -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Green
Start-Process "$env:WINDIR\System32\wscript.exe" -ArgumentList "`"$here\lancer.vbs`""
