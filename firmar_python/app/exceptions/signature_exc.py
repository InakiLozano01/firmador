"""
Signature-related exceptions.
"""

class SignatureError(Exception):
    """Base class for signature-related exceptions."""
    pass

class SignatureValidationError(SignatureError):
    """Raised when signature validation fails."""
    pass

class SignatureCreationError(SignatureError):
    """Raised when signature creation fails."""
    pass

class SignatureVerificationError(SignatureError):
    """Raised when signature verification fails."""
    pass

class SignatureFormatError(SignatureError):
    """Raised when signature format is invalid."""
    pass

class SignatureDataError(SignatureError):
    """Raised when signature data is invalid or missing."""
    pass

class SignatureProcessError(SignatureError):
    """Raised when signature processing fails."""
    pass

class SignatureCertificateError(SignatureError):
    """Raised when there's an issue with the signature certificate."""
    pass
