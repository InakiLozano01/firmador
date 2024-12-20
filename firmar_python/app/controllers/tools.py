import logging
from app.services.tools_service import ToolsService

# Configure logging
logger = logging.getLogger(__name__)

class ToolsController:
    def __init__(self):
        self.service = ToolsService()
        logger.debug("ToolsController initialized")

    def merge_and_watermark_pdfs(self, pdfs, watermark_text):
        logger.info("Starting PDF merge and watermark operation")
        logger.debug(f"Processing {len(pdfs)} PDFs with watermark text: {watermark_text}")
        try:
            result = self.service.merge_and_watermark_pdfs(pdfs, watermark_text)
            logger.info("PDF merge and watermark operation completed successfully")
            return result
        except Exception as e:
            logger.error(f"Error during PDF merge and watermark: {str(e)}", exc_info=True)
            return {"error": str(e)}
