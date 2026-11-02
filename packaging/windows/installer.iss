; Inno Setup script. Build: iscc /DAppVersion=0.1.0 packaging\windows\installer.iss
; Expects the PyInstaller output in dist\UniConv.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
; Never change this GUID: it identifies the app across versions (review #13)
AppId={{504A34CB-03E6-468D-B807-ABF6D6AC0117}
AppName=UniConv
AppVersion={#AppVersion}
AppVerName=UniConv {#AppVersion}
AppPublisher=Forgeline Optimizations
AppPublisherURL=https://github.com/Forgeline-Optimizations/UniConv
AppSupportURL=https://github.com/Forgeline-Optimizations/UniConv/issues
DefaultDirName={localappdata}\Programs\UniConv
DefaultGroupName=UniConv
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=UniConv-{#AppVersion}-windows-x86_64-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\UniConv.exe
UninstallDisplayName=UniConv

[Languages]
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: desktopicon; Description: "Snelkoppeling op het bureaublad"; Flags: unchecked

[Files]
Source: "..\..\dist\UniConv\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

; A version upgrade must not leave files of the old build behind in _internal.
[InstallDelete]
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{group}\UniConv"; Filename: "{app}\UniConv.exe"
Name: "{userdesktop}\UniConv"; Filename: "{app}\UniConv.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\UniConv.exe"; Description: "UniConv starten"; Flags: nowait postinstall skipifsilent

; The uninstaller removes {app} only. Config, log and work dir stay (documented in README).
