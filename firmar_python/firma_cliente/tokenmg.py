##################################################
###              Imports externos              ###
##################################################

import os
from tkinter import filedialog
import json
import tkinter as tk
from tkinter import simpledialog
from flask import jsonify

# Path to the JSON file that stores token-library correspondences
TOKEN_LIB_FILE = "token_lib.json"

def load_token_library_mapping():
    try:
        if os.path.exists(TOKEN_LIB_FILE):
            with open(TOKEN_LIB_FILE, 'r') as file:
                return json.load(file)
        return {}, 200
    except (json.JSONDecodeError, ValueError):
        return jsonify({"status": "error", "message": "Error al cargar el mapeo de bibliotecas de tokens."}), 500

def save_token_library_mapping(mapping):
    try:
        with open(TOKEN_LIB_FILE, 'w') as file:
            json.dump(mapping, file)
        return jsonify({"status": "success", "message": "Mapeo de bibliotecas de tokens guardado correctamente."}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al guardar el mapeo de bibliotecas de tokens: {str(e)}"}), 500

def get_token_unique_id(token_info):
    try:
        return ''.join(format(x, '02x') for x in token_info["ATR"]), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al obtener el ID único del token: {str(e)}"}), 500

def select_library_file():
    try:
        return filedialog.askopenfilename(initialdir="C:\\Windows\\System32\\", title="Seleccione la biblioteca DLL", filetypes=[("DLL files", "*.dll")]), 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al seleccionar la biblioteca DLL: {str(e)}"}), 500
    
def get_pin_from_user():
    try:
        root = tk.Tk()
        root.withdraw()
        pin = simpledialog.askstring("PIN del Token", "Ingrese el PIN para el token:", show='*')
        root.destroy()
        return pin, 200
    except Exception as e:
        return jsonify({"status": "error", "message": f"Error al obtener el PIN del usuario: {str(e)}"}), 500