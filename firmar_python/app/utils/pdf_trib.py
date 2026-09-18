import base64
import io
import re
from dataclasses import dataclass
from typing import List

from PyPDF2 import PdfReader

TRIB_PATTERN = re.compile(r"@TRIB(?![A-Za-z])", re.IGNORECASE)
SELLO_WIDTH = 320
SELLO_HEIGHT = 80


@dataclass(frozen=True)
class MarcadorTrib:
    page: int
    origin_x: float
    origin_y: float
    width: float = SELLO_WIDTH
    height: float = SELLO_HEIGHT


def _prefix_width(prefix: str, font_size: float) -> float:
    if not prefix:
        return 0.0
    try:
        from reportlab.pdfbase.pdfmetrics import stringWidth

        return float(stringWidth(prefix, "Helvetica", font_size))
    except Exception:
        return float(len(prefix) * font_size * 0.5)


def _markers_in_text(text, tm, font_size, page: int) -> List[MarcadorTrib]:
    if not text or tm is None:
        return []
    size = float(font_size or 12)
    markers = []
    for match in TRIB_PATTERN.finditer(text):
        origin_x = float(tm[4]) + _prefix_width(text[: match.start()], size)
        top = float(tm[5]) + size
        markers.append(
            MarcadorTrib(
                page=page,
                origin_x=origin_x,
                origin_y=top - SELLO_HEIGHT,
            )
        )
    return markers


def _markers_in_annotations(page_obj, page_number: int) -> List[MarcadorTrib]:
    markers = []
    annots = page_obj.get("/Annots") or []
    for annot_ref in annots:
        try:
            annot = annot_ref.get_object() if hasattr(annot_ref, "get_object") else annot_ref
        except Exception:
            continue
        contents = str(annot.get("/Contents") or "")
        if not TRIB_PATTERN.search(contents):
            continue
        rect = annot.get("/Rect")
        if not rect:
            continue
        try:
            llx, _lly, _urx, ury = [float(value) for value in rect]
        except (TypeError, ValueError):
            continue
        markers.append(
            MarcadorTrib(
                page=page_number,
                origin_x=llx,
                origin_y=ury - SELLO_HEIGHT,
            )
        )
    return markers


def _merge_page_encodings(texts: List[MarcadorTrib], annots: List[MarcadorTrib]) -> List[MarcadorTrib]:
    if len(texts) == 1 and len(annots) == 1:
        return annots
    return annots + texts


def _dedupe(markers: List[MarcadorTrib]) -> List[MarcadorTrib]:
    seen = set()
    unique = []
    for marker in markers:
        key = (marker.page, round(marker.origin_x), round(marker.origin_y))
        if key in seen:
            continue
        seen.add(key)
        unique.append(marker)
    return unique


def find_marcadores_trib(pdf_b64: str) -> List[MarcadorTrib]:
    reader = PdfReader(io.BytesIO(base64.b64decode(pdf_b64)))
    markers: List[MarcadorTrib] = []
    for index, page in enumerate(reader.pages):
        page_number = index + 1
        found_text: List[MarcadorTrib] = []

        def visitor(text, cm, tm, fontDict, fontSize, _page=page_number, _bucket=found_text):
            _bucket.extend(_markers_in_text(text, tm, fontSize, _page))

        try:
            page.extract_text(visitor_text=visitor)
        except Exception:
            pass
        found_annots = _markers_in_annotations(page, page_number)
        markers.extend(_merge_page_encodings(found_text, found_annots))
    return _dedupe(markers)
