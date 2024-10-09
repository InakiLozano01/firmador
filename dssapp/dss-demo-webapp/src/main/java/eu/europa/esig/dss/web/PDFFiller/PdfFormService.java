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

// Import necessary classes
import com.itextpdf.kernel.colors.DeviceRgb;
import com.itextpdf.kernel.pdf.canvas.PdfCanvas;

@Service
public class PdfFormService {

    private static final Logger logger = LoggerFactory.getLogger(PdfFormService.class);

    public ByteArrayOutputStream updatePdfFields(byte[] pdfBytes, Map<String, String> fieldValues) {
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        PdfDocument pdfDoc = null;

        try {
            PdfReader reader = new PdfReader(new ByteArrayInputStream(pdfBytes));
            PdfWriter writer = new PdfWriter(baos);
            StampingProperties stampingProperties = new StampingProperties().preserveEncryption().useAppendMode();

            pdfDoc = new PdfDocument(reader, writer, stampingProperties);
            PdfAcroForm form = PdfAcroForm.getAcroForm(pdfDoc, true);

            for (Map.Entry<String, PdfFormField> entry : form.getAllFormFields().entrySet()) {
                String fieldName = entry.getKey();
                PdfFormField field = entry.getValue();

                if (!PdfName.Sig.equals(field.getFormType())) {
                    if (fieldValues.containsKey(fieldName)) {
                        Object value = fieldValues.get(fieldName);
                        field.setValue(String.valueOf(value));
                        /*field.setFieldFlag(PdfFormField.FF_READ_ONLY, true);
                        field.setReadOnly(true);*/

                        // Modify field appearance without generating new content
                        for (PdfWidgetAnnotation widget : field.getWidgets()) {
                            // Remove border
                            PdfDictionary borderStyle = new PdfDictionary();
                            borderStyle.put(PdfName.W, new PdfNumber(0));
                            widget.setBorderStyle(borderStyle);

                            // Set no highlight
                            widget.setHighlightMode(PdfAnnotation.HIGHLIGHT_NONE);

                            // Remove appearance characteristics
                            widget.setAppearanceCharacteristics(null);
                            // Force appearance generation
                            field.regenerateField();
                        }

                        logger.info("Updated field: {} with value: {}", fieldName, value);
                    }
                } else {
                    logger.info("Skipping signature field: {}", fieldName);
                }
            }
        } catch (Exception e) {
            logger.error("Error updating PDF form fields", e);
            throw new PdfFormUpdateException("Error updating PDF form fields", e);
        } finally {
            if (pdfDoc != null) {
                pdfDoc.close();
            }
        }

        return baos;
    }
}