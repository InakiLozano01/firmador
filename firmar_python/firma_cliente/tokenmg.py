##################################################
###              Imports externos              ###
##################################################

import json
import sys
from os import path
from smartcard.System import readers
from smartcard.Exceptions import NoCardException

# Ruta al archivo JSON que guarda el mapeo de drivers de tokens
if getattr(sys, 'frozen', False):
    # Path to the directory containing the executable
    # when running as a bundled app (e.g., PyInstaller)
    BASE_DIR = path.dirname(sys.executable)
else:
    # Path to the directory containing this script
    # when running as a normal .py script
    BASE_DIR = path.dirname(path.abspath(__file__))

TOKEN_LIB_FILE = path.join(BASE_DIR, "token_lib.json")

##################################################
###        Custom Token Exceptions             ###
##################################################

class TokenManagementError(Exception):
    """Base class for token management related errors."""
    def __init__(self, message, status_code=500, original_exception=None):
        full_message = message
        if original_exception:
            full_message += f" Detalles: {str(original_exception)}"
        super().__init__(full_message)
        self.message = full_message # Store the potentially modified message
        self.status_code = status_code

class TokenMappingError(TokenManagementError):
    """Error related to loading or saving token library mapping."""
    pass

class SmartcardReaderError(TokenManagementError):
    """Error related to smartcard reader operations."""
    pass

class NoSmartcardFoundError(SmartcardReaderError):
    """Specific error for when no smartcard is found in the reader."""
    def __init__(self, message="No se encontró una tarjeta en el lector.", status_code=404, original_exception=None):
        super().__init__(message, status_code, original_exception)

class TokenATRReadError(SmartcardReaderError):
    """Error when reading ATR or other info from a smartcard."""
    pass

class TokenIdError(TokenManagementError):
    """Error when generating a unique ID from token info."""
    pass 

##################################################
###       Token Management Functions           ###
##################################################

def load_token_library_mapping() -> dict:
    """Loads the token library mapping from JSON file. Raises TokenMappingError on failure."""
    try:
        if path.exists(TOKEN_LIB_FILE):
            with open(TOKEN_LIB_FILE, 'r') as file:
                return json.load(file)
        return {} # Return empty dict if file doesn't exist (considered success)
    except (json.JSONDecodeError, ValueError, IOError) as e:
        raise TokenMappingError("Error al cargar el mapeo de drivers de tokens.", original_exception=e) from e

def save_token_library_mapping(mapping: dict):
    """Saves the token library mapping to a JSON file. Raises TokenMappingError on failure."""
    try:
        with open(TOKEN_LIB_FILE, 'w') as file:
            json.dump(mapping, file)
        # No explicit return needed for success, or could return True
    except (IOError, TypeError) as e: # TypeError if mapping is not serializable
        raise TokenMappingError("Error al guardar el mapeo de drivers de tokens.", original_exception=e) from e
    
def list_smartcard_readers_internal() -> list:
    """Lists available smartcard readers. Raises SmartcardReaderError on failure."""
    # Renamed to avoid direct use from routes without error handling in main.py
    try:
        return readers()
    except Exception as e: # smartcard.System.readers() can throw various exceptions
        raise SmartcardReaderError("Error al listar los lectores de tarjetas.", original_exception=e) from e
    
def list_tokens_internal() -> list:
    """Lists connected tokens with their ATRs. Raises SmartcardReaderError or NoSmartcardFoundError."""
    # Renamed to avoid direct use from routes without error handling in main.py
    token_info_list = []
    # This function now calls the refactored list_smartcard_readers_internal
    # which will raise SmartcardReaderError if it fails. That error will propagate
    # unless caught here. For now, let it propagate to be handled by the route.
    reader_list = list_smartcard_readers_internal() 
    
    if not reader_list: # Handle case where no readers are returned
        # This might not be an error per se, but an empty list of tokens.
        # Depending on desired behavior, could raise an error or return empty.
        # For now, consistent with original, it would lead to empty token_info_list.
        pass

    for reader in reader_list:
        try:
            connection = reader.createConnection()
            connection.connect()
            atr = connection.getATR() # atr is a list of integers
            token_info_list.append({"reader": reader.name, "ATR": atr})
            # Ensure connection is closed if not used further here.
            # The smartcard library examples often show explicit disconnect.
            connection.disconnect()
        except NoCardException as e:
            # This is a specific, often expected, scenario for a single reader
            # If multiple readers, one empty shouldn't stop others usually.
            # For now, if ANY reader has NoCardException, we raise and stop as per original logic.
            # To list all available cards and skip empty readers, the loop structure would change.
            raise NoSmartcardFoundError(original_exception=e) from e
        except Exception as e: # Other errors during connection or ATR fetching for a specific reader
            # Similar to NoCardException, this stops the process for all readers.
            raise TokenATRReadError(f"Error al obtener la información de la tarjeta del lector {reader.name}.", original_exception=e) from e
    return token_info_list

def get_token_unique_id_internal(token_info: dict) -> tuple[str, str]:
    """Gets a unique ID (hex ATR) and reader name from token_info. Raises TokenIdError on failure."""
    # Renamed to avoid direct use from routes without error handling in main.py
    try:
        # token_info is expected like {"ATR": [ints], "reader": "name"}
        atr_bytes = token_info["ATR"] # This is a list of integers from getATR()
        reader_name = token_info['reader']
        hex_atr = ''.join(format(x, '02x') for x in atr_bytes)
        return hex_atr, reader_name
    except KeyError as e:
        raise TokenIdError("Formato de token_info incorrecto, falta la clave 'ATR' o 'reader'.", original_exception=e) from e
    except Exception as e: # Catch any other unexpected error
        raise TokenIdError("Error al obtener el ID único del token.", original_exception=e) from e