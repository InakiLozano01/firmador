[Setup]
AppName=Tuquito
AppVersion=2.0
DefaultDirName={autopf32}\Tuquito
DefaultGroupName=Tuquito
OutputDir=.
OutputBaseFilename=TuquitoInstaller2_0
Compression=lzma2
SolidCompression=yes
DisableWelcomePage=no
WizardImageFile=tapir.bmp
SetupIconFile="app.ico"
PrivilegesRequired=admin

[Languages]
Name: "es"; MessagesFile: "compiler:Languages\Spanish.isl"

[CustomMessages]
es.SetupWindowTitle=Instalación de {AppName}
es.WelcomeLabel1=Estas por instalar {AppName}. El programa firmador del Tribunal de Cuentas de Tucumán.
es.WelcomeLabel2=Este asistente instalará {AppName} en su sistema. Se recomienda cerrar otras aplicaciones antes de continuar.
es.ButtonNext=Siguiente
es.ButtonCancel=Cancelar
es.ButtonFinish=Finalizar

[Files]
Source: "..\dist\Tuquito-v2_0_console.exe"; DestDir: "{autopf32}\Tuquito"; Flags: ignoreversion
Source: "..\dist\Tuquito-v2_0.exe"; DestDir: "{autopf32}\Tuquito"; Flags: ignoreversion
Source: ".\token_lib.json"; DestDir: "{autopf32}\Tuquito"; Flags: ignoreversion

[Icons]
Name: "{commonprograms}\Tuquito"; Filename: "{autopf32}\Tuquito\Tuquito-v2_0.exe"
Name: "{commondesktop}\Tuquito"; Filename: "{autopf32}\Tuquito\Tuquito-v2_0.exe"

[Registry]
; Add to Windows Startup for all users
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Tuquito"; ValueData: "{autopf32}\Tuquito\Tuquito-v2_0.exe"; Flags: uninsdeletevalue

[Run]
Filename: "{autopf32}\Tuquito\Tuquito-v2_0.exe"; Description: "Iniciar Tuquito"; Flags: nowait postinstall

[Dirs]
Name: "{app}"; Permissions: users-modify