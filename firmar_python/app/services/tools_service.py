import logging
from app.utils.watermark_utils import merge_pdf_files_pdfrw, add_watermark_to_pdf
import base64
from datetime import datetime
from app.exceptions import validation_exc

# Configure logging
logger = logging.getLogger(__name__)

class ToolsService:
    def __init__(self):
        logger.debug("ToolsService initialized")

    def merge_and_watermark_pdfs(self, pdfs, watermark_text):
        logger.info("Starting PDF merge and watermark process")
        logger.debug(f"Processing {len(pdfs)} PDFs")

        try:
            logger.debug("Decoding PDF files from base64")
            pdfs_bytes = [base64.b64decode(pdf) for pdf in pdfs]
            logger.debug("Successfully decoded all PDFs")
        except Exception as e:
            logger.error(f"Failed to decode PDFs: {str(e)}", exc_info=True)
            raise validation_exc.InvalidSignatureDataError(f"Error al decodificar los PDFs: {str(e)}")
        
        try:
            logger.debug("Merging PDF files")
            pdf_merged = merge_pdf_files_pdfrw(pdfs_bytes)
            logger.debug("Successfully merged PDFs")
        except Exception as e:
            logger.error(f"Failed to merge PDFs: {str(e)}", exc_info=True)
            raise validation_exc.InvalidSignatureDataError(f"Error al fusionar los PDFs: {str(e)}")
        
        try:
            logger.debug("Adding watermark to merged PDF")
            watermark_text = f"Descargado por: {watermark_text} {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            pdf_watermarked = add_watermark_to_pdf(pdf_merged, watermark_text)
            logger.debug("Successfully added watermark")
        except Exception as e:
            logger.error(f"Failed to add watermark: {str(e)}", exc_info=True)
            raise validation_exc.InvalidSignatureDataError(f"Error al agregar el watermark: {str(e)}")
        
        try:
            logger.debug("Encoding final PDF to base64")
            pdf_bytes = base64.b64encode(pdf_watermarked).decode('utf-8')
            logger.debug("Successfully encoded final PDF")
            logger.info("PDF merge and watermark process completed successfully")
            return pdf_bytes
        except Exception as e:
            logger.error(f"Failed to encode final PDF: {str(e)}", exc_info=True)
            raise validation_exc.InvalidSignatureDataError(f"Error al codificar el PDF: {str(e)}")
