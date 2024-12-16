from pdfrw import PdfReader as pdfr, PdfWriter as pdfw, PdfName as pdfn
import io
import logging
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

# Configure logging
logger = logging.getLogger(__name__)

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
    logger.info(f"Starting PDF merge for {len(pdf_bytes)} files")
    try:
        output = pdfw()
        num = 0
        output_acroform = None
        
        for pdf in pdf_bytes:
            logger.debug(f"Processing PDF {num + 1}/{len(pdf_bytes)}")
            try:
                input_pdf = pdfr(fdata=pdf, verbose=False)
                logger.debug(f"Successfully read PDF {num + 1}")
            except Exception as e:
                logger.error(f"Invalid PDF file at index {num}: {str(e)}", exc_info=True)
                raise InvalidPDFError(f"Invalid PDF file at index {num}: {str(e)}")
                
            output.addpages(input_pdf.pages)
            logger.debug(f"Added {len(input_pdf.pages)} pages from PDF {num + 1}")
            
            if pdfn('AcroForm') in input_pdf[pdfn('Root')].keys():
                logger.debug(f"Processing AcroForm for PDF {num + 1}")
                source_acroform = input_pdf[pdfn('Root')][pdfn('AcroForm')]
                
                # Get form fields safely
                output_formfields = []
                if pdfn('Fields') in source_acroform:
                    fields = source_acroform[pdfn('Fields')]
                    if isinstance(fields, list):
                        output_formfields = fields
                    else:
                        logger.warning(f"Unexpected Fields type in PDF {num + 1}: {type(fields)}")
                        continue
                
                # Rename form fields to avoid conflicts
                logger.debug(f"Renaming {len(output_formfields)} form fields")
                for num2, form_field in enumerate(output_formfields):
                    if not isinstance(form_field, dict):
                        continue
                    key = pdfn('T')
                    if key not in form_field:
                        continue
                    old_name = form_field[key].replace('(','').replace(')','')
                    form_field[key] = f'FILE_{num}_FIELD_{num2}_{old_name}'
                
                # Handle AcroForm merging
                if output_acroform is None:
                    logger.debug("Initializing output AcroForm")
                    output_acroform = source_acroform
                else:
                    logger.debug("Merging AcroForm dictionaries")
                    # Merge AcroForm dictionaries
                    for key in source_acroform.keys():
                        if key not in output_acroform:
                            output_acroform[key] = source_acroform[key]
                    
                    # Handle font dictionaries
                    if (pdfn('DR') in source_acroform.keys()) and (pdfn('Font') in source_acroform[pdfn('DR')].keys()):
                        logger.debug("Merging font dictionaries")
                        if pdfn('Font') not in output_acroform[pdfn('DR')].keys():
                            output_acroform[pdfn('DR')][pdfn('Font')] = source_acroform[pdfn('DR')][pdfn('Font')]
                        else:
                            for font_key in source_acroform[pdfn('DR')][pdfn('Font')].keys():
                                if font_key not in output_acroform[pdfn('DR')][pdfn('Font')]:
                                    output_acroform[pdfn('DR')][pdfn('Font')][font_key] = source_acroform[pdfn('DR')][pdfn('Font')][font_key]
                
                # Update fields
                if pdfn('Fields') not in output_acroform:
                    logger.debug("Initializing output fields")
                    output_acroform[pdfn('Fields')] = output_formfields
                else:
                    logger.debug("Appending form fields")
                    current_fields = output_acroform[pdfn('Fields')]
                    if isinstance(current_fields, list):
                        current_fields.extend(output_formfields)
                    else:
                        output_acroform[pdfn('Fields')] = output_formfields
            
            num += 1
        
        logger.debug("Writing merged PDF")
        if output_acroform is not None:
            output.trailer[pdfn('Root')][pdfn('AcroForm')] = output_acroform
        output_stream = io.BytesIO()
        output.write(output_stream)
        logger.info("PDF merge completed successfully")
        return output_stream.getvalue()
        
    except Exception as e:
        if isinstance(e, InvalidPDFError):
            raise
        logger.error(f"Error merging PDF files: {str(e)}", exc_info=True)
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
    logger.info("Starting watermark creation")
    if not text or not isinstance(text, str):
        logger.error("Invalid watermark text provided")
        raise WatermarkTextError("Watermark text must be a non-empty string")
        
    try:
        logger.debug("Creating watermark canvas")
        packet = io.BytesIO()
        can = canvas.Canvas(packet, pagesize=A3)
        
        # Watermark style
        can.setFont("Helvetica", 11)
        can.setFillColorRGB(0.5, 0.5, 0.5, 0.3)
        
        # Text processing for multiline
        logger.debug("Processing watermark text for multiline")
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
        logger.debug(f"Processed text into {len(text_lines)} lines")
        
        # Page dimensions
        width, height = A3
        
        # Create watermark pattern
        logger.debug("Creating watermark pattern")
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
        logger.info("Watermark created successfully")
        return PdfReader(packet)
        
    except Exception as e:
        logger.error(f"Error creating watermark: {str(e)}", exc_info=True)
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
    logger.info("Starting watermark addition process")
    try:
        # Read input PDF
        logger.debug("Reading input PDF")
        input_pdf = PdfReader(io.BytesIO(pdf))
        output_pdf = PdfWriter()
        
        # Create watermark
        logger.debug("Creating watermark")
        watermark_pdf = create_watermark(watermark_text)
        watermark_page = watermark_pdf.pages[0]
        
        # Apply watermark to each page
        logger.debug(f"Applying watermark to {len(input_pdf.pages)} pages")
        for i, page in enumerate(input_pdf.pages, 1):
            logger.debug(f"Processing page {i}/{len(input_pdf.pages)}")
            page.merge_page(watermark_page)
            output_pdf.add_page(page)
        
        # Write output
        logger.debug("Writing watermarked PDF")
        output_bytes = io.BytesIO()
        output_pdf.write(output_bytes)
        output_bytes.seek(0)
        logger.info("Watermark addition completed successfully")
        return output_bytes.getvalue()
        
    except Exception as e:
        if isinstance(e, (WatermarkCreationError, WatermarkTextError)):
            raise
        elif isinstance(e, (ValueError, TypeError)):
            logger.error(f"Error reading PDF: {str(e)}", exc_info=True)
            raise PDFReadError(f"Error reading PDF: {str(e)}")
        else:
            logger.error(f"Error writing PDF: {str(e)}", exc_info=True)
            raise PDFWriteError(f"Error writing PDF: {str(e)}")
