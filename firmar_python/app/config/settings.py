import logging
import os
from dotenv import load_dotenv

_logger_settings = logging.getLogger(__name__)

# Get the absolute path to the config directory
CONFIG_DIR = os.path.dirname(os.path.abspath(__file__))
APP_ROOT = os.path.dirname(CONFIG_DIR)

# Load environment variables from .env file
load_dotenv(os.path.join(CONFIG_DIR, '.env'))


def _get_str_env(name, default=None):
    value = os.getenv(name, default)
    if value is None:
        return default
    normalized = str(value).strip().strip("'").strip('"')
    return normalized or default


def _get_int_env(name, default):
    value = _get_str_env(name, default)
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
    normalized = _get_str_env(name, "").lower()
    return normalized in {"1", "true", "yes", "y", "on"}


def _resolve_logo_path():
    raw_value = _get_str_env('LOGO_YUNGA_FILE', 'logo_yunga.png')
    if os.path.isabs(raw_value):
        return raw_value
    if os.path.dirname(raw_value):
        return os.path.abspath(os.path.join(APP_ROOT, raw_value))
    return os.path.join(APP_ROOT, 'assets', 'images', raw_value)


class Settings:
    # Database settings
    DB_NAME = _get_str_env('DB_NAME')
    DB_USER = _get_str_env('DB_USER')
    DB_PASSWORD = _get_str_env('DB_PASSWORD')
    DB_HOST = _get_str_env('DB_HOST')
    DB_PORT = _get_str_env('DB_PORT')

    # Certificate settings
    PRIVATE_KEY_PASSWORD = _get_str_env('PRIVATE_KEY_PASSWORD')
    PRIVATE_KEY_PATH = _get_str_env('PRIVATE_KEY_PATH')
    CERTIFICATE_PATH = _get_str_env('CERTIFICATE_PATH')
    ISSUER_POOL_DIR = _get_str_env(
        'ISSUER_POOL_DIR',
        os.path.join(APP_ROOT, 'certs', 'issuer_pool'),
    )

    # Assets paths
    LOGO_PATH = os.path.join(APP_ROOT, 'assets', 'images', 'logo_tribunal_para_tapir_250px.png')
    LOGO_YUNGA_PATH = _resolve_logo_path()

    # Redis settings
    REDIS_HOST = _get_str_env('REDIS_HOST', 'redis')
    REDIS_PORT = _get_int_env('REDIS_PORT', 6379)
    REDIS_DB = _get_int_env('REDIS_DB', 0)
    REDIS_TTL_SECONDS = _get_int_env('REDIS_TTL_SECONDS', 21600)
    REDIS_KEY_PREFIX = _get_str_env('REDIS_KEY_PREFIX', 'signctx')
    REDIS_CONNECT_TIMEOUT_SECONDS = _get_int_env('REDIS_CONNECT_TIMEOUT_SECONDS', 2)
    REDIS_SOCKET_TIMEOUT_SECONDS = _get_int_env('REDIS_SOCKET_TIMEOUT_SECONDS', 5)
    REDIS_FINALIZED_TTL_SECONDS = _get_int_env('REDIS_FINALIZED_TTL_SECONDS', 300)

    # Signing concurrency and repair settings
    SIGNING_FINALIZE_LEASE_MS = _get_int_env('SIGNING_FINALIZE_LEASE_MS', 120000)
    SIGNING_ENTITY_LOCK_TTL_MS = _get_int_env('SIGNING_ENTITY_LOCK_TTL_MS', 120000)
    SIGNING_REPAIR_DIR = _get_str_env('SIGNING_REPAIR_DIR', os.path.join(APP_ROOT, 'repair_queue'))

    # DSS performance settings
    DSS_POOL_MAXSIZE = _get_int_env('DSS_POOL_MAXSIZE', 20)
    DSS_MAX_INFLIGHT_VALIDATE = _get_int_env('DSS_MAX_INFLIGHT_VALIDATE', 4)
    VALIDATION_MAX_WORKERS = _get_int_env('VALIDATION_MAX_WORKERS', 8)

    # Expediente validation hardening
    MAX_EXPEDIENTE_ARCHIVE_FILES = _get_int_env('MAX_EXPEDIENTE_ARCHIVE_FILES', 1000)
    MAX_EXPEDIENTE_ARCHIVE_BYTES = _get_int_env('MAX_EXPEDIENTE_ARCHIVE_BYTES', 250 * 1024 * 1024)

    # Observability settings
    OBS_LOG_LEVEL = _get_str_env('OBS_LOG_LEVEL', 'INFO').upper()
    OBS_CAPTURE_HTTP_BODIES = _get_bool_env('OBS_CAPTURE_HTTP_BODIES', False)
    OBS_CAPTURE_SIGNING_HTTP_BODIES = _get_bool_env('OBS_CAPTURE_SIGNING_HTTP_BODIES', False)
    OBS_PERSIST_DEBUG_LOGS = _get_bool_env('OBS_PERSIST_DEBUG_LOGS', False)
    OBS_ASYNC_QUEUE_SIZE = _get_int_env('OBS_ASYNC_QUEUE_SIZE', 10000)
    OBS_ASYNC_BATCH_SIZE = _get_int_env('OBS_ASYNC_BATCH_SIZE', 50)
    OBS_ASYNC_FLUSH_MS = _get_int_env('OBS_ASYNC_FLUSH_MS', 250)
    OBS_PAYLOAD_VAULT_KEY = _get_str_env('OBS_PAYLOAD_VAULT_KEY')
    OBS_PAYLOAD_VAULT_MAX_BYTES = _get_int_env('OBS_PAYLOAD_VAULT_MAX_BYTES', 5 * 1024 * 1024)
    OBS_PAYLOAD_VAULT_RETENTION_DAYS = _get_int_env('OBS_PAYLOAD_VAULT_RETENTION_DAYS', 30)
    OBS_RUNTIME_HEARTBEAT_SECONDS = _get_int_env('OBS_RUNTIME_HEARTBEAT_SECONDS', 10)
    OBS_PAYLOAD_REVEAL_ROLE = _get_str_env('OBS_PAYLOAD_REVEAL_ROLE', 'admin')


settings = Settings()

# Register /rest/issuer-certs/resolve by wrapping register_routes (runs before main imports register_routes).
try:
    from app.route_extensions import ensure_issuer_resolve_registered

    ensure_issuer_resolve_registered()
except Exception as e:
    _logger_settings.warning("No se pudo registrar /rest/issuer-certs/resolve: %s", e)
