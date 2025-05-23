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
copy /Y "dist\*.exe" "instalador\"

echo.
echo Generando el instalador con Inno Setup...
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" ".\instalador\setup.iss"

echo.
echo Proceso completado. El instalador ha sido generado exitosamente.
pause