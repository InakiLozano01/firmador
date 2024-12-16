class DSSBaseException(Exception):
    """Base exception for DSS-related errors"""
    pass

class DSSRequestError(DSSBaseException):
    """Exception raised when there is an error in the DSS API request"""
    pass

class DSSResponseError(DSSBaseException):
    """Exception raised when there is an error in the DSS API response"""
    pass

class DSSSigningError(DSSBaseException):
    """Exception raised when there is an error during document signing"""
    pass

class PDFClosingError(DSSBaseException):
    """Exception raised when there is an error closing the PDF document"""
    pass
