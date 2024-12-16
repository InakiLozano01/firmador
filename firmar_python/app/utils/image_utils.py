# Description: Módulo para comprimir y codificar imágenes

from PIL import Image, ImageDraw, ImageFont
import base64
import io
import os
import logging
from app.exceptions.tool_exc import (
    ImageProcessingError,
    ImageNotFoundError,
    ImageEncodingError,
    ImageDecodingError,
    InvalidImageFormatError,
    FontLoadError,
    StampDecodingError,
    ImageCreationError,
    ImageScalingError
)

# Configure logging
logger = logging.getLogger(__name__)

# Define font paths
FONT_PATHS = [
    "/app/assets/fonts/PTSerif-Regular.ttf",  # Main container path
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",  # Common Linux fallback
    "/usr/share/fonts/TTF/DejaVuSerif.ttf",  # Alternative Linux path
    "C:\\Windows\\Fonts\\times.ttf"  # Windows fallback
]

def get_available_font(size: int) -> ImageFont.FreeTypeFont:
    """
    Try to load a font from the available font paths.
    
    Args:
        size (int): Font size to use
        
    Returns:
        ImageFont.FreeTypeFont: Loaded font
        
    Raises:
        FontLoadError: If no suitable font can be loaded
    """
    errors = []
    for font_path in FONT_PATHS:
        try:
            logger.debug(f"Attempting to load font from: {font_path}")
            return ImageFont.truetype(font_path, size)
        except Exception as e:
            errors.append(f"Failed to load {font_path}: {str(e)}")
            continue
    
    # If we get here, try to use default font
    try:
        logger.debug("Attempting to load default font")
        return ImageFont.load_default()
    except Exception as e:
        errors.append(f"Failed to load default font: {str(e)}")
    
    error_msg = "\\n".join(errors)
    logger.error(f"Failed to load any fonts: {error_msg}")
    raise FontLoadError(f"Could not load any suitable fonts. Errors: {error_msg}")

def encode_image(image_path: str, dpi: tuple = (200, 200)) -> dict:
    """
    Encode an image to base64 string with compression.
    
    Args:
        image_path (str): Path to the image file
        dpi (tuple): DPI resolution for the image (default: (200, 200))
        
    Returns:
        dict: Dictionary containing the encoded image and status
        
    Raises:
        ImageNotFoundError: If the image file doesn't exist
        ImageEncodingError: If there's an error encoding the image
        InvalidImageFormatError: If the image format is not supported
        ImageProcessingError: For any other unexpected errors
    """
    logger.info(f"Starting image encoding for {image_path}")
    try:
        logger.debug(f"Opening image with DPI {dpi}")
        with Image.open(image_path) as img:
            img = img.convert("L")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True, dpi=dpi)
            encoded_image_bytes = buffer.getvalue()
        
        encoded_image = base64.b64encode(encoded_image_bytes).decode('utf-8')
        logger.info("Image encoded successfully")
        return {
            "success": True,
            "data": encoded_image,
            "message": "Image encoded successfully"
        }
    except FileNotFoundError:
        logger.error(f"Image file not found at path: {image_path}", exc_info=True)
        raise ImageNotFoundError(f"Image file not found at path: {image_path}")
    except IOError as e:
        logger.error(f"Error encoding image: {str(e)}", exc_info=True)
        raise ImageEncodingError(f"Error encoding image: {str(e)}")
    except ValueError as e:
        logger.error(f"Invalid image format: {str(e)}", exc_info=True)
        raise InvalidImageFormatError(f"Invalid image format: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during image processing: {str(e)}", exc_info=True)
        raise ImageProcessingError(f"Unexpected error during image processing: {str(e)}")

def decode_image(encoded_image: str) -> dict:
    """
    Decode a base64 encoded image string back to a PIL Image.
    
    Args:
        encoded_image (str): Base64 encoded image string
        
    Returns:
        dict: Dictionary containing the decoded image and status
        
    Raises:
        ImageDecodingError: If there's an error decoding the base64 string
        InvalidImageFormatError: If the decoded data is not a valid image
        ImageProcessingError: For any other unexpected errors
    """
    logger.info("Starting image decoding")
    try:
        logger.debug("Decoding base64 string")
        image_bytes = base64.b64decode(encoded_image)
        image = Image.open(io.BytesIO(image_bytes))
        logger.info("Image decoded successfully")
        return {
            "success": True,
            "data": image,
            "message": "Image decoded successfully"
        }
    except base64.binascii.Error:
        logger.error("Invalid base64 encoded string", exc_info=True)
        raise ImageDecodingError("Invalid base64 encoded string")
    except IOError as e:
        logger.error(f"Invalid image format or corrupted data: {str(e)}", exc_info=True)
        raise InvalidImageFormatError(f"Invalid image format or corrupted data: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error during image processing: {str(e)}", exc_info=True)
        raise ImageProcessingError(f"Unexpected error during image processing: {str(e)}")

def create_signature_image(text: str, encoded_image: str, path: str, width: int = 233, height: int = 56, scale_factor: int = 3) -> dict:
    """
    Create a signature image with text and a stamp.
    
    Args:
        text (str): The text to add to the signature image
        encoded_image (str): Base64 encoded stamp image
        path (str): Path identifier for the image
        width (int): Final width of the scaled image (default: 233)
        height (int): Final height of the scaled image (default: 56)
        scale_factor (int): Scale factor for initial high-resolution image (default: 3)
        
    Returns:
        dict: Dictionary containing the encoded high-resolution image and status
        
    Raises:
        FontLoadError: If there's an error loading the required font
        StampDecodingError: If there's an error decoding the stamp image
        ImageCreationError: If there's an error creating the signature image
        ImageScalingError: If there's an error scaling the image
        ImageProcessingError: For any other unexpected errors
    """
    logger.info("Starting signature image creation")
    try:
        # Create a new image with white background at higher resolution
        high_res_width, high_res_height = width * scale_factor, height * scale_factor
        logger.debug(f"Creating new image with dimensions {high_res_width}x{high_res_height}")
        img = Image.new('L', (int(high_res_width), int(high_res_height)), color='white')
        draw = ImageDraw.Draw(img)
        
        # Try to load a suitable font
        logger.debug("Loading font")
        font = get_available_font(int(8 * scale_factor))
        logger.debug("Font loaded successfully")
        
        # Decode and open the stamp image
        logger.debug("Decoding stamp image")
        try:
            stamp_data = base64.b64decode(encoded_image)
            stamp = Image.open(io.BytesIO(stamp_data))
            logger.debug("Stamp image decoded successfully")
        except (base64.binascii.Error, IOError) as e:
            logger.error(f"Error decoding stamp image: {str(e)}", exc_info=True)
            raise StampDecodingError(f"Error decoding stamp image: {str(e)}")

        # Calculate new dimensions for the stamp image
        logger.debug("Scaling stamp image")
        try:
            stamp_max_width = high_res_width * 0.25
            stamp_max_height = high_res_height - 10 * scale_factor
            stamp.thumbnail((int(stamp_max_width), int(stamp_max_height)), Image.LANCZOS)
            logger.debug(f"Stamp scaled to {stamp.width}x{stamp.height}")
        except Exception as e:
            logger.error(f"Error scaling stamp image: {str(e)}", exc_info=True)
            raise ImageScalingError(f"Error scaling stamp image: {str(e)}")
        
        # Calculate positions
        stamp_x = 2 * scale_factor
        stamp_y = (high_res_height - stamp.height) // 2
        text_start_x = stamp_x + stamp.width + 10 * scale_factor
        y_text = 5 * scale_factor

        # Paste stamp image
        logger.debug("Pasting stamp image")
        try:
            img.paste(stamp, (int(stamp_x), int(stamp_y)), stamp if stamp.mode == 'RGBA' else None)
            logger.debug("Stamp pasted successfully")
        except Exception as e:
            logger.error(f"Error pasting stamp image: {str(e)}", exc_info=True)
            raise ImageCreationError(f"Error pasting stamp image: {str(e)}")

        # Draw text
        logger.debug("Drawing text")
        try:
            lines = text.split('\n')
            for line in lines:
                draw.text((text_start_x, y_text), line, font=font, fill='black')
                y_text += font.getbbox(line)[3] + 2 * scale_factor
            logger.debug(f"Drew {len(lines)} lines of text")
        except Exception as e:
            logger.error(f"Error drawing text: {str(e)}", exc_info=True)
            raise ImageCreationError(f"Error drawing text: {str(e)}")

        # Save and encode high resolution image
        logger.debug("Saving and encoding final image")
        try:
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True, dpi=(200, 200))
            high_res_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Scale down the image
            img_scaled = img.resize((width, height), Image.LANCZOS)
            logger.debug(f"Image scaled down to {width}x{height}")
            
            logger.info("Signature image created successfully")
            return {
                "success": True,
                "data": high_res_base64,
                "message": "Signature image created successfully"
            }
        except Exception as e:
            logger.error(f"Error encoding final image: {str(e)}", exc_info=True)
            raise ImageEncodingError(f"Error encoding final image: {str(e)}")
            
    except (FontLoadError, StampDecodingError, ImageCreationError, 
            ImageScalingError, ImageEncodingError) as e:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during signature image creation: {str(e)}", exc_info=True)
        raise ImageProcessingError(f"Unexpected error during signature image creation: {str(e)}")


