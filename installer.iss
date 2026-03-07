; Clyro Windows Installer — Inno Setup 6
; Produces: dist\ClyroSetup.exe
; Users just double-click and use — no extra installs needed.

#define MyAppName      "Clyro"
#define MyAppPublisher "Clyro"
#define MyAppExeName   "Clyro.exe"
#define MyAppDir       "dist\Clyro"

#ifndef MyAppVersion
  #error MyAppVersion must be provided by build_release.py
#endif

[Setup]
AppId={{B4C7E2D1-3F9A-4B2C-9D5E-1A2B3C4D5E6F}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL=https://github.com/
DefaultDirName={localappdata}\Programs\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
; Single output .exe
OutputDir=dist
OutputBaseFilename=ClyroSetup
SetupIconFile=src\clyro\assets\icons\app\256.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
; Don't require admin — installs to user's LocalAppData (no UAC prompt)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Minimum Windows 10
MinVersion=10.0
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";    Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "startupentry";   Description: "Launch Clyro when Windows starts";                                 Flags: unchecked

[Files]
; Copy the entire PyInstaller output folder
Source: "{#MyAppDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu shortcut
Name: "{group}\{#MyAppName}";           Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"
; Optional Desktop shortcut
Name: "{autodesktop}\{#MyAppName}";     Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
; Uninstall shortcut in Start Menu
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Registry]
; Optional: launch at Windows startup if user chose the task
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "{#MyAppName}"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: startupentry

[Run]
; Launch after install finishes (optional, user can uncheck)
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; Kill the app if it's running before uninstall
Filename: "taskkill.exe"; Parameters: "/F /IM {#MyAppExeName}"; Flags: runhidden; RunOnceId: "KillClyro"

[UninstallDelete]
; Clean up user data folder (optional — comment out to keep user settings)
; Type: filesandordirs; Name: "{localappdata}\Clyro"
