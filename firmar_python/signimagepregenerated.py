from PIL import Image, ImageDraw, ImageFont
import io
import base64

def create_signature_image(text, encoded_image, width=234, height=57, scale_factor=5):
    # Create a new image with white background at higher resolution
    high_res_width = width * scale_factor
    high_res_height = height * scale_factor
    img = Image.new('RGB', (high_res_width, high_res_height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use the Roboto font, falling back to default if not available
    try:
        font = ImageFont.truetype("./PTSerif-Regular.ttf", 9 * scale_factor)
    except IOError:
        font = ImageFont.load_default()
        print("Warning: Using default font. Text size may not be as expected.")
    
    # Calculate text area width (about 75% of total width)
    text_width = int(high_res_width * 0.75)
    
    # Split text into lines and draw each line
    lines = text.split('\n')
    y_text = 5 * scale_factor
    for line in lines:
        draw.text((5 * scale_factor, y_text), line, font=font, fill='black')
        y_text += font.getbbox(line)[3] + 2 * scale_factor  # Move to next line (font height + 2 pixels)
    
    # Decode and open the stamp image
    stamp_data = base64.b64decode(encoded_image)
    stamp = Image.open(io.BytesIO(stamp_data))
    
    # Resize stamp to fit within the remaining width and height
    stamp_max_width = high_res_width - text_width - 5 * scale_factor  # 5 pixels padding
    stamp_max_height = high_res_height - 4 * scale_factor  # 2 pixels padding top and bottom
    stamp.thumbnail((stamp_max_width, stamp_max_height))
    
    # Calculate position to paste stamp (right-aligned)
    stamp_x = high_res_width - stamp.width - 2 * scale_factor  # 2 pixels padding from right edge
    stamp_y = (high_res_height - stamp.height) // 2
    
    # Paste stamp image
    img.paste(stamp, (stamp_x, stamp_y), stamp if stamp.mode == 'RGBA' else None)
    
    # Downscale the image to the final size
    img = img.resize((width, height), Image.Resampling.LANCZOS)
    
    # Convert the image to base64
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    return img_base64
