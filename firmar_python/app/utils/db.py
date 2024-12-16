# Archivo para la conexión a la base de datos y funciones de la base de datos

import os
import json
import psycopg2
from datetime import datetime
from app.services.dss.close_pdf import close_pdf
from app.exceptions.tool_exc import DatabaseConnectionError, DatabaseTransactionError, DocumentProcessingError, PDFClosingError

###################################################
###      Función para obtener el número de      ###
###         cierre y la fecha de cierre         ###
###################################################
def get_number_and_date_then_close(pdf_to_close, id_doc):
    """
    Get the closing number and date, then close the PDF.

    Args:
        pdf_to_close (str): Base64 encoded PDF to close.
        id_doc (int): Document ID.

    Returns:
        str: Base64 encoded closed PDF.

    Raises:
        DatabaseConnectionError: If connection to database fails
        DatabaseTransactionError: If there's an error during database transaction
        DocumentProcessingError: If there's an error processing the document
        PDFClosingError: If there's an error closing the PDF
    """
    global conn
    dbname = os.getenv('DB_NAME')
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT')

    conn_params = {
        'dbname': dbname,
        'user': user,
        'password': password,
        'host': host,
        'port': port
    }

    try:
        conn = psycopg2.connect(**conn_params)
    except Exception as e:
        raise DatabaseConnectionError(f"Error connecting to database: {str(e)}")

    if not conn or conn.closed != 0:
        raise DatabaseConnectionError("Failed to establish database connection")

    cursor = conn.cursor()
    try:
        cursor.execute("SELECT f_documento_protocolizar(%s)", (id_doc,))
        datos = cursor.fetchone()
        datos_json = json.loads(json.dumps(datos[0]))
        
        if not datos_json['status']:
            raise DocumentProcessingError(f"Error getting date and number: {datos_json['message']}")

        json_field_values1 = {
            "numero": datos_json['numero'],
            "fecha": datetime.strptime(datos_json['fecha'], '%Y-%m-%d').strftime('%d/%m/%Y')
        }
        json_field_values = json.dumps(json_field_values1)

        try:
            pdf, code = close_pdf(pdf_to_close, json_field_values)
            if code == 500:
                response = pdf.get_json()
                if response['status'] == "error":
                    conn.rollback()
                    raise PDFClosingError(f"Error closing PDF: {response['message']}")
            return pdf
        except Exception as e:
            conn.rollback()
            raise PDFClosingError(f"Error closing PDF: {str(e)}")

    except DocumentProcessingError:
        conn.rollback()
        raise
    except Exception as e:
        conn.rollback()
        raise DatabaseTransactionError(f"Transaction error: {str(e)}")
    finally:
        cursor.close()
        if conn and not conn.closed:
            conn.close()

###################################################
###    Funcion para desbloquear el documento    ###
###       cerrar la tarea y guardar hash        ###
###################################################
def unlock_pdf_and_close_task(params: dict):
    """
    Unlock the PDF, close the task, and save the hash.

    Args:
        params (dict): Dictionary containing:
            - id_doc (int): Document ID
            - id_user (int): User ID
            - hash_doc (str): Document hash
            - is_closed (bool): Flag indicating if the document is closed
            - id_sello (int): Seal ID
            - id_oficina (int): Office ID
            - tipo_firma (int): Type of signature
            - is_signed (int, optional): Flag indicating if the document is signed. Defaults to 1

    Raises:
        DatabaseConnectionError: If connection to database fails
        DatabaseTransactionError: If there's an error during the finalization process
        ValueError: If required parameters are missing
    """
    required_params = {'id_doc', 'id_user', 'hash_doc', 'is_closed', 'id_sello', 'id_oficina', 'tipo_firma'}
    missing_params = required_params - set(params.keys())
    if missing_params:
        raise ValueError(f"Missing required parameters: {', '.join(missing_params)}")

    # Set default value for is_signed if not provided
    params.setdefault('is_signed', 1)

    global conn
    dbname = os.getenv('DB_NAME')
    user = os.getenv('DB_USER')
    password = os.getenv('DB_PASSWORD')
    host = os.getenv('DB_HOST')
    port = os.getenv('DB_PORT')
    conn_params = {
        'dbname': dbname,
        'user': user,
        'password': password,
        'host': host,
        'port': port
    }

    try:
        if not (conn and conn.closed == 0):
            conn = psycopg2.connect(**conn_params)
        cursor = conn.cursor()
    except (psycopg2.InterfaceError, Exception) as e:
        try:
            conn = psycopg2.connect(**conn_params)
            cursor = conn.cursor()
        except Exception as exc:
            raise DatabaseConnectionError(f"Error connecting to database: {str(exc)}")

    try:
        cursor.execute(
            "SELECT f_finalizar_proceso_firmado_v2 (%s, %s, %s, %s, %s, %s, %s, %s)", 
            (
                params['id_doc'],
                params['id_user'],
                params['is_signed'],
                params['is_closed'],
                params['id_sello'],
                params['id_oficina'],
                params['tipo_firma'],
                params['hash_doc']
            )
        )
    except Exception as e:
        conn.rollback()
        raise DatabaseTransactionError(f"Error in finalization process: {str(e)}")
    finally:
        cursor.close()
        if conn and not conn.closed:
            conn.close()