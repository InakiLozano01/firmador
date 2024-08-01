##################################################
###              Imports externos              ###
##################################################

import tkinter as tk
from tkinter import Toplevel, Label, Button, Listbox, Scrollbar
from smartcard.System import readers
from smartcard.Exceptions import NoCardException
from flask import jsonify

def list_smartcard_readers():
    try:
        r = readers()
        return r
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al listar los lectores de tarjetas: {str(e)}"}), 500 

def list_tokens():
    token_info = []
    reader_list = list_smartcard_readers()
    for reader in reader_list:
        try:
            connection = reader.createConnection()
            connection.connect()
            atr = connection.getATR()
            token_info.append({"reader": reader.name, "ATR": atr})
        except NoCardException:
            return jsonify({"status": "error", "message": "No se encontró una tarjeta en el lector."}), 404
        except Exception as e:
            return jsonify({"status": "error", "message": f"Error al obtener la información de la tarjeta: {str(e)}"}), 500
    return token_info, 200

def select_token_slot(token_info, result):
    def on_select(evt):
        w = evt.widget
        index = int(w.curselection()[0])
        slot_info = token_info[index]
        slot_label.config(text=f"Slot Seleccionado {index + 1}\nLector: {slot_info['reader']}\nATR: {' '.join(format(x, '02X') for x in slot_info['ATR'])}")
        selected_slot.set(index)
        result.append(index)
        token_window.destroy()

    root = tk.Tk()
    root.withdraw()  # Hide the root window

    token_window = Toplevel(root)
    token_window.title("Seleccionar un Slot de Token")
    token_window.geometry("500x400")
    token_window.resizable(True, True)  # Allow resizing

    # Ensure the window opens in the foreground and centered
    token_window.attributes('-topmost', True)
    token_window.update_idletasks()
    x = (token_window.winfo_screenwidth() - token_window.winfo_reqwidth()) // 2
    y = (token_window.winfo_screenheight() - token_window.winfo_reqheight()) // 2
    token_window.geometry(f"+{x}+{y}")
    token_window.focus_force()

    # Add instruction label
    instruction_label = Label(token_window, text="Seleccione un Slot de Token:", font=("Arial", 12))
    instruction_label.pack(pady=10)

    scrollbar = Scrollbar(token_window)
    scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    listbox = Listbox(token_window, yscrollcommand=scrollbar.set, width=100, height=15)
    for i, info in enumerate(token_info):
        listbox.insert(tk.END, f"Slot {i + 1}: Lector: {info['reader']}")
    listbox.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    listbox.bind('<<ListboxSelect>>', on_select)
    scrollbar.config(command=listbox.yview)

    slot_label = Label(token_window, text="", justify=tk.LEFT, anchor='w', wraplength=400)
    slot_label.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True, padx=10, pady=10)

    selected_slot = tk.IntVar(value=-1)
    select_button = Button(token_window, text="Seleccionar Slot", command=token_window.destroy)
    select_button.pack(pady=10)
    token_window.wait_window()
    root.destroy()