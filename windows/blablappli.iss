; Programme d'installation Windows de blablappli (Inno Setup)
#define AppVersion GetEnv("BLABLAPPLI_VERSION")
#if AppVersion == ""
  #define AppVersion "0.1.0"
#endif

[Setup]
AppId={{6B0D2E9A-3F4C-4C1B-9B7E-B1AB1A9911A1}
AppName=blablappli
AppVersion={#AppVersion}
AppPublisher=gael
DefaultDirName={localappdata}\Programs\blablappli
DefaultGroupName=blablappli
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=dist
OutputBaseFilename=blablappli-installation
SetupIconFile=data\blablappli.ico
UninstallDisplayIcon={app}\blablappli.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"

[Tasks]
Name: "desktopicon"; Description: "Créer une icône sur le Bureau"; GroupDescription: "Raccourcis :"
Name: "autostart"; Description: "Lancer blablappli au démarrage de Windows"; GroupDescription: "Raccourcis :"; Flags: unchecked

[Files]
Source: "dist\blablappli\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\blablappli"; Filename: "{app}\blablappli.exe"
Name: "{group}\Désinstaller blablappli"; Filename: "{uninstallexe}"
Name: "{autodesktop}\blablappli"; Filename: "{app}\blablappli.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "blablappli"; ValueData: """{app}\blablappli.exe"""; Tasks: autostart; Flags: uninsdeletevalue

[Run]
Filename: "{app}\blablappli.exe"; Description: "Lancer blablappli maintenant"; Flags: nowait postinstall skipifsilent
