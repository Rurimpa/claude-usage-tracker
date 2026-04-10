[Setup]
AppName=Claude Usage Tracker
AppVersion=3.2.0
AppPublisher=OpalTools
DefaultDirName={localappdata}\ClaudeUsageTracker
DefaultGroupName=Claude Usage Tracker
OutputDir=output
OutputBaseFilename=ClaudeUsageTracker_Setup_v3.2.0
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayName=Claude Usage Tracker
UninstallDisplayIcon={app}\ClaudeUsageTracker.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Files]
Source: "dist\ClaudeUsageTracker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\data"
Name: "{app}\logs"

[Icons]
Name: "{group}\Claude Usage Tracker"; Filename: "{app}\ClaudeUsageTracker.exe"
Name: "{group}\Claude Usage Tracker をアンインスト�Eル"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Claude Usage Tracker"; Filename: "{app}\ClaudeUsageTracker.exe"

[Run]
Filename: "{app}\ClaudeUsageTracker.exe"; Description: "Claude Usage Tracker を起勁E; Flags: nowait postinstall skipifsilent
