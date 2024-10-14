package eu.europa.esig.dss.web.service;

import eu.europa.esig.dss.AbstractSignatureParameters;
import eu.europa.esig.dss.asic.cades.ASiCWithCAdESSignatureParameters;
import eu.europa.esig.dss.asic.cades.ASiCWithCAdESTimestampParameters;
import eu.europa.esig.dss.asic.cades.signature.ASiCWithCAdESService;
import eu.europa.esig.dss.asic.xades.ASiCWithXAdESSignatureParameters;
import eu.europa.esig.dss.asic.xades.signature.ASiCWithXAdESService;
import eu.europa.esig.dss.cades.CAdESSignatureParameters;
import eu.europa.esig.dss.cades.signature.CAdESCounterSignatureParameters;
import eu.europa.esig.dss.cades.signature.CAdESService;
import eu.europa.esig.dss.cades.signature.CAdESTimestampParameters;
import eu.europa.esig.dss.enumerations.*;
import eu.europa.esig.dss.jades.JAdESSignatureParameters;
import eu.europa.esig.dss.jades.JAdESTimestampParameters;
import eu.europa.esig.dss.jades.signature.JAdESCounterSignatureParameters;
import eu.europa.esig.dss.jades.signature.JAdESService;
import eu.europa.esig.dss.model.*;
import eu.europa.esig.dss.model.x509.CertificateToken;
import eu.europa.esig.dss.pades.*;
import eu.europa.esig.dss.pades.signature.PAdESService;
import eu.europa.esig.dss.service.tsp.OnlineTSPSource;
import eu.europa.esig.dss.signature.CounterSignatureService;
import eu.europa.esig.dss.signature.DocumentSignatureService;
import eu.europa.esig.dss.signature.MultipleDocumentsSignatureService;
import eu.europa.esig.dss.spi.DSSUtils;
import eu.europa.esig.dss.spi.x509.tsp.KeyEntityTSPSource;
import eu.europa.esig.dss.spi.x509.tsp.TSPSource;
import eu.europa.esig.dss.utils.Utils;
import eu.europa.esig.dss.spi.x509.tsp.TimestampToken;
import eu.europa.esig.dss.web.WebAppUtils;
import eu.europa.esig.dss.web.exception.SignatureOperationException;
import eu.europa.esig.dss.web.model.AbstractSignatureForm;
import eu.europa.esig.dss.web.model.ContainerDocumentForm;

import eu.europa.esig.dss.web.model.ExtensionForm;
import eu.europa.esig.dss.web.model.SignatureDocumentForm;

import eu.europa.esig.dss.web.model.TimestampForm;
import eu.europa.esig.dss.xades.XAdESSignatureParameters;
import eu.europa.esig.dss.xades.XAdESTimestampParameters;
import eu.europa.esig.dss.xades.signature.XAdESCounterSignatureParameters;
import eu.europa.esig.dss.xades.signature.XAdESService;
import org.apache.pdfbox.pdmodel.PDDocument;
import org.apache.pdfbox.pdmodel.PDPage;
import org.apache.pdfbox.pdmodel.common.PDRectangle;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotation;
import org.apache.pdfbox.pdmodel.interactive.annotation.PDAnnotationWidget;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Component;

import eu.europa.esig.dss.enumerations.SignatureForm;
import eu.europa.esig.dss.model.InMemoryDocument;


import java.awt.*;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.util.Collections;
import java.util.LinkedList;
import java.util.List;

@Component
public class SigningService {

	private static final Logger LOG = LoggerFactory.getLogger(SigningService.class);

	@Autowired
	private CAdESService cadesService;

	@Autowired
	private PAdESService padesService;

	@Autowired
	private XAdESService xadesService;

	@Autowired
	private JAdESService jadesService;

	@Autowired
	private ASiCWithCAdESService asicWithCAdESService;

	@Autowired
	private ASiCWithXAdESService asicWithXAdESService;

	@Autowired
	private TSPSource tspSource = new OnlineTSPSource("https://freetsa.org/tsr");


	private DSSDocument originalDoc;

	public boolean isMockTSPSourceUsed() {
		return tspSource instanceof KeyEntityTSPSource;
	}

	@SuppressWarnings({ "rawtypes", "unchecked" })
	public DSSDocument extend(ExtensionForm extensionForm) {
		LOG.info("Start extend signature");

		ASiCContainerType containerType = extensionForm.getContainerType();
		SignatureForm signatureForm = extensionForm.getSignatureForm();

		DSSDocument signedDocument = WebAppUtils.toDSSDocument(extensionForm.getSignedFile());
		List<DSSDocument> originalDocuments = WebAppUtils.toDSSDocuments(extensionForm.getOriginalFiles());

		DocumentSignatureService service = getSignatureService(containerType, signatureForm);

		AbstractSignatureParameters parameters = getSignatureParameters(containerType, signatureForm);
		parameters.setSignatureLevel(extensionForm.getSignatureLevel());

		if (Utils.isCollectionNotEmpty(originalDocuments)) {
			parameters.setDetachedContents(originalDocuments);
		}

		DSSDocument extendDocument = service.extendDocument(signedDocument, parameters);
		LOG.info("End extend signature");
		return extendDocument;
	}

	@SuppressWarnings({ "rawtypes", "unchecked" })
	public ToBeSigned getDataToSign(SignatureDocumentForm form) {
		LOG.info("Start getDataToSign with one document");
		DocumentSignatureService service = getSignatureService(form.getContainerType(), form.getSignatureForm());
		this.originalDoc = WebAppUtils.toDSSDocument(form.getDocumentToSign());
		AbstractSignatureParameters parameters = fillParameters(form);

		try {
			DSSDocument toSignDocument = originalDoc;
			ToBeSigned toBeSigned = service.getDataToSign(toSignDocument, parameters);
			LOG.info("End getDataToSign with one document");
			return toBeSigned;
		} catch (Exception e) {
			throw new SignatureOperationException(e.getMessage(), e);
		}
	}


	@SuppressWarnings({ "rawtypes", "unchecked" })
	public TimestampToken getContentTimestamp(SignatureDocumentForm form) {
		LOG.info("Start getContentTimestamp with one document");

		DocumentSignatureService service = getSignatureService(form.getContainerType(), form.getSignatureForm());
		AbstractSignatureParameters parameters = fillParameters(form);

		try {
			DSSDocument toSignDocument = WebAppUtils.toDSSDocument(form.getDocumentToSign());
			TimestampToken contentTimestamp = service.getContentTimestamp(toSignDocument, parameters);

			LOG.info("End getContentTimestamp with one document");
			return contentTimestamp;

		} catch (Exception e) {
			throw new SignatureOperationException(e.getMessage(), e);
		}
	}

	public DSSDocument timestamp(TimestampForm form) {
		List<DSSDocument> dssDocuments = WebAppUtils.toDSSDocuments(form.getOriginalFiles());
		LOG.info("Start timestamp with {} document(s)", dssDocuments.size());

		DSSDocument result;
		ASiCContainerType containerType = form.getContainerType();
		if (containerType == null) {
			if (dssDocuments.size() > 1) {
				throw new DSSException("Only one document is allowed for PAdES");
			}
			DSSDocument toTimestampDocument = dssDocuments.get(0);
			result = padesService.timestamp(toTimestampDocument, new PAdESTimestampParameters());
		} else {
			ASiCWithCAdESTimestampParameters parameters = new ASiCWithCAdESTimestampParameters();
			parameters.aSiC().setContainerType(containerType);
			result = asicWithCAdESService.timestamp(dssDocuments, parameters);
		}

		LOG.info("End timestamp with {} document(s)", dssDocuments.size());
		return result;
	}

	@SuppressWarnings({ "rawtypes" })
	private AbstractSignatureParameters fillParameters(SignatureDocumentForm form) {
		AbstractSignatureParameters parameters = getSignatureParameters(form.getContainerType(), form.getSignatureForm());
		parameters.setSignaturePackaging(form.getSignaturePackaging());

		fillParameters(parameters, form);

		return parameters;
	}

	private void fillParameters(AbstractSignatureParameters parameters, AbstractSignatureForm form) {
		parameters.setSignatureLevel(form.getSignatureLevel());
		parameters.setDigestAlgorithm(form.getDigestAlgorithm());
		// parameters.setEncryptionAlgorithm(form.getEncryptionAlgorithm()); retrieved from certificate
		parameters.bLevel().setSigningDate(form.getSigningDate());
		parameters.setSignWithExpiredCertificate(form.isSignWithExpiredCertificate());
		if (form.getContentTimestamp() != null) {
			parameters.setContentTimestamps(Collections.singletonList(WebAppUtils.toTimestampToken(form.getContentTimestamp())));
		}
		CertificateToken signingCertificate = DSSUtils.loadCertificate(form.getCertificate());
		parameters.setSigningCertificate(signingCertificate);
		List<byte[]> certificateChainBytes = form.getCertificateChain();
		if (Utils.isCollectionNotEmpty(certificateChainBytes)) {
			List<CertificateToken> certificateChain = new LinkedList<>();
			for (byte[] certificate : certificateChainBytes) {
				certificateChain.add(DSSUtils.loadCertificate(certificate));
			}
			parameters.setCertificateChain(certificateChain);
		}

            // Calculate signature field position
            SignatureFieldParameters fieldParameters = calculateSignatureFieldPosition();

            // Set signature field position and size on the original document
            SignatureImageParameters imageParameters = new SignatureImageParameters();
            imageParameters.setFieldParameters(fieldParameters);

            // Set text parameters
            SignatureImageTextParameters textParameters = new SignatureImageTextParameters();
            String subjectName = signingCertificate.getSubject().getRFC2253().substring(3);
            int index = subjectName.indexOf(",C=");
            if (index != -1) {
                subjectName = subjectName.substring(0, index);
            }
            textParameters.setText("Signed by: " + subjectName + "\n" + "Date: " + form.getSigningDate());
            textParameters.setFont(new DSSJavaFont(Font.SERIF, 7));
            textParameters.setSignerTextPosition(SignerTextPosition.LEFT);
            imageParameters.setTextParameters(textParameters);

            //Add timestamp (commented for now)
            padesService.setTspSource(tspSource);


            if (parameters instanceof PAdESSignatureParameters) {
                ((PAdESSignatureParameters) parameters).setImageParameters(imageParameters);
            }

		fillTimestampParameters(parameters, form);
	}

	private SignatureFieldParameters calculateSignatureFieldPosition() {
		try (PDDocument document = PDDocument.load(originalDoc.openStream())) {
			int lastPageNumber = document.getNumberOfPages();
			PDPage lastPage = document.getPage(lastPageNumber - 1);
			List<PDAnnotation> annotations = lastPage.getAnnotations();

			// Set the dimensions of the signature fields
			float signatureWidth = 170;
			float signatureHeight = 50;
			float xSpacing = 20; // spacing between signature fields
			float ySpacing = 20; // spacing between signature fields
			float margin = 20; // margin from page edges
			int signaturesPerRow = 3;

			// Count only signature annotations
			int signatureCount = (int) annotations.stream()
					.filter(ann -> ann instanceof PDAnnotationWidget)
					.count();

			if (signatureCount == 0) {
				// No previous signatures on the last page, add a new page for the first signature
				PDPage newPage = new PDPage();
				document.addPage(newPage);
				lastPage = newPage;
				lastPageNumber++;
			}

			// Calculate row and column for the new signature
			int row = signatureCount / signaturesPerRow;
			int col = signatureCount % signaturesPerRow;

			// Calculate new x and y positions
			float newOriginX = margin + (col * (signatureWidth + xSpacing));
			float newOriginY = margin + (row * (signatureHeight + ySpacing));

			// Get page dimensions
			PDRectangle pageSize = lastPage.getMediaBox();
			float pageWidth = pageSize.getWidth();
			float pageHeight = pageSize.getHeight();

			// Check if new signature will fit horizontally on the current page
			if (newOriginX + signatureWidth > pageWidth) {
				// Move to the next row if not enough space in the current row
				col = 0;
				row++;
				newOriginX = margin;
				newOriginY = margin + (row * (signatureHeight + ySpacing));
			}

			// Check if new signature will fit vertically on the current page
			if (newOriginY + signatureHeight > pageHeight) {
				// Not enough space, add a new page
				PDPage newPage = new PDPage();
				document.addPage(newPage);
				lastPageNumber++;
				row = 0;
				newOriginX = margin;
				newOriginY = margin;
			}

			SignatureFieldParameters fieldParameters = new SignatureFieldParameters();
			fieldParameters.setPage(lastPageNumber);
			fieldParameters.setOriginX(newOriginX);
			fieldParameters.setOriginY(newOriginY);
			fieldParameters.setWidth(signatureWidth);
			fieldParameters.setHeight(signatureHeight);

			// Save the document if a new page has been added or it's the first signature
			if (row == 0 && col == 0) {
				ByteArrayOutputStream baos = new ByteArrayOutputStream();
				document.save(baos);
				originalDoc = new InMemoryDocument(baos.toByteArray());
			}

			return fieldParameters;
		} catch (IOException e) {
			throw new RuntimeException("Error analyzing PDF document", e);
		}
	}


	@SuppressWarnings({ "rawtypes", "unchecked" })
	private void fillTimestampParameters(AbstractSignatureParameters parameters, AbstractSignatureForm form) {
		SignatureForm signatureForm = form.getSignatureForm();

		ASiCContainerType containerType = null;
		if (form instanceof ContainerDocumentForm) {
			containerType = ((ContainerDocumentForm) form).getContainerType();
		}

		TimestampParameters timestampParameters = getTimestampParameters(containerType, signatureForm);
		timestampParameters.setDigestAlgorithm(form.getDigestAlgorithm());

		parameters.setContentTimestampParameters(timestampParameters);
		parameters.setSignatureTimestampParameters(timestampParameters);
		parameters.setArchiveTimestampParameters(timestampParameters);
	}


	@SuppressWarnings({ "rawtypes", "unchecked" })
	public DSSDocument signDocument(SignatureDocumentForm form) {
		LOG.info("Start signDocument with one document");
		DocumentSignatureService service = getSignatureService(form.getContainerType(), form.getSignatureForm());


		this.originalDoc = WebAppUtils.toDSSDocument(form.getDocumentToSign());
		AbstractSignatureParameters parameters = fillParameters(form);

		try {
			//DSSDocument toSignDocument = WebAppUtils.toDSSDocument(form.getDocumentToSign());
			SignatureAlgorithm sigAlgorithm = SignatureAlgorithm.getAlgorithm(form.getEncryptionAlgorithm(), form.getDigestAlgorithm());
			SignatureValue signatureValue = new SignatureValue(sigAlgorithm, form.getSignatureValue());
			DSSDocument signedDocument = service.signDocument(originalDoc, parameters, signatureValue);
			LOG.info("End signDocument with one document");
			return signedDocument;
		} catch (Exception e) {
			throw new SignatureOperationException(e.getMessage(), e);
		}
	}

	@SuppressWarnings("rawtypes")
	private DocumentSignatureService getSignatureService(ASiCContainerType containerType, SignatureForm signatureForm) {
		DocumentSignatureService service = null;
		signatureForm = SignatureForm.PAdES;
		if (containerType != null) {
			service = (DocumentSignatureService) getASiCSignatureService(signatureForm);
		} else {
			switch (signatureForm) {
			case CAdES:
				service = cadesService;
				break;
			case PAdES:
				service = padesService;
				break;
			case XAdES:
				service = xadesService;
				break;
			case JAdES:
				service = jadesService;
				break;
			default:
				LOG.error("Unknown signature form : " + signatureForm);
			}
		}
		return service;
	}
	
    @SuppressWarnings("rawtypes")
	private CounterSignatureService getCounterSignatureService(boolean isZipContainer, SignatureForm signatureForm) {
        CounterSignatureService service;
		if (isZipContainer) {
            service = (CounterSignatureService) getASiCSignatureService(signatureForm);
        } else {
            switch (signatureForm) {
            case CAdES:
                service = cadesService;
                break;
            case XAdES:
                service = xadesService;
                break;
            case JAdES:
                service = jadesService;
                break;
            default:
                throw new DSSException("Not supported signature form for a counter signature : " + signatureForm);
            }
        }
        return service;
    }

	@SuppressWarnings({ "rawtypes" })
	private AbstractSignatureParameters getSignatureParameters(ASiCContainerType containerType, SignatureForm signatureForm) {
		AbstractSignatureParameters parameters = null;
		if (containerType != null) {
			parameters = getASiCSignatureParameters(containerType, signatureForm);
		} else {
			switch (signatureForm) {
			case CAdES:
				parameters = new CAdESSignatureParameters();
				break;
			case PAdES:
				PAdESSignatureParameters padesParams = new PAdESSignatureParameters();
				padesParams.setContentSize(9472 * 2); // double reserved space for signature
				parameters = padesParams;
				break;
			case XAdES:
				parameters = new XAdESSignatureParameters();
				break;
			case JAdES:
				JAdESSignatureParameters jadesParameters = new JAdESSignatureParameters();
				jadesParameters.setJwsSerializationType(JWSSerializationType.JSON_SERIALIZATION); // to allow T+ levels + parallel signing
	            jadesParameters.setSigDMechanism(SigDMechanism.OBJECT_ID_BY_URI_HASH); // to use by default
				parameters = jadesParameters;
				break;
			default:
				LOG.error("Unknown signature form : " + signatureForm);
			}
		}
		return parameters;
	}
	
    private SerializableCounterSignatureParameters getCounterSignatureParameters(SignatureForm signatureForm) {
        SerializableCounterSignatureParameters parameters = null;
        switch (signatureForm) {
            case CAdES:
                parameters = new CAdESCounterSignatureParameters();
                break;
            case XAdES:
                parameters = new XAdESCounterSignatureParameters();
                break;
            case JAdES:
            	JAdESCounterSignatureParameters jadesCounterSignatureParameters = new JAdESCounterSignatureParameters();
	            jadesCounterSignatureParameters.setJwsSerializationType(JWSSerializationType.FLATTENED_JSON_SERIALIZATION);
	            parameters = jadesCounterSignatureParameters;
                break;
            default:
                LOG.error("Not supported form for a counter signature : " + signatureForm);
        }
        return parameters;
    }

	private TimestampParameters getTimestampParameters(ASiCContainerType containerType, SignatureForm signatureForm) {
		TimestampParameters parameters = null;
		if (containerType == null) {
			switch (signatureForm) {
				case CAdES:
					parameters = new CAdESTimestampParameters();
					break;
				case XAdES:
					parameters = new XAdESTimestampParameters();
					break;
				case PAdES:
					parameters = new PAdESTimestampParameters();
					break;
				case JAdES:
					parameters = new JAdESTimestampParameters();
					break;
				default:
					LOG.error("Not supported form for a timestamp : " + signatureForm);
			}

		} else {
			switch (signatureForm) {
				case CAdES:
					ASiCWithCAdESTimestampParameters asicParameters = new ASiCWithCAdESTimestampParameters();
					asicParameters.aSiC().setContainerType(containerType);
					parameters = asicParameters;
					break;
				case XAdES:
					parameters = new XAdESTimestampParameters();
					break;
				default:
					LOG.error("Not supported form for an ASiC timestamp : " + signatureForm);
			}
		}
		return parameters;
	}

	@SuppressWarnings("rawtypes")
	private MultipleDocumentsSignatureService getASiCSignatureService(SignatureForm signatureForm) {
		MultipleDocumentsSignatureService service = null;
		switch (signatureForm) {
		case CAdES:
			service = asicWithCAdESService;
			break;
		case XAdES:
			service = asicWithXAdESService;
			break;
		default:
			LOG.error("Unknown signature form : " + signatureForm);
		}
		return service;
	}

	@SuppressWarnings({ "rawtypes" })
	private AbstractSignatureParameters getASiCSignatureParameters(ASiCContainerType containerType, SignatureForm signatureForm) {
		AbstractSignatureParameters parameters = null;
		switch (signatureForm) {
		case CAdES:
			ASiCWithCAdESSignatureParameters asicCadesParams = new ASiCWithCAdESSignatureParameters();
			asicCadesParams.aSiC().setContainerType(containerType);
			parameters = asicCadesParams;
			break;
		case XAdES:
			ASiCWithXAdESSignatureParameters asicXadesParams = new ASiCWithXAdESSignatureParameters();
			asicXadesParams.aSiC().setContainerType(containerType);
			parameters = asicXadesParams;
			break;
		default:
			LOG.error("Unknown signature form for ASiC container: " + signatureForm);
		}
		return parameters;
	}
}
