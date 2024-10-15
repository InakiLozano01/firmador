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
        if pdfn('AcroForm') in input[pdfn('Root')].keys(): 
            source_acroform = input[pdfn('Root')][pdfn('AcroForm')]
            if pdfn('Fields') in source_acroform:
                output_formfields = source_acroform[pdfn('Fields')]
            else:
                output_formfields = []
            num2 = 0
            for form_field in output_formfields:
                key = pdfn('T')
                old_name = form_field[key].replace('(','').replace(')','') 
                form_field[key] = 'FILE_{n}_FIELD_{m}_{on}'.format(n=num, m=num2, on=old_name)
                num2 += 1
            if output_acroform == None:
                output_acroform = source_acroform
            else:
                for key in source_acroform.keys():
                    if key not in output_acroform:
                        output_acroform[key] = source_acroform[key]
                if (pdfn('DR') in source_acroform.keys()) and (pdfn('Font') in source_acroform[pdfn('DR')].keys()):
                    if pdfn('Font') not in output_acroform[pdfn('DR')].keys():
                        output_acroform[pdfn('DR')][pdfn('Font')] = source_acroform[pdfn('DR')][pdfn('Font')]
                    else:
                        for font_key in source_acroform[pdfn('DR')][pdfn('Font')].keys():
                            if font_key not in output_acroform[pdfn('DR')][pdfn('Font')]:
                                output_acroform[pdfn('DR')][pdfn('Font')][font_key] = source_acroform[pdfn('DR')][pdfn('Font')][font_key]
            if pdfn('Fields') not in output_acroform:
                output_acroform[pdfn('Fields')] = output_formfields
            else:
                output_acroform[pdfn('Fields')] += output_formfields
        num +=1
    output.trailer[pdfn('Root')][pdfn('AcroForm')] = output_acroform
    output_stream = io.BytesIO()
    output.write(output_stream)
    return output_stream.getvalue()

def create_watermark(text):
    packet = io.BytesIO()

    # Crear PDF con ReportLab
    can = canvas.Canvas(packet, pagesize=A3)
    
    # Estilo de la marca de agua
    can.setFont("Helvetica", 11)
    can.setFillColorRGB(0.5, 0.5, 0.5, 0.3)
    
    # Dividir el texto en multilinea (usando '\n' como delimitador)
    # Agregar salto de linea si la longitud de la linea excede 25 caracteres1
    text_with_newlines = ''
    cantidad_caracteres = 25
    char_count = 0
    words = text.split()
    
    for word in words:
        if char_count + len(word) > cantidad_caracteres:
            text_with_newlines += '\n'
            char_count = 0
        text_with_newlines += word + ' '
        char_count += len(word) + 1
    
    text = text_with_newlines.strip()
    text_lines = text.split('\n')
    
    # Ancho y alto de la página
    width, height = A3

    # Texto a 45º y repetir por toda la pagina ajustando espacios
    horizontal_spacing = 140  # Espaciado horizontal
    vertical_spacing = 140    # Espaciado vertical
    for x in range(0, int(width) + horizontal_spacing, horizontal_spacing):  # Espaciado en direccion x
        for y in range(0, int(height) + vertical_spacing, vertical_spacing):  # Espaciado en direccion y
            can.saveState()  # Guardar el estado actual del canvas
            can.translate(x, y)  # Mover el nuevo origen al punto (x, y)
            can.rotate(45)  # Rotar el canvas 45 grados

            line_height = 15  # Tamaño del salto de linea
            
            for i, line in enumerate(text_lines):
                can.drawCentredString(0, -i * line_height, line)
            
            can.restoreState()  # Restaurar el estado del canvas (sin rotacion)
    
    can.save()

    # Colocar al principio del buffer BytesIO
    packet.seek(0)
    return PdfReader(packet)


def add_watermark_to_pdf(pdf, watermark_text):
    # Leer el PDF de entrada
    input_pdf = PdfReader(io.BytesIO(pdf))
    output_pdf = PdfWriter()

    # Crear la marca de agua
    watermark_pdf = create_watermark(watermark_text)
    watermark_page = watermark_pdf.pages[0]

    # Aplicar la marca de agua a cada página del PDF de entrada
    for page in input_pdf.pages:
        page.merge_page(watermark_page)
        output_pdf.add_page(page)

    # Escribir la salida al objeto BytesIO
    output_bytes = io.BytesIO()
    output_pdf.write(output_bytes)
    output_bytes.seek(0)

    # Devolver el PDF con la marca de agua
    return output_bytes.getvalue()