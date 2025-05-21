class SignatureValidationError(Exception):
    """Base exception for signature validation errors."""
    def __init__(self, message="Error validating signature", details=None):
        self.message = message
        self.details = details
        super().__init__(self.message)

class DSServiceConnectionError(SignatureValidationError):
    """Exception raised when there's an error connecting to the DSS service."""
    def __init__(self, message="Error connecting to DSS service", details=None):
        super().__init__(message, details)

class InvalidSignatureDataError(SignatureValidationError):
    """Exception raised when the signature data is invalid or malformed."""
    def __init__(self, message="Invalid signature data provided", details=None):
        super().__init__(message, details)
