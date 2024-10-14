from pdfrw import PdfReader as pdfr, PdfWriter as pdfw, PdfName as pdfn
import io
from PyPDF2 import PdfWriter, PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3

def merge_pdf_files_pdfrw(pdf_bytes):
    output = pdfw()
    num = 0
    output_acroform = None
    for pdf in pdf_bytes:
        input = pdfr(fdata=pdf,verbose=False)
        output.addpages(input.pages)
        if pdfn('AcroForm') in input[pdfn('Root')].keys():  # Not all PDFs have an AcroForm node
            source_acroform = input[pdfn('Root')][pdfn('AcroForm')]
            if pdfn('Fields') in source_acroform:
                output_formfields = source_acroform[pdfn('Fields')]
            else:
                output_formfields = []
            num2 = 0
            for form_field in output_formfields:
                key = pdfn('T')
                old_name = form_field[key].replace('(','').replace(')','')  # Field names are in the "(name)" format
                form_field[key] = 'FILE_{n}_FIELD_{m}_{on}'.format(n=num, m=num2, on=old_name)
                num2 += 1
            if output_acroform == None:
                # copy the first AcroForm node
                output_acroform = source_acroform
            else:
                for key in source_acroform.keys():
                    # Add new AcroForms keys if output_acroform already existing
                    if key not in output_acroform:
                        output_acroform[key] = source_acroform[key]
                # Add missing font entries in /DR node of source file
                if (pdfn('DR') in source_acroform.keys()) and (pdfn('Font') in source_acroform[pdfn('DR')].keys()):
                    if pdfn('Font') not in output_acroform[pdfn('DR')].keys():
                        # if output_acroform is missing entirely the /Font node under an existing /DR, simply add it
                        output_acroform[pdfn('DR')][pdfn('Font')] = source_acroform[pdfn('DR')][pdfn('Font')]
                    else:
                        # else add new fonts only
                        for font_key in source_acroform[pdfn('DR')][pdfn('Font')].keys():
                            if font_key not in output_acroform[pdfn('DR')][pdfn('Font')]:
                                output_acroform[pdfn('DR')][pdfn('Font')][font_key] = source_acroform[pdfn('DR')][pdfn('Font')][font_key]
            if pdfn('Fields') not in output_acroform:
                output_acroform[pdfn('Fields')] = output_formfields
            else:
                # Add new fields
                output_acroform[pdfn('Fields')] += output_formfields
        num +=1
    output.trailer[pdfn('Root')][pdfn('AcroForm')] = output_acroform
    output_stream = io.BytesIO()
    output.write(output_stream)
    return output_stream.getvalue()

def create_watermark(text):
    packet = io.BytesIO()
    # Create a PDF with ReportLab
    can = canvas.Canvas(packet, pagesize=A3)
    
    # Set up the watermark style
    can.setFont("Helvetica", 11)
    can.setFillColorRGB(0.5, 0.5, 0.5, 0.3)  # Light grey color, 30% transparency
    
    # Split the text into multiple lines (using '\n' as delimiter)
    # Introduce a newline character after approximately 30 characters
    text_with_newlines = ''
    char_count = 0
    words = text.split()
    
    for word in words:
        if char_count + len(word) > 25:
            text_with_newlines += '\n'
            char_count = 0
        text_with_newlines += word + ' '
        char_count += len(word) + 1
    
    text = text_with_newlines.strip()
    text_lines = text.split('\n')
    
    # Get the width and height of the page
    width, height = A3

    # Set text at 45º and repeat across the page with adjusted spacing
    horizontal_spacing = 140  # Adjusted horizontal spacing to better fit the width
    vertical_spacing = 140    # Adjusted vertical spacing for balance
    for x in range(0, int(width) + horizontal_spacing, horizontal_spacing):  # Adjust spacing in x-direction
        for y in range(0, int(height) + vertical_spacing, vertical_spacing):  # Adjust spacing in y-direction
            can.saveState()  # Save the current state of the canvas
            can.translate(x, y)  # Move the origin to the (x, y) position
            can.rotate(45)  # Rotate the text by 45 degrees

            # Draw each line of the text with appropriate vertical spacing
            line_height = 15  # Adjust the line height to control the space between lines
            for i, line in enumerate(text_lines):
                can.drawCentredString(0, -i * line_height, line)  # Draw each line offset vertically
            
            can.restoreState()  # Restore the canvas state (no rotation, no translation)
    
    can.save()

    # Move to the beginning of the BytesIO buffer
    packet.seek(0)
    return PdfReader(packet)

# Function to apply watermark to all pages
def add_watermark_to_pdf(pdf, watermark_text):
    # Read the original PDF
    input_pdf = PdfReader(io.BytesIO(pdf))
    output_pdf = PdfWriter()

    # Create watermark PDF
    watermark_pdf = create_watermark(watermark_text)
    watermark_page = watermark_pdf.pages[0]

    # Apply watermark to each page
    for page in input_pdf.pages:
        page.merge_page(watermark_page)
        output_pdf.add_page(page)

    # Write the output to a BytesIO object
    output_bytes = io.BytesIO()
    output_pdf.write(output_bytes)
    output_bytes.seek(0)

    # Return the bytes
    return output_bytes.getvalue()