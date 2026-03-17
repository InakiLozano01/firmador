import base64
import io
import json
import logging
import os
from datetime import datetime

import PyPDF2
import psycopg2

from app.exceptions.tool_exc import (
    DatabaseConnectionError,
    DatabaseTransactionError,
    DocumentProcessingError,
    PDFClosingError,
)
from app.services.dss.close_pdf import close_pdf

logger = logging.getLogger(__name__)

SPANISH_MONTHS = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def open_db_connection():
    dbname = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT")

    conn_params = {
        "dbname": dbname,
        "user": user,
        "password": password,
        "host": host,
        "port": port,
    }

    logger.debug("Attempting database connection to %s:%s/%s", host, port, dbname)
    try:
        conn = psycopg2.connect(**conn_params)
    except Exception as exc:
        logger.error("Failed to connect to database: %s", str(exc), exc_info=True)
        raise DatabaseConnectionError(f"Error connecting to database: {str(exc)}") from exc

    if not conn or conn.closed != 0:
        logger.error("Database connection is not valid")
        raise DatabaseConnectionError("Failed to establish database connection")

    logger.debug("Database connection established")
    return conn


def _resolve_pdf_page_count(pdf_to_close, page_count=None):
    if page_count is not None:
        return int(page_count)

    pdf_bytes = base64.b64decode(pdf_to_close)
    pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
    return len(pdf_reader.pages)


def _normalize_protocolization_payload(payload):
    if isinstance(payload, str):
        return json.loads(payload)
    return json.loads(json.dumps(payload))


def _format_close_date(raw_date: str):
    date_value = datetime.strptime(raw_date, "%Y-%m-%d")
    year = date_value.strftime("%Y")
    formatted_date = f"{date_value.strftime('%d')} de {SPANISH_MONTHS[date_value.month]} de {year}"
    return year, formatted_date


def _build_close_field_values(payload, page_count: int):
    year, formatted_date = _format_close_date(payload["fecha"])
    close_number = f"{payload['numero']} / {year}"
    close_date = formatted_date if payload.get("solo_fecha") == 1 else f"San Miguel de Tucumán, {formatted_date}"

    field_values = {f"numero{i + 1}": close_number for i in range(page_count)}
    field_values["fecha"] = close_date
    return field_values


def _rollback_connection(conn):
    if conn and conn.closed == 0:
        conn.rollback()


def _close_owned_connection(conn, owns_connection: bool):
    if owns_connection and conn and conn.closed == 0:
        logger.debug("Closing database connection")
        conn.close()


def _protocolize_and_close_pdf(protocolize_function, pdf_to_close, id_doc, page_count=None, conn=None, commit=True):
    logger.info("Starting get number and date process for document %s", id_doc)
    active_conn = conn or open_db_connection()
    owns_connection = conn is None
    cursor = None

    try:
        cursor = active_conn.cursor()
        logger.debug("Executing document protocolization for document %s", id_doc)
        cursor.execute(f"SELECT {protocolize_function}(%s)", (id_doc,))
        datos = cursor.fetchone()
        if not datos:
            raise DatabaseTransactionError("Transaction error: empty protocolization response")

        datos_json = _normalize_protocolization_payload(datos[0])
        logger.debug("Protocolization result: %s", datos_json)

        if not datos_json.get("status"):
            logger.error("Document processing error: %s", datos_json.get("message"))
            raise DocumentProcessingError(f"Error getting date and number: {datos_json.get('message')}")

        pdf_number_of_pages = _resolve_pdf_page_count(pdf_to_close, page_count=page_count)
        logger.debug("PDF number of pages: %s", pdf_number_of_pages)
        final_json_field_values = _build_close_field_values(datos_json, pdf_number_of_pages)

        try:
            logger.debug("Attempting to close PDF")
            pdf = close_pdf(pdf_to_close, json.dumps(final_json_field_values))
            logger.debug("PDF closed successfully")
        except Exception as exc:
            logger.error("Failed to close PDF: %s", str(exc), exc_info=True)
            raise PDFClosingError(f"Error closing PDF: {str(exc)}") from exc

        if commit:
            active_conn.commit()
        return pdf
    except (DocumentProcessingError, PDFClosingError, DatabaseTransactionError):
        _rollback_connection(active_conn)
        raise
    except Exception as exc:
        logger.error("Database transaction error: %s", str(exc), exc_info=True)
        _rollback_connection(active_conn)
        raise DatabaseTransactionError(f"Transaction error: {str(exc)}") from exc
    finally:
        if cursor:
            cursor.close()
        _close_owned_connection(active_conn, owns_connection)


def get_number_and_date_then_close(pdf_to_close, id_doc, page_count=None, conn=None, commit=True):
    return _protocolize_and_close_pdf(
        "f_documento_protocolizar",
        pdf_to_close,
        id_doc,
        page_count=page_count,
        conn=conn,
        commit=commit,
    )


def _unlock_pdf_and_close_task(finalize_function, params: dict, conn=None, commit=True):
    logger.info("Starting unlock and close task for document %s", params.get("id_doc"))
    required_params = {"id_doc", "id_user", "hash_doc", "is_closed", "id_sello", "id_oficina", "tipo_firma"}
    missing_params = required_params - set(params.keys())
    if missing_params:
        logger.error("Missing required parameters: %s", missing_params)
        raise ValueError(f"Missing required parameters: {', '.join(missing_params)}")

    active_conn = conn or open_db_connection()
    owns_connection = conn is None
    cursor = None

    try:
        cursor = active_conn.cursor()
        logger.debug("Executing finalization process")
        cursor.execute(
            f"SELECT {finalize_function} (%s, %s, %s, %s, %s, %s, %s, %s)",
            (
                params["id_doc"],
                params["id_user"],
                params.get("is_signed", 1),
                params["is_closed"],
                params["id_sello"],
                params["id_oficina"],
                params["tipo_firma"],
                params["hash_doc"],
            ),
        )
        if commit:
            active_conn.commit()
        logger.debug("Finalization process completed successfully")
    except Exception as exc:
        logger.error("Error in finalization process: %s", str(exc), exc_info=True)
        _rollback_connection(active_conn)
        raise DatabaseTransactionError(f"Error in finalization process: {str(exc)}") from exc
    finally:
        if cursor:
            cursor.close()
        _close_owned_connection(active_conn, owns_connection)
        logger.info("Unlock and close task completed")


def unlock_pdf_and_close_task(params: dict, conn=None, commit=True):
    _unlock_pdf_and_close_task(
        "f_finalizar_proceso_firmado_v2",
        params,
        conn=conn,
        commit=commit,
    )


def unlock_pdf_and_close_task_project(params: dict, conn=None, commit=True):
    _unlock_pdf_and_close_task(
        "f_proyecto_finalizar_proceso_firmado_v2",
        params,
        conn=conn,
        commit=commit,
    )


def get_number_and_date_then_close_project(pdf_to_close, id_doc, page_count=None, conn=None, commit=True):
    return _protocolize_and_close_pdf(
        "f_proyecto_protocolizar",
        pdf_to_close,
        id_doc,
        page_count=page_count,
        conn=conn,
        commit=commit,
    )
