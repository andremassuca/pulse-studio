; Inno Setup script. Build with scripts\build.ps1 (it passes the version).

#ifndef MyAppVersion
  #define MyAppVersion "0.1.0"
#endif
#define MyAppName "Pulse Studio"
#define MyAppExe "Pulse Studio.exe"

[Setup]
AppId={{6B0F6E52-3C0B-4C55-9B7B-5D8E2F7A41C3}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher=andremassuca
AppPublisherURL=https://github.com/andremassuca/pulse-studio
AppSupportURL=https://github.com/andremassuca/pulse-studio/issues
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
; The folder page is shown, so the app can be installed on any drive.
DisableDirPage=no
UsePreviousAppDir=yes
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist
OutputBaseFilename=PulseStudio-Setup-{#MyAppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "..\dist\Pulse Studio\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Settings written by the app (last port, theme, window size). Recordings in
; Documents are the user's data and are left alone.
Type: filesandordirs; Name: "{userappdata}\Pulse Studio"
