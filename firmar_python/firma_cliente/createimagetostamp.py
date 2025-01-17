from PIL import Image, ImageDraw, ImageFont
from io import BytesIO
from base64 import b64decode, b64encode
import os

def create_signature_image(text, encoded_image, path, mode, width=233, height=56, scale_factor=3):
    # Create a new image with white background at higher resolution
    high_res_width, high_res_height = width * scale_factor, height * scale_factor
    img = Image.new('L', (int(high_res_width), int(high_res_height)), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use the PTSerif font, falling back to default if not available
    try:
        if mode == 'python':
            font_path = r'.\fonts\PTSerif-Regular.ttf'
        else:
            exe_dir = os.path.dirname(os.path.abspath(__file__))
            font_path = os.path.join(exe_dir, "PTSerif-Regular.ttf")
        font = ImageFont.truetype(font_path, int(8 * scale_factor))
    except IOError:
        font = ImageFont.load_default()
        print("Warning: Using default font. Text size may not be as expected.")
    
    # Decode and open the stamp image
    stamp_data = b64decode(encoded_image)
    stamp = Image.open(BytesIO(stamp_data))

    # Calculate new dimensions for the stamp image to fit within the final dimensions
    stamp_max_width = high_res_width * 0.25  # Up to 25% of the width for the stamp
    stamp_max_height = high_res_height - 10 * scale_factor  # 10 pixels padding
    stamp.thumbnail((int(stamp_max_width), int(stamp_max_height)), Image.LANCZOS)
    
    # Calculate position to paste stamp (left-aligned)
    stamp_x = 2 * scale_factor  # 2 pixels padding from left edge (scaled)
    stamp_y = (high_res_height - stamp.height) // 2

    # Paste stamp image
    img.paste(stamp, (int(stamp_x), int(stamp_y)), stamp if stamp.mode == 'RGBA' else None)
    
    # Calculate the starting point for the text, adjusted for the stamp width and padding
    text_start_x = stamp_x + stamp.width + 10 * int(scale_factor)  # 10 pixels padding between stamp and text
    y_text = 5 * int(scale_factor)  # Start 5 pixels from top edge (scaled)
    
    # Split text into lines and draw each line
    lines = text.split('\n')
    for line in lines:
        draw.text((text_start_x, y_text), line, font=font, fill='black')
        y_text += font.getbbox(line)[3] + 2 * int(scale_factor)  # Move to next line (font height + 2 pixels, scaled)
    
    # Function to save and encode image
    def save_and_encode(image, filename, dpi):
        buffered = BytesIO()
        image.save(buffered, format="PNG", optimize=True, dpi=dpi)
        """ image.save(filename, format='PNG', dpi=dpi, optimize=True) """
        return b64encode(buffered.getvalue()).decode('utf-8')
    
    # Save and encode high resolution image
    high_res_base64 = save_and_encode(img, "high_res_image" + path + ".png", (200, 200))
    
    # Scale down the image
    img_scaled = img.resize((width, height), Image.LANCZOS)
    
    # Save and encode scaled down image
    scaled_base64 = save_and_encode(img_scaled, "scaled_image.png", (200, 200))
    
    return high_res_base64