from PIL import Image, ImageDraw, ImageFont
import io
import base64

def create_signature_image(text, encoded_image, width=233, height=56, scale_factor=10):
    # Create a new image with white background at higher resolution
    high_res_width, high_res_height = width * scale_factor, height * scale_factor
    img = Image.new('RGB', (high_res_width, high_res_height), color='white')
    draw = ImageDraw.Draw(img)
    
    # Try to use the PTSerif font, falling back to default if not available
    try:
        font = ImageFont.truetype("./PTSerif-Regular.ttf", 8 * scale_factor)
    except IOError:
        font = ImageFont.load_default()
        print("Warning: Using default font. Text size may not be as expected.")
    
    # Split text into lines and draw each line
    lines = text.split('\n')
    y_text = 5 * scale_factor  # Start 5 pixels from top edge (scaled)
    for line in lines:
        draw.text((5 * scale_factor, y_text), line, font=font, fill='black')
        y_text += font.getbbox(line)[3] + 2 * scale_factor  # Move to next line (font height + 2 pixels, scaled)
    
    # Decode and open the stamp image
    stamp_data = base64.b64decode(encoded_image)
    stamp = Image.open(io.BytesIO(stamp_data))
    
    # Scale down the high-resolution stamp image to fit within the final dimensions
    stamp_scaled = stamp.resize((width - int(width * 0.75) - 5, height - 4), Image.LANCZOS)

    # Scale up the stamp image for the high resolution canvas
    stamp_scaled_high_res = stamp_scaled.resize((stamp_scaled.width * scale_factor, stamp_scaled.height * scale_factor), Image.LANCZOS)

    # Calculate position to paste stamp (right-aligned)
    stamp_x = high_res_width - stamp_scaled_high_res.width - 2 * scale_factor  # 2 pixels padding from right edge (scaled)
    stamp_y = (high_res_height - stamp_scaled_high_res.height) // 2

    # Paste stamp image
    img.paste(stamp_scaled_high_res, (stamp_x, stamp_y), stamp_scaled_high_res if stamp_scaled_high_res.mode == 'RGBA' else None)
    
    # Function to save and encode image
    def save_and_encode(image, filename, dpi):
        buffered = io.BytesIO()
        image.save(buffered, format="PNG", optimize=True, dpi=dpi)
        image.save(filename, format='PNG', dpi=dpi, optimize=True)
        return base64.b64encode(buffered.getvalue()).decode('utf-8')
    
    # Save and encode high resolution image
    high_res_base64 = save_and_encode(img, "high_res_image.png", (600, 600))
    
    # Scale down the image
    img_scaled = img.resize((width, height), Image.LANCZOS)
    
    # Save and encode scaled down image
    scaled_base64 = save_and_encode(img_scaled, "scaled_image.png", (600, 600))
    
    return high_res_base64