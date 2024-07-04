package eu.europa.esig.dss.web.PDFFiller;

import com.itextpdf.forms.PdfAcroForm;
import com.itextpdf.forms.fields.PdfFormField;
import com.itextpdf.kernel.pdf.*;
import com.itextpdf.kernel.pdf.annot.PdfAnnotation;
import com.itextpdf.kernel.pdf.annot.PdfWidgetAnnotation;
import org.springframework.stereotype.Service;
import org.springframework.http.ResponseEntity;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Map;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

@Service
public class PdfFormService {

    private static final Logger logger = LoggerFactory.getLogger(PdfFormService.class);

    public ByteArrayOutputStream updatePdfFields(byte[] pdfBytes, Map<String, Object> fieldValues) {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        PdfDocument pdfDoc = null;

        try {
            PdfReader reader = new PdfReader(new ByteArrayInputStream(pdfBytes));
            PdfWriter writer = new PdfWriter(baos);
            StampingProperties stampingProperties = new StampingProperties().useAppendMode();

            pdfDoc = new PdfDocument(reader, writer, stampingProperties);
            PdfAcroForm form = PdfAcroForm.getAcroForm(pdfDoc, true);

            for (Map.Entry<String, PdfFormField> entry : form.getAllFormFields().entrySet()) {
                String fieldName = entry.getKey();
                PdfFormField field = entry.getValue();

                if (!PdfName.Sig.equals(field.getFormType())) {
                    if (fieldValues.containsKey(fieldName)) {
                        Object valor = fieldValues.get(fieldName);
                        field.setValue(String.valueOf(valor));
                        field.setFieldFlag(PdfFormField.FF_READ_ONLY, true);

                        // Remove border and make non-editable
                        for (PdfWidgetAnnotation widget : field.getWidgets()) {
                            widget.setFlag(PdfAnnotation.PRINT);

                            // Remove border
                            PdfDictionary borderStyle = new PdfDictionary();
                            borderStyle.put(PdfName.W, new PdfNumber(0)); // Set border width to 0
                            widget.setBorderStyle(borderStyle);

                            // Set no highlight
                            widget.setHighlightMode(PdfAnnotation.HIGHLIGHT_NONE);

                            // Remove appearance characteristics
                            widget.setAppearanceCharacteristics(new PdfDictionary());
                            }

                        System.out.println("Updating field: " + fieldName + " with value: " + String.valueOf(fieldValues.get(fieldName)));
                    }
                } else {
                System.out.println("Skipping signature field: " + fieldName);
                }
            }
        } catch (IOException e) {
            logger.error("Error al actualizar campos del formulario PDF", e);
            throw new PdfFormUpdateException("Error al actualizar campos del formulario PDF", e);
        } catch (Exception e) {
            logger.error("Error inesperado al actualizar campos del formulario PDF", e);
            throw new PdfFormUpdateException("Error inesperado al actualizar campos del formulario PDF", e);
        } finally {
            if (pdfDoc != null) {
                pdfDoc.close();
            }
        }

        return baos;
    }
}
