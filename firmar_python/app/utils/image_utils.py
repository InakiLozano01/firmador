# Description: Módulo para comprimir y codificar imágenes

from PIL import Image, ImageDraw, ImageFont
import base64
import io
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
    try:
        with Image.open(image_path) as img:
            img = img.convert("L")
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True, dpi=dpi)
            encoded_image_bytes = buffer.getvalue()
        
        encoded_image = base64.b64encode(encoded_image_bytes).decode('utf-8')
        return {
            "success": True,
            "data": encoded_image,
            "message": "Image encoded successfully"
        }
    except FileNotFoundError:
        raise ImageNotFoundError(f"Image file not found at path: {image_path}")
    except IOError as e:
        raise ImageEncodingError(f"Error encoding image: {str(e)}")
    except ValueError as e:
        raise InvalidImageFormatError(f"Invalid image format: {str(e)}")
    except Exception as e:
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
    try:
        image_bytes = base64.b64decode(encoded_image)
        image = Image.open(io.BytesIO(image_bytes))
        return {
            "success": True,
            "data": image,
            "message": "Image decoded successfully"
        }
    except base64.binascii.Error:
        raise ImageDecodingError("Invalid base64 encoded string")
    except IOError as e:
        raise InvalidImageFormatError(f"Invalid image format or corrupted data: {str(e)}")
    except Exception as e:
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
    try:
        # Create a new image with white background at higher resolution
        high_res_width, high_res_height = width * scale_factor, height * scale_factor
        img = Image.new('L', (int(high_res_width), int(high_res_height)), color='white')
        draw = ImageDraw.Draw(img)
        
        # Try to use the PTSerif font
        try:
            font = ImageFont.truetype("../assets/fonts/PTSerif-Regular.ttf", int(8 * scale_factor))
        except IOError as e:
            raise FontLoadError(f"Error loading PTSerif font: {str(e)}")
        
        # Decode and open the stamp image
        try:
            stamp_data = base64.b64decode(encoded_image)
            stamp = Image.open(io.BytesIO(stamp_data))
        except (base64.binascii.Error, IOError) as e:
            raise StampDecodingError(f"Error decoding stamp image: {str(e)}")

        # Calculate new dimensions for the stamp image
        try:
            stamp_max_width = high_res_width * 0.25
            stamp_max_height = high_res_height - 10 * scale_factor
            stamp.thumbnail((int(stamp_max_width), int(stamp_max_height)), Image.LANCZOS)
        except Exception as e:
            raise ImageScalingError(f"Error scaling stamp image: {str(e)}")
        
        # Calculate positions
        stamp_x = 2 * scale_factor
        stamp_y = (high_res_height - stamp.height) // 2
        text_start_x = stamp_x + stamp.width + 10 * scale_factor
        y_text = 5 * scale_factor

        # Paste stamp image
        try:
            img.paste(stamp, (int(stamp_x), int(stamp_y)), stamp if stamp.mode == 'RGBA' else None)
        except Exception as e:
            raise ImageCreationError(f"Error pasting stamp image: {str(e)}")

        # Draw text
        try:
            lines = text.split('\n')
            for line in lines:
                draw.text((text_start_x, y_text), line, font=font, fill='black')
                y_text += font.getbbox(line)[3] + 2 * scale_factor
        except Exception as e:
            raise ImageCreationError(f"Error drawing text: {str(e)}")

        # Save and encode high resolution image
        try:
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True, dpi=(200, 200))
            high_res_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Scale down the image
            img_scaled = img.resize((width, height), Image.LANCZOS)
            
            return {
                "success": True,
                "data": high_res_base64,
                "message": "Signature image created successfully"
            }
        except Exception as e:
            raise ImageEncodingError(f"Error encoding final image: {str(e)}")
            
    except (FontLoadError, StampDecodingError, ImageCreationError, 
            ImageScalingError, ImageEncodingError) as e:
        raise
    except Exception as e:
        raise ImageProcessingError(f"Unexpected error during signature image creation: {str(e)}")


