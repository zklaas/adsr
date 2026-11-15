; Inno Setup script: the Windows installer for ADSR.
; Built by .github/workflows/release.yml from PyInstaller's dist\ADSR folder:
;   iscc /DAppVersion=1.0.0 packaging\adsr.iss
; Installs for the current user only (no administrator rights), adds a Start-menu
; entry and an uninstaller (Settings > Apps).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{204793A3-8042-5233-81D7-C702DA9931E7}
AppName=ADSR
AppVersion={#AppVersion}
AppPublisher=Zachary Klaas
AppPublisherURL=https://github.com/zklaas/adsr
DefaultDirName={localappdata}\Programs\ADSR
DefaultGroupName=ADSR
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\release
OutputBaseFilename=ADSR-Setup-Windows
SetupIconFile=..\icons\adsr.ico
UninstallDisplayIcon={app}\ADSR.exe
LicenseFile=..\LICENSE
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible

[Files]
Source: "..\dist\ADSR\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\ADSR"; Filename: "{app}\ADSR.exe"
Name: "{userdesktop}\ADSR"; Filename: "{app}\ADSR.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Run]
Filename: "{app}\ADSR.exe"; Description: "Start ADSR"; Flags: nowait postinstall skipifsilent
