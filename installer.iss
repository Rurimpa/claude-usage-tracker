[Setup]
AppName=Claude Usage Tracker
AppVersion=3.0.0
AppPublisher=OpalTools
DefaultDirName={localappdata}\ClaudeUsageTracker
DefaultGroupName=Claude Usage Tracker
OutputDir=output
OutputBaseFilename=ClaudeUsageTracker_Setup_v3.0.0
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=lowest
UninstallDisplayName=Claude Usage Tracker
UninstallDisplayIcon={app}\ClaudeUsageTracker.exe

[Languages]
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Messages]
japanese.WelcomeLabel2=このウィザードは Claude Usage Tracker v3.0.0 をインストールします。%n%nClaude Code のトークン消費量・使用率を可視化するツールです。%n%n続行するには「次へ」をクリックしてください。

[Files]
Source: "dist\ClaudeUsageTracker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Dirs]
Name: "{app}\data"
Name: "{app}\logs"

[Icons]
Name: "{group}\Claude Usage Tracker"; Filename: "{app}\ClaudeUsageTracker.exe"
Name: "{group}\Claude Usage Tracker をアンインストール"; Filename: "{uninstallexe}"
Name: "{userdesktop}\Claude Usage Tracker"; Filename: "{app}\ClaudeUsageTracker.exe"

[Run]
Filename: "{app}\ClaudeUsageTracker.exe"; Description: "Claude Usage Tracker を起動"; Flags: nowait postinstall skipifsilent
