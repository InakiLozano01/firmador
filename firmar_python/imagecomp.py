from PIL import Image
import base64
import io

def compressed_image_bytes(image_path, size=(150, 150)):
    try:
        with Image.open(image_path) as img:
            img = img.convert("RGBA")
            img = img.resize(size, Image.LANCZOS)
            
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            compressed_image_bytes = buffer.getvalue()
        
        return compressed_image_bytes
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

# Function to compress and encode the image to base64
def compress_and_encode_image(image_path):
    try:
        with Image.open(image_path) as img:
            # Ensure the image is in RGBA mode to maintain transparency
            img = img.convert("RGBA")
            
            # Resize the image to exactly 150x150 pixels
            img = img.resize((150, 150), Image.LANCZOS)
            
            # Compress the image
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            
            # Get the compressed image bytes
            compressed_image_bytes = buffer.getvalue()
        
        # Encode the compressed image to base64
        encoded_image = base64.b64encode(compressed_image_bytes).decode('utf-8')
        return encoded_image
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

# Function to decode the base64 string back to an image
def decode_image(encoded_image):
    try:
        image_bytes = base64.b64decode(encoded_image)
        return Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

# Compress and encode the image
encoded_image = compress_and_encode_image("logo_tribunal_para_tapir.png")

