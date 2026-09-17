import base64
import io
from typing import Set

from PyPDF2 import PdfReader


def list_pdf_field_names(pdf_b64: str) -> Set[str]:
    reader = PdfReader(io.BytesIO(base64.b64decode(pdf_b64)))
    fields = reader.get_fields() or {}
    return set(fields.keys())
