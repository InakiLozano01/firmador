import os
from dotenv import load_dotenv

# Get the absolute path to the config directory
CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(CONFIG_DIR)

# Load environment variables from .env file
load_dotenv(os.path.join(CONFIG_DIR, '.env'))


def _get_int_env(name, default):
    value = os.getenv(name, default)
    if isinstance(value, str):
        value = value.strip().strip("'").strip('"')
    try:
        return int(value)
    except (TypeError, ValueError):
        return default

class Settings:
    # Database settings
    DB_NAME = os.getenv('DB_NAME')
    DB_USER = os.getenv('DB_USER')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_HOST = os.getenv('DB_HOST')
    DB_PORT = os.getenv('DB_PORT')

    # Certificate settings
    PRIVATE_KEY_PASSWORD = os.getenv('PRIVATE_KEY_PASSWORD')
    
    # Resolve absolute paths for certificates
    # PRIVATE_KEY_PATH = os.path.abspath(os.path.join(APP_ROOT, 'certs/own/TC_clave_csr.key'))
    # CERTIFICATE_PATH = os.path.abspath(os.path.join(APP_ROOT, 'certs/own/GDEcert.cer'))

    # Assets paths
    LOGO_PATH = os.path.join(APP_ROOT, 'assets', 'images', 'logo_tribunal_para_tapir_250px.png')
    LOGO_YUNGA_PATH = os.path.join(APP_ROOT, 'assets', 'images', os.getenv('LOGO_YUNGA_FILE'))

    # Redis settings
    REDIS_HOST = os.getenv('REDIS_HOST', 'redis')
    REDIS_PORT = _get_int_env('REDIS_PORT', 6379)
    REDIS_DB = _get_int_env('REDIS_DB', 0)
    REDIS_TTL_SECONDS = _get_int_env('REDIS_TTL_SECONDS', 21600)
    REDIS_KEY_PREFIX = os.getenv('REDIS_KEY_PREFIX', 'signctx')
    REDIS_CONNECT_TIMEOUT_SECONDS = _get_int_env('REDIS_CONNECT_TIMEOUT_SECONDS', 2)
    REDIS_SOCKET_TIMEOUT_SECONDS = _get_int_env('REDIS_SOCKET_TIMEOUT_SECONDS', 5)

settings = Settings() 
