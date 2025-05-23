import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.ttk import Button, Style
import os
from PIL import Image, ImageTk
import time
import re

def select_token_slot(token_info, result, mode):
    def on_select(evt):
        w = evt.widget
        index = w.grid_info()['row']
        slot_info = token_info[index]
        selected_slot.set(index)
        result.append(index)
        token_window.destroy()

    try:
        mainwindow = tk.Tk()
        mainwindow.withdraw()
    except Exception as e:
        print(f"Error inesperado al crear la ventana principal: {str(e)}")
        return

    windows_base_height = 100
    button_height = 75
    total_height = windows_base_height + len(token_info) * button_height
    
    
    token_window = tk.Toplevel(mainwindow)
    token_window.title("Ventana de selección de Token")
    token_window.geometry(f"500x{total_height}")
    token_window.resizable(False, False)
    token_window.grab_set()

    # Set window icon
    try:
        if mode == 'python':
            # Assuming interfaz.py is in firma_cliente, so ./images/ is firma_cliente/images/
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "app.ico")
            if not os.path.exists(icon_path): # Fallback if not directly in images subdir of script
                icon_path = "./images/app.ico" 
        else:
            # For EXE mode, __file__ is where the script is (possibly temp path)
            # We assume 'images' folder is a subdirectory relative to the script/exe location
            exe_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(exe_dir, "images", "app.ico")
            # If images are bundled directly at the root level with the exe (not in an 'images' subfolder)
            if not os.path.exists(icon_path):
                icon_path = os.path.join(exe_dir, "app.ico")


        if os.path.exists(icon_path):
            token_window.iconbitmap(icon_path)
        else:
            print(f"Icono 'app.ico' no encontrado en la ruta esperada: {icon_path}")
    except Exception as e:
        print(f"Error al establecer el icono de la ventana: {e}")

    # Ensure the window opens in the foreground and centered
    token_window.attributes('-topmost', True)
    token_window.update_idletasks()
    x = (token_window.winfo_screenwidth() - token_window.winfo_reqwidth()) // 2
    y = (token_window.winfo_screenheight() - token_window.winfo_reqheight()) // 2
    token_window.geometry(f"+{x}+{y}")
    token_window.focus_force()

    # Add instruction label
    label_token = tk.Label(token_window, text="Seleccione un Token:", font=("Arial", 18, "bold"))
    label_token.pack(pady=10)

    frame = tk.Frame(token_window)
    frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    style = Style()
    style.configure("TButton", font=("Arial", 12), padding=10)

    icon = None # Initialize icon
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icon_file_name = "icono_token.png"
    icon_file_path = ""

    if mode == 'python':
        icon_file_path = os.path.join(script_dir, "images", icon_file_name)
    else: # EXE mode
        exe_dir = script_dir # In EXE mode, __file__ can be in a temp dir relative to bundled resources
        # Try 'images' subdirectory first
        potential_icon_path = os.path.join(exe_dir, "images", icon_file_name)
        if os.path.exists(potential_icon_path):
            icon_file_path = potential_icon_path
        else:
            # Fallback: assume icon is directly in the exe_dir (e.g. bundled at root if not in 'images')
            icon_file_path = os.path.join(exe_dir, icon_file_name)
    
    if os.path.exists(icon_file_path):
        try:
            icon = tk.PhotoImage(file=icon_file_path)
        except tk.TclError as e: # Catch Tkinter specific error for image loading
            print(f"Error loading token icon '{icon_file_name}' from {icon_file_path}: {e}")
            # icon remains None
    else:
        print(f"Warning: Token icon '{icon_file_name}' not found at expected path: {icon_file_path}")
        # icon remains None

    for i, info in enumerate(token_info):
        button = Button(frame, text=f"   Puerto USB numero: {i + 1}\n   Nombre del Token: {info['reader']}", style="TButton", image=icon, compound='left', cursor="hand2")
        button.grid(row=i, column=0, columnspan=2, pady=10, padx=30, sticky='ew')
        button.bind("<Button-1>", on_select)

    # Add a single column with weight to center the buttons
    frame.grid_columnconfigure(0, weight=1)
    frame.grid_columnconfigure(1, weight=1)

    selected_slot = tk.IntVar(value=-1)
    token_window.bind('<Escape>', lambda event: token_window.destroy())
    token_window.wait_window()
    mainwindow.destroy()

def select_library_file() -> str | None:
    """ 
    Opens a dialog to select a DLL library file.
    Returns the selected file path as a string, or None if cancelled or an error occurs.
    """ 
    # time.sleep(1) # Consider removing if not strictly necessary
    # Create a root window temporarily if one doesn't exist, then withdraw
    # This is often needed for filedialog to work correctly if no other Tk windows are active.
    root = None
    try:
        # Check if a default root window exists from a previous Tkinter call
        # This is a bit of a heuristic; a more robust solution involves managing a single Tk root.
        if not tk._default_root: 
            root = tk.Tk()
            # Set window icon for the temporary root
            try:
                # Try path relative to script first
                script_dir = os.path.dirname(os.path.abspath(__file__))
                icon_path_script_relative = os.path.join(script_dir, "images", "app.ico")
                # Fallback to current working directory's images folder
                icon_path_cwd_relative = os.path.join(".", "images", "app.ico")

                if os.path.exists(icon_path_script_relative):
                    root.iconbitmap(icon_path_script_relative)
                elif os.path.exists(icon_path_cwd_relative):
                    root.iconbitmap(icon_path_cwd_relative)
                else:
                    print(f"Icono 'app.ico' no encontrado en {icon_path_script_relative} ni {icon_path_cwd_relative}")
            except Exception as e:
                print(f"Error al establecer el icono de la ventana para select_library_file: {e}")
            root.withdraw() # Hide it
        
        file_path = filedialog.askopenfilename(
            initialdir="C:\\Windows\\System32\\", 
            title="Seleccione la biblioteca DLL del token", 
            filetypes=[("DLL files", "*.dll")]
        )
        return file_path if file_path else None # Return None if dialog is cancelled (empty string)
    except Exception as e:
        # Log the error, as this is unexpected for a file dialog operation itself
        print(f"Error inesperado al seleccionar la biblioteca DLL: {str(e)}")
        # Optionally, show a messagebox to the user from here, though main.py might also catch this.
        # messagebox.showerror("Error de Archivo", f"No se pudo abrir el diálogo de selección de archivo: {str(e)}")
        return None # Indicate failure
    finally:
        if root: # Destroy the temporary root if we created it
            root.destroy()

def get_pin_from_user(mode) -> str | None:
    """
    Displays a dialog to get the user's PIN.
    Returns the PIN string if entered, or None if cancelled or an error occurs during dialog setup.
    """
    global getpin # Still using global for simplicity within this function's Tkinter callbacks
    getpin = None 
    # time.sleep(1) # Consider removing

    pinwindow = None # Initialize for potential error before assignment
    try:
        pinwindow = tk.Tk()
        pinwindow.title("Introduzca su PIN")

        # Set window icon
        try:
            if mode == 'python':
                icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "app.ico")
                if not os.path.exists(icon_path): 
                    icon_path = "./images/app.ico" 
            else:
                exe_dir = os.path.dirname(os.path.abspath(__file__))
                icon_path = os.path.join(exe_dir, "images", "app.ico")
                if not os.path.exists(icon_path):
                     icon_path = os.path.join(exe_dir, "app.ico")
            
            if os.path.exists(icon_path):
                pinwindow.iconbitmap(icon_path)
            else:
                print(f"Icono 'app.ico' no encontrado en la ruta esperada para get_pin_from_user: {icon_path}")
        except Exception as e:
            print(f"Error al establecer el icono de la ventana para get_pin_from_user: {e}")

        pinwindow.geometry("500x175") # Adjusted height slightly for better fit
        pinwindow.resizable(False, False)
        pinwindow.grab_set()

        pinwindow.attributes('-topmost', True)
        pinwindow.update_idletasks()
        x = (pinwindow.winfo_screenwidth() - pinwindow.winfo_reqwidth()) // 2
        y = (pinwindow.winfo_screenheight() - pinwindow.winfo_reqheight()) // 2
        pinwindow.geometry(f"+{x}+{y}")
        pinwindow.focus_force()

        pin_frame = tk.Frame(pinwindow)
        pin_frame.pack(pady=10)

        label_pin = tk.Label(pin_frame, text="Introduzca su PIN: ", font=("Arial", 14, "bold"))
        label_pin.pack(side="left", pady=10)

        entry_pin = tk.Entry(pin_frame, show="*", width=20, font=("Arial", 14)) # Changed show to *
        entry_pin.pack(side="left", pady=10)
        # entry_pin.focus_set()  # Commented out - will set focus later

        button_frame = tk.Frame(pinwindow)
        button_frame.pack(pady=10)
        style = Style()
        style.configure("TButton", font=("Arial", 12), padding=10)

        script_dir = os.path.dirname(os.path.abspath(__file__))
        base_path_for_images = ""

        if mode == 'python':
            base_path_for_images = os.path.join(script_dir, "images")
        else: # EXE mode
            exe_dir = script_dir # In EXE mode, __file__ can be in a temp dir
            path_in_images_subdir = os.path.join(exe_dir, "images", "aceptar.png") # Check with a known image
            path_in_exe_dir = os.path.join(exe_dir, "aceptar.png") # Check with a known image

            if os.path.exists(path_in_images_subdir):
                base_path_for_images = os.path.join(exe_dir, "images")
            elif os.path.exists(path_in_exe_dir):
                base_path_for_images = exe_dir
            else:
                # Fallback: default to 'images' subdirectory path.
                # Loading attempts below will then print warnings if files are not found.
                base_path_for_images = os.path.join(exe_dir, "images")

        iconaceptar = None
        iconcancelar = None
        
        try:
            path_aceptar = os.path.join(base_path_for_images, "aceptar.png")
            path_cancelar = os.path.join(base_path_for_images, "cancelar.png")

            if os.path.exists(path_aceptar):
                original_aceptar = Image.open(path_aceptar)
                resized_aceptar = original_aceptar.resize((25, 25))
                iconaceptar = ImageTk.PhotoImage(resized_aceptar)
            else:
                print(f"Warning: Icon 'aceptar.png' not found at {path_aceptar}.")

            if os.path.exists(path_cancelar):
                original_cancelar = Image.open(path_cancelar)
                resized_cancelar = original_cancelar.resize((25, 25))
                iconcancelar = ImageTk.PhotoImage(resized_cancelar)
            else:
                print(f"Warning: Icon 'cancelar.png' not found at {path_cancelar}.")
        
        except Exception as e:
            print(f"Error loading or processing button icons: {e}. Ensure images are valid and in the correct location.")
            # iconaceptar and iconcancelar will remain None, allowing buttons to be created without icons


        def on_aceptar():
            global getpin
            getpin = entry_pin.get()
            if pinwindow:
                pinwindow.destroy()

        def on_cancelar():
            global getpin
            getpin = None
            if pinwindow:
                pinwindow.destroy()

        btn_aceptar = Button(button_frame, text="Aceptar", style="TButton", image=iconaceptar, compound='left', command=on_aceptar)
        btn_aceptar.pack(side=tk.LEFT, padx=5)

        btn_cancelar = Button(button_frame, text="Cancelar", style="TButton", image=iconcancelar, compound='left', command=on_cancelar)
        btn_cancelar.pack(side=tk.LEFT, padx=5)

        button_frame.pack(pady=10, anchor=tk.CENTER)

        pinwindow.bind('<Return>', lambda event: on_aceptar())
        pinwindow.bind('<Escape>', lambda event: on_cancelar())
        pinwindow.protocol("WM_DELETE_WINDOW", on_cancelar) # Handle window close button

        # Ensure the window is fully displayed before setting focus
        def set_focus_to_entry():
            entry_pin.focus_force()
            entry_pin.icursor(0)  # Set cursor at the beginning of the entry

        # Set focus after the window is completely rendered
        pinwindow.after(100, set_focus_to_entry)

        pinwindow.mainloop()
        return getpin # Directly return the pin or None

    except Exception as e:
        print(f"Error fatal al crear la ventana de PIN: {str(e)}")
        if pinwindow: # Attempt to destroy if it was partially created
            try:
                pinwindow.destroy()
            except tk.TclError:
                pass # Window might already be destroyed or in a bad state
        return None # Indicates failure to even display dialog or cancellation

def select_certificate(certificates, result, mode):
    def on_select(evt):
        w = evt.widget
        index = w.grid_info()['row']
        cert_info = certificates[index]
        selected_cert.set(index)
        result.append(index)
        cert_window.destroy()

    time.sleep(1)
    certs = tk.Tk()
    certs.withdraw()  # Hide the root window

    windows_base_height = 100
    button_height = 75
    total_height = windows_base_height + len(certificates) * button_height
        
    cert_window = tk.Toplevel(certs)
    cert_window.title("Ventana de selección de certificado")

    # Set window icon
    try:
        if mode == 'python':
            icon_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images", "app.ico")
            if not os.path.exists(icon_path):
                icon_path = "./images/app.ico"
        else:
            exe_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(exe_dir, "images", "app.ico")
            if not os.path.exists(icon_path):
                icon_path = os.path.join(exe_dir, "app.ico")
        
        if os.path.exists(icon_path):
            cert_window.iconbitmap(icon_path)
        else:
            print(f"Icono 'app.ico' no encontrado en la ruta esperada para select_certificate: {icon_path}")
    except Exception as e:
        print(f"Error al establecer el icono de la ventana para select_certificate: {e}")

    cert_window.geometry(f"500x{total_height}")
    cert_window.resizable(False, False)
    cert_window.grab_set()

    # Ensure the window opens in the foreground and centered
    cert_window.attributes('-topmost', True)
    cert_window.update_idletasks()
    x = (cert_window.winfo_screenwidth() - cert_window.winfo_reqwidth()) // 2
    y = (cert_window.winfo_screenheight() - cert_window.winfo_reqheight()) // 2
    cert_window.geometry(f"+{x}+{y}")
    cert_window.focus_force()

    # Add instruction label
    label_certificado = tk.Label(cert_window, text="Seleccione un certificado:", font=("Arial", 18, "bold"))
    label_certificado.pack(pady=10)

    frame = tk.Frame(cert_window)
    frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    style = Style()
    style.configure("TButton", font=("Arial", 10), padding=10)

    iconcertificado = None # Initialize in case image loading fails
    script_dir = os.path.dirname(os.path.abspath(__file__))
    image_file_name = "certificado.png"
    image_path = ""

    if mode == 'python':
        image_path = os.path.join(script_dir, "images", image_file_name)
    else: # EXE mode
        exe_dir = script_dir # In EXE mode, __file__ can be in a temp dir
        path_in_images_subdir = os.path.join(exe_dir, "images", image_file_name)
        path_in_exe_dir = os.path.join(exe_dir, image_file_name)

        if os.path.exists(path_in_images_subdir):
            image_path = path_in_images_subdir
        elif os.path.exists(path_in_exe_dir):
            image_path = path_in_exe_dir
        else:
            # Fallback: default to 'images' subdirectory path.
            # Loading attempt below will print a warning if not found.
            image_path = path_in_images_subdir
            
    if os.path.exists(image_path):
        try:
            original_image = Image.open(image_path)
            resized_image = original_image.resize((50, 50))
            iconcertificado = ImageTk.PhotoImage(resized_image)
        except Exception as e:
            print(f"Error loading or processing certificate icon '{image_file_name}' from {image_path}: {e}")
            # iconcertificado remains None
    else:
        print(f"Warning: Certificate icon '{image_file_name}' not found at {image_path} (tried primary and fallback locations).")
        # iconcertificado remains None

    try:
        for i, cert_subject_str in enumerate(certificates): # certificates is now a list of subject strings
            # Parse CUIL and CN from the RFC 4514 subject string
            # This is a simplified parsing. A more robust solution might involve a dedicated LDAP DN parser.
            cuil = "N/A"
            cn = "N/A"
            cuil_extracted_from_cn = False # Initialize here
            
            # Attempt to extract CUIL (assuming it's in a serialNumber or a specific OID)
            # Example OID for CUIL in Argentina: 2.5.4.5 (serialNumber)
            # Or sometimes it might be part of CN or other attributes.
            parts = cert_subject_str.split(',')
            for part in parts:
                if 'serialNumber=' in part and ('CUIL' in part.upper() or 'CUIT' in part.upper()):
                    cuil = part.split('=')[-1]
                    break # Found CUIL in serialNumber
                elif 'CN=' in part:
                    cn_part = part.split('=')[-1]
                    # Check if CUIL is embedded in CN
                    if 'CUIL' in cn_part.upper() or 'CUIT' in cn_part.upper():
                        # Try to extract number following CUIL/CUIT
                        match = re.search(r'(CUIL|CUIT)?[^0-9]*(\d+)', cn_part, re.IGNORECASE)
                        if match and not cuil_extracted_from_cn: # Prioritize serialNumber if found
                            cuil = match.group(2)
                            cuil_extracted_from_cn = True # Mark that CUIL was found in CN
                    if cn == "N/A": # Take the first CN found
                        cn = cn_part
            
            # If CN was not explicitly found but CUIL was, CN might be the remaining part or a specific field
            # For simplicity, if CN is still N/A, we might try to get the first CN attribute if present
            if cn == "N/A":
                 for part in parts:
                    if 'CN=' in part:
                        cn = part.split('=')[-1]
                        break
            
            # Fallback if CUIL is still N/A but was found in CN and not set above
            if cuil == "N/A" and cuil_extracted_from_cn:
                 for part in parts:
                    if 'CN=' in part:
                        cn_part_val = part.split('=')[-1]
                        if 'CUIL' in cn_part_val.upper() or 'CUIT' in cn_part_val.upper():
                            match = re.search(r'(CUIL|CUIT)?[^0-9]*(\d+)', cn_part_val, re.IGNORECASE)
                            if match:
                                cuil = match.group(2)
                                break

            # If CUIL is still N/A, try a more general regex search across the whole subject string
            if cuil == "N/A":
                match_cuil_general = re.search(r'(CUIL|CUIT)[^0-9]*(\d{11})', cert_subject_str, re.IGNORECASE)
                if match_cuil_general:
                    cuil = match_cuil_general.group(2)

            # Clean up CN if it contains the CUIL already parsed
            if cn != "N/A" and cuil != "N/A" and cuil in cn:
                cn = cn.replace(cuil, '').replace('CUIL', '').replace('CUIT', '').strip(' -/')
                cn = re.sub(r'\s{2,}', ' ', cn).strip() # Remove extra spaces

            resultado = f"CUIL: {cuil} - CN: {cn}"
            if len(resultado) > 60: # Truncate if too long for button
                resultado = resultado[:57] + "..."

            button = Button(frame, text=f"{resultado}", style="TButton", image=iconcertificado, compound='left', cursor="hand2")
            button.grid(row=i, column=0, pady=10, padx=10, sticky='ew')
            button.bind("<Button-1>", on_select)

        # Add a single column with weight to center the buttons
        frame.grid_columnconfigure(0, weight=1)

        selected_cert = tk.IntVar(value=-1)
        cert_window.bind('<Escape>', lambda event: cert_window.destroy())
        cert_window.wait_window()
        certs.destroy()
    
    except Exception as e: # Catch more specific Exception
        print(f"Error en la ventana de selección de certificado: {str(e)}")
        if 'certs' in locals() and certs.winfo_exists():
            certs.destroy() # Ensure cleanup if certs window was created

def show_alert(message, callback=None):
    puerto_uso = tk.Tk()

    # Set window icon
    try:
        # Try path relative to script first
        script_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path_script_relative = os.path.join(script_dir, "images", "app.ico")
        # Fallback to current working directory's images folder
        icon_path_cwd_relative = os.path.join(".", "images", "app.ico")

        if os.path.exists(icon_path_script_relative):
            puerto_uso.iconbitmap(icon_path_script_relative)
        elif os.path.exists(icon_path_cwd_relative):
            puerto_uso.iconbitmap(icon_path_cwd_relative)
        else:
            print(f"Icono 'app.ico' no encontrado en {icon_path_script_relative} ni {icon_path_cwd_relative} para show_alert")
    except Exception as e:
        print(f"Error al establecer el icono de la ventana para show_alert: {e}")
    
    puerto_uso.withdraw()
    messagebox.showwarning("Alerta", message)
    puerto_uso.destroy()
    if callback:
        callback()