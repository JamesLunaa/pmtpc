; Inno Setup script for the Windows installer. Built by .github/workflows/windows.yml:
;   iscc /DAppVersion=0.1.0 /DBuildDir=..\..\dist\pmtpc /DIconFile=..\..\build\pmtpc.ico pmtpc.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef BuildDir
  #define BuildDir "..\..\dist\pmtpc"
#endif
#ifndef IconFile
  #define IconFile "..\..\build\pmtpc.ico"
#endif

#define AppName "Phone Mic to PC"
#define AppExe "pmtpc.exe"
#define FirewallRule "Phone Mic to PC"

[Setup]
AppId={{EF16216D-DFAA-489F-955E-B7E0224BC7FB}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=Jose Cynon Luna
AppPublisherURL=https://github.com/JamesLunaa/pmtpc
AppSupportURL=https://github.com/JamesLunaa/pmtpc/issues
DefaultDirName={autopf}\pmtpc
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
; Admin rights are needed to add the firewall rule.
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..\dist
OutputBaseFilename=pmtpc-setup-{#AppVersion}
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExe}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes

[Tasks]
Name: "autostart"; Description: "Start {#AppName} when Windows starts"; Flags: unchecked
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon
Name: "{autostartup}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: autostart

[Run]
; Replace any rule from a previous install, then allow inbound audio on private networks only,
; so nobody on public Wi-Fi can stream into the virtual mic.
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#FirewallRule}"""; Flags: runhidden
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall add rule name=""{#FirewallRule}"" dir=in action=allow program=""{app}\{#AppExe}"" protocol=UDP profile=private,domain enable=yes"; Flags: runhidden
Filename: "{app}\{#AppExe}"; Description: "Start {#AppName}"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im {#AppExe}"; Flags: runhidden; RunOnceId: "StopApp"
Filename: "{sys}\netsh.exe"; Parameters: "advfirewall firewall delete rule name=""{#FirewallRule}"""; Flags: runhidden; RunOnceId: "DeleteFirewallRule"
