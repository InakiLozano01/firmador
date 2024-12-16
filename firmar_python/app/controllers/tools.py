from app.services.tools_service import ToolsService

class ToolsController:
    def __init__(self):
        self.service = ToolsService()

    def merge_and_watermark_pdfs(self, pdfs, watermark_text):
        try:
            return self.service.merge_and_watermark_pdfs(pdfs, watermark_text)
        except Exception as e:
            return {"error": str(e)}
