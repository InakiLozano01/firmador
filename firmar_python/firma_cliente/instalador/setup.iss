[Setup]
AppName=Tuquito
AppVersion=1.8
DefaultDirName={commonpf}\Tuquito
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
Source: "..\dist\Tuquito-v1_8_console.exe"; DestDir: "{commonpf}\Tuquito"; Flags: ignoreversion
Source: "..\dist\Tuquito-v1_8.exe"; DestDir: "{commonpf}\Tuquito"; Flags: ignoreversion
Source: "..\token_lib.json"; DestDir: "{commonpf}\Tuquito"; Flags: ignoreversion

[Icons]
Name: "{commonprograms}\Tuquito"; Filename: "{commonpf}\Tuquito\Tuquito-v1_8.exe"
Name: "{commondesktop}\Tuquito"; Filename: "{commonpf}\Tuquito\Tuquito-v1_8.exe"

[Registry]
; Add to Windows Startup for all users
Root: HKLM; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "Tuquito"; ValueData: "{commonpf}\Tuquito\Tuquito-v1_8.exe"; Flags: uninsdeletevalue

[Run]
Filename: "{commonpf}\Tuquito\Tuquito-v1_8.exe"; Description: "Iniciar Tuquito"; Flags: nowait postinstall