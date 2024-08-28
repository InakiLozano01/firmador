import tkinter as tk
from tkinter import filedialog, messagebox
from tkinter.ttk import Button, Style
from flask import jsonify
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

    mainwindow = tk.Tk()
    mainwindow.withdraw()  # Hide the mainwindow window

    windows_base_height = 100
    button_height = 75
    total_height = windows_base_height + len(token_info) * button_height
    
    
    token_window = tk.Toplevel(mainwindow)
    token_window.title("Ventana de selección de Token")
    token_window.geometry(f"500x{total_height}")
    token_window.resizable(False, False)
    token_window.grab_set()

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
        icon = tk.PhotoImage(file=os.path.join(exe_dir, "icono_token.png"))

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

def select_library_file():
    time.sleep(1)
    try:
        return filedialog.askopenfilename(initialdir="C:\\Windows\\System32\\", title="Seleccione la biblioteca DLL", filetypes=[("DLL files", "*.dll")]), 200
    except Exception as e:
        return jsonify({"status": False, "message": f"Error al seleccionar la biblioteca DLL: {str(e)}"}), 500

def get_pin_from_user(mode):
    global getpin
    getpin = None
    time.sleep(1)

    def aceptar():
        global getpin
        getpin = entry_pin.get()
        pinwindow.destroy()

    def cancelar():
        global getpin
        getpin = None
        pinwindow.destroy()

    pinwindow = tk.Tk()

    pinwindow.title("Introduzca su pin")
    pinwindow.geometry(f"500x165")
    pinwindow.resizable(False, False)
    pinwindow.grab_set()

    # Ensure the window opens in the foreground and centered
    pinwindow.attributes('-topmost', True)
    pinwindow.update_idletasks()
    x = (pinwindow.winfo_screenwidth() - pinwindow.winfo_reqwidth()) // 2
    y = (pinwindow.winfo_screenheight() - pinwindow.winfo_reqheight()) // 2
    pinwindow.geometry(f"+{x}+{y}")
    pinwindow.focus_force()


    pin_frame = tk.Frame(pinwindow)
    pin_frame.pack(pady=10)

    # Crear un campo de entrada para el PIN
    label_pin = tk.Label(pin_frame, text="Introduzca su PIN: ", font=("Arial", 14, "bold"))
    label_pin.pack(side="left", pady=10)

    entry_pin = tk.Entry(pin_frame, show="o", width=20, font=("Arial", 14))
    entry_pin.pack(side="left", pady=10)
    entry_pin.focus_set()

    button_frame = tk.Frame(pinwindow)
    button_frame.pack(pady=10)
    style = Style()
    style.configure("TButton", font=("Arial", 12), padding=10)

    if mode == 'python':
        original_aceptar = Image.open("./images/aceptar.png")
        original_cancelar = Image.open("./images/cancelar.png")
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
        original_aceptar = Image.open(os.path.join(exe_dir, "aceptar.png"))
        original_cancelar = Image.open(os.path.join(exe_dir, "cancelar.png"))
    
    resized_aceptar = original_aceptar.resize((25, 25))  # Resize to 50x50 pixels
    iconaceptar = ImageTk.PhotoImage(resized_aceptar)
    resized_cancelar = original_cancelar.resize((25, 25))  # Resize to 50x50 pixels
    iconcancelar = ImageTk.PhotoImage(resized_cancelar)


    # Crear el botón de aceptar
    btn_aceptar = Button(button_frame, text="Aceptar", style="TButton", image=iconaceptar, compound='left', command=aceptar)
    btn_aceptar.pack(side=tk.LEFT, padx=5)

    # Crear el botón de cancelar
    btn_cancelar = Button(button_frame, text="Cancelar", style="TButton", image=iconcancelar, compound='left', command=cancelar)
    btn_cancelar.pack(side=tk.LEFT, padx=5)

    button_frame.pack(pady=10, anchor=tk.CENTER)

    pinwindow.bind('<Return>', lambda event: aceptar())
    pinwindow.bind('<Escape>', lambda event: cancelar())

    # Ejecutar el bucle principal de la ventana
    pinwindow.mainloop()

    return getpin, 200

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
        original_image = Image.open(os.path.join(exe_dir, "certificado.png"))
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
    
    except:
        certs.destroy()

def show_alert(message, callback=None):
    puerto_uso = tk.Tk()
    puerto_uso.withdraw()
    messagebox.showwarning("Alerta", message)
    puerto_uso.destroy()
    if callback:
        callback()