from app.utils.watermark_utils import merge_pdf_files_pdfrw, add_watermark_to_pdf
import base64
from datetime import datetime

class ToolsService:
    def merge_and_watermark_pdfs(self, pdfs, watermark_text):
        try:
            pdfs_bytes = [base64.b64decode(pdf) for pdf in pdfs]
        except Exception as e:
            raise Exception("Error al decodificar los PDFs: " + str(e))
        
        try:
            pdf_merged = merge_pdf_files_pdfrw(pdfs_bytes)
        except Exception as e:
            raise Exception("Error al fusionar los PDFs: " + str(e))
        
        try:
            watermark_text = f"Descargado por: {watermark_text} {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            pdf_watermarked = add_watermark_to_pdf(pdf_merged, watermark_text)
        except Exception as e:
            raise Exception("Error al agregar el watermark: " + str(e))
        
        try:
            pdf_bytes = base64.b64encode(pdf_watermarked).decode('utf-8')
            return pdf_bytes
        except Exception as e:
            raise Exception("Error al codificar el PDF: " + str(e))
