; ============================================================
; Inno Setup script for PlayListMaker.
;
; How to use:
; 1. Install Inno Setup (free): https://jrsoftware.org/isinfo.php
; 2. Run build_exe.bat first to generate dist\PlayListMaker.exe
; 3. Open this file (PlayListMaker.iss) in the Inno Setup Compiler
; 4. Build > Compile (or F9)
; 5. The final installer appears at installer_output\PlayListMakerSetup.exe
;
; The wizard already includes two optional checkboxes: "Create a desktop
; shortcut" and "Create a Start Menu shortcut" (Start Menu is checked by
; default; desktop is left to the installer's discretion).
; ============================================================

; NOTE on user preferences (theme/colors):
; The app writes config.json to %APPDATA%\PlayListMaker\, NEVER inside
; this install folder ({app}). This is deliberate: the install folder is
; typically read-only for non-admin Windows users, so it could never be
; written to safely at runtime. No config file ships with the installer —
; the app creates one itself, with default values, on first run.

#define MyAppName "PlayListMaker"
#define MyAppVersion "1.0"
#define MyAppPublisher "Daniel Dinis"
#define MyAppExeName "PlayListMaker.exe"

[Setup]
AppId={{B6C1E7B2-4F3A-4C9E-9B2A-PLAYLISTMAKER}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
OutputDir=..\installer_output
OutputBaseFilename=PlayListMakerSetup
SetupIconFile=..\resources\logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked
Name: "startmenuicon"; Description: "Create a Start Menu shortcut"; GroupDescription: "Additional shortcuts:"; Flags: checkedonce

[Files]
; The .exe built by PyInstaller (build_exe.bat) and anything else it
; packages into the same dist\ folder
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; If you use --onedir instead of --onefile in PyInstaller (launches
; faster, but produces a folder with multiple files instead of one .exe),
; swap the line above for this one, which copies the whole folder:
; Source: "..\dist\{#MyAppExeName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: startmenuicon
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Open {#MyAppName} now"; Flags: nowait postinstall skipifsilent
