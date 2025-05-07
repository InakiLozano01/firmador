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
    "/app/assets/fonts/PTSerif-Regular.ttf",  # Main container path 0
    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf",  # Better Unicode support 1
    "/usr/share/fonts/truetype/noto/NotoSerif-Regular.ttf",  # Full Unicode support 2
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",  # Common Linux fallback 3
    "/usr/share/fonts/TTF/DejaVuSerif.ttf",  # Alternative Linux path 4
    "C:\\Windows\\Fonts\\times.ttf" , # Windows fallback 5
    "/app/assets/fonts/RobotoCondensed-Regular.ttf",  # Regulara path 6
    "/app/assets/fonts/RobotoCondensed-Bold.ttf",  # bold font path 7
    "/app/assets/fonts/RobotoCondensed-Italic.ttf",  # italic font path 8
    
]

def get_available_font(size: int,style: int = -1) -> ImageFont.FreeTypeFont:
    """
    Try to load a font from the available font paths.
    
    Args:
        size (int): Font size to use
        style (int): Index of the font path to use (-1 for auto-detect)
        
    Returns:
        ImageFont.FreeTypeFont: Loaded font
        
    Raises:
        FontLoadError: If no suitable font can be loaded
    """
    errors = []
    if style == -1:
        for font_path in FONT_PATHS:
            try:
                logger.debug(f"Attempting to load font from: {font_path}")
                return ImageFont.truetype(font_path, size)
            except Exception as e:
                errors.append(f"Failed to load {font_path}: {str(e)}")
                continue
    else:
        return ImageFont.truetype(FONT_PATHS[style], size)

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

def create_signature_image(text: str, encoded_image: str, path: str, width: int = 280, height: int = 40, scale_factor: int = 3, usuario: str = '') -> dict:
    """
    Create a signature image with text and a stamp, with all elements properly centered.
    
    Args:
        text (str): The text to add to the signature image (info section)
        encoded_image (str): Base64 encoded stamp image (logo)
        path (str): Path identifier for the image
        width (int): Final width of the scaled image (default: 280)
        height (int): Final height of the scaled image (default: 40)
        scale_factor (int): Scale factor for initial high-resolution image (default: 3)
        usuario (str): User name/information to display
        
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
        img = Image.new('RGB', (int(high_res_width), int(high_res_height)), '#ffffff')
        draw = ImageDraw.Draw(img)
        
        # Try to load suitable fonts
        logger.debug("Loading fonts")
        font_regular = get_available_font(24, 6)  # Regular font for info text
        font_bold = get_available_font(32, 7)     # Bold font for user name
        logger.debug("Fonts loaded successfully")
        
        # Decode and open the stamp image (logo)
        logger.debug("Decoding stamp image")
        try:
            stamp_data = base64.b64decode(encoded_image)
            stamp = Image.open(io.BytesIO(stamp_data))
            logger.debug("Stamp image decoded successfully")
        except (base64.binascii.Error, IOError) as e:
            logger.error(f"Error decoding stamp image: {str(e)}", exc_info=True)
            raise StampDecodingError(f"Error decoding stamp image: {str(e)}")

        # Calculate new dimensions for the stamp image (logo)
        logger.debug("Scaling stamp image")
        try:
            stamp_max_width = 50
            stamp_max_height = 50
            stamp.thumbnail((int(stamp_max_width), int(stamp_max_height)), Image.LANCZOS)
            logger.debug(f"Stamp scaled to {stamp.width}x{stamp.height}")
        except Exception as e:
            logger.error(f"Error scaling stamp image: {str(e)}", exc_info=True)
            raise ImageScalingError(f"Error scaling stamp image: {str(e)}")
        
        # Pre-process text blocks to calculate heights for proper centering
        logger.debug("Calculating text heights for vertical centering")
        
        # Process user text to calculate its height
        user_lines = usuario.split('\n')
        user_total_height = 0
        for line in user_lines:
            line = line.upper()
            left, top, right, bottom = font_bold.getbbox(line)
            line_height = bottom - top
            
            # Check if line needs to be split
            if (right - left) > (high_res_width / 3):
                words = line.split()
                
                user_total_height += line_height   # First part
                user_total_height += line_height   # Second part
            else:
                user_total_height += line_height + 5
        
        # Process info text to calculate its height
        info_lines = text.split('\n')
        info_total_height = 0
        for line in info_lines:
            line = line.upper()
            left, top, right, bottom = font_regular.getbbox(line)
            line_height = bottom - top
            
            # Check if line needs to be split
            if (right - left) > (high_res_width / 3):
                words = line.split()
                if len(words) > 2:
                    info_total_height += line_height + 5  # First part
                    info_total_height += line_height + 5  # Second part
                else:
                    info_total_height += line_height   # First part
                    info_total_height += line_height   # Second part
            else:
                info_total_height += line_height + 5
        
        # Find the tallest element to use for vertical centering
        max_height = max(user_total_height, stamp_max_height, info_total_height)
        
        # Calculate vertical positions to center all elements
        center_y = high_res_height / 2
        user_start_y = center_y - (user_total_height / 2)
        stamp_y = center_y - (stamp_max_height / 2)
        info_start_y = center_y - (info_total_height / 2)
        
        # Calculate horizontal positions with logo section smaller than 1/3
        logo_section_width = stamp_max_width   # Logo width plus margin
        remaining_width = high_res_width - logo_section_width
        
        # Divide the remaining space equally between user and info sections
        user_section_width = remaining_width / 2
        info_section_width = remaining_width / 2
        
        # User section (left)
        user_section_right_edge = user_section_width
        
        # Logo section (middle)
        stamp_x = user_section_width + (logo_section_width / 2) - (stamp.width / 2)
        
        # Info section (right)
        info_section_start_x = user_section_width + logo_section_width
        info_section_center_x = info_section_start_x + (info_section_width / 2)
        
        # Draw USER text block (left side but right-aligned)
        logger.debug("Drawing USER text block")
        current_y = user_start_y
        try:
            for line in user_lines:
                line = line.upper()
                left, top, right, bottom = font_bold.getbbox(line)
                text_width = right - left
                
                # Check if text is too long and needs to be split
                if text_width > (user_section_width * 0.9):
                    words = line.split()
                    if len(words) > 2:
                        # First part
                        first_part = words[0] + " " + words[1]
                        left, top, right, bottom = font_bold.getbbox(first_part)
                        text_width = right - left
                        text_x = user_section_right_edge - text_width - 5  # Align to the right with 10px margin
                        draw.text((text_x, current_y), first_part, font=font_bold, fill='black')
                        current_y += bottom - top + (1 * scale_factor)
                        
                        # Second part
                        second_part = " ".join(words[2:])
                        left, top, right, bottom = font_bold.getbbox(second_part)
                        text_width = right - left
                        text_x = user_section_right_edge - text_width - 5  # Align to the right with 10px margin
                        draw.text((text_x, current_y), second_part, font=font_bold, fill='black')
                    else:
                        # Split into two lines if there are only two words
                        left, top, right, bottom = font_bold.getbbox(words[0])
                        text_width = right - left
                        text_x = user_section_right_edge - text_width - 5  # Align to the right with 10px margin
                        draw.text((text_x, current_y), words[0], font=font_bold, fill='black')
                        current_y += bottom - top + (1 * scale_factor)
                        
                        left, top, right, bottom = font_bold.getbbox(words[1])
                        text_width = right - left
                        text_x = user_section_right_edge - text_width - 5  # Align to the right with 10px margin
                        draw.text((text_x, current_y), words[1], font=font_bold, fill='black')
                else:
                    # Right-align the text in the user section
                    text_x = user_section_right_edge - text_width - 5  # Align to the right with 10px margin
                    draw.text((text_x, current_y), line, font=font_bold, fill='black')
                
                current_y += bottom - top + (1 * scale_factor)
            logger.debug(f"Drew {len(user_lines)} lines of USER text")
        except Exception as e:
            logger.error(f"Error drawing USER text: {str(e)}", exc_info=True)
            raise ImageCreationError(f"Error drawing USER text: {str(e)}")
        
        # Paste stamp image (logo in the middle)
        logger.debug("Pasting stamp image in the center")
        try:
            img.paste(stamp, (int(stamp_x), int(stamp_y)), stamp if stamp.mode == 'RGBA' else None)
            logger.debug("Stamp pasted successfully")
        except Exception as e:
            logger.error(f"Error pasting stamp image: {str(e)}", exc_info=True)
            raise ImageCreationError(f"Error pasting stamp image: {str(e)}")
        
        # Draw INFO text block (right side)
        logger.debug("Drawing INFO text block")
        current_y = info_start_y
        try:
            for line in info_lines:
                line = line.upper()
                left, top, right, bottom = font_regular.getbbox(line)
                text_width = right - left
                
                # Check if text is too long and needs to be split
                if text_width > (info_section_width * 0.9):
                    words = line.split()
                    if len(words) > 2:
                        # First part
                        first_part = words[0] + " " + words[1]
                        left, top, right, bottom = font_regular.getbbox(first_part)
                        text_width = right - left
                        # Alinear a la izquierda desde el inicio de la sección de info
                        text_x = info_section_start_x + 5  # Añadir pequeño margen
                        draw.text((text_x, current_y), first_part, font=font_regular, fill='black')
                        current_y += bottom - top + 6
                        
                        # Second part
                        second_part = " ".join(words[2:])
                        left, top, right, bottom = font_regular.getbbox(second_part)
                        text_width = right - left
                        # Alinear a la izquierda desde el inicio de la sección de info
                        text_x = info_section_start_x + 5  # Añadir pequeño margen
                        draw.text((text_x, current_y), second_part, font=font_regular, fill='black')
                    else:
                        # Split into two lines if there are only two words
                        left, top, right, bottom = font_regular.getbbox(words[0])
                        text_width = right - left
                        # Alinear a la izquierda desde el inicio de la sección de info
                        text_x = info_section_start_x + 5  # Añadir pequeño margen
                        draw.text((text_x, current_y), words[0], font=font_regular, fill='black')
                        current_y += bottom - top + 6
                        
                        left, top, right, bottom = font_regular.getbbox(words[1])
                        text_width = right - left
                        # Alinear a la izquierda desde el inicio de la sección de info
                        text_x = info_section_start_x + 5  # Añadir pequeño margen
                        draw.text((text_x, current_y), words[1], font=font_regular, fill='black')
                else:
                    # Alinear a la izquierda desde el inicio de la sección de info en lugar de centrar
                    text_x = info_section_start_x + 5  # Añadir pequeño margen
                    draw.text((text_x, current_y), line, font=font_regular, fill='black')
                
                current_y += bottom - top + 6
            logger.debug(f"Drew {len(info_lines)} lines of INFO text")
        except Exception as e:
            logger.error(f"Error drawing INFO text: {str(e)}", exc_info=True)
            raise ImageCreationError(f"Error drawing INFO text: {str(e)}")
        
        # Save and encode high resolution image
        logger.debug("Saving and encoding final image")
        try:
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True, dpi=(200, 200))
            high_res_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            logger.info("Signature image created successfully")

            return {
                "success": True,
                "data": high_res_base64,
                "message": "Signature image created successfully"
            }
        except Exception as e:
            logger.error(f"Error encoding final image: {str(e)}", exc_info=True)
            raise ImageEncodingError(f"Error encoding final image {usuario}: {str(e)}")
            
    except (FontLoadError, StampDecodingError, ImageCreationError, 
            ImageScalingError, ImageEncodingError) as e:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during signature image creation: {str(e)}", exc_info=True)
        raise ImageProcessingError(f"Unexpected error during signature image creation: {str(e)}")


def create_signature_image_system(text: str, encoded_image: str, path: str, width: int = 270, height: int = 66, scale_factor: int = 3,usuario: str = '') -> dict:
    """
    Create a signature image with text and a stamp para el System.
    
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
        img = Image.new('RGB', (int(high_res_width), int(high_res_height)),'#ffffff')
        draw = ImageDraw.Draw(img)
        
        # Try to load a suitable font
        logger.debug("Loading font")
        font = get_available_font(24,6) # 6 font roboto 
        font_bold = get_available_font(24,7) # 7 font roboto  BOLD
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
            stamp_max_width =  50 # high_res_width * 0.25
            stamp_max_height = 50 #high_res_height - 10 * scale_factor
            stamp.thumbnail((int(stamp_max_width), int(stamp_max_height)), Image.LANCZOS)
            logger.debug(f"Stamp scaled to {stamp.width}x{stamp.height}")
        except Exception as e:
            logger.error(f"Error scaling stamp image: {str(e)}", exc_info=True)
            raise ImageScalingError(f"Error scaling stamp image: {str(e)}")
        
        # Calculate positions
        stamp_x = (high_res_width/2) - (stamp_max_width/2) - 80 #2 * scale_factor
        stamp_y = (high_res_height - stamp.height) // 2
        text_start_x = stamp_x + stamp.width + 10
        text_y = stamp_y   
        pos_y_user = stamp_y + 10

        # Draw text USUARIO
        logger.debug("Drawing text USUARIO")
        try:
            nombreslower = usuario.split('\n')
            nombres =  []
            for line in nombreslower:
                nombres.append(line.upper())
            for line in nombres:
                logger.debug(f"Original text: {line}")
                logger.debug(f"Text encoding: {line.encode('utf-8')}")
                line = line.encode('utf-8').decode('utf-8')
                # Calcular posición x para alinear a la derecha
                # Calcular tamaño del texto
                left, top, right, bottom = font_bold.getbbox(line)
                text_width = right - left
                text_height = bottom - top
                x = stamp_x - text_width -10  # 5 ajuste para centrar alineado a la derecha
                draw.text((x , pos_y_user), line, font=font_bold, fill='black', align='right')
                pos_y_user += font_bold.getbbox(line)[3] + 2 * scale_factor

            logger.debug(f"Drew {len(nombres)} lines of text USUARIO")
        except Exception as e:
            logger.error(f"Error drawing text: {str(e)}", exc_info=True)
            raise ImageCreationError(f"Error drawing text: {str(e)}")

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
            lines = text.split('\n') # 1 sello 2 oficina 3 fecha
            for line in lines:
               
                line = line.encode('utf-8').decode('utf-8')
                draw.text((text_start_x, text_y), line, font=font, fill='black', align='left')
                text_y += font.getbbox(line)[3] + 2 * scale_factor

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
            
            """ # Scale down the image
            img_scaled = img.resize((width, height), Image.LANCZOS)
            logger.debug(f"Image scaled down to {width}x{height}")
            try:
                with open("signature_image.png", "wb") as f:
                    f.write(base64.b64decode(high_res_base64))
                logger.info("High-resolution image saved to the root of the project as 'signature_image.png'")
            except Exception as e:
               raise ImageCreationError(f"<img src='data:image/png;base64,{high_res_base64}' />") """   
            
            logger.info("Signature image created successfully")

            return {
                "success": True,
                "data": high_res_base64,
                "message": "Signature image created successfully"
            }
        except Exception as e:
            logger.error(f"Error encoding final image: {str(e)}", exc_info=True)
            raise ImageEncodingError(f"Error encoding final image {usuario}: {str(e)}")
            
    except (FontLoadError, StampDecodingError, ImageCreationError, 
            ImageScalingError, ImageEncodingError) as e:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during signature image creation: {str(e)}", exc_info=True)
        raise ImageProcessingError(f"Unexpected error during signature image creation: {str(e)}")


def create_sello_image(text: str, encoded_image: str, path: str, width: int = 280, height: int = 40, scale_factor: int = 3,usuario: str = '') -> dict:
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
        img = Image.new('RGB', (int(high_res_width), int(high_res_height)),'#ffffff')
        draw = ImageDraw.Draw(img)
        
        # Try to load a suitable font
        logger.debug("Loading font")
        font = get_available_font(24,6) # 6 font roboto 
        font_bold = get_available_font(32,7) # 7 font roboto  BOLD
        font_italic = get_available_font(24,8) # 7 font roboto  italic
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

        # Posición vertical inicial
        current_y = 5  # margen superior

        # Draw text USUARIO (centrado)
        logger.debug("Drawing text USUARIO")
        try:
            nombres_separado = usuario.split('\n')
            nombres = []
            for line in nombres_separado:
                nombres.append(line.upper())
           
            # Combinar el nombre completo si hay múltiples líneas
            nombre_completo = " ".join(nombres)
            
            # Calcular posición para centrar el texto
            left, top, right, bottom = font_bold.getbbox(nombre_completo)
            text_width = right - left
            text_height = bottom - top
            
            # Centrar horizontalmente
            pos_x_user = (high_res_width - text_width) // 2
            
            # Dibujar el nombre centrado
            draw.text((pos_x_user, current_y), nombre_completo, font=font_bold, fill='black')
            current_y += text_height + 2 * scale_factor
       
            logger.debug(f"Drew user name text centered")
        except Exception as e:
            logger.error(f"Error drawing text: {str(e)}", exc_info=True)
            raise ImageCreationError(f"Error drawing text: {str(e)}")
    
        # Draw additional text (centrado)
        logger.debug("Drawing additional text")
        try:
            lines = text.split('\n')  # 1 sello 2 oficina 3 fecha
            for i, line in enumerate(lines):
                logger.debug(f"Original text: {line}")
                logger.debug(f"Text encoding: {line.encode('utf-8')}")
                line = line.encode('utf-8').decode('utf-8').upper()
                
                # Choose font based on line number
                current_font = font_italic if i == 0 else font
                
                # Calcular posición para centrar cada línea
                left, top, right, bottom = current_font.getbbox(line)
                text_width = right - left
                text_height = bottom - top
                
                # Centrar horizontalmente
                text_x = (high_res_width - text_width) // 2
                
                draw.text((text_x, current_y), line, font=current_font, fill='black')
                current_y += text_height + 3

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
            
            logger.info("Signature image created successfully")

            return {
                "success": True,
                "data": high_res_base64,
                "message": "Signature image created successfully"
            }
        except Exception as e:
            logger.error(f"Error encoding final image: {str(e)}", exc_info=True)
            raise ImageEncodingError(f"Error encoding final image {usuario}: {str(e)}")
            
    except (FontLoadError, StampDecodingError, ImageCreationError, 
            ImageScalingError, ImageEncodingError) as e:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during signature image creation: {str(e)}", exc_info=True)
        raise ImageProcessingError(f"Unexpected error during signature image creation: {str(e)}")