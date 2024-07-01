package eu.europa.esig.dss.web.PDFFiller;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.Base64;
import org.springframework.web.multipart.MultipartFile;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/pdf")
public class PdfFormController {

    @Autowired
    private PdfFormService pdfFormUpdateService;

    @Autowired
    private ObjectMapper objectMapper; // For converting JSON string to Map

    @PostMapping(value = "/update", consumes = MediaType.APPLICATION_FORM_URLENCODED_VALUE)
    public ResponseEntity<byte[]> updatePdf(
            @RequestParam("fileBase64") String fileBase64,
            @RequestParam("fileName") String fileName,
            @RequestParam("fieldValues") String fieldValuesJson) {
        try {
            // Decode base64 PDF
            byte[] pdfBytes = Base64.getDecoder().decode(fileBase64);

            // Convert JSON string to Map
            Map<String, String> fieldValues = objectMapper.readValue(fieldValuesJson, Map.class);

            // Update the PDF fields
            ByteArrayOutputStream baos = pdfFormUpdateService.updatePdfFields(pdfBytes, fieldValues);

            // Prepare headers
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_PDF);
            // Suggest a filename for the browser to download
            headers.setContentDispositionFormData("attachment", fileName);

            return new ResponseEntity<>(baos.toByteArray(), headers, HttpStatus.OK);
        } catch (IOException e) {
            return new ResponseEntity<>(HttpStatus.INTERNAL_SERVER_ERROR);
        }
    }
}
