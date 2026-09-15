; Inno Setup script of the Dedalo desktop app.
; Compiled by build.ps1:  ISCC.exe /DAppVersion=2.0.0 packaging\windows\installer.iss
; Output: packaging\windows\output\Dedalo-Setup.exe

#ifndef AppVersion
  #define AppVersion "2.0.0"
#endif

; Registry key of the Microsoft Edge WebView2 Runtime (documented by Microsoft).
#define WebView2Key "Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

[Setup]
; Fixed identifier: an upgrade replaces the previous installation instead of adding a second one.
AppId={{8C5E2B7A-4F1D-4B6E-9A3C-2D7F1E6B5A40}
AppName=Dedalo
AppVersion={#AppVersion}
AppPublisher=Dedalo PoC
DefaultDirName={autopf}\Dedalo
DefaultGroupName=Dedalo
DisableProgramGroupPage=yes
; Lets a user without administrator rights install for their account only.
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=output
OutputBaseFilename=Dedalo-Setup
SetupIconFile=build\dedalo.ico
UninstallDisplayIcon={app}\Dedalo.exe
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "italian"; MessagesFile: "compiler:Languages\Italian.isl"

[Tasks]
; Checked by default: the goal is an icon on the desktop.
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[Files]
Source: "dist\Dedalo\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "build\MicrosoftEdgeWebview2Setup.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall; Check: not IsWebView2Installed

[Icons]
Name: "{group}\Dedalo"; Filename: "{app}\Dedalo.exe"
Name: "{autodesktop}\Dedalo"; Filename: "{app}\Dedalo.exe"; Tasks: desktopicon

[Run]
Filename: "{tmp}\MicrosoftEdgeWebview2Setup.exe"; Parameters: "/silent /install"; StatusMsg: "Installazione di Microsoft Edge WebView2..."; Check: not IsWebView2Installed; Flags: waituntilterminated
Filename: "{app}\Dedalo.exe"; Description: "{cm:LaunchProgram,Dedalo}"; Flags: nowait postinstall skipifsilent

; No [UninstallDelete]: the knowledge base in %LOCALAPPDATA%\Dedalo survives an uninstall,
; so removing the program by mistake never deletes the experts' work.

[Code]
function HasWebView2(RootKey: Integer; SubKey: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey, SubKey, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

function IsWebView2Installed: Boolean;
begin
  Result := HasWebView2(HKLM, 'SOFTWARE\WOW6432Node\{#WebView2Key}')
    or HasWebView2(HKLM, 'SOFTWARE\{#WebView2Key}')
    or HasWebView2(HKCU, 'Software\{#WebView2Key}');
end;
