import logging
from app.services.tools_service import ToolsService
from app.config.state import app_state
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
    # Añade este método a la clase ToolsController

    def create_signature_image(self, username, area, department, datetime):
        """
        Create a signature image with user information
        
        Args:
            username (str): Name of the signer
            area (str): Area or position of the signer
            department (str): Department or office of the signer
            datetime (str): Date and time of the signature
        
        Returns:
            str: Base64 encoded image
        """
        try:
            #from app.utils.image_utils import create_sello_image as create_img
            from app.utils.image_utils import create_signature_image as create_img
            
            # Construir el texto para la firma (lado derecho de la imagen)
            text = f"{area}\n{department}\n{datetime}"
            
            # El username va en el parámetro usuario (lado izquierdo de la imagen)
            # Para el stamp image, usamos una imagen estándar o podemos tener una predefinida
            # En este caso, asumimos que hay una imagen predefinida en la función
          
            stamp_path = app_state.encoded_image.get("data")
            # Llamamos a la función de image_utils
            result = create_img(
                text=text,
                encoded_image=stamp_path,  # La imagen se cargará desde stamp_path
                path='show',
                width=280,
                height=40,
                scale_factor=3,
                usuario=username
            )
            
            if result.get("success"):
                # Get base64 data and convert it to HTML image format
                base64_data = result.get("data")
                html_image = f'<img src="data:image/png;base64,{base64_data}" alt="Signature"/>'
                return html_image
            else:
                raise Exception(result.get("message", "Unknown error creating signature image"))
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error in create_signature_image: {str(e)}", exc_info=True)
            raise Exception(f"Failed to create signature image: {str(e)}")    
