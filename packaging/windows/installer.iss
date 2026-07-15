; Inno Setup script — Drive Local Open (per-user install)
#define MyAppName "Drive Local Open"
#ifndef MyAppVersion
  #define MyAppVersion "0.2.0"
#endif
#define MyAppPublisher "I-S3"
#define MyAppURL "https://www.i-s3.com/tools/drive-local-open.html"
#define MyAppExeName "drive-local-open.exe"

[Setup]
AppId={{8E7C2F1A-4B9D-4E2A-9C11-DRIVELOCALOPEN}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
DefaultDirName={localappdata}\Programs\DriveLocalOpen
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\..\dist
OutputBaseFilename=DriveLocalOpen-Setup-{#MyAppVersion}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
InfoBeforeFile=
SetupLogging=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "japanese"; MessagesFile: "compiler:Languages\Japanese.isl"

[Files]
Source: "..\..\dist\drive-local-open.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Registry]
; URL protocol: drive-local-open://
Root: HKCU; Subkey: "Software\Classes\drive-local-open"; ValueType: string; ValueName: ""; ValueData: "URL:Drive Local Open"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\drive-local-open"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\drive-local-open\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --open files ""%1"""

[Run]
Filename: "{app}\{#MyAppExeName}"; Parameters: "--help"; Flags: runhidden; StatusMsg: "Verifying install..."
