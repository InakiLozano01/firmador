import base64
import io
import sys
import unittest
from pathlib import Path

from PyPDF2 import PdfReader
from reportlab.pdfgen import canvas


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.utils.pdf_trib import SELLO_HEIGHT, SELLO_WIDTH, find_marcadores_trib


A4_WIDTH = 595.0
A4_HEIGHT = 842.0


def _pdf_with_text(x, y, text, *, font_size=12, pagesize=(A4_WIDTH, A4_HEIGHT)) -> str:
    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=pagesize)
    pdf.setFont("Helvetica", font_size)
    pdf.drawString(x, y, text)
    pdf.showPage()
    pdf.save()
    return base64.b64encode(buffer.getvalue()).decode("ascii")


class FindMarcadoresTribTest(unittest.TestCase):
    def test_dss_origin_is_top_left_of_page(self):
        # DSS SignatureFieldParameters origin is the page's top-left, not PDF user space.
        pdf = _pdf_with_text(100, 500, "@TRIB", font_size=12)
        markers = find_marcadores_trib(pdf)

        self.assertEqual(len(markers), 1)
        marker = markers[0]
        self.assertEqual(marker.page, 1)
        self.assertAlmostEqual(marker.origin_x, 100, delta=2)
        self.assertAlmostEqual(marker.origin_y, A4_HEIGHT - 500, delta=20)
        self.assertEqual(marker.width, SELLO_WIDTH)
        self.assertEqual(marker.height, SELLO_HEIGHT)

    def test_safyc_comprobante_trib_on_right_keeps_sello_on_page(self):
        # Real SAFyC "Comprobante de Ejecución del Gasto": almost-invisible
        # "@CGP @SAF @TRIB" near the right edge. A 320pt sello growing right
        # from that glyph overflows A4 and DSS returns 500 on getDataToSign.
        pdf = _pdf_with_text(396.19, 271.44, "@CGP @SAF @TRIB", font_size=2)
        markers = find_marcadores_trib(pdf)

        self.assertEqual(len(markers), 1)
        marker = markers[0]
        self.assertGreaterEqual(marker.origin_x, 0)
        self.assertGreaterEqual(marker.origin_y, 0)
        self.assertLessEqual(marker.origin_x + marker.width, A4_WIDTH + 0.01)
        self.assertLessEqual(marker.origin_y + marker.height, A4_HEIGHT + 0.01)
        self.assertAlmostEqual(marker.origin_x, 410, delta=8)
        self.assertLess(marker.width, SELLO_WIDTH)
        self.assertGreater(marker.width, 150)
        self.assertEqual(marker.height, SELLO_HEIGHT)

    def test_trib_near_top_keeps_sello_on_page(self):
        pdf = _pdf_with_text(40, 830, "@TRIB", font_size=12)
        markers = find_marcadores_trib(pdf)

        self.assertEqual(len(markers), 1)
        marker = markers[0]
        self.assertGreaterEqual(marker.origin_y, 0)
        self.assertLessEqual(marker.origin_y + marker.height, A4_HEIGHT + 0.01)
        self.assertLess(marker.origin_y, 20)
        reader = PdfReader(io.BytesIO(base64.b64decode(pdf)))
        self.assertEqual(len(reader.pages), 1)


if __name__ == "__main__":
    unittest.main()
