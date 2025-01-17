package eu.europa.esig.dss.web.model;

import eu.europa.esig.dss.enumerations.ASiCContainerType;
import eu.europa.esig.dss.enumerations.SignaturePackaging;
import eu.europa.esig.dss.web.validation.AssertMultipartFile;
import jakarta.validation.constraints.AssertTrue;
import jakarta.validation.constraints.NotNull;
import org.springframework.web.multipart.MultipartFile;

import java.util.Arrays;

public class SignatureDocumentForm extends AbstractSignatureForm implements ContainerDocumentForm {

	@AssertMultipartFile
	private MultipartFile documentToSign;

	@NotNull(message = "{error.signature.packaging.mandatory}")
	private SignaturePackaging signaturePackaging ;

	private ASiCContainerType containerType;

	public MultipartFile getDocumentToSign() {
		return documentToSign;
	}

	public void setDocumentToSign(MultipartFile documentToSign) {
		this.documentToSign = documentToSign;
	}

	public SignaturePackaging getSignaturePackaging() {
		return signaturePackaging;
	}

	public void setSignaturePackaging(SignaturePackaging signaturePackaging) {
		this.signaturePackaging = signaturePackaging;
	}

	@Override
	public ASiCContainerType getContainerType() {
		return containerType;
	}

	public void setContainerType(ASiCContainerType containerType) {
		this.containerType = containerType;
	}

	@AssertTrue(message = "{error.to.sign.file.mandatory}")
	public boolean isDocumentToSign() {
		return (documentToSign != null) && (!documentToSign.isEmpty());
	}

	@Override
	public String toString() {
		return "SignatureDocumentForm{" +
				"documentToSign=" + documentToSign +
				", signaturePackaging=" + signaturePackaging +
				", containerType=" + containerType +
				", signatureForm=" + this.getSignatureForm() +
				", signatureLevel=" + this.getSignatureLevel() +
				", digestAlgorithm=" + this.getDigestAlgorithm() +
				", certificate=" + Arrays.toString(this.getCertificate()) +
				", certificateChain=" + this.getCertificateChain() +
				", encryptionAlgorithm=" + this.getEncryptionAlgorithm() +
				", signatureValue=" + Arrays.toString(this.getSignatureValue()) +
				'}';
	}
}
