import base64
import io
import re
from dataclasses import dataclass
from typing import List, Tuple

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


@dataclass(frozen=True)
class _TextEncoding:
    page: int
    origin_x: float
    marker_top: float
    glyph_x: float
    glyph_y: float


@dataclass(frozen=True)
class _AnnotEncoding:
    page: int
    origin_x: float
    marker_top: float
    llx: float
    lly: float
    urx: float
    ury: float


def _prefix_width(prefix: str, font_size: float) -> float:
    if not prefix:
        return 0.0
    try:
        from reportlab.pdfbase.pdfmetrics import stringWidth

        return float(stringWidth(prefix, "Helvetica", font_size))
    except Exception:
        return float(len(prefix) * font_size * 0.5)


def _page_box(page) -> Tuple[float, float, float, float]:
    box = page.mediabox
    return float(box.left), float(box.bottom), float(box.right), float(box.top)


def _fit_dss_field(
    origin_x: float,
    origin_y: float,
    width: float,
    height: float,
    page_width: float,
    page_height: float,
) -> Tuple[float, float, float, float]:
    """Keep the TRIB origin and shrink so the DSS field stays on the page."""
    width = min(float(width), page_width)
    height = min(float(height), page_height)
    if origin_x < 0:
        origin_x = 0.0
    if origin_y < 0:
        origin_y = 0.0
    if origin_x >= page_width:
        origin_x = max(0.0, page_width - width)
    if origin_y >= page_height:
        origin_y = max(0.0, page_height - height)
    width = min(width, page_width - origin_x)
    height = min(height, page_height - origin_y)
    return origin_x, origin_y, width, height


def _marcador_on_page(
    *,
    page: int,
    origin_x: float,
    marker_top: float,
    page_left: float,
    page_bottom: float,
    page_right: float,
    page_top: float,
) -> MarcadorTrib:
    page_width = page_right - page_left
    page_height = page_top - page_bottom
    # DSS SignatureFieldParameters: origin is the top-left of the page.
    dss_x = origin_x - page_left
    dss_y = page_top - marker_top
    fitted_x, fitted_y, width, height = _fit_dss_field(
        dss_x, dss_y, SELLO_WIDTH, SELLO_HEIGHT, page_width, page_height
    )
    return MarcadorTrib(
        page=page,
        origin_x=fitted_x,
        origin_y=fitted_y,
        width=width,
        height=height,
    )


def _markers_in_text(text, tm, font_size, page: int) -> List[_TextEncoding]:
    if not text or tm is None:
        return []
    size = float(font_size or 12)
    markers = []
    for match in TRIB_PATTERN.finditer(text):
        glyph_x = float(tm[4]) + _prefix_width(text[: match.start()], size)
        glyph_y = float(tm[5])
        markers.append(
            _TextEncoding(
                page=page,
                origin_x=glyph_x,
                marker_top=glyph_y + size,
                glyph_x=glyph_x,
                glyph_y=glyph_y,
            )
        )
    return markers


def _markers_in_annotations(page_obj, page_number: int) -> List[_AnnotEncoding]:
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
            llx, lly, urx, ury = [float(value) for value in rect]
        except (TypeError, ValueError):
            continue
        markers.append(
            _AnnotEncoding(
                page=page_number,
                origin_x=llx,
                marker_top=ury,
                llx=llx,
                lly=lly,
                urx=urx,
                ury=ury,
            )
        )
    return markers


def _text_inside_annotation(text: _TextEncoding, annot: _AnnotEncoding) -> bool:
    return (
        text.page == annot.page
        and annot.llx <= text.glyph_x <= annot.urx
        and annot.lly <= text.glyph_y <= annot.ury
    )


def _prefer_annotation_when_text_inside(
    texts: List[_TextEncoding],
    annots: List[_AnnotEncoding],
):
    leftover_text = [
        text
        for text in texts
        if not any(_text_inside_annotation(text, annot) for annot in annots)
    ]
    return list(annots) + leftover_text


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
        page_left, page_bottom, page_right, page_top = _page_box(page)
        found_text: List[_TextEncoding] = []

        def visitor(text, cm, tm, fontDict, fontSize, _page=page_number, _bucket=found_text):
            _bucket.extend(_markers_in_text(text, tm, fontSize, _page))

        try:
            page.extract_text(visitor_text=visitor)
        except Exception:
            pass
        found_annots = _markers_in_annotations(page, page_number)
        for encoding in _prefer_annotation_when_text_inside(found_text, found_annots):
            markers.append(
                _marcador_on_page(
                    page=encoding.page,
                    origin_x=encoding.origin_x,
                    marker_top=encoding.marker_top,
                    page_left=page_left,
                    page_bottom=page_bottom,
                    page_right=page_right,
                    page_top=page_top,
                )
            )
    return _dedupe(markers)
