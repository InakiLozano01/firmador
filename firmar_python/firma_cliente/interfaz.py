import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.ttk import Button, Style
import os
from PIL import Image, ImageTk
import time

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

    if mode == 'python':
        icon = tk.PhotoImage(file="./images/icono_token.png")
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
        icon = tk.PhotoImage(file=os.path.join(exe_dir, "images", "icono_token.png"))

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
        entry_pin.focus_set()

        button_frame = tk.Frame(pinwindow)
        button_frame.pack(pady=10)
        style = Style()
        style.configure("TButton", font=("Arial", 12), padding=10)

        base_path = "./images/"
        if mode != 'python':
            base_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "images")
            # For PyInstaller, if images are bundled directly (not in an 'images' subdir of the temp folder)
            # you might need: base_path = os.path.dirname(os.path.abspath(__file__))

        try:
            original_aceptar = Image.open(os.path.join(base_path, "aceptar.png"))
            original_cancelar = Image.open(os.path.join(base_path, "cancelar.png"))
        except FileNotFoundError as fnf_e:
            print(f"Error: Icono no encontrado - {fnf_e}. Asegúrese que las imágenes estén en la carpeta correcta.")
            # Fallback: proceed without icons or use placeholder text buttons
            # For simplicity, we'll let it proceed, buttons will just lack icons.
            iconaceptar = None
            iconcancelar = None
        else:
            resized_aceptar = original_aceptar.resize((25, 25))
            iconaceptar = ImageTk.PhotoImage(resized_aceptar)
            resized_cancelar = original_cancelar.resize((25, 25))
            iconcancelar = ImageTk.PhotoImage(resized_cancelar)

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

    if mode == 'python':
        original_image = Image.open("./images/certificado.png")
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
        original_image = Image.open(os.path.join(exe_dir, "images", "certificado.png"))
    resized_image = original_image.resize((50, 50))  # Resize to 50x50 pixels
    iconcertificado = ImageTk.PhotoImage(resized_image)

    try:
        for i, (cert, _) in enumerate(certificates):

            input_string = str(cert.subject)
            start_cuil = input_string.find("CUIL")
            start_cn = input_string.find("CN")
            end_cuil = input_string.find(",", start_cuil)
            end_cn = input_string.find(")", start_cn)
            cuil = input_string[start_cuil:end_cuil]
            cn = input_string[start_cn:end_cn]
            resultado = f"{cuil} - {cn}"

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