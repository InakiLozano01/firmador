package eu.europa.esig.dss.web.controller;

import org.springframework.context.annotation.Bean;
import org.springframework.web.bind.annotation.*;
import eu.europa.esig.dss.spi.validation.CommonCertificateVerifier;
import eu.europa.esig.dss.ws.dto.RemoteCertificate;
import eu.europa.esig.dss.ws.signature.dto.*;
import eu.europa.esig.dss.model.BLevelParameters;
import eu.europa.esig.dss.model.DSSDocument;
import eu.europa.esig.dss.model.InMemoryDocument;
import eu.europa.esig.dss.model.Policy;
import eu.europa.esig.dss.model.SignerLocation;
import eu.europa.esig.dss.model.ToBeSigned;
import eu.europa.esig.dss.model.x509.CertificateToken;
import eu.europa.esig.dss.pades.PAdESSignatureParameters;
import eu.europa.esig.dss.pades.SignatureFieldParameters;
import eu.europa.esig.dss.pades.SignatureImageParameters;
import eu.europa.esig.dss.pades.SignatureImageTextParameters;
import eu.europa.esig.dss.pades.signature.PAdESService;
import eu.europa.esig.dss.service.crl.OnlineCRLSource;
import eu.europa.esig.dss.service.ocsp.OnlineOCSPSource;
import java.awt.Color;
import java.io.ByteArrayInputStream;
import java.util.ArrayList;
import java.util.List;
import java.security.cert.CertificateException;
import java.security.cert.CertificateFactory;
import java.security.cert.X509Certificate;

/**
 * REST implementation of the remote signature service
 */
@RestController
@RequestMapping("/services/rest")
public class RestDocumentSignatureServiceImpl {

    @Bean
    public CommonCertificateVerifier commonCertificateVerifier() {
        CommonCertificateVerifier certificateVerifier = new CommonCertificateVerifier();
        certificateVerifier.setCrlSource(new OnlineCRLSource());
        certificateVerifier.setOcspSource(new OnlineOCSPSource());
        // certificateVerifier.setDataLoader(new CommonsDataLoader());
        return certificateVerifier;
    }

    private RemoteDocumentSignatureServiceImpl servicio = new RemoteDocumentSignatureServiceImpl(
            new CommonCertificateVerifier());

    private PAdESService service = (PAdESService) servicio.getPAdESService();

    @GetMapping("/serviceStatus")
    public String serviceStatus() {
        return "OK";
    }

    @PostMapping("/getDataToSign")
    public ToBeSigned getDataToSign(@RequestBody DataToSignOneDocumentDTO dataToSignDto) {
        DSSDocument toSignDocument = new InMemoryDocument(dataToSignDto.getToSignDocument().getBytes());
        PAdESSignatureParameters signatureParameters = new PAdESSignatureParameters();

        signatureParameters.setAppName(null);
        BLevelParameters bLevelParams = new BLevelParameters();
        bLevelParams.setClaimedSignerRoles(dataToSignDto.getParameters().getBLevelParams().getClaimedSignerRoles());
        SignerLocation signerLocation = new SignerLocation();
        signerLocation.setCountry(dataToSignDto.getParameters().getBLevelParams().getSignerLocationCountry());
        signerLocation.setLocality(dataToSignDto.getParameters().getBLevelParams().getSignerLocationLocality());
        signerLocation.setPostalCode(dataToSignDto.getParameters().getBLevelParams().getSignerLocationPostalCode());
        signerLocation
                .setStateOrProvince(dataToSignDto.getParameters().getBLevelParams().getSignerLocationStateOrProvince());
        signerLocation
                .setPostalAddress(dataToSignDto.getParameters().getBLevelParams().getSignerLocationPostalAddress());

        bLevelParams.setSignerLocation(signerLocation);
        Policy policy = new Policy();
        policy.setDigestAlgorithm(dataToSignDto.getParameters().getBLevelParams().getPolicyDigestAlgorithm());
        policy.setDigestValue(dataToSignDto.getParameters().getBLevelParams().getPolicyDigestValue());
        policy.setId(dataToSignDto.getParameters().getBLevelParams().getPolicyId());
        policy.setDescription(dataToSignDto.getParameters().getBLevelParams().getPolicyDescription());
        policy.setQualifier(dataToSignDto.getParameters().getBLevelParams().getPolicyQualifier());
        policy.setSpuri(dataToSignDto.getParameters().getBLevelParams().getPolicySpuri());
        bLevelParams.setClaimedSignerRoles(dataToSignDto.getParameters().getBLevelParams().getClaimedSignerRoles());
        bLevelParams.setSignedAssertions(dataToSignDto.getParameters().getBLevelParams().getSignedAssertions());
        bLevelParams.setSigningDate(dataToSignDto.getParameters().getBLevelParams().getSigningDate());
        bLevelParams.setTrustAnchorBPPolicy(true);
        bLevelParams.setSignaturePolicy(policy);

        signatureParameters.setBLevelParams(bLevelParams);
        SignatureImageParameters imageParameters = new SignatureImageParameters();
        if (dataToSignDto.getParameters().getImageParameters().getImage() != null) {
            DSSDocument image = new InMemoryDocument(
                    dataToSignDto.getParameters().getImageParameters().getImage().getBytes());
            image.setName(dataToSignDto.getParameters().getImageParameters().getImage().getName());
            imageParameters
                    .setImage(image);
        }
        imageParameters
                .setAlignmentHorizontal(dataToSignDto.getParameters().getImageParameters().getAlignmentHorizontal());
        imageParameters.setAlignmentVertical(dataToSignDto.getParameters().getImageParameters().getAlignmentVertical());

        /*
         * Color color = new
         * Color(dataToSignDto.getParameters().getImageParameters().getBackgroundColor()
         * .getRed(),
         * dataToSignDto.getParameters().getImageParameters().getBackgroundColor().
         * getGreen(),
         * dataToSignDto.getParameters().getImageParameters().getBackgroundColor().
         * getBlue(), dataToSignDto
         * .getParameters().getImageParameters().getBackgroundColor().getAlpha());
         */
        Color color = new Color(255, 255, 255, 255);
        imageParameters.setBackgroundColor(color);
        imageParameters.setDpi(dataToSignDto.getParameters().getImageParameters().getDpi());
        SignatureFieldParameters fieldParameters = new SignatureFieldParameters();
        fieldParameters
                .setFieldId(dataToSignDto.getParameters().getImageParameters().getFieldParameters().getFieldId());
        fieldParameters.setPage(dataToSignDto.getParameters().getImageParameters().getFieldParameters().getPage());
        fieldParameters.setHeight(dataToSignDto.getParameters().getImageParameters().getFieldParameters().getHeight());
        fieldParameters.setWidth(dataToSignDto.getParameters().getImageParameters().getFieldParameters().getWidth());
        fieldParameters
                .setOriginX(dataToSignDto.getParameters().getImageParameters().getFieldParameters().getOriginX());
        fieldParameters
                .setOriginY(dataToSignDto.getParameters().getImageParameters().getFieldParameters().getOriginY());
        fieldParameters.setRotation(null);
        imageParameters.setFieldParameters(fieldParameters);
        imageParameters.setImageScaling(dataToSignDto.getParameters().getImageParameters().getImageScaling());
        SignatureImageTextParameters textParameters = new SignatureImageTextParameters();
        imageParameters.setTextParameters(textParameters);
        imageParameters.setZoom(dataToSignDto.getParameters().getImageParameters().getZoom());
        signatureParameters.setDigestAlgorithm(dataToSignDto.getParameters().getDigestAlgorithm());
        signatureParameters.setEncryptionAlgorithm(dataToSignDto.getParameters().getEncryptionAlgorithm());
        signatureParameters.setSignaturePackaging(dataToSignDto.getParameters().getSignaturePackaging());
        signatureParameters.setSignatureLevel(dataToSignDto.getParameters().getSignatureLevel());
        signatureParameters.setImageParameters(imageParameters);
        List<RemoteCertificate> remoteCertificates = dataToSignDto.getParameters().getCertificateChain();
        CertificateFactory certificateFactory = null;
        try {
            certificateFactory = CertificateFactory.getInstance("X.509");
        } catch (CertificateException e) {
            // Handle the exception
            e.printStackTrace();
        }

        List<CertificateToken> certificates = new ArrayList<>();

        for (RemoteCertificate remoteCertificate : remoteCertificates) {
            byte[] encodedCertificate = remoteCertificate.getEncodedCertificate();
            try {
                X509Certificate x509Certificate = (X509Certificate) certificateFactory
                        .generateCertificate(new ByteArrayInputStream(encodedCertificate));
                CertificateToken certificateToken = new CertificateToken(x509Certificate);
                certificates.add(certificateToken);
            } catch (CertificateException e) {
                // Handle the exception
                e.printStackTrace();
            }
        }
        signatureParameters.setSigningCertificate(certificates.get(0));
        signatureParameters.setCertificateChain(certificates);
        // Set the necessary parameters for the signatureParameters object
        // ...
        return service.getDataToSign(toSignDocument, signatureParameters);
    }
}
