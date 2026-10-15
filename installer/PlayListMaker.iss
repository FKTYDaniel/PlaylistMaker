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
;
; UNINSTALLING: nothing extra was needed for this. Inno Setup always
; generates a working uninstaller unless "Uninstallable=no" is set below
; (it isn't, and "Uninstallable=yes" is spelled out explicitly further
; down as a reminder) - installing this app already gives the user THREE
; ways to remove it afterwards, all equivalent: Windows Settings > Apps,
; the classic Control Panel > Programs and Features, and the "Uninstall
; PlayListMaker" shortcut this script adds to its own Start Menu group
; (see [Icons] below).
; ============================================================

; NOTE on user preferences (theme/colors):
; The app writes config.json to %APPDATA%\PlayListMaker\, NEVER inside
; this install folder ({app}). This is deliberate: the install folder is
; typically read-only for non-admin Windows users, so it could never be
; written to safely at runtime. No config file ships with the installer --
; the app creates one itself, with default values, on first run.
; As a result, uninstalling does NOT delete that config.json (Inno Setup
; only removes what it installed, under {app}, by default) - so if the
; app is ever reinstalled, the user's theme/colors are still there. If
; the app should instead be a clean slate on every reinstall, that file
; could be removed too via an [UninstallDelete] entry, but leaving user
; preferences alone across an uninstall is the more common expectation.

#define MyAppName "PlayListMaker"
#define MyAppVersion "1.0"
#define MyAppPublisher "Daniel Dinis"
#define MyAppExeName "PlayListMaker.exe"

[Setup]
; A real, randomly-generated GUID -- this is what Windows uses internally
; to tell "this app, any version" apart from every other installed
; program. The previous value here, {{B6C1E7B2-4F3A-4C9E-9B2A-PLAYLISTMAKER},
; was not actually a valid GUID (its last segment must be exactly 12
; hexadecimal digits -- 0-9/A-F only -- and "PLAYLISTMAKER" is neither
; 12 characters nor valid hex). Generate your own via the Inno Setup
; IDE's Tools > Generate GUID if you fork this, so this installer's
; identity never collides with anyone else's.
AppId={{375FBCFD-799A-4F43-ADFD-E35A73B58152}
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
; Explicit for documentation's sake -- this is Inno Setup's own default,
; so leaving it out would behave identically, but spelling it out means
; nobody has to take that on faith when reading this file.
Uninstallable=yes
; PyInstaller (see build_exe.bat) builds a native 64-bit .exe on any
; current Python install, so this keeps the installer consistent with
; that if it's ever switched to an admin-elevated / Program Files
; install (PrivilegesRequired above) rather than the per-user one it
; uses today. Harmless no-op on the per-user path.
ArchitecturesInstallIn64BitMode=x64compatible

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
; This one is what actually runs the auto-generated uninstaller
; ({uninstallexe}, i.e. {app}\unins000.exe) -- it's created regardless of
; the "startmenuicon" task above, since removing the app shouldn't
; depend on a shortcut the user might have declined during install.
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Open {#MyAppName} now"; Flags: nowait postinstall skipifsilent
