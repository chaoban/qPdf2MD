; qPdf2MD installer (Inno Setup 6). Built by build_installer.bat, which runs:
;
;   ISCC /DSourceDir=<dist\qPdf2MD> /DIconFile=<qPdf2MD.ico> /O<output folder> installer\qPdf2MD.iss
;
; SourceDir is the PyInstaller output of build_exe.bat. The version shown everywhere is read
; from qPdf2MD.exe, which gets it from APP_VERSION in qpdf2mk/__init__.py.

#ifndef SourceDir
  #define SourceDir AddBackslash(GetEnv("USERPROFILE")) + ".qpdf2mk\dist\qPdf2MD"
#endif
#ifndef IconFile
  #define IconFile AddBackslash(GetEnv("USERPROFILE")) + ".qpdf2mk\build\qPdf2MD\qPdf2MD.ico"
#endif
#define AppName "qPdf2MD"
#define AppPublisher "SAISAI.Dev"
#define AppCopyright "© 2026 SAISAI.Dev. Licensed under the GNU AGPL v3."
#define AppExeName "qPdf2MD.exe"
#if !FileExists(SourceDir + "\" + AppExeName)
  #error qPdf2MD.exe not found in SourceDir - run build_exe.bat first
#endif
#define AppVersion GetFileProductVersion(SourceDir + "\" + AppExeName)
; Must match SetCurrentProcessExplicitAppUserModelID in qpdf2mk/app.py (ORG_NAME.APP_NAME) so the taskbar
; groups the running window with its Start menu shortcut.
#define AppUserModelID "SAISAI.qPdf2MD"

[Setup]
; Never change AppId: it is how a newer installer finds and upgrades an existing installation.
AppId={{A698F1AF-4688-47C4-A80B-7D5E928BC639}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppCopyright={#AppCopyright}
AppContact=aisais.dev@gmail.com
VersionInfoCompany={#AppPublisher}
VersionInfoCopyright={#AppCopyright}
VersionInfoVersion={#AppVersion}
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
; Installs for the current user without admin rights; the wizard also offers "all users".
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
WizardStyle=modern
ShowLanguageDialog=auto
SetupIconFile={#IconFile}
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
OutputBaseFilename={#AppName}-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "zh_tw"; MessagesFile: "ChineseTraditional.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
zh_tw.AppComment=PDF 轉 Markdown 轉換器
en.AppComment=PDF to Markdown converter
zh_tw.ContextMenu=用 qPdf2MD 轉換成 Markdown
en.ContextMenu=Convert with qPdf2MD
zh_tw.ContextMenuTask=在 PDF 檔案與資料夾的右鍵選單加入「用 qPdf2MD 轉換成 Markdown」
en.ContextMenuTask=Add "Convert with qPdf2MD" to the right-click menu of PDF files and folders

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "contextmenu"; Description: "{cm:ContextMenuTask}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; An upgrade replaces the whole runtime so files dropped from a newer build cannot linger.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Comment: "{cm:AppComment}"; AppUserModelID: "{#AppUserModelID}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Comment: "{cm:AppComment}"; AppUserModelID: "{#AppUserModelID}"; Tasks: desktopicon

[Registry]
; Right-click menu for PDF files and folders (HKA = current user or all users, matching the install mode).
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\qPdf2MD"; ValueType: string; ValueName: ""; ValueData: "{cm:ContextMenu}"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\qPdf2MD"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#AppExeName}"",0"; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\qPdf2MD\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\Directory\shell\qPdf2MD"; ValueType: string; ValueName: ""; ValueData: "{cm:ContextMenu}"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\Directory\shell\qPdf2MD"; ValueType: string; ValueName: "Icon"; ValueData: """{app}\{#AppExeName}"",0"; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\Directory\shell\qPdf2MD\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExeName}"" ""%1"""; Tasks: contextmenu

[Run]
Filename: "{app}\{#AppExeName}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
