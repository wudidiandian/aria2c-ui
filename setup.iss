; Aria2c UI 安装程序脚本
; 使用 Inno Setup 编译

#define MyAppName "Aria2c UI"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "wudidiandian"
#define MyAppURL "https://github.com/wudidiandian/aria2c-ui"
#define MyAppExeName "Aria2cUI.exe"

[Setup]
; 应用程序信息
AppId={{8A3B4C5D-6E7F-8G9H-0I1J-2K3L4M5N6O7P}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\Aria2cUI
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=LICENSE.txt
InfoBeforeFile=README.md
OutputDir=installer
OutputBaseFilename=Aria2cUI-{#MyAppVersion}-Setup
SetupIconFile=assets\icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
; 中文语言支持（如果安装了中文语言包）
; Name: "chinesesimplified"; MessagesFile: "compiler:Languages\ChineseSimplified.isl"
; 默认使用英文
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; 主程序文件
Source: "dist\Aria2cUI\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
; 依赖文件
Source: "dist\Aria2cUI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 注意: 不要在任何共享系统文件上使用 "Flags: ignoreversion"

[Icons]
; 开始菜单快捷方式
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
; 桌面快捷方式
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
; 安装完成后可选运行
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 卸载时删除的文件和目录
Type: filesandordirs; Name: "{app}\downloads"
Type: filesandordirs; Name: "{app}\aria2.session"
Type: filesandordirs; Name: "{app}\aria2c.log"
Type: filesandordirs; Name: "{app}\config.json"

[Code]
// 检查是否已安装
function InitializeSetup(): Boolean;
begin
  Result := true;
end;

// 安装前检查
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := true;
end;