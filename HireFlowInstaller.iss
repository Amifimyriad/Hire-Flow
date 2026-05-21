[Setup]
AppName=HireFlow
AppVersion=1.0.0
DefaultDirName={autopf}\HireFlow
DefaultGroupName=HireFlow
OutputDir=dist
OutputBaseFilename=HireFlowInstaller
Compression=lzma
SolidCompression=yes

[Files]
Source: "dist\HireFlow\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\HireFlow"; Filename: "{app}\HireFlow.exe"
Name: "{commondesktop}\HireFlow"; Filename: "{app}\HireFlow.exe"

[Run]
Filename: "{app}\HireFlow.exe"; Description: "Launch HireFlow"; Flags: nowait postinstall skipifsilent
