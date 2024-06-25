from PIL import Image, ImageDraw, ImageFont
import io
import base64

def create_signature_image(text, encoded_image, width=233, height=56):
    # Create a new image with white background at higher resolution
    
    img = Image.new('RGB', (width, height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use the Roboto font, falling back to default if not available
    try:
        font = ImageFont.truetype("./PTSerif-Regular.ttf", 9)
    except IOError:
        font = ImageFont.load_default()
        print("Warning: Using default font. Text size may not be as expected.")
    
    # Calculate text area width (about 75% of total width)
    #text_width = int(width * 0.75)
    
    # Split text into lines and draw each line
    lines = text.split('\n')
    y_text = 5 # Start 5 pixels from top edge
    for line in lines:
        draw.text((5, y_text), line, font=font, fill='black')
        y_text += font.getbbox(line)[3] + 2  # Move to next line (font height + 2 pixels)
    
    # Decode and open the stamp image
    stamp_data = base64.b64decode(encoded_image)
    stamp = Image.open(io.BytesIO(stamp_data))

    # Ensure the stamp fits within the final dimensions
    stamp.thumbnail((50, 50), Image.LANCZOS)

    # Calculate position to paste stamp (right-aligned)
    stamp_x = width - stamp.width - 2  # 2 pixels padding from right edge
    stamp_y = (height - stamp.height) // 2

    # Paste stamp image
    img.paste(stamp, (stamp_x, stamp_y), stamp if stamp.mode == 'RGBA' else None)
    
    # Convert the image to base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    return img_base64
