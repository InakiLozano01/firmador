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


def _get_bool_env(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().strip("'").strip('"').lower()
    return normalized in {"1", "true", "yes", "y", "on"}

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
    REDIS_FINALIZED_TTL_SECONDS = _get_int_env('REDIS_FINALIZED_TTL_SECONDS', 300)

    # Signing concurrency and repair settings
    SIGNING_FINALIZE_LEASE_MS = _get_int_env('SIGNING_FINALIZE_LEASE_MS', 120000)
    SIGNING_ENTITY_LOCK_TTL_MS = _get_int_env('SIGNING_ENTITY_LOCK_TTL_MS', 120000)
    SIGNING_REPAIR_DIR = os.getenv('SIGNING_REPAIR_DIR', os.path.join(APP_ROOT, 'repair_queue'))

    # DSS performance settings
    DSS_POOL_MAXSIZE = _get_int_env('DSS_POOL_MAXSIZE', 20)
    DSS_MAX_INFLIGHT_VALIDATE = _get_int_env('DSS_MAX_INFLIGHT_VALIDATE', 4)
    VALIDATION_MAX_WORKERS = _get_int_env('VALIDATION_MAX_WORKERS', 8)

    # Expediente validation hardening
    MAX_EXPEDIENTE_ARCHIVE_FILES = _get_int_env('MAX_EXPEDIENTE_ARCHIVE_FILES', 1000)
    MAX_EXPEDIENTE_ARCHIVE_BYTES = _get_int_env('MAX_EXPEDIENTE_ARCHIVE_BYTES', 250 * 1024 * 1024)

    # Observability settings
    OBS_LOG_LEVEL = os.getenv('OBS_LOG_LEVEL', 'INFO').upper()
    OBS_CAPTURE_HTTP_BODIES = _get_bool_env('OBS_CAPTURE_HTTP_BODIES', False)
    OBS_CAPTURE_SIGNING_HTTP_BODIES = _get_bool_env('OBS_CAPTURE_SIGNING_HTTP_BODIES', False)
    OBS_PERSIST_DEBUG_LOGS = _get_bool_env('OBS_PERSIST_DEBUG_LOGS', False)
    OBS_ASYNC_QUEUE_SIZE = _get_int_env('OBS_ASYNC_QUEUE_SIZE', 10000)
    OBS_ASYNC_BATCH_SIZE = _get_int_env('OBS_ASYNC_BATCH_SIZE', 50)
    OBS_ASYNC_FLUSH_MS = _get_int_env('OBS_ASYNC_FLUSH_MS', 250)
    OBS_PAYLOAD_VAULT_KEY = os.getenv('OBS_PAYLOAD_VAULT_KEY')
    OBS_PAYLOAD_VAULT_MAX_BYTES = _get_int_env('OBS_PAYLOAD_VAULT_MAX_BYTES', 5 * 1024 * 1024)
    OBS_PAYLOAD_VAULT_RETENTION_DAYS = _get_int_env('OBS_PAYLOAD_VAULT_RETENTION_DAYS', 30)
    OBS_RUNTIME_HEARTBEAT_SECONDS = _get_int_env('OBS_RUNTIME_HEARTBEAT_SECONDS', 10)
    OBS_PAYLOAD_REVEAL_ROLE = os.getenv('OBS_PAYLOAD_REVEAL_ROLE', 'admin')

settings = Settings() 
