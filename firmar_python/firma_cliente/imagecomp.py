from PIL import Image
from base64 import b64encode
from io import BytesIO

def encode_image(image_path, dpi=(200, 200)):
    try:
        # Abrir la imagen
        with Image.open(image_path) as img:
            # Convertir la imagen a modo RGBA para mantener la transparencia
            img = img.convert("L")
        
            # Comprimir la imagen
            buffer = BytesIO()
            img.save(buffer, format="PNG", optimize=True, dpi=dpi)
            
            # Obtener los bytes de la imagen comprimida
            encoded_image_bytes = buffer.getvalue()
        
        # Codificar la imagen comprimida a base64
        encoded_image = b64encode(encoded_image_bytes).decode('utf-8')
        return encoded_image
    except Exception as e:
        print(f"Error: {str(e)}")
        return None


