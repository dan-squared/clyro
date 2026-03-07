[Setup]
AppName=Clyro
AppVersion=0.1.3
AppPublisher=Daniel
DefaultDirName={autopf}\Clyro
DefaultGroupName=Clyro
OutputDir=dist
OutputBaseFilename=ClyroSetup
Compression=lzma2
SolidCompression=yes
SetupIconFile=src\clyro\assets\icons\app\256.ico
UninstallDisplayIcon={app}\Clyro.exe
PrivilegesRequired=lowest
CloseApplications=yes
RestartApplications=yes
AppMutex=ClyroSingleInstanceMutex

[Files]
Source: "dist\Clyro\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "src\clyro\assets\icons\app\256.ico"; DestDir: "{app}"; DestName: "app_icon.ico"; Flags: ignoreversion

[Icons]
Name: "{group}\Clyro"; Filename: "{app}\Clyro.exe"; IconFilename: "{app}\app_icon.ico"
Name: "{autodesktop}\Clyro"; Filename: "{app}\Clyro.exe"; IconFilename: "{app}\app_icon.ico"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop icon"; GroupDescription: "Additional icons:"; Flags: unchecked
