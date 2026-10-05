@echo off
echo Instalando dependencias...

echo.
echo Generando version sin consola...
pyinstaller Tuquito_no_console.spec

echo.
echo Generando version con consola...
pyinstaller Tuquito_console.spec

echo.
echo Copiando archivos al instalador...
xcopy ".\dist\*.*" ".\instalador\" /E /Y /I

echo.
echo Generando el instalador con Inno Setup...
powershell -NoLogo -NoProfile -Command "& 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' '.\instalador\setup_console.iss'"
if errorlevel 1 (
    echo Error al generar el instalador con Inno Setup.
    exit /b 1
)

echo.
echo Generando el instalador sin consolaInno Setup...
powershell -NoLogo -NoProfile -Command "& 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' '.\instalador\setup_no_console.iss'"
if errorlevel 1 (
    echo Error al generar el instalador con Inno Setup.
    exit /b 1
)

echo .
echo Eliminando archivos temporales...
rmdir /s /q ".\instalador\Tuquito-v2_2_console"
rmdir /s /q ".\instalador\Tuquito-v2_2"


echo.
echo Proceso completado. El instalador ha sido generado exitosamente.
pause