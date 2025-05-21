[Setup]
AppName=Tuquito
AppVersion=2.0
DefaultDirName={pf}\Tuquito
DefaultGroupName=Tuquito
OutputDir=.
OutputBaseFilename=TuquitoInstaller
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
Source: ".\Tuquito-v2_0_console.exe"; DestDir: "{pf}\Tuquito"; Flags: ignoreversion
Source: ".\Tuquito-v2_0.exe"; DestDir: "{pf}\Tuquito"; Flags: ignoreversion
Source: "token_lib.json"; DestDir: "{pf}\Tuquito"; Flags: ignoreversion

[Icons]
Name: "{commonprograms}\Tuquito"; Filename: "{pf}\Tuquito\Tuquito-v2_0.exe"
Name: "{commondesktop}\Tuquito"; Filename: "{pf}\Tuquito\Tuquito-v2_0.exe"

[Registry]
; Add to Windows Startup for all users
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Tuquito"; ValueData: "{pf}\Tuquito\Tuquito-v2_0.exe"; Flags: uninsdeletevalue

[Run]
Filename: "{pf}\Tuquito\Tuquito-v2_0.exe"; Description: "Iniciar Tuquito"; Flags: nowait postinstall