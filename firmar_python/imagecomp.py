from PIL import Image
import base64
import io

# Función para comprimir la imagen y obtener los bytes
def compressed_image_encoded(image_path, size=(50, 50)):
    try:
        # Abrir la imagen
        with Image.open(image_path) as img:
            # Convertir la imagen a modo RGBA para mantener la transparencia
            img = img.convert("RGBA")
            # Redimensionar la imagen a 150x150 píxeles
            img = img.resize(size, Image.LANCZOS)
            
            # Comprimir la imagen
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            # Obtener los bytes de la imagen comprimida
            compressed_image_bytes = buffer.getvalue()
        
        return compressed_image_bytes
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

# Función para comprimir y codificar la imagen a base64
def encode_image(image_path):
    try:
        # Abrir la imagen
        with Image.open(image_path) as img:
            # Convertir la imagen a modo RGBA para mantener la transparencia
            img = img.convert("RGBA")
        
            # Comprimir la imagen
            buffer = io.BytesIO()
            img.save(buffer, format="PNG", optimize=True)
            
            # Obtener los bytes de la imagen comprimida
            encoded_image_bytes = buffer.getvalue()
        
        # Codificar la imagen comprimida a base64
        encoded_image = base64.b64encode(encoded_image_bytes).decode('utf-8')
        return encoded_image
    except Exception as e:
        print(f"Error: {str(e)}")
        return None

# Función para decodificar la cadena base64 de nuevo a una imagen
def decode_image(encoded_image):
    try:
        # Decodificar la cadena base64 a bytes
        image_bytes = base64.b64decode(encoded_image)
        # Abrir la imagen a partir de los bytes
        return Image.open(io.BytesIO(image_bytes))
    except Exception as e:
        print(f"Error: {str(e)}")
        return None


