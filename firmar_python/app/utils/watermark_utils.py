from pdfrw import PdfReader as pdfr, PdfWriter as pdfw, PdfName as pdfn
import io
from PyPDF2 import PdfWriter, PdfReader
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A3
from ..exceptions.tool_exc import (
    WatermarkError,
    PDFReadError,
    PDFWriteError,
    WatermarkCreationError,
    PDFMergeError,
    InvalidPDFError,
    WatermarkTextError
)

def merge_pdf_files_pdfrw(pdf_bytes):
    """
    Merge multiple PDF files while preserving form fields.
    
    Args:
        pdf_bytes: List of PDF files in bytes format
        
    Returns:
        bytes: Merged PDF file
        
    Raises:
        PDFMergeError: If there's an error during PDF merging
        InvalidPDFError: If any of the input PDFs is invalid
    """
    try:
        output = pdfw()
        num = 0
        output_acroform = None
        
        for pdf in pdf_bytes:
            try:
                input_pdf = pdfr(fdata=pdf, verbose=False)
            except Exception as e:
                raise InvalidPDFError(f"Invalid PDF file at index {num}: {str(e)}")
                
            output.addpages(input_pdf.pages)
            
            if pdfn('AcroForm') in input_pdf[pdfn('Root')].keys():
                source_acroform = input_pdf[pdfn('Root')][pdfn('AcroForm')]
                output_formfields = source_acroform.get(pdfn('Fields'), [])
                
                # Rename form fields to avoid conflicts
                for num2, form_field in enumerate(output_formfields):
                    key = pdfn('T')
                    old_name = form_field[key].replace('(','').replace(')','')
                    form_field[key] = f'FILE_{num}_FIELD_{num2}_{old_name}'
                
                # Handle AcroForm merging
                if output_acroform is None:
                    output_acroform = source_acroform
                else:
                    # Merge AcroForm dictionaries
                    for key in source_acroform.keys():
                        if key not in output_acroform:
                            output_acroform[key] = source_acroform[key]
                    
                    # Handle font dictionaries
                    if (pdfn('DR') in source_acroform.keys()) and (pdfn('Font') in source_acroform[pdfn('DR')].keys()):
                        if pdfn('Font') not in output_acroform[pdfn('DR')].keys():
                            output_acroform[pdfn('DR')][pdfn('Font')] = source_acroform[pdfn('DR')][pdfn('Font')]
                        else:
                            for font_key in source_acroform[pdfn('DR')][pdfn('Font')].keys():
                                if font_key not in output_acroform[pdfn('DR')][pdfn('Font')]:
                                    output_acroform[pdfn('DR')][pdfn('Font')][font_key] = source_acroform[pdfn('DR')][pdfn('Font')][font_key]
                
                # Update fields
                if pdfn('Fields') not in output_acroform:
                    output_acroform[pdfn('Fields')] = output_formfields
                else:
                    output_acroform[pdfn('Fields')] += output_formfields
            
            num += 1
        
        output.trailer[pdfn('Root')][pdfn('AcroForm')] = output_acroform
        output_stream = io.BytesIO()
        output.write(output_stream)
        return output_stream.getvalue()
        
    except Exception as e:
        if isinstance(e, InvalidPDFError):
            raise
        raise PDFMergeError(f"Error merging PDF files: {str(e)}")

def create_watermark(text):
    """
    Create a watermark PDF with the given text.
    
    Args:
        text: Text to use as watermark
        
    Returns:
        PdfReader: Watermark PDF reader object
        
    Raises:
        WatermarkCreationError: If there's an error creating the watermark
        WatermarkTextError: If the watermark text is invalid
    """
    if not text or not isinstance(text, str):
        raise WatermarkTextError("Watermark text must be a non-empty string")
        
    try:
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=A3)
        
        # Watermark style
        can.setFont("Helvetica", 11)
        can.setFillColorRGB(0.5, 0.5, 0.5, 0.3)
        
        # Text processing for multiline
        text_with_newlines = ''
        char_limit = 25
        char_count = 0
        words = text.split()
        
        for word in words:
            if char_count + len(word) > char_limit:
                text_with_newlines += '\n'
                char_count = 0
            text_with_newlines += word + ' '
            char_count += len(word) + 1
        
        text = text_with_newlines.strip()
        text_lines = text.split('\n')
        
        # Page dimensions
        width, height = A3
        
        # Create watermark pattern
        horizontal_spacing = 140
        vertical_spacing = 140
        line_height = 15
        
        for x in range(0, int(width) + horizontal_spacing, horizontal_spacing):
            for y in range(0, int(height) + vertical_spacing, vertical_spacing):
                can.saveState()
                can.translate(x, y)
                can.rotate(45)
                
                for i, line in enumerate(text_lines):
                    can.drawCentredString(0, -i * line_height, line)
                
                can.restoreState()
        
        can.save()
        packet.seek(0)
        return PdfReader(packet)
        
    except Exception as e:
        raise WatermarkCreationError(f"Error creating watermark: {str(e)}")

def add_watermark_to_pdf(pdf, watermark_text):
    """
    Add watermark to a PDF file.
    
    Args:
        pdf: PDF file in bytes format
        watermark_text: Text to use as watermark
        
    Returns:
        bytes: PDF with watermark
        
    Raises:
        PDFReadError: If there's an error reading the PDF
        PDFWriteError: If there's an error writing the PDF
        WatermarkError: If there's any other watermark-related error
    """
    try:
        # Read input PDF
        input_pdf = PdfReader(io.BytesIO(pdf))
        output_pdf = PdfWriter()
        
        # Create watermark
        watermark_pdf = create_watermark(watermark_text)
        watermark_page = watermark_pdf.pages[0]
        
        # Apply watermark to each page
        for page in input_pdf.pages:
            page.merge_page(watermark_page)
            output_pdf.add_page(page)
        
        # Write output
        output_bytes = io.BytesIO()
        output_pdf.write(output_bytes)
        output_bytes.seek(0)
        return output_bytes.getvalue()
        
    except Exception as e:
        if isinstance(e, (WatermarkCreationError, WatermarkTextError)):
            raise
        elif isinstance(e, (ValueError, TypeError)):
            raise PDFReadError(f"Error reading PDF: {str(e)}")
        else:
            raise PDFWriteError(f"Error writing PDF: {str(e)}")
