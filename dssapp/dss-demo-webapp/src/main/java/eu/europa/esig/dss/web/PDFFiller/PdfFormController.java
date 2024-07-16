package eu.europa.esig.dss.web.PDFFiller;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import java.util.Base64;
import org.springframework.web.multipart.MultipartFile;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.RestController;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Base64;
import java.util.Map;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

@RestController
@RequestMapping("/pdf")
public class PdfFormController {

    @Autowired
    private PdfFormService pdfFormUpdateService;

    @Autowired
    private ObjectMapper objectMapper; // For converting JSON string to Map

    private static final Logger logger = LoggerFactory.getLogger(PdfFormController.class);

    @PostMapping(value = "/update", consumes = MediaType.APPLICATION_FORM_URLENCODED_VALUE)
    public ResponseEntity <byte[]> updatePdfFields(
            @RequestParam("fileBase64") String fileBase64,
            @RequestParam("fileName") String fileName,
            @RequestParam("fieldValues") String fieldValuesJson) {
        try {
            // Verifica si las entradas son nulas o vacías
            if (fileBase64 == null || fileBase64.isEmpty() || fieldValuesJson == null || fieldValuesJson.isEmpty()) {
                logger.error("Input data is null or empty");
                return ResponseEntity.badRequest().body("Input data is null or empty".getBytes());
            }

            // Decode base64 PDF
            byte[] pdfBytes = Base64.getDecoder().decode(fileBase64);

            // Convert JSON string to Map
            Map<String, Object> fieldValues = objectMapper.readValue(fieldValuesJson, new TypeReference<Map<String, Object>>() {});

            // Update the PDF fields
            ByteArrayOutputStream baos = pdfFormUpdateService.updatePdfFields(pdfBytes, fieldValues);

            return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=" + fileName)
                    .contentType(MediaType.APPLICATION_PDF)
                    .body(baos.toByteArray());
        } catch (PdfFormUpdateException e) {
            logger.error("Error updatePDFfields", e);
            return ResponseEntity.badRequest().body(e.getMessage().getBytes());
        } catch (IllegalArgumentException e) {
            logger.error("Error decoding Base64 PDF", e);
            return ResponseEntity.badRequest().body("Error decoding Base64 PDF".getBytes());
        } catch (IOException e) {
            logger.error("IO Exception", e);
            return ResponseEntity.status(500).body("Internal Server Error".getBytes());
        } catch (Exception e) {
            logger.error("Unexpected error", e);
            return ResponseEntity.status(500).body("Internal Server Error".getBytes());
        }
    }
}
