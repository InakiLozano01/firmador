##################################################
###              Imports externos              ###
##################################################

import json
from os import path
from flask import jsonify
from smartcard.System import readers
from smartcard.Exceptions import NoCardException

# Ruta al archivo JSON que guarda el mapeo de drivers de tokens
TOKEN_LIB_FILE = "token_lib.json"

def load_token_library_mapping():
    try:
        if path.exists(TOKEN_LIB_FILE):
            with open(TOKEN_LIB_FILE, 'r') as file:
                return json.load(file), 200
        return {}, 200
    except (json.JSONDecodeError, ValueError):
        return jsonify({"status": False, "message": "Error al cargar el mapeo de drivers de tokens."}), 500

def save_token_library_mapping(mapping):
    try:
        with open(TOKEN_LIB_FILE, 'w') as file:
            json.dump(mapping, file)
        return jsonify({"status": True, "message": "Mapeo de drivers de tokens guardado correctamente."}), 200
    except Exception as e:
        return jsonify({"status": False, "message": f"Error al guardar el mapeo de drivers de tokens: {str(e)}"}), 500
    
def list_smartcard_readers():
    try:
        r = readers()
        return r
    except Exception as e:
        return jsonify({"status": False, "message": f"Error al listar los lectores de tarjetas: {str(e)}"}), 500 
    
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
            return jsonify({"status": False, "message": "No se encontró una tarjeta en el lector."}), 404
        except Exception as e:
            return jsonify({"status": False, "message": f"Error al obtener la información de la tarjeta: {str(e)}"}), 500
    return token_info, 200

def get_token_unique_id(token_info):
    try:
        print(token_info)
        return ''.join(format(x, '02x') for x in token_info["ATR"]), token_info['reader'], 200
    except Exception as e:
        print("error")
        return jsonify({"status": False, "message": f"Error al obtener el ID único del token: {str(e)}"}), 500