from dotenv import load_dotenv
import os
import psycopg2
from flask import Flask, jsonify, request
import json
load_dotenv()

def get_closing_number_and_date():
    dbname = os.getenv('DB_NAME')
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT')

    # Detalles de conexión
    conn_params = {
        'dbname': dbname,
        'user': user,
        'password': password,
        'host': host,
        'port': port  # Puerto por defecto de PostgreSQL
    }
    try:
        # Establecer la conexión
        conn = psycopg2.connect(**conn_params)
        conn.autocommit = False  # Desactivar el autocommit para manejar transacciones manualmente
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT f_documento_protocolizar(33)")

            datos = cursor.fetchone()
            datos_json = json.loads(json.dumps(datos[0]))
            print(datos)
            print(datos_json)
            print(type(datos_json))
            if datos_json['status'] == False:
                print("Le aviso a pedro")
                print(datos_json['message'].capitalize())
            else:
                print("Cierro el documento")
                print("Firmo el documento")
                conn.commit()
        except Exception as e:
            conn.rollback()
            print("Error en la transacción", e)
        finally:
            cursor.close()
    except Exception as e:
        print("Error al conectar a la base de datos:", e)
    finally:
        if conn:
            conn.close()

get_closing_number_and_date()
###################################################