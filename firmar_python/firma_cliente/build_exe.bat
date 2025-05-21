@echo off
echo Instalando dependencias...
pip install pyinstaller pillow pystray cryptography PyKCS11 flask flask-cors psutil

echo.
echo Generando version sin consola...
pyinstaller --noconfirm --onefile --windowed ^
  --add-data "images/*;images/" ^
  --icon "images/app.ico" ^
  --hidden-import "PIL._tkinter" ^
  --hidden-import "tkinter" ^
  --name "Tuquito-v2_0" ^
  main.py

echo.
echo Generando version con consola...
pyinstaller --noconfirm --onefile --console ^
  --add-data "images/*;images/" ^
  --icon "images/app.ico" ^
  --hidden-import "PIL._tkinter" ^
  --hidden-import "tkinter" ^
  --name "Tuquito-v2_0_console" ^
  main.py

echo.
echo Copiando archivos al instalador...
copy /Y "dist\Tuquito-v2_0.exe" "..\..\instalador\"
copy /Y "dist\Tuquito-v2_0_console.exe" "..\..\instalador\"

echo.
echo Proceso completado. Los archivos EXE han sido generados y copiados a la carpeta instalador.
echo Ahora puedes usar Inno Setup Compiler para generar el instalador con setup.iss
pause 