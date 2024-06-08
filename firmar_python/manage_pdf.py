import fitz
import logging
from errors import PDFSignatureError

def check_and_prepare_pdf(pdf_bytes):
    try:
        pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # Verifica si hay firmas en el PDF
        x, y = calculate_position(pdf_bytes, pdf_doc.page_count - 1)
        output_stream = pdf_bytes

        # Si no hay firmas, añade una nueva página y establece las coordenadas iniciales
        if x==0 and y==0:
            pdf_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            pdf_doc.insert_page(pdf_doc.page_count)
            output_stream = pdf_doc.write()
            x, y = 20, 20

        return output_stream, x, y
    except Exception as e:
        logging.error(f"Error in check_and_prepare_pdf: {str(e)}")
        raise PDFSignatureError("Failed to prepare PDF for signing.")

def calculate_position(pdf_bytes, last_page_number):
    try:
        # Load the PDF document from bytes
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        last_page = pdf_document[last_page_number]

        # Initialize variables to track the last signature position
        last_y = 0
        has_signature = False
        sigs = 0
        margin = 20
        xspace, yspace = 10, 10
        sigwidth, sigheight = 185, 50

        # Iterate over the annotations to find signature fields
        for annot in last_page.annots():
            if annot.type[0] == 19:  # Check if the annotation is a signature (type 19)
                rect = annot.rect
                has_signature = True
                sigs += 1
                if rect.y1 > last_y:
                    last_y = rect.y1
                    last_height = rect.height

        if not has_signature:
            # Check for signature widgets in the page's contents
            for field in last_page.widgets():
                if field.field_type == fitz.PDF_WIDGET_TYPE_SIGNATURE:
                    rect = field.rect
                    has_signature = True
                    sigs += 1
                    if rect.y1 > last_y:
                        last_y = rect.y1
                        last_height = rect.height

        row = int (sigs / 3)
        col = sigs % 3

        if has_signature:
            # Calculate the new position
            x = margin + (col * (sigwidth + xspace))
            y = margin + (row * (sigheight + yspace))
            print(f"Signature found at {x}, {y}")
        else:
            x, y = 0, 0  # Indicate that no signatures were found

        if x + sigwidth > last_page.rect.width or y + sigheight > last_page.rect.height:
            raise PDFSignatureError("No more space for signatures in the last page. Cannot add page because signatures will be broken.")
        return x, y
    except Exception as e:
        logging.error(f"Error in calculate_position: {str(e)}")
        raise PDFSignatureError("Failed to calculate position for signature.")