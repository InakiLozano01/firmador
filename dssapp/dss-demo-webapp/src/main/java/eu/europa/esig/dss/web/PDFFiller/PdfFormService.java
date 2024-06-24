package eu.europa.esig.dss.web.PDFFiller;

import com.itextpdf.forms.PdfAcroForm;
import com.itextpdf.forms.fields.PdfFormField;
import com.itextpdf.kernel.pdf.*;
import com.itextpdf.kernel.pdf.annot.PdfAnnotation;
import com.itextpdf.kernel.pdf.annot.PdfWidgetAnnotation;
import org.springframework.stereotype.Service;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Map;

@Service
public class PdfFormService {

    public ByteArrayOutputStream updatePdfFields(byte[] pdfBytes, Map<String, String> fieldValues) throws IOException {
        PdfReader reader = new PdfReader(new ByteArrayInputStream(pdfBytes));
        ByteArrayOutputStream baos = new ByteArrayOutputStream();
        PdfWriter writer = new PdfWriter(baos);
        StampingProperties stampingProperties = new StampingProperties().useAppendMode();

        PdfDocument pdfDoc = new PdfDocument(reader, writer, stampingProperties);
        PdfAcroForm form = PdfAcroForm.getAcroForm(pdfDoc, true);

        for (Map.Entry<String, PdfFormField> entry : form.getAllFormFields().entrySet()) {
            String fieldName = entry.getKey();
            PdfFormField field = entry.getValue();

            if (!PdfName.Sig.equals(field.getFormType())) {
                if (fieldValues.containsKey(fieldName)) {
                    field.setValue(fieldValues.get(fieldName));
                    field.setFieldFlag(PdfFormField.FF_READ_ONLY, true);

                    // Remove border and make non-editable
                    for (PdfWidgetAnnotation widget : field.getWidgets()) {
                        widget.setFlag(PdfAnnotation.PRINT);

                        // Remove border
                        PdfDictionary borderStyle = new PdfDictionary();
                        borderStyle.put(PdfName.W, new PdfNumber(0)); // Set border width to 0
                        borderStyle.put(PdfName.Width, new PdfNumber(0)); // Set border width to 0
                        widget.setBorderStyle(borderStyle);

                        // Set no highlight
                        widget.setHighlightMode(PdfAnnotation.HIGHLIGHT_NONE);

                        PdfDictionary appearanceCharacteristics = widget.getAppearanceCharacteristics();
                        if (appearanceCharacteristics == null) {
                            appearanceCharacteristics = new PdfDictionary();
                        }
                        appearanceCharacteristics.put(PdfName.BC, new PdfArray(new float[] {1, 1, 1, 0})); // Transparent border color
                        appearanceCharacteristics.put(PdfName.BG, new PdfArray(new float[] {1, 1, 1, 0})); // Transparent background color
                        widget.setAppearanceCharacteristics(appearanceCharacteristics);

                        // Ensure the appearance stream is properly set
                        PdfDictionary mk = widget.getAppearanceCharacteristics();
                        if (mk != null) {
                            mk.put(PdfName.BC, new PdfArray(new float[] {1, 1, 1, 0}));
                            mk.put(PdfName.BG, new PdfArray(new float[] {1, 1, 1, 0}));
                        }

                        // Clear any additional border appearance settings
                        widget.getPdfObject().remove(PdfName.BS);
                        widget.getPdfObject().remove(PdfName.Border);
                        widget.getPdfObject().remove(PdfName.CA);
                        widget.getPdfObject().remove(PdfName.MK);
                    }

                    System.out.println("Updating field: " + fieldName + " with value: " + fieldValues.get(fieldName));
                }
            } else {
                System.out.println("Skipping signature field: " + fieldName);
            }
        }

        pdfDoc.close();
        return baos;
    }
}
