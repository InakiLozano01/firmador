from PIL import Image, ImageDraw, ImageFont
import io
import base64

def create_signature_image(text, encoded_image, width=234, height=57, dpi=300):
    # Calculate the actual size of the image based on the DPI
    new_width = width * dpi // 72
    new_height = height * dpi // 72
    
    # Create a new image with white background at higher resolution
    img = Image.new('RGB', (new_width, new_height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use the Roboto font, falling back to default if not available
    try:
        font = ImageFont.truetype("./Roboto-Regular.ttf", 9 * dpi // 72)  # scale font size to DPI
    except IOError:
        font = ImageFont.load_default()
        print("Warning: Using default font. Text size may not be as expected.")
    
    # Calculate text area width (about 75% of total width)
    text_width = int(new_width * 0.75)
    
    # Split text into lines and draw each line
    lines = text.split('\n')
    y_text = 5 * dpi // 72
    for line in lines:
        draw.text((5 * dpi // 72, y_text), line, font=font, fill='black')
        y_text += font.getbbox(line)[3] + 2 * dpi // 72  # Move to next line (font height + 2 pixels)
    
    # Decode and open the stamp image
    stamp_data = base64.b64decode(encoded_image)
    stamp = Image.open(io.BytesIO(stamp_data))
    
    # Resize stamp to fit within the remaining width and height
    stamp_max_width = new_width - text_width - 5 * dpi // 72  # 5 pixels padding
    stamp_max_height = new_height - 4 * dpi // 72  # 2 pixels padding top and bottom
    stamp.thumbnail((stamp_max_width, stamp_max_height))
    
    # Calculate position to paste stamp (right-aligned)
    stamp_x = new_width - stamp.width - 2 * dpi // 72  # 2 pixels padding from right edge
    stamp_y = (new_height - stamp.height) // 2
    
    # Paste stamp image
    img.paste(stamp, (stamp_x, stamp_y), stamp if stamp.mode == 'RGBA' else None)
    
    # Resize the image back to the original size
    img = img.resize((width, height), Image.ANTIALIAS)
    
    # Convert the image to base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    return img_base64
