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

    // Accepts JSON payload for PDF update
    @PostMapping(value = "/update", consumes = MediaType.APPLICATION_JSON_VALUE)
    public ResponseEntity<byte[]> updatePdfFields(@RequestBody Map<String, Object> payload) {
        try {
            // Extract and validate the required fields
            String fileBase64 = (String) payload.get("fileBase64");
            String fileName = (String) payload.get("fileName");
            Map<String, String> fieldValues = (Map<String, String>) objectMapper.readValue(payload.get("fieldValues").toString(), Map.class);

            if (fileBase64 == null || fileBase64.isEmpty() || fieldValues == null || fieldValues.isEmpty()) {
                logger.error("Input data is null or empty");
                return ResponseEntity.badRequest().body("Input data is null or empty".getBytes());
            }
            
            // Decode the Base64-encoded PDF
            byte[] pdfBytes = Base64.getDecoder().decode(fileBase64);

            // Update PDF fields using the service
            ByteArrayOutputStream baos = pdfFormUpdateService.updatePdfFields(pdfBytes, fieldValues);

            // Return the updated PDF as a downloadable file
            return ResponseEntity.ok()
                    .header(HttpHeaders.CONTENT_DISPOSITION, "attachment; filename=" + fileName)
                    .contentType(MediaType.APPLICATION_PDF)
                    .body(baos.toByteArray());

        } catch (IllegalArgumentException e) {
            logger.error("Invalid input data", e);
            return ResponseEntity.badRequest().body("Invalid input data".getBytes());
        } catch (Exception e) {
            logger.error("Unexpected error", e);
            return ResponseEntity.status(500).body("Unexpected error occurred".getBytes());
        }
    }
}
