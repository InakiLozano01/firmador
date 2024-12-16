# Archivo para guardar los archivos firmados

import json
import base64
import os
import logging
from ..exceptions.tool_exc import JSONSaveError, PDFSaveError

# Configure logging
logger = logging.getLogger(__name__)

def save_signed_json(index, filepath):
    """
    Guarda el índice firmado en formato JSON.

    Args:
        index: Datos del índice a guardar.
        filepath (str): Ruta del archivo donde guardar el JSON.

    Raises:
        JSONSaveError: Si ocurre un error al guardar el archivo JSON.
    """
    logger.info(f"Starting to save signed JSON to {filepath}")
    try:
        dirpath = os.path.dirname(filepath)
        if not os.path.exists(dirpath):
            logger.debug(f"Creating directory: {dirpath}")
            os.makedirs(dirpath)
            
        logger.debug("Writing JSON data to file")
        with open(filepath, 'w') as file:
            json.dump(index, file, separators=(',', ':'), ensure_ascii=False)
        logger.info("Successfully saved signed JSON")
        return True
    except Exception as e:
        logger.error(f"Failed to save signed JSON: {str(e)}", exc_info=True)
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
    logger.info(f"Starting to save signed PDF to {filename}")
    try:
        logger.debug("Decoding base64 PDF data")
        signed_pdf_bytes = base64.b64decode(signed_pdf_base64)
        
        dirpath = os.path.dirname(filename)
        if not os.path.exists(dirpath):
            logger.debug(f"Creating directory: {dirpath}")
            os.makedirs(dirpath)
            
        logger.debug("Writing PDF data to file")
        with open(filename, 'wb') as f:
            f.write(signed_pdf_bytes)
        logger.info("Successfully saved signed PDF")
        return True
    except base64.binascii.Error as e:
        logger.error(f"Failed to decode base64 PDF data: {str(e)}", exc_info=True)
        raise PDFSaveError(f"Error al decodificar el PDF en base64: {str(e)}")
    except OSError as e:
        logger.error(f"Failed to create directory or write file: {str(e)}", exc_info=True)
        raise PDFSaveError(f"Error al crear directorio o escribir archivo: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to save signed PDF: {str(e)}", exc_info=True)
        raise PDFSaveError(f"Error al guardar el PDF firmado: {str(e)}")