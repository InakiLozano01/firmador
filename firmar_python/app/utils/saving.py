# Archivo para guardar los archivos firmados

import json
import base64
import os
import logging
from ..exceptions.tool_exc import JSONSaveError, PDFSaveError

def save_signed_json(index, filepath):
    """
    Guarda el índice firmado en formato JSON.

    Args:
        index: Datos del índice a guardar.
        filepath (str): Ruta del archivo donde guardar el JSON.

    Raises:
        JSONSaveError: Si ocurre un error al guardar el archivo JSON.
    """
    try:
        with open(filepath, 'w') as file:
            json.dump(index, file, separators=(',', ':'), ensure_ascii=False)
        return True
    except Exception as e:
        raise JSONSaveError(f"Error al guardar el indice firmado: {str(e)}")
    
def save_signed_pdf(signed_pdf_base64, filename):
    """
    Guarda el PDF firmado en un archivo.

    Args:
        signed_pdf_base64 (str): PDF firmado en Base64.
        filename (str): Nombre del archivo a guardar en PDF.

    Raises:
        PDFSaveError: Si ocurre un error al guardar el archivo PDF.
    """
    try:
        signed_pdf_bytes = base64.b64decode(signed_pdf_base64)
        dirpath = os.path.dirname(filename)
        if not os.path.exists(dirpath):
            os.makedirs(dirpath)
            
        with open(filename, 'wb') as f:
            f.write(signed_pdf_bytes)
        return True
    except Exception as e:
        logging.error("Error in save_signed_pdf: %s", str(e))
        raise PDFSaveError(f"Error al guardar el PDF firmado: {str(e)}")